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
- 正则/状态栏：四字段结构、字符数(find≤1000/replace≤20000)、条数≤30、stopPropagation、平台红线
- 平台红线(oldmmd)：`<script>`→错误、ES6→错误、innerHTML/cssText→错误、内联事件裸换行→错误
- 平台红线(mmd)：同上但 script→警告（待验证）
- 角色卡：spec/同步；MMD平台强制 v2（spec=chara_card_v2、无 group_only_greetings）
- 世界书：entries字段、蓝绿灯配置

## build-preview.py — 平台保真预览

生成自包含 HTML 沙箱，主AI 用 Preview 工具打开看渲染、测交互（点按钮、切标签页、开侧边栏）。

```bash
python build-preview.py <文件> --platform oldmmd|mmd|st [-o 输出.html]
```

平台渲染差异：
- `st`：原样渲染，script/ES6 全执行
- `oldmmd`：`<script>`剥离并裸露源码（红框）；onerror/onclick内ES6标黄但仍执行（便于测交互）；onerror点火器正常执行
- `mmd`：同 oldmmd，但 script 正常执行并加"待验证"黄角标

输出是自包含 HTML 文件，默认落在 `工作/` 下。不能调 Preview 工具的 agent：提示用户用浏览器打开。

## 工作流（详见各指令文件）

产出物完成 → 子代理跑 validate.py（结果写 `工作/审核记录.md`）→ 有错则主AI/子代理修复复审 → 主AI 跑 build-preview.py 生成沙箱 → 主AI 用 Preview 工具看渲染+测交互（子代理做不了这步）→ 问用户是否预览。

## 测试

```bash
python -m unittest test_validate -v
```
