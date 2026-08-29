# MMD 真实聊天页 DOM/CSS 契约（实测抓取 2026-08-28）

来源：`https://www.sexyai.ai/#/pages/chat/chat?roleId=283787`（旧聊天页 chatVersion:0）
与编辑页 `#/pages/role/create?id=283787` 右侧「对话测试」预览 iframe。
抓取手段：Playwright 进 `iframe#chatIframe`，读 `styleSheets` + `getComputedStyle`。

## 1. 层级骨架（真实，含 uni-app 壳）

```
iframe#chatIframe.chat-iframe        ← 聊天全部内容在这个 iframe 内
└ body[style="--background-color:#17181A; ...共29个变量"]
  └ div > uni-app > uni-page > uni-page-wrapper > uni-page-body
    ├ uni-view.msg-option-scope      长按菜单遮罩（fixed, z-index 99999, display:none）
    ├ uni-view.msg-modify-scope
    └ uni-view.chat                  ← 主容器，CSS 前缀全是 `.chat `
      ├ uni-view.page-header-scope > uni-view.topTabbar    顶栏 45px(2.8125rem)
      ├ uni-view.summary-banner-host
      ├ uni-view.chat-scope-box      ← position:fixed; w/h 100%; z-index 11
      │                                 inline: background:url(角色背景图) center/auto 100%
      │ └ uni-scroll-view.scroll-view.dark   inline: height:calc(100% - 3.2rem);
      │                                       margin-top:2.8125rem; z-index:999; bg transparent
      │   └ div.uni-scroll-view > div.uni-scroll-view > div.uni-scroll-view-content
      │     └ uni-view#msglistview.chat-body
      │       ├ uni-view > uni-view.item.Ai.avatar-body     ← 描述气泡（首条，通栏）
      │       │   └ .touch-scope > .content.left > uni-view  文本
      │       ├ uni-view > uni-view.item.Ai                 ← 开场白/AI消息
      │       │   ├ .select-box (display:none) 2×img.icon
      │       │   └ .touch-scope#item0
      │       │     ├ .content.left#q-1 > uni-view > p×N    ← 正则注入落点
      │       │     ├ .copy-scope (display:none)
      │       │     └ .modify-btn-scope  3×.modify-btn
      │       ├ uni-view.prologue-scope   .prologue-title>span + .prologue-content
      │       ├ uni-view.summary-bubble-host
      │       └ uni-view#chatBottom
      ├ uni-view.chat-scope-box-hidden   同结构影子副本（含 .header-card/.footer-card）
      ├ uni-view.chat-bottom             fixed bottom, z-index 999
      │ ├ .shortcut-bar-wrapper.theme-dark > .shortcut-bar > 6×.shortcut-btn
      │ └ .chat-bottom-wapper > .send-msg > .uni-textarea
      │     ├ .ai-assistant
      │     ├ .chat-input-scope.has-toolbar
      │     └ .more-options-scope
      ├ uni-view.mm-left-side-container   ← 官方侧边挂载点（fixed, top:50%, z-index 9999, left:0）
      ├ uni-view.mm-right-side-container  ← 同上 right:0
      └ 多个 uni-view.u-popup
```

**用户消息侧**：`.item.self` (justify-content:flex-end) + `.content.right`。本次会话无用户消息，class 由 CSS 反推。

## 2. 真实 CSS（去 data-v 后，§ = `.chat .chat-scope-box .scroll-view `）

