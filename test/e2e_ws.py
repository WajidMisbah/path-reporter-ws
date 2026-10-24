# Wajid's own sample reports (WS Case Based Templates) -> case pickers. Builds a throw-away copy of docs/ with a test mirror
# (default /tmp/wstest, see README) so nothing test-only reaches the shipped bundle. Usage: python3 test/e2e_ws.py [ws_test_dir]
import asyncio, sys, os, json, subprocess, tempfile, shutil, zipfile, re, socket
from playwright.async_api import async_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); WSD=sys.argv[1] if len(sys.argv)>1 else '/tmp/wstest'
fails=[]
def ok(c,m): print('PASS' if c else 'FAIL',m); c or fails.append(m)
def doc(f): return zipfile.ZipFile(f).read('word/document.xml').decode()
tmp=tempfile.mkdtemp(); site=tmp+'/docs'; shutil.copytree(ROOT+'/docs',site)
r=subprocess.run(['python3',ROOT+'/tools/gen_bundle.py'],env={**os.environ,'PRWS_WS_DIR':WSD,'PRWS_OUTDIR':site+'/templates'},capture_output=True,text=True)
ok(r.returncode==0,'gen_bundle with test mirror '+r.stderr[-300:]); print('\n'.join(l for l in r.stdout.splitlines() if 'ws' in l.lower()))
b=json.load(open(site+'/templates/bundle.json'))
ws=[x for x in b['diagnoses']+b['ihcPanels']+[c for t in b['reportTypes'] for c in t.get('cases',[])] if x.get('ws')]
ok(len(ws)>=4,'%d WS cases in test bundle'%len(ws))
blob=json.dumps(ws)
ok(not re.search(r'"(Name|UHID|Age|Gender|Lab No|Sample No|Ref\. Doctor|Dept\./Ward|Received on|Reported on):?"',blob) and 'CLINICAL DETAILS' not in blob,'no header / clinical fields in WS cases')
s=socket.socket(); s.bind(('',0)); port=s.getsockname()[1]; s.close()
srv=subprocess.Popen(['python3','-m','http.server',str(port),'-d',site],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
async def main():
  async with async_playwright() as p:
    br=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new']); ctx=await br.new_context(accept_downloads=True,viewport={'width':1280,'height':1000}); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d:asyncio.ensure_future(d.accept()))
    await pg.goto(f'http://localhost:{port}/'); await pg.wait_for_selector('.type.on'); await pg.wait_for_timeout(500)
    async def export(name):
      async with pg.expect_download() as d: await pg.click('#docx')
      f=tmp+'/'+name+'.docx'; await (await d.value).save_as(f); return doc(f)
    # generic (FNAC, sub-folder)
    await pg.click('.type[data-k="fnac"]'); await pg.wait_for_selector('#dxl')
    first=await pg.eval_on_selector('#dxl .dx','e=>e.textContent'); ok('ZZ Test Lipoma' in first and 'My reports' in first,'FNAC: WS case listed first with My reports tag: '+first[:80])
    await pg.click('#dxl .dx >> nth=0'); await pg.wait_for_timeout(300); x=await export('fnac')
    ok('mature adipocytes' in x and re.search(r'<w:b/>.{0,200}Swelling; FNAC:',x,re.S) is not None,'FNAC export: text + bold label kept')
    # histo: visible without "all organs"
    await pg.click('#navHome'); await pg.click('.type[data-k="histo"]'); await pg.wait_for_selector('#dxl')
    names=await pg.eval_on_selector_all('#dxl .dx','e=>e.map(x=>x.textContent)'); ok(any('ZZ Test Appendicitis' in n and 'My reports' in n for n in names),'Histo: WS case listed')
    await pg.fill('#dxq','ZZ Test Appendicitis'); await pg.wait_for_timeout(200); await pg.click('#dxl .dx >> nth=0'); await pg.wait_for_timeout(300); x=await export('histo')
    ok('Acute suppurative (phlegmonous) appendicitis' in x and 'dense transmural infiltrate' in x,'Histo export: FD + micro')
    # CAP
    await pg.click('#navHome'); await pg.click('.type[data-k="cap"]'); await pg.wait_for_selector('#dxl')
    await pg.fill('#dxq','ZZ Test'); await pg.wait_for_timeout(200)
    names=await pg.eval_on_selector_all('#dxl .dx','e=>e.map(x=>x.textContent)'); ok(any('ZZ Test Ovary CAP' in n for n in names),'CAP: WS case listed '+str(names))
    await pg.click('#dxl .dx >> nth=0'); await pg.wait_for_timeout(300); x=await export('cap'); ok('Left Ovary Integrity' in x and 'Capsule intact' in x,'CAP export: synoptic filled')
    # IHC
    await pg.click('#navHome'); await pg.click('.type[data-k="ihc"]'); await pg.wait_for_selector('#dxl'); await pg.fill('#dxq','ZZ Test'); await pg.wait_for_timeout(200)
    t=await pg.eval_on_selector('#dxl .dx','e=>e.textContent'); ok('ZZ Test MMR' in t and 'My reports' in t,'IHC: WS case listed '+t[:60])
    await pg.click('#dxl .dx >> nth=0'); await pg.wait_for_timeout(300); x=await export('ihc'); ok('MLH1 (M1)' in x and 'MISMATCH REPAIR STATUS' in x,'IHC export: results + scoring')
    st=await pg.evaluate("async()=>{const db=await new Promise(r=>{const q=indexedDB.open('path-reporter-ws');q.onsuccess=()=>r(q.result)}); return [...db.objectStoreNames]}")
    ok(all(s in st for s in ['reports','diagnoses','doctors','rtypes','gross']),'IndexedDB stores intact '+str(st))
    await pg.screenshot(path='/workspace/prws_ws_cases.png',full_page=False)
    ok(not errs,'no page errors '+str(errs)); await br.close()
try: asyncio.run(main())
finally: srv.terminate(); shutil.rmtree(tmp,ignore_errors=True)
print('ALL PASS' if not fails else 'FAILURES: %s'%fails); sys.exit(1 if fails else 0)
