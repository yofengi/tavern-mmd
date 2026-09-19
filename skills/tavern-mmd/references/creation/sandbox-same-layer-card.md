# 沙盒同层卡：在新页舞台里运行自己的网页

适用 `/mmdsandbox`、`chatVersion:1`，用户希望自绘聊天页、全屏 HUD 或网页游戏。**这是新页的同层卡路线**，不是旧版 Frame/Host 桥接，也不是普通气泡状态栏。平台事实以 [新页规范](../platforms/mmd-sandbox.md) 为准；贪心鬼工程的借鉴范围与兼容问题见 [new-mmd-hud 审查](../runtime/new-mmd-hud-audit.md)。

## 1. 先分平台，再定界面

| 项目 | 旧版同层卡 | 沙盒同层卡 |
|---|---|---|
| 平台 | `/mmd`，`chatVersion:0` / 缺省 | `/mmdsandbox`，`chatVersion:1` |
| 制作指南 | [same-layer-card.md](same-layer-card.md) | 本文 |
| 作者页面运行位置 | 作者创建的独立 iframe | 平台已提供的跨源沙盒 iframe 内，`sdk.stage.el()` 的自有根节点 |
| 连接 | Host ↔ 原生 DOM Bridge ↔ Frame | 自有 UI ↔ SDK 适配层 ↔ 平台官方 SDK |
| 原生功能 | 旧版桥接能力表 | 新页 SDK 已确认能力；未开放的操作返回原生界面 |
| 独立正则包 | 4 键 | 6 键，包含 `chatVersion:1` 与 `personality` |
| 构建/审核 | `build_same_layer.py` / `review_same_layer.py` | 项目自己的网页构建与沙盒包装；`validate.py --platform mmdsandbox` + 新页全景仿真 |

用户已经指定平台时直接沿用。只说“同层卡”且无平台记录时问一次；背包、地图、存档、Vue，以及 HTML 的 `sandbox` 属性都不能代替平台选择。旧版已有卡不能靠补 `chatVersion:1` 原地升级。

在 main.md 记录：**目标平台、chatVersion、呈现形态、连接方式、状态权威、存档位置、验证层级**。沙盒同层卡的连接方式写“官方 SDK + 舞台”，不要沿用旧页“原生桥接 + Host 本地存档”的默认值。

选择呈现范围：

- 仅状态栏、换肤、抽屉：读 [SBK](../beautify/sandbox-kit.md)，不必重写聊天页。
- 自绘叙事区，仍使用原生顶栏和输入框：舞台 `content` 模式。
- 完整网页（自己的消息列表、输入框、导航）：舞台 `full` 模式；自带发送和“返回原生界面”，原生页保留“打开同层页”入口。

## 2. 网页源码与平台交付是两层

可以像普通网页一样开发 HTML/CSS/JS，或使用 Vue、Canvas 等。Vue 是可选渲染层，游戏引擎也是可选；聊天卡不强制带背包、战斗和模型播放器。

```text
本地 index.html / 开发入口（调试用）
                    ↓
生产入口 → SDK 适配层 → 事件/展示状态 → 页面组件
                    ↕                     ↕
             官方 sdk                 可选规则引擎
                    ↕
             MMD 宿主与服务

构建：生产 JS（经典 IIFE）+ 内联 CSS
      → 沙盒正则包的 <script>/<style>
      → 挂到 sdk.stage.el() 内作者自己的根节点
```

本地可用 Vite 热更新；线上不上传 `index.html` 来替换平台文档，不复制本地 Host，不 `document.write`，不清空平台 root/body。MMD 继续负责会话、模型请求、鉴权和系统弹窗；“接管界面”不等于拿到私有后端、宿主页 DOM 或完整历史接口。

项目可按以下职责拆分（小卡可合并文件）：

| 层 | 职责 |
|---|---|
| platform | 精确映射官方 SDK、事件与错误；Mock 单独实现，不扩张生产契约 |
| runtime/store | 消息投影、发送状态、会话失效、主题、订阅单例和清理 |
| renderer | DOM/Vue/Canvas 页面、输入、滚动、可访问性、深浅主题 |
| domain（可选） | 规则结算、合法动作、版本化存档，不依赖 Vue 或 DOM |
| build | 只打包选中模块；正则包装、长度预算、产物回读、来源清单 |

**不要在新页里再嵌套作者 iframe。** 平台已有隔离容器，作者 iframe 还受到净化与 `frame-src 'none'` 限制。旧版 `host.js/native.js` 和 MessagePort 协议不能直接搬来。

## 3. 先写功能范围，防止画出空按钮

