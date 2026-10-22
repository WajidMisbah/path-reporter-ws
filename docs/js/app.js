// Path Reporter WS v1 - Histopathology. All patient data stays in this browser (IndexedDB).
(function(){
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const app=$('#app');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const uid=p=>p+'-'+Date.now().toString(36)+Math.random().toString(36).slice(2,7);
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('show');clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('show'),2600);}
const HEADER=[['name','Name'],['uhid','UHID'],['age','Age'],['gender','Gender'],['lab no','Lab No'],['ref. doctor','Ref. Doctor'],['dept./ward','Dept./Ward'],['sample no','Sample No'],['received on','Received on'],['reported on','Reported on']];
const TYPES=[['histo','Histopathology',true,'Gross, microscopy, diagnosis; CAP synoptic for cancers'],['ihc','Immunohistochemistry',true,'Results table, scoring (Allred, HER2, Ki-67…), controls, impression'],['cyto','Cytology / FNAC',false],['pap','PAP Smear',false],['fluid','Serous Effusion / Other Fluid',false],['bma','Bone Marrow Aspiration',false],['bmb','Bone Marrow Biopsy',false],['ps','Peripheral Smear Comment',false]];
const GROSS_OPTS=['Saved.','All embedded.','Partially embedded.'];
let S={bundle:null,layouts:{},userDx:[],report:null};

// ---------- item <-> text (one paragraph per line, **Label:** marks a bold heading) ----------
const itemsToText=items=>(items||[]).map(i=>i.label?`**${i.label}** ${i.text||''}`.trimEnd():(i.text||'')).join('\n');
const textToItems=t=>String(t||'').split('\n').map(l=>l.trimEnd()).filter(l=>l.trim()).map(l=>{const m=l.match(/^\*\*(.+?)\*\*\s*(.*)$/);return m?{label:m[1],text:m[2]}:{label:'',text:l};});

// ---------- templates bundle ----------
async function loadBundle(fromNetwork){
  let b=fromNetwork?null:await DB.get('meta','bundle');
  if(b&&(!b.layouts||!b.layouts.ihc||!b.data.reportTypes)) b=null; // older cached bundle: fetch the new one; user stores untouched
  if(!b){
    const r=await fetch('templates/bundle.json?ts='+Date.now(),{cache:'no-store'}); if(!r.ok) throw new Error('bundle '+r.status);
    const data=await r.json(); const L={};
    for(const t of (data.reportTypes||[])) if(t.engine==='generic') data.layouts[t.id]=t.layout;
    for(const [k,p] of Object.entries(data.layouts)){ const x=await fetch(p+'?ts='+Date.now(),{cache:'no-store'}); if(!x.ok) throw new Error(p); L[k]=await x.arrayBuffer(); }
    const old=await DB.get('meta','bundle');
    b={id:'bundle',data,layouts:L,fetched:new Date().toISOString()}; await DB.put('meta',b);
    if(fromNetwork){ const cnt=d=>d?d.diagnoses.length+d.specimens.length+(d.ihcPanels||[]).length+(d.reportTypes||[]).reduce((a,t)=>a+(t.cases||[]).length,0):0; const before=cnt(old&&old.data); const after=cnt(data);
      toast(old&&old.data.version===data.version?'Templates are already up to date':`Templates updated (${after-before>=0?'+':''}${after-before} items)`); }
  }
  S.bundle=b.data; S.layouts=b.layouts; S.userDx=await DB.all('diagnoses');
  $('#bundleInfo').textContent=`${S.bundle.specimens.length} specimens · ${allDx().length} diagnoses · ${allDx('ihc').length} IHC panels · ${(S.bundle.reportTypes||[]).length} report types · templates ${S.bundle.version.slice(0,8)}`;
}
const dxType=d=>d.type||'histo';
function allDx(type='histo'){ const gen=(S.bundle.reportTypes||[]).flatMap(t=>t.cases||[]); const m=new Map([...S.bundle.diagnoses,...(S.bundle.ihcPanels||[]),...gen].map(d=>[d.id,d])); for(const u of S.userDx) m.set(u.id,u); return [...m.values()].filter(d=>dxType(d)===type); }

// ---------- screens ----------
function home(){
  const TY=(S.bundle.reportTypes||[]).map(t=>[t.id,t.name,['histo','ihc','generic'].includes(t.engine),t.desc]);
  app.innerHTML=`<h2>New report</h2><div class="types">${TY.map(([k,n,on,d])=>`<button class="type ${on?'on':'off'}" data-k="${k}" ${on?'':'disabled'}><span class="tname">${esc(n)}</span>${on?'':'<span class="tag grey">coming soon</span>'}<small>${esc(d||'Not in this version yet')}</small></button>`).join('')}</div>
  <div class="card" style="margin-top:16px"><h3>Recent reports</h3><div id="recent" class="list hint">Loading…</div></div>`;
  $$('.type.on').forEach(b=>b.onclick=()=>newReport(b.dataset.k));
  listReports($('#recent'),6);
}
function newReport(k){
  if(k==='ihc') return newIhc();
  const T=typeOf(k); if(T&&T.engine==='generic') return newGeneric(T);
  S.report={id:uid('rep'),type:'histo',created:new Date().toISOString(),updated:null,header:Object.fromEntries(HEADER.map(([k])=>[k,''])),
    clinical:[{label:'Specimen:',text:''},{label:'Procedure:',text:''},{label:'Clinical history:',text:''}],
    specimenId:'',gross:{containers:[{text:'',gross:''}],sections:''},dxId:'',dxName:'',layout:'histo',micro:[],finalDiagnosis:[],comment:[],cap:null};
  S.report.header['reported on']=new Date().toLocaleDateString('en-GB');
  editor();
}
async function listReports(el,limit){
  const rs=(await DB.all('reports')).sort((a,b)=>(b.updated||b.created).localeCompare(a.updated||a.created)).slice(0,limit||1e9);
  el.classList.remove('hint');
  el.innerHTML=rs.length?rs.map(r=>`<div class="item"><div><b>${esc(r.header.name||'(no name)')}</b> · ${esc(r.header['lab no']||'')} <span class="tag ${r.type==='ihc'?'pink':r.type&&r.type!=='histo'?'purple':'blue'}">${esc(typeShort(r.type))}</span> <span class="tag blue">${esc(r.dxName||'no diagnosis')}</span><br><small class="hint">${esc(new Date(r.updated||r.created).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'}))}</small></div><div class="actions"><button class="small" data-o="${r.id}">Open</button><button class="small danger" data-d="${r.id}">Delete</button></div></div>`).join(''):'<p class="hint">No saved reports yet.</p>';
  $$('[data-o]',el).forEach(b=>b.onclick=async()=>{S.report=await DB.get('reports',b.dataset.o);openEditor();});
  $$('[data-d]',el).forEach(b=>b.onclick=async()=>{ if(confirm('Delete this report from this device?')){await DB.del('reports',b.dataset.d);listReports(el,limit);} });
}
function reportsScreen(){ app.innerHTML=`<h2>Saved reports</h2><div class="card"><input id="q" placeholder="Search name, UHID, lab no, diagnosis"><div id="all" class="list" style="margin-top:8px"></div></div>`; listReports($('#all')); $('#q').oninput=e=>{const q=e.target.value.toLowerCase(); $$('#all .item').forEach(i=>i.style.display=i.textContent.toLowerCase().includes(q)?'':'none');}; }
function dataScreen(){
  app.innerHTML=`<h2>Templates &amp; backup</h2>
  <div class="card"><h3>Update templates</h3><p class="hint">Loads the newest specimen and diagnosis templates from the app's website. Your own saved diagnosis templates and reports are kept.</p><p>Current: <b>${esc(S.bundle.version)}</b> · ${S.bundle.specimens.length} specimens · ${S.bundle.diagnoses.length} built-in diagnoses · ${(S.bundle.ihcPanels||[]).length} IHC panels · ${S.userDx.length} of your own</p><button id="upd" class="alt">Update templates</button></div>
  <div class="card"><h3>Backup</h3><p class="hint">Patient data never leaves this tablet. Export a backup file and keep it somewhere safe (it contains patient details).</p>
  <div class="actions"><button id="exp" class="violet">Export backup (.json)</button><label class="hint" style="margin:0"><input type="file" id="imp" accept="application/json,.json" style="display:none"><span class="purple" style="display:inline-block;padding:10px 16px;border-radius:10px;background:var(--purple);color:#fff;cursor:pointer">Import backup…</span></label></div></div>
  <div class="card"><h3>My diagnosis templates</h3><div id="mydx" class="list"></div></div>`;
  $('#upd').onclick=async()=>{ try{ await loadBundle(true); dataScreen(); }catch(e){ toast('Could not update (offline?)'); } };
  $('#exp').onclick=async()=>{ const o=await DB.exportAll(); download(new Blob([JSON.stringify(o,null,1)],{type:'application/json'}),`PathReporterWS-backup-${new Date().toISOString().slice(0,10)}.json`); };
  $('#imp').onchange=async e=>{ const f=e.target.files[0]; if(!f) return; try{ const o=JSON.parse(await f.text()); const mode=confirm('OK = merge with what is on this tablet.\nCancel = replace everything on this tablet with the backup.')?'merge':'replace'; await DB.importAll(o,mode); S.userDx=await DB.all('diagnoses'); toast('Backup imported'); dataScreen(); }catch(err){ toast(err.message); } };
  const el=$('#mydx'); el.innerHTML=S.userDx.length?S.userDx.map(d=>`<div class="item"><div><b>${esc(d.name)}</b> <span class="tag pink">${esc(typeShort(d.type))}</span> <span class="tag ${d.overrides?'purple':'blue'}">${d.overrides?'overwrites built-in':'my template'}</span></div><button class="small danger" data-x="${d.id}">${d.overrides?'Restore built-in':'Delete'}</button></div>`).join(''):'<p class="hint">None yet.</p>';
  $$('[data-x]',el).forEach(b=>b.onclick=async()=>{ await DB.del('diagnoses',b.dataset.x); S.userDx=await DB.all('diagnoses'); dataScreen(); });
}

