---
description: 制作酒馆世界书（输出可导入json）
---

调用 tavern-mmd skill，执行世界书制作流程：

1. 平台确认：按 SKILL.md "确定目标平台"流程（已设定则跳过；世界书json三平台通用，但需知晓平台以决定可用字段范围）。
2. 项目检查：无项目文件夹则用 AskUserQuestion 确认项目名并创建五件套（main.md/plan.md/资料/工作/output）；已有则读 main.md+plan.md 续作。
3. 收集资料：用户提供的素材存入"资料/"，更新main.md。
4. 读取 references/creation/worldbook.md，按三阶段流程执行：
   - 规划：列条目规划表 → 必须用户确认后才动工（plan.md记录）
   - 总纲：写总纲条目 → 给用户过目
   - 展开：逐条写作（正文规则按 creation/character.md），草稿放"工作/"
5. 自检：跑 quality/checklist.md 内容层+格式层。
6. 输出：按 output/worldbook-json.md 生成独立世界书json到 output/，执行 python -m json.tool 校验，更新main.md与plan.md。
