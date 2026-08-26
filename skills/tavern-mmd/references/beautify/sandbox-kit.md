# 沙盒基座 SBK —— MMD沙盒模式的状态栏与美化方法论

> MMD沙盒模式（`/mmdsandbox`）专用的状态栏 / 美化方法论。代号 SBK（SandBox Kit）。
> **不止状态栏**：同一套地基做气泡内状态面板、功能栏入口与精简条、悬浮球、侧边抽屉、舞台面板、主题设置。
> 现成资产与生成器在 `../../assets/sandbox-kit/`，改配置即可复用；协议与 schema 完整参考在 `../../assets/sandbox-kit/sbk/协议说明.md`。

> 🚨 **平台归属：本方法论只针对 MMD沙盒模式（`/mmdsandbox`）。** 它全程依赖 `sdk.*` 与 `[data-chat]` / `[data-slot]` DOM 契约，这两样**只在沙盒新聊天页存在** → 不能用于当前 MMD（`/mmd`）与本地酒馆（`/st`）。反向亦然：雷达法与影渲法**不能用于沙盒**，理由见末节。

> ⚠️ **验证状态**：本文档陈述的**平台事实**（事件时序、CSS 令牌、净化行为、层级）来自**三轮真机探针 + 沙盒应用逆向源码**，且**已实机实测**，可信度高。
> **基座代码 2.0 的历史实机截图已通过**（2026-08-26，卡 64257 预览）：单面板、三分组卡、语义色和宿主唯一。3.0 修复与模块拆分的当前自动化证据记录在 `sandbox-quality-review/工作/验证记录.md`；测试数量以实际运行报告为准，不在本文固定写死。
> **当前本地 GUI 已覆盖**单宿主/单状态面板、preset 切换、tooltip 原生按钮、多轮/switch 与 chat/thin profile。拖动、真实舞台几何、系统主题/触控/软键盘及真实多轮 AI 仍属 `probe-needed` 或最终人工验收范围。
> 🚨 **要在预览里验证，必须点底部「保存编辑」——预览只读卡片正式数据，不读草稿。** 正则面板的「保存配置」只进内存草稿、底部「保存草稿」只写服务端草稿，两者预览都看不到。这一条踩错会让你误以为基座坏了（实机验收时正是它造成四轮误判）。操作纪律见 `../../assets/sandbox-kit/README.md` 的「怎么在实机验证自己的卡」节。

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

### 2.1 功能栏是静态的 → 功能栏上的动态内容只能靠 JS 改 DOM

平台渲染功能栏的 `h_()` **只在装载时调用一次**，主包里没有任何重渲染路径；更关键的是**它的正则输入是卡片 `statusbar` 字段自身，而不是消息内容**（事实卡 §5.6 / 硬约束 14）。

所以「功能栏上的东西跟着对话更新」这件事，**靠正则永远做不到**。做卡人最常见的头号困惑——「我的状态栏第一轮对了，后面再也不动」——根因就在这里。

→ 功能栏上的一切必须是 **JS 在事件回调里改 DOM**。功能栏字段只负责放一个**宿主容器的占位标记**，之后全程由 JS 接管（`chrome` 的入口按钮与 `pinned` 精简条都是这样挂上去的）。而**跟着对话变的状态数据面板压根不放功能栏**——它在气泡内（`status`），随消息滚动，理由见第三节。

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

## 三、角色分工：三个 `modes` 各司其职

上面 2.1 决定了功能栏上的任何东西都必须靠 JS 更新。但**更根本的问题是「什么该放哪」**——1.0 在这里错了，代价是实机截图里出现**两个一模一样的状态面板**。

沙盒是 MMD 的**升级**而不是另一个平台，角色卡底层结构没变，所以沿用 MMD 惯例：

| 位置 | 放什么 | 平台依据 |
|---|---|---|
| **功能栏**（`statusbar` 字段 → 槽位） | **chrome**：主题/设置入口、侧边栏入口、常驻小徽标 | 顶层不滚动（root 的 flex item）；字段仅 200 字符只能放标记；静态渲染 |
| **消息气泡内**（开场白与各条消息末尾） | **状态数据面板**（体力/好感/背包/选项…） | 随消息滚动 = 天然的历史快照；正则管线在此工作 |