// ---------- editor ----------
function blanksUI(ta,box){
  const render=()=>{ const parts=ta.value.split(/_{3,}/); if(parts.length<2){box.innerHTML='<span class="hint">No ____ blanks left.</span>';return;}
    box.innerHTML=parts.slice(0,-1).map((p,i)=>{const ctx=p.split(/\s+/).filter(Boolean).slice(-3).join(' ');return `<span class="blank"><small>${esc(ctx.slice(-28))}</small><input data-i="${i}" inputmode="decimal" placeholder="____"></span>`;}).join('');
    $$('input',box).forEach(inp=>inp.onchange=()=>{ if(inp._done||!inp.value.trim()) return; inp._done=true; let n=-1; ta.value=ta.value.replace(/_{3,}/g,m=>(++n===+inp.dataset.i)?inp.value.trim():m); ta.dispatchEvent(new Event('input')); render(); const nx=$('input',box); if(nx) nx.focus(); }); };
  ta.addEventListener('input',()=>{ if(!box.contains(document.activeElement)) render(); }); render();
}
function nextBlank(ta){ const s=ta.selectionEnd||0; let i=ta.value.indexOf('____',s); if(i<0) i=ta.value.indexOf('____'); if(i<0){toast('No blanks left');return;} let j=i; while(ta.value[j]==='_') j++; ta.focus(); ta.setSelectionRange(i,j); }

