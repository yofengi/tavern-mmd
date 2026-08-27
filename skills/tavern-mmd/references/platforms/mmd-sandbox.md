# MMD沙盒模式平台技术规范（`<script>` 一等公民 + 官方 SDK 30 能力 / 12 事件）

> 本文档描述 MMD（魅魔岛/sexyai.top）的**新聊天页**。「沙盒模式」是本 skill 与用户侧的叫法，**官方口径只有「新页 / 新聊天页」**，开关是角色卡的 `chatVersion: 1`。官方全部资料里 grep「沙盒」零命中，所以跟平台客服/官方文档沟通时请说「新页」。
>
> **证据等级（本文四级标注，读者必须能一眼看出可信度）**：
>
> | 标注 | 含义 | 权重 |
> |---|---|---|
> | `【实机实测 2026-08-26】` | 真机浏览器注入探针采集（卡 64257 创卡页预览 `c64257.sbx.aitchat.org`，瘦环境）。**与官方文档冲突时以此为准** | 最高 |
> | `【源码确证】` | 逆向沙盒应用真实源码：`sandbox-app.js`(577KB) / `render.worker-*.js`(202KB) / `sandbox-app.css`(27KB) | 高 |
> | `【官方文档】` | 官方 PDF《MMD新版对话框角色卡制作手册》34 页 + 官方 skill `generating-role-card`（`contract.json`、`validate.mjs`） | 中（**已发现多处与实况不符**，逐条标注） |
> | `【待验证】` / `【原文未说明】` | 三方都没确证的空白，**不作推断补齐** | — |
>
> 优先级：**源码 > 实机 > 官方手册 > 官方 skill 校验脚本**。未标注的段落沿用原始官方文档级别。
>
> 🚨 **官方资料已被证伪的条目清单**（细节见对应章节）：`ready` 会补发且可做首屏（§2.6）· `stage.el()` 关闭时返回 `null`（§4.6）· 平台 chrome 占 8000–8999（§6.3）· `beginning` 上限 10240（§8）· 4 空格缩进变代码块（§6.5）· 外链脚本需域名白名单（§13）· 纯字面量匹配式是首选（§7.1）· 只有 10 个 `--chat-*` 变量（§6.1）· 只有 `onclick` 可用（§5.2）。
>
> **来源边界**：仍未确证的一律保留 `【待验证】` / `【原文未说明】`。当前已知空白：聊天页是否同施加 `Us` 长度截断（§8）· 15000 字固定传输在沙盒是否适用（§10.2）· `CACHE_QUOTA_BYTES` 超限行为（§4.4）· 取消订阅 API（§4）· 内联脚本是否对内容相同的多条去重（§2.4）· `SAFE_FOR_XML` 的无空格危险形态（§5.2）。
>
> **适用前提**：`chatVersion: 0` 或缺省 = 旧聊天页，**没有 `sdk.*`、没有 `[data-chat]` / `[data-slot]`、没有舞台**。本文所有能力只在新页存在。
>
> 🚨 **进门先记三条（新增，全是头号坑，详见 §2.6）**：① **作者脚本早于 DOM 执行** → 顶层任何 DOM 写入必失败，只能写在事件回调里。② **事件顺序是 `message:new → message:mount → message:done → ready`，`ready` 最后到** → 首屏只能挂 `message:mount`/`message:done`。③ **沙盒是跨源 iframe，不是 Shadow DOM** → 隔离已由 iframe 完成，`attachShadow` 是纯负债。

## 0. `chatVersion` 开关：进得去才谈别的

| 事实 | 来源 |
|---|---|
| `chatVersion: 1` 必写。漏写 = 规则照跑，但 `sdk.*`、`[data-chat]`、`[data-slot]`、舞台**全部失效** | 官方skill `SKILL.md:63` |
| `Number(chatVersion) !== 1` → 官方校验判 ERROR | `validate.mjs:210` |
| 创卡页表单默认 `0`，走旧聊天页 | 官方skill `SKILL.md:63` |
| **该字段只在「新建卡」导入时被读取**；给**已存在**的卡导入会被忽略 | 官方skill `SKILL.md:63` |

> 🚨 **真红线：无法通过导入把老卡升级成新页。** 已存在的卡导入 `chatVersion: 1` 该字段被直接忽略，规则会装上但 SDK 一个都不在，表现是「按钮全不响应、样式对一半」，页面上没有任何报错提示。**交付时必须书面提醒用户：新建卡，并在创卡页确认这张卡是新页**，否则整套沙盒方案零效果。

---

## 1. 与当前 MMD 的差异（决定脚本走哪条分支）

| 项 | 当前MMD `/mmd` | 沙盒模式 `/mmdsandbox` |
|---|---|---|
| `findRegex` 必须 slash literal | ✅ 强制（实测铁律，见 `mmd.md` §8） | ✅ **也应强制写 `/…/`**（`【实机实测 2026-08-26】`：裸字面量 `{{probe}}` 不生效，改 `/{{probe}}/` 立即生效。官方称字面量是首选，实机推翻，见 §7.1） |
| 导入 JSON 顶层键 | 4 键 `pageDepth` / `statusbar` / `beginning` / `regex_scripts` | **恰好 6 键**（多 `chatVersion` / `personality`） |
| `id` 取值 | 时间戳类 | **必须负数**，导入时重编号 |
| 整卡 PNG / chara_card_v2 | ✅ 仅 v2，PNG 承载 | ❌ **官方禁 PNG 整卡**；交付 = 正则 JSON + persona 文本 |
| `<script>` 地位 | 可执行，但 per-message 自渲染/定位不可用 | **一等公民**：装卡即抽出、整卡跑一次；per-message 由 `message:mount` 事件顶替 |
| 状态栏引擎载体 | `img onerror`（唯一可靠 per-message 载体） | **`<script>` + SDK**；`img onerror` 点火器被官方明令禁止 |
| 官方 SDK | ❌ 无 | ✅ 30 能力 / 12 事件 |
| 稳定选择器 | ❌ 平台 class 名会变 | ✅ `[data-chat]` / `[data-slot]` 承诺不改名 |
| 长期面板 | 无处安放（挂气泡会随气泡销毁） | ✅ 舞台 `sdk.stage` |
| 跨设备存档 | ❌ | ✅ `sdk.save`（落服务端） |
| CSS 变量 | 无平台约定 | ✅ **14 个 `--chat-*`** + `--rpx`（`【实机实测】`；手册只记 10 个，见 §6.1） |
| 运行容器 | 宿主同文档 | ✅ **跨源 iframe** `c<卡片ID>.sbx.aitchat.org`（`【实机实测】`，见 §2.3） |
| `document.currentScript` | 可用（实测） | ❌ **恒为 `null`**（`【源码确证】`+`【实机实测】`，见 §2.3） |
| 外部 `fetch` / 外部字体 / 外部样式表 | 视宿主 CSP | ❌ **CSP 封死**（`connect-src 'self'`，见 §13） |
| 世界书条目标题 20 字 | ✅ | ✅ 本 skill 保留，但降级为 WARN（见 §10） |

**共通不变**：正则条数 130、替换产物要再过一遍 Markdown、规则按顺序跑且后条会扫到前条产物。

⚠️ **不共通**：沙盒字段长度有另一组源码归一常量（`name=200`、`regex=4096`、`content=100000`、`beginning=4000`）。其中 `beginning=4000` 与 `replaceString` 的编辑器 20000／导入 100000 双路径已实测；`scriptName` 20/200、`findRegex` 1000/4096 目前只是 UI 显示值与源码观察值，双路径及超限语义仍待验证，详见 §8。

---

## 2. 唯一注入口与执行模型

作者在创卡页跟界面有关的**只有一处**：正则替换规则的「**替换内容**」。HTML、`<style>`、`<script>` 全写在那里（手册开篇）。不写整页 HTML 文件，不上传 JS 文件 —— 所有代码都是某条规则的 `replaceString` 字符串。

功能栏（聊天页顶部下面那一条）来自角色卡 `statusbar` 字段，**同样会过一遍你的规则**。因为 `statusbar` 只有 200 字，标准写法是 `statusbar` 里只放 `{{hud}}`，真界面写在规则里。

### 2.1 `<script>` 是一等公民

以下全部出自手册第 2 / 3 章：

- **抽取时机**：装卡那一刻被抽出，按规则顺序收集。
- **执行次数**：**整张卡只跑一次**（不是每条消息一次）。⚠️ `【源码确证】`**「只跑一次」仅在聊天页 / 分享页成立；创卡页预览会反复重跑**（每改一次规则重装一遍）→ **脚本必须幂等，自带「已初始化」哨兵**，否则预览里会叠加多份。
- **是否需要被匹配命中**：**不需要** —— `<style>` / `<script>` 不论这条规则有没有匹配到都会装上。`【源码确证】`抽取发生在装卡时、与匹配解耦。
- **执行机制** `【源码确证】`：内联脚本经 `(0,eval)` 执行，被包进 `(function(){…}).call(window)`，顶层 `var/let/const/function/class` 由编译器**显式回挂 `window`**（`if(typeof X!=='undefined')this.X=X;`）→ 所以 `onclick="tap()"` 找得到。普通标签上 `on*` 可用，**`svg` 内部的 `on*` 会被删**（见 §5.2）。
- `type="module"` `【源码确证】`：被接受但**按经典脚本执行** → 里面写 `import` 必报错。
- **错误隔离**：一段脚本报错**只废掉它自己**，后面规则的脚本照跑；不弹窗，进调试面板。
- **切会话**：脚本**不重跑**，订阅**不清除**，舞台会被平台关掉 → 属于某个会话的计数要自己在 `conversation:switch` 里清。

> 🚨 **真红线：脚本执行时页面 DOM 还没建好。** 详见 §2.6 —— 顶层写 DOM 必然拿到 `null`，这是沙盒的头号坑。

因为「不命中也会装上」，**不能靠「让规则不匹配」来关掉样式**；反过来，官方首选写法就是利用这一点：

> **专开一条规则只放 `<script>`，匹配式填一个正文里用不到的词**（官方示例卡即 `scriptName: "kit"` / `findRegex: "{{eg-kit}}"`，谁都不引用）。同理一条只放 `<style>`，命名 `卡名-style`。
>
> ⚠️ **匹配式仍要写 slash 形态**（`/卡名-kit/`）—— 实机上裸字面量不生效（§7.1）；且**绝不能匹配空串**（§7.6）。

> 🚨 **真红线：`img onerror` 点火器与 teapot 系写法在沙盒模式被官方明令禁止。** 官方禁止清单逐字包含「teapot：`onerror` 图、`window.teapot*`、CoC 注入」。理由是 `<script>` 已经装卡即抽出、必然执行，点火器不再有存在意义。当前 MMD 那套 `img onerror` 引擎（`../beautify/statusbar-radar.md`）**不要移植到沙盒模式**，要重写成 `<script>` + `sdk.on('message:mount')`。

### 2.2 per-message 绑定：`message:mount` 顶替自渲染

脚本只跑一次，而气泡会滚走再滚回来。给每条气泡里的按钮绑点击**必须**写在 `sdk.on('message:mount')` 里：

```html
<script>
sdk.on('message:mount', function () {
  const btn = document.querySelector('.hello-btn');
  if (!btn) return;
  btn.addEventListener('click', function () {
    sdk.input.set('你好');
  });
});
</script>
```

> 🚨 **`message:mount` 回调里的 `document.querySelector` 被收窄，但收窄的对象是「气泡内元素的过滤」，平台级节点仍可达。**
>
> **机制** `【源码确证】`：不是 Proxy，是平台**全局改写** `Document.prototype.querySelector` / `querySelectorAll` / `getElementById` / `getElementsByClassName` / `getElementsByTagName`，配一个模块级游标 `gc`：
>
> ```js
> Document.prototype.querySelector = function (e) { return xc(this, e) }
> Document.prototype.getElementById = function (e) { if (gc) { …mc.call(gc, `[id="…"]`)… } }
> ```
>
> **实机修正** `【实机实测 2026-08-26】`：在 mount 回调内（`gc` 非 null 时），`document.querySelector('[data-chat="root"]')` 与 `document.body.querySelector(...)` **都成功**（探针 `qs_from_document_works=true`、`body_qs_works=true`）。→ 原先「要查整页不能用它」的说法**过于绝对**，已修正：查功能栏、舞台、root 这类平台节点，`document.querySelector` 可用。
>
> **但纪律不变**：`gc` 是模块级游标，**跨 `await` / `setTimeout` 即失效**。所以**气泡内的元素必须在回调内就地抓引用存到闭包**，绝不能异步之后再去查。`gc === null` 时气泡内元素查不到（`click`/`input`/`change`/`keydown` 的捕获阶段会自动收窄，所以事件处理器里通常是有效的）。

> 🚨 **`sdk.on` 只写在脚本体，绝不写进 `message:mount` 回调**。否则每挂一条气泡就多订一份，同一件事会触发很多次。官方校验对此有专项 WARN（`sdk.on('message:mount'` 之后 1200 字符内又出现 `sdk.on(`）。

### 2.3 运行容器形态与 `document.currentScript`（原「未说明」，现已确证）

> 本节两条结论原为 `【原文未说明】`（当时只有官方文字资料，官方全目录 grep `shadow` / `currentScript` 均零命中）。现已由**源码逆向 + 真机探针**双重确证，标记撤销。

#### 沙盒 = 跨源 iframe 里的独立 Vue 应用 `【源码确证】` + `【实机实测 2026-08-26】`

沙盒是部署在 **`c<卡片ID>.sbx.aitchat.org`** 的独立 Vue 应用（页面 `<title>` 为 `chat sandbox`），以**跨源 iframe** 嵌入宿主 `h5.aitchat.org`。它自身不读卡片数据，**必须由宿主 postMessage 握手投喂卡片配置** —— 直接打开该 URL 会停在 `waiting for host handshake`。

| 探针项 | 实测值 | 结论 |
|---|---|---|
| `window === window.top` | `false` | 在 iframe 里 |
| `window.frameElement` | `null(cross-origin)` | **跨源**，拿不到宿主节点 |
| `location.origin` | `https://c64257.sbx.aitchat.org` | 每张卡一个独立子域 |
| 宿主 iframe `sandbox` | `allow-scripts allow-same-origin allow-forms allow-modals allow-downloads` | `【实机只读复核 2026-08-27】`；这是宿主容器权限，作者内容仍受净化白名单与 CSP 约束 |
| 作者节点 `getRootNode() === document` | `true` | **不是 Shadow DOM**，作者内容就在 iframe 主文档里 |
| `localStorage` | 可用 | 见下 |

