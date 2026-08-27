# 正则交付物规范

## 平台 → 格式速查（先定位再往下读）

| 目标平台 | 正则交付格式 | 本文哪一节 | 顶层键 | `findRegex` 形态 | `id` |
|---|---|---|---|---|---|
| 本地酒馆（`/st`） | 正则 JSON 数组（13 字段/条） | **第一节** | 无（数组） | `/pattern/flags` | UUID 字符串 |
| 当前 MMD（`/mmd`） | 导入 JSON，**4 键顶层** | **第二节** | `pageDepth` `statusbar` `beginning` `regex_scripts` | **强制** `/pattern/flags` slash literal | 固定 `-1` |
| MMD沙盒模式（`/mmdsandbox`） | 导入正则 JSON，**恰好 6 键顶层** | **第三节** | 上面 4 键 + `chatVersion` + `personality` | **强制 slash 形态**（实机裸字面量不生效） | **任意负数**，导入时重编号 |
| MMD 两平台的备选 | 手填清单（Markdown 文档） | **第四节** | —— | 同该平台 | 同该平台 |

三者结构互不兼容，**不要把一个平台的 JSON 直接改平台名交付**：第二节与第三节的顶层键数、`findRegex` 铁律、`id` 取值三处全都不同（沙盒模式还多一份独立 persona 文本，见第三节 3.5）。

> **单独美化 / 状态栏流程的默认交付** = 正则 json + 规则.md（独立的状态栏生成规则文档/模型侧协议），不强制塞进某张卡。若是做整张角色卡，正则默认内嵌进卡、状态栏规则进卡内世界书（蓝灯），见 card-json.md 第 8 节。**沙盒模式例外**：它不走整卡内嵌（见 card-json.md 第 9 节），正则 JSON 始终是独立交付物。

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

## 第二节：当前 MMD 导入 JSON（`/mmd` 首选交付）

> **仅适用于当前 MMD（`--platform mmd`）。** 沙盒模式的导入 JSON 是 6 键顶层且同样强制 slash 形态，见**第三节**；不要把两种顶层结构混用。

当前 MMD 平台支持直接导入专用 4 字段格式的 json（与本地酒馆正则 json 结构**不同**，字段更少）。顶层必须**恰好且仅有** `pageDepth`、`statusbar`、`beginning`、`regex_scripts` 四个键；`regex_scripts` 的每条规则也必须**恰好且仅有** `id`、`scriptName`、`findRegex`、`replaceString` 四个键，不得夹带 ST 字段或任意扩展键。

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
      "findRegex": "/<css>/",
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
| `regex_scripts[].findRegex` | string | 查找正则；当前 MMD **必须写 slash literal**（固定标记也写 `/<css>/`，一般表达式写 `/pattern/flags`） |
| `regex_scripts[].replaceString` | string | 替换内容，可用 `$1` 捕获组 |

