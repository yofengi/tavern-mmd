# tavern-mmd 脚本

主要构建工具使用 Python 标准库（无 pip 依赖）。同层卡另有 Node 引擎/语法测试与可选 Playwright 浏览器验证，依赖见下节。

## 旧版同层卡构建与验证

本节 `build_same_layer.py` / `verify_same_layer.py` / `review_same_layer.py` 与 same-layer 基座测试均为 `/mmd` 旧页专用。沙盒同层卡改走 [新页制作指南](../references/creation/sandbox-same-layer-card.md) 的项目网页构建、`validate.py --platform mmdsandbox` 和 `build-preview.py --platform mmdsandbox --mode panorama`（chat/thin-preview 两套），另补作品测试；当前无沙盒同层专用构建器。

- **作品默认入口**：`review_same_layer.py --project 作品配置.json --out 新审核目录 --browser required`，固定源码后依次构建、通用校验、专项校验、旧 MMD 联动预览与浏览器检查，输出 `review-report.html/.md/.json`。使用现有 Node、Playwright 与本地浏览器；未执行的检查不会算通过。配置样例随 `assets/same-layer-kit/` 提供；详见 [统一预览与审核](../references/creation/same-layer-review.md)。
- `same_layer_preview.py` 复用本脚本目录 `build-preview.py` 的旧 MMD 外壳，结合 `fixtures/mmd-legacy/` 的原创状态模拟器，嵌入原样发布载荷。两页共享本地模拟状态，隔离 Frame 和来源校验保留。
- `review_same_layer_browser.mjs` 检查本次作品的联动与窄屏，并调用 `review_same_layer_native.mjs` 对照旧预览清单检查原生入口与面板操作，`test_review_same_layer.py` 检查入口的失败路径及版本一致性。原有基座单元/浏览器回归继续维护。


- `build_same_layer.py --source 项目源码 --out 新候选目录 --build-id 发布标识 --preview`：输出旧页四键正则包、独立 Frame、发布清单、可选 Mock 预览；`--no-engine` 关闭游戏，`--no-models` 关闭模型模块。新候选不覆盖已有文件。
- `validate.py 候选目录/same-layer-mmd.json --platform mmd`：先做平台结构检查。
- `verify_same_layer.py 候选目录 [--node Node路径]`：校验文件哈希、单向触发链、Base64 重组、UTF-16 长度、版本一致性和原生模式，使用 Node `--check` 检查 Host/Frame 语法。只适用于本构建器格式，不执行卡片代码。
- `python -m unittest test_build_same_layer -v`（在本目录运行）：打包回读、替换符/Unicode、预算、Mock 隔离、拒绝覆盖和损坏检出。
- `audit_native_capabilities.py --upstream 已下载仓库 --out 输出目录`：只读盘点固定上游动作定义和处理器，生成 Markdown/JSON 能力清单；不执行第三方代码。
- `node --test test_same_layer_models.mjs`：外部模型桥接投影、选择核对、目标开关、取消和 Mock。
- `node --test test_same_layer_models_browser.mjs`：独立模型 UI 和原生 DOM 夹具的完整流程，使用下述相同 Playwright 环境配置。
- `node --test test_same_layer.mjs`：确定规则、重复动作、保存失败、隔离、迁移、并发与迟到回复。
- `node --test test_same_layer_browser.mjs`：独立 headless 浏览器验证；环境变量 `PLAYWRIGHT_MODULE` 指向 Playwright 入口、`BROWSER_CHANNEL` 默认 msedge、`PYTHON` 可指定解释器、`MMD_SL_EVIDENCE_DIR` 指定截图目录。未配置 Playwright 明确 SKIP，不算通过。

通过 HTTP localhost 查看 `preview.html`（例如 `python -m http.server 8765 --directory 候选目录`）；不以 file:// 检验 Web Crypto、Web Locks 或存储来源。测试不调用真实 MMD，真站/物理手机证据须另记。

制作入口见 `references/creation/same-layer-card.md` 与 `assets/same-layer-kit/README.md`。普通 `build-preview.py` 的逐气泡三面板不直接承载同层卡；统一入口复用其中旧 MMD 全景外壳。

## worldbook_tool.py — 世界书源文件工具

统一管理大世界书的源文件、索引、搜索、构建和同步检查。工作层使用稳定 `entry_id`，导出 JSON 的 `uid` / `order` 由 build 阶段重排生成。

