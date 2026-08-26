/* SBK theme —— 主题层。挂到 core.js 建立的同一个 window.SBK 上。依据：基座事实卡.md §7.1 / 包分析-CSS D 节 */
(function (W) {
 'use strict';
 var SBK = W.SBK;
 if (!SBK || !SBK.claim) { (W.console && W.console.warn) && W.console.warn('[SBK] theme.js loaded before core.js'); return; }
 if (!SBK.claim('theme')) return;   // 预览重跑幂等（§3/§4.2）

 var d = W.document;
 var STYLE_ID = 'sbk-theme-vars';

 /* §7.1 平台每套 14 个变量，定义在 [data-theme=dark]（L1234）与 [data-theme=light]（L1250）。
   手册只记 10 个，漏 share-pick-bg / input-bg / input-text / shortcut-text / more-item-bg。
   ⚠ 无 :root 定义、无 prefers-color-scheme → 覆盖 :root 不生效。
   ⚠ --chat-viewport-height 不在此列：JS 写在 root 的内联 style（随 visualViewport 更新），CSS 覆盖不了。
   ⚠ --rpx = calc(100vw / 750) 是平台尺寸基准，改它整体错位 → 只读不写。 */
 var VARS = ['bg', 'surface', 'text', 'text-muted', 'border', 'accent',
  'bubble-user-bg', 'bubble-ai-bg', 'bubble-text',
  'share-pick-bg', 'input-bg', 'input-text', 'shortcut-text', 'more-item-bg'];

 /* 语义 token → 平台 --chat-* 映射。作者写语义名，基座翻译。 */
 var MAP = {
  bg: 'bg', surface: 'surface', panel: 'surface', text: 'text', muted: 'text-muted',
  border: 'border', accent: 'accent', primary: 'accent',
  userBubble: 'bubble-user-bg', aiBubble: 'bubble-ai-bg', bubbleText: 'bubble-text',
  sharePick: 'share-pick-bg', inputBg: 'input-bg', inputText: 'input-text',
  shortcutText: 'shortcut-text', moreItemBg: 'more-item-bg'
 };

 function toVar(k) {
  if (k.indexOf('--') === 0) return k;                 // 直给 --chat-* 或自定义 --sbk-*
  if (MAP[k]) return '--chat-' + MAP[k];
  if (VARS.indexOf(k) >= 0) return '--chat-' + k;      // 直给平台后缀名
  // 未知语义名收进基座私有命名空间，camelCase → kebab（onAccent → --sbk-on-accent，对齐 base.css）
  return '--sbk-' + k.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
 }

 function hasOwn(o, k) { return !!o && Object.prototype.hasOwnProperty.call(o, k); }

 /* SBK 私有令牌白名单（值 1 = 允许作者/风格包写）。清单来源是【base.css 真正消费的那些】：
   多写一个没人消费的 --sbk-xxx 只会静默无效，不如生成期就拦住。
   ⚠ 故意不收 --sbk-z-panel/--sbk-z-pop：硬约束 12 的 3500–7999 安全带是结构约定，
    让风格包改层级等于把浮层塞到平台 chrome 底下。
   ⚠ 也不收 --sbk-tone：它是 hud.js 逐条 bar 局部赋的语义色游标（var(--sbk-tone,…)），
    全局写死会让所有进度条同色，正是 2.0 要修的头号视觉问题。 */
 var SBK_OK = {
  'gap': 1, 'pad': 1, 'radius': 1,          // layout：节奏
  'fs': 1, 'fs-sm': 1, 'lh': 1,             // font：字号/次级字号/行距
  'on-accent': 1,                           // palette：accent 上的前景（平台 14 个里没有）
  'shadow': 1, 'lift': 1, 'ball': 1, 'drw-w': 1,   // ui：浮层阴影/提亮层/悬浮球/抽屉宽
  'glow': 1, 'hp': 1, 'mp': 1, 'sp': 1, 'xp': 1    // decoration：发光半径 + 四条语义色
 };

 /* 危险值统一闸门。前两条是【会截断样式块】的注入面（1.0 已有）；后四条是本轮补的：
   url( 与 @import 在 §2 CSP 下要么被封要么是外部依赖（风格包一律零外部资源）；
   expression( 是旧 IE 的可执行 CSS；`;` 与 `{` 让一个令牌值凭空多写几条声明，
   等于绕过令牌白名单。合法值（#hex / rgba() / calc() / 阴影列表）都不含这些。 */
 var DANGER = /\}|\{|;|<\/style|<\/script|url\s*\(|@import|expression\s*\(|javascript\s*:/i;

 /* 令牌名白名单：平台语义名 / 14 个平台后缀 / --chat-* 里确实存在的那 14 个 /
   SBK_OK 私有名 / PAGE 页面级属性。其余一律拒——包括 --chat- 里的臆造名：
   平台没定义的变量写了不报错也不生效，是典型静默失效。 */
 function okToken(k) {
  if (typeof k !== 'string' || !k) return false;
  if (hasOwn(PAGE, k)) return true;
  if (k.indexOf('--chat-') === 0) return VARS.indexOf(k.slice(7)) >= 0;
  if (k.indexOf('--sbk-') === 0) return SBK_OK[k.slice(6)] === 1;
  if (k.indexOf('--') === 0) return false;
  if (hasOwn(MAP, k)) return true;
  if (VARS.indexOf(k) >= 0) return true;
  return SBK_OK[k.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()] === 1;
 }

 /* 硬约束 20 / §9：实测 [data-chat="root"] 带【内联】style：
    --chat-viewport-height:1205px; background-image:url(https://r2.aitchat.org/…)
   内联样式优先级高于任何选择器特异度 → 换页面背景【必须 !important】。
   这是全基座唯一需要 !important 的地方；其余 --chat-* 变量靠 (0,2,0) 特异度即可，不加。
   ⚠ 只改 --chat-bg 换不掉背景图：内联写的是 background-image 属性本身，不是变量。 */
 var PAGE = {
  pageBg: 'background-color', pageBgImage: 'background-image',
  pageBgSize: 'background-size', pageBgPosition: 'background-position',
  pageBgRepeat: 'background-repeat'
 };

 function decls(tokens) {
  var out = '', k, v, prop;
  for (k in tokens) {
   if (!hasOwn(tokens, k)) continue;
   if (!okToken(k)) { SBK.warn('bad token: ' + k); continue; }
   v = tokens[k];
   if (v === null || v === undefined || v === '') continue;
   v = String(v);
   // 危险值（截断样式块 / 外部资源 / 多写声明）一律丢弃并告警，见 DANGER 注释
   if (DANGER.test(v)) { SBK.warn('bad token value: ' + k); continue; }
   prop = PAGE[k];
   if (prop) { out += prop + ':' + v + ' !important;'; continue; }   // 仅此处加 !important
   out += toVar(k) + ':' + v + ';';
  }
  return out;
 }

 /* §7.1 + CSS D 节：平台令牌在 [data-theme=dark]，特异度 (0,1,0)；data-theme 与 data-chat=root
   绑在【同一个 div】上。故写 [data-chat="root"][data-theme="dark"] 得 (0,2,0)，高于平台
   → 深浅色切换不会覆盖回去，且【不需要 !important】。
   只写 [data-theme=dark] 是同特异度靠源顺序取胜（脆）；只写 :root 完全无效。 */
 function sel(mode) { return '[data-chat="root"][data-theme="' + mode + '"]'; }

 function styleNode() {
  // 单节点 + 固定 id，重复调用【替换而非追加】，避免创卡页预览重跑堆积一堆 <style>（§3）
  var root = d.head || d.documentElement, kids = root.childNodes, i, el;
  for (i = 0; i < kids.length; i++) if (kids[i] && kids[i].nodeType === 1 && kids[i].id === STYLE_ID) return kids[i];
  el = d.createElement('style');
  el.id = STYLE_ID;
  root.appendChild(el);
  return el;
 }

 var current = null;   // 最近一次真正写出的合成结果，便于上层回读
 /* 表单和抽屉实现拆到 theme-panel.js；start() 可先于该模块运行，故配置真值留在基础层。 */
 var pc = { title: '\u9605\u8bfb\u8bbe\u7f6e', width: '' };
 function configure(opt) {
  if (opt) {
   if (opt.title) pc.title = String(opt.title);
   if (opt.width) pc.width = String(opt.width);
  }
  return { title: pc.title, width: pc.width };
 }

 /* ================= 单一运行时所有权（审计报告高风险 1） =================
   1.0 有【两条】主题通道：生成器把 config.theme 永久编译进静态 sbk-css，theme.js
   再写 #sbk-theme-vars。后果是 prefs.enabled(false) 只清得掉动态那条，静态覆写还在
   → 「关闭美化＝完全跟随平台」不成立，preset/reset/native 的优先级也不可证明。
   2.1 起【只有本文件写主题】：静态 sbk-css 只装 base.css 骨架，作者基线改由 boot
   载荷下发到这里，与 preset、per-mode overrides 合成同一个 <style>。 */
 var ab = null;    // 作者基线（制作期 config.theme）：{dark:{tokens,tune},light:{…}}
 var nf = false; // apply(null)/'native' 的三态之 native；enabled(true) 会清掉它
 var started = false;      // start/信封只做一次读档，chrome 的第二次 start 幂等

 /* 底层写出器。合成结果 → 单个 <style>。extraCss 走 BRIDGE（字号/行距真值桥）。
   🚨 只有 render() 调它，作者不可见 —— 否则又出现第二个所有者。 */
 function write(tokens, extraCss) {
  var node = styleNode(), css = '', dark, light;
  if (!tokens) {
   // 清空即回到 native。⚠ extraCss 也一并丢弃：native 必须是【真】native（盘点 B.4）
   node.textContent = '';
   current = null;
   SBK.emit('theme', mode());
   return;
  }
  if (tokens.dark || tokens.light) { dark = tokens.dark; light = tokens.light; }
  else { dark = tokens; light = tokens; }
  if (dark) css += sel('dark') + '{' + decls(dark) + '}';
  if (light) css += sel('light') + '{' + decls(light) + '}';
  if (typeof extraCss === 'string' && extraCss) css += extraCss;
  node.textContent = css;
  current = { dark: dark || null, light: light || null };
  SBK.emit('theme', mode());
 }

 /* 一套模式的 {tokens, tune} 归一化。收三种写法：
    {bg:'#111'}                     → 全当 tokens（1.0 扁平写法）
    {tokens:{…}, tune:{fontSize:15}} → 显式两段（生成器编译风格包用这个）
   tune 是【结构化可微调项】，不是 CSS：prefs.get 要回读 fontSize/lineHeight/opacity，
   若只有 tokens 就得去反解析 'calc(24 * var(--rpx))' 这类任意 CSS —— 那必然出错。
   故编译期就把可微调项以数字形态单独带下来（审计报告 8：非颜色字段回读忽略 preset 值）。 */
 function pack2(o, safe) {
  var r = { tokens: {}, tune: {} }, k, v;
  if (!o || typeof o !== 'object') return r;
  function put(t, k, v) {
   var bad = t === 'tokens' ? !okToken(k) || v === null || v === undefined || v === '' || DANGER.test(String(v)) : !FMAP[k] || !okField(k, v);
   if (safe && bad) { SBK.warn('bad author ' + t + ': ' + k); return; }
   r[t][k] = v;
  }
  if (hasOwn(o, 'tokens') || hasOwn(o, 'tune')) {
   if (o.tokens && typeof o.tokens === 'object') {
    for (k in o.tokens) if (hasOwn(o.tokens, k)) put('tokens', k, o.tokens[k]);
   }
   if (o.tune && typeof o.tune === 'object') {
    for (k in o.tune) if (hasOwn(o.tune, k)) put('tune', k, o.tune[k]);
   }
   return r;
  }
  for (k in o) if (hasOwn(o, k)) { v = o[k]; put('tokens', k, v); }
  return r;
 }

 /* 把任意「包」写法拆成两套模式。缺一侧【不补另一侧】：那会让「切到浅色整卡失效」
   变成「切到浅色拿到深色配色」，一样是坏的，且更难发现。register() 会直接拒绝单侧包；
   ab 走的是旧配置兼容路径，扁平写法本就是「两套同值」，故此处照旧展开。 */
 function spread(def) {
  if (!def || typeof def !== 'object') return null;
  if (hasOwn(def, 'dark') || hasOwn(def, 'light')) {
   return { dark: pack2(def.dark, true), light: pack2(def.light, true) };
  }
  var one = pack2(def, true);
  return { dark: one, light: one };
 }

 /* apply(x) —— 对外仍是 1.0 的单参语义，但语义所有权变了：它设的是【作者基线】，
   不再是「最终覆写」。基线之上还会叠 preset 与玩家 overrides，由 render() 统一合成。
    apply({bg:'#111'})                     → 基线两套同值
    apply({dark:{…},light:{…}})            → 基线分两套
    apply({v:2,base:…,presets:…,preset:…}) → boot 信封（生成器下发，见 build_sbk.py）
    apply(null) / apply('native')          → 三态之 native：撤掉全部覆盖，真跟随平台 */
 function apply(x) {
  if (!x || x === 'native') { nf = true; boot1(); render(); return; }
  if (typeof x === 'object' && x.v === 2 && (hasOwn(x, 'base') || hasOwn(x, 'presets'))) {
   envelope(x);
   return;
  }
  nf = false;
  ab = spread(x);
  boot1();
  render();
 }

 /* boot 信封。core.js 的 boot 只会做 `if (o.theme) SBK.theme.apply(o.theme)`，而
   WP-2 不改 core.js → 风格包与默认包名只能【搭这趟车】进来。信封形状自带 v:2 与
   base/presets 两个判别键，与 1.0 的 {dark,light}/扁平写法不会混淆。
   🚨 这也正是「主题初始化与 chrome 解耦」的落点：生成器【总是】下发非空信封，
    故 modes.chrome 无论真假，boot 都会走到这里并把主题层 start 一次。 */
 function envelope(e) {
  var k, ps = e.presets, wasStarted = started;
  if (ps && typeof ps === 'object') {
   for (k in ps) if (hasOwn(ps, k)) regOne(k, ps[k]);
  }
  nf = false;
  ab = hasOwn(e, 'base') && e.base ? spread(e.base) : null;
  /* 作者默认只在首次启动前采纳。started 后的重复 apply(envelope) 属预览重跑/重配置，
    不能把玩家已选择的 preset 拉回作者默认，也不能让 presetName 与 prefs.preset 分叉。 */
  if (!wasStarted && typeof e.preset === 'string' && e.preset && hasOwn(PRESETS, e.preset)) {
   presetName = e.preset;
  }
  boot1();
  render();
 }

 /* 只读一次档。start 与信封都调它；chrome 的第二次 start 因此不会重新 sane() 存档，
   更不会用一个空的 resolve 结果把已生效的主题覆盖掉（幂等要求）。 */
 function boot1() {
  if (started) return false;
  started = true;
  load();
  return true;
 }

 /* mode() 读当前平台深浅色。
   ⚠ SDK 没有暴露读主题的方法，且 theme:change 有去重（值真变才派发，初值就是 dark），
    所以初始主题【只能从 DOM 读】，不能等事件。 */
 function mode() {
  var root = d.querySelector('[data-chat="root"]');
  var v = root && root.getAttribute ? root.getAttribute('data-theme') : null;
  return v === 'light' ? 'light' : 'dark';
 }

 function onChange(fn) {
  if (typeof fn !== 'function') return function () {};
  SBK.on('theme', fn);
  try { fn(mode()); } catch (e) { SBK.warn('theme.onChange initial call threw'); }  // 初值不派发，手动补一次
  return function () { SBK.off('theme', fn); };
 }

 /* §9 深色主题实测真值（探针读 getComputedStyle 所得，14 个变量全部存在）。
   供作者「微调而非全替」时作基线：SBK.theme.apply(SBK.theme.base()) 再改几项。
   ⚠ 三个背景实测同色（页面/用户气泡/AI 气泡均 #17181a）→ 想做气泡与页面分层必须自己拉开对比。 */
 var DARK = {
  bg: '#17181a', surface: '#1e1f24', text: '#fff', muted: '#c5c5c5',
  border: '#333', accent: '#ff6d97',
  userBubble: '#17181a', aiBubble: '#17181a', bubbleText: '#fff',
  inputBg: '#1e1f24', inputText: '#fff', shortcutText: '#fff',
  moreItemBg: '#2c2e32', sharePick: '#2c2e32'
 };

 /* ================= preset + overrides 两层合成（2.0 §4 / 盘点 B.5） =================
   1.0 的 theme.js 是【无状态涂色器】：apply 写一个 <style>，current() 只回读入参，
   玩家改了什么、刷新后还在不在、怎么与作者 preset 合成 —— 完全没有这一层。

   🚨 合成纪律（盘点 B.5 第 1 条，最容易做错且代价很大）：
    resolved(mode) = PRESET[name][mode] + overrides[mode]
    preset 默认值【只存在于源码，绝不写入偏好】。每次都按「当前版本的 preset +
    合法 overrides」重新合成 → 作者升级 preset 后，新默认能作用到玩家【从未改过】的字段。
    若把 preset 快照进存档，玩家的旧快照会永久钉死旧默认值。
   🚨 overrides.dark 与 overrides.light 【分开存】，切换不串值（盘点 B.5 第 3 条）。
   🚨 写回默认值时【删除】该 override，而不是存一份等于默认的值（第 2 条）——
    否则同上，这个字段就再也跟不上 preset 升级了。 */

 /* 作者预置的风格包。key 是包名，值是 {dark:{…},light:{…}} 或扁平（两套同值）。
   ⚠ 盘点 E.3：平台强制两套主题都存在（用户随时可能切），所以风格包【必须两侧都备】。
    只给一侧时另一侧回落到平台原生令牌，会出现「切到浅色整卡失效」。 */
 var PRESETS = {};
 var presetName = '';

 /* 包名：非空、运行安全。允许中日韩汉字与 ASCII 字母数字 空格 _ - ，长度 1..32。
   🚨 包名会进 <option> 文本、进存档、进 select.value：放开引号/尖括号/反斜杠没有好处，
    且 §5.5 净化面前多一类可疑输入就多一个静默失败面。 */
 var NAME_OK = /^[0-9A-Za-z_\-\u3040-\u30ff\u4e00-\u9fa5][0-9A-Za-z_\- \u3040-\u30ff\u4e00-\u9fa5]{0,31}$/;

 /* 单个包的注册 + 全量校验 → boolean。
   四道闸门：① 名称；② dark/light 【都】显式完整；③ 令牌名在白名单内；④ 值不危险。
   ⚠ ② 是盘点 E.3：平台强制两套主题都存在（玩家随时可能切），单侧包切过去会整卡失效。
    这里不做「缺一侧就补另一侧」的善后 —— 那只会把「失效」换成「浅色下显示深色配色」。 */
 function regOne(name, def) {
  var norm, m, i, t, k, v, n, mode2 = ['dark', 'light'];
  function bad(s) { SBK.warn('bad preset: ' + s); return false; }
  if (typeof name !== 'string' || !NAME_OK.test(name)) {
   return bad('bad preset name ' + JSON.stringify(name));
   }
  if (!def || typeof def !== 'object') {
   return bad(name + ' needs an object');
   }
  if (!hasOwn(def, 'dark') || !hasOwn(def, 'light') || !def.dark || !def.light) {
   // 扁平写法在 register 这条路上【不接受】：风格包必须逐侧明确表态，不靠「两套同值」蒙过
   return bad(name + ' needs dark/light');
   }
  norm = { dark: pack2(def.dark), light: pack2(def.light) };
  for (i = 0; i < 2; i++) {
   m = mode2[i];
   t = norm[m].tokens;
   n = 0;
   for (k in t) {
    if (!hasOwn(t, k)) continue;
    n++;
    if (!okToken(k)) {
     return bad(name + '.' + m + ' unknown token ' + k);
    }
    v = t[k];
    if (v === null || v === undefined || v === '') {
     return bad(name + '.' + m + '.' + k + ' is empty');
    }
    if (DANGER.test(String(v))) {
     return bad(name + '.' + m + '.' + k + ' has dangerous value');
    }
    }
   if (!n) {
    return bad(name + '.' + m + ' has no tokens');
    }
   // tune 只收 FIELDS 里的可微调项，且必须过 okField —— 脏 tune 会让 get() 回读出界
   t = norm[m].tune;
   for (k in t) {
    if (!hasOwn(t, k)) continue;
    if (!FMAP[k] || !okField(k, t[k])) {
     return bad(name + '.' + m + '.tune.' + k + ' invalid');
     }
    }
   }
  PRESETS[name] = norm;
  /* 🚨 重注册【当前生效的】包必须重画：否则 prefs.get/resolved 已经回读新默认，
    屏幕上还是旧值 —— 读 API 与 DOM 分叉，是最难查的一类不一致。
    ⚠ 只在已 start 过之后才画：boot 信封是「先 regOne 再 boot1」的顺序，
     那时 started 还是 false，不该在读档之前就落地一次半成品。 */
  if (started && name === presetName) render();
  return true;
  }

 /* 玩家微调字段表。ui.js 直接 for 这张表建控件 —— 控件清单的【唯一真源】在这里，
   不在 ui.js，这样加一个微调项只改本文件一处。
   🚨 语义漂移（2.0 §4.1 / 盘点 B.3）：这里【没有】「日间/夜间/原生」三按钮。
    旧三态 day/night 由玩家选；沙盒的 light|dark 是【平台级】，作者只能读 data-theme
    与跟随 theme:change，【写不动】。玩家按了也切不动 → 放上去就是坏控件。
    取代物是「风格包选择」（作者预置多套，玩家挑）+「启用美化」开关（对应旧 native）。
   tone: 落到哪个语义 token（toVar 再翻成 --chat-* / --sbk-*）；null = 需要特殊桥接。 */
 /* 🚨 fontSize 在 2.1 从 rpx 改成【CSS px】（审计报告 8 / 美化决策「尺寸」）：
    --rpx = calc(100vw / 750) 是平台的【等比】基准，布局节奏用它是对的；但玩家调的
    「字号」是可读性绝对尺度，跟着视口等比缩放会两头翻车 ——
     · 实测 323px 视口下旧默认 24rpx ≈ 10px（小到几乎不能读）；
     · 反过来宽屏（如 900px）同一个 24rpx ≈ 30px，大到破版。
    故 tone 'fs' 现在写 <n>px 真值。lineHeight 继续无单位（比例量，本就与视口无关）。 */
 var FIELDS = [
  { key: 'fontSize', label: '字号', kind: 'int', min: 12, max: 22, step: 1, def: 14, unit: 'px', tone: 'fs' },
  { key: 'lineHeight', label: '行距', kind: 'num', min: 1.1, max: 2.6, step: 0.1, def: 1.5, tone: 'lh' },
  { key: 'textColor', label: '正文色', kind: 'color', tone: 'text' },
  { key: 'accentColor', label: '强调色', kind: 'color', tone: 'accent' },
  { key: 'aiBubbleColor', label: '气泡色', kind: 'color', tone: 'aiBubble' },
  { key: 'opacity', label: '气泡透明度', kind: 'int', min: 40, max: 100, step: 1, def: 100, unit: '%', tone: null }
 ];
 var FMAP = {};
 (function () { for (var i = 0; i < FIELDS.length; i++) FMAP[FIELDS[i].key] = FIELDS[i]; })();

 /* 逐字段验证（盘点 B.6：规则整体照抄，只换载体）。
   它防的是「玩家存档被改坏 → 整卡起不来」，与平台无关 —— 所以非法值一律
   【逐字段丢弃并回落默认】，绝不让 bootstrap 失败（B.5 第 5 条）。 */
 var HEX = /^#[0-9a-fA-F]{6}$/;
 function okField(k, v) {
  var f = FMAP[k];
  if (!f) return false;                                     // 未知键：拒
  if (f.kind === 'color') return typeof v === 'string' && HEX.test(v);   // 严格 #RRGGBB
  if (typeof v !== 'number' || !isFinite(v)) return false;
  if (f.kind === 'int' && v !== Math.floor(v)) return false;
  return v >= f.min && v <= f.max;                          // 越界：拒（不夹取，回落默认更可预期）
 }

 /* 偏好文档。schema 版本化：日后改字段语义时按 v 迁移，而不是让旧存档静默错解。
   v1 → v2：fontSize 的【单位与量纲变了】（rpx → CSS px）。 */
 var SCHEMA = 2;
 var prefs = { v: SCHEMA, preset: '', on: true, ov: { dark: {}, light: {} } };

 /* v1 存档的 fontSize 迁移。
   🚨 绝不能把 24 直接当 24px 用：v1 的 24 是 rpx，实测 323px 视口下 ≈10px，
    直接改读作 24px 是【放大 2.4 倍】，玩家一升级就整卡破版。
   换算依据：--rpx = 100vw/750，即 1rpx = 视口宽/750。取 750 设计稿的常见参照宽
   375px（iPhone 基准）→ 1rpx ≈ 0.5px，故 px ≈ rpx / 2：
     v1 默认 24rpx → 12px      v1 上限 32rpx → 16px      v1 下限 12rpx → 6px
   换算后再【夹取】进 v2 的 12..22（而不是丢弃回落默认）：夹取保住「玩家原本想要偏小
   还是偏大」的意图，v1 下限那种 6px 夹到 12px 只是回到可读下限，不会突然变大。
   ⚠ 这条是有意与 okField 的「越界即拒」不同：那条防的是脏存档，这条是版本迁移。 */
 var V1_RPX_PER_PX = 2;
 function migrateFontSize(v) {
  var f = FMAP.fontSize, n;
  if (typeof v !== 'number' || !isFinite(v)) return null;
  n = Math.round(v / V1_RPX_PER_PX);
  if (n < f.min) n = f.min;
  if (n > f.max) n = f.max;
  return n;
  }

 /* 🚨 存档载体复用 SBK.store（core.js 已实现的三级降级链 save → cache → 内存），
    【绝不另写一套存储】。但 store 只有一个可变 KEY + 800ms 尾部合并写：
    为它临时改 key 会与业务写入抢同一次 flush（写错 key）。
   → 故偏好挂在【状态仓的保留字段】 _sbkTheme 上：store.save() 缺参时存 state.get()，
    于是业务存档与偏好天然同文档、同一次写入，既不抢 key 也不会互相覆盖。
   ✅ 安全性已核对 hud.js pick()：`k.charAt(0) === '_'` 的键被视为内部字段【不渲染】，
    所以这个保留字段不会漏进状态面板。 */
 var SKEY = '_sbkTheme';

 function sane(raw) {
  // 逐字段降级：脏存档（字号 999 / 强调色 '"; drop' / 未知键 / __proto__）只丢该字段，不炸整卡
  var p = { v: SCHEMA, preset: '', on: true, ov: { dark: {}, light: {} } }, i, m, src, dst, k, n, v;
  if (!raw || typeof raw !== 'object') return p;
  // v 缺失/非数字按 1 处理：1.0 写出的存档里确实有 v:1，但脏档也可能整个丢了这个键
  var ver = typeof raw.v === 'number' && isFinite(raw.v) ? raw.v : 1;
  if (typeof raw.preset === 'string' && hasOwn(PRESETS, raw.preset)) p.preset = raw.preset;
  if (typeof raw.on === 'boolean') p.on = raw.on;             // 严格 boolean，非 boolean 回落 true
  for (i = 0; i < 2; i++) {
   m = i ? 'light' : 'dark';
   src = raw.ov && typeof raw.ov === 'object' ? raw.ov[m] : null;
   if (!src || typeof src !== 'object') continue;
   dst = p.ov[m];
   // 只走 FIELDS 白名单：__proto__ / constructor / 未知键都不在表里，天然进不来
   for (n = 0; n < FIELDS.length; n++) {
    k = FIELDS[n].key;
    if (!hasOwn(src, k)) continue;
    v = src[k];
    // v1 → v2 迁移：fontSize 单位从 rpx 变 px，必须换算+夹取，不能照搬也不能丢
    if (ver < 2 && k === 'fontSize') {
     v = migrateFontSize(v);
     if (v === null) { SBK.warn('bad pref: ' + m + '.' + k); continue; }
     SBK.log('theme pref migrated: ' + m + '.fontSize ' + src[k] + 'rpx → ' + v + 'px');
    }
    if (okField(k, v)) dst[k] = v;
    else SBK.warn('bad pref: ' + m + '.' + k);
   }
  }
  return p;
 }

 function hex2rgb(v) {
  return parseInt(v.slice(1, 3), 16) + ',' + parseInt(v.slice(3, 5), 16) + ',' + parseInt(v.slice(5, 7), 16);
 }

 /* ---------- 三层合成：author base → preset → per-mode overrides ----------
   🚨 合成纪律（盘点 B.5 第 1 条）：preset 与 author base 每次都从【当前源码/当前配置】
    现取，绝不写入偏好存档。只有 overrides 落盘 → 作者升级风格包后，新默认能自动
    作用到玩家【从未改过】的字段。 */

 /* 不含 overrides 的基线令牌（author base 叠 preset）。set() 的「等于默认即删除」
   与 prefs.get 的回读都以它为准 —— 两处必须是同一个真源，否则契约会互相打脸。 */
 function baseOf(m, part) {
  var out = {}, i, srcs = [], p = PRESETS[presetName], k, t;
  if (ab && ab[m]) srcs.push(ab[m][part]);
  if (p && p[m]) srcs.push(p[m][part]);            // preset 后叠 → 覆盖作者基线
  for (i = 0; i < srcs.length; i++) {
   t = srcs[i];
   if (t) for (k in t) if (hasOwn(t, k)) out[k] = t[k];
  }
  return out;
 }
 function baseline(m) { return baseOf(m, 'tokens'); }

 /* 不含 overrides 的可微调项真值（结构化数字，不是 CSS）。同样 author base 后叠 preset。 */
 function tuneOf(m) { return baseOf(m, 'tune'); }

 /* 「等于默认值」的比较口径。
   颜色：#RRGGBB 大小写归一后比 —— 取色器回吐的是小写，作者风格包里常写大写，
      不归一会让 '#FFF000' 与 '#fff000' 判成不同，override 永远删不掉。
   数字：按字段 step 的一半作容差。lineHeight 的 0.1 步进经 parseFloat 往返会出现
      1.2000000000000002 这类浮点噪声，=== 比较必然漏判（然后同样删不掉）。
      整数字段 step=1，容差 0.5，仍是精确判等（合法值本就是整数）。 */
 function sameAsDefault(k, v, m) {
  var f = FMAP[k], d = defaultOf(k, m);
  if (!f || d === undefined || d === '') return false;
  if (f.kind === 'color') return String(v).toLowerCase() === String(d).toLowerCase();
  if (typeof v !== 'number' || typeof d !== 'number') return false;
  return Math.abs(v - d) < (f.step || 1) / 2;
 }

 /* 某字段在【不含当前 override】时的默认值 —— set() 的删除判据、get() 的回读来源。
   顺序：preset/base 的对应值 → 字段默认。颜色从 tokens 取（须是可比的 #RRGGBB），
   非颜色从 tune 取（fontSize/lineHeight/opacity 都在这里，不再无视 preset）。 */
 function defaultOf(k, m) {
  var f = FMAP[k], v;
  if (!f) return undefined;
  if (f.kind === 'color') {
   v = baseline(m)[f.tone];
   return HEX.test(String(v || '')) ? String(v).toLowerCase() : '';
   }
  v = tuneOf(m)[k];
  return okField(k, v) ? v : f.def;
  }

 /* 合成一套模式的最终令牌 = baseline + overrides。 */
 function resolve(m) {
  var out = baseline(m), ov = prefs.ov[m] || {}, tune = tuneOf(m), i, f, v, c, op;
  for (i = 0; i < FIELDS.length; i++) {
   f = FIELDS[i];
   if (f.key === 'opacity') continue;                        // 与气泡色联合处理，见下
   v = hasOwn(ov, f.key) ? ov[f.key] : tune[f.key];          // override 优先，其次 preset/base 的 tune
   if (f.kind === 'color') { if (hasOwn(ov, f.key)) out[f.tone] = ov[f.key]; continue; }
   if (!okField(f.key, v)) continue;                         // 没值/脏值 → 不写该令牌，交给 base.css 的默认
   /* 🚨 字号写【CSS px 真值】而不是 calc(n * var(--rpx))：--rpx 等比缩放会让
     同一个数字在 323px 视口上 ≈10px、在宽屏上 ≈30px（审计报告 8）。 */
   out[f.tone] = f.unit === 'px' ? v + 'px' : v;
  }
  // 气泡透明度：平台三个背景令牌实测同色（§9），拉不开层次 → 色 + 透明度合成 rgba
  op = hasOwn(ov, 'opacity') ? ov.opacity : tune.opacity;
  if (okField('opacity', op) && op !== 100) {
   c = hasOwn(ov, 'aiBubbleColor') ? ov.aiBubbleColor : baseline(m).aiBubble;
   if (HEX.test(String(c || ''))) out.aiBubble = 'rgba(' + hex2rgb(c) + ',' + (op / 100) + ')';
  }
  return out;
 }

 /* 字号/行距桥：令牌覆盖只能改 var()，而 base.css 的 .sbk-host 写的是
   font-size:var(--sbk-fs,14px) 与 line-height:1.5 —— 后者是【真值】，不桥就调不动。
   选择器带 [data-chat="root"] 祖先 → (0,2,0) 压过 base.css 的 .sbk-host (0,1,0)，
   无需 !important。两条都带回落值，令牌缺失时仍是可读默认。
   🚨 必须【同时】作用 .sbk-host 与 .sbk-snap（审计报告 8）：1.0 只桥了行距、且字号只
    落在 .sbk-host 上，于是玩家调字号时功能栏跟着变、气泡内状态面板【完全不动】。
    .sbk-snap 是气泡内面板的根，它不是 .sbk-host 的后代（挂在平台气泡里），继承不到。 */
 var BRIDGE = '[data-chat="root"] .sbk-host,[data-chat="root"] .sbk-snap' +
  '{font-size:var(--sbk-fs,14px);line-height:var(--sbk-lh,1.5)}';

 /* 唯一的落地口。三态：nf / 停用美化 → 真 native；否则合成三层。 */
 function render() {
  // 「停用美化」= 旧 native：撤销全部覆盖，完全跟随平台（沙盒下 textContent='' 是【真】native）
  // 🚨 单一所有权的兑现点：静态 sbk-css 里已经没有 theme 覆写了，所以清空【真的】等于跟随平台。
  if (nf || !prefs.on) { write(null); return; }
  write({ dark: resolve('dark'), light: resolve('light') }, BRIDGE);
 }
 function applyPrefs() { render(); }        // 1.0 内部名，保留以免上层引用漂移

 function persist() {
  /* 主题只拥有 `_sbkTheme` 这一枚顶层键，不能把当前 state 当成完整存档覆盖业务文档。
    store.merge 在内核的同一 800ms 队列里与业务 save 合成，一次落盘且不丢任何一方。 */
  var p = pack();
  try {
   SBK.state.patch(p);                      // 保留运行时偏好，切会话时 `_sbk*` 不清
   if (SBK.store && typeof SBK.store.merge === 'function') SBK.store.merge(p);
   else SBK.warn('theme prefs: store.merge unavailable');
  } catch (e) { SBK.warn('theme persist failed', e && e.message); }
 }
 function pack() { var o = {}; o[SKEY] = prefs; return o; }

 function load() {
  /* 🚨 硬约束 18 / §4.4a：瘦预览下 save.get / save.keys 【同步抛 SdkError】。
    store.load() 内部已 try/catch 并返回 null，这里【再兜一层】——
    降级到 cache/内存后仍要保证「取不到偏好」只是回默认，绝不炸整卡。 */
  var doc = null;
  try { doc = SBK.store.load(); } catch (e) { SBK.warn('theme load failed; defaults', e && (e.code || e.message)); }
  prefs = sane(doc && typeof doc === 'object' ? doc[SKEY] : null);
  if (prefs.preset) presetName = prefs.preset;
  return prefs;
 }

 /* 对外的偏好 API。ui.js 只认这一层，不自己碰存储与合成。 */
 var prefsApi = {
  fields: function () { return FIELDS.slice(); },
  field: function (k) { return FMAP[k] || null; },
  presets: function () { return Object.keys(PRESETS); },
  preset: function (name) {
   if (name === undefined) return presetName;
   if (name && !hasOwn(PRESETS, name)) { SBK.warn('unknown preset: ' + name); return presetName; }
   presetName = name || '';
   prefs.preset = presetName;
   applyPrefs(); persist();
   return presetName;
    },
  enabled: function (v) {
   if (v === undefined) return prefs.on;
   prefs.on = !!v;
   /* 🚨 重新开启必须真的恢复 author base / preset / overrides：nf 是
     apply(null) 留下的粘滞态，不清掉的话「开关关了再开」会停在 native（假恢复）。 */
   if (prefs.on) nf = false;
   render(); persist();
   return prefs.on;
    },
  get: function (k, m) {
   /* 回读顺序：override → 当前 resolved preset/base 的对应值 → 字段默认。
     🚨 1.0 的非颜色分支直接 return f.def，无视 preset（审计报告 8）：作者把风格包
      字号定成 16，面板却显示 14，玩家一动控件字号就跳一下。fontSize/lineHeight/
      opacity 现在都从结构化 tune 取，不去反解析任意 CSS。 */
   var mm = m || mode(), ov = prefs.ov[mm] || {}, f = FMAP[k];
   if (hasOwn(ov, k)) return ov[k];
   if (!f) return undefined;
   return defaultOf(k, mm);
    },
  /* set(k,v,mode)
    🚨 override 升级契约（盘点 B.5 第 2 条 / 审计报告 2）：写回的值若【等于不含当前
     override 的 resolved preset/base 默认值】，就【删除】这个 override，而不是存一份
     等于默认的值。否则该字段从此钉死，作者升级风格包时再也跟不上新默认。
     1.0 文档写了这条，代码却无条件保存 —— 这次真做出来。 */
  set: function (k, v, m) {
   var mm = m || mode(), f = FMAP[k];
   if (!f) { SBK.warn('unknown theme pref: ' + k); return false; }
   if (!okField(k, v)) { SBK.warn('invalid theme pref value rejected: ' + k + '=' + v); return false; }
   prefs.ov[mm] = prefs.ov[mm] || {};
   if (sameAsDefault(k, v, mm)) delete prefs.ov[mm][k];
   else prefs.ov[mm][k] = f.kind === 'color' ? String(v).toLowerCase() : v;
   render(); persist();
   return true;
    },
  /* 重置当前主题：删【当前模式】的 overrides（盘点 B.5 第 4 条）。
    另一侧不动 —— 两套 overrides 分开存，切换不串值。 */
  reset: function (m) {
   var mm = m || mode();
   prefs.ov[mm] = {};
   applyPrefs(); persist();
  },
  /* 全部恢复默认：清两套 overrides，但【保留】preset 与 on
    （对位旧协议「保留 mode 与 normalizeQuotes」：用户要的是清微调，不是退出美化）。 */
  resetAll: function () {
   prefs.ov = { dark: {}, light: {} };
   applyPrefs(); persist();
  },
  load: load,
  resolved: function (m) { return resolve(m || mode()); },
  raw: function () { return sane(prefs); },             // 副本，外部改不到内部状态
 };

 SBK.theme = {
  apply: apply,
  /* 注册风格包。register('名', {dark:{…},light:{…}}) → boolean；
    register({名:包, …}) 批量 → {名:boolean, …}。
    ⚠ 只登记不生效：生效要 prefs.preset('名')，或由 boot 信封的 preset 指定。
    🚨 校验不通过【不注册】并返回 false：一个残缺的包注册进去，玩家在面板里挑到它
     就是坏控件（切过去半边失效），比「它压根不出现在列表里」糟得多。 */
  register: function (name, def) {
   var out, k;
   if (name && typeof name === 'object') {
    out = {};
    for (k in name) if (hasOwn(name, k)) out[k] = regOne(k, name[k]);
    return out;
   }
   return regOne(name, def);
    },
  prefs: prefsApi,
  /* 读存档 + 合成 + 落地，一步到位。ui.chrome 与 boot 都走它，重复调用无副作用
    （load 每次重新 sane()，applyPrefs 是替换同一个 <style> 的 textContent）。
    ⚠ 只写 <head> 里的 <style>，不碰气泡/功能栏 → 不受硬约束 17 限制，顶层可调。 */
  start: function (name, opt) {
   /* 🚨 幂等（本轮硬要求）：boot 信封已经 start 过一次，ui.chrome.build() 还会再调一次。
     第二次【不得】重新读档、不得用入参把玩家已生效的包名顶掉、更不得空 resolve 覆盖。
     做法：入参包名只在【还没有生效包名】时采纳；读档由 boot1() 的哨兵挡住第二次。 */
   configure(opt);
   var first = boot1();          // 首次才 load()；load 里存档的 preset 会覆盖 presetName
   if (typeof name === 'string' && name && !presetName && hasOwn(PRESETS, name)) {
    // 存档里没挑过包才用入参当默认（玩家挑过就尊重玩家）
    presetName = name;
    prefs.preset = name;
   }
   if (first || !current) render();   // 第二次且已有产物 → 不重画，避免任何覆盖风险
   return prefsApi;
    },
  mode: mode,
  onChange: onChange,
  vars: function () { return VARS.slice(); },         // 14 个平台后缀名，供 WP-4 校验
  tokens: MAP,                                        // 语义名 → 平台后缀
  page: PAGE,                                         // 需 !important 的页面级属性名
  base: function () { var r = {}, k; for (k in DARK) r[k] = DARK[k]; return r; }, // 实测深色基线副本
  current: function () { return current; },
  /* 作者基线回读（制作期 config.theme 经 boot 信封下发的那份），便于实机自查
    「主题到底是谁在写」。返回内部对象的浅副本，外部改不到合成结果。 */
  author: function () {
   var r = {}, i, m = ['dark', 'light'], k, s;
   if (!ab) return null;
   for (i = 0; i < 2; i++) {
    s = ab[m[i]];
    if (!s) continue;
    r[m[i]] = { tokens: {}, tune: {} };
    for (k in s.tokens) if (hasOwn(s.tokens, k)) r[m[i]].tokens[k] = s.tokens[k];
    for (k in s.tune) if (hasOwn(s.tune, k)) r[m[i]].tune[k] = s.tune[k];
   }
   return r;
  },
  reset: function () { apply(null); },
  /* 单一所有权自证：产物里【只有】本文件写的这一个 <style> 承载主题。
    WP-3 的仿真回归可以据此断言「静态 sbk-css 里不含 [data-theme=…] 覆写块」。 */
  styleId: STYLE_ID
 };
 /* theme-panel.js 只通过这条窄桥拿字段快照、表单刷新订阅与抽屉配置；偏好读写仍走公开 API。 */
 SBK._themeKit = {
  configure: configure,
  onChange: onChange
 };
 SBK.log('theme ready');
})(typeof window !== 'undefined' ? window : globalThis);
