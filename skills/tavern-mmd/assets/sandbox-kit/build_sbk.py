#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_sbk.py —— SBK（MMD 沙盒模式基座）生成器。

把声明式 `sbk.config.json` 编译成**可直接导入 MMD 创卡页**的 6 键正则 JSON。
唯一设计依据：`资料/基座事实卡.md`（下称"事实卡"）。所有规避平台坑的分支都注明节号。

用法
----
    python build_sbk.py sbk.config.json --out dist/sbk.json
    python build_sbk.py sbk.config.json --out dist/sbk.json --verbose
    python build_sbk.py sbk.config.json --out dist/sbk.json --no-strip-comments

产出可再用仓库里的 skill 校验器复核（本脚本**不修改**它）：
    python validate.py dist/sbk.json --type regex --platform mmdsandbox

长度证据与保守门禁：
  1. 沙盒源码归一常量为 beginning/name/regex/content = 4000/200/4096/100000；
     创卡页 UI 显示 name/regex/content = 20/1000/20000。
     `replaceString` 的编辑器 20000 拒存与导入 100000 双路径已确证；name/findRegex
     是否存在同样双路径、超限如何失败仍待验证。本生成器对后两者按 UI 值告警、超过
     源码观察值保守报错，并始终执行不可调高的 `MAX_SOURCE_RULE=18000` 最终门禁。
  2. 两条对本基座产出的**误报**（均为 WARN，可忽略）：
     - `findRegex 含独立保留字 css`：命中的是标记名 `{{sbk-css}}`。该标记是 plan.md 2.1
       冻结的规则布局，不改。
     - `含全局 CSS *{}`：命中的是 base.css 里 `.sbk-host, .sbk-host * { box-sizing }`,
       已被 `.sbk-host` 作用域限定，并非全局选择器。校验器的正则
       `(?:^|[\}\;\s>])\*\s*\{` 会把后代组合子前的 `*` 误判为全局。

配置字段（JSON 不支持注释，故在此说明；示例见 sbk.config.example.json）
------------------------------------------------------------------
必填：
  assetDir      str   基座源码目录（相对 config 文件所在目录），默认 "sbk"
  beginning     str   开场白正文；若含状态块（供气泡面板渲染）需与 persona 约定一致
  statusbar     str   功能栏字段。chrome/pinned 任一开启即必须包含 markers.hud（默认 "{{hud}}"）
选填：
  personality   str   人设文本（导入页不读该字段，仅随 JSON 归档）
  chatVersion   int   必须 1（缺省即 1）
  pageDepth     int   固定 2（缺省即 2）
  theme         obj   【作者基线】主题 token。{dark:{...},light:{...}} 或扁平（两套同值）
                      语义名见 theme.js MAP；也可直给 --chat-* / --sbk-*
                      🚨 2.1 起它【不再】编译进静态 sbk-css，而是经 boot 信封下发给
                      theme.js 作合成的最底层。理由见「主题所有权」一节。
  presets       list|obj  六维风格包。路径数组 ["presets/素雅阅读.json", …]（相对本配置
                      所在目录）或内联映射 {"包名":{六维…}}。六维键恰好
                      palette/layout/ui/font/cohesion/decoration，每维必须【双侧完整】
                      给 dark 与 light。生成器编译成 theme.register 可消费的
                      {tokens, tune} 并放进 boot 信封；只下发本卡列出的包。
  preset        str   默认风格包名（须在 presets 里）。玩家挑过后存档优先。
  modes         obj   {status:bool, chrome:bool, pinned:bool}，默认 true/true/false。
                      🚨 2.0 语义（设计文档第二节）：三者【职责不同】，不是同一份数据的多个渲染器。
                        status = 气泡内状态面板（唯一的状态数据渲染器，原 snapshot）
                        chrome = 功能栏入口按钮组，【不渲染业务数据】
                        pinned = 功能栏常驻精简条，只显示 pinnedFields 的 1..3 项
                      1.0 的 {hud, snapshot} 是「两个渲染器渲染同一份 schema」，示例配置
                      两个都开 → 实机截图里出现两个一模一样的状态面板。旧键仍被接受：
                      snapshot→status；hud=true→pinned 并告警（形态不等价，见 normalize_config）
  pinnedFields  list  精简条字段名，1..3 项。modes.pinned 开启时必填，且须是 schema.fields 里的 key
  schema        obj   状态栏 schema，原样传给 SBK.ui.snapshot（经 SBK.boot 归一化）
  protocolTag   str   数据协议块标签名，默认 "状态"（对应 [状态]…[/状态]）
                      🚨 一律方括号（plan.md 已裁决第 9 条）：§5.4 的剥壳正则会把 <状态>
                      这类中文尖括号标签整个删掉。剥壳跑在正则管线【之后】，所以正则
                      路径还看得见，但凡从气泡 textContent 读标记的路径（hydrate 的兜底
                      解析、pinned、自写脚本）标记都已经没了。方括号不是标签，全链路都活着。
                      正则里方括号是元字符，必须写 /\[状态\]([\s\S]*?)\[\/状态\]/
  hostId        str   功能栏宿主容器 id，默认 "sbk-hud"（chrome 与 pinned 共用）
  markers       obj   五个固定规则的触发串，键 css/core/ui/hud/boot
  sceneRules    list  场景规则；每项 {scriptName, findRegex, replaceString,
                      expectedMatches?(int,默认1), allowNonWhitelistTags?(bool)}
  idBase        int   规则 id 起始负数，默认 -1（依次 -1,-2,…）
  splitThreshold int  脚本自动拆条阈值，默认 18000（编辑器上限 20000 留 2000 余量）

主题所有权（2.1 / 审计报告高风险 1）
------------------------------------
1.0 有**两条**主题通道：本生成器把 `config.theme` 永久编译进静态 `sbk-css`，`theme.js`
又写 `#sbk-theme-vars`。后果是 `prefs.enabled(false)` 只清得掉动态那条，静态覆写还在 →
「关闭美化＝完全跟随平台」不成立，`preset` / `reset` / native 的优先级也无法证明。

2.1 起**只有 `theme.js` 写主题**：
  · `sbk-css` 只装 `base.css` 骨架（无 `[data-theme=…]` 覆写块）；
  · `config.theme` 经 boot 信封下发，作合成的最底层「作者基线」；
  · 最终样式 = author base + 选中的 preset + per-mode overrides，一个 `<style>` 承载。

boot 信封形如 `{"v":2, "base":…, "presets":{…}, "preset":"…"}`，走 `o.theme` 这一个键。
之所以搭这趟车：`core.js` 只有 `if (o.theme) SBK.theme.apply(o.theme)` 一条主题接线，
而本工作包不改 `core.js`。信封**恒为非空对象**，故 `modes.chrome` 无论真假，boot 都会
把主题层 start 一次（1.0 关掉 chrome 就没人读偏好存档，玩家上次的字号开局不生效）。

自动拆条与安全门禁
--------------------
生成器按固定顺序装载 11 个完整经典脚本模块：
`core.js → core-store.js → core-boot.js → theme.js → theme-panel.js → protocol.js →
hud.js → hud-render.js → ui.js → ui-panel.js → ui-stage.js`。

超过 `splitThreshold` 时只按连续的完整 IIFE 文件边界装箱，规则名变为 `sbk-core-N` /
`sbk-ui-N`，每条拿唯一 slash marker；数组顺序就是运行时装载顺序。绝不从函数或字符串
中间切脚本。`MAX_SOURCE_RULE=18000` 是不可调高的最终规则门禁：单模块、boot、场景规则
任何一条超过它都直接 ERROR，必须拆源码/配置，不能让超限文件独占一条或提高阈值绕过。

退出码：0 全绿（可能有 warn）／1 有 error（不写出文件）／2 配置或 IO 错误。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- 事实卡 §6 常量
# 源码归一观察值。超过时为防裁切或拒存保守判 ERROR；只有 content 的导入路径已确认到 100000。
HARD = {
    "beginning": 4000,
    "statusbar": 200,
    "imageUrl": 2048,
    "name": 200,          # scriptName
    "regex": 4096,        # findRegex
    "content": 100000,    # replaceString
    "regexList": 130,
}
# UI 显示/维护安全值。content 超过 20000 的编辑器拒存已确证；name/regex 仅作保守 WARN。
UI_SOFT = {
    "name": 20,
    "regex": 1000,
    "content": 20000,
}

# 事实卡 §5.2 输出预算：budget = max(262144, 输入文本长度 × 4)，按条规则累计所有匹配。
# 超限 → 整条规则回滚（页面上完全不生效，只留告警）。
BUDGET_FLOOR = 262144

# 事实卡 §5.4 worker 侧标签白名单（逐字清单）。非白名单标签被正则剥壳，文字保留。
WORKER_TAGS = set("""
p b a div span h1 h2 h3 h4 h5 h6 ul li ol strong em br img pre font i button
table th tr td input textarea label select option video script user summary
details code blockquote hr del thead tbody s
svg g path circle ellipse rect line polyline polygon text tspan defs use
linearGradient radialGradient stop clipPath title style
""".split())
# `user` 在 worker 白名单里但不是真 HTML 元素，DOMPurify 默认白名单不含它 → 取交集后仍被剥。
DOMPURIFY_MISSING = {"user"}

# 事实卡 §5.5 SAFE_FOR_XML：属性值命中即【整条属性被删】，且早于 forceKeepAttr。
# 实测 title="a[0] > 1"（有空格）完整保留 → 只拦无空格的危险形态。
SAFE_FOR_XML_RE = re.compile(r"((--!?|\])>)|</(style|script|title|xmp|textarea|noscript|iframe|noembed|noframes)", re.I)

# 事实卡 §2 CSP：作者开这三类被 meta frame-src/form-action/object-src 'none' 封死。
CSP_BANNED_TAGS = ("iframe", "form", "object", "embed")

DEFAULT_MARKERS = {
    "css": "{{sbk-css}}",
    "core": "{{sbk-core}}",
    "ui": "{{sbk-ui}}",
    "hud": "{{hud}}",
    "boot": "{{sbk-boot}}",
}
# 顺序就是运行时装载顺序，装箱只能按该顺序取连续完整 IIFE，绝不重排或切开单文件。
# core.js 建 SBK；core-store/core-boot 依赖它；theme-panel 依赖 theme 的私有门面。
# protocol 在 HUD 前；hud-render 复用 hud 的同一 TYPES；ui-panel 复用 ui kit；ui-stage 最后。
CORE_ASSETS = ("core.js", "core-store.js", "core-boot.js", "theme.js", "theme-panel.js")
UI_ASSETS = ("protocol.js", "hud.js", "hud-render.js", "ui.js", "ui-panel.js", "ui-stage.js")
ASSET_ORDER = CORE_ASSETS + UI_ASSETS


