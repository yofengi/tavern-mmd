# 状态栏方案：KV V4.0（轻量备选）

> **MMD状态栏首选混合态雷达法**（`statusbar-radar.md`）：更省token、防崩溃、自适应、支持未知键名嗅探。
> 本文档的 KV V4.0 作为轻量备选保留，适合：快速原型、字段固定的极简面板、不想引入大体积引擎的场景。

## 平台分流

| 平台 | 方案 |
|---|---|
| 旧版MMD | 首选雷达法（statusbar-radar.md）；轻量场景用本文档 KV V4.0 |
| 当前MMD | 同旧版 |
| 本地酒馆 | 雷达法/KV V4.0 均可直接使用 |

> 平台技术红线（ES5、单行JS、img须在容器内等）见 `../platforms/mmd-old.md`，本文档专注状态栏本身。

---

## KV V4.0 架构

### 核心概念：标记触发 + 数据分离

采用简单的 `<status>` 标记触发正则替换，数据通过 HTML 属性传递：

```html
<status>
<div class="z-status-data" style="display:none">
<div data-env tm="3月15日 23:47" loc="金龙园区" goal="调查失踪案" rd="现场杂乱" chars="阿昌,老李"></div>
<div data-st npcs="阿昌|组长|-15,老李|医务室|22" clues="咖啡杯有唇印,窗户没关"></div>
<div data-opt c1="返回宿舍|安全休息|low|safe" c2="找老李|打探消息|medium|opportunity"></div>
</div>
```

### 架构工作流程

```
AI输出: <status> + 数据块
         ↓
正则匹配: 找到 <status> 标记
         ↓
替换为: 完整HTML结构模板
         ↓
img onerror 触发解析函数
         ↓
JS读取数据块，填充到 data-field 位置
```

### 架构优势

| 维度 | 说明 |
|:---|:---|
| **稳定性** | `<status>` 是固定标记，不会因数据变化匹配失败 |
| **可读性** | HTML属性格式，一目了然 |
| **继承支持** | 支持跨消息数据继承 |
| **Token效率** | 仅输出变化部分，节省90% |
| **维护成本** | 单个JS函数统一解析 |

---

## 数据格式规范

### data-env 属性表

| 属性 | 含义 | 示例 | 是否继承 |
|:---|:---|:---|:---|
| `tm` | 时间 | `3月15日 23:47` | ✅ |
| `loc` | 地点 | `金龙国际园区` | ✅ |
| `goal` | 当前目标 | `调查失踪案` | ✅ |
| `rd` | 现场记录 | `桌上有半杯咖啡` | ✅ |
| `chars` | 在场人员 | `阿昌,老李,茜` | ✅ |
| `warn` | 警告信息 | `业绩落后` | ❌ |

### data-st 属性表

| 属性 | 含义 | 格式 | 是否继承 |
|:---|:---|:---|:---|
| `nm` | 姓名 | 字符串 | ✅ |
| `jb` | 职业 | 字符串 | ✅ |
| `mn` | 金钱 | 数字 | ✅ |
| `day` | 天数 | 数字 | ✅ |
| `zy` | 资源条 | `名称:当前/最大,名称2:当前2/最大2` | ✅ |
| `st` | 状态标签 | `中毒,虚弱` | ✅ |
| `npcs` | NPC列表 | `姓名\|角色\|好感度,姓名2\|角色2\|好感度2` | ✅ |
| `clues` | 线索列表 | `线索1,线索2,线索3` | ✅ |
| `bag` | 物品列表 | `物品名\|数量,物品2\|数量2` | ✅ |
| `sthr` | 当前威胁 | 字符串 | ❌ |
| `sopp` | 当前机遇 | 字符串 | ❌ |
| `stsk` | 待办事项 | 字符串 | ❌ |

### data-opt 格式

```
c1="标题|描述|风险|类型"
c2="标题|描述|风险|类型"
c3="标题|描述|风险|类型"
c4="标题|描述|风险|类型"
```

- 风险：`low` / `medium` / `high`
- 类型：`safe` / `opportunity` / `risky` / `normal`

示例：`c1="返回宿舍|安全休息|low|safe"`

### 分隔符速查表

