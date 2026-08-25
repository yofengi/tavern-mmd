#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py 单元测试。运行: python -m unittest test_validate -v"""
import unittest
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

v = importlib.import_module("validate")


def reset():
    v.ERRORS.clear()
    v.WARNS.clear()
    v.OKS.clear()


class TestBOM(unittest.TestCase):
    def test_bom_detected(self):
        reset()
        self.assertTrue(v.check_bom(b"\xef\xbb\xbf{}"))
        self.assertTrue(any("BOM" in m for m in v.ERRORS))

    def test_no_bom(self):
        reset()
        self.assertFalse(v.check_bom(b"{}"))
        self.assertEqual(v.ERRORS, [])


class TestJSON(unittest.TestCase):
    def test_valid_json(self):
        reset()
        obj, _ = v.load_json(b'{"a": 1}')
        self.assertEqual(obj, {"a": 1})
        self.assertEqual(v.ERRORS, [])

    def test_raw_newline_in_string(self):
        reset()
        obj, _ = v.load_json(b'{"a": "line1\nline2"}')
        self.assertIsNone(obj)
        self.assertTrue(any("换行" in m for m in v.ERRORS))

    def test_invalid_utf8_is_error(self):
        reset()
        obj, _ = v.load_json(b'{"a":"\xff"}')
        self.assertIsNone(obj)
        self.assertTrue(any("UTF-8" in m for m in v.ERRORS))


class TestDoubleEscape(unittest.TestCase):
    def test_double_escaped_quotes(self):
        reset()
        s = 'class=\\"box\\" id=\\"a\\" for=\\"b\\" data=\\"c\\" x=\\"d\\" y=\\"e\\"'
        v.check_double_escape(s, "测试")
        self.assertTrue(any("双重转义" in m for m in v.ERRORS))

    def test_clean_html(self):
        reset()
        v.check_double_escape('class="box" id="a"', "测试")
        self.assertEqual(v.ERRORS, [])


class TestPlatformRedlines(unittest.TestCase):
    def test_script_tag_oldmmd_error(self):
        reset()
        v.check_platform_redlines("<script>alert(1)</script>", "oldmmd", "测试")
        self.assertTrue(any("script" in m.lower() for m in v.ERRORS))

    def test_script_tag_mmd_ok(self):
        reset()
        v.check_platform_redlines("<script>x</script>", "mmd", "测试")
        # 当前MMD已确认支持 <script>，应放行（OK），不报错不警告
        self.assertTrue(any("script" in m.lower() for m in v.OKS))
        self.assertEqual(v.ERRORS, [])
        self.assertFalse(any("script" in m.lower() for m in v.WARNS))

    def test_es6_arrow_oldmmd_error(self):
        reset()
        v.check_platform_redlines("var f = x => x+1;", "oldmmd", "测试")
        self.assertTrue(any("ES6" in m for m in v.ERRORS))

    def test_es5_clean(self):
        reset()
        v.check_platform_redlines("var f = function(x){return x;};", "oldmmd", "测试")
        self.assertTrue(any("ES5" in m for m in v.OKS))

    def test_innerHTML_oldmmd_error(self):
        reset()
        v.check_platform_redlines("el.innerHTML = '<b>x</b>';", "oldmmd", "测试")
        self.assertTrue(any("innerHTML" in m for m in v.ERRORS))

    def test_onerror_attr_order_not_false_positive(self):
        reset()
        v.check_onerror_inner_quote('<img onerror="alert(1)" style="display:none">', "mmd", "测试")
        self.assertEqual(v.ERRORS, [])

    def test_single_quoted_onerror_may_contain_double_quotes(self):
        reset()
        v.check_onerror_inner_quote('<img onerror=\'alert("ok")\'>', "mmd", "测试")
        self.assertEqual(v.ERRORS, [])

    def test_double_quoted_onerror_with_inner_quote_errors(self):
        reset()
        v.check_onerror_inner_quote('<img onerror="alert("bad")">', "mmd", "测试")
        self.assertTrue(any("裸双引号" in m for m in v.ERRORS))


