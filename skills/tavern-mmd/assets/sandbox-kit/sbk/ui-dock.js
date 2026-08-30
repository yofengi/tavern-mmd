/* SBK dock：侧边图标导轨 + 两种呈现面（半页抽屉 / 锚定气泡）+ 可选导航栏。
   ------------------------------------------------------------------
   取代 chrome 的 inline 方形按钮（那是「镶嵌在页面里」观感的根因：它走功能栏行内流，
   与平台自己的 chrome 挤在一条上，且功能栏实测 flex-shrink:1 会被消息区抢高度压扁）。

   三条形态纪律（都是「按需出现」，不是恒定层级）：
   1. 层 1 只是一枚【图标】页签，不带文字 —— 文字页签在真机上占宽、且与平台 chrome 抢注意力。
   2. 【单功能不做第二层】：一个页签只有一件事就点开即到；扇形（fan）只在同一页签下
      挂着 ≥2 种【不同类型】功能时才出现，用来快速分流。
   3. 【单 pane 不做导航栏】：呈现面里只有一组内容就直接铺开；导航栏只在 ≥2 pane 时渲染。

   两种呈现面的语义分工（作者没指定时的默认选型依据）：
   · drawer（半页抽屉）＝【基础设置】：美化相关（风格包、字号、配色）。信息量大、要滚动。
   · bubble（锚定气泡）＝【扩展功能】：地图、人物图鉴、自动注入。轻量、看一眼就走，
     不该为它盖掉半个屏幕。
   两种面都支持可选导航栏，所以「集中式」（一个入口 + 导航栏切换）与「分散式」
   （多个图标页签各管一件事）都能表达，由作者或 AI 按功能数量与轻重选择。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-dock.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-dock')) return;

  var kit = SBK._uiKit;
  if (!kit) { SBK.warn('ui-dock: SBK._uiKit missing (ui.js not loaded?)'); return; }

  var d = W.document, h = SBK.dom.h;
  var injectCss = kit.injectCss, childById = kit.childById, defer = kit.defer;
  var armStop = kit.armStop, slotOf = kit.slotOf, stop = kit.stop, clamp = kit.clamp;
  var viewRect = kit.viewRect;

  /* 图标集已拆到 ui-icon.js（本模块内联时剥注释达 18330 + 19 字符包装，
     超过不可调高的 18000 单条门禁，必须真实拆码）。这里只做取用与缺失兜底。 */
  function iconNode(name) {
    if (SBK.ui && typeof SBK.ui.icon === 'function') return SBK.ui.icon(name);
    /* ui-icon.js 缺失时不留空页签：退化成一个字符标记，入口仍可点 */
    SBK.warn('ui.dock: ui-icon.js missing, falling back to a text glyph');
    return h('span', { 'class': 'sbk-ico' }, '\u2699');
  }
  function iconNames() {
    return (SBK.ui && typeof SBK.ui.icons === 'function') ? SBK.ui.icons() : [];
  }

  var DOCK_ID = 'sbk-dock-css';
  /* 几何一律 px，不用 rpx —— 三条理由：
     ① dock 是贴视口边缘的 chrome，不在气泡内容流里，没有「跟 750 稿缩放」的需求；
     ② --rpx 实测恒 0.5px（桌面封顶 375/750，手机 100vw/750），按 750 稿写的系数会腰斩：
        46rpx 只有 23px，低于 44px 可点区，页签会细成一条竖线（实测复现过）；
     ③ --sbk-radius 等节奏令牌是【风格包可改】的（素雅阅读把它压到 8rpx），
        作者调气泡面板圆角不该顺带把外壳也改形。 */
  var DOCK_CSS = [
    /* 导轨：零尺寸定位锚，多个页签在里面竖向堆叠 */
    '.sbk-dk{position:fixed;top:44%;z-index:var(--sbk-z-panel,3500);pointer-events:none;' +
      'display:flex;flex-direction:column;gap:6px;font-size:13px;line-height:1.15}',
    '.sbk-dk--r{right:0;align-items:flex-end}',
    '.sbk-dk--l{left:0;align-items:flex-start}',
    '.sbk-dk *{box-sizing:border-box}',
    /* 页签：默认半透明并推出屏外一截，只露一小条；hover/激活时滑回来。
       36×40 是「够点但不抢眼」的折中：宽度压到 36 让它像屏幕边缘的把手，
       高度 40 配 44px 的 min-height 兜底保证可点。 */
    '.sbk-dk__tab{position:relative;display:flex;align-items:center;justify-content:center;' +
      'width:36px;height:40px;min-height:40px;padding:0;' +
      'border:1px solid var(--chat-border);background:var(--chat-surface);' +
      'color:var(--chat-text-muted);opacity:.6;' +
      'box-shadow:var(--sbk-shadow,0 2px 12px rgba(0,0,0,.35));pointer-events:auto;cursor:pointer;' +
      'appearance:none;-webkit-appearance:none;font-family:inherit;' +
      '-webkit-tap-highlight-color:transparent;' +
      'transition:transform .2s ease,opacity .18s ease,color .18s ease,border-color .18s ease}',
    '.sbk-dk--r .sbk-dk__tab{border-right:0;border-radius:11px 0 0 11px;transform:translateX(5px)}',
    '.sbk-dk--l .sbk-dk__tab{border-left:0;border-radius:0 11px 11px 0;transform:translateX(-5px)}',
    '.sbk-dk__tab:hover{opacity:1;color:var(--chat-text);transform:translateX(0)}',
    /* 激活态（对应面开着）：贴回 + 强调色，明示「这个是开着的那一个」 */
    '.sbk-dk__tab--on{opacity:1;color:var(--chat-accent);border-color:var(--chat-accent);' +
      'transform:translateX(0)}',
    /* 图标基线尺寸由 ui-icon.js 的 .sbk-ico 给，这里只在导轨语境下微调 */
    '.sbk-dk__tab:focus-visible{outline:2px solid var(--chat-accent);outline-offset:2px}',
    /* 扇形选项（.sbk-dk__opt）的样式与坐标都在 ui-fan.js —— 它是可选的第二层，
       且本模块已触到 18000 单条门禁，必须真实拆码。 */
    /* 窄屏：上移避开底部输入区与手势区；页签再收一点但不低于 34px */
    '@media (max-width:560px),(pointer:coarse) and (max-width:760px){' +
      '.sbk-dk{top:33%;gap:5px}' +
      '.sbk-dk__tab{width:34px;height:38px;min-height:38px;opacity:.55}' +
      '.sbk-dk__tab .sbk-ico{width:18px;height:18px}}',
    '@media (orientation:landscape) and (max-height:520px){.sbk-dk{top:36%}}',
    '@media (prefers-reduced-motion:reduce){.sbk-dk__tab{transition:none}}'
  ].join('');

  function dockCss() {
    var head = d.head || d.documentElement, kids = head.childNodes, el = null, i;
    for (i = 0; i < kids.length; i++) {
      if (kids[i] && kids[i].nodeType === 1 && kids[i].id === DOCK_ID) { el = kids[i]; break; }
    }
    if (!el) { el = d.createElement('style'); el.id = DOCK_ID; head.appendChild(el); }
    if (el.textContent !== DOCK_CSS) el.textContent = DOCK_CSS;
    return el;
  }

  /* 扇形几何与选项样式已拆到 ui-fan.js（本模块加了页签增删与呈现面销毁后回到
     18346 含包装，超过不可调高的 18000 单条门禁）。这里只做取用与缺失兜底。 */
  function fanPlace(nodes, tabRect, side) {
    if (SBK.ui && SBK.ui.fan && typeof SBK.ui.fan.place === 'function') {
      return SBK.ui.fan.place(nodes, tabRect, side);
    }
    /* ui-fan.js 缺失时不让扇形叠在一点上：退化成贴页签左侧的等距竖列。
       没有样式表，选项会是裸按钮，但仍可点、仍能分流。 */
    SBK.warn('ui.dock: ui-fan.js missing, falling back to a plain vertical column');
    var n = nodes.length, cy = tabRect.top + tabRect.height / 2;
    for (var i = 0; i < n; i++) {
      var el = nodes[i];
      el.style.position = 'fixed';
      el.style.left = Math.max(6, tabRect.left - 130) + 'px';
      el.style.top = (cy + (i - (n - 1) / 2) * 48 - 22) + 'px';
    }
  }

  var dockApi = null;
  function dock(a, b) {
    var pre = a && a.nodeType === 1 ? a : null;
    var o = (pre ? b : a) || {};
    /* 🚨 导轨是【一条共享导轨】，但重复调用必须【合并页签】而不是丢弃调用方的配置。
       原先这里直接 return 已有实例 → boot() 先建好带设置页签的导轨后，作者自己调
       dock({tabs:[图鉴, 地图]}) 会拿回那个实例、自己的页签被静默丢掉，
       「气泡侧边栏可以有多枚」根本做不出来。现在改成把新页签并进去。 */
    if (dockApi) {
      var add = (o.tabs && o.tabs.length) ? o.tabs
        : ((o.icon || o.panes || o.entries || o.onSelect) ? [o] : []);
      for (var ai = 0; ai < add.length; ai++) dockApi.addTab(add[ai]);
      return dockApi;
    }

    var side = o.side === 'left' ? 'left' : 'right';
    var id = String(o.id || 'sbk-dock');
    var wrap = null, built = false;
    var specs = [], tabs = [];
    /* 页签表的【唯一真源】。addTab/removeTab/setTabs 都只动这一个数组，不再回头读 o。
       ⚠ 只有 o 里真的带了「定义一枚页签」的字段时才播种，否则播空：
       dock({id,side,hoverOpen}) 这种「只开导轨、页签稍后 addTab」的用法很常见
       （chrome() 正是这么调的），播个默认齿轮页签会让设置页签变成第二枚。 */
    var seed = (o.icon || o.panes || o.entries || o.onSelect || o.surface) ? [{
      icon: o.icon || 'gear', label: o.label || '\u8bbe\u7f6e', role: o.role,
      surface: o.surface, panes: o.panes, entries: o.entries, onSelect: o.onSelect,
      active: o.active, width: o.width
    }] : [];
    /* 播种也过 dedupe（见下方 dedupe 注释）：构造参数里塞两枚 settings 同样要被拦住。
       ⚠ dedupe 是函数声明，提升到作用域顶部，所以这里先调用是安全的。 */
    var rawTabs = dedupe((o.tabs && o.tabs.length) ? o.tabs.slice() : seed);

    /* 归一化页签表。兼容旧签名 dock({label, entries}) —— chrome() 与既有卡在用。 */
    function normTabs(raw) {
      return raw.filter(function (t) { return t; }).map(function (t) {
        var panes = (t.panes || []).filter(function (p) { return p; });
        var entries = (t.entries || []).filter(function (e) { return e; });
        var surf = t.surface === 'bubble' ? 'bubble' : (t.surface === 'drawer' ? 'drawer' : null);
        /* 🚨 单功能不做第二层：entries 只剩 1 项时降级成直达那一项，不铺扇形。
           扇形的唯一价值是「≥2 种功能之间快速分流」，一项时它纯属多一次点击。 */
        if (entries.length === 1 && !panes.length) {
          var only = entries[0];
          return { icon: t.icon, label: t.label || only.label, kind: 'action', role: t.role,
                   onSelect: only.onSelect, active: only.active || t.active, raw: t };
        }
        if (entries.length > 1) {
          return { icon: t.icon, label: t.label, kind: 'fan', entries: entries,
                   role: t.role, active: t.active, raw: t };
        }
        if (panes.length) {
          return { icon: t.icon, label: t.label, kind: surf || 'drawer', panes: panes,
                   role: t.role, width: t.width, active: t.active, raw: t };
        }
        return { icon: t.icon, label: t.label, kind: 'action', role: t.role,
                 onSelect: t.onSelect, active: t.active, raw: t };
      });
    }

    /* ---- 页签增删。导轨是【共享的】：设置唯一，其余可多枚 ----
       🚨 数量规则（用户口径）：
       · `role:'settings'` 的页签**全局唯一** —— 第二次加会被拒并告警。
         理由：玩家找「设置」时不该在两枚长得差不多的图标里猜。
       · 抽屉页签、气泡页签**都可以有多枚**。图鉴、地图这类扩展通常各占一枚独立按钮，
         而不是硬塞进同一个气泡的导航栏里 —— 收进一个气泡只是「功能多到导轨放不下」
         时的可选手段，不是默认做法。
       · 因此 dock 虽是模块级单例（一条导轨），但页签表可增删：chrome() 往里加设置页签，
         作者往里加自己的页签，互不覆盖。这修掉了「作者调 dock() 拿回 chrome 的实例、
         自己的 tabs 被静默丢弃」那个冲突。 */
    function hasRole(r) {
      for (var i = 0; i < rawTabs.length; i++) if (rawTabs[i] && rawTabs[i].role === r) return i;
      return -1;
    }
    /* 🚨 唯一性校验必须在【写 rawTabs 的所有入口】上执行，不能只在 addTab 里。
       曾经的漏洞：校验只写在 addTab()，而 rawTabs 还有三条写入路径绕过它 ——
       ① 构造时 o.tabs.slice() 直接播种；② setTabs(list) 整表替换；③ entries(list) 重写。
       于是 dock({tabs:[{role:'settings'},{role:'settings'}]}) 能造出两枚设置页签，
       玩家要在两枚差不多的图标里猜哪个是设置。
       归一策略：保留第一枚 settings，后续的丢弃并告警 —— 不让导轨进入非法状态，
       也不因为一个坏配置就整轨不建。 */
    function dedupe(list) {
      var out = [], seen = false, i, t;
      for (i = 0; i < (list || []).length; i++) {
        t = list[i];
        if (!t) continue;
        if (t.role === 'settings') {
          if (seen) {
            SBK.warn('ui.dock: a settings tab already exists, dropping the extra one ' +
                     '(settings is unique by design; use role-less tabs for extensions)');
            continue;
          }
          seen = true;
        }
        out.push(t);
      }
      return out;
    }
    function addTab(spec) {
      if (!spec) return null;
      if (spec.role === 'settings' && hasRole('settings') >= 0) {
        SBK.warn('ui.dock: a settings tab already exists, ignoring the extra one ' +
                 '(settings is unique by design; use role-less tabs for extensions)');
        return null;
      }
      rawTabs.push(spec);
      if (built) { built = false; build(); }
      return dockApi;
    }
    function removeTab(sel) {
      var i = typeof sel === 'number' ? sel : hasRole(String(sel));
      if (i < 0 || i >= rawTabs.length) return dockApi;
      var st = tabs[i];
      if (st && st.sf && typeof st.sf.destroy === 'function') { try { st.sf.destroy(); } catch (e) {} }
      rawTabs.splice(i, 1);
      if (built) { built = false; build(); }
      return dockApi;
    }

    /* 每个页签一份呈现面句柄，懒建。
       🚨 懒建是硬要求，不是优化：装载期就建面会把主题偏好读取（进而可能是
       sdk.save.get，瘦预览下【同步抛错】）牵进整卡启动路径。 */
    function surfaceOf(st) {
      if (st.sf) return st.sf;
      /* 内容懒求值：nav() 在面第一次打开时才跑，pane 的 content 也逐个懒建。
         ui-nav.js 缺失时退化成「只铺第一个 pane」，不让整卡失效。 */
      var content = function () {
        var mk = SBK.ui && SBK.ui.nav;
        if (typeof mk !== 'function') {
          SBK.warn('ui.dock: ui-nav.js missing, rendering the first pane only');
          var c = st.panes[0] && st.panes[0].content;
          if (typeof c === 'function') { try { c = c(); } catch (e) { c = null; } }
          return c && c.nodeType ? c : h('div', { 'class': 'sbk-pane' });
        }
        st.nav = mk(st.panes, {});
        return st.nav.el();
      };
      if (st.kind === 'bubble') {
        if (!SBK.ui || typeof SBK.ui.bubble !== 'function') {
          SBK.warn('ui.dock: surface=bubble needs ui-bubble.js, falling back to drawer');
          st.kind = 'drawer';
        } else {
          st.sf = SBK.ui.bubble({
            id: id + '-bb-' + st.i, side: side, title: st.label,
            anchor: function () { return st.btn; }, content: content, width: st.width,
            onClose: function () { mark(); }
          });
          return st.sf;
        }
      }
      var mk = SBK.ui && SBK.ui.panel;
      if (typeof mk !== 'function') { SBK.warn('ui.dock: SBK.ui.panel missing'); return null; }
      st.sf = mk({
        id: id + '-dw-' + st.i, side: side, mode: 'drawer', drag: false,
        title: st.label, width: st.width, content: content,
        onClose: function () { mark(); }
      });
      var ball = st.sf.ball && st.sf.ball();
      if (ball) ball.style.display = 'none';   /* 入口是导轨页签，不要额外悬浮球 */
      return st.sf;
    }

    function anyOpen() {
      for (var i = 0; i < tabs.length; i++) {
        var st = tabs[i];
        if (st.fanOn) return st;
        if (st.sf && typeof st.sf.opened === 'function' && st.sf.opened()) return st;
      }
      return null;
    }
    /* 页签激活态刷新。active() 是作者给的只读谓词 —— 绝不在这里构建呈现面。 */
    function mark() {
      for (var i = 0; i < tabs.length; i++) {
        var st = tabs[i], on = false;
        if (st.fanOn) on = true;
        else if (st.sf && typeof st.sf.opened === 'function') on = st.sf.opened();
        else if (typeof st.active === 'function') { try { on = !!st.active(); } catch (e) { on = false; } }
        if (st.btn) st.btn.setAttribute('class', 'sbk-dk__tab' + (on ? ' sbk-dk__tab--on' : ''));
      }
    }

    function closeFan(st) {
      if (!st || !st.fanOn) return;
      st.fanOn = false;
      for (var i = 0; i < st.opts.length; i++) st.opts[i].setAttribute('class', 'sbk-dk__opt');
      mark();
    }
    function closeAll(except) {
      for (var i = 0; i < tabs.length; i++) {
        var st = tabs[i];
        if (st === except) continue;
        closeFan(st);
        if (st.sf && typeof st.sf.close === 'function' && st.sf.opened && st.sf.opened()) st.sf.close();
      }
    }
    function openFan(st) {
      closeAll(st);
      if (!st.opts) buildFan(st);
      st.fanOn = true;
      fanPlace(st.opts, st.btn.getBoundingClientRect(), side);
      for (var i = 0; i < st.opts.length; i++) st.opts[i].setAttribute('class', 'sbk-dk__opt sbk-dk__opt--on');
      mark();
    }
    function buildFan(st) {
      st.opts = st.entries.map(function (it) {
        var el = h('button', { type: 'button', 'class': 'sbk-dk__opt' },
          String(it.label === undefined ? '' : it.label));
        el.addEventListener('click', function (e) {
          stop(e);
          if (typeof it.onSelect === 'function') {
            try { it.onSelect(dockApi, it); } catch (er) { SBK.warn('dock entry threw'); }
          }
          if (it.keepOpen !== true) closeFan(st);
          mark();
        });
        return el;
      });
      /* 扇形挂 wrap（导轨内），wrap 自身 pointer-events:none，选项各自 auto */
      for (var i = 0; i < st.opts.length; i++) wrap.appendChild(st.opts[i]);
    }

    function hit(st) {
      if (st.kind === 'fan') { st.fanOn ? closeFan(st) : openFan(st); return; }
      if (st.kind === 'action') {
        closeAll(null);
        if (typeof st.onSelect === 'function') {
          try { st.onSelect(dockApi, st.raw); } catch (e) { SBK.warn('dock tab onSelect threw'); }
        }
        mark();
        return;
      }
      /* drawer / bubble：点开即到（单 pane 时面里连导航栏都没有） */
      var sf = surfaceOf(st);
      if (!sf) return;
      var was = typeof sf.opened === 'function' && sf.opened();
      if (was) { sf.close(); mark(); return; }
      closeAll(st);
      sf.open();
      mark();
    }

    /* 导轨垂直居中。页签可以有多枚（图鉴、地图各占一枚），条数一多固定 top:44%
       会把导轨顶到顶栏或压到输入区上去 → 按实测高度重算 top 并夹在安全区内。
       🚨 只能改 top，【不能用 transform:translateY(-50%)】：那会让 .sbk-dk 成为
       包含块，挂在它里面的扇形选项是 position:fixed，坐标会从「视口」变成「相对导轨」，
       fanPlace 算好的绝对坐标全部错位。 */
    function centre() {
      if (!wrap) return;
      var v = viewRect(), hgt = 0;
      try { hgt = wrap.getBoundingClientRect().height; } catch (e) {}
      if (!hgt) return;
      var top = v.t + (v.h - hgt) / 2;
      /* 上留一点给顶栏，下留一点给输入区，取两者较严的那个 */
      var lo = v.t + 48, hi = v.t + v.h - hgt - 96;
      wrap.style.top = clamp(top, lo, Math.max(lo, hi)) + 'px';
    }

    function build() {
      if (built) return true;
      var slot = pre || slotOf(side);
      if (!slot) { SBK.warn('ui.dock: no mount point yet'); return false; }
      injectCss();
      dockCss();
      /* 🚨 重建前必须先销毁旧呈现面，不能只清 wrap 的子节点。
         曾经的漏洞：抽屉/气泡挂在【slot】上而不是 wrap 里（fixed 定位需要脱离导轨），
         所以 `while (wrap.firstChild) remove` 清不掉它们。后果是 addTab/setTabs/entries
         触发重建后：旧气泡仍然开着并留在文档里，而它的触发按钮已经被重建成新按钮 ——
         玩家再也关不掉那个气泡。旧面还可能仍持有 document keydown 与 window resize 监听。
         removeTab/destroy 各自销毁过，唯独这条重建路径漏了。 */
      for (var oi = 0; oi < tabs.length; oi++) {
        var ot = tabs[oi];
        if (!ot) continue;
        if (ot.sf && typeof ot.sf.destroy === 'function') { try { ot.sf.destroy(); } catch (e) {} }
        ot.sf = null; ot.nav = null;
        /* 扇形选项也挂在 wrap 外（fanPlace 用 fixed 坐标），同样要显式摘掉 */
        if (ot.opts) {
          for (var oj = 0; oj < ot.opts.length; oj++) {
            var op = ot.opts[oj];
            if (op && op.parentNode) op.parentNode.removeChild(op);
          }
          ot.opts = null;
        }
        ot.fanOn = false;
      }
      specs = normTabs(rawTabs);
      wrap = childById(slot, id);
      if (wrap) { while (wrap.firstChild) wrap.removeChild(wrap.firstChild); }
      else { wrap = h('div', { id: id }); slot.appendChild(wrap); }
      wrap.setAttribute('class', 'sbk-dk sbk-dk--' + (side === 'left' ? 'l' : 'r'));
      tabs = specs.map(function (sp, i) {
        var st = {
          i: i, icon: sp.icon, label: sp.label, kind: sp.kind, panes: sp.panes,
          entries: sp.entries, onSelect: sp.onSelect, active: sp.active, role: sp.role,
          width: sp.width, raw: sp.raw, sf: null, opts: null, fanOn: false, nav: null
        };
        st.btn = h('button', {
          type: 'button', 'class': 'sbk-dk__tab', title: sp.label || ''
        }, [iconNode(sp.icon)]);
        st.btn.addEventListener('click', function (e) { stop(e); hit(st); });
        /* 桌面预览里 hover 预展开扇形；触屏无 hover 不受影响。只对 fan 生效 —— 
           hover 就把抽屉推开会很突兀。 */
        if (o.hoverOpen !== false) {
          st.btn.addEventListener('mouseenter', function () {
            if (st.kind !== 'fan' || st.fanOn) return;
            if (W.matchMedia && W.matchMedia('(hover:hover)').matches) openFan(st);
          });
        }
        wrap.appendChild(st.btn);
        return st;
      });
      armStop(wrap);
      mark();
      centre();
      built = true;
      return true;
    }

    /* 点 dock 之外收起。捕获阶段挂 document（沙盒收窄的是 querySelector，不是事件）。
       ⚠ 抽屉/气泡是 dock 的下游，点它们内部不能收 —— 故排除这几个 class。 */
    function onDoc(e) {
      var t = e && e.target;
      try {
        if (t && wrap && wrap.contains(t)) return;
        while (t && t !== d.body) {
          if (t.classList && (t.classList.contains('sbk-drw') || t.classList.contains('sbk-pop') ||
                              t.classList.contains('sbk-bb'))) return;
          t = t.parentNode;
        }
      } catch (er) {}
      for (var i = 0; i < tabs.length; i++) closeFan(tabs[i]);
    }
    function onMount() { if (built && wrap && !wrap.parentNode) { built = false; build(); } }
    function onBack() { for (var i = 0; i < tabs.length; i++) closeFan(tabs[i]); }
    function reflow() {
      centre();
      for (var i = 0; i < tabs.length; i++) {
        if (tabs[i].fanOn) fanPlace(tabs[i].opts, tabs[i].btn.getBoundingClientRect(), side);
      }
    }

    dockApi = {
      el: function () { return wrap; },
      tabs: function () { return tabs.slice(); },
      tabAt: function (i) { return tabs[i] || null; },
      icons: iconNames,
      opened: function () { return !!anyOpen(); },
      sync: function () { mark(); return dockApi; },
      open: function (i) { var st = tabs[i || 0]; if (st) hit(st); return dockApi; },
      close: function () { closeAll(null); mark(); return dockApi; },
      /* 运行期改页签表：整轨重建（页签数变化会改扇形原点与导轨高度） */
      entries: function (list) {
        if (!list) return specs.slice();
        rawTabs = dedupe([{ icon: o.icon || 'gear', label: o.label || '\u8bbe\u7f6e',
                            role: o.role, entries: list }]);
        if (built) { built = false; build(); }
        return dockApi;
      },
      /* 整表替换也过 dedupe：否则 setTabs 是绕过 settings 唯一性的第三条路 */
      setTabs: function (list) {
        if (!list) return specs.slice();
        rawTabs = dedupe(list.slice());
        if (built) { built = false; build(); }
        return dockApi;
      },
      /* 往共享导轨增删页签。设置页签唯一，其余可多枚（见 addTab 注释） */
      addTab: addTab,
      removeTab: removeTab,
      hasRole: function (r) { return hasRole(String(r)) >= 0; },
      count: function () { return rawTabs.length; },
      destroy: function () {
        SBK.off('mount', onMount);
        SBK.off('back', onBack);
        try { d.removeEventListener('click', onDoc, true); } catch (e) {}
        try { W.removeEventListener('resize', reflow); } catch (e) {}
        for (var i = 0; i < tabs.length; i++) {
          if (tabs[i].sf && typeof tabs[i].sf.destroy === 'function') tabs[i].sf.destroy();
        }
        if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
        wrap = null; tabs = []; specs = []; built = false; dockApi = null;
        return null;
      }
    };
    defer(build);
    SBK.on('mount', onMount);
    SBK.on('back', onBack);
    try { d.addEventListener('click', onDoc, true); } catch (e) {}
    try { W.addEventListener('resize', reflow); } catch (e) {}
    return dockApi;
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.dock = dock;
  /* 不再从这里导出 SBK.ui.icon / .icons —— 它们的归属已移到 ui-icon.js。
     ⚠ 这里若照旧赋值，会在 ui-icon 之后装载时把真实现覆盖成本模块的兜底壳。 */
  SBK.log('ui-dock ready (dock, icon)');
})(typeof window !== 'undefined' ? window : globalThis);
