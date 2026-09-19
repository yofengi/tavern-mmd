# 当前 MMD 同层卡基座与对话模块

作品预览与审核默认使用 [统一流程](../../references/creation/same-layer-review.md)：复制 `same-layer.project.example.json`，配置作品后调用 `scripts/review_same_layer.py`，一次获得同版本发布文件、MMD / 同层卡联动预览和报告。原生页保留旧预览已有入口与面板，审核同时检查原生完整性和同层联动。

旧页 `/mmd` 专用；**不是新页 SDK/SBK**。这是可修改的独立页面、原生桥接、可选小游戏与本地存档起点，真实 MMD/真机兼容尚待项目验收。

沙盒同层卡 `/mmdsandbox` 走 [SDK + 舞台网页制作](../../references/creation/sandbox-same-layer-card.md)，不能只给本基座补 `chatVersion:1` 就转换平台。

## 文件

| 文件 | 作用 |
|---|---|
| core.js | 确定规则示例、公开状态、命令幂等、带校验与作用域的存档、迁移、叙述台账 |
| native.js | 原生 DOM 桥接、外部 NativeBridge 包装、Mock |
| models.js / provided-models.js | 内置原生模型模块、外部桥接模型投影；动态能力与目标版本检查 |
| frame-models.js | 可复用的模型列表、筛选、切换和设置 UI |
| host.js | 单实例、iframe、MessagePort、路由生命周期、原生操作与游戏服务 |
| frame.html / frame.css / frame-ui-config.js | 雾港页面结构、深浅主题和模块开关 |
| frame-features.js / frame-panels.js | 消息操作、会话、人设、补充设定、指令、分享、设置与原生入口 |
| frame.js | 通信、发送、探索/休息、叙述与进度导入导出 |

## 使用

先读 `../../references/creation/same-layer-card.md`。复制本目录为项目源码，修改页面与规则。相对实际 skill 根目录执行：

复制 `same-layer.project.example.json` 为作品配置，填写 `source`、作品信息与功能开关后运行：

```sh
python scripts/review_same_layer.py --project <作品配置.json> --out <新审核目录> --browser required
python -m http.server 8765 --bind 127.0.0.1 --directory <新审核目录>
```

访问本地 `review-report.html`，进入 MMD / 同层卡联动预览。模型与引擎用配置中的 `models` / `engine` 开关。源码、发布文件、预览、报告绑定同一版本，输出目录不会覆盖。依赖与可选独立诊断方式见 [统一指南](../../references/creation/same-layer-review.md)。

`release/` 中提供四字段正则 JSON、frame.html、release-manifest.json。整卡交付再封装为 v2 PNG，独立世界书通过已有世界书工具构建。

### 连接真实 MMD

- 默认自动启动原生桥接，内置固定上游已实现的 61 项动作，不需要额外桥接实例；现成对话模块覆盖已实现动作的入口与流程，可按需组合。顶部“返回 MMD”入口保留。
- 已有贪心鬼 NativeBridge 的宿主可提供实例 `window.__MMD_HUD_NATIVE_BRIDGE__`；它由原宿主管理生命周期，本包不包含上游源码。
- 真实存档须提供经验证的 Host-only `window.__MMD_SAME_LAYER_SCOPE__()`，返回非凭据的 accountKey、roleId、conversationKey。未提供时游戏保存停用；不能把 Mock 的固定值复制进生产。
- scope、Web Locks、localStorage 和 WebCrypto 任何一项不可用，明确显示保存错误。Frame 没有父页 DOM 或 localStorage 权限。
- 此示例将引擎放在 Host，Frame 只接受公共状态。AI 叙述不会更新规则数值。

详见 `../../references/runtime/mmd-native-bridge.md`。

## 测试

```sh
node --test scripts/test_same_layer.mjs scripts/test_same_layer_models.mjs
python -m unittest discover -s scripts -p test_build_same_layer.py -v
```

浏览器测试：给环境变量 PLAYWRIGHT_MODULE 指定已有 Playwright 的 index.mjs，再运行 `node --test scripts/test_same_layer_browser.mjs scripts/test_same_layer_models_browser.mjs`。可配置 BROWSER_CHANNEL（默认 msedge）、PYTHON 和 MMD_SL_EVIDENCE_DIR；没有 Playwright 时该项明确 SKIP。测试不安装包、不访问真实 MMD。

## 证据与来源

资产为 tavern-mmd 的独立最小实现。原生桥接与容器思路参考贪心鬼仓库 ae96d63；规则/存档分离与恢复思路参考用户提供的黑洞猫教程。来源链接与授权边界见制作参考；没有将来源不明的第三方代码重新声明为 MIT。

本地测试证明的是示例合同与浏览器行为。真实平台导入回读、脚本去重、CSP、嵌套视口及实体手机测试应单独标记，不能由本地 PASS 推定。

内置模型模块用法见 `../../references/runtime/mmd-model-controls.md`，接入范围见同目录 `mmd-native-capabilities.md`。内置的其他原生功能见 `../../references/runtime/mmd-action-modules.md`，已有统一结果投影；可用 allowedActions 限制本作品可调用动作。清单之外的自定义外部动作才需要额外 projectResult。待确认阶段保留确认交互。

## 完整原生动作层

`actions.js` 提供参数、快照投影和统一并发控制；`actions-dom.js` 读取原生状态；`actions-handlers.js` 实现新增 52 项动作；`provided-actions.js` 适配调用者已启动的外部 NativeBridge。加上发送和 8 项模型动作，功能层共 61 项。对话页已提供模块界面，配置 `frame-ui-config.js` 选择所需模块。

作者调用方式与确认阶段见 [原生动作模块](../../references/runtime/mmd-action-modules.md)。普通 Mock 预览仍只演示聊天、模型和游戏；旧的 `scripts/preview_same_layer_dialogue.py` 组合原创 DOM 夹具，保留作模块诊断。正常作品使用上述统一联动预览；这些本地工具均不连接真实 MMD。详见 [对话页模块制作](../../references/creation/same-layer-dialogue.md)。

```sh
node --test scripts/test_same_layer_actions.mjs
# 设置 PLAYWRIGHT_MODULE 后运行完整本地原生夹具
node --test scripts/test_same_layer_actions_browser.mjs
```