```bash
python <skill>/scripts/worldbook_tool.py init "工作/世界书"
python <skill>/scripts/worldbook_tool.py add "工作/世界书" --layer "30-角色层" --title "角色：莉娅" --keys "莉娅,Lia" --constant true --summary "女主核心设定"
python <skill>/scripts/worldbook_tool.py import "工作/世界书" "output/原世界书.json" --layer "40-场景物品事件层"
python <skill>/scripts/worldbook_tool.py show "工作/世界书" --entry e0001
python <skill>/scripts/worldbook_tool.py search "工作/世界书" exact "银钥匙"
python <skill>/scripts/worldbook_tool.py search "工作/世界书" fuzzy "魔法反噬" --limit 5
python <skill>/scripts/worldbook_tool.py move "工作/世界书" --entry e0001 --to-layer "20-驱动层"
python <skill>/scripts/worldbook_tool.py reorder "工作/世界书" --entry e0001 --prefix 5
python <skill>/scripts/worldbook_tool.py rename "工作/世界书" --entry e0001 --title "角色：莉娅·银钥"
python <skill>/scripts/worldbook_tool.py delete "工作/世界书" --entry e0001
python <skill>/scripts/worldbook_tool.py build "工作/世界书" --out "output/世界书.json"
python <skill>/scripts/worldbook_tool.py check "工作/世界书" --out "output/世界书.json"
```

目录结构：

```text
工作/世界书/
├── worldbook.config.json      # 层级顺序、order生成规则、next_entry_number、platform
├── index.md                   # 生成的导航索引；AI读它定位，不手改结构字段
├── notes.md                   # 设计说明、约束、人工决策、变更摘要
├── entries/                   # 正式条目源文件；一条一文件，参与 build
├── drafts/                    # 未入库草稿，不参与 build
├── patches/                   # add/move/rename/delete/build 操作日志
└── archive/                   # delete 默认归档位置，不参与 build
```

铁律：新增、导入、删除、移动、重命名、重排条目必须调用本脚本；AI 可以编辑 `entries/` 下的条目正文和非结构性 frontmatter，但编辑后必须重新 `build` + `check`。

标题限额：条目 `title`（导出为 `comment`）在 MMD 系上限 **20 字**（中文一字算 1，标点计入）。开启 `export.include_entry_id_in_comment` 时 `[e0001] ` 前缀 8 字也计入。

平台在 `worldbook.config.json` 的 `"platform"` 字段设定，取值 `mmd`（默认，取严）/ `mmdsandbox` / `st`。三者行为：

| 操作 | `mmd` | `mmdsandbox` | `st` |
|---|---|---|---|
| `add` / `rename` | **拒绝写入，返回 2** | **照常写入 + `[WARN]`** | 不检查 |
| `check` | error | **warning** | 不检查 |
| `build` | `[WARN]`，不阻断导出 | `[WARN]`，不阻断导出 | 静默 |
| `import` | `[WARN]`，不阻断（保留既有数据），随后用 `rename` 缩短 | 同 `mmd` | 不检查 |

沙盒模式为什么保留限制却只告警：20 字来源是 **MMD 创卡页 UI** 对世界书条目标题的截断，与 `chatVersion`（新旧聊天页）无关，沙盒是同一平台的新聊天页 → 限制仍在，继续提示；但官方 `validate-worldbook.mjs` **不检查该项**，本 skill 不拿一条无官方脚本背书的平台侧 UI 限制去阻断交付。代码里对应 `enforces_comment_limit()`（是否检查，黑名单 `!= "st"`）与 `comment_limit_is_hard()`（是否硬拦，`!= "mmdsandbox"`）两个函数，改动前先读它们的 docstring。

## validate.py — 静态审核

子代理可直接调用以节约主上下文。审核 JSON 合法性、BOM、双重转义、平台红线、v2规范、世界书字段。

```bash
python validate.py <文件> [--type regex|card|worldbook] [--platform mmd|mmdsandbox|st]
```

- `--type` 省略时按内容自动识别（regex_scripts→正则、spec→卡、entries→世界书）
- **`--platform` 省略默认 `mmd`（当前MMD）**。审沙盒产出必须显式传 `mmdsandbox`，否则六键顶层会被按当前MMD的四键规则误报；审本地酒馆世界书必须显式传 `st`，否则标题会被误报超限
- 退出码：0=无错误（可能有警告），1=有错误，2=用法/读取错误

