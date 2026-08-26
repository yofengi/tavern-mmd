#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 审核脚本 validate.py
纯文本静态审核：JSON合法性 / BOM / 双重转义 / 平台红线 / v2规范 / 世界书字段。
不渲染、不联网、不依赖第三方库。子代理可直接调用以节约上下文。

用法:
  python validate.py <文件> --type <regex|card|worldbook> --platform <mmd|mmdsandbox|st>

  --type 省略时按文件内容自动猜测。
  --platform 省略时默认 mmd（当前MMD）。
  mmdsandbox = MMD沙盒模式（新聊天页，由角色卡 chatVersion:1 开启），
  规则集与 mmd 有系统性差异：6 键导入 JSON、findRegex 允许纯字面量、SDK 名核对。

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

# MMD 系平台集合。沙盒模式是同一平台的新聊天页（chatVersion:1），不是新后端，
# 故平台侧限制（世界书标题等）与 mmd 同源，但执行模型/校验规则差异极大。
MMD_FAMILY = ("mmd", "mmdsandbox")

# ---- 沙盒模式（MMD 新聊天页）常量。全部对齐官方 scripts/validate.mjs ----
# 顶层键白名单：恰好 6 键（mmd-sandbox.md §8.1）
SANDBOX_TOP_LEVEL_KEYS = (
    "chatVersion", "pageDepth", "statusbar", "beginning", "personality", "regex_scripts",
)
# 出现即 ERROR 的顶层键：世界书/回归夹具形状塞进导入 JSON（mmd-sandbox.md §8.1）
SANDBOX_FORBIDDEN_TOP_LEVEL_KEYS = (
    "role", "presentation", "worldbook", "world_book", "lorebook", "lore_book",
    "entries", "characterBook", "character_book",
)
# 长度上限（mmd-sandbox.md §8 + 基座事实卡 §6）。
#
# 【双阈值设计，勿「修正」】沙盒应用源码里的草稿校验常量是逐字真值（事实卡 §6）：
#   var Us={beginning:4e3,statusbar:200,imageUrl:2048,name:200,regex:4096,
#           content:1e5,regexList:130};
#   function Ws(e,t){...e.length>t?e.slice(0,t)...}   // 静默截断，不报错
# 但该常量位于**创卡预览草稿校验路径**，聊天页吃服务端数据是否同限**未能确证**
# （事实卡 §6 末尾的未确证标注）。而创卡页编辑器 UI 显示的计数器又更严
# （name 20 / regex 1000 / content 20000）。
# 于是分级：
#   *_HARD = 源码真值 → 超出即 ERROR（宽，安全：确定会被平台静默截断）
#   *_SOFT = 编辑器 UI 值 → 超出即 WARN（严，实用：提醒作者一进编辑器就被截断）
# 唯一例外是 beginning：官方 validate.mjs 写 10240，**比真值 4000 松**，
# 会放行超长开场白后被平台静默截断 → 直接改成 4000，单阈值 ERROR。
SANDBOX_MAX_STATUSBAR = 200
SANDBOX_MAX_BEGINNING = 4000
SANDBOX_MAX_PERSONALITY = 10000
SANDBOX_MAX_SCRIPT_NAME = 20
SANDBOX_MAX_SCRIPT_NAME_HARD = 200
SANDBOX_MAX_FIND_REGEX = 1000
SANDBOX_MAX_FIND_REGEX_HARD = 4096
SANDBOX_MAX_REPLACE_STRING = 20000
SANDBOX_MAX_REPLACE_STRING_HARD = 100000
SANDBOX_MAX_RULES = 130

# SDK 能力名（30 个）与事件名（12 个）。**镜像官方 contract.json 的 capabilities /
# events 两张表**（mmd-sandbox.md §4.1 / §4.9）。名字拼错平台不报错、只是永不生效，
# 所以官方校验对未知名判 ERROR，本脚本同步。SDK 升版时只改这两个常量即可。
SANDBOX_SDK_CAPABILITIES = frozenset((
    "input.get", "input.set", "input.add", "input.insert", "input.clear",
    "input.focus", "input.blur", "input.getCursor", "input.setCursor",
    "composer.show", "composer.hide", "composer.visible",
    "message.send", "message.edit",
    "cache.get", "cache.set", "cache.remove",
    "save.get", "save.set", "save.remove", "save.keys",
    "stage.open", "stage.close", "stage.el", "stage.visible",
    "role.get", "user.get", "on", "debug.log", "version",
))
SANDBOX_SDK_EVENTS = frozenset((
    "ready", "message:new", "message:done", "message:stream", "message:mount",
    "message:unmount", "input:change", "conversation:switch", "theme:change",
    "back", "stage:close", "dispose",
))
# sdk.role.get() / sdk.user.get() 的返回字段（mmd-sandbox.md §4.7）
SANDBOX_ROLE_FIELDS = frozenset(("name", "avatarUrl"))
SANDBOX_USER_FIELDS = frozenset(("nickname", "avatarUrl"))
# contract.json 里只有 on，没有 once/off；ready 会补发给晚订阅者，不需要 once。
SANDBOX_SDK_MISSING_CAPABILITIES = ("once", "off")

