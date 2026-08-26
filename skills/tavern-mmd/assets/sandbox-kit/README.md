# 沙盒基座 SBK（SandBox Kit）现成资产

MMD 沙盒模式的状态栏 / 美化基座：三层运行时（内核 / 主题 / 组件）+ 声明式生成器。做卡人只写配置与协议，不写平台胶水。方法论见 `../../references/beautify/sandbox-kit.md`。

> **平台归属：本目录资产【只能】用于 MMD沙盒模式（`/mmdsandbox`）。**
>
> 🚨 **不能用于当前 MMD（`/mmd`）与本地酒馆（`/st`）。** 两条硬原因：① 基座全程依赖 `sdk.*`（`sdk.on` / `sdk.save` / `sdk.stage` / `sdk.cache`），这个 SDK 只在沙盒新聊天页存在；② 布局与主题全部挂在 `[data-chat="root"]` / `[data-slot="statusbar"]` 这套沙盒专属 DOM 契约上（事实卡 §7.3）。硬搬到 `/mmd` 的结果是脚本顶层就取不到 `sdk` 而整体短路，页面上看不出异常。另外沙盒要的是**顶层恰好 6 键**（含 `chatVersion: 1`）的导入正则 JSON，与 MMD 的 4 字段 `.mmd.json` 格式本身也不兼容。
>
> 🚨 **反向同样不成立**：`../radar-examples/`（雷达法）与 `../shadowcast-examples/`（影渲法）**不能导入沙盒**——它们的点火载体是 `img onerror`，沙盒官方明令禁止；且影渲法的 Shadow DOM 隔离在沙盒是**纯负债**（沙盒本身就是跨源 iframe，隔离边界已经免费拿到了）。详见方法论文档「与既有资产的关系」节。

> ✅ **验证状态（务必先读）**：2.0 已**实机截图验收通过**（2026-08-26，卡 64257 预览）：气泡内**只剩一个**状态面板、功能栏是 `设置` 按钮（chrome）、三张分组卡（状态/行囊/见闻）、九种数据类型全渲染、进度条不再是五条同色、`pinned` 默认关未出现、`[状态]` 裸标记不外泄、`#sbk-hud` 宿主计数 1。逐项结果见工作目录的 `资料/基座2.0设计.md` 第四bis节。
> 代码侧另有：分层 harness（内核 / 协议+HUD / 组件）与生成器 **180 项**测试全绿、全部 `.js` 过 `node --check`、生成器实跑 0 error、产物过 `python -m json.tool` 与 `validate.py --platform mmdsandbox`。
> **仍未验证的**：浮层拖动与菜单翻转、舞台开关、平台深浅色切换的跟随、多轮真实对话里的增量更新。这几项只有离线 harness 与代码审查背书。
> 注意区分两种可信度：**平台事实**（事实卡 21 条硬约束、CSS 令牌、事件时序）来自**三轮真机探针 + 逆向源码**；**基座代码**的状态面板与版面层已实机截图确认，上面列出的四项仍待验。首次导入建议开 `?sdkDebug=1` 看 `[SBK]` 日志。
>
> 🚨 **要在预览里验证自己的卡，必须点底部「保存编辑」。预览只读卡片正式数据，不读草稿**（正则面板的「保存配置」只进内存草稿，底部「保存草稿」只写服务端草稿，两者预览都看不到）。这一条踩错会让你以为基座坏了——实机验收时正是它导致四轮误判，详见工作目录的 `资料/沙盒实测报告.md` §三ter。

## 文件清单

| 文件 | 说明 |
|---|---|
| `build_sbk.py` | **生成器**。声明式 config → 可导入的 6 键正则 JSON。含剥注释、体积预算估算、自动拆条、净化合规校验 |
| `sbk.config.example.json` | **配置示例**（可直接跑）。JSON 不支持注释，故用 `_xxx` 键写说明，生成器丢弃所有 `_` 开头顶层键 |
| `test_build_sbk.py` | 生成器测试，180 项 |
| `sbk/base.css` | 基础样式与骨架原语。零硬编码颜色（全走 `var(--chat-*)`），含 `message-body` 与 `flex-shrink` 两处必要重置 |
| `sbk/core.js` | **内核层**：单例哨兵 / 事件总线 / 状态仓 / 持久化 / rAF 调度 / DOM 工具。导出 `window.SBK` |
| `sbk/theme.js` | **主题层**：语义 token → 平台 `--chat-*`（14 个）；风格包（preset）+ 玩家微调（overrides）两层合成、设置面板表单、偏好持久化 |
| `sbk/protocol.js` | **协议解析器**：`[状态]…[/状态]` 块 → 状态对象。容错优先，模型格式漂移不致崩 |
| `sbk/hud.js` | **状态面板渲染器**：`snapshot()` 拼字符串 / `hydrate()` 建 DOM，共用一份 vnode 与控件表（九种数据类型 + `section` 版面项）。`SBK.ui.hud` 已废弃为注册表，见下文 |
| `sbk/ui.js` | **组件层**：`SBK.ui.panel` 浮层 / 抽屉 / 可拖动悬浮球。另导出私有工具箱 `SBK._uiKit` 给 ui-stage 复用 |
| `sbk/ui-stage.js` | **组件层**：`SBK.ui.stage` 舞台面板（走 `sdk.stage`）。从 ui.js 拆出，**依赖 ui.js 先装载** |
| `sbk/协议说明.md` | 协议格式、schema、控件类型、模型侧输出约定的**完整文档**。写协议或调状态栏字段一律看这份，本 README 不重复 |

