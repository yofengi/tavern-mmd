# 旧版MMD平台技术规范（不支持 `<script>`）

本文档适用于旧版MMD / sexyai.top 平台的交互模块开发；状态栏具体方案（三段正则模板、数据格式、继承机制）见 `../beautify/statusbar.md`，全局CSS美化见 `../beautify/global-css.md`。

---

## 1. 红线分级表

### 零级：根本性红线（CSP格式审查）

| 限制 | 现象 / 后果 | 解决方案 |
|:---|:---|:---|
| DOM属性内JS不可多行换行 | CSP对 `onerror`/`onclick` 等属性注入的JS进行格式审查，多行/含换行符代码概率被破坏或拦截，导致代码不完整/语法错误/不执行 | **onerror 及 onclick 内代码必须写成单行，无任何换行符** |
| `<img>` 必须在容器内部 | `img.closest('.container')` 返回 `null`，整个JS解析逻辑完全无法执行 | 确保 `<img onerror>` 标签位于最外层容器闭合标签 `</div>` **之前** |

### 一级：致命红线

| 限制 | 现象 / 后果 | 解决方案 |
|:---|:---|:---|
| 禁止 `<script>` 标签（静态/动态均禁） | 服务器端过滤彻底剥离，`document.createElement('script')` 动态注入同样无效；所有JS函数无法被定义，调用报 `is not defined` | 使用 `<img src="x" onerror="...">` 作为唯一JS执行载体 |
| 事件冒泡污染（PC端） | 模块内点击冒泡到聊天气泡父容器，意外触发编辑/复制等默认行为 | 最外层容器强制添加 `onclick="event.stopPropagation()"` |
| `innerHTML` 字符串拼接 | 代码被破坏或作为原始文本暴露 | 使用纯DOM API：`createElement` + `textContent` + `appendChild` |
| `style.cssText` 赋值 | 报 `Unexpected identifier` 错误 | 预定义CSS类，用 `element.className` 切换 |

### 二级：严重限制

| 限制 | 现象 / 后果 | 解决方案 |
|:---|:---|:---|
| 禁止脚本自动/懒加载 | `onload`、`onmouseenter` 等不可靠或被阻止，无法用于初始化核心JS对象 | 使用 `onerror` 点火器；所有初始化逻辑集中于单个img |
| 跨img状态传递丢失 | 多个img标签间无法共享状态，数据丢失 | **所有JS集中在单个img标签**中执行 |
| `replaceString` 超20000字符截断 | 替换字符串被平台截断，后续内容丢失 | 使用分段式正则规则拆分；单条不超20000字符 |
| 重复ID导致 `getElementById` 失灵 | 所有聊天记录渲染在同一页面文档，重复ID引发JS混乱；**这是"第二次使用就失效"的根本原因** | 每次生成时使用 `Date.now()` 时间戳后缀，确保全局唯一 |

### 三级：交互限制

| 限制 | 现象 / 后果 | 解决方案 |
|:---|:---|:---|
| 注入HTML内的换行被渲染成空白段落 | MMD气泡走markdown管线（vditor），标签间换行/空行被解析器补成空`<p>`，空`<p>`带默认margin撑出大块横向空白条；**浏览器预览查不出**（预览按CSS折叠空白），内容少的页尤其明显 | 注入HTML写成单行无缝（标签间零换行）；防御CSS加 `.容器 p:empty{display:none!important}` + `.容器 p{margin:0!important}` + `.容器 br{display:none!important}`；状态栏方案另见 ../beautify/statusbar-radar.md「MMD换行空白条陷阱」 |
| `onclick` 净化三级行为 | **放行**：极简单行（如 `this.textContent='...'`）；**手术式切除**：含多行/`try-catch` 的元素整体被删除消失；**代码实体化**：严重威胁时所有 `<>`、`"` 被HTML实体化变为纯文本显示 | `onclick` 只作"点火器"，复杂逻辑存入隐藏元素的 `data-s` 属性，onclick调用 `eval(...)` 触发 |
| `window` 函数未定义 | 点击时报 `is not defined` 错误 | 使用内联 `onclick` 逻辑，避免依赖全局函数 |
| 伪元素阻挡点击 | 按钮点击失效 | 装饰性伪元素添加 `pointer-events: none` |

