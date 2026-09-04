# 当前MMD平台技术规范（支持 `<script>`、ES6）

> 本文档描述当前 MMD（魅魔岛/sexyai.top）**主聊天页**。各节分别标注实测、官方文档、保守处理或待验证；只有明确标为实测的条目才可视为探针/真实对话结论。当前 MMD 仍在迭代，本文档随实测更新。未实测的能力（MVU/STScript/酒馆助手等）仍按无处理（保守）。
>
> 状态栏具体方案（三段正则模板、数据格式、继承机制）见 `../beautify/statusbar.md`，全局CSS美化见 `../beautify/global-css.md`。
>
> **真实页 DOM/CSS 契约见 §13**（2026-08-28 实机 CSSOM 抓取）：层级骨架、气泡 CSS 原文、rem 缩放律、29 个主题变量、z-index 层级表。写选择器或定配色前先看那一节。
>
> **另有「沙盒模式」新聊天页**（角色卡 `chatVersion: 1` 开启），执行模型与本文档不同（官方 SDK、`<script>` 一等公民、禁 `img onerror`），单独成规范见 `mmd-sandbox.md`。本文档所述规则**不适用于**沙盒模式。

## 0. 能力速查（全部已实测/已确认）

| 项目 | 当前 MMD | 状态 |
|---|---|---|
| `<script>` 标签 | ✅ 可执行；**per-message 自渲染/定位不可用**；document-level 一次性 bootstrap 与全局 handler 定义可用 | 已实测边界 |
| ES6+ 语法 | ✅ 全支持（img onerror 载体下，7/7 探针全绿），**推荐 ES6** | 已实测 |
| `onerror` 多行 / 双引号 | ✅ 可多行、可用双引号，代码可写干净（内部禁裸双引号，见 §2） | 已实测 |
| `onclick` 净化 | 只放行"干净调用/引用表达式"，禁代码字面量与直接 DOM 赋值 | 已实测 |
| 正则总数上限 | **130 条** | 已实测 |
| findRegex / replaceString 上限 | 1000 / 20000 字符 | 已确认 |
| 角色卡导入 | 仅 chara_card_v2（不识别 v3） | 已确认 |
| 原生 KV `$field` 状态栏 | ✅ 平台内置（`【状态】hp::85【/状态】` → 替换里用 `$hp`，纯HTML零JS） | 官方文档 |
| MVU/STScript/酒馆助手 | ❌ 按无处理 | 保守 |
| 气泡 `white-space` | **`pre-line`**（标签间换行=真实换行，空白条真因，见 §10.1/§13） | 已实测 |
| rem 缩放 | `rootFontSize = 16*min(视口宽,375)/375`（见 §13.3） | 已实测 |
| 真实 DOM 层级 | `.chat > .chat-scope-box > .scroll-view > .chat-body`（见 §13.1） | 已实测 |

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

**结论**：ES6 语法无任何截断或拦截，新写引擎/交互代码**推荐 ES6**——同一功能代码更短、可读可改、bug 更少。前提：以上在 `img onerror` 载体内测得。

ES6 在卡片里的典型用法（纯写法糖，逻辑能力与 ES5 等价）：
- 展开运算符做不可变更新：`const next = { ...上一轮状态, 好感: 上一轮状态.好感 + 3 }`
- 模板字符串拼 HTML：`` `好感 ${cur}/${max}` ``
- 解构 + 可选链安全取值：`const 好感 = 数据?.npc?.好感 ?? 0`
- 箭头 + map/filter 渲染在场角色：`在场.filter(n=>n).map(name=>建角色卡(name))`

---

## 2. `onerror` 的书写自由度（实测）

| 写法 | 实测 |
|---|---|
| 单行 `onerror` | ✅ 可用 |
| 多行 `onerror`（属性值带换行） | ✅ 可用 |
| 属性内双引号（`onerror='...'` 单引号包裹时内部用 `"`） | ✅ 可用 |

`onerror` 内代码可写成正常多行函数、可用双引号（前提是属性本身用单引号包裹，见下方红线）。复杂状态栏引擎可以按人能手写手改的正常代码来写，不必挤成一行。

> 🚨 **真红线：onerror="" 内部禁裸双引号（2026-06-17 浏览器+MMD 实机三组对照确认）**。`onerror="..."` 双引号包裹时，内部 JS 任何 `"` 会提前闭合属性 → 后段 JS 拆成无效裸属性 → img 结构破坏 → 引擎不绑定 → **面板静默不渲染（不爆代码但完全不显示）**。修法：内部字符串全用单引号；注入的配置（CFG/CSS）用单引号 JS 字面量序列化，**勿用 `json.dumps`/`JSON.stringify`**（产双引号）。`validate.py` 已检查此项。
>
> **踩坑复现（2026-08-28，写预览脚手架时又踩了一次）**：想在 onerror 里写属性选择器 `D.querySelector('[data-sheet=\"'+name+'\"]')`，转义后仍是裸 `"` → 属性在此提前闭合，onerror 被**截断到 230 字符**，SyntaxError 被吞，整个面板开关静默失效，现场只剩一个残留 img（正是 §12 的判据）。
>
> **绕法：属性选择器的值合法时可不加引号** —— `[data-sheet=model]`、`[data-open=on]` 都合法，彻底避开引号。但注意 **CSS 标识符不能以数字开头**：`[data-open=1]` 会抛 `SyntaxError: not a valid selector`，所以状态值用 `on/off` 而不是 `1/0`。这两条一起才走得通。
>
> ⚠️ **已撤销的伪铁律**：曾误立"onerror 内禁裸 `<`/`>`/`=>`"，后经实机证伪——onerror **引号内**的 `<`/`>` 是纯文本，HTML 属性值不解析标签，**无害**；比较运算/for 循环/箭头函数可正常用。雷达法引擎满是 `i<n`/`c>0` 实战正常即铁证。当初误诊源于把"内部双引号致暴露"错归为"`>` 致暴露"（双引号在更前面已闭合属性，`>` 只是碰巧在暴露文本里）。**教训：单次实机表象易误导，立红线前须做对照实验。**

> 注：JSON 交付层的换行/引号转义仍照旧（`replaceString` 写进 JSON 仍须转 `\n`、`\"`，见 ../output/regex-output.md 2.3）。"onerror 可多行"指的是**渲染到页面后**的 HTML 属性值层面，与 JSON 字符串字面量的合法性是两回事。

---

## 3. `onclick` 放行规则（实测）

**核心判据：`onclick` 属性值里只能是"干净的调用/引用表达式"，不能出现代码字符串字面量或直接 DOM 赋值语句。**

