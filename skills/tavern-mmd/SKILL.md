---
name: tavern-mmd
description: 为MMD（魅魔岛/sexyai.top，含沙盒模式新聊天页）和本地酒馆SillyTavern创建角色卡、世界书、美化（状态栏/全局美化）、同层卡（旧页原生桥接网页、新页沙盒SDK舞台网页，可选游戏与存档）。触发词：同层卡、沙盒同层卡、网页UI、new-mmd-hud、小游戏、MMD、魅魔岛、沙盒模式、沙盒、新版对话框、MMD新页、新聊天页、chatVersion、酒馆角色卡、角色卡、世界书、状态栏、全局美化、美化、正则、开场白、uni-app酒馆、在线酒馆、sexyai。支持指令 /cardplan /cardplanmax /mmd /mmdsandbox /st /worldbook /beautify /helpmmd。
---

# tavern-mmd：三平台酒馆角色卡创作

## 第一步：确定目标平台

任何技术产出（状态栏/美化/正则/含JS的内容）前必须先确定目标平台。纯文字创作（角色设定/世界书条目正文/开场白）平台无关，可不阻塞。

确定方式（优先级从高到低）：
1. 用户用过平台指令（/mmd /mmdsandbox /st）→ 已写入项目 main.md 或会话上下文
2. 项目 main.md 中已记录"目标平台"
3. 都没有 → 用 AskUserQuestion 问一次，并记录到 main.md

MMD 有两条互不通用的技术路线，问平台时必须区分：卡的 `chatVersion: 1`（官方叫「新页 / 新聊天页」，本 skill 叫「沙盒模式」）走 `/mmdsandbox`，`chatVersion: 0`/缺省走 `/mmd`。选错产出静默失效（脚本装上但 SDK 全不在，页面无报错）。

**同层卡也必须分新旧页，不能默认旧页。** 同层卡是呈现形态，不是平台：旧版用独立 iframe + Host 原生桥接，沙盒用官方 SDK + `sdk.stage` 自绘完整网页。用户已指定 `/mmdsandbox` 时直接进入沙盒同层指南；仅有“同层卡”且无平台记录才问。HTML `iframe sandbox` 属性不代表 MMD 沙盒模式。

## 平台差异矩阵（所有技术分流的依据）

