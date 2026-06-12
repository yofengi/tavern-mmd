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
