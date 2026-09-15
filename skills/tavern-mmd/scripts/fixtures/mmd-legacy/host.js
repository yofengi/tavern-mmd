/* Original local simulator for the observed old-MMD shell. Never a real backend. */
(function (G) {
  'use strict';
  const D = document, cfg = G.__MMD_LEGACY_PREVIEW_CONFIG__, q = s => D.querySelector(s);
  const node = (tag, cls, text = '') => { const n = D.createElement(tag); n.className = cls; n.textContent = text; return n; };
  const box = (cls, text = '') => node('uni-view', cls, text);
  const button = (label, cls, fn) => { const b = node('button', cls, label); b.type = 'button'; b.onclick = e => { e.stopPropagation(); fn(b); }; return b; };
  const iconsBase = new URL('icons/', location.href);
  const icon = name => { const i = D.createElement('img'); i.src = new URL(name, iconsBase).href; i.alt = ''; return i; };
  const id = () => 'preview-' + crypto.randomUUID();
  let messageSerial=Date.now();
  const message = (role, text) => ({ id: String(++messageSerial), role, text });
  const seeded = cfg.messages || [{ role: 'assistant', text: '雾灯亮起，渡船刚刚靠岸。你可以在 MMD 页面和同层页面继续同一段对话。' }];
  const state = {
    scope: { accountKey: 'local-preview-only', roleId: cfg.appId, conversationKey: 'main' },
    current: 'main', draft: '', favorite: false, model: 'a', filter: 'all', generating: false,
    conversations: [{ id: 'main', title: '当前故事', messages: seeded.map(m => message(m.role, m.text)) },
      { id: 'archive', title: '灯塔旧事', messages: [message('assistant', '你回到了灯塔。这里保存着另一段对话。')] }],
    persona: { mode: '自定义', name: '旅人', gender: '未设定', identity: '初到雾港的旅人' },
    supplement: { text: '', position: 0 }, style: '自然', background: 'default', instructions: ['继续故事', '休息片刻'],
    models: [{ id: 'a', name: 'GLM-5.3-flash', description: '实机参数样本，本地模拟回复', cost: '模拟消耗 20', previewEnergy: 20, tokenLimits: ['5000','10000'] }, { id: 'b', name: '本地推理模型', description: '模拟推理回复', cost: '模拟消耗 2', previewEnergy: 2, tokenLimits: ['5000','10000'] }],
    settings: { a: {}, b: {} },
    events: []
  };
  const record = name => { state.events.push(name); if (state.events.length > 500) state.events.shift(); };
  const conversation = () => state.conversations.find(c => c.id === state.current);
  const scope = q('.chat-bottom .chat-input-scope'), inputs = [...scope.querySelectorAll('textarea')];
  const chat = q('.chat'), list = q('#msglistview');
  const layers = box('sim-layers'); chat.append(layers);
  q('.header-roleName').textContent = cfg.title || '角色对话';
  q('.header-role-img').textContent = '雾';
  // Replace visual-only placeholder panels with stateful local panels.
  for (const sel of ['.more-scope', '.instruction-bar', '.msg-option-scope']) q(sel)?.remove();
  G.__MMD_SAME_LAYER_SCOPE__ = () => ({ ...state.scope });
  function fill(value, source) {
    state.draft = value; for (const input of inputs) if (input !== source) input.value = value;
    scope.classList.toggle('is-multiline', value.includes('\n') || value.length > 80);
    record('input');
  }
  function expand(on) { scope.classList.toggle('is-expanded', on); }
  for (const input of inputs) input.addEventListener('input', () => fill(input.value, input));
  q('.chat-input-collapsed-display').onclick = () => { expand(true); inputs[0].focus(); };
  inputs[0].addEventListener('blur', () => expand(false));
  q('.chat-input-toolbar').replaceChildren(button('清空', 'chat-input-tool-btn', () => fill('')));
  function closeAll() { G.MmdLegacyEditor.close(); q('.more-options-scope').dataset.more='off';q('.more-options-scope .btn-icon').textContent='+';layers.replaceChildren(); q('.instruction-bar')?.remove(); q('.shortcut-bar').classList.remove('hidden'); q('.more-scope')?.remove(); }
  function popup(cls, title, parent = layers) {
    const wrap = box('u-popup sim-popup'), overlay = box('sim-mask'), content = box('u-popup__content sim-panel'), body = box(cls);
    const close = button('关闭', 'u-popup__content__close', () => wrap.remove());
    if (title) body.append(box('title', title)); content.append(body, close); wrap.append(overlay, content); parent.append(wrap);
    overlay.onclick = () => wrap.remove(); return body;
  }
  const removePanel = p => p.closest('.sim-popup,.pano-sheet,.pano-dialog')?.remove();
  function confirm(kind, fn) {
    const p = popup('confirm-scope'); p.append(box('confirm-title', kind === 'conversation' ? '删除聊天记录' : '操作确认'),
      box('confirm-content', kind === 'rollback' ? '回溯将会删除此消息下方的所有消息' : '删除后将无法恢复'));
    const bottom = box('confirm-bottom'); bottom.append(button('取消', 'cancel-btn', () => removePanel(p)), button('确认', 'ok-btn', () => { record('confirm-' + kind); fn(); removePanel(p); })); p.append(bottom);
  }
  function menu(row, element) {
    q('.msg-option-scope')?.remove(); const p = box('msg-option-scope sim-message-menu'); p.dataset.open = 'on';
    p.append(box('msg-content-box', row.text)); const choices = box('msg-options-box'); p.append(choices); layers.append(p);
    const current = () => conversation().messages.indexOf(row);
    const operations = [['复制', () => navigator.clipboard?.writeText(row.text).catch(() => {})],
      ['删除', () => confirm('message', () => { conversation().messages.splice(current(), 1); element.remove(); })],
      ['回溯', () => confirm('rollback', () => { conversation().messages.splice(current() + 1); while (element.parentElement.nextSibling) element.parentElement.nextSibling.remove(); })]];
    operations.push(['开启新的故事', () => newConversation(conversation().messages.slice(0, current() + 1))]);
    for (const [label, fn] of operations) choices.append(button(label, 'option-item', () => { record(label); p.remove(); fn(); }));
    p.onclick = e => { if (e.target === p) p.remove(); };
  }
  function editMessage(row, content) { G.MmdLegacyEditor.open({row,content,box,record}); }
  function messageButton(label,file,fn) {
    const b=box('modify-btn'),image=node('uni-image',''),background=node('div',''),span=node('span',''),img=icon(file);
    background.style.backgroundImage='url("'+img.src+'")';img.draggable=false;image.append(background,span,img);b.append(image);
    b.setAttribute('role','button');b.setAttribute('aria-label',label);b.tabIndex=0;
    b.onclick=e=>{e.stopPropagation();fn();};b.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();b.click();}};
    return b;
  }
  function renderMessages() {
    list.replaceChildren(); const rows = conversation().messages;
    rows.forEach((row, index) => {
      const wrap = box(''), item = box('item Ai' + (row.role === 'user' ? ' self' : '')), touch = box('touch-scope'), content = box('content ' + (row.role === 'user' ? 'right' : 'left'), row.text);
      touch.id='item'+index; content.id = 'q'+row.id; touch.append(content); item.append(touch); wrap.append(item); list.append(wrap);
      const controls = box('modify-btn-scope');controls.style.marginRight='3.125rem';
      if (row.role === 'assistant' && index === rows.length - 1) controls.append(messageButton('重新生成','ico_message_refresh.png',()=>{row.text+='\n【本地模拟重新生成】';content.innerText=row.text;record('regenerate');}));
      controls.append(messageButton('编辑','ico_message_edit.png',()=>editMessage(row,content)),messageButton('分享','ico_message_share.png',()=>restored.share(row)));touch.append(controls);
      let timer; const clear = () => clearTimeout(timer);
      content.addEventListener('pointerdown', () => { clear(); timer = setTimeout(() => menu(row, item), 450); });
      content.addEventListener('mousedown', () => { clear(); timer = setTimeout(() => menu(row, item), 450); });
      for (const event of ['pointerup', 'pointercancel', 'mouseup']) content.addEventListener(event, clear);
      content.addEventListener('contextmenu', e => { e.preventDefault(); menu(row, item); });
    });
    q('.pano-chat').scrollTop = q('.pano-chat').scrollHeight;
  }
  function send() {
    if (!state.draft.trim() || state.generating) return;
    record('sendMessage'); const value = state.draft; conversation().messages.push(message('user', value)); fill('');
    conversation().messages.push(message('assistant', '【本地模拟 · ' + state.models.find(m => m.id === state.model).name + '】\n潮声渐近。你的话语已经记录，故事等待下一步选择。'));
    renderMessages();
  }
  for (const b of D.querySelectorAll('.pano-send,.pano-send-expanded,.chat-send-proxy')) {
    // Keep the expanded send target present between pointer-down and click.
    b.onpointerdown = e => e.preventDefault();
    b.onclick = e => { e.stopPropagation(); send(); };
  }
  function switchConversation(key) { if (!state.conversations.some(c => c.id === key)) return; closeAll(); state.current = key; state.scope.conversationKey = key; fill(''); renderMessages(); record('selectConversation'); }
  function newConversation(prefix) { const key = id(); state.conversations.push({ id: key, title: '新的故事 ' + state.conversations.length, messages: prefix ? prefix.map(m => message(m.role, m.text)) : [message('assistant', '新的故事从这里开始。')] }); switchConversation(key); }
  function conversations() {
    record('openConversationPanel'); const p = popup('conversation-list-scope', '会话记录'), rows = box('conversation-list'), bottom = box('bottom'); p.append(rows, bottom);
    state.conversations.forEach(c => {
      const row = box('conversation-item'), left = box('left-scope'), avatar = box('avatar'); avatar.append(icon('avatar.png')); left.append(avatar);
      const center = box('center-scope'), titleScope = box('title-scope'), title = box('', c.title), preview = box('content-scope', c.messages.at(-1)?.text.slice(0, 60) || '空白会话'); titleScope.append(title); center.append(titleScope, preview); row.append(left, center);
      if (c.id === state.current) row.append(box('cur-conversation', '当前'));
      row.onclick = () => switchConversation(c.id);
      row.append(button('备注', 'edit-icon', () => { const ask = popup('confirm-edit-scope'); ask.append(box('confirm-edit-title', '聊天记录备注')); const input = node('input', 'uni-input-input'); input.value = c.title; input.maxLength = 200;
        ask.append(input, button('取消', 'cancel-btn', () => removePanel(ask)), button('确认', 'ok-btn', () => { c.title = input.value; title.textContent = c.title; removePanel(ask); })); }),
      button('删除', 'delete-icon', () => { if (c.id !== state.current) confirm('conversation', () => { state.conversations = state.conversations.filter(x => x !== c); row.remove(); }); })); rows.append(row);
    }); bottom.append(button('新建会话', 'btn', () => newConversation()));
  }
  function persona() {
    const p = restored.panel('role','.role-profile-modal'); p.replaceChildren(); const header = box('header-box'), modes = box('radio-group'), nameCard = box('card'), gender = box('gender-box'), identityCard = box('card textarea-wrapper');
    header.append(box('page-title', '用户人设'), button('返回', 'icon-back', () => removePanel(p)), button('完成', 'complete-btn', () => { record('submitPersona'); removePanel(p); }));
    for (const label of ['默认', '自定义']) { const r = D.createElement('uni-radio'); const b = button('', 'radio-item', () => { state.persona.mode = label; paint(); }); b.append(node('uni-text', '', label), r); modes.append(b); }
    const input = node('input', 'uni-input-input'); input.type = 'text'; input.maxLength = 30; input.value = state.persona.name; input.oninput = () => state.persona.name = input.value;
    const identity = node('textarea', 'uni-textarea-textarea'); identity.maxLength = 1000; identity.value = state.persona.identity; identity.oninput = () => state.persona.identity = identity.value;
    nameCard.append(box('card-title', '名字'), input); identityCard.append(box('card-title', '身份与经历'), identity);
    for (const label of ['未设定', '女', '男']) gender.append(button(label, 'gender-item', () => { state.persona.gender = label; paint(); }));
    function paint() { for (const b of modes.children) { const r = b.querySelector('uni-radio'); r.replaceChildren(); if (b.querySelector('uni-text').textContent === state.persona.mode) { const svg = D.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('width', '10'); svg.setAttribute('height', '10'); r.append(svg); } }
      for (const b of gender.children) b.classList.toggle('active', b.textContent === state.persona.gender); }
    const fields=box('role-setting');fields.append(modes,nameCard,gender,identityCard);p.append(header,fields);paint();
  }
  function supplement() {
    const p = popup('role-extra-setting'), header = box('header-scope'), card = box('textarea-wrapper'), area = node('textarea', 'uni-textarea-textarea'), setting = box('setting-item');
    const labels = ['开头', '中间', '末尾'], value = box('picker-value', labels[state.supplement.position]);
    header.append(box('page-title', '补充设定'), button('返回', 'icon-back', () => removePanel(p)), button('完成', 'complete-btn', () => { record('submitSupplement'); removePanel(p); }));
    area.maxLength = 1000; area.value = state.supplement.text; area.oninput = () => state.supplement.text = area.value; card.append(area); setting.append(value);
    setting.append(button('调整插入位置', 'picker-field', () => {
      const pick = box('u-transition sim-picker'), wheel = box('uni-picker-view-content'); let selected = state.supplement.position; pick.append(wheel); layers.append(pick);
      const paint = () => [...wheel.children].forEach((b, i) => { b.classList.toggle('u-picker__view__column__item--selected', i === selected); b.style.top = (50 + (i - selected) * 36) + 'px'; });
      labels.forEach((label, i) => wheel.append(button(label, 'u-picker__view__column__item', () => { selected = i; paint(); })));
      pick.append(button('取消', '', () => pick.remove()), button('确定', '', () => { state.supplement.position = selected; value.textContent = labels[selected]; pick.remove(); })); paint();
    })); p.append(header, card, setting);
  }
  function instructions() {
    q('.instruction-bar')?.remove(); q('.shortcut-bar').classList.add('hidden'); const p = box('instruction-bar'), rows = node('uni-scroll-view', 'instruction-scroll');
    p.append(rows, button('返回', 'back-btn', () => { p.remove(); q('.shortcut-bar').classList.remove('hidden'); }));
    state.instructions.forEach(label => rows.append(button(label, 'instruction-chip', () => fill('执行：' + label)))); q('.shortcut-bar-wrapper').append(p);
  }
  function chatSettings() { return restored.chatSettings(); }
  function share() { return restored.share(); }
  function background() { return restored.background(); }
  function customInstructions() { const p = popup('custom-instruction-scope'), header = box('header-scope'), area = node('textarea', ''); header.append(box('title', '自定义指令')); area.value = state.instructions.join('\n'); p.append(header, box('sim-note', '每行一个本地模拟指令。'), area, button('保存', '', () => { state.instructions = area.value.split('\n').filter(Boolean).slice(0, 30); removePanel(p); })); }
  function informational(title, content) { const p = popup('sim-information', title); p.append(box('sim-note', content)); }
  const restored=G.MmdLegacyPanels.create({state,cfg,D,q,box,node,button,layers,popup,removePanel,conversation,fill,newConversation,record,renderMessages});
  const featureRows = [
    ['重置聊天','ico_reset2_dark.png',restored.resetChat],['导出聊天','ico_export_chat_dark.png',restored.exportChat],
    ['新的聊天','ico_rechat2_dark.png',conversations],['编辑角色','ico_edit_role_dark.png',restored.editRole],
    ['更换背景','ico_edit_background_dark.png',background],['自定义指令','ico_instruction_dark.png',customInstructions],
    ['用户人设','ico_user_setting_dark.svg',persona],['设定补充','ico_extra_profile_dark.svg',supplement],
    ['对话设置','ico_chat_set_dark.svg',chatSettings],['剧情总结','ico_summary_dark.png',restored.summary],
    ['游玩教程','ico_chat_help_dark.png',()=>{const previous=location.href;history.replaceState(null,'','/pages/help/help');const p=popup('sim-tutorial','游玩教程');p.append(box('sim-note','在原生页或同层页发消息，使用模型设置调整本地参数。总结、角色编辑与背景仅改变此预览；导出可保存本地聊天。真实模型与账号服务需另行验收。'));const wrap=p.closest('.sim-popup');for(const b of wrap.querySelectorAll('button,.sim-mask'))b.onclick=()=>{history.replaceState(null,'',previous);wrap.remove();};}]
  ];
  q('.more-options-scope .btn-icon').onclick = e => { e.stopPropagation(); const old = q('.more-scope'); if (old) { old.remove();e.currentTarget.textContent='+';q('.more-options-scope').dataset.more='off';return; } e.currentTarget.textContent='−';q('.more-options-scope').dataset.more='on';
    const p = box('more-scope'); p.dataset.open = 'on'; for (const [label, file, fn] of featureRows) { const row = box('item'), image = box('item-icon'); image.append(icon(file)); row.append(image, box('item-title', label)); row.onclick = e => { e.stopPropagation(); fn(); }; p.append(row); } q('.chat-bottom-wapper').append(p); };
  function modelChips() { for (const chip of scope.querySelectorAll('.mind-type')) { chip.replaceChildren(box('current-label', state.models.find(m => m.id === state.model).name), box('icon-change', '⌄')); chip.onclick = modelList; } }
  function modelConfig(key) { return restored.modelConfig(key); }
  function modelList() {
    const p = popup('model-switch-scope', '模型选择'), filters = box('model-filters'), rows = box('model-list'); p.append(filters, rows);
    function paint() { rows.replaceChildren(); for (const m of state.models.filter(m => state.filter === 'all' || m.id === state.filter)) {
      const row = box('model-item' + (m.id === state.model ? ' model-item-active' : ''));
      row.append(box('model-title', m.name), box('model-intro', m.description), box('model-battery', m.cost), box('model-perm', '本地模拟可用'));
      const rate = box('model-success-rate'); rate.append(box('success-badge', '模拟数据')); const settings = icon('ico_setting2_dark.png'); settings.title = '模型设置'; settings.onclick = e => { e.stopPropagation(); modelConfig(m.id); };
      row.append(rate, settings); row.onclick = () => { state.model = m.id; modelChips(); removePanel(p); record('selectModel'); }; rows.append(row);
    } }
    for (const [key, label] of [['all', '全部'], ['a', '叙事'], ['b', '推理']]) filters.append(button(label, 'model-filter-tab' + (state.filter === key ? ' active' : ''), b => { state.filter = key; for (const x of filters.children) x.classList.toggle('active', x === b); paint(); })); paint();
  }
  const bar=q('.shortcut-bar');
  const shortcuts={
    '模型设置':['ico_model_dark.png',()=>modelConfig(state.model)],'对话设置':['ico_chat_set_dark.svg',chatSettings],
    '选择指令':['ico_instruction_dark.png',instructions],'总结剧情':['ico_summary_dark.png',restored.summary],
    '新的聊天':['ico_rechat2_dark.png',restored.newChat],'用户人设':['ico_user_setting_dark.svg',persona]
  };
  for(const b of bar.children){const label=b.textContent.trim(),[file,fn]=shortcuts[label]||[];if(!fn)throw Error('Unwired native shortcut: '+label);const image=box('sb-icon');image.append(icon(file));b.replaceChildren(image,box('sb-text',label));b.onclick=e=>{e.stopPropagation();fn();};}
  const headers = [...q('.header-icon-meun').children];
  const headerRows = [['评论', 'ico_comment_dark.png', restored.comments], ['分享', 'ico_share2_dark.png', share], ['收藏', 'ico_collect_dark.png', () => { state.favorite = !state.favorite; paintHeader(); }], ['刷新', 'ico_refresh2_dark.png', () => { renderMessages(); record('refreshConversation'); }]];
  function paintHeader() { headerRows.forEach(([label, file, fn], i) => { const b = headers[i]; b.title = label; b.setAttribute('aria-label', label); b.replaceChildren(icon(i === 2 && state.favorite ? 'ico_collect_sel_dark.png' : file)); b.onclick = fn; }); }
  q('.ai-assistant').onclick = restored.assist;
  const away = box('sim-away'); away.hidden = true; away.append(box('title', '已离开聊天页'), button('返回聊天', '', () => leave(false))); D.body.append(away);
  function leave(on) { state.scope.roleId = on ? 'outside-preview-role' : cfg.appId; chat.hidden = on; away.hidden = !on; }
  q('.page-header-scope .icon-back').onclick = () => leave(true);
  G.__MMD_PREVIEW__ = Object.freeze({ snapshot: () => structuredClone(state),
    native: () => G.__MMD_SAME_LAYER__?.[cfg.appId]?.hide(), card: () => { leave(false); G.__MMD_SAME_LAYER__?.[cfg.appId]?.show(); },
    leave: () => leave(true), returnToChat: () => leave(false), expandInput: expand,
    setFault: fault => { if (fault === 'disable-send') scope.querySelector('.chat-send-proxy').setAttribute('aria-disabled', 'true'); },
    accuracy: 'local representative simulation; no backend services' });
  paintHeader(); modelChips(); renderMessages();
})(window);
