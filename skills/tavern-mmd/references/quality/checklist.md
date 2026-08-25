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
- [ ] （MMD）世界书每条 `comment` ≤20字（中文一字算1、标点计入，超出平台截断）；跑 `validate.py --platform mmd` 无标题超限报错
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
- [ ] **（/mmd）onerror可多行可双引号**；inline onclick 使用已验证的干净形式 `window.__fn&&__fn()` 或 `eval(getElementById('FUNC').dataset.s)`，禁代码字符串字面量与直接DOM赋值
- [ ] onclick复杂逻辑走轻主板 `data-s`（`eval(getElementById('FUNC').dataset.s)`）、全局 `window.__fn`，或在 `img onerror` 内动态绑定 handler（/mmd 已复测可用）
- [ ] 无alert；无`<script>`（/oldmmd）；`<script>`（/mmd）**不做per-message自渲染/定位**（引擎只能img onerror），但可做 document-level 一次性 bootstrap 或定义全局 handler，重复入口必须复用既有实例

## 正则层（MMD）
- [ ] 总条数≤130
- [ ] 每条findRegex≤1000字符、replaceString<20000字符（标注实测值）；replaceString达到18000字符即预警并评估拆包
- [ ] MMD 每条 `findRegex` 都是 `/pattern/flags` slash literal；固定标记也包斜杠，无裸 `<css>` / `<status>` 值
- [ ] MMD 导入json：顶层恰好且仅有 `pageDepth/statusbar/beginning/regex_scripts` 四键；每条规则恰好且仅有 `id/scriptName/findRegex/replaceString` 四键，且 `id=-1`
- [ ] **导入json通过 `python -m json.tool 文件 > /dev/null` 校验（拦截裸换行/未转义引号）**
- [ ] **已跑 `scripts/validate.py 文件 --platform <mmd|oldmmd>` 且 0 错误**（当前MMD务必用 `--platform mmd`，否则误报ES6/script；悬空标记会报错，必须补正则或删标记；旧版用 oldmmd 最严格）
- [ ] **文件无UTF-8 BOM**
- [ ] **回读 replaceString：解析后HTML无多余反斜杠（防双重转义，见 output/regex-output.md 2.4）**
- [ ] **注入HTML载荷内无换行符（防MMD空白条）：CSS/HTML模板写成单行无缝，标签间零换行；JSON转义的`\n`解析后仍是真实换行照样被渲染，必须从HTML源头消灭**
- [ ] （状态栏/美化）已 `scripts/build-preview.py 文件 --platform <平台>` 生成三面板沙箱，主AI 看过：①第一句话剩余预览（选项菜单/图片/特殊美化是否保留）；②状态栏单独预览；③悬浮组件预览（侧边栏/悬浮球），并测过交互（点按钮/切标签/开侧边栏）
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
- [ ] 已明确选择静态换肤或当前 MMD 运行时主题包；需要 day/night/native、玩家微调或设置时已读 theme-runtime.md
- [ ] 静态换肤：所有规则body.z-enabled前缀 + !important + 自有类/ID/变量前缀；不声称停用等于 pristine restore
- [ ] 运行时主题：公共选择器只一份，day/night 只切根属性与 token，没有复制两套长选择器
- [ ] （风格库）已用 AskUserQuestion 问过视觉风格（基调组→风格或混搭），不是默认套用 #0d1117
- [ ] （风格库）先使用制作期规范 token，再映射到产物自有前缀运行时 token；旧三套方言只做局部 adapter
- [ ] （风格库）light/dark 成对检查正文、次要文字、控件、焦点与图标对比度；正文≥4.5:1
- [ ] （风格库）混搭或单点覆盖时跑过整体性检查，制作期覆盖已记入 工作/美化决策.md
- [ ] 玩家运行时覆盖写入 day/night 各自 overrides，不回写 preset 或 style-db

## 当前 MMD 运行时主题包（采用时附加）
- [ ] owner/version 租约唯一；同 owner/version 重复 bootstrap 复用实例，不同 owner 不静默覆盖
- [ ] head 中每类 style/link/meta 资源、设置面板、route supervisor、全局 API 均为单例
- [ ] 全运行时只有一个可断开的 MutationObserver；插件可 unregister，stop/destroy 后无 observer、监听或计时器残留
- [ ] 连续 bootstrap / 重复正则注入 / 同触发器多次执行后，租约、observer、面板和 head 资源计数仍各为1
- [ ] day→night→native 连续切换三轮；根属性、token、面板状态和分主题玩家设置每轮同步
- [ ] native restore 仅恢复本 owner 记录的 property delta；当前值被平台后写时不覆盖，且文案未宣称 pristine
- [ ] destroy 后清除本 owner 的根属性、delta、面板、head资源、监听、observer、计时器、API与租约；重复 destroy 不抛错
- [ ] route leave 执行 stop+restore，返回聊天页 reenter；SPA 整页替换根节点后可重建且资源仍单例
- [ ] 动态新增多条 AI 消息后全局资源不增长；per-message 状态栏仍各自渲染，不复制 runtime
- [ ] 设置按 day/night 分主题保存；“重置当前”只清当前 overrides，“全部重置”恢复默认且不改 preset
- [ ] 非法存储已测：截断JSON、null、数组、未知/未来schema、恶意键、未知token、超长值、存储拒绝/配额异常均降级且不阻断当前页切换
- [ ] 文本规范化是默认关闭的独立 opt-in；开启时明确不可逆边界，不混入 native restore 承诺
- [ ] 移动端已测窄屏、safe-area、软键盘开关、横屏、最长标签、触控目标与滚动/关闭，不遮输入框或发送按钮
- [ ] a11y已测 Tab/Shift+Tab/Enter/Space/Escape、focus-visible、可读名称、aria状态与 day/night 对比度
- [ ] localStorage 当前 MMD 实机矩阵已逐项记录：刷新、离开返回、同角色不同聊天、不同角色卡、App重启、账号切换、存储禁用/清空/配额异常；未测项明确标“待验证”

## 整卡输出形态（做整张角色卡时）
- [ ] 已用 AskUserQuestion 问过输出形态：内嵌正则 PNG / 内嵌正则 JSON / 分离式（卡+正则json+规则.md）
- [ ] （内嵌正则的整卡）状态栏**生成规则**已作为 constant=true（蓝灯）条目放入卡内 character_book——渲染正则≠生成规则，缺这条后续轮次状态栏不更新（见 output/card-json.md 第 8 节）
- [ ] （内嵌正则的整卡）卡内 regex_scripts 用 MMD 4 字段格式；分离式时独立正则 json 的 beginning/regex_scripts 与卡内 first_mes/regex_scripts 一致
- [ ] （单独美化/状态栏流程）默认交付含 正则 json + 规则.md（状态栏生成规则文档）
