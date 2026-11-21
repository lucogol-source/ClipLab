const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8').replace(/\ninit\(\);\s*$/,'');
(async()=>{
  for(const [platform,launcher] of [['MacIntel','Avvia ClipLab.command'],['Win32','Avvia ClipLab.cmd']]){
    const elements=new Map();
    const element=selector=>{
      if(!elements.has(selector))elements.set(selector,{textContent:'',innerHTML:'',hidden:false,addEventListener(){},classList:{toggle(){}}});
      return elements.get(selector);
    };
    const context=vm.createContext({document:{querySelector:element,body:{dataset:{launchFile:'Avvia ClipLab.__CLIPLAB_LAUNCH_EXT__'}}},
      navigator:{platform},window:{addEventListener(){}},setInterval(){},
      location:{replace(){throw Error('Un redirect tra porte non deve essere inventato.');}},
      fetch:async()=>({ok:true,json:async()=>({local:true,paid_services:false,version:'1.0'})})});
    vm.runInContext(source,context);
    await vm.runInContext('init()',context);
    assert.equal(vm.runInContext('state.legacy',context),true);
    assert.equal(element('#app-version').textContent,'V1.0');
    assert.equal(element('#sidebar-version').textContent,'computer · V1.0');
    assert.match(element('#main').innerHTML,new RegExp(launcher.replaceAll('.','\\.')));
    assert.doesNotMatch(element('#main').innerHTML,/127\.0\.0\.1|8768|8778/);
    const text=element('#health-label').textContent;
    await vm.runInContext('checkServer()',context);
    assert.equal(element('#health-label').textContent,text);
  }
  console.log('PASS: versioni precedenti senza redirect fisso, comando di riapertura Mac/Windows corretto.');
})().catch(error=>{console.error(error);process.exitCode=1;});
