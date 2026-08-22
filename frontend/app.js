
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
function escapeHtml(s){
 return String(s).replace(/[&<>"']/g,function(m){
   return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m];
 });
}
let data={client:"",items:[],status:"pending"};
let publicAppBase="";

function brl(v){return new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"}).format(Number(v)||0)}
function go(id){
 const target=$("#"+id);
 if(!target){console.warn("Tela não encontrada:",id);return}
 $$(".screen").forEach(x=>x.classList.remove("active"));
 target.classList.add("active");
 $$(".bottom-nav button").forEach(b=>b.classList.toggle("nav-active",b.dataset.go===id));
 window.scrollTo({top:0,behavior:"smooth"});
 if(id==="client") renderClient();
 if(id==="clients") loadClients();
 if(id==="tracking") updateTracking();
 if(id==="settings") loadAccountOverview();
}
$$("[data-go]").forEach(b=>b.onclick=()=>go(b.dataset.go));

function normalizeItem(it){
  let q=Number(it.qty||1); if(!q||q<0) q=1;
  let unit=it.unit!=null?Number(it.unit):Number(it.value||0)/q;
  return {...it,qty:q,unit:unit,value:q*unit};
}
data.items=data.items.map(normalizeItem);

function renderItems(){
 $("#clientName").value=data.client||"";
 data.items=data.items.map(normalizeItem);
 $("#items").innerHTML=data.items.map((it,i)=>`<div class="item">
 <span class="item-num">${i+1}</span>
 <input class="iname" data-i="${i}" value="${escapeHtml(it.name)}">
 <input class="iqty" data-i="${i}" type="number" min="0.01" step="1" value="${it.qty}">
 <input class="iunit" data-i="${i}" type="number" min="0" step=".01" value="${it.unit}">
 <button class="del" data-del="${i}">×</button></div>`).join("");
 $$(".iname").forEach(x=>x.oninput=e=>{data.items[+e.target.dataset.i].name=e.target.value;calc()});
 $$(".iqty").forEach(x=>x.oninput=e=>{let it=data.items[+e.target.dataset.i];it.qty=Number(e.target.value)||1;it.value=it.qty*it.unit;calc()});
 $$(".iunit").forEach(x=>x.oninput=e=>{let it=data.items[+e.target.dataset.i];it.unit=Number(e.target.value)||0;it.value=it.qty*it.unit;calc()});
 $$("[data-del]").forEach(x=>x.onclick=e=>{data.items.splice(+e.target.dataset.del,1);renderItems()});
 calc();
}
function calc(){
 data.items=data.items.map(normalizeItem);
 let t=data.items.reduce((a,b)=>a+(b.qty*b.unit),0);
 $("#total").textContent=brl(t); return t;
}
$("#clientName").oninput=e=>data.client=e.target.value;
$("#addItem").onclick=()=>{data.items.push({name:"Novo serviço",qty:1,unit:0,value:0});renderItems()};
renderItems();

$("#sendBtn").onclick=()=>{
  if(!validateBudget(true))return;data.client=$("#clientName").value||"Cliente";data.status="pending";updateTracking();go("tracking")};
$("#pdfBtn").onclick=async()=>{
  if(!validateBudget(true))return;
  try{
    if(!backendOnline)return alert("Servidor indisponível.");
    if(!adminAuthenticated)return showLogin();
    data.client=$("#clientName").value||"Cliente";
    data.items=data.items.map(normalizeItem);
    const payload={
      id:serverQuote?.id||activeQuoteId||"",
      client:data.client,
      items:data.items,
      notes:$("#notes").value||""
    };
    const r=await fetch(API+"/pdf",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      credentials:"same-origin",
      body:JSON.stringify(payload)
    });
    if(r.status===401){showLogin();return}
    if(!r.ok)throw new Error("Falha ao gerar o PDF.");
    const blob=await r.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;
    a.download=payload.id?`orcamento-${payload.id}.pdf`:"orcamento.pdf";
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
  }catch(e){
    alert("Não consegui gerar o PDF: "+(e.message||e));
  }
};
$("#previewClient").onclick=()=>{
  if(serverQuote?.token) window.open("/q/"+encodeURIComponent(serverQuote.token),"_blank");
  else go("client");
};
$("#acceptDemo").onclick=()=>{data.status="accepted";updateTracking();go("client")};

