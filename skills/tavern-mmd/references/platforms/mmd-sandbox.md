# MMD沙盒模式平台技术规范（`<script>` 一等公民 + 官方 SDK 30 能力 / 12 事件）

> 本文档描述 MMD（魅魔岛/sexyai.top）的**新聊天页**。「沙盒模式」是本 skill 与用户侧的叫法，**官方口径只有「新页 / 新聊天页」**，开关是角色卡的 `chatVersion: 1`。官方全部资料里 grep「沙盒」零命中，所以跟平台客服/官方文档沟通时请说「新页」。
>
> **证据等级**：全文依据两份官方一手资料 —— 官方 PDF《MMD新版对话框角色卡制作手册》34 页全文，与官方 skill `generating-role-card`（含 `contract.json`、`scripts/validate.mjs` 等校验脚本源码）。**本 skill 尚未对沙盒模式做过实机探针**，因此本文没有「实测」级条目；每条结论标注来源（`手册`／`官方skill`／`contract.json`／`validate.mjs`）。与 `mmd.md` 的实测结论不同，这里的「官方明文」级别不等于「已验证边界」。
>
> **来源边界**：官方资料没说的，本文一律标 `【原文未说明】`，不作推断补齐。尤其：沙盒的具体形态（iframe / Shadow DOM / 同文档）与 `document.currentScript` 是否可用，**两者都未说明**，任何依赖这两点的写法都不要采用。
>
> **适用前提**：`chatVersion: 0` 或缺省 = 旧聊天页，**没有 `sdk.*`、没有 `[data-chat]` / `[data-slot]`、没有舞台**。本文所有能力只在新页存在。

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
| `findRegex` 必须 slash literal | ✅ 强制（实测铁律，见 `mmd.md` §8） | ❌ **不强制；纯字面量 `{{hud}}` 是官方首选写法** |
| 导入 JSON 顶层键 | 4 键 `pageDepth` / `statusbar` / `beginning` / `regex_scripts` | **恰好 6 键**（多 `chatVersion` / `personality`） |
| `id` 取值 | 时间戳类 | **必须负数**，导入时重编号 |
| 整卡 PNG / chara_card_v2 | ✅ 仅 v2，PNG 承载 | ❌ **官方禁 PNG 整卡**；交付 = 正则 JSON + persona 文本 |
| `<script>` 地位 | 可执行，但 per-message 自渲染/定位不可用 | **一等公民**：装卡即抽出、整卡跑一次；per-message 由 `message:mount` 事件顶替 |
| 状态栏引擎载体 | `img onerror`（唯一可靠 per-message 载体） | **`<script>` + SDK**；`img onerror` 点火器被官方明令禁止 |
| 官方 SDK | ❌ 无 | ✅ 30 能力 / 12 事件 |
| 稳定选择器 | ❌ 平台 class 名会变 | ✅ `[data-chat]` / `[data-slot]` 承诺不改名 |
| 长期面板 | 无处安放（挂气泡会随气泡销毁） | ✅ 舞台 `sdk.stage` |
| 跨设备存档 | ❌ | ✅ `sdk.save`（落服务端） |
| CSS 变量 | 无平台约定 | ✅ 10 个 `--chat-*` |
| 世界书条目标题 20 字 | ✅ | ✅ 本 skill 保留，但降级为 WARN（见 §10） |

**共通不变**：正则条数 130、`findRegex` 1000 字、`replaceString` 20000 字、替换产物要再过一遍 Markdown、规则按顺序跑且后条会扫到前条产物。

---

## 2. 唯一注入口与执行模型

作者在创卡页跟界面有关的**只有一处**：正则替换规则的「**替换内容**」。HTML、`<style>`、`<script>` 全写在那里（手册开篇）。不写整页 HTML 文件，不上传 JS 文件 —— 所有代码都是某条规则的 `replaceString` 字符串。

功能栏（聊天页顶部下面那一条）来自角色卡 `statusbar` 字段，**同样会过一遍你的规则**。因为 `statusbar` 只有 200 字，标准写法是 `statusbar` 里只放 `{{hud}}`，真界面写在规则里。

### 2.1 `<script>` 是一等公民

以下全部出自手册第 2 / 3 章：

