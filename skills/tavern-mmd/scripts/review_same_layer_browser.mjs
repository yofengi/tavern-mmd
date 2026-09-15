import { reviewNative } from './review_same_layer_native.mjs';
/* Project-output smoke review. It serves only the generated local preview files. */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';

const [directoryArg, outputArg] = process.argv.slice(2);
if (!directoryArg || !outputArg) throw Error('Provide preview directory and evidence output directory');
const directory = path.resolve(directoryArg), output = path.resolve(outputArg);
await mkdir(output, { recursive: true });
const report = { status: 'FAIL', checks: [], pageErrors: [], blockedExternalRequests: [], realMmd: 'NOT RUN', physicalMobile: 'NOT RUN' };
let browser, server, page;
function assert(value, message) { if (!value) throw Error(message); }
try {
  const manifest = JSON.parse(await readFile(path.join(directory, 'preview-manifest.json'), 'utf8'));
  const files = new Map();
  for (const name of Object.keys(manifest.files)) {
    const target = path.resolve(directory, name);
    assert(target.startsWith(directory + path.sep), 'Unsafe preview resource path');
    const raw = await readFile(target);
    assert(createHash('sha256').update(raw).digest('hex') === manifest.files[name], 'Preview resource hash mismatch: ' + name);
    files.set('/' + name.replaceAll('\\', '/'), raw);
  }
  server = createServer((req, res) => {
    const url = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const name = url === '/' ? '/preview.html' : url, data = files.get(name);
    if (!data) { res.writeHead(404); res.end('Local preview resource not found'); return; }
    res.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript; charset=utf-8' : name.endsWith('.css') ? 'text/css; charset=utf-8' : name.endsWith('.png') ? 'image/png' : name.endsWith('.svg') ? 'image/svg+xml' : 'text/html; charset=utf-8'); res.end(data);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
  browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_CHANNEL || process.platform === 'win32' ? { channel: process.env.BROWSER_CHANNEL || 'msedge' } : {}) });
  const context = await browser.newContext({ viewport: { width: 1360, height: 950 }, permissions: ['clipboard-read', 'clipboard-write'] });
  await context.route('**/*', route => {
    const url = route.request().url();
    if (url.startsWith(base + '/') || url.startsWith('data:') || url.startsWith('blob:')) return route.continue();
    report.blockedExternalRequests.push(url); return route.abort();
  });
  page = await context.newPage(); page.on('pageerror', e => report.pageErrors.push(e.message));
  page.setDefaultTimeout(12000);
  await page.goto(base); const native = await (await page.$('.preview-stage')).contentFrame();
  async function card() {
    await native.waitForFunction(app => window.__MMD_SAME_LAYER__?.[app]?.getState().ready, manifest.appId, { timeout: 12000 });
    const f = await (await native.$('iframe')).contentFrame();
    await f.waitForFunction(() => document.getElementById('connection')?.textContent === '已连接', null, { timeout: 12000 }); return f;
  }
  const state = () => native.evaluate(() => __MMD_PREVIEW__.snapshot());
  const toNative = () => page.locator('#native-view').click();
  const toCard = () => page.locator('#card-view').click();
  const action = (f, name) => f.locator('[data-sl-action="' + name + '"]');
  async function open(f, kind) { if (await f.locator('#feature-nav').isHidden()) await f.locator('#menu-open').click(); await f.locator('#feature-open-' + kind).click(); await f.locator('#features-dialog').waitFor(); }
  async function check(name, fn) { await fn(); report.checks.push({ name, status: 'PASS' }); }
  let f = await card();
  const allowed = manifest.allowedActions;
  const enabled = (...names) => !allowed || names.every(name => allowed.includes(name));
  await check('原样载荷连接、Frame 隔离与旧页结构', async () => {
    const body = await native.locator('.chat').count(); assert(body === 1, 'MMD shell missing');
    assert(await native.locator('.chat-bottom .chat-input-scope textarea').count() === 2, 'Expected old-MMD mirrored inputs');
    assert(await native.locator('.chat-send-proxy').isHidden(), 'Native send proxy must retain its observed hidden state');
    assert(await f.evaluate(() => { try { return parent.document.body ? false : false; } catch (e) { return e.name === 'SecurityError'; } }), 'Card Frame isolation was lost');
    assert(await f.evaluate(() => document.getElementById('mode').textContent === 'MMD'), 'Release was replaced with a Mock Frame');
    await page.screenshot({ path: path.join(output, 'same-layer-desktop.png') });
  });
  if(enabled('openEditMessage','setEditText','submitEditMessage','cancelEditMessage')) await check('同层编辑 → 原生 Vditor 草稿、保存与取消', async () => {
    await action(f,'openEditMessage').last().click();await f.locator('#feature-field-text').fill('同层消息编辑联动检查');
    await action(f,'setEditText').click();
    await native.waitForFunction(()=>document.querySelector('#vditor .vditor-ir > pre')?.innerText.includes('同层消息编辑联动检查'));
    await action(f,'submitEditMessage').click();await f.locator('#features-dialog').waitFor({state:'hidden'});
    assert((await native.locator('#msglistview .content').last().innerText()).includes('同层消息编辑联动检查'),'Bridge edit did not reach native message');
    await action(f,'openEditMessage').last().click();await f.locator('#features-close').click();
    await native.locator('.msg-modify-scope').waitFor({state:'detached'});
  });
  else report.checks.push({name:'同层消息编辑',status:'NOT APPLICABLE',reason:'作品未允许完整编辑流程；原生编辑检查仍执行'});
  await check('原生双输入框同步与原生发送 → 同层消息', async () => {
    await toNative(); await native.locator('.chat-input-collapsed-display').click();
    const text = '原生页面联动检查 ' + Date.now(); await native.locator('.chat-input-scope textarea:visible').fill(text);
    assert((await native.locator('.chat-input-scope textarea').evaluateAll(rows => rows.map(x => x.value))).every(v => v === text), 'Mirrored inputs diverged');
    await native.locator('.pano-send-expanded').click();
    await native.waitForFunction(value => document.getElementById('msglistview').textContent.includes(value), text);
    await page.screenshot({ path: path.join(output, 'mmd-desktop.png') });
    await toCard(); f = await card(); await f.waitForFunction(value => document.getElementById('messages').textContent.includes(value), text);
  });
  if (enabled('sendMessage')) await check('同层发送 → 原生消息与用户角色', async () => {
    const text = '同层页面联动检查 ' + Date.now(); await f.locator('#text').fill(text); await f.locator('#send').click();
    await native.waitForFunction(value => __MMD_PREVIEW__.snapshot().conversations.find(c => c.id === __MMD_PREVIEW__.snapshot().current).messages.some(m => m.role === 'user' && m.text === value), text);
    await f.waitForFunction(value => [...document.querySelectorAll('.message.user')].some(x => x.textContent.includes(value)), text);
  });
  else report.checks.push({ name: '同层发送', status: 'NOT APPLICABLE', reason: '作品未允许 sendMessage' });
  const modules = await f.evaluate(() => ({ ...MmdSameLayerUIConfig.modules }));
  const nativeCaps = await native.evaluate(app => __MMD_SAME_LAYER__[app].bridge.snapshot(), manifest.appId);
  if (modules.models !== false && nativeCaps.models?.enabled) await check('原生切换模型 → 同层模型显示', async () => {
    await toNative(); await native.locator('.mind-type:visible').click(); await native.locator('.model-item .model-title').last().click();
    const selected = (await state()).models.at(-1).name; await toCard(); f = await card();
    await f.waitForFunction(value => document.getElementById('models-open').textContent.includes(value), selected);
  });
  else report.checks.push({ name: '模型模块', status: 'NOT APPLICABLE', reason: '作品未启用模型模块' });
  if (modules.models !== false && nativeCaps.models?.enabled && enabled('openModelPanel','selectModel','openModelConfiguration','setModelConfigurationValue','submitModelConfiguration','closeModelPanel')) await check('同层模型选择与设置 → 原生保存状态', async () => {
    await f.locator('#models-open').click(); await f.locator('[data-model-select]').first().click();
    await native.waitForFunction(() => __MMD_PREVIEW__.snapshot().model === 'a');
    await f.locator('#models-open').click(); await f.locator('[data-model-settings]').last().click();
    const before=(await state()).settings.b.stream;
    await f.locator('.sl-model-switch input').first().click(); await f.locator('#models-save-settings').click();
    assert((await state()).settings.b.stream === !before,'Model toggle not retained in native state');
    await f.locator('#models-close').click(); await f.waitForFunction(() => !document.getElementById('models-dialog').open);
  });
  if (modules.persona !== false && enabled('openPersona','setPersonaName','setPersonaIdentity','submitPersona','closePersona') && nativeCaps.capabilities.openPersona?.available) await check('同层人设 → 原生表单，原生修改 → 同层表单', async () => {
    await open(f, 'persona'); await f.locator('#feature-field-name').fill('联动旅人'); await action(f, 'submitPersona').click();
    await native.waitForFunction(() => __MMD_PREVIEW__.snapshot().persona.name === '联动旅人');
    await toNative(); await native.locator('.shortcut-btn').filter({ hasText: '用户人设' }).click();
    assert(await native.locator('.role-profile-modal input').inputValue() === '联动旅人', 'Native persona did not receive Frame change');
    await native.locator('.role-profile-modal input').fill('原生修改人设'); await native.locator('.role-profile-modal .complete-btn').click();
    await toCard(); f = await card(); await open(f, 'persona'); assert(await f.locator('#feature-field-name').inputValue() === '原生修改人设', 'Frame persona did not receive native change');
    await f.locator('#features-close').click(); await f.waitForFunction(() => !document.getElementById('features-dialog').open);
  });
  else report.checks.push({ name: '人设模块', status: 'NOT APPLICABLE', reason: '作品未启用或未允许人设操作' });
  if (enabled('sendMessage')) await check('隐藏发送入口停用与原生草稿保护', async () => {
    await native.evaluate(() => __MMD_PREVIEW__.setFault('disable-send'));
    await f.waitForFunction(() => document.getElementById('send').disabled);
    await native.evaluate(() => document.querySelector('.chat-send-proxy').removeAttribute('aria-disabled'));
    await f.waitForFunction(() => !document.getElementById('send').disabled);
    const count = (await state()).conversations.find(c=>c.id==='main').messages.length;
    await native.evaluate(() => { const input=MmdSameLayerInput.resolve(document).input; input.value='已有原生草稿'; input.dispatchEvent(new Event('input',{bubbles:true})); });
    await f.locator('#text').fill('不能覆盖原生草稿'); await f.locator('#send').click();
    await f.waitForFunction(() => document.getElementById('notice').textContent.includes('不同的草稿'));
    assert((await state()).draft==='已有原生草稿','Native draft overwritten');
    assert((await state()).conversations.find(c=>c.id==='main').messages.length===count,'Conflicting draft sent');
    await native.evaluate(() => { const input=MmdSameLayerInput.resolve(document).input; input.value=''; input.dispatchEvent(new Event('input',{bubbles:true})); }); await f.locator('#text').fill('');
    assert(await native.evaluate(() => { const scope=document.querySelector('.chat-bottom .chat-input-scope'), copy=scope.cloneNode(true); scope.after(copy); const blocked=!MmdSameLayerInput.resolve(document).input; copy.remove(); return blocked; }), 'Ambiguous native composers accepted');
  });
  if (modules.supplement !== false && enabled('openSupplement','setSupplementText','openSupplementPositionPicker','setSupplementPosition','confirmSupplementPosition','submitSupplement','closeSupplement')) await check('补充设定与位置提交后重新读取', async () => {
    await open(f,'supplement'); await f.locator('#feature-field-text').fill('潮汐会改变码头道路。');
    await action(f,'openSupplementPositionPicker').click(); await action(f,'setSupplementPosition').last().click();
    await action(f,'confirmSupplementPosition').click(); await action(f,'submitSupplement').click();
    await f.waitForFunction(() => !document.getElementById('features-dialog').open);
    assert((await state()).supplement.text === '潮汐会改变码头道路。' && (await state()).supplement.position===2,'Supplement state not shared');
    await open(f,'supplement'); assert(await f.locator('#feature-field-text').inputValue()==='潮汐会改变码头道路。','Supplement not retained after reopening');
    await f.locator('#features-close').click(); await f.waitForFunction(() => !document.getElementById('features-dialog').open);
  });
  let gameTurn = null;
  if (await f.locator('#game-panel').isVisible()) await check('规则行动与当前会话进度', async () => {
    await f.locator('#explore').click(); await f.waitForFunction(() => Number(document.getElementById('turn').textContent) > 0); gameTurn = await f.locator('#turn').innerText();
  });
  if (modules.conversations !== false && enabled('openConversationPanel','selectConversation','closeConversationPanel') && nativeCaps.capabilities.openConversationPanel?.available) await check('会话双向切换与游戏进度隔离', async () => {
    let previousFrame = await native.locator('iframe').getAttribute('name');
    await open(f, 'conversations'); await action(f, 'selectConversation').last().click();
    await native.waitForFunction(() => __MMD_PREVIEW__.snapshot().current === 'archive');
    await native.waitForFunction(previous => document.querySelector('iframe')?.name && document.querySelector('iframe').name !== previous, previousFrame); f = await card();
    assert((await f.locator('#messages').innerText()).includes('灯塔'), 'New Frame did not load the selected history');
    if (gameTurn !== null) assert(await f.locator('#turn').innerText() === '0', 'Game save leaked across conversations');
    await toNative(); await native.locator('.more-options-scope .btn-icon').click(); await native.locator('.more-scope .item').filter({hasText:'新的聊天'}).click();
    previousFrame = await native.locator('iframe').getAttribute('name');
    await native.locator('.conversation-item').filter({ hasText: '当前故事' }).locator('.center-scope').click();
    await native.waitForFunction(() => __MMD_PREVIEW__.snapshot().current === 'main');
    await native.waitForFunction(previous => document.querySelector('iframe')?.name && document.querySelector('iframe').name !== previous, previousFrame); await toCard(); f = await card();
    if (gameTurn !== null) await f.waitForFunction(value => document.getElementById('turn').textContent === value, gameTurn);
  });
  else report.checks.push({ name: '会话模块', status: 'NOT APPLICABLE', reason: '作品未启用或未允许会话操作' });
  await check('390px 窄屏：两个界面可见且无横向溢出', async () => {
    await page.setViewportSize({ width: 390, height: 844 }); await toNative();
    assert(await native.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Native page overflows horizontally');
    assert(await native.evaluate(() => [...document.querySelectorAll('.modify-btn-scope')].every(el => { const text=el.closest('.touch-scope')?.querySelector('.content'); return text && el.getBoundingClientRect().top >= text.getBoundingClientRect().bottom-1; })), 'Native message controls overlap their text');
    await page.screenshot({ path: path.join(output, 'mmd-mobile.png') });
    await toCard(); f = await card(); assert(await f.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Card overflows horizontally');
    await page.screenshot({ path: path.join(output, 'same-layer-mobile.png') });
  });
  await check('离开角色后解除挂载，返回后重新连接', async () => {
    await native.evaluate(() => __MMD_PREVIEW__.leave()); await native.waitForFunction(() => !document.querySelector('iframe'));
    await native.evaluate(() => __MMD_PREVIEW__.returnToChat()); f = await card(); assert(await f.locator('#connection').innerText() === '已连接', 'Card failed to reconnect after navigation');
  });
  await reviewNative({context,base,manifest,output,check,assert,report});
  await check('运行时无脚本错误', async () => assert(report.pageErrors.length === 0, report.pageErrors.join('\n')));
  report.status = report.blockedExternalRequests.length ? 'FAIL' : 'PASS';
  if (report.blockedExternalRequests.length) report.error = '预览请求了本地清单以外的网络资源，已阻止并需要复核。';
} catch (error) { report.error = error.message; console.error(error.stack); if (page) { await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{}); report.diagnostics = await Promise.all(page.frames().map(f=>f.evaluate(()=>({url:location.href,text:document.body.innerText.slice(-1200)})).catch(()=>({detached:true})))); } }
finally {
  if (browser) await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
  await writeFile(path.join(output, 'results.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
}
process.exitCode = report.status === 'PASS' ? 0 : 1;
