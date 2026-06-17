# 当前MMD平台技术规范（支持 `<script>`、ES6）

> 本文档描述当前版本MMD（魅魔岛/sexyai.top）。以下为**实测结论**（逐语法/逐写法独立探针 + 真实多轮对话验证），非推断。
> 旧版 MMD 已冻结、不再更新；当前 MMD 仍在迭代，本文档随实测更新。未实测的能力（MVU/STScript/酒馆助手等）仍按无处理（保守）。

## 与旧版的差异（全部已实测）

| 项目 | 旧版 | 当前版 | 状态 |
|---|---|---|---|
| `<script>` 标签 | ❌ 被剥离 | ✅ 可执行，但**只能定义 `window.__fn` 供 onclick 调，做不了 per-message 自渲染** | 已实测 |
| ES6+ 语法 | ❌ ES5 only | ✅ 全支持（img onerror 载体下，7/7 探针全绿），**推荐 ES6** | 已实测 |
| `onerror` 多行 / 双引号 | ❌ 单行 only、须单引号 | ✅ 可多行、可用双引号，代码可写干净 | 已实测 |
| `onclick` 净化 | 放行极简单行赋值 | **收紧**：只放行"干净调用/引用表达式"，禁代码字面量与直接DOM赋值 | 已实测 |
| 正则总数上限 | 30 条 | **130 条** | 已实测 |
| findRegex/replaceString 上限 | 1000 / 20000 | 同旧版 1000 / 20000 | 已确认 |
| 角色卡导入 | 仅 chara_card_v2 | 同旧版（仅v2，不识别v3） | 已确认 |
| 原生 KV `$field` 状态栏 | — | ✅ 平台内置（`【状态】hp::85【/状态】` → 替换里用 `$hp`，纯HTML零JS） | 官方文档 |
| MVU/STScript/酒馆助手 | ❌ | ❌ 按无处理 | 保守 |

---

## 1. ES6 能力（实测全支持，img onerror 载体下）

逐语法独立探针，7/7 全部可用、结果正确：

| 语法 | 示例 | 结果 |
|---|---|---|
| 箭头函数 | `[1,2,3].map(x=>x*2)` | ✅ |
| let / const | `const a=10;let b=20` | ✅ |
| 模板字符串 | `` `你好-${n}` `` | ✅ |
| 解构赋值 | `const {p,q}=o` | ✅ |
| 展开运算符 | `[...a,...b]` | ✅ |
| 可选链 | `o?.a?.b` | ✅ |
| ES5 基准 | `[1,2,3].join('-')` | ✅ |

**结论**：旧版"遇到 `=>` 从该处截断、ES5 only"的限制在当前版**已不存在**。新写引擎/交互代码**推荐 ES6**——同一功能代码更短、可读可改、bug 更少。前提：以上在 `img onerror` 载体内测得。

ES6 在卡片里的典型用法（纯写法糖，逻辑能力与 ES5 等价）：
- 展开运算符做不可变更新：`const next = { ...上一轮状态, 好感: 上一轮状态.好感 + 3 }`
- 模板字符串拼 HTML：`` `好感 ${cur}/${max}` ``
- 解构 + 可选链安全取值：`const 好感 = 数据?.npc?.好感 ?? 0`
- 箭头 + map/filter 渲染在场角色：`在场.filter(n=>n).map(name=>建角色卡(name))`

---

## 2. `onerror` 已彻底解放（实测）

| 写法 | 旧版 | 当前版 |
|---|---|---|
| 单行 `onerror` | ✅ | ✅ |
| 多行 `onerror`（属性值带换行） | ❌ | ✅ 可用 |
| 属性内双引号（`onerror='...'` 内用 `"`） | ❌ | ✅ 可用 |

`onerror` 内代码可写成正常多行函数、随意用双引号。这是当前版对引擎作者最实在的提效——复杂状态栏从"全挤一行、只能单引号的天书"变成"人能手写手改的正常代码"。

