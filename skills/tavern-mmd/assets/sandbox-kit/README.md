# 沙盒基座 SBK（SandBox Kit）现成资产

MMD 沙盒模式的状态栏 / 美化基座：三层运行时（内核 / 主题 / 组件）+ 声明式生成器。做卡人只写配置与协议，不写平台胶水。方法论见 `../../references/beautify/sandbox-kit.md`。

> **平台归属：本目录资产【只能】用于 MMD沙盒模式（`/mmdsandbox`）。**
>
> 🚨 **不能用于当前 MMD（`/mmd`）与本地酒馆（`/st`）。** 两条硬原因：① 基座全程依赖 `sdk.*`（`sdk.on` / `sdk.save` / `sdk.stage` / `sdk.cache`），这个 SDK 只在沙盒新聊天页存在；② 布局与主题全部挂在 `[data-chat="root"]` / `[data-slot="statusbar"]` 这套沙盒专属 DOM 契约上（事实卡 §7.3）。硬搬到 `/mmd` 的结果是脚本顶层就取不到 `sdk` 而整体短路，页面上看不出异常。另外沙盒要的是**顶层恰好 6 键**（含 `chatVersion: 1`）的导入正则 JSON，与 MMD 的 4 字段 `.mmd.json` 格式本身也不兼容。
>
> 🚨 **反向同样不成立**：`../radar-examples/`（雷达法）与 `../shadowcast-examples/`（影渲法）**不能导入沙盒**——它们的点火载体是 `img onerror`，沙盒官方明令禁止；且影渲法的 Shadow DOM 隔离在沙盒是**纯负债**（沙盒本身就是跨源 iframe，隔离边界已经免费拿到了）。详见方法论文档「与既有资产的关系」节。

> ✅ **验证状态（务必先读）**：2.0 已**实机截图验收通过**（2026-08-26，卡 64257 预览）：气泡内**只剩一个**状态面板、功能栏是 `设置` 按钮（chrome）、三张分组卡（状态/行囊/见闻）、九种数据类型全渲染、进度条不再是五条同色、`pinned` 默认关未出现、`[状态]` 裸标记不外泄、`#sbk-hud` 宿主计数 1。逐项结果见工作目录的 `资料/基座2.0设计.md` 第四bis节。
> 代码侧另有零依赖 runtime、生成器和本地 sandbox 仿真回归；全部 `.js` 需过 `node --check`，示例产物还须过 `json.tool` 与 `validate.py --platform mmdsandbox`。当前实测数字统一记录在本轮 `sandbox-quality-review/工作/验证记录.md`，不在 README 多处复制。
> **仍未验证的**：浮层拖动与菜单翻转、舞台开关、平台深浅色切换的跟随、多轮真实对话里的增量更新。这几项只有离线 harness 与代码审查背书。
> 注意区分两种可信度：**平台事实**（事实卡 21 条硬约束、CSS 令牌、事件时序）来自**三轮真机探针 + 逆向源码**；**基座代码**的状态面板与版面层已实机截图确认，上面列出的四项仍待验。首次导入建议开 `?sdkDebug=1` 看 `[SBK]` 日志。
>
> 🚨 **要在预览里验证自己的卡，必须点底部「保存编辑」。预览只读卡片正式数据，不读草稿**（正则面板的「保存配置」只进内存草稿，底部「保存草稿」只写服务端草稿，两者预览都看不到）。这一条踩错会让你以为基座坏了——实机验收时正是它导致四轮误判，详见工作目录的 `资料/沙盒实测报告.md` §三ter。

## 文件清单