| 写法 | 实测 | 说明 |
|---|---|---|
| `onclick="window.__fn&&__fn()"` | ✅ 放行 | 纯短路调用全局函数（官方推荐）；不需要参数时使用这个 canonical 形式 |
| `onclick="eval(getElementById('FUNC').dataset.s)"` | ✅ 放行（E1） | 干净的调用表达式；eval 本体未被 CSP 拦，执行了 data-s 里的 DOM 操作 |
| `el.onclick=function(){}`（img onerror 里 JS 赋值绑定） | ✅ 放行 | 净化器只扫 HTML 属性文本，扫不到 JS 赋的 handler |
| `onclick="eval('...代码...')"`（代码字符串塞进属性） | ❌ 净化（E2） | 属性内出现代码字面量，命中净化规则 |
| `onclick="this.x='y'"`（直接 DOM 赋值） | ❌ 不触发 | 赋值语句也算代码，被净化 |

**两条合法交互路径（当前 MMD 二选一，均已实测）**：
1. **`window.__fn` 全局函数**（官方推荐）：在 `<script>` 或 `img onerror` 里定义 `window.__fn = window.__fn || function(){...}`，无参数按钮使用已验证的 canonical 形式 `onclick="window.__fn&&__fn()"`。
2. **轻主板 + 胖遥控器**（见 §10.3，已复测可用）：复杂逻辑存进隐藏元素的 `data-s` 属性，`onclick="eval(getElementById('FUNC').dataset.s)"` 只做干净的 eval 调用——正因为踩中"属性内是干净调用、代码在 data-s 里"才放行。

> 雷达引擎的选项按钮一直能点，用的就是路径 ③ `el.onclick=function(){}`（img onerror 里 JS 赋值绑定）——净化器扫不到 JS 赋的 handler。

---

## 4. `<script>` 的能力边界（per-message 不可用，document-level 可用）

`<script>` 已解禁可执行，但**做不了 per-message 自渲染/定位**，状态栏引擎仍只能用 `img onerror`。两个原因：

1. **拿不到自身位置**：自渲染引擎依赖 `document.currentScript` 定位，在 MMD 执行模型里不可用；官方所有 script 示例都靠 `window.__fn` + `onclick` 调用，从不自定位。
2. **同段 `<script>` 只加载一次**（官方原文）：状态栏每条消息都带同一份引擎 → 会被去重，不逐条执行 → 整块空白。

**结论**：
- per-message 动态渲染（状态栏引擎）**必须用 `<img onerror>`**——每元素每条触发、`this` 可靠自定位。
- document-level 单例可以用一次性 `<script>` bootstrap，例如定义 `window.__唯一名` handler，或取得/复用一个全局主题 runtime；bootstrap 必须幂等，不能依赖同段 script 随每条消息重跑。
- "开放 script"不解决 per-message 自渲染/定位问题，但可承载全局交互定义和文档级运行时初始化。

> 实测反例：把雷达引擎从 img onerror 改成 `<script>` 载体后，状态栏整块空白。

### 4b. 全局运行时与 per-message 脚本边界

同段 `<script>` 只执行一次，对两类任务的含义相反：

| 类型 | 正确边界 | 去重后的要求 |
|---|---|---|
| **全局主题运行时** | 文档级单例，负责 owner/version 租约、head CSS、主题面板、一个 observer 和路由生命周期 | 一次 bootstrap 正合适；重复触发只能调用既有实例 `reenter()`，不得再声明一份运行时 |
| **per-message 状态栏 / 消息组件** | 每条消息各自定位、读取该条数据并渲染 | 不能依赖同段 `<script>` 重复执行，仍用 `img onerror`；全局资源不得随消息数增长 |

当前 MMD 是动态路由页面。全局运行时不能只在首次执行时判断一次 `location`，必须安装**一个 route supervisor**：监听适用的 `hashchange`、`popstate`、`pageshow/pagehide` 等信号，进入聊天路由时 `reenter()`，离开时 `leave()`，整页替换聊天根节点时校正重建；只有 `destroy()` 才移除 supervisor。完整 `bootstrap/enter/leave/start/stop/destroy/reenter` 语义见 `../beautify/theme-runtime.md`。

per-message 点火器若要唤醒主题，只能调用已存在的全局 API，例如 `window.__某前缀ThemeRuntime?.reenter()`，然后自毁；不得在每条 AI 消息内附带公共 CSS、MutationObserver、主题面板或 route supervisor。

### 4c. localStorage 作用域：全局偏好候选，待实机矩阵

历史记录曾写到状态栏跨气泡读取 localStorage 为 `NULL`，但该记录**未附完整日期、客户端/版本、frame 与路由环境，也未附可复现探针代码**，因此只能作为待复验线索，不能单独推导任何 runtime 语义。状态栏协议仍不应依赖 localStorage 做跨轮继承；依据是 per-message 数据应可由消息快照/历史 DOM 自足恢复，而不是把这条缺证探针当成平台定律。全局主题能否持久化同样须在当前 MMD iframe / WebView、路由、角色卡、账号与会话矩阵中重新验证。

运行时主题可以把 localStorage 作为失败可降级的偏好候选，但在完成矩阵前必须标“待验证”：同页刷新、离开后返回、同角色不同聊天、不同角色卡、App 重启、账号切换、存储禁用 / 清空 / 配额异常。存储失败时，当前页面的 day/night/native 切换仍须工作；owner 租约和 DOM 恢复不得依赖 localStorage。schema、校验、迁移和矩阵见 `../beautify/theme-runtime.md`。

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

> **自定义标签存活（2026-06-17 实测）**：未知自定义标签（如 `<z-live-widget>`）**不在删除名单、实测未被剥离**，白名单对未知标签实际放行。但 `customElements.define()` 须在 `<script>` 里跑，注册只属于当前 document，完整 reload 后需由 document-level bootstrap 重新注册（见 §4），所以**不要让 per-message 组件依赖 Custom Elements 注册**；要用 Shadow DOM 隔离请走 §6b 的 `img onerror` + `attachShadow` 路线。

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
| `img onerror` 里 `attachShadow({mode:'open'})` | ✅ 成功，shadow 内 `<style>`+DOM 正常渲染 | **不需要 `customElements.define`**（注册属于当前 document，reload 后须 bootstrap 重建），纯 onerror 即可拿 Shadow DOM |
| shadow 抗平台重绘 | ✅ 翻页/刷新后 host 与 shadowRoot 仍在；onerror 重新点火走"已有则复用刷新"分支 | 雷达法的防劫持自检/2.5秒重建探针**可省** |
| 🔑 shadow 内 `*害羞*` 星号 | ✅ 原样保留，不被 markdown 吃 | **shadow 内 UI 对 markdown 完全免疫** |

