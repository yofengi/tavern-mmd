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

已知与该校验器的冲突（只记录，不改它）：
  1. 长度上限取的是**创卡页 UI 显示值**，与事实卡 §6 逐字常量 `var Us={...}` 不同：
       beginning 10240 vs 真值 4000（UI 也显示 4000 → 校验器偏松，会漏放行超长开场白）
       name      20    vs 真值 200
       regex     1000  vs 真值 4096
       content   20000 vs 真值 100000
     本脚本双轨处理：运行时真值超出 → ERROR（会被 Ws() 静默截断）；
     UI 值超出 → WARN（导入不受影响，但作者一进编辑器就被截断）。
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
  beginning     str   开场白正文；若含模式 B 的状态块触发串需与 persona 约定一致
  statusbar     str   功能栏字段。模式 A 必须包含 markers.hud（默认 "{{hud}}"）
选填：
  personality   str   人设文本（导入页不读该字段，仅随 JSON 归档）
  chatVersion   int   必须 1（缺省即 1）
  pageDepth     int   固定 2（缺省即 2）
  theme         obj   主题 token。{dark:{...},light:{...}} 或扁平（两套同值）
                      语义名见 theme.js MAP；也可直给 --chat-* / --sbk-*
  modes         obj   {hud:bool, snapshot:bool}。A 常驻 HUD / B 消息内快照
  schema        obj   状态栏 schema，原样传给 SBK.ui.hud / SBK.ui.snapshot
  protocolTag   str   数据协议块标签名，默认 "状态"（对应 [状态]…[/状态]）
                      🚨 一律方括号（plan.md 已裁决第 9 条）：§5.4 的剥壳正则会把 <状态>
                      这类中文尖括号标签整个删掉，模式 A 的 HUD 从气泡文本兜底读取时
                      标记已经没了。方括号不是标签，全链路都活着。
                      正则里方括号是元字符，必须写 /\[状态\]([\s\S]*?)\[\/状态\]/
  hostId        str   HUD 宿主容器 id，默认 "sbk-hud"
  markers       obj   五个固定规则的触发串，键 css/core/ui/hud/boot
  sceneRules    list  场景规则；每项 {scriptName, findRegex, replaceString,
                      expectedMatches?(int,默认1), allowNonWhitelistTags?(bool)}
  idBase        int   规则 id 起始负数，默认 -1（依次 -1,-2,…）
  splitThreshold int  脚本自动拆条阈值，默认 18000（编辑器上限 20000 留 2000 余量）