于是 2.0 的 `modes` 是**三件职责不同的东西**，而不是「同一份 schema 的几个渲染器」：

| | **`status`** | **`chrome`** | **`pinned`** |
|---|---|---|---|
| 是什么 | **唯一的状态数据渲染器** | 功能栏入口按钮组 | 功能栏**精简条** |
| 载体 | 每条 AI 气泡内部 | `[data-slot="statusbar"]` 内的宿主 | 功能栏，chrome 的兄弟节点 |
| 渲染业务数据 | ✅ 全套（分组/进度条/chip/tooltip） | ❌ **完全不渲染** | 单行、1–3 项、纯短文本 |
| 更新方式 | 每条消息 mount/done 时就地升级 | 静态，装一次 | JS 订阅 `state`/`done` 重绘 |
| 随滚动 | 跟着气泡滚走 = **每轮留痕，可回溯** | **不消失** | **不消失** |
| 默认 | **true** | **true** | **false** |

**1.0 错在哪**（三层，性质各不相同）：

| 层次 | 错误 | 性质 |
|---|---|---|
| **角色分工** | 把状态数据面板放进功能栏槽位 | **违反 MMD 惯例**。功能栏历来放全局美化/侧边栏等 chrome，状态栏历来在气泡内 |
| **默认配置** | 示例 config 同时开 `hud` 与 `snapshot`，两者渲染同一份 schema | 必然重复。双模不是"都开着"，而是"各司其职" |
| **视觉深度** | 控件全平铺，无分组、无语义色、无层次 | 截图里五条 bar 全是同一个金色，体力/灵力/银钱视觉上无区别 |

> 🚨 **根因是方法错误，不是代码错误**：1.0 排查时全程只查 DOM（数节点、量 bar 百分比），**一次没截图**。DOM 计数永远反映不出「两个面板重复」「五条 bar 同色」这类问题。
> **纪律：视觉产出必须截图验收，代码检查与截图并重。**

**怎么选**：绝大多数卡**只需要默认值**（`status` + `chrome`）。想要「抬头就能看到现在多少血」才开 `pinned`——它是对沙盒新能力的利用（`<script>` 一等公民 + 功能栏 JS 挂载可持久，实机验证过 JS 插入的节点整页重载后仍在），但**默认关且形态强制区分**：单行、只显示 `pinnedFields` 指定的 1–3 项、无分组无标签行、不画进度条、自己的 `.sbk-pin*` 命名空间。这样开了也不会与气泡面板重复，因为**内容与形态都不同**。

上限 3 项是**形态约束**不是性能考虑：项数一多就又变成「同一份数据渲染两遍」。

### 🚨 `status` 面板的根元素必须带 `.sbk-snap`

平台给 `[data-chat="message-body"]` 写了两个属性，会把气泡内的自定义 UI 毁掉（事实卡 §7.3 / 硬约束 11、裁决 4）：

- **`white-space: pre-line`** —— 你 HTML 里的换行与缩进会被当**真实换行**渲染出来，排版全烂（这就是雷达法时代著名的「markdown 空白条」在沙盒的等价物）；
- **`opacity: .9`** —— 建立**层叠上下文**，把浮层囚禁在气泡内，且整体发灰。

`base.css` 靠 `.sbk-snap` 这个类名定点重置这两项：

```css
[data-chat="message-body"]:has(.sbk-snap) { opacity: 1; }
[data-chat="message-body"] .sbk-snap,
[data-chat="message-body"] .sbk-snap * { white-space: normal; }
```

用 `:has()` 把作用域收窄到**确实含基座内容的气泡**，不粗暴影响平台正文渲染。→ 面板根元素**少了这个类，重置就不生效**，症状是排版莫名散开且发灰。

`status` 还有个设计取巧处：正则**不负责计算**。它只把 `[状态]…[/状态]` 换成 `<div class="sbk-snap sbk-snap--raw">原文</div>`（纯文本，天然无净化风险），真正的结构化渲染由 `SBK.ui.snapshot.hydrate()` 在 mount 回调内接管。好处是百分比、进度条宽度这类计算全在 JS 里做，正则只搬字符串——正则算不了数，硬凑会写出极长的替换文本，反而撞上输出预算。

