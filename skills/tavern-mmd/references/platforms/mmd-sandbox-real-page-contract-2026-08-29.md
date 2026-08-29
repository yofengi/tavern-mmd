# MMD 沙盒模式真实页 DOM/CSS 契约（实测抓取 2026-08-29）

宿主页：`https://h5.aitchat.org/#/pages/chat/host?roleId=64304`
卡片 iframe：`https://c64304.sbx.aitchat.org/`（**独立子域、跨源**，`sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-downloads"`）
编辑页：`https://h5.aitchat.org/#/pages/role/create?id=64304`
抓取手段：Playwright 直接在 iframe 内 evaluate，读 `styleSheets`（CSSOM）+ `getComputedStyle`。

> 与旧聊天页（`/mmd`，`www.sexyai.ai`）**域名、路由、DOM、变量体系全部不同**，两套不可混用。

## 1. 宿主与容器

| 项 | 实测 |
|---|---|
| 宿主 iframe | `iframe#sbx.chat-iframe`，`style="pointer-events:auto"` |
| iframe sandbox 属性 | `allow-scripts allow-same-origin allow-forms allow-modals allow-downloads` |
| 卡片页 URL | `https://c<roleId>.sbx.aitchat.org/`（每角色独立子域） |
| `window===window.top` | **false**（跨源嵌套） |
| iframe 内 `html` | `lang="zh-CN"`，**无** inline style、**无** class |
| iframe 内 `body` | 无属性 |
| 根挂载 | `div#app[data-v-app]` > `div[data-chat=root]` |
| 根 root font-size | 16px（**不做 rem 缩放**，尺寸走 `--rpx`，见 §4） |

## 2. 层级骨架（实测，全部靠 `data-*` 钩子）

```
div#app[data-v-app]
└ div[data-chat=root][data-theme=dark][data-composer=visible]
      inline style: --chat-viewport-height:900px; background-image:url(角色图);
                    background-position:center center; background-size:auto 100%; background-repeat:no-repeat
  ├ header[data-chat=header]
  │ ├ button[data-chat=header-back] > img
  │ ├ div[data-chat=header-title] > img + span（角色名）
  │ ├ div[data-chat=header-actions]
  │ │ ├ button.header-comments[data-action=comments] > img
  │ │ ├ button[data-action=share] > img
  │ │ ├ button[data-action=favorite] > img
  │ │ └ button[data-action=sync] > img
  │ └ div[data-slot=header-extra]          ← 作者插槽（:empty 时 display:none）
  ├ div[data-slot=statusbar]               ← 功能栏落点（卡片 statusbar 字段）
  ├ main[data-chat=messages]
  │ └ div[data-chat=list]
  │   ├ div[data-probe=role-intro][data-from=ai]
  │   │   └ div[data-probe=role-intro-body]      ← 角色描述气泡（独立于消息体系）
  │   ├ div[data-chat=list-spacer]
  │   ├ div[data-chat=message-frame]
  │   │   └ article[data-chat=message][data-from=ai][data-state=done]
  │   │       └ （内部 message-body / message-actions）
  │   ├ div[data-chat=list-spacer]
  │   └ div[data-probe=prologue]
  │       ├ p[data-probe=prologue-title] > span
  │       └ button[data-probe=prologue-chip] × N
  ├ div[data-slot=left]                    ← 作者插槽
  ├ div[data-slot=right]                   ← 作者插槽
  ├ div[data-chat=author-stage][data-stage=closed]   ← 舞台，三态 closed/content/full
  └ footer[data-chat=composer]
    ├ div[data-slot=toolbar]               ← 作者插槽
    ├ div.composer-shortcut-wrap
    │ ├ div[data-chat=shortcut]            6×button[data-action=model|style|instructions|summary|conversations|persona]
    │ └ div.hidden[data-chat=instruction-bar]
    │     ├ button[data-chat=instruction-back]
    │     └ div.instruction-scroll > button[data-chat=instruction-chip] × N
    └ div.composer-row
      ├ div.assistant-anchor > button[data-chat=assistant][data-action=assistant]
      ├ div.composer-field
      │ ├ textarea[data-chat=input]
      │ ├ button[data-chat=model-chip][data-action=model]
      │ └ button[data-chat=send]
      └ button[data-action=more] > img
```

**代码里已有但真机名字不同 / 遗漏的钩子**（要对齐）：
- 舞台是 `data-chat="author-stage"`（带 `data-stage` 三态），不是 `stage`。
- 快捷条是 `data-chat="shortcut"`；指令栏 `data-chat="instruction-bar"` + `instruction-back` + `instruction-chip`。
- 输入区还有 `data-chat="assistant"`、`assistant-tip`、`model-chip`、`snack`。
- 消息区外还有 `data-probe=role-intro / role-intro-body / prologue / prologue-title / prologue-chip / history-loading / snackbar`，以及 `data-chat="list-spacer"`。
- 弹窗/浮层族：`message-menu`、`alert` + `toast` + `alert-ok`、`more-panel`、`share-bar`、`share-pick-bar`、`share-pick-toggle`、`share-pick-icon`、`share-pick-cancel`、`share-pick-switch`、`share-shot-*`、`summary-bubble`。