**Shadow DOM 免疫哪些、不免疫哪些（2026-08-28 实机探针修订）**：

| 项 | Shadow DOM | 说明 |
|---|---|---|
| markdown 吃 `*害羞*` 星号 | ✅ 免疫 | shadow 内容不过 vditor 管线 |
| CSS 类名冲突（原需 `z-` 前缀） | ✅ 免疫 | 外部样式表选择器进不来 |
| 强制染色注入 MutationObserver 哨兵 | ✅ 可省 | shadow 抗平台重绘（本节表格已测） |
| **换行空白条** | ❌ **不免疫** | `white-space` 是**继承属性**，穿过 shadow 边界从 host 继承。实测 shadow 内 computed 值就是 `pre-line`，同样撑出 102px（vs 子元素合计 51px）。必须在 shadow 内显式写 `:host{white-space:normal}` 或 `*{white-space:normal}` |

> 🚨 上一版本这里写的是「Shadow DOM 对 markdown 陷阱免疫，换行空白条补丁全部不再需要」——**换行空白条那一项是错的**。误诊源头：把空白条归因于"markdown 补空 `<p>`"，于是推出"不过 markdown 管线 → 自然免疫"。实测真因是 host 的 `white-space:pre-line` 继承（见 §10.1 与 §13），与 markdown 无关，所以 shadow 隔离救不了它。教训与 §2 撤销伪铁律同一条：**推论链再顺，也要用探针验一次终点**。

**架构（数据留 light + UI 进 shadow）**：
- **数据**：放 light DOM 隐藏 `<span style="display:none">`——实测其 textContent 经 markdown 后一字不差（含 `*`/`|`/`/`），可被后续消息全局扫描做跨轮恢复。**绝不把数据放 shadow 内**（shadow 跨气泡扫不到、且 reload 即失）。
- **载体**：`img onerror`（唯一可靠 per-message 渲染载体，见 §4）。读同气泡 light 数据 + 扫历史 light span 折叠兜底。
- **渲染**：`onerror` 里 `h.shadowRoot || h.attachShadow(...)`（已有则复用，幂等防重影）→ `createElement` 装配进 shadow root。
- **协议**：模型每轮吐**全量快照**。per-message 状态继承不依赖存储；历史 `NULL` 记录缺完整环境与探针、仍待复验，不能用来推导全局主题或消息 runtime 的存储语义，见 §4c。

**选型补充**：动态/自创 NPC/长线复杂数据 → Shadow DOM 方案（隔离最省心）或雷达法（成熟、示例多）；二者数据恢复地基相同（扫 light span），区别仅在 UI 是否进 shadow。固定字段仍走原生 `$field` / KV V4.0。详见 ../beautify/statusbar-radar.md 与记忆 [[mmd-statusbar-next-gen-design]]。

---

## 7. 平台硬上限

| 项 | 硬上限 | 超出后果 |
|---|---|---|
| **固定传输字符** | **15000 字** | 截断 |
| 单条正则 replaceString | 20000 字 | 截断 |
| 单条正则 findRegex | 1000 字 | 失效 |
| 正则条数 | 130 条 | 无法再加 |
| **世界书条目标题** | **20 字**（`comment` 字段） | 截断 |
| 角色卡格式 | 仅 chara_card_v2 | v3 不识别 |
| 角色卡图片 | 仅 PNG（JPG 读不出 chara 数据）| 导入无数据 |

### 世界书条目标题（20 字上限）

条目标题即导出 JSON 的 `comment` 字段（源文件 frontmatter 的 `title`），MMD 平台上限 **20 字**，超出部分导入后被截断。本地酒馆无此限制。

计长口径：**按字符数，中文一字算 1**，标点与空格同样计入。所以装饰符很贵——`【角色状态与局势面板 · 状态栏生成协议】` 是 21 字，仅 `【】` 和 ` · ` 就吃掉 5 字额度。写标题的纪律：

- 不加 `【】`、`·`、`—` 等装饰框线，需要分组就靠层级目录和 `order`，不靠标题排版。
- 用 `角色：莉娅`、`魔法代价规则` 这类"类别：名字"或直接名词短语，20 字足够。
- 标题只是平台 UI 里的定位标签，不参与注入，不用写全描述——摘要写进源文件 `summary`。
- 若开了 `include_entry_id_in_comment`，`[e0001] ` 前缀（8 字符，随 entry_id 位数增长）也计入这 20 字，标题本身只剩 12 字，一般不建议开。

脚本已强制此限：`worldbook_tool.py add/rename` 超限直接拒绝（不写出源文件、退出码 2），`check` 报 error，`build` 不阻断导出但打 `[WARN]`（兜手改 frontmatter 的情况），`import` 保留既有数据只打 `[WARN]`，`validate.py --platform mmd` 对 `comment` 报 error。若项目目标平台是本地酒馆，在 `worldbook.config.json` 里设 `"platform": "st"` 可关掉该检查（`validate.py` 侧对应传 `--platform st`）。

### 固定传输字符（15000 字上限）

**固定传输字符 = 每一轮请求都固定发给模型的常驻内容**，上限 15000 字。

**计入固定传输**：
- `description`（人设）+ `personality` + `scenario`
- **所有蓝灯（constant=true）世界书条目的 content**（常驻每轮注入）

**不计入（默认状态下）**：
- **绿灯（constant=false）条目**——未触发时不发
- `first_mes` / `alternate_greetings`（开场白）——只第一条消息，不作为每轮设定重发
- 聊天历史、状态栏数据块等变动内容

**⚠️ 关键陷阱：绿灯触发时也计入**

绿灯条目**一旦被关键词命中，那一轮它的 content 也塞进 15000 固定传输**。所以绿灯不是"免费扩容"，要守的是**峰值**：

```
蓝灯content合计 + 人设+性格+情境 + （该轮同时触发的绿灯content）≤ 15000
```

并且要为变动内容（聊天历史 / 状态栏数据块 / 临时事件）**预留缓冲（建议 2000–3000 字）**，不要把固定传输顶满。

---

## 8. 正则系统

- **总数 ≤ 130 条**；findRegex ≤ 1000 字符（超出后正则失效）；replaceString ≤ 20000 字符（超出后被截断，超限拆多条）。
- **findRegex 必须是 `/pattern/flags` slash literal**（2026-06-17 实测铁律）：四字段 JSON 导入与 UI 手填都不得使用裸模式。不带斜杠（如 `\[k=([^\]]+)\]`）时平台正则控制台**测试能过、实际聊天界面不替换**；写成 `/\[k=([^\]]+)\]/` 才生效。固定标记也必须写成 `/<标记>/`。
- **正则跑在 markdown(vditor) 之前**：正则替换产出的 HTML 还要再过一遍 markdown 管线（`*x*` 会被吃成斜体）。靠正则直接吐可见文本会被 markdown 误伤；数据藏 `display:none` + UI 由 JS `createElement` 生成（或进 shadow）则绕开。
- **聊天运行在 `chatIframe` 内**：浏览器控制台默认 TOP frame 查不到状态栏 DOM，须切执行上下文到 chatIframe；`document` 作用域、数据扫描同理。
- 导入方式：json 批量导入（MMD 专用 4 字段格式 pageDepth/statusbar/beginning/regex_scripts）或平台 UI 逐条手填，见 ../output/regex-output.md。