# 命名空间首段集合，供「sdk.input」这类只写首段的引用放行。
SANDBOX_SDK_NAMESPACES = frozenset(
    name.split(".", 1)[0] for name in SANDBOX_SDK_CAPABILITIES if "." in name
)

# 平台自己的 data-* 钩子；作者自写的 data-* 会被净化删掉（mmd-sandbox.md §5）。
SANDBOX_PLATFORM_DATA_ATTRS = frozenset((
    "data-chat", "data-slot", "data-theme", "data-composer", "data-from",
    "data-state", "data-msg-id",
))
# 会被净化删掉的标签（mmd-sandbox.md §5.2）
SANDBOX_FORBIDDEN_TAGS = ("iframe", "link", "meta", "form", "object", "embed")
# 创卡页文案禁的匹配式保留字；线上真卡有用 `【css】` 当匹配式的，故仅 WARN。
SANDBOX_RESERVED_IN_PATTERN = ("html", "head", "body", "css")

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
    满是 i<n/c>0 实战正常），不在此检查——曾误立的"禁裸 <>"已撤销。
    沙盒模式不适用：onerror 点火器被官方明令禁止，<script> 是一等公民。"""
    if platform != "mmd":
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


# ============ 沙盒模式（MMD 新聊天页）专项检查 ============

_SANDBOX_SDK_REF = re.compile(
    r"\bsdk\.(" + _JS_IDENT + r")(?:\.(" + _JS_IDENT + r"))?")
_SANDBOX_SDK_ON = re.compile(
    r"\bsdk\.on\s*\(\s*(?P<quote>['\"])(?P<event>[^'\"]*)(?P=quote)")
_SANDBOX_ROLE_FIELD = re.compile(r"\bsdk\.role\.get\s*\(\s*\)\s*\.\s*(" + _JS_IDENT + r")")
_SANDBOX_USER_FIELD = re.compile(r"\bsdk\.user\.get\s*\(\s*\)\s*\.\s*(" + _JS_IDENT + r")")


def check_sandbox_sdk_names(s, where):
    """SDK 能力名/事件名核对。名字拼错平台不报错、只是永不生效，故判 ERROR。

    名单见 SANDBOX_SDK_CAPABILITIES / SANDBOX_SDK_EVENTS（镜像官方 contract.json）。"""
    seen = set()
    for m in _SANDBOX_SDK_REF.finditer(s):
        first, second = m.group(1), m.group(2)
        if first in SANDBOX_SDK_MISSING_CAPABILITIES:
            if first in seen:
                continue
            seen.add(first)
            err("%s 用了 sdk.%s——contract.json 里只有 sdk.on，没有 %s。"
                "不需要 once：ready 这类只发一次的事件会**补发给后来的订阅者**，晚订阅不会漏。"
                % (where, first, first))
            continue
        dotted = "%s.%s" % (first, second) if second else first
        if dotted in SANDBOX_SDK_CAPABILITIES:
            continue
        # 只写首段（如 `sdk.input` 整体传递）时放行
        if not second and first in SANDBOX_SDK_NAMESPACES:
            continue
        if dotted in seen:
            continue
        seen.add(dotted)
        err("%s 用了 sdk.%s——contract.json 里没有这个能力，平台不报错但**永不生效**。"
            "请对照 30 个合法能力名逐字照抄。" % (where, dotted))
    for m in _SANDBOX_SDK_ON.finditer(s):
        event = m.group("event")
        if event in SANDBOX_SDK_EVENTS or event in seen:
            continue
        seen.add(event)
        err("%s sdk.on('%s')——不在 12 个合法事件名内，打错不报错、只是**永不触发**。"
            "合法事件：%s。" % (where, event, "、".join(sorted(SANDBOX_SDK_EVENTS))))
    for regex, allowed, call in ((_SANDBOX_ROLE_FIELD, SANDBOX_ROLE_FIELDS, "role"),
                                (_SANDBOX_USER_FIELD, SANDBOX_USER_FIELDS, "user")):
        for m in regex.finditer(s):
            field = m.group(1)
            key = "%s.get().%s" % (call, field)
            if field in allowed or key in seen:
                continue
            seen.add(key)
            err("%s sdk.%s.get().%s 不存在——返回对象只有 %s。"
                % (where, call, field, "、".join(sorted(allowed))))


class _TagAttributeParser(HTMLParser):
    """收集真实开始标签上的全部属性，带标签名。script/style 文本不会被当属性扫描。"""
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag.lower(), [(n.lower(), v or "") for n, v in attrs]))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def _extract_tags_with_attrs(s):
    parser = _TagAttributeParser()
    try:
        parser.feed(s)
        parser.close()
    except (ValueError, TypeError):
        return []
    return parser.tags


# 点火器判据：onerror 体在做代码注入/组件引导，而不是普通图片兜底。
# 保守起见只认这几个明确的注入信号——误报 ERROR 比漏报 WARN 更糟。
_SANDBOX_IGNITER_BODY = re.compile(
    r"\beval\s*\(|new\s+Function\s*\(|\bFunction\s*\(\s*['\"]|"
    r"\.innerHTML\s*=|\binsertAdjacentHTML\s*\(|document\.write\s*\(|"
    r"\bcreateElement\s*\(\s*['\"]script|\bappendChild\s*\(|\bimport\s*\(",
    re.I)
# teapot 系写法（官方明令禁止的旧写法）
_SANDBOX_TEAPOT = re.compile(
    r"\bwindow\.teapot[A-Za-z0-9_$]*|\bteapot[A-Za-z0-9_$]*\s*=", re.I)


def check_sandbox_redlines(s, where):
    """沙盒模式红线（ERROR）：img onerror 点火器与 teapot 系写法。

    两者在沙盒模式都被官方明令禁止，且完全不必要——<script> 是一等公民，
    装卡即被抽出执行，不需要靠图片加载失败来点火。"""
    for tag, attrs in _extract_tags_with_attrs(s):
        if tag != "img":
            continue
        for name, value in attrs:
            if name != "onerror":
                continue
            body = html_mod.unescape(value or "")
            if _SANDBOX_IGNITER_BODY.search(body):
                err("%s 用 <img onerror> 点火器注入代码——沙盒模式**官方明令禁止**（teapot 系写法），"
                    "且完全不必要：<script> 是一等公民，装卡那一刻就被抽出执行。"
                    "改法：**专开一条规则只放 <script>**，匹配式填正文用不到的词"
                    "（如 {{卡名-kit}}），谁都不引用即可。" % where)
    if _SANDBOX_TEAPOT.search(s):
        err("%s 含 teapot 系写法——沙盒模式官方明令禁止。改用专开一条只放 <script> 的规则，"
            "配合 sdk.on('message:mount') 给每条气泡绑事件。" % where)


# 选择器前缘：串首、块结束、分号、空白，或 <style> 的 `>`。
# 前缘限制是为了不误伤 [data-chat="message-body"]{...} 这类属性选择器。
_SANDBOX_GLOBAL_CSS = (
    # 裸 `*{}` 与后代/子组合子里的 `*` 必须分开：真正污染平台 chrome 的只有
    # **选择器起始位置**的通用选择器。`.sbk-host *{}`、`.a > *{}` 已被祖先限定作用域，
    # 是良好写法，不该报。原正则前缘含 `\s` 与 `>`，把 `.sbk-host ` 的那个空格
    # 和 `.a > ` 的箭头都当成了前缘 → 误报。
    # 现在前缘只认「选择器起始」：串首 / `}` 后（上一块结束）/ `;` 后 /
    # `,` 后（逗号后另起一个裸选择器，`.a, *{}` 该报）/ `{` 后（@media 内首个选择器）/
    # `<style>` 标签之后。注意 `>` 与空白**不**是前缘，那是组合子。
    (re.compile(r"(?:^|[\},;{]|<style[^>]*>)\s*\*\s*\{"), "*{}"),
    (re.compile(r"(?:^|[\}\;\s>])html\s*\{", re.I), "html{}"),
    (re.compile(r"(?:^|[\}\;\s>])body\s*\{", re.I), "body{}"),
    (re.compile(r":root\s*\{", re.I), ":root{}"),
)
_SANDBOX_MARKDOWN_CODE_BLOCK = re.compile(r"^[ ]{4,}<", re.M)


def check_sandbox_content_warnings(s, where):
    """沙盒模式 WARN（全部来自官方 validate.mjs）：净化、禁用标签、全局 CSS、
    Markdown 代码块、订阅位置、自问自答死循环、「消息生成中」占位陷阱。"""
    # 作者自写 data-* 会被净化删掉 → 自己的按钮用 class 或 id
    author_attrs = []
    for _tag, attrs in _extract_tags_with_attrs(s):
        for name, _value in attrs:
            if name.startswith("data-") and name not in SANDBOX_PLATFORM_DATA_ATTRS:
                if name not in author_attrs:
                    author_attrs.append(name)
    if author_attrs:
        warn("%s 可见 HTML 上自写 %s——沙盒模式会把作者自写的 data-* **净化删掉**，"
             "选择器会失效。自己的节点用 class 或 id。" % (where, "、".join(author_attrs)))
    # 会被净化删掉的标签
    present = [t for t in SANDBOX_FORBIDDEN_TAGS if re.search(r"<%s\b" % t, s, re.I)]
    if present:
        warn("%s 含 <%s>——不在沙盒模式标签白名单内，会被净化删掉。"
             % (where, ">、<".join(present)))
    # 禁全局 CSS
    hits = [label for regex, label in _SANDBOX_GLOBAL_CSS if regex.search(s)]
    if hits:
        warn("%s 含全局 CSS %s——沙盒模式禁全局 CSS（会污染平台 chrome）。"
             '改用 [data-chat="root"] 作用域。' % (where, "、".join(hits)))
    # 替换内容会过一遍 Markdown：缩进 4 空格的 HTML 会被当代码块原样显示
    if _SANDBOX_MARKDOWN_CODE_BLOCK.search(s):
        warn("%s 有行缩进 4+ 空格后紧跟 <——替换内容会过一遍 Markdown，"
             "这会被当**代码块**原样显示成源码。HTML 不要缩进 4 空格。" % where)
    # 订阅应写在脚本体，不要写在 mount 回调里（每挂一条气泡就重复订阅一次）
    mount = re.search(r"sdk\.on\s*\(\s*['\"]message:mount['\"]", s)
    if mount and re.search(r"sdk\.on\s*\(", s[mount.end():mount.end() + 1200]):
        warn("%s 在 sdk.on('message:mount') 之后不远处又出现 sdk.on(——"
             "订阅要写在**脚本体**里，写进 mount 回调会每挂一条气泡就重复订阅一次。" % where)
    # message:done + message.send 同条 = 自问自答死循环
    if "message:done" in s and re.search(r"sdk\.message\.send\s*\(", s):
        warn("%s 同一条规则里既有 message:done 又有 sdk.message.send(——"
             "收到回复就再发一条会做成**自问自答死循环**。请加状态位或改由用户手势触发。" % where)
    # 「消息生成中」占位陷阱
    if (mount and '[data-chat="message-body"]' in s
            and (re.search(r"message\.send\s*\(", s) or "message:stream" in s)):
        warn("%s 从 message:mount 里读 [data-chat=\"message-body\"]——"
             "空 AI 气泡刚挂上时那里是平台占位「消息生成中」，**不是模型回的字**。"
             "跟字用 message:stream 的 msg.content，收尾用 message:done 的 msg.content；"
             "content 空时也不要退回去读 DOM。" % where)


def check_sandbox_find_regex_content(fr, where):
    """匹配式的内容禁令（WARN）：别含 HTML 标签或独立保留字。"""
    if re.search(r"<[a-zA-Z/]", fr):
        warn("%s findRegex 含 HTML 标签——平台不建议，匹配式应是正文里的标记词。" % where)
    # 单词边界比官方 validate.mjs 的 `(^|[^A-Za-z])w([^A-Za-z]|$)` 更窄：
    # 边界排除了 `-` 与 `_`，所以连字符/下划线复合标识符里的保留字不再误报。
    # 起因：基座装载标记名形如 `/{{sbk-css}}/`，`css` 前是 `-`、后是 `}`，
    # 按官方算法算「独立保留字」被误 WARN。而 `sbk-css` 显然是一个整体标识符，
    # 不是创卡页文案禁的那个裸保留字。规则本身保留（官方文档确有此禁令，
    # 且线上真卡有用 `【css】` 当匹配式的，故仍只 WARN）。
    hit = [w for w in SANDBOX_RESERVED_IN_PATTERN
           if re.search(r"(^|[^A-Za-z_-])%s([^A-Za-z_-]|$)" % w, fr, re.I)]
    if hit:
        warn("%s findRegex 含独立保留字 %s——创卡页文案禁用，建议换词。"
             % (where, "、".join(hit)))


def check_comment_length(comment, platform, where):
    """世界书条目标题（comment）长度。MMD 上限 20 字，超出在平台侧被截断；st 无限制。

    沙盒模式**故意降级为 WARN**（锁定决策 D8）：沙盒是同一 MMD 平台的新聊天页，
    20 字来源是创卡页 UI，限制仍在，但官方 validate-worldbook.mjs **不检查该项**，
    判 ERROR 会与官方校验结论冲突。请勿"顺手修正"成 ERROR。"""
    if platform not in MMD_FAMILY:
        return
    if not isinstance(comment, str):
        return
    if len(comment) > MAX_COMMENT_LEN:
        report = warn if platform == "mmdsandbox" else err
        report("%s 标题共 %d 字，超过 MMD 上限 %d 字——导入后标题被截断。"
               "请精简标题，去掉【】·— 等装饰符（装饰符同样占额度）。"
               % (where, len(comment), MAX_COMMENT_LEN))


def check_platform_redlines(s, platform, where):
    """s: 待检字符串（如 replaceString 解析后的值）。where: 来源描述。"""
    # onerror="" 内部裸双引号（影渲法 demo 实机踩出的真红线）
    check_onerror_inner_quote(s, platform, where)

    # <script> 标签：两个在役 MMD 平台都支持（沙盒模式更是一等公民），仅记 OK
    if re.search(r"<script\b", s, re.I):
        if platform == "mmd":
            ok("%s 含 <script>——当前MMD已确认支持，正常执行。" % where)
        elif platform == "mmdsandbox":
            ok("%s 含 <script>——沙盒模式的一等公民，装卡即抽出，整张卡只跑一次。" % where)
        # st 不报

    # ES6 语法不再检查：在役的 mmd / mmdsandbox 均全面支持，仅退役的 ES5-only 旧平台需要。

    # 纯DOM API：innerHTML 拼接 / cssText
    if re.search(r"\.innerHTML\s*=", s):
        warn("%s 用 innerHTML 赋值——易被平台破坏，改用 createElement/textContent。" % where)
    if re.search(r"\.cssText\s*=", s):
        warn("%s 用 style.cssText——易被平台净化，改用预定义CSS类。" % where)

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
    """执行当前 MMD 的 inline onclick 净化规则。

    仅 mmd：净化 allowlist 是当前 MMD 面板的实测结论。沙盒模式不适用——普通标签
    onclick 可用（svg 内会被删），每条气泡的按钮官方要求写在 sdk.on('message:mount') 里。
    「内联处理器必须单行」是退役旧平台的 CSP 限制，已随之删除。"""
    if platform != "mmd":
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
        return ["MMD 正则导入必须为 pageDepth/statusbar/beginning/regex_scripts 四字段对象，顶层数组仅适用于 ST"]
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


def _js_regex_pattern_body_error(pattern):
    """pattern 体的保守结构 fallback（不含分隔符与 flags）。命中项均为确定的 JS 非法写法。"""
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
    return None


def _js_regex_body_or_oracle_error(pattern, flags):
    """pattern+flags 是否为合法 JS RegExp。先保守 fallback，Node 可用时以真实语法为准。"""
    body_error = _js_regex_pattern_body_error(pattern)
    if body_error:
        return body_error
    oracle_available, oracle_error = _node_js_regex_error(pattern, flags)
    if oracle_available and oracle_error:
        return "Node JS RegExp SyntaxError: %s" % oracle_error
    return None


def _js_regex_structure_error(fr):
    """当前 MMD 的 findRegex 门禁：必须是 /pattern/flags 字面量且正则体合法。"""
    parsed = _split_findregex_literal(fr)
    if parsed is None:
        return "必须为 /pattern/flags 形式，且分隔符、字符类、换行和 flags 合法"
    pattern, flags = parsed
    return _js_regex_body_or_oracle_error(pattern, flags)


# 官方 classifyPattern 的正则形态判定式。合法 flags 仅 gimsuy（无 d、无 v）。
_SANDBOX_SLASH_FORM = re.compile(r"^/([\s\S]+)/([gimsuy]*)$")


def classify_sandbox_pattern(raw):
    """沙盒模式匹配式形态判定。逐字对齐官方 classifyPattern
    （packages/chat-render/src/transforms.ts，validate.mjs:51-66 等价实现）。

    返回 (kind, payload)：
      ("empty", None) / ("literal", 字面量) / ("regex", None) / ("bad-regex", 错误信息)

    锁定决策 D7：**沙盒模式不强制 slash literal**。纯字面量标记（{{hud}}）是官方
    首选写法，绝不能当成非法。当前 MMD 那条「必须写 /…/」的实测铁律只适用于 /mmd。"""
    trimmed = (raw if isinstance(raw, str) else "").strip()
    trimmed = re.sub(r"^`|`$", "", trimmed)      # 先 trim 再剥掉首尾反引号
    if not trimmed:
        return "empty", None
    m = _SANDBOX_SLASH_FORM.match(trimmed)
    if not m:
        return "literal", trimmed
    pattern, flags = m.group(1), m.group(2)
    if "g" not in flags:
        flags += "g"                              # 缺 g 平台自动补 → 总是全文替换
    error = _js_regex_body_or_oracle_error(pattern, flags)
    if error:
        return "bad-regex", error
    return "regex", None


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

    沙盒模式也适用：attachShadow 降级守卫与平台版本无关，且沙盒模式长期面板应挂舞台
    （sdk.stage），影渲法只在需要样式隔离时用。

    - 含 attachShadow = 影渲法引擎。2.0 起要求 shadow→light DOM 降级链：
      attachShadow 不可用环境（旧 WebView/平台禁用）应回退 light DOM，否则面板静默消失。
    - 判据：attachShadow 调用应被 try/catch 或三元守卫包裹（shadowOf 模式
      `b.shadowRoot||(b.attachShadow?b.attachShadow(...):null)`），且存在 light 兜底
      （document 注 style + 非 shadow 挂载）。裸 attachShadow 无守卫 → 警告（1.0 隐患）。
    """
    if platform not in MMD_FAMILY:
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


