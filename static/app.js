'use strict';
function getLaunchFile(){
  const declared=document.body?.dataset?.launchFile;
  if(['Avvia ClipLab.cmd','Avvia ClipLab.command'].includes(declared))return declared;
  const platform=typeof navigator==='undefined'?'':navigator.userAgentData?.platform||navigator.platform||'';
  return /Win/i.test(platform)?'Avvia ClipLab.cmd':'Avvia ClipLab.command';
}
const launchFile=getLaunchFile();
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const clock = seconds => {const t=Math.max(0,Math.floor(seconds||0));return t>=3600?`${Math.floor(t/3600)}:${String(Math.floor(t/60)%60).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`:`${Math.floor(t/60)}:${String(t%60).padStart(2,'0')}`;};
const timeInput = s => {const v=Number(s||0);return `${Math.floor(v/60)}:${(v%60).toFixed(2).padStart(5,'0')}`;};
const parseTime = s => {const parts=String(s).split(':').map(Number);if(parts.some(n=>!Number.isFinite(n)||n<0)||parts.length>3)throw Error('Usa un tempo come 1:25.50');return parts.reduce((a,b)=>a*60+b,0);};
const state = {projects:[],connection:{connected:false,configured:false},project:null,tab:'youtube',file:null,format:'9:16',editor:null,poll:null,signature:'',loading:false,online:null,legacy:false,tiktok:{connected:false,configured:false}};
const statusLabel = {queued:'In coda',processing:'In elaborazione',ready:'Pronto',error:'Da verificare',cancelled:'Interrotto',suggested:'Da esportare',rendering:'Esportazione…',exported:'MP4 pronto',uploading:'Caricamento…',published:'Pubblicato',transcribing:'Trascrizione…',tracking:'Tracking volti…'};
const badge = s => `<span class="status ${esc(s)}">${s==='published'?icon('check'):''}${statusLabel[s]||esc(s)}</span>`;
const media = (pid,name,download=false) => `/api/projects/${encodeURIComponent(pid)}/media/${encodeURIComponent(name)}${download?'?download=true':''}`;
function setServerStatus(online){
  state.online=online;
  const label=$('#health-label'),connection=$('.connection'),banner=$('#server-status');
  if(label)label.textContent=online?'Sul tuo computer':'Motore scollegato';
  if(connection)connection.classList.toggle('offline',!online);
  if(banner)banner.hidden=online;
}
async function api(path, options={}) {
  let res;
  try{res=await fetch('/api'+path,options);}
  catch(cause){setServerStatus(false);const error=Error(`Il motore locale di ClipLab non risponde. Apri ${launchFile}, poi premi Riprova connessione.`);error.code='SERVER_OFFLINE';error.cause=cause;throw error;}
  setServerStatus(true);
  const data=await res.json().catch(()=>({detail:'Risposta non valida dal server'}));
  if(!res.ok){const error=Error(typeof data.detail==='string'?data.detail:res.status===422?'Controlla i campi: alcuni valori non sono validi.':`Operazione non riuscita (${res.status})`);error.status=res.status;throw error;}
  return data;
}
const post = (path,body) => api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function toast(message,error=false){const el=document.createElement('div');el.className='toast'+(error?' error':'');el.textContent=message;$('#toasts').append(el);setTimeout(()=>el.remove(),7000);}
function loadingButton(button,loading,label){if(!button)return;button.disabled=loading;if(label)button.innerHTML=label;}
function route(){return location.hash.slice(1)||'home';}
function setNav(page){document.querySelectorAll('[data-nav]').forEach(a=>a.classList.toggle('active',a.dataset.nav===page));$('#breadcrumb').innerHTML=`Workspace <span>/</span> ${page==='home'?'Studio':page==='settings'?'Canali social':page==='publishing'?'Pubblicazioni':page==='projects'?'I miei progetti':'Progetto'}`;}
async function loadProjects(){state.projects=await api('/projects');$('#project-count').textContent=state.projects.length;}
async function loadConnection(){const [yt,tt]=await Promise.all([api('/youtube'),api('/tiktok')]);state.connection=yt;state.tiktok=tt;}
function go(hash){if(location.hash==='#'+hash)renderRoute();else location.hash=hash;}