审核项：
- 通用：JSON合法性、UTF-8 BOM、replaceString/HTML内双重转义反斜杠
- 正则/状态栏（`mmd`）：顶层 keys 必须恰好为 `pageDepth/statusbar/beginning/regex_scripts`；每条 keys 必须恰好为 `id/scriptName/findRegex/replaceString`，且 `id=-1`、字段类型严格、`findRegex` 必须是 slash literal；字符数(find≤1000/replace≤20000)、条数≤130、stopPropagation、平台红线、**悬空标记**（statusbar/beginning 里的 `<标记>` 无对应 findRegex → ERROR）
- JS RegExp：优先调用可用的 Node.js `new RegExp(pattern, flags)` 做真实语法门禁，`SyntaxError` → ERROR；Node 不可用时执行保守结构 fallback，并明确 WARN 未经 JS oracle。合法但 Python preview 后端不支持的 JS 正则只 WARN 并跳过模拟
- 平台红线(mmd)：script/ES6 已实测支持→放行；onerror 多行放行，但 `onerror="…"` 内部裸双引号 → ERROR；inline onclick 仅允许干净调用、固定 id 的 `eval(getElementById('FUNC').dataset.s)` 与同名 `window.__fn&&__fn()` guard-call，其他代码字面量/赋值/嵌套/sequence → ERROR；innerHTML/cssText 仍按需提示
- 角色卡：spec/同步；`mmd` 强制 v2（spec=chara_card_v2、无 group_only_greetings）；`mmdsandbox` 不套 v2 检查，改 WARN 说明沙盒真正的交付物（导入正则 JSON + 独立 persona 文本），提示改用 `--type regex`
- 世界书：entries字段、蓝绿灯配置、条目标题 `comment` ≤20字——`mmd` 报 ERROR、**`mmdsandbox` 报 WARN**（官方校验脚本不查该项，见下）、`st` 不查

### 沙盒模式专项检查（`--platform mmdsandbox`）

沙盒模式（官方口径「新页 / 新聊天页」，开关 `chatVersion: 1`）换的是一整套检查，与 `mmd` 分支不共用：

- **结构**：顶层**恰好 6 键**白名单 `chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts`；`chatVersion` 必须为 1；禁用顶层键（`role`/`presentation`/`worldbook`/`world_book`/`lorebook`/`lore_book`/`entries`/`characterBook`/`character_book`）→ ERROR；其他未知顶层键 → WARN；`id` 必须为**负数**
- **长度**：`statusbar`≤200、`beginning`≤4000、`personality`≤10000、`regex_scripts`≤130。常规交付按 `scriptName`≤20 / `findRegex`≤1000 / `replaceString`≤20000；源码归一常量分别可见 200 / 4096 / 100000。只有 replaceString 的编辑器 20000／导入 100000 双路径与编辑器拒存语义已确证，scriptName/findRegex 的双路径仍待验证。
- **匹配式**：当前 MMD 与沙盒交付都强制 slash 形态；沙盒 worker 的裸字面量分支不等于实机可交付能力。
- **SDK**：能力名不在 30 能力表、`sdk.on()` 事件名不在 12 事件表、用了不存在的 `sdk.once` / `sdk.off`、`role.get()`/`user.get()` 读封闭字段之外的字段 → 全部 ERROR（平台侧名字写错**不报错只是永不触发**，只能靠静态校验拦）
- **被禁写法**：`img onerror` 点火器与 teapot 系 → ERROR（官方明令；沙盒 `<script>` 装卡即抽出必然执行，点火器无存在意义）
- **WARN 项**：作者自写 `data-*`（会被净化删掉）；`iframe`/`link`/`meta`/`form`/`object`/`embed` 等被删标签；全局 CSS（`*{}`/`html{}`/`body{}`/`:root{}` → 应改 `[data-chat="root"]`）；HTML 缩进 4 空格（官方 WARN；实机当前会在 Markdown 前剥掉缩进，不据此断言会变代码块，仍保守顶格写）；`sdk.on` 写进 `message:mount` 回调（每挂一条气泡重复订阅）；`message:done` + `message.send` 自问自答死循环
- 判罚级别刻意与官方脚本对齐，改动前请读 `validate.py` 里 `check_comment_length` / `classify_sandbox_pattern` 的 docstring（都写明了「请勿顺手修正」的理由）

## build-preview.py — 平台保真预览

生成自包含 HTML 沙箱，主AI 用 Preview 工具打开看渲染、测交互（点按钮、切标签页、开侧边栏）。

MMD 导入 json（含 `statusbar`/`beginning`/`regex_scripts`）走**真实替换管线模拟**：先把 `statusbar + beginning` 拼成消息文本，再按 `regex_scripts` 逐条替换，最后输出三面板：

