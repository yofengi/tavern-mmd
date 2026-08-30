---
name: tavern-mmd
description: 为MMD（魅魔岛/sexyai.top，含沙盒模式新聊天页）和本地酒馆SillyTavern创建角色卡、世界书、美化（状态栏/全局美化）。触发词：MMD、魅魔岛、沙盒模式、沙盒、新版对话框、MMD新页、新聊天页、chatVersion、酒馆角色卡、角色卡、世界书、状态栏、全局美化、美化、正则、开场白、uni-app酒馆、在线酒馆、sexyai。支持指令 /cardplan /cardplanmax /mmd /mmdsandbox /st /worldbook /beautify /helpmmd。
---

# tavern-mmd：三平台酒馆角色卡创作

## 第一步：确定目标平台

任何技术产出（状态栏/美化/正则/含JS的内容）前必须先确定目标平台。纯文字创作（角色设定/世界书条目正文/开场白）平台无关，可不阻塞。

确定方式（优先级从高到低）：
1. 用户用过平台指令（/mmd /mmdsandbox /st）→ 已写入项目 main.md 或会话上下文
2. 项目 main.md 中已记录"目标平台"
3. 都没有 → 用 AskUserQuestion 问一次，并记录到 main.md

MMD 有两条互不通用的技术路线，问平台时必须区分：卡的 `chatVersion: 1`（官方叫「新页 / 新聊天页」，本 skill 叫「沙盒模式」）走 `/mmdsandbox`，`chatVersion: 0`/缺省走 `/mmd`。选错产出静默失效（脚本装上但 SDK 全不在，页面无报错）。

## 平台差异矩阵（所有技术分流的依据）

| 能力 | 本地酒馆 /st | 当前MMD /mmd | 沙盒模式 /mmdsandbox |
|---|---|---|---|
| `<script>` 标签 | ✅ | ✅ 可执行；**per-message 自渲染/定位不可用**，状态栏仍走 img onerror；document-level 一次性 bootstrap 与全局 handler 定义可用 | ✅ **一等公民**：装卡即抽出（不需被匹配命中）、**整卡只跑一次**；per-message 绑定由 `sdk.on('message:mount')` 顶替；**`img onerror` 点火器被官方明令禁止** |
| ES6+ 语法 | ✅ | ✅ 实测全支持（img onerror 载体下，7/7 语法探针全绿），**推荐 ES6** | ✅ 实机与官方示例均确认 |
| 正则导入方式 | json 直接导入 | json导入（MMD专用4字段格式）或UI手填 | 创卡页「导入正则」json（**6键格式**，多 `chatVersion`/`personality`）或UI手填；**不能导入整卡** |
| 正则限额 | 无硬限制 | ≤130条；findRegex≤1000字符；replaceString≤20000字符 | ≤130条；保守交付按 scriptName≤20 / findRegex≤1000 / replaceString≤20000。源码可见归一常量为 200 / 4096 / 100000；只有 replaceString 的编辑器 20000／导入 100000 双路径已确证，scriptName/findRegex 的双路径与超限语义仍待验证；另 statusbar 200 / **beginning 4000** / personality 10000 |
| `findRegex` 形态 | 任意正则 | **强制 `/pattern/flags` slash literal**，固定标记也要包斜杠 | **交付统一 `/pattern/flags` slash 形态**（约定，非硬性）：实机复验裸字面量也生效（卡 64304 A/B，2026-08-30），与 worker 源码一致；统一 slash 为跨平台一致，校验器对裸字面量出 WARN 不出 ERROR |
| 稳定选择器 | 正常 DOM | ❌ 平台 class 名会变 | ✅ `[data-chat]` / `[data-slot]` 承诺不改名（作者自写 `data-*` 会被净化删掉，自己的元素用 class/id） |
| 状态栏方案 | 雷达法/KV V4.0均可 | **动态/自创NPC：混合态雷达法**；固定字段：原生`$field`（最轻零JS）或 KV V4.0（带骨架），AI 择一 | `<script>` + SDK：`message:done` 取 `msg.content` 解析后渲染；短小可见块可纯规则替换（`$1`/`$名字`）零 JS；长期面板挂舞台 `sdk.stage`；**雷达法/onerror 引擎不可移植** |
| 全局美化 | 主题/自定义CSS | 静态换肤，或 day/night/native 三态运行时主题包（含玩家微调、route 生命周期） | 改 **14** 个 `--chat-*` 变量换肤，覆盖写 `[data-chat="root"][data-theme=*]`（特异度 (0,2,0)）才不被平台切回；订 `theme:change` 跟随深浅色；舞台承载长期面板。基座见 `assets/sandbox-kit/` |
| 事件处理 | 正常 | inline onclick 使用已验证的干净形式 `window.__fn&&__fn()` 或 `eval(getElementById('FUNC').dataset.s)`；禁代码字符串字面量与直接DOM赋值；复杂组件可动态绑定 handler；stopPropagation必加 | 顶层 `function`/`const`/`class` 自动挂 `window`，`onclick="tap()"` 直接可用（**`svg` 内的 onclick 会被删**）；气泡内按钮在 `message:mount` 里绑，回调内同步抓引用，跨异步边界不再查询气泡 DOM |
| MVU/STScript/酒馆助手 | ✅ | ❌（保守） | ❌（官方 SDK 顶替，见下行） |
| 官方 SDK / 存档 / 舞台 | ❌（走酒馆自身生态） | ❌ 无 | ✅ **30 能力 / 12 事件**；`sdk.save` 落服务端跨设备（上限由宿主动态下发，**不写死 10 key**）、`sdk.cache` 刷新即失、`sdk.stage` 舞台放长期面板 |
| 角色卡导入 | json/png | png（**仅v2**，不识别v3；jpg弃用、不能直接导入json整卡） | ❌ **不用 chara_card_v2、官方禁 PNG 整卡**；交付 = 6键正则 json + 独立 persona 文本（导入页不读 `personality`，须手工粘贴） |
| 世界书导入 | json/png | png/json/角色卡连带 | 独立 json（根对象**只留 `entries`**）；**不能**塞进导入正则 json（顶层出现 `entries`/`character_book` 等判 ERROR） |
| 世界书条目标题 | 无限制 | **≤20字**（`comment`；中文一字算1、标点计入，超出截断） | **≤20字**（同为 MMD 创卡页限制，本 skill 保留；官方校验脚本不查此项，故降级为 WARN） |