| 页面功能 | 已确认接法 / 边界 |
|---|---|
| 玩家点击发送 | 点击当帧调用 `sdk.message.send(text)`，捕获失败；不能先 `await` 再发送 |
| 行动选项填草稿 | `sdk.input.set(text)` 写的是**原生输入框**；自有输入框需明确做受控同步或只写自己的草稿，不能误以为 SDK 会更新 Vue 文本框 |
| 流式与完整正文 | stream 的 content 是与气泡同步的**已揭示累计文字**，不是差量或提前获取的完整回复；最终正文读 done |
| 编辑消息 | 有 `serverId` 才能调用 `sdk.message.edit(serverId,text)`；本地 `id` 不能当编辑参数 |
| 角色/用户头像名称 | `role.get()` / `user.get()` 仅返回平台文档列出的字段 |
| 返回原生页 | 作者自己的关闭函数调用 `stage.close()` 并同步清理/暂停；若改过 composer，恢复本实例修改的状态 |
| 模型列表/切模型、会话列表/主动切会话、删除/回溯/重生成/停止生成、原生设置 | 当前已收录 SDK **没有这些公开调用契约**；保留原生入口或明确不可用，不沿用旧版 61 项桥接能力，不猜 `sdk.models` / `sdk.conversation` / `sdk.message.stop` 等 |

收到 `conversation:switch` 是**知道会话换了**，并不表示能调用 SDK 主动切会话。只有发现并验证了新契约后才能增加相应按钮；不可用功能不能用本地假成功代替。

## 4. 事件转为自己的页面状态

### 消息模型

已确认的消息载荷是 `{id, serverId, role, content}`；没有上游 Mock 使用的 `state`、`generated`、`mounted`。显示状态由**事件名**推导，放在自己 store 中，不能反过来要求平台载荷带它。

| 事件 | 自有页面的处理 |
|---|---|
| `message:new` | 按 id 创建/合并消息元数据；空气泡可显示等待，不结算剧情 |
| `message:mount` | 首屏挂载机会、气泡按钮绑定；不把 mount 当生成完成，也不以 DOM 占位补正文 |
| `message:stream` | 将本条正文**替换**为当前已揭示累计 `content`，标为 streaming；节流到绘制帧，勿重复拼接，也不假定能抢先读取完整回复 |
| `message:done` | 按 id 更新正文/`serverId` 并标为 done；历史补发也会来，不能每次都发奖励、写档或再次发送 |
| `message:unmount` | 不等于消息被删除；当前契约无可依赖的消息 id 载荷，不能凭它删除聊天记录 |
| `conversation:switch` | 无需载荷也立即清空消息投影/草稿/待发送和会话临时状态，取消旧异步任务与待写档 |
| `theme:change` | 不依赖 `payload.theme`；样式继承 token，必要时读 `[data-chat="root"]` 的 `data-theme` |

本轮页面使用 `id` 去重；持久消息关联使用 `serverId`，`null` 不可编辑/做永久主键。同一消息重载后本地 id 会改变。`role` 的 AI 值是 `ai`；若组件使用 `assistant`，在适配层转换。

**消息 store 是已收到事件的投影，不是服务器完整历史。** SDK 没有已确认的历史分页/全量查询接口，也不能保证编辑、删除、回溯的完整同步。若作品必须精确管理全历史，先验证该能力；现阶段保留原生历史入口，不能宣称重写了全部聊天管理。

AI 正文视为数据。纯文本用 `textContent` / 框架转义插值；需 Markdown 时在自己的渲染链做净化。不要把 `msg.content` 当可信 HTML 直接交给 `innerHTML` / `v-html`，更不能执行其中脚本。

### 发送与状态结算

- 自有发送按钮在用户点击当帧调用 SDK；用 pending 哨兵防连点，`BUSY` / 限频 / 网络失败保留草稿，不自动重发。
- `send` 返回 `Promise<void>`，不返回消息快照；请求返回、AI 完成和持久化完成分别处理，不用 Promise 成功宣称三者全完成。
- 生成状态来自消息事件。等待超时转为“结果待确认”，提供返回原生页核对，不能当成服务端已取消。
- `message:done` 有历史补发语义。解析状态可重复执行，奖励/剧情推进必须另有幂等判据；纯聊天不需要规则结算。

## 5. 启动、舞台和退出

