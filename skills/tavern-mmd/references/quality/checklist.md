# 交付前检查清单

> 交付前逐项核对。纯文字卡只走内容层+格式层。技术产出按平台分流：
>
> - **当前 MMD `/mmd`**：内容层 + 格式层 + 结构层 + 代码层 + 正则层 + 样式层（雷达法/运行时主题按采用情况附加）
> - **当前 MMD 同层卡**：内容层 + 格式层 + 正则层 + **「同层卡」专节**；不套逐消息 onerror 结构/代码/雷达法，也不要求普通状态栏三面板预览。
> - **MMD沙盒模式 `/mmdsandbox`**：内容层 + 格式层 + 正则层 + **「沙盒模式」专节**（该节替代结构层／代码层／雷达法三节——那三节以 `img onerror` 为载体，沙盒禁用）
> - **沙盒同层卡 `/mmdsandbox`**：上述沙盒检查 + **「沙盒同层卡」专节**；不走旧页 Frame/Host 审核器，也不把 SBK 状态栏预览当完整同层页验收。
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
- [ ] MMD导入json：replaceString内所有换行已转义为\n（非真实换行）、HTML双引号转义为\"、文件无UTF-8 BOM；JS 字符串嵌入 HTML script 时保护内部 `</script>`，不把整个 Frame 文档的结束标签全部转义
- [ ] （/st）chara_card_v3：顶层与data字段同步；spec/spec_version正确
- [ ] （/mmd、/mmdsandbox）角色卡为v2格式：spec="chara_card_v2"、spec_version="2.0"、无group_only_greetings（MMD系不识别v3）
- [ ] **（/mmdsandbox）交付形态已按 output/card-json.md §8.1 弹窗选定**：路线A（v2整卡 PNG/JSON，含内嵌世界书与正则）或路线B（6键正则json+独立persona文本+可选独立世界书json）。**沙盒能导v2整卡**（编辑页导入按新卡处理），旧版「禁PNG整卡、固定三件套」已更正
- [ ] **（/mmdsandbox）交付说明里写明两条前置铁律**：①导入走**新建卡**；②**首次保存前**在创卡页把「新版聊天页」选成**使用新版**（首次保存后永久不可改）。漏②则规则装上但 sdk.*／[data-chat]／舞台全不在，且页面无任何报错
- [ ] 世界书：蓝灯constant:true（key可为空）、绿灯constant:false有keys；递归控制按设计
- [ ] （/mmd）世界书每条 `comment` ≤20字（中文一字算1、标点计入，超出平台截断）；跑 `validate.py --platform mmd` 无标题超限报错
- [ ] （/mmdsandbox）世界书条目标题同样按 ≤20 字写，但判罚降为 WARN 不阻断（限制来自创卡页UI仍在，官方校验脚本不查该项）；见 output/worldbook-json.md 5.2
- [ ] （整张图片卡）png 能被 stdlib 解出 `chara` chunk 并还原 JSON：跑 `python -m unittest test_make_card_image -v` 通过；v3 卡 `chara`+`ccv3` 都在，v2 卡仅 `chara`
- [ ] （整张图片卡）嵌入的卡规格与平台匹配：当前MMD=v2、**沙盒模式=v2**、本地酒馆=v3（沙盒同样可做整张图片卡）
- [ ] （整张图片卡）只导 PNG（jpg 已弃用：MMD 实测读不出卡数据）
- [ ] output/文件齐全且main.md索引已更新

## 结构层（当前MMD `/mmd` 逐消息组件）

> 本层与下面「代码层」「雷达法」都以 `img onerror` 为载体，**整层不适用沙盒模式**（沙盒禁 onerror 点火器、禁作者自写 `data-*`）。沙盒模式看本文最后的「沙盒模式」专节。

- [ ] 最外层容器有 onclick="event.stopPropagation()"（防点击冒泡到气泡触发编辑/复制）
- [ ] img点火器在最外层容器闭合`</div>`**之前**（放容器外 `img.closest()` 返回 null，整段JS一行都跑不起来；见 platforms/mmd.md §10.1）
- [ ] 数据区 style="display:none"
- [ ] 所有ID带时间戳后缀且同模块一致（同页多条消息重复ID会串台，是"第二次使用就失效"的根因）
- [ ] 填充位置有data-field/data-list标记

