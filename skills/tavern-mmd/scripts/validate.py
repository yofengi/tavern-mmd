#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 审核脚本 validate.py
纯文本静态审核：JSON合法性 / BOM / 双重转义 / 平台红线 / v2规范 / 世界书字段。
不渲染、不联网、不依赖第三方库。子代理可直接调用以节约上下文。

用法:
  python validate.py <文件> --type <regex|card|worldbook> --platform <oldmmd|mmd|st>

  --type 省略时按文件内容自动猜测。
  --platform 省略时默认 oldmmd（最严格）。

退出码: 0=无错误(可能有警告)  1=有错误  2=用法/读取错误
输出: 文本报告，[ERROR]/[WARN]/[OK] 前缀，便于人和AI阅读。
"""
import sys
import json
import argparse
import re
import html as html_mod
import shutil
import subprocess
from html.parser import HTMLParser

# Windows 控制台默认 GBK，强制 UTF-8 输出，避免中文报告乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass  # 旧 Python 或已重定向时忽略

# MMD 世界书条目标题（comment）硬上限，按字符数计，中文一字算 1。本地酒馆无此限制。
MAX_COMMENT_LEN = 20

MMD_TOP_LEVEL_KEYS = ("pageDepth", "statusbar", "beginning", "regex_scripts")
MMD_SCRIPT_KEYS = ("id", "scriptName", "findRegex", "replaceString")

_NODE_REGEX_ORACLE = (
    "const fs=require('fs');"
    "const x=JSON.parse(fs.readFileSync(0,'utf8'));"
    "try{new RegExp(x.pattern,x.flags);"
    "process.stdout.write(JSON.stringify({ok:true}));}"
    "catch(e){process.stdout.write(JSON.stringify({ok:false,name:e&&e.name||'',"
    "message:String(e&&e.message||e)}));}"
)
_NODE_REGEX_CACHE = {}

ERRORS = []
WARNS = []
OKS = []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNS.append(msg)


def ok(msg):
    OKS.append(msg)


def read_raw_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def check_bom(rawb):
    if rawb[:3] == b"\xef\xbb\xbf":
        err("文件带 UTF-8 BOM 头，部分平台导入会报 json 异常。请用无 BOM 的 UTF-8 保存。")
        return True
    ok("无 BOM")
    return False


def load_json(rawb):
    """返回 (obj, 已去BOM文本) 或 (None, 文本)。失败时记录错误。"""
    try:
        txt = rawb.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        err("文件不是合法 UTF-8: byte %d: %s。请用无 BOM 的 UTF-8 保存。" % (e.start, e.reason))
        return None, ""
    try:
        obj = json.loads(txt)
        ok("JSON 语法合法")
        return obj, txt
    except json.JSONDecodeError as e:
        # 给出常见原因提示
        hint = ""
        line = txt.splitlines()[e.lineno - 1] if 0 < e.lineno <= len(txt.splitlines()) else ""
        if "control character" in str(e).lower():
            hint = "（字符串内有未转义的真实换行/控制符——大段HTML的换行必须写成 \\n）"
        elif "delimiter" in str(e).lower() or "expecting" in str(e).lower():
            hint = "（可能是字符串内双引号未转义为 \\\"，或缺逗号/括号）"
        err("JSON 语法非法: line %d col %d: %s %s" % (e.lineno, e.colno, e.msg, hint))
        if line:
            err("  出错行: %s" % line[:120])
        return None, txt
    return None, txt


# ============ 平台红线检查（作用于解析后的 HTML/JS 字符串） ============

class _EventAttributeParser(HTMLParser):
    """只收集真实开始标签上的事件属性；script/style 文本不会被当属性扫描。"""
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            low = name.lower()
            if low in ("onerror", "onclick"):
                self.attrs.append((low, value or ""))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def _extract_event_handler_attrs(s):
    """返回真实 HTML 标签上的 [(attr_name, body), ...]，支持单双/未引号属性。"""
    parser = _EventAttributeParser()
    try:
        parser.feed(s)
        parser.close()
    except (ValueError, TypeError):
        return []
    return parser.attrs


def _extract_event_handler_bodies(s):
    return list(_extract_event_handler_attrs(s))


_JS_IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
_INTERNAL_IDENT = r"__[A-Za-z_$][A-Za-z0-9_$]*"
_CLEAN_WINDOW_GUARD_CALL = re.compile(
    r"^window\.(?P<guard>" + _INTERNAL_IDENT + r")\s*&&\s*"
    r"(?:window\.)?(?P<call>" + _INTERNAL_IDENT + r")\(\s*\)\s*;?$"
)
_CLEAN_STOP_CALL = re.compile(r"^event\.stopPropagation\(\s*\)\s*;?$")
_CLEAN_EVAL_ELEMENT_CALL = re.compile(
    r"^eval\(\s*getElementById\(\s*(?P<quote>['\"])(?P<id>[A-Za-z_$][A-Za-z0-9_$:.-]*)"
    r"(?P=quote)\s*\)\.dataset\.s\s*\)\s*;?$"
)


def _mask_js_strings(s):
    out = []
    quote = None
    escaped = False
    for ch in s:
        if quote:
            out.append(" ")
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def classify_mmd_onclick(body):
    """当前 MMD inline onclick allowlist；返回 (allowed, reason)。"""
    source = html_mod.unescape(body or "").strip()
    if not source:
        return False, "空 onclick"
    if "\n" in source or "\r" in source:
        return False, "含裸换行/多行代码"
    if "`" in source:
        return False, "含模板字符串/动态代码"
    if re.search(r"\beval\s*\(\s*['\"`]", source) or re.search(
            r"\beval\s*\([^)]*\beval\s*\(\s*['\"`]", source):
        return False, "含 eval 直接或嵌套代码字符串"
    masked = _mask_js_strings(source)
    if re.search(r"(?<![=!<>])=(?!=|>)", masked):
        return False, "含直接 DOM/属性赋值"
    trimmed = masked[:-1].rstrip() if masked.endswith(";") else masked
    if ";" in trimmed or "," in trimmed or "{" in masked or "}" in masked:
        return False, "含 sequence、多语句或代码块"
    if _CLEAN_STOP_CALL.fullmatch(source):
        return True, ""
    if _CLEAN_EVAL_ELEMENT_CALL.fullmatch(source):
        return True, ""
    guard_call = _CLEAN_WINDOW_GUARD_CALL.fullmatch(source)
    if guard_call and guard_call.group("guard") == guard_call.group("call"):
        return True, ""
    return False, "不属于已实测的 canonical 干净调用"


def _scan_tag_end(s, start):
    quote = None
    i = start + 1
    while i < len(s):
        ch = s[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch == '"' or ch == "'":
            quote = ch
        elif ch == ">":
            return i + 1
        i += 1
    return None


def _attr_tail_has_junk(tail):
    """判断属性闭合引号后到标签结尾前是否出现非属性语法垃圾。
    onerror="alert("x")" 会在第一个内部引号处提前闭合，后续 x")" 不是合法属性序列。"""
    i = 0
    while i < len(tail):
        while i < len(tail) and tail[i].isspace():
            i += 1
        if i >= len(tail) or tail[i] == "/":
            return False
        m = re.match(r"[A-Za-z_:][A-Za-z0-9_.:-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?", tail[i:])
        if not m:
            return True
        i += m.end()
    return False


def check_onerror_inner_quote(s, platform, where):
    """onerror="..." 双引号包裹时，内部 JS 禁裸双引号——会提前闭合属性、破坏 img 结构、
    引擎不绑定 → 面板静默不渲染（不爆代码但完全不显示）。2026-06-17 浏览器+MMD 实机
    三组对照确认的唯一引号红线。修法：内部字符串全用单引号，CFG/CSS 用单引号 JS 字面量
    序列化（非 json.dumps）。仅 MMD 系平台（onerror 是注入载体）。
    注：裸 < > => 在 onerror 引号内经实机证实无害（HTML 属性值不解析标签；雷达法引擎
    满是 i<n/c>0 实战正常），不在此检查——曾误立的"禁裸 <>"已撤销。"""
    if platform not in ("oldmmd", "mmd"):
        return
    bad = 0
    for m in re.finditer(r"\bonerror\s*=\s*\"", s, re.I):
        tag_start = s.rfind("<", 0, m.start())
        tag_end = _scan_tag_end(s, tag_start) if tag_start != -1 else None
        if tag_end is None:
            continue
        value_start = m.end()
        value_end = s.find('"', value_start)
        if value_end == -1 or value_end >= tag_end:
            continue
        if _attr_tail_has_junk(s[value_end + 1:tag_end - 1]):
            bad += 1
    if bad > 0:
        err('%s onerror="" 内部含 %d 个裸双引号——会提前闭合属性、img 结构破坏、'
            '引擎不绑定、面板静默不渲染。内部字符串改单引号，CFG/CSS 用单引号 JS '
            '字面量序列化（勿用 json.dumps）。' % (where, bad))


def check_comment_length(comment, platform, where):
    """世界书条目标题（comment）长度。MMD 上限 20 字，超出在平台侧被截断；st 无限制。"""
    if platform not in ("oldmmd", "mmd"):
        return
    if not isinstance(comment, str):
        return
    if len(comment) > MAX_COMMENT_LEN:
        err("%s 标题共 %d 字，超过 MMD 上限 %d 字——导入后标题被截断。"
            "请精简标题，去掉【】·— 等装饰符（装饰符同样占额度）。" % (where, len(comment), MAX_COMMENT_LEN))


def check_platform_redlines(s, platform, where):
    """s: 待检字符串（如 replaceString 解析后的值）。where: 来源描述。"""
    # onerror="" 内部裸双引号（影渲法 demo 实机踩出的真红线）
    check_onerror_inner_quote(s, platform, where)

    # <script> 标签
    if re.search(r"<script\b", s, re.I):
        if platform == "oldmmd":
            err("%s 含 <script> 标签——旧版MMD会剥离，JS不执行。改用 img onerror 点火器。" % where)
        elif platform == "mmd":
            ok("%s 含 <script>——当前MMD已确认支持，正常执行。" % where)
        # st 不报

    # ES6 语法（仅 MMD 系平台关心）
    if platform in ("oldmmd", "mmd"):
        es6 = []
        if re.search(r"=>", s):
            es6.append("箭头函数(=>)")
        if re.search(r"\blet\b", s):
            es6.append("let")
        if re.search(r"\bconst\b", s):
            es6.append("const")
        if "`" in s:
            es6.append("模板字符串(反引号)")
        if re.search(r"\.\.\.", s) and re.search(r"\[\s*\.\.\.|\(\s*\.\.\.", s):
            es6.append("展开运算符")
        if re.search(r"\?\.", s):
            es6.append("可选链(?.)")
        if es6:
            if platform == "oldmmd":
                err("%s 含 ES6+ 语法: %s——旧版MMD会从该处截断，后续代码丢失。" % (where, "、".join(es6)))
            else:
                ok("%s 含 ES6+ 语法: %s——当前MMD实测全支持（img载体下）。" % (where, "、".join(es6)))
        else:
            ok("%s 全 ES5" % where)

    # 纯DOM API：innerHTML 拼接 / cssText
    if re.search(r"\.innerHTML\s*=", s):
        (err if platform == "oldmmd" else warn)("%s 用 innerHTML 赋值——易被平台破坏，改用 createElement/textContent。" % where)
    if re.search(r"\.cssText\s*=", s):
        (err if platform == "oldmmd" else warn)("%s 用 style.cssText——旧版MMD报 Unexpected identifier，改用预定义CSS类。" % where)

    # alert
    if re.search(r"\balert\s*\(", s):
        warn("%s 含 alert()——平台静默阻止且中断执行，移除。" % where)


def check_double_escape(s, where):
    """检查解析后的 HTML 是否残留多余反斜杠（双重转义典型症状）。

    真信号=`\\"`/`\\'`（属性引号被转义两次）→ err，但**仅对非 JS 载体**成立。
    含 onerror/onclick 的 JS 载体里，`\\'`/`\\"` 是合法的 JS 字符串转义（如单引号
    字符串内的 CSS `content:''` 或字体名 `'Songti SC'` 必写成 `\\'`），不是属性引号
    双重转义——故先判 has_js 放行，再对纯美化 HTML 用 quote_bs 判真双重转义。
    （2026 实测：富交互状态栏的 CSS content/字体引号 >5 处曾被误报，此处修正判断顺序。）"""
    bs = s.count("\\")
    if bs == 0:
        ok("%s 无残留反斜杠（无双重转义）" % where)
        return
    # 含 onerror/onclick = JS 载体：内部字符串/正则字面量的 \" \' \d \s \/ 均为合法
    # JS 转义，不是 HTML 属性引号双重转义。须先于 quote_bs 判断（否则 JS 载体里 >5 个
    # 合法 \' 会被误判为双重转义）。
    has_js = bool(re.search(r"on(error|click)\s*=", s, re.I))
    if has_js:
        ok("%s 含 %d 个反斜杠，但为 JS 载体（onerror/onclick）的字符串/正则字面量，正常" % (where, bs))
        return
    # 非 JS 载体（纯美化 HTML）：反斜杠后紧跟引号 = 属性引号被多转义（真双重转义）
    quote_bs = len(re.findall(r'\\[\"\']', s))
    if quote_bs > 5:
        err("%s 解析后含 %d 处 \\\" 或 \\' ——几乎确定是双重转义（HTML属性引号被转义两次）。"
            "源HTML喂给json.dumps前需先 .replace(chr(92)+chr(34), chr(34)) 还原。" % (where, quote_bs))
        return
    if bs > 0:
        warn("%s 解析后含 %d 个反斜杠——纯美化HTML通常应为0，请确认是否双重转义。" % (where, bs))


def check_interactive_event_newlines(s, where, platform):
    """检查内联事件处理器，并执行 MMD 当前版 onclick 净化规则。"""
    if platform not in ("oldmmd", "mmd"):
        return
    if platform == "oldmmd":
        bodies = [body for _attr, body in _extract_event_handler_attrs(s)]
        bad = [body for body in bodies if "\n" in body or "\r" in body]
        if bad:
            err("%s 有 %d 个内联事件处理器(onclick/onerror)含裸换行——旧版MMD的CSP会破坏多行JS，必须单行。" % (where, len(bad)))
        else:
            ok("%s 内联事件处理器均单行" % where)
        return

    onclicks = [body for attr, body in _extract_event_handler_attrs(s) if attr == "onclick"]
    if not onclicks:
        ok("%s 未发现真实 inline onclick（onerror 当前MMD可多行）" % where)
        return

    clean = 0
    for body in onclicks:
        allowed, reason = classify_mmd_onclick(body)
        if allowed:
            clean += 1
        else:
            err("%s onclick 会被当前MMD净化：%s。属性内仅保留 window.__name(event/this 等简单引用)、"
                "window.__fn&&__fn() 同名纯 guard-call、event.stopPropagation() 或 "
                "eval(getElementById('固定ID').dataset.s)。未列出的调用即使语法简单，也没有当前 MMD 实测认证。" % (where, reason))
    if clean == len(onclicks):
        ok("%s onclick 均为 allowlist 内的干净单一调用（onerror 当前MMD可多行）" % where)


# ============ 类型专项校验 ============

def looks_like(obj):
    """猜测 JSON 类型。"""
    if isinstance(obj, dict):
        if "regex_scripts" in obj:
            return "regex"  # MMD 导入 json
        if "spec" in obj and "data" in obj:
            return "card"
        if "entries" in obj and isinstance(obj.get("entries"), (dict, list)):
            return "worldbook"
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "findRegex" in obj[0]:
        return "regex"  # 本地酒馆正则数组
    return None


HTML_TAGS = set("""a abbr address area article aside audio b base bdi bdo blockquote body br button canvas
caption cite code col colgroup data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption
figure footer form h1 h2 h3 h4 h5 h6 head header hgroup hr html i iframe img input ins kbd label legend li
link main map mark menu meta meter nav noscript object ol optgroup option output p picture pre progress q rp rt
ruby s samp script search section select slot small source span strong style sub summary sup svg table tbody td
template textarea tfoot th thead time title tr track u ul var video wbr""".split())


def _split_findregex_literal(fr):
    """解析 JS `/pattern/flags` 字面量；尊重转义与字符类中的斜杠。"""
    if not isinstance(fr, str) or not fr.startswith("/"):
        return None
    escaped = False
    in_class = False
    end = None
    for i in range(1, len(fr)):
        ch = fr[i]
        if ch in "\r\n" or ord(ch) in (0x2028, 0x2029):
            return None
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "[":
            in_class = True
        elif ch == "]" and in_class:
            in_class = False
        elif ch == "/" and not in_class:
            end = i
            break
    if end is None:
        return None
    flags = fr[end + 1:]
    if not re.fullmatch(r"[dgimsuvy]*", flags):
        return None
    if len(set(flags)) != len(flags) or ("u" in flags and "v" in flags):
        return None
    return fr[1:end], flags


def _node_js_regex_error(pattern, flags):
    """返回 (oracle_available, syntax_error)。Node 仅经 stdin 接收 JSON，不拼接用户正则。"""
    node = shutil.which("node")
    cache_key = (node, pattern, flags)
    if cache_key in _NODE_REGEX_CACHE:
        return _NODE_REGEX_CACHE[cache_key]
    if not node:
        result = (False, None)
        _NODE_REGEX_CACHE[cache_key] = result
        return result
    try:
        proc = subprocess.run(
            [node, "-e", _NODE_REGEX_ORACLE],
            input=json.dumps({"pattern": pattern, "flags": flags}, ensure_ascii=False),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        result = (False, None)
    elif data["ok"]:
        result = (True, None)
    elif data.get("name") == "SyntaxError":
        result = (True, str(data.get("message") or "JS RegExp SyntaxError"))
    else:
        result = (False, None)
    _NODE_REGEX_CACHE[cache_key] = result
    return result


def _js_regex_oracle_available():
    return _node_js_regex_error("", "")[0]


def _exact_key_error(actual, expected, label):
    expected_order = tuple(expected)
    actual = set(actual)
    expected = set(expected_order)
    if actual == expected:
        return None
    parts = []
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        parts.append("缺少 %s" % "、".join(missing))
    if extra:
        parts.append("多出 %s" % "、".join(extra))
    return "%s keys 必须恰好为 %s（%s）" % (label, "/".join(expected_order), "；".join(parts))


def _mmd_regex_top_level_errors(obj):
    errors = []
    if not isinstance(obj, dict):
        return ["MMD/oldmmd 正则导入必须为 pageDepth/statusbar/beginning/regex_scripts 四字段对象，顶层数组仅适用于 ST"]
    key_error = _exact_key_error(obj.keys(), MMD_TOP_LEVEL_KEYS, "MMD 顶层")
    if key_error:
        errors.append(key_error)
    if "pageDepth" in obj and (isinstance(obj["pageDepth"], bool)
                                or not isinstance(obj["pageDepth"], (int, float))):
        errors.append("MMD 顶层 pageDepth 必须为 number，当前为 %s" % type(obj["pageDepth"]).__name__)
    for field in ("statusbar", "beginning"):
        if field in obj and not isinstance(obj[field], str):
            errors.append("MMD 顶层 %s 必须为 string，当前为 %s" % (field, type(obj[field]).__name__))
    scripts = obj.get("regex_scripts")
    if "regex_scripts" in obj and not isinstance(scripts, list):
        errors.append("MMD 顶层 regex_scripts 必须为 array，当前为 %s" % type(scripts).__name__)
    return errors


def _mmd_regex_schema_errors(obj):
    """返回 MMD 四字段导入结构错误；ST 数组不调用此检查。"""
    errors = _mmd_regex_top_level_errors(obj)
    if not isinstance(obj, dict):
        return errors
    scripts = obj.get("regex_scripts")
    if not isinstance(scripts, list):
        return errors
    for i, sc in enumerate(scripts):
        label = "MMD regex_scripts[%d]" % i
        if not isinstance(sc, dict):
            errors.append("%s 必须为 object，当前为 %s" % (label, type(sc).__name__))
            continue
        key_error = _exact_key_error(sc.keys(), MMD_SCRIPT_KEYS, label)
        if key_error:
            errors.append(key_error)
        if "id" in sc and (type(sc["id"]) is not int or sc["id"] != -1):
            errors.append("%s id 必须为整数 -1，当前为 %r" % (label, sc["id"]))
        for field in ("scriptName", "findRegex", "replaceString"):
            if field in sc and not isinstance(sc[field], str):
                errors.append("%s %s 必须为 string，当前为 %s" %
                              (label, field, type(sc[field]).__name__))
    return errors


def _simple_reversed_class_range(pattern):
    """只判断端点均为未转义字符的明确逆序范围；其余交给 Node。"""
    i = 0
    while i < len(pattern):
        if pattern[i] == "\\":
            i += 2
            continue
        if pattern[i] != "[":
            i += 1
            continue
        tokens = []
        i += 1
        escaped = False
        while i < len(pattern):
            ch = pattern[i]
            if escaped:
                tokens.append((ch, True))
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "]":
                break
            else:
                tokens.append((ch, False))
            i += 1
        for j in range(1, len(tokens) - 1):
            prev_ch, prev_escaped = tokens[j - 1]
            ch, ch_escaped = tokens[j]
            next_ch, next_escaped = tokens[j + 1]
            if (ch == "-" and not ch_escaped and not prev_escaped and not next_escaped
                    and prev_ch != "-" and next_ch != "-" and ord(prev_ch) > ord(next_ch)):
                return "%s-%s" % (prev_ch, next_ch)
        i += 1
    return None


def _js_regex_structure_error(fr):
    """先做保守结构 fallback；Node 可用时再以真实 JS RegExp 语法为准。"""
    parsed = _split_findregex_literal(fr)
    if parsed is None:
        return "必须为 /pattern/flags 形式，且分隔符、字符类、换行和 flags 合法"
    pattern, flags = parsed
    escaped = False
    in_class = False
    depth = 0
    for i, ch in enumerate(pattern):
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif in_class:
            if ch == "]":
                in_class = False
        elif ch == "[":
            in_class = True
        elif ch == "(":
            if pattern.startswith("?P<", i + 1) or pattern.startswith("?P=", i + 1):
                return "含 Python 专有命名组语法 (?P<...>)/(?P=...)，不是 JS RegExp 语法"
            if pattern.startswith("?(", i + 1):
                return "含 Python 专有条件组语法 (?(...))，不是 JS RegExp 语法"
            if pattern.startswith("?<", i + 1) and i + 3 < len(pattern) and pattern[i + 3] not in ("=", "!"):
                end = pattern.find(">", i + 3)
                if end == -1:
                    return "命名捕获组名称未闭合"
                name = pattern[i + 3:end]
                if (not name or name[0].isdigit() or
                        (name.isascii() and "\\" not in name and not re.fullmatch(_JS_IDENT, name))):
                    return "命名捕获组名称 %r 不是合法 JS 标识符" % name
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return "pattern 含无对应开始括号的 )"
        elif ch == "{":
            quantifier = re.match(r"\{(\d+),(\d+)\}", pattern[i:])
            if quantifier and int(quantifier.group(1)) > int(quantifier.group(2)):
                return "量词下界 %s 大于上界 %s" % (quantifier.group(1), quantifier.group(2))
    if depth:
        return "pattern 含未闭合的 ("
    reversed_range = _simple_reversed_class_range(pattern)
    if reversed_range:
        return "字符类范围 [%s] 起点大于终点" % reversed_range
    oracle_available, oracle_error = _node_js_regex_error(pattern, flags)
    if oracle_available and oracle_error:
        return "Node JS RegExp SyntaxError: %s" % oracle_error
    return None


def _translate_js_named_groups(pattern):
    """只翻译真实 JS named group/backref，返回 (translated, reason)。"""
    out = []
    i = 0
    in_class = False
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            if not in_class and pattern.startswith("\\k<", i):
                end = pattern.find(">", i + 3)
                if end == -1:
                    return None, "命名反向引用未闭合"
                name = pattern[i + 3:end]
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    return None, "命名反向引用名称超出预览器支持范围"
                out.append("(?P=%s)" % name)
                i = end + 1
                continue
            out.append(pattern[i:i + 2])
            i += 2
            continue
        if in_class:
            out.append(ch)
            if ch == "]":
                in_class = False
            i += 1
            continue
        if ch == "[":
            in_class = True
            out.append(ch)
            i += 1
            continue
        if pattern.startswith("(?<", i) and i + 3 < len(pattern) and pattern[i + 3] not in ("=", "!"):
            end = pattern.find(">", i + 3)
            if end == -1:
                return None, "命名组名称未闭合"
            name = pattern[i + 3:end]
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                return None, "命名组名称超出预览器支持范围"
            out.append("(?P<%s>" % name)
            i = end + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), None


def _parse_findregex(fr):
    """兼容旧调用：返回结构解析结果；不再以 Python re.compile 判断 JS 合法性。"""
    return None if _js_regex_structure_error(fr) else _split_findregex_literal(fr)


def _compile_js_regex_for_preview(fr):
    """编译预览器支持的 JS RegExp 子集，返回 (regex, flags, reason)。

    reason 仅表示 Python 预览器无法可靠模拟，不能据此判断 MMD/JS 规则非法。"""
    parsed = _split_findregex_literal(fr)
    if parsed is None or _js_regex_structure_error(fr):
        return None, "", "findRegex 结构非法"
    pattern, js_flags = parsed
    if "v" in js_flags:
        return None, js_flags, "暂不支持 v flag 的 UnicodeSets 语义"
    if re.search(r"\\[pP]\{", pattern):
        return None, js_flags, "暂不支持 Unicode property escape（\\p/\\P）"
    if re.search(r"\\u\{[0-9A-Fa-f]+\}", pattern):
        return None, js_flags, "暂不支持 JS code point escape（\\u{...}）"
    if re.search(r"\\c[A-Za-z]", pattern):
        return None, js_flags, "暂不支持 JS control escape（\\cX）"

    translated, translate_reason = _translate_js_named_groups(pattern)
    if translate_reason:
        return None, js_flags, translate_reason
    py_flags = 0
    if "i" in js_flags:
        py_flags |= re.I
    if "m" in js_flags:
        py_flags |= re.M
    if "s" in js_flags:
        py_flags |= re.S
    try:
        return re.compile(translated, py_flags), js_flags, None
    except re.error as exc:
        return None, js_flags, "Python 预览后端无法模拟：%s" % exc


def _match_group(m, key):
    try:
        return m.group(key) or ""
    except (IndexError, KeyError, re.error):
        return ""


def _expand_js_replacement(template, m, source):
    """展开 JS String.replace replacement tokens；反斜杠按字面保留。"""
    out = []
    i = 0
    groups = m.re.groups
    named = bool(m.re.groupindex)
    while i < len(template):
        if template[i] != "$" or i + 1 >= len(template):
            out.append(template[i])
            i += 1
            continue
        nxt = template[i + 1]
        if nxt == "$":
            out.append("$")
            i += 2
        elif nxt == "&":
            out.append(m.group(0))
            i += 2
        elif nxt == "`":
            out.append(source[:m.start()])
            i += 2
        elif nxt == "'":
            out.append(source[m.end():])
            i += 2
        elif nxt == "<":
            end = template.find(">", i + 2)
            if end == -1 or not named:
                out.append("$")
                i += 1
            else:
                out.append(_match_group(m, template[i + 2:end]))
                i = end + 1
        elif nxt.isdigit():
            first = int(nxt)
            if first == 0:
                if i + 2 < len(template) and template[i + 2].isdigit():
                    second = int(template[i + 2])
                    if second and second <= groups:
                        out.append(_match_group(m, second))
                        i += 3
                    else:
                        out.append(template[i:i + 3])
                        i += 3
                else:
                    out.append("$0")
                    i += 2
                continue
            if i + 2 < len(template) and template[i + 2].isdigit():
                two_digit = first * 10 + int(template[i + 2])
                if two_digit <= groups:
                    out.append(_match_group(m, two_digit))
                    i += 3
                    continue
            if first <= groups:
                out.append(_match_group(m, first))
                i += 2
            else:
                out.append("$" + nxt)
                i += 2
        else:
            out.append("$")
            i += 1
    return "".join(out)


def _replace_js_regex(source, regex, js_flags, replacement):
    """模拟 String.replace 的 g/y 匹配范围和 replacement token。"""
    matches = []
    global_mode = "g" in js_flags
    if "y" in js_flags:
        pos = 0
        while pos <= len(source):
            m = regex.match(source, pos)
            if m is None:
                break
            matches.append(m)
            if not global_mode:
                break
            next_pos = m.end()
            pos = next_pos if next_pos > pos else pos + 1
    elif global_mode:
        matches = list(regex.finditer(source))
    else:
        m = regex.search(source)
        if m is not None:
            matches = [m]
    if not matches:
        return source
    out = []
    last = 0
    for m in matches:
        out.append(source[last:m.start()])
        out.append(_expand_js_replacement(replacement, m, source))
        last = m.end()
    out.append(source[last:])
    return "".join(out)


def _apply_supported_regex_pipeline(obj):
    """执行预览器支持的规则；非法或 JS-only 未支持规则保持跳过。"""
    if not isinstance(obj, dict):
        return ""
    text = "".join(obj.get(k, "") if isinstance(obj.get(k, ""), str) else ""
                   for k in ("statusbar", "beginning"))
    scripts = obj.get("regex_scripts", [])
    if not isinstance(scripts, list):
        return text
    for sc in scripts:
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        rs = sc.get("replaceString", "")
        if not isinstance(fr, str) or not isinstance(rs, str) or not fr:
            continue
        regex, js_flags, reason = _compile_js_regex_for_preview(fr)
        if regex is None or reason:
            continue
        text = _replace_js_regex(text, regex, js_flags, rs)
    return text


def _custom_marker_occurrences(text):
    """返回最终文本中的自定义开始/结束标记 occurrence，不按名称去重。"""
    out = []
    for m in re.finditer(r"</?([A-Za-z一-鿿][A-Za-z0-9_.\-一-鿿]*)\s*>", text):
        if m.group(1).lower() not in HTML_TAGS:
            out.append((m.group(0), m.start()))
    return out


def _preview_unsupported_rules(scripts):
    out = []
    for i, sc in enumerate(scripts if isinstance(scripts, list) else []):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        if not isinstance(fr, str) or not fr or _js_regex_structure_error(fr):
            continue
        regex, _flags, reason = _compile_js_regex_for_preview(fr)
        if regex is None or reason:
            out.append(str(sc.get("scriptName", sc.get("name", "#%d" % i))))
    return out


def check_dangling_markers(obj, scripts=None):
    """按受支持规则的最终管线输出逐 occurrence 检查自定义开始/结束标记。"""
    if not isinstance(obj, dict):
        return
    scripts = scripts if isinstance(scripts, list) else obj.get("regex_scripts", [])
    unsupported = _preview_unsupported_rules(scripts)
    if unsupported:
        warn("悬空标记审计已跳过：预览器无法模拟 JS 正则规则 %s。" % "、".join(unsupported))
        return
    rendered = _apply_supported_regex_pipeline(obj)
    for marker, pos in _custom_marker_occurrences(rendered):
        err("悬空标记 %s：最终管线输出位置 %d 仍有自定义标记，渲染时会裸露。" % (marker, pos))


def check_shadowcast(s, platform, where):
    """影渲法（ShadowCast）写法识别。仅 MMD 系平台。

    - 含 attachShadow = 影渲法引擎。2.0 起要求 shadow→light DOM 降级链：
      attachShadow 不可用环境（旧 WebView/平台禁用）应回退 light DOM，否则面板静默消失。
    - 判据：attachShadow 调用应被 try/catch 或三元守卫包裹（shadowOf 模式
      `b.shadowRoot||(b.attachShadow?b.attachShadow(...):null)`），且存在 light 兜底
      （document 注 style + 非 shadow 挂载）。裸 attachShadow 无守卫 → 警告（1.0 隐患）。
    """
    if platform not in ("oldmmd", "mmd"):
        return
    if "attachShadow" not in s:
        return
    # 守卫信号：三元探测（attachShadow? ... :）或 try/catch 包裹 + shadowRoot 复用
    has_ternary_guard = bool(re.search(r"attachShadow\s*\?", s))
    has_reuse = "shadowRoot" in s            # 复用已有 shadow（幂等）
    # 兜底信号：adoptedStyleSheets 或 document 注 style 的 light 路径
    has_adopted = "adoptedStyleSheets" in s
    guarded = has_ternary_guard and has_reuse
    if guarded:
        extra = "，adoptedStyleSheets 缓存样式" if has_adopted else ""
        ok("%s 影渲法 2.0 写法：attachShadow 带降级守卫（shadow→light DOM 兜底）%s。" % (where, extra))
    else:
        warn("%s 含 attachShadow 但未见降级守卫（shadowOf 三元探测 + shadowRoot 复用）——"
             "影渲法 1.0 隐患：attachShadow 不可用环境会抛错致面板静默消失。"
             "升级为 `b.shadowRoot||(b.attachShadow?b.attachShadow({mode:'open'}):null)` + light DOM 兜底。" % where)


def validate_regex(obj, platform):
    """MMD 导入 JSON 必须是严格四字段 dict；ST 保持正则数组兼容。"""
    scripts = []
    mmd_platform = platform in ("oldmmd", "mmd")
    if mmd_platform:
        schema_errors = _mmd_regex_schema_errors(obj)
        for message in schema_errors:
            err(message)
        if not isinstance(obj, dict):
            return
        scripts = obj.get("regex_scripts", [])
        if not isinstance(scripts, list):
            scripts = []
        if _js_regex_oracle_available():
            ok("findRegex 已通过 Node.js new RegExp 语法 oracle 门禁")
        else:
            warn("未找到可用 Node.js；findRegex 仅执行结构 fallback，未经过真实 JS RegExp oracle。")
        ok("识别为 MMD 导入json 格式（%d 条正则）" % len(scripts))
        sb = obj.get("statusbar", "")
        if isinstance(sb, str) and sb:
            ok("statusbar 触发标记: %s" % sb)
    elif isinstance(obj, dict) and "regex_scripts" in obj:
        scripts = obj.get("regex_scripts", [])
        if not isinstance(scripts, list):
            err("正则对象 regex_scripts 应为数组，当前为 %s。" % type(scripts).__name__)
            scripts = []
        for k in MMD_TOP_LEVEL_KEYS:
            if k not in obj:
                warn("正则对象缺字段 %s" % k)
        ok("识别为 MMD 导入json 格式（%d 条正则）" % len(scripts))
    elif isinstance(obj, list):
        scripts = obj
        ok("识别为 本地酒馆正则数组（%d 条）" % len(scripts))
    else:
        err("无法识别的正则结构")
        return

    if mmd_platform and isinstance(obj, dict):
        check_dangling_markers(obj, scripts)

    if mmd_platform:
        if len(scripts) > 130:
            err("正则条数 %d > 130，超出MMD上限。" % len(scripts))
        else:
            ok("正则条数 %d ≤ 130" % len(scripts))

    for i, sc in enumerate(scripts):
        if not isinstance(sc, dict):
            err("第%d条正则不是对象" % i)
            continue
        name = sc.get("scriptName", sc.get("name", "#%d" % i))
        raw_fr = sc.get("findRegex", "")
        fr = raw_fr
        rs = sc.get("replaceString", "")
        tag = "正则[%s]" % name

        # 容错：findRegex/replaceString 必须是字符串，否则告警并按空串处理（防 len() 崩溃）
        if not isinstance(fr, str):
            warn("%s findRegex 非字符串（%s），已按空串处理" % (tag, type(fr).__name__))
            fr = ""
        if not isinstance(rs, str):
            warn("%s replaceString 非字符串（%s），已按空串处理" % (tag, type(rs).__name__))
            rs = ""

        if mmd_platform:
            if isinstance(obj, dict) and raw_fr not in ("", None) and not isinstance(raw_fr, str):
                err("%s findRegex 非法：MMD 四字段导入 JSON 的非空 findRegex 必须为 /pattern/flags 字符串。" % tag)
            elif isinstance(obj, dict) and fr:
                regex_error = _js_regex_structure_error(fr)
                if regex_error:
                    err("%s findRegex 非法：%s。" % (tag, regex_error))
            if len(fr) > 1000:
                err("%s findRegex %d 字符 > 1000" % (tag, len(fr)))
            else:
                ok("%s findRegex %d 字符 ≤ 1000" % (tag, len(fr)))
            if len(rs) > 20000:
                err("%s replaceString %d 字符 > 20000" % (tag, len(rs)))
            elif len(rs) >= 18000:
                warn("%s replaceString %d 字符，距 MMD 20000 字符上限余量不足。" % (tag, len(rs)))
            else:
                ok("%s replaceString %d 字符 < 18000（余量充足）" % (tag, len(rs)))

        # 对 replaceString 内容做红线 + 转义 + 单行检查
        if rs:
            check_platform_redlines(rs, platform, tag)
            check_double_escape(rs, tag)
            check_interactive_event_newlines(rs, tag, platform)
            check_shadowcast(rs, platform, tag)
            # 容器事件冒泡（仅实际内联 onclick 属性需要；动态 el.onclick= 不属于属性）
            has_inline_onclick = any(attr == "onclick" for attr, _body
                                     in _extract_event_handler_attrs(rs))
            if platform in ("oldmmd", "mmd") and has_inline_onclick:
                if "stopPropagation" not in rs:
                    warn("%s 有 onclick 但未见 stopPropagation——交互模块最外层应加 onclick=\"event.stopPropagation()\" 防事件冒泡。" % tag)


def validate_card(obj, platform):
    spec = obj.get("spec", "")
    sv = obj.get("spec_version", "")
    ok("角色卡 spec=%s spec_version=%s" % (spec, sv))
    data = obj.get("data", {})
    if not isinstance(data, dict):
        data = {}

    if platform in ("oldmmd", "mmd"):
        if spec != "chara_card_v2":
            err("MMD 仅识别 chara_card_v2，当前 spec=%s。必须输出 v2（spec=\"chara_card_v2\", spec_version=\"2.0\", 删除 data.group_only_greetings）。" % spec)
        else:
            ok("v2 规范 spec 正确")
        if "group_only_greetings" in data:
            err("MMD v2 卡不应含 data.group_only_greetings（v3 专有字段），请删除。")
        else:
            ok("无 v3 专有字段 group_only_greetings")
    else:
        if spec not in ("chara_card_v2", "chara_card_v3"):
            warn("spec=%s 非标准 v2/v3" % spec)

    # 顶层与 data 同步
    for k in ("name", "first_mes", "description", "personality", "scenario", "mes_example"):
        if k in obj and k in data and obj[k] != data[k]:
            warn("顶层 %s 与 data.%s 不一致（酒馆可能行为不一）" % (k, k))

    # 卡内世界书条目里如带 HTML（美化/状态栏），也查红线
    cb = data.get("character_book", {})
    for e in cb.get("entries", []) if isinstance(cb, dict) else []:
        if not isinstance(e, dict):
            continue
        check_comment_length(e.get("comment", ""), platform, "卡内条目[%s]" % e.get("comment", "?"))
        c = e.get("content", "")
        if isinstance(c, str) and re.search(r"<(?:script|style)\b|on(?:error|click)\s*=", c, re.I):
            check_platform_redlines(c, platform, "卡内条目[%s]" % e.get("comment", "?"))
            check_interactive_event_newlines(c, "卡内条目[%s]" % e.get("comment", "?"), platform)


def validate_worldbook(obj, platform):
    entries = obj.get("entries", {})
    if isinstance(entries, dict):
        items = list(entries.items())
    elif isinstance(entries, list):
        items = list(enumerate(entries))  # 数组形式：下标当 uid
        ok("entries 为数组形式（部分酒馆导出），已按下标遍历")
    else:
        err("独立世界书 entries 应为对象或数组，当前为 %s" % type(entries).__name__)
        return
    ok("独立世界书：%d 个条目" % len(items))
    for uid, e in items:
        if not isinstance(e, dict):
            err("条目 %s 不是对象" % uid)
            continue
        tag = "条目[%s]" % e.get("comment", uid)
        # 标题长度（MMD 20 字上限）
        check_comment_length(e.get("comment", ""), platform, tag)
        # 绿灯必须有 key
        if e.get("constant") is False and not e.get("key"):
            warn("%s 是绿灯(constant=false)但 key 为空——永不触发。" % tag)
        # 蓝灯 selective 约定
        if e.get("constant") is True and e.get("selective") is True:
            warn("%s 蓝灯(constant=true)却 selective=true，通常蓝灯 selective=false。" % tag)
        c = e.get("content", "")
        if isinstance(c, str) and re.search(r"<(?:script|style)\b|on(?:error|click)\s*=", c, re.I):
            check_platform_redlines(c, platform, tag)
            check_interactive_event_newlines(c, tag, platform)


# ============ 主流程 ============

def main():
    p = argparse.ArgumentParser(description="tavern-mmd 静态审核")
    p.add_argument("file", help="待审核的 json 文件")
    p.add_argument("--type", choices=["regex", "card", "worldbook"], help="不填则自动猜测")
    p.add_argument("--platform", choices=["oldmmd", "mmd", "st"], default="oldmmd",
                   help="目标平台，默认 oldmmd（最严格）")
    args = p.parse_args()

    try:
        rawb = read_raw_bytes(args.file)
    except OSError as e:
        print("[ERROR] 无法读取文件: %s" % e)
        sys.exit(2)

    print("=== tavern-mmd 审核报告 ===")
    print("文件: %s  平台: %s" % (args.file, args.platform))
    print()

    check_bom(rawb)
    obj, txt = load_json(rawb)

    if obj is not None:
        t = args.type or looks_like(obj)
        if t is None:
            warn("无法自动判断类型，请用 --type 指定。已做通用JSON检查。")
        elif t == "regex":
            validate_regex(obj, args.platform)
        elif t == "card":
            validate_card(obj, args.platform)
        elif t == "worldbook":
            validate_worldbook(obj, args.platform)

    # 输出
    for m in OKS:
        print("[OK]   " + m)
    for m in WARNS:
        print("[WARN] " + m)
    for m in ERRORS:
        print("[ERROR] " + m)
    print()
    print("结果: %d 错误, %d 警告, %d 通过项" % (len(ERRORS), len(WARNS), len(OKS)))
    sys.exit(1 if ERRORS else 0)


if __name__ == "__main__":
    main()