```css
.chat .chat-scope-box .scroll-view { background-color:#f6f6f6; }   /* 被 inline 的 transparent 覆盖 */
§.chat-body { position:relative; padding-bottom:10.625rem; display:flex; flex-direction:column; font-size:15px; }
§.chat-body .item { display:flex; align-items:center; padding:0.71875rem 0.9375rem; }
§.chat-body .self { justify-content:flex-end; }
§.chat-body .self-select-show { justify-content:space-between; }
§.chat-body .item .left  { background-color:#fff; border-radius:1rem 1rem 1rem 0 !important; }
§.chat-body .item .right { background-color:#c2dcff; border-radius:1rem 1rem 0 !important; }
§.chat-body .item .touch-scope { position:relative; max-width:94%; color:var(--chat-content-font-color,#FFF); }
§.chat-body .item .touch-scope .content {
    padding:0.75rem;
    background:var(--background-color,#17181A);   /* ← 覆盖 .left 的白底 */
    opacity:0.9;
    box-shadow:0 0.125rem 0.125rem rgba(0,0,0,.01);
    border-radius:0.5rem;
    white-space:pre-line;                          /* ★★★ 关键 */
}
§.chat-body .item .touch-scope .content table { border-collapse:collapse; empty-cells:show; overflow:auto;
    border-spacing:0; display:block; word-break:keep-all; width:100%; }
§.chat-body .item .touch-scope .content table th { font-weight:600; }
§.chat-body .item .touch-scope .content table td,
§.chat-body .item .touch-scope .content table th { padding:6px 13px; border:1px solid #dfe2e5;
    word-break:normal; white-space:nowrap; }
§.chat-body .item .avatar { display:flex; justify-content:center; width:2.4375rem; height:2.4375rem;
    background:#4f7df5; border-radius:1.5625rem; overflow:hidden; }
§.chat-body .avatar-body { width:100%; }
§.chat-body .avatar-body .touch-scope { width:100%; max-width:100%; }
§.chat-body .avatar-body .touch-scope .left { border-radius:0.5rem !important; }   /* 首条不带尖角 */
§.chat-body .select-box { margin-right:0.625rem; }
§.chat-body .select-box .icon { width:1.25rem; height:1.25rem; }

.prologue-scope { padding:0 0.96156rem; }
.prologue-scope .prologue-title { text-align:center; }
.prologue-scope .prologue-title span { background:rgba(0,0,0,.5); border-radius:0.46875rem;
    font-size:0.875rem; color:#fff; padding:0.3125rem 0.625rem; }
.prologue-scope .prologue-content { display:flex; align-items:center; min-height:2.8125rem; height:auto;
    background:var(--background-color,#17181A); opacity:.9; border-radius:0.375rem;
    font-size:0.8125rem; color:var(--chat-content-font-color,#FFF); padding:0.9375rem; margin-top:0.625rem; }

.modify-btn-scope { position:absolute; left:0; z-index:2; margin-top:0.5rem; display:flex; }
.modify-btn-scope .modify-btn { width:1.5rem; height:1.5rem; display:flex; align-items:center;
    justify-content:center; background:rgba(0,0,0,.5); border-radius:50%; margin-right:0.5rem; }

.chat .topTabbar { width:100%; height:2.8125rem; line-height:2.8125rem; display:flex; justify-content:space-between; }
.chat .topTabbar .header-center { width:55%; flex:1; display:flex; align-items:center;
    color:var(--primary-font-color,#FFF); }
.chat .topTabbar .header-center .header-role-img uni-image { border-radius:0.78125rem; width:1.5625rem; height:1.5625rem; }
.chat .topTabbar .header-roleName { margin:0 5px; font-size:0.9375rem; overflow:hidden;
    white-space:nowrap; text-overflow:ellipsis; }
.chat .topTabbar .header-icon-meun { display:flex; align-items:center; margin-right:12px; position:relative; }
.chat .topTabbar .header-icon-meun .header-meun { display:flex; align-items:center; margin-left:0.78125rem; }
.chat .topTabbar .header-icon-meun .header-meun uni-image { width:1.09375rem; height:1.09375rem; }

.chat .chat-bottom { z-index:999; width:100%; position:fixed; bottom:0; transition:.1s; }
.chat .chat-bottom .shortcut-bar-wrapper { position:relative; height:2.375rem;
    background:var(--background-color,#17181A); overflow:hidden; margin-bottom:-1px; }
.chat .chat-bottom .shortcut-bar { display:flex; align-items:center; height:2.375rem;
    padding:0 0.375rem; gap:0.3125rem; overflow-x:auto; white-space:nowrap; }
.chat .chat-bottom .shortcut-btn { flex-shrink:0; display:flex; align-items:center; justify-content:center;
    gap:0.1875rem; height:1.75rem; padding:0 0.5rem; background:var(--input-background-color,#1E1F24);
    border-radius:0.875rem; font-size:0.75rem; color:var(--shortcut-button-font-color,#8D949D); white-space:nowrap; }
.chat .chat-bottom .shortcut-bar-wrapper.theme-dark .shortcut-btn { background:#2c2e32; }
.chat .chat-bottom .shortcut-bar-wrapper.theme-light .shortcut-btn { background:#f1f4f9; }
.chat .chat-bottom .shortcut-btn .sb-icon { width:0.8125rem; height:0.8125rem; opacity:.9; }
.chat .chat-bottom .chat-bottom-wapper { background:var(--background-color,#17181A); }
.chat .chat-bottom .send-msg { display:flex; align-items:flex-end; padding:0.5rem 0.9375rem; width:100%; margin-bottom:-1px; }
.chat .chat-bottom .uni-textarea { width:100%; display:flex; align-items:flex-end; justify-content:space-between; }
.chat .chat-bottom .uni-textarea .chat-input-scope { width:100%; position:relative;
    background:var(--input-background-color,#1E1F24); border-radius:1.25rem;
    border:.0625rem solid var(--primary-color,#FF6D97); display:flex; align-items:center;
    justify-content:space-between; padding:0 0.5rem; }
.chat .chat-bottom .uni-textarea .chat-input-scope.has-toolbar { flex-direction:column;
    align-items:stretch; padding:0.3125rem 0.5rem; border-radius:0.75rem; }
.chat .chat-bottom .uni-textarea .chat-input-scope .chat-input-collapsed-placeholder {
    font-size:1rem; line-height:1.4; color:#999; }

.chat .mm-left-side-container  { position:fixed; top:50%; transform:translateY(-50%); display:flex;
    flex-direction:column; gap:0.375rem; z-index:9999; left:0; }
.chat .mm-right-side-container { 同上; right:0; }

.msg-option-scope { height:100%; width:100%; position:fixed; background-color:#000;
    z-index:99999; backdrop-filter:blur(5px); }

/* uni-app 全局重置（预览必须照抄，否则 p 的 margin 不同） */
* { margin:0; -webkit-tap-highlight-color:transparent; }
uni-view { display:block; }
html,body { user-select:none; width:100%; height:100%; touch-action:manipulation;
    font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased; }
body { overflow-x:hidden; font-size:16px; }
```

