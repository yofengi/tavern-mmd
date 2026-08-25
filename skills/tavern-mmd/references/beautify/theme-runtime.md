# 当前 MMD 运行时主题协议

定位：本文件是**当前 MMD（魅魔岛 / sexyai.top）全局运行时主题包的权威协议**。凡需要 `day / night / native` 三态、玩家微调、持久偏好或路由重入的全局美化，都必须先读本文件，再读 `global-css.md`、`style-system.md` 与 `../platforms/mmd.md`。

本协议的生命周期、租约、恢复与存储设计是在仓库既有社区快照提供架构启发后，由 tavern-mmd 面向当前 MMD 重新设计与实现的；不复制旧运行时代码。所参考快照由用户提供，作者、原 URL 与许可证未完整记录，仅作兼容研究参考，不据此宣称原创。选择器与视觉细节若受第三方案例启发，必须在资产 README 单独标明来源，也不能把浏览器沙箱结果写成 MMD 实机结论。

> **适用范围只有当前 MMD（`/mmd`）。** 本协议是**为当前 MMD 的约束量身设计的**，不是通用主题框架：owner/version 租约、route supervisor、MutationObserver 哨兵、`html` / `body` 根节点属性、localStorage 偏好候选，这些机制存在的理由全部是「当前 MMD 没有官方主题接口、平台 class 名会变、动态路由会换掉聊天根节点」。
>
> - **本地 SillyTavern（`/st`）**：走其原生主题或自定义 CSS，不用本协议。
> - **MMD沙盒模式（`/mmdsandbox`）：本协议不适用。** 那里平台自带主题接口 —— `[data-chat="root"]` 上有 `data-theme="light|dark"`、10 个 `--chat-*` 变量、以及 `theme:change` 事件；换肤只是在 `[data-chat="root"]` 上改变量，不需要租约与哨兵。而且本协议依赖的两样东西在沙盒模式是**被禁的**：`body{}` / `html{}` / `:root{}` 全局选择器（官方校验 WARN，须改写成 `[data-chat="root"]`），以及 `img onerror` 点火器（官方明令禁止）。沙盒模式的换肤做法见 `global-css.md`「沙盒模式换肤」与 `../platforms/mmd-sandbox.md` §6。
>
> 除非测试记录明确写明日期、版本和路径，本文件不宣称运行时资产已经通过 MMD 实机验证。

## 1. 先选静态换肤还是运行时主题包

| 需求 | 静态换肤 | 运行时主题包 |
|---|---|---|
| 只有一套固定外观 | 适合 | 可用但通常过重 |
| `day / night / native` 三态 | 不适合 | 必选 |
| 玩家按主题微调并重置 | 不适合 | 必选 |
| 跨路由离开、返回后重建 | 可做简单激活 | 必须完整实现 |
| 需要 `destroy()` 卸载 | 可用删除根属性处理 | 必须完整实现 |
| 需要持久偏好 | 不建议 | 候选能力，须实机验证 |

**静态换肤**只注入一份公共 CSS 和一组固定 token，通常由一条规则激活；它可以有“启用 / 停用”，但不伪装成运行时主题管理器。

**运行时主题包**是一个有所有者、有版本、有生命周期的全局单例。默认只要用户要求日夜切换、`native`、设置面板、玩家微调或记住选择，就必须选本档。

## 2. 核心状态与不可变约束

运行时至少公开三种模式：

- `day`：启用日间 token。
- `night`：启用夜间 token。
- `native`：停用本运行时的主题覆盖，并恢复本运行时记录过的可逆 property delta。

另有一个不是主题模式的操作：

- `destroy`：彻底卸载当前 owner 的运行时实例、资源、监听、面板与租约。除非用户明确执行“重置偏好”，`destroy` 不默认删除已验证合法的偏好记录。

必须同时满足以下不变量：

1. 同一文档最多一个运行时 owner 持有主题租约。
2. 同一 owner/version 的 bootstrap、enter、start 和 reenter 均幂等。
3. 公共选择器只写一份；日夜差异只通过根属性和 token 切换，不复制两套选择器。
4. `native` 与 `destroy` 都只能恢复当前运行时实际拥有并记录的变更，不能宣称把页面恢复到平台初始态。
5. 所有 DOM ID、CSS 类、根属性、自定义属性、全局变量、事件名、存储键和 head 资源必须使用同一个自有命名空间。
6. 只有一个可断开的 MutationObserver；插件不得各建常驻 observer。
7. 文本规范化默认关闭，并与主题切换、清污和 native 恢复解耦。

