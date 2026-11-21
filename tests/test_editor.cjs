const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const elements=new Map();
function element(selector){
  if(!elements.has(selector))elements.set(selector,{open:true,value:'',innerHTML:'',textContent:'',addEventListener(){},classList:{toggle(){}}});
  return elements.get(selector);
}
const clip={id:'c',status:'error',edit_revision:1,start:0,end:20,exports:[],error:'Whisper non disponibile'};
const context=vm.createContext({document:{querySelector:element,querySelectorAll:()=>[]},$ :element,
  state:{project:{clips:[clip]},editor:'c'},confirm:()=>true,toast(){},esc:String,
  statusLabel:{error:'Errore'},api:async()=>{throw Error('Unexpected API call');},post:async()=>{throw Error('Richiesta rifiutata');}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/editor.js'),'utf8'),context);
vm.runInContext("needsExport=()=>false;renderCaptionRows=()=>{};pollProject=async()=>{};editSession={pid:'p',cid:'c',awaitTrack:null,awaitTranscript:true,transcriptRevision:1,cues:[],captionStart:0,captionEnd:10,cuesDirty:true}",context);
vm.runInContext('syncEditor()',context);
assert.equal(vm.runInContext('editSession.awaitTranscript',context),false);
assert.match(element('#export-state').innerHTML,/Whisper non disponibile/);
(async()=>{
  let sent;
  context.api=async(url,opts)=>{
    if(opts?.method==='PATCH'&&url.endsWith('/captions'))sent=JSON.parse(opts.body);
    return {cues:[{start:10,end:20,text:'Parte aggiunta.'}]};
  };
  vm.runInContext("editorSettings=()=>({start:0,end:20,title:'Clip'});editSession.awaitTranscript=false",context);
  await vm.runInContext('saveEditor()',context);
  assert.equal(sent.end,10,'Le correzioni devono coprire il tratto effettivamente rivisto.');
  assert.equal(vm.runInContext('editSession.captionEnd',context),20);
  assert.equal(vm.runInContext('editSession.cues[0].text',context),'Parte aggiunta.');
  await vm.runInContext('retranscribeCurrent()',context);
  assert.equal(vm.runInContext('editSession.awaitTranscript',context),false,'Una richiesta rifiutata non deve lasciare l’editor in attesa.');
  console.log('PASS: ritrascrizione fallita/rifiutata senza attesa persistente; ampliamento del taglio con traccia aggiornata.');
})().catch(e=>{console.error(e);process.exitCode=1;});