> 🚨 **真红线：Shadow DOM 隔离（影渲法 / ShadowCast）在沙盒是纯负债，零收益。**
>
> **iframe 本身就是隔离边界** —— 作者代码不可能污染宿主，宿主样式也漏不进来。再套一层 `attachShadow` 只会额外付出：样式要重复注入、`querySelector` 收窄机制与 shadow 边界互相打架、平台的 `--chat-*` 变量继承链变复杂。原文档 §11.2 曾以「`currentScript` 未说明」为由劝阻移植，理由不够硬；**现在的根本理由是隔离已经由平台完成，再隔离没有任何东西可隔**。

**`localStorage`** `【实机实测】`：可用，且**按卡天然隔离**（每张卡一个独立源）→ 可以放单卡本地偏好（面板折叠状态、主题选择）。但**不能跨卡共享**，也**不跨设备** —— 跨设备进度仍然只能走 `sdk.save`（§4.5）。

#### `document.currentScript` 恒为 `null` `【源码确证】` + `【实机实测 2026-08-26】`

结论从「不要用它」升级为「**它恒为 `null`，用了必然拿不到东西**」：

- `【源码确证】`：内联脚本经 `(0,eval)` 执行，被包进 `(function(){…}).call(window)` —— **根本没有 script 节点存在**，所以 `currentScript` 无从可取。全文该标识符只在 DOMPurify 内部出现过。
- `【实机实测】`：脚本顶层取 `document.currentScript` → `null`；在事件回调里再取 → **仍是 `null`**（探针 `toplevel_currentScript=null`、`now_currentScript=null`）。

→ **脚本无法自定位**。per-message 定位一律走 `message:mount`；需要找自己的节点就靠**固定 id / class 约定**。

> 例外：**外链 `<script src>` 走的是真 script 节点**，所以在外链脚本里 `document.currentScript` 是可用的。但沙盒 CSP 允许任意 https 外链却封死 `fetch`（§13），外链脚本的价值有限，且有「未被 await」的坑（§2.4）。

作者代码里可以直接写 `document.querySelector`、`document.createElement`、`el.closest(...)`、`document.body` —— 这一点手册、官方 fixture 与实机探针三方一致。

### 2.4 外链 `<script src>`

`【官方文档】`手册第 2 章：按书写顺序加载，**前一个加载完才跑后面的代码**；**同一个 URL 只加载一次**；地址必须 `https://` 开头，**`http://` 被直接跳过**；加载失败**不中断整张卡**，在调试面板留一行；域名还要在**平台白名单**里，自建域名先问平台。

**两处已被源码修正**：

- 🚨 **不存在应用层域名白名单** `【源码确证】`：应用只校验 `^https://`，域名放行由 CSP `script-src … https:` 决定 → **任意 https 域名都能加载**。手册「需平台白名单」与实况不符（细节见 §13）。
- 🚨 **外链脚本没有被 await** `【源码确证】`：`d_(c.authorScripts)` 在 `g_` 中无 `await` → 手册「前一个加载完才跑后面的代码」不可靠。实际后果是 **第一个外链之后的内联脚本注册的 `ready` 回调永久收不到**（`ready` 本身也没有补发，见 §2.6）。→ **要用外链就把关键订阅写在外链之前的内联脚本里**，或干脆不用外链。

```html
<script src="https://cdn.example.com/tiny-engine.min.js"></script>
<script>
  sdk.on('message:mount', function () {
    const box = document.querySelector('.engine-box');
    if (!box || !window.TinyEngine) return;
    TinyEngine.mount(box);
  });
</script>
```

内联脚本是否对「内容相同的多条」去重 `【原文未说明】`（明确的只有「整张卡只跑一次」与「外链同 URL 只加载一次」）。

### 2.5 调试与瘦预览

- **调试面板**：聊天页 URL 加 `?sdkDebug=1`，配 `sdk.debug.log(...)`。手机上没有控制台，关键路径全靠这个。面板内容包含作者日志、**脚本报错**、**外链没加载上**、未处理的 Promise 失败。
- **瘦预览**：创卡页里那个预览是简化环境，写类能力大多不可用，**样式与舞台可用**；逐能力待遇见 §4.1。日常开发先在本地沙盒仿真页跑 `chat` 与 `thin-preview` 两个 profile；真实聊天页只用于仿真标为 `probe-needed` 的边界和用户授权后的最终人工验收，不作为 AI 默认登录的回归环境。

#### 2.5.1 瘦预览的真实行为（`【实机实测 2026-08-26】`，修正「一律 `NOT_SUPPORTED`」的说法）

原文按官方口径写成「一律 `NOT_SUPPORTED`」（即返回错误码）。实测发现**表现形式不统一，其中一种会炸整卡**：

| 能力 | 瘦预览实测行为 | 官方/包分析原说法 | 作者对策 |
|---|---|---|---|
| `save.get` / `save.keys` | 🚨 **同步抛 `SdkError`** | 返回 `NOT_SUPPORTED` | **必须 `try/catch`** —— 否则创卡页预览里读存档这一行直接把整卡脚本废掉，且页面上没有报错提示。**这是最容易翻车的一处** |
| `cache.get` | 返回 `undefined`，**不抛** | 可用 | 可直接当降级层用 |
| `composer.visible()` | **`true`**（真实可用，与 root 上 `data-composer="visible"` 一致） | `false` 静默降级 | 可信，不是降级值 |
| `input.get()` | `""` | `''` 降级 | 一致 |
| `input.getCursor()` | `0` | `0` 降级 | 一致 |
| `role.get()` / `user.get()` | **返回真实数据**（实测 `{"name":"测试",…}` / `{"nickname":"洛璃",…}`） | 可用 | 可信 |
| `stage.el()` | 返回 `<DIV>`（**即使 `stage.visible()===false`**） | 未打开时返回 `null` | 见 §4.6，**只能用 `visible()` 判开关** |

```html
<script>
function loadSave(key) {
  try {
    return sdk.save.get(key);            // 瘦预览会同步 throw SdkError
  } catch (e) {
    sdk.debug.log('save 不可用，走降级', e && e.code);
    return null;
  }
}
</script>
```

### 2.6 🚨🚨 执行时机、事件顺序与载荷形状（本节全部为新增实测事实，是沙盒的头号坑）

> 官方手册完全没写执行时机，并且把 `ready` 描述成「页面就绪、可做首屏、晚订阅会补发」—— **三点全错**。本节结论全部来自 `【实机实测 2026-08-26】` + `【源码确证】`。

#### 2.6.1 作者脚本在 DOM 渲染之前就执行完毕

探针在**脚本顶层**调 `document.getElementById('pbOut')` 去取自己刚写入功能栏的节点 → **返回 `null`**（`toplevel_found_pbOut=false`）。同一个探针**在事件回调里**再取同一个 id → **成功**。

原因：`<style>` / `<script>` 装卡即抽出并**立即执行**，而功能栏与消息 HTML 由 Vue **在之后**才挂进 DOM。

> 🚨 **真红线：顶层直接渲染必然失败，任何 DOM 写入都必须发生在事件回调内。**
>
> 症状是「我明明写了 `appendChild`，页面上什么都没有，也没报错」。顶层只能做：定义函数、挂 `window`、`sdk.on(...)` 订阅、准备数据。**碰 DOM 一律进回调。**

```html
<script>
// ✗ 不要这样：顶层碰 DOM
var box = document.getElementById('my-hud');    // 恒为 null
box.innerHTML = '…';                            // 直接抛错，整段脚本废掉

// ✓ 要这样：顶层只定义与订阅，DOM 全在回调里
function renderHud() {
  var box = document.getElementById('my-hud');
  if (!box || box.__inited) return;             // 幂等哨兵：创卡页预览会重跑
  box.__inited = 1;
  box.appendChild(document.createTextNode('就绪'));
}
sdk.on('message:mount', renderHud);             // 首屏靠这个，不是 ready
sdk.on('message:done', renderHud);
</script>
```

#### 2.6.2 冷启动事件顺序：`ready` 是最后到的

`【实机实测】`同一探针按到达顺序累计（探针 `ORDER` 行逐字）：

```
message:new  →  message:mount  →  message:done  →  ready
```

**`ready` 在首条消息 mount 且 done 之后才到**，与「ready 表示页面就绪、可以做首屏」的直觉完全相反。

并且 `【源码确证】`：**`ready` 没有 late replay（不补发）**；有补发的是 **`message:mount` 与 `message:done`**。官方手册说「`ready` 这类只发一次的事件会补发给后来的订阅者」，**是错的**。

> 🚨 **真红线：首屏渲染只能挂 `message:mount` / `message:done`，挂 `ready` 会晚一整轮。**
>
> 双重原因：① 顺序上 `ready` 最后到；② 它不补发，配合 §2.4 的「外链脚本未被 await」，第一个外链之后注册的 `ready` 回调**永久收不到**。→ **`ready` 只当「时序信号」用**（比如打一行调试日志），不承载首屏。

#### 2.6.3 事件载荷形状：恰好 4 键，正文字段名就是 `content`

`【实机实测】`对每个事件的第一次触发做 `for...in` + `Object.keys` 枚举，`message:new` / `message:mount` / `message:done` **三者载荷形状完全一致**：

```js
{ content: string, id: string, role: 'ai' | 'user', serverId: string | null }
```

| 事实 | 意义 |
|---|---|
| **正文字段名就是 `content`**，恰好 4 键 | 不用猜 `text` / `message` / `body` / `raw`，**只读 `content`** |
| `id` 是**字符串**（开场白实测为 `"greeting"`） | 不是数字，别拿它做算术 |
| `serverId` 开场白时为 `null` | 它是 `data-msg-id` 的对应物。**`serverId === null` 表示服务端还不认得这条 → 不可 `message.edit`**，调用前必须判空（§4.3） |
| `role` 实测为 `"ai"` | 与气泡上 `data-from` 对应 |
| **SDK 回调只传 1 个实参**（`argcount=1`） | 官方契约里写的 `fn(payload, bubbleRoot)` 的第二参 `bubbleRoot` **不是 SDK 提供的**，别指望它 |
| `ready` 载荷为 `undefined` | 纯时序信号，不携带数据 |

→ **取正文一律 `payload.content`；判断可编辑一律 `payload.serverId != null`。**

---

## 3. 🚨 「消息生成中」占位陷阱（官方全篇强调 6 处，头号杀手）

> 🚨 **真红线：空 AI 气泡一挂上，`[data-chat="message-body"]` 里写的是平台占位「消息生成中」，不是模型回的字。**

用户一点发送（或你调了 `sdk.message.send`），平台**立刻**挂一条空的 AI 气泡，`message:mount` 马上就来。这时：

- `msg.content` 是空的
- `[data-chat="message-body"]` 里是平台占位「消息生成中」
- 接口的 stream 可能**已经在吐字**，占位还在

正确取值路径：**跟字**（打字机伴随动画）用 `message:stream` 的 `msg.content`（已攒起来的原文，累积量）；**收尾**（读完整回复、切剧情、推进选项）用 `message:done` 的 `msg.content`；`message:mount` **只**用来给这条气泡里的按钮绑点击 —— 在它里面读正文这种用法**不存在**。

「消息生成中」「消息生成超时…」「……」**都不是正文**。`content` 空时也**不要退回去读 DOM** —— 读到占位就清了等待态，后面的 `stream` / `done` 全丢掉，表现是「界面永远停在加载中」或「剧情跳过一轮」。

官方给的判别函数（逐字，含平台占位串的实际前缀 `消息生成`）：

```html
<script>
function isReplyText(s) {
  s = String(s == null ? '' : s).replace(/^\s+|\s+$/g, '');
  if (!s) return false;
  if (s.indexOf('消息生成') === 0 || s === '……') return false;
  return true;
}
sdk.on('message:stream', function (msg) {
  if (!msg || msg.role !== 'ai') return;
  if (!isReplyText(msg.content)) return;
  sdk.debug.log('跟字', msg.content);
});
sdk.on('message:done', function (msg) {
  if (!isReplyText(msg && msg.content)) return;
  sdk.debug.log('说完了', msg.content);
});
</script>
```

可用载荷字段 `【实机实测 2026-08-26】`：**恰好 4 个** —— `msg.content`、`msg.id`（字符串）、`msg.role`（`'ai'` / `'user'`）、`msg.serverId`（`string | null`）。**正文字段名就是 `content`，不用猜别的名字**，完整形状见 §2.6.3。

官方校验有专项 WARN：同一条规则里同时出现「订阅 `message:mount`」+「引用 `[data-chat="message-body"]`」+「有 `message.send(` 或 `message:stream`」就告警。

⚠️ 注意 `message:mount` 的载荷**也带 `content`**（与 `new`/`done` 同形状）。所以「在 `message:mount` 里读正文」这件事技术上做得到 —— 但**读到的仍可能是空串**（空气泡刚挂上时），判别仍必须过 `isReplyText`。「不要在 mount 里读正文」这条纪律不变，理由从「载荷里没有」修正为「**载荷里有但内容不可信**」。

---

## 4. SDK：30 能力 / 12 事件

`sdk` 是平台挂在页面上的对象。**能力名与事件名拼错都不会报错，只是永远不生效／永不触发** —— 所以以下所有名字必须逐字照抄。官方校验会拿 `contract.json` 核对：`sdk.X` / `sdk.X.Y` 不在能力表 → ERROR；`sdk.on('X')` 的 `X` 不在事件表 → ERROR。