class TestEventNewlines(unittest.TestCase):
    def test_multiline_onclick_oldmmd(self):
        reset()
        v.check_interactive_event_newlines('<div onclick="a();\nb()">', "测试", "oldmmd")
        self.assertTrue(any("裸换行" in m for m in v.ERRORS))

    def test_singleline_onclick_ok(self):
        reset()
        v.check_interactive_event_newlines('<div onclick="a();b()">', "测试", "oldmmd")
        self.assertTrue(any("单行" in m for m in v.OKS))

    def test_mmd_canonical_calls_are_allowed(self):
        bodies = (
            "event.stopPropagation()",
            "eval(getElementById('FUNC').dataset.s)",
            "window.__fn&&__fn()",
            "window.__fn && window.__fn()",
        )
        for body in bodies:
            with self.subTest(body=body):
                reset()
                v.check_interactive_event_newlines('<button onclick="%s">' % body, "测试", "mmd")
                self.assertEqual(v.ERRORS, [])
                self.assertTrue(any("干净单一调用" in m for m in v.OKS))

    def test_mmd_unverified_simple_calls_are_rejected(self):
        for body in ("window.__fn(event)", "window.__fn()", "eval(this.dataset.s)"):
            with self.subTest(body=body):
                reset()
                v.check_interactive_event_newlines('<button onclick="%s">' % body, "测试", "mmd")
                self.assertTrue(any("canonical" in m for m in v.ERRORS))

    def test_mmd_multiline_onclick_is_error(self):
        reset()
        v.check_interactive_event_newlines('<button onclick="window.__fn(\nevent)">', "测试", "mmd")
        self.assertTrue(any("裸换行" in m for m in v.ERRORS))

    def test_mmd_eval_direct_code_string_is_error(self):
        reset()
        v.check_interactive_event_newlines("<button onclick=\"eval('window.__bad()')\">", "测试", "mmd")
        self.assertTrue(any("代码字符串" in m for m in v.ERRORS))

    def test_mmd_direct_assignment_is_error(self):
        for body in ("this.hidden=true", "document.body.dataset.x='1'", "window.foo=1"):
            with self.subTest(body=body):
                reset()
                v.check_interactive_event_newlines('<button onclick="%s">' % body, "测试", "mmd")
                self.assertTrue(any("赋值" in m for m in v.ERRORS))

    def test_mmd_multiple_statements_and_code_blocks_are_errors(self):
        for body in ("a();b()", "if(x){a()}"):
            with self.subTest(body=body):
                reset()
                v.check_interactive_event_newlines('<button onclick="%s">' % body, "测试", "mmd")
                self.assertTrue(v.ERRORS)

    def test_dynamic_onclick_assignment_is_not_inline_attribute(self):
        reset()
        source = "<script>el.onclick=function(){el.hidden=true;};</script>"
        v.check_interactive_event_newlines(source, "测试", "mmd")
        self.assertEqual(v.ERRORS, [])
        self.assertFalse(any("stopPropagation" in m for m in v.WARNS))
    def test_mmd_real_onclick_parser_handles_quotes_and_unquoted(self):
        for html in ('<button onclick="window.__fn&&__fn()">',
                     '<button onclick="event.stopPropagation()">',
                     "<button onclick=eval(getElementById('FUNC').dataset.s)>"):
            with self.subTest(html=html):
                reset()
                v.check_interactive_event_newlines(html, "测试", "mmd")
                self.assertEqual(v.ERRORS, [])

    def test_data_onclick_and_script_strings_are_not_inline_attributes(self):
        reset()
        source = ('<div data-onclick="window.bad=1"></div>'
                  '<script>var x=\'<button onclick="window.bad=1">\';</script>')
        v.check_interactive_event_newlines(source, "测试", "mmd")
        self.assertEqual(v.ERRORS, [])

    def test_mmd_sequence_nested_code_string_template_and_arbitrary_call_error(self):
        bodies = ("window.__fn(event),window.__other(event)",
                  "window.__fn(event)", "window.__fn()", "eval(this.dataset.s)",
                  "window.__fn(eval('bad()'))", "window.__fn(`bad()`)",
                  "document.querySelector('#x').click()",
                  "eval(getElementById(x).dataset.s)",
                  "eval(getElementById('FUNC').dataset.x)",
                  "window.__fn&&__other()",
                  "window.__fn&&__fn(),window.__other()")
        for body in bodies:
            with self.subTest(body=body):
                reset()
                v.check_interactive_event_newlines('<button onclick="%s">' % body, "测试", "mmd")
                self.assertTrue(v.ERRORS)


