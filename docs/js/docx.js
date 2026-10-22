// Path Reporter WS - fills a copy of Wajid's own .dotx in the browser (layout, margins, fonts untouched).
// Port of the rules used to build the case-based templates (casetemplates/tools/lib.py).
(function(){
const W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const W14='http://schemas.microsoft.com/office/word/2010/wordml';
const XMLNS='http://www.w3.org/XML/1998/namespace';
const DOTX_CT='application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml';
const DOCX_CT='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml';
const kids=(el,tag)=>Array.from(el.childNodes).filter(n=>n.nodeType===1&&n.namespaceURI===W&&n.localName===tag);
const kid=(el,tag)=>kids(el,tag)[0]||null;
const desc=(el,tag)=>Array.from(el.getElementsByTagNameNS(W,tag));
const text=el=>desc(el,'t').map(t=>t.textContent).join('');
const rows=t=>kids(t,'tr');
const cells=tr=>kids(tr,'tc');
const paras=tc=>kids(tc,'p');
function wel(doc,tag){return doc.createElementNS(W,'w:'+tag);}
function stripW14(el){
  const all=[el,...el.getElementsByTagName('*')];
  for(const e of all){ for(const a of Array.from(e.attributes||[])){ if(a.namespaceURI===W14) e.removeAttributeNode(a);} }
  return el;
}
function stripBold(rpr){ if(!rpr) return null; rpr=rpr.cloneNode(true); for(const t of ['b','bCs']) kids(rpr,t).forEach(e=>rpr.removeChild(e)); return rpr;}
function addBold(doc,rpr){
  rpr=rpr?rpr.cloneNode(true):wel(doc,'rPr');
  if(!kid(rpr,'b')){
    let ref=null; for(const c of Array.from(rpr.childNodes)){ if(c.nodeType===1&&!['rStyle','rFonts'].includes(c.localName)){ref=c;break;} }
    const b=wel(doc,'b'), bc=wel(doc,'bCs'); rpr.insertBefore(b,ref); rpr.insertBefore(bc,ref);
  }
  return rpr;
}
function mkrun(doc,txt,rpr){
  const r=wel(doc,'r'); if(rpr&&rpr.childNodes.length) r.appendChild(rpr.cloneNode(true));
  const t=wel(doc,'t'); t.setAttributeNS(XMLNS,'xml:space','preserve'); t.textContent=txt; r.appendChild(t); return r;
}
function baseRpr(p){
  const rs=kids(p,'r');
  for(const r of rs){ const rp=kid(r,'rPr'); if(!rp||!kid(rp,'b')) return rp?rp.cloneNode(true):null; }
  if(rs.length) return stripBold(kid(rs[0],'rPr'));
  const ppr=kid(p,'pPr'); return stripBold(ppr?kid(ppr,'rPr'):null);
}
function labelRpr(doc,p){
  for(const r of kids(p,'r')){ const rp=kid(r,'rPr'); if(rp&&kid(rp,'b')) return rp.cloneNode(true);} return addBold(doc,baseRpr(p));
}
function dropTrailingSpaceRuns(p){
  const rs=kids(p,'r');
  for(let i=rs.length-1;i>=0;i--){ const r=rs[i]; const rp=kid(r,'rPr');
    if(text(r).trim()===''&&!(rp&&kid(rp,'b'))&&!kid(r,'tab')) p.removeChild(r); else break; }
}
function appendValue(doc,p,value){
  const rpr=baseRpr(p); dropTrailingSpaceRuns(p);
  const lab=text(p); const sep=(lab.endsWith(' ')||lab==='')?'':' ';
  if(value) p.appendChild(mkrun(doc,sep+value,rpr));
}
function setPlain(doc,p,value,heading){
  const rpr=baseRpr(p); kids(p,'r').forEach(r=>p.removeChild(r));
  if(heading){ p.appendChild(mkrun(doc,heading,addBold(doc,rpr))); value=value?' '+value:''; }
  if(value) p.appendChild(mkrun(doc,value,rpr));
}
function cloneParaAfter(p){
  const n=p.cloneNode(true); kids(n,'r').forEach(r=>n.removeChild(r)); kids(n,'proofErr').forEach(r=>n.removeChild(r));
  stripW14(n); p.parentNode.insertBefore(n,p.nextSibling); return n;
}
function fillCellParas(doc,tc,items){
  const ps=paras(tc); let p=ps[0]; ps.slice(1).forEach(x=>tc.removeChild(x));
  items=items.filter(it=>(it.label||'').trim()||(it.text||'').trim());
  let first=true;
  for(const it of items){ if(!first) p=cloneParaAfter(p); setPlain(doc,p,it.text||'',it.label||null); first=false; }
}
function table(body,heading){
  const norm=s=>s.toUpperCase().replace(/\s/g,'');
  for(const t of kids(body,'tbl')){ if(norm(text(rows(t)[0]))===norm(heading)) return t; }
  throw new Error('Table not found: '+heading);
}
function fillGross(doc,t,containers,sections){
  const rs=rows(t); const desc0=rs[1], gr0=rs[2], sec=rs[3]; const L='ABCDEFGHIJKL';
  containers=containers.length?containers:[{text:'',gross:''}];
  const lrpr=labelRpr(doc,desc(gr0,'p')[0]); const prpr=stripBold(lrpr);
  containers.forEach((c,i)=>{
    let d=desc0,g=gr0;
    if(i>0){
      d=stripW14(desc0.cloneNode(true)); g=stripW14(gr0.cloneNode(true));
      const tcpr=desc(d,'tcPr')[0]; const b=tcpr&&kid(tcpr,'tcBorders'); if(b) tcpr.removeChild(b);
      t.insertBefore(d,sec); t.insertBefore(g,sec);
      desc(g,'p').forEach(p=>kids(p,'r').slice(1).forEach(r=>p.removeChild(r)));
    }
    const p=desc(d,'p')[0]; kids(p,'r').forEach(r=>p.removeChild(r));
    if(containers.length>1||c.forceLabel!==false){ p.appendChild(mkrun(doc,'Container '+L[i]+':',lrpr)); p.appendChild(mkrun(doc,' '+(c.text||''),prpr)); }
    appendValue(doc,desc(g,'p')[0],c.gross||'');
  });
  appendValue(doc,desc(sec,'p')[0],sections||'');
}
function fillClinical(doc,t,items){
  const rs=rows(t); const tplRows=rs.slice(1); const last=tplRows[tplRows.length-1]; const mid=tplRows[Math.min(1,tplRows.length-1)];
  const lab=tr=>text(tr).trim().replace(/:$/,'').trim().toLowerCase();
  const used=new Set(); const extras=[];
  for(const it of items){
    if(!(it.label||'').trim()&&!(it.text||'').trim()) continue;
    const tr=tplRows.find(r=>!used.has(r)&&lab(r)===(it.label||'').trim().replace(/:$/,'').toLowerCase());
    if(tr){ used.add(tr); appendValue(doc,desc(tr,'p')[0],it.text||''); } else extras.push(it);
  }
  for(const it of extras){
    const tr=stripW14(mid.cloneNode(true)); const tcpr=desc(tr,'tcPr')[0]; const b=tcpr&&kid(tcpr,'tcBorders'); if(b) tcpr.removeChild(b);
    const p=desc(tr,'p')[0]; const lr=labelRpr(doc,p); const vr=baseRpr(p); kids(p,'r').forEach(r=>p.removeChild(r)); kids(p,'proofErr').forEach(r=>p.removeChild(r));
    let L=(it.label||'').trim(); if(L&&!L.endsWith(':')) L+=':';
    if(L) p.appendChild(mkrun(doc,L,lr)); p.appendChild(mkrun(doc,(L?' ':'')+(it.text||''),vr));
    t.insertBefore(tr,last);
  }
  // keep template's bottom thin line: if extras exist the last template row stays last
}
function buildCap(doc,t,title,sections){
  const rs=rows(t); const hdr=rs[0], firstHead=rs[1], itemTpl=rs[2], headTpl=rs[3], lastTpl=rs[rs.length-1];
  const hp=desc(hdr,'p')[0]; const hr=kids(hp,'r'); desc(hr[0],'t')[0].textContent='SYNOPTIC REPORT';
  hr.slice(1).forEach(r=>hp.removeChild(r)); hp.appendChild(mkrun(doc,' '+title,kid(hr[0],'rPr')));
  const ptpl=desc(itemTpl,'p')[0].cloneNode(true); const labR=kid(kids(ptpl,'r')[0],'rPr');
  const labRpr=labR?labR.cloneNode(true):null;
  kids(ptpl,'r').forEach(r=>ptpl.removeChild(r)); kids(ptpl,'proofErr').forEach(r=>ptpl.removeChild(r)); stripW14(ptpl);
  const lastTc=desc(lastTpl,'tcPr')[0]; const lastB=lastTc&&kid(lastTc,'tcBorders')?kid(lastTc,'tcBorders').cloneNode(true):null;
  rs.slice(1).forEach(r=>t.removeChild(r));
  const nw=[];
  sections.forEach((s,si)=>{
    const h=stripW14((si===0?firstHead:headTpl).cloneNode(true)); const hp=desc(h,'p')[0]; const hrs=kids(hp,'r');
    const hrpr=hrs.length?kid(hrs[0],'rPr'):null; hrs.forEach(r=>hp.removeChild(r)); kids(hp,'proofErr').forEach(r=>hp.removeChild(r));
    hp.appendChild(mkrun(doc,s.heading+':',hrpr?hrpr.cloneNode(true):null)); t.appendChild(h); nw.push(h);
    const it=stripW14(itemTpl.cloneNode(true)); const tc=kid(it,'tc'); paras(tc).forEach(p=>tc.removeChild(p));
    const items=s.items.length?s.items:[{label:null,value:'',ilvl:0}];
    for(const x of items){
      const p=ptpl.cloneNode(true); const np=desc(p,'numPr')[0];
      if(np){ kid(np,'ilvl').setAttributeNS(W,'w:val',String(x.ilvl||0)); kid(np,'numId').setAttributeNS(W,'w:val',String(s.numId||3)); }
      if(x.label){ p.appendChild(mkrun(doc,x.label+':-',labRpr)); p.appendChild(mkrun(doc,' '+(x.value||''),null)); }
      else p.appendChild(mkrun(doc,x.value||'',null));
      tc.appendChild(p);
    }
    t.appendChild(it); nw.push(it);
  });
  const tcpr=desc(nw[nw.length-1],'tcPr')[0]; const old=kid(tcpr,'tcBorders'); if(old) tcpr.removeChild(old);
  if(lastB){ const tcw=kid(tcpr,'tcW'); tcpr.insertBefore(lastB,tcw?tcw.nextSibling:tcpr.firstChild); }
}
function fillHeader(doc,root,fields){
  const norm=s=>s.trim().replace(/:$/,'').trim().toLowerCase();
  for(const t of desc(root,'tbl')) for(const tr of rows(t)){
    const cs=cells(tr);
    for(let i=0;i<cs.length-1;i++){
      const k=norm(text(cs[i])); if(!k) continue;
      if(k in fields && text(cs[i+1]).trim()===''){ appendValue(doc,desc(cs[i+1],'p')[0],fields[k]||''); }
    }
  }
}

// ---------------- Layout layer (all report types): rows, sections, headings, sign-out ----------------
// Section types = Wajid's 'Type of sections.docx' (Pathology Reporting Assets).
const SECTION_TYPES=[
  {id:'single',name:'Single column section',widths:[9638]},
  {id:'two-sym',name:'Two column symmetrical section',widths:[4819,4819]},
  {id:'two-asym',name:'Two column asymmetrical section',widths:[3212,6426]},
  {id:'three',name:'Three column section',widths:[3212,3213,3213]},
  {id:'four',name:'Four column section',widths:[2409,2410,2409,2410]}];
const isSep=n=>n&&n.nodeType===1&&n.localName==='p'&&!text(n).trim()&&!desc(n,'drawing').length;
function topTables(body){ return kids(body,'tbl'); }
function describe(buf){
  const zip=new PizZip(buf); const doc=new DOMParser().parseFromString(zip.file('word/document.xml').asText(),'application/xml');
  const ts=topTables(desc(doc,'body')[0]); const so=ts[ts.length-1];
  return {sections:ts.slice(0,-1).map(t=>({heading:text(rows(t)[0]).trim(),cols:kids(kid(t,'tblGrid')||t,'gridCol').length||1,
      rows:rows(t).slice(1).map(tr=>({cells:cells(tr).length,text:cells(tr).map(tc=>paras(tc).map(text).join(' ').trim()).join(' | ')}))})),
    signout:so?cells(rows(so)[rows(so).length-1]).map(tc=>paras(tc).map(text).filter(x=>x.trim())):[]};
}
// bold markup: "**Word** rest" -> runs
function boldRuns(doc,p,line,rpr){
  const base=stripBold(rpr); const bold=addBold(doc,base);
  String(line).split(/(\*\*[^*]+?\*\*)/).forEach(seg=>{ if(!seg) return; const m=seg.match(/^\*\*([^*]+?)\*\*$/); p.appendChild(mkrun(doc,m?m[1]:seg,m?bold:base)); });
}
function setCellText(doc,tc,txt){
  const ps=paras(tc); const p0=ps[0]||tc.appendChild(wel(doc,'p')); const rpr=baseRpr(p0);
  ps.slice(1).forEach(x=>tc.removeChild(x)); Array.from(p0.childNodes).forEach(n=>{ if(!(n.nodeType===1&&n.localName==='pPr')) p0.removeChild(n); });
  const lines=String(txt||'').split('\n'); let p=p0;
  lines.forEach((l,i)=>{ if(i){ const n=p0.cloneNode(true); Array.from(n.childNodes).forEach(c=>{ if(!(c.nodeType===1&&c.localName==='pPr')) n.removeChild(c); }); tc.appendChild(n); p=n; } if(l) boldRuns(doc,p,l,rpr); });
}
function tcBorders(doc,tc,create){ let pr=kid(tc,'tcPr'); if(!pr){ if(!create) return null; pr=wel(doc,'tcPr'); tc.insertBefore(pr,tc.firstChild);} let b=kid(pr,'tcBorders');
  if(!b&&create){ b=wel(doc,'tcBorders'); const after=kid(pr,'vMerge')||kid(pr,'gridSpan')||kid(pr,'tcW'); pr.insertBefore(b,after?after.nextSibling:pr.firstChild); } return b; }
const BORDER_ORDER=['top','start','left','bottom','end','right','insideH','insideV','tl2br','tr2bl'];
function setBorder(doc,tc,side,sz){
  const b=tcBorders(doc,tc,sz!=null); if(!b) return; kids(b,side).forEach(e=>b.removeChild(e)); if(sz==null){ if(!kids(b,'*').length&&!Array.from(b.childNodes).some(n=>n.nodeType===1)) b.parentNode.removeChild(b); return; }
  const e=wel(doc,side); e.setAttributeNS(W,'w:val','single'); e.setAttributeNS(W,'w:sz',String(sz)); e.setAttributeNS(W,'w:space','0'); e.setAttributeNS(W,'w:color','auto');
  const idx=BORDER_ORDER.indexOf(side); let ref=null; for(const c of Array.from(b.childNodes)){ if(c.nodeType===1&&BORDER_ORDER.indexOf(c.localName)>idx){ref=c;break;} } b.insertBefore(e,ref);
}
const getBorder=(tc,side)=>{ const pr=kid(tc,'tcPr'); const b=pr&&kid(pr,'tcBorders'); const e=b&&kid(b,side); return e&&e.getAttributeNS(W,'val')!=='none'?+(e.getAttributeNS(W,'sz')||4):null; };
function fixLast(doc,t){ // last row of a section: thin bottom line; heading row: thick
  const rs=rows(t); if(!rs.length) return; rs.forEach((tr,i)=>{ if(i===rs.length-1&&i>0) cells(tr).forEach(tc=>setBorder(doc,tc,'bottom',4)); });
  cells(rs[0]).forEach(tc=>setBorder(doc,tc,'bottom',18));
}
function addRowTo(doc,t,vals,multi){
  const rs=rows(t); const last=rs[rs.length-1]; const fromHead=rs.length===1;
  const tr=stripW14(last.cloneNode(true)); kids(tr,'tblPrEx').forEach(e=>tr.removeChild(e));
  if(fromHead){ // section had only its heading: build a plain body row from the grid
    const ws=kids(kid(t,'tblGrid'),'gridCol').map(g=>+g.getAttributeNS(W,'w'));
    cells(tr).forEach(c=>tr.removeChild(c));
    ws.forEach((w,i)=>{ const tc=frag(doc,`<w:tc><w:tcPr><w:tcW w:w="${w}" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:after="60"/><w:rPr><w:lang w:val="en-IN"/></w:rPr></w:pPr></w:p></w:tc>`); tr.appendChild(tc);
      if(ws.length>1){ if(i) setBorder(doc,tc,'left',4); if(i<ws.length-1) setBorder(doc,tc,'right',4); } });
  }
  else {
    cells(tr).forEach(tc=>{ if(getBorder(tc,'top')===18) setBorder(doc,tc,'top',multi?4:null); });
    if(!multi) cells(last).forEach(tc=>setBorder(doc,tc,'bottom',null));
  }
  if(multi&&!fromHead) cells(tr).forEach(tc=>setBorder(doc,tc,'top',4));
  cells(tr).forEach((tc,i)=>setCellText(doc,tc,(vals||[])[i]||''));
  t.appendChild(tr); fixLast(doc,t); return tr;
}
function setHeading(doc,t,h){
  const tc=cells(rows(t)[0])[0]; const p=paras(tc)[0]; const rs=kids(p,'r'); const rpr=addBold(doc,rs.length?kid(rs[0],'rPr'):null);
  paras(tc).slice(1).forEach(x=>tc.removeChild(x)); Array.from(p.childNodes).forEach(n=>{ if(!(n.nodeType===1&&n.localName==='pPr')) p.removeChild(n); });
  p.appendChild(mkrun(doc,String(h||'').toUpperCase(),rpr));
}
const TBLPR=`<w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="9638" w:type="dxa"/><w:tblBorders>${'top left bottom right insideH insideV'.split(' ').map(s=>`<w:${s} w:val="none" w:sz="0" w:space="0" w:color="auto"/>`).join('')}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>`;
function newSection(doc,type,heading,rowsVals){
  const T=SECTION_TYPES.find(x=>x.id===type)||SECTION_TYPES[0]; const n=T.widths.length;
  const t=frag(doc,`<w:tbl>${TBLPR}<w:tblGrid>${T.widths.map(w=>`<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid><w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="340"/></w:trPr><w:tc><w:tcPr><w:tcW w:w="9638" w:type="dxa"/>${n>1?`<w:gridSpan w:val="${n}"/>`:''}<w:tcBorders><w:bottom w:val="single" w:sz="18" w:space="0" w:color="auto"/></w:tcBorders></w:tcPr><w:p><w:pPr><w:keepNext/><w:spacing w:after="40"/></w:pPr><w:r><w:rPr><w:b/><w:bCs/><w:lang w:val="en-IN"/></w:rPr><w:t></w:t></w:r></w:p></w:tc></w:tr></w:tbl>`);
  setHeading(doc,t,heading||'NEW SECTION');
  const rv=(rowsVals&&rowsVals.length)?rowsVals:[Array(n).fill('')];
  rv.forEach(v=>addRowTo(doc,t,v,n>1));
  return t;
}
function capture(body){ const ts=topTables(body); return {tables:ts.slice(0,-1).map(t=>({t,h:text(rows(t)[0]).trim(),rows:rows(t).slice(1)})),signout:ts[ts.length-1]}; }
function applySignout(doc,so,S){
  if(!so||!S||!S.n) return; const tr=rows(so)[rows(so).length-1]; const cs=cells(tr); if(cs.length<3) return;
  const left=S.n===1?['CHECKED BY']:(S.left||[]); const right=S.right||[];
  [[cs[0],left],[cs[2],right]].forEach(([tc,lines])=>{
    const ps=paras(tc); const p0=ps[0]; const rs=kids(p0,'r'); const rpr=rs.length?kid(rs[0],'rPr'):(kid(p0,'pPr')&&kid(kid(p0,'pPr'),'rPr'));
    ps.slice(1).forEach(x=>tc.removeChild(x)); Array.from(p0.childNodes).forEach(n=>{ if(!(n.nodeType===1&&n.localName==='pPr')) p0.removeChild(n); });
    const L=lines.filter(x=>String(x).trim()); (L.length?L:['']).forEach((l,i)=>{ let p=p0; if(i){ p=stripW14(p0.cloneNode(true)); Array.from(p.childNodes).forEach(n=>{ if(!(n.nodeType===1&&n.localName==='pPr')) p.removeChild(n); }); tc.appendChild(p);} if(l) p.appendChild(mkrun(doc,l,rpr?rpr.cloneNode(true):null)); });
  });
}
// R.secLayout: {secs:[{src,type,heading,removed,del:[rowIdx],add:[[cell..]]}]}; signout: {n,left:[lines],right:[lines]}
function applyLayout(doc,body,pre,R){
  const L=R.secLayout; applySignout(doc,pre.signout,R.signout);
  if(!L||!L.secs||!L.secs.length) return;
  const byH=new Map(); pre.tables.forEach(x=>{ if(!byH.has(x.h)) byH.set(x.h,x); });
  // blocks: each captured table + following nodes until next captured table / sign-out table
  const capSet=new Set(pre.tables.map(x=>x.t)); const block=new Map();
  for(const x of pre.tables){ const b=[x.t]; let n=x.t.nextSibling; while(n&&!capSet.has(n)&&n!==pre.signout){ b.push(n); n=n.nextSibling; } block.set(x.t,b); }
  const sepProto=pre.tables.map(x=>block.get(x.t).find(isSep)).find(Boolean);
  const anchor=pre.tables.length?pre.tables[0].t:pre.signout; const parent=anchor.parentNode;
  const startMark=wel(doc,'p'); parent.insertBefore(startMark,anchor);
  for(const x of pre.tables) for(const n of block.get(x.t)) if(n.parentNode) n.parentNode.removeChild(n);
  const used=new Set();
  for(const s of L.secs){
    let t,b;
    if(s.src!=null){ const x=byH.get(s.src); if(!x||used.has(x)) continue; used.add(x); if(s.removed) continue; t=x.t; b=block.get(t);
      const multi=kids(kid(t,'tblGrid')||t,'gridCol').length>1;
      const dels=(s.del||[]).map(i=>x.rows[i]).filter(r=>r&&r.parentNode===t);
      if(dels.length){ const topB=cells(x.rows[0]||rows(t)[1]||rows(t)[0]).map(tc=>getBorder(tc,'top'));
        dels.forEach(r=>t.removeChild(r)); const r1=rows(t)[1]; if(r1&&topB[0]===18) cells(r1).forEach(tc=>setBorder(doc,tc,'top',18)); fixLast(doc,t); }
      (s.add||[]).forEach(v=>addRowTo(doc,t,v,multi));
      if(s.heading!=null&&s.heading.trim()&&s.heading.trim()!==s.src) setHeading(doc,t,s.heading);
    } else { if(s.removed) continue; t=newSection(doc,s.type,s.heading,s.add); const sp=sepProto?stripW14(sepProto.cloneNode(true)):wel(doc,'p'); b=[t,sp]; }
    for(const n of b) parent.insertBefore(n,startMark);
  }
  // template sections the layout does not mention stay (in their original order) after the listed ones
  for(const x of pre.tables) if(!used.has(x)) for(const n of block.get(x.t)) parent.insertBefore(n,startMark);
  parent.removeChild(startMark);
}
const ser=d=>{let s=new XMLSerializer().serializeToString(d); if(!s.startsWith('<?xml')) s='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'+s; return s;};
// report: {header:{name:..}, clinical:[{label,text}], gross:{containers:[{text,gross}],sections}, micro:[], finalDiagnosis:[], comment:[], cap:{title,sections}|null}
function buildDocx(templateBuf,report){
  const zip=new PizZip(templateBuf);
  const P=new DOMParser();
  const doc=P.parseFromString(zip.file('word/document.xml').asText(),'application/xml');
  const body=desc(doc,'body')[0]; const pre=capture(body);
  fillClinical(doc,table(body,'CLINICAL DETAILS'),report.clinical||[]);
  fillGross(doc,table(body,'GROSS DESCRIPTION'),report.gross.containers||[],report.gross.sections||'');
  fillCellParas(doc,cells(rows(table(body,'MICROSCOPIC DESCRIPTION'))[1])[0],report.micro||[]);
  if(report.cap&&report.cap.sections&&report.cap.sections.length) buildCap(doc,table(body,'SYNOPTIC REPORT (CAP protocol, June 2025)'),report.cap.title||'',report.cap.sections);
  fillCellParas(doc,cells(rows(table(body,'FINAL DIAGNOSIS'))[1])[0],report.finalDiagnosis||[]);
  fillCellParas(doc,cells(rows(table(body,'COMMENT'))[1])[0],report.comment||[]);
  applyLayout(doc,body,pre,report);
  zip.file('word/document.xml',ser(doc));
  for(const f of Object.keys(zip.files)){ if(/^word\/header\d*\.xml$/.test(f)){
    const h=P.parseFromString(zip.file(f).asText(),'application/xml'); fillHeader(h,h.documentElement,report.header||{}); zip.file(f,ser(h)); } }
  const ct=zip.file('[Content_Types].xml').asText(); zip.file('[Content_Types].xml',ct.replace(DOTX_CT,DOCX_CT));
  return zip.generate({type:'blob',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',compression:'DEFLATE'});
}

// ---------------- IHC (port of casetemplates/ihc_cases/build.py) ----------------
const LANG='<w:lang w:val="en-IN"/>';
const xesc=t=>String(t??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function frag(doc,xml){ const d=new DOMParser().parseFromString(`<root xmlns:w="${W}">${xml}</root>`,'application/xml'); const e=Array.from(d.documentElement.childNodes).find(n=>n.nodeType===1); return doc.importNode(e,true); }
function ihcRun(doc,t,b){ return frag(doc,`<w:r><w:rPr>${b?'<w:b/><w:bCs/>':''}${LANG}</w:rPr><w:t xml:space="preserve">${xesc(t)}</w:t></w:r>`); }
const NONE=['top','left','bottom','right','insideH','insideV'].map(s=>`<w:${s} w:val="none" w:sz="0" w:space="0" w:color="auto"/>`).join('');
function scoreTable(doc,title,cols,widths,data){
  const bd=(top,bot)=>{const x=(top?'<w:top w:val="single" w:sz="18" w:space="0" w:color="auto"/>':'')+(bot?`<w:bottom w:val="single" w:sz="${bot}" w:space="0" w:color="auto"/>`:''); return x?`<w:tcBorders>${x}</w:tcBorders>`:'';};
  const p=(t,b,after=60,keep=false)=>t?`<w:p><w:pPr>${keep?'<w:keepNext/>':''}<w:spacing w:after="${after}"/><w:jc w:val="left"/></w:pPr><w:r><w:rPr>${b?'<w:b/><w:bCs/>':''}${LANG}</w:rPr><w:t xml:space="preserve">${xesc(t)}</w:t></w:r></w:p>`:`<w:p><w:pPr><w:spacing w:after="${after}"/></w:pPr></w:p>`;
  const c=(w,content,b,span=1)=>`<w:tc><w:tcPr><w:tcW w:w="${w}" w:type="dxa"/>${span>1?`<w:gridSpan w:val="${span}"/>`:''}${b}</w:tcPr>${content}</w:tc>`;
  const tr=cs=>`<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="340"/></w:trPr>${cs}</w:tr>`;
  const rows=[tr(c(9638,p(title,true,40,true),bd(false,18),cols.length))];
  rows.push(tr(cols.map((h,i)=>c(widths[i],p(h,true),bd(true))).join('')));
  data.forEach((r,i)=>{const last=i===data.length-1; rows.push(tr(cols.map((_,j)=>c(widths[j],p(r[j]||''),bd(false,last?4:null))).join('')));});
  const g=widths.map(w=>`<w:gridCol w:w="${w}"/>`).join('');
  return frag(doc,`<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="9638" w:type="dxa"/><w:tblBorders>${NONE}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>${g}</w:tblGrid>${rows.join('')}</w:tbl>`);
}
function fillLabels(doc,t,vals){
  for(const tr of rows(t).slice(1)){ const p=desc(tr,'p')[0]; const lab=text(p).trim(); const v=vals[lab]??vals[lab.replace(/:$/,'')]; if(v) p.appendChild(ihcRun(doc,v)); }
}
function fillFree(doc,t,plist){
  const tc=cells(rows(t)[1])[0]; const p0=kids(tc,'p')[0];
  plist.filter(x=>x.some(([t])=>String(t).trim())).forEach((runs,i)=>{
    let p=p0; if(i){ p=stripW14(p0.cloneNode(true)); kids(p,'r').forEach(r=>p.removeChild(r)); tc.appendChild(p); }
    for(const [t,b] of runs) if(t) p.appendChild(ihcRun(doc,t,b));
  });
}
function buildIhcDocx(templateBuf,R){
  const zip=new PizZip(templateBuf); const P=new DOMParser();
  const doc=P.parseFromString(zip.file('word/document.xml').asText(),'application/xml'); const body=desc(doc,'body')[0]; const pre=capture(body);
  fillClinical(doc,table(body,'CLINICAL DETAILS'),R.clinical||[]);
  fillLabels(doc,table(body,'SPECIMEN AND BLOCK DETAILS'),R.block||{});
  fillLabels(doc,table(body,'CONTROLS'),R.controls||{});
  const rt=table(body,'IMMUNOHISTOCHEMISTRY RESULTS'); const trs=rows(rt); const proto=trs[2];
  trs.slice(2).forEach(r=>rt.removeChild(r));
  const res=(R.results||[]).filter(r=>r.some(v=>String(v||'').trim()));
  (res.length?res:[['','','']]).forEach(vals=>{ const r=proto.cloneNode(true); cells(r).forEach((tc,i)=>{ if(vals[i]) kids(tc,'p')[0].appendChild(ihcRun(doc,vals[i])); }); rt.appendChild(r); });
  const sc=R.scoring;
  if(sc&&sc.rows&&sc.rows.length){
    let sp=rt.nextSibling; while(sp&&sp.nodeType!==1) sp=sp.nextSibling;
    const st=scoreTable(doc,sc.title||'SCORING',sc.cols,sc.widths,sc.rows);
    body.insertBefore(st,sp.nextSibling); body.insertBefore(sp.cloneNode(true),st.nextSibling);
  }
  fillFree(doc,table(body,'IMPRESSION'),(R.impression||[]).map(i=>i.label?[[i.label.endsWith(' ')?i.label:i.label+' ',true],[i.text||'',false]]:[[i.text||'',false]]));
  fillFree(doc,table(body,'COMMENT'),(R.comment||[]).map(i=>i.label?[[i.label+' ',true],[i.text||'',false]]:[[i.text||'',false]]));
  applyLayout(doc,body,pre,R);
  zip.file('word/document.xml',ser(doc));
  for(const f of Object.keys(zip.files)){ if(/^word\/header\d*\.xml$/.test(f)){ const h=P.parseFromString(zip.file(f).asText(),'application/xml'); fillHeader(h,h.documentElement,R.header||{}); zip.file(f,ser(h)); } }
  zip.file('[Content_Types].xml',zip.file('[Content_Types].xml').asText().replace(DOTX_CT,DOCX_CT));
  return zip.generate({type:'blob',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',compression:'DEFLATE'});
}

// ---------------- Generic engine: any Basic Template, schema detected by tools/schema.py ----------------
function fillGrowCell(doc,tc,v){
  const p=kids(tc,'p')[0]; const existing=text(p);
  if(existing.trim()){ const r=kids(p,'r').find(r=>text(r)); const t=desc(r,'t')[0]; t.textContent=v+t.textContent; t.setAttributeNS(XMLNS,'xml:space','preserve'); }
  else setPlain(doc,p,v,null);
}
function buildGenericDocx(templateBuf,R,schema){
  const zip=new PizZip(templateBuf); const P=new DOMParser();
  const doc=P.parseFromString(zip.file('word/document.xml').asText(),'application/xml'); const body=desc(doc,'body')[0]; const pre=capture(body);
  const vals=R.values||{};
  for(const s of schema.sections){
    const V=vals[s.heading]; if(!V) continue;
    const t=table(body,s.heading); const rs=rows(t);
    for(const pt of s.parts){
      const key=pt.r+'.'+(pt.p||0); const v=V[key]; if(v==null||v==='') continue;
      if(pt.k==='label'){ appendValue(doc,kids(cells(rs[pt.r])[0],'p')[pt.p],v); }
      else if(pt.k==='free'){ fillCellParas(doc,cells(rs[pt.r])[0],v); }
      else if(pt.k==='grow'){ cells(rs[pt.r]).forEach((tc,i)=>{ if(pt.cells[i]&&pt.cells[i].e&&v[i]) fillGrowCell(doc,tc,v[i]); }); }
      else if(pt.k==='dyn'){ const proto=rs[pt.r]; const data=v.filter(r=>r.some(x=>String(x||'').trim()));
        data.forEach((row,i)=>{ const tr=i===0?proto:stripW14(proto.cloneNode(true)); if(i){ const last=rows(t)[rows(t).length-1]; t.insertBefore(tr,last.nextSibling); }
          cells(tr).forEach((tc,j)=>setPlain(doc,kids(tc,'p')[0],row[j]||'',null)); }); }
      else if(pt.k==='gross'){ fillGross(doc,t,v.containers||[],v.sections||''); }
    }
  }
  applyLayout(doc,body,pre,R);
  zip.file('word/document.xml',ser(doc));
  for(const f of Object.keys(zip.files)){ if(/^word\/header\d*\.xml$/.test(f)){ const h=P.parseFromString(zip.file(f).asText(),'application/xml'); fillHeader(h,h.documentElement,R.header||{}); zip.file(f,ser(h)); } }
  zip.file('[Content_Types].xml',zip.file('[Content_Types].xml').asText().replace(DOTX_CT,DOCX_CT));
  return zip.generate({type:typeof window!=='undefined'?'blob':'nodebuffer',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',compression:'DEFLATE'});
}
const API={buildDocx,buildIhcDocx,buildGenericDocx,describe,SECTION_TYPES};
if(typeof window!=='undefined') window.DocxFill=API; if(typeof module!=='undefined') module.exports=API;
})();
