---
name: tavern-mmd
description: 为MMD（魅魔岛/sexyai.top）和本地酒馆SillyTavern创建角色卡、世界书、美化（状态栏/全局美化）。触发词：MMD、魅魔岛、酒馆角色卡、角色卡、世界书、状态栏、全局美化、美化、正则、开场白、uni-app酒馆、在线酒馆、sexyai。支持指令 /cardplan /cardplanmax /mmd /oldmmd /st /worldbook /beautify /helpmmd。
---

# tavern-mmd：三平台酒馆角色卡创作

## 第一步：确定目标平台

任何技术产出（状态栏/美化/正则/含JS的内容）前必须先确定目标平台。纯文字创作（角色设定/世界书条目正文/开场白）平台无关，可不阻塞。

确定方式（优先级从高到低）：
1. 用户用过平台指令（/mmd /oldmmd /st）→ 已写入项目 main.md 或会话上下文
2. 项目 main.md 中已记录"目标平台"
3. 都没有 → 用 AskUserQuestion 问一次，并记录到 main.md

## 平台差异矩阵（所有技术分流的依据）

| 能力 | 本地酒馆 /st | 当前MMD /mmd | 旧版MMD /oldmmd |
|---|---|---|---|
| `<script>` 标签 | ✅ | ✅ 可执行，但**做不了 per-message 自渲染**（仅用于定义 `window.__fn` 给 onclick 调）→ 状态栏引擎仍走 img onerror | ❌ → img onerror 点火器 |
| ES6+ 语法 | ✅ | ✅ 实测全支持（img onerror 载体下，7/7 语法探针全绿），**推荐 ES6** | ❌ ES5 only |
| 正则导入方式 | json 直接导入 | json导入（MMD专用4字段格式）或UI手填 | 同当前MMD |
| 正则限额 | 无硬限制 | ≤130条；findRegex≤1000字符；replaceString≤20000字符 | ≤130条；同当前MMD |
| 状态栏方案 | 雷达法/KV V4.0均可 | **动态/自创NPC：混合态雷达法**；固定字段：原生`$field`（最轻零JS）或 KV V4.0（带骨架），AI 择一 | 同当前MMD |
| 全局美化 | 主题/自定义CSS | 正则包裹+uni-app类名覆盖+`!important`+body开关类（激活器可用script或img onerror） | 同当前MMD |
| 事件处理 | 正常 | onclick仅放行"干净调用/引用表达式"（`__fn()`、`eval(x.dataset.s)`）；禁代码字符串字面量与直接DOM赋值；stopPropagation必加；时间戳ID | 同当前MMD（旧版略宽：曾放行极简单行赋值，当前版收紧） |
| MVU/STScript/酒馆助手 | ✅ | ❌（保守） | ❌ |
| 角色卡导入 | json/png | png（**仅v2**，不识别v3；jpg弃用、不能直接导入json整卡） | 同当前MMD |
| 世界书导入 | json/png | png/json/角色卡连带 | 同当前MMD |

**当前MMD已实测**：`<script>` 与 ES6 解禁、`onerror` 可多行可用双引号、正则上限 130 条。`<script>` 不能做 per-message 自渲染（`document.currentScript` 不可用 + 同段脚本只加载一次被去重），状态栏引擎仍只能 img onerror。MVU/STScript 等未确认能力仍按无处理（保守）。

## 任务路由

| 用户意图 | 读取文档 |
|---|---|
| 平台技术细节/避坑 | `references/platforms/{mmd,mmd-old,sillytavern}.md` |
| 角色设定/性格写作 | `references/creation/character.md` |
| 世界书设计/条目规划 | `references/creation/worldbook.md` |
| 开场白 | `references/creation/opening.md` |
| 文风控制 | `references/creation/style.md` |
| 美化风格选择/风格库/换配色换主题 | **先读** `references/beautify/style-system.md`（token契约+6维度+分装+覆盖）；风格清单见 `references/beautify/style-db/README.md` |
| 状态栏 | 动态/自创NPC **首选** `references/beautify/statusbar-radar.md`（雷达法）或 `references/beautify/statusbar-shadowcast.md`（影渲法/ShadowCast，Shadow DOM 隔离、markdown 免疫、含双轨代谢，11靶验证+生成器）；固定字段走原生 `$field`（最轻）或 `statusbar.md`（KV V4.0），由 AI 择一 + 对应平台文档；换风格见 beautify/style-system.md |
| 全局美化 | `references/beautify/global-css.md` + 对应平台文档；换风格见 beautify/style-system.md |
| 悬浮组件（可拖动悬浮球/侧边栏抽屉/带菜单的悬浮按钮） | `references/beautify/floating-components.md`（light DOM 认证写法：img onerror 注入 + CSS类 + classList，菜单跟随本体+翻转避裁+选项可点击；两版分流）；**Shadow DOM 隔离变体**见 `references/beautify/statusbar-shadowcast.md`（host 挂 body + shadow 内 fixed，样式不外泄/不被染色，已验证） |
| 正则规则 | `references/beautify/regex-rules.md` |
| 角色卡JSON输出 | `references/output/card-json.md` |
| 世界书JSON输出 | `references/output/worldbook-json.md` |
| 正则产出（json/MMD导入json/手填清单） | `references/output/regex-output.md` |
| 雷达法现成示例资产 | `assets/radar-examples/`（西幻RPG状态栏、日夜主题全局美化集成案例） |
| 影渲法（ShadowCast）现成资产 | `assets/shadowcast-examples/`（状态栏+悬浮球+侧边栏成品 json、生成器 build_demo.py/build_float.py、README；改字段重新生成或直接改造成品） |
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
│   └── 美化决策.md  # 仅美化项目：选用风格、混搭维度、单点覆盖（token 原值→新值+原因）的留痕
└── output/      # 最终交付物
```

规则：
- 创建任何文件后立即更新 main.md（一行：文件路径—用途—状态）
- 完成 plan.md 中一步立即打勾，不批量补记
- 新会话续作：先读 main.md 再读 plan.md，禁止跳过直接动工
- 做美化时，风格选择与每次单点覆盖都记入 `工作/美化决策.md`（无美化则不建此文件）；详见 beautify/style-system.md 第5节

## 产出规范

| 产出物 | 本地酒馆 | MMD（新旧同） |
|---|---|---|
| 角色卡 | chara_card_v3 json | **chara_card_v2 json**（MMD不识别v3，见 card-json.md 第5节） |
| 世界书 | SillyTavern 世界书 json | 同左 |
| 正则 | 正则脚本 json | MMD导入json（pageDepth/statusbar/beginning/regex_scripts四字段，见 regex-output.md）；手填清单 .md 作备选 |

所有 json 交付前必须语法校验：`python -m json.tool <文件> > /dev/null`。

**整张角色卡可导出为图片**：MMD 用 png 导入整卡（不能导入 json 整卡；**jpg 已弃用**，实测 MMD 读不出卡数据），本地酒馆 png/json 均可。交付整卡图片前用弹窗问底图来源（默认米黄底图 / 用户图），用 `scripts/make_card_image.py` 生成（只产 png），详见 output/card-json.md 第 7 节。

## 整卡输出形态（末尾询问）

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
- 交付整张角色卡前，用弹窗问输出形态（内嵌正则 PNG / 内嵌正则 JSON / 分离式：卡+正则json+规则.md），详见《整卡输出形态》节与 output/card-json.md 第 8 节
- /cardplanmax 模式额外允许大段开放讨论（见指令文件）
