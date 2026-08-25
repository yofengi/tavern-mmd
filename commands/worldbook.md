---
description: 制作酒馆世界书（输出可导入json）
---

调用 tavern-mmd skill，执行世界书制作流程：

1. 平台确认：按 SKILL.md "确定目标平台"流程（已设定则跳过；世界书 json 在 `/st`、`/mmd`、`/mmdsandbox` 三平台通用，但需知晓平台以决定可用字段范围与条目标题上限）。
2. 项目检查：无项目文件夹则用 AskUserQuestion 确认项目名并创建五件套（main.md/plan.md/资料/工作/output）；已有则读 main.md+plan.md 续作。
3. 收集资料：用户提供的素材存入"资料/"，更新main.md。
4. 读取 `references/creation/worldbook.md`，按索引源文件工作流执行：
   - 初始化 `工作/世界书/`：`python <skill>/scripts/worldbook_tool.py init "工作/世界书"`
   - 目标平台是本地酒馆时，把 `工作/世界书/worldbook.config.json` 的 `platform` 改为 `"st"`（默认 `"mmd"`：会套用 20 字条目标题上限，超限的 `add`/`rename` 被硬拒绝）。沙盒模式填 `"mmdsandbox"`，同样保留 20 字上限
   - 沙盒模式（`/mmdsandbox`）的世界书**必须独立交付**：根对象只留 `entries`，不能并进那份 6 键导入正则 json（顶层出现 `entries`/`worldbook`/`character_book` 等会被官方判 ERROR），详见 `references/platforms/mmd-sandbox.md` §10
   - 在 `notes.md`/对话/plan.md 中列层级与条目规划 → 必须用户确认后才动工；`index.md` 是生成导航，只读不写规划
   - 若修改既有独立世界书 JSON，先导入源文件：`python <skill>/scripts/worldbook_tool.py import "工作/世界书" "output/原世界书.json" --layer "40-场景物品事件层"`
   - 结构操作（新增/删除/移动/重命名/重排）统一调用 `worldbook_tool.py`，不要手改 UID/order/index 表格
   - 正式条目写入 `工作/世界书/entries/`；未确认草稿放 `drafts/`
   - 修改既有源条目时，先读 `index.md`，再用 `show`/`search` 定位完整条目，只编辑目标源文件
5. 自检：跑 `python <skill>/scripts/worldbook_tool.py build "工作/世界书" --out "output/<世界书名>.json"`，再跑 `python <skill>/scripts/worldbook_tool.py check "工作/世界书" --out "output/<世界书名>.json"`，再读 `references/quality/checklist.md` 做内容层+格式层自检。
6. 输出：按 output/worldbook-json.md 生成/确认独立世界书json到 output/，执行 python -m json.tool 校验，更新main.md与plan.md。

## 交付前审核（强制）

输出世界书 json 后：先跑 `python <skill>/scripts/worldbook_tool.py check "工作/世界书" --out "output/<世界书名>.json"`，再派子代理跑 `python <skill>/scripts/validate.py "output/<世界书名>.json" --type worldbook --platform <mmd|mmdsandbox|st>`（`--platform` 省略时默认 `mmd`），报告写入 `工作/审核记录.md`。有 ERROR 则主AI/子代理修复后复审，0 错误才交付。世界书无交互渲染，不需 build-preview。
