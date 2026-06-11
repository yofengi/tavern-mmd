---
description: 设定目标平台为本地酒馆SillyTavern
---

调用 tavern-mmd skill。执行：

1. 设定本会话目标平台 = 本地酒馆SillyTavern。
2. 若存在项目文件夹，将 main.md 中"目标平台"更新为"本地酒馆"；无项目则记在会话内。
3. 读取 ~/.claude/skills/tavern-mmd/references/platforms/sillytavern.md。
4. 向用户输出一句确认 + 能力摘要（3行内）：script/ES6+可用、正则json直接导入、世界书全字段支持。
5. 若用户消息中带具体任务，确认平台后直接进入对应任务流程。
