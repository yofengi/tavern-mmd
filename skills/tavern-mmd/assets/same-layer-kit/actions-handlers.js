/* Original behavior for old-MMD feature groups; no card UI is created here. */
(function (G) {
  'use strict';
  function create(u) {
    const { C, A, document, view, config, pending, capture, target, text, visible, enabled, all, one, unique,
      panel, features, header, shortcut, composer, moreEntry, editor, closeButton, picker, pickerButton } = u;
    const featureAction = { openConversationPanel: 'newChat', openTutorial: 'tutorial', openBackgroundPanel: 'background',
      openCustomInstructions: 'customInstructions', openPersona: 'persona', openSupplement: 'supplement' };
    const closeSelectors = { closeChatSettings: ['chatSettings', '.cs-header-left'], submitChatSettings: ['chatSettings', '.cs-header-right > .confirm-btn'],
      closePersona: ['personaPanel', '.header-box .icon-back'], closeSupplement: ['supplementPanel', '.header-scope .icon-back'] };
    function available(action, s) {
      if (featureAction[action]) return !!panel(features[featureAction[action]][2]) || enabled(moreEntry()) || !!panel('moreMenu');
      if (closeSelectors[action]) { const [key, selector] = closeSelectors[action]; return enabled(one(panel(key), selector)) && (key !== 'supplementPanel' || !picker()); }
      if (['copyMessage', 'deleteMessage', 'rollbackMessage', 'startNewStoryFromMessage', 'regenerateMessage', 'openEditMessage'].includes(action)) {
        const key = { copyMessage: 'copy', deleteMessage: 'delete', rollbackMessage: 'rollback', startNewStoryFromMessage: 'startNewStory', regenerateMessage: 'regenerate', openEditMessage: 'edit' }[action];
        return s.messages.items.some(m => m.capabilities[key]);
      }
      switch (action) {
        case 'setInputText': return s.composer.available;
        case 'exit': return enabled(one(document, '.header-box .icon-back'));
        case 'openComments': return enabled(header('comments'));
        case 'toggleFavorite': return enabled(header('favorite'));
        case 'refreshConversation': return enabled(header('refresh'));
        case 'openSharePanel': return !!panel('sharePanel') || enabled(header('share'));
        case 'copyShareLink': return enabled(one(panel('sharePanel'), '.gen-link-btn'));
        case 'closeSharePanel': return enabled(closeButton(panel('sharePanel')));
        case 'openMoreMenu': return !!panel('moreMenu') || enabled(moreEntry());
        case 'closeMoreMenu': return !!panel('moreMenu') && enabled(moreEntry());
        case 'activateMoreMenuItem': return s.moreMenu.items.some(i => i.available && !i.destructive);
        case 'openChatSettings': return !!panel('chatSettings') || enabled(shortcut('对话设置', 'ico_chat_set_'));
        case 'openPromptSelector': return !!panel('instructionSelector') || enabled(shortcut('选择指令', 'ico_instruction_'));
        case 'closePromptSelector': return enabled(one(panel('instructionSelector'), ':scope > .back-btn'));
        case 'applyInstruction': return s.instructionSelector.open && s.composer.available && s.instructionSelector.instructions.length > 0;
        case 'createConversation': return enabled(one(panel('conversationPanel'), ':scope > .bottom > .btn'));
        case 'closeConversationPanel': return enabled(closeButton(panel('conversationPanel')));
        case 'selectConversation': return s.conversationPanel.conversations.some(x => x.available);
        case 'renameConversation': return s.conversationPanel.conversations.some(x => x.capabilities.rename);
        case 'requestDeleteConversation': return s.conversationPanel.conversations.some(x => x.capabilities.delete);
        case 'deleteConversation': return !!pending.conversation && s.conversationPanel.conversations.some(x => x.capabilities.delete);
        case 'setPersonaName': return s.personaPanel.open && !s.personaPanel.nameDisabled;
        case 'setPersonaIdentity': return s.personaPanel.open && !s.personaPanel.identityDisabled;
        case 'setPersonaMode': return s.personaPanel.modes.some(x => !x.disabled);
        case 'setPersonaGender': return s.personaPanel.genderChoices.some(x => !x.disabled);
        case 'submitPersona': return enabled(one(panel('personaPanel'), '.header-box .complete-btn'));
        case 'setSupplementText': return enabled(one(panel('supplementPanel'), '.textarea-wrapper textarea.uni-textarea-textarea')) && !picker();
        case 'submitSupplement': return enabled(one(panel('supplementPanel'), '.header-scope .complete-btn')) && !picker();
        case 'openSupplementPositionPicker': return enabled(one(panel('supplementPanel'), '.setting-item .picker-field')) && !picker();
        case 'setSupplementPosition': return !!picker() && s.supplementPanel.picker.choices.filter(x => x.selected).length === 1;
        case 'confirmSupplementPosition': return enabled(pickerButton('确定')) && s.supplementPanel.picker.choices.filter(x => x.selected).length === 1;
        case 'cancelSupplementPosition': return enabled(pickerButton('取消'));
        case 'setEditText': case 'applyEditTransform': case 'submitEditMessage': case 'cancelEditMessage':
          return !!pending.edit && pending.edit.expires > Date.now() && panel('editPanel') === pending.edit.panel;
        default: return false;
      }
    }
    function bound(id, kind) { capture(); const value = target(id, kind); return { ...value, id }; }
    function checkBound(value) { capture(); const current = target(value.id, value.kind);
      if (current.el !== value.el || current.signature !== value.signature || current.index !== value.index) C.fail('STALE_TARGET', '目标内容或位置已经改变'); return current; }
    function boundMessage(p) { const item = bound(p.messageId, 'message'); const row = capture().messages.items.find(x => x.id === p.messageId);
      if (!row || !item.content || row.role === 'unknown') C.fail('STALE_TARGET'); return { ...item, row }; }
    function boundConversation(p, capability) {
      const value = bound(p.conversationId, 'conversation'), row = capture().conversationPanel.conversations.find(x => x.id === p.conversationId);
      if (!row?.available || row.fingerprint !== p.fingerprint || row.index !== p.index || (capability && !row.capabilities[capability])) C.fail('STALE_TARGET');
      return { ...value, row };
    }
    const confirmPanels = () => all(document, '.u-popup__content .confirm-scope');
    function confirmDialog(kind) {
      return unique(confirmPanels().filter(p => { const title = text(p.querySelector('.confirm-title')), body = text(p.querySelector('.confirm-content'));
        return kind === 'conversation' ? /删除/.test(title) && /聊天|会话|记录/.test(title + body) :
          kind === 'rollback' ? body.includes('回溯将会删除此消息下方的所有消息') : body.includes('删除后将无法恢复');
      }));
    }
    function issue(key, item, p) {
      const token = C.uuid(); pending[key] = { item, token, expires: Date.now() + 30000, revision: p.revision };
      const prompt = key === 'rollback' ? '回溯会删除目标消息下方的消息，确认继续？' : '确认删除这条消息？删除后无法恢复。';
      return { phase: 'confirmation-required', accepted: false, messageId: p.messageId,
        confirmation: { messageId: p.messageId, confirmationToken: token, prompt } };
    }
    function consume(key, p) {
      const value = pending[key]; pending[key] = null;
      if (!value || value.expires < Date.now() || value.token !== p.confirmationToken || value.item.id !== p.messageId || value.revision !== p.revision) C.fail('CONFIRMATION_EXPIRED');
      checkBound(value.item); return value.item;
    }
    async function run(action, p, op) {
      const { s, check, click, wait, write } = op;
      const result = (phase, data = {}) => ({ phase, ...data });
      async function closeMore() { if (panel('moreMenu')) { click(moreEntry()); await wait(() => !panel('moreMenu')); } }
      async function openMore() { if (!panel('moreMenu')) { click(moreEntry()); await wait(() => panel('moreMenu')); } }
      async function feature(kind, itemId) {
        const definition = features[kind]; if (!definition) C.fail('NOT_AVAILABLE');
        const opened = () => kind === 'tutorial' ? view.location.href.includes('/pages/help/help') : panel(definition[2]);
        if (opened()) return result('opened', { kind });
        await openMore();
        const row = await wait(() => capture().moreMenu.items.find(i => i.kind === kind && (!itemId || i.id === itemId) && i.available && !i.destructive));
        const choices = capture().moreMenu.items.filter(i => i.kind === kind && i.available);
        if (choices.length !== 1) C.fail('STALE_TARGET');
        click(target(row.id, 'more').el); await wait(opened); return result('opened', { kind, itemId: row.id });
      }
      async function messageMenu(item) {
        if (one(document, '.msg-option-scope')) C.fail('NATIVE_PANEL_BUSY', '请先关闭既有消息菜单');
        checkBound(item); check();
        const el = item.content, rect = el.getBoundingClientRect(), init = { bubbles: true, cancelable: true, composed: true,
          button: 0, buttons: 1, clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 };
        if (view.PointerEvent) el.dispatchEvent(new view.PointerEvent('pointerdown', { ...init, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
        el.dispatchEvent(new view.MouseEvent('mousedown', init));
        let menu;
        try { menu = await wait(() => one(document, '.msg-option-scope')); }
        finally {
          // Always release a synthetic press; never issue a click during cancellation.
          if (view.PointerEvent) el.dispatchEvent(new view.PointerEvent('pointerup', { ...init, buttons: 0, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
          el.dispatchEvent(new view.MouseEvent('mouseup', { ...init, buttons: 0 }));
        }
        check(); checkBound(item);
        const options = all(menu, '.msg-options-box > .option-item'), expected = item.row.role === 'assistant' ? ['复制', '删除', '回溯', '开启新的故事'] : ['复制', '删除', '回溯'];
        if (C.canonical(options.map(text)) !== C.canonical(expected)) C.fail('PLATFORM_CHANGED', '消息菜单结构不匹配');
        return { menu, options: Object.fromEntries(options.map(el => [text(el), el])) };
      }
      function editSession() {
        const edit = pending.edit;
        if (!edit || edit.expires < Date.now() || panel('editPanel') !== edit.panel) C.fail('STALE_TARGET', '请重新打开目标消息的编辑界面');
        checkBound(edit.item); edit.expires = Date.now() + 30000; return edit;
      }
      if (featureAction[action]) return feature(featureAction[action]);
      if (closeSelectors[action]) {
        const [key, selector] = closeSelectors[action]; click(one(panel(key), selector)); await wait(() => !panel(key));
        if (['personaPanel', 'supplementPanel'].includes(key)) await closeMore();
        return result(action.startsWith('submit') ? 'submitted' : 'closed');
      }
      switch (action) {
        case 'setInputText': { const el = composer(); write(el, p.text); await wait(() => composer() === el && el.value === p.text); return result('input-observed', { text: p.text }); }
        case 'exit': click(one(document, '.header-box .icon-back')); return result('dispatched');
        case 'openComments': click(header('comments')); return result('dispatched');
        case 'refreshConversation': click(header('refresh')); return result('dispatched');
        case 'toggleFavorite': { const before = s.favorite; click(header('favorite')); await wait(() => capture().navigation.favorite !== before); return result('favorite-observed', { favorite: capture().navigation.favorite }); }
        case 'openSharePanel': if (!panel('sharePanel')) { click(header('share')); await wait(() => panel('sharePanel')); } return result('opened');
        case 'copyShareLink': click(one(panel('sharePanel'), '.gen-link-btn')); return result('dispatched', { link: s.link, clipboard: 'unknown' });
        case 'closeSharePanel': click(closeButton(panel('sharePanel'))); await wait(() => !panel('sharePanel')); return result('closed');
        case 'openMoreMenu': await openMore(); return result('opened');
        case 'closeMoreMenu': await closeMore(); return result('closed');
        case 'activateMoreMenuItem': {
          const row = s.items.find(i => i.id === p.itemId); if (!row?.available || row.destructive) C.fail('NOT_AVAILABLE'); return feature(row.kind, row.id);
        }
        case 'openChatSettings': if (!panel('chatSettings')) { click(shortcut('对话设置', 'ico_chat_set_')); await wait(() => panel('chatSettings')); } return result('opened');
        case 'openPromptSelector': if (!panel('instructionSelector')) { click(shortcut('选择指令', 'ico_instruction_')); await wait(() => panel('instructionSelector')); } return result('opened');
        case 'closePromptSelector': click(one(panel('instructionSelector'), ':scope > .back-btn')); await wait(() => !panel('instructionSelector')); return result('closed');
        case 'applyInstruction': {
          const row = s.instructions.find(x => x.id === p.instructionId);
          if (!row || row.fingerprint !== p.fingerprint || row.label !== p.label || row.index !== p.index) C.fail('STALE_TARGET');
          const input = composer(), before = input.value; click(target(row.id, 'instruction').el);
          await wait(() => composer()?.value.trim() && composer().value !== before);
          return result('input-observed', { instructionId: row.id, text: composer().value });
        }
        case 'selectConversation': {
          const item = boundConversation(p); if (item.row.current) return result('selection-observed', { conversationId: item.id });
          const before = C.canonical(capture().messages.items); click(item.el);
          await wait(() => { const current = capture(); return current.conversationPanel.currentConversationId === item.id || C.canonical(current.messages.items) !== before; });
          return result('conversation-change-observed', { conversationId: item.id });
        }
        case 'createConversation': {
          const before = C.canonical(capture().messages.items); click(one(panel('conversationPanel'), ':scope > .bottom > .btn'));
          await wait(() => !panel('conversationPanel') || C.canonical(capture().messages.items) !== before);
          return result('creation-dispatched');
        }
        case 'closeConversationPanel': click(closeButton(panel('conversationPanel'))); await wait(() => !panel('conversationPanel')); await closeMore(); return result('closed');
        case 'renameConversation': {
          const item = boundConversation(p, 'rename');
          if (all(document, '.confirm-edit-scope').length) C.fail('NATIVE_PANEL_BUSY');
          if (item.row.title === p.title) return result('renamed', { title: p.title });
          click(one(item.el, '.edit-icon'));
          const dialog = await wait(() => one(document, '.confirm-edit-scope'));
          if (text(dialog.querySelector('.confirm-edit-title')) !== '聊天记录备注') C.fail('PLATFORM_CHANGED');
          checkBound(item); const input = one(dialog, 'input.uni-input-input'); write(input, p.title);
          checkBound(item); if (one(document, '.confirm-edit-scope') !== dialog) C.fail('STALE_TARGET'); click(one(dialog, '.ok-btn'));
          await wait(() => { const now = capture().conversationPanel.conversations; return !visible(dialog) && now.some(row => row.id === item.id && row.title === p.title); });
          return result('renamed', { conversationId: item.id, title: p.title });
        }
        case 'requestDeleteConversation': {
          pending.conversation = null; const item = boundConversation(p, 'delete'); if (confirmPanels().length) C.fail('NATIVE_PANEL_BUSY');
          click(one(item.el, '.delete-icon')); const dialog = await wait(() => confirmDialog('conversation')); checkBound(item);
          if (confirmPanels().length !== 1) C.fail('PLATFORM_CHANGED'); const token = C.uuid();
          pending.conversation = { item, dialog, token, expires: Date.now() + 30000, revision: p.revision };
          return result('confirmation-required', { accepted: false, conversationId: item.id,
            confirmation: { conversationId: item.id, fingerprint: p.fingerprint, index: p.index, confirmationToken: token, prompt: '确认删除这条会话？删除后无法恢复。' } });
        }
        case 'deleteConversation': {
          const value = pending.conversation; pending.conversation = null;
          const item = boundConversation(p, 'delete');
          if (!value || value.item.el !== item.el || value.token !== p.confirmationToken || value.expires < Date.now() ||
            value.revision !== p.revision || confirmPanels().length !== 1 || confirmDialog('conversation') !== value.dialog) C.fail('CONFIRMATION_EXPIRED');
          checkBound(value.item); const before = capture().conversationPanel.conversations; click(one(value.dialog, '.confirm-bottom > .ok-btn'));
          const expected = before.filter(x => x.id !== item.id).map(x => x.fingerprint);
          await wait(() => !visible(value.dialog) && C.canonical(capture().conversationPanel.conversations.map(x => x.fingerprint)) === C.canonical(expected));
          return result('deleted', { conversationId: item.id });
        }
        case 'setPersonaMode': case 'setPersonaGender': {
          const mode = action === 'setPersonaMode', rows = mode ? s.modes : s.genderChoices, id = mode ? p.modeId : p.genderId;
          const row = rows.find(x => x.id === id); if (!row || row.disabled || rows.filter(x => x.label === row.label).length !== 1) C.fail('NOT_AVAILABLE');
          if (!row.selected) { click(target(id, mode ? 'mode' : 'gender').el); await wait(() => capture().personaPanel[mode ? 'currentModeId' : 'selectedGenderId'] === id); }
          return result('setting-observed');
        }
        case 'setPersonaName': case 'setPersonaIdentity': {
          const name = action === 'setPersonaName', value = name ? p.name : p.identity;
          const el = one(panel('personaPanel'), name ? '.card input[type="text"]' : '.card.textarea-wrapper textarea');
          write(el, value); await wait(() => el.isConnected && el.value === value); return result('setting-observed');
        }
        case 'submitPersona': {
          const owner = panel('personaPanel'), name = one(owner, '.card input[type="text"]'), identity = one(owner, '.card.textarea-wrapper textarea');
          if (enabled(name)) write(name, p.name); if (enabled(identity)) write(identity, p.identity);
          if (panel('personaPanel') !== owner) C.fail('STALE_TARGET'); click(one(owner, '.header-box .complete-btn'));
          await wait(() => !panel('personaPanel')); await closeMore(); return result('submitted');
        }
        case 'setSupplementText': {
          const el = one(panel('supplementPanel'), '.textarea-wrapper textarea.uni-textarea-textarea'); write(el, p.text);
          await wait(() => el.isConnected && el.value === p.text); return result('setting-observed');
        }
        case 'openSupplementPositionPicker': click(one(panel('supplementPanel'), '.setting-item .picker-field')); await wait(picker); return result('opened');
        case 'setSupplementPosition': {
          const initial = s.picker.choices, desired = initial.findIndex(x => x.id === p.choiceId); if (desired < 0) C.fail('STALE_TARGET');
          for (let step = 0; step <= initial.length; step++) {
            const rows = capture().supplementPanel.picker.choices;
            if (C.canonical(rows.map(x => [x.id, x.label])) !== C.canonical(initial.map(x => [x.id, x.label])) || rows.filter(x => x.selected).length !== 1) C.fail('STALE_TARGET');
            const index = rows.findIndex(x => x.selected); if (index === desired) return result('setting-observed');
            const next = rows[index + Math.sign(desired - index)], selected = target(rows[index].id, 'position').el, el = target(next.id, 'position').el;
            const rect = selected.getBoundingClientRect(), centerY = rect.top + rect.height / 2, dst = el.getBoundingClientRect();
            check(); if (!enabled(el)) C.fail('NOT_AVAILABLE');
            el.dispatchEvent(new view.MouseEvent('click', { bubbles: true, cancelable: true, composed: true, clientX: dst.left + dst.width / 2, clientY: dst.top + dst.height / 2 }));
            await wait(() => { const now = capture().supplementPanel.picker; const r = el.getBoundingClientRect();
              return now.pendingChoiceId === next.id && Math.abs(r.top + r.height / 2 - centerY) < 2; });
          }
          C.fail('TIMEOUT'); break;
        }
        case 'confirmSupplementPosition': { const chosen = s.picker.choices.find(x => x.selected); click(pickerButton('确定'));
          await wait(() => !picker() && capture().supplementPanel.positionLabel === chosen.label); return result('setting-observed'); }
        case 'cancelSupplementPosition': click(pickerButton('取消')); await wait(() => !picker()); return result('closed');
        case 'submitSupplement': {
          const owner = panel('supplementPanel'); write(one(owner, '.textarea-wrapper textarea.uni-textarea-textarea'), p.text);
          if (panel('supplementPanel') !== owner) C.fail('STALE_TARGET'); click(one(owner, '.header-scope .complete-btn'));
          await wait(() => !panel('supplementPanel')); await closeMore(); return result('submitted');
        }
        case 'copyMessage': {
          const item = boundMessage(p); check();
          const value = item.content.innerText || item.content.textContent || '';
          if (!view.navigator.clipboard?.writeText) C.fail('CLIPBOARD_UNAVAILABLE', '浏览器未提供剪贴板权限，请返回原生页面复制');
          await view.navigator.clipboard.writeText(value); check(); return result('copied', { messageId: item.id });
        }
        case 'regenerateMessage': {
          const item = boundMessage(p); if (!item.row.capabilities.regenerate) C.fail('NOT_AVAILABLE');
          const before = item.signature; click(item.buttons.regenerate);
          await wait(() => { const current = capture().messages.items.find(x => x.id === item.id); return !current || target(item.id, 'message').signature !== before; });
          return result('generation-change-observed', { messageId: item.id });
        }
        case 'openEditMessage': {
          const item = boundMessage(p); if (!item.row.capabilities.edit || panel('editPanel')) C.fail('NATIVE_PANEL_BUSY');
          click(item.buttons.edit); const owner = await wait(() => panel('editPanel')); checkBound(item);
          if (!editor(owner)) C.fail('PLATFORM_CHANGED'); pending.edit = { item, messageId: item.id, panel: owner, expires: Date.now() + 30000 };
          return result('opened', { messageId: item.id });
        }
        case 'setEditText': { const edit = editSession(); write(editor(edit.panel), p.text); return result('text-observed'); }
        case 'applyEditTransform': { const edit = editSession(), el = target(p.transformId, 'transform').el;
          if (!edit.panel.contains(el)) C.fail('STALE_TARGET'); click(el); await Promise.resolve(); check(); editSession(); return result('transform-dispatched'); }
        case 'cancelEditMessage': { const edit = editSession(); pending.edit = null; click(edit.panel); await wait(() => !visible(edit.panel)); return result('closed'); }
        case 'submitEditMessage': {
          const edit = editSession(); if (edit.messageId !== p.messageId) C.fail('STALE_TARGET');
          write(editor(edit.panel), p.text); checkBound(edit.item);
          if (panel('editPanel') !== edit.panel) C.fail('STALE_TARGET'); pending.edit = null; click(one(edit.panel, '.modify-btn-box > .modify-btn'));
          await wait(() => !visible(edit.panel) && edit.item.el.isConnected && (edit.item.content.innerText || '').trim() === p.text.trim());
          return result('edit-observed', { messageId: p.messageId });
        }
        case 'deleteMessage': case 'rollbackMessage': {
          const key = action === 'deleteMessage' ? 'deletion' : 'rollback';
          if (!p.confirmationToken) return issue(key, boundMessage(p), p);
          const item = consume(key, p); if (confirmPanels().length) C.fail('NATIVE_PANEL_BUSY');
          const before = capture().messages.items, menu = await messageMenu(item); checkBound(item);
          click(menu.options[key === 'deletion' ? '删除' : '回溯']);
          if (key === 'deletion') {
            await wait(() => !item.el.isConnected || confirmDialog('message'));
            const dialog = confirmDialog('message');
            if (dialog) { if (confirmPanels().length !== 1) C.fail('PLATFORM_CHANGED'); checkBound(item); click(one(dialog, '.confirm-bottom > .ok-btn')); }
          } else {
            const dialog = await wait(() => confirmDialog('rollback')); if (confirmPanels().length !== 1) C.fail('PLATFORM_CHANGED');
            checkBound(item); click(one(dialog, '.confirm-bottom > .ok-btn'));
          }
          const expected = (key === 'deletion' ? before.filter(x => x.id !== item.id) : before.filter(x => x.index <= item.index)).map(x => [x.id, x.fingerprint]);
          await wait(() => C.canonical(capture().messages.items.map(x => [x.id, x.fingerprint])) === C.canonical(expected));
          return result(key === 'deletion' ? 'deleted' : 'rollback-observed', { messageId: item.id });
        }
        case 'startNewStoryFromMessage': {
          const item = boundMessage(p); if (item.row.role !== 'assistant') C.fail('NOT_AVAILABLE');
          const expected = capture().messages.items.filter(x => x.index <= item.index).map(x => [x.role, x.text]);
          const oldIds = capture().messages.items.map(x => x.id), menu = await messageMenu(item); click(menu.options['开启新的故事']);
          await wait(() => { const rows = capture().messages.items; return C.canonical(rows.map(x => [x.role, x.text])) === C.canonical(expected) && rows.some(x => !oldIds.includes(x.id)); });
          return result('story-change-observed', { messageId: item.id });
        }
        default: C.fail('NOT_AVAILABLE');
      }
    }
    return { available, run };
  }
  G.MmdSameLayerActionHandlers = Object.freeze({ create });
})(globalThis);
