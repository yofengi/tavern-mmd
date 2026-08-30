/* SBK bubble：锚定在侧边按钮旁的弹窗气泡。dock 的第二种呈现面。
   ------------------------------------------------------------------
   与 drawer（半页抽屉）的分工 —— 这是【语义】分工，不是两种皮肤：
   · drawer ＝ 基础设置：美化相关（风格包、字号、配色）。信息量大、要滚动、值得盖半屏。
   · bubble ＝ 扩展功能：地图、人物图鉴、自动注入。轻量、看一眼就走 ——
     为它盖掉半个屏幕不划算，就地弹在按钮旁边最合适。
   两者都支持 ui-nav.js 的可选导航栏（≥2 pane 才渲染），所以「一个气泡统筹多功能、
   靠导航栏切换」与「多个图标页签各管一件事」都能表达。

   定位复用 ui.js 的 place(box, anchorRect, {side:'x'})：横向优先贴按钮，
   放不下自动翻到另一侧，并夹在视口内。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-bubble.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-bubble')) return;

  var kit = SBK._uiKit;
  if (!kit) { SBK.warn('ui-bubble: SBK._uiKit missing (ui.js not loaded?)'); return; }

  var d = W.document, h = SBK.dom.h;
  var injectCss = kit.injectCss, defer = kit.defer, armStop = kit.armStop;
  var place = kit.place, stop = kit.stop, headOf = kit.headOf, slotOf = kit.slotOf;

  var BB_ID = 'sbk-bb-css';
  /* 几何 px：气泡是 chrome 级 UI，--rpx 恒 0.5px 会让尺寸腰斩（详见 ui-dock.js 注释）。
     字号沿用 .sbk-drw/.sbk-pop 那套 --sbk-cfs*，这里给 .sbk-bb 也定义一份。 */
  var BB_CSS = [
    '.sbk-bb{--sbk-cfs:15px;--sbk-cfs-sm:13px;--sbk-cfs-xs:12px;' +
      'position:fixed;z-index:var(--sbk-z-pop,3600);display:none;flex-direction:column;' +
      'width:var(--sbk-bb-w,278px);max-width:calc(100vw - 24px);' +
      'max-height:min(70vh,70dvh);overflow:hidden;' +
      'background:var(--chat-surface);color:var(--chat-text);' +
      'border:1px solid var(--chat-border);border-radius:14px;' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));' +
      'font-size:var(--sbk-cfs-sm,13px);' +
      'opacity:0;transform:scale(.94);transform-origin:right center;' +
      'transition:opacity .16s ease,transform .18s ease}',
    '.sbk-bb--on{opacity:1;transform:scale(1)}',
    '.sbk-bb--l{transform-origin:left center}',
    /* 标题行：与抽屉同一套 .sbk-pnl__hd/__ti/__x，视觉语言统一，只把内距压小一档 */
    '.sbk-bb>.sbk-pnl__hd{padding:10px 12px}',
    '.sbk-bb>.sbk-pnl__ti{font-size:var(--sbk-cfs,15px)}',
    '.sbk-bb__bd{flex:1 1 auto;min-height:0;overflow:auto;padding:12px;' +
      'scrollbar-width:thin;scrollbar-color:var(--chat-border) transparent}',
    '.sbk-bb__bd::-webkit-scrollbar{width:7px}',
    '.sbk-bb__bd::-webkit-scrollbar-thumb{background:var(--chat-border);border-radius:999px}',
    /* 指向按钮的小三角。用 border 画，不用额外节点里的 svg —— 省字节且不吃净化风险。
       它只是装饰：位置由 JS 按锚点中心写内联 top，翻侧时换左右。 */
    '.sbk-bb__tip{position:absolute;width:0;height:0;border:7px solid transparent}',
    '.sbk-bb--r .sbk-bb__tip{right:-14px;border-left-color:var(--chat-border)}',
    '.sbk-bb--l .sbk-bb__tip{left:-14px;border-right-color:var(--chat-border)}',
    '@media (prefers-reduced-motion:reduce){.sbk-bb{transition:none}}',
    /* 窄屏：气泡改为贴底的宽卡片。278px 在 375px 屏上虽然放得下，但紧贴右缘会
       压住半个聊天区，且拇指要横跨屏幕 —— 与抽屉在窄屏改底部抽屉同一个理由。 */
    '@media (max-width:420px){' +
      /* 🚨 max-width 必须解除：基线的 calc(100vw - 24px) 会把宽度锁成 380，
         而 left:8px 又钉住左边 → 右侧空出 16px，气泡在窄屏上明显偏左（实测 8/16）。
         这里由 left/right 这对约束决定宽度，故 max-width 交回 none。 */
      '.sbk-bb{left:8px!important;right:8px!important;width:auto;max-width:none;' +
      'top:auto!important;bottom:10px;max-height:min(62vh,62dvh);' +
      'transform-origin:bottom center}' +
      '.sbk-bb__tip{display:none}}'
  ].join('');

  function bbCss() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === BB_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = BB_ID; head.appendChild(el); }
    if (el.textContent !== BB_CSS) el.textContent = BB_CSS;
    return el;
  }

  var reg = {};
  function bubble(opts) {
    var o = opts || {};
    var id = String(o.id || 'sbk-bubble');
    if (reg[id]) { SBK.warn('ui.bubble: id already mounted, returning existing: ' + id); return reg[id]; }
    var side = o.side === 'left' ? 'left' : 'right';
    var box = null, tip = null, built = false, dead = false, opened = false;
    var api, lastFocus = null;

    function anchorEl() {
      var a = o.anchor;
      if (typeof a === 'function') { try { a = a(); } catch (e) { a = null; } }
      return a && a.nodeType === 1 ? a : null;
    }
    function bodyNode() {
      var c = typeof o.content === 'function' ? o.content(api) : o.content;
      if (c && c.nodeType) return c;
      if (typeof c === 'string') return h('div', { 'class': 'sbk-pre' }, c);
      return h('div');
    }
    function build() {
      if (dead || built) return !dead;
      var slot = slotOf(side);
      if (!slot) { SBK.warn('ui.bubble: no mount point yet'); return false; }
      injectCss();
      bbCss();
      var kids = [];
      var hd = headOf(o.title, o.title && o.closeButton !== false, function () { api.close(); });
      if (hd) kids.push(hd);
      kids.push(h('div', { 'class': 'sbk-bb__bd' }, bodyNode()));
      tip = h('span', { 'class': 'sbk-bb__tip' });
      kids.push(tip);
      box = h('div', { 'class': 'sbk-bb sbk-bb--' + (side === 'left' ? 'l' : 'r') }, kids);
      if (o.width) box.style.setProperty('--sbk-bb-w', String(o.width));
      armStop(box);
      slot.appendChild(box);
      built = true;
      return true;
    }
    /* class 由状态【整条重写】，不做字符串拼接/替换。
       🚨 曾经踩过：open() 里 `class += ' sbk-bb--on'` 而 locate() 也会带上同一个类，
       于是 class 里出现两份 --on；close() 的 replace 没有 /g 只删掉一份，
       气泡的打开态类残留，反复开合还会持续累积。整条重写从根上消灭这类 bug。 */
    var flipped = false;
    function paint() {
      if (!box) return;
      box.setAttribute('class', 'sbk-bb sbk-bb--' + (flipped ? 'l' : 'r') +
        (opened ? ' sbk-bb--on' : ''));
    }
    /* 定位：place() 横向优先贴锚点，放不下自动翻侧。翻侧后要同步换 class，
       否则小三角与缩放原点会指错方向。 */
    function locate() {
      var a = anchorEl();
      if (!a || !box) return;
      var ar = a.getBoundingClientRect();
      place(box, ar, { side: 'x', gap: 10 });
      var br = box.getBoundingClientRect();
      flipped = br.left > ar.left;            /* 气泡落在锚点右侧 = 指向左 */
      /* 🚨 place() 会为了量尺寸写下【内联】 visibility:hidden + display:block，
         而且只回写 left/top，【不负责还原】这两项（ui-panel.js 的浮层路径是在
         place() 之后自己补 visibility:'visible' 的）。不还原的后果极隐蔽：
         visibility:hidden 的元素【仍然占布局】，所以 getBoundingClientRect 照样
         返回正常尺寸位置、DOM 探针一切正常，但屏幕上什么都没有 ——
         实测就是这样：探针报 278x146@835,325 而截图里空白，judge 判 fail 才暴露。
         display 也必须掰回 flex：place() 写的 block 会让标题行/正文的纵向 flex 布局失效。 */
      box.style.visibility = 'visible';
      box.style.display = 'flex';
      paint();
      if (tip) {
        var cy = ar.top + ar.height / 2 - br.top - 7;
        tip.style.top = Math.max(8, Math.min(cy, br.height - 22)) + 'px';
      }
    }
    function onEsc(e) {
      var k = e && e.key;
      if ((k === 'Escape' || k === 'Esc') && opened) api.close();
    }
    function onWin() { if (opened) locate(); }

    api = {
      el: function () { return box; },
      box: function () { return box; },
      opened: function () { return opened; },
      open: function () {
        if (dead) return api;
        if (!built) { defer(function () { if (!dead) { build(); api.open(); } }); return api; }
        if (opened) return api;
        try { lastFocus = d.activeElement || null; } catch (e) { lastFocus = null; }
        box.style.display = 'flex';
        opened = true;
        /* 先布好位再由 paint() 落打开态：缩放动画从锚点方向展开，而不是从旧位置漂移。
           locate() 内部已调 paint()，此处不再手工拼 class（见 paint() 注释）。 */
        locate();
        paint();
        try { d.addEventListener('keydown', onEsc, true); } catch (e) {}
        try { W.addEventListener('resize', onWin); } catch (e) {}
        var f = null;
        try { f = box.querySelectorAll('button,input,select,textarea,[tabindex]')[0]; } catch (e) {}
        if (f && f.focus) { try { f.focus(); } catch (e) {} }
        if (typeof o.onOpen === 'function') { try { o.onOpen(api); } catch (e) {} }
        return api;
      },
      close: function () {
        if (!built || !opened) { opened = false; return api; }
        opened = false;
        paint();
        box.style.display = 'none';
        try { d.removeEventListener('keydown', onEsc, true); } catch (e) {}
        try { W.removeEventListener('resize', onWin); } catch (e) {}
        if (lastFocus && typeof lastFocus.focus === 'function') {
          try { if (d.body && d.body.contains(lastFocus)) lastFocus.focus(); } catch (e) {}
        }
        lastFocus = null;
        if (typeof o.onClose === 'function') { try { o.onClose(api); } catch (e) {} }
        return api;
      },
      toggle: function () { return opened ? api.close() : api.open(); },
      locate: function () { locate(); return api; },
      setContent: function (c) {
        o.content = c;
        if (!built) return api;
        var bd = null;
        try { bd = box.querySelectorAll('.sbk-bb__bd')[0]; } catch (e) {}
        if (bd) { while (bd.firstChild) bd.removeChild(bd.firstChild); bd.appendChild(bodyNode()); }
        if (opened) locate();
        return api;
      },
      destroy: function () {
        SBK.off('mount', onMount);
        SBK.off('back', onBack);
        try { d.removeEventListener('keydown', onEsc, true); } catch (e) {}
        try { W.removeEventListener('resize', onWin); } catch (e) {}
        if (box && box.parentNode) box.parentNode.removeChild(box);
        box = tip = null; built = false; opened = false; dead = true; lastFocus = null;
        delete reg[id];
        return null;
      }
    };
    function onMount() { if (built && box && !box.parentNode) { built = false; build(); } }
    function onBack() { if (opened && o.closeOnBack !== false) api.close(); }
    reg[id] = api;
    SBK.on('mount', onMount);
    SBK.on('back', onBack);
    return api;
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.bubble = bubble;
  SBK.log('ui-bubble ready (bubble)');
})(typeof window !== 'undefined' ? window : globalThis);