| 分隔符 | 用途 | 示例 |
|:---|:---|:---|
| `\|` | 分隔同一条目的子项 | `茜\|目击者\|15` |
| `,` | 分隔不同条目 | `茜\|目击者\|15,真红\|嫌疑人\|-20` |
| `:` | 分隔资源名称和值 | `hp:65/100` |
| `/` | 分隔当前值和最大值 | `65/100` |

### 列表格式详解

**资源条 `zy`**：
```
名称:当前值/最大值,名称2:当前值2/最大值2
```
示例：`zy="hp:65/100,mp:45/60,饥饿:3/10,体力:7/10"`

**NPC列表 `npcs`**：
```
姓名|角色|好感度,姓名2|角色2|好感度2
```
示例：`npcs="茜|目击者|15,真红|嫌疑人|-20,老李|线人|8"`

**线索列表 `clues`**：
```
线索1,线索2,线索3
```
示例：`clues="咖啡杯有唇印,窗户没关,地上有脚印"`

**物品 `bag`**：
```
物品名|数量,物品名2|数量2
```
示例：`bag="香烟|3,馒头|1,止痛药|2"`

**选项 `c1-c4`**：
```
标题|描述|风险|类型
```
示例：`c1="询问茜|了解当时情况|low|safe"`

### 完整格式示例（首条消息）

```html
<status>
<div class="z-status-data" style="display:none">
<div data-env tm="3月15日 14:30" loc="咖啡厅二楼" goal="调查失踪案" rd="桌上有半杯咖啡，似乎有人匆忙离开。窗户半开，地上有泥土脚印。" chars="茜,真红,老李"></div>
<div data-st nm="柑硕" jb="调查员" day="7" mn="5000" zy="hp:85/100,mp:60/80,精力:7/10,饥饿:3/10" st="正常" npcs="茜|目击者|15,真红|嫌疑人|-20,老李|线人|8" clues="咖啡杯上有唇印,窗户没关,地上有泥土脚印" bag="笔记本|1,相机|1,现金|500"></div>
<div data-opt c1="询问茜|了解当时情况|low|safe" c2="质问真红|直接对质|high|risky" c3="检查窗户|寻找线索|low|opportunity" c4="联系老李|获取情报|medium|normal"></div>
</div>
```

### 精简格式示例（后续仅更新变化部分）

```html
<status>
<div class="z-status-data" style="display:none">
<div data-env tm="3月15日 15:00" rd="茜回忆起当时看到一个戴帽子的可疑人影从后门离开"></div>
<div data-st zy="hp:85/100,mp:55/80,精力:6/10,饥饿:4/10" npcs="茜|目击者|20,真红|嫌疑人|-20,老李|线人|8" clues="咖啡杯上有唇印,窗户没关,地上有泥土脚印,茜看到可疑人影从后门离开"></div>
<div data-opt c1="追问细节|深入了解可疑人特征|low|safe" c2="去后巷|追踪可疑人|medium|risky" c3="调取监控|获取视频证据|low|opportunity" c4="休息一下|整理目前线索|low|normal"></div>
</div>
```

---

## 数据继承机制

### 继承原理

当前消息的数据区未提供某字段时，解析函数自动向上遍历历史消息，查找最近一次该字段的值。

### 继承规则配置表

| 数据类型 | 是否继承 | 说明 |
|:---|:---|:---|
| `data-env` | ✅ 继承 | 时间地点等环境信息不常变 |
| `data-st` 基础属性 | ✅ 继承 | 姓名、职业等基本不变 |
| `data-st` 列表数据 | ✅ 继承 | npcs/clues/bag 等 |
| `data-st` 处境描述 | ❌ 不继承 | sthr/sopp/stsk 每次不同 |
| `data-opt` | ❌ 不继承 | 选项每次都不同 |

### Token节省效果表

| 场景 | 传统方式 | 继承方式 | 节省比例 |
|:---|:---|:---|:---|
| 首条完整数据 | ~500字符 | ~300字符 | 40% |
| 后续仅更新HP | ~500字符 | ~50字符 | **90%** |
| 后续仅更新选项 | ~500字符 | ~100字符 | **80%** |
| 10轮对话累计 | ~5000字符 | ~800字符 | **84%** |

### findData 继承代码实现