## 3. 主题变量（body inline style，JS 注入，暗色实测值，共 29 个）

```
--background-color:#17181A          --card-background-color:#282A2E
--chat-content-font-color:#FFFFFF   --primary-font-color:#FFFFFF
--primary-color:#FF6D97             --shortcut-button-font-color:#FFFFFF
--input-background-color:#33353B    --input-font-color:#FFFFFF
--mindtype-font-color:#FF6D97       --more-item-bg-color:#2C2E32
--share-item-bg-color:#2C2E32       --history-font-color:#FFFFFF
--history-remark-font-color:#C5C5C5 --model-help-content-font-color:#FFFFFF
--model-setting-power-bg-color:#0D0E0F  --model-setting-power-tips-color:#999999
--model-setting-remark-color:#C5C5C5    --modify-input-bg-color:#1E1F24
--vditor-bg-color:#0D0E0F           --msg-option-separator-color:#333333
--conversation-list-content-color:#C5C5C5  --cancel-btn-background-color:#FFB7CC
--item-background-color:#1E1F24     --item-tip-color:#FF6D97
--item-tip2-color:#FF6D97           --tip-font-color:#cccccc
--modify-item-bottom-color:#999999  --btn-bg-color:#33353B
--btn-border-color:transparent
```
注：`--primary-color` 亮色主题为 `#17AAFD`（从 `.theme-light` 规则反推）。主题切换靠改 body inline 变量，不是加 class。

## 4. rem 缩放律（实测两点拟合，误差 <0.001px）

`html { font-size }` 由 uni-app inline 设置：

```
rootFontSize = 16 * min(innerWidth, 375) / 375
```

实测两点：
- 主聊天页 iframe 宽 1280 → `font-size:16px`（封顶）
- 编辑页预览 iframe 宽 283 → `font-size:12.0747px`（= 16×283/375 = 12.074666…）

**预览要贴近真实必须复现这条**，否则所有 rem 尺寸全错。

## 5. 关键纠正：「换行空白条」的真因不是空 `<p>`

`references/platforms/mmd.md` §10.1 与 statusbar-radar.md 记的机制是"markdown 把换行补成空 `<p>`，空 `<p>` 带 margin 撑出空条"。**实测证伪**：

探针（在真实 `.content.left` 里 appendChild）：

| 注入内容 | 高度 | 说明 |
|---|---|---|
| `<div>l1</div>\n<div>l2</div>\n\n<div>l3</div>` | 102px | 3 子元素共 51px，多出 **51px** |
| 同上但 `white-space:normal` | 51px | 空条消失 |
| `<p>a</p>\n<p>b</p>` | 51px | 多出 17px |
| `<p>a</p><p>b</p>` | 34px | 无多余 |

`p:empty` 数量 = **0**。真因是 `.content { white-space: pre-line }` —— 标签之间的换行文本节点被 `pre-line` 保留为真实换行，每个换行撑出一整行行高（约 17px @rootFont 16px）。

**影响修法**：
- `p:empty{display:none}` / `br{display:none}` 这两条防御 **CSS 无效**（没有空 p，也没有 br）。
- 真正有效的两条：① 注入 HTML 标签间零换行（原结论正确，但理由要改）；② 在自己容器上 `white-space: normal`（新解法，原文档没有，实测 102px→51px）。

### 5b. 追加纠正：Shadow DOM 对空白条 **不免疫**

同样探针，改成 `attachShadow` 后在 shadow root 里注入带换行的 HTML：

| 载体 | 高度 | 子元素合计 | shadow 内 computed white-space |
|---|---|---|---|
| shadow root，标签间带换行 | **102px** | 51px | **pre-line** |
| light DOM + `white-space:normal` | 51px | 51px | normal |

`white-space` 是**继承属性**，会穿过 shadow 边界从 host 继承下来（shadow 隔离的是**选择器**，不隔离继承属性）。所以 mmd.md §6b「Shadow DOM 方案对 markdown 陷阱免疫，换行空白条补丁不再需要」这一条 **是错的** —— 走 Shadow DOM 仍必须显式在 shadow 内写 `:host{white-space:normal}` 或 `*{white-space:normal}`，否则一样撑空条。