| 文件 | 说明 |
|---|---|
| `build_sbk.py` | **生成器**。声明式 config → 可导入的 6 键正则 JSON。含剥注释、体积预算估算、自动拆条、净化合规校验 |
| `sbk.config.example.json` | **配置示例**（可直接跑）。JSON 不支持注释，故用 `_xxx` 键写说明，生成器丢弃所有 `_` 开头顶层键 |
| `test_build_sbk.py` | 生成器、模块边界、装载顺序与体积门禁测试 |
| `sbk/base.css` | 基础样式与骨架原语；颜色走 `var(--chat-*)`，含平台污染重置与响应式规则 |
| `sbk/core.js` | **内核基础**：SDK 快照、claim、事件桥、状态仓、调度与 DOM/宿主工具；创建 `window.SBK` |
| `sbk/core-store.js` | **持久化**：`save/load/merge/clear/key`、800ms 合并队列与 save→cache→内存降级 |
| `sbk/core-boot.js` | **编排**：schema/modes/pinned 归一、精简条与 `SBK.boot` |
| `sbk/theme.js` | **主题引擎**：14 个平台 token、作者基线/preset/overrides 合成、偏好语义与持久化 |
| `sbk/theme-panel.js` | **主题设置界面**：表单、设置抽屉与 `prefs.form/panel/toggle/open/close` |
| `sbk/protocol.js` | **协议解析器**：`[状态]…[/状态]` 块 → 状态对象 |
| `sbk/hud.js` | **HUD 基础**：vnode、十二种控件、归一化、控件注册表 `SBK.ui.hud` |
| `sbk/hud-render.js` | **HUD 渲染**：section 分组、`snapshot()`、`hydrate()`、`snapshot.auto()` |
| `sbk/ui.js` | **组件工具层**：CSS、DOM 就绪队列、定位/事件/标题栏工具，导出 `SBK._uiKit` |
| `sbk/ui-panel.js` | **组件面板层**：浮层/抽屉/悬浮球 `panel` 与设置入口 `chrome`（默认路由到导轨） |
| `sbk/ui-nav.js` | **可选导航栏**：`SBK.ui.nav`，抽屉与气泡共用的分页容器。**单 pane 不渲染导航栏** |
| `sbk/ui-icon.js` | **图标集**：`SBK.ui.icon(name)` / `icons()`，8 个内联 SVG（`gear/wrench/tools/sliders/map/book/spark/dots`） |
| `sbk/ui-fan.js` | **扇形第二层**：`SBK.ui.fan.place()`，同一页签下 ≥2 类功能时的快速分流坐标与样式 |
| `sbk/ui-dock.js` | **侧边图标导轨**：`SBK.ui.dock`，页签 + 两种呈现面（半页抽屉 / 锚定气泡）+ 可选导航栏 |
| `sbk/ui-bubble.js` | **锚定气泡面**：`SBK.ui.bubble`，贴着导轨页签弹出的轻量气泡，支持专属导航栏 |
| `sbk/ui-inject.js` | **自动注入**（扩展）：`SBK.ui.inject`，滑块开关 + 输入框，发送时把内容附加到用户输入末尾 |
| `sbk/ui-codex.js` | **人物图鉴**（扩展）：`SBK.ui.codex`，单列/双列/导航分组/大图左右滑动四种版式 |
| `sbk/ui-map.js` | **地图**（扩展）：`SBK.ui.map`，图片地图（缩放 + 可点标识 + 气泡）与渲染地图 |
| `sbk/ui-stage.js` | **舞台层**：`SBK.ui.stage`，依赖 `ui.js` 的工具箱 |
| `sbk/协议说明.md` | 协议格式、schema、控件类型、模型侧输出约定的完整文档 |

装载顺序固定（19 个模块）：`core.js` → `core-store.js` → `core-boot.js` → `theme.js` → `theme-panel.js` → `protocol.js` → `hud.js` → `hud-render.js` → `ui.js` → `ui-panel.js` → `ui-nav.js` → `ui-icon.js` → `ui-fan.js` → `ui-dock.js` → `ui-bubble.js` → `ui-inject.js` → `ui-codex.js` → `ui-map.js` → `ui-stage.js`。每个文件都是完整经典脚本 IIFE，拥有独立 claim；顺序错了会由依赖检查告警并短路。

侧边栏一族的依赖方向（都是「晚到只会静默退化，不报错」，故顺序不能靠记忆）：

