# 影渲法（ShadowCast）—— Shadow DOM 隔离动态渲染框架

> 当前 MMD（魅魔岛/sexyai.top）**实测验证**（11 靶探针 + 浏览器实机 + node 逻辑测试）的隔离式渲染方法。"影"=Shadow DOM 隔离，"渲"=渲染，对仗雷达法。
> **不止状态栏**：同一套地基可做状态栏、可拖动悬浮球、侧边栏抽屉——凡"自包含、只管好自己"的 UI 组件皆可。**全局美化不可用**（它要穿透改平台元素，与隔离相反，见末节）。
> 现成生成器在仓库 `g3-demo/`（`build_demo.py` 状态栏、`build_float.py` 悬浮组件），改字段/改配色即可复用。

## 一句话内核

模型每轮吐**全量快照**到 light DOM 隐藏 span → `img onerror` 点火 → `attachShadow` 把 UI 渲进 **shadow root**（隔离）→ 数据留 light（可扫描跨轮恢复）、UI 进 shadow（不过 markdown、不被染色）。

## 与雷达法 / KV V4.0 的选型对比

| 维度 | 影渲法（本文档） | 雷达法（statusbar-radar.md） | KV V4.0（statusbar.md） |
|---|---|---|---|
| UI 载体 | **Shadow DOM**（隔离） | light DOM + 防御补丁 | light DOM 预制骨架 |
| markdown 空白条 | **免疫**（shadow 不过 markdown 管线） | 需源头压平 + 三件套防御 CSS | 需防御 CSS |
| 平台强制染色 | **免疫**（shadow 边界天然挡） | 需 MutationObserver 哨兵剥离 | 无防御 |
| CSS 类名冲突 | **免疫**（shadow 内隔离，无需前缀） | 需 `z-` 前缀 | 需前缀 |
| 防平台重绘 | onerror 重新点火自动水合（幂等） | 探针自检 + 2.5s 重建 | 无 |
| 数据持久/恢复 | light span 全量快照，扫历史折叠兜底 | 扫历史键值对兜底 | 继承链（易断） |
| 长线防中毒 | **双轨代谢**（固态继承/情境用完即焚） | 双轨生命周期（液态快照无兜底） | 无 |
| 工程复杂度 | 中（生成器产出，引擎随字段恒定） | 高（引擎~13K，需 AI 辅助） | 低（三段固定模板） |
| 成熟度 | 新（已 11 靶验证 + demo，长线实战待积累） | 成熟（实战打磨、示例多） | 成熟 |
| 适用 | 追求干净隔离的状态栏/悬浮组件 | 长线复杂数据、需嗅探未知键名 | 快速原型、极简固定面板 |

**选型建议**：动态状态栏与悬浮组件 → 影渲法（隔离最省心）或雷达法（成熟、示例多），二者数据恢复地基相同；固定字段 → 原生 `$field` / KV V4.0；需"模型自由涌现新键名" → 雷达法（影渲法是 schema 驱动，字段预定义）。

---

## 三条铁律（生成引擎时逐条核对，全是实机踩出来的）

影渲法引擎整段塞进 `onerror="..."` 属性（双引号包裹）。

### 铁律1：onerror 内部禁裸双引号 `"`（否则面板静默不渲染、不报错）

`onerror="..."` 双引号包裹，引擎内任何 `"` 会提前闭合属性 → 后面 JS 拆成无效裸属性 → img 结构破坏 → onerror 没绑上 → **既不报错也不渲染**（最隐蔽的失败）。
- 引擎内所有字符串字面量**全程单引号**。
- 注入的配置（CFG/CSS）用**单引号 JS 字面量序列化**（自写序列化器），**绝不能用 `JSON.stringify`/`json.dumps`**（产双引号）。

> **⚠️ 已撤销的伪铁律（2026-06-17 纠正）**：曾误立"禁裸 `<`/`>`/`=>`"，后经浏览器+MMD 实机三组对照证伪——onerror **引号内**的裸 `<`/`>` 是纯文本，HTML 属性值不解析标签，**无害**。雷达法引擎满是 `i<n`/`c>0`/`nIdx>=len` 实战正常即铁证。当初 g3 demo "断在 `j>=0`" 的暴露，真因是**内部双引号**（CFG 用 json.dumps）在更前面闭合了属性，`>` 只是碰巧在那行。比较运算、for 循环、箭头函数**可正常使用**，无需改写。

