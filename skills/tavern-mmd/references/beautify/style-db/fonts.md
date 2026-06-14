# 字体维度库（fonts）

本文件覆盖风格数据库的字体维度。配合 ../style-system.md 使用。核心原则：MMD 不保证 webfont 加载，font-family 末尾必须始终带系统栈兜底。

## 通用规则

- 系统安全栈（中文优先，MMD 与本地酒馆都安全）：`-apple-system,"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif`
- 等宽栈：`"SF Mono","JetBrains Mono",Consolas,"Courier New",monospace`
- 衬线栈：`Georgia,"Times New Roman","Songti SC",serif`
- webfont 规则：本地酒馆可 `@import` Google Fonts（如 Playfair Display / Cormorant Garamond / Orbitron）；**MMD 不保证 webfont 加载，必须给系统栈兜底（font-family 末尾始终带系统栈）**。
- 字号刻度：`11/12/14/16/18/24` 六档。
- 字重层级：标题 600-700 / 正文 400 / 标签 500。
- 数字列：`font-variant-numeric:tabular-nums`（数据/数值状态栏用）。

## 各风格字体

| # | 风格 | 标题字族 | 正文字族 | 需webfont(降级目标) | 特殊 |
|---|------|----------|----------|---------------------|------|
| 1 | 极简墨白 | Playfair Display→衬线栈 | Source Serif 4→衬线栈 | 是→衬线栈 | 首字下沉可选 |
| 2 | 瑞士极简 | Inter→系统栈 | Inter→系统栈 | 是→系统栈 | — |
| 3 | 便签纸墨 | 衬线栈 | 衬线栈(Georgia) | 否 | 阅读向 |
| 4 | 大地陶土 | 系统栈 | 系统栈 | 否 | — |
| 5 | 复古胶片 | 衬线栈 | 衬线栈 | 否 | 暖调 |
| 6 | 杂志编排 | 粗体无衬线→系统栈 | Georgia/Merriweather→衬线栈 | 是→衬线栈 | 首字下沉+拉栏 |
| 7 | 手绘速写 | Kalam→系统栈 | Patrick Hand→系统栈 | 是→系统栈 | 手写感 |
| 8 | 黏土软糖 | Nunito→系统栈 | DM Sans→系统栈 | 是→系统栈 | 圆润 |
| 9 | 新拟物 | Plus Jakarta Sans→系统栈 | 系统栈 | 是→系统栈 | — |
| 10 | 软UI进化 | 系统栈 | 系统栈 | 否 | — |
| 11 | 有机生物 | 系统栈 | 系统栈 | 否 | — |
| 12 | 便当格 | 系统栈 | 系统栈 | 否 | — |
| 13 | 暗夜霓虹 | 等宽栈 | 等宽栈 | 否 | 等宽 |
| 14 | 全息HUD | 等宽栈 | 等宽栈 | 否 | 等宽 |
| 15 | 终端CLI | 等宽栈(JetBrains Mono) | 等宽栈 | 否 | 等宽/字号仅12/14/16 |
| 16 | 影院暗调 | Inter→系统栈 | Inter→系统栈 | 是→系统栈 | — |
| 17 | 赛博HUD | Orbitron→等宽栈 | JetBrains Mono→等宽栈 | 是→等宽栈 | 等宽 |
| 18 | OLED纯黑 | 系统栈 | 系统栈 | 否 | — |
| 19 | 学院典籍 | Cormorant Garamond→衬线栈 | Crimson Pro→衬线栈 | 是→衬线栈 | 首字下沉+罗马数字 |
| 20 | 金橙账本 | Space Grotesk→系统栈 | Inter→系统栈 | 是→系统栈 | 数字等宽tabular-nums |
| 21 | 粗体海报 | Playfair Display Italic→衬线栈 | Inter Tight→系统栈 | 是→混合栈 | 超大标题48-72px |
| 22 | 动势野兽 | Space Grotesk→系统栈 | 系统栈 | 是→系统栈 | 跑马灯 |
| 23 | 毛玻璃 | 系统栈 | 系统栈 | 否 | — |
| 24 | 新野兽派 | 粗体无衬线→系统栈 | 系统栈 | 否 | 粗体700+ |
| 25 | 包豪斯 | Outfit→系统栈 | 系统栈 | 是→系统栈 | 几何粗体900 |
| 26 | Y2K千禧 | 系统栈 | 系统栈 | 否 | — |
| 27 | 孟菲斯 | 系统栈 | 系统栈 | 否 | — |
| 28 | 晨昏极光 | 系统栈 | 系统栈 | 否 | — |
| 29 | 蒸汽波 | 等宽栈 | 系统栈 | 否 | 复古 |
| 30 | 渐变网格 | 系统栈 | 系统栈 | 否 | — |
