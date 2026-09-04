/* SBK icon：内置 SVG 图标集。侧边导轨的图标页签、以及作者自己的按钮都可以用。
   ------------------------------------------------------------------
   为什么用 SVG 而不是 emoji 或文字：
   · emoji 在不同机型上字形差异大，且吃不到 currentColor（主题切换时颜色不跟随）；
   · 文字页签占宽，还会与平台自己的 chrome 抢注意力（用户明确要求层 1 只放图标）。

   全部 24×24 viewBox、stroke 描边、fill:none → 颜色由 CSS 的 color 统一控制，
   主题切换免维护。
   🚨 §5.5：SVG 内部的 on* 属性会被平台净化器删掉 → 图标只负责画，
      事件一律绑在外层的 HTML <button> 上。core.js 的 h() 对此有专项告警。

   独立成模块的原因：ui-dock.js 内联图标集后剥注释达 18330 字符，
   加上 19 字符的 script 包装超过不可调高的 18000 单条门禁，必须真实拆码。
   顺带让 codex / map / 作者代码都能直接取用同一套图标。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-icon.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-icon')) return;

  var d = W.document, h = SBK.dom.h;
  var CSS_ID = 'sbk-ico-css';
  var CSS = '.sbk-ico{width:19px;height:19px;display:block;flex-shrink:0;pointer-events:none}';

  var ICONS = {
    /* 齿轮：圆 + 8 根辐条 */
    gear: 'M12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7zM12 2v3M12 19v3M4.9 4.9L7 7' +
      'M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1L7 17M17 7l2.1-2.1',
    wrench: 'M20.7 5.3a5 5 0 0 1-6.6 6.6l-8.7 8.7a2 2 0 0 1-2.8-2.8l8.7-8.7a5 5 0 0 1 6.6-6.6' +
      'l-3 3 2.8 2.8 3-3z',
    /* 交叉工具：扳手 + 螺丝刀交叉 */
    tools: 'M15.5 3.5a4 4 0 0 0 5 5L21 9 9 21l-3-3L18 6zM6.5 3.5l4 4-3 3-4-4zM3.5 17.5l3 3',
    /* 推子：最贴「阅读微调」语义（字号/行距/透明度都是连续量） */
    sliders: 'M4 7h6M14 7h6M4 17h10M18 17h2M12 4.5v5M16 14.5v5',
    map: 'M9 3L3 6v15l6-3 6 3 6-3V3l-6 3zM9 3v15M15 6v15',
    book: 'M3 5a2 2 0 0 1 2-2h5v18H5a2 2 0 0 1-2-2zM21 5a2 2 0 0 0-2-2h-5v18h5a2 2 0 0 0 2-2z',
    spark: 'M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z',
    dots: 'M12 5.5h.01M12 12h.01M12 18.5h.01'
  };
  var FALLBACK = 'gear';

  function css() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === CSS_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = CSS_ID; head.appendChild(el); }
    if (el.textContent !== CSS) el.textContent = CSS;
    return el;
  }

  /* icon(name, extraClass?) → <svg>。未知名回落 FALLBACK 并告警 ——
     真机没有控制台，所以生成器另有一层白名单在生成期就拦（CHROME_ICONS）。 */
  function icon(name, extra) {
    css();
    var key = ICONS[name] ? name : FALLBACK;
    if (!ICONS[name] && name) SBK.warn('ui.icon: unknown icon "' + name + '", using ' + FALLBACK);
    return h('svg', {
      'class': 'sbk-ico' + (extra ? ' ' + extra : ''),
      viewBox: '0 0 24 24', fill: 'none',
      stroke: 'currentColor', 'stroke-width': '1.8',
      'stroke-linecap': 'round', 'stroke-linejoin': 'round'
    }, [h('path', { d: ICONS[key] })]);
  }
  function names() {
    var a = [], k;
    for (k in ICONS) if (Object.prototype.hasOwnProperty.call(ICONS, k)) a.push(k);
    return a;
  }
  function has(n) { return !!ICONS[n]; }

  SBK.ui = SBK.ui || {};
  SBK.ui.icon = icon;
  SBK.ui.icons = names;
  SBK.ui.icon.has = has;
  SBK.log('ui-icon ready (icon)');
})(typeof window !== 'undefined' ? window : globalThis);
