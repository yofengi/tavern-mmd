# 正则配置规则

## 平台限制对照

| 项目 | 本地酒馆 `/st` | 当前MMD `/mmd` | MMD沙盒模式 `/mmdsandbox` |
|---|---|---|---|
| 导入方式 | json（regex_scripts数组） | json导入（MMD专用4字段格式）或平台UI手填 | json导入（**顶层恰好6键**）或创卡页「导入正则」逐条手填 |
| 顶层键 | 角色卡内 `regex_scripts` | 4 键 `pageDepth`/`statusbar`/`beginning`/`regex_scripts` | **6 键**：多 `chatVersion`（必须 `1`）/ `personality` |
| 条数 | 无硬限制（建议精简） | ≤130条 | ≤130条 |
| findRegex长度 | 无硬限制 | ≤1000字符 | **保守交付 ≤1000**（UI 显示 1000；源码归一常量 4096，双路径与超限语义待确证） |
| replaceString长度 | 无硬限制 | ≤20000字符 | ≤20000字符（编辑器上限，超了拆条） |
| `id` 取值 | 平台自管 | 时间戳类 | **必须负数**，导入时重编号 |
| `scriptName` 长度 | 无硬限制 | 无硬限制 | **保守交付 ≤20**（UI 显示 20；源码归一常量 200，双路径与超限语义待确证） |
| findRegex 形态 | `/pattern/flags` | **强制** `/pattern/flags`（实测铁律） | **强制** `/pattern/flags`（实机裸字面量不生效；worker 字面量分支只作逆向事实） |
| random标签 | 不支持（ST用{{random}}宏） | 支持`(random(a\|b\|c))`，多标签独立、可嵌$1捕获组 | 支持官方文字变量 `{{random:甲::乙::丙}}`；`(random(a\|b\|c))` 形态在沙盒模式**官方资料未提及**【待验证】 |

三平台正则json字段结构不同（本地酒馆13字段 vs 当前MMD 4字段 vs 沙盒模式6键顶层+4字段条目），均见 `../output/regex-output.md`。

### findRegex 形态：两个 MMD 路线都用 slash

**当前 MMD `/mmd`**：`findRegex` 必须写成 `/pattern/flags`。裸模式在平台正则控制台测试能过、实际聊天界面不替换；固定标记也写成 `/<status>/`。

**MMD 沙盒 `/mmdsandbox`**：worker 源码的 `classifyPattern` 确实存在两形态，但实机裸字面量 `{{probe}}` 不生效，改 `/{{probe}}/` 立即生效。宿主交给 worker 前仍有未逆向处理层，因此交付同样强制 slash：

| 写法 | 交付判定 | 行为 |
|---|---|---|
| `/{{hud}}/`、`/【图鉴】/` | ✅ 固定标记 | 缺 `g` 平台自动补 |
| `/pattern/flags` | ✅ 正则 | 合法 flags 仅 `gimsuy` |
| `{{hud}}` | ❌ 裸字面量 | worker 理论支持，实机不生效 |
| 语法错误的 `/…/` | ❌ bad-regex | 整条规则静默丢弃 |

固定标记不能重复；`findRegex` 也不要含 HTML 标签或独立保留字 `html/head/body/css`。完整源码与实机冲突见 `../platforms/mmd-sandbox.md` §7.1。

## 设计原则

1. **固定标记触发**：findRegex匹配AI输出的固定标记（如`<status>`），不匹配多变内容——数据变化不破坏匹配
2. **分段替换链**：超长replaceString按20000字符拆链：标记A→内容+标记B→内容+标记C（KV V4.0三段式即此模式）
3. **MMD字符数预算**：写完每条必须统计字符数并标注；接近限额（>18000）时预拆分
4. **命名规范**：[界面]xxx=渲染美化（markdownOnly）、[不发送]xxx=提示词隐藏（promptOnly）——本地酒馆json用此区分；MMD无此字段，手填清单中注明用途即可
5. **MMD随机化**：动态文本优先用random标签而非JS随机（不消耗JS预算且稳定）

## 常用正则模式

| 用途 | findRegex | replaceString |
|---|---|---|
| 状态栏触发 | `/<status>/` | 容器+CSS模板（见statusbar.md） |
| 链式注入 | `/<!-- Z_CONTENT -->/` | 主HTML+下一标记 |
| 隐藏标签不渲染 | `/<UpdateVariable>[\s\S]*?<\/UpdateVariable>/gs` | 空（本地酒馆配promptOnly） |
| 关键词包裹样式 | `/（引用\|强调内容）/g` | `<span class="z-q">$1</span>` |
| 全局美化激活 | 开场白固定标记或`/<beautify>/` | 激活器img+<style>全套 |

## 转义注意

- replaceString中的`"`在HTML属性内用`'`替代或实体化
- 两个 MMD 路线都强制 `/pattern/flags` slash literal；固定标记写成 `/<status>/`，不得交付裸模式。沙盒 worker 的字面量分支与实机冲突，不能用作交付依据
- slash literal 内若模式本身含 `/`，须转义为 `\/`；JSON 字符串层再按 JSON 规则转义反斜杠
- JSON 字符串里的 `</script>` 要写成 `<\/script>`，避免宿主页面提前截断（沙盒模式因 `<script>` 是一等公民，这条尤其常撞上）
- `$1`-`$9`捕获组两平台均可用于replaceString
