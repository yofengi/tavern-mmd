# 沙盒基座 SBK（SandBox Kit）现成资产

MMD 沙盒模式的状态栏 / 美化基座：三层运行时（内核 / 主题 / 组件）+ 声明式生成器。做卡人只写配置与协议，不写平台胶水。方法论见 `../../references/beautify/sandbox-kit.md`。

> **平台归属：本目录资产【只能】用于 MMD沙盒模式（`/mmdsandbox`）。**
>
> 🚨 **不能用于当前 MMD（`/mmd`）与本地酒馆（`/st`）。** 两条硬原因：① 基座全程依赖 `sdk.*`（`sdk.on` / `sdk.save` / `sdk.stage` / `sdk.cache`），这个 SDK 只在沙盒新聊天页存在；② 布局与主题全部挂在 `[data-chat="root"]` / `[data-slot="statusbar"]` 这套沙盒专属 DOM 契约上（事实卡 §7.3）。硬搬到 `/mmd` 的结果是脚本顶层就取不到 `sdk` 而整体短路，页面上看不出异常。另外沙盒要的是**顶层恰好 6 键**（含 `chatVersion: 1`）的导入正则 JSON，与 MMD 的 4 字段 `.mmd.json` 格式本身也不兼容。
>
> 🚨 **反向同样不成立**：`../radar-examples/`（雷达法）与 `../shadowcast-examples/`（影渲法）**不能导入沙盒**——它们的点火载体是 `img onerror`，沙盒官方明令禁止；且影渲法的 Shadow DOM 隔离在沙盒是**纯负债**（沙盒本身就是跨源 iframe，隔离边界已经免费拿到了）。详见方法论文档「与既有资产的关系」节。

> ⚠️ **验证状态（务必先读）**：基座代码已过**分层单元自测**（内核 56 / 协议+HUD 151 / 组件 47 / 生成器 133 项）、全部 `.js` 过 `node --check`、生成器实跑 0 error、产物过 `python -m json.tool` 与 `validate.py --platform mmdsandbox`。
> **但尚未导入真实卡片做端到端实机验证。** 请把它当「设计与单测充分、实机待验」的资产用，首次导入务必开 `?sdkDebug=1` 看 `[SBK]` 日志。
> 注意区分两种可信度：**平台事实**（事实卡 21 条硬约束、CSS 令牌、事件时序）是**三轮真机探针 + 逆向源码**得来的，可信；**基座代码**只是单测过，未整卡跑过。
> 🚨 **已知阻断缺陷（实机必炸，见文末「已知缺陷」节）**：生成的 `sbk-boot` 规则调用 `SBK.boot(...)`，而 `sbk/*.js` 里**从未定义 `SBK.boot`**。当前产物导入后 HUD / 快照 / 主题**一个都不会启动**。

## 文件清单

| 文件 | 说明 |
|---|---|
| `build_sbk.py` | **生成器**。声明式 config → 可导入的 6 键正则 JSON。含剥注释、体积预算估算、自动拆条、净化合规校验 |
| `sbk.config.example.json` | **配置示例**（可直接跑）。JSON 不支持注释，故用 `_xxx` 键写说明，生成器丢弃所有 `_` 开头顶层键 |
| `test_build_sbk.py` | 生成器测试，133 项 |
| `sbk/base.css` | 基础样式与骨架原语。零硬编码颜色（全走 `var(--chat-*)`），含 `message-body` 与 `flex-shrink` 两处必要重置 |
| `sbk/core.js` | **内核层**：单例哨兵 / 事件总线 / 状态仓 / 持久化 / rAF 调度 / DOM 工具。导出 `window.SBK` |
| `sbk/theme.js` | **主题层**：语义 token → 平台 `--chat-*`（14 个），三态 dark/light/native |
| `sbk/protocol.js` | **协议解析器**：`[状态]…[/状态]` 块 → 状态对象。容错优先，模型格式漂移不致崩 |
| `sbk/hud.js` | **双模状态栏渲染器**：模式 A 常驻 HUD + 模式 B 消息内快照，共用一份 schema 与控件 |
| `sbk/ui.js` | **组件层**：`SBK.ui.panel` 浮层 / 抽屉 / 可拖动悬浮球。另导出私有工具箱 `SBK._uiKit` 给 ui-stage 复用 |
| `sbk/ui-stage.js` | **组件层**：`SBK.ui.stage` 舞台面板（走 `sdk.stage`）。从 ui.js 拆出，**依赖 ui.js 先装载** |
| `sbk/协议说明.md` | 协议格式、schema、控件类型、模型侧输出约定的**完整文档**。写协议或调状态栏字段一律看这份，本 README 不重复 |