| 能力 | 本地酒馆 /st | 当前MMD /mmd | 沙盒模式 /mmdsandbox |
|---|---|---|---|
| `<script>` 标签 | ✅ | ✅ 可执行；**per-message 自渲染/定位不可用**，逐消息状态栏仍走 img onerror；同层卡走文档级单例；document-level 一次性 bootstrap 与全局 handler 定义可用 | ✅ **一等公民**：装卡即抽出（不需被匹配命中）、**整卡只跑一次**；per-message 绑定由 `sdk.on('message:mount')` 顶替；**`img onerror` 点火器被官方明令禁止** |
| ES6+ 语法 | ✅ | ✅ 实测全支持（img onerror 载体下，7/7 语法探针全绿），**推荐 ES6** | ✅ 实机与官方示例均确认 |
| 正则导入方式 | json 直接导入 | json导入（MMD专用4字段格式）或UI手填 | 创卡页「导入正则」json（**6键格式**，多 `chatVersion`/`personality`）、UI手填，或**内嵌进 v2 整卡**（`data.extensions.regex_scripts`） |
| 正则限额 | 无硬限制 | ≤130条；findRegex≤1000字符；replaceString≤20000字符 | ≤130条；保守交付按 scriptName≤20 / findRegex≤1000 / replaceString≤20000。源码可见归一常量为 200 / 4096 / 100000；只有 replaceString 的编辑器 20000／导入 100000 双路径已确证，scriptName/findRegex 的双路径与超限语义仍待验证；另 statusbar 200 / **beginning 4000** / personality 10000 |
| `findRegex` 形态 | 任意正则 | **强制 `/pattern/flags` slash literal**，固定标记也要包斜杠 | **交付统一 `/pattern/flags` slash 形态**（约定，非硬性）：实机复验裸字面量也生效（卡 64304 A/B，2026-08-30），与 worker 源码一致；统一 slash 为跨平台一致，校验器对裸字面量出 WARN 不出 ERROR |
| 稳定选择器 | 正常 DOM | ❌ 平台 class 名会变 | ✅ `[data-chat]` / `[data-slot]` 承诺不改名（作者自写 `data-*` 会被净化删掉，自己的元素用 class/id） |
| 状态栏方案 | 雷达法/KV V4.0均可 | **动态/自创NPC：混合态雷达法**；固定字段：原生`$field`（最轻零JS）或 KV V4.0（带骨架），AI 择一 | `<script>` + SDK：`message:done` 取 `msg.content` 解析后渲染；短小可见块可纯规则替换（`$1`/`$名字`）零 JS；长期面板挂舞台 `sdk.stage`；**雷达法/onerror 引擎不可移植** |
| 全局美化 | 主题/自定义CSS | 静态换肤，或 day/night/native 三态运行时主题包（含玩家微调、route 生命周期） | 沙盒阅读主题覆盖 **29** 个 `--chat-*` 颜色变量，跟随 `theme:change`；宿主弹窗另用 **21 个 `[data-host]` 根**的静态 `<style>` 抽取过滤通道，不是跨源 DOM 接口。SBK 的制作期 `hostStyles` 与运行时阅读主题开关分开；见宿主指南 |
| 事件处理 | 正常 | inline onclick 使用已验证的干净形式 `window.__fn&&__fn()` 或 `eval(getElementById('FUNC').dataset.s)`；禁代码字符串字面量与直接DOM赋值；复杂组件可动态绑定 handler；stopPropagation必加 | 顶层 `function`/`const`/`class` 自动挂 `window`，`onclick="tap()"` 直接可用（**`svg` 内的 onclick 会被删**）；气泡内按钮在 `message:mount` 里绑，回调内同步抓引用，跨异步边界不再查询气泡 DOM |
| MVU/STScript/酒馆助手 | ✅ | ❌（保守） | ❌（官方 SDK 顶替，见下行） |
| 官方 SDK / 存档 / 舞台 | ❌（走酒馆自身生态） | ❌ 无 | ✅ **30 能力 / 12 事件 / 7 公开错误码**；`sdk.save` 用版本化对象合并保存，文档 10 key 与历史源码差异需按目标版本验收，不承诺无限额；`sdk.cache` 当场缓存、`sdk.stage` 长期面板 |
| 同层卡 / 完整自绘网页 | 按酒馆自身生态 | 独立 Frame + Host 原生桥接；旧页四键正则包；`assets/same-layer-kit/` | 官方 SDK 薄适配 + `sdk.stage` 的 content/full 模式；新页六键正则包；制作见 `references/creation/sandbox-same-layer-card.md`，不继承旧页桥接动作表 |
| 平台状态变量（`sdk.vars`/`vars:change`/`<abc_vars>`） | ❌（走 MVU 等酒馆生态） | ❌ 无 | ⚠️ 业务规则沿用项目资料：仅新页可开、最多 6 层 80 键、快照随消息存并按楼层回溯、`{{var}}` 只替换本轮新组装内容、分享页与瘦预览可读不可写。但 **2026-09-05 网页核对与本轮资料未提供完整运行契约**；不得推测签名、返回值或导入字段，也不据此声称平台不支持。现阶段状态栏按已确认的 AI 正文协议解析；数据来源见 mmd-sandbox.md §14 |
| 角色卡导入 | json/png | png（**仅v2**，不识别v3；jpg弃用、不能直接导入json整卡） | ✅ **可导 v2 PNG 整卡**：编辑页导入按新卡处理，首次保存前选新版。JSON 整卡直接导入记录冲突、待复验（见 card-json.md 文首），当前作源码/备份；也可走 6键正则 json + 独立 persona 文本 |
| 世界书导入 | json/png | png/json/角色卡连带 | png/json/角色卡连带（创卡页原文：「可导入PNG或json格式世界书」）；**唯一限制**是不能塞进 6键导入正则 json（那份顶层出现 `entries`/`character_book` 等判 ERROR），走整卡时正常放 `character_book` |
| 世界书条目标题 | 无限制 | **≤20字**（`comment`；中文一字算1、标点计入，超出截断） | **≤20字**（同为 MMD 创卡页限制，本 skill 保留；官方校验脚本不查此项，故降级为 WARN） |