> 🚨 **`sdk.once` 与 `sdk.off` 都不存在。** `contract.json.capabilities` 里只有 `on`；`【实机实测 2026-08-26】`双重确认 `sdk.once` 与 `sdk.off` **均为 `undefined`**。写 `sdk.once(...)` 官方校验直接判 ERROR。
>
> **面向作者的取消订阅 API 仍 `【原文未说明】`**。`【源码确证】`内部唯一的退订是 `Ac()`，它**清掉所有脚本的全部订阅**（跨脚本互相干扰），不是给作者用的。→ **脚本必须单例 + 幂等，自带「已初始化」哨兵，绝不重复订阅。**
>
> 🚨 **原文这里写过「`ready` 会补发给后来的订阅者，所以不需要 `once`」—— 这是官方手册的错误说法，已推翻。** `【源码确证】``ready` **没有补发**；有补发的是 `message:mount` 与 `message:done`。详见 §2.6.2。
>
> `【实机实测】``sdk` 顶层键恰为 11 个：`cache, composer, debug, input, message, on, role, save, stage, user, version`。`sdk` **未冻结、非 Proxy**（`Object.isFrozen(sdk) === false`）→ 建议启动时把要用的方法快照到局部变量。

### 4.1 能力全表（30 个，签名逐字）

「瘦预览」列 = 创卡页预览环境的待遇。`sync` = 同步，`async` = **返回 Promise，必须 `.catch`**。

⚠️ **瘦预览列已按 `【实机实测 2026-08-26】` 修正**，加粗项是与官方口径不同的实测值。逐项说明与代码见 §2.5.1。

| 能力 | 参数 | 返回 | 同步性 | 瘦预览 |
|---|---|---|---|---|
| `input.get` | — | `string` | sync | 回空串（实测 `""`） |
| `input.set` | `text: string` | `void` | sync | `NOT_SUPPORTED` |
| `input.add` | `text: string` | `void` | sync | `NOT_SUPPORTED` |
| `input.insert` | `text: string` | `void` | sync | `NOT_SUPPORTED` |
| `input.clear` | — | `void` | sync | `NOT_SUPPORTED` |
| `input.focus` | — | `void` | sync | `NOT_SUPPORTED` |
| `input.blur` | — | `void` | sync | `NOT_SUPPORTED` |
| `input.getCursor` | — | `number` | sync | 回 0 |
| `input.setCursor` | `n: number` | `void` | sync | `NOT_SUPPORTED` |
| `composer.show` | — | `void` | sync | `NOT_SUPPORTED` |
| `composer.hide` | — | `void` | sync | `NOT_SUPPORTED` |
| `composer.visible` | — | `boolean` | sync | **实测回 `true`（真实可用，不是降级值）** |
| `message.send` | `text?: string` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `message.edit` | `id: string`, `text: string` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `cache.get` | `key: string` | `unknown` | sync | 可用（实测回 `undefined`，**不抛**） |
| `cache.set` | `key: string`, `value: unknown` | `void` | sync | 可用 |
| `cache.remove` | `key: string` | `void` | sync | 可用 |
| `save.get` | `key: string` | `unknown` | sync | 🚨 **实测同步抛 `SdkError`（不是返回错误码）→ 必须 `try/catch`** |
| `save.set` | `key: string`, `value: unknown` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `save.remove` | `key: string` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `save.keys` | — | `string[]` | sync | 🚨 **实测同步抛 `SdkError` → 必须 `try/catch`** |
| `stage.open` | `mode?: 'content' \| 'full'` | `void` | sync | 可用 |
| `stage.close` | — | `void` | sync | 可用 |
| `stage.el` | — | `HTMLElement`（🚨 **实测关闭时也返回 DIV，不是 `null`**） | sync | 可用 |
| `stage.visible` | — | `boolean` | sync | 可用（**判断舞台开关只能用它**） |
| `role.get` | — | `{ name: string; avatarUrl: string }` | sync | 可用（实测返回真实数据） |
| `user.get` | — | `{ nickname: string; avatarUrl: string }` | sync | 可用（实测返回真实数据） |
| `on` | `event: string`, `cb: (payload) => void` | `void` | sync | 可用 |
| `debug.log` | `...args: unknown[]` | `void` | sync | 可用 |
| `version` | —（**是值，不是函数**，恒为 `'1'`） | `string` | — | 可用 |

> 瘦预览里**写类**能力（`input.set/add/insert/clear`、`composer.show/hide`、`message.send/edit`、`save.set/remove`）不可用；**读类**能力实测大多真实可用（`composer.visible`、`role.get`、`user.get`、`cache.get`、`stage.*`）。所以创卡页能验样式、舞台、角色数据，**输入框写入、发送、存档必须回聊天页验**。
>
> 🚨 **两处别记错**：`save.get`/`save.keys` 是**抛异常**不是返回错误码（不 catch 就炸整卡）；`composer.visible()` 在瘦预览是**真值 `true`** 不是降级 `false`。

### 4.2 `sdk.input.*` —— 输入框（9 个）

最常见用法：点选项 → `sdk.input.set('你好')` 把话填进输入框 → 用户自己按发送。

`set` / `add` / `insert` / `clear` 在**用户正在用拼音打字、字还没上屏**时会失败（IME 组合期抛 `INVALID_ARGS`），点按钮的路径撞不上。`insert` 取不到光标就落到末尾，别假设插入后光标停在原处。`clear` 在用户点发送后平台已经清了，不必自己再清。`focus` **别在页面刚打开时调**，手机键盘会盖住你刚画的东西。`setCursor` **没有选区 API**，别拿它模拟选区。`get` 别轮询判断用户在打字，用 `input:change` 事件。

### 4.3 `sdk.composer.*` 与 `sdk.message.*`

`composer.show` **覆盖卡片配置**；`composer.hide` 顺手收键盘 —— **藏了就必须自己给用户一条发消息的路**，否则他只能退出。

`message.*` 默认不该用：优先 `input.set` 把话填进输入框让用户自己发。这两个会**以用户的身份说话**，有授权、有限频。

> 🚨 **`message.send` 必须在用户点击的当帧内调用**才不弹授权。定时器里发会先问用户。**点了之后不要先 `await` 再 `send`** —— 那已经不算手势了，会走授权路径拿 `UNAUTHORIZED`。

```html
<script>
function sendNow() {
  sdk.message.send('我准备好了').catch(function (err) {
    sdk.debug.log('发送失败', err.code);   // 失败必须 .catch，页面上不会有提示
  });
}
</script>
```

`send` 不传文字就发当前输入框内容。**别在 `message:done` 里无条件再 `send`**，那是自问自答死循环（官方校验对「同条规则里既有 `message:done` 又有 `sdk.message.send(`」有专项 WARN）。

`edit` 的 `id` 来自气泡上的 `data-msg-id`。**刚插入、服务端还不认得的消息没有 id → 调用前必须判空**，别拿 `null` 拼字符串。

> 🚨 **更省事的判空口径** `【实机实测 2026-08-26】`：事件载荷里的 **`msg.serverId` 就是 `data-msg-id` 的对应物**（开场白实测为 `null`）。所以不必去 DOM 上 `closest` + `getAttribute`，直接在回调里判 `msg.serverId != null` 即可 —— **`serverId === null` 就是「服务端还不认得这条，不可编辑」**。载荷完整形状见 §2.6.3。
>
> ```js
> sdk.on('message:done', function (msg) {
>   if (!msg || msg.serverId == null) return;      // 不可编辑
>   sdk.message.edit(msg.serverId, '改过的正文').catch(function (e) {
>     sdk.debug.log('没改成', e.code);
>   });
> });
> ```

```html
<script>
sdk.on('message:mount', function () {
  const btn = document.querySelector('.rewrite-btn');
  if (!btn) return;
  btn.addEventListener('click', function () {
    const body = document.querySelector('[data-chat="message-body"]');
    const card = body && body.closest('[data-chat="message"]');
    const id = card && card.getAttribute('data-msg-id');
    if (!id) return;
    sdk.message.edit(id, '改过的正文').catch(function (err) {
      sdk.debug.log('没改成', err.code);
    });
  });
});
</script>
```

### 4.4 `sdk.cache.*` —— 临时缓存

**刷新页面就没**。只适合「面板开着还是关着」「滚动位置」这类当场要用的状态。**进度、血量一律用 `save`**。配额 `CACHE_QUOTA_BYTES` = 1048576（1 MiB），**超限行为仍 `【待验证】`**（源码未定位到明确的超限分支，实机也没测）。

`cache.get` 在瘦预览返回 `undefined` 且**不抛异常** `【实机实测 2026-08-26】` → 可以放心当 `save` 的降级层用（`save` 会抛，见 §2.5.1）。

**另有一条 `localStorage` 通路** `【实机实测】`：沙盒里 `localStorage` 可用，且因为每张卡一个独立源（`c<卡片ID>.sbx.aitchat.org`）而**天然按卡隔离**。它比 `cache` 强的地方是**刷新不丢**；比 `save` 弱的地方是**不跨设备、不跨卡**。定位：单卡本地偏好（面板折叠、音量、已读引导）用 `localStorage`，当场状态用 `cache`，玩法进度用 `save`。

### 4.5 `sdk.save.*` —— 存档

落到服务端，**换设备还在**。约束：

| 项 | 值 |
|---|---|
| `SAVE_MAX_KEYS` | 官方写 **10 个**。⚠️ `【源码确证】`**该常量不存在于沙盒**：上限由宿主动态下发且被沙盒丢弃，沙盒侧**零条数校验** → 别把 10 写死进代码，但纪律不变：**把整套状态打成一包（一个对象）再存** |
| 存档名长度 | ≤ **64 字符** |
| 存档名字符 | **不能含冒号**（`hp:cur` 会被拒，用 `hp_cur`） |
| 值 | 必须可 `JSON.stringify`（函数、`Map`、循环引用存不进去） |
| 写入限频 | `save.set` 1 分钟 **20** 次。`【源码确证】``save.remove` **无限频** |

`save.get` 是**同步**的，读的是进页时预载进来的那份内存副本。`set` / `remove` 必须 `.catch`（写法同上面 `message.send`），失败时页面上不会有任何提示。

> 🚨 **真红线：`save.get` / `save.keys` 在创卡页瘦预览会同步抛 `SdkError`，不 catch 就炸整卡。** `【实机实测 2026-08-26】`
>
> 官方口径是「瘦预览返回 `NOT_SUPPORTED`」，实测是 **throw**。后果：读存档那一行直接把整段脚本废掉，页面上没有任何报错提示，表现是「预览里整卡完全不工作，聊天页却正常」。**所有 `save.get` / `save.keys` 调用必须包 `try/catch`**，代码见 §2.5.1。这是沙盒最容易翻车的一处。

> 🚨 **真红线：游客存档退出即失，且作者永远测不出来。** 游客身上写存档不报错，但只留在本地，**他登录时会被丢掉、不会迁移**。你的代码在游客和登录用户上表现一模一样 —— 而**你自己是登录态，永远碰不到这个差别**。平台会在游客第一次写存档时提示他登录。**所以别把「必须攒进度」做成这张卡唯一的玩法**：进度丢了也要能玩下去。

`save.set` 别在每帧或每次输入都写，把状态攒起来再写一次。

### 4.6 `sdk.stage.*` —— 舞台（瘦预览**全部可用**）

一块盖在聊天页上的空盒子，专门放要一直在的界面（地图、背包、小游戏）。

- `'content'` 盖住消息区，**顶栏和输入框还能用**；`'full'` 盖住整屏（**盖不住授权 / 充值那种系统弹窗**）；不传参默认 `content`。
- 🚨 **`stage.el()` 未打开时不返回 `null`** —— 手册明说返回 `null`，**实测是错的**，见下方红线。返回节点的内部平台不碰。
- **关掉再开，盒子里的东西还在**，不必每次重建。
- **自己调 `stage.close()` 不触发 `stage:close`**（那条只在平台关时发）。切会话时舞台会被平台关掉。

> 🚨 **真红线：判断舞台开关只能用 `stage.visible()`，绝不能靠 `stage.el()` 是否为 `null`。** `【实机实测 2026-08-26】`
>
> 实测 `stage.visible() === false` 时 `stage.el()` **仍然返回 `<DIV>`**（探针 `stage_visible=false` / `stage_el=<DIV>`）。手册「没打开时是 `null`」是**错的**。
>
> 后果：写 `if (sdk.stage.el()) { …认为舞台开着… }` 会**恒真**，于是「关掉后仍往里画」、「重复初始化」、「以为开着其实用户看不见」。判空写法要改成：
>
> ```js
> if (!sdk.stage.visible()) sdk.stage.open('content');
> var el = sdk.stage.el();
> if (!el) return;                  // 仍然保留判空，属防御，但它不代表「舞台关着」
> ```

> 🚨 **长期面板必须挂舞台，不能挂气泡。** 气泡滚出屏幕就被销毁，挂在气泡里的画布/面板等于随时会没（症状：「画的东西滚一会儿就没了」）。同时舞台**在虚拟化列表之外，不随消息滚动**，别把它当消息容器用。

```html
<script>
function openBoard() {
  sdk.stage.open('content');
  const el = sdk.stage.el();
  if (!el || el.querySelector('canvas')) return;
  const canvas = document.createElement('canvas');
  canvas.width = 320;
  canvas.height = 240;
  el.appendChild(canvas);
}
sdk.on('stage:close', function () {
  sdk.debug.log('舞台被平台关了');
});
</script>
```

⚠️ 上面这段示例用 `el.querySelector('canvas')` 做「已建过就不重建」的判断 —— 这是**正确写法**，因为它查的是舞台节点内部，不依赖 `stage.el()` 的空值语义。

`【源码确证】`**舞台节点本身带 `z-index`**：`content` 模式 `2000`、`full` 模式 `3000`。作者自己的浮层要压过舞台就得 > 3000，见 §6.3 的层级表。

### 4.7 `sdk.role.get()` / `sdk.user.get()`

**返回字段是封闭的**：`role.get()` 只有 `name` / `avatarUrl`，`user.get()` 只有 `nickname` / `avatarUrl`，读别的字段官方校验判 **ERROR**。

**读不到 `personality`、世界设定、开场白或正则** —— 不要编造 `role.personality` / `role.worldbook` / `role.beginning` / `role.statusbar` 这类运行时字段。

`user.get()` **游客也有值（占位值），不能拿它判断登没登录**。官方推荐的安全取值：`var role = sdk.role.get(); var roleName = role && role.name ? role.name : '角色';`

### 4.8 `sdk.debug.log` 与 `sdk.version`

`sdk.debug.log(...)` 往页内调试面板写一行（`?sdkDebug=1` 可见）。`sdk.version` **是值不是函数**，恒为 `'1'` —— **别拿它做能力探测**，平台只维护一份 SDK。

### 4.9 `sdk.on` 与 12 个合法事件名

