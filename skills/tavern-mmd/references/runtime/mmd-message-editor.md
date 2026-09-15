# 旧 MMD 消息编辑：实机结构与预览

适用：当前 MMD 旧聊天页。2026-09-16 在用户提供的无正则、无美化页面手动打开 AI 消息编辑器，读取 DOM 和计算样式后取消，未改写真实消息。以下是这一版本的观察记录，不是所有版本的固定承诺。

## 稳定定位

| 元素 | 实机选择器 / 节点 |
|---|---|
| 消息操作组 | `.touch-scope > uni-view.modify-btn-scope` |
| 气泡按钮 | `uni-view.modify-btn`，内部 `uni-image > div + span + img` |
| 编辑遮罩 | `uni-page-body > uni-view.msg-modify-scope`，不套通用 `.u-popup` |
| 编辑容器 | `.modify-input-box > uni-view#vditor.vditor` |
| 可编辑区 | `#vditor .vditor-ir > pre.vditor-reset[contenteditable="true"]` |
| 文字工具 | `.option-box > uni-view.option-item` |
| 保存按钮 | `.msg-modify-scope > .modify-btn-box > uni-view.modify-btn`，文案 **保存**，无固定 ID |
| Vditor 导出框架 | `iframe#vditorExportIframe` |

不要把气泡编辑按钮和弹窗保存按钮的同名 `.modify-btn` 混用；必须限定父容器。也不要只查 `.vditor-reset`：源码、所见即所得和即时渲染区域可能同时存在，部分隐藏。

AI 消息按钮顺序为重新生成、编辑、分享；用户消息为编辑、分享。原生图标按钮没有文字，本地补充 ARIA 标签以便键盘和读屏操作；桥接仍保留上游图标尺寸识别路径。消息容器 `item<索引>` 和正文 `q<消息标识>` 是动态值，预览用本地时间戳标识，不能复制真实消息 ID。编译生成的 `data-v-*` 不属于稳定接口。

## 样式记录

- 气泡圆钮 24×24px，圆角 50%，背景 `rgba(0,0,0,.5)`，右距 8px；内部图像 14×14px。原始图片尺寸分别为 80×81、56×57、200×200，预览图案为自绘替代品。
- 遮罩全屏 fixed，z-index 9999，背景 `rgba(0,0,0,.7)`，`backdrop-filter: blur(10px)`。
- 编辑外框顶部 5rem、内边距 1rem，最小高度 19.9375rem，最大高度 70%，溢出滚动。
- Vditor 即时渲染模式，**固定 `height:40vh;width:100%`**，短文也填满编辑区域；16px / 24px 字体、内边距 10px 35px。底色沿用 Vditor：失焦 `#fff`，聚焦 `#fafbfc`；不要强制覆盖为另一种颜色。工具栏使用 `vditor-toolbar--hide`，实机高度 **0.5px**、左内边距 35px；库默认 5px 会留下明显色带。检查尺寸时等待高度动画结束。
- 外层容器和 Vditor 内部的 `::-webkit-scrollbar` 均为 `display:none;width:0;height:0`。保留滚动能力，不能以 `overflow:hidden` 冒充隐藏轨道；长文主要在 `.vditor-ir > pre` 内滚动。检查短文高度、底色覆盖、横竖轨道隐藏与真实滚轮操作，不能只依赖默认隐藏滚动条的无头浏览器截图。
- 工具依次为“简转繁 / 繁转简 / 去除异常符号 / 去除异常文字”。保存按钮粉色，42.5px 高、25px 圆角，两侧 12px。按钮栏 fixed，但不是固定在屏幕最底端。

## 仿真边界

统一预览离线包含与观察页相同版本的 Vditor 3.11.1，使用其真实即时渲染 DOM 和 Markdown 序列化；不会把编辑器库打入角色卡正则包。OpenCC JS 1.0.5 实现本地简繁转换。依赖来源、版本、校验值及 MIT 许可证位于 `scripts/fixtures/mmd-legacy/vendor/`。

本地保存修改当前模拟消息，取消丢弃草稿；Vditor 可能将可编辑段落序列化为带空行的 Markdown。**不要将本地保存当作真实 MMD 服务端保存成功。** 两项异常清理的实机规则未核实，预览保留原文案和结构，通过 `aria-disabled="true"` 禁用，并提供说明；不可随意截断文字冒充清理。

桥接写入 `contenteditable` 前后须保持有效 Range；来自同层 iframe 的操作可能让宿主没有光标选区，Vditor 的 input 处理会因此报错。当前基座写入正文后建立末尾 Range，再触发 input/change。Markdown、正则和复杂富文本的最终结果仍需在真实平台核对。

## 审核

统一审核的 `review_same_layer_edit.mjs` 对照标签、固定 ID、层级、文案和关键样式，并检查原生编辑/取消/转换、长文滚动、窄屏按钮可达。联动审核另外覆盖同层打开、写入、保存、取消；出现编辑器异步加载、光标错误或错误面板时应失败，不能退回纯文本假面板让测试通过。

制作流程见 [统一预览与审核](../creation/same-layer-review.md)，动作范围见 [原生动作模块](mmd-action-modules.md)。