### 8a. `random` 标签三种用法

平台级正则特性，写在 `replaceString` 里。

**用法1：多个独立 random 标签各自随机。** 同一 `replaceString` 中多个 `random` 标签**各自独立**随机，互不干扰。

```
replaceString: 你抽到了武器：(random(长剑|战斧|法杖)) 和防具：(random(皮甲|锁子甲|布袍))。
可能结果：  "你抽到了武器：长剑 和防具：布袍。"
           "你抽到了武器：战斧 和防具：皮甲。"
```

**用法2：在语句中无缝嵌入。** `random` 标签可嵌入句子任意位置，生成流畅文本。

```
replaceString: 石头剪刀布，我决定出 (random(石头|剪刀|布)) 来一决胜负！
可能结果：  "石头剪刀布，我决定出 剪刀 来一决胜负！"
```

**用法3：捕获组 `$1` 作为 random 选项。** 将 `findRegex` 中捕获到的内容作为 `random` 标签的动态选项，实现最强联动。

```
findRegex:     /我选择(.+)/
replaceString: 你选择了 $1 啊，这真是个 (random(不错的|绝妙的|有待商榷的|$1 自己的)) 选择。

当用户输入："我选择苹果"
可能结果1（常规项）：  "你选择了 苹果 啊，这真是个 绝妙的 选择。"
可能结果2（$1被选中）："你选择了 苹果 啊，这真是个 苹果 自己的 选择。"
```

**避坑两条**：

- 使用捕获组作为 `random` 选项时，确保 `findRegex` 能**稳定准确**捕获预期内容，不稳定的正则会导致 `random` 出现非预期文本。
- 时刻注意 `replaceString` 总字符数，复杂 `random` 组合（尤其多个长选项）会快速消耗 20000 字符额度。

> 另有官方文字变量形态 `{{random:A::B::C}}`（见 §6），两种写法并存。

---

## 9. 写作策略

1. **状态栏/交互模块**：动态走雷达法（见 ../beautify/statusbar-radar.md，引擎载体 img onerror），固定字段走原生 `$field` / KV V4.0。引擎代码推荐 ES6。
2. **交互（点击/折叠/切图）**：走 §3 两条合法路径（`window.__fn` 或轻主板 eval）。
3. **全局美化**：先在 ../beautify/global-css.md 选择静态换肤或运行时主题包；需要 day/night/native、玩家微调或路由重入时再读 ../beautify/theme-runtime.md。全局运行时是文档级单例，不属于 per-message 渲染。
4. **正则交付**：json 导入（4 字段）或手填、130 条限额，见 ../output/regex-output.md。
5. **任何交互模块动手前先过 §10**：结构红线（img 位置、stopPropagation、时间戳 ID、换行空白条）与四种核心架构模式（onerror 点火器、轻主板+胖遥控器、纯CSS radio 切换、appendChild 置顶）都在那一节。

---

## 10. 结构红线与核心架构模式

本节是所有交互模块（状态栏、面板、模态框、悬浮组件）共用的地基，与具体功能无关。

### 10.1 结构红线（违反即整块失效）

| 红线 | 现象 / 后果 | 做法 |
|:---|:---|:---|
| `<img onerror>` 必须在容器内部 | `img.closest('.容器')` 返回 `null`，整段 JS 逻辑一行都跑不起来 | 点火器 `<img onerror>` 必须位于最外层容器闭合 `</div>` **之前**，不能放在容器外 |
| 事件冒泡污染（PC端） | 模块内点击冒泡到聊天气泡父容器，意外触发编辑/复制等默认行为 | 最外层容器加 `onclick="event.stopPropagation()"` |
| 重复 ID 让 `getElementById` 失灵 | 所有聊天记录渲染在同一页面文档，重复 ID 引发 JS 串台；**这是"第二次使用就失效"的根本原因** | 所有 ID 带时间戳后缀，见 §10.5 |
| 单条正则注入 HTML 超 20000 字符 | 被截断或整体失效 | 压缩代码、CSS 用短类名、超限拆多条正则 |

> 🚨 **换行空白条陷阱**（2026-08-28 实机探针纠正机制，见 §13）：气泡容器 `.content` 带 **`white-space: pre-line`**，标签之间的换行会被当作**真实换行保留**，每个换行撑出一整行行高 → 大块横向空白条。内容少的页尤其明显。
>
> **两条有效修法**：① 注入 HTML 写成单行无缝（标签间零换行）；② 自己的容器上写 **`white-space: normal`**（实测 102px→51px，最省事，推荐）。
>
> ⚠️ **无效的旧修法（别再抄）**：`p:empty{display:none}` / `br{display:none}` —— 实测现场 `p:empty` 数量为 **0**、也没有 `br`，这两条 CSS 什么都没做。`p{margin:0}` 只对 markdown 生成的 `<p>` 有意义，与本陷阱无关。
>
> ⚠️ **Shadow DOM 对此陷阱不免疫**（旧文档说免疫，是错的）：`white-space` 是继承属性，会穿过 shadow 边界从 host 继承进来（shadow 隔离的是**选择器**，不隔离继承属性）。走 §6b 仍须在 shadow 内显式写 `:host{white-space:normal}`。
>
> 状态栏侧详见 ../beautify/statusbar-radar.md「MMD换行空白条陷阱」。

### 10.2 onerror 点火器（per-message 唯一可靠载体）

见 §4：`<script>` 做不了 per-message 自渲染，逐条消息渲染只能用 `img onerror`。基础骨架：

```html
<img src="x" style="display:none" onerror='(function(img){const box=img.closest(".容器类名");if(!box)return;/* 逻辑写这里，可多行、可用 ES6 */img.remove()})(this)'>
```

关键要点：
- 用 IIFE `(function(img){ ... })(this)` 包装，`img` 即触发元素本身，`this` 是可靠的自定位手段。
- `img` 标签必须在最外层容器闭合 `</div>` **之前**（§10.1）。
- 执行完毕调用 `img.remove()` 清理 DOM；中途抛错会留下残留 img，这正是 §12 的关键判据。
- 代码**可多行、可写 ES6**（§1、§2）；但属性用双引号包裹时内部禁裸双引号（§2 红线），骨架示例故意用单引号包裹属性。