- **抽取时机**：装卡那一刻被抽出，按规则顺序收集。
- **执行次数**：**整张卡只跑一次**（不是每条消息一次）。
- **是否需要被匹配命中**：**不需要** —— `<style>` / `<script>` 不论这条规则有没有匹配到都会装上。
- **顶层 `function` / `const` / `class`** 挂到 `window` 上，`onclick="tap()"` 找得到。普通标签 `onclick=""` 可用，但**`svg` 内部的 `onclick` 会被删**。
- **错误隔离**：一段脚本报错**只废掉它自己**，后面规则的脚本照跑；不弹窗，进调试面板。
- **切会话**：脚本**不重跑**，订阅**不清除**，舞台会被平台关掉 → 属于某个会话的计数要自己在 `conversation:switch` 里清。

因为「不命中也会装上」，**不能靠「让规则不匹配」来关掉样式**；反过来，官方首选写法就是利用这一点：

> **专开一条规则只放 `<script>`，匹配式填一个正文里用不到的词**（官方示例卡即 `scriptName: "kit"` / `findRegex: "{{eg-kit}}"`，谁都不引用）。同理一条只放 `<style>`，命名 `{{卡名-style}}`。

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

> 🚨 **`message:mount` 回调里的 `document.querySelector` 只在当前这条气泡内查找**（手册原话「被收成『只看当前气泡』」）。要查整页（功能栏、舞台）**不能**用它，要**从 `document.body` 出发，或用 `sdk.stage.el()`**。具体的作用域实现机制 `【原文未说明】`。

> 🚨 **`sdk.on` 只写在脚本体，绝不写进 `message:mount` 回调**。否则每挂一条气泡就多订一份，同一件事会触发很多次。官方校验对此有专项 WARN（`sdk.on('message:mount'` 之后 1200 字符内又出现 `sdk.on(`）。

### 2.3 未说明、不得断言的两点

- **沙盒是 iframe / Shadow DOM / 同一 document**：`【原文未说明】`。官方全目录无 iframe 作为运行容器的描述（`iframe` 只以「白名单外会被删的标签」出现），grep `shadow` 零命中。**不得断言任何一种**，也不要基于「同文档」去写跨帧/跨根的取巧代码。
- **`document.currentScript`**：`【原文未说明】`。官方全目录 grep `currentScript` 零命中。脚本是被平台「收集起来」后统一执行，但原文既没说它可用也没说不可用 → **不要用它做自定位**，per-message 定位一律走 `message:mount`。

作者代码里可以直接写 `document.querySelector`、`document.createElement`、`el.closest(...)`、`document.body`（手册与官方 fixture 都这么写），这是有明文依据的；仅「底层容器形态」无明文。

### 2.4 外链 `<script src>`

手册第 2 章：按书写顺序加载，**前一个加载完才跑后面的代码**；**同一个 URL 只加载一次**；地址必须 `https://` 开头，**`http://` 被直接跳过**；加载失败**不中断整张卡**，在调试面板留一行；域名还要在**平台白名单**里，自建域名先问平台。

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
- **瘦预览**：创卡页里那个预览是简化环境，改输入框、发送、存档一律 `NOT_SUPPORTED`；**样式与舞台可用**。要验完整行为必须回聊天页。逐能力待遇见 §4 表格「瘦预览」列。

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

可用载荷字段：`msg.content`、`msg.role`（值 `'ai'`）、`msg.id`。官方校验有专项 WARN：同一条规则里同时出现「订阅 `message:mount`」+「引用 `[data-chat="message-body"]`」+「有 `message.send(` 或 `message:stream`」就告警。

---

## 4. SDK：30 能力 / 12 事件

`sdk` 是平台挂在页面上的对象。**能力名与事件名拼错都不会报错，只是永远不生效／永不触发** —— 所以以下所有名字必须逐字照抄。官方校验会拿 `contract.json` 核对：`sdk.X` / `sdk.X.Y` 不在能力表 → ERROR；`sdk.on('X')` 的 `X` 不在事件表 → ERROR。

> 🚨 **`sdk.once` 与 `sdk.off` 都不存在。** `contract.json.capabilities` 里只有 `on`。写 `sdk.once(...)` 官方校验直接判 ERROR。取消订阅的 API `【原文未说明】`（原文只说「订阅在整个会话内存活，脚本源被替换时才清」）。
>
> **不需要 `once`**：`ready` 这类只发一次的事件**会补发给后来的订阅者**，晚订阅不会漏。

### 4.1 能力全表（30 个，签名逐字）

「瘦预览」列 = 创卡页预览环境的待遇。`sync` = 同步，`async` = **返回 Promise，必须 `.catch`**。