装载顺序固定：`core.js` → `theme.js` → `protocol.js` → `hud.js` → `ui.js` → `ui-stage.js`。后面每个文件都假定 `window.SBK` 已存在，顺序错了就静默少功能（各文件自带告警）。

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

### `chrome` 层：功能栏入口 + 设置抽屉

```js
SBK.ui.chrome({ hostId: 'sbk-hud', settings: true, label: '设置', title: '阅读设置',
                width: '80%', preset: '古卷', entries: [{ label: '档案', onSelect: fn }] });
// -> { el(), toggle(), panel() }
```

`boot()` 在 `modes.chrome` 为真时自己调它（传 `{hostId}`），一般不用手写。**模块级单例**：重复调用直接返回已有句柄并告警。它也容错 `chrome(hostEl, opts)` 形态（首参是元素就当宿主）。

- 只负责「功能栏上有个按钮，点了调设置抽屉」。抽屉本体归主题层（`SBK.theme.prefs.panel/toggle`），chrome 不持有引用——单一归属，避免两处状态不同步。
- 它建的是宿主里的子容器 `<hostId>-chr`，**只清自己这一个子节点**。精简条宿主是 `<hostId>-pin`，两者是兄弟：清整个宿主会把对方擦掉（`core.js` 与 `ui.js` 都就此留了注释）。
- 缺主题层时按钮仍在，点了只告警，不抛异常炸整卡。

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

持久化复用 `SBK.store` 的三级降级链（`sdk.save` → `sdk.cache` → 内存），偏好挂在状态仓的保留字段 `_sbkTheme` 上：与业务存档同文档、同一次节流写入，既不抢 key 也不互相覆盖。`_` 开头的键在状态面板里不渲染，所以它不会漏进面板。

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

`--no-strip-comments` 保留注释便于排查，但 `core.js + theme.js` 带注释已 20757 字符、逼近创卡页编辑器显示上限 20000，正式产出**别开**。

### 交付物形态

生成器**只产一个 JSON 文件**，顶层恰好 6 键：

```
chatVersion(=1) / pageDepth(=2) / statusbar / beginning / personality / regex_scripts
```

- **沙盒不用 PNG 整卡、不用 `chara_card_v2`**。导入路径是创卡页的「**导入正则**」按钮（原生文件选择器），不是角色卡导入。
- `personality` 虽然写在 JSON 里，但**导入页不读这个字段**——它只是随 JSON 归档。你得自己把它从 JSON 里复制出来，**手工粘贴**进创卡页的人设框。这是唯一需要手工搬运的部分。
- 模型侧输出约定（要模型每轮吐 `[状态]` 块）必须写进 `personality`，否则状态栏永远没数据。模板见 `sbk/协议说明.md` 第六节。

### 自动拆条：为什么规则名会变成 `sbk-ui-1/2/3`

单条规则的 `replaceString` 超过 `splitThreshold`（默认 18000，给编辑器显示上限 20000 留 2000 余量）时，生成器**按文件边界**自动拆成多条，各自拿一个唯一的 slash 标记。跑示例配置的实际结果：

```
sbk-core   {{sbk-core}}    14704   core.js + theme.js
sbk-ui-1   {{sbk-ui-1}}    13818   protocol.js + hud.js
sbk-ui-2   {{sbk-ui-2}}    16132   ui.js
sbk-ui-3   {{sbk-ui-3}}     4298   ui-stage.js
```

