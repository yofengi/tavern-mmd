/* SBK codex：人物图鉴。四种版式，同一份词条数据。
   ------------------------------------------------------------------
   典型放置：气泡侧边栏的一枚独立页签（轻量、瞄一眼就走），也可挂抽屉 pane 或舞台
   （词条几十条、要长时间翻阅时挂舞台更合适）。

   四种版式（用户口径）：
   · single  单列人物图：一行一个，图左文右。词条少、说明长时最好读。
   · double  双列人物图：网格两列，图上名下。十几条以内的常见选择。
   · nav     带导航栏的图鉴：按 category 分组，导航栏切换阵营/类型。
   · swipe   大图左右滑动切换：一屏一个大图，横向 scroll-snap + 左右按钮。

   ⚠ 版式是【呈现】，不是数据：同一份 entries 换 layout 即可，不必改数据结构。
   nav 版式复用 ui-nav.js（≥2 分类才出栏，只有一个分类时自动退化成纯网格）。

   图片：CSP `img-src 'self' data: blob: https:` → 远程图与 data: 都可用（§13）。
   🚨 图片失败兜底走 addEventListener('error')，【不写 onerror 属性】：
      平台明令禁止 `img onerror`（那是被禁的点火器写法）。本模块的节点是 JS 建的、
      不过净化管线，用 addEventListener 挂错误处理与那套点火器无关，但仍刻意避免
      让 onerror 字面量出现在任何字符串里，免得撞上校验器与人工审核。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-codex.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-codex')) return;

  var kit = SBK._uiKit;
  if (!kit) { SBK.warn('ui-codex: SBK._uiKit missing (ui.js not loaded?)'); return; }

  var d = W.document, h = SBK.dom.h, stop = kit.stop;
  var CSS_ID = 'sbk-cdx-css';
  var LAYOUTS = { single: 1, double: 1, nav: 1, swipe: 1 };
  var CSS = [
    '.sbk-cdx{display:flex;flex-direction:column;gap:10px;min-width:0}',
    /* 网格：single 一列、double 两列。用 grid 而非 flex，卡片等高对齐免手工算 */
    '.sbk-cdx__grid{display:grid;gap:10px;min-width:0}',
    '.sbk-cdx--single .sbk-cdx__grid{grid-template-columns:1fr}',
    '.sbk-cdx--double .sbk-cdx__grid{grid-template-columns:1fr 1fr}',
    /* 卡片 */
    '.sbk-cdx__c{display:flex;gap:10px;min-width:0;padding:8px;' +
      'border:1px solid var(--chat-border);border-radius:10px;' +
      'background:var(--sbk-lift,rgba(255,255,255,.05));text-align:left;' +
      'font-family:inherit;color:var(--chat-text);cursor:default}',
    '.sbk-cdx__c--tap{cursor:pointer}',
    '.sbk-cdx__c--tap:hover{border-color:var(--chat-accent)}',
    /* single 图左文右；double 图上名下 */
    '.sbk-cdx--double .sbk-cdx__c{flex-direction:column;gap:6px;align-items:stretch}',
    '.sbk-cdx__ava{flex-shrink:0;width:56px;height:56px;border-radius:8px;overflow:hidden;' +
      'background:var(--chat-border);display:flex;align-items:center;justify-content:center}',
    '.sbk-cdx--double .sbk-cdx__ava{width:100%;height:96px}',
    '.sbk-cdx__ava img{width:100%;height:100%;object-fit:cover;display:block}',
    /* 图挂了就露出首字兜底：不留一个破图图标 */
    '.sbk-cdx__ava--bad img{display:none}',
    '.sbk-cdx__ini{color:var(--chat-text-muted);font-size:18px;font-weight:600}',
    '.sbk-cdx__txt{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:3px}',
    '.sbk-cdx__nm{color:var(--chat-text);font-size:var(--sbk-cfs-sm,13px);font-weight:600;' +
      'overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.sbk-cdx__ds{color:var(--chat-text-muted);font-size:var(--sbk-cfs-xs,12px);line-height:1.5}',
    '.sbk-cdx__tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}',
    '.sbk-cdx__tag{padding:1px 7px;border:1px solid var(--chat-border);border-radius:999px;' +
      'color:var(--chat-text-muted);font-size:11px}',
    /* swipe：横向 scroll-snap，一屏一个大图 */
    '.sbk-cdx__strip{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;' +
      'scrollbar-width:none;-webkit-overflow-scrolling:touch}',
    '.sbk-cdx__strip::-webkit-scrollbar{display:none}',
    '.sbk-cdx__slide{flex:0 0 100%;scroll-snap-align:center;display:flex;flex-direction:column;' +
      'gap:8px;min-width:0}',
    '.sbk-cdx__big{width:100%;height:190px;border-radius:10px;overflow:hidden;' +
      'background:var(--chat-border);display:flex;align-items:center;justify-content:center}',
    '.sbk-cdx__big img{width:100%;height:100%;object-fit:cover;display:block}',
    '.sbk-cdx__big--bad img{display:none}',
    '.sbk-cdx__bar{display:flex;align-items:center;justify-content:space-between;gap:8px}',
    '.sbk-cdx__nav{flex-shrink:0;width:32px;height:32px;padding:0;border-radius:50%;' +
      'border:1px solid var(--chat-border);background:var(--chat-surface);' +
      'color:var(--chat-text);font-family:inherit;font-size:15px;line-height:1;cursor:pointer}',
    '.sbk-cdx__nav:hover{border-color:var(--chat-accent);color:var(--chat-accent)}',
    '.sbk-cdx__nav:focus-visible{outline:2px solid var(--chat-accent);outline-offset:2px}',
    '.sbk-cdx__pos{color:var(--chat-text-muted);font-size:var(--sbk-cfs-xs,12px);' +
      'font-variant-numeric:tabular-nums}',
    '.sbk-cdx__empty{color:var(--chat-text-muted);font-size:var(--sbk-cfs-sm,13px);' +
      'padding:12px;text-align:center}',
    /* 窄屏：双列压成单列（两列卡片在 375px 上每张不到 170px，图和名都挤） */
    '@media (max-width:420px){.sbk-cdx--double .sbk-cdx__grid{grid-template-columns:1fr}' +
      '.sbk-cdx--double .sbk-cdx__c{flex-direction:row}' +
      '.sbk-cdx--double .sbk-cdx__ava{width:56px;height:56px}' +
      '.sbk-cdx__big{height:150px}}'
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

  function initial(name) {
    var s = String(name || '?').replace(/^\s+/, '');
    return s ? s.charAt(0) : '?';
  }
  /* 头像盒。图片可缺省；加载失败时给盒子加 --bad，露出首字兜底。 */
  function avatar(e, cls) {
    var kids = [h('span', { 'class': 'sbk-cdx__ini' }, initial(e.name))];
    var boxCls = cls;
    if (e.image) {
      var img = h('img', { src: String(e.image), alt: '', loading: 'lazy' });
      /* 见文件头：用 addEventListener 而非 onerror 属性 */
      img.addEventListener('error', function () {
        if (bx) bx.setAttribute('class', boxCls + ' ' + boxCls.split(' ')[0] + '--bad');
      });
      kids.unshift(img);
    }
    var bx = h('div', { 'class': boxCls }, kids);
    return bx;
  }

  function tagRow(e) {
    var list = (e.tags || []).filter(function (x) { return x; });
    if (!list.length) return null;
    return h('div', { 'class': 'sbk-cdx__tags' }, list.map(function (x) {
      return h('span', { 'class': 'sbk-cdx__tag' }, String(x));
    }));
  }

  function card(e, onPick) {
    var txtKids = [h('div', { 'class': 'sbk-cdx__nm' }, String(e.name === undefined ? '' : e.name))];
    if (e.desc) txtKids.push(h('div', { 'class': 'sbk-cdx__ds' }, String(e.desc)));
    var tg = tagRow(e);
    if (tg) txtKids.push(tg);
    var kids = [avatar(e, 'sbk-cdx__ava'), h('div', { 'class': 'sbk-cdx__txt' }, txtKids)];
    if (typeof onPick !== 'function') return h('div', { 'class': 'sbk-cdx__c' }, kids);
    /* 可点词条用 <button>：键盘可达，且点击宿主是 HTML 不是 SVG */
    var b = h('button', { type: 'button', 'class': 'sbk-cdx__c sbk-cdx__c--tap' }, kids);
    b.addEventListener('click', function (ev) {
      stop(ev);
      try { onPick(e); } catch (er) { SBK.warn('codex onSelect threw'); }
    });
    return b;
  }

  function grid(list, onPick) {
    if (!list.length) return h('div', { 'class': 'sbk-cdx__empty' }, '\u6682\u65e0\u8bcd\u6761');
    return h('div', { 'class': 'sbk-cdx__grid' }, list.map(function (e) { return card(e, onPick); }));
  }

  function codex(opts) {
    var o = opts || {};
    var list = (o.entries || []).filter(function (e) { return e; });
    var layout = LAYOUTS[o.layout] ? o.layout : 'single';
    var onPick = typeof o.onSelect === 'function' ? o.onSelect : null;
    css();

    var box = h('div', { 'class': 'sbk-cdx sbk-cdx--' + layout });
    var api = { el: function () { return box; }, layout: function () { return layout; },
                count: function () { return list.length; } };

    if (layout === 'nav') {
      /* 按 category 分组。分组只有一个时 ui-nav 自己就不建栏（≥2 才建），
         所以「带导航栏的图鉴」在只有一类人物时会自动退化成纯网格，不出空栏。 */
      var order = [], bag = {};
      list.forEach(function (e) {
        var k = e.category ? String(e.category) : '\u672a\u5206\u7c7b';
        if (!bag[k]) { bag[k] = []; order.push(k); }
        bag[k].push(e);
      });
      var mk = SBK.ui && SBK.ui.nav;
      if (typeof mk !== 'function') {
        SBK.warn('ui.codex: layout=nav needs ui-nav.js, falling back to a flat grid');
        box.appendChild(grid(list, onPick));
      } else {
        var nv = mk(order.map(function (k) {
          return { label: k, content: function () { return grid(bag[k], onPick); } };
        }), {});
        api.nav = function () { return nv; };
        api.categories = function () { return order.slice(); };
        box.appendChild(nv.el());
      }
      return api;
    }

    if (layout === 'swipe') {
      if (!list.length) { box.appendChild(h('div', { 'class': 'sbk-cdx__empty' }, '\u6682\u65e0\u8bcd\u6761')); return api; }
      var idx = 0;
      var strip = h('div', { 'class': 'sbk-cdx__strip' }, list.map(function (e) {
        var kids = [avatar(e, 'sbk-cdx__big'),
                    h('div', { 'class': 'sbk-cdx__nm' }, String(e.name === undefined ? '' : e.name))];
        if (e.desc) kids.push(h('div', { 'class': 'sbk-cdx__ds' }, String(e.desc)));
        var tg = tagRow(e);
        if (tg) kids.push(tg);
        return h('div', { 'class': 'sbk-cdx__slide' }, kids);
      }));
      var pos = h('span', { 'class': 'sbk-cdx__pos' });
      function show(i) {
        idx = i < 0 ? 0 : (i >= list.length ? list.length - 1 : i);
        pos.textContent = (idx + 1) + ' / ' + list.length;
        /* 触屏靠原生 scroll-snap 滑动；按钮路径用 scrollTo（桌面无触摸手势）。
           fake DOM 无 scrollTo，故守着调用。 */
        try {
          var w = strip.clientWidth || 0;
          if (typeof strip.scrollTo === 'function') strip.scrollTo({ left: idx * w, behavior: 'smooth' });
          else strip.scrollLeft = idx * w;
        } catch (e) {}
      }
      var prev = h('button', { type: 'button', 'class': 'sbk-cdx__nav' }, '\u2039');
      var next = h('button', { type: 'button', 'class': 'sbk-cdx__nav' }, '\u203a');
      prev.addEventListener('click', function (e) { stop(e); show(idx - 1); });
      next.addEventListener('click', function (e) { stop(e); show(idx + 1); });
      box.appendChild(strip);
      box.appendChild(h('div', { 'class': 'sbk-cdx__bar' }, [prev, pos, next]));
      show(0);
      api.show = show;
      api.index = function () { return idx; };
      return api;
    }

    /* single / double */
    box.appendChild(grid(list, onPick));
    return api;
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.codex = codex;
  SBK.ui.codex.layouts = function () { return ['single', 'double', 'nav', 'swipe']; };
  SBK.log('ui-codex ready (codex)');
})(typeof window !== 'undefined' ? window : globalThis);
