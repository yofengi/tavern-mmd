---
description: 设定目标平台为MMD沙盒模式（魅魔岛新聊天页，chatVersion:1，<script>一等公民+官方SDK）
---

调用 tavern-mmd skill。执行：

1. 设定本会话目标平台 = MMD沙盒模式。
2. 若存在项目文件夹（当前目录或用户指定），将 main.md 中"目标平台"更新为"MMD沙盒模式"；无项目则仅记在会话内，待建项目时写入。
3. 读取 ~/.claude/skills/tavern-mmd/references/platforms/mmd-sandbox.md。
4. 向用户输出一句确认 + 该平台关键限制摘要（5-7行）：
   - `chatVersion: 1` 必写，且**只在新建卡导入时被读取**——已存在的卡导入会被忽略，无法把老卡升级成新页（表现是脚本装上但 SDK 全不在、页面无报错）。交付时必须书面提醒用户新建卡并在创卡页确认是新页。
   - `<script>` 是一等公民：装卡即抽出、不需被匹配命中、**整张卡只跑一次**（不是每条消息一次）。每条气泡里的按钮绑定必须写在 `sdk.on('message:mount')` 里，且 `sdk.on` 只写在脚本体、绝不写进 mount 回调。
   - 官方 SDK 30 能力 / 12 事件（`sdk.input/composer/message/cache/save/stage/role/user/debug`；`sdk.once` 与 `sdk.off` 不存在）；长期面板挂舞台 `sdk.stage`，不要挂气泡。
   - **「消息生成中」占位陷阱**（头号杀手）：空 AI 气泡里 `[data-chat="message-body"]` 是平台占位文案不是模型正文。跟字用 `message:stream` 的 `msg.content`，收尾用 `message:done` 的 `msg.content`，`content` 为空也不要退回去读 DOM。
   - 导入正则 JSON 顶层**恰好 6 键**（`chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts`）：statusbar 200 / beginning 10240 / personality 10000 / scriptName 20 / findRegex 1000 / replaceString 20000 / 规则 ≤130 条；`id` 必须负数；世界书不能塞进来（另出独立 json，根对象只留 `entries`）。
   - `findRegex` **不强制** slash literal，纯字面量标记（`{{hud}}`）是官方首选写法；`img onerror` 点火器与 teapot 系写法**官方明令禁止**，脚本改用「专开一条只放 `<script>` 的规则」。
   - 交付 = 6键正则 json + 独立 persona 文本 +（可选）独立世界书 json；**不走 chara_card_v2、不产整卡 PNG**。
5. 若用户消息中带具体任务（如"/mmdsandbox 做个状态栏"），确认平台后直接进入对应任务流程。
