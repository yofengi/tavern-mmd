# 过时资产（已退役，不随 skill 分发）

本目录存放已从 `tavern-mmd` skill 中退役的文件，**仅作历史与考古参考**。目录不在 `skills/` 树内，不随 skill 分发，也不被任何指令或脚本读取。

> ⚠️ **不要用本目录里的任何内容回答「平台现在是什么行为」。** 这里的结论对应一个已冻结的旧平台基线，与当前 MMD、MMD 沙盒模式的实际行为存在系统性冲突（尤其是 `<script>`、ES6、`onclick` 净化、正则条数上限这几项）。要查当前行为，一律读 `skills/tavern-mmd/references/platforms/` 下的现行规范。

## 退役记录

**旧版MMD（`oldmmd`）平台 —— 2026-08-25 整体退役。**

原因：
1. 旧版 MMD 平台已冻结、不再更新，实际用户基本迁走。
2. 平台侧演进出了两个新形态：当前 MMD 主聊天页（支持 `<script>`、ES6）与 MMD 沙盒模式新聊天页（官方 SDK、`chatVersion: 1`），已完整覆盖旧版的全部使用场景。
3. 继续维护第四个平台分支会让平台矩阵、校验脚本与文档三处同时背上一份没人用的最严格约束。

退役后 skill 保留三个平台：`st`（本地酒馆 SillyTavern）/ `mmd`（当前 MMD）/ `mmdsandbox`（MMD 沙盒模式）。

## 目录内容

| 文件 | 原路径 | 原用途 |
|---|---|---|
| `mmd-old.md` | `skills/tavern-mmd/references/platforms/mmd-old.md` | 旧版MMD平台技术规范。红线分级表（零级 CSP / 一级致命 / 二级严重 / 三级交互 / 四级长度）、ES6+ 语法禁用清单、纯 DOM API 原则、正则系统限制与 `random` 标签、五大核心架构模式、调试诊断表、开发检查清单 |
| `oldmmd.md` | `commands/oldmmd.md` | `/oldmmd` 指令定义：把会话目标平台设为旧版MMD并加载上面那份规范 |

## 仍然有效的内容去哪了

退役前已把**与平台版本无关**的部分迁进 `skills/tavern-mmd/references/platforms/mmd.md`：

- `random` 标签三种用法与避坑 → `mmd.md` §8a
- 结构红线（`<img onerror>` 须在容器 `</div>` 之前、最外层 `onclick="event.stopPropagation()"`、重复 ID、单条 20000 字符）→ `mmd.md` §10.1
- 换行空白条陷阱（markdown 管线补空 `<p>`）→ `mmd.md` §10.1 红线块
- onerror 点火器骨架 → `mmd.md` §10.2（已改写为可多行、可 ES6 的当前写法）
- 轻主板 + 胖遥控器 → `mmd.md` §10.3
- 纯 CSS 切换（radio + `:checked`）→ `mmd.md` §10.4
- appendChild 置顶与避坑 5 条 → `mmd.md` §10.5
- 时间戳唯一 ID 与检查清单 → `mmd.md` §10.6
- 自动/懒加载不可靠、跨 img 状态丢失、`alert()` 静默失效、伪元素挡点击、纯 DOM API 建议 → `mmd.md` §10.7（标为「社区文档，待复验」）
- 调试诊断表 → `mmd.md` §12a

**故意没有迁移**的部分（只对已冻结的旧平台成立，在当前 MMD 上是错的）：

- ES6+ 语法禁用清单与「必须全面使用 ES5」——当前 MMD 已实测 ES6 全支持，且推荐 ES6
- 「禁止 `<script>` 标签」零级/一级红线——当前 MMD 的 `<script>` 可执行（边界见 `mmd.md` §4）
- 「`onerror`/`onclick` 内 JS 必须单行无换行」——当前 MMD 可多行
- 「`onerror` 内须单引号、禁双引号」的整体禁令——当前 MMD 的准确规则更细，见 `mmd.md` §2（属性用双引号包裹时内部禁裸双引号）
- 旧版开发检查清单里全部 ES5 / 禁 script 相关条目——当前平台的检查清单见 `skills/tavern-mmd/references/quality/checklist.md`