```
ready  message:new  message:done  message:stream  message:mount  message:unmount
input:change  conversation:switch  theme:change  back  stage:close  dispose
```

🚨 **本表的「载荷」列已按 `【实机实测 2026-08-26】` 重写。** 官方手册对多个事件写「无载荷」，实测三个 message 事件都带**恰好 4 键**的同形载荷 `{content, id, role, serverId}`（§2.6.3）；而 `ready` 官方说「会补发」，实测**不补发且最后到**（§2.6.2）。

| 你想做的事 | 用这个 | 载荷 |
|---|---|---|
| ~~页面刚开好：第一次画界面~~ → **只当时序信号** | `ready` | `undefined`。🚨 **实测最后到（在首条 mount+done 之后）且不补发** → **不能用它做首屏**，见 §2.6.2 |
| **首屏渲染** + 给这条气泡里的按钮绑点击 | `message:mount` | **`{content, id, role, serverId}`**（滚回来会再发、**会补发**；`content` 可能是空串或占位，别当正文用） |
| AI 说完了，读完整回复、按结局切剧情 | `message:done` | **`{content, id, role, serverId}`**（**会补发**） |
| 跟着一个字一个字往外蹦做动画 | `message:stream` | `msg.content`（**已攒原文，累积量**；触发极密，**回调里别查 DOM、别算布局**） |
| 气泡滚走了，停掉定时器 / observer | `message:unmount` | 无 |
| 用户换了一个会话，清掉上一场的计数 | `conversation:switch` | 无 |
| 用户切了深浅色 | `theme:change` | 无 |
| 输入框里的字变了，更新预览 | `input:change` | 无（自己 `sdk.input.get()`；**别在这里再 `input.set`**，会和拼音输入打架、绕成死循环） |
| 用户按了返回 | `back` | 无（舞台开着时平台先关舞台，**不一定轮到你**） |
| 平台把舞台关了 | `stage:close` | 无（作者调 `stage.close()` 不发） |
| 聊天页要关掉了，最后收尾 | `dispose` | 无 |
| 新消息刚出现，正文还是空的 | `message:new`（**几乎用不到**） | **`{content, id, role, serverId}`**（与 mount/done 同形状） |

**日常做卡，`message:mount` + `message:done` 两个就够** —— 原文这里写的是「`ready` + `message:mount` + `message:done`」，已按实测修正：`ready` 既不补发也最后到，**首屏不要依赖它**（§2.6.2）。需要「只跑一次」的初始化，就在 `message:mount` 回调里用幂等哨兵自己拦（因为没有 `once`）。

### 4.10 错误码（官方记 6 个，源码实为 7 个）与限额限频

| code | 常见原因 |
|---|---|
| `UNAUTHORIZED` | 非手势路径发消息，用户没同意 |
| `RATE_LIMITED` | 写太勤或发太勤 |
| `INVALID_ARGS` | 空消息、存档名违规、正在拼音输入时改草稿、编辑一条不存在的消息 |
| `HOST_DENIED` | 存档还没准备好、发送通道没接上、切会话把这次作废了 |
| `NETWORK` | 请求发出去了但没成 |
| `NOT_SUPPORTED` | 当前环境没有这个能力，**多半是创卡页瘦预览** |
| `BUSY` | `【源码确证】`**官方 6 码清单漏记这一个**：同类操作还在进行中。同样要在 `.catch` 里认得它 |

⚠️ `【实机实测】`瘦预览下 `save.get` / `save.keys` 是**抛 `SdkError`**，不是「返回 `NOT_SUPPORTED`」——所以别只写 `.catch`，同步调用要 `try/catch`（§2.5.1）。

**限额**：`CACHE_QUOTA_BYTES` = 1048576（超限行为 `【待验证】`）。`SAVE_MAX_KEYS` = 10 是官方口径，`【源码确证】`该常量**不存在于沙盒**、沙盒零条数校验（§4.5）→ 不写死，但仍按「打成一包」的纪律做。

**限频**（窗口一律 60 秒，**超限拿到 `RATE_LIMITED`，不是静默失败**）：`save.set` 20 次 · `message.send.gesture`（用户点出来的）3 次 · `message.send.auto.minute`（定时器等自动发的）3 次 · `message.edit` 10 次。

把 `err.code` 打进 `sdk.debug.log`。未处理的失败也会进调试面板。

---

## 5. DOM 结构与钩子

> **平台自己的 class 名会变，不要抄页面上看到的 `.xxx` 当选择器。** 承诺不偷偷改名的只有下面这些 `data-chat` / `data-slot`。自己画的 HTML 用自己起的 class（建议加前缀，免得撞上平台内部名字）。

```
[data-chat="root"]                    整页。上面还有 data-theme（light/dark）、data-composer
  ├─ [data-chat="header"]             顶栏
  │    ├─ [data-chat="header-back"]   返回
  │    ├─ [data-chat="header-title"]  头像 + 角色名
  │    ├─ [data-chat="header-actions"] 评论 / 分享 / 收藏 / 同步
  │    └─ [data-slot="header-extra"]  给你留的空位
  ├─ [data-slot="statusbar"]          功能栏。statusbar 为空则整块不存在
  ├─ [data-chat="messages"]           可滚动的消息区
  │    └─ [data-chat="list"]
  │         └─ [data-chat="message-frame"]  一条的外框
  │              └─ [data-chat="message"]   一条消息（data-from / data-state / data-msg-id）
  │                   ├─ [data-chat="message-body"]   你的消息 HTML 在这里
  │                   ├─ [data-slot="message-extra"]
  │                   └─ [data-chat="message-actions"]  重新生成 / 编辑
  ├─ [data-slot="left"] / [data-slot="right"]
  ├─ [data-chat="author-stage"]        舞台：长期面板挂这里
  └─ [data-chat="composer"]            底部输入区。卡片关掉输入时整块不存在
       ├─ [data-slot="toolbar"]
       ├─ [data-chat="input"]
       └─ [data-chat="send"]
```

`[data-slot]` 六个槽位：`header-extra`、`statusbar`、`left`、`right`、`toolbar`、`message-extra`。其中 **`left` / `right` 窄屏上可能不在**，只作可选增强，不当前提。

**实测宿主链** `【实机实测 2026-08-26】`：

```
div  <  [data-slot="statusbar"]  <  [data-chat="root"]  <  div  <  body  <  html
```

→ 两条可用信息：① **功能栏是 `[data-chat="root"]` 的直接子节点**；② **`root` 不是 `body` 的直接子节点**（中间还有一层 `div`）→ 写 `body > [data-chat="root"]` 这类子选择器会失配，用后代选择器或直接从 `[data-chat="root"]` 起手。预览环境实测 `[data-chat]` 节点数 26。

`【源码确证】`可安全挂浮层的槽位是 **`[data-slot="left"]` / `[data-slot="right"]`** —— 它们是 root 的直接子节点，祖先链上没有 `opacity` / `transform` / `overflow` 陷阱。挂在 `[data-chat="message-body"]` 里的浮层会被它的 `opacity:.9` 囚禁在层叠上下文内（§6.3）。

### 5.0 真实聊天页外壳测量（`【实机只读 2026-08-27】`）

对 `https://h5.aitchat.org/#/pages/chat/host?roleId=64304` 内可见 `iframe.chat-iframe` 作只读 DOM、几何与计算样式采集；未保存、未提交、未修改卡片数据。

- 当前观测主题为 dark：root `display:flex; flex-direction:column; position:relative`，背景 `#17181a`；内联 style 同时写 `--chat-viewport-height` 与 `background-image/position/size/repeat`。
- 1232×1248 下 header **45px**、`flex-shrink:0`；messages 吃剩余空间并独立滚动；composer 是静态 flex item、约 **95px**、`flex-shrink:0`，由快捷工具条和输入行构成。
- message 全宽，桌面 padding **11.5px 15px**；message-body `max-width:90%`、正文 **15px**、`white-space:pre-line`、`opacity:.9`，AI 气泡左下角为 0。
- `statusbar/left/right` 是 root 直接槽位；每条 message 含 `message-body/message-extra/message-actions`。外壳尺寸用 `--rpx=100vw/750` 缩放，正文仍保持约 15px。
- light 外壳本次未量化；不能把 dark 几何外推成 light exact。

本地 `build-preview.py --platform mmdsandbox` 以共享契约 v1.1.0 复刻以上外壳，并让内联 `--chat-viewport-height` 随 iframe resize/键盘 inset 更新。仿真器是回归工具，不反向定义平台事实。

### 5.1 可读属性

`[data-chat="message"]` 上：`data-from`（`user` 或 `ai`）、`data-state`（如 `done`、`streaming`）、`data-msg-id`（**服务端认得这条时才有**，刚插入未落库的没有 → `message.edit` 前必须判空）。

`[data-chat="root"]` 上：`data-theme`（`light` / `dark`）、`data-composer`（底部输入区开着还是关着）。

### 5.2 标签白名单 / 黑名单

消息和功能栏里的 HTML 会过净化，白名单之外的标签被丢掉（**里面的文字保留**）。

🚨 **实际是两道闸，取交集才是真相** `【源码确证】`：① **worker 侧的标签白名单**（正则剥壳），② DOMPurify。手册只描述了一个粗略清单，漏记 20 个标签。

**worker 侧白名单逐字 62 项**（`render.worker-*.js`）：

```
p b a div span h1 h2 h3 h4 h5 h6 ul li ol strong em br img pre font i button
table th tr td input textarea label select option video script user summary
details code blockquote hr del thead tbody s
svg g path circle ellipse rect line polyline polygon text tspan defs use
linearGradient radialGradient stop clipPath title
+ style
```

手册漏记的包括 **`a`、`font`、`thead`、`tbody`、`del`、`s`、`g`、`ellipse`、`polyline`、`polygon`、`tspan`、`defs`、`use`、`linearGradient`、`radialGradient`、`stop`、`clipPath`、`title`、`user`** —— 其中 `defs` / `use` / `clipPath` / `linearGradient` 的存在意味着**SVG 渐变与裁剪可用**，做血条、环形进度不必退回纯 CSS。

- **会被删**：`iframe` `link` `meta` `form` `object` `embed`（且 CSP 另有一层封锁，见 §13）
- `<style>` 和 `<script>` **不算被删**，它们被抽出来单独生效（见 §2.1）
- **非白名单标签是被「正则剥壳」**，逐字 `/<\/?([\u4e00-\u9fa5a-zA-Z0-9_]+)(\s+[^>]*)?>/g` —— 只删标签、**文字保留**

> 🚨 **真红线：中文尖括号标签会被整个剥掉。** `【源码确证】`
>
> 上面那条剥壳正则的字符类含 `\u4e00-\u9fa5`，所以 `<状态>`、`<面板>`、`</状态>` 这类**中文尖括号标记会被当标签删掉**（里面文字保留）。
>
> → **模型侧的协议标记一律用方括号 `[状态]…[/状态]`**，不要用尖括号。做状态栏必踩这一条：人设里让模型吐 `<状态>…</状态>`，规则却永远匹配不到（因为标记在进正则之前就没了）。注意这与人设本身的 `<角色设定>` 成对标签不冲突 —— 人设不过渲染管线，只有**模型输出的正文**才过。

#### `on*` 事件属性：范围比手册宽

- 🚨 **HTML 元素上任意 `on*` 都保留** `【源码确证】`+`【实机实测 2026-08-26】`：源码 `Mh=/^on[a-z]+$/i` 配 `forceKeepAttr`（跳过属性白名单与 URI 校验）；实测 `<b onclick>` 与 `<b onmouseenter>` **均 KEPT**。→ 手册只说 `onclick` 能用，实际 **hover / input / change / focus 全都能用**。
- 🚨 **SVG 内 `on*` 被删** `【实机实测】`：`<circle onclick>` 实测 **STRIPPED**。→ **交互必须挂 HTML 壳**（外面套 `div` / `button` 绑事件，里面的 svg 只负责画）。

#### 🚨 `SAFE_FOR_XML` 默认开：属性值里的 `]>` 会让整条属性消失

`【源码确证】`属性值命中这个正则 → **整条属性被删**，且判定发生在 `forceKeepAttr` **之前**（所以 `on*` 的强留特权救不了它）：

```
/((--!?|])>)|<\/(style|script|title|xmp|textarea|noscript|iframe|noembed|noframes)/i
```

→ **`onclick="if(a[0]>1)"` 会整条失效**（含 `]>`）。规避：

- **比较运算符两侧留空格**：写 `if (a[0] > 1)`，不写 `a[0]>1`。
- 属性值里**禁出现** `]>`、`-->`、`--!>`，以及 `</style` `</script` `</title` `</textarea` 等闭合串。
- 更稳的做法：**别把逻辑写进属性**，`on*` 里只调一个顶层函数（`onclick="tap(this)"`），逻辑全放 `<script>` 里 —— 这样天然绕过。

`【实机实测】`已正面验证规避手法有效：`title="a[0] > 1"`（有空格）**完整保留**。⚠️ **无空格的危险形态 `]>` 未实机测试**，「整条属性被删」属**源码推断** `【待验证】` —— 但规避成本为零，照做即可。

#### 其它净化事实

- **作者自写 `data-*` 全删** `【实机实测】`：`data-mine` → `null`。平台自己的 `data-chat` / `data-slot` 由 Vue 创建，从未进净化器，所以只有作者的会被删。
- 🚨 **`aria-*` 与 `role` 属性被删** `【源码确证】`：`ALLOW_ARIA_ATTR:!1`。→ **无障碍在此平台受限，这是平台限制，不是作者疏忽**。做卡时能做的补偿：靠可见文字、足够的对比度与点击区尺寸，而不是 `aria-label`。
- **`id` 撞 document 属性名即删** `【源码确证】`（比如 `id="forms"`、`id="images"` 这类会和 `document.xxx` 撞的名字）→ id 加前缀。
- 🚨 **反引号里的 HTML 会原样成文本** `【源码确证】`：worker 先把 ``` ```…``` ``` 与 `` `…` `` 抽成占位符保护、剥壳后再还原。→ 想在页面上**展示** HTML 源码就用反引号包；反过来，**要真渲染的 HTML 千万别被反引号包住**（症状：「我的标签变成一串文字印在页面上」）。

