#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build-preview.py 单元测试。运行: python -m unittest test_build_preview -v"""
import unittest
import html as html_mod
import importlib
import io
import json
import os
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
        first, status, _ = bp.split_preview_panels(rendered)
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

    def test_panorama_has_fixed_input_bar_and_send_button(self):
        html = bp.assemble_panorama(self.FOUR, "mmd", "t.json")
        self.assertIn("pano-input-bar", html)
        self.assertIn("position:fixed", html)        # 输入栏固定
        self.assertIn("bottom:0", html)
        self.assertIn("pano-send", html)             # 发送按钮
        self.assertIn("uni-textarea-textarea", html)  # 主输入框（与选项回填选择器一致）

    def test_panorama_has_mmd_chat_runtime_scaffold(self):
        html = bp.assemble_panorama(self.FOUR, "mmd", "t.json")
        for marker in ("topTabbar", "chat chat-bg pano-chat", "chat-body",
                       "data-message-role=&quot;user&quot;", "data-message-role=&quot;ai&quot;",
                       "content right", "content left"):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)
        self.assertIn("#/pages/chat/chat", html)
        self.assertIn("data-pano-runtime-scaffold", html)

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

    def test_bare_literal_is_error_and_never_renders(self):
        """🚨 实机推翻原 D7：裸字面量在真机上**不生效**（探针 {{probe}} 完全不触发，
        改 /{{probe}}/ 立即生效）。预览必须判 ERROR 且**绝不替换**——否则作者在预览里
        看到内容出现、上真机什么都没有，这是最坏的一种谎。"""
        obj = self.card("正文 {{hud}} 尾巴", [
            {"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
             "replaceString": "<div id='must-not-render'>血量</div>"}])
        invalid = bp.find_invalid_findregexes(obj, "mmdsandbox")
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0][0], "hud")
        self.assertIn("实机裸字面量未生效", invalid[0][2])
        self.assertIn("worker 源码", invalid[0][2])
        # 不替换：触发串原样留在正文里。
        rendered = bp.apply_regex_pipeline(obj, "mmdsandbox")
        self.assertIn("{{hud}}", rendered)
        self.assertNotIn("must-not-render", rendered)
        html = bp.assemble_preview(obj, "mmdsandbox", "t.json")
        self.assertIn("ERROR 非法 findRegex", html)
        self.assertTrue(bp.fatal_preview_findings(obj, "mmdsandbox")["findRegex"])

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

    def test_worker_literal_branch_stays_explainable(self):
        """worker 源码确有 literal 分支，内部函数要能说明它；但它不是交付判据。"""
        self.assertEqual(bp.classify_sandbox_pattern("{{hud}}")[:2], ("literal", "{{hud}}"))
        self.assertEqual(bp.classify_sandbox_pattern("a.b")[:2], ("literal", "a.b"))
        # 交付门禁与 worker 分类分开：前者对字面量判错，后者仍照实描述 worker。
        self.assertIn("实机裸字面量未生效", bp.sandbox_pattern_delivery_error("{{hud}}"))
        self.assertIsNone(bp.sandbox_pattern_delivery_error("/{{hud}}/"))
        self.assertEqual(bp.sandbox_delivery_regex("/{{hud}}/"), "/{{hud}}/g")
        self.assertIsNone(bp.sandbox_delivery_regex("{{hud}}"))

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

    # 匹配式一律 slash 形态：实机裸字面量不生效（事实卡 §8.21），预览判 ERROR。
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
        css = bp.SANDBOX_CHROME_CSS
        self.assertIn('height:var(--chat-viewport-height)', css)
        self.assertIn('max-width:100%;overflow:hidden auto;background-color:var(--chat-bg)', css)
        self.assertIn('[data-chat="composer"]{position:static;', css)
        self.assertIn('left:auto;right:auto;bottom:auto', css)
        self.assertNotIn('[data-slot="statusbar"]{position:sticky', css)
        self.assertNotIn('[data-slot="statusbar"]{flex-shrink:0', css)
        self.assertIn('white-space:pre-line;opacity:.9', css)
        self.assertIn('.pano-compose-icon,.pano-send{flex:0 0 auto;', css)
        self.assertIn('min-width:0;height:calc(60 * var(--rpx));', css)
        self.assertIn('padding:0;border:0;border-radius:0;background:transparent', css)
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
        """防回归：14 个实测设计令牌必须全部注入产物。

        引用实现里的 SANDBOX_DESIGN_TOKENS 而非另抄一份清单，避免测试与实现漂移。
        曾漏注入后 5 个（手册也漏记），导致作者写 var(--chat-input-bg) 在预览里
        解析不到、真机却正常 —— 会误导作者去修不存在的 bug。
        """
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        chrome = html_mod.unescape(html)
        self.assertEqual(len(bp.SANDBOX_DESIGN_TOKENS), 14)
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
        dark = chrome.split('[data-chat="root"][data-theme="dark"]{', 1)[1].split("}", 1)[0]
        parsed = dict(kv.split(":", 1) for kv in
                      (p.strip() for p in dark.replace("\n", "").split(";")) if kv)
        self.assertEqual(parsed, bp.SANDBOX_DARK_TOKEN_VALUES)
        # 实测：两个气泡背景与页面背景同色，预览不得再把它们画成分离的。
        self.assertEqual(parsed["--chat-bg"], "#17181a")
        self.assertEqual(parsed["--chat-bubble-user-bg"], parsed["--chat-bg"])
        self.assertEqual(parsed["--chat-bubble-ai-bg"], parsed["--chat-bg"])
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
        dark = chrome.split('[data-chat="root"][data-theme="dark"]{', 1)[1].split("}", 1)[0]
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
        dark = chrome.split('[data-chat="root"][data-theme="dark"]{', 1)[1].split("}", 1)[0]
        for var in ("--chat-input-bg", "--chat-input-text", "--chat-shortcut-text",
                    "--chat-more-item-bg", "--chat-share-pick-bg"):
            with self.subTest(var=var):
                self.assertIn("%s:" % var, dark)

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