function importPanel(){return `<section class="import-panel" aria-label="Importa un video">
  <div class="panel-heading"><h2>Da dove iniziamo?</h2><span class="step-badge">01 / IMPORTA</span></div>
  <div class="tabs" role="tablist" aria-label="Sorgente video"><button class="tab ${state.tab==='youtube'?'active':''}" role="tab" aria-selected="${state.tab==='youtube'}" data-tab="youtube">${icon('youtube')}Link YouTube</button><button class="tab ${state.tab==='file'?'active':''}" role="tab" aria-selected="${state.tab==='file'}" data-tab="file">${icon('up')}File locale</button></div>
  <form id="import-form">
    <div id="youtube-input" ${state.tab!=='youtube'?'hidden':''}><div class="url-row"><div class="url-wrap">${icon('link')}<input id="video-url" type="url" aria-label="Link del video YouTube" placeholder="Incolla il link del tuo video YouTube…" autocomplete="off"></div><button class="btn primary" type="submit" id="start-youtube">Crea le mie clip ${icon('arrow')}</button></div><p class="help-text">Video singoli, podcast e interviste · fino a 2 ore · qualità sorgente fino a 1080p</p></div>
    <div id="file-input" ${state.tab!=='file'?'hidden':''}><div class="upload-row"><label class="dropzone" id="dropzone" for="video-file">${icon('up')}<div><strong id="filename">Trascina qui il tuo video</strong><span>oppure scegli un file · MP4, MOV, MKV, WEBM · max 2 GB</span></div></label><button class="btn primary" type="submit" id="start-file">Crea le clip ${icon('arrow')}</button></div><input type="file" id="video-file" accept=".mp4,.mov,.mkv,.webm,.m4v" hidden></div>
    <div class="config-row">
      <div class="field"><label>Formato</label><div class="segmented" id="format-options" aria-label="Formato video"><button type="button" class="active" data-format="9:16">9:16</button><button type="button" data-format="1:1">1:1</button><button type="button" data-format="16:9">16:9</button></div></div>
      <div class="field"><label for="duration">Durata indicativa</label><select id="duration"><option value="30">~30 secondi</option><option value="45" selected>~45 secondi</option><option value="60">~60 secondi</option><option value="90">~90 secondi</option></select></div>
      <div class="field"><label for="clip-count">Quante clip?</label><select id="clip-count">${Array.from({length:8},(_,i)=>`<option value="${i+1}" ${i===3?'selected':''}>${i+1} clip</option>`).join('')}</select></div>
      <div class="field"><label for="captions">Sottotitoli</label><select id="captions"><option value="karaoke">Parole evidenziate</option><option value="clean">Bianco essenziale</option><option value="none">Senza sottotitoli</option></select></div>
    </div>
    <details><summary>Lingua e modello di trascrizione</summary><div class="extra-options"><div class="field"><label for="language">Lingua del video</label><select id="language"><option value="auto">Riconosci automaticamente</option><option value="it">Italiano</option><option value="en">Inglese</option><option value="es">Spagnolo</option><option value="fr">Francese</option><option value="de">Tedesco</option></select></div><div class="field"><label for="model">Whisper locale</label><select id="model"><option value="tiny">Tiny · più veloce (~75 MB)</option><option value="base">Base · più veloce (~145 MB)</option><option value="small" selected>Small · più preciso (~465 MB)</option></select></div></div><div class="field" style="margin-top:12px"><label for="glossary">Nomi e termini da riconoscere</label><input id="glossary" maxlength="1500" placeholder="Es. Grand Theft Auto, Liberty City, Tommy Vercetti"></div><p class="help-text">Il modello si scarica una volta. I termini aiutano Whisper senza sostituire il controllo del testo.</p></details>
    <div class="auto-row">${icon('youtube')}<label class="switch"><input type="checkbox" id="auto-publish" ${!state.connection.connected?'disabled':''}>Esporta e carica automaticamente su YouTube</label><a class="text-btn" href="#settings">${state.connection.connected?'Gestisci canale':'Collega un canale →'}</a></div>
    <div class="auto-config" id="auto-config" hidden><div class="field"><label for="auto-privacy">Visibilità su YouTube</label><select id="auto-privacy"><option value="private">Privato · visibile solo a te</option><option value="unlisted">Non in elenco</option><option value="public">Pubblico · pubblica sul canale</option></select></div><div class="field"><label for="auto-kids">Pubblico del contenuto</label><select id="auto-kids"><option value="false">Non destinato ai bambini</option><option value="true">Destinato ai bambini</option></select></div><div class="auto-summary" id="auto-summary"></div></div>
    <p class="rights-note">Usa video tuoi o per cui hai il permesso di creare e pubblicare clip. La viralità non implica diritti di riutilizzo.</p>
  </form>
  </section>`;}

