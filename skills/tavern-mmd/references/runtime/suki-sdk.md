# 绮梦社写卡接口

本表按随 skill 发布的 Moonstage `63a7768` 核对。写新卡时按 `rules.json.pageMode` 选择下列入口。传统页也把 `window.sdk` 设为 `window.stage` 的别名，单凭这个全局变量存在无法判断页面能力。[随包版本](../../assets/suki-sandbox/source.json) · [官网的页面绑定](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/pages/canvas/canvas.vue)

## 沙箱的 `window.sdk`

以下各表的第一列是顶层入口，第二列列出其公开成员。带 `?` 的参数可省略。[SDK 定义](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/sandbox/sdk/create-sdk.ts)

| 页面与消息 | 公开成员 | 写卡时的用法 |
|---|---|---|
| `sdk.input` | `get()`、`set(text)`、`add(text)`、`insert(text)`、`clear()`、`focus()`、`blur()`、`getCursor()`、`setCursor(pos)` | `add` 追加到末尾，`insert` 在光标处插入。给玩家编辑的选项用 `set` 回填。 |
| `sdk.composer` | `show()`、`hide()`、`visible()` | 控制整块输入区。 |
| `sdk.stage` | `open(mode?)`、`close()`、`el()`、`visible()` | `content` 覆盖消息区，`full` 覆盖整页。把自定义面板加到 `el()` 返回的容器，开关状态读 `visible()`。 |
| `sdk.message` | `capabilities()`、`send(text?, options?)`、`edit(id, text)` | 省略正文即提交草稿。发送成功表示宿主已受理，终稿读 `message:done`。编辑可触发重新生成，受宿主权限控制。发送、编辑在玩家点击时调用，手势外由沙箱请求玩家确认。 |
| `sdk.role` | `get()` | 卡片的 `name`、`avatarUrl`。 |
| `sdk.user` | `get()` | 玩家的 `nickname`、`avatarUrl`、`locale`。 |
| `sdk.text` | `convert(text)`、`ready()` | 按玩家界面语言显示简繁文字。需要字典时先 `await ready()`，表单写入保留原文。 |
| `sdk.model` | `get()` | 读当前模型的 `name`、`cost` 及 `capabilities`。模型或能力变更后重读。 |
| `sdk.generation` | `get()`、`act(action)` | `get()` 返回 `phase/since/outcome`。阶段有 `idle`、`preparing`、`summarizing`、`thinking`、`writing`。在玩家点击时，执行当前 `outcome.actions` 中列出的动作。 |
| `sdk.on` | `on(event, handler)` | 注册下表中的事件，返回 `void`。在脚本初始化时订阅一次。 |
| `sdk.debug` | `log(...args)` | 输出作者脚本调试记录。 |
| `sdk.version` | 字符串属性 | 当前值为 `"1"`。各项宿主能力分别探测。 |

| 数据与分享 | 公开成员 | 作用域和约定 |
|---|---|---|
| `sdk.cache` | `get(key)`、`set(key, value)`、`remove(key)` | 页内临时数据，同步读写。 |
| `sdk.save` | `get(key)`、`keys()`、`set(key, value)`、`remove(key)` | 按卡和玩家保存。预载后可同步读，写入和删除要 `await`。最多 10 个键，每值最多 64 KiB。 |
| `sdk.state` | `get()`、`of(messageId)`、`set(patch)` | 卡变量的现值或历史快照为 `{messageId, data, changes}` 或 `null`。`set` 需要 Context 能力，把路径到值的补丁写在主线最新进度，主线生成中会返回 `BUSY`。 |
| `sdk.archive` | `list()`、`save(title?)`、`fork(serverId)`、`open(id)`、`start(opening?)`、`rename(id, title)`、`remove(id)` | 平台对话存档。`fork` 取消息事件的 `serverId`。`start` 省略参数沿用宿主的开场选择，0 为主开场，1 起为备选开场。 |
| `sdk.history` | `capabilities()`、`list(options?)`、`onChange(handler)` | 当前玩家、卡片、会话的消息历史。`capabilities().available` 为真时才读。`onChange` 返回取消订阅函数。 |
| `sdk.share` | `enabled`、`context`、`audience`、`poll`（只读），`link(code?)`、`qr(text)`、`tallyLink(code, pollKey)`、`respond(option)`、`results()` | 分享入口读 `enabled`。普通链接同步生成，二维码异步返回 `{size, path}`。回流投票先生成专属链接，访客从 `poll` 选答，分享者可查自己发出链接的结果。 |
| `sdk.shared` | `read(keys)`、`vote(key, option)`、`add(key, delta)`、`leaderboard(key, options?)` | 在 `rules.json.sharedState` 先声明跨玩家投票或计数器。一次读一个键或至多 16 个键，排行可传 `{limit}`，写入需要已登录且玩过这张卡的玩家。 |
| `sdk.workshop` | `list()` | 返回本会话启用的工坊项目身份及开场来源。项目含 `workshopId/version/kind/order`，类型为 `dlc` 或 `lorebook`。`openingSource` 可为 `null`、基础开场的索引或工坊开场的标识。 |