> 🚨 **真红线：onerror="" 内部禁裸双引号（2026-06-17 浏览器+MMD 实机三组对照确认）**。`onerror="..."` 双引号包裹时，内部 JS 任何 `"` 会提前闭合属性 → 后段 JS 拆成无效裸属性 → img 结构破坏 → 引擎不绑定 → **面板静默不渲染（不爆代码但完全不显示）**。修法：内部字符串全用单引号；注入的配置（CFG/CSS）用单引号 JS 字面量序列化，**勿用 `json.dumps`/`JSON.stringify`**（产双引号）。`validate.py` 已检查此项。
>
> ⚠️ **已撤销的伪铁律**：曾误立"onerror 内禁裸 `<`/`>`/`=>`"，后经实机证伪——onerror **引号内**的 `<`/`>` 是纯文本，HTML 属性值不解析标签，**无害**；比较运算/for 循环/箭头函数可正常用。雷达法引擎满是 `i<n`/`c>0` 实战正常即铁证。当初误诊源于把"内部双引号致暴露"错归为"`>` 致暴露"（双引号在更前面已闭合属性，`>` 只是碰巧在暴露文本里）。**教训：单次实机表象易误导，立红线前须做对照实验。**

> 注：JSON 交付层的换行/引号转义仍照旧（`replaceString` 写进 JSON 仍须转 `\n`、`\"`，见 ../output/regex-output.md 2.3）。"onerror 可多行"指的是**渲染到页面后**的 HTML 属性值层面，与 JSON 字符串字面量的合法性是两回事。

---

## 3. `onclick` 放行规则（实测，比旧版收紧）

**核心判据：`onclick` 属性值里只能是"干净的调用/引用表达式"，不能出现代码字符串字面量或直接 DOM 赋值语句。**

| 写法 | 实测 | 说明 |
|---|---|---|
| `onclick="window.__fn()"` | ✅ 放行 | 调用全局函数（官方推荐） |
| `onclick="eval(getElementById('FUNC').dataset.s)"` | ✅ 放行（E1） | 干净的调用表达式；eval 本体未被 CSP 拦，执行了 data-s 里的 DOM 操作 |
| `el.onclick=function(){}`（img onerror 里 JS 赋值绑定） | ✅ 放行 | 净化器只扫 HTML 属性文本，扫不到 JS 赋的 handler |
| `onclick="eval('...代码...')"`（代码字符串塞进属性） | ❌ 净化（E2） | 属性内出现代码字面量，命中净化规则 |
| `onclick="this.x='y'"`（直接 DOM 赋值） | ❌ 不触发 | 赋值语句也算代码，被净化（旧版曾放行极简单行，当前版收紧） |

**两条合法交互路径（当前 MMD 二选一，均已实测）**：
1. **`window.__fn` 全局函数**（官方推荐）：在 `<script>` 或 `img onerror` 里定义 `window.__唯一名 = window.__唯一名 || function(){...}`，按钮写 `onclick="window.__唯一名 && __唯一名()"`。
2. **轻主板 + 胖遥控器**（见 ../platforms/mmd-old.md §5.3，当前 MMD **已复测可用**）：复杂逻辑存进隐藏元素的 `data-s` 属性，`onclick="eval(getElementById('FUNC').dataset.s)"` 只做干净的 eval 调用——正因为踩中"属性内是干净调用、代码在 data-s 里"才放行。

> 雷达引擎的选项按钮一直能点，用的就是路径 ③ `el.onclick=function(){}`（img onerror 里 JS 赋值绑定）——净化器扫不到 JS 赋的 handler。

---

## 4. `<script>` 的能力边界（实测：做不了状态栏）

`<script>` 已解禁可执行，但**做不了 per-message 自渲染**，状态栏引擎仍只能用 `img onerror`。两个原因：

1. **拿不到自身位置**：自渲染引擎依赖 `document.currentScript` 定位，在 MMD 执行模型里不可用；官方所有 script 示例都靠 `window.__fn` + `onclick` 调用，从不自定位。
2. **同段 `<script>` 只加载一次**（官方原文）：状态栏每条消息都带同一份引擎 → 会被去重，不逐条执行 → 整块空白。

**结论**：
- per-message 动态渲染（状态栏引擎）**必须用 `<img onerror>`**——每元素每条触发、`this` 可靠自定位。
- `<script>` 的正确用途：定义 `window.__唯一名` 全局函数，供 `onclick` 调用（选项填输入框、折叠、画廊切图等**交互**）。
- "开放 script"对动态状态栏无帮助，主要价值是让点击类交互能正规写、降低新手门槛。

> 实测反例：把雷达引擎从 img onerror 改成 `<script>` 载体后，状态栏整块空白。