### 四级：代码长度与弹窗限制

| 限制 | 现象 / 后果 | 解决方案 |
|:---|:---|:---|
| 单条正则注入HTML约20000字符上限 | 超出部分被截断或整体失效 | 压缩代码，避免冗余；CSS用短类名；超限拆分多条正则 |
| `alert()` 静默失效 | 弹窗被平台静默阻止，且中断代码执行不报错 | 使用DOM元素在页面内显示调试信息，禁用 `alert()` |

---

## 2. ES6+语法禁用清单

平台对ES6+语法全面禁用：遇到箭头函数 `=>` 等ES6语法从该处截断，后续代码丢失。**必须全面使用ES5语法。**

| 被禁语法 | 错误示例 | 正确替代 |
|:---|:---|:---|
| 箭头函数 | `items.forEach(i => { ... })` | `for(var i=0; i<items.length; i++){ ... }` |
| 模板字符串 | `` `Hello ${name}` `` | `'Hello ' + name` |
| `let` / `const` | `let x = 1; const y = 2;` | `var x = 1; var y = 2;` |
| 解构赋值 | `const {a, b} = obj` | `var a = obj.a; var b = obj.b;` |
| 展开运算符 | `[...items]` | 用 `for` 循环逐项复制 |
| 可选链 | `obj?.prop` | `obj && obj.prop` |

---

## 3. 纯DOM API原则

`onerror` 内部**绝对禁止**：

- `innerHTML = '...'` 字符串拼接
- `style.cssText = '...'` 内联样式赋值
- 任何含 `color:`、`background:` 等CSS属性的字符串赋值
- ES6+语法（箭头函数、模板字符串、`let`/`const` 等）

**必须使用**：

```javascript
// 创建元素
var el = document.createElement('div');
// 设置类名（不用style.cssText）
el.className = 'my-class';
// 设置文本（不用innerHTML）
el.textContent = '内容';
// 挂载子元素
parent.appendChild(el);
// 变量声明
var x = 1;
// 函数定义
var fn = function() { ... };
```

---

## 4. 正则系统限制与random标签

### 4.1 基础限制

| 项目 | 上限 | 说明 |
|:---|:---|:---|
| `findRegex` 字段 | **1000字符** | 超出后正则失效 |
| `replaceString` 字段 | **20000字符** | 超出后被截断 |
| 正则条目总数 | **30条** | 无法动态增加 |

导入方式：支持 **json 批量导入**（MMD专用4字段格式：pageDepth/statusbar/beginning/regex_scripts，见 `../output/regex-output.md`），也可在平台UI逐条手填。

### 4.2 `random` 标签三种用法

#### 用法1：多个独立random标签各自随机

同一 `replaceString` 中多个 `random` 标签**各自独立**随机，互不干扰。

```
replaceString: 你抽到了武器：(random(长剑|战斧|法杖)) 和防具：(random(皮甲|锁子甲|布袍))。
可能结果：  "你抽到了武器：长剑 和防具：布袍。"
           "你抽到了武器：战斧 和防具：皮甲。"
```

#### 用法2：在语句中无缝嵌入

`random` 标签可嵌入句子任意位置，生成流畅文本。

```
replaceString: 石头剪刀布，我决定出 (random(石头|剪刀|布)) 来一决胜负！
可能结果：  "石头剪刀布，我决定出 剪刀 来一决胜负！"
```

#### 用法3：捕获组 `$1` 作为random选项

将 `findRegex` 中捕获到的内容作为 `random` 标签的动态选项，实现最强联动。

```
findRegex:     /我选择(.+)/
replaceString: 你选择了 $1 啊，这真是个 (random(不错的|绝妙的|有待商榷的|$1 自己的)) 选择。

当用户输入："我选择苹果"
可能结果1（常规项）：  "你选择了 苹果 啊，这真是个 绝妙的 选择。"
可能结果2（$1被选中）："你选择了 苹果 啊，这真是个 苹果 自己的 选择。"
```

