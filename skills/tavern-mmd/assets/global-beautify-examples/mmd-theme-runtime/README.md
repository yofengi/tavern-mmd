# MMD 三态主题运行时

这是面向**当前 MMD（魅魔岛 / sexyai.top，`/mmd`）**的全局主题运行时资产。成品 `mmd-theme-runtime.mmd.json` 可导入当前 MMD 正则系统（MMD 专用 4 字段格式）；日间酒红/羊皮纸与夜间深灰/柔酒红只是示例 preset，不是固定视觉规范。

> 🚨 **不适用于 MMD沙盒模式（`/mmdsandbox`），也不声明、不测试沙盒兼容性。** 本资产整套机制都是为当前 MMD 的约束设计的，在沙盒模式逐条失效：
>
> - 主题状态写在 `html[data-zmr-mode="day|night"]` 上 —— 沙盒模式禁 `html{}` / `body{}` / `:root{}` 全局选择器（官方校验 WARN），根钩子是 `[data-chat="root"]`；且**作者自写 `data-*` 会被净化删掉**，`data-zmr-mode` 这类自定义属性在那里立不住。
> - 激活与点火依赖 `img onerror` —— 沙盒模式**官方明令禁止** `img onerror` 点火器（teapot 系）。
> - `MutationObserver` 清污哨兵 + route supervisor + owner/version 租约 —— 沙盒模式不需要：平台自带 `data-theme="light|dark"`、14 个 `--chat-*` 变量（实测确证，官方手册只记 10 个）与 `theme:change` 事件，换肤只是在 `[data-chat="root"]` 上改变量。
> - 导入格式也不同：沙盒模式是**顶层恰好 6 键**的正则 JSON（含 `chatVersion: 1`），本资产的 4 字段 json 导进去不成立。
>
> 沙盒模式换肤请读 `../../../references/beautify/global-css.md`「沙盒模式换肤」与 `../../../references/platforms/mmd-sandbox.md` §6。

## 文件与模块

| 文件 | 职责 |
|---|---|
| `../mmd_cleanup_core.js` | 可复用清污 v2 factory：一个 `MutationObserver`、首次一次全量、之后按 `MutationRecord` 增量处理；支持多插件、最新污染值的属性级 delta 恢复、插件 teardown 与断连记录 prune。 |
| `quote-plugin.js` | AI 正文增量插件：始终识别 MMD 橙色元素并添加 `zmr-hdm`；双左弯引号 `“文本“` 的文本规范化默认关闭，只在用户明确 opt-in 后执行，不替换标签或删除属性。 |
| `theme.css` | 一份公共结构选择器 + day/night token；平台覆盖只在 `html[data-zmr-mode="day"]` 或 `night` 下生效。 |
| `settings-ui.js` | 可访问设置 UI factory：DOM 构建、ARIA、Escape、焦点进入/返回、当前/全部重置和 SPA body 替换后的重挂载。 |
| `runtime.js` | day/night/native 单一状态机、pagehide/pageshow 路由监督、schema-2 overrides、schema-1 迁移、资源接管和全局租约销毁。 |
| `build_theme.py` | Python 标准库生成器与发布 guard，是 MMD JSON 的单一真相源。 |
| `test_theme.py` | Python `unittest` + Node 临时 fake DOM 行为测试，覆盖 delta、插件 teardown、UI 重挂、路由竞态、迁移、CSS 隔离、升级接管与产物一致性。 |
| `mmd-theme-runtime.mmd.json` | 生成的当前 MMD 四字段导入文件。 |

生成 JSON 固定使用五条正则，`statusbar` 一次性按以下顺序部署：清污 factory、引号插件 factory、公共主题 CSS、设置 UI factory、运行时 bootstrap。每个脚本/样式都带 `data-zmr-owner='tavern-mmd/zmr'`、版本和唯一 id；bootstrap 每次重新查询候选、去重并把唯一 style 提升到 `head`。相同 owner/version/id 重复触发时复用现有 lease，仅 `refreshAssets()` 并 `reenter()`，不会 destroy worker/UI；不同版本才以 `superseded` 原因完整销毁旧 worker/UI/监听和旧实例持有的 style，但保留新候选供接管。显式 `destroy()` 才清除该 owner/theme-id 的全部 style。