---

## 5. 原生 KV `$field` 状态栏（固定字段的轻量首选）

平台内置 KV 替换，**纯 HTML/CSS、零 JS**，适合**固定字段**：

- 模型按约定输出：`【状态】hp::85;;mood::害羞;;favor::72【/状态】`
- 正则匹配 `/【状态】(.*?)【\/状态】/`，替换内容里直接用 `$hp`/`$mood`/`$favor` 引用字段。
- 规则：第一个捕获括号里同时含 `::` 和 `;;` 时，替换里用 `$字段名` 引用。

**选型**：固定字段（HP/心情/好感等预定义、不增不减）→ 原生 `$field`（最轻）或 KV V4.0（带 HTML 骨架、见 ../beautify/statusbar.md），由 AI 按需择一；**动态字段 / 自创 NPC / 长线复杂数据 → 雷达法**（../beautify/statusbar-radar.md）。

---

## 6. 标签白名单与文字变量（官方文档）

**AI 回复里可用标签**：`div span p a img button style details summary table video input textarea` 等。
**AI 回复里会被删**：`section header footer nav iframe canvas audio form`。开场白限制更少。

> **自定义标签存活（2026-06-17 实测）**：未知自定义标签（如 `<z-live-widget>`）**不在删除名单、实测未被剥离**，白名单对未知标签实际放行。但 `customElements.define()` 须在 `<script>` 里跑、reload 不持久（见 §4），所以**不要依赖 Custom Elements 注册**；要用 Shadow DOM 隔离请走 §6b 的 `img onerror` + `attachShadow` 路线。

**内置文字变量**：
- `{{user}}`（玩家昵称）/ `{{char}}`（角色名）：**仅开场白生效**，AI 回复里不替换。
- `{{random:A::B::C}}`：替换内容里可用，随机显示其一；多个 random 标签各自独立随机。

**选项填输入框选择器**：官方示例用 `document.querySelector('textarea, input[type="text"]')`；雷达引擎用的 `.uni-textarea-textarea` 建议加这层兜底。

---

## 6b. Shadow DOM 状态栏（2026-06-17 实测，隔离型新方案）

8 靶探针实测确认：**`img onerror` 内可对容器调 `attachShadow`，把状态栏 UI 渲进 shadow root，拿到原生隔离**。这是比雷达法更省心的新地基——shadow 内容**完全不过 vditor markdown 管线**，把雷达法一大批防御补丁直接消除。

| 实测项 | 结果 | 意义 |
|---|---|---|
| `<z-live-widget>` 自定义标签 | ✅ 未被白名单剥离（chatIframe 内可见） | 白名单对未知标签实际放行 |
| `img onerror` 里 `attachShadow({mode:'open'})` | ✅ 成功，shadow 内 `<style>`+DOM 正常渲染 | **不需要 `customElements.define`**（那要 script、reload 不持久），纯 onerror 即可拿 Shadow DOM |
| shadow 抗平台重绘 | ✅ 翻页/刷新后 host 与 shadowRoot 仍在；onerror 重新点火走"已有则复用刷新"分支 | 雷达法的防劫持自检/2.5秒重建探针**可省** |
| 🔑 shadow 内 `*害羞*` 星号 | ✅ 原样保留，不被 markdown 吃 | **shadow 内 UI 对 markdown 完全免疫** |

**Shadow DOM 方案对 markdown 陷阱免疫，以下雷达法补丁全部不再需要**：换行空白条（空 `<p>`）、三件套防御 CSS（`p:empty`/`p{margin:0}`/`br{display:none}`）、强制染色注入 MutationObserver 哨兵、CSS 类名冲突（`z-` 前缀）。

**架构（数据留 light + UI 进 shadow）**：
- **数据**：放 light DOM 隐藏 `<span style="display:none">`——实测其 textContent 经 markdown 后一字不差（含 `*`/`|`/`/`），可被后续消息全局扫描做跨轮恢复。**绝不把数据放 shadow 内**（shadow 跨气泡扫不到、且 reload 即失）。
- **载体**：`img onerror`（唯一可靠 per-message 渲染载体，见 §4）。读同气泡 light 数据 + 扫历史 light span 折叠兜底。
- **渲染**：`onerror` 里 `h.shadowRoot || h.attachShadow(...)`（已有则复用，幂等防重影）→ `createElement` 装配进 shadow root。
- **协议**：模型每轮吐**全量快照**（实测 per-message 渲染无跨气泡状态，localStorage 跨气泡读为 NULL，增量+继承不可行）。