class TestTypeGuess(unittest.TestCase):
    def test_mmd_regex(self):
        self.assertEqual(v.looks_like({"regex_scripts": [], "statusbar": "<x>"}), "regex")

    def test_mmd_regex_missing_statusbar_still_recognized(self):
        self.assertEqual(v.looks_like({"regex_scripts": []}), "regex")

    def test_card(self):
        self.assertEqual(v.looks_like({"spec": "chara_card_v2", "data": {}}), "card")

    def test_worldbook(self):
        self.assertEqual(v.looks_like({"entries": {"0": {}}}), "worldbook")

    def test_local_regex_array(self):
        self.assertEqual(v.looks_like([{"findRegex": "/x/", "replaceString": ""}]), "regex")


class TestCardV2(unittest.TestCase):
    def test_v3_on_mmd_errors(self):
        reset()
        v.validate_card({"spec": "chara_card_v3", "data": {"group_only_greetings": []}}, "mmd")
        self.assertTrue(any("v2" in m for m in v.ERRORS))
        self.assertTrue(any("group_only_greetings" in m for m in v.ERRORS))

    def test_v2_on_mmd_ok(self):
        reset()
        v.validate_card({"spec": "chara_card_v2", "data": {}}, "mmd")
        self.assertFalse(any("v2" in m and "仅识别" in m for m in v.ERRORS))


class TestRegexLimits(unittest.TestCase):
    def _validate_replace_length(self, length, platform="mmd"):
        reset()
        v.validate_regex({"pageDepth": 2, "statusbar": "", "beginning": "",
                          "regex_scripts": [{"id": -1, "scriptName": "t",
                                             "findRegex": "/x/", "replaceString": "x" * length}]}, platform)

    def test_replace_17999_has_no_margin_warning(self):
        self._validate_replace_length(17999)
        self.assertFalse(any("余量不足" in m for m in v.WARNS))
        self.assertFalse(any("replaceString" in m for m in v.ERRORS))

    def test_replace_18000_warns_about_margin(self):
        self._validate_replace_length(18000)
        self.assertTrue(any("余量不足" in m for m in v.WARNS))
        self.assertFalse(any("replaceString" in m for m in v.ERRORS))

    def test_replace_20000_warns_but_does_not_error(self):
        self._validate_replace_length(20000)
        self.assertTrue(any("余量不足" in m for m in v.WARNS))
        self.assertFalse(any("replaceString" in m for m in v.ERRORS))

    def test_replace_20001_is_error(self):
        self._validate_replace_length(20001)
        self.assertTrue(any("20000" in m for m in v.ERRORS))
        self.assertFalse(any("余量不足" in m for m in v.WARNS))

    def test_over_130_scripts(self):
        reset()
        scripts = [{"id": -1, "scriptName": str(i), "findRegex": "/<x>/", "replaceString": "y"} for i in range(131)]
        v.validate_regex({"pageDepth": 2, "statusbar": "<x>", "beginning": "",
                          "regex_scripts": scripts}, "oldmmd")
        self.assertTrue(any("130" in m for m in v.ERRORS))


