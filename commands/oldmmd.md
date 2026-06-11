---
description: 设定目标平台为旧版MMD（魅魔岛，不支持<Script>）
---

调用 tavern-mmd skill。执行：

1. 设定本会话目标平台 = 旧版MMD。
2. 若存在项目文件夹，将 main.md 中"目标平台"更新为"旧版MMD"；无项目则记在会话内。
3. 读取 ~/.claude/skills/tavern-mmd/references/platforms/mmd-old.md。
4. 向用户输出一句确认 + 关键红线摘要（5行内）：禁<script>（用img onerror点火器）、ES5 only、onerror/onclick单行、正则手填≤30条/1000/10000、stopPropagation+时间戳ID必加。
5. 若用户消息中带具体任务，确认平台后直接进入对应任务流程。
