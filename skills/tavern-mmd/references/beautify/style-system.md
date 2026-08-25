# 美化风格系统总纲

定位：本文件规定**制作期规范 token**、六维度风格模型、light/dark 配对、旧方言兼容和项目级覆盖。当前 MMD 的运行时生命周期与存储协议另见 `theme-runtime.md`。

## 1. 两层 token 模型

### 1.1 制作期规范 token

风格库和美化决策只使用下面的规范名。它们是设计数据的中间层，不是直接注入页面的全局 CSS API。

| 规范 token | 含义 |
|---|---|
| `--bg` | 页面或面板底色 |
| `--surface` | 卡片、气泡、区块底色 |
| `--surface-2` | 次级区块或层次底色 |
| `--border` | 边框和分隔线 |
| `--text` | 正文 |
| `--text-2` | 次要文字 |
| `--text-3` | 弱化文字、标签 |
| `--accent` | 主强调 |
| `--accent-2` | 辅助强调 |
| `--highlight` | 选中或高亮底色 |
| `--shadow` | 常规阴影 |
| `--shadow-accent` | 强调阴影或辉光 |
| `--success` / `--warning` / `--danger` | 语义状态色 |
| `--radius` | 组件圆角刻度 |
| `--icon-filter` | PNG / 背景图图标染色 |

### 1.2 运行时 CSS token

新产物必须选择自有命名空间 `<ns>`，将制作期规范 token 映射到 `--<ns>-*`：

```text
--bg          -> --<ns>-bg
--surface     -> --<ns>-surface
--text        -> --<ns>-text
--accent      -> --<ns>-accent
--icon-filter -> --<ns>-icon-filter
```

规则：

1. 新产物只走“规范 token -> 自有前缀运行时 token”这一条映射。
2. 不把无前缀的 `--bg`、`--text`、`--accent` 写到 `:root`、`html` 或 `body`。
3. 全局主题 token 放在 light DOM 根主题属性下；Shadow DOM 面板可消费它们，但不能成为平台 light DOM 的主题状态源。
4. 静态换肤也应使用自有前缀；只有维护历史选择器时才允许旧方言 adapter。
5. token 负责视觉值，不夹带 owner、路由或存储逻辑；运行时合同见 `theme-runtime.md`。

> **沙盒模式（`/mmdsandbox`）**：本文的六维度风格模型与 light/dark 配对**可以照用**，落地时把自有前缀 token 挂在 `[data-chat="root"]` 上，并把最终视觉值映射到平台的 10 个 `--chat-*` 变量（`--chat-bg` / `--chat-surface` / `--chat-text` / `--chat-accent` 等）。上面第 2 条在沙盒模式是**平台硬规则**而不只是纪律：`*{}` / `html{}` / `body{}` / `:root{}` 全部被官方校验判 WARN，必须改写成 `[data-chat="root"]`。第 3 条的「light DOM 根主题属性」在沙盒模式**不适用** —— 作者自写 `data-*` 会被净化删掉，主题状态读平台的 `data-theme="light|dark"`、变化订 `theme:change`。见 `global-css.md`「沙盒模式换肤」与 `../platforms/mmd-sandbox.md` §6。

## 2. 三套旧方言的兼容边界

仓库已有三套方言，保留兼容但不继续扩散：

| 语义 | 制作期规范 | 旧全局美化 | 旧状态栏 | 旧悬浮 / 雷达集成 |
|---|---|---|---|---|
| 页面底 | `--bg` | `--lb` | `--bg` | 由组件决定 |
| 区块底 | `--surface` | `--lc` | `--bg2` | `--cb` |
| 次级区块 | `--surface-2` | `--lcm` | 区块变体 | `--cbm` |
| 边框 | `--border` | `--lm` | `--border` | 通常复用 `--ac` |
| 正文 | `--text` | `--lt` | `--t1` | `--fc` |
| 次要 / 弱化文字 | `--text-2` / `--text-3` | `--lts` / 缺槽 | `--t2` / `--t3` | 项目自定义 |
| 主 / 辅助强调 | `--accent` / `--accent-2` | `--la` / `--lg` | `--accent` / `--gold` | `--ac` / 项目自定义 |
| 高亮 | `--highlight` | `--lh` | 区块变体 | `--cbm` |
| 阴影 | `--shadow` / `--shadow-accent` | `--ls` / `--lsr` | 规则内值 | `--sd` 等项目变量 |
| 图标染色 | `--icon-filter` | `--lif` | 缺槽 | 项目自定义 |

兼容策略：

- **维护旧资产**：可在旧模块自己的作用域根上写 adapter，例如 `.<ns>-legacy { --cb:var(--<ns>-surface); }`。
- **组合旧组件**：adapter 只覆盖该组件实际读取的旧变量，不建立整套全局别名。
- **新组件**：直接消费 `--<ns>-*`，不得为了“兼容”继续新增 `--cb`、`--fc` 等依赖。
- **迁移完成**：删除 adapter 前先扫描实际引用；不要机械改名后留下失效 `var()`。

