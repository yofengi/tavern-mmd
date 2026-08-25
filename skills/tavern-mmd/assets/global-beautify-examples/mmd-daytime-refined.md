# MMD 日间模式全局美化（Legacy Selector Reference）

> **历史参考，非默认成品**：本文件保留的是 **2026-06-21 当前 MMD** 页面选择器与米白/酒红主题案例，仅适用于当前 MMD，不适用于旧版 MMD 或本地 SillyTavern。它来自用户提供的社区快照，作者、原 URL 与许可证未记录；skill 资产库仅作历史收录与最低限度债务修复，不宣称原创，也没有在本次整理中重新宣称 MMD 实机验证。
>
> 此案例把样式写到 `:root,body` 且大量选择器未用自有根属性作用域；清污脚本会移除平台类名、内联属性与私有变量，未记录 property delta，无法完整恢复；引号规范化也会直接改写文本节点，属于不可逆操作。它没有 `native` 恢复、`destroy`、owner/version 租约和完整路由重入生命周期，因此不再作为“直接可用”的默认推荐。
>
> 新产物优先使用架构启发后重新设计与实现的三态运行时主题包，见 [mmd-theme-runtime/README.md](mmd-theme-runtime/README.md)。

## 概述

这是一个用于查询 2026-06-21 当前 MMD 类名与覆盖面的 legacy selector reference，采用米白+酒红配色，记录当时案例覆盖的常用界面。

**覆盖范围**：
- 聊天页：气泡、输入框、快捷栏、长按菜单、开场白
- 模型设置：Token 上限、流式输出、预设提示词、模型卡片、分类标签
- 用户人设：输入框、性别按钮、头像区
- 对话设置：文风、人称、输出字数、深度
- 设定补充：自定义指令、各类开关
- 分享页：顶部栏、底部按钮
- 底部滚轮选择器、开关按钮

**三段式架构**：
1. **全局美化 CSS**：视觉主题（米白+酒红），通过 10 个 CSS 变量驱动配色
2. **清污引擎**：MutationObserver 常驻监听，自动移除 MMD 原生日夜模式残留污染
3. **引号修复**：修复双左引号 bug，接管 MMD 引号高亮（橙色 `<font>` 改为可控的 `.hdm`）

**特点**：
- 配色模块化：10 个 CSS 变量，换主题只需改变量值
- 清污自动化：MutationObserver 持续对抗 MMD 原生样式"反扑"
- 幂等清理：可反复执行，不会越清越多
- 钩子协同：清污引擎驱动引号修复，无需双重监听

## 历史复现方式

以下步骤仅用于维护者复现旧案例或提取选择器，不作为新项目的默认交付说明。在当前 MMD 正则替换系统中，旧案例按顺序使用以下三条规则；执行前应接受未作用域、不可完整恢复与文本改写的风险。

### 导入顺序
1. 先导入「全局美化 CSS」
2. 再导入「清污引擎」
3. 最后导入「引号修复」

### 替换方式
每条规则都是「查找正则表达式」→「替换为」：
- 查找表达式是 slash literal 包裹的**触发标记**（如 `/<css0>/`、`/<代码1>/`），必须避免与现有标记冲突
- 替换内容是完整的 `<style>...</style>` 或 `<script>...</script>`

## 配色变量

主题配色通过 10 个 CSS 变量驱动，定义在 `:root,body` 中。想换配色只需修改这 10 个变量值，无需改后续 1000+ 行选择器。

| 变量 | 含义 | 默认值（米白+酒红） | 用途 |
|---|---|---|---|
| `--b` | background（页面底色） | `#FDF5E6` 米黄 | body、顶栏、弹窗背景 |
| `--c` | card（卡片底色） | `#FFFDF9` 奶白 | 气泡、按钮、卡片背景 |
| `--f` | font（文字主色） | `#4A0E0E` 深酒红 | 正文颜色 |
| `--a` | accent（强调色） | `#7A1723` 酒红 | 标题、选中态、按钮、图标 |
| `--n` | input（输入框底色） | `#FFF4EB` 淡黄 | 输入框、文本域背景 |
| `--l` | layer（半透明遮罩） | `rgba(253,245,230,.78)` | 快捷栏、菜单半透明背景 |
| `--d` | divider（边框） | `#9B7A3D` 金棕 | 边框、分隔线 |
| `--s` | shadow（阴影） | `rgba(74,14,14,.12)` | 卡片阴影 |
| `--p` | placeholder（占位符） | `rgba(74,14,14,.55)` | 输入框 placeholder |
| `--i` | icon-filter（图标反色滤镜） | `brightness(0) saturate(100%) invert(14%)...` | 把白色图标染成酒红 |

