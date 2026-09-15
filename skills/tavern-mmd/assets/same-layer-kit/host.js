/* Host owns platform access, storage, engine and iframe lifetime. */
(function (G) {
  'use strict';
  const C = G.MmdSameLayerCore;
  const A = G.MmdSameLayerAdapters;
  function boot(config, frameHtml) {
    if (!config || !/^[a-z0-9-]{1,40}$/.test(config.appId) || !config.buildId || config.buildId === 'dev') C.fail('INVALID_CONFIG');
    const registry = G.__MMD_SAME_LAYER__ || (G.__MMD_SAME_LAYER__ = Object.create(null));
    const previous = registry[config.appId];
    if (previous) {
      previous.show();
      if (previous.buildId !== config.buildId) previous.notice('新版本已载入；请导出进度后完整刷新，以免打断当前游戏。');
      return previous;
    }
    const supplied = config.bridge || G.__MMD_HUD_NATIVE_BRIDGE__;
    if (typeof supplied === 'function') C.fail('BRIDGE_FACTORY', '请由宿主先创建并启动桥接实例，再传给基座');
    const bridge = config.mode === 'mock' ? A.mock(config) : supplied ? A.provided(supplied, config) : A.dom(document, config);
    const resolver = G.__MMD_SAME_LAYER_SCOPE__;
    if (!config.readScope && typeof resolver === 'function') config.readScope = resolver;
    let frame = null, shell = null, returnButton = null, port = null, ready = false, stopped = false;
    let returnObserver = null;
    let contextId = '', scope = null, identity = null, store = null, pending = 0, lastSnapshot = '';
    let clientIds = new Set(), controller = 0, viewGame = null, gameError = '', bootNonce = '';
    const bootId = C.uuid();
    const originHref = G.location.href;
    let owner = null;
    function belongsHere(value) {
      return owner ? !!value && value.accountKey === owner.accountKey && value.roleId === owner.roleId : G.location.href === originHref;
    }
    const timer = setInterval(pulse, 500);
    function assertContext(token) {
      if (stopped || !ready || token !== contextId || !belongsHere(currentScope()) ||
          C.canonical(currentScope()) !== C.canonical(scope) || bridge.identity() !== identity) C.fail('SCOPE_CHANGED', '连接或会话已改变');
    }
    function currentScope() { try { return bridge.scope(); } catch (_) { return null; } }
    function sameScope(value) { try { return value && C.scopeKey(currentScope()) === C.scopeKey(value); } catch (_) { return false; } }
    function createStore(boundScope, boundContext) {
      if (!boundScope) return null;
      let storage;
      try { storage = G.localStorage; } catch (_) { return null; }
      return new C.SaveStore({ scope: boundScope, storage,
        lock: G.navigator?.locks ? (key, fn) => G.navigator.locks.request(key, fn) : null,
        isCurrent: () => !stopped && contextId === boundContext && belongsHere(currentScope()) && sameScope(boundScope) });
    }
    function post(message) { if (port && ready) port.postMessage({ protocol: 'mmd-sl/1', contextId, ...message }); }
    function notice(text) { post({ type: 'notice', text }); }
    function gameView(record) { return { epoch: record.epoch, version: record.version,
      ...C.publicState(record.state), ledger: C.clone(record.ledger.slice(-10)) }; }
    function applyRecord(record) {
      if (!viewGame || record.version >= viewGame.version) viewGame = gameView(record);
    }
    async function loadGame(token) {
      const bound = store;
      if (!bound || !config.engine) { viewGame = null; return; }
      try {
        const record = await bound.load();
        if (token !== contextId || bound !== store) return;
        applyRecord(record); gameError = '';
      } catch (e) { if (token === contextId) { viewGame = null; gameError = e.message; } }
      lastSnapshot = ''; publish();
    }
    function publish() {
      if (!ready) return;
      let native;
      try { native = bridge.snapshot(); } catch (_) { native = { connected: false, messages: [], capabilities: {} }; }
      const snapshot = { native, game: viewGame, engine: config.engine === true,
        gameError: gameError || (!scope ? '当前会话尚未确认；聊天可用，游戏保存未启用。' : ''),
        localPreview: config.mode === 'mock' };
      const serialized = C.canonical(snapshot);
      if (serialized !== lastSnapshot) { lastSnapshot = serialized; post({ type: 'snapshot', snapshot }); }
    }
    async function dispatch(method, params, token) {
      assertContext(token);
      if (method === 'native.invoke') {
        if (typeof params?.action !== 'string') C.fail('INVALID_REQUEST');
        const answer = await bridge.invoke(params.action, params.payload, { check: () => assertContext(token) });
        assertContext(token); publish(); return answer;
      }
      if (method === 'ui.native') { queueMicrotask(() => hide()); return { accepted: true }; }
      if (method === 'snapshot') { publish(); return { accepted: true }; }
      if (!config.engine || !store) C.fail('SAVE_UNAVAILABLE', gameError || '当前会话尚未确认，游戏存档不可用');
      const bound = store;
      if (method === 'game.load') { await loadGame(token); return viewGame; }
      if (method === 'game.export') return bound.export();
      let record;
      if (method === 'game.action') record = await bound.action(params.command, params.epoch);
      else if (method === 'game.import') record = await bound.import(params.raw, params.epoch);
      else if (method === 'game.narrate') {
        if (bridge.snapshot().capabilities.sendMessage?.available !== true) C.fail('NOT_AVAILABLE');
        const fact = await bound.reserveNarration(params); assertContext(token);
        await loadGame(token); assertContext(token);
        const prompt = '请用简短叙述描写以下已结算的游戏事实，不修改数值或替玩家行动：\n' + C.canonical(fact);
        try {
          const result = await bridge.invoke('sendMessage', { text: prompt }, { check: () => assertContext(token) });
          assertContext(token);
          if (!result?.ok) C.fail('NATIVE_FAILED');
          record = await bound.settleNarration(params.id, 'accepted', params.epoch);
          notice('已交给 MMD；请在对话区查看回复。游戏结果不受回复影响。');
        } catch (e) {
          // Reservation is already durable as unknown. Never retry automatically.
          notice('叙述提交结果待核对，请查看原生聊天记录；不会自动重发。'); throw e;
        }
      } else C.fail('METHOD_NOT_ALLOWED');
      assertContext(token);
      applyRecord(record); lastSnapshot = ''; publish(); return viewGame;
    }
    function receive(event) {
      const m = event.data;
      if (!m || m.protocol !== 'mmd-sl/1' || m.buildId !== config.buildId || m.nonce !== bootNonce) return;
      if (m.type === 'ready' && !ready) {
        ready = true; publish(); loadGame(contextId); return;
      }
      if (!ready || m.type !== 'request' || m.contextId !== contextId ||
          typeof m.id !== 'string' || m.id.length > 120 || clientIds.has(m.id)) return;
      if (clientIds.size >= 5000 || pending >= 12) { post({ type: 'result', id: m.id, ok: false, error: '请求过多，请重新进入页面' }); return; }
      let size;
      try { size = JSON.stringify(m).length; } catch (_) { return; }
      if (size > 1100000 || !['native.invoke', 'ui.native', 'snapshot', 'game.load', 'game.action', 'game.export', 'game.import', 'game.narrate'].includes(m.method)) {
        post({ type: 'result', id: m.id, ok: false, error: '无效请求' }); return;
      }
      clientIds.add(m.id); pending += 1;
      const token = contextId;
      Promise.resolve().then(() => dispatch(m.method, m.params || {}, token)).then(
        result => { if (token === contextId) post({ type: 'result', id: m.id, ok: true, result }); },
        e => { if (token === contextId) post({ type: 'result', id: m.id, ok: false, error: e.message, code: e.code || 'FAILED' }); }
      ).finally(() => { pending -= 1; });
    }
    function mount() {
      controller += 1; const generation = controller;
      contextId = C.uuid(); bootNonce = C.uuid(); ready = false; lastSnapshot = ''; viewGame = null;
      store = createStore(scope, contextId); gameError = ''; clientIds = new Set();
      shell = document.createElement('div'); shell.id = 'MMD_SL_' + config.appId + '_' + Date.now();
      shell.style.cssText = 'position:fixed;inset:0;z-index:2147483000;background:#faf6ed;white-space:normal;display:flex;flex-direction:column;';
      const bar = document.createElement('div');
      bar.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#173e41;color:#fff;font:14px sans-serif;';
      const title = document.createElement('span'); title.textContent = config.title || '同层卡';
      const back = document.createElement('button'); back.textContent = '返回 MMD';
      back.onclick = e => { e.stopPropagation(); hide(); };
      const close = document.createElement('button'); close.textContent = '关闭';
      close.onclick = e => { e.stopPropagation(); destroy(); };
      bar.append(title, back, close);
      frame = document.createElement('iframe');
      frame.title = config.title || '同层卡页面'; frame.setAttribute('sandbox', 'allow-scripts allow-downloads');
      frame.style.cssText = 'width:100%;flex:1;min-height:0;border:0;background:#faf6ed;';
      const expectedOrigin = G.location.origin;
      frame.name = JSON.stringify({ protocol: 'mmd-sl/1', buildId: config.buildId, nonce: bootNonce, parentOrigin: expectedOrigin });
      frame.srcdoc = frameHtml;
      frame.addEventListener('load', () => {
        if (generation !== controller || !frame) return;
        if (port) { unmount(); pulse(); return; }
        const channel = new MessageChannel(); port = channel.port1; port.onmessage = receive; port.start();
        frame.contentWindow.postMessage({ protocol: 'mmd-sl/1', type: 'connect', buildId: config.buildId, nonce: bootNonce }, '*', [channel.port2]);
      });
      shell.append(bar, frame); document.body.append(shell);
      returnButton = document.createElement('button'); returnButton.textContent = '返回游戏'; returnButton.hidden = true;
      returnButton.style.cssText = 'position:fixed;right:0;top:40%;z-index:2147483001;padding:12px 8px;border:0;border-radius:8px 0 0 8px;background:#173e41;color:white;';
      returnButton.onclick = e => { e.stopPropagation(); show(); };
      document.body.append(returnButton);
      returnObserver = new MutationObserver(syncReturnButton);
      returnObserver.observe(document.body, {childList:true,subtree:true,attributes:true,attributeFilter:['style','class','hidden','data-open']});
    }
    // Native popup controls must remain reachable while the card is hidden.
    function syncReturnButton() {
      if (!returnButton || !shell) return;
      const modal = shell.hidden && [...document.querySelectorAll('.u-popup__content,.msg-option-scope,.msg-modify-scope')].some(el => {
        if (shell.contains(el) || !el.getClientRects().length || el.closest('[hidden]')) return false;
        const rect=el.getBoundingClientRect(), style=G.getComputedStyle(el);
        return rect.width>0 && rect.height>0 && style.visibility!=='hidden' && style.display!=='none' && style.opacity!=='0';
      });
      const hidden = !shell.hidden || modal;
      if (returnButton.hidden !== hidden) returnButton.hidden = hidden;
    }
    function unmount() {
      returnObserver?.disconnect(); returnObserver = null;
      bridge.cancel?.();
      controller += 1; ready = false; contextId = C.uuid();
      if (port) port.close(); port = null;
      shell?.remove(); returnButton?.remove(); frame = shell = returnButton = null;
      store = null; viewGame = null;
    }
    function hide() { bridge.cancel?.(); if (shell) { shell.hidden = true; shell.style.display = 'none'; syncReturnButton(); } }
    function show() { if (shell) { shell.hidden = false; shell.style.display = 'flex'; returnButton.hidden = true; lastSnapshot = ''; publish(); } }
    function pulse() {
      if (stopped || !document.body) return;
      const nextScope = currentScope(); const nextIdentity = bridge.identity();
      if (!owner && nextScope && G.location.href === originHref) owner = { accountKey: nextScope.accountKey, roleId: nextScope.roleId };
      if (!belongsHere(nextScope)) { if (shell) unmount(); return; }
      const scopeChanged = C.canonical(scope) !== C.canonical(nextScope);
      if (scopeChanged || nextIdentity !== identity || (shell && !shell.isConnected)) unmount();
      scope = nextScope; identity = nextIdentity;
      if (!identity) { if (shell) unmount(); return; }
      if (!frame) mount(); else publish();
    }
    const onRoute = () => { unmount(); identity = null; };
    const onStorage = () => { if (ready && store) loadGame(contextId); };
    function destroy() {
      if (stopped) return; stopped = true; clearInterval(timer); unmount(); bridge.destroy();
      G.removeEventListener('pagehide', destroy); G.removeEventListener('hashchange', onRoute);
      G.removeEventListener('popstate', onRoute); G.removeEventListener('storage', onStorage);
      delete registry[config.appId];
    }
    const api = { buildId: config.buildId, bootId, show, hide, destroy, notice, bridge,
      getState: () => ({ ready, scopeReady: !!scope, game: viewGame, pending }) };
    registry[config.appId] = api;
    G.addEventListener('pagehide', destroy); G.addEventListener('hashchange', onRoute);
    G.addEventListener('popstate', onRoute); G.addEventListener('storage', onStorage);
    bridge.start(); pulse(); return api;
  }
  G.MmdSameLayerHost = Object.freeze({ boot });
})(globalThis);
