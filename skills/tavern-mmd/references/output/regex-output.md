# 正则交付物规范

三种交付形式：**本地酒馆正则 JSON**（可导入）、**MMD 导入 JSON**（首选，平台直接导入）和 **MMD 手填清单**（Markdown 文档，备选）。

> **单独美化 / 状态栏流程的默认交付** = 正则 json + 规则.md（独立的状态栏生成规则文档/模型侧协议），不强制塞进某张卡。若是做整张角色卡，正则默认内嵌进卡、状态栏规则进卡内世界书（蓝灯），见 card-json.md 第 8 节。

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
- 限额仍然适用：≤130条、findRegex≤1000字符、replaceString≤20000字符
- 现成范例见 `../../assets/radar-examples/` 下两个"导入用"json
- 校验命令同第一节

### 2.3 JSON 字符串转义（最易踩的坑，必读）

`replaceString` 里放大段 HTML/CSS/JS 时，**整个值必须是合法的 JSON 字符串字面量**，否则 MMD 导入会报"json 数据异常"。两条铁律：

1. **所有换行必须转义为 `\n`，不能用真实换行。** HTML 在源码里是多行的，但写进 JSON 后必须是单行字符串，换行用 `\n` 表示。
   - ❌ 错误（值里有真实回车，JSON 非法）：
     ```
     "replaceString": "<style>
     body{color:red}
     </style>"
     ```
   - ✅ 正确：
     ```
     "replaceString": "<style>\nbody{color:red}\n</style>"
     ```
2. **HTML 内部的双引号必须转义为 `\"`**（如 `class=\"box\"`），或在 HTML 里改用单引号。
3. **文件不能带 UTF-8 BOM**：用无 BOM 的 UTF-8 保存（Windows 记事本"另存为"要选 UTF-8 而非 UTF-8 BOM）。

**生成方式（强烈推荐）**：不要手写转义。用脚本构造对象再序列化，让工具自动转义：

```python
import json
html = open('statusbar.html', encoding='utf-8').read()   # 可读的多行HTML
obj = {
    "pageDepth": 2,
    "statusbar": "<wabisabi-ui>",
    "beginning": "",
    "regex_scripts": [
        {"id": -1, "scriptName": "规则名", "findRegex": "<wabisabi-ui>", "replaceString": html}
    ]
}
# ensure_ascii=False 保留中文；json.dumps 自动把换行转\n、引号转\"
open('out.json', 'w', encoding='utf-8').write(json.dumps(obj, ensure_ascii=False, indent=2))
json.loads(open('out.json', encoding='utf-8').read())   # 回读自检
```

### 2.4 双重转义陷阱（用脚本时必查）

`json.dumps` 只能对**裸 HTML**（属性引号是 `"`、换行是真实换行）正确转义一次。若喂给它的 `html` 变量本身已经是转义过的内容（属性写成 `\"`、换行写成字面 `\n`），会被**再转义一层**，导致：

- 解析出来的 HTML 里属性变成 `class=\"box\"`（多了反斜杠），浏览器渲染错乱
- 或字面 `\n` 没变成真换行，CSS 全挤在一行

典型来源：从另一个 JSON 的 `replaceString` 里复制内容、或从聊天记录粘贴已转义的代码。

**强制自检（生成后必跑）**：
```python
import json
rs = json.load(open('out.json', encoding='utf-8'))['regex_scripts'][0]['replaceString']
assert rs.count('\\') == 0 or '\\' not in rs, f'HTML残留{rs.count(chr(92))}个反斜杠，疑双重转义'
assert '<script' not in rs.lower(), '含<script>，旧版MMD禁用'
print('字符数', len(rs), '| 残留反斜杠', rs.count(chr(92)))
```
解析后的 `replaceString` 里**反斜杠数应为 0**（除非 HTML/JS 逻辑真的需要反斜杠，如正则脚本——纯美化 HTML 通常不含）。若数量异常偏高（几百个），几乎一定是双重转义，需把源 HTML 先 `.replace('\\"','"')` 还原再重新 dumps。

**交付前必须 `python -m json.tool out.json > /dev/null`**——能拦住裸换行、未转义引号、BOM 等全部此类错误。

### 2.5 交付前强制审核（用 validate.py，必做）

skill 自带 `scripts/validate.py` 一次性覆盖上述所有检查（JSON合法性、BOM、双重转义、平台红线、字符数、v2规范、**悬空标记**），比手写 assert 更全。**0 错误才能交付：**

```bash
python <skill>/scripts/validate.py output/文件.json --platform <mmd|oldmmd>
```