## 3. 命名空间与 owner/version 租约

每个 bundle 选择稳定前缀，例如 `<ns>`，并在 README 列出完整映射。以下名称只是协议占位，不要求逐字使用：

```text
owner:       <ns>.theme-runtime
version:     1.0.0
window:      window.__<ns>ThemeRuntime
lease:       window.__<ns>ThemeLease
root attr:   data-<ns>-theme="day|night"
style id:    <ns>-theme-style
panel id:    <ns>-theme-panel
storage key: <ns>.theme.preferences
```

禁止使用 `theme-btn`、`active-theme`、`dark-mode`、`style1` 这类无前缀通用名。版本使用可比较的明确版本号；不得用“最新版”“final2”代替。

### 3.1 租约记录

租约至少包含：

```js
{
  owner: '<稳定 bundle id>',
  version: '<明确版本>',
  instance: '<公开生命周期 API 引用>',
  acquiredAt: '<诊断时间戳，可选>'
}
```

bootstrap 的处置顺序：

1. **无租约**：创建实例并取得租约。
2. **同 owner、同 version**：复用现有实例，调用 `reenter()`；不得重复注入资源。
3. **同 owner、不同 version**：先调用旧实例的 `destroy({reason:'upgrade'})`，确认资源释放后再迁移偏好并取得新租约。
4. **不同 owner**：默认中止第二份运行时并输出可诊断状态；不得静默覆盖、删对方节点或并存两套 observer。只有对方租约明确暴露标准 `destroy()` 且产品策略允许接管时，才可先卸载后取得租约。

释放租约时必须核对 `lease.owner` 和 `lease.instance` 仍属于自己，避免旧实例误删新实例租约。

## 4. 生命周期状态机

标准 API 为 `bootstrap / enter / leave / start / stop / destroy / reenter`。实现可以增加方法，但不得削弱这些语义。

| 方法 | 职责 | 幂等要求 |
|---|---|---|
| `bootstrap()` | 取得租约；校验/迁移偏好；安装一个 route supervisor；若已在目标路由则 `enter()` | 重复调用只复用实例 |
| `enter()` | 确认目标路由；创建或复用 head 单例资源、light DOM 根状态和运行时面板；应用当前合法模式；随后 `start()` | 已进入时不重复建资源 |
| `start()` | 连接唯一 observer，注册当前路由所需监听，启动已启用插件 | 已运行时无操作 |
| `stop()` | 断开 observer，停止插件，清计时器和路由内监听；保留租约、偏好和可复用资源记录 | 已停止时无操作 |
| `leave()` | `stop()`；恢复本运行时 property delta；移除路由内面板和根主题属性；保留 route supervisor 以等待返回 | 离开多次结果一致 |
| `reenter()` | 对 SPA 重绘或回到聊天路由执行“校正后 enter”；复用同一租约和 head 资源 | 不增加资源计数 |
| `destroy()` | `leave()`；移除 owner 的全部 head 资源、全局 API、route supervisor 和租约；清空插件注册 | 多次调用不抛错 |

### 4.1 route supervisor

当前 MMD 是动态页面，不能只在首次脚本执行时判断一次 URL。route supervisor 至少监听适用的 `hashchange`、`popstate`、`pageshow`、`pagehide` 或等价路由信号，并以节流后的单一 `checkRoute()` 决定：

- 进入聊天目标路由：`reenter()`。
- 离开目标路由：`leave()`。
- URL 未变但页面根节点被整页替换：检测 UI host/root 失联，调用 `ensureMounted()` 把同一 host 挂到当前 `body` 后 `reenter()`。
- `pagehide`：先取消已排队的 route timer，再进入 suspended/pageHidden 状态并 `leave()`；任何 reconcile/reenter 都不得绕过门闩。
- `pageshow`：清除门闩后才允许重新排队 reconcile。

route supervisor 属于全局运行时，不得由每条 AI 消息重复创建。`leave()` 后它可继续存在；只有 `destroy()` 才移除。

## 5. head 资源必须是单例

