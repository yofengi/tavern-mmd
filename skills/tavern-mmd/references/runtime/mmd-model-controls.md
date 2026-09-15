# 同层卡模型模块

适用旧 MMD `chatVersion:0`/缺省。用户要把模型列表、筛选、切换或设置放进同层卡 UI 时读取本页。原生动作总表见 [能力清单](mmd-native-capabilities.md)。

## 1. 已经提供什么

模型模块与其他原生功能一起随构建结果打包，无需玩家额外安装桥接脚本。Host 自动创建原生 DOM 适配器；Frame 显示自己绘制的模型 UI。后台的 MMD 原生页面仍负责实际模型操作。

| 用户功能 | 内置动作 | UI 行为 |
|---|---|---|
| 打开/关闭模型列表 | openModelSettings / closeModelSettings | 读取列表，显示模型名称、介绍、原生消耗与权限文字 |
| 分类筛选 | selectModelFilter | 使用原生分类，不自行编造模型目录 |
| 切换模型 | selectModel | 触发原生选择，再核对当前模型入口或重新读取选中项 |
| 打开/关闭模型设置 | openModelConfiguration / closeModelConfiguration | 展示模型实际提供的设置项 |
| 修改与提交设置 | setModelSetting / submitModelConfiguration | 支持选项、开关与预设；开关使用明确目标值，避免重复操作把它翻回去 |

这些是原创适配代码，模型 DOM 选择器依据上游固定提交整理。**本地夹具已覆盖实现行为，真实旧 MMD 与手机的兼容性仍要单独验收。** 不把“上游有处理器”“本地测试通过”写成“真实平台已验证”。

模型价格、权限和成功率等均显示平台当时提供的文字；不硬编码名称、价格表或权限推断。列表里的消耗信息不会作为游戏金币结算。

## 2. 制作时怎样使用

1. 复制整个 `assets/same-layer-kit/`，沿用用户选择的页面风格。
2. 默认构建包含模型模块。`--no-models` 隐藏该模块；与 `--no-engine` 独立，纯聊天卡同样可以切模型。
3. `frame-models.js` 是可复用的 UI 模块，默认在 Frame 的 header 内加入入口；它只使用 Host 暴露的消息通道。不写父页选择器，不在 Frame 调用私有后端。
4. 自定义布局可以替换模块样式或用同一协议绘制自己的下拉菜单/设置抽屉，保留当前可用性、目标版本和结果核对。
5. 构建、标准校验、专项校验后跑模型浏览器测试；交付时附能力与证据范围。

```sh
python scripts/build_same_layer.py --source <项目源码> --out <新候选> --build-id models-001 --preview
python scripts/validate.py <新候选>/same-layer-mmd.json --platform mmd
python scripts/verify_same_layer.py <新候选>
```

构建器加入 `models.js`、`provided-models.js` 和 `frame-models.js`，发布清单记录 `models: true/false`。它们与普通状态栏路线无关，不往逐消息 onerror 中复制整套模块。

## 3. Frame 合同

`snapshot.native.models` 包含：

- `enabled`、`busy`、`issue`：模块是否启用、是否等待操作，以及不可用原因。
- `current`：已观察的模型名称与证据来源；尚未确认时名称可为空。
- `modelPanel`：open、revision、filters、models、loading。
- `modelConfiguration`：open、revision、modelName、energyLabel、controls。

模型行只投影 id、name、description、batteryLabel、permission、successRate、selected、available、canConfigure。不会将原生 HTML 或凭据转交 Frame。内置 DOM 目标 ID 仅对当前页面有效，不能作为模型服务器 ID 或存档键。

通过 `native.invoke` 提交动作：

```js
await call('native.invoke', { action: 'openModelSettings', payload: {} });

// 从当前 snapshot 取值，不硬编码 UUID、模型名称或列表序号。
await call('native.invoke', {
  action: 'selectModel',
  payload: { revision: modelPanel.revision, modelId: chosenModel.id }
});

await call('native.invoke', {
  action: 'setModelSetting',
  payload: { revision: modelConfiguration.revision, controlId: toggle.id, value: true }
});
```

除打开列表外，每个动作都带相应面板的 revision。筛选用 filterId；模型选择/打开设置用 modelId；选项设置用 controlId＋choiceId；关闭/提交也要带 revision。模型列表重建、字段变化或会话切换后，旧请求会被拒绝。

所有按钮依据最新 capability 和目标行的 available/canConfigure 启用。模型模块将同一时刻的原生操作串行处理；超时后不会自动重试。

## 4. 结果语义

| data.phase | 含义 |
|---|---|
| opened / filtered / closed | 已观察对应列表状态 |
| selection-observed | 原生当前模型文字或重新读取的选中项与目标相符 |
| selection-unconfirmed | 发出了选择动作，但不能核对结果；提示重新读取或返回 MMD |
| configuration-opened / configuration-closed | 已打开匹配设置或关闭设置 |
| setting-observed | 已观察设置项变化 |
| configuration-submitted | 原生提交动作返回，设置面板已关闭 |

关闭列表本身不能证明模型切换成功。模型切换在入口名称不足以核对时，会重新打开原生列表读选中项，然后尝试关闭。不会为了核对而再次执行模型选择。

以上结果仍不等于服务器持久化回执。completed/persisted 继续为 unknown；尤其关闭模型设置不能声称撤销修改。UI 使用“关闭设置”和“提交设置”，不虚构回滚能力。

## 5. 使用已有贪心鬼 NativeBridge

若宿主已经创建并启动 `window.__MMD_HUD_NATIVE_BRIDGE__` 实例，基座仍可包装它。`provided-models.js` 将上游模型快照与动作转换为上述 Frame 合同，内置模型组不再需要作者另写 `projectResult`。

这条路径检查 allowedActions、getCapabilities 和 getRegisteredActions（若提供），并只投影模型相关字段。开关目标值会转换为上游的开关动作；当前值已符合要求时不重复点击。

外部实例的 start/destroy 由原宿主管理。取消只使本基座的请求失效，不销毁外部对象，也不承诺撤销平台已执行的动作。其他已内置原生动作的参数与快照见 [原生动作模块](mmd-action-modules.md)，作者按需设计 UI；清单之外的动作才需要补结果投影。

## 6. 验证

- `node --test scripts/test_same_layer_models.mjs`：外部桥接投影、选择核对、显式开关、过期目标、取消与 Mock。
- 配置 Playwright 后运行 `node --test scripts/test_same_layer_models_browser.mjs`：实际打包入口 → Host → Frame → 模拟原生 DOM；覆盖加载、筛选、切换、设置、过期列表、重复目标、超时、取消和禁用模块。
- 普通消息/存档的回归继续运行 `test_same_layer.mjs` 和 `test_same_layer_browser.mjs`。
- 本地、真实 MMD、物理手机分别记录。不要把模型模块自动启动误写成真实账号/会话解析已完成；模型 UI 无需游戏存档，但持久游戏仍需可靠 scope。

## 现成对话页

已提供可组合的消息、模型与原生功能界面，详见 [对话页模块制作](../creation/same-layer-dialogue.md)。模块开关不改变 Host 允许调用范围；原生设置只能在已实现动作范围内操作。
