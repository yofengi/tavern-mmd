#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build-preview.py 单元测试。运行: python -m unittest test_build_preview -v"""
import unittest
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
        """测试脚手架在被测内容外，不应被当成被测产物加平台角标。"""
        for platform in ("mmd", "mmdsandbox"):
            with self.subTest(platform=platform):
                html = bp.assemble_panorama(self.FOUR, platform, "t.json")
                self.assertIn("data-pano-scaffold", html)
                self.assertIn("data-pano-runtime-scaffold", html)
                runtime_idx = html.find("data-pano-runtime-scaffold")
                around = html[max(0, runtime_idx - 240):runtime_idx]
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

    def test_bare_literal_marker_renders_and_is_not_flagged(self):
        """D7 回归闸：纯字面量标记是官方首选写法，必须正常替换且不报非法。"""
        obj = self.card("正文 {{hud}} 尾巴", [
            {"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
             "replaceString": "<div class='my-hud'>血量</div>"}])
        rendered = bp.apply_regex_pipeline(obj, "mmdsandbox")
        self.assertIn("<div class='my-hud'>血量</div>", rendered)
        self.assertNotIn("{{hud}}", rendered)
        self.assertEqual(bp.find_invalid_findregexes(obj, "mmdsandbox"), [])
        self.assertEqual(bp.find_unsupported_preview_regexes(obj, "mmdsandbox"), [])
        html = bp.assemble_preview(obj, "mmdsandbox", "t.json")
        self.assertNotIn("ERROR 非法 findRegex", html)
        self.assertIn("my-hud", html)

    def test_literal_metachars_are_escaped_and_replacement_is_global(self):
        obj = self.card("axb a.b a.b", [
            {"id": -1, "scriptName": "点", "findRegex": "a.b", "replaceString": "<b>X</b>"}])
        # 元字符被转义：a.b 不匹配 axb；且字面量全文每处都换
        self.assertEqual(bp.apply_regex_pipeline(obj, "mmdsandbox"), "axb <b>X</b> <b>X</b>")

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
            {"id": -1, "scriptName": "卡名-style", "findRegex": "{{卡名-style}}",
             "replaceString": "<style>.my-hud{color:red}</style>"},
            {"id": -2, "scriptName": "卡名-kit", "findRegex": "{{卡名-kit}}",
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
            {"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
             "replaceString": "<style>.a{color:red}</style><div class='my-hud'>栏</div>"}])
        rendered = bp.apply_regex_pipeline(obj, "mmdsandbox")
        self.assertIn("<div class='my-hud'>栏</div>", rendered)
        self.assertNotIn("<style>", rendered)
        self.assertIn("<style>.a{color:red}</style>", bp.collect_sandbox_assets(obj))

    def test_svg_children_are_not_reported_as_dangling_markers(self):
        """svg 及 path/circle/rect/line/text 在沙盒白名单内（§5.2），
        但通用 HTML_TAGS 不含它们 → 必须不被误判成悬空标记。"""
        obj = self.card("{{图}}", [
            {"id": -1, "scriptName": "图", "findRegex": "{{图}}",
             "replaceString": "<svg viewBox='0 0 10 10'><circle r='4'></circle>"
                              "<path d='M0 0'></path></svg>"}])
        self.assertEqual(bp.find_dangling_markers(obj, "mmdsandbox"), [])
        self.assertEqual(bp.fatal_preview_findings(obj, "mmdsandbox")["dangling"], [])

    def test_real_dangling_marker_outside_svg_still_reported(self):
        obj = self.card("正文<missing>", [])
        self.assertIn("<missing>", bp.find_dangling_markers(obj, "mmdsandbox"))

    def test_mmd_still_rejects_bare_literal(self):
        """不得削弱当前MMD：裸字面量在 /mmd 仍是结构错误。"""
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
                   {"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
                    "replaceString": "<button onclick=\"tap()\">点</button>"}]}
        self.assertEqual(bp.find_invalid_onclicks(obj, "mmdsandbox"), [])
        self.assertEqual(bp.fatal_preview_findings(obj, "mmdsandbox")["onclick"], [])

    def test_svg_onclick_and_author_data_attr_are_warned(self):
        content = ('<svg viewBox="0 0 10 10"><circle onclick="tap()" r="4"></circle></svg>'
                   '<div data-hp="80">血量</div>')
        kinds = [k for k, _ in bp.find_sandbox_sanitized_attrs(content)]
        self.assertIn("svg-onclick", kinds)
        self.assertIn("author-data-attr", kinds)
        rows = bp._onclick_audit_html(content, "mmdsandbox")
        self.assertIn("svg 内的 onclick 会被沙盒净化删除", rows)
        self.assertIn("作者自写 data-* 会被沙盒净化删除", rows)

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

    CARD = {"chatVersion": 1, "pageDepth": 2, "statusbar": "{{hud}}",
            "beginning": "正文 {{panel}}", "personality": "",
            "regex_scripts": [
                {"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
                 "replaceString": "<div class='my-hud'>功能栏</div>"},
                {"id": -2, "scriptName": "panel", "findRegex": "{{panel}}",
                 "replaceString": "<div class='my-panel'>面板</div>"},
            ]}

    def test_panorama_carries_data_chat_hooks(self):
        """断言属性形态（前导空格），避免被 SANDBOX_CHROME_CSS 里的选择器文本蒙过。"""
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        for hook in ("root", "header", "header-title", "messages", "list",
                     "message-frame", "message", "message-body",
                     "author-stage", "composer", "input", "send"):
            with self.subTest(hook=hook):
                self.assertIn(" data-chat=&quot;%s&quot;" % hook, html)
        for slot in ("statusbar", "header-extra"):
            with self.subTest(slot=slot):
                self.assertIn(" data-slot=&quot;%s&quot;" % slot, html)
        self.assertIn(" data-from=&quot;ai&quot;", html)
        self.assertIn(" data-from=&quot;user&quot;", html)
        self.assertIn(" data-theme=&quot;light&quot;", html)
        self.assertIn(" data-msg-id=&quot;pano-", html)

    def test_panorama_defines_all_ten_chat_variables(self):
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        for var in ("--chat-bg", "--chat-surface", "--chat-text", "--chat-text-muted",
                    "--chat-border", "--chat-accent", "--chat-bubble-user-bg",
                    "--chat-bubble-ai-bg", "--chat-bubble-text", "--chat-viewport-height"):
            with self.subTest(var=var):
                self.assertIn(var, html)

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

    def test_panorama_states_what_is_not_simulated(self):
        html = bp.assemble_panorama(self.CARD, "mmdsandbox", "t.json")
        self.assertIn("未模拟", html)
        self.assertIn("官方 SDK", html)

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