（Shadow 对**类名冲突**和**外部样式表污染**的隔离仍然成立，那部分结论不变。）

## 5c. 弹窗体系（实机逐个点开抓取）

全局美化会打到这些面板，必须仿真。**通用外壳三层**：

```
uni-view.u-popup                      ← 恒 height:0（别用它做可见性判据！）
├ uni-view.u-transition.u-fade-*           遮罩层，无 .u-popup__content
│   └ .u-overlay { position:fixed; inset:0; background:rgba(0,0,0,.7) }
└ uni-view.u-transition.u-slide-up-*       内容层 position:fixed; bottom:0; left:0
  └ uni-view.u-popup__content              ← 圆角/底色在这里（多为内联 style）
    └ uni-view.<各面板自己的 scope 类>
    └ uni-view.u-safe-bottom.u-safe-area-inset-bottom
```

框架基线（uview）：`.u-popup__content{background-color:#fff;position:relative}` ——**基线是白色**，深色是各面板自己的 scope 或内联 style 覆盖的。`--round-bottom` = `border-radius:10px 10px 0 0`；`--round-center` = `10px`。可选关闭钮 `.u-popup__content__close--top-right{top:15px;right:15px}`。

### 逐个面板实测

| 入口 | 形态 | scope 根类 | z-index | content 内联 style | 备注 |
|---|---|---|---|---|---|
| 快捷条·模型设置 | slide-up 半屏 | `.model-setting-scope.theme-dark` | **10075** | `flex:1;border-top-left/right-radius:10px` | scope 自带 `background-color:var(--background-color)`、`padding:0 1rem 1rem`、`height:34.375rem` |
| 快捷条·对话设置 | slide-up 69vh | `.conv-style-modal` | 10075 | `flex:1;background-color:#17181A` | scope 本身 `background:transparent`，底色由 content 内联给；无圆角 |
| 快捷条·选择指令 | **不是弹窗** | — | — | — | 原地把 `.shortcut-bar` 加 `.hidden`、显示 `.instruction-bar`（26 个 `.instruction-chip`），高度仍 2.375rem |
| 快捷条·总结剧情 | slide-up 半屏 | `.summary-sheet.theme-dark` | **1000000000** | `flex:1;border-top-*-radius:10px` | z-index 比别的高 5 个数量级；`height:34.375rem;max-height:84vh` |
| 快捷条·用户人设 | slide-up 69vh | `.role-profile-modal` | 10075 | `flex:1`（无底色） | 内部 `.header-scope`(取消/标题/保存) + `.role-setting`；**用 `--lo*` 变量族** |
| 快捷条·新的聊天 | 未点（破坏性） | — | — | — | 会重置对话，只做 UI 仿真 |
| 顶栏·评论(第1) | **路由跳转** | — | — | — | 跳 `#/pages/role/index`，不是弹窗 |
| 顶栏·分享(第2) | slide-up 矮条 | `.share-popup` | 10075 | `flex:1` | `.share-title`/`.share-sub-title`/`.gen-link-btn`；实测 bg `#282A2E`(=`--card-background-color`)、padding 15.4px、h 167px；用框架自带 `.u-popup__content__close--top-right` |
| 顶栏·收藏(第3) | 无 UI | — | — | — | 静默 toggle，无弹窗无 toast |
| 顶栏·刷新(第4) | 无弹窗 | — | — | — | 直接重新生成 |
| 输入框右·`+` | **不是弹窗** | `.more-scope` | — | — | 在 `.chat-bottom` 内展开，4 列 `.item`×11（重置聊天/导出聊天/新的聊天/编辑角色/更换背景/自定义指令/用户人设/设定补充/对话设置/剧情总结/游玩教程），底栏高度 105px→**317px** |
| 输入框左·AI帮聊💡 | 居中 dialog（未点，按既有 DOM/CSS 仿真） | `.alert-scope` | — | — | `u-fade-zoom-*` 动画；`width:18.75rem;padding:0 1.875rem`；`.alert-title`/`.alert-content`/`.alert-checkbox`/`.alert-bottom(-double)`；按钮 `.ok-btn`(主题色)/`.cancel-btn` |

### 🚨 `--lo*` 变量族：18 个「引用但从未定义」

`.role-profile-modal` / `.role-setting` 这套用户人设面板走**另一套变量名**：`--loBackground-color`、`--loPrimary-color`、`--loPrimary-font-color`、`--loCard-background-color`、`--loInput-background-color`、`--lo-subtitle-color`、`--lo-disabled-*` 等共 **18 个**。

实测在 `body` 上解析这 18 个**全部为空**——页面从未定义它们，永远走 `var(--loX, 字面量)` 里的 fallback。含义：