function renderClient(){
 $("#clientViewName").textContent=data.client||"Cliente";
 if($("#clientQuoteTitle")) $("#clientQuoteTitle").textContent=serverQuote?.id?`Orçamento #${serverQuote.id}`:"Orçamento";
 $("#clientItems").innerHTML=data.items.map(x=>`<div class="client-item"><span>${escapeHtml(x.name)}</span><b>${brl(normalizeItem(x).qty*normalizeItem(x).unit)}</b></div>`).join("");
 $("#clientTotal").textContent=brl(data.items.reduce((a,b)=>a+(normalizeItem(b).qty*normalizeItem(b).unit),0));
 const providerSource=serverQuote?.provider||{
   name:$("#providerName")?.value||"",
   phone:$("#providerPhone")?.value||"",
   doc:$("#providerDoc")?.value||""
 };
 if($("#clientProviderName")) $("#clientProviderName").textContent=providerSource.name||"Prestador";
 if($("#clientProviderPhone")) $("#clientProviderPhone").textContent=providerSource.phone||"";
 if($("#clientProviderDoc")) $("#clientProviderDoc").textContent=providerSource.doc||"";
 const notes=($("#notes")?.value||serverQuote?.notes||"").trim();
 if($("#clientNotesWrap")) $("#clientNotesWrap").style.display=notes?"block":"none";
 if($("#clientNotes")) $("#clientNotes").textContent=notes;
 const badge=$("#statusBadge");
 badge.className="badge "+(data.status==="accepted"?"accepted":data.status==="rejected"?"rejected":"pending");
 badge.textContent=data.status==="accepted"?"ACEITO":data.status==="rejected"?"RECUSADO":"PENDENTE";
 const terminal=data.status==="accepted"||data.status==="rejected";
 if($("#clientAccept")) $("#clientAccept").hidden=terminal;
 if($("#clientReject")) $("#clientReject").hidden=terminal;
 const notice=$("#clientResponseNotice");
 if(notice){
   notice.hidden=!terminal;
   if(terminal){
     const dt=serverQuote?.responseAt?new Date(serverQuote.responseAt):null;
     const when=dt&&!Number.isNaN(dt.getTime())?` em ${dt.toLocaleDateString("pt-BR")} às ${dt.toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})}`:"";
     notice.className=`client-response-notice ${data.status}`;
     notice.innerHTML=data.status==="accepted"?`✓ Orçamento aceito${when}.`:`✕ Orçamento recusado${when}.`;
   }
 }
}
function updateTracking(){
  const currentClient = (serverQuote?.client || data.client || $("#clientName")?.value || "Cliente").trim();
  const currentId = serverQuote?.id || activeQuoteId || "";
  const currentStatus = serverQuote?.status || data.status || "pending";
  const total = serverQuote?.total ?? data.items.map(normalizeItem).reduce((a,b)=>a+(b.qty*b.unit),0);

  if($("#trackTitle")){
    $("#trackTitle").textContent = currentId ? `Orçamento #${currentId}` : "Orçamento";
  }

  if($("#viewedBy")){
    $("#viewedBy").textContent = currentStatus==="accepted"
      ? `Aceito por ${currentClient}`
      : currentStatus==="rejected"
      ? `Recusado por ${currentClient}`
      : `Aguardando ${currentClient}`;
  }

  if($("#viewedAt")){
    $("#viewedAt").textContent = currentStatus==="pending"
      ? `Total ${brl(total)}`
      : "Atualizado agora";
  }

  const s=$("#acceptStep");
  if(!s) return;

  if(currentStatus==="accepted"){
    s.className="step done";
    s.innerHTML=`<i>✓</i><div><b>Aceito por ${escapeHtml(currentClient)}</b><small>O cliente aceitou este orçamento.</small></div>`;
  }else if(currentStatus==="rejected"){
    s.className="step";
    s.innerHTML=`<i>×</i><div><b>Recusado por ${escapeHtml(currentClient)}</b><small>O cliente recusou este orçamento.</small></div>`;
  }else{
    s.className="step";
    s.innerHTML=`<i>○</i><div><b>Aguardando resposta de ${escapeHtml(currentClient)}</b><small>O cliente pode aceitar ou recusar pelo link.</small></div>`;
  }

  // Não mostra link antigo quando ainda não existe orçamento persistido.
  if($("#quoteLink") && serverQuote){
    $("#quoteLink").value = publicUrl(serverQuote);
  }
}
$("#clientAccept").onclick=()=>{data.status="accepted";renderClient();updateTracking()};
$("#clientReject").onclick=()=>{data.status="rejected";renderClient();updateTracking()};




const unitWords={um:1,uma:1,dois:2,duas:2,"três":3,tres:3,quatro:4,cinco:5,seis:6,sete:7,oito:8,nove:9,dez:10};
const qty=s=>unitWords[String(s).toLowerCase()]||parseFloat(String(s).replace(",","."))||1;
const val=s=>parseFloat(String(s).replace(/\./g,"").replace(",",".").replace(/[^\d.]/g,""))||0;
const nice=s=>String(s).trim().replace(/\s+/g," ").replace(/^./,c=>c.toUpperCase());



function smartParse(text){
 const raw=String(text||"").replace(/\s+/g," ").trim();
 let client="Cliente", items=[], notes=[];

 // Trabalha trecho por trecho para não perder um produto ao interpretar outro.
 const parts=raw.split(/[,;.]+/).map(x=>x.trim()).filter(Boolean);

 for(let part of parts){
   // Cliente pode estar em qualquer posição.
   let c=part.match(/\bcliente\s+(?:é\s+|e\s+)?([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,3})\s*$/i);
   if(c){ client=nice(c[1]); continue; }

   if(/^(pagamento|forma de pagamento|pode pagar)\b/i.test(part)){notes.push(nice(part));continue}
   if(/^validade\b/i.test(part)){notes.push(nice(part));continue}

   // "troquei 2 telhas 10 reais cada"
   // "2 telhas a 10 cada"
   // "instalei duas lâmpadas por 20 reais cada"
   let m=part.match(/^(?:(troquei|trocar|instalei|instalar|coloquei|colocar)\s+)?(um|uma|dois|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|\d+)\s+(.+?)\s+(?:a\s+|por\s+)?(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:reais?)?\s*(?:cada|a unidade|unidade)$/i);
   if(m){
     const q=qty(m[2]), u=val(m[4]);
     let name=m[3].trim(), action=(m[1]||"").toLowerCase();
     if(action.startsWith("troc")) name="Troca de "+name;
     else if(action.startsWith("instal")) name="Instalação de "+name;
     else if(action.startsWith("coloc")) name="Colocação de "+name;
     items.push({name:nice(name),qty:q,unit:u,value:q*u});
     continue;
   }

   // "troquei a calha 50 reais", "material 50", "serviço 150"
   m=part.match(/^(.+?)\s+(?:deu\s+|ficou\s+|foi\s+|custou\s+|por\s+)?(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:reais?)?$/i);
   if(m){
     let name=m[1].trim(), u=val(m[2]);
     name=name.replace(/^troquei\s+(?:a|o|as|os)\s+/i,"Troca de ")
              .replace(/^troquei\s+/i,"Troca de ")
              .replace(/^instalei\s+(?:a|o|as|os)\s+/i,"Instalação de ")
              .replace(/^instalei\s+/i,"Instalação de ")
              .replace(/^coloquei\s+(?:a|o|as|os)\s+/i,"Colocação de ")
              .replace(/^coloquei\s+/i,"Colocação de ");
     items.push({name:nice(name),qty:1,unit:u,value:u});
     continue;
   }
 }

 if(!items.length) items=[{name:"Serviço informado — revise antes de enviar",qty:1,unit:0,value:0}];
 return {client,items,notes:notes.join(". ")};
}