注意：
- **没有** placement/markdownOnly/promptOnly 等字段（MMD 正则仅作用于显示层）
- **两条 MMD 路线的交付 `findRegex` 都必须是 `/pattern/flags` slash 形态**：当前 MMD 与沙盒实机都不接受裸字面量交付。沙盒 worker 源码虽有 literal 分支，但实机裸字面量不生效，不能把实现分支当可交付能力。
- 限额仍然适用：≤130条、findRegex≤1000字符、replaceString≤20000字符
- 现成状态栏范例可参考 `../../assets/radar-examples/西幻RPG-正则与第一句话.json`
- `../../assets/radar-examples/完整美化-日夜主题与雷达.json` 是 **legacy 日夜集成包**，只作兼容研究，不再推荐作为新全局主题基底；需要 day/night/native 或生命周期管理时，优先使用 `../../assets/global-beautify-examples/mmd-theme-runtime/` 的新 runtime
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
        {"id": -1, "scriptName": "规则名", "findRegex": "/<wabisabi-ui>/", "replaceString": html}
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
print('字符数', len(rs), '| 残留反斜杠', rs.count(chr(92)))
# 注：不要在这里 assert 「无 <script>」——在役的两个 MMD 平台都允许 <script>
# （当前 MMD 已实测可执行；沙盒模式更是一等公民）。平台红线交给 validate.py 判。
```
解析后的 `replaceString` 里**反斜杠数应为 0**（除非 HTML/JS 逻辑真的需要反斜杠，如正则脚本——纯美化 HTML 通常不含）。若数量异常偏高（几百个），几乎一定是双重转义，需把源 HTML 先 `.replace('\\"','"')` 还原再重新 dumps。

**交付前必须 `python -m json.tool out.json > /dev/null`**——能拦住裸换行、未转义引号、BOM 等全部此类错误。

### 2.5 交付前强制审核（用 validate.py，必做）

skill 自带 `scripts/validate.py` 一次性覆盖上述所有检查（JSON合法性、BOM、双重转义、平台红线、字符数、v2规范、**悬空标记**），比手写 assert 更全。**0 错误才能交付：**

```bash
python <skill>/scripts/validate.py output/文件.json --platform mmd
```

`--platform` 的三个取值是 `mmd`（当前 MMD，**默认值**）/ `mmdsandbox`（沙盒模式）/ `st`（本地酒馆）。审沙盒产出必须显式写 `--platform mmdsandbox`，否则会按 4 键顶层误报（沙盒的 `chatVersion`/`personality` 会被当成多余键）。

报错对照处理：
- `双重转义` → 源HTML喂 json.dumps 前已含 `\"`，先 `.replace(chr(92)+chr(34), chr(34))` 还原（见 2.4 与 wabisabi 案例）
- `BOM` → 改用无 BOM 的 UTF-8 保存
- `换行` → replaceString 内真实换行未转 `\n`
- `innerHTML`/`cssText` → 易被平台净化，按报告改写（两个 MMD 平台都只是 WARN）
- `悬空标记` → `statusbar`/`beginning` 里有 `<标记>` 但 `regex_scripts` 没有对应 `findRegex` 消费；会在页面裸露，必须补正则或删标记

可选预览（状态栏/美化必做）：`python <skill>/scripts/build-preview.py output/文件.json --platform <mmd|mmdsandbox|st>`（`--platform` 必填无默认；默认 `--mode both`）。MMD 导入 json 会生成三面板诊断与全景：三面板用于逐组件审核；全景把组件组合进一个聊天页。`mmd`/`st` 的通用全景使用 fixed 输入栏与占位 AI；`mmdsandbox` 使用真实新聊天页的 root flex 外壳、静态 composer 和本地 SDK profile，仿真控制/证据说明默认折叠。主AI 先看三面板，再按平台检查全景；沙盒还要分别生成 `chat`/`thin-preview` 并验桌面、竖屏、横屏/键盘高度。

> `--platform mmd`（当前 MMD，validate.py 的默认值）下，`<script>`/ES6/onerror 多行均按实测能力放行；inline `onclick` 只认证平台已实测的 canonical 形式，代码字符串、赋值和未认证形式均记为 ERROR，并在 preview 中禁用。`--platform mmdsandbox` 换一整套检查（6 键顶层白名单、`chatVersion` 必须为 1、`id` 必须负数、SDK 能力/事件名核对、禁 `img onerror` 点火器等），见第三节 3.6。

### 2.6 平台原生替换语法（**当前 MMD 专用**，写正则时可直接用）

**当前 MMD inline handler 的权威可用形式**：无参数全局调用用 `onclick="window.__fn&&__fn()"`；轻主板调用用 `onclick="eval(getElementById('FUNC').dataset.s)"`。两者都是单一干净调用/引用表达式；不要把代码字符串直接塞进 `eval('...')`，也不要在属性里写 DOM 赋值。复杂组件还可在 `img onerror` 内用 `el.onclick=function(){...}` 动态绑定，避开 inline 属性净化。

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

