/* Original, text-only feature views. Host actions and payloads stay explicit. */
(function (G) {
  'use strict';
  const definitions = {
    conversations: ['会话记录', 'conversationPanel', 'openConversationPanel', 'closeConversationPanel'],
    persona: ['我的人设', 'personaPanel', 'openPersona', 'closePersona'],
    supplement: ['补充设定', 'supplementPanel', 'openSupplement', 'closeSupplement'],
    instructions: ['选择指令', 'instructionSelector', 'openPromptSelector', 'closePromptSelector'],
    settings: ['对话设置', 'chatSettings', 'openChatSettings', 'closeChatSettings'],
    sharing: ['分享对话', 'sharePanel', 'openSharePanel', 'closeSharePanel'],
    more: ['更多原生功能', 'moreMenu', 'openMoreMenu', 'closeMoreMenu'],
    edit: ['编辑消息', 'editPanel', 'openEditMessage', 'cancelEditMessage']
  };
  const ref = row => ({ conversationId: row.id, fingerprint: row.fingerprint, index: row.index });
  function render(kind, u) {
    const { data: s, add, el, button, field, run, draft, confirm, prompt, openResult, native } = u;
    const rev = extra => ({ revision: s.revision, ...extra });
    const control = (label, action, payload = {}, after, disabled = false) => button(label, action, () => run(action, rev(typeof payload === 'function' ? payload() : payload), after), disabled);
    if (kind === 'conversations') {
      add(el('p', 'muted', '会话列表来自当前 MMD。切换后会重新读取对应的对话与游戏进度。'));
      for (const row of s.conversations) {
        const card = el('section', 'sl-card'); card.append(el('h3', '', row.title || '未命名会话'), el('p', 'muted', row.preview));
        if (row.current) card.append(el('span', 'sl-badge', '当前会话'));
        const actions = el('div', 'actions');
        actions.append(control('进入会话', 'selectConversation', ref(row), () => u.closeLocal(), !row.available || row.current));
        actions.append(button('修改备注', 'renameConversation', () => prompt('修改会话备注', row.title, title => run('renameConversation', rev({ ...ref(row), title }))), !row.capabilities.rename));
        actions.append(button('删除会话', 'requestDeleteConversation', () => confirm('删除这份会话？', (row.title || '未命名会话') + '\n删除后无法恢复。', () => u.removeConversation(rev(ref(row)))), !row.capabilities.delete || row.current));
        card.append(actions); add(card);
      }
      add(control('开始新会话', 'createConversation', {}, () => u.closeLocal()));
    } else if (kind === 'persona') {
      add(el('p', 'muted', s.restriction || '填写你的名字与身份，再提交给 MMD。'));
      const modes = el('div', 'actions');
      for (const row of s.modes) { const b = control(row.label, 'setPersonaMode', { modeId: row.id }, null, row.disabled); b.setAttribute('aria-pressed', String(row.selected)); modes.append(b); } add(modes);
      add(field('name', '名字', s.name, s.maxLength, s.nameDisabled));
      add(control('同步名字', 'setPersonaName', () => ({ name: draft('name', s.name) }), null, s.nameDisabled));
      const genders = el('div', 'actions');
      for (const row of s.genderChoices) { const b = control(row.label, 'setPersonaGender', { genderId: row.id }, null, row.disabled); b.setAttribute('aria-pressed', String(row.selected)); genders.append(b); } add(genders);
      add(field('identity', '身份与经历', s.identity, s.identityMaxLength, s.identityDisabled, true));
      add(control('同步身份', 'setPersonaIdentity', () => ({ identity: draft('identity', s.identity) }), null, s.identityDisabled));
      add(control('提交人设', 'submitPersona', () => ({ name: draft('name', s.name), identity: draft('identity', s.identity) }), () => u.closeLocal()));
    } else if (kind === 'supplement') {
      add(field('text', '补充内容', s.text, s.maxLength, s.picker.open, true));
      add(control('同步草稿', 'setSupplementText', () => ({ text: draft('text', s.text) })));
      add(el('p', 'muted', '插入位置：' + (s.positionLabel || '尚未读取')));
      if (s.picker.open) {
        const choices = el('div', 'actions');
        for (const row of s.picker.choices) { const b = control(row.label, 'setSupplementPosition', { choiceId: row.id }, null, row.disabled); b.setAttribute('aria-pressed', String(row.selected)); choices.append(b); } add(choices);
        add(control('确认位置', 'confirmSupplementPosition'), control('取消选位', 'cancelSupplementPosition'));
      } else add(control('调整插入位置', 'openSupplementPositionPicker'));
      add(control('提交补充设定', 'submitSupplement', () => ({ text: draft('text', s.text) }), () => u.closeLocal()));
    } else if (kind === 'instructions') {
      add(el('p', 'muted', '选择后填入输入框，由你确认发送。现有草稿会先询问是否替换。'));
      if (!s.instructions.length) add(el('p', '', '当前没有可用指令。'));
      for (const row of s.instructions) add(button(row.label, 'applyInstruction', () => {
        const apply = () => run('applyInstruction', rev({ instructionId: row.id, fingerprint: row.fingerprint, label: row.label, index: row.index }), result => {
          if (typeof result.data?.text === 'string') document.getElementById('text').value = result.data.text;
          else u.say('指令已交给 MMD。当前桥接未返回内容，请回原生页核对。');
        });
        if (document.getElementById('text').value.trim() || u.nativeDraft() == null || u.nativeDraft().trim()) confirm('替换输入框草稿？', '这会把所选指令填入输入框，尚不会发送。', apply); else apply();
      }));
    } else if (kind === 'settings') {
      add(el('p', 'muted', '这里展示已读取的设置。当前桥接没有逐项修改接口，调整选项请前往 MMD。'));
      if (!s.controls.length) add(el('p', '', '当前未读取到设置项。'));
      for (const row of s.controls) { const card = el('section', 'sl-card'); card.append(el('h3', '', row.label), el('p', 'muted', row.description));
        const choice = row.options.find(x => x.id === row.selectedOptionId || x.selected);
        card.append(el('p', '', choice?.label || '尚未确认当前选项')); add(card); }
      add(button('前往 MMD 调整', null, native), control('提交当前设置', 'submitChatSettings', {}, () => u.closeLocal()));
    } else if (kind === 'sharing') {
      add(el('p', '', s.subtitle || '使用 MMD 的分享功能。'), el('p', 'sl-share-link', s.link || '链接尚未生成。'));
      add(control('生成 / 复制分享链接', 'copyShareLink'));
      add(el('p', 'muted', '复制动作交由 MMD 执行；请检查系统剪贴板是否成功。'));
    } else if (kind === 'more') {
      add(el('p', 'muted', '只显示桥接已识别的入口。背景与自定义指令会打开原生页面。'));
      for (const row of s.items) add(control(row.label, 'activateMoreMenuItem', { itemId: row.id }, result => openResult(result.data?.kind || row.kind), !row.available || row.destructive));
      add(control('打开背景设置', 'openBackgroundPanel', {}, native), control('打开自定义指令', 'openCustomInstructions', {}, native), control('打开使用教程', 'openTutorial', {}, native));
    } else if (kind === 'edit') {
      add(field('text', '消息内容', s.text, 100000, false, true));
      add(control('同步编辑草稿', 'setEditText', () => ({ text: draft('text', s.text) })));
      for (const row of s.transforms) add(button(row.label, 'applyEditTransform', () => {
        const apply = () => run('applyEditTransform', rev({ transformId: row.id }), () => u.resetDraft());
        if (u.dirty()) confirm('使用“' + row.label + '”？', '该操作处理 MMD 中的内容。未同步的本地草稿会被结果替换。', apply); else apply();
      }, row.disabled));
      add(control('保存消息', 'submitEditMessage', () => ({ messageId: s.messageId, text: draft('text', s.text) }), () => u.closeLocal()));
    }
  }
  G.MmdSameLayerPanels = Object.freeze({ definitions, render });
})(globalThis);
