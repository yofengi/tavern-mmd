#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 预览脚本 build-preview.py
把状态栏/美化正则的 replaceString 拼成完整 HTML 沙箱文件，按平台注入渲染限制。
主AI 用自带 Preview 工具打开看渲染、测交互（子代理无法与渲染工具交互）。

用法:
  python build-preview.py <文件> --platform <mmd|mmdsandbox|st> [--mode panels|panorama|both] [-o 输出.html]

平台渲染差异:
  st         : 原样渲染，<script>/ES6 全执行
  mmd        : <script>/ES6 全执行（已确认支持）；script 加"✓script"角标标明正常执行
               findRegex 强制 /pattern/flags，裸字面量按结构错误处理
               inline onclick 按当前MMD净化 allowlist 过滤
  mmdsandbox : MMD沙盒模式（新聊天页，chatVersion:1）。<script> 一等公民 + 官方 SDK
               findRegex 走官方 classifyPattern：/pattern/flags 为正则，其余非空串为字面量
               （字面量是官方首选写法）；写成 /…/ 但语法错 → 平台整条静默丢弃，预览判 ERROR
               不施加当前MMD 的 onclick 净化；改为提示 svg 内 onclick 与自写 data-* 会被净化删除
               <style>/<script> 装卡即抽出，不论规则有没有匹配到都装上（官方首选写法
               「专开一条只放 script/style、匹配式谁都不引用」在预览里照样生效）
               全景模式额外注入 [data-chat]/[data-slot] 钩子与 14 个 --chat-* 设计令牌
               （实测确证，官方手册只记 10 个；见 SANDBOX_DESIGN_TOKENS），另注入
               --rpx 尺寸基准与 --chat-viewport-height 静态值（这两个不计入 14 个）

