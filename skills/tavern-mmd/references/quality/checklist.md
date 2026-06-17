# 交付前检查清单

> 交付前逐项核对。MMD技术产出走全部五层；纯文字卡只走内容层+格式层。

## 内容层（全平台）
- [ ] 全文简体中文，无繁体/日文汉字
- [ ] 无占位符（某城市/某组织）
- [ ] 绝对零度：无主观评价、陈旧比喻、堆砌形容词
- [ ] 八股化扫描：无模糊词/微表情/语气描写/极端情绪词/"不是而是"句式/性格标签
- [ ] 开场白不替{{user}}发言行动
- [ ] 设定一致性：开场白/世界书/状态栏数据互不矛盾（角色名、时间线、数值）

## 格式层（全平台）
- [ ] json语法校验通过：python -m json.tool <文件> > /dev/null（能拦截裸换行/未转义引号/BOM）
- [ ] MMD导入json：replaceString内所有换行已转义为\n（非真实换行）、HTML双引号转义为\"、文件无UTF-8 BOM
- [ ] chara_card_v3：顶层与data字段同步；spec/spec_version正确
- [ ] MMD项目角色卡为v2格式：spec="chara_card_v2"、spec_version="2.0"、无group_only_greetings（MMD不识别v3）
- [ ] 世界书：蓝灯constant:true（key可为空）、绿灯constant:false有keys；递归控制按设计
- [ ] （整张图片卡）png 能被 stdlib 解出 `chara` chunk 并还原 JSON：跑 `python -m unittest test_make_card_image -v` 通过；v3 卡 `chara`+`ccv3` 都在，v2 卡仅 `chara`
- [ ] （整张图片卡）嵌入的卡规格与平台匹配：MMD=v2、本地酒馆=v3
- [ ] （整张图片卡）只导 PNG（jpg 已弃用：MMD 实测读不出卡数据）
- [ ] output/文件齐全且main.md索引已更新

## 结构层（MMD技术产出）
- [ ] 最外层容器有 onclick="event.stopPropagation()"
- [ ] img点火器在容器闭合</div>之前（旧版MMD）
- [ ] 数据区 style="display:none"
- [ ] 所有ID带时间戳后缀且同模块一致
- [ ] 填充位置有data-field/data-list标记

## 代码层（MMD技术产出）
- [ ] **（/oldmmd）全ES5**：无箭头函数/模板字符串/let/const/解构/展开/可选链
- [ ] **（/mmd）ES6可用**：img载体下实测全支持，推荐ES6；引擎默认ES6版、ES5版兜底
- [ ] 纯DOM API：无innerHTML字符串拼接、无style.cssText（两版都建议遵守，防实体化）
- [ ] **（/oldmmd）onerror/onclick内代码单行无换行**
- [ ] **（/mmd）onerror可多行可双引号**；onclick仅放行干净调用/引用表达式（`__fn()`/`eval(x.dataset.s)`），禁代码字面量与直接DOM赋值
- [ ] onclick复杂逻辑走轻主板data-s（eval(dataset.s)）或 window.__fn（/mmd 已复测可用）
- [ ] 无alert；无`<script>`（/oldmmd）；`<script>`（/mmd）仅用于定义window.__fn交互，**不做per-message状态栏自渲染**（引擎只能img onerror）

