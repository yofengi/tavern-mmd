#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build-preview.py 单元测试。运行: python -m unittest test_build_preview -v"""
import unittest
import html as html_mod
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

bp = importlib.import_module("build-preview")


class TestExtractFragments(unittest.TestCase):
    def test_table_and_form_fragments_kept(self):
        obj = {"regex_scripts": [
            {"scriptName": "表格", "replaceString": "<table><tr><td>HP</td></tr></table>"},
            {"scriptName": "表单", "replaceString": "<input type=text><button>提交</button>"},
            {"scriptName": "div", "replaceString": "<div>x</div>"},
        ]}
        names = [f[0] for f in bp.extract_fragments(obj)]
        self.assertEqual(set(names), {"表格", "表单", "div"})

    def test_pure_beacon_converter_skipped(self):
        obj = {"regex_scripts": [
            {"scriptName": "信标", "replaceString": "[$1=$2]"},
        ]}
        self.assertEqual(bp.extract_fragments(obj), [])

    def test_nonstring_replace_is_skipped(self):
        obj = {"regex_scripts": [
            {"scriptName": "坏字段", "replaceString": 123},
            {"scriptName": "正常", "replaceString": "<div>x</div>"},
        ]}
        self.assertEqual([f[0] for f in bp.extract_fragments(obj)], ["正常"])


class TestFragmentIsolation(unittest.TestCase):
    def test_fragments_wrapped_in_isolated_iframe(self):
        obj = {"regex_scripts": [
            {"scriptName": "A", "replaceString": "<style>.box{color:red}</style><div class=box>A</div>"},
            {"scriptName": "B", "replaceString": "<style>.box{color:blue}</style><div class=box>B</div>"},
        ]}
        frags = bp.extract_fragments(obj)
        html = bp.assemble_html(frags, "mmd", "t.json")
        self.assertEqual(html.count("<iframe"), 2)
        self.assertIn("srcdoc=", html)

    def test_iframe_srcdoc_escaped(self):
        obj = {"regex_scripts": [
            {"scriptName": "Q", "replaceString": '<div class="box">x</div>'},
        ]}
        html = bp.assemble_html(bp.extract_fragments(obj), "mmd", "t.json")
        self.assertIn("srcdoc=", html)
        self.assertIn("&quot;", html)


class TestMarkerCssInIframe(unittest.TestCase):
    def test_marker_css_injected_into_srcdoc(self):
        # apply_platform_limits 产出的标记元素（✓script 角标/onclick 描边）CSS 必须随片段进 iframe
        obj = {"regex_scripts": [
            {"scriptName": "S", "replaceString": "<script>var x=1</script><div>hi</div>"},
        ]}
        for platform in ("mmd", "mmdsandbox"):
            with self.subTest(platform=platform):
                html = bp.assemble_html(bp.extract_fragments(obj), platform, "t.json")
                import re
                src = re.search(r'srcdoc="([^"]*)"', html).group(1)
                self.assertIn(".mmd-warn-badge", src)
                self.assertIn("✓script", src)


class TestBlankBarDetection(unittest.TestCase):
    def test_bare_newline_between_tags_flagged(self):
        # 标签之间有裸换行 → MMD markdown 管线会补空<p>撑空白条，应在 frag-label 警告
        obj = {"regex_scripts": [
            {"scriptName": "换行", "replaceString": "<div>A</div>\n<div>B</div>"},
        ]}
        html = bp.assemble_html(bp.extract_fragments(obj), "mmd", "t.json")
        self.assertIn("空白条", html)

    def test_single_line_not_flagged(self):
        obj = {"regex_scripts": [
            {"scriptName": "单行", "replaceString": "<div>A</div><div>B</div>"},
        ]}
        html = bp.assemble_html(bp.extract_fragments(obj), "mmd", "t.json")
        self.assertNotIn("空白条", html)


class TestPipelinePreview(unittest.TestCase):
    def test_first_message_preview_applies_statusbar_and_beginning_regexes(self):
        obj = {
            "pageDepth": 2,
            "statusbar": "<theme>",
            "beginning": "第一句<choice><ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "主题", "findRegex": "/<theme>/", "replaceString": "<style>.theme{color:red}</style>"},
                {"scriptName": "选项", "findRegex": "/<choice>/", "replaceString": "<button>选项A</button>"},
                {"scriptName": "信标", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]\\s*/g", "replaceString": "<span style=\"display:none\">[$1=$2]</span>"},
                {"scriptName": "状态栏", "findRegex": "/<ztl>/", "replaceString": "<div class=\"z-status-box\">状态栏</div>"},
            ],
        }
        rendered = bp.apply_regex_pipeline(obj)
        self.assertIn("<style>.theme{color:red}</style>", rendered)
        self.assertIn("第一句", rendered)
        self.assertIn("<button>选项A</button>", rendered)
        self.assertIn("<div class=\"z-status-box\">状态栏</div>", rendered)
        self.assertNotIn("<choice>", rendered)
        self.assertNotIn("<ztl>", rendered)
        self.assertIn("[hp=85]", rendered)

    def test_assemble_preview_contains_integrated_statusbar_and_floating_panels(self):
        obj = {
            "pageDepth": 2,
            "statusbar": "",
            "beginning": "正文<ztl><float>",
            "regex_scripts": [
                {"scriptName": "状态栏", "findRegex": "/<ztl>/", "replaceString": "<div class=\"z-status-box\">状态栏</div>"},
                {"scriptName": "悬浮球", "findRegex": "/<float>/", "replaceString": "<button class=\"z-float-ball\" style=\"position:fixed;right:0\">球</button>"},
            ],
        }
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertIn("第一句话剩余预览", html)
        self.assertIn("状态栏单独预览", html)
        self.assertIn("悬浮组件预览", html)
        self.assertIn("正文", html)
        self.assertIn("z-status-box", html)
        self.assertIn("z-float-ball", html)

    def test_nested_statusbar_div_is_kept_whole(self):
        rendered = '正文<div class="z-status-box"><div>inner</div><div>tail</div></div>结尾'
        first, status, _, _ = bp.split_preview_panels(rendered)
        self.assertIn('<div class="z-status-box"><div>inner</div><div>tail</div></div>', status)
        self.assertNotIn("<div>tail</div></div>", first)

    def test_statusbar_panel_keeps_onerror_engine_when_runtime_creates_ui(self):
        obj = {
            "pageDepth": 2,
            "statusbar": "",
            "beginning": "正文<ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "状态栏", "findRegex": "/<ztl>/", "replaceString": "<img src=\"x\" data-radar-engine=\"1\" onerror=\"this.insertAdjacentHTML('afterend','&lt;div class=z-status-box&gt;状态栏&lt;/div&gt;')\">"},
            ],
        }
        html = bp.assemble_preview(obj, "mmd", "t.json")
        status_panel = html.split("状态栏单独预览", 1)[1].split("悬浮组件预览", 1)[0]
        self.assertIn("data-radar-engine", status_panel)
        self.assertNotIn("（无内容）", status_panel)

    def test_statusbar_panel_keeps_onerror_engine_when_js_contains_gt(self):
        obj = {
            "pageDepth": 2,
            "statusbar": "",
            "beginning": "正文<ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "状态栏", "findRegex": "/<ztl>/", "replaceString": "<img src=\"x\" onerror=\"if(c>0){var k='data-sid';this.rdrNode=1}\">"},
            ],
        }
        html = bp.assemble_preview(obj, "mmd", "t.json")
        status_panel = html.split("状态栏单独预览", 1)[1].split("悬浮组件预览", 1)[0]
        self.assertIn("rdrNode", status_panel)
        self.assertNotIn("（无内容）", status_panel)

    def test_regex_replacement_preserves_backslashes_without_python_escape_errors(self):
        obj = {
            "pageDepth": 2,
            "statusbar": "",
            "beginning": "[hp=85]",
            "regex_scripts": [
                {"scriptName": "带反斜杠", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]/g", "replaceString": "<span data-re=\"\\\\d+\">[$1=$2]</span>"},
            ],
        }
        rendered = bp.apply_regex_pipeline(obj)
        self.assertIn('data-re="\\\\d+"', rendered)
        self.assertIn("[hp=85]", rendered)

    def test_dangling_marker_is_reported_as_error(self):
        obj = {
            "pageDepth": 2,
            "statusbar": "<css>",
            "beginning": "正文<missing>",
            "regex_scripts": [
                {"scriptName": "样式", "findRegex": "/<css>/", "replaceString": "<style></style>"},
            ],
        }
        errors = bp.find_dangling_markers(obj)
        self.assertIn("<missing>", errors)
        self.assertNotIn("<css>", errors)

    def test_mmd_bare_findregex_is_skipped_and_audited_in_panels(self):
        obj = {"pageDepth": 2, "statusbar": "<x>", "beginning": "正文",
               "regex_scripts": [{"scriptName": "坏规则", "findRegex": "<x>",
                                  "replaceString": "<div id='must-not-render'>坏替换</div>"}]}
        rendered = bp.apply_regex_pipeline(obj, "mmd")
        self.assertIn("<x>", rendered)
        self.assertNotIn("must-not-render", rendered)
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertIn("ERROR 非法 findRegex", html)
        self.assertIn("ERROR 悬空标记", html)
        self.assertIn("&lt;x&gt;", html)
        self.assertNotIn("must-not-render", html)

    def test_mmd_bare_findregex_is_skipped_and_audited_in_panorama(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "正文<x>",
               "regex_scripts": [{"scriptName": "坏规则", "findRegex": "<x>",
                                  "replaceString": "<div id='must-not-render'>坏替换</div>"}]}
        html = bp.assemble_panorama(obj, "mmd", "t.json")
        self.assertIn("ERROR 非法 findRegex", html)
        self.assertIn("ERROR 悬空标记", html)
        self.assertNotIn("must-not-render", html)

    def test_low_level_unspecified_and_st_keep_bare_literal_compatibility(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "<x>",
               "regex_scripts": [{"scriptName": "兼容", "findRegex": "<x>",
                                  "replaceString": "<b>ok</b>"}]}
        self.assertEqual(bp.apply_regex_pipeline(obj), "<b>ok</b>")
        self.assertEqual(bp.apply_regex_pipeline(obj, "st"), "<b>ok</b>")
        self.assertEqual(bp.find_dangling_markers(obj), [])

    def test_non_global_global_and_sticky_pipeline_results(self):
        def render(find_regex):
            return bp.apply_regex_pipeline({"pageDepth": 2, "statusbar": "", "beginning": "aa ba",
                                            "regex_scripts": [{"findRegex": find_regex,
                                                               "replaceString": "X"}]}, "mmd")
        self.assertEqual(render("/a/"), "Xa ba")
        self.assertEqual(render("/a/g"), "XX bX")
        self.assertEqual(render("/a/y"), "Xa ba")
        self.assertEqual(render("/a/gy"), "XX ba")
        self.assertEqual(render("/b/y"), "aa ba")

    def test_js_replacement_tokens_pipeline_result(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "abc",
               "regex_scripts": [{"findRegex": "/(b)/",
                                  "replaceString": "$$|$&|$`|$'|$1"}]}
        self.assertEqual(bp.apply_regex_pipeline(obj, "mmd"), "a$|b|a|c|bc")

    def test_js_replacement_edge_tokens_match_js(self):
        def replace(find_regex, replacement):
            obj = {"pageDepth": 2, "statusbar": "", "beginning": "a",
                   "regex_scripts": [{"findRegex": find_regex,
                                      "replaceString": replacement}]}
            return bp.apply_regex_pipeline(obj, "mmd")
        self.assertEqual(replace("/(a)/", "$01"), "a")
        self.assertEqual(replace("/(a)/", "$10"), "a0")
        self.assertEqual(replace("/(a)/", "$0"), "$0")
        self.assertEqual(replace("/(a)/", "$00"), "$00")
        self.assertEqual(replace("/(a)/", "$2"), "$2")
        self.assertEqual(replace("/(?<x>a)/", "$<missing>"), "")
        self.assertEqual(replace("/(a)/", "$<x>"), "$<x>")

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_replacement_results_match_node_oracle(self):
        cases = [
            {"source": "a", "pattern": "(a)", "flags": "", "replacement": "\\"},
            {"source": "a", "pattern": "(a)", "flags": "", "replacement": "\\\\"},
            {"source": "a", "pattern": "(a)", "flags": "", "replacement": "$0"},
            {"source": "a", "pattern": "(a)", "flags": "", "replacement": "$00"},
            {"source": "a", "pattern": "(a)", "flags": "", "replacement": "$01"},
            {"source": "a", "pattern": "(a)", "flags": "", "replacement": "$10"},
            {"source": "abcdefghij", "pattern": "(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)",
             "flags": "", "replacement": "$10"},
        ]
        oracle = (
            "const fs=require('fs'),xs=JSON.parse(fs.readFileSync(0,'utf8'));"
            "process.stdout.write(JSON.stringify(xs.map(x=>x.source.replace(new RegExp(x.pattern,x.flags),x.replacement))))"
        )
        expected = json.loads(subprocess.run(
            [shutil.which("node"), "-e", oracle], input=json.dumps(cases),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", check=True).stdout)
        actual = []
        for case in cases:
            obj = {"pageDepth": 2, "statusbar": "", "beginning": case["source"],
                   "regex_scripts": [{"findRegex": "/%s/%s" % (case["pattern"], case["flags"]),
                                      "replaceString": case["replacement"]}]}
            actual.append(bp.apply_regex_pipeline(obj, "mmd"))
        self.assertEqual(actual, expected)

    def test_named_group_replacement_is_previewed(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "abc",
               "regex_scripts": [{"findRegex": "/(?<mid>b)/",
                                  "replaceString": "<$<mid>>"}]}
        self.assertEqual(bp.apply_regex_pipeline(obj, "mmd"), "a<b>c")
        self.assertEqual(bp.find_unsupported_preview_regexes(obj, "mmd"), [])

    def test_js_property_escape_is_valid_but_preview_unsupported_and_skipped(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "abc",
               "regex_scripts": [{"scriptName": "Unicode", "findRegex": r"/\p{L}+/u",
                                  "replaceString": "X"}]}
        self.assertEqual(bp.find_invalid_findregexes(obj, "mmd"), [])
        self.assertEqual(bp.apply_regex_pipeline(obj, "mmd"), "abc")
        unsupported = bp.find_unsupported_preview_regexes(obj, "mmd")
        self.assertEqual(unsupported[0][0], "Unicode")
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertIn("预览器不支持此 JS 正则", html)
        self.assertNotIn("ERROR 非法 findRegex：规则 Unicode", html)

    def test_python_named_group_is_invalid_not_preview_unsupported(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "abc",
               "regex_scripts": [{"scriptName": "Python", "findRegex": r"/(?P<n>b)/",
                                  "replaceString": "X"}]}
        self.assertTrue(bp.find_invalid_findregexes(obj, "mmd"))
        self.assertEqual(bp.find_unsupported_preview_regexes(obj, "mmd"), [])
        self.assertEqual(bp.apply_regex_pipeline(obj, "mmd"), "abc")

    def test_dangling_scans_each_start_end_and_introduced_occurrence(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "<x><x></x>",
               "regex_scripts": []}
        self.assertEqual(bp.find_dangling_markers(obj, "mmd"), ["<x>", "<x>", "</x>"])
        introduced = {"pageDepth": 2, "statusbar": "", "beginning": "<x>",
                      "regex_scripts": [{"findRegex": "/<x>/", "replaceString": "<new>"}]}
        self.assertEqual(bp.find_dangling_markers(introduced, "mmd"), ["<new>"])

    def test_mmd_array_is_rejected_while_st_array_remains_compatible(self):
        arr = [{"scriptName": "片段", "findRegex": "<x>",
                "replaceString": "<div id='st-fragment'>ok</div>"}]
        self.assertEqual(bp.extract_fragments(arr, "mmd"), [])
        mmd_html = bp.assemble_preview(arr, "mmd", "t.json")
        self.assertIn("ERROR 非法顶层结构", mmd_html)
        self.assertNotIn("st-fragment", mmd_html)
        self.assertEqual(len(bp.extract_fragments(arr, "st")), 1)

    def test_missing_four_field_is_rejected(self):
        obj = {"statusbar": "", "beginning": "x", "regex_scripts": []}
        self.assertEqual(bp.apply_regex_pipeline(obj, "mmd"), "")
        audit = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertIn("缺少 pageDepth", audit)
        self.assertIn("ERROR 非法顶层结构", audit)

    def test_slash_literal_parser_handles_escaped_and_class_slashes(self):
        for literal in (r"/a\/b/gi", r"/[/]path/"):
            with self.subTest(literal=literal):
                self.assertIsNotNone(bp._parse_regex_literal(literal))
    def test_slash_literal_parser_rejects_newline(self):
        self.assertIsNone(bp._parse_regex_literal("/a\nb/"))

    def test_onclick_sanitize_real_attrs_and_keep_clean_calls(self):
        source = ("<button id='unverified-call' onclick='window.__fn(event)'>u</button>"
                  "<button id='stop' onclick=event.stopPropagation()>s</button>"
                  "<button id='eval-id' onclick=\"eval(getElementById('FUNC').dataset.s)\">e</button>"
                  "<button id='guard-a' onclick='window.__fn&&__fn()'>a</button>"
                  "<button id='guard-b' onclick='window.__fn && window.__fn()'>b</button>"
                  "<button id='unverified-eval' onclick='eval(this.dataset.s)'>u</button>"
                  "<button id='bad' onclick='this.hidden=true'>b</button>")
        cleaned, removed = bp.sanitize_mmd_onclick(source)
        self.assertIn('onclick="event.stopPropagation()"', cleaned)
        for element_id in ("unverified-call", "unverified-eval", "bad"):
            tag = cleaned.split('id="%s"' % element_id, 1)[1].split(">", 1)[0]
            self.assertNotIn("onclick=", tag)
            self.assertIn('data-mmd-onclick-disabled="1"', tag)
        self.assertEqual(len(removed), 3)

    def test_onclick_sanitize_ignores_data_attr_and_script_string(self):
        source = ('<div data-onclick="this.hidden=true"></div>'
                  '<script>var x=\'<button onclick="this.hidden=true">\';</script>')
        cleaned, removed = bp.sanitize_mmd_onclick(source)
        self.assertEqual(removed, [])
        self.assertIn('data-onclick="this.hidden=true"', cleaned)
        self.assertIn('onclick="this.hidden=true"', cleaned)

    def test_apply_platform_limits_removes_invalid_inline_onclick(self):
        source = ('<button id="bad" onclick="eval(\'bad()\')">bad</button>'
                  '<button id="canonical" onclick="eval(getElementById(\'FUNC\').dataset.s)">good</button>'
                  '<button id="unverified" onclick="eval(this.dataset.s)">unverified</button>')
        cleaned = bp.apply_platform_limits(source, "mmd")
        bad_tag = cleaned.split('id="bad"', 1)[1].split(">", 1)[0]
        canonical_tag = cleaned.split('id="canonical"', 1)[1].split(">", 1)[0]
        unverified_tag = cleaned.split('id="unverified"', 1)[1].split(">", 1)[0]
        self.assertNotIn("onclick=", bad_tag)
        self.assertIn("data-mmd-onclick-disabled", bad_tag)
        self.assertIn("onclick=", canonical_tag)
        self.assertNotIn("onclick=", unverified_tag)
        self.assertIn("data-mmd-onclick-disabled", unverified_tag)

    def test_preview_audits_only_rendered_invalid_onclick(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "<x>",
               "regex_scripts": [
                   {"scriptName": "命中", "findRegex": "/<x>/",
                    "replaceString": "<button onclick='this.hidden=true'>x</button>"},
                   {"scriptName": "未命中", "findRegex": "/<never>/",
                    "replaceString": "<button onclick='window.bad=1'>n</button>"},
               ]}
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertEqual(html.count("ERROR inline onclick 已禁用"), 1)
        self.assertIn("data-mmd-onclick-disabled", html)

    def test_nonstring_findregex_is_skipped_and_audited(self):
        obj = [{"scriptName": "坏类型", "findRegex": 123,
                "replaceString": "<div id='must-not-render'>bad</div>"}]
        self.assertEqual(bp.extract_fragments(obj, "mmd"), [])
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertIn("ERROR 非法 findRegex", html)
        self.assertNotIn("must-not-render", html)


class TestRuntimeFloatingEngines(unittest.TestCase):
    """MMD 真正的悬浮球/侧边栏是运行时 <img onerror> 注入的可拖动按钮/抽屉，
    position:fixed 由 JS cssText 设，静态扫描看不到，必须靠引擎特征归入悬浮面板。"""

    DRAGGABLE_BALL = (
        "<img src=\"x\" data-float-ball=\"1\" style=\"display:none\" "
        "onerror=\"(function(e){var b=document.createElement('button');b.id='z-fab';"
        "b.style.cssText='position:fixed;left:18px;bottom:90px';"
        "b.addEventListener('mousedown',function(ev){});document.body.appendChild(b);e.remove();})(this)\">"
    )
    SLIDE_DRAWER = (
        "<img src=\"x\" data-sidebar=\"1\" style=\"display:none\" "
        "onerror=\"(function(e){var d=document.createElement('div');d.id='z-drawer';"
        "d.style.cssText='position:fixed;right:0;transform:translateX(100%)';"
        "document.body.appendChild(d);e.remove();})(this)\">"
    )
    RADAR = (
        "<img src=\"x\" data-radar-engine=\"1\" onerror=\"if(c>0){var k='data-sid';this.rdrNode=1}\">"
    )
    # Pointer Events 版悬浮球（build_float.py 现产物形状）：data-zsf-ball 标记 + pointerdown，
    # 无旧的 mousedown/touchstart。锁死"重写后仍归入悬浮面板、不被漏检"。
    POINTER_BALL = (
        "<img src=\"x\" data-zsf-ball=\"1\" style=\"display:none\" "
        "onerror=\"(function(e){var b=document.createElement('div');b.className='zsf-ball';"
        "b.addEventListener('pointerdown',function(ev){ev.stopPropagation();});"
        "document.body.appendChild(b);e.remove();})(this)\">"
    )
    # 无已知标记、仅靠通用回退（position:fixed + pointerdown）识别的悬浮球。
    POINTER_BALL_GENERIC = (
        "<img src=\"x\" style=\"display:none\" "
        "onerror=\"(function(e){var b=document.createElement('button');"
        "b.style.cssText='position:fixed;left:18px;bottom:90px';"
        "b.addEventListener('pointerdown',function(ev){});document.body.appendChild(b);e.remove();})(this)\">"
    )

    def _panels(self, html):
        first = html.split("状态栏单独预览", 1)[0]
        status = html.split("状态栏单独预览", 1)[1].split("悬浮组件预览", 1)[0]
        floating = html.split("悬浮组件预览", 1)[1]
        return first, status, floating

    def test_draggable_ball_engine_routed_to_floating_panel(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "正文<ball>",
               "regex_scripts": [{"scriptName": "悬浮球", "findRegex": "/<ball>/",
                                  "replaceString": self.DRAGGABLE_BALL}]}
        _, status, floating = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        self.assertIn("data-float-ball", floating)
        self.assertNotIn("data-float-ball", status)

    def test_slide_drawer_engine_not_misclassified_as_statusbar(self):
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "正文<side>",
               "regex_scripts": [{"scriptName": "侧边栏", "findRegex": "/<side>/",
                                  "replaceString": self.SLIDE_DRAWER}]}
        _, status, floating = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        self.assertIn("data-sidebar", floating)
        self.assertNotIn("data-sidebar", status)

    def test_pointer_events_ball_routed_to_floating_panel(self):
        """Pointer Events 版悬浮球（data-zsf-ball + pointerdown）仍归入悬浮面板，不漏检。"""
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "正文<ball>",
               "regex_scripts": [{"scriptName": "悬浮球", "findRegex": "/<ball>/",
                                  "replaceString": self.POINTER_BALL}]}
        _, status, floating = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        self.assertIn("data-zsf-ball", floating)
        self.assertNotIn("data-zsf-ball", status)

    def test_pointer_events_ball_detected_by_generic_fallback(self):
        """无标记的 Pointer Events 悬浮球靠 position:fixed + pointerdown 通用回退识别。"""
        self.assertTrue(bp._is_floating_engine_tag(self.POINTER_BALL_GENERIC))
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "正文<ball>",
               "regex_scripts": [{"scriptName": "悬浮球", "findRegex": "/<ball>/",
                                  "replaceString": self.POINTER_BALL_GENERIC}]}
        _, status, floating = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        self.assertIn("pointerdown", floating)
        self.assertNotIn("pointerdown", status)

    def test_all_four_components_each_panel_gets_its_engine(self):
        """全局美化(style) + 侧边栏 + 悬浮球 + 状态栏雷达 同场：各引擎不串台。"""
        obj = {
            "pageDepth": 2,
            "statusbar": "<css>",
            "beginning": "正文<side><ball><ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "全局美化", "findRegex": "/<css>/", "replaceString": "<style>body{color:red}</style>"},
                {"scriptName": "侧边栏", "findRegex": "/<side>/", "replaceString": self.SLIDE_DRAWER},
                {"scriptName": "悬浮球", "findRegex": "/<ball>/", "replaceString": self.DRAGGABLE_BALL},
                {"scriptName": "信标", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]\\s*/g", "replaceString": "<span style=\"display:none\">[$1=$2]</span>"},
                {"scriptName": "状态栏", "findRegex": "/<ztl>/", "replaceString": self.RADAR},
            ],
        }
        _, status, floating = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        # 悬浮面板拿到两个悬浮引擎，且没有状态栏雷达引擎
        self.assertIn("data-sidebar", floating)
        self.assertIn("data-float-ball", floating)
        self.assertNotIn("data-radar-engine", floating)
        # 状态栏面板拿到雷达引擎，且没有悬浮引擎
        self.assertIn("data-radar-engine", status)
        self.assertNotIn("data-float-ball", status)
        self.assertNotIn("data-sidebar", status)

    def test_offsets_stay_valid_when_multiple_engines_extracted(self):
        """多引擎同场抽取后剩余文本不残留半截 <img> 标签（防 start/end 偏移失效）。"""
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "A<side>B<ball>C<ztl>\n[hp=85]",
               "regex_scripts": [
                   {"scriptName": "侧边栏", "findRegex": "/<side>/", "replaceString": self.SLIDE_DRAWER},
                   {"scriptName": "悬浮球", "findRegex": "/<ball>/", "replaceString": self.DRAGGABLE_BALL},
                   {"scriptName": "状态栏", "findRegex": "/<ztl>/", "replaceString": self.RADAR},
               ]}
        first, _, _ = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        # 整合面板保留正文骨架，不残留被抽走引擎的 data-* 属性
        self.assertNotIn("data-float-ball", first)
        self.assertNotIn("data-sidebar", first)