class Diag:
    """诊断收集器。error 阻止写出；warn 只提示。"""

    def __init__(self):
        self.errors = []
        self.warns = []
        self.notes = []

    def err(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warns.append("%s: %s" % (where, msg))

    def note(self, msg):
        self.notes.append(msg)

    @property
    def ok(self):
        return not self.errors


class BuildError(Exception):
    """配置/IO 级致命错误，直接退出码 2。"""


# ---------------------------------------------------------------- 剥注释
# plan.md 已裁决第 1 条：生成时剥注释，仓库保留带注释源码。
# 最终 18000 门禁独立于平台宽路径，确保生成规则可在编辑器中维护。

_REGEX_OK_AFTER = re.compile(r"[(,=:\[!&|?{};+\-*%~^<>]$")
_REGEX_OK_KEYWORD = re.compile(r"\b(return|typeof|case|in|of|new|delete|void|instanceof|do|else|yield|await)$")


def _regex_allowed(prev):
    """判断 `/` 处于正则字面量位置而非除号位置。"""
    s = prev.rstrip()
    if not s:
        return True
    if _REGEX_OK_AFTER.search(s):
        return True
    return bool(_REGEX_OK_KEYWORD.search(s))


def strip_js_comments(src):
    """剥 JS 注释，保留行号（块注释内换行原样保留）。

    状态机必须认得**模板字符串与正则字面量**，否则会把 `http://` 或 `/\\/*/` 里的内容误删。
    """
    out = []
    i, n = 0, len(src)
    # 模板字符串里的 ${...} 允许嵌套，用栈记录 brace 深度
    tpl_stack = []
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j          # 保留换行本身
            continue
        if c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            body = src[i:n] if j < 0 else src[i:j + 2]
            out.append("\n" * body.count("\n"))   # 保住行号
            i = n if j < 0 else j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    j += 1
                    break
                j += 1
            out.append(src[i:j])
            i = j
            continue
        if c == "`":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "`":
                    j += 1
                    break
                if src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    # 进入插值：交回主循环处理（可能含注释/嵌套模板）
                    tpl_stack.append(1)
                    j += 2
                    break
                j += 1
            out.append(src[i:j])
            i = j
            continue
        if c == "/" and _regex_allowed("".join(out)):
            j, in_cls, closed = i + 1, False, False
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "\n":
                    break                      # 正则不能跨行 → 判定失败，按除号处理
                if ch == "[":
                    in_cls = True
                elif ch == "]":
                    in_cls = False
                elif ch == "/" and not in_cls:
                    j += 1
                    closed = True
                    break
                j += 1
            if closed:
                while j < n and src[j] in "gimsuyd":
                    j += 1
                out.append(src[i:j])
                i = j
                continue
        out.append(c)
        i += 1
    text = "".join(out)
    # 行尾空白 + 连续空行压掉（纯代码区，模板字符串已原样保留在 out 里，
    # 这里只削行尾空格与全空行，不动行内内容 → 不会破坏模板字符串的可见字符）
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join([ln for ln in lines if ln.strip()])


def strip_css_comments(src):
    """剥 CSS 注释并压掉空行。CSS 只有 /*…*/ 一种注释，但要避开字符串与 url()。"""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    j += 1
                    break
                j += 1
            out.append(src[i:j])
            i = j
            continue
        out.append(c)
        i += 1
    lines = [ln.rstrip() for ln in "".join(out).split("\n")]
    return "\n".join([ln for ln in lines if ln.strip()])


def node_check(js, diag, where):
    """剥完注释必须仍语法有效 → 有 node 就跑一次 `node --check`（经典脚本模式）。"""
    exe = shutil.which("node")
    if not exe:
        diag.note("未找到 node，跳过 %s 的语法校验（建议装 node 后复跑）" % where)
        return None
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(js)
        r = subprocess.run([exe, "--check", path], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            out = (r.stderr or r.stdout or "").strip()
            # node --check 把版本号打在最后一行，取 tail[-1] 只会拿到 "Node.js vXX"。
            # 真正有用的是 SyntaxError 那行 + 它上面的位置行。
            lines = [ln for ln in out.splitlines() if ln.strip()]
            pick = [ln.strip() for ln in lines if "Error" in ln]
            detail = pick[0] if pick else (lines[0] if lines else "unknown")
            diag.err(where, "剥注释后语法无效（node --check）：%s" % detail)
            return False
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        diag.note("node --check 执行失败（%s），跳过 %s 语法校验" % (exc, where))
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------- 单项校验器

def check_module_syntax(text, diag, where):
    """事实卡 §3：内联脚本经 (0,eval) 按经典脚本执行，type=module 被接受但仍按经典跑
    → 顶层 import/export 必报错。"""
    if re.search(r"^\s*import\s+[\w{*'\"]", text, re.M) or re.search(r"^\s*import\s*\(", text, re.M):
        diag.err(where, "含 import 语句——内联脚本按经典脚本执行（§3），import 必报错。改用 IIFE。")
    if re.search(r"^\s*export\s+(default|const|let|var|function|class|\{)", text, re.M):
        diag.err(where, "含 export 语句——经典脚本不支持（§3）。")


def check_csp(text, diag, where):
    """事实卡 §2 CSP 边界。注意：图片外链 https 是允许的（img-src https:），不要误报。"""
    # 外部样式表 / 外部字体：style-src 无 https:、font-src 交集后仅 'self' → 封死
    if re.search(r"@import\s+(url\()?['\"]?https?:", text, re.I):
        diag.err(where, "含 @import 外部样式表——CSP style-src 无 https:（§2），封死。")
    for m in re.finditer(r"<link\b[^>]*>", text, re.I):
        tag = m.group(0)
        if re.search(r"rel\s*=\s*['\"]?stylesheet", tag, re.I):
            diag.err(where, "含 <link rel=stylesheet>——外部样式表被 CSP 封死（§2）。样式必须内联。")
    # 外部字体：@font-face 里的远程 url()
    for m in re.finditer(r"@font-face[^{]*\{[^}]*\}", text, re.I | re.S):
        if re.search(r"url\(\s*['\"]?https?:", m.group(0), re.I):
            diag.err(where, "@font-face 指向外部字体——font-src 交集后仅 'self'（§2），封死。用系统字体栈。")
    # 外部请求：connect-src 'self'
    if re.search(r"\bfetch\s*\(\s*['\"`]https?:", text, re.I) or \
       re.search(r"\.open\s*\(\s*['\"][A-Z]+['\"]\s*,\s*['\"`]https?:", text, re.I):
        diag.warn(where, "含指向外部的 fetch/XHR——connect-src 'self'（§2）会拦截，请求必失败。")
    elif re.search(r"\b(fetch|XMLHttpRequest)\b", text) and not re.search(r"//.*fetch", text):
        diag.warn(where, "出现 fetch/XMLHttpRequest——若目标是外部域名会被 connect-src 'self' 拦（§2）。")
    # 作者开 iframe/form/object
    for tag in CSP_BANNED_TAGS:
        if re.search(r"<%s\b" % tag, text, re.I):
            diag.err(where, "含 <%s>——meta frame-src/form-action/object-src 'none' 封死（§2）。" % tag)


def check_sanitize(text, diag, where):
    """事实卡 §5.5 DOMPurify 关键行为。"""
    # 自写 data-* 全删（实测 data-mine → null）。平台自己的 data-chat/data-slot 由 Vue 创建，
    # 从未进净化器 → 作为【选择器】读它们是合法的，只有【自己写属性】才被删。
    for m in re.finditer(r"<[a-zA-Z][^>]*?\s(data-[\w-]+)\s*=", text):
        diag.err(where, "HTML 里自写 %s——作者 data-* 全被净化删除（§5.5 实测 data-mine=null），改用 class/id。" % m.group(1))
    for m in re.finditer(r"setAttribute\s*\(\s*['\"](data-[\w-]+)['\"]", text):
        diag.err(where, "setAttribute('%s')——作者 data-* 全被删（§5.5），改用 class/id。" % m.group(1))
    # aria-* 与 role：ALLOW_ARIA_ATTR:!1 → 被删（平台限制，非基座缺陷）
    hits = set(re.findall(r"<[a-zA-Z][^>]*?\s(aria-[\w-]+)\s*=", text))
    if re.search(r"<[a-zA-Z][^>]*?\srole\s*=", text):
        hits.add("role")
    hits |= set(re.findall(r"setAttribute\s*\(\s*['\"](aria-[\w-]+)['\"]", text))
    if hits:
        diag.warn(where, "含 %s——ALLOW_ARIA_ATTR:!1，aria-*/role 被删（§5.5）。无障碍在此平台受限。"
                  % "/".join(sorted(hits)))
    # SAFE_FOR_XML：属性值命中即整条属性被删，且早于 forceKeepAttr
    for m in re.finditer(r"""\s[\w:-]+\s*=\s*(?:"([^"]*)"|'([^']*)')""", text):
        val = m.group(1) if m.group(1) is not None else m.group(2)
        hit = SAFE_FOR_XML_RE.search(val or "")
        if hit:
            diag.err(where, "属性值含危险序列 %r——SAFE_FOR_XML 默认开，【整条属性被删】（§5.5）。"
                     "比较运算符两侧留空格，如 a[0] > 1（实测该写法完整保留）。" % hit.group(0))
    # SVG 内 on*：实测 <circle onclick> STRIPPED；HTML 元素上任意 on* 均保留 → 不要误报
    for m in re.finditer(r"<svg\b.*?</svg\s*>", text, re.I | re.S):
        for t in re.finditer(r"<([a-zA-Z][\w-]*)\b([^>]*)>", m.group(0)):
            name, attrs = t.group(1).lower(), t.group(2)
            if name == "svg":
                continue
            on = re.search(r"\s(on[a-z]+)\s*=", attrs, re.I)
            if on:
                diag.err(where, "<%s %s> 在 SVG 内——SVG 元素上 on* 被删（§5.5 实测 circle onclick STRIPPED），"
                         "交互必须挂 HTML 壳。" % (name, on.group(1)))
    # 反引号里的 HTML 会原样成文本（§5.4 代码围栏/行内代码先抽占位符再还原）
    for m in re.finditer(r"`([^`\n]{0,400}?)`", text):
        if re.search(r"<[a-zA-Z][^>]*>", m.group(1)):
            diag.warn(where, "replaceString 里有反引号包裹的 HTML——代码围栏与行内代码受保护，"
                      "反引号内 HTML 会原样成文本而非渲染（§5.4 / 硬约束 16）。")
            break


def check_tags(text, diag, where, allow_non_whitelist=False):
    """事实卡 §5.4：worker 白名单 ∩ DOMPurify 才是真相。非白名单标签被正则剥壳，文字保留。"""
    if allow_non_whitelist:
        return
    # <style>/<script> 装卡时被抽走，不参与标签检查
    body = re.sub(r"<(style|script)\b.*?</\1\s*>", "", text, flags=re.I | re.S)
    bad = set()
    for m in re.finditer(r"</?([a-zA-Z][\w-]*)\b", body):
        name = m.group(1).lower()
        if name not in WORKER_TAGS:
            bad.add(name)
        elif name in DOMPURIFY_MISSING:
            bad.add(name)
    for name in sorted(bad):
        if name in DOMPURIFY_MISSING:
            diag.warn(where, "<%s> 在 worker 白名单但 DOMPurify 默认白名单不含它——取交集后仍被剥壳（§5.4）。" % name)
        else:
            diag.warn(where, "<%s> 不在 worker 标签白名单——会被正则剥壳，文字保留（§5.4）。" % name)


def classify_pattern(find_regex):
    """复刻事实卡 §5.1 worker 的 p()：trim → 剥首尾反引号 → /…/flags 否则字面量。

    返回 (kind, body, flags)，kind ∈ {'empty','slash','literal','bad-regex'}。
    """
    t = (find_regex or "").strip()
    t = re.sub(r"^`|`$", "", t)
    if not t:
        return ("empty", "", "")
    m = re.match(r"^/([\s\S]+)/([gimsuy]*)$", t)
    if not m:
        return ("literal", t, "g")
    body, flags = m.group(1), m.group(2) or ""
    if "g" not in flags:
        flags += "g"          # worker 缺 g 自动补
    return ("slash", body, flags)


def _js_re_to_py(body, flags):
    """把 JS 正则体粗略转成 Python 可编译形态，仅用于"能否匹配空串"的探测。"""
    py = body.replace(r"\d", "[0-9]").replace(r"\w", "[0-9A-Za-z_]")
    py = re.sub(r"\(\?<([A-Za-z_]\w*)>", r"(?P<\1>", py)   # 命名组语法差异
    f = 0
    if "i" in flags:
        f |= re.I
    if "s" in flags:
        f |= re.S
    if "m" in flags:
        f |= re.M
    return re.compile(py, f)


# 空的否定环视：`(?!)` / `(?<!)` 恒失败，即【永不匹配】而非匹配空串。
_NEVER_MATCH_RE = re.compile(r"\(\?<?!\)")


def zero_width_hazard(find_regex):
    """返回 (code, detail) 或 None。code ∈ {'empty-match','degenerate','unknown'}。

    两类隐患要分开说，因为成因不同：
    - empty-match：匹配式**能匹配空串** → replace() 在每个位置都插一次 → 输出爆量 →
      `i.length>a` 成立 → 整条规则回滚并打 `empty-match` 标签（§5.2 逐字逻辑）。
    - degenerate：`/(?!)/` 这类**恒失败**的零宽写法。plan.md 2.1 与硬约束明令禁止拿它当
      「永不匹配」。⚠ 按 worker 源码它其实一次都不匹配、不会触发回滚，
      但仍统一按 ERROR 拦：约定是用「正文里不会出现的字面标记」，
      可读性与可校验性都更好，且不必赌宿主侧那一层额外处理的行为。
    """
    if _NEVER_MATCH_RE.search(find_regex or ""):
        return ("degenerate", "含恒失败的空否定环视 (?!)")
    r = matches_empty(find_regex)
    if r is True:
        return ("empty-match", "能匹配空串")
    if r is None:
        return ("unknown", "无法静态判定")
    return None


def matches_empty(find_regex):
    """事实卡 §5.2：匹配式能匹配空串 → 每个位置都插一次 → empty-match 告警 → 整条规则回滚。

    返回 True/False/None（None = 无法判定）。
    """
    kind, body, flags = classify_pattern(find_regex)
    if kind == "empty":
        return True
    if kind == "literal":
        return False          # 非空字面量被转义后必然有长度
    try:
        rx = _js_re_to_py(body, flags)
    except re.error:
        return None
    try:
        m = rx.search("")
        if m is not None:
            return True
        # 空串搜不到也可能在非空文本上产生零宽匹配（如 /a*/ 在 "b" 上）
        for probe in ("x", "\n", " ", "0", "<div>x</div>"):
            m2 = rx.search(probe)
            if m2 is not None and m2.start() == m2.end():
                return True
    except re.error:
        return None
    return False


def estimate_budget(rule, input_len, expected_matches, diag, where):
    """事实卡 §5.2 输出预算估算。

    budget = max(262144, 输入文本长度 × 4)；按条规则**累计所有匹配**的输出。
    超限 → 整条规则回滚（页面上完全不生效，只留告警）。三种形态：
      replacement-alone  替换文本本身 > budget
      volume             次数 × 长度 > budget
      empty-match        匹配式能匹配空串
    """
    rs = rule["replaceString"]
    budget = max(BUDGET_FLOOR, input_len * 4)
    rlen = len(rs)

    hazard = zero_width_hazard(rule["findRegex"])
    if hazard and hazard[0] == "empty-match":
        diag.err(where, "匹配式能匹配空串——触发 worker 的 empty-match 判定，【整条规则被撤销】（§5.2）。"
                 "改用正文里不会出现的字面标记，包在 slash 里。")
    elif hazard and hazard[0] == "degenerate":
        diag.err(where, "匹配式用了 /(?!)/ 这类零宽写法当「永不匹配」——plan.md 2.1 明令禁止。"
                 "纯 CSS/JS 规则的 <style>/<script> 在装卡时就被抽走，与是否匹配解耦（§5.6），"
                 "所以只要用正文里不会出现的【字面标记】（包在 slash 里）即可。")
    elif hazard and hazard[0] == "unknown":
        diag.warn(where, "匹配式无法静态判定是否匹配空串，请人工确认不会零宽匹配（§5.2）。")

    if rlen > budget:
        diag.err(where, "replaceString %d 字符 > 预算 %d——replacement-alone，【整条规则回滚】（§5.2）。"
                 % (rlen, budget))
    total = rlen * max(1, expected_matches)
    if total > budget:
        diag.err(where, "预计输出 %d 字符（%d × %d 次）> 预算 %d——volume，【整条规则回滚】（§5.2）。"
                 % (total, rlen, expected_matches, budget))
    elif total > budget * 0.5:
        diag.warn(where, "预计输出 %d 字符已过预算 %d 的一半——匹配次数再多就会 volume 回滚（§5.2）。"
                  % (total, budget))
    return {"budget": budget, "replaceLen": rlen, "estOutput": total,
            "expectedMatches": max(1, expected_matches)}


def check_lengths(rule, diag, where):
    """事实卡 §6：UI 显示值保守告警；源码观察值外保守报错。"""
    pairs = (("scriptName", "name"), ("findRegex", "regex"), ("replaceString", "content"))
    for field, key in pairs:
        v = rule[field]
        n = len(v)
        if n > HARD[key]:
            if key == "content":
                diag.err(where, "%s %d 字符 > 已确认导入上限 %d——请拆条（§6）。"
                         % (field, n, HARD[key]))
            else:
                diag.err(where, "%s %d 字符 > 源码归一观察值 %d——录入路径失败语义待验证，"
                         "为防裁切或拒存保守判 ERROR（§6）。" % (field, n, HARD[key]))
        elif n > UI_SOFT[key]:
            if key == "content":
                diag.warn(where, "%s %d 字符 > 创卡页编辑器上限 %d（导入已确认可到 %d）——"
                          "编辑器保存会静默拒绝整次修改，不是截断；建议拆条（§6）。"
                          % (field, n, UI_SOFT[key], HARD[key]))
            else:
                diag.warn(where, "%s %d 字符 > UI 显示值 %d；源码归一观察值为 %d。"
                          "双路径与超限语义待验证，交付仍建议按 UI 值控制（§6）。"
                          % (field, n, UI_SOFT[key], HARD[key]))


def check_slash_form(rule, diag, where):
    """硬约束 21：findRegex 必须写成 /…/ slash 形态。

    实机验证：裸字面量 {{probe}} **不生效**，改 /{{probe}}/ 后立刻生效。
    这与 worker 源码 p() 的字面量分支矛盾，说明宿主侧在交给 worker 前另有一层处理 → 实机为准。
    """
    kind, body, flags = classify_pattern(rule["findRegex"])
    if kind == "empty":
        diag.err(where, "findRegex 为空——worker p() 返回 'empty'，规则被跳过（§5.1）。")
        return
    if kind == "literal":
        diag.err(where, "findRegex %r 是裸字面量——必须写成 /…/ slash 形态（硬约束 21，实机验证裸字面量不生效）。"
                 % rule["findRegex"])
        return
    try:
        _js_re_to_py(body, flags)
    except re.error as exc:
        diag.warn(where, "findRegex 体 %r 在 Python 侧无法编译（%s）；JS 语法可能仍有效，请人工确认。"
                  % (body, exc))


def dumps_sbk(doc, indent=2):
    """序列化产出。§6.10 官方要求：JSON 里 </script> 写成 <\\/script>，避免宿主页提前截断。

    这是【JSON 层的转义】——`\\/` 是 JSON 规范里 `/` 的合法转义，解析回来仍是 `</script>`，
    所以脚本抽取不受影响。若把反斜杠写进字符串【值】里反而会破坏 <script> 闭合，
    因为 HTML 不认 `<\\/script>` 为结束标签。故只在文本序列化后替换，不动 doc 本身。
    """
    text = json.dumps(doc, ensure_ascii=False, indent=indent)
    return re.sub(r"</(script)\b", r"<\\/\1", text, flags=re.I)


def check_script_close(text, diag, where):
    """自检：序列化后不应再有未转义的 </script（§6.10）。"""
    if re.search(r"(?<!\\)</script\b", text, re.I):
        diag.err(where, "序列化文本仍含未转义的 </script>——必须写成 <\\/script>，否则宿主页提前截断（§6.10）。")


# ---------------------------------------------------------------- 资源装配

def load_assets(asset_dir, names, diag, strip):
    """存在则合并，缺失则跳过并告警（WP-2/WP-3 可能还没交付）。

    `names` 的顺序就是装载顺序。每项必须是完整经典脚本模块；本函数只读取、剥注释和
    记录缺失项，不排序、不切文件。跨模块依赖由 CORE_ASSETS/UI_ASSETS 的唯一清单保证。
    """
    parts, loaded, missing = [], [], []
    for name in names:
        p = Path(asset_dir) / name
        if not p.is_file():
            missing.append(name)
            continue
        raw = p.read_text(encoding="utf-8")
        body = strip_js_comments(raw) if (strip and name.endswith(".js")) else \
               (strip_css_comments(raw) if (strip and name.endswith(".css")) else raw)
        parts.append(body)
        loaded.append({"name": name, "raw": len(raw), "out": len(body), "text": body})
    for name in missing:
        diag.warn("assets", "%s 缺失——跳过（WP-2/WP-3 交付后重跑生成器即可合并）。" % name)
    return "\n".join(parts), loaded, missing


# ---------------------------------------------------------------- 自动拆条
# plan.md 已裁决第 7 条：脚本合计超编辑器显示上限 20000 就自动拆条。
# regexList 上限 130 条（§6），额度极充裕，拆条成本可忽略。

SCRIPT_WRAPPER = "<script>\n%s\n</script>"
# 包裹开销："<script>\n" + "\n</script>" —— 打包时必须预留，否则贴着阈值会溢出
WRAPPER_OVERHEAD = len(SCRIPT_WRAPPER % "")
MAX_SOURCE_RULE = 18000          # 不可绕过：所有 SBK 源模块规则含 <script> 包装后的硬预算
DEFAULT_SPLIT_THRESHOLD = MAX_SOURCE_RULE


def pack_by_file(loaded, threshold):
    """按**文件边界**贪心装箱，保持原始顺序。

    粒度是整个文件：每个文件本身是完整 IIFE，切开必然语法错（plan.md 已裁决第 7 条）。
    若单个文件自身就超阈值，允许它独占一条——这比切开它安全得多。
    返回 [[entry, ...], ...]，箱内与箱间顺序均与 `loaded` 一致。
    """
    room = max(1, threshold - WRAPPER_OVERHEAD)
    bins, cur, cur_len = [], [], 0
    for e in loaded:
        n = len(e["text"])
        # 已有内容且再加就超 → 先封箱（+1 是 join 的换行）
        if cur and cur_len + 1 + n > room:
            bins.append(cur)
            cur, cur_len = [], 0
        cur.append(e)
        cur_len += (1 if cur_len else 0) + n
    if cur:
        bins.append(cur)
    return bins


def _suffix_marker(marker, n):
    """`{{sbk-ui}}` → `{{sbk-ui-1}}`；非 {{}} 形态则直接追加 `-N`。"""
    m = re.match(r"^(\{\{)(.*?)(\}\})$", marker)
    if m:
        return "%s%s-%d%s" % (m.group(1), m.group(2), n, m.group(3))
    return "%s-%d" % (marker, n)


def emit_script_rules(rid, base_name, base_marker, loaded, threshold, diag, strip):
    """把一组脚本资源编成 1..N 条规则。返回 (rules, next_rid, layout)。

    layout: [{scriptName, marker, files:[...], chars}]，供构建报告展示。
    单箱时沿用基名与基标记（`sbk-ui` / `{{sbk-ui}}`），多箱时才加 `-N` 后缀，
    避免没超限的卡白白改名。
    """
    if not loaded:
        return [], rid, []
    bins = pack_by_file(loaded, threshold)
    multi = len(bins) > 1
    rules, layout = [], []
    for i, box in enumerate(bins, 1):
        name = "%s-%d" % (base_name, i) if multi else base_name
        marker = _suffix_marker(base_marker, i) if multi else base_marker
        body = "\n".join(e["text"] for e in box)
        # 每箱都是若干完整 IIFE 的拼接 → 单独校验语法
        if strip:
            node_check(body, diag, "%s（剥注释后）" % name)
        rules.append(_rule(rid, name, marker, SCRIPT_WRAPPER % body))
        layout.append({"scriptName": name, "marker": marker,
                       "files": [e["name"] for e in box],
                       "chars": len(body) + WRAPPER_OVERHEAD})
        rid -= 1
    if multi:
        diag.note("%s 合计 %d 字符超阈值 %d，已按文件边界自动拆成 %d 条（顺序保持 %s）"
                  % (base_name, sum(len(e["text"]) for e in loaded) + WRAPPER_OVERHEAD,
                     threshold, len(bins), " → ".join(e["name"] for e in loaded)))
    for item in layout:
        if item["chars"] > MAX_SOURCE_RULE:
            diag.err(item["scriptName"],
                     "%d 字符 > SBK 源模块安全上限 %d，且按完整 IIFE 文件边界已无法再拆（%s）。"
                     "必须在源码侧拆成新的完整模块；不能提高 splitThreshold、不能任意切字符串，"
                     "否则创卡页保存会静默拒绝或脚本语法损坏。"
                     % (item["chars"], MAX_SOURCE_RULE, "/".join(item["files"])))
        elif item["chars"] > threshold:
            # 自定义阈值可低于安全上限；完整单模块无法再装箱，只提示，不把低阈值冒充平台硬限。
            diag.warn(item["scriptName"],
                      "%d 字符 > 自定义拆条阈值 %d，且 %s 是完整单模块，已独占一条。"
                      "仍低于固定安全上限 %d。"
                      % (item["chars"], threshold, "/".join(item["files"]), MAX_SOURCE_RULE))
    return rules, rid, layout


# ==================================================== 主题所有权与风格 bundle
# 🚨 2.1 单一运行时所有权（审计报告高风险 1）：这里【不再】把 config.theme 编译进静态
#    sbk-css。1.0 有两条主题通道（静态 sbk-css 覆写 + theme.js 的 #sbk-theme-vars），
#    于是 prefs.enabled(false) 只清得掉动态那条，「关闭美化＝完全跟随平台」不成立，
#    preset / reset / native 的优先级也无法证明。
#    2.1 起 sbk-css 只装 base.css 骨架；config.theme 改由 boot 载荷作为【作者基线】下发，
#    与 preset、per-mode overrides 在 theme.js 里合成同一个 <style>。
#    ⚠ 故本文件不再有 theme→CSS 的编译函数。要断言「静态通道已拆除」，测试应检查
#      sbk-css 规则的 replaceString 里不含 [data-theme= 覆写块。

# 风格 bundle 六维（美化决策「风格 bundle」冻结）。键名恰好这六个，多一个少一个都 ERROR：
#   palette    配色 → 落 14 个平台 --chat-* 语义令牌 + --sbk-on-accent
#   layout     骨架节奏 → --sbk-gap / --sbk-pad / --sbk-radius
#   ui         控件质感 → --sbk-shadow / --sbk-lift / --sbk-ball / --sbk-drw-w
#   font       字号行距 → --sbk-fs / --sbk-fs-sm + 结构化 tune(fontSize/lineHeight)
#   cohesion   一致性元信息 → 【只校验、不输出任何 CSS】
#   decoration 装饰 → --sbk-glow + 四条语义色 --sbk-hp/mp/sp/xp
BUNDLE_DIMS = ("palette", "layout", "ui", "font", "cohesion", "decoration")

# cohesion 只承载「这套包的设计意图」，供生成期校验与文档用，绝不编译成声明。
# 未知键只 WARN（元信息不影响运行），但值必须是标量——塞对象进来说明作者误当样式维用了。
COHESION_KEYS = ("contrast", "density", "motion", "mood", "note", "pairing")

# 可微调项：编译进 tune（结构化数字），不进 tokens。
# 🚨 这三项是 theme.js FIELDS 里 kind!=color 的那几个，两侧必须一致 ——
#    值域漂移会让生成期放行的包在运行时被 okField 逐字段丢弃（静默失效）。
#    test_build_sbk 有一条测试直接从 theme.js 读 FIELDS 比对本表。
TUNE_FIELDS = {
    "fontSize": {"kind": "int", "min": 12, "max": 22},      # 2.1 起是 CSS px，不再是 rpx
    "lineHeight": {"kind": "num", "min": 1.1, "max": 2.6},
    "opacity": {"kind": "int", "min": 40, "max": 100},
}

# 包名：与 theme.js 的 NAME_OK 同口径（中日韩汉字 + ASCII 字母数字 空格 _ -，1..32）
PRESET_NAME_RE = re.compile(
    r"^[0-9A-Za-z_\-\u3040-\u30ff\u4e00-\u9fa5]"
    r"[0-9A-Za-z_\- \u3040-\u30ff\u4e00-\u9fa5]{0,31}$")

# 危险值闸门：与 theme.js 的 DANGER 逐条对齐（同样有一条测试比对两侧）。
# 前两条会截断样式块；url(/@import 是外部资源（§2 CSP 封死且风格包一律零外部依赖）；
# expression( 是可执行 CSS；`;`/`{` 让单个令牌值凭空多写声明 = 绕过令牌白名单。
THEME_DANGER_RE = re.compile(
    r"\}|\{|;|</style|</script|url\s*\(|@import|expression\s*\(|javascript\s*:", re.I)

# palette 必须逐侧显式给全的五个核心键：对比度是【可证明】而非「大概能读」，
# 缺一个就没有基准可算。其余 palette 键可选，且允许 rgba()（只是不参与严格对比度检查）。
PALETTE_CORE = ("bg", "surface", "text", "accent", "border")

_HEX_FULL_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_HEX_SHORT_RE = re.compile(r"^#[0-9a-fA-F]{3}$")


def norm_hex(v):
    """#abc → #aabbcc；已是 6 位则小写归一。不是可解析 hex 返回 None。

    归一是对比度检查的前提，也让「等于默认值就删 override」在两侧口径一致
    （theme.js 的 sameAsDefault 同样做大小写归一）。
    """
    if not isinstance(v, str):
        return None
    s = v.strip()
    if _HEX_FULL_RE.match(s):
        return s.lower()
    if _HEX_SHORT_RE.match(s):
        return ("#" + s[1] * 2 + s[2] * 2 + s[3] * 2).lower()
    return None


def _lin(c):
    """sRGB 分量 → 线性值（WCAG 2.x 相对亮度公式）。"""
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex6):
    r = int(hex6[1:3], 16)
    g = int(hex6[3:5], 16)
    b = int(hex6[5:7], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b):
    """WCAG 对比度 (L1+0.05)/(L2+0.05)，1.0..21.0。入参须是归一后的 #rrggbb。"""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# WCAG 2.1 阈值。正文 4.5:1（1.4.3 AA 普通文本）；非文本图形与大号/次要前景 3:1（1.4.11）。
CONTRAST_TEXT = 4.5
CONTRAST_GRAPHIC = 3.0


# theme.js 的 SBK_OK 镜像，【只在读不到 theme.js 时兜底】。
# 🚨 真源是 theme.js（_sbk_whitelist_from_theme_js 会去读）。这里留一份是为了让「读不到」
#    走【严格】路径而不是放行一切：放行一切等于生成期不校验私有令牌，作者写错一个名字
#    （--sbk-wobble）会静默无效，正是本轮要消灭的一类缺陷。
#    test_build_sbk 有一条测试断言两侧完全相等，漂移立刻红。
SBK_PRIVATE_FALLBACK = frozenset({
    "gap", "pad", "radius", "fs", "fs-sm", "lh", "on-accent",
    "shadow", "lift", "ball", "drw-w", "glow", "hp", "mp", "sp", "xp",
})


def _sbk_whitelist_from_theme_js(asset_dir, diag=None):
    """从 theme.js 的 SBK_OK 表【读出】私有令牌白名单，不在生成器里写死一份副本。

    真值只有一处（theme.js）。运行时拒绝的令牌，生成期就该拒绝；两边各写一份必然漂移成
    「生成期放行、运行时静默丢弃」——那正是本轮要消灭的一类缺陷。
    读不到（文件缺失／写法变了）时返回 None，调用方据此降级为只按平台令牌校验并告警。
    """
    p = Path(asset_dir) / "theme.js"
    src = p.read_text(encoding="utf-8") if p.is_file() else ""
    m = re.search(r"var SBK_OK = \{(.*?)\};", src, re.S) if src else None
    if not m:
        if diag is not None:
            diag.warn("theme", "没能从 %s 读出 SBK_OK 私有令牌白名单——"
                               "本次按内置镜像 SBK_PRIVATE_FALLBACK 校验（仍是严格路径，"
                               "不会放行未知 --sbk-* 名）。若 theme.js 改了写法，"
                               "请同步 _sbk_whitelist_from_theme_js 与该镜像。" % p)
        return set(SBK_PRIVATE_FALLBACK)
    return set(re.findall(r"'([a-z0-9-]+)'\s*:\s*1", m.group(1)))


def theme_var(k):
    """语义名 / 平台后缀 / 直给变量名 → 最终 CSS 变量名。与 theme.js 的 toVar 同口径。"""
    if k.startswith("--"):
        return k
    if k in _THEME_MAP:
        return "--chat-" + _THEME_MAP[k]
    if k in _PLATFORM_VARS:
        return "--chat-" + k
    return "--sbk-" + re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", k).lower()


def ok_token(k, sbk_ok=None):
    """令牌名白名单。与 theme.js 的 okToken 同口径。

    sbk_ok 省略/None 时用内置镜像 SBK_PRIVATE_FALLBACK ——【始终严格】。
    🚨 曾经的写法是「读不到白名单就放行一切 --sbk-*」，那等于生成期不校验私有令牌：
       作者写错一个名字（--sbk-wobble）会静默无效，正是本轮要消灭的一类缺陷。
    🚨 --chat-* 只认平台真实存在的那 14 个：平台没定义的变量写了不报错也不生效，
       同样是静默失效，必须生成期拦住。
    """
    if not isinstance(k, str) or not k:
        return False
    wl = SBK_PRIVATE_FALLBACK if sbk_ok is None else sbk_ok
    if k in _PAGE_KEYS:
        return True
    if k.startswith("--chat-"):
        return k[len("--chat-"):] in _PLATFORM_VARS
    if k.startswith("--sbk-"):
        return k[len("--sbk-"):] in wl
    if k.startswith("--"):
        return False
    if k in _THEME_MAP or k in _PLATFORM_VARS:
        return True
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", k).lower() in wl


# theme.js 的 PAGE 表：需要 !important 的页面级属性名（不是变量）。
# 风格包里出现它们是合法的，但 url() 会被 THEME_DANGER_RE 拦下（零外部资源）。
_PAGE_KEYS = ("pageBg", "pageBgImage", "pageBgSize", "pageBgPosition", "pageBgRepeat")


def _ok_tune(k, v):
    """tune 值域校验。与 theme.js 的 okField 同口径（越界即拒，不夹取）。"""
    spec = TUNE_FIELDS.get(k)
    if spec is None:
        return False
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    if spec["kind"] == "int" and int(v) != v:
        return False
    return spec["min"] <= v <= spec["max"]


def compile_bundle(name, bundle, diag, sbk_ok=None):
    """六维风格包 → theme.register 可消费的 {dark:{tokens,tune},light:{tokens,tune}}。

    编译规则（美化决策「风格 bundle」）：
      · 六维键恰好 BUNDLE_DIMS，未知维 ERROR（写错一个字就整维静默不生效）。
      · 每维必须【同时】给 dark 与 light：平台强制两套主题都存在（玩家随时可能切），
        单侧包切过去会「整卡失效」或更糟的「浅色下显示深色配色」（盘点 E.3）。
      · cohesion 是元信息，只校验不输出——它绝不能产出任何声明。
      · 维内条目里，命中 TUNE_FIELDS 的进 tune（结构化数字），其余进 tokens（CSS 值）。
    返回 (compiled|None, 是否成功)。失败一律 None，绝不产出半成品包。
    """
    where = "presets[%s]" % name
    if not PRESET_NAME_RE.match(name or ""):
        diag.err(where, "风格包名 %r 不合法：需 1..32 个汉字/字母/数字/空格/_/-，"
                        "且首字符不是空格。包名会进 <option>、进存档、进 select.value，"
                        "放开引号尖括号只会多一个静默失败面。" % (name,))
        return None, False
    if not isinstance(bundle, dict):
        diag.err(where, "风格包必须是对象（六维：%s）。" % list(BUNDLE_DIMS))
        return None, False

    unknown = sorted(k for k in bundle if not k.startswith("_") and k not in BUNDLE_DIMS)
    if unknown:
        diag.err(where, "未知六维键 %s——合法键恰好 %s。写错的维【整维静默不生效】，"
                        "实机看不出少了什么，故此处报错而非告警。"
                 % (unknown, list(BUNDLE_DIMS)))
        return None, False

    missing_dims = [k for k in BUNDLE_DIMS if k not in bundle]
    if missing_dims:
        diag.err(where, "缺少六维键 %s——完整风格包必须恰好声明 %s。即使某一维暂不输出令牌，"
                        "也要显式给 {\"dark\":{},\"light\":{}}，让双侧设计意图可审计。"
                 % (missing_dims, list(BUNDLE_DIMS)))
        return None, False

    out = {"dark": {"tokens": {}, "tune": {}}, "light": {"tokens": {}, "tune": {}}}
    ok = True
    for dim in BUNDLE_DIMS:
        side = bundle[dim]
        if not isinstance(side, dict):
            diag.err(where, "%s 必须是对象，形如 {\"dark\":{…},\"light\":{…}}。" % dim)
            ok = False
            continue
        missing = [m for m in ("dark", "light") if not isinstance(side.get(m), dict)]
        if missing:
            diag.err(where, "%s 缺 %s ——风格包必须【双侧完整】。平台强制两套主题都存在，"
                            "玩家随时可能切；只给一侧时另一侧回落平台原生令牌，"
                            "实机现象是「切到浅色整卡失效」（盘点 E.3）。"
                     % (dim, "/".join(missing)))
            ok = False
            continue
        if dim == "cohesion":
            # 🚨 返回值必须并进 ok：cohesion 只记 diag 不影响成败的话，
            #    「六维里塞错一维」会在 ERROR 里报出来却仍产出一个包（半成品注册进运行时）。
            if not _check_cohesion(where, side, diag):
                ok = False
            continue
        for mode in ("dark", "light"):
            if not _compile_dim(where, dim, mode, side[mode], out[mode], diag, sbk_ok):
                ok = False

    if not ok:
        return None, False
    for mode in ("dark", "light"):
        if not out[mode]["tokens"]:
            diag.err(where, "%s 侧编译后没有任何令牌——注册进去也只是个空包，"
                            "玩家在面板里挑到它等于什么都没发生。" % mode)
            return None, False
    return out, True


def _check_cohesion(where, side, diag):
    """cohesion：只校验、绝不输出 CSS。值必须是标量（对象说明作者误当样式维用了）。

    返回是否全部合法 —— 调用方必须把它并进整体成败，否则会「报了 ERROR 还照样产出包」。
    """
    ok = True
    for mode in ("dark", "light"):
        for k, v in side[mode].items():
            if k.startswith("_"):
                continue
            if isinstance(v, (dict, list)):
                diag.err(where, "cohesion.%s.%s 的值是 %s——cohesion 是【一致性元信息】，"
                                "只参与生成期校验与文档，不产出任何 CSS 声明。"
                                "想调样式请写 palette/layout/ui/font/decoration。"
                         % (mode, k, type(v).__name__))
                ok = False
            elif k not in COHESION_KEYS:
                diag.warn(where, "cohesion.%s 不是已知元信息键（已知：%s）——"
                                 "已保留但不参与校验，也不会输出 CSS。"
                          % (k, list(COHESION_KEYS)))
    return ok


def _compile_dim(where, dim, mode, src, dst, diag, sbk_ok):
    """把一维一侧编译进 dst（{tokens,tune}）。返回是否全部合法。"""
    ok = True
    for k, v in src.items():
        if k.startswith("_"):
            continue
        if k in TUNE_FIELDS:
            if not _ok_tune(k, v):
                spec = TUNE_FIELDS[k]
                diag.err(where, "%s.%s.%s = %r 越界或类型错——合法区间 %s..%s（%s）。"
                                "运行时 okField 会逐字段丢弃越界值，生成期放行等于静默失效。"
                         % (dim, mode, k, v, spec["min"], spec["max"], spec["kind"]))
                ok = False
            else:
                dst["tune"][k] = v
            continue
        if not ok_token(k, sbk_ok):
            diag.err(where, "%s.%s 里的令牌名 %r 不在白名单内——合法范围：平台 14 个语义名/"
                            "后缀名、--chat-* 里真实存在的那 14 个、theme.js SBK_OK 列出的 "
                            "--sbk-* 私有名、以及页面级属性 %s。平台没定义的变量写了不报错"
                            "也不生效，是典型静默失效。" % (dim, mode, k, list(_PAGE_KEYS)))
            ok = False
            continue
        if v is None or v == "":
            diag.err(where, "%s.%s.%s 是空值——空令牌不会产生任何效果，"
                            "更可能是配置写漏了。" % (dim, mode, k))
            ok = False
            continue
        sv = str(v)
        if THEME_DANGER_RE.search(sv):
            diag.err(where, "%s.%s.%s 的值含危险片段（} { ; </style url( @import expression( "
                            "javascript:）——已拒绝。前两类会截断整个样式块；url(/@import 是"
                            "外部资源（§2 CSP 封死，且风格包一律零外部依赖）；`;`/`{` 让单个"
                            "令牌值凭空多写声明，等于绕过令牌白名单。" % (dim, mode, k))
            ok = False
            continue
        dst["tokens"][k] = sv
    return ok


def check_bundle_contrast(name, compiled, diag):
    """生成期对比度校验（WCAG 2.1）。只对【可解析 hex】做严格检查，不可解析一律 ERROR。

    🚨 「不可解析就跳过」是假通过：作者把 text 写成 var(--x) 或 rgba(…)，检查静默放行，
       实机可能是白底白字。故 PALETTE_CORE 五键要求逐侧显式 hex —— 有基准才算得出比值。
    阈值（WCAG 2.1）：
      · 正文 text 对 bg / surface ≥ 4.5:1（1.4.3 AA 普通文本）
      · accent 作前景（链接/强调文字/按钮底色）对 bg / surface ≥ 3:1（1.4.11 非文本对比）
      · border 作控件边界/焦点环这类关键图形，对 bg ≥ 3:1（1.4.11）
      · onAccent 对 accent ≥ 4.5:1（按钮上的字是正文级可读性），仅在两者都给了 hex 时查
    """
    ok = True
    where = "presets[%s]" % name
    for mode in ("dark", "light"):
        tok = compiled[mode]["tokens"]
        core = {}
        for k in PALETTE_CORE:
            raw = tok.get(k)
            if raw is None:
                diag.err(where, "%s 侧缺 palette.%s ——对比度是【可证明】而非「大概能读」，"
                                "缺基准色就算不出比值。palette 必须逐侧显式给全 %s。"
                         % (mode, k, list(PALETTE_CORE)))
                ok = False
                continue
            h = norm_hex(raw)
            if h is None:
                diag.err(where, "%s 侧 palette.%s = %r 不是可解析的 #RGB/#RRGGBB——"
                                "无法执行对比度检查。这里【不能】跳过：静默放行的后果"
                                "可能是实机白底白字。核心五键请写 hex 字面量。"
                         % (mode, k, raw))
                ok = False
                continue
            core[k] = h
        if len(core) < len(PALETTE_CORE):
            continue

        pairs = [
            ("text", "bg", CONTRAST_TEXT, "正文对页面底"),
            ("text", "surface", CONTRAST_TEXT, "正文对卡片底"),
            ("accent", "bg", CONTRAST_GRAPHIC, "强调色作前景对页面底"),
            ("accent", "surface", CONTRAST_GRAPHIC, "强调色作前景对卡片底"),
            ("border", "bg", CONTRAST_GRAPHIC, "控件边界/焦点环对页面底"),
        ]
        for fg, bg, need, label in pairs:
            r = contrast(core[fg], core[bg])
            if r < need - 0.005:      # 容差只吸收浮点噪声，不放宽阈值
                diag.err(where, "%s 侧对比度不足：%s（%s %s vs %s %s）实际 %.2f:1 < %.1f:1。"
                                "WCAG 2.1 %s。修法：压暗/提亮其中一方。"
                         % (mode, label, fg, core[fg], bg, core[bg], r, need,
                            "1.4.3 AA 普通文本" if need == CONTRAST_TEXT else "1.4.11 非文本对比"))
                ok = False

        on_accent = norm_hex(tok.get("onAccent") or tok.get("--sbk-on-accent") or "")
        if on_accent:
            r = contrast(on_accent, core["accent"])
            if r < CONTRAST_TEXT - 0.005:
                diag.err(where, "%s 侧对比度不足：accent 上的前景色（onAccent %s vs accent %s）"
                                "实际 %.2f:1 < %.1f:1。按钮上的字是正文级可读性，按 1.4.3 AA 判。"
                         % (mode, on_accent, core["accent"], r, CONTRAST_TEXT))
                ok = False
    return ok


def load_presets(raw, base_dir, diag):
    """config.presets → {包名: 六维源包}。

    两种写法（选最简单可维护的一组，不再多造语法）：
      "presets": ["presets/素雅阅读.json", …]   相对 config 所在目录的 JSON 路径数组
      "presets": {"包名": {六维…}, …}            内联对象（小改动/单元测试用）
    路径指向的 JSON 可以是：
      · 单个包：{"name":"素雅阅读","palette":{…},…}（无 name 时取文件名）
      · 包映射：{"素雅阅读":{六维…}, "密集状态":{…}}
    """
    out = {}
    if raw is None:
        return out
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k.startswith("_"):
                continue
            if k in out:
                diag.err("presets", "风格包名 %r 重复。" % k)
            out[k] = v
        return out
    if not isinstance(raw, list):
        diag.err("config", "presets 必须是路径数组或包映射对象，当前 %s。" % type(raw).__name__)
        return out

    for i, item in enumerate(raw):
        if isinstance(item, dict):
            # 数组里直接内联一个包：必须自带 name（否则没有键可挂）
            nm = item.get("name")
            if not isinstance(nm, str) or not nm:
                diag.err("presets[%d]" % i, "内联风格包必须带 name 字段。")
                continue
            out[nm] = {k: v for k, v in item.items() if k != "name"}
            continue
        if not isinstance(item, str) or not item.strip():
            diag.err("presets[%d]" % i, "每项必须是 JSON 路径字符串或内联包对象。")
            continue
        p = Path(item)
        if not p.is_absolute():
            p = Path(base_dir) / p
        if not p.is_file():
            diag.err("presets[%d]" % i, "风格包文件不存在：%s" % p)
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            diag.err("presets[%d]" % i, "%s 不是合法 JSON：%s" % (p, exc))
            continue
        if not isinstance(doc, dict):
            diag.err("presets[%d]" % i, "%s 顶层必须是对象。" % p)
            continue
        # 判形：含任一六维键 → 单个包；否则视为「包名 → 包」映射
        if any(k in doc for k in BUNDLE_DIMS):
            nm = doc.get("name")
            if not isinstance(nm, str) or not nm:
                nm = p.stem
            out[nm] = {k: v for k, v in doc.items() if k != "name"}
        else:
            for k, v in doc.items():
                if k.startswith("_"):
                    continue
                if k in out:
                    diag.err("presets", "风格包名 %r 重复（%s）。" % (k, p))
                out[k] = v
    return out


def build_presets(cfg, diag):
    """编译 + 校验全部风格包 → {包名: {dark:{tokens,tune},light:{…}}}。

    只编译【本卡配置里列出的】包。绝不把整个 style-db 打包进产物：
    每个包都要进 boot 载荷的 replaceString，全量搬运会直接顶到 §6 的长度上限，
    而玩家一次只用得上一套。
    """
    src = cfg.get("presetSources") or {}
    if not src:
        return {}
    sbk_ok = _sbk_whitelist_from_theme_js(cfg["assetDir"], diag)
    out = {}
    for name in sorted(src):
        compiled, ok = compile_bundle(name, src[name], diag, sbk_ok)
        if not ok:
            continue
        if not check_bundle_contrast(name, compiled, diag):
            continue
        out[name] = compiled
    return out


# theme.js 的语义名 → 平台 --chat-* 后缀（与 theme.js MAP 保持一致）
_THEME_MAP = {
    "bg": "bg", "surface": "surface", "panel": "surface", "text": "text", "muted": "text-muted",
    "border": "border", "accent": "accent", "primary": "accent",
    "userBubble": "bubble-user-bg", "aiBubble": "bubble-ai-bg", "bubbleText": "bubble-text",
    "sharePick": "share-pick-bg", "inputBg": "input-bg", "inputText": "input-text",
    "shortcutText": "shortcut-text", "moreItemBg": "more-item-bg",
}
_PLATFORM_VARS = {"bg", "surface", "text", "text-muted", "border", "accent",
                  "bubble-user-bg", "bubble-ai-bg", "bubble-text", "share-pick-bg",
                  "input-bg", "input-text", "shortcut-text", "more-item-bg"}

_AUTHOR_COLOR_VARS = {
    "--chat-bg": "bg", "--chat-surface": "surface", "--chat-text": "text",
    "--chat-accent": "accent", "--chat-border": "border", "--sbk-on-accent": "onAccent",
}


def _check_author_contrast(mode, tokens, diag):
    """对作者基线实际提供的核心色做可证明的局部对比度检查。"""
    where = "config.theme.%s" % mode
    colors = {}
    for k, v in tokens.items():
        final = theme_var(k)
        name = _AUTHOR_COLOR_VARS.get(final)
        if not name:
            continue
        h = norm_hex(v)
        if h is None:
            diag.err(where, "%s = %r 不是可解析的 #RGB/#RRGGBB，无法验证作者基线对比度。"
                            "核心颜色请使用 hex 字面量；其它非颜色 token 仍可使用合法 CSS 值。"
                     % (k, v))
            continue
        colors[name] = h
    pairs = [
        ("text", "bg", CONTRAST_TEXT, "正文对页面底"),
        ("text", "surface", CONTRAST_TEXT, "正文对卡片底"),
        ("accent", "bg", CONTRAST_GRAPHIC, "强调色对页面底"),
        ("accent", "surface", CONTRAST_GRAPHIC, "强调色对卡片底"),
        ("border", "bg", CONTRAST_GRAPHIC, "边界对页面底"),
        ("onAccent", "accent", CONTRAST_TEXT, "强调底上的正文"),
    ]
    for fg, bg, need, label in pairs:
        if fg not in colors or bg not in colors:
            continue
        ratio = contrast(colors[fg], colors[bg])
        if ratio < need - 0.005:
            diag.err(where, "对比度不足：%s（%s %s vs %s %s）实际 %.2f:1 < %.1f:1。"
                     % (label, fg, colors[fg], bg, colors[bg], ratio, need))


def normalize_author_theme(raw, asset_dir, diag):
    """校验并规范化 config.theme 作者基线；局部覆写合法，坏字段构建期报错。"""
    if raw is None or raw == {}:
        return {}
    if not isinstance(raw, dict):
        diag.err("config.theme", "theme 必须是对象。")
        return {}

    explicit = "dark" in raw or "light" in raw
    if explicit:
        missing = [m for m in ("dark", "light") if not isinstance(raw.get(m), dict)]
        extra = [k for k in raw if not k.startswith("_") and k not in ("dark", "light")]
        if missing:
            diag.err("config.theme", "显式分侧写法必须同时给 dark/light 对象，当前缺 %s。" % missing)
        if extra:
            diag.err("config.theme", "分侧写法含未知顶层键 %s；token 应放进 dark/light。" % extra)
        if missing or extra:
            return {}
        sides = {"dark": raw["dark"], "light": raw["light"]}
    else:
        sides = {"dark": raw, "light": raw}       # 旧扁平写法：两侧同值

    sbk_ok = _sbk_whitelist_from_theme_js(asset_dir, diag)
    out = {"dark": {"tokens": {}, "tune": {}}, "light": {"tokens": {}, "tune": {}}}
    for mode in ("dark", "light"):
        side = sides[mode]
        structured = "tokens" in side or "tune" in side
        if structured:
            extra = [k for k in side if not k.startswith("_") and k not in ("tokens", "tune")]
            if extra:
                diag.err("config.theme.%s" % mode,
                         "结构化写法含未知键 %s；只允许 tokens/tune。" % extra)
            tok = side.get("tokens", {})
            tune = side.get("tune", {})
            if not isinstance(tok, dict):
                diag.err("config.theme.%s.tokens" % mode, "必须是对象。")
                tok = {}
            if not isinstance(tune, dict):
                diag.err("config.theme.%s.tune" % mode, "必须是对象。")
                tune = {}
        else:
            tok = {k: v for k, v in side.items() if not k.startswith("_")}
            tune = {}

        for k, v in tok.items():
            where = "config.theme.%s.%s" % (mode, k)
            if not ok_token(k, sbk_ok):
                diag.err(where, "令牌名不在平台 14 个或 theme.js SBK_OK 白名单内。")
                continue
            if v is None or v == "":
                diag.err(where, "主题令牌不能为空。")
                continue
            if isinstance(v, (dict, list)):
                diag.err(where, "主题令牌值必须是 CSS 标量，不能是 %s。" % type(v).__name__)
                continue
            if THEME_DANGER_RE.search(str(v)):
                diag.err(where, "主题令牌值含危险片段（样式截断、多声明或外部资源）。")
                continue
            out[mode]["tokens"][k] = v
        for k, v in tune.items():
            if not _ok_tune(k, v):
                diag.err("config.theme.%s.tune.%s" % (mode, k),
                         "不是合法可微调项或值越界。")
                continue
            out[mode]["tune"][k] = v
        _check_author_contrast(mode, out[mode]["tokens"], diag)
    return out


def _theme_var(k):
    if k.startswith("--"):
        return k
    if k in _THEME_MAP:
        return "--chat-" + _THEME_MAP[k]
    if k in _PLATFORM_VARS:
        return "--chat-" + k
    return "--sbk-" + re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", k).lower()


def hud_host_html(host_id):
    """HUD 宿主容器。事实卡 §3 currentScript 恒 null → 靠固定 id 约定定位。
    §5.5 自写 data-* 被删 → 只用 class/id。"""
    return '<div id="%s" class="sbk-host"></div>' % host_id


def theme_envelope(cfg):
    """boot 载荷的 theme 字段 = 主题信封 {v:2, base, presets, preset}。

    🚨 为什么是信封而不是三个顶层键：core.js 的 boot 只有
         if (o.theme) SBK.theme.apply(o.theme)
       这一条主题接线，而 WP-2 不改 core.js（另包所有）。故作者基线、风格包、默认包名
       只能搭 o.theme 这趟车进来，由 theme.js 的 apply() 按 v:2 判形拆开。
       信封自带 v:2 与 base/presets 判别键，与 1.0 的 {dark,light} / 扁平写法不会混淆。

    🚨 【总是】返回非空对象（至少 {v:2,base:null,presets:{},preset:''}）：
       这正是「theme 初始化与 chrome 解耦」的落点 —— o.theme 恒为真值，于是无论
       modes.chrome 真假，boot 都会走到 apply() 并把主题层 start 一次。
       1.0 只有 modes.chrome=true 时 ui.chrome 才调 theme.start，关掉 chrome 就
       完全没人读偏好存档：玩家上次存的字号/配色开局不生效。
    """
    return {
        "v": 2,
        # 制作期 config.theme（旧配置照旧可用）→ 运行时的【作者基线】，不再是永久覆写
        "base": cfg.get("theme") or None,
        # 只下发本卡配置的包，绝不搬整个 style-db（会顶到 §6 长度上限，且玩家一次只用一套）
        "presets": cfg.get("presets") or {},
        "preset": cfg.get("preset") or "",
    }


def boot_script(cfg, diag):
    """启动调用。事实卡 §4.1 硬约束 17：任何 DOM 写入必须在事件回调内
    （作者脚本早于 DOM 执行，顶层 getElementById 返回 null）。
    §4.1 冷启动挂 message:mount/done——ready 最后到且无补发。
    这里只做参数投喂 + SBK.boot()，真正的订阅在 core.js 里。"""
    payload = {
        "hostId": cfg["hostId"],
        "schema": cfg.get("schema") or {},
        "modes": cfg["modes"],
        # 精简条字段名（modes.pinned 开启时 boot 才用它）。始终下发：值已归一化，
        # 空数组也无害，且让实机 payload 形状稳定，便于对着 sbk.json 自查。
        "pinnedFields": cfg.get("pinnedFields") or [],
        "protocolTag": cfg["protocolTag"],
        "theme": theme_envelope(cfg),
    }
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # 内联脚本里出现 </script 会【真的】提前闭合 <script>（这与 §6.10 的 JSON 层转义是两件事）。
    # 配置来自作者，此处按 JS 字符串转义拆开，闭合序列不再成形。
    if re.search(r"</script", js, re.I):
        js = re.sub(r"</(script)", r"<\\/\1", js, flags=re.I)
        diag.warn("boot payload", "配置值里含 </script——已按 JS 转义拆开（避免提前闭合 <script>）。")
    return (
        "(function(W){'use strict';var S=W.SBK;"
        "if(!S||!S.boot){(W.console&&W.console.warn)&&W.console.warn('[SBK] boot before core');return;}"
        "S.boot(%s);})(typeof window!=='undefined'?window:globalThis);" % js
    )


# ---------------------------------------------------------------- 配置读取

def _need_str(cfg, key, diag, default=None):
    v = cfg.get(key, default)
    if v is None:
        diag.err("config", "缺少必填字段 %s。" % key)
        return ""
    if not isinstance(v, str):
        diag.err("config", "%s 必须是字符串，当前 %s。" % (key, type(v).__name__))
        return ""
    return v


# ------------------------------------------------------- modes（2.0 语义）
# 设计文档第二节：三者【职责不同】，不是同一份 schema 的多个渲染器。
#   status = 气泡内状态面板（唯一的状态数据渲染器，1.0 叫 snapshot）
#   chrome = 功能栏入口按钮组，不渲染业务数据
#   pinned = 功能栏常驻精简条，只显示 pinnedFields 的 1..PIN_MAX 项，默认关
# 1.0 的 {hud, snapshot} 语义是「两个渲染器渲染同一份 schema」，示例配置两个都开
# → 实机截图里同时出现两个一模一样的状态面板。这就是本次重构要修的真实缺陷。
DEFAULT_MODES = {"status": True, "chrome": True, "pinned": False}
PIN_MAX = 3          # 与 core.js 的 PIN_MAX 一致：精简条最多 3 项（形态强制区分的一部分）


def _alias_modes(m, modes, diag):
    """旧键归一化：snapshot→status，hud=true→pinned。老 config 不报错，但必须告警。

    返回被别名【间接】开启的键集合。调用方据此把「pinned 开着却没配 pinnedFields」
    从 error 降级为 warn —— 1.0 的老配置本来就不可能有 pinnedFields 这个字段，
    对它报错等于「老 config 直接跑不过」，违反兼容要求。
    """
    aliased = set()
    if "snapshot" in m and "status" not in m:
        modes["status"] = bool(m["snapshot"])
        diag.warn("modes", "modes.snapshot 是 1.0 的名字，已归一化为 modes.status"
                           "（语义不变：气泡内状态面板）。请更新配置。")
    if "hud" in m and "pinned" not in m:
        if m["hud"]:
            modes["pinned"] = True
            aliased.add("pinned")
            # 🚨 必须讲清楚这【不是】等价替换，否则做卡人以为面板还在，实机只看到一行条
            diag.warn("modes", "modes.hud 在 2.0 已移除，已映射到 modes.pinned——"
                               "🚨 但语义【变了】：旧 hud 是功能栏里的【完整面板】"
                               "（分组/标签/进度条），新 pinned 是【单行精简条】，"
                               "只显示 pinnedFields 指定的 1..%d 项，且必须显式配 pinnedFields。"
                               "状态数据面板现在在【气泡内】（modes.status，默认开）。"
                               "若你原本要的是完整面板，改开 modes.status 而不是 pinned。" % PIN_MAX)
        else:
            diag.warn("modes", "modes.hud 在 2.0 已移除；它本来就是 false，已忽略。"
                               "新语义见 modes.status / chrome / pinned。")
    return aliased


def normalize_modes(cfg, diag):
    """-> (modes, pinnedFields)。modes 三键齐全；pinnedFields 去空去重后截到 PIN_MAX。"""
    modes = dict(DEFAULT_MODES)
    aliased = set()
    m = cfg.get("modes")
    if m is None:
        m = {}
    if isinstance(m, dict):
        aliased = _alias_modes(m, modes, diag)
        for k in DEFAULT_MODES:
            if k in m:
                modes[k] = bool(m[k])
        unknown = sorted(set(m) - set(DEFAULT_MODES) - {"hud", "snapshot"}
                         - {k for k in m if k.startswith("_")})
        if unknown:
            diag.warn("modes", "无法识别的 modes 键 %s——已忽略。合法键：%s。"
                      % (unknown, sorted(DEFAULT_MODES)))
    else:
        diag.err("config", "modes 必须是对象，如 "
                           "{\"status\":true,\"chrome\":true,\"pinned\":false}。")

    raw_pins = cfg.get("pinnedFields")
    if isinstance(raw_pins, str):
        raw_pins = [raw_pins]
    pins = []
    if raw_pins is None:
        raw_pins = []
    elif not isinstance(raw_pins, list):
        diag.err("config", "pinnedFields 必须是数组（1..%d 个字段名）。" % PIN_MAX)
        raw_pins = []
    for v in raw_pins:
        if not isinstance(v, str) or not v.strip():
            diag.err("config", "pinnedFields 每项必须是非空字符串，当前 %r。" % (v,))
            continue
        s = v.strip()
        if s not in pins:
            pins.append(s)
    if len(pins) > PIN_MAX:
        diag.err("config", "pinnedFields 有 %d 项 > 上限 %d——精简条是【单行】形态，"
                           "项数多了会挤爆功能栏，也就和气泡面板没区别了"
                           "（设计文档第二节：形态必须与气泡面板不同）。已截取前 %d 项。"
                           % (len(pins), PIN_MAX, PIN_MAX))
        pins = pins[:PIN_MAX]

    _check_pins(cfg, modes, pins, diag, aliased)
    return modes, pins


def _check_pins(cfg, modes, pins, diag, aliased=()):
    """pinned 与 pinnedFields 的一致性，以及字段名是否真在 schema 里。"""
    if modes["pinned"] and not pins:
        # 少了这个校验，boot 只会 warn 一句然后整个模式静默不启动 —— 生成期就该拦住。
        # 但若 pinned 是【旧 hud 别名间接开的】，报错就等于老 config 直接跑不过 → 降级为 warn。
        msg = ("精简条不知道该显示什么，SBK.boot 会跳过整个模式，功能栏上什么都不会出现。"
               "修法：加 \"pinnedFields\": [\"体力\"]（1..%d 项，取 schema.fields 里的 key）。"
               % PIN_MAX)
        if "pinned" in aliased:
            diag.warn("config", "modes.pinned 由旧键 modes.hud 映射而来，但没有 pinnedFields——"
                                + msg + "（本次不算错误：1.0 的配置里本就没有这个字段。"
                                        "精简条这一轮不会渲染，气泡内状态面板不受影响。）")
        else:
            diag.err("config", "modes.pinned 已开，但 pinnedFields 为空——" + msg)
    if pins and not modes["pinned"]:
        diag.warn("config", "配了 pinnedFields %s 但 modes.pinned 是 false——"
                            "精简条不会渲染，该字段被忽略。要么开 modes.pinned，要么删掉它。"
                            % pins)
    if not pins:
        return
    schema = cfg.get("schema")
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list) or not fields:
        return          # 没有 schema.fields 可比对（合法：靠模型输出顺序全渲染）→ 不猜
    keys = [f.get("key") for f in fields
            if isinstance(f, dict) and isinstance(f.get("key"), str)]
    for p in pins:
        if p not in keys:
            diag.err("config", "pinnedFields 里的 %r 不在 schema.fields 的 key 里"
                               "（现有：%s）——精简条按 key 从状态仓取值，取不到就整项不渲染，"
                               "实机现象是那一项凭空消失。修法：改成已有 key，或在 schema.fields 里补上。"
                     % (p, keys))