外壳类名要两个都带：`.sbk-snap` 管重置，`.sbk-snap--raw` 是 `hydrate()` 的选择器。生成器为此做双向一致性校验，并优先从拆分后的 `hud-render.js` 读取升级类名（兼容旧单文件 `hud.js`），不复制第二份真值。

### 3.1 版面层：`section` 分组（1.0 最大的缺口）

1.0 只有一个容器，20 个字段拉平成一张长表，读者拿不到「哪几项是一组」。2.0 补 `section`：

```js
fields: [
  { type: 'section', label: '状态' },
  { key: '体力', type: 'bar' }, { key: '境界', type: 'level' },
  { type: 'section', label: '行囊' },
  { key: '装备', type: 'kvlist' }
]
```

`section` 是**版面声明不是数据字段**：没有 `key`，state 里没有对应值，也不在控件表里，由分组游标单独处理。遇到它就收口上一组、开一张新分组卡，后续字段累进当前组。**组内一个字段都没有就不产出这张卡**——连续两个 `section`、或整组字段本轮模型全没输出，都不会留下空卡片。

视觉上是三层明度递进（面板 → 分组卡 → 内容区）各带细边框，组标题用主题色小字。🚨 明度差不能靠「外层用 `--chat-bg` 内层用 `--chat-surface`」造——实测深色下页面背景与两个气泡背景**同色**（`#17181a`），拉不开层次。解法是第二层在 surface 上叠一层中性提亮（`linear-gradient` 叠加而非 `background-color` 替换），第三层用平台自带的 `--chat-more-item-bg`（实测比 surface 更亮）。三档明度全部由令牌推导，作者换 surface 时自动跟随。

### 3.2 值的内部结构：四个结构类型（第二大缺口）

1.0 的解析器对 `|` 与 `:` 零语义，凡带内部结构的值一律退化成 `text`。2.0 补四个（都是**纯展示、零状态**）：

| 类型 | 协议形态 | 渲染 |
|---|---|---|
| `path` | `内城-东市-药铺` | 面包屑 chips，段间 `›` |
| `level` | `炼气三层\|120/300` | 左等级名 + 右经验 + XP 条（只有经验段解析成功才画条） |
| `stats` | `攻:12 防:8 敏:15` | `键:值` chip 紧凑网格，chip 左 3px 主题色竖条 |
| `kvlist` | `头:斗笠\|身:麻衣` | 竖排「槽位：名」，信息密度最高 |

四个分隔符各有分工：**主分割 `|`、列表项 `,`（`stats` 也认空格）、标签值 `:`、次级说明第三段**。`stats`/`kvlist` 的第三段是「成因/说明」，自动折进 tooltip。

两条设计纪律：

- **结构不完整就返回 `null`，降级到 `text`。** 宁可显示成一行文本，也不能因为模型写歪一个字段就渲染出畸形控件。半解析的网格比纯文本更难读，还会让做卡人以为协议支持某种写法（实际只是碰巧过了一半）。
- **推断与强制走同一批解析器。** schema 写 `type:'stats'` 时的适配器与自动推断共用一份代码——否则「自动认出的 `stats`」和「强制的 `stats`」会有两套行为，是最难查的一类不一致。

判定顺序有讲究（`bar` 之后、`entities`/`tags` 之前，`level` 严于 `kvlist`），完整优先级链与「为什么 `2026-08-26` 不会被误判成 `path`」这类边界说明见 `../../assets/sandbox-kit/sbk/协议说明.md` §1.2。

### 3.3 tooltip 与交互出口：两处不能照搬旧资产

- **tooltip**：旧实现用纯 CSS `:hover`，**移动端不成立** → 改为**点击 toggle**。且 `on*` 必须挂 HTML 壳（SVG 内的 `on*` 会被净化器删）。要在两条渲染出口都能点，就得同时给函数 handler（DOM 路径）与内联 `onclick` 字符串（快照路径）。
- **可点选项**：旧实现直接操作 `.uni-textarea-textarea` DOM → 沙盒改用 `sdk.input.set()`。

