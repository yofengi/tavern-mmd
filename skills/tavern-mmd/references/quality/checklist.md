# 交付前检查清单

> 交付前逐项核对。纯文字卡只走内容层+格式层。技术产出按平台分流：
>
> - **当前 MMD `/mmd`**：内容层 + 格式层 + 结构层 + 代码层 + 正则层 + 样式层（雷达法/运行时主题按采用情况附加）
> - **MMD沙盒模式 `/mmdsandbox`**：内容层 + 格式层 + 正则层 + **「沙盒模式」专节**（该节替代结构层／代码层／雷达法三节——那三节以 `img onerror` 为载体，沙盒禁用）
> - **本地酒馆 `/st`**：内容层 + 格式层
>
> 逐条前缀 `（/mmd）`／`（/mmdsandbox）`／`（/st）` 表示该条只对该平台成立；无前缀的是共用项。

## 内容层（全平台）
- [ ] 全文简体中文，无繁体/日文汉字
- [ ] 无占位符（某城市/某组织）
- [ ] 绝对零度：无主观评价、陈旧比喻、堆砌形容词
- [ ] 八股化扫描：无模糊词/微表情/语气描写/极端情绪词/"不是而是"句式/性格标签
- [ ] 开场白不替{{user}}发言行动
- [ ] 设定一致性：开场白/世界书/状态栏数据互不矛盾（角色名、时间线、数值）

## 格式层（全平台）
- [ ] json语法校验通过：python -m json.tool <文件> > /dev/null（能拦截裸换行/未转义引号/BOM）
- [ ] MMD导入json：replaceString内所有换行已转义为\n（非真实换行）、HTML双引号转义为\"、文件无UTF-8 BOM；`</script>` 写成 `<\/script>`
- [ ] （/st）chara_card_v3：顶层与data字段同步；spec/spec_version正确
- [ ] （/mmd）角色卡为v2格式：spec="chara_card_v2"、spec_version="2.0"、无group_only_greetings（当前MMD不识别v3）
- [ ] **（/mmdsandbox）没有角色卡json、没有PNG整卡这两样产出**——沙盒交付=导入正则json+独立persona文本（+可选独立世界书json）；官方明令禁PNG整卡，见 output/card-json.md 第9节
- [ ] 世界书：蓝灯constant:true（key可为空）、绿灯constant:false有keys；递归控制按设计
- [ ] （/mmd）世界书每条 `comment` ≤20字（中文一字算1、标点计入，超出平台截断）；跑 `validate.py --platform mmd` 无标题超限报错
- [ ] （/mmdsandbox）世界书条目标题同样按 ≤20 字写，但判罚降为 WARN 不阻断（限制来自创卡页UI仍在，官方校验脚本不查该项）；见 output/worldbook-json.md 5.2
- [ ] （整张图片卡）png 能被 stdlib 解出 `chara` chunk 并还原 JSON：跑 `python -m unittest test_make_card_image -v` 通过；v3 卡 `chara`+`ccv3` 都在，v2 卡仅 `chara`
- [ ] （整张图片卡）嵌入的卡规格与平台匹配：当前MMD=v2、本地酒馆=v3（沙盒模式不做整张图片卡）
- [ ] （整张图片卡）只导 PNG（jpg 已弃用：MMD 实测读不出卡数据）
- [ ] output/文件齐全且main.md索引已更新

## 结构层（当前MMD `/mmd` 技术产出）

> 本层与下面「代码层」「雷达法」都以 `img onerror` 为载体，**整层不适用沙盒模式**（沙盒禁 onerror 点火器、禁作者自写 `data-*`）。沙盒模式看本文最后的「沙盒模式」专节。

- [ ] 最外层容器有 onclick="event.stopPropagation()"（防点击冒泡到气泡触发编辑/复制）
- [ ] img点火器在最外层容器闭合`</div>`**之前**（放容器外 `img.closest()` 返回 null，整段JS一行都跑不起来；见 platforms/mmd.md §10.1）
- [ ] 数据区 style="display:none"
- [ ] 所有ID带时间戳后缀且同模块一致（同页多条消息重复ID会串台，是"第二次使用就失效"的根因）
- [ ] 填充位置有data-field/data-list标记

