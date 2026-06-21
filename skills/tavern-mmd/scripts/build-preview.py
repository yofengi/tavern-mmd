#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 预览脚本 build-preview.py
把状态栏/美化正则的 replaceString 拼成完整 HTML 沙箱文件，按平台注入渲染限制。
主AI 用自带 Preview 工具打开看渲染、测交互（子代理无法与渲染工具交互）。

用法:
  python build-preview.py <文件> --platform <oldmmd|mmd|st> [-o 输出.html]

平台渲染差异:
  st     : 原样渲染，<script>/ES6 全执行
  oldmmd : <script>剥离并裸露源码(红框)；onerror/onclick内ES6标红但仍执行；onerror点火器正常
  mmd    : <script>/ES6 全执行（已确认支持）；script 加"✓script"角标标明正常执行

退出码: 0=生成成功  2=用法/读取错误
"""
import sys
import json
import argparse
import re
import html as html_mod

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def load(path):
    with open(path, "rb") as f:
        rawb = f.read()
    txt = rawb.decode("utf-8-sig", errors="replace")
    return json.loads(txt)


def extract_fragments(obj):
    """返回 [(scriptName, findRegex, replaceString), ...]，仅含含HTML的替换。"""
    frags = []
    if isinstance(obj, dict) and "regex_scripts" in obj:
        scripts = obj.get("regex_scripts", [])
    elif isinstance(obj, list):
        scripts = obj
    else:
        scripts = []
    for sc in scripts:
        if not isinstance(sc, dict):
            continue
        rs = sc.get("replaceString", "")
        name = sc.get("scriptName", sc.get("name", ""))
        fr = sc.get("findRegex", "")
        # 含任意 HTML 标签的替换都渲染；跳过纯信标转换器（无标签的占位文本）
        if re.search(r"<[a-zA-Z][a-zA-Z0-9]*[\s/>]", rs):
            frags.append((name, fr, rs))
    return frags


def detect_blank_bar_risk(rs):
    """MMD markdown 管线会把标签之间的裸换行补成空 <p> 撑出横向空白条。
    检测 replaceString 里标签闭合与下一个标签之间是否夹着换行（>\\n...<）。"""
    return bool(re.search(r">\s*\n\s*<", rs))


HTML_TAGS = set("""a audio b big body br button code del details div em font form h1 h2 h3 h4 h5 h6
head hr html i iframe img input ins label li link mark meta nav ol option p pre script section select small span
strong style sub summary sup table tbody td textarea th thead title tr u ul video""".split())


def _parse_regex_literal(fr):
    """返回 (pattern, flags) 或 None；不支持的 JS flag 忽略。"""
    if not (isinstance(fr, str) and fr.startswith("/")):
        return None
    end = fr.rfind("/")
    if end <= 0:
        return None
    pattern = fr[1:end]
    js_flags = fr[end + 1:]
    flags = 0
    if "i" in js_flags:
        flags |= re.I
    if "m" in js_flags:
        flags |= re.M
    if "s" in js_flags:
        flags |= re.S
    try:
        return re.compile(pattern, flags)
    except re.error:
        return None


def _js_repl_to_python(repl):
    """把 JS/MMD 替换里的 $1/$2 转成 Python re.sub 的 \\1/\\2。
    （已弃用：影渲法引擎 replaceString 含正则字面量 \\d/\\s，被 re.sub 模板当转义会崩。
    改用 _make_repl_func 函数式替换。保留此函数仅作兼容。）"""
    return re.sub(r"\$(\d+)", r"\\\1", repl)


def _make_repl_func(rs):
    """返回供 re.sub 用的替换函数，按 MMD 真实语义展开：
      - `$1`/`$2` → 对应捕获组
      - `\\\\` → 单个 `\\`（模板转义折叠：JSON 存的双反斜杠渲染成单）
      - 其余字符原样输出
    用函数式替换而非 re.sub 模板字符串，故 replaceString 里的单反斜杠序列
    （如影渲法/雷达法引擎正则 \\d \\s）不会触发 're bad escape' 崩溃——
    这正是之前预览脚本在影渲法引擎上崩的根因。"""
    def repl(m):
        out = []
        i = 0
        n = len(rs)
        while i < n:
            ch = rs[i]
            if ch == "$" and i + 1 < n and rs[i + 1].isdigit():
                j = i + 1
                while j < n and rs[j].isdigit():
                    j += 1
                idx = int(rs[i + 1:j])
                try:
                    out.append(m.group(idx) or "")
                except (IndexError, re.error):
                    out.append(rs[i:j])
                i = j
            elif ch == "\\" and i + 1 < n and rs[i + 1] == "\\":
                out.append("\\")          # \\ → \（模板转义折叠）
                i += 2
            else:
                out.append(ch)
                i += 1
        return "".join(out)
    return repl


def apply_regex_pipeline(obj):
    """模拟 MMD：statusbar + beginning 经 regex_scripts 全量替换后的 HTML。"""
    if isinstance(obj, list):
        return ""
    text = str(obj.get("statusbar", "")) + str(obj.get("beginning", ""))
    for sc in obj.get("regex_scripts", []):
        if not isinstance(sc, dict):
            continue
        fr = sc.get("findRegex", "")
        rs = sc.get("replaceString", "")
        if not isinstance(fr, str) or not isinstance(rs, str) or not fr:
            continue
        regex = _parse_regex_literal(fr)
        if regex is None:
            text = text.replace(fr, rs)
        else:
            text = regex.sub(_make_repl_func(rs), text)
    return text


def find_dangling_markers(obj):
    """找出 statusbar/beginning 中无对应 findRegex 消费的自定义 <标记>。

    判据=该标记经完整正则管线后是否仍残留在渲染结果里。
    （旧逻辑用裸标记 `<g3>` 去 rx.search 试探，对"整段匹配型" findRegex
    如 /<g3>([\\s\\S]*?)<\\/g3>/ 会误判悬空——影渲法/雷达法常用整段匹配。
    改为 post-pipeline 残留检测：被消费的标记不会出现在最终 HTML 里。）"""
    if isinstance(obj, list):
        return []
    hay = str(obj.get("statusbar", "")) + str(obj.get("beginning", ""))
    rendered = apply_regex_pipeline(obj)
    errors = []
    seen = set()
    for m in re.finditer(r"<([A-Za-z一-鿿][A-Za-z0-9_.\-一-鿿]*)>", hay):
        marker = m.group(0)
        name = m.group(1).lower()
        if name in HTML_TAGS:
            continue
        if marker in seen:
            continue
        # 被某条 findRegex 消费的标记，跑完管线后不会残留；仍残留=真悬空
        if marker in rendered:
            errors.append(marker)
            seen.add(marker)
    return errors


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
        i = start + len(needle)
        quote = None
        while i < len(html):
            ch = html[i]
            if quote:
                if ch == quote:
                    quote = None
            elif ch == '"' or ch == "'":
                quote = ch
            elif ch == ">":
                end = i + 1
                yield start, end, html[start:end]
                pos = end
                break
            i += 1
        else:
            return


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
    # 1) 静态状态栏骨架（KV/已渲染状态栏）
    for pat in [r"<div[^>]*class=[\"'][^\"']*z-status-box[^\"']*[\"'][^>]*>[\s\S]*?</div>"]:
        for m in list(re.finditer(pat, rest, re.I)):
            status_parts.append(m.group(0))
            rest = rest.replace(m.group(0), "", 1)

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
        return assemble_html(extract_fragments(obj), platform, src_name)
    rendered = apply_regex_pipeline(obj)
    first, status, floating = split_preview_panels(rendered)
    audit = "".join('<div class="frag-warn">ERROR 悬空标记：%s</div>' % html_mod.escape(x)
                    for x in find_dangling_markers(obj))
    body = "\n".join([
        _panel("第一句话整合预览", first, platform, "beginning+statusbar"),
        _panel("状态栏单独预览", status, platform, "status"),
        _panel("悬浮组件预览", floating, platform, "floating/sidebar"),
        audit,
    ])
    banner = make_banner(platform, src_name, len(obj.get("regex_scripts", [])))
    return PAGE_TEMPLATE % {"platform": platform, "banner": banner,
                            "body": body, "marker_css": MARKER_CSS}


# 全景预览聊天页骨架 CSS（中性默认；被测的全局美化用 !important 会正常压过，与MMD真机一致）。
# .page 是全高 flex 列容器；.pano-chat 滚动区 flex:1；.pano-input-bar 固定底部。
PANORAMA_CSS = """html,body{height:100%;margin:0}
body{display:flex;flex-direction:column;font-family:system-ui,sans-serif;background:#fff;color:#222}
.page{flex:1;display:flex;flex-direction:column;min-height:0;background:#fff}
.pano-chat{flex:1;overflow-y:auto;padding:14px 12px 88px;-webkit-overflow-scrolling:touch}
.pano-chat .chat-body{display:flex;flex-direction:column}
.item{display:flex;margin:10px 0}
.item .content{max-width:82%;padding:10px 13px;border-radius:10px;line-height:1.55;word-break:break-word}
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
%(marker_css)s
.pano-frame{flex:1;width:100%%;border:0;display:block;background:#fff;min-height:480px}
</style></head>
<body>
%(banner)s
%(body)s
</body></html>"""


# 全景发送脚手架：预览工具自带，非被测产物。走 img onerror 点火器（ES5），三平台都执行，
# 且不被 apply_platform_limits 的 <script> 剥离器当成被测内容裸露。
PANORAMA_SEND_SCAFFOLD = (
    '<img src="x" data-pano-scaffold="1" style="display:none" '
    "onerror=\"(function(){"
    "var ta=document.querySelector('.uni-textarea-textarea');"
    "var btn=document.querySelector('.pano-send');"
    "var chat=document.querySelector('.pano-chat');"
    "if(!ta||!btn||!chat)return;"
    "var addMsg=function(side,text){"
    "var it=document.createElement('div');it.className='item';"
    "var ct=document.createElement('div');ct.className='content '+side;"
    "ct.textContent=text;it.appendChild(ct);chat.appendChild(it);"
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
        chat_inner = "".join("%s" % rs for _, _, rs in extract_fragments(obj))
    else:
        chat_inner = apply_regex_pipeline(obj)

    # 聊天页结构：套上真实 MMD 类名（.page/.chat/.chat-bg/.chat-body/.item/.content.left、
    # .chat-bottom/.chat-input-scope），让全局美化 CSS（按 MMD 选择器写）能命中；pano-* 类只负责
    # 布局与固定输入栏。否则美化的页面底色/气泡底色规则匹配不到，会露出白底（washed out）。
    page = (
        '<div class="page">'
        '<div class="chat chat-bg pano-chat" id="pano-chat">'
        '<div class="chat-body">'
        '<div class="item"><div class="touch-scope"><div class="content left">%s</div></div></div>'
        '</div></div>'
        '<div class="chat-bottom chat-input-scope pano-input-bar">'
        '<textarea class="uni-textarea-textarea" rows="1" placeholder="输入消息（Enter 发送，Shift+Enter 换行）"></textarea>'
        '<button class="pano-send send-msg" type="button">发送</button>'
        '</div>'
        '</div>'
        '%s'
    ) % (chat_inner, PANORAMA_SEND_SCAFFOLD)

    processed = apply_platform_limits(page, platform)
    frame_doc = "<style>%s</style><style>%s</style>%s" % (MARKER_CSS, PANORAMA_CSS, processed)
    srcdoc = html_mod.escape(frame_doc, quote=True)

    n = len(obj.get("regex_scripts", [])) if isinstance(obj, dict) else len(obj)
    banner = make_banner(platform, src_name, n).replace("预览平台", "全景预览 ｜ 平台")
    audit = ""
    if isinstance(obj, dict):
        audit = "".join('<div class="frag-warn">ERROR 悬空标记：%s</div>' % html_mod.escape(x)
                        for x in find_dangling_markers(obj))
    body = (
        '<div class="frag"><div class="frag-label">全景预览（所有组件组合 · 固定输入框 · 发送测试）</div>'
        '<iframe class="pano-frame" srcdoc="%s" sandbox="allow-scripts allow-same-origin"></iframe>'
        '</div>%s' % (srcdoc, audit)
    )
    return PANORAMA_PAGE_TEMPLATE % {"platform": platform, "banner": banner,
                                     "body": body, "marker_css": MARKER_CSS}


def assemble_html(frags, platform, src_name):
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
    body = "\n".join(body_parts)
    banner = make_banner(platform, src_name, len(frags))
    return PAGE_TEMPLATE % {"platform": platform, "banner": banner,
                            "body": body, "marker_css": MARKER_CSS}


def apply_platform_limits(rs, platform):
    """按平台改写HTML片段以模拟渲染限制。"""
    if platform == "st":
        return rs

    out = rs

    # 1. <script>...</script>：oldmmd 剥离并裸露源码；mmd 保留但标黄
    def script_repl(m):
        full = m.group(0)
        if platform == "oldmmd":
            return '<pre class="mmd-stripped">%s</pre>' % html_mod.escape(full)
        else:  # mmd
            return '<div class="mmd-warn-badge" title="当前MMD已确认支持 script，正常执行">✓script</div>' + full
    out = re.sub(r"<script\b[\s\S]*?</script>", script_repl, out, flags=re.I)

    # 2. onerror/onclick 内 ES6 语法：仅旧版MMD会截断，标黄高亮（不阻止执行，便于AI测交互）
    #    当前MMD已确认支持ES6，不标记。
    def es6_mark(m):
        tag = m.group(0)
        if re.search(r"on\w+\s*=\s*\"[^\"]*(=>|\blet\b|\bconst\b|`)[^\"]*\"", tag):
            return tag.replace(">", ' data-mmd-es6="真实平台此处会截断">', 1)
        return tag
    if platform == "oldmmd":
        out = re.sub(r"<[a-zA-Z][^>]*on\w+\s*=[^>]*>", es6_mark, out)

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
        return assemble_preview(obj, platform, src_name), len(obj.get("regex_scripts", []))
    frags = extract_fragments(obj)
    if not frags:
        print("[WARN] 未找到含HTML的替换片段（可能是纯数据转换器）。")
    return assemble_html(frags, platform, src_name), len(frags)


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
    except (OSError, json.JSONDecodeError) as e:
        print("[ERROR] 读取/解析失败: %s" % e)
        print("提示: 先用 validate.py 确认 JSON 合法。")
        sys.exit(2)

    import os
    base = os.path.splitext(args.file)[0]

    def write(path, content):
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print("[OK] 预览已生成: %s" % path)

    if args.mode in ("panels", "both"):
        panels_html, frags_count = _build_panels_html(obj, args.platform, args.file)
        path = args.output if (args.output and args.mode == "panels") else \
            "%s-preview-%s.html" % (base, args.platform)
        write(path, panels_html)
        print("片段数: %d  平台: %s  模式: 三面板诊断" % (frags_count, args.platform))

    if args.mode in ("panorama", "both"):
        pano_html = assemble_panorama(obj, args.platform, args.file)
        path = args.output if (args.output and args.mode == "panorama") else \
            "%s-panorama-%s.html" % (base, args.platform)
        write(path, pano_html)
        print("全景预览  平台: %s  （固定输入框+发送+占位AI气泡，所有组件组合显示）" % args.platform)

    if args.mode == "both":
        print("工作流：先看三面板审核单组件 → 再看全景二次审核组合效果（全景不默认关闭，留给你自查）。")

    dangling = find_dangling_markers(obj) if isinstance(obj, dict) else []
    if dangling:
        print("[ERROR] 悬空标记: %s" % ", ".join(dangling))
        sys.exit(1)
    print("请用浏览器或 Preview 工具打开查看渲染与交互。")


if __name__ == "__main__":
    main()