> 🚨 **真红线：作者自己写的 `data-*` 会被净化删掉**（`【实机实测 2026-08-26】` 确认：`data-mine` → `null`）。自己的按钮/容器用 `class` 或 `id`。`[data-chat="…"]` / `[data-slot="…"]` 是平台的，只能读、可以当选择器。症状是「我写的 `data-xxx` 不见了」，随后所有依赖它的 `querySelector` 全查不到。官方校验对可见 HTML 上自写 `data-*` 有 WARN。

### 5.3 只改某一块

只改 AI 气泡：`[data-chat="message"][data-from="ai"] [data-chat="message-body"] { … }`。同理 `[data-from="user"]` 改用户气泡、`[data-chat="input"]` 改输入框、`[data-chat="header"]` 改顶栏背景。

---

## 6. CSS

所有规则里的 `<style>` **合成一张全页样式表，后写的盖住先写的**。样式是全页作用域、**无隔离** —— 多条规则的 `<style>` 互相覆盖是**预期行为，不是 bug**（症状：「样式在预览里对，上线不对」）。

### 6.1 `--chat-*` 变量：实为 14 个（手册只记 10 个）

🚨 `【源码确证】`+`【实机实测 2026-08-26】`：**每套 14 个**，定义在 **`[data-theme=dark]` 与 `[data-theme=light]`** 两个选择器上。**没有 `:root` 定义、没有 `prefers-color-scheme`** —— 主题完全由 root 上的 `data-theme` 属性驱动。

| 变量 | 说明 | 深色实测值 |
|---|---|---|
| `--chat-bg` | 整页背景 | `#17181a` |
| `--chat-surface` | 卡片、面板这类块的底色 | `#1e1f24` |
| `--chat-text` | 正文颜色 | `#fff` |
| `--chat-text-muted` | 次要文字，比正文淡 | `#c5c5c5` |
| `--chat-border` | 边框颜色 | `#333` |
| `--chat-accent` | 强调色，按钮高亮、血条可以用 | `#ff6d97` |
| `--chat-bubble-user-bg` | 用户气泡背景 | `#17181a` |
| `--chat-bubble-ai-bg` | AI 气泡背景 | `#17181a` |
| `--chat-bubble-text` | 气泡里的字 | `#fff` |
| **`--chat-input-bg`**（手册漏记） | 输入框底色 | `#1e1f24` |
| **`--chat-input-text`**（手册漏记） | 输入框文字 | `#fff` |
| **`--chat-shortcut-text`**（手册漏记） | 快捷条文字 | `#fff` |
| **`--chat-more-item-bg`**（手册漏记） | 「更多」面板条目底色 | `#2c2e32` |
| **`--chat-share-pick-bg`**（手册漏记） | 分享选择态底色 | `#2c2e32` |

**另有一个尺寸基准**：**`--rpx`** = `calc(100vw / 750)` `【实机实测】` —— 平台全部尺寸都以它为单位（750 设计稿宽）。作者想跟平台的视觉节奏，用 `calc(24 * var(--rpx))` 比写死 `px` 更贴。

🚨 **`--chat-viewport-height` 不是样式表变量** `【源码确证】`+`【实机实测】`：它是 **JS 写在 root 上的内联 style**（值为 `clientHeight - 键盘 inset`，随 `visualViewport` 实时更新，实测 `1205px`）。→ **不要试图用 CSS 覆盖它**（内联优先级压过样式表规则），也不要假设它是静态值；要读就 `getComputedStyle` 或直接用 `var(--chat-viewport-height)`。

**两个气泡背景与页面背景同色** `【实机实测】`（都是 `#17181a`）→ 印证手册「气泡三色默认等于页面背景」。这也意味着**默认状态下气泡与背景没有视觉分界**，想要卡片感必须自己给 `--chat-surface` 或自定义底色。

换肤在 `[data-chat="root"]` 上改变量，**不要写死 `#fff`** —— 用变量深浅色切换时才跟得上。自己用 JS 涂的颜色要跟主题，就订 `theme:change`。算出来的值（进度条宽度、血条颜色）写在标签的内联 `style=""` 上；内联会压过 `<style>` 里的规则，颜色仍尽量用 `var(--chat-accent)`。

**换肤的正确选择器** `【源码确证】`：写 `[data-chat="root"][data-theme="dark"]` / `[data-theme="light"]`，特异度 (0,2,0) 高于平台自己的 `[data-theme=dark]`(0,1,0)，**不会被平台切回，且不需要 `!important`**。

🚨 **唯一需要 `!important` 的地方：换页面背景。** `【实机实测】`root 上带 **内联 `background-image`**（实测 `background-image: url("https://r2.aitchat.org/…jpg")`，来自卡片配置的聊天背景图）→ 想换掉整页背景**必须** `background-image: none !important` 或用 `!important` 覆盖，否则那张图一直在。

### 6.2 全局 CSS：是文档约定，运行时不拦

> 🚨 **`*{}` / `html{}` / `body{}` / `:root{}` 应改写成 `[data-chat="root"]`。** 官方校验检测式 `/(^|[\s,};])(\*|html|body|:root)\s*\{/` → WARN（`:root{}` 也在名单里，脚本比官方文案更全）。

**实况修正** `【源码确证】`：**CSS 选择器零过滤** —— `:root{` / `html{` / `body{` 在主包与 worker 中**均 0 命中**，运行时**没有任何拦截逻辑**。所以：

- 这条是**文档约定 + 官方校验 WARN**，**不是运行时硬限制**。写了不会被删，会照常生效。
- **但仍然建议作用域化**，理由变了：不是「会被拦」，而是**沙盒 iframe 里除了你的内容还有平台自己的 chrome**（顶栏、输入框、长按菜单、alert）。写 `*{box-sizing:border-box}` 或 `body{font-size:18px}` 会连平台组件一起改，症状是「顶栏字变大了」「输入框内边距怪了」。
- 跨源 iframe 意味着**污染不出沙盒**（宿主 `h5.aitchat.org` 绝对安全，见 §2.3），所以这条的风险等级比当前 MMD 低得多 —— **是礼貌与自保，不是硬红线**。
- 官方校验仍会报 WARN → 交付前照样改掉，免得用户看见告警。

### 6.3 z-index：手册的分段表不成立，作者安全带是 3500–7999

🚨 **官方手册的「1000–1999 作者内容 / 8000–8999 平台 chrome / 9000–9999 平台模态」是错的，按下面这版写。**

**为什么错** `【实机实测 2026-08-26】`：header / statusbar / messages / composer / stage 五个平台节点实测**全部 `z-index:auto`、`position:static`**（探针 `E.*` 行逐字）。它们只是 root 这个 flex 容器的普通 flex item，**根本没进 8000–8999 段**。→ 作者按手册用 1000–1999，**会盖住顶栏和输入框**。

**样式表穷举的真实占用** `【源码确证】`（`sandbox-app.pretty.css` 全表 `z-index` 声明）：

| z-index | 是什么 | position |
|---|---|---|
| `10090` | snackbar（屏幕正中黑底提示） | `fixed` |
| `9000` | 平台 alert / toast 遮罩 | `absolute` |
| `8200` | 长按消息的全屏菜单（带 `backdrop-filter`） | `fixed` |
| `8100` | 输入区 snack 提示 | `fixed` |
| `8000` | 分享截图 loading | `fixed` |
| `3000` | **舞台 `full`** | — |
| `2000` | **舞台 `content`** | — |
| `40` | SDK 调试面板（`?sdkDebug=1`） | — |
| `10` / `2` / `1` | assistant-tip / history-loading / rate-tip | 多为静态 |

> 🚨 **作者安全带 = `3500`–`7999`。**
>
> 下界 3500：压过舞台 `full` 的 3000（也就压过了 content 2000）。上界 7999：不越过 8000 起的那五个平台临时浮层（分享 loading、输入区提示、长按菜单、alert、snackbar）—— **模态就该在最上，被它们盖住是设计意图，可接受**。
>
> 常驻装饰 / 背景层用 `1`–`999`：在 header/composer（`z-index:auto`）之下或同层，不抢 chrome。

**两个容易踩空的层叠上下文陷阱** `【源码确证】`：

- `[data-chat="message-body"]` 有 **`opacity:.9`** → 它创建层叠上下文，**挂在气泡里的浮层 z-index 写 999999 也翻不出气泡**，而且颜色永远透 10%。→ **浮层不要挂气泡内**，挂 `[data-slot="left"]` / `[data-slot="right"]`（root 直接子节点，祖先链干净）。
- `[data-chat="root"]` 自己是 `position:relative` 但**无 `z-index`** → 它**不创建层叠上下文**。所以挂在 root 下的作者浮层，z-index 与平台浮层**在同一个根层叠上下文里直接比大小** —— 这既是自由（能精确控层级）也是风险（数字写大了真会盖住 alert）。
- 长按菜单（8200）带 `backdrop-filter`，会成为 fixed 后代的包含块 → **它打开时作者浮层一定在下面**，做「常驻不可遮挡」的倒计时之类要接受这一点。

越界不会被拦，**只会盖错东西**。

### 6.4 功能栏：零样式、会被压扁、而且是静态的

`[data-slot="statusbar"]` **平台没给它任何样式** `【源码确证】`，背景、高度全要作者自己写。角色卡 `statusbar` 留空则这个节点**整块不存在**。

**三条实测修正**：

- 🚨 **必须自己补 `flex-shrink:0`** `【实机实测 2026-08-26】`：实测 `[data-slot="statusbar"]` 是 **`flex-shrink:1`**，而 header 与 composer 都显式写了 `flex-shrink:0`（探针 `E.statusbar shrink=1` vs `E.header shrink=0`）。→ **内容一多，功能栏会被 messages 抢走高度压扁**，症状是「状态栏内容多了就挤成一条/文字被切」。作者样式里第一句就该写 `[data-slot="statusbar"]{flex-shrink:0;}`。
- **不用写粘顶** `【源码确证】`：statusbar 是 root 的 flex item，**天然不随消息列表滚动** → 手册说「粘顶 `position:sticky` 要自己写」是多余的，写了反而可能出问题。
- **它是 root 的直接子节点**（`【实机实测】` 宿主链见 §5），祖先链上没有 `opacity` / `transform` 陷阱 → 是**最适合放常驻状态栏的槽位**。

> 🚨 **真红线：功能栏是静态的，只在装载时渲染一次，不存在「重新跑正则刷新」这条路。** `【源码确证】`
>
> 源码里渲染功能栏的 `h_()` **只在装载时调一次，没有任何重渲染路径**；而且它的正则输入是 **`statusbar` 字段自身**，不是消息内容 —— 所以哪怕 AI 每条消息都吐新状态，功能栏也不会跟着变。
>
> → **动态状态栏只能靠作者 JS 改 DOM**（在 `message:done` 回调里改功能栏里已有节点的文字 / class / 内联 style），**不能靠功能栏正则刷新**。
>
> 另：`【源码确证】`主包 grep `降低` / `层级` / `lowerLayer` **零命中** → 创卡页那个「降低层级」复选框是**宿主 uni-app 侧的功能，沙盒不实现**，别指望它改变沙盒内的层级行为。

> ✅ **JS 插入的功能栏节点可以保留。** “功能栏静态”只表示 `statusbar` 字段与其正则在装载时跑一次，不会随消息内容重跑；它不表示平台持续覆盖作者 DOM。实机确认 JS 插入的宿主节点在整页重载后的新装载周期仍可按同一 id 建立并正常渲染，SBK 也用全文档归一解决 statusbar 迟到造成的重复宿主。
>
> → 标准做法是：`statusbar`/规则提供最小静态触发与可选骨架，JS 在 `message:mount`/`message:done` 回调同步期按固定 id 幂等挂载或复用宿主，并更新文字、class、内联 style。长期大面板仍放舞台。

### 6.5 Markdown 陷阱（缩进那条已被推翻，反引号那条才是真的）

替换内容会过一遍 Markdown。

- ⚠️ **「HTML 缩进 4 个空格会被当代码块」在沙盒不成立** `【源码确证】`：平台在跑 markdown **之前就删掉了行首 4+ 空格**，所以 4 空格缩进**不会**变代码块 —— 与手册相反。官方校验 `/^ {4,}</m` → WARN 仍会报，交付前照样顶格写（免得用户看见告警），但**这不是真实故障源**。
- 🚨 **真实故障源是反引号** `【源码确证】`：worker 先把 ``` ```…``` ``` 与 `` `…` `` 抽成占位符保护、剥壳后再还原 → **反引号里的 HTML 会原样成为页面上的文字**。症状正是手册描述的「把源码印在页面上」，只是**病因是反引号，不是缩进**。→ 要真渲染的 HTML **绝不能被反引号包住**；反过来想展示源码就用反引号（这是唯一可靠的展示手段）。
- **注入 HTML 尽量单行无换行**：标签之间的换行会被 markdown 补成空 `<p>` 撑出空白条（这条与当前 MMD 一致，见 `../beautify/style-db/decoration.md`）。

### 6.6 🚨 平台默认样式必须显式重置的三项（新增）

作者内容默认落在 `[data-chat="message-body"]` 里，而它带两个会静默毁掉排版的属性 `【实机实测 2026-08-26】`（探针 `E.msgbody op=0.9 ws=pre-line`）：

| 属性 | 平台默认值 | 不重置的后果 |
|---|---|---|
| `opacity` | **`.9`** | 作者所有颜色都透 10%（对不上设计稿的色值）；并且**创建层叠上下文**，把作者的 z-index 囚禁在气泡内（§6.3） |
| `white-space` | **`pre-line`** | 作者 HTML 里的换行与缩进**全部显形**，表格/flex 布局里冒出意外空行 |
| `flex-shrink`（功能栏侧） | statusbar 为 **`1`** | 内容多时功能栏被压扁（§6.4） |

```css
/* 作者容器上一次性重置，写在自己的根 class 上 */
.mycard-root {
  opacity: 1;                 /* 压掉 message-body 的 .9 */
  white-space: normal;        /* 压掉 pre-line */
}
[data-slot="statusbar"] { flex-shrink: 0; }
```

⚠️ `opacity` 的重置只能救**颜色**，救不了**层叠上下文** —— 父节点 `message-body` 的 `.9` 已经创建了上下文，子节点写 `opacity:1` 也翻不出去。**要精确控层级只能换挂载点**（`[data-slot="left"]` / `"right"`，见 §6.3）。