报错对照处理：
- `双重转义` → 源HTML喂 json.dumps 前已含 `\"`，先 `.replace(chr(92)+chr(34), chr(34))` 还原（见 2.4 与 wabisabi 案例）
- `BOM` → 改用无 BOM 的 UTF-8 保存
- `换行` → replaceString 内真实换行未转 `\n`
- `<script>`/`ES6`/`innerHTML` → 旧版MMD红线，按报告改写
- `悬空标记` → `statusbar`/`beginning` 里有 `<标记>` 但 `regex_scripts` 没有对应 `findRegex` 消费；会在页面裸露，必须补正则或删标记

可选预览（状态栏/美化必做）：`python <skill>/scripts/build-preview.py output/文件.json --platform <mmd|oldmmd>`（默认 `--mode both`）。MMD 导入 json 会生成两份：**三面板沙箱**（①第一句话剩余预览，显示扣除单独抽检的状态栏/悬浮组件后的正文、选项菜单/图片/特殊美化；②状态栏单独预览；③悬浮组件预览，侧边栏/悬浮球）用于逐组件审核；**全景预览**（`-panorama-` 文件）把所有组件组合进一个模拟 MMD 聊天页，底部固定主输入框+发送按钮，发送出现用户气泡+占位AI气泡，用于二次审核组合效果。主AI 用 Preview 工具先看三面板、再看全景，全景不默认关闭留给用户自查。

> `--platform mmd`（当前 MMD）下，`<script>`/ES6/onerror多行均不报红（实测支持），只对 onclick 代码字面量/赋值告警；`--platform oldmmd` 保持全红线最严格。校验当前 MMD 产出务必带 `--platform mmd`，否则会误报 ES6/script。

### 2.6 平台原生替换语法（当前 MMD，写正则时可直接用）

MMD 平台正则的 `replaceString` 内除了 HTML/CSS/JS，还可用平台内置语法：

| 写法 | 作用 | 生效范围 |
|---|---|---|
| `$1` `$2` | 引用 findRegex 捕获组 | 通用 |
| `$字段名`（如 `$hp`） | KV 格式字段引用：findRegex 第一个捕获里同时含 `::` 和 `;;` 时，替换里用 `$hp` 取 `hp::85;;...` 的值 | 原生 KV 状态栏（零JS固定字段） |
| `{{random:A::B::C}}` | 随机显示其一；多个 random 各自独立 | 替换内容里 |
| `{{user}}` / `{{char}}` | 玩家名 / 角色名 | **仅开场白**，AI 回复里不替换 |
| 替换留空 | 匹配内容隐藏（AI 仍可见原文） | 通用 |

**标签白名单（AI 回复里）**：可用 `div span p a img button style details summary table video input textarea` 等；会被删 `section header footer nav iframe canvas audio form`。开场白限制更少。

**选项填输入框的选择器**：官方示例用 `document.querySelector('textarea, input[type="text"]')`；若引擎/脚本写死了 `.uni-textarea-textarea`，建议加这层兜底选择器，避免平台改版选不中输入框。

---

## 第三节：MMD 手填清单（Markdown 交付物，备选）

当用户偏好手动录入或导入失败时使用。交付物格式如下：

````markdown
# <项目名> MMD正则配置清单

> 共N条（限额130）。逐条复制到MMD平台正则配置界面。
> 每条均已标注字符数；findRegex限1000字符，replaceString限20000字符。

## 规则1：<用途说明>

**findRegex**（填入"查找"框，X字符/限1000）：

```
<status>
```

**replaceString**（填入"替换"框，X字符/限20000）：

```
<div class="z-status-box" ...>……
```

- [ ] 已填写

## 规则2：……
（同上结构）

---
总条数核对：N/130
````

### 3.1 清单生成规则

1. **每条带编号 + 用途说明**：标题格式 `## 规则N：<用途>`，便于追踪
2. **findRegex 与 replaceString 分开独立代码块**：每块单独全选复制，减少误操作
3. **字符数为实测值**：生成时统计并标注在括号内（如 `248字符/限1000`）
4. **末尾总条数核对行**：`总条数核对：N/130`，超过130条须拆分或合并规则
5. **每条勾选框**：`- [ ] 已填写`，手填完毕后勾选，避免遗漏

### 3.2 MMD 平台填写注意事项

- findRegex 字段：直接填写正则内容（不带 `/pattern/flags` 外层斜杠）或带斜杠均可，按 MMD 界面要求为准
- replaceString 字段：如含 HTML，注意转义确认界面接受原始 HTML
- 每条填写后建议发条测试消息验证效果，再勾选 `- [ ] 已填写`
- MMD 平台正则仅作用于显示层（等效 markdownOnly=true）