## 代码层（当前MMD `/mmd` 技术产出）
- [ ] **ES6可用**：img载体下实测全支持（7/7探针全绿），推荐ES6
- [ ] 纯DOM API：无innerHTML字符串拼接、无style.cssText（建议遵守，防实体化/被净化）
- [ ] **onerror可多行**；但**属性用双引号包裹时内部禁裸双引号**——内部任何 `"` 会提前闭合属性、img结构破坏、引擎静默不绑定（platforms/mmd.md §2 真红线）。修法：属性用单引号包裹 `onerror='...'`，或内部字符串统一单引号
- [ ] 注入的配置（CFG/CSS）用单引号 JS 字面量序列化，**勿用 `json.dumps`/`JSON.stringify`**（产双引号，撞上一条）
- [ ] inline onclick 使用已验证的干净形式 `window.__fn&&__fn()` 或 `eval(getElementById('FUNC').dataset.s)`，禁代码字符串字面量与直接DOM赋值
- [ ] onclick复杂逻辑走轻主板 `data-s`（`eval(getElementById('FUNC').dataset.s)`）、全局 `window.__fn`，或在 `img onerror` 内动态绑定 handler（已复测可用）
- [ ] 无alert；`<script>` 可执行但**不做per-message自渲染/定位**（拿不到 `document.currentScript`、同段script只加载一次；per-message渲染只能img onerror），可做 document-level 一次性 bootstrap 或定义全局 handler，重复入口必须复用既有实例

## 正则层（MMD 两平台共用）
- [ ] 总条数≤130
- [ ] 每条findRegex≤1000字符、replaceString<20000字符（标注实测值）；replaceString达到18000字符即预警并评估拆包
- [ ] **（/mmd）每条 `findRegex` 都是 `/pattern/flags` slash literal**；固定标记也包斜杠，无裸 `<css>` / `<status>` 值
- [ ] **（/mmdsandbox）每条 `findRegex` 也写 `/pattern/flags` slash 形态**；实机裸字面量 `{{hud}}` 不生效，虽与 worker 源码的字面量分支矛盾，交付仍以实机为准
- [ ] （/mmd）导入json：顶层恰好且仅有 `pageDepth/statusbar/beginning/regex_scripts` 四键；每条规则恰好且仅有 `id/scriptName/findRegex/replaceString` 四键，且 `id=-1`
- [ ] （/mmdsandbox）导入json：顶层恰好 `chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts` 六键，`id` 为负数——详见下方「沙盒模式」专节
- [ ] **导入json通过 `python -m json.tool 文件 > /dev/null` 校验（拦截裸换行/未转义引号）**
- [ ] **已跑 `scripts/validate.py 文件 --platform <mmd|mmdsandbox|st>` 且 0 错误**（`--platform` 省略时**默认 `mmd`**；审沙盒产出必须显式传 `mmdsandbox`，否则六键顶层会被按四键误报；悬空标记会报错，必须补正则或删标记）
- [ ] **文件无UTF-8 BOM**
- [ ] **回读 replaceString：解析后HTML无多余反斜杠（防双重转义，见 output/regex-output.md 2.4）**
- [ ] **注入HTML载荷内无换行符（防MMD空白条）：CSS/HTML模板写成单行无缝，标签间零换行；JSON转义的`\n`解析后仍是真实换行照样被渲染，必须从HTML源头消灭**
- [ ] （状态栏/美化）已 `scripts/build-preview.py 文件 --platform <mmd|mmdsandbox|st>`（必填，无默认）生成三面板沙箱，主AI 看过：①第一句话剩余预览（选项菜单/图片/特殊美化是否保留）；②状态栏单独预览；③悬浮组件预览（侧边栏/悬浮球），并测过交互（点按钮/切标签/开侧边栏）
- [ ] **（状态栏/美化）已看过全景预览（`--mode both` 自动生成 `-panorama-` 文件）二次审核组合效果：所有组件同场无串台、底部输入框固定（滚动不动）、点发送出现用户气泡+占位AI气泡、状态栏选项点击能回填输入框**
- [ ] **（MMD状态栏/美化）已实机导入MMD看渲染——沙箱预览正常≠MMD正常，markdown管线把标签间换行补成空`<p>`撑出空白条，只有实机能复现，重点看内容最少的页有无横向空白条**
- [ ] 手填清单（备选交付时）：每条带用途、分框代码块、字符数、勾选框
- [ ] 替换链标记（Z_CONTENT等）首尾衔接无断裂
- [ ] **无正则触发标记交叉污染：任一正则的触发标记（`<ztl>`/`<css>`/`<悬浮球>`/`<status>`等）不得以字面形式出现在另一条正则的 replaceString 里（尤其 onerror/onclick 引擎内给模型的指令文本）**。否则该标记会被对应正则交叉替换成 HTML、破坏 JS 语法 → 引擎静默不执行。validate 查不出（单条都合法，是跨正则运行时污染）。修法：指令文本里的标记拆开拼，如 `'<zt'+'l>'`，运行时拼回完整、源码不含连续 token。详见 ../platforms/mmd.md「正则触发标记交叉污染」