**当前MMD已实测**：`<script>` 与 ES6 解禁、`onerror` 可多行可用双引号、正则上限 130 条。`<script>` 不能做 per-message 自渲染/定位（`document.currentScript` 不可用 + 同段脚本只加载一次被去重），状态栏引擎仍只能 img onerror；这不妨碍 document-level 单例用一次性 `<script>` bootstrap，并在重复入口复用既有实例。MVU/STScript 等未确认能力仍按无处理（保守）。

**沙盒模式证据等级**：平台事实已由沙盒应用源码逆向 + 三轮真机探针复核。与官方资料冲突时按 `源码 > 隔离实测 > 官方手册 > 官方 skill`；完整真值只读 `references/platforms/mmd-sandbox.md` 与 `sandbox-foundation/资料/基座事实卡.md`。`chatVersion` **只在新建卡导入时被读取**，无法通过导入把老卡升级成新页，交付时必须书面提醒用户新建卡。

**沙盒验证默认本地优先**：日常开发先跑 `validate.py` 与本地沙盒仿真页，完成 DOM、SDK、主题、舞台、移动视口和截图回归。AI **不默认登录真实 MMD 账号**，不把正式卡或公开卡当测试夹具；真实站只保留标为 `probe-needed` 的平台边界探针与用户授权后的最终人工验收。

## 任务路由

