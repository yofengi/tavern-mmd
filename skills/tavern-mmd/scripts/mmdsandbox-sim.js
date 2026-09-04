/* mmdsandbox-sim.js — MMD 沙盒模式（chatVersion:1）本地日常仿真
 *
 * 经典脚本，零 module、零外部依赖。必须在**作者 hoisted scripts 之前**执行，
 * 这样作者脚本顶层拿到的 window.sdk 就已经在位（实机也是脚本执行时 sdk 已存在）。
 *
 * 事实依据（唯一）：sandbox-foundation/资料/基座事实卡.md
 *                   sandbox-foundation/资料/探针实测原始数据.md
 * 共享契约：      scripts/fixtures/mmdsandbox/contract.json
 *
 * 🚨 这不是完整平台，也不冒充完整平台。每个能力都带 accuracy：
 *   exact        实机探针/源码逐字确证 → 按确证行为复现
 *   conservative 方向已知、取值或时序未逐一实测 → 保守确定性实现
 *   probe-needed 未确证 → 不声称精确，界面必须标注需真实站验证
 */
(function () {
  'use strict';

  var W = (typeof window !== 'undefined' && window) ||
          (typeof globalThis !== 'undefined' && globalThis) || {};
  // 单例 + 幂等：SDK 无 off/once，创卡页预览会反复重跑（事实卡 §3、§4.2）。
  if (W.__MMD_SANDBOX_SIM__) { return; }

  var CFG = W.__MMD_SANDBOX_SIM_CONFIG__ || {};
  var CONTRACT_VERSION = '1.1.0';
  var PROFILE = CFG.profile === 'thin-preview' ? 'thin-preview' : 'chat';
  var THIN = PROFILE === 'thin-preview';

  // ---- 契约镜像。测试对撞 fixtures/mmdsandbox/contract.json，防止两份真相漂移 ----
  var EVENTS = ['ready', 'message:new', 'message:done', 'message:stream',
                'message:mount', 'message:unmount', 'input:change',
                'conversation:switch', 'theme:change', 'back', 'stage:close', 'dispose'];
  // 有 late replay 的只有 mount/done；ready 绝不补发（事实卡 §4.1，与手册相反）。
  var REPLAY_EVENTS = ['message:mount', 'message:done'];
  var COLD_START_ORDER = ['message:new', 'message:mount', 'message:done', 'ready'];
  var PAYLOAD_KEYS = ['content', 'id', 'role', 'serverId'];

  var ACCURACY_EXACT = ['input.get', 'input.getCursor', 'composer.visible', 'cache.get',
                        'save.get', 'save.keys', 'stage.close', 'stage.el', 'stage.visible',
                        'role.get', 'user.get', 'on', 'version'];
  var ACCURACY_CONSERVATIVE = ['input.set', 'input.add', 'input.insert', 'input.clear',
                               'input.focus', 'input.blur', 'input.setCursor',
                               'composer.show', 'composer.hide', 'message.send', 'message.edit',
                               'cache.set', 'cache.remove', 'save.set', 'save.remove',
                               'stage.open', 'debug.log'];
  // 瘦预览下这两项没有任何实测依据：cache.get 实测返回 undefined，但 set/remove 的
  // 真实表现未探到 → 降级标 probe-needed，绝不假装精确。
  var THIN_PROBE_NEEDED = ['cache.set', 'cache.remove'];

  var ACCURACY = {};
  (function () {
    var i;
    for (i = 0; i < ACCURACY_EXACT.length; i++) { ACCURACY[ACCURACY_EXACT[i]] = 'exact'; }
    for (i = 0; i < ACCURACY_CONSERVATIVE.length; i++) {
      ACCURACY[ACCURACY_CONSERVATIVE[i]] = 'conservative';
    }
    if (THIN) {
      for (i = 0; i < THIN_PROBE_NEEDED.length; i++) {
        ACCURACY[THIN_PROBE_NEEDED[i]] = 'probe-needed';
      }
    }
  })();

  // 实机错误码共 7 个（事实卡 §4.4，手册漏记 BUSY/NETWORK）；完整名单未探全，
  // 模拟器只用已确证的 NOT_SUPPORTED。
  function SdkError(code, message) {
    var e = new Error(message || code);
    e.name = 'SdkError';
    e.code = code;
    // 瘦预览实测是「同步抛 SdkError」，这里保证 name/code 都在，便于作者 try/catch 判码。
    return e;
  }

  var LOG = {
    contractVersion: CONTRACT_VERSION,
    profile: PROFILE,
    events: [],        // {seq, event, payload, listeners}
    calls: [],         // {seq, capability, args, outcome, accuracy}
    debug: [],         // sdk.debug.log 的转录
    warnings: [],      // 模拟器自己的保守/未确证提示
    scopeBlocked: []   // 被 message scope 挡掉的 Document 查询
  };
  var seq = 0;

  function note(text) {
    if (LOG.warnings.indexOf(text) === -1) { LOG.warnings.push(text); }
  }

  function record(capability, args, outcome) {
    seq += 1;
    LOG.calls.push({
      seq: seq, capability: capability, args: args,
      outcome: outcome, accuracy: ACCURACY[capability] || 'probe-needed'
    });
    return outcome;
  }

  // ================= message scope（事实卡 §4.3） =================
  // 真实机制不是 Proxy，是全局改写 Document.prototype 的 5 个查询方法 + 模块级游标 gc。
  // 收窄的作用对象是**气泡内元素的过滤**，平台级节点（root/statusbar/composer）仍可达
  // ——这一点是探针实测修正（qs_from_document_works=true）。
  var D = W.document || null;
  var BUBBLE_SEL = '[data-chat="message"]';
  var scopeOn = CFG.scope !== false;
  var cursor = null;          // 对应实机的 gc：非 null 时才看得到该气泡内元素
  var native = {};

  function matchesSel(node, sel) {
    if (!node || node.nodeType !== 1) { return false; }
    var fn = node.matches || node.msMatchesSelector || node.webkitMatchesSelector;
    return fn ? !!fn.call(node, sel) : false;
  }

  // 找 node 的所属气泡，只看**严格祖先**。气泡根自身由 querySelector 的
  // 「cursor 自身优先」分支处理；不能把其它气泡根当平台节点放行，否则两条气泡
  // 同时存在时 document.querySelector(All) 会泄漏到第一条消息。
  function ownerBubble(node) {
    var n = node ? node.parentNode : null;
    while (n && n.nodeType === 1) {
      if (matchesSel(n, BUBBLE_SEL)) { return n; }
      n = n.parentNode;
    }
    return null;
  }

  // 可见性判据：气泡外节点永远可见；气泡内节点只在「当前游标就是它所属气泡」时可见。
  function scopeAllows(node) {
    if (!scopeOn || !node) { return true; }
    if (matchesSel(node, BUBBLE_SEL)) { return cursor !== null && node === cursor; }
    var owner = ownerBubble(node);
    if (!owner) { return true; }
    return cursor !== null && owner === cursor;
  }

  function blocked(method, selector) {
    if (LOG.scopeBlocked.length < 200) {
      LOG.scopeBlocked.push({ method: method, selector: String(selector), cursor: cursor !== null });
    }
  }

  function installScopePatch() {
    if (!D || !W.Document || !W.Document.prototype) { return false; }
    var P = W.Document.prototype;
    var names = ['querySelector', 'querySelectorAll', 'getElementById',
                 'getElementsByClassName', 'getElementsByTagName'];
    for (var i = 0; i < names.length; i++) {
      if (typeof P[names[i]] !== 'function') { return false; }
      native[names[i]] = P[names[i]];
    }
    /* 🚨 收窄不是「先全文档查、再过滤」，而是**游标非 null 时先在游标气泡内查**
       （事实卡 §4.3 源码：getElementById 走 mc.call(gc, '[id="…"]')）。
       差别很关键：页面上有多条气泡时，全文档查 [data-chat="message-body"] 命中的是
       第一条（开场白），过滤后只会得到 null —— 作者在自己气泡的回调里反而什么都拿不到。 */
    P.querySelector = function (sel) {
      if (cursor !== null && scopeOn) {
        // 🚨 先看游标**自身**是否命中：内核桥接层要用
        // document.querySelector('[data-chat="message"]') 拿当前气泡根，而
        // Element.querySelector 只查后代、不含自身。少了这一步，查询会穿到全文档，
        // 命中第一条气泡（气泡根按平台节点放行）→ 桥接层拿到**错的 root**。
        if (matchesSel(cursor, sel)) { return cursor; }
        var inScope = cursor.querySelector(sel);      // Element 级查询，未被改写
        if (inScope) { return inScope; }
      }
      var found = native.querySelector.call(this, sel);
      if (found && !scopeAllows(found)) { blocked('querySelector', sel); return null; }
      return found;
    };
    P.querySelectorAll = function (sel) {
      var all, out = [], seen = [], i;
      // 与 querySelector 一样，先走当前 cursor（Element.querySelectorAll 不含自身）。
      // 然后才补平台节点；这让 [data-chat="message"] 的结果恰为当前气泡。
      if (cursor !== null && scopeOn) {
        if (matchesSel(cursor, sel)) { out.push(cursor); seen.push(cursor); }
        var scoped = cursor.querySelectorAll(sel);
        for (i = 0; i < scoped.length; i++) { out.push(scoped[i]); seen.push(scoped[i]); }
      }
      all = native.querySelectorAll.call(this, sel);
      for (i = 0; i < all.length; i++) {
        if (seen.indexOf(all[i]) === -1 && scopeAllows(all[i])) { out.push(all[i]); }
      }
      if (out.length !== all.length) { blocked('querySelectorAll', sel); }
      // 保守偏差：返回数组而非实时 NodeList。真机改写后的返回类型未确证。
      return out;
    };
    P.getElementById = function (id) {
      if (cursor !== null && scopeOn) {
        if (cursor.getAttribute && cursor.getAttribute('id') === String(id)) { return cursor; }
        var inScope = cursor.querySelector('[id="' + String(id) + '"]');
        if (inScope) { return inScope; }
      }
      var found = native.getElementById.call(this, id);
      if (found && !scopeAllows(found)) { blocked('getElementById', id); return null; }
      return found;
    };
    function filtered(method) {
      return function (arg) {
        var all = native[method].call(this, arg), out = [], i;
        for (i = 0; i < all.length; i++) {
          if (scopeAllows(all[i])) { out.push(all[i]); }
        }
        if (out.length !== all.length) { blocked(method, arg); }
        return out;
      };
    }
    P.getElementsByClassName = filtered('getElementsByClassName');
    P.getElementsByTagName = filtered('getElementsByTagName');
    note('message scope 只改 Document.prototype 的 5 个查询方法；Element.prototype.querySelector ' +
         '保持原生（实机同此，document.body.querySelector 能查到气泡内元素）。' +
         'querySelectorAll/getElementsBy* 返回静态数组而非实时集合，属保守偏差。');
    return true;
  }

  var scopeInstalled = installScopePatch();

  // 模拟器自用查询：一律走原生，不受 scope 影响（内核桥接层同理）。
  function nq(sel) {
    if (!D) { return null; }
    return (native.querySelector || D.querySelector).call(D, sel);
  }

  // ================= 事件分发（事实卡 §4.1 / §4.4c） =================
  var listeners = {};
  var replayHistory = { 'message:mount': [], 'message:done': [] };
  var disposed = false;

  function makePayload(content, id, role, serverId) {
    // 恰好 4 键，键序与探针 ownKeys 一致。多一键少一键都算失真。
    return { content: String(content), id: String(id), role: role,
             serverId: serverId === undefined ? null : serverId };
  }

  function invoke(fn, payload, bubble) {
    var prev = cursor;
    // mount/done/stream 的同步回调期间游标指向本气泡；回调结束即复原。
    if (bubble) { cursor = bubble; }
    try {
      // SDK 只传 1 个实参（探针 argcount=1）。第二参 bubbleRoot 是内核桥接层合成的，
      // 不是 SDK 给的 → 模拟器照实机只给一个。
      fn(payload);
    } catch (e) {
      LOG.warnings.push('作者回调抛错（实机一段脚本报错只废自己）：' + (e && e.message));
    } finally {
      cursor = prev;
    }
  }

  function emit(event, payload, bubble) {
    seq += 1;
    var list = listeners[event] ? listeners[event].slice() : [];
    LOG.events.push({ seq: seq, event: event, payload: payload, listeners: list.length });
    if (replayHistory[event]) { replayHistory[event].push({ payload: payload, bubble: bubble }); }
    for (var i = 0; i < list.length; i++) { invoke(list[i], payload, bubble); }
  }

  function on(event, fn) {
    if (typeof fn !== 'function') { return record('on', [event], undefined); }
    if (EVENTS.indexOf(event) === -1) {
      // 实机：名字打错不报错，只是永不触发。模拟器照此并留诊断。
      note('sdk.on(\'' + event + '\') 不在 12 个合法事件名内——实机不报错，只是永不触发。');
      return record('on', [event], undefined);
    }
    if (!listeners[event]) { listeners[event] = []; }
    listeners[event].push(fn);
    // late replay：只有 mount/done 补发；ready 绝不补发。
    if (replayHistory[event]) {
      var past = replayHistory[event].slice();
      for (var i = 0; i < past.length; i++) { invoke(fn, past[i].payload, past[i].bubble); }
    }
    return record('on', [event], undefined);   // 实机返回 undefined，无法退订
  }

  // ================= 气泡 DOM 构造（对齐全景骨架） =================
  var msgSeq = 0;

  function buildBubble(role, text, state, renderedHtml) {
    if (!D) { return null; }
    var list = nq('[data-chat="list"]');
    if (!list) { return null; }
    msgSeq += 1;
    var item = D.createElement('div');
    item.className = 'item';
    item.setAttribute('data-chat', 'message-frame');
    var touch = D.createElement('div');
    touch.className = 'touch-scope';
    touch.setAttribute('data-chat', 'message');
    touch.setAttribute('data-from', role);
    touch.setAttribute('data-state', state || 'done');
    touch.setAttribute('data-msg-id', 'sim-' + msgSeq);
    // 头像/昵称：真机存在但 0×0 隐藏，动态气泡也建出来（作者选择器可命中）。
    var avatar = D.createElement('div');
    avatar.setAttribute('data-chat', 'message-avatar');
    var name = D.createElement('div');
    name.setAttribute('data-chat', 'message-name');
    var body = D.createElement('div');
    body.className = 'content ' + (role === 'user' ? 'right' : 'left');
    body.setAttribute('data-chat', 'message-body');
    var time = D.createElement('time');
    time.setAttribute('data-chat', 'message-time');
    var extra = D.createElement('div');
    extra.setAttribute('data-slot', 'message-extra');
    // 三圆钮随角色变（实测 2026-08-31）：ai 3 钮 / user 2 钮 / first 0 钮。
    // 动态追加的气泡不是「第一句话」，故按 ai|user 给钮。
    var actions = D.createElement('div');
    actions.setAttribute('data-chat', 'message-actions');
    var acts = role === 'user'
      ? [['edit', '\u270E'], ['share', '\u27A4']]
      : [['regenerate', '\u21BB'], ['edit', '\u270E'], ['share', '\u27A4']];
    for (var ai = 0; ai < acts.length; ai++) {
      var ab = D.createElement('button');
      ab.type = 'button';
      ab.setAttribute('data-action', acts[ai][0]);
      var gl = D.createElement('span');
      gl.className = 'pano-glyph';
      gl.textContent = acts[ai][1];
      ab.appendChild(gl);
      actions.appendChild(ab);
    }
    touch.setAttribute('data-msg-kind', role === 'user' ? 'user' : 'ai');
    if (role === 'ai' && typeof renderedHtml === 'string' && renderedHtml) {
      body.innerHTML = renderedHtml;              // 仅预览器传入的离线规则结果；事件 payload 仍保留原文
    } else {
      body.textContent = String(text);
    }
    // 子节点顺序对齐真机：avatar → name → body → time → actions → extra
    touch.appendChild(avatar);
    touch.appendChild(name);
    touch.appendChild(body);
    touch.appendChild(time);
    touch.appendChild(actions);
    touch.appendChild(extra);
    item.appendChild(touch);
    list.appendChild(item);
    // 追加动态气泡即进入「已发送」态：隐藏开场白选择块（与真机一致）。
    var rootEl = nq('[data-chat="root"]');
    if (rootEl) { rootEl.setAttribute('data-chat-state', 'sent'); }
    var pane = nq('[data-chat="messages"]');
    if (pane) { pane.scrollTop = pane.scrollHeight; }
    return touch;
  }

  // 冷启动那条消息由全景静态骨架提供；控制 API 追加的消息才需要建 DOM。
  function pushMessage(role, text, state, renderedHtml) {
    var bubble = buildBubble(role, text, state, renderedHtml);
    msgSeq = msgSeq;
    var payload = makePayload(text, 'sim-' + msgSeq, role, 's' + msgSeq);
    return { bubble: bubble, payload: payload };
  }

  function textarea() { return nq('[data-chat="input"]'); }
  function root() { return nq('[data-chat="root"]'); }
  function stageEl() { return nq('[data-chat="author-stage"]'); }

  // ================= 同步/异步签名分界（不许把同步能力 Promise 化） =================
  // 🚨 只有这 4 个是**异步** Promise：message.send / message.edit / save.set / save.remove。
  // 其余能力（input.* 写类、composer.show/hide、cache.set/remove、stage.open）都是
  // **同步 void**：chat 下同步返回 undefined，thin 下按签名**同步抛** SdkError。
  // 把同步能力包成 Promise 会让作者写出 `await sdk.input.set(x)` 这种真机上没意义的代码，
  // 更糟的是 thin 下的失败会变成「未处理的 rejection」而不是当场抛错。
  var ASYNC_CAPABILITIES = ['message.send', 'message.edit', 'save.set', 'save.remove'];

  function thinThrow(capability) {
    record(capability, [], 'threw SdkError(NOT_SUPPORTED)');
    throw SdkError('NOT_SUPPORTED', capability + ' 在创卡页瘦预览不可用（同步抛 SdkError）');
  }

  function thinReject(capability) {
    // 仅供上面那 4 个异步能力使用：异步失败不该把整卡炸掉。
    record(capability, [], 'rejected SdkError(NOT_SUPPORTED)');
    var err = SdkError('NOT_SUPPORTED', capability + ' 在创卡页瘦预览不可用');
    if (typeof Promise === 'function') { return Promise.reject(err); }
    throw err;
  }

  function syncOk(capability, args) {
    record(capability, args, 'ok');
    return undefined;                 // 同步 void，与实机签名一致
  }

  function resolved(capability, args, value) {
    record(capability, args, 'resolved');
    return typeof Promise === 'function' ? Promise.resolve(value) : value;
  }

  function rejected(capability, args, error) {
    record(capability, args, 'rejected SdkError(' + error.code + ')');
    if (typeof Promise === 'function') { return Promise.reject(error); }
    throw error;
  }

  var input = {
    get: function () {
      // 瘦预览实测 ""；chat 读本页 composer 真值。
      if (THIN) { return record('input.get', [], ''); }
      var ta = textarea();
      return record('input.get', [], ta ? String(ta.value || '') : '');
    },
    getCursor: function () {
      if (THIN) { return record('input.getCursor', [], 0); }
      var ta = textarea();
      return record('input.getCursor', [], ta && ta.selectionStart ? ta.selectionStart : 0);
    },
    // 以下写类全部**同步 void**：chat 返回 undefined，thin 同步抛 SdkError。
    set: function (text) {
      if (THIN) { return thinThrow('input.set'); }
      var ta = textarea();
      if (ta) { ta.value = String(text === undefined ? '' : text); }
      return syncOk('input.set', [text]);
    },
    add: function (text) {
      if (THIN) { return thinThrow('input.add'); }
      var ta = textarea();
      if (ta) { ta.value = String(ta.value || '') + String(text === undefined ? '' : text); }
      return syncOk('input.add', [text]);
    },
    insert: function (text) {
      if (THIN) { return thinThrow('input.insert'); }
      var ta = textarea(), s = String(text === undefined ? '' : text);
      if (ta) {
        var v = String(ta.value || '');
        var at = typeof ta.selectionStart === 'number' ? ta.selectionStart : v.length;
        ta.value = v.slice(0, at) + s + v.slice(at);
      }
      return syncOk('input.insert', [text]);
    },
    clear: function () {
      if (THIN) { return thinThrow('input.clear'); }
      var ta = textarea();
      if (ta) { ta.value = ''; }
      return syncOk('input.clear', []);
    },
    focus: function () {
      if (THIN) { return thinThrow('input.focus'); }
      var ta = textarea();
      if (ta && ta.focus) { ta.focus(); }
      return syncOk('input.focus', []);
    },
    blur: function () {
      if (THIN) { return thinThrow('input.blur'); }
      var ta = textarea();
      if (ta && ta.blur) { ta.blur(); }
      return syncOk('input.blur', []);
    },
    setCursor: function (at) {
      if (THIN) { return thinThrow('input.setCursor'); }
      var ta = textarea();
      if (ta && ta.setSelectionRange) {
        try { ta.setSelectionRange(at, at); } catch (e) { /* 非可选区元素 */ }
      }
      return syncOk('input.setCursor', [at]);
    }
  };

  var composer = {
    // 瘦预览实测 true（不是包分析说的 false 降级）→ 两 profile 都返回 true。
    visible: function () { return record('composer.visible', [], true); },
    show: function () {
      if (THIN) { return thinThrow('composer.show'); }
      var r = root();
      if (r) { r.setAttribute('data-composer', 'visible'); }
      return syncOk('composer.show', []);
    },
    hide: function () {
      if (THIN) { return thinThrow('composer.hide'); }
      var r = root();
      if (r) { r.setAttribute('data-composer', 'hidden'); }
      return syncOk('composer.hide', []);
    }
  };

  var message = {
    send: function (text) {
      if (THIN) { return thinReject('message.send'); }
      // 本地只追加用户气泡：真实模型回复必须回真实站。
      var made = pushMessage('user', text === undefined ? '' : text, 'done');
      emit('message:new', made.payload, made.bubble);
      emit('message:mount', made.payload, made.bubble);
      emit('message:done', made.payload, made.bubble);
      note('message.send 只在本页追加用户气泡；**没有真实 AI 回复**，模型行为需回真实聊天页验证。');
      // 实机签名是 Promise<void>：不要把 payload 当返回值喂给作者，那会让人以为
      // 能从 send() 的结果里读到消息 id/serverId。要拿消息请订阅 message:* 事件。
      return resolved('message.send', [text], undefined);
    },
    edit: function (serverId, content) {
      if (THIN) { return thinReject('message.edit'); }
      // serverId===null 表示服务端还不认得这条（开场白即如此）→ 不可编辑。
      if (serverId === null || serverId === undefined || serverId === '') {
        record('message.edit', [serverId], 'rejected serverId 为空');
        var e = SdkError('INVALID_ARGS', 'serverId 为空（开场白 serverId===null）时不可 message.edit');
        return typeof Promise === 'function' ? Promise.reject(e) : (function () { throw e; })();
      }
      var hit = null, all = D ? (native.querySelectorAll || D.querySelectorAll)
        .call(D, '[data-chat="message"]') : [];
      for (var i = 0; i < all.length; i++) {
        if (all[i].getAttribute('data-msg-id') === String(serverId)) { hit = all[i]; }
      }
      if (hit) {
        var body = hit.querySelector('[data-chat="message-body"]');   // Element 查询，不受 scope 影响
        if (body) { body.textContent = String(content === undefined ? '' : content); }
      }
      return resolved('message.edit', [serverId, content], undefined);
    }
  };

  // cache：瘦预览 get 返回 undefined 且**不抛**（与 save 相反）。
  var cacheStore = {};
  var cache = {
    get: function (key) {
      if (THIN) { return record('cache.get', [key], undefined); }
      var v = Object.prototype.hasOwnProperty.call(cacheStore, key) ? cacheStore[key] : undefined;
      return record('cache.get', [key], v);
    },
    // cache.set/remove 是**同步 void**，不是 Promise。
    set: function (key, value) {
      if (THIN) { return thinThrow('cache.set'); }
      cacheStore[key] = value;
      return syncOk('cache.set', [key]);
    },
    remove: function (key) {
      if (THIN) { return thinThrow('cache.remove'); }
      delete cacheStore[key];
      return syncOk('cache.remove', [key]);
    }
  };

  var saveStore = {};
  function checkSaveKey(key) {
    if (typeof key !== 'string') {
      throw SdkError('INVALID_ARGS', 'save key 必须是字符串');
    }
    var k = key;
    if (k.length > 64) { throw SdkError('INVALID_ARGS', 'save key 超过 64 字'); }
    if (k.indexOf(':') !== -1) { throw SdkError('INVALID_ARGS', 'save key 禁含 :'); }
    return k;
  }
  var save = {
    get: function (key) {
      // 🚨 瘦预览同步抛 SdkError。作者的 store.load() 必须 try/catch，否则整卡炸。
      if (THIN) { return thinThrow('save.get'); }
      var v = Object.prototype.hasOwnProperty.call(saveStore, key) ? saveStore[key] : undefined;
      return record('save.get', [key], v);
    },
    keys: function () {
      if (THIN) { return thinThrow('save.keys'); }
      var out = [];
      for (var k in saveStore) {
        if (Object.prototype.hasOwnProperty.call(saveStore, k)) { out.push(k); }
      }
      return record('save.keys', [], out);
    },
    set: function (key, value) {
      if (THIN) { return thinReject('save.set'); }
      var checked;
      try { checked = checkSaveKey(key); } catch (e) {
        return rejected('save.set', [key], e);
      }
      saveStore[checked] = value;
      note('save 在本地仿真只存本页内存；真实跨设备持久化与限额需回真实聊天页验证。');
      return resolved('save.set', [key], undefined);
    },
    remove: function (key) {
      if (THIN) { return thinReject('save.remove'); }
      var checked;
      try { checked = checkSaveKey(key); } catch (e) {
        return rejected('save.remove', [key], e);
      }
      delete saveStore[checked];
      return resolved('save.remove', [key], undefined);
    }
  };

  var stageOpen = false;
  var stage = {
    // 🚨 关闭时仍返回 DIV（实测），绝不能靠 el() 是否 null 判开关。
    el: function () { return record('stage.el', [], stageEl()); },
    visible: function () { return record('stage.visible', [], stageOpen); },
    // stage.open/close 都是**同步 void**。瘦预览下 stage 实测可用
    // （stage_visible=false / stage_el=<DIV> 均正常返回），故两 profile 同一实现。
    open: function () {
      var el = stageEl();
      stageOpen = true;
      if (el) { el.removeAttribute('hidden'); }
      return syncOk('stage.open', []);
    },
    close: function () {
      var el = stageEl();
      stageOpen = false;
      if (el) { el.setAttribute('hidden', ''); }
      // 🚨 sdk.stage.close() **不派发** stage:close（事实卡 §4.4）。
      // 只有平台自己关闭舞台才派 → 见 control.stageClose()。
      record('stage.close', [], 'closed without stage:close event');
      return undefined;
    }
  };

  var role = { get: function () { return record('role.get', [], {
    name: CFG.roleName || '测试', avatarUrl: CFG.roleAvatar || ''
  }); } };
  var user = { get: function () { return record('user.get', [], {
    nickname: CFG.userNickname || '洛璃', avatarUrl: CFG.userAvatar || ''
  }); } };
  var debug = { log: function () {
    var args = Array.prototype.slice.call(arguments);
    LOG.debug.push(args.map(String).join(' '));
    if (W.console && W.console.log) { W.console.log.apply(W.console, ['[sdk.debug]'].concat(args)); }
    return record('debug.log', args, undefined);
  } };

  // ================= 装配 sdk（顶层恰 11 键，无 once/off） =================
  var sdk = {
    cache: cache, composer: composer, debug: debug, input: input, message: message,
    // 🚨 version 是**字符串** '1'，不是数字 1。作者写 sdk.version === 1 会永远为假。
    on: on, role: role, save: save, stage: stage, user: user, version: '1'
  };
  // 实机 sdk 未冻结、非 Proxy（Object.isFrozen(sdk)===false）→ 这里同样不冻结。
  W.sdk = sdk;
  if (typeof globalThis !== 'undefined') { globalThis.sdk = sdk; }

  // ================= 控制 API（预览工具用，非 SDK 的一部分） =================
  var streaming = null;      // {payload, bubble, content}
  var booted = false;

  var control = {
    /* 冷启动：作者脚本已在 DOM 之前跑完，这里模拟 DOM 完成后的严格顺序
       message:new -> message:mount -> message:done -> ready（实测 ready 最后到）。 */
    boot: function () {
      if (booted) { return false; }
      booted = true;
      // 真机由宿主按当前 visualViewport 把该值写成 root 内联变量。
      control.setViewportHeight(CFG.viewportHeight || W.innerHeight || 1205);
      var bubble = nq('[data-chat="message"][data-from="ai"]');
      var content = CFG.greeting !== undefined ? String(CFG.greeting)
        : (bubble ? String(bubble.textContent || '') : '');
      // 开场白：id 为字符串 "greeting"，serverId 为 null（不可 message.edit）。
      var payload = makePayload(content, 'greeting', 'ai', null);
      emit('message:new', payload, null);
      emit('message:mount', payload, bubble);
      emit('message:done', payload, bubble);
      emit('ready', undefined, null);        // ready 载荷为 undefined，且不补发
      return true;
    },
    addAI: function (text, renderedHtml) {
      var raw = text === undefined ? '[仿真 AI 消息]' : text;
      var made = pushMessage('ai', raw, 'done', renderedHtml);
      emit('message:new', made.payload, made.bubble);
      emit('message:mount', made.payload, made.bubble);
      emit('message:done', made.payload, made.bubble);
      return made.payload;
    },
    addUser: function (text) {
      var made = pushMessage('user', text === undefined ? '[仿真用户消息]' : text, 'done');
      emit('message:new', made.payload, made.bubble);
      emit('message:mount', made.payload, made.bubble);
      emit('message:done', made.payload, made.bubble);
      return made.payload;
    },
    /* 流式：先 new+mount，再逐块 message:stream（content 为累计值），done() 收尾。
       实机流式阶段跳过整条正则管线，故此处不做替换。 */
    stream: function (chunks) {
      var list = Object.prototype.toString.call(chunks) === '[object Array]'
        ? chunks : [chunks === undefined ? '流式片段' : chunks];
      if (!streaming) {
        var made = pushMessage('ai', '', 'streaming');
        streaming = { payload: made.payload, bubble: made.bubble, content: '' };
        emit('message:new', streaming.payload, streaming.bubble);
        emit('message:mount', streaming.payload, streaming.bubble);
      }
      for (var i = 0; i < list.length; i++) {
        streaming.content += String(list[i]);
        var body = streaming.bubble
          ? streaming.bubble.querySelector('[data-chat="message-body"]') : null;
        if (body) { body.textContent = streaming.content; }
        var p = makePayload(streaming.content, streaming.payload.id,
                            'ai', streaming.payload.serverId);
        emit('message:stream', p, streaming.bubble);
      }
      note('message:stream 的载荷形状按 new/mount/done 的 4 键同构实现，属保守推断；' +
           '流式分块节奏与真实模型输出需回真实聊天页验证。');
      return streaming.content;
    },
    done: function () {
      if (!streaming) { return null; }
      var s = streaming;
      streaming = null;
      if (s.bubble) { s.bubble.setAttribute('data-state', 'done'); }
      var p = makePayload(s.content, s.payload.id, 'ai', s.payload.serverId);
      emit('message:done', p, s.bubble);
      return p;
    },
    unmountLast: function () {
      var all = D ? (native.querySelectorAll || D.querySelectorAll)
        .call(D, '[data-chat="message"]') : [];
      if (!all.length) { return null; }
      var last = all[all.length - 1];
      // 🚨 官方事件表里 message:unmount **没有载荷**。之前这里伪造了 4 键 payload，
      // 那会让作者写 msg.content 在预览里能跑、真机上是 undefined。改派 undefined。
      emit('message:unmount', undefined, last);
      var frame = last.parentNode;
      if (frame && frame.parentNode) { frame.parentNode.removeChild(frame); }
      return true;
    },
    /* 切会话：实机平台脚本不重跑，公开状态需作者自清。清 replay 历史与流式态，
       但**不清订阅**（无 off，订阅不可撤销）。 */
    switchConversation: function (id) {
      streaming = null;
      replayHistory['message:mount'] = [];
      replayHistory['message:done'] = [];
      var list = nq('[data-chat="list"]');
      if (list) {
        var kids = [], i;
        for (i = 0; i < list.childNodes.length; i++) { kids.push(list.childNodes[i]); }
        for (i = 0; i < kids.length; i++) { list.removeChild(kids[i]); }
      }
      emit('conversation:switch', id === undefined ? 'sim-conversation-2' : id, null);
      note('conversation:switch 载荷形状未确证（这里给会话 id 字符串），属 probe-needed。');
      return true;
    },
    theme: function (name) {
      var next = name === 'dark' ? 'dark' : (name === 'light' ? 'light' : null);
      var r = root();
      if (!next) {
        var now = r ? r.getAttribute('data-theme') : 'light';
        next = now === 'dark' ? 'light' : 'dark';
      }
      if (r) { r.setAttribute('data-theme', next); }
      emit('theme:change', next, null);
      return next;
    },
    back: function () { emit('back', undefined, null); return true; },
    /* 平台侧关闭舞台才派 stage:close；sdk.stage.close() 不派（事实卡 §4.4）。 */
    stageClose: function () {
      var el = stageEl();
      stageOpen = false;
      if (el) { el.setAttribute('hidden', ''); }
      emit('stage:close', undefined, null);
      return true;
    },
    dispose: function () {
      disposed = true;
      emit('dispose', undefined, null);
      return true;
    },
    /* 软键盘/visualViewport：至少要能改 --chat-viewport-height（实机是 JS 内联 style）。 */
    setViewportHeight: function (px) {
      var r = root();
      var v = String(px === undefined ? 1205 : px) + 'px';
      if (r && r.style) { r.style.setProperty('--chat-viewport-height', v); }
      return v;
    },
    setKeyboardInset: function (inset) {
      var base = CFG.viewportHeight || W.innerHeight || 1205;
      return control.setViewportHeight(Math.max(0, base - (inset || 0)));
    },
    setScope: function (enabled) { scopeOn = enabled !== false; return scopeOn; },
    diagnose: function () {
      return {
        contractVersion: CONTRACT_VERSION,
        profile: PROFILE,
        scopeInstalled: scopeInstalled,
        scopeOn: scopeOn,
        cursorActive: cursor !== null,
        booted: booted,
        disposed: disposed,
        streaming: !!streaming,
        stageVisible: stageOpen,
        eventCount: LOG.events.length,
        callCount: LOG.calls.length,
        scopeBlockedCount: LOG.scopeBlocked.length,
        accuracy: ACCURACY,
        events: EVENTS.slice(),
        replayEvents: REPLAY_EVENTS.slice(),
        coldStartOrder: COLD_START_ORDER.slice(),
        payloadKeys: PAYLOAD_KEYS.slice(),
        warnings: LOG.warnings.slice()
      };
    },
    eventOrder: function () {
      var out = [], i;
      for (i = 0; i < LOG.events.length; i++) { out.push(LOG.events[i].event); }
      return out;
    },
    log: LOG
  };

  // ================= 暴露日志/控制面 =================
  LOG.control = control;
  LOG.contract = {
    version: CONTRACT_VERSION, profile: PROFILE, events: EVENTS.slice(),
    replayEvents: REPLAY_EVENTS.slice(), coldStartOrder: COLD_START_ORDER.slice(),
    payloadKeys: PAYLOAD_KEYS.slice(), accuracy: ACCURACY,
    capabilityCount: (function () { var n = 0, k; for (k in ACCURACY) {
      if (Object.prototype.hasOwnProperty.call(ACCURACY, k)) { n += 1; } } return n; })()
  };
  W.__MMD_SANDBOX_SIM__ = LOG;

  // ================= 生命周期引导 =================
  // 实机：作者脚本先执行、此时 DOM 未完成（探针 toplevel_found_pbOut=false），
  // DOM 完成之后才走冷启动。这里用 DOMContentLoaded 复现这个先后关系：
  // 本脚本与作者 hoisted scripts 都在 <body> 前部执行，气泡 DOM 在其后才解析。
  if (D && D.readyState === 'loading' && D.addEventListener) {
    D.addEventListener('DOMContentLoaded', function () { control.boot(); });
  } else if (D) {
    // 已完成（例如脚本被后置注入）：仍保持异步，避免作者顶层同步就拿到 mount。
    if (typeof W.setTimeout === 'function') { W.setTimeout(function () { control.boot(); }, 0); }
  }

  // 本地 iframe 尺寸变化时同步宿主内联高度。真机由 visualViewport 驱动；
  // 预览页 setViewportSize 会触发 iframe window.resize，不能沿用冷启动旧值。
  if (!CFG.viewportHeight && W && typeof W.addEventListener === 'function') {
    W.addEventListener('resize', function () {
      control.setViewportHeight(W.innerHeight || 1205);
    });
  }

  // 输入框变化 → input:change。载荷形状未确证，这里给当前文本。
  if (D && D.addEventListener) {
    D.addEventListener('DOMContentLoaded', function () {
      var ta = textarea();
      if (ta && ta.addEventListener) {
        ta.addEventListener('input', function () {
          emit('input:change', String(ta.value || ''), null);
        });
      }
    });
  }
})();
