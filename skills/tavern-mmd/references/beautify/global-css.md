# 全局美化（按平台分流）

## 平台分流

| 平台 | 方案 |
|---|---|
| MMD（新旧） | 正则注入：img onerror 给 body 加开关类 + uni-app 类名覆盖 CSS（本文档主体）；当前 MMD 可改 script 激活，保留 onerror 回退 |
| 本地酒馆 | 同样的正则注入 CSS 可用；或建议用户走主题/自定义 CSS（非卡内交付物） |

---

## MMD 激活机制

> `<script>` 标签在 MMD 会被过滤，改用 img onerror 执行 JS。所有覆盖样式以 `body.z-enabled` 为前缀，便于一键还原。

| 部件 | 写法 | 说明 |
|---|---|---|
| 激活开关 | `<img src="x" style="display:none" onerror="document.body.classList.add('z-enabled');this.remove()">` | img onerror 注入 JS，执行后自毁 |
| 总开关类 | `body.z-enabled` | 所有覆盖样式都以它为前缀，便于一键还原 |
| 夜间模式类 | `body.z-enabled.z-dark-mode` | 覆盖同名 CSS 变量即换色，选择器不动 |
| 悬浮切换按钮 | `.z-sidebar-btn` + `.z-btn-text` | fixed 贴边按钮，inline onclick 循环 原/日/夜 |
| 正则配合类 | `.z-q` 等 | 留给正则把正文关键词包成 `<span class="z-q">`，复用全局样式 |

自定义类一律加自己的前缀（样本用 `z-`），避免撞平台类名。

---

## MMD 页面结构类名清单（基础层）

> 来源：用户补充的页面结构逆向清单。与下节"完整层"速查表有少量出入，两者都收录并标注。

### 容器层级

```
.chat（最外层聊天容器）
  └─ .chat-scope-box（聊天作用域盒子）
       └─ .scroll-view（滚动视图容器）
            └─ .chat-body（聊天主体区域）
```

### 消息气泡

```
.item（单条消息项）
  └─ .touch-scope（触摸作用域）
       └─ .content（内容容器）
            ├─ .content.left   → AI 回复气泡
            └─ .content.right  → 用户发送气泡
.msg-content（消息文本内容区）
.msg-text（具体文字内容）
```

### 底部输入区

```
.chat-bottom（底部整体容器）
  └─ .uni-textarea（文本输入框外层）
       └─ .chat-input-scope（输入作用域）
            └─ textarea（实际输入框元素）
```

### 头像与标识

- `.avatar`（头像容器）—— **补充清单版本**
- `.avatar-img`（头像图片）
- `.avatar-scope` —— **档案版本**（不同版本/页面可能类名有差异，实际使用时建议两组选择器都写）

### 功能按钮区

```
.btn-scope（按钮作用域）
  └─ .send-btn（发送按钮）  ← 补充清单版本
```

> 档案版本发送按钮为 `.chat .chat-bottom .send-msg`，实际使用时建议两组都写。

### 页面背景

- `.page`（页面根容器）
- `.chat-bg`（聊天背景层）

### 图片

- `.msg-img`（消息中的图片）
- `img`（所有图片元素）

### 常用完整选择器写法

| 目标 | 完整选择器 |
|---|---|
| 用户消息气泡 | `.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content.right` |
| AI 消息气泡 | `.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content.left` |
| 输入框 | `.chat .chat-bottom .uni-textarea .chat-input-scope textarea` |
| 发送按钮（补充版） | `.chat .chat-bottom .btn-scope .send-btn` |
| 发送按钮（档案版） | `.chat .chat-bottom .send-msg` |
| 整体背景 | `.chat-bg` |
| 页面容器 | `.page` |

---

## MMD 界面类名速查（完整层）

> 来源：实际生效样本逆向整理。类名是逆向成果，完整保留。

### 聊天主界面

| 区域 | 选择器 |
|---|---|
| 顶栏 | `.chat .topTabbar`，角色名 `.header-roleName` |
| 开场白 | `.prologue-scope .prologue-content` |
| AI 气泡 | `.content.left`（正文文字 `.content.left font`） |
| 用户气泡 | `.content.right`（正文文字 `.content.right font`） |
| 气泡通用路径 | `.chat .item .touch-scope .content`、`.chat .chat-scope-box .scroll-view .chat-body .item` |
| 头像 | `.avatar-scope`（样本直接 `display:none` 并把气泡改通栏） |
| 消息长按菜单 | `.msg-action-scope`，项 `.action-item` |
| 消息选项卡 | `.msg-option-scope .msg-content-box`、`.msg-options-box .option-item`（内文 `uni-text`） |
| 消息编辑弹层 | `.msg-modify-scope .option-box .option-item` |
| 代码块 | `.hljs`、`.vditor-ir pre.vditor-reset` |

### 输入区

| 区域 | 选择器 |
|---|---|
| 底部容器 | `.chat-bottom-wapper`、`.chat-bottom`（样本设为透明） |
| 输入框 | `.chat .chat-bottom .uni-textarea .chat-input-scope` 及其 `textarea` |
| 发送按钮 | `.chat .chat-bottom .send-msg` |
| 快捷按钮条 | `.shortcut-button-scope`，项 `.shortcut-button-scope .item` |
| "更多"面板 | `.more-scope`，项 `.more-scope .item`，图标 `.item-icon`，标题 `.item-title` |

