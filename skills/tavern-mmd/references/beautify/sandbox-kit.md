# 沙盒基座 SBK —— MMD沙盒模式的状态栏与美化方法论

> MMD沙盒模式（`/mmdsandbox`）专用的状态栏 / 美化方法论。代号 SBK（SandBox Kit）。
> **不止状态栏**：同一套地基做常驻 HUD、消息内快照、悬浮球、侧边抽屉、舞台面板。
> 现成资产与生成器在 `../../assets/sandbox-kit/`，改配置即可复用；协议与 schema 完整参考在 `../../assets/sandbox-kit/sbk/协议说明.md`。

> 🚨 **平台归属：本方法论只针对 MMD沙盒模式（`/mmdsandbox`）。** 它全程依赖 `sdk.*` 与 `[data-chat]` / `[data-slot]` DOM 契约，这两样**只在沙盒新聊天页存在** → 不能用于当前 MMD（`/mmd`）与本地酒馆（`/st`）。反向亦然：雷达法与影渲法**不能用于沙盒**，理由见末节。

> ⚠️ **验证状态**：本文档陈述的**平台事实**（事件时序、CSS 令牌、净化行为、层级）来自**三轮真机探针 + 沙盒应用逆向源码**，可信度高。而**基座代码本身只过了分层单元自测**（内核 56 / 协议+HUD 151 / 组件 47 / 生成器 133 项）+ `node --check` + 产物校验，**尚未导入真实卡片做端到端实机验证**。
> 🚨 且有一个**已知阻断缺陷**：生成器产出的 boot 规则调用 `SBK.boot(...)`，而运行时**从未定义该函数** → 当前产物导入后各组件不会启动。详见 `../../assets/sandbox-kit/README.md` 的「已知缺陷」节。读本文档时请把它当**设计规范**看，别当「已验收的成品说明」。

平台事实一律不在本文档展开，指向 `../platforms/mmd-sandbox.md`（1231 行，已含全部实测修正）。本文档只讲**方法论与设计思路**：为什么必须这么做。

## 一、为什么沙盒需要一套新方法论

既有两套方法（雷达法 `statusbar-radar.md`、影渲法 `statusbar-shadowcast.md`）都建立在同一组前提上：

1. **`img onerror` 点火**——没有 `<script>` 可用，只能靠图片加载失败触发内联 JS；
2. **Shadow DOM 隔离**——light DOM 里的 UI 会过 markdown 管线、被平台强制染色、类名互撞，所以要躲进 shadow root。

沙盒把这两条前提**同时推翻**：

| 前提 | 沙盒实况 | 结论 |
|---|---|---|
| 只能 `img onerror` 点火 | `<script>` 是**一等公民**，装卡即抽出并执行；且官方**明令禁止** `img onerror` 点火器与 teapot 系写法 | 点火器整套删掉，直接写脚本 |
| 需要 Shadow DOM 隔离 | 沙盒是部署在 `c<卡片ID>.sbx.aitchat.org` 的**独立 Vue 应用，以跨源 iframe 嵌入宿主**。实测 `getRootNode()===document` 为真、`window===window.top` 为 **false** | **iframe 本身就是隔离边界**，隔离已经免费到手 |

第二条是根本理由，值得说透。跨源 iframe 意味着：作者代码跑在**自己的文档、自己的源**里，不可能污染宿主，宿主样式也漏不进来。此时再套一层 Shadow DOM，收益为零，代价却实打实：

- 平台的 14 个 `--chat-*` 设计令牌定义在 iframe 文档的 `[data-theme]` 上，shadow 内**继承不到**具体规则，主题跟随得自己重新搭一遍；
- 平台 CSS 变量、`--rpx` 尺寸基准全部要手动透传；
- 调试成本翻倍（devtools 里每层都要展开）；
- `adoptedStyleSheets` 那套跨气泡缓存优化，在只有一个文档的沙盒里没有意义。

