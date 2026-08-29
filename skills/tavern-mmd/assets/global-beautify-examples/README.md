# 全局美化资产库

本目录按“当前 MMD 运行时成品 / legacy 参考”分级。方法论入口是 `../../references/beautify/global-css.md`；需要 day/night/native、玩家微调或路由生命周期时，还必须读 `../../references/beautify/theme-runtime.md`。

## 当前 MMD 优先入口

| 方案 | 定位 | 状态 | 路径 |
|---|---|---|---|
| **MMD 三态运行时主题包** | day / night / native、玩家分主题微调、重置、owner/version 租约、route leave/reenter、destroy | **新产物默认优先**；实机验证状态以目录 README 为准，不从本索引推定 | [mmd-theme-runtime/README.md](mmd-theme-runtime/README.md) |
| **ZMR 2.0 cleanup factory** | 单 observer、插件注册/注销、增量清污、property delta restore/destroy | 新 runtime 基础设施；由 runtime owner 统一管理，不单独当旧清污脚本导入 | [mmd_cleanup_core.js](mmd_cleanup_core.js) |

该运行时生命周期、恢复与存储协议是在社区快照提供架构启发后由 tavern-mmd 重新设计与实现的。若实现中的选择器或视觉细节受第三方案例启发，必须在其 README 另行标注；浏览器沙箱通过不等于 MMD 实机通过。

## Legacy 参考

| 资产 | 参考价值 | 不再推荐的原因 | 文件 |
|---|---|---|---|
| **旧雷达日夜集成包** | 雷达状态栏、复制式日夜 CSS 与侧栏切换的组合结构 | 用户提供的社区快照启发，作者/原 URL/许可证未完整记录；虽已迁移 slash findRegex 并修复当前 MMD handler，但无 native/destroy/route 生命周期，不再推荐作全局主题基底 | [完整美化-日夜主题与雷达.json](../radar-examples/完整美化-日夜主题与雷达.json) |
| **2026-06-21 日间 selector reference** | 米白 + 酒红历史配色、当时当前 MMD 的界面选择器、旧 CSS / 清污 / 引号规范化结构 | 未完整作用域；清污未记录 property delta；文本规范化不可逆；无 native/destroy/owner/version/完整路由重入 | [mmd-daytime-refined.md](mmd-daytime-refined.md) |

Legacy 资产只适用于它标注的当前 MMD 历史版本，不适用于旧版 MMD或本地 SillyTavern，也不能称为当前“直接可用默认成品”。确需复现时先阅读资产首页风险说明，并重新做当前 MMD 实机验证。

## 选型

1. 只有一套固定外观，不需要原生模式、设置或记忆：按 `global-css.md` 做**静态换肤**。
2. 需要 day/night/native、玩家微调、重置、持久偏好候选或 route 生命周期：选 `mmd-theme-runtime/`。
3. 只查历史类名或旧清污思路：读 `mmd-daytime-refined.md`，不要把其整段 CSS / JS 直接作为新基底。
4. 本地 SillyTavern：优先使用本地原生主题 / 自定义 CSS，不使用 MMD 清污资产。

## MMD 导入与校验

- MMD 四字段 JSON 的每条 `findRegex` 必须为 `/pattern/flags` slash literal，固定标记也要包斜杠。
- 使用 JSON parser 生成文件，UTF-8 无 BOM；不要手工修改单行大 JSON。
- 每条 `findRegex < 1000`、`replaceString < 20000`；replaceString 达到 18000 即预警。
- 先跑 `python -m json.tool <文件>`，再跑 `../../scripts/validate.py <文件> --platform mmd`。
- 浏览器预览只能检查结构和交互；route、WebView、localStorage、markdown 与 iframe 边界仍需当前 MMD 实机矩阵。

## 风格定制

1. 用 `../../references/beautify/style-system.md` 选择制作期规范 token 和成对 light/dark 色板。
2. 新 runtime 将规范 token 映射到 bundle 自有前缀运行时变量；不要继续扩散 `--lb/...`、`--bg/--bg2/...` 或 `--ac/--cb/...` 旧方言。
3. 玩家覆盖只写 day/night 各自 overrides，不回写 preset。

## 来源边界

- **社区快照**：2026-06-21 日间全局美化、历史 MMD 类名与旧清污 / 引号修复结构来自用户提供的社区文档快照；作者、原 URL 与许可证未记录，仅作兼容研究参考，不宣称原创。
- **架构启发后的重写**：`theme-runtime.md` 的运行时协议，以及 `mmd-theme-runtime/` 中按该协议交付的新资产，是吸收既有材料的架构启发后重新设计与实现的代码，不复制旧运行时实现。

## 技术参考

- `../../references/beautify/global-css.md`：静态换肤 / 运行时主题二档与 MMD 选择器
- `../../references/beautify/theme-runtime.md`：当前 MMD 运行时权威协议
- `../../references/beautify/style-system.md`：制作期 token、运行时前缀映射与玩家覆盖
- `../../references/platforms/mmd.md`：script 去重、per-message 边界与 localStorage 结论范围
- `../../references/quality/checklist.md`：交付矩阵