拆条**严格保持装载顺序**（`regex_scripts` 数组序即装载顺序，worker 按 `regexSort` 升序跑）。**绝不切开单个文件**——每个文件是完整 IIFE，切一半必然语法错；单文件自身超阈值时它会独占一条并告警。`regexList` 上限 130 条，拆条成本可忽略。

## 关键约束速查（最容易踩的几条）

| # | 约束 | 依据 |
|---|---|---|
| 1 | **功能栏是静态的**——`h_()` 只在装载时跑一次，且正则输入是 `statusbar` 字段自身而非消息内容。动态状态栏**只能靠 JS 改 DOM** | 事实卡 §5.6 / 硬约束 14 |
| 2 | **任何 DOM 写入必须在事件回调内**——作者脚本早于 DOM 渲染，顶层 `getElementById` 实测返回 `null` | 事实卡 §4.1 / 硬约束 17 |
| 3 | **冷启动挂 `message:mount`/`done`，别挂 `ready`**——实测顺序 `new→mount→done→ready`，`ready` 最后到且**无补发** | 事实卡 §4.1 / 硬约束 5 |
| 4 | **协议标记用方括号 `[状态]`**——尖括号 `<状态>` 会被 worker 剥壳正则当非白名单标签**整个删掉** | 事实卡 §5.4 / 裁决 9 |
| 5 | **`findRegex` 一律 `/…/` slash 形态**——实机裸字面量 `{{probe}}` 不生效，加斜杠立即生效 | 硬约束 21 |
| 6 | **匹配式绝不能匹配空串**——触发 `empty-match` 会让**整条规则回滚**。`/(?!)/` 是恒失败（安全但无用），`/a*/` 才是杀手 | 事实卡 §5.2 / 裁决 6 |
| 7 | **`status` 面板的根元素必须带 `.sbk-snap`**——否则 `base.css` 对 `message-body` 的 `opacity:.9` 与 `white-space:pre-line` 重置不生效，排版必烂。外壳规则还必须带 `.sbk-snap--raw`，`hydrate()` 靠它找待升级节点 | 事实卡 §7.3 / 裁决 4 |
| 8 | **零外部依赖**——CSP `style-src` 无 `https:`、`connect-src 'self'`，外部样式表 / 外部字体 / `fetch` 全部封死 | 事实卡 §2 / 硬约束 3 |
| 9 | **属性值禁 `]>`、`-->`**，比较运算符两侧留空格——`SAFE_FOR_XML` 默认开，命中即**整条属性被删**（`onclick="if(a[0]>1)"` 是头号事故） | 事实卡 §5.5 / 硬约束 8 |
| 10 | **禁自写 `data-*` / `aria-*` / `role`**（净化器全删），用 class；浮层 z-index 取 **3500–7999** | 事实卡 §5.5 §7.2 / 硬约束 9、12 |

完整 21 条见方法论文档的「避坑清单」节与平台文档 `../../references/platforms/mmd-sandbox.md`。

## 测试

```bash
cd assets/sandbox-kit
python -m unittest test_build_sbk          # 180 项，须全绿
```

运行时三层各自的分层 harness（内核 / 协议+HUD / 组件）在 `sandbox-foundation/` 工作目录里，未随资产迁入。JS 语法自查：

```bash
for f in sbk/*.js; do node --check "$f"; done
```

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
2. **schema 的 `type` 写错不会报错**。`hud.js` 是 `TYPES[type] || TYPES.text`，表外的名字**静默回落成 `text`**；生成器也不校验 type 白名单。合法值恰十种，见 `sbk/协议说明.md` 第三节与 `sbk.config.example.json` 的 `_schemaTypes`。
3. `validate.py` 对 `sbk-ui-2` 报 1 个反斜杠 WARN，属 unicode 转义误报，可忽略。
4. 该校验器的 `beginning`/`name`/`regex`/`content` 上限取创卡页 UI 值，与事实卡 §6 运行时真值（4000/200/4096/100000）不同，属已知冲突。**注意这不只是"数字不同"**：`replaceString` 走**创卡页正则编辑器**手工录入时 20000 是**硬上限，超限直接拒绝保存**（点击无提示、重载后改动全部回滚，不是截断）；走**「导入正则」导入 JSON** 时上限是 100000。生成器默认阈值 18000 按编辑器路径的保守值定，**两条路径都安全**（事实卡 §6.1）。

## 相关文档

- `../../references/beautify/sandbox-kit.md` —— **方法论与设计思路**（为什么长这样、怎么选模式、避坑清单）
- `../../references/platforms/mmd-sandbox.md` —— 沙盒平台技术规范（1231 行，含全部实测修正）
- `sbk/协议说明.md` —— 协议格式与 schema 完整参考

