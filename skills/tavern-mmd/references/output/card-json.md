# 角色卡 JSON 规范（chara_card_v3 / v2）

定位：角色卡 JSON 权威参考。**本地酒馆交付 v3**（第1-4节）；**MMD 交付 v2**（第5节，MMD 仅识别 v2，不识别 v3）。

---

## 1. 完整骨架

```json
{
  "name": "角色名",
  "description": "角色描述",
  "personality": "性格",
  "scenario": "场景",
  "first_mes": "开场白",
  "mes_example": "<START>\n{{user}}: …\n{{char}}: …",
  "creatorcomment": "制作者备注",
  "avatar": "none",
  "talkativeness": "0.5",
  "fav": false,
  "tags": [],
  "spec": "chara_card_v3",
  "spec_version": "3.0",
  "create_date": "2026-01-01T00:00:00.000Z",
  "data": {
    "name": "角色名",
    "description": "角色描述",
    "personality": "性格",
    "scenario": "场景",
    "first_mes": "开场白",
    "mes_example": "<START>\n{{user}}: …\n{{char}}: …",
    "creator_notes": "",
    "system_prompt": "",
    "post_history_instructions": "",
    "tags": [],
    "creator": "",
    "character_version": "1.0",
    "alternate_greetings": [],
    "group_only_greetings": [],
    "extensions": {
      "talkativeness": "0.5",
      "fav": false,
      "world": "角色名",
      "depth_prompt": {
        "prompt": "",
        "depth": 4,
        "role": "system"
      }
    },
    "character_book": {
      "name": "角色名",
      "entries": []
    }
  }
}
```

---

## 2. 同步规则

| 字段 | 说明 |
|---|---|
| `name` | 顶层与 `data.name` 必须一致 |
| `first_mes` | 顶层与 `data.first_mes` 必须一致 |
| `mes_example` | 顶层与 `data.mes_example` 必须一致 |
| `description` | 顶层与 `data.description` 必须一致 |
| `personality` | 顶层与 `data.personality` 必须一致 |
| `scenario` | 顶层与 `data.scenario` 必须一致 |
| `data.extensions.world` | 通常等于角色名（用于关联卡内世界书） |

---

## 3. 卡内世界书条目结构

`data.character_book.entries` 是数组，每个元素结构如下：

```json
{
  "id": 0,
  "keys": [],
  "secondary_keys": [],
  "comment": "条目备注（界面显示名）",
  "content": "注入内容",
  "constant": true,
  "selective": false,
  "insertion_order": 100,
  "enabled": true,
  "position": "after_char",
  "use_regex": true,
  "extensions": {
    "position": 1,
    "exclude_recursion": true,
    "display_index": 0,
    "probability": 100,
    "useProbability": true,
    "depth": 4,
    "selectiveLogic": 0,
    "outlet_name": "",
    "group": "",
    "group_override": false,
    "group_weight": 100,
    "prevent_recursion": true,
    "delay_until_recursion": false,
    "scan_depth": null,
    "match_whole_words": null,
    "use_group_scoring": false,
    "case_sensitive": null,
    "automation_id": "",
    "role": 0,
    "vectorized": false,
    "sticky": 0,
    "cooldown": 0,
    "delay": 0,
    "match_persona_description": false,
    "match_character_description": false,
    "match_character_personality": false,
    "match_character_depth_prompt": false,
    "match_scenario": false,
    "match_creator_notes": false,
    "triggers": [],
    "ignore_budget": false
  }
}
```

### 3.1 position 对应关系

| 条目层（字符串） | extensions 层（数字） |
|---|---|
| `"before_char"` | `0` |
| `"after_char"` | `1` |

两处必须同步，否则酒馆行为不一致。

### 3.2 selective 与 constant 的关系

`selective = !constant`：蓝灯（常驻）条目 constant=true → selective=false；绿灯（关键词触发）constant=false → selective=true。

### 3.3 display_index

按条目在数组中的插入顺序递增，从 0 开始。

---

## 4. 嵌入正则（本地酒馆）

卡内正则存放在 `data.extensions.regex_scripts`（数组）。本地酒馆读取此字段；MMD 平台忽略此字段，MMD 正则走导入json或手填清单，详见 `regex-output.md`。

```json
"data": {
  "extensions": {
    "talkativeness": "0.5",
    "fav": false,
    "world": "角色名",
    "depth_prompt": { "prompt": "", "depth": 4, "role": "system" },
    "regex_scripts": []
  }
}
```

---

## 5. chara_card_v2（MMD 交付格式）

MMD（新旧版同）**仅支持导入 v2 角色卡**。MMD 项目的角色卡 json 必须按本节输出。

### 5.1 与 v3 的差异（v2 = v3 骨架做以下修改）

| 位置 | v3 | v2 |
|---|---|---|
| `spec` | `"chara_card_v3"` | `"chara_card_v2"` |
| `spec_version` | `"3.0"` | `"2.0"` |
| `data.group_only_greetings` | 有 | **删除**（v3专有字段） |
| 其余字段 | — | 完全一致（含顶层遗留字段、data内字段、character_book条目结构、同步规则） |

### 5.2 v2 骨架（差异部分示意）

