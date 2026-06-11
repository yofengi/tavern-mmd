# 正则交付物规范

三种交付形式：**本地酒馆正则 JSON**（可导入）、**MMD 导入 JSON**（首选，平台直接导入）和 **MMD 手填清单**（Markdown 文档，备选）。

---

## 第一节：本地酒馆正则 JSON

### 1.1 单条脚本完整字段

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "scriptName": "[界面]状态栏显示",
  "findRegex": "/<status>([\\s\\S]*?)<\\/status>/gs",
  "replaceString": "<div class=\"z-status-box\">$1</div>",
  "trimStrings": [],
  "placement": [2],
  "disabled": false,
  "markdownOnly": true,
  "promptOnly": false,
  "runOnEdit": false,
  "substituteRegex": 0,
  "minDepth": null,
  "maxDepth": null
}
```

### 1.2 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | UUID 格式，每条唯一，用 `uuid.uuid4()` 生成 |
| `scriptName` | string | 界面显示名，建议前缀 `[界面]` 或 `[不发送]` |
| `findRegex` | string | 正则表达式，格式 `/pattern/flags`，常用 `gs` 标志 |
| `replaceString` | string | 替换内容，可用 `$1` 引用捕获组 |
| `trimStrings` | array | 替换前先裁剪的字符串列表，通常为空 |
| `placement` | array | `[1]`=用户输入，`[2]`=AI 输出，`[1,2]`=双向；AI 输出替换用 `[2]` |
| `disabled` | boolean | false=启用，true=禁用 |
| `markdownOnly` | boolean | true=仅作用于渲染层（不影响发送给 AI 的提示词） |
| `promptOnly` | boolean | true=仅作用于提示词层（不影响渲染显示） |
| `runOnEdit` | boolean | 是否在编辑消息时也运行 |
| `substituteRegex` | number | 0=关闭，其他值=启用变量替换 |
| `minDepth` | number\|null | 最小楼层深度限制，null=不限 |
| `maxDepth` | number\|null | 最大楼层深度限制，null=不限 |

**注意**：`markdownOnly` 与 `promptOnly` 不可同时为 true。

### 1.3 打包方式

**多条正则打成 JSON 数组**，单文件，酒馆"导入正则"可批量吃入：

```json
[
  { "id": "uuid-1", "scriptName": "…", "…": "…" },
  { "id": "uuid-2", "scriptName": "…", "…": "…" }
]
```

或嵌入角色卡 `data.extensions.regex_scripts`（数组），随卡一并导入。

### 1.4 命名约定

- `[界面]xxx`：仅渲染层，不影响 AI 上下文
- `[不发送]xxx`：promptOnly=false，markdownOnly=true 的常见简称
- `[提示词]xxx`：作用于 promptOnly=true 的正则

### 1.5 校验命令

```bash
python -m json.tool output/正则文件名.json > /dev/null && echo OK
```

---

## 第二节：MMD 导入 JSON（首选交付）

MMD 平台支持直接导入专用 4 字段格式的 json（与本地酒馆正则 json 结构**不同**，字段更少）。

### 2.1 完整结构

```json
{
  "pageDepth": 2,
  "statusbar": "<css><代码>",
  "beginning": "第一句话正文……\n<ztl>\n[键名=键值]\n[键名2=键值2]",
  "regex_scripts": [
    {
      "id": -1,
      "scriptName": "响应式级联样式表部署",
      "findRegex": "<css>",
      "replaceString": "<style>……</style>"
    },
    {
      "id": -1,
      "scriptName": "数据信标转换器",
      "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]\\s*/g",
      "replaceString": "<span style=\"display:none\">[$1=$2]</span>"
    }
  ]
}
```

### 2.2 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `pageDepth` | number | 页面深度，常用 `2` |
| `statusbar` | string | 状态栏触发标记位（部署类标记放这里，如 `<css><代码>`） |
| `beginning` | string | 第一句话正文（可含测试数据块与 `<ztl>` 锚点） |
| `regex_scripts` | array | 正则数组，每条仅 4 字段 |
| `regex_scripts[].id` | number | 固定 `-1` |
| `regex_scripts[].scriptName` | string | 规则名 |
| `regex_scripts[].findRegex` | string | 查找正则；字面标记直接写（`<css>`），正则表达式带 `/pattern/flags` |
| `regex_scripts[].replaceString` | string | 替换内容，可用 `$1` 捕获组 |

注意：
- **没有** placement/markdownOnly/promptOnly 等字段（MMD 正则仅作用于显示层）
- 限额仍然适用：≤30条、findRegex≤1000字符、replaceString≤10000字符
- 现成范例见 `../../assets/radar-examples/` 下两个"导入用"json
- 校验命令同第一节

---

## 第三节：MMD 手填清单（Markdown 交付物，备选）

当用户偏好手动录入或导入失败时使用。交付物格式如下：

````markdown
# <项目名> MMD正则配置清单

> 共N条（限额30）。逐条复制到MMD平台正则配置界面。
> 每条均已标注字符数；findRegex限1000字符，replaceString限10000字符。

## 规则1：<用途说明>

**findRegex**（填入"查找"框，X字符/限1000）：

```
<status>
```

**replaceString**（填入"替换"框，X字符/限10000）：

```
<div class="z-status-box" ...>……
```

- [ ] 已填写

## 规则2：……
（同上结构）

---
总条数核对：N/30
````

### 3.1 清单生成规则

1. **每条带编号 + 用途说明**：标题格式 `## 规则N：<用途>`，便于追踪
2. **findRegex 与 replaceString 分开独立代码块**：每块单独全选复制，减少误操作
3. **字符数为实测值**：生成时统计并标注在括号内（如 `248字符/限1000`）
4. **末尾总条数核对行**：`总条数核对：N/30`，超过30条须拆分或合并规则
5. **每条勾选框**：`- [ ] 已填写`，手填完毕后勾选，避免遗漏

### 3.2 MMD 平台填写注意事项

- findRegex 字段：直接填写正则内容（不带 `/pattern/flags` 外层斜杠）或带斜杠均可，按 MMD 界面要求为准
- replaceString 字段：如含 HTML，注意转义确认界面接受原始 HTML
- 每条填写后建议发条测试消息验证效果，再勾选 `- [ ] 已填写`
- MMD 平台正则仅作用于显示层（等效 markdownOnly=true）