顺带记住 root 上还有一个**内联 `background-image`**（卡片聊天背景图），换整页背景**必须 `!important`**（§6.1）。

---

## 7. 正则 / 替换机制

一条规则三样东西：**名称**（给自己看）、**匹配式**（要被换掉的那段字）、**替换内容**（换上去的东西）。JSON 字段**恰好这四个**：

| JSON 字段 | 创卡页叫法 | 约束 |
|---|---|---|
| `id` | —— | **必须是负数**（`-1`、`-2`…），导入时会重编号。`typeof !== 'number'` 或 `>= 0` → ERROR |
| `scriptName` | 名称 | 非空。UI 显示 **20**，源码归一常量 `name=200`；双路径与超限语义待验证，实践按 20 写，见 §8 |
| `findRegex` | 匹配式 | 非空。UI 显示 **1000**，源码归一常量 `regex=4096`；双路径与超限语义待验证，实践按 1000，见 §8 |
| `replaceString` | 替换内容 | 编辑器 **20000**／导入 **100000** 的双路径与编辑器拒存语义已确证，见 §8 |

多余字段 → WARN；缺任一字段 → ERROR。

### 7.1 匹配式形态：源码说两种都行，实机上只有 `/…/` 生效

```js
function classifyPattern(raw) {
  const trimmed = String(raw ?? '').trim().replace(/^`|`$/g, '');
  if (!trimmed) return { kind: 'empty' };
  const m = /^\/([\s\S]+)\/([gimsuy]*)$/.exec(trimmed);
  if (!m) return { kind: 'literal', literal: trimmed };
  let flags = m[2] ?? '';
  if (!flags.includes('g')) flags += 'g';
  try { new RegExp(m[1], flags); return { kind: 'regex' }; }
  catch (e) { return { kind: 'bad-regex', message: e.message }; }
}
```

`【源码确证】`**worker 侧的真实实现与上面这段官方脚本逐字一致**（`render.worker-*.js` 的 `p()` / `m()`）：

```js
function p(e){let t=(e??``).trim().replace(/^`|`$/g,``);if(!t)return`empty`;
let n=/^\/([\s\S]+)\/([gimsuy]*)$/.exec(t);if(!n)return new RegExp(m(t),`g`);
let r=n[1];if(r===void 0)return`bad-regex`;let i=n[2]??``;
i.includes(`g`)||(i+=`g`);try{return new RegExp(r,i)}catch{return`bad-regex`}}
function m(e){return e.replace(/[.*+?^${}()|[\]\\]/g,`\\$&`)}
```

由此确证：**前置处理**先 `.trim()` 再剥掉首尾反引号；**`/pattern/flags`** → 正则，合法 flags **仅 `gimsuy`**（无 `d`、无 `v`），**缺 `g` 平台自动补** → 总是全文替换；**其余任何非空串** → **字面量**，元字符被转义（`a.b` 不匹配 `axb`），全文每处都换。

> 🚨 **真红线：源码允许字面量，但实机上裸字面量不生效 —— 一律写 `/…/`。**
>
> `【实机实测 2026-08-26】`探针最初用裸字面量 `{{probe}}` 作匹配式，**规则完全不生效**；改成 `/{{probe}}/` 后**立即生效**。
>
> 这与上面 worker 源码的字面量分支**矛盾** —— 说明**宿主侧在把规则交给 worker 之前另有一层处理**（那一层没有被逆向到）。既然源码路径与实机行为冲突，**以实机为准**。
>
> → **结论：沙盒模式的 `findRegex` 也应一律写 slash 形态 `/…/`**，与当前 MMD（`mmd.md` §8）的铁律一致。原文档这里写的「不强制 slash literal、纯字面量是官方首选写法」**已推翻**。
>
> 转义提示：正则里 `{}` 在**非量词位置就是字面量**，所以 `/{{hud}}/` 不需要转义成 `/\{\{hud\}\}/`（写了也对，只是没必要）。中文、方括号标记同理：`/【图鉴】/`、`/\[status\]([\s\S]*?)\[\/status\]/`（`[` 要转义，因为它是字符类起始）。

⚠️ **`【待验证】`**：宿主侧那层预处理的具体逻辑未逆向到，所以「字面量在什么条件下会生效」不明。不要花时间试探，直接写 `/…/`。

> 🚨 **写成 `/…/` 但正则语法错 → 整条规则被静默丢弃**，不降级成字面量，**页面上看不出异常**（只有告警）。官方校验对此判 ERROR。

> 🚨 **匹配式不要重复。** 规则按顺序跑（`【源码确证】`按 `regexSort` 升序），前一条把全文换完了，后一条同串的规则**永远匹配不到**。官方校验判 **ERROR**。
>
> `【源码确证】`另有一条：**`__` 前缀的规则整条被丢弃** —— 想临时停用一条规则，给名称加 `__` 前缀即可，不必删掉。

### 7.2 替换内容里能取的值

| 记号 | 意思 |
|---|---|
| `$1`、`$2` | 正则里第 1、2 个括号捕获到的内容 |
| `$名字` | 第一个捕获组形如 `血量::10;;金币::3` 时，`$血量` 取到 `10`（键值分隔 `::`，条目分隔 `;;`） |
| `{{random:甲::乙::丙}}` | 三个里随机一个 |

**源码逐字确证的细节** `【源码确证】`：

- `$名字` 的匹配式是 `/\$([a-zA-Z_\u4e00-\u9fa5][\w\u4e00-\u9fa5]*)/g` → **中文与 ASCII 名字都支持**。但**数据源固定是 `$1`**（只看第一个捕获组），且 **`$1` 必须同时含 `::` 与 `;;` 才会被解析**成键值表。只有一对键值时也要写成 `血量::10;;`（或多给一项），否则 `$血量` 取不到。
- `{{random:…}}` 的匹配式是 `/\{\{random:([^}]*)\}\}/g` → `::` 分隔、每项 trim、丢弃空项、均匀随机（**不支持权重**）。因为字符类是 `[^}]*`，所以**不支持嵌套**（里面再写 `{{…}}` 会截断）。**选项内可以用 `$1`**。

```
findRegex:      /血量[:：]\s*(\d+)/
replaceString:  <div class="my-bar" style="width:$1%;height:8px;border-radius:4px;background:var(--chat-accent)"></div>
```

### 7.3 触发串必须接得上

**可见 HTML 的匹配式，必须能在 `statusbar` / `beginning` / 另一条规则的 `replaceString` 里找到**（链式触发被官方认可），否则页面上永不出现（官方校验 WARN）。人设里的「输出约定」必须和这些匹配式对得上 —— **模型写得出，规则才换得掉**。

反过来，只放 `<style>` / `<script>` 的规则，匹配式**故意谁都不引用**（`/卡名-style/` / `/卡名-kit/`），因为它们装卡时就被抽走，不需要被匹配到（`【源码确证】`抽取与匹配解耦）。**但仍要写成 slash 形态，且绝不能匹配空串**（否则触发 `empty-match`，见 §7.6）。

### 7.4 匹配式的内容禁令与转义

- `findRegex` 别含 HTML 标签（检测 `/<[a-zA-Z/]/` → WARN）。
- `findRegex` 别含**独立保留字** `html` / `head` / `body` / `css`（大小写不敏感，独立单词才命中，`htmlish` 不误报）→ WARN。
- 匹配式写太松（比如只写一个 `：`）会把正常对话切碎 —— 规则对**这张卡的每条 AI 消息**都生效，不是只作用在你测的那一条。
- JSON 字符串里 `</script>` 要写成 `<\/script>`，避免宿主页面提前截断。

### 7.5 官方推荐的拆条形态（三条起手）

名称 `hud` / 匹配式 `/{{hud}}/` 放功能栏可见 UI（1～3 个按钮）· `卡名-style` / `/卡名-style/` 只放 `<style>`，谁都不引用 · `卡名-kit` / `/卡名-kit/` 只放 `<script>`，谁都不引用。

⚠️ **匹配式一律 slash 形态**（§7.1 实机结论）。原文这里的 `{{卡名-style}}` 裸写法已按实测改为 `/卡名-style/`。

每块可见 UI 再各开一条（触发串进 `statusbar` 或 `beginning`）。**单条替换内容超 20000 字才继续拆**；不要一上来就切成 19 段，也不要复刻旧卡的 14 条侧边栏。

### 7.6 🚨 输出预算：超了整条规则静默回滚（新增，官方三份资料都没提）

`【源码确证】`worker 里每条规则跑之前先算一个预算，逐字：

```js
let a = Math.max(262144, e.length * 4);            // e = 本条规则的输入文本
if (e.replacement.length > a) { …`replacement-alone`; continue }
let c = 0;
i = i.replace(s, (...t) => { …c += r.length; if (c > a) throw u; return r });
i.length > a && (i = t, r.push(f(e.name, o ? `empty-match` : `volume`)));
```

| 事实 | 说明 |
|---|---|
| **预算 = `max(262144, 输入长度 × 4)`** | 即至少 256 KB；输入长的消息预算按 4 倍放大 |
| **按条规则累计所有匹配的输出** | 不是单次替换，是这条规则在整段文本里**所有命中位置的产物之和** |
| **超限 → 整条规则回滚**（`i = t`） | 页面上该规则**完全不生效**，只在调试面板留一行告警 |

**三种告警**：

- `replacement-alone` —— **替换文本本身**就超预算（单条 `replaceString` 太大）。
- `volume` —— **匹配次数 × 每次输出**累计超预算。典型场景：匹配式写得太松（比如只写一个 `：`），一条消息里命中几十处，每处都插一大块 HTML。
- `empty-match` —— **匹配式能匹配空串**，于是**每个字符位置都插一次**，瞬间炸预算。

> 🚨 **真红线：匹配式绝不能匹配空串。**
>
> 能匹配空串的是 `/a*/`、`/(\d*)/`、`/[abc]?/`、`/(?:x)?/` 这类**整体可为零长度**的写法。→ 量词一律用 `+` 而不是 `*`，可选组不要放在匹配式最外层。
>
> ⚠️ **注意别搞混**：`/(?!)/` 是**恒失败**（永不匹配任何东西，包括空串），**不会触发 `empty-match`** —— 它反而是「只放 `<style>`/`<script>` 的规则」想要「永不匹配」时的安全写法之一。真正的坑是 `/{{kit}}*/` 这种手滑多打一个 `*`。

**症状识别**：「某条规则在短消息里正常，长消息里莫名不生效」= 撞 `volume`；「整条规则从来没生效过，页面无异常」= `replacement-alone` 或 `empty-match`。三种都**只有调试面板能看见**（`?sdkDebug=1`）。

**实践口径**：单条规则的输出总量控制在**远低于 256 KB**（正常做卡差着两三个数量级，只要匹配式不写松、不匹配空串就碰不到）。真正需要警惕的是「一条规则 + 松匹配式 + 大块 HTML」这个组合。

---

## 8. 平台长度契约与保守门禁

| 项 | 硬上限 | 超出后果 |
|---|---|---|
| `chatVersion` | 必须 `1` | 落到旧聊天页，SDK 与 `data-*` 全失效（官方 ERROR） |
| `pageDepth` | 固定 `2` | 只对旧页有意义，**新页不实现**；非 2 → 官方 WARN |
| `statusbar` | **200 字** | 官方 ERROR（**与源码真值一致**） |
| `beginning` | **4000 字**（源码真值，🚨 官方校验脚本的 10240 是错的） | 超出平台字段上限会被裁；创卡页计数器同为 4000，见 §8.2 |
| `personality` | **10000 字** | 官方 ERROR（公开卡审核文案建议 2000–5000） |
| `scriptName` | UI 显示 **20** / 源码归一常量 `name=200` | 双路径与超限语义待验证；交付按 20 |
| `findRegex` | UI 显示 **1000** / 源码归一常量 `regex=4096` | 双路径与超限语义待验证；交付按 1000 |
| `replaceString` | 导入 **100000** / 编辑器硬上限 **20000** | 双路径已确证；编辑器超限会**静默拒绝保存整条修改**，不是截断；见 §8.2 |
| `imageUrl` | **2048 字**（源码真值，官方未记录） | 静默截断 |
| `regex_scripts` 条数 | **130 条** | 官方 ERROR；导入时会被直接截断（**与源码真值一致**） |
| 世界书条目标题（`comment`） | **20 字** | 本 skill 保留，降级为 WARN（见 §10） |
| 角色卡格式 | **不用 chara_card_v2 / PNG 整卡** | 官方禁 PNG 整卡（见 §9） |

### 8.1 顶层键白名单（恰好 6 键）

```
chatVersion  pageDepth  statusbar  beginning  personality  regex_scripts
```

**出现以下顶层键 → 官方判 ERROR**：`role`、`presentation`、`worldbook`、`world_book`、`lorebook`、`lore_book`、`entries`、`characterBook`、`character_book`。其他未知顶层键 → WARN（导入页不认）。

`regex_scripts` 为空数组**且** `personality` 空白 → ERROR「没有可交付物」。

> 注：官方示例卡 `authoring/example-card/card.json` 用的是 `role` / `presentation.transforms[]` 形状 —— 那是**回归夹具，不是导入格式**，照抄会被判 ERROR。

### 8.2 🚨 源码归一常量、UI 显示值与已确认的 replaceString 双路径

`【源码确证】`沙盒源码里的归一常量与裁切函数，逐字：

```js
var Us = { beginning:4e3, statusbar:200, imageUrl:2048, name:200, regex:4096, content:1e5, regexList:130 };
function Ws(e,t){ return typeof e===`string` ? (e.length>t ? e.slice(0,t) : e) : `` }
```

这段代码证明某条源码归一路径会把 `name` / `regex` / `content` 分别裁到 200 / 4096 / 100000。它本身**不能证明** `scriptName` 与 `findRegex` 已存在 editor/import 双路径，也不能推出创卡页保存按钮的失败语义。只有 `replaceString` 的 20000/100000 双路径已经通过实机事故与平台方口径确认。