装载顺序固定：`core.js` → `theme.js` → `protocol.js` → `hud.js` → `ui.js` → `ui-stage.js`。后面每个文件都假定 `window.SBK` 已存在，顺序错了就静默少功能（各文件自带告警）。

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
| 7 | **模式 B 根元素必须带 `.sbk-snap`**——否则 `base.css` 对 `message-body` 的 `opacity:.9` 与 `white-space:pre-line` 重置不生效，排版必烂 | 事实卡 §7.3 / 裁决 4 |
| 8 | **零外部依赖**——CSP `style-src` 无 `https:`、`connect-src 'self'`，外部样式表 / 外部字体 / `fetch` 全部封死 | 事实卡 §2 / 硬约束 3 |
| 9 | **属性值禁 `]>`、`-->`**，比较运算符两侧留空格——`SAFE_FOR_XML` 默认开，命中即**整条属性被删**（`onclick="if(a[0]>1)"` 是头号事故） | 事实卡 §5.5 / 硬约束 8 |
| 10 | **禁自写 `data-*` / `aria-*` / `role`**（净化器全删），用 class；浮层 z-index 取 **3500–7999** | 事实卡 §5.5 §7.2 / 硬约束 9、12 |

完整 21 条见方法论文档的「避坑清单」节与平台文档 `../../references/platforms/mmd-sandbox.md`。

## 测试

```bash
cd assets/sandbox-kit
python -m unittest test_build_sbk          # 133 项，须全绿
```

运行时三层各自的单元自测（内核 56 / 协议+HUD 151 / 组件 47）在 `sandbox-foundation/` 工作目录里，未随资产迁入。JS 语法自查：

```bash
for f in sbk/*.js; do node --check "$f"; done
```

## 🚨 已知缺陷

1. **`SBK.boot` 未实现（阻断级）**。`build_sbk.py` 的 `boot_script()` 产出 `S.boot({hostId, schema, modes, protocolTag, theme})`，但 `sbk/*.js` 里**没有任何地方定义 `SBK.boot`**。生成的卡导入后，boot 规则会走 `if(!S||!S.boot){console.warn('[SBK] boot before core');return;}` 分支静默短路 → **HUD 不挂载、快照不升级、主题不应用**。修法二选一：在 `core.js`（或新增 `boot.js`）实现 `SBK.boot(cfg)`，把 `theme.apply` / `ui.hud` / `ui.snapshot.auto` 按 `modes` 接起来；或改生成器直接产出显式调用而不走 `SBK.boot`。这是单元测试测不到的接缝——各层自测都只测自己，生成器只测产物形状。
2. **示例配置的 `schema` 与渲染器不对口**。`sbk.config.example.json` 写的是 `"schema": {"rows": [...]}` 且用 `"type": "table"`，而 `hud.js` 的 `pick()` 读的是 `schema.fields`，控件类型只有 `bar / num / text / tags / entities`（无 `table`）。当前效果是 schema 被整体忽略、退化成「按模型输出顺序全渲染」。正确写法见 `sbk/协议说明.md` 第三节。
3. `validate.py` 对 `sbk-ui-2` 报 1 个反斜杠 WARN，属 unicode 转义误报，可忽略。
4. 该校验器的 `beginning`/`name`/`regex`/`content` 上限取创卡页 UI 值，与事实卡 §6 运行时真值（4000/200/4096/100000）不同，属已知冲突。

## 相关文档

- `../../references/beautify/sandbox-kit.md` —— **方法论与设计思路**（为什么长这样、怎么选模式、避坑清单）
- `../../references/platforms/mmd-sandbox.md` —— 沙盒平台技术规范（1231 行，含全部实测修正）
- `sbk/协议说明.md` —— 协议格式与 schema 完整参考