| 能力 | 参数 | 返回 | 同步性 | 瘦预览 |
|---|---|---|---|---|
| `input.get` | — | `string` | sync | 回空串 |
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
| `composer.visible` | — | `boolean` | sync | 回 false |
| `message.send` | `text?: string` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `message.edit` | `id: string`, `text: string` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `cache.get` | `key: string` | `unknown` | sync | 可用 |
| `cache.set` | `key: string`, `value: unknown` | `void` | sync | 可用 |
| `cache.remove` | `key: string` | `void` | sync | 可用 |
| `save.get` | `key: string` | `unknown` | sync | `NOT_SUPPORTED` |
| `save.set` | `key: string`, `value: unknown` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `save.remove` | `key: string` | `Promise<void>` | **async** | `NOT_SUPPORTED` |
| `save.keys` | — | `string[]` | sync | `NOT_SUPPORTED` |
| `stage.open` | `mode?: 'content' \| 'full'` | `void` | sync | 可用 |
| `stage.close` | — | `void` | sync | 可用 |
| `stage.el` | — | `HTMLElement \| null` | sync | 可用 |
| `stage.visible` | — | `boolean` | sync | 可用 |
| `role.get` | — | `{ name: string; avatarUrl: string }` | sync | 可用 |
| `user.get` | — | `{ nickname: string; avatarUrl: string }` | sync | 可用 |
| `on` | `event: string`, `cb: (payload) => void` | `void` | sync | 可用 |
| `debug.log` | `...args: unknown[]` | `void` | sync | 可用 |
| `version` | —（**是值，不是函数**，恒为 `'1'`） | `string` | — | 可用 |

> 瘦预览里 `input` / `composer` / `message` / `save` 整片 `NOT_SUPPORTED`，只有 `cache` / `stage` / `role` / `user` / `on` / `debug` 可用 —— 所以创卡页只能验样式与舞台，**输入框、发送、存档必须回聊天页验**。

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

**刷新页面就没**。只适合「面板开着还是关着」「滚动位置」这类当场要用的状态。**进度、血量一律用 `save`**。配额 `CACHE_QUOTA_BYTES` = 1048576（1 MiB），超限行为 `【原文未说明】`。

### 4.5 `sdk.save.*` —— 存档

落到服务端，**换设备还在**。约束：

| 项 | 值 |
|---|---|
| `SAVE_MAX_KEYS` | **10 个** → 把整套状态打成一包（一个对象）再存 |
| 存档名长度 | ≤ **64 字符** |
| 存档名字符 | **不能含冒号**（`hp:cur` 会被拒，用 `hp_cur`） |
| 值 | 必须可 `JSON.stringify`（函数、`Map`、循环引用存不进去） |
| 写入限频 | 1 分钟 **20** 次 |

`save.get` 是**同步**的，读的是进页时预载进来的那份内存副本。`set` / `remove` 必须 `.catch`（写法同上面 `message.send`），失败时页面上不会有任何提示。

> 🚨 **真红线：游客存档退出即失，且作者永远测不出来。** 游客身上写存档不报错，但只留在本地，**他登录时会被丢掉、不会迁移**。你的代码在游客和登录用户上表现一模一样 —— 而**你自己是登录态，永远碰不到这个差别**。平台会在游客第一次写存档时提示他登录。**所以别把「必须攒进度」做成这张卡唯一的玩法**：进度丢了也要能玩下去。

`save.set` 别在每帧或每次输入都写，把状态攒起来再写一次。

### 4.6 `sdk.stage.*` —— 舞台（瘦预览**全部可用**）

一块盖在聊天页上的空盒子，专门放要一直在的界面（地图、背包、小游戏）。

- `'content'` 盖住消息区，**顶栏和输入框还能用**；`'full'` 盖住整屏（**盖不住授权 / 充值那种系统弹窗**）；不传参默认 `content`。
- `stage.el()` **未打开时返回 `null`** → 必须判空。返回节点的内部平台不碰。
- **关掉再开，盒子里的东西还在**，不必每次重建。
- **自己调 `stage.close()` 不触发 `stage:close`**（那条只在平台关时发）。切会话时舞台会被平台关掉。

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

