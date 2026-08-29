# 全局美化（按平台与交付档位分流）

## 平台分流

| 平台 | 方案 |
|---|---|
| 当前 MMD | 先在“静态换肤 / 运行时主题包”二档中选型；运行时档必须再读 `theme-runtime.md` |
| 旧版 MMD | 只走静态换肤；不得套用当前 MMD 的运行时主题协议 |
| 本地 SillyTavern | 优先使用原生主题 / 自定义 CSS；卡内注入另按本地平台能力设计 |

## 两档交付

| 档位 | 适用需求 | 交付边界 |
|---|---|---|
| **静态换肤** | 一套固定外观，不需要日夜切换、`native`、玩家微调或持久偏好 | 一条正则可注入激活器 + 公共 CSS + 单套 token；本文后续单规则骨架只适用于本档 |
| **运行时主题包** | `day / night / native` 三态、玩家分主题微调、重置、持久偏好候选、路由离开/重入或 `destroy()` | 仅适用于当前 MMD；必须遵守 `theme-runtime.md` 的 owner/version 租约、生命周期、单例资源、增量恢复与测试矩阵 |

默认规则：用户提出“日夜”“跟随偏好”“原生模式”“设置面板”“记住选择”或任何玩家微调时，不再向静态骨架叠加按钮，直接选择运行时主题包。日夜共享同一份公共选择器，只切根状态与 token；禁止复制两套长选择器。

---

## MMD 静态换肤激活机制

> 本节只描述**静态换肤**。旧版 MMD `<script>` 被过滤，必须用 img onerror；当前 MMD `<script>` 虽可执行，但静态激活只是给 body 加一次开关类，推荐保留 img onerror 作为跨版本写法。运行时主题包不得在此骨架上继续堆切换逻辑，改读 `theme-runtime.md`。

| 部件 | 写法 | 说明 |
|---|---|---|
| 激活开关 | `<img src="x" style="display:none" onerror="document.body.classList.add('z-enabled');this.remove()">` | img onerror 执行后自毁 |
| 总开关类 | `body.z-enabled` | 静态覆盖样式都以它为前缀，停用时移除该类 |
| 正则触发 | `/<beautify>/` | 当前 MMD 的 `findRegex` 必须是 slash literal |
| 正文配合类 | `.z-q` 等 | 留给正则把正文关键词包成自有前缀元素，复用静态样式 |

自定义类、ID、属性和变量一律使用项目自有前缀（样本用 `z-`），避免撞平台类名。静态换肤不宣称提供 `native` 完整恢复：移除开关类只能停用自身 CSS，不能撤销第三方脚本或不可逆 DOM 改写。

> 可拖动悬浮球与抽屉见 `floating-components.md`。运行时主题的设置入口优先复用主题包自带面板，不另造一套侧栏引擎。

---

## MMD 页面结构类名清单（基础层）

> 来源：用户提供的社区文档快照。作者、原 URL 与许可证未记录，仅作兼容研究参考，不宣称原创。它与下节“完整层”速查表有少量出入，两者都收录并标注。

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

> 来源：用户提供的实际生效社区样本快照逆向整理。作者、原 URL 与许可证未记录；类名仅作兼容研究参考，完整保留但不宣称原创或当前稳定。

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
样本做法：定义变量 `--lif`（历史样本变量；新产物对应自有前缀 `--<ns>-icon-filter`），统一打到以下选择器：

- `img[src*='ico_']`、`uni-image img[src*='ico_']`、`uni-image div[style*='background-image']`
- `.btn-icon` 及其子元素、`.header-meun div`、`.header-icon-meun uni-image`
- `.icon-back div`、`.icon-box div`、`.edit-icon div`、`.delete-icon div`、`.modify-btn div[style*='background-image']`、`.model-opt-btn div[style*='background-image']`
- `.item-icon` 下的 `div` / `img` / `uni-image`、`.history-setting-scope .option-btn div[style*='background-image']`

---

## 静态换肤变量架构

> 正式交付使用产物自有前缀。以下骨架以 `z` 为示例命名空间，实际项目应替换成稳定的 bundle 前缀；不得把无前缀短变量暴露到 `:root` / `body`。旧 `--lb/--lc/...` 仅是 legacy selector 方言，需要维护旧选择器时才在该旧模块的作用域根上显式做 alias。

```css
body.z-enabled {
  /* 静态换肤只定义一套值；运行时日夜 token 见 theme-runtime.md */
  --z-bg: 页面底色;
  --z-surface: 卡片底色;
  --z-surface-2: 卡片渐变或次级底色;
  --z-border: 边框色;
  --z-text: 正文色;
  --z-text-2: 次要文字色;
  --z-accent: 强调色;
  --z-accent-2: 辅助强调色;
  --z-highlight: 高亮底色;
  --z-shadow: 阴影;
  --z-shadow-accent: 强调阴影;
  --z-icon-filter: 图标染色 filter;
}
```

静态换肤只有一套变量值。若要 day/night，两套色板都映射到同一组带自有前缀的运行时 token，由 light DOM 根属性切换；公共选择器仍只写一份，具体协议见 `theme-runtime.md`。