### 铁律2：禁字面 `[键=值]`（信标转换器会啃断）

若项目含数据信标转换器（正则 `/\[..=..\]/`），它会扫整条消息 HTML（含 onerror 内 JS 源码字符串），把字面 `[键=值]` 替换成 `<span>` → 啃断 JS。
- 方括号用 `String.fromCharCode(91)`/`(93)` 拼。**连 CSS 选择器 `input[type=text]` 也要拼**（`[type=text]` 命中信标模式）。
- 数组索引 `arr[0]`、对象 `obj[k]` 安全（方括号内无 `=`）。

### 铁律3：findRegex 必须带 `/.../ ` 斜杠分隔符

不带斜杠（如 `\[k=([^\]]+)\]`）时平台正则控制台测试能过、**实际聊天界面不替换**。每条 findRegex 务必 `/pattern/flags` 形式。

> 用生成器（`build_demo.py`/`build_float.py`）则前两条由**构建期 guard 自动拦截**（扫引擎 JS 体：内部裸双引号、字面 `[键=值]` 直接报错），手写才需逐条自查。`validate.py` 也检查内部双引号（真红线）。

---

## 状态栏写法

### 数据流

```
模型每轮吐全量快照 <g3>hp=85/100;mood=害羞;...</g3>
  │ 正则 /<g3>([\s\S]*?)<\/g3>/ →（捕获组 $1 放进隐藏 span）
  ▼
<div class="g3-host"><span class="g3-data" style="display:none">$1</span>
  <img src=x style="display:none" onerror="引擎">
</div>
  │ onerror 点火（per-message，script 不持久故必用 onerror）
  ▼
引擎：读同气泡 .g3-data → split 解析 → 缺失字段扫历史 .g3-host 折叠兜底
  → box.shadowRoot || box.attachShadow({mode:'open'})（已有则复用，幂等防重影）
  → createElement 装配进 shadow root
  ▼
shadow 内 UI（不过 markdown、不被染色、CSS 隔离）
```

### 关键设计点

- **数据在 light DOM 隐藏 span**：实测其 textContent 经 markdown 后**一字不差**（含 `*`/`|`/`/`），可被后续消息全局扫描做跨轮恢复。**绝不把数据放 shadow 内**（shadow 跨气泡扫不到、reload 即失）。
- **每轮全量快照**：per-message 渲染**无跨气泡状态**（实测 localStorage 跨气泡读为 NULL），不可依赖"只吐变化+继承"；引擎侧虽有历史兜底，但模型全量最稳。
- **host 留在气泡内**：状态栏属于该消息、随气泡走、per-message 更新。**不可挂 body**（会变全局单例、没法逐条更新）。

### 双轨代谢（长线防中毒，零额外 token）

字段分两类，由单一真相源 `FIELDS` 的 `volatile` 标记驱动：

| 类型 | 标记 | 引擎行为 | 模型协议 | 例子 |
|---|---|---|---|---|
| 固态 | 默认 | 缺失时向历史折叠兜底 | 每轮必出（即使没变） | hp/mood/loc/npc |
| 情境（液态代谢） | `volatile:True` | **不兜底**，缺失即不渲染 | **仅情境那轮输出，结束就停** | 战斗遭遇/极端感官状态 |

代谢本质：情境字段是高刺激信息，残留在历史会让模型过度推演（长线"智商下降"）。影渲法的代谢=**模型不再吐 + 引擎不兜底**，面板随之消失，数据层 light span 仍可追溯。**零额外 token**——反而因模型不必每轮复述情境字段而省。

> 生成器把 `volatile` 映射成引擎 CFG 的 `inherit:false`（复用已有折叠分支，引擎逻辑零改动），并自动生成协议文档里"情境字段只在该情境输出"的指示。

---

## 悬浮组件写法（悬浮球 / 侧边栏）

与状态栏同地基，但 **host 归属相反**——这是关键区别，挂错就坏：

| | host 挂哪 | 为什么 |
|---|---|---|
| 状态栏 | **留消息气泡内** | 属于该消息、per-message 更新 |
| 悬浮球/侧边栏 | **挂 `document.body`** | 全局唯一常驻，浮在所有消息之上 |