| 你想做的事 | 用这个 | 载荷 |
|---|---|---|
| 页面刚开好：读存档、第一次画界面 | `ready` | 无（只发一次，**晚订阅会补发**） |
| 给这条气泡里的按钮绑点击 | `message:mount` | 无（滚回来会再发；`querySelector` 只看当前气泡） |
| AI 说完了，读完整回复、按结局切剧情 | `message:done` | `msg.content` |
| 跟着一个字一个字往外蹦做动画 | `message:stream` | `msg.content`（**已攒原文，累积量**；触发极密，**回调里别查 DOM、别算布局**） |
| 气泡滚走了，停掉定时器 / observer | `message:unmount` | 无 |
| 用户换了一个会话，清掉上一场的计数 | `conversation:switch` | 无 |
| 用户切了深浅色 | `theme:change` | 无 |
| 输入框里的字变了，更新预览 | `input:change` | 无（自己 `sdk.input.get()`；**别在这里再 `input.set`**，会和拼音输入打架、绕成死循环） |
| 用户按了返回 | `back` | 无（舞台开着时平台先关舞台，**不一定轮到你**） |
| 平台把舞台关了 | `stage:close` | 无（作者调 `stage.close()` 不发） |
| 聊天页要关掉了，最后收尾 | `dispose` | 无 |
| 新消息刚出现，正文还是空的 | `message:new`（**几乎用不到**） | `msg.id` |

**日常做卡，`ready` + `message:mount` + `message:done` 三个就够。**

### 4.10 错误码（6 个）与限额限频

| code | 常见原因 |
|---|---|
| `UNAUTHORIZED` | 非手势路径发消息，用户没同意 |
| `RATE_LIMITED` | 写太勤或发太勤 |
| `INVALID_ARGS` | 空消息、存档名违规、正在拼音输入时改草稿、编辑一条不存在的消息 |
| `HOST_DENIED` | 存档还没准备好、发送通道没接上、切会话把这次作废了 |
| `NETWORK` | 请求发出去了但没成 |
| `NOT_SUPPORTED` | 当前环境没有这个能力，**多半是创卡页瘦预览** |

**限额**：`SAVE_MAX_KEYS` = 10、`CACHE_QUOTA_BYTES` = 1048576。

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

### 5.1 可读属性

`[data-chat="message"]` 上：`data-from`（`user` 或 `ai`）、`data-state`（如 `done`、`streaming`）、`data-msg-id`（**服务端认得这条时才有**，刚插入未落库的没有 → `message.edit` 前必须判空）。

`[data-chat="root"]` 上：`data-theme`（`light` / `dark`）、`data-composer`（底部输入区开着还是关着）。

### 5.2 标签白名单 / 黑名单

消息和功能栏里的 HTML 会过一遍净化，白名单之外的标签被丢掉（**里面的文字保留**）。

- **能用**：`div` `span` `p` `b` `i` `strong` `em` `br` `hr`、`h1`–`h6`、`ul` `ol` `li`、`table` `tr` `th` `td`、`pre` `code` `blockquote`、`button` `input` `textarea` `label` `select` `option`、`img` `video`、`details` `summary`、`svg` 及 `path` `circle` `rect` `line` `text` 等一套绘图标签
- **会被删**：`iframe` `link` `meta` `form` `object` `embed`
- `<style>` 和 `<script>` **不算被删**，它们被抽出来单独生效（见 §2）
- 普通标签上的 `onclick="tap()"` **能用**；写在 `svg` 里的 `onclick` **会被删**

> 🚨 **真红线：作者自己写的 `data-*` 会被净化删掉。** 自己的按钮/容器用 `class` 或 `id`。`[data-chat="…"]` / `[data-slot="…"]` 是平台的，只能读、可以当选择器。症状是「我写的 `data-xxx` 不见了」，随后所有依赖它的 `querySelector` 全查不到。官方校验对可见 HTML 上自写 `data-*` 有 WARN。

### 5.3 只改某一块

只改 AI 气泡：`[data-chat="message"][data-from="ai"] [data-chat="message-body"] { … }`。同理 `[data-from="user"]` 改用户气泡、`[data-chat="input"]` 改输入框、`[data-chat="header"]` 改顶栏背景。

---

## 6. CSS

所有规则里的 `<style>` **合成一张全页样式表，后写的盖住先写的**。样式是全页作用域、**无隔离** —— 多条规则的 `<style>` 互相覆盖是**预期行为，不是 bug**（症状：「样式在预览里对，上线不对」）。

### 6.1 10 个 `--chat-*` 变量

| 变量 | 说明 | 变量 | 说明 |
|---|---|---|---|
| `--chat-bg` | 整页背景 | `--chat-accent` | 强调色，按钮高亮、血条可以用 |
| `--chat-surface` | 卡片、面板这类块的底色 | `--chat-bubble-user-bg` | 用户气泡背景 |
| `--chat-text` | 正文颜色 | `--chat-bubble-ai-bg` | AI 气泡背景 |
| `--chat-text-muted` | 次要文字，比正文淡 | `--chat-bubble-text` | 气泡里的字 |
| `--chat-border` | 边框颜色 | `--chat-viewport-height` | 可视区域高度 |