# hostId 是会派生 `-pin` / `-chr` 的配置基名。最终 DOM id 上限 64，后缀各占 4 字符，
# 因此配置基名总长最多 60；字符集仍取 HTML id、CSS 选择器与 JS 字符串无需转义的交集。
HOST_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,59}$")


def check_host_id(host_id, diag):
    """hostId 字符集校验。不合法时报错并回落默认，绝不把脏值拼进 HTML/CSS。

    🚨 它同时出现在两个注入面：
      1) `<div id="…">`（hud_host_html）—— 含引号/尖括号可以闭合属性甚至开新标签；
      2) core.js / ui.js 的 `#…` 与属性选择器 —— 含空格或 `]` 会让选择器整条失效
         （静默：宿主找不到，功能栏什么都不出现）。
    """
    if not isinstance(host_id, str) or not HOST_ID_RE.match(host_id):
        diag.err("config", "hostId %r 不合法：需匹配 %s（首字符为字母，其后字母/数字/_/-，"
                           "配置基名最长 60；基座会追加 -pin/-chr，使最终 DOM id 仍不超过 64）。"
                           "它会同时进入 <div id=…> 与宿主查找逻辑——含引号尖括号可闭合属性，"
                           "含空格或 ] 会让选择器失效。已回落默认 \"sbk-hud\"。"
                 % (host_id, HOST_ID_RE.pattern))
        return "sbk-hud"
    return host_id