- 作者改 `--loBackground-color` **不会**改变这些面板的颜色（变量没被定义，改了也没人读；fallback 恒生效）。
- 要给用户人设面板换肤，只能**直接选类名**（`.role-setting`、`.role-setting .card` 等）。
- 与 §3 那 29 个 `--*`（真实定义在 body 内联 style）是两套独立体系，别混。

## 5d. 输入框：两个节点 × 三种状态（关系到文字注入/发送/美化）

点输入框展开、点外面收回，**不是同一个节点在变高**，而是两个 textarea 互相让位。

### 状态类（同时挂在 `.uni-textarea` 与 `.chat-input-scope` 上）

| 状态 | class | 触发 |
|---|---|---|
| 折叠（基线） | `chat-input-scope has-toolbar` | 初始 / 主 textarea **失焦** |
| 展开 | `+ is-expanded` | 点 `.chat-input-collapsed-display` |
| 多行 | `+ is-multiline` | 渲染**高度超过一行**（换行 or 长文本折行，**折叠态也会加**） |
| ？ | `+ is-via` | CSS 里有，两次实测均未触发出来，用途待查 |

> **2026-08-29 实测修订（三条，均已在真机 `roleId=283787` 验证）**：
>
> **① 收回是 `blur` 驱动，不是「点外面」驱动。** 真值源是 Vue 的 `chatInputFocused`。对 `#msglistview` / `.chat-body` / `.chat-scope-box` / `uni-page-body` 派 `mousedown+mouseup+click` 合成事件，四个目标**全部收不回**（class 恒 `is-expanded`）；对主 textarea 派一个 `blur` 事件，**立刻**收回（`focused:true→false`，高度 125px→53px）。真人点外面能收回，是因为浏览器把焦点挪走**顺带触发了 blur**，不是页面装了 outside-click 监听。
>
> 对卡的意义：想程序化收回输入框，派 `blur`（或调 `.blur()`）；**别去模拟点击页面空白**，合成 click 不移动焦点，等于没点。
>
> **② `is-multiline` 是高度判据，不是「含换行」判据。** 实测：`'短'`（1 字）→ 无 `is-multiline`（86px）；`'A\nB'` → 有（92px）；**`'长'×120`（零换行）→ 同样有**（92px）。所以它跟着 auto-height 传感器量出来的行数走。
>
> **③ 清空后 `is-multiline` 会卡住（auto-height 传感器不复位）。** 从长文本**直接**置空（`value=''` + `input`），class 残留 `is-multiline`、高度卡在 159px 不回落。修法：中间垫一个短值再清空 —— `value='.'`+input → 等一拍 → `value=''`+input，实测 159px→86px→53px 正常回落。卡片里做"清空输入框"功能要照这个两步走。

### 两个 textarea，**class 完全相同**

```
.chat-input-scope.has-toolbar
├ uni-image.btn-icon.chat-send-proxy      ← 恒 display:none;0×0;absolute（见下）
├ uni-view.chat-input-toolbar             ← 仅展开态可见：粘贴 / 清空
├ uni-textarea.chatMsgTextarea            ← 【主】仅展开态可见
│   └ textarea.uni-textarea-textarea      ← 索引 [0]
├ uni-view.chat-input-collapsed-row       ← 仅折叠态可见
│ ├ uni-view > .mind-type                    电量数字（45）
│ ├ uni-view.chat-input-collapsed-display
│ │ └ uni-textarea.chatMsgTextarea.chat-input-collapsed-preview   ← 【预览】仅折叠态可见
│ │     └ textarea.uni-textarea-textarea  ← 索引 [1]
│ └ uni-view > uni-image.btn-icon            折叠态的发送按钮
└ uni-view.chat-input-bottom-row          ← 仅展开态可见
  ├ uni-view > .mind-type
  └ uni-view > uni-image.btn-icon            展开态的发送按钮
```

**DOM 顺序恒定**（[0] 主、[1] 预览），变的只是**谁可见**。所以：

- `document.querySelector('.uni-textarea-textarea')` **永远命中 [0] 主节点**——折叠态下它是**不可见**的（height:0）。
- `.chatMsgTextarea` 这个 class **两个都有**，`querySelector` 同样只拿到主的。

### ✅ 文字注入：写哪个都行（实测双向同步）

| 写入目标 | 立刻 | ~500ms 后 | 结论 |
|---|---|---|---|
| [0] 主（折叠态下不可见） | 只有 [0] 有值，界面无变化 | [1] 同步、折叠预览显示出文字 | ✅ 生效 |
| [1] 预览（可见） | 只有 [1] 有值 | [0] 同步 | ✅ 生效 |

机制：**Vue 的 model 是唯一真值源**。`el.value = 文本` + `dispatchEvent(new Event('input',{bubbles:true}))` 会被 Vue 采纳，再由它同步到另一个节点。所以现有雷达/状态栏引擎用的 `.uni-textarea-textarea` 选择器**是对的**，不必改。

#### Vue model 真值字段（2026-08-29 实测定位，可直接读来自检）

