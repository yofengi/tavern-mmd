# tavern-mmd

为 **MMD（魅魔岛 / sexyai.top）** 和 **本地酒馆 SillyTavern** 创建角色卡、世界书、美化（状态栏 / 全局美化）的 Claude Code Skill。

skill 本体是自包含 Markdown 文档；另附纯 Python 标准库辅助脚本，用于审核、预览、世界书源文件管理和角色卡 PNG 导出。

## 为什么需要这个 skill

MMD 是在线（uni-app 套壳）酒馆平台，与本地 SillyTavern 有显著差异：

- MMD 自己就有**两套互不通用的聊天页**：当前 MMD（旧聊天页）支持 `<script>` 与 ES6（实测全支持），但状态栏只能靠 `img onerror` 载体；**沙盒模式**（新聊天页，角色卡 `chatVersion: 1`）把 `<script>` 变成一等公民，另给官方 SDK（30 能力 / 12 事件）、稳定 `[data-chat]` 选择器、舞台与跨设备存档，且**明令禁止 `img onerror` 点火器**
- 正则限额 130 条（findRegex ≤ 1000 字符、replaceString ≤ 20000 字符），导入格式与本地酒馆不同：当前 MMD 是 4 键 json 且 findRegex 必须包斜杠，沙盒模式是 6 键 json 且纯字面量标记才是首选写法
- 角色卡：MMD 系（当前 MMD 与沙盒模式）都仅支持 chara_card_v2（不识别 v3），整卡只能用 png 导入。沙盒模式**同样可导 v2 整卡** —— 编辑页导入 v2 卡按**新卡**处理，创卡页「新版聊天页」单选仍可选；也可改走分离式的导入正则 json + 独立人设文本
- 不支持酒馆助手、MVU 变量框架、STScript

通用的角色卡创作流程在 MMD 上会产出无法运行的卡。本 skill 内置 **平台差异矩阵**，根据目标平台自动选择可行的技术方案（如 MMD 状态栏首选混合态雷达法：模型只输出纯键值对，JS 引擎动态装配 UI）。

## 功能

| 能力 | 说明 |
|---|---|
| 三平台支持 | 当前 MMD（旧聊天页，`<script>`/ES6 + onerror 载体）/ MMD 沙盒模式（新聊天页 `chatVersion:1`，`<script>` 一等公民 + 官方 SDK + 舞台）/ 本地酒馆 SillyTavern |
| 角色卡创作 | 标准流程（快问快答）与深度共创流程（开放讨论 + 方案收敛）两种模式 |
| 世界书制作 | 索引源文件工作流（entry_id 稳定、uid/order build 重排）、蓝绿灯策略、token 预算、递归控制 |
| 状态栏 | 首选混合态雷达法（特征嗅探 + 动态DOM + 双轨生命周期 + 七重防御）；KV V4.0 轻量备选 |
| 全局美化 | 静态换肤 / 当前 MMD day-night-native 三态运行时主题包二档；运行时含 owner/version、路由重入、可恢复清污、玩家分主题覆盖与移动端设置面板协议 |
| 项目管理 | 每个项目独立文件夹（main.md / plan.md / 资料 / 工作 / output），断点续作 |
| 质量保障 | 写作规则（绝对零度 / 八股化扫描 / 具体性检查）+ 分层交付检查清单（含运行时主题矩阵） |

## 审核与预览脚本

skill 自带多个纯 Python 标准库脚本（零依赖，全 agent 通用），AI 会根据 skill 指引在制作与交付前自行调用，用法详见 `skills/tavern-mmd/scripts/README.md`。

- **JSON 格式审核**：AI 调用 `scripts/validate.py` 对导入 json 做静态审核（JSON 合法性、BOM、双重转义、平台红线、字符数限额、v2 与世界书字段）。
- **世界书源文件工具**：AI 调用 `scripts/worldbook_tool.py` 管理 `工作/世界书/` 的 add/delete/move/rename/show/search/build/check，避免直接编辑大 JSON。
- **状态栏 / 全局美化预览**：AI 调用 `scripts/build-preview.py` 生成 HTML 沙箱，再用 agent 的 Preview 工具自行查看渲染、测交互。

