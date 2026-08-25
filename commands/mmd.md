---
description: 设定目标平台为当前MMD（魅魔岛，支持<Script>）
---

调用 tavern-mmd skill。执行：

1. 设定本会话目标平台 = 当前MMD。
2. 若存在项目文件夹（当前目录或用户指定），将 main.md 中"目标平台"更新为"当前MMD"；无项目则仅记在会话内，待建项目时写入。
3. 读取 ~/.claude/skills/tavern-mmd/references/platforms/mmd.md。
4. 向用户输出一句确认 + 该平台关键限制摘要（3-5行）：支持<script>与ES6（实测全支持）、正则≤130条/1000/20000（支持json导入）、角色卡仅v2格式（整卡只能png导入）、事件冒泡stopPropagation、时间戳ID。
5. **选错平台会静默产出坏卡**：本指令针对旧聊天页（`chatVersion: 0`/缺省）。若用户的卡在 MMD 新页（新版对话框 / `chatVersion: 1`，有官方 SDK 与舞台），应改用 `/mmdsandbox`——两边写法不通用，把这套 img onerror / 雷达法用到新页上不会报错，只是不生效。不确定时先问一句。
6. 若用户消息中带具体任务（如"/mmd 做个状态栏"），确认平台后直接进入对应任务流程。