# hud.js 真实支持的 schema type。九个数据类型 + 版面项 section（1.0 十种），
# 本轮按美化决策「控件范围」补三种纯展示项：time / summary / turn。
# 🚨 未知 type 在 hud.js 里走 `TYPES[type] || TYPES.text` 静默回落成 text ——
#    多实体表渲染不出来却不报错，极难排查，故生成期直接 ERROR。
SCHEMA_TYPES = ("bar", "num", "text", "tags", "entities", "path", "level", "stats",
                "kvlist", "section", "time", "summary", "turn")


def normalize_schema(schema, diag):
    """schema 校验 + 归一化。

    · 未知 type → ERROR（静默回落 text，是本轮要消灭的一类静默失效）
    · schema.persist → WARN 并【删除】：审计报告 3 认定它是假契约（协议说明声称走
      SBK.store，运行时既没有加载也没有保存，更没有作用域定义）。与 runtime 裁决一致：
      删掉这个键，显式调 SBK.store 的路径不受影响。
    """
    if not isinstance(schema, dict):
        diag.err("config", "schema 必须是对象。")
        return {}
    out = {k: v for k, v in schema.items()}
    if "persist" in out:
        diag.warn("schema", "schema.persist 是【假契约】，已丢弃（不会进 boot 载荷）。"
                            "协议说明曾声称它走 SBK.store，但运行时既没有加载也没有保存，"
                            "更没有定义作用域——留着只会让人以为存档已生效。"
                            "确实要持久化请显式调 SBK.store.save()/load()。")
        out.pop("persist", None)
    fields = out.get("fields")
    if fields is None:
        return out
    if not isinstance(fields, list):
        diag.err("schema", "schema.fields 必须是数组。")
        return out
    for i, f in enumerate(fields):
        if not isinstance(f, dict):
            diag.err("schema", "fields[%d] 必须是对象。" % i)
            continue
        t = f.get("type")
        if t is None:
            continue
        if t not in SCHEMA_TYPES:
            diag.err("schema", "fields[%d] 的 type %r 不受支持——hud.js 走 "
                               "`TYPES[type] || TYPES.text` 会【静默回落成 text】，"
                               "该项看着像渲染了其实结构全丢。合法 type：%s。"
                     % (i, t, list(SCHEMA_TYPES)))
    return out