视觉细节：进度条同色 `box-shadow` 发光、chip 左竖条、角标 `float:right` 不占行、按钮 hover/active 两态。**尺寸一律 `calc(N * var(--rpx))`**——旧资产用 px，沙盒必须换算。

### 3.4 明确不移植

Shadow DOM 与降级链、`img onerror` 点火、禁裸双引号铁律、`String.fromCharCode` 拼方括号、ES5 写法、`localStorage` 直存偏好（改 `sdk.save`）、`body`/`html` 全局选择器、雷达法对抗哨兵补丁。**这些是旧平台约束的产物，在沙盒是纯负债。**

## 四、三层架构

- **内核基础** `core.js`：SDK 快照、claim/事件桥、状态仓、调度与 DOM/宿主工具；`core-store.js`：持久化与合并队列；`core-boot.js`：modes/schema/pinned 与唯一编排入口
- **主题层** `theme.js`：token、作者基线/preset/overrides、偏好语义与落地；`theme-panel.js`：设置表单和抽屉
- **组件层** `protocol.js` 协议解析；`hud.js` 控件/归一/注册表 + `hud-render.js` 快照/hydrate；`ui.js` CSS/队列/定位工具 + `ui-panel.js` panel/chrome；`ui-stage.js` stage

所有源模块都是完整经典脚本 IIFE，独立 claim，固定顺序装载；生成器只按连续文件边界装箱，不会从函数或字符串中间切开。

`SBK.boot(opts)` 是**唯一**把各层接起来的地方（生成器产出的 boot 规则只调它）：归一化 `modes`/`pinnedFields`/`schema` → 应用主题 → 配协议块名 → 按 `modes` 启动 `status`/`chrome`/`pinned`。它是**纯集成层**，不重复实现任何一层的功能；**缺层一律告警并跳过该功能，绝不抛异常炸整卡**（只装了 core 没装 ui 时，状态面板会被跳过并在返回的句柄里标出来）。返回句柄的 `modes` 是**实际生效值**而非请求值，方便实机自查。boot 自带哨兵：预览反复重跑时第二次起直接返回首次的句柄，不再挂任何订阅。

分层的意义不是好看，是**把平台坑收敛到一处**。做卡人调 `SBK.dom.h()` 建元素，就自动拿到了「拒绝 `data-*`/`aria-*`」「拦截 `]>` 属性值」「SVG 内 `on*` 告警」三重防御，不需要记住净化器的行为。

### 4.1 `window.SBK` API 速查

签名与 `../../assets/sandbox-kit/sbk/` 下真实代码一致。

**内核**

```js
SBK.version                     // '1'
SBK.claim(name)                 // -> boolean。已占用返回 false，调用方必须据此短路
SBK.boot(opts)                  // 唯一编排入口 -> {schema, modes, pinnedFields, skipped,
                                //                 pinned, el, render, feed, dispose}
SBK.schema(sc) / SBK.modes(m) / SBK.pins(v)   // 三个归一化器，直接调渲染器时可复用
SBK.pinned(keys, hostId?)       // 功能栏精简条 -> {el, render, feed, mount, keys}
SBK.on(evt, fn)                 // fn(payload, bubbleRoot)
SBK.off(evt, fn)                // -> boolean。内核自有分发，不依赖 sdk
SBK.emit(evt, payload, root)
SBK.log(...) / SBK.warn(msg, extra)
SBK.sdk                         // 启动时的 sdk 快照，不受后续改写影响
```

