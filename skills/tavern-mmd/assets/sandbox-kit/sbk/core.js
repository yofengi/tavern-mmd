/* SBK core —— 沙盒基座内核层。依据：资料/基座事实卡.md
   经典脚本 IIFE：事实卡 §3 内联脚本走 (0,eval)，import 必报错，禁 module。
   顶层声明会被编译器回挂 window（§3），故除 SBK 外一律藏在闭包里。 */
(function (W) {
  'use strict';
  if (W.SBK && W.SBK.version) return; // 预览重跑（§3）：已装载则整体短路

  /* §4.4 sdk 未冻结非 Proxy，可被同卡其它脚本改写 → 启动即快照私有引用 */
  var S = W.sdk || {};
  var S_on = typeof S.on === 'function' ? S.on.bind(S) : null;
  var S_dbg = S.debug && typeof S.debug.log === 'function' ? S.debug.log.bind(S.debug) : null;
  var S_save = S.save || null;
  var S_cache = S.cache || null;

  function log() {
    // §4.4 debug.log 无瘦环境闸门，手机上唯一可见通道（URL 加 ?sdkDebug=1）
    if (!S_dbg) return;
    try { S_dbg.apply(null, ['[SBK]'].concat([].slice.call(arguments))); } catch (e) {}
  }
  function warn(msg, extra) { log('WARN ' + msg, extra === undefined ? '' : extra); }

  /* ---------- 单例哨兵 ---------- */
  var claimed = {};
  function claim(name) {
    var k = String(name || 'anon');
    if (claimed[k]) { log('claim rejected: ' + k); return false; }
    claimed[k] = 1;
    return true;
  }

  /* ---------- 事件总线 ----------
     §4.2 sdk.on 返回 undefined，无 off/无 once，唯一退订会清掉所有脚本订阅。
     故对每个 sdk 事件只订阅一次，内部再分发，对外提供真正的 off。 */
  /* stage:close / back / message:unmount 保留【原名】不缩写，对外即 SBK.on('stage:close'|'back'|'unmount')。
     stage:close 只在平台侧关闭舞台时派发（如用户按返回）；sdk.stage.close() 自己调【不派发】，
     见事实卡 §4.4b。桥接必须在内核，组件层不得自建，否则双份派发。 */
  var EVT = {
    'message:mount': 'mount',
    'message:done': 'done',
    'message:stream': 'stream',
    'message:unmount': 'unmount',
    'theme:change': 'theme',
    'conversation:switch': 'switch',
    'stage:close': 'stage:close',
    'back': 'back',
    'dispose': 'dispose',
    'ready': 'ready'
  };
  var subs = {};

  function on(evt, fn) {
    if (typeof fn !== 'function') return fn;
    (subs[evt] || (subs[evt] = [])).push(fn);
    return fn;
  }
  function off(evt, fn) {
    var a = subs[evt];
    if (!a) return false;
    for (var i = 0; i < a.length; i++) if (a[i] === fn) { a.splice(i, 1); return true; }
    return false;
  }
  function emit(evt, payload, root) {
    var a = subs[evt];
    if (!a || !a.length) return;
    var list = a.slice(); // 快照：回调内可能 off 自己
    for (var i = 0; i < list.length; i++) {
      try { list[i](payload, root); } catch (e) { warn('handler threw on ' + evt, e && e.message); }
    }
  }

  /* 桥接：每个 sdk 事件只 on 一次。
     §4.3 收窄靠全局改写 Document.prototype.* + 模块级游标 gc。mount/done 回调运行期间
     gc === 本气泡，此刻 document.querySelector('[data-chat="message"]') 就是本气泡根；
     跨 await/setTimeout 后 gc 回落 null，气泡内元素全部隐身，再也查不回来。
     故此处【同步】抓根引用，作为第二参数传给消费者，绝不延后。 */
  function bridge() {
    if (!S_on) { warn('sdk.on unavailable, bus is local-only'); return; }
    Object.keys(EVT).forEach(function (raw) {
      var name = EVT[raw];
      try {
        S_on(raw, function (payload) {
          var root = null;
          if (name === 'mount' || name === 'done' || name === 'stream') {
            // 就地抓引用（§4.3）。不要「优化」成回调外查询或延后查询。
            try { root = W.document.querySelector('[data-chat="message"]'); } catch (e) { root = null; }
          }
          emit(name, payload, root);
        });
      } catch (e) { warn('bridge failed: ' + raw, e && e.message); }
    });
  }

  /* ---------- 状态仓 ---------- */
  var st = {};
  function snap(o) { var r = {}, k; for (k in o) if (Object.prototype.hasOwnProperty.call(o, k)) r[k] = o[k]; return r; }
  var state = {
    get: function () { return snap(st); },
    patch: function (p) {
      if (!p || typeof p !== 'object') return state.get();
      for (var k in p) if (Object.prototype.hasOwnProperty.call(p, k)) st[k] = p[k];
      emit('state', state.get());
      return state.get();
    },
    replace: function (next) {
      st = next && typeof next === 'object' ? snap(next) : {};
      emit('state', state.get());
      return state.get();
    },
    subscribe: function (fn) { on('state', fn); return function () { off('state', fn); }; }
  };

  /* ---------- 持久化 ----------
     §4.4 save key 须 1..64 且禁 ':'；save.get 同步（未预载抛 HOST_DENIED）；
     save.set 异步、限频 20 次/60s，必须 .catch。
     🚨 硬约束 18 / §4.4a 实机修正：瘦预览下 save.get / save.keys 是【同步抛 SdkError】，
        不是「返回 NOT_SUPPORTED」。这是最易翻车处 —— 不 try/catch 会在创卡页预览直接炸整卡。
        故 readRaw 对 save.get 就地 try/catch，store.load 再兜一层。
     降级链：save → sdk.cache（实测 cache.get 返 undefined 不抛，可靠）→ 内存。 */
  var KEY = 'sbk-state';           // 无 ':'，14 字符
  var mem = null;                  // 最终回落
  var deadSave = false;            // save 通道判死后不再重试
  var bucket = [];                 // 令牌桶时间戳
  var LIMIT = 18, WIN = 60000;     // 留 2 次余量给业务方自己写
  var pending = null, timer = null;

  function okKey(k) { return typeof k === 'string' && k.length > 0 && k.length <= 64 && k.indexOf(':') < 0; }
  function allow() {
    var now = Date.now();
    while (bucket.length && now - bucket[0] > WIN) bucket.shift();
    if (bucket.length >= LIMIT) return false;
    bucket.push(now); return true;
  }
  function readRaw() {
    if (!deadSave && S_save && typeof S_save.get === 'function') {
      try { var v = S_save.get(KEY); if (v !== undefined && v !== null) return v; return null; }
      catch (e) { deadSave = true; warn('save.get unavailable, fallback to cache', e && e.code); }
    }
    if (S_cache && typeof S_cache.get === 'function') {
      try { var c = S_cache.get(KEY); if (c !== undefined && c !== null) return c; } catch (e) {}
    }
    return mem;
  }
  function writeRaw(str) {
    mem = str;
    if (S_cache && typeof S_cache.set === 'function') {
      // 先落 cache：同步、无限频，保证本会话内至少不丢
      try { S_cache.set(KEY, str); } catch (e) { warn('cache.set failed', e && e.code); }
    }
    if (deadSave || !S_save || typeof S_save.set !== 'function') return;
    if (!allow()) { warn('save.set throttled locally, kept in cache'); return; }
    try {
      var p = S_save.set(KEY, str);
      if (p && typeof p.then === 'function') {
        p.catch(function (e) {
          var code = e && e.code;
          if (code === 'NOT_SUPPORTED' || code === 'HOST_DENIED') deadSave = true;
          warn('save.set rejected: ' + (code || 'unknown'));
        });
      }
    } catch (e) { warn('save.set threw', e && e.code); }
  }
  var store = {
    key: function (k) { if (okKey(k)) KEY = k; else warn('bad save key ignored (need 1..64, no ":")', k); return KEY; },
    load: function () {                       // 同步。整体兜底：任何异常都返回 null，绝不外抛（硬约束 18）
      try {
        var raw = readRaw();
        if (typeof raw !== 'string') return raw && typeof raw === 'object' ? raw : null;
        return JSON.parse(raw);
      } catch (e) { warn('store.load failed, returning null', e && (e.code || e.message)); return null; }
    },
    save: function (obj) {                    // 异步 + 节流（尾部合并）
      var data = obj === undefined ? state.get() : obj;
      try { pending = JSON.stringify(data); } catch (e) { warn('store.save stringify failed'); return; }
      if (timer) return;
      timer = W.setTimeout(function () { timer = null; var s = pending; pending = null; if (s !== null) writeRaw(s); }, 800);
    },
    clear: function () {
      pending = null; mem = null;
      if (S_cache && typeof S_cache.remove === 'function') { try { S_cache.remove(KEY); } catch (e) {} }
      // §4.4 save.remove 不过任何限频桶
      if (!deadSave && S_save && typeof S_save.remove === 'function') {
        try { var p = S_save.remove(KEY); if (p && p.catch) p.catch(function (e) { warn('save.remove rejected', e && e.code); }); }
        catch (e) { warn('save.remove threw', e && e.code); }
      }
    }
  };

  /* ---------- 渲染调度 ----------
     §5 message:stream 触发极密，官方明说别在里面查 DOM/算布局 → rAF 合帧，同一 fn 每帧只跑一次 */
  var jobs = [], raf = null;
  var rAF = W.requestAnimationFrame ? W.requestAnimationFrame.bind(W) : function (f) { return W.setTimeout(f, 16); };
  function flush() {
    raf = null;
    var list = jobs; jobs = [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](); } catch (e) { warn('scheduled job threw', e && e.message); }
    }
  }
  function schedule(fn) {
    if (typeof fn !== 'function') return;
    if (jobs.indexOf(fn) < 0) jobs.push(fn);
    if (!raf) raf = rAF(flush);
  }

  /* ---------- DOM 工具 ---------- */
  /* §5.4 worker 白名单 ∩ DOMPurify。非白名单标签在管线里被正则剥壳（文字保留）。
     JS 建的节点本身不过净化器，但 h() 仍按白名单校验：同一份结构会被 WP-2
     序列化成快照 HTML 走管线，两边行为必须一致。 */
  var TAGS = ('p b a div span h1 h2 h3 h4 h5 h6 ul li ol strong em br img pre font i button table th tr td ' +
    'input textarea label select option video user summary details code blockquote hr del thead tbody s ' +
    'svg g path circle ellipse rect line polyline polygon text tspan defs use linearGradient radialGradient ' +
    'stop clipPath title').split(' ');
  var SVG = 'svg g path circle ellipse rect line polyline polygon text tspan defs use linearGradient radialGradient stop clipPath'.split(' ');
  var NS = 'http://www.w3.org/2000/svg';
  /* §5.5 SAFE_FOR_XML 默认开：属性值命中此式 → 整条属性被删，且早于 forceKeepAttr。
     头号事故是 onclick="if(a[0]>1)" 里的 ']>' 让整个 onclick 静默消失。
     → 比较运算符两侧留空格；属性值禁 ]> --> --!> 与 </style|script|…> */
  var XML_BAD = /((--!?|])>)|<\/(style|script|title|xmp|textarea|noscript|iframe|noembed|noframes)/i;

  function h(tag, attrs, children) {
    var t = String(tag || 'div').toLowerCase();
    if (TAGS.indexOf(t) < 0) { warn('tag not in worker whitelist, coerced to div: ' + t); t = 'div'; }
    var el = SVG.indexOf(t) >= 0 ? W.document.createElementNS(NS, t) : W.document.createElement(t);
    var k, v;
    if (attrs) for (k in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
      v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      var lk = k.toLowerCase();
      // §5.5 作者自写 data-* 全删；ALLOW_ARIA_ATTR:!1 → aria-* 与 role 全删。告警而非静默。
      if (lk.indexOf('data-') === 0 || lk.indexOf('aria-') === 0 || lk === 'role') {
        warn('attr stripped by sanitizer, use class instead: ' + k + ' on <' + t + '>');
        continue;
      }
      /* §5.5 on* 保留范围：Mh=/^on[a-z]+$/i，非 SVG 元素上 forceKeepAttr 强留。
         ⚠ 实测确认是【任意 on*】而非仅 onclick：<b onclick> 与 <b onmouseenter> 双双 KEPT。
           故这里【不做 on* 白名单收窄】—— 后人别加，会误杀合法事件。
         SVG 内则全删（实测 <circle onclick> STRIPPED）→ 交互必须挂 HTML 壳。 */
      if (lk.indexOf('on') === 0 && SVG.indexOf(t) >= 0 && typeof v !== 'function') {
        warn('on* is removed inside SVG, wrap in an HTML host: ' + k);
        continue;
      }
      if (typeof v === 'function' && lk.indexOf('on') === 0) {
        el.addEventListener(lk.slice(2), v); // JS 直绑，不过净化器，无 SAFE_FOR_XML 风险
        continue;
      }
      v = v === true ? '' : String(v);
      if (XML_BAD.test(v)) {
        warn('attr value hits SAFE_FOR_XML and would be dropped whole: ' + k + '=' + v);
        continue;
      }
      try { el.setAttribute(k, v); } catch (e) { warn('setAttribute failed: ' + k, e && e.message); }
    }
    append(el, children);
    return el;
  }
  function append(el, c) {
    if (c === null || c === undefined || c === false) return;
    if (Array.isArray(c)) { for (var i = 0; i < c.length; i++) append(el, c[i]); return; }
    if (c && c.nodeType) { el.appendChild(c); return; }
    el.appendChild(W.document.createTextNode(String(c)));
  }

  /* §4.3 查【气泡内】元素必须在传入的 root 上查，不要走 document。
     收窄的作用对象是**气泡内元素的过滤**（bc()）：gc===null 时「在气泡内 → 不可见」，
     故气泡内元素查不到；gc 仅在 mount/done 回调与 click/input/change/keydown 捕获期非空，
     且恢复走 queueMicrotask → 跨 await/setTimeout 即失效。
     ⚠ 措辞澄清（§4.3 实机修正）：document 并非完全不可用 —— mount 回调内
       document.querySelector('[data-chat="root"]') 等【平台级节点实测可达】。
       受限的只有气泡内元素。故 mountHost 用 document 是对的，本函数用 root 也是对的。
     Element.prototype 对气泡内元素走原生实现，故 root.querySelector 干净可靠。
     ⚠ 别把本函数「优化」成 document.querySelector：查气泡内元素时会在异步路径上静默返回 null。 */
  function inBubble(root, sel) {
    if (!root || typeof root.querySelector !== 'function') { warn('inBubble called without a root element'); return null; }
    try { return root.querySelector(sel); } catch (e) { warn('inBubble bad selector: ' + sel); return null; }
  }
  function allInBubble(root, sel) {
    if (!root || typeof root.querySelectorAll !== 'function') return [];
    try { return [].slice.call(root.querySelectorAll(sel)); } catch (e) { return []; }
  }

  /* §3 currentScript 恒 null（顶层与回调内实测均 null）→ 宿主只能靠固定 id 约定定位。
     §9 实测宿主链：div < [data-slot=statusbar] < [data-chat=root] < div < body
     —— root【不是】body 的直接子节点。故全程用后代选择器搜索，不做任何固定跳数/parentNode 链假设。
     §7.3 statusbar 槽位仅当卡片 statusbar 字段非空才渲染 → 缺失时逐级回落。 */
  function mountHost(id) {
    var hid = String(id || 'sbk-host');
    var d = W.document;
    // 硬约束 17：作者脚本早于 DOM 渲染（实测顶层取自己写入功能栏的节点得 null）。
    // root 不存在 = DOM 还没挂，此时任何挂载都是徒劳 → 明确报错，让调用方改到事件回调里。
    var root = d.querySelector('[data-chat="root"]');
    if (!root) { warn('mountHost: DOM not rendered yet (no [data-chat="root"]). Call it inside a mount/done handler.'); return null; }
    var slot = d.querySelector('[data-slot="statusbar"]');
    var fallback = false;
    if (!slot) {
      slot = d.querySelector('[data-slot="left"]');
      fallback = true;
      warn('statusbar slot missing (card statusbar field empty?), falling back to [data-slot="left"]');
    }
    // 末位回落 root 本身（flex 列容器），不用 body：body 在 root 之外，挂那里会脱离平台布局
    if (!slot) { slot = root; fallback = true; warn('no slot found, falling back to [data-chat="root"]'); }
    // 不用 getElementById：那也被改写过（§4.3）。直接遍历子节点最稳。
    var kids = slot.childNodes, i, n;
    for (i = 0; i < kids.length; i++) {
      n = kids[i];
      if (n && n.nodeType === 1 && n.id === hid) return n; // 预览重跑复用，不堆积
    }
    var host = h('div', { id: hid, 'class': 'sbk-host' + (fallback ? ' sbk-host--float' : '') });
    slot.appendChild(host);
    return host;
  }

  /* ---------- 编排入口 ----------
     SBK.boot 是【唯一】把各层接起来的地方，生成器产出的 sbk-boot 规则只调它。
     纯集成层：只做参数归一化与投喂，不重复实现任何一层已有的功能。
     缺层（只装了 core 没装 ui/protocol/theme）一律告警并跳过该功能，绝不抛异常炸整卡。 */

  /* schema 键名归一化。权威键名是 fields（协议说明 §3 与 hud.js 的 pick 只读 sc.fields）。
     rows 作容错别名：键名写错时 hud 读不到 defs，会静默退化成「按模型输出顺序全渲染」，
     现象是 schema 像根本没生效，极难排查 → 宽容接受 + 告警，成本远低于踩坑代价。
     归一化放在这一层，是因为它是所有配置进入基座的唯一入口；组件层保持只认 fields 的单一契约。 */
  function normSchema(sc) {
    if (!sc || typeof sc !== 'object') return {};
    var out = snap(sc);                       // 复制：不改调用方传进来的载荷对象
    if (!out.fields && out.rows) {
      out.fields = out.rows;
      delete out.rows;
      warn('schema.rows is a tolerated alias; rename it to schema.fields (authoritative key)');
    }
    return out;
  }

  var booted = null;   // 句柄缓存：重跑时原样返回，调用方拿到的始终是同一个

  function boot(opts) {
    // §3 创卡页预览反复重跑整卡脚本 + §4.2 sdk.on 无 off/once → 重复 boot 会让订阅翻倍。
    // 哨兵短路：第二次起直接返回首次的句柄，不再挂任何订阅。
    if (!claim('boot')) { log('boot already done, returning existing handle'); return booted; }

    var o = opts && typeof opts === 'object' ? opts : {};
    var modes = o.modes && typeof o.modes === 'object' ? o.modes : {};
    var wantHud = modes.hud === undefined ? true : !!modes.hud;
    var wantSnap = !!modes.snapshot;             // 与生成器默认一致（hud:true / snapshot:false）
    var sc = normSchema(o.schema);
    if (o.hostId && !sc.hostId) sc.hostId = o.hostId;   // 宿主 id 由配置顶层给，schema 未显式覆盖时下传
    var skipped = [];

    // 主题：apply 只写 <head> 里的 <style>，不碰气泡/功能栏 → 顶层调用安全（不受硬约束 17 限制）。
    // 载荷形如 {dark:{…},light:{…}}，theme.apply 原生就认这个形状（也认扁平写法=两套同值）。
    if (o.theme) {
      if (SBK.theme && typeof SBK.theme.apply === 'function') {
        try { SBK.theme.apply(o.theme); } catch (e) { skipped.push('theme'); warn('boot: theme.apply threw', e && e.message); }
      } else { skipped.push('theme'); warn('boot: theme layer not loaded, theme tokens ignored'); }
    }

    // 协议块标记：parse.config 存在即协议层已装（core 的占位实现没有 .config）
    if (o.protocolTag) {
      if (SBK.parse && typeof SBK.parse.config === 'function') {
        try { SBK.parse.config({ block: o.protocolTag }); } catch (e) { warn('boot: parse.config threw', e && e.message); }
      } else { skipped.push('protocol'); warn('boot: protocol layer not loaded, protocolTag ignored'); }
    }

    /* 🚨 硬约束 17 / §4.1：作者脚本早于 DOM 执行（实测顶层 getElementById 取功能栏节点得 null），
       故此处【绝不】在顶层挂 HUD —— 只 new 出渲染器，宿主容器由它自己在事件回调内取。
       🚨 §4.1 实测冷启动顺序 message:new > message:mount > message:done > ready：
          ready【最后】到且无补发，只有 mount/done 有补发 → hud() 内部订阅的正是 mount/done，
          这里不得改挂 ready，否则首屏晚一整轮且历史气泡拿不到补发。 */
    var hud = null;
    if (wantHud) {
      if (SBK.ui && typeof SBK.ui.hud === 'function') hud = SBK.ui.hud(null, sc);
      else { skipped.push('hud'); warn('boot: SBK.ui.hud not loaded, mode A disabled'); }
    }

    // 模式 B：snapshot.auto 自己挂 mount/done 做 hydrate（mount 有补发，历史气泡也会被升级）
    var snapOn = false;
    if (wantSnap) {
      if (SBK.ui && SBK.ui.snapshot && typeof SBK.ui.snapshot.auto === 'function') {
        try { SBK.ui.snapshot.auto(sc); snapOn = true; }
        catch (e) { skipped.push('snapshot'); warn('boot: snapshot.auto threw', e && e.message); }
      } else { skipped.push('snapshot'); warn('boot: SBK.ui.snapshot not loaded, mode B disabled'); }
    }

    booted = {
      schema: sc,
      modes: { hud: !!hud, snapshot: snapOn },
      skipped: skipped,
      hud: hud,                                            // 模式 A 句柄（el/render/feed/mount），缺层时 null
      el: function () { return hud ? hud.el() : null; },
      render: function () { if (hud) hud.render(); },
      feed: function (text) { return hud ? hud.feed(text) : false; },
      /* dispose 只回收【看得见的产物】：主题样式 + HUD 宿主内容。
         §4.2 无 off/once，hud/snapshot 是用匿名函数订阅内部总线的，没有函数引用可撤 →
         订阅留着。故【不释放 boot 哨兵】：再 boot 只会拿回旧句柄，不会二次订阅。 */
      dispose: function () {
        if (SBK.theme && typeof SBK.theme.reset === 'function') { try { SBK.theme.reset(); } catch (e) {} }
        var host = hud ? hud.el() : null;
        if (host) { while (host.firstChild) host.removeChild(host.firstChild); }
        warn('boot: disposed visuals only; event subscriptions are not revocable (§4.2)');
      }
    };
    log('boot done: hud=' + booted.modes.hud + ' snapshot=' + snapOn +
      (skipped.length ? ' skipped=' + skipped.join(',') : ''));
    return booted;
  }

  /* ---------- 导出 ---------- */
  var SBK = {
    version: '1',
    claim: claim,
    boot: boot,             // 唯一编排入口，生成器的 sbk-boot 规则调它
    schema: normSchema,     // schema 归一化（rows → fields），供直接调 ui.hud 的做卡人复用
    on: on, off: off, emit: emit,
    state: state,
    store: store,
    schedule: schedule,
    dom: { h: h, mountHost: mountHost, inBubble: inBubble, all: allInBubble },
    log: log, warn: warn,
    sdk: S,                 // 启动快照，供上层使用，不受后续改写影响
    // WP-2 装载协议后覆写；未装载时优雅返回 null 而非抛错，避免炸掉整卡
    parse: function () { warn('SBK.parse called but protocol layer (WP-2) is not loaded'); return null; },
    theme: {},              // WP-1 theme.js 填充
    /* WP-3 ui.js 填充。给 WP-3 的硬提醒（硬约束 19 / §4.4b）：
       判断舞台开关【只能用 sdk.stage.visible()】。实测 visible()===false 时
       stage.el() 仍返回 <DIV>（手册说返回 null 是错的）→ 任何 `if (stage.el())` 都会误判为已打开。
       core 未包装 stage，故此处仅留约定，不提供据 el() 判断的工具函数。 */
    ui: {}
  };
  W.SBK = SBK;

  if (claim('core')) bridge();   // 哨兵短路：预览重跑不会重复订阅（§4.2）
  log('core ready v' + SBK.version);
})(typeof window !== 'undefined' ? window : globalThis);
