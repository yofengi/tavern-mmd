/* SBK nav：呈现面内部的可选导航栏 + 分页容器。drawer 与 bubble 共用。
   ------------------------------------------------------------------
   🚨 核心纪律：【单 pane 不渲染导航栏】。只有一组内容时直接把内容铺开 ——
   一条只有一个格子的导航栏是纯噪音（用户明确点出过这个问题）。
   ≥2 pane 才出现导航栏，用来在同一个面里切换不同类型的功能。

   独立成模块而不是塞进 ui-dock.js：① dock 的 drawer 面与 ui-bubble.js 的气泡面
   都要用它，放任一边都会变成跨模块反向依赖；② ui-dock.js 剥注释后已达 18.7K，
   超过生成器不可调高的 18000 单条门禁，必须真实拆码而不是靠删注释。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-nav.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-nav')) return;

  var kit = SBK._uiKit;
  if (!kit) { SBK.warn('ui-nav: SBK._uiKit missing (ui.js not loaded?)'); return; }

  var d = W.document, h = SBK.dom.h, stop = kit.stop;
  var NAV_ID = 'sbk-nav-css';
  /* 几何用 px：导航栏是 chrome 级 UI，--rpx 恒 0.5px 会让它腰斩（详见 ui-dock.js 注释）。
     字号取 ui.js 在 .sbk-drw/.sbk-pop 上定义的 --sbk-cfs-sm，带 px 兜底。 */
  var NAV_CSS = [
    '.sbk-nav{display:flex;gap:4px;flex-shrink:0;overflow-x:auto;scrollbar-width:none;' +
      'padding:4px;margin:0 0 10px;border:1px solid var(--chat-border);border-radius:999px;' +
      'background:var(--sbk-lift,rgba(255,255,255,.05))}',
    '.sbk-nav::-webkit-scrollbar{display:none}',
    '.sbk-nav__b{flex:1 1 auto;min-width:max-content;min-height:32px;padding:0 14px;' +
      'border:0;border-radius:999px;background:transparent;color:var(--chat-text-muted);' +
      'font-family:inherit;font-size:var(--sbk-cfs-sm,13px);cursor:pointer;white-space:nowrap;' +
      '-webkit-tap-highlight-color:transparent;transition:background .16s ease,color .16s ease}',
    '.sbk-nav__b--on{background:var(--chat-accent);color:var(--sbk-on-accent,#fff);font-weight:600}',
    '.sbk-nav__b:focus-visible{outline:2px solid var(--chat-accent);outline-offset:-2px}',
    '.sbk-navwrap{display:flex;flex-direction:column;min-width:0}',
    '.sbk-pane{min-width:0}'
  ].join('');

  function navCss() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === NAV_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = NAV_ID; head.appendChild(el); }
    if (el.textContent !== NAV_CSS) el.textContent = NAV_CSS;
    return el;
  }

  /* nav(panes, opts) → {el, bar, body, show(i), index, count}
     panes: [{label, content}]，content 为节点、字符串或返回节点的函数（懒求值）。 */
  function nav(panes, opts) {
    var list = (panes || []).filter(function (p) { return p; });
    var o = opts || {};
    navCss();
    var body = h('div', { 'class': 'sbk-pane' });
    var wrap = h('div', { 'class': 'sbk-navwrap' });
    var cur = -1, bar = null, btns = [];

    function render(i) {
      if (i === cur || !list[i]) return;
      cur = i;
      while (body.firstChild) body.removeChild(body.firstChild);
      var c = list[i].content;
      if (typeof c === 'function') {
        try { c = c(); } catch (e) { SBK.warn('nav: pane content threw'); c = null; }
      }
      if (c && c.nodeType) body.appendChild(c);
      else if (typeof c === 'string') body.appendChild(h('div', { 'class': 'sbk-pre' }, c));
      for (var j = 0; j < btns.length; j++) {
        btns[j].setAttribute('class', 'sbk-nav__b' + (j === i ? ' sbk-nav__b--on' : ''));
      }
      if (typeof o.onSwitch === 'function') { try { o.onSwitch(i, list[i]); } catch (e) {} }
    }

    /* 🚨 只有 >1 才建栏。0 pane 返回空容器，由调用方兜底。 */
    if (list.length > 1) {
      btns = list.map(function (p, i) {
        return h('button', {
          type: 'button', 'class': 'sbk-nav__b',
          onclick: function (e) { stop(e); render(i); }
        }, String(p.label === undefined ? ('' + (i + 1)) : p.label));
      });
      bar = h('div', { 'class': 'sbk-nav' }, btns);
      wrap.appendChild(bar);
    }
    wrap.appendChild(body);
    if (list.length) render(0);

    return {
      el: function () { return wrap; },
      bar: function () { return bar; },
      body: function () { return body; },
      show: function (i) { render(i); return cur; },
      index: function () { return cur; },
      count: function () { return list.length; }
    };
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.nav = nav;
  SBK.log('ui-nav ready (nav)');
})(typeof window !== 'undefined' ? window : globalThis);
