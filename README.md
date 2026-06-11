# tavern-mmd

为 **MMD（魅魔岛 / sexyai.ai）** 和 **本地酒馆 SillyTavern** 创建角色卡、世界书、美化（状态栏 / 全局美化）的 Claude Code Skill。

完全自包含的纯文档型 skill：不依赖 MCP server、Python 或 Node 脚本，安装即用。

## 为什么需要这个 skill

MMD 是在线（uni-app 套壳）酒馆平台，与本地 SillyTavern 有显著差异：

- 旧版 MMD 禁止 `<script>` 标签，CSP 严格审查 DOM 属性内的 JS，仅支持 ES5
- 正则配置只能在平台 UI 手动填写，限额 30 条（findRegex ≤ 1000 字符、replaceString ≤ 10000 字符）
- 不支持酒馆助手、MVU 变量框架、STScript

通用的角色卡创作流程在 MMD 上会产出无法运行的卡。本 skill 内置 **平台差异矩阵**，根据目标平台自动选择可行的技术方案（如旧版 MMD 状态栏走 `<status>` 标记 + 三段正则替换 + img onerror 点火器架构）。

## 功能

| 能力 | 说明 |
|---|---|
| 三平台支持 | 当前 MMD（支持 `<script>`）/ 旧版 MMD（不支持`<script>`）/ 本地酒馆 SillyTavern |
| 角色卡创作 | 标准流程（快问快答）与深度共创流程（开放讨论 + 方案收敛）两种模式 |
| 世界书制作 | 三阶段流程（规划 → 总纲 → 展开），蓝绿灯策略、token 预算、递归控制 |
| 状态栏 | KV V4.0 方案：HTML 属性式数据块 + 跨消息数据继承（长对话省 token 最高 90%） |
| 全局美化 | MMD uni-app 界面类名速查（41 个选择器）+ CSS 变量主题架构 + 日夜切换 |
| 项目管理 | 每个项目独立文件夹（main.md / plan.md / 资料 / 工作 / output），断点续作 |
| 质量保障 | 写作规则（绝对零度 / 八股化扫描 / 具体性检查）+ 27 项交付前检查清单 |

## 安装

将仓库内容复制到 Claude Code 的用户目录：

```bash
# skill 本体
cp -r skills/tavern-mmd ~/.claude/skills/

# 8 个斜杠指令
cp commands/*.md ~/.claude/commands/
```

> Windows 用户：`~/.claude` 即 `C:\Users\<用户名>\.claude`。
> 若不想占用全局指令命名空间，可只装 skill 本体——直接对话（如"给旧版 MMD 做个状态栏"）也能触发。

安装后**开启新会话**生效。

## 指令

指令分两个维度，自由组合：

### 平台指令（设定目标平台）

| 指令 | 平台 |
|---|---|
| `/mmd` | 当前 MMD（支持 `<script>`，其余按旧版保守处理） |
| `/oldmmd` | 旧版 MMD（禁 `<script>`，onerror 点火器 + ES5） |
| `/st` | 本地酒馆 SillyTavern（无限制） |

### 任务指令（执行制作）

| 指令 | 用途 |
|---|---|
| `/cardplan` | 角色卡标准工作流：弹窗快问快答 → plan.md → 执行 |
| `/cardplanmax` | 角色卡深度工作流：开放讨论 → 方案收敛 → 分节设计确认 → 分段执行 |
| `/worldbook` | 制作世界书，输出可导入 json |
| `/beautify` | 制作美化（全局美化 / 状态栏） |
| `/helpmmd` | 显示全部指令帮助 |

### 组合示例

```
/oldmmd → /beautify     # 旧版 MMD 状态栏（三段正则方案，产出手填清单）
/st → /worldbook        # 本地酒馆世界书（全字段，json 直接导入）
/mmd → /cardplanmax     # 从零共创一张当前 MMD 完整角色卡
```

## 产出物

| 产出 | 本地酒馆 | MMD（新旧同） |
|---|---|---|
| 角色卡 | chara_card_v3 json | 同左（MMD 支持 json 导入） |
| 世界书 | SillyTavern 世界书 json | 同左 |
| 正则 | 正则脚本 json（直接导入） | 手填清单 .md（逐条复制粘贴到平台 UI，附字符数统计） |

## 目录结构

```
skills/tavern-mmd/
├── SKILL.md                      # 入口：平台差异矩阵、任务路由、项目文件树规则
└── references/
    ├── platforms/                # 三平台技术规范
    │   ├── mmd.md                #   当前 MMD（script 差异 + 待验证标注）
    │   ├── mmd-old.md            #   旧版 MMD（红线分级、ES6 禁用清单、五大架构模式）
    │   └── sillytavern.md        #   本地酒馆（position 表、正则字段）
    ├── creation/                 # 创作规则
    │   ├── character.md          #   角色写作（绝对零度 / 八股化 / 具体性）
    │   ├── worldbook.md          #   世界书三阶段流程 + 条目规划表
    │   ├── opening.md            #   开场白三要素
    │   └── style.md              #   文风条目模板
    ├── beautify/                 # 美化方案
    │   ├── statusbar.md          #   KV V4.0 状态栏（三段正则模板 + 数据继承）
    │   ├── global-css.md         #   全局美化（uni-app 类名速查 + 主题变量）
    │   └── regex-rules.md        #   正则设计原则与平台限额
    ├── output/                   # 产出格式权威参考
    │   ├── card-json.md          #   chara_card_v3 完整字段
    │   ├── worldbook-json.md     #   独立世界书 json + 与卡内条目字段差异对照
    │   └── regex-output.md       #   正则 json / MMD 手填清单模板
    └── quality/
        └── checklist.md          # 交付前五层检查清单（27 项）

commands/                         # 8 个斜杠指令
```

## 平台差异矩阵（核心）

| 能力 | 本地酒馆 | 旧版 MMD | 当前 MMD |
|---|---|---|---|
| `<script>` | ✅ | ❌ → img onerror 点火器 | ✅（待验证） |
| ES6+ | ✅ | ❌ ES5 only | 保守用 ES5 |
| 正则导入 | json | 手动填写，≤30 条 | 同旧版 |
| 状态栏 | 任意方案 | `<status>` + 三段正则 + onerror | script 简化，可回退 |
| MVU/STScript | ✅ | ❌ | ❌（保守） |

> 当前 MMD 仅确认解禁 `<script>`，其余限制按旧版保守处理并标注"待验证"，实测后可更新 `references/platforms/mmd.md`。

## 致谢

- 旧版 MMD 平台限制与架构模式整理自社区MMD开发规范与类名定义 和 KV-Robust V4.0 澄清状态栏规范
- 创作质量体系（绝对零度原则、八股化检查等）提炼自 SillyTavern 社区角色卡创作实践

## License

MIT