async function processSpeech(text){
  try{
    let p=null;
    try{
      const r=await fetch("/api/interpret",{method:"POST",credentials:"same-origin",
        headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});
      if(r.ok) p=await r.json();
    }catch(e){console.warn("IA indisponível; usando interpretador local.",e)}
    if(!p) p=smartParse(text);
    if(p.source==="ollama" || p.source==="groq") document.body.dataset.ai="online";
    window.lastInterpretation={
      id:p.interpretation_id||null,
      originalText:text,
      source:p.source||"local",
      model:p.model||"",
      elapsedMs:p.elapsed_ms||0
    };
    data.client=p.client;
    data.items=p.items;
    data.transcript=text;
    $("#clientName").value=data.client;
    if(p.notes) $("#notes").value=p.notes;
    const box=$("#transcriptBox");
    if(box){
      box.style.display="block";
      box.innerHTML="<b>Você disse:</b><br>"+escapeHtml(text)+"<br><small>Interpretador "+(p.source==="groq"?"IA online":(p.source==="ollama"?"IA local":"interpretador local"))+" · "+p.items.length+" item(ns) · Cliente: "+escapeHtml(p.client)+"</small>";
    }
    renderItems();
    status.textContent="Pronto! Confira o orçamento.";
    mic.classList.remove("listening");
    go("edit");
  }catch(err){
    console.error(err);
    mic.classList.remove("listening");
    status.textContent="Não consegui organizar. Tente novamente.";
    alert("Não consegui interpretar essa frase. Você pode tentar de novo ou editar manualmente.");
  }
}

const mic=$("#micBtn"), status=$("#micStatus");
function typed(){
  const t=prompt("Digite como você falaria normalmente:",
    "Cliente Carlos, instalação de duas tomadas a 80 reais cada, troca de disjuntor 120 reais, material 90.");
  if(!t){status.textContent="Toque para falar";return;}
  status.textContent="Organizando...";
  setTimeout(()=>processSpeech(t),50);
}
if($("#typeBtn")) $("#typeBtn").onclick=typed;
if($("#demoBtn")) $("#demoBtn").onclick=()=>{
  status.textContent="Organizando...";
  setTimeout(()=>processSpeech("Cliente Carlos, instalação de duas tomadas a 80 reais cada, troca de disjuntor 120 reais, material 90."),50);
};

let speechRecognizer=null;
let speechRecording=false;
let speechTranscript="";
let speechStopping=false;

function appendSpeechResult(event){
  for(let i=event.resultIndex;i<event.results.length;i++){
    const phrase=(event.results[i][0]?.transcript||"").trim();
    if(phrase && event.results[i].isFinal){
      speechTranscript+=(speechTranscript?" ":"")+phrase;
    }
  }
}

function setSpeechUI(on){
  speechRecording=on;
  mic.classList.toggle("listening",on);
  status.textContent=on?"Ouvindo… clique novamente para finalizar":"Toque para falar";
}

function makeRecognizer(SR){
  const r=new SR();
  speechRecognizer=r;
  r.lang="pt-BR";
  r.interimResults=true;
  r.continuous=true;
  r.onresult=appendSpeechResult;
  r.onerror=e=>{
    console.warn("SpeechRecognition:",e.error);
    if(["not-allowed","service-not-allowed","audio-capture"].includes(e.error)){
      speechStopping=true; speechRecording=false; speechRecognizer=null;
      mic.classList.remove("listening");
      status.textContent=e.error==="audio-capture"?"Não consegui acessar o microfone.":"Microfone bloqueado. Permita no navegador.";
    }
  };
  r.onend=()=>{
    if(speechRecognizer===r)speechRecognizer=null;
    if(speechRecording && !speechStopping){
      setTimeout(()=>{
        if(speechRecording && !speechStopping && !speechRecognizer){
          try{makeRecognizer(SR).start()}catch(e){console.warn(e)}
        }
      },350);
    }
  };
  return r;
}

async function startSpeech(){
  if(!window.isSecureContext && !["localhost","127.0.0.1"].includes(location.hostname)){
    alert("O microfone precisa de HTTPS. Abra pelo link seguro.");
    return;
  }
  try{
    if(navigator.mediaDevices?.getUserMedia){
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      stream.getTracks().forEach(t=>t.stop());
    }
  }catch(e){
    alert("O navegador bloqueou o microfone. Permita o acesso nas configurações do site.");
    return;
  }
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){alert("Use Chrome/Edge ou o botão Digitar.");return}
  speechTranscript=""; speechStopping=false; setSpeechUI(true);
  try{makeRecognizer(SR).start()}catch(e){setSpeechUI(false);console.warn(e)}
}