## 3. light / dark 必须成对设计

运行时主题包的每个 preset 必须提供完整 `light` 与 `dark` token 集；`day` 读取 light，`night` 读取 dark。不能只把背景取反，也不能复制一套值后只改 `--bg`。

每一对至少同时校验：

- `text` 对 `bg`、`surface`、`surface-2` 的普通正文对比度 >= 4.5:1。
- 大号文字对比度 >= 3:1；控件边界、焦点环和关键图形对比度 >= 3:1。
- `text-2`、`text-3` 在实际承载背景上仍可读，不能为了“弱化”降到不可辨认。
- `accent` 上的文字、选中态、链接、危险 / 成功状态不能只靠颜色区分。
- placeholder、disabled、hover、active、focus-visible 在 light/dark 分别检查。
- PNG 图标 filter 在两套底色上分别检查，不能假定同一 filter 通用。

风格库若只提供单侧色板：静态换肤可只用该侧；运行时主题必须先补齐另一侧并完成对比度检查，不能把缺失色板标成已完成 preset。

## 4. 六维度定义

| 维度 | 内容 | 取值入口 |
|---|---|---|
| 配色 palette | bg/surface/border/text x3/accent x2/语义色，light + dark | `style-db/palettes.md` |
| 布局 layout | 密度、排列、圆角档、分隔线 | `style-db/layout-ui.md` |
| UI | 边框、阴影、hover/active/focus、按钮形状 | `style-db/layout-ui.md` |
| 字体 font | 系统安全字族、字号刻度、字重层级、数字等宽 | `style-db/fonts.md` |
| 整体性 cohesion | 明暗、圆角、空间、交互状态协调 | 本文件第 6 节 |
| 装饰 decoration | 扫描线、颗粒、辉光、硬阴影或无装饰 | `style-db/decoration.md` |

## 5. 选择与组装流程

1. 用 AskUserQuestion 先选基调组，再选具体风格；也可按用户要求混搭维度。
2. 默认取完整 bundle，不只取一组主色。
3. 生成制作期 `light` / `dark` 规范 token；静态换肤只需一侧时明确记录采用哪侧。
4. 运行第 6 节整体性和对比度检查。
5. 选择产物命名空间，把规范 token 编译为 `--<ns>-*`。
6. 只有嵌入旧模块时才生成局部 adapter。
7. 把风格、token、adapter 和玩家覆盖策略记入项目 `工作/美化决策.md`。

## 6. 整体性守护

- 明暗一致：换背景必须同步正文、弱化文字、边框、图标与控件状态。
- 圆角一致：同一产物的状态栏、面板和全局主题使用同一档；用户明确要求局部差异时记录原因。
- 装饰契合：霓虹 / 扫描线只配暗底；纸纹 / 颗粒只配亮哑光底；装饰不得降低正文可读性。
- 动效一致：hover、active 与 focus 的运动幅度和时长使用同一尺度，并尊重 `prefers-reduced-motion`。

| 冲突组合 | 原因 |
|---|---|
| 0 圆角野兽派 + 大圆角黏土柔影 | 轮廓与空间语言相反 |
| 霓虹辉光 + 亮底纸纹颗粒 | 发光与哑光材质依赖相反底色 |
| 硬阴影 + 毛玻璃模糊 | 实体边界与透明层叠的深度逻辑冲突 |

## 7. preset 与玩家覆盖

preset 是只读基线，玩家覆盖是独立增量层：

```text
resolved(theme) = preset[theme] + overrides[theme]
```

约束：

1. `overrides.day` 与 `overrides.night` 分开；切换主题不串值。
2. 玩家修改只能写 overrides，**不得回写 preset** 或风格数据库。
3. “重置当前主题”只清当前主题 overrides；“全部重置”才清两套 overrides。
4. 非法、未知或越界 token 不进入 resolved 结果；验证和存储 schema 见 `theme-runtime.md`。
5. 项目制作阶段的人工定制仍写进最终项目 preset，并在 `工作/美化决策.md` 留痕；运行时玩家操作只写偏好 overrides。
6. 换 preset 时默认保留与新 preset 兼容的白名单 overrides，或由产品明确要求清除；不得静默把旧覆盖写进新 preset。

## 8. 项目级制作覆盖

1. 预设是基线而非锁死。用户在制作期提出“主色改为某值”“状态栏圆角更小”等要求时，直接修改该项目的规范 token 或维度配置。
2. 改动只落项目产物和 `工作/美化决策.md`，不回写 `style-db/`。
3. 每次覆盖记录 token、原值、新值、适用主题和原因。
4. 单点修改后重新检查 light/dark 对比度、语义状态、圆角和组件整体性。
5. 制作期覆盖与运行时玩家 overrides 必须分开命名和存储，不能把一次玩家操作固化回项目 preset。
