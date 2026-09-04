/* SBK theme panel. Loads after theme.js and extends its public prefs API. */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) { (W.console && W.console.warn) && W.console.warn('[SBK] theme-panel.js loaded before core.js'); return; }
  if (!SBK.claim('theme-panel')) return;

  var d = W.document;
  var prefs = SBK.theme && SBK.theme.prefs;
  var kit = SBK._themeKit;
  if (!prefs || !kit || typeof kit.configure !== 'function' || typeof kit.onChange !== 'function') {
    SBK.warn('theme-panel.js needs theme.js');
    return;
  }

  var SET_ID = 'sbk-set-css';
  var SET_CSS = [
    '.sbk-set{display:flex;flex-direction:column;gap:calc(12 * var(--rpx,1.333px))}',
    '.sbk-set__row{display:flex;align-items:center;justify-content:space-between;' +
      'gap:calc(12 * var(--rpx,1.333px));min-height:max(44px,calc(88 * var(--rpx,1.333px)))}',
    '.sbk-set__label{flex:1 1 auto;min-width:0;color:var(--chat-text-muted,#c5c5c5);' +
      'font-size:var(--sbk-fs-sm,calc(20 * var(--rpx,1.333px)))}',
    '.sbk-set__ctl{flex:0 0 auto;display:flex;align-items:center;gap:calc(8 * var(--rpx,1.333px))}',
    '.sbk-set__ctl input,.sbk-set__ctl select{color-scheme:inherit;' +
      'background:var(--chat-input-bg,#1e1f24);color:var(--chat-input-text,#fff);' +
      'border:1px solid var(--chat-border,#333);border-radius:calc(8 * var(--rpx,1.333px));' +
      'font:inherit;padding:calc(6 * var(--rpx,1.333px)) calc(8 * var(--rpx,1.333px))}',
    '.sbk-set__ctl input[type="number"]{width:calc(120 * var(--rpx,1.333px));text-align:right}',
    '.sbk-set__ctl input[type="color"]{width:calc(72 * var(--rpx,1.333px));' +
      'height:calc(56 * var(--rpx,1.333px));padding:calc(3 * var(--rpx,1.333px))}',
    '.sbk-set__ctl input[type="range"]{width:calc(150 * var(--rpx,1.333px));padding:0;border:0;background:transparent}',
    '.sbk-set__ctl input[type="checkbox"]{width:calc(44 * var(--rpx,1.333px));height:calc(44 * var(--rpx,1.333px));' +
      'accent-color:var(--chat-accent,#ff6d97);padding:0}',
    '.sbk-set__ctl select{max-width:calc(300 * var(--rpx,1.333px))}',
    '.sbk-set__out{min-width:calc(64 * var(--rpx,1.333px));text-align:right;' +
      'font-variant-numeric:tabular-nums;color:var(--chat-text,#fff)}',
    '.sbk-set__grp--off{opacity:.55}',
    '.sbk-set__grp--off .sbk-set__ctl{pointer-events:none}',
    '.sbk-set__act{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:calc(12 * var(--rpx,1.333px));' +
      'padding-top:calc(8 * var(--rpx,1.333px));border-top:1px solid var(--chat-border,#333)}'
  ].join('');

  function setCss() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === SET_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = SET_ID; head.appendChild(el); }
    if (el.textContent !== SET_CSS) el.textContent = SET_CSS;
    return el;
  }

  var H = SBK.dom.h;
  var HEX = /^#[0-9a-fA-F]{6}$/;
  function row(label, ctl) {
    return H('div', { 'class': 'sbk-set__row' }, [
      H('div', { 'class': 'sbk-set__label' }, label),
      H('div', { 'class': 'sbk-set__ctl' }, ctl)
    ]);
  }

  function fieldRow(f, ctls) {
    var el, out = null;
    if (f.kind === 'color') el = H('input', { type: 'color' });
    else if (f.unit === '%') {
      el = H('input', { type: 'range', min: f.min, max: f.max, step: f.step });
      out = H('span', { 'class': 'sbk-set__out' });
    } else {
      el = H('input', { type: 'number', min: f.min, max: f.max, step: f.step });
      el.setAttribute('inputmode', f.kind === 'int' ? 'numeric' : 'decimal');
    }
    function readout() { if (out) out.textContent = el.value + '%'; }
    function fill() {
      var v = prefs.get(f.key);
      if (f.kind === 'color') el.value = HEX.test(String(v || '')) ? v : '#000000';
      else el.value = String(v === undefined || v === null ? f.def : v);
      readout();
    }
    function commit() {
      var v = f.kind === 'color' ? String(el.value) : parseFloat(el.value);
      if (!prefs.set(f.key, v)) fill();
      else readout();
    }
    el.addEventListener('change', commit);
    if (out) el.addEventListener('input', readout);
    ctls.push({ el: el, fill: fill });
    return row(f.label, out ? [el, out] : el);
  }

  /* 🚨 表单可以【同时存在多份】：dock 形态下 chrome() 把 prefs.form() 直接嵌进导轨
     抽屉的 pane，而作者仍可能另外调 prefs.panel() 拿独立抽屉。原先这里是单槽
     （syncForm = refresh），第二份表单一建就把第一份的刷新函数覆盖掉 ——
     玩家在导轨里改字号，另一份表单的控件停在旧值，下次打开显示的是过期状态。
     改成登记表 + 每次广播时剔掉已脱离文档的那几份（避免泄漏）。 */
  var syncForms = [];
  function syncAll() {
    for (var i = syncForms.length - 1; i >= 0; i--) {
      var rec = syncForms[i];
      /* 已从文档摘掉的表单不再刷新也不再持有 */
      if (rec.box && rec.box.isConnected === false) { syncForms.splice(i, 1); continue; }
      try { rec.refresh(); } catch (e) {}
    }
  }
  function form() {
    setCss();
    var box = H('div', { 'class': 'sbk-set' }), ctls = [], list, fields, i, sel_ = null, grp, r1, r2;
    list = prefs.presets();
    if (list.length) {
      sel_ = H('select', { onchange: function () { prefs.preset(sel_.value); refresh(); } },
        [H('option', { value: '' }, '\u9ed8\u8ba4')]);
      for (i = 0; i < list.length; i++) sel_.appendChild(H('option', { value: list[i] }, list[i]));
      box.appendChild(row('\u98ce\u683c\u5305', sel_));
    }

    var cb = H('input', { type: 'checkbox', onchange: function () { prefs.enabled(cb.checked); refresh(); } });
    box.appendChild(row('\u542f\u7528\u7f8e\u5316\uff08\u5173\u95ed\uff1d\u8ddf\u968f\u5e73\u53f0\uff09', cb));

    grp = H('div', { 'class': 'sbk-set__grp' });
    fields = prefs.fields();
    for (i = 0; i < fields.length; i++) grp.appendChild(fieldRow(fields[i], ctls));
    box.appendChild(grp);

    r1 = H('button', { 'class': 'sbk-btn', onclick: function () { prefs.reset(); refresh(); } }, '\u6062\u590d\u5f53\u524d\u4e3b\u9898\u9ed8\u8ba4');
    r2 = H('button', { 'class': 'sbk-btn', onclick: function () { prefs.resetAll(); refresh(); } }, '\u5168\u90e8\u6062\u590d\u9ed8\u8ba4');
    box.appendChild(H('div', { 'class': 'sbk-set__act' }, [r1, r2]));

    function refresh() {
      var j;
      cb.checked = prefs.enabled();
      if (sel_) sel_.value = prefs.preset();
      for (j = 0; j < ctls.length; j++) {
        ctls[j].fill();
        ctls[j].el.disabled = !prefs.enabled();
      }
      grp.setAttribute('class', 'sbk-set__grp' + (prefs.enabled() ? '' : ' sbk-set__grp--off'));
      r1.disabled = !prefs.enabled();
    }
    refresh();
    syncForms.push({ box: box, refresh: refresh });
    return box;
  }

  /* The UI factory is deliberately read only when this method is called. */
  var setNode = null;
  function setPanel() {
    if (setNode) return setNode;
    var mk = SBK.ui && SBK.ui.panel;
    if (typeof mk !== 'function') { SBK.warn('theme.prefs.panel needs the ui layer (SBK.ui.panel)'); return null; }
    var cfg = kit.configure();
    setNode = mk({
      id: 'sbk-set', side: 'right', mode: 'drawer', drag: false,
      title: cfg.title, width: cfg.width || undefined,
      content: function () { return form(); }
    });
    var b = setNode.ball();
    if (b) b.style.display = 'none';
    return setNode;
  }

  kit.onChange(syncAll);
  prefs.form = form;
  prefs.panel = setPanel;
  /* dock 形态的设置页签用这个：只要一个【可嵌进任意 pane 的节点】，不要独立抽屉外壳。
     与 prefs.panel() 的区别是它不建 SBK.ui.panel、不建悬浮球 —— 外壳由 dock 提供。 */
  prefs.pane = form;
  prefs.toggle = function () { var p = setPanel(); if (p) p.toggle(); return p; };
  prefs.open = function () { var p = setPanel(); if (p) p.open(); return p; };
  prefs.close = function () { if (setNode) setNode.close(); return setNode; };
  SBK.log('theme-panel ready');
})(typeof window !== 'undefined' ? window : globalThis);
