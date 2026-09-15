import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdtemp, cp } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createServer } from 'node:http';

test('all additional native actions through packaged Host/Frame', { skip: !process.env.PLAYWRIGHT_MODULE, timeout: 180000 }, async t => {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
  const directory = await mkdtemp(path.join(tmpdir(),'mmd-actions-')), source = path.join(directory,'source'), out = path.join(directory,'out');
  await cp(fileURLToPath(new URL('../assets/same-layer-kit',import.meta.url)),source,{recursive:true});
  const frame = await readFile(path.join(source,'frame.js'),'utf8');
  // Test-only access to the real Frame transport; never written to distributed assets.
  await writeFile(path.join(source,'frame.js'),frame.replace(/\}\)\(\);\s*$/, 'globalThis.featureHarness={call,state:()=>snapshot};\n})();'));
  const build=spawnSync(process.env.PYTHON||'python',[fileURLToPath(new URL('build_same_layer.py',import.meta.url)),'--source',source,'--out',out,'--build-id','actions-test','--no-engine'],{encoding:'utf8'});
  assert.equal(build.status,0,build.stderr);
  const pkg=JSON.parse(await readFile(path.join(out,'same-layer-mmd.json'),'utf8'));
  let runtime=pkg.statusbar;
  for(const row of pkg.regex_scripts){const end=row.findRegex.lastIndexOf('/');runtime=runtime.replace(new RegExp(row.findRegex.slice(1,end),row.findRegex.slice(end+1)),row.replaceString);}
  const fixture=await readFile(new URL('test-fixtures/same-layer-actions.html',import.meta.url),'utf8');
  const html=fixture.replace('<!--RUNTIME-->',runtime);
  const server=createServer((req,res)=>{if(req.url.startsWith('/icons/')){res.writeHead(204);res.end();return;}res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser; const covered=new Set();
  try {
    browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'msedge'});
    const base='http://127.0.0.1:'+server.address().port;
    async function visit(fn){const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
      try{await page.goto(base);await page.waitForSelector('iframe');const f=await(await page.$('iframe')).contentFrame();await f.waitForFunction(()=>globalThis.featureHarness?.state());
        const snap=()=>f.evaluate(async()=>{await featureHarness.call('snapshot');return featureHarness.state().native.actions;});
        const invoke=async(group,action,extra={})=>{const s=await snap();const answer=await f.evaluate(({action,payload})=>featureHarness.call('native.invoke',{action,payload}),{action,payload:{revision:s[group].revision,...extra}});assert.equal(answer.ok,true,action);covered.add(action);return answer;};
        await fn({page,f,snap,invoke});assert.deepEqual(errors,[]);
      }catch(e){console.log('Native feature failure',e.message,await page.evaluate(()=>({events:fixture.events,panels:document.getElementById('panels').innerText})));throw e;}finally{await context.close();}}

    await t.test('input, navigation, share, prompt and chat-settings read/dispatch',async()=>visit(async({page,snap,invoke})=>{
      await invoke('composer','setInputText',{text:'测试草稿'});assert.equal(await page.inputValue('#chat-input-scope textarea'),'测试草稿');
      await invoke('navigation','exit');await invoke('navigation','openComments');await invoke('navigation','refreshConversation');
      await invoke('navigation','toggleFavorite');assert.equal((await snap()).navigation.favorite,true);
      await invoke('sharePanel','openSharePanel');assert.equal((await snap()).sharePanel.link,'https://example.invalid/share/demo');
      assert.equal((await invoke('sharePanel','copyShareLink')).data.clipboard,'unknown');await invoke('sharePanel','closeSharePanel');
      await invoke('instructionSelector','openPromptSelector');const choice=(await snap()).instructionSelector.instructions[1];
      await invoke('instructionSelector','applyInstruction',{instructionId:choice.id,fingerprint:choice.fingerprint,label:choice.label,index:choice.index});
      assert.equal(await page.inputValue('#chat-input-scope textarea'),'执行：休息');await invoke('instructionSelector','closePromptSelector');
      await invoke('chatSettings','openChatSettings');assert.equal((await snap()).chatSettings.controls[0].label,'风格');await invoke('chatSettings','closeChatSettings');
      await invoke('chatSettings','openChatSettings');await invoke('chatSettings','submitChatSettings');
    }));
    await t.test('more menu and feature openings retain explicit supported kinds',async()=>visit(async({page,snap,invoke})=>{
      await invoke('moreMenu','openMoreMenu');let menu=(await snap()).moreMenu;
      const row=menu.items.find(x=>x.kind==='background');await invoke('moreMenu','activateMoreMenuItem',{itemId:row.id});assert.equal((await snap()).backgroundPanel.open,true);
      await page.evaluate(()=>document.querySelector('.modify-scope').parentElement.remove());
      await invoke('moreMenu','openBackgroundPanel');assert.equal((await snap()).backgroundPanel.open,true);
      await invoke('moreMenu','openCustomInstructions');assert.equal((await snap()).customInstructionsPanel.open,true);
      await invoke('moreMenu','closeMoreMenu');assert.equal((await snap()).moreMenu.open,false);
      // Navigation deliberately detaches an old Host context; test native action receipt directly.
      const answer=await page.evaluate(async()=>{const a=MmdSameLayerAdapters.dom(document,{});try{return await a.invoke('openTutorial',{});}finally{a.destroy();}});
      assert.equal(answer.ok,true);covered.add('openTutorial');assert.match(page.url(),/pages\/help\/help/);
    }));
    await t.test('persona modes, gender, fields and submit/close',async()=>visit(async({page,snap,invoke})=>{
      await invoke('personaPanel','openPersona');let s=(await snap()).personaPanel;
      await invoke('personaPanel','setPersonaMode',{modeId:s.modes[1].id});s=(await snap()).personaPanel;
      await invoke('personaPanel','setPersonaGender',{genderId:s.genderChoices[1].id});
      await invoke('personaPanel','setPersonaName',{name:'旅人'});await invoke('personaPanel','setPersonaIdentity',{identity:'来自海边'});
      await invoke('personaPanel','submitPersona',{name:'旅人',identity:'来自海边'});assert.deepEqual(await page.evaluate(()=>fixture.values.persona),['旅人','来自海边']);
      await invoke('personaPanel','openPersona');await invoke('personaPanel','closePersona');assert.equal((await snap()).personaPanel.open,false);
    }));
    await t.test('supplement text, adjacent wheel movement, confirmation and submission',async()=>visit(async({page,snap,invoke})=>{
      await invoke('supplementPanel','openSupplement');await invoke('supplementPanel','setSupplementText',{text:'港口有雾'});
      await invoke('supplementPanel','openSupplementPositionPicker');let s=(await snap()).supplementPanel;
      await invoke('supplementPanel','setSupplementPosition',{choiceId:s.picker.choices[2].id});await invoke('supplementPanel','confirmSupplementPosition');
      assert.equal((await snap()).supplementPanel.positionLabel,'末尾');
      await invoke('supplementPanel','openSupplementPositionPicker');await invoke('supplementPanel','cancelSupplementPosition');
      await invoke('supplementPanel','submitSupplement',{text:'港口有雾'});assert.equal(await page.evaluate(()=>fixture.values.supplement),'港口有雾');
      await invoke('supplementPanel','openSupplement');await invoke('supplementPanel','closeSupplement');
    }));
    await t.test('conversation selection, rename, two-stage deletion and creation',async()=>visit(async({page,snap,invoke})=>{
      await invoke('conversationPanel','openConversationPanel');let row=(await snap()).conversationPanel.conversations[1];
      const reference=()=>({conversationId:row.id,fingerprint:row.fingerprint,index:row.index});
      await invoke('conversationPanel','renameConversation',{...reference(),title:'新备注'});
      row=(await snap()).conversationPanel.conversations.find(x=>x.title==='新备注');assert.ok(row);
      const requested=await invoke('conversationPanel','requestDeleteConversation',reference());assert.equal(requested.accepted,false);
      assert.equal((await snap()).conversationPanel.conversations.length,3);
      await invoke('conversationPanel','deleteConversation',{...reference(),confirmationToken:requested.data.confirmation.confirmationToken});
      assert.equal((await snap()).conversationPanel.conversations.length,2);
      row=(await snap()).conversationPanel.conversations[1];await invoke('conversationPanel','selectConversation',reference());
      assert.equal(await page.locator('#msglistview .content').innerText(),'选择了故事 2');
      await invoke('conversationPanel','openConversationPanel');await invoke('conversationPanel','closeConversationPanel');
      await invoke('conversationPanel','openConversationPanel');await invoke('conversationPanel','createConversation');
      assert.equal(await page.locator('#msglistview .content').innerText(),'新故事');
    }));
    await t.test('message copy, regenerate and bound editor text/transform/submit/cancel',async()=>visit(async({page,snap,invoke})=>{
      const last=(await snap()).messages.items.at(-1);await invoke('messages','copyMessage',{messageId:last.id});
      assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),'第二答');
      await invoke('messages','regenerateMessage',{messageId:last.id});assert.match(await page.locator('#msglistview .content').last().innerText(),/重写/);
      await invoke('messages','openEditMessage',{messageId:last.id});await invoke('editPanel','setEditText',{text:'编辑草稿'});
      const transform=(await snap()).editPanel.transforms[0];await invoke('editPanel','applyEditTransform',{transformId:transform.id});assert.equal((await snap()).editPanel.text,'简化后的内容');
      await invoke('editPanel','submitEditMessage',{messageId:last.id,text:'最终文本'});assert.equal(await page.locator('#msglistview .content').last().innerText(),'最终文本');
      await invoke('messages','openEditMessage',{messageId:last.id});await invoke('editPanel','cancelEditMessage');
    }));
    await t.test('message delete and rollback require tokens and verify exact surviving messages',async()=>visit(async({page,snap,invoke})=>{
      let row=(await snap()).messages.items[2];let result=await invoke('messages','deleteMessage',{messageId:row.id});assert.equal(result.accepted,false);assert.equal(await page.locator('#msglistview .item').count(),4);
      await invoke('messages','deleteMessage',{messageId:row.id,confirmationToken:result.data.confirmation.confirmationToken});assert.equal(await page.locator('#msglistview .item').count(),3);
      row=(await snap()).messages.items[1];result=await invoke('messages','rollbackMessage',{messageId:row.id});assert.equal(result.data.phase,'confirmation-required');
      await invoke('messages','rollbackMessage',{messageId:row.id,confirmationToken:result.data.confirmation.confirmationToken});assert.deepEqual(await page.locator('#msglistview .content').allTextContents(),['第一句','第一答']);
    }));
    await t.test('new story retains the selected prefix and observes replacement identities',async()=>visit(async({page,snap,invoke})=>{
      const row=(await snap()).messages.items[1];await invoke('messages','startNewStoryFromMessage',{messageId:row.id});assert.deepEqual(await page.locator('#msglistview .content').allTextContents(),['第一句','第一答']);
    }));
    await t.test('stale targets, unknown actions, disabled fields and destructive generic entries are rejected',async()=>visit(async({page,f,snap,invoke})=>{
      await invoke('personaPanel','openPersona');const before=await snap();await page.evaluate(()=>document.querySelector('.role-profile-modal input').disabled=true);
      await assert.rejects(invoke('personaPanel','setPersonaName',{name:'不能写'}));assert.equal(await page.inputValue('.role-profile-modal input'),'');
      await page.evaluate(()=>fixture.reset());await invoke('moreMenu','openMoreMenu');const reset=(await snap()).moreMenu.items.find(x=>x.destructive);
      await assert.rejects(invoke('moreMenu','activateMoreMenuItem',{itemId:reset.id}));assert.equal(await page.evaluate(()=>fixture.events.includes('UNEXPECTED_RESET')),false);
      await assert.rejects(f.evaluate(()=>featureHarness.call('native.invoke',{action:'stopGeneration',payload:{}})));
      const s=await snap(),row=s.messages.items[1];await page.evaluate(()=>document.querySelectorAll('#msglistview .content')[1].textContent='已变化');
      await assert.rejects(f.evaluate(payload=>featureHarness.call('native.invoke',{action:'deleteMessage',payload}),{revision:s.messages.revision,messageId:row.id}));
      assert.equal(await page.locator('#msglistview .item').count(),4);
    }));
    await t.test('timeout and cancel never replay clicks; shared adapter serializes groups',async()=>visit(async({page})=>{
      const result=await page.evaluate(async()=>{const a=MmdSameLayerAdapters.dom(document,{actionTimeoutMs:100});fixture.fault='no-more';let timeout;
        try{await a.invoke('openMoreMenu',{});}catch(e){timeout=e.code;}const clicks=fixture.events.filter(x=>x==='openMoreMenu').length;
        fixture.fault='';fixture.delay=500;const pending=a.invoke('openMoreMenu',{}).then(()=>'',e=>e.code);let concurrent;
        try{await a.invoke('openComments',{});}catch(e){concurrent=e.code;}a.cancel();const cancelled=await pending;a.destroy();return {timeout,clicks,concurrent,cancelled};});
      assert.equal(result.timeout,'TIMEOUT');assert.equal(result.clicks,1);assert.equal(result.concurrent,'NOT_AVAILABLE');assert.equal(result.cancelled,'CONTEXT_CHANGED');
    }));

    await t.test('native delete tokens cannot operate on a changed message or replacement confirmation dialog',async()=>visit(async({page,snap,invoke})=>{
      let s=await snap(),row=s.messages.items[1];const request=await invoke('messages','deleteMessage',{messageId:row.id});
      await page.evaluate(()=>document.querySelectorAll('#msglistview .content')[1].textContent='changed after confirmation');
      await assert.rejects(invoke('messages','deleteMessage',{messageId:row.id,confirmationToken:request.data.confirmation.confirmationToken}));
      assert.equal(await page.locator('#msglistview .item').count(),4);
      await invoke('conversationPanel','openConversationPanel');row=(await snap()).conversationPanel.conversations[1];
      const ref={conversationId:row.id,fingerprint:row.fingerprint,index:row.index};
      const pending=await invoke('conversationPanel','requestDeleteConversation',ref);
      await page.evaluate(()=>{const p=document.querySelector('.confirm-scope');p.replaceWith(p.cloneNode(true));});
      await assert.rejects(invoke('conversationPanel','deleteConversation',{...ref,confirmationToken:pending.data.confirmation.confirmationToken}));
      assert.equal((await snap()).conversationPanel.conversations.length,3);
      assert.equal(await page.evaluate(()=>fixture.events.includes('confirm-conversation')),false);
    }));
    await t.test('editing cannot submit to a replaced message or a different editor instance',async()=>visit(async({page,snap,invoke})=>{
      let row=(await snap()).messages.items.at(-1);await invoke('messages','openEditMessage',{messageId:row.id});
      await page.evaluate(()=>{const p=document.querySelector('.msg-modify-scope');p.replaceWith(p.cloneNode(true));});
      await assert.rejects(invoke('editPanel','submitEditMessage',{messageId:row.id,text:'wrong owner'}));
      assert.equal(await page.locator('#msglistview .content').last().innerText(),'第二答');
      assert.equal(await page.evaluate(()=>fixture.events.includes('submitEditMessage')),false);
    }));
    await t.test('duplicate conversation identities and a restricted action allowlist stay unavailable',async()=>visit(async({page,snap,invoke})=>{
      await invoke('conversationPanel','openConversationPanel');
      await page.evaluate(()=>{const row=document.querySelectorAll('.conversation-item')[1];row.parentElement.append(row.cloneNode(true));});
      const rows=(await snap()).conversationPanel.conversations.filter(x=>x.title==='故事 1');assert.equal(rows.length,2);assert.ok(rows.every(x=>x.available===false));
      const answer=await page.evaluate(async()=>{const a=MmdSameLayerAdapters.dom(document,{allowedActions:['openComments']});let code;
        try{await a.invoke('openPersona',{});}catch(e){code=e.code;}const result={code,available:a.snapshot().capabilities.openPersona.available};a.destroy();return result;});
      assert.deepEqual(answer,{code:'NOT_AVAILABLE',available:false});
    }));
    const expected=await (async()=>{const p=await browser.newPage();try{await p.goto(base);await p.waitForFunction(()=>globalThis.MmdSameLayerActions);return await p.evaluate(()=>MmdSameLayerActions.actions);}finally{await p.close();}})();
    assert.equal(expected.length,52);assert.deepEqual([...covered].sort(),[...expected].sort(),'every implemented additional action exercised successfully');
  }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
});
