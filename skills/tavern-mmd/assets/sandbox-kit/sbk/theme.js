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

  /* apply(tokens)
     - apply({bg:'#111', ...})                 → 两套主题同值
     - apply({dark:{...}, light:{...}})        → 分别覆盖
     - apply('native') / apply(null)           → 三态之 native：不覆盖，完全跟随平台 */
  function apply(tokens) {
    var node = styleNode();
    if (!tokens || tokens === 'native') {
      node.textContent = '';           // 清空即回到 native
      current = null;
      SBK.emit('theme', mode());
      return;
    }
    var css = '', dark, light;
    if (tokens.dark || tokens.light) { dark = tokens.dark; light = tokens.light; }
    else { dark = tokens; light = tokens; }
    if (dark) css += sel('dark') + '{' + decls(dark) + '}';
    if (light) css += sel('light') + '{' + decls(light) + '}';
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

  SBK.theme = {
    apply: apply,
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