### 悬浮球要点（实测全绿）

- **挂 body 挣脱气泡 stacking context**：`document.body.appendChild(wrap)`，shadow 内 `position:fixed` + `z-index:2147483647`，浮在消息气泡和输入框之上（解决"放开场白球被消息盖住"）。
- **单例防重**：`if(document.getElementById('zsf-ball-wrap'))return;`——每条消息 onerror 都触发，但已存在就跳过，屏幕只有一个球。reload 后球消失、再发消息重新点火重建（script/DOM 不持久，正常）。
- **拖动**：`mousedown/touchstart` 记起点 → `mousemove` 改 `style.left/top`（单属性放行）→ 移动超 3px 记为拖动、否则算点击展开菜单。本体夹取进视口（`Math.max/min`，注意铁律1 不能用 `<`/`>`）。
- **菜单跟随 + 翻转避裁**：拖动时 `reposition()` 重算菜单坐标；上方放得下放上方、否则翻下方；水平夹取进视口。
- **回填输入框**：选择器用 `'textarea, input'+LB+'type=text'+RB`（LB/RB 由 `fromCharCode` 拼，避铁律3），`dispatchEvent(new Event('input',{bubbles:true}))`。

### 跨 shadow 交互（已验证）

悬浮球菜单可操作侧边栏：`document.getElementById('zsf-drawer-wrap').shadowRoot.querySelector('.drawer').classList.add('open')`——穿过两个独立 shadow root 成立。

### 事件绑定

shadow 内 `el.onclick=function(){}` 与 `el.addEventListener` 两种都通（实测靶9）。最外层 `ev.stopPropagation()` 防冒泡到气泡。

---

## 生成器工作流（`g3-demo/`）

1. **改单一真相源**：`build_demo.py` 的 `FIELDS`（状态栏字段：key/label/type/format/example/volatile）或 `build_float.py` 的 `MENU_ITEMS`/`DRAWER_ITEMS`/`COLORS`。
2. **生成**：`python build_demo.py`（产 `g3-statusbar.mmd.json` + `协议.md`）/ `python build_float.py`（产 `float-shadow.mmd.json`）。
3. **构建期 guard 自动校验**：内部裸双引号、字面`[键=值]`、字符数 ≤20000/1000、findRegex 带斜杠、键名三方一致（字段=引擎 CFG=测试数据）。（裸 `<`/`>` 经实机证实无害，不查。）
4. **审核**：`python scripts/validate.py <json> --platform mmd` 须 0 错（已认识影渲法，不误报悬空/反斜杠）。
5. **预览**：`python scripts/build-preview.py <json> --platform mmd`，浏览器/Preview 工具看渲染与交互（已支持影渲法引擎）。
6. **实机导入 MMD** 验收（shadow/markdown/iframe 真实环境，沙箱复现不了全部）。

### 单一真相源消灭多处对齐

`FIELDS` 一处定义 → 生成器产出引擎 CFG、模型协议、测试数据三者并 assert 键名一致。改字段只动一处，对齐由构建期断言保证，不靠人脑（对比雷达法改字段要四处手动对齐）。引擎逻辑**不随字段数增长**（通用解释器只认结构类型 bar/text/list，业务键名是数据），故 20000 字符限额几乎碰不到。

---

## 全局美化为何不可影渲法化

全局美化的目的是"我的 CSS 要**穿透**到平台每个气泡/按钮去改它们"，Shadow DOM 的作用是"把里面的样式跟外界**隔离**"——正好相反。把全局美化放进 shadow，CSS 出不去、平台元素一个改不到。全局美化仍用现有穿透方案（正则包裹 + uni-app 类名覆盖 + `!important` + body 开关类，见 global-css.md）。

**判据**：组件"只管好自己"→ 影渲法加分；需求"要改别人"（仅全局美化这一类）→ 影渲法帮倒忙。

---

## 与 mmd.md 的关系

平台级实测事实（attachShadow 可用、shadow 不过 markdown、自定义标签存活、聊天在 chatIframe 内、正则在 markdown 前跑、script 不持久）见 `../platforms/mmd.md` §6b、§7。本文档专注影渲法本身的架构与写法。换风格（配色/字体/布局）见 `style-system.md`——只换 shadow 内 CSS 的变量值，引擎逻辑不动。