## 2b. 🚨 判决性实验：官方手册「白名单弹窗」到底指什么

官方《角色卡制作手册》（36 页版）第 1 章说底栏与「会话列表 / 模型 / 角色资料这类**白名单**弹窗」吃 `--chat-composer-* / --chat-input-* / --chat-modal-*` 这 18 个变量。读快了容易理解成"这些弹窗在沙盒内、卡片能换肤"。**做了判决性实验，结论是三层，不是两层。**

方法：在 iframe 内按手册写法注入一组刺眼色
`[data-chat="root"]{--chat-modal-bg:#00ff00;--chat-modal-surface:#ff00ff;--chat-modal-text:#ffff00;--chat-modal-accent:#00ffff;--chat-more-item-bg:#ff8800;--chat-shortcut-bg:#0088ff}`
再逐个打开面板量 computed 值。

| 目标 | 注入后实测 | 判定 |
|---|---|---|
| 宿主「模型设置」`.model-setting-scope` | 仍 `rgb(23,24,26)`；`--chat-modal-bg` 在宿主 scope 上**解析为空** | ❌ **不吃**，卡片 CSS 改不动 |
| iframe 内 `[data-chat=more-panel]` 壳 | `rgb(0,255,0)` | ✅ 吃 `--chat-modal-bg` |
| `[data-chat=more-panel] button > span` | `rgb(255,136,0)` | ✅ 吃 `--chat-more-item-bg` |
| `[data-chat=shortcut] > button` | `rgb(0,136,255)` | ✅ 吃 `--chat-shortcut-bg` |
| `[data-chat=instruction-chip]` | `rgb(0,136,255)` | ✅ 吃 `--chat-shortcut-bg` |
| `[data-chat=instruction-back]` | `rgb(0,255,255)` | ✅ 吃 `--chat-modal-accent` |

**结论（手册与实测不矛盾，是措辞容易误读）**：

1. 手册讲的是**变量归属**（这批 UI 吃 modal 族、不吃气泡族），**不是渲染位置**。手册自己在变量表里把 `--chat-modal-bg` 写成「更多面板壳、**宿主**列表弹窗底」，第 4 章也明说「改 `--chat-bg` 不会带动底栏和**宿主弹窗**」—— 它用的就是"宿主"这个词。
2. **iframe 内**那批（more-panel / shortcut / instruction-* / assistant tip / message-menu / alert / snack / share-* / summary-bubble）：手册那 18 个变量**完全有效**，作者能改、也会改歪 → 预览必须完整仿真。
3. **宿主页**那五个（模型设置 / 对话设置 / 总结剧情 / 用户人设 / 分享）：是宿主 uni-app 组件，吃宿主 `body` 上的 51 个 `--background-color` / `--lo*` 变量；`--chat-modal-*` 在宿主侧**根本没定义**。视觉上与 iframe 一致是因为**平台两边各自设了同样的深色值**，不是作者 CSS 穿过去了。所以"改 modal 族顺带给宿主弹窗换肤"**做不到**。

**对预览的含义不变但依据更硬**：iframe 内那批做可开关完整仿真；宿主那五个只画层级/遮挡轮廓 + 标注「平台侧、卡片改不动」。

### 2c. 令牌计数与手册对齐

手册列「可改色」10 个 + 「底栏和白名单弹窗」18 个 = 28。实测 theme 块内 29 个。差异已核清：

- `--chat-viewport-height` 手册算在那 10 个里，但它**不在 theme 块**（是平台 JS 写在 root 内联 style），所以 theme 块内实为 27 个手册项。
- 手册**未列**但 theme 块内确实定义的 2 个：**`--chat-more-item-bg`**、**`--chat-share-pick-bg`**。二者都有真实消费者（前者=更多项方块底，实验已验证；后者=分享选中态气泡底 `[data-chat=message-frame][data-share-picked]`）。
- 27 + 2 = **29**，与实测吻合。作者写这 2 个是**真机可用**的，预览必须一并注入。

## 3. 设计令牌：实测 **29 个**（不是 14），两套主题都有真值

定义在 `[data-theme="dark"]` / `[data-theme="light"]` 上（**没有 `:root` 定义**）。`--chat-viewport-height` 与 `--rpx` 另算（见 §4）。

### 深色（实测原文）

```
--chat-bg:#17181a           --chat-surface:#1e1f24        --chat-text:#fff
--chat-text-muted:#c5c5c5   --chat-border:#333            --chat-accent:#ff6d97
--chat-bubble-user-bg:var(--chat-bg)   --chat-bubble-ai-bg:var(--chat-bg)
--chat-bubble-text:var(--chat-text)    --chat-share-pick-bg:#2c2e32
--chat-input-bg:#1e1f24     --chat-input-text:#fff        --chat-shortcut-text:#fff
--chat-more-item-bg:var(--chat-modal-surface)
--chat-composer-bg:#17181a  --chat-composer-text:#fff     --chat-shortcut-bg:#2c2e32
--chat-input-placeholder:#c5c5c5       --chat-input-border:#ff6d97
--chat-modal-bg:#17181a     --chat-modal-surface:#2c2e32  --chat-modal-text:#fff
--chat-modal-muted:#c5c5c5  --chat-modal-accent:#ff6d97
--chat-modal-input-bg:#1e1f24          --chat-modal-input-text:#fff
--chat-modal-cancel-bg:#ffb7cc         --chat-modal-btn-bg:#33353b
--chat-modal-btn-border:transparent
```

