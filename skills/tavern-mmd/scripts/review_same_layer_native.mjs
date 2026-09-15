/* Native-surface completeness, independent from which card UI modules are enabled. */
import path from 'node:path';
import { readFile } from 'node:fs/promises';
import { reviewEdit } from './review_same_layer_edit.mjs';

export async function reviewNative({ context, base, manifest, output, check, assert, report }) {
  const page=await context.newPage();page.on('pageerror',e=>report.pageErrors.push(e.message));page.setDefaultTimeout(12000);
  try {
    await page.goto(base);const native=await(await page.$('.preview-stage')).contentFrame();
    await native.waitForFunction(()=>!!window.__MMD_PREVIEW__);
    await native.waitForFunction(app=>window.__MMD_SAME_LAYER__?.[app]?.getState().ready,manifest.appId);
    await page.locator('#native-view').click();
    const state=()=>native.evaluate(()=>__MMD_PREVIEW__.snapshot());
    const shortcut=label=>native.locator('.shortcut-btn').filter({hasText:label});
    const openMore=async()=>{if(!await native.locator('.more-scope').count())await native.locator('.more-options-scope .btn-icon').click();};
    const more=async label=>{await openMore();await native.locator('.more-scope > .item').filter({hasText:new RegExp('^'+label+'$')}).click();};
    const selectNativeConversation=async(title,key)=>{const previous=await native.locator('iframe').getAttribute('name');await native.locator('.conversation-item').filter({hasText:title}).locator('.center-scope').click();
      await native.waitForFunction(({previous,key})=>document.querySelector('iframe')?.name!==previous&&__MMD_PREVIEW__.snapshot().current===key,{previous,key});
      await native.waitForFunction(app=>__MMD_SAME_LAYER__[app].getState().ready,manifest.appId);await page.locator('#native-view').click();};
    const closeCustom=()=>native.locator('.sim-popup').last().locator('.u-popup__content__close').click();
    const dismissMore=async()=>{if(await native.locator('.more-scope').count())await native.locator('.more-options-scope .btn-icon').click();};
    await check('原生完整性：保留旧预览全部快捷、更多入口与面板模板',async()=>{
      assert(JSON.stringify(await native.locator('.shortcut-btn .sb-text').allTextContents())===JSON.stringify(manifest.nativeInventory.shortcuts),'Native shortcuts differ from existing MMD preview');
      await openMore();assert(JSON.stringify(await native.locator('.more-scope > .item .item-title').allTextContents())===JSON.stringify(manifest.nativeInventory.more),'Native more-menu entries were lost');
      const panels=await native.evaluate(()=>[...document.getElementById('mmd-native-panel-templates').content.querySelectorAll('[data-sheet]')].map(el=>el.dataset.sheet));
      assert(manifest.nativeInventory.panels.every(name=>panels.includes(name)),'An original native panel template is missing');
      await page.screenshot({path:path.join(output,'native-more-desktop.png')});await dismissMore();
    });
    await check('实机模型参数对照：选项、分组、提示和样式一致',async()=>{
      const expected=JSON.parse(await readFile(new URL('./fixtures/mmd-legacy/model-observed.json',import.meta.url),'utf8'));
      await shortcut('模型设置').click();
      const actual=await native.locator('.model-setting-scope').evaluate((p,expected)=>{
        const text=s=>p.querySelector(s)?.textContent.trim();
        return {title:text('.mp-card-title'),hint:text('.mp-card-hint'),choices:[...p.querySelectorAll('.mp-token-btn')].map(e=>e.textContent.trim()),
          switchTitle:text('.mp-sw-title'),switchDescription:text('.mp-sw-desc'),energyUnit:text('.mp-el'),
          groups:p.querySelectorAll('.mp-card,.mp-preset-card,.mp-switch-row').length,
          styles:Object.fromEntries(Object.entries(expected.styles).map(([selector,props])=>{
            const el=selector==='.model-setting-scope'?p:p.querySelector(selector),css=el?getComputedStyle(el):{};
            return [selector,Object.fromEntries(Object.keys(props).map(k=>[k,css[k]??'MISSING']))];
          }))};
      },expected);
      report.nativeModelComparison={observedAt:expected.observedAt,actual};
      for(const key of ['title','hint','choices','switchTitle','switchDescription','energyUnit','styles'])
        assert(JSON.stringify(actual[key])===JSON.stringify(expected[key]),'Live model reference differs: '+key+' '+JSON.stringify(actual[key]));
      assert(actual.groups===2,'Extra simulator model settings must not enter the native preview');
      await page.screenshot({path:path.join(output,'native-model-initial.png')});
      await native.locator('.model-setting-scope .mp-close').click();
    });
    await check('原生模型设置：直接打开参数、输出上限与流式选项保留',async()=>{
      await shortcut('模型设置').click();assert(await native.locator('.model-setting-scope').isVisible(),'Shortcut did not open model settings');
      assert(!await native.locator('.model-switch-scope').count(),'Model settings was incorrectly replaced by model list');
      await native.getByRole('button',{name:'返回游戏',exact:true}).waitFor({state:'hidden'});
      await native.locator('.mp-token-btn').filter({hasText:/^10000$/}).click();
      await native.locator('.mp-switch-row').filter({hasText:'流式输出'}).locator('.u-switch').click();
      await native.waitForFunction(()=>{const p=document.querySelector('.model-setting-scope'),n=p.querySelector('.u-switch__node');return getComputedStyle(n).transform==='matrix(1, 0, 0, 1, -20, 0)'&&getComputedStyle(p.querySelector('.u-switch')).backgroundColor==='rgb(255, 255, 255)';});
      await page.screenshot({path:path.join(output,'native-model-settings.png')});
      await native.locator('.model-setting-scope .bottom .btn').click();
      assert((await state()).settings.a.outputTokens==='10000' && (await state()).settings.a.stream===false,'Native model changes were not retained');
      await shortcut('模型设置').click();assert(await native.locator('.mp-token-btn.selected').filter({hasText:/^10000$/}).count()===1,'Reopened model output limit lost');await native.locator('.model-setting-scope .mp-close').click();await native.getByRole('button',{name:'返回游戏',exact:true}).waitFor({state:'visible'});
    });
    await check('原生设置、指令和人设面板可打开并保留选择',async()=>{
      await shortcut('对话设置').click();assert(await native.locator('.cs-group-card').count()>=6,'Chat settings were reduced to one demo choice');
      await native.locator('.cs-group-card').filter({hasText:'叙述人称'}).getByRole('button',{name:'第三人称',exact:true}).click();
      await native.locator('.conv-style-modal .confirm-btn').click();await shortcut('对话设置').click();
      assert(await native.locator('.cs-group-card').filter({hasText:'叙述人称'}).locator('.cs-style-item.active').innerText()==='第三人称','Chat setting choice was lost');
      await native.locator('.conv-style-modal .cs-header-left').click();
      await shortcut('选择指令').click();await native.locator('.instruction-chip').first().click();assert((await state()).draft.startsWith('执行：'),'Instruction did not fill shared composer');await native.locator('.instruction-bar .back-btn').click();
      await native.locator('.chat-input-scope textarea:visible').fill('');
      await shortcut('用户人设').click();await native.locator('.role-profile-modal .header-box .icon-back').click();
    });
    await check('原生剧情总结：保存、重开和会话隔离',async()=>{
      await shortcut('总结剧情').click();await native.locator('#native-summary-text').fill('已抵达雾港，正在寻找旧地图。');await native.locator('.summary-save-btn').click();
      await more('剧情总结');assert(await native.locator('#native-summary-text').inputValue()==='已抵达雾港，正在寻找旧地图。','Summary not retained');await native.locator('.summary-close').click();
      await more('新的聊天');await selectNativeConversation('灯塔旧事','archive');
      await shortcut('总结剧情').click();assert(await native.locator('#native-summary-text').inputValue()==='','Summary leaked into another conversation');await native.locator('.summary-close').click();
      await more('新的聊天');await selectNativeConversation('当前故事','main');
    });
    await reviewEdit({page,native,output,check,assert});
    await check('原生用户消息编辑与消息分享可操作',async()=>{
      // Author seeds may contain no user message. Add one through the native composer.
      if(!await native.locator('.item.self').count()){await native.locator('.chat-input-scope textarea:visible').fill('原生消息按钮检查');await native.locator('.pano-send:visible').click();}
      const row=native.locator('.item.self').first();assert(await row.locator('.modify-btn').count()===2,'User edit/share controls missing');
      await row.getByRole('button',{name:'编辑',exact:true}).click();await native.locator('#vditor .vditor-ir > pre.vditor-reset').fill('原生编辑后的用户消息');await native.locator('.modify-btn-box .modify-btn').click();
      assert(await row.locator('.content').innerText()==='原生编辑后的用户消息','User edit not saved');
      await row.getByRole('button',{name:'分享',exact:true}).click();assert((await native.locator('.native-share-excerpt').innerText()).includes('原生编辑后的用户消息'),'Message share did not bind the clicked message');
      await native.locator('.pano-sheet[data-sheet=share] .u-popup__content__close').click();
    });
    await check('原生导出聊天与角色编辑保存可用',async()=>{
      await more('导出聊天');const pending=page.waitForEvent('download');await native.locator('.export-json').click();const download=await pending;
      const exported=JSON.parse(await readFile(await download.path(),'utf8'));assert(exported.messages.some(m=>m.text==='原生编辑后的用户消息'),'Export did not contain current chat');await closeCustom();
      await more('编辑角色');await native.locator('#native-role-name').fill('本地角色编辑检查');await native.locator('.save-role').click();
      assert(await native.locator('.header-roleName').innerText()==='本地角色编辑检查','Local character title not updated');
      await more('编辑角色');assert(await native.locator('#native-role-name').inputValue()==='本地角色编辑检查','Character editor did not retain local fields');await closeCustom();
    });
    await check('原生背景、自定义指令、补充设定与教程入口可用',async()=>{
      await more('更换背景');await native.getByRole('button',{name:'雾蓝',exact:true}).click();assert((await state()).background==='#1e2c3d','Background choice did not apply');
      assert(await native.locator('.native-background-file').count()===1,'Local background image picker missing');await closeCustom();
      await more('自定义指令');await native.locator('.custom-instruction-scope textarea').fill('继续故事\n检查灯塔');await native.locator('.custom-instruction-scope').getByRole('button',{name:'保存',exact:true}).click();
      await dismissMore();await shortcut('选择指令').click();assert((await native.locator('.instruction-chip').allTextContents()).includes('检查灯塔'),'Custom instruction did not reach selector');await native.locator('.instruction-bar .back-btn').click();
      await more('设定补充');await native.locator('.role-extra-setting .icon-back').click();
      await more('用户人设');await native.locator('.role-profile-modal .icon-back').click();
      await more('对话设置');await native.locator('.conv-style-modal .cs-header-left').click();
      await more('游玩教程');assert(await native.locator('.sim-tutorial').isVisible(),'Tutorial missing');await closeCustom();await dismissMore();
    });
    await check('原生评论、分享和帮聊面板具有本地操作',async()=>{
      await native.locator('[aria-label=评论]').click();await native.locator('#native-comment-text').fill('本地评论检查');await native.locator('.add-local-comment').click();assert((await state()).comments.includes('本地评论检查'),'Local comment not added');await closeCustom();
      await native.locator('.header-icon-meun [aria-label=分享]').click();assert(await native.locator('.gen-link-btn').isVisible(),'Native share action missing');await native.locator('.pano-sheet[data-sheet=share] .u-popup__content__close').click();
      await native.locator('.ai-assistant').click();await native.locator('.pano-dialog[data-sheet=alert] .ok-btn').click();assert((await state()).draft==='我想再听听这段故事。','Local assist did not fill composer');
    });
    await check('原生窄屏：更多菜单、总结和模型设置可操作',async()=>{
      await page.setViewportSize({width:390,height:844});await openMore();await page.screenshot({path:path.join(output,'native-more-mobile.png')});
      assert(await native.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Native more menu overflows');
      await more('剧情总结');await page.screenshot({path:path.join(output,'native-summary-mobile.png')});await native.locator('.summary-save-btn').click();await dismissMore();
      await shortcut('模型设置').click();await page.screenshot({path:path.join(output,'native-model-mobile.png')});const before=(await state()).settings.a.stream;await native.locator('.mp-switch-row').filter({hasText:'流式输出'}).locator('.u-switch').click();assert((await state()).settings.a.stream===!before,'Narrow model settings control is unreachable');await native.locator('.model-setting-scope .bottom .btn').click();
    });
    await check('原生新聊天与重置：取消保护、确认后改变本地状态',async()=>{
      const initial=(await state()).current;await shortcut('新的聊天').click();await native.locator('.pano-dialog[data-sheet=newchat] .cancel-btn').click();assert((await state()).current===initial,'Cancel unexpectedly created chat');
      const previous=await native.locator('iframe').getAttribute('name');await shortcut('新的聊天').click();await native.locator('.pano-dialog[data-sheet=newchat] .ok-btn').click();await native.waitForFunction(({initial,previous})=>__MMD_PREVIEW__.snapshot().current!==initial&&document.querySelector('iframe')?.name&&document.querySelector('iframe').name!==previous,{initial,previous});await native.waitForFunction(app=>__MMD_SAME_LAYER__[app].getState().ready,manifest.appId);await page.locator('#native-view').click();
      await more('重置聊天');await native.locator('.pano-dialog[data-sheet=newchat] .cancel-btn').click();
      await more('重置聊天');await native.locator('.pano-dialog[data-sheet=newchat] .ok-btn').click();assert((await state()).events.includes('resetLocalChat'),'Local reset confirmation did not run');
    });
  } catch(error) { report.nativeDiagnostics=await Promise.all(page.frames().map(f=>f.evaluate(()=>({url:location.href,text:document.body.innerText.slice(-1500)})).catch(()=>({detached:true}))));await page.screenshot({path:path.join(output,'native-failure.png')}).catch(()=>{});throw error; }
  finally {await page.close();}
}