| 字段 | 源码归一观察值 | 创卡页 UI / 已确证行为 |
|---|---:|---|
| `beginning` | **4000** | **4000**（计数器实测），按 4000 阻断；官方 skill 的 10240 错 |
| `scriptName` / `name` | **200** | UI 显示 **20**；是否存在双路径、超限如何失败仍 `【待验证】`，交付按 20 |
| `findRegex` / `regex` | **4096** | UI 显示 **1000**；是否存在双路径、超限如何失败仍 `【待验证】`，交付按 1000 |
| `replaceString` / `content` | **100000** | 编辑器 **20000 硬上限**；双路径已确证，超限保存整次失效 |
| `statusbar` | **200** | **200**，一致 |
| `regexList` | **130** | **130**，一致 |
| `imageUrl` | **2048** | UI 未记录；源码归一路径会裁切 |

> 🚨 **编辑器 20000 的真实事故形态必须记准。** 实机粘贴 63317 字符后点击「保存配置」，界面无错误，但重载后规则名、匹配式与内容整体回到上一次版本。若误写成“截断”，排查会去找半条脚本；真实情况是本轮改动**一字未存**。

**本 skill 的取值策略**：

- `beginning` 按 **4000** 卡 ERROR；`statusbar`/`personality`/条数按各自硬上限。
- 默认产物仍按编辑器路径的严值写：`scriptName <= 20`、`findRegex <= 1000`、单条 `replaceString <= 18000`（为 20000 留余量）。生成器按完整文件边界自动拆条，因此导入和手填两条路径都安全。
- 只有 `replaceString` 明确走「导入正则」且不需要在编辑器内打开修改时，才可使用高于 20000、最高 100000 的宽路径；交付说明必须写清维护限制。`scriptName` / `findRegex` 在双路径实测前仍分别按 20 / 1000。
- 修改后不能以“按钮没报错”为证据：重载并回读字段计数器/真值，确认变化到达正式数据层。

⚠️ 长度不是唯一的量级约束 —— 还有**运行时输出预算**（单条规则累计输出超 `max(256KB, 输入×4)` 会整条静默回滚），见 §7.6。两者互相独立，都要过。

---

## 9. 交付形态与人设格式

> 🚨 **沙盒模式不走 chara_card_v2、不走 PNG 整卡。** 官方明令「不写对话示例、**PNG 整卡**」。导入入口是创卡页的「**导入正则**」（也叫「设置正则」），格式是 **JSON 文本**。这与当前 MMD（`mmd.md` §7：仅 chara_card_v2、仅 PNG）完全不同 —— 别把 `card-json.md` 那套 v2 打包流程套过来。

### 9.1 三件交付物

- **导入正则 JSON**（顶层恰好 6 键，见 §8.1）→ 创卡页「导入正则」入口。
- **独立 persona 文本**（未转义正文，纯文本）→ **导入页不会读 `personality` 字段**，必须让用户手工粘贴到人设框。
- **独立世界书 JSON**（可选，根对象**只留 `entries`**）→ 世界书**不能**塞进导入正则 JSON（塞了判 ERROR），有独立导入入口。

导入 JSON 的完整形状：

```json
{
  "chatVersion": 1,
  "pageDepth": 2,
  "statusbar": "{{hud}}",
  "beginning": "雨还在下。禾安把伞往 {{user}} 那边偏了偏。{{intro}}",
  "personality": "<角色设定 名字：禾安>\n<基本信息>\n- 身份：种子铺守护人\n</基本信息>\n</角色设定>",
  "regex_scripts": [
    { "id": -1, "scriptName": "hud", "findRegex": "/{{hud}}/", "replaceString": "<div class=\"my-hud\">…</div>" }
  ]
}
```

`personality` 仍要写进 JSON（供校验与留档），但**同时**必须另出一份纯文本给用户粘贴。落盘命名沿用 `../output/regex-output.md` 的约定；官方侧的命名习惯是 `<短名>-regex.json` / `<短名>-persona.txt` / `<短名>-worldbook.json`。

### 9.2 人设格式要点

**ERROR 级**：角色主标签必须写成 `<角色设定 名字：真实角色名>` 并用 `</角色设定>` 闭合（闭合标签不重复名字属性）；开始与闭合标签**各自独占一行**（冒号全角半角均可，推荐全角）；每个开始标签必须有同名闭合标签，严格按后开先闭嵌套；**禁 `{{char}}` / `$#char#$` / `$#user#$`** —— 角色名在正文里直接写真名。

**WARN 级**：缺 `{{user}}`；含 `<script` / `<style` / `sdk.`（人设里不放 HTML、CSS、脚本或 SDK 调用）；成对章节标签少于 3 组。

**玩家只用 `{{user}}`**，不写死玩家姓名。**禁 `【章节】` 方括号标题**，也不用 Markdown 标题 —— 一律改成成对单行标签。

推荐章节顺序：`<世界观>` / `<历史背景>` / `<地图>` → `<角色设定 名字：X>`（内含 `<基本信息>`、`<与{{user}}的关系>`、`<性格特点>`、`<说话方式>`、`<外貌特征>`、`<背景设定>`、`<道具>`、`<能力与限制>`、`<行为逻辑>`）→ `<养成规则>`。有界面需求时**必写 `<输出格式>`**，把模型该吐的标记（如 `[status]` 块、`〖骰=…〗`）写清楚 —— 否则规则永远匹配不到东西。

`beginning` 是**玩家看见的第一句话，不是人设**，别把整篇人设贴进开场白。可以夹触发串（如 `{{intro}}`）。

### 9.3 界面要两层都在

模型输出标记（人设 `<输出格式>` 写明）+ 规则/脚本渲染，**缺一层就只是「看起来有」**。官方校验有对应交叉检查：规则里含 `[status]` 但 personality 无 `[status]` → WARN；含 `〖骰=` 但 personality 无 `〖骰=` → WARN。

> 🚨 **真红线：模型侧的协议标记必须用方括号 `[状态]…[/状态]`，绝不能用中文尖括号 `<状态>…</状态>`。** `【源码确证】`
>
> 渲染管线的剥壳正则是 `/<\/?([\u4e00-\u9fa5a-zA-Z0-9_]+)(\s+[^>]*)?>/g` —— 字符类含 `\u4e00-\u9fa5`，所以**中文尖括号标签在进入你的正则之前就被整个删掉了**（文字保留，标签消失）。症状是「人设写得好好的，模型也照吐了，规则却永远匹配不到」。做状态栏必踩这一条，细节见 §5.2。
>
> 注意区分两件事：**人设本身**的 `<角色设定>` / `<输出格式>` 成对标签**没问题**（人设不过渲染管线）；只有**模型输出的正文**才过管线。所以人设里描述格式时，要让模型吐的是 `[状态]`，而承载这个描述的章节标签仍写 `<输出格式>`。

---

## 10. 世界书

- 世界书**有独立导入 JSON**，但**不能**放进「导入正则」JSON（顶层出现 `entries` / `worldbook` / `characterBook` 等 → ERROR）。
- 独立文件根对象**只保留 `entries`**（官方校验：顶层键必须恰好一个且为 `entries`）。
- `entries` 是**对象映射**（键建议连续数字字符串），不是数组；空 `entries` → ERROR。
- 每条目 12 个必需字段全给，其中 `probability` 必须是**两位小数字符串**（如 `"100.00"`），`key` / `keysecondary` 必须是**JSON 字符串**（不能直接写数组）。字段细节见 `../output/worldbook-json.md`。
- 条目 `content` 必须**至少包含一组成对章节标签**，且不得含 `$#char#$` / `$#user#$` / `{{char}}`（均 ERROR）。
- 若目标入口不支持世界书、或世界书导入失败，官方的兜底是把内容压进 `personality`（会吃 10000 字额度）。

### 10.1 条目标题 20 字：本 skill 保留，但降级为 WARN

**本 skill 在沙盒模式继续检查条目标题（`comment` 字段）≤ 20 字，级别是 WARN 而非 ERROR。**

理由必须写清楚，免得后来人「顺手修正」：

1. **保留的理由**：沙盒模式是**同一个 MMD 平台的新聊天页，不是新后端**。20 字上限的来源是 MMD **创卡页 UI** 对世界书条目标题的截断，与 `chatVersion` 无关，没有任何证据表明新页改了这个 UI 限制。所以继续提示是对用户负责。
2. **降级的理由**：官方 `validate-worldbook.mjs` 里**没有**这项检查（它只查 `comment` 非空、非字符串等）。本 skill 不能拿一条无官方脚本背书的平台侧 UI 限制去阻断交付。
3. 该限制在沙盒模式下**未复验** `【待验证】` —— 若哪天实机确认新页放开了，直接删掉这条 WARN 即可，不影响其他检查。

计长口径与写标题的纪律沿用 `mmd.md` §7「世界书条目标题（20 字上限）」：按字符数、中文一字算 1，标点空格计入；不加 `【】`、`·`、`—` 等装饰框线。

### 10.2 固定传输字符

当前 MMD 的 15000 字固定传输上限（`mmd.md` §7）在沙盒模式下**仍 `【待验证】`** —— 官方资料未提及，源码逆向也没找到对应常量（沙盒只负责渲染，提示词组装在服务端，不在这个包里）。因此：

- 字段级上限按 §8.2 的**源码真值**硬卡（注意 `beginning` 是 **4000** 不是 10240）。
- 蓝灯世界书条目 + 人设的**合计**是否仍有 15000 常驻预算，未知。稳妥做法是**继续按 15000 预算控制蓝灯总量并留 2000–3000 字缓冲**，直到实机复验。
- 这条与 §7.6 的**输出预算**是两件事：15000 是**给模型的输入**预算（未确证），§7.6 是**渲染时的输出**预算（已源码确证）。

---

## 11. 排查表：出问题先看这里

沙盒模式的故障**不弹窗**，报错进页内调试面板（聊天页 URL 加 `?sdkDebug=1` + `sdk.debug.log`）。手机上没有控制台，这是唯一的观测口。

| 症状 | 根因 | 修法 |
|---|---|---|
| 按钮全不响应、样式对一半、SDK 全不在 | 卡不是新页（`chatVersion` 没生效，或给已存在的卡导入被忽略） | 新建卡 + 创卡页确认新页（§0） |
| 点了发送，画布上出现「消息生成中」，stream 已经在吐字 | 在 `message:mount` 里读 `[data-chat="message-body"]` 当回复 | 跟字用 `message:stream` 的 `msg.content`，收尾用 `message:done`（§3） |
| 按钮点了没反应 | 绑事件写到脚本顶层了；气泡滚出屏幕会被拆掉 | 绑定写进 `sdk.on('message:mount')`（§2.2） |
| **顶层 `getElementById` / `querySelector` 全拿到 `null`，页面上什么都没画出来** | **作者脚本早于 DOM 执行** | **任何 DOM 写入都搬进事件回调（§2.6.1）** |
| **首屏永远不出现，或迟到一整轮** | **首屏挂在 `ready` 上；`ready` 最后到且不补发** | **改挂 `message:mount` / `message:done`（§2.6.2）** |
| **用了外链 `<script src>` 后，`ready` 回调再也不触发** | 外链未被 await + `ready` 不补发 | 关键订阅写在外链之前，或不用外链（§2.4） |
| **创卡页预览里整卡完全不工作，聊天页却正常** | `save.get` / `save.keys` 在瘦预览**同步抛 `SdkError`**，没 catch 就废掉整段脚本 | 包 `try/catch`（§2.5.1、§4.5） |
| **预览里效果叠加了好几份** | 预览会反复重装整卡（「只跑一次」只在聊天页成立） | 加「已初始化」幂等哨兵（§2.1） |
| **`stage.el()` 判空恒真，以为舞台开着** | `stage.el()` 关闭时仍返回 DIV | 判开关只用 `stage.visible()`（§4.6） |
| **模型吐了 `<状态>…</状态>`，规则永远匹配不到** | 中文尖括号标签被剥壳正则整个删掉 | 协议标记改方括号 `[状态]`（§5.2、§9.3） |
| **规则在短消息里正常，长消息里莫名不生效** | 撞输出预算 `volume`，整条规则静默回滚 | 收紧匹配式、减小单次输出（§7.6） |
| **某条规则从来没生效过，调试面板有 `empty-match`** | 匹配式能匹配空串，每个位置都插一次 | 量词用 `+` 不用 `*`（§7.6） |
| **`beginning` 后半段丢了** | 真上限是 **4000**，官方校验脚本的 10240 是错的，超出**静默截断** | 按 4000 卡（§8.2） |
| **我的标签变成一串文字印在页面上** | 被反引号包住了（**不是 4 空格缩进**，那条在沙盒不成立） | 去掉反引号（§6.5） |
| **状态栏内容一多就被压扁 / 文字被切** | `[data-slot="statusbar"]` 是 `flex-shrink:1` | 自己补 `flex-shrink:0`（§6.4、§6.6） |
| **颜色比设计稿淡一档，且浮层翻不出气泡** | `message-body` 带 `opacity:.9`（还创建层叠上下文） | 重置 `opacity`，浮层换挂 `[data-slot="left"]`（§6.6、§6.3） |
| **HTML 里的换行/缩进在页面上全显形** | `message-body` 带 `white-space:pre-line` | 显式 `white-space:normal`（§6.6） |
| **换了页面背景没反应** | root 上有内联 `background-image` | 用 `!important`（§6.1） |
| **`aria-label` / `role` 属性不见了** | `ALLOW_ARIA_ATTR:!1`，平台限制 | 靠可见文字与足够点击区补偿（§5.2） |
| **`onclick` 里带比较运算的逻辑整条失效** | 属性值含 `]>`，`SAFE_FOR_XML` 删掉整条属性 | 运算符两侧留空格，或逻辑挪进 `<script>`（§5.2） |
| **svg 里的 `onclick` 不触发** | SVG 内 `on*` 被删 | 外面套 HTML 壳绑事件（§5.2） |
| **状态栏字段变了但功能栏没刷新** | 功能栏**静态**，只在装载时渲染一次 | 骨架写进规则，值靠 JS 改 DOM（§6.4） |
| **`fetch` 外部接口全失败** | CSP `connect-src 'self'` | 状态只能来自 AI 正文 / `save` / `cache` / `localStorage`（§13） |
| **外部字体、外部 CSS 加载不上** | CSP `style-src` 无 `https:`，`font-src` 仅 `'self'` | 改用系统字体栈 + 内联 `<style>`（§13） |
| 同一件事触发了好几次 | `sdk.on` 写进 `message:mount` 回调里了 | 订阅只写在脚本体，一次就够（§2.2） |
| 我写的 `data-xxx` 不见了 | 净化删掉作者自写 `data-*` | 用 class 或 id（§5.2） |
| 事件一次都不触发 | 事件名写错，**平台不报错** | 照 §4.9 的 12 个名字抄 |
| 能力调用完全没反应 | 能力名写错，**平台不报错** | 照 §4 能力全表抄 |
| 样式在预览里对，上线不对 | 别的规则也带 `<style>`，全页合成、后写盖先写 | 加 class 前缀、排查覆盖顺序（§6） |
| 画的东西滚一会儿就没了 | 长期面板挂在气泡里，气泡销毁即没 | 挂舞台 `sdk.stage`（§4.6） |
| JS 插入的功能栏宿主重复或位置不对 | 作者脚本早于 statusbar DOM；过早走 fallback 后静态宿主又迟到 | mount/done 同步期按固定 id 做全文档归一与内容迁移（§6.4） |
| 预览里调什么都报 `NOT_SUPPORTED` | 创卡页是瘦预览，input / send / save 全不开放 | 回聊天页验（§2.5） |
| 某条规则完全没生效、页面无异常 | 写成 `/…/` 但正则语法错 → **整条静默丢弃** | 校验匹配式（§7.1）。**不要退回字面量** —— 实机上裸字面量本身就不生效 |
| **规则写的是裸字面量 `{{hud}}`，页面上永不替换** | **实机上裸字面量不生效**（官方称字面量是首选，已推翻） | **改写 `/{{hud}}/`（§7.1）** |
| 后面那条同标记的规则永不生效 | 匹配式重复，前一条已换完全文 | 换标记；官方判 ERROR（§7.1） |
| 想临时停用一条规则 | — | 名称加 `__` 前缀，整条被丢弃（§7.1） |
| 界面上那块 UI 永远不出现 | 触发串没接到 `statusbar` / `beginning` / 别的 `replaceString` | 接上触发串（§7.3） |
| ~~源码被原样印在页面上：HTML 缩进 4 空格~~ | **该说法在沙盒不成立**（平台在 markdown 前先删行首 4+ 空格）。真病因是**反引号** | 去掉包住 HTML 的反引号（§6.5） |
| 外链库 `window.XXX` 是 undefined | 用了 `http://`（直接跳过）。**不是域名白名单问题** —— 应用层无白名单，任意 https 都放行 | 换 `https://`；查调试面板（§2.4、§13） |
| `message.edit` 报错 / 拼出 `null` | 刚插入未落库的消息没有 `data-msg-id` | 调用前判空（§4.3） |
| 发消息报 `UNAUTHORIZED` | 不是用户手势当帧（先 `await` 了，或定时器里发） | 点击当帧直接 `send`（§4.3） |
| 存档/发送报 `RATE_LIMITED` | 超限频 | 攒批再写；照 §4.10 的次数控制 |
| 存档在别人手机上全丢 | 游客存档退出即失、登录不迁移，**作者自己测不出** | 别把攒进度做成唯一玩法（§4.5） |
| 面板挡住了平台长按菜单/提示 | z-index ≥ 8000，撞上平台临时浮层段 | 压回 **3500–7999**（**不是手册说的 1000–1999**，那个段位会盖住顶栏和输入框，§6.3） |
| 面板被顶栏/输入框盖住，或反过来盖住了它们 | 照手册用 1000–1999，而 header/composer 实测是 `z-index:auto` | 用 3500–7999；常驻装饰用 1–999（§6.3） |
| 自问自答死循环 | `message:done` 里无条件 `message.send` | 加条件或改用 `input.set`（§4.3） |
| 剧情跳一轮 / 卡在等待态 | `content` 空时退回去读 DOM，读到占位就清了等待态 | 用 `isReplyText` 判别（§3） |

