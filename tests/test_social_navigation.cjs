const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname,'..');
async function check(platform) {
  const elements = new Map();
  const element = name => {
    if (!elements.has(name)) elements.set(name,{
      value:'',textContent:'',innerHTML:'',dataset:{},open:false,hidden:false,
      options:[{text:'Privato'}],selectedIndex:0,
      addEventListener(name,handler){this["on"+name]=handler;},append(){},classList:{toggle(){}}
    });
    return elements.get(name);
  };
  let authorizationCalls = 0;
  const location={hash:'#settings',port:'8765',href:''};
  const context=vm.createContext({
    document:{querySelector:element,querySelectorAll:()=>[],createElement:()=>element('section'),
      body:{dataset:{launchFile:'Avvia ClipLab.'+(platform==='Win32'?'cmd':'command')}}},
    navigator:{platform},window:{addEventListener(){}},location,
    setInterval(){},setTimeout(){},clearTimeout(){},
    fetch:async url=>({ok:true,json:async()=>{
      if(url==='/api/youtube/connect'){authorizationCalls++;return {url:'https://accounts.google.com/test'};}
      return {connected:false,configured:true};
    }})
  });
  for (const file of ['app.js','editor.js','publishing.js']) {
    const code=fs.readFileSync(path.join(root,'static',file),'utf8').replace(/\ninit\(\);\s*$/,'');
    vm.runInContext(code,context,{filename:file});
  }
  await vm.runInContext('renderRoute()',context);
  assert.match(element('#main').innerHTML,/Collega YouTube/);
  assert.equal(element('#main h1').textContent,'Collega i tuoi canali.');
  await element('#connect-youtube').onclick({currentTarget:element('#connect-youtube')});
  assert.equal(authorizationCalls,1);
  assert.equal(location.href,'https://accounts.google.com/test');
  vm.runInContext('renderHome()',context);
  element('#clip-mode').value='full';
  element('#clip-mode').onchange();
  assert.equal(element('#clip-count').disabled,true);
  assert.match(element('#clip-mode-help').textContent,/30 clip/);
  element('#clip-mode').value='highlights';
  element('#clip-mode').onchange();
  assert.equal(element('#clip-count').disabled,false);
}
(async()=>{
  await check('Win32');
  await check('MacIntel');
  console.log('PASS: caricamento degli script reali, navigazione Canali social, avvio OAuth e cambio modalità su Mac e Windows.');
})().catch(e=>{console.error(e);process.exitCode=1});