**当前MMD已实测**：`<script>` 与 ES6 解禁、`onerror` 可多行可用双引号、正则上限 130 条。`<script>` 不能做 per-message 自渲染/定位（`document.currentScript` 不可用 + 同段脚本只加载一次被去重），逐消息状态栏引擎仍用 img onerror；独立同层卡使用文档级单例与 iframe；这不妨碍 document-level 单例用一次性 `<script>` bootstrap，并在重复入口复用既有实例。MVU/STScript 等未确认能力仍按无处理（保守）。

**沙盒模式证据规则**：先核对版本、日期与运行环境，再比较同一范围内的源码、实测和文档。2026-08/09 历史探针保留；2026-09-05 网页核对记录补充 BUSY 与已揭示累计流式语义，本轮 37 页手册补充 21 个宿主根。旧 ready/save.remove/配额/外链冲突按日期限定并待目标版本复验，不能用旧实现绝对否定新文档，也不能将本地模拟标为新实测。来源汇总见 `references/platforms/mmd-sandbox.md` 和 `references/beautify/sandbox-host-styles.md`。`chatVersion` 的既有导入记录要求新建卡，交付仍提醒「新建卡 + 首次保存前选择新版」。

**沙盒验证默认本地优先**：日常开发先跑 `validate.py` 与本地沙盒仿真页，完成 DOM、SDK、主题、舞台、移动视口和截图回归。AI **不默认登录真实 MMD 账号**，不把正式卡或公开卡当测试夹具；真实站只保留标为 `probe-needed` 的平台边界探针与用户授权后的最终人工验收。

## 任务路由