**读完整历史。** 第一页可传 `{limit, content: true}`。沿用它的 `revision` 和每一页返回的 `cursor` 逐页读取，到 `complete: true` 才交给时间线或回顾面板。遇到 `HISTORY_STALE` 丢弃本轮累积，从第一页重读。切档、`reset` 或 `unavailable` 时失效旧结果。`replyTo` 可能为 `null` 或指向另一页，不能根据相邻顺序配对。气泡挂载事件仅用于界面渲染。[历史接口与数据类型](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/common/history.ts)

| Context 与主线 | 公开成员 | 写卡时的用法 |
|---|---|---|
| `sdk.capabilities` | `capabilities()` | 返回 `{contexts}`。为真时才能使用以下三组接口、`state.set` 和主线发送的 Context 选项。 |
| `sdk.context` | `run(id, vars, options?)`、`stop(callId)`、`list(id, options?)`、`instances()`、`truncate(id, afterSeq, options?)`、`quote(id, vars, options?)`、`quoteMany(items)`、`models(id, options?)`、`setModel(id, modelId, options?)` | 在 `contexts/<id>.json` 声明独立上下文并提供预设。`quote` 估价，`quoteMany` 单次至多 16 项。`list` 读指定上下文的记录，可用 `afterSeq` 翻页。 |
| `sdk.batch` | `open(options)`、`close(batchId)` | 用 `{maxCharge, idempotencyKey?}` 建立共用预算，把 `batchId` 传给相应调用。关闭返回 `closing` 时，扣点仍在结算。 |
| `sdk.main` | `onCompose(handler)` | `card.json` 声明 `main.assembly: "client"` 时，处理器接收主线输入并返回 `messages`，支持异步。传 `null` 可移除。 |

