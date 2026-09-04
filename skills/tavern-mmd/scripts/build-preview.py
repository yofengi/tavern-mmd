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
               交付 findRegex 统一 /pattern/flags（约定）；裸字面量实机也生效（卡 64304 A/B
               2026-08-30），预览按 worker m() 转义后照常渲染，只有语法错的 /…/ 整条静默丢弃
               不施加当前MMD 的 onclick 净化；改为提示 svg 内 onclick 与自写 data-* 会被净化删除
               <style>/<script> 装卡即抽出，不论规则有没有匹配到都装上
               全景模式复刻真实 dark chat flex 外壳、稳定槽位与 14 个 --chat-* 设计令牌，
               注入 --rpx，并以 root 内联 --chat-viewport-height 跟随 iframe resize

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


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SANDBOX_CONTRACT_PATH = os.path.join(_SCRIPT_DIR, "fixtures", "mmdsandbox", "contract.json")
SANDBOX_SIM_PATH = os.path.join(_SCRIPT_DIR, "mmdsandbox-sim.js")
SANDBOX_PROFILES = ("chat", "thin-preview")
_SANDBOX_CACHE = {}


def load_sandbox_contract():
    """读共享契约（fixtures/mmdsandbox/contract.json）。预览与模拟器共用一份真相。"""
    if "contract" not in _SANDBOX_CACHE:
        with open(SANDBOX_CONTRACT_PATH, encoding="utf-8") as f:
            _SANDBOX_CACHE["contract"] = json.load(f)
    return _SANDBOX_CACHE["contract"]


def load_sandbox_sim_source():
    """读经典脚本模拟器源码，内联进全景（零外部请求，file:// 直开也能跑）。"""
    if "sim" not in _SANDBOX_CACHE:
        with open(SANDBOX_SIM_PATH, encoding="utf-8") as f:
            _SANDBOX_CACHE["sim"] = f.read()
    return _SANDBOX_CACHE["sim"]


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
    """复刻 worker 源码 classifyPattern：返回 (kind, value, reason)。
    kind 取 empty / literal / regex / bad-regex。
    literal 时 value 是待字面量替换的串；regex 时 value 是规范化后的 /pattern/flags。

    worker 源码有 literal 分支（`if(!n)return new RegExp(m(t),'g')`，见事实卡 §5.1），
    `【实机实测 2026-08-30】`（卡 64304 A/B）确认裸字面量**生效**：裸 `体力` 与 `/灵力/`
    在真实聊天页同一轮渲染都被替换（事实卡 §8.21），宿主包只把 pattern 原样转发。
    → 两种形态预览都要渲染；literal 走 m() 等价转义后当全文替换。"""
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


def sandbox_pattern_delivery_error(raw):
    """沙盒**交付**门禁：只拦真正会静默失效的形态，返回错误原因，合规返回 None。

    与 classify_sandbox_pattern（worker 源码分类）分开：那个解释 worker 怎么想，这个决定
    预览/交付放不放行。裸字面量实机生效（卡 64304 A/B 2026-08-30），不拦；只有「写成 /…/
    但正则语法错」才判错（整条静默丢弃）。"""
    if not isinstance(raw, str):
        return "findRegex 必须是字符串"
    kind, _value, reason = classify_sandbox_pattern(raw)
    if kind == "bad-regex":
        return "写成 /…/ 但正则语法错，平台会整条静默丢弃（%s）" % reason
    return None                          # empty 由必填校验管；literal 实机生效，照渲染


def _worker_m_escape(literal):
    """复刻 worker 的 m()：转义正则元字符 `[.*+?^${}()|[\\]\\]`，使字面量按原文匹配。"""
    return re.sub(r"([.*+?^${}()|\[\]\\])", r"\\\1", literal)


def sandbox_delivery_regex(raw):
    """交付形态下用于预览替换的规范化 /pattern/flags；不合规返回 None。

    literal 复刻 worker `new RegExp(m(t),'g')`：元字符转义后当全文字面量替换。"""
    if sandbox_pattern_delivery_error(raw):
        return None
    kind, value, _reason = classify_sandbox_pattern(raw)
    if kind == "regex":
        return value
    if kind == "literal":
        return "/%s/g" % _escape_for_slash_literal(_worker_m_escape(value))
    return None


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
            # 裸字面量与 /…/ 都渲染（实机裸字面量生效）；只有语法错的 /…/ 被丢弃。
            if sandbox_pattern_delivery_error(raw_fr):
                continue
            value = sandbox_delivery_regex(raw_fr)
            if value:
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
            reason = sandbox_pattern_delivery_error(fr)
            if not reason:
                continue
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
            value = sandbox_delivery_regex(fr)
            if not value:
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
            # 🚨 只有 slash 形态才会生效。裸字面量在实机上不触发，预览**绝不能**替换它，
            # 否则作者在预览里看到内容出现、上真机却什么都没有（最坏的那种谎）。
            # 语法错的 /…/ 同样不替换（平台整条静默丢弃）。
            value = sandbox_delivery_regex(fr)
            if value:
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
                       "data-preview-hoisted", "data-preview-bubble-outline",
                       "data-preview-sim", "data-preview-accuracy",
                       "data-preview-bucket")


# SAFE_FOR_XML 危险形态（事实卡 §5.5 逐字判据）：属性值命中即整条属性被删，
# 且发生在 on* 强留之前 → 连 onclick 都保不住。
_SANDBOX_SAFE_FOR_XML = re.compile(
    r"((--!?|\])>)|</(style|script|title|xmp|textarea|noscript|iframe|noembed|noframes)",
    re.I)
# 非白名单标签会被正则剥壳（文字保留）。
_SANDBOX_STRIPPED_TAGS = ("iframe", "link", "meta", "form", "object", "embed")


def find_sandbox_sanitized_attrs(content):
    """已确证的沙盒净化子集。返回 [(种类, 详情)]；权威检查在 validate.py。

    覆盖：作者自写 data-*、aria-*/role、SVG 内 on*、禁用标签、SAFE_FOR_XML 危险属性值。
    每项都有实机或源码依据（事实卡 §5.5）；未确证项不进这里。"""
    if not isinstance(content, str):
        return []
    found = []
    svg_ranges = _svg_ranges(content)
    for start, end, tag in _iter_all_tags(content):
        in_svg = any(s <= start < e for s, e in svg_ranges)
        # SVG 内所有 on*（不只 onclick）都被删；HTML 元素上的 on* 全部保留。
        if in_svg:
            m_on = re.search(r"\bon[a-z]+\s*=", tag, re.I)
            if m_on:
                found.append(("svg-on-attr", "%s（%s）" % (m_on.group(0).rstrip("= "), tag[:80])))
        name_match = re.match(r"</?\s*([a-zA-Z][a-zA-Z0-9]*)", tag)
        if name_match and name_match.group(1).lower() in _SANDBOX_STRIPPED_TAGS:
            found.append(("stripped-tag", "%s（%s）" % (name_match.group(1).lower(), tag[:80])))
        for m in re.finditer(r'\b(data-[a-zA-Z0-9_-]+)\s*=', tag):
            name = m.group(1).lower()
            if name in _PLATFORM_DATA_ATTRS or name in _PREVIEW_DATA_ATTRS:
                continue
            found.append(("author-data-attr", "%s（%s）" % (m.group(1), tag[:80])))
        for m in re.finditer(r'\b(aria-[a-zA-Z0-9_-]+|role)\s*=', tag):
            found.append(("aria-or-role", "%s（%s）" % (m.group(1), tag[:80])))
        for m in re.finditer(r'\b([a-zA-Z_:][-\w:.]*)\s*=\s*"([^"]*)"', tag):
            if _SANDBOX_SAFE_FOR_XML.search(html_mod.unescape(m.group(2))):
                found.append(("safe-for-xml", "%s（%s）" % (m.group(1), tag[:80])))
    return found


_SANDBOX_SANITIZE_MESSAGES = {
    "svg-on-attr": "svg 内的 on* 会被沙盒净化删除（实测 &lt;circle onclick&gt; 被删）"
                   "——交互改挂 HTML 壳，或用 sdk.on('message:mount') 绑定",
    "author-data-attr": "作者自写 data-* 会被沙盒净化删除（实测 data_mine=null）"
                        "——自己的节点改用 class 或 id",
    "aria-or-role": "aria-* 与 role 会被沙盒净化删除（ALLOW_ARIA_ATTR 为关）"
                    "——属平台限制而非卡片缺陷，语义靠原生标签承载",
    "stripped-tag": "该标签不在沙盒白名单内，会被正则剥壳（文字保留、标签消失）",
    "safe-for-xml": "属性值命中 SAFE_FOR_XML 危险形态（]&gt; / --&gt; / --!&gt; / &lt;/style 等），"
                    "**整条属性被删**，且发生在 on* 强留之前 → 连 onclick 都保不住。"
                    "比较运算符两侧留空格即可规避",
}


def _sandbox_sanitize_audit_html(content, label="最终输出"):
    rows = []
    for kind, detail in find_sandbox_sanitized_attrs(content):
        message = _SANDBOX_SANITIZE_MESSAGES.get(kind, "会被沙盒净化处理")
        rows.append('<div class="frag-warn">WARN %s：%s（%s）</div>'
                    % (message, html_mod.escape(label), html_mod.escape(detail)))
    return "".join(rows)


SANDBOX_OUTPUT_BUDGET_FLOOR = 262144
SANDBOX_OUTPUT_BUDGET_INPUT_MULTIPLIER = 4


def sandbox_output_budget(input_length):
    """单条规则输出预算：max(262144, 输入长度×4)（事实卡 §5.2 逐字常量）。"""
    return max(SANDBOX_OUTPUT_BUDGET_FLOOR,
               int(input_length) * SANDBOX_OUTPUT_BUDGET_INPUT_MULTIPLIER)


def find_sandbox_budget_findings(obj, platform):
    """输出预算与空串匹配。两者都令**整条规则回滚**：页面上这条完全不生效，只留告警。
    返回 [(规则名, 种类, 说明)]，种类取 replacement-alone / empty-match。"""
    if platform != "mmdsandbox" or not isinstance(obj, dict):
        return []
    input_text = _text_field(obj, "statusbar") + _text_field(obj, "beginning")
    budget = sandbox_output_budget(len(input_text))
    out = []
    for i, sc in enumerate(_script_list(obj)):
        if not isinstance(sc, dict):
            continue
        name = str(sc.get("scriptName", sc.get("name", "#%d" % i)))
        rs = sc.get("replaceString")
        fr = sc.get("findRegex")
        if isinstance(rs, str) and len(rs) > budget:
            out.append((name, "replacement-alone",
                        "replaceString 单条 %d 字，超过输出预算 %d（=max(262144, 输入长度×4)）"
                        % (len(rs), budget)))
        if not isinstance(fr, str) or sandbox_pattern_delivery_error(fr):
            continue
        regex, _flags, reason = _compile_js_regex_for_preview(re.sub(r"^`|`$", "", fr.strip()))
        if regex is None or reason:
            continue
        if regex.search(""):
            out.append((name, "empty-match",
                        "匹配式能匹配空串——每个位置都插一次替换内容，瞬间撑爆预算"))
    return out


def _sandbox_budget_audit_html(obj, platform):
    return "".join(
        '<div class="frag-warn">ERROR 规则整条回滚（%s）：规则 %s——%s。'
        '页面上这条<b>完全不生效</b>，只留告警。</div>'
        % (html_mod.escape(kind), html_mod.escape(name), html_mod.escape(detail))
        for name, kind, detail in find_sandbox_budget_findings(obj, platform))


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
    if platform == "mmd":
        # 三面板也要有平台底子：否则单组件诊断阶段查不出空白条、var(--*) 解析为空、
        # rem 尺寸按 16px 算而非随宽缩放 —— 而 checklist 的工作流是"先三面板审单组件"，
        # 第一步没有平台底子等于白审。用扁平壳（无顶栏/底栏/弹窗，见 §面板壳）。
        frame_doc = "<style>%s</style><style>%s</style>%s%s" % (
            MARKER_CSS, _mmd_panel_shell_css(), extra,
            _wrap_in_mmd_bubble(processed))
    else:
        frame_doc = "<style>%s</style>%s%s" % (MARKER_CSS, extra, processed)
    return html_mod.escape(frame_doc, quote=True)


def _wrap_in_mmd_bubble(inner):
    """把被测片段裹进真实气泡容器链，让作者写的深选择器在三面板里也能命中。

    真机链是 `.chat > .chat-scope-box > .scroll-view > .uni-scroll-view-content >
    .chat-body > .item.Ai > .touch-scope > .content.left`。三面板是自动撑高的诊断
    iframe，所以壳 CSS 里把 `.chat-scope-box/.scroll-view` 改成静态流（见
    `_mmd_panel_shell_css`），层级与类名保持一致。"""
    return (
        '<uni-view class="chat"><uni-view class="chat-scope-box">'
        '<uni-scroll-view class="scroll-view dark">'
        '<div class="uni-scroll-view"><div class="uni-scroll-view-content">'
        '<uni-view class="chat-body" id="msglistview">'
        '<uni-view><uni-view class="item Ai">'
        '<uni-view class="touch-scope"><uni-view class="content left">'
        '%s'
        '</uni-view></uni-view></uni-view></uni-view>'
        '</uni-view></div></div></uni-scroll-view>'
        '</uni-view></uni-view>' % inner
    )


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
            "data-zsf-ball" in low or "data-zsf-drawer" in low or
            "z-float" in low or "z-sidebar" in low or "z-drawer" in low or "z-fab" in low or
            "zsf-ball" in low or "zsf-drawer" in low):
        return True
    # 通用特征：onerror 里出现 position:fixed + 拖动/抽屉关键词。
    # pointerdown 覆盖 Pointer Events 版悬浮球（旧版 mousedown/touchstart 双绑已弃用）。
    if "position:fixed" in low.replace(" ", "") and (
            "pointerdown" in low or "mousedown" in low or "touchstart" in low or
            "translatex" in low or "float" in low or "sidebar" in low or "drawer" in low):
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


def _is_shadowcast_engine_tag(tag):
    """ShadowCast / attachShadow 型组件引擎（标题栏 / NPC 状态栏 / 主角 HUD 等自绘 chrome）。
    这类 <img onerror> 运行时 attachShadow 把 UI 渲进 shadow root，宿主与数据留 light DOM。
    它们既不是可拖动悬浮球（不含 pointerdown/translateX 拖动特征），也不匹配雷达/KV 状态栏
    启发式，旧版三面板因此把它们漏进「第一句话剩余预览」——本函数把它们收进独立面板。

    precedence 铁律：悬浮球/抽屉与雷达/KV 状态栏已按既有精度在前面归类，这里**只收它们
    没认领的** attachShadow 组件，故对既有分类零回归。判据通用（按引擎结构，不写死某张卡的
    命名前缀）：① 运行时 attachShadow；② 命名空间化的组件生命周期属性 data-<前缀>-<角色>
    （owner/bootstrap/deploy/trigger/css-loader…，影渲法组件包普遍用它声明归属）；
    ③ 影渲法宿主类名约定（g3-host / sc-host / shadowcast）。"""
    low = tag.lower()
    if "onerror" not in low:
        return False
    # 预览自身的发送脚手架（data-pano-scaffold）不是被测组件，绝不归类。
    if "data-pano-scaffold" in low:
        return False
    # 悬浮/状态栏引擎保持既有归属，这里不抢（precedence）。
    if _is_floating_engine_tag(tag) or _is_statusbar_engine_tag(tag):
        return False
    # ① 强特征：运行时 attachShadow（影渲法地基）。
    if "attachshadow" in low:
        return True
    # ② 命名空间化组件生命周期属性：data-<前缀[可带连字符]>-<角色>。通用匹配，不写死前缀。
    if re.search(r'data-[a-z0-9-]+-(?:owned|bootstrap|deploy|trigger|'
                 r'css-loader|renderer|component-host|core|mount)\b', low):
        return True
    # ③ 影渲法宿主类名约定。
    if "g3-host" in low or "sc-host" in low or "shadowcast" in low:
        return True
    return False


def _extend_hidden_status_spans(html, end):
    """状态栏引擎后常跟一串 display:none 的 [key=value] 信标，一并归入状态栏面板。"""
    m = re.match(r'(?:\s*<span[^>]*display\s*:\s*none[^>]*>\[[\s\S]*?\]</span>)+', html[end:], re.I)
    if m:
        return end + m.end()
    return end


def split_preview_panels(rendered):
    """返回 (first_message, statusbar, floating, shadowcast)。轻量文本拆分，供预览定位问题。

    shadowcast 桶收 attachShadow 型自绘组件（标题栏/NPC 状态栏/主角 HUD 等），它们既非
    悬浮球也非雷达/KV 状态栏，旧版会漏进 first_message —— 现在单独成面板，见
    _is_shadowcast_engine_tag。precedence：悬浮 > 状态栏 > shadowcast，对既有分类零回归。"""
    status_parts = []
    floating_parts = []
    shadowcast_parts = []
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
    # precedence：悬浮 > 状态栏 > shadowcast。shadowcast 组件的数据同样常跟一串
    # display:none 信标 span，一并收进同面板（复用状态栏那套扫描）。
    bucket_of = {"float": floating_parts, "status": status_parts,
                 "shadow": shadowcast_parts}
    spans = []  # (start, end, bucket, chunk)
    for start, end, tag in _iter_tags(rest, "img"):
        if _is_floating_engine_tag(tag):
            spans.append((start, end, "float", rest[start:end]))
        elif _is_statusbar_engine_tag(tag):
            ext_end = _extend_hidden_status_spans(rest, end)
            spans.append((start, ext_end, "status", rest[start:ext_end]))
        elif _is_shadowcast_engine_tag(tag):
            ext_end = _extend_hidden_status_spans(rest, end)
            spans.append((start, ext_end, "shadow", rest[start:ext_end]))
    for start, end, bucket, chunk in sorted(spans, key=lambda x: x[0]):
        bucket_of[bucket].append(chunk)
    for start, end, bucket, chunk in sorted(spans, key=lambda x: x[0], reverse=True):
        rest = rest[:start] + rest[end:]

    # 3) 静态悬浮组件（非引擎注入：直接写死的 position:fixed / float/sidebar/ball 类）
    for pat in [r"<[^>]*(?:class=[\"'][^\"']*(?:float|sidebar|ball)[^\"']*[\"'][^>]*)[^>]*>[\s\S]*?</(?:div|button|a)>",
                r"<[^>]*style=[\"'][^\"']*position\s*:\s*fixed[^\"']*[\"'][^>]*>[\s\S]*?</(?:div|button|a)>"]:
        for m in list(re.finditer(pat, rest, re.I)):
            floating_parts.append(m.group(0))
            rest = rest.replace(m.group(0), "", 1)
    return (rest, "\n".join(status_parts), "\n".join(floating_parts),
            "\n".join(shadowcast_parts))


def assemble_preview(obj, platform, src_name):
    """三面板预览：第一句话整合 / 状态栏单独 / 悬浮组件。"""
    if isinstance(obj, list):
        rendered = "".join(rs for _name, _fr, rs in extract_fragments(obj, platform))
        return assemble_html(extract_fragments(obj, platform), platform, src_name,
                             _findregex_audit_html(obj, platform) + _onclick_audit_html(rendered, platform))
    rendered = apply_regex_pipeline(obj, platform)
    first, status, floating, shadowcast = split_preview_panels(rendered)
    audit = _findregex_audit_html(obj, platform) + _onclick_audit_html(rendered, platform)
    audit += "".join('<div class="frag-warn">ERROR 悬空标记：%s</div>' % html_mod.escape(x)
                     for x in find_dangling_markers(obj, platform))
    # 沙盒模式：装卡即抽出的 style/script 与匹配无关，每个隔离 iframe 都要带上，
    # 否则「只放 style/script 且谁都不引用」的官方首选写法在预览里等于不存在。
    assets = collect_sandbox_assets(obj) if platform == "mmdsandbox" else ""
    panels = [
        _panel("第一句话剩余预览", first, platform, "beginning remainder", assets),
        _panel("状态栏单独预览", status, platform, "status", assets),
        _panel("悬浮组件预览", floating, platform, "floating/sidebar", assets),
    ]
    # ShadowCast 组件（标题栏/NPC 状态栏/主角 HUD 等 attachShadow 自绘 chrome）单独成面板。
    # 仅在被测卡确实含此类组件时才出面板，避免给普通卡凭空多一格空面板。
    if shadowcast.strip():
        panels.append(_panel("ShadowCast 组件预览", shadowcast, platform,
                             "shadowcast (titlebar/npc/hud)", assets))
    body = "\n".join(panels + [audit])
    banner = make_banner(platform, src_name, _script_count(obj))
    return PAGE_TEMPLATE % {"platform": platform, "banner": banner,
                            "body": body, "marker_css": MARKER_CSS}


# ── MMD 真实聊天页外壳（实测复刻，2026-08-28）────────────────────────────────
# 依据：Playwright 进真实 iframe#chatIframe 读 CSSOM + getComputedStyle，
#      站点 www.sexyai.ai #/pages/chat/chat（旧聊天页 chatVersion:0）。
#      完整契约见 preview/MMD真实页DOM契约-2026-08-28.md。
#
# 🚨 改这份 CSS 前先读这段。这里每条取值都是实测真值，不是"看着顺眼"调出来的。
# 旧版本这里放的是一套凭空造的中性浅色骨架（白底 #fff、AI 气泡 #f0f0f3、用户气泡
# #3a76f0、顶栏 48px、气泡 max-width:82%、无 pre-line），与真机**没有一项相符**。
# 后果不是"预览丑一点"：
#   1) 缺 `white-space:pre-line` → 预览查不出「换行空白条」，这是 MMD 头号排版坑；
#   2) 气泡配色凭空取值 → 作者照预览定状态栏配色，上真机全糊在背景里；
#   3) 缺 .chat-scope-box/.scroll-view 两层 → 作者按文档写深选择器，预览失配。
# 沙盒分支早就被测试禁止"好看但失真"（test_dark_tokens_equal_measured_truth），
# MMD 分支同一条纪律，别往回改。
#
# 主题变量：平台由 JS 写在 body 内联 style 上（实测共 29 个），不是样式表规则、也不靠
# class 切换主题。这里注入实测的**深色一套**。浅色一套真机未抓到取值（运行时不暴露），
# 故不臆造 —— 需要浅色请回真机抓，别在这里填猜的值。
MMD_THEME_VARS_DARK = {
    "--background-color": "#17181A", "--card-background-color": "#282A2E",
    "--chat-content-font-color": "#FFFFFF", "--primary-font-color": "#FFFFFF",
    "--primary-color": "#FF6D97", "--shortcut-button-font-color": "#FFFFFF",
    "--input-background-color": "#33353B", "--input-font-color": "#FFFFFF",
    "--mindtype-font-color": "#FF6D97", "--more-item-bg-color": "#2C2E32",
    "--share-item-bg-color": "#2C2E32", "--history-font-color": "#FFFFFF",
    "--history-remark-font-color": "#C5C5C5",
    "--model-help-content-font-color": "#FFFFFF",
    "--model-setting-power-bg-color": "#0D0E0F",
    "--model-setting-power-tips-color": "#999999",
    "--model-setting-remark-color": "#C5C5C5", "--modify-input-bg-color": "#1E1F24",
    "--vditor-bg-color": "#0D0E0F", "--msg-option-separator-color": "#333333",
    "--conversation-list-content-color": "#C5C5C5",
    "--cancel-btn-background-color": "#FFB7CC", "--item-background-color": "#1E1F24",
    "--item-tip-color": "#FF6D97", "--item-tip2-color": "#FF6D97",
    "--tip-font-color": "#cccccc", "--modify-item-bottom-color": "#999999",
    "--btn-bg-color": "#33353B", "--btn-border-color": "transparent",
}

# rem 缩放律（实测两点拟合，误差 <0.001px）：
#   rootFontSize = 16 * min(innerWidth, 375) / 375
# 实测：主聊天页 iframe 宽 1280 → 16px（封顶）；编辑页预览 iframe 宽 283 → 12.0747px。
# 真机由 uni-app 写在 html 内联 style 上。CSS 的 min()/calc() 能精确表达同一条式子，
# 不需要 JS，且 iframe 改宽时自动跟随 —— 少了这条，所有 rem 尺寸全错。
MMD_ROOT_FONT_SIZE = "min(16px, calc(100vw * 16 / 375))"