1. 脚本体只建立单例、状态和一次性 SDK 事件分发器。作者脚本可能早于 DOM，不在顶层开舞台或挂网页。
2. 在 `message:mount` / `message:done` 的可重入初始化中确认舞台节点、创建/复用自有根，再打开选定模式。2026-08-26 历史探针的 ready 最后到且不补发，当前版本待复验；兼容实现不把它当唯一首屏入口，迟加载也保留幂等初始化与用户“打开”入口。
3. 区分 `ensureMounted()` 和“用户愿意显示”。初次打开后，后续消息只更新状态，不能每次 done 都 `stage.open()`，把用户刚关闭的舞台抢回来。
4. `stage.visible()` 才是开关状态。`stage.el()` 关闭时仍有节点；平台不清空内部 DOM，重新打开复用它。所有内容挂在本作品根节点，避免误删其他功能。
5. 作者调用 `stage.close()` **不会**触发 `stage:close`；自己的关闭路径和平台关闭事件要共用暂停/状态更新逻辑。用户返回时平台可能先关舞台，不能只监听 `back`。
6. `conversation:switch` 不重跑脚本；增加本地 epoch，取消 debounce 写档、计时器和请求结果落地，清空旧会话投影。不依赖 `payload.conversationId`，也不伪造可跨重载使用的会话 ID。重开入口按新会话重新初始化；默认不从旧 done 回调自动重开。
7. `dispose` 清理作者的 observer、DOM 监听、RAF、框架实例及 WebGL/音频资源。SDK 的 `on` 无已确认的退订返回值，不调用其返回值；无 `off/once`。预览重注入应复用单一订阅分发器，替换当前逻辑，不能只销毁 UI 又追加一套 SDK 订阅。

epoch 能隔离作者发起的旧异步任务，**不能凭空给平台无会话标识的迟到事件补身份**。切会话期间旧流式事件是否被平台拦截、历史补发范围与顺序，仍按项目实站边界探针验证。

舞台里的聊天列表由作者自己滚动、分页和渲染；它位于平台虚拟化列表之外。这里可以画完整聊天 UI，只是不能期待平台把原生消息列表自动搬进舞台。

与 SBK 组合时只有一个模块负责舞台根和开关；复用所需主题/协议模块，不同时启动两个全屏应用争抢舞台。

原生弹窗换肤不需要把业务搬入舞台。21 个开放 `[data-host]` 根走静态 `<style>` 抽取过滤，和 iframe 内 UI 的 CSS 分开；不是跨源 DOM 接口。summary 主根本体、根内编辑/锚点与树外 summary-confirm 的范围见 [宿主换肤指南](../beautify/sandbox-host-styles.md)，未知内部结构不按 Mock 编造。与 SBK 组合可选制作期 `hostStyles`，运行时阅读主题停用不撤销宿主皮肤。

## 6. 写卡内容与存档