→ **Shadow DOM 在沙盒是纯负债**（事实卡 §一 / 硬约束 1）。SBK 全程用 light DOM + `sbk-` 类名前缀。

顺带说明：`localStorage` 在沙盒里按卡天然隔离（不同源），可以放心当单卡本地偏好用；但**不能跨卡共享**，跨设备同步仍须走 `sdk.save`。

## 二、沙盒的三个决定性约束

这三条不是「注意事项」，它们**直接决定架构必须长成什么样**。

### 2.1 功能栏是静态的 → 动态状态栏只能靠 JS 改 DOM

平台渲染功能栏的 `h_()` **只在装载时调用一次**，主包里没有任何重渲染路径；更关键的是**它的正则输入是卡片 `statusbar` 字段自身，而不是消息内容**（事实卡 §5.6 / 硬约束 14）。

所以「常驻状态栏跟着对话更新」这件事，**靠正则永远做不到**。做卡人最常见的头号困惑——「我的状态栏第一轮对了，后面再也不动」——根因就在这里。

→ 状态栏必须是 **JS 在事件回调里重绘 DOM**。功能栏字段只负责放一个**宿主容器的占位标记**，之后全程由 JS 接管。

顺便一个好消息：`[data-slot="statusbar"]` 是 `[data-chat="root"]` 的 flex item，**天然不随消息列表滚动**，不需要自己写粘顶。但它**没有 `flex-shrink:0`**（`header` 和 `composer` 都有，唯独它没有），内容一多就被压扁 → 基座必须自己补上（事实卡 §7.3 / 硬约束 13）。

### 2.2 作者脚本早于 DOM 执行、`ready` 最后到且无补发 → 冷启动只能挂 mount/done

两个实测事实叠在一起，把冷启动的写法逼成唯一解：

**其一，脚本跑完时 DOM 还不存在。** 探针在脚本顶层调 `document.getElementById('pbOut')` 取自己刚「写入」功能栏的节点 → **返回 `null`**；同一探针在事件回调里再取 → **成功**。`<style>`/`<script>` 是装卡即抽出并立即执行的，而功能栏与消息 HTML 由 Vue 在之后才挂进 DOM（事实卡 §4.1 / 硬约束 17）。

→ **顶层直接渲染必然失败。任何 DOM 写入都必须发生在事件回调里。**

**其二，`ready` 是最后到的，而且没有补发。** 实测冷启动事件到达顺序：

```
message:new  →  message:mount  →  message:done  →  ready
```

这跟「ready 表示页面就绪、可以做首屏」的直觉**完全相反**。而且 `ready` **没有 late replay**，有补发的反而是 `message:mount` 与 `message:done`（与官方手册说法相反）。更糟的是外链脚本未被 await，首个外链之后的内联脚本注册的 `ready` 回调**永久收不到**（事实卡 §3）。

→ **首屏渲染只能挂 `message:mount` / `message:done`**（有补发，历史气泡也会被处理），挂 `ready` 会晚一整轮甚至永远不到（硬约束 5）。

### 2.3 `sdk.on` 无 `off`/`once` + 预览会重跑 → 必须单例幂等

`sdk.on` 返回 `undefined`，**没有 `off`、没有 `once`**（实测 `sdk.off` 与 `sdk.once` 均为 `undefined`，双重确认）。唯一的退订是内部 `Ac()`，而它会**清掉所有脚本的全部订阅**——跨脚本互相干扰，不能用。

同时：「整卡只跑一次」仅在 chat / share 页成立，**创卡页预览会反复重跑整卡脚本**（事实卡 §3）。

两条相乘 = 每次预览重跑都会**再订阅一遍**，事件触发 N 次，状态栏渲染 N 份。

→ 基座必须**单例 + 幂等**：自带「已初始化」哨兵，对每个 sdk 事件**只订阅一次**，内部再分发给多个消费者。这样对外还能提供一个真正的 `off`（内核自有分发层可以退订，sdk 那层不行）。

## 三、双模状态栏