### 10.3 轻主板 + 胖遥控器

**突破 `onclick` 净化限制的稳定架构**（当前 MMD 已复测可用，见 §3 路径 2）。

原理：把复杂 JS 逻辑作为纯文本字符串存在隐藏 `<p>` 的 `data-s` 属性里（轻主板），按钮 `onclick` 只执行极简 `eval(...)` 调用（胖遥控器）。

架构优势：
- **代码与结构分离**：复杂逻辑存为纯文本，不触发平台对属性内代码字面量的净化。
- **绕过 CSP 限制**：`data-*` 属性不受内容安全策略约束。
- **配合时间戳**：每个主板独立时间戳 ID，同一页面多次生成互不干扰。

```html
<!-- 轻主板：存储复杂逻辑 -->
<p id="FUNC_CALCULATE_1729584719271" style="display:none"
   data-s="var input=document.getElementById('INPUT_1729584719271').value;var result=parseFloat(input)*2;document.getElementById('OUTPUT_1729584719271').textContent='结果:'+result;"></p>

<!-- 最外层容器，阻止冒泡 -->
<div id="CALC_MODULE_1729584719271" onclick="event.stopPropagation()">
    <input type="text" id="INPUT_1729584719271" placeholder="输入数字">
    <!-- 胖遥控器：onclick 只做 eval 触发 -->
    <button onclick="eval(document.getElementById('FUNC_CALCULATE_1729584719271').dataset.s)">
        计算
    </button>
    <div id="OUTPUT_1729584719271">结果将显示在这里</div>
</div>
```

> 当前 MMD 下 `data-s` 内不必再压成 ES5 单行，可正常用 ES6；但它仍是属性值，双引号规则照 §2 办（属性用双引号包裹时内部字符串用单引号）。若不需要传参，§3 的 `window.__fn` 路径更简单，优先考虑。

### 10.4 纯CSS切换（radio + `:checked`）

完全不依赖 JS 的动态显隐，天然免疫所有 JS 净化规则，标签页/分页首选。

```html
<style>
    .page { display: none; }
    #radio1_时间戳:checked ~ .container .page1 { display: block; }
    #radio2_时间戳:checked ~ .container .page2 { display: block; }
</style>

<!-- 隐藏 radio 作状态控制器 -->
<input type="radio" id="radio1_时间戳" name="nav_时间戳" checked style="display:none">
<input type="radio" id="radio2_时间戳" name="nav_时间戳" style="display:none">

<div class="container">
    <!-- label 触发 radio 切换 -->
    <label for="radio1_时间戳">第一页</label>
    <label for="radio2_时间戳">第二页</label>
    <div class="page page1">第一页内容</div>
    <div class="page page2">第二页内容</div>
</div>
```

注意：所有 `id`、`name`、`for` 属性都必须含时间戳后缀保证唯一性（§10.5），`<label>` 的 `for` 与目标 `input` 的 `id` 时间戳必须一致。

### 10.5 appendChild 置顶（模态框/浮窗覆盖整页）

DOM 原理（4 步）：
1. 聊天气泡及其内部的原始容器在 DOM 树中位置固定。
2. 执行 `document.body.appendChild(container)` 时，容器**从原始位置移除**并**重新挂载**到 `<body>` 最末尾。
3. 容器在 DOM 树中的位置比所有聊天消息、导航栏都更靠后（后来居上）。
4. 配合 `position: fixed` 定位，该元素在视觉上浮动于所有内容之上。

关键 CSS：
```css
position: fixed;                   /* 脱离文档流，相对视口定位 */
top: 50%; left: 50%;
transform: translate(-50%, -50%);  /* 水平垂直居中 */
z-index: 9999;                     /* appendChild 已保证顺序，z-index 作保险 */
```

**避坑5条：**
1. **时间戳一致性**：同一模态框系统所有 ID 必须使用相同时间戳。
2. **冒泡处理**：模态框内容区必须有 `onclick="event.stopPropagation()"`；遮罩层点击用于关闭。
3. **显示顺序**：先 `appendChild(overlay)` 再 `appendChild(modal)`，确保模态框在遮罩层之上。
4. **z-index 保险**：`appendChild` 已保证 DOM 顺序，仍建议设 `z-index: 9999`。
5. **性能**：频繁 `appendChild` 触发重排；需要频繁切换的元素只 `appendChild` 一次，后续仅切 `display`。

> 遮罩层 + 模态框的开关逻辑，当前 MMD 可直接写成 §3 路径 1 的 `window.__fn` 全局函数（比塞进 `data-s` 更好读）；若逻辑需要按元素带参，再走 §10.3 轻主板。

### 10.6 时间戳唯一ID

**根本原因**：平台把所有聊天记录渲染在同一页面文档，重复 ID 导致 `getElementById` 失灵（这是"第二次使用就失效"的根本原因）。

生成方式：`Date.now()` 取当前毫秒时间戳。命名格式 `元素类型_功能描述_时间戳`，例如 `BUTTON_SAVE_1729584719271`、`INPUT_NAME_1729584719271`、`FUNC_TOGGLE_1729584719271`。

**检查清单4条：**
- [ ] 每次生成新模块都生成新时间戳（不复用旧时间戳）
- [ ] 同一模块内所有 ID 使用**相同**时间戳后缀
- [ ] JS 代码中引用的 ID 也含时间戳（`data-s` 内部的 ID 字符串同样要含）
- [ ] `<label>` 的 `for` 与目标 `input` 的 `id` 时间戳一致

### 10.7 仍然不可靠的载体与交互细节

以下条目来自旧基线社区文档，未在当前 MMD 逐项复测，按保守处理（**证据等级：社区文档，待复验**）：

| 项 | 现象 | 做法 |
|:---|:---|:---|
| 脚本自动/懒加载 | `onload`、`onmouseenter` 等不可靠或被阻止，不能用于初始化核心逻辑 | per-message 初始化一律用 `onerror` 点火器 |
| 跨 img 状态传递 | 多个 img 标签之间无法共享状态 | 同一模块的初始化逻辑集中在**单个** img 内 |
| `alert()` | 被平台静默阻止，且中断代码执行不报错 | 调试信息用 DOM 元素在页面内显示，禁用 `alert()` |
| 装饰性伪元素阻挡点击 | 按钮点不动 | 装饰性伪元素加 `pointer-events: none`；交互元素设 `position: relative` 与适当 `z-index` |
| `innerHTML` 字符串拼接 / `style.cssText` 赋值 | 旧基线上会被实体化或报错 | 当前 MMD 未复测其严重度，仍建议纯 DOM API（`createElement` + `textContent` + `appendChild` + `className` 切预定义类）；`validate.py` 对当前 MMD 按告警处理 |

