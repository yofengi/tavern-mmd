---
description: 设定目标平台为当前MMD（魅魔岛，支持<Script>）
---

调用 tavern-mmd skill。执行：

1. 设定本会话目标平台 = 当前MMD。
2. 若存在项目文件夹（当前目录或用户指定），将 main.md 中"目标平台"更新为"当前MMD"；无项目则仅记在会话内，待建项目时写入。
3. 读取 ~/.claude/skills/tavern-mmd/references/platforms/mmd.md。
4. 向用户输出一句确认 + 该平台关键限制摘要（3-5行）：支持<script>（其余按旧版保守）、正则≤30条/1000/20000（支持json导入）、角色卡仅v2格式、ES5建议、事件冒泡stopPropagation、时间戳ID。
5. 若用户消息中带具体任务（如"/mmd 做个状态栏"），确认平台后直接进入对应任务流程。