def normalize_config(raw, config_path, diag):
    if not isinstance(raw, dict):
        raise BuildError("配置顶层必须是 JSON 对象。")
    cfg = {k: v for k, v in raw.items() if not k.startswith("_")}

    cv = cfg.get("chatVersion", 1)
    if cv != 1:
        diag.err("config", "chatVersion 必须为 1（沙盒模式由它开启），当前 %r。" % cv)
    pd = cfg.get("pageDepth", 2)
    if pd != 2:
        diag.err("config", "pageDepth 固定为 2，当前 %r。" % pd)

    markers = dict(DEFAULT_MARKERS)
    user_markers = cfg.get("markers") or {}
    if not isinstance(user_markers, dict):
        diag.err("config", "markers 必须是对象。")
        user_markers = {}
    markers.update({k: v for k, v in user_markers.items() if not k.startswith("_")})
    for k, v in markers.items():
        if not isinstance(v, str) or not v.strip():
            diag.err("config", "markers.%s 必须是非空字符串。" % k)

    modes, pins = normalize_modes(cfg, diag)

    base = Path(config_path).resolve().parent
    asset_dir = cfg.get("assetDir", "sbk")
    if not isinstance(asset_dir, str):
        diag.err("config", "assetDir 必须是字符串。")
        asset_dir = "sbk"
    adir = Path(asset_dir)
    if not adir.is_absolute():
        adir = base / adir

    scenes = cfg.get("sceneRules") or []
    if not isinstance(scenes, list):
        diag.err("config", "sceneRules 必须是数组。")
        scenes = []

    out = {
        "chatVersion": 1,
        "pageDepth": 2,
        # 不给 default：缺失必须报错，而不是静默变成空串
        "beginning": _need_str(cfg, "beginning", diag),
        "statusbar": _need_str(cfg, "statusbar", diag),
        "personality": cfg.get("personality") or "",
        "assetDir": adir,
        # 作者基线走与 theme.js 一致的 token/tune/危险值校验，再进 boot 信封。
        "theme": normalize_author_theme(cfg.get("theme") or {}, adir, diag),
        # 六维风格包源（路径数组或内联映射）→ 稍后由 build_presets 编译进 cfg["presets"]
        "presetSources": load_presets(cfg.get("presets"), base, diag),
        "preset": cfg.get("preset") or "",
        "modes": modes,
        "pinnedFields": pins,
        "schema": normalize_schema(cfg.get("schema") or {}, diag),
        "protocolTag": cfg.get("protocolTag") or "状态",
        "hostId": check_host_id(cfg.get("hostId") or "sbk-hud", diag),
        "markers": markers,
        "sceneRules": scenes,
        "idBase": cfg.get("idBase", -1),
        "splitThreshold": cfg.get("splitThreshold", DEFAULT_SPLIT_THRESHOLD),
    }
    th = out["splitThreshold"]
    if not isinstance(th, int) or th < 1000 or th > MAX_SOURCE_RULE:
        diag.err("config", "splitThreshold 必须是 1000..%d 的整数（固定安全上限不可调高），当前 %r。"
                 % (MAX_SOURCE_RULE, th))
        out["splitThreshold"] = DEFAULT_SPLIT_THRESHOLD
    if not isinstance(out["personality"], str):
        diag.err("config", "personality 必须是字符串。")
        out["personality"] = ""
    if not isinstance(out["idBase"], int) or out["idBase"] >= 0:
        diag.err("config", "idBase 必须是负整数（规则 id 为负数），当前 %r。" % out["idBase"])
        out["idBase"] = -1
    return out


