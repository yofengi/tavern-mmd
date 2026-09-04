/* SBK hud-render —— 气泡状态面板与快照出口。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] hud-render.js loaded before core.js');
    return;
  }
  if (!SBK.claim('hud-render')) return;
  var kit = SBK._hudKit;
  if (!kit || !kit.TYPES || !kit.pick || !kit.PANEL || !kit.SNAP || !kit.toDom || !kit.toHtml) {
    SBK.warn('hud-render.js loaded before hud.js');
    return;
  }
  var TYPES = kit.TYPES, PANEL = kit.PANEL, SNAP = kit.SNAP, pick = kit.pick, toDom = kit.toDom, toHtml = kit.toHtml;

  function tree(state, schema, order) {
    var fs = pick(state, schema, order), out = [], cur = null, curLabel = '', curTone = '', i, f, fn, node;
    if (schema && schema.title) out.push({ t: 'div', c: 'sbk-label sbk-title', x: schema.title });
    function flush() {
      if (cur && cur.length) {
        var k = curLabel ? [{ t: 'div', c: 'sbk-label sbk-sect__t', x: curLabel }].concat(cur) : cur;
        out.push({ t: 'div', c: PANEL + ' sbk-sect' + (curTone ? ' sbk-tone--' + curTone : ''), k: k });
      }
      cur = null; curLabel = ''; curTone = '';
    }
    for (i = 0; i < fs.length; i++) {
      f = fs[i];
      if (f.type === 'section') { flush(); cur = []; curLabel = f.label; curTone = f.tone || ''; continue; }
      fn = TYPES[f.type] || TYPES.text;
      node = null;
      try { node = fn(f); } catch (e) { SBK.warn('hud: renderer threw for ' + f.key); }
      if (!node) continue;
      if (cur) cur.push(node); else out.push(node);
    }
    flush();
    return out;
  }

  function snapshot(state, schema) {
    var st = state, ord = null;
    if (st && typeof st === 'object' && st.state && typeof st.state === 'object') {
      ord = st.order; st = st.state;
    }
    if (!st || typeof st !== 'object') return '';
    var kids = tree(st, schema || {}, ord), s = '', i;
    for (i = 0; i < kids.length; i++) s += toHtml(kids[i]);
    if (!s) return '';
    return '<div class="' + SNAP + ' ' + PANEL + '">' + s + '</div>';
  }

  function hydrate(root, schema) {
    var nodes = SBK.dom.all(root, '.sbk-snap--raw'), i, n, r, kids, box, j;
    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      if (n.getAttribute('class').indexOf('sbk-snap--done') >= 0) continue;
      var tx = n.textContent;
      r = SBK.parse(tx);
      if (!r || !r.order.length) {
      if (SBK.parse && typeof SBK.parse.wrap === 'function') {
        var w = SBK.parse(SBK.parse.wrap(tx));
        if (w && w.order.length) r = w;
      }

      }
      if (!r || !r.order.length) { n.setAttribute('class', SNAP + ' sbk-pre sbk-snap--raw sbk-snap--done'); continue; }
      kids = tree(r.state, schema || {}, r.order);
      while (n.firstChild) n.removeChild(n.firstChild);
      box = SBK.dom.h('div', { 'class': PANEL });
      for (j = 0; j < kids.length; j++) box.appendChild(toDom(kids[j]));
      n.appendChild(box);
      n.setAttribute('class', SNAP + ' sbk-snap--raw sbk-snap--done');
    }
    return nodes.length;
  }
  snapshot.hydrate = hydrate;
  snapshot.auto = function (schema) {
    SBK.on('mount', function (p, root) { if (root) hydrate(root, schema); });
    SBK.on('done', function (p, root) { if (root) hydrate(root, schema); });
    return snapshot;
  };

  SBK.ui = SBK.ui || {};
  SBK.ui.snapshot = snapshot;
  SBK.log('hud-render ready');
})(typeof window !== 'undefined' ? window : globalThis);