1. **第一句话剩余预览**：第一句话经全量替换后，扣除单独抽检的状态栏/悬浮组件后的剩余正文；如果第一句话含可选菜单、图片或特殊美化，会在这里显示。
2. **状态栏单独预览**：从整合结果中抽出雷达/KV状态栏；雷达法会保留 `img onerror` 引擎和隐藏信标数据，让 Preview 能实际触发 onerror。
3. **悬浮组件预览**：从整合结果中抽出 `position:fixed` / `float/sidebar/ball` 类组件（侧边栏、悬浮球等），便于单独检查。

本地酒馆正则数组（无 `beginning`）继续走逐片段 iframe 模式。MMD 系平台还会静态扫描标签间裸换行，命中则标"空白条"警告（把只有实机能发现的头号陷阱前移到预览）。

### 两种产出：三面板诊断 + 全景预览（`--mode`）

- `--mode panels`：只产**三面板诊断**（上述），逐组件隔离，定位单组件 CSS/ID 冲突。
- `--mode panorama`：只产**全景预览**。`mmd`/`st` 保留通用聊天骨架（滚动聊天区 + fixed 输入栏 + 发送占位气泡）；`mmdsandbox` 使用真实新聊天页的 root flex 外壳：header/statusbar/messages/left/right/stage/composer 都是同一列的稳定节点，只有 messages 滚动，composer 是静态 `flex-shrink:0` 子项。沙盒发送走本地 `sdk.message.send` 表面，动态消息与静态开场白使用同一 `message-body/message-extra/message-actions` 结构。
- `--mode both`（默认）：两份都产，`<文件>-preview-<平台>.html`（三面板）+ `<文件>-panorama-<平台>.html`（全景）。`-o` 仅在单一 mode 时生效，both 模式按默认命名输出两份文件。

> 全景发送逻辑是预览工具脚手架，不代表被测产物可以照抄。沙盒脚手架用经典 `<script>` + `sdk.message.send`，不使用被官方禁用的 `img onerror`；`mmd`/`st` 仍走各自旧脚手架。

```bash
python build-preview.py <文件> --platform mmd|mmdsandbox|st [--mode panels|panorama|both] [-o 输出.html]
```

`--platform` **必填，无默认值**（与 validate.py 不同）。

平台渲染差异：
- `st`：原样渲染，script/ES6 全执行
- `mmd`：script/ES6 全执行（已确认支持）；script 加"✓script"角标标明正常执行；inline onclick 按已实测的净化规则处理
- `mmdsandbox`：复刻 2026-08-27 只读实测的新聊天页外壳与稳定 DOM 契约：dark root flex 列、45px desktop header、statusbar/messages/left/right、message-frame/message/message-body/message-extra/message-actions、静态 composer/toolbar/input/send、author-stage，以及 **29 个 `--chat-*` 设计令牌**（气泡/整页 10 + 底栏与白名单弹窗 18 + 别名 1；官方手册正文只列前 10）。另注入 `--rpx=calc(100vw / 750)`；`--chat-viewport-height` 不属于那 29 个令牌，由模拟宿主写在 root 内联 style，并随 iframe resize 与键盘 inset 更新。未命中规则里的 `<style>/<script>` 仍按平台装卡即抽出执行，但 script 审计角标只留在三面板诊断，不挤进实际全景 iframe。仿真控制、证据说明和气泡边界辅助线默认关闭/折叠。

> **沙盒预览带能力精度诊断**：已装零依赖本地 SDK 模拟器，提供 `chat` / `thin-preview` profile、30 能力、12 事件、message scope、stage/theme/switch 与已确证净化/预算子集。每项标 `exact` / `conservative` / `probe-needed`；宿主握手、真实 AI 流式、完整 Markdown/净化、跨设备 save、CSP、触控/软键盘仍由真实站承担。

2026-09-19 升级：沙盒同层网页可在 `chat` 全景中检查 `content/full/closed` 舞台、关闭重开保留节点、会话切换关闭，以及 `BUSY` 时保留草稿；外层工具栏提供模拟忙态/解除忙态。流式内容按“当前已揭示的累计文本”模拟。旧页同层卡仍使用前述 `review_same_layer.py`，两套入口不互换。

静态宿主皮肤使用另一条 CSS 通道：`sandbox_host_css.py` 按 `fixtures/mmdsandbox/host-contract.json` 的 21 个开放根抽取保守子集，`sandbox_host_preview.py` 把接受的样式与宿主夹具放到 iframe 外。普通 CSS 与作者脚本留在 iframe 内；静态 `<style>` 的 `media` 条件保留。总结页提供正文编辑、锚点编辑、选中/禁用状态及树外 `summary-confirm`；缺少结构证据的根只展示注明限制的占位。`thin-preview` 不提供宿主弹窗。