def _sandbox_chat_version_is_one(value):
    """对齐官方 Number(data.chatVersion) !== 1。bool 不算数字（配错的可能性远大于故意）。"""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        try:
            return float(value.strip()) == 1
        except ValueError:
            return False
    return False


def _validate_sandbox_top_level(obj):
    """沙盒模式导入 JSON 顶层：恰好 6 键白名单。返回 regex_scripts（非 list 时为 None）。"""
    # chatVersion 是最要命的一个字段：写错会静默落到旧聊天页，没有 SDK、没有 data-*，
    # 页面上看不出「哪里错了」，只是所有交互都不工作。
    if "chatVersion" not in obj:
        err("沙盒模式导入 JSON 缺 chatVersion——缺省等于 chatVersion:0，"
            "卡会**静默落到旧聊天页**（无 SDK、无 [data-chat]、无舞台），"
            "页面上看不出异常但所有交互都不工作。必须写 chatVersion:1。")
    elif not _sandbox_chat_version_is_one(obj["chatVersion"]):
        err("沙盒模式 chatVersion 必须是 1，当前为 %r——会**静默落到旧聊天页**"
            "（无 SDK、无 [data-chat]、无舞台）。" % (obj["chatVersion"],))
    else:
        ok("chatVersion=1（新聊天页 / 沙盒模式已开启）")

    for key in SANDBOX_FORBIDDEN_TOP_LEVEL_KEYS:
        if key in obj:
            err("沙盒模式导入 JSON 不能有顶层 %s——世界书要单独交付（根对象只留 entries），"
                "role/presentation 是官方**回归夹具**形状而非导入格式，照抄会被判 ERROR。" % key)
    unknown = [k for k in obj
               if k not in SANDBOX_TOP_LEVEL_KEYS and k not in SANDBOX_FORBIDDEN_TOP_LEVEL_KEYS]
    if unknown:
        warn("沙盒模式顶层出现未知键 %s——导入页不认，会被忽略。顶层恰好 6 键：%s。"
             % ("、".join(sorted(unknown)), "/".join(SANDBOX_TOP_LEVEL_KEYS)))

    if "pageDepth" in obj and obj["pageDepth"] != 2:
        warn("沙盒模式 pageDepth 建议固定 2（当前 %r）——该字段只对旧页有意义，新页不实现。"
             % (obj["pageDepth"],))
    for field in ("statusbar", "beginning"):
        if field not in obj:
            warn("沙盒模式导入 JSON 缺 %s。" % field)

    limits = (("statusbar", SANDBOX_MAX_STATUSBAR), ("beginning", SANDBOX_MAX_BEGINNING),
              ("personality", SANDBOX_MAX_PERSONALITY))
    for field, limit in limits:
        if field not in obj:
            continue
        value = obj[field]
        if not isinstance(value, str):
            err("沙盒模式顶层 %s 必须为 string，当前为 %s。" % (field, type(value).__name__))
            continue
        if len(value) > limit:
            err("沙盒模式 %s 共 %d 字，超过上限 %d 字。" % (field, len(value), limit))
        else:
            ok("%s %d 字 ≤ %d" % (field, len(value), limit))

    scripts = obj.get("regex_scripts")
    if "regex_scripts" in obj and not isinstance(scripts, list):
        err("沙盒模式顶层 regex_scripts 必须为 array，当前为 %s。" % type(scripts).__name__)
        return None
    if not isinstance(scripts, list):
        scripts = []
    personality = obj.get("personality", "")
    if not scripts and not (isinstance(personality, str) and personality.strip()):
        err("沙盒模式导入 JSON 没有可交付物：regex_scripts 为空且 personality 空白。")
        return None
    if len(scripts) > SANDBOX_MAX_RULES:
        err("沙盒模式正则 %d 条，超过上限 %d 条——导入时会被直接截断。"
            % (len(scripts), SANDBOX_MAX_RULES))
    else:
        ok("正则条数 %d ≤ %d" % (len(scripts), SANDBOX_MAX_RULES))
    return scripts


