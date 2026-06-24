---
description: 制作酒馆美化（全局美化/状态栏）
---

调用 tavern-mmd skill，执行美化制作流程：

1. 平台确认：按 SKILL.md 流程。美化方案强依赖平台，未设定必须先问。
2. 用 AskUserQuestion 问类型：全局美化（整体界面换肤）/ 状态栏（每条消息末尾数据面板）/ 两者都要。
2.5. **选风格（强制前置）**：读 references/beautify/style-system.md，用 AskUserQuestion 先选基调组（素雅/柔和/科技/考究/玩味/氛围）再选具体风格（可给 2-3 个 preview 描述），风格清单见 references/beautify/style-db/README.md；或按用户要求混搭维度。把选定风格/覆盖项记入 plan.md 与 工作/美化决策.md。默认风格仍可用旧的 #0d1117，但必须问过用户。
3. 项目检查：无项目文件夹则确认项目名并创建五件套；已有则读 main.md+plan.md 续作。
4. 按类型读取文档并制作：
   - 状态栏：首选混合态雷达法 references/beautify/statusbar-radar.md（按其"制作工作流"节执行：字段五级分类→从 assets/radar-examples/ 选示例改造→四条正则+状态栏规则）；轻量场景或用户指定时用 references/beautify/statusbar.md（KV V4.0三段正则）。两者均需先用 AskUserQuestion（带preview）让用户选布局风格与数据字段（资源条/NPC好感/线索/选项等）。
   - 全局美化：references/beautify/global-css.md。先问配色主题（可给2-3方案preview），再产出激活器+CSS正则。雷达法集成案例（日夜双主题+侧边栏切换）见 assets/radar-examples/完整美化-日夜主题与雷达.json。
5. 代码草稿放"工作/"；每条正则统计字符数（MMD限额预检）。
6. 自检：quality/checklist.md 结构/代码/正则/样式层全跑。
7. 输出到 output/：本地酒馆=正则json；MMD=导入json（pageDepth/statusbar/beginning/regex_scripts四字段，首选）+手填清单.md（备选），格式均见 output/regex-output.md。**单独美化/状态栏流程的默认交付 = 正则 json + 状态栏规则.md**（独立的状态栏生成规则/模型侧协议文档），不强制塞进某张卡。更新main.md与plan.md。

## 交付前审核与预览（强制）

产出 json 后执行：
1. **子代理审核**（省主上下文）：派子代理跑 `python <skill>/scripts/validate.py <文件> --platform <平台>`，把完整报告写入项目 `工作/审核记录.md`（含时间戳、文件名、结果）。
2. **有 ERROR 时修复闭环**：主AI读报告 → 派第二个子代理修复 → 子代理1复审；若仍 ERROR，主AI 亲自接手。每轮写入 `工作/审核记录.md`。
3. **主AI 交互测试**（子代理做不了）：跑 `python <skill>/scripts/build-preview.py <文件> --platform <平台> --mode both`，默认生成 `<文件>-preview-<平台>.html`（三面板诊断）和 `<文件>-panorama-<平台>.html`（全景预览）。用自带 Preview 工具先看三面板，再看全景，并实测交互：点击选项按钮、切换标签页、展开侧边栏/折叠面板。发现问题改源码 → 回第1步复审。
4. **问用户预览**：能调 Preview 工具的，附截图；不能的，提示用户用浏览器打开生成的 `-preview-` 与 `-panorama-` 两份 HTML。
5. 无子代理的 agent：主AI 顺序自跑 validate → 修复 → preview → 交互测试。