⚠️ `boot().dispose()` 只回收**看得见的产物**（主题样式 + 精简条内容）。**订阅回收不了**——`sdk.on` 无 `off`/`once`，各渲染器是用匿名函数订阅内部总线的，没有函数引用可撤。所以 dispose **不释放 boot 哨兵**：再 boot 只会拿回旧句柄，不会二次订阅。

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
SBK.store.save(obj?)            // 业务整文档 + 800ms 队列；缺省用 state.get()，保留未覆盖的 _sbk*
SBK.store.merge(partial)        // 顶层补丁；与 save 同窗合并，不覆盖其它业务字段
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
SBK.theme.apply(tokens, extraCss?)   // {bg:..} 两套同值 / {dark:{},light:{}} 分别 / null 清空
SBK.theme.register(name, tokens)     // 注册风格包（也接受 {名:包,…} 批量）。只登记不生效
SBK.theme.start(presetName?, opts?)  // 读存档 + 合成 + 落地。chrome 与 boot 都走它，重复调无副作用
SBK.theme.mode()                     // -> 'dark'|'light'，从 DOM 读（平台级，只读不可写）
SBK.theme.onChange(fn)               // -> unsubscribe。会立刻用当前值调一次
SBK.theme.vars()                     // -> 14 个平台后缀名
SBK.theme.base()                     // -> 实测深色基线副本，供「微调而非全替」
SBK.theme.current()                  // -> 最近一次 apply 的入参，清空时为 null
SBK.theme.reset()                    // = apply(null)

// 偏好核心语义在 theme.js；表单/抽屉扩展在 theme-panel.js，chrome 由 ui-panel.js 调用
SBK.theme.prefs.presets()            // -> 已注册的风格包名数组
SBK.theme.prefs.preset(name?)        // 读/切风格包
SBK.theme.prefs.enabled(v?)          // 启用美化；false = 撤销全部覆盖，完全跟随平台
SBK.theme.prefs.get(k, m?) / .set(k, v, m?)    // 玩家微调，按 dark/light 分开存
SBK.theme.prefs.reset(m?)            // 只清【当前模式】的 overrides，另一侧不动
SBK.theme.prefs.resetAll()           // 清两套 overrides，保留 preset 与启用状态
SBK.theme.prefs.fields()             // -> 微调字段表（控件清单的唯一真源）
SBK.theme.prefs.resolved(m?)         // -> 合成后的最终令牌
SBK.theme.prefs.form()               // -> 设置面板表单节点（建 DOM 但不挂载）
SBK.theme.prefs.panel() / .toggle() / .open() / .close()
```

**协议与组件**

```js
SBK.parse(text)                 // -> {state, order, cleanedText, skipped} | null
SBK.parse.pattern(cap?)         // -> 推荐匹配式字符串（slash 形态）
SBK.parse.config({block:'状态'})
SBK.parse.value(raw)            // 单值分类器
SBK.parse.struct(type, raw)     // 结构类型强制适配（path/level/stats/kvlist）

SBK.ui.snapshot(state, schema)  // -> HTML 字符串（status 面板，拼给 replaceString）
SBK.ui.snapshot.auto(schema)    // 装一次，自动升级所有气泡（订阅 mount/done）
SBK.ui.snapshot.hydrate(root, schema)          // 手动升级某个气泡根
SBK.ui.chrome(opts)             // 功能栏入口 -> {el, toggle, panel}
SBK.ui.panel(opts)              // -> {el, ball, box, open, close, toggle, opened, setContent, move, destroy}
SBK.ui.stage(opts)              // -> {open, close, toggle, visible, el, box, mode, rebuild, render, destroy}

