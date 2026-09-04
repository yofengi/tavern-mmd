(function (W) {
  'use strict';
  if (W.SBK && W.SBK.version) return;

  var S = W.sdk || {};
  var S_on = typeof S.on === 'function' ? S.on.bind(S) : null;
  var S_dbg = S.debug && typeof S.debug.log === 'function' ? S.debug.log.bind(S.debug) : null;

  function log() {
    if (!S_dbg) return;
    try { S_dbg.apply(null, ['[SBK]'].concat([].slice.call(arguments))); } catch (e) {}
  }
  function warn(msg, extra) { log('WARN ' + msg, extra === undefined ? '' : extra); }

  var claimed = {};
  function claim(name) {
    var k = String(name || 'anon');
    if (claimed[k]) { log('claim rejected: ' + k); return false; }
    claimed[k] = 1;
    return true;
  }

  var EVT = {
    'message:mount': 'mount',
    'message:done': 'done',
    'message:stream': 'stream',
    'message:unmount': 'unmount',
    'theme:change': 'theme',
    'conversation:switch': 'switch',
    'stage:close': 'stage:close',
    'back': 'back',
    'dispose': 'dispose',
    'ready': 'ready'
  };
  var subs = {};

  function on(evt, fn) {
    if (typeof fn !== 'function') return fn;
    (subs[evt] || (subs[evt] = [])).push(fn);
    return fn;
  }
  function off(evt, fn) {
    var a = subs[evt];
    if (!a) return false;
    for (var i = 0; i < a.length; i++) if (a[i] === fn) { a.splice(i, 1); return true; }
    return false;
  }
  function eventPayload(v) {
    if (!v || typeof v !== 'object') return v;
    if (Array.isArray(v) || isPlain(v) || v instanceof Date) return deep(v);
    return v;
  }
  function emit(evt, payload, root) {
    var a = subs[evt];
    if (!a || !a.length) return;
    var list = a.slice();
    for (var i = 0; i < list.length; i++) {
      try { list[i](eventPayload(payload), root); } catch (e) { warn('handler threw on ' + evt, e && e.message); }
    }
  }
  function bridge() {
    if (!S_on) { warn('sdk.on unavailable, bus is local-only'); return; }
    Object.keys(EVT).forEach(function (raw) {
      var name = EVT[raw];
      try {
        S_on(raw, function (payload) {
          var root = null;
          if (name === 'mount' || name === 'done' || name === 'stream') {
            try { root = W.document.querySelector('[data-chat="message"]'); } catch (e) { root = null; }
          }
          emit(name, payload, root);
        });
      } catch (e) { warn('bridge failed: ' + raw, e && e.message); }
    });
  }

  var st = {};
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  var DEPTH = 24;
  var cloneWarned = false;
  function cloneWarn(why) {
    if (cloneWarned) return;
    cloneWarned = true;
    warn('state value is not structurally cloneable, degraded: ' + why +
      ' (state should hold JSON-like values only: primitives / plain objects / arrays / Date)');
  }
  function clone(v, depth, seen) {
    if (v === null || typeof v !== 'object') {
      if (typeof v === 'function') { cloneWarn('function'); return null; }
      return v;
    }
    if (depth > DEPTH) { cloneWarn('nesting deeper than ' + DEPTH); return null; }
    if (seen.indexOf(v) >= 0) { cloneWarn('circular reference'); return null; }
    if (v.nodeType !== undefined && typeof v.nodeName === 'string') { cloneWarn('DOM node'); return null; }
    if (v instanceof Date) return new Date(v.getTime());
    seen.push(v);
    var out, i, k;
    if (Array.isArray(v)) {
      out = [];
      for (i = 0; i < v.length; i++) out.push(clone(v[i], depth + 1, seen));
    } else if (isPlain(v)) {
      out = {};
      for (k in v) if (has(v, k)) out[k] = clone(v[k], depth + 1, seen);
    } else {
      cloneWarn('exotic object (' + kindOf(v) + ')');
      out = {};
      for (k in v) if (has(v, k)) out[k] = clone(v[k], depth + 1, seen);
    }
    seen.pop();
    return out;
  }
  function isPlain(o) {
    var p = Object.getPrototypeOf ? Object.getPrototypeOf(o) : o.__proto__;
    return p === Object.prototype || p === null;
  }
  function kindOf(o) {
    try { return Object.prototype.toString.call(o).slice(8, -1); } catch (e) { return 'unknown'; }
  }
  function deep(o) { return clone(o, 0, []); }
  function emitState() {
    var a = subs.state;
    if (!a || !a.length) return;
    var list = a.slice();
    for (var i = 0; i < list.length; i++) {
      try { list[i](deep(st)); } catch (e) { warn('handler threw on state', e && e.message); }
    }
  }
  var state = {
    get: function () { return deep(st); },
    patch: function (p) {
      if (!p || typeof p !== 'object') return state.get();
      for (var k in p) if (has(p, k)) st[k] = deep(p[k]);
      emitState();
      return state.get();
    },
    replace: function (next) {
      st = next && typeof next === 'object' ? deep(next) : {};
      emitState();
      return state.get();
    },
    subscribe: function (fn) { on('state', fn); return function () { off('state', fn); }; }
  };
  var KEEP = /^_sbk/;
  function clearOnSwitch() {
    var k, n = 0;
    for (k in st) if (has(st, k) && !KEEP.test(k)) { delete st[k]; n++; }
    log('conversation switched, cleared ' + n + ' public state key(s), kept _sbk* internals');
    emitState();
  }
  on('switch', clearOnSwitch);

  var jobs = [], raf = null;
  var rAF = W.requestAnimationFrame ? W.requestAnimationFrame.bind(W) : function (f) { return W.setTimeout(f, 16); };
  function flush() {
    raf = null;
    var list = jobs; jobs = [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](); } catch (e) { warn('scheduled job threw', e && e.message); }
    }
  }
  function schedule(fn) {
    if (typeof fn !== 'function') return;
    if (jobs.indexOf(fn) < 0) jobs.push(fn);
    if (!raf) raf = rAF(flush);
  }

  var TAGS = ('p b a div span h1 h2 h3 h4 h5 h6 ul li ol strong em br img pre font i button table th tr td ' +
    'input textarea label select option video user summary details code blockquote hr del thead tbody s ' +
    'svg g path circle ellipse rect line polyline polygon text tspan defs use linearGradient radialGradient ' +
    'stop clipPath title').split(' ');
  var SVG = 'svg g path circle ellipse rect line polyline polygon text tspan defs use linearGradient radialGradient stop clipPath'.split(' ');
  var NS = 'http://www.w3.org/2000/svg';
  var XML_BAD = /((--!?|])>)|<\/(style|script|title|xmp|textarea|noscript|iframe|noembed|noframes)/i;
  function h(tag, attrs, children) {
    var t = String(tag || 'div').toLowerCase();
    if (TAGS.indexOf(t) < 0) { warn('tag not in worker whitelist, coerced to div: ' + t); t = 'div'; }
    var el = SVG.indexOf(t) >= 0 ? W.document.createElementNS(NS, t) : W.document.createElement(t);
    var k, v;
    if (attrs) for (k in attrs) {
      if (!has(attrs, k)) continue;
      v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      var lk = k.toLowerCase();
      if (lk.indexOf('data-') === 0 || lk.indexOf('aria-') === 0 || lk === 'role') {
        warn('attr stripped by sanitizer, use class instead: ' + k + ' on <' + t + '>');
        continue;
      }
      if (lk.indexOf('on') === 0 && SVG.indexOf(t) >= 0 && typeof v !== 'function') {
        warn('on* is removed inside SVG, wrap in an HTML host: ' + k);
        continue;
      }
      if (typeof v === 'function' && lk.indexOf('on') === 0) {
        el.addEventListener(lk.slice(2), v);
        continue;
      }
      v = v === true ? '' : String(v);
      if (XML_BAD.test(v)) {
        warn('attr value hits SAFE_FOR_XML and would be dropped whole: ' + k + '=' + v);
        continue;
      }
      try { el.setAttribute(k, v); } catch (e) { warn('setAttribute failed: ' + k, e && e.message); }
    }
    append(el, children);
    return el;
  }
  function append(el, c) {
    if (c === null || c === undefined || c === false) return;
    if (Array.isArray(c)) { for (var i = 0; i < c.length; i++) append(el, c[i]); return; }
    if (c && c.nodeType) { el.appendChild(c); return; }
    el.appendChild(W.document.createTextNode(String(c)));
  }
  function inBubble(root, sel) {
    if (!root || typeof root.querySelector !== 'function') { warn('inBubble called without a root element'); return null; }
    try { return root.querySelector(sel); } catch (e) { warn('inBubble bad selector: ' + sel); return null; }
  }
  function allInBubble(root, sel) {
    if (!root || typeof root.querySelectorAll !== 'function') return [];
    try { return [].slice.call(root.querySelectorAll(sel)); } catch (e) { return []; }
  }

  var hosts = {};
  function childIdOf(parent, id) {
    if (!parent || !id) return null;
    var k = parent.childNodes, i;
    for (i = 0; i < k.length; i++) if (k[i] && k[i].nodeType === 1 && k[i].id === id) return k[i];
    return null;
  }
  function adopt(keep, src) {
    if (!keep || !src || keep === src) return;
    var n, p;
    while (src.firstChild) {
      n = src.firstChild;
      p = n.id ? childIdOf(keep, n.id) : null;
      if (p) src.removeChild(n);
      else keep.appendChild(n);
    }
  }
  var HOST_ID = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
  var HOST_BASE_ID = /^[A-Za-z][A-Za-z0-9_-]{0,59}$/;
  var HOST_FALLBACK = 'sbk-host';
  var HOST_BASE_FALLBACK = 'sbk-hud';
  function normHostId(id) {
    var s = id === null || id === undefined ? '' : String(id);
    if (HOST_ID.test(s)) return s;
    warn('invalid host id ' + JSON.stringify(s) + ', falling back to "' + HOST_FALLBACK +
      '" (final DOM id must match /^[A-Za-z][A-Za-z0-9_-]{0,63}$/)');
    return HOST_FALLBACK;
  }
  function normHostBaseId(id) {
    var s = id === null || id === undefined ? '' : String(id);
    if (HOST_BASE_ID.test(s)) return s;
    warn('invalid host base id ' + JSON.stringify(s) + ', falling back to "' + HOST_BASE_FALLBACK +
      '" (config/chrome base must match /^[A-Za-z][A-Za-z0-9_-]{0,59}$/ so -pin/-chr stay within 64)');
    return HOST_BASE_FALLBACK;
  }
  function docById(d, id) {
    var out = [], all, i;
    try { all = d.querySelectorAll('[id]'); } catch (e) { return out; }
    for (i = 0; i < all.length; i++) if (all[i].id === id) out.push(all[i]);
    return out;
  }
  function mountHost(id) {
    var hid = normHostId(id === null || id === undefined || id === '' ? HOST_FALLBACK : id);
    var d = W.document;
    var root = d.querySelector('[data-chat="root"]');
    if (!root) { warn('mountHost: DOM not rendered yet (no [data-chat="root"]). Call it inside a mount/done handler.'); return null; }
    var sb = d.querySelector('[data-slot="statusbar"]'), slot = sb, got, i, n;
    var list = docById(d, hid);
    got = list[0];
    for (i = 0; i < list.length; i++) if (list[i].parentNode === sb) got = list[i];
    if (!got) {
      if (!slot) {
        slot = d.querySelector('[data-slot="left"]');
        warn('statusbar slot missing (card statusbar field empty?), falling back to [data-slot="left"]');
      }
      if (!slot) { slot = root; warn('no slot found, falling back to [data-chat="root"]'); }
      got = h('div', { id: hid, 'class': 'sbk-host' + (slot === sb ? '' : ' sbk-host--float') });
      slot.appendChild(got);
    }
    for (i = 0; i < list.length; i++) if ((n = list[i]) !== got) {
      adopt(got, n);
      n.parentNode.removeChild(n);
      warn('dup #' + hid + ' merged');
    }
    adopt(got, hosts[hid]);
    hosts[hid] = got;
    return got;
  }
  function sweep() {
    for (var k in hosts) mountHost(k);
  }
  on('mount', sweep); on('done', sweep);

  var SBK = {
    version: '1',
    claim: claim,
    on: on, off: off, emit: emit,
    state: state,
    schedule: schedule,
    dom: { h: h, mountHost: mountHost, hostId: normHostId, hostBaseId: normHostBaseId,
      childById: childIdOf, inBubble: inBubble, all: allInBubble },
    log: log, warn: warn,
    sdk: S,
    _coreKit: { deep: deep },
    parse: function () { warn('SBK.parse called but protocol layer (WP-2) is not loaded'); return null; },
    theme: {},
    ui: {}
  };
  W.SBK = SBK;

  if (claim('core')) bridge();
  log('core ready v' + SBK.version);
})(typeof window !== 'undefined' ? window : globalThis);
