---
description: 制作酒馆美化（全局美化/状态栏）
---

调用 tavern-mmd skill，执行美化制作流程：

1. 平台确认：按 SKILL.md 流程。美化方案强依赖平台，未设定必须先问。
2. 用 AskUserQuestion 问类型：全局美化（整体界面换肤）/ 状态栏（每条消息末尾数据面板）/ 两者都要。
3. 项目检查：无项目文件夹则确认项目名并创建五件套；已有则读 main.md+plan.md 续作。
4. 按类型读取文档并制作：
   - 状态栏：首选混合态雷达法 references/beautify/statusbar-radar.md（按其"制作工作流"节执行：字段五级分类→从 assets/radar-examples/ 选示例改造→四条正则+状态栏规则）；轻量场景或用户指定时用 references/beautify/statusbar.md（KV V4.0三段正则）。两者均需先用 AskUserQuestion（带preview）让用户选布局风格与数据字段（资源条/NPC好感/线索/选项等）。
   - 全局美化：references/beautify/global-css.md。先问配色主题（可给2-3方案preview），再产出激活器+CSS正则。雷达法集成案例（日夜双主题+侧边栏切换）见 assets/radar-examples/完整美化-日夜主题与雷达.json。
5. 代码草稿放"工作/"；每条正则统计字符数（MMD限额预检）。
6. 自检：quality/checklist.md 结构/代码/正则/样式层全跑。
7. 输出到 output/：本地酒馆=正则json；MMD=导入json（pageDepth/statusbar/beginning/regex_scripts四字段，首选）+手填清单.md（备选），格式均见 output/regex-output.md。状态栏附"状态栏规则"文本块（用户需放进卡的世界书或人设）。更新main.md与plan.md。