class TestShadowCastPanelClassification(unittest.TestCase):
    """attachShadow 型自绘组件（标题栏/NPC 状态栏/主角 HUD）应进独立 ShadowCast 面板，
    不再漏进「第一句话剩余预览」。判据按引擎结构通用，不写死某张卡的命名前缀。"""

    # 标题栏引擎：命名空间化生命周期属性 data-yzt-core-deploy + attachShadow。
    SC_TITLEBAR = (
        '<img src="yzt-core-deploy-v1" data-yzt-core-deploy="1" style="display:none" '
        'onerror="(function(img){var h=img.previousElementSibling;'
        'h.attachShadow({mode:\'open\'});img.remove()})(this)">')
    # NPC 状态栏引擎：data-yzr-core-deploy + attachShadow。
    SC_NPC = (
        '<img src="yzr-core-deploy-v2" data-yzr-core-deploy="1" style="display:none" '
        'onerror="(function(e){var host=document.createElement(\'div\');'
        'host.attachShadow({mode:\'open\'});e.remove()})(this)">')
    # 主角 HUD 引擎：data-yzh-bootstrap + attachShadow（桌面态会横向挤开页面）。
    SC_HUD = (
        '<img src="yzh-render-trigger-v1" data-yzh-bootstrap="renderer" style="display:none" '
        'onerror="(function(win,doc){var r=win.__YZHUDV1=win.__YZHUDV1||{};'
        'r.host&&r.host.attachShadow({mode:\'open\'})})(window,document)">')
    # 影渲法 g3 家族（skill 自带示例）：g3-host 宿主类 + attachShadow。
    SC_G3 = (
        '<img src=x style="display:none" data-g3v="1" '
        'onerror="(function(img){var b=img.closest(\'.g3-host\');'
        'b.attachShadow({mode:\'open\'});img.remove()})(this)">')

    def _panel_of(self, html, title):
        after = html.split(title, 1)[1]
        # 到下一个 frag-label 或 pano-audit 之前
        return re.split(r'frag-label|pano-audit|issue-report', after, 1)[0]

    def test_shadowcast_titlebar_npc_hud_go_to_shadowcast_panel(self):
        obj = {"pageDepth": 2, "statusbar": "",
               "beginning": "正文<t><n><h>",
               "regex_scripts": [
                   {"scriptName": "标题栏", "findRegex": "/<t>/", "replaceString": self.SC_TITLEBAR},
                   {"scriptName": "NPC状态栏", "findRegex": "/<n>/", "replaceString": self.SC_NPC},
                   {"scriptName": "主角HUD", "findRegex": "/<h>/", "replaceString": self.SC_HUD},
               ]}
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertIn("ShadowCast 组件预览", html)
        sc = self._panel_of(html, "ShadowCast 组件预览")
        for marker in ("data-yzt-core-deploy", "data-yzr-core-deploy", "data-yzh-bootstrap"):
            with self.subTest(marker=marker):
                self.assertIn(marker, sc)
        # 关键回归：三个组件不得残留在「第一句话剩余预览」
        first = html.split("状态栏单独预览", 1)[0]
        for marker in ("data-yzt-core-deploy", "data-yzr-core-deploy", "data-yzh-bootstrap"):
            with self.subTest(leak=marker):
                self.assertNotIn(marker, first)

    def test_shadowcast_detector_unit(self):
        for tag in (self.SC_TITLEBAR, self.SC_NPC, self.SC_HUD, self.SC_G3):
            with self.subTest(tag=tag[:40]):
                self.assertTrue(bp._is_shadowcast_engine_tag(tag))

    def test_shadowcast_detector_excludes_scaffold_and_others(self):
        # 预览自身发送脚手架绝不被当作被测组件
        scaffold = ('<img src="x" data-pano-scaffold="1" style="display:none" '
                    'onerror="(function(){document.querySelector(\'.pano-send\')})()">')
        self.assertFalse(bp._is_shadowcast_engine_tag(scaffold))
        # 悬浮球 / 雷达状态栏保持各自归属，不被 shadowcast 抢
        self.assertFalse(bp._is_shadowcast_engine_tag(TestRuntimeFloatingEngines.DRAGGABLE_BALL))
        self.assertFalse(bp._is_shadowcast_engine_tag(TestRuntimeFloatingEngines.RADAR))

    def test_shadowcast_panel_absent_when_no_such_component(self):
        """普通卡（无 attachShadow 组件）不凭空多一格空 ShadowCast 面板。"""
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "只有正文",
               "regex_scripts": [{"scriptName": "空", "findRegex": "/x/", "replaceString": "y"}]}
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertNotIn("ShadowCast 组件预览", html)