```javascript
var findData = function(selector, currentOnly) {
  // 1. 先在当前状态栏查找
  var dataBox = box.querySelector('.z-status-data');
  if (dataBox) {
    var found = dataBox.querySelector(selector);
    if (found) return found;
  }
  // 2. 不继承则返回null
  if (currentOnly) return null;
  // 3. 向上遍历历史状态栏
  var allBoxes = document.querySelectorAll('.z-status-box');
  var idx = -1;
  for (var i = 0; i < allBoxes.length; i++) {
    if (allBoxes[i] === box) { idx = i; break; }
  }
  for (var j = idx - 1; j >= 0; j--) {
    var prevData = allBoxes[j].querySelector('.z-status-data');
    if (prevData) {
      var found = prevData.querySelector(selector);
      if (found) return found;
    }
  }
  return null;
};

// 使用示例
var env = findData('div[data-env]', false);  // 允许继承
var st = findData('div[data-st]', false);    // 允许继承
var opt = findData('div[data-opt]', true);   // 不继承，每次必须提供
```

---

## 三段正则模板（交付时复制用）

本系统使用3条正则规则，每条规则的 replaceString 必须原样完整复制，不得修改任何字符。

| 规则序号 | 规则名称 | findRegex | 用途 | 字符数量级 |
|:---|:---|:---|:---|:---|
| 1 | 状态栏结构 | `<status>` | 输出容器+CSS | ~4000 |
| 2 | HTML内容 | `<!-- Z_CONTENT -->` | 输出主HTML结构 | ~3500 |
| 3 | JS解析器 | `<!-- Z_SCRIPT -->` | 输出JS解析逻辑（含findData继承） | ~4000 |

---

### 规则1：容器 + CSS

**findRegex**：`<status>`

**用途**：将 AI 输出的 `<status>` 标记替换为外层容器和完整 CSS 样式定义，并在末尾留下 `<!-- Z_CONTENT -->` 锚点供规则2继续替换。

**replaceString**（全文原样，~4000字符）：