- `ui-nav` / `ui-icon` / `ui-fan` **必须早于** `ui-dock`——dock 消费它们。缺 `ui-icon` 页签退化成一个字符；缺 `ui-nav` 呈现面只铺第一个 pane；缺 `ui-fan` 扇形退化成等距竖列。
- `ui-dock` **必须晚于** `ui-panel`——`chrome()` 反查 `SBK.ui.dock` 决定入口形态。晚到会静默回落成旧的功能栏按钮排，也就是「设置按钮镶嵌在页面里」那个观感问题。
- `ui-inject` / `ui-codex` / `ui-map` 只依赖 core + ui kit(+nav/icon)，**互不依赖，可单独裁剪**（不做地图就别打包 `ui-map.js`，省 replaceString 预算）。

## `modes`：三个职责不同的东西（2.0 语义）

`modes` 不是「同一份 schema 的几个渲染器」，而是**三件职责不同的东西**，两两不重复：

| 键 | 是什么 | 位置 | 默认 |
|---|---|---|---|
| `status` | **唯一的状态数据渲染器**。气泡内状态面板，随消息滚动＝天然历史快照 | 每条 AI 气泡内 | **true** |
| `chrome` | 功能栏入口按钮组（`设置` 等）。**不渲染任何业务数据** | `[data-slot="statusbar"]` | **true** |
| `pinned` | 可选的功能栏**精简条**：单行、无分组、无标签行、不画进度条 | 功能栏，chrome 的兄弟节点 | **false** |

- 开 `pinned` 就**必须**配 `pinnedFields`，取 `schema.fields` 里的 key，**限 1–3 项**（`core.js` 的 `PIN_MAX`，超出截断；生成器直接报错）。只配 `pinnedFields` 不开 `pinned` 会告警并忽略。
- 上限 3 项是**形态约束**不是性能考虑：精简条必须与气泡面板明显不同，项数一多就又变成「同一份数据渲染两遍」。值一律压成短文本（单项超 24 字符截断），`entities`/`tags` 这类结构不进精简条。
- **为什么这么分**：1.0 的 `{hud, snapshot}` 是两个渲染器渲染同一份 schema，示例配置两个都开 → 实机截图里同时出现**两个一模一样的状态面板**；而且 `hud` 把状态数据放进了功能栏，**违反 MMD 惯例**（功能栏历来放全局美化/侧边栏这类 chrome，状态栏历来在气泡内）。这是 1.0 的头号缺陷，性质是角色分工错，不是代码 bug。
- **旧键仍被接受**（`core.js` 的 `normModes` 与生成器的 `_alias_modes` 各一份，都会告警）：`snapshot` → `status`（同义）；`hud: true` → `pinned`，但 ⚠ **不是等价替换**——旧 `hud` 是完整面板，新 `pinned` 是单行精简条。要完整面板请开 `status`。`hud: false` 直接忽略。

### `chrome` 层：设置入口（默认＝侧边图标导轨）

```js
SBK.ui.chrome({ hostId: 'sbk-hud', icon: 'wrench', label: '设置', side: 'right' });
// -> { el(), toggle(), panel(), dock() }
```

`boot()` 在 `modes.chrome` 为真时自己调它，把 config 的 `chrome` 块（`form/side/icon/label/dockLabel/hoverOpen/settings`）按白名单透传进来，一般不用手写。**模块级单例**：重复调用直接返回已有句柄并告警。它也容错 `chrome(hostEl, opts)` 形态（首参是元素就当宿主，此时强制走 bar）。

**两种形态，默认 dock**：

| `form` | 形态 | 何时用 |
|---|---|---|
| `dock`（默认） | 贴视口边缘的一枚**图标**页签，点开是半页抽屉 | 默认全用这个 |
| `bar` | 旧的功能栏内按钮排（大按钮＋「设置」文字） | 只在作者显式要求、或 `ui-dock.js` 被裁掉时 |

**为什么默认换成 dock**：bar 形态走功能栏行内流，与平台自己的 chrome 挤在一条上，且功能栏实测 `flex-shrink:1` 会被消息区抢高度压扁——观感就是「设置按钮镶嵌在页面里」。dock 把它挪到视口边缘、只留一枚半透明图标把手。

