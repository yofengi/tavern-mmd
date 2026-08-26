/* SBK ui-stage —— 组件层：舞台面板 stage。
   由 ui.js 拆出：ui.js 剥注释后 19628 字符，装成一条正则规则后距创卡页编辑器显示上限
   20000 仅余数百字符（plan.md 已裁决第 7 条：超限就拆条；这里在【源码侧】先拆开）。
   依据：资料/基座事实卡.md、包分析-CSS与层级契约.md D.2 / C.0 / E5
   经典脚本 IIFE：§3 内联脚本走 (0,eval)，import 必报错，禁 module；顶层声明会被回挂 window。
   🚨 装载顺序 protocol.js → hud.js → ui.js → ui-stage.js（build_sbk.py 的 UI_ASSETS）：
      本文件复用 ui.js 导出的私有工具箱 SBK._uiKit，顺序错了就拿不到。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-stage.js loaded before core.js');
    return;
  }
  /* §3/§4.2 预览重跑幂等：sdk.on 无 off/once，创卡页预览会反复重跑整卡脚本。
     哨兵不过就整体短路，绝不重复注册与重复挂载。
     🚨 哨兵名必须与 ui.js 的 'ui' 【不同】：两个文件同用 'ui' 的话，第二个会被第一个的
        哨兵直接拦掉、整个文件一行都不执行 → SBK.ui.stage 永远不存在。 */
  if (!SBK.claim('ui-stage')) return;

  /* ---------- 共享工具箱 ----------
     injectCss / childById / defer / armStop / headOf 由 ui.js 定义并挂在 SBK._uiKit。
     🚨 defer 的排队队列必须【共用】：它内部用 SBK.on('mount'|'done') 排空，
        两个文件各留一份就会有两个排空订阅者 → 同一批任务被排空两次。
     🚨 injectCss 共用 → 全局只有一个 <style id="sbk-ui-css">，
        天然不存在「两份 CSS 抢同一个 style id 互相覆盖」的问题（CSS 里已含 .sbk-stg）。 */
  var kit = SBK._uiKit;
  if (!kit) {
    SBK.warn('ui-stage: SBK._uiKit missing (ui.js not loaded?) — stage unavailable');
    return;
  }
  var h = SBK.dom.h;
  var injectCss = kit.injectCss, childById = kit.childById;
  var defer = kit.defer, armStop = kit.armStop, headOf = kit.headOf;
  /* 注意：本文件不需要 document / window 引用 —— 舞台容器由 sdk.stage.el() 给出，
     DOM 查询与样式注入都在 ui.js 的工具箱里完成。 */

  /* ---------- SBK.ui.stage ----------
     舞台面板。用途：地图、背包、小游戏这类需要长期存在且占大面积的 UI。
     走 sdk.stage.open('content'|'full') / close() / el() / visible()。
     content 盖消息区（顶栏与输入框仍可用）；full 盖整屏（盖不住授权/充值等系统弹窗）。
     舞台在虚拟化列表之外，【不随消息滚动】（平台 content 模式用 JS 内联几何对齐消息容器）。
     opts = {
       mode?:'content'|'full'   默认 content
       title?:string            给了才有头部
       render?:fn(box, api)     只在【首次】构建时调用一次（舞台关掉再开内容还在 → 支持复用）
       content?:string|Node     render 的简写
       closeButton?:false       默认给关闭按钮
       onOpen?:fn(api)
       onClose?:fn(api, byPlatform)   byPlatform=true 表示平台侧关闭（用户按返回等）
     }
     返回 api = { open, close, toggle, visible, el, box, mode, rebuild, destroy } */
  var S = SBK.sdk || {};

  /* 🚨 §4.4 / 硬约束：sdk.stage.close() 【不派发】stage:close —— 那条只在平台侧关闭时发
        （用户按返回等）。故我方 close() 之后必须【主动同步内部状态】，不能等事件回来。
     stage:close 的桥接归内核（core.js 的 EVT 表已含 'stage:close'，保留原名不缩写），
     这里只用 SBK.on 订阅，签名与其它事件一致 fn(payload, bubbleRoot)；
     stage:close 场景 bubbleRoot 恒为 null —— 内核只对 mount/done/stream 合成气泡根。
     ⚠ 别在这里再用 SBK.sdk.on('stage:close') 自建桥：内核已派发一次，自建会【双份派发】。
     §4.2 sdk.on 无 off/once，但 SBK.on/off 是内核自有分发，可安全按实例订阅与退订。 */

  function stage(opts) {
    var o = opts || {};
    var mode = o.mode === 'full' ? 'full' : 'content';
    var BOX_ID = String(o.id || 'sbk-stage-box');
    var box = null, built = false, open_ = false, dead = false;
    var st = S.stage || null;
    var api;

    if (!st || typeof st.open !== 'function') SBK.warn('ui.stage: sdk.stage unavailable');

    /* 🚨 硬约束 19 / §4.4b：判断开关【只能用 sdk.stage.visible()】。
          实测 stage.visible()===false 时 stage.el() 【仍返回 <DIV>】（手册说返回 null 是错的）
          → 任何 `if (stage.el())` 都会把关闭状态误判成已打开。这里绝不据 el() 判断。 */
    function isVisible() {
      if (st && typeof st.visible === 'function') {
        try { return !!st.visible(); } catch (e) {}
      }
      return open_;   // SDK 不可用时退回自记状态
    }

    /* 舞台关掉再开内容还在（官方明说）→ 复用而非每次 open 都清空重建。
       built 哨兵保证 render 只跑一次；要重建走 api.rebuild()。 */
    function build() {
      if (dead) return false;   // 同 panel：destroy 后排队里的 build 不得复活实例
      if (!st || typeof st.el !== 'function') return false;
      var host = null;
      try { host = st.el(); } catch (e) { host = null; }
      // ⚠ 这里的 el() 只用来【拿容器节点】，不用来判断开关（§4.4b）
      if (!host || !host.appendChild) { SBK.warn('ui.stage: stage element not available'); return false; }
      injectCss();
      var found = childById(host, BOX_ID);
      if (found && found === box && built) return true;      // 已建好，复用
      if (found && found !== box) { box = found; built = false; }  // 上一生命周期留下的，接管并重渲染
      if (!box) { box = h('div', { id: BOX_ID, 'class': 'sbk-stg' }); }
      if (box.parentNode !== host) host.appendChild(box);
      if (built) return true;
      while (box.firstChild) box.removeChild(box.firstChild);
      var hd = headOf(o.title, o.closeButton !== false, function () { api.close(); });
      if (hd) box.appendChild(hd);
      var bd = h('div', { 'class': 'sbk-pnl__bd' });
      box.appendChild(bd);
      armStop(box);
      if (typeof o.render === 'function') {
        try { o.render(bd, api); } catch (e) { SBK.warn('ui.stage: render threw', e && e.message); }
      } else if (o.content !== undefined && o.content !== null) {
        if (o.content.nodeType) bd.appendChild(o.content);
        else bd.appendChild(h('div', { 'class': 'sbk-pre' }, String(o.content)));
      }
      built = true;
      return true;
    }

    api = {
      visible: isVisible,
      el: function () { try { return st && st.el ? st.el() : null; } catch (e) { return null; } },
      box: function () { return box; },
      mode: function () { return mode; },
      open: function (m) {
        if (m === 'full' || m === 'content') mode = m;
        // 硬约束 17：DOM 未就绪时 stage.el() 拿不到可用容器 → 排队到首个 mount/done
        defer(function () {
          if (!st || typeof st.open !== 'function') return;
          try { st.open(mode); } catch (e) { SBK.warn('ui.stage: open failed', e && e.message); return; }
          open_ = true;
          build();          // open 之后再建：此时平台已把舞台切出 display:none
          if (typeof o.onOpen === 'function') { try { o.onOpen(api); } catch (e) {} }
        });
        return api;
      },
      close: function () {
        if (st && typeof st.close === 'function') {
          try { st.close(); } catch (e) { SBK.warn('ui.stage: close failed', e && e.message); }
        }
        /* 🚨 sdk.stage.close() 不派发 stage:close → 这里必须自己同步状态并回调，
              否则内部 open_ 会永远停在 true，下次 toggle 就反了。
              byPlatform=false 区分「我们关的」与「平台关的」。 */
        open_ = false;
        if (typeof o.onClose === 'function') { try { o.onClose(api, false); } catch (e) {} }
        return api;
      },
      // 用 visible() 而非内部标志：平台可能在我们背后关掉（且 close 无事件），visible() 才是真值
      toggle: function (m) { return isVisible() ? api.close() : api.open(m); },
      rebuild: function () { built = false; defer(build); return api; },
      render: function () { defer(build); return api; },
      destroy: function () {
        SBK.off('stage:close', onPlatformClose);
        if (box && box.parentNode) box.parentNode.removeChild(box);
        box = null; built = false; open_ = false; dead = true;
        return null;
      }
    };

    /* 平台侧关闭（用户按返回等）。内核已桥接 stage:close 并按实例分发，
       故这里按实例订阅即可，不需要模块级自建桥（那会双份派发）。
       签名 fn(payload, bubbleRoot)：stage:close 的 bubbleRoot 恒为 null，此处不用它。 */
    function onPlatformClose(payload) {
      open_ = false;
      if (typeof o.onClose === 'function') { try { o.onClose(api, true); } catch (e) {} }
    }
    SBK.on('stage:close', onPlatformClose);

    // 开局对齐一次真实状态：预览重跑或热切会话时舞台可能已经是开着的
    defer(function () { if (isVisible()) { open_ = true; build(); } });
    return api;
  }

  /* 🚨 合并挂载，不能覆盖：hud.js 已挂 SBK.ui.hud / SBK.ui.snapshot，ui.js 已挂 SBK.ui.panel。
     写成 SBK.ui = { stage:.. } 会把它们整个踩掉（装载顺序 core → protocol → hud → ui → ui-stage）。 */
  SBK.ui = SBK.ui || {};
  SBK.ui.stage = stage;
  SBK.log('ui-stage ready (stage)');
})(typeof window !== 'undefined' ? window : globalThis);