```
<div class="z-status-box" onclick="event.stopPropagation()"><style>.z-status-box{--bg:#0d1117;--bg2:#161b22;--border:#30363d;--t1:#e6edf3;--t2:#8b949e;--t3:#484f58;--accent:#58a6ff;--danger:#f85149;--success:#3fb950;--gold:#d29922;font-family:system-ui,sans-serif;background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:0;margin:16px 0;overflow:hidden}.z-status-box *{box-sizing:border-box;margin:0;padding:0}.z-status-box::before,.z-status-box::after{content:'';position:absolute;width:12rem;height:12rem;border-radius:50%;filter:blur(80px);pointer-events:none;opacity:0.4}.z-status-box::before{top:-6rem;left:-6rem;background:rgba(88,166,255,0.1)}.z-status-box::after{bottom:-6rem;right:-6rem;background:rgba(210,153,34,0.08)}.z-status-header{background:linear-gradient(135deg,#1a1f2e,#0d1117);padding:16px;border-bottom:1px solid var(--border)}.z-status-title{font-size:14px;color:var(--t1);font-weight:600}.z-status-env-tabs{display:flex;gap:8px;padding:12px 16px;background:var(--bg2);border-bottom:1px solid var(--border)}.z-status-env-tab{padding:8px 16px;border-radius:8px;font-size:12px;color:var(--t2);cursor:pointer;border:1px solid transparent;transition:all 0.2s}.z-status-env-tab:hover{color:var(--t1);background:rgba(255,255,255,0.05)}.z-status-env-tab-active{color:var(--accent);background:rgba(88,166,255,0.1);border-color:rgba(88,166,255,0.3)}.z-status-env-panel{display:none;padding:16px}.z-status-env-panel-active{display:block}.z-status-env{padding:0}.z-status-env-row{display:flex;padding:10px 0;border-bottom:1px solid var(--border)}.z-status-env-row:last-child{border-bottom:none}.z-status-env-label{width:60px;font-size:11px;color:var(--t3);flex-shrink:0}.z-status-env-val{font-size:12px;color:var(--t1);flex:1}.z-status-sec{padding:16px;border-bottom:1px solid var(--border)}.z-status-sec:last-child{border-bottom:none}.z-status-sec-title{font-size:11px;color:var(--t3);margin-bottom:12px;text-transform:uppercase;letter-spacing:1px}.z-status-sec-note{background:rgba(88,166,255,0.05);border-left:3px solid var(--accent);padding:12px;border-radius:0 8px 8px 0;font-size:12px;color:var(--t2)}.z-status-chars{display:flex;flex-wrap:wrap;gap:6px}.z-status-char{padding:4px 10px;background:var(--bg2);border:1px solid var(--border);border-radius:6px;font-size:11px;color:var(--t2)}.z-status-clue-list{display:flex;flex-direction:column;gap:8px}.z-status-clue{padding:10px;background:var(--bg2);border-radius:8px;border-left:3px solid var(--gold);font-size:12px;color:var(--t2)}.z-status-npc-container{display:flex;flex-direction:column;gap:8px}.z-status-npc{display:flex;align-items:center;gap:12px;padding:12px;background:var(--bg2);border-radius:10px}.z-status-npc-avatar{width:40px;height:40px;border-radius:8px;background:var(--bg);display:flex;align-items:center;justify-content:center;font-size:16px;color:var(--t3);border:1px solid var(--border)}.z-status-npc-info{flex:1}.z-status-npc-name{font-size:13px;color:var(--t1);font-weight:500}.z-status-npc-role{font-size:11px;color:var(--t3)}.z-status-npc-favor{font-size:11px;padding:2px 8px;border-radius:4px;background:rgba(0,0,0,0.2)}.z-status-npc-favor.pos{color:var(--success)}.z-status-npc-favor.neg{color:var(--danger)}.z-status-options{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:16px}.z-status-opt{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer;transition:all 0.2s;text-align:left;position:relative;z-index:10}.z-status-opt:hover{border-color:var(--accent);transform:translateY(-2px)}.z-status-opt.safe{border-color:rgba(63,185,80,0.3)}.z-status-opt.safe:hover{border-color:var(--success)}.z-status-opt.risky{border-color:rgba(248,81,73,0.3)}.z-status-opt.risky:hover{border-color:var(--danger)}.z-status-opt.opportunity{border-color:rgba(210,153,34,0.3)}.z-status-opt.opportunity:hover{border-color:var(--gold)}.z-status-opt-title{font-size:12px;color:var(--t1);margin-bottom:4px;font-weight:500}.z-status-opt-desc{font-size:10px;color:var(--t3);line-height:1.4}.z-status-opt-risk{font-size:9px;margin-top:6px;padding:2px 6px;border-radius:4px;display:inline-block}.z-status-opt-risk.low{background:rgba(63,185,80,0.15);color:var(--success)}.z-status-opt-risk.medium{background:rgba(210,153,34,0.15);color:var(--gold)}.z-status-opt-risk.high{background:rgba(248,81,73,0.15);color:var(--danger)}.z-status-data{display:none}.z-status-zy{margin:0 16px 16px;display:grid;grid-template-columns:1fr 1fr;gap:10px}.z-status-zy-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px}.z-status-zy-label{font-size:10px;color:var(--t3);margin-bottom:6px}.z-status-zy-val{font-size:12px;color:var(--t1);margin-bottom:6px}.z-status-zy-bar{height:4px;background:var(--bg);border-radius:2px;overflow:hidden}.z-status-zy-fill{height:100%;border-radius:2px;transition:width 0.3s}.z-status-zy-fill.c0{background:linear-gradient(90deg,var(--danger),#ff6b6b)}.z-status-zy-fill.c1{background:linear-gradient(90deg,#4a0080,#8b00ff)}.z-status-zy-fill.c2{background:linear-gradient(90deg,var(--gold),#ffa502)}.z-status-zy-fill.c3{background:linear-gradient(90deg,var(--success),#2ed573)}</style><!-- Z_CONTENT -->
```

---

### 规则2：主HTML结构

**findRegex**：`<!-- Z_CONTENT -->`

**用途**：将规则1留下的锚点替换为完整的面板 HTML 骨架，包含标签页切换 onclick（纯 ES5 内联）和所有 `data-field` / `data-list` 占位符，末尾留下 `<!-- Z_SCRIPT -->` 锚点供规则3继续替换。

**replaceString**（全文原样，~3500字符）：

