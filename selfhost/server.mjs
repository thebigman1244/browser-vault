import http from 'node:http';
import https from 'node:https';
import { readFile, writeFile, rename, mkdir } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { X509Certificate } from 'node:crypto';
import { createAuthenticator } from './auth.mjs';
import { readProtection } from './protection.mjs';
import { readSecurity } from './security.mjs';
import { websiteUrl, sessionMinutes, displaySettings } from './session-policy.mjs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root=path.dirname(fileURLToPath(import.meta.url));
const config=JSON.parse(readFileSync(process.env.VAULT_CONFIG || '/etc/browser-vault/config.json','utf8'));
const auth=await createAuthenticator(config);
const stateDir=process.env.VAULT_STATE || '/var/lib/browser-vault';
const staticDir=process.env.VAULT_STATIC || path.join(root,'public');
const healthFile=process.env.VAULT_HEALTH;
const stateFile=path.join(stateDir,'session.json');
await mkdir(stateDir,{recursive:true,mode:0o700});
let session=null, busy=false;
try{session=JSON.parse(await readFile(stateFile,'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
// A saved display token can be invalid after a Kasm restart. Refresh it on recovery.
if(session)delete session.viewUrl;
const allowed=new Set(config.allowedOrigins);
const missing=()=>!config.kasmApiKey||!config.kasmApiSecret||!config.kasmUserId||!config.isolationVerified;
class PublicError extends Error {constructor(message,status=400){super(message);this.status=status;}}
function kasm(endpoint,body={}){
  return new Promise((resolve,reject)=>{
    let cert;
    try{cert=readFileSync(config.kasmCertificate);}catch{return reject(new PublicError('The browser server certificate has not been configured.',503));}
    const fingerprint=new X509Certificate(cert).fingerprint256;
    const payload=JSON.stringify({api_key:config.kasmApiKey,api_key_secret:config.kasmApiSecret,...body});
    const req=https.request(new URL('/api/public/'+endpoint,config.kasmOrigin),{method:'POST',ca:cert,checkServerIdentity:(_host,peer)=>peer.fingerprint256===fingerprint?undefined:new Error('Browser server certificate changed'),headers:{'content-type':'application/json','content-length':Buffer.byteLength(payload)},timeout:35000},res=>{
      let data='';res.setEncoding('utf8');res.on('data',chunk=>{data+=chunk;if(data.length>2_000_000)req.destroy(new Error('Response too large'));});
      res.on('end',()=>{try{const result=JSON.parse(data);if(result.error_message){const error=new PublicError(/invalid kasm_id/i.test(result.error_message)?'Session no longer exists.':'The browser service rejected the request. Check its configuration or available resources.',502);error.gone=/invalid kasm_id/i.test(result.error_message);return reject(error);}if(res.statusCode!==200)return reject(new PublicError('Browser service unavailable.',502));resolve(result);}catch(e){reject(e);}});
    });req.on('timeout',()=>req.destroy(new Error('Browser service timeout')));req.on('error',reject);req.end(payload);
  });
}
async function persist(){const tmp=stateFile+'.tmp';await writeFile(tmp,JSON.stringify(session),{mode:0o600});await rename(tmp,stateFile);}
function publicSession(){if(!session)return null;return {state:session.state,browser:session.browser,profile:session.profile,display:session.display||'native',minutes:session.minutes||30,startedAt:session.startedAt,readyAt:session.readyAt,viewUrl:session.state==='running'?session.viewUrl:undefined,expiresAt:session.expiresAt};}
function viewUrl(relative){const base=new URL(config.kasmPublicOrigin);const result=new URL(relative,base);if(result.origin!==base.origin||result.protocol!=='https:')throw new Error('Unexpected remote-view origin');return result.href+(result.hash.includes('?')?'&':'?')+'disable_tips=1&disable_viewers=1';}
async function updateSession(refreshView=false){
  if(!session)return;
  try{
    if(session.expiresAt<=Date.now()&&session.state!=='deleting'){await kasm('destroy_kasm',{user_id:config.kasmUserId,kasm_id:session.id});session.state='deleting';await persist();}
    const result=await kasm('get_kasm_status',{user_id:config.kasmUserId,kasm_id:session.id});
    const status=result.kasm?.operational_status || result.operational_status;
    if(session.state!=='deleting'&&status==='running'&&(session.state!=='running'||!session.viewUrl||refreshView)){session.state='running';session.readyAt ||= Date.now();session.viewUrl=viewUrl(result.kasm_url);await persist();}
    if(['error','failed'].includes(status))throw new PublicError('The browser failed to start. End the session and try another profile.',502);
  }catch(e){if(e.gone){session=null;await persist();}else throw e;}
}
function validated(fn,value){try{return fn(value);}catch(e){throw new PublicError(e.message);}}
const attempts=new Map();
function rateAllowed(ip){const now=Date.now();let item=attempts.get(ip);if(!item||item.until<now)item={count:0,until:now+60000};item.count++;attempts.set(ip,item);if(attempts.size>5000){for(const [key,item]of attempts)if(item.until<now)attempts.delete(key);}return item.count<=60;}
function send(res,status,body){res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(body));}
async function body(req){let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>8192)throw new PublicError('Request too large.',413);}try{return JSON.parse(raw);}catch{throw new PublicError('Invalid request.',400);}}
const server=http.createServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Permissions-Policy','camera=(), microphone=(), geolocation=(), usb=(), clipboard-read=(), clipboard-write=()');
  const origin=req.headers.origin;
  if(origin&&!allowed.has(origin))return send(res,403,{error:'This site is not allowed to connect to the server.'});
  if(origin){res.setHeader('Access-Control-Allow-Origin',origin);res.setHeader('Vary','Origin');res.setHeader('Access-Control-Allow-Headers','Authorization, Content-Type, X-Requested-With');res.setHeader('Access-Control-Allow-Methods','GET, POST, DELETE, OPTIONS');}
  if(req.method==='OPTIONS'){res.writeHead(204);res.end();return;}
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(auth.mode==='cloudflare'&&!await auth.verify(req.headers))return send(res,401,{error:'Sign in through Cloudflare to use Browser Vault.'});
  if(pathname==='/api/auth'&&req.method==='GET')return send(res,200,{mode:auth.mode});
  if(!pathname.startsWith('/api/')){
    if(!['GET','HEAD'].includes(req.method))return send(res,405,{error:'Method not allowed.'});
    try{
      const relative=['/','/desktop','/security'].includes(decodeURIComponent(pathname))?'index.html':decodeURIComponent(pathname).slice(1);
      const file=path.resolve(staticDir,relative);
      if(!file.startsWith(path.resolve(staticDir)+path.sep))return send(res,404,{error:'Not found.'});
      let data;
      if(/\bgzip\b/.test(req.headers['accept-encoding']||'')&&!/gzip\s*;\s*q=0(?:\D|$)/.test(req.headers['accept-encoding']||'')){
        try{data=await readFile(file+'.gz');res.setHeader('Content-Encoding','gzip');}catch{}
      }
      data ||= await readFile(file);
      const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2','.txt':'text/plain'}[path.extname(file)]||'application/octet-stream';
      res.setHeader('Vary',origin?'Origin, Accept-Encoding':'Accept-Encoding');
      if(/^assets\/[\w.-]+-[\w-]+\.(js|css)$/.test(relative))res.setHeader('Cache-Control','private, max-age=31536000, immutable');
      res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self' https: http://localhost:* http://127.0.0.1:*; frame-src https:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
      res.writeHead(200,{'Content-Type':mime});res.end(req.method==='HEAD'?undefined:data);
    }catch{send(res,404,{error:'Not found.'});}return;
  }
  if(!rateAllowed(req.socket.remoteAddress))return send(res,429,{error:'Too many requests. Wait one minute.'});
  if(auth.mode==='key'&&!await auth.verify(req.headers))return send(res,401,{error:'The access key is incorrect.'});
  if(busy)return send(res,409,{error:'Another operation is in progress. Try again in a moment.'});
  busy=true;
  try{
    if(pathname==='/api/status'&&req.method==='GET'){
      if(!missing())await updateSession();
      const protection=await readProtection(healthFile);
      return send(res,200,{ready:!missing()&&protection.ready,version:'1.2',protection,browsers:[...new Set(Object.keys(config.workspaces).map(k=>k.split(':')[0]))],profiles:Object.keys(config.workspaces),session:publicSession()});
    }
    if(pathname==='/api/security'&&req.method==='GET')return send(res,200,{protection:await readProtection(healthFile),downloads:await readSecurity(session?.id,process.env.VAULT_SECURITY)});
    if(pathname==='/api/security/rescan'&&req.method==='POST'){
      if(!session||session.state!=='running')throw new PublicError('Start a session before requesting a scan.',409);
      await writeFile(path.join(stateDir,'scan-request.json'),JSON.stringify({requestedAt:Date.now()}),{mode:0o600});
      return send(res,202,{queued:true,message:'Scan requested. The monitor checks for requests every 30 seconds.'});
    }
    if(missing())throw new PublicError('Complete the server setup and isolation checks before launching.',503);
    if(pathname==='/api/sessions'&&req.method==='POST'){
      await updateSession();if(session)throw new PublicError('End the current session before starting another.',409);
      const protection=await readProtection(healthFile);if(!protection.ready)throw new PublicError(protection.reason,503);
      const input=await body(req);const key=`${input.browser}:${input.profile}`;const workspace=config.workspaces[key];if(!workspace)throw new PublicError('That browser and resource profile are not installed.');
      const target=input.browser==='desktop'?'about:blank':validated(websiteUrl,input.url),minutes=validated(sessionMinutes,input.minutes),environment=validated(displaySettings,input.display);
      const startedAt=Date.now();
      const result=await kasm('request_kasm',{user_id:config.kasmUserId,image_id:workspace.id,enable_sharing:false,kasm_url:target,environment});
      if(!result.kasm_id)throw new Error('No session ID returned');
      session={id:result.kasm_id,state:'starting',browser:input.browser,profile:input.profile,display:input.display||'smooth',minutes,startedAt,expiresAt:startedAt+minutes*60000};await persist();return send(res,201,publicSession());
    }
    if(pathname==='/api/sessions/reconnect'&&req.method==='POST'){
      await updateSession(true);if(!session||session.state!=='running')throw new PublicError('No running session to reconnect to.',409);
      return send(res,200,publicSession());
    }
    if(pathname==='/api/sessions/extend'&&req.method==='POST'){
      await updateSession();if(!session||session.state!=='running')throw new PublicError('No running session to extend.',409);
      const deadline=Math.min(session.startedAt+30*60000,session.expiresAt+5*60000);
      if(deadline<=session.expiresAt)throw new PublicError('This session already has the maximum 30-minute lifetime.',409);
      session.expiresAt=deadline;await persist();return send(res,200,publicSession());
    }
    if(pathname==='/api/sessions'&&req.method==='DELETE'){
      if(session){try{await kasm('destroy_kasm',{user_id:config.kasmUserId,kasm_id:session.id});session.state='deleting';}catch(e){if(e.gone)session=null;else throw e;}await persist();}return send(res,202,{state:'deleting'});
    }
    send(res,404,{error:'Not found.'});
  }catch(e){send(res,e.status||502,{error:e instanceof PublicError?e.message:'Could not contact the browser service. Check the VM and service are running.'});}finally{busy=false;}
});
setInterval(async()=>{if(!session||busy||missing())return;if(session.expiresAt>Date.now()&&session.state!=='deleting')return;busy=true;try{await updateSession();}catch{console.error('Session cleanup will retry.');}finally{busy=false;}},15000).unref();
server.listen(config.port||8080,'0.0.0.0',()=>console.log('Browser Vault service ready. Authentication required for browser operations.'));
