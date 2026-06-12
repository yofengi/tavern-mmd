# 正则配置规则

## 平台限制对照

| 项目 | 本地酒馆 | MMD（新旧同） |
|---|---|---|
| 导入方式 | json（regex_scripts数组） | json导入（MMD专用4字段格式）或平台UI手填 |
| 条数 | 无硬限制（建议精简） | ≤30条 |
| findRegex长度 | 无硬限制 | ≤1000字符 |
| replaceString长度 | 无硬限制 | ≤20000字符 |
| random标签 | 不支持（ST用{{random}}宏） | 支持`(random(a\|b\|c))`，多标签独立、可嵌$1捕获组 |

两平台正则json字段结构不同（本地酒馆13字段 vs MMD 4字段），均见 `../output/regex-output.md`。

## 设计原则

1. **固定标记触发**：findRegex匹配AI输出的固定标记（如`<status>`），不匹配多变内容——数据变化不破坏匹配
2. **分段替换链**：超长replaceString按20000字符拆链：标记A→内容+标记B→内容+标记C（KV V4.0三段式即此模式）
3. **MMD字符数预算**：写完每条必须统计字符数并标注；接近限额（>18000）时预拆分
4. **命名规范**：[界面]xxx=渲染美化（markdownOnly）、[不发送]xxx=提示词隐藏（promptOnly）——本地酒馆json用此区分；MMD无此字段，手填清单中注明用途即可
5. **MMD随机化**：动态文本优先用random标签而非JS随机（不消耗JS预算且稳定）

## 常用正则模式

| 用途 | findRegex | replaceString |
|---|---|---|
| 状态栏触发 | `<status>` | 容器+CSS模板（见statusbar.md） |
| 链式注入 | `<!-- Z_CONTENT -->` | 主HTML+下一标记 |
| 隐藏标签不渲染 | `<UpdateVariable>[\s\S]*?</UpdateVariable>` | 空（本地酒馆配promptOnly） |
| 关键词包裹样式 | `（引用\|强调内容）` | `<span class="z-q">$1</span>` |
| 全局美化激活 | 开场白固定标记或`<beautify>` | 激活器img+<style>全套 |

## 转义注意

- replaceString中的`"`在HTML属性内用`'`替代或实体化
- findRegex是字符串形式正则：本地酒馆json中写`/pattern/flags`格式（如`/<status>/g`）；MMD手填按平台输入框要求（默认全局匹配）
- `$1`-`$9`捕获组两平台均可用于replaceString
