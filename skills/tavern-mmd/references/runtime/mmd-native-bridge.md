# 同层卡原生桥接与存档合同

仅旧聊天页。制作入口见 [same-layer-card.md](../creation/same-layer-card.md)。本页记录基座自己的合同，**不是 MMD 官方 SDK**。

## 1. 适配器层

`assets/same-layer-kit/native.js` 提供三个实现：

| 实现 | 行为 | 证据边界 |
|---|---|---|
| dom | 读原生消息与面板状态，执行固定上游已实现的 61 项动作；随卡自动启动 | 选择器来自已读源码，当前独立实现仍待真站验证 |
| provided | 包装宿主提供的 NativeBridge 实例；检查动作白名单与最新 capability | 与贪心鬼接口形状对接，完整第三方版本仍需项目联调 |
| mock | 本地消息与主/A/B 会话模拟 | 不调用 MMD，不产生真实模型费用 |

默认 DOM 实现内置 61 项动作，包括消息发送、模型组与 [其余原生功能组](mmd-action-modules.md)。发送保留现有原生草稿；显式 setInputText 会按作者请求改写草稿。模型模块见 [mmd-model-controls.md](mmd-model-controls.md)，全部动作接入状态见 [能力清单](mmd-native-capabilities.md)；只有定义的 6 项保持不可用，原生功能仍可通过返回入口使用。消息快照只传文字并限量展示，不将 AI 文本作为 HTML 执行。

提供上游 Bridge 时，宿主先负责创建、启动并维护其生命周期，然后设置 `window.__MMD_HUD_NATIVE_BRIDGE__` 为实例。基座不自行复制第三方源码，也不默认 destroy 外部所有者的对象。传工厂时必须在宿主先实例化；不要让 Frame 访问这个全局。

内置的 61 项原生动作已有参数、快照与结果投影，不需要作者另写 `projectResult`。`allowedActions` 可收窄内置 DOM 和外部桥接的动作白名单。若扩展清单之外的新动作，才需要补处理器、结果投影和测试；外部桥接的自定义动作继续支持 `projectResult(action, result)` 扩展口。投影必须保留动作所需的阶段（例如 confirmation-required）、目标标识和确认数据，只返回 UI 所需的 JSON，不转发凭据或完整宿主对象。作者 UI 收到待确认阶段时应展示确认交互，不能直接显示操作完成。按钮依据 capability，结果根据具体动作合同处理。已有 NativeBridge 的模型组由 provided-models.js 适配到同一 Frame 合同；默认内置 DOM 路线不需要额外实例。禁止只看到 NativeAction 类型名就宣布可用；上游所研究版本含尚未注册 handler 的动作。

## 2. 作用域解析

真实存档通过 Host-only 的 `window.__MMD_SAME_LAYER_SCOPE__` 函数，或启动配置的 `readScope`，取得：

```js
// 这是作者适配点。三个值必须由当前项目已验证的宿主读取逻辑获得。
// 不要直接复制虚构账号、固定 main 或 DOM 索引作为真实身份。
function readScope() {
  return { accountKey, roleId, conversationKey };
}
```

- `accountKey` 为宿主维护的非凭据隔离标识，不向 Frame 暴露账号资料。
- `roleId` 与 `conversationKey` 必须稳定且当前有效。临时会话也要有经验证的作用域；不以正负号简单判断是否有历史。
- 基座自动加入 `appId`；四个字段一起生成存档键。
- 默认最小 DOM 适配器不猜账号/会话。解析器缺失时，游戏保存明确停用，聊天仍可使用。
- 切换作用域会关闭旧端口、重建 Frame。每次存储操作在取得锁之后及落盘前重新检查作用域，旧任务不能写进新聊天。
- `appId` 跨 UI 版本保持稳定；不要把 buildId 塞进存档命名空间而使升级后找不到旧进度。

## 3. Host / Frame 通信

基座协议名为 `mmd-sl/1`，与上游 `mmd-hud-iframe` 协议不互换。

- Frame 使用 `sandbox="allow-scripts allow-downloads"`，不授予 allow-same-origin。该配置不放行 HTML 表单提交；发送按钮直接绑定 JS 点击事件，不能依赖 form submit。
- bootstrap 通过 iframe.name 传递 buildId、随机 nonce 与 parentOrigin。
- Host 只向自己创建的 iframe 交付 MessagePort；Frame 验证 source、origin、buildId、nonce 和唯一端口，然后移除全局 message listener。
- ready 之后只通过端口通信。切换 Frame 或会话生成新的 contextId；旧上下文请求与结果不采用。
- 请求仅限固定方法；不提供任意 URL、父页 eval、任意选择器点击或完整存储导出。