## 雷达法状态栏（当前MMD `/mmd` 采用时附加）

> 雷达法载体是 `img onerror`，**沙盒模式不可移植**（onerror点火器被官方明令禁止）。沙盒模式要同类功能改用「一条只放 `<script>` 的规则 + `sdk.on('message:mount')`」，只可参考本节的数据协议与信息架构。

- [ ] **引擎逻辑零双引号（统一单引号）**——理由**不是**净化器，而是 HTML 属性闭合：`onerror="..."` 双引号包裹时内部任何 `"` 会提前闭合属性、引擎静默不绑定。属性改用单引号包裹 `onerror='...'` 则内部可正常写双引号（platforms/mmd.md §2）
- [ ] **无星号（乘法改除法）**——理由**不是**净化器，而是正则跑在 markdown(vditor) **之前**，`*x*` 会被吃成斜体。渲进 Shadow DOM 则此项可省；light DOM 下当前MMD是否放宽【待验证】，按保守处理
- [ ] 全半角鲁棒解析：分隔符正则兼容 `／｜：` 全角变体
- [ ] 兜底白名单：一/二/五类键名在列，四类快照排除在外
- [ ] 状态栏规则与引擎键名严格一致；规则中无任何UI机制描述
- [ ] 规则明确要求每轮输出`<ztl>`锚点
- [ ] 含防劫持巡检（探针自检+自毁）与剪枝探针（indexOf预筛）

## 样式层（MMD美化）

> 下面「静态换肤 / 运行时主题 / 风格库」各项按当前 MMD 写。沙盒模式换肤只改 `[data-chat="root"]` 上的 14 个 `--chat-*` 变量（实测确证，官方手册只记 10 个），另见沙盒专节。

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

## 沙盒模式 `/mmdsandbox`（技术产出时替代上面「结构层／代码层／雷达法」三节）

> 沙盒模式的故障**全部不弹窗**：报错进页内调试面板（聊天页 URL 加 `?sdkDebug=1`）。下面每一条都是「错了页面上看不出异常」的类型，所以必须逐条核。平台细节见 platforms/mmd-sandbox.md。

