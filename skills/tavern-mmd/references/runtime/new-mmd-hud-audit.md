# new-mmd-hud：可借鉴结构与沙盒兼容审查

审查日：2026-09-19。来源：[贪心鬼 Godcount10/new-mmd-hud](https://github.com/Godcount10/new-mmd-hud/tree/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f)，固定提交 `cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f`，提交日期 2026-09-06。以下评价只针对该快照；不能因后来获取了不同提交仍沿用逐行结论。

**结论：采用其分层思路，重写平台适配和交付包装。** 它能说明如何用真正的网页组件自绘新页界面，但本地 Mock 与 skill 已确证的 SDK 行为有多处差异，不能原样并入作为沙盒基座。制作方法见 [沙盒同层卡指南](../creation/sandbox-same-layer-card.md)。

## 1. 实际接管了什么

[production/entry.ts](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/production/entry.ts) 读取 `window.sdk`（兼容脚本作用域的 `sdk`），打开 `full` 舞台，建立 `HudRuntime`，注册实例选中的功能与渲染器。[platform/contracts.ts](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/platform/contracts.ts) 只是包住 SDK、window/document 和订阅。

因此它接管的是**作者可见的 UI 和交互映射**：MMD 的宿主、SDK、会话和模型请求仍在。它没有在生产端安装本地 `MockMmdRuntime`，也没有证明取得了所有底层私有接口。称为“官方 SDK 上的完整网页渲染层”更准确。

[ARCHITECTURE.md](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/ARCHITECTURE.md) 的 Instance → Adapter / Runtime / Store / 可选 Domain / Features / Renderers 分工值得保留：

- 网页作者能使用 Vue、DOM、Canvas、WebGL；框架只负责表现。
- 本地 Host/Mock 与生产 SDK 接口分开，便于本地迭代。
- 游戏规则可独立于框架，不要求每张卡创建 GameStore。
- 按实例打包模块，避免聊天页面携带全部播放器和资源库。
- 不可用原生动作显式返回不可用，而非偷偷沿用旧桥接。

其中最接近完整聊天同层卡的是 **Dragon Raja** 实例；NIKKE/Live2D 主要展示舞台图鉴/播放器，不能将其效果等同于完整聊天接口已覆盖。

## 2. 必须修正的契约差异

下表“skill 依据”指 [mmd-sandbox.md](../platforms/mmd-sandbox.md) 的源码/实机记录。它们是截至该资料核对日期的证据，不代表本次重新上站测试。

| 项目 | 上游代码行为 | skill 依据与接入要求 |
|---|---|---|
| 消息状态 | `HudRuntime.syncStore` 要求 `payload.state` 非空；types 定义 `done/streaming` | §2.6.3、§3：消息载荷只有 `id/serverId/role/content`。按事件名产生本地状态，否则真实形状消息被全部忽略 |
| 编辑 ID | `mapMessage` 使用本地 `message.id`，`submitEditMessage` 将它传给 `sdk.message.edit`；模型缺 `serverId` | §4.3：编辑需要服务端 `serverId`，空值不可编辑。本地 id 跨重载变化，不能代替持久主键 |
| 切会话 | `syncStore` 只有 `payload.conversationId` 存在才更新；`setConversation` 本身不清消息 | §4.9：事件无已确认 ID 载荷，必须无条件使旧状态失效。Mock 另行直接清了 store，掩盖生产缺口 |
| 主题 | 依赖 `payload.theme` | §4.9：无载荷；读 root 的 `data-theme` 或直接继承 CSS token |
| 取消订阅 | `sdk.on` 类型返回函数，`dispose` 逐个调用 | §4.1 与本地契约 `sdk.onReturns`：返回 void/undefined，无 `off/once`。UI 清理与 SDK 单例分发分开 |
| ready | Mock 给晚注册者补发 ready，渲染器监听 ready 并立即 mount | §2.6：ready 最后到且不补发；顶层可能无 DOM。必须支持 mount/done 初始化和迟加载 |
| 舞台 | 生产入口顶层 `stage.open('full')`；类型允许 `stage.el()` 为 null | §2.6/§4.6：延后 DOM 操作，visible 判开关。上游 el 判空本身可保留作防御，不能据此判断可见 |
| 本地存档 | 内存 Map、硬限 10 key、`structuredClone`、remove 成功 | §4.5：宿主动态配额、JSON 可序列化、真实读写异常与已记录 remove 故障；Map 不证明服务端/跨设备持久化 |
| 导入格式 | 导出 `pageDepth/statusbar/beginning/regex_scripts` 四键，开场白为空 | §8/§9：沙盒独立正则包六键，必须补 `chatVersion:1`、`personality`；它也不是 v2 整卡 |
| 匹配式 | 导出裸占位符 | §7.1：新页接受裸字面量，不算平台故障；skill 交付统一 slash，属于格式约定 |
| 网络说明 | README 仍说 HTTPS 脚本需平台白名单 | §13：已记录 CSP 允许 HTTPS script，未发现该应用层白名单；fetch、外链 CSS/字体、作者 iframe 各有独立限制，不能一概当可用 |

主要源码：[sdk.ts](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/platform/sdk.ts)、[HudRuntime](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/hud/runtime.ts)、[Mock SDK](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/runtime/mockSdk.ts)、[Mock MMD](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/runtime/mockMmd.ts)、[Dragon Raja 映射](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/renderers/dragon-raja/dragonRajaContext.ts)。

### 本次本地复现

将上游纯 TS runtime 去除类型后执行，注册返回 undefined 的 SDK 替身，并输入 skill 已记录的消息/无载荷事件；未连接 MMD，未安装或运行资源播放器：

- `{id:'l1',serverId:'8014',role:'ai',content:'实际消息正文'}` 的 done 事件后，store 消息数为 **0**；控制组额外加 `state:'done'` 后为 **1**。
- 随后无载荷 `conversation:switch`，旧消息仍为 **1**。
- `dispose()` 抛出 **`TypeError: unsubscribe is not a function`**。
- 独立执行上游 Mock SDK，晚注册 ready 确实补发、on 确实返回函数，第 11 个存档 key 报 `RATE_LIMITED`，remove 成功。

这些结果证明 Mock 会掩盖上述合同差异；不声称是在真实新页观察到的运行结果。复现材料放在本轮工作记录，skill 不随附或重新分发上游源码。

## 3. 功能数不能照旧版继承

[Dragon Raja SUPPORTED](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/src/renderers/dragon-raja/dragonRajaContext.ts) 只有 `sendMessage`、`setInputText`、`submitEditMessage`、`exit` 四类动作；其余旧协议动作是不可用占位。页面中的模型、会话、人设等面板快照大量为空壳，这不能算真实接通。

skill 的旧版同层卡“61 项动作”属于另一个仓库与旧页桥接，**不适用于新页**。新页这份上游类型大致覆盖已收录的 SDK 方法名，问题主要是**行为契约不准**，并非简单再添几个方法就完整。平台状态变量的新资料也不能填成猜测的 SDK 签名。

## 4. 构建方法可以借鉴，产物不能照搬

[build-role-card-json.mjs](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/scripts/build-role-card-json.mjs) 将 bundle 切为字符串片段，对 `<` 和 `$` 编码，按转义后长度收缩到约 18000 字符，再用 script 拼接执行；它有重组验证和相同 build 防重复启动，方向正确。

但接入 skill 还要处理：

1. 改六键沙盒包，独立说明 v2 整卡和新建卡开关；总规则数连同作品其他规则一起检查 ≤130，上游此导出器未限制总条数。
2. 新页脚本本来就装卡抽取，不需要依赖 statusbar 占位链。需测试未命中规则仍加载、抽取顺序及实际载荷，不只执行最终替换出的 HTML。
3. 全局 `__MMD_HUD_JSON_STATE__` 中片段只按下标复用、未按 build 分桶；少一条新片段可能混到旧片段。加入构建隔离、完整性校验与失败可恢复状态。
4. `started` 标记不等于网页成功挂载。上游追加动态 script 后即标记，不证明 SDK/DOM 就绪、业务初始化成功或可重试。
5. 分片规则之间是数据装配，最后才执行 bundle；校验转义后的脚本、UTF-16 长度、缺片/混版、重复注入和与其他规则合包，不只测单条上限。

[verify-hud-json.mjs](https://github.com/Godcount10/new-mmd-hud/blob/cc6a126e61eefa4c57b2ae63a461b96f3bb9b17f/scripts/verify-hud-json.mjs) 验证了源码重组、语法和同 build 防重复，但没有模拟真实 SDK 的上述差异，也未执行实际网页/宿主握手，PASS 不等于可直接导入新卡运行。

Spine/Live2D 的“外链 script 注册模型数据、图片承载贴图”符合部分 CSP 通道，属于值得单独验证的资源技巧。不能因此断言全部模型格式、字体、WASM、worker 或默认 fetch 加载器可用；实例的原始资源还不完整包含在源码仓库。

## 5. skill 接入范围与证据边界

- 主入口按 `chatVersion` 分流，两种同层卡共用“独立界面”概念，各用不同运行合同。
- 新页新增网页制作、SDK 映射、消息/会话生命周期、数据权威、构建和验收指南；旧页基座与工具继续保留。
- SBK 继续负责新页状态栏/美化，不能把它描述为完整聊天同层基座。
- 本轮是**制作方法与路由接入**，未提供沙盒成品基座/专用构建器，未验证当前真站部署和跨设备恢复。
- 仓库未发现根级明确授权本项目源码的许可证；第三方依赖许可证不等于整个工程授权。本轮采用架构分析与自行编写的说明，不打包上游或模型资源。