### 11.1 官方「别这么写」清单（逐条对照 §4 已展开）

`input.get` 别轮询 · `input.set` 别在 IME 组合期调 · `input.add` 别逐字追加 · `input.insert` 别假设光标不动 · `input.clear` 发送后不用自己清 · `input.focus` 别在页面刚加载时调 · `input.setCursor` 别拿它模拟选区 · `composer.hide` 藏了要给发送路径 · `message.send` 别在 `message:done` 里无条件调 · `message.edit` 别拿 `null` 当 id · `cache.*` 别存进度 · `save.set` 别每帧写 · `stage.open` 别每次重建内部 DOM · `stage.el` 别当消息容器 · `user.get` 别当登录态判断 · `on` 事件名别打错 · `version` 别做能力探测。

### 11.2 从当前 MMD 迁过来时必须扔掉的东西

- **`img onerror` 点火器 / 雷达法引擎 / teapot 系**（`onerror` 图、`window.teapot*`、CoC 注入）→ 一条只放 `<script>` 的规则 + `sdk.on('message:mount')`。官方明令禁 teapot。
- **`window.__fn` + `onclick="window.__fn&&__fn()"` 那套净化绕行**、**轻主板 + 胖遥控器**（`data-s` + `eval`）→ 都不需要：顶层 `function` 直接挂 `window`，普通标签 `onclick="tap()"` 就能用；且作者自写 `data-*` 会被删。
- **`【侧边栏1】`…`【侧边栏14】` 屏外注入切片** → 功能栏是**可见槽位不是注入口**；`statusbar` 放 `{{hud}}` + 长期面板放舞台。
- **`[sta` + `tus]` 拆词绕检测** → `/\[status\]([\s\S]*?)\[\/status\]/` 一条真正则吃整块。
- 🚨 **Shadow DOM 状态栏（`attachShadow` / 影渲法 / ShadowCast）** → **扔掉，理由已升级为硬理由**：`【实机实测 2026-08-26】`沙盒本身就是**跨源 iframe**（作者节点 `getRootNode() === document`，不是 shadow root）→ **iframe 已经完成了全部隔离，再套一层 Shadow DOM 是纯负债、零收益**：样式要重复注入、和平台的 `querySelector` 收窄机制打架、`--chat-*` 变量继承链变复杂。原文这里写的理由是「沙盒形态未说明所以别移植」，那是证据不足时的保守判断；**现在的理由是「没有任何东西需要再隔离」**（§2.3）。
- **`document.currentScript` 自定位** → 扔掉，**它恒为 `null`**（`【源码确证】`内联脚本走 `(0,eval)`，根本没有 script 节点；`【实机实测】`顶层与回调内均为 `null`）。定位改用固定 id/class 约定 + `message:mount`（§2.3）。
- **chara_card_v2 / PNG 打包** → 正则 JSON + persona 文本（§9）。

对抗检定 `〖⚔=①…〗` 这类，用户没点名就不要做；骰子标记用 ASCII 分隔 `〖骰=检定名|属性|目标|出目|成功或失败〗`。

---

## 12. 写作策略

1. **起手三条规则**：一条 `/卡名-style/` 只放 `<style>`，一条 `/{{hud}}/` 放功能栏可见 UI，一条 `/卡名-kit/` 只放 `<script>`。每块新增可见 UI 再各开一条并接上触发串。**匹配式一律写 slash 形态**（§7.1）。
2. **脚本骨架**：顶层只做「定义函数 + `sdk.on` 订阅 + 挂 `window`」，**一行 DOM 都不碰**；渲染函数挂 `message:mount` 与 `message:done`，函数内自带幂等哨兵（预览会重跑）。**不要用 `ready` 做首屏**（§2.6）。
3. **状态栏 / 面板**：短小可见块走规则替换（`$1` / `$名字` 直出 HTML，零 JS）；要跟剧情变的走 `<script>` + `message:done` 读 `msg.content` 再渲染 —— **骨架写进规则保证节点存在，值靠 JS 改**（功能栏是静态的，不会自己刷新，§6.4）；要一直在的（地图、背包、小游戏）**一律挂舞台**。
4. **状态持久化**：当场状态 `sdk.cache`，单卡本地偏好 `localStorage`，跨设备进度 `sdk.save`（打成一包、攒批写，`save.get` **必须 `try/catch`**）。**游客会丢，别做成唯一玩法。**
5. **配色**：改 `[data-chat="root"][data-theme="dark|light"]` 上的 **14 个** `--chat-*` 变量（§6.1），不写死颜色；尺寸可用 `--rpx` 跟平台节奏；JS 涂色的订 `theme:change`。**换页面背景要 `!important`**。
6. **必做的三项重置**：`opacity:1`、`white-space:normal`（压掉 `message-body` 的默认值）、功能栏 `flex-shrink:0`（§6.6）。浮层 z-index 取 **3500–7999**，挂 `[data-slot="left"]`/`"right"`（§6.3）。
7. **零外部依赖**：CSP 封死 `fetch`、外部字体、外部样式表（§13）→ 用系统字体栈、内联 `<style>`、`data:` 图片；状态只能来自 AI 正文 / `save` / `cache` / `localStorage`。
8. **模型侧协议用方括号** `[状态]…[/状态]`，**绝不用中文尖括号**（会被剥壳删掉，§9.3）；匹配式**不能匹配空串**、别写太松（输出预算，§7.6）。
9. **验证顺序**：`validate.py` → 本地沙盒仿真 `chat` + `thin-preview` → 桌面/窄屏/横屏 GUI 与截图；能力矩阵标为 `probe-needed` 时才回真实站做隔离探针。AI 不默认登录账号、不对正式卡或公开卡执行保存编辑；最终实站验收由用户授权并负责账号侧操作。
10. **交付**：正则 JSON + persona 文本（+ 可选世界书 JSON），并在交付说明里写明「必须新建卡、创卡页确认新页」。`beginning` **按 4000 字卡**（§8.2）。

---

## 13. 🚨 CSP 硬边界（新增，`【源码确证】` 响应头 + meta 取交集）

沙盒 iframe 的实际 CSP（响应头与页内 `<meta>` **取交集后**的有效约束）：

```
default-src 'self';
frame-ancestors https://h5.aitchat.org https://admin.aitchat.org;
script-src 'self' 'unsafe-inline' 'unsafe-eval' https:;
style-src  'self' 'unsafe-inline';
img-src    'self' data: blob: https:;
connect-src 'self';
worker-src 'self';
（meta 侧另加 frame-src / form-action / object-src 'none'）
```

| 作者想做的事 | 判定 |
|---|---|
| 内联 `<script>` / `eval` / `new Function` | ✅ 可用（`'unsafe-inline'` + `'unsafe-eval'`） |
| 外部 `<script src="https://…">` | ✅ **任意 https 都放行**。🚨 **应用层没有域名白名单**，只校验 `^https://` —— 手册「需平台白名单」与实况不符 |
| 内联 `<style>` / 元素 `style=""` | ✅ 可用 |
| 🚨 **外部样式表** `<link rel=stylesheet>` | ❌ **封死**（`style-src` 无 `https:`） |
| 🚨 **外部字体**（Google Fonts、CDN 字体） | ❌ **封死**（`font-src` 交集后仅 `'self'`） |
| 🚨 **`fetch` / `XMLHttpRequest` 打外部 API** | ❌ **封死**（`connect-src 'self'`） |
| 图片 | ✅ 任意 `https:` / `data:` / `blob:` |
| 作者自己开 `<iframe>` / `<form>` / `<object>` | ❌ 封死（meta `frame-src` / `form-action` / `object-src` 均 `'none'`；标签本身也不在白名单，§5.2） |
| Web Worker | 仅 `'self'`（平台自己的渲染 worker），作者无处放脚本文件 → 实际不可用 |

**三条可执行结论**：

1. 🚨 **卡片必须完全自包含**：零 CDN 样式、零外部字体、零外部请求。想要特殊字体只能用**系统字体栈**（`font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`）或把图形做成 SVG（白名单里 SVG 一整套都在，含 `defs`/`use`/`clipPath`/渐变，§5.2）。
2. 🚨 **状态只有四个来源**：AI 正文（经正则/脚本解析）、`sdk.save`（跨设备）、`sdk.cache`（当场）、`localStorage`（单卡本地）。**没有「从服务器拉数据」这条路** —— 想做联网排行榜、在线词典、远程配置一律不可能。
3. **外链 `<script>` 虽然 CSP 放行，但实用价值有限**：它没被 await（§2.4），会让之后注册的 `ready` 回调收不到；而且库拿不到网络（`connect-src 'self'`），大部分 SDK 类库在这里是废的。**能内联就内联。**

`frame-ancestors` 只允许 `h5.aitchat.org` 与 `admin.aitchat.org` —— 这解释了为什么直接打开 `c<卡片ID>.sbx.aitchat.org` 会停在 `waiting for host handshake`（§2.3）：它只能被这两个宿主嵌入，且必须靠宿主 postMessage 投喂卡片配置。

---

## 相关文档

- `mmd.md` —— 当前 MMD（`/mmd`）平台规范，`img onerror` 载体那一套。**两边写法不通用**，注意别串。
- `sillytavern.md` —— 本地酒馆平台规范。
- `../output/regex-output.md` —— 正则 JSON 交付与转义（沙盒模式是 6 字段，注意与当前 MMD 的 4 字段区分）。
- `../output/worldbook-json.md` —— 世界书条目字段与导出。
- `../output/card-json.md` —— chara_card_v2 打包，**沙盒模式不用**，仅当前 MMD / 本地酒馆用。
- `../quality/checklist.md` —— 交付前自检。
- `../beautify/statusbar.md` / `../beautify/statusbar-radar.md` —— 当前 MMD 的状态栏方案，**沙盒模式不可直接移植**（载体是被禁的 `img onerror`），只可参考数据协议与信息架构。
- `../beautify/global-css.md` / `../beautify/style-system.md` —— 视觉设计思路可复用，选择器与变量须换成 `[data-chat]` / `--chat-*`（注意是 **14 个**，见 §6.1）。
- `../beautify/statusbar-shadowcast.md` —— 影渲法（Shadow DOM 隔离）。**沙盒模式一律不用**：沙盒本身是跨源 iframe，隔离已完成，再套 Shadow DOM 是纯负债（§2.3、§11.2）。其数据协议与 schema 设计仍可参考。

> **本文档与 `mmd.md` 的证据等级已不同**：`mmd.md` 是本 skill 的实机实测；本文档是**逆向沙盒源码 + 真机探针**，并已推翻官方手册的多处说法（清单见文首）。两边的结论都不要互相套用。