上面 2.1 决定了常驻状态栏必须靠 JS。但「靠 JS 重绘」有个副作用：**状态只有当前值，历史留不下痕**。回滚到三十轮前，状态栏显示的还是最新值。

所以 SBK 提供**两种模式，可并存**：

| | **模式 A 常驻 HUD** | **模式 B 消息内快照** |
|---|---|---|
| 载体 | `[data-slot="statusbar"]` 内的宿主容器 | 每条 AI 气泡内部 |
| 更新方式 | JS 在 `message:done` 后重渲染 | 正则一次性渲染，之后不再变 |
| 随滚动 | **不消失**（root 的 flex item） | 跟着气泡滚走 |
| 历史 | 只有当前值 | **每轮留痕，可回溯** |
| 适合 | 血量 / 资源 / 好感这类「当前值」 | 战斗结算、事件快照、需要回看的记录 |

**怎么选**：想要「抬头就能看到现在多少血」→ A。想要「翻回去看第五轮打赢时掉了多少」→ B。两个都要就都开，它们**共用同一份数据协议与渲染器**——协议解析出的状态对象，既能喂给 HUD 重绘，也能被快照就地渲染成 HTML 字符串。自定义控件写一次，两个模式都能用。

### 🚨 模式 B 的根元素必须带 `.sbk-snap`

平台给 `[data-chat="message-body"]` 写了两个属性，会把气泡内的自定义 UI 毁掉（事实卡 §7.3 / 硬约束 11、裁决 4）：

- **`white-space: pre-line`** —— 你 HTML 里的换行与缩进会被当**真实换行**渲染出来，排版全烂（这就是雷达法时代著名的「markdown 空白条」在沙盒的等价物）；
- **`opacity: .9`** —— 建立**层叠上下文**，把浮层囚禁在气泡内，且整体发灰。

`base.css` 靠 `.sbk-snap` 这个类名定点重置这两项：

```css
[data-chat="message-body"]:has(.sbk-snap) { opacity: 1; }
[data-chat="message-body"] .sbk-snap,
[data-chat="message-body"] .sbk-snap * { white-space: normal; }
```

用 `:has()` 把作用域收窄到**确实含基座内容的气泡**，不粗暴影响平台正文渲染。→ 快照根元素**少了这个类，重置就不生效**，症状是排版莫名散开且发灰。

模式 B 还有个设计取巧处：正则**不负责计算**。它只把 `[状态]…[/状态]` 换成 `<div class="sbk-snap sbk-snap--raw">原文</div>`（纯文本，天然无净化风险），真正的结构化渲染由 `SBK.ui.snapshot.hydrate()` 在 mount 回调内接管。好处是百分比、进度条宽度这类计算全在 JS 里做，正则只搬字符串——正则算不了数，硬凑会写出极长的替换文本，反而撞上输出预算。

## 四、三层架构

- **内核层** `core.js` —— 单例哨兵 / 事件总线 / 状态仓 / 持久化 / rAF 调度 / DOM 工具
- **主题层** `theme.js` —— 语义 token → 平台 `--chat-*`，三态 dark/light/native
- **组件层** `protocol.js` 协议解析、`hud.js` 双模状态栏、`ui.js` panel（浮层/抽屉/悬浮球）、`ui-stage.js` stage（舞台面板）

分层的意义不是好看，是**把平台坑收敛到一处**。做卡人调 `SBK.dom.h()` 建元素，就自动拿到了「拒绝 `data-*`/`aria-*`」「拦截 `]>` 属性值」「SVG 内 `on*` 告警」三重防御，不需要记住净化器的行为。

### 4.1 `window.SBK` API 速查

签名与 `../../assets/sandbox-kit/sbk/` 下真实代码一致。

**内核**

```js
SBK.version                     // '1'
SBK.claim(name)                 // -> boolean。已占用返回 false，调用方必须据此短路
SBK.on(evt, fn)                 // fn(payload, bubbleRoot)
SBK.off(evt, fn)                // -> boolean。内核自有分发，不依赖 sdk
SBK.emit(evt, payload, root)
SBK.log(...) / SBK.warn(msg, extra)
SBK.sdk                         // 启动时的 sdk 快照，不受后续改写影响
```

