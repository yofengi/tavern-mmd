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

| 能力 | 本地酒馆 /st | 旧版MMD /oldmmd | 当前MMD /mmd |
|---|---|---|---|
| `<script>` 标签 | ✅ | ❌ → img onerror 点火器 | ✅（待验证） |
| ES6+ 语法 | ✅ | ❌ ES5 only | 保守用 ES5（待验证） |
| 正则导入方式 | json 直接导入 | json导入（MMD专用4字段格式）或UI手填 | 同旧版 |
| 正则限额 | 无硬限制 | ≤30条；findRegex≤1000字符；replaceString≤20000字符 | 同旧版 |
| 状态栏方案 | 雷达法/KV V4.0均可 | **首选混合态雷达法**；KV V4.0轻量备选 | 同旧版 |
| 全局美化 | 主题/自定义CSS | 正则包裹+uni-app类名覆盖+`!important`+body开关类 | 同旧版 |
| 事件处理 | 正常 | onclick仅极简单行；stopPropagation必加；时间戳ID | 同旧版（待验证） |
| MVU/STScript/酒馆助手 | ✅ | ❌ | ❌（保守） |
| 角色卡导入 | json/png | png/jpg/json（**仅v2**，不识别v3） | png/jpg/json（**仅v2**，不识别v3） |
| 世界书导入 | json/png | png/json/角色卡连带 | png/json/角色卡连带 |

**保守原则**：当前MMD仅确认解禁`<Script>`，其余按旧版处理，标注"待验证"。

## 任务路由

| 用户意图 | 读取文档 |
|---|---|
| 平台技术细节/避坑 | `references/platforms/{mmd,mmd-old,sillytavern}.md` |
| 角色设定/性格写作 | `references/creation/character.md` |
| 世界书设计/条目规划 | `references/creation/worldbook.md` |
| 开场白 | `references/creation/opening.md` |
| 文风控制 | `references/creation/style.md` |
| 状态栏 | **首选** `references/beautify/statusbar-radar.md`（雷达法）；轻量备选 `statusbar.md`（KV V4.0）+ 对应平台文档 |
| 全局美化 | `references/beautify/global-css.md` + 对应平台文档 |
| 正则规则 | `references/beautify/regex-rules.md` |
| 角色卡JSON输出 | `references/output/card-json.md` |
| 世界书JSON输出 | `references/output/worldbook-json.md` |
| 正则产出（json/MMD导入json/手填清单） | `references/output/regex-output.md` |
| 雷达法现成示例资产 | `assets/radar-examples/`（西幻RPG状态栏、日夜主题全局美化集成案例） |
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
└── output/      # 最终交付物
```

规则：
- 创建任何文件后立即更新 main.md（一行：文件路径—用途—状态）
- 完成 plan.md 中一步立即打勾，不批量补记
- 新会话续作：先读 main.md 再读 plan.md，禁止跳过直接动工

## 产出规范

| 产出物 | 本地酒馆 | MMD（新旧同） |
|---|---|---|
| 角色卡 | chara_card_v3 json | **chara_card_v2 json**（MMD不识别v3，见 card-json.md 第5节） |
| 世界书 | SillyTavern 世界书 json | 同左 |
| 正则 | 正则脚本 json | MMD导入json（pageDepth/statusbar/beginning/regex_scripts四字段，见 regex-output.md）；手填清单 .md 作备选 |

所有 json 交付前必须语法校验：`python -m json.tool <文件> > /dev/null`。

## 交互风格

- 提问用 AskUserQuestion 弹窗选项式，一次一个问题
- 关键节点（条目清单、设计方案、最终交付）必须停下让用户确认
- /cardplanmax 模式额外允许大段开放讨论（见指令文件）