### 结构与导入 JSON
- [ ] **`chatVersion: 1` 在顶层且值就是 1**——漏写/写0 = 落回旧聊天页，规则照装但 `sdk.*`、`[data-chat]`、舞台**全部不在**，表现是"按钮全不响应、样式对一半"且无报错
- [ ] 顶层**恰好 6 键** `chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts`，`pageDepth` 为 2
- [ ] 顶层**无禁用键** `role`/`presentation`/`worldbook`/`world_book`/`lorebook`/`lore_book`/`entries`/`characterBook`/`character_book`（出现即官方 ERROR）
- [ ] 每条规则 `id` 是**负数**（导入时会重编号）；四字段恰好 `id/scriptName/findRegex/replaceString`
- [ ] 长度全过：`statusbar`≤200、`beginning`≤**4000**、`personality`≤10000、条数≤130；常规交付按 `scriptName`≤20 / `findRegex`≤1000 / `replaceString`≤20000。源码归一常量分别可见 200 / 4096 / 100000，但只有 replaceString 的编辑器 20000／导入 100000 双路径与编辑器拒存语义已确证；scriptName/findRegex 的双路径仍待验证
- [ ] JSON 里 `</script>` 已写成 `<\/script>`（防宿主页面提前截断）
- [ ] **交付说明写明「必须新建卡，并在创卡页确认这张卡是新页」**——`chatVersion` 只在新建卡导入时被读取，给已存在的卡导入会被忽略，无法用导入把老卡升级成新页

### 匹配式与触发链
- [ ] **每个可见 HTML 的匹配式都能在 `statusbar` / `beginning` / 另一条规则的 `replaceString` 里找到**（链式触发算）——接不上则那块 UI 在页面上永不出现
- [ ] 只放 `<style>` / `<script>` 的规则，匹配式**故意谁都不引用**（`{{卡名-style}}`/`{{卡名-kit}}`）；它们装卡即被抽出，不需要被命中
- [ ] slash 形式的匹配式语法全部合法——**写成 `/…/` 但正则语法错 → 整条规则被静默丢弃**，不降级字面量，页面上看不出异常
- [ ] **字面量匹配式无重复**——规则按顺序跑，前一条换完全文后，后一条同串永远匹配不到
- [ ] 人设 `<输出格式>` 里的输出约定与这些匹配式对得上（模型写得出，规则才换得掉）

### 脚本与 SDK
- [ ] **`sdk.on` 写在脚本体里，不写进 `message:mount` 回调**——写进去则每挂一条气泡多订一份，同一件事触发很多次
- [ ] SDK **能力名与事件名逐字正确**（30 能力 / 12 合法事件）——**拼错既不报错也永不触发**，只能靠 `validate.py` 静态拦
- [ ] 无 `sdk.once` / `sdk.off`（**两者都不存在**）；需要一次性逻辑自己加幂等哨兵。`ready` **最后到且不补发**，首屏挂 `message:mount` / `message:done`
- [ ] **绝不把 `[data-chat="message-body"]` 当回复正文读**——空 AI 气泡挂上时里面是平台占位「消息生成中」。跟字用 `message:stream` 的 `msg.content`、收尾用 `message:done` 的 `msg.content`；`content` 空时**也不要退回去读 DOM**
- [ ] **无 `img onerror` 点火器、无 teapot 系写法**（`onerror` 图 / `window.teapot*` / CoC 注入）——官方明令禁止，改用「一条只放 `<script>` 的规则」
- [ ] 长期面板（地图/背包/小游戏）挂**舞台 `sdk.stage`**，不挂气泡（气泡滚出屏幕即销毁）
- [ ] `sdk.message.*` / `sdk.save.*` 等返回 Promise 的调用都有 `.catch`（失败时页面上没有任何提示）
- [ ] 不靠"必须攒进度"做唯一玩法——游客存档退出即失、登录不迁移，且**作者自己是登录态永远测不出这个差别**