class TestPanorama(unittest.TestCase):
    """全景预览：所有组件组合进单文档，固定输入栏+发送按钮+占位AI气泡。"""

    FOUR = {
        "pageDepth": 2,
        "statusbar": "<css>",
        "beginning": "正文<side><ball><ztl>\n[hp=85]",
        "regex_scripts": [
            {"id": -1, "scriptName": "全局美化", "findRegex": "/<css>/", "replaceString": "<style>body{color:red}</style>"},
            {"id": -1, "scriptName": "侧边栏", "findRegex": "/<side>/",
             "replaceString": "<img src=\"x\" data-sidebar=\"1\" style=\"display:none\" onerror=\"(function(e){var d=document.createElement('div');d.id='z-drawer';d.style.cssText='position:fixed;right:0;transform:translateX(100%)';document.body.appendChild(d);e.remove();})(this)\">"},
            {"scriptName": "悬浮球", "findRegex": "/<ball>/",
             "replaceString": "<img src=\"x\" data-float-ball=\"1\" style=\"display:none\" onerror=\"(function(e){var b=document.createElement('button');b.id='z-fab';b.style.cssText='position:fixed;left:18px;bottom:90px';b.addEventListener('mousedown',function(ev){});document.body.appendChild(b);e.remove();})(this)\">"},
            {"scriptName": "信标", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]\\s*/g", "replaceString": "<span style=\"display:none\">[$1=$2]</span>"},
            {"scriptName": "状态栏", "findRegex": "/<ztl>/",
             "replaceString": "<img src=\"x\" data-radar-engine=\"1\" onerror=\"this.insertAdjacentHTML('afterend','&lt;div class=z-status-box&gt;状态栏&lt;/div&gt;')\">"},
        ],
    }

    @staticmethod
    def _panorama_unescaped(four, platform="mmd"):
        """🚨 全景把聊天壳塞进 `iframe srcdoc`，整块过 `html.escape` —— 页面源码里
        引号是 `&quot;`/`&#x27;`。所以断言带引号的 JS/HTML 片段前必须先 unescape，
        否则永远找不到（本文件曾有 4 条断言因此长期红，不是实现回归）。"""
        return html_mod.unescape(bp.assemble_panorama(four, platform, "t.json"))

    def test_mmd_input_collapse_is_blur_driven_not_outside_click(self):
        """2026-08-29 实机：收回由主 textarea 失焦驱动，页面没装 outside-click 监听器。
        对 .chat-body 派合成 click 收不回（真机四个目标全试过）。预览必须照此复刻，
        否则作者在预览里"点空白能收回"、上真机就静默失效。"""
        mmd = self._panorama_unescaped(self.FOUR)
        self.assertIn("addEventListener('blur'", mmd)
        # 不得把收回绑在 .chat-body 的 click 上
        self.assertNotIn("body.addEventListener('click',function(){setState(false);})", mmd)

    def test_mmd_input_multiline_is_height_based_not_newline_based(self):
        """is-multiline 是渲染高度判据（实测 120 字零换行同样会加），不是"含换行"判据。
        另钉两个量法坑：必须量当前可见节点（折叠态 [0] 是 display:none、scrollHeight 恒 0）；
        量前须把 height 压 0 再还原（textarea 的 scrollHeight 只涨不缩）。"""
        mmd = self._panorama_unescaped(self.FOUR)
        self.assertIn("var isML=function", mmd)
        self.assertIn("scrollHeight", mmd)
        self.assertIn("offsetParent!==null", mmd)      # 挑可见节点量
        self.assertIn("m.style.height='0px'", mmd)     # 压 0 才能缩回
        self.assertIn("m.style.height=prev", mmd)      # 同 tick 还原

    def test_mmd_input_syncs_same_tick_on_input_event_plus_poll_fallback(self):
        """派 input → 同 tick 同步（实测）；裸赋值 → 约 100ms 被轮询采纳。
        轮询兜底要留着，它复现的是真机那个竞态窗口（窗口内两次写会互相盖）。"""
        mmd = self._panorama_unescaped(self.FOUR)
        self.assertIn("el.addEventListener('input',function(){syncFrom(el);})", mmd)
        self.assertIn("setInterval(", mmd)
        # 不得再用 setTimeout 给 input 事件人为加延迟（旧复刻是错的）
        self.assertNotIn("setTimeout(function(){syncFrom(el);},120)", mmd)

    def test_mmd_send_buttons_carry_btn_icon_for_visibility_filter(self):
        """真机发送钮是 uni-image.btn-icon，作者用
        `.btn-icon:not(.chat-send-proxy)` + offsetParent 筛可见钮（任一状态恰好 1 个）。
        预览按钮必须带 btn-icon 才能测通；同时要有还原尺寸的规则，
        否则 `.chat-input-scope .btn-icon`(1.25rem) 特异性更高会把按钮压小。"""
        mmd = self._panorama_unescaped(self.FOUR)
        self.assertIn('class="pano-send send-btn btn-icon"', mmd)
        self.assertIn('class="pano-send-expanded send-btn btn-icon"', mmd)
        self.assertIn(".pano-send.btn-icon", mmd)
        self.assertIn(".pano-send-expanded.btn-icon", mmd)
        # proxy 恒隐藏，不能被可见性筛法选中
        self.assertIn("btn-icon chat-send-proxy", mmd)
        # 实测两态发送钮都是 1.25rem(20px)。旧版写 1.625rem 并注明"防止被压小"，
        # 但它要防的那条规则当时根本不存在 —— 对着不存在的规则做补偿。
        self.assertIn("width:1.25rem;height:1.25rem", mmd)

    def test_mmd_more_panel_sits_after_send_msg_pushing_input_up(self):
        """🚨 实测 `.more-scope` 在 `.chat-bottom-wapper` 里排在 `.send-msg` **之后** ——
        面板在输入框**下方**、把输入框整条往上顶（底栏 105px→422px）。
        旧版预览排在前面，面板会展开在输入框**上方**，与真机相反。"""
        mmd = self._panorama_unescaped(self.FOUR)
        send_at = mmd.find('<uni-view class="send-msg">')
        more_at = mmd.find('<uni-view class="more-scope"')
        self.assertGreater(send_at, 0)
        self.assertGreater(more_at, send_at)
        # 两者同为 .chat-bottom-wapper 的子节点（面板不是 fixed 弹窗）
        wapper_at = mmd.find('<uni-view class="chat-bottom-wapper">')
        self.assertGreater(send_at, wapper_at)

    def test_mmd_plus_button_stays_outside_input_in_both_states(self):
        """`+` 是 `.chat-input-scope` 的**兄弟**（`.more-options-scope`），
        两态都留在输入框右侧外部 —— 不会移到输入框下方。
        位置靠 padding-bottom 垫片压到视觉中线：折叠 0.96875rem(15.5px)、
        展开/多行 0.84375rem(13.5px)。旧版预览这个类**一条 CSS 都没有**，
        `+` 全靠默认流排版，所以两态都不在真机位置上。"""
        css = bp._mmd_panorama_css()
        self.assertIn(".chat .chat-bottom .uni-textarea .more-options-scope{", css)
        self.assertIn("margin-left:0.375rem", css)
        # 图标尺寸：外面的「+」1.5625rem，比输入框内的发送钮(1.25rem)大一档
        self.assertIn(".more-options-scope .btn-icon{width:1.5625rem;height:1.5625rem}", css)
        self.assertIn("padding-bottom:0.96875rem", css)
        self.assertIn("padding-bottom:0.84375rem", css)
        # 输入框内图标那条规则必须真的存在（旧注释引用了它却没写）
        self.assertIn(".chat-input-scope .btn-icon{width:1.25rem;height:1.25rem}", css)
        # `+` 在 DOM 上是 .chat-input-scope 的兄弟，不能嵌在里面
        mmd = self._panorama_unescaped(self.FOUR)
        scope_at = mmd.find('<uni-view class="chat-input-scope has-toolbar">')
        plus_at = mmd.find('<uni-view class="more-options-scope"')
        self.assertGreater(plus_at, scope_at)
        self.assertNotIn('class="chat-input-scope has-toolbar"><uni-view class="more-options-scope"', mmd)

    def test_mmd_plus_toggles_glyph_and_data_more_like_real_icon_swap(self):
        """真机 `+` 随开合换图（ico_more_dark ⇄ ico_more_called_dark，都是"灰圈里的±号"）。
        预览用 CSS 画灰圈、JS 只换圈内字形 +(43) ⇄ −(8722)，并同步 `data-more`。
        🚨 字形用**裸** 43/8722，不用带圈的 8854(⊖)：圈已交给 CSS 画，带圈字形会叠成双圈。
        🚨 判开合请用 `data-more`：真机关态 `.more-scope` 是 **v-if 节点不存在**，
        预览是 display:none —— 拿 `querySelector('.more-scope')` 判会得到相反结论。"""
        mmd = self._panorama_unescaped(self.FOUR)
        self.assertIn('class="more-options-scope" data-more="off"', mmd)
        self.assertIn("mo.setAttribute('data-more',on?'on':'off')", mmd)
        self.assertIn("String.fromCharCode(8722)", mmd)  # − 展开态（裸减号，CSS 另画圈）
        self.assertIn("String.fromCharCode(43)", mmd)    # + 折叠态（裸加号，CSS 另画圈）
        # 初始 HTML 用裸 + (&#43;)，不是全角＋(&#65291;)
        self.assertIn('<uni-view class="btn-icon">&#43;</uni-view>', mmd)

    def test_mmd_plus_button_drawn_as_gray_ring_not_bare_glyph(self):
        """🚨 真机 `+` 是"灰色描边圆圈里一个加号"（PNG 图标），不是裸字形。
        预览用 CSS 给 `.more-options-scope .btn-icon` 画 border 圆环 + 居中字形，
        两态都带圈。旧版退化成飘在边上的裸全角＋（无圈），与真机差最远。"""
        css = bp._mmd_panorama_css()
        # 圆环：border + border-radius:50% + 居中
        self.assertIn("border:0.09375rem solid #6b7079;border-radius:50%", css)
        # 灰色字形 + flex 居中
        self.assertIn("color:#9198a1;display:flex;align-items:center;justify-content:center", css)

    def test_mmd_send_button_is_transparent_gray_plane_not_pink_circle(self):
        """🚨 真机发送钮是 `ico_send_dark.png`（灰色纸飞机）、**背景透明、不变粉**
        （2026-08-29 实机注入文字前后复验 bg 恒 rgba(0,0,0,0)）。旧版画成粉色实心圆+白箭头是错的。
        预览覆盖成透明底 + 灰色纸飞机 SVG（currentColor 驱动）。"""
        css = bp._mmd_panorama_css()
        # .chat-input-scope 内的发送钮覆盖成透明底 + 灰色（不波及沙盒矩形发送键）
        self.assertIn("width:1.25rem;height:1.25rem;background:transparent;border-radius:0;\n"
                      "  color:#9198a1", css)
        # 纸飞机 SVG（Feather send）出现在两态发送钮
        mmd = self._panorama_unescaped(self.FOUR)
        self.assertIn('<polygon points="22 2 15 22 11 13 2 9 22 2">', mmd)
        # 纸飞机 polygon 是发送钮独有（分享钮用 circle），恰好 2 个：折叠态 + 展开态。
        # 不数通用 viewBox —— 分享钮 SVG 也用同一 viewBox，会误计。
        self.assertEqual(mmd.count('<polygon points="22 2 15 22 11 13 2 9 22 2">'), 2)

    def test_mmd_message_action_buttons_ai_three_user_two(self):
        """🚨 实测 2026-08-29：AI 消息 3 圆钮（刷新/编辑/分享），用户消息 2 圆钮（编辑/分享，无刷新）。
        分享钮真机是分享图标（旧预览第三钮误画成实心圆 ●）。用户圆钮靠气泡右下。"""
        mmd = self._panorama_unescaped(self.FOUR)
        # AI 消息三钮 title
        self.assertIn('title="刷新（重新生成）"', mmd)
        self.assertIn('title="编辑"', mmd)
        self.assertIn('title="分享"', mmd)
        # 分享钮用三圆点连线 SVG（不是实心圆 ●）；AI+用户各一 = 2 个
        self.assertEqual(mmd.count('<circle cx="18" cy="5" r="3">'), 2)
        self.assertNotIn('<uni-view class="modify-btn">&#9679;</uni-view>', mmd)  # 旧实心圆已删
        # 用户消息（.self）有 modify-btn-scope（编辑+分享）
        self.assertIn('class="item Ai self"', mmd)
        css = bp._mmd_panorama_css()
        # 用户圆钮靠右
        self.assertIn(".item.self .modify-btn-scope{left:auto;right:0;justify-content:flex-end}", css)

    def test_mmd_longpress_menu_four_options_with_beautify_vars(self):
        """🚨 实测 2026-08-29：长按菜单 4 项（复制/删除/回溯/开启新的故事）。
        first_mes 仅复制（其余 data-only-full 项 runtime 隐藏）。菜单吃美化变量：
        内容框/选项框 --modify-input-bg-color、选项字 --primary-font-color、分隔线 --msg-option-separator-color。"""
        mmd = self._panorama_unescaped(self.FOUR)
        for label in ("复制", "删除", "回溯", "开启新的故事"):
            self.assertIn("<span>%s</span>" % label, mmd)
        # 三个 data-only-full 选项项（删除/回溯/开启新的故事）+ 3 分隔线 = first_mes 时隐藏
        self.assertEqual(mmd.count('data-only-full="1"'), 6)
        self.assertIn('data-opt="copy"', mmd)
        self.assertIn('data-open="off"', mmd)  # 菜单默认关
        css = bp._mmd_panorama_css()
        self.assertIn(".msg-option-scope[data-open=\"on\"]{display:block}", css)
        self.assertIn("background:var(--modify-input-bg-color,#1E1F24)", css)
        self.assertIn("border-top:.03125rem solid var(--msg-option-separator-color,#333333)", css)

    def test_mmd_prologue_click_fills_input_and_state_flow(self):
        """🚨 实测 2026-08-29：点开场白 .prologue-content → 正文进输入框；
        发送一条 → 开场白消失；回溯 → 开场白重现。runtime 暴露 hide/showPrologue + openMenu。"""
        mmd = self._panorama_unescaped(self.FOUR)
        # 开场白点击填入输入框的逻辑
        self.assertIn("pc.onclick=function", mmd)
        self.assertIn("el.value=(pc.textContent", mmd)
        # 状态流转函数 + 暴露
        self.assertIn("var hidePrologue=function()", mmd)
        self.assertIn("var showPrologue=function()", mmd)
        self.assertIn("hidePrologue:hidePrologue,showPrologue:showPrologue", mmd)
        # 长按绑定 + 按消息类型分 kind（first/self/ai）
        self.assertIn("var bindLong=function", mmd)
        self.assertIn("?'first':", mmd)
        # 发送钮点击隐藏开场白
        self.assertIn("sends[si].addEventListener('click',hidePrologue)", mmd)
        # 开场白内容吃美化变量（回归保护）
        css = bp._mmd_panorama_css()
        self.assertIn(".prologue-scope .prologue-content{", css)
        self.assertIn("color:var(--chat-content-font-color,#FFFFFF)", css)

    def test_mmd_message_two_state_layout_order(self):
        """🚨 实测 2026-08-29：消息顺序 描述→first_mes→[初始:开场白 | 发送后:用户+AI]。
        DOM 序恒为 描述→first_mes→开场白(initial)→用户(sent)→AI(sent)，靠 .chat[data-chat-state]
        切两态互斥；默认 sent（被测内容在 AI 回复气泡，作者一开即见）。"""
        mmd = self._panorama_unescaped(self.FOUR)
        # first_mes 气泡（无三圆钮，data-msg=first），在描述气泡之后、开场白之前
        self.assertIn('class="item Ai" data-msg="first"', mmd)
        desc_at = mmd.find("avatar-body")
        first_at = mmd.find('data-msg="first"')
        prologue_at = mmd.find('class="prologue-scope"')
        user_at = mmd.find('class="item Ai self"')
        ai_at = mmd.find('id="item0"')
        # 顺序：描述 < first_mes < 开场白 < 用户 < AI回复
        self.assertLess(desc_at, first_at)
        self.assertLess(first_at, prologue_at)
        self.assertLess(prologue_at, user_at)
        self.assertLess(user_at, ai_at)
        # 开场白标 initial 态、用户+AI 标 sent 态
        self.assertIn('class="prologue-scope" data-msg-state="initial"', mmd)
        # 数元素形态（不数 CSS 选择器 [data-msg-state="sent"]，那是内联样式里的）：用户 + AI回复 = 2
        self.assertEqual(mmd.count('<uni-view data-msg-state="sent">'), 2)
        # 两态互斥 CSS + 默认 sent
        css = bp._mmd_panorama_css()
        self.assertIn('.chat[data-chat-state="sent"] [data-msg-state="initial"]{display:none}', css)
        self.assertIn('.chat[data-chat-state="initial"] [data-msg-state="sent"]{display:none}', css)
        self.assertIn('data-chat-state="sent"', mmd)
        # setChatState 暴露 + 两态切换绑在发送/回溯
        self.assertIn("setChatState:setChatState", mmd)
        self.assertIn("var setChatState=function(s)", mmd)

    def test_mmd_shortcut_newchat_is_dialog_not_instruction_bar(self):
        """🚨 实测 2026-08-29：快捷栏「新的聊天」是独立动作 onShortcutNewChat（确认弹窗），
        **不是指令栏**。只有「选择指令」走指令栏(else→toggleInstr)。旧预览误让新的聊天走指令栏。"""
        mmd = self._panorama_unescaped(self.FOUR)
        # 映射里「新的聊天」(\u65b0\u7684\u804a\u5929) → newchat
        self.assertIn("\\u65b0\\u7684\\u804a\\u5929':'newchat'", mmd)
        # newchat 确认弹窗存在
        self.assertIn('data-sheet="newchat"', mmd)
        self.assertIn("开启新的聊天", mmd)

    def test_mmd_textarea_padding_lives_on_shell_not_inner(self):
        """🚨 真机上下 padding 一律挂在 `uni-textarea` **壳**上，内层 `textarea` 恒零上下
        padding（实测折叠壳 24px/内层 22px；展开壳与内层同 22px）。
        预览曾把两层压平写在内层，每一态都多 16px：折叠输入框 53→55px、展开主输入 22→43px。
        另钉 `vertical-align:top` 消 inline 基线间隙 —— 不能改用 `display:block` 修，
        那会让 rows=1 的高度约束失效（折叠预览 22→67px，本地实测踩过）。"""
        css = bp._mmd_panorama_css()
        self.assertIn("padding-top:0;padding-bottom:0;vertical-align:top", css)
        self.assertNotIn("padding-top:0;padding-bottom:0;display:block", css)
        # 壳承 padding
        self.assertIn("padding:0.75rem 0.25rem 0.75rem 0.1875rem", css)
        # 内层那条共用规则不得再带上下 padding
        inner = [ln for ln in css.splitlines() if "resize:none" in ln]
        self.assertTrue(inner, "共用 textarea 规则应存在")
        self.assertNotIn("padding:0.5rem 0.25rem", "\n".join(inner))

    def test_mmd_expanded_hides_collapsed_row(self):
        """折叠行与展开行互斥。漏掉这条隐藏规则 → 两行叠加、
        展开态输入框 125→172px（本地改 CSS 时确实漏抄过一次）。"""
        css = bp._mmd_panorama_css()
        self.assertIn(
            ".chat-input-scope.is-expanded .chat-input-collapsed-row{display:none}", css)

    def test_mmd_collapsed_row_side_cells_follow_multiline_branch(self):
        """折叠行左右两格（算力数字 / 发送钮）：单行态 `align-self:stretch` 撑满行高居中；
        `.is-multiline` 时改 `align-self:auto` + `padding-bottom:0.5rem` 沉到底（实测）。
        展开行两格则是 `padding-top:0.875rem`。"""
        css = bp._mmd_panorama_css()
        self.assertIn("align-self:stretch;display:flex;align-items:center;min-height:1.25rem", css)
        self.assertIn("align-self:auto;padding-bottom:0.5rem", css)
        self.assertIn("padding-top:0.875rem;min-height:1.25rem", css)

    def test_panorama_has_fixed_input_bar_and_send_button(self):
        """MMD 走实测复刻底栏（.chat-bottom 自己就是 fixed bottom:0）；
        ST 仍是中性骨架的 .pano-input-bar。两边都必须有可发送的输入框。"""
        mmd = bp.assemble_panorama(self.FOUR, "mmd", "t.json")
        self.assertIn("chat-bottom", mmd)
        self.assertIn("position:fixed", mmd)
        self.assertIn("bottom:0", mmd)
        self.assertIn("pano-send", mmd)
        self.assertIn("uni-textarea-textarea", mmd)  # 主输入框（与选项回填选择器一致）
        # MMD 已改走实测外壳，不该再出现中性骨架的占位输入栏类名。
        self.assertNotIn("pano-input-bar", mmd)
        st = bp.assemble_panorama(self.FOUR, "st", "t.json")
        self.assertIn("pano-input-bar", st)
        self.assertIn("pano-send", st)

    def test_panorama_has_mmd_chat_runtime_scaffold(self):
        html = bp.assemble_panorama(self.FOUR, "mmd", "t.json")
        for marker in ("topTabbar", "scroll-view dark pano-chat", "chat-body",
                       "item Ai self", "item Ai avatar-body",
                       "content right", "content left"):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)
        self.assertIn("#/pages/chat/chat", html)
        self.assertIn("data-pano-runtime-scaffold", html)

    # ── 以下 4 条把「MMD 全景 = 实测真实页」这件事钉死 ──────────────────
    # 依据：Playwright 进真实 iframe#chatIframe 读 CSSOM + getComputedStyle
    #      （www.sexyai.ai #/pages/chat/chat，旧聊天页，2026-08-28）。
    # 契约全文：preview/MMD真实页DOM契约-2026-08-28.md
    # 这几条防的是"顺手改回好看的臆想值"——沙盒分支早有同类锁
    # （test_dark_tokens_equal_measured_truth），MMD 分支以前没有，于是骨架
    # 一路飘到与真机零重合。别为了预览好看放宽它们。

    def test_mmd_panorama_reproduces_measured_dom_layers(self):
        """真机所有 chat-body 后代规则都以 .chat-scope-box .scroll-view 为前缀。
        少这两层，作者按文档写的深选择器在预览里会失配（真机却能中）。"""
        html = html_mod.unescape(bp.assemble_panorama(self.FOUR, "mmd", "t.json"))
        for frag in (
            # 真机外层壳：div#app > uni-app > uni-page > uni-page-wrapper > uni-page-body
            # （实测契约 §1）。少这层，桌面型 HUD 的 pageTarget() 找不到全高祖先 → 退回 .chat
            # → transform 落在 45px 盒上、fixed 后代塌缩（桌面 HUD 偏差根因）。
            '<div id="app"><uni-app><uni-page><uni-page-wrapper><uni-page-body>',
            # .chat 根节点带 data-chat-state（两态互斥开关，默认 sent）
            '<uni-view class="chat" data-chat-state="sent">',
            '<uni-view class="chat-scope-box">',
            '<uni-scroll-view class="scroll-view dark pano-chat" id="pano-chat">',
            '<div class="uni-scroll-view"><div class="uni-scroll-view-content">',
            '<uni-view class="chat-body" id="msglistview">',
            '<uni-view class="touch-scope" id="item0">',
            '<uni-view class="content left" id="q-1">',
            # 官方侧边挂载点（悬浮组件靶位）与开场白块（开场白带 data-msg-state=initial）
            '<uni-view class="mm-left-side-container">',
            '<uni-view class="mm-right-side-container">',
            '<uni-view class="prologue-scope" data-msg-state="initial">',
            # 外层壳正确闭合（顺序与开壳镜像）
            '</uni-page-body></uni-page-wrapper></uni-page></uni-app></div>',
        ):
            with self.subTest(frag=frag):
                self.assertIn(frag, html)
        # 三个已证实不存在于真机的臆想类名，不得回归。
        for dead in ('class="page"', "chat-bg", "data-message-role"):
            with self.subTest(dead=dead):
                self.assertNotIn(dead, html)

    def test_mmd_panorama_full_height_ancestors_prevent_desktop_hud_collapse(self):
        """桌面型 HUD（如柚子岛）的 pageTarget() 按 #app→uni-app→uni-page-body→.page 找
        全高祖先来横向缩窄腾出侧栏位；找不到就退回 .chat。.chat 只有顶栏在流内（≈45px），
        一旦 HUD 对它 transform，其 fixed 后代（.chat-scope-box/.chat-bottom）改以该 45px
        盒为包含块 → 桌面预览整体塌缩。修复=补齐全高祖先链，让 pageTarget() 命中全高盒。

        本测试钉死两件事：① DOM 里有这条祖先链且各层可被 pageTarget() 选中；
        ② CSS 给这几层全高（height:100%），否则补了 DOM 也仍是 0 高盒、面积为 0 被跳过。"""
        html = html_mod.unescape(bp.assemble_panorama(self.FOUR, "mmd", "t.json"))
        # ① pageTarget() 的三个主要靶子都在（#app 命中最优先分支）
        self.assertIn('id="app"', html)
        self.assertIn('<uni-app>', html)
        self.assertIn('<uni-page-body>', html)
        # .chat 位于该祖先内部（uni-page-body 之后才是 .chat）
        body_at = html.index('<uni-page-body>')
        chat_at = html.index('<uni-view class="chat"')
        self.assertLess(body_at, chat_at)
        # ② CSS 全高链：这几层必须 display:block + height:100%，否则量到面积 0 会被跳过
        css = bp._mmd_panorama_css()
        self.assertIn(
            "#app,uni-app,uni-page,uni-page-wrapper,uni-page-body{display:block;width:100%;height:100%}",
            css)

    def test_mmd_bubble_css_keeps_pre_line_and_measured_opacity(self):
        """🚨 `white-space:pre-line` 是「换行空白条」的**真因**（实测：注入带换行的
        HTML，高度 102px vs 子元素合计 51px；p:empty 数量为 0）。少了它，预览就查
        不出 MMD 头号排版坑。opacity:.9 同理影响实际观感色。"""
        css = bp._mmd_panorama_css()
        self.assertIn("white-space:pre-line", css)
        self.assertIn("opacity:.9", css)
        # 气泡背景由 --background-color 覆盖 .left/.right 的白底/蓝底（深色下两侧同色）
        self.assertIn("background:var(--background-color,#17181A)", css)
        self.assertIn("border-radius:1rem 1rem 1rem 0!important", css)   # AI 尖角
        self.assertIn("border-radius:1rem 1rem 0!important", css)        # 用户尖角
        self.assertIn("border-radius:0.5rem!important", css)             # 首条对称圆角
        self.assertIn("max-width:94%", css)                              # .touch-scope
        # 旧版那套臆想配色不得回归
        for fake in ("#f0f0f3", "#3a76f0"):
            with self.subTest(fake=fake):
                self.assertNotIn(fake, css)

    def test_mmd_panorama_reproduces_measured_rem_scaling_law(self):
        """实测两点拟合（误差 <0.001px）：rootFontSize = 16*min(w,375)/375。
        主聊天页 iframe 宽 1280 → 16px 封顶；编辑页预览 iframe 宽 283 → 12.0747px。
        真机尺寸全走 rem，少这条则所有 rem 尺寸失真。"""
        self.assertEqual(bp.MMD_ROOT_FONT_SIZE, "min(16px, calc(100vw * 16 / 375))")
        self.assertIn("html{font-size:min(16px, calc(100vw * 16 / 375))}",
                      bp._mmd_panorama_css())

    def test_mmd_panels_also_carry_measured_platform_shell(self):
        """三面板（单组件诊断）也要有平台底子：checklist 的工作流是"先三面板审单组件、
        再全景审组合"，第一步没有 pre-line / 主题变量 / rem 基准 = 白审。
        壳是**扁平**的（静态流、无顶栏底栏弹窗），布局与全景不同但取值一律照抄实测。"""
        html = html_mod.unescape(bp.assemble_preview(self.FOUR, "mmd", "t.json"))
        # 气泡容器链与类名照真机
        for frag in ('<uni-view class="chat"><uni-view class="chat-scope-box">',
                     '<uni-view class="chat-body" id="msglistview">',
                     '<uni-view class="content left">'):
            with self.subTest(frag=frag):
                self.assertIn(frag, html)
        shell = bp._mmd_panel_shell_css()
        # 三样最要紧的实测取值
        self.assertIn("white-space:pre-line", shell)
        self.assertIn("html{font-size:min(16px, calc(100vw * 16 / 375))}", shell)
        self.assertIn("--background-color:#17181A;", shell)
        # 气泡盒模型与全景一致（同一批实测值）
        self.assertIn("padding:0.75rem", shell)
        self.assertIn("border-radius:0.5rem", shell)
        self.assertIn("max-width:94%", shell)
        # 扁平：不得带 fixed 定位/视口高度，否则自动撑高的诊断 iframe 会塌。
        # 只查声明，不查注释文本（注释里会提到 fixed 解释为什么不用它）。
        decls = re.sub(r"/\*.*?\*/", "", shell, flags=re.S)
        self.assertIn(".chat .chat-scope-box{position:static", decls)
        self.assertNotIn("position:fixed", decls)
        self.assertNotIn("100vh", decls)
        # 顶栏/底栏/弹窗属于组合审核，不该混进单组件诊断
        for noise in ("topTabbar", "chat-bottom", "u-popup", "shortcut-btn"):
            with self.subTest(noise=noise):
                self.assertNotIn(noise, decls)
        # ST 分支不受影响（无 ST 实测依据，保持原样）
        st = html_mod.unescape(bp.assemble_preview(self.FOUR, "st", "t.json"))
        self.assertNotIn('<uni-view class="chat-scope-box">', st)

    def test_mmd_panorama_simulates_measured_popups(self):
        """全局美化会打到弹窗面板，全景必须能逐个打开自查（2026-08-28 实机逐个点开抓取）。
        六个面板 + 两个「不是弹窗」的原地展开状态（更多面板 / 指令栏）。"""
        html = html_mod.unescape(bp.assemble_panorama(self.FOUR, "mmd", "t.json"))
        for scope in ("model-setting-scope theme-dark", "conv-style-modal",
                      "summary-sheet theme-dark", "role-profile-modal",
                      "share-popup", "alert-scope"):
            with self.subTest(scope=scope):
                self.assertIn(scope, html)
        # 「新的聊天」确认弹窗（快捷栏 onShortcutNewChat，独立动作非指令栏）
        self.assertIn('data-sheet="newchat"', html)
        # 通用外壳三层齐全
        for frag in ('class="u-popup pano-sheet"', 'class="u-popup__content"',
                     "u-safe-bottom u-safe-area-inset-bottom",
                     "u-popup__content__close--top-right"):
            with self.subTest(frag=frag):
                self.assertIn(frag, html)
        # 默认全关（真机也是关的）。只看面板节点自身：脚手架源码里也含
        # `[data-sheet][data-open=on]` 选择器字符串，不能拿它当"有面板开着"。
        # 🚨 值用 off/on 而非 0/1：无引号属性选择器 `[data-open=1]` 非法
        #（CSS 标识符不能以数字开头），而属性内又不能写裸双引号（§2 红线）。
        panels = re.findall(r'<uni-view class="u-popup pano-(?:sheet|dialog)"[^>]*>', html)
        # 7 个：model/conv/summary/role/share/alert + newchat（快捷栏「新的聊天」确认框）
        self.assertEqual(len(panels), 7)
        for tag in panels:
            with self.subTest(tag=tag):
                self.assertIn('data-open="off"', tag)
        # 「选择指令」与「+」是原地展开，不是弹窗
        self.assertIn('class="instruction-bar hidden"', html)
        self.assertIn("instruction-chip", html)
        self.assertIn('class="more-scope" data-open="off"', html)
        self.assertIn("more-options-scope", html)
        self.assertIn("ai-assistant", html)
        # 开关脚手架与外层工具栏按钮
        self.assertIn("data-pano-panel-scaffold", html)
        self.assertIn("__panoPanels", html)
        for label in ("模型设置", "对话设置", "总结剧情", "用户人设",
                      "分享", "AI帮聊说明", "＋更多面板", "指令栏切换"):
            with self.subTest(label=label):
                self.assertIn(label, html)

    def test_popup_css_keeps_framework_white_baseline_and_zindex_tiers(self):
        """两件必须照抄真机的事：
        ① `.u-popup__content` 基线是**白底**（实测 uview 原文），深色全靠面板 scope 或内联
           style 覆盖 —— 作者漏改某面板时真机露白，预览要能重现，不能"顺手"改成深色。
        ② z-index 两档：多数面板 10075，但总结剧情实测 1000000000（差 5 个数量级）。"""
        css = bp._mmd_panorama_css()
        self.assertIn(".u-popup__content{background-color:#fff", css)
        self.assertIn("z-index:10075", css)
        self.assertIn('.pano-sheet[data-sheet="summary"]{z-index:1000000000}', css)
        # 遮罩实测取值
        self.assertIn(".u-overlay{position:fixed", css)
        self.assertIn("background-color:rgba(0,0,0,.7)", css)
        # 「+」面板在 .chat-bottom 内展开（不是 fixed 弹窗）
        self.assertIn(".chat .chat-bottom .more-scope{", css)

    def test_lo_variable_family_is_left_undefined_on_purpose(self):
        """🚨 `--lo*` 那 18 个变量真机**引用但从未定义**，恒走 `var(--loX, 字面量)` fallback。
        预览故意也不定义 —— 好让作者在预览阶段就发现"改 --lo* 没反应"，而不是上真机才发现。
        所以这些名字只能出现在 var() 的引用位置，不得出现在 `--loX:值` 的定义位置。"""
        css = bp._mmd_panorama_css()
        self.assertIn("var(--loBackground-color,#17181A)", css)
        self.assertIn("var(--loPrimary-color,#FF6D97)", css)
        self.assertIn("var(--loCard-background-color,#1E1F24)", css)
        # 定义位置零出现（`--loX:` 形态）
        self.assertNotRegex(css, r"--lo[A-Za-z-]*\s*:\s*#")
        # 那 29 个真实变量与 --lo* 是两套体系，别混进来
        for name in bp.MMD_THEME_VARS_DARK:
            self.assertFalse(name.startswith("--lo"), name)

    def test_mmd_theme_vars_equal_measured_dark_palette(self):
        """29 个主题变量取值 = 真机 body 内联 style 实测真值，逐字锁定。
        计数依据：解析真机 body[style] 得 29 对（不是 30——初稿曾误记 30，实测纠正）。
        浅色一套真机运行时不暴露，**故意不提供**——需要请回真机抓，别臆造。"""
        self.assertEqual(len(bp.MMD_THEME_VARS_DARK), 29)
        for name, value in (("--background-color", "#17181A"),
                            ("--primary-color", "#FF6D97"),
                            ("--input-background-color", "#33353B"),
                            ("--card-background-color", "#282A2E"),
                            ("--chat-content-font-color", "#FFFFFF")):
            with self.subTest(name=name):
                self.assertEqual(bp.MMD_THEME_VARS_DARK[name], value)
        css = bp._mmd_panorama_css()
        for name, value in bp.MMD_THEME_VARS_DARK.items():
            with self.subTest(name=name):
                self.assertIn("%s:%s;" % (name, value), css)

    def test_panorama_exposes_dynamic_ai_and_route_test_helpers(self):
        html = bp.assemble_panorama(self.FOUR, "mmd", "t.json")
        self.assertIn("__tavernPreview", html)
        self.assertIn("addAI:function", html)
        self.assertIn("“待修复“", html)
        self.assertIn("&quot;keep&quot;", html)
        self.assertIn("leave:function", html)
        self.assertIn("returnToChat:function", html)
        self.assertIn("aria-hidden", html)
        self.assertIn("pane.hidden=!active", html)
        self.assertIn("data-preview-dynamic", html)
        self.assertIn("data-preview-tools", html)
        self.assertIn("追加 AI", html)
        self.assertIn("离开聊天页", html)
        self.assertIn("返回聊天页", html)

    def test_route_helper_relies_on_single_native_hashchange(self):
        self.assertNotIn("dispatchEvent(new Event('hashchange'))", bp.PANORAMA_RUNTIME_SCAFFOLD)
        self.assertIn("if(location.hash!==hash)location.hash=hash", bp.PANORAMA_RUNTIME_SCAFFOLD)
        self.assertIn("syncRoute(hash)", bp.PANORAMA_RUNTIME_SCAFFOLD)

    def test_panorama_send_scaffold_appends_user_and_placeholder_ai_bubbles(self):
        html = bp.assemble_panorama(self.FOUR, "mmd", "t.json")
        self.assertIn("data-pano-scaffold", html)     # 脚手架点火器存在
        # srcdoc 经 html.escape(quote=True)，单引号转 &#x27;。脚手架 addMsg 构建
        # 用户气泡(content right)与占位AI气泡(content left)。
        self.assertIn("content &#x27;+side", html)     # createElement className 拼接
        self.assertIn("addMsg(&#x27;right&#x27;", html)  # 用户气泡
        self.assertIn("addMsg(&#x27;left&#x27;", html)   # 占位AI气泡
        # 占位文案为中文（\\uXXXX 转义），可见 ASCII 仅 'AI'/'MMD'
        self.assertIn("AI", html)
        self.assertIn("MMD", html)

    def test_panorama_combines_all_four_components_in_one_document(self):
        html = bp.assemble_panorama(self.FOUR, "mmd", "t.json")
        # 单 iframe srcdoc 内同时含四组件特征
        self.assertIn("data-sidebar", html)
        self.assertIn("data-float-ball", html)
        self.assertIn("data-radar-engine", html)
        self.assertIn("body{color:red}", html)        # 全局美化样式

    def test_panorama_scaffold_not_marked_as_tested_script(self):
        """测试脚手架在被测内容外，不应被当成被测产物加平台角标。
        沙盒改用 data-preview-sim 系脚手架（经典 <script>，无 img onerror）。"""
        cases = (("mmd", "data-pano-runtime-scaffold"),
                 ("mmdsandbox", "data-preview-sim"))
        for platform, marker in cases:
            with self.subTest(platform=platform):
                html = bp.assemble_panorama(self.FOUR, platform, "t.json")
                self.assertIn(marker, html)
                idx = html.find(marker)
                around = html[max(0, idx - 240):idx]
                self.assertNotIn("mmd-warn-badge", around)

    def test_panorama_local_array_degrades_gracefully(self):
        """本地酒馆正则数组（无 beginning）：全景退化为片段堆叠，仍含输入栏。"""
        arr = [{"scriptName": "片段", "findRegex": "<x>", "replaceString": "<div class='card'>卡片</div>"}]
        html = bp.assemble_panorama(arr, "st", "t.json")
        self.assertIn("pano-input-bar", html)
        self.assertIn("pano-send", html)
        self.assertIn("card", html)