SBK.ui.hud.type(name, fn)       // 注册自定义控件（仍是公开入口）
SBK.ui.hud.types()              // -> 已注册类型名数组
SBK.ui.hud(...)                 // 🚨 已废弃：告警 + 返回惰性句柄，不挂订阅、不写 DOM
```

🚨 **`SBK.ui.hud` 作为渲染器已废弃。** 1.0 时代它的职责是「把状态数据面板渲染进功能栏槽位」，这正是两个重复状态栏的根源。2.0 里三项职责各有归属：状态面板 → `ui.snapshot.auto()`、功能栏常驻 → `SBK.pinned()`、功能栏入口 → `ui.chrome()`。符号保留只为兼容 `.type()` 注册入口，直接当渲染器调会告警并返回惰性句柄（`el()` 返 `null`、`feed()` 返 `false`），老卡不炸但也不再渲染重复面板。

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

`<状态>` 是中文标签名，**不在白名单里 → 整个标签被删掉**（文字保留、标签消失）。

这个坑很隐蔽，因为**正则管线跑在剥壳之前**，尖括号在链路上是「半死」的：`status` 那条外壳规则的匹配式**看得见** `<状态>` 所以能匹配成功；但任何**从气泡文本读取标记**的路径——`hydrate()` 拿到的节点 `textContent`、你自己写的 `feed(payload.content)`、精简条的 `feed`——那时标记已经被剥掉了，解析必然失败。表现是「气泡里那一块渲染出来了，别处死活不动」。

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

### 语义色令牌必须自备深浅两套

平台的 14 个 `--chat-*` 里**没有语义色对应物**（盘点确认）。所以血量红/灵力蓝/体力绿/经验金这四类得基座自己定义，且**不得硬编码**——写成 `[data-chat="root"][data-theme="dark|light"]` 下的令牌，与换肤同一套机制，保证平台切深浅色时跟随。浅色主题的红要换成在白底上仍读作「危险」的深红，不能照抄深色那支。

消费点只有一个（进度条填充与 chip 竖条读 `var(--sbk-tone, var(--chat-accent))`），赋值靠修饰类：`.sbk-tone--*` 挂在任意祖先染整组、`.sbk-bar--*` 挂在槽上只染一条。**用 CSS 变量继承 + 修饰类而不是 `data-*` 属性**——作者自写 `data-*` 会被净化器全删，属性选择器在气泡内必然失效。没有 tone 就回退 `--chat-accent`，与 1.0 视觉一致。

**当前实现已完成 key → tone 接线。** `bar` 默认按字段 key 推断 `hp/mp/sp/xp`，schema 显式 `tone` 恒优先；`section` 可显式给整组 tone，字段自身声明会覆盖继承。自动推断只是可复现的默认值，不是真理：例如「体力」默认判 `hp`，作耐力时必须显式写 `tone:'sp'`。

### 🚨 设置面板的语义漂移：`light|dark` 是平台级的，作者只能读不能写

**这一条不写清，后人会把旧资产的三态面板整个搬回来。**

旧 runtime 的三态 `day/night/native` 是**玩家在面板里选**的。沙盒不是这样：`light|dark` 由**平台**掌握，用户在平台设置里切，**作者只能读 `data-theme` 与跟随 `theme:change`，写不动**。

→ 设置面板**不放「日间/夜间/原生」三按钮**。前两个按了切不动，放上去就是**坏控件**。取代物：

- **风格包选择**（作者预置多套 preset，玩家挑一套）；
- **启用美化开关**（关 = 撤销全部覆盖、完全跟随平台，对应旧 `native`。沙盒下这是**真** native）；
- **玩家微调**（字号、行距、正文色、强调色、气泡色、气泡透明度）。

配套的两条实现纪律：

- **关掉美化不关设置入口**，否则玩家再也回不来。
- **「全部恢复默认」永不禁用**——它是玩家把自己改坏之后的唯一出路。（「恢复当前主题默认」在停用美化时无意义，那个可以禁。）
- 无障碍属性在此平台**落不了地**（`aria-*` 与 `role` 被净化器全删，属平台限制而非基座缺陷）→ 禁用态用「真 `disabled` 属性 + class 视觉弱化」表达，不双写 `aria-disabled`。
- 原生控件要写 `color-scheme: inherit`：平台没有 `color-scheme` 声明，不写这条深色下滑块与取色器会是白的。

### 主题持久化：preset + overrides 两层合成

```
resolved(mode) = PRESET[风格包名][mode] + overrides[mode]
```

三条纪律，做错的代价都是「玩家永远跟不上作者的更新」或「一个脏值毁掉整卡」：

1. **preset 默认值只存在于源码，绝不写进存档。** 每次都按「当前版本的 preset + 合法 overrides」重新合成 → 作者升级风格包后，新默认能作用到玩家**从未改过**的字段。把 preset 快照进存档会把旧默认永久钉死。
2. **`overrides.dark` 与 `overrides.light` 分开存**，切深浅色不串值；玩家把某项**改回默认时删除该 override**，而不是存一份等于默认的值（否则这个字段又跟不上升级了）。平台切主题时还要回填面板控件，否则面板显示的是另一套主题的值。
3. **白名单校验 + 逐字段降级。** 微调值只走字段表里的 key（`__proto__`/`constructor`/未知键天然进不来），颜色严格 `#RRGGBB`，数值越界一律拒绝并**回落默认而不是夹取**。玩家存档里的脏值只丢那一个字段，**绝不让 bootstrap 失败**。偏好文档带 schema 版本号，日后改字段语义时按版本迁移而不是让旧存档静默错解。