### 浅色（实测原文，**不再是类推**）

```
--chat-bg:#fff              --chat-surface:#f5f8fc        --chat-text:#212226
--chat-text-muted:#8d949d   --chat-border:#e5e7eb         --chat-accent:#17aafd
--chat-bubble-user-bg:var(--chat-bg)   --chat-bubble-ai-bg:var(--chat-bg)
--chat-bubble-text:var(--chat-text)    --chat-share-pick-bg:#e6e6e6
--chat-input-bg:#f6f8fc     --chat-input-text:#333        --chat-shortcut-text:#8d949d
--chat-more-item-bg:var(--chat-modal-surface)
--chat-composer-bg:#fff     --chat-composer-text:#212226  --chat-shortcut-bg:#f1f4f9
--chat-input-placeholder:#8d949d       --chat-input-border:#17aafd
--chat-modal-bg:#fff        --chat-modal-surface:#f5f8fc  --chat-modal-text:#212226
--chat-modal-muted:#8d949d  --chat-modal-accent:#17aafd
--chat-modal-input-bg:#f6f8fc          --chat-modal-input-text:#212226
--chat-modal-cancel-bg:#f5f8fc         --chat-modal-btn-bg:#fff
--chat-modal-btn-border:#efefef
```

**关键点**：
- 气泡三色是 `var(--chat-bg)` / `var(--chat-text)` 的**别名**，不是独立取值 → 两套主题下气泡都与页面背景同色，改 `--chat-bg` 气泡跟着变。
- `--chat-more-item-bg` 是 `var(--chat-modal-surface)` 的别名。
- **`--chat-modal-*` 共 9 个**（bg/surface/text/muted/accent/input-bg/input-text/cancel-bg/btn-bg/btn-border）—— 弹窗全靠这一族，代码里 14 个令牌**一个都没包含它们**。

## 4. `--rpx` 尺寸基准（实测两点 + 断点原文）

```css
[data-chat="root"] { --rpx: calc(100vw / 750); width:100%; max-width:100%;
  height: var(--chat-viewport-height, 100vh);
  background-color: var(--chat-bg); color: var(--chat-text);
  display:flex; flex-direction:column; margin:0; position:relative; overflow-x:hidden }
@media (min-width: 961px) { [data-chat="root"] { --rpx: calc(375px / 750) } }
```

实测：视口 400px → `--rpx: calc(100vw/750)`，`750*--rpx` = 400px；视口 1280px → `--rpx: calc(375px/750)`，`750*--rpx` = **375px**（桌面封顶）。

`--chat-viewport-height` 由平台 JS 写在 root **内联 style**（实测 900px / 860px，随视口高变化），不是样式表变量。

## 5. 关键结构 CSS（实测原文，去重节选）

