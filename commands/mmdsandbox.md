---
description: 设定目标平台为MMD沙盒模式（魅魔岛新聊天页，chatVersion:1，<script>一等公民+官方SDK）
---

调用 tavern-mmd skill。执行：

1. 设定本会话目标平台 = MMD沙盒模式。
2. 若存在项目文件夹（当前目录或用户指定），将 main.md 中"目标平台"更新为"MMD沙盒模式"；无项目则仅记在会话内，待建项目时写入。
3. 读取当前 skill 根目录下的 `references/platforms/mmd-sandbox.md`（ZCode 部署副本通常为 `~/.zcode/skills/tavern-mmd/`，不要硬编码 `.claude` 路径）。
4. 向用户输出一句确认 + 该平台关键限制摘要（5-7行）：
   - `chatVersion: 1` 必写，且**只在新建卡导入时被读取**——已存在的卡导入会被忽略，无法把老卡升级成新页（表现是脚本装上但 SDK 全不在、页面无报错）。它在 UI 上的真身是创卡页的**「新版聊天页」单选**，标注**「首次保存后不可再改」**。交付时必须书面提醒：**新建卡 + 首次保存前选「使用新版」**，选错只能重开一张卡。
   - `<script>` 是一等公民：装卡即抽出、不需被匹配命中、**整张卡只跑一次**（不是每条消息一次）。每条气泡里的按钮绑定必须写在 `sdk.on('message:mount')` 里，且 `sdk.on` 只写在脚本体、绝不写进 mount 回调。
   - 公开 SDK 30 能力 / 12 事件 / 7 错误码（`sdk.input/composer/message/cache/save/stage/role/user/debug`；无公开 `once/off`）；长期面板挂舞台 `sdk.stage`，content/full 关闭后保留作者内容。发送/生成未结束再发立即 BUSY，保留草稿，不排队、不自动重试。
   - **「消息生成中」占位陷阱**：空 AI 气泡 DOM 是占位文案。stream 的 `msg.content` 是**与气泡同步的已揭示累计文字**，替换当前显示，不逐次重复追加或提前读取完整回复；最终正文用 done，content 为空也不退回读 DOM。
   - 导入正则 JSON 顶层**恰好 6 键**（`chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts`）。确定上限：statusbar 200 / **beginning 4000**（官方校验脚本写 10240 是错的）/ personality 10000 / replaceString 导入 100000 / 规则 ≤130 条。`scriptName` 的 UI 显示值 20、源码归一常量 200；`findRegex` 对应 1000 / 4096，这两项的 editor/import 双路径与超限语义**尚未确证**，交付仍保守按 20 / 1000。`replaceString` 的编辑器 20000／导入 100000 双路径已确证：编辑器超限会**静默拒绝保存整条修改**，不是截断。`id` 必须负数。世界书不能塞进**这一份** json（另出独立 json，根对象只留 `entries`）—— 但那只是这份文件的格式约束，走整卡时世界书正常放卡内 `character_book`。
   - `findRegex` **交付统一写 `/…/` slash 形态**，但这是**跨平台一致性约定、不是硬红线**：`【实机实测 2026-08-30】`（卡 64304 A/B）确认**裸字面量也生效**，与 worker 源码及官方「字面量是首选」一致，校验器对裸字面量出 WARN 不出 ERROR。（旧文案「裸字面量不生效」已被自家实机证伪，勿再沿用。）`img onerror` 点火器与 teapot 系写法**官方明令禁止**，脚本改用「专开一条只放 `<script>` 的规则」。
   - **兼容启动**：2026-08-26 历史探针中脚本早于 DOM，ready 最后到且不补发；首屏采用幂等 mount/done，不只依赖 ready。证据先比较版本/日期/环境；ready、save.remove、配额、外链顺序/白名单的旧冲突保留日期，当前部署待复验。
   - **功能栏（statusbar）是静态的**（装载时只跑一次，正则输入是 `statusbar` 字段自身）→ 动态状态栏只能靠 JS 改 DOM，指望正则刷新是徒劳。
   - **验证默认走本地仿真**：先跑 `validate.py --platform mmdsandbox` 与 `build-preview.py --platform mmdsandbox --mode both`，在本地完成 SDK/事件/舞台/主题/移动视口与截图回归。AI 不默认登录真实 MMD 账号，也不拿正式卡或公开卡做日常测试；真实站只保留未确证边界探针与用户授权后的最终人工验收。
   - **交付两条路线，做整卡时用弹窗问一次**（`references/output/card-json.md` §8.1）：**路线A** = v2 PNG 整卡，JSON 作源码/备份（世界书进 `character_book`、正则进 `data.extensions.regex_scripts`、人设进 `data.description`）；**路线B** = 6键正则 json + persona 文本（导入页不读 `personality`，须手工粘贴）+（可选）独立世界书 json。沙盒整卡 JSON 直接导入的历史记录冲突，标待复验，不影响六键正则 JSON 的导入。两条路线都要提醒「**新建卡 + 首次保存前在创卡页选「使用新版」聊天页**，此选择首次保存后永久不可改」。
   - **做状态栏/美化直接用现成基座**：`assets/sandbox-kit/`（改 `sbk.config.example.json` 跑 `build_sbk.py` 即得可导入 JSON），方法论见 `references/beautify/sandbox-kit.md`。
   - **宿主弹窗换肤**：21 个开放 `[data-host]` 根（19 + summary + summary-confirm）走静态 `<style>` 抽取过滤，不是跨源 DOM 接口。读 `references/beautify/sandbox-host-styles.md`；SBK 可选 `hostStyles:["path.css"]`，与运行时阅读主题开关分开，动态转发未验。summary 主根与根内编辑/锚点、树外 summary-confirm 分别写样式；禁区与未知内部结构不编造。
   - **平台状态变量 `sdk.vars` / `vars:change` / `<abc_vars>`（§14）**：业务资料与运行契约分开。保留项目业务规则：仅新页可开、最多 6 层 80 键、快照随消息存并按楼层回溯、`{{var}}` 只替换本轮新组装内容、分享页/瘦预览可读不可写。2026-09-05 网页核对及本轮资料没有完整签名/返回/导入字段，不编造调用，不把推测的 varSchema/varInit 塞进六键包，也不据此说平台不支持。现阶段用已确认的正文状态协议解析；平台内部 `<abc_vars>` 不冒用、不用正则隐藏。
   - **公开发布门槛（§10.3）**：固定传输字符（人设 + 已启用且常驻且 100% 概率的世界书正文）须在 **2000–15000** 含边界，`beginning` **≥200 字**（与 4000 上限夹成 200–4000），不许空白凑数；私人自用卡与纯草稿不受此约束。单条世界书 `content` **≤3000 字**。
5. 若用户要**同层卡、完整自绘网页、替换聊天界面或参考 new-mmd-hud**，读取 `references/creation/sandbox-same-layer-card.md`；分析/迁移贪心鬼新版仓库时再读 `references/runtime/new-mmd-hud-audit.md`。采用官方 SDK + 舞台，不能套旧页 `assets/same-layer-kit`、四键导出器和 61 项原生桥接表；SBK 不替代完整同层页。
6. 若用户消息中带具体任务（如"/mmdsandbox 做个状态栏"），确认平台后直接进入对应任务流程；已选新页无需因“同层卡”再询问平台。