气泡那三个默认等于页面的背景和文字，只改其中一个也不会和整页脱节。

换肤在 `[data-chat="root"]` 上改变量，**不要写死 `#fff`** —— 用变量深浅色切换时才跟得上。自己用 JS 涂的颜色要跟主题，就订 `theme:change`。算出来的值（进度条宽度、血条颜色）写在标签的内联 `style=""` 上；内联会压过 `<style>` 里的规则，颜色仍尽量用 `var(--chat-accent)`。

### 6.2 禁全局 CSS

> 🚨 **`*{}` / `html{}` / `body{}` / `:root{}` 全部禁用，改写成 `[data-chat="root"]`。** 官方校验检测式 `/(^|[\s,};])(\*|html|body|:root)\s*\{/` → WARN（注意 `:root{}` 也在名单里，脚本比官方文案更全）。

### 6.3 z-index 分段（约定，平台不执法）

**1000–1999 作者内容** · 2000 舞台 `content` · 3000 舞台 `full` · 8000–8999 平台 chrome · 9000–9999 平台模态。

越界不会被拦，**只会盖错东西** —— 作者面板超过 1999 会挡住长按菜单和提示。

### 6.4 功能栏样式全靠作者

`[data-slot="statusbar"]` **平台没给它任何样式**，背景、高度、粘顶（`position: sticky`）全要作者自己写。角色卡 `statusbar` 留空则这个节点**整块不存在**。

> 🚨 **真红线：用 JS 往功能栏塞节点留不住。** 功能栏 HTML 由平台按 `statusbar` 字段**整块**写进去；创卡页里每改一次规则这块就重画一次，`appendChild` 进去的东西会一起没。改里面已有节点的文字、class 没问题。**会变的内容写进规则，长期面板放舞台。**

### 6.5 Markdown 陷阱

替换内容会过一遍 Markdown。**HTML 不要缩进 4 个空格**，会被当成代码块原样显示（把源码印在页面上）。官方校验：`/^ {4,}</m` → WARN。

---

## 7. 正则 / 替换机制

一条规则三样东西：**名称**（给自己看）、**匹配式**（要被换掉的那段字）、**替换内容**（换上去的东西）。JSON 字段**恰好这四个**：

| JSON 字段 | 创卡页叫法 | 约束 |
|---|---|---|
| `id` | —— | **必须是负数**（`-1`、`-2`…），导入时会重编号。`typeof !== 'number'` 或 `>= 0` → ERROR |
| `scriptName` | 名称 | 非空、≤ 20 字 |
| `findRegex` | 匹配式 | 非空、≤ 1000 字 |
| `replaceString` | 替换内容 | ≤ 20000 字 |

多余字段 → WARN；缺任一字段 → ERROR。

### 7.1 匹配式两形态（权威判定 = 官方 `classifyPattern`）

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

由这段代码确证：**前置处理**先 `.trim()` 再剥掉首尾反引号；**`/pattern/flags`** → 正则，合法 flags **仅 `gimsuy`**（无 `d`、无 `v`），**缺 `g` 平台自动补** → 总是全文替换；**其余任何非空串** → **字面量**，元字符被转义（`a.b` 不匹配 `axb`），全文每处都换。

> 🚨 **与当前 MMD 的最大分歧：沙盒模式的 `findRegex` 不强制 slash literal。** 纯字面量标记（`{{hud}}`、`【图鉴】`）是**官方首选写法**，手册原话「多数规则都这么写」「不确定就用第一种」。当前 MMD 那条「必须写 `/…/`，裸模式测试能过但聊天页不替换」的实测铁律（`mmd.md` §8）**只适用于 `/mmd`，不要套到沙盒模式上**。

> 🚨 **写成 `/…/` 但正则语法错 → 整条规则被静默丢弃**，不降级成字面量，**页面上看不出异常**（只有告警）。官方校验对此判 ERROR。

> 🚨 **字面量匹配式不要重复。** 规则按数组顺序跑，前一条把全文换完了，后一条同串的规则**永远匹配不到**。官方校验判 **ERROR**。

### 7.2 替换内容里能取的值