聊天页组件（从 `#chat-input-scope` 沿 `__vueParentComponent.parent` 往上找，`data` 有 126 个 key 的那一层）上三个字段：

| 字段 | 含义 |
|---|---|
| `chatMsg` | 输入框正文，**发送时真正发出去的就是它** |
| `chatMsgTemp` | 与 `chatMsg` 同步的副本，实测两者恒等 |
| `chatInputFocused` | 焦点态，**`is-expanded` 就是跟着它走的** |

```js
// 调试用（浏览器控制台，chatIframe 上下文）：拿到 model 自检注入有没有真进 Vue
let c = document.getElementById('chat-input-scope').__vueParentComponent;
while (c && c.data?.chatMsg === undefined) c = c.parent;
c.data.chatMsg;            // ← 发送时会发出去的真值
c.data.chatInputFocused;   // ← 展开/收回的真值源
```

> 仅调试用。卡片正式代码别依赖这条链路（Vue 内部结构随平台构建变动），注入照旧走 `.value` + `input` 事件。

#### ⚠️ 修订：「必须派 input 事件」的真实理由是**时序**，不是「Vue 不知情」

2026-08-29 A/B 实测：

| 手法 | model 何时更新 |
|---|---|
| `value=x` + 派 `input` | **同一 tick 立刻**（同步读 `chatMsg` 已是新值） |
| `value=x`，**不派任何事件** | **约 100ms 后也会被采纳**（实测 101ms，采样 26/51/76ms 时仍是旧值） |

所以 uni-app 侧存在一条**约 100ms 的轮询/传感器兜底**，裸赋值最终也会进 model。但仍然**必须派 `input`**，理由是时序而非可见性：

- 不派事件时那 ~100ms 是**竞态窗口**。窗口内再写第二个值，两次写会互相盖——本次调试就自己踩了一次：前一次未派事件的写在窗口内被轮询采纳，把后面的清空操作覆盖回去，现场表现成"输入框清不掉"，误判为平台 bug。
- 派了 `input` 就是同步落定，没有窗口，行为确定。

**纪律**：每次写 `.value` 后立刻派 `input`，一次写一个值，不要在同一批代码里连续裸赋值两次。

> 同时修订原第 1 条「有一拍延迟 ≤600ms、注入后立刻读另一节点会读到空」：那是**不派事件**时的表现。派了 `input` 后，[0]/[1] 与 model 三者同 tick 一致，立刻读回是准的。

#### 长文本不受 `maxlength=140` 限制

折叠预览节点 `maxlength=140`、主节点 `maxlength=2000`，但 `maxlength` **只约束真人键入，不截断程序化赋值**。实测注入 300 字：model / [0] / [1] 三者长度都是 300，预览节点照样收下（超出部分靠 `max-height:8.75rem` + 滚动显示）。

### ⚠️ 发送按钮会换位置

| 状态 | 可见发送按钮所在 |
|---|---|
| 折叠 | `.chat-input-collapsed-row > uni-view:last-child .btn-icon` |
| 展开 | `.chat-input-bottom-row .btn-icon` |

写死单条路径的卡，换个状态就点不到。另有 **`.chat-send-proxy`**：`uni-image.btn-icon.chat-send-proxy`，内联 `display:none;width:0;height:0;position:absolute`，带发送图标，**两种状态下都在**。

**状态无关的稳妥写法（2026-08-29 实测）**：`.chat-input-scope` 内一共 3 个 `.btn-icon`（proxy + 折叠态发送 + 展开态发送），实测**任一状态下"可见且非 proxy"的恰好只有 1 个**（宽 20px = 1.25rem，另两个都是 0×0）。所以按可见性筛，不用判断状态：

```js
var scope = document.getElementById('chat-input-scope');
var btn = [].slice.call(scope.querySelectorAll('.btn-icon:not(.chat-send-proxy)'))
             .filter(function(b){ return b.offsetParent !== null })[0];
// btn 即当前状态下那个真正可见的发送按钮
```

`#chat-input-scope` 这个 **id 真机存在**（不是我们加的），可以直接当锚点用。

> ⚠️ **`.chat-send-proxy` 的用途属推断，未验证**：名字（proxy）+ 恒存在 + 恒隐藏 + 带发送图标，看着就是给程序化发送预留的钩子，但我**没有点它**——点一次就真发消息、真扣电量（当前模型 45/条）。要确认得实机点一次，需要你允许。

**发送钮观感（2026-08-29 实测）**：可见发送钮是 `ico_send_dark.png`（**灰色纸飞机**），`.btn-icon` 容器 **background 恒 `rgba(0,0,0,0)`（透明底）**，图标是内部 `div` 的 `background-image`。A/B 实测注入 `测试文字` 前后：`sendBg` 恒透明、`divBgImg` 恒 `ico_send_dark.png`——**发送钮不随"有无文字"变色/变粉、无激活态**。全局美化改输入框时它不吃语义色变量（是 PNG）。做预览别画成粉色实心圆。