## 第三节：MMD沙盒模式导入正则 JSON（`/mmdsandbox`）

> **仅适用于沙盒模式（`--platform mmdsandbox`）。** 「沙盒模式」是本 skill 的叫法，官方口径是「新页 / 新聊天页」，开关是角色卡 `chatVersion: 1`。平台能力全集见 `../platforms/mmd-sandbox.md`。
>
> 导入入口是创卡页的「**导入正则**」（也叫「设置正则」），吃 **JSON 文本**。沙盒模式**不走** chara_card_v2、**不走 PNG 整卡**（官方明令禁止），所以正则 JSON 是主交付物而不是附件。

顶层必须**恰好 6 键**，多一个不认、少一个报错：

```
chatVersion  pageDepth  statusbar  beginning  personality  regex_scripts
```

`regex_scripts` 的每条规则仍是**恰好 4 键** `id` / `scriptName` / `findRegex` / `replaceString`（与第二节同名，但 `id` 取值规则不同）。

### 3.1 完整结构（可直接照抄的合法样例）

```json
{
  "chatVersion": 1,
  "pageDepth": 2,
  "statusbar": "{{hud}}",
  "beginning": "雨还在下。禾安把伞往 {{user}} 那边偏了偏，指尖沾着湿泥。\n\n{{intro}}",
  "personality": "<角色设定 名字：禾安>\n<基本信息>\n- 身份：种子铺守护人\n- 年龄：二十七\n</基本信息>\n<说话方式>\n- 句子短，不用比喻。\n</说话方式>\n</角色设定>\n<输出格式>\n- 每轮正文结束后另起一行输出 [状态]\n血量: 当前值/上限\n金币: 整数\n[/状态]\n</输出格式>",
  "regex_scripts": [
    {
      "id": -1,
      "scriptName": "禾安-style",
      "findRegex": "/{{禾安-style}}/",
      "replaceString": "<style>\n.hean-hud{display:flex;gap:8px;padding:6px 10px;background:var(--chat-surface);color:var(--chat-text);border-bottom:1px solid var(--chat-border)}\n.hean-hud button{background:var(--chat-accent);border:0;border-radius:4px;padding:2px 8px;color:var(--chat-bubble-text)}\n</style>"
    },
    {
      "id": -2,
      "scriptName": "hud",
      "findRegex": "/{{hud}}/",
      "replaceString": "<div class=\"hean-hud\"><span class=\"hean-hp\">血量 --</span><button class=\"hean-ask\">问路</button></div>"
    },
    {
      "id": -3,
      "scriptName": "状态块渲染",
      "findRegex": "/\\[状态\\]([\\s\\S]*?)\\[\\/状态\\]/",
      "replaceString": "<div class=\"hean-row\" style=\"display:none\">$1</div>"
    },
    {
      "id": -4,
      "scriptName": "禾安-kit",
      "findRegex": "/{{禾安-kit}}/",
      "replaceString": "<script>\nsdk.debug.log('禾安 kit 就位');\nsdk.on('message:done', function (msg) {\n  if (!msg || !msg.content) return;\n  var m = /血量[:：]\\s*(\\d+)/.exec(msg.content);\n  if (!m) return;\n  var hp = parseInt(m[1], 10);\n  if (isNaN(hp)) return;\n  var el = document.body.querySelector('.hean-hp');\n  if (el) el.textContent = '血量 ' + hp;\n});\nsdk.on('message:mount', function () {\n  var btn = document.querySelector('.hean-ask');\n  if (!btn) return;\n  btn.addEventListener('click', function () { sdk.input.set('这条路通去哪里？'); });\n});\n<\\/script>"
    }
  ]
}
```