```css
[data-chat="messages"] { flex:1 1 0; min-width:0; max-width:100%; overflow:hidden auto; overflow-anchor:none }
[data-chat="message-frame"] { display:flow-root }
[data-chat="message"] { box-sizing:border-box; width:100%; min-width:0; max-width:100%;
  padding: calc(23 * var(--rpx)) calc(30 * var(--rpx)); display:flex; flex-direction:column }
[data-chat="message"][data-from="user"] { align-items:flex-end }
[data-chat="message"][data-from="ai"]   { align-items:flex-start }
[data-chat="message-name"], [data-chat="message-avatar"] { width:0; height:0; overflow:hidden }  /* 平台隐藏 */
[data-chat="message-body"] { width:fit-content; max-width:90%; padding: calc(24 * var(--rpx));
  box-shadow: 0 calc(4 * var(--rpx)) calc(4 * var(--rpx)) #00000003;
  background: var(--chat-bubble-ai-bg); opacity:.9;
  white-space: pre-line;                      /* ★ 与旧聊天页同一个陷阱 */
  overflow-wrap:anywhere; word-break:break-word; color:var(--chat-bubble-text); font-size:15px }
[data-chat="message-body"] p,h1..h6,ul,ol,blockquote { margin:0 }   /* 平台已清零，无需自己压 */
[data-chat="message"][data-from="ai"]   [data-chat="message-body"] { border-radius: calc(32*var(--rpx)) calc(32*var(--rpx)) calc(32*var(--rpx)) 0 }
[data-chat="message"][data-from="user"] [data-chat="message-body"] { border-radius: calc(32*var(--rpx)) calc(32*var(--rpx)) 0 calc(32*var(--rpx)) }
[data-chat="message-body"] table { border-collapse:collapse; display:block; overflow:auto; width:100%; word-break:keep-all }
[data-chat="message-body"] table td,th { border:1px solid #dfe2e5; padding:6px 13px; white-space:nowrap }
[data-chat="message-body"] img { width:100%; height:auto }
[data-chat="message-body"] div:not([data-chat="message-body"]) > img { width:auto; height:auto }
[data-chat="message-body"] pre, pre.hljs { white-space:break-spaces; border-radius:10px; padding:10px; font-size:14px; overflow-x:auto }

[data-chat="header"] { height: calc(90 * var(--rpx)); min-height: calc(90 * var(--rpx));
  background: var(--chat-bg); color: var(--chat-text); flex-shrink:0;
  display:flex; align-items:center; justify-content:space-between }
[data-chat="header-back"], [data-chat="header-actions"] > [data-action] {
  height: calc(90 * var(--rpx)); background:0 0; border:0; cursor:pointer; display:inline-flex }
[data-chat="header-back"] { padding: 0 calc(20 * var(--rpx)) }
[data-chat="header-back"] img { width: calc(36 * var(--rpx)); height: calc(36 * var(--rpx)) }
[data-chat="header-title"] { flex:1 1 0; min-width:0; font-size: calc(30 * var(--rpx));
  white-space:nowrap; overflow:hidden; display:flex; align-items:center; line-height:1.25 }
[data-chat="header-title"] img { width: calc(50*var(--rpx)); height: calc(50*var(--rpx));
  margin-right: calc(5*var(--rpx)); border-radius:50%; object-fit:cover }
[data-chat="header-actions"] { margin-right:12px; display:flex; align-items:center; justify-content:flex-end }
[data-chat="header-actions"] > [data-action] { margin-left: calc(25 * var(--rpx)) }
[data-chat="header-actions"] > [data-action] img { width: calc(35*var(--rpx)); height: calc(35*var(--rpx)) }
[data-chat="header-actions"] .rate-tip { position:absolute; bottom: calc(-14*var(--rpx)); left:50%;
  transform:translateX(-50%); background:var(--chat-accent); color:#fff; font-size: calc(16*var(--rpx));
  border-radius: calc(20*var(--rpx)); padding: calc(2*var(--rpx)) calc(8*var(--rpx)) }

[data-slot="header-extra"]:empty, [data-chat="author-stage"][data-stage="closed"] { display:none }
[data-chat="author-stage"][data-stage="content"] { position:absolute; z-index:2000 }
[data-chat="author-stage"][data-stage="full"]    { position:fixed; inset:0; z-index:3000 }

/* 角色描述气泡：独立于消息体系，圆角 16rpx（不是 32），底色 --chat-bg */
[data-probe="role-intro"] { width:100%; padding: calc(23*var(--rpx)) calc(30*var(--rpx));
  display:flex; flex-direction:column; align-items:flex-start }
[data-probe="role-intro-body"] { width:fit-content; max-width:100%; padding: calc(24*var(--rpx));
  border-radius: calc(16*var(--rpx)); background: var(--chat-bg); opacity:.9;
  white-space: pre-line; color: var(--chat-text); font-size:15px }

/* 开场白 */
[data-probe="prologue"] { padding: 0 calc(31*var(--rpx)) calc(20*var(--rpx)) }
[data-probe="prologue-title"] span { background:rgba(0,0,0,.5); color:#fff;
  border-radius: calc(15*var(--rpx)); font-size: calc(28*var(--rpx));
  padding: calc(10*var(--rpx)) calc(20*var(--rpx)); display:inline-block }
[data-probe="prologue-chip"] { width:100%; min-height: calc(90*var(--rpx));
  margin-top: calc(20*var(--rpx)); padding: calc(30*var(--rpx));
  border-radius: calc(12*var(--rpx)); background: var(--chat-bg); opacity:.9;
  font-size: calc(26*var(--rpx)); color: var(--chat-text); text-align:left; border:0 }

/* 底栏 */
[data-chat="composer"] { background: var(--chat-composer-bg); color: var(--chat-composer-text);
  width:100%; flex-shrink:0; display:flex; flex-direction:column }
[data-chat="composer"] button { appearance:none; background:0 0; border:0; margin:0; padding:0;
  color:inherit; font:inherit; cursor:pointer }
[data-chat="composer"] button:disabled { opacity:.4; cursor:not-allowed }
[data-chat="composer"] .composer-shortcut-wrap { height: calc(76*var(--rpx)); position:relative; overflow:hidden }
[data-chat="composer"] [data-chat="shortcut"], [data-chat="instruction-bar"] {
  height: calc(76*var(--rpx)); padding: 0 calc(12*var(--rpx)); gap: calc(10*var(--rpx));
  display:flex; align-items:center; transition:transform .3s cubic-bezier(.4,0,.2,1), opacity .3s }
[data-chat="shortcut"].hidden        { transform:translateX(calc(-30*var(--rpx))); opacity:0; position:absolute; inset:0; pointer-events:none }
[data-chat="instruction-bar"].hidden { transform:translateX(calc(30*var(--rpx)));  opacity:0; position:absolute; inset:0; pointer-events:none }
[data-chat="shortcut"] > button { height: calc(56*var(--rpx)); padding: 0 calc(16*var(--rpx));
  border-radius: calc(28*var(--rpx)); font-size: calc(24*var(--rpx));
  background: var(--chat-shortcut-bg); color: var(--chat-shortcut-text); gap: calc(6*var(--rpx)) }
[data-chat="instruction-chip"] { height: calc(56*var(--rpx)); padding: 0 calc(22*var(--rpx));
  margin-right: calc(10*var(--rpx)); background: var(--chat-shortcut-bg);
  border-radius: calc(28*var(--rpx)); font-size: calc(24*var(--rpx)); color: var(--chat-shortcut-text) }
[data-chat="instruction-back"] { width: calc(48*var(--rpx)); height: calc(48*var(--rpx));
  background: var(--chat-modal-accent); color:#fff; border-radius:50%;
  box-shadow: 0 calc(4*var(--rpx)) calc(16*var(--rpx)) #ff6d9759 }
[data-theme="dark"] [data-chat="instruction-back"] { box-shadow:none }
[data-chat="composer"] .composer-row { width:100%; padding: calc(16*var(--rpx)) calc(30*var(--rpx));
  display:flex; align-items:center }
[data-chat="composer"] .composer-field { flex:1 1 0; min-width:0; padding: 0 calc(16*var(--rpx));
  background: var(--chat-input-bg); border-radius: calc(24*var(--rpx));
  border: calc(2*var(--rpx)) solid var(--chat-input-border); display:flex; align-items:center }
[data-chat="composer"] .composer-field.is-expanded { display:grid; padding: calc(20*var(--rpx));
  grid-template-areas:"tools tools tools" "input input input" "chip . send" }
[data-chat="assistant"] img { width: calc(50*var(--rpx)); height: calc(50*var(--rpx)) }
[data-chat="assistant"] .beta-badge { position:absolute; top: calc(-10*var(--rpx)); left: calc(-20*var(--rpx));
  background: var(--chat-accent); color:#fff; font-size: calc(20*var(--rpx));
  border-radius: calc(10*var(--rpx)); padding: calc(4*var(--rpx)) calc(6*var(--rpx)) }
[data-chat="assistant-tip"] { position:absolute; bottom:100%; left:0; transform:translateX(-5%);
  margin-bottom: calc(28*var(--rpx)); padding: calc(8*var(--rpx)) calc(10*var(--rpx));
  border-radius: calc(15*var(--rpx)); background: var(--chat-modal-accent); color:#fff;
  font-size: calc(22*var(--rpx)); white-space:nowrap; z-index:10 }
[data-chat="model-chip"] { font-size: calc(25*var(--rpx)); color: var(--chat-composer-text);
  grid-area:chip; order:-1; display:flex; align-items:center }
[data-action="more"] img { width: calc(50*var(--rpx)); height: calc(50*var(--rpx)) }
```