# ---------------------------------------------------------------- 构建

def escape_js_regex(s):
    """按 JS 正则语法转义字面标记。

    不能直接用 Python 的 re.escape：它还会转义 `-` 等字符，而 `\\-` 在 JS 的 unicode 模式
    （`u` 标志）下是非法 IdentityEscape。这里只转义 JS 的 SyntaxCharacter 与 `/`。
    """
    return re.sub(r"([\^\$\\\.\*\+\?\(\)\[\]\{\}\|/])", r"\\\1", s)


def _rule(rid, name, marker, body):
    """每条规则恰好四键：id/scriptName/findRegex/replaceString，id 为负数。
    findRegex 一律 slash 形态（硬约束 21）。marker 用正文里不会出现的字面标记，
    绝不用 /(?!)/ 这类零宽写法当"永不匹配"——那会触发 empty-match 撤销整条规则（§5.2）。"""
    return {
        "id": rid,
        "scriptName": name,
        "findRegex": "/" + escape_js_regex(marker) + "/",
        "replaceString": body,
    }


# ------------------------- 气泡面板接缝一致性（诊断分类名沿用 "双模一致性"，见下方 diag 调用）
# 实机缺陷：功能栏正常，但气泡里 [状态]…[/状态] 原样暴露给用户。
# 根因是气泡内状态面板需要【两样东西同时存在】，而生成器只读了其中一样：
#   1) modes.status=true —— 让 boot 调 SBK.ui.snapshot.auto(schema) 去订阅 mount/done；
#   2) 一条场景规则 —— 把 [状态]…[/状态] 换成带 hydrate 选择器类的外壳。
# hud.js 的 hydrate() 靠 SBK.dom.all(root, '.sbk-snap--raw') 找待升级节点：
# 少了那条外壳规则，hydrate() 永远找不到东西 → 气泡面板静默失效。
# 两样都缺时反而无害（气泡面板干脆没开），所以必须做【双向】一致性校验。