```
<div class="z-status-content"><div class="z-status-header"><div class="z-status-title">状态面板</div></div><div class="z-status-env-tabs"><div class="z-status-env-tab z-status-env-tab-active" data-envpanel="scene" onclick="var box=this.closest('.z-status-box');var tabs=box.querySelectorAll('.z-status-env-tab');for(var i=0;i<tabs.length;i++){tabs[i].className='z-status-env-tab'}this.className='z-status-env-tab z-status-env-tab-active';var panels=box.querySelectorAll('.z-status-env-panel');for(var j=0;j<panels.length;j++){panels[j].className='z-status-env-panel'}var p=box.querySelector('.z-status-env-panel[data-envtype=scene]');if(p)p.className='z-status-env-panel z-status-env-panel-active'">场景</div><div class="z-status-env-tab" data-envpanel="clue" onclick="var box=this.closest('.z-status-box');var tabs=box.querySelectorAll('.z-status-env-tab');for(var i=0;i<tabs.length;i++){tabs[i].className='z-status-env-tab'}this.className='z-status-env-tab z-status-env-tab-active';var panels=box.querySelectorAll('.z-status-env-panel');for(var j=0;j<panels.length;j++){panels[j].className='z-status-env-panel'}var p=box.querySelector('.z-status-env-panel[data-envtype=clue]');if(p)p.className='z-status-env-panel z-status-env-panel-active'">线索</div></div><div class="z-status-env-panel z-status-env-panel-active" data-envtype="scene"><div class="z-status-env"><div class="z-status-env-row"><span class="z-status-env-label">时间：</span><span class="z-status-env-val" data-field="tm">--</span></div><div class="z-status-env-row"><span class="z-status-env-label">地点：</span><span class="z-status-env-val" data-field="loc">--</span></div><div class="z-status-env-row"><span class="z-status-env-label">目标：</span><span class="z-status-env-val" data-field="goal">--</span></div></div><div class="z-status-sec"><div class="z-status-sec-title">在场人员</div><div class="z-status-chars" data-list="chars"></div></div><div class="z-status-sec z-status-sec-note"><div class="z-status-sec-title">现场记录</div><span data-field="rd">--</span></div></div><div class="z-status-env-panel" data-envtype="clue"><div class="z-status-clue-list" data-list="clues"></div></div><div class="z-status-zy" data-list="zy"></div><div class="z-status-sec"><div class="z-status-sec-title">关注对象</div><div class="z-status-npc-container" data-list="npcs"></div></div><div class="z-status-sec"><div class="z-status-sec-title">行动选项</div><div class="z-status-options" data-list="opts"></div></div></div><!-- Z_SCRIPT -->
```

---

### 规则3：JS解析器（含findData继承逻辑）

**findRegex**：`<!-- Z_SCRIPT -->`

**用途**：将锚点替换为 `img onerror` 触发的 IIFE 解析器，读取 data-env / data-st / data-opt 数据并通过纯 DOM API 填充 UI，完成后调用 `img.remove()` 自清理。

**replaceString**（全文原样，~4000字符）：