def _strip_style_and_script(s):
    """剥掉 <style>/<script> 块，判断这条规则是否产出可见内容。

    闭合标签容忍 `<\\/script>` 写法：官方要求 JSON 字符串里把 `</script>` 写成
    `<\\/script>` 防宿主页面提前截断，作者偶尔会多转义一层留下真实反斜杠。"""
    return re.sub(r"<(style|script)\b[\s\S]*?<\\?/\1\s*>", "", s, flags=re.I).strip()


def _validate_sandbox_rules(obj, scripts):
    """逐条校验沙盒模式规则，并做字面量去重与触发串接得上的交叉检查。"""
    # 触发串汤：statusbar / beginning / 其他规则的 replaceString（链式触发被官方认可）
    # 每项为 (来源下标或 None, 文本)；下标用于把规则自己的 replaceString 排除掉。
    soup_parts = [(None, obj.get(k, "") if isinstance(obj.get(k, ""), str) else "")
                  for k in ("statusbar", "beginning")]
    for idx, sc in enumerate(scripts):
        if isinstance(sc, dict) and isinstance(sc.get("replaceString"), str):
            soup_parts.append((idx, sc["replaceString"]))
    seen_literals = {}
    seen_names = {}

    for i, sc in enumerate(scripts):
        label = "沙盒规则[%d]" % i
        if not isinstance(sc, dict):
            err("%s 必须为 object，当前为 %s。" % (label, type(sc).__name__))
            continue
        name = sc.get("scriptName")
        if isinstance(name, str) and name.strip():
            label = "沙盒规则[%s]" % name
        for field in MMD_SCRIPT_KEYS:
            if field not in sc:
                err("%s 缺字段 %s——一条规则恰好四个字段：%s。"
                    % (label, field, "/".join(MMD_SCRIPT_KEYS)))
        extra = [k for k in sc if k not in MMD_SCRIPT_KEYS]
        if extra:
            warn("%s 有多余字段 %s——一条规则恰好四个字段：%s。"
                 % (label, "、".join(sorted(extra)), "/".join(MMD_SCRIPT_KEYS)))

        if "id" in sc:
            rid = sc["id"]
            if isinstance(rid, bool) or not isinstance(rid, (int, float)) or rid >= 0:
                err("%s id 必须是**负数**（-1、-2…，导入时会重编号），当前为 %r。" % (label, rid))

        if "scriptName" in sc:
            if not isinstance(name, str) or not name.strip():
                err("%s scriptName 必须为非空字符串，当前为 %r。" % (label, name))
            elif len(name) > SANDBOX_MAX_SCRIPT_NAME_HARD:
                # 双阈值见文件头 SANDBOX_MAX_* 注释（基座事实卡 §6）：
                # 200 是源码真值 name:200，超出必被 Ws() 静默截断 → ERROR。
                err("%s scriptName 共 %d 字，超过平台硬上限 %d 字，会被静默截断。"
                    % (label, len(name), SANDBOX_MAX_SCRIPT_NAME_HARD))
            else:
                if len(name) > SANDBOX_MAX_SCRIPT_NAME:
                    # 20 是创卡页编辑器 UI 的计数器上限：导入能绕过，但作者一进
                    # 编辑器改这条就被截断 → 只 WARN，不拦。
                    warn("%s scriptName 共 %d 字，超过编辑器上限 %d 字（导入能绕过，"
                         "但作者一进创卡页编辑器就会被截断）。平台硬上限是 %d 字。"
                         % (label, len(name), SANDBOX_MAX_SCRIPT_NAME,
                            SANDBOX_MAX_SCRIPT_NAME_HARD))
                if name in seen_names:
                    warn("%s scriptName 与第 %d 条重名——名称只给自己看，但重名难排查。"
                         % (label, seen_names[name]))
                else:
                    seen_names[name] = i

        fr = sc.get("findRegex")
        if "findRegex" in sc:
            if not isinstance(fr, str) or not fr.strip():
                err("%s findRegex 必须为非空字符串，当前为 %r。" % (label, fr))
            elif len(fr) > SANDBOX_MAX_FIND_REGEX_HARD:
                # 双阈值见文件头 SANDBOX_MAX_* 注释（基座事实卡 §6）：
                # 4096 是源码真值 regex:4096，超出必被 Ws() 静默截断成废匹配式 → ERROR。
                err("%s findRegex 共 %d 字，超过平台硬上限 %d 字，会被静默截断。"
                    % (label, len(fr), SANDBOX_MAX_FIND_REGEX_HARD))
            else:
                if len(fr) > SANDBOX_MAX_FIND_REGEX:
                    # 1000 是创卡页编辑器 UI 的计数器上限 → 只 WARN，不拦。
                    warn("%s findRegex 共 %d 字，超过编辑器上限 %d 字（导入能绕过，"
                         "但作者一进创卡页编辑器就会被截断）。平台硬上限是 %d 字。"
                         % (label, len(fr), SANDBOX_MAX_FIND_REGEX,
                            SANDBOX_MAX_FIND_REGEX_HARD))
                _validate_sandbox_pattern(fr, label, i, seen_literals, soup_parts, sc)

        rs = sc.get("replaceString")
        if "replaceString" in sc:
            if not isinstance(rs, str):
                err("%s replaceString 必须为 string，当前为 %s。" % (label, type(rs).__name__))
            elif len(rs) > SANDBOX_MAX_REPLACE_STRING_HARD:
                # 双阈值见文件头 SANDBOX_MAX_* 注释（基座事实卡 §6）：
                # 100000 是源码真值 content:1e5，超出必被 Ws() 静默截断 → ERROR。
                err("%s replaceString 共 %d 字，超过平台硬上限 %d 字，会被静默截断，请拆条。"
                    % (label, len(rs), SANDBOX_MAX_REPLACE_STRING_HARD))
            elif len(rs) > SANDBOX_MAX_REPLACE_STRING:
                # 20000 是创卡页编辑器 UI 的计数器上限 → 只 WARN，不拦。
                warn("%s replaceString 共 %d 字，超过编辑器上限 %d 字（导入能绕过），"
                     "但超了作者一进编辑器就被截断，建议拆条。平台硬上限是 %d 字。"
                     % (label, len(rs), SANDBOX_MAX_REPLACE_STRING,
                        SANDBOX_MAX_REPLACE_STRING_HARD))


