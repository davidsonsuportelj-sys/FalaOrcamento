
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
function escapeHtml(s){
 return String(s).replace(/[&<>"']/g,function(m){
   return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m];
 });
}
let data={client:"Carlos",items:[
 {name:"Instalação de 2 tomadas",value:160},
 {name:"Troca de disjuntor",value:120},
 {name:"Material",value:90}
],status:"pending"};

function brl(v){return new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"}).format(Number(v)||0)}
function go(id){
 $$(".screen").forEach(x=>x.classList.remove("active")); $("#"+id).classList.add("active");
 $$(".bottom-nav button").forEach(b=>b.classList.toggle("nav-active",b.dataset.go===id));
 window.scrollTo({top:0,behavior:"smooth"}); if(id==="client") renderClient();
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

const sampleQuotes=[
 ["#0023","Carlos","R$ 450,00","Hoje 11:30"],["#0022","João","R$ 1.280,00","Hoje 10:15"],["#0021","Marcos","R$ 320,00","Ontem 16:40"]
];
$("#quoteList").innerHTML=sampleQuotes.map(q=>`<div class="quote-row"><b>${q[0]}</b><span>${q[1]}<small>${q[3]}</small></span><strong>${q[2]} ›</strong></div>`).join("");

$("#sendBtn").onclick=()=>{data.client=$("#clientName").value||"Cliente";data.status="pending";$("#trackTitle").textContent="Orçamento #0023";go("tracking")};
$("#pdfBtn").onclick=()=>window.print();
$("#previewClient").onclick=()=>go("client");
$("#acceptDemo").onclick=()=>{data.status="accepted";updateTracking();go("client")};

function renderClient(){
 $("#clientViewName").textContent=data.client;
 $("#clientItems").innerHTML=data.items.map(x=>`<div class="client-item"><span>${x.name}</span><b>${brl(x.value)}</b></div>`).join("");
 $("#clientTotal").textContent=brl(data.items.reduce((a,b)=>a+(normalizeItem(b).qty*normalizeItem(b).unit),0));
 const badge=$("#statusBadge");
 badge.className="badge "+(data.status==="accepted"?"accepted":data.status==="rejected"?"rejected":"pending");
 badge.textContent=data.status==="accepted"?"ACEITO":data.status==="rejected"?"RECUSADO":"PENDENTE";
}
function updateTracking(){
 const s=$("#acceptStep");
 if(data.status==="accepted"){s.className="step done";s.innerHTML="<i>✓</i><div><b>Aceito por "+data.client+"</b><small>Agora mesmo</small></div>"}
 else if(data.status==="rejected"){s.className="step";s.innerHTML="<i>×</i><div><b>Recusado por "+data.client+"</b><small>Agora mesmo</small></div>"}
 else{s.className="step";s.innerHTML="<i>○</i><div><b>Aguardando resposta</b><small>O cliente pode aceitar ou recusar pelo link.</small></div>"}
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
    data.client=p.client;
    data.items=p.items;
    data.transcript=text;
    $("#clientName").value=data.client;
    if(p.notes) $("#notes").value=p.notes;
    const box=$("#transcriptBox");
    if(box){
      box.style.display="block";
      box.innerHTML="<b>Você disse:</b><br>"+escapeHtml(text)+"<br><small>Interpretador "+(p.source==="ai"?"IA":"local")+" · "+p.items.length+" item(ns) · Cliente: "+escapeHtml(p.client)+"</small>";
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

mic.onclick=()=>{
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){typed();return;}
  mic.classList.add("listening");
  status.textContent="Ouvindo… fale naturalmente";
  const r=new SR(); r.lang="pt-BR"; r.interimResults=false; r.continuous=false;
  r.onresult=e=>{status.textContent="Organizando...";processSpeech(e.results[0][0].transcript)};
  r.onerror=()=>{mic.classList.remove("listening");status.textContent="Não consegui ouvir. Use Digitar para testar.";};
  try{r.start()}catch(e){mic.classList.remove("listening");typed();}
};


// ---------- Persistência local v0.4 ----------
const STORE_QUOTES="falaorcamento_quotes_v04";
const STORE_PROVIDER="falaorcamento_provider_v04";

function getSavedQuotes(){
  try{return JSON.parse(localStorage.getItem(STORE_QUOTES)||"[]")}catch(e){return []}
}
function saveQuotes(list){
  localStorage.setItem(STORE_QUOTES,JSON.stringify(list.slice(0,50)));
}
function providerData(){
  try{return JSON.parse(localStorage.getItem(STORE_PROVIDER)||"{}")}catch(e){return {}}
}
function saveCurrentQuote(){
  const quotes=getSavedQuotes();
  data.items=data.items.map(normalizeItem);
  const total=data.items.reduce((a,b)=>a+(b.qty*b.unit),0);
  const existing=quotes.findIndex(q=>q.id==="0023");
  const q={
    id:"0023", client:data.client||"Cliente",
    items:data.items, total, notes:$("#notes").value||"",
    status:data.status||"pending", updatedAt:new Date().toISOString()
  };
  if(existing>=0) quotes.splice(existing,1);
  quotes.unshift(q); saveQuotes(quotes); renderHistory();
}
function renderHistory(){
  const quotes=getSavedQuotes();
  const list=$("#quoteList");
  if(!list) return;
  const fallback=[
    {id:"0023",client:"Carlos",total:450,updatedAt:new Date().toISOString()},
    {id:"0022",client:"João",total:1280,updatedAt:new Date(Date.now()-3600000).toISOString()},
    {id:"0021",client:"Marcos",total:320,updatedAt:new Date(Date.now()-86400000).toISOString()}
  ];
  const source=quotes.length?quotes:fallback;
  list.innerHTML=source.slice(0,8).map(q=>`<div class="quote-row saved-quote" data-qid="${q.id}">
    <b>#${q.id}</b><span>${escapeHtml(q.client)}<small>${new Date(q.updatedAt).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}</small></span>
    <strong>${brl(q.total)} ›</strong></div>`).join("");
  $$(".saved-quote").forEach(el=>el.onclick=()=>{
    const q=getSavedQuotes().find(x=>x.id===el.dataset.qid);
    if(q){data.client=q.client;data.items=q.items;data.status=q.status||"pending";$("#notes").value=q.notes||"";renderItems();go("edit")}
  });
}
function loadProviderForm(){
  const p=providerData();
  if($("#providerName")) $("#providerName").value=p.name||"João Silva Serviços Elétricos";
  if($("#providerPhone")) $("#providerPhone").value=p.phone||"(11) 99999-9999";
  if($("#providerDoc")) $("#providerDoc").value=p.doc||"12.345.678/0001-90";
}
if($("#saveProvider")) $("#saveProvider").onclick=()=>{
  const p={name:$("#providerName").value.trim(),phone:$("#providerPhone").value.trim(),doc:$("#providerDoc").value.trim()};
  localStorage.setItem(STORE_PROVIDER,JSON.stringify(p));
  $("#saveNotice").style.display="block";
  setTimeout(()=>$("#saveNotice").style.display="none",1800);
  renderClient();
};

// Enhance client rendering with saved provider information.
const originalRenderClient=renderClient;
renderClient=function(){
  originalRenderClient();
  const p=providerData();
  const card=$(".quote-card");
  if(card){
    const paras=card.querySelectorAll("p");
    if(paras[0]){
      paras[0].innerHTML="<b>Prestador</b><br>"+escapeHtml(p.name||"João Silva Serviços Elétricos")+"<br>"+
      escapeHtml(p.phone||"(11) 99999-9999")+"<br>"+escapeHtml(p.doc||"12.345.678/0001-90");
    }
  }
};

// Save when the user sends the quote or when status changes.
const oldSend=$("#sendBtn").onclick;
$("#sendBtn").onclick=()=>{data.client=$("#clientName").value||"Cliente";data.status="pending";saveCurrentQuote();go("tracking")};
const oldAccept=$("#clientAccept").onclick;
$("#clientAccept").onclick=()=>{data.status="accepted";saveCurrentQuote();renderClient();updateTracking()};
const oldReject=$("#clientReject").onclick;
$("#clientReject").onclick=()=>{data.status="rejected";saveCurrentQuote();renderClient();updateTracking()};
$("#acceptDemo").onclick=()=>{data.status="accepted";saveCurrentQuote();updateTracking();go("client")};

loadProviderForm();
renderHistory();


// ---------- Orçamentos individuais e compartilhamento v0.5 ----------
let activeQuoteId=null;

function nextQuoteId(){
  const qs=getSavedQuotes();
  let max=22;
  qs.forEach(q=>{const n=parseInt(q.id,10);if(!isNaN(n))max=Math.max(max,n)});
  return String(max+1).padStart(4,"0");
}
function makeToken(){
  try{
    if(crypto && crypto.randomUUID) return crypto.randomUUID().replace(/-/g,"").slice(0,12);
  }catch(e){}
  return Math.random().toString(36).slice(2,14);
}
function quotePublicUrl(q){
  const base=location.href.split("?")[0].split("#")[0];
  return base+"?orcamento="+encodeURIComponent(q.token||q.id);
}
function findQuoteByToken(token){
  return getSavedQuotes().find(q=>q.token===token || q.id===token);
}
function openSavedQuote(q, target="edit"){
  activeQuoteId=q.id;
  data.client=q.client; data.items=(q.items||[]).map(normalizeItem);
  data.status=q.status||"pending";
  $("#notes").value=q.notes||"";
  renderItems(); updateTracking(); go(target);
}
function saveCurrentQuoteV5(){
  let quotes=getSavedQuotes();
  let id=activeQuoteId || nextQuoteId();
  let existing=quotes.find(q=>q.id===id);
  const total=data.items.map(normalizeItem).reduce((a,b)=>a+b.qty*b.unit,0);
  const q={
    id, token:(existing&&existing.token)||makeToken(),
    client:data.client||"Cliente", items:data.items.map(normalizeItem),
    total, notes:$("#notes").value||"", status:data.status||"pending",
    createdAt:(existing&&existing.createdAt)||new Date().toISOString(),
    updatedAt:new Date().toISOString()
  };
  quotes=quotes.filter(x=>x.id!==id); quotes.unshift(q); saveQuotes(quotes);
  activeQuoteId=id; renderHistoryV5(); updateShareBox(q); return q;
}
function renderHistoryV5(){
  const quotes=getSavedQuotes(), list=$("#quoteList"); if(!list)return;
  if(!quotes.length){renderHistory();return}
  list.innerHTML=quotes.slice(0,10).map(q=>`<div class="quote-row saved-quote-v5" data-qid="${q.id}">
  <b>#${q.id}</b><span>${escapeHtml(q.client)}<small>${new Date(q.updatedAt).toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}</small></span>
  <strong>${brl(q.total)} ›</strong></div>`).join("");
  $$(".saved-quote-v5").forEach(el=>el.onclick=()=>{const q=getSavedQuotes().find(x=>x.id===el.dataset.qid);if(q)openSavedQuote(q)});
}
function updateShareBox(q){
  if(!q && activeQuoteId) q=getSavedQuotes().find(x=>x.id===activeQuoteId);
  if(!q)return;
  $("#trackTitle").textContent="Orçamento #"+q.id;
  if($("#quoteLink")) $("#quoteLink").value=quotePublicUrl(q);
}
$("#copyLink").onclick=async()=>{
  const v=$("#quoteLink").value;
  try{await navigator.clipboard.writeText(v);$("#copyLink").textContent="Copiado!";setTimeout(()=>$("#copyLink").textContent="Copiar",1300)}
  catch(e){$("#quoteLink").select();document.execCommand("copy")}
};
$("#whatsShare").onclick=()=>{
  const q=getSavedQuotes().find(x=>x.id===activeQuoteId); if(!q)return;
  const text=`Olá ${q.client}! Segue seu orçamento #${q.id}, no valor de ${brl(q.total)}.\n\n${quotePublicUrl(q)}`;
  window.open("https://wa.me/?text="+encodeURIComponent(text),"_blank");
};

// Override send: every new send receives its own number/token.
$("#sendBtn").onclick=()=>{
  data.client=$("#clientName").value||"Cliente"; data.status="pending";
  if(!activeQuoteId || !getSavedQuotes().some(q=>q.id===activeQuoteId)) activeQuoteId=null;
  const q=saveCurrentQuoteV5(); updateShareBox(q); go("tracking");
};
$("#clientAccept").onclick=()=>{data.status="accepted";const q=saveCurrentQuoteV5();renderClient();updateTracking();updateShareBox(q)};
$("#clientReject").onclick=()=>{data.status="rejected";const q=saveCurrentQuoteV5();renderClient();updateTracking();updateShareBox(q)};

// New quote when user starts a fresh voice/text capture.
const oldProcessSpeech=processSpeech;
processSpeech=function(text){activeQuoteId=null;oldProcessSpeech(text)};

// Open ?orcamento=TOKEN directly in customer view.
// Works across the same browser in this serverless MVP; true cross-device links require backend.
(function bootSharedQuote(){
 const token=new URLSearchParams(location.search).get("orcamento");
 if(token){
   const q=findQuoteByToken(token);
   if(q){openSavedQuote(q,"client");}
 }
})();
renderHistoryV5();



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
  setTimeout(()=>$("#adminPassword")?.focus(),50);
}
function hideLogin(){
  $("#loginGate").style.display="none";
}

async function loginAdmin(){
  const email=$("#businessEmail").value.trim();
  const password=$("#adminPassword").value;
  $("#loginError").textContent="";
  try{
    await api("/login",{method:"POST",body:JSON.stringify({email,password})});
    adminAuthenticated=true;
    hideLogin();
    await loadProviderServer();
    await renderHistoryServer();
  }catch(e){
    $("#loginError").textContent=e.message||"Não foi possível entrar.";
  }
}
if($("#loginBtn")) $("#loginBtn").onclick=loginAdmin;
if($("#adminPassword")) $("#adminPassword").addEventListener("keydown",e=>{
  if(e.key==="Enter")loginAdmin();
});
if($("#logoutBtn")) $("#logoutBtn").onclick=async()=>{
  try{await api("/logout",{method:"POST"})}catch(e){}
  adminAuthenticated=false;
  showLogin();
};

async function checkBackend(){
  try{
    await api("/health");
    backendOnline=true;
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
  return location.origin+location.pathname+"?orcamento="+encodeURIComponent(q.token);
}
function updateShareBoxServer(q){
  $("#trackTitle").textContent="Orçamento #"+q.id;
  if($("#quoteLink"))$("#quoteLink").value=publicUrl(q);
}

async function createQuoteServer(){
  data.client=$("#clientName").value||"Cliente";
  data.items=data.items.map(normalizeItem);
  const q=await api("/quotes",{
    method:"POST",
    body:JSON.stringify({
      client:data.client,
      items:data.items,
      notes:$("#notes").value||""
    })
  });
  serverQuote=q;
  data.status=q.status;
  await renderHistoryServer();
  updateShareBoxServer(q);
  return q;
}

if($("#sendBtn")) $("#sendBtn").onclick=async()=>{
  try{
    if(!backendOnline)return alert("Servidor indisponível.");
    if(!adminAuthenticated)return showLogin();
    const q=await createQuoteServer();
    go("tracking");
  }catch(e){
    if(e.status===401)showLogin();
    else alert("Não consegui salvar o orçamento: "+e.message);
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
  }catch(e){alert("Não consegui atualizar o status: "+e.message)}
}

if($("#clientAccept")) $("#clientAccept").onclick=()=>setServerStatus("accepted");
if($("#clientReject")) $("#clientReject").onclick=()=>setServerStatus("rejected");
if($("#acceptDemo")) $("#acceptDemo").onclick=async()=>{
  await setServerStatus("accepted");
  go("client");
};

const renderClientBase=renderClient;
renderClient=function(){
  renderClientBase();
  if(serverQuote && serverQuote.provider){
    const paras=$(".quote-card")?.querySelectorAll("p");
    if(paras && paras[0]){
      const p=serverQuote.provider;
      paras[0].innerHTML="<b>Prestador</b><br>"+
        escapeHtml(p.name||"Prestador")+"<br>"+
        escapeHtml(p.phone||"")+"<br>"+
        escapeHtml(p.doc||"");
    }
  }
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
    alert("Este orçamento não foi encontrado ou não está mais disponível.");
  }
}

checkBackend();

if($("#togglePassword")) $("#togglePassword").onclick=()=>{
  const input=$("#adminPassword");
  input.type=input.type==="password"?"text":"password";
  $("#togglePassword").textContent=input.type==="password"?"👁":"🙈";
};

if($("#forgotBtn")) $("#forgotBtn").onclick=()=>{
  alert("Recuperação de senha ainda não está ativa nesta versão. O empresário deve solicitar a redefinição ao administrador do sistema.");
};