## 6. 弹窗/浮层族 CSS（实测原文）

```css
/* 长按消息菜单：z-index 8200 + backdrop-filter blur(5px) */
[data-chat="message-menu"] { position:fixed; inset:0; z-index:8200; backdrop-filter:blur(5px) }
[data-chat="message-menu"] .menu-preview { margin: calc(160*var(--rpx)) calc(32*var(--rpx)) 0;
  max-height:50%; padding: calc(32*var(--rpx)); border-radius: calc(40*var(--rpx));
  background: var(--chat-modal-surface); color: var(--chat-modal-text);
  box-shadow: 0 0 calc(8*var(--rpx)) #0000000f; white-space:pre-line; overflow:auto }
[data-chat="message-menu"] .menu-options { width: calc(290*var(--rpx)); margin-left:1rem;
  margin-top: calc(30*var(--rpx)); padding: calc(20*var(--rpx)) calc(32*var(--rpx));
  border-radius: calc(40*var(--rpx)); background: var(--chat-modal-surface) }
[data-chat="message-menu"] .menu-sep { width: calc(233*var(--rpx));
  border: calc(1*var(--rpx)) solid var(--chat-border); height:0 }
[data-chat="message-menu"] .menu-options [data-action] { width:100%; height: calc(80*var(--rpx));
  color: var(--chat-modal-text); font-size: calc(26*var(--rpx)); line-height: calc(80*var(--rpx));
  display:flex; justify-content:space-between; align-items:center }

/* 居中 alert：z-index 9000，遮罩 rgba(0,0,0,.45)，position:absolute（不是 fixed） */
[data-chat="alert"] { position:absolute; inset:0; z-index:9000; background:rgba(0,0,0,.45);
  display:flex; align-items:center; justify-content:center }
[data-chat="alert"] [data-chat="toast"] { padding: calc(45*var(--rpx)) 0;
  font-size: calc(28*var(--rpx)); text-align:center; margin:0 }
[data-chat="alert-ok"] { width:100%; margin: 0 0 calc(30*var(--rpx));
  color: var(--chat-accent); font-size: calc(32*var(--rpx)); text-align:center; display:block }

/* snackbar：两个不同的，z-index 10090 / 8100 */
[data-probe="snackbar"] { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
  z-index:10090; background:rgba(0,0,0,.7); color:#fff; border-radius:4px;
  padding:10px 20px; font-size:14px; max-width:80%; pointer-events:none }
[data-chat="snack"] { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
  z-index:8100; background:rgba(0,0,0,.72); color:#fff; border-radius: calc(16*var(--rpx));
  padding: calc(20*var(--rpx)) calc(28*var(--rpx)); font-size: calc(28*var(--rpx)); max-width:70% }

/* 「+」更多面板：在 composer 内展开，4 列 */
[data-chat="more-panel"] { padding: calc(24*var(--rpx)) calc(30*var(--rpx)) calc(30*var(--rpx));
  gap: calc(20*var(--rpx)); background: var(--chat-modal-bg); color: var(--chat-modal-text);
  display:flex; flex-wrap:wrap }
[data-chat="more-panel"] > button { width: calc(25% - calc(20*var(--rpx)));
  font-size: calc(26*var(--rpx)); line-height: calc(37*var(--rpx));
  color: var(--chat-modal-text); display:flex; flex-direction:column; align-items:center }
[data-chat="more-panel"] > button > span { width:100%; height: calc(129*var(--rpx));
  border-radius: calc(40*var(--rpx)); background: var(--chat-more-item-bg);
  margin-bottom: calc(14*var(--rpx)); display:flex; align-items:center; justify-content:center }
[data-chat="more-panel"] > button img { width: calc(55*var(--rpx)); height: calc(55*var(--rpx)) }

/* AI帮聊候选项（更多面板内） */
.ai-chat-item { background: var(--chat-modal-surface); padding: calc(20*var(--rpx));
  border-radius: calc(20*var(--rpx)); margin-bottom: calc(20*var(--rpx)); display:flex; align-items:center }
.ai-chat-item .item-content { color: var(--chat-modal-text); font-size: calc(28*var(--rpx)); text-align:left }
[data-chat="assistant-tips"] { text-align:center; color: var(--chat-modal-text); font-size: calc(22*var(--rpx)) }
[data-chat="assistant"].ai-assistant-loading { opacity:.6; pointer-events:none }

/* 分享条与分享选择模式 */
[data-chat="share-bar"] { padding: calc(24*var(--rpx)) calc(30*var(--rpx));
  column-gap: calc(24*var(--rpx)); background: var(--chat-composer-bg); display:flex; align-items:center }
[data-chat="share-bar"] > button { flex:1 1 0; padding: calc(20*var(--rpx)) 0;
  border-radius: calc(16*var(--rpx)); background: var(--chat-accent); color:#fff; font-size: calc(28*var(--rpx)) }
[data-chat="root"][data-share-pick] [data-chat="message-frame"] { display:flex; align-items:center }
[data-chat="message-frame"][data-share-picked] { background-color: var(--chat-share-pick-bg); opacity:.9 }
[data-chat="share-pick-toggle"] { width: calc(40*var(--rpx)); height: calc(40*var(--rpx));
  margin: 0 0 0 calc(20*var(--rpx)) }
[data-chat="share-pick-cancel"], [data-chat="share-pick-switch"] { height: calc(90*var(--rpx));
  padding: 0 calc(20*var(--rpx)); color: var(--chat-text); font-size: calc(30*var(--rpx)) }
[data-chat="share-pick-switch"] { color: var(--chat-accent) }
[data-chat="share-pick-bar"] { padding: calc(40*var(--rpx)); column-gap: calc(40*var(--rpx));
  background: var(--chat-modal-surface); display:flex; align-items:center; justify-content:center }
[data-chat="share-pick-bar"] > button { width:25%; color: var(--chat-modal-text);
  font-size: calc(26*var(--rpx)); display:flex; flex-direction:column; align-items:center }
[data-chat="share-pick-icon"] { width: calc(120*var(--rpx)); height: calc(120*var(--rpx));
  margin-bottom: calc(14*var(--rpx)); background: var(--chat-border); border-radius:50% }

/* 分享长图 */
[data-chat="share-shot-intro"] { max-width:90%; margin: calc(16*var(--rpx)) calc(24*var(--rpx));
  padding: calc(24*var(--rpx)); border-radius: calc(32*var(--rpx));
  background: color-mix(in srgb, var(--chat-bg) 90%, transparent) }
[data-chat="share-shot-header"], [data-chat="share-shot-footer"] { width:100%;
  padding: calc(30*var(--rpx)); background:#222; color:#fff; font-size: calc(28*var(--rpx)); opacity:.9 }
[data-chat="share-shot-loading"] { position:absolute; inset:0; z-index:8000;
  background:rgba(0,0,0,.35); color:#fff; font-size: calc(28*var(--rpx)) }

/* 剧情总结提示气泡（在消息流里） */
[data-chat="summary-bubble"] { margin: calc(72*var(--rpx)) calc(30*var(--rpx)) calc(16*var(--rpx));
  padding: calc(18*var(--rpx)) calc(24*var(--rpx)); border-radius: calc(40*var(--rpx));
  border: calc(1*var(--rpx)) solid #ff6d9740; color:#ff6d97;
  background-color:rgba(255,109,151,.08); gap: calc(16*var(--rpx)); display:flex; align-items:center }
[data-chat="summary-bubble"].summary-light { color:#17aafd;
  background-color:rgba(23,170,253,.08); border-color:rgba(23,170,253,.35) }
[data-chat="summary-bubble"] .summary-bubble-btn { padding: calc(8*var(--rpx)) calc(24*var(--rpx));
  border-radius: calc(24*var(--rpx)); background:#ff6d97; color:#fff; font-size: calc(22*var(--rpx)) }

/* 历史加载骨架（会把 messages 整块隐藏） */
[data-chat="root"]:has([data-probe="history-loading"]) [data-chat="messages"] {
  visibility:hidden; flex:0 0 0; min-height:0; overflow:hidden }
[data-probe="history-loading"] { flex:1 1 0; display:flex; align-items:center; justify-content:center;
  gap: calc(12*var(--rpx)); font-size: calc(26*var(--rpx)); color: var(--chat-text-muted); z-index:2 }

/* SDK 调试面板（平台自带，作者插槽） */
[data-slot="sdk-debug"] { position:fixed; bottom:8px; right:8px; z-index:40;
  max-width:42%; max-height:28%; padding:8px; background:rgba(0,0,0,.72); color:#eee;
  font-size:11px; line-height:1.35; pointer-events:none; overflow:auto }
```