事件名（内核已把平台事件改成短名）：`mount` / `done` / `stream` / `unmount` / `theme` / `switch` / `ready` / `state`，以及**保留原名不缩写**的 `stage:close` / `back` / `dispose`。

🚨 **回调第二参 `bubbleRoot` 是内核合成的**，不是 SDK 给的（SDK 回调实测只传 1 个实参）。内核只对 `mount`/`done`/`stream` 合成气泡根，其余场景恒为 `null`。**消费方必须用第 2 参查气泡内元素，禁止自己 `document.querySelector`**——理由见 9.3。

**状态仓 / 持久化 / 调度**

```js
SBK.state.get()                 // -> 不可变快照
SBK.state.patch(partial)        // 合并，触发 'state'
SBK.state.replace(next)
SBK.state.subscribe(fn)         // -> unsubscribe

SBK.store.key(k)                // 改存档 key（校验 ≤64、禁 ':'）
SBK.store.load()                // 同步。任何异常都返回 null，绝不外抛
SBK.store.save(obj?)            // 异步 + 800ms 节流；缺省存 state.get()
SBK.store.clear()

SBK.schedule(fn)                // rAF 合帧，同一 fn 每帧只跑一次
```

**DOM 工具**

```js
SBK.dom.h(tag, attrs, children) // 建元素。自动拒 data-*/aria-*/role，拦 ]> 属性值
SBK.dom.mountHost(id)           // 在 statusbar 槽位内取/建宿主容器，必须在事件回调内调
SBK.dom.inBubble(root, sel)     // 在 root 内查（不走 document）
SBK.dom.all(root, sel)          // -> 数组
```

**主题**

```js
SBK.theme.apply(tokens)         // {bg:..} 两套同值 / {dark:{},light:{}} 分别 / null|'native' 清空
SBK.theme.mode()                // -> 'dark'|'light'，从 DOM 读
SBK.theme.onChange(fn)          // -> unsubscribe。会立刻用当前值调一次
SBK.theme.vars()                // -> 14 个平台后缀名
SBK.theme.base()                // -> 实测深色基线副本，供「微调而非全替」
SBK.theme.current()             // -> 最近一次 apply 的入参，native 时为 null
SBK.theme.reset()
```

**协议与组件**

```js
SBK.parse(text)                 // -> {state, order, cleanedText, skipped} | null
SBK.parse.pattern(cap?)         // -> 推荐匹配式字符串（slash 形态）
SBK.parse.config({block:'状态'})
SBK.parse.value(raw)            // 单值分类器

SBK.ui.hud(hostEl, schema)      // -> {el, render, feed, mount}
SBK.ui.hud.type(name, fn)       // 注册自定义控件
SBK.ui.snapshot(state, schema)  // -> HTML 字符串（模式 B）
SBK.ui.snapshot.auto(schema)    // 装一次，自动升级所有气泡
SBK.ui.panel(opts)              // -> {el, ball, box, open, close, toggle, opened, setContent, move, destroy}
SBK.ui.stage(opts)              // -> {open, close, toggle, visible, el, box, mode, rebuild, render, destroy}
```

## 五、数据协议：为什么自己造

平台自带取值语法 `$名字`，看着现成，但**表达力不够**（事实卡 §5.3）：

- 数据源**固定是 `$1`**——只能从第一个捕获组取值，多字段得自己在一个组里塞完；
- `$1` 必须**同时含 `::` 与 `;;`** 才会被解析（形如 `键::值;;键::值`），格式僵硬；
- `{{random:A::B::C}}` 因为用 `[^}]*` 匹配，**不支持嵌套、不支持权重**。

状态栏要的是「血量 72/100、好感 熙宁=61 阿澈=25、标记 中毒,疲劳」这种嵌套结构，`$1` 那套写起来又长又脆，而且**算不了百分比**。