| 记号 | 意思 |
|---|---|
| `$1`、`$2` | 正则里第 1、2 个括号捕获到的内容 |
| `$名字` | 第一个捕获组形如 `血量::10;;金币::3` 时，`$血量` 取到 `10`（键值分隔 `::`，条目分隔 `;;`） |
| `{{random:甲::乙::丙}}` | 三个里随机一个 |

```
findRegex:      /血量[:：]\s*(\d+)/
replaceString:  <div class="my-bar" style="width:$1%;height:8px;border-radius:4px;background:var(--chat-accent)"></div>
```

### 7.3 触发串必须接得上

**可见 HTML 的匹配式，必须能在 `statusbar` / `beginning` / 另一条规则的 `replaceString` 里找到**（链式触发被官方认可），否则页面上永不出现（官方校验 WARN）。人设里的「输出约定」必须和这些匹配式对得上 —— **模型写得出，规则才换得掉**。

反过来，只放 `<style>` / `<script>` 的规则，匹配式**故意谁都不引用**（`{{卡名-style}}` / `{{卡名-kit}}`），因为它们装卡时就被抽走，不需要被匹配到。

### 7.4 匹配式的内容禁令与转义

- `findRegex` 别含 HTML 标签（检测 `/<[a-zA-Z/]/` → WARN）。
- `findRegex` 别含**独立保留字** `html` / `head` / `body` / `css`（大小写不敏感，独立单词才命中，`htmlish` 不误报）→ WARN。
- 匹配式写太松（比如只写一个 `：`）会把正常对话切碎 —— 规则对**这张卡的每条 AI 消息**都生效，不是只作用在你测的那一条。
- JSON 字符串里 `</script>` 要写成 `<\/script>`，避免宿主页面提前截断。

### 7.5 官方推荐的拆条形态（三条起手）

`hud` / `{{hud}}` 放功能栏可见 UI（1～3 个按钮）· `卡名-style` / `{{卡名-style}}` 只放 `<style>`，谁都不引用 · `卡名-kit` / `{{卡名-kit}}` 只放 `<script>`，谁都不引用。

每块可见 UI 再各开一条（触发串进 `statusbar` 或 `beginning`）。**单条替换内容超 20000 字才继续拆**；不要一上来就切成 19 段，也不要复刻旧卡的 14 条侧边栏。

---

## 8. 平台硬上限

| 项 | 硬上限 | 超出后果 |
|---|---|---|
| `chatVersion` | 必须 `1` | 落到旧聊天页，SDK 与 `data-*` 全失效（官方 ERROR） |
| `pageDepth` | 固定 `2` | 只对旧页有意义，**新页不实现**；非 2 → 官方 WARN |
| `statusbar` | **200 字** | 官方 ERROR |
| `beginning` | **10240 字** | 官方 ERROR |
| `personality` | **10000 字** | 官方 ERROR（公开卡审核文案建议 2000–5000） |
| `scriptName` | **20 字** | 官方 ERROR |
| `findRegex` | **1000 字** | 官方 ERROR |
| `replaceString` | **20000 字** | 见下方说明 |
| `regex_scripts` 条数 | **130 条** | 官方 ERROR；导入时会被直接截断 |
| 世界书条目标题（`comment`） | **20 字** | 本 skill 保留，降级为 WARN（见 §10） |
| 角色卡格式 | **不用 chara_card_v2 / PNG 整卡** | 官方禁 PNG 整卡（见 §9） |

`replaceString` 的 20000 是**编辑器上限而非导入上限**（靠导入能绕过），但超了作者一进编辑器就被截断 → **照 20000 卡，超了拆条**。

### 8.1 顶层键白名单（恰好 6 键）

```
chatVersion  pageDepth  statusbar  beginning  personality  regex_scripts
```

**出现以下顶层键 → 官方判 ERROR**：`role`、`presentation`、`worldbook`、`world_book`、`lorebook`、`lore_book`、`entries`、`characterBook`、`character_book`。其他未知顶层键 → WARN（导入页不认）。

`regex_scripts` 为空数组**且** `personality` 空白 → ERROR「没有可交付物」。

> 注：官方示例卡 `authoring/example-card/card.json` 用的是 `role` / `presentation.transforms[]` 形状 —— 那是**回归夹具，不是导入格式**，照抄会被判 ERROR。

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
    { "id": -1, "scriptName": "hud", "findRegex": "{{hud}}", "replaceString": "<div class=\"my-hud\">…</div>" }
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

当前 MMD 的 15000 字固定传输上限（`mmd.md` §7）在沙盒模式下**官方资料未提及** —— `【待验证】`。官方只给了 `personality` 10000、`beginning` 10240 这两个字段级上限。因此：