function stopSpeech(){
  if(!speechRecording)return;
  speechStopping=true; speechRecording=false; mic.classList.remove("listening");
  status.textContent="Finalizando…";
  const r=speechRecognizer; speechRecognizer=null;
  try{r?.stop()}catch(e){}
  setTimeout(()=>{
    const text=speechTranscript.trim();
    speechTranscript=""; speechStopping=false;
    if(text){status.textContent="Entendi. Organizando…";processSpeech(text)}
    else status.textContent="Não consegui ouvir. Clique no microfone e tente novamente.";
  },450);
}

mic.onclick=async()=>{
  if(speechRecording) stopSpeech();
  else await startSpeech();
};




// ---------- Estado online multiempresa ----------
let activeQuoteId=null;
const oldProcessSpeech=processSpeech;
processSpeech=function(text){
  activeQuoteId=null;
  serverQuote=null;
  oldProcessSpeech(text);
};

// ---------- Backend online v0.7 ----------
const API="/api";
let backendOnline=false;
let serverQuote=null;
let adminAuthenticated=false;

async function api(path, options={}){
  const res=await fetch(API+path,{
    credentials:"same-origin",
    headers:{"Content-Type":"application/json",...(options.headers||{})},
    ...options
  });
  let body={};
  try{body=await res.json()}catch(e){}
  if(!res.ok){
    const err=new Error(body.error||"Erro no servidor");
    err.status=res.status;
    throw err;
  }
  return body;
}

function publicMode(){
  return new URLSearchParams(location.search).has("orcamento");
}

function showLogin(){
  if(publicMode())return;
  $("#loginGate").style.display="grid";
  setTimeout(()=>$("#businessEmail")?.focus(),50);
  initGoogleLogin();
}
function hideLogin(){ $("#loginGate").style.display="none"; }
function authMessage(error="",success=""){
  if($("#loginError")) $("#loginError").textContent=error;
  if($("#loginSuccess")) $("#loginSuccess").textContent=success;
}
function showAuthPanel(which){
  ["loginPanel","registerPanel","forgotPanel","resetPanel"].forEach(id=>$("#"+id)?.classList.toggle("active",id===which));
  $("#authTabLogin")?.classList.toggle("active",which==="loginPanel");
  $("#authTabRegister")?.classList.toggle("active",which==="registerPanel");
  authMessage();
}
$("#authTabLogin")?.addEventListener("click",()=>showAuthPanel("loginPanel"));
$("#authTabRegister")?.addEventListener("click",()=>showAuthPanel("registerPanel"));
$("#backToLogin")?.addEventListener("click",()=>showAuthPanel("loginPanel"));

let googleInitialized=false;
async function initGoogleLogin(){
  if(googleInitialized)return;
  try{
    const cfg=await api("/auth/config");
    if($("#demoBtn")) $("#demoBtn").style.display=cfg.demoEnabled?"inline-flex":"none";
    if(!cfg.googleEnabled){$("#googleUnavailable").style.display="block";return}
    if(!window.google?.accounts?.id){setTimeout(initGoogleLogin,500);return}
    google.accounts.id.initialize({client_id:cfg.googleClientId,callback:handleGoogleCredential});
    google.accounts.id.renderButton($("#googleButton"),{theme:"outline",size:"large",shape:"rectangular",text:"continue_with",width:320,locale:"pt-BR"});
    googleInitialized=true;
  }catch(e){console.warn("Google Sign-In indisponível",e)}
}
async function handleGoogleCredential(response){
  authMessage();
  try{
    await api("/auth/google",{method:"POST",body:JSON.stringify({credential:response.credential})});
    adminAuthenticated=true;hideLogin();await loadProviderServer();await loadAccountProfile();await renderHistoryServer();
  }catch(e){authMessage(e.message||"Não foi possível entrar com Google.")}
}

async function loginAdmin(){
  const email=$("#businessEmail").value.trim();
  const password=$("#adminPassword").value;
  const remember=!!$("#rememberLogin")?.checked;
  authMessage();
  try{
    await api("/login",{method:"POST",body:JSON.stringify({email,password,remember})});
    adminAuthenticated=true;hideLogin();await loadProviderServer();await loadAccountProfile();await renderHistoryServer();
  }catch(e){authMessage(e.message||"Não foi possível entrar.")}
}
$("#loginBtn")?.addEventListener("click",loginAdmin);
$("#adminPassword")?.addEventListener("keydown",e=>{if(e.key==="Enter")loginAdmin()});

async function registerAccount(){
  authMessage();
  const password=$("#registerPassword").value;
  const passwordConfirm=$("#registerPasswordConfirm")?.value||"";
  if(password!==passwordConfirm){authMessage("As senhas não coincidem.");return}
  const payload={name:$("#registerName").value.trim(),businessName:$("#registerBusiness").value.trim(),email:$("#registerEmail").value.trim(),password};
  if(!$("#acceptTerms")?.checked){authMessage("Você precisa aceitar os Termos e a Política de Privacidade.");return}
  try{
    await api("/register",{method:"POST",body:JSON.stringify(payload)});
    adminAuthenticated=true;hideLogin();await loadProviderServer();await loadAccountProfile();await renderHistoryServer();
  }catch(e){authMessage(e.message||"Não foi possível criar sua conta.")}
}
$("#registerBtn")?.addEventListener("click",registerAccount);