→ SBK 改用**由基座 JS 解析的块协议**。模型只需在正文末尾输出：

```
[状态]
体力: 84/100
灵力: 30/60
银钱: 12
好感: 苏九=5, 阿澈=25
标记: 初来乍到, 疲劳
[/状态]
```

`键: 值` 逐行解析；`a/b` 自动识别成进度条，`名=数` 逗号分隔识别成多实体表，逗号分隔纯文本识别成标签组。**容错优先**——模型格式漂移（中英标点混用、markdown 列表前缀、漏闭合标记）都不应该让状态栏崩掉，单行解析失败只跳过那一行。

### 🚨 协议标记必须用方括号 `[状态]`

worker 用这个正则剥掉非白名单标签（事实卡 §5.4）：

```
/<\/?([\u4e00-\u9fa5a-zA-Z0-9_]+)(\s+[^>]*)?>/g
```

`<状态>` 是中文标签名，**不在白名单里 → 整个标签被删掉**（文字保留、标签消失）。这个坑很隐蔽，因为**正则管线跑在剥壳之前**：模式 B 的正则**看得见** `<状态>` 所以能匹配成功，但模式 A 的 HUD 从气泡文本兜底读取时，标记已经没了 → 解析必然失败。表现是「快照能渲染，常驻状态栏死活不动」。

方括号不是标签，**全链路都活着**（裁决 9）。解析器为了兼容也认尖括号与书名号三族写法，但**文档、`personality`、默认值一律用方括号**，别改回去。

协议的完整格式、容错清单、schema 字段、控件类型、模型侧输出约定模板 → `../../assets/sandbox-kit/sbk/协议说明.md`（本文档不重复）。

## 六、主题

平台每套主题 **14 个** `--chat-*` 令牌，定义在 `[data-theme=dark]` 与 `[data-theme=light]` 上。**官方手册只记了 10 个**，漏掉 `--chat-share-pick-bg`、`--chat-input-bg`、`--chat-input-text`、`--chat-shortcut-text`、`--chat-more-item-bg`（事实卡 §7.1）。另有 `--rpx = calc(100vw / 750)` 是平台全部尺寸的基准，**只读不写**，改它整体错位。

### 换肤写哪个选择器

```css
[data-chat="root"][data-theme="dark"] { --chat-accent: #c8a15a; }
```

理由是特异度算术（事实卡 §7.1 / 硬约束 10）：平台令牌写在 `[data-theme=dark]` 上，特异度 **(0,1,0)**；而 `data-theme` 与 `data-chat="root"` 绑在**同一个 div** 上，所以两个属性选择器叠起来得 **(0,2,0)**，稳定高于平台 → 深浅色切换**不会被覆盖回去，且不需要 `!important`**。

对比两个错误写法：
- 只写 `[data-theme=dark]` → 同特异度，靠源顺序取胜，**脆**；
- 写 `:root` → **完全无效**。平台**没有 `:root` 定义、没有 `prefers-color-scheme`**，覆盖一个不存在的定义不会生效。

还有一个陷阱：`--chat-viewport-height` **不是样式表变量**，是 JS 写在 root 上的**内联 style**（`clientHeight - 键盘 inset`，随 `visualViewport` 更新）→ CSS 覆盖不了它。

### 唯一需要 `!important` 的地方

`[data-chat="root"]` 带**内联** `background-image`。内联样式优先级高于任何选择器特异度 → **换页面背景必须 `!important`**（硬约束 20）。这是全基座唯一该用 `!important` 的地方，其余靠 (0,2,0) 就够。

⚠️ 只改 `--chat-bg` 换不掉背景：内联写的是 `background-image` **属性本身**，不是变量。`SBK.theme.apply({pageBgImage: 'none'})` 才行——主题层对这几个页面级属性自动加 `!important`。