公共 CSS、可选字体链接、运行时元数据等统一放在 `document.head`，每类资源一个带命名空间的稳定 ID。

创建规则：

1. 先按 ID 查找。
2. 节点属于同 owner/version 时复用，不 append 第二份。
3. 同 owner 但 version 较低的既有节点由升级流程替换。
4. ID 冲突但 owner 不同则中止并报告，禁止覆写未知资源。
5. `leave()` 可保留无激活根属性的公共 CSS；`destroy()` 必须删除当前 owner 的全部 head 资源。

测试时必须统计资源节点数，重复 bootstrap、动态新增 AI 消息和三轮切换后仍应各为 1。

## 6. 一个 observer 与可注销插件

运行时只创建一个 MutationObserver，由 supervisor 把批次分发给插件。推荐插件接口：

```js
const unregister = runtime.registerPlugin({
  id: '<ns>.cleanup',
  start(context) {},
  onMutations(records, context) {},
  stop(context) {},
  destroy(context) {}
});
```

约束：

- `registerPlugin()` 必须去重；同 ID 注册同一实例是幂等操作，同 ID 替换为不同实例时必须先 teardown 旧实例再保存新实例。
- 返回的 `unregister()` 必须立即停止插件并释放其监听、计时器和缓存；teardown 对可用方法按 `stop()` 后 `destroy()` 调用，每一步异常隔离。
- 已显式 unregister 或因同 ID 被替换的实例必须先从注册表删除，最终 runtime `destroy()` 不得再次 teardown 它。
- 插件不得自行创建常驻 MutationObserver；确有短时 observer 的特殊组件须写明时限并在同一任务内断开，不能成为第二个全局监听器。
- observer 回调只收集目标并批处理，不在每个 mutation 上全量扫描 `document.body`。
- `stop()` 先断 observer 再恢复 DOM，避免恢复动作触发自身循环；完成后仅在 `start()` 重连。
- 一个插件异常不得阻断其他插件和 `destroy()`，但必须留下可查询的诊断状态。

## 7. 公共 CSS、运行时 token 与选择器

主题 CSS 分三层：

1. **公共选择器层**：只写一次 MMD 选择器，值全部引用运行时 token。
2. **模式 token 层**：`day` 与 `night` 各定义一组成对 token。
3. **玩家覆盖层**：只覆盖当前模式的运行时 token，不复制选择器，也不改写 preset。

根状态必须落在 **light DOM** 的平台可达根节点上，例如 `html` 或 `body` 的 `data-<ns>-theme` 属性。样式以该根属性为作用域：

```css
:root[data-<ns>-theme="day"],
body[data-<ns>-theme="day"] {
  --<ns>-bg: ...;
  --<ns>-text: ...;
}

[data-<ns>-theme] .content.left {
  background: var(--<ns>-surface) !important;
  color: var(--<ns>-text) !important;
}
```

不得把主题状态只放进 Shadow DOM。Shadow DOM 可以隔离设置面板，但隔离边界内的变量和属性无法直接驱动平台 light DOM；面板动作最终必须调用运行时 API，修改 light DOM 根属性或变量。

`native` 时移除本 owner 的根主题属性和玩家覆盖，不保留一个伪造的 `data-theme="native"` 去压平台样式；运行时面板可继续存在，以便切回 day/night。

## 8. 制作期 token 到运行时 token

`style-system.md` 的规范 token 是**制作期中间层**，不能把 `--bg`、`--text` 等无前缀变量直接泄漏到全局页面。编译/组装时映射为 bundle 自有运行时 token：

| 制作期规范 token | 运行时槽位示例 |
|---|---|
| `--bg` | `--<ns>-bg` |
| `--surface` / `--surface-2` | `--<ns>-surface` / `--<ns>-surface-2` |
| `--border` | `--<ns>-border` |
| `--text` / `--text-2` / `--text-3` | `--<ns>-text` / `--<ns>-text-2` / `--<ns>-text-3` |
| `--accent` / `--accent-2` | `--<ns>-accent` / `--<ns>-accent-2` |
| `--success` / `--warning` / `--danger` | 同语义的 `<ns>` 前缀槽位 |
| `--radius` / `--shadow` / `--icon-filter` | 同语义的 `<ns>` 前缀槽位 |

