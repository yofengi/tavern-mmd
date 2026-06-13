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
- [ ] output/文件齐全且main.md索引已更新

## 结构层（MMD技术产出）
- [ ] 最外层容器有 onclick="event.stopPropagation()"
- [ ] img点火器在容器闭合</div>之前（旧版MMD）
- [ ] 数据区 style="display:none"
- [ ] 所有ID带时间戳后缀且同模块一致
- [ ] 填充位置有data-field/data-list标记

## 代码层（MMD技术产出）
- [ ] 全ES5：无箭头函数/模板字符串/let/const/解构/展开/可选链
- [ ] 纯DOM API：无innerHTML字符串拼接、无style.cssText
- [ ] onerror/onclick内代码单行无换行
- [ ] onclick仅极简指令（复杂逻辑走轻主板data-s或script）
- [ ] 无alert；无<script>（旧版MMD）

## 正则层（MMD）
- [ ] 总条数≤30
- [ ] 每条findRegex≤1000字符、replaceString≤20000字符（标注实测值）
- [ ] 导入json：含pageDepth/statusbar/beginning/regex_scripts四字段，每条正则id=-1
- [ ] **导入json通过 `python -m json.tool 文件 > /dev/null` 校验（拦截裸换行/未转义引号）**
- [ ] **已跑 `scripts/validate.py 文件 --platform oldmmd` 且 0 错误（一次性覆盖JSON合法/BOM/双重转义/红线/字符数）**
- [ ] **文件无UTF-8 BOM**
- [ ] **回读 replaceString：解析后HTML无多余反斜杠（防双重转义，见 output/regex-output.md 2.4）**
- [ ] （状态栏/美化）已 `scripts/build-preview.py 文件 --platform <平台>` 生成沙箱，主AI 看过渲染并测过交互（点按钮/切标签/开侧边栏）
- [ ] 手填清单（备选交付时）：每条带用途、分框代码块、字符数、勾选框
- [ ] 替换链标记（Z_CONTENT等）首尾衔接无断裂

## 雷达法状态栏（采用时附加）
- [ ] 引擎逻辑零双引号（统一单引号）、无星号（乘法改除法）
- [ ] 全半角鲁棒解析：分隔符正则兼容 `／｜：` 全角变体
- [ ] 兜底白名单：一/二/五类键名在列，四类快照排除在外
- [ ] 状态栏规则与引擎键名严格一致；规则中无任何UI机制描述
- [ ] 规则明确要求每轮输出`<ztl>`锚点
- [ ] 含防劫持巡检（探针自检+自毁）与剪枝探针（indexOf预筛）

## 样式层（MMD美化）
- [ ] 装饰性伪元素 pointer-events:none
- [ ] 交互元素 position:relative + z-index
- [ ] 全局美化：所有规则body.z-enabled前缀 + !important + 自有类前缀