## 代码层（当前MMD `/mmd` 逐消息组件）
- [ ] **ES6可用**：img载体下实测全支持（7/7探针全绿），推荐ES6
- [ ] 纯DOM API：无innerHTML字符串拼接、无style.cssText（建议遵守，防实体化/被净化）
- [ ] **onerror可多行**；但**属性用双引号包裹时内部禁裸双引号**——内部任何 `"` 会提前闭合属性、img结构破坏、引擎静默不绑定（platforms/mmd.md §2 真红线）。修法：属性用单引号包裹 `onerror='...'`，或内部字符串统一单引号
- [ ] 注入的配置（CFG/CSS）用单引号 JS 字面量序列化，**勿用 `json.dumps`/`JSON.stringify`**（产双引号，撞上一条）
- [ ] inline onclick 使用已验证的干净形式 `window.__fn&&__fn()` 或 `eval(getElementById('FUNC').dataset.s)`，禁代码字符串字面量与直接DOM赋值
- [ ] onclick复杂逻辑走轻主板 `data-s`（`eval(getElementById('FUNC').dataset.s)`）、全局 `window.__fn`，或在 `img onerror` 内动态绑定 handler（已复测可用）
- [ ] 无alert；`<script>` 可执行但**不做per-message自渲染/定位**（拿不到 `document.currentScript`、同段script只加载一次；per-message渲染只能img onerror），可做 document-level 一次性 bootstrap 或定义全局 handler，重复入口必须复用既有实例

