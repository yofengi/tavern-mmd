/* Frame-only composition: no parent DOM, native HTML, or unbounded action dispatch. */
(function (G) {
  'use strict';
  function mount({ call, act, say }) {
    const $ = id => document.getElementById(id), P = G.MmdSameLayerPanels;
    const enabled = key => G.MmdSameLayerUIConfig?.modules?.[key] !== false;
    const el = (tag, cls = '', text = '') => { const n = document.createElement(tag); n.className = cls; n.textContent = text; return n; };
    let state = null, busy = false, view = null, own = false, dead = false, confirmation = null;
    const dialog = el('dialog', 'sl-feature-dialog'); dialog.id = 'features-dialog';
    const heading = el('h2'), info = el('p', 'muted'), body = el('div', 'sl-feature-body'), footer = el('div', 'actions');
    heading.id = 'features-title'; dialog.setAttribute('aria-labelledby', heading.id); info.id = 'features-notice'; info.setAttribute('role', 'status');
    const btn = (label, handler, id) => { const b = el('button', 'secondary', label); b.type = 'button'; if (id) b.id = id; b.onclick = handler; return b; };
    const native = () => { if (!busy) call('ui.native').catch(e => say(e.message)); };
    const close = btn('关闭', closePanel, 'features-close'), reload = btn('重新读取', () => {
      const read = () => execute(async () => { await call('snapshot'); refreshView(false); });
      if (view?.dirty) confirm('重新读取并丢弃草稿？', '当前未提交的本地输入将替换为 MMD 中的内容。', read); else read();
    }, 'features-reload');
    const back = btn('返回 MMD', native, 'features-native');
    footer.append(reload, close, back); dialog.append(heading, info, body, footer); document.body.append(dialog);
    const question = el('dialog', 'sl-question'); question.id = 'features-confirm';
    const qTitle = el('h2'), qText = el('p', 'sl-confirm-text'), qInput = el('input'), qActions = el('div', 'actions');
    qTitle.id = 'features-confirm-title'; question.setAttribute('aria-labelledby', qTitle.id); qInput.id = 'features-answer'; qInput.maxLength = 200; qInput.setAttribute('aria-label', '会话备注');
    const yes = btn('确认', () => { const task = confirmation; confirmation = null; question.close(); task?.(qInput.value); }, 'features-confirm-yes');
    const no = btn('取消', () => { confirmation = null; question.close(); }, 'features-confirm-no');
    qActions.append(no, yes); question.append(qTitle, qText, qInput, qActions); document.body.append(question);
    question.addEventListener('cancel', () => { confirmation = null; });
    function confirm(title, text, fn, initial) {
      if (busy || question.open) return;
      qTitle.textContent = title; qText.textContent = text; qInput.hidden = initial === undefined; qInput.value = initial || '';
      confirmation = fn; question.showModal(); (initial === undefined ? no : qInput).focus();
    }
    function prompt(title, initial, fn) { confirm(title, '只修改会话列表中的备注。', fn, initial); }
    function closeLocal() { dialog.close(); view = null; }
    function closePanel() {
      if (busy || !view) return;
      const task = () => execute(async () => {
        const current = state.actions?.[P.definitions[view.kind][1]];
        if (view.kind === 'supplement' && current?.picker?.open) {
          await invoke('cancelSupplementPosition', { revision: current.revision });
        }
        const latest = state.actions?.[P.definitions[view.kind][1]];
        if (latest?.open) await invoke(P.definitions[view.kind][3], { revision: latest.revision });
        closeLocal();
      });
      if (view.dirty) confirm('关闭并放弃本地草稿？', '已经同步到 MMD 的内容由原生页面处理。', task); else task();
    }
    dialog.addEventListener('cancel', e => { e.preventDefault(); closePanel(); });
    async function invoke(action, payload = {}) {
      const result = await call('native.invoke', { action, payload });
      if (result.data?.phase === 'confirmation-required') return result;
      const message = result.data?.phase === 'submitted' ? '已提交给 MMD，请以原生页面的最终状态为准。' : '操作已返回，显示内容已重新读取。';
      say(message); return result;
    }
    function execute(fn) {
      if (busy || dead) return;
      own = true;
      return act(async () => {
        try { await fn(); }
        catch (e) { await call('snapshot').catch(() => {}); info.textContent = e.message; throw e; }
        finally { own = false; }
      });
    }
    function run(action, payload = {}, after) {
      if (view?.stale) { say('MMD 内容已变化，请先重新读取。草稿仍保留在当前表单。'); return; }
      return execute(async () => { const result = await invoke(action, payload); after?.(result); if (view) refreshView(true); });
    }
    function refreshView(keepDraft) {
      if (!view) return;
      const data = state.actions?.[P.definitions[view.kind][1]];
      if (!data?.open) { closeLocal(); return; }
      view.data = structuredClone(data); view.stale = false;
      if (!keepDraft) { view.drafts = {}; view.dirty = false; }
      draw();
    }
    function show(kind) {
      if (!P.definitions[kind] || (kind !== 'edit' && !enabled(kind))) return;
      view = { kind, drafts: {}, dirty: false, stale: false, data: null }; refreshView(false);
      if (view && !dialog.open) dialog.showModal();
    }
    function open(kind, payload = {}) {
      if (!P.definitions[kind] || (kind !== 'edit' && !enabled(kind))) return;
      return execute(async () => { await invoke(P.definitions[kind][2], payload); show(kind); });
    }
    function openResult(kind) {
      const match = { newChat: 'conversations', persona: 'persona', supplement: 'supplement' }[kind];
      if (match && enabled(match)) show(match);
      else { closeLocal(); call('ui.native').catch(e => say(e.message)); }
    }
    function button(label, action, handler, disabled = false) {
      const b = btn(label, handler); if (action) b.dataset.slAction = action;
      b.dataset.fixedDisabled = String(disabled); return b;
    }
    function draw() {
      if (!view) return;
      const current = view, s = current.data; heading.textContent = P.definitions[current.kind][0]; body.replaceChildren();
      const field = (key, label, initial, limit, disabled, multiline) => {
        const wrapper = el('label', 'sl-field'), input = el(multiline ? 'textarea' : 'input');
        input.id = 'feature-field-' + key; input.value = current.drafts[key] ?? initial ?? ''; input.maxLength = limit > 0 ? limit : 100000;
        input.dataset.fixedDisabled = String(disabled); input.oninput = () => { current.drafts[key] = input.value; current.dirty = true; };
        wrapper.append(el('span', '', label), input); return wrapper;
      };
      P.render(current.kind, { data: s, el, button, field, add: (...nodes) => body.append(...nodes), run,
        draft: (key, fallback) => current.drafts[key] ?? fallback, dirty: () => current.dirty,
        resetDraft: () => { current.drafts = {}; current.dirty = false; }, confirm, prompt, openResult,
        native: () => call('ui.native').catch(e => say(e.message)), closeLocal, say, nativeDraft: () => state.actions?.composer?.text,
        removeConversation: payload => execute(async () => {
          const requested = await invoke('requestDeleteConversation', payload);
          const token = requested.data?.confirmation?.confirmationToken;
          if (!token) throw Error('MMD 未返回删除确认，请到原生页面核对。');
          await invoke('deleteConversation', { ...payload, confirmationToken: token }); refreshView(false);
        })
      });
      updateControls();
    }
    function updateControls() {
      for (const b of document.querySelectorAll('[data-sl-action]')) {
        const cap = state?.capabilities?.[b.dataset.slAction];
        b.disabled = busy || !cap?.available || b.dataset.fixedDisabled === 'true' || (dialog.contains(b) && !!view?.stale);
        b.title = cap?.available ? '' : cap?.reason || '当前桥接未提供这项功能';
      }
      for (const input of body.querySelectorAll('input,textarea')) input.disabled = busy || input.dataset.fixedDisabled === 'true';
      close.disabled = busy; reload.disabled = busy; back.disabled = busy;
      if (view?.stale) info.textContent = 'MMD 内容已变化。当前草稿已保留，请重新读取后再操作。';
      else if (view) info.textContent = busy ? '正在等待 MMD……' : '内容来自当前 MMD；提交后请核对结果。';
    }
    const nav = $('feature-nav');
    for (const [key, d] of Object.entries(P.definitions)) {
      if (key === 'edit' || !enabled(key)) continue;
      const b = button(d[0], d[2], () => open(key)); b.id = 'feature-open-' + key; nav.append(b);
    }
    const navActions = [['刷新对话', 'refreshConversation'], ['收藏角色', 'toggleFavorite'], ['查看评论', 'openComments'], ['离开聊天', 'exit']];
    if (enabled('navigation')) for (const [label, action] of navActions) {
      const b = button(label, action, () => {
        const payload = action === 'toggleFavorite' ? { revision: state.actions?.navigation.revision } : {};
        execute(async () => { await invoke(action, payload); if (action === 'openComments' || action === 'exit') await call('ui.native'); });
      }); b.id = 'feature-' + action; nav.append(b);
    }
    nav.append(btn('返回 MMD', native, 'feature-native'));
    $('menu-open').onclick = () => { const hidden = !nav.hidden; nav.hidden = hidden; $('menu-open').setAttribute('aria-expanded', String(!hidden)); };
    $('theme-toggle').onclick = () => { const light = document.documentElement.dataset.theme !== 'light'; document.documentElement.dataset.theme = light ? 'light' : 'dark'; $('theme-toggle').textContent = light ? '深色' : '浅色'; };
    document.documentElement.dataset.theme = G.MmdSameLayerUIConfig?.theme === 'light' ? 'light' : 'dark';
    $('theme-toggle').textContent = document.documentElement.dataset.theme === 'light' ? '深色' : '浅色';
    const sync = button('同步到 MMD 输入框', 'setInputText', () => {
      const payload = { revision: state.actions.composer.revision, text: $('text').value };
      const go = () => execute(() => invoke('setInputText', payload));
      const draft = state.actions.composer.text;
      if (draft == null || (draft.trim() && draft !== payload.text)) confirm('替换 MMD 输入框中的草稿？', '将用当前输入内容替换原生草稿，尚不会发送。', go); else go();
    });
    sync.id = 'composer-sync'; $('composer-tools').append(sync);
    const messageNodes = new Map();
    function messages() {
      const area = $('messages'), bottom = area.scrollHeight - area.scrollTop - area.clientHeight < 60, scroll = area.scrollTop;
      const rows = state.messages || [], ids = new Set(rows.map(m => m.id));
      for (const [id, node] of messageNodes) if (!ids.has(id)) { node.remove(); messageNodes.delete(id); }
      rows.forEach((m, index) => {
        let box = messageNodes.get(m.id);
        if (!box) { box = el('article', 'message ' + (m.role === 'user' ? 'user' : 'assistant')); box.dataset.messageId = m.id;
          box.append(el('div', 'role'), el('div', 'sl-message-text'), el('div', 'sl-message-actions')); messageNodes.set(m.id, box); }
        const label = (m.role === 'user' ? '你' : '叙述') + ' / ' + String(index + 1).padStart(2, '0');
        if (box.children[0].textContent !== label) box.children[0].textContent = label;
        if (box.children[1].textContent !== m.text) box.children[1].textContent = m.text;
        const signature = JSON.stringify([m.capabilities, state.actions?.messages?.revision]);
        if (box.dataset.signature !== signature) {
          box.dataset.signature = signature; const controls = box.children[2]; controls.replaceChildren();
          if (enabled('messageActions')) for (const [cap, action, label] of [
            ['copy', 'copyMessage', '复制'], ['edit', 'openEditMessage', '编辑'], ['regenerate', 'regenerateMessage', '重新生成'],
            ['rollback', 'rollbackMessage', '回溯'], ['startNewStory', 'startNewStoryFromMessage', '从此开启故事'], ['delete', 'deleteMessage', '删除']
          ]) {
            if (!m.capabilities?.[cap]) continue;
            const payload = { revision: state.actions.messages.revision, messageId: m.id };
            controls.append(button(label, action, () => {
              if (action === 'openEditMessage') return open('edit', payload);
              const go = () => execute(async () => {
                const result = await invoke(action, payload);
                if (result.data?.phase === 'confirmation-required') {
                  const token = result.data.confirmation?.confirmationToken;
                  if (!token) throw Error('确认信息缺失，请重新读取消息。');
                  await invoke(action, { ...payload, confirmationToken: token });
                }
              });
              if (['deleteMessage', 'rollbackMessage', 'startNewStoryFromMessage', 'regenerateMessage'].includes(action)) {
                const consequence = action === 'deleteMessage' ? '删除后无法恢复。' : action === 'rollbackMessage' ? '将删除这条消息之后的内容。' : action === 'regenerateMessage' ? '将请求 MMD 重新生成这条回复。' : '将以这条消息及之前的内容开启故事。';
                confirm(label + '？', m.text.slice(0, 240) + '\n\n' + consequence, go);
              } else go();
            }));
          }
        }
        if (area.children[index] !== box) area.insertBefore(box, area.children[index] || null);
      });
      area.scrollTop = bottom ? area.scrollHeight : scroll;
      $('message-count').textContent = String(rows.length).padStart(2, '0') + ' 条已读取';
    }
    function render(nativeState, isBusy) {
      state = nativeState; busy = isBusy;
      if (view && !own && state.actions?.[P.definitions[view.kind][1]]?.revision !== view.data?.revision) view.stale = true;
      messages(); updateControls();
      const favorite = $('feature-toggleFavorite'); if (favorite) favorite.textContent = state.actions?.navigation?.favorite === true ? '已收藏 · 取消收藏' : '收藏角色';
      $('connection').textContent = state.connected ? '已连接' : '正在连接';
    }
    function reset() { confirmation = null; question.close(); closeLocal(); $('text').value = ''; messageNodes.clear(); $('messages').replaceChildren(); }
    return { render, reset, dispose() { dead = true; reset(); dialog.remove(); question.remove(); } };
  }
  G.MmdSameLayerFeatureUI = Object.freeze({ mount });
})(globalThis);
