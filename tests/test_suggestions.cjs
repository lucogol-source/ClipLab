const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const context = vm.createContext({esc: value => String(value).replaceAll('<','&lt;'), URL, console});
vm.runInContext(fs.readFileSync(path.join(root,'static/suggestions.js'),'utf8'),context);
const base = {id:'abc',created:1000,platform:'Windows',title:'<titolo>',description:'Testo',detail:''};
for (const [state, number] of [['sent',5],['queued',null],['checking',null],['handoff',null]]) {
  const html = context.suggestionCard({...base,state,number});
  assert.ok(html.includes('&lt;titolo>'));
  assert.equal(html.includes('/issues/5'),state==='sent');
  assert.equal(html.includes('data-retry'),['queued','checking'].includes(state));
}
const code = fs.readFileSync(path.join(root,'developer/codex-inbox.js'),'utf8');
vm.runInContext(code,context);
const repo='https://api.github.com/repos/lucogol-source/ClipLab';
const issue={url:repo+'/issues/1',number:1,title:'[Suggerimento] Prova',state:'open',comments:1};
const owner={id:7,body:'/cliplab approva '+'a'.repeat(64), user:{id:325669126,login:'lucogol-source',type:'User'},
  created_at:'date',updated_at:'date',issue_url:issue.url,author_association:'OWNER'};
async function check(comments,pulls,expectedCalls) {
  let calls=0;
  const tools={exec_command:async () => {calls++; return {exit_code:0,output:JSON.stringify({issue:1,approval_id:7,scope:'prova'})};},
    mcp__codex_apps__github_fetch:async ({url}) => {
      const data=url.includes('/comments?')?comments:url.includes('/pulls?')?pulls:issue;
      return {structuredContent:{content:JSON.stringify(data)}};
    }};
  const result=await context.inspectClipLab(tools,root,1);
  assert.equal(calls,expectedCalls);
  return result.eligible;
}
(async()=>{
  assert.equal((await check([owner],[],1)).length,1);
  assert.equal((await check([owner],[{number:2}],1)).length,0);
  assert.equal((await check([{...owner,user:{...owner.user,id:99}}],[],0)).length,0);
  assert.equal((await check([owner,{...owner,id:8,body:'/cliplab revoca'}],[],0)).length,0);
  console.log('PASS: stati delle proposte, selezione proprietario, revoca e PR già esistente.');
})().catch(e=>{console.error(e);process.exitCode=1});