## 6b. 🚨 弹窗架构：**平台弹窗在宿主页，卡片 CSS 打不到**

逐个点开实测，这是沙盒与旧聊天页**最重要的结构差异**：

| 面板 | 渲染位置 | 卡片 CSS 能否影响 |
|---|---|---|
| 模型设置 `.model-setting-scope.theme-dark` | **宿主页**（h5.aitchat.org 的 uni-app） | ❌ 不能 |
| 对话设置 `.conv-style-modal` | **宿主页** | ❌ 不能 |
| 总结剧情 `.summary-sheet.theme-dark` | **宿主页** | ❌ 不能 |
| 用户人设 `.role-profile-modal` + `.role-setting` | **宿主页** | ❌ 不能 |
| 分享 `.share-popup` | **宿主页** | ❌ 不能 |
| **`+` 更多面板 `[data-chat=more-panel]`** | **iframe 内**（composer 子节点） | ✅ **能** |
| **指令栏 `[data-chat=instruction-bar]`** | **iframe 内** | ✅ **能** |
| **快捷条 `[data-chat=shortcut]`** | **iframe 内** | ✅ **能** |
| **AI帮聊 `[data-chat=assistant]` + tip** | **iframe 内** | ✅ **能** |
| 长按菜单 `[data-chat=message-menu]` | **iframe 内**（CSS 在沙盒表里） | ✅ **能** |
| alert/toast、snack、share-bar、share-pick、share-shot、summary-bubble | **iframe 内** | ✅ **能** |