```
<img src="x" style="display:none" onerror="(function(img){var box=img.closest('.z-status-box');if(!box)return;var q=function(s){return box.querySelector(s)};var attr=function(el,a){return el?el.getAttribute(a):null};var setTxt=function(sel,val){var el=q(sel);if(el&&val)el.textContent=val};var findData=function(selector,currentOnly){var dataBox=box.querySelector('.z-status-data');if(dataBox){var found=dataBox.querySelector(selector);if(found)return found}if(currentOnly)return null;var allBoxes=document.querySelectorAll('.z-status-box');var idx=-1;for(var i=0;i<allBoxes.length;i++){if(allBoxes[i]===box){idx=i;break}}for(var j=idx-1;j>=0;j--){var prevData=allBoxes[j].querySelector('.z-status-data');if(prevData){var found=prevData.querySelector(selector);if(found)return found}}return null};var env=findData('div[data-env]',false);var st=findData('div[data-st]',false);var opt=findData('div[data-opt]',true);if(env){setTxt('[data-field=tm]',attr(env,'tm'));setTxt('[data-field=loc]',attr(env,'loc'));setTxt('[data-field=goal]',attr(env,'goal'));setTxt('[data-field=rd]',attr(env,'rd'));var charsStr=attr(env,'chars');if(charsStr){var cb=q('[data-list=chars]');if(cb){cb.innerHTML='';var items=charsStr.split(',');for(var i=0;i<items.length;i++){var span=document.createElement('span');span.className='z-status-char';span.textContent=items[i].trim();cb.appendChild(span)}}}}if(st){var zyStr=attr(st,'zy');if(zyStr){var zyBox=q('[data-list=zy]');if(zyBox){zyBox.innerHTML='';var items=zyStr.split(',');for(var i=0;i<items.length;i++){var m=items[i].trim().match(/^([^:]+):(-?\d+)\/(\d+)/);if(m){var card=document.createElement('div');card.className='z-status-zy-card';var lbl=document.createElement('div');lbl.className='z-status-zy-label';lbl.textContent=m[1];card.appendChild(lbl);var val=document.createElement('div');val.className='z-status-zy-val';val.textContent=m[2]+'/'+m[3];card.appendChild(val);var bar=document.createElement('div');bar.className='z-status-zy-bar';var fill=document.createElement('div');fill.className='z-status-zy-fill c'+(i%4);var pct=Math.max(0,Math.min(100,parseInt(m[2])/parseInt(m[3])*100));fill.style.width=pct+'%';bar.appendChild(fill);card.appendChild(bar);zyBox.appendChild(card)}}}}var npcsStr=attr(st,'npcs');if(npcsStr){var nb=q('[data-list=npcs]');if(nb){nb.innerHTML='';var items=npcsStr.split(',');for(var i=0;i<items.length;i++){var parts=items[i].split('|');if(parts.length>=3){var d=document.createElement('div');d.className='z-status-npc';var av=document.createElement('div');av.className='z-status-npc-avatar';av.textContent=parts[0].charAt(0);d.appendChild(av);var info=document.createElement('div');info.className='z-status-npc-info';var nm=document.createElement('div');nm.className='z-status-npc-name';nm.textContent=parts[0];info.appendChild(nm);var rl=document.createElement('div');rl.className='z-status-npc-role';rl.textContent=parts[1];info.appendChild(rl);d.appendChild(info);var fv=parseInt(parts[2])||0;var fvs=document.createElement('span');fvs.className='z-status-npc-favor '+(fv>0?'pos':fv<0?'neg':'');fvs.textContent=(fv>0?'+':'')+fv;d.appendChild(fvs);nb.appendChild(d)}}}}var cluesStr=attr(st,'clues');if(cluesStr){var clb=q('[data-list=clues]');if(clb){clb.innerHTML='';var items=cluesStr.split(',');for(var i=0;i<items.length;i++){var d=document.createElement('div');d.className='z-status-clue';d.textContent=items[i].trim();clb.appendChild(d)}}}}if(opt){var og=q('[data-list=opts]');if(og){og.innerHTML='';var rt={low:'低风险',medium:'中风险',high:'高风险'};for(var n=1;n<=4;n++){var cd=attr(opt,'c'+n);if(!cd)continue;var parts=cd.split('|');if(parts.length>=4){var btn=document.createElement('div');btn.className='z-status-opt '+(parts[3]==='safe'?'safe':parts[3]==='risky'?'risky':parts[3]==='opportunity'?'opportunity':'');btn.setAttribute('data-cmd',parts[0]);btn.onclick=function(ev){ev.stopPropagation();var t=document.querySelector('.chatMsgTextarea');if(t){var inp=t.querySelector('textarea')||t;inp.value=inp.value+' '+this.getAttribute('data-cmd');inp.dispatchEvent(new Event('input',{bubbles:true}))}};var bt=document.createElement('div');bt.className='z-status-opt-title';bt.textContent=parts[0];btn.appendChild(bt);var bd=document.createElement('div');bd.className='z-status-opt-desc';bd.textContent=parts[1];btn.appendChild(bd);var br=document.createElement('span');br.className='z-status-opt-risk '+parts[2];br.textContent=rt[parts[2]]||parts[2];btn.appendChild(br);og.appendChild(btn)}}}}img.remove()})(this)"></div>
```

---

## AI生成规范（写进卡的输出协议）

### 技术输出协议

在**每次回复的末尾**输出以下格式的数据块。

**完整格式（首次/需要完整更新时）**：

