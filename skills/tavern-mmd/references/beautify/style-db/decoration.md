# 装饰维度库（decoration）

本文件覆盖风格数据库的装饰维度（伪元素特效）。配合 ../style-system.md 使用。每类装饰标注 CSS 实现、MMD 可用性与性能。

## 装饰类型表

| 装饰 | CSS 实现 | MMD 可用性 | 性能 |
|---|---|---|---|
| 光晕 blur-blob | ::before/::after 圆 + filter:blur(80px) | ✓（filter 可用） | 中 |
| 扫描线 scanline | ::before repeating-linear-gradient | ✓ | 优 |
| 颗粒 grain | 半透明 noise 背景 / 多层 radial | ✓ | 优 |
| 辉光 glow | text-shadow/box-shadow 0 0 Npx | ✓ | 优 |
| 漏光 light-leak | 角落 radial-gradient 暖色 | ✓ | 优 |
| 硬阴影 hard-shadow | box-shadow:4px 4px 0 #000 | ✓ | 优 |
| 毛玻璃 backdrop-blur | backdrop-filter:blur() | ⚠ 待验证（MMD未实测） | 中-重 |
| 跑马灯 marquee | animation translateX 循环 | ✓（注意单行无换行） | 中 |
| 斜切角 chamfer | clip-path:polygon | ✓ | 优 |

## MMD 铁律

- 注入 HTML 必须单行无换行（markdown 管线会把标签间换行补成空 `<p>` 撑出空白条）。
- 所有装饰性伪元素加 `pointer-events:none`（防挡点击）。
- onerror/onclick 内代码单行无换行。
- 毛玻璃 backdrop-blur 类一律标"待验证"，必须留 onerror 回退方案。

## 各风格装饰

| # | 风格 | 主装饰 | 次装饰 | MMD注意点 |
|---|---|---|---|---|
| 1 | 极简墨白 | 纸纹grain(opacity .03) | 无 | 单行无换行 |
| 2 | 瑞士极简 | 无 | 无 | — |
| 3 | 便签纸墨 | 纸纹/颗粒 | 无 | — |
| 4 | 大地陶土 | 颗粒grain(.1) | 柔影 | — |
| 5 | 复古胶片 | 颗粒 | 漏光light-leak | — |
| 6 | 杂志编排 | 无 | 首字下沉 | — |
| 7 | 手绘速写 | 不规则边/微旋转 | 硬偏移阴影 | — |
| 8 | 黏土软糖 | 拟物内外影 | 浮动blob | blob用filter:blur，性能中 |
| 9 | 新拟物 | 双层柔影 | 无 | — |
| 10 | 软UI进化 | 柔影 | 无 | — |
| 11 | 有机生物 | 柔影 | 有机曲线 | — |
| 12 | 便当格 | 柔影 | hover缩放 | — |
| 13 | 暗夜霓虹 | 扫描线 | 霓虹辉光 | 暗底专用 |
| 14 | 全息HUD | 描线/角标 | 扫描动画 | 暗底专用 |
| 15 | 终端CLI | 光标闪烁 | 扫描线 | 暗底专用 |
| 16 | 影院暗调 | 环境光晕blur-blob | 微辉光 | 光晕用filter:blur，性能中 |
| 17 | 赛博HUD | 斜切角chamfer | HUD括号/扫描 | clip-path可用 |
| 18 | OLED纯黑 | 极简辉光 | 无 | 暗底专用 |
| 19 | 学院典籍 | 暗角vignette | 首字下沉 | 暖暗 |
| 20 | 金橙账本 | 橙金渐变 | 脉冲点pulse | 数据行 |
| 21 | 粗体海报 | 超大标题 | 下划线CTA | — |
| 22 | 动势野兽 | 跑马灯marquee | 反色按压 | 单行无换行；动画注意性能 |
| 23 | 毛玻璃 | backdrop-blur | 光晕 | **MMD待验证，留onerror回退** |
| 24 | 新野兽派 | 硬阴影4px | 3px黑边 | — |
| 25 | 包豪斯 | 硬阴影4px | 点阵/几何 | — |
| 26 | Y2K千禧 | 金属渐变 | 光泽glossy/glow | — |
| 27 | 孟菲斯 | 几何图形 | 旋转/重复图案 | clip-path/transform |
| 28 | 晨昏极光 | 流动渐变 | 虹彩iridescent | 渐变动画8-12s，性能中 |
| 29 | 蒸汽波 | 网格grid | 扫描线/glow | 暗底专用 |
| 30 | 渐变网格 | 多停渐变 | 微光shimmer | 渐变动画，性能中 |