宿主页弹窗的实测细节（供参考，作者管不着但要知道存在）：
- 外壳同 uview 三层（`.u-popup` → `.u-transition.u-fade-*`/`.u-slide-up-*` → `.u-popup__content` → scope 类），与旧聊天页**同一批组件**。
- 宿主页 `body` 内联 **51 个**变量：`--background-color`/`--primary-color`/`--card-background-color`… 外加 **`--lo*` 全族**。
- **与旧聊天页的差异**：旧页 `--lo*` 18 个全部「引用但从未定义」；沙盒宿主页**有定义**（实测 `--loBackground-color:#17181a`、`--loPrimary-color:#ff6d97`、`--loCard-background-color:#2c2e32`、`--lo-subtitle-color:#c5c5c5`）。
- 宿主 scope 上解析 `--chat-*` **全部为空**（那 29 个只存在于 iframe 内），反之 iframe 内没有 `--background-color` 那一套。**两套变量体系物理隔离。**
- z-index：模型设置/对话设置/用户人设 10075，**分享 9000**（旧页是 10075，这里不同），总结剧情 **1000000000**。

**对预览的含义**：沙盒全景**不该**把这些宿主弹窗做成"卡片能改样式"的靶子（那是撒谎）。正确做法是：
1. **iframe 内**那批（more-panel / instruction-bar / shortcut / assistant / message-menu / alert / snack / share-* / summary-bubble）要**完整仿真**，因为作者的 CSS 真能打到、也真会打歪。
2. **宿主页**那批只做**层级与遮挡提示**（画出它们盖下来时的 z-index 与覆盖范围），并明确标注"平台侧、卡片改不动"，避免作者白写选择器。

## 6c. 「+」更多面板与指令栏（iframe 内，实测）

| 项 | 实测 |
|---|---|
| `+` 面板节点 | `[data-chat=more-panel]`，父节点是 `[data-chat=composer]` |
| 展开后 composer 高度 | 95px → **412px**（面板本体 317px） |
| 项目数 / 列数 | 11 项 / **4 列**（重置聊天、导出聊天、新的聊天、编辑角色、更换背景、自定义指令、用户人设、设定补充、对话设置、剧情总结、游玩教程） |
| 面板底色 | `var(--chat-modal-bg)`（实测 `#17181a`） |
| 指令栏 | `[data-chat=instruction-bar]`，与 `[data-chat=shortcut]` 互斥切换（加/去 `.hidden`），实测 16 个 `[data-chat=instruction-chip]` |
| `.composer-shortcut-wrap` 高度 | 38px（`calc(76*var(--rpx))`，桌面 rpx=0.5） |
| AI帮聊 💡 | `button[data-chat=assistant][data-action=assistant]`，25×25px，内含 `img`（base64 PNG）+ `.beta-badge`（22×14px，`#ff6d97` 底、白字、10px，实测文案是次数如 "8"）。`[data-chat=assistant-tip]` **默认不存在**，点击后才插入 |
| 舞台 | `[data-chat=author-stage][data-stage=closed]` 时 `display:none`、`position:static`、`z-index:auto` |

## 7. z-index 层级表（实测）

