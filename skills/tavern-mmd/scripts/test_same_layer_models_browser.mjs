import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdtemp, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createServer } from 'node:http';

test('model module browser integration', { skip: !process.env.PLAYWRIGHT_MODULE, timeout: 120000 }, async t => {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
  const directory = await mkdtemp(path.join(tmpdir(), 'mmd-models-'));
  const builder = fileURLToPath(new URL('build_same_layer.py', import.meta.url));
  function build(out, extra = []) {
    const result = spawnSync(process.env.PYTHON || 'python', [builder, '--out', out, '--build-id', 'models-test', '--no-engine', '--preview', ...extra], {encoding:'utf8'});
    assert.equal(result.status, 0, result.stderr);
  }
  build(directory); build(path.join(directory, 'disabled'), ['--no-models']);
  const fixture = await readFile(new URL('test-fixtures/same-layer-models.html', import.meta.url), 'utf8');
  function expand(pkg) { let html = pkg.statusbar; for (const row of pkg.regex_scripts) {
    const end = row.findRegex.lastIndexOf('/'); html = html.replace(new RegExp(row.findRegex.slice(1,end),row.findRegex.slice(end+1)),row.replaceString);
  } return html; }
  const source = fixture.replace('<!--RUNTIME-->', expand(JSON.parse(await readFile(path.join(directory,'same-layer-mmd.json'),'utf8'))));
  const mock = await readFile(path.join(directory,'preview.html'),'utf8');
  const disabled = await readFile(path.join(directory,'disabled','preview.html'),'utf8');
  const server = createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(req.url==='/mock'?mock:req.url==='/disabled'?disabled:source);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless:true, channel:process.env.BROWSER_CHANNEL || 'msedge' });
    const base = 'http://127.0.0.1:' + server.address().port;
    const evidence = process.env.MMD_SL_EVIDENCE_DIR || directory;
    await mkdir(evidence,{recursive:true});
    async function visit(route, fn) {
      const context = await browser.newContext({ viewport:{width:1280,height:900} }); const page = await context.newPage(); const errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      try {
        await page.goto(base+route);await page.waitForSelector('iframe');
        const f=await (await page.$('iframe')).contentFrame();
        await f.waitForFunction(()=>document.getElementById('mode')?.textContent==='MMD'||document.getElementById('mode')?.textContent==='本地演示');
        await fn(page,f);
        assert.deepEqual(errors,[]);
      } catch(error) {
        console.log('Model failure:',await page.evaluate(()=>window.fixture&&({selected:fixture.selected,selects:fixture.selects,opens:fixture.openCount,changes:fixture.changes})));
        for(const frame of page.frames().slice(1)) console.log(await frame.locator('body').innerText().catch(()=> 'detached'));
        throw error;
      } finally {await context.close();}
    }
    const open = async f => {await f.locator('#models-open').click();await f.locator('[data-model-select]').first().waitFor();};
    const model = (f,name)=>f.locator('.sl-model-card').filter({has:f.getByRole('heading',{name,exact:true})});

    await t.test('packaged native model UI: delayed lists, filter, select, choices, toggle, preset and submit', async()=>visit('/',async(page,f)=>{
      await open(f);
      assert.equal(await f.locator('[data-model-select]').count(),2);
      await f.getByRole('button',{name:'推理',exact:true}).click();
      await f.waitForFunction(()=>document.querySelectorAll('[data-model-select]').length===1);
      await model(f,'星海·乙').locator('[data-model-select]').click();
      await f.waitForFunction(()=>!document.getElementById('models-dialog').open);
      assert.equal(await page.evaluate(()=>fixture.selected),'b');
      assert.match(await f.locator('#models-open').innerText(),/星海·乙/);
      await open(f);await model(f,'星海·乙').locator('[data-model-settings]').click();
      await f.locator('#models-save-settings').waitFor();
      await f.getByRole('button',{name:'简短',exact:true}).click();
      await f.waitForFunction(()=>document.querySelector('[data-model-choice][aria-pressed=true]')?.textContent==='简短');
      await f.getByRole('checkbox',{name:'记忆辅助'}).check();
      await page.waitForFunction(()=>fixture.values.b.memory===true);
      await f.getByRole('button',{name:'均衡',exact:true}).click();
      await page.waitForFunction(()=>fixture.values.b.preset==='balanced');
      await page.screenshot({path:path.join(evidence,'models-settings-desktop.png')});
      await f.locator('#models-save-settings').click();await f.locator('[data-model-select]').first().waitFor();
      assert.equal(await page.evaluate(()=>fixture.saves),1);
      await page.setViewportSize({width:390,height:844});
      assert.equal(await f.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      assert.equal(await f.locator('#models-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth),true);
      await page.screenshot({path:path.join(evidence,'models-list-mobile.png')});
      await f.locator('#models-close').click();await f.waitForFunction(()=>!document.getElementById('models-dialog').open);
      assert.equal(await page.locator('#model-popup').isVisible(),false);
    }));

    await t.test('rereads selected row when native entry has no model label',async()=>visit('/',async(page,f)=>{
      await page.evaluate(()=>{fixture.fault='no-entry-label';document.querySelector('.current-label').textContent='';});
      await open(f);await model(f,'星海·乙').locator('[data-model-select]').click();
      await f.waitForFunction(()=>!document.getElementById('models-dialog').open);
      assert.equal(await page.evaluate(()=>fixture.selects.length),1);
      assert.equal(await page.evaluate(()=>fixture.openCount),2);
      assert.match(await f.locator('#models-open').innerText(),/星海·乙/);
    }));

    await t.test('a closed panel without a changed selection is not reported as success',async()=>visit('/',async(page,f)=>{
      await page.evaluate(()=>fixture.fault='close-without-select');await open(f);
      await model(f,'星海·乙').locator('[data-model-select]').click();
      await f.waitForFunction(()=>document.getElementById('models-notice').textContent.includes('尚未确认'));
      assert.equal(await page.evaluate(()=>fixture.selected),'a');assert.equal(await page.evaluate(()=>fixture.selects.length),1);
      assert.equal(await f.locator('#models-dialog').evaluate(el=>el.open),true);
    }));

    await t.test('stale list and configuration targets are rejected before any native mutation',async()=>visit('/',async(page,f)=>{
      await open(f);
      const answer = await page.evaluate(async()=>{
        const api=window.__MMD_SAME_LAYER__['fog-harbor'];const before=api.bridge.snapshot().models.modelPanel;
        fixture.render();
        try {await api.bridge.invoke('selectModel',{revision:before.revision,modelId:before.models[1].id});return 'unexpected';}
        catch(error){return error.code;}
      });
      assert.equal(answer,'STALE_TARGET');assert.equal(await page.evaluate(()=>fixture.selects.length),0);
      // Re-read native nodes before selecting settings.
      await f.locator('#models-refresh').click();await model(f,'星海·甲').locator('[data-model-settings]').click();
      await f.locator('#models-save-settings').waitFor();
      const stale=await page.evaluate(async()=>{
        const api=window.__MMD_SAME_LAYER__['fog-harbor'];const cfg=api.bridge.snapshot().models.modelConfiguration;
        const toggle=cfg.controls.find(row=>row.type==='toggle');document.querySelector('.u-switch').click();
        const count=fixture.changes;
        try{await api.bridge.invoke('setModelSetting',{revision:cfg.revision,controlId:toggle.id,value:!toggle.value});return {code:'unexpected'};}
        catch(error){return {code:error.code,unchanged:fixture.changes===count};}
      });assert.deepEqual(stale,{code:'STALE_TARGET',unchanged:true});
    }));

    await t.test('timeouts and cancellation release pending operations without automatic retries',async()=>visit('/',async(page)=>{
      const answer=await page.evaluate(async()=>{
        const direct=window.MmdSameLayerModels.dom(document,{modelTimeoutMs:200});fixture.fault='no-open';
        let timeout;try{await direct.invoke('openModelSettings');}catch(error){timeout=error.code;}
        const afterTimeout=fixture.openCount;fixture.fault='none';fixture.delay=500;
        const waiting=direct.invoke('openModelSettings').then(()=> 'unexpected',e=>e.code);
        setTimeout(()=>direct.cancel(),40);const cancelled=await waiting;
        const busy=direct.snapshot().busy;direct.destroy();
        return {timeout,cancelled,busy,afterTimeout,openCount:fixture.openCount};
      });assert.deepEqual(answer,{timeout:'TIMEOUT',cancelled:'CANCELLED',busy:false,afterTimeout:1,openCount:2});
    }));

    await t.test('ambiguous model rows cannot be selected',async()=>visit('/',async(page,f)=>{
      await open(f);await page.evaluate(()=>{const row=document.querySelector('.model-item');row.after(row.cloneNode(true));});
      await f.waitForFunction(()=>document.querySelectorAll('[data-model-select]:disabled').length>=2);
      const rows=await page.evaluate(()=>window.__MMD_SAME_LAYER__['fog-harbor'].bridge.snapshot().models.modelPanel.models);
      assert.equal(rows.filter(row=>row.name==='星海·甲').every(row=>!row.available&&!row.canConfigure),true);
      assert.equal(await page.evaluate(()=>fixture.selects.length),0);
    }));

    await t.test('closing from settings also closes the underlying list',async()=>visit('/',async(page,f)=>{
      await open(f);await model(f,'星海·甲').locator('[data-model-settings]').click();await f.locator('#models-save-settings').waitFor();
      await f.locator('#models-close-settings').click();await f.locator('[data-model-select]').first().waitFor();
      assert.equal(await page.locator('.model-setting-scope').isVisible(),false);
      await model(f,'星海·甲').locator('[data-model-settings]').click();await f.locator('#models-save-settings').waitFor();
      await f.locator('#models-close').click();await f.waitForFunction(()=>!document.getElementById('models-dialog').open);
      assert.equal(await page.locator('.model-setting-scope').isVisible(),false);assert.equal(await page.locator('#model-popup').isVisible(),false);
    }));

    await t.test('leaving the bound role invalidates an in-flight model action',async()=>visit('/',async(page,f)=>{
      await page.evaluate(()=>fixture.fault='no-open');await f.locator('#models-open').click();
      await page.evaluate(()=>fixture.scope={...fixture.scope,roleId:'another-role'});
      await page.waitForFunction(()=>document.querySelector('iframe')===null);
      await page.waitForFunction(()=>window.__MMD_SAME_LAYER__['fog-harbor'].getState().pending===0);
      assert.equal(await page.evaluate(()=>fixture.openCount),1);
      assert.equal(await page.evaluate(()=>window.__MMD_SAME_LAYER__['fog-harbor'].bridge.snapshot().models.busy),false);
    }));

    await t.test('Mock model UI and build-time module disable remain separate',async()=>{
      await visit('/mock',async(page,f)=>{await open(f);await model(f,'模拟·推理').locator('[data-model-select]').click();await f.waitForFunction(()=>!document.getElementById('models-dialog').open);assert.match(await f.locator('#models-open').innerText(),/模拟·推理/);});
      await visit('/disabled',async(page,f)=>{assert.equal(await f.locator('#models-open').isVisible(),false);assert.equal(await f.locator('#game-panel').isVisible(),false);});
    });
    console.log('Model browser evidence: '+evidence+'; real MMD / physical mobile: NOT RUN');
  } finally {await browser?.close();await new Promise(resolve=>server.close(resolve));}
});
