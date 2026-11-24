'use strict';

const downloadSelection = new Map();

function currentExport(c) {
  return c.exports.length && (c.exports.at(-1).edit_revision || 0) === (c.edit_revision || 0);
}

function promotionNote(c) {
  const info=c.promotion;
  if (!info) return 'Genera un titolo e gli hashtag per questa clip.';
  if (info.trend_status !== 'fresh') return 'Tendenze non disponibili. Hashtag ricavati dal contenuto.';
  const date=new Date(info.trend_checked_at*1000).toLocaleString('it-IT');
  return `Google Trends · Italia · ${date}${info.trending_hashtags.length ? ' · '+info.trending_hashtags.join(' ') : ' · nessuna tendenza pertinente'}`;
}

function bindDownloads(p) {
  const selected=downloadSelection.get(p.id) || new Set();
  downloadSelection.set(p.id,selected);
  const ready=p.clips.filter(c=>currentExport(c) && !clipBusy(c));
  for (const id of selected) if (!ready.some(c=>c.id===id)) selected.delete(id);
  const bar=document.createElement('section');
  bar.className='download-bar';
  bar.innerHTML=`<label><input type="checkbox" id="download-all">Seleziona le clip esportate</label><button class="btn" id="download-selected">Scarica selezionati · ZIP</button><span id="download-count" class="muted"></span>`;
  const grid=$('.clips-grid');
  if (!grid) return;
  grid.before(bar);
  document.querySelectorAll('[data-download-clip]').forEach(input=>{
    input.checked=selected.has(input.dataset.downloadClip);
    input.onchange=()=>{input.checked?selected.add(input.dataset.downloadClip):selected.delete(input.dataset.downloadClip);update();};
  });
  const update=()=>{
    $('#download-count').textContent=selected.size+' selezionate';
    $('#download-selected').disabled=!selected.size;
    $('#download-all').checked=!!ready.length && ready.every(c=>selected.has(c.id));
    $('#download-all').disabled=!ready.length;
  };
  $('#download-all').onchange=e=>{
    selected.clear();
    if(e.target.checked) ready.forEach(c=>selected.add(c.id));
    document.querySelectorAll('[data-download-clip]').forEach(input=>input.checked=selected.has(input.dataset.downloadClip));
    update();
  };
  $('#download-selected').onclick=async e=>{
    const button=e.currentTarget;
    button.disabled=true;
    try {
      const ids=p.clips.filter(c=>selected.has(c.id)).map(c=>c.id);
      await post('/projects/'+p.id+'/download/check',{clip_ids:ids});
      const a=document.createElement('a');
      a.href='/api/projects/'+p.id+'/download?clips='+encodeURIComponent(ids.join(','));
      a.target='_blank';a.rel='noopener';a.download='ClipLab-'+p.id.slice(0,8)+'.zip';
      document.body.append(a);a.click();a.remove();
      toast('Preparazione dello ZIP. Il browser avvierà il download.');
    } catch(error) {toast(error.message,true);}
    finally {update();}
  };
  update();
}

async function refreshClipPromotion(replaceTitle) {
  const session=editSession;
  const button=$(replaceTitle?'#generate-headline':'#refresh-hashtags');
  button.disabled=true;
  try {
    await saveEditor();
    await post('/projects/'+session.pid+'/clips/'+session.cid+'/promotion',{replace_title:replaceTitle});
    await pollProject();
    if (editSession !== session) return;
    const c=state.project.clips.find(c=>c.id===session.cid);
    $('#clip-title').value=c.title;
    $('#clip-description').value=c.description||'';
    $('#clip-promotion-note').textContent=promotionNote(c);
    toast(replaceTitle?'Titolo e hashtag aggiornati.':'Hashtag aggiornati.');
    syncEditor();
  } catch(error) {toast(error.message,true);}
  finally {button.disabled=false;}
}