> ⚠️ 渲染沙箱是标准浏览器渲染，不一定能暴露状态栏在 MMD 上的所有问题（如 markdown 管线把换行解析成空 `<p>` 撑出的空白条），状态栏 / 美化仍需实机导入 MMD 验证。

## 安装

skill 本体是纯 Markdown，任何能读文件的 AI 编程助手都能用。各 agent 的存放位置：

| Agent | Skill 位置 | 指令位置 | 调用方式 |
|---|---|---|---|
| **Claude Code** | `~/.claude/skills/` | `~/.claude/commands/` | 触发词自动激活 + `/指令` |
| **OpenCode** | 原生兼容 `~/.claude/skills/`（或 `~/.config/opencode/skills/`） | `~/.config/opencode/commands/` | `/指令` |
| **Pi** | `~/.pi/agent/skills/`（或 `.pi/skills/` 项目级） | 技能即指令 | `/skill:tavern-mmd` |
| **Codex CLI** | `~/.codex/skills/` | `~/.codex/prompts/` | `/指令名` |
| **Trae IDE** | 无技能目录 → 仓库复制进项目 | `.trae/rules/` 或项目根 `AGENTS.md` | 规则常驻 / `#规则名` |
| **任意 agent** | 任意路径 clone | 规则文件加一句指路 | 见下方"通用兜底" |

### Claude Code

```bash
cp -r skills/tavern-mmd ~/.claude/skills/
cp commands/*.md ~/.claude/commands/
```

> Windows：`~/.claude` 即 `C:\Users\<用户名>\.claude`。安装后**开启新会话**生效。
> 若不想占用全局指令命名空间，可只装 skill 本体——直接对话（如"给 MMD 新版对话框做个状态栏"）也能触发。

### OpenCode

OpenCode 会自动发现 `~/.claude/skills/*/SKILL.md`，按 Claude Code 方式安装 skill 即可零配置复用。指令另复制一份：

```bash
cp -r skills/tavern-mmd ~/.claude/skills/          # OpenCode 自动发现
cp commands/*.md ~/.config/opencode/commands/       # /mmd /beautify 等指令
```

OpenCode 没有 Claude Code 那样的触发词自动路由，建议在 `~/.config/opencode/AGENTS.md` 加一行下方"通用兜底"的指路句。

### Pi

```bash
cp -r skills/tavern-mmd ~/.pi/agent/skills/
```

聊天中输入 `/skill:tavern-mmd` 调用。commands 目录下的指令文件内容可手动复制为提示模板（`~/.pi/agent/prompts/`），或直接在对话里描述任务。

### Codex CLI

```bash
cp -r skills/tavern-mmd ~/.codex/skills/
cp commands/*.md ~/.codex/prompts/                  # 以 /mmd /beautify 等方式调用
```

### Trae IDE

Trae 没有技能目录，走"仓库进项目 + 规则指路"：

1. 把本仓库（至少 `skills/tavern-mmd/` 文件夹）复制到你的项目里
2. 在项目根新建 `AGENTS.md`（Trae 原生支持，且兼容 CLAUDE.md），或在 `.trae/rules/project_rules.md` 中写入下方指路句
3. commands 的指令文件在 Trae 中不可用，需要哪个流程就把对应 .md 内容粘贴进对话

### 通用兜底（任意 agent）

clone 本仓库到任意位置，在该 agent 的规则文件（AGENTS.md / 系统提示 / rules）里加一句：

```
制作酒馆角色卡、世界书、状态栏或全局美化（MMD/SillyTavern 相关）时，
必须先完整阅读 <仓库路径>/skills/tavern-mmd/SKILL.md，
并按其中"任务路由"表读取对应 references 文档后再动工。
```

> **路径注意**：`commands/` 里的 mmd/mmdsandbox/st 三个平台指令内写的是 `~/.claude/skills/tavern-mmd/...` 绝对路径。skill 装在其他位置时，请把指令文件里的路径替换为实际位置（或依赖 agent 自己的技能发现机制，不用指令文件）。