### 美化影响

- `.chat-input-toolbar`（粘贴/清空两个 `.chat-input-tool-btn`）**只在展开态存在**，全局美化改输入框必须**两个状态都看过**，否则展开后才发现工具条错色。
- `.chat-input-collapsed-text` / `.chat-input-collapsed-placeholder` 这两个类**CSS 里有定义，DOM 里查不到**（实测均为 null）——是另一条未启用的渲染路径（可能旧版或 `is-via` 态才用）。**别照它们写选择器**。
- 折叠态可见文字由 `.chat-input-collapsed-preview` 这个 **textarea** 渲染，不是普通文本节点；想改折叠态字色要落到它上面。

### `+` 更多按钮 + 底栏面板（2026-08-29 实测）

- **`+` 是 `.more-options-scope`**，`.chat-input-scope` 的**右侧兄弟**（不在输入框内）：`margin-left:6px`、`align-items:center`、两态 `padding-bottom` 15.5px(折叠)/13.5px(展开/多行) 把图标压到输入框视觉中线；容器 25×41，图标 `.btn-icon` 25×25。
- 观感：`+` 图标是 **`ico_more_dark.png` = 一个灰色描边圆圈里一个加号**；点开后换成 `ico_more_called_dark.png`（**圈里变减号**）——是**换 PNG**，不是 CSS 画的符号。做预览要复刻"灰圈 + ±字形"两态，别画成飘边的裸加号。
- **底栏 `.more-scope`**：点 `+` 才出现（**v-if 节点，关态 DOM 不存在**，不是 `display:none`——拿 `querySelector('.more-scope')` 判开合会得反结论，判开合看 `+` 图标态）。它在 `.chat-bottom-wapper` 里排在 `.send-msg`**之后** → 满宽面板在输入行**下方**撑开、把输入行**顶上去**（输入框 y 660→343，面板自身 317px）。`+` 跟输入行一起上移，仍在右侧。
- 4 列 `.item`×11：`.item-icon` 高 64.5px、圆角 20px、**底色 `var(--more-item-bg-color,#2C2E32)`**；`.item-title` 13px、**字色 `var(--primary-font-color,#FFFFFF)`**、mt7。**这两个变量吃全局美化**（实测改 `--more-item-bg-color`/`--primary-font-color`，底栏格子底色与标题字色同步变）——底栏是白名单浮层，属官方手册「底栏和白名单弹窗」变量的作用域。

## 5e. 开场白选择区 + 消息圆钮 + 长按菜单（2026-08-29 实测，发消息真机验证）

### 消息列表两态顺序（实测 DOM 序，发消息真机验证）
真机 `#msglistview` 消息顺序，**两态**：
- **初始态**：`描述气泡(.item.Ai.avatar-body)` → `first_mes(.item.Ai，角色第一句话)` → `.prologue-scope(开场白选择)`
- **发送后**（开场白填充发送 或 打字发送）：`描述气泡` → `first_mes` → `用户消息(.item.self)` → `AI回复(.item.Ai)`；**开场白消失**
- 回溯消息 → 回到初始态（开场白重现）。
- 描述气泡（卡片简介）与 first_mes 一直在顶部，两态都在；变的只是其后是开场白还是"用户+AI"。
- 预览用 `.chat[data-chat-state=initial|sent]` 切两态互斥（DOM 序 描述→first_mes→开场白→用户→AI，隐藏项塌陷，视觉序自然对），默认 `sent`（被测组件落在 AI 回复气泡，作者一开即见）。

### 开场白选择区 `.prologue-scope`
- 位置：在 `#msglistview` 消息列表里，排在 AI 第一条消息（first_mes）**之后**，不是独立浮层。结构 `.prologue-title>span`（"你可以选择开场"，**固定黑底白字** `rgba(0,0,0,.5)`）+ `.prologue-content`（开场白正文选项）。
- **吃全局美化**（用户强调的核心）：`.prologue-content` 底色 `var(--background-color,#17181A)` + 字色 `var(--chat-content-font-color,#FFFFFF)`，`opacity:.9`。实测改这两个变量 → 开场白选项底色/字色同步变（做美化必须覆盖到这里）。
- **点击填入输入框**：点 `.prologue-content` → 该开场白正文写进输入框（`.uni-textarea-textarea` + 派 input）。
- **状态流转**：发送一条消息后开场白**消失**；**回溯**消息后开场白**重现**（实测发消息 `prologueAfter:false` 确认消失）。