| 用户意图 | 读取文档 |
|---|---|
| 平台技术细节/避坑 | `references/platforms/{mmd,mmd-sandbox,sillytavern}.md` |
| 沙盒模式（`chatVersion:1` 新聊天页）任何技术问题：SDK/舞台/存档/`message:mount`/6键导入 json/人设格式 | `references/platforms/mmd-sandbox.md`（该平台分层来源汇总；按日期/环境读取，**不要**套用 mmd.md 的 onerror/雷达法） |
| **已选新页**的平台状态变量 / 好感度 / 背包 / 养成 / 地图持久化「数据放哪」 | `references/platforms/mmd-sandbox.md` §14（三来源分工：平台状态变量 vs `sdk.save` vs `sdk.cache`；`<abc_vars>` 不可碰；契约未补齐的边界）。**动手写界面前先定数据来源**，别让同一个剧情数值有两份真值 |
| 新页公开发布门槛（要过审核的卡） | `references/platforms/mmd-sandbox.md` §10.3（固定传输 2000–15000、`beginning` ≥200）。私人自用卡与纯草稿不受此约束 |
| 角色设定/性格写作 | `references/creation/character.md` |
| 世界书设计/条目规划 | `references/creation/worldbook.md` |
| 开场白 | `references/creation/opening.md` |
| 文风控制 | `references/creation/style.md` |
| 美化风格选择/风格库/换配色换主题 | **先读** `references/beautify/style-system.md`（token契约+6维度+分装+覆盖）；风格清单见 `references/beautify/style-db/README.md` |
| **同层卡 / 独立网页UI / 替换聊天界面 / 网页小游戏** | **先按已选平台分流**：旧页 `/mmd` → `references/creation/same-layer-card.md` + `references/runtime/mmd-native-bridge.md` + `assets/same-layer-kit/README.md`；沙盒 `/mmdsandbox` → `references/creation/sandbox-same-layer-card.md` + `references/platforms/mmd-sandbox.md`。无平台记录先问，数据/背包/地图需求不可自动改平台。游戏引擎均可选；旧页私有后端实验另见 `references/runtime/mmd-backend-host.md` |
| **沙盒同层卡 / 新页完整网页 / new-mmd-hud / 贪心鬼新版 HUD** | `references/creation/sandbox-same-layer-card.md`。分析或迁移该上游再读 `references/runtime/new-mmd-hud-audit.md`；借鉴网页分层，SDK 合同以平台资料为准，不能原样搬 Mock、四键导出器或旧页 bridge。当前为制作方法，尚无新页同层专用成品基座/一键构建器 |
| **同层卡预览 / 审核 / MMD 原生页联动** | **旧页专用**：`references/creation/same-layer-review.md`，用 `scripts/review_same_layer.py` 构建、校验、联动预览与报告。**沙盒同层**：`references/creation/sandbox-same-layer-card.md` §8，使用新页全景 chat/thin 仿真并补项目测试；不调用旧页专用审核器。均测试原样发布载荷，真实平台与实体手机证据另列 |
| **旧版同层卡中的模型列表/模型切换/模型设置/原生功能可用范围** | **仅 `/mmd`**：`references/runtime/mmd-model-controls.md` + `references/runtime/mmd-native-capabilities.md`。模型组默认随卡打包启动，可用 `--no-models` 关闭；固定上游 61 项已实现动作、6 项仅定义不可用。界面见 `references/creation/same-layer-dialogue.md`。沙盒不继承这份能力表，改读沙盒同层指南 §3 |
| **旧版同层卡原生动作：消息编辑/删除/回溯、会话管理、人设、补充设定、指令、导航与原生面板** | **仅 `/mmd`**：`references/runtime/mmd-action-modules.md` + `references/runtime/mmd-native-capabilities.md`；现成 UI 见 `references/creation/same-layer-dialogue.md`。参数、revision 与确认阶段按合同处理，真实平台另验。沙盒按官方 SDK 映射，未开放动作返回原生界面 |
| 状态栏 | **先分平台**。沙盒模式（`/mmdsandbox`）→ `references/beautify/sandbox-kit.md`（SBK 基座，沙盒唯一适用方案：`status` 气泡内唯一数据面板 + `chrome` 功能栏入口 + 可选 `pinned` 精简条；雷达法/影渲法/onerror 引擎不可移植）。当前MMD/本地酒馆 → 动态/自创NPC **首选** `references/beautify/statusbar-radar.md`（雷达法）或 `references/beautify/statusbar-shadowcast.md`（影渲法/ShadowCast，Shadow DOM 隔离、markdown 免疫、含双轨代谢，11靶验证+生成器）；固定字段走原生 `$field`（最轻）或 `statusbar.md`（KV V4.0），由 AI 择一 + 对应平台文档；换风格见 beautify/style-system.md |
| 全局美化 | **先分平台**。沙盒模式（`/mmdsandbox`）→ `references/beautify/sandbox-kit.md` 主题层（语义 token → 平台 **29** 个 `--chat-*`，覆盖写 `[data-chat="root"][data-theme=*]` 才不被平台深浅色切回）。当前MMD/本地酒馆 → `references/beautify/global-css.md` + 对应平台文档；先区分**静态换肤 / 当前 MMD 三态运行时主题包**。只要需要 day/night/native、玩家微调、设置或持久偏好候选，默认再读 `references/beautify/theme-runtime.md`；新资产优先见 `assets/global-beautify-examples/mmd-theme-runtime/README.md`，风格映射见 `style-system.md` |
| **新页宿主弹窗换肤 / data-host / 模型设置 / 总结与确认层** | `references/beautify/sandbox-host-styles.md`：21 根（19 + summary + summary-confirm）、静态 CSS 抽取过滤、排除区、summary 根内编辑/锚点与树外确认。SBK 可选 `hostStyles:["path.css"]` 独立静态输出；停用运行时阅读主题不撤销宿主皮肤。chat 外层预览为保守近似，thin 不模拟宿主；不能推测动态转发、宿主 DOM 或新 SDK |
| 悬浮组件（可拖动悬浮球/侧边栏抽屉/带菜单的悬浮按钮） | `references/beautify/floating-components.md`（light DOM 认证写法：img onerror 注入 + CSS类 + classList，菜单跟随本体+翻转避裁+选项可点击）；沙盒模式改走 `<script>` + `sdk.stage` 舞台，见 `references/platforms/mmd-sandbox.md`；**Shadow DOM 隔离变体**见 `references/beautify/statusbar-shadowcast.md`（host 挂 body + shadow 内 fixed，样式不外泄/不被染色，已验证） |
| 正则规则 | `references/beautify/regex-rules.md` |
| 角色卡JSON输出 | `references/output/card-json.md` |
| 世界书JSON输出 | `references/output/worldbook-json.md` |
| 正则产出（json/MMD导入json/手填清单） | `references/output/regex-output.md` |
| 雷达法现成示例资产 | `assets/radar-examples/`；可参考 `西幻RPG-正则与第一句话.json` 的状态栏结构。`完整美化-日夜主题与雷达.json` 是用户提供的社区快照启发的 legacy 集成参考（作者/原 URL/许可证未完整记录），虽已迁移 slash findRegex 和当前 MMD handler，但缺少 native/destroy/route 生命周期，不再推荐作全局主题基底 |
| 影渲法（ShadowCast）现成资产 | `assets/shadowcast-examples/`（状态栏+悬浮球+侧边栏成品 json、生成器 build_demo.py/build_float.py、README；改字段重新生成或直接改造成品）。**富 UI 状态栏**（RPG/养成：面包屑/资源条tooltip/XP条/属性网格/装备说明/可切页背包/敌人卡/可点选项写回输入框）用同目录 `shadowcast_core.py` 共享引擎 + `build_rpg.py`/`build_manor.py` 场景脚本（雷达法移植，12种字段类型，含 rpg/manor 两套成品 json+蓝灯世界书）。**仅当前MMD/本地酒馆，沙盒不可用** |
| **沙盒基座（SBK）现成资产** | `assets/sandbox-kit/`（**沙盒专用**）：`sbk/` 的 `base.css` + 11 个完整经典脚本模块（内核/存储/启动/主题/协议/HUD/UI/舞台）+ `build_sbk.py` 生成器 + `sbk.config.example.json` + 协议说明。改 config 跑生成器即得可导入的 6 键 JSON（自动按完整 IIFE 边界拆条）。方法论见 `references/beautify/sandbox-kit.md`。**不能用于 /mmd 与 /st**（依赖 `sdk.*` 与 `[data-chat]`，只在沙盒新页存在） |
| 交付前自检 | `references/quality/checklist.md` |

