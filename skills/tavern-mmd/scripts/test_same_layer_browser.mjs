import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdtemp, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createServer } from 'node:http';

const enabled = !!process.env.PLAYWRIGHT_MODULE;
test('local browser: iframe, native bridge, engine, saves, sessions and packaged launch', { skip: !enabled, timeout: 90000 }, async () => {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
  const temp = await mkdtemp(path.join(tmpdir(), 'mmd-same-layer-browser-'));
  const script = fileURLToPath(new URL('build_same_layer.py', import.meta.url));
  const built = spawnSync(process.env.PYTHON || 'python', [script, '--out', temp, '--build-id', 'browser-test', '--preview'], { encoding: 'utf8' });
  assert.equal(built.status, 0, built.stderr);
  const preview = await readFile(path.join(temp, 'preview.html'), 'utf8');
  const pkg = JSON.parse(await readFile(path.join(temp, 'same-layer-mmd.json'), 'utf8'));
  let injected = pkg.statusbar;
  for (const rule of pkg.regex_scripts) {
    const end = rule.findRegex.lastIndexOf('/');
    injected = injected.replace(new RegExp(rule.findRegex.slice(1, end), rule.findRegex.slice(end + 1)), rule.replaceString);
  }
  const fixture = `<!doctype html><meta charset="utf-8"><body><h1>原生聊天测试壳</h1>
    <div id="msglistview"><div class="item Ai"><div class="content left">原生历史</div></div></div>
    <div id="chat-input-scope"><textarea class="uni-textarea-textarea"></textarea><button class="chat-send-proxy">发送</button></div>
    <script>window.testScope={accountKey:'test-account',roleId:'test-role',conversationKey:'main'};window.__MMD_SAME_LAYER_SCOPE__=()=>window.testScope;
    window.nativeSends=0;document.querySelector('.chat-send-proxy').onclick=()=>{window.nativeSends++;const box=document.createElement('div');box.className='item self';const text=document.createElement('div');text.className='content right';const input=document.querySelector('textarea');text.textContent=input.value;input.value='';box.append(text);document.querySelector('#msglistview').append(box);};</script>` + injected;
  const server = createServer((req, res) => { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(req.url === '/import' ? fixture : preview); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1280, height: 880 }, acceptDownloads: true });
  const page = await context.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') console.log('Browser console:', m.text()); });
  const base = 'http://127.0.0.1:' + server.address().port;
  async function frame(turn) {
    await page.waitForSelector('iframe');
    const f = await (await page.$('iframe')).contentFrame();
    await f.waitForFunction(v => document.getElementById('turn')?.textContent === String(v), turn);
    return f;
  }
  try {
    await page.goto(base); let f = await frame(0);
    assert.equal(await f.evaluate(() => { try { return parent.document.body ? 'accessible' : 'none'; } catch (e) { return e.name; } }), 'SecurityError');
    await f.locator('#explore').click(); await f.waitForFunction(() => document.getElementById('turn').textContent === '1');
    assert.equal(await f.locator('#energy').innerText(), '4');
    await f.locator('#narrate').click();
    await f.waitForFunction(() => document.getElementById('messages').textContent.includes('本地模拟'));
    assert.equal(await f.locator('#narrate').isDisabled(), true);
    await f.locator('#text').fill('你好，港口！'); await f.locator('#send').click();
    await f.waitForFunction(() => [...document.querySelectorAll('.message.assistant')].length === 3);
    const downloadPromise = page.waitForEvent('download'); await f.locator('#export').click();
    const download = await downloadPromise; const saved = await readFile(await download.path());
    await f.locator('#rest').click(); await f.waitForFunction(() => document.getElementById('turn').textContent === '2');
    await f.locator('#file').setInputFiles({ name: 'save.json', mimeType: 'application/json', buffer: saved });
    await f.locator('#confirm-import').click(); await f.waitForFunction(() => document.getElementById('turn').textContent === '1');
    await page.getByRole('button', { name: '返回 MMD', exact: true }).click();
    assert.equal(await page.locator('iframe').isVisible(), false);
    await page.getByRole('button', { name: '返回游戏', exact: true }).click();
    assert.equal(await page.locator('iframe').count(), 1);
    let previousFrame = await page.$('iframe');
    await page.evaluate(() => window.__MMD_SAME_LAYER__['fog-harbor'].bridge.changeConversation('A'));
    await page.waitForFunction(el => !el.isConnected, previousFrame);
    f = await frame(0); await f.locator('#explore').click(); await f.waitForFunction(() => document.getElementById('turn').textContent === '1');
    await f.locator('#rest').click(); await f.waitForFunction(() => document.getElementById('turn').textContent === '2');
    previousFrame = await page.$('iframe');
    await page.evaluate(() => window.__MMD_SAME_LAYER__['fog-harbor'].bridge.changeConversation('main'));
    await page.waitForFunction(el => !el.isConnected, previousFrame);
    f = await frame(1); await page.reload(); f = await frame(1);
    const evidence = process.env.MMD_SL_EVIDENCE_DIR || temp;
    await mkdir(evidence, { recursive: true });
    await page.screenshot({ path: path.join(evidence, 'same-layer-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await f.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(evidence, 'same-layer-mobile.png'), fullPage: true });
    await page.getByRole('button', { name: '关闭', exact: true }).click();
    assert.equal(await page.locator('iframe').count(), 0);
    assert.equal(await page.getByRole('button', { name: '返回游戏', exact: true }).count(), 0);
    await page.goto(base + '/import'); f = await frame(0);
    await f.locator('#text').fill('通过原生桥接发送'); await f.locator('#send').click();
    await page.waitForFunction(() => window.nativeSends === 1);
    await f.waitForFunction(() => document.getElementById('messages').textContent.includes('通过原生桥接发送'));
    await f.locator('#explore').click(); await f.waitForFunction(() => document.getElementById('turn').textContent === '1');
    await page.reload(); f = await frame(1);
    const currentBoot = await page.evaluate(() => window.__MMD_SAME_LAYER__['fog-harbor'].bootId);
    await page.evaluate(() => window.MmdSameLayerHost.boot({appId:'fog-harbor',buildId:'browser-test',engine:true}, 'unused'));
    assert.equal(await page.locator('iframe').count(), 1);
    assert.equal(await page.evaluate(() => window.__MMD_SAME_LAYER__['fog-harbor'].bootId), currentBoot);
    await page.evaluate(() => { window.testScope = {...window.testScope, roleId:'another-card'}; });
    await page.waitForFunction(() => document.querySelector('iframe') === null);
    await page.waitForTimeout(650); assert.equal(await page.locator('iframe').count(), 0);
    await page.evaluate(() => { window.testScope = {...window.testScope, roleId:'test-role'}; });
    f = await frame(1);
    await page.evaluate(() => window.__MMD_SAME_LAYER__['fog-harbor'].destroy());
    const standaloneFrame = await readFile(path.join(temp, 'frame.html'), 'utf8');
    await page.evaluate(html => window.MmdSameLayerHost.boot({appId:'chat-only',buildId:'test-chat',engine:false,mode:'mock'}, html), standaloneFrame);
    await page.waitForSelector('iframe');
    f = await (await page.$('iframe')).contentFrame();
    await f.locator('#send').waitFor();
    await f.waitForFunction(() => !document.getElementById('send').disabled);
    assert.equal(await f.locator('#game-panel').isVisible(), false);
    await f.locator('#text').fill('纯聊天也能发送'); await f.locator('#send').click();
    await f.waitForFunction(() => document.getElementById('messages').textContent.includes('本地模拟'));
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('Browser evidence: ' + evidence + '; real MMD / physical mobile: NOT RUN');
  } catch (error) {
    console.log('Failure state:', await page.evaluate(() => window.__MMD_SAME_LAYER__?.['fog-harbor']?.getState()));
    for (const child of page.frames().slice(1)) console.log('Frame:', await child.locator('body').innerText().catch(() => 'detached'));
    throw error;
  } finally {
    await context.close(); await browser.close(); await new Promise(resolve => server.close(resolve));
  }
});