```html
<status>
<div class="z-status-data" style="display:none">
<div data-env tm="{{日期时间}}" loc="{{地点}}" goal="{{目标}}" rd="{{现场记录}}" chars="{{在场人员}}"></div>
<div data-st nm="{{姓名}}" jb="{{职业}}" day="{{天数}}" mn="{{金钱}}" zy="{{资源条}}" st="{{状态}}" npcs="{{NPC列表}}" clues="{{线索列表}}" bag="{{物品}}" sthr="{{当前威胁}}" sopp="{{当前机遇}}" stsk="{{待办}}"></div>
<div data-opt c1="{{选项1}}" c2="{{选项2}}" c3="{{选项3}}" c4="{{选项4}}"></div>
</div>
```

**精简格式（仅更新变化的字段）**：

```html
<status>
<div class="z-status-data" style="display:none">
<div data-env rd="茜提供了新线索"></div>
<div data-st zy="hp:65/100" clues="咖啡杯有唇印,茜看到可疑人影"></div>
<div data-opt c1="追问细节|深入了解|low|safe" c2="去后巷|追踪可疑人|medium|risky" c3="调取监控|获取证据|low|opportunity" c4="休息一下|整理思路|low|normal"></div>
</div>
```

### 关键要求

1. 必须以 `<status>` 标记开头
2. 未变化的字段可以省略（继承机制会自动填充）
3. `data-opt` 每次都要提供（不继承）

### 字段填写说明表

| 字段 | 类型 | 继承 | 说明 | 示例 |
|:---|:---|:---|:---|:---|
| `tm` | 字符串 | ✅ | 日期时间 | `3月15日 23:47` |
| `loc` | 字符串 | ✅ | 地点 | `咖啡厅二楼` |
| `goal` | 字符串 | ✅ | 当前目标 | `调查失踪案` |
| `rd` | 字符串 | ✅ | 现场记录 | `桌上有半杯咖啡` |
| `chars` | 逗号分隔 | ✅ | 在场人员 | `茜,真红,老李` |
| `nm` | 字符串 | ✅ | 姓名 | `柑硕` |
| `jb` | 字符串 | ✅ | 职业 | `调查员` |
| `day` | 数字 | ✅ | 天数 | `7` |
| `mn` | 数字 | ✅ | 金钱 | `186500` |
| `zy` | 格式串 | ✅ | 资源条 | `hp:65/100,mp:45/60` |
| `st` | 字符串 | ✅ | 状态标签 | `正常` / `中毒,虚弱` |
| `npcs` | 管道分隔 | ✅ | NPC列表 | `茜\|目击者\|15,真红\|嫌疑人\|-20` |
| `clues` | 逗号分隔 | ✅ | 线索列表 | `咖啡杯有唇印,窗户没关` |
| `bag` | 管道分隔 | ✅ | 物品列表 | `香烟\|3,馒头\|1` |
| `c1-c4` | 管道分隔 | ❌ | 选项 | `返回宿舍\|安全休息\|low\|safe` |

### 继承策略总结表

| 场景 | 需要输出的内容 | Token估算 |
|:---|:---|:---|
| 首条消息 | 完整 `data-env` + `data-st` + `data-opt` | ~400字符 |
| 仅HP变化 | `data-st zy="hp:..."` + `data-opt` | ~150字符 |
| 换场景 | `data-env` + `data-opt` | ~200字符 |
| 仅选项更新 | `data-opt` | ~100字符 |

### 生成前自检清单

- [ ] 以 `<status>` 标记开头？
- [ ] 数据块以 `<div class="z-status-data" style="display:none">` 包裹？
- [ ] `data-opt` 每次都提供了（不继承）？
- [ ] 4个选项 `c1-c4` 都填写了？
- [ ] 列表数据使用 `|` 分隔子项，`,` 分隔条目？
- [ ] 资源条使用 `名称:当前/最大` 格式？
- [ ] 无需变化的字段已省略（利用继承）？

---

## 状态栏规则放哪里（整卡 vs 单独流程）

上节"AI生成规范"是状态栏的**生成规则**（模型侧协议），必须随产出一起交付，放哪里取决于流程：