预览沿用本地 `srcdoc` 与工具控制，验证的是文档归属和布局，不等价于真实跨源安全环境。动态插入的样式、SBK 运行时变量向宿主传递和完整过滤器仍需平台复测。写作边界见 [宿主皮肤指南](../references/beautify/sandbox-host-styles.md)，可选配方见 [总结页皮肤](../assets/sandbox-host-styles/README.md)。新增回归：`python -m unittest test_sandbox_host_css test_sandbox_host_preview`。

输出是自包含 HTML 文件。默认路径规则：输入文件直属项目 `output/` 时输出到 sibling `工作/`；其他位置输出到输入文件同目录。结构、findRegex、最终 inline onclick 和悬空标记的致命审计全部在写文件前完成，失败不遗留 preview/panorama 文件。不能调 Preview 工具的 agent：提示用户用浏览器打开。

## make_card_image.py — 角色卡图片导出

把角色卡 JSON 嵌入 PNG（写 tEXt chara chunk），产出可导入的整卡图片。纯 stdlib。

```bash
python make_card_image.py <卡JSON> [--bg 底图路径] [-o 输出路径]
```

- PNG：在 IDAT 前写 `chara` tEXt chunk（base64 卡 JSON）；卡 spec=chara_card_v3 时额外写 `ccv3` chunk。`--bg` 省略则生成默认米黄底图（下部带 tavern-mmd 标签），给路径则注入用户 PNG。
- JPG：**已弃用**。实测 MMD 无法从 jpg 读出卡数据（EXIF UserComment 与 JPEG COM 段两种方案均验证不可用）。`--format jpg` 会直接报错退出；底层 embed_jpg/read_jpg_chara 仅保留作历史参考。MMD 整卡只用 PNG（或 JSON，本地酒馆）。
- 自动按卡 JSON 的 `spec` 决定写 v2（仅 chara）还是 v3（chara+ccv3）。
- 退出码：0 成功，1 失败（JSON 不合法/底图缺失或非法/请求 jpg），2 用法错误。
- **服务三个平台**：当前 MMD 与沙盒模式传 v2、本地酒馆传 v3。旧版本这里写「沙盒不要用本脚本，官方明令禁 PNG 整卡」，`【用户实测】`已推翻 —— 沙盒能导 v2 整卡（编辑页导入按新卡处理），照样用本脚本产 PNG。沙盒的额外要求只在交付说明：**新建卡 + 首次保存前在创卡页选「使用新版」聊天页**。

测试：`python -m unittest test_make_card_image -v`（往返一致性）。

## 工作流（详见各指令文件）

产出物完成 → 子代理跑 validate.py（结果写 `工作/审核记录.md`；悬空标记必须 0 错）→ 有错则主AI/子代理修复复审 → 主AI 跑 build-preview.py（默认 `--mode both`）→ **先看三面板诊断**审核单组件并测交互 → **再看全景预览**审核组合效果。沙盒还须分别跑 `chat`/`thin-preview`，检查桌面、竖屏、横屏/键盘高度、主题、舞台与多轮；外层仿真控制和诊断默认折叠，用户首屏直接看到实际聊天页。截图判结构，颜色/间距/字号用 computed style 复核。

## 测试

```bash
python -m unittest test_validate test_build_preview test_make_card_image test_worldbook_tool -v
node --test test_mmdsandbox_sim.mjs
```

当前沙盒模拟器回归为 **49 项**；契约版本以 `fixtures/mmdsandbox/contract.json` 为准，不在代码外另抄行为真值。

### 全部已实现原生动作

`test_same_layer_actions.mjs` 检查外部桥接 52 项扩展的参数/结果与确认阶段；`test_same_layer_actions_browser.mjs` 构建临时测试 Frame，通过真实打包链逐项执行新增动作，另测过期目标、并发与取消。测试需 `PLAYWRIGHT_MODULE` 和本地浏览器。普通 Mock 预览并未新增这些面板 UI。

### 同层对话页模块

旧的独立诊断工具 `preview_same_layer_dialogue.py --out <新目录> [--source <作品源码>]` 生成原创 DOM 夹具的完整交互预览 `dialogue-preview.html`，仅供本地模拟，不能导入 MMD。普通构建器的 `--preview` 保持聊天/模型/游戏 Mock。新增 UI 浏览器回归为 `test_same_layer_dialogue_browser.mjs`；制作说明见 [对话页模块](../references/creation/same-layer-dialogue.md)。