实测深色真值（`accent` 是 `#ff6d97`，页面/用户气泡/AI 气泡**三者同色** `#17181a`）见事实卡 §九。想做气泡与页面分层，必须自己拉开对比度，平台默认是平的。`SBK.theme.base()` 返回这份基线副本，供「微调而非全替」。

## 七、组件层

### 7.1 浮层挂哪里

挂 `[data-slot="left"]` 或 `[data-slot="right"]`。它们是 `[data-chat="root"]` 的直接子节点，**祖先链上没有 `opacity`/`transform`/`overflow` 陷阱**（事实卡 §7.3）——这点很关键，任何一个都会建立层叠上下文或裁剪，把 `position: fixed` 的浮层囚禁住。

反面教材：把浮层塞进气泡里。`message-body` 带 `opacity:.9` 就是个层叠上下文，浮层再怎么调 z-index 也飞不出气泡。

### 7.2 z-index 安全带是 3500–7999

**手册说的「平台 chrome 占 8000–8999，作者用 1000–1999」不成立。**

实测穷举平台 11 条 z-index：`10090` snackbar / `9000` alert / `8200` message-menu / `8100` composer-snack / `8000` share-shot-loading / `3000` stage-full / `2000` stage-content / `40` sdk-debug / `10` assistant-tip / `2` history-loading / `1` rate-tip。而 `header`、`statusbar`、`messages`、`composer`、`stage` 探针实测**全部 `z-index: auto` + `position: static`**——它们只是 root 的普通 flex item（事实卡 §7.2）。

→ 作者用 1000–1999 **会盖住 header 和输入框**。目前没出事只是因为作者内容大多落在带 `opacity:.9` 的 `message-body` 里，被层叠上下文囚禁住了——**这是偶然保护，不可依赖**。

**3500–7999** 是唯一安全带（硬约束 12）：避开 `stage-full` 的 3000，也避开平台弹窗的 8000+。基座预置 `--sbk-z-panel: 3500` / `--sbk-z-pop: 3600`。

### 7.3 舞台开关只能用 `stage.visible()`

手册明说「舞台没打开时 `stage.el()` 是 null」，**这是错的**。实测 `stage.visible() === false` 时 `stage.el()` **仍然返回一个 `<DIV>`**（事实卡 §4.4b / 硬约束 19）。

→ 任何 `if (stage.el())` 都会**误判为已打开**。判断开关**只能** `stage.visible()`。

另一个配套坑：`sdk.stage.close()` **不派发** `stage:close`——那个事件只在**平台侧**关闭时发（用户按返回键等）。所以自己调 `close()` 之后必须**主动同步内部状态**，不能等事件回来。`SBK.ui.stage` 的 `onClose(api, byPlatform)` 第二参就是用来区分这两种来源的。

## 八、工作流

① 复制 `sbk.config.example.json` → ② 改 `theme`/`schema`/`beginning`/`personality` → ③ `build_sbk.py --out … --verbose`（看拆条与体积报告）→ ④ `validate.py --platform mmdsandbox` 须 0 错 → ⑤ 创卡页「**导入正则**」导入 JSON，再把 `personality` **手工粘贴**进人设框（导入页不读该字段）。命令原文见 `../../assets/sandbox-kit/README.md`。

**沙盒不用 PNG 整卡、不用 `chara_card_v2`**——交付物就是一份 6 键 JSON。

生成器替你兜住的事：剥注释、按文件边界自动拆条并保持装载顺序、估算每条规则的输出预算、校验标签白名单与净化合规、`</script>` 在 JSON 序列化层转义。这些都是「不做会静默失效」的类别。

首次实机导入建议 URL 加 `?sdkDebug=1`，`SBK.log` 全部走 `sdk.debug.log`，那是**手机上唯一可见的日志通道**。

## 九、避坑清单

事实卡 21 条硬约束里与基座使用相关的，按「症状 → 原因 → 做法」列。

