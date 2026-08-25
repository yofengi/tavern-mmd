# 悬浮组件（可拖动悬浮球 / 侧边栏抽屉 / 带菜单的悬浮按钮）

MMD 真正的悬浮组件是**运行时注入的可交互元素**：悬浮球是一个可以在页面上拖动的按钮，点击展开菜单；侧边栏是从屏幕外滑入的抽屉。它们不是静态写死的 HTML，而是由正则 `replaceString` 里的 `img onerror` 点火器在渲染时 `createElement` 注入 `document.body`。

本文档给出**两个平台都验证过**的认证写法，供后续直接调用/改配色。预览验证用 `scripts/build-preview.py`（悬浮组件会被自动归入"悬浮组件预览"面板，全景预览里与其他组件组合显示）。

> **Shadow DOM 变体（2026-06-17 当前 MMD 实测可行，可选增强）**：可把组件 UI 包进 shadow root 拿样式隔离。实测靶 10-11 全绿：**host 挂 `document.body` + shadow 内 `position:fixed` + `z-index:2147483647` 浮在消息之上 + 拖动 + `getElementById` 单例防重**全部成立。收益：组件 CSS 不外泄污染平台、平台强制染色渗不进来、不过 markdown 管线（无空白条）；代价：多一层 `attachShadow` 包装。**关键：host 必须 `appendChild` 到 `document.body`**（不能留消息气泡内，否则被气泡 stacking context 困住、被新消息盖住）。写法：`var wrap=document.createElement('div');wrap.id='z-fab-wrap';var sr=wrap.attachShadow({mode:'open'});`（CSS+按钮 createElement 进 sr）`document.body.appendChild(wrap);`。**铁律照旧**：onerror 属性用双引号包裹时内部全单引号、禁内部裸双引号（属性改用单引号包裹则内部可写双引号）。本文下方 light DOM 写法是当前 MMD 与本地酒馆的基线；shadow 变体用于需要强隔离的组件。全局主题 CSS 本身不可 shadow 化，因为它必须作用于平台 light DOM。**这两种写法都不适用于沙盒模式**（见下方平台红线表）。

### 主题切换 / 设置 UI 的职责边界

主题按钮或设置面板可以放在 Shadow DOM 隔离自身样式，但 Shadow DOM 内部状态不能直接给平台页面换肤。每个动作最终必须调用全局主题 runtime API，由它修改 `html` / `body` 等 **light DOM 根节点**上的自有主题属性或运行时 CSS 变量；不得只给 shadow host 加 `day/night` 类后宣称全局主题已切换。

需要 day/night/native、玩家微调或持久偏好时，优先复用 `theme-runtime.md` 与 `../../assets/global-beautify-examples/mmd-theme-runtime/` 提供的 runtime 面板。不要另造第二套悬浮球 / 侧栏引擎、MutationObserver、route supervisor 或 localStorage schema；附加入口只能调用同一 owner 的公开 API。

---

## 平台红线（决定写法）

| 限制 | 当前 MMD `/mmd` | 本地酒馆 `/st` | MMD沙盒模式 `/mmdsandbox` |
|---|---|---|---|
| `<script>` | 可用（document-level 一次性 bootstrap）；per-message 渲染仍须 img onerror | 可用 | **一等公民**，装卡即抽出、整卡跑一次 |
| `img onerror` 点火器 | ✅ per-message 唯一可靠载体 | ✅ 可用 | 🚨 **官方明令禁止**（teapot 系） |
| `style.cssText=` | 仅告警 | ✅ 允许 | 【待验证】官方未提及；按纯 DOM API 保守处理 |
| `el.innerHTML=` | 仅告警 | ✅ 允许 | 【待验证】官方未提及；按纯 DOM API 保守处理 |
| `onerror` 多行 | ✅ 可多行（属性用双引号包裹时内部禁裸双引号） | ✅ 可多行 | 不适用（onerror 被禁） |
| 内联 `onclick` | **只放行干净调用/引用表达式**，禁代码字面量与直接 DOM 赋值 → 用 `el.onclick=function(){}` | ✅ 允许 | ✅ 普通标签 `onclick="tap()"` 可用（顶层 `function` 挂 `window`）；**`svg` 内部 `onclick` 会被删** |
| 作者自写 `data-*` | ✅ 允许（轻主板 `data-s` 就靠它） | ✅ 允许 | 🚨 **会被净化删掉** → 用 `class` 或 `id` |
| `el.style.left/top=`（单属性） | ✅ 允许 | ✅ 允许 | ✅ 允许（算出来的值写内联 `style`） |
| `classList.add/remove/toggle` | ✅ 允许 | ✅ 允许 | ✅ 允许 |
| 长期悬浮 UI 挂哪 | `document.body.appendChild` + `position:fixed` | 同左 | 🚨 **挂舞台 `sdk.stage`**，不能挂气泡（气泡滚出屏幕即销毁） |
| z-index | `9999` 级即可 | 无约束 | **作者段 1000–1999**；超了会挡平台长按菜单 |