**换配色示例**（改成深色夜间版）：
```css
:root,body{
  --b:#1a1a1a;  /* 页面底色改深灰 */
  --c:#2a2a2a;  /* 卡片改浅灰 */
  --f:#e0e0e0;  /* 文字改浅色 */
  --a:#ff6b9d;  /* 强调改粉色 */
  /* 其余变量类推 */
}
```

## 技术架构

### 1. 全局美化 CSS（段1）
- 1000+ 行 CSS，覆盖 MMD 全部常用界面
- 选择器精准对应 MMD 类名（`.topTabbar`、`.model-setting-scope`、`.role-setting` 等）
- 用 `!important` 覆盖 MMD 原生样式
- 特殊处理：输入框内联样式（`input.vig-native-input__el` 用 box-shadow inset 反向填充背景色）

### 2. 清污引擎（段2，历史内嵌快照）
- **MutationObserver 常驻监听** `body` 的 DOM/属性变化
- **白名单清理**：只移除 MMD 原生日夜模式特征（黑底/白字/粉蓝橙高亮/暗色类名/私有 CSS 变量）
- **幂等设计**：可反复执行，不会越清越多
- **页面切换自动卸载**：非聊天页不占内存
- **钩子接口**：`window._mmd_process(callback)` 让其他脚本（如引号修复）注册进清污队列

### 3. 引号修复（段3）
- **TreeWalker 遍历文本节点**：修复 `“文本“` 双左弯引号 bug（改为 `“文本”`），并把成对 ASCII 双引号规范化为弯引号；这是不可逆文本改写
- **接管 MMD 引号高亮**：把橙色 `<font>` 标签改为可控的 `.hdm` class（颜色由 CSS 定义）
- **防护机制**：跳过 `<script>`/`<style>` 内部文本，避免破坏代码
- **协同机制**：通过 `window._mmd_process` 注册进清污引擎，随 DOM 变化自动触发

## 正则规则

### 规则1：全局美化 CSS

**查找正则表达式**：`/<css0>/`

**替换为**：

（由于内容过长，这里给出结构，完整内容见原始文件「一、全局美化css」段）

```html
<style>
:root,body{
  --b:#FDF5E6;
  --c:#FFFDF9;
  --f:#4A0E0E;
  --a:#7A1723;
  --n:#FFF4EB;
  --l:rgba(253,245,230,.78);
  --d:#9B7A3D;
  --s:rgba(74,14,14,.12);
  --p:rgba(74,14,14,.55);
  --i:brightness(0) saturate(100%) invert(14%) sepia(85%) saturate(3150%) hue-rotate(345deg) brightness(85%) contrast(105%);
  background:var(--b);
  color:var(--f)
}

/* 1000+ 行选择器覆盖，完整内容见原文件 */
.topTabbar,.send-msg,.u-popup__content,...{...}
...
</style>
```

### 规则2：清污引擎

**查找正则表达式**：`/<代码1>/` 或 `/<cleanup>/`

**替换为（仅历史复现，使用下方旧快照）**：