- **设置页签全局唯一**（`role:'settings'`，由 dock 的 dedupe 保证）：玩家找设置时不该在两枚差不多的图标里猜。作者的扩展页签（图鉴/地图）可以多枚。
- **单功能不做第二层**：设置只有美化一件事时，抽屉里只有一个 pane，`ui-nav` 见 ≤1 pane 就不渲染导航栏，点开即是表单。传 `panes` 才会并列出导航栏。
- 传旧的 `entries` 仍然可用：它们各自成为导轨上一枚**独立 action 页签**，而不是塞进设置抽屉——`entries` 是「点一下就执行」的扩展动作，与「基础设置」不同类，混进去会让设置变成杂物抽屉。
- 抽屉里的设置表单归主题层（`SBK.theme.prefs.pane()`，可嵌进任意 pane 的节点；老资产的 `prefs.form()` 也兼容）。chrome 不复制表单逻辑——单一归属。
- 缺 `ui-dock.js` 时自动回落 bar，既有卡不白屏；显式写 `form:'dock'` 但模块缺失会额外告警一次。
- bar 形态建的是宿主里的子容器 `<hostId>-chr`，**只清自己这一个子节点**。精简条宿主是 `<hostId>-pin`，两者是兄弟：清整个宿主会把对方擦掉。`hostId` 是派生基名，限 ASCII 字母开头、其后字母数字 `_` `-`、总长 ≤60；追加 4 字符后缀后最终 DOM id 仍 ≤64。
- 缺主题层时入口仍在，点了只告警，不抛异常炸整卡。

### `theme` 层：preset + overrides 两层合成

```js
SBK.theme.register('古卷', { dark: {…}, light: {…} });   // 只登记不生效
SBK.theme.start(presetName, opts);                       // 读存档 + 合成 + 落地，chrome/boot 都走它

SBK.theme.prefs.presets()          // -> 已注册的风格包名数组
SBK.theme.prefs.preset(name?)      // 读/切风格包
SBK.theme.prefs.enabled(v?)        // 启用美化；false = 撤销全部覆盖，完全跟随平台（对应旧 native）
SBK.theme.prefs.get(k, m?) / .set(k, v, m?)   // 玩家微调，按 dark/light 分开存
SBK.theme.prefs.reset()            // 只清【当前模式】的 overrides，另一侧不动
SBK.theme.prefs.resetAll()         // 清两套 overrides，但保留 preset 与启用状态
SBK.theme.prefs.fields()           // -> 微调字段表（控件清单的唯一真源）
SBK.theme.prefs.form() / .panel() / .toggle() / .open() / .close()
SBK.theme.reset()                  // = apply(null)，撤销全部主题覆盖
```

三条纪律（做错代价很大）：

1. **合成式恒为 `PRESET[name][mode] + overrides[mode]`，preset 默认值只存在于源码、绝不写进存档。** 每次都按「当前版本的 preset + 合法 overrides」重新合成 → 作者升级 preset 后，新默认能作用到玩家**从未改过**的字段。把 preset 快照进存档会把旧默认永久钉死。
2. **`overrides.dark` 与 `overrides.light` 分开存**，切深浅色不串值；写回默认值时**删除**该 override 而不是存一份等于默认的值。
3. **白名单 + 逐字段降级**：微调值只走字段表里的 key（`__proto__` / 未知键天然进不来），颜色严格 `#RRGGBB`，数值越界一律拒绝并回落默认。玩家存档里的脏值只丢那一个字段，绝不让整卡起不来。

持久化复用 `SBK.store` 的三级降级链（`sdk.save` → `sdk.cache` → 内存）。运行时偏好仍位于保留字段 `_sbkTheme`，切会话时不会清掉；落盘则调用 `store.merge({_sbkTheme:…})` 做顶层补丁，不把当前 state 冒充完整业务存档。业务 `store.save(obj)` 在同一 800ms 窗口与补丁合成一次写入，并自动保留调用方未显式覆盖的 `_sbk*` 内部键。