## 生命周期

运行时把 `window['tavern-mmd/zmr'].lease` 作为唯一主题租约。聊天判断结合 `location.hash` 中的 `chat/chat` 与可见 `.chat` 容器，后者也便于 preview 环境。进入聊天页时启动 worker；离开聊天页依次 `stop()` worker、恢复清污 delta、移除 `data-zmr-mode` 和阅读变量并隐藏 UI，style 与路由监督留在 `head`/window。`pagehide` 会取消已排队的 route timer 并挂起 reconcile/reenter，直到 `pageshow` 清除门闩后才重新调度；因此后台页不会被旧 timer 重入。`hashchange`、`popstate`、`focus` 和 `visibilitychange` 等监督仍保留。enter/reenter/资源刷新都会调用 UI 的 `ensureMounted()`，平台替换 `body` 后复用同一 host 并挂到当前 body。首次 worker 对明确 platform target 做一次全量；后续重入只把当前 `.chat` 作为有界根处理停用期间的变化。

三种模式的语义不同：

- `day` / `night`：应用对应 token 与各自阅读配置，并启用清污。
- `native`：移除主题标记和运行时阅读变量，恢复清污记录并关闭 cleaning；同一个 observer 仍可驱动独立引号插件。
- `destroy()`：停止 worker和所有监督，恢复清污 delta，销毁插件，移除运行时 UI、主题 style、主题标记与阅读变量，并释放全局租约。

`native` 是可再次切回 day/night 的状态，不等于销毁。弯引号规范化是独立的全局 opt-in，默认 `false`，native 下仍可启用；橙色高亮识别不依赖该开关。用户开启后，插件先有界处理当前 `.chat` 内已有 AI 正文，之后继续处理新增 AI 子树；关闭后停止新的文本写入，但已经把 `“文本“` 修成 `“文本”` 的内容不会在关闭、native 或 destroy 时反向改回。插件添加的 `zmr-hdm` 类会在 destroy 时移除，原 `font`/元素及其属性始终保留。

## 设置与存储

设置按钮为 44px 贴边按钮，对话框为非模态 `role="dialog"`。模式、字号、行距、颜色、AI 气泡透明度、独立的“规范化弯引号”checkbox、“恢复当前主题默认”和“全部恢复默认”均通过 `createElement`、`textContent` 与事件监听器构建；没有 `innerHTML`、inline `onclick` 或 `cssText`。面板支持 Escape、焦点进入/返回、`hidden`、`aria-expanded`、`aria-pressed` 与 `aria-disabled`。native 模式下阅读微调 fieldset 与当前主题恢复按钮使用真实 `disabled`，但引号 checkbox 和“全部恢复默认”不被禁用。

当前存储键是 `tavern-mmd/zmr/theme-settings/schema-2`。状态只持久化 `schema`、`mode`、`normalizeQuotes` 和白名单 `overrides.day/night`；preset `DEFAULTS` 留在源码，effective theme 每次按 `DEFAULTS + overrides` 合成，不把整份 preset 写入存储。字段规则为：

- mode：`day`、`night` 或 `native`；
- `normalizeQuotes`：严格 boolean，默认 `false`；
- 颜色：严格 `#RRGGBB`；
- 字号：整数 12-32；
- 行距：1.1-2.6；
- AI 气泡透明度：整数 40-100；
- overrides：只接受 `fontSize`、`lineHeight`、`textColor`、`accentColor`、`aiBubbleColor`、`opacity`。