### 消息操作圆钮 `.modify-btn-scope`
- `position:absolute`、`z-index:2`、`margin-top:8px`；内含 `.modify-btn`（24×24、`rgba(0,0,0,.5)`、`border-radius:50%`、gap 8px、图标 inline base64 PNG）。
- **AI 消息 3 钮**：刷新(重新生成) + 编辑 + 分享，靠气泡**左下**（scope `margin-right:3.125rem`）。
- **用户消息 2 钮**：编辑 + 分享（**无刷新**，用户消息不能重生成），靠气泡**右下**（`justify-content:flex-end`）。编辑/分享图标与 AI 后两钮**同款**。
- **first_mes（角色卡第一句话）**：`.modify-btn-scope` 存在但 3 个 `.modify-btn` 全 `visible:false`、0×0 → **无可见圆钮**（这是"第一句话没有三个圆钮"的真相：不是没 scope，是按钮塌陷隐藏）。

### 长按菜单 `.msg-option-scope`
- **全局单例**（不是 per-message），`fixed`、`z-index:99999`、`bg rgba(0,0,0,.7)`、`backdrop-filter:blur`、默认 `display:none`，长按消息 → 弹出。内含 `.msg-content-box`（被长按消息正文预览，底色 `var(--modify-input-bg-color,#1E1F24)`）+ `.msg-options-box`（选项列表，同底色）。
- **选项按消息类型算**：常规 AI/用户消息 **4 项**——复制(仅复制文本) / 删除(从上下文删) / 回溯(删这条及下方所有,含AI和用户) / 开启新的故事(保留这条及上文,进新聊天)，图标 `ico_copy/delete/return/fenzhi_dark.png`。**first_mes（第一句话）仅"复制"**（其余项隐藏）。
- **吃全局美化**：选项文字 `var(--primary-font-color,#FFFFFF)`、分隔线 `var(--msg-option-separator-color,#333333)`、框底 `--modify-input-bg-color`。
- ⚠️ 合成 touch 事件**触发不了** Vue 的长按计时器（菜单能靠 handler 开但按类型过滤逻辑不跑，落到默认"仅复制"态）——真机勘查用真实长按(touchstart 保持不放)验证菜单确实 `display:block`。

### 快捷栏按钮 `.shortcut-btn`（输入框上方那栏，2026-08-29 实测）
6 个按钮：模型设置 / 对话设置 / 选择指令 / 总结剧情 / 新的聊天 / 用户人设。
- **吃全局美化**（用户强调）：字色 `var(--shortcut-button-font-color,#8D949D)`、wrapper 底 `.shortcut-bar-wrapper` 用 `var(--background-color,#17181A)`。**但按钮底色在深色态是硬编码**：`.shortcut-bar-wrapper.theme-dark .shortcut-btn{background:#2c2e32}`（特异性高于基础规则的 `var(--input-background-color)`，浅色态则 `#f1f4f9`）——即深浅色下按钮底走固定值，字色跟美化变量。做美化改字色有效、想改按钮底色得覆盖 theme-dark/light 那条。
- **点击动作**（实测 Vue 方法）：模型设置→`.model-setting-scope` 面板、对话设置→`openConvSetting` 面板、总结剧情→summary 面板、用户人设→role 面板、**新的聊天→`onShortcutNewChat`（独立确认弹窗，保存当前对话进历史后开新聊天，`instrHidden` 不变=不切指令栏）**；**仅「选择指令」原地替换快捷条为指令栏**（`.instruction-bar`，不是弹窗）。
- 🚨 易错点：`新的聊天` 与 `选择指令` 视觉都在快捷栏，但前者开弹窗、后者切指令栏——别把 `新的聊天` 也当指令栏处理。

## 6. 全景预览升级要点（据以上契约）

必须复现的：
1. iframe 内 `body` 挂 29 个主题变量 inline style。
2. uni-app 元素名（`uni-view`/`uni-scroll-view`/`uni-image`/`uni-text`）+ `uni-view{display:block}` 重置。
3. `.chat > .chat-scope-box(fixed,背景图) > .scroll-view(margin-top:2.8125rem; height:calc(100% - 3.2rem)) > .uni-scroll-view-content > .chat-body#msglistview`。
4. `.content { white-space:pre-line; opacity:.9; background:var(--background-color) }` —— 少了 `pre-line` 就查不出空白条；少了 `opacity:.9` 颜色会偏。
5. 圆角双轨：`.item .left` 是 `1rem 1rem 1rem 0`，但 `.avatar-body .touch-scope .left` 覆盖成 `0.5rem`（首条描述气泡）。
6. `rootFontSize = 16*min(w,375)/375`。
7. `.touch-scope{max-width:94%}`，`.avatar-body .touch-scope{max-width:100%}`。
8. 表格样式（`display:block; th/td padding 6px 13px; border 1px #dfe2e5; white-space:nowrap`）—— 状态栏用表格时预览必须一致。
9. 官方侧边挂载点 `.mm-left-side-container` / `.mm-right-side-container`（悬浮组件靶位）。
10. 长按菜单 `.msg-option-scope`（z-index 99999）与 `.modify-btn-scope`（z-index 2）—— 检查组件 z-index 是否被压。
