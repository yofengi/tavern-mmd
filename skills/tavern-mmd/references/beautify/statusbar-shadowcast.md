# 影渲法（ShadowCast 2.0）—— Shadow DOM 隔离动态渲染框架

> 当前 MMD（魅魔岛/sexyai.top）**实测验证**（11 靶探针 + 浏览器实机 + node 逻辑测试）的隔离式渲染方法。"影"=Shadow DOM 隔离，"渲"=渲染，对仗雷达法。
> **不止状态栏**：同一套地基可做状态栏、可拖动悬浮球、侧边栏抽屉——凡"自包含、只管好自己"的 UI 组件皆可。**全局美化不可用**（它要穿透改平台元素，与隔离相反，见末节）。
> 现成生成器在仓库 `g3-demo/`（`build_demo.py` 状态栏、`build_float.py` 悬浮组件），改字段/改配色即可复用。
> **2.0 强化（吸收哨兵雷达法 sd3 卡【280366】实测优点，浏览器三路验证通过）**：① shadow→light DOM 降级链，attachShadow 不可用环境照常渲染；② `adoptedStyleSheets` + 跨气泡缓存单张 sheet；③ 事务式渲染（建好再挂载，异常回退纯净态）。详见末节「2.0 强化」。

## 一句话内核

模型每轮吐**全量快照**到 light DOM 隐藏 span → `img onerror` 点火 → `attachShadow` 把 UI 渲进 **shadow root**（隔离）→ 数据留 light（可扫描跨轮恢复）、UI 进 shadow（不过 markdown、不被染色）。

## 与雷达法 / KV V4.0 的选型对比

| 维度 | 影渲法（本文档） | 雷达法（statusbar-radar.md） | KV V4.0（statusbar.md） |
|---|---|---|---|
| UI 载体 | **Shadow DOM**（隔离） | light DOM + 防御补丁 | light DOM 预制骨架 |
| markdown 空白条 | **免疫**（shadow 不过 markdown 管线） | 需源头压平 + 三件套防御 CSS | 需防御 CSS |
| 平台强制染色 | **免疫**（shadow 边界天然挡） | 需 MutationObserver 哨兵剥离 | 无防御 |
| CSS 类名冲突 | **免疫**（shadow 内隔离，无需前缀） | 需 `z-` 前缀 | 需前缀 |
| 防平台重绘 | onerror 重新点火自动水合（幂等）；2.0 事务回退不留破碎 UI | 探针自检 + 2.5s 重建 | 无 |
| 环境降级 | **2.0 shadow→light DOM 自动兜底**（attachShadow 禁用也渲染） | 本就 light DOM | 本就 light DOM |
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
  → buildPanel() 在内存里建好整个面板（不挂载）
  → shadowOf(box)：box.shadowRoot || (box.attachShadow ? box.attachShadow(...) : null)
      ├─ 拿到 shadow root → applyCss(sr)（adoptedStyleSheets 缓存单 sheet / <style> 兜底）→ 挂 panel
      └─ 返回 null（环境禁 Shadow DOM）→ styleLight() 注 CSS 到 document → panel 挂进 light DOM
  → 成功才 setAttribute('data-g3v','sc2')；任何异常 catch → resetPlain()（移半成品+记 g3LastError）
  ▼
shadow 路径：UI 不过 markdown、不被染色、CSS 隔离（首选）
light 路径：g3- 前缀类名零冲突，面板照常显示（降级兜底，不再静默消失）
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

## 富 UI 状态栏（雷达法移植，`assets/shadowcast-examples/` 的 `shadowcast_core.py`）

`build_demo.py` 只有 `bar`/`text`/`list` 三类型，适合简单固定面板。要做雷达法那种 RPG/养成富交互状态栏（面包屑地点、带 tooltip 的资源条、XP 条、属性网格、装备名↔说明交叉绑定、可切页背包、敌人卡、可点击选项写回输入框），用 `radar-converted/` 的 **`shadowcast_core.py` 共享引擎**——同一影渲法地基（shadow 隔离 + 2.0 降级链 + 事务渲染），但内置更多字段类型：