若 schema-2 键不存在，运行时会读取旧 `schema-1` 的完整 `themes.day/night`。迁移使用源码中明确固定的 legacy defaults，只把与旧默认不同且合法的字段写成 override，避免把当时未修改的默认值永久钉住；成功后写回 schema-2。恢复当前主题会删除当前 `overrides[mode]`；“全部恢复默认”会清空 day/night 两套 overrides，**保留当前 mode 与 `normalizeQuotes`**。schema 不符、JSON 异常、缺字段或越界值都回退到内置默认值，任何存储字符串都不会直接成为任意 CSS。localStorage 在 MMD `chatIframe` 中的持久性、隐私模式/配额异常和不同客户端 WebView 的行为仍属于**待实机验证边界**；代码会在读写异常时继续使用内存默认状态，不阻断主题。

## 清污与选择器边界

清污 selector pack 复核日期为 **2026-08-25**。它不使用“某个 scope 后代的任意 `[style]` / `[color]`”查询，只枚举明确的当前 MMD 平台 target：聊天壳、输入组件、弹窗、设置容器、dark class 与消息 wrapper。对于 `.content.left` / `.content.right`，最多处理气泡 wrapper 自身和其直接子级的 `.msg-content-box`、`.msg-options-box`、`.msg-mask`，默认拒绝更深的 AI/用户富文本正文，因此不会删除正文作者合法的白色、filter 或其他行内语义；橙色 `font` 仅由 quote plugin 识别。`zmr-hdm` 不是组件边界，因此元素的 style/color 不再橙色时插件可在属性 mutation 上移除该类；状态栏与悬浮组件边界仍跳过。清污每次实际删除同一 style property 时都会更新保存的 value/priority，每次删除污染 `color` attribute 也更新其值；native restore 因而恢复最后一次被删除的污染，而平台后写的合法非污染值不会被覆盖。清理/恢复 cycle 会 `takeRecords -> disconnect -> 写入 -> reobserve`，避免 observer 把自身写入误记为平台变更。插件同 ID 替换、显式 unregister 和最终 destroy 统一按可用的 `stop()` 后 `destroy()` teardown，异常逐步隔离，已注销实例不会在最终 destroy 再次调用。

平台 DOM 类名仍可能在 MMD 更新后变化。selector pack、`.content.left` AI 正文边界、路由 hash 与第三方状态栏跳过列表都应在实机升级后重新抽查；当前日期表示源码复核时间，不代表平台提供稳定 DOM API。

## 构建与校验

在本目录运行：

```bash
python build_theme.py
python build_theme.py --check
```

普通构建以 UTF-8 无 BOM 写出 JSON；`--check` 不写文件，并要求现有成品与源码逐字节一致。guard 会检查 MMD 四字段、五条规则顺序、所有 `findRegex` 的 `/.../` 格式、1000/20000 平台字符上限与本项目 `<18000` 余量上限、单行替换、资源 metadata、触发标记交叉污染、生命周期 API、同版本复用/异版本升级、离开聊天的视觉撤销顺序、单 observer 与增量路径、禁止正文/`body` 全量扫描、默认关闭的引号 opt-in 与 checkbox 位置、UI output/ARIA、CSS owned/状态栏隔离、`--zmr-*` 变量、禁止的宽泛选择器、day/night 平台作用域、默认文本 4.5:1 与焦点 3:1 对比度，以及 JSON 回读一致性。

`test_theme.py` 无 npm 依赖，使用 Python `unittest` 调用 Node，并在临时目录运行仓库中的实际四个 JS 源码。最小 fake DOM/Node 行为层覆盖 style value/priority、属性 mutation、连接状态、body 替换、observer records、事件、timer 与 localStorage；测试不是只做字符串断言。

```bash
python test_theme.py
```

仓库验证器：

```bash
python ../../../scripts/validate.py mmd-theme-runtime.mmd.json --platform mmd
```

相对路径从本目录计算。也可用 `python -m json.tool mmd-theme-runtime.mmd.json` 做基础 JSON 语法检查。

## 来源说明

本实现仅从仓库既有日间美化、清污案例和 ShadowCast/雷达生命周期经验中吸收架构启发。清污 factory、插件接口、三态状态机、可访问设置 UI、存储 schema、资源租约和生成 guard 均为本目录面向当前 MMD 的重写代码，不复制或继续暴露旧案例的 `_mmd_*` 第三方命名接口。