```json
{
  "name": "角色名",
  "…顶层遗留字段同第1节…": "…",
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "create_date": "2026-01-01T00:00:00.000Z",
  "data": {
    "name": "角色名",
    "…data字段同第1节，但不含 group_only_greetings…": "…",
    "alternate_greetings": [],
    "extensions": { "…同第1节…": "…" },
    "character_book": { "name": "角色名", "entries": [] }
  }
}
```

### 5.3 交付规则

- MMD 项目：output/ 只产出 v2 卡
- 本地酒馆项目：产出 v3 卡
- 用户两边都要：产出两份（`卡名-v3.json` + `卡名-v2-MMD.json`），内容仅按 5.1 差异表区别
- 卡内世界书条目结构 v2/v3 一致（第3节通用），世界书也可单独走独立世界书json（见 worldbook-json.md，MMD可导入）

---

## 6. 校验命令

```bash
python -m json.tool output/卡名.json > /dev/null && echo OK
```

输出 `OK` 即 JSON 格式合法。导入酒馆前务必执行。

---

## 7. 导出整张图片卡

整张角色卡的导入能力按平台不同：

| 平台 | png 整卡 | jpg 整卡 | json 整卡 |
|---|---|---|---|
| MMD（新/旧） | ✅ | ❌ 已弃用（实测读不出卡数据） | ❌ 不能直接导入整卡（仅世界书/正则可 json 导入） |
| 本地酒馆 | ✅ | ❌ 已弃用 | ✅ |

> **JPG 已弃用**：实测 MMD 无法从 jpg 读出卡数据——EXIF UserComment 方案因 8 字节字符集前缀致 atob 失败、JPEG COM 段方案也验证不可用。整卡图片一律用 **PNG**。

**交付整张图片卡前，主 AI 用 AskUserQuestion 问底图来源**：默认米黄底图（下部带 tavern-mmd 标签） / 用户自备图（让用户给路径）。

（输出形态 PNG / JSON / 分离式 的三选弹窗见第 8 节；本节只管图片底图。）

**生成命令**（脚本见 scripts/make_card_image.py，只产 png）：
```bash
# 默认底图 + v2 卡（MMD）
python make_card_image.py output/卡名-v2-MMD.json -o output/卡名.png
# 用户底图（png）
python make_card_image.py output/卡名.json --bg 资料/底图.png -o output/卡名.png
```

**嵌入与 v2/v3**：脚本只忠实嵌入传入的卡 JSON。MMD 项目传 v2（只写 `chara` chunk）；本地酒馆传 v3（写 `chara` + `ccv3`）。两边都要则分别用 v3 与 v2 JSON 各跑一次。

---

## 8. 整卡输出形态与状态栏规则进世界书

### 8.1 三种输出形态（末尾用弹窗询问）

做整张角色卡、用户未指定时，完成后用 AskUserQuestion 问输出形态：

| 形态 | 产出 | 适用 |
|---|---|---|
| (a) 内嵌正则的整卡 PNG | 一张 png，卡内含设定+世界书+`data.extensions.regex_scripts` | 推荐。MMD 导入即一次到位 |
| (b) 内嵌正则的整卡 JSON | v2 卡 json（含内嵌 regex_scripts） | MMD 不能直接导 json 整卡，多用于本地酒馆/备份 |
| (c) 分离式 | 角色卡 + 独立正则 json（见 regex-output.md）+ 状态栏规则.md | 卡与正则分文件，便于单独维护/复用 |

内嵌正则用 MMD 4 字段格式（id:-1/scriptName/findRegex/replaceString）放进 `data.extensions.regex_scripts`，见第 4 节。分离式的独立正则 json 的 `beginning`/`regex_scripts` 应与卡内 `first_mes`/`regex_scripts` 保持一致，避免分开导入时互相覆盖。

### 8.2 状态栏生成规则必须进世界书（默认蓝灯）

**渲染正则 ≠ 生成规则。** 内嵌的 `regex_scripts` 只负责把 `<status>` 数据块渲染成面板；它不会让模型去**生成**数据块。若只内嵌渲染正则，模型只在 `first_mes` 那一个数据块时显示状态栏，后续轮次不再输出 → 状态栏不更新。

因此，输出整张内嵌正则的角色卡（a/b 形态）时，状态栏的**生成规则**（模型侧协议：要求 AI 每轮在正文末尾输出 `<status>` 数据块、字段格式、继承规则、选项必出等）必须作为一条 **constant=true（蓝灯/固定）** 条目放进卡内 `character_book.entries`。

条目按第 3 节结构，关键字段：

```json
{
  "id": 0,
  "keys": [],
  "comment": "状态栏生成规则（模型侧协议）",
  "content": "每轮回复正文结束后，另起一行输出 <status> 数据块……（字段格式/继承/选项必出等完整协议）",
  "constant": true,
  "selective": false,
  "insertion_order": 100,
  "enabled": true,
  "position": "after_char",
  "extensions": { "position": 1, "...": "同第3节" }
}
```

- `constant: true` + `selective: false`：蓝灯常驻，每轮注入（见 §3.2）。
- 规则正文怎么写见 `../beautify/statusbar.md`（KV V4.0）或 `../beautify/statusbar-radar.md`（雷达法）的规则写法节。
- 分离式（c 形态）则把这份规则单独输出为 `状态栏规则.md`，不放进卡。
