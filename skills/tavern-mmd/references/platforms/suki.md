# 绮梦社（Hearthroom）写卡与迁移

目标平台始终记为 `/suki`。新作默认选沙箱；已有作品另记来源（MMD 旧页、MMD 沙盒或酒馆整卡）、当前聊天页和实际验证环境。同一功能优先采用绮梦原生 SDK，导入时先保留已有的可用效果。网页编辑器在「基本 → 聊天页」切换传统页与沙箱，保存后可用「对话测试」核对效果。`sdk.*` 属于沙箱；留在传统页时，已有脚本按该页文档使用公开接口，例如 `window.stage.state.get()`。[网页写卡指南](https://sukisuki.chat/zh-Hans/guide?way=web) · [同版 Markdown 手册](https://sukisuki.chat/zh-Hans/guide.md)

## 原生卡目录

`hearthroom card init night-train --language zh-Hans` 在本地新建一张简体中文卡。用实际作品语言替换 `zh-Hans`。整卡交付可继续编辑的卡目录；使用网页编辑器的作者可按同一字段清单手填。下列文件按作品需要创建。[官方卡目录格式](https://github.com/hearthroom/cli/blob/main/docs/card-folder.md)

| 要写的内容 | 卡目录中的位置 |
|---|---|
| 卡名、简介、语言、模型输出约定 | `card.json`，清单版本为 `formatVersion: 1`。需要模型持续输出标记时写入 `outputContract` 或人设，并在开场给出一份样例 |
| 人设、首条消息、备选开场 | `definition.md`、`welcome.md`、`openings/*.md`。另有只展示给玩家的 `opening.html`，其独立页面按钮用 `hearthroom.fill(text)` 或 `hearthroom.send(text)` |
| 世界书 | `lorebook.json` 的 `entries` 是数组，条目用 `name/content/keywords/constant` 等字段。分条维护时在卡目录的 `worldbook/*.md` 写源条目，运行 `hearthroom lorebook build night-train` 和 `hearthroom lorebook check night-train`。导入后只有 JSON 时直接维护它；改为分条源前先把全部原条目转入源文件，核对条目数和内容再 build，以免覆盖原书 |
| 规则、功能栏、聊天页 | `rules.json` 中的 `rules`、`mountTrigger`、`mountLayer`、`pageMode`。使用沙箱 SDK 的卡显式写 `"pageMode": "sandbox"` |
| 全局换肤、媒体 | `card.css` 放整卡 CSS，`assets/` 放资源。两种页面共用的基础颜色可在 `.canvas-root` 设置 `--lt-canvas-*`，沙箱还有 `--chat-*` |
| 随剧情变化的精确数值 | `variables.json` 定初值，`variables.md` 定变化规则，`panel.hbs` 可展示聊天区上方的当前值面板。脚本在沙箱读 `sdk.state.get()`、`sdk.state.of(messageId)` 或订阅 `state:change`。同一数值只保留一份来源 |

分条世界书的每个 Markdown 文件以 `---` 包住元数据，例如 `name: 夜班站台`、`keywords: [站台, 车票]`，正文写在结束的 `---` 后面。

## 沙箱交互

显示规则可查找固定标记或 `/pattern/flags`，替换可含 HTML、CSS 与脚本。新建规则可用 `targets` 限定消息对象。比如在 `welcome.md` 写「末班车就要开了。【查验车票】」，配上下列完整的 `rules.json`，点按钮会把一句话填入输入框，玩家可以继续编辑。

```json
{
  "pageMode": "sandbox",
  "rules": [
    {
      "id": "inspect-ticket",
      "name": "查验车票",
      "enabled": true,
      "targets": ["ai"],
      "find": "【查验车票】",
      "replace": "<button type=\"button\" onclick=\"sdk.input.set('我把车票递给检票员。')\">递交车票</button>"
    }
  ]
}
```

- **逐消息状态栏**。简单状态或选项可以先在目标沙箱预览 `[status]…[/status]`、`[choices]…[/choices]` 的内置显示。自定义显示用规则替换；需要历史快照时读取 `sdk.state.of(messageId)`。每条启用规则的脚本随卡加载一次。`message:mount`、`message:done` 可能补发，最终正文读 `msg.content`。规则异步完成后会替换气泡正文，按钮用规则内的点击处理或在沙箱 `document` 上委托；若向气泡插入面板，要能在正文替换后重新绘制且只保留一份。
- **同层网页和常驻面板**。用 `sdk.stage.open('content')` 或 `sdk.stage.open('full')` 打开舞台，用 `sdk.stage.el()` 取得容器。输入、发信、编辑分别走 `sdk.input`、`sdk.message.send(text)`、`sdk.message.edit(id, text)`。直接发送按钮在玩家点击回调内调用，遇到 `BUSY` 时保留草稿。
- **存档**。游戏偏好或卡自管进度用 `sdk.save`，按卡和玩家跨设备共享，每卡每人最多 10 个键、每值 64 KiB；临时数据用 `sdk.cache`。对话存档、分叉和切档用 `sdk.archive`。需随消息回溯的剧情数值走卡变量。
- **现成组件**。安装了官方技能包时，从 `using-hearthroom` 进入 `hearthroom-sandbox-kit`。其中的 `assets/sandbox-kit/build.mjs` 写入原生 `rules.json`，适合状态面板、选项和主题。按需查阅[官方技能入口](https://github.com/hearthroom/skills/blob/main/skills/using-hearthroom/SKILL.md)和[沙箱能力表](https://github.com/hearthroom/skills/blob/main/references/platform-facts.md)。

## 从 MMD 导入

在已有素材的目录运行官方 CLI。使用独立输出目录可保留原件；参数按实际已有的文件填写。网页也支持在编辑器导入 MMD 分件，或在「基本」拖入酒馆 PNG/JSON 整卡。CLI 另支持 CHARX。[官方导入命令](https://github.com/hearthroom/cli/blob/main/site/src/content/manual/card__import.md)

```sh
hearthroom card import rules.json book.json persona.txt --language zh-Hans --out migrated-card --json
```

| 来源 | 先保留什么 | 在绮梦核对什么 |
|---|---|---|
| MMD 旧页，四键规则包 | 规则顺序、捕获组、开场、静态 CSS 与原有按钮。绮梦指南明确兼容旧式 `img onerror` 启动片段 | CLI 导入四键包可能省略 `pageMode`。先试沙箱；已有卡依赖旧页行为时可选 `classic` 并在网页测试。旧 MMD 同层桥接依赖的站点 DOM、模型或存档动作要逐项核对，需改写的交互优先走绮梦沙箱 SDK |
| MMD 沙盒，新页六键包 | `chatVersion: 1` 会转为 `rules.json.pageMode: "sandbox"`。保留两边共有的 `sdk.input`、`sdk.message`、`sdk.stage`、`sdk.save` 及消息事件 | 检查舞台开关、历史气泡重挂和存档作用域。来源用到 `sdk.vars`、`vars:change`、`<abc_vars>` 的部分映射到绮梦卡变量与 `sdk.state`，核对初值和回溯 |
| 含 MMD 美化的酒馆格式整卡 | 用 `hearthroom card import character.png --language zh-Hans --out migrated-card --json` 导入整卡；按实际格式也可传 JSON | 对照人设、开场、世界书、内嵌规则及其样式作用域，再在目标卡中选择聊天页 |

CLI 的 MMD 三件套是规则 JSON、World Info JSON 与人设 TXT。开场来自规则包的 `beginning`，功能栏来自 `statusbar`。v0.13.0 中独立 TXT 优先；只有六键规则包时也可从 `personality` 取人设。读导入报告的 `notes`，与原件逐项对照 `definition.md`、`welcome.md`、`lorebook.json` 和 `rules.json`，尤其核对缺件和被跳过的规则字段。以上字段映射已用该版本在本地核对。[v0.13.0 导入器](https://github.com/hearthroom/cli/blob/v0.13.0/internal/importer/mmd.go)

## 用官网聊天页沙盒做本地预览

安装官方 Hearthroom CLI 后，从本 skill 根目录运行下面的命令。第一条打开可操作的聊天页，第二条在 `night-train/preview/shots/` 写入截图与 `findings.json`。可在卡目录的 `preview/replies.md` 放示例回复来测试规则和按钮。[CLI 下载](https://github.com/hearthroom/cli/releases) · [预览命令手册](https://github.com/hearthroom/cli/blob/v0.13.0/site/src/content/manual/card__preview.md)

```sh
python scripts/preview_suki.py night-train --open
python scripts/preview_suki.py night-train --check --json
```

CLI 0.13.0 的预览界面默认使用繁体中文。要核对简体界面，在打开的预览地址末尾添加 `&locale=zh-Hans`。沙盒会按玩家界面语言转换显示文字，点击回填保留卡片写入的原文。[官方预览页](https://github.com/hearthroom/cli/blob/v0.13.0/internal/preview/assets/preview.js)

skill 在 `assets/suki-sandbox/dist-sandbox/` 内附官网发布的 `index.html`、`sandbox.js`、`sandbox.css` 和简繁转换字典 `sandbox-zh.js`。启动器核对内容哈希，再将这个目录直接交给官方 `hearthroom card preview --shell`。所有卡共用这一份渲染器，首次预览也可离线。卡片自行引用的远程素材仍按原地址加载。渲染器版本随 skill 更新，`--shell <目录>` 可指定其他构建或已有的旧版缓存快照。[随包版本记录](../../assets/suki-sandbox/source.json) · [官网沙盒构建清单](https://github.com/hearthroom/hearthroom/blob/main/scripts/copy-sandbox.mjs)

`rules.json` 标为 `"pageMode": "classic"` 的卡可以直接打开。预览使用同一个沙盒，保留卡片的传统页设置。先检查规则、样式和按钮，依赖传统页宿主接口或布局的部分再到编辑器「对话测试」核对。消息、存档和模型示例回复由 CLI 的本地测试宿主提供。[CLI 本地预览实现](https://github.com/hearthroom/cli/blob/v0.13.0/internal/preview/preview.go)

要测试某个官网源码版本，在该版本的主仓库根目录执行以下命令，使用它锁定的 `stage` 子模块。然后给上述预览命令加上 `--shell "<官网仓库>/stage/dist-sandbox"`。[绮梦社官网源码](https://github.com/hearthroom/hearthroom)

```sh
git submodule update --init stage
npm --prefix stage ci
npm --prefix stage run build:sandbox
```

## 验证与交付

### 整卡与世界书的独立复核

1. 主代理自检后，把用户需求或已确认的 `plan.md`、待交付文件路径交给一名未参与编写的子代理。整卡和随卡世界书可以同轮复核。单独交付世界书时，把最终文件原样放入测试卡的 `lorebook.json`。采用分条源文件时，制作者先构建，并在受检卡目录的 `worldbook/` 保留对应源条目。
2. 复核子代理亲自读取交付物，对原生卡目录运行 `hearthroom card check <卡目录> --json`。有 Markdown 源条目时加跑 `hearthroom lorebook check <卡目录>`，核对源条目与交付 JSON 一致。仅按网页字段交付时，子代理核对最终字段和实际编辑器测试记录。
3. 按需求检查内容。整卡对照人设、开场、随卡世界书及约定组件。世界书逐项核对约定条目、正文、关键词和常驻设置，确认能按设计触发。主代理用内置沙盒实测交互卡的按钮、状态栏等实际行为，将预览结果交给复核人。纯文字世界书按条目验收。
4. 复核子代理提交每轮结论，写入项目 `工作/审核记录.md`，注明复核人、文件或条目、实跑命令及结果。遇到 ERROR 或与已确认需求不符的问题，由主代理或其他制作者修复，再交独立子代理复审改后的交付物。最终版本经独立复核且阻断问题清零才交付。当前环境无法调用子代理时，标记「待独立复核」。

### 预览与交付

单独交付规则或样式时，把实际文件装入测试卡运行 `hearthroom card check <卡目录> --json`。预览时查看开场，实际点击自定义按钮，确认输入框、舞台或面板出现预期变化。按卡片用到的功能再检查重挂和存档。传统页卡的本地结果记为「沙盒兼容预览」。仅用网页工作时，可先在规则「测试」栏验证样例，再看完整页面。

交付卡目录或所需组件，注明聊天页、依赖和实际跑过的检查。需要服务端试玩时，先用 `hearthroom card status night-train` 看绑定目标；新建且未绑定的目录执行 `hearthroom card push night-train --validate` 会建立私人试玩卡，已绑定自有卡的目录会更新该卡。`card render` 查看服务端规则结果；发送真实模型消息（`--allow-spend`）及送审按用户要求另行执行。[官方 CLI](https://github.com/hearthroom/cli)

需要配置创作环境时先用 `hearthroom version` 检查 CLI；Codex 的官方插件名是 `hearthroom@hearthroom-skills`，市场是 `hearthroom/skills`。安装入口在[绮梦 Agent 指南](https://sukisuki.chat/zh-Hans/guide)与[官方设置说明](https://sukisuki.chat/agent-setup.md)。通过网页写卡时可以直接使用字段和 SDK 示例。