## 正则层（MMD 两平台共用）
- [ ] 总条数≤130
- [ ] 每条findRegex≤1000字符、replaceString≤20000字符（标注实测值）；replaceString达到18000字符即预警并评估拆包
- [ ] **（/mmd）每条 `findRegex` 都是 `/pattern/flags` slash literal**；固定标记也包斜杠，无裸 `<css>` / `<status>` 值
- [ ] **（/mmdsandbox）每条 `findRegex` 统一写 `/pattern/flags` slash 形态**（约定，为跨平台一致）；裸字面量实机也生效（卡 64304 A/B 2026-08-30），校验器对它出 WARN 不出 ERROR，不阻断交付
- [ ] （/mmd）导入json：顶层恰好且仅有 `pageDepth/statusbar/beginning/regex_scripts` 四键；每条规则恰好且仅有 `id/scriptName/findRegex/replaceString` 四键，且 `id=-1`
- [ ] （/mmdsandbox）导入json：顶层恰好 `chatVersion/pageDepth/statusbar/beginning/personality/regex_scripts` 六键，`id` 为负数——详见下方「沙盒模式」专节
- [ ] **导入json通过 `python -m json.tool 文件 > /dev/null` 校验（拦截裸换行/未转义引号）**
- [ ] **已跑 `scripts/validate.py 文件 --platform <mmd|mmdsandbox|st>` 且 0 错误**（`--platform` 省略时**默认 `mmd`**；审沙盒产出必须显式传 `mmdsandbox`，否则六键顶层会被按四键误报；悬空标记会报错，必须补正则或删标记）
- [ ] **文件无UTF-8 BOM**
- [ ] **回读 replaceString：解析后HTML无多余反斜杠（防双重转义，见 output/regex-output.md 2.4）**
- [ ] **组件根容器已写 `white-space: normal`（防MMD空白条，一行治本）**：气泡容器 `.content` 带 `white-space:pre-line`，标签间换行会被保留成真实换行、每个撑一行行高（实测 102px vs 应有 51px）。走 Shadow DOM 的写 `:host{white-space:normal}`（继承属性穿边界，shadow **不免疫**）。~~`p:empty`/`br{display:none}`~~ 无效已废弃。见 ../platforms/mmd.md §13
- [ ] **逐消息 light DOM 注入HTML载荷内无换行符（第二道防线）：CSS/HTML模板写成单行无缝，标签间零换行；JSON转义的`\n`解析后仍是真实换行照样被渲染，必须从HTML源头消灭**
- [ ] （状态栏/美化）已 `scripts/build-preview.py 文件 --platform <mmd|mmdsandbox|st>`（必填，无默认）生成三面板沙箱，主AI 看过：①第一句话剩余预览（选项菜单/图片/特殊美化是否保留）；②状态栏单独预览；③悬浮组件预览（侧边栏/悬浮球），并测过交互（点按钮/切标签/开侧边栏）。**MMD 的三面板自 2026-08-28 起带实测平台外壳**（真实气泡容器链 + 29 个主题变量 + `white-space:pre-line` + rem 缩放律，扁平版不含顶栏/底栏/弹窗），所以单组件阶段就能查出空白条与 `var(--*)` 失效
- [ ] **（状态栏/美化）已看过全景预览（`--mode both` 自动生成 `-panorama-` 文件）二次审核组合效果：所有组件同场无串台、底部输入框固定（滚动不动）、点发送出现用户气泡+占位AI气泡、状态栏选项点击能回填输入框**
- [ ] **（MMD全局美化）已逐个打开弹窗面板自查**：工具栏「弹窗仿真」六个（模型设置/对话设置/总结剧情/用户人设/分享/AI帮聊说明）+「＋更多面板」「指令栏切换」全开一遍，确认无露白、无错色、组件未被压住。uview `.u-popup__content` 基线是**白底**，漏改哪个面板哪个露白；对话设置底色在 content 内联 style 上、用户人设走 `--lo*`（18 个全未定义、改了没反应）、`+` 面板让底栏 105px→317px。详见 ../platforms/mmd.md §13.6
- [ ] **（MMD状态栏/美化）已实机导入MMD看渲染**——MMD 全景预览自 2026-08-28 起按实机 CSSOM 复刻真实气泡（含 `white-space:pre-line`、真实 padding/圆角/主题变量、rem 缩放律），**空白条已能在预览阶段复现并拦下**；但预览仍不模拟 markdown 管线本身（`*星号*` 被吃、反引号内 HTML 变文本等），交付前仍须实机确认一次
- [ ] 手填清单（备选交付时）：每条带用途、分框代码块、字符数、勾选框
- [ ] 替换链标记（Z_CONTENT等）首尾衔接无断裂
- [ ] **无正则触发标记交叉污染（同层卡构建器经校验的单向下一跳除外）：任一正则的触发标记（`<ztl>`/`<css>`/`<悬浮球>`/`<status>`等）不得以字面形式出现在另一条正则的 replaceString 里（尤其 onerror/onclick 引擎内给模型的指令文本）**。否则该标记会被对应正则交叉替换成 HTML、破坏 JS 语法 → 引擎静默不执行。validate 查不出（单条都合法，是跨正则运行时污染）。修法：指令文本里的标记拆开拼，如 `'<zt'+'l>'`，运行时拼回完整、源码不含连续 token。详见 ../platforms/mmd.md「正则触发标记交叉污染」

## 同层卡专节（当前 MMD `/mmd` 采用独立页面时）

- [ ] 已确认 `chatVersion:0`/缺省，五项架构决策已记录；没有因为「存档/背包/按钮」就改为新页。
- [ ] 本地 Mock 与交付 native 配置分开；正式包不会发送给 Mock。没有未经验证的私有后端直连。
- [ ] 需要模型功能时已使用 mmd-model-controls.md 模块，模型/设置数据来自原生快照，操作带 revision，切换已核对选中结果；关闭设置不声称撤销。--no-models 与 --no-engine 独立验证。
- [ ] 原生操作按 capability 显示；核心发送保护已有草稿，未镜像功能可返回原生界面；accepted 不冒充生成结束或服务端保存。
- [ ] 单一 appId 实例；重复注入、新版本、隐藏返回、关闭、路由离开/返回、账号与会话切换均有验证。
- [ ] Frame 隔离、握手、唯一端口、请求白名单、上下文失效、超时不重发；Frame 不拿宿主凭据、不执行 AI HTML。
- [ ] 父文档元素 ID 唯一且按钮阻止事件冒泡；Frame 可使用文档内局部 ID，规则 `id=-1`。
- [ ] 采用引擎时：规则先结算、存档回读成功后显示；重复动作不重复奖励；随机状态持久化；AI 不另维护同一数值真值。
- [ ] 存档作用域可靠；未知作用域明确停用；坏档/容量错误不静默新开局；迁移和导入先备份；旧 epoch 结果不跨读档写入；多标签并发有锁。
- [ ] 对外叙述提交先落台账；超时与退出不等于服务端取消，重复操作不自动再次请求模型。
- [ ] `validate.py --platform mmd` 与 `verify_same_layer.py` 通过；回读分片并核对链路、SHA-256、UTF-16 字符数与文件清单；与其他规则合包后重新构建验证。
- [ ] 本地引擎/存档测试与独立浏览器测试通过；看过桌面和窄屏截图，测试滚动、发送、导入导出及返回原生。
- [ ] 本地预览、真实 MMD、物理手机分别记录证据。未实测标 `NOT RUN`，不能将浏览器模拟视口称为手机实测；真实站测试按用户已有授权范围执行。
- [ ] 同层运行包与整卡 v2 PNG 区分；带游戏的世界书只规定规则权威与 AI 叙述边界；未向玩家承诺自动跨设备同步。