## 正则层（MMD）
- [ ] 总条数≤130
- [ ] 每条findRegex≤1000字符、replaceString≤20000字符（标注实测值）
- [ ] 导入json：含pageDepth/statusbar/beginning/regex_scripts四字段，每条正则id=-1
- [ ] **导入json通过 `python -m json.tool 文件 > /dev/null` 校验（拦截裸换行/未转义引号）**
- [ ] **已跑 `scripts/validate.py 文件 --platform <mmd|oldmmd>` 且 0 错误**（当前MMD务必用 `--platform mmd`，否则误报ES6/script；悬空标记会报错，必须补正则或删标记；旧版用 oldmmd 最严格）
- [ ] **文件无UTF-8 BOM**
- [ ] **回读 replaceString：解析后HTML无多余反斜杠（防双重转义，见 output/regex-output.md 2.4）**
- [ ] **注入HTML载荷内无换行符（防MMD空白条）：CSS/HTML模板写成单行无缝，标签间零换行；JSON转义的`\n`解析后仍是真实换行照样被渲染，必须从HTML源头消灭**
- [ ] （状态栏/美化）已 `scripts/build-preview.py 文件 --platform <平台>` 生成三面板沙箱，主AI 看过：①第一句话整合预览（选项菜单/图片/特殊美化是否并入）；②状态栏单独预览；③悬浮组件预览（侧边栏/悬浮球），并测过交互（点按钮/切标签/开侧边栏）
- [ ] **（状态栏/美化）已看过全景预览（`--mode both` 自动生成 `-panorama-` 文件）二次审核组合效果：所有组件同场无串台、底部输入框固定（滚动不动）、点发送出现用户气泡+占位AI气泡、状态栏选项点击能回填输入框**
- [ ] **（MMD状态栏/美化）已实机导入MMD看渲染——沙箱预览正常≠MMD正常，markdown管线把标签间换行补成空`<p>`撑出空白条，只有实机能复现，重点看内容最少的页有无横向空白条**
- [ ] 手填清单（备选交付时）：每条带用途、分框代码块、字符数、勾选框
- [ ] 替换链标记（Z_CONTENT等）首尾衔接无断裂
- [ ] **无正则触发标记交叉污染：任一正则的触发标记（`<ztl>`/`<css>`/`<悬浮球>`/`<status>`等）不得以字面形式出现在另一条正则的 replaceString 里（尤其 onerror/onclick 引擎内给模型的指令文本）**。否则该标记会被对应正则交叉替换成 HTML、破坏 JS 语法 → 引擎静默不执行。validate 查不出（单条都合法，是跨正则运行时污染）。修法：指令文本里的标记拆开拼，如 `'<zt'+'l>'`，运行时拼回完整、源码不含连续 token。详见 ../platforms/mmd.md「正则触发标记交叉污染」

## 雷达法状态栏（采用时附加）
- [ ] **（/oldmmd）引擎逻辑零双引号（统一单引号）、无星号（乘法改除法）**——onerror净化规避；**（/mmd）onerror可多行双引号，此项可放宽**
- [ ] 全半角鲁棒解析：分隔符正则兼容 `／｜：` 全角变体
- [ ] 兜底白名单：一/二/五类键名在列，四类快照排除在外
- [ ] 状态栏规则与引擎键名严格一致；规则中无任何UI机制描述
- [ ] 规则明确要求每轮输出`<ztl>`锚点
- [ ] 含防劫持巡检（探针自检+自毁）与剪枝探针（indexOf预筛）

## 样式层（MMD美化）
- [ ] 装饰性伪元素 pointer-events:none
- [ ] 交互元素 position:relative + z-index
- [ ] 全局美化：所有规则body.z-enabled前缀 + !important + 自有类前缀
- [ ] （风格库）已用 AskUserQuestion 问过视觉风格（基调组→风格或混搭），不是默认套用 #0d1117
- [ ] （风格库）配色已按 style-system.md 第1节 token 映射填入，未改动渲染管线/正则/JS
- [ ] （风格库）混搭或单点覆盖时跑过整体性检查（对比度≥4.5:1、明暗一致、圆角同档），覆盖项已记入 工作/美化决策.md

## 整卡输出形态（做整张角色卡时）
- [ ] 已用 AskUserQuestion 问过输出形态：内嵌正则 PNG / 内嵌正则 JSON / 分离式（卡+正则json+规则.md）
- [ ] （内嵌正则的整卡）状态栏**生成规则**已作为 constant=true（蓝灯）条目放入卡内 character_book——渲染正则≠生成规则，缺这条后续轮次状态栏不更新（见 output/card-json.md 第 8 节）
- [ ] （内嵌正则的整卡）卡内 regex_scripts 用 MMD 4 字段格式；分离式时独立正则 json 的 beginning/regex_scripts 与卡内 first_mes/regex_scripts 一致
- [ ] （单独美化/状态栏流程）默认交付含 正则 json + 规则.md（状态栏生成规则文档）