已有 `--lb/...`、`--bg/--bg2/...`、`--ac/--cb/...` 三套方言只能通过明确 adapter 兼容旧组件；新产物不得继续扩散这些无统一前缀的全局变量。

## 9. 偏好存储 schema、验证与迁移

### 9.1 候选 schema

存储值使用 JSON 对象，不保存可执行代码或整段 CSS。最低 schema：

```json
{
  "schema": 2,
  "mode": "day",
  "normalizeQuotes": false,
  "overrides": {
    "day": {},
    "night": {}
  }
}
```

preset 默认值只存在于源码，不写入偏好。effective theme 每次按“当前版本 `DEFAULTS[mode]` + 合法 `overrides[mode]`”合成，因此升级后的新默认能作用到玩家从未修改的字段。玩家微调只写入 `overrides.day` 或 `overrides.night`，写回默认值时删除对应 override，**不得回写 preset**；“重置当前主题”删除当前 `overrides[mode]`；“全部恢复默认”清空两套 overrides，但保留当前 `mode` 和 `normalizeQuotes`，除非产品另有明确且已文档化的“重置全部偏好”动作。

### 9.2 读取验证

读取 localStorage 时必须：

1. `try/catch` 包住存取和 `JSON.parse`。
2. 检查值为普通对象，`schema` 为支持的整数。
3. `mode` 只接受 `day/night/native`。
4. overrides 只接受白名单 token；拒绝 `__proto__`、`constructor`、未知键和超长值。
5. 颜色、长度、透明度等按 token 类型验证或夹取；禁止把任意字符串拼进 `<style>`。
6. 任一字段非法时使用逐字段默认值，不让 bootstrap 失败；保留诊断原因。
7. 迁移成功后写回新 schema；无迁移路径的未来版本只读默认值，不破坏原值。

### 9.3 迁移

每次 schema 升级提供纯数据迁移函数，例如 `v1 -> v2`，并测试：旧值、部分缺字段、未知未来版本、截断 JSON、`null`、数组和恶意键。迁移不得依赖页面 DOM。若 v1 保存的是完整 day/night theme，迁移器必须在源码中固定该版本发布时的 legacy defaults，只把合法且与对应旧默认不同的字段迁成 override；不得拿当前新默认比较，也不得把旧对象全部复制到 overrides，否则会钉住玩家从未修改的旧默认。迁移成功后写回 schema-2 键，旧键仅作为兼容读取来源。

### 9.4 localStorage 结论边界

`localStorage` 只能视为“**全局偏好候选**”。浏览器标准中的 origin 范围不能替代 MMD iframe、WebView、账号、角色卡与路由的实机结论。历史状态栏记录曾写到跨气泡读取为 `NULL`，但未附完整日期、客户端/版本、frame/路由环境或可复现探针代码；该记录必须复验，不能直接外推成运行时主题一定可用或一定不可用，也不能用来定义 runtime 生命周期。

因此交付时必须写“待当前 MMD 实机矩阵验证”，在验证完成前：

- 不承诺跨会话、跨角色卡或跨设备保存。
- 存储失败时当前页面内切换仍须可用。
- 不用 localStorage 承担 DOM 恢复或 owner 租约；租约只存在于当前文档运行时。

## 10. `native` 不等于 pristine

`native` 的严格定义是：**关闭并撤销本 owner 可证明拥有的主题变更**。它不等于“平台从未被任何脚本修改过”的 pristine 状态，原因包括：

- 平台自身主题或路由在运行期间可能改变 DOM。
- 其他资产可能已修改同一属性。
- 早先版本的清污脚本可能删除过类、内联属性或文本，且没有 delta。
- 文本规范化属于不可逆内容改写。

UI 文案应使用“原生”或“停用本主题”，不得写“完全恢复初始页面”。测试报告要分别记录 native restore 和 full destroy，不能把两者合并成一个勾选项。

## 11. 文本规范化必须独立 opt-in

引号修复、全半角替换、空白折叠等任何 text node 改写都不是主题换肤。新运行时默认不注册此类插件；只有用户明确选择后才启用，并在 UI/README 标注：

- 会修改已经渲染的正文文本。
- native、leave 或 destroy 不保证恢复旧文本。
- 不得扫描 `script/style/textarea/input/code/pre` 等内容节点。
- 不得借“清污”名义默认开启。

若业务要求可逆，必须逐节点保存原文并处理后续平台改写冲突；做不到就明确标为不可逆，不得声称 native 可恢复。