样例里的四条对应沙盒起手形态：一条只放 `<style>`、一条放功能栏可见 UI、一条把模型吐的 `[状态]` 块吃掉、一条只放 `<script>`。`/{{禾安-style}}/` 与 `/{{禾安-kit}}/` 的标记故意谁都不引用；`<style>` / `<script>` 装卡即被抽出，不需要真正匹配命中，但匹配式本身仍按实机纪律写成合法 slash。

> **注意最后一条里的 `<\/script>`**：JSON 字符串里的 `</script>` 必须写成 `<\/script>`，避免宿主页面提前截断。`\/` 是合法 JSON 转义，解析回来就是 `/`。

### 3.2 字段说明与硬上限

| 字段 | 类型 | 说明 | 硬上限 |
|---|---|---|---|
| `chatVersion` | number | **必须是 `1`**，这是沙盒模式（新聊天页）的总开关。漏写或写 0 → 落回旧聊天页，规则照跑但 `sdk.*`、`[data-chat]`、舞台全部失效，页面上没有任何报错 | 必须 `1` |
| `pageDepth` | number | 固定 `2`。只对旧页有意义，**新页不实现**；非 2 官方判 WARN | 固定 `2` |
| `statusbar` | string | 功能栏触发标记位。会过一遍规则。**标准写法是只放 `{{hud}}`**，真界面写在规则里（200 字放不下界面） | **200 字** |
| `beginning` | string | 开场白，**玩家看见的第一句话，不是人设**。可夹触发串（如 `{{intro}}`） | **4000 字** |
| `personality` | string | 人设正文。**导入页不会读这个字段**，必须另出独立文本给用户手工粘贴（见 3.5） | **10000 字** |
| `regex_scripts` | array | 规则数组，每条恰好 4 键 | **130 条** |
| `regex_scripts[].id` | number | **必须是负数**（`-1`、`-2`…，不必连续），导入时平台会重编号。`typeof !== 'number'` 或 `>= 0` → ERROR | —— |
| `regex_scripts[].scriptName` | string | 规则名，非空 | UI 显示 **20** / 源码归一常量 **200**；双路径与超限语义待确证，交付按 20 |
| `regex_scripts[].findRegex` | string | 匹配式，非空；交付一律 slash 形态，见 3.3 | UI 显示 **1000** / 源码归一常量 **4096**；双路径与超限语义待确证，交付按 1000 |
| `regex_scripts[].replaceString` | string | 替换内容：HTML / `<style>` / `<script>` 全写在这里 | 编辑器 **20000** / 导入源码上限 **100000** |

规则里多余字段 → WARN；缺任一字段 → ERROR。

**禁止出现的顶层键**（官方直接判 ERROR，因为它们属于别的格式）：

```
role  presentation  worldbook  world_book  lorebook  lore_book  entries  characterBook  character_book
```

其余未知顶层键 → WARN（导入页不认）。世界书为什么不能塞进来见 3.5。

> `replaceString` 有两条录入路径：创卡页编辑器 **20000 硬上限**，超限会无提示拒绝保存整条修改；「导入正则」源码上限为 100000。默认仍按 18000 拆条，保证导入与手工维护都安全。

### 3.3 `findRegex`：worker 有两形态，交付只用 slash

worker 源码的 `classifyPattern` 确实包含裸字面量分支：非空非斜杠串会被转义后全文替换；`/pattern/flags` 编译为正则，缺 `g` 自动补。然而 `【实机实测 2026-08-26】` 裸字面量 `{{probe}}` 完全不生效，改成 `/{{probe}}/` 立即生效，说明宿主交给 worker 前还有未逆向到的处理层。

因此交付纪律只有一条：**MMD 沙盒的 `findRegex` 一律写 `/pattern/flags` slash 形态。** worker 字面量分支只作为逆向事实保留，不能作为可交付能力推荐。