$("#forgotBtn")?.addEventListener("click",()=>{$("#forgotEmail").value=$("#businessEmail").value||"";showAuthPanel("forgotPanel")});
$("#sendResetBtn")?.addEventListener("click",async()=>{
  authMessage();
  try{const r=await api("/password/forgot",{method:"POST",body:JSON.stringify({email:$("#forgotEmail").value.trim()})});authMessage("",r.message||"Verifique seu e-mail.")}catch(e){authMessage(e.message||"Não foi possível solicitar a recuperação.")}
});

$("#logoutBtn")?.addEventListener("click",async()=>{try{await api("/logout",{method:"POST"})}catch(e){}adminAuthenticated=false;showAuthPanel("loginPanel");showLogin()});

const resetTokenFromUrl=new URLSearchParams(location.search).get("reset");
if(resetTokenFromUrl){setTimeout(()=>{showLogin();showAuthPanel("resetPanel")},100)}
$("#confirmResetBtn")?.addEventListener("click",async()=>{
  authMessage();
  const p=$("#resetPassword").value, c=$("#resetPasswordConfirm").value;
  if(p!==c){authMessage("As senhas não coincidem.");return}
  try{
    await api("/password/reset",{method:"POST",body:JSON.stringify({token:resetTokenFromUrl,password:p})});
    history.replaceState({},"",location.pathname);
    showAuthPanel("loginPanel");authMessage("","Senha alterada. Agora você pode entrar.");
  }catch(e){authMessage(e.message||"Não foi possível redefinir a senha.")}
});

async function checkBackend(){
  try{
    await api("/health");
    backendOnline=true;
    try{
      const cfg=await api("/auth/config");
      publicAppBase=String(cfg.publicAppUrl||"").replace(/\/$/,"");
      if($("#demoBtn")) $("#demoBtn").style.display=cfg.demoEnabled?"inline-flex":"none";
    }catch(e){}
    document.body.dataset.backend="online";

    if(publicMode()){
      document.body.classList.add("public-mode");
      await bootPublicQuoteServer();
      return;
    }

    const sess=await api("/session");
    adminAuthenticated=!!sess.authenticated;
    if(!adminAuthenticated){
      showLogin();
      return;
    }

    hideLogin();
    await loadProviderServer();
    await loadAccountProfile();
    await renderHistoryServer();
  }catch(e){
    backendOnline=false;
    console.error(e);
    alert("Não foi possível conectar ao servidor do FalaOrçamento.");
  }
}

async function loadProviderServer(){
  if(!backendOnline||!adminAuthenticated)return;
  const p=await api("/provider");
  if($("#providerName")) $("#providerName").value=p.name||"";
  if($("#providerPhone")) $("#providerPhone").value=p.phone||"";
  if($("#providerDoc")) $("#providerDoc").value=p.doc||"";
}

if($("#saveProvider")) $("#saveProvider").onclick=async()=>{
  try{
    const p={
      name:$("#providerName").value.trim(),
      phone:$("#providerPhone").value.trim(),
      doc:$("#providerDoc").value.trim()
    };
    await api("/provider",{method:"POST",body:JSON.stringify(p)});
    $("#saveNotice").style.display="block";
    setTimeout(()=>$("#saveNotice").style.display="none",1800);
  }catch(e){
    if(e.status===401)showLogin();
    else alert("Não consegui salvar: "+e.message);
  }
};

async function renderHistoryServer(){
  if(!adminAuthenticated)return;
  try{
    const list=$("#quoteList");
    const qs=await api("/quotes");
    if(!qs.length){
      list.innerHTML='<div style="padding:18px;text-align:center;color:#7b8293;font-size:12px">Nenhum orçamento salvo ainda.</div>';
      return;
    }
    list.innerHTML=qs.map(q=>`<div class="quote-row online-quote" data-token="${q.token}">
      <b>#${q.id}</b>
      <span>${escapeHtml(q.client)}<small>${q.status==="accepted"?"Aceito":q.status==="rejected"?"Recusado":"Pendente"}</small></span>
      <strong>${brl(q.total)} ›</strong>
    </div>`).join("");
    $$(".online-quote").forEach(el=>el.onclick=async()=>{
      const q=await api("/quotes/"+encodeURIComponent(el.dataset.token));
      applyServerQuote(q,"edit");
    });
  }catch(e){
    if(e.status===401)showLogin(); else console.error(e);
  }
}

function applyServerQuote(q,target="edit"){
  serverQuote=q;
  activeQuoteId=q.id;
  data.client=q.client;
  data.items=(q.items||[]).map(normalizeItem);
  data.status=q.status||"pending";
  $("#notes").value=q.notes||"";
  $("#clientName").value=q.client||"Cliente";
  renderItems();
  updateTracking();
  if(target==="tracking")updateShareBoxServer(q);
  renderClient();
  go(target);
}

function publicUrl(q){
  if(q?.publicUrl) return String(q.publicUrl);
  const base=publicAppBase||location.origin;
  return base+"/q/"+encodeURIComponent(q.token);
}
function updateShareBoxServer(q){
  $("#trackTitle").textContent="Orçamento #"+q.id;
  if($("#quoteLink"))$("#quoteLink").value=publicUrl(q);
}