| 用户意图 | 读取文档 |
|---|---|
| 平台技术细节/避坑 | `references/platforms/{mmd,mmd-sandbox,sillytavern}.md` |
| 沙盒模式（`chatVersion:1` 新聊天页）任何技术问题：SDK/舞台/存档/`message:mount`/6键导入 json/人设格式 | `references/platforms/mmd-sandbox.md`（该平台唯一权威；**不要**套用 mmd.md 的 onerror/雷达法那套） |
| 角色设定/性格写作 | `references/creation/character.md` |
| 世界书设计/条目规划 | `references/creation/worldbook.md` |
| 开场白 | `references/creation/opening.md` |
| 文风控制 | `references/creation/style.md` |
| 美化风格选择/风格库/换配色换主题 | **先读** `references/beautify/style-system.md`（token契约+6维度+分装+覆盖）；风格清单见 `references/beautify/style-db/README.md` |
| 状态栏 | **先分平台**。沙盒模式（`/mmdsandbox`）→ `references/beautify/sandbox-kit.md`（SBK 基座，沙盒唯一适用方案：`status` 气泡内唯一数据面板 + `chrome` 功能栏入口 + 可选 `pinned` 精简条；雷达法/影渲法/onerror 引擎不可移植）。当前MMD/本地酒馆 → 动态/自创NPC **首选** `references/beautify/statusbar-radar.md`（雷达法）或 `references/beautify/statusbar-shadowcast.md`（影渲法/ShadowCast，Shadow DOM 隔离、markdown 免疫、含双轨代谢，11靶验证+生成器）；固定字段走原生 `$field`（最轻）或 `statusbar.md`（KV V4.0），由 AI 择一 + 对应平台文档；换风格见 beautify/style-system.md |
| 全局美化 | **先分平台**。沙盒模式（`/mmdsandbox`）→ `references/beautify/sandbox-kit.md` 主题层（语义 token → 平台 **14** 个 `--chat-*`，覆盖写 `[data-chat="root"][data-theme=*]` 才不被平台深浅色切回）。当前MMD/本地酒馆 → `references/beautify/global-css.md` + 对应平台文档；先区分**静态换肤 / 当前 MMD 三态运行时主题包**。只要需要 day/night/native、玩家微调、设置或持久偏好候选，默认再读 `references/beautify/theme-runtime.md`；新资产优先见 `assets/global-beautify-examples/mmd-theme-runtime/README.md`，风格映射见 `style-system.md` |
| 悬浮组件（可拖动悬浮球/侧边栏抽屉/带菜单的悬浮按钮） | `references/beautify/floating-components.md`（light DOM 认证写法：img onerror 注入 + CSS类 + classList，菜单跟随本体+翻转避裁+选项可点击）；沙盒模式改走 `<script>` + `sdk.stage` 舞台，见 `references/platforms/mmd-sandbox.md`；**Shadow DOM 隔离变体**见 `references/beautify/statusbar-shadowcast.md`（host 挂 body + shadow 内 fixed，样式不外泄/不被染色，已验证） |
| 正则规则 | `references/beautify/regex-rules.md` |
| 角色卡JSON输出 | `references/output/card-json.md` |
| 世界书JSON输出 | `references/output/worldbook-json.md` |
| 正则产出（json/MMD导入json/手填清单） | `references/output/regex-output.md` |
| 雷达法现成示例资产 | `assets/radar-examples/`；可参考 `西幻RPG-正则与第一句话.json` 的状态栏结构。`完整美化-日夜主题与雷达.json` 是用户提供的社区快照启发的 legacy 集成参考（作者/原 URL/许可证未完整记录），虽已迁移 slash findRegex 和当前 MMD handler，但缺少 native/destroy/route 生命周期，不再推荐作全局主题基底 |
| 影渲法（ShadowCast）现成资产 | `assets/shadowcast-examples/`（状态栏+悬浮球+侧边栏成品 json、生成器 build_demo.py/build_float.py、README；改字段重新生成或直接改造成品）。**富 UI 状态栏**（RPG/养成：面包屑/资源条tooltip/XP条/属性网格/装备说明/可切页背包/敌人卡/可点选项写回输入框）用同目录 `shadowcast_core.py` 共享引擎 + `build_rpg.py`/`build_manor.py` 场景脚本（雷达法移植，12种字段类型，含 rpg/manor 两套成品 json+蓝灯世界书）。**仅当前MMD/本地酒馆，沙盒不可用** |
| **沙盒基座（SBK）现成资产** | `assets/sandbox-kit/`（**沙盒专用**）：`sbk/` 的 `base.css` + 11 个完整经典脚本模块（内核/存储/启动/主题/协议/HUD/UI/舞台）+ `build_sbk.py` 生成器 + `sbk.config.example.json` + 协议说明。改 config 跑生成器即得可导入的 6 键 JSON（自动按完整 IIFE 边界拆条）。方法论见 `references/beautify/sandbox-kit.md`。**不能用于 /mmd 与 /st**（依赖 `sdk.*` 与 `[data-chat]`，只在沙盒新页存在） |
| 交付前自检 | `references/quality/checklist.md` |

按需读取，不要一次全读。技术产出必读对应平台文档；写正文必读 creation/character.md 的写作规则节。

## 项目文件树管理

每个创作项目在用户当前工作目录下建独立文件夹：

```
项目文件夹/
├── main.md      # 实时索引：目标平台、各文件功能与状态（断点续作入口）
├── plan.md      # 任务规划：勾选框步骤清单、决策记录、进度
├── 资料/        # 用户素材、讨论记录、被否决方向存档
├── 工作/        # 制作中间文件（条目草稿、代码草稿）
│   ├── 世界书/        # 世界书源文件工作目录（仅世界书项目或含世界书组件时创建）
│   │   ├── worldbook.config.json
│   │   ├── index.md
│   │   ├── notes.md
│   │   ├── entries/
│   │   ├── drafts/
│   │   ├── patches/
│   │   └── archive/
│   └── 美化决策.md  # 仅美化项目：选用风格、混搭维度、单点覆盖（token 原值→新值+原因）的留痕
└── output/      # 最终交付物
```

规则：
- 创建任何文件后立即更新 main.md（一行：文件路径—用途—状态）
- 完成 plan.md 中一步立即打勾，不批量补记
- 新会话续作：先读 main.md 再读 plan.md，禁止跳过直接动工
- 做美化时，风格选择与每次单点覆盖都记入 `工作/美化决策.md`（无美化则不建此文件）；详见 beautify/style-system.md 的项目级制作覆盖
- 世界书项目：新增/导入/删除/移动/重命名/重排条目必须用 `scripts/worldbook_tool.py`；`output/*.json` 是 build 产物，不作为常规编辑源；修改前先读 `工作/世界书/index.md` 并用 `show`/`search` 定位 `entry_id`。