| type | 渲染 | 协议格式 |
|---|---|---|
| `path` | 面包屑 chips + › 箭头 | `大陆-国家-地标-房间` |
| `time` | 高亮时段词 | `年月日 黄昏` |
| `bar` | 资源条；值带 `\|成因` → hover tooltip | `45/45` 或 `15\|圣骑士庇护` |
| `level` | 名 + (经验/阈值) + XP 条 | `3级精灵\|100/300` |
| `stats` | chips 网格（`属性:值:成因` 带 tooltip） | `体质:10,力量:8` |
| `kvlist` | 槽位：名（名带 hover 说明） | `头饰:月夜辉冠\|感知+3` |
| `lines` | 编号记录列表 | `1.初见\|2.密谈\|3.异样` |
| `summary` | 斜体摘要 | `3/3\|阶段回顾...` |
| `turn` | 区块标题右上角角标 | `5` |
| `bag` | 可切页背包(◀▶ 导航) | multi：`消耗品\|药剂/卷轴` |
| `enemy` | 敌人卡（红边+HP条+属性格），volatile | multi：`石像鬼\|28/40\|AC:14\|左翼碎裂` |
| `option` | 可点击按钮，写回 `.uni-textarea-textarea`（♥→ero样式），volatile | multi：`简介\|内容` |

`build_rpg.py`（西幻RPG）/`build_manor.py`（宅邸养成）是两个**只含 config** 的场景脚本（FIELDS + 主题 CSS + 标题），引擎全复用 core——改 bug 只动 core，所有场景同步。`multi:True` 字段允许同名键重复（read 累积成数组）。这套由雷达法资产转换而来：转后删掉雷达法整套对抗哨兵补丁（引号修复/font→span/染色哨兵）与信标转换器（`/\[k=v\]/` 扫整条气泡），换成单块 `<g3>` 捕获 + shadow 隔离。**全局美化部分不可转**（穿透 vs 隔离相反，见末节）。

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

## 2.0 强化（吸收哨兵雷达法优点，2026-06-18 浏览器三路验证）

哨兵雷达法作者的卡【280366】（VER=`sd3`）把弱边界协议嫁接到了 Shadow 地基，其工程上有三点比影渲法 1.0 更硬，已并入生成器引擎（`build_demo.py`，VER=`sc2`）。三点都在浏览器实机验证：shadow 正常路径 `data-g3v=sc2 / adoptedStyleSheets=1 / 4 行渲染`；禁用 `attachShadow` 后 light 路径 `hasShadow=false / 面板照常 4 行 / CSS 注入 document`；强制 `createElement` 中途抛错后 `leftoverPanel=false / g3LastError 已记 / 数据 span 完好`。

### 强化1：shadow→light DOM 降级链（鲁棒性头条）

1.0 直接 `box.shadowRoot||box.attachShadow({mode:'open'})`——若环境禁用 Shadow DOM（旧 WebView、平台策略），`attachShadow` 抛错 → 整个面板**静默消失**。2.0 改 `shadowOf()` 探测：

```javascript
var shadowOf=function(b){
try{return b.shadowRoot||(b.attachShadow?b.attachShadow({mode:'open'}):null);}
catch(e){return null;}
};
```

拿到 shadow root 走隔离路径（首选）；返回 null 则走 light DOM 兜底（`styleLight()` 把 CSS 注 document 一次 + panel 直接 `box.appendChild`）。**前提**：CSS 类名全程 `g3-` 前缀（`.g3-panel`/`.g3-row`/…），light 路径注入 document 才零冲突——这是 1.0 用裸 `.panel`/`.row` 时做不到降级的原因，2.0 一并改了前缀。

> 影渲法的数据本就在独立 `.g3-data` 隐藏 span，light 兜底只需 append 面板，**不需要**哨兵卡那套 `wl-hide`（字号归零/透明）隐藏原文的隐藏术——那是哨兵法"扫整条气泡正文重构"才需要的，影渲法数据视图本就分离，省掉。

### 强化2：adoptedStyleSheets + 跨气泡缓存单 sheet

1.0 每条消息都 `createElement('style')` 塞进各自 shadow root（N 条消息 = N 份相同 CSS 文本）。2.0 `applyCss()` 优先用 `adoptedStyleSheets`，并把构造好的 `CSSStyleSheet` 缓存在 `window[_g3Sheet]`，所有气泡共享同一张：

```javascript
var applyCss=function(sr){
if(sr.adoptedStyleSheets!==undefined&&window.CSSStyleSheet){
try{
var key=us+'g3Sheet';
var sh=window[key];
if(!sh){sh=new CSSStyleSheet();sh.replaceSync(CSS);window[key]=sh;}
sr.adoptedStyleSheets=[sh];return;
}catch(e){}
}
var st=document.createElement('style');st.textContent=CSS;sr.appendChild(st);  // 兜底
};
```

