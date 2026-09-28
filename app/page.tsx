"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Check, ChevronRight, CircleHelp, Cpu, Globe2, HardDrive, KeyRound, Loader2, LockKeyhole, Monitor, Network, Power, Server, Settings2, Shield, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiResponseError, readApiResponse } from "../selfhost/api-response.mjs";
const browsers = [
  { id: "chromium", name: "Chromium", engine: "Blink", letter: "C", color: "#9ccb8a" },
  { id: "firefox", name: "Firefox", engine: "Gecko", letter: "F", color: "#f5ad71" },
  { id: "brave", name: "Brave", engine: "Blink", letter: "B", color: "#ed977f" },
];
const profiles = [
  { id: "light", name: "Light", cpu: 1, ram: 2, hint: "Simple pages" },
  { id: "balanced", name: "Balanced", cpu: 2, ram: 3, hint: "Everyday testing" },
  { id: "power", name: "Power", cpu: 3, ram: 4, hint: "Heavier websites" },
];
type Session = { state: string; browser?: string; profile?: string; viewUrl?: string; expiresAt?: number; startedAt?: number; readyAt?: number; minutes?: number; display?: string; };
type Protection = {ready:boolean;fresh:boolean;checkedAt:number|null;checks:{firewall:boolean;routing:boolean;vpn:boolean;proxy:boolean};reason:string};
type Host = { protection?: Protection; ready: boolean; profiles: string[]; browsers: string[]; session: Session | null; };
type WebTool = { name: string; description: string; inputSchema: object; annotations: {readOnlyHint: boolean}; execute: (input: unknown) => unknown; };
export default function Home() {
  const [browser, setBrowser] = useState("chromium"), [profile, setProfile] = useState("balanced"), [url, setUrl] = useState("");
  const [minutes,setMinutes] = useState(30), [display,setDisplay] = useState("smooth"), [autoOpen,setAutoOpen] = useState(true);
  const pendingTab = useRef<Window|null>(null);
  const [endpoint, setEndpoint] = useState(""), [password, setPassword] = useState("");
  const [cloudflare, setCloudflare] = useState(false);
  const [needsSignIn, setNeedsSignIn] = useState(false);
  const [host, setHost] = useState<Host | null>(null), [session, setSession] = useState<Session | null>(null);
  const [dialog, setDialog] = useState<"connect" | "isolation" | null>(null), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [now, setNow] = useState(Date.now());
  const selected = browsers.find(b => b.id === browser)!, resource = profiles.find(p => p.id === profile)!;
  useEffect(() => { try {setEndpoint(location.origin);}catch{} }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/auth', {cache:'no-store', credentials:'same-origin', signal:controller.signal, headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(readApiResponse).then(auth=>{if(auth?.mode==='cloudflare')setCloudflare(true);}).catch(e=>{if(e.name!=='AbortError'){setMessage(e.message);if(e instanceof ApiResponseError)setNeedsSignIn(e.needsSignIn);}});
    return()=>controller.abort();
  }, []);
  useEffect(()=>{if(cloudflare&&endpoint)void connect();},[cloudflare,endpoint]);
  useEffect(() => { const tick = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(tick); }, []);
  useEffect(() => {
    const context = (document as Document & { modelContext?: { registerTool: (tool: WebTool, options: {signal: AbortSignal}) => unknown } }).modelContext;
    if (!context) return;
    const lifecycle = new AbortController();
    try { Promise.resolve(context.registerTool({name:"configure_browser_session",description:"Select a browser and resource profile. Does not launch a browser or visit a URL.",inputSchema:{type:"object",properties:{browser:{type:"string",enum:browsers.map(b=>b.id)},profile:{type:"string",enum:profiles.map(p=>p.id)}},required:["browser","profile"],additionalProperties:false},annotations:{readOnlyHint:false},execute(input){const value=input as {browser:string;profile:string};if(!browsers.some(b=>b.id===value?.browser)||!profiles.some(p=>p.id===value?.profile))throw new Error("Choose a listed browser and resource profile.");setBrowser(value.browser);setProfile(value.profile);return {...value,launched:false};}}, {signal:lifecycle.signal})).catch(()=>{});}catch{}
    return()=>lifecycle.abort();
  }, []);
  async function api(path: string, method="GET", body?: object) {
    const target=new URL(cloudflare?location.origin:endpoint);
    if(target.protocol!=="https:" && !(target.protocol==="http:" && ["localhost","127.0.0.1"].includes(target.hostname)))throw new Error("Use an HTTPS server address, or localhost for local access.");
    const res=await fetch(`${target.origin}/api${path}`,{method,credentials:'same-origin',headers:{"Content-Type":"application/json","X-Requested-With":"XMLHttpRequest",...(!cloudflare?{"Authorization":`Bearer ${password}`}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(45000),cache:"no-store",redirect:"manual"});
    try { const result=await readApiResponse(res);setNeedsSignIn(false);return result as Host & Session; } catch(e) {if(e instanceof ApiResponseError)setNeedsSignIn(e.needsSignIn);throw e;}
  }
  async function connect(){setBusy(true);setMessage("");try{const result=await api("/status");setHost(result);setSession(result.session);localStorage.setItem("vault-endpoint",new URL(endpoint).origin);setDialog(null);setMessage(result.ready?"Connected to your browser server.":result.protection?.reason||"Waiting for protection checks.");}catch(e){setHost(null);setMessage(e instanceof Error?e.message:"Could not connect. Check the server address and that the VM is running.");}finally{setBusy(false);}}
  async function launch(){
    if(!host){if(cloudflare)await connect();else setDialog("connect");return;}
    if(autoOpen){pendingTab.current=window.open('/preparing.html','_blank');if(pendingTab.current)pendingTab.current.opener=null;}
    setBusy(true);setMessage("");
    try{setSession(await api("/sessions","POST",{browser,profile,url,minutes,display}));}
    catch(e){pendingTab.current?.close();pendingTab.current=null;setMessage(e instanceof Error?e.message:"Launch failed.");}
    finally{setBusy(false);}
  }
  useEffect(()=>{
    if(session?.state==='running'&&session.viewUrl&&pendingTab.current){
      try{if(!pendingTab.current.closed)pendingTab.current.location.replace(session.viewUrl);}catch{}
      pendingTab.current=null;
    }
  },[session?.state,session?.viewUrl]);
  async function reconnectDisplay(){setBusy(true);try{setSession(await api('/sessions/reconnect','POST'));setMessage('Display link refreshed. Open your browser again.');}catch(e){setMessage(e instanceof Error?e.message:'Could not refresh the display link.');}finally{setBusy(false);}}

  useEffect(()=>{
    if(!endpoint||needsSignIn||(!cloudflare&&!password))return;
    let stopped=false;let timer:ReturnType<typeof setTimeout>;
    const pollingStarted=Date.now();
    const pollDelay=()=>session?.state==='starting'||session?.state==='deleting'?(Date.now()-pollingStarted<15000?750:1500):15000;
    const poll=async()=>{try{const result=await api('/status');if(!stopped){setHost(result);setSession(result.session);if(session&&!result.session)setMessage('Session deleted. You can start a fresh browser.');}}catch(e){if(!stopped){setHost(null);setMessage(e instanceof Error?e.message:'Connection interrupted.');}}finally{if(!stopped)timer=setTimeout(poll,pollDelay());}};
    timer=setTimeout(poll,pollDelay());
    return()=>{stopped=true;clearTimeout(timer);};
  },[session?.state,endpoint,password,needsSignIn]);
  async function end(signOut=false){setBusy(true);setMessage('');try{await api('/sessions','DELETE');pendingTab.current?.close();pendingTab.current=null;setSession({state:'deleting'});if(cloudflare&&signOut)location.assign('/cdn-cgi/access/logout');}catch(e){setMessage(e instanceof Error?e.message:'Could not end the session. The server timeout remains active.');}finally{setBusy(false);}}
  const protection=host?.protection;
  const protectionFresh=!!protection?.checkedAt&&now-protection.checkedAt<=45000&&protection.fresh;
  const launchReady=host?.ready&&protectionFresh;
  const available=!host||(host.browsers.includes(browser)&&host.profiles.includes(`${browser}:${profile}`));
  const remaining=session?.expiresAt?Math.max(0,Math.ceil((session.expiresAt-now)/60000)):null;
  return <div className="vault-app">
    <header className="topbar"><a className="brand" href="/" aria-label="Browser Vault home"><span className="brand-icon"><Shield size={21}/></span>browser<span>vault</span><span className="version">VM EDITION · 1.1</span></a>{cloudflare&&<Button variant="ghost" onClick={()=>void end(true)} disabled={busy}>Sign out</Button>}<Button variant="ghost" onClick={()=>setDialog("isolation")}><Shield size={16}/><span className="hide-mobile">Isolation details</span></Button></header>
    <main className="workspace"><div className="heading"><div><div className="eyebrow">YOUR PRIVATE BROWSER VM</div><h1>A fresh browser.<br/><span>A separate space.</span></h1><p>Choose a browser, set its resources, and start a disposable session inside your dedicated browser VM.</p></div><button className={`host-pill ${host?"online":""}`} onClick={()=>cloudflare?void connect():setDialog("connect")}><span className="status-dot"/>{host?"Server connected":"Server not connected"}<ChevronRight size={15}/></button></div>
    <section className={`protection-strip ${protectionFresh&&protection?.ready?'checked':'pending'}`} aria-label="Live protection status">
      <div><Shield size={20}/><strong>{protectionFresh&&protection?.ready?'Protection checks passed':'Waiting for protection checks'}</strong><span>{protectionFresh?'Checked '+Math.max(0,Math.floor((now-protection!.checkedAt!)/1000))+'s ago':'New sessions stay paused until checks return.'}</span></div>
      <div className="protection-chips">{[['vpn','VPN handshake'],['firewall','Browser firewall'],['routing','VPN-only routing'],['proxy','Display service']].map(([key,label])=><span key={key} className={protectionFresh&&protection?.checks[key as keyof Protection['checks']]?'passed':''}>{protectionFresh&&protection?.checks[key as keyof Protection['checks']]?<Check size={14}/>:<CircleHelp size={14}/>} {label}</span>)}</div>
      {protectionFresh&&!protection?.ready&&<p>{protection?.reason}</p>}
    </section>
    {session?<section className="session-panel"><div className="session-toolbar"><div><Monitor size={17}/><strong>{browsers.find(b=>b.id===session.browser)?.name||"Browser"}</strong><span>{session.state==="running"?"Live session":session.state==="deleting"?"Ending session":"Starting browser"}</span></div><div>{remaining!==null&&<span>{Math.floor(Math.max(0,(session.expiresAt!-now)/1000)/60)}:{String(Math.floor(Math.max(0,(session.expiresAt!-now)/1000)%60)).padStart(2,"0")} left</span>}<Button variant="outline" onClick={()=>void end()} disabled={busy||session.state==="deleting"}><Power size={15}/>End session</Button></div></div>{session.state==="running"&&session.viewUrl?<div className="remote-ready"><Monitor size={42}/><h2>Your interactive browser is ready</h2><p>{session.readyAt&&session.startedAt?`Ready in ${((session.readyAt-session.startedAt)/1000).toFixed(1)} seconds. `:""}{session.display==="smooth"?"Smooth display":"Sharper display"} · Keyboard and mouse enabled.</p><a className="remote-open" href={session.viewUrl} target="_blank" rel="noopener noreferrer">Open interactive browser <ArrowUpRight size={20}/></a><Button variant="outline" onClick={reconnectDisplay} disabled={busy}>Refresh display link</Button><p className="remote-help">Keep this launcher to end the session and start a fresh one. Closing the browser tab does not delete it; the session timer still applies.</p><p className="remote-help">Clipboard and file sharing are disabled. If Cloudflare asks you to sign in, complete it in the browser tab.</p></div>:<div className="session-loading"><Loader2 className="spin" size={30}/><h2>{session.state==="deleting"?"Cleaning up your session":"Preparing your browser"}</h2><p>{session.state==="deleting"?"Removing the browser and its temporary profile.":"Starting a fresh browser on your Pi. It will open automatically if a tab was allowed."}</p><p>{session.startedAt?`${Math.max(0,Math.floor((now-session.startedAt)/1000))} seconds elapsed`:""}</p></div>}</section>:<div className="launch-grid"><section className="configuration">
      <div className="section-label"><span>01</span><h2>Choose your browser</h2><span className="section-detail">Desktop · Linux</span></div><RadioGroup value={browser} onValueChange={setBrowser} className="browser-grid" aria-label="Browser">{browsers.map(b=><label key={b.id} className={`browser-card ${browser===b.id?"selected":""}`}><RadioGroupItem value={b.id} id={`browser-${b.id}`} className="choice-radio"/><span className="browser-letter" style={{color:b.color}}>{b.letter}</span><strong>{b.name}</strong><span>{b.engine}</span>{browser===b.id&&<Check className="selected-check" size={16}/>}</label>)}</RadioGroup><p className="field-note">Native ARM64 Linux browsers. Chromium is not the Google Chrome product.</p>
      <div className="section-label resources-title"><span>02</span><h2>Allocate resources</h2><SlidersHorizontal size={16}/></div><RadioGroup value={profile} onValueChange={setProfile} className="profile-grid" aria-label="CPU and memory profile">{profiles.map(p=><label key={p.id} className={`profile-card ${profile===p.id?"selected":""}`}><div><RadioGroupItem value={p.id} id={`profile-${p.id}`}/><strong>{p.name}</strong></div><span>{p.cpu} vCPU <span className="dot-separator">·</span> {p.ram} GB RAM</span><small>{p.hint}</small></label>)}</RadioGroup><div className="resource-meter"><div><Cpu size={17}/><span>CPU allocation</span><strong>{resource.cpu} of 4 vCPU</strong></div><div className="meter"><span style={{width:`${resource.cpu/4*100}%`}}/></div><div><HardDrive size={17}/><span>Memory allocation</span><strong>{resource.ram} of 6.5 GB</strong></div><div className="meter"><span style={{width:`${resource.ram/6.5*100}%`}}/></div><p>Remaining resources support the virtual machine and browser service.</p></div>
      <div className="section-label url-title"><span>03</span><h2>Open a website</h2><span className="section-detail">Optional</span></div><label className="address-field"><Globe2 size={19}/><input aria-label="Website URL" placeholder="https://example.com" value={url} onChange={e=>setUrl(e.target.value)} autoComplete="off" spellCheck={false} inputMode="url"/></label><p className="field-note">The address is sent to your remote browser when you launch.</p>
      <div className="session-options"><label>Display<select aria-label="Display mode" value={display} onChange={e=>setDisplay(e.target.value)}><option value="smooth">Smooth · balanced quality</option><option value="native">Sharper · more display detail</option></select><small>Smooth limits display updates and image quality to reduce streaming work.</small></label><label>Delete session after<select aria-label="Session duration" value={minutes} onChange={e=>setMinutes(Number(e.target.value))}>{[5,15,30].map(n=><option key={n} value={n}>{n} minutes</option>)}</select></label><label className="auto-open"><input type="checkbox" checked={autoOpen} onChange={e=>setAutoOpen(e.target.checked)}/> Open the browser automatically when ready</label></div>
    </section><aside className="launch-summary"><div className="summary-top"><span className="eyebrow">NEW SESSION</span><Monitor size={20}/></div><div className="summary-browser"><span className="browser-letter" style={{color:selected.color}}>{selected.letter}</span><div><h2>{selected.name}</h2><p>Fresh, temporary profile</p></div></div><dl><div><dt>Processing</dt><dd>{resource.cpu} vCPU</dd></div><div><dt>Memory</dt><dd>{resource.ram} GB</dd></div><div><dt>Session limit</dt><dd>{minutes} minutes</dd></div><div><dt>Runs on</dt><dd>Your Raspberry Pi</dd></div></dl><div className="isolation-note"><Shield size={20}/><div><strong>Separated from your desktop</strong><p>Browsers run inside a dedicated virtual machine on your Pi, with access to private networks blocked.</p></div></div><Button className="launch-button" onClick={launch} disabled={busy||!!host&&(!launchReady||!available)}>{busy?<Loader2 className="spin" size={18}/>:<Power size={18}/>} {host?(autoOpen?"Launch & open":"Launch browser"):cloudflare?"Reconnect to your Pi":"Connect your server"}<ChevronRight size={17}/></Button>{host&&!available&&<p className="field-note">This browser and resource profile are not installed on your server.</p>}<p className="summary-foot">Fresh profile every time. One session at a time.</p><button className="text-button" onClick={()=>cloudflare?void connect():setDialog("connect")}><Settings2 size={15}/>{cloudflare?"Reconnect to your Pi":"Server settings"}</button></aside></div>}
    {message&&<div className="notice" role="status"><CircleHelp size={18}/><span>{message}</span>{needsSignIn&&<Button variant="outline" onClick={()=>location.assign("/")}>Sign in again</Button>}<button aria-label="Dismiss message" onClick={()=>setMessage("")}><X size={17}/></button></div>}<div className="bottom-notes"><span><LockKeyhole size={16}/>{cloudflare?"Cloudflare-protected access":"Password-protected access"}</span><span><Network size={16}/>Private-network restrictions · VPN required</span><button onClick={()=>setDialog("isolation")}>How isolation works <ArrowUpRight size={14}/></button></div></main><footer><span>browser vault</span><span>Your machine. Your sessions.</span></footer>
    <Dialog open={dialog!==null} onOpenChange={open=>!open&&setDialog(null)}><DialogContent className="vault-dialog"><DialogHeader><DialogTitle>{dialog==="connect"?"Connect your browser server":"How isolation works"}</DialogTitle><DialogDescription>{dialog==="connect"?"Connect to Browser Vault running inside your dedicated Linux virtual machine.":"A separate browser environment with a clear security boundary."}</DialogDescription></DialogHeader>{dialog==="connect"?<form onSubmit={e=>{e.preventDefault();connect();}} className="connect-form"><label>Server address<input type="url" required placeholder="https://your-machine.your-tailnet.ts.net" value={endpoint} onChange={e=>setEndpoint(e.target.value)}/></label><label>Access key<input type="password" required autoComplete="off" placeholder="Your private server access key" value={password} onChange={e=>setPassword(e.target.value)}/></label><p>The key stays in this page’s memory and is sent only to the server above. Refreshing or closing the page clears it.</p><Button disabled={busy} type="submit">{busy?<Loader2 className="spin" size={17}/>:<KeyRound size={17}/>}Connect</Button>{message&&<p role="status">{message}</p>}<div className="setup-note"><Server size={18}/><p>First-time setup requires the Linux VM, Kasm, and the Browser Vault service. Your Pi stays on; your Windows PC can be off.</p></div></form>:<div className="isolation-details"><p>Websites execute in disposable browser containers inside a dedicated Linux VM on your Raspberry Pi. Your device receives the display and sends keyboard and pointer input.</p><ul><li>Clipboard, file transfers, shared folders, and device forwarding are disabled.</li><li>Browser traffic to the Pi, your home network, and private addresses is blocked.</li><li>End sessions to destroy their browser profiles. Choose a 5-, 15- or 30-minute limit, enforced by the server.</li><li>Keep the Pi, its virtual machine, and browser images updated.</li></ul><p>This is networked isolation, not an air gap or a guarantee against every exploit. Browser Internet traffic must use your WireGuard VPN. If the tunnel disconnects, Internet access is blocked; Pi management stays reachable outside the VPN. Live checks read the VPN handshake, firewall rules, routing and display service every 15 seconds. They are operational checks, not a guarantee against every exploit.</p><p>{cloudflare?"Access requires your authorized Cloudflare sign-in.":"A public link still requires your private access key."}</p></div>}</DialogContent></Dialog>
  </div>;
}
