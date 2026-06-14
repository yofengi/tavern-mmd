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
  mmd    : <script>/ES6 全执行（已确认支持）；script 加"保留回退"黄角标提醒兼容旧版

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
        # 只渲染含HTML标签的替换（跳过纯信标转换器如 <span style=display:none>[$1=$2]</span>）
        if "<style" in rs or "<div" in rs or "<img" in rs:
            frags.append((name, fr, rs))
    return frags


def assemble_html(frags, platform, src_name):
    """把所有HTML片段拼进一个预览页。"""
    body_parts = []
    for name, fr, rs in frags:
        processed = apply_platform_limits(rs, platform)
        body_parts.append(
            '<div class="frag"><div class="frag-label">规则: %s （findRegex: %s）</div>%s</div>'
            % (html_mod.escape(name), html_mod.escape(fr), processed))
    body = "\n".join(body_parts)
    banner = make_banner(platform, src_name, len(frags))
    return PAGE_TEMPLATE % {"platform": platform, "banner": banner, "body": body}


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
            return '<div class="mmd-warn-badge" title="当前MMD已确认支持script；保留 onerror 回退以兼容旧版">⚠保留回退</div>' + full
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
              "mmd": "当前MMD（支持script/ES6，推荐ES5）",
              "oldmmd": "旧版MMD（禁script/ES5）"}
    return ('<div class="banner banner-%s">预览平台: %s ｜ 来源: %s ｜ %d 个HTML片段</div>'
            % (platform, labels.get(platform, platform), html_mod.escape(src_name), n))


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
.mmd-stripped{display:block;margin:8px;padding:10px;border:2px solid #f85149;border-radius:6px;
  background:#2d0a0a;color:#ff7b72;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-all}
.mmd-stripped::before{content:'⚠ 旧版MMD会剥离此标签，不执行（源码裸露）：';display:block;color:#f85149;margin-bottom:6px;font-weight:600}
[data-mmd-es6]{outline:2px solid #d29922 !important;outline-offset:1px;position:relative}
[data-mmd-es6]::after{content:'⚠ES6:'attr(data-mmd-es6);position:absolute;top:-8px;right:0;background:#d29922;color:#000;font-size:9px;padding:1px 4px;border-radius:3px;z-index:99}
.mmd-warn-badge{display:inline-block;background:#d29922;color:#000;font-size:10px;padding:1px 6px;border-radius:3px;margin:2px}
</style></head>
<body>
%(banner)s
%(body)s
</body></html>"""


def main():
    p = argparse.ArgumentParser(description="tavern-mmd 平台预览生成")
    p.add_argument("file")
    p.add_argument("--platform", choices=["oldmmd", "mmd", "st"], required=True)
    p.add_argument("-o", "--output", help="输出HTML路径，默认同目录 <文件名>-preview-<平台>.html")
    args = p.parse_args()

    try:
        obj = load(args.file)
    except (OSError, json.JSONDecodeError) as e:
        print("[ERROR] 读取/解析失败: %s" % e)
        print("提示: 先用 validate.py 确认 JSON 合法。")
        sys.exit(2)

    frags = extract_fragments(obj)
    if not frags:
        print("[WARN] 未找到含HTML的替换片段（可能是纯数据转换器）。")
    out_html = assemble_html(frags, args.platform, args.file)

    out_path = args.output
    if not out_path:
        import os
        base = os.path.splitext(args.file)[0]
        out_path = "%s-preview-%s.html" % (base, args.platform)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write(out_html)
    print("[OK] 预览已生成: %s" % out_path)
    print("片段数: %d  平台: %s" % (len(frags), args.platform))
    print("请用浏览器或 Preview 工具打开查看渲染与交互。")


if __name__ == "__main__":
    main()