class TestSandboxPatternClassify(unittest.TestCase):
    """沙盒模式 findRegex 走官方 classifyPattern：两形态，字面量是首选写法（D7）。"""

    def test_classify_matches_official_semantics(self):
        cases = [
            ("{{hud}}", ("literal", "{{hud}}")),
            ("  `{{hud}}`  ", ("literal", "{{hud}}")),   # 先 trim 再剥首尾反引号
            ("a.b", ("literal", "a.b")),
            ("/a/", ("regex", "/a/g")),                  # 缺 g 平台自动补
            ("/a/g", ("regex", "/a/g")),
            ("/a/d", ("literal", "/a/d")),               # d 不在 gimsuy → 整串当字面量
            ("/x/gimsuy", ("regex", "/x/gimsuy")),
        ]
        for raw, (kind, value) in cases:
            with self.subTest(raw=raw):
                self.assertEqual(bp.classify_sandbox_pattern(raw)[:2], (kind, value))

    def test_empty_and_bad_regex_kinds(self):
        self.assertEqual(bp.classify_sandbox_pattern("")[0], "empty")
        self.assertEqual(bp.classify_sandbox_pattern("   ")[0], "empty")
        self.assertEqual(bp.classify_sandbox_pattern("/[z-a]/")[0], "bad-regex")
        self.assertEqual(bp.classify_sandbox_pattern("/a/gg")[0], "bad-regex")
        self.assertEqual(bp.classify_sandbox_pattern(123)[0], "bad-regex")

    def test_pattern_containing_escaped_slash_still_regex(self):
        self.assertEqual(bp.classify_sandbox_pattern(r"/a\/b/g")[0], "regex")


