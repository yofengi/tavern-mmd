# 角色卡 JSON 规范（chara_card_v3）

定位：SillyTavern chara_card_v3 格式角色卡，三平台通用（本地酒馆、MMD、其他兼容前端）。

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

卡内正则存放在 `data.extensions.regex_scripts`（数组）。本地酒馆读取此字段；MMD 平台忽略此字段，MMD 正则必须另出手填清单，详见 `regex-output.md`。

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

## 5. 校验命令

```bash
python -m json.tool output/卡名.json > /dev/null && echo OK
```

输出 `OK` 即 JSON 格式合法。导入酒馆前务必执行。
