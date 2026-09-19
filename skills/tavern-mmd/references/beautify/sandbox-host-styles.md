# 新页宿主弹窗换肤

适用 `/mmdsandbox`、`chatVersion:1`。作者规则中的静态 `<style>` 可以包含开放的 `[data-host="…"]` 选择器；平台将这部分 CSS **抽取、过滤后注入宿主页**。这是样式通道，不是跨源 DOM 接口，也没有新增 SDK 能力。作者不能据此读取宿主 DOM、调用私有业务或复制虚假的平台设置。

iframe 内的消息、功能栏、舞台仍按 `[data-chat]`、`[data-slot]` 和作者 class/id 制作；平台生成的 `data-host` 根与“作者 HTML 的自写 `data-*` 会被净化”并不矛盾。两份文档不共享 CSS 变量继承链，不能假定 iframe 的 `--sbk-*` 自动到达宿主。

## 1. 来源与时效

先核对版本、日期与环境，再比较同一范围内的证据强弱。旧探针保留为历史记录，不能据旧版没有通道就否定后续文档开放的能力；本地预览通过也不等于新平台验收。

| 依据 | 本次可采用的内容 | 边界 |
|---|---|---|
| 用户提供《角色卡制作手册-1.pdf》，37 页，第 7、36–37 页；2026-09-19 离线核对 | 21 个开放根、排除区与静态 CSS 抽取过滤 | 来源摘要及文件指纹见 [host-contract.json](../../scripts/fixtures/mmdsandbox/host-contract.json)；核对日不是平台发布日期 |
| 资料包 2026-09-15 `h5.testai1.com` 观察 | 特定弹窗内部结构、状态，宿主过滤 `:has()` 的现象 | 测试站与当日实现，不是所有正式环境的稳定 API |
| 资料包 2026-09-16 总结记录与用户验收反馈 | summary 主面板、正文编辑与添加锚点可复用，之前未注入问题已被用户确认恢复 | 不声称本轮重新完成所有交互、保存或设备验收 |
| 仓库 2026-08/09 历史探针 | 跨源隔离、旧弹窗布局、直接改 iframe 变量不会穿透宿主 | 不等于“卡片 CSS 永远改不了宿主”；内部 class 和尺寸按原日期保留 |

SDK 的 30 能力、12 事件、7 公开错误码与 `BUSY`/已揭示累计流式文本按 2026-09-05 官方网页核对记录收录；`ready`、`save.remove`、存档配额与外链加载冲突按 [平台规范](../platforms/mmd-sandbox.md) 的历史日期处理，目标版本待复验。资料仍未提供 `sdk.vars`/`vars:change` 的完整运行契约，不推测签名。

## 2. 开放根：19 + summary + summary-confirm

机器清单以 [host-contract.json](../../scripts/fixtures/mmdsandbox/host-contract.json) 为准。根开放不代表它的全部内部结构、确认分支或真实保存已验收。

| `data-host` 值 | 功能 |
|---|---|
| `conversations` | 会话列表、新建聊天 |
| `conv-delete` | 删除会话确认 |
| `conv-rename` | 重命名会话 |
| `conv-limit` | 会话条数上限 |
| `models` | 模型列表及模型帮助层 |
| `model-setting` | 模型设置 |
| `persona` | 用户人设 |
| `persona-confirm` | 人设未保存确认，独立树 |
| `extra` | 设定补充 |
| `style` | 对话设置 |
| `instructions` | 自定义指令管理 |
| `reset` | 重置确认 |
| `background` | 更换背景 |
| `assistant-intro` | 帮聊介绍 |
| `message-edit` | 消息编辑 |
| `message-delete` | 消息删除确认 |
| `message-backtrack` | 回溯确认 |
| `share-role` | 分享角色 |
| `share-records` | 分享聊天记录 |
| `summary` | 总结/记忆管理主面板，正文编辑及添加锚点在根内 |
| `summary-confirm` | 总结相关确认：删除、还原、档位、超限、提示词介绍、执行确认等；位于 summary 树外 |

未开放区域包括充值 `recharge`、SDK 授权 `sdk-prompt`、沙盒断联 `sandbox-lost`、启动加载 `boot-loading` 和登录页。部分主题色可能透传不代表这些区域开放了定向样式或布局。

入口也要分清：模型切换是 `models`，模型设置是 `model-setting`；“选择指令”使用 iframe 内 `instruction-bar`，自定义指令管理才是宿主 `instructions`；“新的聊天”先打开 `conversations`。换肤不替代这些原生入口与业务。

## 3. 两条 CSS 通路

| 通路 | 写法 | 约束 |
|---|---|---|
| 沙盒文档 | `[data-chat="root"]`、`[data-slot]`、作者 class/id | 样式仅在 iframe 内应用；旧源码的选择器观察仅适用于这条通路 |
| 宿主弹窗 | 每个选择器最左直接写精确的开放 `[data-host="…"]`，再用空格或 `>` 选已核对后代 | 不加 `[data-chat="root"]` 或作者容器前缀；抽取后经独立过滤进入宿主 |

