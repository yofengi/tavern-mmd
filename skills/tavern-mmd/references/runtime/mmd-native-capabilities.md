# 原生能力清单

来源：[mmd-hud-iframe 固定提交 ae96d63c](https://github.com/Godcount10/mmd-hud-iframe/tree/ae96d63c15dfea75fe75913d22627b4f416ed50e)。

共 67 项动作定义，上游实现 61 项；本基座内置 61 项功能接口；现成对话页已提供这些动作的入口与操作流程。

“已实现”指源码中有处理器，不等于所有页面状态均可调用，也不等于通过真实 MMD 验证。背景、自定义指令和教程为原生跳转入口，对话设置只能读取/提交/关闭。仅定义动作不可只加 UI 按钮就声称支持。

本表的本地测试入口不代表本次已执行；执行结果见具体发布的验证报告。所有真实 MMD 项当前均为 NOT RUN。功能调用详见 [原生动作模块](mmd-action-modules.md)，模型 UI 详见 [模型制作模块](mmd-model-controls.md)。

| 动作 | 分组 | 上游实现 | 基座/界面 | 前置条件 |
|---|---|---|---|---|
| `sendMessage` | 输入 | 有 | 内置 / 示例 UI | 原生输入区可用；sendMessage 保护不同的原生草稿，完全相同的内容可发送 |
| `setInputText` | 输入 | 有 | 内置 / 示例 UI | 原生输入区可用；sendMessage 保护不同的原生草稿，完全相同的内容可发送 |
| `exit` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `copyMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `stopGeneration` | 消息 | **仅定义** | 未实现 | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `continueGeneration` | 消息 | **仅定义** | 未实现 | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `regenerateMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `openEditMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `setEditText` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `applyEditTransform` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `submitEditMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `cancelEditMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `rollbackMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `startNewStoryFromMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `openComments` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `openSharePanel` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `copyShareLink` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `closeSharePanel` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `toggleFavorite` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `refreshConversation` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `deleteMessage` | 消息 | 有 | 内置 / 示例 UI | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `editMessage` | 消息 | **仅定义** | 未实现 | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `previousBranch` | 消息 | **仅定义** | 未实现 | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `nextBranch` | 消息 | **仅定义** | 未实现 | 目标消息存在且身份/操作组匹配；破坏性操作需确认流程 |
| `newChat` | 会话 | **仅定义** | 未实现 | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `openModelSettings` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `closeModelSettings` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `selectModelFilter` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `selectModel` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `openModelConfiguration` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `setModelSetting` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `submitModelConfiguration` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `closeModelConfiguration` | 模型 | 有 | 内置 / 示例 UI | 唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许 |
| `openChatSettings` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `closeChatSettings` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `submitChatSettings` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `openMoreMenu` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `closeMoreMenu` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `activateMoreMenuItem` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `openTutorial` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `openBackgroundPanel` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `openCustomInstructions` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `openConversationPanel` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `selectConversation` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `renameConversation` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `requestDeleteConversation` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `deleteConversation` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `createConversation` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `closeConversationPanel` | 会话 | 有 | 内置 / 示例 UI | 当前会话面板与目标身份有效；删除类动作需确认流程 |
| `openPersona` | 人设 | 有 | 内置 / 示例 UI | 用户人设面板已打开且对应字段可修改 |
| `setPersonaMode` | 人设 | 有 | 内置 / 示例 UI | 用户人设面板已打开且对应字段可修改 |
| `setPersonaName` | 人设 | 有 | 内置 / 示例 UI | 用户人设面板已打开且对应字段可修改 |
| `setPersonaGender` | 人设 | 有 | 内置 / 示例 UI | 用户人设面板已打开且对应字段可修改 |
| `setPersonaIdentity` | 人设 | 有 | 内置 / 示例 UI | 用户人设面板已打开且对应字段可修改 |
| `submitPersona` | 人设 | 有 | 内置 / 示例 UI | 用户人设面板已打开且对应字段可修改 |
| `closePersona` | 人设 | 有 | 内置 / 示例 UI | 用户人设面板已打开且对应字段可修改 |
| `openSupplement` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `setSupplementText` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `openSupplementPositionPicker` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `setSupplementPosition` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `confirmSupplementPosition` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `cancelSupplementPosition` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `submitSupplement` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `closeSupplement` | 补充设定 | 有 | 内置 / 示例 UI | 补充设定面板/位置选择器处于相应状态 |
| `openPromptSelector` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `closePromptSelector` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |
| `applyInstruction` | 导航与设置 | 有 | 内置 / 示例 UI | 对应原生入口/面板存在，且最新 capability 允许 |

## 维护

`mmd-native-capabilities.json` 保存动作参数、源码行与证据状态。用 `scripts/audit_native_capabilities.py --upstream 已下载仓库 --out 输出目录` 重新生成，然后核对新增动作与实际内置模块。不要把解析脚本当 TypeScript 编译器，遇到上游定义形态变化须复核。

第三方代码不随该清单分发。默认基座自动启动自己的原生 DOM 适配器；外部 NativeBridge 的能力以实例声明、已注册处理器与当前状态为准。