- 字段级上限按 §8 硬卡（有官方明文）。
- 蓝灯世界书条目 + 人设的**合计**是否仍有 15000 常驻预算，未知。稳妥做法是**继续按 15000 预算控制蓝灯总量并留 2000–3000 字缓冲**，直到实机复验。

---

## 11. 排查表：出问题先看这里

沙盒模式的故障**不弹窗**，报错进页内调试面板（聊天页 URL 加 `?sdkDebug=1` + `sdk.debug.log`）。手机上没有控制台，这是唯一的观测口。

| 症状 | 根因 | 修法 |
|---|---|---|
| 按钮全不响应、样式对一半、SDK 全不在 | 卡不是新页（`chatVersion` 没生效，或给已存在的卡导入被忽略） | 新建卡 + 创卡页确认新页（§0） |
| 点了发送，画布上出现「消息生成中」，stream 已经在吐字 | 在 `message:mount` 里读 `[data-chat="message-body"]` 当回复 | 跟字用 `message:stream` 的 `msg.content`，收尾用 `message:done`（§3） |
| 按钮点了没反应 | 绑事件写到脚本顶层了；气泡滚出屏幕会被拆掉 | 绑定写进 `sdk.on('message:mount')`（§2.2） |
| 同一件事触发了好几次 | `sdk.on` 写进 `message:mount` 回调里了 | 订阅只写在脚本体，一次就够（§2.2） |
| 我写的 `data-xxx` 不见了 | 净化删掉作者自写 `data-*` | 用 class 或 id（§5.2） |
| 事件一次都不触发 | 事件名写错，**平台不报错** | 照 §4.9 的 12 个名字抄 |
| 能力调用完全没反应 | 能力名写错，**平台不报错** | 照 §4 能力全表抄 |
| 样式在预览里对，上线不对 | 别的规则也带 `<style>`，全页合成、后写盖先写 | 加 class 前缀、排查覆盖顺序（§6） |
| 画的东西滚一会儿就没了 | 长期面板挂在气泡里，气泡销毁即没 | 挂舞台 `sdk.stage`（§4.6） |
| 往功能栏 `appendChild` 的东西会消失 | 功能栏由平台整块重画 | 会变的内容写进规则，长期面板放舞台（§6.4） |
| 预览里调什么都报 `NOT_SUPPORTED` | 创卡页是瘦预览，input / send / save 全不开放 | 回聊天页验（§2.5） |
| 某条规则完全没生效、页面无异常 | 写成 `/…/` 但正则语法错 → **整条静默丢弃** | 校验匹配式；不确定就用字面量（§7.1） |
| 后面那条同标记的规则永不生效 | 字面量匹配式重复，前一条已换完全文 | 换标记；官方判 ERROR（§7.1） |
| 界面上那块 UI 永远不出现 | 触发串没接到 `statusbar` / `beginning` / 别的 `replaceString` | 接上触发串（§7.3） |
| 源码被原样印在页面上 | HTML 缩进了 4 个空格，被 Markdown 当代码块 | 顶格写（§6.5） |
| 外链库 `window.XXX` 是 undefined | 用了 `http://`（直接跳过）或域名不在白名单 | 换 `https://` + 问平台白名单；查调试面板（§2.4） |
| `message.edit` 报错 / 拼出 `null` | 刚插入未落库的消息没有 `data-msg-id` | 调用前判空（§4.3） |
| 发消息报 `UNAUTHORIZED` | 不是用户手势当帧（先 `await` 了，或定时器里发） | 点击当帧直接 `send`（§4.3） |
| 存档/发送报 `RATE_LIMITED` | 超限频 | 攒批再写；照 §4.10 的次数控制 |
| 存档在别人手机上全丢 | 游客存档退出即失、登录不迁移，**作者自己测不出** | 别把攒进度做成唯一玩法（§4.5） |
| 面板挡住了平台长按菜单/提示 | z-index 超出作者段 | 压回 1000–1999（§6.3） |
| 自问自答死循环 | `message:done` 里无条件 `message.send` | 加条件或改用 `input.set`（§4.3） |
| 剧情跳一轮 / 卡在等待态 | `content` 空时退回去读 DOM，读到占位就清了等待态 | 用 `isReplyText` 判别（§3） |

### 11.1 官方「别这么写」清单（逐条对照 §4 已展开）