| 正式变量 | 含义 | legacy alias（仅兼容旧选择器） |
|---|---|---|
| `--z-bg` | 页面底色 | `--lb` |
| `--z-surface` | 卡片底色 | `--lc` |
| `--z-surface-2` | 次级底色 / 旧卡片渐变色 | `--lcm` |
| `--z-border` | 边框色 | `--lm` |
| `--z-text` | 正文色 | `--lt` |
| `--z-text-2` | 次要文字色 | `--lts` |
| `--z-accent` | 主强调色 | `--la` |
| `--z-accent-2` | 辅助强调色 | `--lg` |
| `--z-highlight` | 高亮底色 | `--lh` |
| `--z-shadow` | 常规阴影 | `--ls` |
| `--z-shadow-accent` | 强调阴影 | `--lsr` |
| `--z-icon-filter` | 图标染色 filter | `--lif` |

legacy adapter 只放在旧模块自己的作用域根上，例如：

```css
.z-legacy-selectors {
  --lb: var(--z-bg);
  --lc: var(--z-surface);
  --lt: var(--z-text);
  --la: var(--z-accent);
  /* 只映射该模块实际读取的槽位 */
}
```
---

## 强制规则

### 静态换肤

1. 所有覆盖样式使用 `!important` 压过 App 自带样式。
2. 所有规则以 `body.z-enabled` 前缀开头；这只能停用自身 CSS，不代表 pristine restore。
3. 自定义类、ID、属性与变量使用项目自有前缀。
4. 本档允许 1 条正则交付（`findRegex` 匹配触发标记，`replaceString` 为激活器 + `<style>`）；字符数必须 < 20000，达到 18000 即预警并评估拆分。

### 运行时主题包

1. 遵守 `theme-runtime.md`，不得套用静态档的“一条规则 + 一个 body 类”充当三态运行时。
2. 公共 CSS、day/night token、玩家 overrides 分层；不复制日夜选择器。
3. `native`、`destroy`、route leave/reenter、资源单例和非法存储降级必须进入测试矩阵。

### 静态换肤交付骨架

> 以下示例**只适用于静态换肤**，不是运行时主题骨架。

```
findRegex:    /<beautify>/
replaceString:
  <img src="x" style="display:none"
       onerror="document.body.classList.add('z-enabled');this.remove()">
  <style>
  body.z-enabled {
    --z-bg: #1a1a2e; --z-surface: #16213e; --z-surface-2: #0f3460;
    --z-border: #533483; --z-text: #e0e0e0; --z-text-2: #a0a0b0;
    --z-accent: #e94560; --z-accent-2: #ff6b6b; --z-highlight: #2a2a4a;
    --z-shadow: 0 2px 8px rgba(0,0,0,.5);
    --z-shadow-accent: 0 4px 16px rgba(233,69,96,.4);
    --z-icon-filter: brightness(0) invert(1) sepia(1) saturate(5) hue-rotate(300deg);
  }
  body.z-enabled .content.left { background: var(--z-surface) !important; color: var(--z-text) !important; }
  body.z-enabled .content.right { background: var(--z-accent) !important; color: #fff !important; }
  /* ... 其余规则 ... */
  </style>
```

> `findRegex` 的触发标记由卡片开场白或系统提示插入，正则匹配后替换为激活器+样式块。

## 换用风格数据库

1. 按 `style-system.md` 选风格（或混搭），先得到制作期规范 token。
2. 静态换肤新产物直接映射到本页 `--z-*` 示例槽位（实际项目替换为自己的命名空间）；只有嵌入旧选择器时，才在其局部根上显式提供 `--lb/--lc/...` legacy adapter。
3. 运行时主题必须把规范 token 映射到 bundle 自有前缀变量，并提供成对 light/dark 色板；玩家覆盖只写 overrides，不回写 preset。
4. 圆角、边框、阴影与装饰按 `style-db/layout-ui.md`、`style-db/decoration.md` 取值；两套主题分别检查对比度与整体性。

---

## 现成范例

优先级如下：

1. **当前 MMD 三态运行时主题包（架构启发后的重写）**：`../../assets/global-beautify-examples/mmd-theme-runtime/`，入口见其 `README.md`。需要 `day/night/native`、玩家微调或路由生命周期时默认选它；验证状态以资产 README 为准，不从本方法论文档虚构实机结论。
2. **[mmd-daytime-refined.md](../../assets/global-beautify-examples/mmd-daytime-refined.md)（社区快照 legacy selector reference）**：仅保留 2026-06-21 当前 MMD 的历史选择器、配色和旧清污结构。它未完整作用域、清污与文本规范化不可完整恢复，不再作为直接可用默认成品。

`../../assets/global-beautify-examples/mmd_cleanup_core.js` 当前是架构启发后重写的 ZMR 2.0 cleanup factory，可供新 runtime owner 作为单 observer、插件总线和 property delta 恢复基础设施；不得脱离 owner 单独重复安装。`mmd-daytime-refined.md` 代码块中的 `_mmd_*` 清污段只是 2026-06-21 社区快照，不代表同名外部 JS 的当前实现。