| 方法 | 用途 |
|---|---|
| snapshot | 请求刷新页面快照 |
| native.invoke | 执行适配器允许且当前可用的原生动作 |
| ui.native | 暂时隐藏 HUD，显示原生界面与返回入口 |
| game.load / game.action | 读取游戏；提交带 epoch、expectedRevision、唯一命令 ID 的动作 |
| game.export / game.import | 导出校验封套；经 UI 确认后恢复同作用域存档 |
| game.narrate | 为最新行动保留台账后提交一次原生叙述请求 |

模型动作另返回 data.phase（区分已观察选择与结果待确认），详见模型模块；发送成功返回 accepted；completed 与 persisted 为 unknown，不伪装成服务器回执。Frame 超时不自动重发。新玩法若需要正式接纳 AI 结果，应另做生成身份、完整流结束与事实校验；当前示例只显示原生消息，不让 AI 改写引擎。

## 4. 引擎与持久化

示例的 `core.js` 在 Host 运行纯规则引擎；Frame 只接收公共状态。具体项目也可以另行拆引擎模块，但保持唯一规则真值和保存后显示。

- 命令包含唯一 ID 与期望 revision，重复 ID 不重复结算，不同内容复用 ID 会被拒绝。
- 随机状态进入存档，重读不重新抽取结果；公共投影不暴露内部 rng。
- 状态、行动回执和叙述提交台账写在同一个 localStorage 封套，避免多键提交顺序撕裂。
- 按同一作用域使用 Web Locks；不支持安全写锁时明确报错，不降级成可能丢更新的写入。
- SHA-256 检查意外损坏，**不是防恶意篡改的签名**。导入还检查 schema、scope、字段和边界。
- 写入后立即回读确认；失败保留当前页面先前状态并显示错误，不能静默新开局。
- 示例有容量/回合限额，正式作品应按实际数据设计预算、归档与导出；不将该示例上限当平台上限。

### 迁移与读档

示例包含明确的 schema 1（gold）→ schema 2（coins）迁移。先验证旧封套与作用域，保存可定位旧版本备份，再写新封套并回读。未支持版本、坏档、作用域错误都停止，不扫描整个存储猜旧档。

导入前保留当前封套，恢复后生成新 epoch；原来的叙述台账合并保留，避免读旧档后忘记已经派发的请求。迟到结果不能跨 epoch 写回。备份只属于本作品明确的键；长期作品需提供玩家可理解的备份管理。

### 生成台账

`game.narrate` 先保存 unknown 记录，再尝试原生发送；确认原生动作触发后记录 accepted。两者都不代表 AI 完整回复已保存。重复点击同一行动的叙述按钮被拒绝；关闭页面、断线或失败不触发自动重发。

实际发出请求后，即便页面退出，也不能把它当作服务器取消。需要对账时返回原生消息记录；当前 DOM 方案没有伪造服务器消息号或完整 EOF。

## 5. 生命周期与版本

- 同 appId 重复启动复用实例；新 buildId 遇到活动实例时提示刷新，不直接拆掉正在运行的游戏。
- 隐藏后保留实例并显示返回入口；最终关闭清除 Frame、返回按钮、端口、计时器和监听器。
- 离开所属路由/角色后不在其他卡片上继续挂载；返回原卡可由文档级 supervisor 重新进入。
- 保存按每次行动同步确认，不依赖 beforeunload/pagehide 最后抢写。
- 新代码与存档 schema 分开升版。真实 MMD 的脚本去重、同步重建、嵌套 iframe 视口与 BFCache 仍需项目真机矩阵。

## 6. 扩展顺序

先完成需要的最小闭环，再增加原生面板镜像或更复杂玩法。新增每项能力都应说明：数据从哪来、何时可用、何时算成功、作用域切换怎么处理、失败后是否允许重试。

本地存档不自动跨设备。若希望迁移，使用同作用域导出导入；如果目标是官方跨设备保存，重新确认是否应选择新页与 sdk.save，不在旧页编造该能力。