# MMD 真实聊天页骨架 CSS。选择器层级与真机一字对应（去掉 uni-app 的 data-v scope hash，
# 那个 hash 每次构建都变，作者写卡也用不到）。被测的全局美化用 !important 照常压过。
MMD_PANORAMA_CSS = """html{font-size:%(rootfont)s}
html,body{margin:0;width:100%%;height:100%%;user-select:none;touch-action:manipulation;
  font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
body{overflow-x:hidden;font-size:16px;background-color:var(--background-color,#17181A);%(themevars)s}
*{margin:0;-webkit-tap-highlight-color:transparent}
uni-view,uni-scroll-view,uni-image,uni-text{display:block}
/* 真机外层壳（实测契约 §1）。uni-app 系是自定义元素，默认 inline，必须显式 block，
   否则宽高塌成 0、pageTarget() 量到的面积为 0 会退回 .chat（就是桌面 HUD 偏差的根因）。
   全高链 height:100%% 逐层继承 html/body 的 100%%，让 #app/uni-app/uni-page-body 都是
   全视口盒 —— HUD 无论命中链上哪个祖先，transform 都落在全高盒上，其 fixed 后代
   （.chat-scope-box/.chat-bottom）仍以视口高解析，不再塌成 45px。 */
#app,uni-app,uni-page,uni-page-wrapper,uni-page-body{display:block;width:100%%;height:100%%}

/* 顶栏：真实 2.8125rem = 45px @16px 基准 */
.chat .topTabbar{width:100%%;height:2.8125rem;line-height:2.8125rem;display:flex;
  justify-content:space-between;color:var(--primary-font-color,#FFFFFF)}
.chat .topTabbar .header-box{padding:0 0.625rem;display:flex;align-items:center;justify-content:space-between}
.chat .topTabbar .header-center{width:55%%;flex:1;display:flex;align-items:center;
  color:var(--primary-font-color,#FFFFFF)}
.chat .topTabbar .header-role-img{display:flex;align-items:center;margin-right:0.15625rem}
.chat .topTabbar .header-role-img .pano-avatar-dot{width:1.5625rem;height:1.5625rem;
  border-radius:0.78125rem;background:#4f7df5}
.chat .topTabbar .header-roleName{margin:0 5px;font-size:0.9375rem;overflow:hidden;
  white-space:nowrap;text-overflow:ellipsis}
.chat .topTabbar .header-icon-meun{display:flex;align-items:center;margin-right:12px;position:relative}
.chat .topTabbar .header-icon-meun .header-meun{display:flex;align-items:center;
  margin-left:0.78125rem;width:1.09375rem;height:1.09375rem;opacity:.75;
  font-size:0.8125rem;justify-content:center}

/* 滚动壳：真机 .chat-scope-box 是 fixed 全屏 + 角色背景图，.scroll-view 用内联 style
   下推 2.8125rem 并留出 3.2rem。这两层是所有 chat-body 后代选择器的前缀，不能省。 */
.chat .chat-scope-box{position:fixed;top:0;left:0;width:100%%;height:100%%;z-index:11;
  background-position:center center;background-size:auto 100%%;background-repeat:no-repeat}
.chat .chat-scope-box .scroll-view{height:calc(100%% - 3.2rem);margin-top:2.8125rem;
  background:rgba(0,0,0,0);position:relative;z-index:999;overflow-y:auto;
  -webkit-overflow-scrolling:touch}
.chat .chat-scope-box .scroll-view .uni-scroll-view-content{min-height:100%%}

/* 消息列表 */
.chat .chat-scope-box .scroll-view .chat-body{position:relative;padding-bottom:10.625rem;
  display:flex;flex-direction:column;font-size:15px}
.chat .chat-scope-box .scroll-view .chat-body .item{display:flex;align-items:center;
  padding:0.71875rem 0.9375rem}
.chat .chat-scope-box .scroll-view .chat-body .self{justify-content:flex-end}
.chat .chat-scope-box .scroll-view .chat-body .item .left{background-color:#fff;
  border-radius:1rem 1rem 1rem 0!important}
.chat .chat-scope-box .scroll-view .chat-body .item .right{background-color:#c2dcff;
  border-radius:1rem 1rem 0!important}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope{position:relative;
  max-width:94%%;color:var(--chat-content-font-color,#FFFFFF)}
/* 🚨 .content 这块是重点：background 覆盖上面 .left/.right 的白底/蓝底（所以深色主题下
   两侧气泡同色），opacity:.9 影响实际观感色，white-space:pre-line 是「换行空白条」真因。 */
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content{padding:0.75rem;
  background:var(--background-color,#17181A);opacity:.9;
  box-shadow:0 0.125rem 0.125rem rgba(0,0,0,.01);border-radius:0.5rem;white-space:pre-line}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table{
  border-collapse:collapse;empty-cells:show;overflow:auto;border-spacing:0;display:block;
  word-break:keep-all;width:100%%}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table th{font-weight:600}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table td,
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table th{
  padding:6px 13px;border:1px solid #dfe2e5;word-break:normal;white-space:nowrap}
.chat .chat-scope-box .scroll-view .chat-body .item .avatar{display:flex;justify-content:center;
  width:2.4375rem;height:2.4375rem;background:#4f7df5;border-radius:1.5625rem;overflow:hidden}
/* 首条描述气泡：通栏 + 圆角被覆盖成对称 0.5rem（无尖角） */
.chat .chat-scope-box .scroll-view .chat-body .avatar-body{width:100%%}
.chat .chat-scope-box .scroll-view .chat-body .avatar-body .touch-scope{width:100%%;max-width:100%%}
.chat .chat-scope-box .scroll-view .chat-body .avatar-body .touch-scope .left{border-radius:0.5rem!important}
.chat .chat-scope-box .scroll-view .chat-body .select-box{margin-right:0.625rem}
/* 消息操作小圆钮（实测 2026-08-29）：z-index 只有 2，组件层级要压过它。
   AI 消息 3 钮（刷新/编辑/分享）靠气泡左下；用户消息 2 钮（编辑/分享）靠右下。
   真机 .modify-btn 24px、rgba(0,0,0,.5)、圆形、gap 8px；scope position:absolute。
   第一句话(first_mes)的 scope 存在但按钮 0×0 隐藏 —— 预览首条描述气泡不放 scope 复刻此态。*/
.modify-btn-scope{position:absolute;left:0;z-index:2;margin-top:0.5rem;display:flex}
.modify-btn-scope .modify-btn{width:1.5rem;height:1.5rem;display:flex;align-items:center;
  justify-content:center;background:rgba(0,0,0,.5);border-radius:50%%;margin-right:0.5rem;
  font-size:0.75rem;color:#fff}
.modify-btn-scope .modify-btn svg{width:0.875rem;height:0.875rem;display:block}
/* 用户消息（.self）圆钮靠右：真机 justify-end、x≈右侧（实测 x=1039 对 1191 宽气泡）*/
.item.self .modify-btn-scope{left:auto;right:0;justify-content:flex-end}
/* 消息两态互斥（实测状态流转 2026-08-29）：初始态显开场白、发送后显用户+AI回复。
   顺序恒为 描述→first_mes→开场白(initial)→用户(sent)→AI(sent)，隐藏项塌陷，视觉序自然对。
   默认 data-chat-state=sent（被测内容落在 AI 回复气泡，作者开预览即见）。*/
.chat[data-chat-state="sent"] [data-msg-state="initial"]{display:none}
.chat[data-chat-state="initial"] [data-msg-state="sent"]{display:none}

/* 开场白选择块 */
.prologue-scope{padding:0 0.96156rem}
.prologue-scope .prologue-title{text-align:center}
.prologue-scope .prologue-title span{background:rgba(0,0,0,.5);border-radius:0.46875rem;
  font-size:0.875rem;color:#fff;padding:0.3125rem 0.625rem}
.prologue-scope .prologue-content{display:flex;align-items:center;min-height:2.8125rem;height:auto;
  background:var(--background-color,#17181A);opacity:.9;border-radius:0.375rem;
  font-size:0.8125rem;color:var(--chat-content-font-color,#FFFFFF);padding:0.9375rem;margin-top:0.625rem}

/* 官方侧边挂载点：悬浮组件的靶位，真机就是这两个空容器 */
.chat .mm-left-side-container{position:fixed;top:50%%;transform:translateY(-50%%);display:flex;
  flex-direction:column;gap:0.375rem;z-index:9999;left:0}
.chat .mm-right-side-container{position:fixed;top:50%%;transform:translateY(-50%%);display:flex;
  flex-direction:column;gap:0.375rem;z-index:9999;right:0}

/* 底部：快捷条 + 输入区。真机 .chat-bottom 是 fixed bottom, z-index 999 */
.chat .chat-bottom{z-index:999;width:100%%;transition:.1s;position:fixed;bottom:0}
.chat .chat-bottom .shortcut-bar-wrapper{position:relative;height:2.375rem;
  background:var(--background-color,#17181A);overflow:hidden;margin-bottom:-1px}
.chat .chat-bottom .shortcut-bar{display:flex;align-items:center;height:2.375rem;
  padding:0 0.375rem;gap:0.3125rem;overflow-x:auto;white-space:nowrap;scrollbar-width:none}
.chat .chat-bottom .shortcut-bar::-webkit-scrollbar{display:none}
.chat .chat-bottom .shortcut-btn{flex-shrink:0;display:flex;align-items:center;
  justify-content:center;gap:0.1875rem;height:1.75rem;box-sizing:border-box;padding:0 0.5rem;
  background:var(--input-background-color,#1E1F24);border-radius:0.875rem;font-size:0.75rem;
  color:var(--shortcut-button-font-color,#8D949D);white-space:nowrap;border:0}
.chat .chat-bottom .shortcut-bar-wrapper.theme-dark .shortcut-btn{background:#2c2e32}
.chat .chat-bottom .chat-bottom-wapper{background:var(--background-color,#17181A)}
.chat .chat-bottom .send-msg{display:flex;align-items:flex-end;padding:0.5rem 0.9375rem;
  width:100%%;box-sizing:border-box;transition:.1s;margin-bottom:-1px}
.chat .chat-bottom .uni-textarea{width:100%%;display:flex;align-items:flex-end;justify-content:space-between}
.chat .chat-bottom .uni-textarea .chat-input-scope{width:100%%;position:relative;
  background:var(--input-background-color,#1E1F24);border-radius:1.25rem;
  border:.0625rem solid var(--primary-color,#FF6D97);display:flex;align-items:center;
  justify-content:space-between;padding:0 0.5rem;box-sizing:border-box}
.chat .chat-bottom .uni-textarea .chat-input-scope.has-toolbar{flex-direction:column;
  align-items:stretch;padding:0.3125rem 0.5rem;border-radius:0.75rem}
/* ── 输入框折叠/展开两态（实测）──────────────────────────────────────────
   折叠：显示 .chat-input-collapsed-row（内含 [1] 预览 textarea + 发送钮）
   展开：+.is-expanded → 显示 .chat-input-toolbar + [0] 主 textarea + .chat-input-bottom-row
   🚨 全局美化改输入框必须**两态都看**：工具条（粘贴/清空）只在展开态存在。*/
.chat .chat-bottom .uni-textarea .chat-input-scope.has-toolbar .chat-input-toolbar{display:none}
.chat .chat-bottom .uni-textarea .chat-input-scope.has-toolbar.is-expanded .chat-input-toolbar{
  display:flex;align-items:center;gap:0.5rem;margin-bottom:0.375rem}
.chat .chat-bottom .uni-textarea .chat-input-scope.has-toolbar .chat-input-toolbar
  .chat-input-tool-btn{display:flex;align-items:center;gap:0.1875rem;font-size:0.75rem;
  color:#a0a0a0;padding:0.25rem 0.5625rem;background-color:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.1);border-radius:0.375rem}
/* [0] 主 textarea：折叠态隐藏、展开态显示 */
.chat .chat-bottom .uni-textarea .chat-input-scope>.chatMsgTextarea{display:none}
.chat .chat-bottom .uni-textarea .chat-input-scope.is-expanded>.chatMsgTextarea{display:block;
  width:100%%;line-height:1.4;min-height:1.4rem;max-height:9.8rem;padding:0 0.125rem;
  margin-bottom:0.5rem;overflow-y:auto}
/* 折叠行 / 展开行互斥 */
.chat .chat-bottom .uni-textarea .chat-input-scope .chat-input-collapsed-row{display:flex;
  align-items:center;justify-content:space-between;min-height:2.5625rem}
/* 折叠行与展开行互斥：展开态隐藏折叠行（否则两行叠加、输入框高成 172px 而非 125px） */
.chat .chat-bottom .uni-textarea .chat-input-scope.is-expanded .chat-input-collapsed-row{display:none}
/* 折叠行左右两格（算力数字 / 发送钮）：单行态 align-self:stretch 撑满行高居中；
   多行态改 align-self:auto + padding-bottom 沉到底（实测 .is-multiline 分支）。*/
.chat .chat-bottom .uni-textarea .chat-input-scope .chat-input-collapsed-row>uni-view:first-child,
.chat .chat-bottom .uni-textarea .chat-input-scope .chat-input-collapsed-row>uni-view:last-child{
  align-self:stretch;display:flex;align-items:center;min-height:1.25rem;
  transition:padding-top .25s,padding-bottom .25s}
.chat .chat-bottom .uni-textarea .chat-input-scope.is-multiline .chat-input-collapsed-row{
  align-items:flex-end}
.chat .chat-bottom .uni-textarea .chat-input-scope.is-multiline
  .chat-input-collapsed-row>uni-view:first-child,
.chat .chat-bottom .uni-textarea .chat-input-scope.is-multiline
  .chat-input-collapsed-row>uni-view:last-child{align-self:auto;padding-bottom:0.5rem}
.chat .chat-bottom .uni-textarea .chat-input-scope .chat-input-bottom-row{display:none}
.chat .chat-bottom .uni-textarea .chat-input-scope.is-expanded .chat-input-bottom-row{display:flex;
  align-items:center;justify-content:space-between;padding-bottom:0.375rem}
.chat .chat-bottom .uni-textarea .chat-input-scope.is-expanded
  .chat-input-bottom-row>uni-view{padding-top:0.875rem;min-height:1.25rem}
/* 输入框内的图标（发送钮）实测 1.25rem —— 比外面的「+」(1.5625rem) 小一档 */
.chat .chat-bottom .uni-textarea .chat-input-scope .btn-icon{width:1.25rem;height:1.25rem}
.chat .chat-bottom .uni-textarea .chat-input-scope.is-expanded{padding:0.625rem}
.chat .chat-bottom .uni-textarea .chat-input-scope .chat-input-collapsed-display{flex:1;
  min-width:0;padding:0 0.375rem;cursor:text}
.chat .chat-bottom .uni-textarea .chat-input-scope .chat-input-collapsed-preview{
  max-height:8.75rem;padding-top:0;padding-bottom:2px}
/* 🚨 上下 padding 一律挂在 `uni-textarea` **壳**上，内层 `textarea` 恒零上下 padding
   —— 这是真机的分层方式（实测：折叠预览壳 24px / 内层 22px；展开主输入壳与内层同 22px）。
   预览曾把两层压平成一条 `padding:0.5rem 0.25rem` 写在内层上，后果是每一态都多 16px：
   折叠 41→43px、输入框 53→55px；展开态主输入 22→43px。改壳不改内层。*/
/* `vertical-align:top` 消掉 textarea 的 inline 基线间隙。真机内层是 `position:absolute`
   所以本来就不撑壳；预览内层走正常流，不消间隙会让壳比内层高 5px
   → 展开态输入框 125→131px。
   ⚠️ 别改成 `display:block` 修这个：block 会让 rows=1 的高度约束失效，
   折叠预览从 22px 涨到 67px、折叠态输入框 53→79px（本地实测踩过）。*/
.chat .chat-bottom .uni-textarea .chat-input-scope .uni-textarea-textarea{
  padding-top:0;padding-bottom:0;vertical-align:top}
.chat .chat-bottom .uni-textarea .chat-input-scope .mind-type{display:flex;place-items:center;
  font-weight:500;font-size:0.78125rem;color:var(--mindtype-font-color,#FF6D97)}
.chat .chat-bottom .uni-textarea.is-multiline,
.chat .chat-bottom .uni-textarea.is-expanded{align-items:flex-end}
/* 壳（uni-textarea）承 padding；内层 textarea 只承字体/颜色/无边框，上下 padding 由
   上面那条清零。真机壳基线 `padding:0.75rem 0.25rem 0.75rem 0.1875rem`，
   折叠预览与展开态各自覆盖（见上）。*/
.chat .chat-bottom .uni-textarea .chat-input-scope .chatMsgTextarea{
  padding:0.75rem 0.25rem 0.75rem 0.1875rem;box-sizing:border-box}
.chat .chat-bottom .uni-textarea .chat-input-scope .chatMsgTextarea,
.chat .chat-bottom .uni-textarea .chat-input-scope .uni-textarea-textarea{width:100%%;
  max-height:11.875rem;overflow-y:auto;line-height:1.4!important;font-size:1rem;
  font-family:"PingFang SC";color:var(--input-font-color,#FFFFFF);background:transparent;
  border:0;outline:0;resize:none;box-sizing:border-box}
.chat .chat-bottom .uni-textarea .chat-input-scope .chatMsgTextarea::placeholder,
.chat .chat-bottom .uni-textarea .chat-input-scope .uni-textarea-textarea::placeholder{color:#999}
.chat .chat-bottom .pano-compose-row{display:flex;align-items:flex-end;gap:0.375rem;width:100%%}
.chat .chat-bottom .pano-send{flex:0 0 auto;width:1.625rem;height:1.625rem;border:0;padding:0;
  border-radius:50%%;background:var(--primary-color,#FF6D97);color:#fff;font-size:0.75rem;
  line-height:1;cursor:pointer}
.chat .chat-bottom .pano-send:active{opacity:.8}
/* 预览发送钮同时带 .btn-icon（对齐真机 uni-image.btn-icon，好让作者测可见性筛法）。
   尺寸跟 `.chat-input-scope .btn-icon` 一致 = 实测 1.25rem（20px）。
   ⚠️ 旧版这里写 1.625rem 并注明"防止被压小"，是错的：真机两态发送钮都是 20px，
   1.625rem(26px) 来自 `.send-btn-icon` 那条**未被用到**的规则。
   🚨 观感：真机发送钮是 `ico_send_dark.png`（灰色纸飞机）、**背景透明、不变粉**
   （2026-08-29 实机注入文字前后复验：bg 恒 rgba(0,0,0,0)，无激活变色）。
   旧版画成粉色实心圆+白箭头是错的，这里覆盖成透明底+灰色纸飞机 SVG（currentColor 驱动）。*/
.chat .chat-bottom .uni-textarea .chat-input-scope .pano-send.btn-icon,
.chat .chat-bottom .uni-textarea .chat-input-scope .pano-send-expanded.btn-icon{
  width:1.25rem;height:1.25rem;background:transparent;border-radius:0;
  color:#9198a1;display:flex;align-items:center;justify-content:center}
.chat .chat-bottom .uni-textarea .chat-input-scope .pano-send.btn-icon svg,
.chat .chat-bottom .uni-textarea .chat-input-scope .pano-send-expanded.btn-icon svg{
  width:0.9375rem;height:0.9375rem;display:block}
.chat .chat-bottom .pano-compose-icon{flex:0 0 auto;width:1.75rem;height:1.75rem;border:0;
  padding:0;border-radius:50%%;background:var(--input-background-color,#33353B);
  color:var(--primary-font-color,#FFFFFF);font-size:0.8125rem;cursor:pointer}

/* 长按菜单遮罩：真机 z-index 99999，组件想盖在它上面基本不可能 —— 预览留着做层级参照。
   实测(2026-08-29)：默认 display:none，长按弹出 → data-open=on。内含 .msg-content-box
   (被长按消息正文预览) + .msg-options-box(选项列表)。选项按消息类型算：AI/用户常规消息
   复制/删除/回溯/开启新的故事；first_mes 仅复制(其余项 display:none)。*/
.msg-option-scope{height:100%%;width:100%%;position:fixed;top:0;left:0;
  background-color:rgba(0,0,0,.7);z-index:99999;backdrop-filter:blur(5px);display:none}
.msg-option-scope[data-open="on"]{display:block}
.msg-option-scope .msg-content-box{overflow:auto;margin:5rem 1rem 0;min-height:1rem;max-height:50%%;
  background:var(--modify-input-bg-color,#1E1F24);box-shadow:0 0 0.25rem rgba(0,0,0,.06);
  border-radius:1.25rem;padding:1rem;color:var(--primary-font-color,#FFFFFF);white-space:pre-line}
.msg-option-scope .msg-options-box{margin-left:1rem;padding:0.625rem 1rem;margin-top:0.9375rem;
  width:9.0625rem;background:var(--modify-input-bg-color,#1E1F24);
  box-shadow:0 0 0.25rem rgba(0,0,0,.06);border-radius:1.25rem}
.msg-option-scope .msg-options-box .option-item{display:flex;align-items:center;
  justify-content:space-between;height:2.5rem;cursor:pointer}
.msg-option-scope .msg-options-box .option-item uni-text,
.msg-option-scope .msg-options-box .option-item span{font-weight:500;font-size:0.8125rem;
  color:var(--primary-font-color,#FFFFFF);line-height:1.6875rem}
.msg-option-scope .msg-options-box .option-item .opt-icon{width:1.125rem;height:1.125rem;
  display:flex;align-items:center;justify-content:center;color:var(--primary-font-color,#FFFFFF);
  opacity:.85;font-size:0.9375rem}
.msg-option-scope .msg-options-box .option-separator{width:100%%;height:0;
  border-top:.03125rem solid var(--msg-option-separator-color,#333333)}

/* ── 弹窗体系（实测复刻，全局美化会打到这些面板）───────────────────────────
   通用三层：.u-popup(height:0!) > .u-transition.u-fade-*(遮罩) / .u-slide-up-*(内容)
             > .u-popup__content > 各面板自己的 scope 类
   🚨 uview 基线 .u-popup__content 是**白底**，深色全靠面板 scope 或内联 style 覆盖 ——
   作者若只改了自己面板忘了别的，真机就会露白，预览必须能重现这一点。*/
.u-popup{flex:1}                        /* 真机 height:0，别拿它做可见性判据 */
.u-overlay{position:fixed;top:0;left:0;width:100%%;height:100%%;background-color:rgba(0,0,0,.7)}
.u-popup__content{background-color:#fff;position:relative}   /* ← 框架基线白底，实测原文 */
.u-popup__content--round-bottom{border-radius:10px 10px 0 0}
.u-popup__content--round-center{border-radius:10px}
.u-popup__content__close{position:absolute}
.u-popup__content__close--top-right{top:15px;right:15px}
.u-status-bar,.u-safe-bottom{width:100%%}
.pano-sheet{position:fixed;left:0;bottom:0;width:100%%;z-index:10075;display:none}
.pano-sheet[data-open="on"]{display:block}
.pano-sheet-mask{position:fixed;top:0;left:0;width:100%%;height:100%%;background-color:rgba(0,0,0,.7)}
/* 总结剧情实测 z-index 1000000000，比别的高 5 个数量级 —— 组件永远盖不过它 */
.pano-sheet[data-sheet="summary"]{z-index:1000000000}

/* 模型设置：scope 自带底色/padding/高度 */
.model-setting-scope{height:34.375rem;box-sizing:border-box;width:100%%;max-width:100%%;overflow:hidden;
  padding:0 1rem 1rem;background-color:var(--background-color,#17181A);display:flex;flex-direction:column}
.model-setting-scope .mp-top{display:flex;align-items:center;justify-content:space-between;
  padding:1.125rem 0.125rem 0.5625rem;flex-shrink:0}
.model-setting-scope .mp-top .mp-title{font-weight:600;font-size:1.0625rem;
  color:var(--primary-font-color,#FFFFFF);line-height:1}
.model-setting-scope .mp-top .mp-close{width:1.5rem;height:1.5rem;line-height:1.375rem;text-align:center;
  border-radius:50%%;color:var(--model-setting-remark-color,#C5C5C5);font-size:1.125rem;font-weight:300}
.model-setting-scope .mp-info-bar{display:flex;align-items:center;justify-content:space-between;
  padding:0 0.125rem 0.75rem;flex-shrink:0}
.model-setting-scope .mp-info-bar .mp-model-name{font-size:0.75rem;
  color:var(--model-setting-remark-color,#C5C5C5);flex:1;overflow:hidden;white-space:nowrap;
  text-overflow:ellipsis;padding-right:0.5rem}
.model-setting-scope .mp-info-bar .mp-energy-pill{display:flex;align-items:baseline;gap:0.125rem;
  background:var(--model-setting-power-bg-color,#0D0E0F);border-radius:0.75rem;
  padding:0.25rem 0.5625rem;flex-shrink:0}
.model-setting-scope .mp-info-bar .mp-energy-pill .mp-ev{font-size:1.25rem;font-weight:700;line-height:1;
  color:var(--primary-color,#FF6D97)}
.model-setting-scope .mp-info-bar .mp-energy-pill .mp-el{font-size:0.6875rem;font-weight:500;line-height:1;
  color:var(--model-setting-remark-color,#C5C5C5)}
.model-setting-scope .mp-setting-body{flex:1;height:0;min-height:0;overflow-y:auto}
.model-setting-scope .mp-card,.model-setting-scope .mp-switch-row{
  background:var(--model-setting-power-bg-color,#0D0E0F);border-radius:0.5rem;margin-bottom:0.5rem}
.model-setting-scope .mp-card{padding:0.625rem 0.6875rem 0.4375rem}
.model-setting-scope .mp-card-head{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:0.5rem}
.model-setting-scope .mp-card-head .mp-card-title{font-size:0.8125rem;font-weight:500;
  color:var(--primary-font-color,#FFFFFF)}
.model-setting-scope .mp-tokens{display:flex;flex-wrap:wrap;gap:0.3125rem}
.model-setting-scope .mp-tokens .mp-token-btn{width:calc(25%% - 0.25rem);height:1.875rem;display:flex;
  align-items:center;justify-content:center;line-height:1;border-radius:0.3125rem;
  border:.0625rem solid var(--model-setting-remark-color,#C5C5C5);text-align:center;font-size:0.8125rem;
  color:var(--primary-font-color,#FFFFFF);margin-bottom:0.3125rem;background:transparent;box-sizing:border-box}
.model-setting-scope .mp-tokens .mp-token-btn.selected{color:var(--primary-color,#FF6D97);font-weight:600;
  border-color:var(--primary-color,#FF6D97)}
.model-setting-scope .mp-switch-row{display:flex;align-items:center;justify-content:space-between;padding:0.6875rem}
.model-setting-scope .mp-sw-title{font-size:0.8125rem;font-weight:500;color:var(--primary-font-color,#FFFFFF)}
.model-setting-scope .mp-sw-desc{font-size:0.6875rem;color:var(--model-setting-remark-color,#C5C5C5)}
.model-setting-scope .bottom .btn{color:#fff;font-size:1rem;width:100%%;height:2.65625rem;
  line-height:2.65625rem;text-align:center;background:var(--primary-color,#FF6D97);border-radius:1.5625rem}

/* 对话设置：scope 透明，底色靠 content 内联；无圆角 */
.conv-style-modal{display:flex;flex-direction:column;background-color:transparent;width:100%%;
  height:69vh;overflow:hidden;box-sizing:border-box}
.cs-modal-header{height:3.125rem;display:flex;align-items:center;justify-content:space-between;
  padding:0 0.9375rem;border-bottom:0.03125rem solid rgba(255,255,255,.05);
  background-color:var(--background-color,#1E1F24);color:var(--primary-font-color,#FFFFFF)}
.cs-header-left,.cs-header-right{font-size:0.875rem;color:var(--primary-font-color,#FFFFFF);
  display:flex;align-items:center}
.cs-header-center{flex:1;text-align:center}
.cs-header-title{font-size:0.9375rem;font-weight:700}
.cs-modal-content{flex:1;height:0;display:flex;flex-direction:column;overflow-y:auto;padding:0.9375rem}

/* 总结剧情 */
.summary-sheet{display:flex;flex-direction:column;width:100%%;height:34.375rem;max-height:84vh;
  background-color:var(--background-color,#17181A);color:var(--primary-font-color,#FFFFFF);
  padding:0 1rem 1rem;overflow:hidden;position:relative;box-sizing:border-box}
.summary-top{display:flex;align-items:center;justify-content:space-between;
  padding:1.125rem 0.125rem 0.5625rem;flex-shrink:0}
.summary-top-title{font-size:1.0625rem;font-weight:600;color:var(--primary-font-color,#FFFFFF);line-height:1}
.summary-close{width:1.5rem;height:1.5rem;line-height:1.375rem;text-align:center;border-radius:50%%;
  color:var(--model-setting-remark-color,#C5C5C5);font-size:1.125rem;font-weight:300}
.summary-body{flex:1;height:0;padding:0.625rem 0.125rem 0.875rem;box-sizing:border-box;overflow-y:auto}
.summary-card{background:var(--card-background-color,#1E1F24);border-radius:0.5rem;padding:0.75rem}
.summary-label{font-size:0.75rem;color:var(--model-setting-remark-color,#C5C5C5);margin-bottom:0.375rem;
  display:flex;align-items:center;justify-content:space-between}
.summary-footer.bottom{padding:0.75rem 0 0;flex-shrink:0;display:flex;flex-direction:column}
.summary-save-btn.btn{width:100%%;height:2.625rem;border-radius:1.3125rem;
  background:var(--primary-color,#FF6D97);color:#fff;font-size:0.9375rem;font-weight:500;
  line-height:2.625rem;text-align:center;box-sizing:border-box}

/* 用户人设：🚨 这一套用 --lo* 变量族，实测那 18 个全部「引用但从未定义」，
   恒走 var(--loX, 字面量) 的 fallback → 作者改 --lo* 不生效，只能直接选类名。
   预览照真机**不定义**它们，好让作者在预览里就发现改不动。*/
.role-profile-modal{display:flex;flex-direction:column;isolation:isolate;background-color:transparent;
  width:100%%;height:69vh;overflow:hidden;box-sizing:border-box;font-size:0.875rem;line-height:1.4;
  color:var(--loPrimary-font-color,#FFFFFF)}
.role-profile-modal .header-scope{padding:0.875rem 0;flex-shrink:0;width:100%%;
  background-color:var(--loBackground-color,#17181A)}
.role-profile-modal .header-scope .header-box{padding:0 0.625rem;display:flex;align-items:center;
  justify-content:space-between;font-size:1rem}
.role-profile-modal .header-scope .icon-back{display:flex;align-items:center;
  color:var(--loPrimary-font-color,#FFFFFF);font-size:0.8125rem}
.role-profile-modal .header-scope .page-title{font-weight:500;font-size:0.9375rem;
  color:var(--loPrimary-font-color,#FFFFFF)}
.role-profile-modal .header-scope .complete-btn{margin-right:0.48063rem;font-weight:500;
  color:var(--loPrimary-color,#FF6D97);font-size:0.875rem}
.role-setting{background-color:var(--loBackground-color,#17181A);padding:0.9375rem;
  color:var(--loPrimary-font-color,#FFFFFF);flex:1;overflow-y:auto}
.role-setting .switch-card{background-color:var(--loCard-background-color,#1E1F24);border-radius:0.625rem;
  padding:0.625rem;margin-bottom:0.5rem;display:flex;align-items:center;justify-content:space-between}
.role-setting .switch-card .switch-title{font-size:0.8125rem;
  color:var(--loPrimary-font-color,#FFFFFF);margin-bottom:0.1875rem;font-weight:700}
.role-setting .switch-card .switch-desc{font-size:0.6875rem;color:var(--lo-subtitle-color,#ccc);line-height:1.4}
.role-setting .card{background-color:var(--loCard-background-color,#1E1F24);border-radius:0.625rem;
  padding:0.625rem;margin-bottom:0.5rem}
.role-setting .card .card-title{font-size:0.8125rem;font-weight:600;
  color:var(--loPrimary-font-color,#FFFFFF)}
.role-setting .card .card-desc{font-size:0.6875rem;color:var(--lo-subtitle-color,#ccc);margin-bottom:0.625rem}
.role-setting .card .textarea-dark{padding:0.625rem;border:0;border-radius:0.375rem;font-size:0.75rem;
  width:100%%;box-sizing:border-box;min-height:6.25rem;
  background-color:var(--loInput-background-color,#1E1F24);color:var(--loPrimary-font-color,#FFFFFF)}

/* 分享：矮条，实测 bg #282A2E(=--card-background-color)、padding 15.4px、h 167px */
.share-popup{background-color:var(--card-background-color,#282A2E);padding:0.9375rem;
  display:flex;flex-direction:column;align-items:center;gap:0.625rem}
.share-popup .share-title{font-size:1rem;font-weight:700;color:var(--primary-font-color,#FFFFFF)}
.share-popup .share-sub-title{font-size:0.75rem;color:var(--model-setting-remark-color,#C5C5C5)}
.share-popup .gen-link-btn{padding:0.375rem 1.25rem;border-radius:1rem;
  background:var(--primary-color,#FF6D97);color:#fff;font-size:0.8125rem}

/* AI帮聊 居中 dialog（未点，按既有 DOM/CSS 仿真）：u-fade-zoom-* + round-center */
.pano-dialog{position:fixed;top:0;left:0;width:100%%;height:100%%;z-index:10075;display:none;
  align-items:center;justify-content:center}
.pano-dialog[data-open="on"]{display:flex}
.pano-dialog .u-popup__content{background-color:var(--background-color,#17181A);border-radius:10px}
.alert-scope{height:auto;width:18.75rem;padding:0 1.875rem;display:flex;flex-direction:column}
.alert-scope .alert-title{color:var(--primary-font-color,#FFFFFF);font-size:1.09375rem;text-align:center;
  margin-top:0.9375rem;font-weight:700}
.alert-scope .alert-content{color:var(--primary-font-color,#FFFFFF);padding:1.40625rem 0;
  font-size:0.875rem;text-align:center}
.alert-scope .alert-checkbox{display:flex;align-items:center;justify-content:center;font-size:0.8125rem;
  color:var(--primary-font-color,#FFFFFF);margin-bottom:0.625rem}
.alert-scope .alert-checkbox .checkbox-box{display:flex;align-items:center;justify-content:center;
  width:0.875rem;height:0.875rem;border:.0625rem solid var(--primary-font-color,#FFFFFF);
  border-radius:0.1875rem;margin-right:0.375rem;box-sizing:border-box}
.alert-scope .alert-bottom{display:flex;justify-content:center;align-items:center;font-size:1rem;
  padding:0 0 0.9375rem}
.alert-scope .alert-bottom-double{justify-content:space-between}
.alert-scope .alert-bottom .ok-btn{color:var(--primary-color,#FF6D97)}
.alert-scope .alert-bottom-double .cancel-btn{color:var(--primary-font-color,#FFFFFF)}

/* 输入框左侧 AI帮聊入口（💡）实测样式。
   真机那里是 25×25 的 `uni-image`，容器实测 25×41。预览用 💡 字形代替图片，
   所以必须把字形锁进 1.5625rem 的盒子里 —— 否则 27px 字形会把整行顶高 2px，
   连带 .chat-input-scope 53→55px（本地实测踩过）。*/
.chat .chat-bottom .uni-textarea .ai-assistant{position:relative;display:flex;align-items:center;
  margin-right:0.1875rem;color:var(--primary-font-color,#FFFFFF);
  width:1.5625rem;height:1.5625rem;box-sizing:content-box;
  font-size:1.5625rem;line-height:1;justify-content:center}
/* 右侧「+」更多入口：真机是 .chat-input-scope 的**兄弟**，不在输入框内部。
   两态都留在输入框右侧外部（不会跑到输入框下方）；靠 padding-bottom 把图标压到视觉中线。*/
.chat .chat-bottom .uni-textarea .more-options-scope{display:flex;align-items:center;
  margin-left:0.375rem}
.chat .chat-bottom .uni-textarea .more-options-scope .btn-icon{width:1.5625rem;height:1.5625rem}
/* 🚨 观感：真机 `+` 是 `ico_more_dark.png` —— **一个灰色描边圆圈里一个加号**（展开态换
   `ico_more_called_dark.png`，圈里变减号）。旧版预览退化成飘在边上的裸全角＋（无圈），
   与真机差最远。这里用 CSS 把它画成灰圈+居中字形，两态都带圈（＋⇄－，JS 只换字形不换圈）。
   字形用裸 43(+)/8722(−)（不用带圈的 8854 ⊖，否则与 CSS 圈叠成双圈）。*/
.chat .chat-bottom .uni-textarea .more-options-scope .btn-icon{
  box-sizing:border-box;border:0.09375rem solid #6b7079;border-radius:50%%;
  color:#9198a1;display:flex;align-items:center;justify-content:center;
  font-size:1rem;line-height:1;font-weight:300}
/* 🚨 两态 padding-bottom 差 0.125rem（实测 15.5px→13.5px）：.uni-textarea 是 align-items
   flex-end，两侧图标靠这个 padding 顶到输入框视觉中线。展开态输入框变高、底行自带
   padding，所以垫片要略薄一点。改全局美化时动了这两个值，图标就会偏离中线。*/
.chat .chat-bottom .uni-textarea .ai-assistant,
.chat .chat-bottom .uni-textarea .more-options-scope{padding-bottom:0.96875rem;
  transition:padding-bottom .25s}
.chat .chat-bottom .uni-textarea.is-multiline .ai-assistant,
.chat .chat-bottom .uni-textarea.is-expanded .ai-assistant,
.chat .chat-bottom .uni-textarea.is-multiline .more-options-scope,
.chat .chat-bottom .uni-textarea.is-expanded .more-options-scope{padding-bottom:0.84375rem}
.chat .chat-bottom .uni-textarea .ai-assistant .beta-badge{position:absolute;top:-0.3125rem;
  left:-0.625rem;background-color:var(--primary-color,#FF6D97);color:#fff;font-size:0.625rem;
  padding:0.125rem 0.1875rem;border-radius:0.3125rem;line-height:1}

/* 「+」展开的更多面板：不是弹窗，在 .chat-bottom 内展开。
   位置：`.chat-bottom-wapper` 里排在 `.send-msg` **之后** → 面板在输入框**下方**、
   把输入框整条往上顶（实测底栏 105px→422px；面板自身 317px）。
   若同时展开输入框则 105→494px。组件按"底栏 105px"算避让位置会被压住。*/
.chat .chat-bottom .more-scope{height:auto;padding:0.75rem 0.9375rem 0.9375rem;display:none;
  flex-wrap:wrap;gap:0.625rem;background:var(--background-color,#17181A)}
.chat .chat-bottom .more-scope[data-open="on"]{display:flex}
.chat .chat-bottom .more-scope .item{width:calc(25%% - 0.625rem);text-align:center}
.chat .chat-bottom .more-scope .item .item-title{font-weight:400;font-size:0.8125rem;
  color:var(--primary-font-color,#FFFFFF);line-height:1.15625rem;height:1.15625rem;margin-top:0.4375rem}
.chat .chat-bottom .more-scope .item .item-icon{width:100%%;height:4.03125rem;
  background:var(--more-item-bg-color,#2C2E32);border-radius:1.25rem;padding:1.25rem 1.40625rem;
  box-sizing:border-box;display:flex;align-items:center;justify-content:center;font-size:1.25rem}

/* 指令栏：真机「选择指令」原地替换快捷条（不是弹窗） */
.chat .chat-bottom .shortcut-bar-wrapper .instruction-bar{display:flex;align-items:center;
  height:2.375rem;padding:0 0.375rem;gap:0.3125rem;overflow-x:auto;white-space:nowrap;
  scrollbar-width:none}
.chat .chat-bottom .shortcut-bar-wrapper .instruction-bar.hidden{transform:translateX(0.9375rem);
  opacity:0;pointer-events:none;position:absolute;inset:0}
.chat .chat-bottom .shortcut-bar-wrapper .shortcut-bar.hidden{transform:translateX(-0.9375rem);
  opacity:0;pointer-events:none;position:absolute;inset:0}
.chat .chat-bottom .shortcut-bar-wrapper .back-btn{flex-shrink:0;width:1.5rem;height:1.5rem;
  border-radius:50%%;background:var(--primary-color,#FF6D97);display:flex;align-items:center;
  justify-content:center;color:#fff;box-shadow:0 0.125rem 0.5rem rgba(255,109,151,.35)}
.chat .chat-bottom .shortcut-bar-wrapper .instruction-chip{display:inline-flex;align-items:center;
  justify-content:center;flex-shrink:0;height:1.75rem;box-sizing:border-box;padding:0 0.6875rem;
  margin-right:0.3125rem;background:var(--input-background-color,#1E1F24);border-radius:0.875rem;
  font-size:0.75rem;color:var(--shortcut-button-font-color,#8D949D);white-space:nowrap;border:0}
.chat .chat-bottom .shortcut-bar-wrapper.theme-dark .instruction-chip{background:#2c2e32}"""