**同层卡先于普通状态栏分流，再按平台选制作路线。** 在 main.md 记录「目标平台 / chatVersion / 呈现形态 / 连接方式 / 状态权威 / 存档位置 / 验证层级」。旧页用 Frame + 原生桥接，持久化按可靠作用域选 Host 本地存档；沙盒用 SDK + 舞台，持久进度按平台合同选 `sdk.save`。只需聊天网页时不加载引擎；需要游戏时 AI 仅叙述已结算事实。不要把 SBK 状态栏模板当完整同层聊天页，也不要把旧页 61 项能力当沙盒 SDK 已支持。

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
| 角色卡 | chara_card_v3 json | **chara_card_v2 json**（MMD不识别v3，见 card-json.md 第5节） | **chara_card_v2 json / 整卡 PNG**（同当前MMD，见 card-json.md 第5节）；或分离式的 6键导入正则 json + 独立 persona 文本（`.txt`） |
| 世界书 | SillyTavern 世界书 json | 同左 | 同左；走整卡时并入卡内 `character_book`，走分离式时独立 json（根对象只留 `entries`）。**只是不能塞进 6键正则 json** |
| 正则 | 正则脚本 json | MMD导入json（pageDepth/statusbar/beginning/regex_scripts四字段，见 regex-output.md）；手填清单 .md 作备选 | 导入正则 json（`chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts` **六键**）；手填清单 .md 作备选 |

当前 MMD 独立正则导入 JSON 的顶层必须恰好且仅有 `pageDepth/statusbar/beginning/regex_scripts` 四键；沙盒模式恰好且仅有上表那六键（`chatVersion` 必须为 `1`）。两者每条 `regex_scripts` 规则都必须恰好且仅有 `id/scriptName/findRegex/replaceString` 四键；当前 MMD 规则 `id` 固定 `-1`，沙盒模式的 `id` 必须是负数。时间戳用于父文档 HTML 元素 ID，不用于规则 `id`。**两个 MMD 路线的交付匹配式统一写 `/pattern/flags` slash 形态**（沙盒是约定而非硬性：实机复验裸字面量也生效，卡 64304 A/B 2026-08-30，与 worker 源码一致；统一 slash 为跨平台一致，校验器对裸字面量出 WARN）。所有 json 交付前必须语法校验：`python -m json.tool <文件> > /dev/null`；再跑 `python scripts/validate.py <文件> --platform <mmd|mmdsandbox|st>`（`--platform` 默认 `mmd`）。