## 沙盒同层卡专节（新页 `/mmdsandbox` 自绘网页时）

制作方法见 [沙盒同层卡](../creation/sandbox-same-layer-card.md)。

- [ ] 已记录 `chatVersion:1`、舞台 content/full、SDK 连接、数据权威与存档位置；没有复用旧页 bridge/61 项能力表或嵌套作者 iframe。
- [ ] 原样交付包恰好六键或按 v2 整卡规范封装；导入说明包含新建卡 + 首次保存前使用新版，不把正则包称为完整角色卡。
- [ ] 首屏不依赖 ready/顶层 DOM，初始化幂等；重复脚本不叠 SDK 订阅，不调用 on 返回值、off 或 once。
- [ ] `{id,serverId,role,content}` 能进入消息投影，不依赖 state；stream 是与气泡同步的已揭示累计正文，替换而不重复追加，不假定提前拿到完整回复；done 补发不重复结算，unmount 不当删除。
- [ ] 编辑使用非空 serverId；历史投影不宣称完整服务端历史；AI 正文经转义或净化，不作为可信可执行 HTML。
- [ ] 自有输入框与原生输入框归属明确；点击当帧发送，BUSY/失败保留草稿，超时不自动重发，不以 send 返回冒充生成或保存完成。
- [ ] 无载荷 conversation:switch 会清投影并使旧异步结果/待写档失效；无载荷 theme:change 可正确更新。未编造会话 ID。
- [ ] visible 判断开关；作者关闭路径不等待 stage:close；关闭后新消息不抢开舞台；原生返回/同层重开均可用，播放器隐藏后暂停并在 dispose 释放。
- [ ] save 同步异常和异步失败均有反馈；不硬编码 10 key；逻辑清档不声称释放 key；存档不自动进入 AI 上下文，也不承诺自动随剧情回溯。
- [ ] 分片回读/完整性/混版/重注入与全部规则预算已验；生产包无开发 Host、Mock、开发地址或 ESM 残留；外部资源按各自 CSP 通道验收。
- [ ] chat/thin-preview 两套新页全景中测试原样载荷，桌面/窄屏页面操作与失败路径通过；模型/会话管理等无公开 SDK 契约的功能提供原生入口。
- [ ] content/full/closed 的 DOM 属性与 SDK visible 一致；关闭/重开/切会话保留作者标记节点，content 视口变化后仍对齐消息区。作品自行清会话状态，不靠平台清作者 DOM。
- [ ] 本地 BUSY 注入与 stream/done 已测：pending/生成中拒绝并保留草稿，解除后不自动发送；空消息 INVALID_ARGS，省略文本发送原生草稿且成功后清理；无真实 AI 调用不冒充生成验收。
- [ ] 若做宿主换肤，按 [宿主指南](../beautify/sandbox-host-styles.md) 验 iframe 外样式、原生入口与未知分支标注；thin 不模拟宿主，运行时停用阅读主题不承诺撤销静态皮肤。
- [ ] 真实 MMD 冷启动/切会话迟到事件、真实历史同步、跨设备保存、实体手机各自记录证据，未执行标 NOT RUN。本地 Mock PASS 不提升为实站结论。

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