class TestSandboxPipeline(unittest.TestCase):
    """沙盒模式替换管线：字面量按转义全文替换，/…/ 走正则，语法错的 /…/ 整条丢弃。"""

    @staticmethod
    def card(beginning, scripts, statusbar=""):
        return {"chatVersion": 1, "pageDepth": 2, "statusbar": statusbar,
                "beginning": beginning, "personality": "", "regex_scripts": scripts}

    def test_bare_literal_renders_and_is_not_error(self):
        """🚨 实机订正（卡 64304 A/B，2026-08-30）：裸字面量**生效**（裸 `体力` 与
        `/灵力/` 同一轮渲染都被替换）。预览必须照渲染、不判非法——否则作者在预览里
        看不到内容、以为坏了，反而误导。"""
        obj = self.card("正文 {{hud}} 尾巴", [
            {"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
             "replaceString": "<div class='does-render'>血量</div>"}])
        # 不判非法（裸字面量实机生效）。
        self.assertEqual(bp.find_invalid_findregexes(obj, "mmdsandbox"), [])
        # 照替换：触发串被换掉、替换内容出现。
        rendered = bp.apply_regex_pipeline(obj, "mmdsandbox")
        self.assertNotIn("{{hud}}", rendered)
        self.assertIn("does-render", rendered)
        html = bp.assemble_preview(obj, "mmdsandbox", "t.json")
        self.assertNotIn("ERROR 非法 findRegex", html)
        self.assertFalse(bp.fatal_preview_findings(obj, "mmdsandbox")["findRegex"])

    def test_bare_literal_metachars_match_literally(self):
        """裸字面量走 worker m() 转义：`a.b` 只匹配字面 `a.b`，不匹配 `axb`。"""
        obj = self.card("has a.b and axb", [
            {"id": -1, "scriptName": "dot", "findRegex": "a.b",
             "replaceString": "<b>HIT</b>"}])
        rendered = bp.apply_regex_pipeline(obj, "mmdsandbox")
        self.assertIn("<b>HIT</b> and axb", rendered)   # 只有 a.b 被换，axb 原样

    def test_slash_form_marker_renders_and_is_not_flagged(self):
        """交付形态（slash）必须正常替换且不报非法。"""
        obj = self.card("正文 {{hud}} 尾巴", [
            {"id": -1, "scriptName": "hud", "findRegex": "/{{hud}}/",
             "replaceString": "<div class='my-hud'>血量</div>"}])
        rendered = bp.apply_regex_pipeline(obj, "mmdsandbox")
        self.assertIn("<div class='my-hud'>血量</div>", rendered)
        self.assertNotIn("{{hud}}", rendered)
        self.assertEqual(bp.find_invalid_findregexes(obj, "mmdsandbox"), [])
        self.assertEqual(bp.find_unsupported_preview_regexes(obj, "mmdsandbox"), [])
        html = bp.assemble_preview(obj, "mmdsandbox", "t.json")
        self.assertNotIn("ERROR 非法 findRegex", html)
        self.assertIn("my-hud", html)

    def test_worker_literal_branch_renders(self):
        """worker 源码的 literal 分支实机生效：分类为 literal，交付门禁不拦，且能编译成
        预览用的转义 slash 正则。"""
        self.assertEqual(bp.classify_sandbox_pattern("{{hud}}")[:2], ("literal", "{{hud}}"))
        self.assertEqual(bp.classify_sandbox_pattern("a.b")[:2], ("literal", "a.b"))
        # 门禁不再对字面量判错。
        self.assertIsNone(bp.sandbox_pattern_delivery_error("{{hud}}"))
        self.assertIsNone(bp.sandbox_pattern_delivery_error("/{{hud}}/"))
        self.assertEqual(bp.sandbox_delivery_regex("/{{hud}}/"), "/{{hud}}/g")
        # 字面量编译成转义后的全文替换正则（元字符被转义）。
        self.assertEqual(bp.sandbox_delivery_regex("a.b"), r"/a\.b/g")

    def test_slash_form_without_g_is_still_global(self):
        obj = self.card("aa ba", [
            {"id": -1, "scriptName": "正则", "findRegex": "/a/", "replaceString": "X"}])
        self.assertEqual(bp.apply_regex_pipeline(obj, "mmdsandbox"), "XX bX")

    def test_bad_slash_form_is_surfaced_as_error_not_literal_fallback(self):
        obj = self.card("正文 /[z-a]/ 尾巴", [
            {"id": -1, "scriptName": "坏正则", "findRegex": "/[z-a]/",
             "replaceString": "<div id='must-not-render'>x</div>"}])
        invalid = bp.find_invalid_findregexes(obj, "mmdsandbox")
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0][0], "坏正则")
        self.assertIn("静默丢弃", invalid[0][2])
        # 不降级成字面量：整条被平台丢弃，替换内容不该出现
        self.assertNotIn("must-not-render", bp.apply_regex_pipeline(obj, "mmdsandbox"))
        html = bp.assemble_preview(obj, "mmdsandbox", "t.json")
        self.assertIn("ERROR 非法 findRegex", html)
        self.assertNotIn("must-not-render", html)
        self.assertTrue(bp.fatal_preview_findings(obj, "mmdsandbox")["findRegex"])

    def test_sandbox_skips_mmd_four_field_schema_audit(self):
        """沙盒导入 JSON 是 6 键白名单，不能套当前MMD 四字段 schema。"""
        obj = self.card("正文", [])
        self.assertEqual(bp.find_structure_errors(obj, "mmdsandbox"), [])
        self.assertTrue(bp.find_structure_errors(obj, "mmd"))

    def test_unmatched_style_and_script_rules_are_still_installed(self):
        """§2.1：<style>/<script> 装卡即抽出，不论这条规则有没有匹配到都会装上。
        官方首选写法就是「专开一条只放 script/style、匹配式谁都不引用」。"""
        obj = self.card("正文", [
            {"id": -1, "scriptName": "卡名-style", "findRegex": "/{{卡名-style}}/",
             "replaceString": "<style>.my-hud{color:red}</style>"},
            {"id": -2, "scriptName": "卡名-kit", "findRegex": "/{{卡名-kit}}/",
             "replaceString": "<script>function tap(){}</script>"},
        ])
        assets = bp.collect_sandbox_assets(obj)
        self.assertIn("<style>.my-hud{color:red}</style>", assets)
        self.assertIn("<script>function tap(){}</script>", assets)
        for html in (bp.assemble_panorama(obj, "mmdsandbox", "t.json"),
                     bp.assemble_preview(obj, "mmdsandbox", "t.json")):
            self.assertIn("function tap()", html)
            self.assertIn(".my-hud{color:red}", html)
            # 既 hoist 又随替换插入会执行两次，必须只出现一次
            self.assertEqual(html.count("function tap()"), 1)

    def test_hoisted_assets_are_removed_from_visible_replacement(self):
        obj = self.card("{{hud}}", [
            {"id": -1, "scriptName": "hud", "findRegex": "/{{hud}}/",
             "replaceString": "<style>.a{color:red}</style><div class='my-hud'>栏</div>"}])
        rendered = bp.apply_regex_pipeline(obj, "mmdsandbox")
        self.assertIn("<div class='my-hud'>栏</div>", rendered)
        self.assertNotIn("<style>", rendered)
        self.assertIn("<style>.a{color:red}</style>", bp.collect_sandbox_assets(obj))

    def test_svg_children_are_not_reported_as_dangling_markers(self):
        """svg 及 path/circle/rect/line/text 在沙盒白名单内（§5.2），
        但通用 HTML_TAGS 不含它们 → 必须不被误判成悬空标记。"""
        obj = self.card("{{图}}", [
            {"id": -1, "scriptName": "图", "findRegex": "/{{图}}/",
             "replaceString": "<svg viewBox='0 0 10 10'><circle r='4'></circle>"
                              "<path d='M0 0'></path></svg>"}])
        self.assertEqual(bp.find_dangling_markers(obj, "mmdsandbox"), [])
        self.assertEqual(bp.fatal_preview_findings(obj, "mmdsandbox")["dangling"], [])

    def test_real_dangling_marker_outside_svg_still_reported(self):
        obj = self.card("正文<missing>", [])
        self.assertIn("<missing>", bp.find_dangling_markers(obj, "mmdsandbox"))

    def test_mmd_still_rejects_bare_literal(self):
        """不得削弱当前MMD：裸字面量在 /mmd 仍是结构错误。
        ⚠️ 这条的 findRegex 必须保持**裸字面量**——它测的就是 MMD 拒绝裸字面量。"""
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "{{hud}}",
               "regex_scripts": [{"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
                                  "replaceString": "<div>x</div>"}]}
        self.assertTrue(bp.find_invalid_findregexes(obj, "mmd"))
        self.assertIn("{{hud}}", bp.apply_regex_pipeline(obj, "mmd"))