🚨 **设置面板里没有「日间/夜间/原生」三按钮，这是刻意的。** 沙盒的 `light|dark` 是**平台级**、玩家在平台设置里切，**作者只能读不能写** → 那三个按钮按了切不动，放上去就是坏控件。取代物是**风格包选择 + 启用美化开关（关＝跟随平台）+ 玩家微调（字号/行距/正文色/强调色/气泡色/气泡透明度）**。

### 🚨 `SBK.ui.hud` 已废弃

2.0 里它退化成**控件注册表 + 告警壳**：

- `.type(name, fn)` / `.types()` **仍是公开的自定义控件注册入口**，注册进去的控件在状态面板里照常生效。
- 直接当渲染器调（`SBK.ui.hud(host, schema)`）→ **告警并返回一个惰性句柄**：`el()` 返回 `null`、`feed()` 返回 `false`、`mount()` 返回 `false`、`render()` 空转，**不挂任何订阅、不写任何 DOM**。老卡不会抛异常炸整卡，但也不会再渲染出重复面板。

**为什么废弃**：1.0 时代它的职责就是「把状态数据面板渲染进功能栏槽位」，这正是实机截图里**两个重复状态栏**的根源。2.0 里它的三项职责已各有归属：状态面板 → `SBK.ui.snapshot.auto(schema)`（气泡内）、功能栏常驻 → `SBK.pinned(keys)`（单行精简条）、功能栏入口 → `SBK.ui.chrome()`。渲染器本体已是死代码，删掉省输出预算；符号保留是因为 `.type()` 被写进了协议说明、做卡人代码里存在。

## 怎么用

三步：改配置 → 跑生成器 → 创卡页导入。

```bash
cd assets/sandbox-kit

# 1. 复制一份配置去改（别直接改 example，它是基准）
cp sbk.config.example.json my-card.json

# 2. 生成（--verbose 打印拆条与体积明细，建议一直开）
python build_sbk.py my-card.json --out dist/my-card.json --verbose

# 3. 交付前复核，须 0 错
python ../../scripts/validate.py dist/my-card.json --type regex --platform mmdsandbox
```

生成器会打印一张表：每条规则的 `findRegex` / `replaceString` 长度与**输出预算**估算。预算超限（事实卡 §5.2）会直接报 ERROR 并拒绝写文件（`--force` 可强写，仅调试用）。

所有正式产物都会剥源注释；`--no-strip-comments` 只供本地排查。生成器对**最终每条规则**执行不可调高的 18000 字符安全门禁，因此保留注释导致超限时会直接报错，不会产出只能导入、不能在编辑器保存的规则。

### 交付物形态

生成器**只产一个 JSON 文件**，顶层恰好 6 键：

```
chatVersion(=1) / pageDepth(=2) / statusbar / beginning / personality / regex_scripts
```

- 这份 JSON 走的是**分离式路线**：导入路径是创卡页的「**导入正则**」按钮（原生文件选择器）。
- ✅ **更正**：旧版本这里写「沙盒不用 PNG 整卡、不用 `chara_card_v2`」，**那是错的**。`【用户实测】`沙盒**能导 v2 整卡**（编辑页导入 v2 卡按新卡处理，「新版聊天页」单选仍可改）。生成器本身不产整卡，但你可以把它的产物搬进 v2 卡：`regex_scripts` → `data.extensions.regex_scripts`、`personality` → `data.description`、世界书 → `character_book`，再用 `../../scripts/make_card_image.py` 出 PNG。走整卡就**没有手工粘贴那一步**。
- 🚨 **两条路线都要**：导入必须走**新建卡**，且**首次保存前**在创卡页把「新版聊天页」选成**使用新版**（该选择首次保存后永久不可改）。漏了这步，脚本装上但 `sdk.*` 一个都不在，页面无任何报错。
- `personality` 虽然写在 JSON 里，但**导入页不读这个字段**——它只是随 JSON 归档。走分离式时你得自己把它从 JSON 里复制出来，**手工粘贴**进创卡页的人设框。这是分离式路线唯一需要手工搬运的部分。
- 模型侧输出约定（要模型每轮吐 `[状态]` 块）必须写进 `personality`，否则状态栏永远没数据。模板见 `sbk/协议说明.md` 第六节。

