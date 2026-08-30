/* SBK map：地图。两族 —— 图片地图与渲染地图。
   ------------------------------------------------------------------
   典型放置：气泡侧边栏的一枚独立页签（速查当前位置），大图缩放版更适合挂舞台
   （`sdk.stage`）—— 气泡只有 278px 宽，捏合缩放一张世界地图会很憋屈。

   两族（用户口径）：
   · image  图片地图：一张大图，可缩放（按钮 + 滚轮 + 拖拽平移），图上有可点标记，
            点标记弹出小气泡说明。也支持「大图套小图」：点标记后换一张子区域图（drill）。
   · grid   渲染地图：纯文字 / 像素格。可点格子，可按状态栏地点高亮当前位置。

   ⚠ 「捕获状态栏地点来显示附近地图」这件事本模块**不自己订阅事件**：
     它只暴露 `focus(name)`。要联动就由做卡人在 `message:done` 里解析出地点再调它 ——
     状态数据的解析归协议层（`SBK.parse`），地图只负责画。这样换协议不必改地图。

   图片：CSP `img-src 'self' data: blob: https:` → 远程图与 data: 都可用（§13）。
   🚨 缩放用 transform:scale 加在【内层】包裹上，标记按百分比定位在同一包裹里 ——
      这样标记随图一起缩放平移，不必逐个重算坐标。但标记的【视觉大小】要抗缩放，
      故标记自身反向 scale(1/z)，否则放大到 3 倍时标记也变成 3 倍大。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-map.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-map')) return;

  var kit = SBK._uiKit;
  if (!kit) { SBK.warn('ui-map: SBK._uiKit missing (ui.js not loaded?)'); return; }

  var d = W.document, h = SBK.dom.h, stop = kit.stop, clamp = kit.clamp;
  var CSS_ID = 'sbk-map-css';
  var CSS = [
    '.sbk-map{display:flex;flex-direction:column;gap:8px;min-width:0}',
    /* 视口：裁掉缩放溢出。position:relative 给标记气泡当定位锚 */
    '.sbk-map__vp{position:relative;overflow:hidden;border:1px solid var(--chat-border);' +
      'border-radius:10px;background:var(--chat-bg);height:var(--sbk-map-h,200px);' +
      'touch-action:none;cursor:grab}',
    '.sbk-map__vp--drag{cursor:grabbing}',
    /* 内层：被 scale/translate 的那一层，图与标记都在里面 */
    '.sbk-map__in{position:absolute;left:0;top:0;width:100%;height:100%;' +
      'transform-origin:0 0;will-change:transform}',
    '.sbk-map__img{width:100%;height:100%;object-fit:contain;display:block;' +
      'pointer-events:none;user-select:none;-webkit-user-drag:none}',
    /* 标记：百分比定位 → 随图缩放平移；自身反向缩放 → 视觉大小恒定 */
    '.sbk-map__pin{position:absolute;width:22px;height:22px;margin:-11px 0 0 -11px;padding:0;' +
      'border-radius:50%;border:2px solid var(--sbk-on-accent,#fff);' +
      'background:var(--chat-accent);color:var(--sbk-on-accent,#fff);' +
      'font-family:inherit;font-size:11px;line-height:1;cursor:pointer;' +
      'display:flex;align-items:center;justify-content:center;' +
      'box-shadow:0 1px 4px rgba(0,0,0,.5);transform-origin:center center}',
    '.sbk-map__pin:hover{filter:brightness(1.15)}',
    '.sbk-map__pin:focus-visible{outline:2px solid var(--chat-accent);outline-offset:3px}',
    '.sbk-map__pin--here{background:var(--sbk-hp,#ff4d4f)}',
    /* 标记说明气泡：贴在视口内，不用 ui-bubble（那个是锚在侧边按钮上的） */
    '.sbk-map__tip{position:absolute;max-width:70%;padding:6px 9px;border-radius:8px;' +
      'background:var(--chat-more-item-bg,#2c2e32);border:1px solid var(--chat-accent);' +
      'color:var(--chat-text);font-size:var(--sbk-cfs-xs,12px);line-height:1.45;' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));z-index:2;display:none}',
    '.sbk-map__tip--on{display:block}',
    '.sbk-map__tip b{display:block;color:var(--chat-accent);font-size:var(--sbk-cfs-sm,13px)}',
    /* 工具条 */
    '.sbk-map__bar{display:flex;align-items:center;gap:6px}',
    '.sbk-map__btn{width:30px;height:30px;padding:0;border-radius:8px;' +
      'border:1px solid var(--chat-border);background:var(--chat-surface);' +
      'color:var(--chat-text);font-family:inherit;font-size:15px;line-height:1;cursor:pointer}',
    '.sbk-map__btn:hover{border-color:var(--chat-accent);color:var(--chat-accent)}',
    '.sbk-map__btn:focus-visible{outline:2px solid var(--chat-accent);outline-offset:2px}',
    '.sbk-map__z{color:var(--chat-text-muted);font-size:var(--sbk-cfs-xs,12px);' +
      'font-variant-numeric:tabular-nums;min-width:38px;text-align:center}',
    '.sbk-map__where{flex:1 1 auto;min-width:0;text-align:right;color:var(--chat-text-muted);' +
      'font-size:var(--sbk-cfs-xs,12px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    /* 渲染地图：等宽字符格。cell 用 button 以便可点 */
    '.sbk-map__grid{display:grid;gap:2px;padding:8px;border:1px solid var(--chat-border);' +
      'border-radius:10px;background:var(--chat-bg);overflow:auto}',
    '.sbk-map__cell{aspect-ratio:1/1;min-width:18px;min-height:18px;padding:0;border:0;' +
      'border-radius:4px;background:var(--sbk-lift,rgba(255,255,255,.05));' +
      'color:var(--chat-text);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;' +
      'font-size:13px;line-height:1;display:flex;align-items:center;justify-content:center;' +
      'cursor:default}',
    '.sbk-map__cell--tap{cursor:pointer}',
    '.sbk-map__cell--tap:hover{background:var(--chat-border)}',
    '.sbk-map__cell--here{background:var(--chat-accent);color:var(--sbk-on-accent,#fff);' +
      'font-weight:700}',
    '.sbk-map__cell:focus-visible{outline:2px solid var(--chat-accent);outline-offset:-2px}',
    '@media (max-width:420px){.sbk-map__vp{height:var(--sbk-map-h,168px)}}'
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

  var ZMIN = 1, ZMAX = 4;

  /* ---- 图片地图 ---- */
  function imageMap(o) {
    var marks = (o.marks || []).filter(function (m) { return m; });
    var z = 1, tx = 0, ty = 0, here = o.here ? String(o.here) : '';
    var img = null, inner = null, vp = null, tip = null, zTxt = null, whereTxt = null;
    var pins = [], api;

    function applyTx() {
      if (!inner) return;
      /* 平移量夹住：放大 z 倍后可移动范围是 (z-1) × 视口尺寸 */
      var w = vp.clientWidth || 0, hh = vp.clientHeight || 0;
      var maxX = w * (z - 1), maxY = hh * (z - 1);
      tx = clamp(tx, -maxX, 0);
      ty = clamp(ty, -maxY, 0);
      inner.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + z + ')';
      /* 标记反向缩放，视觉大小恒定 */
      for (var i = 0; i < pins.length; i++) pins[i].style.transform = 'scale(' + (1 / z) + ')';
      if (zTxt) zTxt.textContent = z.toFixed(1) + '\u00d7';
    }
    function zoom(next, ox, oy) {
      var prev = z;
      z = clamp(next, ZMIN, ZMAX);
      if (z === prev) return;
      /* 以某点为锚缩放：保持该点在视口里的位置不变 */
      var w = vp.clientWidth || 0, hh = vp.clientHeight || 0;
      var cx = ox === undefined ? w / 2 : ox, cy = oy === undefined ? hh / 2 : oy;
      tx = cx - (cx - tx) * (z / prev);
      ty = cy - (cy - ty) * (z / prev);
      applyTx();
    }
    function showTip(m, pin) {
      if (!tip) return;
      var kids = [h('b', null, String(m.name === undefined ? '' : m.name))];
      if (m.desc) kids.push(h('span', null, String(m.desc)));
      while (tip.firstChild) tip.removeChild(tip.firstChild);
      for (var i = 0; i < kids.length; i++) tip.appendChild(kids[i]);
      tip.setAttribute('class', 'sbk-map__tip sbk-map__tip--on');
      /* 贴在标记在【视口坐标】里的位置：标记在内层，故要经过当前 transform */
      var px = (parseFloat(m.x) || 0) / 100, py = (parseFloat(m.y) || 0) / 100;
      var w = vp.clientWidth || 0, hh = vp.clientHeight || 0;
      var vx = px * w * z + tx, vy = py * hh * z + ty;
      tip.style.left = clamp(vx + 14, 6, Math.max(6, w - 6)) + 'px';
      tip.style.top = clamp(vy - 8, 6, Math.max(6, hh - 6)) + 'px';
      if (typeof o.onSelect === 'function') { try { o.onSelect(m, api); } catch (e) {} }
      /* 大图套小图：标记带 map 就换底图（drill down） */
      if (m.map && img) { img.setAttribute('src', String(m.map)); z = 1; tx = ty = 0; applyTx(); }
    }
    function hideTip() { if (tip) tip.setAttribute('class', 'sbk-map__tip'); }

    function build() {
      css();
      inner = h('div', { 'class': 'sbk-map__in' });
      if (o.src) {
        img = h('img', { 'class': 'sbk-map__img', src: String(o.src), alt: '', draggable: 'false' });
        inner.appendChild(img);
      }
      pins = marks.map(function (m) {
        var isHere = here && String(m.name) === here;
        var b = h('button', {
          type: 'button',
          'class': 'sbk-map__pin' + (isHere ? ' sbk-map__pin--here' : ''),
          title: String(m.name === undefined ? '' : m.name)
        }, String(m.icon === undefined ? '' : m.icon));
        b.style.left = (parseFloat(m.x) || 0) + '%';
        b.style.top = (parseFloat(m.y) || 0) + '%';
        b.addEventListener('click', function (e) { stop(e); showTip(m, b); });
        inner.appendChild(b);
        return b;
      });
      tip = h('div', { 'class': 'sbk-map__tip' });
      vp = h('div', { 'class': 'sbk-map__vp' }, [inner, tip]);
      if (o.height) vp.style.setProperty('--sbk-map-h', String(o.height));

      /* 拖拽平移。pointer 事件在触屏与鼠标上统一；touch-action:none 交给我们处理 */
      var on = false, sx = 0, sy = 0, ox = 0, oy = 0, moved = false, pid = null;
      vp.addEventListener('pointerdown', function (e) {
        if (z <= 1) return;                    /* 未放大时不拖，免得与页面滚动打架 */
        on = true; moved = false; sx = e.clientX; sy = e.clientY; ox = tx; oy = ty; pid = e.pointerId;
        try { vp.setPointerCapture(pid); } catch (er) {}
        vp.setAttribute('class', 'sbk-map__vp sbk-map__vp--drag');
      });
      vp.addEventListener('pointermove', function (e) {
        if (!on) return;
        var dx = e.clientX - sx, dy = e.clientY - sy;
        if (!moved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) moved = true;
        if (!moved) return;
        tx = ox + dx; ty = oy + dy;
        applyTx();
        stop(e);
      });
      function up() {
        if (!on) return;
        on = false;
        try { vp.releasePointerCapture(pid); } catch (er) {}
        vp.setAttribute('class', 'sbk-map__vp');
      }
      vp.addEventListener('pointerup', up);
      vp.addEventListener('pointercancel', up);
      /* 滚轮缩放。passive:false 才能 preventDefault 拦掉页面滚动 */
      if (o.wheel !== false) {
        try {
          vp.addEventListener('wheel', function (e) {
            if (e.preventDefault) e.preventDefault();
            var r = vp.getBoundingClientRect();
            zoom(z + (e.deltaY > 0 ? -0.25 : 0.25), e.clientX - r.left, e.clientY - r.top);
          }, { passive: false });
        } catch (er) {}
      }
      vp.addEventListener('click', function (e) {
        /* 点空白处收气泡；点标记时标记自己已 stopPropagation */
        if (e.target === vp || e.target === inner || e.target === img) hideTip();
      });

      var zo = h('button', { type: 'button', 'class': 'sbk-map__btn', title: '\u7f29\u5c0f' }, '\u2212');
      var zi = h('button', { type: 'button', 'class': 'sbk-map__btn', title: '\u653e\u5927' }, '+');
      var rs = h('button', { type: 'button', 'class': 'sbk-map__btn', title: '\u590d\u4f4d' }, '\u25a1');
      zo.addEventListener('click', function (e) { stop(e); zoom(z - 0.5); });
      zi.addEventListener('click', function (e) { stop(e); zoom(z + 0.5); });
      rs.addEventListener('click', function (e) { stop(e); z = 1; tx = ty = 0; applyTx(); hideTip(); });
      zTxt = h('span', { 'class': 'sbk-map__z' }, '1.0\u00d7');
      whereTxt = h('span', { 'class': 'sbk-map__where' }, here);
      var box = h('div', { 'class': 'sbk-map' }, [
        vp, h('div', { 'class': 'sbk-map__bar' }, [zo, zi, rs, zTxt, whereTxt])
      ]);
      applyTx();
      return box;
    }

    var el = build();
    api = {
      el: function () { return el; },
      kind: function () { return 'image'; },
      zoom: function (v) { if (v === undefined) return z; zoom(v); return z; },
      reset: function () { z = 1; tx = ty = 0; applyTx(); hideTip(); return api; },
      pins: function () { return pins.slice(); },
      /* 联动出口：做卡人在 message:done 里解析出地点后调它。本模块不自己订阅事件。 */
      focus: function (name) {
        here = name ? String(name) : '';
        if (whereTxt) whereTxt.textContent = here;
        for (var i = 0; i < marks.length; i++) {
          var isHere = here && String(marks[i].name) === here;
          pins[i].setAttribute('class', 'sbk-map__pin' + (isHere ? ' sbk-map__pin--here' : ''));
          if (isHere) showTip(marks[i], pins[i]);
        }
        return api;
      },
      here: function () { return here; }
    };
    return api;
  }

  /* ---- 渲染地图（纯文字 / 像素格）---- */
  function gridMap(o) {
    css();
    var rows = (o.rows || []).filter(function (r) { return r !== undefined && r !== null; });
    var here = o.here ? String(o.here) : '';
    var cells = [], api;
    /* rows 支持两种写法：字符串（每字符一格）或数组（每项一格，可为对象） */
    var matrix = rows.map(function (r) {
      if (typeof r === 'string') return r.split('').map(function (ch) { return { t: ch }; });
      return (r || []).map(function (c) {
        return (c && typeof c === 'object') ? c : { t: String(c === undefined ? '' : c) };
      });
    });
    var wide = 0;
    matrix.forEach(function (r) { if (r.length > wide) wide = r.length; });

    var box = h('div', { 'class': 'sbk-map' });
    var g = h('div', { 'class': 'sbk-map__grid' });
    g.style.gridTemplateColumns = 'repeat(' + (wide || 1) + ', minmax(18px, 1fr))';
    matrix.forEach(function (r, ri) {
      r.forEach(function (c, ci) {
        var tap = typeof o.onSelect === 'function';
        var isHere = here && c.name && String(c.name) === here;
        var cell = h('button', {
          type: 'button',
          'class': 'sbk-map__cell' + (tap ? ' sbk-map__cell--tap' : '') +
                   (isHere ? ' sbk-map__cell--here' : ''),
          title: c.name ? String(c.name) : ''
        }, String(c.t === undefined ? '' : c.t));
        if (c.color) cell.style.background = String(c.color);
        if (tap) {
          cell.addEventListener('click', function (e) {
            stop(e);
            try { o.onSelect(c, { row: ri, col: ci }, api); } catch (er) { SBK.warn('map onSelect threw'); }
          });
        }
        cells.push({ el: cell, c: c });
        g.appendChild(cell);
      });
    });
    box.appendChild(g);
    var whereTxt = null;
    if (o.showWhere !== false) {
      whereTxt = h('span', { 'class': 'sbk-map__where' }, here);
      box.appendChild(h('div', { 'class': 'sbk-map__bar' }, [whereTxt]));
    }
    api = {
      el: function () { return box; },
      kind: function () { return 'grid'; },
      cells: function () { return cells.map(function (x) { return x.el; }); },
      focus: function (name) {
        here = name ? String(name) : '';
        if (whereTxt) whereTxt.textContent = here;
        cells.forEach(function (x) {
          var isHere = here && x.c.name && String(x.c.name) === here;
          var cl = x.el.getAttribute('class').replace(/\s*sbk-map__cell--here/g, '');
          x.el.setAttribute('class', cl + (isHere ? ' sbk-map__cell--here' : ''));
        });
        return api;
      },
      here: function () { return here; }
    };
    return api;
  }

  function map(opts) {
    var o = opts || {};
    var kind = o.kind === 'grid' ? 'grid' : (o.kind === 'image' ? 'image' : (o.rows ? 'grid' : 'image'));
    if (kind === 'grid') return gridMap(o);
    if (!o.src) SBK.warn('ui.map: kind=image without src — only marks will render');
    return imageMap(o);
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.map = map;
  SBK.ui.map.kinds = function () { return ['image', 'grid']; };
  SBK.log('ui-map ready (map)');
})(typeof window !== 'undefined' ? window : globalThis);