### 4.3 避坑

- 使用捕获组作为 `random` 选项时，确保 `findRegex` 能**稳定准确**捕获预期内容，不稳定的正则会导致 `random` 出现非预期文本
- 时刻注意 `replaceString` 总字符数，复杂 `random` 组合（尤其多个长选项）会快速消耗20000字符额度

---

## 5. 核心架构模式

### 5.1 onerror点火器

**唯一可靠的JS执行载体。** 基础骨架：

```html
<img src="x" style="display:none" onerror="(function(img){var box=img.closest('.容器类名');if(!box)return;/* 所有逻辑写这里，单行无换行 */img.remove()})(this)">
```

关键要点：
- 使用 IIFE `(function(img){ ... })(this)` 包装，`img` 即触发元素本身
- 整个 `onerror` 属性值**必须单行，无任何换行符**
- `img` 标签必须在最外层容器闭合 `</div>` **之前**
- 执行完毕后调用 `img.remove()` 清理DOM

### 5.2 纯CSS切换（radio + :checked）

完全不依赖JS，利用CSS `:checked` 伪类实现动态显隐。完整代码结构：

```html
<style>
    .page { display: none; }
    #radio1_时间戳:checked ~ .container .page1 { display: block; }
    #radio2_时间戳:checked ~ .container .page2 { display: block; }
</style>

<!-- 隐藏radio作状态控制器 -->
<input type="radio" id="radio1_时间戳" name="nav_时间戳" checked style="display:none">
<input type="radio" id="radio2_时间戳" name="nav_时间戳" style="display:none">

<div class="container">
    <!-- label触发radio切换 -->
    <label for="radio1_时间戳">第一页</label>
    <label for="radio2_时间戳">第二页</label>
    <!-- 内容区 -->
    <div class="page page1">第一页内容</div>
    <div class="page page2">第二页内容</div>
</div>
```

注意：所有 `id`、`name`、`for` 属性都必须含时间戳后缀保证唯一性。

### 5.3 轻主板+胖遥控器

**突破 onclick 净化限制的唯一稳定架构。**

原理：将复杂JS逻辑作为纯文本字符串存储在隐藏 `<p>` 的 `data-s` 属性（轻主板），按钮 `onclick` 仅执行极简的 `eval(...)` 调用（胖遥控器）。

架构优势：
- **代码与结构分离**：复杂逻辑存为纯文本，不触发平台审查
- **绕过CSP限制**：`data-*` 属性不受内容安全策略约束
- **完美支持时间戳**：每个主板独立时间戳ID，多次生成互不干扰
- **可维护性高**：逻辑集中管理，易于调试更新

完整计算器示例：

```html
<!-- 轻主板：存储复杂逻辑（data-s值为单行字符串） -->
<p id="FUNC_CALCULATE_1729584719271" style="display:none"
   data-s="var input=document.getElementById('INPUT_1729584719271').value;var result=parseFloat(input)*2;document.getElementById('OUTPUT_1729584719271').textContent='结果:'+result;"></p>

<!-- 最外层容器，阻止冒泡 -->
<div id="CALC_MODULE_1729584719271" onclick="event.stopPropagation()">
    <input type="text" id="INPUT_1729584719271" placeholder="输入数字">
    <!-- 胖遥控器：onclick只做eval触发 -->
    <button onclick="eval(document.getElementById('FUNC_CALCULATE_1729584719271').dataset.s)">
        计算
    </button>
    <div id="OUTPUT_1729584719271">结果将显示在这里</div>
</div>
```

### 5.4 appendChild置顶

**实现模态框/浮窗覆盖整个页面的DOM技术。**

DOM原理（4步）：
1. 聊天气泡及其内部的原始容器在DOM树中位置固定
2. 执行 `document.body.appendChild(container)` 时，将容器**从原始位置移除**并**重新挂载**到 `<body>` 最末尾
3. 容器在DOM树中的位置比所有聊天消息、导航栏都更"靠后"（后来居上原则）
4. 配合 `position: fixed` 定位，该元素在视觉上浮动于所有内容之上