class TestFindRegexFormat(unittest.TestCase):
    def _validate(self, find_regex, platform="mmd", as_array=False):
        reset()
        script = {"scriptName": "规则", "findRegex": find_regex, "replaceString": "x"}
        obj = [script] if as_array else {
            "pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [script]
        }
        v.validate_regex(obj, platform)

    def test_mmd_bare_literal_is_error(self):
        self._validate("<x>", "mmd")
        self.assertTrue(any("/pattern/flags" in m for m in v.ERRORS))

    def test_oldmmd_bare_literal_is_error(self):
        self._validate("<x>", "oldmmd")
        self.assertTrue(any("/pattern/flags" in m for m in v.ERRORS))

    def test_empty_findregex_is_allowed(self):
        self._validate("", "mmd")
        self.assertFalse(any("/pattern/flags" in m for m in v.ERRORS))

    def test_escaped_slash_and_character_class_slash_parse(self):
        for literal in (r"/a\/b/gi", r"/[/]path/"):
            with self.subTest(literal=literal):
                self._validate(literal)
                self.assertFalse(any("findRegex 非法" in m for m in v.ERRORS))

    def test_missing_delimiter_invalid_flags_and_newline_are_errors(self):
        for literal in ("/unterminated", "/x/q", "/x/gg", "/x/uv", "/a\nb/"):
            with self.subTest(literal=literal):
                self._validate(literal)
                self.assertTrue(any("findRegex 非法" in m for m in v.ERRORS))

    def test_nonstring_nonempty_findregex_is_error(self):
        self._validate(123, "mmd")
        self.assertTrue(any("/pattern/flags 字符串" in m for m in v.ERRORS))

    def test_st_regex_array_keeps_bare_literal_compatibility(self):
        self._validate("<x>", "st", as_array=True)
        self.assertFalse(any("/pattern/flags" in m for m in v.ERRORS))

    def test_mmd_and_oldmmd_reject_top_level_arrays(self):
        for platform in ("mmd", "oldmmd"):
            with self.subTest(platform=platform):
                reset()
                v.validate_regex([{"findRegex": "/x/", "replaceString": "y"}], platform)
                self.assertTrue(any("顶层数组仅适用于 ST" in m for m in v.ERRORS))

    def test_mmd_missing_four_field_is_error(self):
        reset()
        v.validate_regex({"regex_scripts": []}, "mmd")
        self.assertTrue(any("MMD 顶层 keys 必须恰好" in m and "pageDepth" in m
                            for m in v.ERRORS))

    def test_st_array_still_accepted(self):
        reset()
        v.validate_regex([{"findRegex": "x", "replaceString": "y"}], "st")
        self.assertFalse(v.ERRORS)
        self.assertTrue(any("本地酒馆正则数组" in m for m in v.OKS))

    def test_js_named_group_and_property_escape_are_not_rejected(self):
        for literal in (r"/(?<word>\w+)/g", r"/\p{L}+/u"):
            with self.subTest(literal=literal):
                self._validate(literal, "mmd")
                self.assertFalse(any("findRegex 非法" in m for m in v.ERRORS))

    def test_python_named_group_is_rejected_as_non_js(self):
        self._validate(r"/(?P<word>\w+)/", "mmd")
        self.assertTrue(any("Python 专有" in m for m in v.ERRORS))

    def test_unbalanced_parenthesis_is_structural_error(self):
        self._validate(r"/(abc/", "mmd")
        self.assertTrue(any("未闭合" in m for m in v.ERRORS))

    def test_clear_js_syntax_errors_are_rejected(self):
        for literal in (r"/a{2,1}/", r"/[z-a]/", r"/(?<1>a)/"):
            with self.subTest(literal=literal):
                self._validate(literal, "mmd")
                self.assertTrue(any("findRegex 非法" in m for m in v.ERRORS))

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_node_oracle_rejects_node_only_syntax_error(self):
        self._validate(r"/(?<x>a)(?<x>b)/", "mmd")
        self.assertTrue(any("Node JS RegExp SyntaxError" in m for m in v.ERRORS))

    def test_missing_node_warns_and_uses_structure_fallback(self):
        reset()
        v._NODE_REGEX_CACHE.clear()
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": []}
        with mock.patch.object(v.shutil, "which", return_value=None):
            v.validate_regex(obj, "mmd")
        self.assertTrue(any("未经过真实 JS RegExp oracle" in m for m in v.WARNS))
        self.assertFalse(v.ERRORS)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_cli_rejects_clear_js_syntax_errors(self):
        script = os.path.join(os.path.dirname(__file__), "validate.py")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "invalid.json")
            obj = {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [
                {"id": -1, "scriptName": literal, "findRegex": literal, "replaceString": ""}
                for literal in (r"/a{2,1}/", r"/[z-a]/", r"/(?<1>a)/")
            ]}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
            proc = subprocess.run([sys.executable, script, path, "--type", "regex", "--platform", "mmd"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                  encoding="utf-8", errors="replace", check=False)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.count("findRegex 非法"), 3)

    def test_mmd_dict_dangling_marker_not_hidden_by_bare_literal(self):
        reset()
        v.validate_regex({"pageDepth": 2, "statusbar": "<x>", "beginning": "",
                          "regex_scripts": [{"scriptName": "坏规则", "findRegex": "<x>",
                                             "replaceString": "done"}]}, "mmd")
        self.assertTrue(any("findRegex 非法" in m for m in v.ERRORS))
        self.assertTrue(any("悬空标记" in m and "<x>" in m for m in v.ERRORS))