宿主规则用平铺 CSS；文档说明原生嵌套丢弃、含 `url(` 的声明丢弃。`:has()` 被过滤是资料包的 2026-09-15 测试站观察，制作时避用，不能扩大成“整个沙盒 CSS 都禁用 :has”。内部 class、选中态属性和过滤器生成的重复根选择器均不升格为稳定接口。

本地 `sandbox_host_css.py` 只接受可判断作用域的保守子集：精确根、后代关系及 `@media`，对混入非宿主根的选择器组、树外兄弟、原生嵌套、`url()`、`:has()`/复杂伪类、转义及未知语法报告并拒绝转发。**解析器拒绝不等于平台明确禁止该语法**；不能拿它证明平台过滤器逐字相同。

只放 `<style>` 的规则装卡即被抽取，不需要命中一个可见锚点。不要用 CSS `content` 换平台文字，不替换原生图标、价格、权限和真实保存；也不覆盖宿主 `transform` 破坏开场动画与键盘避让。根本身和内部控件分别检查深浅色、禁用态、焦点、长内容与滚动。

## 4. 总结面板的三个范围

资料中的 `data-host="summary"` **就在 `.summary-sheet` 本体上**。改面板本身直接写 `[data-host="summary"]`；`[data-host="summary"] .summary-sheet` 会误把本体当后代。正文编辑 `.summary-ov-edit` 与添加锚点 `.summary-ov-anchor` 位于根内，这两个 class 是当日结构记录。

`summary-confirm` 是独立的树外根，不能写成 `[data-host="summary"] [data-host="summary-confirm"]`。目前只确认开放根及关系，未形成可依赖的内部 class 契约。先做根级配色/尺寸，不编造按钮或正文层类名，不据本地占位夹具宣称删除、还原、超限等分支已测试。

```css
/* summary 主根本身 */
[data-host="summary"] {
  background: #20232b;
  color: #f4f1eb;
}
/* 已观察的根内编辑层 */
[data-host="summary"] .summary-ov-edit,
[data-host="summary"] .summary-ov-anchor {
  background: #292d37;
  color: #f4f1eb;
}
/* 树外确认根单独声明；这里不推测内部 class */
[data-host="summary-confirm"] {
  background: #20232b;
  color: #f4f1eb;
}
```

以上是固定配色示例，不声称自动适配深浅色。可复用配方见 [summary.css](../../assets/sandbox-host-styles/summary.css)；按作品所需改值，根内浮层与树外确认层分开验收。完整结构只保留必要选择器，不搬整张测试站 DOM。

## 5. SBK 制作期配置与运行时主题

SBK 的 `theme.js` 与生成器共享 29 个 `--chat-*` 颜色变量注册，保留既有别名；`--chat-viewport-height` 是平台几何值，不纳入调色盘。可选宿主样式通过配置引入：

```json
{"hostStyles": ["summary.css"]}
```

路径相对配置文件。生成器按完整规则边界输出独立静态 `<style>` 规则并校验宿主子集；默认不启用，不将它塞进 iframe 的 `base.css` 或世界书。完整用法见 [SBK 方法论](sandbox-kit.md)。

**阅读主题与静态宿主皮肤分别管理。** 玩家切换 preset 或停用 SBK 阅读主题，只作用于运行时阅读覆盖，不撤销制作期输出的宿主皮肤。iframe 运行时新增 style、修改变量、切卡清理和停用撤销是否再次转发尚未验证；不能承诺统一开关，也不为此编造 postMessage、宿主 DOM 桥或 SDK 方法。

## 6. 本地预览与交付

新页 chat 全景在 iframe 外展示宿主根索引，并把抽取后的 CSS 仅注入外层。已知结构可用于检查外观和遮挡；未知根/分支只显示明确标注的占位。summary 包含主面板、已观察的编辑/锚点层，summary-confirm 内部仍待验证。thin-preview 只验沙盒文档及 SDK 降级，不模拟宿主弹窗换肤。

舞台调试走统一状态：content 对齐消息区、full 覆盖沙盒视口；关闭/重开/切会话不删除作者子树。用 BUSY 控制和流式动作测试草稿保留、禁止自动重试；模拟器不调用真实 AI。详见 [沙盒同层验收](../creation/sandbox-same-layer-card.md#8-制作与验收顺序)。

交付记录分别列出资料依据、静态校验、本地浏览器、目标平台和实体设备证据。重点验证原生入口仍可点、确认/取消可见、关闭二层回到父层、长内容/窄屏/短屏/软键盘不遮挡；没有真实保存或确认动作证据就标未执行。本地 CSS 子集通过不代表生产过滤器、付费/权限或持久化已验收。