function renderHome(){setNav('home');state.format='9:16';state.file=null;$('#main').innerHTML=`<section class="intro"><div><div class="eyebrow">${icon('spark')}Il tuo studio, senza limiti di abbonamento</div><h1>Un video lungo.<br><em>Tante storie brevi.</em></h1><p>Trova i momenti da raccontare. Trasformali in Shorts.<br>Dal link al tuo canale, direttamente dal computer.</p></div><div class="hero-art" aria-hidden="true"><div class="hero-landscape">${icon('play')}</div><div class="hero-portrait"><span>UNA BUONA IDEA.<br>IN POCHI SECONDI.</span></div>${icon('spark').replace('<svg','<svg class="art-star"')}<span class="art-tag">LONG FORM → SHORT FORM</span></div></section>${importPanel()}<div class="local-banner">${icon('shield')}Elaborazione sul tuo computer. Nessun abbonamento. Nessun credito da acquistare.</div><div class="section-row"><h2>Dal video al tuo prossimo Short</h2><span>UN FLUSSO, TRE PASSAGGI</span></div><section class="workflow"><article class="workflow-card"><span class="number">01</span>${icon('youtube')}<h3>Importa il video</h3><p>Incolla un link YouTube o carica un file dal tuo computer.</p></article><article class="workflow-card"><span class="number">02</span>${icon('cut')}<h3>Trova il momento</h3><p>Whisper trascrive. La selezione locale propone i tagli. Tu puoi rifinirli.</p></article><article class="workflow-card"><span class="number">03</span>${icon('up')}<h3>Portalo sul tuo canale</h3><p>Esporta un MP4 oppure attiva il caricamento automatico su YouTube.</p></article></section>${state.projects.length?`<div class="section-row"><h2>Riprendi da dove eri</h2><a href="#projects" class="text-btn">Tutti i progetti →</a></div><div class="projects-grid">${state.projects.slice(0,3).map(projectCard).join('')}</div>`:''}`;
  bindImport();
}
function projectCard(p){return `<a class="project-card" href="#project/${p.id}"><div class="project-cover">${p.duration?`<img src="${media(p.id,'poster.jpg')}" alt="" loading="lazy">`:icon('cut')}${badge(p.status)}</div><div class="project-info"><h3>${esc(p.title)}</h3><div><span>${new Date(p.created*1000).toLocaleDateString('it-IT',{day:'numeric',month:'short'})}</span><span>${p.duration?clock(p.duration):p.stage}</span></div></div></a>`;}
function renderProjects(){setNav('projects');$('#main').innerHTML=`<div class="page-head"><div><div class="eyebrow">LA TUA LIBRERIA LOCALE</div><h1>I miei progetti</h1><p>I video e le clip restano sul tuo computer.</p></div><a class="btn primary" href="#home">${icon('plus')}Nuovo progetto</a></div>${state.projects.length?`<div class="projects-grid">${state.projects.map(projectCard).join('')}</div>`:`<div class="empty-state">${icon('folder')}<h2>La prima clip ti aspetta.</h2><p>Importa un video per iniziare il tuo primo progetto.</p><a href="#home" class="btn primary">Inizia a creare ${icon('arrow')}</a></div>`}`;}