> 🚨 **沙盒模式不要用本文档的写法。** 本文档全部组件的地基是「`img onerror` 点火器 + `createElement` 注入 `document.body`」，这在沙盒模式里两头都不成立：点火器被官方禁，长期浮层要挂舞台而不是 body。沙盒模式做悬浮 UI 的正确形状：专开一条规则只放 `<script>` → `sdk.stage.open('content')` + `sdk.stage.el()` 里装配面板（关掉再开内容还在，不必重建）→ 气泡内的按钮用 `sdk.on('message:mount')` 绑事件。规范见 `../platforms/mmd-sandbox.md` §4.6（舞台）、§5.2（净化与白名单）、§6.3（z-index）。**本文档的交互设计（拖动、菜单翻转、防冒泡、单例防重）思路可参考，载体与挂载点必须整体重写。**

**统一结论（当前 MMD 与本地酒馆通用的最稳写法）**：
1. 静态外观（尺寸/配色/圆角/阴影/默认位置）→ **预定义 CSS 类**（放进美化 `<style>`），不用 `cssText`。
2. 开关状态（菜单显隐、抽屉滑入滑出）→ **`classList.toggle('z-open')`** + CSS 类里写 `.z-open{...}`，不用改 `style.display`/`style.transform` 字符串。
3. 拖动位置、菜单翻转坐标这类**连续数值** → 用**单属性** `el.style.left=x+'px'`（validate 只拦 `cssText`/`innerHTML`，放行单属性）。
4. 事件绑定 → 在 `img onerror` 内 `el.onclick=function(){}` / `el.addEventListener(...)`（合法路径），**不写 inline onclick**。
5. 动态构建内容 → `createElement`/`textContent`/`appendChild`，**不用 innerHTML**。
6. 所有可点元素最外层 `ev.stopPropagation()` 防冒泡到气泡。
7. 点火器自身 `this.remove()` 自毁；用 `if(document.getElementById('z-xxx')){e.remove();return;}` 防重复注入（同一条消息多次渲染）。

---

## 一、可拖动悬浮球 + 跟随菜单（核心组件）

要点（用户实测要求）：
- **本体可拖动**：按下→移动改 `style.left/top`，移动超过 3px 记为"拖动"。
- **未拖动的点击 = 切换菜单**；拖动则不触发菜单（用 `moved` 标志区分）。
- **菜单跟随本体**：拖动时每帧重算菜单位置（`reposition()`），菜单粘在球旁边。
- **菜单在能完整展开的方位打开**：上方放得下放上方，否则翻到下方；水平方向夹取进视口——**确保菜单不被屏幕裁掉**。
- **菜单选项可点击**：每项 `onclick` 绑定动作（回填输入框 / 开抽屉 / 自定义），点完关菜单。
- 本体也夹取进视口，拖不出屏幕。

### CSS 类（放进美化 `<style>`）

```css
.z-float-ball{position:fixed;left:18px;bottom:90px;width:48px;height:48px;border-radius:50%;
  background:var(--z-float-accent,#B38F5C);color:#fff;border:none;font-size:22px;z-index:99999;cursor:grab;
  box-shadow:0 3px 10px rgba(0,0,0,.3);touch-action:none}
.z-float-menu{position:fixed;display:none;background:var(--z-float-surface,#fff);color:var(--z-float-text,#2b2b2b);
  border:1px solid var(--z-float-accent,#B38F5C);border-radius:8px;padding:6px;z-index:99999;
  box-shadow:0 3px 10px rgba(0,0,0,.3);min-width:130px}
.z-float-menu.z-open{display:block}
.z-float-menu-item{padding:7px 10px;cursor:pointer;white-space:nowrap;border-radius:6px}
.z-float-menu-item:hover{background:var(--z-float-surface-hover,#f2eadf)}
```

