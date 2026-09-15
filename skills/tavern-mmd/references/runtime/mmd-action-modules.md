# 旧 MMD 同层卡原生动作模块

适用 `chatVersion:0` / 缺省。基座内置固定上游已实现的 **61 项功能接口**，包括发送、8 项模型动作与本页的 52 项扩展。它操作原生页面，不是 MMD 官方 SDK，也不是后端直连。仅有定义的 stopGeneration、continueGeneration、editMessage、previousBranch、nextBranch、newChat 仍不可用；会话新建使用已经实现的 createConversation。

现成演示界面保持消息、模型和可选小游戏；本页的新增功能由作者按需求设计界面。普通 Mock 预览没有假装提供所有原生面板；全部动作的本地验证使用独立 DOM 夹具。全部真实 MMD 证据当前为 NOT RUN。

## 1. 功能层与数据

复制完整 `assets/same-layer-kit/` 并用 `build_same_layer.py` 构建，即会包含内置 DOM 桥接。已有宿主也可以提供已启动的 NativeBridge 实例，由 `provided-actions.js` 适配。61 项内置动作不需要作者额外提供 projectResult。可在 Host 启动配置用 allowedActions 收窄当前作品可调用的动作；它同时约束发送、模型和本页功能。

调用通道沿用 `native.invoke`。`snapshot.native.actions` 提供下表的功能快照，每组有自己的 `revision`。消息也以同一 ID 出现在 `snapshot.native.messages`。模型快照仍在 `snapshot.native.models`，见 [模型模块](mmd-model-controls.md)。

| 功能快照 | 主要内容 | 动作 |
|---|---|---|
| composer | 输入框文字与是否可编辑 | setInputText |
| navigation | 已观察的收藏状态 | exit / openComments / toggleFavorite / refreshConversation |
| messages | items：消息 ID、角色、文字、位置、指纹和逐消息能力 | copyMessage / regenerateMessage / openEditMessage / deleteMessage / rollbackMessage / startNewStoryFromMessage |
| editPanel | 绑定消息、编辑文字、文本工具 | setEditText / applyEditTransform / submitEditMessage / cancelEditMessage |
| sharePanel | 标题、原生分享链接 | openSharePanel / copyShareLink / closeSharePanel |
| moreMenu | 项目 ID、名称、种类、可用性和 destructive 标记 | openMoreMenu / closeMoreMenu / activateMoreMenuItem / openTutorial / openBackgroundPanel / openCustomInstructions |
| conversationPanel | conversations：ID、指纹、位置、标题、摘要、当前标记、修改/删除能力 | openConversationPanel / selectConversation / renameConversation / requestDeleteConversation / deleteConversation / createConversation / closeConversationPanel |
| personaPanel | 模式、称呼、性别选项、身份描述、字段长度与只读状态 | openPersona / setPersonaMode / setPersonaName / setPersonaGender / setPersonaIdentity / submitPersona / closePersona |
| supplementPanel | 正文、长度、位置文字和 picker 选项 | openSupplement / setSupplementText / openSupplementPositionPicker / setSupplementPosition / confirmSupplementPosition / cancelSupplementPosition / submitSupplement / closeSupplement |
| instructionSelector | 指令 ID、标签、指纹、位置 | openPromptSelector / closePromptSelector / applyInstruction |
| chatSettings | 只读设置分组与选项快照 | openChatSettings / closeChatSettings / submitChatSettings |

backgroundPanel 和 customInstructionsPanel 另提供 open、title、revision，用于确认打开状态。**打开面板不等于已实现其中全部编辑行为**；例如上游没有独立修改对话设置选项的动作，本基座不编造一个。通用更多菜单也不能绕过限制调用重置聊天、导出聊天或编辑角色等未支持项目。

内置 DOM 快照仅发送必要文字和结构，不发送原生 HTML、凭据或 DOM 对象。临时 ID、指纹和列表位置是当前目标引用，不能当服务器会话 ID 或存档键。历史快照限量，historyComplete 保持 false。

## 2. 参数

每次执行先读取最新快照。所有目标动作、字段修改、关闭/提交动作以及 toggleFavorite 都带所属组的 revision；直接打开顶层面板和 exit/openComments/refreshConversation 可以不带。状态变化或节点替换后，旧 revision 被拒绝。选择器、任意脚本和未知参数不能从 Frame 传给 Host。