function setImportTab(tab){state.tab=tab;document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-selected',b.dataset.tab===tab);});$('#youtube-input').hidden=tab!=='youtube';$('#file-input').hidden=tab!=='file';}
function fileSelected(file){if(!file)return;state.file=file;$('#filename').textContent=file.name;setImportTab('file');}
function autoSummary(){const select=$('#auto-privacy');if(!select)return;const privacy=select.options[select.selectedIndex].text;$('#auto-summary').textContent=`Destinazione: ${state.connection.channel?.title||'nessun canale'} · ${privacy}. Avviando il flusso autorizzi il caricamento delle clip selezionate automaticamente.`;}
function bindImport(){
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>setImportTab(b.dataset.tab));
  document.querySelectorAll('[data-format]').forEach(b=>b.onclick=()=>{state.format=b.dataset.format;document.querySelectorAll('[data-format]').forEach(x=>x.classList.toggle('active',x===b));});
  $('#video-file').onchange=e=>fileSelected(e.target.files[0]);
  const drop=$('#dropzone');drop.ondragover=e=>{e.preventDefault();drop.classList.add('dragover');};drop.ondragleave=()=>drop.classList.remove('dragover');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('dragover');fileSelected(e.dataTransfer.files[0]);};
  $('#auto-publish').onchange=e=>{$('#auto-config').hidden=!e.target.checked;autoSummary();};$('#auto-privacy').onchange=autoSummary;
  $('#import-form').onsubmit=async e=>{
    e.preventDefault();if(state.loading)return;
    const options={duration:Number($('#duration').value),count:Number($('#clip-count').value),format:state.format,captions:$('#captions').value,language:$('#language').value,model:$('#model').value,glossary:$('#glossary').value,auto_publish:$('#auto-publish').checked,channel_id:state.connection.channel?.id||'',privacy:$('#auto-privacy').value,made_for_kids:$('#auto-kids').value==='true'};
    const button=state.tab==='youtube'?$('#start-youtube'):$('#start-file');
    try{
      if(state.tab==='file'&&!state.file)throw Error('Scegli prima un file video.');
      if(state.file?.size>2*1024**3&&state.tab==='file')throw Error('Il file supera il limite di 2 GB.');
      if(state.tab==='youtube'&&!$('#video-url').value.trim())throw Error('Incolla il link del video YouTube.');
      state.loading=true;loadingButton(button,true,state.tab==='file'?'Importazione…':'Avvio…');
      let p;
      if(state.tab==='youtube')p=await post('/import/youtube',{...options,url:$('#video-url').value.trim()});
      else {const form=new FormData();form.append('file',state.file);form.append('options',JSON.stringify(options));p=await api('/import/file',{method:'POST',body:form});}
      state.project=p;await loadProjects();go('project/'+p.id);
    }catch(err){toast(err.message,true);}finally{state.loading=false;loadingButton(button,false,`Crea le mie clip ${icon('arrow')}`);}
  };
}