### 点火器（正则 replaceString，单行；此处为可读分行，交付须脚本序列化成单行）

```js
// findRegex: /<悬浮球>/   replaceString:
<img src="x" data-float-ball="1" style="display:none" onerror="(function(e){
  if(document.getElementById('z-fab')){e.remove();return;}
  var fab=document.createElement('button');fab.id='z-fab';fab.className='z-float-ball';fab.textContent='✦';
  var menu=document.createElement('div');menu.id='z-fab-menu';menu.className='z-float-menu';
  menu.onclick=function(ev){ev.stopPropagation();};
  var ms=['📜 回顾剧情','🎲 随机事件','⚙️ 打开设置'];
  var acts=['请回顾目前剧情进展','触发一个随机事件',''];
  for(var i=0;i<ms.length;i++){(function(idx){               // 闭包捕获 idx
    var mi=document.createElement('div');mi.className='z-float-menu-item';mi.textContent=ms[idx];
    mi.onclick=function(ev){ev.stopPropagation();
      if(idx===2){var dr=document.getElementById('z-drawer');if(dr)dr.classList.add('z-open');} // 开抽屉
      else{var a=document.querySelector('.uni-textarea-textarea');                              // 回填输入框
           if(a){a.value=acts[idx];a.dispatchEvent(new Event('input',{bubbles:true}));}}
      menu.classList.remove('z-open');};
    menu.appendChild(mi);})(i);}
  var moved=false,sx=0,sy=0,ox=0,oy=0,GAP=8;
  var reposition=function(){                                  // 菜单跟随本体 + 翻转避裁
    if(!menu.classList.contains('z-open'))return;
    var r=fab.getBoundingClientRect(),mw=menu.offsetWidth,mh=menu.offsetHeight;
    var vw=window.innerWidth,vh=window.innerHeight,top;
    if(r.top-GAP-mh>=0){top=r.top-GAP-mh;}                    // 上方放得下→上方
    else if(r.bottom+GAP+mh<=vh){top=r.bottom+GAP;}          // 否则→下方
    else{top=Math.max(GAP,Math.min(vh-mh-GAP,r.top));}        // 都放不下→贴可见边
    var left=Math.max(GAP,Math.min(vw-mw-GAP,r.left));        // 水平夹取进视口
    menu.style.left=left+'px';menu.style.top=top+'px';menu.style.bottom='auto';};
  var onMove=function(cx,cy){if(Math.abs(cx-sx)>3||Math.abs(cy-sy)>3)moved=true;
    var nx=ox+cx-sx,ny=oy+cy-sy,vw=window.innerWidth,vh=window.innerHeight,bw=fab.offsetWidth,bh=fab.offsetHeight;
    nx=Math.max(0,Math.min(vw-bw,nx));ny=Math.max(0,Math.min(vh-bh,ny));   // 本体夹取进视口
    fab.style.left=nx+'px';fab.style.top=ny+'px';fab.style.bottom='auto';reposition();};
  var mm=function(ev){onMove(ev.clientX,ev.clientY);};
  var tm=function(ev){var t=ev.touches[0];onMove(t.clientX,t.clientY);ev.preventDefault();};
  var up=function(){document.removeEventListener('mousemove',mm);document.removeEventListener('mouseup',up);
    document.removeEventListener('touchmove',tm);document.removeEventListener('touchend',up);fab.style.cursor='grab';
    if(!moved){if(menu.classList.contains('z-open')){menu.classList.remove('z-open');}
      else{menu.classList.add('z-open');reposition();}}};   // 未拖动=切换菜单
  var down=function(cx,cy){moved=false;sx=cx;sy=cy;var r=fab.getBoundingClientRect();ox=r.left;oy=r.top;fab.style.cursor='grabbing';};
  fab.addEventListener('mousedown',function(ev){ev.stopPropagation();down(ev.clientX,ev.clientY);
    document.addEventListener('mousemove',mm);document.addEventListener('mouseup',up);});
  fab.addEventListener('touchstart',function(ev){ev.stopPropagation();var t=ev.touches[0];down(t.clientX,t.clientY);
    document.addEventListener('touchmove',tm,{passive:false});document.addEventListener('touchend',up);});
  document.body.appendChild(fab);document.body.appendChild(menu);e.remove();
})(this)">
```

---

## 二、侧边栏抽屉（滑入/滑出）

