/* Original adapters. Selectors are observations, not a stable MMD API contract. */
(function (G) {
  'use strict';
  const C = G.MmdSameLayerCore;
  function scopeReader(config) {
    return () => {
      try {
        const value = config.readScope?.();
        if (!value) return null;
        const scope = { ...value, appId: config.appId };
        C.scopeKey(scope);
        return Object.fromEntries(['appId', 'accountKey', 'roleId', 'conversationKey'].map(key => [key, scope[key]]));
      } catch (_) { return null; }
    };
  }
  // Old MMD has two mirrored textareas and a deliberately hidden send proxy.
  // Accept only one observed visible composer; do not broaden to arbitrary textareas.
  function inputControls(document) {
    const view = document.defaultView;
    const visible = el => el?.isConnected && el.getClientRects().length && !el.closest('[hidden]') &&
      view.getComputedStyle(el).visibility !== 'hidden' && view.getComputedStyle(el).display !== 'none';
    const usable = el => !el.disabled && !el.readOnly && !el.hasAttribute('disabled') &&
      !el.classList.contains('disabled') && el.getAttribute('aria-disabled') !== 'true';
    const scopes = [...document.querySelectorAll('#chat-input-scope,.chat-bottom .chat-input-scope')].filter(visible);
    if (scopes.length !== 1) return { input: null, send: null };
    const scope = scopes[0];
    const inputs = [...scope.querySelectorAll('textarea.uni-textarea-textarea')].filter(el => visible(el) && usable(el));
    const proxies = [...scope.querySelectorAll('.chat-send-proxy')].filter(el => el.isConnected && usable(el));
    return { input: inputs.length === 1 ? inputs[0] : null, send: proxies.length === 1 ? proxies[0] : null };
  }
  G.MmdSameLayerInput = Object.freeze({ resolve: inputControls });
  function dom(document, config) {
    const ids = new WeakMap(); let counter = 0;
    const models = G.MmdSameLayerModels?.dom(document, config);
    const features = G.MmdSameLayerActionDOM?.dom(document, config);
    const root = () => document.querySelector('#msglistview');
    const controls = () => inputControls(document);

    return {
      scope: scopeReader(config), identity: root, start() {}, cancel() { models?.cancel(); features?.cancel(); }, destroy() { models?.destroy(); features?.destroy(); },
      snapshot() {
        const list = root(); const { input, send } = controls(); const actionState = features?.snapshot();
        const items = [...(list?.querySelectorAll('.item.Ai, .item.self') || [])];
        return { connected: !!list, mode: 'native-dom', messages: actionState?.messages.items || items.slice(-100).map(el => {
          if (!ids.has(el)) ids.set(el, 'dom-' + (++counter));
          const ai = el.classList.contains('Ai') && !el.classList.contains('self');
          return { id: ids.get(el), role: ai ? 'assistant' : 'user',
            text: (el.querySelector(ai ? '.content.left' : '.content.right')?.textContent || '').slice(0, 6000) };
        }), capabilities: { sendMessage: { available: !!(list && input && send),
          reason: '需要唯一、可输入的原生输入框与发送按钮' }, ...models?.capabilities(), ...features?.capabilities() }, actions: actionState || null, models: models?.snapshot() || null, historyComplete: false };
      },
      async invoke(action, payload, options = {}) {
        options.check?.();
        if (G.MmdSameLayerModels?.actions.includes(action)) return models.invoke(action, payload, options);
        if (G.MmdSameLayerActions?.actions.includes(action) && features) return features.invoke(action, payload, options);
        if (action !== 'sendMessage') C.fail('NOT_AVAILABLE', '请返回原生界面使用这项功能');
        if (typeof payload?.text !== 'string' || !payload.text.trim() || payload.text.length > 15000) C.fail('INVALID_TEXT');
        const { input, send } = controls();
        if (!root() || !input || !send) C.fail('NOT_AVAILABLE', '原生输入区暂时不可用');
        if (input.value.trim() && input.value !== payload.text) C.fail('DRAFT_EXISTS', '原生输入框已有不同的草稿，请先返回原生界面处理');
        const originalRoot = root();
        const view = document.defaultView;
        Object.getOwnPropertyDescriptor(view.HTMLTextAreaElement.prototype, 'value').set.call(input, payload.text);
        input.dispatchEvent(new view.Event('input', { bubbles: true, composed: true }));
        input.dispatchEvent(new view.Event('change', { bubbles: true, composed: true }));
        await Promise.resolve(); options.check?.();
        const current = controls();
        if (!input.isConnected || !send.isConnected || current.input !== input || current.send !== send || root() !== originalRoot) C.fail('PLATFORM_CHANGED');
        if (input.value !== payload.text) C.fail('DRAFT_CHANGED', '输入内容在发送前发生变化，已停止发送');
        send.dispatchEvent(new view.MouseEvent('click', { bubbles: true, cancelable: true, composed: true }));
        return { ok: true, action, accepted: true, completed: 'unknown', persisted: 'unknown' };
      }
    };
  }
  function provided(bridge, config) {
    if (!bridge || !['getSnapshot', 'getCapabilities', 'invoke'].every(k => typeof bridge[k] === 'function')) C.fail('INVALID_BRIDGE');
    const models = G.MmdSameLayerProvidedModels?.create(bridge, config);
    const features = G.MmdSameLayerProvidedActions?.create(bridge, config);
    const allowed = new Set(config.allowedActions || ['sendMessage', ...(G.MmdSameLayerModels?.actions || []), ...(G.MmdSameLayerActions?.actions || [])]);
    function available(action) {
      return allowed.has(action) && bridge.getCapabilities()[action]?.available === true &&
        (!bridge.getRegisteredActions || bridge.getRegisteredActions().includes(action)) &&
        (action === 'sendMessage' || typeof config.projectResult === 'function');
    }
    return {
      scope: scopeReader(config), identity: () => bridge,
      // A provided bridge is caller-owned: its start/destroy stay with its owner.
      start() {}, cancel() { models?.cancel(); features?.cancel(); }, destroy() { models?.destroy(); features?.destroy(); },
      snapshot() {
        const raw = bridge.getSnapshot(); const caps = bridge.getCapabilities(); const actionState = features?.snapshot();
        return { connected: raw.connection?.status === 'connected', mode: 'provided-bridge',
          messages: actionState?.messages.items || (raw.messages || []).slice(-100).map(m => ({ id: String(m.id),
            role: m.role === 'user' ? 'user' : 'assistant', text: String(m.text || '').slice(0, 6000) })),
          capabilities: Object.fromEntries([...allowed].map(a => [a, { available: available(a),
            reason: String(caps[a]?.reason || '当前能力不可用') }]).concat(Object.entries(models?.capabilities() || {}), Object.entries(features?.capabilities() || {}))), actions: actionState || null, models: models?.snapshot() || null, historyComplete: false };
      },
      async invoke(action, payload, options = {}) {
        options.check?.();
        if (models && G.MmdSameLayerModels.actions.includes(action)) return models.invoke(action, payload, options);
        if (features && G.MmdSameLayerActions.actions.includes(action)) return features.invoke(action, payload, options);
        if (!available(action)) C.fail('NOT_AVAILABLE');
        const result = await bridge.invoke(action, C.clone(payload || {}));
        options.check?.();
        if (!result?.ok) C.fail(result?.error?.code || 'NATIVE_FAILED', result?.error?.message || '原生操作未成功');
        // Extra actions need an explicit projection, e.g. a confirmation-required phase.
        const data = config.projectResult ? C.clone(config.projectResult(action, result)) : null;
        if (C.canonical(data).length > 200000) C.fail('RESULT_TOO_LARGE');
        return { ok: true, action, data, accepted: true, completed: 'unknown', persisted: 'unknown' };
      }
    };
  }
  function mock(config) {
    let conversation = 'main'; let scopeEpoch = 0;
    const models = G.MmdSameLayerModels?.mock(config);
    const histories = new Map([['main', [{ id: 'hello', role: 'assistant', text: '欢迎来到雾港。聊天与寻物小游戏可以分别使用。' }]]]);
    let busy = false;
    const timers = new Set();
    return {
      scope: () => ({ appId: config.appId, accountKey: 'local-demo', roleId: 'fog-harbor', conversationKey: conversation }),
      identity: () => 'mock-' + scopeEpoch,
      start() {}, cancel() { models?.cancel(); }, destroy() { timers.forEach(clearTimeout); timers.clear(); models?.destroy(); },
      changeConversation(value) {
        conversation = value; scopeEpoch += 1; busy = false; models?.cancel();
        if (!histories.has(value)) histories.set(value, []);
      },
      snapshot: () => ({ connected: true, mode: 'mock', messages: C.clone(histories.get(conversation)),
        capabilities: { sendMessage: { available: !busy, reason: '正在生成模拟回复' }, ...models?.capabilities() }, models: models?.snapshot() || null, historyComplete: false }),
      async invoke(action, payload, options = {}) {
        options.check?.();
        if (G.MmdSameLayerModels?.actions.includes(action)) return models.invoke(action, payload, options);
        if (action !== 'sendMessage' || busy) C.fail('NOT_AVAILABLE');
        if (typeof payload?.text !== 'string' || !payload.text.trim()) C.fail('INVALID_TEXT');
        const rows = histories.get(conversation); const generation = scopeEpoch;
        rows.push({ id: C.uuid(), role: 'user', text: payload.text }); busy = true;
        const timer = setTimeout(() => {
          timers.delete(timer);
          rows.push({ id: C.uuid(), role: 'assistant', text: '【本地模拟】雾灯亮起，港口传来潮声。你的选择已经记录。' });
          if (generation === scopeEpoch) busy = false;
        }, 120);
        timers.add(timer);
        return { ok: true, action, accepted: true, completed: 'unknown', persisted: 'unknown' };
      }
    };
  }
  const serial = G.MmdSameLayerActions?.serial || (value => value);
  G.MmdSameLayerAdapters = Object.freeze({ dom: (...args) => serial(dom(...args), args[1]?.allowedActions), provided: (...args) => serial(provided(...args), args[1]?.allowedActions), mock: (...args) => serial(mock(...args), args[0]?.allowedActions) });
})(globalThis);
