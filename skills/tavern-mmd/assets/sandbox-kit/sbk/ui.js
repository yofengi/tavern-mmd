(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui')) return;

  var d = W.document;
  var h = SBK.dom.h;
  var STYLE_ID = 'sbk-ui-css';
  var CSS = [
    '.sbk-pnl{position:fixed;left:0;top:0;width:0;height:0;pointer-events:none;z-index:var(--sbk-z-panel,3500)}',
    '.sbk-pnl>*{pointer-events:auto}',
    '.sbk-pnl__ball{position:fixed;display:flex;align-items:center;justify-content:center;' +
      'width:var(--sbk-ball,calc(96 * var(--rpx)));height:var(--sbk-ball,calc(96 * var(--rpx)));' +
      'border-radius:50%;background:var(--chat-surface);color:var(--chat-text);' +
      'border:1px solid var(--chat-border);box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));' +
      'font-size:var(--sbk-fs,calc(24 * var(--rpx)));touch-action:none;cursor:pointer;' +
      'user-select:none;-webkit-user-select:none;overflow:hidden;' +
      'appearance:none;-webkit-appearance:none;font-family:inherit;line-height:1;padding:0;margin:0}',
    '.sbk-pnl__ball:active{opacity:.8}',
    '.sbk-pnl__ball--drag{opacity:.9}',
    '.sbk-pnl__ball:focus-visible,.sbk-pop__item:focus-visible,.sbk-x:focus-visible{' +
      'outline:2px solid var(--chat-accent);outline-offset:2px}',
    '.sbk-pop{position:fixed;z-index:var(--sbk-z-pop,3600);min-width:calc(200 * var(--rpx));' +
      'max-width:calc(560 * var(--rpx));max-height:70vh;overflow:auto;background:var(--chat-surface);' +
      'color:var(--chat-text);border:1px solid var(--chat-border);border-radius:var(--sbk-radius,calc(12 * var(--rpx)));' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));padding:calc(8 * var(--rpx)) 0}',
    '.sbk-pop--pad{padding:var(--sbk-pad,calc(16 * var(--rpx)))}',
    '.sbk-pop__item{display:block;width:100%;box-sizing:border-box;text-align:left;' +
      'padding:calc(16 * var(--rpx)) var(--sbk-pad,calc(16 * var(--rpx)));cursor:pointer;' +
      'white-space:nowrap;color:var(--chat-text);font-size:var(--sbk-fs,calc(24 * var(--rpx)));' +
      'background:transparent;border:0;font-family:inherit;line-height:1.5;' +
      'min-height:max(44px,calc(72 * var(--rpx)))}',
    '.sbk-pop__item:active{background:var(--chat-more-item-bg)}',
    '.sbk-pop__item--off{opacity:.45}',
    '.sbk-pop__item[disabled]{cursor:default}',
    '.sbk-drw{position:fixed;top:0;bottom:0;z-index:var(--sbk-z-pop,3600);display:flex;flex-direction:column;' +
      'width:var(--sbk-drw-w,min(calc(560 * var(--rpx)),86%));background:var(--chat-surface);color:var(--chat-text);' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));transition:transform .22s ease;overflow:hidden;' +
      'height:100%;height:100vh;height:100dvh}',
    '.sbk-drw--l{left:0;border-right:1px solid var(--chat-border);transform:translateX(-101%);' +
      'padding-left:env(safe-area-inset-left,0px)}',
    '.sbk-drw--r{right:0;border-left:1px solid var(--chat-border);transform:translateX(101%);' +
      'padding-right:env(safe-area-inset-right,0px)}',
    '.sbk-drw--on{transform:translateX(0)}',
    '.sbk-drw>.sbk-pnl__hd{padding-top:calc(var(--sbk-pad,calc(16 * var(--rpx))) + env(safe-area-inset-top,0px))}',
    '.sbk-drw>.sbk-pnl__bd{padding-bottom:calc(var(--sbk-pad,calc(16 * var(--rpx))) + env(safe-area-inset-bottom,0px))}',
    '@media (orientation:landscape) and (max-height:520px){' +
      '.sbk-drw{width:var(--sbk-drw-w,min(calc(560 * var(--rpx)),60%))}' +
      '.sbk-pnl__hd{padding:calc(8 * var(--rpx)) var(--sbk-pad,calc(16 * var(--rpx)))}' +
      '.sbk-pop{max-height:88vh}}',
    '@media (prefers-reduced-motion:reduce){.sbk-drw{transition:none}}',
    '.sbk-mask{position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,.45);' +
      'z-index:calc(var(--sbk-z-pop,3600) - 1)}',
    '.sbk-pnl__hd{display:flex;align-items:center;gap:var(--sbk-gap,calc(12 * var(--rpx)));flex-shrink:0;' +
      'padding:var(--sbk-pad,calc(16 * var(--rpx)));border-bottom:1px solid var(--chat-border)}',
    '.sbk-pnl__ti{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.sbk-pnl__bd{flex:1 1 auto;min-height:0;overflow:auto;padding:var(--sbk-pad,calc(16 * var(--rpx)))}',
    '.sbk-x{flex-shrink:0;width:calc(56 * var(--rpx));height:calc(56 * var(--rpx));display:flex;' +
      'align-items:center;justify-content:center;border-radius:50%;cursor:pointer;' +
      'background:transparent;border:0;color:var(--chat-text-muted);font-size:calc(32 * var(--rpx));' +
      'line-height:1;padding:0}',
    '.sbk-x:active{background:var(--chat-more-item-bg)}',
    '.sbk-stg{position:absolute;left:0;top:0;right:0;bottom:0;display:flex;flex-direction:column;' +
      'background:var(--chat-bg);color:var(--chat-text);overflow:hidden}',
    '.sbk-chr{display:flex;flex-wrap:wrap;align-items:center;gap:calc(12 * var(--rpx));' +
      'padding:calc(8 * var(--rpx)) 0}',
    '.sbk-chr .sbk-btn{min-height:max(44px,calc(72 * var(--rpx)))}'
  ].join('');

  function injectCss() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === STYLE_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = STYLE_ID; head.appendChild(el); }
    if (el.textContent !== CSS) el.textContent = CSS;
    return el;
  }

  var queue = [], hooked = false;
  function domReady() {
    try { return !!d.querySelector('[data-chat="root"]'); } catch (e) { return false; }
  }
  function drain() {
    if (!domReady()) return;
    var list = queue; queue = [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](); } catch (e) { SBK.warn('ui: deferred task threw', e && e.message); }
    }
  }
  function defer(fn) {
    if (domReady()) { try { fn(); } catch (e) { SBK.warn('ui: task threw', e && e.message); } return; }
    queue.push(fn);
    if (!hooked) {
      hooked = true;
      SBK.warn('ui: called before DOM exists (hard constraint 17), deferring to first mount/done');
      SBK.on('mount', drain);
      SBK.on('done', drain);
    }
  }

  function slotOf(side) {
    var want = side === 'left' ? 'left' : 'right', el = null;
    try { el = d.querySelector('[data-slot="' + want + '"]'); } catch (e) {}
    if (el) return el;
    try { el = d.querySelector('[data-slot="' + (want === 'left' ? 'right' : 'left') + '"]'); } catch (e) {}
    if (el) { SBK.warn('ui: slot ' + want + ' missing, using the other side'); return el; }
    try { el = d.querySelector('[data-chat="root"]'); } catch (e) {}
    if (el) SBK.warn('ui: no left/right slot, falling back to [data-chat="root"]');
    return el;
  }
  function childById(parent, id) {
    if (!parent) return null;
    var k = parent.childNodes, i;
    for (i = 0; i < k.length; i++) if (k[i] && k[i].nodeType === 1 && k[i].id === id) return k[i];
    return null;
  }
  function viewRect() {
    var r = null, root = null;
    try { root = d.querySelector('[data-chat="root"]'); } catch (e) {}
    if (root && root.getBoundingClientRect) {
      r = root.getBoundingClientRect();
      if (r && r.width > 0 && r.height > 0) return { l: r.left, t: r.top, w: r.width, h: r.height };
    }
    return { l: 0, t: 0, w: W.innerWidth || 320, h: W.innerHeight || 480 };
  }
  function clamp(v, lo, hi) { return hi < lo ? lo : (v < lo ? lo : (v > hi ? hi : v)); }
  function place(pop, aRect, opt) {
    var o = opt || {}, gap = o.gap === undefined ? 8 : o.gap, v = viewRect(), m = 6;
    pop.style.visibility = 'hidden';
    pop.style.display = 'block';
    pop.style.left = '0px'; pop.style.top = '0px';
    pop.style.maxHeight = (v.h - m * 2) + 'px';
    var pw = pop.offsetWidth, ph = pop.offsetHeight;
    var loX = v.l + m, hiX = v.l + v.w - m - pw, loY = v.t + m, hiY = v.t + v.h - m - ph;
    var x, y;
    if (o.side === 'x') {
      x = aRect.right + gap;
      if (x + pw > v.l + v.w - m) x = aRect.left - gap - pw;
      y = aRect.top + aRect.height / 2 - ph / 2;
    } else {
      y = aRect.bottom + gap;
      if (y + ph > v.t + v.h - m) {
        var up = aRect.top - gap - ph;
        if (up >= loY || (aRect.top - v.t) > (v.t + v.h - aRect.bottom)) y = up;
      }
      x = aRect.left + aRect.width / 2 - pw / 2;
    }
    pop.style.left = clamp(x, loX, Math.max(loX, hiX)) + 'px';
    pop.style.top = clamp(y, loY, Math.max(loY, hiY)) + 'px';
    return pop;
  }
  function stop(e) { if (e && e.stopPropagation) e.stopPropagation(); }
  function armStop(el) {
    if (!el || !el.addEventListener) return el;
    ['pointerdown', 'click', 'contextmenu'].forEach(function (n) { el.addEventListener(n, stop); });
    return el;
  }
  function headOf(title, withX, onX) {
    if (!title && !withX) return null;
    var kids = [h('div', { 'class': 'sbk-pnl__ti' }, String(title || ''))];
    if (withX) kids.push(h('button', { type: 'button', 'class': 'sbk-x', onclick: function (e) { stop(e); onX(); } }, '\u00d7'));
    return h('div', { 'class': 'sbk-pnl__hd' }, kids);
  }

  SBK._uiKit = {
    injectCss: injectCss,
    childById: childById,
    defer: defer,
    armStop: armStop,
    headOf: headOf,
    slotOf: slotOf,
    viewRect: viewRect,
    clamp: clamp,
    place: place,
    stop: stop
  };
  SBK.log('ui ready (kit)');
})(typeof window !== 'undefined' ? window : globalThis);