**选型补充**：动态/自创 NPC/长线复杂数据 → Shadow DOM 方案（隔离最省心）或雷达法（成熟、示例多）；二者数据恢复地基相同（扫 light span），区别仅在 UI 是否进 shadow。固定字段仍走原生 `$field` / KV V4.0。详见 ../beautify/statusbar-radar.md 与记忆 [[mmd-statusbar-next-gen-design]]。

---

## 7. 正则系统

- **总数 ≤ 130 条**（当前版，旧版 30 已同步提至 130）；findRegex ≤ 1000 字符；replaceString ≤ 20000 字符。
- **findRegex 必须带 `/.../ ` 斜杠分隔符**（2026-06-17 实测铁律）：不带斜杠（如 `\[k=([^\]]+)\]`）时平台正则控制台**测试能过、实际聊天界面不替换**；写成 `/\[k=([^\]]+)\]/` 才生效。交付前务必确认每条 findRegex 带斜杠。
- **正则跑在 markdown(vditor) 之前**：正则替换产出的 HTML 还要再过一遍 markdown 管线（`*x*` 会被吃成斜体）。靠正则直接吐可见文本会被 markdown 误伤；数据藏 `display:none` + UI 由 JS `createElement` 生成（或进 shadow）则绕开。
- **聊天运行在 `chatIframe` 内**：浏览器控制台默认 TOP frame 查不到状态栏 DOM，须切执行上下文到 chatIframe；`document` 作用域、数据扫描同理。
- 导入方式：json 批量导入（MMD 专用 4 字段格式 pageDepth/statusbar/beginning/regex_scripts）或平台 UI 逐条手填，见 ../output/regex-output.md。
- random 标签三种用法、避坑：沿用 ../platforms/mmd-old.md §4.2-4.3（与平台无关）。

---

## 8. 写作策略

1. **状态栏/交互模块**：动态走雷达法（见 ../beautify/statusbar-radar.md，引擎载体 img onerror），固定字段走原生 `$field` / KV V4.0。引擎代码推荐 ES6。
2. **交互（点击/折叠/切图）**：走 §3 两条合法路径（`window.__fn` 或轻主板 eval）。
3. **全局美化**：见 ../beautify/global-css.md，激活器可用 `<script>` 或 img onerror。
4. **正则交付**：json 导入（4 字段）或手填、130 条限额，见 ../output/regex-output.md。

---

## 9. 沿用旧版的通用规则（与平台版本无关）

以下条目旧版当前版**完全一致**，直接沿用 ../platforms/mmd-old.md：

- **§1 结构红线**：`<img onerror>` 必须在容器闭合 `</div>` 之前；最外层容器 `onclick="event.stopPropagation()"` 防冒泡。
- **§4 正则系统**：random 标签三种用法、字符数避坑（总数上限改 130）。
- **§5 核心架构**：§5.1 onerror 点火器、§5.2 纯CSS radio:checked 切换、§5.3 轻主板+胖遥控器（**当前版已复测可用**）、§5.4 appendChild 置顶、§5.5 时间戳唯一ID。
- **MMD 换行空白条陷阱**：markdown 管线（vditor）把标签间换行补成空 `<p>`，浏览器预览查不出，详见 ../beautify/statusbar-radar.md 与 mmd-old.md §3 三级表。

**当前版与旧版的唯一交互差异**：旧版曾放行极简单行 inline 赋值（`this.x='y'`），当前版收紧——inline 赋值也被净化，交互一律走 §3 的 `window.__fn` 或轻主板 eval。`<img onerror>` 内可用 ES6、可多行（旧版须 ES5 单行），但纯 DOM API 原则（避免 `innerHTML` 字符串拼接被实体化）仍建议遵守。

---

## 10. 正则触发标记交叉污染（2026-06-17 实机踩出，validate 查不出）

**症状**：多正则项目里，某个组件（如悬浮球）静默不显示，但每条正则单独看都合法、validate/JSON 校验全过。

