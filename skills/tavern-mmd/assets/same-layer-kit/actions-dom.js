/* Original native feature reader. Selectors describe observed old-MMD structures. */
(function (G) {
  'use strict';
  const C = G.MmdSameLayerCore, A = G.MmdSameLayerActions;
  const panels = { editPanel: '.msg-modify-scope', sharePanel: '.u-popup .share-popup', moreMenu: '.more-scope',
    conversationPanel: '.conversation-list-scope', personaPanel: '.role-profile-modal', supplementPanel: '.role-extra-setting',
    instructionSelector: '.shortcut-bar-wrapper > .instruction-bar', chatSettings: '.conv-style-modal',
    backgroundPanel: '.modify-scope', customInstructionsPanel: '.custom-instruction-scope' };
  const features = Object.freeze({ newChat: ['新的聊天', 'ico_rechat2_dark.png', 'conversationPanel'],
    background: ['更换背景', 'ico_edit_background_dark.png', 'backgroundPanel'],
    customInstructions: ['自定义指令', 'ico_instruction_dark.png', 'customInstructionsPanel'],
    persona: ['用户人设', 'ico_user_setting_dark.svg', 'personaPanel'], supplement: ['设定补充', 'ico_extra_profile_dark.svg', 'supplementPanel'],
    chatSettings: ['对话设置', 'ico_chat_set_dark.svg', 'chatSettings'], tutorial: ['游玩教程', 'ico_chat_help_dark.png', 'tutorial'] });
  function dom(document, config = {}) {
    const view = document.defaultView, revisions = A.revisions(), ids = new WeakMap();
    let refs = new Map(), bindings = {}, state = {}, controller = null, stopped = false;
    const pending = { edit: null, deletion: null, rollback: null, conversation: null };
    const text = e => (e?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 6000);
    const visible = e => !!(e?.isConnected && e.getClientRects().length && !e.closest('[hidden]') &&
      !['none'].includes(view.getComputedStyle(e).display) && view.getComputedStyle(e).visibility !== 'hidden' && view.getComputedStyle(e).opacity !== '0');
    const enabled = e => visible(e) && !e.disabled && !e.readOnly && !e.hasAttribute('disabled') && !e.classList.contains('disabled') &&
      e.getAttribute('aria-disabled') !== 'true' && view.getComputedStyle(e).pointerEvents !== 'none';
    const all = (root, selector) => [...(root?.querySelectorAll(selector) || [])].filter(visible);
    const unique = rows => rows.length === 1 ? rows[0] : null;
    const one = (root, selector) => unique(all(root, selector));
    const panel = key => {
      if (!panels[key]) return null;
      const body = one(document, panels[key]);
      return key === 'supplementPanel' ? body?.closest('.u-popup__content') || body : body;
    };
    function mark(el) { if (!el) return ''; if (!ids.has(el)) ids.set(el, C.uuid()); return ids.get(el); }
    function fingerprint(value) { let h = 2166136261; for (const char of value) { h ^= char.codePointAt(0); h = Math.imul(h, 16777619); } return (h >>> 0).toString(36); }
    function bind(el, kind, data = {}) { const id = mark(el); refs.set(id, { el, kind, ...data }); return id; }
    function src(el) { return el?.getAttribute('src') || ''; }
    function option(el, kind, selected = el.classList.contains('active')) {
      return { id: bind(el, kind), label: text(el), selected, disabled: !enabled(el), available: enabled(el) };
    }
    function header(kind) {
      const scope = one(document, '.topTabbar > .header-icon-meun'), buttons = all(scope, ':scope > .header-meun');
      if (buttons.length !== 4) return null;
      const patterns = { comments: /ico_comment_dark\.png|^(评论|评论区|comments?)$/, share: /ico_share2_dark\.png|^(分享|share)$/,
        favorite: /ico_collect(?:_sel)?_dark\.png|^(收藏|已收藏|favorite|collect)$/, refresh: /ico_refresh2_dark\.png|^(刷新|刷新对话|同步|refresh|reload|sync)$/ };
      const result = {};
      for (const button of buttons) {
        const tokens = [text(button), button.getAttribute('aria-label') || '', button.getAttribute('title') || '', ...all(button, 'img').map(src)];
        const matches = Object.keys(patterns).filter(key => tokens.some(token => patterns[key].test(token)));
        if (matches.length !== 1 || result[matches[0]]) return null;
        result[matches[0]] = button;
      }
      return result[kind] || null;
    }
    function shortcut(label, icon) {
      const bar = one(document, '.shortcut-bar-wrapper > .shortcut-bar'), buttons = all(bar, ':scope > .shortcut-btn');
      return [5, 6].includes(buttons.length) ? unique(buttons.filter(e => text(e.querySelector('.sb-text')) === label && src(e.querySelector('.sb-icon img')).includes(icon))) : null;
    }
    function messageButtons(item) {
      const groups = all(item, '.modify-btn-scope').map(scope => {
        const buttons = all(scope, ':scope > .modify-btn'); if (![2, 3].includes(buttons.length)) return null;
        const result = {}; let structural = false;
        const expected = buttons.length === 3 ? ['regenerate', 'edit'] : ['edit'];
        const dimensions = { regenerate: '80x81', edit: '56x57', copy: '200x200' };
        function size(button) { const img = unique(all(button, 'img')); return img ? (img.naturalWidth || img.width) + 'x' + (img.naturalHeight || img.height) : ''; }
        for (const button of buttons) {
          const hint = [text(button), button.getAttribute('aria-label') || '', button.getAttribute('title') || '', ...all(button, 'img').map(e => /^data:/.test(src(e)) ? '' : src(e))].join(' ').toLowerCase();
          let found = [['regenerate', /重新生成|重新回复|重生成|regenerate|retry|refresh|reload/], ['edit', /编辑|修改|edit|modify|pencil/], ['copy', /复制|拷贝|copy|clipboard/], ['share', /分享|share/]].filter(([, re]) => re.test(hint)).map(([key]) => key);
          if (!found.length) { structural = true; found = Object.keys(dimensions).filter(key => dimensions[key] === size(button)); }
          if (found.length !== 1 || result[found[0]]) return null; result[found[0]] = button;
        }
        if (!expected.every(key => result[key]) || !!result.copy === !!result.share || (structural && ![...expected,'copy'].every(key => result[key] && size(result[key]) === dimensions[key]))) return null;
        return result;
      }).filter(Boolean);
      return unique(groups) || {};
    }
    const composer = () => G.MmdSameLayerInput.resolve(document).input;
    const moreEntry = () => one(one(document, '.more-options-scope'), '.btn-icon');
    const editor = p => one(p, '#vditor .vditor-ir > pre.vditor-reset[contenteditable="true"]');
    const closeButton = p => one(p?.closest('.u-popup__content') || p?.parentElement, '.u-popup__content__close');
    const picker = () => { const c = one(document, '.uni-picker-view-content'); return c?.closest('.u-transition') || c?.closest('.u-popup__content') || c?.parentElement || null; };
    const pickerButton = label => unique(all(picker(), '*').filter(e => !e.children.length && text(e) === label));
    function capture() {
      refs = new Map(); bindings = {}; const data = {};
      const input = composer(); data.composer = { text: input?.value || '', readable: !!input, available: enabled(input) }; bindings.composer = mark(input);
      data.navigation = { favorite: header('favorite') ? !!header('favorite').querySelector('img[src*="ico_collect_sel_dark.png"]') : null, evidence: header('favorite') ? 'native-icon' : 'unknown' };
      bindings.navigation = ['comments', 'share', 'favorite', 'refresh'].map(k => mark(header(k)));
      const items = all(one(document, '#msglistview'), '.item.Ai, .item.self');
      data.messages = { items: items.slice(-100).map((el, offset) => {
        const role = el.classList.contains('Ai') && !el.classList.contains('self') ? 'assistant' : el.classList.contains('self') ? 'user' : 'unknown';
        const content = one(el, role === 'assistant' ? '.content.left' : '.content.right'), buttons = role === 'assistant' ? messageButtons(el) : {};
        const sig = [role, content?.id, content?.innerHTML]; const index = items.length - Math.min(items.length, 100) + offset;
        const id = bind(el, 'message', { content, buttons, signature: C.canonical(sig), index });
        return { id, index, role, text: (content?.innerText || content?.textContent || '').slice(0, 6000), fingerprint: fingerprint(C.canonical(sig)),
          capabilities: { copy: !!content, edit: enabled(buttons.edit), delete: !!content && role !== 'unknown',
            regenerate: index === items.length - 1 && enabled(buttons.regenerate), rollback: !!content && role !== 'unknown', startNewStory: !!content && role === 'assistant' } };
      }) }; bindings.messages = items.map(el => [mark(el), el.querySelector('.content')?.innerHTML || '']);
      for (const [key, selector] of Object.entries(panels)) { const p = one(document, selector); data[key] = { open: !!p }; bindings[key] = mark(p); }
      let p = panel('editPanel');
      Object.assign(data.editPanel, { messageId: pending.edit?.messageId || '', text: editor(p)?.innerText || '',
        transforms: all(p, '.option-box > .option-item').map(el => option(el, 'transform')) });
      p = panel('sharePanel'); Object.assign(data.sharePanel, { title: text(p?.querySelector('.share-title')), subtitle: text(p?.querySelector('.share-sub-title')),
        link: text(p?.querySelector('.share-sub-title')) });
      p = panel('moreMenu'); data.moreMenu.items = all(p, ':scope > .item').map(el => {
        const label = text(el.querySelector('.item-title')), icon = src(el.querySelector('.item-icon img'));
        const kind = Object.keys(features).find(k => label === features[k][0] && icon.split(/[?#]/)[0].endsWith('/' + features[k][1])) || 'unknown';
        return { id: bind(el, 'more'), label, icon: icon.split('/').pop().split(/[?#]/)[0], kind,
          available: kind !== 'unknown' && enabled(el), destructive: label === '重置聊天' || icon.includes('ico_reset2_dark.png') };
      });
      p = panel('conversationPanel'); data.conversationPanel.title = text(p?.querySelector(':scope > .title'));
      data.conversationPanel.conversations = all(p, '.conversation-list .conversation-item').map((el, index) => {
        const title = text(el.querySelector('.center-scope .title-scope > uni-view:first-child'));
        const preview = text(el.querySelector('.center-scope .content-scope')), avatar = src(el.querySelector('.left-scope .avatar img'));
        const signature = C.canonical([title, preview, avatar]), current = !!el.querySelector('.cur-conversation');
        return { id: bind(el, 'conversation', { signature, index }), fingerprint: fingerprint(signature), index, title, preview, current, available: enabled(el),
          capabilities: { rename: enabled(one(el, '.edit-icon')), delete: !current && enabled(one(el, '.delete-icon')) } };
      });
      for (const item of data.conversationPanel.conversations) if (data.conversationPanel.conversations.filter(x => x.fingerprint === item.fingerprint).length !== 1) {
        item.available = false; item.capabilities = { rename: false, delete: false };
      }
      data.conversationPanel.currentConversationId = data.conversationPanel.conversations.find(x => x.current)?.id || '';
      p = panel('personaPanel'); const name = one(p, '.card input[type="text"]'), identity = one(p, '.card.textarea-wrapper textarea');
      Object.assign(data.personaPanel, { title: text(p?.querySelector('.header-box .page-title')),
        modes: all(p, '.radio-group > .radio-item').map(el => ({ ...option(el, 'mode', !!el.querySelector('uni-radio svg')),
          label: text(el.querySelector('uni-text')), disabled: !enabled(el) || !!el.querySelector('uni-radio[disabled]') })),
        genderChoices: all(p, '.gender-box > .gender-item').map(el => option(el, 'gender')),
        name: name?.value || '', maxLength: name?.maxLength || 0, nameDisabled: !enabled(name),
        identity: identity?.value || '', identityMaxLength: identity?.maxLength || 0, identityDisabled: !enabled(identity), restriction: text(p?.querySelector('.forbidden-tag .tag-text')) });
      data.personaPanel.currentModeId = data.personaPanel.modes.find(x => x.selected)?.id || '';
      data.personaPanel.selectedGenderId = data.personaPanel.genderChoices.find(x => x.selected)?.id || '';
      p = panel('supplementPanel'); const area = one(p, '.textarea-wrapper textarea.uni-textarea-textarea');
      const pick = picker(), choices = all(pick, '.u-picker__view__column__item').map(el => option(el, 'position', el.classList.contains('u-picker__view__column__item--selected')));
      Object.assign(data.supplementPanel, { title: text(p?.querySelector('.header-scope .page-title')), text: area?.value || '', maxLength: area?.maxLength || 0,
        positionLabel: text(p?.querySelector('.setting-item .picker-value')), positionId: '', picker: { open: !!pick, choices, pendingChoiceId: choices.find(x => x.selected)?.id || '' } });
      bindings.supplementPanel = [bindings.supplementPanel, mark(pick), ...choices.map(x => x.id)];
      p = panel('instructionSelector');
      data.instructionSelector.instructions = all(p, '.instruction-scroll .instruction-chip').filter(el => text(el)).map((el, index) => {
        const attrs = [...el.attributes].filter(a => !['class', 'style'].includes(a.name)).map(a => [a.name, a.value]).sort();
        return { id: bind(el, 'instruction'), label: text(el), index, fingerprint: fingerprint(C.canonical([text(el), attrs])) };
      }); data.instructionSelector.empty = !data.instructionSelector.instructions.length;
      p = panel('chatSettings'); data.chatSettings.title = text(p?.querySelector('.cs-header-title'));
      data.chatSettings.controls = all(p, '.outer-scroll-view .cs-group-card').map(el => {
        const options = all(el, '.cs-style-grid > .cs-style-item:not(.fixed-item)').map(e => option(e, 'chat-option'));
        return { id: mark(el), label: text(el.querySelector('.cs-section-title')), description: text(el.querySelector('.cs-section-subtitle')),
          options, selectedOptionId: options.find(x => x.selected)?.id || '', collapsed: el.classList.contains('collapsed') };
      }); data.chatSettings.empty = !data.chatSettings.controls.length;
      data.backgroundPanel.title = text(panel('backgroundPanel')?.querySelector('.modify-title'));
      data.customInstructionsPanel.title = text(panel('customInstructionsPanel')?.querySelector('.header-scope .title'));
      state = Object.fromEntries(Object.entries(data).map(([key, value]) => [key, revisions.stamp(key, value, bindings[key])]));
      return state;
    }
    function target(id, kind) { const row = refs.get(id); if (!row || row.kind !== kind || !row.el.isConnected) C.fail('STALE_TARGET'); return row; }
    function needView(action, payload) { const current = capture()[A.groupFor[action]]; if (!A.rootActions.has(action) && payload.revision !== current.revision) C.fail('STALE_VIEW', '界面数据已变化，请重新读取'); return current; }
    const handlers = G.MmdSameLayerActionHandlers.create({ C, A, document, view, config, pending, capture, target,
      text, visible, enabled, all, one, unique, mark, panel, panels, features, header, shortcut, composer, moreEntry, editor, closeButton, picker, pickerButton });
    function capabilities() {
      const s = capture(); return Object.fromEntries(A.actions.map(action => [action, { available: !stopped && !controller && handlers.available(action, s),
        reason: '需要对应原生入口、最新目标与有效面板；确认阶段不会自动完成删除' }]));
    }
    function cancel() { controller?.abort(); controller = null; revisions.clear(); for (const key of Object.keys(pending)) pending[key] = null; }
    return { snapshot: () => ({ enabled: true, ...capture() }), capabilities,
      async invoke(action, payload = {}, options = {}) {
        A.validate(action, payload); options.check?.();
        if (stopped || controller) C.fail('NOT_AVAILABLE');
        const s = needView(action, payload); if (!handlers.available(action, state)) C.fail('NOT_AVAILABLE');
        const run = new AbortController(); controller = run;
        const check = () => { if (stopped || run.signal.aborted) C.fail('CONTEXT_CHANGED'); options.check?.(); };
        const click = el => { check(); if (!enabled(el)) C.fail('NOT_AVAILABLE', '原生目标不可操作');
          for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
            check(); if (!el.isConnected) C.fail('STALE_TARGET'); const E = type.startsWith('pointer') && view.PointerEvent || view.MouseEvent;
            el.dispatchEvent(new E(type, { bubbles: true, cancelable: true, composed: true, button: 0 }));
          }
        };
        const wait = async (predicate, timeout = config.actionTimeoutMs || 8000) => {
          const end = Date.now() + timeout;
          do { check(); const value = predicate(); if (value) return value;
            await new Promise(resolve => { const done = () => { clearTimeout(timer); run.signal.removeEventListener('abort', done); resolve(); };
              const timer = setTimeout(done, 30); run.signal.addEventListener('abort', done, { once: true }); });
          } while (Date.now() < end);
          check(); C.fail('TIMEOUT', '原生动作已发出，但未能确认结果；不会自动重试');
        };
        const write = (el, value) => { check(); if (!enabled(el)) C.fail('NOT_AVAILABLE');
          if (el.maxLength > 0 && value.length > el.maxLength) C.fail('INVALID_ARGUMENT', '输入超过原生字段长度');
          if (el.isContentEditable) {
            el.innerText = value;
            // Vditor's input handler reads the current Range even for a DOM write.
            // A card iframe may have focus, leaving the host with no selection.
            const selection = view.getSelection();
            if (selection) { const range = document.createRange(); range.selectNodeContents(el); range.collapse(false); selection.removeAllRanges(); selection.addRange(range); }
          }
          else { const type = el instanceof view.HTMLTextAreaElement ? view.HTMLTextAreaElement : view.HTMLInputElement;
            Object.getOwnPropertyDescriptor(type.prototype, 'value').set.call(el, value); }
          el.dispatchEvent(new view.Event('input', { bubbles: true, composed: true }));
          check(); if (!el.isConnected) C.fail('STALE_TARGET'); el.dispatchEvent(new view.Event('change', { bubbles: true, composed: true }));
        };
        try { const data = await handlers.run(action, payload, { s, check, click, wait, write }); check();
          return { ok: true, action, accepted: data.accepted !== false, completed: 'unknown', persisted: 'unknown', data };
        } finally { if (controller === run) controller = null; }
      }, cancel, destroy() { stopped = true; cancel(); } };
  }
  G.MmdSameLayerActionDOM = Object.freeze({ dom });
})(globalThis);