关键CSS：
```css
position: fixed;                              /* 脱离文档流，相对视口定位 */
top: 50%; left: 50%;
transform: translate(-50%, -50%);            /* 水平垂直居中 */
z-index: 9999;                               /* appendChild已保证顺序，z-index作保险 */
```

完整带遮罩层模态框示例：

```html
<style>
    .modal-overlay {
        display: none;
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background: rgba(0,0,0,0.5);
        z-index: 9998;
    }
    .modal-content {
        position: fixed;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        border-radius: 12px;
        padding: 30px;
        max-width: 500px;
        z-index: 9999;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    }
</style>

<!-- 轻主板：打开模态框逻辑 -->
<p id="FUNC_OPEN_MODAL_1729584719271" style="display:none"
   data-s="var overlay=document.getElementById('OVERLAY_1729584719271');var modal=document.getElementById('MODAL_1729584719271');overlay.style.display='block';modal.style.display='block';document.body.appendChild(overlay);document.body.appendChild(modal);"></p>

<!-- 轻主板：关闭模态框逻辑 -->
<p id="FUNC_CLOSE_MODAL_1729584719271" style="display:none"
   data-s="document.getElementById('OVERLAY_1729584719271').style.display='none';document.getElementById('MODAL_1729584719271').style.display='none';"></p>

<!-- 触发按钮（胖遥控器） -->
<button onclick="eval(document.getElementById('FUNC_OPEN_MODAL_1729584719271').dataset.s)">
    打开模态框
</button>

<!-- 遮罩层：点击关闭 -->
<div id="OVERLAY_1729584719271" class="modal-overlay"
     onclick="eval(document.getElementById('FUNC_CLOSE_MODAL_1729584719271').dataset.s)"></div>

<!-- 模态框主体 -->
<div id="MODAL_1729584719271" class="modal-content" style="display:none;" onclick="event.stopPropagation()">
    <h2>这是一个模态框</h2>
    <p>通过 document.body.appendChild() 实现完美置顶效果。</p>
    <input type="text" placeholder="可以在这里输入内容" style="width:100%; padding:8px; margin:10px 0;">
    <button onclick="eval(document.getElementById('FUNC_CLOSE_MODAL_1729584719271').dataset.s)"
            style="background:#333; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer;">
        关闭
    </button>
</div>
```

**避坑5条：**
1. **时间戳一致性**：同一模态框系统所有ID必须使用相同时间戳
2. **冒泡处理**：模态框内容区必须有 `onclick="event.stopPropagation()"`；遮罩层点击用于关闭
3. **显示顺序**：先 `appendChild(overlay)` 再 `appendChild(modal)`，确保模态框在遮罩层之上
4. **z-index保险**：`appendChild` 已保证DOM顺序，仍建议设置 `z-index: 9999` 作保险
5. **性能**：频繁 `appendChild` 触发重排；对需要频繁切换的元素，只执行一次 `appendChild`，后续仅切换 `display` 属性

### 5.5 时间戳唯一ID

**根本原因**：平台将所有聊天记录渲染在同一页面，重复ID导致 `getElementById` 失灵（这是"第二次使用就失效"的根本原因）。

生成方式：`Date.now()` 获取当前毫秒时间戳。

命名格式：`元素类型_功能描述_时间戳`

示例：`BUTTON_SAVE_1729584719271`、`INPUT_NAME_1729584719271`、`FUNC_TOGGLE_1729584719271`

**检查清单4条：**
- [ ] 每次生成新模块时都生成新的时间戳（不复用旧时间戳）
- [ ] 同一模块内所有ID使用**相同**时间戳后缀
- [ ] JavaScript代码中引用的ID也包含时间戳（`data-s` 内部的ID字符串同样要含时间戳）
- [ ] `<label>` 的 `for` 属性与目标 `input` 的 `id` 属性时间戳一致

---

## 6. 调试诊断表

> 注：表中 data-env/data-st/data-opt/zy/findData 为状态栏方案专属概念，详见 `../beautify/statusbar.md`；其余条目适用于任何交互模块。