先按 [平台 §14](../platforms/mmd-sandbox.md#14-平台状态变量子系统sdkvars--varschange--abc_vars) 确定每个字段的权威来源：

- AI 叙事状态：写进人设/世界书的输出协议，从 done 正文标记解析；渲染代码不会让模型自动知道协议。做整卡时放固定世界书条目。
- 程序游戏状态：由可选引擎结算，AI 只叙述已确认事实；需要模型知情时用已确认的消息通道同步，`sdk.save` 不自动进入上下文，也不保证跟随回溯。
- 平台状态变量：业务存在，但 `sdk.vars` / `vars:change` 运行签名仍未补齐；不编造、不把 `<abc_vars>` 当自定义状态协议，也不写成平台不支持。

持久进度用 `sdk.save` 的版本化对象；当前会话展示状态用内存/`sdk.cache`，单卡本地偏好可用 localStorage。不能拿上游内存 Map 存档声称跨设备成功。

`save.get/keys` 用 `try/catch`，写入捕获 Promise 错误；瘦预览同步读档失败时保留可看 UI，并标明不能保存。初始化读档可尝试，但失败不是空档，不自动覆盖成新进度；`ready` 可作为一次重试信号，迟加载时还须保留用户主动重试。切会话先取消旧写档，再在宿主存档就绪后读取。

key ≤64 且不含冒号；文档约定 10 key，历史沙盒源码未见本地校验不代表服务端无限额，合并并限频保存。`save.remove` 在 2026-08-30 有故障记录，目标版本待复验；若复现才按平台 §4.5 用 set(key,null) 逻辑清档，说明 key 未释放。没有可靠会话标识时不能声称已实现跨设备会话命名空间；真实保存作用域、切会话读写和重载恢复单独验收。游客不保证跨设备持久化。

## 7. 打包成沙盒卡

开发网页和本地模拟器不直接作为交付物。生产包只含本卡 UI、适配器、所需库与内联 CSS：

1. 构建经典 IIFE，不保留 `import` / `export`、开发服务器 URL 或 Node 全局；平台的 `type="module"` 按经典脚本执行。
2. 小包直接放 script 规则；大包按完整可执行包装分片，计入 JSON/JS 字符串转义后的长度。分片需要独立 app/build 命名空间、预期数量和完整性验证，缺片、混版不启动。
3. 脚本在装卡时按规则抽取，**无需匹配命中**。使用互不重复、不会匹配空串的专用标记即可；不必用占位链把整个大包展开放进 statusbar，避免正文替换预算与标记残留。仅需要可见入口的那条匹配 statusbar 短标记。
4. 包装脚本中的 `</script>` 与替换符必须安全编码；全部分片按规则顺序回读、比较原始 bundle，检查脚本语法和重复启动；不只检查单片长度。不要照搬旧页 Base64 启动器或上游未修正的四键导出器。
5. 独立正则 JSON **恰好六键**：`chatVersion:1`、`pageDepth:2`、`statusbar`、`beginning`、`personality`、`regex_scripts`。每条恰好四键 `id/scriptName/findRegex/replaceString`，负数 id、统一 slash 匹配式。保守交付 ≤130 条、每条替换 ≤20000、规则名 ≤20、匹配式 ≤1000；字段其余限额见平台 §8。
6. 六键包是正则导入文件，不是完整角色卡。整卡另按 [v2 输出](../output/card-json.md) 打包，默认用 PNG 导入；JSON 整卡直接导入的记录冲突见该文首，复验前作源码/备份。人设、世界书、开场白按选定路线放入。独立包 `personality` 字段不替代创卡页手工粘贴人设的交付说明。
7. 交付明确写：**新建卡；首次保存前选「使用新版」聊天页；首次保存后不可改**。公开卡另满足固定传输和开场白门槛，不能照搬上游空 `beginning` 当完整成品。

资源边界见平台 §13：CSS 内联，字体优先系统栈，图片使用已允许来源。2026-08 记录的 CSP 允许 HTTPS 经典脚本且调用未 await；与后续文档顺序/白名单要求有差异，须按目标部署验证、固定版本并自行处理加载依赖与失败。外部 fetch/XHR、样式表、字体、作者 iframe 仍按各自通道验证。Spine/Live2D 可选，不假定默认网络加载器可用；上游“脚本注册数据 + 图片贴图”方法逐种验证资源及授权，不默认打进聊天卡。

## 8. 制作与验收顺序

1. 定平台、呈现范围、可用功能和数据权威；把原生保留功能写进设计。
2. 开发自有网页，生产适配器按平台文档写；本地 Mock 特意覆盖无 `state`、无事件载荷、无退订、瘦预览失败等真实边界。
3. 先通首屏、发送、累计流式、返回原生与重开，再做剧情面板/可选玩法；记录项目级状态协议与存档版本。
4. 打包后测试**原样交付载荷**。不要用 Vite 页面正常替代导入包验收。

从 skill 根目录运行（路径换成本项目交付包）：

```sh
python scripts/validate.py output/card-sandbox.json --platform mmdsandbox
python scripts/build-preview.py output/card-sandbox.json --platform mmdsandbox --mode panorama --sandbox-profile chat -o output/preview-chat.html
python scripts/build-preview.py output/card-sandbox.json --platform mmdsandbox --mode panorama --sandbox-profile thin-preview -o output/preview-thin.html
```

在本地浏览器验证两个 profile、窄屏和桌面：冷启动、迟加载、重复注入、历史 done 补发、流式替换、连续点击、失败保稿、无载荷切会话、旧保存计时器、主题切换、关闭/重开、dispose。另查段落滚动、输入法、键盘遮挡和原生返回入口。

预览调试入口只属于本地，`control` 指 `window.__MMD_SANDBOX_SIM__.control`：`control.stageMode(mode)` 接受 content/full/closed，统一 data-stage/hidden/SDK visible，不清作者子树；content 对齐消息区并随视口更新，full 的 fixed/inset 交给 CSS。测试标记节点跨关闭/重开/切会话仍存在，再确认作品自行清理会话状态。`control.setBusy(true)` 注入忙态，stream 开始也忙、done 结束流式忙态；`setBusy(false)` 只释放手动忙态，不中止 stream。BUSY 时草稿不清、解除后不自动重发。`sdk.message.send()` 省略文本取原生草稿，空消息 INVALID_ARGS，成功返回 Promise<void>；本地只追加用户消息，不调用真实 AI。

使用宿主皮肤时，chat 全景另验 iframe 外 21 根索引、静态抽取诊断和已观察夹具；thin 不模拟宿主。summary-confirm 的未知内部结构只能看占位标注。预览接受/拒绝的 CSS 只是保守子集，不能当作平台过滤器完全一致；动态转发、保存和真实确认行为单列未验项。

`build-preview.py` 是通用新页仿真，不自动提供此作品的全套同层业务测试；`review_same_layer.py` / `verify_same_layer.py` 目前仍是旧页专用。按 [检查清单](../quality/checklist.md) 增补项目测试；本地 PASS 不等于真实 MMD、跨设备存档或实体手机已通过。

当前 skill 提供这套制作与迁移方法，**尚无沙盒专用同层成品基座或一键构建器**。`assets/sandbox-kit` 是美化基座，`assets/same-layer-kit` 是旧页基座，两者不能冒充沙盒同层成品。需要具体作品时按以上分层实现，并完成相应验收。