> 下面「静态换肤 / 运行时主题 / 风格库」各项按当前 MMD 写。沙盒阅读主题覆盖 29 个 `--chat-*` 颜色变量，宿主皮肤另走 21 个开放 `[data-host]` 根的静态 CSS 抽取过滤；两条通路见沙盒专节，不套旧页运行时桥接。

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
- [ ] SDK 能力/事件名符合 30 能力、12 事件公开表，错误处理列明 7 个公开码且能显示未知码；历史 UI_BUSY 等内部记录不扩张公开 API
- [ ] 无公开 `sdk.once`/`sdk.off`，一次性逻辑自己幂等。ready 最后到且不补发属于 2026-08-26 历史观察；兼容首屏用 mount/done，不只依赖 ready，未复验不宣称新平台结论
- [ ] 不把生成中 DOM 占位当回复。stream 的 content 是与气泡同步的已揭示累计文字，替换显示而不重复追加；最终正文读 done；content 为空不退回读 DOM，也不假定提前获得完整原始回复
- [ ] **无 `img onerror` 点火器、无 teapot 系写法**（`onerror` 图 / `window.teapot*` / CoC 注入）——官方明令禁止，改用「一条只放 `<script>` 的规则」
- [ ] 长期面板（地图/背包/小游戏）挂**舞台 `sdk.stage`**，不挂气泡（气泡滚出屏幕即销毁）
- [ ] `sdk.message.*` / `sdk.save.*` 等返回 Promise 的调用都有 `.catch`（失败时页面上没有任何提示）
- [ ] 不靠"必须攒进度"做唯一玩法——游客存档退出即失、登录不迁移，且**作者自己是登录态永远测不出这个差别**
- [ ] `sdk.message.send` 有**并发防护**：发送/生成未结束时再调会**立刻拿 `BUSY`（不排队、不占限频）** → 保留草稿、提示用户稍后自己发，**不自动重试**；且**没有在 `message:done` 里无条件 `send`**（自问自答死循环）
- [ ] 用到 `sdk.vars.*` / `vars:change`（平台状态变量，mmd-sandbox.md §14）时：**官方 contract.json 未收录其签名** → 校验器出 WARN 不出 ERROR，但必须确认**签名不是编造的**（要有用户提供的新版 SDK/导出样本），交付说明写明「状态读写待接入」。没有样本时优先走「AI 正文吐 `[状态]` 块 + 脚本解析」这条已确证的路
- [ ] **没有自造状态标签去跟平台内部 `<abc_vars>` 抢，也没有写正则藏它**（平台接口已把它从正文拆出，正文本来就是干净剧情）；`varSchema` / `varInit` 这类推测字段**没有**被塞进 6 键正则包
- [ ] 同一个剧情数值**没有**同时由平台状态表和 `sdk.save` 各存一份（两份真值必然漂移，回溯时只有一份跟着回）

