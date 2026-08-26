/* SBK ui —— 组件层：浮层/抽屉 panel（悬浮球/抽屉/菜单）。
   舞台面板 stage 已拆到【ui-stage.js】：本文件剥注释后曾达 19628 字符，装成一条正则规则后
   距创卡页编辑器显示上限 20000 只剩数百字符（plan.md 已裁决第 7 条），故在源码侧先拆开。
   本文件同时导出私有工具箱 SBK._uiKit 给 ui-stage.js 复用（见文件末尾说明）。
   依据：资料/基座事实卡.md、包分析-CSS与层级契约.md D.2 / C.0 / E5
   经典脚本 IIFE：§3 内联脚本走 (0,eval)，import 必报错，禁 module；顶层声明会被回挂 window。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui.js loaded before core.js');
    return;
  }
  /* §3/§4.2 预览重跑幂等：sdk.on 无 off/once，创卡页预览会反复重跑整卡脚本。
     哨兵不过就整体短路，绝不重复注册与重复挂载。 */
  if (!SBK.claim('ui')) return;

  var d = W.document;
  var h = SBK.dom.h;

  /* ---------- 自有样式 ----------
     base.css 属 WP-1，不改它 → 组件私有样式由 JS 注入独立 <style>。
     §3 预览重跑：固定 id + 【替换】textContent，绝不 append 新节点，否则堆积一堆 <style>。
     §2 CSP：style-src 无 https: → 零 @import、零外部字体；配色一律 var(--chat-*)（§7.1），
     写死颜色会让平台深浅色切换失效。尺寸走 --rpx（= calc(100vw / 750)，平台尺寸基准）。 */
  var STYLE_ID = 'sbk-ui-css';
  var CSS = [
    /* 浮层外壳挂在 [data-slot=left|right]（root 直接子节点，祖先链无 opacity/transform/overflow 陷阱，
       见 D.2 / E5：两者实为 messages 之后的零高空 div，平台零样式 → 几何必须自己写）。
       position:fixed 让包含块变成视口，不受父级零高影响。
       外壳 pointer-events:none + 子节点 auto：外壳虽然铺满，但不吃掉消息区的点击。 */
    '.sbk-pnl{position:fixed;left:0;top:0;width:0;height:0;pointer-events:none;z-index:var(--sbk-z-panel,3500)}',
    '.sbk-pnl>*{pointer-events:auto}',
    /* 悬浮球：touch-action:none 是 pointer 拖动的前提（否则浏览器先滚页面再给事件） */
    '.sbk-pnl__ball{position:fixed;display:flex;align-items:center;justify-content:center;' +
      'width:var(--sbk-ball,calc(96 * var(--rpx)));height:var(--sbk-ball,calc(96 * var(--rpx)));' +
      'border-radius:50%;background:var(--chat-surface);color:var(--chat-text);' +
      'border:1px solid var(--chat-border);box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));' +
      'font-size:var(--sbk-fs,calc(24 * var(--rpx)));touch-action:none;cursor:pointer;' +
      'user-select:none;-webkit-user-select:none;overflow:hidden}',
    '.sbk-pnl__ball:active{opacity:.8}',
    '.sbk-pnl__ball--drag{opacity:.9}',
    /* 弹出层（菜单/气泡面板）。z 用 --sbk-z-pop(3600) 压在同层浮层之上，仍在 8000 之下 */
    '.sbk-pop{position:fixed;z-index:var(--sbk-z-pop,3600);min-width:calc(200 * var(--rpx));' +
      'max-width:calc(560 * var(--rpx));max-height:70vh;overflow:auto;background:var(--chat-surface);' +
      'color:var(--chat-text);border:1px solid var(--chat-border);border-radius:var(--sbk-radius,calc(12 * var(--rpx)));' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));padding:calc(8 * var(--rpx)) 0}',
    '.sbk-pop--pad{padding:var(--sbk-pad,calc(16 * var(--rpx)))}',
    '.sbk-pop__item{padding:calc(16 * var(--rpx)) var(--sbk-pad,calc(16 * var(--rpx)));cursor:pointer;' +
      'white-space:nowrap;color:var(--chat-text);font-size:var(--sbk-fs,calc(24 * var(--rpx)))}',
    '.sbk-pop__item:active{background:var(--chat-more-item-bg)}',
    '.sbk-pop__item--off{opacity:.45}',
    /* 抽屉：全高固定，transform 位移做进出，不用 left/right 动画（避免重排） */
    '.sbk-drw{position:fixed;top:0;bottom:0;z-index:var(--sbk-z-pop,3600);display:flex;flex-direction:column;' +
      'width:var(--sbk-drw-w,min(calc(560 * var(--rpx)),86%));background:var(--chat-surface);color:var(--chat-text);' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));transition:transform .22s ease;overflow:hidden}',
    '.sbk-drw--l{left:0;border-right:1px solid var(--chat-border);transform:translateX(-101%)}',
    '.sbk-drw--r{right:0;border-left:1px solid var(--chat-border);transform:translateX(101%)}',
    '.sbk-drw--on{transform:translateX(0)}',
    /* 遮罩 z 比抽屉低 1，保证抽屉在上；仍高于 stage-full(3000) */
    '.sbk-mask{position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,.45);' +
      'z-index:calc(var(--sbk-z-pop,3600) - 1)}',
    /* 面板头/体：头不缩、体滚动 */
    '.sbk-pnl__hd{display:flex;align-items:center;gap:var(--sbk-gap,calc(12 * var(--rpx)));flex-shrink:0;' +
      'padding:var(--sbk-pad,calc(16 * var(--rpx)));border-bottom:1px solid var(--chat-border)}',
    '.sbk-pnl__ti{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.sbk-pnl__bd{flex:1 1 auto;min-height:0;overflow:auto;padding:var(--sbk-pad,calc(16 * var(--rpx)))}',
    '.sbk-x{flex-shrink:0;width:calc(56 * var(--rpx));height:calc(56 * var(--rpx));display:flex;' +
      'align-items:center;justify-content:center;border-radius:50%;cursor:pointer;' +
      'background:transparent;border:0;color:var(--chat-text-muted);font-size:calc(32 * var(--rpx));' +
      'line-height:1;padding:0}',
    '.sbk-x:active{background:var(--chat-more-item-bg)}',
    /* 舞台内容容器：铺满平台给的舞台节点。舞台自身几何由平台管（content 走 JS 内联对齐消息区，
       full 是 fixed 四边 0），我们只负责填内容与自备背景（平台不给舞台背景，会透出 root 背景图）。
       ⚠ .sbk-stg 的消费者在 ui-stage.js：CSS 与 injectCss 都留在本文件统一注入，
         这样全局只有一个 <style id="sbk-ui-css">，两个文件不会抢同一个 style id 互相覆盖。 */
    '.sbk-stg{position:absolute;left:0;top:0;right:0;bottom:0;display:flex;flex-direction:column;' +
      'background:var(--chat-bg);color:var(--chat-text);overflow:hidden}',
    /* 功能栏 chrome 入口条（SBK.ui.chrome）。只放入口按钮，【不渲染业务数据】（2.0 §2.1）。
       flex-wrap 而非横向滚动：功能栏是 root 的 flex item，横滚容器在窄屏会吃掉纵向手势。
       按钮本体复用 base.css 的 .sbk-btn（已有 hover/active 两态与 flex-shrink:0），此处不重复定义。 */
    '.sbk-chr{display:flex;flex-wrap:wrap;align-items:center;gap:calc(12 * var(--rpx));' +
      'padding:calc(8 * var(--rpx)) 0}',
    // 触控目标下限 44px（盘点 C.5）。rpx 在窄屏偏小，故用 max() 兜住。字号继承 .sbk-host，不另设
    '.sbk-chr .sbk-btn{min-height:max(44px,calc(72 * var(--rpx)))}'
  ].join('');

  function injectCss() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    // 不用 getElementById：§4.3 它被平台改写过（走 gc 游标），直接遍历子节点最稳
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === STYLE_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = STYLE_ID; head.appendChild(el); }
    if (el.textContent !== CSS) el.textContent = CSS;   // 替换而非追加
    return el;
  }
  /* ---------- 延迟到事件回调 ----------
     🚨 硬约束 17 / §4.1 实测：作者脚本在 DOM 渲染【之前】就执行完毕（顶层
        document.getElementById 取自己刚写入功能栏的节点 → null）。
        故顶层调 panel()/stage() 时 DOM 还不存在，任何挂载都是徒劳。
     🚨 §4.1 实测冷启动顺序 message:new > message:mount > message:done > ready
        —— ready【最后】到且无补发，只有 mount/done 有补发 → 排队只能等 mount/done，绝不能等 ready。
     故本层不要求调用方自己判断时机：顶层调用会被自动排队，首个 mount/done 到达时统一落地。 */
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

  /* ---------- 挂载点 ----------
     🚨 硬约束 12 / D.2：浮层只挂 [data-slot="left"] / [data-slot="right"]。
        两者是 [data-chat="root"] 的直接子节点（C.0），平台零样式，祖先链上无
        opacity / transform / backdrop-filter / overflow 陷阱 → z-index 与几何都干净可控。
     🚨 绝不挂气泡内：[data-chat="message-body"] 的 opacity:.9 会建层叠上下文把 z-index 囚禁（B.3 陷阱一），
        且 §7.3 气泡属虚拟化列表，滚出屏幕即销毁 → 常驻 UI 会凭空消失。
     🚨 也不挂 [data-slot="statusbar"]：C.3 平台是 innerHTML 注入且整体替换节点 → DOM 引用会失效。
        （HUD 走那里是因为它每轮重绘；常驻浮层不行。）
     回落链：目标槽位 → 另一侧槽位 → [data-chat="root"] 本身（flex 列容器）。
     绝不回落 body：root 不是 body 的直接子节点（§9 宿主链），挂 body 会脱离平台布局与主题变量作用域。 */
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
  // §4.3 getElementById 被平台改写过 → 遍历子节点找自己的宿主，供预览重跑复用
  function childById(parent, id) {
    if (!parent) return null;
    var k = parent.childNodes, i;
    for (i = 0; i < k.length; i++) if (k[i] && k[i].nodeType === 1 && k[i].id === id) return k[i];
    return null;
  }

  /* 可视区矩形。
     🚨 不用 window.innerHeight：§7.1 键盘弹出时 innerHeight 不变，而平台把真实可视高写进
        [data-chat="root"] 的内联 --chat-viewport-height（clientHeight - 键盘 inset，随 visualViewport 更新）。
        取 root 的 getBoundingClientRect 等于免费拿到这个值 → 悬浮球不会被键盘盖住。
     §9 实测视口 323x1205（窄屏移动端为主），所以边界约束是必需项而非锦上添花。 */
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

  /* 弹出层翻转避裁：贴哪边就朝内展开。
     先以 visibility:hidden + display:block 量真实尺寸（此时不闪、不吃点击），
     定好位再交给调用方置 visible —— 不测量直接猜宽度在窄屏上必然溢出。 */
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
      // 抽屉/侧挂：优先放锚点外侧，外侧放不下就翻到内侧
      x = aRect.right + gap;
      if (x + pw > v.l + v.w - m) x = aRect.left - gap - pw;
      y = aRect.top + aRect.height / 2 - ph / 2;
    } else {
      // 默认竖向：锚点下方，下方放不下就翻到上方；水平按锚点中心对齐后夹紧
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

  /* 事件冒泡拦截：平台在 composer 上挂 onPointerdown、气泡上有长按菜单（message-menu z=8200）。
     基座控件不拦的话，点一下会顺手触发平台手势 → 菜单乱弹。 */
  function stop(e) { if (e && e.stopPropagation) e.stopPropagation(); }
  function armStop(el) {
    if (!el || !el.addEventListener) return el;
    ['pointerdown', 'click', 'contextmenu'].forEach(function (n) {
      el.addEventListener(n, stop);
    });
    return el;
  }

  /* 标题栏：panel 与 stage 共用。× 挂在 <button>（HTML 壳）上而不是 SVG 图标里 ——
     §5.5 实测 <circle onclick> STRIPPED，SVG 内 on* 一律被删。 */
  function headOf(title, withX, onX) {
    if (!title && !withX) return null;
    var kids = [h('div', { 'class': 'sbk-pnl__ti' }, String(title || ''))];
    if (withX) kids.push(h('button', { 'class': 'sbk-x', onclick: function (e) { stop(e); onX(); } }, '\u00d7'));
    return h('div', { 'class': 'sbk-pnl__hd' }, kids);
  }
  /* ---------- SBK.ui.panel ----------
     浮层 / 抽屉。用途：可拖动悬浮球、侧边抽屉、带菜单的悬浮按钮这类常驻 UI。
     opts = {
       id?:'sbk-panel'      宿主 id（§3 currentScript 恒 null → 定位只能靠固定 id 约定）
       side?:'right'|'left' 挂哪个槽位，也是抽屉出现的边
       mode?:'ball'|'drawer'|'bare'   ball=悬浮球+弹出面板；drawer=悬浮球+侧抽屉；bare=只要壳自己摆
       icon?:string|Node    球内图标。字符串按文本；SVG 节点可用但【点击必须挂 HTML 壳】
       title?:string        面板/抽屉标题（给了才有头部与关闭按钮）
       content?:string|Node|fn(api)   面板体
       menu?:[{label,onSelect?,disabled?}]  给了 menu 就渲染菜单（与 content 二选一，content 优先）
       drag?:true           球是否可拖（默认 true，mode:'bare' 无球则无效）
       pos?:{x,y}           球初始位置（视口坐标，缺省右下偏上）
       width?:string        抽屉宽度，落到 --sbk-drw-w
       mask?:true           抽屉是否带遮罩（默认 true；ball 模式默认 false）
       open?:false          初始是否展开
       remember?:true       是否用 localStorage 记住球位置（§1 localStorage 按卡隔离，实测可用）
       closeOnBack?:true    用户按返回时先收起展开态（订阅内核 'back'），而不是直接离开页面
       onOpen?/onClose?/onDrag?  回调
     }
     返回 api = { el, ball, box, open, close, toggle, opened, setContent, move, destroy } */
  var reg = {};   // 同 id 复用，防重复挂载（预览重跑已被 claim 挡住，这里挡同页多次调用）

  function panel(opts) {
    var o = opts || {};
    var id = String(o.id || 'sbk-panel');
    if (reg[id]) { SBK.warn('ui.panel: id already mounted, returning existing: ' + id); return reg[id]; }

    var side = o.side === 'left' ? 'left' : 'right';
    var mode = o.mode === 'drawer' ? 'drawer' : (o.mode === 'bare' ? 'bare' : 'ball');
    var wantDrag = o.drag !== false && mode !== 'bare';
    var wantMask = o.mask === undefined ? (mode === 'drawer') : !!o.mask;
    var LS = 'sbk-pnl-' + id;                 // localStorage 键（按卡天然隔离，§1）
    var wrap = null, ball = null, box = null, mask = null, opened = !!o.open, built = false, dead = false;
    var pos = o.pos && typeof o.pos.x === 'number' ? { x: o.pos.x, y: o.pos.y } : null;
    var api;

    function savePos() {
      if (o.remember === false || !pos) return;
      // §4.4a save.* 在瘦预览会同步抛 SdkError；localStorage 实测 OK。球位置是纯本地偏好，用 localStorage 足够
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

    // 把球夹回可视区内。§9 实测视口 323x1205，不夹会被拖出屏幕再也点不回来
    function applyPos() {
      if (!ball) return;
      var v = viewRect(), bw = ball.offsetWidth || 40, bh = ball.offsetHeight || 40, m = 4;
      if (!pos) {
        // 缺省落在贴边偏下（避开 header 90rpx 与 composer），side 决定左右
        pos = {
          x: side === 'left' ? v.l + m : v.l + v.w - bw - m,
          y: v.t + v.h * 0.62
        };
      }
      pos.x = clamp(pos.x, v.l + m, Math.max(v.l + m, v.l + v.w - bw - m));
      pos.y = clamp(pos.y, v.t + m, Math.max(v.t + m, v.t + v.h - bh - m));
      ball.style.left = pos.x + 'px';
      ball.style.top = pos.y + 'px';
    }

    /* 拖动走 pointer 事件：一套 API 同时覆盖触摸与鼠标，且有 setPointerCapture 免丢帧。
       moved 阈值区分「拖」与「点」——不区分的话手指微动就吞掉点击。 */
    function arm(el) {
      var sx = 0, sy = 0, ox = 0, oy = 0, moved = false, on = false, pid = null;
      el.addEventListener('pointerdown', function (e) {
        if (!wantDrag) return;
        on = true; moved = false;
        sx = e.clientX; sy = e.clientY;
        ox = pos ? pos.x : 0; oy = pos ? pos.y : 0;
        pid = e.pointerId;
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
        // §5 高频事件合帧（stream 同理）：pointermove 每帧多次，直接写样式会抖
        SBK.schedule(applyPos);
        if (typeof o.onDrag === 'function') { try { o.onDrag(pos); } catch (er) {} }
        stop(e);
      });
      function up(e) {
        if (!on) return;
        on = false;
        try { el.releasePointerCapture(pid); } catch (er) {}
        el.setAttribute('class', 'sbk-pnl__ball');
        if (moved) { applyPos(); savePos(); }
        else api.toggle();     // 没拖动 = 点击
        stop(e);
      }
      el.addEventListener('pointerup', up);
      el.addEventListener('pointercancel', up);
      // 不加 click 监听：pointerup 已经处理，再加会双触发
      el.addEventListener('click', stop);
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
          // dom.h 见 function 型 on* 走 addEventListener，不过净化器 → 无 SAFE_FOR_XML 风险（§5.5）
          k.push(h('div', {
            'class': cls,
            onclick: function (e) {
              stop(e);
              if (it.disabled) return;
              if (typeof it.onSelect === 'function') { try { it.onSelect(api, it); } catch (er) { SBK.warn('menu onSelect threw'); } }
              if (it.keepOpen !== true) api.close();
            }
          }, String(it.label === undefined ? '' : it.label)));
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
      // 顶层调用会被 defer 排到首个 mount/done；若调用方在那之前就 destroy()，
      // 排队里的 build 仍会跑并把已销毁实例复活 → 用 dead 哨兵挡住。
      if (dead || built) return dead ? false : true;
      var slot = slotOf(side);
      if (!slot) { SBK.warn('ui.panel: no mount point yet'); return false; }
      injectCss();
      var found = childById(slot, id);
      if (found) { wrap = found; while (wrap.firstChild) wrap.removeChild(wrap.firstChild); }
      else { wrap = h('div', { id: id, 'class': 'sbk-pnl' }); slot.appendChild(wrap); }
      if (mode !== 'bare') {
        var ic = o.icon;
        ball = h('div', { 'class': 'sbk-pnl__ball' }, ic && ic.nodeType ? ic : String(ic === undefined ? '\u2630' : ic));
        // 🚨 §5.5 实测 <circle onclick> STRIPPED：SVG 内 on* 一律被删 → 图标可以是 SVG，
        //    但监听必须挂在这个 HTML 壳（div）上。别把 handler 挪进 SVG 子节点。
        arm(ball);
        wrap.appendChild(ball);
        pos = pos || loadPos();
        applyPos();
      }
      buildBox();
      wrap.appendChild(box);   // 抽屉/弹层都是 fixed，挂 wrap 下只为跟着 destroy 一起收
      built = true;
      if (opened) { opened = false; api.open(); }
      return true;
    }

    api = {
      el: function () { return wrap; },
      ball: function () { return ball; },
      box: function () { return box; },
      opened: function () { return opened; },
      open: function () {
        if (!built) { defer(function () { opened = true; build(); }); return api; }
        if (opened) return api;
        opened = true;
        if (mode === 'drawer') {
          if (wantMask && !mask) {
            mask = h('div', { 'class': 'sbk-mask', onclick: function (e) { stop(e); api.close(); } });
            wrap.appendChild(mask);
          }
          box.setAttribute('class', DRW + ' sbk-drw--on');
        } else {
          // 翻转避裁：以球为锚点，贴边时朝内展开（place 内部量完真实尺寸再定位）
          var a = ball ? ball.getBoundingClientRect() : { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 };
          place(box, a, { side: o.popSide === 'x' ? 'x' : 'y' });
          box.style.visibility = 'visible';
        }
        if (typeof o.onOpen === 'function') { try { o.onOpen(api); } catch (e) {} }
        return api;
      },
      close: function () {
        if (!built || !opened) { opened = false; return api; }
        opened = false;
        if (mode === 'drawer') {
          box.setAttribute('class', DRW);
          if (mask && mask.parentNode) { mask.parentNode.removeChild(mask); mask = null; }
        } else { box.style.display = 'none'; }
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
        if (was) api.open();
        return api;
      },
      move: function (x, y) { pos = { x: x, y: y }; applyPos(); savePos(); return api; },
      destroy: function () {
        // SBK.off 是内核自有分发的真退订（sdk 侧无 off/once，但内核这层可以）→ 不留悬挂订阅
        SBK.off('mount', onMount);
        SBK.off('back', onBack);
        if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
        wrap = ball = box = mask = null; built = false; opened = false; dead = true;
        delete reg[id];
        return null;
      }
    };

    /* 平台切会话/重渲染可能把槽位内容清掉；mount 时校验一次，掉了就补挂。
       只在【真掉了】时重建，别每次 mount 都重建（会丢用户拖动位置与展开态）。 */
    function onMount() {
      if (!built) return;
      if (wrap && !wrap.parentNode) { built = false; build(); }
    }
    /* 用户按返回（内核 'back'，保留原名不缩写）：展开态先收起，让返回键"逐层退出"，
       符合移动端预期，而不是一次性离开页面。签名 fn(payload, bubbleRoot)，此处不用第 2 参。 */
    function onBack() { if (opened && o.closeOnBack !== false) api.close(); }

    reg[id] = api;
    // 硬约束 17：顶层调用时 DOM 还不存在 → defer 会排到首个 mount/done
    defer(build);
    SBK.on('mount', onMount);
    SBK.on('back', onBack);
    return api;
  }

  /* ---------- SBK.ui.chrome ----------
     功能栏 chrome 层：入口按钮组 + 主题设置抽屉。
     🚨 角色分工（2.0 §2 / 盘点 A.3，1.0 在此处犯的是【方法错误】）：功能栏放 chrome
        （主题设置入口、侧边栏入口、常驻小徽标），业务状态面板在【气泡内】。
        1.0 把状态数据面板塞进功能栏槽位 → 实机截图里页面同时出现两个一模一样的面板。
        故本层【绝不渲染任何业务数据】，只出按钮。
     §5.6 功能栏是静态的（h_() 只在装载时跑一次，且其正则输入是 statusbar 字段自身）→
        入口只需渲染一次，不必跟随消息刷新；真要动的内容靠 JS 改 DOM。
     §2.2 已裁定「JS 往功能栏 appendChild 留不住」是旧 MMD 行为被误带过来的，
        事实卡 §5.6 正确（无重渲染路径），实机验证整页重载后 JS 插入的节点仍在
        → 设置面板可以挂功能栏，不必占用舞台。

     签名：chrome(opts) —— 与 core.js boot() 的【实际调用点】对齐（它调 SBK.ui.chrome({hostId:…})）。
     同时容错 chrome(hostEl, opts) 形态（设计稿写法）：首参是元素就当宿主用。
     opts = {
       hostId?:'sbk-hud'   功能栏宿主 id（与 core 的 pinned 宿主 hostId+'-pin' 是兄弟节点，互不擦除）
       settings?:false     是否出「设置」入口（默认出）
       label?:'设置'       该入口文案
       title?:'阅读设置'   抽屉标题
       width?:string       抽屉宽度
       entries?:[{label,onSelect,accent?}]  作者自定义入口（侧边栏/档案/音效开关等）
       preset?:string      首次启动的默认风格包名
     }
     返回 api = { el, toggle, panel } —— 开合转发到 SBK.theme.prefs（抽屉归主题层所有） */
  var chromeApi = null;      // 模块级单例：重复调用直接返回，不重复挂载、不重复订阅

  function chrome(a, b) {
    var pre = a && a.nodeType === 1 ? a : null;      // 首参是元素 → 当宿主；否则当 opts
    var o = (pre ? b : a) || {};
    if (chromeApi) { SBK.warn('ui.chrome: already mounted, returning existing'); return chromeApi; }

    var hid = String(o.hostId || 'sbk-hud');
    var gid = hid + '-chr';                          // 自己的子容器 id，只清它、不动兄弟节点
    var grp = null, built = false;

    /* 设置抽屉【不在本层实现】：它的载体是 panel({mode:'drawer'})，而内容与开合语义属主题层，
       故整块归 theme.js 的 prefs.panel/toggle（它在调用时才取 SBK.ui.panel，规避装载顺序）。
       本层只负责「功能栏上有个按钮，点了调它」——这正是 chrome 的职责边界（2.0 §2.1）。
       缺主题层时告警并留下按钮（点了只告警），不抛异常炸整卡。 */
    function prefs() {
      var t = SBK.theme;
      if (t && t.prefs && typeof t.prefs.toggle === 'function') return t.prefs;
      SBK.warn('ui.chrome: theme prefs layer not loaded, settings entry is inert');
      return null;
    }

    function build() {
      if (built) return true;
      // 硬约束 17：宿主只能在事件回调内取（作者脚本早于 DOM 执行）→ 本函数只被 defer 调用
      var host = pre || SBK.dom.mountHost(hid);
      if (!host) { SBK.warn('ui.chrome: no mount point yet'); return false; }
      injectCss();
      /* 幂等：宿主里已有自己的条就复用并清空重建，不 append 第二条。
         🚨 只清 #<gid> 自己的子节点，【绝不】清整个宿主 —— core 的 pinned 精简条是
            同一个功能栏槽位里的兄弟节点，清宿主会把它一起擦掉（core.js 已就此留注释）。 */
      grp = childById(host, gid);
      if (grp) { while (grp.firstChild) grp.removeChild(grp.firstChild); }
      else { grp = h('div', { id: gid, 'class': 'sbk-chr' }); host.appendChild(grp); }

      /* 偏好读档 + 合成 + 落地，在【首个入口按钮出现之前】就做完 ——
         玩家上次存的字号/配色必须开局即生效，而不是等他打开一次面板才应用。
         store.load 自带 try/catch（§4.4a 瘦预览下 save.get 同步抛 SdkError）。 */
      var t = SBK.theme;
      // 整个 o 直接传下去：theme.start 只读它的 title/width，多余键它不看
      if (t && typeof t.start === 'function') {
        try { t.start(o.preset, o); } catch (e) { SBK.warn('ui.chrome: theme.start threw', e && e.message); }
      }

      var list = [];
      if (o.settings !== false) list.push({ label: o.label || '\u8bbe\u7f6e', onSelect: function () { var p = prefs(); if (p) p.toggle(); } });
      if (o.entries && o.entries.length) list = list.concat(o.entries);
      // forEach 天然一项一个闭包，不必再套 IIFE（本文件 armStop 已是同一写法）
      list.forEach(function (it) {
        // §5.5 交互必须挂 HTML 壳：SVG 内 on* 一律被删（实测 <circle onclick> STRIPPED）
        grp.appendChild(h('button', {
          'class': 'sbk-btn' + (it.accent ? ' sbk-btn--accent' : ''),
          onclick: function (ev) {
            stop(ev);
            if (typeof it.onSelect === 'function') { try { it.onSelect(chromeApi); } catch (er) { SBK.warn('chrome entry threw'); } }
          }
        }, String(it.label === undefined ? '' : it.label)));
      });
      armStop(grp);                 // 拦 pointerdown/click/contextmenu，避免顺手触发平台长按菜单
      built = true;
      return true;
    }

    // 开合一律转给主题层，chrome 自己不持有抽屉引用（单一归属，避免两处状态不同步）
    chromeApi = {
      el: function () { return grp; },
      panel: function () { var p = prefs(); return p ? p.panel() : null; },
      toggle: function () { var p = prefs(); if (p) p.toggle(); return chromeApi; }
    };

    // 硬约束 17：顶层调用时 DOM 还不存在 → defer 排到首个 mount/done（ready 最后到且无补发）
    defer(build);
    /* 平台切会话可能把功能栏槽位内容清掉 → mount 时校验，掉了才补挂。
       单例保证这里只订阅一次（重复 chrome() 已在函数入口返回）。 */
    SBK.on('mount', function () {
      if (built && grp && !grp.parentNode) { built = false; build(); }
    });
    return chromeApi;
  }

  /* ---------- 私有工具箱：给 ui-stage.js 复用 ----------
     下划线前缀 = 内部约定，不属对外 API，上层业务不要依赖。
     为什么共享而不是两边各留一份：
       1) 🚨 defer 的队列内部用 SBK.on('mount'|'done') 排空 —— 各留一份就有两个排空订阅者，
          同一批排队任务会被排空两次；共享则全局只有一对 mount/done 订阅。
       2) 🚨 injectCss 共享 → 全局只有一个 <style id="sbk-ui-css"> 节点，
          天然不存在「两份 CSS 抢同一个 style id 互相覆盖」的问题（CSS 里已含 .sbk-stg）。
       3) 体积：CSS + 工具约占本层一半，复制一份两个文件都会重新逼近编辑器上限。
     代价是 ui-stage.js 依赖本文件先装载 —— 装载顺序已由 build_sbk.py 的 UI_ASSETS 固定
     （protocol.js → hud.js → ui.js → ui-stage.js），且 ui-stage.js 取不到工具箱时会告警并短路。 */
  /* 只导出 ui-stage.js 【真正用到】的 5 个：injectCss / childById / defer / armStop / headOf。
     stop 不导出 —— 它已被 armStop 闭包捕获，stage 侧无直接调用点（要加交互再按需补）。 */
  SBK._uiKit = {
    injectCss: injectCss,
    childById: childById,
    defer: defer,
    armStop: armStop,
    headOf: headOf
  };

  /* 🚨 合并挂载，不能覆盖：WP-2 的 hud.js 已经往同一个 SBK.ui 上挂了 hud 与 snapshot。
     写成 SBK.ui = { panel:.. } 会把它们整个踩掉（装载顺序 core → protocol → hud → ui → ui-stage）。
     stage 已拆到 ui-stage.js，由那边自己往 SBK.ui 上追加。 */
  SBK.ui = SBK.ui || {};
  SBK.ui.panel = panel;
  SBK.ui.chrome = chrome;      // core.js boot() 在 modes.chrome 为真（默认真）时调它
  SBK.log('ui ready (panel, chrome)');
})(typeof window !== 'undefined' ? window : globalThis);