HYDRATE_CLASS_FALLBACK = "sbk-snap--raw"
# hud-render.js（新拆分）或 hud.js（旧单文件兼容）里的升级选择器。
_HYDRATE_SELECTOR_RE = re.compile(
    r"""dom\.all\(\s*root\s*,\s*['"]\.([A-Za-z0-9_-]+)['"]""")


def hydrate_class(asset_dir, diag=None):
    """从 HUD 渲染模块读出升级选择器类名，不在生成器里复制真值。"""
    tried = []
    for name in ("hud-render.js", "hud.js"):
        p = Path(asset_dir) / name
        tried.append(str(p))
        if not p.is_file():
            continue
        m = _HYDRATE_SELECTOR_RE.search(p.read_text(encoding="utf-8"))
        if m:
            return m.group(1), True
    if diag is not None:
        diag.warn("双模一致性",
                  "没能从 HUD 渲染模块 %s 读出升级选择器（期望形如 "
                  "SBK.dom.all(root, '.%s')）——本次按常量 %r 校验；若类名已改，"
                  "请同步 _HYDRATE_SELECTOR_RE。"
                  % (" / ".join(tried), HYDRATE_CLASS_FALLBACK, HYDRATE_CLASS_FALLBACK))
    return HYDRATE_CLASS_FALLBACK, False


_BACKREF_RE = re.compile(r"\$(?:[1-9]|&|<[^>]+>)")
_CLASS_ATTR_RE = re.compile(r"""class\s*=\s*["']([^"']*)["']""")


def _class_tokens(rs):
    """取 replaceString 里所有 class 属性的类名 token 集合。

    必须按 token 比而不是按子串比：`class="sbk-snap--raw"` 的子串里含 `sbk-snap`，
    但 CSS 选择器 `.sbk-snap` 并不会命中它 —— 子串比会漏掉「缺基类」这种真缺陷。
    """
    toks = set()
    for m in _CLASS_ATTR_RE.finditer(rs):
        toks.update(m.group(1).split())
    return toks


def _shell_hint(cfg, cls):
    """给出可直接粘贴的修复样板。方括号在正则里是元字符，必须转义（漏转义会变成字符类）。"""
    tag = cfg["protocolTag"]
    return ('sceneRules 里加一条：{"scriptName": "sbk-snap", "findRegex": '
            '"/\\\\[%s\\\\]([\\\\s\\\\S]*?)\\\\[\\\\/%s\\\\]/", "replaceString": '
            '"<div class=\\"sbk-snap sbk-card sbk-pre %s\\">$1</div>"}'
            '（findRegex 写进 JSON 时反斜杠要再叠一层，如上）' % (tag, tag, cls))


def _dual_mode_on(cfg, diag, cls, base, shells, base_only):
    """modes.status=true：必须有一条产出 .<cls> 外壳的场景规则。"""
    if not shells:
        if base_only:
            # A2：排版类对了、升级类漏了。最阴的一种——外观像「渲染成卡片了」，
            # 但 hydrate() 的 SBK.dom.all(root,'.<cls>') 命中不到，结构化渲染永不接管。
            for label, _ in base_only:
                diag.err("双模一致性",
                         "modes.status 已开，场景规则 %r 的产物带了 .%s 但【缺 .%s】——"
                         "hud.js 的 hydrate() 正是靠 SBK.dom.all(root, '.%s') 找待升级节点，"
                         "少这个类 JS 升级永不触发，气泡里只会留一段纯文本。"
                         "修法：把 .%s 加进该规则根元素的 class（形如 "
                         "class=\"%s sbk-card sbk-pre %s\"）。"
                         % (label, base, cls, cls, cls, base, cls))
        else:
            # A1：两样只有一样。实机现象＝气泡里 [状态]…[/状态] 原样暴露给用户。
            diag.err("双模一致性",
                     "modes.status 已开，但 sceneRules 里没有任何一条产出 .%s 外壳的规则——"
                     "boot 会调 SBK.ui.snapshot.auto()，可 hydrate() 靠 "
                     "SBK.dom.all(root, '.%s') 找节点，永远找不到东西，状态面板静默失效："
                     "实机现象是气泡里 [%s]…[/%s] 原样暴露给用户。"
                     "修法：%s；或若本就不想要气泡内状态面板，把 modes.status 改成 false。"
                     % (cls, cls, cfg["protocolTag"], cfg["protocolTag"],
                        _shell_hint(cfg, cls)))
        return

    for label, sc in shells:
        rs, fr = sc["replaceString"], sc.get("findRegex")
        # A3：hydrate 读的是节点 textContent，壳里没有回填 → 拿到空串 → SBK.parse 解析不出
        # 字段，走「原样留着」兜底分支，等于白渲染一次。
        if not _BACKREF_RE.search(rs):
            diag.warn("双模一致性",
                      "场景规则 %r 产出了 .%s 外壳，但 replaceString 里没有 $1/$& 之类的回填——"
                      "hydrate() 读的是该节点的 textContent，壳内为空则解析不出任何字段，"
                      "会走「原样留着」的兜底分支。修法：壳内放 $1（且只放 $1，"
                      "别再套 <span>状态</span> 之类装饰，多出来的文字会被当成块体首行）。"
                      % (label, cls))
        # A4：改了 protocolTag 却忘了改外壳规则的匹配式 —— 规则装上了但永不命中。
        if isinstance(fr, str) and cfg["protocolTag"] not in fr:
            diag.warn("双模一致性",
                      "场景规则 %r 是 .%s 外壳，但它的 findRegex 里不含协议标签 %r——"
                      "改过 protocolTag 后忘了同步匹配式的话，这条规则永不命中，"
                      "气泡内状态面板（modes.status）一样不工作。"
                      "修法：把匹配式改成 /\\[%s\\]([\\s\\S]*?)\\[\\/%s\\]/"
                      "（方括号是正则元字符，必须转义）。"
                      % (label, cls, cfg["protocolTag"],
                         cfg["protocolTag"], cfg["protocolTag"]))


def _dual_mode_off(cfg, diag, cls, shells):
    """modes.status=false：不该有产出 .<cls> 外壳的规则（反向不一致）。"""
    # B1：规则把协议块换成了外壳，但 boot 不会调 snapshot.auto() → 没人订阅 mount/done →
    # hydrate() 一次都不跑，气泡里留一个永不升级的死壳（纯文本），且原始标记已被替换掉，
    # pinned 精简条从气泡文本兜底读取时也拿不到 [状态] 标记了。
    for label, _ in shells:
        diag.err("双模一致性",
                 "场景规则 %r 产出了 .%s 外壳，但 modes.status 是 false——"
                 "boot 不会调 SBK.ui.snapshot.auto()，没人订阅 mount/done，hydrate() 一次都不跑，"
                 "气泡里只会留一个永不升级的死壳。修法：把 modes.status 改成 true；"
                 "或删掉这条规则。" % (label, cls))


def _warn_no_data_outlet(cfg, diag):
    """B2：status 与 pinned 都关 → 协议块没有任何渲染出口。

    2.0 只看这两个：chrome 是入口按钮组，【不渲染业务数据】，开着也不构成出口。
    这不是「配置错」而是「基座白装」，故只告警不报错——允许有人只要主题/样式与入口。
    """
    diag.warn("双模一致性",
              "modes.status 与 modes.pinned 双关——协议块 [%s]…[/%s] 没有任何渲染出口，"
              "状态数据整体不显示（基座只剩样式、主题与功能栏入口）。"
              "注意 modes.chrome 不算出口：它只放入口按钮，不渲染业务数据。"
              "若确实只想要样式请忽略；否则至少开 modes.status。"
              % (cfg["protocolTag"], cfg["protocolTag"]))


def check_dual_mode(cfg, diag, asset_dir=None):
    """气泡面板接缝一致性：modes.status 与「外壳场景规则」必须【同时】在或【同时】不在。

    函数名与诊断分类名沿用 1.0 的 dual_mode/「双模一致性」叫法（对外可见，不改）。

    返回诊断用的中间量 {cls, base, shells, baseOnly}，方便测试与 --verbose 复核。
    """
    snap_on = bool(cfg["modes"].get("status"))
    # B2 与选择器无关，只看两个数据出口开关，故先判。chrome 不算出口。
    if not snap_on and not cfg["modes"].get("pinned"):
        _warn_no_data_outlet(cfg, diag)
    # 无可查对象时【不读 hud.js 也不告警】：status 关且没有任何场景规则 →
    # 气泡内面板干脆没开启，不存在「只开了一半」的不一致。
    scenes = [sc for sc in cfg["sceneRules"]
              if isinstance(sc, dict) and isinstance(sc.get("replaceString"), str)]
    if not snap_on and not scenes:
        return {"cls": None, "base": None, "shells": [], "baseOnly": []}

    cls, _ = hydrate_class(asset_dir if asset_dir is not None else cfg["assetDir"], diag)
    # 基类由升级类名推导（sbk-snap--raw → sbk-snap），同样不写死：
    # hud.js snapshot() 的根元素必须带基类，base.css 靠它重置 message-body 的
    # opacity/.white-space（硬约束 11），少了它排版必烂。
    base = cls.split("--")[0] if "--" in cls else "sbk-snap"
    shells, base_only = [], []
    for i, sc in enumerate(cfg["sceneRules"]):
        if not isinstance(sc, dict):
            continue
        rs = sc.get("replaceString")
        if not isinstance(rs, str):
            continue
        label = sc.get("scriptName") if isinstance(sc.get("scriptName"), str) \
            else "sceneRules[%d]" % i
        toks = _class_tokens(rs)
        if cls in toks:
            shells.append((label, sc))
        elif base in toks:
            base_only.append((label, sc))

    if snap_on:
        _dual_mode_on(cfg, diag, cls, base, shells, base_only)
    else:
        _dual_mode_off(cfg, diag, cls, shells)
    return {"cls": cls, "base": base,
            "shells": [n for n, _ in shells], "baseOnly": [n for n, _ in base_only]}


def build(cfg, diag, strip=True):
    adir, mk = cfg["assetDir"], cfg["markers"]
    if not Path(adir).is_dir():
        diag.err("assets", "资源目录不存在：%s" % adir)

    rules, assets_report = [], {}
    rid = cfg["idBase"]

    # ---- 1. sbk-css：【只装】base.css 骨架 ----
    # 🚨 2.1 单一运行时所有权（审计报告高风险 1）：这里【不再】拼 config.theme 的永久覆写。
    #    1.0 把作者主题编译进这条静态规则，导致 prefs.enabled(false) 只清得掉 theme.js 的
    #    动态 <style>，静态覆写还在 → 「关闭美化＝完全跟随平台」不成立。
    #    作者基线现在走 boot 信封（theme_envelope）交给 theme.js，与 preset/overrides
    #    合成同一个 #sbk-theme-vars。整卡的主题【只有一个写入者】。
    css_src, loaded, _ = load_assets(adir, ("base.css",), diag, strip)
    assets_report["sbk-css"] = loaded
    rules.append(_rule(rid, "sbk-css", mk["css"], "<style>\n%s\n</style>" % css_src))
    rid -= 1

    # ---- 1b. 风格包编译（进 boot 信封，不进 CSS）----
    cfg["presets"] = build_presets(cfg, diag)
    if cfg.get("preset") and cfg["preset"] not in cfg["presets"]:
        diag.err("config", "preset 默认包名 %r 不在已注册的风格包里（现有：%s）——"
                           "theme.js 的 apply() 只接受已注册的包名，实机会静默用「默认」"
                           "（即只有 author base，风格包等于没生效）。"
                 % (cfg["preset"], sorted(cfg["presets"])))

    threshold = cfg["splitThreshold"]
    layouts = []

    # ---- 2. sbk-core：内核/存储/编排/主题/设置，按完整模块边界自动装箱 ----
    _, loaded, _ = load_assets(adir, CORE_ASSETS, diag, strip)
    assets_report["sbk-core"] = loaded
    core_rules, rid, core_layout = emit_script_rules(
        rid, "sbk-core", mk["core"], loaded, threshold, diag, strip)
    rules.extend(core_rules)
    layouts.extend(core_layout)

    # ---- 3. sbk-ui：协议/HUD 渲染/UI kit/panel/stage，顺序不可变 ----
    _, loaded, missing = load_assets(adir, UI_ASSETS, diag, strip)
    assets_report["sbk-ui"] = loaded
    if loaded:
        ui_rules, rid, ui_layout = emit_script_rules(
            rid, "sbk-ui", mk["ui"], loaded, threshold, diag, strip)
        rules.extend(ui_rules)
        layouts.extend(ui_layout)
    else:
        diag.warn("sbk-ui", "protocol.js/hud.js/ui.js 全部缺失——本条规则已省略（%s）。"
                  % "/".join(missing))

    # ---- 4. sbk-hud：功能栏宿主容器 HTML（chrome 与 pinned 共用一个宿主）----
    # 2.0：不再由已废除的 modes.hud 决定。chrome（入口按钮组）与 pinned（精简条）
    # 都挂在这个容器里，任一开启就必须产出它；两个都关则整条省略。
    need_host = cfg["modes"]["chrome"] or cfg["modes"]["pinned"]
    if need_host:
        rules.append(_rule(rid, "sbk-hud", mk["hud"], hud_host_html(cfg["hostId"])))
        rid -= 1
        # §5.6 功能栏静态：h_() 只在装载时跑一次，且其正则输入是 statusbar 字段自身。
        # 触发串不在 statusbar 里 → 宿主容器永远不出现 → chrome/pinned 全部失效。
        if mk["hud"] not in cfg["statusbar"]:
            on = [k for k in ("chrome", "pinned") if cfg["modes"][k]]
            diag.err("sbk-hud", "modes.%s 已启用，但 statusbar 字段里找不到触发串 %r——"
                     "功能栏正则的输入是 statusbar 自身（§5.6），宿主容器永远不会出现，"
                     "功能栏入口与精简条都不会渲染。" % ("/".join(on), mk["hud"]))

    # ---- 5. sbk-boot：启动调用，排最后确保内核已定义 ----
    rules.append(_rule(rid, "sbk-boot", mk["boot"], "<script>\n%s\n</script>" % boot_script(cfg, diag)))
    rid -= 1

    # ---- 6+. 场景规则 ----
    for i, sc in enumerate(cfg["sceneRules"]):
        label = "sceneRules[%d]" % i
        if not isinstance(sc, dict):
            diag.err(label, "必须是对象。")
            continue
        name = sc.get("scriptName")
        fr = sc.get("findRegex")
        rs = sc.get("replaceString")
        if not isinstance(name, str) or not name.strip():
            diag.err(label, "scriptName 必须是非空字符串。")
            continue
        if not isinstance(fr, str) or not isinstance(rs, str):
            diag.err(label, "findRegex 与 replaceString 必须是字符串。")
            continue
        if name.startswith("__"):
            diag.err(label, "scriptName 以 __ 开头——worker 会整条丢弃（§5.6）。")
        rules.append({"id": rid, "scriptName": name, "findRegex": fr, "replaceString": rs})
        rid -= 1

    # ---- 7. 气泡面板接缝：modes.status 与外壳场景规则必须同时在/同时不在 ----
    # 放在场景规则装配之后：需要看全 cfg["sceneRules"] 才能判断外壳规则是否存在。
    # 结果只经 diag 上报，不塞进 assets_report——那个 dict 被 render_report 当
    # {规则名: [资源条目]} 遍历，塞异形值会让报告渲染崩。
    check_dual_mode(cfg, diag, adir)

    return rules, assets_report, layouts


