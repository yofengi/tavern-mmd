# tavern-mmd 脚本

两个纯 Python 标准库脚本（无 pip 依赖），任何能跑 `python` 的 agent 通用。

## validate.py — 静态审核

子代理可直接调用以节约主上下文。审核 JSON 合法性、BOM、双重转义、平台红线、v2规范、世界书字段。

```bash
python validate.py <文件> [--type regex|card|worldbook] [--platform oldmmd|mmd|st]
```

- `--type` 省略时按内容自动识别（regex_scripts→正则、spec→卡、entries→世界书）
- `--platform` 省略默认 oldmmd（最严格）
- 退出码：0=无错误（可能有警告），1=有错误，2=用法/读取错误

审核项：
- 通用：JSON合法性、UTF-8 BOM、replaceString/HTML内双重转义反斜杠
- 正则/状态栏：四字段结构、字符数(find≤1000/replace≤20000)、条数≤130、stopPropagation、平台红线、**悬空标记**（statusbar/beginning 里的 `<标记>` 无对应 findRegex → ERROR）
- 平台红线(oldmmd)：`<script>`→错误、ES6→错误、innerHTML/cssText→错误、内联事件裸换行→错误
- 平台红线(mmd)：script/ES6 已实测支持→放行；onerror 多行放行；onclick 代码字面量/直接赋值告警；innerHTML/cssText 仍按需提示
- 角色卡：spec/同步；MMD平台强制 v2（spec=chara_card_v2、无 group_only_greetings）
- 世界书：entries字段、蓝绿灯配置

## build-preview.py — 平台保真预览

生成自包含 HTML 沙箱，主AI 用 Preview 工具打开看渲染、测交互（点按钮、切标签页、开侧边栏）。

MMD 导入 json（含 `statusbar`/`beginning`/`regex_scripts`）走**真实替换管线模拟**：先把 `statusbar + beginning` 拼成消息文本，再按 `regex_scripts` 逐条替换，最后输出三面板：

1. **第一句话整合预览**：第一句话经全量替换后的真实长相；如果第一句话含可选菜单、图片或特殊美化，会在这里一起显示。
2. **状态栏单独预览**：从整合结果中抽出雷达/KV状态栏；雷达法会保留 `img onerror` 引擎和隐藏信标数据，让 Preview 能实际触发 onerror。
3. **悬浮组件预览**：从整合结果中抽出 `position:fixed` / `float/sidebar/ball` 类组件（侧边栏、悬浮球等），便于单独检查。

本地酒馆正则数组（无 `beginning`）继续走逐片段 iframe 模式。MMD 系平台还会静态扫描标签间裸换行，命中则标"空白条"警告（把只有实机能发现的头号陷阱前移到预览）。

### 两种产出：三面板诊断 + 全景预览（`--mode`）

- `--mode panels`：只产**三面板诊断**（上述），逐组件隔离，定位单组件 CSS/ID 冲突。
- `--mode panorama`：只产**全景预览**——所有组件组合进**一个模拟 MMD 聊天页**的单文档：可滚动聊天区（第一句话整合渲染，全局美化/状态栏/侧边栏/悬浮球同场运行）+ **底部固定主输入框**（上下滑动不受影响）+ 右侧发送按钮。发送会在聊天区追加用户气泡（`.content.right`）和一条占位 AI 气泡（`.content.left`，文案标明"预览模式，真实回复需实机生成"）。输入框用 `.uni-textarea-textarea` 类名，与状态栏选项按钮的回填选择器一致，所以选项点击→回填输入框这条链在全景里也通。
- `--mode both`（默认）：两份都产，`<文件>-preview-<平台>.html`（三面板）+ `<文件>-panorama-<平台>.html`（全景）。

> 全景发送逻辑是预览工具自带的脚手架（走 `img onerror` 点火器，三平台都执行，不被 `<script>` 剥离器当被测内容裸露），与被测美化产物无关。

```bash
python build-preview.py <文件> --platform oldmmd|mmd|st [--mode panels|panorama|both] [-o 输出.html]
```

平台渲染差异：
- `st`：原样渲染，script/ES6 全执行
- `oldmmd`：`<script>`剥离并裸露源码（红框）；onerror/onclick内ES6标黄但仍执行（便于测交互）；onerror点火器正常执行
- `mmd`：script/ES6 全执行（已确认支持）；script 加"✓script"角标标明正常执行

输出是自包含 HTML 文件，默认落在 `工作/` 下。不能调 Preview 工具的 agent：提示用户用浏览器打开。

## make_card_image.py — 角色卡图片导出

把角色卡 JSON 嵌入 PNG（写 tEXt chara chunk），产出可导入的整卡图片。纯 stdlib。

```bash
python make_card_image.py <卡JSON> [--bg 底图路径] [-o 输出路径]
```

- PNG：在 IDAT 前写 `chara` tEXt chunk（base64 卡 JSON）；卡 spec=chara_card_v3 时额外写 `ccv3` chunk。`--bg` 省略则生成默认米黄底图（下部带 tavern-mmd 标签），给路径则注入用户 PNG。
- JPG：**已弃用**。实测 MMD 无法从 jpg 读出卡数据（EXIF UserComment 与 JPEG COM 段两种方案均验证不可用）。`--format jpg` 会直接报错退出；底层 embed_jpg/read_jpg_chara 仅保留作历史参考。MMD 整卡只用 PNG（或 JSON，本地酒馆）。
- 自动按卡 JSON 的 `spec` 决定写 v2（仅 chara）还是 v3（chara+ccv3）。
- 退出码：0 成功，1 失败（JSON 不合法/底图缺失或非法/请求 jpg），2 用法错误。

测试：`python -m unittest test_make_card_image -v`（往返一致性）。

## 工作流（详见各指令文件）

产出物完成 → 子代理跑 validate.py（结果写 `工作/审核记录.md`；悬空标记必须 0 错）→ 有错则主AI/子代理修复复审 → 主AI 跑 build-preview.py（默认 `--mode both`）→ **先用 Preview 工具看三面板诊断**审核单组件（第一句话整合、状态栏单独、悬浮组件）并测交互 → **再看全景预览二次审核**组合效果（所有组件同场无串台、输入框固定、发送/选项回填正常）→ 全景预览不默认关闭，留给用户自查是否要改（子代理做不了 Preview 这步）。

## 测试

```bash
python -m unittest test_validate test_build_preview -v
```
