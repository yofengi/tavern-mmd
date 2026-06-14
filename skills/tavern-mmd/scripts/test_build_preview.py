#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build-preview.py 单元测试。运行: python -m unittest test_build_preview -v"""
import unittest
import importlib

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
    def test_oldmmd_marker_css_injected_into_srcdoc(self):
        # oldmmd 把 <script> 变成 .mmd-stripped 元素，其 CSS 必须随片段进 iframe
        obj = {"regex_scripts": [
            {"scriptName": "S", "replaceString": "<script>var x=1</script><div>hi</div>"},
        ]}
        html = bp.assemble_html(bp.extract_fragments(obj), "oldmmd", "t.json")
        import re
        src = re.search(r'srcdoc="([^"]*)"', html).group(1)
        # srcdoc(子文档)里必须自带 .mmd-stripped 规则，否则红框标记无样式
        self.assertIn(".mmd-stripped", src)


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
