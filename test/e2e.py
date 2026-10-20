import asyncio, sys, os
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8931/'
OUT='/workspace/path-reporter-ws/test/out/'
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--headless=new'])
        ctx=await b.new_context(viewport={'width':1280,'height':800},device_scale_factor=1,accept_downloads=True,
            user_agent='Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36')
        pg=await ctx.new_page(); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m: m.type=='error' and errs.append(m.text))
        pg.on('dialog',lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(URL); await pg.wait_for_selector('.type.on')
        await pg.screenshot(path=OUT+'01_home.png')
        await pg.click('.type.on')
        vals={'name':'Test Patient','uhid':'UH123456','age':'45 Y','gender':'Female','lab no':'HP/26/1234','ref. doctor':'Dr. Surgeon','dept./ward':'General Surgery','sample no':'S-889','received on':'19/10/2026','reported on':'20/10/2026'}
        for k,v in vals.items(): await pg.fill(f'[data-h="{k}"]',v)
        await pg.fill('[data-ct="1"]','Laparoscopic cholecystectomy.'); await pg.fill('[data-ct="2"]','Recurrent right upper quadrant pain; USG: cholelithiasis.')
        opt=await pg.eval_on_selector('#spec',"s=>[...s.options].find(o=>o.text==='Gallbladder Non-cancer').value")
        await pg.select_option('#spec',opt)
        await pg.screenshot(path=OUT+'02_specimen_gross.png',full_page=True)
        ins=await pg.query_selector_all('[data-bl="0"] input')
        for v in ['8','3.5','2','0.4','1.2']:
            i=await pg.query_selector('[data-bl="0"] input')
            if not i: break
            await i.fill(v); await i.dispatch_event('change')
        await pg.select_option('[data-gs="0"]','Partially embedded.')
        await pg.fill('#sections','A1 – neck; A2 – body; A3 – fundus.')
        await pg.fill('#dxq','chronic calculous')
        await pg.click('.dx >> nth=0')
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=OUT+'03_diagnosis_filled.png',full_page=True)
        await pg.click('#save'); await pg.screenshot(path=OUT+'04_save_dialog.png'); await pg.click('[data-m="patient"]'); await pg.wait_for_timeout(300)
        async with pg.expect_download() as d: await pg.click('#docx')
        dl=await d.value; await dl.save_as(OUT+'sample_gallbladder_chronic.docx')
        await pg.click('#prev'); await pg.wait_for_selector('#pv section.docx'); await pg.wait_for_timeout(800)
        el=await pg.query_selector('#pv'); await el.screenshot(path=OUT+'05_preview.png')
        # CAP case
        await pg.click('#dxall'); await pg.fill('#dxq','Gallbladder, Biliary')
        await pg.click('.dx >> nth=0'); await pg.wait_for_timeout(300)
        await pg.screenshot(path=OUT+'06_cap_diagnosis.png',full_page=True)
        async with pg.expect_download() as d: await pg.click('#docx')
        dl=await d.value; await dl.save_as(OUT+'sample_gallbladder_cap.docx')
        # new template save
        await pg.evaluate("window.prompt=()=> 'My GB adenoca template'")
        await pg.click('#save'); await pg.click('[data-m="new"]'); await pg.wait_for_timeout(300)
        await pg.click('#navData'); await pg.wait_for_timeout(300); await pg.screenshot(path=OUT+'07_templates_backup.png',full_page=True)
        async with pg.expect_download() as d: await pg.click('#exp')
        await (await d.value).save_as(OUT+'backup_test.json')
        await pg.click('#upd'); await pg.wait_for_timeout(1500)
        await pg.click('#navReports'); await pg.wait_for_timeout(300); await pg.screenshot(path=OUT+'08_saved_reports.png')
        # print emulation
        await pg.click('#navReports'); await pg.click('[data-o]'); await pg.wait_for_selector('#print')
        await pg.evaluate("window.print=()=>{window.__printed=true}")
        await pg.click('#print'); await pg.wait_for_timeout(1500)
        await pg.emulate_media(media='print'); await pg.pdf(path=OUT+'print_view.pdf',format='A4',print_background=True)
        print('printed?',await pg.evaluate('window.__printed'))
        print('ERRORS',errs)
        await b.close()
asyncio.run(main())