| 节点 | z-index |
|---|---|
| `[data-probe="snackbar"]` | 10090 |
| `[data-chat="alert"]` | 9000 |
| `[data-chat="message-menu"]` | 8200 |
| `[data-chat="snack"]` | 8100 |
| `[data-chat="share-shot-loading"]` | 8000 |
| `[data-chat="author-stage"][data-stage="full"]` | 3000 |
| `[data-chat="author-stage"][data-stage="content"]` | 2000 |
| `[data-chat="assistant-tip"]` | 10 |
| `[data-slot="sdk-debug"]` | 40 |

## 8. 输入行与「+」面板细节（实测 2026-08-29）

### 8.1 composer-row 子件（真机盒模型 @1280 视口，--rpx=0.5px）

```
.composer-row  {1254x57, padding 8px 15px, align-items:center}
├ .assistant-anchor {25x25, margin-right 3px}
│ └ button[data-chat=assistant][data-action=assistant] {25x25}
│     ├ img {25x25}   ← 实测 50rpx（先由 assistant/send 共用的 40rpx 规则设，再被单独覆盖）
│     └ span.beta-badge {22x14, bg #ff6d97, 白字 10px}
├ .composer-field {1191x41, padding 0 8px, radius 12px, min-height 41px(=82rpx)}
│ ├ .composer-tools {0x0 display:none}  ← 仅 is-expanded 显示
│ │   ├ button[data-chat=paste] 粘贴
│ │   └ button[data-chat=clear] 清空
│ ├ textarea[data-chat=input] {padding 0 6px, font-size 13.33px(浏览器默认), max-height 140px}
│ ├ button[data-chat=model-chip][data-action=model] {44x19, order:-1, font-size 12.5px}
│ └ button[data-chat=send] {20x20}
│     └ img {20x20}  ← 40rpx
└ button[data-action=more] {25x25, margin-left 6px}
    └ img {25x25}
```

🚨 `[data-chat="input"]` **本体不设 font-size**；`font-size:calc(32*var(--rpx))` 那条实测在 `::placeholder` 规则里。

### 8.2 三态原文

```css
[data-chat="composer"] .composer-field{background:var(--chat-input-bg);
  border-radius:calc(24*var(--rpx));border:calc(2*var(--rpx)) solid var(--chat-input-border);
  padding:0 calc(16*var(--rpx));flex:1 1 0;align-items:center;display:flex}
[data-chat="composer"] .composer-field:not(.is-expanded){min-height:calc(82*var(--rpx))}
[data-chat="composer"] .composer-field.is-expanded{padding:calc(20*var(--rpx));
  grid-template-columns:auto 1fr auto;
  grid-template-areas:"tools tools tools" "input input input" "chip . send";
  align-items:stretch;display:grid}
[data-chat="composer"] .composer-field:not(.is-expanded) .composer-tools{display:none}
[data-chat="composer"] .composer-row:has(.is-expanded),
[data-chat="composer"] .composer-row:has(.is-multiline){align-items:flex-end}
[data-chat="composer"] .composer-row:has(.is-multiline) .assistant-anchor,
[data-chat="composer"] .composer-row:has(.is-multiline) [data-action="more"]{
  padding-bottom:calc(27*var(--rpx));align-self:flex-end}
[data-chat="composer"] .composer-field.is-expanded [data-chat="model-chip"]{order:0}
```

### 8.3 「+」面板 11 项 data-action（顺序照真机）

`reset` 重置聊天 · `export` 导出聊天 · `conversations` 新的聊天 · `role-edit` 编辑角色 ·
`background` 更换背景 · `instructions` 自定义指令 · `persona` 用户人设 · `extra` 设定补充 ·
`style` 对话设置 · `summary` 剧情总结 · `help` 游玩教程

结构：`button[data-action] > span`（span 是圆角图标底 129rpx 高、吃 `--chat-more-item-bg`）+ 文字。
面板本体 4 列（每项 `width:calc(25% - 20rpx)`），壳吃 `--chat-modal-bg`、文字 `--chat-modal-text`。

## 9. 🚨 令牌特异性与别名（预览复刻必须照抄）

**特异性**：平台令牌挂**单属性** `[data-theme="dark"]` / `[data-theme="light"]`（0,1,0）。作者写
`[data-chat="root"]{--chat-modal-bg:X}` 也是 0,1,0，靠文档顺序取胜（平台 CSS 在前、作者 hoisted
`<style>` 在后）→ **作者赢，且不需要 `!important`**。

预览若写成 `[data-chat="root"][data-theme="dark"]`（0,2,0）会压过作者覆盖 → 作者以为白名单变量
没生效。这是**预览比真机更严**的假象，代价与"预览比真机更宽"同样高。

**别名 4 个**（两套主题皆然，必须发 `var()` 引用形态，不能展开成字面量）：

| 令牌 | 实为 |
|---|---|
| `--chat-bubble-user-bg` | `var(--chat-bg)` |
| `--chat-bubble-ai-bg` | `var(--chat-bg)` |
| `--chat-bubble-text` | `var(--chat-text)` |
| `--chat-more-item-bg` | `var(--chat-modal-surface)` |

展开成字面量后，作者改 `--chat-bg` / `--chat-modal-surface` 真机跟随、预览不跟随。