function editor(){
  const R=S.report; const specs=S.bundle.specimens;
  app.innerHTML=`<h2>Histopathology report</h2>
  <div class="card"><h3>1 · Patient details</h3><div class="grid">${HEADER.map(([k,l])=>`<div><label>${esc(l)}</label><input data-h="${esc(k)}" value="${esc(R.header[k])}"></div>`).join('')}</div></div>
  <div class="card"><h3>2 · Clinical details</h3><div id="clin"></div><div class="actions"><button class="small light" id="addClin">+ Add row</button></div></div>
  <div class="card"><h3>3 · Specimen &amp; gross</h3>
   <label>Specimen</label><select id="spec"><option value="">— choose specimen —</option>${[...new Set(specs.map(s=>s.organ))].map(o=>`<optgroup label="${esc(o)}">${specs.filter(s=>s.organ===o).map(s=>`<option value="${s.id}" ${s.id===R.specimenId?'selected':''}>${esc(s.name)}</option>`).join('')}</optgroup>`).join('')}</select>
   <div id="conts"></div><div class="actions"><button class="small light" id="addCont">+ Add container</button></div>
   <label>Sections</label><textarea id="sections" style="min-height:60px">${esc(R.gross.sections)}</textarea></div>
  <div class="card"><h3>4 · Diagnosis</h3><div class="row"><input id="dxq" placeholder="Search diagnoses"><label class="hint" style="flex:0 0 auto;display:flex;gap:6px;align-items:center"><input type="checkbox" id="dxall" style="width:auto"> all organs</label></div>
   <div id="dxl" class="dxlist" style="margin-top:8px"></div><p class="hint" id="dxsel">${R.dxName?'Loaded: <b>'+esc(R.dxName)+'</b>':'Choosing a diagnosis fills the sections below (you can edit everything).'}</p>
   <label>Microscopic description</label><textarea id="micro" style="min-height:160px">${esc(itemsToText(R.micro))}</textarea>
   <div id="capbox"></div>
   <label>Final diagnosis</label><textarea id="fd">${esc(itemsToText(R.finalDiagnosis))}</textarea>
   <label>Comment</label><textarea id="comment">${esc(itemsToText(R.comment))}</textarea>
   <p class="hint">One paragraph per line. Text between ** ** prints bold, e.g. <code>**Gallbladder, cholecystectomy:** Chronic cholecystitis.</code></p></div>
  <div id="layoutBox"></div>
  <div class="card actions" style="position:sticky;bottom:8px"><button id="save">Save…</button><button id="docx" class="alt">Download .docx</button><button id="prev" class="violet">Preview</button><button id="print" class="pink">Print / PDF</button></div>
  <div id="previewBox"></div>`;
  $$('[data-h]').forEach(i=>i.oninput=()=>R.header[i.dataset.h]=i.value);
  const renderClin=()=>{ $('#clin').innerHTML=R.clinical.map((c,i)=>`<div class="row" style="margin-bottom:6px"><input class="narrow" data-cl="${i}" value="${esc(c.label)}" placeholder="Label:"><textarea data-ct="${i}" style="min-height:44px" placeholder="Details">${esc(c.text)}</textarea><button class="small danger" data-cx="${i}" style="flex:0 0 auto">✕</button></div>`).join('');
    $$('[data-cl]').forEach(e=>e.oninput=()=>R.clinical[e.dataset.cl].label=e.value); $$('[data-ct]').forEach(e=>e.oninput=()=>R.clinical[e.dataset.ct].text=e.value);
    $$('[data-cx]').forEach(e=>e.onclick=()=>{R.clinical.splice(+e.dataset.cx,1);renderClin();}); };
  renderClin(); $('#addClin').onclick=()=>{R.clinical.push({label:'',text:''});renderClin();};
  const renderConts=()=>{ const multi=R.gross.containers.length>1;
    $('#conts').innerHTML=R.gross.containers.map((c,i)=>`<div class="card" style="background:#fbfcff"><div class="row"><b style="flex:0 0 auto">Container ${'ABCDEFGHIJ'[i]}</b><span></span><button class="small light" data-nb="${i}" style="flex:0 0 auto">Next ____</button>${multi?`<button class="small danger" data-rx="${i}" style="flex:0 0 auto">Remove</button>`:''}</div>
     <textarea data-gt="${i}" style="min-height:130px">${esc(c.text)}</textarea><div class="blanks" data-bl="${i}"></div>
     <label>Gross</label><select data-gs="${i}">${['',...GROSS_OPTS].map(o=>`<option ${o===c.gross?'selected':''} value="${esc(o)}">${o||'— Saved / All embedded / Partially embedded —'}</option>`).join('')}${c.gross&&!GROSS_OPTS.includes(c.gross)?`<option selected>${esc(c.gross)}</option>`:''}</select></div>`).join('');
    $$('[data-gt]').forEach(t=>{ t.oninput=()=>R.gross.containers[t.dataset.gt].text=t.value; blanksUI(t,$(`[data-bl="${t.dataset.gt}"]`)); });
    $$('[data-gs]').forEach(s=>s.onchange=()=>R.gross.containers[s.dataset.gs].gross=s.value);
    $$('[data-nb]').forEach(b=>b.onclick=()=>nextBlank($(`[data-gt="${b.dataset.nb}"]`)));
    $$('[data-rx]').forEach(b=>b.onclick=()=>{R.gross.containers.splice(+b.dataset.rx,1);renderConts();}); };
  renderConts();
  $('#addCont').onclick=()=>{ const sp=specs.find(s=>s.id===R.specimenId); R.gross.containers.push({text:sp?sp.containers[0].text:'',gross:''}); renderConts(); };
  $('#sections').oninput=e=>R.gross.sections=e.target.value;
  $('#spec').onchange=e=>{ const sp=specs.find(s=>s.id===e.target.value); R.specimenId=e.target.value;
    if(sp){ const has=R.gross.containers.some(c=>c.text.trim()); if(!has||confirm('Replace the gross text with the '+sp.name+' template?')){ R.gross.containers=sp.containers.map(c=>({text:c.text,gross:''})); renderConts(); } }
    if(sp&&!R.clinical[0].text) { R.clinical[0].text=sp.organ+'.'; renderClin(); }
    renderDx(); };
  const renderDx=()=>{ const q=$('#dxq').value.toLowerCase(); const sp=specs.find(s=>s.id===R.specimenId); const all=$('#dxall').checked||!sp;
    let L=allDx().filter(d=>(all||d.userOrgan===sp?.organ||new RegExp(sp.match,'i').test(d.path||''))&&(!q||(d.name+' '+(d.path||'')).toLowerCase().includes(q)));
    if(sp&&!all){ const want=sp.kind==='Cancer'?'Neoplastic':'Non-neoplastic'; L.sort((a,b)=>((a.nature===want?0:1)-(b.nature===want?0:1))||a.name.localeCompare(b.name)); } else L.sort((a,b)=>a.name.localeCompare(b.name));
    $('#dxl').innerHTML=L.length?L.slice(0,300).map(d=>`<div class="dx ${d.id===R.dxId?'sel':''}" data-dx="${d.id}"><b>${esc(d.name)}</b> ${d.layout==='cap'?'<span class="tag purple">CAP</span>':''}${d.user?'<span class="tag blue">mine</span>':''}<br><small>${esc(d.nature||'')} · ${esc((d.path||'').split('/').slice(0,2).join(' / '))}</small></div>`).join(''):`<p class="hint" style="padding:10px">No diagnoses for this specimen yet${sp?' — tick "all organs" to see everything':''}.</p>`;
    $$('[data-dx]').forEach(el=>el.onclick=()=>pickDx(el.dataset.dx)); };
  const pickDx=id=>{ const d=allDx().find(x=>x.id===id); if(!d) return;
    if((R.micro.length||R.finalDiagnosis.length)&&!confirm('Replace microscopic, diagnosis and comment with "'+d.name+'"?')) return;
    R.dxId=d.id; R.dxName=d.name; R.layout=d.layout; R.micro=structuredClone(d.micro||[]); R.finalDiagnosis=structuredClone(d.finalDiagnosis||[]); R.comment=structuredClone(d.comment||[]); R.cap=d.cap?structuredClone(d.cap):null;
    $('#micro').value=itemsToText(R.micro); $('#fd').value=itemsToText(R.finalDiagnosis); $('#comment').value=itemsToText(R.comment);
    if(d.secLayout&&d.secLayout.secs) R.secLayout=structuredClone(d.secLayout); if(d.signout) R.signout=structuredClone(d.signout);
    $('#dxsel').innerHTML='Loaded: <b>'+esc(d.name)+'</b>'; renderCap(); renderDx(); layoutCard($('#layoutBox')); toast('Diagnosis loaded'); };
  const renderCap=()=>{ const c=R.cap; if(!c){$('#capbox').innerHTML='';return;}
    $('#capbox').innerHTML=`<label>Synoptic report ${esc(c.title)}</label><div class="card" style="background:#fbfaff">${c.sections.map((s,si)=>`<div class="capsec"><input data-sh="${si}" value="${esc(s.heading)}" style="font-weight:700">${s.items.map((it,ii)=>`<div class="capitem"><input data-il="${si}.${ii}" value="${esc(it.label||'')}" placeholder="(no label)"><input data-iv="${si}.${ii}" value="${esc(it.value||'')}"><select data-ii="${si}.${ii}"><option value="0" ${!it.ilvl?'selected':''}>•</option><option value="1" ${it.ilvl==1?'selected':''}>◦</option><option value="2" ${it.ilvl==2?'selected':''}>▪</option></select><button class="small danger" data-ix="${si}.${ii}">✕</button></div>`).join('')}<button class="small light" data-ia="${si}">+ item</button></div>`).join('')}</div>`;
    const at=k=>k.split('.').map(Number);
    $$('[data-sh]').forEach(e=>e.oninput=()=>c.sections[e.dataset.sh].heading=e.value);
    $$('[data-il]').forEach(e=>e.oninput=()=>{const[a,b]=at(e.dataset.il);c.sections[a].items[b].label=e.value;});
    $$('[data-iv]').forEach(e=>e.oninput=()=>{const[a,b]=at(e.dataset.iv);c.sections[a].items[b].value=e.value;});
    $$('[data-ii]').forEach(e=>e.onchange=()=>{const[a,b]=at(e.dataset.ii);c.sections[a].items[b].ilvl=+e.value;});
    $$('[data-ix]').forEach(e=>e.onclick=()=>{const[a,b]=at(e.dataset.ix);c.sections[a].items.splice(b,1);renderCap();});
    $$('[data-ia]').forEach(e=>e.onclick=()=>{c.sections[+e.dataset.ia].items.push({label:'',value:'',ilvl:0});renderCap();}); };
  renderCap(); renderDx();
  $('#dxq').oninput=renderDx; $('#dxall').onchange=renderDx;
  $('#micro').oninput=e=>R.micro=textToItems(e.target.value); $('#fd').oninput=e=>R.finalDiagnosis=textToItems(e.target.value); $('#comment').oninput=e=>R.comment=textToItems(e.target.value);
  layoutCard($('#layoutBox')); $('#save').onclick=saveDialog; $('#docx').onclick=()=>exportDocx(); $('#prev').onclick=()=>preview($('#previewBox')); $('#print').onclick=printReport;
}

