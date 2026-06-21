# 影渲法（ShadowCast 2.0）现成资产

Shadow DOM 隔离动态渲染的可运行示例与生成器。方法原理见 `../../references/beautify/statusbar-shadowcast.md`。

> **2.0（引擎 VER=`sc2`，浏览器三路验证通过）**：① shadow→light DOM 降级链（attachShadow 不可用环境照常渲染，类名全程 `g3-` 前缀保证 light 路径零冲突）；② `adoptedStyleSheets` + 跨气泡缓存单 sheet；③ 事务式渲染（建好再挂载、异常回退纯净态 + 记 `window.g3LastError`）。来自吸收哨兵雷达法 sd3 卡的工程优点，细节见参考文档「2.0 强化」节。

## 文件清单

| 文件 | 说明 |
|---|---|
| `build_demo.py` | **简单状态栏生成器**（bar/text/list 三类型）。`FIELDS` 是单一真相源，改字段只动这里 → 自动生成引擎/模型协议/测试数据并断言键名一致 |
| `build_float.py` | **悬浮组件生成器**。可拖动悬浮球（点击展开菜单）+ 侧边栏抽屉，含跨组件交互（球菜单开侧边栏） |
| `状态栏-影渲法.mmd.json` | 简单状态栏成品（MMD 导入 json，4 字段），直接导入即可看 |
| `悬浮球侧边栏-影渲法.mmd.json` | 悬浮球+侧边栏成品，直接导入 |
| `状态栏-模型侧协议.md` | 简单状态栏的模型侧协议（蓝灯条目正文：要求 AI 每轮输出 `<g3>` 数据块） |
| `shadowcast_core.py` | **富 UI 共享引擎**（单一引擎源，雷达法移植）。12 种字段类型，`build_rpg.py`/`build_manor.py` 复用 |
| `build_rpg.py` | **西幻RPG 富状态栏生成器**（只含 config，引擎复用 core） |
| `build_manor.py` | **宅邸养成 富状态栏生成器**（只含 config，引擎复用 core） |
| `rpg-statusbar.mmd.json` + `RPG状态栏协议-蓝灯世界书.json` + `RPG协议.md` | 西幻RPG 成品：渲染正则 + 必配蓝灯协议 + 人读协议 |
| `manor-statusbar.mmd.json` + `宅邸状态栏协议-蓝灯世界书.json` + `宅邸协议.md` | 宅邸养成 成品：同上 |

### 富 UI 状态栏（雷达法移植）—— `shadowcast_core.py` + `build_rpg.py`/`build_manor.py`

把雷达法（light DOM 重构）的复杂 RPG/养成状态栏完整转进 Shadow DOM，删掉雷达法整套对抗哨兵补丁与信标转换器。`shadowcast_core.py` 提供比 `build_demo.py` 多得多的字段类型，浏览器三路实测全绿：

- **共享引擎 `shadowcast_core.py`**（单一引擎源）含全部富 UI 类型：`path`(面包屑) / `time`(时段高亮) / `bar`(带成因 tooltip) / `level`(XP条) / `stats`(属性网格) / `kvlist`(名↔说明 tooltip) / `lines`(编号记录) / `summary` / `turn`(角标) / `bag`(可切页◀▶) / `enemy`(敌人卡，volatile) / `option`(♥ero + 写回输入框)。
- **场景脚本 `build_rpg.py` / `build_manor.py`** 只提供 config（FIELDS + 主题 CSS + 标题），引擎全复用 core，改 bug 只动 core。改字段/配色只动场景脚本。
- 每套产 `*-statusbar.mmd.json`（渲染正则）+ `*-蓝灯世界书.json`（必配 constant=true 协议条目）——**两者必须一起导入，否则模型不持续吐数据块**。

> 想要简单固定面板 → `build_demo.py`（bar/text/list 三类型）。想要 RPG/养成那种富交互 → `shadowcast_core.py` + `build_rpg.py`/`build_manor.py`。

## 快速用法

**直接改造成品**：导入对应 `.mmd.json` 看效果，改里面的字段/配色。

**用生成器（推荐，改字段不易错）**：
```bash
python build_demo.py            # 改 FIELDS 后重新生成状态栏
python build_float.py           # 改 MENU_ITEMS/DRAWER_ITEMS/COLORS 后重新生成悬浮组件
python build_demo.py --check    # 只跑 guard 校验不写文件
```

### 改状态栏字段（build_demo.py 的 `FIELDS`）

每个字段一条声明：
```python
{"key":"hp","label":"生命","type":"bar","format":"当前/最大","example":"85/100","inherit":True}
```
- `type`：`bar`（进度条）/ `text`（文本）/ `list`（标签列表）
- `volatile:True`：情境字段（液态代谢）——只在该情境那轮输出、结束就消失、不向历史兜底（防高刺激信息污染上下文）。不加则为固态字段（每轮必出、缺失向历史兜底）。

### 改悬浮组件（build_float.py）

改顶部 `MENU_ITEMS`（菜单项+动作）、`DRAWER_ITEMS`（侧边栏条目）、`COLORS`（配色）即可。

## 铁律（生成器 guard 自动拦，手写才需自查）

1. **onerror="" 内部禁裸双引号**——内部字符串全单引号，CFG/CSS 用单引号 JS 字面量序列化（勿用 `json.dumps`），否则面板静默不渲染。
2. **禁字面 `[键=值]`**——用 `String.fromCharCode(91/93)` 拼方括号（含 CSS 选择器 `input[type=text]`），否则被数据信标转换器啃断。
3. **findRegex 带 `/.../ ` 斜杠**——否则实际聊天不替换。

> 注：onerror 引号内的裸 `<`/`>`/`=>` 经实机证实**无害**（HTML 属性值不解析标签），比较运算/for 循环/箭头函数可正常用，无需改写。

## 交付前

```bash
python ../../scripts/validate.py <你的.mmd.json> --platform mmd    # 须 0 错
python ../../scripts/build-preview.py <你的.mmd.json> --platform mmd # 浏览器看渲染
```
实机导入 MMD 最终验收（shadow/markdown/iframe 真实环境，沙箱复现不了全部）。
