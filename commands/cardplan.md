---
description: 角色卡标准计划流程（弹窗快问快答→plan.md→执行）
---

调用 tavern-mmd skill，执行标准计划流程。适合需求明确的中小型卡。

阶段一：快速决策（全程 AskUserQuestion 弹窗，一次一问）
1. 项目名 → 创建项目文件夹五件套（main.md/plan.md/资料/工作/output），main.md写入初始索引。
2. 目标平台（已设定则跳过）。
3. 卡类型：单角色卡 / 多角色卡 / 世界卡（无主角色）/ 二创卡（需用户提供原作资料存"资料/"）。
4. 组件清单（multiSelect）：世界书 / 状态栏 / 全局美化 / 多开场白（问数量）。
5. 核心设定一句话确认：题材+基调+主角色概念（用户自由输入或从选项选）。

阶段二：计划与执行
6. 把以上决策写入 plan.md：任务拆为带勾选框的步骤（每步=一个条目/组件，附验收标准），决策记录附后。
7. 按 plan.md 顺序执行，调用对应references文档（worldbook/character/opening/statusbar等），每完成一步打勾。
8. 关键节点停下确认：条目规划表 → 开场白成稿 → 技术组件成稿 → 最终交付。
9. 交付前跑 quality/checklist.md，json校验，全部产出进 output/，更新main.md。

## 交付前审核（强制）

产出 json 完成后：派子代理跑 `python <skill>/scripts/validate.py <文件> --type <card|regex> --platform <mmd|mmdsandbox|st>`（`--platform` 省略时默认 `mmd`），报告写入 `工作/审核记录.md`。有 ERROR 修复后复审。若卡内含状态栏/美化，按 /beautify 的预览流程让主AI 测交互。

平台决定校验什么：`--platform mmd` 与 `--platform mmdsandbox` 的角色卡都按 chara_card_v2 规范校验，`--platform st` 走 v3。**`/mmdsandbox` 同样是 v2 卡平台**（`【用户实测】`编辑页导入 v2 卡按新卡处理，故整卡路线可达新页）：走整卡就跑 `--type card --platform mmdsandbox`，走分离式再跑 `--type regex --platform mmdsandbox` 审那份 6 键 json。人设格式与「新建卡 + 首次保存前选『使用新版』聊天页」的交付提醒见 `references/platforms/mmd-sandbox.md` §9。
