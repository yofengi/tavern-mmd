/* SBK theme —— 主题层。挂到 core.js 建立的同一个 window.SBK 上。依据：基座事实卡.md §7.1 / 包分析-CSS D 节 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) { (W.console && W.console.warn) && W.console.warn('[SBK] theme.js loaded before core.js'); return; }
  if (!SBK.claim('theme')) return;   // 预览重跑幂等（§3/§4.2）

  var d = W.document;
  var STYLE_ID = 'sbk-theme-vars';

  /* §7.1 平台每套 14 个变量，定义在 [data-theme=dark]（L1234）与 [data-theme=light]（L1250）。
     手册只记 10 个，漏 share-pick-bg / input-bg / input-text / shortcut-text / more-item-bg。
     ⚠ 无 :root 定义、无 prefers-color-scheme → 覆盖 :root 不生效。
     ⚠ --chat-viewport-height 不在此列：JS 写在 root 的内联 style（随 visualViewport 更新），CSS 覆盖不了。
     ⚠ --rpx = calc(100vw / 750) 是平台尺寸基准，改它整体错位 → 只读不写。 */
  var VARS = ['bg', 'surface', 'text', 'text-muted', 'border', 'accent',
    'bubble-user-bg', 'bubble-ai-bg', 'bubble-text',
    'share-pick-bg', 'input-bg', 'input-text', 'shortcut-text', 'more-item-bg'];

  /* 语义 token → 平台 --chat-* 映射。作者写语义名，基座翻译。 */
  var MAP = {
    bg: 'bg', surface: 'surface', panel: 'surface', text: 'text', muted: 'text-muted',
    border: 'border', accent: 'accent', primary: 'accent',
    userBubble: 'bubble-user-bg', aiBubble: 'bubble-ai-bg', bubbleText: 'bubble-text',
    sharePick: 'share-pick-bg', inputBg: 'input-bg', inputText: 'input-text',
    shortcutText: 'shortcut-text', moreItemBg: 'more-item-bg'
  };

  function toVar(k) {
    if (k.indexOf('--') === 0) return k;                 // 直给 --chat-* 或自定义 --sbk-*
    if (MAP[k]) return '--chat-' + MAP[k];
    if (VARS.indexOf(k) >= 0) return '--chat-' + k;      // 直给平台后缀名
    // 未知语义名收进基座私有命名空间，camelCase → kebab（onAccent → --sbk-on-accent，对齐 base.css）
    return '--sbk-' + k.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
  }

  /* 硬约束 20 / §9：实测 [data-chat="root"] 带【内联】style：
       --chat-viewport-height:1205px; background-image:url(https://r2.aitchat.org/…)
     内联样式优先级高于任何选择器特异度 → 换页面背景【必须 !important】。
     这是全基座唯一需要 !important 的地方；其余 --chat-* 变量靠 (0,2,0) 特异度即可，不加。
     ⚠ 只改 --chat-bg 换不掉背景图：内联写的是 background-image 属性本身，不是变量。 */
  var PAGE = {
    pageBg: 'background-color', pageBgImage: 'background-image',
    pageBgSize: 'background-size', pageBgPosition: 'background-position',
    pageBgRepeat: 'background-repeat'
  };

  function decls(tokens) {
    var out = '', k, v, prop;
    for (k in tokens) {
      if (!Object.prototype.hasOwnProperty.call(tokens, k)) continue;
      v = tokens[k];
      if (v === null || v === undefined || v === '') continue;
      v = String(v);
      // 值里出现 } 或 </style 会截断样式块；直接丢弃并告警
      if (v.indexOf('}') >= 0 || /<\/style/i.test(v)) { SBK.warn('theme token value rejected: ' + k); continue; }
      prop = PAGE[k];
      if (prop) { out += prop + ':' + v + ' !important;'; continue; }   // 仅此处加 !important
      out += toVar(k) + ':' + v + ';';
    }
    return out;
  }

  /* §7.1 + CSS D 节：平台令牌在 [data-theme=dark]，特异度 (0,1,0)；data-theme 与 data-chat=root
     绑在【同一个 div】上。故写 [data-chat="root"][data-theme="dark"] 得 (0,2,0)，高于平台
     → 深浅色切换不会覆盖回去，且【不需要 !important】。
     只写 [data-theme=dark] 是同特异度靠源顺序取胜（脆）；只写 :root 完全无效。 */
  function sel(mode) { return '[data-chat="root"][data-theme="' + mode + '"]'; }

  function styleNode() {
    // 单节点 + 固定 id，重复调用【替换而非追加】，避免创卡页预览重跑堆积一堆 <style>（§3）
    var el = null, kids = (d.head || d.documentElement).childNodes, i;
    for (i = 0; i < kids.length; i++) if (kids[i] && kids[i].nodeType === 1 && kids[i].id === STYLE_ID) { el = kids[i]; break; }
    if (!el) {
      el = d.createElement('style');
      el.id = STYLE_ID;
      (d.head || d.documentElement).appendChild(el);
    }
    return el;
  }

  var current = null;   // 最近一次 apply 的入参，便于上层回读

  /* apply(tokens, extraCss)
     - apply({bg:'#111', ...})                 → 两套主题同值
     - apply({dark:{...}, light:{...}})        → 分别覆盖
     - apply('native') / apply(null)           → 三态之 native：不覆盖，完全跟随平台
     extraCss 是【内部参数】（prefs 层用它桥 fontSize/lineHeight，见 bridge()）：
     令牌覆盖只能改 var()，而 base.css 把 .sbk-host 的 font-size/line-height 写成了
     具体声明，不改这两条真值就调不动字号行距。对外仍是 1.0 的单参语义，作者不必知道。 */
  function apply(tokens, extraCss) {
    var node = styleNode();
    if (!tokens || tokens === 'native') {
      // 清空即回到 native。⚠ extraCss 也一并丢弃：native 必须是【真】native（盘点 B.4）
      node.textContent = '';
      current = null;
      SBK.emit('theme', mode());
      return;
    }
    var css = '', dark, light;
    if (tokens.dark || tokens.light) { dark = tokens.dark; light = tokens.light; }
    else { dark = tokens; light = tokens; }
    if (dark) css += sel('dark') + '{' + decls(dark) + '}';
    if (light) css += sel('light') + '{' + decls(light) + '}';
    if (typeof extraCss === 'string' && extraCss) css += extraCss;
    node.textContent = css;
    current = tokens;
    SBK.emit('theme', mode());
  }

  /* mode() 读当前平台深浅色。
     ⚠ SDK 没有暴露读主题的方法，且 theme:change 有去重（值真变才派发，初值就是 dark），
        所以初始主题【只能从 DOM 读】，不能等事件。 */
  function mode() {
    var root = d.querySelector('[data-chat="root"]');
    var v = root && root.getAttribute ? root.getAttribute('data-theme') : null;
    return v === 'light' ? 'light' : 'dark';
  }

  function onChange(fn) {
    if (typeof fn !== 'function') return function () {};
    SBK.on('theme', fn);
    try { fn(mode()); } catch (e) { SBK.warn('theme.onChange initial call threw'); }  // 初值不派发，手动补一次
    return function () { SBK.off('theme', fn); };
  }

  /* §9 深色主题实测真值（探针读 getComputedStyle 所得，14 个变量全部存在）。
     供作者「微调而非全替」时作基线：SBK.theme.apply(SBK.theme.base()) 再改几项。
     ⚠ 三个背景实测同色（页面/用户气泡/AI 气泡均 #17181a）→ 想做气泡与页面分层必须自己拉开对比。 */
  var DARK = {
    bg: '#17181a', surface: '#1e1f24', text: '#fff', muted: '#c5c5c5',
    border: '#333', accent: '#ff6d97',
    userBubble: '#17181a', aiBubble: '#17181a', bubbleText: '#fff',
    inputBg: '#1e1f24', inputText: '#fff', shortcutText: '#fff',
    moreItemBg: '#2c2e32', sharePick: '#2c2e32'
  };

  /* ================= preset + overrides 两层合成（2.0 §4 / 盘点 B.5） =================
     1.0 的 theme.js 是【无状态涂色器】：apply 写一个 <style>，current() 只回读入参，
     玩家改了什么、刷新后还在不在、怎么与作者 preset 合成 —— 完全没有这一层。

     🚨 合成纪律（盘点 B.5 第 1 条，最容易做错且代价很大）：
        resolved(mode) = PRESET[name][mode] + overrides[mode]
        preset 默认值【只存在于源码，绝不写入偏好】。每次都按「当前版本的 preset +
        合法 overrides」重新合成 → 作者升级 preset 后，新默认能作用到玩家【从未改过】的字段。
        若把 preset 快照进存档，玩家的旧快照会永久钉死旧默认值。
     🚨 overrides.dark 与 overrides.light 【分开存】，切换不串值（盘点 B.5 第 3 条）。
     🚨 写回默认值时【删除】该 override，而不是存一份等于默认的值（第 2 条）——
        否则同上，这个字段就再也跟不上 preset 升级了。 */

  /* 作者预置的风格包。key 是包名，值是 {dark:{…},light:{…}} 或扁平（两套同值）。
     ⚠ 盘点 E.3：平台强制两套主题都存在（用户随时可能切），所以风格包【必须两侧都备】。
       只给一侧时另一侧回落到平台原生令牌，会出现「切到浅色整卡失效」。 */
  var PRESETS = {};
  var presetName = '';

  /* 玩家微调字段表。ui.js 直接 for 这张表建控件 —— 控件清单的【唯一真源】在这里，
     不在 ui.js，这样加一个微调项只改本文件一处。
     🚨 语义漂移（2.0 §4.1 / 盘点 B.3）：这里【没有】「日间/夜间/原生」三按钮。
        旧三态 day/night 由玩家选；沙盒的 light|dark 是【平台级】，作者只能读 data-theme
        与跟随 theme:change，【写不动】。玩家按了也切不动 → 放上去就是坏控件。
        取代物是「风格包选择」（作者预置多套，玩家挑）+「启用美化」开关（对应旧 native）。
     tone: 落到哪个语义 token（toVar 再翻成 --chat-* / --sbk-*）；null = 需要特殊桥接。 */
  var FIELDS = [
    { key: 'fontSize', label: '字号', kind: 'int', min: 12, max: 32, step: 1, def: 24, unit: 'rpx', tone: 'fs' },
    { key: 'lineHeight', label: '行距', kind: 'num', min: 1.1, max: 2.6, step: 0.1, def: 1.5, tone: 'lh' },
    { key: 'textColor', label: '正文色', kind: 'color', tone: 'text' },
    { key: 'accentColor', label: '强调色', kind: 'color', tone: 'accent' },
    { key: 'aiBubbleColor', label: '气泡色', kind: 'color', tone: 'aiBubble' },
    { key: 'opacity', label: '气泡透明度', kind: 'int', min: 40, max: 100, step: 1, def: 100, unit: '%', tone: null }
  ];
  var FMAP = {};
  (function () { for (var i = 0; i < FIELDS.length; i++) FMAP[FIELDS[i].key] = FIELDS[i]; })();

  /* 逐字段验证（盘点 B.6：规则整体照抄，只换载体）。
     它防的是「玩家存档被改坏 → 整卡起不来」，与平台无关 —— 所以非法值一律
     【逐字段丢弃并回落默认】，绝不让 bootstrap 失败（B.5 第 5 条）。 */
  var HEX = /^#[0-9a-fA-F]{6}$/;
  function okField(k, v) {
    var f = FMAP[k];
    if (!f) return false;                                     // 未知键：拒
    if (f.kind === 'color') return typeof v === 'string' && HEX.test(v);   // 严格 #RRGGBB
    if (typeof v !== 'number' || !isFinite(v)) return false;
    if (f.kind === 'int' && v !== Math.floor(v)) return false;
    return v >= f.min && v <= f.max;                          // 越界：拒（不夹取，回落默认更可预期）
  }

  /* 偏好文档。schema 版本化：日后改字段语义时按 v 迁移，而不是让旧存档静默错解。 */
  var SCHEMA = 1;
  var prefs = { v: SCHEMA, preset: '', on: true, ov: { dark: {}, light: {} } };

  /* 🚨 存档载体复用 SBK.store（core.js 已实现的三级降级链 save → cache → 内存），
        【绝不另写一套存储】。但 store 只有一个可变 KEY + 800ms 尾部合并写：
        为它临时改 key 会与业务写入抢同一次 flush（写错 key）。
     → 故偏好挂在【状态仓的保留字段】 _sbkTheme 上：store.save() 缺参时存 state.get()，
       于是业务存档与偏好天然同文档、同一次写入，既不抢 key 也不会互相覆盖。
     ✅ 安全性已核对 hud.js pick()：`k.charAt(0) === '_'` 的键被视为内部字段【不渲染】，
        所以这个保留字段不会漏进状态面板。 */
  var SKEY = '_sbkTheme';

  function sane(raw) {
    // 逐字段降级：脏存档（字号 999 / 强调色 '"; drop' / 未知键 / __proto__）只丢该字段，不炸整卡
    var p = { v: SCHEMA, preset: '', on: true, ov: { dark: {}, light: {} } }, i, m, src, dst, k, n;
    if (!raw || typeof raw !== 'object') return p;
    if (typeof raw.preset === 'string' && Object.prototype.hasOwnProperty.call(PRESETS, raw.preset)) p.preset = raw.preset;
    if (typeof raw.on === 'boolean') p.on = raw.on;             // 严格 boolean，非 boolean 回落 true
    for (i = 0; i < 2; i++) {
      m = i ? 'light' : 'dark';
      src = raw.ov && typeof raw.ov === 'object' ? raw.ov[m] : null;
      if (!src || typeof src !== 'object') continue;
      dst = p.ov[m];
      // 只走 FIELDS 白名单：__proto__ / constructor / 未知键都不在表里，天然进不来
      for (n = 0; n < FIELDS.length; n++) {
        k = FIELDS[n].key;
        if (!Object.prototype.hasOwnProperty.call(src, k)) continue;
        if (okField(k, src[k])) dst[k] = src[k];
        else SBK.warn('theme pref rejected: ' + m + '.' + k);
      }
    }
    return p;
  }

  function hex2rgb(v) {
    return parseInt(v.slice(1, 3), 16) + ',' + parseInt(v.slice(3, 5), 16) + ',' + parseInt(v.slice(5, 7), 16);
  }

  /* 合成一套模式的最终令牌。preset 每次从源码现取（绝不来自存档），overrides 叠在上面。 */
  function resolve(m) {
    var base = PRESETS[presetName], src = null, out = {}, k, ov, i, f, v;
    if (base) src = (base.dark || base.light) ? base[m] : base;
    if (src) for (k in src) if (Object.prototype.hasOwnProperty.call(src, k)) out[k] = src[k];
    ov = prefs.ov[m] || {};
    for (i = 0; i < FIELDS.length; i++) {
      f = FIELDS[i];
      if (!Object.prototype.hasOwnProperty.call(ov, f.key)) continue;
      v = ov[f.key];
      // 字号走 --sbk-fs（base.css 已用它做 .sbk-host 的 font-size），单位换 rpx 保持窄屏比例
      if (f.unit === 'rpx') out[f.tone] = 'calc(' + v + ' * var(--rpx))';
      else if (f.key === 'opacity') continue;                   // 与气泡色联合处理，见下
      else out[f.tone] = v;
    }
    // 气泡透明度：平台三个背景令牌实测同色（§9），拉不开层次 → 色 + 透明度合成 rgba
    if (Object.prototype.hasOwnProperty.call(ov, 'opacity')) {
      var c = ov.aiBubbleColor;
      if (!HEX.test(String(c || ''))) c = out.aiBubble;         // 没微调过颜色就拿 preset 的
      if (HEX.test(String(c || ''))) out.aiBubble = 'rgba(' + hex2rgb(c) + ',' + (ov.opacity / 100) + ')';
    }
    return out;
  }

  /* 行距桥：令牌覆盖只能改 var()，而 base.css 的 .sbk-host 写的是 line-height:1.5 这条【真值】。
     故额外发一条消费 --sbk-lh 的规则。选择器带 [data-chat="root"] 祖先 → (0,2,0) 压过
     base.css 的 .sbk-host (0,1,0)，无需 !important。带回落值，令牌缺失时仍是 1.5。 */
  var BRIDGE = '[data-chat="root"] .sbk-host,[data-chat="root"] .sbk-snap{line-height:var(--sbk-lh,1.5)}';

  function applyPrefs() {
    // 「停用美化」= 旧 native：撤销全部覆盖，完全跟随平台（沙盒下 textContent='' 是【真】native）
    if (!prefs.on) { apply(null); return; }
    apply({ dark: resolve('dark'), light: resolve('light') }, BRIDGE);
  }

  function persist() {
    // 偏好写进保留字段后调 store.save()（缺参 = 存 state.get()）→ 复用 core 的三级降级链
    try {
      SBK.state.patch(pack());
      SBK.store.save();
    } catch (e) { SBK.warn('theme prefs persist failed', e && e.message); }   // 降级不外抛
  }
  function pack() { var o = {}; o[SKEY] = prefs; return o; }

  function load() {
    /* 🚨 硬约束 18 / §4.4a：瘦预览下 save.get / save.keys 【同步抛 SdkError】。
       store.load() 内部已 try/catch 并返回 null，这里【再兜一层】——
       降级到 cache/内存后仍要保证「取不到偏好」只是回默认，绝不炸整卡。 */
    var doc = null;
    try { doc = SBK.store.load(); } catch (e) { SBK.warn('theme prefs load threw, using defaults', e && (e.code || e.message)); }
    prefs = sane(doc && typeof doc === 'object' ? doc[SKEY] : null);
    if (prefs.preset) presetName = prefs.preset;
    return prefs;
  }

  /* 对外的偏好 API。ui.js 只认这一层，不自己碰存储与合成。 */
  var prefsApi = {
    fields: function () { return FIELDS.slice(); },     // 控件清单唯一真源，ui.js 据此建面板
    field: function (k) { return FMAP[k] || null; },
    presets: function () { var a = [], k; for (k in PRESETS) if (Object.prototype.hasOwnProperty.call(PRESETS, k)) a.push(k); return a; },
    preset: function (name) {
      if (name === undefined) return presetName;
      if (name && !Object.prototype.hasOwnProperty.call(PRESETS, name)) { SBK.warn('unknown preset: ' + name); return presetName; }
      presetName = name || '';
      prefs.preset = presetName;
      applyPrefs(); persist();
      return presetName;
    },
    enabled: function (v) {
      if (v === undefined) return prefs.on;
      prefs.on = !!v;
      applyPrefs(); persist();
      return prefs.on;
    },
    get: function (k, m) {
      // 回读顺序：override → preset 的对应值 → 字段默认。ui.js 用它填控件初值
      var mm = m || mode(), ov = prefs.ov[mm] || {}, f = FMAP[k], r;
      if (Object.prototype.hasOwnProperty.call(ov, k)) return ov[k];
      if (!f) return undefined;
      if (f.kind === 'color') {
        r = resolve(mm)[f.tone];
        return HEX.test(String(r || '')) ? r : '';
      }
      return f.def;
    },
    set: function (k, v, m) {
      var mm = m || mode(), f = FMAP[k];
      if (!f) { SBK.warn('unknown theme pref: ' + k); return false; }
      if (!okField(k, v)) { SBK.warn('invalid theme pref value rejected: ' + k + '=' + v); return false; }
      prefs.ov[mm] = prefs.ov[mm] || {};
      prefs.ov[mm][k] = v;
      applyPrefs(); persist();
      return true;
    },
    /* 重置当前主题：删【当前模式】的 overrides（盘点 B.5 第 4 条）。
       另一侧不动 —— 两套 overrides 分开存，切换不串值。 */
    reset: function (m) {
      var mm = m || mode();
      prefs.ov[mm] = {};
      applyPrefs(); persist();
    },
    /* 全部恢复默认：清两套 overrides，但【保留】preset 与 on
       （对位旧协议「保留 mode 与 normalizeQuotes」：用户要的是清微调，不是退出美化）。 */
    resetAll: function () {
      prefs.ov = { dark: {}, light: {} };
      applyPrefs(); persist();
    },
    load: load,
    resolved: function (m) { return resolve(m || mode()); },
    raw: function () { return sane(prefs); },            // 副本，外部改不到内部状态
    /* 设置面板表单节点。ui.chrome 拿它塞进抽屉体；作者也能自己塞进舞台或别处。
       ⚠ 建 DOM 但【不挂载】→ 调用方负责挂载时机，故本函数本身不违反硬约束 17。 */
    form: function () { return form(); },
    panel: setPanel,
    /* 开合设置抽屉。ui.chrome 的按钮就调 toggle()，作者也能从自己的菜单里调。 */
    toggle: function () { var p = setPanel(); if (p) p.toggle(); return p; },
    open: function () { var p = setPanel(); if (p) p.open(); return p; },
    close: function () { if (setNode) setNode.close(); return setNode; }
  };

  /* ---------- 设置面板样式 ----------
     🚨 base.css 属 WP-B，本工作包不改它 → .sbk-set* 全套样式在这里注入，
        且【每个 var() 都带可独立工作的回落值】（盘点 F.2 配色契约）：
        「停用美化」时 apply(null) 撤掉全部覆盖，面板仍必须可读（盘点 C.5 两层 token 纪律）。
     §3 预览重跑：固定 id + 替换 textContent，绝不 append 新节点，否则堆积一堆 <style>。
     §2 CSP：零 @import、零外部字体；尺寸一律 calc(N * var(--rpx))（2.0 §3.5，旧资产用 px，沙盒须换算）。 */
  var SET_ID = 'sbk-set-css';
  var SET_CSS = [
    '.sbk-set{display:flex;flex-direction:column;gap:calc(12 * var(--rpx,1.333px))}',
    /* field 行：label 左、控件右，两端对齐。min-height 44px 是触控目标下限（盘点 C.5）——
       换算成 rpx 后在窄屏仍≥44px，故取 max() 兜住宽屏。 */
    '.sbk-set__row{display:flex;align-items:center;justify-content:space-between;' +
      'gap:calc(12 * var(--rpx,1.333px));min-height:max(44px,calc(88 * var(--rpx,1.333px)))}',
    '.sbk-set__label{flex:1 1 auto;min-width:0;color:var(--chat-text-muted,#c5c5c5);' +
      'font-size:var(--sbk-fs-sm,calc(20 * var(--rpx,1.333px)))}',
    '.sbk-set__ctl{flex:0 0 auto;display:flex;align-items:center;gap:calc(8 * var(--rpx,1.333px))}',
    /* 原生控件配色跟随：§7.1 平台无 color-scheme 声明，不写这条深色下滑块/取色器会是白的（盘点 F.3 #9） */
    '.sbk-set__ctl input,.sbk-set__ctl select{color-scheme:inherit;' +
      'background:var(--chat-input-bg,#1e1f24);color:var(--chat-input-text,#fff);' +
      'border:1px solid var(--chat-border,#333);border-radius:calc(8 * var(--rpx,1.333px));' +
      'font:inherit;padding:calc(6 * var(--rpx,1.333px)) calc(8 * var(--rpx,1.333px))}',
    '.sbk-set__ctl input[type="number"]{width:calc(120 * var(--rpx,1.333px));text-align:right}',
    /* 取色器：padding 让色块四周留边，否则整块被色填满看不出是控件 */
    '.sbk-set__ctl input[type="color"]{width:calc(72 * var(--rpx,1.333px));' +
      'height:calc(56 * var(--rpx,1.333px));padding:calc(3 * var(--rpx,1.333px))}',
    '.sbk-set__ctl input[type="range"]{width:calc(150 * var(--rpx,1.333px));padding:0;border:0;background:transparent}',
    '.sbk-set__ctl input[type="checkbox"]{width:calc(44 * var(--rpx,1.333px));height:calc(44 * var(--rpx,1.333px));' +
      'accent-color:var(--chat-accent,#ff6d97);padding:0}',
    '.sbk-set__ctl select{max-width:calc(300 * var(--rpx,1.333px))}',
    // tabular-nums 让滑块读数跳动时宽度不变（盘点 C.3 第 8 项）
    '.sbk-set__out{min-width:calc(64 * var(--rpx,1.333px));text-align:right;' +
      'font-variant-numeric:tabular-nums;color:var(--chat-text,#fff)}',
    // 微调组停用态：真 disabled + 视觉弱化（盘点 C.5 禁用态双写；aria-disabled 会被净化删，见下）
    '.sbk-set__grp--off{opacity:.55}',
    '.sbk-set__grp--off .sbk-set__ctl{pointer-events:none}',
    '.sbk-set__act{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:calc(12 * var(--rpx,1.333px));' +
      'padding-top:calc(8 * var(--rpx,1.333px));border-top:1px solid var(--chat-border,#333)}'
  ].join('');

  function setCss() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    // 不用 getElementById：§4.3 它被平台改写过（走 gc 游标），遍历子节点最稳
    for (i = 0; i < kids.length; i++) if (kids[i] && kids[i].nodeType === 1 && kids[i].id === SET_ID) { el = kids[i]; break; }
    if (!el) { el = d.createElement('style'); el.id = SET_ID; head.appendChild(el); }
    if (el.textContent !== SET_CSS) el.textContent = SET_CSS;   // 替换而非追加
    return el;
  }

  /* ---------- 设置面板表单 ----------
     控件按 FIELDS 生成 → 加一个微调项只改 FIELDS 一处，面板自动多一行。
     🚨 §5.5 ALLOW_ARIA_ATTR:!1 → aria-* 与 role 被净化器【删除】（core 的 h() 会告警并跳过）。
        事实卡原话：这属【平台限制】而非基座缺陷。故旧资产盘点 C.5 的
        aria-pressed / role="dialog" / aria-labelledby 在此一律落不了地 →
        禁用态改用「真 disabled 属性 + class 视觉弱化」表达，不双写 aria-disabled。
     🚨 §5.5 SAFE_FOR_XML：属性值禁 ]> / --> / --!>，比较运算符两侧留空格。
        本表单所有 on* 都走 h() 的 function 形态（addEventListener 直绑、不过净化器）→ 天然免疫。 */
  var H = SBK.dom.h;
  function row(label, ctl) {
    return H('div', { 'class': 'sbk-set__row' }, [
      H('div', { 'class': 'sbk-set__label' }, label),
      H('div', { 'class': 'sbk-set__ctl' }, ctl)
    ]);
  }

  function fieldRow(f, ctls) {
    var el, out = null;
    if (f.kind === 'color') el = H('input', { type: 'color' });
    else if (f.unit === '%') {
      el = H('input', { type: 'range', min: f.min, max: f.max, step: f.step });
      out = H('span', { 'class': 'sbk-set__out' });   // <output> 不在 §5.4 白名单 → 用 span
    } else {
      el = H('input', { type: 'number', min: f.min, max: f.max, step: f.step });
      // 移动端弹对应键盘：整数弹数字盘，小数弹带小数点的
      el.setAttribute('inputmode', f.kind === 'int' ? 'numeric' : 'decimal');
    }
    function readout() { if (out) out.textContent = el.value + '%'; }
    function fill() {
      var v = prefsApi.get(f.key);
      if (f.kind === 'color') el.value = HEX.test(String(v || '')) ? v : '#000000';
      else el.value = String(v === undefined || v === null ? f.def : v);
      readout();
    }
    function commit() {
      var v = f.kind === 'color' ? String(el.value) : parseFloat(el.value);
      // 非法/越界被 set 拒绝（已告警）→ 把控件拨回真值，绝不让界面停在一个没生效的值上
      if (!prefsApi.set(f.key, v)) fill();
      else readout();
    }
    /* commit 挂 change 而非 input：§G.6 存档写入有限频（core 的 store.save 已 800ms 尾部合并
       + 令牌桶 18次/60s），滑块每帧提交会白烧配额。input 只更新读数，不落盘。 */
    el.addEventListener('change', commit);
    if (out) el.addEventListener('input', readout);
    ctls.push({ el: el, fill: fill });
    return row(f.label, out ? [el, out] : el);
  }

  /* 设置抽屉（懒建单例）。
     🚨 载体复用 SBK.ui.panel 的 mode:'drawer'：.sbk-drw 是 fixed + top/bottom + 贴边，
        几何完全自足，不需要球做锚点；遮罩、返回键先收起、mount 掉了补挂、同 id 防重挂
        全部现成 → 不把抽屉再实现一遍。panel 的球只是它的默认入口，这里由 chrome 的
        按钮当入口，故把球藏掉。
     🚨 装载顺序是 core → theme → protocol → hud → ui（build_sbk.py 的 CORE/UI_ASSETS 固定），
        theme.js 装载时 SBK.ui.panel 【还不存在】→ 所以只能在【调用时】才取 SBK.ui.panel，
        绝不能在模块顶层缓存它。缺 ui 层时告警并返回 null，不抛。 */
  var setNode = null;
  var setOpts = { title: '\u9605\u8bfb\u8bbe\u7f6e', width: '' };
  function setPanel() {
    if (setNode) return setNode;
    var mk = SBK.ui && SBK.ui.panel;
    if (typeof mk !== 'function') { SBK.warn('theme.prefs.panel needs the ui layer (SBK.ui.panel)'); return null; }
    setNode = mk({
      id: 'sbk-set', side: 'right', mode: 'drawer', drag: false,
      title: setOpts.title, width: setOpts.width || undefined,
      content: function () { return form(); }
    });
    var b = setNode.ball();
    if (b) b.style.display = 'none';
    return setNode;
  }

  var syncForm = null;        // 最近一次 form() 的刷新器，供 theme 变化时回填

  function form() {
    setCss();
    var box = H('div', { 'class': 'sbk-set' }), ctls = [], list, i, sel_ = null, grp, r1, r2;

    /* ① 风格包选择 —— 取代旧「日间/夜间/原生」三按钮（2.0 §4.1 / 盘点 B.3）。
       作者没注册风格包时整行不出现：只有「默认」一项的选择器是坏控件。 */
    list = prefsApi.presets();
    if (list.length) {
      sel_ = H('select', { onchange: function () { prefsApi.preset(sel_.value); refresh(); } },
        [H('option', { value: '' }, '默认')]);
      for (i = 0; i < list.length; i++) sel_.appendChild(H('option', { value: list[i] }, list[i]));
      box.appendChild(row('风格包', sel_));
    }

    /* ② 启用美化（关 = 跟随平台，对应旧 native）。
       ⚠ 盘点 B.1：关掉美化【不关设置入口】，否则玩家再也回不来。 */
    var cb = H('input', { type: 'checkbox', onchange: function () { prefsApi.enabled(cb.checked); refresh(); } });
    box.appendChild(row('启用美化（关闭＝跟随平台）', cb));

    // ③ 玩家微调组：6 项由 FIELDS 驱动。停用美化时整组真 disabled（盘点 C.5）
    grp = H('div', { 'class': 'sbk-set__grp' });
    for (i = 0; i < FIELDS.length; i++) grp.appendChild(fieldRow(FIELDS[i], ctls));
    box.appendChild(grp);

    // ④ 两个重置：语义差别见 prefs.reset / prefs.resetAll
    r1 = H('button', { 'class': 'sbk-btn', onclick: function () { prefsApi.reset(); refresh(); } }, '恢复当前主题默认');
    r2 = H('button', { 'class': 'sbk-btn', onclick: function () { prefsApi.resetAll(); refresh(); } }, '全部恢复默认');
    box.appendChild(H('div', { 'class': 'sbk-set__act' }, [r1, r2]));

    function refresh() {
      var j;
      cb.checked = prefs.on;
      if (sel_) sel_.value = presetName;
      for (j = 0; j < ctls.length; j++) {
        ctls[j].fill();
        ctls[j].el.disabled = !prefs.on;       // 真 disabled，不只是视觉弱化
      }
      grp.setAttribute('class', 'sbk-set__grp' + (prefs.on ? '' : ' sbk-set__grp--off'));
      r1.disabled = !prefs.on;                 // 停用时「恢复当前主题默认」无意义
      // r2「全部恢复默认」永不禁用（盘点 C.3 第 10 项）：它是玩家把自己改坏后的唯一出路
    }
    refresh();
    syncForm = refresh;
    return box;
  }

  /* 平台切深浅色时回填控件：prefs.get 是按 mode 取的，两套 overrides 分开存 →
     不回填的话面板会显示另一套主题的值。只改控件显示，不写偏好，故不会与 set 形成回环。 */
  onChange(function () { if (syncForm) { try { syncForm(); } catch (e) {} } });

  SBK.theme = {
    apply: apply,
    /* 注册风格包。register('名', {dark:{…},light:{…}})，或 register({名:包, …}) 批量。
       ⚠ 只登记不生效：生效要 prefs.preset('名')，或 boot 时由配置指定。 */
    register: function (name, def) {
      if (name && typeof name === 'object') { for (var k in name) if (Object.prototype.hasOwnProperty.call(name, k)) PRESETS[k] = name[k]; return; }
      if (typeof name === 'string' && name && def && typeof def === 'object') PRESETS[name] = def;
      else SBK.warn('theme.register needs (name, tokens) or an object map');
    },
    prefs: prefsApi,
    /* 读存档 + 合成 + 落地，一步到位。ui.chrome 与 boot 都走它，重复调用无副作用
       （load 每次重新 sane()，applyPrefs 是替换同一个 <style> 的 textContent）。
       ⚠ 只写 <head> 里的 <style>，不碰气泡/功能栏 → 不受硬约束 17 限制，顶层可调。 */
    start: function (name, opt) {
      if (typeof name === 'string' && name) presetName = name;
      if (opt) {
        if (opt.title) setOpts.title = String(opt.title);
        if (opt.width) setOpts.width = String(opt.width);
      }
      load();
      // 存档里的 preset 优先于入参：玩家挑过风格包就尊重玩家（入参只作首次默认）
      applyPrefs();
      return prefsApi;
    },
    mode: mode,
    onChange: onChange,
    vars: function () { return VARS.slice(); },         // 14 个平台后缀名，供 WP-4 校验
    tokens: MAP,                                        // 语义名 → 平台后缀
    page: PAGE,                                         // 需 !important 的页面级属性名
    base: function () { var r = {}, k; for (k in DARK) r[k] = DARK[k]; return r; }, // 实测深色基线副本
    current: function () { return current; },
    reset: function () { apply(null); }
  };
  SBK.log('theme ready');
})(typeof window !== 'undefined' ? window : globalThis);