## 12. 增量清污与 property delta

新运行时禁止旧式“每次 mutation 全量扫描 body，再删除整个 style/class”的清污方式。允许的流程：

1. `enter()` 做一次有界初始扫描，仅覆盖已知目标容器。
2. observer 只处理 `addedNodes` 与白名单属性变化，批次去重后增量清理。
3. 每次实际删除污染 style property 时，把该次 value 与 priority 覆盖写入 delta；每次实际删除污染 `color` attribute 时同样更新为该次值。平台连续写 `#0d0e0f`、再写 `#101113` 时，restore 的候选必须是 `#101113`，不是第一次值。
4. 清污运行时写入是“删除 property/attribute/class”；恢复仅在对应槽位仍为空/仍保持运行时写入态时回填最后候选。若平台后来写入合法非污染值，则不得覆盖该值。
5. CSS property 逐项 `setProperty/removeProperty`，不得删除整个 `style` 属性。
6. class 逐 token 记录，禁止覆盖整个 `className`；语义类（例如橙色标记）不得被误当成组件 skip boundary，否则其失效时无法增量移除。
7. 用可枚举的 `Map<Element, Delta>` 或 WeakMap + touched 集合保存 delta；节点断开后及时移出集合。
8. cycle、native restore 和插件 teardown 写 DOM 前执行 `takeRecords()` 并断开唯一 observer，写完再按运行态 reobserve；自身写入不得进入下一批平台 mutation。
9. 切到 `native`、`leave()` 和 `destroy()` 都要走同一恢复函数；leave/destroy 已 stop 时保持 observer 断开。

清污插件只在 day/night 需要时工作；native 下应停止写入。无法记录并恢复的清理必须改成独立、显式、不可逆插件，不得混入基础主题。

## 13. 当前 MMD 的 script 去重与 per-message 边界

当前 MMD 已实测：同段 `<script>` 会去重，且 `<script>` 不能作为 per-message 自定位渲染器。对全局主题和消息组件要严格分层：

- **全局运行时**：可以用一次性 `<script>` 或点火器 bootstrap 全局 owner；依靠 route supervisor 管理重入，不依靠每条消息重复执行同一 script。
- **per-message 状态栏**：仍使用 `img onerror` 在每条消息定位和渲染；不得把全局主题 observer、面板或 head CSS 各复制一份。
- **消息触发全局重入**：若确有需要，per-message 点火器只能调用现有 `window` API 的 `reenter()`，取得/复用租约后立即自毁；不能重新声明整套运行时。
- **去重测试**：连续新增多条 AI 消息后，lease、observer、route supervisor、面板和每个 head 资源计数仍为 1；per-message 状态栏数量则按消息数增长。

## 14. 设置面板、a11y 与移动端

优先复用运行时自带面板，不另造一套悬浮球、侧栏 observer 或存储引擎。面板可以用 Shadow DOM 隔离自身 CSS，但动作必须调用 light DOM 运行时 API。

最低要求：

- `day/night/native` 使用真实 button 或 radio/segmented control 语义；用 `aria-pressed` 或 checked 状态同步当前模式。
- 所有控件有可读名称；纯图标按钮提供 `aria-label` 和 tooltip。
- 键盘可用：Tab 顺序合理，Enter/Space 激活，Escape 关闭非模态抽屉；不无故困住焦点。
- 焦点可见，对比度符合正文 4.5:1；day/night 两套分别测。
- 触控目标建议至少 44 x 44 CSS px，面板不遮发送按钮和输入框。
- 使用 `env(safe-area-inset-*)` 处理刘海与底部安全区。
- 监听 `visualViewport` 或等价可用信号处理软键盘；键盘弹出时面板可滚动、可关闭，不被压到视口外。
- 窄屏和横屏使用受约束宽高，例如 `max-width`、`max-height`、`overflow:auto`；最长中文标签不溢出。
- 点击入口和面板内部必须 `stopPropagation()`，但不得阻断必要的键盘事件和平台输入事件。

## 15. 字符预算与拆包

当前 MMD 单条 `findRegex <= 1000`、`replaceString <= 20000`，所有 findRegex 必须是 `/pattern/flags` slash literal。运行时资产还须执行以下预算纪律：

