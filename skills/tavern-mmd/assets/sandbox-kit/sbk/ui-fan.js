/* SBK fan：扇形第二层的几何与样式。ui-dock 的可选伴生模块。
   ------------------------------------------------------------------
   扇形只在一枚页签下挂着 ≥2 种【不同类型】功能时才出现（单功能不做第二层，
   见方法论 §7.6）。所以它是 dock 的可选层，独立成模块有两层意义：
   ① 语义上它确实是「另一层」，不是导轨本身；
   ② ui-dock.js 加了页签增删与呈现面销毁后回到 18346（含 19 字符包装），
      超过不可调高的 18000 单条门禁，必须真实拆码。

   🚨 坐标一律 px，与选项自身尺寸同量纲。不能用 rpx：--rpx 实测恒 0.5px
   （桌面封顶 375px/750，手机 100vw/750），按 750 稿写的 -196rpx 只有 -98px，
   小于选项自身 min-width(104px)，选项会挂到屏幕外去（实测复现过）。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-fan.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-fan')) return;

  var kit = SBK._uiKit;
  if (!kit) { SBK.warn('ui-fan: SBK._uiKit missing (ui.js not loaded?)'); return; }

  var d = W.document;
  var viewRect = kit.viewRect, clamp = kit.clamp;
  var CSS_ID = 'sbk-fan-css';
  /* 选项胶囊。默认三态全关（opacity/visibility/pointer-events），展开由 dock 加
     .sbk-dk--on 打开；visibility 延迟到过渡结束再关，避免关闭瞬间还能点到。 */
  var CSS = [
    '.sbk-dk__opt{position:fixed;display:inline-flex;align-items:center;justify-content:center;' +
      'white-space:nowrap;min-width:104px;min-height:44px;padding:0 16px;' +
      'border:1px solid var(--chat-border);border-radius:999px;' +
      'background:var(--chat-surface);color:var(--chat-text);font-size:14px;' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));' +
      'appearance:none;-webkit-appearance:none;font-family:inherit;line-height:1.2;' +
      'cursor:pointer;-webkit-tap-highlight-color:transparent;' +
      'z-index:var(--sbk-z-pop,3600);opacity:0;visibility:hidden;pointer-events:none;' +
      'transform:scale(.72);' +
      'transition:transform .2s ease,opacity .16s ease,visibility 0s linear .2s,' +
      'background .16s ease,color .16s ease,border-color .16s ease}',
    '.sbk-dk__opt--on{opacity:1;visibility:visible;pointer-events:auto;transform:scale(1);' +
      'transition:transform .2s ease,opacity .16s ease,visibility 0s,' +
      'background .16s ease,color .16s ease,border-color .16s ease}',
    '.sbk-dk__opt:hover{border-color:var(--chat-accent)}',
    '.sbk-dk__opt:focus-visible{outline:2px solid var(--chat-accent);outline-offset:2px}',
    '@media (prefers-reduced-motion:reduce){.sbk-dk__opt{transition:none}}'
  ].join('');

  function css() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === CSS_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = CSS_ID; head.appendChild(el); }
    if (el.textContent !== CSS) el.textContent = CSS;
    return el;
  }

  /* 纵向张角表：项数越多张角越窄，避免越界到顶栏/输入区。超过 5 项退化成等距竖列
     （扇形排不下时，可读性优先于造型）。 */
  var ARC = {
    2: [-34, 34],
    3: [-68, 0, 68],
    4: [-96, -32, 32, 96],
    5: [-120, -60, 0, 60, 120]
  };

  /* place(nodes, tabRect, side)：以页签实际 rect 为原点向内侧铺弧，结果夹在视口内。
     ⚠ 必须【现算】而不是预置 CSS 变量：导轨会因页签数变化而上下移动（centre()），
     页签 rect 每次都不同，预置坐标会与实际页签位置脱节。 */
  function place(nodes, tabRect, side) {
    css();
    var n = nodes.length, v = viewRect(), m = 6;
    var ys = ARC[n] || nodes.map(function (_, i) { return (i - (n - 1) / 2) * 52; });
    var cy = tabRect.top + tabRect.height / 2;
    for (var i = 0; i < n; i++) {
      var el = nodes[i], w = el.offsetWidth || 104, hgt = el.offsetHeight || 44;
      /* 中间项推得更远，形成弧感：|y| 越小 → x 越远 */
      var far = 118 + Math.round(30 * (1 - Math.abs(ys[i]) / 130));
      var x = side === 'left' ? tabRect.right + far - w : tabRect.left - far;
      var y = cy + ys[i] - hgt / 2;
      el.style.left = clamp(x, v.l + m, Math.max(v.l + m, v.l + v.w - w - m)) + 'px';
      el.style.top = clamp(y, v.t + m, Math.max(v.t + m, v.t + v.h - hgt - m)) + 'px';
      el.style.transformOrigin = (side === 'left' ? 'left' : 'right') + ' center';
    }
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.fan = { place: place, arc: function () { return ARC; }, css: css };
  SBK.log('ui-fan ready (fan.place)');
})(typeof window !== 'undefined' ? window : globalThis);