class TestSandboxRendering(unittest.TestCase):
    """沙盒模式渲染差异：<script> 保留、不套当前MMD onclick 净化、净化告警、横幅。"""

    def test_script_survives_and_is_badged(self):
        source = "<script>function tap(){}</script><button onclick=\"tap()\">点</button>"
        out = bp.apply_platform_limits(source, "mmdsandbox")
        self.assertIn("<script>function tap(){}</script>", out)
        self.assertIn("✓script", out)
        self.assertIn("一等公民", out)

    def test_ordinary_onclick_is_not_sanitized(self):
        """沙盒允许普通标签 onclick 调顶层函数，不施加当前MMD 纯度规则。"""
        source = "<button onclick=\"tap()\">点</button>"
        self.assertIn('onclick="tap()"', bp.apply_platform_limits(source, "mmdsandbox"))
        self.assertNotIn("data-mmd-onclick-disabled",
                         bp.apply_platform_limits(source, "mmdsandbox"))
        obj = {"chatVersion": 1, "pageDepth": 2, "statusbar": "", "beginning": "{{hud}}",
               "personality": "", "regex_scripts": [
                   {"id": -1, "scriptName": "hud", "findRegex": "/{{hud}}/",
                    "replaceString": "<button onclick=\"tap()\">点</button>"}]}
        self.assertEqual(bp.find_invalid_onclicks(obj, "mmdsandbox"), [])
        self.assertEqual(bp.fatal_preview_findings(obj, "mmdsandbox")["onclick"], [])

    def test_svg_on_attr_and_author_data_attr_are_warned(self):
        content = ('<svg viewBox="0 0 10 10"><circle onclick="tap()" r="4"></circle></svg>'
                   '<div data-hp="80">血量</div>')
        kinds = [k for k, _ in bp.find_sandbox_sanitized_attrs(content)]
        # 实测 SVG 内**所有** on* 都被删（不只 onclick），故种类名为 svg-on-attr。
        self.assertIn("svg-on-attr", kinds)
        self.assertIn("author-data-attr", kinds)
        rows = bp._onclick_audit_html(content, "mmdsandbox")
        self.assertIn("svg 内的 on* 会被沙盒净化删除", rows)
        self.assertIn("作者自写 data-* 会被沙盒净化删除", rows)

    def test_confirmed_sanitization_subset_is_audited(self):
        """已确证净化子集：aria-*/role、SVG on*、禁用标签、SAFE_FOR_XML 危险属性值。"""
        cases = {
            "aria-or-role": '<div role="button" aria-label="x">a</div>',
            "stripped-tag": '<iframe src="x"></iframe>',
            "safe-for-xml": '<b onclick="if(a[0]>1){f()}">x</b>',
            "svg-on-attr": '<svg><circle onmouseenter="f()"></circle></svg>',
        }
        for kind, html in cases.items():
            with self.subTest(kind=kind):
                kinds = [k for k, _ in bp.find_sandbox_sanitized_attrs(html)]
                self.assertIn(kind, kinds)

    def test_safe_for_xml_spaced_comparison_is_not_flagged(self):
        """实测 title="a[0] > 1"（] 与 > 之间有空格）完整保留 → 不该报。"""
        kinds = [k for k, _ in bp.find_sandbox_sanitized_attrs('<b title="a[0] > 1">x</b>')]
        self.assertNotIn("safe-for-xml", kinds)

    def test_output_budget_and_empty_match_rollback_are_errors(self):
        card = {"chatVersion": 1, "pageDepth": 2, "statusbar": "", "beginning": "正文",
                "personality": "", "regex_scripts": [
                    {"id": -1, "scriptName": "超预算", "findRegex": "/正文/",
                     "replaceString": "x" * (bp.SANDBOX_OUTPUT_BUDGET_FLOOR + 1)},
                    {"id": -2, "scriptName": "空串匹配", "findRegex": "/a*/",
                     "replaceString": "<b>x</b>"}]}
        findings = bp.find_sandbox_budget_findings(card, "mmdsandbox")
        kinds = {name: kind for name, kind, _ in findings}
        self.assertEqual(kinds.get("超预算"), "replacement-alone")
        self.assertEqual(kinds.get("空串匹配"), "empty-match")
        rows = bp._sandbox_budget_audit_html(card, "mmdsandbox")
        self.assertIn("整条回滚", rows)
        # 预算公式锁定：max(262144, 输入长度×4)
        self.assertEqual(bp.sandbox_output_budget(0), 262144)
        self.assertEqual(bp.sandbox_output_budget(100000), 400000)

    def test_platform_data_attrs_are_not_warned(self):
        content = ('<div data-chat="root"><span data-slot="statusbar"></span>'
                   '<button onclick="tap()">ok</button></div>')
        self.assertEqual(bp.find_sandbox_sanitized_attrs(content), [])

    def test_banner_label_and_css_class(self):
        banner = bp.make_banner("mmdsandbox", "t.json", 3)
        self.assertIn("banner-mmdsandbox", banner)
        self.assertIn("MMD沙盒模式", banner)
        self.assertIn("chatVersion:1", banner)
        # 两处 CSS 块都要有 .banner-mmdsandbox 规则
        self.assertIn(".banner-mmdsandbox{", bp.PAGE_TEMPLATE)
        self.assertIn(".banner-mmdsandbox{", bp.PANORAMA_PAGE_TEMPLATE)

    def test_oldmmd_platform_is_retired(self):
        """oldmmd 已退役：CSS、labels、--platform choices 都不该再有它。"""
        self.assertNotIn("oldmmd", bp.PAGE_TEMPLATE)
        self.assertNotIn("oldmmd", bp.PANORAMA_PAGE_TEMPLATE)
        self.assertNotIn("oldmmd", bp.MARKER_CSS)
        with open(bp.__file__, encoding="utf-8") as f:
            self.assertNotIn("oldmmd", f.read())