// ---------- save ----------
function saveDialog(){
  const R=S.report; const cur=allDx(R.type||'histo').find(d=>d.id===R.dxId);
  $('#modalBody').innerHTML=`<h3>Save report</h3><p class="hint">The report is always saved on this tablet. Choose what happens to the diagnosis text you edited:</p>
   <button class="choice-btn" data-m="patient"><b>This patient only</b><br><small>Keep the edits in this report; templates stay unchanged.</small></button>
   <button class="choice-btn" data-m="new"><b>Save as a new template</b><br><small>Adds a new entry under <b>${esc(typeShort(R.type))}</b> with your text, sections, rows and sign-out.</small></button>
   <button class="choice-btn" data-m="over" ${cur?'':'disabled'}><b>Overwrite the existing template</b><br><small>${cur?'Replaces "'+esc(cur.name)+'" on this tablet.':'No diagnosis loaded.'}</small></button>
   <div class="actions"><button class="light" id="mcancel">Cancel</button></div>`;
  $('#modal').classList.remove('hidden'); $('#mcancel').onclick=()=>$('#modal').classList.add('hidden');
  $$('[data-m]').forEach(b=>b.onclick=async()=>{ const m=b.dataset.m; const sp=S.bundle.specimens.find(s=>s.id===R.specimenId);
    const tpl=base=>(typeOf(R.type)||{}).engine==='generic'?({...(base||{}),type:R.type,values:structuredClone(R.values),user:true,saved:new Date().toISOString()}):R.type==='ihc'?({...(base||{}),type:'ihc',block:structuredClone(R.block),results:structuredClone(R.results),scoring:structuredClone(R.scoring),controls:structuredClone(R.controls),impression:structuredClone(R.impression),comment:structuredClone(R.comment),user:true,saved:new Date().toISOString()})
      :({...(base||{}),micro:R.micro,finalDiagnosis:R.finalDiagnosis,comment:R.comment,cap:R.cap,layout:R.cap?'cap':'histo',user:true,saved:new Date().toISOString()});
    const tpl0=tpl; const tplL=base=>({...tpl0(base),secLayout:R.secLayout?structuredClone(R.secLayout):null,signout:R.signout?structuredClone(R.signout):null});
    if(m==='new'){ const name=prompt('Name for the new template (saved under '+typeShort(R.type)+'):',R.dxName?R.dxName+' (modified)':''); if(!name) return;
      const d=tplL({id:uid('mydx'),name,nature:cur?.nature||(sp?.kind==='Cancer'?'Neoplastic':'Non-neoplastic'),path:cur?.path||(sp?sp.organ:''),userOrgan:sp?.organ||null}); await DB.put('diagnoses',d); R.dxId=d.id; R.dxName=name; }
    if(m==='over'&&cur){ if(!confirm('Overwrite "'+cur.name+'" for all future reports on this tablet?')) return;
      const d=tplL(cur); d.overrides=!cur.user||!!cur.overrides; await DB.put('diagnoses',d); }
    R.updated=new Date().toISOString(); await DB.put('reports',structuredClone(R)); S.userDx=await DB.all('diagnoses');
    $('#modal').classList.add('hidden'); toast(m==='patient'?'Report saved':m==='new'?'Report saved + new template added':'Report saved + template overwritten'); });
}

// ---------- output ----------
function makeBlob(){ const R=S.report; if(R.type==='ihc') return DocxFill.buildIhcDocx(S.layouts.ihc,R);
  const GT=typeOf(R.type); if(GT&&GT.engine==='generic') return DocxFill.buildGenericDocx(S.layouts[GT.id],R,GT.schema); const layout=R.cap&&R.cap.sections?.length?'cap':'histo'; const buf=S.layouts[layout]; return DocxFill.buildDocx(buf,R); }
