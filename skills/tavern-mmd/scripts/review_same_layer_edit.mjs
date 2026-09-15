/* Contracts observed on the user's unstyled old MMD page, 2026-09-16. */
import path from 'node:path';
export async function reviewEdit({page,native,output,check,assert}) {
  const panel=native.locator('.msg-modify-scope');
  const editor=native.locator('#vditor .vditor-ir > pre.vditor-reset[contenteditable="true"]');
  const row=native.locator('.item.Ai:not(.self)').last();
  const open=async()=>{await row.getByRole('button',{name:'编辑',exact:true}).click();await editor.waitFor();
    // Vditor animates the toolbar height when the native overlay class appears.
    await native.waitForFunction(()=>getComputedStyle(document.querySelector('#vditor .vditor-toolbar--hide')).height==='0.5px');};
  const cancel=async()=>{await panel.click({position:{x:8,y:8}});await panel.waitFor({state:'detached'});};
  await check('实机消息编辑：节点、ID、按钮文案与关键样式对照',async()=>{
    assert(await row.locator('.modify-btn-scope > uni-view.modify-btn > uni-image').count()>=2,'Native bubble buttons must use uni-view / uni-image');
    const iconStyle=await row.locator('.modify-btn-scope > .modify-btn').first().evaluate(e=>{const s=getComputedStyle(e);return [s.width,s.height,s.borderRadius,s.backgroundColor]});
    assert(JSON.stringify(iconStyle)===JSON.stringify(['24px','24px','50%','rgba(0, 0, 0, 0.5)']),'Bubble icon size/style differs from live MMD');
    await open();
    const surface=await panel.evaluate(p=>{const mount=p.querySelector('#vditor'),pre=p.querySelector('.vditor-ir > pre'),outer=p.querySelector('.modify-input-box');return {
      height:mount.getBoundingClientRect().height,viewport:innerHeight,preHeight:pre.getBoundingClientRect().height,
      bars:[outer,pre].map(el=>{const s=getComputedStyle(el,'::-webkit-scrollbar');return [s.display,s.width,s.height]}),
      outerGutter:outer.offsetWidth-outer.clientWidth,preGutter:pre.offsetWidth-pre.clientWidth
    }});
    assert(Math.abs(surface.height-surface.viewport*.4)<1,'Native Vditor must keep 40vh height, including short messages');
    assert(surface.height-surface.preHeight<5,'Editable background does not fill the editor: '+JSON.stringify(surface));
    assert(surface.bars.every(s=>JSON.stringify(s)===JSON.stringify(['none','0px','0px']))&&surface.outerGutter===0&&surface.preGutter===0,'Native editor scrollbars must be hidden without reserving a gutter');
    assert(await panel.locator(':scope > uni-view.modify-input-box > uni-view#vditor.vditor').count()===1,'Edit hierarchy differs from live MMD');
    assert(await panel.locator('.u-popup__content').count()===0,'Editor must not be a generic popup');
    assert(await panel.locator('#vditorExportIframe').count()===1,'Vditor export iframe ID missing');
    assert(JSON.stringify(await panel.locator('.option-box > uni-view.option-item').allTextContents())===JSON.stringify(['简转繁','繁转简','去除异常符号','去除异常文字']),'Native transform labels differ');
    assert(await panel.locator(':scope > uni-view.modify-btn-box > uni-view.modify-btn').innerText()==='保存','Save tag, class or label differs');
    const observed=await panel.evaluate(p=>{const s=getComputedStyle(p),pre=getComputedStyle(p.querySelector('.vditor-ir > pre')),btn=getComputedStyle(p.querySelector('.modify-btn-box .modify-btn'));return {parent:p.parentElement.tagName,position:s.position,z:s.zIndex,blur:s.backdropFilter,bg:s.backgroundColor,preBg:pre.backgroundColor,prePadding:pre.padding,saveBg:btn.backgroundColor,saveHeight:btn.height,saveRadius:btn.borderRadius,toolbar:getComputedStyle(p.querySelector('.vditor-toolbar')).overflow}});
    const expectedBg=await editor.evaluate(e=>e.matches(':focus')?'rgb(250, 251, 252)':'rgb(255, 255, 255)');
    assert(JSON.stringify(observed)===JSON.stringify({parent:'UNI-PAGE-BODY',position:'fixed',z:'9999',blur:'blur(10px)',bg:'rgba(0, 0, 0, 0.7)',preBg:expectedBg,prePadding:'10px 35px',saveBg:'rgb(255, 109, 151)',saveHeight:'42.5px',saveRadius:'25px',toolbar:'hidden'}),'Editor style differs: '+JSON.stringify(observed));
    await editor.click();
    assert(await editor.evaluate(e=>getComputedStyle(e).backgroundColor)==='rgb(250, 251, 252)','Focused editor must use the native uniform light background');
    await page.screenshot({path:path.join(output,'native-edit-desktop.png')});await cancel();
  });
  await check('消息编辑：取消不改正文，保存与重开一致，简繁转换可用',async()=>{
    const before=await row.locator('.content').innerText();
    await open();await editor.fill('取消后不应留下此句');await editor.click();assert(await panel.count()===1,'Editing bubbles to backdrop');await cancel();
    assert(await row.locator('.content').innerText()===before,'Cancel changed saved text');
    await open();await editor.fill('汉字转换测试');await panel.getByRole('button',{name:'简转繁',exact:true}).click();
    assert((await editor.innerText()).includes('漢字轉換測試'),'Simplified conversion failed');
    await panel.getByRole('button',{name:'繁转简',exact:true}).click();assert((await editor.innerText()).includes('汉字转换测试'),'Traditional conversion failed');
    // Vditor serializes the two editable paragraphs as Markdown separated by a blank line.
    const saved='本地编辑保存检查\n\n第二行保持原样';await editor.fill('本地编辑保存检查\n第二行保持原样');await panel.locator('.modify-btn-box > .modify-btn').click();await panel.waitFor({state:'detached'});
    assert(await row.locator('.content').innerText()===saved,'Save did not change only the selected message');
    await open();assert((await editor.innerText()).trim()===saved,'Reopening editor lost saved text');await cancel();
  });
  await check('消息编辑窄屏：长文滚动、保存可达、遮罩取消',async()=>{
    const size=page.viewportSize();await page.setViewportSize({width:390,height:844});await open();await editor.fill(('长段落用于检查滚动与按钮位置。\n\n').repeat(50));
    const visible=await panel.locator('.modify-btn-box .modify-btn').evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.right<=innerWidth});
    assert(visible,'Save button outside mobile viewport');
    assert(await editor.evaluate(e=>e.scrollHeight>e.clientHeight),'Long text must scroll inside the editable area');
    const bounds=await editor.boundingBox();await page.mouse.move(bounds.x+bounds.width/2,bounds.y+bounds.height/2);await page.mouse.wheel(0,450);
    await native.waitForFunction(()=>document.querySelector('#vditor .vditor-ir > pre').scrollTop>0);
    assert(await editor.evaluate(e=>getComputedStyle(e,'::-webkit-scrollbar').display)==='none','Scrolling revealed the native scrollbar');
    await page.screenshot({path:path.join(output,'native-edit-mobile.png')});await cancel();await page.setViewportSize(size);
  });
}