**载体复用 `SBK.store`**（三级降级链 `sdk.save` → `sdk.cache` → 内存），不另写存储。主题运行时把 `_sbkTheme` 留在 state 以跨会话保留，但持久化只调用 `store.merge({_sbkTheme:…})`；它不会把当前 state 冒充完整业务存档。`store.save(obj)` 与 merge 共用 800ms 队列，同一窗口合成一次写入，并保留调用方未显式覆盖的 `_sbk*` 内部键。

读档必须**再兜一层 try/catch**：瘦预览下 `save.get`/`save.keys` **同步抛 `SdkError`**，取不到偏好只能回默认，不能炸整卡。

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

### 7.4 chrome 层：功能栏入口挂得住，不必占用舞台

**已裁定的文档冲突**：`global-css.md` 称「JS 往功能栏 `appendChild` 留不住，平台按 `statusbar` 字段整块重画」，与事实卡 §5.6「`h_()` 只在装载时调一次、无重渲染路径」矛盾。

**裁定：事实卡正确**，`global-css.md` 那句是当前 MMD 的旧行为被误带过来。证据是实机——用 JS 往 statusbar 槽位插了宿主 `<div>`，**整页重载后该节点仍在并正常渲染**。若平台真按字段重画，JS 插入的节点不可能存活。

→ **设置面板可以挂功能栏，不必占用舞台。** 这是 `chrome` 层成立的前提。

职责边界要划清：chrome 只负责「功能栏上有个按钮，点了调它」，**抽屉本体归主题层**（`SBK.theme.prefs.panel/toggle`）。chrome 自己不持有抽屉引用——单一归属，避免两处状态不同步。缺主题层时按钮仍在、点了只告警，不抛异常炸整卡。

两个实现要点：

- **宿主要分开。** chrome 建的是 `<hostId>-chr`，精简条是 `<hostId>-pin`，两者是功能栏里的**兄弟节点**。精简条每次重绘都清空自己的宿主 → 共用一个宿主的话，第一次 state 变化就会把入口按钮全部擦掉。所以两边都只清自己那个子容器，**绝不清整个宿主**。
- **宿主归一。** 实机踩过一次 `#sbk-hud` 出现**两份**：`boot()` 调 `mountHost` 时 statusbar 槽位尚未渲染，走了回落分支在 `[data-slot="left"]` 建了新节点，之后平台才渲染出静态宿主 → 同 id 两份。修法是 `mountHost` 改为**全文档归一**（优先留 statusbar 的直接子节点）+ 内容迁移，并在每轮 mount/done 先归一一次。

**偏好读档 + 合成 + 落地必须在首个入口按钮出现之前做完**，否则玩家上次存的字号/配色要等他打开一次面板才生效。

## 八、工作流

① 复制配置 → ② 修改主题/schema/正文 → ③ 生成器与 validator → ④ 本地 sandbox `chat` + `thin-preview` → ⑤ 桌面/竖屏/横屏 GUI 与截图。只有能力矩阵标为 `probe-needed`，或用户授权最终人工验收时才进真实站；AI 不默认登录账号、不把正式卡/公开卡当日常夹具。真实站操作仍按固定交付形态导入 6 键 JSON，并手工粘贴 persona。

**沙盒不用 PNG 整卡、不用 `chara_card_v2`**——交付物就是一份 6 键 JSON。

生成器替你兜住的事：剥注释、按文件边界自动拆条并保持装载顺序、估算每条规则的输出预算、校验标签白名单与净化合规、`</script>` 在 JSON 序列化层转义。这些都是「不做会静默失效」的类别。

首次实机导入建议 URL 加 `?sdkDebug=1`，`SBK.log` 全部走 `sdk.debug.log`，那是**手机上唯一可见的日志通道**。