### DOM 与 CSS
- [ ] **无作者自写 `data-*`**——会被净化删掉，随后所有依赖它的 `querySelector` 全查不到。自己的按钮/容器用 `class` 或 `id`
- [ ] 无 `iframe` / `link` / `meta` / `form` / `object` / `embed`（白名单外，会被删）
- [ ] **无全局 CSS 选择器** `*{}` / `html{}` / `body{}` / `:root{}` → 一律改 `[data-chat="root"]`
- [ ] HTML 顶格、无反引号包裹待渲染 HTML。平台实况会在 Markdown 前删除 4+ 空格，故“4 空格必变代码块”不是实测故障；仍顶格写以通过官方 WARN，并防其他 Markdown 路径差异
- [ ] 作者 z-index 落在 **3500–7999**（实测安全带）。依据：实测平台 `header`/`statusbar`/`messages`/`composer`/`author-stage` 全是 `z-index:auto` + `position:static`，手册所谓「平台 chrome 占 8000–8999」**不成立**；样式表穷举的真实占用是 `10090` snackbar / `9000` alert / `8200` message-menu / `8100` composer-snack / `8000` share-loading / `3000` stage-full / `2000` stage-content / `40` sdk-debug。3500 起是为避开舞台的 2000/3000，7999 止是为避开平台 8000+ 那几层（越界不会被拦，只会挡住平台长按菜单/提示/弹窗）
- [ ] 换肤只改 `[data-chat="root"]` 上的 14 个 `--chat-*` 变量（实测确证；官方手册只记 10 个，漏记 `--chat-input-bg`/`--chat-input-text`/`--chat-shortcut-text`/`--chat-more-item-bg`/`--chat-share-pick-bg`），**不写死 `#fff`**（深浅色切换才跟得上）；JS 涂色的订 `theme:change`
- [ ] 功能栏自己补 `flex-shrink:0` 与所需背景/高度；它的**正则输入静态且不随消息重跑**，动态值靠 JS 改 DOM。JS 插入的宿主节点实机可保留，但必须在 mount/done 回调内挂载并做幂等/宿主归一

### 审核与验证
- [ ] **已跑 `scripts/validate.py 文件 --platform mmdsandbox` 且 0 错误**，WARN 逐条看过并确认是有意保留
- [ ] 已跑 `scripts/build-preview.py 文件 --platform mmdsandbox --mode panorama --sandbox-profile chat` 与 `--sandbox-profile thin-preview`；事件顺序、历史补发、消息 scope、主题、舞台、存储降级和多轮更新的诊断无失败
- [ ] 沙盒全景首屏是实际聊天页：仿真控制/证据说明默认折叠，iframe 内无 `✓script` 审计角标，气泡辅助线默认关闭；header/messages/composer 与 left/right/message-extra/actions 槽位均存在
- [ ] 已在本地浏览器验桌面、窄屏竖向、横屏/软键盘：真实点击、输入、拖动、菜单、设置、stage、深浅色与截图结构无重叠；`--chat-viewport-height` 随 iframe resize/键盘 inset 更新，composer/input 始终可见；字号/颜色/间距用 computed style 复核，不凭压缩截图猜值
- [ ] 预览能力矩阵已看过：`exact` 可作日常回归，`conservative` 只作保守门禁，`probe-needed` 不当成平台事实
- [ ] **真实 MMD 不是日常默认回归环境**：AI 不自行登录账号、不把正式卡/公开卡当夹具。只有出现 `probe-needed` 平台边界，或用户授权最终人工验收时才回真实站；任何「保存编辑」/公开提交先确认对外影响
- [ ] 若做最终实站验收，已区分瘦预览真实行为：`save.get/save.keys` 会同步抛 `SdkError`，`cache.get` 返回 `undefined`，`composer.visible()` 与 stage 读能力仍可用；不能概括成“一律 NOT_SUPPORTED”

## 整卡输出形态（做整张角色卡时，当前MMD / 本地酒馆）

> 沙盒模式没有这道选择题：交付形态固定为「导入正则json + 独立persona文本（+可选独立世界书json）」，见 output/card-json.md 第 9 节。

- [ ] 已用 AskUserQuestion 问过输出形态：内嵌正则 PNG / 内嵌正则 JSON / 分离式（卡+正则json+规则.md）
- [ ] （内嵌正则的整卡）状态栏**生成规则**已作为 constant=true（蓝灯）条目放入卡内 character_book——渲染正则≠生成规则，缺这条后续轮次状态栏不更新（见 output/card-json.md 第 8 节）
- [ ] （内嵌正则的整卡）卡内 regex_scripts 用当前MMD的 4 字段格式；分离式时独立正则 json 的 beginning/regex_scripts 与卡内 first_mes/regex_scripts 一致
- [ ] （单独美化/状态栏流程）默认交付含 正则 json + 规则.md（状态栏生成规则文档）