### DOM 与 CSS
- [ ] **无作者自写 `data-*`**——会被净化删掉，随后所有依赖它的 `querySelector` 全查不到。自己的按钮/容器用 `class` 或 `id`
- [ ] 无 `iframe` / `link` / `meta` / `form` / `object` / `embed`（白名单外，会被删）
- [ ] **无全局 CSS 选择器** `*{}` / `html{}` / `body{}` / `:root{}` → 一律改 `[data-chat="root"]`
- [ ] HTML 顶格、无反引号包裹待渲染 HTML。平台实况会在 Markdown 前删除 4+ 空格，故“4 空格必变代码块”不是实测故障；仍顶格写以通过官方 WARN，并防其他 Markdown 路径差异
- [ ] 作者层级按组件用途和目标版本验收。历史样式的 content/full 舞台为 2000/3000，需浮在舞台上的 SBK 面板默认 3500–7999，原生消息菜单/提示等在 8000+；这不是所有元素唯一安全带。舞台不能压住所需抽屉/原生返回，iframe 内提高 z-index 也不能越过宿主弹窗
- [ ] 沙盒阅读主题的 29 个 `--chat-*` 颜色变量以共享注册表为准（历史观测 2026-08-29）：气泡/整页 10 + 底栏/浮层 18 + 别名 1；composer/shortcut/input/modal 均覆盖，保留原别名，不将只读几何值 `--chat-viewport-height`/`--rpx` 当颜色配置；深浅色各验可读性
- [ ] 底栏/输入框/iframe 浮层使用独立的 composer/shortcut/input/modal 变量，不假设气泡三色自动带动；宿主弹窗的静态 data-host 样式单列，不假定 iframe 的 `--sbk-*` 自动继承或动态转发。固定色不称自动深浅适配，不替换平台图标/文案
- [ ] **4 个别名不要写死**：`--chat-bubble-user-bg`/`--chat-bubble-ai-bg` → `var(--chat-bg)`、`--chat-bubble-text` → `var(--chat-text)`、`--chat-more-item-bg` → `var(--chat-modal-surface)`。写死会切断传导链（之后改基色它们不再跟随）
- [ ] `--chat-viewport-height` **不算样式表变量、不要用 CSS 覆盖**：它是 JS 写在 root 上的内联 style（`clientHeight − 键盘 inset`，随 `visualViewport` 实时更新），内联优先级压过样式表；要读就 `getComputedStyle` 或直接 `var(--chat-viewport-height)`
- [ ] 功能栏自己补 `flex-shrink:0` 与所需背景/高度；它的**正则输入静态且不随消息重跑**，动态值靠 JS 改 DOM。JS 插入的宿主节点实机可保留，但必须在 mount/done 回调内挂载并做幂等/宿主归一

### 宿主弹窗样式（配置 data-host / hostStyles 时）
- [ ] 根名符合 [21 根契约](../../scripts/fixtures/mmdsandbox/host-contract.json)（19 + summary + summary-confirm），每个选择器最左为开放的精确 data-host；无作者根前缀、混合非宿主选择器或树外兄弟范围
- [ ] 未触及充值、SDK 授权、断联、启动加载和登录区域；不读写宿主 DOM，不新增私有接口，不用假控件代替平台真实保存/权限
- [ ] 文档平铺/无 url 声明限制、测试站 `:has()` 观察、本地 parser 的额外保守拒绝分别注明；没有将“CSS 零过滤”扩展到宿主通路，也没有把 parser 拒绝说成平台绝对禁止
- [ ] summary 根就在面板本体；根内编辑/锚点使用已观察的 `.summary-ov-edit`/`.summary-ov-anchor`；summary-confirm 位于树外，独立根样式，无虚构内部 class
- [ ] `hostStyles:["path.css"]` 路径相对配置，输出独立静态 style；默认按需开启，不塞进 base.css/动态阅读主题样式。preset/停用仅控制阅读覆盖，未承诺撤销宿主皮肤或验证动态转发
- [ ] chat 全景只把抽取 CSS 注入 iframe 外，普通沙盒 CSS 留在内层；thin 不模拟宿主。已观察夹具与未知根占位分别标明，21 根索引不冒充 21 根完整业务验收