## 指令

指令分两个维度，自由组合：

### 平台指令（设定目标平台）

| 指令 | 平台 |
|---|---|
| `/mmd` | 当前 MMD，旧聊天页（`<script>`/ES6 可用，状态栏走 img onerror 载体） |
| `/mmdsandbox` | MMD 沙盒模式，新聊天页（`chatVersion: 1`；`<script>` 一等公民 + 官方 SDK + 舞台 + 跨设备存档） |
| `/st` | 本地酒馆 SillyTavern（无限制） |

`/mmd` 与 `/mmdsandbox` 是同一个站的两套聊天页，**技术写法互不通用，选错的产出不报错、只是不生效**。卡是新建的且在创卡页确认过是「新页 / 新版对话框」→ `/mmdsandbox`；老卡或不确定 → `/mmd`（`chatVersion` 只在新建卡导入时被读取，没法把老卡升级成新页）。

### 任务指令（执行制作）

| 指令 | 用途 |
|---|---|
| `/cardplan` | 角色卡标准工作流：弹窗快问快答 → plan.md → 执行 |
| `/cardplanmax` | 角色卡深度工作流：开放讨论 → 方案收敛 → 分节设计确认 → 分段执行 |
| `/worldbook` | 制作世界书，输出可导入 json |
| `/beautify` | 制作美化（全局美化 / 状态栏） |
| `/helpmmd` | 显示全部指令帮助 |

### 组合示例

```
/mmd → /beautify          # 当前 MMD 状态栏（雷达法四条正则，产出可导入json）
/mmdsandbox → /beautify   # 沙盒模式状态栏（<script>+SDK，长期面板挂舞台）
/st → /worldbook          # 本地酒馆世界书（全字段，json 直接导入）
/mmd → /cardplanmax       # 从零共创一张当前 MMD 完整角色卡
```

## 产出物

| 产出 | 本地酒馆 `/st` | 当前 MMD `/mmd` | 沙盒模式 `/mmdsandbox` |
|---|---|---|---|
| 角色卡 | chara_card_v3 json | chara_card_v2 json（MMD 仅识别 v2），整卡走 png | **chara_card_v2 json / 整卡 png**（同当前 MMD，导入按新卡处理）；或分离式 = 6 键导入正则 json + 独立 persona 文本 |
| 世界书 | SillyTavern 世界书 json | 同左 | 同左：走整卡进卡内 `character_book`，走分离式出独立 json（根对象只留 `entries`）。**只是不能并进那份 6 键正则 json** |
| 正则 | 正则脚本 json（直接导入） | MMD 导入 json（4 键，首选）；手填清单 .md 备选 | 导入正则 json（**6 键**，多 `chatVersion`/`personality`）；手填清单 .md 备选 |

## 目录结构

```
skills/tavern-mmd/
├── SKILL.md                      # 入口：平台差异矩阵、任务路由、项目文件树规则
├── references/
    ├── platforms/                # 三平台技术规范
    │   ├── mmd.md                #   当前 MMD / 旧聊天页（onerror 载体、五大架构模式、待验证标注）
    │   ├── mmd-sandbox.md        #   MMD 沙盒模式 / 新聊天页（SDK 30能力12事件、舞台、6键导入json、人设格式）
    │   └── sillytavern.md        #   本地酒馆（position 表、正则字段）
    ├── creation/                 # 创作规则
    │   ├── character.md          #   角色写作（绝对零度 / 八股化 / 具体性）
    │   ├── worldbook.md          #   世界书索引源文件工作流 + 蓝绿灯策略 + 条目规划
    │   ├── opening.md            #   开场白三要素
    │   └── style.md              #   文风条目模板
    ├── beautify/                 # 美化方案
    │   ├── statusbar-radar.md    #   混合态雷达法状态栏（MMD首选：五级分类+防御体系）
    │   ├── statusbar.md          #   KV V4.0 状态栏（轻量备选：三段正则模板 + 数据继承）
    │   ├── global-css.md         #   全局美化二档分流 + uni-app 类名速查
    │   ├── theme-runtime.md      #   当前 MMD 三态运行时权威协议
    │   ├── style-system.md       #   制作期 token、运行时前缀映射与覆盖
    │   └── regex-rules.md        #   正则设计原则与平台限额
    ├── output/                   # 产出格式权威参考
    │   ├── card-json.md          #   chara_card_v3 完整字段 + v2 差异（MMD 交付格式）
    │   ├── worldbook-json.md     #   独立世界书 json + 与卡内条目字段差异对照
    │   └── regex-output.md       #   正则 json / MMD 手填清单模板
    └── quality/
        └── checklist.md          # 交付前检查清单（含雷达法专项）
└── assets/
    ├── global-beautify-examples/ # 当前 MMD runtime 优先；旧日间 selector reference
    │   └── mmd-theme-runtime/    # day/night/native 运行时主题资产
    └── radar-examples/           # 西幻 RPG 状态栏；旧日夜集成包仅 legacy 参考

commands/                         # 8 个斜杠指令
过时资产/                          # 已退役平台的存档（不随 skill 分发，仅作历史参考）
```