沙盒模式的交付形态、人设成对标签格式与「必须新建卡 + 首次保存前选新版聊天页」提醒，详见 `references/platforms/mmd-sandbox.md` 第 9 节。

**整张角色卡可导出为图片**（`/mmd`、`/st`、`/mmdsandbox` 三平台均可）：MMD 系默认用 v2 PNG 导入整卡（旧页不能直接导 JSON；沙盒 JSON 直接导入记录冲突、待复验；**jpg 已弃用**），本地酒馆 png/json 均可。交付整卡图片前用弹窗问底图来源（默认米黄底图 / 用户图），用 `scripts/make_card_image.py` 生成（只产 png），详见 output/card-json.md 第 7 节。沙盒导入后**首次保存前必须在创卡页选「使用新版」聊天页**（见下节铁律）。

## 整卡输出形态（末尾询问）

**三个平台都有这个选择**（`/mmd`、`/st`、`/mmdsandbox`）。沙盒模式此前被写成「固定三件交付物、不问形态」，那是基于「官方禁 PNG 整卡」的错误前提，已更正。

做整张角色卡、用户未指定输出方式时，**完成后用 AskUserQuestion 问一次输出形态**（三选一）：

| 形态 | 产出 | 说明 |
|---|---|---|
| (a) 内嵌正则的整卡 PNG | 一张 png（卡内含设定+世界书+正则） | 推荐。导入即设定/世界书/正则一次到位 |
| (b) 内嵌正则的整卡 JSON | 一份 v2 卡 json（含内嵌 regex_scripts） | 旧 MMD 不能直接导入，沙盒直接导入待复验；当前作源码/备份，本地酒馆可用 |
| (c) 分离式 | 角色卡 + 独立正则 json + 状态栏规则.md | 卡与正则分文件，便于单独维护/复用。沙盒的正则 json 走 6 键格式 |

**沙盒模式（`/mmdsandbox`）附加铁律**：整卡路线要在交付说明里写明「①导入必须走**新建卡**（编辑页导入 v2 卡按新卡处理）；②**首次保存前**在创卡页把「新版聊天页」选成**使用新版**，该选择**首次保存后永久不可改**」。漏了第②步，卡能进但 `sdk.*`/`[data-chat]`/舞台全不在，页面无任何报错。走分离式（c）时，6 键正则 json 里的 `chatVersion: 1` 只在新建卡导入时被读取，同样要提醒。

**整卡内嵌正则（a/b 形态）且由 AI 正文提供状态时**：状态栏的**生成规则**（模型侧协议：要求 AI 每轮在正文末尾输出 `<status>` 数据块）必须作为一条 constant=true（蓝灯/固定）条目放进卡内 `character_book`。内嵌的 `regex_scripts` 只负责**渲染**，没有这条规则模型不会持续输出数据块、后续轮次状态栏不更新。详见 output/card-json.md 第 8 节。同层卡若由确定规则引擎维护数值，世界书只声明规则边界与叙述要求，不能再要求 AI 生成同一组权威数值；纯聊天 UI 不凭空新增状态协议。

## 交互风格

- 提问用 AskUserQuestion 弹窗选项式，一次一个问题
- 关键节点（条目清单、设计方案、最终交付）必须停下让用户确认
- 做美化（状态栏/全局）前，先用弹窗问视觉风格（基调组→具体风格，或混搭），默认整套 bundle；详见 beautify/style-system.md
- 交付整张角色卡前，用弹窗问输出形态（内嵌正则 PNG / 内嵌正则 JSON / 分离式：卡+正则json+规则.md），详见《整卡输出形态》节与 output/card-json.md 第 8 节；**沙盒模式同样要问**（它能导 v2 整卡），只是要额外提醒「新建卡 + 首次保存前选新版聊天页」
- /cardplanmax 模式额外允许大段开放讨论（见指令文件）
