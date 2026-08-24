# 世界书设计

## 工作流程（索引源文件驱动）

阶段一 规划：判断卡型 → 初始化 `工作/世界书/` → 规划层级与条目清单 → 用户确认后才动工。
阶段二 入库：使用 `scripts/worldbook_tool.py add` 创建正式条目源文件；条目正文写在 `工作/世界书/entries/`，未确认内容先放 `drafts/`，层级与条目规划写入 `notes.md`/`plan.md`。
阶段三 展开：主代理/子代理先读 `工作/世界书/index.md` 定位 `entry_id`，再用 `show`/`search` 读取完整条目，只编辑目标源文件。
阶段四 导出：运行 `build` 生成 `output/*.json`，运行 `check` 与 `validate.py` 审核后交付。

**核心原则**：工作层稳定的是 `entry_id` 与源文件；导出层的 `uid`/`order` 是 build 产物，可以随移动和重排改变。禁止把 output JSON 当作常规编辑源。

## 卡型判断与蓝绿灯策略
| 类型 | 判定 | 策略 |
|---|---|---|
| 单角色卡 | 1个核心角色（拆分条目不算多角色） | 该角色所有条目蓝灯常驻 |
| 多角色卡 | ≥2核心角色 | 角色速览蓝灯 + 各角色详情绿灯（keys=全名,昵称,外号） |

## 条目规划表模板（给用户确认用）
| 层级 | 条目 | position | 蓝/绿灯 | keys | 说明 |
|---|---|---|---|---|---|
| 世界设定层 | 世界观总纲 | 0 ↑Char | 蓝 | - | 始终存在 |
| 角色层 | 角色速览 | 0 ↑Char | 蓝 | - | 多角色卡必写 |
| 角色层 | 角色设定（每角色一条） | 1 ↓Char | 视卡型 | 角色名 | `<character>`结构 |
| 角色层 | 性格（每角色一条） | 1 ↓Char | 视卡型 | 同上 | `<personality>`独立 |
| 场景物品事件层 | 物品/能力/场景/事件 | 1 ↓Char | 绿 | 名称关键词 | 用到才触发 |
| 角色层 | NPC | 1 ↓Char | 绿 | NPC名 | 支线/背景 NPC |
| 文风约束层 | 文风指导 | 2 ↑AT（MMD平台用蓝灯↓Char） | 蓝 | - | 见style.md |

> 规划阶段先确认层级和条目清单，不需要提前固定最终 `uid`/`order`。导出顺序由 `worldbook_tool.py build` 根据层级顺序与文件顺序生成。

## 世界书工作目录

```text
工作/世界书/
├── worldbook.config.json
├── index.md
├── notes.md
├── entries/
├── drafts/
├── patches/
└── archive/
```

- `index.md`：导航索引，记录 `entry_id`、当前导出 uid/order、层级、文件、标题、灯色、keys、摘要、状态。由脚本维护，AI 只读不手改结构字段。
- `notes.md`：世界书设计约束、用户确认过的决策、人读变更记录。
- `entries/`：正式条目源文件，一条一文件，参与 build。
- `drafts/`：未确认草稿，不参与 build。
- `patches/`：脚本生成的 add/move/rename/delete/build 操作日志。
- `archive/`：删除默认归档，不参与 build。

结构操作统一调用：

```bash
python <skill>/scripts/worldbook_tool.py init "工作/世界书"
python <skill>/scripts/worldbook_tool.py add "工作/世界书" --layer "30-角色层" --title "角色：莉娅" --keys "莉娅,Lia" --constant true
python <skill>/scripts/worldbook_tool.py import "工作/世界书" "output/原世界书.json" --layer "40-场景物品事件层"
python <skill>/scripts/worldbook_tool.py reorder "工作/世界书" --entry e0001 --prefix 5
python <skill>/scripts/worldbook_tool.py search "工作/世界书" fuzzy "魔法反噬" --limit 5
python <skill>/scripts/worldbook_tool.py build "工作/世界书" --out "output/世界书.json"
python <skill>/scripts/worldbook_tool.py check "工作/世界书" --out "output/世界书.json"
```

### 导入既有世界书的分工

导入既有世界书 JSON 时，不由主代理或子代理手工重建索引，而是按三层分工执行：

