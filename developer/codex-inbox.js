/* Developer-side adapter used by the scheduled Codex task. No credentials in the app. */
async function inspectClipLab(tools, root, onlyIssue = null) {
  const repo = 'lucogol-source/ClipLab';
  const api = 'https://api.github.com/repos/' + repo;
  const quote = value => "'" + String(value).replaceAll("'", "'\\''") + "'";
  const result = response => {
    if (response.isError || !response.structuredContent) throw Error('Il connettore GitHub non è disponibile.');
    return response.structuredContent;
  };
  async function get(url) {
    return JSON.parse(result(await tools.mcp__codex_apps__github_fetch({url})).content);
  }
  async function pages(url, consume) {
    for (let page = 1; ; page++) {
      const rows = await get(url + (url.includes('?') ? '&' : '?') + 'per_page=20&page=' + page);
      if (!Array.isArray(rows)) throw Error('Pagina GitHub incompleta.');
      await consume(rows);
      if (rows.length < 20) break;
    }
  }
  async function local(args, payload) {
    const pipe = payload === undefined ? '' : 'printf %s ' + quote(JSON.stringify(payload)) + ' | ';
    const response = await tools.exec_command({
      cmd: pipe + ['.venv/bin/python', ...args].map(quote).join(' '), workdir:root, max_output_tokens:20000
    });
    if (response.exit_code !== 0) throw Error('Controllo locale ClipLab non riuscito.');
    return response.output.trim() ? JSON.parse(response.output) : null;
  }
  let delivered = 0;
  if (onlyIssue === null) {
    // Only submissions explicitly queued by the local Save and send button.
    for (let count = 0; count < 20; count++) {
      const job = await local(['suggestions.py','bridge-next']);
      if (!job) break;
      if (job.repository !== repo || !/^[a-f0-9]{32}$/.test(job.id)) throw Error('Destinazione locale non valida.');
      let number;
      if (job.action === 'create') {
        const created = result(await tools.mcp__codex_apps__github_create_issue({
          repository_full_name:repo, title:job.title, body:job.body
        }));
        number = (created.issue || created).number;
        if (!Number.isSafeInteger(number)) throw Error('Ricevuta incompleta. Il prossimo controllo cercherà la proposta.');
      } else if (job.action === 'find') {
        const query = 'repo:' + repo + ' is:issue author:lucogol-source in:body "' + job.id + '"';
        const found = await get('https://api.github.com/search/issues?q=' + encodeURIComponent(query));
        const match = found.items.find(i => i.repository_url === api && i.user?.id === 325669126 &&
          (i.body || '').replaceAll('\r\n','\n').includes('\nID proposta: ' + job.id + '\n'));
        if (!match) {
          if (!found.incomplete_results) await local(['suggestions.py','bridge-missing',job.id]);
          continue;
        }
        number = match.number;
      } else throw Error('Stato di consegna sconosciuto.');
      const receipt = await get(api + '/issues/' + number);
      await local(['suggestions.py','bridge-confirm',job.id],receipt);
      delivered++;
    }
  } else if (!Number.isSafeInteger(onlyIssue) || onlyIssue <= 0) throw Error('Numero issue non valido.');

  const eligible = [];
  async function inspect(issue) {
    if (issue.pull_request || issue.state !== 'open' || !issue.title.startsWith('[Suggerimento] ') || !issue.comments) return;
    let latest = null;
    await pages(api + '/issues/' + issue.number + '/comments', async rows => {
      for (const c of rows) {
        if (c.user?.id !== 325669126 || c.user.login !== 'lucogol-source' || c.user.type !== 'User' ||
            c.author_association !== 'OWNER' || c.performed_via_github_app || !c.created_at ||
            c.created_at !== c.updated_at || c.issue_url !== issue.url) continue;
        const body = (c.body || '').trim();
        if (body === '/cliplab revoca' || /^\/cliplab approva [a-f0-9]{64}$/.test(body)) {
          if (!latest || c.id > latest.id) latest = c;
        }
      }
    });
    if (!latest || latest.body.trim() === '/cliplab revoca') return;
    const approved = await local(['-I','-S','approval.py'], {issue,comments:[latest]});
    if (!approved) return;
    const branch = 'suggerimenti/issue-' + issue.number + '-' + latest.body.trim().slice(-12);
    const existing = await get(api + '/pulls?state=all&per_page=1&head=' + encodeURIComponent('lucogol-source:' + branch));
    if (!Array.isArray(existing)) throw Error('Impossibile verificare le pull request.');
    if (!existing.length) eligible.push({...approved,branch});
  }
  if (onlyIssue !== null) await inspect(await get(api + '/issues/' + onlyIssue));
  else await pages(api + '/issues?state=open', async issues => {
    for (const issue of issues) await inspect(issue);
  });
  return {delivered, eligible};
}