| 症状 | 原因 | 解决方案 |
|:---|:---|:---|
| 所有字段显示 `--` | 数据解析失败（img位置错误或JS被截断） | 检查img标签是否在 `</div>` 之前；检查data-env/data-st属性格式 |
| 代码暴露原样显示 | 正则链断裂，或平台将HTML实体化 | 检查正则标记是否正确；排查onclick内是否含复杂逻辑被实体化 |
| 选项不显示 | `data-opt` 未提供（不继承字段） | 确保每次都输出 `data-opt` |
| 资源条不显示 | `zy` 格式错误 | 检查 `名称:当前值/最大值` 格式（冒号、斜杠） |
| 点击无反应 | 伪元素阻挡点击，或按钮整体被净化删除 | 添加 `pointer-events: none`；将逻辑移入轻主板 |
| 继承失效 | `findData` 函数selector参数错误，或img在容器外导致box为null | 检查选择器；确认img标签位置 |
| 标签页切换失效 | `onclick` 被截断（含ES6语法导致从箭头函数处截断） | 排查onclick内是否使用了ES6语法，改用ES5 |
| 面板内出现横向空白条（预览正常，导入后才有） | 注入HTML的换行被markdown管线补成空`<p>`段落，空`<p>`带margin撑出空条；内容少的页更明显 | HTML压成单行无换行；防御CSS `p:empty{display:none!important}` + `p{margin:0!important}` + `br{display:none!important}`；详见 ../beautify/statusbar-radar.md |

---

## 7. 开发检查清单

### 结构层

- [ ] 最外层容器有 `onclick="event.stopPropagation()"`
- [ ] `<img onerror>` 标签在最外层容器 `</div>` **之前**（不在外部）
- [ ] 数据区/隐藏元素有 `style="display:none"`
- [ ] 所有需要填充的位置有 `data-field` 或 `data-list` 标记
- [ ] 单条正则注入HTML未超过20000字符（超限拆分多条正则）
- [ ] 没有使用 `<script>` 标签（静态或动态注入均禁止）
- [ ] 没有依赖自动加载机制（`onload` 等不可靠）

### 代码层

- [ ] `onerror` 及 `onclick` 内代码**单行无换行符**
- [ ] 复杂JS逻辑存储在隐藏元素的 `data-s` 属性中（轻主板+胖遥控器架构）
- [ ] `onclick` 属性内只有极简的 `eval(document.getElementById(...).dataset.s)` 调用
- [ ] 使用 IIFE `(function(img){...})(this)` 包装 `onerror` 执行代码
- [ ] 使用纯DOM API替代 `innerHTML` 字符串拼接
- [ ] 完全不使用ES6+语法（无箭头函数、模板字符串、`let`/`const`、解构、展开运算符、可选链）
- [ ] 所有变量声明使用 `var`，函数使用 `function(){}`
- [ ] 没有使用 `alert()` 作为调试或提示手段
- [ ] 所有ID引用（包括 `data-s` 字符串内部）都包含时间戳

### 样式层

- [ ] UI切换优先使用纯CSS方案（radio + `:checked`）
- [ ] 所有装饰性伪元素添加了 `pointer-events: none`
- [ ] 交互元素设置了 `position: relative` 和适当的 `z-index`
- [ ] 需要置顶的元素使用 `position: fixed` 或 `absolute`，配合 `z-index: 9999`
- [ ] 响应式设计（移动端适配）

### 数据层

- [ ] 每次生成模块都生成新的时间戳，同模块内所有ID使用相同时间戳后缀
- [ ] `data-opt` 每次都提供（不继承字段）
- [ ] 列表使用正确分隔符（`|` 分隔子项，`,` 分隔条目）
- [ ] 资源条使用 `名称:当前值/最大值` 格式
- [ ] 数据收集使用原生表单元素（`.value` 属性天然数据容器）
- [ ] 无变化字段省略以节省Token（利用继承机制）
- [ ] `findRegex` ≤ 1000字符，`replaceString` ≤ 20000字符，正则条目 ≤ 30条