| 症状 | 原因 | 做法 |
|---|---|---|
| 状态栏第一轮对，之后再也不动 | 指望功能栏正则刷新。`h_()` 只在装载时跑一次，正则输入是 `statusbar` 字段自身（§5.6） | 功能栏只放宿主容器标记，之后 JS 在 `message:done` 里重绘（硬约束 14） |
| 顶层写好的渲染代码完全没效果 | 作者脚本早于 DOM 执行，顶层取节点实测返回 `null`（§4.1） | DOM 写入放进事件回调（硬约束 17）。基座 `defer()` 会把顶层调用自动排到首个 mount/done |
| 异步里查气泡元素永远是 `null` | 平台**全局改写了 `Document.prototype.querySelector` 等 5 个方法** + 模块级游标 `gc`。`gc === null` 时气泡内元素查不到；`gc` 只在 mount/done 回调与 `click/input/change/keydown` 捕获阶段非空，**跨 `await`/`setTimeout` 即失效**（§4.3） | mount 回调内**同步就地抓引用**存进闭包，用 `SBK.dom.inBubble(root, sel)` |
| 创卡页预览一打开就整卡炸掉 | 瘦预览下 `save.get`/`save.keys` **同步抛 `SdkError`**（不是返回 `NOT_SUPPORTED`，包分析原说法已被实机推翻，§4.4a）。**最易翻车处** | `store.load()` 必须 try/catch。基座已兜两层，异常一律返回 `null`。降级链 `save → cache → 内存`（`cache.get` 实测返 `undefined` 不抛） |
| 规则装上了但整条不生效，只有告警 | 输出预算 `max(262144, 输入长度×4)`，**按条累计所有匹配的输出**，超限**整条回滚**（§5.2，手册与三份包分析均未提）。告警分 `replacement-alone`/`volume`/`empty-match` | 单条远低于 256KB；**匹配式绝不能匹配空串**。`/(?!)/` 是恒失败（安全但无用），`/a*/` 这类才触发回滚（裁决 6） |

| 匹配式明明写对了却不替换 | 实机上裸字面量 `{{probe}}` **未生效**，改 `/{{probe}}/` 立即生效。与 worker 源码 `p()` 的字面量分支矛盾，说明宿主侧在交给 worker 前另有一层处理（§5.4 / 硬约束 21） | `findRegex` **一律 `/…/` slash 形态**。`{}` 在非量词位置无需转义，但**方括号是元字符必须转义**：`/\[状态\]([\s\S]*?)\[\/状态\]/`。漏转义会变成字符类（匹配「状」「态」任一字符），静默失效且极难排查 |
| `onclick` 静默消失 | `SAFE_FOR_XML` 默认开，属性值命中 `/((--!?|])>)|<\/(style\|script\|…)/i` → **整条属性被删**，且早于 `forceKeepAttr`（§5.5）。头号事故是 `onclick="if(a[0]>1)"` 里的 `]>` | **比较运算符两侧留空格**，属性值禁 `]>`/`-->`/`--!>`（硬约束 8）。`SBK.dom.h` 会拦下并告警。**好消息**：HTML 元素上**所有 `on*` 都可用**（实测 `<b onclick onmouseenter>` 双双保留），hover/input/change 放心用 |
| SVG 里的点击事件不触发 | `on*` 在非 SVG 元素上强留，**SVG 内删除**（实测 `<circle onclick>` 被删，§5.5） | 交互必须挂 **HTML 壳**，`<path onclick>` 无效 |
| 自写 `data-*`/`aria-*` 属性不见了 | 作者自写 `data-*` **全删**；`ALLOW_ARIA_ATTR:!1` → `aria-*` 与 `role` **全删**（§5.5）。平台自己的 `data-chat` 由 Vue 创建、从未进净化器，所以看着能用 | 用 class/id 传状态（硬约束 9）。**无障碍在此平台受限，属平台限制而非基座缺陷** |
| 正文里的 HTML 变成纯文本 | **代码围栏与行内代码受保护**：``` ```…``` ``` 与 `` `…` `` 先抽成占位符再还原 → **反引号里的 HTML 原样留存为文本**（§5.4） | 基座产出的正文不要用反引号包 HTML（硬约束 16） |