1. **脚本负责机械导入**：先运行 `worldbook_tool.py import`，把既有 JSON 转成 `entries/` 源文件、稳定 `entry_id`、初始 `index.md` 和 patch 记录。
2. **主代理负责策略与验收**：决定默认导入层，确认导入条目数、build/check/validate 结果，审核最终层级和重排方案。
3. **子代理负责批量理解**：条目较多时，子代理分批用 `show`/`search` 读取完整条目，提出层级、摘要、重排、重命名建议；结构修改仍必须通过 `worldbook_tool.py move/reorder/rename` 完成，禁止手改 `index.md` 或 output JSON。

小世界书可由主代理直接分类；中大型世界书优先派子代理分批整理，再由主代理统一裁决和执行结构操作。

### 条目源文件格式

正式条目是一条一文件，使用 JSON frontmatter（避免额外 YAML 依赖）：

```md
---
{
  "entry_id": "e0001",
  "title": "世界观总纲",
  "layer": "00-世界设定层",
  "constant": true,
  "position": 0,
  "keys": [],
  "summary": "世界类型、时代、核心矛盾",
  "status": "active"
}
---

这里写世界书条目正文。
```

- `entry_id` 是工作层稳定 ID，不等于导出 JSON 的 `uid`。
- `title` 导出为 JSON `comment`，**MMD 平台上限 20 字**（中文一字算 1，标点计入），超限 `add`/`rename` 会直接拒绝、`check` 报错。别用 `【】`/`·` 装饰，摘要写进 `summary` 而不是标题。目标平台是本地酒馆时在 `worldbook.config.json` 设 `"platform": "st"` 关掉该检查。
- `keys` 导出为 JSON `key`。
- 正文导出为 JSON `content`。
- `uid` 与 `order` 由 build 阶段生成，可以因移动/重排而改变。

## 配置规则
- 所有条目默认 preventRecursion + excludeRecursion。
- 禁用@D depth≥1（打断对话流）；depth=0仅用于行为纠正指令（role=system），不放设定。
- 绿灯keys：英文逗号分隔，含全名/昵称/外号。
- token预算：单条目≤800字为宜；总纲≤500字；蓝灯总量控制（常驻全算token）——多角色卡蓝灯条目数≤5。
- 条目标题（`title`→`comment`）≤20字（MMD硬上限，截断）；不加装饰符，`【】`和`·`同样占额度。
- 新增、删除、移动、重命名、重排条目必须用 `worldbook_tool.py`；不要手工维护 `uid`、`order`、`index.md` 表格。

## 内容写法
条目正文全部遵守 creation/character.md 的写作规则（绝对零度/八股化/具体性/简体中文/无占位符）。
世界观压缩四问：删了这句AI会错吗？是信息还是装饰？列表能替代吗？不看原文能理解吗？

## 平台差异

### 本地酒馆（SillyTavern）
- 全字段可用（含position 2/4/5/6、sticky等）
- 无固定传输字符硬上限（受模型上下文窗口限制）

### MMD 平台
- 保守只用 position 0/1 + 蓝绿灯 + 递归控制；文风条目改↓Char蓝灯（@AT支持未验证）
- **固定传输字符硬上限 15000 字**（会被截断）

**MMD 写卡留字符纪律**：

固定传输字符 = 人设 + 性格 + 情境 + 所有蓝灯条目 content + 该轮触发的绿灯条目 content，上限 15000 字。

1. **蓝灯压瘦**：只放每轮都必须在的（核心人设、系统规则、状态栏输出协议、文风）。蓝灯既吃 15000 额度、又每轮烧 token。
2. **厚设定优先绿灯**：前世记忆、图鉴、地点志、支线 NPC、成人向写法等"用到才需要"的内容塞绿灯。
3. **绿灯按情境错峰**：设计 keys 时想"哪几条会被同一句话/同一情境同时勾起来"，控制这组的峰值，别叠到逼近 15000。例如按"形态阶段"分的记忆条目，天然错峰（不会同阶段一起触发）。
4. **留缓冲**：固定传输基线 + 最坏峰值 应明显低于 15000，给历史/数据块留位（建议预留 2000–3000 字）。

> **硬上限与软建议的关系**：
> - **软建议**（单条≤800字、蓝灯≤5条）管"质量/省token"。
> - **硬上限**（固定传输≤15000字）管"会不会被平台截断"。
> 两者并列遵守：先守硬上限（不被截断），再优化软建议（质量/成本）。

### 通用说明
- 独立世界书json与卡内character_book字段结构不同——输出时见 output/worldbook-json.md