| 写法 | 交付判定 | 行为 |
|---|---|---|
| `/{{hud}}/`、`/【图鉴】/` | ✅ 固定标记 | `{}` 在非量词位置可不转义；中文照常 |
| `/血量[:：]\s*(\d+)/` | ✅ 正则 | 合法 flags 仅 `gimsuy`；缺 `g` 平台自动补 |
| `/[未闭合/` | ❌ bad-regex | 整条规则静默丢弃，不降级字面量 |
| `{{hud}}` | ❌ 裸字面量 | worker 理论支持，但实机不生效，禁止交付 |
| 空串 | ❌ empty | ERROR |

两条会让规则永久失效、且页面上毫无迹象的坑：

1. slash 正则语法写错会整条静默丢弃，交付前必须让 `validate.py --platform mmdsandbox` 编译门禁通过。
2. 固定标记不要重复。规则按数组顺序跑，前一条换完全文后，后一条同串永远匹配不到。

匹配式别含 HTML 标签或独立保留字 `html/head/body/css`，也别写太松；规则会扫这张卡的每条 AI 消息。

### 3.4 触发串必须接得上（可见 HTML 才会出现）

**可见 HTML 的匹配式，必须能在 `statusbar` / `beginning` / 另一条规则的 `replaceString` 里找到**（链式触发被官方认可），否则页面上永不出现。人设 `<输出格式>` 里的输出约定必须和这些匹配式对得上 —— **模型写得出，规则才换得掉**。

反过来，只放 `<style>` / `<script>` 的规则，匹配式**故意谁都不引用**（`{{卡名-style}}` / `{{卡名-kit}}`）：它们装卡时就被抽走，不需要被匹配命中。这也意味着**不能靠「让规则不匹配」来关掉样式**。

### 3.5 三件交付物（沙盒模式特有）

| 交付物 | 内容 | 去哪 |
|---|---|---|
| `<短名>-regex.json` | 本节的 6 键导入 JSON | 创卡页「导入正则」入口 |
| `<短名>-persona.txt` | **未转义的人设纯文本** | **导入页不读 `personality` 字段** → 必须让用户手工粘贴到人设框 |
| `<短名>-worldbook.json`（可选） | 独立世界书，根对象**只留 `entries`** | 世界书独立导入入口 |

- `personality` **仍要写进 JSON**（供校验与留档），但**同时**必须另出一份纯文本。两份内容要一致。
- 世界书**不能**塞进导入正则 JSON（顶层出现 `entries` / `worldbook` / `characterBook` 等直接 ERROR），字段规范见 `worldbook-json.md`。
- 人设格式要点（`<角色设定 名字：真实角色名>` 成对单行标签、只用 `{{user}}`、禁 `{{char}}` / `$#char#$` / `$#user#$`、禁 `【章节】` 方括号标题）见 `card-json.md` 第 9 节。
- 交付说明里**必须写明「必须新建卡，并在创卡页确认这张卡是新页」** —— `chatVersion` 只在新建卡导入时被读取，给已存在的卡导入会被忽略，表现是「按钮全不响应、样式对一半」且无任何报错。

### 3.6 交付前强制审核

转义规则与生成方式**完全沿用 2.3 / 2.4**（换行转 `\n`、双引号转 `\"`、无 BOM、用 `json.dumps` 生成而非手写、回读查双重转义）。额外只多一条：JSON 里的 `</script>` 写成 `<\/script>`。

```bash
python <skill>/scripts/validate.py output/文件-regex.json --platform mmdsandbox
python <skill>/scripts/build-preview.py output/文件-regex.json --platform mmdsandbox
```

`--platform mmdsandbox` 下 `validate.py` 换的是一整套沙盒检查，**0 错误才能交付**：

