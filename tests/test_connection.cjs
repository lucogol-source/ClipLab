const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const elements = new Map();
function element(selector){
  if(!elements.has(selector))elements.set(selector,{textContent:'',hidden:true,classList:{toggle(){}}});
  return elements.get(selector);
}
const context = vm.createContext({document:{querySelector:element},fetch:async()=>{throw TypeError('Failed to fetch');}});
const source = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8').split('const post =')[0];
vm.runInContext(source,context);

(async()=>{
  await assert.rejects(vm.runInContext("api('/import/youtube',{method:'POST'})",context), error=>error.code==='SERVER_OFFLINE'&&error.message.includes('Avvia ClipLab.command'));
  assert.equal(element('#server-status').hidden,false);
  assert.equal(element('#health-label').textContent,'Motore scollegato');
  let calls=0;
  context.fetch=async()=>{calls++;return {ok:true,json:async()=>({ok:true})};};
  assert.equal((await vm.runInContext("api('/health')",context)).ok,true);
  assert.equal(calls,1);
  assert.equal(element('#server-status').hidden,true);
  context.fetch=async()=>({ok:false,status:400,json:async()=>({detail:'Link YouTube non valido'})});
  await assert.rejects(vm.runInContext("api('/import/youtube')",context), error=>error.status===400&&error.message==='Link YouTube non valido');
  assert.equal(element('#server-status').hidden,true);
  console.log('PASS: errore di rete chiaro, ripristino connessione, errore HTTP distinto, nessun reinvio automatico.');
})().catch(error=>{console.error(error);process.exitCode=1;});