class TestSandboxPanoramaChrome(unittest.TestCase):
    """沙盒模式全景注入官方稳定钩子与 --chat-* 变量，作者选择器/变量在预览里可解析。"""

    # 匹配式统一 slash 形态（约定；裸字面量实机也生效，事实卡 §8.21）。
    CARD = {"chatVersion": 1, "pageDepth": 2, "statusbar": "{{hud}}",
            "beginning": "正文 {{panel}}", "personality": "",
            "regex_scripts": [
                {"id": -1, "scriptName": "hud", "findRegex": "/{{hud}}/",
                 "replaceString": "<div class='my-hud'>功能栏</div>"},
                {"id": -2, "scriptName": "panel", "findRegex": "/{{panel}}/",
                 "replaceString": "<div class='my-panel'>面板</div>"},
            ]}

    def test_panorama_carries_data_chat_hooks(self):
        """断言属性形态（前导空格），避免被 SANDBOX_CHROME_CSS 里的选择器文本蒙过。"""
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        for hook in ("root", "header", "header-back", "header-title", "header-actions",
                     "messages", "list", "message-frame", "message", "message-body",
                     "message-actions", "author-stage", "composer", "input", "send"):
            with self.subTest(hook=hook):
                self.assertIn(" data-chat=&quot;%s&quot;" % hook, html)
        for slot in ("statusbar", "header-extra", "message-extra", "left", "right", "toolbar"):
            with self.subTest(slot=slot):
                self.assertIn(" data-slot=&quot;%s&quot;" % slot, html)
        self.assertIn(" data-from=&quot;ai&quot;", html)
        self.assertIn(" data-from=&quot;user&quot;", html)
        self.assertIn(" data-theme=&quot;dark&quot;", html)
        self.assertIn(" data-composer=&quot;visible&quot;", html)
        self.assertIn(" data-msg-id=&quot;pano-", html)

    def test_sandbox_host_matches_measured_chat_shell(self):
        """锁定 2026-08-27 真实聊天页的宿主边界，避免退回通用 fixed-input 预览。"""
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        self.assertIn('<div class="pano-sandbox-host"><div class="page" data-chat="root"', chrome)
        self.assertIn('style="--chat-viewport-height:100vh;', chrome)
        self.assertIn("background-image:url('data:image/svg+xml", chrome)
        self.assertIn('<header class="topTabbar" data-chat="header">', chrome)
        self.assertIn('<main class="chat chat-bg pano-chat" id="pano-chat" data-chat="messages">', chrome)
        self.assertIn('<footer class="chat-bottom chat-input-scope pano-input-bar" data-chat="composer">', chrome)
        self.assertIn('placeholder="快来聊天吧~" data-chat="input"', chrome)
        self.assertIn("模型设置", chrome)
        self.assertIn("用户人设", chrome)
        self.assertIn("气泡辅助线", chrome)
        # 真机 default：辅助线不开；工具按钮才按需挂标记。
        root_open = chrome.split('<div class="pano-sandbox-host">', 1)[1].split(">", 1)[0]
        self.assertNotIn("data-preview-bubble-outline", root_open)

    def test_sandbox_dom_slots_are_direct_root_children(self):
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        left = chrome.index('<div data-slot="left"></div>')
        right = chrome.index('<div data-slot="right"></div>')
        stage = chrome.index('<div data-chat="author-stage"')
        composer = chrome.index('<footer class="chat-bottom')
        self.assertLess(left, right)
        self.assertLess(right, stage)
        self.assertLess(stage, composer)
        # 只计实际节点开标签，不能把 CSS 选择器文本算进去。
        self.assertEqual(chrome.count('<div data-slot="left"></div>'), 1)
        self.assertEqual(chrome.count('<div data-slot="right"></div>'), 1)

    def test_sandbox_author_scripts_execute_without_inframe_audit_badges(self):
        """角标属于诊断层；放进 iframe 会挤掉真实 header/composer 几何。"""
        card = dict(self.CARD, regex_scripts=list(self.CARD["regex_scripts"]) + [
            {"id": -3, "scriptName": "kit", "findRegex": "/{{kit}}/",
             "replaceString": "<script>window.__author_ran=1;</script>"}])
        chrome = html_mod.unescape(bp.assemble_panorama(card, "mmdsandbox", "t.json"))
        self.assertIn("window.__author_ran=1", chrome)
        frame_doc = html_mod.unescape(
            chrome.split('<iframe class="pano-frame" srcdoc="', 1)[1].split('" sandbox=', 1)[0])
        # marker CSS 可包含类名；禁止的是实际可见角标节点。
        self.assertNotIn('<div class="mmd-warn-badge"', frame_doc)
        self.assertNotIn(">✓script</div>", frame_doc)
        # 三面板诊断仍保留角标，脚本可执行性证据没有被删除。
        panels = bp.assemble_preview(card, "mmdsandbox", "t.json")
        self.assertIn("✓script", panels)

    def test_sandbox_controls_and_diagnostics_are_collapsed(self):
        html = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        self.assertIn('<details class="preview-tools" data-preview-tools="1">', html)
        self.assertNotIn('<details class="preview-tools" data-preview-tools="1" open', html)
        self.assertIn('<div class="preview-tools-body">', html)
        self.assertIn('.preview-tools:not([open])>.preview-tools-body{display:none}',
                      bp.PANORAMA_PAGE_TEMPLATE)
        self.assertNotIn('.preview-tools{display:flex', bp.PANORAMA_PAGE_TEMPLATE)
        self.assertIn("沙盒仿真控制（默认折叠）", html)
        self.assertIn('<details class="pano-audit">', html)
        self.assertIn("white-space:nowrap;overflow:hidden;text-overflow:ellipsis", bp.PANORAMA_PAGE_TEMPLATE)
        # 映射模板里的裸 % 会直到最终格式化才爆，必须直接锁定整页可生成。
        rendered = bp.PANORAMA_PAGE_TEMPLATE % {
            "platform": "mmdsandbox", "banner": "b", "body": "x", "marker_css": "m"
        }
        self.assertIn("width:100%", rendered)

    def test_sandbox_css_preserves_platform_defaults_for_sbk_to_fix(self):
        # 读渲染后的 CSS：模板里裸 % 已转义成 %%（要填两套令牌与 rpx 两档）。
        css = bp._sandbox_chrome_css()
        self.assertIn('height:var(--chat-viewport-height)', css)
        self.assertIn('background-color:var(--chat-bg)', css)
        self.assertIn('[data-chat="composer"]{position:static;', css)
        self.assertIn('left:auto;right:auto;bottom:auto', css)
        self.assertNotIn('[data-slot="statusbar"]{position:sticky', css)
        self.assertNotIn('[data-slot="statusbar"]{flex-shrink:0', css)
        self.assertIn('white-space:pre-line;opacity:.9', css)
        # 底栏按钮的平台默认（真机 button reset）走真实钩子，不再用 .pano-* 自造类。
        self.assertIn('[data-chat="composer"] button{appearance:none;', css)
        self.assertIn('background:0 0;border:0;margin:0;padding:0;', css)
        # legacy 自造类不得再带样式（否则与钩子规则打架，行为偏离真机）。
        # 只查声明，不查注释（注释里会提到这些类名解释为什么不给样式）。
        decls = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for legacy in (".pano-input-shell{", ".pano-compose-icon,.pano-send{",
                       ".pano-shortcut{", ".pano-shortcuts{", ".pano-compose-row{"):
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, decls)
        self.assertIn('[data-preview-bubble-outline] [data-chat="message-body"]', css)
        # 真实消息附加槽必须存在，动态消息也由模拟器构造同样的子节点。
        self.assertIn('data-slot="message-extra"', html_mod.unescape(
            bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")))
        sim = bp.load_sandbox_sim_source()
        self.assertIn("extra.setAttribute('data-slot', 'message-extra')", sim)
        self.assertIn("actions.setAttribute('data-chat', 'message-actions')", sim)

    def test_contract_records_real_chat_visual_shell(self):
        shell = bp.load_sandbox_contract()["cssContract"]["visualShell"]
        self.assertEqual(shell["accuracy"], "exact")
        self.assertEqual(shell["defaultObservedTheme"], "dark")
        self.assertEqual(shell["header"]["desktopHeightPx"], 45)
        self.assertEqual(shell["composer"]["position"], "static")
        self.assertEqual(shell["message"]["bodyOpacity"], 0.9)
        self.assertEqual(shell["message"]["bodyWhiteSpace"], "pre-line")
        self.assertEqual(shell["directRootSlots"], ["statusbar", "left", "right"])
        self.assertEqual(shell["messageChildren"],
                         ["message-body", "message-extra", "message-actions"])

    def test_panorama_defines_all_sandbox_design_tokens(self):
        """防回归：29 个实测设计令牌必须全部注入产物（两套主题各一份）。

        引用实现里的 SANDBOX_DESIGN_TOKENS 而非另抄一份清单，避免测试与实现漂移。
        🚨 2026-08-29 实测把 14 → 29：旧版漏了 15 个，其中整个 --chat-modal-* 族（9 个）
        与 --chat-composer-*/--chat-shortcut-bg/--chat-input-placeholder/--chat-input-border
        都是真机可用的（官方手册称「底栏和白名单弹窗」18 个变量，逐个注入醒目色验证生效）。
        漏注入 → 作者写 var(--chat-modal-bg) 在预览里解析不到、真机却正常，
        会误导作者去修不存在的 bug。
        """
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        chrome = html_mod.unescape(html)
        self.assertEqual(len(bp.SANDBOX_DESIGN_TOKENS), 29)
        # 分组构成：气泡 10 + 白名单 18 + more-item-bg 别名 1
        self.assertEqual(len(bp.SANDBOX_BUBBLE_TOKENS), 10)
        self.assertEqual(len(bp.SANDBOX_WHITELIST_TOKENS), 18)
        for var in bp.SANDBOX_DESIGN_TOKENS:
            with self.subTest(var=var):
                self.assertIn("%s:" % var, chrome)

    def test_panorama_injects_non_token_sandbox_vars(self):
        """--chat-viewport-height 与 --rpx 都不属那 14 个令牌，但预览要模拟注入。

        --chat-viewport-height 真机是 JS 内联 style；--rpx 是平台尺寸基准，
        不注入则作者的 calc(24 * var(--rpx)) 会算空 → 预览尺寸全塌。
        """
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        self.assertIn("--chat-viewport-height:", chrome)
        self.assertIn("--rpx:calc(100vw / 750)", chrome)
        self.assertNotIn("--chat-viewport-height", bp.SANDBOX_DESIGN_TOKENS)
        self.assertNotIn("--rpx", bp.SANDBOX_DESIGN_TOKENS)

    def test_dark_tokens_equal_measured_truth(self):
        """防回退：深色 14 个令牌必须等于实测真值，不许改成"好看但失真"的值。

        曾经这里是 --chat-bg:#16181d + 气泡 #1a7f5a/#22262c，预览因此显示出
        "气泡有独立底色"这个平台不存在的配色 —— 作者照它定配色，上真机才发现
        整块糊在背景里。这种谎发生在设计决策阶段，代价高于"气泡默认看不见"。
        """
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        dark = chrome.split('[data-theme="dark"]{', 1)[1].split("}", 1)[0]
        parsed = dict(kv.split(":", 1) for kv in
                      (p.strip() for p in dark.replace("\n", "").split(";")) if kv)
        # 4 个别名必须发 var() 引用形态（真机如此）；其余发实测字面量。
        # 展开成字面量会让作者改 --chat-bg/--chat-modal-surface 时预览不跟随、真机跟随。
        expected = {k: bp.SANDBOX_ALIAS_TOKENS.get(k, v)
                    for k, v in bp.SANDBOX_DARK_TOKEN_VALUES.items()}
        self.assertEqual(parsed, expected)
        self.assertEqual(parsed["--chat-bg"], "#17181a")
        self.assertEqual(parsed["--chat-bubble-user-bg"], "var(--chat-bg)")
        self.assertEqual(parsed["--chat-bubble-ai-bg"], "var(--chat-bg)")
        self.assertEqual(parsed["--chat-bubble-text"], "var(--chat-text)")
        self.assertEqual(parsed["--chat-more-item-bg"], "var(--chat-modal-surface)")
        # 解析后仍与页面背景同色（实测），只是这层关系由 var() 表达而非硬编码
        self.assertEqual(bp.SANDBOX_DARK_TOKEN_VALUES["--chat-bubble-ai-bg"],
                         bp.SANDBOX_DARK_TOKEN_VALUES["--chat-bg"])
        self.assertEqual(set(parsed), set(bp.SANDBOX_DESIGN_TOKENS))

    def test_bubble_outline_is_preview_aid_not_a_color_claim(self):
        """描边必须独立、默认关闭、只用 --chat-border，且 NOTE 说清真机没有。"""
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        chrome = html_mod.unescape(html)
        root_open = chrome.split('<div class="pano-sandbox-host">', 1)[1].split(">", 1)[0]
        self.assertNotIn('data-preview-bubble-outline', root_open)
        self.assertIn("[data-preview-bubble-outline] [data-chat=\"message-body\"]"
                      "{box-shadow:inset 0 0 0 1px var(--chat-border)}", chrome)
        # 描边不得混进令牌定义块（那里只放平台真值）。
        dark = chrome.split('[data-theme="dark"]{', 1)[1].split("}", 1)[0]
        self.assertNotIn("box-shadow", dark)
        # NOTE 必须告诉作者这是预览辅助、真机气泡与背景同色。
        self.assertIn("预览辅助线", html)
        self.assertIn("真机上没有", html)
        # 预览器自注的标记不该被当成作者自写 data-* 报净化告警。
        self.assertEqual(bp.find_sandbox_sanitized_attrs(
            '<div data-preview-bubble-outline="1"></div>'), [])

    def test_sandbox_tokens_defined_in_both_themes(self):
        """两套主题各一份（实测：平台定义在 [data-theme=dark]/[data-theme=light]，无 :root）。

        预览把浅色放基底规则、深色放 [data-theme="dark"] 覆盖规则，故深色块里
        只需出现主题相关的差异令牌；此处断言深色覆盖块确实带上了漏记的 5 个。
        """
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        dark = chrome.split('[data-theme="dark"]{', 1)[1].split("}", 1)[0]
        for var in ("--chat-input-bg", "--chat-input-text", "--chat-shortcut-text",
                    "--chat-more-item-bg", "--chat-share-pick-bg"):
            with self.subTest(var=var):
                self.assertIn("%s:" % var, dark)

    # ── 以下 5 条锁死 2026-08-29 沙盒实机抓取的结论 ──────────────────────────
    # 依据：Playwright 进真实卡片 iframe（c<roleId>.sbx.aitchat.org，跨源）读 CSSOM
    #      + 逐个点开面板 + 注入探针验证变量是否生效。
    # 契约：references/platforms/mmd-sandbox-real-page-contract-2026-08-29.md

    def test_light_tokens_equal_measured_truth(self):
        """浅色 29 个也是实测真值（旧注释说"类推、未实测"，那个状态已结束）。

        平台把两套分别定义在 [data-theme=light]/[data-theme=dark]（无 :root）。
        预览把浅色放基底规则 —— 断言它逐字等于实测表，防有人"顺手调好看"。
        """
        self.assertEqual(len(bp.SANDBOX_LIGHT_TOKEN_VALUES), 29)
        self.assertEqual(set(bp.SANDBOX_LIGHT_TOKEN_VALUES), set(bp.SANDBOX_DESIGN_TOKENS))
        for name, value in (("--chat-bg", "#fff"), ("--chat-accent", "#17aafd"),
                            ("--chat-modal-bg", "#fff"), ("--chat-modal-surface", "#f5f8fc"),
                            ("--chat-shortcut-bg", "#f1f4f9"),
                            ("--chat-modal-btn-border", "#efefef")):
            with self.subTest(name=name):
                self.assertEqual(bp.SANDBOX_LIGHT_TOKEN_VALUES[name], value)
        # 气泡三色实测是 var(--chat-bg)/var(--chat-text) 的别名 → 解析后必然同色
        lv = bp.SANDBOX_LIGHT_TOKEN_VALUES
        self.assertEqual(lv["--chat-bubble-ai-bg"], lv["--chat-bg"])
        self.assertEqual(lv["--chat-bubble-user-bg"], lv["--chat-bg"])
        self.assertEqual(lv["--chat-bubble-text"], lv["--chat-text"])
        # 基底规则（浅色）必须真的带上这些取值
        chrome = bp._sandbox_chrome_css()
        base = chrome.split('[data-theme="light"]{', 1)[1].split("}", 1)[0]
        self.assertIn("--chat-modal-bg:#fff;", base)
        self.assertIn("--chat-accent:#17aafd;", base)

    def test_sandbox_rpx_matches_measured_breakpoint(self):
        """--rpx 实测两档：基底 100vw/750，@media(min-width:961px) 封顶 375px/750。

        🚨 旧版写 `@media(min-width:750px){--rpx:1px}` —— 断点与取值双错。桌面档真值
        是 0.5px 而非 1px，差 2 倍：作者按预览调的尺寸上真机全错一半。
        实测三点：视口 298→单位 298px、400→400px、1280→375px。
        """
        self.assertEqual(bp.SANDBOX_RPX_BASE, "calc(100vw / 750)")
        self.assertEqual(bp.SANDBOX_RPX_DESKTOP, "calc(375px / 750)")
        self.assertEqual(bp.SANDBOX_RPX_BREAKPOINT, "961px")
        css = bp._sandbox_chrome_css()
        self.assertIn("--rpx:calc(100vw / 750)", css)
        self.assertIn("@media (min-width:961px){[data-chat=\"root\"]{--rpx:calc(375px / 750)}}", css)
        # 旧的错值不得回归
        self.assertNotIn("--rpx:1px", css)
        self.assertNotIn("min-width:750px", css)

    def test_sandbox_carries_measured_composer_hooks(self):
        """底栏真实钩子名（旧版是 .pano-* 自造类，作者按手册写选择器会失配）。"""
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        for hook in ('data-chat="shortcut"', 'data-chat="instruction-bar"',
                     'data-chat="instruction-back"', 'data-chat="instruction-chip"',
                     'data-chat="assistant"', 'data-chat="model-chip"',
                     'data-action="more"', 'class="composer-shortcut-wrap"',
                     'composer-row', 'composer-field'):
            with self.subTest(hook=hook):
                self.assertIn(hook, chrome)
        # 快捷条 6 个按钮带真实 data-action（真机就是这套）
        for act in ("model", "style", "instructions", "summary", "conversations", "persona"):
            with self.subTest(act=act):
                self.assertIn('data-action="%s"' % act, chrome)

    def test_sandbox_simulates_in_iframe_overlays(self):
        """iframe 内浮层：卡片 CSS 能打到，必须完整仿真且默认全关。"""
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        for node in ('data-chat="more-panel"', 'data-chat="message-menu"',
                     'data-chat="alert"', 'data-chat="toast"', 'data-chat="alert-ok"',
                     'data-chat="snack"', 'data-probe="snackbar"',
                     'data-chat="share-bar"', 'data-chat="share-pick-bar"',
                     'data-chat="share-shot-loading"', 'data-chat="summary-bubble"',
                     'data-probe="history-loading"'):
            with self.subTest(node=node):
                self.assertIn(node, chrome)
        # 默认全关。只看节点开标签：CSS 里满是 `[data-open="on"]` 选择器、
        # 脚手架里也有 'on' 字面量，都不能当"有面板开着"。
        tags = re.findall(r'<div [^>]*data-open="(on|off)"', chrome)
        self.assertTrue(tags, "没有找到任何浮层节点")
        self.assertEqual(set(tags), {"off"})
        # 「+」面板吃白名单变量（手册说法，实测一致）
        css = bp._sandbox_chrome_css()
        self.assertIn('[data-chat="more-panel"]{', css)
        self.assertIn("background:var(--chat-modal-bg);color:var(--chat-modal-text)", css)
        self.assertIn("background:var(--chat-more-item-bg)", css)
        # 舞台三态（旧版只有一个 fixed/z-2000，把 content 也画成盖整屏了）
        self.assertIn('[data-chat="author-stage"][data-stage="content"]'
                      '{position:absolute;z-index:2000}', css)
        self.assertIn('[data-chat="author-stage"][data-stage="full"]'
                      '{position:fixed;inset:0;z-index:3000}', css)
        # 开关脚手架必须是经典 script（沙盒禁 img onerror）
        self.assertIn('data-preview-panels="1"', chrome)
        self.assertIn("__sbxPanels", chrome)

    def test_token_specificity_lets_author_override_win(self):
        """🚨 令牌必须挂**单属性** [data-theme=*]，与真机同特异性 0,1,0。

        曾写成 `[data-chat="root"][data-theme="dark"]`（0,2,0）→ 作者按官方手册写
        `[data-chat="root"]{--chat-modal-bg:X}`（0,1,0）在预览里被压过、看着"没生效"，
        而真机两边都是 0,1,0、靠文档顺序作者赢（平台 CSS 在前、作者 hoisted style 在后）。
        这类"预览比真机更严"的假象会让作者去改一个没坏的东西。
        同理 more-panel 那几条真机不带 composer 前缀，预览也不能多套一层。
        """
        css = bp._sandbox_chrome_css()
        # 只查声明，不查注释（注释里会引用旧的错写法解释为什么不能那样写）
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertIn('[data-theme="dark"]{', css)
        self.assertIn('[data-theme="light"]{', css)
        self.assertNotIn('[data-chat="root"][data-theme=', css)
        # more-panel 四条保持真机特异性（不带 [data-chat="composer"] 前缀）
        for sel in ('[data-chat="more-panel"]{', '[data-chat="more-panel"][data-open="on"]{',
                    '[data-chat="more-panel"] > button{',
                    '[data-chat="more-panel"] > button > span{'):
            with self.subTest(sel=sel):
                self.assertIn("\n" + sel, css)
                self.assertNotIn('[data-chat="composer"] ' + sel, css)
        # 别名 4 个发引用形态，作者改基色时能顺着传导
        self.assertEqual(len(bp.SANDBOX_ALIAS_TOKENS), 4)
        for name, ref in bp.SANDBOX_ALIAS_TOKENS.items():
            with self.subTest(name=name):
                self.assertIn("%s:%s;" % (name, ref), css)

    def test_composer_field_three_states_match_measured_css(self):
        """输入框三态照实测原文（2026-08-29）：

        折叠 `min-height:82rpx`（旧版漏了，输入行整体矮一截）；
        多行 is-multiline 换 padding + 底对齐、两侧圆钮 padding-bottom 27rpx；
        展开 is-expanded 转 grid 三区，工具行「粘贴/清空」才显示、model-chip order 归 0。
        🚨 font-size 实测在 ::placeholder 规则里而非 input 本体 —— 照抄，别给 input 补字号。
        """
        css = bp._sandbox_chrome_css()
        self.assertIn(".composer-field:not(.is-expanded){min-height:calc(82 * var(--rpx))}", css)
        self.assertIn('grid-template-areas:"tools tools tools" "input input input" '
                      '"chip . send"', css)
        self.assertIn(".composer-field:not(.is-expanded) .composer-tools{display:none}", css)
        self.assertIn(".composer-field.is-expanded [data-chat=\"model-chip\"]{order:0}", css)
        self.assertIn("padding-bottom:calc(27 * var(--rpx));align-self:flex-end", css)
        self.assertIn(".composer-field:not(.is-expanded) [data-chat=\"input\"]"
                      "{padding:0 calc(12 * var(--rpx))", css)
        # 字号只在 placeholder 规则里
        input_rule = css.split('[data-chat="input"]{', 1)[1].split("}", 1)[0]
        self.assertNotIn("font-size", input_rule)
        self.assertIn('[data-chat="input"]::placeholder{', css)
        ph = css.split('[data-chat="input"]::placeholder{', 1)[1].split("}", 1)[0]
        self.assertIn("font-size:calc(32 * var(--rpx))", ph)
        # 骨架里工具行与三态切换 API
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        self.assertIn('class="composer-tools"', chrome)
        self.assertIn('data-chat="paste"', chrome)
        self.assertIn('data-chat="clear"', chrome)
        self.assertIn("fieldState", chrome)
        # 顺序：composer-field 内 composer-tools 在 input 之前（grid 里 tools 区在最上）。
        # 只在 field 片段里比，否则会撞上前面 CSS 里的同名字符串。
        field = chrome.split('class="pano-input-shell composer-field">', 1)[1]
        self.assertLess(field.index('class="composer-tools"'),
                        field.index('data-chat="input"'))

    def test_more_panel_items_are_clickable_with_measured_actions(self):
        """「+」面板 11 项的 data-action 照真机，且每项可点。

        面板在 iframe 内 → 作者的全局美化能打到它，所以必须点得开、看得见效果。
        能开面板的直接开（对话设置/剧情总结/用户人设/新的聊天走宿主占位、
        自定义指令切指令栏），其余弹 snack 说明是平台侧动作、预览不模拟真实副作用。
        """
        self.assertEqual(len(bp.SANDBOX_MORE_ITEMS), 11)
        actions = [a for a, _g, _l in bp.SANDBOX_MORE_ITEMS]
        self.assertEqual(actions, ["reset", "export", "conversations", "role-edit",
                                   "background", "instructions", "persona", "extra",
                                   "style", "summary", "help"])
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        panel = chrome.split('<div data-chat="more-panel"', 1)[1].split("</div>", 1)[0]
        for act in actions:
            with self.subTest(act=act):
                self.assertIn('data-action="%s"' % act, panel)
        # 11 个按钮都有图标底 span（吃 --chat-more-item-bg）与文字标签
        self.assertEqual(panel.count("<button"), 11)
        self.assertEqual(panel.count("<span>"), 11)
        # 脚手架里绑了点击 + snack 兜底
        self.assertIn('[data-chat="more-panel"] > button', chrome)
        self.assertIn("function snack(", chrome)

    def test_host_popups_are_marked_unstylable_not_faked(self):
        """🚨 宿主页那 5 个弹窗渲染在 h5 域的 uni-app 里，跨源 iframe 之外。

        探针验证：在卡片 iframe 内注入 --chat-modal-bg:#00ff00 后打开模型设置，
        它仍是 #17181a，且该变量在其上解析为「未定义」。所以预览**只画层级占位**、
        明确标注平台侧，绝不套 --chat-modal-* —— 套了就是撒谎，作者会白写选择器。
        """
        chrome = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        for name in ("model", "conv", "summary", "role", "share"):
            with self.subTest(name=name):
                self.assertIn('data-host-popup="%s"' % name, chrome)
        self.assertIn("平台侧 · 卡片改不动", chrome)
        self.assertIn("对它无效", chrome)
        # 占位壳用硬编码灰底斜纹，不吃白名单令牌（吃了就等于宣称能改）
        css = bp._sandbox_chrome_css()
        sheet = css.split(".pano-host-popup .pano-host-sheet{", 1)[1].split("}", 1)[0]
        self.assertIn("background:#17181a", sheet)
        self.assertNotIn("--chat-modal", sheet)
        # 实测 z-index 差异：总结剧情 1000000000，分享 9000（旧聊天页是 10075）
        self.assertIn('.pano-host-popup[data-host-popup="summary"]{z-index:1000000000}', css)
        self.assertIn("z-index <b>9000</b>", chrome)

    STATUSBAR_NODE = "&lt;div data-slot=&quot;statusbar&quot;"

    def test_statusbar_rendered_into_its_own_slot(self):
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        self.assertIn(self.STATUSBAR_NODE, html)
        statusbar_block = html.split(self.STATUSBAR_NODE, 1)[1].split("&lt;/div&gt;", 1)[0]
        self.assertIn("my-hud", statusbar_block)
        # beginning 的内容归消息体，不混进功能栏
        self.assertNotIn("my-panel", statusbar_block)
        self.assertIn("my-panel", html)

    def test_empty_statusbar_node_absent(self):
        """角色卡 statusbar 留空 → 平台上功能栏整块不存在，预览照此处理。"""
        card = dict(self.CARD, statusbar="")
        html = bp.assemble_panorama(card, "mmdsandbox", "t.json")
        self.assertNotIn(self.STATUSBAR_NODE, html)

    def test_multiround_toolbar_carries_raw_and_rendered_state(self):
        card = dict(self.CARD, regex_scripts=list(self.CARD["regex_scripts"]) + [{
            "id": -9, "scriptName": "状态快照",
            "findRegex": r"/\[状态\]([\s\S]*?)\[\/状态\]/",
            "replaceString": '<div class="sbk-snap sbk-snap--raw">$1</div>'
        }])
        html = html_mod.unescape(bp.assemble_panorama(card, "mmdsandbox", "t.json"))
        self.assertIn("AI 追答", html)
        self.assertIn("[状态]", html, "事件 payload 必须保留原始模型正文")
        self.assertIn("sbk-snap sbk-snap--raw", html, "动态气泡 DOM 必须使用同一离线规则管线")
        self.assertIn("好感: 苏九=64", html, "第二轮夹具应有可观察的状态变化")

    def test_panorama_diagnostics_are_collapsed_after_preview(self):
        html = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        self.assertIn('<details class="pano-audit">', html)
        self.assertNotIn('<details class="pano-audit" open', html,
                         "诊断说明默认必须折叠，不能挡住实际预览")
        self.assertIn("诊断与证据说明（默认折叠）", html)
        self.assertLess(html.index('class="pano-frame"'), html.index('class="pano-audit"'),
                        "实际预览必须排在诊断说明之前")
        self.assertIn("NOT SIMULATED", html, "折叠只能改变布局，不能删除证据边界")

    def test_sandbox_panorama_matches_real_iframe_permissions(self):
        contract = bp.load_sandbox_contract()
        permissions = contract["environment"]["hostIframeSandbox"]
        self.assertEqual(
            permissions["attribute"],
            "allow-scripts allow-same-origin allow-forms allow-modals allow-downloads",
        )
        self.assertEqual(permissions["accuracy"], "exact")
        html = html_mod.unescape(bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json"))
        self.assertIn('sandbox="%s"' % permissions["attribute"], html)
        legacy = html_mod.unescape(bp.assemble_panorama(TestPanorama.FOUR, "mmd", "t.json"))
        self.assertIn('sandbox="allow-scripts allow-same-origin"', legacy)
        self.assertNotIn("allow-forms", legacy)

    def test_panorama_states_what_is_not_simulated(self):
        """SDK 现在**有**本地仿真，但必须同时讲清哪些仍需真实站验证。"""
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        self.assertIn("NOT SIMULATED", html)
        self.assertIn("真实站验证", html)
        self.assertIn("真实多轮 AI", html)
        self.assertIn("本地日常仿真，不是完整平台", html)
        # probe-needed 绝不能显示成已精确模拟。
        self.assertIn("probe-needed 一律<b>不代表已精确模拟</b>", html)
        self.assertIn("Markdown", html)

    def test_panorama_installs_sdk_simulator_before_author_assets(self):
        """🚨 顺序即契约：实机上作者脚本执行时 window.sdk 已在位。"""
        card = dict(self.CARD, regex_scripts=list(self.CARD["regex_scripts"]) + [
            {"id": -3, "scriptName": "kit", "findRegex": "/{{kit}}/",
             "replaceString": "<script>window.__author_ran=1;</script>"}])
        html = bp.assemble_panorama(card, "mmdsandbox", "t.json")
        sim_idx = html.find("data-preview-sim=&quot;1&quot;")
        hoist_idx = html.find("data-preview-hoisted")
        self.assertGreater(sim_idx, -1, "必须内联模拟器")
        self.assertGreater(hoist_idx, -1, "必须有作者 hoisted 区块")
        self.assertLess(sim_idx, hoist_idx, "模拟器必须在作者 hoisted assets 之前")
        self.assertIn("__MMD_SANDBOX_SIM_CONFIG__", html)
        self.assertIn("__MMD_SANDBOX_SIM__", html)

    def test_sandbox_panorama_has_no_img_onerror_scaffold(self):
        """沙盒 <script> 是一等公民，脚手架绝不能再用 img onerror（官方明令禁止）。"""
        for profile in bp.SANDBOX_PROFILES:
            with self.subTest(profile=profile):
                html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json",
                                            sandbox_profile=profile)
                self.assertNotIn("onerror", html)
        # MMD 旧分支保留 onerror 载体，不受影响。
        self.assertIn("onerror", bp.assemble_panorama(TestPanorama.FOUR, "mmd", "t.json"))

    def test_sandbox_profiles_are_reflected_in_output(self):
        chat = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json", sandbox_profile="chat")
        thin = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json",
                                    sandbox_profile="thin-preview")
        self.assertIn("profile=chat", chat)
        self.assertIn("profile=thin-preview", thin)
        self.assertIn('&quot;profile&quot;: &quot;thin-preview&quot;', thin)
        # thin 下 cache 写操作没有实测依据 → 必须降级标 probe-needed。
        # 定位到 probe-needed **能力桶那一行**（按 data 属性取），不要撞上 Markdown 告警。
        bucket = thin.split('data-preview-bucket="probe-needed">', 1)[1]
        bucket = bucket.split("</div>", 1)[0]
        self.assertIn("cache.set", bucket)
        self.assertIn("cache.remove", bucket)
        # chat 下这两项是 conservative，probe-needed 桶整行都不该存在。
        self.assertNotIn('data-preview-bucket="probe-needed"', chat)
        self.assertIn("cache.set",
                      chat.split('data-preview-bucket="conservative">', 1)[1]
                          .split("</div>", 1)[0])
        self.assertIn("probe-needed 2", thin)
        self.assertIn("probe-needed 0", chat)
        # 非法 profile 回落到 chat，不炸。
        self.assertIn("profile=chat",
                      bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json",
                                           sandbox_profile="nonsense"))

    def test_contract_pins_corrected_sdk_facts(self):
        """契约必须钉住几处易回退的实测真值（都曾被写错过）。"""
        c = bp.load_sandbox_contract()
        # version 是字符串 '1'，不是数字 1。
        self.assertEqual(c["sdk"]["version"], "1")
        self.assertIsInstance(c["sdk"]["version"], str)
        # 只有 4 个能力是异步 Promise，其余同步 void。
        self.assertEqual(sorted(c["sdk"]["asyncCapabilities"]),
                         ["message.edit", "message.send", "save.remove", "save.set"])
        self.assertEqual(c["sdk"]["messageSendReturns"], "Promise<void>")
        # 错误码拼写是 INVALID_ARGS。
        self.assertIn("INVALID_ARGS", c["sdk"]["errorCodes"]["known"])
        self.assertNotIn("INVALID_ARG", c["sdk"]["errorCodes"]["known"])
        # message:unmount 无载荷，不许伪装 4 键。
        self.assertEqual(c["eventPayloads"]["message:unmount"]["shape"], "undefined")
        # ready 无 late replay。
        self.assertEqual(c["events"]["lateReplay"]["notReplayed"], ["ready"])
        self.assertEqual(sorted(c["events"]["lateReplay"]["replayed"]),
                         ["message:done", "message:mount"])

    def test_simulator_source_matches_contract_signatures(self):
        """源码层对撞：模拟器不得把同步能力 Promise 化，version 必须是字符串。"""
        src = bp.load_sandbox_sim_source()
        self.assertIn("version: '1'", src)
        self.assertNotIn("version: 1", src)
        self.assertIn("INVALID_ARGS", src)
        self.assertNotIn("INVALID_ARG'", src)
        # 同步 void 能力走 syncOk/thinThrow，不走 resolved/thinReject。
        self.assertIn("function syncOk", src)
        for capability in ("input.set", "composer.show", "cache.set", "stage.open"):
            with self.subTest(capability=capability):
                self.assertIn("syncOk('%s'" % capability, src)
        # 那 4 个异步能力才允许 resolved/thinReject。
        for capability in ("message.send", "save.set"):
            with self.subTest(capability=capability):
                self.assertIn("thinReject('%s')" % capability, src)
        # 收窄必须先看游标自身（否则桥接层拿错气泡根）。
        self.assertIn("matchesSel(cursor, sel)", src)

    def test_contract_and_accuracy_are_embedded(self):
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        contract = bp.load_sandbox_contract()
        self.assertIn("契约 v%s" % contract["contractVersion"], html)
        self.assertIn("能力 30 项", html)
        for level in ("exact", "conservative", "probe-needed"):
            with self.subTest(level=level):
                self.assertIn('data-preview-accuracy="%s"' % level,
                              html_mod.unescape(html))
        # 冷启动顺序与 payload 形状写进页面，作者一眼能核对。
        self.assertIn("message:new → message:mount → message:done → ready", html)
        self.assertIn("{content,id,role,serverId}", html)

    def test_toolbar_exposes_simulation_controls(self):
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        for label in ("追加 AI", "流式追加", "结束流式", "多轮对话", "切深浅色",
                      "切会话", "平台关舞台", "键盘弹起", "事件日志"):
            with self.subTest(label=label):
                self.assertIn(label, html)
        self.assertIn("__MMD_SANDBOX_SIM__.control", html_mod.unescape(html))

    def test_other_platforms_keep_scaffold_unchanged(self):
        for platform in ("mmd", "st"):
            with self.subTest(platform=platform):
                html = bp.assemble_panorama(TestPanorama.FOUR, platform, "t.json")
                self.assertNotIn("data-chat=", html)
                self.assertNotIn("--chat-accent", html)