| 动作类别 | revision 之外的参数 |
|---|---|
| setInputText / setEditText / setSupplementText / submitSupplement | text（允许空串清空；受字段长度约束） |
| copyMessage / regenerateMessage / openEditMessage / startNewStoryFromMessage | messageId |
| deleteMessage / rollbackMessage | messageId；确认执行时再带 confirmationToken |
| applyEditTransform | transformId |
| submitEditMessage | messageId、text |
| activateMoreMenuItem | itemId |
| selectConversation / requestDeleteConversation | conversationId、fingerprint、index |
| renameConversation | 上述会话引用＋title |
| deleteConversation | 上述会话引用＋confirmationToken |
| setPersonaMode / setPersonaGender | modeId / genderId |
| setPersonaName / setPersonaIdentity | name / identity |
| submitPersona | name、identity；当前只读字段不被覆盖 |
| setSupplementPosition | choiceId |
| applyInstruction | instructionId、fingerprint、label、index；外部桥接所需的原生 revision 由适配器转换 |
| 其余打开、关闭、提交、导航动作 | 无额外参数 |

例如，作者自己的会话列表选中一行后：

```js
const panel = snapshot.native.actions.conversationPanel;
const selected = panel.conversations.find(row => row.id === selectedRowId);
await call('native.invoke', {
  action: 'selectConversation',
  payload: {
    revision: panel.revision,
    conversationId: selected.id,
    fingerprint: selected.fingerprint,
    index: selected.index
  }
});
```

capabilities[action].available 表示当前动作入口可用；还需检查目标行的 capabilities/available/disabled。setInputText 是显式改写原生草稿，不发送；sendMessage 则保留现有草稿，避免无意覆盖。

外部桥接只返回自身已提供的数据。当前上游快照不提供完整 composer 文字或独立收藏布尔状态，因此 text/favorite 返回 null，分别标记 readable:false / evidence:unknown；以动作回执和原生页面为准。其他项目缺失字段同样不猜测。

## 3. 删除、回溯和编辑

- deleteMessage：首次调用返回 confirmation-required，不删除。作者界面展示 prompt；玩家确认后，用原 messageId、当前 revision 和 confirmationToken 再次调用。
- rollbackMessage：采用同样的两阶段协议。即使上游处理器会自行点击原生确认，本基座也先返回待确认阶段。
- 会话删除：先 requestDeleteConversation，展示返回的 prompt；确认后调用 deleteConversation。只处理结构明确的非当前会话。
- 令牌只对目标、当前上下文和短期交互有效，使用后即失效。目标变化、会话切换、取消或超时后重新读取，不自动重试。
- 消息编辑绑定最初打开的气泡和编辑面板。setEditText、工具操作及提交都检查该绑定，不能修改后来出现的无关面板。
- 已有原生编辑或确认弹窗与新操作冲突时，返回原生页面处理。关闭设置/人设面板不承诺撤销此前已经生效的修改。

## 4. 结果与生命周期

成功返回 `{ok, action, accepted, completed, persisted, data}`。confirmation-required 的 accepted 为 false；它不是动作执行完成。其余 data.phase 说明实际观察到的阶段：

- input-observed / setting-observed / text-observed：已读到当前字段状态。
- opened / closed：相应面板出现或关闭。
- edit-observed / deleted / rollback-observed：已核对气泡变化或目标移除；历史超过当前可见窗口时可能无法核对完整结果，返回未确认错误，不自动再操作。
- conversation-change-observed / story-change-observed：观察到原生消息或目标状态变化；不证明已取得服务器会话标识。
- creation-dispatched / dispatched / transform-dispatched：操作已经发出。复制分享链接不伪称已读回剪贴板；退出、评论、刷新等同样不伪造服务器完成回执。
- submitted：原生提交动作后面板已关闭，不等于服务器持久化证明。

completed 与 persisted 始终为 unknown。外部桥接返回的已知阶段会保留，仍不提升证据等级。导航或切换账号/角色/会话可能关闭当前 Frame，使旧调用不再收到结果；不要在新会话自动重放。

所有原生组共享一个并发入口，包括模型和消息发送。退出/隐藏时取消本基座的后续处理；已经送到平台的动作不能据此视为撤销。外部实例仍由原宿主管理，本基座不 start/destroy 调用者的 NativeBridge。

## 5. 验证范围

`test_same_layer_actions_browser.mjs` 使用原创原生 DOM 夹具和临时测试 Frame，经过真实构建链执行新增 52 项动作，并检查数据变化、确认、目标过期、禁用、超时与取消。`test_same_layer_actions.mjs` 检查外部实例的全动作参数映射和生命周期。消息/游戏与模型组继续用各自回归。

能力表的源码来源、实现状态和 UI 状态见 [能力清单](mmd-native-capabilities.md)。测试卡可用于静态比较打包与动作名称；未经真实环境验收，不把“测试卡中存在代码”当成“所有动作在当前 MMD 已可用”。

## 现成对话页

已提供可组合的消息、模型与原生功能界面，详见 [对话页模块制作](../creation/same-layer-dialogue.md)。模块开关不改变 Host 允许调用范围；原生设置只能在已实现动作范围内操作。