## 平台差异矩阵（核心）

| 能力 | 本地酒馆 | 当前 MMD | 沙盒模式 |
|---|---|---|---|
| `<script>` | ✅ | ✅ 可执行，但 per-message 自渲染/定位不可用 | ✅ **一等公民**：装卡即抽出、整卡只跑一次；per-message 走 `message:mount` |
| ES6+ | ✅ | ✅ 无限制（已确认实测全支持） | ✅ |
| 正则导入 | json | MMD 专用 json（**4 键**）或手填，≤130 条；findRegex 必须包斜杠 | 导入正则 json（**6 键**）或手填，≤130 条；findRegex 可用纯字面量（官方首选） |
| 状态栏 | 雷达法 / KV V4.0 | 首选混合态雷达法（img onerror 载体） | `<script>` + SDK（`message:done` 解析正文）；**onerror 点火器被官方禁**；长期面板挂舞台 |
| 官方 SDK / 舞台 / 存档 | ❌ | ❌ | ✅ 30 能力 / 12 事件、`sdk.stage`、`sdk.save` 跨设备 |
| 角色卡格式 | v3 json / png | 仅 chara_card_v2，整卡走 png | 不用 v2、**官方禁整卡 PNG**：正则 json + persona 文本 |
| MVU/STScript | ✅ | ❌（保守） | ❌（官方 SDK 顶替） |

> 证据等级不同，别混用：当前 MMD 的结论多为本 skill 实机实测（`<script>`、ES6、正则上限均已确认）；**沙盒模式的结论来自官方手册与官方校验脚本，尚未做过实机探针**，官方没写的（沙盒底层形态、`document.currentScript`）一律标 `【原文未说明】`，不做推断补齐。任一平台上未确认的能力都按「不可用」保守处理并标"待验证"，详见 `skills/tavern-mmd/references/platforms/mmd.md` 与 `mmd-sandbox.md`。

## 来源与致谢

- **社区快照边界**：早期 MMD 平台（已退役，存档在仓库根 `过时资产/`）的开发规范、类名定义、KV-Robust V4.0 与 2026-06-21 日间美化均为用户提供的社区文档快照；除文内保留的既有署名外，作者、原 URL 与许可证未完整记录，仅作兼容研究参考，不宣称原创。雷达法材料保留既有“黑洞猫”署名，但原 URL 与许可证同样未记录。
- **架构启发后的重写**：当前 MMD `theme-runtime.md` 的 day/night/native 生命周期、owner/version 租约、可恢复 property delta、存储 schema 和测试矩阵，以及 `assets/global-beautify-examples/mmd-theme-runtime/` 对应新资产，均是在既有材料提供架构启发后重新设计与实现，不复制旧运行时代码。其 MMD 实机验证状态只以资产 README / 测试记录为准，本 README 不替代实机证据。

## License

MIT 适用于仓库中可明确归属 tavern-mmd 的原创及架构启发后重写内容。用户提供的社区文档/资产快照未记录原许可证，仅作兼容研究参考，不因收录而被重新许可为 MIT。