function renderProject(p){setNav('project');const busy=['queued','processing'].includes(p.status);$('#main').innerHTML=`<a href="#projects" class="back">${icon('arrow')}Tutti i progetti</a><div class="page-head project-heading"><div><div class="eyebrow">${p.source_url?'YOUTUBE':'FILE LOCALE'} ${p.duration?' · '+clock(p.duration):''}${p.language?' · '+esc(p.language.toUpperCase()):''}</div><h1>${esc(p.title)}</h1></div><div class="actions">${busy?`<button class="btn ghost small" id="cancel-project">Interrompi</button>`:`<button class="btn ghost icon" id="delete-project" aria-label="Elimina progetto">${icon('trash')}</button>`}${badge(p.status)}</div></div><div id="project-progress">${busy?progressPanel(p):''}</div>${p.error?`<div class="notice error">${esc(p.error)}</div>`:''}${p.notice?`<div class="notice">${esc(p.notice)}</div>`:''}
    ${p.source_file&&p.duration?`<section class="source-grid"><div class="source-panel"><video id="source-video" controls playsinline preload="metadata" poster="${media(p.id,'poster.jpg')}" src="${media(p.id,p.source_file)}"></video><div class="source-meta"><span>Video sorgente</span><span>${p.width} × ${p.height} · ${clock(p.duration)}</span></div></div><div class="transcript-panel"><h3>Trascrizione <span class="muted">${p.segments.length} ${p.segments.length===1?'segmento':'segmenti'}</span></h3><div class="transcript-scroll">${p.segments.length?p.segments.map((s,i)=>`<button class="transcript-line" data-segment="${i}"><time>${clock(s.start)}</time><span>${esc(s.text)}</span></button>`).join(''):`<p class="muted" style="font-size:11px">${busy?'La trascrizione apparirà qui.':'Nessun parlato riconosciuto.'}</p>`}</div></div></section>`:''}
    ${p.clips.length?`<div class="section-row"><h2>${p.clips.length} ${p.clips.length===1?'clip selezionata':'clip selezionate'}</h2><span>SELEZIONE LOCALE · MODIFICABILE</span></div><div class="clips-grid">${p.clips.map((c,i)=>clipCard(p,c,i)).join('')}</div><p class="help-text">Il punteggio considera apertura, densità del parlato e fine frase. Non prevede visualizzazioni o viralità. Apri l’editor per correggere i sottotitoli, rilevare i volti o adattare l’inquadratura. Nessun watermark aggiunto.</p>`:''}`;
  $('#cancel-project')?.addEventListener('click',async()=>{try{await post(`/projects/${p.id}/cancel`,{});toast('Interruzione richiesta. Il passaggio corrente potrebbe richiedere qualche istante.');}catch(e){toast(e.message,true);}});
  $('#delete-project')?.addEventListener('click',async()=>{if(!confirm('Eliminare questo progetto e tutti i relativi video dal computer? I video già su YouTube resteranno sul canale.'))return;try{await api('/projects/'+p.id,{method:'DELETE'});await loadProjects();go('projects');}catch(e){toast(e.message,true);}});
  document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>openEditor(b.dataset.edit));
  document.querySelectorAll('[data-segment]').forEach(b=>b.onclick=()=>{const video=$('#source-video');video.currentTime=p.segments[Number(b.dataset.segment)].start;video.play().catch(()=>{});});
  $('#source-video')?.addEventListener('timeupdate',e=>{const time=e.target.currentTime;document.querySelectorAll('[data-segment]').forEach(b=>{const s=p.segments[Number(b.dataset.segment)];b.classList.toggle('current',time>=s.start&&time<s.end);});});
}
function progressPanel(p){return `<div class="progress-panel"><span class="spinner" aria-hidden="true"></span><h2>${p.clips.length?'Le tue clip stanno prendendo il volo.':'Qui inizia il montaggio.'}</h2><p>Puoi lasciare aperta questa finestra. Il primo utilizzo di Whisper richiede il download gratuito del modello. Il computer deve restare acceso e l’app in esecuzione.</p><div class="progress-line" role="progressbar" aria-valuenow="${p.progress}" aria-valuemin="0" aria-valuemax="100" aria-label="Avanzamento"><span style="width:${p.progress}%"></span></div><div class="progress-meta"><span id="stage-label">${esc(p.stage)}</span><span id="progress-number">${p.progress}%</span></div></div>`;}
function clipCard(p,c,i){const last=c.exports.at(-1);return `<article class="clip-card"><div class="clip-top"><span>CLIP ${String(i+1).padStart(2,'0')}</span>${c.score?`<span class="score" title="${esc(c.reason)}">${icon('spark')}${c.score}/99</span>`:''}${badge(c.status)}</div><h3>${esc(c.title)}</h3><div class="clip-times"><span>${clock(c.start)} → ${clock(c.end)}</span><span>${(c.end-c.start).toFixed(1)} s</span></div>${c.text?`<p class="clip-excerpt">${esc(c.text)}</p>`:''}${c.error?`<div class="clip-error">${esc(c.error)}</div>`:''}<div class="clip-actions"><button class="btn ${last?'ghost':'primary'}" data-edit="${c.id}" ${['queued','processing'].includes(p.status)?'disabled':''}>${icon('edit')}${last?'Apri e pubblica':'Modifica ed esporta'}</button>${last?`<a class="btn ghost icon" href="${media(p.id,last.file,true)}" aria-label="Scarica MP4">${icon('down')}</a>`:''}${c.youtube?`<a class="btn small" href="${esc(c.youtube.url)}" target="_blank" rel="noopener">${icon('youtube')}Apri</a>`:''}</div></article>`;}