### 自动拆条：为什么会有 `sbk-core-1..4` / `sbk-ui-1..5`

`splitThreshold` 默认 18000，且**不能调高**。生成器只按连续的完整 IIFE 文件边界装箱，严格保持装载顺序；任一单模块或最终规则超过 18000 都直接 ERROR，必须在源码/配置侧继续拆，不能靠提高阈值或任意切字符串绕过。

当前示例配置的实测布局：

```text
sbk-core-1  11914  core.js
sbk-core-2  14449  core-store.js + core-boot.js
sbk-core-3  18000  theme.js
sbk-core-4   7029  theme-panel.js
sbk-ui-1     7671  protocol.js
sbk-ui-2    17841  hud.js
sbk-ui-3    12719  hud-render.js + ui.js
sbk-ui-4    13392  ui-panel.js
sbk-ui-5     5207  ui-stage.js
```

每条规则有唯一 slash marker，`regex_scripts` 数组序就是装载顺序。13 条完整示例仍远低于 130 条上限。

## 关键约束速查（最容易踩的几条）

| # | 约束 | 依据 |
|---|---|---|
| 1 | **功能栏是静态的**——`h_()` 只在装载时跑一次，且正则输入是 `statusbar` 字段自身而非消息内容。动态状态栏**只能靠 JS 改 DOM** | 事实卡 §5.6 / 硬约束 14 |
| 2 | **任何 DOM 写入必须在事件回调内**——作者脚本早于 DOM 渲染，顶层 `getElementById` 实测返回 `null` | 事实卡 §4.1 / 硬约束 17 |
| 3 | **冷启动挂 `message:mount`/`done`，别挂 `ready`**——实测顺序 `new→mount→done→ready`，`ready` 最后到且**无补发** | 事实卡 §4.1 / 硬约束 5 |
| 4 | **协议标记用方括号 `[状态]`**——尖括号 `<状态>` 会被 worker 剥壳正则当非白名单标签**整个删掉** | 事实卡 §5.4 / 裁决 9 |
| 5 | **`findRegex` 统一 `/…/` slash 形态**（约定，非硬性）——裸字面量实机也生效（卡 64304 A/B 2026-08-30，与 worker 源码一致）；统一 slash 为跨平台一致，校验器对裸字面量出 WARN 不出 ERROR | 事实卡 §8.21 |
| 6 | **匹配式绝不能匹配空串**——触发 `empty-match` 会让**整条规则回滚**。`/(?!)/` 是恒失败（安全但无用），`/a*/` 才是杀手 | 事实卡 §5.2 / 裁决 6 |
| 7 | **`status` 面板的根元素必须带 `.sbk-snap`**——否则 `base.css` 对 `message-body` 的 `opacity:.9` 与 `white-space:pre-line` 重置不生效，排版必烂。外壳规则还必须带 `.sbk-snap--raw`，`hydrate()` 靠它找待升级节点 | 事实卡 §7.3 / 裁决 4 |
| 8 | **零外部依赖**——CSP `style-src` 无 `https:`、`connect-src 'self'`，外部样式表 / 外部字体 / `fetch` 全部封死 | 事实卡 §2 / 硬约束 3 |
| 9 | **属性值禁 `]>`、`-->`**，比较运算符两侧留空格——`SAFE_FOR_XML` 默认开，命中即**整条属性被删**（`onclick="if(a[0]>1)"` 是头号事故） | 事实卡 §5.5 / 硬约束 8 |
| 10 | **禁自写 `data-*` / `aria-*` / `role`**（净化器全删），用 class；浮层 z-index 取 **3500–7999** | 事实卡 §5.5 §7.2 / 硬约束 9、12 |