async function createQuoteServer(){
  data.client=$("#clientName").value||"Cliente";
  data.items=data.items.map(normalizeItem);

  const payload={
    client:data.client,
    items:data.items,
    notes:$("#notes").value||"",
    status:"pending"
  };

  let q;

  // Se já existe um orçamento persistido em edição, atualiza o mesmo registro.
  if(serverQuote?.token){
    q=await api("/quotes/"+encodeURIComponent(serverQuote.token),{
      method:"PATCH",
      body:JSON.stringify(payload)
    });
  }else{
    q=await api("/quotes",{
      method:"POST",
      body:JSON.stringify(payload)
    });
  }

  serverQuote=q;
  activeQuoteId=q.id;
  data.status=q.status;
  await renderHistoryServer();
  updateShareBoxServer(q);
  return q;
}

if($("#sendBtn")) $("#sendBtn").onclick=async()=>{
  const btn=$("#sendBtn");
  if(btn?.dataset.busy==="1")return;

  try{
    if(!backendOnline){
      alert("Servidor indisponível.");
      return;
    }
    if(!adminAuthenticated){
      showLogin();
      return;
    }
    if(window.validateBudget && !validateBudget(true))return;

    if(btn){
      btn.dataset.busy="1";
      btn.disabled=true;
      btn.textContent=serverQuote?.token?"ATUALIZANDO…":"SALVANDO…";
    }

    const q=await createQuoteServer();
    updateShareBoxServer(q);
    go("tracking");
  }catch(e){
    if(e.status===401)showLogin();
    else alert("Não consegui salvar o orçamento: "+e.message);
  }finally{
    if(btn){
      btn.dataset.busy="0";
      btn.disabled=false;
      btn.textContent="ENVIAR NO WHATSAPP";
    }
  }
};

if($("#copyLink")) $("#copyLink").onclick=async()=>{
  const v=$("#quoteLink").value;
  if(!v)return;
  try{
    await navigator.clipboard.writeText(v);
    $("#copyLink").textContent="Copiado!";
    setTimeout(()=>$("#copyLink").textContent="Copiar",1300);
  }catch(e){
    $("#quoteLink").select();
    document.execCommand("copy");
  }
};

if($("#whatsShare")) $("#whatsShare").onclick=()=>{
  if(!serverQuote)return;
  const text=`Olá ${serverQuote.client}! Segue seu orçamento #${serverQuote.id}, no valor de ${brl(serverQuote.total)}.\n\n${publicUrl(serverQuote)}`;
  window.open("https://wa.me/?text="+encodeURIComponent(text),"_blank");
};

async function setServerStatus(status){
  if(!serverQuote)return;
  try{
    const q=await api("/quotes/"+encodeURIComponent(serverQuote.token),{
      method:"PATCH",
      body:JSON.stringify({status})
    });
    serverQuote=q;
    data.status=q.status;
    renderClient();
    updateTracking();
    if(adminAuthenticated)await renderHistoryServer();
  }catch(e){
    if(e.status===409){
      try{
        const q=await api("/quotes/"+encodeURIComponent(serverQuote.token));
        serverQuote=q;data.status=q.status;renderClient();updateTracking();
      }catch(_){}
      alert(e.message||"Este orçamento já recebeu uma resposta.");
      return;
    }
    alert("Não consegui atualizar o status: "+e.message);
  }
}

if($("#clientAccept")) $("#clientAccept").onclick=()=>setServerStatus("accepted");
if($("#clientReject")) $("#clientReject").onclick=()=>setServerStatus("rejected");
if($("#acceptDemo")) $("#acceptDemo").onclick=async()=>{
  await setServerStatus("accepted");
  go("client");
};

async function bootPublicQuoteServer(){
  const token=new URLSearchParams(location.search).get("orcamento");
  if(!token)return;
  try{
    const q=await api("/quotes/"+encodeURIComponent(token));
    serverQuote=q;
    data.client=q.client;
    data.items=(q.items||[]).map(normalizeItem);
    data.status=q.status||"pending";
    $("#notes").value=q.notes||"";
    $("#clientName").value=q.client||"Cliente";
    renderItems();
    renderClient();
    go("client");
  }catch(e){
    console.error("Falha ao abrir orçamento público:",e);
    const home=$("#home");
    if(home){
      $$(".screen").forEach(x=>x.classList.remove("active"));
      home.classList.add("active");
      const mainTitle=home.querySelector("h1");
      if(mainTitle) mainTitle.textContent="Orçamento indisponível";
      const sub=home.querySelector("p");
      if(sub) sub.textContent="Este link não corresponde a um orçamento disponível.";
      const micArea=$("#micBtn")?.parentElement;
      if(micArea) micArea.style.display="none";
    }
  }
}

checkBackend();

if($("#togglePassword")) $("#togglePassword").onclick=()=>{
  const input=$("#adminPassword");
  input.type=input.type==="password"?"text":"password";
  $("#togglePassword").textContent=input.type==="password"?"👁":"🙈";
};


async function checkLocalAI(){
  try{
    const r=await fetch("/api/ai-health",{credentials:"same-origin"});
    const j=await r.json();
    if(j.ok && j.modelAvailable){
      document.body.dataset.ai="online";
      console.log("IA online:",j.provider||"configurada",j.model);
    }else{
      document.body.dataset.ai="offline";
      console.warn("IA/modelo indisponível:",j);
    }
  }catch(e){
    document.body.dataset.ai="offline";
  }
}
if(!publicMode()){
  setTimeout(checkLocalAI,1000);
}


