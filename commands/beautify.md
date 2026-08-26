---
description: 制作酒馆美化（全局美化/状态栏）
---

调用 tavern-mmd skill，执行美化制作流程：

1. 平台确认：按 SKILL.md 流程。美化方案强依赖平台，未设定必须先问。
2. 用 AskUserQuestion 问类型：全局美化（整体界面换肤）/ 状态栏（每条消息末尾数据面板）/ 两者都要。
2.1. **全局美化分流（先按平台分，再问档位）**：
   - `/mmd` 与 `/st`：问“静态换肤 / 当前 MMD 三态运行时主题包”。用户要求 day/night/native、玩家微调、设置面板、重置或记住偏好时，默认选三态运行时。
   - `/mmdsandbox`：**不走上面二档，直接用 SBK 基座**。先读 `references/beautify/sandbox-kit.md`（方法论）+ `assets/sandbox-kit/README.md`（怎么跑生成器），平台事实见 `references/platforms/mmd-sandbox.md`。要点：平台有 **14** 个 `--chat-*` 变量（不是 10 个），换肤必须覆盖 `[data-chat="root"][data-theme=*]`（特异度 (0,2,0)）才不被深浅色切换打回；页面背景是 root 上的**内联** `background-image`，唯一需要 `!important` 的地方；订 `theme:change` 跟随；常驻面板挂 `sdk.stage` 而非气泡。**不要移植当前 MMD 的 runtime 主题包**（它为 mmd 的约束而设计）。
2.5. **选风格（强制前置）**：读 references/beautify/style-system.md，用 AskUserQuestion 先选基调组（素雅/柔和/科技/考究/玩味/氛围）再选具体风格（可给 2-3 个 preview 描述），风格清单见 references/beautify/style-db/README.md；或按用户要求混搭维度。把选定风格/覆盖项记入 plan.md 与 工作/美化决策.md。默认风格仍可用旧的 #0d1117，但必须问过用户。
3. 项目检查：无项目文件夹则确认项目名并创建五件套；已有则读 main.md+plan.md 续作。
4. 按类型读取文档并制作：
   - 状态栏（`/mmd`、`/st`）：首选混合态雷达法 references/beautify/statusbar-radar.md（按其"制作工作流"节执行：字段五级分类→从 assets/radar-examples/ 选示例改造→四条正则+状态栏规则）；轻量场景或用户指定时用 references/beautify/statusbar.md（KV V4.0三段正则）。两者均需先用 AskUserQuestion（带preview）让用户选布局风格与数据字段（资源条/NPC好感/线索/选项等）。
   - 状态栏（`/mmdsandbox`）：**直接用 SBK 基座**，别从零手写。读 `references/beautify/sandbox-kit.md`，按 2.0 三职责选择：`status`＝气泡内唯一状态数据面板（默认开），`chrome`＝功能栏入口（默认开、不渲染业务数据），`pinned`＝可选 1–3 字段单行精简条（默认关）。不要再使用 1.0 的“常驻 HUD + 消息快照双开”说法，那会重新制造两个重复状态面板。改 `assets/sandbox-kit/sbk.config.example.json` 的 `schema.fields` 后跑 `build_sbk.py`。三条根本约束：雷达法与 img onerror 不可移植；功能栏正则静态、动态值靠 JS；`ready` 最后到且无补发，首屏挂 mount/done。
   - 全局美化：先读 references/beautify/global-css.md 做二档选型。静态换肤按其中单规则骨架；当前 MMD 只要需要 day/night/native、玩家微调、设置、重置或持久偏好候选，必须再读 references/beautify/theme-runtime.md，并优先从 assets/global-beautify-examples/mmd-theme-runtime/ 改造。该 runtime 协议与新资产是在社区快照提供架构启发后重新设计与实现的，实机状态以资产 README 为准，不得虚构已验证。assets/radar-examples/完整美化-日夜主题与雷达.json 仅为社区来源启发的 legacy 集成参考，不再推荐作当前全局主题基底。
5. 代码草稿放"工作/"；每条正则统计字符数（MMD 限额预检，replaceString 达到 18000 即预警）。**当前 MMD 与沙盒模式都必须**把每条 findRegex 写成 `/pattern/flags` slash 形态——沙盒实机验证裸字面量 `{{hud}}` 不生效、改 `/{{hud}}/` 立即生效（与官方文档说法相反，以实机为准）。沙盒的 `id` 必须为负数。沙盒还有一条手册与官方校验器都漏掉的硬限制：**单条规则输出预算 `max(262144, 输入长度×4)`，超限整条规则回滚**（页面上完全不生效只留告警），且**匹配式绝不能匹配空串**。用 `assets/sandbox-kit/build_sbk.py` 生成时这两条会自动预检。
6. 自检：quality/checklist.md 结构/代码/正则/样式层全跑。
7. 输出到 output/：本地酒馆=正则json；当前MMD=导入json（pageDepth/statusbar/beginning/regex_scripts四字段，首选）+手填清单.md（备选）；沙盒模式=导入正则json（chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts **六字段**，`chatVersion` 必须为 1）+手填清单.md（备选），并在交付说明里写明「必须新建卡、创卡页确认是新页」。格式均见 output/regex-output.md。**单独美化/状态栏流程的默认交付 = 正则 json + 状态栏规则.md**（独立的状态栏生成规则/模型侧协议文档），不强制塞进某张卡。更新main.md与plan.md。

## 交付前审核与预览（强制）

产出 json 后执行：
1. **子代理审核**（省主上下文）：派子代理跑 `python <skill>/scripts/validate.py <文件> --platform <平台>`，把完整报告写入项目 `工作/审核记录.md`（含时间戳、文件名、结果）。
2. **有 ERROR 时修复闭环**：主AI读报告 → 派第二个子代理修复 → 子代理1复审；若仍 ERROR，主AI 亲自接手。每轮写入 `工作/审核记录.md`。
3. **主AI 交互测试**（子代理做不了）：跑 `python <skill>/scripts/build-preview.py <文件> --platform <平台> --mode both`，默认生成 `<文件>-preview-<平台>.html`（三面板诊断）和 `<文件>-panorama-<平台>.html`（全景预览）。用自带 Preview 工具先看三面板，再看全景，并实测交互：点击选项按钮、切换标签页、展开侧边栏/折叠面板。发现问题改源码 → 回第1步复审。
4. **问用户预览**：能调 Preview 工具的，附截图；不能的，提示用户用浏览器打开生成的 `-preview-` 与 `-panorama-` 两份 HTML。
5. 无子代理的 agent：主AI 顺序自跑 validate → 修复 → preview → 交互测试。