class TestDanglingMarkers(unittest.TestCase):
    def test_statusbar_beginning_marker_without_matching_findregex_is_error(self):
        reset()
        v.validate_regex({"pageDepth": 2,
                          "statusbar": "<css>",
                          "beginning": "正文<missing>",
                          "regex_scripts": [
                              {"id": -1, "scriptName": "样式", "findRegex": "/<css>/", "replaceString": "<style></style>"}
                          ]}, "mmd")
        self.assertTrue(any("悬空标记" in m and "<missing>" in m for m in v.ERRORS))
        self.assertFalse(any("<css>" in m and "悬空标记" in m for m in v.ERRORS))

    def test_html_tags_are_not_treated_as_dangling_markers(self):
        reset()
        v.validate_regex({"pageDepth": 2,
                          "statusbar": "",
                          "beginning": "<div><button>点</button></div>",
                          "regex_scripts": []}, "mmd")
        self.assertFalse(any("悬空标记" in m for m in v.ERRORS))
    def test_dangling_checks_each_occurrence_start_end_and_replacement_markers(self):
        reset()
        v.validate_regex({"pageDepth": 2, "statusbar": "<x><x></x>", "beginning": "",
                          "regex_scripts": []}, "mmd")
        dangling = [m for m in v.ERRORS if "悬空标记" in m]
        self.assertEqual(len(dangling), 3)
        self.assertTrue(any("</x>" in m for m in dangling))

        reset()
        v.validate_regex({"pageDepth": 2, "statusbar": "<x>", "beginning": "",
                          "regex_scripts": [{"findRegex": "/<x>/", "replaceString": "<new>"}]}, "mmd")
        self.assertTrue(any("<new>" in m and "悬空标记" in m for m in v.ERRORS))

    def test_unsupported_js_regex_skips_dangling_judgment(self):
        reset()
        v.validate_regex({"pageDepth": 2, "statusbar": "<x>", "beginning": "",
                          "regex_scripts": [{"scriptName": "属性", "findRegex": r"/\p{L}+/u",
                                             "replaceString": ""}]}, "mmd")
        self.assertFalse(any("悬空标记" in m for m in v.ERRORS))
        self.assertTrue(any("审计已跳过" in m for m in v.WARNS))


