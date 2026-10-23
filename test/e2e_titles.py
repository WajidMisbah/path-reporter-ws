# Title lines (all report types) + Save as new report type lifecycle.
import asyncio, sys, zipfile, re, json
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'; OUT='/workspace/path-reporter-ws/test/out/titles/'
FAIL=[]
def ok(c,m):
  print(('PASS ' if c else 'FAIL ')+m)
  if not c: FAIL.append(m)
def titles(path):
  x=zipfile.ZipFile(path).read('word/document.xml').decode(); body=x.split('<w:body>')[1]; pre=body[:body.find('<w:tbl>')]
  ps=re.findall(r'<w:p\b[^>]*?(?:/>|>.*?</w:p>)',pre,re.S); return ps,x
import html
def tx(p): return html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)',p)))
def check_titles(path,dept,typ,label):
  ps,x=titles(path)
  ok(len(ps)==3,f'{label}: 3 paragraphs before first section ({len(ps)})')
  for i,(p,want) in enumerate(zip(ps[:2],[dept,typ])):
    ok(tx(p)==want,f'{label}: line {i+1} text {tx(p)!r}=={want!r}')
    r=re.findall(r'<w:r>.*?</w:r>',p,re.S); rp=r[0] if r else ''
    ok(len(r)==1 and '<w:b/>' in rp and '<w:sz w:val="32"/>' in rp and '<w:szCs w:val="32"/>' in rp and '<w:u w:val="single"/>' in rp and '<w:jc w:val="center"/>' in p,f'{label}: line {i+1} sz32 b u centred')
  if len(ps)>2: ok(not tx(ps[2]) and '<w:sz w:val="24"/>' in ps[2],f'{label}: line 3 empty sz24')
  sect=re.findall(r'<w:sectPr.*?</w:sectPr>',x)[-1]; ok('w:left="1134"' in sect and 'headerReference' in sect and 'footerReference' in sect,f'{label}: sectPr/header/footer kept')