# 全景预览聊天页骨架 CSS（中性默认；被测的全局美化用 !important 会正常压过）。
# 🚨 这份现在只给 **本地酒馆(st)** 用：它是一套中性占位骨架，没有 ST 真机实测依据。
# MMD 已改走 MMD_PANORAMA_CSS（实测复刻）。别再把这份当"MMD 聊天页"——它不是。
# 要给 ST 做同等还原，需要先抓真实 ST 页（.mes/.mes_text/#chat 那一套）再改这里。
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
.banner{padding:8px 14px;font-size:12px;font-weight:600;flex:0 0 auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.banner-st{background:#1f6feb}.banner-mmd{background:#9e6a03}.banner-mmdsandbox{background:#1a7f5a}
.frag{flex:1;margin:8px 12px;display:flex;flex-direction:column;border:1px dashed #30363d;border-radius:8px;overflow:hidden;min-height:0}
.frag-label{background:#161b22;color:#8b949e;font-size:11px;padding:6px 12px;border-bottom:1px solid #30363d;flex:0 0 auto}
.frag-warn{background:#3a2d00;color:#f0c674;font-size:11px;padding:6px 12px}
.pano-audit{flex:0 0 auto;margin:0 12px 12px;border:1px solid #30363d;border-radius:6px;background:#161b22;color:#c9d1d9}
.pano-audit>summary{cursor:pointer;padding:7px 12px;font-size:12px;font-weight:600;list-style-position:inside}
.pano-audit[open]>summary{border-bottom:1px solid #30363d}
.pano-audit-body{max-height:38vh;overflow:auto}
.preview-tools{display:block;padding:0;background:#161b22;border-bottom:1px solid #30363d;flex:0 0 auto}
.preview-tools>summary{cursor:pointer;color:#c9d1d9;font-size:11px;font-weight:600;list-style-position:inside;padding:6px 12px}
.preview-tools[open]>summary{border-bottom:1px solid #30363d}
.preview-tools:not([open])>.preview-tools-body{display:none}
.preview-tools-body{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 12px}
.preview-tools-label{color:#8b949e;font-size:11px;margin-right:2px}
.preview-tool{border:1px solid #484f58;border-radius:4px;background:#21262d;color:#e6edf3;padding:4px 8px;font-size:11px;cursor:pointer}
.preview-tool:hover{background:#30363d}
%(marker_css)s
.pano-frame{flex:1;width:100%%;border:0;display:block;background:#fff;min-height:min(480px,calc(100vh - 150px))}
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
    # MMD 骨架下 .chat 是根容器、滚动区是 #pano-chat（.scroll-view），二者不再同一个节点；
    # 元素名也要跟着建成 uni-view，否则作者写 `uni-view > .content` 在动态气泡上会失配。
    "function mmd(){return !!D.querySelector('.chat-scope-box');}"
    "function el(tag){return D.createElement(mmd()?'uni-view':tag);}"
    "function pane(){return D.querySelector('#pano-chat')||D.querySelector('.chat');}"
    "function shell(){return D.querySelector('.chat-scope-box')||D.querySelector('.chat');}"
    "function add(side,text){var root=chat();if(!root)return null;"
    "var it=el('div');it.className='item'+(mmd()?' Ai':'')+(side==='right'?' self':'');"
    "it.setAttribute('data-preview-dynamic','1');"
    "var touch=el('div');touch.className='touch-scope';"
    "var ct=el('div');ct.className='content '+side;ct.textContent=text;"
    "hook(it,touch,ct,side);"
    "touch.appendChild(ct);it.appendChild(touch);"
    "if(mmd()){var wrap=el('div');wrap.appendChild(it);root.appendChild(wrap);}"
    "else{root.appendChild(it);}"
    "var sc=pane();if(sc)sc.scrollTop=sc.scrollHeight;return ct;}"
    "function syncRoute(hash){var active=/chat\\/chat/.test(hash);"
    "var pane=shell(),input=D.querySelector('.chat-bottom'),label=D.querySelector('.pano-route-label');"
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
    # MMD 骨架下滚动区是 #pano-chat；.chat 退化成根容器（不滚动）。
    "var chat=document.querySelector('#pano-chat')||document.querySelector('.chat');"
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


_TAG_RE = re.compile(r"<[^>]+>")


def _sandbox_greeting_text(obj):
    """冷启动 payload.content 用的开场白**纯文本**。
    实机 payload.content 是正文字符串（探针：content='测试-第一句话'），不是渲染后 HTML，
    故这里剥掉标签，避免模拟器把 HTML 当正文喂给作者。"""
    if not isinstance(obj, dict):
        return ""
    raw = _text_field(obj, "beginning")
    return html_mod.unescape(_TAG_RE.sub("", raw)).strip()


def _sandbox_sim_block(profile, greeting):
    """模拟器注入块。**必须整体位于作者 hoisted assets 之前**：实机上作者脚本执行时
    window.sdk 已在位，顺序反了作者顶层就拿不到 sdk（与真机不符，会误导作者加兜底）。"""
    config = {
        "profile": profile,
        "greeting": greeting,
        # 探针实测的真实身份字段形状（role: name/avatarUrl；user: nickname/avatarUrl）。
        "roleName": "测试", "userNickname": "洛璃",
        # viewportHeight 不写死：浏览器端按 iframe 当前 innerHeight 初始化，
        # 键盘控制再从该实时基线扣除 inset。
    }
    return ('<script data-preview-sim="config">window.__MMD_SANDBOX_SIM_CONFIG__=%s;</script>'
            '<script data-preview-sim="1">%s</script>'
            % (json.dumps(config, ensure_ascii=False), load_sandbox_sim_source()))


# 沙盒发送脚手架：经典 <script>，**绝不用 img onerror**。
# 沙盒 <script> 是一等公民，用 onerror 点火既被官方明令禁止、也完全没必要
# （事实卡 §8.2）。走 sdk.message.send，让发送这条路也过一遍真实 SDK 表面。
SANDBOX_SEND_SCAFFOLD = (
    '<script data-preview-sim="send">'
    "(function(){"
    "var D=document;"
    "D.addEventListener('DOMContentLoaded',function(){"
    "var ta=D.querySelector('[data-chat=\"input\"]');"
    "var btn=D.querySelector('[data-chat=\"send\"]');"
    "if(!ta||!btn)return;"
    "var send=function(){var v=String(ta.value||'').replace(/^\\s+|\\s+$/g,'');"
    "if(!v)return;"
    "var ctl=window.__MMD_SANDBOX_SIM__&&window.__MMD_SANDBOX_SIM__.control;"
    "if(!ctl)return;"
    "ta.value='';"
    # 走 SDK 真实表面；thin profile 下 message.send 是 rejected Promise，
    # 此时退回控制 API 追加气泡，并把拒绝原因打进诊断（这正是要让作者看到的差异）。
    "try{var p=window.sdk.message.send(v);"
    "if(p&&typeof p.then==='function'){p.then(null,function(e){"
    "ctl.addUser(v);ctl.log.warnings.push('message.send 被拒（'+(e&&e.code)+'）："
    "瘦预览下写类能力不可用，已退回本地追加气泡。');});}}"
    "catch(e){ctl.addUser(v);}"
    "};"
    "btn.addEventListener('click',function(ev){ev.stopPropagation();send();});"
    "ta.addEventListener('keydown',function(ev){"
    "if(ev.key==='Enter'&&!ev.shiftKey){ev.preventDefault();send();}});"
    "});"
    "})()"
    '</script>'
)


SANDBOX_MULTIROUND_RAW = (
    "AI 追答\n\n[状态]\n体力: 79/100\n灵力: 26/60\n境界: 炼气三层|145/300\n"
    "银钱: 372\n装备: 头:斗笠|身:麻衣:防御+2|腰:药囊\n"
    "属性: 攻:12 防:8:破甲 敏:15\n位置: 内城-东市-药铺\n"
    "好感: 苏九=64, 阿澈=25\n标记: 初来乍到, 中毒\n[/状态]"
)


def _sandbox_multiround_expr(obj):
    """事件拿原始模型正文，DOM 拿同一离线规则管线的结果；模拟器不自造正则事实。"""
    rendered = _apply_pipeline_to_text(SANDBOX_MULTIROUND_RAW, obj, "mmdsandbox")
    rendered = apply_platform_limits(rendered, "mmdsandbox")
    return "addUser('用户追问');c.addAI(%s,%s)" % (
        json.dumps(SANDBOX_MULTIROUND_RAW, ensure_ascii=False),
        json.dumps(rendered, ensure_ascii=False))


# 沙盒模式聊天页骨架的稳定钩子（mmd-sandbox.md §5）。挂到全景已有节点上，作者写的
# [data-chat="root"] 选择器与 var(--chat-accent) 在预览里就能真的解析到。
_SANDBOX_HOOKS = {
    # data-preview-bubble-outline 是预览专属辅助标记（真机无此属性、无那圈描边）。
    # 默认不挂，保持真实外观；外层「气泡辅助线」按钮可临时切换，样式见 SANDBOX_CHROME_CSS。
    # 默认用已实测的 dark 真值；light 令牌仍保留为可切换的 probe-needed 占位。
    "root": (' data-chat="root" data-theme="dark" data-composer="visible" data-chat-state="initial"'
             ' style="--chat-viewport-height:100vh;'
             'background-image:url(\'data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22/%3E\');'
             'background-position:center center;background-size:auto 100%;background-repeat:no-repeat"'),
    "header": ' data-chat="header"',
    "header_back": ' data-chat="header-back"',
    "header_title": ' data-chat="header-title"',
    "header_actions": ' data-chat="header-actions"',
    "header_extra": '<span data-slot="header-extra"></span>',
    "messages": ' data-chat="messages"',
    "list": ' data-chat="list"',
    "frame": ' data-chat="message-frame"',
    "msg_user": ' data-chat="message" data-from="user" data-state="done" data-msg-id="pano-1"',
    "msg_ai": ' data-chat="message" data-from="ai" data-state="done" data-msg-id="pano-2"',
    "body": ' data-chat="message-body"',
    "message_extra": '<div data-slot="message-extra"></div>',
    "message_actions": '<div data-chat="message-actions"></div>',
    "stage": '<div data-chat="author-stage" class="pano-stage" hidden></div>',
    "composer": ' data-chat="composer"',
    "toolbar": '<div data-slot="toolbar"></div>',
    "input": ' data-chat="input"',
    "send": ' data-chat="send"',
    # 以下为 2026-08-29 实测补齐的钩子（旧版缺，作者按手册写选择器会失配）
    "shortcut": ' data-chat="shortcut"',
    "instruction_bar": ' data-chat="instruction-bar"',
    "instruction_back": ' data-chat="instruction-back"',
    "instruction_chip": ' data-chat="instruction-chip"',
    "assistant": ' data-chat="assistant" data-action="assistant"',
    "assistant_tip": "",   # 真机点击后才插入，默认不渲染
    "model_chip": ' data-chat="model-chip" data-action="model"',
}


# 沙盒全景工具栏按钮：(标签, 传给 iframe 内控制 API 的表达式, 悬浮说明)。
# 全部走 __MMD_SANDBOX_SIM__.control，不碰被测内容。
SANDBOX_TOOL_BUTTONS = (
    ("追加 AI", "addAI()", "追加一条 AI 气泡，派 new/mount/done"),
    ("流式追加", "stream(['流式','片段'])", "开一条流式气泡并逐块派 message:stream"),
    ("结束流式", "done()", "给流式气泡派 message:done"),
    ("多轮对话", None, "连续追加一轮用户+带更新状态块的 AI，检验历史快照与收窄"),
    ("切深浅色", "theme()", "改 root 的 data-theme 并派 theme:change"),
    ("切会话", "switchConversation()", "清消息与补发历史并派 conversation:switch"),
    ("平台关舞台", "stageClose()",
     "模拟平台侧关闭舞台才派 stage:close（sdk.stage.close 不派）"),
    ("键盘弹起", "setKeyboardInset(420)", "把 --chat-viewport-height 压到键盘之上"),
    ("键盘收起", "setKeyboardInset(0)", "恢复 --chat-viewport-height"),
    ("卸载末条", "unmountLast()", "派 message:unmount 并移除最后一条气泡"),
    ("返回", "back()", "派 back 事件"),
    ("dispose", "dispose()", "派 dispose 事件"),
)


def _sandbox_toolbar_html(obj):
    """沙盒全景工具栏。按钮调 iframe 内的控制 API，模拟平台侧动作。"""
    rows = []
    for label, expr, title in SANDBOX_TOOL_BUTTONS:
        if label == "多轮对话":
            expr = _sandbox_multiround_expr(obj)
        call = ("(function(){var c=document.querySelector('.pano-frame').contentWindow"
                ".__MMD_SANDBOX_SIM__.control;c.%s;})()" % expr)
        rows.append('<button class="preview-tool" type="button" title="%s" onclick="%s">%s</button>'
                    % (html_mod.escape(title, quote=True),
                       html_mod.escape(call, quote=True), html_mod.escape(label)))
    rows.append('<button class="preview-tool" type="button" title="%s" onclick="%s">%s</button>'
                % ("切换预览辅助线（真机默认无描边）",
                   html_mod.escape(
                       "(function(){var r=document.querySelector('.pano-frame').contentWindow."
                       "document.querySelector('[data-chat=\"root\"]');if(!r)return;"
                       "if(r.hasAttribute('data-preview-bubble-outline'))"
                       "r.removeAttribute('data-preview-bubble-outline');"
                       "else r.setAttribute('data-preview-bubble-outline','1');})()",
                       quote=True),
                   "气泡辅助线"))
    dump = ("(function(){var s=document.querySelector('.pano-frame').contentWindow"
            ".__MMD_SANDBOX_SIM__;console.log('[sim] 事件顺序',s.control.eventOrder());"
            "console.log('[sim] 诊断',s.control.diagnose());console.log('[sim] 调用',s.calls);"
            "window.alert('事件顺序：'+s.control.eventOrder().join(' > '));})()")
    rows.append('<button class="preview-tool" type="button" title="%s" onclick="%s">%s</button>'
                % ("打印事件顺序/调用日志到控制台",
                   html_mod.escape(dump, quote=True), "事件日志"))
    return ('<details class="preview-tools" data-preview-tools="1">'
            '<summary>沙盒仿真控制（默认折叠）</summary><div class="preview-tools-body">'
            '<span class="preview-tools-label">平台侧动作</span>%s'
            '%s</div></details>' % ("".join(rows), _sandbox_panel_tools_html()))


# 浮层开关按钮：分两组摆，标签直接写清"卡片能改 / 平台侧改不动"，
# 免得作者对着宿主弹窗白写 --chat-modal-*。
SANDBOX_PANEL_TOOLS_IN = (
    ("more-panel", "＋更多面板", "composer 内展开（不是弹窗）；壳吃 --chat-modal-bg、"
                              "正文 --chat-modal-text、项图标 --chat-more-item-bg。"
                              "实测 composer 95→412px"),
    ("message-menu", "长按菜单", "[data-chat=message-menu]，z-8200 + backdrop blur；"
                               "内层吃 --chat-modal-surface / --chat-modal-text"),
    ("alert", "居中 alert", "[data-chat=alert]，实测 position:absolute（非 fixed）、"
                          "遮罩 rgba(0,0,0,.45)、z-9000；确定钮吃 --chat-accent"),
    ("snack", "snack 提示", "[data-chat=snack]，composer 侧，z-8100"),
    ("snackbar", "snackbar", "[data-probe=snackbar]，平台侧，z-10090（最高）"),
    ("share-bar", "分享条", "[data-chat=share-bar]，吃 --chat-composer-bg + --chat-accent"),
    ("share-pick-bar", "选消息底栏", "[data-chat=share-pick-bar]，吃 --chat-modal-surface"),
    ("share-shot-loading", "长图 loading", "[data-chat=share-shot-loading]，z-8000"),
    ("summary-bubble", "总结气泡", "[data-chat=summary-bubble]，长在消息流里"),
    ("history-loading", "历史加载", "[data-probe=history-loading]，会把 messages 整块隐藏"),
)

SANDBOX_PANEL_TOOLS_HOST = (
    ("model", "模型设置"), ("conv", "对话设置"), ("summary", "总结剧情"),
    ("role", "用户人设"), ("share", "分享"),
)


def _sandbox_panel_tools_html():
    """沙盒浮层开关（预览工具，非被测产物）。"""
    win = "document.querySelector('.pano-frame').contentWindow"
    parts = ['<span class="preview-tools-label">iframe 内浮层（卡片 CSS 能改）</span>']
    for name, label, tip in SANDBOX_PANEL_TOOLS_IN:
        parts.append(
            '<button class="preview-tool" type="button" title="%s" '
            'onclick="%s.__sbxPanels.open(\'%s\')">%s</button>'
            % (html_mod.escape(tip, quote=True), win, name, label))
    parts.append(
        '<button class="preview-tool" type="button" title="指令栏与快捷条原地互斥切换'
        '（不是弹窗）" onclick="%s.__sbxPanels.toggleInstruction()">指令栏切换</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="AI帮聊 tip：真机点击后才插入'
        '（[data-chat=assistant-tip]，吃 --chat-modal-accent）" '
        'onclick="%s.__sbxPanels.assistantTip()">帮聊 tip</button>' % win)
    for mode in ("content", "full", "closed"):
        parts.append(
            '<button class="preview-tool" type="button" title="舞台 %s 态'
            '（实测 content=absolute/z-2000、full=fixed/z-3000、closed=display:none）" '
            'onclick="%s.__sbxPanels.stage(\'%s\')">舞台 %s</button>' % (mode, win, mode, mode))
    parts.append('<span class="preview-tools-label">宿主页弹窗（平台侧 · 卡片改不动，'
                 '只看遮挡层级）</span>')
    for name, label in SANDBOX_PANEL_TOOLS_HOST:
        parts.append(
            '<button class="preview-tool" type="button" '
            'title="渲染在宿主页 uni-app，跨源 iframe 之外；探针验证在卡里改 '
            '--chat-modal-* 对它无效" '
            'onclick="%s.__sbxPanels.open(\'%s\')">%s</button>' % (win, name, label))
    parts.append('<span class="preview-tools-label">输入框三态</span>')
    for state, lab, tip in (
            ("", "折叠", "基线态：min-height 82rpx、单行居中（实测）"),
            ("is-multiline", "多行", "真机内容多行时自动加：换 padding、底对齐，"
                                    "两侧圆钮 padding-bottom 27rpx"),
            ("is-expanded", "展开", "转 grid 三区（tools/input/chip.send），"
                                   "工具行「粘贴/清空」才显示、model-chip order 归 0")):
        parts.append(
            '<button class="preview-tool" type="button" title="%s" '
            'onclick="%s.__sbxPanels.fieldState(\'%s\')">%s</button>'
            % (html_mod.escape(tip, quote=True), win, state, lab))
    parts.append('<span class="preview-tools-label">消息态与长按（实测状态流转）</span>')
    parts.append(
        '<button class="preview-tool" type="button" title="初始态：显 first_mes + 开场白选择块'
        '（[data-probe=prologue]）；发送一条后开场白消失、显用户+AI回复；回溯则重现" '
        'onclick="%s.__sbxPanels.setChatState(\'initial\')">初始态(含开场白)</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="已发送态：开场白消失，'
        '显用户消息(2圆钮)+AI回复(3圆钮)" '
        'onclick="%s.__sbxPanels.setChatState(\'sent\')">已发送态</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="点开场白 chip 的等效动作：'
        '把示例正文注入输入框（实测点开场白即填入，且不展开输入框）" '
        'onclick="%s.__sbxPanels.fillInput(\'（示例）来自开场白的注入正文\')">开场白→输入框</button>'
        % win)
    parts.append(
        '<button class="preview-tool" type="button" title="点击/聚焦输入框展开（加 is-expanded），'
        '真机 blur 收回" onclick="%s.__sbxPanels.expandField()">展开输入框</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="失焦收回输入框（去 is-expanded）" '
        'onclick="%s.__sbxPanels.collapseField()">收回输入框</button>' % win)
    for kind, lab, tip in (
            ("first", "长按·第一句话", "角色卡「第一句话」长按菜单仅「复制」（实测）"),
            ("ai", "长按·AI消息", "AI 消息长按：复制/删除/回溯/开启新的故事（实测）"),
            ("user", "长按·用户消息", "用户消息长按：同 AI 四项（回溯对用户消息也成立；"
                                   "用户菜单逐字复核标 probe-needed）")):
        parts.append(
            '<button class="preview-tool" type="button" title="%s" '
            'onclick="%s.__sbxPanels.longPress(\'%s\',\'被长按的消息正文（示例）\')">%s</button>'
            % (html_mod.escape(tip, quote=True), win, kind, lab))
    parts.append('<span class="preview-tools-label">主题</span>')
    for t, lab in (("dark", "深色"), ("light", "浅色")):
        parts.append(
            '<button class="preview-tool" type="button" title="切 [data-theme]'
            '（两套 29 令牌均为实测真值）" '
            'onclick="%s.__sbxPanels.theme(\'%s\')">%s</button>' % (win, t, lab))
    parts.append(
        '<button class="preview-tool" type="button" title="关闭所有浮层" '
        'onclick="%s.__sbxPanels.closeAll()">全部关闭</button>' % win)
    return "".join(parts)


def _sandbox_accuracy_html(profile):
    """能力精度诊断表。每个能力都必须带 accuracy；probe-needed 绝不显示成已精确模拟。"""
    contract = load_sandbox_contract()
    caps = contract["capabilities"]
    thin = profile == "thin-preview"
    # thin 下 cache 写操作没有任何实测依据，模拟器降级为 probe-needed，诊断表必须同步。
    downgraded = ("cache.set", "cache.remove") if thin else ()
    buckets = {"exact": [], "conservative": [], "probe-needed": []}
    for name in sorted(caps):
        level = "probe-needed" if name in downgraded else caps[name]["accuracy"]
        buckets[level].append(name)
    legend = contract["accuracyLevels"]
    profile_info = contract["profiles"][profile]
    rows = [
        '<div class="frag-warn" data-preview-accuracy="summary">'
        'PROFILE <b>%s</b>（%s，accuracy=<b>%s</b>）｜契约 v%s｜'
        '能力 %d 项：exact %d ／ conservative %d ／ probe-needed %d'
        '</div>' % (html_mod.escape(profile), html_mod.escape(profile_info["label"]),
                    html_mod.escape(profile_info["accuracy"]),
                    html_mod.escape(contract["contractVersion"]), len(caps),
                    len(buckets["exact"]), len(buckets["conservative"]),
                    len(buckets["probe-needed"]))
    ]
    for level in ("exact", "conservative", "probe-needed"):
        if not buckets[level]:
            continue
        # data-preview-bucket 专门标「能力桶」那几行：其它带 accuracy 标签的说明行
        # （如 Markdown probe-needed 告警）不带这个属性，便于精确定位与断言。
        rows.append('<div class="frag-warn" data-preview-accuracy="%s" '
                    'data-preview-bucket="%s"><b>%s</b>（%s）：%s</div>'
                    % (level, level, html_mod.escape(level),
                       html_mod.escape(legend[level]),
                       html_mod.escape("、".join(buckets[level]))))
    rows.append('<div class="frag-warn" data-preview-accuracy="probe-needed">'
                'probe-needed 一律<b>不代表已精确模拟</b>：Markdown 管线只做保守预警，'
                '真实取值必须回真实聊天页验证。</div>')
    rows.append('<div class="frag-warn" data-preview-accuracy="not-simulated">'
                'NOT SIMULATED（须真实站验证）：%s</div>'
                % html_mod.escape("；".join(contract["notSimulated"]["requiresRealSite"])))
    return "".join(rows)


# 三面板专用「扁平壳」CSS：与全景共用同一批实测取值，但去掉 fixed 定位与视口高度，
# 让诊断 iframe 仍能靠 body.scrollHeight 自动撑高。
#
# 🚨 与全景壳的区别只有**布局**（fixed→静态流、100%高→auto），**取值一律照抄实测**：
# 主题变量、rem 缩放律、气泡 padding/圆角/opacity、以及最要紧的 white-space:pre-line。
# 别为了"面板看着紧凑"改这些数 —— 三面板是单组件体检台，量错了后面全景也白搭。
# 顶栏/底栏/弹窗**故意不放**：那些属于组合审核，是全景的职责，放进来只会干扰单组件诊断。
MMD_PANEL_SHELL_CSS = """html{font-size:%(rootfont)s}
html,body{margin:0;width:100%%;
  font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
body{font-size:16px;background-color:var(--background-color,#17181A);%(themevars)s}
*{margin:0;-webkit-tap-highlight-color:transparent}
uni-view,uni-scroll-view,uni-image,uni-text{display:block}
/* 层级与类名照真机，但改静态流（fixed 会让诊断 iframe 撑不起高度） */
.chat .chat-scope-box{position:static;width:100%%}
.chat .chat-scope-box .scroll-view{position:static;margin:0;height:auto;background:rgba(0,0,0,0)}
.chat .chat-scope-box .scroll-view .chat-body{position:relative;padding-bottom:0;
  display:flex;flex-direction:column;font-size:15px}
.chat .chat-scope-box .scroll-view .chat-body .item{display:flex;align-items:center;
  padding:0.71875rem 0.9375rem}
.chat .chat-scope-box .scroll-view .chat-body .item .left{background-color:#fff;
  border-radius:1rem 1rem 1rem 0!important}
.chat .chat-scope-box .scroll-view .chat-body .item .right{background-color:#c2dcff;
  border-radius:1rem 1rem 0!important}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope{position:relative;
  max-width:94%%;color:var(--chat-content-font-color,#FFFFFF)}
/* 🚨 pre-line 是「换行空白条」真因，三面板必须带 —— 少了它单组件阶段查不出来 */
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content{padding:0.75rem;
  background:var(--background-color,#17181A);opacity:.9;
  box-shadow:0 0.125rem 0.125rem rgba(0,0,0,.01);border-radius:0.5rem;white-space:pre-line}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table{
  border-collapse:collapse;empty-cells:show;overflow:auto;border-spacing:0;display:block;
  word-break:keep-all;width:100%%}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table th{font-weight:600}
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table td,
.chat .chat-scope-box .scroll-view .chat-body .item .touch-scope .content table th{
  padding:6px 13px;border:1px solid #dfe2e5;word-break:normal;white-space:nowrap}
/* 悬浮组件面板：组件多用 position:fixed 挂 body，给个最小视口高度好让它们有处可去 */
body{min-height:220px}"""


def _mmd_panel_shell_css():
    """三面板用的扁平壳（与全景共用实测取值，布局改静态流）。"""
    themevars = "".join("%s:%s;" % (k, v) for k, v in MMD_THEME_VARS_DARK.items())
    return MMD_PANEL_SHELL_CSS % {"rootfont": MMD_ROOT_FONT_SIZE, "themevars": themevars}


def _mmd_panorama_css():
    """把实测主题变量与 rem 缩放律填进 MMD 外壳 CSS。

    主题变量写在 body 规则里（真机是 body 内联 style，样式表规则等效且可被作者
    的全局美化用 !important 压过，与真机一致）。"""
    themevars = "".join("%s:%s;" % (k, v) for k, v in MMD_THEME_VARS_DARK.items())
    return MMD_PANORAMA_CSS % {"rootfont": MMD_ROOT_FONT_SIZE, "themevars": themevars}


# 弹窗仿真节点（实测复刻，2026-08-28 逐个点开抓取）。
# 全局美化会打到这些面板，作者必须能在预览里看到自己的 CSS 有没有波及/漏掉它们。
# 默认全部关闭（真机也是关的），由外层工具栏按钮切 data-open。
#
# 🚨 三件必须照抄真机的事，别"优化"掉：
#   1. `.u-popup__content` 保留框架基线白底（实测 `background-color:#fff`）。深色是各面板
#      自己的 scope 或内联 style 覆盖出来的 —— 作者漏改某个面板时真机会露白，预览得能重现。
#   2. 「模型设置/对话设置/用户人设/分享」z-index 10075，但「总结剧情」是 1000000000
#      （实测差 5 个数量级）。组件层级参照必须区分这两档。
#   3. 用户人设那套用 `--lo*` 变量族，实测 18 个全部「引用但从未定义」，恒走 fallback。
#      预览**故意不定义**它们 —— 好让作者在预览阶段就发现"改 --lo* 没反应"。
MMD_POPUP_SIM = (
    # ── 模型设置：slide-up 半屏，scope 自带底色 ──
    '<uni-view class="u-popup pano-sheet" data-sheet="model" data-open="off">'
    '<uni-view class="u-transition pano-sheet-mask" data-pano-sheet-close="model"></uni-view>'
    '<uni-view class="u-transition" style="position:fixed;left:0;bottom:0;width:100%">'
    '<uni-view class="u-popup__content" '
    'style="flex:1;border-top-left-radius:10px;border-top-right-radius:10px">'
    '<uni-view class="model-setting-scope theme-dark">'
    '<uni-view class="mp-top"><uni-view class="mp-title">模型设置</uni-view>'
    '<uni-view class="mp-close" data-pano-sheet-close="model">&#215;</uni-view></uni-view>'
    '<uni-view class="mp-info-bar"><uni-view class="mp-model-name">gemini-3.1-pro</uni-view>'
    '<uni-view class="mp-energy-pill"><uni-text class="mp-ev">45</uni-text>'
    '<uni-text class="mp-el">电量</uni-text></uni-view></uni-view>'
    '<uni-scroll-view class="mp-setting-body">'
    '<uni-view class="mp-card"><uni-view class="mp-card-head">'
    '<uni-view class="mp-card-title">上下文长度</uni-view></uni-view>'
    '<uni-view class="mp-tokens">'
    '<uni-view class="mp-token-btn">4K</uni-view>'
    '<uni-view class="mp-token-btn selected">8K</uni-view>'
    '<uni-view class="mp-token-btn">16K</uni-view>'
    '<uni-view class="mp-token-btn">32K</uni-view>'
    '</uni-view></uni-view>'
    '<uni-view class="mp-switch-row"><uni-view class="mp-sw-left">'
    '<uni-view class="mp-sw-title">流式输出</uni-view>'
    '<uni-view class="mp-sw-desc">逐字返回，体验更流畅</uni-view></uni-view></uni-view>'
    '</uni-scroll-view>'
    '<uni-view class="bottom"><uni-view class="btn">确定</uni-view></uni-view>'
    '</uni-view><uni-view class="u-safe-bottom u-safe-area-inset-bottom"></uni-view>'
    '</uni-view></uni-view></uni-view>'
    # ── 对话设置：scope 透明，底色由 content 内联给；无圆角 ──
    '<uni-view class="u-popup pano-sheet" data-sheet="conv" data-open="off">'
    '<uni-view class="u-transition pano-sheet-mask" data-pano-sheet-close="conv"></uni-view>'
    '<uni-view class="u-transition" style="position:fixed;left:0;bottom:0;width:100%">'
    '<uni-view class="u-popup__content" style="flex:1;background-color:#17181A">'
    '<uni-view class="conv-style-modal">'
    '<uni-view class="cs-modal-header">'
    '<uni-view class="cs-header-left" data-pano-sheet-close="conv">取消</uni-view>'
    '<uni-view class="cs-header-center"><uni-view class="cs-header-title">对话设置</uni-view></uni-view>'
    '<uni-view class="cs-header-right" data-pano-sheet-close="conv">确定</uni-view></uni-view>'
    '<uni-view class="cs-modal-content"><uni-scroll-view class="outer-scroll-view">'
    '<uni-view class="summary-card">对话样式设置项（预览占位）</uni-view>'
    '</uni-scroll-view></uni-view>'
    '</uni-view><uni-view class="u-safe-bottom u-safe-area-inset-bottom"></uni-view>'
    '</uni-view></uni-view></uni-view>'
    # ── 总结剧情：z-index 1000000000（实测，比别的高 5 个数量级）──
    '<uni-view class="u-popup pano-sheet" data-sheet="summary" data-open="off">'
    '<uni-view class="u-transition pano-sheet-mask" data-pano-sheet-close="summary"></uni-view>'
    '<uni-view class="u-transition" style="position:fixed;left:0;bottom:0;width:100%">'
    '<uni-view class="u-popup__content" '
    'style="flex:1;border-top-left-radius:10px;border-top-right-radius:10px">'
    '<uni-view class="summary-sheet theme-dark">'
    '<uni-view class="summary-top"><uni-text class="summary-top-title">记忆管理面板</uni-text>'
    '<uni-view class="summary-close" data-pano-sheet-close="summary">&#215;</uni-view></uni-view>'
    '<uni-scroll-view class="summary-body">'
    '<uni-view class="summary-label"><uni-text>剧情总结</uni-text></uni-view>'
    '<uni-view class="summary-card">总结内容（预览占位）</uni-view>'
    '</uni-scroll-view>'
    '<uni-view class="summary-footer bottom">'
    '<uni-view class="summary-save-btn btn">保存</uni-view></uni-view>'
    '</uni-view><uni-view class="u-safe-bottom u-safe-area-inset-bottom"></uni-view>'
    '</uni-view></uni-view></uni-view>'
    # ── 用户人设：--lo* 变量族（故意不定义，照真机走 fallback）──
    '<uni-view class="u-popup pano-sheet" data-sheet="role" data-open="off">'
    '<uni-view class="u-transition pano-sheet-mask" data-pano-sheet-close="role"></uni-view>'
    '<uni-view class="u-transition" style="position:fixed;left:0;bottom:0;width:100%">'
    '<uni-view class="u-popup__content" style="flex:1">'
    '<uni-view class="role-profile-modal">'
    '<uni-view class="header-scope"><uni-view class="header-box">'
    '<uni-view class="icon-back" data-pano-sheet-close="role">取消</uni-view>'
    '<uni-view class="page-title">用户人设</uni-view>'
    '<uni-view class="complete-btn" data-pano-sheet-close="role">保存</uni-view>'
    '</uni-view></uni-view>'
    '<uni-view class="role-setting">'
    '<uni-view class="switch-card"><uni-view>'
    '<uni-view class="switch-title">启用用户人设</uni-view>'
    '<uni-view class="switch-desc">开启后 AI 会参考你的人设</uni-view></uni-view></uni-view>'
    '<uni-view class="card"><uni-view class="card-title">人设内容</uni-view>'
    '<uni-view class="card-desc">描述你扮演的角色</uni-view>'
    '<uni-view class="textarea-dark">（预览占位）</uni-view></uni-view>'
    '</uni-view>'
    '</uni-view><uni-view class="u-safe-bottom u-safe-area-inset-bottom"></uni-view>'
    '</uni-view></uni-view></uni-view>'
    # ── 分享：矮条 + 框架自带右上角关闭钮 ──
    '<uni-view class="u-popup pano-sheet" data-sheet="share" data-open="off">'
    '<uni-view class="u-transition pano-sheet-mask" data-pano-sheet-close="share"></uni-view>'
    '<uni-view class="u-transition" style="position:fixed;left:0;bottom:0;width:100%">'
    '<uni-view class="u-popup__content" style="flex:1">'
    '<uni-view class="u-status-bar u-safe-area-inset-top"></uni-view>'
    '<uni-view class="share-popup">'
    '<uni-view class="share-title">分享角色</uni-view>'
    '<uni-view class="share-sub-title">https://www.sexyai.ai/</uni-view>'
    '<uni-view class="gen-link-btn">生成链接</uni-view>'
    '</uni-view>'
    '<uni-view class="u-popup__content__close u-popup__content__close--top-right" '
    'data-pano-sheet-close="share">&#10005;</uni-view>'
    '<uni-view class="u-safe-bottom u-safe-area-inset-bottom"></uni-view>'
    '</uni-view></uni-view></uni-view>'
    # ── AI帮聊说明：居中 dialog（未点真机，按既有 DOM/CSS 仿真）──
    '<uni-view class="u-popup pano-dialog" data-sheet="alert" data-open="off">'
    '<uni-view class="u-transition pano-sheet-mask" data-pano-sheet-close="alert"></uni-view>'
    '<uni-view class="u-transition" style="position:relative">'
    '<uni-view class="u-popup__content u-popup__content--round-center">'
    '<uni-view class="alert-scope">'
    '<uni-view class="alert-title">AI帮聊功能介绍</uni-view>'
    '<uni-view class="alert-content">AI帮聊：不知道怎么回？让AI做你的嘴替！</uni-view>'
    '<uni-view class="alert-checkbox"><uni-view class="checkbox-box"></uni-view>'
    '<uni-text>不再提示</uni-text></uni-view>'
    '<uni-view class="alert-bottom alert-bottom-double">'
    '<uni-view class="cancel-btn" data-pano-sheet-close="alert">取消</uni-view>'
    '<uni-view class="ok-btn" data-pano-sheet-close="alert">确定</uni-view>'
    '</uni-view></uni-view>'
    '<uni-view class="u-safe-bottom u-safe-area-inset-bottom"></uni-view>'
    '</uni-view></uni-view></uni-view>'
    # 「新的聊天」确认弹窗（快捷栏 onShortcutNewChat → 居中 dialog，复用 alert-scope 样式）。
    # 实测点「新的聊天」是独立动作(非指令栏)；预览用确认框占位，走宿主真实副作用不模拟。
    '<uni-view class="u-popup pano-dialog" data-sheet="newchat" data-open="off">'
    '<uni-view class="u-transition pano-sheet-mask" data-pano-sheet-close="newchat"></uni-view>'
    '<uni-view class="u-transition" style="position:relative">'
    '<uni-view class="u-popup__content u-popup__content--round-center">'
    '<uni-view class="alert-scope">'
    '<uni-view class="alert-title">开启新的聊天</uni-view>'
    '<uni-view class="alert-content">确定要开启新的聊天吗？当前对话会被保存到历史。</uni-view>'
    '<uni-view class="alert-bottom alert-bottom-double">'
    '<uni-view class="cancel-btn" data-pano-sheet-close="newchat">取消</uni-view>'
    '<uni-view class="ok-btn" data-pano-sheet-close="newchat">确定</uni-view>'
    '</uni-view></uni-view>'
    '<uni-view class="u-safe-bottom u-safe-area-inset-bottom"></uni-view>'
    '</uni-view></uni-view></uni-view>'
)


# 弹窗/面板开关脚手架：预览工具自带，非被测产物。走 img onerror 与 MMD 载体一致。
# 暴露 window.__panoPanels 给外层工具栏与 GUI 测试调用。
MMD_PANEL_SCAFFOLD = (
    '<img src="x" data-pano-panel-scaffold="1" style="display:none" '
    "onerror=\"(function(){"
    "var D=document;"
    "var closeAll=function(){"
    "var l=D.querySelectorAll('[data-sheet]');"
    "for(var i=0;i<l.length;i++){l[i].setAttribute('data-open','off');}};"
    # 🚨 属性用双引号包裹 → 内部禁裸双引号（mmd.md §2 红线，初版在此踩坑：
    # `[data-sheet=\"'+name+'\"]` 里的 `"` 提前闭合属性，onerror 被截断到 230 字符 →
    # SyntaxError 静默吞掉 → 面板开关整个不工作、只留一个残留 img。
    # 修法：CSS 属性选择器的值是合法标识符时可**不加引号**，彻底避开引号问题。
    "var open=function(name){closeAll();"
    "var el=D.querySelector('[data-sheet='+name+']');"
    "if(el){el.setAttribute('data-open','on');}return !!el;};"
    # 「+」更多面板开合。复刻真机三件事：
    #  ① 面板排在 .send-msg **之后** → 展开时输入框被往上顶（底栏 105→422px，实测）。
    #  ② 图标随开合换图（真机 ico_more_dark ⇄ ico_more_called_dark，都是"灰圈里的±号"）
    #     → 预览用 CSS 画灰圈、JS 只换圈内字形 +(43)⇄−(8722)，
    #     并同步 .more-options-scope 的 data-more，好让作者用属性选择器判开合。
    #  ③ 真机关态 `.more-scope` 是 **v-if 节点不存在**，不是 display:none —— 所以这里
    #     用 data-open 之外还挂 data-vif-absent 提示；作者若拿 querySelector('.more-scope')
    #     判开合，预览与真机结论会相反（预览恒命中）。判据请用 data-more。
    "var toggleMore=function(){var m=D.querySelector('.more-scope');if(!m)return false;"
    "var on=m.getAttribute('data-open')!=='on';"
    "m.setAttribute('data-open',on?'on':'off');"
    "var mo=D.querySelector('.more-options-scope');"
    "if(mo){mo.setAttribute('data-more',on?'on':'off');"
    "var ic=mo.querySelector('.btn-icon');"
    "if(ic){ic.textContent=on?String.fromCharCode(8722):String.fromCharCode(43);}}"
    "return on;};"
    "var toggleInstr=function(){"
    "var sb=D.querySelector('.shortcut-bar'),ib=D.querySelector('.instruction-bar');"
    "if(!sb||!ib)return false;"
    "var on=sb.className.indexOf('hidden')<0;"
    "sb.className=on?'shortcut-bar hidden':'shortcut-bar';"
    "ib.className=on?'instruction-bar':'instruction-bar hidden';return on;};"
    "var l=D.querySelectorAll('[data-pano-sheet-close]');"
    "for(var i=0;i<l.length;i++){l[i].onclick=function(ev){ev.stopPropagation();closeAll();};}"
    "var sc=D.querySelectorAll('.shortcut-btn');"
    # 快捷按钮点击映射（实测 2026-08-29）：模型设置/对话设置/总结剧情/用户人设 → 各自面板；
    # 新的聊天 → 独立确认弹窗(onShortcutNewChat，**不是指令栏**)；仅 选择指令 走指令栏(else)。
    "var map={'\\u6a21\\u578b\\u8bbe\\u7f6e':'model','\\u5bf9\\u8bdd\\u8bbe\\u7f6e':'conv',"
    "'\\u603b\\u7ed3\\u5267\\u60c5':'summary','\\u7528\\u6237\\u4eba\\u8bbe':'role',"
    "'\\u65b0\\u7684\\u804a\\u5929':'newchat'};"
    "for(var j=0;j<sc.length;j++){(function(b){b.onclick=function(ev){ev.stopPropagation();"
    "var t=(b.textContent||'').replace(/^\\s+|\\s+$/g,'');"
    "if(map[t]){open(map[t]);}else{toggleInstr();}};})(sc[j]);}"
    "var mo=D.querySelector('.more-options-scope');"
    "if(mo){mo.onclick=function(ev){ev.stopPropagation();toggleMore();};}"
    "var ai=D.querySelector('.ai-assistant');"
    "if(ai){ai.onclick=function(ev){ev.stopPropagation();open('alert');};}"
    "var bk=D.querySelector('.back-btn');"
    "if(bk){bk.onclick=function(ev){ev.stopPropagation();toggleInstr();};}"
    # ── 开场白点击填入 + 长按菜单 + 状态流转（复刻 2026-08-29 实测）──
    # 实测：点 .prologue-content → 开场白正文进输入框；发送一条 → 开场白消失；
    #       长按消息 → .msg-option-scope 弹出(data-open=on)；回溯 → 开场白重现。
    "var prologue=D.querySelector('.prologue-scope');"
    "var pc=D.querySelector('.prologue-content');"
    "if(pc){pc.style.cursor='pointer';pc.onclick=function(ev){ev.stopPropagation();"
    "var el=D.querySelector('.uni-textarea-textarea');"
    "if(el){el.value=(pc.textContent||'').replace(/^\\s+|\\s+$/g,'');"
    "el.dispatchEvent(new Event('input',{bubbles:true}));}};}"
    # 状态流转切 .chat[data-chat-state]（一次控制 开场白/用户/AI 三块互斥）：
    # sent=发送后(开场白隐、用户+AI显) / initial=初始或回溯后(开场白显、用户+AI隐)。
    "var chatRoot=D.querySelector('.chat');"
    "var setChatState=function(s){if(chatRoot){chatRoot.setAttribute('data-chat-state',s);}return s;};"
    "var hidePrologue=function(){return setChatState('sent');};"
    "var showPrologue=function(){return setChatState('initial');};"
    # 长按菜单：first_mes(kind=first) 仅复制，隐藏 data-only-full 项；常规消息 4 项全显
    "var menu=D.querySelector('.msg-option-scope');"
    "var openMenu=function(kind,text){if(!menu)return false;"
    "var tb=menu.querySelector('.msg-content-text');if(tb){tb.textContent=text||'';}"
    "var full=(kind!=='first');"
    "var onlys=menu.querySelectorAll('[data-only-full]');"
    "for(var i=0;i<onlys.length;i++){onlys[i].style.display=full?'':'none';}"
    "menu.setAttribute('data-open','on');return true;};"
    "var closeMenu=function(){if(menu){menu.setAttribute('data-open','off');}};"
    "if(menu){menu.onclick=function(ev){if(ev.target===menu){closeMenu();}};}"
    # 绑长按到每条消息：描述气泡(avatar-body)=first_mes 仅复制 / .self=用户 / 其余=AI
    "var bindLong=function(it,kind){var tsc=it.querySelector('.touch-scope')||it;"
    "var timer=null;var ct=it.querySelector('.content');"
    "var txt=ct?(ct.textContent||''):'';"
    "var cancel=function(){if(timer){clearTimeout(timer);timer=null;}};"
    "var start=function(){cancel();timer=setTimeout(function(){openMenu(kind,txt);},500);};"
    # harness-only：统一 Pointer Events，避免移动端触摸后补发模拟鼠标二次 start()、残留 timer 误开菜单
    "tsc.addEventListener('pointerdown',start);"
    "tsc.addEventListener('pointerup',cancel);tsc.addEventListener('pointerleave',cancel);"
    "tsc.addEventListener('pointercancel',cancel);};"
    "var mitems=D.querySelectorAll('.chat-body .item');"
    "for(var mi=0;mi<mitems.length;mi++){(function(it){"
    "var kind=it.className.indexOf('avatar-body')>=0?'first':"
    "(it.className.indexOf('self')>=0?'self':'ai');bindLong(it,kind);})(mitems[mi]);}"
    # 回溯项 → 恢复开场白；发送钮 → 隐藏开场白（复刻状态流转，供作者验证美化两态）
    "var backOpt=menu?menu.querySelector('[data-opt=back]'):null;"
    "if(backOpt){backOpt.onclick=function(ev){ev.stopPropagation();showPrologue();closeMenu();};}"
    "var sends=D.querySelectorAll('.pano-send,.pano-send-expanded');"
    "for(var si=0;si<sends.length;si++){sends[si].addEventListener('click',hidePrologue);}"
    # ── 输入框折叠/展开 + 双 textarea 同步（复刻 2026-08-29 实测行为）──
    # 真机是 Vue model 单一真值源：写任一 textarea + 派发 input，另一个同 tick 跟上。
    # 预览用同名 class 的两个节点 + 手动镜像来复现，好让作者验证回填选择器与美化两态。
    #
    # 实测三条（此前预览复刻错了，已改，详见契约 §5d）：
    #  ① 收回是 blur 驱动，不是"点 .chat-body"驱动 —— 真机对页面空白派合成 click
    #     四个目标全部收不回；派 blur 立刻收回。真人点外面能收回是因为焦点被挪走
    #     顺带触发 blur。所以这里绑 blur，不绑 body click：真人点外面照样收回
    #     （浏览器会移焦→触发 blur），而作者用合成 click 试就会跟真机一样收不回。
    #  ② is-multiline 是**高度**判据不是"含换行"判据 —— 实测 120 字零换行同样会加。
    #  ③ 派了 input 事件是**同 tick 立刻**同步；不派事件也会在 ~100ms 被轮询采纳。
    #     所以这里 input 立刻同步，另设 ~100ms 轮询兜底裸赋值，连那个竞态窗口一起复现。
    "var scope=D.querySelector('.chat-input-scope');"
    "var uni=D.querySelector('.uni-textarea');"
    "var tas=D.querySelectorAll('.uni-textarea-textarea');"
    # 高度判据（对齐真机：is-multiline 看渲染行数，不看换行符）。两个坑：
    #  a) 必须量**当前可见**的那个 textarea —— 折叠态 [0] 是 display:none、
    #     scrollHeight 恒 0，量它永远判不出 multiline。
    #  b) textarea 的 scrollHeight **只涨不缩**，内容变短后仍保留涨上去的高度。
    #     所以量之前先把 height 压到 0、读完立刻还原（同 tick 内，无闪烁）。
    # 两个坑本地实测都踩过一次，别简化掉。
    "var isML=function(el,v){"
    "if(v.indexOf(String.fromCharCode(10))>=0)return true;"
    "var m=null;"
    "for(var i=0;i<tas.length;i++){if(tas[i].offsetParent!==null){m=tas[i];break;}}"
    "if(!m)m=el;"
    "if(!m)return false;"
    "var lh=parseFloat((D.defaultView||window).getComputedStyle(m).lineHeight);"
    "if(!lh||isNaN(lh))lh=20;"
    "var prev=m.style.height;"
    "m.style.height='0px';"
    "var sh=m.scrollHeight;"
    "m.style.height=prev;"
    "return sh>lh*1.8;};"
    "var applyCls=function(on,ml){if(!scope)return;"
    "scope.className='chat-input-scope has-toolbar'+(on?' is-expanded':'')+(ml?' is-multiline':'');"
    "if(uni){uni.className='uni-textarea'+(on?' is-expanded':'')+(ml?' is-multiline':'');}};"
    "var setState=function(on){if(!scope)return;"
    "applyCls(on,/is-multiline/.test(scope.className));return on;};"
    "var syncFrom=function(src){if(tas.length<2)return;"
    "var v=src.value;"
    "for(var i=0;i<tas.length;i++){if(tas[i]!==src&&tas[i].value!==v){tas[i].value=v;}}"
    "if(scope){applyCls(/is-expanded/.test(scope.className),isML(tas[0]||src,v));}};"
    "for(var t=0;t<tas.length;t++){(function(el){"
    # 派了 input 事件 → 真机同 tick 落定，这里也立刻同步（不再 setTimeout）
    "el.addEventListener('input',function(){syncFrom(el);});"
    "})(tas[t]);}"
    # 轮询兜底：复现真机"裸赋值 .value 不派事件，约 100ms 后也会被采纳"，
    # 连带那个竞态窗口（窗口内写两次会互相盖）一起可复现。
    "var lastSeen=tas.length?tas[0].value:'';"
    "setInterval(function(){if(!tas.length)return;"
    "for(var i=0;i<tas.length;i++){if(tas[i].value!==lastSeen){"
    "lastSeen=tas[i].value;syncFrom(tas[i]);return;}}},100);"
    "var disp=D.querySelector('.chat-input-collapsed-display');"
    "if(disp){disp.onclick=function(ev){ev.stopPropagation();setState(true);"
    "if(tas[0]){tas[0].focus();}};}"
    # 收回 = 主 textarea 失焦（真机判据）。真人点页面任何地方都会移焦→collapse。
    "if(tas[0]){tas[0].addEventListener('blur',function(){setState(false);});}"
    "window.__panoInput={expand:function(){return setState(true);},"
    "collapse:function(){return setState(false);},"
    "state:function(){return scope?scope.className:null;},"
    "nodes:function(){var o=[];for(var i=0;i<tas.length;i++){"
    "o.push({i:i,val:tas[i].value,visible:tas[i].getBoundingClientRect().height>0});}return o;},"
    "fill:function(v){var el=D.querySelector('.uni-textarea-textarea');if(!el)return null;"
    "el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));return el.value;}};"
    "window.__panoPanels={open:open,closeAll:closeAll,"
    "toggleMore:toggleMore,toggleInstruction:toggleInstr,"
    "openMenu:openMenu,closeMenu:closeMenu,"
    "hidePrologue:hidePrologue,showPrologue:showPrologue,setChatState:setChatState,"
    "chatState:function(){return chatRoot?chatRoot.getAttribute('data-chat-state'):null;},"
    "list:function(){var o=[],l=D.querySelectorAll('[data-sheet]');"
    "for(var i=0;i<l.length;i++){o.push(l[i].getAttribute('data-sheet'));}return o;},"
    "opened:function(){var l=D.querySelectorAll('[data-sheet][data-open=on]');"
    "return l.length?l[0].getAttribute('data-sheet'):null;}};"
    "})()\">"
)


# 外层工具栏的弹窗开关按钮。全局美化必须逐个面板看过 —— 作者常只顾气泡，
# 忘了模型设置/对话设置/用户人设/分享/AI帮聊说明，真机一开面板就露白或错色。
MMD_PANEL_TOOLS = (
    ("model", "模型设置", "slide-up 半屏 · scope 自带底色 · z-index 10075"),
    ("conv", "对话设置", "slide-up 69vh · 底色在 content 内联 · 无圆角"),
    ("summary", "总结剧情", "slide-up 半屏 · z-index 1000000000（比别的高5个数量级）"),
    ("role", "用户人设", "slide-up 69vh · 用 --lo* 变量族（实测18个全未定义，恒走fallback）"),
    ("share", "分享", "矮条 · 框架自带右上角关闭钮"),
    ("alert", "AI帮聊说明", "居中 dialog · .alert-scope · round-center"),
    ("newchat", "新的聊天", "居中确认 dialog · 快捷栏 onShortcutNewChat（独立动作，非指令栏）"),
)


def _mmd_panel_tools_html():
    """MMD 全景专属：弹窗/面板开关按钮（预览工具，非被测产物）。"""
    win = "document.querySelector('.pano-frame').contentWindow"
    parts = ['<span class="preview-tools-label">弹窗仿真</span>']
    for name, label, tip in MMD_PANEL_TOOLS:
        parts.append(
            '<button class="preview-tool" type="button" title="%s" '
            'onclick="%s.__panoPanels.open(\'%s\')">%s</button>'
            % (html_mod.escape(tip, quote=True), win, name, label))
    parts.append(
        '<button class="preview-tool" type="button" title="输入框右侧「+」展开的面板'
        '（在 .chat-bottom 内，不是弹窗；底栏 105px→317px）" '
        'onclick="%s.__panoPanels.toggleMore()">＋更多面板</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="「选择指令」原地替换快捷条'
        '（不是弹窗）" onclick="%s.__panoPanels.toggleInstruction()">指令栏切换</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="长按 AI/用户消息弹出的菜单'
        '（复制/删除/回溯/开启新的故事；first_mes 仅复制）。也可直接长按消息触发" '
        'onclick="%s.__panoPanels.openMenu(\'ai\',\'长按菜单预览（AI 消息四项）\')">长按菜单</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="发送后态：开场白消失，显示 用户消息+AI回复'
        '（被测内容在 AI 回复气泡里）。真机发一条后即此态" '
        'onclick="%s.__panoPanels.setChatState(\'sent\')">发送后态</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="初始/回溯态：显示 first_mes+开场白选择'
        '（用户+AI回复隐藏）。真机回溯消息后回到此态" '
        'onclick="%s.__panoPanels.setChatState(\'initial\')">初始/回溯态</button>' % win)
    parts.append(
        '<button class="preview-tool" type="button" title="关闭所有弹窗" '
        'onclick="%s.__panoPanels.closeAll();%s.__panoPanels.closeMenu()">全部关闭</button>' % (win, win))
    return "".join(parts)


def _mmd_panorama_page(tested_content, hooks, runtime, send_scaffold):
    """MMD 真实聊天页骨架 HTML（实测复刻，2026-08-28）。

    与真机一字对应的层级（去 data-v scope hash）：
      .chat > .topTabbar
            > .chat-scope-box > .scroll-view > .uni-scroll-view-content > .chat-body#msglistview
            > .chat-bottom
            > .mm-left-side-container / .mm-right-side-container
    气泡两种形态都给：`.item.Ai.avatar-body`（首条描述，通栏、对称圆角）与
    `.item.Ai`（普通 AI 消息，带 .modify-btn-scope 小圆钮），再加一条 `.item.self`
    用户消息 —— 三种真机形态齐了，作者才能看出组件在哪种气泡里会挤。

    被测内容放在**普通 AI 气泡**里（真机状态栏就长在这），不放通栏描述气泡。
    真机元素名是 uni-view/uni-scroll-view/uni-image/uni-text（自定义元素，非 div），
    照抄是有意义的：作者若写 `div > .content` 这类子选择器，真机会失配，预览得能暴露。"""
    return (
        '%(runtime)s'
        '%(hoisted)s'
        # ── 真机外层壳（实测契约 §1：div#app > uni-app > uni-page > uni-page-wrapper
        #    > uni-page-body > uni-view.chat）。这层**不是装饰**：桌面型 HUD 的
        #    pageTarget() 按 #app→uni-app→uni-page-body→.page 顺序找"全高祖先"来横向
        #    缩窄、给侧栏腾位；找不到就退回 .chat。而 .chat 只有顶栏一个在流内子节点
        #    （≈45px 高，其余全 fixed），一旦 HUD 对它施加 transform，.chat 就成了
        #    fixed 后代（.chat-scope-box / .chat-bottom）的包含块 → 整个聊天区塌成 45px。
        #    补齐这条全高祖先链后 pageTarget() 命中 #app（全高），transform 落在全高盒上，
        #    fixed 后代仍以视口高解析，桌面 HUD 几何才成立。全高由 MMD_PANORAMA_CSS 里
        #    `#app,uni-app,uni-page,uni-page-wrapper,uni-page-body{height:100%}` 保证。
        #    **不要**为绕开此偏差去改被测 JSON。
        '<div id="app"><uni-app><uni-page><uni-page-wrapper><uni-page-body>'
        '<uni-view class="chat" data-chat-state="sent"%(root)s>'
        # ── 顶栏 ──
        '<uni-view class="page-header-scope">'
        '<uni-view class="topTabbar"%(header)s>'
        '<uni-view class="header-box"><uni-view class="icon-back"%(header_back)s>&#8249;</uni-view></uni-view>'
        '<uni-view class="header-center">'
        '<uni-view class="header-role-img"><uni-view class="pano-avatar-dot"></uni-view></uni-view>'
        '<uni-view class="header-roleName"%(header_title)s>角色名</uni-view>'
        '</uni-view>'
        '<uni-view class="header-icon-meun"%(header_actions)s>'
        '<uni-view class="header-meun header-meun-rating">&#9734;</uni-view>'
        '<uni-view class="header-meun">&#9776;</uni-view>'
        '<uni-view class="header-meun">&#8635;</uni-view>'
        '<uni-view class="header-meun">&#8942;</uni-view>'
        '</uni-view>%(header_extra)s</uni-view></uni-view>'
        '%(statusbar)s'
        # ── 滚动壳（两层，真机所有 chat-body 后代选择器的前缀）──
        '<uni-view class="chat-scope-box">'
        '<uni-scroll-view class="scroll-view dark pano-chat" id="pano-chat"%(messages)s>'
        '<div class="uni-scroll-view"><div class="uni-scroll-view-content">'
        '<uni-view class="chat-body" id="msglistview"%(list)s>'
        # 首条：描述气泡（通栏 + 对称圆角，无尖角）
        '<uni-view><uni-view class="item Ai avatar-body"%(frame)s>'
        '<uni-view class="touch-scope">'
        '<uni-view class="content left">角色描述气泡（通栏形态：touch-scope 满宽、圆角对称 0.5rem）</uni-view>'
        '</uni-view></uni-view></uni-view>'
        # first_mes（角色卡「第一句话」，莉娜开场）：普通 AI 气泡但**无可见圆钮**
        # （实测 modify-btn 存在但 0×0 隐藏）。它一直在顶部（描述气泡之下），两态都显示。
        '<uni-view><uni-view class="item Ai" data-msg="first"%(frame)s>'
        '<uni-view class="touch-scope">'
        '<uni-view class="content left">第一句话（角色开场白正文，无三圆钮，长按仅"复制"）</uni-view>'
        '</uni-view></uni-view></uni-view>'
        # ── 两态互斥（实测状态流转，2026-08-29）──────────────────────────
        # 初始态：first_mes 之后是 .prologue-scope（开场白选择）。
        # 发送一条后：开场白消失，出现 用户消息 + AI回复。回溯则开场白重现。
        # DOM 顺序 = 描述→first_mes→开场白(initial)→用户(sent)→AI回复(sent)，
        # 靠 .chat[data-chat-state] 切 display，隐藏项塌陷，视觉顺序天然正确。
        # 默认 sent（tested 落在 AI 回复气泡里，作者一开预览就看得到被测组件）。
        # 开场白选择块（仅初始态显示）
        '<uni-view class="prologue-scope" data-msg-state="initial">'
        '<uni-view class="prologue-title"><span>你可以选择开场</span></uni-view>'
        '<uni-view class="prologue-content">开场白示例</uni-view>'
        '</uni-view>'
        # 用户消息（.self 右对齐 + .content.right，仅发送后态）。实测 2 圆钮（编辑/分享）靠右下，
        # 无"刷新"钮（用户消息不能重新生成）。图标与 AI 的后两钮同款。
        '<uni-view data-msg-state="sent"><uni-view class="item Ai self"%(frame)s>'
        '<uni-view class="touch-scope"%(msg_user)s>'
        '<uni-view class="content right"%(body)s>用户示例消息</uni-view>'
        '<uni-view class="modify-btn-scope">'
        '<uni-view class="modify-btn" title="编辑">&#9998;</uni-view>'
        '<uni-view class="modify-btn" title="分享">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle>'
        '<circle cx="18" cy="19" r="3"></circle>'
        '<line x1="8.6" y1="13.5" x2="15.4" y2="17.5"></line>'
        '<line x1="15.4" y1="6.5" x2="8.6" y2="10.5"></line></svg>'
        '</uni-view>'
        '</uni-view>'
        '</uni-view></uni-view></uni-view>'
        # 被测内容：普通 AI 气泡（真机状态栏/组件的落点，仅发送后态）
        '<uni-view data-msg-state="sent"><uni-view class="item Ai"%(frame)s>'
        '<uni-view class="select-box" style="display:none"></uni-view>'
        '<uni-view class="touch-scope" id="item0"%(msg_ai)s>'
        '<uni-view class="content left" id="q-1"%(body)s>%(tested)s</uni-view>'
        # AI 消息 3 圆钮（实测 2026-08-29）：刷新(重新生成) / 编辑 / 分享。
        # 第三钮真机是分享图标（旧预览误画成实心圆 ●）。
        '<uni-view class="modify-btn-scope">'
        '<uni-view class="modify-btn" title="刷新（重新生成）">&#8635;</uni-view>'
        '<uni-view class="modify-btn" title="编辑">&#9998;</uni-view>'
        '<uni-view class="modify-btn" title="分享">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle>'
        '<circle cx="18" cy="19" r="3"></circle>'
        '<line x1="8.6" y1="13.5" x2="15.4" y2="17.5"></line>'
        '<line x1="15.4" y1="6.5" x2="8.6" y2="10.5"></line></svg>'
        '</uni-view>'
        '</uni-view>%(message_extra)s%(message_actions)s'
        '</uni-view></uni-view></uni-view>'
        '<uni-view id="chatBottom"></uni-view>'
        '</uni-view></div></div></uni-scroll-view></uni-view>'
        # 官方侧边挂载点（悬浮组件靶位）
        '<uni-view class="mm-left-side-container"></uni-view>'
        '<uni-view class="mm-right-side-container"></uni-view>'
        '%(stage)s'
        # ── 底部：快捷条 + 输入区 ──
        '<uni-view class="chat-bottom"%(composer)s>'
        '%(toolbar)s'
        # 快捷条与指令栏互斥（真机「选择指令」原地替换，不是弹窗）
        '<uni-view class="shortcut-bar-wrapper theme-dark"><uni-view class="shortcut-bar">'
        '<button class="shortcut-btn" type="button">模型设置</button>'
        '<button class="shortcut-btn" type="button">对话设置</button>'
        '<button class="shortcut-btn" type="button">选择指令</button>'
        '<button class="shortcut-btn" type="button">总结剧情</button>'
        '<button class="shortcut-btn" type="button">新的聊天</button>'
        '<button class="shortcut-btn" type="button">用户人设</button>'
        '</uni-view>'
        '<uni-view class="instruction-bar hidden">'
        '<uni-view class="back-btn"><uni-text class="back-arrow">&#8249;</uni-text></uni-view>'
        '<uni-scroll-view class="instruction-scroll">'
        '<uni-view class="instruction-chip">清空输入框</uni-view>'
        '<uni-view class="instruction-chip">通用总结</uni-view>'
        '<uni-view class="instruction-chip">选项生成</uni-view>'
        '<uni-view class="instruction-chip">字数控制</uni-view>'
        '<uni-view class="instruction-chip">人称转换</uni-view>'
        '</uni-scroll-view></uni-view></uni-view>'
        '<uni-view class="chat-bottom-wapper">'
        '%(sendmsg)s'
        # 「+」展开的更多面板：在 .chat-bottom 内（不是弹窗），11 项 4 列。
        # 🚨 位置在 `.send-msg` **之后** —— 面板在输入框下方、把输入框往上顶（实测）。
        # 排到前面会变成"面板在输入框上方"，和真机相反。
        '<uni-view class="more-scope" data-open="off">'
        '<uni-view class="item"><uni-view class="item-icon">&#8635;</uni-view>'
        '<uni-view class="item-title">重置聊天</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#8681;</uni-view>'
        '<uni-view class="item-title">导出聊天</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9998;</uni-view>'
        '<uni-view class="item-title">新的聊天</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9881;</uni-view>'
        '<uni-view class="item-title">编辑角色</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9634;</uni-view>'
        '<uni-view class="item-title">更换背景</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9776;</uni-view>'
        '<uni-view class="item-title">自定义指令</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9786;</uni-view>'
        '<uni-view class="item-title">用户人设</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9744;</uni-view>'
        '<uni-view class="item-title">设定补充</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9636;</uni-view>'
        '<uni-view class="item-title">对话设置</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">&#9635;</uni-view>'
        '<uni-view class="item-title">剧情总结</uni-view></uni-view>'
        '<uni-view class="item"><uni-view class="item-icon">?</uni-view>'
        '<uni-view class="item-title">游玩教程</uni-view></uni-view>'
        '</uni-view>'
        '</uni-view></uni-view>'
        # 长按菜单（实测 2026-08-29）：默认 display:none，长按消息 → data-open=on 弹出。
        # 内容框显示被长按消息正文；选项框 4 项。first_mes 长按仅"复制"（其余项 data-only-full
        # 由 runtime 按消息类型隐藏），常规 AI/用户消息 4 项全显。
        '<uni-view class="msg-option-scope" data-open="off">'
        '<uni-view class="msg-content-box"><uni-view class="msg-content-text"></uni-view></uni-view>'
        '<uni-view class="msg-options-box">'
        '<uni-view class="option-item" data-opt="copy">'
        '<uni-text><span>复制</span></uni-text><uni-view class="opt-icon">&#10697;</uni-view></uni-view>'
        '<uni-view class="option-separator" data-only-full="1"></uni-view>'
        '<uni-view class="option-item" data-opt="delete" data-only-full="1">'
        '<uni-text><span>删除</span></uni-text><uni-view class="opt-icon">&#10005;</uni-view></uni-view>'
        '<uni-view class="option-separator" data-only-full="1"></uni-view>'
        '<uni-view class="option-item" data-opt="back" data-only-full="1">'
        '<uni-text><span>回溯</span></uni-text><uni-view class="opt-icon">&#8617;</uni-view></uni-view>'
        '<uni-view class="option-separator" data-only-full="1"></uni-view>'
        '<uni-view class="option-item" data-opt="newstory" data-only-full="1">'
        '<uni-text><span>开启新的故事</span></uni-text><uni-view class="opt-icon">&#9282;</uni-view></uni-view>'
        '</uni-view></uni-view>'
        # 弹窗体系仿真（默认全关，真机也是关的）
        '%(popupsim)s'
        '</uni-view>'
        # 关闭真机外层壳（uni-page-body > uni-page-wrapper > uni-page > uni-app > #app）
        '</uni-page-body></uni-page-wrapper></uni-page></uni-app></div>'
        '%(sendscaffold)s'
        '%(panelscaffold)s'
    ) % dict(hooks, runtime=runtime, tested=tested_content,
             statusbar="", hoisted="", sendscaffold=send_scaffold,
             popupsim=MMD_POPUP_SIM, panelscaffold=MMD_PANEL_SCAFFOLD,
             sendmsg=MMD_SEND_MSG_HTML % dict(hooks))


# 输入区（`.send-msg`）：单独拆出来，好让 `.more-scope` 能排在它**之后**（实测顺序）。
MMD_SEND_MSG_HTML = (
        '<uni-view class="send-msg">'
        '<uni-view class="uni-textarea">'
        # 输入框左侧 AI帮聊入口（💡）—— 点它开 .alert-scope 居中 dialog
        '<uni-view class="ai-assistant">&#128161;'
        '<uni-view class="beta-badge">10</uni-view></uni-view>'
        # 输入框：实测是**两个 textarea 互相让位**（不是一个节点变高）。
        # DOM 顺序恒定 [0]主 / [1]折叠预览，变的只是谁可见；class 两个都叫
        # `.uni-textarea-textarea chatMsgTextarea`，所以 querySelector 永远命中 [0]。
        # 折叠态下 [0] 不可见 —— 引擎回填仍然有效（Vue model 双向同步），预览照此复刻。
        '<uni-view class="chat-input-scope has-toolbar">'
        # 恒隐藏的发送代理（真机内联 display:none;0×0;absolute，两种状态都在）
        '<uni-image class="btn-icon chat-send-proxy" '
        'style="display:none;width:0;height:0;position:absolute"></uni-image>'
        # 工具条：仅展开态可见
        '<uni-view class="chat-input-toolbar">'
        '<uni-view class="chat-input-tool-btn">粘贴</uni-view>'
        '<uni-view class="chat-input-tool-btn">清空</uni-view>'
        '</uni-view>'
        # [0] 主 textarea：仅展开态可见
        '<uni-textarea class="chatMsgTextarea">'
        '<textarea class="uni-textarea-textarea" rows="1" '
        'placeholder="快来聊天吧~"%(input)s></textarea>'
        '</uni-textarea>'
        # 折叠行：含 [1] 预览 textarea 与折叠态发送按钮
        '<uni-view class="chat-input-collapsed-row">'
        '<uni-view><uni-view class="mind-type">45</uni-view></uni-view>'
        '<uni-view class="chat-input-collapsed-display">'
        '<uni-textarea class="chatMsgTextarea chat-input-collapsed-preview">'
        '<textarea class="uni-textarea-textarea" rows="1" placeholder="快来聊天吧~"></textarea>'
        '</uni-textarea></uni-view>'
        # 带 btn-icon：真机发送钮就是 uni-image.btn-icon，作者用
        # `.btn-icon:not(.chat-send-proxy)` + offsetParent 筛可见钮的写法要能在预览里测通。
        '<uni-view><button class="pano-send send-btn btn-icon" type="button" '
        'title="发送（折叠态）"%(send)s>'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="22" y1="2" x2="11" y2="13"></line>'
        '<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>'
        '</button></uni-view>'
        '</uni-view>'
        # 展开行：展开态的发送按钮
        '<uni-view class="chat-input-bottom-row">'
        '<uni-view><uni-view class="mind-type">45</uni-view></uni-view>'
        '<uni-view><button class="pano-send-expanded send-btn btn-icon" type="button" '
        'title="发送（展开态）">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="22" y1="2" x2="11" y2="13"></line>'
        '<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>'
        '</button></uni-view>'
        '</uni-view>'
        '</uni-view>'
        # 「+」更多入口：真机是 .chat-input-scope 的兄弟节点，两态都在输入框右侧外部。
        # data-more 由脚手架切 on/off，好复刻真机换图标（＋ ⇄ ⊖）。
        '<uni-view class="more-options-scope" data-more="off">'
        '<uni-view class="btn-icon">&#43;</uni-view></uni-view>'
        '</uni-view></uni-view>'
    )


def _panorama_hooks(platform):
    """沙盒模式返回官方 data-* 钩子；其余平台全为空串（骨架一字不变）。"""
    keys = ("root", "header", "header_back", "header_title", "header_actions",
            "header_extra", "messages", "list", "frame", "msg_user", "msg_ai",
            "body", "message_extra", "message_actions", "stage", "composer",
            "toolbar", "input", "send",
            # 2026-08-29 实测补齐
            "shortcut", "instruction_bar", "instruction_back", "instruction_chip",
            "assistant", "assistant_tip", "model_chip")
    if platform != "mmdsandbox":
        return {k: "" for k in keys}
    return dict(_SANDBOX_HOOKS)


# ── 沙盒模式设计令牌：实测 29 个（2026-08-29 真机 CSSOM）─────────────────────
# 依据：Playwright 进真实卡片 iframe（c<roleId>.sbx.aitchat.org）读 styleSheets，
# 平台把两套值分别定义在 [data-theme="dark"] / [data-theme="light"]，各 29 条，
# **没有 :root 定义**。完整契约见 references/platforms/mmd-sandbox-real-page-contract-2026-08-29.md
#
# 🚨 历史修正：这里曾只列 14 个，漏了 15 个 —— 其中整个 `--chat-modal-*` 族（9 个）
# 与 `--chat-composer-*`/`--chat-shortcut-bg`/`--chat-input-placeholder`/`--chat-input-border`
# 都是**真机可用**的。官方《角色卡制作手册》把后 18 个称作「底栏和白名单弹窗」变量，
# 与本次实测完全一致（18/18 逐个注入醒目色验证生效）。少注入它们 → 预览塌样式而真机
# 正常，作者会去"修"一个不存在的 bug。
#
# 分两组是**语义**差异，不是证据等级差异（两组都是实测）：
#   气泡组（前 10 个，含 viewport-height）：改了会带动整页与气泡。
#   白名单组（后 18 个）：只换底栏与「+」更多面板等 iframe 内浮层，**不动**气泡语义色，
#   也不动图标（图标是 <img>，改不了）。
SANDBOX_BUBBLE_TOKENS = (
    "--chat-bg", "--chat-surface", "--chat-text", "--chat-text-muted",
    "--chat-border", "--chat-accent",
    "--chat-bubble-user-bg", "--chat-bubble-ai-bg", "--chat-bubble-text",
    "--chat-share-pick-bg",
)

# 官方手册「底栏和白名单弹窗另有 18 个变量」——逐个实测生效（见上方注释）。
SANDBOX_WHITELIST_TOKENS = (
    "--chat-composer-bg", "--chat-composer-text",
    "--chat-shortcut-bg", "--chat-shortcut-text",
    "--chat-input-bg", "--chat-input-text",
    "--chat-input-placeholder", "--chat-input-border",
    "--chat-modal-bg", "--chat-modal-surface",
    "--chat-modal-text", "--chat-modal-muted", "--chat-modal-accent",
    "--chat-modal-input-bg", "--chat-modal-input-text",
    "--chat-modal-cancel-bg", "--chat-modal-btn-bg", "--chat-modal-btn-border",
)

# `--chat-more-item-bg` 实测是 `var(--chat-modal-surface)` 的**别名**（两套主题都是），
# 平台自己这么定义的，作者可直接覆盖，故一并计入。
SANDBOX_DESIGN_TOKENS = (
    SANDBOX_BUBBLE_TOKENS + SANDBOX_WHITELIST_TOKENS + ("--chat-more-item-bg",)
)

# 沙盒模式 14 个设计令牌的预览默认值。定义在 [data-chat="root"] 上，作者换肤改变量、
# 用 var() 取色在预览里行为一致。
# 归属说明（实测）：平台真身把两套值分别定义在 [data-theme=dark] / [data-theme=light]
# 上，**没有 :root 定义**。预览这里把浅色一套放在无 data-theme 的基底规则上、深色一套
# 放在 [data-theme="dark"] 覆盖规则上，效果等价且省一份重复。
#
# 🚨 证据等级（别混淆，也别为了"好看"改回失真值）：
#   深浅两套 **各 29 个全部是【实测】真值**（2026-08-29 抓 [data-theme=dark] /
#   [data-theme=light] 两条规则的 cssText，逐字照抄）。浅色不再是类推 —— 旧注释说
#   "探针只覆盖深色、浅色按对应关系类推"，那个状态已经结束。
#   曾经这里放的是好看但失真的值（--chat-bg:#16181d、气泡 #1a7f5a/#22262c），让预览
#   显示出"气泡有独立底色"这个平台并不存在的配色 —— 作者会照着它定状态栏配色，上真机
#   才发现整块糊在背景里。这个谎发生在**设计决策阶段**，代价比"气泡默认看不见"高得多。
#   实测气泡三色是 var(--chat-bg)/var(--chat-text) 的**别名**（两套主题皆然），
#   所以气泡与页面背景恒同色。预览照此还原；视觉分界用预览专属描边解决
#   （见下 data-preview-bubble-outline），不靠篡改令牌取值。
# 🚨 --chat-viewport-height 不计入 29 个：实测它是平台用 JS 写在 root 上的**内联
# style**（实测 900px/860px/857px 随视口高变），不是样式表变量。
# --rpx 同样不计入，但它是平台全部尺寸的基准。实测两档（见 SANDBOX_RPX_* ）。
# 功能栏平台不给样式（实测 [data-slot=statusbar] 只有 flex:0 1 auto），作者需自己写。
SANDBOX_DARK_TOKEN_VALUES = {
    # 【实测】[data-theme="dark"] 规则原文，2026-08-29。测试锁定这份取值，防回退。
    "--chat-bg": "#17181a", "--chat-surface": "#1e1f24", "--chat-text": "#fff",
    "--chat-text-muted": "#c5c5c5", "--chat-border": "#333", "--chat-accent": "#ff6d97",
    # 气泡三色实测是别名（var(--chat-bg)/var(--chat-text)），此处展开为解析后的值。
    "--chat-bubble-user-bg": "#17181a", "--chat-bubble-ai-bg": "#17181a",
    "--chat-bubble-text": "#fff",
    "--chat-share-pick-bg": "#2c2e32",
    # 白名单 18 个（官方手册「底栏和白名单弹窗」，实测逐个生效）
    "--chat-composer-bg": "#17181a", "--chat-composer-text": "#fff",
    "--chat-shortcut-bg": "#2c2e32", "--chat-shortcut-text": "#fff",
    "--chat-input-bg": "#1e1f24", "--chat-input-text": "#fff",
    "--chat-input-placeholder": "#c5c5c5", "--chat-input-border": "#ff6d97",
    "--chat-modal-bg": "#17181a", "--chat-modal-surface": "#2c2e32",
    "--chat-modal-text": "#fff", "--chat-modal-muted": "#c5c5c5",
    "--chat-modal-accent": "#ff6d97",
    "--chat-modal-input-bg": "#1e1f24", "--chat-modal-input-text": "#fff",
    "--chat-modal-cancel-bg": "#ffb7cc", "--chat-modal-btn-bg": "#33353b",
    "--chat-modal-btn-border": "transparent",
    # 实测是 var(--chat-modal-surface) 的别名
    "--chat-more-item-bg": "#2c2e32",
}

SANDBOX_LIGHT_TOKEN_VALUES = {
    # 【实测】[data-theme="light"] 规则原文，2026-08-29。**不再是类推**。
    "--chat-bg": "#fff", "--chat-surface": "#f5f8fc", "--chat-text": "#212226",
    "--chat-text-muted": "#8d949d", "--chat-border": "#e5e7eb", "--chat-accent": "#17aafd",
    "--chat-bubble-user-bg": "#fff", "--chat-bubble-ai-bg": "#fff",
    "--chat-bubble-text": "#212226",
    "--chat-share-pick-bg": "#e6e6e6",
    "--chat-composer-bg": "#fff", "--chat-composer-text": "#212226",
    "--chat-shortcut-bg": "#f1f4f9", "--chat-shortcut-text": "#8d949d",
    "--chat-input-bg": "#f6f8fc", "--chat-input-text": "#333",
    "--chat-input-placeholder": "#8d949d", "--chat-input-border": "#17aafd",
    "--chat-modal-bg": "#fff", "--chat-modal-surface": "#f5f8fc",
    "--chat-modal-text": "#212226", "--chat-modal-muted": "#8d949d",
    "--chat-modal-accent": "#17aafd",
    "--chat-modal-input-bg": "#f6f8fc", "--chat-modal-input-text": "#212226",
    "--chat-modal-cancel-bg": "#f5f8fc", "--chat-modal-btn-bg": "#fff",
    "--chat-modal-btn-border": "#efefef",
    "--chat-more-item-bg": "#f5f8fc",
}

# --rpx 尺寸基准（实测三点 + 断点原文，2026-08-29）：
#   [data-chat="root"]{--rpx:calc(100vw / 750)}
#   @media (min-width:961px){[data-chat="root"]{--rpx:calc(375px / 750)}}
# 实测：视口 298px→单位 298px、400px→400px、1280px→**375px**（桌面封顶）。
# 🚨 旧值是 `@media(min-width:750px){--rpx:1px}` —— 断点与取值双错：真机断点是 961px，
# 且桌面档不是固定 1px 而是 375/750=0.5px。差 2 倍，作者按预览调的尺寸上真机全错。
SANDBOX_RPX_BASE = "calc(100vw / 750)"
SANDBOX_RPX_DESKTOP = "calc(375px / 750)"
SANDBOX_RPX_BREAKPOINT = "961px"

SANDBOX_CHROME_CSS = """html,body{height:100%%;margin:0}
body{display:flex;flex-direction:column;background:#17181a}
.pano-sandbox-host{height:100%%;min-height:0;overflow:hidden;background:#17181a}
/* 🚨 令牌必须挂在**单属性** [data-theme=*] 上（与真机同特异性 0,1,0）。
   曾写成 [data-chat="root"][data-theme="dark"]（0,2,0）→ 作者按手册写
   `[data-chat="root"]{--chat-modal-bg:X}`（0,1,0）在预览里被压过、看着"没生效"，
   而真机两边都是 0,1,0、靠文档顺序作者赢（平台 CSS 在前、作者 hoisted style 在后）。
   这类"预览比真机更严"的假象会让作者去改一个没坏的东西，别改回去。 */
[data-theme="light"]{%(light)s}
[data-theme="dark"]{%(dark)s}
[data-chat="root"]{
  --chat-viewport-height:100vh;--rpx:%(rpxbase)s;
  width:100%%;max-width:100%%;height:var(--chat-viewport-height);min-height:0;
  background-color:var(--chat-bg);color:var(--chat-text);
  display:flex;flex-direction:column;margin:0;position:relative;overflow-x:hidden;overflow-y:auto;
  background-position:center center;background-size:auto 100%%;background-repeat:no-repeat;
  font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;box-sizing:border-box}
[data-chat="root"] *,[data-chat="root"] *:before,[data-chat="root"] *:after{box-sizing:border-box}
[data-chat="header"]{flex:0 0 calc(90 * var(--rpx));min-height:calc(90 * var(--rpx));height:calc(90 * var(--rpx));display:flex;
  align-items:center;justify-content:space-between;padding:0;background:var(--chat-bg);border:0;color:var(--chat-text)}
[data-chat="header-back"]{flex:0 0 auto;width:calc(76 * var(--rpx));height:100%%;display:flex;align-items:center;
  justify-content:center;padding:0 calc(20 * var(--rpx));border:0;background:transparent;color:var(--chat-text);
  font:inherit;font-size:calc(50 * var(--rpx));cursor:pointer}
[data-chat="header-title"]{flex:1 1 0;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;
  font-size:calc(30 * var(--rpx));line-height:1.25;font-weight:500}
/* 🚨 实测尺寸律（2026-08-29）：actions 用 **margin-right:12px（px，不是 rpx）** 且
   gap:normal；间距靠每项 margin-left:25rpx。项本身 35rpx 宽 × 撑满顶栏高，img 35rpx。
   曾写成 gap:8rpx + 52rpx 方钮 —— 桌面档下图标间距和真机差一截。 */
[data-chat="header-actions"]{flex:0 0 auto;display:flex;align-items:center;margin-right:12px}
[data-chat="header-actions"] > button,.pano-head-action{width:calc(35 * var(--rpx));height:100%%;
  margin-left:calc(25 * var(--rpx));display:flex;align-items:center;justify-content:center;padding:0;
  border:0;background:transparent;color:var(--chat-text);font:inherit;
  font-size:calc(30 * var(--rpx));cursor:pointer}
[data-chat="header-actions"] > button > .pano-glyph,.pano-head-action > .pano-glyph{
  width:calc(35 * var(--rpx));height:calc(35 * var(--rpx));font-size:calc(30 * var(--rpx));
  display:flex;align-items:center;justify-content:center;line-height:1}
/* 顶栏第 1 钮（评论）真机是 .header-comments，position:relative —— 给 .rate-tip 定位用。
   .rate-tip 本次未出现（可能有条件），先把定位上下文留出来。 */
[data-chat="header-actions"] .header-comments{position:relative}
[data-chat="header-actions"] .rate-tip{position:absolute;z-index:1}
/* 标题左侧角色头像：实测 50rpx 圆形 + margin-right:5rpx。曾整个漏掉。 */
[data-chat="header-title"] > .pano-title-avatar{width:calc(50 * var(--rpx));height:calc(50 * var(--rpx));
  margin-right:calc(5 * var(--rpx));border-radius:50%%;flex-shrink:0;background:var(--chat-modal-surface);
  display:flex;align-items:center;justify-content:center;font-size:calc(26 * var(--rpx));overflow:hidden}
/* 🚨 实测原文是 :empty 才隐藏。曾写成无条件 display:none —— 作者往 header-extra
   插内容，预览里永远看不见，真机却显示。别改回无条件。 */
[data-slot="header-extra"]:empty{display:none}
[data-slot="statusbar"]{flex:0 1 auto;min-height:0}
[data-chat="messages"]{flex:1 1 auto;min-height:0;overflow:hidden auto;padding:0;background:transparent;
  -webkit-overflow-scrolling:touch}
[data-chat="messages"] [data-chat="list"]{display:block;min-height:100%%;padding:0 0 calc(18 * var(--rpx))}
/* 顶部角色描述块（实测 [data-probe=role-intro]/role-intro-body）：通栏 AI 侧对齐，
   气泡吃 --chat-bg（与普通气泡同色，靠 opacity .9 与背景略分），对称 16rpx 圆角。 */
[data-probe="role-intro"]{box-sizing:border-box;width:100%%;padding:calc(23 * var(--rpx)) calc(30 * var(--rpx));
  flex-direction:column;align-items:flex-start;display:flex}
[data-probe="role-intro-body"]{box-sizing:border-box;width:fit-content;min-width:0;max-width:100%%;
  padding:calc(24 * var(--rpx));border-radius:calc(16 * var(--rpx));
  box-shadow:0 calc(4 * var(--rpx)) calc(4 * var(--rpx)) #00000003;background:var(--chat-bg);opacity:.9;
  white-space:pre-line;overflow-wrap:anywhere;word-break:break-word;color:var(--chat-text);font-size:15px}
/* 消息之间的空隙节点（实测存在，无样式承诺，仅占位不塌） */
[data-chat="list-spacer"]{flex:0 0 auto}
/* 开场白选择块（实测 [data-probe=prologue]）：仅初始态显示。标题是黑底 pill；
   每个 chip 吃 --chat-bg + --chat-text（作者全局美化直接波及，与真机一致），可点注入输入框。 */
[data-probe="prologue"]{padding:0 calc(31 * var(--rpx)) calc(20 * var(--rpx))}
[data-probe="prologue-title"]{text-align:center;margin:0}
[data-probe="prologue-title"] span{border-radius:calc(15 * var(--rpx));font-size:calc(28 * var(--rpx));
  color:#fff;padding:calc(10 * var(--rpx)) calc(20 * var(--rpx));background:rgba(0,0,0,.5);display:inline-block}
[data-probe="prologue-chip"]{box-sizing:border-box;width:100%%;min-height:calc(90 * var(--rpx));
  margin-top:calc(20 * var(--rpx));padding:calc(30 * var(--rpx));border-radius:calc(12 * var(--rpx));
  background:var(--chat-bg);opacity:.9;font-size:calc(26 * var(--rpx));color:var(--chat-text);
  text-align:left;cursor:pointer;border:0;align-items:center;display:flex}
[data-chat="message-frame"]{display:flow-root;margin:0}
[data-chat="message"]{display:flex;flex-direction:column;width:100%%;max-width:100%%;padding:calc(23 * var(--rpx)) calc(30 * var(--rpx));
  margin:0;align-items:flex-start;background:transparent;color:var(--chat-text)}
[data-chat="message"][data-from="user"]{align-items:flex-end}
[data-chat="message"] [data-chat="message-body"]{max-width:90%%;padding:calc(24 * var(--rpx));margin:0;border:0;
  border-radius:calc(32 * var(--rpx)) calc(32 * var(--rpx)) calc(32 * var(--rpx)) 0;
  background:var(--chat-bubble-ai-bg);color:var(--chat-bubble-text);font-size:15px;line-height:1.55;
  white-space:pre-line;opacity:.9;word-break:break-word}
[data-chat="message"][data-from="user"] [data-chat="message-body"]{border-radius:calc(32 * var(--rpx)) calc(32 * var(--rpx)) 0 calc(32 * var(--rpx));
  background:var(--chat-bubble-user-bg)}
/* 头像/昵称：实测 0×0 隐藏（此卡不显示），但节点存在（作者选择器可命中）。 */
[data-chat="message-name"],[data-chat="message-avatar"]{flex:0 0 auto;width:0;height:0;margin:0;padding:0;overflow:hidden}
[data-chat="message-time"]{display:none}
/* message-extra 恒隐藏；message-actions 仅**非空**才显示（实测 :not(:empty)）——
   角色卡「第一句话」actions 为空 → 整块不占位、无三圆钮，与真机一致。 */
[data-slot="message-extra"]{display:block;width:0;height:0;overflow:hidden}
[data-chat="message-actions"]{display:none}
[data-chat="message-actions"]:not(:empty){margin-top:calc(16 * var(--rpx));gap:calc(16 * var(--rpx));display:flex}
/* 三圆钮：实测 48rpx 圆、rgba(0,0,0,.5) 底、img 28rpx。用户消息 2 钮（编辑/分享），
   AI 消息 3 钮（刷新/编辑/分享），第一句话 0 钮。 */
[data-chat="message-actions"] [data-action]{box-sizing:border-box;width:calc(48 * var(--rpx));
  height:calc(48 * var(--rpx));cursor:pointer;background:rgba(0,0,0,.5);border:0;border-radius:50%%;
  justify-content:center;align-items:center;margin:0;padding:0;display:flex;color:#fff}
[data-chat="message-actions"] [data-action] .pano-glyph{width:calc(28 * var(--rpx));height:calc(28 * var(--rpx));
  font-size:calc(24 * var(--rpx));display:flex;align-items:center;justify-content:center;line-height:1}
/* 消息两态互斥（实测状态流转）：初始态显 role-intro? 不——role-intro 两态都在；
   仅 prologue(initial) 与 用户/AI回复(sent) 互斥。顺序恒为
   描述→first_mes→prologue(initial)→用户(sent)→AI回复(sent)，隐藏项塌陷，视觉序自然对。
   默认 data-chat-state=initial（真机新会话首屏即此态：显 first_mes + 开场白选择）。 */
[data-chat="root"][data-chat-state="sent"] [data-msg-state="initial"]{display:none}
[data-chat="root"][data-chat-state="initial"] [data-msg-state="sent"]{display:none}
[data-slot="left"],[data-slot="right"]{position:relative;flex:0 1 auto;min-height:0}
/* 🚨 底栏吃的是 --chat-composer-bg/-text（不是 --chat-bg/--chat-text）。实测原文如此，
   两者默认同色所以肉眼看不出差别 —— 但作者只改 --chat-composer-bg 时，写错会让预览
   毫无反应而真机变色。别"顺手"统一成 --chat-bg。 */
[data-chat="composer"]{position:static;left:auto;right:auto;bottom:auto;flex:0 0 auto;display:flex;
  flex-direction:column;align-items:stretch;gap:0;padding:0;background:var(--chat-composer-bg);border:0;
  color:var(--chat-composer-text);z-index:auto}
[data-slot="toolbar"]{display:block;height:0}
/* ── 底栏：实测复刻（2026-08-29）。官方手册「底栏和白名单弹窗」那 18 个变量的靶点。
   🚨 旧版这里用 .pano-shortcuts/.pano-shortcut/.pano-compose-row/.pano-input-shell 四个
   自造类名，真机对应的是 [data-chat=shortcut] / [data-chat=instruction-bar] /
   .composer-shortcut-wrap / .composer-row / .composer-field。作者按手册写钩子选择器时，
   预览必须能命中，否则调不出效果又找不到原因。自造类保留为兼容别名（见下 legacy 段）。*/
[data-chat="composer"] button{appearance:none;background:0 0;border:0;margin:0;padding:0;
  color:inherit;font:inherit;cursor:pointer;-webkit-tap-highlight-color:transparent}
[data-chat="composer"] button:disabled{opacity:.4;cursor:not-allowed}
[data-chat="composer"] img{display:block}
[data-chat="composer"] .composer-shortcut-wrap{height:calc(76 * var(--rpx));position:relative;overflow:hidden}
[data-chat="composer"] [data-chat="shortcut"],[data-chat="instruction-bar"]{height:calc(76 * var(--rpx));
  padding:0 calc(12 * var(--rpx));gap:calc(10 * var(--rpx));display:flex;align-items:center;box-sizing:border-box;
  transition:transform .3s cubic-bezier(.4,0,.2,1),opacity .3s}
[data-chat="composer"] [data-chat="shortcut"]{overflow:auto hidden;white-space:nowrap;scrollbar-width:none}
[data-chat="composer"] [data-chat="shortcut"]::-webkit-scrollbar{display:none}
[data-chat="composer"] [data-chat="shortcut"].hidden{transform:translateX(calc(-30 * var(--rpx)));opacity:0;
  pointer-events:none;position:absolute;inset:0}
[data-chat="composer"] [data-chat="instruction-bar"]{overflow:hidden}
[data-chat="composer"] [data-chat="instruction-bar"].hidden{transform:translateX(calc(30 * var(--rpx)));opacity:0;
  pointer-events:none;position:absolute;inset:0}
[data-chat="composer"] [data-chat="shortcut"] > button{height:calc(56 * var(--rpx));padding:0 calc(16 * var(--rpx));
  border-radius:calc(28 * var(--rpx));font-size:calc(24 * var(--rpx));gap:calc(6 * var(--rpx));
  background:var(--chat-shortcut-bg);color:var(--chat-shortcut-text);white-space:nowrap;
  flex-shrink:0;display:flex;align-items:center;justify-content:center;box-sizing:border-box}
[data-chat="composer"] [data-chat="instruction-chip"]{height:calc(56 * var(--rpx));padding:0 calc(22 * var(--rpx));
  margin-right:calc(10 * var(--rpx));background:var(--chat-shortcut-bg);
  border-radius:calc(28 * var(--rpx));font-size:calc(24 * var(--rpx));color:var(--chat-shortcut-text);
  white-space:nowrap;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box}
[data-chat="composer"] [data-chat="instruction-back"]{width:calc(48 * var(--rpx));height:calc(48 * var(--rpx));
  background:var(--chat-modal-accent);color:#fff;border-radius:50%%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 calc(4 * var(--rpx)) calc(16 * var(--rpx)) #ff6d9759}
[data-theme="dark"] [data-chat="instruction-back"]{box-shadow:none}
[data-chat="composer"] .instruction-back-arrow{font-size:calc(38 * var(--rpx));transform:translateY(calc(-5 * var(--rpx)));
  font-weight:600;line-height:1}
[data-chat="composer"] .instruction-scroll{white-space:nowrap;scrollbar-width:none;flex:1 1 0;align-items:center;
  min-width:0;display:flex;overflow:auto hidden}
[data-chat="composer"] .instruction-scroll::-webkit-scrollbar{display:none}
[data-chat="composer"] .composer-row{width:100%%;padding:calc(16 * var(--rpx)) calc(30 * var(--rpx));
  box-sizing:border-box;display:flex;align-items:center}
[data-chat="composer"] .assistant-anchor,[data-action="more"]{flex-shrink:0;display:flex;align-items:center;
  justify-content:center;align-self:center;position:relative}
[data-chat="composer"] .assistant-anchor{margin-right:calc(6 * var(--rpx))}
[data-chat="composer"] [data-action="more"]{margin-left:calc(12 * var(--rpx))}
[data-chat="composer"] [data-chat="assistant"]{display:flex;align-items:center;justify-content:center;position:relative}
[data-chat="composer"] [data-chat="assistant"] .beta-badge{position:absolute;top:calc(-10 * var(--rpx));
  left:calc(-20 * var(--rpx));padding:calc(4 * var(--rpx)) calc(6 * var(--rpx));
  border-radius:calc(10 * var(--rpx));background:var(--chat-accent);color:#fff;
  font-size:calc(20 * var(--rpx));display:flex;align-items:center;font-weight:500;line-height:1}
/* AI帮聊 tip：真机点击后才插入，预览默认不渲染（由面板开关插入） */
[data-chat="composer"] [data-chat="assistant-tip"]{position:absolute;bottom:100%%;left:0;transform:translateX(-5%%);
  margin-bottom:calc(28 * var(--rpx));padding:calc(8 * var(--rpx)) calc(10 * var(--rpx));
  border-radius:calc(15 * var(--rpx));background:var(--chat-modal-accent);color:#fff;
  font-size:calc(22 * var(--rpx));white-space:nowrap;z-index:10;width:max-content;line-height:1.4}
[data-chat="composer"] .assistant-tip-arrow{position:absolute;top:100%%;left:calc(30 * var(--rpx));width:0;height:0;
  border-left:calc(8 * var(--rpx)) solid transparent;border-right:calc(8 * var(--rpx)) solid transparent;
  border-top:calc(8 * var(--rpx)) solid var(--chat-modal-accent)}
/* 输入框壳与三态（实测原文对齐 2026-08-29）：
   折叠态 min-height:82rpx（旧版漏了这条，输入行整体矮一截）；
   多行态 is-multiline 换 padding 并底对齐；展开态 is-expanded 转 grid（三区 tools/input/chip.send）。
   🚨 font-size 那条实测在 ::placeholder 规则里（不是 input 本体），input 本体不设字号
   —— 照抄，别"顺手"给 input 补 font-size，否则与真机差一截。 */
[data-chat="composer"] .composer-field{flex:1 1 0;min-width:0;padding:0 calc(16 * var(--rpx));
  background:var(--chat-input-bg);border-radius:calc(24 * var(--rpx));
  border:calc(2 * var(--rpx)) solid var(--chat-input-border);
  display:flex;align-items:center;box-sizing:border-box}
[data-chat="composer"] .composer-field:not(.is-expanded){min-height:calc(82 * var(--rpx))}
[data-chat="composer"] .composer-field.is-expanded{padding:calc(20 * var(--rpx));border-radius:calc(24 * var(--rpx));
  grid-template-columns:auto 1fr auto;
  grid-template-areas:"tools tools tools" "input input input" "chip . send";
  align-items:stretch;display:grid}
[data-chat="composer"] .composer-tools{align-items:center;gap:calc(16 * var(--rpx));
  margin-bottom:calc(12 * var(--rpx));grid-area:tools;display:flex}
[data-chat="composer"] .composer-field:not(.is-expanded) .composer-tools{display:none}
[data-chat="composer"] .composer-tools button{align-items:center;gap:calc(6 * var(--rpx));
  font-size:calc(24 * var(--rpx));color:var(--chat-shortcut-text);
  padding:calc(8 * var(--rpx)) calc(18 * var(--rpx));background:var(--chat-shortcut-bg);
  border-radius:calc(12 * var(--rpx));border:1px solid rgba(255,255,255,.1);display:flex}
[data-chat="composer"] [data-chat="input"]{resize:none;width:100%%;min-width:0;color:var(--chat-input-text);
  background:0 0;border:0;outline:none;flex:1 1 0;grid-area:input;font-family:inherit}
[data-chat="composer"] [data-chat="input"]::placeholder{color:var(--chat-input-placeholder);
  font-size:calc(32 * var(--rpx));padding:calc(8 * var(--rpx));box-sizing:border-box;
  max-height:calc(32 * var(--rpx) * 1.4 * 5);scrollbar-width:none;font-family:inherit;
  overflow-y:auto;line-height:1.4 !important}
[data-chat="composer"] [data-chat="input"]::-webkit-scrollbar{width:0;height:0;display:none}
[data-chat="composer"] .composer-field:not(.is-expanded) [data-chat="input"]{padding:0 calc(12 * var(--rpx));
  max-height:calc(280 * var(--rpx));align-self:center}
[data-chat="composer"] .composer-field.is-multiline:not(.is-expanded){padding:calc(16 * var(--rpx)) calc(20 * var(--rpx));
  align-items:flex-end}
[data-chat="composer"] .composer-field.is-multiline:not(.is-expanded) [data-chat="input"]{
  padding:calc(8 * var(--rpx)) calc(12 * var(--rpx))}
[data-chat="composer"] .composer-field.is-multiline:not(.is-expanded) [data-chat="model-chip"],
[data-chat="composer"] .composer-field.is-multiline:not(.is-expanded) [data-chat="send"]{
  padding-bottom:calc(16 * var(--rpx))}
[data-chat="composer"] .composer-field.is-expanded [data-chat="input"]{min-height:calc(32 * var(--rpx) * 1.4);
  max-height:calc(32 * var(--rpx) * 1.4 * 7);padding:0 calc(4 * var(--rpx));
  margin-bottom:calc(16 * var(--rpx));overflow-y:auto}
/* 多行/展开时左右两个圆钮改为底对齐（实测 :has() 选择器原文） */
[data-chat="composer"] .composer-row:has(.is-expanded),
[data-chat="composer"] .composer-row:has(.is-multiline){align-items:flex-end}
[data-chat="composer"] .composer-row:has(.is-expanded) .assistant-anchor,
[data-chat="composer"] .composer-row:has(.is-multiline) .assistant-anchor,
[data-chat="composer"] .composer-row:has(.is-expanded) [data-action="more"],
[data-chat="composer"] .composer-row:has(.is-multiline) [data-action="more"]{
  padding-bottom:calc(27 * var(--rpx));align-self:flex-end}
[data-chat="composer"] [data-chat="model-chip"]{font-weight:500;font-size:calc(25 * var(--rpx));
  color:var(--chat-composer-text);white-space:nowrap;flex-shrink:0;order:-1;
  grid-area:chip;align-items:center;display:flex}
[data-chat="composer"] .composer-field.is-expanded [data-chat="model-chip"]{order:0}
[data-chat="composer"] [data-chat="send"]{flex-shrink:0;grid-area:send;justify-content:center;align-items:center;
  display:flex;color:var(--chat-accent)}
/* 图标尺寸（实测）：send 的 img 40rpx；assistant 与 more 的 img 50rpx。
   真机是「两者都 40rpx」后面再单独把 assistant 覆盖成 50rpx，这里照同样的顺序写。 */
[data-chat="composer"] [data-chat="assistant"] .pano-glyph,
[data-chat="composer"] [data-chat="send"] .pano-glyph{
  width:calc(40 * var(--rpx));height:calc(40 * var(--rpx));font-size:calc(34 * var(--rpx));
  display:flex;align-items:center;justify-content:center;line-height:1}
[data-chat="composer"] [data-chat="assistant"] .pano-glyph{
  width:calc(50 * var(--rpx));height:calc(50 * var(--rpx));font-size:calc(42 * var(--rpx))}
[data-chat="composer"] [data-action="more"] .pano-glyph{width:calc(50 * var(--rpx));height:calc(50 * var(--rpx));
  font-size:calc(44 * var(--rpx));display:flex;align-items:center;justify-content:center;line-height:1}
/* 「+」更多面板：真机在 composer 内展开（不是弹窗），4 列 11 项，实测 composer 95→412px。
   壳吃 --chat-modal-bg、正文吃 --chat-modal-text、项图标底吃 --chat-more-item-bg。*/
[data-chat="more-panel"]{gap:calc(20 * var(--rpx));
  padding:calc(24 * var(--rpx)) calc(30 * var(--rpx)) calc(30 * var(--rpx));
  box-sizing:border-box;background:var(--chat-modal-bg);color:var(--chat-modal-text);
  flex-wrap:wrap;display:none}
[data-chat="more-panel"][data-open="on"]{display:flex}
[data-chat="more-panel"] > button{width:calc(25%% - calc(20 * var(--rpx)));text-align:center;
  font-size:calc(26 * var(--rpx));font-weight:400;line-height:calc(37 * var(--rpx));
  color:var(--chat-modal-text);flex-direction:column;align-items:center;display:flex}
[data-chat="more-panel"] > button > span{width:100%%;height:calc(129 * var(--rpx));
  border-radius:calc(40 * var(--rpx));background:var(--chat-more-item-bg);box-sizing:border-box;
  margin-bottom:calc(14 * var(--rpx));justify-content:center;align-items:center;display:flex;
  font-size:calc(48 * var(--rpx))}
[data-chat="messages"]{background:transparent}
[data-chat="message"][data-from="ai"] [data-chat="message-body"]{background:var(--chat-bubble-ai-bg);color:var(--chat-bubble-text)}
[data-chat="message"][data-from="user"] [data-chat="message-body"]{background:var(--chat-bubble-user-bg)}
/* 预览专属辅助线，默认关闭；外层工具可临时在 root 挂此标记。 */
[data-preview-bubble-outline] [data-chat="message-body"]{box-shadow:inset 0 0 0 1px var(--chat-border)}
/* 舞台三态（实测）：closed 不显示；content 只盖消息区 z-index 2000；full 盖整屏 3000。
   旧版只有一个 fixed/inset:0/z-2000 + [hidden]，把 content 也画成盖整屏了。*/
[data-chat="author-stage"]{background:var(--chat-bg)}
[data-chat="author-stage"][data-stage="closed"]{display:none}
[data-chat="author-stage"][data-stage="content"]{position:absolute;z-index:2000}
[data-chat="author-stage"][data-stage="full"]{position:fixed;inset:0;z-index:3000}
[data-chat="author-stage"][hidden]{display:none}

/* ── iframe 内浮层族（实测复刻）：这批**卡片 CSS 能打到**，必须完整仿真 ── */
/* 长按消息菜单 z-8200 + backdrop blur */
[data-chat="message-menu"]{position:fixed;inset:0;z-index:8200;backdrop-filter:blur(5px);
  box-sizing:border-box;display:none}
[data-chat="message-menu"][data-open="on"]{display:block}
[data-chat="message-menu"] .menu-preview{margin:calc(160 * var(--rpx)) calc(32 * var(--rpx)) 0;
  max-height:50%%;padding:calc(32 * var(--rpx));border-radius:calc(40 * var(--rpx));
  background:var(--chat-modal-surface);color:var(--chat-modal-text);white-space:pre-line;
  box-shadow:0 0 calc(8 * var(--rpx)) #0000000f;box-sizing:border-box;overflow:auto}
[data-chat="message-menu"] .menu-options{width:calc(290 * var(--rpx));margin-left:1rem;
  margin-top:calc(30 * var(--rpx));padding:calc(20 * var(--rpx)) calc(32 * var(--rpx));
  border-radius:calc(40 * var(--rpx));background:var(--chat-modal-surface);
  box-shadow:0 0 calc(8 * var(--rpx)) #0000000f;box-sizing:border-box}
[data-chat="message-menu"] .menu-sep{width:calc(233 * var(--rpx));height:0;
  border:calc(1 * var(--rpx)) solid var(--chat-border)}
[data-chat="message-menu"] .menu-options [data-action]{width:100%%;height:calc(80 * var(--rpx));
  color:var(--chat-modal-text);font-weight:500;font-size:calc(26 * var(--rpx));
  line-height:calc(80 * var(--rpx));display:flex;justify-content:space-between;align-items:center}
/* 居中 alert：实测 position:absolute（不是 fixed）、遮罩 .45、z-9000 */
[data-chat="alert"]{position:absolute;inset:0;z-index:9000;background:rgba(0,0,0,.45);
  justify-content:center;align-items:center;display:none}
[data-chat="alert"][data-open="on"]{display:flex}
[data-chat="alert"] .alert-box{background:var(--chat-modal-bg);color:var(--chat-modal-text);
  border-radius:calc(24 * var(--rpx));min-width:calc(480 * var(--rpx));
  padding:0 calc(40 * var(--rpx));box-sizing:border-box}
[data-chat="alert"] [data-chat="toast"]{padding:calc(45 * var(--rpx)) 0;
  font-size:calc(28 * var(--rpx));text-align:center;margin:0}
[data-chat="alert-ok"]{width:100%%;margin:0 0 calc(30 * var(--rpx));color:var(--chat-accent);
  font-size:calc(32 * var(--rpx));text-align:center;display:block;background:0 0;border:0}
/* 两个 snackbar：平台侧 z-10090 与 composer 侧 z-8100 */
[data-probe="snackbar"]{position:fixed;top:50%%;left:50%%;transform:translate(-50%%,-50%%);
  z-index:10090;background:rgba(0,0,0,.7);color:#fff;border-radius:4px;padding:10px 20px;
  font-size:14px;max-width:80%%;text-align:center;pointer-events:none;line-height:1.4;display:none}
[data-probe="snackbar"][data-open="on"]{display:block}
[data-chat="snack"]{position:fixed;top:50%%;left:50%%;transform:translate(-50%%,-50%%);
  z-index:8100;background:rgba(0,0,0,.72);color:#fff;border-radius:calc(16 * var(--rpx));
  padding:calc(20 * var(--rpx)) calc(28 * var(--rpx));font-size:calc(28 * var(--rpx));
  max-width:70%%;text-align:center;pointer-events:none;line-height:1.4;display:none}
[data-chat="snack"][data-open="on"]{display:block}
/* 剧情总结提示气泡（长在消息流里） */
[data-chat="summary-bubble"]{margin:calc(72 * var(--rpx)) calc(30 * var(--rpx)) calc(16 * var(--rpx));
  padding:calc(18 * var(--rpx)) calc(24 * var(--rpx));border-radius:calc(40 * var(--rpx));
  border:calc(1 * var(--rpx)) solid #ff6d9740;color:#ff6d97;background-color:rgba(255,109,151,.08);
  gap:calc(16 * var(--rpx));align-items:center;box-sizing:border-box;display:none}
[data-chat="summary-bubble"][data-open="on"]{display:flex}
[data-chat="summary-bubble"].summary-light{color:#17aafd;background-color:rgba(23,170,253,.08);
  border-color:rgba(23,170,253,.35)}
[data-chat="summary-bubble"] .summary-bubble-text{font-size:calc(24 * var(--rpx));color:inherit;
  flex:1 1 0;font-weight:600;line-height:1.5}
[data-chat="summary-bubble"] .summary-bubble-btn{padding:calc(8 * var(--rpx)) calc(24 * var(--rpx));
  border-radius:calc(24 * var(--rpx));background-color:#ff6d97;color:#fff;
  font-size:calc(22 * var(--rpx));border:0;flex-shrink:0;font-weight:600}
/* 分享条 / 分享选择模式 / 长图 */
[data-chat="share-bar"]{align-items:center;column-gap:calc(24 * var(--rpx));
  padding:calc(24 * var(--rpx)) calc(30 * var(--rpx));background:var(--chat-composer-bg);
  flex:0 0 auto;display:none}
[data-chat="share-bar"][data-open="on"]{display:flex}
[data-chat="share-bar"] > button{padding:calc(20 * var(--rpx)) 0;border-radius:calc(16 * var(--rpx));
  background:var(--chat-accent);color:#fff;font-size:calc(28 * var(--rpx));border:0;flex:1 1 0}
[data-chat="share-pick-bar"]{justify-content:center;align-items:center;column-gap:calc(40 * var(--rpx));
  padding:calc(40 * var(--rpx));background:var(--chat-modal-surface);flex:0 0 auto;display:none}
[data-chat="share-pick-bar"][data-open="on"]{display:flex}
[data-chat="share-pick-bar"] > button{width:25%%;color:var(--chat-modal-text);
  font-size:calc(26 * var(--rpx));background:0 0;border:0;flex-direction:column;
  align-items:center;display:flex}
[data-chat="share-pick-icon"]{width:calc(120 * var(--rpx));height:calc(120 * var(--rpx));
  margin-bottom:calc(14 * var(--rpx));background:var(--chat-border);border-radius:50%%;
  justify-content:center;align-items:center;display:flex}
[data-chat="message-frame"][data-share-picked]{background-color:var(--chat-share-pick-bg);opacity:.9}
[data-chat="share-shot-loading"]{position:absolute;inset:0;z-index:8000;background:rgba(0,0,0,.35);
  color:#fff;font-size:calc(28 * var(--rpx));justify-content:center;align-items:center;display:none}
[data-chat="share-shot-loading"][data-open="on"]{display:flex}
/* 历史加载骨架：真机会把 messages 整块隐藏 */
[data-probe="history-loading"]{flex:1 1 0;justify-content:center;align-items:center;
  gap:calc(12 * var(--rpx));font-size:calc(26 * var(--rpx));color:var(--chat-text-muted);
  z-index:2;min-height:0;display:none}
[data-probe="history-loading"][data-open="on"]{display:flex}
[data-chat="root"]:has([data-probe="history-loading"][data-open="on"]) [data-chat="messages"]{
  visibility:hidden;flex:0 0 0;min-height:0;overflow:hidden}

/* ── 宿主页弹窗：卡片 CSS **打不到**，只画层级遮挡轮廓 ──────────────────────
   实测：模型设置/对话设置/总结剧情/用户人设/分享 五个渲染在宿主页（h5.aitchat.org 的
   uni-app），吃宿主 51 个 --background-color 系变量；在卡片 iframe 内注入
   --chat-modal-* 对它们**零影响**（探针验证：注入 #00ff00 后弹窗仍 #17181a、
   该变量在其上解析为未定义）。所以预览刻意把它们画成**灰底斜纹的"平台侧"占位**，
   不套 --chat-modal-* —— 套了就是撒谎，作者会白写一堆选择器。*/
.pano-host-popup{position:absolute;left:0;right:0;bottom:0;z-index:10075;display:none;
  box-sizing:border-box;font-family:inherit}
.pano-host-popup[data-open="on"]{display:block}
/* 🚨 z-index 逐个实测（2026-08-29），不是一档：
   9000  = model / model-switch / conversation / share / assist-alert
   10075 = conv / role
   1e9   = summary（比别的高 5 个数量级，组件永远盖不过它）
   曾把 model 记成 10075 —— 实测是 9000。 */
.pano-host-popup[data-host-popup="model"],
.pano-host-popup[data-host-popup="model-switch"],
.pano-host-popup[data-host-popup="conversation"],
.pano-host-popup[data-host-popup="share"],
.pano-host-popup[data-host-popup="assist-alert"]{z-index:9000}
.pano-host-popup[data-host-popup="summary"]{z-index:1000000000}
/* AI帮聊 alert：实测 u-fade-zoom + flex 居中 + 260px 定宽 + radius 10px（不是底部升起） */
.pano-host-popup[data-host-popup="assist-alert"][data-open="on"]{display:flex;
  align-items:center;justify-content:center;top:0}
.pano-host-popup[data-host-popup="assist-alert"] .pano-host-sheet{width:260px;
  border-radius:10px;background:#1e1f24}
/* 遮罩实测 .5（沙盒宿主页），旧 MMD 聊天页是 .7 —— 别混。 */
.pano-host-popup .pano-host-mask{position:absolute;inset:0;background:rgba(0,0,0,.5)}
.pano-host-popup .pano-host-sheet{position:relative;background:#17181a;color:#fff;
  border-top-left-radius:10px;border-top-right-radius:10px;padding:16px;
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.045) 0 8px,transparent 8px 16px)}
.pano-host-popup[data-host-popup="conv"] .pano-host-sheet,
.pano-host-popup[data-host-popup="role"] .pano-host-sheet{border-radius:0}
.pano-host-popup .pano-host-tag{display:inline-block;margin-bottom:8px;padding:2px 8px;
  border-radius:4px;background:#d29922;color:#000;font-size:10px;font-weight:600}
.pano-host-popup .pano-host-title{font-size:15px;font-weight:600;margin-bottom:6px}
.pano-host-popup .pano-host-note{font-size:11px;line-height:1.5;color:#c5c5c5}
.pano-host-popup .pano-host-close{position:absolute;top:10px;right:12px;width:22px;height:22px;
  border:0;border-radius:50%%;background:rgba(255,255,255,.08);color:#c5c5c5;font-size:14px;cursor:pointer}

/* legacy 自造类：骨架上仍挂着这些 class（.pano-shortcuts/.pano-shortcut/.pano-compose-row/
   .pano-compose-icon/.pano-send/.pano-input-shell），但**不再给它们任何样式** ——
   样式全部由真实钩子（[data-chat=*]）提供。
   🚨 曾在这里放过一份"等效"别名规则，结果 `.pano-input-shell{background:var(--chat-input-bg)}`
   与 `[data-chat="composer"] .composer-field` 同时命中同一节点，作者想用类选择器改输入框时
   两条打架、行为与真机不一致。类名只留作兼容锚点，样式一律走钩子。 */

/* 桌面档：实测断点 961px、--rpx 封顶 375/750（旧版写 750px/1px，断点与取值双错）。
   rpx 一改，下面所有 calc(N * var(--rpx)) 自动跟着缩，不需要再逐条写 px 覆盖。 */
@media (min-width:%(bp)s){[data-chat="root"]{--rpx:%(rpxdesk)s}}
"""


# ── 沙盒浮层仿真节点（实测复刻，2026-08-29）─────────────────────────────────
# 分两类，别混：
#   A. iframe 内（本段前半）：卡片 CSS **能**打到，作者的全局美化会波及它们，必须完整
#      仿真、可开关。实测靶点见 references/platforms/mmd-sandbox.md。
#   B. 宿主页（SANDBOX_HOST_POPUPS）：模型设置/对话设置/总结剧情/用户人设/分享 五个渲染
#      在 h5.aitchat.org 的 uni-app 里，**跨源 iframe 之外**。探针验证：在卡片 iframe 内
#      注入 --chat-modal-bg:#00ff00 后打开模型设置，它仍是 #17181a，且该变量在其上解析
#      为「未定义」。所以这五个只画灰底斜纹的层级占位，**不套 --chat-modal-***
#      —— 套了就是撒谎，作者会照着预览白写一堆选择器。
# 默认全关（真机也是关的），由外层工具栏切 data-open="on|off"。

# 「+」更多面板 11 项，data-action 全部照真机（实测顺序与取值，2026-08-29）。
# 每项都可点：能开面板的直接开（对话设置/剧情总结/用户人设/新的聊天走宿主弹窗占位，
# 自定义指令切指令栏），其余弹 snack 说明"平台侧动作，预览不模拟真实副作用"。
SANDBOX_MORE_ITEMS = (
    ("reset", "&#8635;", "重置聊天"),
    ("export", "&#8681;", "导出聊天"),
    ("conversations", "&#9998;", "新的聊天"),
    ("role-edit", "&#9881;", "编辑角色"),
    ("background", "&#9634;", "更换背景"),
    ("instructions", "&#9776;", "自定义指令"),
    ("persona", "&#9786;", "用户人设"),
    ("extra", "&#9744;", "设定补充"),
    ("style", "&#9636;", "对话设置"),
    ("summary", "&#9635;", "剧情总结"),
    ("help", "?", "游玩教程"),
)

SANDBOX_MORE_PANEL = (
    '<div data-chat="more-panel" data-open="off">'
    + "".join('<button type="button" data-action="%s"><span>%s</span>%s</button>'
              % (act, glyph, label) for act, glyph, label in SANDBOX_MORE_ITEMS)
    + '</div>'
)

# 展开态才显示的工具行（实测 .composer-field:not(.is-expanded) .composer-tools{display:none}）
SANDBOX_COMPOSER_TOOLS = (
    '<div class="composer-tools">'
    '<button type="button" data-chat="paste">粘贴</button>'
    '<button type="button" data-chat="clear">清空</button>'
    '</div>'
)

SANDBOX_SUMMARY_BUBBLE = (
    '<div data-chat="summary-bubble" data-open="off">'
    '<span class="summary-bubble-text">剧情已总结到第 12 轮，可继续对话</span>'
    '<button class="summary-bubble-btn" type="button">查看</button>'
    '</div>'
)

SANDBOX_HISTORY_LOADING = (
    '<div data-probe="history-loading" data-open="off">'
    '<span data-probe="history-loading-spinner"></span>正在载入历史…'
    '</div>'
)

# 长按菜单（实测 [data-chat=message-menu]）：选项**随被长按消息的角色而变**（实测 2026-08-31）。
#   AI 消息：复制（仅文本）/ 删除（从上下文移除）/ 回溯（删本条及下方全部）/ 开启新的故事（保留本条及以上，进新聊天）
#   用户消息：同 AI 四项（回溯对用户消息同样成立；实测未逐字复核用户菜单，标 probe-needed）
#   角色卡「第一句话」(msg-id=-1)：仅「复制」
# 静态 HTML 先放 AI 四项占位；面板脚手架在长按时按 data-msg-kind 重建 .menu-options。
SANDBOX_MENU_OPTIONS = {
    "ai": (("copy", "复制", "&#10697;"), ("delete", "删除", "&#10005;"),
           ("backtrack", "回溯", "&#8630;"), ("newstory", "开启新的故事", "&#10022;")),
    "user": (("copy", "复制", "&#10697;"), ("delete", "删除", "&#10005;"),
             ("backtrack", "回溯", "&#8630;"), ("newstory", "开启新的故事", "&#10022;")),
    "first": (("copy", "复制", "&#10697;"),),
}


def _sandbox_menu_options_html(kind):
    opts = SANDBOX_MENU_OPTIONS.get(kind, SANDBOX_MENU_OPTIONS["ai"])
    parts = []
    for i, (act, label, glyph) in enumerate(opts):
        if i:
            parts.append('<div class="menu-sep"></div>')
        parts.append('<button type="button" data-action="%s">%s<span class="pano-glyph">%s</span></button>'
                     % (act, label, glyph))
    return "".join(parts)


SANDBOX_MESSAGE_MENU = (
    '<div data-chat="message-menu" data-open="off">'
    '<div class="menu-preview">被长按的消息正文（预览占位）</div>'
    '<div class="menu-options">%s</div></div>' % _sandbox_menu_options_html("ai")
)


# 三圆钮：AI 3 钮（刷新/编辑/分享）、用户 2 钮（编辑/分享）、第一句话 0 钮（实测 2026-08-31）。
SANDBOX_MESSAGE_ACTIONS = {
    "ai": (("regenerate", "刷新（重新生成）", "&#8635;"),
           ("edit", "编辑", "&#9998;"), ("share", "分享", "&#10148;")),
    "user": (("edit", "编辑", "&#9998;"), ("share", "分享", "&#10148;")),
    "first": (),
}


def _sandbox_actions_html(kind):
    return "".join('<button type="button" data-action="%s" title="%s"><span class="pano-glyph">%s</span></button>'
                   % (act, title, glyph)
                   for act, title, glyph in SANDBOX_MESSAGE_ACTIONS.get(kind, ()))


# 顶部角色描述块（实测 [data-probe=role-intro]，通栏、两态都在）。
SANDBOX_ROLE_INTRO = (
    '<div data-probe="role-intro" data-from="ai">'
    '<div data-probe="role-intro-body">角色卡描述（role-intro，通栏，两态都显示）</div>'
    '</div>'
)

# 开场白选择块（实测 [data-probe=prologue]，仅初始态）。真机最多 5 句；预览给 3 个可点 chip 示意。
# 每个 chip 点击后把正文注入输入框（实测行为），并吃 --chat-bg/--chat-text（作者美化直接波及）。
SANDBOX_PROLOGUE = (
    '<div data-probe="prologue" data-msg-state="initial">'
    '<div data-probe="prologue-title"><span>你可以选择开场</span></div>'
    '<button type="button" data-probe="prologue-chip">开场白示例一（点击填入输入框）</button>'
    '<button type="button" data-probe="prologue-chip">开场白示例二（点击填入输入框）</button>'
    '<button type="button" data-probe="prologue-chip">开场白示例三（点击填入输入框）</button>'
    '</div>'
)

SANDBOX_ALERT = (
    '<div data-chat="alert" data-open="off">'
    '<div class="alert-box">'
    '<p data-chat="toast">这是平台 alert 的正文（居中、position:absolute、z-9000）</p>'
    '<button data-chat="alert-ok" type="button">确定</button>'
    '</div></div>'
)

SANDBOX_SNACK = (
    '<div data-chat="snack" data-open="off">composer 侧提示（z-8100）</div>'
)

SANDBOX_SNACKBAR = (
    '<div data-probe="snackbar" data-open="off">平台 snackbar（z-10090）</div>'
)

SANDBOX_SHARE_BAR = (
    '<div data-chat="share-bar" data-open="off">'
    '<button type="button">分享长图</button>'
    '<button type="button">选择消息</button>'
    '</div>'
)

SANDBOX_SHARE_PICK_BAR = (
    '<div data-chat="share-pick-bar" data-open="off">'
    '<button type="button"><span data-chat="share-pick-icon">&#10697;</span>复制</button>'
    '<button type="button"><span data-chat="share-pick-icon">&#9634;</span>长图</button>'
    '<button type="button"><span data-chat="share-pick-icon">&#8681;</span>保存</button>'
    '<button type="button"><span data-chat="share-pick-icon">&#10005;</span>取消</button>'
    '</div>'
)

SANDBOX_SHARE_SHOT = (
    '<div data-chat="share-shot-loading" data-open="off">正在生成长图…（z-8000）</div>'
)


# 沙盒浮层开关脚手架：**必须是经典 <script>**，沙盒禁 img onerror（测试也断言产物
# 整页不得出现 "onerror"）。暴露 window.__sbxPanels 给外层工具栏与 GUI 测试。
# data-open 用 on/off 而非 1/0：无引号属性选择器 [data-open=1] 非法（CSS 标识符不能
# 以数字开头），带引号又会在别处引发转义麻烦。
SANDBOX_PANEL_SCAFFOLD = (
    '<script data-preview-panels="1">'
    "(function(){var D=document;"
    "var SEL='[data-chat=\"more-panel\"],[data-chat=\"message-menu\"],"
    "[data-chat=\"alert\"],[data-chat=\"snack\"],[data-probe=\"snackbar\"],"
    "[data-chat=\"share-bar\"],[data-chat=\"share-pick-bar\"],"
    "[data-chat=\"share-shot-loading\"],[data-chat=\"summary-bubble\"],"
    "[data-probe=\"history-loading\"],.pano-host-popup';"
    "function all(){return D.querySelectorAll(SEL);}"
    "function closeAll(){var l=all();for(var i=0;i<l.length;i++){"
    "l[i].setAttribute('data-open','off');}"
    "var tip=D.querySelector('[data-chat=\"assistant-tip\"]');if(tip)tip.remove();"
    "if(typeof moreGlyph==='function')moreGlyph(false);}"
    "function nodeOf(name){"
    "return D.querySelector('[data-chat=\"'+name+'\"]')"
    "||D.querySelector('[data-probe=\"'+name+'\"]')"
    "||D.querySelector('.pano-host-popup[data-host-popup=\"'+name+'\"]');}"
    "function open(name){closeAll();var el=nodeOf(name);"
    "if(el){el.setAttribute('data-open','on');}return !!el;}"
    "function toggleInstr(){var sb=D.querySelector('[data-chat=\"shortcut\"]');"
    "var ib=D.querySelector('[data-chat=\"instruction-bar\"]');"
    "if(!sb||!ib)return false;var on=sb.className.indexOf('hidden')<0;"
    "sb.className=on?'pano-shortcuts hidden':'pano-shortcuts';"
    "ib.className=on?'':'hidden';return on;}"
    "function assistantTip(){var a=D.querySelector('.assistant-anchor');if(!a)return false;"
    "var old=D.querySelector('[data-chat=\"assistant-tip\"]');if(old){old.remove();return false;}"
    "var t=D.createElement('div');t.setAttribute('data-chat','assistant-tip');"
    "t.textContent='\\u4e0d\\u77e5\\u9053\\u600e\\u4e48\\u56de\\uff1f\\u8ba9AI\\u5e2e\\u4f60';"
    "var ar=D.createElement('span');ar.className='assistant-tip-arrow';"
    "t.appendChild(ar);a.appendChild(t);return true;}"
    "function stage(mode){var s=D.querySelector('[data-chat=\"author-stage\"]');"
    "if(!s)return null;s.removeAttribute('hidden');"
    "s.setAttribute('data-stage',mode);"
    "s.textContent=mode==='closed'?'':'\\u821e\\u53f0 '+mode;return mode;}"
    "function themeOf(t){var r=D.querySelector('[data-chat=\"root\"]');"
    "if(r)r.setAttribute('data-theme',t);return t;}"
    "window.__sbxPanels={open:open,closeAll:closeAll,"
    "toggleInstruction:toggleInstr,assistantTip:assistantTip,"
    "stage:stage,theme:themeOf,"
    "list:function(){var o=[],l=all();for(var i=0;i<l.length;i++){"
    "o.push(l[i].getAttribute('data-chat')||l[i].getAttribute('data-probe')"
    "||l[i].getAttribute('data-host-popup'));}return o;},"
    "opened:function(){var l=all(),o=[];for(var i=0;i<l.length;i++){"
    "if(l[i].getAttribute('data-open')==='on'){"
    "o.push(l[i].getAttribute('data-chat')||l[i].getAttribute('data-probe')"
    "||l[i].getAttribute('data-host-popup'));}}return o;}};"
    "var cl=D.querySelectorAll('[data-host-close]');"
    "for(var i=0;i<cl.length;i++){cl[i].onclick=function(ev){"
    "ev.stopPropagation();closeAll();};}"
    "var sc=D.querySelectorAll('[data-chat=\"shortcut\"] > button');"
    "var map={model:'model',style:'conv',summary:'summary',"
    "conversations:'model',persona:'role'};"
    "for(var j=0;j<sc.length;j++){(function(b){b.onclick=function(ev){"
    "ev.stopPropagation();var a=b.getAttribute('data-action');"
    "if(a==='instructions'){toggleInstr();}else if(map[a]){open(map[a]);}};})(sc[j]);}"
    # 「+」按钮：点开更多面板时字形换成「−」（实测真机是换 PNG，预览用字形切换等效），
    # 面板作为 composer 内的后置块把输入行往上顶（几何由 CSS 承担，这里只切 data-open + 字形）。
    "function moreGlyph(open){var g=D.querySelector('[data-action=\"more\"] .pano-glyph');"
    "if(g)g.innerHTML=open?'\\u2212':'\\uff0b';}"
    "var more=D.querySelector('[data-action=\"more\"]');"
    "if(more){more.onclick=function(ev){ev.stopPropagation();"
    "var p=D.querySelector('[data-chat=\"more-panel\"]');if(!p)return;"
    "var on=p.getAttribute('data-open')==='on';"
    "closeAll();if(!on)p.setAttribute('data-open','on');moreGlyph(!on);};}"
    "var asst=D.querySelector('[data-chat=\"assistant\"]');"
    "if(asst){asst.onclick=function(ev){ev.stopPropagation();assistantTip();};}"
    "var back=D.querySelector('[data-chat=\"instruction-back\"]');"
    "if(back){back.onclick=function(ev){ev.stopPropagation();toggleInstr();};}"
    # 「+」面板 11 个按钮全部可点：能开面板的直接开，其余弹 snack 说明是平台侧动作。
    # 作者的全局美化能打到这批（面板在 iframe 内），所以点开后要能看出自己的 CSS 效果。
    "function snack(msg){var s=D.querySelector('[data-chat=\"snack\"]');if(!s)return;"
    "s.textContent=msg;closeAll();s.setAttribute('data-open','on');}"
    "var MORE={style:'conv',summary:'summary',persona:'role',conversations:'model'};"
    "var LABEL={reset:'\\u91cd\\u7f6e\\u804a\\u5929',export:'\\u5bfc\\u51fa\\u804a\\u5929',"
    "'role-edit':'\\u7f16\\u8f91\\u89d2\\u8272',background:'\\u66f4\\u6362\\u80cc\\u666f',"
    "extra:'\\u8bbe\\u5b9a\\u8865\\u5145',help:'\\u6e38\\u73a9\\u6559\\u7a0b'};"
    "var mi=D.querySelectorAll('[data-chat=\"more-panel\"] > button');"
    "for(var k=0;k<mi.length;k++){(function(b){b.onclick=function(ev){"
    "ev.stopPropagation();var a=b.getAttribute('data-action');"
    "if(a==='instructions'){closeAll();toggleInstr();return;}"
    "if(MORE[a]){open(MORE[a]);return;}"
    "snack((LABEL[a]||a)+'\\uff1a\\u5e73\\u53f0\\u4fa7\\u52a8\\u4f5c\\uff0c"
    "\\u9884\\u89c8\\u4e0d\\u6a21\\u62df\\u771f\\u5b9e\\u526f\\u4f5c\\u7528');};})(mi[k]);}"
    # 输入框三态：真机按内容行数自动加 is-multiline / 展开加 is-expanded。
    # 预览按 textarea 实际换行数近似，并暴露 fieldState() 供工具栏强制切。
    "var ta=D.querySelector('[data-chat=\"input\"]');"
    "var field=D.querySelector('.composer-field');"
    "function syncField(){if(!ta||!field)return;"
    "var multi=(ta.value.indexOf('\\n')>=0)||ta.value.length>40;"
    "if(field.className.indexOf('is-expanded')<0){"
    "field.className=multi?'pano-input-shell composer-field is-multiline'"
    ":'pano-input-shell composer-field';}}"
    "if(ta){ta.addEventListener('input',syncField);}"
    # 🚨 两态契约（实测 2026-08-31）：**点击/聚焦输入框 → 加 is-expanded 展开**（框变高、+ 钮
    # 底对齐上移）；**点框外/失焦 → 去 is-expanded 收回**。这是真机行为（focus 派发即展开，
    # blur 即收回），不是靠 outside-click 监听。注入文字**不自动展开**（实测：点开场白把正文塞进
    # 输入框后，field 仍是收起态）。展开态优先于 multiline。
    "function expand(){if(field&&field.className.indexOf('is-expanded')<0){"
    "field.className='pano-input-shell composer-field is-expanded';}}"
    "function collapse(){if(field){field.className='pano-input-shell composer-field';syncField();}}"
    "if(ta){ta.addEventListener('focus',expand);ta.addEventListener('blur',collapse);}"
    "function fieldState(s){if(!field)return null;"
    "field.className='pano-input-shell composer-field'+(s?' '+s:'');return s||'base';}"
    "window.__sbxPanels.fieldState=fieldState;"
    "window.__sbxPanels.expandField=expand;window.__sbxPanels.collapseField=collapse;"
    "window.__sbxPanels.snack=snack;"
    # 开场白 chip 点击 → 正文注入输入框（实测行为）。注入用原生 setter + input 事件（与 SDK
    # composer.set 一致的可观察副作用），**不展开**输入框。
    "function fillInput(text){if(!ta)return;"
    "var setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(ta),'value');"
    "if(setter&&setter.set){setter.set.call(ta,text);}else{ta.value=text;}"
    "ta.dispatchEvent(new Event('input',{bubbles:true}));syncField();}"
    "window.__sbxPanels.fillInput=fillInput;"
    "var chips=D.querySelectorAll('[data-probe=\"prologue-chip\"]');"
    "for(var pc=0;pc<chips.length;pc++){(function(ch){ch.onclick=function(ev){"
    "ev.stopPropagation();fillInput(ch.textContent||'');};})(chips[pc]);}"
    # 消息两态开关（实测状态流转）：发送→sent（开场白消失）；回溯→initial（开场白重现）。
    "function setChatState(s){var r=D.querySelector('[data-chat=\"root\"]');"
    "if(!r)return null;var st=(s==='sent')?'sent':'initial';"
    "r.setAttribute('data-chat-state',st);return st;}"
    "function toggleChatState(){var r=D.querySelector('[data-chat=\"root\"]');"
    "if(!r)return null;return setChatState(r.getAttribute('data-chat-state')==='sent'?'initial':'sent');}"
    "window.__sbxPanels.setChatState=setChatState;"
    "window.__sbxPanels.toggleChatState=toggleChatState;"
    # 长按菜单：选项随被长按消息角色变（实测）。ai/user 四项（复制/删除/回溯/开启新的故事），
    # 「第一句话」(data-msg-kind=first) 仅「复制」。真机是 touch 长按，预览额外暴露 longPress(kind)
    # 供工具栏与真实长按共用；每条气泡也绑 pointerdown 计时（>420ms 触发），移动/抬起取消。
    "var MENU={"
    "ai:[['copy','\\u590d\\u5236','\\u2a19'],['delete','\\u5220\\u9664','\\u2715'],"
    "['backtrack','\\u56de\\u6eaf','\\u21ba'],['newstory','\\u5f00\\u542f\\u65b0\\u7684\\u6545\\u4e8b','\\u2726']],"
    "user:[['copy','\\u590d\\u5236','\\u2a19'],['delete','\\u5220\\u9664','\\u2715'],"
    "['backtrack','\\u56de\\u6eaf','\\u21ba'],['newstory','\\u5f00\\u542f\\u65b0\\u7684\\u6545\\u4e8b','\\u2726']],"
    "first:[['copy','\\u590d\\u5236','\\u2a19']]};"
    "function buildMenu(kind,previewText){var m=D.querySelector('[data-chat=\"message-menu\"]');"
    "if(!m)return false;var opts=MENU[kind]||MENU.ai;"
    "var pv=m.querySelector('.menu-preview');if(pv)pv.textContent=previewText||'';"
    "var box=m.querySelector('.menu-options');if(box){box.innerHTML='';"
    "for(var i=0;i<opts.length;i++){if(i){var sep=D.createElement('div');sep.className='menu-sep';box.appendChild(sep);}"
    "var b=D.createElement('button');b.type='button';b.setAttribute('data-action',opts[i][0]);"
    "b.appendChild(D.createTextNode(opts[i][1]));var g=D.createElement('span');g.className='pano-glyph';"
    "g.textContent=opts[i][2];b.appendChild(g);"
    "(function(act){b.onclick=function(ev){ev.stopPropagation();closeAll();"
    "snack(act+'\\uff1a\\u9884\\u89c8\\u4e0d\\u6a21\\u62df\\u771f\\u5b9e\\u526f\\u4f5c\\u7528');};})(opts[i][0]);"
    "box.appendChild(b);}}"
    "closeAll();m.setAttribute('data-open','on');return true;}"
    "function longPress(kind,text){return buildMenu(kind||'ai',text||'');}"
    "window.__sbxPanels.longPress=longPress;"
    "var frames=D.querySelectorAll('[data-chat=\"message\"]');"
    "for(var mf=0;mf<frames.length;mf++){(function(fr){var tm=null;"
    "var kind=fr.getAttribute('data-msg-kind')||(fr.getAttribute('data-from')==='user'?'user':'ai');"
    "var bodyEl=fr.querySelector('[data-chat=\"message-body\"]');"
    "var txt=bodyEl?(bodyEl.textContent||''):'';"
    "fr.addEventListener('pointerdown',function(){tm=setTimeout(function(){longPress(kind,txt);},420);});"
    "var cancel=function(){if(tm){clearTimeout(tm);tm=null;}};"
    "fr.addEventListener('pointerup',cancel);fr.addEventListener('pointermove',cancel);"
    "fr.addEventListener('pointercancel',cancel);})(frames[mf]);}"
    # 长按菜单点遮罩空白处关闭（实测 backdrop 可点关）
    "var mm=D.querySelector('[data-chat=\"message-menu\"]');"
    "if(mm){mm.addEventListener('click',function(ev){if(ev.target===mm)closeAll();});}"
    "})()"
    '</script>'
)


def _host_popup(name, title, note):
    return (
        '<div class="pano-host-popup" data-host-popup="%s" data-open="off">'
        '<div class="pano-host-mask" data-host-close="%s"></div>'
        '<div class="pano-host-sheet">'
        '<button class="pano-host-close" type="button" data-host-close="%s">&#215;</button>'
        '<span class="pano-host-tag">平台侧 · 卡片改不动</span>'
        '<div class="pano-host-title">%s</div>'
        '<div class="pano-host-note">%s</div>'
        '</div></div>' % (name, name, name, title, note)
    )


# 五个宿主弹窗（实测 scope 类名与 z-index 都在 note 里写明，供作者判断遮挡）
SANDBOX_HOST_POPUPS = "".join([
    _host_popup("model", "模型设置（快捷条第 1 钮）",
                "真机 <b>.model-setting-scope.theme-dark</b>，渲染在宿主页 uni-app（h5 域），"
                "z-index <b>9000</b>。内容是<b>参数</b>设置（输出 Token 上限 / 流式输出 / 预设提示词），"
                "不是模型列表。吃宿主 <b>--background-color</b> 系变量；"
                "在卡里改 --chat-modal-* <b>对它无效</b>（已探针验证：注入 #00ff00 后仍 #17181a、"
                "该变量在其上解析为 undefined）。"),
    _host_popup("model-switch", "对话模型选择（底栏模型芯片）",
                "真机 <b>.model-switch-scope</b>，宿主页，z-index <b>9000</b>。"
                "点底栏 <b>[data-chat=model-chip]</b> 打开（与快捷条「模型设置」是<b>两个不同面板</b>）。"
                "内含 .title-row / .model-filter-tabs / .model-list 三段。卡片 CSS 打不到。"),
    _host_popup("conv", "对话设置",
                "真机 <b>.conv-style-modal</b>，宿主页，z-index 10075，无圆角，"
                "底色由 .u-popup__content 内联 style 给。卡片 CSS 打不到。"),
    _host_popup("summary", "总结剧情 / 记忆管理面板",
                "真机 <b>.summary-sheet.theme-dark</b>，宿主页，"
                "z-index <b>1000000000</b>（比别的高 5 个数量级，组件永远盖不过它）。"),
    _host_popup("role", "用户人设",
                "真机 <b>.role-profile-modal</b> + <b>.role-setting</b>，宿主页，z-index 10075。"
                "用 <b>--lo*</b> 变量族（沙盒宿主页<b>有定义</b>，与旧聊天页不同）。"),
    _host_popup("share", "分享角色（顶栏第 2 钮）",
                "真机 <b>.share-popup</b>，宿主页，z-index <b>9000</b>"
                "（旧聊天页是 10075，这里不同）。带框架自带右上角关闭钮 .u-popup__content__close。"),
    _host_popup("conversation", "开启新的聊天（快捷条第 5 钮）",
                "真机 <b>.conversation-list-scope</b>，宿主页，z-index <b>9000</b>，实测高 187px。"
                "内含 .title-row / .conversation-list / .bottom &gt; .btn「创建新的聊天」。卡片 CSS 打不到。"),
    _host_popup("assist-alert", "AI帮聊功能介绍（底栏左下角）",
                "真机 <b>.alert-scope</b> 在宿主页，z-index <b>9000</b>，"
                "过渡是 <b>u-fade-zoom</b>（居中 260px，不是底部升起）。"
                "点 <b>[data-chat=assistant]</b> 首次触发。注意：这与 SDK 的 "
                "<b>[data-chat=alert]</b>（iframe 内、卡片能改）<b>是两个东西</b>。"),
])


# 🚨 这 4 个在真机两套主题里都是**别名**，不是独立字面量：
#   --chat-bubble-user-bg / --chat-bubble-ai-bg : var(--chat-bg)
#   --chat-bubble-text                          : var(--chat-text)
#   --chat-more-item-bg                         : var(--chat-modal-surface)
# 必须照抄成 var() 引用，不能展开成字面量 —— 展开后作者改 --chat-bg / --chat-modal-surface
# 时真机会跟着变、预览不变，作者会以为"改了没用"。SANDBOX_*_TOKEN_VALUES 里存的是
# **解析后**的取值（供文档与断言用），发到 CSS 时这 4 个要换回引用形态。
SANDBOX_ALIAS_TOKENS = {
    "--chat-bubble-user-bg": "var(--chat-bg)",
    "--chat-bubble-ai-bg": "var(--chat-bg)",
    "--chat-bubble-text": "var(--chat-text)",
    "--chat-more-item-bg": "var(--chat-modal-surface)",
}


def _sandbox_chrome_css():
    """把实测的两套 29 令牌与 --rpx 两档填进沙盒外壳 CSS。

    两套分别挂 [data-theme=light] / [data-theme=dark]（单属性，与真机同特异性
    0,1,0 —— 见 CSS 里的红线注释），平台无 :root 定义。
    别名 4 个发 var() 引用形态（见 SANDBOX_ALIAS_TOKENS）。"""
    def _decl(values, indent="  "):
        items = ["%s:%s;" % (k, SANDBOX_ALIAS_TOKENS.get(k, values[k]))
                 for k in SANDBOX_DESIGN_TOKENS]
        # 每行 3 个，保持可读
        lines = [indent + "".join(items[i:i + 3]) for i in range(0, len(items), 3)]
        return "\n" + "\n".join(lines)
    return SANDBOX_CHROME_CSS % {
        "light": _decl(SANDBOX_LIGHT_TOKEN_VALUES),
        "dark": _decl(SANDBOX_DARK_TOKEN_VALUES),
        "rpxbase": SANDBOX_RPX_BASE,
        "rpxdesk": SANDBOX_RPX_DESKTOP,
        "bp": SANDBOX_RPX_BREAKPOINT,
    }


def assemble_panorama(obj, platform, src_name, sandbox_profile="chat"):
    """全景预览：所有组件在同一文档里组合显示，模拟 MMD 聊天页。

    mmd/st 保留通用 fixed composer；mmdsandbox 复刻真实 root flex 外壳，composer 是静态
    flex item，消息区独立滚动，root 高度由内联 --chat-viewport-height 驱动。

    沙盒模式额外做三件事：
      1. 把官方稳定钩子挂到同一套骨架上（见 _panorama_hooks）；
      2. 在**作者 hoisted assets 之前**内联 mmdsandbox-sim.js，装上 window.sdk；
      3. 发送脚手架走经典 <script> + sdk.message.send，绝不用 img onerror。
    sandbox_profile 仅对 mmdsandbox 有效：chat（默认）或 thin-preview。"""
    sandbox = platform == "mmdsandbox"
    profile = sandbox_profile if sandbox_profile in SANDBOX_PROFILES else "chat"
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
                       % apply_platform_limits(assets, platform, script_badges=False))
    statusbar_node = ""
    if sandbox and statusbar_html.strip():
        # 角色卡 statusbar 留空 → 平台上这个节点整块不存在，预览照此处理。
        statusbar_node = ('<div data-slot="statusbar" class="pano-statusbar">%s</div>'
                          % apply_platform_limits(statusbar_html, platform))
    if sandbox:
        # 🚨 顺序即契约：sim 装 window.sdk → 作者 hoisted assets → 页面骨架。
        # 沙盒是独立 Vue 应用（非 uni-app 路由页），不注入 MMD 的路由脚手架。
        # 开场白正文传纯文本：实机 payload.content 是正文字符串，不是渲染后的 HTML。
        runtime = _sandbox_sim_block(profile, _sandbox_greeting_text(obj))
        send_scaffold = SANDBOX_SEND_SCAFFOLD
    else:
        runtime = PANORAMA_RUNTIME_SCAFFOLD
        send_scaffold = PANORAMA_SEND_SCAFFOLD
    if sandbox:
        page = (
            '%(runtime)s'
            '%(hoisted)s'
            '<div class="pano-sandbox-host">'
            '<div class="page"%(root)s>'
            '<header class="topTabbar"%(header)s>'
            '<button class="pano-head-back" type="button" title="返回"%(header_back)s>‹</button>'
            '<div%(header_title)s>SBK 沙盒预览</div>'
            '<div%(header_actions)s>'
            '<button class="pano-head-action" type="button" title="评论">▣</button>'
            '<button class="pano-head-action" type="button" title="分享">⌯</button>'
            '<button class="pano-head-action" type="button" title="收藏">☆</button>'
            '<button class="pano-head-action" type="button" title="刷新">↻</button>'
            '</div>%(header_extra)s</header>'
            '%(statusbar)s'
            '<main class="chat chat-bg pano-chat" id="pano-chat"%(messages)s>'
            '<div class="chat-body"%(list)s>'
            # 顶部角色描述块（两态都显示）
            '%(roleintro)s'
            '<div data-chat="list-spacer"></div>'
            # first_mes（角色卡「第一句话」= beginning 字段的实机落点）：AI 气泡、msg-id=-1、
            # **0 圆钮**（message-actions 空 → :not(:empty) 不命中 → 整块不显示），长按仅「复制」。
            # 被测正文（作者正则/脚本产物）渲染在此，两态都可见。
            '<div class="item" data-message-role="ai"%(frame)s>'
            '<article class="touch-scope" data-chat="message" data-from="ai" data-state="done" '
            'data-msg-id="-1" data-msg-kind="first">'
            '<div data-chat="message-avatar"></div><div data-chat="message-name"></div>'
            '<div class="content left"%(body)s>%(tested)s</div>'
            '<time data-chat="message-time"></time>'
            '<div data-chat="message-actions"></div>%(message_extra)s'
            '</article></div>'
            # 开场白选择块（仅初始态）：可点 chip → 正文注入输入框
            '%(prologue)s'
            # 用户消息（仅发送后态）：2 圆钮（编辑/分享）
            '<div class="item" data-message-role="user" data-msg-state="sent"%(frame)s>'
            '<article class="touch-scope"%(msg_user)s data-msg-kind="user">'
            '<div data-chat="message-avatar"></div><div data-chat="message-name"></div>'
            '<div class="content right"%(body)s>用户示例消息</div>'
            '<time data-chat="message-time"></time>'
            '<div data-chat="message-actions">%(actuser)s</div>%(message_extra)s'
            '</article></div>'
            # AI 回复（仅发送后态）：3 圆钮（刷新/编辑/分享）
            '<div class="item" data-message-role="ai" data-msg-state="sent"%(frame)s>'
            '<article class="touch-scope"%(msg_ai)s data-msg-kind="ai">'
            '<div data-chat="message-avatar"></div><div data-chat="message-name"></div>'
            '<div class="content left"%(body)s>AI 回复示例（发送后出现；作者正则/脚本亦渲染于此）</div>'
            '<time data-chat="message-time"></time>'
            '<div data-chat="message-actions">%(actai)s</div>%(message_extra)s'
            '</article></div>'
            '</div></main>'
            '%(summarybubble)s'
            '%(historyloading)s'
            '<div data-slot="left"></div><div data-slot="right"></div>'
            '%(stage)s'
            '<footer class="chat-bottom chat-input-scope pano-input-bar"%(composer)s>'
            '%(toolbar)s'
            # 底栏：真实钩子名（[data-chat=shortcut] / instruction-bar / composer-row /
            # composer-field / assistant / model-chip / more），作者按手册写选择器能命中。
            '<div class="composer-shortcut-wrap">'
            '<div class="pano-shortcuts"%(shortcut)s>'
            '<button class="pano-shortcut" type="button" data-action="model">模型设置</button>'
            '<button class="pano-shortcut" type="button" data-action="style">对话设置</button>'
            '<button class="pano-shortcut" type="button" data-action="instructions">选择指令</button>'
            '<button class="pano-shortcut" type="button" data-action="summary">总结剧情</button>'
            '<button class="pano-shortcut" type="button" data-action="conversations">新的聊天</button>'
            '<button class="pano-shortcut" type="button" data-action="persona">用户人设</button>'
            '</div>'
            '<div class="hidden"%(instruction_bar)s>'
            '<button type="button"%(instruction_back)s>'
            '<span class="instruction-back-arrow">&#8249;</span></button>'
            '<div class="instruction-scroll">'
            '<button type="button"%(instruction_chip)s>清空输入框</button>'
            '<button type="button"%(instruction_chip)s>通用总结</button>'
            '<button type="button"%(instruction_chip)s>选项生成</button>'
            '<button type="button"%(instruction_chip)s>字数控制</button>'
            '</div></div></div>'
            # 输入行：子件顺序与真机一致（assistant-anchor / composer-field / more），
            # field 内是 composer-tools（展开才显示）→ input → model-chip(order:-1) → send。
            '<div class="pano-compose-row composer-row">'
            '<div class="assistant-anchor">'
            '<button class="pano-compose-icon" type="button" title="AI帮聊"%(assistant)s>'
            '<span class="pano-glyph">&#128161;</span>'
            '<span class="beta-badge">8</span></button>'
            '%(assistant_tip)s'
            '</div>'
            '<div class="pano-input-shell composer-field">'
            '%(composertools)s'
            '<textarea class="uni-textarea-textarea" rows="1" placeholder="快来聊天吧~"%(input)s></textarea>'
            '<button class="pano-compose-icon" type="button" title="模型"%(model_chip)s>80</button>'
            '<button class="pano-send send-msg" type="button" title="发送"%(send)s>'
            '<span class="pano-glyph">&#10148;</span></button>'
            '</div>'
            '<button class="pano-compose-icon" type="button" title="更多" data-action="more">'
            '<span class="pano-glyph">&#65291;</span></button>'
            '</div>'
            '%(morepanel)s'
            '%(sharebar)s'
            '%(sharepickbar)s'
            '</footer>'
            '%(messagemenu)s'
            '%(alertbox)s'
            '%(snack)s'
            '%(snackbar)s'
            '%(shareshot)s'
            '%(hostpopups)s'
            '</div></div>'
            '%(sendscaffold)s'
            '%(panelscaffold)s'
        ) % dict(hooks, runtime=runtime, tested=tested_content,
                 statusbar=statusbar_node, hoisted=hoisted,
                 sendscaffold=send_scaffold,
                 roleintro=SANDBOX_ROLE_INTRO, prologue=SANDBOX_PROLOGUE,
                 actuser=_sandbox_actions_html("user"), actai=_sandbox_actions_html("ai"),
                 panelscaffold=SANDBOX_PANEL_SCAFFOLD,
                 morepanel=SANDBOX_MORE_PANEL,
                 composertools=SANDBOX_COMPOSER_TOOLS,
                 summarybubble=SANDBOX_SUMMARY_BUBBLE,
                 historyloading=SANDBOX_HISTORY_LOADING,
                 messagemenu=SANDBOX_MESSAGE_MENU,
                 alertbox=SANDBOX_ALERT,
                 snack=SANDBOX_SNACK, snackbar=SANDBOX_SNACKBAR,
                 sharebar=SANDBOX_SHARE_BAR, sharepickbar=SANDBOX_SHARE_PICK_BAR,
                 shareshot=SANDBOX_SHARE_SHOT, hostpopups=SANDBOX_HOST_POPUPS)
    elif platform == "mmd":
        page = _mmd_panorama_page(tested_content, hooks, runtime, send_scaffold)
    else:
        page = (
            '%(runtime)s'
            '%(hoisted)s'
            '<div class="page"%(root)s>'
            '<div class="topTabbar"%(header)s><span%(header_title)s>ST Chat Preview</span>'
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
        ) % dict(hooks, runtime=runtime, tested=tested_content,
                 statusbar=statusbar_node, hoisted=hoisted,
                 sendscaffold=send_scaffold)

    if sandbox:
        # 🚨 沙盒不再叠中性 PANORAMA_CSS（与 mmd 分支同样的理由：两份规则互相打架）。
        # 实测暴露的具体伤害：`.pano-input-bar .uni-textarea-textarea{font:inherit}` 把
        # 输入框字号顶成 16px，而真机是浏览器默认 13.33px（真机 input 本体不设字号，
        # 字号只在 ::placeholder 规则里）。另外那份还带 `.content.right{background:#3a76f0}`
        # 蓝气泡与 `.pano-input-bar{position:fixed;z-index:90000}`，对沙盒全是假的。
        shell_css = ""
        chrome_css = _sandbox_chrome_css()
    elif platform == "mmd":
        # MMD 走实测复刻外壳，不叠中性骨架（两份规则会互相打架）。
        shell_css = _mmd_panorama_css()
        chrome_css = ""
    else:
        shell_css = PANORAMA_CSS
        chrome_css = ""
    frame_doc = "<style>%s</style><style>%s</style><style>%s</style>%s" % (
        MARKER_CSS, shell_css, chrome_css, page)
    srcdoc = html_mod.escape(frame_doc, quote=True)

    n = _script_count(obj)
    banner = make_banner(platform, src_name, n).replace("预览平台", "全景预览 ｜ 平台")
    audit = _findregex_audit_html(obj, platform) + _onclick_audit_html(chat_inner, platform)
    if sandbox:
        audit += ('<div class="frag-warn">NOTE 已模拟：[data-chat]/[data-slot] 钩子结构与 14 个 '
                  '--chat-* 设计令牌默认值（深色一套为实测真值；官方手册只记 10 个），另注入 '
                  '--rpx 尺寸基准；--chat-viewport-height 由模拟宿主写在 root 内联 style，'
                  '并随 iframe resize/键盘 inset 更新（后者不属那 14 个）。'
                  '</div>'
                  '<div class="frag-warn">NOTE 气泡那圈淡描边是<b>默认关闭的预览辅助线，'
                  '真机上没有</b>：实测平台气泡三色与页面背景<b>同色</b>（深色都是 #17181a），'
                  '气泡默认与背景无视觉分界。想临时看边界，可在 root 上添加 '
                  'data-preview-bubble-outline 属性；正式效果仍以不带辅助线为准。</div>'
                  '<div class="frag-warn">NOTE 已装 <b>window.sdk 本地仿真</b>'
                  '（mmdsandbox-sim.js，置于作者脚本之前）：11 个顶层键、30 个能力、'
                  '12 个事件、冷启动 message:new → message:mount → message:done → ready、'
                  'mount/done 对晚订阅补发而 ready 不补发、payload 恰 '
                  '{content,id,role,serverId}、message scope 收窄、stage/theme/switch。'
                  '这是<b>本地日常仿真，不是完整平台</b>，逐项精度见下表。</div>')
        audit += _sandbox_budget_audit_html(obj, platform)
        audit += ('<div class="frag-warn" data-preview-accuracy="probe-needed">'
                  'WARN Markdown 管线为 <b>probe-needed</b>：替换内容会过一遍 Markdown，'
                  '但具体边界未确证（已知 4 空格缩进<b>不会</b>变代码块，与手册相反；'
                  '反引号里的 HTML 会原样留成文本）。预览<b>不模拟</b> Markdown，'
                  '这里只做保守预警，不声称精确——排版异常请回真实聊天页确认。</div>')
        audit += _sandbox_accuracy_html(profile)
    if isinstance(obj, dict):
        audit += "".join('<div class="frag-warn">ERROR 悬空标记：%s</div>' % html_mod.escape(x)
                         for x in find_dangling_markers(obj, platform))
    if sandbox:
        # 沙盒走仿真控制台（模拟平台侧动作）；MMD/ST 保留原路由脚手架工具。
        tools = _sandbox_toolbar_html(obj)
        label = ('沙盒聊天页仿真 · profile=%s · 深色实测外壳 · window.sdk 已装'
                 % html_mod.escape(profile))
    else:
        tools = (
            '<div class="preview-tools" data-preview-tools="1">'
            '<span class="preview-tools-label">预览测试工具</span>'
            '<button class="preview-tool" type="button" title="追加动态 AI 内容" '
            'onclick="document.querySelector(\'.pano-frame\').contentWindow.__tavernPreview.addAI()">追加 AI</button>'
            '<button class="preview-tool" type="button" title="模拟离开聊天页" '
            'onclick="document.querySelector(\'.pano-frame\').contentWindow.__tavernPreview.leave()">离开聊天页</button>'
            '<button class="preview-tool" type="button" title="模拟返回聊天页" '
            'onclick="document.querySelector(\'.pano-frame\').contentWindow.__tavernPreview.returnToChat()">返回聊天页</button>'
            + (_mmd_panel_tools_html() if platform == "mmd" else "")
            + '</div>')
        label = ('全景预览（所有组件组合 · 固定输入框 · 发送测试'
                 + (' · 弹窗仿真）' if platform == "mmd" else '）'))
    audit_panel = (
        '<details class="pano-audit"><summary>诊断与证据说明（默认折叠）</summary>'
        '<div class="pano-audit-body">%s</div></details>' % audit
    ) if audit else ""
    frame_sandbox = (
        load_sandbox_contract()["environment"]["hostIframeSandbox"]["attribute"]
        if sandbox else "allow-scripts allow-same-origin"
    )
    body = (
        '<div class="frag"><div class="frag-label">%s</div>%s'
        '<iframe class="pano-frame" srcdoc="%s" sandbox="%s"></iframe>'
        '</div>%s' % (label, tools, srcdoc, frame_sandbox, audit_panel)
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


def apply_platform_limits(rs, platform, script_badges=True):
    """按平台改写 HTML；当前 MMD 额外禁用 allowlist 外的真实 inline onclick。
    沙盒模式不净化 onclick，script_badges 只控制预览角标，不影响脚本执行。"""
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
    out = re.sub(r"<script\b[\s\S]*?</script>", script_repl, out, flags=re.I) if script_badges else out
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
    p.add_argument("--sandbox-profile", choices=list(SANDBOX_PROFILES), default="chat",
                   help="仅 --platform mmdsandbox 有效：chat=聊天页完整环境（默认）；"
                        "thin-preview=创卡页瘦预览（save.get/keys 同步抛 SdkError，写类能力被拒）")
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
        pano_html = assemble_panorama(obj, args.platform, args.file,
                                      sandbox_profile=args.sandbox_profile)
        path = args.output if (args.output and args.mode == "panorama") else \
            _default_output_path(args.file, "panorama", args.platform)
        if args.platform == "mmdsandbox":
            summary = ("全景预览  平台: mmdsandbox  profile: %s  "
                       "（已装 window.sdk 本地仿真；能力精度见页内诊断表）" % args.sandbox_profile)
        else:
            summary = ("全景预览  平台: %s  （固定输入框+发送+占位AI气泡，所有组件组合显示）"
                       % args.platform)
        outputs.append((path, pano_html, summary))

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