自动拆条（plan.md 已裁决第 7 条）
--------------------------------
`sbk-core`（core.js+theme.js）与 `sbk-ui`（protocol.js+hud.js+ui.js）超过 splitThreshold
就按**文件边界**拆成 `sbk-core-1/-2`、`sbk-ui-1/-2`…，各自获得唯一的 slash 形态标记。
🚨 拆条严格保持装载顺序 protocol.js → hud.js → ui.js：三者都依赖 core.js 已定义，
且 hud.js/ui.js 用「合并挂载」往 `SBK.ui` 上追加，顺序错了会出现未定义引用。
`regex_scripts` 数组序即装载顺序（worker 按 regexSort 升序）。
绝不切开单个文件——每个文件本身是完整 IIFE，切开必然语法错。单文件自身超阈值时
允许它独占一条并告警（当前 ui.js 剥注释后 19537 字符，距编辑器上限 20000 仅余 444）。

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
# 运行时真值（逐字取自 `var Us={...}`），超出即静默截断 → 视为 ERROR。
HARD = {
    "beginning": 4000,
    "statusbar": 200,
    "imageUrl": 2048,
    "name": 200,          # scriptName
    "regex": 4096,        # findRegex
    "content": 100000,    # replaceString
    "regexList": 130,
}
# 创卡页编辑器 UI 显示值：不影响导入，但作者一进编辑器就被截断 → 视为 WARN。
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
# plan.md 2.1：内核/主题 → sbk-core；协议/HUD/组件 → sbk-ui（已裁决拆两条）。
# 🚨 元组顺序 = 装载顺序，绝不重排也绝不排序：
#   core.js 先建 window.SBK，theme.js 才能往上挂；
#   protocol.js/hud.js/ui.js/ui-stage.js 都依赖 core 已定义，
#   且 hud.js 与 ui*.js 用「合并挂载」往 SBK.ui 上追加 → 顺序错了会出现未定义引用。
# 缺失的文件由 load_assets 跳过并告警，所以这里可以预留还没交付的文件名。
CORE_ASSETS = ("core.js", "theme.js")
UI_ASSETS = ("protocol.js", "hud.js", "ui.js", "ui-stage.js")


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
# core+theme 带注释已 17969 字符，逼近编辑器显示上限 20000（事实卡 §6 运行时真值 100000）。

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
    """事实卡 §6：运行时真值硬限（超出静默截断→ERROR），编辑器 UI 值告警。"""
    pairs = (("scriptName", "name"), ("findRegex", "regex"), ("replaceString", "content"))
    for field, key in pairs:
        v = rule[field]
        n = len(v)
        if n > HARD[key]:
            diag.err(where, "%s %d 字符 > 运行时上限 %d——超出被 Ws() 静默截断（§6）。"
                     % (field, n, HARD[key]))
        elif n > UI_SOFT[key]:
            diag.warn(where, "%s %d 字符 > 创卡页编辑器显示上限 %d（运行时真值 %d）——"
                      "导入不受影响，但作者一进编辑器就被截断（§6）。"
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

    `names` 的顺序**就是装载顺序**，绝不重排：protocol.js → hud.js → ui.js 都依赖
    core.js 已定义，且 hud.js/ui.js 用「合并挂载」往 SBK.ui 上追加，顺序错了会出现未定义引用。
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
DEFAULT_SPLIT_THRESHOLD = 18000     # 20000 UI 上限留 2000 安全余量


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
        # 单文件超阈值时允许独占一条，但仍要提醒它逼近 UI 上限 20000
        if item["chars"] > threshold:
            diag.warn(item["scriptName"],
                      "%d 字符 > 拆条阈值 %d，且已无法再拆（%s 单文件即超阈值）。"
                      "距编辑器显示上限 %d 仅余 %d，请考虑在源码侧拆分该文件。"
                      % (item["chars"], threshold, "/".join(item["files"]),
                         UI_SOFT["content"], UI_SOFT["content"] - item["chars"]))
    return rules, rid, layout


def theme_override_css(theme, diag):
    """把 theme token 编译成 [data-chat=root][data-theme=*] 覆盖块。

    事实卡 §7.1 + 硬约束 10：平台令牌定义在 [data-theme=dark]（特异度 (0,1,0)），
    data-theme 与 data-chat=root 在【同一个 div】上 → 写两个属性选择器得 (0,2,0)，
    高于平台且【不需要 !important】。写 :root 完全无效（平台无 :root 定义）。
    """
    if not theme:
        return ""
    if "dark" in theme or "light" in theme:
        sets = [("dark", theme.get("dark")), ("light", theme.get("light"))]
    else:
        sets = [("dark", theme), ("light", theme)]
    out = []
    for mode, tokens in sets:
        if not tokens:
            continue
        decls = []
        for k, v in tokens.items():
            if v is None or v == "":
                continue
            v = str(v)
            # 值里出现 } 或 </style 会截断整个样式块
            if "}" in v or re.search(r"</style", v, re.I):
                diag.err("theme", "token %s 的值含 } 或 </style，会截断样式块——已拒绝。" % k)
                continue
            decls.append("%s:%s;" % (_theme_var(k), v))
        if decls:
            out.append('[data-chat="root"][data-theme="%s"]{%s}' % (mode, "".join(decls)))
    return "\n".join(out)


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


def boot_script(cfg, diag):
    """启动调用。事实卡 §4.1 硬约束 17：任何 DOM 写入必须在事件回调内
    （作者脚本早于 DOM 执行，顶层 getElementById 返回 null）。
    §4.1 冷启动挂 message:mount/done——ready 最后到且无补发。
    这里只做参数投喂 + SBK.boot()，真正的订阅在 core.js 里。"""
    payload = {
        "hostId": cfg["hostId"],
        "schema": cfg.get("schema") or {},
        "modes": cfg["modes"],
        "protocolTag": cfg["protocolTag"],
        "theme": cfg.get("theme") or None,
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

    modes = {"hud": True, "snapshot": False}
    m = cfg.get("modes") or {}
    if isinstance(m, dict):
        for k in ("hud", "snapshot"):
            if k in m:
                modes[k] = bool(m[k])
    else:
        diag.err("config", "modes 必须是对象，如 {\"hud\":true,\"snapshot\":false}。")

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
        "theme": cfg.get("theme") or {},
        "modes": modes,
        "schema": cfg.get("schema") or {},
        "protocolTag": cfg.get("protocolTag") or "状态",
        "hostId": cfg.get("hostId") or "sbk-hud",
        "markers": markers,
        "sceneRules": scenes,
        "idBase": cfg.get("idBase", -1),
        "splitThreshold": cfg.get("splitThreshold", DEFAULT_SPLIT_THRESHOLD),
    }
    th = out["splitThreshold"]
    if not isinstance(th, int) or th < 1000 or th > HARD["content"]:
        diag.err("config", "splitThreshold 必须是 1000..%d 的整数，当前 %r。" % (HARD["content"], th))
        out["splitThreshold"] = DEFAULT_SPLIT_THRESHOLD
    elif th > UI_SOFT["content"]:
        diag.warn("config", "splitThreshold %d > 编辑器显示上限 %d——拆出的规则仍会在编辑器里被截断（§6）。"
                  % (th, UI_SOFT["content"]))
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


def build(cfg, diag, strip=True):
    adir, mk = cfg["assetDir"], cfg["markers"]
    if not Path(adir).is_dir():
        diag.err("assets", "资源目录不存在：%s" % adir)

    rules, assets_report = [], {}
    rid = cfg["idBase"]

    # ---- 1. sbk-css：base.css + theme 覆盖 ----
    css_src, loaded, _ = load_assets(adir, ("base.css",), diag, strip)
    assets_report["sbk-css"] = loaded
    override = theme_override_css(cfg["theme"], diag)
    css_body = "\n".join([x for x in (css_src, override) if x])
    rules.append(_rule(rid, "sbk-css", mk["css"], "<style>\n%s\n</style>" % css_body))
    rid -= 1

    threshold = cfg["splitThreshold"]
    layouts = []

    # ---- 2. sbk-core：core.js + theme.js（超阈值自动拆条）----
    # 也纳入拆条：目前剥注释约 14.6K 尚在阈值内，但 WP-1 再加代码就会爆。
    _, loaded, _ = load_assets(adir, CORE_ASSETS, diag, strip)
    assets_report["sbk-core"] = loaded
    core_rules, rid, core_layout = emit_script_rules(
        rid, "sbk-core", mk["core"], loaded, threshold, diag, strip)
    rules.extend(core_rules)
    layouts.extend(core_layout)

    # ---- 3. sbk-ui：protocol.js + hud.js + ui.js（WP-2/WP-3，缺失跳过并告警）----
    # 顺序必须是 protocol → hud → ui：hud/ui 往 SBK.ui 合并挂载，且都依赖 core 已定义。
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

    # ---- 4. sbk-hud：宿主容器 HTML（模式 A）----
    if cfg["modes"]["hud"]:
        rules.append(_rule(rid, "sbk-hud", mk["hud"], hud_host_html(cfg["hostId"])))
        rid -= 1
        # §5.6 功能栏静态：h_() 只在装载时跑一次，且其正则输入是 statusbar 字段自身。
        # 触发串不在 statusbar 里 → 宿主容器永远不出现 → HUD 整个模式失效。
        if mk["hud"] not in cfg["statusbar"]:
            diag.err("sbk-hud", "模式 A 已启用，但 statusbar 字段里找不到触发串 %r——"
                     "功能栏正则的输入是 statusbar 自身（§5.6），宿主容器永远不会出现。" % mk["hud"])

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
        diag.err("top", "beginning %d 字符 > 4000（§6 运行时真值，创卡页 UI 同样显示 4000）——"
                 "超出被静默截断。" % len(doc["beginning"]))
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
    L.append("（该校验器部分长度上限取创卡页 UI 值，与事实卡 §6 运行时真值不同，属已知冲突）")
    return "\n".join(L)


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
               "注意该校验器的 beginning/name/regex/content 上限取创卡页 UI 值，"
               "与事实卡 §6 运行时真值（4000/200/4096/100000）不同，属已知冲突，本脚本双轨处理。",
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