### 🚨 要在预览里看到效果，必须「保存编辑」

创卡页三个保存动作写到**三个不同的层**，搞错这一层是「改了没生效」的绝大多数原因：

| 动作 | 写到哪 | 预览能否看到 |
|---|---|---|
| 正则面板里的「保存配置」 | 创卡页**内存草稿** | ❌ 重载即丢 |
| 底部「保存草稿」 | **服务端草稿** | ❌ 看不到 |
| 底部**「保存编辑」** | **服务端卡片正式数据** | ✅ **只有这个能让预览看到** |

**预览渲染不包括草稿。** ⚠️ 「保存编辑」是**对外动作**：卡若为公开会**提交审核并消耗每周公开配额**，自动化前先确认公开设置。

配套三条纪律：

- 关正则面板后**等 `.u-transition` 计数归零**（实测约 1 秒）再点底部按钮。不等就点会命中遮罩、**静默失败**。
- **改完必须重载后复核字段真值**（看字符计数器）。不能只看点击有没有报错——超 20000 是静默拒绝保存、遮罩挡住也是静默失败，两者都不报错。
- **视觉产出必须截图验收**，代码检查与截图并重。

> 这一条的代价有实例：四个新控件类型一度实机全为 0，四轮排查（怀疑实机代码陈旧 / 平台文本管线剥掉了那几行 / 生成器过滤了新类型）**全部走错方向**，真相是那几轮改动都停在草稿层、预览从未看见，代码自始至终是对的。
> 更值得记的教训：此前还曾把「预览读草稿」当成一条"更正"郑重写进文档，依据是「点了保存草稿后开场白变了」——但那次变化来自**用户侧的保存**，是把时间相关性当成了因果，**用一个错误结论去更正一个正确结论**。
> → **平台语义的结论必须有隔离实验**（有他人同时操作时「我做了 A 然后看到 B」不成立）；**改完必须确认自己的写入到达了被观测的那一层**（草稿层 ≠ 卡片层）。

## 九、避坑清单

事实卡 21 条硬约束里与基座使用相关的，按「症状 → 原因 → 做法」列。

| 症状 | 原因 | 做法 |
|---|---|---|
| 状态栏第一轮对，之后再也不动 | 指望功能栏正则刷新。`h_()` 只在装载时跑一次，正则输入是 `statusbar` 字段自身（§5.6） | 功能栏只放宿主容器标记，之后 JS 在 `message:done` 里改 DOM（硬约束 14）。跟着对话变的状态数据用 `status`（气泡内） |
| 页面上出现**两个一模一样的状态面板** | 1.0 的 `{hud, snapshot}` 是两个渲染器渲染同一份 schema，两个都开必然重复；且 `hud` 把状态数据放进了功能栏，违反 MMD 惯例 | 用 2.0 的 `modes`：`status`（气泡内，唯一数据渲染器）/ `chrome`（功能栏入口，不含数据）/ `pinned`（精简条，默认关）。**别再调 `SBK.ui.hud` 当渲染器** |
| 改了半天实机毫无变化 | 改动停在**草稿层**。预览只读卡片正式数据，**不读草稿** | 点底部**「保存编辑」**，重载后复核字段计数器。见第八节 |
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
- **用户消息不跑规则**、**流式阶段跳过整条正则管线**。`status` 因此天然安全（用户打的 `[状态]…[/状态]` 不会变成外壳，也就不会被升级）；但**任何直接从事件载荷读正文的 JS 路径**（自己写的 `feed(payload.content)`、精简条喂数据）会照单全收 → 必须按 `payload.role === 'ai'` 过滤，否则用户在输入框打一句 `[状态]体力: 999/100[/状态]` 就能改你的数据。
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
- `../../assets/sandbox-kit/README.md` —— 资产目录、生成器用法、`modes` 语义、**已知缺陷与限制**、**怎么在实机验证自己的卡**
- `../../assets/sandbox-kit/sbk/协议说明.md` —— 协议格式、schema、控件类型、模型侧输出约定
- `statusbar-shadowcast.md` / `statusbar-radar.md` —— 当前 MMD 的两套方法（**不可用于沙盒**，模型侧协议可复用）