function renderSettings(){setNav('settings');const c=state.connection;$('#main').innerHTML=`<div class="page-head"><div><div class="eyebrow">DAL TUO MAC AL TUO CANALE</div><h1>Collega YouTube.</h1><p>Una configurazione gratuita. Poi il flusso è tutto qui.</p></div></div><div class="settings-grid"><section class="settings-panel"><h2>${c.connected?'Il tuo canale è collegato.':'Scegli dove pubblicare.'}</h2>${c.connected?`<div class="channel-connected">${icon('youtube')}<div><strong>${esc(c.channel.title)}</strong><small>${esc(c.channel.id)}</small></div></div><p>Ogni caricamento verifica il canale autorizzato. Puoi scegliere la visibilità per ciascuna clip o per l’intero flusso automatico.</p><button class="btn ghost" id="disconnect-youtube">Scollega dal computer</button><p class="privacy-note">Per revocare anche il consenso su Google, usa <a class="inline-link" href="https://myaccount.google.com/permissions" target="_blank" rel="noopener">Connessioni del tuo account Google</a>.</p>`:`<p>ClipLab usa l’API ufficiale di YouTube. Nessun servizio di pubblicazione a pagamento. La prima volta crea le credenziali OAuth del tuo progetto personale:</p><ol><li>Apri <a class="inline-link" href="https://console.cloud.google.com/projectcreate" target="_blank" rel="noopener">Google Cloud Console</a> e crea un progetto. Per questo flusso non serve attivare servizi a pagamento.</li><li>In <strong>API e servizi → Libreria</strong>, abilita <strong>YouTube Data API v3</strong>.</li><li>In <strong>Google Auth Platform</strong> configura l’app. Se è in test, aggiungi la tua email tra gli utenti di test.</li><li>Crea un <strong>ID client OAuth → App desktop</strong> e scarica il file JSON. Non è una chiave API a pagamento.</li><li>Carica il JSON qui sotto, poi collega l’account. Nel consenso Google scegli il canale giusto, anche se è un Brand Account.</li></ol><label class="btn ghost" for="oauth-file">${icon('up')}${c.configured?'Sostituisci JSON OAuth':'Carica JSON OAuth'}</label><input id="oauth-file" type="file" accept=".json,application/json" hidden><button class="btn primary" id="connect-youtube" ${!c.configured?'disabled':''}>${icon('youtube')}Collega il canale</button>${c.configured?'<p class="help-text">JSON configurato. Ora autorizza il tuo account Google.</p>':''}`}</section><aside><section class="settings-panel"><h2>Zero abbonamenti.</h2><p>Gli strumenti di elaborazione sono gratuiti e funzionano sul tuo computer.</p><div class="cost-list"><div><span>Importazione e taglio</span><b>Gratis</b></div><div><span>Trascrizione Whisper locale</span><b>Gratis</b></div><div><span>Sottotitoli e rendering MP4</span><b>Gratis</b></div><div><span>YouTube Data API</span><b>Quota gratuita</b></div></div><p class="privacy-note">Restano l’uso della tua connessione, dello spazio su disco e dell’energia del computer. I limiti di quota e di caricamento di YouTube possono fermare il flusso: l’app non acquista quote o servizi.</p></section><div class="model-note"><strong>Le credenziali restano sul computer.</strong><br>Il JSON OAuth e i token sono salvati nella cartella privata dell’app. Video e audio non vengono inviati a servizi di trascrizione. Solo le clip che scegli di caricare vengono inviate a YouTube.<br><br>Con un’app OAuth in modalità test Google può chiederti di ricollegare l’account dopo 7 giorni.</div></aside></div>`;
  $('#oauth-file')?.addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const f=new FormData();f.append('file',file);await api('/youtube/config',{method:'POST',body:f});await loadConnection();renderSettings();toast('Configurazione salvata sul computer. Ora collega il canale.');}catch(err){toast(err.message,true);}});
  $('#connect-youtube')?.addEventListener('click',async e=>{loadingButton(e.currentTarget,true);try{const r=await post('/youtube/connect',{});location.href=r.url;}catch(err){loadingButton($('#connect-youtube'),false);toast(err.message,true);}});
  $('#disconnect-youtube')?.addEventListener('click',async()=>{try{await api('/youtube',{method:'DELETE'});await loadConnection();renderSettings();toast('Accesso rimosso dal computer.');}catch(err){toast(err.message,true);}});
}