def _validate_sandbox_pattern(fr, label, index, seen_literals, soup_parts, sc):
    """匹配式形态判定 + 字面量去重 + 触发串接得上检查。"""
    check_sandbox_find_regex_content(fr, label)
    kind, payload = classify_sandbox_pattern(fr)
    if kind == "bad-regex":
        err("%s findRegex 写成 /…/ 但正则语法错（%s）——"
            "**整条规则会被静默丢弃**，不降级成字面量，页面上看不出异常。"
            "不确定就改用纯字面量标记（如 {{hud}}），那是官方首选写法。" % (label, payload))
        return
    if kind != "literal":
        return
    literal = payload
    # 字面量按顺序跑：前一条把全文换完，后一条同串永远匹配不到
    if literal in seen_literals:
        err("%s 字面量匹配式 %r 与第 %d 条重复——规则按顺序跑，"
            "前一条会把全文都换掉，这条**永远匹配不到**。" % (label, literal, seen_literals[literal]))
        return
    seen_literals[literal] = index
    # 可见 HTML 的匹配式必须能在 statusbar/beginning/另一条规则的 replaceString 里找到
    rs = sc.get("replaceString")
    if not isinstance(rs, str) or not _strip_style_and_script(rs):
        return   # 只放 <style>/<script> 的规则，匹配式故意谁都不引用
    if not any(literal in text for src, text in soup_parts if src != index):
        warn("%s 字面量匹配式 %r 会产出可见内容，但它在 statusbar / beginning / "
             "其他规则的 replaceString 里都找不到——**页面上永远不会出现**。"
             "把触发串写进 statusbar 或 beginning（人设的输出约定也要对得上）。"
             % (label, literal))