- 任一 replaceString 达到 **18000 字符即预警**，为 JSON 转义、修复和平台变化保留余量。
- 公共选择器只保留一份；day/night 只存 token，不复制 10K 选择器。
- 拆包按职责分为 bootstrap、公共 CSS、可选面板或插件，但每份仍遵守同 owner/version 租约，不能各建运行时。
- 统计解析后的 `findRegex` 和 `replaceString` 长度，同时检查最终 JSON 无 BOM、语法合法。
- 运行时 CSS 放 head 单例；不要让每条消息长期携带同一份大 CSS。

## 16. 测试矩阵

浏览器沙箱、静态 validator 与 MMD 实机是三种不同证据。报告必须注明证据层级，不得用沙箱通过代替实机通过。

### 16.1 静态与结构

- [ ] JSON 语法合法、无 BOM，所有 findRegex 为 slash literal。
- [ ] `validate.py --platform mmd` 为 0 error；warning 有明确处置。
- [ ] 每条 replaceString < 20000；达到 18000 有预警记录。
- [ ] owner/version/命名空间一致，无通用 ID 或无前缀全局变量。
- [ ] head 每类资源、lease、observer、route supervisor、设置面板计数均为 1。

### 16.2 生命周期与主题

- [ ] 连续 bootstrap 三次不重复注入。
- [ ] `day -> night -> native` 连续切换三轮，token、根属性和面板状态同步。
- [ ] native restore 只撤销本 owner delta，不覆盖平台后写值。
- [ ] destroy 后无 owner 的 head 资源、根属性、面板、observer、监听、计时器、全局 API 和租约。
- [ ] route leave 后停止并恢复；返回聊天 route 后 reenter 且资源仍单例。
- [ ] pagehide 取消已排队 route timer；pageshow 前 queued/manual reconcile 均不能重入，pageshow 后才恢复。
- [ ] SPA 整页替换 `body`/聊天根节点后，同一 UI host 重新挂到当前 body，不遗留旧节点引用。
- [ ] 动态新增多条 AI 消息后，全局资源不增长，消息状态栏仍按 per-message 边界工作。

### 16.3 设置与非法数据

- [ ] day 与 night 的玩家 overrides 分开保存，切换不串值；持久状态不含 preset/full themes。
- [ ] 重置当前主题删除当前 overrides；全部恢复默认清两主题 overrides，并按资产 README 约定保留 mode/normalizeQuotes。
- [ ] schema-1 完整 theme 只迁移相对固定 legacy defaults 的合法差异，不钉住旧默认。
- [ ] 非法 JSON、`null`、数组、未知 schema、未来 schema、恶意键、超长值均降级到默认且不阻断启动。
- [ ] 至少一版旧 schema 能迁移并写回；迁移失败保留可诊断原因。
- [ ] localStorage 拒绝/配额异常时，当前页面切换仍工作。
- [ ] 文本规范化默认关闭；开启后明确记录其不可逆边界。

### 16.4 移动端与 a11y

- [ ] 常见窄屏、横屏、刘海 safe-area、底部手势区无控件遮挡。
- [ ] 软键盘打开/关闭时面板与输入框都可访问。
- [ ] 触控目标、滚动、关闭动作可用，最长标签不溢出。
- [ ] 键盘 Tab/Shift+Tab/Enter/Space/Escape 可完成操作，焦点样式可见。
- [ ] day/night 的正文、次要文字、按钮和禁用态分别检查对比度。

### 16.5 localStorage 当前 MMD 实机矩阵

以下各项在实测前统一标“待验证”，不得预填通过：

| 场景 | 要记录的结果 |
|---|---|
| 同一聊天页刷新 | mode 与两套 overrides 是否保留 |
| 离开聊天再返回 | route 重入后是否读取同一值 |
| 同角色不同聊天 | 偏好是否共享 |
| 不同角色卡 | 是否意外串用，是否符合产品预期 |
| App/WebView 完全关闭后重开 | 是否持久 |
| 登录状态变化或账号切换 | 是否隔离 |
| 不同设备或浏览器 | 不应默认期待同步，记录实际结果 |
| 存储被禁用、清空或配额异常 | 是否无崩溃降级 |

只有完成对应当前 MMD 实机矩阵，才能在资产 README 把某项从“候选 / 待验证”改为“已验证”，并附日期、环境和结果。