| 流程 | 规则放哪 | 说明 |
|---|---|---|
| 整张角色卡（内嵌正则） | 卡内 `character_book` 一条 **constant=true（蓝灯）** 条目 | 渲染正则只把数据块变面板、不会让模型生成数据块；必须有这条蓝灯规则让模型每轮输出 `<status>`，否则后续轮次状态栏不更新。见 ../output/card-json.md 第 8 节 |
| 单独状态栏 / 美化流程 | 独立 `规则.md` 文件 | 默认交付 = 正则 json + 规则.md（模型侧协议文档），不强制塞进某张卡 |

---

## script载体变体（当前MMD / 本地酒馆）

当前MMD 平台允许 `<script>` 标签时，可将规则3的 `img onerror` 改为 `<script>` 包裹同等解析逻辑：仍使用 ES5 语法、仍用时间戳生成唯一ID防止重复、仍在最外层 onclick 中调用 `event.stopPropagation()`。规则1（容器+CSS）和规则2（主HTML结构）保持不变。数据格式（data-env / data-st / data-opt）与 onerror 版完全一致，两种载体可随时互换，切换时只需替换规则3的 replaceString。

---

## 常见错误与诊断

### 错误预防表

| 错误类型 | 错误示例 | 正确做法 |
|:---|:---|:---|
| 遗漏status标记 | 直接输出数据块 | 必须以 `<status>` 开头 |
| 遗漏data-opt | 只输出data-st | data-opt每次必须提供 |
| 列表分隔符错误 | `茜,目击者,15` | 使用 `茜\|目击者\|15` |
| 资源条格式错误 | `hp=65/100` | 使用 `hp:65/100` |
| innerHTML拼接 | `el.innerHTML='<div>'+x+'</div>'` | 使用createElement+textContent |
| ES6语法 | `items.forEach(i => ...)` | 使用for循环 |
| img在容器外 | `</div><img onerror="...">` | `<img onerror="..."></div>` |
| 选项不完整 | 只有c1和c2 | 必须填写全部4个选项 |

### 症状诊断表

| 症状 | 原因 | 解决方案 |
|:---|:---|:---|
| 所有字段显示"--" | 数据解析失败 | 检查data-env/data-st属性格式 |
| 代码暴露显示 | 正则链断裂 | 检查Z_CONTENT/Z_SCRIPT标记是否正确 |
| 选项不显示 | data-opt未提供 | 确保每次都输出data-opt |
| 资源条不显示 | zy格式错误 | 检查`名称:值/最大值`格式 |
| 点击无反应 | 伪元素阻挡 | 添加pointer-events:none |
| 继承失效 | 选择器错误 | 检查findData函数的selector参数 |
| 标签页切换失效 | onclick被截断 | 检查是否使用了ES6语法 |
| 面板内横向空白条（预览正常，导入MMD才有） | 三段模板的HTML字符串内含换行，被markdown管线补成空`<p>`段落撑出空条；内容少的页更明显 | 三段replaceString的HTML压成单行无换行；防御CSS加 `.z-status-box p:empty{display:none!important}` + `.z-status-box p{margin:0!important}` + `.z-status-box br{display:none!important}`；详见 statusbar-radar.md「MMD换行空白条陷阱」 |

### 快速验证方法

在浏览器控制台执行：

```javascript
// 检查数据区是否正确解析
document.querySelectorAll('.z-status-box .z-status-data div').forEach(function(el){
  console.log(el.outerHTML);
});

// 检查继承链
document.querySelectorAll('.z-status-box').forEach(function(box, i){
  console.log('Box ' + i + ':', box.querySelector('.z-status-data') ? '有数据' : '无数据');
});
```

## 换用风格数据库

本节上方的 `#0d1117` GitHub 暗黑配色只是**默认风格之一**。状态栏的全部视觉（配色/圆角/边框/阴影/字体/装饰）可整套替换为 ../style-db/ 里任一风格：
1. 按 ../style-system.md 选风格（或混搭维度）。
2. 把该风格 palettes.md 的色板填进本方案 CSS 的 `--bg/--bg2/--border/--t1/--t2/--t3/--accent` 等变量（变量名映射见 style-system.md 第1节）。
3. 圆角/边框/阴影/装饰按 layout-ui.md 与 decoration.md 的该风格取值替换对应 CSS。
4. 渲染引擎、正则结构、JS 解析逻辑**完全不动**——只换样式值。
5. 用户要单独微调（换主色、改圆角等）按 style-system.md 第5节项目级覆盖处理。