退出码: 0=生成成功  1=致命审计失败（不写文件）  2=用法/读取错误
"""
import sys
import json
import argparse
import re
import os
import html as html_mod
from html.parser import HTMLParser

from validate import (classify_mmd_onclick,
                      _split_findregex_literal as _split_regex_literal,
                      _js_regex_structure_error, _compile_js_regex_for_preview,
                      _replace_js_regex, _custom_marker_occurrences,
                      _mmd_regex_top_level_errors, _mmd_regex_schema_errors,
                      _js_regex_oracle_available)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def load(path):
    with open(path, "rb") as f:
        rawb = f.read()
    txt = rawb.decode("utf-8-sig")
    return json.loads(txt)


def _script_list(obj):
    if isinstance(obj, dict):
        scripts = obj.get("regex_scripts", [])
        return scripts if isinstance(scripts, list) else []
    if isinstance(obj, list):
        return obj
    return []


def _script_count(obj):
    return len(_script_list(obj))


def _text_field(obj, name):
    v = obj.get(name, "") if isinstance(obj, dict) else ""
    return v if isinstance(v, str) else ""


_SANDBOX_SLASH_FORM = re.compile(r"^/([\s\S]+)/([gimsuy]*)$")


def _escape_for_slash_literal(pattern):
    """把 pattern 里未转义的 / 与行终止符改写成等价转义，供 slash 字面量解析器复用。
    JS 里 \\/ 与 /、\\n 与裸换行在正则源码中语义相同，改写不改变匹配行为。"""
    out = []
    escaped = False
    for ch in pattern:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == "/":
            out.append("\\/")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\u2028":
            out.append("\\u2028")
        elif ch == "\u2029":
            out.append("\\u2029")
        else:
            out.append(ch)
    return "".join(out)


def classify_sandbox_pattern(raw):
    """复刻沙盒模式官方 classifyPattern：返回 (kind, value, reason)。
    kind 取 empty / literal / regex / bad-regex。
    literal 时 value 是待字面量替换的串；regex 时 value 是规范化后的 /pattern/flags。"""
    if not isinstance(raw, str):
        return "bad-regex", "", "findRegex 必须是字符串"
    trimmed = re.sub(r"^`|`$", "", raw.strip())
    if not trimmed:
        return "empty", "", None
    m = _SANDBOX_SLASH_FORM.match(trimmed)
    if not m:
        return "literal", trimmed, None
    pattern, flags = m.group(1), m.group(2)
    if len(set(flags)) != len(flags):
        return "bad-regex", "", "flags 重复（JS RegExp 会抛错）"
    if "g" not in flags:
        flags += "g"          # 缺 g 平台自动补 → 总是全文替换
    canonical = "/%s/%s" % (_escape_for_slash_literal(pattern), flags)
    reason = _js_regex_structure_error(canonical)
    if reason:
        return "bad-regex", "", reason
    return "regex", canonical, None


def _mmd_top_level_error(obj, platform):
    # 沙盒模式导入 JSON 是 6 键白名单（含 chatVersion/personality），与当前MMD 四字段
    # schema 不同，不能套用；沙盒的顶层结构审核归 validate.py。
    if platform != "mmd":
        return None
    errors = _mmd_regex_top_level_errors(obj)
    return errors[0] if errors else None


def find_structure_errors(obj, platform):
    if platform != "mmd":
        return []
    return _mmd_regex_schema_errors(obj)


def extract_fragments(obj, platform=None):
    """返回可由预览器执行且含 HTML 的替换片段。"""
    if _mmd_top_level_error(obj, platform):
        return []
    frags = []
    for sc in _script_list(obj):
        if not isinstance(sc, dict):
            continue
        rs = sc.get("replaceString", "")
        name = sc.get("scriptName", sc.get("name", ""))
        raw_fr = sc.get("findRegex", "")
        fr = raw_fr if isinstance(raw_fr, str) else ""
        if not isinstance(rs, str):
            continue
        if platform == "mmd" and raw_fr not in ("", None):
            if not isinstance(raw_fr, str) or _js_regex_structure_error(raw_fr):
                continue
            regex, _flags, reason = _compile_js_regex_for_preview(raw_fr)
            if regex is None or reason:
                continue
        if platform == "mmdsandbox" and raw_fr not in ("", None):
            # 字面量是官方首选写法，照常渲染；只有 /…/ 语法错（平台整条静默丢弃）
            # 和预览器模拟不了的正则才跳过。
            kind, value, _reason = classify_sandbox_pattern(raw_fr)
            if kind == "bad-regex":
                continue
            if kind == "regex":
                regex, _flags, reason = _compile_js_regex_for_preview(value)
                if regex is None or reason:
                    continue
        # 含任意 HTML 标签的替换都渲染；跳过纯信标转换器（无标签的占位文本）
        if re.search(r"<[a-zA-Z][a-zA-Z0-9]*[\s/>]", rs):
            frags.append((name, fr, rs))
    return frags


def detect_blank_bar_risk(rs):
    """MMD markdown 管线会把标签之间的裸换行补成空 <p> 撑出横向空白条。
    检测 replaceString 里标签闭合与下一个标签之间是否夹着换行（>\\n...<）。"""
    return bool(re.search(r">\s*\n\s*<", rs))


def _parse_regex_literal(fr):
    """兼容测试/调用：仅返回预览器可执行的 Python regex。"""
    regex, _flags, reason = _compile_js_regex_for_preview(fr)
    return None if reason else regex


def find_invalid_findregexes(obj, platform):
    """返回真正的平台级 findRegex 错误；不含预览器能力限制。
    mmd：必须是 /pattern/flags，裸字面量算结构错误。
    mmdsandbox：字面量合法（官方首选），只有写成 /…/ 却语法错才算错误——
    这种规则被平台整条静默丢弃，页面上看不出异常，必须在预览里点出来。"""
    if platform not in ("mmd", "mmdsandbox"):
        return []
    invalid = []
    for i, sc in enumerate(_script_list(obj)):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        if fr in ("", None):
            continue
        if platform == "mmdsandbox":
            kind, _value, reason = classify_sandbox_pattern(fr)
            if kind != "bad-regex":
                continue
            reason = "写成 /…/ 但正则语法错，平台会整条静默丢弃（%s）" % reason
        else:
            reason = "findRegex 必须是字符串" if not isinstance(fr, str) else _js_regex_structure_error(fr)
        if reason:
            name = sc.get("scriptName", sc.get("name", "#%d" % i))
            invalid.append((str(name), str(fr), reason))
    return invalid


def find_unsupported_preview_regexes(obj, platform):
    """返回 JS 结构合法、但 Python 预览后端无法可靠模拟的规则。
    沙盒模式只有正则形态才可能落到这里；字面量替换预览器完全能模拟。"""
    if platform not in ("mmd", "mmdsandbox"):
        return []
    unsupported = []
    for i, sc in enumerate(_script_list(obj)):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        if not isinstance(fr, str) or not fr:
            continue
        if platform == "mmdsandbox":
            kind, value, _reason = classify_sandbox_pattern(fr)
            if kind != "regex":
                continue
        else:
            if _js_regex_structure_error(fr):
                continue
            value = fr
        regex, _flags, reason = _compile_js_regex_for_preview(value)
        if regex is None or reason:
            name = sc.get("scriptName", sc.get("name", "#%d" % i))
            unsupported.append((str(name), fr, reason or "未知限制"))
    return unsupported


def _findregex_audit_html(obj, platform):
    rows = [
        '<div class="frag-warn">ERROR 非法顶层结构：%s</div>' % html_mod.escape(message)
        for message in find_structure_errors(obj, platform)
    ]
    rows.extend(
        '<div class="frag-warn">ERROR 非法 findRegex：规则 %s（%s；%s）</div>'
        % (html_mod.escape(name), html_mod.escape(fr), html_mod.escape(reason))
        for name, fr, reason in find_invalid_findregexes(obj, platform)
    )
    rows.extend(
        '<div class="frag-warn">WARN 预览器不支持此 JS 正则：规则 %s（%s；%s），已跳过预览替换</div>'
        % (html_mod.escape(name), html_mod.escape(fr), html_mod.escape(reason))
        for name, fr, reason in find_unsupported_preview_regexes(obj, platform)
    )
    return "".join(rows)


_SANDBOX_ASSET_RE = re.compile(r"<(style|script)\b[\s\S]*?</\1\s*>", re.I)


def _split_sandbox_assets(rs):
    """把一条规则的 replaceString 拆成 (装卡即抽出的 style/script, 剩余可见 HTML)。"""
    assets = "".join(m.group(0) for m in _SANDBOX_ASSET_RE.finditer(rs))
    return assets, _SANDBOX_ASSET_RE.sub("", rs)


def collect_sandbox_assets(obj):
    """沙盒模式下 <style>/<script> 装卡那一刻被抽出、按规则顺序收集，
    不论这条规则有没有匹配到都会装上（mmd-sandbox.md §2.1）。
    因此官方首选的「专开一条只放 script/style、匹配式谁都不引用」写法必须照样生效。"""
    parts = []
    for sc in _script_list(obj):
        if not isinstance(sc, dict):
            continue
        rs = sc.get("replaceString", "")
        if not isinstance(rs, str):
            continue
        assets, _visible = _split_sandbox_assets(rs)
        if assets:
            parts.append(assets)
    return "".join(parts)


def _apply_pipeline_to_text(text, obj, platform=None):
    """按规则顺序把替换管线作用在一段文本上。
    沙盒模式：style/script 已由 collect_sandbox_assets 抽出，这里只替换可见 HTML，
    避免同一段脚本既被 hoist 又随替换插入而执行两次。"""
    for sc in _script_list(obj):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        rs = sc.get("replaceString", "")
        if not isinstance(rs, str):
            continue
        if platform == "mmdsandbox":
            _assets, rs = _split_sandbox_assets(rs)
            # 官方 classifyPattern 语义：字面量按转义后全文替换，/…/ 走正则，
            # 语法错的 /…/ 被平台整条静默丢弃（不降级字面量）。
            kind, value, _reason = classify_sandbox_pattern(fr)
            if kind == "literal":
                text = text.replace(value, rs)
            elif kind == "regex":
                regex, js_flags, reason = _compile_js_regex_for_preview(value)
                if regex is not None and not reason:
                    text = _replace_js_regex(text, regex, js_flags, rs)
            continue
        if not isinstance(fr, str) or not fr:
            continue
        if platform != "mmd" and not fr.startswith("/"):
            text = text.replace(fr, rs)
            continue
        if _js_regex_structure_error(fr):
            if platform != "mmd":
                text = text.replace(fr, rs)
            continue
        regex, js_flags, reason = _compile_js_regex_for_preview(fr)
        if regex is None or reason:
            continue
        text = _replace_js_regex(text, regex, js_flags, rs)
    return text


def apply_regex_pipeline(obj, platform=None):
    """模拟 JS 替换管线；当前MMD 跳过结构错误和预览器不支持规则。"""
    if _mmd_top_level_error(obj, platform):
        return ""
    if isinstance(obj, list):
        return ""
    text = _text_field(obj, "statusbar") + _text_field(obj, "beginning")
    return _apply_pipeline_to_text(text, obj, platform)


def _svg_ranges(html):
    """返回 [(start, end)]，覆盖每个 <svg>…</svg> 区间。"""
    return [(start, _find_balanced_tag_end(html, start, end, "svg"))
            for start, end, _tag in _iter_tags(html, "svg")]


def find_dangling_markers(obj, platform=None):
    """管线可完整模拟时，扫描每个自定义开始/结束标记 occurrence。
    沙盒模式白名单显式收录 svg 及 path/circle/rect/line/text 等绘图标签
    （mmd-sandbox.md §5.2），但通用 HTML_TAGS 不含它们 → svg 内的标签会被误判成
    悬空标记（致命）。故沙盒模式下剔除落在 <svg>…</svg> 区间内的 occurrence。"""
    if isinstance(obj, list) or find_unsupported_preview_regexes(obj, platform):
        return []
    rendered = apply_regex_pipeline(obj, platform)
    occurrences = _custom_marker_occurrences(rendered)
    if platform == "mmdsandbox":
        ranges = _svg_ranges(rendered)
        return [marker for marker, pos in occurrences
                if not any(s <= pos < e for s, e in ranges)]
    return [marker for marker, _pos in occurrences]


class _OnclickSanitizer(HTMLParser):
    """重建 HTML，仅移除当前 MMD allowlist 外的真实 onclick 属性。"""
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=False)
        self.parts = []
        self.removed = []

    @staticmethod
    def _attrs(attrs):
        out = []
        for name, value in attrs:
            if value is None:
                out.append(" " + name)
            else:
                out.append(' %s="%s"' % (name, html_mod.escape(value, quote=True)))
        return "".join(out)

    def _start(self, tag, attrs, closed):
        kept = []
        removed_here = []
        for name, value in attrs:
            if name.lower() == "onclick":
                allowed, reason = classify_mmd_onclick(value or "")
                if not allowed:
                    removed_here.append((value or "", reason))
                    continue
            kept.append((name, value))
        if removed_here:
            kept.append(("data-mmd-onclick-disabled", "1"))
            self.removed.extend(removed_here)
        self.parts.append("<%s%s%s" % (tag, self._attrs(kept), "/>" if closed else ">"))

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def handle_endtag(self, tag):
        self.parts.append("</%s>" % tag)

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append("&%s;" % name)

    def handle_charref(self, name):
        self.parts.append("&#%s;" % name)

    def handle_comment(self, data):
        self.parts.append("<!--%s-->" % data)

    def handle_decl(self, decl):
        self.parts.append("<!%s>" % decl)

    def handle_pi(self, data):
        self.parts.append("<?%s>" % data)


def sanitize_mmd_onclick(html):
    parser = _OnclickSanitizer()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, TypeError):
        return html, []
    return "".join(parser.parts), parser.removed


_PLATFORM_DATA_ATTRS = ("data-chat", "data-slot", "data-theme", "data-composer",
                        "data-from", "data-state", "data-msg-id")
# 预览器自己注入的标记属性，不是作者写的，不参与沙盒净化告警。
_PREVIEW_DATA_ATTRS = ("data-pano-scaffold", "data-pano-runtime-scaffold",
                       "data-preview-tools", "data-preview-dynamic",
                       "data-mmd-onclick-disabled", "data-message-role",
                       "data-preview-hoisted", "data-preview-bubble-outline")


def find_sandbox_sanitized_attrs(content):
    """沙盒模式净化会删两样东西：svg 内的 onclick、作者自写的 data-*。
    返回 [(种类, 标签片段)]；只做浅层扫描，权威检查在 validate.py。"""
    if not isinstance(content, str):
        return []
    found = []
    svg_ranges = _svg_ranges(content)
    for start, end, tag in _iter_all_tags(content):
        in_svg = any(s <= start < e for s, e in svg_ranges)
        if in_svg and re.search(r"\bonclick\s*=", tag, re.I):
            found.append(("svg-onclick", tag))
        for m in re.finditer(r'\b(data-[a-zA-Z0-9_-]+)\s*=', tag):
            name = m.group(1).lower()
            if name in _PLATFORM_DATA_ATTRS or name in _PREVIEW_DATA_ATTRS:
                continue
            found.append(("author-data-attr", "%s（%s）" % (m.group(1), tag[:80])))
    return found


def _sandbox_sanitize_audit_html(content, label="最终输出"):
    rows = []
    for kind, detail in find_sandbox_sanitized_attrs(content):
        if kind == "svg-onclick":
            rows.append('<div class="frag-warn">WARN svg 内的 onclick 会被沙盒净化删除：'
                        '%s（%s）——改绑到普通标签或用 sdk.on(\'message:mount\') 绑定</div>'
                        % (html_mod.escape(label), html_mod.escape(detail)))
        else:
            rows.append('<div class="frag-warn">WARN 作者自写 data-* 会被沙盒净化删除：'
                        '%s（%s）——自己的节点改用 class 或 id</div>'
                        % (html_mod.escape(label), html_mod.escape(detail)))
    return "".join(rows)


def _onclick_audit_html(content, platform, label="最终输出"):
    """当前MMD：inline onclick 净化审计（致命）。
    沙盒模式：普通标签 onclick 合法，不套用当前MMD 的纯度规则；改为提示官方明说会被
    净化删掉的两样东西（svg 内 onclick / 自写 data-*），判 WARN。"""
    if platform == "mmdsandbox":
        return _sandbox_sanitize_audit_html(content, label)
    if platform != "mmd" or not isinstance(content, str):
        return ""
    _cleaned, removed = sanitize_mmd_onclick(content)
    return "".join(
        '<div class="frag-warn">ERROR inline onclick 已禁用：%s（%s；%s）</div>'
        % (html_mod.escape(label), html_mod.escape(body), html_mod.escape(reason))
        for body, reason in removed
    )


def find_invalid_onclicks(obj, platform):
    """只审计实际进入最终渲染文本的 inline onclick；未命中替换不误报。
    仅当前MMD：沙盒模式允许普通标签 onclick="tap()" 调顶层函数，不适用此纯度规则。"""
    if platform != "mmd":
        return []
    if isinstance(obj, list):
        rendered = "".join(rs for _name, _fr, rs in extract_fragments(obj, platform))
    else:
        rendered = apply_regex_pipeline(obj, platform)
    _cleaned, removed = sanitize_mmd_onclick(rendered)
    return removed


def fatal_preview_findings(obj, platform):
    """所有致命审计均在调用者写文件前完成。"""
    structure = find_structure_errors(obj, platform)
    invalid_regex = find_invalid_findregexes(obj, platform)
    invalid_onclick = find_invalid_onclicks(obj, platform) if not structure else []
    dangling = []
    if isinstance(obj, dict) and not structure:
        dangling = find_dangling_markers(obj, platform)
    return {
        "structure": structure,
        "findRegex": invalid_regex,
        "onclick": invalid_onclick,
        "dangling": dangling,
    }


def _default_output_path(input_path, kind, platform):
    source = os.path.abspath(input_path)
    source_dir = os.path.dirname(source)
    if os.path.basename(os.path.normpath(source_dir)).casefold() == "output":
        output_dir = os.path.join(os.path.dirname(source_dir), "工作")
    else:
        output_dir = source_dir
    stem = os.path.splitext(os.path.basename(source))[0]
    return os.path.join(output_dir, "%s-%s-%s.html" % (stem, kind, platform))


def _html_to_srcdoc(content, platform, assets=""):
    processed = apply_platform_limits(content, platform)
    extra = apply_platform_limits(assets, platform) if assets else ""
    frame_doc = "<style>%s</style>%s%s" % (MARKER_CSS, extra, processed)
    return html_mod.escape(frame_doc, quote=True)


def _panel(title, content, platform, badge="", assets=""):
    label = "%s%s" % (html_mod.escape(title), (" <span class=\"badge\">%s</span>" % html_mod.escape(badge)) if badge else "")
    if not content:
        return '<div class="frag"><div class="frag-label">%s</div><div class="frag-warn">（无内容）</div></div>' % label
    return ('<div class="frag"><div class="frag-label">%s</div>'
            '<iframe class="frag-frame" srcdoc="%s" sandbox="allow-scripts allow-same-origin" '
            'onload="this.style.height=this.contentWindow.document.body.scrollHeight+20+\'px\'">'
            '</iframe></div>' % (label, _html_to_srcdoc(content, platform, assets)))


def _scan_tag_end(html, start):
    quote = None
    i = start + 1
    while i < len(html):
        ch = html[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch == '"' or ch == "'":
            quote = ch
        elif ch == ">":
            return i + 1
        i += 1
    return None


def _iter_all_tags(html):
    """轻量标签扫描器：找到任意开始标签，且尊重单双引号内的 >。"""
    pos = 0
    while True:
        start = html.find("<", pos)
        if start == -1:
            return
        if start + 1 >= len(html) or html[start + 1] in "/!":
            pos = start + 1
            continue
        end = _scan_tag_end(html, start)
        if end is None:
            return
        yield start, end, html[start:end]
        pos = end


def _iter_tags(html, tag_name):
    """轻量标签扫描器：找到 <tag ...>，且尊重单双引号内的 >。
    用于扫描 img onerror 引擎；正则的 [^>]* 会被 JS 里的 c>0 截断。"""
    low = html.lower()
    needle = "<" + tag_name.lower()
    pos = 0
    while True:
        start = low.find(needle, pos)
        if start == -1:
            return
        after = start + len(needle)
        if after < len(html) and (html[after].isalnum() or html[after] in "_-:"):
            pos = after
            continue
        end = _scan_tag_end(html, start)
        if end is None:
            return
        yield start, end, html[start:end]
        pos = end


def _attr_value(tag, attr):
    m = re.search(r"\b%s\s*=\s*([\"'])([\s\S]*?)\1" % re.escape(attr), tag, re.I)
    return m.group(2) if m else ""


def _tag_has_class(tag, class_name):
    return class_name in _attr_value(tag, "class").split()


def _find_balanced_tag_end(html, open_start, open_end, tag_name):
    """从一个开始标签位置找到同名闭合标签结尾；失败时退回开始标签结尾。"""
    low = html.lower()
    name = tag_name.lower()
    depth = 1
    pos = open_end
    while True:
        next_open = low.find("<" + name, pos)
        next_close = low.find("</" + name, pos)
        if next_close == -1:
            return open_end
        if next_open != -1 and next_open < next_close:
            after = next_open + len(name) + 1
            if after < len(html) and (html[after].isalnum() or html[after] in "_-:"):
                pos = after
                continue
            tag_end = _scan_tag_end(html, next_open)
            if tag_end is None:
                return open_end
            depth += 1
            pos = tag_end
            continue
        close_end = low.find(">", next_close)
        if close_end == -1:
            return open_end
        depth -= 1
        pos = close_end + 1
        if depth == 0:
            return pos


def _is_floating_engine_tag(tag):
    """运行时悬浮/侧边栏引擎：<img onerror> 内用 JS 创建 position:fixed 的可拖动按钮/抽屉。
    MMD 真正的悬浮组件是运行时注入的（cssText 设 position:fixed），静态扫描看不到，
    必须靠引擎特征识别——否则会漏进整合面板或被状态栏启发式误吞。"""
    low = tag.lower()
    if "onerror" not in low:
        return False
    if ("data-float-ball" in low or "data-sidebar" in low or "data-drawer" in low or
            "z-float" in low or "z-sidebar" in low or "z-drawer" in low or "z-fab" in low):
        return True
    # 通用特征：onerror 里出现 position:fixed + 拖动/抽屉关键词。
    if "position:fixed" in low.replace(" ", "") and (
            "mousedown" in low or "touchstart" in low or "translatex" in low or
            "float" in low or "sidebar" in low or "drawer" in low):
        return True
    return False


def _is_statusbar_engine_tag(tag):
    low = tag.lower()
    # 悬浮/侧边栏引擎优先归类，避免被状态栏启发式误吞（二者都用 onerror+DOM创建）。
    if _is_floating_engine_tag(tag):
        return False
    if "data-radar" in low or "data-radar-engine" in low:
        return True
    if "onerror" not in low:
        return False
    # 雷达引擎常见特征：rdrNode/data-sid/uni-textarea/动态插入 z-status-box。
    return ("rdr" in low or "data-sid" in low or "uni-textarea" in low or
            "z-status-box" in low or "insertadjacenthtml" in low or "状态栏" in tag)


def _extend_hidden_status_spans(html, end):
    """状态栏引擎后常跟一串 display:none 的 [key=value] 信标，一并归入状态栏面板。"""
    m = re.match(r'(?:\s*<span[^>]*display\s*:\s*none[^>]*>\[[\s\S]*?\]</span>)+', html[end:], re.I)
    if m:
        return end + m.end()
    return end


def split_preview_panels(rendered):
    """返回 (first_message, statusbar, floating)。轻量文本拆分，供预览定位问题。"""
    status_parts = []
    floating_parts = []
    rest = rendered
    # 1) 静态状态栏骨架（KV/已渲染状态栏）。用平衡标签扫描，避免嵌套 div 被截断。
    status_spans = []
    last_end = -1
    for start, end, tag in _iter_tags(rest, "div"):
        if not _tag_has_class(tag, "z-status-box"):
            continue
        ext_end = _find_balanced_tag_end(rest, start, end, "div")
        if start < last_end:
            continue
        status_spans.append((start, ext_end, rest[start:ext_end]))
        last_end = ext_end
    for start, end, chunk in status_spans:
        status_parts.append(chunk)
    for start, end, chunk in sorted(status_spans, key=lambda x: x[0], reverse=True):
        rest = rest[:start] + rest[end:]

    # 2) 运行时引擎（<img onerror>）：一次扫描分类悬浮/状态栏，再从后往前删除，避免删一个就让
    #    后续 start/end 偏移失效。MMD 真正的悬浮球/抽屉是运行时注入的可拖动按钮，position:fixed
    #    由 JS cssText 设，静态扫描看不到，只能靠引擎特征识别（悬浮优先，免被状态栏启发式误吞）。
    spans = []  # (start, end, bucket, chunk)
    for start, end, tag in _iter_tags(rest, "img"):
        if _is_floating_engine_tag(tag):
            spans.append((start, end, "float", rest[start:end]))
        elif _is_statusbar_engine_tag(tag):
            ext_end = _extend_hidden_status_spans(rest, end)
            spans.append((start, ext_end, "status", rest[start:ext_end]))
    for start, end, bucket, chunk in sorted(spans, key=lambda x: x[0]):
        (floating_parts if bucket == "float" else status_parts).append(chunk)
    for start, end, bucket, chunk in sorted(spans, key=lambda x: x[0], reverse=True):
        rest = rest[:start] + rest[end:]

    # 3) 静态悬浮组件（非引擎注入：直接写死的 position:fixed / float/sidebar/ball 类）
    for pat in [r"<[^>]*(?:class=[\"'][^\"']*(?:float|sidebar|ball)[^\"']*[\"'][^>]*)[^>]*>[\s\S]*?</(?:div|button|a)>",
                r"<[^>]*style=[\"'][^\"']*position\s*:\s*fixed[^\"']*[\"'][^>]*>[\s\S]*?</(?:div|button|a)>"]:
        for m in list(re.finditer(pat, rest, re.I)):
            floating_parts.append(m.group(0))
            rest = rest.replace(m.group(0), "", 1)
    return rest, "\n".join(status_parts), "\n".join(floating_parts)


def assemble_preview(obj, platform, src_name):
    """三面板预览：第一句话整合 / 状态栏单独 / 悬浮组件。"""
    if isinstance(obj, list):
        rendered = "".join(rs for _name, _fr, rs in extract_fragments(obj, platform))
        return assemble_html(extract_fragments(obj, platform), platform, src_name,
                             _findregex_audit_html(obj, platform) + _onclick_audit_html(rendered, platform))
    rendered = apply_regex_pipeline(obj, platform)
    first, status, floating = split_preview_panels(rendered)
    audit = _findregex_audit_html(obj, platform) + _onclick_audit_html(rendered, platform)
    audit += "".join('<div class="frag-warn">ERROR 悬空标记：%s</div>' % html_mod.escape(x)
                     for x in find_dangling_markers(obj, platform))
    # 沙盒模式：装卡即抽出的 style/script 与匹配无关，每个隔离 iframe 都要带上，
    # 否则「只放 style/script 且谁都不引用」的官方首选写法在预览里等于不存在。
    assets = collect_sandbox_assets(obj) if platform == "mmdsandbox" else ""
    body = "\n".join([
        _panel("第一句话剩余预览", first, platform, "beginning remainder", assets),
        _panel("状态栏单独预览", status, platform, "status", assets),
        _panel("悬浮组件预览", floating, platform, "floating/sidebar", assets),
        audit,
    ])
    banner = make_banner(platform, src_name, _script_count(obj))
    return PAGE_TEMPLATE % {"platform": platform, "banner": banner,
                            "body": body, "marker_css": MARKER_CSS}


# 全景预览聊天页骨架 CSS（中性默认；被测的全局美化用 !important 会正常压过，与MMD真机一致）。
# .page 是全高 flex 列容器；.pano-chat 滚动区 flex:1；.pano-input-bar 固定底部。
PANORAMA_CSS = """html,body{height:100%;margin:0}
body{display:flex;flex-direction:column;font-family:system-ui,sans-serif;background:#fff;color:#222}
.page{flex:1;display:flex;flex-direction:column;min-height:0;background:#fff}
.topTabbar{flex:0 0 48px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;
  border-bottom:1px solid #ddd;background:#fafafa;box-sizing:border-box;font-size:14px;font-weight:600}
.topTabbar .pano-route-label{font-size:12px;font-weight:400;color:#666}
.pano-chat{flex:1;overflow-y:auto;padding:14px 12px 88px;-webkit-overflow-scrolling:touch}
.pano-chat .chat-body{display:flex;flex-direction:column;min-height:100%}
.item{display:flex;margin:10px 0}
.item .touch-scope{display:flex;width:100%}
.item .content{max-width:82%;padding:10px 13px;border-radius:8px;line-height:1.55;word-break:break-word;box-sizing:border-box}
.content.left{background:#f0f0f3;color:#222;margin-right:auto}
.content.right{background:#3a76f0;color:#fff;margin-left:auto}
.pano-input-bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:8px;align-items:flex-end;
  padding:10px 12px;background:#fafafa;border-top:1px solid #ddd;box-sizing:border-box;z-index:90000}
.pano-input-bar .uni-textarea-textarea{flex:1;min-height:38px;max-height:120px;resize:none;
  padding:9px 11px;border:1px solid #ccc;border-radius:8px;font:inherit;box-sizing:border-box;background:#fff;color:#222}
.pano-send{flex:0 0 auto;height:38px;padding:0 18px;border:none;border-radius:8px;
  background:#3a76f0;color:#fff;font-size:14px;font-weight:600;cursor:pointer}
.pano-send:active{opacity:.8}"""


# 全景预览整页模板：横幅 sticky，iframe 高度撑满视口下方（让内部 position:fixed 输入栏可见）。
PANORAMA_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tavern-mmd 全景预览 [%(platform)s]</title>
<style>
html,body{height:100%%;margin:0}
body{background:#0d1117;color:#e6edf3;font-family:system-ui,sans-serif;display:flex;flex-direction:column}
.banner{padding:10px 16px;font-size:13px;font-weight:600;flex:0 0 auto}
.banner-st{background:#1f6feb}.banner-mmd{background:#9e6a03}.banner-mmdsandbox{background:#1a7f5a}
.frag{flex:1;margin:12px;display:flex;flex-direction:column;border:1px dashed #30363d;border-radius:8px;overflow:hidden;min-height:0}
.frag-label{background:#161b22;color:#8b949e;font-size:11px;padding:6px 12px;border-bottom:1px solid #30363d;flex:0 0 auto}
.frag-warn{background:#3a2d00;color:#f0c674;font-size:11px;padding:6px 12px}
.preview-tools{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 12px;background:#161b22;border-bottom:1px solid #30363d;flex:0 0 auto}
.preview-tools-label{color:#8b949e;font-size:11px;margin-right:2px}
.preview-tool{border:1px solid #484f58;border-radius:4px;background:#21262d;color:#e6edf3;padding:4px 8px;font-size:11px;cursor:pointer}
.preview-tool:hover{background:#30363d}
%(marker_css)s
.pano-frame{flex:1;width:100%%;border:0;display:block;background:#fff;min-height:480px}
</style></head>
<body>
%(banner)s
%(body)s
</body></html>"""


# 全景运行时测试脚手架：预览工具自带，非被测产物。它在被测主题执行前预设聊天路由，
# 并暴露稳定接口给 GUI 黑盒测试追加 AI 内容、切换同文档 DOM 可见性/hash。
# 这只模拟路由观察条件，不宣称卸载或重建真实页面运行时。
PANORAMA_RUNTIME_SCAFFOLD = (
    '<script data-pano-runtime-scaffold="1">'
    "if(!/chat\\/chat/.test(location.hash)){location.hash='#/pages/chat/chat';}"
    "(function(){"
    "var D=document,W=window,seq=0;"
    "function chat(){return D.querySelector('.chat-body');}"
    "function sandbox(){var r=D.querySelector('.page');return !!(r&&r.getAttribute('data-chat')==='root');}"
    "function hook(it,touch,ct,side){if(!sandbox())return;"
    "it.setAttribute('data-chat','message-frame');"
    "touch.setAttribute('data-chat','message');"
    "touch.setAttribute('data-from',side==='left'?'ai':'user');"
    "touch.setAttribute('data-state','done');"
    "ct.setAttribute('data-chat','message-body');}"
    "function add(side,text){var root=chat();if(!root)return null;"
    "var it=D.createElement('div');it.className='item';it.setAttribute('data-preview-dynamic','1');"
    "var touch=D.createElement('div');touch.className='touch-scope';"
    "var ct=D.createElement('div');ct.className='content '+side;ct.textContent=text;"
    "hook(it,touch,ct,side);"
    "touch.appendChild(ct);it.appendChild(touch);root.appendChild(it);"
    "var pane=D.querySelector('.chat');if(pane)pane.scrollTop=pane.scrollHeight;return ct;}"
    "function syncRoute(hash){var active=/chat\\/chat/.test(hash);"
    "var pane=D.querySelector('.chat'),input=D.querySelector('.chat-bottom'),label=D.querySelector('.pano-route-label');"
    "if(pane){pane.hidden=!active;pane.setAttribute('aria-hidden',active?'false':'true');}"
    "if(input){input.hidden=!active;input.setAttribute('aria-hidden',active?'false':'true');}"
    "if(label)label.textContent=active?'chat/chat':'index/index';return active;}"
    "function route(hash){syncRoute(hash);if(location.hash!==hash)location.hash=hash;return location.hash;}"
    "W.__tavernPreview={"
    "addAI:function(text){seq++;return add('left',text||('[Dynamic AI '+seq+'] “待修复“ / \"keep\"'));},"
    "addUser:function(text){seq++;return add('right',text||('[Dynamic user '+seq+']'));},"
    "leave:function(){return route('#/pages/index/index');},"
    "returnToChat:function(){return route('#/pages/chat/chat');},"
    "setRoute:route,getRoute:function(){return location.hash;}"
    "};"
    "})()"
    '</script>'
)


# 发送脚手架走 img onerror，保持与 MMD 交互载体一致；它位于被测内容之外，不参与平台剥离。
PANORAMA_SEND_SCAFFOLD = (
    '<img src="x" data-pano-scaffold="1" style="display:none" '
    "onerror=\"(function(){"
    "var ta=document.querySelector('.uni-textarea-textarea');"
    "var btn=document.querySelector('.pano-send');"
    "var chat=document.querySelector('.chat');"
    "if(!ta||!btn||!chat)return;"
    "var addMsg=function(side,text){"
    "if(window.__tavernPreview){return side==='left'?window.__tavernPreview.addAI(text):window.__tavernPreview.addUser(text);}"
    "var root=document.querySelector('.chat-body');if(!root)return;"
    "var it=document.createElement('div');it.className='item';"
    "var touch=document.createElement('div');touch.className='touch-scope';"
    "var ct=document.createElement('div');ct.className='content '+side;"
    "ct.textContent=text;touch.appendChild(ct);it.appendChild(touch);root.appendChild(it);"
    "chat.scrollTop=chat.scrollHeight;return ct;};"
    "var send=function(){var v=ta.value.replace(/^\\s+|\\s+$/g,'');if(!v)return;"
    "addMsg('right',v);ta.value='';"
    "addMsg('left','[\\u9884\\u89c8\\u6a21\\u5f0f\\uff1a\\u6b64\\u5904\\u4e3aAI\\u56de\\u590d\\u5360\\u4f4d\\uff0c"
    "\\u771f\\u5b9e\\u56de\\u590d\\u9700\\u5728MMD\\u5b9e\\u673a\\u751f\\u6210]');};"
    "btn.onclick=function(ev){ev.stopPropagation();send();};"
    "ta.addEventListener('keydown',function(ev){"
    "if(ev.key==='Enter'&&!ev.shiftKey){ev.preventDefault();send();}});"
    "})()\">"
)


# 沙盒模式聊天页骨架的稳定钩子（mmd-sandbox.md §5）。挂到全景已有节点上，作者写的
# [data-chat="root"] 选择器与 var(--chat-accent) 在预览里就能真的解析到。
_SANDBOX_HOOKS = {
    # data-preview-bubble-outline 是预览专属辅助标记（真机无此属性、无那圈描边），
    # 挂在 root 上让所有气泡（含脚手架动态追加的）都吃到，作者可随手在开发者工具里
    # 删掉它看真实的"气泡与背景同色"效果。样式见 SANDBOX_CHROME_CSS 末尾。
    "root": (' data-chat="root" data-theme="light" data-composer="open"'
             ' data-preview-bubble-outline="1"'),
    "header": ' data-chat="header"',
    "header_title": ' data-chat="header-title"',
    "header_extra": '<span data-slot="header-extra"></span>',
    "messages": ' data-chat="messages"',
    "list": ' data-chat="list"',
    "frame": ' data-chat="message-frame"',
    "msg_user": ' data-chat="message" data-from="user" data-state="done" data-msg-id="pano-1"',
    "msg_ai": ' data-chat="message" data-from="ai" data-state="done" data-msg-id="pano-2"',
    "body": ' data-chat="message-body"',
    "stage": '<div data-chat="author-stage" class="pano-stage" hidden></div>',
    "composer": ' data-chat="composer"',
    "input": ' data-chat="input"',
    "send": ' data-chat="send"',
}


def _panorama_hooks(platform):
    """沙盒模式返回官方 data-* 钩子；其余平台全为空串（骨架一字不变）。"""
    keys = ("root", "header", "header_title", "header_extra", "messages", "list", "frame",
            "msg_user", "msg_ai", "body", "stage", "composer", "input", "send")
    if platform != "mmdsandbox":
        return {k: "" for k in keys}
    return dict(_SANDBOX_HOOKS)


# 沙盒模式设计令牌清单（实测确证共 14 个，mmd-sandbox.md §6.1）。
# 依据：逆向沙盒样式表 sandbox-app.css + 真机探针实测。官方手册只记了前 9 个
# + --chat-viewport-height（共 10 条），漏记了本清单最后 5 个 —— 作者在卡里写
# var(--chat-input-bg) 等是**真机可用**的，预览必须一并注入，否则预览样式塌掉
# 而真机正常，作者会去"修"一个不存在的 bug。改动这里前请先确认实测依据。
SANDBOX_DESIGN_TOKENS = (
    "--chat-bg", "--chat-surface", "--chat-text", "--chat-text-muted",
    "--chat-border", "--chat-accent",
    "--chat-bubble-user-bg", "--chat-bubble-ai-bg", "--chat-bubble-text",
    # 以下 5 个为官方手册漏记项，实测两套主题均有定义。
    "--chat-input-bg", "--chat-input-text", "--chat-shortcut-text",
    "--chat-more-item-bg", "--chat-share-pick-bg",
)

# 沙盒模式 14 个设计令牌的预览默认值。定义在 [data-chat="root"] 上，作者换肤改变量、
# 用 var() 取色在预览里行为一致。
# 归属说明（实测）：平台真身把两套值分别定义在 [data-theme=dark] / [data-theme=light]
# 上，**没有 :root 定义**。预览这里把浅色一套放在无 data-theme 的基底规则上、深色一套
# 放在 [data-theme="dark"] 覆盖规则上，效果等价且省一份重复。
#
# 🚨 证据等级（别混淆，也别为了"好看"改回失真值）：
#   深色 14 个全部是 `【实测】` 真值，一字不改。曾经这里放的是好看但失真的值
#   （--chat-bg:#16181d、气泡 #1a7f5a/#22262c），让预览显示出"气泡有独立底色"
#   这个平台并不存在的配色 —— 作者会照着它定状态栏配色，上真机才发现整块糊在
#   背景里。这个谎发生在**设计决策阶段**，代价比"气泡默认看不见"高得多。
#   实测两个气泡背景与页面背景**同色**（都是 #17181a），预览照此还原。
#   浅色一套是 `【类推，未实测】`：探针只覆盖了深色，这里按既有浅色板与深色的
#   对应关系类推，仅作可用占位，**不要当实测事实引用**。
#   气泡默认无视觉分界的问题用预览专属描边解决（见下 data-preview-bubble-outline），
#   不靠篡改令牌取值 —— 描边一眼是辅助线，改底色是冒充平台配色。
# 🚨 --chat-viewport-height 不在那 14 个里：实测它是平台用 JS 写在 root 上的**内联
# style**（随 visualViewport 变化），不是样式表变量。预览注入它只是合理的静态模拟，
# 别把它当设计令牌统计。
# --rpx = calc(100vw / 750) 同样不计入 14 个，但它是平台全部尺寸的基准，作者按文档
# 会写 calc(24 * var(--rpx))，预览不注入就会算成 0 → 尺寸全塌。故一并注入。
# 功能栏平台不给样式，这里只给最小可见占位，作者仍需自己写背景/高度/sticky。
SANDBOX_DARK_TOKEN_VALUES = {
    # 【实测】逆向 sandbox-app.css + 真机探针。测试锁定这份取值，防回退。
    "--chat-bg": "#17181a", "--chat-surface": "#1e1f24", "--chat-text": "#fff",
    "--chat-text-muted": "#c5c5c5", "--chat-border": "#333", "--chat-accent": "#ff6d97",
    # 气泡三色 = 页面背景，实测无视觉分界。
    "--chat-bubble-user-bg": "#17181a", "--chat-bubble-ai-bg": "#17181a",
    "--chat-bubble-text": "#fff",
    "--chat-input-bg": "#1e1f24", "--chat-input-text": "#fff",
    "--chat-shortcut-text": "#fff",
    "--chat-more-item-bg": "#2c2e32", "--chat-share-pick-bg": "#2c2e32",
}

SANDBOX_CHROME_CSS = """[data-chat="root"]{--chat-bg:#ffffff;--chat-surface:#f5f6f8;--chat-text:#1f2328;
  --chat-text-muted:#6b7280;--chat-border:#d8dbe0;--chat-accent:#1a7f5a;
  --chat-bubble-user-bg:#ffffff;--chat-bubble-ai-bg:#ffffff;--chat-bubble-text:#1f2328;
  --chat-input-bg:#ffffff;--chat-input-text:#1f2328;--chat-shortcut-text:#1f2328;
  --chat-more-item-bg:#f5f6f8;--chat-share-pick-bg:#f5f6f8;
  --chat-viewport-height:100vh;--rpx:calc(100vw / 750);
  background:var(--chat-bg);color:var(--chat-text)}
[data-chat="root"][data-theme="dark"]{--chat-bg:#17181a;--chat-surface:#1e1f24;--chat-text:#fff;
  --chat-text-muted:#c5c5c5;--chat-border:#333;--chat-accent:#ff6d97;
  --chat-bubble-user-bg:#17181a;--chat-bubble-ai-bg:#17181a;--chat-bubble-text:#fff;
  --chat-input-bg:#1e1f24;--chat-input-text:#fff;--chat-shortcut-text:#fff;
  --chat-more-item-bg:#2c2e32;--chat-share-pick-bg:#2c2e32}
[data-chat="messages"]{background:var(--chat-bg)}
[data-chat="message"][data-from="ai"] [data-chat="message-body"]{background:var(--chat-bubble-ai-bg);color:var(--chat-bubble-text)}
[data-chat="message"][data-from="user"] [data-chat="message-body"]{background:var(--chat-bubble-user-bg)}
/* 预览专属辅助线，真机没有这条描边。实测气泡三色 = 页面背景（同为 #17181a），
   气泡默认与背景无视觉分界；预览若不给任何提示，作者看不出气泡边界在哪。
   这里用 var(--chat-border) 画一圈 inset 描边，只借用平台已有的边框令牌，
   **不冒充任何平台底色** —— 一眼能看出是辅助线，而不是配色主张。
   刻意挂在独立的 data-preview-bubble-outline 标记上，不混进令牌定义块，
   便于作者用开发者工具直接关掉看真实效果。 */
[data-preview-bubble-outline] [data-chat="message-body"]{box-shadow:inset 0 0 0 1px var(--chat-border)}
[data-slot="statusbar"]{position:sticky;top:0;z-index:800}
[data-chat="author-stage"]{position:fixed;inset:0;z-index:2000;background:var(--chat-bg)}
[data-chat="author-stage"][hidden]{display:none}"""


def assemble_panorama(obj, platform, src_name):
    """全景预览：所有组件在同一文档里组合显示，模拟真实 MMD 聊天页。
    底部固定输入栏（滚动不受影响）+ 发送按钮；发送追加用户气泡 + 占位AI气泡。
    沙盒模式额外把官方稳定钩子挂到同一套骨架上（见 _panorama_hooks）。"""
    sandbox = platform == "mmdsandbox"
    statusbar_html = ""
    if isinstance(obj, list):
        # 本地酒馆正则数组（无 beginning）：把各 HTML 片段堆进聊天区一条气泡。
        chat_inner = "".join("%s" % rs for _, _, rs in extract_fragments(obj, platform))
    else:
        chat_inner = apply_regex_pipeline(obj, platform)
        if sandbox:
            # 沙盒模式 statusbar 是独立的功能栏节点，不和消息正文同处一块。
            statusbar_html = _apply_pipeline_to_text(_text_field(obj, "statusbar"), obj, platform)
            chat_inner = _apply_pipeline_to_text(_text_field(obj, "beginning"), obj, platform)

    # 只对被测产物施加平台净化；测试脚手架随后拼入，避免被误当主题 script 剥离。
    tested_content = apply_platform_limits(chat_inner, platform)
    hooks = _panorama_hooks(platform)
    hoisted = ""
    if sandbox:
        # 装卡即抽出的 style/script，与匹配无关，整张卡只装一次。
        assets = collect_sandbox_assets(obj)
        if assets:
            hoisted = ('<div data-preview-hoisted="1">%s</div>'
                       % apply_platform_limits(assets, platform))
    statusbar_node = ""
    if sandbox and statusbar_html.strip():
        # 角色卡 statusbar 留空 → 平台上这个节点整块不存在，预览照此处理。
        statusbar_node = ('<div data-slot="statusbar" class="pano-statusbar">%s</div>'
                          % apply_platform_limits(statusbar_html, platform))
    page = (
        '%(runtime)s'
        '%(hoisted)s'
        '<div class="page"%(root)s>'
        '<div class="topTabbar"%(header)s><span%(header_title)s>MMD Chat Preview</span>'
        '<span class="pano-route-label">chat/chat</span>%(header_extra)s</div>'
        '%(statusbar)s'
        '<div class="chat chat-bg pano-chat" id="pano-chat"%(messages)s>'
        '<div class="chat-body"%(list)s>'
        '<div class="item" data-message-role="user"%(frame)s><div class="touch-scope"%(msg_user)s>'
        '<div class="content right"%(body)s>用户示例消息</div></div></div>'
        '<div class="item" data-message-role="ai"%(frame)s><div class="touch-scope"%(msg_ai)s>'
        '<div class="content left"%(body)s>%(tested)s</div></div></div>'
        '</div></div>'
        '%(stage)s'
        '<div class="chat-bottom chat-input-scope pano-input-bar"%(composer)s>'
        '<textarea class="uni-textarea-textarea" rows="1" '
        'placeholder="输入消息（Enter 发送，Shift+Enter 换行）"%(input)s></textarea>'
        '<button class="pano-send send-msg" type="button"%(send)s>发送</button>'
        '</div>'
        '</div>'
        '%(sendscaffold)s'
    ) % dict(hooks, runtime=PANORAMA_RUNTIME_SCAFFOLD, tested=tested_content,
             statusbar=statusbar_node, hoisted=hoisted,
             sendscaffold=PANORAMA_SEND_SCAFFOLD)

    chrome_css = SANDBOX_CHROME_CSS if sandbox else ""
    frame_doc = "<style>%s</style><style>%s</style><style>%s</style>%s" % (
        MARKER_CSS, PANORAMA_CSS, chrome_css, page)
    srcdoc = html_mod.escape(frame_doc, quote=True)

    n = _script_count(obj)
    banner = make_banner(platform, src_name, n).replace("预览平台", "全景预览 ｜ 平台")
    audit = _findregex_audit_html(obj, platform) + _onclick_audit_html(chat_inner, platform)
    if sandbox:
        audit += ('<div class="frag-warn">NOTE 已模拟：[data-chat]/[data-slot] 钩子结构与 14 个 '
                  '--chat-* 设计令牌默认值（深色一套为实测真值；官方手册只记 10 个），另注入 '
                  '--rpx 尺寸基准与 --chat-viewport-height 静态值（后者真机是 JS 内联 style，'
                  '不属那 14 个），作者的平台选择器与 var() 在此可解析。'
                  '</div>'
                  '<div class="frag-warn">NOTE 气泡那圈淡描边是<b>预览辅助线，真机上没有</b>：'
                  '实测平台气泡三色与页面背景<b>同色</b>（深色都是 #17181a），气泡默认与背景'
                  '无视觉分界。想要卡片感必须自己给底色（比如 var(--chat-surface)），'
                  '别以为平台已经帮你把气泡分出来了。要看真实效果：删掉 root 上的 '
                  'data-preview-bubble-outline 属性。'
                  '未模拟：官方 SDK（sdk.on/stage/save/message 等全部不存在）、'
                  '「消息生成中」占位、净化白名单、Markdown 管线、真实换肤与限频。'
                  'SDK 相关行为必须回真实聊天页验证。</div>')
    if isinstance(obj, dict):
        audit += "".join('<div class="frag-warn">ERROR 悬空标记：%s</div>' % html_mod.escape(x)
                         for x in find_dangling_markers(obj, platform))
    body = (
        '<div class="frag"><div class="frag-label">全景预览（所有组件组合 · 固定输入框 · 发送测试）</div>'
        '<div class="preview-tools" data-preview-tools="1"><span class="preview-tools-label">预览测试工具</span>'
        '<button class="preview-tool" type="button" title="追加动态 AI 内容" '
        'onclick="document.querySelector(\'.pano-frame\').contentWindow.__tavernPreview.addAI()">追加 AI</button>'
        '<button class="preview-tool" type="button" title="模拟离开聊天页" '
        'onclick="document.querySelector(\'.pano-frame\').contentWindow.__tavernPreview.leave()">离开聊天页</button>'
        '<button class="preview-tool" type="button" title="模拟返回聊天页" '
        'onclick="document.querySelector(\'.pano-frame\').contentWindow.__tavernPreview.returnToChat()">返回聊天页</button>'
        '</div>'
        '<iframe class="pano-frame" srcdoc="%s" sandbox="allow-scripts allow-same-origin"></iframe>'
        '</div>%s' % (srcdoc, audit)
    )
    return PANORAMA_PAGE_TEMPLATE % {"platform": platform, "banner": banner,
                                     "body": body, "marker_css": MARKER_CSS}


def assemble_html(frags, platform, src_name, audit=""):
    """把所有HTML片段拼进一个预览页。每个片段包进独立 iframe srcdoc，
    隔离 CSS/ID 作用域，模拟 MMD 每条消息独立气泡（防跨片段污染）。"""
    body_parts = []
    for name, fr, rs in frags:
        processed = apply_platform_limits(rs, platform)
        # 标记 CSS 随片段注入子文档（iframe 不继承父文档样式）
        frame_doc = "<style>%s</style>%s" % (MARKER_CSS, processed)
        srcdoc = html_mod.escape(frame_doc, quote=True)
        # 空白条风险警告（仅 MMD 系平台关心；标签间裸换行会被补成空<p>）
        warn_row = ""
        if platform == "mmd" and detect_blank_bar_risk(rs):
            warn_row = ('<div class="frag-warn">⚠ 检测到标签间裸换行——'
                        'MMD markdown 管线会补成空&lt;p&gt;撑出横向空白条；'
                        '注入HTML请压成单行无换行（预览看不出此问题，详见 statusbar-radar.md）</div>')
        body_parts.append(
            '<div class="frag"><div class="frag-label">规则: %s （findRegex: %s）</div>%s'
            '<iframe class="frag-frame" srcdoc="%s" sandbox="allow-scripts allow-same-origin" '
            'onload="this.style.height=this.contentWindow.document.body.scrollHeight+20+\'px\'">'
            '</iframe></div>'
            % (html_mod.escape(name), html_mod.escape(fr), warn_row, srcdoc))
    body = "\n".join(body_parts) + audit
    banner = make_banner(platform, src_name, len(frags))
    return PAGE_TEMPLATE % {"platform": platform, "banner": banner,
                            "body": body, "marker_css": MARKER_CSS}


def apply_platform_limits(rs, platform):
    """按平台改写 HTML；当前 MMD 额外禁用 allowlist 外的真实 inline onclick。
    沙盒模式不净化 onclick（普通标签 onclick 合法），<script> 同样保留并标角标。"""
    if platform == "st":
        return rs

    out = rs
    if platform == "mmd":
        out, _removed = sanitize_mmd_onclick(out)

    # <script>...</script>：mmd 与沙盒模式都放行，保留并标黄角标标明正常执行。
    badge_title = ("沙盒模式 <script> 是一等公民，装卡即抽出、整张卡只跑一次"
                   if platform == "mmdsandbox" else "当前MMD已确认支持 script，正常执行")

    def script_repl(m):
        return ('<div class="mmd-warn-badge" title="%s">✓script</div>'
                % html_mod.escape(badge_title, quote=True)) + m.group(0)
    out = re.sub(r"<script\b[\s\S]*?</script>", script_repl, out, flags=re.I)
    return out


def make_banner(platform, src_name, n):
    labels = {"st": "本地酒馆 SillyTavern（无限制渲染）",
              "mmd": "当前MMD（支持script/ES6）",
              "mmdsandbox": "MMD沙盒模式（新聊天页 chatVersion:1；支持script/官方SDK）"}
    return ('<div class="banner banner-%s">预览平台: %s ｜ 来源: %s ｜ %d 个HTML片段</div>'
            % (platform, labels.get(platform, platform), html_mod.escape(src_name), n))


# 平台限制标记的 CSS（onclick 禁用描边/黄角标）。父文档与每个 iframe 子文档都要注入，
# 否则 apply_platform_limits 生成的标记元素在 iframe 里无样式（iframe 不继承父文档 CSS）。
MARKER_CSS = """[data-mmd-onclick-disabled]{outline:2px solid #f85149 !important;outline-offset:1px}
[data-mmd-onclick-disabled]::after{content:'onclick disabled';font-size:9px;background:#f85149;color:#fff;padding:1px 4px}
.mmd-warn-badge{display:inline-block;background:#d29922;color:#000;font-size:10px;padding:1px 6px;border-radius:3px;margin:2px}"""


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tavern-mmd 预览 [%(platform)s]</title>
<style>
body{margin:0;background:#0d1117;color:#e6edf3;font-family:system-ui,sans-serif}
.banner{padding:10px 16px;font-size:13px;font-weight:600;position:sticky;top:0;z-index:9999}
.banner-st{background:#1f6feb}.banner-mmd{background:#9e6a03}.banner-mmdsandbox{background:#1a7f5a}
.frag{margin:16px;padding:0;border:1px dashed #30363d;border-radius:8px;overflow:hidden}
.frag-label{background:#161b22;color:#8b949e;font-size:11px;padding:6px 12px;border-bottom:1px solid #30363d}
.frag-warn{background:#3a2d00;color:#f0c674;font-size:11px;padding:6px 12px;border-bottom:1px solid #30363d}
%(marker_css)s
.frag-frame{width:100%%;border:0;display:block;background:#fff;min-height:80px}
</style></head>
<body>
%(banner)s
%(body)s
</body></html>"""


def _build_panels_html(obj, platform, src_name):
    """三面板诊断（MMD导入json）或逐片段iframe（本地酒馆数组）。返回 (html, 片段数)。"""
    if isinstance(obj, dict) and "regex_scripts" in obj and ("beginning" in obj or "statusbar" in obj):
        return assemble_preview(obj, platform, src_name), _script_count(obj)
    frags = extract_fragments(obj, platform)
    if not frags:
        print("[WARN] 未找到含HTML的替换片段（可能是纯数据转换器）。")
    rendered = "".join(rs for _name, _fr, rs in frags)
    return assemble_html(frags, platform, src_name,
                         _findregex_audit_html(obj, platform) + _onclick_audit_html(rendered, platform)), len(frags)


def main():
    p = argparse.ArgumentParser(description="tavern-mmd 平台预览生成")
    p.add_argument("file")
    p.add_argument("--platform", choices=["mmd", "mmdsandbox", "st"], required=True)
    p.add_argument("--mode", choices=["panels", "panorama", "both"], default="both",
                   help="panels=三面板诊断；panorama=单页全景(模拟MMD聊天页)；both=两者都生成(默认)")
    p.add_argument("-o", "--output", help="输出HTML路径。仅单一 mode 时生效；both 模式忽略并按默认名各产一份")
    args = p.parse_args()

    try:
        obj = load(args.file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        print("[ERROR] 读取/解析失败: %s" % e)
        print("提示: 先用 validate.py 确认 JSON 合法。")
        sys.exit(2)

    findings = fatal_preview_findings(obj, args.platform)
    unsupported = find_unsupported_preview_regexes(obj, args.platform)
    if args.platform in ("mmd", "mmdsandbox") and not _js_regex_oracle_available():
        print("[WARN] 未找到可用 Node.js；findRegex 仅执行结构 fallback，未经过真实 JS RegExp oracle。")
    for message in findings["structure"]:
        print("[ERROR] 非法结构: %s" % message)
    if findings["findRegex"]:
        print("[ERROR] 非法 findRegex: %s" %
              ", ".join("%s=%s (%s)" % x for x in findings["findRegex"]))
    for body, reason in findings["onclick"]:
        print("[ERROR] inline onclick 会被当前MMD净化: %s (%s)" % (body, reason))
    if unsupported:
        print("[WARN] 预览器不支持此 JS 正则: %s" %
              ", ".join("%s=%s (%s)" % x for x in unsupported))
    if findings["dangling"]:
        print("[ERROR] 悬空标记: %s" % ", ".join(findings["dangling"]))
    if any(findings.values()):
        sys.exit(1)

    outputs = []
    if args.mode in ("panels", "both"):
        panels_html, frags_count = _build_panels_html(obj, args.platform, args.file)
        path = args.output if (args.output and args.mode == "panels") else \
            _default_output_path(args.file, "preview", args.platform)
        outputs.append((path, panels_html, "片段数: %d  平台: %s  模式: 三面板诊断" %
                        (frags_count, args.platform)))

    if args.mode in ("panorama", "both"):
        pano_html = assemble_panorama(obj, args.platform, args.file)
        path = args.output if (args.output and args.mode == "panorama") else \
            _default_output_path(args.file, "panorama", args.platform)
        outputs.append((path, pano_html,
                        "全景预览  平台: %s  （固定输入框+发送+占位AI气泡，所有组件组合显示）" %
                        args.platform))

    for path, content, summary in outputs:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print("[OK] 预览已生成: %s" % path)
        print(summary)

    if args.mode == "both":
        print("工作流：先看三面板审核单组件 → 再看全景二次审核组合效果（全景不默认关闭，留给你自查）。")
    print("请用浏览器或 Preview 工具打开查看渲染与交互。")


if __name__ == "__main__":
    main()
