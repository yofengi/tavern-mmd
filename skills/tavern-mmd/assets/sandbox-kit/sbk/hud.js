/* SBK hud —— 双模状态栏渲染器。依据：资料/基座事实卡.md、plan.md §2.2
   模式 A 常驻 HUD（JS 改 DOM）／模式 B 消息内快照（HTML 字符串）。共用一份 vnode 与控件表。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] hud.js loaded before core.js');
    return;
  }
  if (!SBK.claim('hud')) return;   // 预览重跑幂等（§3/§4.2）

  /* ---------- vnode ----------
     {t:标签, c:class, s:style, x:文本, k:子节点}
     一份结构，两条出口：toDom 走 SBK.dom.h（模式 A），toHtml 拼字符串（模式 B）。
     模式 B 必须返回字符串（要塞进正则 replaceString），故【不能】用 dom.h。 */
  function esc(s) {
    // 把 > 也转义掉，顺带根治 §5.5：属性值/文本里的 ]> 与 --> 命中 SAFE_FOR_XML 会让整条属性被删
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function toDom(v) {
    var a = {};
    if (v.c) a['class'] = v.c;
    if (v.s) a.style = v.s;
    if (v.on) a.onclick = v.on;         // dom.h 见 function 型 on* 走 addEventListener，不过净化器
    var kids = v.k ? v.k.map(toDom) : null;
    return SBK.dom.h(v.t || 'div', a, v.x !== undefined ? String(v.x) : kids);
  }
  function toHtml(v) {
    var t = v.t || 'div', s = '<' + t;
    if (v.c) s += ' class="' + esc(v.c) + '"';
    if (v.s) s += ' style="' + esc(v.s) + '"';
    s += '>';
    if (v.x !== undefined) s += esc(v.x);
    else if (v.k) for (var i = 0; i < v.k.length; i++) s += toHtml(v.k[i]);
    return s + '</' + t + '>';
  }

  /* base.css 已有的原语，这里只组合不新增类名（base.css 属 WP-1） */
  function row(label, kids) {
    var k = [];
    if (label) k.push({ t: 'span', c: 'sbk-label', x: label });
    return { t: 'div', c: 'sbk-row', k: k.concat(kids) };
  }
  function val(x, grow) { return { t: 'span', c: 'sbk-val' + (grow ? ' sbk-grow' : ''), x: x }; }

  /* ---------- 控件表 ----------
     f = {key,label,type,value,max,unit,opt}。可扩展：SBK.ui.hud.type('自定义', fn)。
     🚨 配色一律 var(--chat-*)，零硬编码色值：写死颜色会让平台深浅色切换失效（§7.1）。
        §9 实测深色 --chat-accent:#ff6d97，只作视觉参考，代码里仍用变量。 */
  function pct(v, m) { return m > 0 ? Math.max(0, Math.min(100, v / m * 100)) : 0; }
  var TYPES = {
    bar: function (f) {
      var p = pct(f.value, f.max), tx = f.unit === '%' ? f.value + '%' : f.value + '/' + f.max;
      return row(f.label, [
        { t: 'div', c: 'sbk-bar sbk-grow', k: [{ t: 'div', c: 'sbk-bar__fill', s: 'width:' + p.toFixed(1) + '%' }] },
        val(tx)
      ]);
    },
    num: function (f) { return row(f.label, [val(String(f.value) + (f.unit || ''), 1)]); },
    text: function (f) { return row(f.label, [val(f.value, 1)]); },
    tags: function (f) {
      var k = [], a = f.value, i;
      for (i = 0; i < a.length; i++) k.push({ t: 'span', c: 'sbk-chip', x: a[i] });
      return { t: 'div', c: 'sbk-row sbk-row--wrap', k: (f.label ? [{ t: 'span', c: 'sbk-label', x: f.label }] : []).concat(k) };
    },
    entities: function (f) {
      var k = [], a = f.value, i, e, top = 0;
      for (i = 0; i < a.length; i++) if (a[i].value > top) top = a[i].value;
      if (top <= 0) top = 1;
      for (i = 0; i < a.length; i++) {
        e = a[i];
        k.push(row(e.name, [
          { t: 'div', c: 'sbk-bar sbk-grow', k: [{ t: 'div', c: 'sbk-bar__fill', s: 'width:' + pct(e.value, f.max || top).toFixed(1) + '%' }] },
          val(String(e.value))
        ]));
      }
      if (f.label) k.unshift({ t: 'span', c: 'sbk-label', x: f.label });
      return { t: 'div', c: 'sbk-col', k: k };
    }
  };

  /* ---------- schema → 字段列表 ----------
     schema = { title?, fields?: [ {key,label?,type?,max?,unit?} | '键名' ], extra?:true, persist?:true }
     fields 缺省 = 按模型输出顺序全渲染（order 由 SBK.parse 给出）。 */
  /* schema 里 type 覆写后，值的形态可能与控件不符（把 text 强制成 tags 等）。
     不 coerce 的话 tags 渲染器会把字符串按【字符】迭代，一个字一个 chip。
     所以按目标类型重新分类一次，让「type 覆写」在任何输入上都安全。 */
  function fit(type, v, raw) {
    var re;
    if (type === 'tags') return Array.isArray(v) ? v : (re = SBK.parse.value(raw), Array.isArray(re.value) ? re.value : [String(v)]);
    if (type === 'entities') return Array.isArray(v) ? v : [];
    if (type === 'bar' || type === 'num') {
      if (typeof v === 'number') return v;
      re = SBK.parse.value(raw);
      return typeof re.value === 'number' ? re.value : 0;
    }
    return typeof v === 'string' ? v : (Array.isArray(v) ? v.join(', ') : String(raw === undefined ? v : raw));
  }
  function cell(key, raw, def) {
    var f = raw;
    // 允许业务方直接 patch 原始值（state.patch({血量:'72/100'})）→ 这里补跑一次分类器
    if (!f || typeof f !== 'object' || !f.type) f = SBK.parse.value(f === undefined || f === null ? '' : f);
    def = def || {};
    var ty = def.type || f.type;
    var mx = def.max !== undefined ? def.max : f.max;
    // 强制成 bar 却没给上限（「金币: 380」+ type:'bar'）→ 按百分比常规取 100，
    // 否则会渲染出 "380/undefined" 和 0% 宽度的空条
    if (ty === 'bar' && !(typeof mx === 'number' && isFinite(mx) && mx !== 0)) mx = 100;
    return {
      key: key, label: def.label === undefined ? key : def.label,
      type: ty, value: ty === f.type ? f.value : fit(ty, f.value, f.raw),
      max: mx, unit: def.unit || f.unit, opt: def
    };
  }
  function pick(state, schema, order) {
    var sc = schema || {}, out = [], seen = {}, defs = sc.fields, i, d, k;
    if (defs && defs.length) {
      for (i = 0; i < defs.length; i++) {
        d = typeof defs[i] === 'string' ? { key: defs[i] } : (defs[i] || {});
        k = d.key;
        if (!k) continue;
        seen[k] = 1;
        // 声明了但本轮模型没输出 → 跳过而不是渲染空行（缺项容错）
        if (!Object.prototype.hasOwnProperty.call(state, k)) continue;
        out.push(cell(k, state[k], d));
      }
      if (sc.extra !== true) return out;
    }
    var ord = order && order.length ? order : Object.keys(state);
    for (i = 0; i < ord.length; i++) {
      k = ord[i];
      if (seen[k] || k.charAt(0) === '_') continue;   // _ 前缀为内部字段，不渲染
      if (!Object.prototype.hasOwnProperty.call(state, k)) continue;
      out.push(cell(k, state[k], null));
    }
    return out;
  }
  function tree(state, schema, order) {
    var fs = pick(state, schema, order), k = [], i, fn;
    if (schema && schema.title) k.push({ t: 'div', c: 'sbk-label', x: schema.title });
    for (i = 0; i < fs.length; i++) {
      fn = TYPES[fs[i].type] || TYPES.text;
      try { k.push(fn(fs[i])); } catch (e) { SBK.warn('hud: renderer threw for ' + fs[i].key); }
    }
    return k;
  }

  /* 从 message:* 载荷里取正文。
     🚨 探针3 实测（2026-08-26）：message:new / message:mount / message:done 三者载荷形状
        【完全一致】，恰 4 键 {content, id, role, serverId}：
          content  string  正文，就是这个字段，不用试探别名
          id       string  【字符串】非数字，开场白为 "greeting"
          role     string  'ai' | 'user'
          serverId object  null 表示服务端还不认得这条消息（不可 message.edit）
        ready 载荷是 undefined，纯时序信号，取不到正文 → 别想从 ready 拿正文。
     bubbleRoot 兜底保留作平台改版保险。注意它是【内核桥接层合成的第二参】：
        SDK 回调本身只给 1 个实参（实测 argcount=1），fn(payload, bubbleRoot) 是基座契约
        而非 SDK 行为。§4.3：气泡根只能在回调内同步取得，禁止自己 document.querySelector 查气泡内元素。 */
  function textOf(p, root) {
    if (p && typeof p.content === 'string') return p.content;
    if (typeof p === 'string') return p;                                  // 平台改版直接给字符串
    if (root && typeof root.textContent === 'string') return root.textContent;
    return '';
  }

  /* ---------- 模式 A：常驻 HUD ----------
     🚨 §5.6 功能栏是静态的：h_() 只在装载时跑一次，且其正则输入是 statusbar 字段【自身】
        而非消息内容，主包里没有任何重渲染路径。→ 状态栏能跟着对话变，【只能】靠这里改 DOM，
        指望正则刷新一定失败。这是整个双模设计的前提（硬约束 14）。
     🚨 硬约束 17：作者脚本早于 DOM 执行（实测顶层 getElementById 返回 null）→ 宿主必须在
        事件回调内取。首屏挂 mount/done（有补发），不能等 ready：§4.1 实测顺序
        message:new > message:mount > message:done > ready，ready【最后】到且无补发。 */
  function hud(hostEl, schema) {
    var sc = schema || {}, host = hostEl || null, order = null;

    function draw() {
      if (!host) return;
      var kids = tree(SBK.state.get(), sc, order), i;
      // 整树重建：HUD 字段个数是个位数，diff 的复杂度不值得。清空前先断开引用避免泄漏。
      while (host.firstChild) host.removeChild(host.firstChild);
      var box = SBK.dom.h('div', { 'class': 'sbk-card sbk-col sbk-hud' });
      for (i = 0; i < kids.length; i++) box.appendChild(toDom(kids[i]));
      host.appendChild(box);
    }
    // §5 message:stream 触发极密 → rAF 合帧。draw 引用稳定，schedule 内部按 fn 去重，
    // 一帧内 N 次 patch 只重绘一次。
    function paint() { SBK.schedule(draw); }

    function ensure(sync) {
      // mountHost 内部走 document.querySelector 找 [data-chat="root"]/[data-slot="statusbar"]：
      // §4.3 实机修正 —— 平台级节点在 mount 回调内可达，气泡内元素才受 gc 收窄影响。
      // 故必须在【事件回调同步期】调用，不能推到 rAF 里（那时 gc 已回落 null）。
      if (!host && sync) host = SBK.dom.mountHost(sc.hostId || 'sbk-hud');
      return !!host;
    }

    function feed(text) {
      var r = SBK.parse(text), i, k;
      if (!r) return false;
      // order 必须【累积】而不是替换：state 是 patch 语义（旧字段留着），若 order 只留本轮的键，
      // 模型某轮没提「金币」就会让它从 HUD 上凭空消失。新键追加在尾部，老键保持原位。
      if (!order) order = [];
      for (i = 0; i < r.order.length; i++) { k = r.order[i]; if (order.indexOf(k) < 0) order.push(k); }
      SBK.state.patch(r.state);        // patch 会 emit('state') → 下面的 subscribe 触发重绘
      if (sc.persist) SBK.store.save();
      return true;
    }

    if (sc.persist) {
      // 硬约束 18：瘦预览下 save.get/keys 同步抛 SdkError。core 的 store.load 已 try/catch 兜住。
      var saved = SBK.store.load();
      if (saved && typeof saved === 'object') SBK.state.replace(saved);
    }
    /* 只吃 AI 消息的状态块。探针3 确证载荷带 role（'ai'|'user'）。
       §5.6「用户消息不跑规则」只保护了模式 B 的正则路径；HUD 走的是 JS 事件，
       用户自己在输入框打一句 [状态]血量: 999/100[/状态] 会被照单全收 → 必须挡。
       role 缺失时放行：平台改版删了这个字段的话，宁可回到旧行为也不要整个状态栏失灵。 */
    function fromAI(p) { return !p || p.role === undefined || p.role === null || p.role === 'ai'; }

    SBK.state.subscribe(paint);
    SBK.on('mount', function (p, root) { if (ensure(1)) paint(); });
    SBK.on('done', function (p, root) {
      if (!ensure(1)) return;
      if (fromAI(p)) feed(textOf(p, root));
      paint();
    });

    if (host) paint();
    return { el: function () { return host; }, render: paint, feed: feed, mount: ensure };
  }
  hud.type = function (name, fn) { if (name && typeof fn === 'function') TYPES[String(name)] = fn; return hud; };
  hud.types = function () { return Object.keys(TYPES); };

  /* ---------- 模式 B：消息内快照 ----------
     返回 HTML 字符串（要塞进正则 replaceString，故【不能】用 dom.h）。
     🚨 已裁决第 4 条：根元素必须带 .sbk-snap —— base.css 靠它把 message-body 的
        opacity:.9 与 white-space:pre-line 重置掉（§7.3 / 硬约束 11），少这个类排版必烂。
     🚨 净化合规（§5.5）：无自写 data-* 属性（全删）、无 aria 属性与 role（ALLOW_ARIA_ATTR:!1 全删）、
        属性值经 esc() 后不可能含 ]> 或 -->（SAFE_FOR_XML 会删整条属性）。
        标签只用 div/span（§5.4 worker 白名单 ∩ DOMPurify）。
     🚨 §5.2 单条规则输出预算 max(262144, 输入长度×4)，超限【整条回滚】→ 产物必须紧凑：
        无缩进、无换行、无注释，class 名复用 base.css 已有原语。 */
  function snapshot(state, schema) {
    var st = state, ord = null;
    if (st && typeof st === 'object' && st.state && typeof st.state === 'object') {
      ord = st.order; st = st.state;    // 容忍直接把 SBK.parse 的返回值传进来
    }
    if (!st || typeof st !== 'object') return '';
    var kids = tree(st, schema || {}, ord), s = '', i;
    for (i = 0; i < kids.length; i++) s += toHtml(kids[i]);
    if (!s) return '';
    return '<div class="sbk-snap sbk-card sbk-col">' + s + '</div>';
  }

  /* 升级：正则把 <状态>…</状态> 换成 <div class="sbk-snap sbk-snap--raw">原文</div>（纯文本，
     不含 HTML，天然安全），这里在 mount 回调内把它解析并替换成真渲染。
     好处是模式 B 不需要正则会算百分比 —— 正则只搬字符串，计算全在 JS。
     §4.3：必须用回调给的 root（dom.all 在 root 上查，走 Element.prototype 原生实现，不受 gc 影响）。 */
  function hydrate(root, schema) {
    var nodes = SBK.dom.all(root, '.sbk-snap--raw'), i, n, r, kids, box, j;
    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      if (n.getAttribute('class').indexOf('sbk-snap--done') >= 0) continue;   // 幂等：mount 可能补发
      var tx = n.textContent;
      r = SBK.parse(tx);
      // §5.4 剥壳在正则管线【之后】跑：若做卡人的 replaceString 原样吐回 <状态>，这个中文标签
      // 会被当非白名单标签删掉，此处拿到的就是裸行。补回方括号标记再试一次，两种写法都能活。
      if (!r || !r.order.length) {
        var w = SBK.parse(SBK.parse.wrap(tx));
        // 只在真解析出字段时才采纳：否则一段普通文字会被「成功解析成空块」而被清空
        if (w && w.order.length) r = w;
      }
      // 解析不出来就原样留着（.sbk-pre 保住换行），比清空成空白块友好
      if (!r || !r.order.length) { n.setAttribute('class', 'sbk-snap sbk-pre sbk-snap--raw sbk-snap--done'); continue; }
      kids = tree(r.state, schema || {}, r.order);
      while (n.firstChild) n.removeChild(n.firstChild);
      box = SBK.dom.h('div', { 'class': 'sbk-card sbk-col' });
      for (j = 0; j < kids.length; j++) box.appendChild(toDom(kids[j]));
      n.appendChild(box);
      n.setAttribute('class', 'sbk-snap sbk-snap--raw sbk-snap--done');
    }
    return nodes.length;
  }
  snapshot.hydrate = hydrate;
  // 自动升级开关：装一次即可，mount 有补发（§4.1）故历史气泡也会被处理
  snapshot.auto = function (schema) {
    SBK.on('mount', function (p, root) { if (root) hydrate(root, schema); });
    SBK.on('done', function (p, root) { if (root) hydrate(root, schema); });
    return snapshot;
  };

  /* 合并而非覆盖：WP-3 的 ui.js 会往同一个 SBK.ui 上挂 panel/stage，直接赋新对象会互相踩掉 */
  SBK.ui = SBK.ui || {};
  SBK.ui.hud = hud;
  SBK.ui.snapshot = snapshot;
  SBK.log('hud ready, types=' + hud.types().join(','));
})(typeof window !== 'undefined' ? window : globalThis);