```html
<script>
// 以下是 2026-06-21 旧 `_mmd_*` 清污快照，不是当前 mmd_cleanup_core.js（ZMR 2.0）的源码。
(function(){var W=window,D=document,O,A=1,T=0,B=0,P=0,Q=[],K='background,background-color,color,border-color,box-shadow,text-shadow,-webkit-text-fill-color,filter,--background-color,--primary-font-color,--input-font-color,--card-background-color,--input-background-color,--model-setting,--share-item-bg-color,--vig-native-ph-color'.split(','),X=/#(0d0e0f|101113|101014|141414|17181a|1a1a1a|1c1c1e|1e1f24|212226|25262a|2a2b30|33353b|fff|ffffff|dc8333|ff6d97|409eff|3c9cff|1989fa)|rgb\((255,\s*255,\s*255|13,\s*14,\s*15|16,\s*17,\s*19|23,\s*24,\s*26|30,\s*31,\s*36|220,\s*131,\s*51|255,\s*109,\s*151|64,\s*158,\s*255|25,\s*137,\s*250)\)|--(background-color|primary-font-color|input-font-color|card-background-color|input-background-color|model-setting|share-item-bg-color|vig-native)|box-shadow|filter|textarea-dark|input-dark|vditor|--lo/i;function ok(){return /chat\/chat/.test(location.hash)}try{W._mmd_off&&W._mmd_off()}catch(e){}if(!ok())return;function ev(m){W[m]('hashchange',ck);W[m]('popstate',ck);W[m]('pagehide',off);W[m]('beforeunload',off);W[m]('focus',wk);W[m]('pageshow',wk);D[m]('visibilitychange',wk)}function off(){A=0;clearTimeout(T);O&&O.disconnect();ev('removeEventListener');delete W._mmd_obs;delete W._mmd_process;delete W._mmd_off}function ck(){ok()||off()}function one(x){var s=(x.getAttribute('style')||'')+(x.getAttribute('color')||'');x.classList.remove('theme-dark','doc-markdown-body--dark','vditor--dark','active-dark');if(s&&X.test(s)){for(var i=0;i<K.length;i++)x.style.removeProperty(K[i]);x.getAttribute('style')||x.removeAttribute('style');x.removeAttribute('color')}}function inp(){D.querySelectorAll('.role-setting :is(uni-input,uni-textarea,input,textarea,.input-placeholder),.depth-input :is(input,.input-placeholder),.vig-native-input__el,.vig-native-textarea__el').forEach(x=>{var p=x.classList.contains('input-placeholder'),c=p?'var(--p)':'var(--f)';x.removeAttribute('color');['color','-webkit-text-fill-color'].map(y=>x.style.setProperty(y,c,'important'));p||x.style.setProperty('background','transparent','important')})}function cl(){var b=D.body;one(b);var a=b.querySelectorAll('[style],[color],.theme-dark,.doc-markdown-body--dark,.vditor--dark,.active-dark');for(var i=0;i<a.length;i++)one(a[i]);inp()}function run(){if(!A||!D.body)return;if(B)return P=1;B=1;O&&O.disconnect();try{cl();for(var i=0;i<Q.length;i++)try{Q[i]()}catch(e){}}finally{B=0;A&&O.observe(D.body,{childList:1,subtree:1,characterData:1,attributes:1,attributeFilter:['style','class','color']});P&&(P=0,wk(50))}}function wk(d){if(!A||T)return;T=setTimeout(()=>{T=0;run()},d||60)}W._mmd_process=f=>{f&&Q.indexOf(f)<0&&Q.push(f);wk(1)};W._mmd_off=off;O=new MutationObserver(()=>wk(60));W._mmd_obs=O;ev('addEventListener');run()})();
</script>
```

### 规则3：引号修复

**查找正则表达式**：`/<代码2>/` 或 `/<quote-fix>/`

**替换为**：

```html
<script>
(function(){
  var W=window,D=document,rg=/dc8333|220\s*,\s*131\s*,\s*51/i;
  if(!/chat\/chat/.test(location.hash))return;
  
  function bad(n){return /SCRIPT|STYLE|NOSCRIPT/.test(n&&n.parentElement&&n.parentElement.tagName)}
  
  function tx(n){
    if(!bad(n)){
      var s=n.nodeValue.replace(/“([^“”]*)“/g,'“$1”').replace(/"([^"\n]{1,800})"/g,'“$1”');
      s!=n.nodeValue&&(n.nodeValue=s)
    }
  }
  
  function walk(r){
    if(!r)return;
    if(r.nodeType==3)return tx(r);
    var w=D.createTreeWalker(r,4,{acceptNode:n=>bad(n)?2:1});
    while(w.nextNode())tx(w.currentNode)
  }
  
  function font(f){
    var s=D.createElement('span');
    s.className='hdm';
    while(f.firstChild)s.appendChild(f.firstChild);
    f.parentNode.replaceChild(s,f)
  }
  
  function mark(x){
    if(bad(x))return;
    var st=(x.getAttribute('style')||'')+(x.getAttribute('color')||'');
    if(rg.test(st)){
      x.classList.add('hdm');
      x.removeAttribute('color');
      'color,-webkit-text-fill-color,text-shadow'.split(',').forEach(p=>x.style.removeProperty(p))
    }
  }
  
  function task(){
    var b=D.body;
    if(!b)return;
    var a=b.getElementsByTagName('font'),i;
    for(i=a.length-1;i>=0;i--)font(a[i]);
    a=b.querySelectorAll('[color],[style*="dc8333" i],[style*="220, 131, 51"],[style*="220,131,51"]');
    for(i=0;i<a.length;i++)mark(a[i]);
    walk(b)
  }
  
  W._mhdm=task;
  W._mmd_process?W._mmd_process(task):task()
})();
</script>
```

