#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 预览脚本 build-preview.py
把状态栏/美化正则的 replaceString 拼成完整 HTML 沙箱文件，按平台注入渲染限制。
主AI 用自带 Preview 工具打开看渲染、测交互（子代理无法与渲染工具交互）。

用法:
  python build-preview.py <文件> --platform <oldmmd|mmd|st> [--mode panels|panorama|both] [-o 输出.html]

平台渲染差异:
  st     : 原样渲染，<script>/ES6 全执行
  oldmmd : <script>剥离并裸露源码(红框)；onerror/onclick 内 ES6 标红提示真实旧版会截断
  mmd    : <script>/ES6 全执行（已确认支持）；script 加"✓script"角标标明正常执行

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


def _mmd_top_level_error(obj, platform):
    if platform not in ("oldmmd", "mmd"):
        return None
    errors = _mmd_regex_top_level_errors(obj)
    return errors[0] if errors else None


def find_structure_errors(obj, platform):
    if platform not in ("oldmmd", "mmd"):
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
        if platform in ("oldmmd", "mmd") and raw_fr not in ("", None):
            if not isinstance(raw_fr, str) or _js_regex_structure_error(raw_fr):
                continue
            regex, _flags, reason = _compile_js_regex_for_preview(raw_fr)
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
    """返回真正的 MMD 结构/JS dialect 错误；不含预览器能力限制。"""
    if platform not in ("oldmmd", "mmd"):
        return []
    invalid = []
    for i, sc in enumerate(_script_list(obj)):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        if fr in ("", None):
            continue
        reason = "findRegex 必须是字符串" if not isinstance(fr, str) else _js_regex_structure_error(fr)
        if reason:
            name = sc.get("scriptName", sc.get("name", "#%d" % i))
            invalid.append((str(name), str(fr), reason))
    return invalid


def find_unsupported_preview_regexes(obj, platform):
    """返回 JS 结构合法、但 Python 预览后端无法可靠模拟的规则。"""
    if platform not in ("oldmmd", "mmd"):
        return []
    unsupported = []
    for i, sc in enumerate(_script_list(obj)):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        if not isinstance(fr, str) or not fr or _js_regex_structure_error(fr):
            continue
        regex, _flags, reason = _compile_js_regex_for_preview(fr)
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


def apply_regex_pipeline(obj, platform=None):
    """模拟 JS 替换管线；MMD 系跳过结构错误和预览器不支持规则。"""
    if _mmd_top_level_error(obj, platform):
        return ""
    if isinstance(obj, list):
        return ""
    text = _text_field(obj, "statusbar") + _text_field(obj, "beginning")
    for sc in _script_list(obj):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        rs = sc.get("replaceString", "")
        if not isinstance(fr, str) or not isinstance(rs, str) or not fr:
            continue
        if platform not in ("oldmmd", "mmd") and not fr.startswith("/"):
            text = text.replace(fr, rs)
            continue
        if _js_regex_structure_error(fr):
            if platform not in ("oldmmd", "mmd"):
                text = text.replace(fr, rs)
            continue
        regex, js_flags, reason = _compile_js_regex_for_preview(fr)
        if regex is None or reason:
            continue
        text = _replace_js_regex(text, regex, js_flags, rs)
    return text


def find_dangling_markers(obj, platform=None):
    """管线可完整模拟时，扫描每个自定义开始/结束标记 occurrence。"""
    if isinstance(obj, list) or find_unsupported_preview_regexes(obj, platform):
        return []
    rendered = apply_regex_pipeline(obj, platform)
    return [marker for marker, _pos in _custom_marker_occurrences(rendered)]


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


def _onclick_audit_html(content, platform, label="最终输出"):
    if platform != "mmd" or not isinstance(content, str):
        return ""
    _cleaned, removed = sanitize_mmd_onclick(content)
    return "".join(
        '<div class="frag-warn">ERROR inline onclick 已禁用：%s（%s；%s）</div>'
        % (html_mod.escape(label), html_mod.escape(body), html_mod.escape(reason))
        for body, reason in removed
    )


def find_invalid_onclicks(obj, platform):
    """只审计实际进入最终渲染文本的 inline onclick；未命中替换不误报。"""
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