**措辞澄清**（关于上表第 3 行）：`document` 并非完全不可用——实测 mount 回调内 `document.querySelector('[data-chat="root"]')` 等**平台级节点可达**，受限的只有**气泡内元素**。所以 `mountHost` 内部用 `document` 是对的，`inBubble` 用 `root` 也是对的。

### 其它零散约束
- **零外部依赖**：CSP 封死外部样式表、外部字体、`fetch`/XHR、作者自开 `iframe`/`form`/`object`。只能用系统字体栈（事实卡 §2 / 硬约束 3）。
- **`document.currentScript` 恒为 `null`**（走 eval，无 script 节点）→ 脚本定位靠约定 id/class（硬约束 7）。
- **`type="module"` 被接受但按经典脚本执行** → `import` 必报错。全部写 IIFE。
- **用户消息不跑规则**、**流式阶段跳过整条正则管线**。但 HUD 走的是 JS 事件，用户自己打一句 `[状态]血量: 999/100[/状态]` 会被照单全收 → 必须按 `payload.role === 'ai'` 过滤。
- **载荷形状恰 4 键** `{content, id, role, serverId}`，正文字段名**就是 `content`**（不用猜别名）。`serverId === null` 表示服务端还不认得这条 → **不可 `message.edit`**，必须判空（事实卡 §4.4c）。
- **4 空格缩进不会变代码块**（平台在 markdown 前删掉行首 4+ 空格）——与手册相反。
- `SAVE_MAX_KEYS=10` **不存在于沙盒**，别写死 10，但也别滥用。`save` key ≤64 且禁 `:`。
- `window.__rpc` 能绕过全部限频，属未公开内部通道，**基座不使用**。

## 十、与既有资产的关系

### 不可用于沙盒

| 资产 | 为什么不能用 |
|---|---|
| `../../assets/radar-examples/`（雷达法 `statusbar-radar.md`） | 点火载体是 `img onerror`，沙盒**官方明令禁止**；整套对抗哨兵/防染色补丁针对的是当前 MMD 的 light DOM 环境，沙盒里无对应问题 |
| `../../assets/shadowcast-examples/`（影渲法 `statusbar-shadowcast.md`） | 同样是 `img onerror` 点火；且 **Shadow DOM 在沙盒是纯负债**（跨源 iframe 已是隔离边界，见第一节）。成品还是 MMD 专用 4 字段 json，与沙盒 6 键格式不兼容 |
| `theme-runtime.md` | 依赖当前 MMD 的运行时注入与选择器契约，沙盒的令牌体系（14 个 `--chat-*` + `[data-theme]` 特异度算术）完全不同 |

硬导的结果通常是**规则装上了但一条都不点火，页面上看不出异常**——所以别试。

### 可以复用

**模型侧协议文档可以直接搬**：`../../assets/shadowcast-examples/状态栏-模型侧协议.md`、`RPG协议.md`、`宅邸协议.md`。它们**只约定模型输出什么数据块，与渲染载体无关**。把标记形态换成方括号（第五节），字段表就能直接喂给 SBK 的 schema。

同理可参考的是**设计思路**而非代码：影渲法的双轨代谢（固态字段每轮必出、情境字段用完即焚，防高刺激信息污染上下文）、全量快照协议、schema 驱动字段设计，这些在沙盒一样成立。

## 相关文档

- `../platforms/mmd-sandbox.md` —— 沙盒平台技术规范（1231 行，含全部实测修正）。**平台事实以它为准**
- `../../assets/sandbox-kit/README.md` —— 资产目录、生成器用法、**已知缺陷**
- `../../assets/sandbox-kit/sbk/协议说明.md` —— 协议格式、schema、控件类型、模型侧输出约定
- `statusbar-shadowcast.md` / `statusbar-radar.md` —— 当前 MMD 的两套方法（**不可用于沙盒**，模型侧协议可复用）