- **结构**：顶层 6 键白名单 + 禁用顶层键；`chatVersion` 必须为 1；`id` 必须为负数；上表全部长度/条数上限。
- **匹配式**：每条必须是合法 `/pattern/flags`；裸字面量按实机策略判 ERROR；固定标记重复同样判 ERROR。
- **SDK**：能力名不在 30 能力表、事件名不在 12 事件表、用了不存在的 `sdk.once` / `sdk.off` → 全部 ERROR（平台侧写错名字**不报错只是永不触发**，只能靠静态校验拦）。
- **被禁写法**：`img onerror` 点火器与 teapot 系 → ERROR（官方明令，沙盒模式 `<script>` 装卡即执行，点火器不再有意义）。
- **WARN 项**：作者自写 `data-*`（会被净化删掉）；`iframe` / `link` / `meta` / `form` / `object` / `embed` 等被删标签；全局 CSS（`*{}` / `html{}` / `body{}` / `:root{}` → 改用 `[data-chat="root"]`）；HTML 缩进 4 空格（官方 WARN；实机当前会在 Markdown 前剥掉缩进，不据此断言会变代码块，仍保守顶格写）；`sdk.on` 写进 `message:mount` 回调（每挂一条气泡多订一份）；`message:done` 里 `message.send` 自问自答死循环。
- 世界书条目标题 20 字在沙盒模式是 **WARN**（当前 MMD 仍是 ERROR），理由见 `worldbook-json.md` 与 `../platforms/mmd-sandbox.md` §10.1。
- 若误把 chara_card_v2 卡传进来审沙盒，会 WARN 提示沙盒真正的交付物是本节的导入 JSON。

`build-preview.py --platform mmdsandbox` 使用共享契约 v1.1.0 复刻真实新聊天页：dark root flex 外壳、header/statusbar/messages/left/right、message-frame/message/message-body/message-extra/message-actions、author-stage、静态 composer/toolbar/input/send，以及 **14 个 `--chat-*` 设计令牌**。另注入 `--rpx`；`--chat-viewport-height` 由模拟宿主以内联 style 写入并随 iframe resize/键盘 inset 更新。未命中规则里的 `<style>/<script>` 仍装卡即抽出执行，但 script 审计角标只在诊断页展示，不挤占全景 iframe。预览自带 `chat`/`thin-preview` SDK profile、能力精度表、默认折叠的仿真控制与证据说明；真实宿主握手、AI 分块节奏、完整 Markdown/净化、跨设备 save、CSP 与最终人工验收仍需真实站。

## 第四节：MMD 手填清单（Markdown 交付物，备选）

当用户偏好手动录入或导入失败时使用。交付物格式如下：

````markdown
# <项目名> MMD正则配置清单

> 共N条（限额130）。逐条复制到MMD平台正则配置界面。
> 每条均已标注字符数；findRegex限1000字符，replaceString限20000字符。

## 规则1：<用途说明>

**findRegex**（填入"查找"框，X字符/限1000）：

```
/<status>/
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

### 4.1 清单生成规则

1. **每条带编号 + 用途说明**：标题格式 `## 规则N：<用途>`，便于追踪
2. **findRegex 与 replaceString 分开独立代码块**：每块单独全选复制，减少误操作
3. **字符数为实测值**：生成时统计并标注在括号内（如 `248字符/限1000`）
4. **末尾总条数核对行**：`总条数核对：N/130`，超过130条须拆分或合并规则
5. **每条勾选框**：`- [ ] 已填写`，手填完毕后勾选，避免遗漏

### 4.2 MMD 平台填写注意事项

- **findRegex 两个 MMD 路线都填 `/pattern/flags` 外层斜杠**，固定标记也写成 `/<标记>/`；沙盒 worker 的字面量分支不能抵消实机裸值不生效的结论
- replaceString 字段：如含 HTML，注意转义确认界面接受原始 HTML
- 每条填写后建议发条测试消息验证效果，再勾选 `- [ ] 已填写`
- MMD 平台正则仅作用于显示层（等效 markdownOnly=true）
- 沙盒模式手填时**别忘了创卡页表单里的 `chatVersion`**：手填清单只覆盖规则，`chatVersion: 1` 要用户在创卡页自己确认（默认是 0），漏了整套方案零效果