## 产出规范

| 产出物 | 本地酒馆 /st | 当前MMD /mmd | 沙盒模式 /mmdsandbox |
|---|---|---|---|
| 角色卡 | chara_card_v3 json | **chara_card_v2 json**（MMD不识别v3，见 card-json.md 第5节） | **不产 v2 卡、不产整卡 PNG**；交付 = 6键导入正则 json + 独立 persona 文本（`.txt`） |
| 世界书 | SillyTavern 世界书 json | 同左 | 独立 json，根对象只留 `entries`；不并入正则 json |
| 正则 | 正则脚本 json | MMD导入json（pageDepth/statusbar/beginning/regex_scripts四字段，见 regex-output.md）；手填清单 .md 作备选 | 导入正则 json（`chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts` **六键**）；手填清单 .md 作备选 |

当前 MMD 独立正则导入 JSON 的顶层必须恰好且仅有 `pageDepth/statusbar/beginning/regex_scripts` 四键；沙盒模式恰好且仅有上表那六键（`chatVersion` 必须为 `1`）。两者每条 `regex_scripts` 规则都必须恰好且仅有 `id/scriptName/findRegex/replaceString` 四键；沙盒模式的 `id` 必须是负数。**两个 MMD 路线的交付匹配式统一写 `/pattern/flags` slash 形态**（沙盒是约定而非硬性：实机复验裸字面量也生效，卡 64304 A/B 2026-08-30，与 worker 源码一致；统一 slash 为跨平台一致，校验器对裸字面量出 WARN）。所有 json 交付前必须语法校验：`python -m json.tool <文件> > /dev/null`；再跑 `python scripts/validate.py <文件> --platform <mmd|mmdsandbox|st>`（`--platform` 默认 `mmd`）。

沙盒模式的三件交付物、人设成对标签格式与「必须新建卡」提醒，详见 `references/platforms/mmd-sandbox.md` 第 9 节。

**整张角色卡可导出为图片**（仅 `/mmd` 与 `/st`）：当前 MMD 用 png 导入整卡（不能导入 json 整卡；**jpg 已弃用**，实测 MMD 读不出卡数据），本地酒馆 png/json 均可。交付整卡图片前用弹窗问底图来源（默认米黄底图 / 用户图），用 `scripts/make_card_image.py` 生成（只产 png），详见 output/card-json.md 第 7 节。**沙盒模式不适用**：官方禁 PNG 整卡，不要为它生成卡图。

## 整卡输出形态（末尾询问）

**仅适用 `/mmd` 与 `/st`。沙盒模式没有这个选择**——它的交付形态固定为「导入正则 json（6键）+ 独立 persona 文本 +（可选）独立世界书 json」，做完直接按此交付并附「必须新建卡、创卡页确认是新页」的提醒，不必弹窗问形态。

做整张角色卡、用户未指定输出方式时，**完成后用 AskUserQuestion 问一次输出形态**（三选一）：

| 形态 | 产出 | 说明 |
|---|---|---|
| (a) 内嵌正则的整卡 PNG | 一张 png（卡内含设定+世界书+正则） | 推荐。导入即设定/世界书/正则一次到位 |
| (b) 内嵌正则的整卡 JSON | 一份 v2 卡 json（含内嵌 regex_scripts） | MMD 不能直接导入 json 整卡，多用于本地酒馆或备份 |
| (c) 分离式 | 角色卡 + 独立正则 json + 状态栏规则.md | 卡与正则分文件，便于单独维护/复用 |

**整卡内嵌正则（a/b 形态）时的铁律**：状态栏的**生成规则**（模型侧协议：要求 AI 每轮在正文末尾输出 `<status>` 数据块）必须作为一条 constant=true（蓝灯/固定）条目放进卡内 `character_book`。内嵌的 `regex_scripts` 只负责**渲染**，没有这条规则模型不会持续输出数据块、后续轮次状态栏不更新。详见 output/card-json.md 第 8 节。

## 交互风格

- 提问用 AskUserQuestion 弹窗选项式，一次一个问题
- 关键节点（条目清单、设计方案、最终交付）必须停下让用户确认
- 做美化（状态栏/全局）前，先用弹窗问视觉风格（基调组→具体风格，或混搭），默认整套 bundle；详见 beautify/style-system.md
- 交付整张角色卡前，用弹窗问输出形态（内嵌正则 PNG / 内嵌正则 JSON / 分离式：卡+正则json+规则.md），详见《整卡输出形态》节与 output/card-json.md 第 8 节；**沙盒模式跳过此问**，按其固定三件交付物走
- /cardplanmax 模式额外允许大段开放讨论（见指令文件）
