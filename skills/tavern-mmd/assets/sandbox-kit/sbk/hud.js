/* SBK hud —— 状态数据渲染器与控件注册表。依据：资料/基座事实卡.md、plan.md §2.2
   一份 vnode 与一份控件表，两条出口：toHtml 拼 HTML 字符串、toDom 建 DOM。
   两条出口是渲染管线的需要，与 modes 无关 —— 字符串出口供 snapshot() 塞进正则
   replaceString，DOM 出口供 hydrate() 升级气泡节点、以及功能栏精简条 pinned 复用控件。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] hud.js loaded before core.js');
    return;
  }
  if (!SBK.claim('hud')) return;   // 预览重跑幂等（§3/§4.2）

  /* ---------- vnode ----------
     {t:标签, c:class, s:style, x:文本, k:子节点}
     一份结构，两条出口：toDom 走 SBK.dom.h（建真 DOM），toHtml 拼字符串。
     🚨 字符串出口【不能】用 dom.h：它服务 snapshot()，产物要塞进正则 replaceString，
        那里只接受字符串。DOM 出口服务 hydrate() 与功能栏精简条 pinned。 */
  function esc(s) {
    // 把 > 也转义掉，顺带根治 §5.5：属性值/文本里的 ]> 与 --> 命中 SAFE_FOR_XML 会让整条属性被删
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function toDom(v) {
    var a = {};
    if (v.c) a['class'] = v.c;
    if (v.s) a.style = v.s;
    if (v.on) a.onclick = v.on;         // dom.h 见 function 型 on* 走 addEventListener，不过净化器
    var kids = v.k ? v.k.map(toDom) : null;
    return SBK.dom.h(v.t || 'div', a, v.x !== undefined ? String(v.x) : kids);
  }
  function toHtml(v) {
    var t = v.t || 'div', s = '<' + t;
    if (v.c) s += ' class="' + esc(v.c) + '"';
    if (v.s) s += ' style="' + esc(v.s) + '"';
    /* oc = 内联 onclick 字符串。v.on 是函数，只能走 toDom（字符串路径没法带函数）→
       需要在两条出口都能点的控件（tooltip）必须同时给 on 与 oc。
       §5.5 on* 在【非 SVG】元素上被 forceKeepAttr 强留（实测 <b onclick> KEPT、
       <circle onclick> STRIPPED）→ 内联 onclick 挂在 span 上是安全的。
       🚨 §5.5 SAFE_FOR_XML：属性值命中 ]> / --> / --!> / </style|script|… 会让【整条属性】
          被删，且早于 forceKeepAttr。TT_JS 里因此不出现 ]>，比较运算符两侧留空格。 */
    if (v.oc) s += ' onclick="' + esc(v.oc) + '"';
    s += '>';
    if (v.x !== undefined) s += esc(v.x);
    else if (v.k) for (var i = 0; i < v.k.length; i++) s += toHtml(v.k[i]);
    return s + '</' + t + '>';
  }

  /* base.css 已有的原语，这里只组合不新增类名（base.css 属 WP-B） */
  function row(label, kids) {
    var k = [];
    if (label) k.push({ t: 'span', c: 'sbk-label', x: label });
    return { t: 'div', c: 'sbk-row', k: k.concat(kids) };
  }
  function val(x, grow) { return { t: 'span', c: 'sbk-val' + (grow ? ' sbk-grow' : ''), x: x }; }

  /* ---------- 面板容器类名：单一真相源 ----------
     🚨 快照有两条渲染路径 —— snapshot() 拼字符串、hydrate() 建 DOM。1.0 里两处各写一份
        类名（snapshot 的根带 sbk-snap sbk-card sbk-col，hydrate 的内层只带 sbk-card sbk-col），
        改一处忘另一处就会漂移，而 base.css 靠 .sbk-snap 重置气泡的 opacity:.9 与
        white-space:pre-line（§7.3 / 硬约束 11），漂移的代价是排版直接烂掉。
        → 类名在此定义一次，两条路径都从这里取。 */
  var PANEL = 'sbk-card sbk-col';      // 面板骨架（第一层明度）
  var SNAP = 'sbk-snap';               // 气泡内重置钩子，缺它必烂排版

  /* ---------- tap toggle tooltip（2.0 §3.4 / 盘点 C.5） ----------
     旧资产用纯 CSS :hover。🚨 沙盒是移动端 webview，**hover 在触屏上不成立** → 改点击 toggle。
     两条纪律：
       ① stopPropagation —— 气泡自带点击/长按菜单（§7.2 message-menu z=8200），不拦会掀起菜单。
       ② 显隐用【内联 style】而非 class：base.css 归 WP-B，此处不能假设某个类已存在；
          内联 display 自带初值，缺 CSS 也能正常开合，只是没有浮层定位（可读性仍在）。
     🚨 §5.5：属性值禁 ]> / --> / --!>，比较运算符两侧留空格 —— TT_JS 全程只用 === 与 ？:，
        不含 ] 紧跟 >，故 SAFE_FOR_XML 不会命中。 */
  var TT_JS = "event.stopPropagation();var b = this.nextElementSibling;" +
    "if (b) b.style.display = b.style.display === 'block' ? 'none' : 'block';";
  function ttFn(ev) {
    try {
      if (ev && ev.stopPropagation) ev.stopPropagation();
      var b = this.nextElementSibling;
      if (b) b.style.display = b.style.display === 'block' ? 'none' : 'block';
    } catch (e) {}
  }
  /* 有 note 就包成「触发词 + 折叠的说明」，没有就退回一个普通 span —— 调用方无需分支。 */
  function tip(text, note, cls) {
    var c = cls || 'sbk-val';
    if (!note) return { t: 'span', c: c, x: text };
    return {
      t: 'span', c: 'sbk-tt', k: [
        { t: 'span', c: c + ' sbk-tt__hit', x: text, on: ttFn, oc: TT_JS },
        { t: 'span', c: 'sbk-tt__box', s: 'display:none', x: note }
      ]
    };
  }

  /* ---------- 控件表 ----------
     f = {key,label,type,value,max,unit,opt}。可扩展：SBK.ui.hud.type('自定义', fn)。
     🚨 配色一律 var(--chat-*)，零硬编码色值：写死颜色会让平台深浅色切换失效（§7.1）。
        §9 实测深色 --chat-accent:#ff6d97，只作视觉参考，代码里仍用变量。 */
  function pct(v, m) { return m > 0 ? Math.max(0, Math.min(100, v / m * 100)) : 0; }

  /* ---------- 语义色：字段 → tone（2.0 §3.3 / 盘点 B.5 + D.1） ----------
     base.css（WP-B）已备好令牌与 tone 类，但没有任何代码把字段映射到 tone，
     于是所有 bar 都落 `var(--sbk-tone, var(--chat-accent))` 的回退 = 同一个金色。
     这里补的就是那根线：解析出 tone → bar 槽加 .sbk-bar--<tone>。
     🚨 只能走 class，不能走 data-*：事实卡 §5.5 实测「作者自写 data-* 全删」（硬约束 9）。
     🚨 类名/令牌名与 base.css 逐字一致（已 grep 核对 base.css L170-173）。 */
  var TONES = { hp: 1, mp: 1, sp: 1, xp: 1 };    // 合法值恰四种，表外一律告警并忽略

  /* 中文关键词 → tone，**按数组顺序取首个子串命中**。
     顺序只在存在子串包含关系时才重要（如「体力值」含「体力」→ 同归 hp，无歧义）。
     🚨「体力」是真实歧义：武侠卡里常指耐力(sp)，战斗卡里常指血条(hp)。
        这里默认判 **hp**，依据两条：
          ① 移植目标是旧资产「hp 红/mp 蓝/sp 绿」的自动配色，而旧资产的 hp 条在中文卡里
             最常见的写法就是「体力」（盘点 B.5）；
          ② 「体力/体力值」是同一概念的两种写法，不该因为一个「值」字分到两种颜色。
        要改成 sp 只需把下面 ['体力','hp'] 挪进 sp 段——做卡人也可以用显式 tone 逐字段覆盖。 */
  var TONE_HINTS = [
    ['血量', 'hp'], ['生命', 'hp'], ['气血', 'hp'], ['血条', 'hp'], ['体力', 'hp'], ['血', 'hp'],
    ['灵力', 'mp'], ['法力', 'mp'], ['魔力', 'mp'], ['魔法', 'mp'], ['内力', 'mp'],
    ['真气', 'mp'], ['查克拉', 'mp'], ['精神', 'mp'],
    ['精力', 'sp'], ['耐力', 'sp'], ['饱食', 'sp'], ['饥饿', 'sp'], ['斗志', 'sp'],
    ['经验', 'xp'], ['修为', 'xp'], ['熟练', 'xp'], ['成长', 'xp']
  ];
  /* ✅ 已修（base.css 侧）：.sbk-bar--xp 曾同时赋 --sbk-tone 并把高度从 10rpx 压到 8rpx，
     于是 key 含「经验/修为/熟练/成长」的【普通 bar 字段】会连带变薄 —— 颜色与尺寸耦合。
     现在 base.css 的高度规则已收窄成 .sbk-level .sbk-bar--xp（细条只属 level，盘点 B.6），
     裸 .sbk-bar--xp 只负责颜色 → 普通 bar 的 xp 字段高度回到 10rpx。此处无需再做任何事。 */

  /* 英文分两档，因为短码会误伤：
       EN_WORD  长词，子串匹配足够安全（'health' 不会藏在别的字段名里）；
       EN_CODE  两三字母短码，【必须整词匹配】——'hp' 藏在 champion、'mp' 藏在 temperature、
                'sp' 藏在 speed/despair 里，子串匹配会把「体温 temperature」染成蓝色。
     整词判定：按非字母数字切分（空格/下划线/连字符/中文标点都算分隔），逐 token 全等比较。 */
  var EN_WORD = [
    ['health', 'hp'], ['vitality', 'hp'], ['blood', 'hp'],
    ['mana', 'mp'], ['magic', 'mp'], ['spirit', 'mp'],
    ['stamina', 'sp'], ['energy', 'sp'], ['endurance', 'sp'], ['satiety', 'sp'], ['hunger', 'sp'],
    ['experience', 'xp'], ['proficiency', 'xp']
  ];
  var EN_CODE = { hp: 'hp', mp: 'mp', sp: 'sp', xp: 'xp', exp: 'xp', ep: 'sp' };

  /* 只按 key 推断，不看任何上下文（不猜「这张卡还有没有别的条」——那种推断不可复现）。 */
  function toneByKey(key) {
    var s = String(key == null ? '' : key), low = s.toLowerCase(), i, toks, t;
    for (i = 0; i < TONE_HINTS.length; i++) if (s.indexOf(TONE_HINTS[i][0]) >= 0) return TONE_HINTS[i][1];
    for (i = 0; i < EN_WORD.length; i++) if (low.indexOf(EN_WORD[i][0]) >= 0) return EN_WORD[i][1];
    toks = low.split(/[^a-z0-9]+/);
    for (i = 0; i < toks.length; i++) {
      t = toks[i];
      if (t && Object.prototype.hasOwnProperty.call(EN_CODE, t)) return EN_CODE[t];
    }
    return '';
  }

  /* 显式 tone 优先于 key 推断；推断【只对 bar 生效】——num/text/tags 没有条，染色无意义。
     非法值告警而非静默：做卡人写了 tone:'red' 若无声忽略，他会以为生效了（本次缺口的教训）。
     显式 tone 即使写在非 bar 字段上也照样校验，这样拼写错误在任何类型上都能被发现。
     🚨 type==='section' 走的也是这里：分组级 tone【只认显式声明，不做 key 推断】——
        section 没有 key（它是版面声明不是数据字段），label 是给人看的组名，
        拿「状态」这种组名去猜颜色属于过度推断，且不可复现。校验与告警口径与字段级完全一致。 */
  function toneOf(type, key, def) {
    var t = def && def.tone;
    if (t !== undefined && t !== null && t !== '') {
      t = String(t).toLowerCase();
      if (Object.prototype.hasOwnProperty.call(TONES, t)) return t;
      SBK.warn('hud: unknown tone ' + JSON.stringify(def.tone) + ' on ' +
        (type === 'section' ? 'section' : 'field') + ' ' +
        JSON.stringify(String(key)) + ', ignored (valid: hp|mp|sp|xp)');
      return '';
    }
    return type === 'bar' ? toneByKey(key) : '';
  }
  var TYPES = {
    bar: function (f) {
      var p = pct(f.value, f.max), tx = f.unit === '%' ? f.value + '%' : f.value + '/' + f.max;
      /* tone 类挂在【bar 槽本身】而不是祖先：.sbk-tone--* 挂祖先会让整行/整组的条与
         .sbk-stat 竖条一起变色（base.css L166-173 两种用法同一个消费点），
         对「一行一条」的 bar 而言那是外溢。槽上加 .sbk-bar--* 只染这一条，精确。 */
      return row(f.label, [
        {
          t: 'div', c: 'sbk-bar sbk-grow' + (f.tone ? ' sbk-bar--' + f.tone : ''),
          k: [{ t: 'div', c: 'sbk-bar__fill', s: 'width:' + p.toFixed(1) + '%' }]
        },
        val(tx)
      ]);
    },
    num: function (f) { return row(f.label, [val(String(f.value) + (f.unit || ''), 1)]); },
    text: function (f) { return row(f.label, [val(f.value, 1)]); },
    tags: function (f) {
      var k = [], a = f.value, i;
      for (i = 0; i < a.length; i++) k.push({ t: 'span', c: 'sbk-chip', x: a[i] });
      return { t: 'div', c: 'sbk-row sbk-row--wrap', k: (f.label ? [{ t: 'span', c: 'sbk-label', x: f.label }] : []).concat(k) };
    },
    /* ---- 2.0 §3.2 值的内部结构。四个都是纯展示零状态，两条出口通用。 ---- */
    /* path：面包屑 chips，段间 › （\u203A）。复用 .sbk-chip，只新增箭头类名。 */
    path: function (f) {
      var a = f.value, k = [], i;
      for (i = 0; i < a.length; i++) {
        if (i) k.push({ t: 'span', c: 'sbk-arrow', x: '\u203A' });
        k.push({ t: 'span', c: 'sbk-chip sbk-crumb', x: a[i] });
      }
      return { t: 'div', c: 'sbk-row sbk-row--wrap', k: (f.label ? [{ t: 'span', c: 'sbk-label', x: f.label }] : []).concat(k) };
    },
    /* level：上行「左等级名 + 右经验」，下行 XP 条。
       🚨 只有经验段解析成功才画条（盘点 B.6）：否则只留一行名字，不画 0% 的空槽 —— 那是
          1.0 bar 在缺 max 时的取巧写法留下的视觉噪音。 */
    level: function (f) {
      var v = f.value || {}, k = [], has = typeof v.value === 'number' && typeof v.max === 'number' && v.max > 0;
      k.push({
        t: 'div', c: 'sbk-row', k: [
          { t: 'span', c: 'sbk-val sbk-grow', x: v.name || '' },
          { t: 'span', c: 'sbk-label', x: has ? v.value + '/' + v.max : '' }
        ]
      });
      if (has) k.push({ t: 'div', c: 'sbk-bar sbk-bar--xp', k: [{ t: 'div', c: 'sbk-bar__fill', s: 'width:' + pct(v.value, v.max).toFixed(1) + '%' }] });
      return row(f.label, [{ t: 'div', c: 'sbk-col sbk-grow sbk-level', k: k }]);
    },
    /* stats：`键:值` chip 紧凑网格（chip 左 3px 主题色竖条由 WP-B 的 .sbk-stat 提供）。
       第三段成因 → tap toggle tooltip，把第三层信息折进第二层（盘点 B.7 / E.4）。 */
    stats: function (f) {
      var a = f.value, k = [], i, e;
      for (i = 0; i < a.length; i++) {
        e = a[i];
        k.push({
          t: 'span', c: 'sbk-chip sbk-stat', k: [
            { t: 'span', c: 'sbk-label', x: e.name },
            tip(e.value, e.note, 'sbk-val')
          ]
        });
      }
      return { t: 'div', c: 'sbk-row sbk-row--wrap', k: (f.label ? [{ t: 'span', c: 'sbk-label', x: f.label }] : []).concat(k) };
    },
    /* kvlist：竖排「槽位：名」，信息密度最高的控件（盘点 B.8）。名带 |说明 → tooltip。 */
    kvlist: function (f) {
      var a = f.value, k = [], i, e;
      for (i = 0; i < a.length; i++) {
        e = a[i];
        k.push({ t: 'div', c: 'sbk-row sbk-kv', k: [{ t: 'span', c: 'sbk-label', x: e.name }, tip(e.value, e.note, 'sbk-val sbk-grow')] });
      }
      if (f.label) k.unshift({ t: 'span', c: 'sbk-label', x: f.label });
      return { t: 'div', c: 'sbk-col', k: k };
    },
    entities: function (f) {
      var k = [], a = f.value, i, e, top = 0;
      for (i = 0; i < a.length; i++) if (a[i].value > top) top = a[i].value;
      if (top <= 0) top = 1;
      for (i = 0; i < a.length; i++) {
        e = a[i];
        k.push(row(e.name, [
          { t: 'div', c: 'sbk-bar sbk-grow', k: [{ t: 'div', c: 'sbk-bar__fill', s: 'width:' + pct(e.value, f.max || top).toFixed(1) + '%' }] },
          val(String(e.value))
        ]));
      }
      if (f.label) k.unshift({ t: 'span', c: 'sbk-label', x: f.label });
      return { t: 'div', c: 'sbk-col', k: k };
    }
  };

  /* ---------- schema → 字段列表 ----------
     schema = { title?, fields?: [ {key,label?,type?,max?,unit?} | '键名' ], extra?:true, persist?:true }
     fields 缺省 = 按模型输出顺序全渲染（order 由 SBK.parse 给出）。 */
  /* schema 里 type 覆写后，值的形态可能与控件不符（把 text 强制成 tags 等）。
     不 coerce 的话 tags 渲染器会把字符串按【字符】迭代，一个字一个 chip。
     所以按目标类型重新分类一次，让「type 覆写」在任何输入上都安全。 */
  /* 结构类型的强制适配走 SBK.parse.struct —— 与推断路径【同一批解析器】（protocol.js）。
     不在这里自己 split：那会让「自动认出的 stats」与「schema 写 type:'stats' 的 stats」
     出现两套行为，是最难查的一类不一致。struct 解析失败返回 null → 下面按类型给安全空值，
     渲染器拿到空数组/空对象只会画一个空壳，不会抛。 */
  var STRUCT = { path: 1, level: 1, stats: 1, kvlist: 1 };
  function fit(type, v, raw) {
    var re;
    if (STRUCT[type]) {
      // 已经是目标形态就直接用（patch 进来的值可能本身就是结构）
      if (type === 'level' ? (v && typeof v === 'object' && !Array.isArray(v)) : Array.isArray(v)) return v;
      re = SBK.parse.struct ? SBK.parse.struct(type, raw === undefined ? v : raw) : null;
      if (re) return re;
      SBK.warn('hud: cannot coerce value to ' + type + ', rendering empty shell');
      return type === 'level' ? { name: typeof v === 'string' ? v : String(raw === undefined ? '' : raw), value: null, max: null } : [];
    }
    if (type === 'tags') return Array.isArray(v) ? v : (re = SBK.parse.value(raw), Array.isArray(re.value) ? re.value : [String(v)]);
    /* entities 要的是 [{name,value:数}]。🚨 原先只判 Array.isArray 就放行，于是
       「原始值数组」也能过（文本 'a, b' 强制 type:'entities' 时先被切成 tags 的
       ['a','b'] 再送进来）→ 渲染器读 e.name/e.value 全是 undefined，
       pct(undefined,…) 算出 NaN → 实测吐出 width:NaN% 与 undefined。
       这与缺口 3 是同一种失败形态，只是入口在「强制类型」而非「直喂」，故一并收口：
       形状不合就按 fit() 既有纪律给空壳 + 告警，绝不把 NaN 送进 DOM。 */
    if (type === 'entities') {
      if (!Array.isArray(v)) return [];
      if (allPairs(v) && v.length) {
        re = [];
        for (var ei = 0; ei < v.length; ei++) re.push({ name: String(v[ei].name), value: numOr0(v[ei].value) });
        return re;
      }
      if (!v.length) return [];
      SBK.warn('hud: cannot coerce value to entities (need [{name,value}]), rendering empty shell');
      return [];
    }
    if (type === 'bar' || type === 'num') {
      if (typeof v === 'number') return v;
      re = SBK.parse.value(raw);
      return typeof re.value === 'number' ? re.value : 0;
    }
    return typeof v === 'string' ? v : (Array.isArray(v) ? v.join(', ') : String(raw === undefined ? v : raw));
  }
  /* ---------- 直喂结构化入参的识别（做卡人直接调 API 会踩的坑） ----------
     🚨 成因：cell() 原先只认「parse 出来的描述对象」（带 .type），其余一律过 SBK.parse.value()，
        而 parse.value 的入口是 String(raw) —— 直接喂数组/对象
        （SBK.ui.snapshot({好感:[{name:'苏九',value:61}]}, {fields:[{key:'好感',type:'entities'}]})）
        会被 stringify 成 '[object Object]'，于是：
          · 单项   → 落 text，fit('entities') 返回 [] → 整行【静默消失】；
          · 两项起 → '[object Object],[object Object]' 被切成 tags，再按 entities 消费
                     → 渲染出 width:NaN% 与 undefined（实测复现，即本缺口的报错形态）。
        文本形态（'好感: 苏九=61'）一直正常，所以只有【直接调 API 的做卡人】会踩。
     修法：入参已是结构化数组/对象时【直接采用】，不再过 parse.value。
     ⚠ 判定【只看形状不看类型名】：形状对得上就采用；对不上返回 null 交回原路
       （仍走 parse.value → 降级 text），行为不变，容错优先（与 protocol.js 同一纪律）。
     ⚠ 不改 protocol.js（不在名下且不该改）：那里管「文本 → 结构」，
       本缺口是 hud 侧「结构 → 结构」这条路径根本不存在。 */
  function allPrim(a) {
    for (var i = 0; i < a.length; i++) if (a[i] !== null && typeof a[i] === 'object') return false;
    return true;
  }
  // 键值项数组：每项都是带 name 的普通对象（entities/stats/kvlist 三者的共同形状）
  function allPairs(a) {
    var i, e;
    for (i = 0; i < a.length; i++) {
      e = a[i];
      if (!e || typeof e !== 'object' || Array.isArray(e) || e.name === undefined) return false;
    }
    return true;
  }
  function allNumVal(a) {
    for (var i = 0; i < a.length; i++) if (typeof a[i].value !== 'number') return false;
    return true;
  }
  // entities 的 value 必须是有限数：非数字会让 pct() 算出 NaN（本缺口的报错形态），故兜底 0
  function numOr0(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /* 入参已是结构化值 → 合成一个与 parse.value() 【同形】的描述对象（{type,value,max?,unit?}）。
     同形是关键：cell() 下游（fit/toneOf/渲染器）完全不需要知道值是文本解析来的还是直喂的，
     两条来源在此汇成一条，不会产生第二套行为。
     want = schema 里声明的 type（可空）。形状与 want 都对得上就按 want 采用；
     没写 want 就按形状推断；形状对不上返回 null（交回 parse.value 原路，不发明数据）。 */
  function direct(want, v) {
    var i, e, out;
    if (v === null || v === undefined || typeof v !== 'object') return null;

    if (Array.isArray(v)) {
      // tags/path：元素必须全是原始值（对象数组不是标签组，交回原路）
      if (want === 'tags' || want === 'path' || (!want && allPrim(v))) {
        if (!allPrim(v)) return null;
        out = [];
        for (i = 0; i < v.length; i++) out.push(String(v[i]));
        return { type: want === 'path' ? 'path' : 'tags', value: out };
      }
      if (!allPairs(v)) return null;          // 键值项数组之外的形状一律交回原路
      // entities：名 + 数。value 走 numOr0 兜底，杜绝 pct() 的 NaN。
      if (want === 'entities' || (!want && allNumVal(v))) {
        out = [];
        for (i = 0; i < v.length; i++) out.push({ name: String(v[i].name), value: numOr0(v[i].value) });
        return { type: 'entities', value: out };
      }
      /* stats/kvlist 同形（{name,value,note}），靠 want 区分；没写 want 时取 stats ——
         kvlist 的文本形态以 | 分项、stats 以逗号/空白分项，直喂时这个线索不存在，
         而 stats 是更紧凑的默认版面（盘点 B.7）。想要 kvlist 就显式写 type。 */
      if (want === 'stats' || want === 'kvlist' || !want) {
        out = [];
        for (i = 0; i < v.length; i++) {
          e = v[i];
          out.push({ name: String(e.name), value: e.value === undefined ? '' : String(e.value),
            note: e.note === undefined || e.note === null ? '' : String(e.note) });
        }
        return { type: want === 'kvlist' ? 'kvlist' : 'stats', value: out };
      }
      return null;
    }

    /* 非数组对象。level 的 {name,value,max} 与 bar 的 {value,max} 是两种直喂形态。
       判定顺序：先看 name（有名字就是 level，bar 没有名字概念），再看 value/max。 */
    if (v.name !== undefined && (want === 'level' || !want || want === 'bar')) {
      if (want === 'bar' && !isNum(v.value)) return null;
      if (want !== 'bar') {
        return { type: 'level', value: {
          name: String(v.name),
          value: isNum(v.value) ? v.value : null,
          max: isNum(v.max) ? v.max : null } };
      }
    }
    if (isNum(v.value)) {
      // 有 max → 进度条；无 max 时只有显式 want==='bar' 才画条（cell() 随后补 max=100），
      // 否则当纯数值 num —— 与 parse.value('380') 落 num 的口径一致。
      if (isNum(v.max) && v.max !== 0) return { type: 'bar', value: v.value, max: v.max, unit: v.unit };
      if (want === 'bar') return { type: 'bar', value: v.value, unit: v.unit };
      return { type: 'num', value: v.value, unit: v.unit };
    }
    return null;
  }

  function cell(key, raw, def) {
    def = def || {};
    var f = raw, d;
    // 允许业务方直接 patch 原始值（state.patch({血量:'72/100'})）→ 这里补跑一次分类器
    if (!f || typeof f !== 'object' || !f.type) {
      d = direct(def.type, f);
      f = d || SBK.parse.value(f === undefined || f === null ? '' : f);
    }
    var ty = def.type || f.type;
    var mx = def.max !== undefined ? def.max : f.max;
    // 强制成 bar 却没给上限（「金币: 380」+ type:'bar'）→ 按百分比常规取 100，
    // 否则会渲染出 "380/undefined" 和 0% 宽度的空条
    if (ty === 'bar' && !(typeof mx === 'number' && isFinite(mx) && mx !== 0)) mx = 100;
    /* tone 在此【算一次】并落到字段对象上 —— cell() 是 snapshot()（字符串路径）与
       hydrate()（DOM 路径）唯一的公共上游（两者都经 tree → pick → cell），
       所以两条路径拿到的 tone 必然同源。类名同源的纪律见上方 PANEL/SNAP 的注释：
       此前正是「两处各写一份」导致过漂移。 */
    return {
      key: key, label: def.label === undefined ? key : def.label,
      type: ty, value: ty === f.type ? f.value : fit(ty, f.value, f.raw),
      max: mx, unit: def.unit || f.unit, tone: toneOf(ty, key, def), opt: def
    };
  }
  function pick(state, schema, order) {
    var sc = schema || {}, out = [], seen = {}, defs = sc.fields, i, d, k;
    if (defs && defs.length) {
      for (i = 0; i < defs.length; i++) {
        d = typeof defs[i] === 'string' ? { key: defs[i] } : (defs[i] || {});
        /* 🚨 section 是【版面声明】不是数据字段（2.0 §3.1 / 盘点 B.1）：它没有 key、
           state 里也没有对应值，所以必须在「无 key 就跳过」与「模型没输出就跳过」两道
           过滤【之前】原样放行，否则分组永远出不来。空分组由 tree() 负责不渲染。 */
        /* 组级 tone 在此算一次并落到 section 描述对象上，与字段级 tone 同一个 toneOf()
           （同一批校验/告警），故两级语义永不漂移。key 位传 label 仅用于告警可读性。 */
        if (d.type === 'section') {
          out.push({ type: 'section', label: d.label || '', tone: toneOf('section', d.label || '', d), opt: d });
          continue;
        }
        k = d.key;
        if (!k) continue;
        seen[k] = 1;
        // 声明了但本轮模型没输出 → 跳过而不是渲染空行（缺项容错）
        if (!Object.prototype.hasOwnProperty.call(state, k)) continue;
        out.push(cell(k, state[k], d));
      }
      if (sc.extra !== true) return out;
    }
    var ord = order && order.length ? order : Object.keys(state);
    for (i = 0; i < ord.length; i++) {
      k = ord[i];
      if (seen[k] || k.charAt(0) === '_') continue;   // _ 前缀为内部字段，不渲染
      if (!Object.prototype.hasOwnProperty.call(state, k)) continue;
      out.push(cell(k, state[k], null));
    }
    return out;
  }
  /* ---------- 版面层：section 分组（2.0 §3.1，最大缺口） ----------
     1.0 只有 sbk-card 一个容器，20 个字段拉平成一张长表，读者拿不到「哪几项是一组」
     （盘点 E.1 判定这是「视觉太朴素」的根因）。
     实现是一个【游标 + 惰性开卡】：遇到 section 先把上一组收口，后续字段累进当前组，
     直到下一个 section。组内一个字段都没有就【不产出这张卡】——
     连续两个 section、或整组字段本轮模型全没输出时，都不会留下空卡片。
     三层明度递进（面板 → 分组卡 → 内容区）与组标题配色属 WP-B 的 .sbk-sect*，此处只给结构。 */
  function tree(state, schema, order) {
    var fs = pick(state, schema, order), out = [], cur = null, curLabel = '', curTone = '', i, f, fn, node;
    if (schema && schema.title) out.push({ t: 'div', c: 'sbk-label sbk-title', x: schema.title });

    function flush() {
      if (cur && cur.length) {
        var k = curLabel ? [{ t: 'div', c: 'sbk-label sbk-sect__t', x: curLabel }].concat(cur) : cur;
        /* 组级 tone 挂在【分组卡】这个祖先上（base.css 的 .sbk-tone--* 用法①）：
           --sbk-tone 靠继承传给组内所有 .sbk-bar__fill 与 .sbk-stat 左竖条，一次染整组。
           🚨 字段自己的 .sbk-bar--* 仍然赢：那是 bar 槽【自身】的声明，
              层叠里「自身声明」强于「继承值」，与特异度/源码顺序无关（base.css 同处有说明）。
           🚨 只能走 class 不能走 data-*：事实卡 §5.5 作者自写 data-* 全删（硬约束 9）。 */
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
      // 有分组游标就进组，没有（schema 没写 section，或首个 section 之前的字段）就直接进面板
      if (cur) cur.push(node); else out.push(node);
    }
    flush();
    return out;
  }

  /* ---------- SBK.ui.hud —— 2.0 已废弃，退化为控件注册表 + 告警壳 ----------
     处置理由（2.0 设计文档 §一/§2.1，实机截图确证）：
       1.0 的 hud 是「把状态数据面板渲染进功能栏槽位」。截图里页面同时出现两个一模一样的
       面板（功能栏一个、气泡内一个），字段与样式完全相同 —— 这是 1.0 的头号缺陷，
       性质是【违反 MMD 惯例】（功能栏历来放 chrome，状态栏在气泡内），不是代码 bug。
     2.0 里它的三项职责已各有归属，没有任何调用方剩下：
       · 状态数据面板 → 气泡内状态面板（本文件 snapshot/hydrate）= modes.status
       · 功能栏常驻   → core.js 的 pinned()（单行精简条，形态被强制区分，默认关）
       · 功能栏入口   → ui.js 的 chrome()
     实证：core.js 的 boot() 已完全不引用 SBK.ui.hud（status→snapshot.auto、chrome→ui.chrome、
     pinned→core 自带），全仓库无其它调用点。→ 渲染器本体是死代码，删掉省预算（§5.2）。
     🚨 但【不能连符号一起删】：协议说明 §3.1 把 SBK.ui.hud.type() 写成自定义控件的公开
        注册入口，做卡人代码里存在。故保留同名壳：
          · .type()/.types() 原样可用（注册表是真的，注册进去的控件在快照里生效）
          · 直接当渲染器调 → 告警并返回一个惰性句柄（feed 返回 false、el 返回 null），
            不挂任何订阅、不写任何 DOM。老卡不会抛异常炸整卡，但也不会再渲染出重复面板。 */
  function hud() {
    SBK.warn('SBK.ui.hud is removed in 2.0 (it put a data panel in the toolbar, which duplicated ' +
      'the in-bubble panel). Use SBK.ui.snapshot.auto(schema) for the status panel, ' +
      'SBK.pinned(keys) for a single-line toolbar strip, or SBK.ui.chrome() for toolbar entries. ' +
      'SBK.ui.hud.type() still works for registering custom widgets.');
    return {
      el: function () { return null; },
      render: function () {},
      feed: function () { return false; },
      mount: function () { return false; }
    };
  }
  hud.type = function (name, fn) { if (name && typeof fn === 'function') TYPES[String(name)] = fn; return hud; };
  hud.types = function () { return Object.keys(TYPES); };

  /* ---------- 气泡内状态面板（modes.status，唯一的状态数据渲染器） ----------
     随消息滚动 = 天然的历史快照，故内部与 API 沿用 snapshot 之名。
     返回 HTML 字符串（要塞进正则 replaceString，故【不能】用 dom.h）。
     🚨 已裁决第 4 条：根元素必须带 .sbk-snap —— base.css 靠它把 message-body 的
        opacity:.9 与 white-space:pre-line 重置掉（§7.3 / 硬约束 11），少这个类排版必烂。
     🚨 净化合规（§5.5）：无自写 data-* 属性（全删）、无 aria 属性与 role（ALLOW_ARIA_ATTR:!1 全删）、
        属性值经 esc() 后不可能含 ]> 或 -->（SAFE_FOR_XML 会删整条属性）。
        标签只用 div/span（§5.4 worker 白名单 ∩ DOMPurify）。
     🚨 §5.2 单条规则输出预算 max(262144, 输入长度×4)，超限【整条回滚】→ 产物必须紧凑：
        无缩进、无换行、无注释，class 名复用 base.css 已有原语。 */
  function snapshot(state, schema) {
    var st = state, ord = null;
    if (st && typeof st === 'object' && st.state && typeof st.state === 'object') {
      ord = st.order; st = st.state;    // 容忍直接把 SBK.parse 的返回值传进来
    }
    if (!st || typeof st !== 'object') return '';
    var kids = tree(st, schema || {}, ord), s = '', i;
    for (i = 0; i < kids.length; i++) s += toHtml(kids[i]);
    if (!s) return '';
    return '<div class="' + SNAP + ' ' + PANEL + '">' + s + '</div>';   // 类名单一真相源，见 PANEL/SNAP 定义
  }

  /* 升级：正则把 <状态>…</状态> 换成 <div class="sbk-snap sbk-snap--raw">原文</div>（纯文本，
     不含 HTML，天然安全），这里在 mount 回调内把它解析并替换成真渲染。
     好处是不需要正则会算百分比 —— 正则只搬字符串，计算全在 JS。
     §4.3：必须用回调给的 root（dom.all 在 root 上查，走 Element.prototype 原生实现，不受 gc 影响）。 */
  function hydrate(root, schema) {
    var nodes = SBK.dom.all(root, '.sbk-snap--raw'), i, n, r, kids, box, j;
    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      if (n.getAttribute('class').indexOf('sbk-snap--done') >= 0) continue;   // 幂等：mount 可能补发
      var tx = n.textContent;
      r = SBK.parse(tx);
      // §5.4 剥壳在正则管线【之后】跑：若做卡人的 replaceString 原样吐回 <状态>，这个中文标签
      // 会被当非白名单标签删掉，此处拿到的就是裸行。补回方括号标记再试一次，两种写法都能活。
      if (!r || !r.order.length) {
        var w = SBK.parse(SBK.parse.wrap(tx));
        // 只在真解析出字段时才采纳：否则一段普通文字会被「成功解析成空块」而被清空
        if (w && w.order.length) r = w;
      }
      // 解析不出来就原样留着（.sbk-pre 保住换行），比清空成空白块友好
      if (!r || !r.order.length) { n.setAttribute('class', SNAP + ' sbk-pre sbk-snap--raw sbk-snap--done'); continue; }
      kids = tree(r.state, schema || {}, r.order);
      while (n.firstChild) n.removeChild(n.firstChild);
      box = SBK.dom.h('div', { 'class': PANEL });          // 与 snapshot() 同源（PANEL），不再各写一份
      for (j = 0; j < kids.length; j++) box.appendChild(toDom(kids[j]));
      n.appendChild(box);
      n.setAttribute('class', SNAP + ' sbk-snap--raw sbk-snap--done');
    }
    return nodes.length;
  }
  snapshot.hydrate = hydrate;
  // 自动升级开关：装一次即可，mount 有补发（§4.1）故历史气泡也会被处理
  snapshot.auto = function (schema) {
    SBK.on('mount', function (p, root) { if (root) hydrate(root, schema); });
    SBK.on('done', function (p, root) { if (root) hydrate(root, schema); });
    return snapshot;
  };

  /* 合并而非覆盖：WP-3 的 ui.js 会往同一个 SBK.ui 上挂 panel/stage，直接赋新对象会互相踩掉 */
  SBK.ui = SBK.ui || {};
  SBK.ui.hud = hud;
  SBK.ui.snapshot = snapshot;
  SBK.log('hud ready, types=' + hud.types().join(','));
})(typeof window !== 'undefined' ? window : globalThis);