### 审核与验证
- [ ] **已跑 `scripts/validate.py 文件 --platform mmdsandbox` 且 0 错误**，WARN 逐条看过并确认是有意保留
- [ ] 已跑 `scripts/build-preview.py 文件 --platform mmdsandbox --mode panorama --sandbox-profile chat` 与 `--sandbox-profile thin-preview`；事件顺序、历史补发、消息 scope、主题、舞台、存储降级和多轮更新的诊断无失败
- [ ] 沙盒全景首屏是实际聊天页：仿真控制/证据说明默认折叠，iframe 内无 `✓script` 审计角标，气泡辅助线默认关闭；header/messages/composer 与 left/right/message-extra/actions 槽位均存在
- [ ] 已在本地浏览器验桌面、窄屏竖向、横屏/软键盘：真实点击、输入、拖动、菜单、设置、stage、深浅色与截图结构无重叠；`--chat-viewport-height` 随 iframe resize/键盘 inset 更新，composer/input 始终可见；字号/颜色/间距用 computed style 复核，不凭压缩截图猜值
- [ ] 预览能力矩阵已看过：`exact` 可作日常回归，`conservative` 只作保守门禁，`probe-needed` 不当成平台事实
- [ ] 证据先匹配版本、日期、环境；ready、save.remove、配额、外链加载的历史冲突保留日期，当前部署未复验就明说。旧沙盒未见配额校验不代表服务端无限额，set(null) 逻辑清档不等于释放 key
- [ ] **真实 MMD 不是日常默认回归环境**：AI 不自行登录账号、不把正式卡/公开卡当夹具。只有出现 `probe-needed` 平台边界，或用户授权最终人工验收时才回真实站；任何「保存编辑」/公开提交先确认对外影响
- [ ] 若做最终实站验收，已区分瘦预览真实行为：`save.get/save.keys` 会同步抛 `SdkError`，`cache.get` 返回 `undefined`，`composer.visible()` 与 stage 读能力仍可用；不能概括成“一律 NOT_SUPPORTED”
- [ ] **（仅公开发布的卡才卡这条；私人自用卡与纯草稿跳过）** 固定传输字符 = 人设 + 「已启用 且 常驻 且 概率 100%」的世界书正文，落在 **2000–15000 含边界**；`beginning` **≥200 字**（与 4000 上限夹成 200–4000）。关键词条目、停用条目、概率不足 100% 的常驻条目不计入；**没有用空白换行凑数**。详见 mmd-sandbox.md §10.3
- [ ] 单条世界书 `content` **≤3000 字**（字段级硬限；与「单条 ≤800」的成本软建议是两件事）

## 整卡输出形态（做整张角色卡时，三平台通用）

> **沙盒模式同样有这道选择题**（旧版写「沙盒没有、固定三件套」已更正）：它能导 v2 整卡，见 output/card-json.md 第 8-9 节。沙盒额外要核「新建卡 + 首次保存前选新版聊天页」两条铁律。

- [ ] 已用 AskUserQuestion 问过输出形态：内嵌正则 PNG / 内嵌正则 JSON / 分离式（卡+正则json+规则.md）
- [ ] （内嵌正则的整卡）状态栏**生成规则**已作为 constant=true（蓝灯）条目放入卡内 character_book——渲染正则≠生成规则，缺这条后续轮次状态栏不更新（见 output/card-json.md 第 8 节）
- [ ] （内嵌正则的整卡）卡内 regex_scripts 为 4 字段结构；`/mmd`、`/st` 按各自纪律写，**沙盒的规则内容按沙盒纪律**（`<script>` 一等公民、禁 img onerror 点火器、id 负数、slash 形态）
- [ ] （内嵌正则的整卡）**正则同时另出一份独立 json**——卡内是否被读取尚有未决矛盾 `【待验证】`（见 output/card-json.md 第 4 节的保守交付纪律），双份可保证用户补导即可补齐
- [ ] （分离式）独立正则 json 的 beginning/regex_scripts 与卡内 first_mes/regex_scripts 一致；沙盒的分离式正则 json 走 6 键格式
- [ ] （单独美化/状态栏流程）默认交付含 正则 json + 规则.md（状态栏生成规则文档）

- [ ] **旧版同层卡 `/mmd`** 使用新增原生动作时，已按 `runtime/mmd-action-modules.md` 检查动作白名单、对应快照 revision、目标引用、确认阶段与会话切换；本地验证和真实站验证分开记录。


### 旧版同层卡的统一预览与审核入口

旧版同层作品优先按 [统一指南](../creation/same-layer-review.md) 使用 `review_same_layer.py`，复用通用校验及旧 MMD 全景外壳，生成与发布载荷同版本的联动预览和报告。检查 MMD / 同层页切换及共享状态。报告 PASS 仅指实际列出的本地自动项；缺环境为未完成，视觉/剧情审核、真实 MMD 与实体手机分别记证据。**沙盒同层卡改走 [新页指南 §8](../creation/sandbox-same-layer-card.md#8-制作与验收顺序)**，不用此旧页审核器；普通气泡美化沿用各自流程。

同层联动预览还需通过原生完整性检查：对照旧预览快捷/更多/面板清单，验证参数入口未错接为模型列表、总结和用户消息按钮未丢失、原生关闭控件不被同层返回浮钮遮挡。恢复原生 UI 不代表扩展了已审核桥接接口。
