(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-panel.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-panel')) return;

  var kit = SBK._uiKit;
  if (!kit) {
    SBK.warn('ui-panel: SBK._uiKit missing (ui.js not loaded?)');
    return;
  }
  var d = W.document, h = SBK.dom.h, schedule = SBK.schedule;
  var injectCss = kit.injectCss, childById = kit.childById, defer = kit.defer;
  var armStop = kit.armStop, headOf = kit.headOf, slotOf = kit.slotOf;
  var viewRect = kit.viewRect, clamp = kit.clamp, place = kit.place, stop = kit.stop;
  var reg = {};

  function panel(opts) {
    var o = opts || {};
    var id = String(o.id || 'sbk-panel');
    if (reg[id]) { SBK.warn('ui.panel: id already mounted, returning existing: ' + id); return reg[id]; }
    var side = o.side === 'left' ? 'left' : 'right';
    var mode = o.mode === 'drawer' ? 'drawer' : (o.mode === 'bare' ? 'bare' : 'ball');
    var wantDrag = o.drag !== false && mode !== 'bare';
    var wantMask = o.mask === undefined ? mode === 'drawer' : !!o.mask;
    var LS = 'sbk-pnl-' + id;
    var wrap = null, ball = null, box = null, mask = null, opened = !!o.open, built = false, dead = false;
    var pos = o.pos && typeof o.pos.x === 'number' ? { x: o.pos.x, y: o.pos.y } : null;
    var api, lastFocus = null, epoch = 0;

    function savePos() {
      if (o.remember === false || !pos) return;
      try { W.localStorage.setItem(LS, pos.x + ',' + pos.y); } catch (e) {}
    }
    function loadPos() {
      if (o.remember === false) return null;
      try {
        var s = W.localStorage.getItem(LS);
        if (!s) return null;
        var a = s.split(','), x = parseFloat(a[0]), y = parseFloat(a[1]);
        if (isFinite(x) && isFinite(y)) return { x: x, y: y };
      } catch (e) {}
      return null;
    }
    function applyPos() {
      if (!ball) return;
      var v = viewRect(), bw = ball.offsetWidth || 40, bh = ball.offsetHeight || 40, m = 4;
      if (!pos) pos = { x: side === 'left' ? v.l + m : v.l + v.w - bw - m, y: v.t + v.h * 0.62 };
      pos.x = clamp(pos.x, v.l + m, Math.max(v.l + m, v.l + v.w - bw - m));
      pos.y = clamp(pos.y, v.t + m, Math.max(v.t + m, v.t + v.h - bh - m));
      ball.style.left = pos.x + 'px';
      ball.style.top = pos.y + 'px';
    }
    function arm(el) {
      var sx = 0, sy = 0, ox = 0, oy = 0, moved = false, on = false, pid = null, suppress = false;
      el.addEventListener('pointerdown', function (e) {
        suppress = false;
        if (!wantDrag) return;
        on = true; moved = false; sx = e.clientX; sy = e.clientY; ox = pos ? pos.x : 0; oy = pos ? pos.y : 0; pid = e.pointerId;
        try { el.setPointerCapture(pid); } catch (er) {}
        stop(e);
      });
      el.addEventListener('pointermove', function (e) {
        if (!on) return;
        var dx = e.clientX - sx, dy = e.clientY - sy;
        if (!moved && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) {
          moved = true;
          el.setAttribute('class', 'sbk-pnl__ball sbk-pnl__ball--drag');
        }
        if (!moved) return;
        pos = { x: ox + dx, y: oy + dy };
        schedule(applyPos);
        if (typeof o.onDrag === 'function') { try { o.onDrag(pos); } catch (er) {} }
        stop(e);
      });
      function up(e) {
        if (!on) return;
        on = false;
        try { el.releasePointerCapture(pid); } catch (er) {}
        el.setAttribute('class', 'sbk-pnl__ball');
        if (moved) { applyPos(); savePos(); suppress = true; }
        moved = false;
        stop(e);
      }
      el.addEventListener('pointerup', up);
      el.addEventListener('pointercancel', up);
      el.addEventListener('click', function (e) {
        stop(e);
        if (suppress) { suppress = false; return; }
        api.toggle();
      });
      el.addEventListener('keydown', function (e) {
        var k = e && e.key;
        if (k === 'Enter' || k === ' ' || k === 'Spacebar') suppress = false;
      });
      el.addEventListener('contextmenu', stop);
      return el;
    }
    function bodyNode() {
      var c = typeof o.content === 'function' ? o.content(api) : o.content;
      if (c && c.nodeType) return c;
      if (typeof c === 'string') return h('div', { 'class': 'sbk-pre' }, c);
      return null;
    }
    function menuNode() {
      var items = o.menu || [], k = [], i;
      for (i = 0; i < items.length; i++) {
        (function (it) {
          var cls = 'sbk-pop__item' + (it.disabled ? ' sbk-pop__item--off' : '');
          var attrs = {
            type: 'button',
            'class': cls,
            onclick: function (e) {
              stop(e);
              if (it.disabled) return;
              if (typeof it.onSelect === 'function') { try { it.onSelect(api, it); } catch (er) { SBK.warn('menu onSelect threw'); } }
              if (it.keepOpen !== true) api.close();
            }
          };
          if (it.disabled) attrs.disabled = true;
          k.push(h('button', attrs, String(it.label === undefined ? '' : it.label)));
        })(items[i]);
      }
      return k;
    }

    var DRW = 'sbk-drw sbk-drw--' + (side === 'left' ? 'l' : 'r');
    function buildBox() {
      var body = bodyNode(), kids = [];
      var hd = headOf(o.title, o.title && o.closeButton !== false, function () { api.close(); });
      if (hd) kids.push(hd);
      if (body) kids.push(h('div', { 'class': 'sbk-pnl__bd' }, body));
      else if (o.menu) kids = kids.concat(menuNode());
      if (mode === 'drawer') {
        box = h('div', { 'class': DRW }, kids);
        if (o.width) box.style.setProperty('--sbk-drw-w', String(o.width));
      } else {
        box = h('div', { 'class': 'sbk-pop' + (body ? ' sbk-pop--pad' : '') }, kids);
        box.style.display = 'none';
      }
      armStop(box);
      return box;
    }
    function build() {
      if (dead || built) return dead ? false : true;
      var slot = slotOf(side);
      if (!slot) { SBK.warn('ui.panel: no mount point yet'); return false; }
      injectCss();
      var found = childById(slot, id);
      if (found) { wrap = found; while (wrap.firstChild) wrap.removeChild(wrap.firstChild); }
      else { wrap = h('div', { id: id, 'class': 'sbk-pnl' }); slot.appendChild(wrap); }
      if (mode !== 'bare') {
        var ic = o.icon;
        ball = h('button', { type: 'button', 'class': 'sbk-pnl__ball' }, ic && ic.nodeType ? ic : String(ic === undefined ? '\u2630' : ic));
        arm(ball);
        wrap.appendChild(ball);
        pos = pos || loadPos();
        applyPos();
      }
      buildBox();
      wrap.appendChild(box);
      built = true;
      if (opened) { opened = false; api.open(); }
      return true;
    }
    function focusablesIn(el) {
      if (!el || typeof el.querySelectorAll !== 'function') return [];
      var out = [], n, i;
      try { n = el.querySelectorAll('button,input,select,textarea,a[href],[tabindex]'); } catch (e) { return out; }
      for (i = 0; i < n.length; i++) {
        if (n[i].disabled) continue;
        if (n[i].getAttribute && n[i].getAttribute('tabindex') === '-1') continue;
        out.push(n[i]);
      }
      return out;
    }
    function onEsc(e) {
      var k = e && e.key;
      if ((k === 'Escape' || k === 'Esc') && opened) api.close();
    }
    function grabFocus(keepOrigin) {
      if (!keepOrigin) {
        try { lastFocus = d.activeElement || null; } catch (e) { lastFocus = null; }
      }
      if (mode !== 'drawer' || !box) return;
      var f = focusablesIn(box);
      try {
        if (f.length) f[0].focus();
        else if (box.focus) { box.setAttribute('tabindex', '-1'); box.focus(); }
      } catch (e) {}
    }
    function releaseFocus() {
      var t = lastFocus;
      lastFocus = null;
      if (!t || typeof t.focus !== 'function') return;
      try { if (d.body && !d.body.contains(t)) return; } catch (e) { return; }
      try { t.focus(); } catch (e) {}
    }

    function open(keepOrigin) {
      if (!built) {
        var token = ++epoch;
        defer(function () {
          if (dead || token !== epoch) return;
          build();
          if (!dead && built && token === epoch && !opened) open(keepOrigin);
        });
        return api;
      }
      if (opened) return api;
      opened = true;
      if (mode === 'drawer') {
        if (wantMask && !mask) {
          mask = h('div', { 'class': 'sbk-mask', onclick: function (e) { stop(e); api.close(); } });
          wrap.appendChild(mask);
        }
        box.setAttribute('class', DRW + ' sbk-drw--on');
      } else {
        var a = ball ? ball.getBoundingClientRect() : { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 };
        place(box, a, { side: o.popSide === 'x' ? 'x' : 'y' });
        box.style.visibility = 'visible';
      }
      try { d.addEventListener('keydown', onEsc, true); } catch (e) {}
      grabFocus(keepOrigin === true);
      if (typeof o.onOpen === 'function') { try { o.onOpen(api); } catch (e) {} }
      return api;
    }

    api = {
      el: function () { return wrap; },
      ball: function () { return ball; },
      box: function () { return box; },
      opened: function () { return opened; },
      open: function () { return open(false); },
      close: function () {
        epoch++;
        if (!built || !opened) { opened = false; return api; }
        opened = false;
        try { d.removeEventListener('keydown', onEsc, true); } catch (e) {}
        if (mode === 'drawer') {
          box.setAttribute('class', DRW);
          if (mask && mask.parentNode) { mask.parentNode.removeChild(mask); mask = null; }
        } else box.style.display = 'none';
        releaseFocus();
        if (typeof o.onClose === 'function') { try { o.onClose(api); } catch (e) {} }
        return api;
      },
      toggle: function () { return opened ? api.close() : api.open(); },
      setContent: function (c) {
        o.content = c;
        if (!built) return api;
        var was = opened;
        if (box && box.parentNode) box.parentNode.removeChild(box);
        opened = false;
        buildBox();
        wrap.appendChild(box);
        if (was) open(true);
        return api;
      },
      move: function (x, y) { pos = { x: x, y: y }; applyPos(); savePos(); return api; },
      destroy: function () {
        epoch++;
        SBK.off('mount', onMount);
        SBK.off('back', onBack);
        try { d.removeEventListener('keydown', onEsc, true); } catch (e) {}
        lastFocus = null;
        if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
        wrap = ball = box = mask = null; built = false; opened = false; dead = true;
        delete reg[id];
        return null;
      }
    };
    function onMount() {
      if (built && wrap && !wrap.parentNode) { built = false; build(); }
    }
    function onBack() { if (opened && o.closeOnBack !== false) api.close(); }
    reg[id] = api;
    defer(build);
    SBK.on('mount', onMount);
    SBK.on('back', onBack);
    return api;
  }

  var chromeApi = null;
  function chrome(a, b) {
    var pre = a && a.nodeType === 1 ? a : null;
    var o = (pre ? b : a) || {};
    if (chromeApi) { SBK.warn('ui.chrome: already mounted, returning existing'); return chromeApi; }
    var normBase = SBK.dom.hostBaseId || SBK.dom.hostId;
    var hid = normBase ? normBase(o.hostId || 'sbk-hud') : String(o.hostId || 'sbk-hud');
    var gid = hid + '-chr';
    var grp = null, built = false;
    function prefs() {
      var t = SBK.theme;
      if (t && t.prefs && typeof t.prefs.toggle === 'function') return t.prefs;
      SBK.warn('ui.chrome: theme prefs layer not loaded, settings entry is inert');
      return null;
    }
    function build() {
      if (built) return true;
      var host = pre || SBK.dom.mountHost(hid);
      if (!host) { SBK.warn('ui.chrome: no mount point yet'); return false; }
      injectCss();
      grp = childById(host, gid);
      if (grp) { while (grp.firstChild) grp.removeChild(grp.firstChild); }
      else { grp = h('div', { id: gid, 'class': 'sbk-chr' }); host.appendChild(grp); }
      var t = SBK.theme;
      if (t && typeof t.start === 'function') {
        try { t.start(o.preset, o); } catch (e) { SBK.warn('ui.chrome: theme.start threw', e && e.message); }
      }
      var list = [];
      if (o.settings !== false) list.push({ label: o.label || '\u8bbe\u7f6e', onSelect: function () { var p = prefs(); if (p) p.toggle(); } });
      if (o.entries && o.entries.length) list = list.concat(o.entries);
      list.forEach(function (it) {
        grp.appendChild(h('button', {
          type: 'button',
          'class': 'sbk-btn' + (it.accent ? ' sbk-btn--accent' : ''),
          onclick: function (ev) {
            stop(ev);
            if (typeof it.onSelect === 'function') { try { it.onSelect(chromeApi); } catch (er) { SBK.warn('chrome entry threw'); } }
          }
        }, String(it.label === undefined ? '' : it.label)));
      });
      armStop(grp);
      built = true;
      return true;
    }
    chromeApi = {
      el: function () { return grp; },
      panel: function () { var p = prefs(); return p ? p.panel() : null; },
      toggle: function () { var p = prefs(); if (p) p.toggle(); return chromeApi; }
    };
    defer(build);
    SBK.on('mount', function () {
      if (built && grp && !grp.parentNode) { built = false; build(); }
    });
    return chromeApi;
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.panel = panel;
  SBK.ui.chrome = chrome;
  SBK.log('ui-panel ready (panel, chrome)');
})(typeof window !== 'undefined' ? window : globalThis);
