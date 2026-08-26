# tavern-mmd 脚本

纯 Python 标准库脚本（无 pip 依赖），任何能跑 `python` 的 agent 通用。

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
- **长度**：`statusbar`≤200、`beginning`≤10240、`personality`≤10000、`scriptName`≤20、`findRegex`≤1000、`replaceString`≤20000、`regex_scripts`≤130 条
- **匹配式**（对齐官方 `classifyPattern`）：**纯字面量放行**（`{{hud}}` 是官方首选写法，不再要求 slash literal）；slash 形式语法错 → ERROR（平台会**整条静默丢弃**）；字面量重复 → ERROR（后一条永远匹配不到）
- **SDK**：能力名不在 30 能力表、`sdk.on()` 事件名不在 12 事件表、用了不存在的 `sdk.once` / `sdk.off`、`role.get()`/`user.get()` 读封闭字段之外的字段 → 全部 ERROR（平台侧名字写错**不报错只是永不触发**，只能靠静态校验拦）
- **被禁写法**：`img onerror` 点火器与 teapot 系 → ERROR（官方明令；沙盒 `<script>` 装卡即抽出必然执行，点火器无存在意义）
- **WARN 项**：作者自写 `data-*`（会被净化删掉）；`iframe`/`link`/`meta`/`form`/`object`/`embed` 等被删标签；全局 CSS（`*{}`/`html{}`/`body{}`/`:root{}` → 应改 `[data-chat="root"]`）；HTML 缩进 4 空格（被 Markdown 当代码块，源码印在页面上）；`sdk.on` 写进 `message:mount` 回调（每挂一条气泡重复订阅）；`message:done` + `message.send` 自问自答死循环
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
- `--mode panorama`：只产**全景预览**——所有组件组合进**一个模拟 MMD 聊天页**的单文档：可滚动聊天区（第一句话整合渲染，全局美化/状态栏/侧边栏/悬浮球同场运行）+ **底部固定主输入框**（上下滑动不受影响）+ 右侧发送按钮。发送会在聊天区追加用户气泡（`.content.right`）和一条占位 AI 气泡（`.content.left`，文案标明"预览模式，真实回复需实机生成"）。输入框用 `.uni-textarea-textarea` 类名，与状态栏选项按钮的回填选择器一致，所以选项点击→回填输入框这条链在全景里也通。
- `--mode both`（默认）：两份都产，`<文件>-preview-<平台>.html`（三面板）+ `<文件>-panorama-<平台>.html`（全景）。`-o` 仅在单一 mode 时生效，both 模式按默认命名输出两份文件。

> 全景发送逻辑是预览工具自带的脚手架，在所有平台下都执行，与被测美化产物无关 —— 它不代表被测产物可以这么写（沙盒模式禁 `img onerror` 点火器，脚手架的写法不要抄进产物）。

```bash
python build-preview.py <文件> --platform mmd|mmdsandbox|st [--mode panels|panorama|both] [-o 输出.html]
```

`--platform` **必填，无默认值**（与 validate.py 不同）。

平台渲染差异：
- `st`：原样渲染，script/ES6 全执行
- `mmd`：script/ES6 全执行（已确认支持）；script 加"✓script"角标标明正常执行；inline onclick 按已实测的净化规则处理
- `mmdsandbox`：复刻真实 DOM 契约 —— `[data-chat="root"]`、顶栏、`[data-slot="statusbar"]`、messages / list / message-frame / message / message-body、composer / input / send、author-stage，以及 **14 个 `--chat-*` 设计令牌**（实测确证，官方手册只记 10 个；清单见脚本里的 `SANDBOX_DESIGN_TOKENS`），深浅两套各一份。另注入 `--rpx`（= `calc(100vw / 750)`，平台尺寸基准，作者写 `calc(24 * var(--rpx))` 才算得出来）与 `--chat-viewport-height` 静态值 —— 后两个**不属于**那 14 个令牌（`--chat-viewport-height` 在真机是 JS 写的内联 style）。并按平台的做法把**未被匹配命中**规则里的 `<style>` / `<script>` 也抽出装上（沙盒模式装卡即抽出，不需要命中）

> **沙盒预览带一条 NOTE，列明没有模拟的四类**：SDK（`sdk.*` 全部能力与 12 事件）、「消息生成中」占位、净化白名单（作者自写 `data-*` 与被删标签不会真的被删）、Markdown 管线（4 空格缩进不会真的变代码块）。这四类只能回实机 + `?sdkDebug=1` 验。创卡页预览本身也是"瘦环境"：输入框/发送/存档一律 `NOT_SUPPORTED`，只有样式与舞台可用。

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
- **只服务当前 MMD（v2）与本地酒馆（v3）**。沙盒模式不要用本脚本 —— 官方明令禁 PNG 整卡，它的交付物是导入正则 JSON + 独立 persona 文本。

测试：`python -m unittest test_make_card_image -v`（往返一致性）。

## 工作流（详见各指令文件）

产出物完成 → 子代理跑 validate.py（结果写 `工作/审核记录.md`；悬空标记必须 0 错）→ 有错则主AI/子代理修复复审 → 主AI 跑 build-preview.py（默认 `--mode both`）→ **先用 Preview 工具看三面板诊断**审核单组件（第一句话剩余、状态栏单独、悬浮组件）并测交互 → **再看全景预览二次审核**组合效果（所有组件同场无串台、输入框固定、发送/选项回填正常）→ 全景预览不默认关闭，留给用户自查是否要改（子代理做不了 Preview 这步）。

## 测试

```bash
python -m unittest test_validate test_build_preview test_make_card_image test_worldbook_tool -v
```