async def dl(pg,f):
  async with pg.expect_download() as d: await pg.click('#docx')
  dd=await d.value; await dd.save_as(f); return dd.suggested_filename
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
    ctx=await b.new_context(viewport={'width':1100,'height':900},accept_downloads=True); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    answers=[]
    pg.on('dialog',lambda d: asyncio.ensure_future(d.accept(answers.pop(0) if answers and d.type=='prompt' else (d.default_value or 'x'))))
    await pg.goto(URL); await pg.wait_for_selector('.type.on')
    # 1) default titles of every built-in report type
    ks=await pg.eval_on_selector_all('.type.on','e=>e.map(x=>[x.dataset.k,x.querySelector(".tname").textContent])')
    for k,n in ks:
      await pg.click('#navHome'); await pg.click(f'.type[data-k="{k}"]'); await pg.wait_for_selector('#tDept')
      dept=await pg.text_content('#tpDept'); typ=await pg.text_content('#tpType')
      f=OUT+k+'.docx'; await dl(pg,f); check_titles(f,dept,typ,k); ok(dept=='DEPARTMENT OF PATHOLOGY','%s default dept %r'%(k,dept)); print('   ',k,'line2:',typ)
    # CAP layout
    await pg.click('#navHome'); await pg.click('.type[data-k="histo"]'); await pg.check('#dxall'); await pg.wait_for_timeout(200)
    await pg.click('.dx:has(.tag.purple) >> nth=0'); await pg.wait_for_timeout(300); f=OUT+'cap.docx'; await dl(pg,f); check_titles(f,'DEPARTMENT OF PATHOLOGY','Histopathology Report','cap')
    # 2) edited titles normalised
    await pg.click('#navHome'); await pg.click('.type[data-k="pap"]'); await pg.wait_for_selector('#tDept')
    await pg.fill('#tDept','department of pathology & laboratory medicine'); await pg.fill('#tType','pap smear report (conventional)'); await pg.press('#tType','Tab')
    ok(await pg.text_content('#tpType')=='Pap Smear Report (Conventional)','editor preview title case')
    f=OUT+'pap_edit.docx'; await dl(pg,f); check_titles(f,'DEPARTMENT OF PATHOLOGY & LABORATORY MEDICINE','Pap Smear Report (Conventional)','pap edited')
    await pg.click('#prev'); await pg.wait_for_timeout(1500)
    box=await pg.query_selector('#titlesBox'); await box.screenshot(path=OUT+'titles_card.png')
    await pg.evaluate("document.querySelectorAll('header,.topbar').forEach(h=>h.style.position='static')"); el=await pg.query_selector('#pv .docx-wrapper section'); await el.screenshot(path='/workspace/prws_titles.png')
    # 3) Save as new report type (from histo with patient data)
    await pg.click('#navHome'); await pg.click('.type[data-k="histo"]'); await pg.fill('[data-h="name"]','Secret Patient'); await pg.fill('[data-h="sample no"]','HP-55/26'); await pg.fill('[data-h="uhid"]','UH998877')
    await pg.fill('[data-ct="2"]','Known case secret history'); await pg.fill('#dxq','chronic calculous'); await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
    await pg.fill('#tType','frozen section report')
    await pg.click('[data-las="2"]'); await pg.fill('#nsh','intra-operative consultation'); await pg.click('[data-st="two-asym"]'); await pg.click('#nsok'); await pg.fill('[data-lc="3.0.0"]','**Frozen section:**')
    await pg.click('#save'); answers[:]=[ '' ]; answers.clear()
    await pg.click('[data-m="rtype"]'); await pg.wait_for_timeout(600)
    ut=await pg.evaluate("async()=>await DB.all('rtypes')")
    ok(len(ut)==1 and ut[0]['name']=='Frozen Section Report','report type created with default name: '+str([u['name'] for u in ut]))
    sj=json.dumps(ut); ok(not any(s in sj for s in ['Secret Patient','HP-55','UH998877','secret history']),'patient data stripped from report type')
    st=ut[0]['structure']; ok(ut[0]['base']=='histo' and st['secLayout'] and st['micro'] and st['finalDiagnosis'] and [c['label'] for c in st['clinical']][:3]==['Specimen:','Procedure:','Clinical history:'] and st['titles']['type'].lower()=='frozen section report','structure + template text kept')
    # Home card
    await pg.click('#navHome'); await pg.wait_for_selector('.type.mine'); await pg.screenshot(path='/workspace/prws_newtype_home.png',full_page=True)
    col=await pg.eval_on_selector('.type.mine .tname','e=>getComputedStyle(e).color'); ok(col!='rgb(255, 255, 255)','card text readable '+col)
    # new report from it
    await pg.click('.type.mine'); await pg.wait_for_selector('#tDept')
    ok(await pg.text_content('h2')=='Frozen Section Report report','editor heading')
    ok(await pg.input_value('[data-h="name"]')=='' and await pg.input_value('[data-ct="2"]')=='','new report has blank patient fields')
    heads=await pg.eval_on_selector_all('.lhead','e=>e.map(x=>x.value)'); ok('INTRA-OPERATIVE CONSULTATION' in heads,'sections carried: '+str(heads))
    ok(await pg.text_content('#dxl p')!=None,'own (empty) template list')
    await pg.fill('[data-h="name"]','Ravi'); fn=await dl(pg,OUT+'ut.docx'); ok(fn=='Ravi Frozen Section Report.docx','file name '+fn)
    check_titles(OUT+'ut.docx','DEPARTMENT OF PATHOLOGY','Frozen Section Report','user type')
    answers.append('FS breast template'); await pg.click('#save'); await pg.click('[data-m="new"]'); await pg.wait_for_timeout(500)
    dx=await pg.evaluate("async()=>(await DB.all('diagnoses')).filter(d=>d.utype).map(d=>[d.name,d.utype,d.titles&&d.titles.type])"); ok(len(dx)==1 and dx[0][1]==ut[0]['id'],'template saved under new type '+str(dx))
    await pg.click('#navHome'); await pg.click('.type.mine'); await pg.wait_for_selector('#dxl .dx'); ok('FS breast template' in await pg.text_content('#dxl'),'template listed under new type')
    await pg.click('#navHome'); await pg.click('.type[data-k="histo"]'); await pg.fill('#dxq','FS breast'); await pg.check('#dxall'); await pg.wait_for_timeout(200); ok('FS breast' not in await pg.text_content('#dxl'),'not listed under Histopathology')
    # reload + update templates
    await pg.reload(); await pg.wait_for_selector('.type.mine'); ok(True,'card persists after reload')
    await pg.click('#navData'); await pg.click('#upd'); await pg.wait_for_timeout(2500); await pg.click('#navHome'); ok(await pg.query_selector('.type.mine') is not None,'card persists after Update templates')
    exp=await pg.evaluate("async()=>{const o=await DB.exportAll(); return (o.rtypes||[]).length}"); ok(exp==1,'backup includes report types')
    # rename + delete (reports kept)
    nrep=await pg.evaluate("async()=>(await DB.all('reports')).length")
    await pg.click('#navData'); answers.append('Frozen Section'); await pg.click('[data-ur]'); await pg.wait_for_timeout(400)
    ok((await pg.evaluate("async()=>(await DB.all('rtypes'))[0].name"))=='Frozen Section','rename')
    await pg.click('[data-ux]'); await pg.wait_for_timeout(500)
    ok((await pg.evaluate("async()=>(await DB.all('rtypes')).length"))==0 and (await pg.evaluate("async()=>(await DB.all('reports')).length"))==nrep,'delete keeps reports')
    ok(not errs,'no page errors '+str(errs)); await b.close()
  print('RESULT', 'ALL PASS' if not FAIL else 'FAILURES: '+str(FAIL)); sys.exit(1 if FAIL else 0)
asyncio.run(main())