// ---------- Diagnóstico da IA corrigido ----------
async function saveCurrentAsCorrection(){
  const info=window.lastInterpretation;
  if(!info?.id){alert("A interpretação atual não veio da IA ou ainda não possui registro.");return}
  const corrected={
    client:$("#clientName")?.value||data.client||"",
    items:data.items.map(normalizeItem).map(x=>({name:x.name,qty:x.qty,unit:x.unit})),
    notes:$("#notes")?.value||""
  };
  try{
    await api("/interpretations/"+info.id+"/correction",{
      method:"POST",body:JSON.stringify({corrected})
    });
    alert("Correção registrada.");
  }catch(e){alert(e.message||"Não foi possível registrar a correção.")}
}

async function showAIDiagnostics(){
  try{
    const rows=await api("/interpretations");
    const recent=rows.slice(0,10);
    const avg=recent.length?recent.reduce((s,x)=>s+(x.elapsed_ms||0),0)/recent.length:0;
    const corrected=recent.filter(x=>x.corrected).length;
    const lines=recent.map(x=>`#${x.id} · ${((x.elapsed_ms||0)/1000).toFixed(1)}s · ${x.model||x.source}\n${x.text}${x.corrected?"\n✓ corrigido":""}`).join("\n\n");
    alert(`DIAGNÓSTICO DA IA\n\nÚltimas: ${recent.length}\nTempo médio: ${(avg/1000).toFixed(1)}s\nCom correção: ${corrected}${lines?"\n\n"+lines:""}`);
  }catch(e){alert(e.message||"Não foi possível abrir o diagnóstico.")}
}
$("#saveCorrectionBtn")?.addEventListener("click",saveCurrentAsCorrection);
$("#showDiagnosticsBtn")?.addEventListener("click",showAIDiagnostics);

// ---------- Clientes ----------
let cachedClients=[];

async function loadClients(){
  if(!adminAuthenticated)return;
  try{
    cachedClients=await api("/clients");
    renderClients();
  }catch(e){
    if(e.status===401)showLogin();
    else alert(e.message||"Não foi possível carregar os clientes.");
  }
}

function renderClients(){
  const q=($("#clientSearch")?.value||"").toLowerCase().trim();
  const rows=cachedClients.filter(c=>!q||[c.name,c.phone,c.doc,c.email].some(v=>(v||"").toLowerCase().includes(q)));
  const list=$("#clientsList");
  if(!list)return;
  if(!rows.length){
    list.innerHTML='<div class="empty-state">Nenhum cliente encontrado.</div>';
    return;
  }
  list.innerHTML=rows.map(c=>`
    <div class="client-card">
      <div class="client-avatar">${escapeHtml((c.name||"?").trim().charAt(0).toUpperCase())}</div>
      <div class="client-main">
        <b>${escapeHtml(c.name||"")}</b>
        <small>${escapeHtml(c.phone||"Sem telefone")}${c.doc?' · '+escapeHtml(c.doc):''}</small>
      </div>
      <div class="client-actions">
        <button type="button" data-use-client="${c.id}">Usar</button>
        <button type="button" data-edit-client="${c.id}">Editar</button>
        <button type="button" class="danger-link" data-delete-client="${c.id}">Excluir</button>
      </div>
    </div>`).join("");

  $$("[data-use-client]").forEach(b=>b.onclick=()=>useClientInBudget(Number(b.dataset.useClient)));
  $$("[data-edit-client]").forEach(b=>b.onclick=()=>editClient(Number(b.dataset.editClient)));
  $$("[data-delete-client]").forEach(b=>b.onclick=()=>removeClient(Number(b.dataset.deleteClient)));
}

$("#clientSearch")?.addEventListener("input",renderClients);

function clearClientForm(){
  ["clientId","clientFormName","clientFormPhone","clientFormDoc","clientFormEmail","clientFormNotes"].forEach(id=>{
    const el=$("#"+id); if(el)el.value="";
  });
}
function openClientForm(){
  clearClientForm(); $("#clientFormCard").style.display="block"; $("#clientFormName")?.focus();
}
$("#newClientBtn")?.addEventListener("click",openClientForm);
$("#cancelClientBtn")?.addEventListener("click",()=>{$("#clientFormCard").style.display="none";clearClientForm()});

async function saveClient(){
  const id=$("#clientId").value;
  const payload={
    name:$("#clientFormName").value.trim(),
    phone:$("#clientFormPhone").value.trim(),
    doc:$("#clientFormDoc").value.trim(),
    email:$("#clientFormEmail").value.trim(),
    notes:$("#clientFormNotes").value.trim()
  };
  if(!payload.name){alert("Informe o nome do cliente.");return}
  try{
    if(id) await api("/clients/"+id,{method:"PATCH",body:JSON.stringify(payload)});
    else await api("/clients",{method:"POST",body:JSON.stringify(payload)});
    $("#clientFormCard").style.display="none"; clearClientForm(); await loadClients();
  }catch(e){alert(e.message||"Não foi possível salvar o cliente.")}
}
$("#saveClientBtn")?.addEventListener("click",saveClient);

function editClient(id){
  const c=cachedClients.find(x=>x.id===id); if(!c)return;
  $("#clientId").value=c.id; $("#clientFormName").value=c.name||"";
  $("#clientFormPhone").value=c.phone||""; $("#clientFormDoc").value=c.doc||"";
  $("#clientFormEmail").value=c.email||""; $("#clientFormNotes").value=c.notes||"";
  $("#clientFormCard").style.display="block"; $("#clientFormName")?.focus();
}
async function removeClient(id){
  const c=cachedClients.find(x=>x.id===id);
  if(!confirm(`Excluir o cliente ${c?.name||""}?`))return;
  try{await api("/clients/"+id,{method:"DELETE"});await loadClients()}
  catch(e){alert(e.message||"Não foi possível excluir o cliente.")}
}
function useClientInBudget(id){
  const c=cachedClients.find(x=>x.id===id); if(!c)return;
  data.client=c.name;
  $("#clientName").value=c.name;
  go("edit");
}

