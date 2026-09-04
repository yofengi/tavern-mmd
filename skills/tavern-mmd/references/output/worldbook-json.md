# 独立世界书 JSON 规范

定位：SillyTavern 独立世界书格式，可直接导入本地酒馆或 MMD 平台（含沙盒模式）。与角色卡内嵌世界书（`character_book.entries`）字段名有差异，见第 3 节对照表。

本文的字段结构**三平台通用**。平台差异只有两处，都在第 5 节：**能不能内嵌**，以及**条目标题 20 字上限的判罚级别**。

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

## 5. 各平台导入说明

| 平台 | 独立世界书 JSON | 随角色卡内嵌 | 条目标题 20 字 |
|---|---|---|---|
| 本地酒馆 `/st` | ✅ 可导入 | ✅ 卡内 `character_book` | **无限制**（不检查） |
| 当前 MMD `/mmd` | ✅ 世界书管理界面导入 | ✅ 卡内 `character_book` 随卡载入 | **ERROR**（硬拦） |
| MMD沙盒模式 `/mmdsandbox` | ✅ 独立导入入口 | ✅ 卡内 `character_book` 随卡载入（同当前 MMD） | **WARN**（提示但不阻断） |

- 两种导入方式产出的条目结构对应关系见第 3 节对照表。
- MMD 系（`/mmd` 与 `/mmdsandbox`）：将角色卡导入时，其中内嵌的 `character_book` 也会同步载入。创卡页原文写明「可导入PNG或json格式世界书」。

### 5.1 沙盒模式：可以随卡内嵌，只是不能进那份 6 键正则 JSON

> ✅ **更正**：旧版本本小节标题是「沙盒模式：世界书必须单独交付」，结论是「沙盒没有整卡内嵌，世界书只能独立文件」。**那是错的，已删除。** `【用户实测】`沙盒能导 v2 整卡，世界书正常放卡内 `character_book`，与当前 MMD 一致。

仍然成立的那一条是**格式约束，范围只限一份文件**：

> 🚨 **世界书不能塞进「导入正则」那份 6 键 JSON。** 那份 JSON 的顶层是**恰好 6 键白名单**，一旦出现 `entries` / `worldbook` / `world_book` / `lorebook` / `lore_book` / `characterBook` / `character_book` 中任何一个，官方直接判 ERROR。

所以沙盒的世界书有**两条路**，按 `card-json.md` §8.1 选定的输出形态走：

- **随整卡（路线 A）**：放卡内 `character_book`，字段名按第 3 节对照表的卡内一侧。状态栏生成规则也照 `card-json.md` §8.2 作蓝灯条目进卡。
- **独立文件（路线 B）**：`<短名>-worldbook.json`，走世界书独立导入入口，并且：
  - **根对象只保留 `entries`** —— 官方校验要求顶层键恰好一个且为 `entries`。本文第 1 节的结构正好就是这个形状，照写即可，别顺手加 `name` / `description` 之类。
  - `entries` 是**对象映射**（键建议连续数字字符串），不是数组；空 `entries` → ERROR。

两条路共同的条目 `content` 约束（沙盒特有）：必须**至少含一组成对章节标签**，且不得含 `$#char#$` / `$#user#$` / `{{char}}`（均 ERROR）。这与人设格式同源，见 `card-json.md` 第 9.2 节。

兜底：若世界书导入失败或入口不可用，官方的退路是把内容压进人设（走路线 A 是 `data.description`、路线 B 是 `personality`，都会吃掉 10000 字额度）。

### 5.2 条目标题 20 字：沙盒模式是 WARN 而非 ERROR

20 字上限的来源是 **MMD 创卡页 UI** 对世界书条目标题的截断，**与 `chatVersion`（新旧聊天页）无关** —— 沙盒模式是同一个 MMD 平台的新聊天页，不是新后端，所以限制**继续保留**、继续提示。

但**判罚级别降为 WARN**：官方 `validate-worldbook.mjs` 里没有这项检查（它只查 `comment` 非空、类型正确等），本 skill 不拿一条无官方脚本背书的平台侧 UI 限制去阻断交付。

三平台在两个工具里的实际行为：

| 工具与操作 | `/mmd` | `/mmdsandbox` | `/st` |
|---|---|---|---|
| `validate.py --type worldbook` | ERROR | **WARN** | 不检查 |
| `worldbook_tool.py add` / `rename` | 拒绝写入，退出码 2 | **照常写入 + `[WARN]`** | 不检查 |
| `worldbook_tool.py check` | error | **warning** | 不检查 |
| `worldbook_tool.py build` | `[WARN]`，不阻断导出 | `[WARN]`，不阻断导出 | 静默 |

在 `worldbook.config.json` 里设 `"platform": "mmdsandbox"` 即切到这套行为（默认值是 `"mmd"`，取严）。

> 该限制在沙盒模式下**尚未实机复验** `【待验证】`。若哪天确认新页放开了这个 UI 限制，直接删掉这条 WARN 即可，不影响其他检查。计长口径与写标题的纪律见第 6 节 `title` 行。

---

## 6. 源文件到 JSON 的字段映射

| 源文件 frontmatter / 正文 | 独立世界书 JSON | 说明 |
|---|---|---|
| `entry_id` | 不默认导出 | 工作层稳定定位 ID；可通过配置选择写入 comment 前缀，但默认保持导出标题干净（开启后前缀 8 字也占标题额度） |
| `title` | `comment` | 平台 UI 里显示的条目标题。**MMD 系上限 20 字**：按字符数计，中文一字算 1，标点空格同样计入，超出导入后被截断；本地酒馆无限制。别加 `【】`/`·`/`—` 等装饰符（同样占额度）。当前 MMD 判 ERROR、沙盒模式判 WARN，见第 5.2 节；口径详见 ../platforms/mmd.md §7 与 ../platforms/mmd-sandbox.md §10.1 |
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
python <skill>/scripts/validate.py "output/世界书名.json" --type worldbook --platform <mmd|mmdsandbox|st>
```

`--platform` 省略时默认 `mmd`（取严，标题超限报 ERROR）。审本地酒馆世界书务必显式传 `--platform st`，否则标题会被误报超限；审沙盒模式传 `--platform mmdsandbox`，标题超限降为 WARN（见第 5.2 节）。