完整 21 条见方法论文档的「避坑清单」节与平台文档 `../../references/platforms/mmd-sandbox.md`。

## 测试

```bash
cd assets/sandbox-kit
python test_build_sbk.py
node test_sbk_runtime.mjs
for f in sbk/*.js; do node --check "$f"; done
```

生成器测试守配置、装载顺序、完整 IIFE 和 18000 门禁；runtime harness 执行 state/store/theme/stage/HUD/UI 生命周期。视觉与真实 CSS 层叠仍须走本地浏览器仿真，不拿 fake DOM 充当视觉真值。

### 🚨 怎么在实机验证自己的卡

**唯一可靠的路径是「保存编辑」。预览只读卡片正式数据，不读草稿。** 创卡页三个保存动作写到三层：

| 动作 | 写到哪 | 预览能否看到 |
|---|---|---|
| 正则面板里的「保存配置」 | 创卡页**内存草稿** | ❌ 重载即丢 |
| 底部「保存草稿」 | **服务端草稿** | ❌ 看不到 |
| 底部**「保存编辑」** | **服务端卡片正式数据** | ✅ **只有这个能让预览看到** |

操作纪律：

1. 正则面板改完点「保存配置」（进内存）。
2. **关面板，等 `.u-transition` 计数归零**（实测约 1 秒）再点底部按钮。不等就点会命中遮罩、**静默失败**。
3. 点**「保存编辑」**，重载预览。⚠ 这是**对外动作**：卡若为公开会**提交审核并消耗每周公开配额**，自动化前先确认公开设置。
4. **重载后复核字段真值**（看创卡页的字符计数器，如功能栏 `56/200`、开场白 `111/4000`）。不能只看点击有没有报错——超 20000 是静默拒绝保存、遮罩挡住也是静默失败，两者都不报错。
5. 视觉产出**必须截图验收**。DOM 计数永远反映不出「两个面板重复」「五条 bar 同色」这类问题——1.0 的两个头号缺陷正是这么漏过去的。

> 这一条是实机验收里代价最大的教训：四个新控件类型一度实机全为 0，四轮排查（怀疑代码陈旧 / 平台文本管线 / 生成器过滤）全部走错方向，真正原因是**那几轮改动都停在草稿层，预览从未看见**。代码自始至终是对的。

## 🚨 已知缺陷与限制

1. **「体力」判成 `hp`（红）是一次取舍，不是普适真理**。`bar` 字段没写 `tone` 时按 key 推断，
   而「体力」在中文卡里既可能是血条（仙侠卡最常见，且这类卡往往没有单独的「血量」字段），
   也可能是耐力条（战斗卡里与「血量」并存）。基座默认判 `hp`；
   作耐力用时显式写 `tone:'sp'` 覆盖即可——**显式 `tone` 恒优先于 key 推断**。
   英文短码 `hp|mp|sp|xp|exp|ep` 走**整词匹配**（否则 `temperature` 会被染成 mp、
   `champion` 被染成 hp），长词 `health`/`mana`/`stamina` 等才做子串匹配。
2. **未知 schema `type` 会在生成期报错；运行时则告警一次并按 `text` 降级。** 合法值为十二种数据控件加版面项 `section`，见协议说明第三节。
3. `validate.py` 会把经典 `<script>` 中的正则/字符串反斜杠识别为 JS 语法，不应再报纯 HTML 双重转义假警告；任何剩余反斜杠警告都要实际检查。
4. `replaceString` 的导入路径上限是 100000，编辑器保存上限是 20000；超限会静默拒绝整次保存，不是截断。SBK 再收紧为不可调高的 18000，导入与手填两条路径都留有余量。

## 相关文档

- `../../references/beautify/sandbox-kit.md` —— **方法论与设计思路**（为什么长这样、怎么选模式、避坑清单）
- `../../references/platforms/mmd-sandbox.md` —— 沙盒平台技术规范（含全部实测修正）
- `sbk/协议说明.md` —— 协议格式与 schema 完整参考

