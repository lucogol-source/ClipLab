'use strict';

const issuesUrl = 'https://github.com/lucogol-source/ClipLab/issues';
let suggestionTimer;
let suggestionFormKey;
let suggestionFormContent;

function suggestionCard(item) {
  const sent = item.state === 'sent' && Number.isInteger(item.number);
  const status = sent ? 'Inviata' : ['checking','bridge_check'].includes(item.state) ? 'In verifica' : 'In attesa di invio';
  const date = new Date(item.created * 1000).toLocaleDateString('it-IT');
  const action = sent
    ? `<a class="inline-link" target="_blank" rel="noopener" href="${issuesUrl}/${item.number}">Apri issue #${item.number} ↗</a>`
    : item.state.startsWith('bridge_') || item.state === 'handoff' ? '' : `<button class="btn small ghost" type="button" data-retry="${esc(item.id)}">${['checking','bridge_check'].includes(item.state) ? 'Verifica ora' : 'Riprova ora'}</button>`;
  return `<article class="suggestion-card"><div class="suggestion-meta"><span>${esc(date)} · ${esc(item.platform)}</span><span class="status">${status}</span></div>
    <h3>${esc(item.title)}</h3><p class="suggestion-text">${esc(item.description)}</p>
    ${item.detail ? `<p class="help-text">${esc(item.detail)}</p>` : ''}${action}
    ${item.can_resend ? `<button class="btn small ghost" type="button" data-resend="${esc(item.id)}">Ripeti invio…</button>` : ''}</article>`;
}

async function refreshSuggestions(list) {
  clearTimeout(suggestionTimer);
  const {items, via_codex} = await api('/suggestions');
  if (route() !== 'suggestions' || !list.isConnected) return;
  $('#suggestion-access').hidden = via_codex;
  $('#suggestion-delivery').hidden = !via_codex;
  $('#suggestion-review').hidden = !via_codex;
  list.innerHTML = items.length ? items.map(suggestionCard).join('') : '<p class="muted">Le proposte salvate su questo computer appariranno qui.</p>';
  if (items.some(item => item.state !== 'sent')) {
    suggestionTimer = setTimeout(() => {
      if (route() === 'suggestions' && list.isConnected) refreshSuggestions(list).catch(e => toast(e.message, true));
    }, 5000);
  }
}

async function renderSuggestions() {
  setNav('suggestions');
  $('#main').innerHTML = `<div class="page-head"><div><h1>Suggerimenti</h1><p>Quale modifica ti aiuterebbe a creare le tue clip?</p></div></div>
    <section class="settings-panel"><form id="suggestion-form">
      <div class="field"><label for="idea-title">Titolo</label><input id="idea-title" maxlength="120" required placeholder="Es. Spostare più sottotitoli insieme"></div>
      <div class="field"><label for="idea-text">Cosa vorresti cambiare?</label><textarea id="idea-text" maxlength="4000" required rows="4" placeholder="Descrivi cosa stai facendo e il risultato che vorresti ottenere."></textarea></div>
      <p class="help-text">Titolo, descrizione, versione e sistema operativo saranno inviati con il tuo account al repository privato <a class="inline-link" href="${issuesUrl}" target="_blank" rel="noopener">lucogol-source/ClipLab</a>.</p>
      <button class="btn primary" type="submit">Salva e invia a GitHub ${icon('arrow')}</button>
    </form><p id="suggestion-delivery" class="help-text" hidden>Su questo Mac Codex inoltra le proposte tramite il tuo account al prossimo controllo orario.</p><details id="suggestion-access" class="suggestion-access"><summary>Come collegare GitHub per il primo invio</summary>
      <p>Installa <a class="inline-link" href="https://cli.github.com/" target="_blank" rel="noopener">GitHub CLI</a>. Apri Terminale su Mac o PowerShell su Windows ed esegui <code>gh auth login --hostname github.com --web</code>. Accedi con l’account invitato al repository.</p>
      <p>Puoi salvare una proposta anche prima di collegarti. ClipLab riprova mentre è aperto e dopo un riavvio.</p></details>
    <details id="suggestion-review" class="suggestion-access" hidden><summary>Approvare una proposta e rivedere le modifiche</summary>
      <p>Apri l’<a class="inline-link" href="${issuesUrl}" target="_blank" rel="noopener">issue su GitHub</a> con l’account lucogol-source. Copia il comando di approvazione dal fondo della proposta e pubblicalo da solo in un nuovo commento.</p>
      <p>Al controllo orario Codex prepara le modifiche. Le trovi nelle <a class="inline-link" href="https://github.com/lucogol-source/ClipLab/pulls" target="_blank" rel="noopener">pull request da rivedere</a>. In <strong>Files changed</strong> puoi rivedere il codice prima del merge.</p></details></section>
    <div class="section-row"><h2>Le tue proposte</h2></div><div id="suggestion-list"><p>Caricamento…</p></div>`;
  const form = $('#suggestion-form');
  const list = $('#suggestion-list');
  form.onsubmit = async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    if (button.disabled) return;
    button.disabled = true;
    const title = $('#idea-title').value.trim(), description = $('#idea-text').value.trim();
    const content = JSON.stringify([title, description]);
    try {
      if (!suggestionFormKey || suggestionFormContent !== content) {
        suggestionFormKey = crypto.randomUUID().replaceAll('-', '');
        suggestionFormContent = content;
      }
      await post('/suggestions', {id: suggestionFormKey, title, description});
      suggestionFormKey = null;
      form.reset();
      toast('Proposta salvata. Puoi seguire l’invio in Le tue proposte.');
      await refreshSuggestions(list);
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; }
  };
  list.onclick = async event => {
    const button = event.target.closest('[data-retry],[data-resend]');
    if (!button) return;
    const resend = button.hasAttribute('data-resend');
    if (resend && !confirm('Hai controllato su GitHub che la proposta sia assente? Confermando autorizzi un nuovo invio che potrebbe creare un duplicato.')) return;
    button.disabled = true;
    try {
      await post('/suggestions/' + encodeURIComponent(button.dataset.resend || button.dataset.retry) + (resend ? '/resend' : '/retry'), {});
      await refreshSuggestions(list);
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; }
  };
  await refreshSuggestions(list);
}
