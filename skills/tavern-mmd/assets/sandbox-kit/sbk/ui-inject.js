/* SBK inject：自动注入。开关 + 输入框，启用时把输入框内容追加到玩家发送的消息末尾。
   ------------------------------------------------------------------
   典型放置：气泡侧边栏里的一枚独立页签（扩展功能），也可以作抽屉的一个 pane。

   🚨🚨 本模块是整个基座里**唯一没有官方支撑点**的功能，风险必须写在最显眼处。

   平台的 12 个事件里【没有 before-send 钩子】（`ready` / `message:new|done|stream|mount|unmount`
   / `input:change` / `conversation:switch` / `theme:change` / `back` / `stage:close` / `dispose`）。
   `message:new` 到达时消息已经在发送管线里了，改不动草稿。所以「发送前追加」只能靠
   **拦发送手势**：在发送按钮的 click 与输入框的 Enter 上挂【捕获阶段】监听，
   先用 `sdk.input.set()` 把草稿改成「原文 + 注入」，再让事件继续冒泡给平台自己的处理器。

   这条路有一个**我无法在本地证伪的时序假设**：平台的发送处理器读的是 Vue 响应式
   状态（那么 `input.set` 同帧生效、注入成功），还是直接读 DOM 的 `textarea.value`
   （那么当帧还是旧值，注入会丢，且下一条消息会带上这次的注入 —— 错位一轮）。
   已知的相邻事实是 `input.set()` 之后同帧 `setCursor` 必然失效，因为 DOM 上
   `textarea.value` 当帧还是旧值（事实卡 §4.2）—— 这说明 DOM 侧确实滞后一帧，
   但**并不能推出**平台发送时读的是哪一侧。

   → **必须在真机上验一次**：开 `?sdkDebug=1`，启用注入后发一条，看发出去的气泡
     里有没有注入内容。若发现注入丢失或错位一轮，唯一可靠的退路是**不拦手势**，
     改成把注入内容做成一个「按钮：把注入词填进输入框」让玩家自己按发送
     （`sdk.input.add()`），牺牲自动性换确定性。`setAuto(false)` 就是这个退路的开关。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] ui-inject.js loaded before core.js');
    return;
  }
  if (!SBK.claim('ui-inject')) return;

  var kit = SBK._uiKit;
  if (!kit) { SBK.warn('ui-inject: SBK._uiKit missing (ui.js not loaded?)'); return; }

  var d = W.document, h = SBK.dom.h, stop = kit.stop;
  var CSS_ID = 'sbk-inj-css';
  var STORE_KEY = '_sbkInject';
  var CSS = [
    '.sbk-inj{display:flex;flex-direction:column;gap:10px;min-width:0}',
    '.sbk-inj__row{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:40px}',
    '.sbk-inj__lbl{color:var(--chat-text);font-size:var(--sbk-cfs-sm,13px);font-weight:600}',
    '.sbk-inj__note{margin:0;color:var(--chat-text-muted);font-size:var(--sbk-cfs-xs,12px);line-height:1.5}',
    /* 滑块开关：用 checkbox 撑语义与键盘可达，视觉靠兄弟 span 画。
       平台删 aria-*，所以状态可辨性靠「颜色 + 滑块位置」两重线索，不靠 aria。 */
    '.sbk-inj__sw{position:relative;flex-shrink:0;width:46px;height:26px;display:inline-block}',
    '.sbk-inj__sw input{position:absolute;left:0;top:0;width:100%;height:100%;margin:0;' +
      'opacity:0;cursor:pointer;z-index:2}',
    '.sbk-inj__sw span{position:absolute;left:0;top:0;right:0;bottom:0;border-radius:999px;' +
      'background:var(--chat-border);transition:background .18s ease;pointer-events:none}',
    '.sbk-inj__sw span::after{content:"";position:absolute;left:3px;top:3px;width:20px;height:20px;' +
      'border-radius:50%;background:var(--chat-surface);box-shadow:0 1px 3px rgba(0,0,0,.4);' +
      'transition:transform .18s ease}',
    '.sbk-inj__sw input:checked + span{background:var(--chat-accent)}',
    '.sbk-inj__sw input:checked + span::after{transform:translateX(20px)}',
    '.sbk-inj__sw input:focus-visible + span{outline:2px solid var(--chat-accent);outline-offset:2px}',
    '.sbk-inj__ta{width:100%;box-sizing:border-box;min-height:88px;resize:vertical;' +
      'padding:8px 10px;border:1px solid var(--chat-border);border-radius:10px;' +
      'background:var(--chat-input-bg);color:var(--chat-input-text);' +
      'font-family:inherit;font-size:var(--sbk-cfs-sm,13px);line-height:1.5}',
    '.sbk-inj__ta::placeholder{color:var(--chat-input-placeholder)}',
    '.sbk-inj__ta:focus{outline:none;border-color:var(--chat-input-border)}',
    '.sbk-inj--off .sbk-inj__ta{opacity:.55}',
    '.sbk-inj__foot{display:flex;align-items:center;justify-content:space-between;gap:8px}',
    '.sbk-inj__cnt{color:var(--chat-text-muted);font-size:var(--sbk-cfs-xs,12px);' +
      'font-variant-numeric:tabular-nums}'
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

  var injApi = null;
  function inject(opts) {
    var o = opts || {};
    if (injApi) { SBK.warn('ui.inject: already created, returning existing'); return injApi; }

    var maxLen = typeof o.maxLength === 'number' && o.maxLength > 0 ? o.maxLength : 500;
    var auto = o.auto !== false;          /* 拦手势自动注入；false = 只存不发（见文件头退路） */
    var sep = typeof o.separator === 'string' ? o.separator : '\n';
    /* 🚨 长度归一必须是【唯一入口】，所有写 text 的路径都过它。
       曾经的缺陷：只有 textarea 的 oninput 做了截断，于是两条路绕过 maxLength ——
       ① 构造参数 o.text 直接赋值不截断；② 程序性改 ta.value 后 fire('change')，
       onchange 里 `text = ta.value` 也不截断（真实场景：作者用按钮写入超长内容）。
       症状是 payload() 吐出超过 maxLength 的串，而平台输入框的总长上限在权威文档里
       【没有确证】，所以不能指望平台帮你兜住。 */
    function clamp(v) {
      var s = v === undefined || v === null ? '' : String(v);
      return s.length > maxLen ? s.slice(0, maxLen) : s;
    }
    var on = !!o.enabled, text = clamp(o.text);
    var loaded = false, hooked = false, busy = false;
    var cb = null, ta = null, box = null, cnt = null;

    /* 读档。store 的降级链是 save → cache → 内存；save.get 在瘦预览会同步抛，
       core-store 内部已 try/catch，这里再兜一层防它换实现。 */
    function load() {
      if (loaded) return;
      loaded = true;
      var doc_ = null;
      try { doc_ = SBK.store.load(); } catch (e) { doc_ = null; }
      var v = doc_ && doc_[STORE_KEY];
      if (!v || typeof v !== 'object') return;
      if (typeof v.on === 'boolean') on = v.on;
      /* 存档也过 clamp：作者调小了 maxLength 之后，老存档里的长值不能绕过新上限 */
      if (typeof v.text === 'string') text = clamp(v.text);
    }
    function persist() {
      var patch = {};
      patch[STORE_KEY] = { on: on, text: text };
      try { SBK.store.merge(patch); } catch (e) { SBK.warn('ui.inject: persist failed'); }
    }

    /* 当前该追加的内容。空串表示不注入。
       🚨 必须先 load()：payload/apply 可能在面板从未建立时就被调用（作者只用发送拦截、
       不展示面板是合法用法），那时 on/text 还是构造默认值，读档里的玩家设置会被忽略。 */
    function payload() { load(); return on && text ? text : ''; }

    /* ---- 发送拦截 ----
       捕获阶段挂 document：平台收窄的是 querySelector，addEventListener 不受影响。
       用 busy 去重：发送按钮 click 与 Enter 可能都命中同一次发送。 */
    function appendNow() {
      var add = payload();
      if (!add || busy) return false;
      var cur = '';
      try { cur = SBK.sdk.input.get() || ''; } catch (e) { cur = ''; }
      if (!cur) return false;                       /* 空草稿不注入，免得只发注入词 */
      if (cur.indexOf(add) >= 0) return false;      /* 已经含注入词，不重复叠加 */
      busy = true;
      try { SBK.sdk.input.set(cur + sep + add); }
      catch (e) {
        /* IME 组合期 input.set 抛 INVALID_ARGS —— 拼音没上屏时按发送会撞上 */
        SBK.warn('ui.inject: input.set refused (IME composing?), skipping this turn',
                 e && e.code);
        busy = false;
        return false;
      }
      W.setTimeout(function () { busy = false; }, 0);
      return true;
    }
    function onDocDown(e) {
      if (!auto) return;
      var t = e && e.target;
      try {
        while (t && t.nodeType === 1) {
          if (t.getAttribute && t.getAttribute('data-chat') === 'send') { appendNow(); return; }
          t = t.parentNode;
        }
      } catch (er) {}
    }
    function onDocKey(e) {
      if (!auto) return;
      if (!e || e.key !== 'Enter' || e.shiftKey || e.isComposing) return;
      var t = e.target;
      try {
        if (!t || !t.getAttribute) return;
        var inInput = t.getAttribute('data-chat') === 'input' ||
          (t.closest && t.closest('[data-chat="input"]'));
        if (inInput) appendNow();
      } catch (er) {}
    }
    function hooks() {
      if (hooked || !auto) return injApi;
      hooked = true;
      /* click 而非 pointerdown：pointerdown 早于平台把草稿同步进状态的时机就改值，
         反而更容易踩上「平台读旧值」。click 是发送真正成立的那一下。 */
      try { d.addEventListener('click', onDocDown, true); } catch (e) {}
      try { d.addEventListener('keydown', onDocKey, true); } catch (e) {}
      return injApi;
    }

    function sync() {
      if (!box) return;
      box.setAttribute('class', 'sbk-inj' + (on ? '' : ' sbk-inj--off'));
      if (cb) cb.checked = on;
      if (ta) ta.value = text;
      if (cnt) cnt.textContent = text.length + ' / ' + maxLen;
    }

    function panel() {
      if (box) return box;
      css();
      load();
      cb = h('input', { type: 'checkbox', onchange: function () {
        on = !!cb.checked; persist(); sync();
      } });
      ta = h('textarea', {
        'class': 'sbk-inj__ta', rows: 4,
        placeholder: o.placeholder || '\u4f8b\uff1a\uff08\u4fdd\u6301\u7b2c\u4e09\u4eba\u79f0\u53d9\u8ff0\uff09',
        oninput: function () {
          text = clamp(ta.value);
          if (ta.value !== text) ta.value = text;   /* 回写只在真的超长时做，免得打断输入法 */
          if (cnt) cnt.textContent = text.length + ' / ' + maxLen;
        },
        /* onchange 也必须过 clamp：程序性改 value 再 fire change 不经过 oninput */
        onchange: function () { text = clamp(ta.value); persist(); sync(); }
      });
      cnt = h('span', { 'class': 'sbk-inj__cnt' });
      box = h('div', { 'class': 'sbk-inj' }, [
        h('p', { 'class': 'sbk-inj__note' },
          o.note || '\u5f00\u542f\u540e\uff0c\u4e0b\u65b9\u5185\u5bb9\u4f1a\u5728\u4f60\u53d1\u9001\u6d88\u606f\u65f6' +
                    '\u81ea\u52a8\u63a5\u5728\u6d88\u606f\u672b\u5c3e\u4e00\u8d77\u53d1\u51fa\u3002'),
        h('div', { 'class': 'sbk-inj__row' }, [
          h('span', { 'class': 'sbk-inj__lbl' }, o.label || '\u542f\u7528\u6ce8\u5165'),
          h('label', { 'class': 'sbk-inj__sw' }, [cb, h('span')])
        ]),
        ta,
        h('div', { 'class': 'sbk-inj__foot' }, [h('span'), cnt])
      ]);
      sync();
      hooks();
      return box;
    }

    injApi = {
      el: panel,
      panel: panel,
      hooks: hooks,
      /* 🚨 setter 也必须先 load()，不能只有 getter 做。
         否则「存档里已有旧值 + 作者在 panel() 之前先写值」这条路径上，
         首次 panel() 内部的 load() 会把刚写的新值覆盖回旧存档值，作者的初始化被静默吃掉。
         真机症状是「面板一打开就变回上次的内容」，看起来像存档没生效的反面，极难查。
         load() 自带 loaded 哨兵，重复调用无副作用。 */
      enabled: function (v) {
        load();
        if (v === undefined) return on;
        on = !!v; persist(); sync(); return on;
      },
      text: function (v) {
        load();
        if (v === undefined) return text;
        text = clamp(v); persist(); sync(); return text;
      },
      payload: payload,
      /* 手动追加一次（不依赖手势拦截）。作为文件头那条退路的公开出口。 */
      apply: appendNow,
      setAuto: function (v) {
        auto = !!v;
        if (!auto && hooked) {
          try { d.removeEventListener('click', onDocDown, true); } catch (e) {}
          try { d.removeEventListener('keydown', onDocKey, true); } catch (e) {}
          hooked = false;
        } else if (auto) hooks();
        return auto;
      },
      destroy: function () {
        try { d.removeEventListener('click', onDocDown, true); } catch (e) {}
        try { d.removeEventListener('keydown', onDocKey, true); } catch (e) {}
        hooked = false; box = cb = ta = cnt = null; injApi = null;
        return null;
      }
    };
    return injApi;
  }

  SBK.ui = SBK.ui || {};
  SBK.ui.inject = inject;
  SBK.log('ui-inject ready (inject)');
})(typeof window !== 'undefined' ? window : globalThis);