---

---

## 11. 正则触发标记交叉污染（2026-06-17 实机踩出，validate 查不出）

**症状**：多正则项目里，某个组件（如悬浮球）静默不显示，但每条正则单独看都合法、validate/JSON 校验全过。

**根因**：MMD 按顺序跑所有正则，每条正则的 findRegex 会扫**整条消息的当前 HTML——包括前面正则已经替换出来的内容**。如果 A 正则的触发标记（如状态栏的 `<ztl>`）以**字面形式**出现在 B 正则（如悬浮球）的 replaceString 里（常见于 onerror 引擎内"给模型的指令文本"，如 `fillTA('...输出 <ztl> 锚点...')`），那么 A 正则会把 B 引擎源码字符串里的 `<ztl>` 也替换成 A 的 HTML（`<img src="...">`）。这段 HTML 的双引号/标签**破坏 B 的 onerror 属性 JS 语法 → SyntaxError → B 引擎整段不执行 → 不显示**。

**为什么 validate 查不出**：这是**跨正则的运行时污染**，单条正则都合法，只有把所有正则按序应用后才暴露。

**修法**：组件引擎内任何提及别的触发标记的字面文本，**拆开拼接**让源码不含连续 token：
```js
fillTA('...另起一行输出 ' + '<zt'+'l>' + ' 锚点...');   // 运行时拼回完整 <ztl>，源码扫不到
```
同理 `<css>`/`<status>`/`<悬浮球>` 等任何触发标记都不可在别处 replaceString 里以字面完整出现。这与「§3 onclick 净化」「数据信标转换器啃断 `[键=值]`」（见 ../beautify/floating-components.md）是同一类"载荷被后续正则二次处理"的陷阱。

---

## 12. 隐性渲染错误排查法（组件不显示/代码暴露/静默失败时）

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
4. **对比"原始 replaceString" vs "渲染后 DOM 里的 onerror 属性"**：若两者长度/内容不同，说明被正则管线改过——重点看截断处、被替换成 `<img/<span` 的地方，倒推是哪条正则的标记/信标啃的（见 §11、数据信标 `[键=值]`）。这步是定位"交叉污染"的决定性手段：
   ```js
   var code=D.querySelector('img[data-xxx]').getAttribute('onerror');
   code.length    // 比原始 replaceString 短 = 被截断/啃断
   code.slice(-90) // 看尾部停在哪、有没有混进 <img src= 之类异物
   ```
5. **node 复核源码本身**：把原始 replaceString 的 onerror 体抽出，`new Function('img', inner)` 解析。node 通过但浏览器报 SyntaxError → 差异来自渲染管线（污染/markdown），不是源码——回到第 4 步。

> 经验：onerror 故障**九成是"渲染管线动了源码"而非源码本身错**（交叉污染、信标啃断、双引号闭合属性、markdown 实体化）。先比对"原始 vs 渲染后"，比逐行读源码快得多。

### 12a. 症状 → 原因速查表

> 注：表中 data-env/data-st/data-opt/zy/findData 为状态栏方案专属概念，详见 `../beautify/statusbar.md`；其余条目适用于任何交互模块。

| 症状 | 原因 | 解决方案 |
|:---|:---|:---|
| 所有字段显示 `--` | 数据解析失败（img 位置错误或 JS 被截断） | 检查 img 标签是否在 `</div>` 之前（§10.1）；检查 data-env/data-st 属性格式 |
| 代码暴露原样显示 | 正则链断裂，或平台把 HTML 实体化 | 检查正则标记是否正确（§11）；排查 `onclick` 内是否含代码字面量被净化（§3）；排查 `onerror="..."` 内是否有裸双引号（§2） |
| 选项不显示 | `data-opt` 未提供（不继承字段） | 确保每次都输出 `data-opt` |
| 资源条不显示 | `zy` 格式错误 | 检查 `名称:当前值/最大值` 格式（冒号、斜杠） |
| 点击无反应 | 伪元素阻挡点击，或按钮整体被净化删除 | 加 `pointer-events: none`（§10.7）；逻辑改走 §3 两条合法路径 |
| 继承失效 | `findData` 的 selector 参数错误，或 img 在容器外导致 box 为 `null` | 检查选择器；确认 img 标签位置（§10.1） |
| 面板内出现横向空白条 | `.content` 的 `white-space:pre-line` 把标签间换行当真实换行保留，每个换行撑一行行高（**不是**空 `<p>`，实测 `p:empty`=0） | 自己容器上 `white-space:normal`（首选）；或 HTML 压成单行无换行。`p:empty`/`br{display:none}` 无效，Shadow DOM 也不免疫（继承属性穿边界）。见 §10.1 / §13 |
| 组件静默不显示、每条正则单看都合法 | 跨正则触发标记交叉污染 | 见 §11，把标记字面量拆开拼接 |

---

## 13. 真实聊天页 DOM/CSS 契约（2026-08-28 实机抓取）

**抓取方式**：Playwright 进真实站 `www.sexyai.ai #/pages/chat/chat` 的 `iframe#chatIframe`，读 `styleSheets`（CSSOM）+ `getComputedStyle` + 注入探针量高度。这是**一手实测**，不是社区快照。完整契约（含全部 CSS 规则原文）见 `mmd-real-page-contract-2026-08-28.md`。

`scripts/build-preview.py` 的 MMD 预览已按此复刻、并有测试钉死，两种模式分工：

| 模式 | 壳 | 用途 |
|---|---|---|
| `--mode panels`（三面板） | **扁平壳**：真实气泡容器链 + 29 个主题变量 + `pre-line` + rem 律，静态流、**无**顶栏/底栏/弹窗 | 单组件体检（组件建没建出来、有无残留 img、空白条、`var(--*)` 是否解析） |
| `--mode panorama`（全景） | **完整壳**：再加顶栏/底栏/快捷条/侧边挂载点 + 六个弹窗面板与两个原地展开态 | 组合审核（同场串台、层级压盖、全局美化是否漏改某个面板） |

先三面板审单组件，再全景审组合。

### 13.1 层级骨架