function validateBudget(show=true){
 const client=($("#clientName")?.value||data.client||"").trim();
 const items=(data.items||[]).map(normalizeItem);
 if(!client||client.toLowerCase()==="cliente"){if(show)alert("Informe o nome do cliente.");return false}
 if(!items.length){if(show)alert("Adicione pelo menos um item.");return false}
 for(let i=0;i<items.length;i++){
  if(!String(items[i].name||"").trim()){if(show)alert(`Informe a descrição do item ${i+1}.`);return false}
  if(!Number.isFinite(Number(items[i].qty))||Number(items[i].qty)<=0){if(show)alert(`Quantidade inválida no item ${i+1}.`);return false}
  if(!Number.isFinite(Number(items[i].unit))||Number(items[i].unit)<0){if(show)alert(`Valor inválido no item ${i+1}.`);return false}
 }
 return true;
}
window.validateBudget=validateBudget;

function resetCurrentQuoteIdentity(){
  serverQuote=null;
  activeQuoteId=null;
  data.status="pending";
}
window.resetCurrentQuoteIdentity=resetCurrentQuoteIdentity;

if($("#toggleRegisterPassword")) $("#toggleRegisterPassword").onclick=()=>{
 const input=$("#registerPassword");input.type=input.type==="password"?"text":"password";$("#toggleRegisterPassword").textContent=input.type==="password"?"👁":"🙈";
};


// ---------- PWA v1.6.10 ----------
if("serviceWorker" in navigator && location.protocol==="https:"){
  window.addEventListener("load",()=>{
    navigator.serviceWorker.register("/service-worker.js").catch(err=>{
      console.warn("Service Worker indisponível:",err);
    });
  });
}


// ---------- Conta, backup e produção v1.6.10 ----------
async function loadAccountOverview(){
  const statsEl=$("#accountStats"), readyEl=$("#productionReadiness");
  if(!adminAuthenticated) return;
  try{
    const stats=await api("/account/stats");
    const total=brl(stats.quotedTotal||0);
    if(statsEl) statsEl.textContent=`${stats.clients} cliente(s) · ${stats.quotes} orçamento(s) · ${total} orçados`;
  }catch(e){ if(statsEl) statsEl.textContent="Resumo indisponível no momento."; }
  try{
    const r=await api("/production-readiness");
    if(readyEl){
      if(r.ready) readyEl.textContent="Ambiente preparado para produção.";
      else {
        const c=r.checks||{}, pending=[];
        if(!c.postgresConfigured) pending.push("PostgreSQL");
        if(!c.googleConfigured) pending.push("Google");
        if(!c.smtpConfigured) pending.push("e-mail");
        if(!c.secureCookie) pending.push("HTTPS");
        readyEl.textContent=`Produção pendente: ${pending.join(", ") || "configurações do servidor"}.`;
      }
    }
  }catch(e){ if(readyEl) readyEl.textContent=""; }
}

$("#exportAccountBtn")?.addEventListener("click",async()=>{
  try{
    const data=await api("/account/export");
    const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;
    a.download=`falaorcamento-backup-${new Date().toISOString().slice(0,10)}.json`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }catch(e){ alert(e.message||"Não foi possível exportar o backup."); }
});


// ---------- Conta e empresa v1.6.28 ----------
async function loadAccountProfile(){
  if(!backendOnline || !adminAuthenticated) return;
  try{
    const p=await api("/account/profile");
    if($("#accountUserName")) $("#accountUserName").value=p.user?.name||"";
    if($("#accountBusinessName")) $("#accountBusinessName").value=p.account?.name||"";
    if($("#accountEmail")) $("#accountEmail").value=p.user?.email||"";
    if($("#accountAuthInfo")){
      const provider=p.user?.auth_provider==="google"?"Google":"E-mail e senha";
      $("#accountAuthInfo").textContent=`Acesso: ${provider}`;
    }
  }catch(e){
    console.warn("Não foi possível carregar a conta",e);
  }
}

$("#saveAccountProfile")?.addEventListener("click",async()=>{
  try{
    const payload={
      userName:$("#accountUserName")?.value.trim()||"",
      businessName:$("#accountBusinessName")?.value.trim()||""
    };
    const r=await api("/account/profile",{
      method:"PATCH",
      body:JSON.stringify(payload)
    });
    if($("#accountUserName")) $("#accountUserName").value=r.user?.name||payload.userName;
    if($("#accountBusinessName")) $("#accountBusinessName").value=r.account?.name||payload.businessName;
    const n=$("#accountSaveNotice");
    if(n){n.style.display="block";setTimeout(()=>n.style.display="none",1800)}
  }catch(e){
    alert(e?.message||"Não foi possível atualizar a conta.");
  }
});

async function loadAiProviderStatus(){
  const el=document.querySelector("#aiProviderStatus");
  if(!el) return;
  try{
    const s=await api("/ai/status");
    if(s.provider==="groq" && s.configured){
      el.textContent=`IA online conectada · Groq · ${s.model||"modelo ativo"}`;
    }else{
      el.textContent="IA online não configurada · usando fallback";
    }
  }catch(e){
    el.textContent="Status da IA indisponível";
  }
}
document.addEventListener("DOMContentLoaded",()=>{ setTimeout(loadAiProviderStatus,800); });
