/* Original local behavior attached to the existing old-MMD preview templates. */
(function (G) {
  'use strict';
  G.MmdLegacyPanels = { create(u) {
    const { state, cfg, D, q, box, node, button, layers, popup, removePanel, conversation, fill, newConversation, record } = u;
    state.character = { name: cfg.title || '角色对话', description: '', opening: conversation().messages[0]?.text || '' };
    state.chatOptions = { perspective: '第二人称', length: '适中', pace: '平衡', parallel: '关闭', summary: '手动' };
    state.summaries = {}; state.comments = []; state.assistDismissed = false;
    for (const model of state.models) Object.assign(state.settings[model.id], { outputTokens: model.tokenLimits[0], stream: true });
    function panel(name, selector) {
      const template = q('#mmd-native-panel-templates').content.querySelector('[data-sheet="' + name + '"]');
      if (!template) throw Error('Missing original native panel: ' + name);
      const wrap = template.cloneNode(true); wrap.classList.add('native-restored'); wrap.dataset.open = 'on';
      for (const b of wrap.querySelectorAll('[data-pano-sheet-close]')) b.onclick = e => { e.stopPropagation(); wrap.remove(); };
      layers.append(wrap); record('panel:' + name); return wrap.querySelector(selector);
    }
    function textArea(id, value, title, parent, maxLength = 12000) {
      parent.append(box('sim-field-label', title)); const input=node('textarea','uni-textarea-textarea');
      input.id=id; input.value=value; input.maxLength=maxLength; parent.append(input); return input;
    }
    function summary() {
      const p=panel('summary','.summary-sheet'), body=p.querySelector('.summary-body'); body.replaceChildren();
      const current=state.current, input=textArea('native-summary-text',state.summaries[current]||'','剧情总结',body);
      body.append(box('sim-note','此处保存当前本地会话的总结；自动模型总结需要真实服务。'));
      p.querySelector('.summary-save-btn').onclick=()=>{state.summaries[current]=input.value;record('saveSummary');removePanel(p);};
    }
    function newChat() {
      const p=panel('newchat','.alert-scope');
      p.querySelector('.ok-btn').onclick=()=>{removePanel(p);newConversation();};
    }
    function resetChat() {
      const p=panel('newchat','.alert-scope'); p.querySelector('.alert-title').textContent='重置本地聊天';
      p.querySelector('.alert-content').textContent='清空当前本地模拟会话的消息和总结？其他会话会保留。';
      p.querySelector('.ok-btn').onclick=()=>{const current=state.current; conversation().messages.splice(0,Infinity,{id:'preview-'+crypto.randomUUID(),role:'assistant',text:state.character.opening});delete state.summaries[current];u.renderMessages();record('resetLocalChat');removePanel(p);};
    }
    function download(filename, value, type) {
      const url=URL.createObjectURL(new Blob([value],{type})), a=D.createElement('a');a.href=url;a.download=filename;a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);record('exportChat');
    }
    function exportChat() {
      const p=popup('export-chat-scope','导出聊天');p.append(box('sim-note','导出当前本地会话。文件不包含账号凭据。'));
      p.append(button('导出 JSON','export-json',()=>download('mmd-preview-chat.json',JSON.stringify({format:'mmd-local-preview-chat',title:conversation().title,messages:conversation().messages,summary:state.summaries[state.current]||''},null,2),'application/json')),
        button('导出文本','export-text',()=>download('mmd-preview-chat.txt',conversation().messages.map(m=>(m.role==='user'?'你':'角色')+'：'+m.text).join('\n\n'),'text/plain')));
    }
    function editRole() {
      const p=popup('edit-role-scope','编辑角色');p.append(box('sim-note','仅编辑本地预览中的角色资料；不修改发布卡和平台角色。'));
      const name=node('input','uni-input-input');name.id='native-role-name';name.value=state.character.name;name.maxLength=100;
      p.append(box('sim-field-label','角色名字'),name);
      const desc=textArea('native-role-description',state.character.description,'角色描述',p);
      const opening=textArea('native-role-opening',state.character.opening,'开场白',p);
      p.append(button('保存本地角色','save-role',()=>{state.character={name:name.value,description:desc.value,opening:opening.value};q('.header-roleName').textContent=name.value;record('editLocalRole');removePanel(p);}));
    }
    function background() {
      const p=popup('modify-scope',''), title=box('modify-title','更换背景');p.append(title,box('sim-note','修改本地聊天背景，可选颜色或本机图片。'));
      const target=q('.chat-scope-box');
      for (const [label,color] of [['夜色','#17181a'],['雾蓝','#1e2c3d'],['松绿','#23352e']]) p.append(button(label,'native-background-color',()=>{state.background=color;target.style.backgroundColor=color;}));
      const input=node('input','native-background-file');input.type='file';input.accept='image/png,image/jpeg,image/webp';
      const note=box('sim-note');input.onchange=async()=>{const file=input.files[0];if(!file)return;if(file.size>5000000||!['image/png','image/jpeg','image/webp'].includes(file.type)){note.textContent='请选择 5 MB 以内的 PNG、JPEG 或 WebP 图片。';return;}
        const reader=new FileReader();reader.onload=()=>{target.style.backgroundImage='url("'+reader.result+'")';state.backgroundImage=reader.result;note.textContent='本地背景图片已应用。';};reader.readAsDataURL(file);};
      p.append(box('sim-field-label','背景图片'),input,button('清除图片','native-background-clear',()=>{target.style.backgroundImage='';delete state.backgroundImage;}),note);
    }
    function assist() {
      const p=panel('alert','.alert-scope'), row=p.querySelector('.alert-checkbox'), input=node('input','');input.type='checkbox';input.checked=state.assistDismissed;
      row.querySelector('.checkbox-box').replaceChildren(input);row.querySelector('uni-text').textContent='本地记住此选项';
      p.querySelector('.alert-content').textContent='本地预览可填入一条示例回复；真实 AI 帮聊需要模型服务。';
      p.querySelector('.ok-btn').textContent='填入示例回复';
      p.querySelector('.ok-btn').onclick=()=>{state.assistDismissed=input.checked;if(state.draft.trim()){p.querySelector('.alert-content').textContent='输入框已有草稿，请先处理草稿后再使用帮聊。';return;}fill('我想再听听这段故事。');record('localAssist');removePanel(p);};
    }
    function comments() {
      const p=popup('comments-scope','本地评论'), rows=box('native-comment-list');p.append(box('sim-note','评论只保留在这次本地预览中，不会发给其他人。'),rows);
      const paint=()=>{rows.replaceChildren(...state.comments.map(t=>box('native-comment',t)));};paint();
      const input=textArea('native-comment-text','','写一条本地评论',p,1000);
      p.append(button('添加本地评论','add-local-comment',()=>{if(!input.value.trim())return;state.comments.push(input.value);input.value='';paint();record('localComment');}));
    }
    function chatSettings() {
      const p=panel('conv','.conv-style-modal'), scroll=p.querySelector('.outer-scroll-view');scroll.replaceChildren();
      const groups=[['style','叙述风格',['自然','细腻','简洁']],['perspective','叙述人称',['第一人称','第二人称','第三人称']],['length','回复篇幅',['简短','适中','详细']],['pace','剧情推进',['缓慢','平衡','积极']],['parallel','平行故事',['关闭','开启']],['summary','总结方式',['手动','自动']]];
      for(const [key,label,options] of groups){const card=box('cs-group-card'),grid=box('cs-style-grid');card.append(box('cs-section-title',label),box('cs-section-subtitle','本地演示选项；真实可选值以平台为准'),grid);
        for(const value of options)grid.append(button(value,'cs-style-item'+((key==='style'?state.style:state.chatOptions[key])===value?' active':''),b=>{if(key==='style')state.style=value;else state.chatOptions[key]=value;for(const x of grid.children)x.classList.toggle('active',x===b);}));scroll.append(card);}
      const right=p.querySelector('.cs-header-right');right.removeAttribute('data-pano-sheet-close');right.onclick=null;right.replaceChildren(button('确认','confirm-btn',()=>removePanel(p)));
    }
    function modelConfig(key) {
      // Bind the existing old-page controls; do not replace the template body
      // with adapter-test examples or settings from a different platform.
      const p=panel('model','.model-setting-scope'), value=state.settings[key];
      const model=state.models.find(m=>m.id===key);
      p.querySelector('.mp-model-name').textContent=model.name;
      p.querySelector('.mp-ev').textContent=model.previewEnergy;
      p.querySelector('.mp-energy-pill').title='本地模拟电量，不代表平台价格';
      const tokenBox=p.querySelector('.mp-tokens'), prototype=tokenBox.firstElementChild;
      tokenBox.replaceChildren(...model.tokenLimits.map(label=>{const option=prototype.cloneNode(false);option.textContent=label;return option;}));
      const choices=[...p.querySelectorAll('.mp-token-btn')];
      for(const choice of choices){
        const label=choice.textContent.trim();
        choice.setAttribute('role','button');choice.tabIndex=0;
        choice.classList.toggle('selected',value.outputTokens===label);
        const select=()=>{value.outputTokens=label;for(const item of choices){const selected=item===choice;item.classList.toggle('selected',selected);item.setAttribute('aria-pressed',String(selected));}};
        choice.setAttribute('aria-pressed',String(value.outputTokens===label));
        choice.onclick=e=>{e.stopPropagation();select();};
        choice.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();select();}};
      }
      const toggle=p.querySelector('.u-switch'),knob=toggle.querySelector('.u-switch__node');
      function paint(){knob.classList.toggle('u-switch__node--on',value.stream);toggle.setAttribute('aria-checked',String(value.stream));}
      const flip=()=>{value.stream=!value.stream;paint();};
      toggle.onclick=e=>{e.stopPropagation();flip();};
      toggle.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();flip();}};
      paint();
      p.querySelector('.bottom .btn').onclick=()=>{record('submitModelConfiguration');removePanel(p);};
    }
    function share(row) {
      const p=panel('share','.share-popup');p.querySelector('.share-title').textContent=row?'分享消息':'分享对话';
      const link='https://example.invalid/preview/'+cfg.appId+(row?'#'+row.id:'');p.querySelector('.share-sub-title').textContent=link;
      p.append(box('sim-note','示例链接仅供本地检查，不是公开分享地址。'));
      if(row)p.append(box('native-share-excerpt',row.text));p.querySelector('.gen-link-btn').onclick=()=>navigator.clipboard?.writeText(link).catch(()=>{});
    }
    return {panel,summary,newChat,resetChat,exportChat,editRole,background,assist,comments,chatSettings,modelConfig,share};
  }};
})(window);
