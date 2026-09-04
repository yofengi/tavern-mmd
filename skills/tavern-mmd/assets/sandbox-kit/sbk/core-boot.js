(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim || !SBK.state || !SBK.dom || !SBK.schedule) {
    (W.console && W.console.warn) && W.console.warn('[SBK] core-boot.js loaded before core.js');
    return;
  }
  if (!SBK.claim('core-boot')) return;

  var has = Object.prototype.hasOwnProperty;
  function own(o, k) { return has.call(o, k); }
  function warn(msg, extra) { SBK.warn(msg, extra); }
  function snap(o) {
    var r = {}, k;
    for (k in o) if (own(o, k)) r[k] = o[k];
    return r;
  }
  function normSchema(sc) {
    if (!sc || typeof sc !== 'object') return {};
    var out = snap(sc);
    if (!out.fields && out.rows) {
      out.fields = out.rows;
      delete out.rows;
      warn('schema.rows is a tolerated alias; rename it to schema.fields (authoritative key)');
    }
    if (own(out, 'persist')) {
      delete out.persist;
      warn('schema.persist is removed (it never did anything: no load, no save, no defined scope). ' +
        'Persist explicitly instead: SBK.store.save(obj) / SBK.store.load(), and decide the ' +
        'business scope yourself (which fields, when to write, what a conversation switch means).');
    }
    return out;
  }

  var MODES = { status: true, chrome: true, pinned: false };
  var PIN_MAX = 3;
  function normModes(m, ff) {
    var o = {}, k, warnf = typeof ff === 'function' ? ff : warn;
    for (k in MODES) if (own(MODES, k)) o[k] = MODES[k];
    if (!m || typeof m !== 'object') return o;
    if (own(m, 'snapshot') && !own(m, 'status')) {
      o.status = !!m.snapshot;
      warnf('modes.snapshot is the 1.0 name; renamed to modes.status (same meaning: in-bubble panel)');
    }
    if (own(m, 'hud') && !own(m, 'pinned')) {
      if (m.hud) {
        o.pinned = true;
        warnf('modes.hud is gone in 2.0. Mapped to modes.pinned, but semantics CHANGED: ' +
          'hud was a full panel in the toolbar, pinned is a single-line strip of 1..' + PIN_MAX +
          ' fields (set pinnedFields). The status panel now lives in the bubble (modes.status).');
      } else {
        warnf('modes.hud is gone in 2.0; ignored (it was false anyway). See modes.status/chrome/pinned.');
      }
    }
    for (k in MODES) if (own(MODES, k) && own(m, k)) o[k] = !!m[k];
    return o;
  }
  function normPins(v) {
    var out = [], i, s;
    if (typeof v === 'string') v = [v];
    if (!v || !v.length) return out;
    for (i = 0; i < v.length && out.length < PIN_MAX; i++) {
      s = v[i] === null || v[i] === undefined ? '' : String(v[i]).trim();
      if (s && out.indexOf(s) < 0) out.push(s);
    }
    return out;
  }

  var PIN_LEN = 24;
  function pinText(v) {
    if (v === null || v === undefined) return '';
    var t;
    if (typeof v !== 'object') t = String(v);
    else if (v.type === 'bar' && typeof v.value === 'number') {
      t = v.value + (typeof v.max === 'number' ? '/' + v.max : '');
    } else if (typeof v.raw === 'string' && v.raw) t = v.raw;
    else if (v.value !== null && v.value !== undefined && typeof v.value !== 'object') t = String(v.value);
    else t = '';
    return t.length > PIN_LEN ? t.slice(0, PIN_LEN - 1) + '…' : t;
  }
  function pinned(keys, hostId) {
    var ks = normPins(keys), host = null;
    var hid = SBK.dom.hostId(hostId === undefined || hostId === null || hostId === '' ? 'sbk-pin' : hostId);
    function draw() {
      if (!host) return;
      var s = SBK.state.get(), i, k, t, row;
      while (host.firstChild) host.removeChild(host.firstChild);
      row = SBK.dom.h('div', { 'class': 'sbk-pin' });
      for (i = 0; i < ks.length; i++) {
        k = ks[i];
        t = pinText(s[k]);
        if (!t) continue;
        row.appendChild(SBK.dom.h('span', { 'class': 'sbk-pin-item' }, [
          SBK.dom.h('span', { 'class': 'sbk-pin-k' }, k), SBK.dom.h('span', { 'class': 'sbk-pin-v' }, t)
        ]));
      }
      host.appendChild(row);
    }
    function paint() { SBK.schedule(draw); }
    function ensure(sync) {
      if (sync) host = SBK.dom.mountHost(hid) || host;
      return !!host;
    }
    function feed(text) {
      var r = SBK.parse(text);
      if (!r || !r.state) return false;
      SBK.state.patch(r.state);
      return true;
    }
    SBK.state.subscribe(paint);
    SBK.on('mount', function () { if (ensure(1)) paint(); });
    SBK.on('done', function (p, root) {
      if (!ensure(1)) return;
      if (!p || p.role === undefined || p.role === null || p.role === 'ai') {
        feed(p && typeof p.content === 'string' ? p.content : '');
      }
      paint();
    });
    return { el: function () { return host; }, render: paint, feed: feed, mount: ensure, keys: function () { return ks.slice(); } };
  }

  var booted = null;
  function boot(opts) {
    if (!SBK.claim('boot')) { SBK.log('boot already done, returning existing handle'); return booted; }

    var o = opts && typeof opts === 'object' ? opts : {};
    var md = normModes(o.modes);
    var pins = normPins(o.pinnedFields);
    var sc = normSchema(o.schema);
    var baseHost = SBK.dom.hostBaseId(o.hostId === undefined || o.hostId === null || o.hostId === '' ? 'sbk-hud' : o.hostId);
    if (o.hostId && !sc.hostId) sc.hostId = baseHost;
    var skipped = [];

    if (o.theme) {
      if (SBK.theme && typeof SBK.theme.apply === 'function') {
        try { SBK.theme.apply(o.theme); } catch (e) { skipped.push('theme'); warn('boot: theme.apply threw', e && e.message); }
      } else { skipped.push('theme'); warn('boot: theme layer not loaded, theme tokens ignored'); }
    }
    if (o.protocolTag) {
      if (SBK.parse && typeof SBK.parse.config === 'function') {
        try { SBK.parse.config({ block: o.protocolTag }); } catch (e) { warn('boot: parse.config threw', e && e.message); }
      } else { skipped.push('protocol'); warn('boot: protocol layer not loaded, protocolTag ignored'); }
    }

    var statusOn = false;
    if (md.status) {
      if (SBK.ui && SBK.ui.snapshot && typeof SBK.ui.snapshot.auto === 'function') {
        try { SBK.ui.snapshot.auto(sc); statusOn = true; }
        catch (e) { skipped.push('status'); warn('boot: snapshot.auto threw', e && e.message); }
      } else { skipped.push('status'); warn('boot: SBK.ui.snapshot not loaded, status panel disabled'); }
    }
    var chromeOn = false;
    if (md.chrome) {
      if (SBK.ui && typeof SBK.ui.chrome === 'function') {
        /* chrome 形态与文案透传：config.chrome 是可选对象，缺省即 dock 形态。
           只挑白名单键，不整个 spread —— 避免配置里的脏键混进 UI 层。 */
        var co = o.chrome && typeof o.chrome === 'object' ? o.chrome : {};
        var ca = { hostId: baseHost };
        if (co.form === 'bar' || co.form === 'dock') ca.form = co.form;
        if (co.side === 'left' || co.side === 'right') ca.side = co.side;
        if (typeof co.icon === 'string' && co.icon) ca.icon = co.icon;
        if (typeof co.label === 'string' && co.label) ca.label = co.label;
        if (typeof co.dockLabel === 'string' && co.dockLabel) ca.dockLabel = co.dockLabel;
        if (co.hoverOpen === false) ca.hoverOpen = false;
        if (co.settings === false) ca.settings = false;
        try { SBK.ui.chrome(ca); chromeOn = true; }
        catch (e) { skipped.push('chrome'); warn('boot: ui.chrome threw', e && e.message); }
      } else { skipped.push('chrome'); warn('boot: SBK.ui.chrome not loaded, toolbar entries disabled'); }
    }
    var pin = null;
    if (md.pinned) {
      if (!pins.length) {
        skipped.push('pinned');
        warn('boot: modes.pinned is on but pinnedFields is empty — nothing to show, strip skipped');
      } else pin = pinned(pins, baseHost + '-pin');
    }

    booted = {
      schema: sc,
      modes: { status: statusOn, chrome: chromeOn, pinned: !!pin },
      pinnedFields: pins,
      skipped: skipped,
      pinned: pin,
      el: function () { return pin ? pin.el() : null; },
      render: function () { if (pin) pin.render(); },
      feed: function (text) { return pin ? pin.feed(text) : false; },
      dispose: function () {
        if (SBK.theme && typeof SBK.theme.reset === 'function') { try { SBK.theme.reset(); } catch (e) {} }
        var host = pin ? pin.el() : null;
        if (host) { while (host.firstChild) host.removeChild(host.firstChild); }
        warn('boot: disposed visuals only; event subscriptions are not revocable (§4.2)');
      }
    };
    SBK.log('boot done: status=' + statusOn + ' chrome=' + chromeOn + ' pinned=' + !!pin +
      (skipped.length ? ' skipped=' + skipped.join(',') : ''));
    return booted;
  }

  SBK.boot = boot;
  SBK.schema = normSchema;
  SBK.modes = normModes;
  SBK.pins = normPins;
  SBK.pinned = pinned;
  SBK.log('core-boot ready');
})(typeof window !== 'undefined' ? window : globalThis);