```
iframe#chatIframe > body[29个主题变量inline] > uni-app > uni-page-body
└ uni-view.chat                          ← 主容器，CSS 前缀全是 `.chat `
  ├ uni-view.page-header-scope > .topTabbar      顶栏 2.8125rem(45px)
  ├ uni-view.chat-scope-box                      fixed 全屏、z-index 11、角色背景图
  │ └ uni-scroll-view.scroll-view.dark           margin-top:2.8125rem; height:calc(100% - 3.2rem)
  │   └ div.uni-scroll-view > div.uni-scroll-view-content
  │     └ uni-view#msglistview.chat-body         padding-bottom:10.625rem; font-size:15px
  │       ├ .item.Ai.avatar-body > .touch-scope > .content.left   ← 描述气泡（通栏、对称圆角）
  │       ├ .item.Ai > .touch-scope#item0 > .content.left#q-1     ← 正则注入落点
  │       │   └ .modify-btn-scope（z-index 仅 2）
  │       └ .prologue-scope
  ├ uni-view.chat-bottom                         fixed bottom、z-index 999
  │ ├ .shortcut-bar-wrapper.theme-dark > .shortcut-bar > 6×.shortcut-btn
  │ └ .chat-bottom-wapper > .send-msg > .uni-textarea > .chat-input-scope.has-toolbar
  ├ uni-view.mm-left-side-container              ← 官方侧边挂载点 fixed/top:50%/z-index 9999
  └ uni-view.mm-right-side-container
```

**几个容易写错的点**：
- 元素是 `uni-view`/`uni-scroll-view`/`uni-image`/`uni-text`（uni-app 自定义元素），**不是 `div`**。写 `div > .content` 这类子选择器会失配。
- `.chat-body` 与 `.chat` 之间隔着 **`.chat-scope-box` 与 `.scroll-view` 两层**，真机所有 chat-body 后代规则都带这个前缀。
- 用户消息是 `.item.self`（`justify-content:flex-end`）+ `.content.right`。
- `.content` 的 class 属性字面量就是 `class="content left"`，所以 `.content.left` 这个复合选择器**是对的**。
- **不存在**的类名（曾被文档/预览误用）：`.page`、`.chat-bg`。实测 DOM 与 CSSOM 双双零命中。

### 13.2 气泡关键 CSS（实测原文）

```css
.chat .chat-scope-box .scroll-view .chat-body .item{padding:0.71875rem 0.9375rem}
.chat ... .item .left {background-color:#fff;    border-radius:1rem 1rem 1rem 0!important}
.chat ... .item .right{background-color:#c2dcff; border-radius:1rem 1rem 0!important}
.chat ... .item .touch-scope{max-width:94%; color:var(--chat-content-font-color,#FFF)}
.chat ... .touch-scope .content{
    padding:0.75rem; border-radius:0.5rem;
    background:var(--background-color,#17181A);  /* ← 覆盖上面 .left/.right 的白底/蓝底 */
    opacity:0.9;
    white-space:pre-line;                        /* ← 换行空白条真因，见 §10.1 */
}
/* 首条描述气泡：通栏 + 圆角被改成对称 0.5rem（无尖角） */
.chat ... .avatar-body .touch-scope{width:100%;max-width:100%}
.chat ... .avatar-body .touch-scope .left{border-radius:0.5rem!important}
```

**推论**：深色主题下**两侧气泡与页面背景同色**（都是 `#17181A`），`.left/.right` 那两个底色被 `.content` 的 `background` 盖掉了。所以状态栏配色不能靠"气泡自带底色"拉层次——真机上没有层次。

### 13.3 rem 缩放律（两点实测拟合，误差 <0.001px）

```
rootFontSize = 16 * min(innerWidth, 375) / 375
```

由 uni-app 写在 `html` 内联 style 上。实测两点：主聊天页 iframe 宽 1280 → `16px`（封顶）；编辑页右侧「对话测试」预览 iframe 宽 283 → `12.0747px`（= 16×283/375）。真机全部尺寸走 rem，**窄容器下所有 rem 尺寸等比缩小**——在编辑页预览里看到的组件比主聊天页小一圈，是这条律，不是 bug。

### 13.4 主题变量（29 个，body 内联 style）

平台由 JS 把 29 个 `--*` 变量写在 `body` 的**内联 style** 上，不是样式表规则、也不靠 class 切主题。常用几个（深色实测）：

| 变量 | 值 | 用途 |
|---|---|---|
| `--background-color` | `#17181A` | 页面背景 + **气泡背景** |
| `--primary-color` | `#FF6D97` | 强调色（亮色主题为 `#17AAFD`） |
| `--chat-content-font-color` | `#FFFFFF` | 气泡正文色 |
| `--card-background-color` | `#282A2E` | 卡片面 |
| `--input-background-color` | `#33353B` | 输入框底 |
| `--more-item-bg-color` | `#2C2E32` | 比 card 更亮一档 |

作者写 `var(--background-color)` 取色是真机可用的。浅色一套取值运行时不暴露，未实测——需要请回真机抓，别照猜的值定配色。

### 13.5 层级参照（组件 z-index 要压过谁）

| 节点 | z-index | 含义 |
|---|---|---|
| **总结剧情面板** | **1000000000** | 实测比别的弹窗高 5 个数量级，组件永远盖不过 |
| `.msg-option-scope` 长按菜单 | 99999 | 基本压不过，别试 |
| 其余弹窗（模型/对话设置、用户人设、分享、AI帮聊） | 10075 | uview `.u-popup` 标准档 |
| `.mm-left/right-side-container` | 9999 | 官方侧边挂载点，悬浮组件同级 |
| `.chat-bottom` | 999 | 输入栏，组件别挡它 |
| `.scroll-view`（内联） | 999 | 滚动区 |
| `.chat-scope-box` | 11 | 背景层 |
| `.modify-btn-scope` | 2 | 重开/编辑小圆钮，组件很容易盖住它 |

### 13.6 弹窗体系（全局美化必须逐个面板看过）

**做全局美化时，气泡只是一小部分**——顶栏/底栏按钮拉起的这些面板同样吃你的 CSS。全景预览已内建全部仿真，工具栏「弹窗仿真」逐个可开。

**通用外壳三层**（uview `u-popup`）：

```
uni-view.u-popup                      ← 恒 height:0，别拿它做可见性判据
├ .u-transition.u-fade-*                  遮罩：.u-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7)}
└ .u-transition.u-slide-up-*               内容层：position:fixed;bottom:0;left:0
  └ .u-popup__content                      ← 圆角/底色在这里，多为**内联 style**
    └ <各面板自己的 scope 类>
    └ .u-safe-bottom.u-safe-area-inset-bottom
```

> 🚨 **框架基线是白底**：`.u-popup__content{background-color:#fff}`（uview 原文）。深色全靠各面板的 scope 类或内联 style 覆盖出来。含义：**你的美化漏改哪个面板，那个面板就露白**。挨个开一遍是唯一可靠的自查方式。