**根因**：MMD 按顺序跑所有正则，每条正则的 findRegex 会扫**整条消息的当前 HTML——包括前面正则已经替换出来的内容**。如果 A 正则的触发标记（如状态栏的 `<ztl>`）以**字面形式**出现在 B 正则（如悬浮球）的 replaceString 里（常见于 onerror 引擎内"给模型的指令文本"，如 `fillTA('...输出 <ztl> 锚点...')`），那么 A 正则会把 B 引擎源码字符串里的 `<ztl>` 也替换成 A 的 HTML（`<img src="...">`）。这段 HTML 的双引号/标签**破坏 B 的 onerror 属性 JS 语法 → SyntaxError → B 引擎整段不执行 → 不显示**。

**为什么 validate 查不出**：这是**跨正则的运行时污染**，单条正则都合法，只有把所有正则按序应用后才暴露。

**修法**：组件引擎内任何提及别的触发标记的字面文本，**拆开拼接**让源码不含连续 token：
```js
fillTA('...另起一行输出 ' + '<zt'+'l>' + ' 锚点...');   // 运行时拼回完整 <ztl>，源码扫不到
```
同理 `<css>`/`<status>`/`<悬浮球>` 等任何触发标记都不可在别处 replaceString 里以字面完整出现。这与「§3 onclick 净化」「数据信标转换器啃断 `[键=值]`」（见 ../beautify/floating-components.md）是同一类"载荷被后续正则二次处理"的陷阱。

---

## 11. 隐性渲染错误排查法（组件不显示/代码暴露/静默失败时）

onerror 引擎类故障（不显示、代码暴露、面板空白）的错误**不进控制台**（onerror 抛错被吞），且 validate 只查静态合法性。按以下顺序快速定位——本法 2026-06-17 实机定位"悬浮球 `<ztl>` 交叉污染"全程：

1. **先 validate**：`scripts/validate.py 文件 --platform mmd`。0 错也不代表没问题（运行时污染查不出），但能先排掉字符数/BOM/双重转义/悬空等静态错。
2. **浏览器预览看"建没建出来"**：`scripts/build-preview.py 文件 --platform mmd` → 用 Preview 工具开 panorama，在 iframe 里查组件根节点是否存在：
   ```js
   var D=document.querySelector('iframe.pano-frame').contentDocument;
   D.getElementById('组件wrap的id')   // null=引擎没执行成功
   D.querySelectorAll('img[data-xxx]').length  // >0 残留=onerror触发了但中途抛错没self-remove
   ```
   **关键判据**：根节点 null + img 残留 = 引擎执行中途抛错（而非没触发）。同项目里"A组件出、B组件不出"→ 差异在 B 引擎本身或它被污染。
3. **捕获被吞的异常**：onerror 抛错不进 console，手动在 iframe 里 try/catch 执行引擎体：
   ```js
   var code=D.querySelector('img[data-xxx]').getAttribute('onerror');  // 取渲染后的实际 onerror
   try{ W.eval('(function(img){'+code.replace(/^\(function\(img\)\{/,'').replace(/\}\)\(this\)$/,'')+'})')(img); }
   catch(e){ return e.name+': '+e.message; }
   ```
   报 `SyntaxError` → 源码被污染/转义坏了；报 `TypeError` → 逻辑 bug。
4. **对比"原始 replaceString" vs "渲染后 DOM 里的 onerror 属性"**：若两者长度/内容不同，说明被正则管线改过——重点看截断处、被替换成 `<img/<span` 的地方，倒推是哪条正则的标记/信标啃的（见 §10、数据信标 `[键=值]`）。这步是定位"交叉污染"的决定性手段：
   ```js
   var code=D.querySelector('img[data-xxx]').getAttribute('onerror');
   code.length    // 比原始 replaceString 短 = 被截断/啃断
   code.slice(-90) // 看尾部停在哪、有没有混进 <img src= 之类异物
   ```
5. **node 复核源码本身**：把原始 replaceString 的 onerror 体抽出，`new Function('img', inner)` 解析。node 通过但浏览器报 SyntaxError → 差异来自渲染管线（污染/markdown），不是源码——回到第 4 步。

> 经验：onerror 故障**九成是"渲染管线动了源码"而非源码本身错**（交叉污染、信标啃断、双引号闭合属性、markdown 实体化）。先比对"原始 vs 渲染后"，比逐行读源码快得多。