function fname(){ const R=S.report; return [typeShort(R.type),R.header['lab no'],R.header.name].filter(Boolean).join(' - ').replace(/[\\/:*?"<>|]/g,'_')+'.docx'; }
function download(blob,name){ const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; document.body.appendChild(a); a.click(); setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},2000); }
function exportDocx(){ try{ download(makeBlob(),fname()); }catch(e){ console.error(e); toast('Could not build .docx: '+e.message); } }
async function renderInto(el){ el.innerHTML=''; await docx.renderAsync(makeBlob(),el,null,{className:'docx',inWrapper:true,ignoreWidth:false,ignoreHeight:false,breakPages:true,renderHeaders:true,renderFooters:true,experimental:true,useBase64URL:true}); }
async function preview(box){ box.innerHTML='<div class="card"><h3>Preview</h3><div class="preview-wrap" id="pv"></div></div>'; await renderInto($('#pv')); box.scrollIntoView({behavior:'smooth'}); }
async function printReport(){ await renderInto($('#printArea')); await document.fonts.ready; setTimeout(()=>window.print(),300); }
window.PRWS={state:()=>S,makeBlob};

function openEditor(){ const T=typeOf(S.report.type); if(T&&T.engine==='generic') genericEditor(T); else if(S.report.type==='ihc') ihcEditor(); else editor(); }
function typeOf(id){ return (S.bundle.reportTypes||[]).find(t=>t.id===(id||'histo')); }
function typeShort(id){ id=id||'histo'; return id==='histo'?'Histo':id==='ihc'?'IHC':((typeOf(id)||{}).name||id); }
// ---------- generic report types (sections from the .dotx) ----------
function newGeneric(T){
  S.report={id:uid('rep'),type:T.id,created:new Date().toISOString(),updated:null,header:Object.fromEntries(HEADER.map(([k])=>[k,''])),values:{},dxId:'',dxName:''};
  S.report.header['reported on']=new Date().toLocaleDateString('en-GB'); genericEditor(T);
}
function genericEditor(T){
  const R=S.report; R.values=R.values||{};
  const V=h=>(R.values[h]=R.values[h]||{});
  const secHtml=(s,si)=>{ const v=R.values[s.heading]||{}; let h=`<div class="card" data-sec="${si}"><h3>${esc(s.heading)}</h3>`;
    const grid=s.parts.filter(p=>p.k==='ghead'||p.k==='grow'||p.k==='dyn');
    for(const p of s.parts){ const key=p.r+'.'+(p.p||0);
      if(p.k==='label') h+=`<label>${esc(p.label.replace(/:\s*$/,''))}</label><textarea data-lab="${si}|${key}" style="min-height:44px">${esc(v[key]||'')}</textarea>`;
      else if(p.k==='free') h+=`<textarea data-free="${si}|${key}" style="min-height:90px" placeholder="One paragraph per line; **Label:** prints bold">${esc(itemsToText(v[key]||[]))}</textarea>`;
      else if(p.k==='ghead'){ const n=p.cols.length; h+=`<div class="capitem" style="grid-template-columns:repeat(${n},1fr) 40px">${p.cols.map(c=>`<b>${esc(c)}</b>`).join('')}<span></span></div>`; }
      else if(p.k==='grow'){ const n=p.cells.length; const vv=v[key]||[]; h+=`<div class="capitem" style="grid-template-columns:repeat(${n},1fr) 40px">${p.cells.map((c,i)=>c.e?`<input data-grow="${si}|${key}|${i}" value="${esc(vv[i]||'')}" placeholder="${esc(c.t.trim())}">`:`<span style="padding:8px 0">${esc(c.t)}</span>`).join('')}<span></span></div>`; }
      else if(p.k==='dyn'){ const rows=v[key]&&v[key].length?v[key]:[Array(p.n).fill('')]; V(s.heading)[key]=rows;
        h+=rows.map((r,ri)=>`<div class="capitem" style="grid-template-columns:repeat(${p.n},1fr) 40px">${r.map((x,ci)=>`<input data-dyn="${si}|${key}|${ri}|${ci}" value="${esc(x||'')}">`).join('')}<button class="small danger" data-dynx="${si}|${key}|${ri}">✕</button></div>`).join('')+`<button class="small light" data-dyna="${si}|${key}|${p.n}">+ Add row</button>`; }
      else if(p.k==='gross'){ const g=v[key]||{containers:[{text:'',gross:''}],sections:''}; V(s.heading)[key]=g;
        h+=g.containers.map((c,ci)=>`<label>Container ${'ABCDEFGHIJ'[ci]}</label><textarea data-gt="${si}|${key}|${ci}" style="min-height:90px">${esc(c.text)}</textarea><label>Gross</label><select data-gs="${si}|${key}|${ci}">${['','Saved.','All embedded.','Partially embedded.'].map(o=>`<option ${o===c.gross?'selected':''} value="${o}">${o||'—'}</option>`).join('')}${c.gross&&!['Saved.','All embedded.','Partially embedded.'].includes(c.gross)?`<option selected>${esc(c.gross)}</option>`:''}</select>`).join('')+
          `<div class="actions"><button class="small light" data-ga="${si}|${key}">+ Container</button></div><label>Sections</label><textarea data-gsec="${si}|${key}" style="min-height:50px">${esc(g.sections)}</textarea>`; }
    }
    return h+'</div>'; };
  const cases=allDx(T.id);
  app.innerHTML=`<h2>${esc(T.name)} report</h2>
  <div class="card"><h3>Patient details</h3><div class="grid">${HEADER.map(([k,l])=>`<div><label>${esc(l)}</label><input data-h="${esc(k)}" value="${esc(R.header[k])}"></div>`).join('')}</div></div>
  <div class="card"><h3>Diagnosis / case template</h3><input id="dxq" placeholder="Search ${cases.length} templates"><div id="dxl" class="dxlist" style="margin-top:8px"></div>
   <p class="hint" id="dxsel">${R.dxName?'Loaded: <b>'+esc(R.dxName)+'</b>':'Choosing one fills the sections below (all editable).'+(T.blankOnPick&&T.blankOnPick.length?' '+esc(T.blankOnPick.join(', ').toLowerCase())+' stay as you entered them.':'')}</p></div>
  ${T.schema.sections.map(secHtml).join('')}
  <div id="layoutBox"></div>
  <div class="card actions" style="position:sticky;bottom:8px"><button id="save">Save…</button><button id="docx" class="alt">Download .docx</button><button id="prev" class="violet">Preview</button><button id="print" class="pink">Print / PDF</button></div>
  <div id="previewBox"></div>`;
  const sec=i=>T.schema.sections[+i].heading;
  $$('[data-h]').forEach(i=>i.oninput=()=>R.header[i.dataset.h]=i.value);
  $$('[data-lab]').forEach(e=>e.oninput=()=>{const[a,k]=e.dataset.lab.split('|');V(sec(a))[k]=e.value;});
  $$('[data-free]').forEach(e=>e.oninput=()=>{const[a,k]=e.dataset.free.split('|');V(sec(a))[k]=textToItems(e.value);});
  $$('[data-grow]').forEach(e=>e.oninput=()=>{const[a,k,i]=e.dataset.grow.split('|');const o=V(sec(a));o[k]=o[k]||[];o[k][+i]=e.value;});
  $$('[data-dyn]').forEach(e=>e.oninput=()=>{const[a,k,r,c]=e.dataset.dyn.split('|');V(sec(a))[k][+r][+c]=e.value;});
  $$('[data-dynx]').forEach(e=>e.onclick=()=>{const[a,k,r]=e.dataset.dynx.split('|');V(sec(a))[k].splice(+r,1);genericEditor(T);});
  $$('[data-dyna]').forEach(e=>e.onclick=()=>{const[a,k,n]=e.dataset.dyna.split('|');V(sec(a))[k].push(Array(+n).fill(''));genericEditor(T);});
  $$('[data-gt]').forEach(e=>e.oninput=()=>{const[a,k,c]=e.dataset.gt.split('|');V(sec(a))[k].containers[+c].text=e.value;});
  $$('[data-gs]').forEach(e=>e.onchange=()=>{const[a,k,c]=e.dataset.gs.split('|');V(sec(a))[k].containers[+c].gross=e.value;});
  $$('[data-ga]').forEach(e=>e.onclick=()=>{const[a,k]=e.dataset.ga.split('|');V(sec(a))[k].containers.push({text:'',gross:''});genericEditor(T);});
  $$('[data-gsec]').forEach(e=>e.oninput=()=>{const[a,k]=e.dataset.gsec.split('|');V(sec(a))[k].sections=e.value;});
  const renderDx=()=>{ const q=$('#dxq').value.toLowerCase(); const L=cases.filter(d=>!q||(d.name+' '+(d.group||'')).toLowerCase().includes(q)).sort((a,b)=>(a.group||'').localeCompare(b.group||'')||a.name.localeCompare(b.name));
    $('#dxl').innerHTML=L.map(d=>`<div class="dx ${d.id===R.dxId?'sel':''}" data-dx="${d.id}"><b>${esc(d.name)}</b> ${d.user?'<span class="tag blue">mine</span>':''}<br><small>${esc(d.nature||'')}${d.group?' · '+esc(d.group):''}</small></div>`).join('')||'<p class="hint" style="padding:10px">No case templates for this report type yet — fill the sections below and use Save → new template.</p>';
    $$('[data-dx]').forEach(el=>el.onclick=()=>pick(el.dataset.dx)); };
  const pick=id=>{ const d=cases.find(x=>x.id===id); if(!d) return;
    const has=Object.entries(R.values).some(([h,v])=>!(T.blankOnPick||[]).includes(h)&&Object.keys(v).length);
    if(has&&!confirm('Replace the report sections with "'+d.name+'"?')) return;
    const keep=Object.fromEntries((T.blankOnPick||[]).filter(h=>R.values[h]).map(h=>[h,R.values[h]]));
    const nv=structuredClone(d.values||{}); for(const h of (T.blankOnPick||[])) delete nv[h];
    R.values={...nv,...keep}; R.dxId=d.id; R.dxName=d.name; if(d.secLayout&&d.secLayout.secs) R.secLayout=structuredClone(d.secLayout); if(d.signout) R.signout=structuredClone(d.signout); genericEditor(T); toast('Template loaded'); };
  $('#dxq').oninput=renderDx; renderDx();
  layoutCard($('#layoutBox')); $('#save').onclick=saveDialog; $('#docx').onclick=()=>exportDocx(); $('#prev').onclick=()=>preview($('#previewBox')); $('#print').onclick=printReport;
}
// ---------- IHC ----------
const IHC_CLIN=['Specimen:','Procedure:','Clinical history:','Previous histopathology no. / Block no.:','Referring diagnosis:','Test requested:'];
const BLOCK=['Block tested:','Fixative:','Platform:']; const CTRL=['External control:','Internal control:'];
const SCORE_DEF={title:'SCORING',cols:['Marker','Scoring system','Score','Interpretation'],widths:[1800,2700,2338,2800],rows:[['','','','']]};
function newIhc(){
  S.report={id:uid('rep'),type:'ihc',created:new Date().toISOString(),updated:null,header:Object.fromEntries(HEADER.map(([k])=>[k,''])),
    clinical:IHC_CLIN.map(l=>({label:l,text:''})),block:Object.fromEntries(BLOCK.map(l=>[l,''])),results:[['','','']],scoring:null,
    controls:Object.fromEntries(CTRL.map(l=>[l,''])),impression:[],comment:[],dxId:'',dxName:''};
  S.report.header['reported on']=new Date().toLocaleDateString('en-GB'); ihcEditor();
}
function ihcEditor(){
  const R=S.report;
  app.innerHTML=`<h2>Immunohistochemistry report</h2>
  <div class="card"><h3>1 · Patient details</h3><div class="grid">${HEADER.map(([k,l])=>`<div><label>${esc(l)}</label><input data-h="${esc(k)}" value="${esc(R.header[k])}"></div>`).join('')}</div></div>
  <div class="card"><h3>2 · Clinical details</h3><div id="clin"></div><div class="actions"><button class="small light" id="addClin">+ Add row</button></div></div>
  <div class="card"><h3>3 · Panel / diagnosis</h3><input id="dxq" placeholder="Search IHC panels"><div id="dxl" class="dxlist" style="margin-top:8px"></div>
   <p class="hint" id="dxsel">${R.dxName?'Loaded: <b>'+esc(R.dxName)+'</b>':'Choosing a panel fills block details, results, scoring, controls, impression and comment (all editable).'}</p></div>
  <div class="card"><h3>4 · Specimen and block details</h3>${BLOCK.map(l=>`<label>${esc(l)}</label><input data-bk="${esc(l)}" value="${esc(R.block[l]||'')}">`).join('')}</div>
  <div class="card"><h3>5 · Immunohistochemistry results</h3><div id="res"></div><div class="actions"><button class="small light" id="addRes">+ Add marker</button></div></div>
  <div class="card"><h3>6 · Scoring</h3><div id="score"></div></div>
  <div class="card"><h3>7 · Controls</h3>${CTRL.map(l=>`<label>${esc(l)}</label><textarea data-ck="${esc(l)}" style="min-height:50px">${esc(R.controls[l]||'')}</textarea>`).join('')}</div>
  <div class="card"><h3>8 · Impression &amp; comment</h3><label>IMPRESSION</label><textarea id="imp">${esc(itemsToText(R.impression))}</textarea>
   <label>Comment</label><textarea id="comment">${esc(itemsToText(R.comment))}</textarea><p class="hint">One paragraph per line. Text between ** ** prints bold.</p></div>
  <div id="layoutBox"></div>
  <div class="card actions" style="position:sticky;bottom:8px"><button id="save">Save…</button><button id="docx" class="alt">Download .docx</button><button id="prev" class="violet">Preview</button><button id="print" class="pink">Print / PDF</button></div>
  <div id="previewBox"></div>`;
  $$('[data-h]').forEach(i=>i.oninput=()=>R.header[i.dataset.h]=i.value);
  const renderClin=()=>{ $('#clin').innerHTML=R.clinical.map((c,i)=>`<div class="row" style="margin-bottom:6px"><input class="narrow" data-cl="${i}" value="${esc(c.label)}" placeholder="Label:"><textarea data-ct="${i}" style="min-height:44px">${esc(c.text)}</textarea><button class="small danger" data-cx="${i}" style="flex:0 0 auto">✕</button></div>`).join('');
    $$('[data-cl]').forEach(e=>e.oninput=()=>R.clinical[e.dataset.cl].label=e.value); $$('[data-ct]').forEach(e=>e.oninput=()=>R.clinical[e.dataset.ct].text=e.value);
    $$('[data-cx]').forEach(e=>e.onclick=()=>{R.clinical.splice(+e.dataset.cx,1);renderClin();}); };
  renderClin(); $('#addClin').onclick=()=>{R.clinical.push({label:'',text:''});renderClin();};
  const bindKV=()=>{ $$('[data-bk]').forEach(e=>e.oninput=()=>R.block[e.dataset.bk]=e.value); $$('[data-ck]').forEach(e=>e.oninput=()=>R.controls[e.dataset.ck]=e.value); }; bindKV();
  const renderRes=()=>{ $('#res').innerHTML=`<div class="capitem" style="grid-template-columns:24% 26% 1fr 40px"><b>Marker (clone)</b><b>Result</b><b>Pattern / expression</b><span></span></div>`+R.results.map((r,i)=>`<div class="capitem" style="grid-template-columns:24% 26% 1fr 40px">${[0,1,2].map(j=>`<input data-r="${i}.${j}" value="${esc(r[j]||'')}">`).join('')}<button class="small danger" data-rx="${i}">✕</button></div>`).join('');
    $$('[data-r]').forEach(e=>e.oninput=()=>{const[a,b]=e.dataset.r.split('.').map(Number);R.results[a][b]=e.value;});
    $$('[data-rx]').forEach(e=>e.onclick=()=>{R.results.splice(+e.dataset.rx,1);renderRes();}); };
  renderRes(); $('#addRes').onclick=()=>{R.results.push(['','','']);renderRes();};
  const renderScore=()=>{ const sc=R.scoring;
    if(!sc){ $('#score').innerHTML='<p class="hint">No scoring table (added between Results and Controls only when a marker is scored).</p><button class="small light" id="addSc">+ Add scoring table</button>'; $('#addSc').onclick=()=>{R.scoring=structuredClone(SCORE_DEF);renderScore();}; return; }
    const gc=`grid-template-columns:repeat(${sc.cols.length},1fr) 40px`;
    $('#score').innerHTML=`<input id="scT" value="${esc(sc.title)}" style="font-weight:700;margin-bottom:6px"><div class="capitem" style="${gc}">${sc.cols.map((c,j)=>`<input data-sh="${j}" value="${esc(c)}" style="font-weight:700">`).join('')}<span></span></div>`+sc.rows.map((r,i)=>`<div class="capitem" style="${gc}">${sc.cols.map((_,j)=>`<input data-s="${i}.${j}" value="${esc(r[j]||'')}">`).join('')}<button class="small danger" data-sx="${i}">✕</button></div>`).join('')+`<div class="actions"><button class="small light" id="addScR">+ Add row</button><button class="small danger" id="delSc">Remove scoring table</button></div>`;
    $('#scT').oninput=e=>sc.title=e.target.value;
    $$('[data-sh]').forEach(e=>e.oninput=()=>sc.cols[+e.dataset.sh]=e.value);
    $$('[data-s]').forEach(e=>e.oninput=()=>{const[a,b]=e.dataset.s.split('.').map(Number);sc.rows[a][b]=e.value;});
    $$('[data-sx]').forEach(e=>e.onclick=()=>{sc.rows.splice(+e.dataset.sx,1);renderScore();});
    $('#addScR').onclick=()=>{sc.rows.push(sc.cols.map(()=>''));renderScore();}; $('#delSc').onclick=()=>{R.scoring=null;renderScore();}; };
  renderScore();
  const renderDx=()=>{ const q=$('#dxq').value.toLowerCase(); const L=allDx('ihc').filter(d=>!q||(d.name+' '+(d.site||'')).toLowerCase().includes(q)).sort((a,b)=>a.name.localeCompare(b.name));
    $('#dxl').innerHTML=L.map(d=>`<div class="dx ${d.id===R.dxId?'sel':''}" data-dx="${d.id}"><b>${esc(d.name)}</b> ${d.scoring?'<span class="tag purple">scoring</span>':''}${d.user?'<span class="tag blue">mine</span>':''}<br><small>${esc(d.nature||'')} · ${esc(d.site||'')} · ${(d.results||[]).length} markers</small></div>`).join('')||'<p class="hint" style="padding:10px">No panels found.</p>';
    $$('[data-dx]').forEach(el=>el.onclick=()=>pick(el.dataset.dx)); };
  const pick=id=>{ const d=allDx('ihc').find(x=>x.id===id); if(!d) return;
    if(R.results.some(r=>r.some(v=>v))&&!confirm('Replace the IHC sections with "'+d.name+'"?')) return;
    Object.assign(R,{dxId:d.id,dxName:d.name,block:{...Object.fromEntries(BLOCK.map(l=>[l,''])),...structuredClone(d.block||{})},results:structuredClone(d.results||[]),scoring:d.scoring?structuredClone(d.scoring):null,
      controls:{...Object.fromEntries(CTRL.map(l=>[l,''])),...structuredClone(d.controls||{})},impression:structuredClone(d.impression||[]),comment:structuredClone(d.comment||[])});
    if(d.secLayout&&d.secLayout.secs) R.secLayout=structuredClone(d.secLayout); if(d.signout) R.signout=structuredClone(d.signout);
    ihcEditor(); toast('Panel loaded'); };
  $('#dxq').oninput=renderDx; renderDx();
  $('#imp').oninput=e=>R.impression=textToItems(e.target.value); $('#comment').oninput=e=>R.comment=textToItems(e.target.value);
  layoutCard($('#layoutBox')); $('#save').onclick=saveDialog; $('#docx').onclick=()=>exportDocx(); $('#prev').onclick=()=>preview($('#previewBox')); $('#print').onclick=printReport;
}

// ---------- sections, rows & sign-out (all report types) ----------
const DEFAULT_DOCTORS=[{id:'doc-wajid',name:'Dr. Wajid Misbahudheen',lines:['Dr. WAJID MISBAHUDHEEN, MD','ASSOCIATE CONSULTANT (PATHOLOGY)','VMSH']},
  {id:'doc-sansina',name:'Dr. Sansina',lines:['Dr. SANSINA N, MD','ASSOCIATE CONSULTANT (PATHOLOGY)','VMSH']}];
async function loadDoctors(){ if(!(await DB.get('meta','doctorsSeeded'))){ for(const d of DEFAULT_DOCTORS) if(!(await DB.get('doctors',d.id))) await DB.put('doctors',d); await DB.put('meta',{id:'doctorsSeeded',at:new Date().toISOString()}); }
  S.doctors=(await DB.all('doctors')).sort((a,b)=>a.name.localeCompare(b.name)); }
function layoutBuf(){ const R=S.report; if(R.type==='ihc') return S.layouts.ihc; const T=typeOf(R.type); if(T&&T.engine==='generic') return S.layouts[T.id]; return S.layouts[R.cap&&R.cap.sections?.length?'cap':'histo']; }
function reconcileLayout(D){ const R=S.report; const L=R.secLayout=(R.secLayout&&R.secLayout.secs)?R.secLayout:{secs:[]}; const hs=D.sections.map(s=>s.heading);
  L.secs=L.secs.filter(s=>s.src==null||hs.includes(s.src));
  hs.forEach((h,i)=>{ if(!L.secs.some(s=>s.src===h)){ const prev=hs.slice(0,i).reverse().find(x=>L.secs.some(s=>s.src===x)); const at=prev?L.secs.findIndex(s=>s.src===prev)+1:0; L.secs.splice(at,0,{src:h,heading:h,del:[],add:[]}); } });
  return L; }
const colsOf=(s,D)=>{ if(s.src==null) return (DocxFill.SECTION_TYPES.find(t=>t.id===s.type)||{widths:[1]}).widths.length; const d=D.sections.find(x=>x.heading===s.src); const r=d.rows[d.rows.length-1]; return r?r.cells:d.cols; };
function layoutCard(box){
  const R=S.report; let D; try{ D=DocxFill.describe(layoutBuf()); }catch(e){ box.innerHTML=''; return; }
  const L=reconcileLayout(D); const ST=DocxFill.SECTION_TYPES;
  const sec=(s,i)=>{ const d=s.src!=null?D.sections.find(x=>x.heading===s.src):null; const n=colsOf(s,D);
    const tname=s.src==null?(ST.find(t=>t.id===s.type)||ST[0]).name:'from template';
    return `<div class="lsec ${s.removed?'removed':''}"><div class="row"><input class="lhead" data-lh="${i}" value="${esc(s.heading)}" ${s.removed?'disabled':''}>
      <button class="small light" data-lu="${i}" style="flex:0 0 auto" ${i?'':'disabled'}>↑</button><button class="small light" data-ld="${i}" style="flex:0 0 auto" ${i<L.secs.length-1?'':'disabled'}>↓</button>
      <button class="small ${s.removed?'alt':'danger'}" data-lrm="${i}" style="flex:0 0 auto">${s.removed?'Restore section':'Remove section'}</button></div>
      <small class="hint">${esc(tname)} · ${n} column${n>1?'s':''}</small>
      ${s.removed?'':`${d?d.rows.map((r,j)=>{const del=(s.del||[]).includes(j);return `<div class="lrow ${del?'del':''}"><span>${esc(r.text||'(empty row – filled above)')}</span><button class="small ${del?'alt':'danger'}" data-ldel="${i}.${j}">${del?'Undo':'Delete row'}</button></div>`;}).join(''):''}
      ${(s.add||[]).map((r,k)=>`<div class="lrow add" style="grid-template-columns:repeat(${n},1fr) auto">${Array.from({length:n},(_,c)=>`<textarea data-lc="${i}.${k}.${c}" placeholder="${n>1?'Column '+(c+1):'New row – **bold** works'}">${esc(r[c]||'')}</textarea>`).join('')}<button class="small danger" data-lrx="${i}.${k}">✕</button></div>`).join('')}
      <div class="actions"><button class="small light" data-lra="${i}">+ Add row</button><button class="small violet" data-las="${i}">+ Add section below</button></div>`}</div>`; };
  box.innerHTML=`<div class="card"><h3>Sections &amp; rows</h3><p class="hint">Add or delete rows, add/remove/move sections, rename headings (always printed in CAPITALS, bold). The last row of each section keeps its thin bottom line. Text between ** ** prints bold.</p>
    <div class="actions"><button class="small violet" data-las="-1">+ Add section at top</button></div>${L.secs.map(sec).join('')}</div><div id="signoutBox"></div>`;
  const ij=k=>k.split('.').map(Number); const re=()=>layoutCard(box);
  $$('[data-lh]',box).forEach(e=>e.oninput=()=>{ const v=e.value.toUpperCase(); if(v!==e.value){const p=e.selectionStart; e.value=v; e.setSelectionRange(p,p);} L.secs[+e.dataset.lh].heading=v; });
  $$('[data-lu]',box).forEach(e=>e.onclick=()=>{const i=+e.dataset.lu; [L.secs[i-1],L.secs[i]]=[L.secs[i],L.secs[i-1]]; re();});
  $$('[data-ld]',box).forEach(e=>e.onclick=()=>{const i=+e.dataset.ld; [L.secs[i+1],L.secs[i]]=[L.secs[i],L.secs[i+1]]; re();});
  $$('[data-lrm]',box).forEach(e=>e.onclick=()=>{const s=L.secs[+e.dataset.lrm]; if(s.src==null&&!s.removed){ if(confirm('Remove the section "'+s.heading+'"?')) L.secs.splice(+e.dataset.lrm,1); } else s.removed=!s.removed; re();});
  $$('[data-ldel]',box).forEach(e=>e.onclick=()=>{const[i,j]=ij(e.dataset.ldel); const s=L.secs[i]; s.del=s.del||[]; const d=D.sections.find(x=>x.heading===s.src);
    if(s.del.includes(j)) s.del=s.del.filter(x=>x!==j); else { if(d&&s.del.length+1>=d.rows.length&&!(s.add||[]).length){ toast('A section needs at least one row – add a row first'); return; } s.del.push(j); } re();});
  $$('[data-lc]',box).forEach(e=>e.oninput=()=>{const[i,k,c]=ij(e.dataset.lc); L.secs[i].add[k][c]=e.value;});
  $$('[data-lrx]',box).forEach(e=>e.onclick=()=>{const[i,k]=ij(e.dataset.lrx); const s=L.secs[i]; const d=s.src!=null?D.sections.find(x=>x.heading===s.src):null; const left=(d?d.rows.length-(s.del||[]).length:0)+s.add.length-1;
    if(left<1){ toast('A section needs at least one row'); return; } s.add.splice(k,1); re();});
  $$('[data-lra]',box).forEach(e=>e.onclick=()=>{const s=L.secs[+e.dataset.lra]; s.add=s.add||[]; s.add.push(Array(colsOf(s,D)).fill('')); re();});
  $$('[data-las]',box).forEach(e=>e.onclick=()=>addSectionDialog(+e.dataset.las,L,re));
  signoutCard($('#signoutBox',box),D);
}
function addSectionDialog(after,L,done){
  const ST=DocxFill.SECTION_TYPES;
  $('#modalBody').innerHTML=`<h3>Add section</h3><label>Heading</label><input id="nsh" placeholder="E.G. SPECIAL STAINS" style="text-transform:uppercase;font-weight:700">
   <label>Section type</label>${ST.map((t,i)=>`<button class="choice-btn ${i?'':'sel'}" data-st="${t.id}"><b>${esc(t.name)}</b><div class="colprev">${t.widths.map(w=>`<span style="flex:${w}"></span>`).join('')}</div></button>`).join('')}
   <div class="actions"><button id="nsok">Add section</button><button class="light" id="mcancel">Cancel</button></div>`;
  $('#modal').classList.remove('hidden'); let type=ST[0].id;
  $$('[data-st]').forEach(b=>b.onclick=()=>{ type=b.dataset.st; $$('[data-st]').forEach(x=>x.classList.toggle('sel',x===b)); });
  $('#mcancel').onclick=()=>$('#modal').classList.add('hidden');
  $('#nsok').onclick=()=>{ const h=$('#nsh').value.trim().toUpperCase(); if(!h){ toast('Type a heading'); return; } const n=ST.find(t=>t.id===type).widths.length;
    L.secs.splice(after+1,0,{src:null,type,heading:h,add:[Array(n).fill('')]}); $('#modal').classList.add('hidden'); done(); };
}
function signoutCard(box,D){
  const R=S.report; const docs=S.doctors||[]; const byId=id=>docs.find(d=>d.id===id);
  if(!R.signout){ R.signout={n:2,d1:'doc-sansina',d2:'doc-wajid'}; }
  const so=R.signout; const resolve=()=>{ const a=byId(so.d1), b=byId(so.d2);
    if(so.n===1){ so.left=['CHECKED BY']; so.right=a?a.lines.slice():(so.right||[]); } else { so.left=a?a.lines.slice():(so.left||[]); so.right=b?b.lines.slice():(so.right||[]); } };
  resolve();
  const opts=sel=>`<option value="">— choose doctor —</option>`+docs.map(d=>`<option value="${d.id}" ${d.id===sel?'selected':''}>${esc(d.name)}</option>`).join('');
  const prevCol=lines=>`<div class="socol">${(lines||[]).map(l=>`<div>${esc(l)}</div>`).join('')||'&nbsp;'}</div>`;
  box.innerHTML=`<div class="card"><h3>Sign-out</h3><div class="actions"><span class="hint" style="margin:0">Doctors signing:</span><button class="small ${so.n===1?'':'light'}" data-son="1">1 doctor</button><button class="small ${so.n===2?'':'light'}" data-son="2">2 doctors</button></div>
    ${so.n===2?`<div class="grid"><div><label>Doctor 1 (left)</label><select data-sod="d1">${opts(so.d1)}</select></div><div><label>Doctor 2 (right)</label><select data-sod="d2">${opts(so.d2)}</select></div></div>`
      :`<div class="grid"><div><label>Left</label><input value="CHECKED BY" disabled></div><div><label>Signing doctor (right)</label><select data-sod="d1">${opts(so.d1)}</select></div></div>`}
    <div class="soprev">${prevCol(so.left)}<div class="socol mid"></div>${prevCol(so.right)}</div>
    <div class="actions"><button class="small light" id="mandoc">Manage doctors…</button></div></div>`;
  const re=()=>signoutCard(box,D);
  $$('[data-son]',box).forEach(b=>b.onclick=()=>{ const n=+b.dataset.son; if(n===so.n) return; if(n===1){ so.d1=so.d2||so.d1; } else { so.d2=so.d1; so.d1=docs.find(d=>d.id!==so.d2)?.id||''; } so.n=n; re(); });
  $$('[data-sod]',box).forEach(e=>e.onchange=()=>{ so[e.dataset.sod]=e.value; re(); });
  $('#mandoc',box).onclick=()=>doctorsDialog(re);
}
function doctorsDialog(done){
  const render=()=>{ const docs=S.doctors||[];
    $('#modalBody').innerHTML=`<h3>Doctors (sign-out)</h3><p class="hint">Saved on this tablet only; never erased by Update templates.</p>
     <div class="list">${docs.map(d=>`<div class="item"><div><b>${esc(d.name)}</b><br><small class="hint">${d.lines.map(esc).join(' · ')}</small></div><div class="actions"><button class="small light" data-de="${d.id}">Edit</button><button class="small danger" data-dd="${d.id}">Delete</button></div></div>`).join('')||'<p class="hint">No doctors.</p>'}</div>
     <div class="actions"><button class="small violet" id="dadd">+ Add doctor</button><button class="light" id="mclose">Done</button></div>`;
    $('#mclose').onclick=()=>{ $('#modal').classList.add('hidden'); done(); };
    $('#dadd').onclick=()=>edit(null);
    $$('[data-de]').forEach(b=>b.onclick=()=>edit(docs.find(d=>d.id===b.dataset.de)));
    $$('[data-dd]').forEach(b=>b.onclick=async()=>{ const d=docs.find(x=>x.id===b.dataset.dd); if(!confirm('Delete '+d.name+'?')) return; await DB.del('doctors',d.id); await loadDoctors(); render(); }); };
  const edit=d=>{ $('#modalBody').innerHTML=`<h3>${d?'Edit':'Add'} doctor</h3><label>Name (for the picker)</label><input id="dn" value="${esc(d?.name||'')}" placeholder="Dr. …">
     <label>Sign-out lines (one per line, printed bold and centred)</label><textarea id="dl" style="min-height:110px" placeholder="Dr. NAME, MD&#10;DESIGNATION&#10;HOSPITAL">${esc((d?.lines||[]).join('\n'))}</textarea>
     <div class="actions"><button id="dsave">Save</button><button class="light" id="dback">Back</button></div>`;
    $('#dback').onclick=render;
    $('#dsave').onclick=async()=>{ const name=$('#dn').value.trim(); const lines=$('#dl').value.split('\n').map(x=>x.trim()).filter(Boolean); if(!name){toast('Type a name');return;}
      await DB.put('doctors',{id:d?.id||uid('doc'),name,lines:lines.length?lines:[name]}); await loadDoctors(); render(); }; };
  $('#modal').classList.remove('hidden'); render();
}
// ---------- boot ----------
$('#navHome').onclick=home; $('#navReports').onclick=reportsScreen; $('#navData').onclick=dataScreen;
(async()=>{ try{ await loadBundle(false); try{ await loadDoctors(); }catch(e){ S.doctors=DEFAULT_DOCTORS; } home(); }catch(e){ app.innerHTML=`<div class="card"><h3>Templates not loaded</h3><p>${esc(e.message)}. Connect to the internet once to download the templates.</p></div>`; } })();
if('serviceWorker' in navigator) { navigator.serviceWorker.register('sw.js',{updateViaCache:'none'}).then(r=>r.update()).catch(()=>{}); let rl=false; navigator.serviceWorker.addEventListener('controllerchange',()=>{ if(!rl){rl=true; location.reload();} }); }
if(navigator.storage&&navigator.storage.persist) navigator.storage.persist();
})();