| 入口 | 形态 | scope 根类 | 备注 |
|---|---|---|---|
| 快捷条·模型设置 | slide-up 半屏，圆角 10px | `.model-setting-scope.theme-dark` | scope 自带 `background:var(--background-color)`、`padding:0 1rem 1rem`、`height:34.375rem` |
| 快捷条·对话设置 | slide-up 69vh，**无圆角** | `.conv-style-modal` | scope 本身 `background:transparent`，底色由 content 内联给 → 只改 scope 改不动底色 |
| 快捷条·选择指令 | **不是弹窗** | — | 原地把 `.shortcut-bar` 加 `.hidden`、显示 `.instruction-bar`（26 个 `.instruction-chip`），高度仍 2.375rem |
| 快捷条·总结剧情 | slide-up 半屏，圆角 10px | `.summary-sheet.theme-dark` | z-index 1000000000；`max-height:84vh` |
| 快捷条·用户人设 | slide-up 69vh | `.role-profile-modal` + `.role-setting` | **用 `--lo*` 变量族**，见下方红线 |
| 快捷条·新的聊天 | 破坏性 | — | 会重置对话；本次未点，只做 UI 仿真 |
| 顶栏·评论(第1) | **路由跳转** | — | 跳 `#/pages/role/index`，不是弹窗 |
| 顶栏·分享(第2) | slide-up 矮条 | `.share-popup` | bg `#282A2E`(=`--card-background-color`)、h 167px；用框架自带 `.u-popup__content__close--top-right{top:15px;right:15px}` |
| 顶栏·收藏(第3) | 无 UI | — | 静默 toggle，无弹窗无 toast |
| 顶栏·刷新(第4) | 无弹窗 | — | 直接重新生成 |
| 输入框右·`+` | **不是弹窗** | `.more-scope` | 在 `.chat-bottom` 内展开，4 列 × 11 项，底栏 105px→**422px**（面板自身 317px）。面板排在 `.send-msg` **之后** → 在输入框**下方**、把输入框顶上去。组件若按"底栏 105px"算避让位置，这里会被压住。详见 §13.7 |
| 输入框左·AI帮聊💡 | **居中** dialog | `.alert-scope` | `u-fade-zoom-*` + `--round-center`(10px)；`width:18.75rem`；`.alert-title`/`.alert-content`/`.alert-checkbox`/`.alert-bottom(-double)`，按钮 `.ok-btn`(主题色)/`.cancel-btn` |

#### 🚨 `--lo*` 变量族：18 个「引用但从未定义」

用户人设面板（`.role-profile-modal` / `.role-setting`）走**另一套变量名**：`--loBackground-color`、`--loPrimary-color`、`--loPrimary-font-color`、`--loCard-background-color`、`--loInput-background-color`、`--lo-subtitle-color`、`--lo-disabled-*` 等共 **18 个**。

实测这 18 个在 `body` 上解析**全部为空**——页面从未定义它们，永远走 `var(--loX, 字面量)` 里的 fallback。所以：

- 改 `--loBackground-color` **不会**改变这些面板的颜色（没人定义过它，fallback 恒生效）。
- 要给用户人设面板换肤，只能**直接选类名**（`.role-setting`、`.role-setting .card`、`.role-setting .switch-card` …）。
- 与 §13.4 那 29 个真实变量是**两套独立体系**，别混。全景预览照真机**故意不定义**它们，好让你在预览阶段就发现"改 `--lo*` 没反应"。

---

## 13.7 底栏与输入框两态几何（2026-08-29 实机复核）

改全局美化动到输入区之前，先看这一节。全景预览已按此对齐（误差 ≤1px）。

### 底栏三态高度（`.chat-bottom`，fixed bottom、z-index 999）

| 状态 | 高度 | 组成 |
|---|---|---|
| 折叠 | **105px** | 快捷条 38 + 输入区 69（含 -1px 压边） |
| `+` 展开 | **422px** | 上面 105 + `.more-scope` 317 |
| `+` 展开 + 输入框展开 | **494px** | 输入框由 53→125px |

`.chat-body` 的 `padding-bottom` 恒 **170px**，**不随底栏变**——所以 `+` 展开时它会盖住最后一条消息。悬浮组件按"底栏 105px"算避让位置，`+` 一展开就被压住。

### `+` 按钮（`.more-options-scope`）

- 是 `.chat-input-scope` 的**兄弟**节点，不在输入框内部。
- **两态都留在输入框右侧外部**，不会移到输入框下方。
- 位置靠垫片：`padding-bottom` 折叠 `0.96875rem`(15.5px) / 展开或多行 `0.84375rem`(13.5px)，把 25×25 图标压到输入框视觉中线。左侧 AI帮聊 💡 用同一套垫片。
- 图标随开合换图：`ico_more_dark.png` ⇄ `ico_more_called_dark.png`。

### `.more-scope` 更多面板

挂在 `.chat-bottom-wapper` 下、**排在 `.send-msg` 之后** → 面板在输入框**下方**、把输入框整条往上顶。
`padding:12px 15px 15px`、`gap:10px`、`flex-wrap:wrap`；11 项 4 列，item 宽 `calc(25% - 0.625rem)`、高 90px（图标区 65 + 标题 25）。

### 输入框两态（`.chat-input-scope.has-toolbar`）

| | 折叠 | 展开（加 `.is-expanded`） |
|---|---|---|
| 高度 | **53px** | **125px** |
| padding | `5px 8px` | `10px` |
| 可见行 | `.chat-input-collapsed-row` 41px | 工具条 27 + 主输入 22 + `.chat-input-bottom-row` 40 |
| 工具条节点 | **不存在**（v-if） | 存在（粘贴 / 清空） |
| 发送钮 | 20×20 | 20×20 |

**两个 v-if 陷阱**：折叠态 `.chat-input-toolbar` 与关态 `.more-scope` 都是**节点根本不存在**，不是 `display:none`。所以 `querySelector('.more-scope')` 判底栏是否展开，在真机上是可靠的（关态返回 `null`）；但**预览是 CSS 隐藏、恒命中**，预览里请改用 `.more-options-scope[data-more=on]` 判。

**padding 分层**：上下 padding 一律挂在 `uni-textarea` **壳**上，内层 `textarea` 恒零上下 padding。折叠预览壳 24px / 内层 22px；展开主输入壳与内层同 22px。写美化时若把 padding 直接写到内层 textarea，每一态都会多撑一截。

**发送钮尺寸**：两态都是 `1.25rem`(20px)。样式表里另有一条 `.send-btn-icon{1.625rem}` 与 `.send-btn{3.75rem×2.34375rem}`，**实测都没被用到**，别照抄。

另有一个未记录的类 `.is-via`（给 `.chat-input-collapsed-preview` 加 `padding-bottom:0.25rem`），触发条件未测出。