要点：默认 `translateX(100%)` 藏在屏外；点贴边 ☰ 按钮 `classList.toggle('z-open')` 滑入/滑出。条目可点击。

### CSS 类

```css
.z-sidebar-btn{position:fixed;right:0;top:30%;background:var(--z-float-surface,#fff);color:var(--z-float-text,#2b2b2b);
  border:1px solid var(--z-float-accent,#B38F5C);border-right:none;padding:10px 7px;border-radius:8px 0 0 8px;
  z-index:99998;cursor:pointer;font-size:18px;box-shadow:-2px 2px 10px var(--z-float-shadow,rgba(179,143,92,.35))}
.z-drawer{position:fixed;right:0;top:0;height:100%;width:240px;background:var(--z-float-surface,#fff);color:var(--z-float-text,#2b2b2b);
  border-left:1px solid var(--z-float-accent,#B38F5C);z-index:99997;transform:translateX(100%);transition:transform .35s ease;
  padding:46px 16px 16px;box-shadow:-4px 0 16px rgba(0,0,0,.3);overflow-y:auto;box-sizing:border-box}
.z-drawer.z-open{transform:translateX(0)}
.z-drawer-title{color:var(--z-float-accent,#B38F5C);font-weight:700;font-size:16px;margin-bottom:12px;
  border-bottom:1px solid var(--z-float-accent,#B38F5C);padding-bottom:6px}
.z-drawer-item{padding:8px 6px;border-radius:6px;cursor:pointer;margin-bottom:4px}
.z-drawer-item:hover{background:var(--z-float-surface-hover,#f2eadf)}
```

### 点火器

```js
// findRegex: /<侧边栏>/   replaceString（单行）:
<img src="x" data-sidebar="1" style="display:none" onerror="(function(e){
  if(document.getElementById('z-drawer')){e.remove();return;}
  var tg=document.createElement('button');tg.id='z-drawer-btn';tg.className='z-sidebar-btn';tg.textContent='☰';
  var dr=document.createElement('div');dr.id='z-drawer';dr.className='z-drawer';
  dr.onclick=function(ev){ev.stopPropagation();};
  var ti=document.createElement('div');ti.className='z-drawer-title';ti.textContent='❖ 角色档案';dr.appendChild(ti);
  var items=['👤 姓名：林夏','📜 任务：调查匿名信','⚙️ 设置'];
  for(var i=0;i<items.length;i++){var it=document.createElement('div');it.className='z-drawer-item';it.textContent=items[i];dr.appendChild(it);}
  tg.onclick=function(ev){ev.stopPropagation();dr.classList.toggle('z-open');};
  document.body.appendChild(dr);document.body.appendChild(tg);e.remove();
})(this)">
```

---

## 陷阱（实测踩过，必避）

这两条都会让悬浮组件**静默不渲染**（`img onerror` 抛错不进控制台），且 validate 查不出，只有实机/全景预览能发现。

### 1. 菜单/模板里的字面 `[键=值]` 会被信标转换器吃掉

若项目里有数据信标转换器（优先级正则 `/\[([^=\]]+)=([^\]]+)\]/g` → `<span style="display:none">…</span>`），它会扫过**整条消息的 HTML，包括你悬浮组件 onerror 里的 JS 源码字符串**。一旦你的菜单动作要回填「状态栏格式要求」这类含 `[姓名=][HP=当前/上限]` 的模板，这些方括号会在渲染时被替换成 `<span>`，把 JS 字符串字面量啃断 → 语法错误 → 整个组件挂掉。

**避法**：组件源码里**不要出现任何字面 `[键=值]`**。方括号用变量拼：
```js
var L=String.fromCharCode(91),R=String.fromCharCode(93);   // [ 和 ]，避开信标正则
var F=function(k){return L+k+'='+R;};
fillTA('请按格式输出：'+F('姓名')+F('职业')+L+'HP=当前/上限'+R+' …');
```
> 注意连 `var L='[',R=']'` 这种写法也不行——源码里 `['` 后面跟 `,R=']` 仍会拼出 `[',R=']` 被正则命中。必须用 `String.fromCharCode`。**注释里也不能写 `[键=值]`**（flatten 后照样被吃）。

### 2. onerror 里的 JS（含注释）禁用 ASCII 双引号

