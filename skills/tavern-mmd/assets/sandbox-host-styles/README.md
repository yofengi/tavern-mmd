# 沙盒宿主皮肤配方

仅用于 MMD 新页 `chatVersion:1`。`summary.css` 覆盖总结根、已观察到的正文编辑/锚点后代，并给独立 `summary-confirm` 根配色；后者内部结构未确证，所以没有编造内部选择器。

这份皮肤采用制作期的深色配色，颜色集中在两个宿主根的 `--summary-*` 声明，可据作品调整。它不是 SBK 深浅色 preset，也不依赖 iframe 内变量跨源继承。玩家关闭阅读主题不会撤销静态宿主皮肤。

使用 SBK：在配置中设置 `"hostStyles": ["../sandbox-host-styles/summary.css"]`（路径相对配置文件；此例假设配置位于 assets/sandbox-kit）。生成器输出独立 `<style>` 正则条目。也可以手动将 CSS 放进替换内容的 `<style>`，不能把 `.css` 直接当正则 JSON 导入。

不改平台文案、图标、动画 transform、禁用态或业务数据。类名来自 2026-09-15/16 材料中的观察，不是稳定 SDK。使用后检查滚动、选中态、编辑返回、树外确认、窄屏与软键盘；保存和确认分支须在实际平台另验。

完整边界与 21 个根见 [宿主换肤指南](../../references/beautify/sandbox-host-styles.md)。