`context.run` 的选项有 `instance`、`source`、`label`、`worldbooks`、`batch`、`messages`、`tool`、`idempotencyKey`、`onDelta(delta, text)`、`signal`。结束时读取 `status`、`text`、`toolCall`、`reason`、`reasonCode` 和结算字段 `charged/settled`，其中工具和原因字段按结果提供。写回主线由卡片显式选择 `sdk.state.set(patch)` 或 `sdk.message.send(text, {as: 'card', from: {context}})`。`from` 还可指定 `instance/source`，主线发送选项也支持 `batch` 和 `messages`。[Context 声明、参数与结果](https://github.com/hearthroom/cli/blob/v0.13.0/docs/card-contexts.md)

**卡片工具。** 在 `card.json.tools` 声明 `{name, description, schema}`。要调用指定工具，先检查 `sdk.message.capabilities?.().tools`，再检查 `sdk.model.get().capabilities` 的 `tools` 和 `forcedTools` 都为 `supported`。同一对象还报告 `jsonSchema` 和 `imageInput`，值均可能为 `supported`、`unsupported` 或 `unknown`。调用 `sdk.message.send(text, {tool: name})` 后，在 `message:done` 核对工具名和 `toolCall.valid` 再使用 `args`。遇到中断或工具缺失时保留已有正文，按 `reason/reasonCode` 显示结果。[卡片工具手册](https://github.com/hearthroom/cli/blob/v0.13.0/docs/card-tools.md)

## 沙箱事件与显示位置

| 事件 | 何时使用 |
|---|---|
| `ready`、`dispose` | 初始化完成与清理。`ready` 只发一次，晚订阅时直接读当前状态。 |
| `message:new`、`message:stream`、`message:done` | 消息建立、流式正文、终稿。流式载荷为 `{id, role, content}`，终稿另有 `serverId` 和按需提供的工具结果。系统通知不触发消息事件。 |
| `message:mount`、`message:unmount` | 气泡挂载与卸载。晚订阅时 `mount`、`done` 可补发，绘制要能重复执行。对气泡的同步事件回调中查询 DOM 时，选择器作用于该气泡。 |
| `input:change`、`conversation:switch`、`theme:change` | 输入载荷为草稿文本。切档时重读会话数据，换主题时重读根节点。 |
| `back`、`stage:close` | 处理返回及宿主关闭舞台。脚本自行调用 `sdk.stage.close()` 时自行清理。 |
| `model:change`、`generation:phase`、`generation:outcome` | 模型能力、生成阶段或上一轮结果变化。晚挂载先读 `model.get()`、`generation.get()`。 |
| `share:change`、`state:change` | 前者重读 `sdk.share`。后者给出卡变量快照，晚订阅补发最近一份。 |

主题与布局使用公开的 `data-chat` 节点，如 `root`、`message`、`message-body`、`input`、`composer`、`author-stage`。功能栏非空时有 `[data-slot="statusbar"]`。侧栏插入 `left` 或 `right` 插槽，另有 `header-extra`、`toolbar`。卡内文本可用 `{{user}}` 和 `{{char}}`。[事件定义](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/sandbox/sdk/events.ts) · [官方写卡手册](https://sukisuki.chat/zh-Hans/guide.md)

## 沙箱错误码

同步方法可能抛错，异步方法可能拒绝。按 `err.code` 处理，附加信息按需读取 `err.data`。[SDK 错误定义](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/sandbox/sdk/errors.ts)

| 错误码 | 处理方式 |
|---|---|
| `UNAUTHORIZED`、`HOST_DENIED`、`NOT_SUPPORTED`、`UNKNOWN_CAPABILITY` | 核对玩家是否同意、宿主权限及能力开关，提供仍能使用的交互。`UNKNOWN_CAPABILITY` 是保留码。 |
| `INVALID_ARGS`、`RATE_LIMITED`、`BUSY`、`LIMIT_REACHED`、`NETWORK` | 分别检查参数、调用频率、当前生成状态、数量上限和请求结果。会产生扣点的操作先核对结果再决定是否重试。 |
| `SHARE_CONTEXT_INVALID`、`SHARED_DISABLED`、`NOT_DECLARED`、`OPTION_INVALID`、`NOT_ELIGIBLE` | 分别核对分享情境码、共享开关、已声明的键、投票选项和玩家资格。 |
| `HISTORY_UNAVAILABLE`、`HISTORY_STALE`、`HISTORY_CURSOR_INVALID`、`HISTORY_LIMIT` | 依次对应历史当前不可读、版本失效、游标无效和单次读取过大。失效时重新分页，超过上限可缩小页或只读元数据。 |
| `CONTEXT_UNAVAILABLE`、`CONFLICT`、`MODEL_UNSUPPORTED`、`PAUSED` | 核对上下文声明与来源、幂等键与实例设置、所选模型。被暂停后按宿主给出的等待时间处理。 |
| `INSUFFICIENT`、`CHARGE_LIMIT`、`BATCH_CLOSED` | 余额或共用预算不足、估价超出声明上限、批次已关闭或过期时，停止本次调用。 |

## 传统页的 `window.stage`

在 `pageMode: "classic"` 下，`window.sdk` 指向下表同一个对象。沙箱里的 `sdk.stage` 专指作者舞台。迁移时按具体成员选接口。[传统页接口定义](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/utils/stage-intent-api.js)

| 入口 | 公开成员 | 约定 |
|---|---|---|
| `stage.input` | `get()`、`set(text)`、`append(text)`、`add(text)`、`insert(text)`、`clear()`、`focus()`、`blur()`、`getCursor()`、`setCursor(pos)` | `append` 与 `add` 均为追加。 |
| `stage.message` | `send(text?)` | 在玩家点击回调内直接调用，离开手势会拒绝并返回 `not_a_gesture`。 |
| `stage.send` | `send()` | 提交当前草稿，同样需要玩家手势。 |
| `stage.beforeSend` | `beforeSend(handler)` | 同步改写提交文本，重复注册以最后一次为准，传 `null` 清除。处理器报错、超时或返回非字符串时发送原文。 |
| `stage.background` | `set(url)` | 设置聊天背景。 |
| `stage.scroll` | `toTop()`、`toBottom()` | 滚动聊天区。 |
| `stage.on` | `on(event, handler)` | 返回订阅是否成功，支持的事件见下文。 |
| `stage.state` | `get()`、`of(messageId)` | 读当前和历史卡变量快照。 |
| `stage.archive` | `start(opening?)` | 另开对话，开场索引与沙箱相同。 |
| `stage.history` | `capabilities()`、`list(options?)`、`onChange(handler)` | 由宿主按需提供，先检查 `stage.history?.capabilities().available`，翻页规则与沙箱相同。 |
| `stage.share` | `enabled`、`context`、`audience`、`poll`（只读），`link(code?)`、`qr(text)`、`tallyLink(code, pollKey)`、`respond(option)`、`results()` | 情境链接无效或不可用时，同步 `link` 返回 `null`。 |
| `stage.shared` | `read(keys)`、`vote(key, option)`、`add(key, delta)`、`leaderboard(key, options?)` | 与沙箱使用同一套跨玩家声明及资格检查。 |
| `stage.workshop` | `list()` | 与沙箱返回同一形状的工坊元数据。 |

传统页支持 `message:mount`、`message:done`、`conversation:switch`、`theme:change`、`dispose`、`share:change`、`state:change` 七个事件。[传统页事件定义](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/utils/author-asset-mount.js)

已有 MMD HUD 插件的卡还可使用传统页提供的 `window.__MMD_HUD_NATIVE_BRIDGE__`。`getRegisteredActions()` 枚举动作，`getCapabilities()` 检查此刻可用的动作，`getSnapshot()`、`subscribe(listener)` 读取和订阅界面状态，`invoke(action, payload?)`、`sendMessage(text)` 调用动作。桥还提供生命周期方法 `start()`、`refresh()`、`destroy()`，由插件管理。[绮梦的 HUD 桥与动作表](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/pages/canvas/canvas-hud-bridge.ts)

## 独立开场页与本地验收

`opening.html` 在独立文档中运行。公开入口为 `window.hearthroom.fill(text)`（回填草稿）和 `window.hearthroom.send(text)`（玩家点击后发送第一句，缺少手势时改为回填）。聊天规则和舞台交互放在 `rules.json`，开场消息文本放在 `welcome.md`。[开场页接口实现](https://github.com/hearthroom/moonstage/blob/63a7768414952cdb371ac60ac4bfedc789aa08f8/src/common/opening-page.ts)

本地预览使用随包沙箱和官方 CLI 0.13.0 的测试宿主。可实测按钮、输入、舞台、消息生命周期、样例回复及页内模拟存档。此宿主上 `history.capabilities().available`、`capabilities().contexts`、`message.capabilities().tools` 和 `share.enabled` 都为 `false`，模型能力为 `unknown`。工坊元数据、消息编辑或未协商的历史读取返回 `HOST_DENIED`，Context 调用返回 `NOT_SUPPORTED`。制作涉及完整历史、编辑、真实模型、跨玩家状态、工坊或跨设备存档的卡时，将对应行为列为站内试玩项。[本地预览命令](../platforms/suki.md#用官网聊天页沙盒做本地预览) · [官方 CLI 测试宿主](https://github.com/hearthroom/cli/blob/v0.13.0/internal/preview/assets/preview.js)
