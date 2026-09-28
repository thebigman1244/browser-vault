import { lstat, readFile } from 'node:fs/promises';
export const SECURITY_FILE='/run/browser-vault-security/status.json';
export function securityStatus(sample,sessionId,now=Date.now()) {
  const fresh=sample?.version===1&&Number.isFinite(sample.checkedAt)&&sample.checkedAt<=now+5000&&now-sample.checkedAt<180000;
  if(!fresh)return {fresh:false,checkedAt:null,state:'unavailable',message:'Download monitoring is unavailable or out of date.',files:[],engine:null};
  const sameSession=!!sessionId&&sample.sessionId===sessionId;
  const files=sameSession&&Array.isArray(sample.files)?sample.files.slice(0,100).filter(f=>typeof f.name==='string'&&(f.sha256===null||typeof f.sha256==='string'&&/^[a-f0-9]{64}$/.test(f.sha256))).map(f=>({name:f.name.slice(0,500),sha256:f.sha256,size:Number(f.size)||0,status:['pending','not_scanned','error','flagged','no_detection'].includes(f.status)?f.status:'error',scannedAt:Number(f.scannedAt)||null,findings:Array.isArray(f.findings)?f.findings.filter(x=>typeof x==='string').map(x=>x.slice(0,300)).slice(0,8):[]})):[];
  return {fresh:true,checkedAt:sample.checkedAt,state:!sessionId?'idle':sameSession?sample.state:'waiting',message:!sessionId?'Start a session to monitor its Downloads folder.':sameSession?String(sample.message||'').slice(0,500):'Waiting for the scanner to find this session.',files,engine:sample.engine&&{available:sample.engine.available===true,version:String(sample.engine.version||'').slice(0,150),definitionsAt:Number(sample.engine.definitionsAt)||null,definitionsFresh:sample.engine.definitionsFresh===true},limits:{fileMiB:32,batchMiB:128,files:100},scope:'Downloads folder; snapshots only. Files are not executed, removed, or uploaded to a scanning service.'};
}
export async function readSecurity(sessionId,file=SECURITY_FILE){
  try{const stat=await lstat(file);if(!stat.isFile()||stat.uid!==0||(stat.mode&0o022)||stat.size>262144)return securityStatus(null,sessionId);return securityStatus(JSON.parse(await readFile(file,'utf8')),sessionId);}catch{return securityStatus(null,sessionId);}
}
