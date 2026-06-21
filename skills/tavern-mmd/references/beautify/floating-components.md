# 悬浮组件（可拖动悬浮球 / 侧边栏抽屉 / 带菜单的悬浮按钮）

MMD 真正的悬浮组件是**运行时注入的可交互元素**：悬浮球是一个可以在页面上拖动的按钮，点击展开菜单；侧边栏是从屏幕外滑入的抽屉。它们不是静态写死的 HTML，而是由正则 `replaceString` 里的 `img onerror` 点火器在渲染时 `createElement` 注入 `document.body`。

本文档给出**两个平台都验证过**的认证写法，供后续直接调用/改配色。预览验证用 `scripts/build-preview.py`（悬浮组件会被自动归入"悬浮组件预览"面板，全景预览里与其他组件组合显示）。

> 💡 **Shadow DOM 变体（2026-06-17 当前 MMD 实测可行，可选增强）**：可把组件 UI 包进 shadow root 拿样式隔离。实测靶 10-11 全绿：**host 挂 `document.body` + shadow 内 `position:fixed` + `z-index:2147483647` 浮在消息之上 + 拖动 + `getElementById` 单例防重**全部成立。收益：组件 CSS 不外泄污染平台、平台强制染色渗不进来、不过 markdown 管线（无空白条）；代价：多一层 `attachShadow` 包装。**关键：host 必须 `appendChild` 到 `document.body`**（不能留消息气泡内，否则被气泡 stacking context 困住、被新消息盖住——这正是"开场白里球被消息盖住"的根因）。写法：`var wrap=document.createElement('div');wrap.id='z-fab-wrap';var sr=wrap.attachShadow({mode:'open'});`（CSS+按钮 createElement 进 sr）`document.body.appendChild(wrap);`。**铁律照旧**：onerror 双引号包裹、内部全单引号、**禁内部裸双引号**（裸 `<`/`>` 经实机证实无害，见 ../platforms/mmd.md §2）。本文档下方 light DOM 写法仍是跨版本最稳基线；shadow 变体用于需要强隔离的场景。全局美化**不可** shadow 化（它要穿透改平台元素，与隔离相反）。

---

## 平台红线（决定写法）

| 限制 | oldmmd | mmd（当前） |
|---|---|---|
| `<script>` | 剥离不执行 → **必须 img onerror 点火** | 可用，但 img onerror 仍是跨版本回退首选 |
| `style.cssText=` | 报 Unexpected identifier → **禁用** | 仅告警 |
| `el.innerHTML=` | 易被破坏 → **禁用** | 仅告警 |
| `onerror` 多行 | CSP 破坏多行 → **必须单行** | 可多行 |
| 内联 `onclick` 写 DOM 赋值 | 单行可用 | **会被净化** → 用 `el.onclick=function(){}` |
| `el.style.left/top=`（单属性） | ✅ 允许 | ✅ 允许 |
| `classList.add/remove/toggle` | ✅ 允许 | ✅ 允许 |

**统一结论（两版通用的最稳写法）**：
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
  background:var(--ac);color:#fff;border:none;font-size:22px;z-index:99999;cursor:grab;
  box-shadow:0 3px 10px rgba(0,0,0,.3);touch-action:none}
.z-float-menu{position:fixed;display:none;background:var(--cb);color:var(--fc);
  border:1px solid var(--ac);border-radius:8px;padding:6px;z-index:99999;
  box-shadow:0 3px 10px rgba(0,0,0,.3);min-width:130px}
.z-float-menu.z-open{display:block}
.z-float-menu-item{padding:7px 10px;cursor:pointer;white-space:nowrap;border-radius:6px}
.z-float-menu-item:hover{background:var(--cbm)}
```

### 点火器（正则 replaceString，单行；此处为可读分行，交付须脚本序列化成单行）

```js
// findRegex: <悬浮球>   replaceString:
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
.z-sidebar-btn{position:fixed;right:0;top:30%;background:var(--cb);color:var(--fc);
  border:1px solid var(--ac);border-right:none;padding:10px 7px;border-radius:8px 0 0 8px;
  z-index:99998;cursor:pointer;font-size:18px;box-shadow:-2px 2px 10px var(--ac)}
.z-drawer{position:fixed;right:0;top:0;height:100%;width:240px;background:var(--cb);color:var(--fc);
  border-left:1px solid var(--ac);z-index:99997;transform:translateX(100%);transition:transform .35s ease;
  padding:46px 16px 16px;box-shadow:-4px 0 16px rgba(0,0,0,.3);overflow-y:auto;box-sizing:border-box}
.z-drawer.z-open{transform:translateX(0)}
.z-drawer-title{color:var(--ac);font-weight:700;font-size:16px;margin-bottom:12px;
  border-bottom:1px solid var(--ac);padding-bottom:6px}
.z-drawer-item{padding:8px 6px;border-radius:6px;cursor:pointer;margin-bottom:4px}
.z-drawer-item:hover{background:var(--cbm)}
```

### 点火器

```js
// findRegex: <侧边栏>   replaceString（单行）:
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

1. **配色**：上面 CSS 用了 `var(--ac)/--cb/--cbm/--fc`，这些由全局美化（`body.z-enabled` 主题变量，见 global-css.md / style-system.md）提供；无全局美化时给每个 `var()` 加 fallback（如 `var(--ac,#B38F5C)`）。
2. **CSS 类位置**：把上面 `<style>` 拼进美化条/状态栏样式条的 `replaceString`，触发标记进 `statusbar`/`beginning`。
3. **触发标记**：`<悬浮球>`/`<侧边栏>` 写进第一句话（`beginning`）或 `statusbar`，由对应正则消费——别留**悬空标记**（validate 会报错）。
4. **菜单动作**：改 `acts` 数组与 `mi.onclick` 分支即可换行为（回填输入框/开抽屉/打开你自己的弹层）。回填输入框统一用选择器 `.uni-textarea-textarea`（与状态栏选项按钮一致）。
5. **序列化**：`replaceString` 必须脚本序列化成单行（换行转 `\n`、引号转 `\"`、无 BOM），禁手写多行——见 ../output/regex-output.md 2.3。
6. **验证**：`validate.py --platform <mmd|oldmmd>` 必 0 错 → `build-preview.py`（默认 `--mode both`）看三面板"悬浮组件预览"+全景预览，实测拖动、菜单跟随、翻转、选项点击。oldmmd 与 mmd 同一套写法都已验证通过。

> 现成可跑样例：仓库根 `preview/gen_test_fixture.py` 生成的 `test-fixture-full.json` 含本文档全部组件（全局美化+侧边栏+悬浮球+状态栏），`--platform oldmmd` 与 `mmd` 审核均 0 错。