def validate_rules(rules, cfg, diag):
    """逐条跑全部校验，返回每条的度量。"""
    # 事实卡 §6 regexList 上限 130 条
    if len(rules) > HARD["regexList"]:
        diag.err("rules", "共 %d 条 > 上限 %d 条（§6）。" % (len(rules), HARD["regexList"]))

    scene_meta = {}
    for i, sc in enumerate(cfg["sceneRules"]):
        if isinstance(sc, dict) and isinstance(sc.get("scriptName"), str):
            scene_meta[sc["scriptName"]] = sc

    # 输入文本长度：预算 = max(262144, 输入长度×4)。保守取 statusbar/beginning 里较短者，
    # 因为消息正文长度未知；用最小的输入长度得到最紧的预算 → 不会低估风险（§5.2）。
    input_len = max(1, min(len(cfg["statusbar"]) or 1, len(cfg["beginning"]) or 1))

    seen_ids, seen_names, metrics = set(), set(), []
    for r in rules:
        where = "规则[%s]" % r["scriptName"]
        if set(r.keys()) != {"id", "scriptName", "findRegex", "replaceString"}:
            diag.err(where, "必须恰好四键 id/scriptName/findRegex/replaceString，当前 %s。"
                     % sorted(r.keys()))
        if not isinstance(r["id"], int) or r["id"] >= 0:
            diag.err(where, "id 必须是负数，当前 %r。" % r["id"])
        if r["id"] in seen_ids:
            diag.err(where, "id %r 重复。" % r["id"])
        seen_ids.add(r["id"])
        if r["scriptName"] in seen_names:
            diag.warn(where, "scriptName 重复。")
        seen_names.add(r["scriptName"])

        check_lengths(r, diag, where)
        if len(r["replaceString"]) > MAX_SOURCE_RULE:
            diag.err(where, "replaceString %d 字符 > SBK 交付安全上限 %d。所有最终规则都必须留足"
                            "编辑器保存余量；资源脚本请拆完整 IIFE，boot/场景规则请拆配置或规则。"
                     % (len(r["replaceString"]), MAX_SOURCE_RULE))
        check_slash_form(r, diag, where)
        check_module_syntax(r["replaceString"], diag, where)
        check_csp(r["replaceString"], diag, where)
        check_sanitize(r["replaceString"], diag, where)
        meta = scene_meta.get(r["scriptName"], {})
        check_tags(r["replaceString"], diag, where,
                   allow_non_whitelist=bool(meta.get("allowNonWhitelistTags")))
        exp = meta.get("expectedMatches", 1)
        if not isinstance(exp, int) or exp < 1:
            exp = 1
        m = estimate_budget(r, input_len, exp, diag, where)
        m["scriptName"] = r["scriptName"]
        m["id"] = r["id"]
        m["nameLen"] = len(r["scriptName"])
        m["findLen"] = len(r["findRegex"])
        metrics.append(m)
    return metrics


def validate_top_level(doc, diag):
    """顶层 6 键 + 长度硬限（§6）。"""
    keys = set(doc.keys())
    want = {"chatVersion", "pageDepth", "statusbar", "beginning", "personality", "regex_scripts"}
    if keys != want:
        diag.err("top", "顶层必须恰好 6 键 %s，当前 %s。" % (sorted(want), sorted(keys)))
    if len(doc["beginning"]) > HARD["beginning"]:
        diag.err("top", "beginning %d 字符 > 4000（§6；源码归一常量与 UI 计数器一致）。"
                 % len(doc["beginning"]))
    if len(doc["statusbar"]) > HARD["statusbar"]:
        diag.err("top", "statusbar %d 字符 > 200（§6）——超出被静默截断。" % len(doc["statusbar"]))
    # imageUrl 不是 6 键之一，但配置里若出现 URL 字段仍按 2048 硬限（§6）
    for m in re.finditer(r'"(?:imageUrl|avatarUrl)"\s*:\s*"([^"]*)"', json.dumps(doc, ensure_ascii=False)):
        if len(m.group(1)) > HARD["imageUrl"]:
            diag.err("top", "imageUrl %d 字符 > 2048（§6）。" % len(m.group(1)))
    # 可见内容规则的触发串必须能在 statusbar / beginning / 其他规则的 replaceString 里找到，
    # 否则页面上永远不出现（§5.6 功能栏正则输入是 statusbar 自身）。
    soup = [doc["statusbar"], doc["beginning"]] + [r["replaceString"] for r in doc["regex_scripts"]]
    for r in doc["regex_scripts"]:
        visible = re.sub(r"<(style|script)\b.*?</\1\s*>", "", r["replaceString"], flags=re.I | re.S).strip()
        if not visible:
            continue      # 纯 CSS/JS 规则：装卡即抽出，匹配式故意谁都不引用（§5.6）
        kind, body, flags = classify_pattern(r["findRegex"])
        if kind != "slash":
            continue
        others = [t for t in soup if t is not r["replaceString"]]
        # 真拿正则去搜，而不是抠字面量：形如 /\[状态\]([\s\S]*?)\[\/状态\]/ 的模式
        # 只有编译后才能确认它在 beginning 里命中。
        try:
            rx = _js_re_to_py(body, flags)
        except re.error:
            continue          # 编译不了就不猜，check_slash_form 已另行告警
        if any(rx.search(t) for t in others):
            continue
        diag.warn("规则[%s]" % r["scriptName"],
                  "会产出可见内容，但匹配式 %s 在 statusbar / beginning / 其他规则的 "
                  "replaceString 里都匹配不到——页面上永远不会出现。"
                  "把触发串写进 statusbar 或 beginning（人设的输出约定也要对得上）。"
                  % r["findRegex"])


def assemble(cfg, rules):
    return {
        "chatVersion": 1,          # 必须 1：沙盒模式由它开启
        "pageDepth": 2,            # 固定 2
        "statusbar": cfg["statusbar"],
        "beginning": cfg["beginning"],
        "personality": cfg["personality"],
        "regex_scripts": rules,
    }


# ---------------------------------------------------------------- 报告

def render_report(doc, metrics, assets_report, diag, verbose=False):
    L = []
    L.append("=" * 72)
    L.append("SBK 构建报告")
    L.append("=" * 72)
    L.append("chatVersion=%s  pageDepth=%s  规则 %d 条（上限 %d）"
             % (doc["chatVersion"], doc["pageDepth"], len(doc["regex_scripts"]), HARD["regexList"]))
    L.append("statusbar %d/200  beginning %d/4000  personality %d 字符"
             % (len(doc["statusbar"]), len(doc["beginning"]), len(doc["personality"])))
    L.append("")
    L.append("%-4s %-14s %8s %8s %10s %10s" % ("id", "scriptName", "find", "replace", "估算输出", "预算"))
    L.append("-" * 72)
    for m in metrics:
        L.append("%-4s %-14s %8d %8d %10d %10d"
                 % (m["id"], m["scriptName"][:14], m["findLen"], m["replaceLen"],
                    m["estOutput"], m["budget"]))
    total = sum(m["replaceLen"] for m in metrics)
    L.append("-" * 72)
    L.append("replaceString 合计 %d 字符" % total)

    layouts = (assets_report or {}).get("__layout__") or []
    if layouts:
        L.append("")
        L.append("脚本拆条（按文件边界，顺序即装载顺序）：")
        L.append("  %-12s %-16s %7s  %s" % ("scriptName", "marker", "chars", "含源文件"))
        for it in layouts:
            L.append("  %-12s %-16s %7d  %s"
                     % (it["scriptName"], it["marker"], it["chars"], " + ".join(it["files"])))

    if verbose and assets_report:
        L.append("")
        L.append("资源合并明细（剥注释前 → 后）：")
        for rule_name, items in assets_report.items():
            if rule_name == "__layout__":
                continue
            for it in items:
                saved = it["raw"] - it["out"]
                pct = (saved * 100.0 / it["raw"]) if it["raw"] else 0
                L.append("  %-10s %-12s %6d → %6d  省 %d (%.1f%%)"
                         % (rule_name, it["name"], it["raw"], it["out"], saved, pct))

    if diag.notes:
        L.append("")
        L.append("说明 %d 条：" % len(diag.notes))
        for n in diag.notes:
            L.append("  · " + n)
    L.append("")
    L.append("WARN %d 条：" % len(diag.warns))
    for w in diag.warns:
        L.append("  ! " + w)
    L.append("ERROR %d 条：" % len(diag.errors))
    for e in diag.errors:
        L.append("  x " + e)
    L.append("")
    L.append("复核建议：python validate.py <out.json> --type regex --platform mmdsandbox")
    L.append("（长度门禁：name/regex 按 UI 显示值保守维护，content 按已确认编辑器 20000；"
             "所有生成脚本另受不可调高的 18000 最终门禁）")
    return "\n".join(L)


def check_split_base_markers(cfg, layouts, diag):
    """多箱时原始基名 marker 不再对应任何规则；残留在可见字段会原样泄漏。"""
    sources = [cfg.get("statusbar", ""), cfg.get("beginning", ""), cfg.get("personality", "")]
    sources.extend(sc.get("replaceString", "") for sc in cfg.get("sceneRules", []) if isinstance(sc, dict))
    for group, base in (("sbk-core", cfg["markers"]["core"]), ("sbk-ui", cfg["markers"]["ui"])):
        boxes = [it for it in layouts if it["scriptName"].startswith(group + "-")]
        if len(boxes) < 2 or not any(base in text for text in sources):
            continue
        diag.warn(group, "资源已拆成 %d 条，原始基名 marker %r 不再对应任何规则，却仍残留在"
                         "statusbar/beginning/personality/场景替换内容中，会原样显示。删除它；脚本/样式"
                         "模块装卡即抽出，不需要把生成后的 -N marker 写进正文。" % (len(boxes), base))


# ---------------------------------------------------------------- 编排

def build_document(config_path, strip=True, diag=None):
    """读配置 → 装配 → 校验。返回 (doc, metrics, assets_report, diag)。"""
    diag = diag or Diag()
    p = Path(config_path)
    if not p.is_file():
        raise BuildError("配置文件不存在：%s" % config_path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BuildError("配置文件不是合法 JSON：%s" % exc)

    cfg = normalize_config(raw, p, diag)
    rules, assets_report, layouts = build(cfg, diag, strip=strip)
    assets_report["__layout__"] = layouts
    check_split_base_markers(cfg, layouts, diag)
    doc = assemble(cfg, rules)
    metrics = validate_rules(rules, cfg, diag)
    validate_top_level(doc, diag)

    # 产出必须能过 python -m json.tool：自检一次「序列化 → 回读 → 内容等价」
    text = dumps_sbk(doc)
    check_script_close(text, diag, "output")
    try:
        back = json.loads(text)
        if back != doc:
            diag.err("output", "序列化后回读与原始文档不等价——转义处理有误。")
    except (TypeError, ValueError) as exc:
        diag.err("output", "产出不是合法 JSON：%s" % exc)
    return doc, metrics, assets_report, diag


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="build_sbk.py",
        description="SBK 生成器：声明式 sbk.config.json → 可导入 MMD 创卡页的 6 键正则 JSON。",
        epilog="产出可再用 skill 校验器复核："
               "python validate.py <out.json> --type regex --platform mmdsandbox 。"
               "常规交付按 UI 显示值 name<=20 / regex<=1000 与已确认的 content<=20000 维护；"
               "生成脚本另受不可调高的 18000 最终门禁。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", help="sbk.config.json 路径")
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    ap.add_argument("--no-strip-comments", action="store_true",
                    help="不剥注释（默认剥：core+theme 带注释已逼近编辑器显示上限 20000）")
    ap.add_argument("--verbose", "-v", action="store_true", help="打印资源合并明细")
    ap.add_argument("--force", action="store_true", help="即使有 ERROR 也写出文件（仅用于调试）")
    a = ap.parse_args(argv)

    try:
        doc, metrics, assets, diag = build_document(a.config, strip=not a.no_strip_comments)
    except BuildError as exc:
        sys.stderr.write("配置错误：%s\n" % exc)
        return 2

    print(render_report(doc, metrics, assets, diag, verbose=a.verbose))

    if diag.errors and not a.force:
        sys.stderr.write("\n有 %d 条 ERROR，未写出文件。修完重跑，或加 --force 强制写出。\n"
                         % len(diag.errors))
        return 1

    out = Path(a.out)
    try:
        if out.parent and str(out.parent) not in ("", "."):
            out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(dumps_sbk(doc), encoding="utf-8")
    except OSError as exc:
        sys.stderr.write("写出失败：%s\n" % exc)
        return 2
    print("\n已写出：%s（%d 字节）" % (out, out.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