组件 JS 整段塞进 `onerror="…"` 属性。源码里任何 ASCII `"`（哪怕在 `/* 注释 */` 里，如 `核心"切割"质感`）都会提前闭合属性 → 语法错误。**字符串统一用单引号；注释里的引号用全角「」**。打包脚本若不剥离注释，这条尤其致命。

> 下面两条不致渲染失败，但会让交互**看起来卡顿/错乱**，validate 同样查不出，实机/预览拖动时才暴露。

### 3. 可拖动元素禁用 `transition:all`（拖动卡顿根因）

悬浮球常给 hover 加过渡（如太极反色、旋转）。若图省事写 `transition:all .25s`，那么拖动时每帧改的 `left/top` 也会被纳入过渡 → 球用 0.25s 补间"滑"向鼠标位置、永远追不上指针，看起来就是**拖动卡顿/有拖影延迟**。

**避法**：transition 只列**视觉属性**，绝不含 `left`/`top`/`transform`（若 transform 不用于拖动可保留）：
```css
/* 错：拖动卡顿 */ .z-fab{transition:all .25s}
/* 对：位置即时跟手，hover 动画照旧 */ .z-fab{transition:background .25s,color .25s,transform .25s}
```
> 位置用 `left/top` 拖动时，transition 里必须排除 `left`/`top`。若用 `transform:translate` 拖动，则排除 `transform`。

### 4. 贴边按钮组容器禁用默认 `align-items:stretch`（hover 一个全变宽）

侧边栏多个贴边按钮常放进 `display:flex;flex-direction:column` 的竖向容器。flex 容器**交叉轴默认 `align-items:stretch`**——某个按钮 `:hover` 变宽（如 `width:44px→52px`）会把容器撑宽，于是**同列其余按钮被 stretch 拉到同宽**，看起来"hover 一个、三个一起动"。

**避法**：容器显式设 `align-items:flex-end`（贴右边栏）或 `flex-start`，让每个按钮**独立宽度**，只有 hover 的那个变宽：
```css
/* 错：hover 单个按钮，同列全变宽 */ .z-sidebtns{display:flex;flex-direction:column;gap:8px}
/* 对：只有 hover 的按钮拉伸 */ .z-sidebtns{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
```

---

## 调用清单

1. **配色契约**：上面 CSS 使用组件自有 `--z-float-*` 变量，并为每个 `var()` 提供可独立工作的 fallback；`global-css.md` **不会自动提供**这些变量。若要跟随某个全局主题，必须在组件实际元素上显式写 adapter，例如 `.z-float-ball,.z-float-menu,.z-sidebar-btn,.z-drawer{--z-float-accent:var(--mytheme-accent);--z-float-surface:var(--mytheme-surface);--z-float-text:var(--mytheme-text)}`，其中 `--mytheme-*` 换成该 bundle 的真实前缀。若项目另建共享 wrapper，也可把同一 adapter 放到 wrapper。旧 `--ac/--cb/--cbm/--fc` 只可在 legacy 组件局部 adapter 中出现。
2. **CSS 类位置**：把上面 `<style>` 拼进美化条/状态栏样式条的 `replaceString`，触发标记进 `statusbar`/`beginning`。
3. **触发标记**：`<悬浮球>`/`<侧边栏>` 写进第一句话（`beginning`）或 `statusbar`，由对应正则消费——别留**悬空标记**（validate 会报错）。
4. **菜单动作**：改 `acts` 数组与 `mi.onclick` 分支即可换行为（回填输入框/开抽屉/打开你自己的弹层）。回填输入框统一用选择器 `.uni-textarea-textarea`（与状态栏选项按钮一致）。
5. **序列化**：`replaceString` 必须脚本序列化成单行（换行转 `\n`、引号转 `\"`、无 BOM），禁手写多行——见 ../output/regex-output.md 2.3。
6. **验证**：`validate.py --platform mmd` 必 0 错 → `build-preview.py --platform mmd`（默认 `--mode both`）看三面板"悬浮组件预览"+全景预览，实测拖动、菜单跟随、翻转、选项点击。本文写法在当前 MMD 与本地酒馆均已验证通过；沙盒模式请勿套用（见「平台红线」）。

> 现成资产与生成器：`../../assets/shadowcast-examples/` 下的 `build_float.py`、`悬浮球侧边栏-影渲法.mmd.json` 和 `README.md`。生成器当前默认输出名以脚本 `--help` / README 为准；用 `../../scripts/build-preview.py` 生成预览，不再引用仓库中不存在的 fixture 脚本。
