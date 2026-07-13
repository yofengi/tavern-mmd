# 独立世界书 JSON 规范

定位：SillyTavern 独立世界书格式，可直接导入本地酒馆或 MMD 平台。与角色卡内嵌世界书（`character_book.entries`）字段名有差异，见第 3 节对照表。

---

## 1. 顶层结构

**注意**：`entries` 是以 uid 字符串为键的对象，不是数组。

> **索引源文件工作流说明**：使用 tavern-mmd 的 `工作/世界书/` 工作流时，`entries` 源文件中的稳定定位编号是 `entry_id`，不是导出 JSON 的 `uid`。导出 JSON 的 `uid` 与 `order` 由 `scripts/worldbook_tool.py build` 按当前层级和文件顺序生成，可在重排后变化。常规修改应回到源文件，再重新 build；不要手动把 output JSON 当作工作源。

```json
{
  "entries": {
    "0": { "uid": 0, "…": "…" },
    "1": { "uid": 1, "…": "…" }
  }
}
```

---

## 2. 单条目完整字段

```json
{
  "uid": 0,
  "key": ["关键词1", "关键词2"],
  "keysecondary": [],
  "comment": "条目备注",
  "content": "注入内容",
  "constant": false,
  "vectorized": false,
  "selective": false,
  "selectiveLogic": 0,
  "addMemo": true,
  "order": 100,
  "position": 0,
  "disable": false,
  "ignoreBudget": false,
  "excludeRecursion": false,
  "preventRecursion": false,
  "matchPersonaDescription": false,
  "matchCharacterDescription": false,
  "matchCharacterPersonality": false,
  "matchCharacterDepthPrompt": false,
  "matchScenario": false,
  "matchCreatorNotes": false,
  "delayUntilRecursion": false,
  "probability": 100,
  "useProbability": true,
  "depth": 1,
  "outletName": "",
  "group": "",
  "groupOverride": false,
  "groupWeight": 100,
  "scanDepth": null,
  "caseSensitive": null,
  "matchWholeWords": null,
  "useGroupScoring": false,
  "automationId": "",
  "role": 0,
  "sticky": 0,
  "cooldown": 0,
  "delay": 0,
  "triggers": [],
  "displayIndex": 0,
  "extensions": {},
  "characterFilter": {
    "isExclude": false,
    "names": [],
    "tags": []
  }
}
```

---

## 3. 与卡内条目字段名差异对照

| 独立世界书（本节） | 卡内条目（card-json.md §3） | 说明 |
|---|---|---|
| `key` | `keys` | 主关键词数组 |
| `keysecondary` | `secondary_keys` | 次关键词数组 |
| `order` | `insertion_order` | 注入顺序权重 |
| `disable: false` | `enabled: true` | 语义相反，逻辑等价 |
| `position: 0`（数字） | `position: "after_char"`（字符串） | position 编码方式不同 |
| 驼峰扁平字段（如 `excludeRecursion`） | 嵌套 `extensions.exclude_recursion` | 独立世界书扁平存于顶层；卡内条目存于 extensions 子对象 |
| `addMemo` | 无对应 | 独立世界书专有，控制备注显示 |
| `characterFilter` | 无对应 | 独立世界书专有，按角色过滤激活 |

### position 数字编码（独立世界书）

| 数值 | 含义 |
|---|---|
| `0` | before_char（角色定义前，↑Char） |
| `1` | after_char（角色定义后，↓Char） |
| `2` | Author's Note 之前（↑AT） |
| `3` | Author's Note 之后（↓AT） |
| `4` | at_depth（@D，与 depth/role 字段配合） |
| `5` | 示例消息之前（↑EM） |
| `6` | 示例消息之后（↓EM） |

---

## 4. 蓝灯 / 绿灯配置

| 模式 | constant | selective | key |
|---|---|---|---|
| 蓝灯（常驻注入） | `true` | `false` | 可为空 |
| 绿灯（关键词触发） | `false` | `true` | 必须非空 |

> `selective` 实际控制次关键词（`keysecondary`）过滤逻辑，仅在 `keysecondary` 非空时生效；绿灯条目按惯例设 `true`（与卡内条目 `selective = !constant` 约定一致，也是酒馆UI新建条目的默认值）。

**本 skill 约定**：新建条目默认 `preventRecursion: true`，`excludeRecursion: true`；使用 `worldbook_tool.py build` 会自动补齐。确需改写递归、depth、role、sticky、cooldown、keysecondary 等高级字段时，可在源文件 JSON frontmatter 中加入对应独立世界书字段，build 会保留这些字段。

---

## 5. MMD 导入说明

- 独立世界书 JSON 可直接在 MMD 世界书管理界面导入。
- 将角色卡 JSON 导入时，其中内嵌的 `character_book` 也会同步载入。
- 两种导入方式产出的条目结构对应关系见第 3 节对照表。

---

## 6. 源文件到 JSON 的字段映射

| 源文件 frontmatter / 正文 | 独立世界书 JSON | 说明 |
|---|---|---|
| `entry_id` | 不默认导出 | 工作层稳定定位 ID；可通过配置选择写入 comment 前缀，但默认保持导出标题干净 |
| `title` | `comment` | 平台 UI 里显示的条目标题 |
| `keys` | `key` | 主关键词数组 |
| `constant` | `constant` | 蓝灯为 true，绿灯为 false |
| `position` | `position` | 独立世界书数字 position |
| 正文 | `content` | 条目注入内容 |
| 高级字段（如 `keysecondary`、`depth`、`role`、`sticky`、`cooldown`、`scanDepth`、`caseSensitive`、`extensions`） | 同名字段 | 可选写入源文件 frontmatter；build 会透传到独立世界书 JSON |
| 层级与文件顺序 | `uid` / `order` | build 阶段自动生成，可重排 |

---

## 7. 校验命令

```bash
python -m json.tool "output/世界书名.json"
```

命令退出码为 0 即 JSON 格式合法。若在 POSIX/Git Bash 中想静默校验，可追加 `> /dev/null`；Windows PowerShell 可追加 `> $null`。

使用源文件工作流时还要运行：

```bash
python <skill>/scripts/worldbook_tool.py check "工作/世界书" --out "output/世界书名.json"
python <skill>/scripts/validate.py "output/世界书名.json" --type worldbook --platform mmd
```