## 完整 CSS（规则1 的完整内容）


```html
<style>:root,body{--b:#FDF5E6;--c:#FFFDF9;--f:#4A0E0E;--a:#7A1723;--n:#FFF4EB;--l:rgba(253,245,230,.78);--d:#9B7A3D;--s:rgba(74,14,14,.12);--p:rgba(74,14,14,.55);--i:brightness(0) saturate(100%) invert(14%) sepia(85%) saturate(3150%) hue-rotate(345deg) brightness(85%) contrast(105%);background:var(--b);color:var(--f)}.topTabbar,.send-msg,.u-popup__content,.u-safe-bottom,.header-scope,.more-options-scope,.modify-scope,.custom-instruction-scope,.role-setting,.u-picker,.model-setting-scope,.shortcut-bar-wrapper,.chat-bottom-wapper,.msg-option-scope,.preset-intro-scope,.mp-preset-scope,.role-extra-setting,.role-extra-setting .setting-top,.cs-modal-header,.cs-modal-header>*,.share-chat-page,.share-chat-scope,.share-chat-content,.share-chat-wrapper,.share-chat-topbar,.share-chat-btn-scope{background:var(--b)!important;color:var(--f)!important}:is(.custom-instruction-scope) .item,.shortcut-btn,.instruction-chip,.chat-input-tool-btn,.item-icon,:is(.role-extra-setting,.role-setting,.custom-instruction-scope) .card,.switch-card,.cs-group-card,.model-item,.conversation-item,.modify-item,.option-item,.prologue-content,.mp-preset-card,.mp-preset-item,.preset-intro-content,.mp-card,.mp-switch-row,.mp-token-btn,.card.textarea-wrapper,.input-wrapper{background:var(--c)!important;border:1px solid var(--d)!important;border-radius:8px;color:var(--f)!important;box-shadow:0 2px 6px var(--s)}.model-battery,.model-perm,.success-badge,.mp-preset-help{background:var(--b)!important;border:1px solid var(--d)!important;color:var(--f)!important;-webkit-text-fill-color:var(--f)!important;border-radius:6px;display:inline-flex;align-items:center;gap:3px;box-shadow:none;text-shadow:none!important}.model-battery *,.model-perm *,.success-badge *,.role-extra-setting :is(.depth-desc,.label,.picker-value){color:var(--f)!important;-webkit-text-fill-color:var(--f)!important}.u-toolbar{background:var(--c)!important;border-bottom:1px solid var(--d)!important}.chat-input-scope,.textarea-wrapper,.token-scope,.token-scope .item,.value.input-scope,.value.custom-textarea-box,.cs-custom-input,.token,.model-filter-tab,.role-setting .input-dark,.role-setting .textarea-dark,.role-setting .input-scope,.role-setting .custom-textarea-box,.custom-instruction-scope .input-scope,.custom-instruction-scope .custom-textarea-box{background:var(--n)!important;border:1px solid var(--d)!important;border-radius:8px;color:var(--f)!important;box-shadow:none}.option-box,.item-title,.model-filter-tabs,uni-input.input-dark,uni-textarea.textarea-dark,.textarea-dark,.input-dark,.cs-custom-textarea,.uni-input-wrapper,.uni-textarea-wrapper,.uni-input-input,.uni-textarea-textarea,.picker-field,.uni-select,.uni-radio-input,.prologue-scope{background:transparent!important;border:0!important;box-shadow:none!important}input.vig-native-input__el.input-dark,textarea.vig-native-textarea__el.textarea-dark{--vig-native-ph-color:var(--p)!important;background:var(--n)!important;background-image:none!important;color:var(--f)!important;-webkit-text-fill-color:var(--f)!important;border:1px solid var(--d)!important;border-radius:8px;box-shadow:0 0 0 1000px var(--n) inset!important;filter:none!important;opacity:1!important}.depth-input{background:var(--n)!important;border:1px solid var(--d)!important;border-radius:8px;color:var(--f)!important;box-shadow:none;display:inline-flex;align-items:center}.depth-input input,.depth-input .uni-input-input,.depth-input .vig-native-input__el{background:transparent!important;border:0!important;box-shadow:none!important;color:var(--f)!important;-webkit-text-fill-color:var(--f)!important;text-shadow:none!important;filter:none!important;opacity:1!important}input,textarea,uni-input.input-dark,uni-textarea.textarea-dark,.uni-input-input,.uni-textarea-textarea,.chatMsgTextarea,.chat-input-collapsed-text{color:var(--f)!important;-webkit-text-fill-color:var(--f)!important;caret-color:var(--a)!important}.uni-input-placeholder,.uni-textarea-placeholder,.limit,.char-count,.char-count span,.count-text,.count-text span,input::placeholder,textarea::placeholder,.role-extra-setting .input-placeholder{color:var(--p)!important;-webkit-text-fill-color:var(--p)!important}:is(.u-popup__content,.shortcut-bar-wrapper,.instruction-bar,.topTabbar,.chat-input-scope,.chat-bottom-wapper,.modify-scope,.custom-instruction-scope,.role-setting,.u-picker,.model-setting-scope,.msg-option-scope,.preset-intro-scope) *{color:var(--f)!important;text-shadow:none!important}.header-roleName,.title,.card-title,.cs-header-title,.model-title,.prologue-title,.complete-btn,.page-title,.confirm-title{color:var(--a)!important;font-weight:700}uni-text.u-toolbar__wrapper__cancel,.u-toolbar__wrapper__cancel span,.model-intro,.sub-title,.des-scope,.tips,.card-desc,.icon-back{color:var(--p)!important;text-shadow:none!important}.token-scope .selected,.ok-btn,.bottom .btn,.modify-btn,.gen-link-btn,.u-switch--on,.beta-badge,.token.selected,.header-badge,.mp-token-btn.selected{background:var(--a)!important;color:#fff!important;border-color:var(--a)!important}.token-scope .selected *,.ok-btn *,.bottom .btn *,.beta-badge *,.header-badge *,.mp-token-btn.selected *{color:#fff!important}.model-filter-tab.active,.model-filter-tab.active-dark{background:var(--a)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border-color:var(--a)!important;box-shadow:0 3px 10px rgba(122,23,35,.18)!important;filter:none!important;text-shadow:none}:is(.header-scope,.header-box) .complete-btn,.u-toolbar__wrapper__confirm,.save-btn,:is(.confirm-scope,.confirm-bottom,.alert-scope,.alert-bottom) .ok-btn,:is(.cs-modal-header,.cs-header-right) .confirm-btn,.btn-scope .save-btn,.mp-energy-pill{background:var(--c)!important;color:var(--a)!important;-webkit-text-fill-color:var(--a)!important;border:1px solid var(--a)!important;border-radius:999px;padding:2px 9px;min-height:22px;line-height:18px;display:inline-flex;align-items:center;justify-content:center;box-shadow:0 1px 4px var(--s);font-weight:700}:is(.header-scope,.header-box) .complete-btn *,.u-toolbar__wrapper__confirm *,.save-btn *,:is(.confirm-scope,.confirm-bottom,.alert-scope,.alert-bottom) .ok-btn *,:is(.cs-modal-header,.cs-header-right) .confirm-btn *,.btn-scope .save-btn *,.mp-energy-pill *{color:var(--a)!important;-webkit-text-fill-color:var(--a)!important}.u-popup__content:has(.u-picker),.u-picker.u-picker,.u-toolbar.u-toolbar,.u-picker__view.u-picker__view,.uni-picker-view-wrapper,.u-picker__view__column,.uni-picker-view-group,.uni-picker-view-content,.u-popup__content:has(.share-chat-btn-scope),.u-popup__content:has(.share-chat-btn-scope) .u-safe-bottom{background:var(--b)!important;color:var(--f)!important;text-shadow:none!important}.u-picker .uni-picker-view-mask{background:linear-gradient(180deg,var(--b) 0,rgba(253,245,230,.45) 38%,rgba(253,245,230,0) 50%,rgba(253,245,230,.45) 62%,var(--b) 100%)!important}.u-picker .uni-picker-view-indicator{background:rgba(122,23,35,.1)!important;border-top:1px solid var(--a)!important;border-bottom:1px solid var(--a)!important}.u-picker .u-picker__view__column__item,.u-picker .u-picker__view__column__item.u-line-1{color:var(--f)!important;-webkit-text-fill-color:var(--f)!important;opacity:1!important;text-align:center;text-shadow:none!important}.u-picker .u-picker__view__column__item--selected{color:var(--a)!important;-webkit-text-fill-color:var(--a)!important;opacity:1!important;font-weight:900;background:rgba(122,23,35,.16)!important;border-radius:8px}.u-picker .u-toolbar__wrapper__cancel,.u-picker .u-toolbar__wrapper__cancel *{color:var(--p)!important;-webkit-text-fill-color:var(--p)!important;background:transparent!important;border:0!important;box-shadow:none!important}.u-picker .u-toolbar__wrapper__confirm,.u-picker .u-toolbar__wrapper__confirm *{color:var(--a)!important;-webkit-text-fill-color:var(--a)!important;background:transparent!important;border:0!important;box-shadow:none!important}.uni-radio-input{background:var(--b)!important;border:1px solid var(--d)!important}.uni-radio-input:has(svg),.corner-check,.u-switch:has(.u-switch__node--on),.radio-item:has(svg) .uni-radio-input,.mp-preset-item.selected .mp-pi-radio{background:var(--a)!important;border-color:var(--a)!important}.model-item.model-item-active,.model-item:has(.corner-check){box-shadow:0 0 0 1px rgba(122,23,35,.26),0 0 8px 2px rgba(122,23,35,.28),0 0 14px 4px rgba(122,23,35,.14),inset 0 0 8px rgba(122,23,35,.06)!important}.css-check{border-color:#fff!important}.chat-body .content.left{background:var(--c)!important;color:var(--f)!important;border:0!important;box-shadow:0 2px 5px var(--s);opacity:1!important;backdrop-filter:none;border-radius:8px}.chat-body .content.left .msg-content-box,.chat-body .content.left .msg-options-box,.chat-body .content.left .msg-mask{background:var(--c)!important;border:0!important;box-shadow:none!important}.chat-body .content.right,.chat-body .content.right *{background:var(--a)!important;color:#fff!important;border-color:var(--a)!important;border:0!important;border-radius:8px}.chat-body .content.right .msg-content-box,.chat-body .content.right .msg-options-box,.chat-body .content.right .msg-mask{background:var(--a)!important;border:0!important;box-shadow:none!important}.shortcut-bar-wrapper{background:var(--l)!important;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);padding:5px 10px}.shortcut-bar,.instruction-bar{background:transparent!important;border:0!important;box-shadow:none!important;height:auto;min-height:28px;gap:6px;padding:0}.shortcut-btn,.instruction-chip,.chat-input-tool-btn{display:inline-flex;align-items:center;justify-content:center;gap:4px;min-height:30px;line-height:1.1;text-align:center}.shortcut-btn .sb-text,.shortcut-btn .sb-text span,.instruction-chip{display:inline-flex;align-items:center;justify-content:center;text-align:center}.instruction-bar .back-btn{background:var(--c)!important;border:1px solid var(--d)!important;border-radius:50%;box-shadow:none!important;filter:none!important;text-shadow:none!important;color:var(--a)!important;display:flex;align-items:center;justify-content:center}.instruction-bar .back-btn *{box-shadow:none!important;filter:none!important;text-shadow:none!important}.instruction-bar .back-arrow,.instruction-bar .back-arrow span{background:transparent!important;color:var(--a)!important;-webkit-text-fill-color:var(--a)!important}.back-btn img[src*="arrow_back2_dark"],.icon-back uni-image img[src*="arrow_back2_dark"],.modify-scope uni-image img[src*="arrow_back2_dark"],uni-image img[src*="arrow_back2_dark"],:is(.chat-input-scope,.more-options-scope,.header-meun,.ai-assistant,.close-btn,.model-opt-btn,.custom-instruction-scope,.modify-scope,.role-setting,.power,.msg-options-box,.shortcut-bar-wrapper,.chat-bottom-wapper,.model-setting-scope) uni-image,.topTabbar .icon-back uni-image,.topTabbar .header-meun uni-image,.radio-lock{filter:var(--i)!important;opacity:1!important}.model-battery .icon-battery,.model-battery img[src*="ico_battery2_white"],.model-perm .paid-icon,.model-perm img[src*="ico_crown"]{filter:var(--i)!important;opacity:1!important;background:transparent!important;border:0!important;box-shadow:none!important}:is(.topTabbar,.more-options-scope,.chat-bottom-wapper,.chat-input-scope,.shortcut-bar-wrapper,.msg-option-scope,.model-setting-scope) svg,:is(.topTabbar,.more-options-scope,.chat-bottom-wapper,.chat-input-scope,.shortcut-bar-wrapper,.msg-option-scope,.model-setting-scope) svg *{color:var(--a)!important;fill:var(--a)!important;stroke:var(--a)!important;opacity:1!important}.header-role-img,.header-role-img uni-image,.header-role-img div,.header-role-img img,.avatar img,.character-avatar{filter:none!important;background:transparent!important}.avatar{position:relative;z-index:10}.avatar img,.character-avatar{border-radius:50%;box-shadow:0 1px 3px var(--s)}.beta-badge uni-image{filter:brightness(0) invert(1)!important}.hdm,p .hdm,blockquote .hdm,li .hdm,h1 .hdm,h2 .hdm,h3 .hdm,h4 .hdm,h5 .hdm,h6 .hdm{color:#8B0000!important;-webkit-text-fill-color:#8B0000!important;font-weight:700;text-shadow:0 1px 2px rgba(0,0,0,.08)!important}.prologue-title{background:var(--c)!important;border:1px solid var(--d)!important;border-radius:20px;padding:6px 16px;width:fit-content;margin:0 auto 12px;display:block;text-align:center;box-shadow:0 2px 5px var(--s)}.prologue-scope{width:100%!important;text-align:center!important}.prologue-scope .prologue-title{display:inline-flex!important;align-items:center;justify-content:center;align-self:center!important;margin-left:auto!important;margin-right:auto!important;text-align:center!important}.prologue-scope .prologue-content{align-self:stretch!important;text-align:left!important}.prologue-title span{background:transparent!important;color:var(--a)!important;-webkit-text-fill-color:var(--a)!important}.msg-option-scope{background:var(--l)!important;backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px)}.msg-option-scope .msg-content-box,.msg-option-scope .msg-options-box{background:var(--c)!important;border:1px solid var(--d)!important;border-radius:12px!important;box-shadow:0 4px 15px var(--s)!important}.msg-option-scope .option-item{background:transparent!important;border:none!important;box-shadow:none!important}.msg-option-scope .option-separator{background:var(--d)!important;height:1px!important;margin:0!important}.modify-input-box{background:var(--b)!important;border:1px solid var(--d)!important;border-radius:10px;color:var(--f)!important;box-shadow:0 2px 8px var(--s);padding:8px}.vditor{border:1px solid var(--d)!important;border-radius:10px;overflow:hidden;box-shadow:none}:is(.role-setting,.custom-instruction-scope) input,:is(.role-setting,.custom-instruction-scope) textarea{background:var(--n)!important;color:var(--f)!important;-webkit-text-fill-color:var(--f)!important;border-color:var(--d)!important;box-shadow:none!important}::-webkit-scrollbar{width:8px}::-webkit-scrollbar-thumb{background:var(--a)!important;border-radius:4px;border:0}.role-extra-setting :is(.textarea-wrapper,.textarea-dark,.uni-textarea-wrapper,textarea){background:var(--n)!important;color:var(--f)!important;-webkit-text-fill-color:var(--f)!important}.u-switch{background:var(--c)!important;border:1px solid var(--a)!important}.u-switch__node{background:var(--c)!important;border:1px solid var(--a)!important;box-shadow:0 1px 4px var(--s)}.u-switch__node--on{border-color:var(--c)!important}.radio-item:has(svg){color:var(--f)!important}.radio-item:has(svg) svg path,.uni-radio-input:has(svg) svg path{fill:#fff!important}.share-chat-topbar .cancel-btn,.share-chat-topbar .toggle-chat-history-btn,.share-chat-topbar .header-roleName{color:var(--a)!important;-webkit-text-fill-color:var(--a)!important;text-shadow:none!important}.share-chat-btn-scope .btn-item{background:transparent!important;border:0!important;box-shadow:none!important;color:var(--f)!important}.share-chat-btn-scope .btn-item-icon{background:var(--c)!important;border:1px solid var(--d)!important;border-radius:50%;box-shadow:0 2px 6px var(--s);display:flex;align-items:center;justify-content:center}.share-chat-btn-scope .btn-item-icon uni-image{opacity:1!important}.share-chat-btn-scope .btn-item-icon uni-image>div,.share-chat-btn-scope img[src*="ico_share4"],.share-chat-btn-scope img[src*="ico_save_pic"],.share-chat-btn-scope img[src*="ico_comment2_dark"]{filter:var(--i)!important;opacity:1!important}.share-chat-btn-scope .btn-item-title{color:var(--f)!important;-webkit-text-fill-color:var(--f)!important;text-shadow:none!important;text-align:center}.topTabbar::before,.topTabbar::after{display:none!important;background:transparent!important}.topTabbar .header-center,.topTabbar .header-role-img{position:relative;z-index:2}.topTabbar .header-role-img,.topTabbar .header-role-img uni-image,.topTabbar .header-role-img uni-image div,.topTabbar .header-role-img img{filter:none!important;background-color:transparent!important;opacity:1!important;z-index:3}.topTabbar .header-role-img img{display:block!important}.mp-pi-radio{width:18px;height:18px;border:2px solid var(--d)!important;border-radius:50%;background:var(--c)!important;box-shadow:none!important;position:relative}.mp-preset-item.selected .mp-pi-radio::after{content:"";position:absolute;left:50%;top:50%;width:6px;height:6px;border-radius:50%;background:#fff;transform:translate(-50%,-50%)}.gender-item,.cs-style-item{background:var(--c)!important;border:1px solid var(--d)!important;border-radius:8px;color:var(--f)!important;box-shadow:0 2px 6px var(--s);display:flex;align-items:center;justify-content:center}.gender-item.active,.cs-style-item.active{background:var(--a)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border-color:var(--a)!important}.gender-item.active *,.cs-style-item.active *{color:#fff!important;-webkit-text-fill-color:#fff!important}.cs-style-item uni-image,.cs-style-item .intro-icon,.cs-style-item img[src*="ico_intro_help_dark"]{filter:var(--i)!important;opacity:1!important}.edit-icon,.delete-icon,uni-image.edit-icon,uni-image.delete-icon,.edit-icon>div,.delete-icon>div,.edit-icon img,.delete-icon img,img[src*="ico_edit6_light"],img[src*="ico_delete6_light"]{filter:var(--i)!important;opacity:1!important}.confirm-edit-scope,.confirm-edit-content{background:var(--b)!important;color:var(--f)!important}.confirm-edit-title{color:var(--a)!important;font-weight:700}.confirm-edit-scope .input-scope{background:var(--n)!important;border:1px solid var(--d)!important;border-radius:8px!important;box-shadow:0 2px 6px var(--s);color:var(--f)!important}.confirm-edit-scope .input-scope .uni-input-wrapper,.confirm-edit-scope .input-scope .uni-input-input{background:transparent!important;border:0!important;box-shadow:none!important;color:var(--f)!important;-webkit-text-fill-color:var(--f)!important}.confirm-edit-scope .input-placeholder{color:var(--p)!important;-webkit-text-fill-color:var(--p)!important}.confirm-edit-scope .ok-btn,.confirm-edit-bottom .ok-btn{background:var(--c)!important;color:var(--a)!important;-webkit-text-fill-color:var(--a)!important;border:1px solid var(--a)!important;border-radius:999px;padding:2px 12px;min-height:24px;line-height:20px;display:inline-flex;align-items:center;justify-content:center;box-shadow:0 1px 4px var(--s);font-weight:700}.confirm-edit-scope .ok-btn *,.confirm-edit-bottom .ok-btn *{color:var(--a)!important;-webkit-text-fill-color:var(--a)!important}.chat-body .content.right .hdm,.chat-body .content.right .hdm *,.content.right .hdm,.content.right .hdm *{color:#fff!important;-webkit-text-fill-color:#fff!important;text-shadow:none!important;font-weight:inherit!important}</style>
```

## 作者与来源

- **社区快照边界**：原始案例《【6.21改四版】新版MMD日间版全局美化+清污+引号修复》（记录日期 2026-06-21）是用户提供的社区文档快照；作者、原 URL 与许可证未记录，仅作兼容研究参考，不宣称原创。本文件保留其历史选择器与结构，不能据此推定当前页面仍全部一致。
- **skill 历史整理**：tavern-mmd 资产库于 2026-06-22 收录旧案例；本文代码块保留当时 `_mmd_*` 清污快照。本次只修复文档与兼容债务，不把该旧方案改称原创或重新验证的成品。
- **架构启发后的重写**：运行时生命周期、三态切换与可恢复策略见 `../../references/beautify/theme-runtime.md`；当前 `mmd_cleanup_core.js` 已是 ZMR 2.0 cleanup factory，不等同于本文历史快照。对应主题资产见 `mmd-theme-runtime/README.md`，其验证状态以资产 README 和测试记录为准。