`us=String.fromCharCode(95)`（下划线，避免裸标识符问题）。不支持 `adoptedStyleSheets` 的环境自动退 `<style>` 节点，行为与 1.0 一致。

### 强化3：事务式渲染（异常显性化，不留破碎 UI）

1.0 边建边挂（`sr.appendChild(panel)` 后才逐字段填充），中途抛错会留下半个面板。2.0 把整段 render 包进 try/catch：`buildPanel()` 在内存里把面板**整个建好**，最后一步才 `appendChild` 挂载；任何异常 → `resetPlain()`（移除半成品、清 shadow、`data-g3v` 不打标）+ `window.g3LastError=e` 留痕调试。**数据 span 始终完好**，下条消息 onerror 重新点火可干净重渲。对应影渲法早就主张的"异常不应被漂亮 UI 掩盖"原则，1.0 没在引擎层落实，2.0 补上。

### 没有吸收的（边界说明）

哨兵卡还有弱边界"键：值"自然语言协议、RPG 储物袋三级 UI、`MutationObserver` 常驻扫描等。这些**未并入**：①影渲法是 schema 驱动（字段预定义、`<g3>` 标记包裹），强结构换来构建期键名三方一致断言，与哨兵法"无信标自由涌现"是不同取向，不混；②储物袋等是具体 UI 形态，属"换皮"层（改 `FIELDS` + shadow CSS 即可自行扩展），非地基能力。需要"模型自由涌现新键名"仍走雷达法（见选型表）。

### 强化4：key 同义词归一化（吸收哨兵 norm() 思想，但不改强边界协议）

> 评估过"整体换弱边界行锚协议"，结论是**赔本**：弱边界用影渲法的核心长处（强边界确定性提取、数据藏 span 不依赖换行存活、构建期键名断言）去换它本就不缺的东西（无信标/自由涌现是影渲法有意舍弃的取向），且作者自承需"协议修复层"（未建）。故协议主体不动，**只借**其 `norm()` 的 key 容错这一项纯增益。

模型可能把 `hp` 写成 `HP`/`生命`/`血量`。2.0 引擎加一张归一化表 `ALIAS`（别名小写 → 标准 key），`read()` 解析每个键时 `normKey(k)` 先查表再存：

```javascript
var ALIAS={'hp':'hp','生命':'hp','血量':'hp','mood':'mood','情绪':'mood',...};
var normKey=function(k){var n=ALIAS[k.toLowerCase()];return n?n:k;};
// read() 内：if(k)o[normKey(k)]=pair.slice(i+1).trim();
```

- 别名在 `FIELDS` 每字段 `aliases:[...]` 一处声明（仍单一真相源），生成器构建 `ALIAS` 表注入引擎，并在协议文档字段表加「可接受别名」列。
- **不破坏三方键名断言**：断言比的是标准 `key`，别名只是输入侧容错。
- **归一化在 `read()` 入口**，所以跨气泡历史继承也走标准 key——实测 A 气泡写 `血量=55/100`、B 气泡省略 hp，B 正确继承 55%（两边都归一到 `hp` 再折叠）。
- 协议仍**推荐标准键名**（最稳），别名仅兜底，不鼓励模型刻意发散。

---

## 全局美化为何不可影渲法化

全局美化的目的是"我的 CSS 要**穿透**到平台每个气泡/按钮去改它们"，Shadow DOM 的作用是"把里面的样式跟外界**隔离**"——正好相反。把全局美化放进 shadow，CSS 出不去、平台元素一个改不到。全局美化仍用现有穿透方案（正则包裹 + uni-app 类名覆盖 + `!important` + body 开关类，见 global-css.md）。

**判据**：组件"只管好自己"→ 影渲法加分；需求"要改别人"（仅全局美化这一类）→ 影渲法帮倒忙。

---

## 与 mmd.md 的关系

平台级实测事实（attachShadow 可用、shadow 不过 markdown、自定义标签存活、聊天在 chatIframe 内、正则在 markdown 前跑、script 不持久）见 `../platforms/mmd.md` §6b、§7。本文档专注影渲法本身的架构与写法。换风格（配色/字体/布局）见 `style-system.md`——只换 shadow 内 CSS 的变量值，引擎逻辑不动。