def _html_to_srcdoc(content, platform):
    processed = apply_platform_limits(content, platform)
    frame_doc = "<style>%s</style>%s" % (MARKER_CSS, processed)
    return html_mod.escape(frame_doc, quote=True)


def _panel(title, content, platform, badge=""):
    label = "%s%s" % (html_mod.escape(title), (" <span class=\"badge\">%s</span>" % html_mod.escape(badge)) if badge else "")
    if not content:
        return '<div class="frag"><div class="frag-label">%s</div><div class="frag-warn">（无内容）</div></div>' % label
    return ('<div class="frag"><div class="frag-label">%s</div>'
            '<iframe class="frag-frame" srcdoc="%s" sandbox="allow-scripts allow-same-origin" '
            'onload="this.style.height=this.contentWindow.document.body.scrollHeight+20+\'px\'">'
            '</iframe></div>' % (label, _html_to_srcdoc(content, platform)))


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


def _event_tag_has_es6(tag):
    for m in re.finditer(r"\bon\w+\s*=\s*([\"'])([\s\S]*?)\1", tag, re.I):
        body = m.group(2)
        if re.search(r"=>|\blet\b|\bconst\b|`", body):
            return True
    return False


def _add_attr_to_tag(tag, attr_text):
    if tag.endswith("/>"):
        return tag[:-2] + " " + attr_text + "/>"
    return tag[:-1] + " " + attr_text + ">"


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
    body = "\n".join([
        _panel("第一句话剩余预览", first, platform, "beginning remainder"),
        _panel("状态栏单独预览", status, platform, "status"),
        _panel("悬浮组件预览", floating, platform, "floating/sidebar"),
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
.banner-st{background:#1f6feb}.banner-mmd{background:#9e6a03}.banner-oldmmd{background:#6e1423}
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
    "function add(side,text){var root=chat();if(!root)return null;"
    "var it=D.createElement('div');it.className='item';it.setAttribute('data-preview-dynamic','1');"
    "var touch=D.createElement('div');touch.className='touch-scope';"
    "var ct=D.createElement('div');ct.className='content '+side;ct.textContent=text;"
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


def assemble_panorama(obj, platform, src_name):
    """全景预览：所有组件在同一文档里组合显示，模拟真实 MMD 聊天页。
    底部固定输入栏（滚动不受影响）+ 发送按钮；发送追加用户气泡 + 占位AI气泡。"""
    if isinstance(obj, list):
        # 本地酒馆正则数组（无 beginning）：把各 HTML 片段堆进聊天区一条气泡。
        chat_inner = "".join("%s" % rs for _, _, rs in extract_fragments(obj, platform))
    else:
        chat_inner = apply_regex_pipeline(obj, platform)

    # 只对被测产物施加平台净化；测试脚手架随后拼入，避免被误当主题 script 剥离。
    tested_content = apply_platform_limits(chat_inner, platform)
    page = (
        '%s'
        '<div class="page">'
        '<div class="topTabbar"><span>MMD Chat Preview</span><span class="pano-route-label">chat/chat</span></div>'
        '<div class="chat chat-bg pano-chat" id="pano-chat">'
        '<div class="chat-body">'
        '<div class="item" data-message-role="user"><div class="touch-scope"><div class="content right">用户示例消息</div></div></div>'
        '<div class="item" data-message-role="ai"><div class="touch-scope"><div class="content left">%s</div></div></div>'
        '</div></div>'
        '<div class="chat-bottom chat-input-scope pano-input-bar">'
        '<textarea class="uni-textarea-textarea" rows="1" placeholder="输入消息（Enter 发送，Shift+Enter 换行）"></textarea>'
        '<button class="pano-send send-msg" type="button">发送</button>'
        '</div>'
        '</div>'
        '%s'
    ) % (PANORAMA_RUNTIME_SCAFFOLD, tested_content, PANORAMA_SEND_SCAFFOLD)

    frame_doc = "<style>%s</style><style>%s</style>%s" % (MARKER_CSS, PANORAMA_CSS, page)
    srcdoc = html_mod.escape(frame_doc, quote=True)

    n = _script_count(obj)
    banner = make_banner(platform, src_name, n).replace("预览平台", "全景预览 ｜ 平台")
    audit = _findregex_audit_html(obj, platform) + _onclick_audit_html(chat_inner, platform)
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
        if platform in ("oldmmd", "mmd") and detect_blank_bar_risk(rs):
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
    """按平台改写 HTML；当前 MMD 额外禁用 allowlist 外的真实 inline onclick。"""
    if platform == "st":
        return rs

    out = rs
    if platform == "mmd":
        out, _removed = sanitize_mmd_onclick(out)

    # 1. <script>...</script>：oldmmd 剥离并裸露源码；mmd 保留但标黄
    def script_repl(m):
        full = m.group(0)
        if platform == "oldmmd":
            return '<pre class="mmd-stripped">%s</pre>' % html_mod.escape(full)
        else:  # mmd
            return '<div class="mmd-warn-badge" title="当前MMD已确认支持 script，正常执行">✓script</div>' + full
    out = re.sub(r"<script\b[\s\S]*?</script>", script_repl, out, flags=re.I)

    # 2. onerror/onclick 内 ES6 语法：旧版MMD真实平台不支持，会截断；预览只标黄提示。
    if platform == "oldmmd":
        parts = []
        pos = 0
        for start, end, tag in _iter_all_tags(out):
            if re.search(r"\bon\w+\s*=", tag, re.I) and _event_tag_has_es6(tag):
                parts.append(out[pos:start])
                parts.append(_add_attr_to_tag(tag, 'data-mmd-es6="真实旧版MMD不支持ES6，此处会截断"'))
                pos = end
        if parts:
            parts.append(out[pos:])
            out = "".join(parts)

    return out


def make_banner(platform, src_name, n):
    labels = {"st": "本地酒馆 SillyTavern（无限制渲染）",
              "mmd": "当前MMD（支持script/ES6）",
              "oldmmd": "旧版MMD（禁script/ES5）"}
    return ('<div class="banner banner-%s">预览平台: %s ｜ 来源: %s ｜ %d 个HTML片段</div>'
            % (platform, labels.get(platform, platform), html_mod.escape(src_name), n))


# 平台限制标记的 CSS（红框源码/ES6描边/黄角标）。父文档与每个 iframe 子文档都要注入，
# 否则 apply_platform_limits 生成的标记元素在 iframe 里无样式（iframe 不继承父文档 CSS）。
MARKER_CSS = """.mmd-stripped{display:block;margin:8px;padding:10px;border:2px solid #f85149;border-radius:6px;
  background:#2d0a0a;color:#ff7b72;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-all}
.mmd-stripped::before{content:'⚠ 旧版MMD会剥离此标签，不执行（源码裸露）：';display:block;color:#f85149;margin-bottom:6px;font-weight:600}
[data-mmd-es6]{outline:2px solid #d29922 !important;outline-offset:1px;position:relative}
[data-mmd-es6]::after{content:'⚠ES6:'attr(data-mmd-es6);position:absolute;top:-8px;right:0;background:#d29922;color:#000;font-size:9px;padding:1px 4px;border-radius:3px;z-index:99}
[data-mmd-onclick-disabled]{outline:2px solid #f85149 !important;outline-offset:1px}
[data-mmd-onclick-disabled]::after{content:'onclick disabled';font-size:9px;background:#f85149;color:#fff;padding:1px 4px}
.mmd-warn-badge{display:inline-block;background:#d29922;color:#000;font-size:10px;padding:1px 6px;border-radius:3px;margin:2px}"""


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tavern-mmd 预览 [%(platform)s]</title>
<style>
body{margin:0;background:#0d1117;color:#e6edf3;font-family:system-ui,sans-serif}
.banner{padding:10px 16px;font-size:13px;font-weight:600;position:sticky;top:0;z-index:9999}
.banner-st{background:#1f6feb}.banner-mmd{background:#9e6a03}.banner-oldmmd{background:#6e1423}
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
    p.add_argument("--platform", choices=["oldmmd", "mmd", "st"], required=True)
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
    if args.platform in ("oldmmd", "mmd") and not _js_regex_oracle_available():
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