async function pollProject(){const current=route();if(!current.startsWith('project/'))return;const pid=current.split('/')[1];try{const p=await api('/projects/'+pid);if(route()!==current)return;state.project=p;const signature=JSON.stringify([p.status,p.error,p.duration>0,p.clips,p.segments.length,p.notice]);if(signature!==state.signature){state.signature=signature;renderProject(p);}else if(['queued','processing'].includes(p.status)){const bar=$('.progress-line');if(bar){bar.setAttribute('aria-valuenow',p.progress);bar.firstElementChild.style.width=p.progress+'%';$('#stage-label').textContent=p.stage;$('#progress-number').textContent=p.progress+'%';}}syncEditor();if(['ready','error','cancelled'].includes(p.status))await loadProjects();}catch(e){if(e.code!=='SERVER_OFFLINE')toast(e.message,true);}finally{clearTimeout(state.poll);if(route().startsWith('project/'))state.poll=setTimeout(pollProject,1800);}}
async function renderRoute(){clearTimeout(state.poll);if($('#editor').open&&!closeEditor())return;const r=route();if(r.startsWith('project/')){state.signature='';$('#main').innerHTML='<div class="page-loading"><span class="spinner"></span><p>Caricamento progetto…</p></div>';await pollProject();}else if(r==='settings'){await loadConnection();renderSettings();}else {await loadProjects();if(r==='projects')renderProjects();else renderHome();}}
window.addEventListener('hashchange',()=>{if(!state.legacy)renderRoute().catch(e=>{if(e.code!=='SERVER_OFFLINE')toast(e.message,true);});});
let checkingServer=false;
async function checkServer(){
  if(checkingServer||state.legacy)return;
  checkingServer=true;
  const wasOffline=state.online===false;
  try{
    await api('/health',{signal:AbortSignal.timeout(4000)});
    if(wasOffline){
      await Promise.all([loadProjects(),loadConnection()]);
      if($('#offline-start'))await renderRoute();
      else if(route().startsWith('project/'))await pollProject();
      else if(route()==='projects')renderProjects();
      else if(route()==='settings')renderSettings();
    }
  }catch(e){if(e.code!=='SERVER_OFFLINE')toast(e.message,true);}
  finally{checkingServer=false;}
}
$('#reconnect-server').addEventListener('click',checkServer);
window.addEventListener('focus',checkServer);
setInterval(checkServer,8000);
function showLegacyServer(version){
  state.legacy=true;
  $('#health-label').textContent='Versione precedente';
  $('#main').innerHTML=`<div class="notice" id="legacy-start"><h2>Riapri ClipLab dal comando di avvio</h2><p>Questa finestra è collegata alla versione ${esc(version||'precedente')}. Apri <strong>${esc(launchFile)}</strong> nella cartella ClipLab.</p><p>Il comando trova l’app aggiornata e apre il suo indirizzo nel browser. Puoi poi chiudere questa finestra.</p></div>`;
}
async function init(){
  try{
    const health=await api('/health');
    if($('#app-version'))$('#app-version').textContent='V'+health.version;
    if($('#sidebar-version'))$('#sidebar-version').textContent='computer · V'+health.version;
    if(!health.application&&health.local&&health.paid_services===false){showLegacyServer(health.version);return;}
    await Promise.all([loadProjects(),loadConnection()]);await renderRoute();
    if(new URLSearchParams(location.search).has('connected')){toast('Canale YouTube collegato.');history.replaceState(null,'','/#settings');}
  }catch(e){$('#main').innerHTML=`<div id="offline-start" class="notice error">${esc(e.message)}</div>`;}
}
init();
