---
description: 设定目标平台为MMD沙盒模式（魅魔岛新聊天页，chatVersion:1，<script>一等公民+官方SDK）
---

调用 tavern-mmd skill。执行：

1. 设定本会话目标平台 = MMD沙盒模式。
2. 若存在项目文件夹（当前目录或用户指定），将 main.md 中"目标平台"更新为"MMD沙盒模式"；无项目则仅记在会话内，待建项目时写入。
3. 读取当前 skill 根目录下的 `references/platforms/mmd-sandbox.md`（ZCode 部署副本通常为 `~/.zcode/skills/tavern-mmd/`，不要硬编码 `.claude` 路径）。
4. 向用户输出一句确认 + 该平台关键限制摘要（5-7行）：
   - `chatVersion: 1` 必写，且**只在新建卡导入时被读取**——已存在的卡导入会被忽略，无法把老卡升级成新页（表现是脚本装上但 SDK 全不在、页面无报错）。交付时必须书面提醒用户新建卡并在创卡页确认是新页。
   - `<script>` 是一等公民：装卡即抽出、不需被匹配命中、**整张卡只跑一次**（不是每条消息一次）。每条气泡里的按钮绑定必须写在 `sdk.on('message:mount')` 里，且 `sdk.on` 只写在脚本体、绝不写进 mount 回调。
   - 官方 SDK 30 能力 / 12 事件（`sdk.input/composer/message/cache/save/stage/role/user/debug`；`sdk.once` 与 `sdk.off` 不存在）；长期面板挂舞台 `sdk.stage`，不要挂气泡。
   - **「消息生成中」占位陷阱**（头号杀手）：空 AI 气泡里 `[data-chat="message-body"]` 是平台占位文案不是模型正文。跟字用 `message:stream` 的 `msg.content`，收尾用 `message:done` 的 `msg.content`，`content` 为空也不要退回去读 DOM。
   - 导入正则 JSON 顶层**恰好 6 键**（`chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts`）。确定上限：statusbar 200 / **beginning 4000**（官方校验脚本写 10240 是错的）/ personality 10000 / replaceString 导入 100000 / 规则 ≤130 条。`scriptName` 的 UI 显示值 20、源码归一常量 200；`findRegex` 对应 1000 / 4096，这两项的 editor/import 双路径与超限语义**尚未确证**，交付仍保守按 20 / 1000。`replaceString` 的编辑器 20000／导入 100000 双路径已确证：编辑器超限会**静默拒绝保存整条修改**，不是截断。`id` 必须负数；世界书不能塞进来（另出独立 json，根对象只留 `entries`）。
   - `findRegex` **一律写 `/…/` slash 形态**：实机验证裸字面量 `{{hud}}` **不生效**，改 `/{{hud}}/` 立即生效（与官方文档「字面量是首选」相反，以实机为准）。`img onerror` 点火器与 teapot 系写法**官方明令禁止**，脚本改用「专开一条只放 `<script>` 的规则」。
   - **作者脚本早于 DOM 执行**（顶层写 DOM 必失败），且 `ready` **最后到且无补发**（实测顺序 `message:new → message:mount → message:done → ready`）→ 首屏渲染只能挂 `message:mount`/`message:done`。
   - **功能栏（statusbar）是静态的**（装载时只跑一次，正则输入是 `statusbar` 字段自身）→ 动态状态栏只能靠 JS 改 DOM，指望正则刷新是徒劳。
   - **验证默认走本地仿真**：先跑 `validate.py --platform mmdsandbox` 与 `build-preview.py --platform mmdsandbox --mode both`，在本地完成 SDK/事件/舞台/主题/移动视口与截图回归。AI 不默认登录真实 MMD 账号，也不拿正式卡或公开卡做日常测试；真实站只保留未确证边界探针与用户授权后的最终人工验收。
   - 交付 = 6键正则 json + persona 文本（导入页不读 `personality`，须手工粘贴）+（可选）独立世界书 json；**不走 chara_card_v2、不产整卡 PNG**。
   - **做状态栏/美化直接用现成基座**：`assets/sandbox-kit/`（改 `sbk.config.example.json` 跑 `build_sbk.py` 即得可导入 JSON），方法论见 `references/beautify/sandbox-kit.md`。
5. 若用户消息中带具体任务（如"/mmdsandbox 做个状态栏"），确认平台后直接进入对应任务流程。