def validate_regex(obj, platform):
    """MMD 导入 JSON 必须是严格四字段 dict；ST 保持正则数组兼容。"""
    scripts = []
    if platform == "mmdsandbox":
        if not isinstance(obj, dict):
            err("沙盒模式导入 JSON 顶层必须是对象（恰好 6 键：%s），当前为 %s。"
                % ("/".join(SANDBOX_TOP_LEVEL_KEYS), type(obj).__name__))
            return
        scripts = _validate_sandbox_top_level(obj)
        if scripts is None:
            return
        ok("识别为 沙盒模式导入json 格式（%d 条正则）" % len(scripts))
        _validate_sandbox_rules(obj, scripts)
        for i, sc in enumerate(scripts):
            if not isinstance(sc, dict):
                continue
            name = sc.get("scriptName")
            tag = ("沙盒规则[%s]" % name if isinstance(name, str) and name.strip()
                   else "沙盒规则[%d]" % i)
            rs = sc.get("replaceString")
            if not isinstance(rs, str) or not rs:
                continue
            check_sandbox_redlines(rs, tag)
            check_sandbox_sdk_names(rs, tag)
            check_sandbox_content_warnings(rs, tag)
            check_platform_redlines(rs, platform, tag)
            # `<\/script>` 是官方**要求**的写法（防宿主页面提前截断），先还原再查双重转义，
            # 否则每条正确的脚本规则都会被误报成"残留反斜杠"。
            check_double_escape(rs.replace("<\\/", "</"), tag)
            check_shadowcast(rs, platform, tag)
        for field in ("statusbar", "beginning"):
            value = obj.get(field)
            if isinstance(value, str) and value:
                check_sandbox_content_warnings(value, "顶层 %s" % field)
        return

    mmd_platform = platform == "mmd"
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
            if platform == "mmd" and has_inline_onclick:
                if "stopPropagation" not in rs:
                    warn("%s 有 onclick 但未见 stopPropagation——交互模块最外层应加 onclick=\"event.stopPropagation()\" 防事件冒泡。" % tag)


def validate_card(obj, platform):
    spec = obj.get("spec", "")
    sv = obj.get("spec_version", "")
    ok("角色卡 spec=%s spec_version=%s" % (spec, sv))
    data = obj.get("data", {})
    if not isinstance(data, dict):
        data = {}

    if platform == "mmdsandbox":
        # 锁定决策 D6：沙盒模式不走 chara_card_v2 / PNG 整卡，故不套 v2 强制检查。
        warn("沙盒模式不使用 chara_card_v2 / PNG 整卡（官方明令禁 PNG 整卡）。"
             "交付物应为「顶层恰好 6 键的导入正则 JSON」+「独立 persona 文本文件」"
             "（导入页不读 personality 字段，须手工粘贴）+（可选）独立世界书 JSON。"
             "请改用 --type regex 审核导入 JSON。")
    elif platform == "mmd":
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
    p.add_argument("--platform", choices=["mmd", "mmdsandbox", "st"], default="mmd",
                   help="目标平台，默认 mmd（当前MMD）。mmdsandbox = MMD沙盒模式（chatVersion:1 新聊天页）")
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