`input.get` 别轮询 · `input.set` 别在 IME 组合期调 · `input.add` 别逐字追加 · `input.insert` 别假设光标不动 · `input.clear` 发送后不用自己清 · `input.focus` 别在页面刚加载时调 · `input.setCursor` 别拿它模拟选区 · `composer.hide` 藏了要给发送路径 · `message.send` 别在 `message:done` 里无条件调 · `message.edit` 别拿 `null` 当 id · `cache.*` 别存进度 · `save.set` 别每帧写 · `stage.open` 别每次重建内部 DOM · `stage.el` 别当消息容器 · `user.get` 别当登录态判断 · `on` 事件名别打错 · `version` 别做能力探测。

### 11.2 从当前 MMD 迁过来时必须扔掉的东西

- **`img onerror` 点火器 / 雷达法引擎 / teapot 系**（`onerror` 图、`window.teapot*`、CoC 注入）→ 一条只放 `<script>` 的规则 + `sdk.on('message:mount')`。官方明令禁 teapot。
- **`window.__fn` + `onclick="window.__fn&&__fn()"` 那套净化绕行**、**轻主板 + 胖遥控器**（`data-s` + `eval`）→ 都不需要：顶层 `function` 直接挂 `window`，普通标签 `onclick="tap()"` 就能用；且作者自写 `data-*` 会被删。
- **`【侧边栏1】`…`【侧边栏14】` 屏外注入切片** → 功能栏是**可见槽位不是注入口**；`statusbar` 放 `{{hud}}` + 长期面板放舞台。
- **`[sta` + `tus]` 拆词绕检测** → `/\[status\]([\s\S]*?)\[\/status\]/` 一条真正则吃整块。
- **Shadow DOM 状态栏（`attachShadow`）与 `document.currentScript` 自定位** → 沙盒形态与 `currentScript` 均 `【原文未说明】`，不要移植；定位改用 `message:mount`。
- **chara_card_v2 / PNG 打包** → 正则 JSON + persona 文本（§9）。

对抗检定 `〖⚔=①…〗` 这类，用户没点名就不要做；骰子标记用 ASCII 分隔 `〖骰=检定名|属性|目标|出目|成功或失败〗`。

---

## 12. 写作策略

1. **起手三条规则**：一条 `{{卡名-style}}` 只放 `<style>`，一条 `{{hud}}` 放功能栏可见 UI，一条 `{{卡名-kit}}` 只放 `<script>`。每块新增可见 UI 再各开一条并接上触发串。
2. **状态栏 / 面板**：短小可见块走规则替换（`$1` / `$名字` 直出 HTML，零 JS）；有交互、要跟剧情变的走 `<script>` + `message:done` 解析 `msg.content` 再渲染；要一直在的（地图、背包、小游戏）**一律挂舞台**。
3. **状态持久化**：当场状态 `sdk.cache`，跨设备进度 `sdk.save`（打成一包、≤10 个 key、攒批写）。**游客会丢，别做成唯一玩法。**
4. **配色**：只改 `[data-chat="root"]` 上的 10 个 `--chat-*` 变量，不写死颜色；JS 涂色的订 `theme:change`。
5. **验证顺序**：创卡页瘦预览先看样式与舞台 → 回聊天页加 `?sdkDebug=1` 验输入框/发送/存档 → 按 §11 排查表定位。
6. **交付**：正则 JSON + persona 文本（+ 可选世界书 JSON），并在交付说明里写明「必须新建卡、创卡页确认新页」。

---

## 相关文档

- `mmd.md` —— 当前 MMD（`/mmd`）平台规范，`img onerror` 载体那一套。**两边写法不通用**，注意别串。
- `sillytavern.md` —— 本地酒馆平台规范。
- `../output/regex-output.md` —— 正则 JSON 交付与转义（沙盒模式是 6 字段，注意与当前 MMD 的 4 字段区分）。
- `../output/worldbook-json.md` —— 世界书条目字段与导出。
- `../output/card-json.md` —— chara_card_v2 打包，**沙盒模式不用**，仅当前 MMD / 本地酒馆用。
- `../quality/checklist.md` —— 交付前自检。
- `../beautify/statusbar.md` / `../beautify/statusbar-radar.md` —— 当前 MMD 的状态栏方案，**沙盒模式不可直接移植**（载体是被禁的 `img onerror`），只可参考数据协议与信息架构。
- `../beautify/global-css.md` / `../beautify/style-system.md` —— 视觉设计思路可复用，选择器与变量须换成 `[data-chat]` / `--chat-*`。