class TestMmdStrictSchema(unittest.TestCase):
    def test_exact_four_field_schema_passes(self):
        reset()
        obj = {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [
            {"id": -1, "scriptName": "规则", "findRegex": "/x/", "replaceString": "y"}
        ]}
        v.validate_regex(obj, "mmd")
        self.assertFalse(any("keys 必须恰好" in m or "必须为" in m or "id 必须" in m
                             for m in v.ERRORS))

    def test_top_level_keys_are_exact(self):
        for obj in (
            {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [], "extra": True},
            {"pageDepth": 2, "statusbar": "", "regex_scripts": []},
        ):
            with self.subTest(obj=obj):
                reset()
                v.validate_regex(obj, "mmd")
                self.assertTrue(any("MMD 顶层 keys 必须恰好" in m for m in v.ERRORS))

    def test_top_level_types_are_strict(self):
        cases = (("pageDepth", "2"), ("pageDepth", True), ("statusbar", None),
                 ("beginning", []), ("regex_scripts", {}))
        for field, value in cases:
            with self.subTest(field=field, value=value):
                reset()
                obj = {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": []}
                obj[field] = value
                v.validate_regex(obj, "mmd")
                self.assertTrue(any(field in m and "必须为" in m for m in v.ERRORS))

    def test_each_script_has_exact_keys_id_and_types(self):
        bad_scripts = (
            {"id": -1, "scriptName": "x", "findRegex": "/x/", "replaceString": "y", "extra": 1},
            {"id": 0, "scriptName": "x", "findRegex": "/x/", "replaceString": "y"},
            {"id": -1, "scriptName": 1, "findRegex": "/x/", "replaceString": "y"},
            {"id": -1, "scriptName": "x", "findRegex": "/x/"},
        )
        for script in bad_scripts:
            with self.subTest(script=script):
                reset()
                obj = {"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [script]}
                v.validate_regex(obj, "mmd")
                self.assertTrue(v.ERRORS)
                self.assertTrue(any("regex_scripts[0]" in m for m in v.ERRORS))

    def test_st_array_does_not_require_mmd_schema(self):
        reset()
        v.validate_regex([{"findRegex": "x", "replaceString": "y", "extra": True}], "st")
        self.assertFalse(v.ERRORS)


class TestRegexNonString(unittest.TestCase):
    def test_none_findregex_and_replacestring_no_crash(self):
        reset()
        v.validate_regex({"regex_scripts": [
            {"scriptName": "x", "findRegex": None, "replaceString": None}
        ], "statusbar": "<s>"}, "mmd")
        self.assertFalse(any("> 1000" in m or "> 20000" in m for m in v.ERRORS))

    def test_numeric_replacestring_no_crash(self):
        reset()
        v.validate_regex({"regex_scripts": [
            {"scriptName": "y", "replaceString": 123}
        ], "statusbar": ""}, "mmd")
        self.assertTrue(any("非字符串" in m for m in v.WARNS))

    def test_regex_scripts_must_be_array(self):
        reset()
        v.validate_regex({"regex_scripts": None, "statusbar": "<s>", "beginning": ""}, "mmd")
        self.assertTrue(any("regex_scripts 必须为 array" in m for m in v.ERRORS))


class TestWorldbookArrayForm(unittest.TestCase):
    def test_looks_like_recognizes_array_entries(self):
        self.assertEqual(
            v.looks_like({"entries": [{"comment": "x", "content": "y"}]}),
            "worldbook")

    def test_validate_worldbook_array_entries(self):
        reset()
        v.validate_worldbook({"entries": [
            {"comment": "蓝灯", "content": "<style>.a{}</style>", "constant": True}
        ]}, "st")
        self.assertFalse(any("entries 应为对象" in m for m in v.ERRORS))

    def test_worldbook_script_oldmmd_error(self):
        reset()
        v.validate_worldbook({"entries": {
            "0": {"comment": "脚本", "content": "<script>x</script>", "constant": True}
        }}, "oldmmd")
        self.assertTrue(any("script" in m.lower() for m in v.ERRORS))

    def test_card_book_script_oldmmd_error(self):
        reset()
        v.validate_card({"spec": "chara_card_v2", "data": {
            "character_book": {"entries": [
                {"comment": "脚本", "content": "<script>x</script>"}
            ]}
        }}, "oldmmd")
        self.assertTrue(any("script" in m.lower() for m in v.ERRORS))


class TestNullFieldsNoCrash(unittest.TestCase):
    def test_card_null_data_no_crash(self):
        reset()
        v.validate_card({"spec": "chara_card_v2", "data": None}, "mmd")
        # 不崩溃即可（data=null 被容错为 {}）
        self.assertTrue(True)

    def test_worldbook_nonstring_content_no_crash(self):
        reset()
        v.validate_worldbook({"entries": [
            {"comment": "坏条目", "content": None, "constant": True}
        ]}, "st")
        self.assertTrue(True)

    def test_card_entry_nonstring_content_no_crash(self):
        reset()
        v.validate_card({"spec": "chara_card_v2", "data": {
            "character_book": {"entries": [{"comment": "x", "content": 123}]}
        }}, "mmd")
        self.assertTrue(True)


TITLE_20 = "这是一个刚好二十个字的世界书条目的标题啊"    # 恰好 20 字，合规边界
TITLE_21 = "这是一个整整二十一个字的世界书条目超长标题"    # 21 字，超限


class TestCommentLength(unittest.TestCase):
    def test_worldbook_over_length_title_error_on_mmd(self):
        reset()
        v.validate_worldbook({"entries": {
            "0": {"comment": TITLE_21, "content": "正文", "constant": True}
        }}, "mmd")
        self.assertTrue(any("超过 MMD 上限" in m for m in v.ERRORS))

    def test_worldbook_over_length_title_error_on_oldmmd(self):
        reset()
        v.validate_worldbook({"entries": {
            "0": {"comment": TITLE_21, "content": "正文", "constant": True}
        }}, "oldmmd")
        self.assertTrue(any("超过 MMD 上限" in m for m in v.ERRORS))

    def test_exactly_twenty_chars_passes(self):
        reset()
        v.validate_worldbook({"entries": {
            "0": {"comment": TITLE_20, "content": "正文", "constant": True}
        }}, "mmd")
        self.assertFalse(any("上限" in m for m in v.ERRORS))

    def test_st_platform_has_no_title_limit(self):
        reset()
        v.validate_worldbook({"entries": {
            "0": {"comment": TITLE_21, "content": "正文", "constant": True}
        }}, "st")
        self.assertFalse(any("上限" in m for m in v.ERRORS))

    def test_card_book_over_length_title_error(self):
        reset()
        v.validate_card({"spec": "chara_card_v2", "data": {
            "character_book": {"entries": [{"comment": TITLE_21, "content": "正文"}]}
        }}, "mmd")
        self.assertTrue(any("超过 MMD 上限" in m for m in v.ERRORS))

    def test_nonstring_comment_no_crash(self):
        reset()
        v.validate_worldbook({"entries": {
            "0": {"comment": None, "content": "正文", "constant": True}
        }}, "mmd")
        self.assertFalse(any("上限" in m for m in v.ERRORS))


if __name__ == "__main__":
    unittest.main()