class TestMainModes(unittest.TestCase):
    """main() --mode 接线：both 产两文件，单一 mode 产一文件。"""

    def _run_main(self, tmpdir, mode):
        src = os.path.join(tmpdir, "fx.json")
        fixture = json.loads(json.dumps(TestPanorama.FOUR, ensure_ascii=False))
        for script in fixture["regex_scripts"]:
            script.setdefault("id", -1)
        with open(src, "w", encoding="utf-8") as f:
            json.dump(fixture, f, ensure_ascii=False)
        argv = ["build-preview", src, "--platform", "mmd", "--mode", mode]
        old = sys.argv
        sys.argv = argv
        try:
            bp.main()
        finally:
            sys.argv = old
        return (bp._default_output_path(src, "preview", "mmd"),
                bp._default_output_path(src, "panorama", "mmd"))

    def test_both_mode_writes_two_files(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            panels, pano = self._run_main(d, "both")
            self.assertTrue(os.path.exists(panels))
            self.assertTrue(os.path.exists(pano))

    def test_panels_mode_writes_only_panels(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            panels, pano = self._run_main(d, "panels")
            self.assertTrue(os.path.exists(panels))
            self.assertFalse(os.path.exists(pano))

    def test_panorama_mode_writes_only_panorama(self):
        with tempfile.TemporaryDirectory() as d:
            panels, pano = self._run_main(d, "panorama")
            self.assertFalse(os.path.exists(panels))
            self.assertTrue(os.path.exists(pano))

    def test_output_input_uses_sibling_work_directory(self):
        with tempfile.TemporaryDirectory() as d:
            output_dir = os.path.join(d, "output")
            os.makedirs(output_dir)
            panels, pano = self._run_main(output_dir, "both")
            self.assertEqual(os.path.dirname(panels), os.path.join(d, "工作"))
            self.assertEqual(os.path.dirname(pano), os.path.join(d, "工作"))
            self.assertTrue(os.path.exists(panels))
            self.assertTrue(os.path.exists(pano))

    def test_sandbox_platform_choice_writes_both_files(self):
        """--platform mmdsandbox 端到端可跑通，产两份 HTML。"""
        card = json.loads(json.dumps(TestSandboxPanoramaChrome.CARD, ensure_ascii=False))
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "sb.json")
            with open(src, "w", encoding="utf-8") as f:
                json.dump(card, f, ensure_ascii=False)
            old = sys.argv
            sys.argv = ["build-preview", src, "--platform", "mmdsandbox", "--mode", "both"]
            try:
                bp.main()
            finally:
                sys.argv = old
            for kind in ("preview", "panorama"):
                path = bp._default_output_path(src, kind, "mmdsandbox")
                self.assertTrue(os.path.exists(path))
                with open(path, encoding="utf-8") as f:
                    self.assertIn("banner-mmdsandbox", f.read())

    def test_retired_oldmmd_platform_is_rejected_by_argparse(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "x.json")
            with open(src, "w", encoding="utf-8") as f:
                json.dump({"regex_scripts": []}, f)
            old, old_err = sys.argv, sys.stderr
            sys.argv = ["build-preview", src, "--platform", "oldmmd"]
            sys.stderr = io.StringIO()
            try:
                with self.assertRaises(SystemExit) as cm:
                    bp.main()
                self.assertEqual(cm.exception.code, 2)
            finally:
                sys.argv, sys.stderr = old, old_err

    def test_non_output_input_stays_alongside(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(os.path.dirname(bp._default_output_path(
                os.path.join(d, "fx.json"), "preview", "mmd")), os.path.abspath(d))

    def test_fatal_audits_leave_no_output_files(self):
        invalid_objects = (
            {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [], "extra": True},
            {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [
                {"id": -1, "scriptName": "坏正则", "findRegex": "/[z-a]/", "replaceString": ""}
            ]},
            {"pageDepth": 2, "statusbar": "", "beginning": "<x>", "regex_scripts": [
                {"id": -1, "scriptName": "坏点击", "findRegex": "/<x>/",
                 "replaceString": "<button onclick='this.hidden=true'>x</button>"}
            ]},
            {"pageDepth": 2, "statusbar": "<missing>", "beginning": "", "regex_scripts": []},
        )
        for index, obj in enumerate(invalid_objects):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as d:
                output_dir = os.path.join(d, "output")
                os.makedirs(output_dir)
                src = os.path.join(output_dir, "bad.json")
                with open(src, "w", encoding="utf-8") as f:
                    json.dump(obj, f, ensure_ascii=False)
                old = sys.argv
                sys.argv = ["build-preview", src, "--platform", "mmd", "--mode", "both"]
                try:
                    with self.assertRaises(SystemExit) as cm:
                        bp.main()
                finally:
                    sys.argv = old
                self.assertEqual(cm.exception.code, 1)
                work = os.path.join(d, "工作")
                self.assertFalse(os.path.exists(work))
                self.assertFalse(any(name.endswith(".html") for name in os.listdir(output_dir)))
