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
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function snap(o) { var r = {}, k; for (k in o) if (has(o, k)) r[k] = o[k]; return r; }
  var state = {
    get: function () { return snap(st); },
    patch: function (p) {
      if (!p || typeof p !== 'object') return state.get();
      for (var k in p) if (has(p, k)) st[k] = p[k];
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
      if (!has(attrs, k)) continue;
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
     §7.3 statusbar 槽位仅当卡片 statusbar 字段非空才渲染 → 缺失时逐级回落。

     🚨 实机缺陷（同一 id 出现两次，已双重确认：截图 + DOM 计数）：
        boot 期调 mountHost 时 [data-slot="statusbar"] 【还没渲染出来】，于是走回落分支
        在 [data-slot="left"] 现造一个 #<id>（带 --float）；平台【随后】才把 statusbar 字段
        渲染出来，rule1 的 <div id="<id>" class="sbk-host"> 成为 statusbar 的直接子节点
        → 文档里两个同 id，且 chrome 的内容留在错误的槽位。
        故「选定一个槽位、只遍历它的直接子节点找同 id」是不够的：它既看不到当时还不存在的
        静态宿主，也无法事后发现自己造了重复。改为【全文档归一】+ 每轮 mount/done 复查。 */
  var hosts = {};        // id → 上一轮交付出去的宿主节点，供事后纠正与内容迁移

  /* 迁移用【搬】不用重建：appendChild 是移动语义，JS 直绑的 listener 随节点走
     （h() 走 addEventListener，见上方 §5.5 注释）→ 迁移后 chrome 的按钮仍可点。
     子节点撞 id（两边都建过自己的子容器，如 #<host>-chr）时留 keep 里【已有】的那个：
     它才是上层句柄当前持有的引用，用搬来的旧壳顶掉会让 chrome/pinned 对着摘下来的节点空写。
     ⚠ 撞 id 只认 keep 的【直接子节点】（dup.parentNode === keep）。写成「keep 子树里存在即算撞」
       会在 src 恰好嵌在 keep 内部时把 n 自己找出来，当成重复删掉 → 静默丢内容（已实测）。
       各层的子容器（-chr / .sbk-pin）本就都是宿主的直接子节点，直接子判定即足够。
     ⚠ keep.querySelector 走 Element.prototype（§4.3 明确它是原生实现），可靠；
       别改成 document.getElementById —— 那个被平台改写过。
     循环必然收敛：两条分支都把 n 从 src 摘掉（appendChild 是移动语义），
     src.childNodes 每轮严格减一 → 不需要额外的圈数上限。 */
  function adopt(keep, src) {
    if (!keep || !src || keep === src) return;
    var n, p;
    while (src.firstChild) {
      n = src.firstChild;
      p = n.id ? keep.querySelector('[id="' + n.id + '"]') : null;
      if (p && p.parentNode === keep) src.removeChild(n);
      else keep.appendChild(n);
    }
  }
  /* 全文档归一 + 挂载，同一个函数：同 id 只留一个。
     优先留 statusbar 的【直接子节点】—— 那是 rule1 的静态宿主，C.3 平台整体替换节点时
     会重新给到，是唯一稳定锚点；自造的回落节点则内容搬走后就地删掉。
     上一轮交付的节点若已被平台整体替换（C.3 innerHTML 注入）就不在 list 里 → 也搬过来。
     搬 grp 而不是让上层重建，还有一个作用：grp.parentNode 保持非空，
     ui.chrome 的补挂哨兵（!grp.parentNode 才重建）不会白跑一轮。 */
  function mountHost(id) {
    var hid = String(id || 'sbk-host');
    var d = W.document;
    // 硬约束 17：作者脚本早于 DOM 渲染（实测顶层取自己写入功能栏的节点得 null）。
    // root 不存在 = DOM 还没挂，此时任何挂载都是徒劳 → 明确报错，让调用方改到事件回调里。
    var root = d.querySelector('[data-chat="root"]');
    if (!root) { warn('mountHost: DOM not rendered yet (no [data-chat="root"]). Call it inside a mount/done handler.'); return null; }
    var sb = d.querySelector('[data-slot="statusbar"]'), slot = sb, got, i, n;
    /* §4.3 getElementById 被平台改写（走 gc 游标）→ 用属性选择器。
       querySelectorAll 只返回仍在文档里的节点 → 天然过滤掉已被平台摘掉的旧宿主。
       allInBubble 就是「带 try/catch 的 qsa」，名字虽带 inBubble 但对 document 一样适用。 */
    var list = allInBubble(d, '[id="' + hid + '"]');
    got = list[0];
    for (i = 0; i < list.length; i++) if (list[i].parentNode === sb) got = list[i];
    // 已有节点：归一后直接复用，绝不再造第二个（预览重跑同样走这条）
    if (!got) {
      if (!slot) {
        slot = d.querySelector('[data-slot="left"]');
        warn('statusbar slot missing (card statusbar field empty?), falling back to [data-slot="left"]');
      }
      // 末位回落 root 本身（flex 列容器），不用 body：body 在 root 之外，挂那里会脱离平台布局
      if (!slot) { slot = root; warn('no slot found, falling back to [data-chat="root"]'); }
      // slot!==sb 即走了回落 → 自己定位成浮层（.sbk-host--float，见 base.css）
      got = h('div', { id: hid, 'class': 'sbk-host' + (slot === sb ? '' : ' sbk-host--float') });
      slot.appendChild(got);
    }
    // 多余的同 id 节点：内容搬进 got 后就地删掉，保证全文档只剩一个。
    // list 来自 qsa → 每项都还在文档里，parentNode 必非空，不必再判。
    for (i = 0; i < list.length; i++) if ((n = list[i]) !== got) {
      adopt(got, n);
      n.parentNode.removeChild(n);
      warn('dup #' + hid + ' merged');
    }
    adopt(got, hosts[hid]);   // 上一轮的节点已被平台整体替换（C.3）→ 内容搬进来，别让渲染器空写
    hosts[hid] = got;
    return got;
  }

  /* 每轮 mount/done 复查一次：statusbar 迟到、平台整体替换槽位、切会话清空，都在这里收敛。
     mountHost 自身已是「先归一、没有才造、造完搬旧内容」→ 直接重调即可，无需另写一套。
     🚨 订阅写在模块级（core 装载即挂），故它排在 boot 期各渲染器的 mount 订阅【之前】
        → 每轮先归一宿主、再让 chrome/pinned 检查自己的节点，顺序不能反。
     🚨 §4.3 走 document 找平台级节点必须在回调【同步期】，故这里直接做，不进 schedule。 */
  function sweep() {
    // hosts 是本闭包私有的裸对象（无原型污染面）→ 不必 has() 过滤；
    // mountHost 只改写已有键、不新增键 → 边遍历边调安全
    for (var k in hosts) mountHost(k);
  }
  on('mount', sweep); on('done', sweep);

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

  /* ---------- modes 语义（2.0 重构） ----------
     1.0 是 {hud, snapshot} = 两个渲染器渲染【同一份 schema】，示例配置两个都开 →
     实机截图里同时出现两个一模一样的状态面板。且 hud 把状态数据放进功能栏，
     违反 MMD 惯例（功能栏放 chrome，状态栏在气泡内）。
     2.0 改为职责不同的三件东西：
       status = 气泡内状态面板（唯一的状态数据渲染器），默认开
       chrome = 功能栏入口按钮组（主题/设置/侧边栏），【不渲染业务数据】，默认开
       pinned = 功能栏常驻精简条，只显示 pinnedFields 指定的 1..3 项，默认关
     三者两两不重复：status 在气泡内，chrome 不含数据，pinned 形态被强制区分（单行无标签）。 */
  var MODES = { status: true, chrome: true, pinned: false };
  var PIN_MAX = 3;                       // 精简条上限，超出即截断（形态强制区分的一部分）

  /* 旧键别名归一化。老 config 不报错，但必须告警——
     ⚠ hud → pinned【不是等价替换】：旧 hud 是完整面板（含分组/标签/进度条），
       新 pinned 是单行精简条，只显示 1..3 项。做卡人必须知道形态变了。 */
  function normModes(m, ff) {
    var o = {}, k, warnf = typeof ff === 'function' ? ff : warn;
    for (k in MODES) if (has(MODES, k)) o[k] = MODES[k];
    if (!m || typeof m !== 'object') return o;
    if (has(m, 'snapshot') && !has(m, 'status')) {
      o.status = !!m.snapshot;
      warnf('modes.snapshot is the 1.0 name; renamed to modes.status (same meaning: in-bubble panel)');
    }
    if (has(m, 'hud') && !has(m, 'pinned')) {
      // 只在开着时才映射：hud:false 的老配置本就没有功能栏数据面板，静默按新默认走
      if (m.hud) {
        o.pinned = true;
        warnf('modes.hud is gone in 2.0. Mapped to modes.pinned, but semantics CHANGED: ' +
          'hud was a full panel in the toolbar, pinned is a single-line strip of 1..' + PIN_MAX +
          ' fields (set pinnedFields). The status panel now lives in the bubble (modes.status).');
      } else {
        warnf('modes.hud is gone in 2.0; ignored (it was false anyway). See modes.status/chrome/pinned.');
      }
    }
    for (k in MODES) if (has(MODES, k) && has(m, k)) o[k] = !!m[k];
    return o;
  }

  /* pinnedFields 归一化：去空、去重、截到 PIN_MAX。返回数组（可能为空）。 */
  function normPins(v) {
    var out = [], i, s;
    if (typeof v === 'string') v = [v];
    if (!v || !v.length) return out;
    for (i = 0; i < v.length && out.length < PIN_MAX; i++) {
      s = v[i] === null || v[i] === undefined ? '' : String(v[i]).trim();
      if (s && out.indexOf(s) < 0) out.push(s);
    }
    return out;
  }

  /* ---------- 功能栏精简条（modes.pinned） ----------
     🚨 形态与气泡面板【必须】不同，否则又变成同一份数据渲染两遍（1.0 的原缺陷）。
        这里靠三件事保证：① 只取 pinnedFields 的 1..3 项 ② 单行、无分组、无标签行、
        无进度条（值一律压成短文本）③ 自己的 class 命名空间 .sbk-pin*，不复用 .sbk-card/.sbk-col。
     🚨 硬约束 17：不在顶层挂 DOM（作者脚本早于 DOM 执行）→ 宿主在 mount/done 回调内才取。
     §5.6 功能栏静态（h_() 只在装载时跑一次，输入是 statusbar 字段自身）→
        精简条的刷新只能靠 JS 改 DOM，这正是它订阅 state/done 的原因。 */
  var PIN_LEN = 24;                      // 单项值最长字符数，超出截断（保住单行形态）
  function pinText(v) {
    // 把协议解析出的值压成【短文本】。bar 取 当前/上限，其余取 raw/value，绝不画条。
    if (v === null || v === undefined) return '';
    var t;
    if (typeof v !== 'object') t = String(v);
    else if (v.type === 'bar' && typeof v.value === 'number') {
      t = v.value + (typeof v.max === 'number' ? '/' + v.max : '');
    } else if (typeof v.raw === 'string' && v.raw) t = v.raw;
    else if (v.value !== null && v.value !== undefined && typeof v.value !== 'object') t = String(v.value);
    else t = '';
    /* 🚨 精简条是【单行】形态：entities/tags 的 raw 可能很长（「苏九=5, 阿澈=25, 王三=99」），
       不截断就会把功能栏挤成多行，形态又和气泡面板没区别了（设计文档第二节）。
       截断而非整项丢弃：丢弃会让做卡人看到「配了字段但凭空消失」，比截断难排查得多。 */
    return t.length > PIN_LEN ? t.slice(0, PIN_LEN - 1) + '…' : t;
  }

  function pinned(keys, hostId) {
    var ks = normPins(keys), host = null, hid = String(hostId || 'sbk-pin');
    function draw() {
      if (!host) return;
      var s = state.get(), i, k, t, row;
      while (host.firstChild) host.removeChild(host.firstChild);
      row = h('div', { 'class': 'sbk-pin' });          // 单行容器，与 .sbk-card 无关
      for (i = 0; i < ks.length; i++) {
        k = ks[i];
        t = pinText(s[k]);
        if (!t) continue;                              // 无值不占位，避免空标签
        // 每项一个 chip：键名小字 + 值。无 label 行、无独立标题，故不会像气泡面板。
        row.appendChild(h('span', { 'class': 'sbk-pin-item' }, [
          h('span', { 'class': 'sbk-pin-k' }, k), h('span', { 'class': 'sbk-pin-v' }, t)
        ]));
      }
      host.appendChild(row);
    }
    function paint() { schedule(draw); }
    function ensure(sync) {
      /* §4.3：mountHost 走 document 找平台级节点，必须在事件回调【同步期】调，不能推到 rAF 里。
         🚨 每次都重取（不再 `if (!host)` 短路）：C.3 平台会整体替换槽位节点，缓存的
            host 可能已被摘下 → 那时 draw 会往一个不在文档里的节点空写，精简条凭空消失。
            mountHost 现在自带全文档归一 + 内容迁移，重复调既幂等也不会造重复宿主。 */
      if (sync) host = mountHost(hid) || host;
      return !!host;
    }
    function feed(text) {
      // 只吃 AI 消息由调用方保证。parse 缺层时返回 null（core 占位实现），静默不更新。
      var r = SBK.parse(text);
      if (!r || !r.state) return false;
      state.patch(r.state);                            // patch 会 emit('state') → paint
      return true;
    }
    state.subscribe(paint);
    on('mount', function () { if (ensure(1)) paint(); });
    on('done', function (p, root) {
      if (!ensure(1)) return;
      // 载荷字段名就是 content（§4.4c 实测）。role 缺失时放行，宁可回旧行为也不失灵。
      if (!p || p.role === undefined || p.role === null || p.role === 'ai') {
        feed(p && typeof p.content === 'string' ? p.content : '');
      }
      paint();
    });
    return { el: function () { return host; }, render: paint, feed: feed, mount: ensure, keys: function () { return ks.slice(); } };
  }

  var booted = null;   // 句柄缓存：重跑时原样返回，调用方拿到的始终是同一个

  function boot(opts) {
    // §3 创卡页预览反复重跑整卡脚本 + §4.2 sdk.on 无 off/once → 重复 boot 会让订阅翻倍。
    // 哨兵短路：第二次起直接返回首次的句柄，不再挂任何订阅。
    if (!claim('boot')) { log('boot already done, returning existing handle'); return booted; }

    var o = opts && typeof opts === 'object' ? opts : {};
    var md = normModes(o.modes);                 // status/chrome/pinned + 旧键别名归一化（含告警）
    var pins = normPins(o.pinnedFields);
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
       故此处【绝不】在顶层挂任何 DOM —— 只 new 出渲染器，宿主容器由它自己在事件回调内取。
       🚨 §4.1 实测冷启动顺序 message:new > message:mount > message:done > ready：
          ready【最后】到且无补发，只有 mount/done 有补发 → 各渲染器订阅的正是 mount/done，
          这里不得改挂 ready，否则首屏晚一整轮且历史气泡拿不到补发。 */

    // status（唯一的状态数据渲染器，位置在气泡内）：
    // snapshot.auto 自己挂 mount/done 做 hydrate（mount 有补发，历史气泡也会被升级）
    var statusOn = false;
    if (md.status) {
      if (SBK.ui && SBK.ui.snapshot && typeof SBK.ui.snapshot.auto === 'function') {
        try { SBK.ui.snapshot.auto(sc); statusOn = true; }
        catch (e) { skipped.push('status'); warn('boot: snapshot.auto threw', e && e.message); }
      } else { skipped.push('status'); warn('boot: SBK.ui.snapshot not loaded, status panel disabled'); }
    }

    // chrome（功能栏入口按钮组，【不渲染业务数据】）：由 WP-C 的 ui.js 提供
    var chromeOn = false;
    if (md.chrome) {
      if (SBK.ui && typeof SBK.ui.chrome === 'function') {
        try { SBK.ui.chrome({ hostId: o.hostId || 'sbk-hud' }); chromeOn = true; }
        catch (e) { skipped.push('chrome'); warn('boot: ui.chrome threw', e && e.message); }
      } else { skipped.push('chrome'); warn('boot: SBK.ui.chrome not loaded, toolbar entries disabled'); }
    }

    /* pinned（功能栏精简条）：core 自带实现，不依赖 ui 层。缺 pinnedFields 则整个模式不启动。
       🚨 宿主必须与 chrome 【分开】：精简条每次重绘都会清空自己宿主的全部子节点，
          若与 chrome 共用 #sbk-hud，第一次 state 变化就会把入口按钮全部擦掉。
          故取 hostId + '-pin'，在功能栏槽位里做 chrome 的兄弟节点
          （mountHost 找不到就用 JS 建，实机验证过 JS 插入的节点整页重载后仍在，见设计文档 §2.2）。 */
    var pin = null;
    if (md.pinned) {
      if (!pins.length) {
        skipped.push('pinned');
        warn('boot: modes.pinned is on but pinnedFields is empty — nothing to show, strip skipped');
      } else pin = pinned(pins, (o.hostId || 'sbk-hud') + '-pin');
    }

    booted = {
      schema: sc,
      // 实际生效值（非请求值）：缺层被跳过的模式在这里是 false，方便实机自查
      modes: { status: statusOn, chrome: chromeOn, pinned: !!pin },
      pinnedFields: pins,
      skipped: skipped,
      pinned: pin,                                         // 精简条句柄（el/render/feed/mount/keys），关闭时 null
      el: function () { return pin ? pin.el() : null; },
      render: function () { if (pin) pin.render(); },
      feed: function (text) { return pin ? pin.feed(text) : false; },
      /* dispose 只回收【看得见的产物】：主题样式 + 精简条宿主内容。
         §4.2 无 off/once，各渲染器是用匿名函数订阅内部总线的，没有函数引用可撤 →
         订阅留着。故【不释放 boot 哨兵】：再 boot 只会拿回旧句柄，不会二次订阅。 */
      dispose: function () {
        if (SBK.theme && typeof SBK.theme.reset === 'function') { try { SBK.theme.reset(); } catch (e) {} }
        var host = pin ? pin.el() : null;
        if (host) { while (host.firstChild) host.removeChild(host.firstChild); }
        warn('boot: disposed visuals only; event subscriptions are not revocable (§4.2)');
      }
    };
    log('boot done: status=' + statusOn + ' chrome=' + chromeOn + ' pinned=' + !!pin +
      (skipped.length ? ' skipped=' + skipped.join(',') : ''));
    return booted;
  }

  /* ---------- 导出 ---------- */
  var SBK = {
    version: '1',
    claim: claim,
    boot: boot,             // 唯一编排入口，生成器的 sbk-boot 规则调它
    schema: normSchema,     // schema 归一化（rows → fields），供直接调渲染器的做卡人复用
    modes: normModes,       // modes 归一化（旧 hud/snapshot 别名 → status/chrome/pinned）
    pins: normPins,         // pinnedFields 归一化（去空去重、截到 3 项）
    pinned: pinned,         // 功能栏精简条渲染器，core 自带（不依赖 ui 层）
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
