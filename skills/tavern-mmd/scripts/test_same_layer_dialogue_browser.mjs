import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdtemp, cp, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createServer } from 'node:http';

test('dialogue modules: real UI clicks against local native DOM fixtures', {skip:!process.env.PLAYWRIGHT_MODULE,timeout:180000}, async t=>{
  const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
  const dir=await mkdtemp(path.join(tmpdir(),'mmd-dialogue-ui-'));
  const script=fileURLToPath(new URL('preview_same_layer_dialogue.py',import.meta.url));
  function build(out,extra=[]){const r=spawnSync(process.env.PYTHON||'python',[script,'--out',out,...extra],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);}
  build(dir); const html=await readFile(path.join(dir,'dialogue-preview.html'),'utf8');
  const minimal=path.join(dir,'minimal'); await cp(fileURLToPath(new URL('../assets/same-layer-kit',import.meta.url)),minimal,{recursive:true});
  await writeFile(path.join(minimal,'frame-ui-config.js'),`globalThis.MmdSameLayerUIConfig={theme:'light',modules:Object.fromEntries(['messageActions','models','conversations','persona','supplement','instructions','settings','sharing','navigation','more','game'].map(x=>[x,false]))};`);
  build(path.join(dir,'disabled'),['--source',minimal]); const disabled=await readFile(path.join(dir,'disabled/dialogue-preview.html'),'utf8');
  const server=createServer((req,res)=>{if(req.url.startsWith('/icons/')){res.writeHead(204);res.end();return;}res.setHeader('Content-Type','text/html; charset=utf-8');res.end(req.url==='/disabled'?disabled:html);});
  await new Promise(r=>server.listen(0,'127.0.0.1',r)); const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'msedge'});
  const base='http://127.0.0.1:'+server.address().port;const evidence=process.env.MMD_SL_EVIDENCE_DIR||dir;await mkdir(evidence,{recursive:true});
  async function visit(fn,route='/') {const context=await browser.newContext({viewport:{width:1360,height:950},permissions:['clipboard-read','clipboard-write']});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    try{await page.goto(base+route);await page.waitForSelector('iframe');const f=await(await page.$('iframe')).contentFrame();await f.waitForFunction(()=>document.getElementById('connection')?.textContent==='已连接');await fn({page,f});assert.deepEqual(errors,[]);}
    catch(e){console.log('Dialogue failure:',e.message,await page.evaluate(()=>fixture.events));for(const f of page.frames().slice(1))console.log(await f.locator('body').innerText().catch(()=> 'detached'));throw e;}finally{await context.close();}}
  // A conversation replaces the Host iframe on its next state pulse.
  // Wait for that replacement and handshake instead of racing a fixed delay.
  const nextConversationFrame=async(page,previous)=>{
    await page.waitForFunction(previous=>{
      const frame=document.querySelector('iframe');
      return frame?.name && frame.name!==previous;
    },previous);
    const frame=await(await page.$('iframe')).contentFrame();
    await frame.locator('#connection').filter({hasText:'已连接'}).waitFor();
    return frame;
  };
  const action=(f,name)=>f.locator(`[data-sl-action="${name}"]`);
  const open=async(f,kind)=>{if(await f.locator('#feature-nav').isHidden())await f.locator('#menu-open').click();await f.locator('#feature-open-'+kind).click();await f.locator('#features-dialog').waitFor();await f.locator('#features-close').waitFor({state:'visible'});};
  const done=async f=>{await f.waitForFunction(()=>!document.getElementById('features-close').disabled);};
  const close=async f=>{await f.locator('#features-close').click();if(await f.locator('#features-confirm').isVisible())await f.locator('#features-confirm-yes').click();await f.waitForFunction(()=>!document.getElementById('features-dialog').open);};
  const yes=async f=>{await f.locator('#features-confirm-yes').click();};
  try {
    await t.test('composer, game, model and dark/light/mobile layout',async()=>visit(async({page,f})=>{
      await f.locator('#text').fill('码头的灯还亮着吗？');await f.locator('#composer-sync').click();await page.waitForFunction(()=>document.querySelector('#chat-input-scope textarea').value==='码头的灯还亮着吗？');
      await f.locator('#send').click();await f.waitForFunction(()=>document.querySelectorAll('.message').length===5);
      await f.locator('#explore').click();await f.waitForFunction(()=>document.getElementById('turn').textContent==='1');
      await page.screenshot({path:path.join(evidence,'dialogue-desktop.png')});
      await f.locator('#models-open').click();await f.locator('[data-model-select]').last().click();await f.waitForFunction(()=>document.getElementById('models-open').textContent.includes('星海·乙'));
      await f.locator('#theme-toggle').click();assert.equal(await f.locator('html').getAttribute('data-theme'),'light');await page.screenshot({path:path.join(evidence,'dialogue-light.png')});
      await page.setViewportSize({width:390,height:844});assert.equal(await f.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(evidence,'dialogue-mobile.png')});
      await open(f,'persona');await done(f);assert.equal(await f.evaluate(()=>document.getElementById('features-dialog').scrollWidth<=document.getElementById('features-dialog').clientWidth),true);await page.screenshot({path:path.join(evidence,'dialogue-persona-mobile.png')});
    }));
    await t.test('native draft conflict, explicit replacement and input-change-before-send guard',async()=>visit(async({page,f})=>{
      await page.locator('#chat-input-scope textarea').fill('原生独立草稿');await f.locator('#text').fill('本地草稿');await f.locator('#send').click();
      await f.waitForFunction(()=>document.getElementById('notice').textContent.includes('不同的草稿'));assert.equal(await page.locator('#chat-input-scope textarea').inputValue(),'原生独立草稿');assert.equal(await page.locator('#msglistview .item').count(),3);
      await f.locator('#composer-sync').click();await f.locator('#features-confirm-no').click();assert.equal(await page.locator('#chat-input-scope textarea').inputValue(),'原生独立草稿');
      await f.locator('#composer-sync').click();await yes(f);await page.waitForFunction(()=>document.querySelector('#chat-input-scope textarea').value==='本地草稿');
      await page.evaluate(()=>document.querySelector('#chat-input-scope textarea').addEventListener('input',e=>{e.target.value='输入事件期间变化';},{once:true}));
      await f.locator('#send').click();await f.waitForFunction(()=>document.getElementById('notice').textContent.includes('发送前发生变化'));assert.equal(await page.locator('#msglistview .item').count(),3);
    }));
    await t.test('message copy, regenerate and new-story workflow use displayed target',async()=>visit(async({page,f})=>{
      await action(f,'copyMessage').last().click();await f.waitForFunction(()=>document.getElementById('notice').textContent.includes('操作已返回'));assert.match(await page.evaluate(()=>navigator.clipboard.readText()),/潮水退下/);
      await action(f,'regenerateMessage').last().click();await yes(f);await page.waitForFunction(()=>document.querySelector('#msglistview .item:last-child').textContent.includes('重写'));
      await action(f,'startNewStoryFromMessage').first().click();await yes(f);await page.waitForFunction(()=>fixture.events.includes('startNewStoryFromMessage'));assert.equal(await page.locator('#msglistview .item').count(),1);
    }));
    await t.test('navigation reflects favorite and returns to native comments',async()=>visit(async({page,f})=>{
      await f.locator('#menu-open').click();await action(f,'toggleFavorite').click();await f.waitForFunction(()=>document.getElementById('feature-toggleFavorite').textContent.includes('已收藏'));
      await action(f,'refreshConversation').click();await page.waitForFunction(()=>fixture.events.includes('refreshConversation'));
      await action(f,'openComments').click();await page.waitForFunction(()=>fixture.events.includes('openComments'));await page.waitForFunction(()=>document.querySelector('iframe').getBoundingClientRect().width===0);
    }));
    await t.test('editor drafts survive polling; transforms, sync, save and native cancel',async()=>visit(async({page,f})=>{
      await action(f,'openEditMessage').last().click();await f.locator('#feature-field-text').fill('本地编辑草稿');await page.waitForTimeout(550);assert.equal(await f.locator('#feature-field-text').inputValue(),'本地编辑草稿');
      await action(f,'setEditText').click();await done(f);assert.equal(await page.locator('.vditor-reset').innerText(),'本地编辑草稿');
      await action(f,'applyEditTransform').click();await yes(f);await done(f);assert.equal(await f.locator('#feature-field-text').inputValue(),'简化后的内容');
      await f.locator('#feature-field-text').fill('最终消息');await action(f,'submitEditMessage').click();await f.waitForFunction(()=>!document.getElementById('features-dialog').open);assert.equal(await page.locator('#msglistview .content').last().innerText(),'最终消息');
      await action(f,'openEditMessage').last().click();await close(f);assert.equal(await page.locator('.msg-modify-scope').count(),0);
    }));
    await t.test('stale editor keeps draft and refuses submit until explicit reload',async()=>visit(async({page,f})=>{
      await action(f,'openEditMessage').last().click();await f.locator('#feature-field-text').fill('保留的草稿');
      await page.locator('.vditor-reset').fill('外部编辑');await f.waitForFunction(()=>document.getElementById('features-notice').textContent.includes('内容已变化'));
      assert.equal(await f.locator('#feature-field-text').inputValue(),'保留的草稿');assert.equal(await action(f,'submitEditMessage').isDisabled(),true);
      await f.locator('#features-reload').click();await f.locator('#features-confirm-no').click();assert.equal(await f.locator('#feature-field-text').inputValue(),'保留的草稿');
      await f.locator('#features-reload').click();await yes(f);await done(f);assert.equal(await f.locator('#feature-field-text').inputValue(),'外部编辑');
    }));
    await t.test('persona drafts, modes, gender, field sync and submit',async()=>visit(async({page,f})=>{
      await open(f,'persona');await f.locator('#feature-field-name').fill('巡灯人');await f.locator('#feature-field-identity').fill('在雾港长大');
      await action(f,'setPersonaMode').last().click();await done(f);assert.equal(await f.locator('#feature-field-name').inputValue(),'巡灯人');
      await action(f,'setPersonaGender').last().click();await done(f);await action(f,'setPersonaName').click();await done(f);await action(f,'setPersonaIdentity').click();await done(f);
      await action(f,'submitPersona').click();await page.waitForFunction(()=>fixture.values.persona?.[0]==='巡灯人');assert.deepEqual(await page.evaluate(()=>fixture.values.persona),['巡灯人','在雾港长大']);
    }));
    await t.test('supplement draft persists through position picker; cancel and submit',async()=>visit(async({page,f})=>{
      await open(f,'supplement');await f.locator('#feature-field-text').fill('夜晚涨潮');await action(f,'setSupplementText').click();await done(f);
      await action(f,'openSupplementPositionPicker').click();await action(f,'setSupplementPosition').last().click();await done(f);await action(f,'confirmSupplementPosition').click();await done(f);
      assert.equal(await f.locator('#feature-field-text').inputValue(),'夜晚涨潮');await action(f,'openSupplementPositionPicker').click();await action(f,'cancelSupplementPosition').click();await done(f);
      await action(f,'submitSupplement').click();await page.waitForFunction(()=>fixture.values.supplement==='夜晚涨潮');
      await open(f,'supplement');await action(f,'openSupplementPositionPicker').click();await close(f);assert.equal(await page.locator('.uni-picker-view-content').count(),0);
    }));
    await t.test('instructions protect composer draft; sharing and read-only settings',async()=>visit(async({page,f})=>{
      await f.locator('#text').fill('尚未发送');await open(f,'instructions');await action(f,'applyInstruction').last().click();await f.locator('#features-confirm-no').click();assert.equal(await f.locator('#text').inputValue(),'尚未发送');
      await action(f,'applyInstruction').last().click();await yes(f);await done(f);assert.equal(await f.locator('#text').inputValue(),'执行：休息');await close(f);
      await open(f,'sharing');assert.match(await f.locator('.sl-share-link').innerText(),/example.invalid/);await action(f,'copyShareLink').click();await done(f);await close(f);
      await open(f,'settings');assert.match(await f.locator('.sl-feature-body').innerText(),/自然/);await action(f,'submitChatSettings').click();await page.waitForFunction(()=>fixture.events.includes('submitChatSettings'));
    }));
    await t.test('conversations: rename, cancel deletes without native popup, confirmed delete, switch/create',async()=>visit(async({page,f})=>{
      await open(f,'conversations');await action(f,'renameConversation').nth(1).click();await f.locator('#features-answer').fill('灯塔之约');await yes(f);await done(f);assert.match(await f.locator('.sl-feature-body').innerText(),/灯塔之约/);
      await action(f,'requestDeleteConversation').nth(1).click();await f.locator('#features-confirm-no').click();assert.equal(await page.locator('.confirm-scope').count(),0);assert.equal(await page.locator('.conversation-item').count(),3);
      await action(f,'requestDeleteConversation').nth(1).click();await yes(f);await done(f);assert.equal(await page.locator('.conversation-item').count(),2);
      let previous=await page.locator('iframe').getAttribute('name');
      await action(f,'selectConversation').last().click();await page.waitForFunction(()=>document.querySelector('#msglistview').textContent.includes('选择了故事 2'));f=await nextConversationFrame(page,previous);await f.locator('#messages').filter({hasText:'选择了故事 2'}).waitFor();
      await open(f,'conversations');previous=await page.locator('iframe').getAttribute('name');
      await action(f,'createConversation').click();await page.waitForFunction(()=>document.querySelector('#msglistview').textContent.includes('新故事'));f=await nextConversationFrame(page,previous);await f.locator('#messages').filter({hasText:'新故事'}).waitFor();
    }));
    await t.test('message destructive confirmation, stale target and text-only rendering',async()=>visit(async({page,f})=>{
      await action(f,'deleteMessage').first().click();await f.locator('#features-confirm-no').click();assert.equal(await page.locator('#msglistview .item').count(),3);
      await action(f,'deleteMessage').first().click();await page.evaluate(()=>document.querySelector('#msglistview .content').textContent='<img src=x onerror=alert(1)>已变更');await yes(f);
      await f.waitForFunction(()=>document.getElementById('notice').textContent.includes('变化')||document.getElementById('notice').textContent.includes('改变')||document.getElementById('notice').textContent.includes('过期'));
      assert.equal(await page.locator('#msglistview .item').count(),3);assert.equal(await f.locator('#messages img').count(),0);await f.waitForFunction(()=>document.getElementById('messages').textContent.includes('已变更'));
      await action(f,'deleteMessage').first().click();await yes(f);await page.waitForFunction(()=>document.querySelectorAll('#msglistview .item').length===2);
      await action(f,'rollbackMessage').first().click();await yes(f);await page.waitForFunction(()=>document.querySelectorAll('#msglistview .item').length===1);
    }));
    await t.test('more menu routes supported panels; disabled generic entries stay blocked',async()=>visit(async({page,f})=>{
      await open(f,'more');assert.equal(await action(f,'activateMoreMenuItem').filter({hasText:'重置聊天'}).isDisabled(),true);
      await action(f,'activateMoreMenuItem').filter({hasText:'用户人设'}).click();await f.locator('#feature-field-name').waitFor();await close(f);
      await open(f,'more');await action(f,'openBackgroundPanel').click();await page.waitForFunction(()=>fixture.events.includes('openBackgroundPanel'));await page.waitForFunction(()=>document.querySelector('iframe').hidden||!document.querySelector('iframe').isConnected||document.querySelector('iframe').getBoundingClientRect().width===0);
    }));
    await t.test('author module switches hide UI while basic chat remains',async()=>visit(async({f})=>{
      assert.equal(await f.locator('html').getAttribute('data-theme'),'light');assert.equal(await f.locator('#models-open').count(),0);assert.equal(await f.locator('#game-panel').isHidden(),true);assert.equal(await f.locator('.sl-message-actions button').count(),0);
      await f.locator('#menu-open').click();assert.equal(await f.locator('#feature-nav button').count(),1);assert.equal(await f.locator('#send').isEnabled(),true);
    },'/disabled'));
    console.log('Dialogue evidence:',evidence,'; real MMD / physical mobile: NOT RUN');
  } finally {await browser.close();await new Promise(r=>server.close(r));}
});