### 弹窗与设置页

| 区域 | 选择器 |
|---|---|
| 通用弹窗 | `.u-popup__content` |
| 确认框 | `.confirm-scope`（`.confirm-title` / `.confirm-content` / `.confirm-bottom` / `.ok-btn` / `.cancel-btn`） |
| 模型设置页 | `.model-setting-scope`（`.des-scope`、`.header-scope .title`、`.stream-switch-scope`、`.power-scope`、`.save-btn`、`.bottom-scope .btn`、`.token-scope .token` 与 `.token.selected`） |
| 模型列表 | `.model-list`、`.model-switch-scope`、`.model-item`、`.model-intro`、`.model-battery`、`.model-perm` |
| 历史记录页 | `.history-setting-scope`（`.history-item .title` / `.remark`、`.option .option-btn`、`.header-scope .title`） |
| 自定义指令页 | `.custom-instruction-scope`（`.list-scope .content-scope .item`、`.edit-scope .content-scope .form-item` 下的 `.label` / `.input-scope` / `.custom-textarea-box`、`.header-scope .title` / `.btn-scope`、`.bottom-scope .save-btn`） |
| 输入组件 | `.u-input__content__field-wrapper__field` |
| 开关 | `.u-switch`、`.u-switch__node`、`.u-switch--on` |
| 加载动画 | `.u-loading-icon`、`.u-loading-icon__spinner--semicircle` |
| 滚动条 | `::-webkit-scrollbar` / `-track` / `-thumb`（body.z-enabled 前缀下） |

### 图标染色

App 图标是 PNG/背景图，无法用 `color` 改色，只能用 `filter` 重新染色。
样本做法：定义变量 `--lif`（一串 `brightness/invert/sepia/saturate/hue-rotate` 滤镜），统一打到以下选择器：

- `img[src*='ico_']`、`uni-image img[src*='ico_']`、`uni-image div[style*='background-image']`
- `.btn-icon` 及其子元素、`.header-meun div`、`.header-icon-meun uni-image`
- `.icon-back div`、`.icon-box div`、`.edit-icon div`、`.delete-icon div`、`.modify-btn div[style*='background-image']`、`.model-opt-btn div[style*='background-image']`
- `.item-icon` 下的 `div` / `img` / `uni-image`、`.history-setting-scope .option-btn div[style*='background-image']`

---

## 主题变量架构

```css
body.z-enabled {
  --lb: 页面底色;
  --lc: 卡片底色;
  --lcm: 卡片渐变色;
  --lm: 主题深色（边框）;
  --lt: 正文色;
  --lts: 次要文字色;
  --la: 强调色;
  --lg: 辅助强调色;
  --lh: 高亮底色;
  --ls: 阴影;
  --lsr: 强调阴影;
  --lif: 图标染色 filter;
}

body.z-enabled.z-dark-mode {
  /* 同名变量换夜间值，选择器不动 */
}
```

换主题 = 只改变量值；日/夜切换 = body 加减 `z-dark-mode`，选择器不用动。

| 变量 | 含义 |
|---|---|
| `--lb` | 页面底色（背景色） |
| `--lc` | 卡片底色 |
| `--lcm` | 卡片渐变色 |
| `--lm` | 主题深色，用于边框 |
| `--lt` | 正文色 |
| `--lts` | 次要文字色 |
| `--la` | 强调色 |
| `--lg` | 辅助强调色 |
| `--lh` | 高亮底色 |
| `--ls` | 阴影 |
| `--lsr` | 强调阴影 |
| `--lif` | 图标染色 filter 值 |

---

## 强制规则

1. 所有覆盖样式必须 `!important`（压过 App 自带样式）
2. 所有规则以 `body.z-enabled` 前缀开头（一键还原）
3. 自定义类加自有前缀防撞平台类名（样本用 `z-`）
4. 交付物 = 1 条正则（findRegex 匹配触发标记，replaceString = 激活器 + `<style>` 全套 CSS），字符数必须 ≤ 20000，超限拆分多条正则

### 交付正则骨架示例

```
findRegex:    <beautify>
replaceString:
  <img src="x" style="display:none"
       onerror="document.body.classList.add('z-enabled');this.remove()">
  <style>
  body.z-enabled {
    --lb: #1a1a2e; --lc: #16213e; --lcm: #0f3460;
    --lm: #533483; --lt: #e0e0e0; --lts: #a0a0b0;
    --la: #e94560; --lg: #ff6b6b; --lh: #2a2a4a;
    --ls: 0 2px 8px rgba(0,0,0,.5);
    --lsr: 0 4px 16px rgba(233,69,96,.4);
    --lif: brightness(0) invert(1) sepia(1) saturate(5) hue-rotate(300deg);
  }
  body.z-enabled .content.left { background: var(--lc) !important; color: var(--lt) !important; }
  body.z-enabled .content.right { background: var(--la) !important; color: #fff !important; }
  /* ... 其余规则 ... */
  </style>
```

> `findRegex` 的触发标记由卡片开场白或系统提示插入，正则匹配后替换为激活器+样式块。
