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
    def test_script_tag_mmd_ok(self):
        reset()
        v.check_platform_redlines("<script>x</script>", "mmd", "测试")
        # 当前MMD已确认支持 <script>，应放行（OK），不报错不警告
        self.assertTrue(any("script" in m.lower() for m in v.OKS))
        self.assertEqual(v.ERRORS, [])
        self.assertFalse(any("script" in m.lower() for m in v.WARNS))

    def test_script_tag_sandbox_is_first_class(self):
        reset()
        v.check_platform_redlines("<script>x</script>", "mmdsandbox", "测试")
        self.assertTrue(any("一等公民" in m for m in v.OKS))
        self.assertEqual(v.ERRORS, [])

    def test_es6_is_never_rejected_on_surviving_platforms(self):
        # ES6 判罚只属于已退役的 ES5-only 旧平台；在役两个 MMD 平台全面支持。
        for platform in ("mmd", "mmdsandbox"):
            with self.subTest(platform=platform):
                reset()
                v.check_platform_redlines("const f = x => `${x}`;", platform, "测试")
                self.assertEqual(v.ERRORS, [])
                self.assertFalse(any("ES6" in m for m in v.WARNS))

    def test_innerHTML_is_warn_not_error(self):
        for platform in ("mmd", "mmdsandbox"):
            with self.subTest(platform=platform):
                reset()
                v.check_platform_redlines("el.innerHTML = '<b>x</b>';", platform, "测试")
                self.assertTrue(any("innerHTML" in m for m in v.WARNS))
                self.assertEqual(v.ERRORS, [])

    def test_csstext_is_warn_not_error(self):
        reset()
        v.check_platform_redlines("el.style.cssText = 'color:red';", "mmd", "测试")
        self.assertTrue(any("cssText" in m for m in v.WARNS))
        self.assertEqual(v.ERRORS, [])

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
    def test_sandbox_is_not_subject_to_mmd_onclick_purity(self):
        # 沙盒模式普通标签 onclick 可用；每条气泡的绑定官方要求写在 message:mount 里。
        reset()
        v.check_interactive_event_newlines('<div onclick="a();\nb()">', "测试", "mmdsandbox")
        self.assertEqual(v.ERRORS, [])
        self.assertEqual(v.OKS, [])

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
                          "regex_scripts": scripts}, "mmd")
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

    def test_mmd_rejects_top_level_arrays(self):
        reset()
        v.validate_regex([{"findRegex": "/x/", "replaceString": "y"}], "mmd")
        self.assertTrue(any("顶层数组仅适用于 ST" in m for m in v.ERRORS))

    def test_sandbox_rejects_top_level_arrays(self):
        reset()
        v.validate_regex([{"findRegex": "{{x}}", "replaceString": "y"}], "mmdsandbox")
        self.assertTrue(any("顶层必须是对象" in m for m in v.ERRORS))

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

    def test_worldbook_script_is_not_an_error_on_surviving_platforms(self):
        # <script> 在 mmd 与沙盒模式都支持，不再是红线。
        for platform in ("mmd", "mmdsandbox"):
            with self.subTest(platform=platform):
                reset()
                v.validate_worldbook({"entries": {
                    "0": {"comment": "脚本", "content": "<script>x</script>", "constant": True}
                }}, platform)
                self.assertEqual(v.ERRORS, [])

    def test_card_book_script_is_not_an_error_on_mmd(self):
        reset()
        v.validate_card({"spec": "chara_card_v2", "data": {
            "character_book": {"entries": [
                {"comment": "脚本", "content": "<script>x</script>"}
            ]}
        }}, "mmd")
        self.assertEqual(v.ERRORS, [])


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

    def test_over_length_title_is_warn_on_sandbox_but_error_on_mmd(self):
        """锁定决策 D8：沙盒模式保留 20 字限制但降级为 WARN（官方校验不查该项）。"""
        entries = {"0": {"comment": TITLE_21, "content": "正文", "constant": True}}
        reset()
        v.validate_worldbook({"entries": dict(entries)}, "mmdsandbox")
        self.assertTrue(any("超过 MMD 上限" in m for m in v.WARNS))
        self.assertFalse(any("超过 MMD 上限" in m for m in v.ERRORS))

        reset()
        v.validate_worldbook({"entries": dict(entries)}, "mmd")
        self.assertTrue(any("超过 MMD 上限" in m for m in v.ERRORS))
        self.assertFalse(any("超过 MMD 上限" in m for m in v.WARNS))

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


def sandbox_card(**overrides):
    """一张干净的沙盒模式导入卡（顶层恰好 6 键），用 overrides 定点破坏。"""
    obj = {
        "chatVersion": 1,
        "pageDepth": 2,
        "statusbar": "{{hud}}",
        "beginning": "开场白 {{panel}}",
        "personality": "<角色设定 名字：阿岚>\n正文\n</角色设定>",
        "regex_scripts": [
            {"id": -1, "scriptName": "hud", "findRegex": "{{hud}}",
             "replaceString": "<div class='hud'>状态</div>"},
            {"id": -2, "scriptName": "panel", "findRegex": "{{panel}}",
             "replaceString": "<div class='p'>面板</div>"},
        ],
    }
    obj.update(overrides)
    return obj


def run_sandbox(**overrides):
    reset()
    # 走一遍真实 JSON 往返，让 <\/script> 这类官方要求的转义还原成运行时形态
    v.validate_regex(json.loads(json.dumps(sandbox_card(**overrides))), "mmdsandbox")


def sandbox_rule(**overrides):
    rule = {"id": -1, "scriptName": "kit", "findRegex": "{{kit}}", "replaceString": "x"}
    rule.update(overrides)
    return rule


class TestSandboxCleanCard(unittest.TestCase):
    def test_clean_card_is_silent(self):
        run_sandbox()
        self.assertEqual(v.ERRORS, [])
        self.assertEqual(v.WARNS, [])

    def test_script_only_rule_needs_no_trigger_reference(self):
        """只放 <script> 的规则匹配式故意谁都不引用，不该报"永不出现"。"""
        run_sandbox(regex_scripts=[sandbox_rule(
            findRegex="{{card-kit}}",
            replaceString="<script>sdk.on('ready',function(){sdk.debug.log('go');});<\\/script>")])
        self.assertEqual(v.ERRORS, [])
        self.assertFalse(any("永远不会出现" in m for m in v.WARNS))


class TestSandboxTopLevel(unittest.TestCase):
    def test_chat_version_must_be_one(self):
        for value in (0, 2, "0", True, None):
            with self.subTest(value=value):
                run_sandbox(chatVersion=value)
                self.assertTrue(any("chatVersion 必须是 1" in m for m in v.ERRORS))

    def test_missing_chat_version_is_error(self):
        obj = sandbox_card()
        del obj["chatVersion"]
        reset()
        v.validate_regex(obj, "mmdsandbox")
        self.assertTrue(any("缺 chatVersion" in m for m in v.ERRORS))

    def test_chat_version_one_accepts_number_and_string(self):
        for value in (1, 1.0, "1"):
            with self.subTest(value=value):
                run_sandbox(chatVersion=value)
                self.assertFalse(any("chatVersion" in m for m in v.ERRORS))

    def test_forbidden_top_level_keys_are_errors(self):
        for key in v.SANDBOX_FORBIDDEN_TOP_LEVEL_KEYS:
            with self.subTest(key=key):
                run_sandbox(**{key: {}})
                self.assertTrue(any("不能有顶层 %s" % key in m for m in v.ERRORS))

    def test_unknown_top_level_key_is_warn(self):
        run_sandbox(mystery=1)
        self.assertTrue(any("未知键" in m and "mystery" in m for m in v.WARNS))
        self.assertEqual(v.ERRORS, [])

    def test_page_depth_other_than_two_is_warn(self):
        run_sandbox(pageDepth=1)
        self.assertTrue(any("pageDepth" in m for m in v.WARNS))
        self.assertEqual(v.ERRORS, [])

    def test_length_limits(self):
        cases = (("statusbar", v.SANDBOX_MAX_STATUSBAR),
                 ("beginning", v.SANDBOX_MAX_BEGINNING),
                 ("personality", v.SANDBOX_MAX_PERSONALITY))
        for field, limit in cases:
            with self.subTest(field=field, limit=limit):
                run_sandbox(**{field: "x" * limit})
                self.assertFalse(any(field in m and "超过上限" in m for m in v.ERRORS))
                run_sandbox(**{field: "x" * (limit + 1)})
                self.assertTrue(any(field in m and "超过上限 %d" % limit in m
                                    for m in v.ERRORS))

    def test_over_130_rules_is_error(self):
        rules = [sandbox_rule(id=-(i + 1), scriptName=str(i), findRegex="{{r%d}}" % i,
                              replaceString="<style>.a{}</style>")
                 for i in range(v.SANDBOX_MAX_RULES + 1)]
        run_sandbox(regex_scripts=rules)
        self.assertTrue(any("超过上限 %d 条" % v.SANDBOX_MAX_RULES in m for m in v.ERRORS))

    def test_no_deliverable_is_error(self):
        run_sandbox(regex_scripts=[], personality="  ")
        self.assertTrue(any("没有可交付物" in m for m in v.ERRORS))

    def test_regex_scripts_must_be_array(self):
        run_sandbox(regex_scripts={})
        self.assertTrue(any("regex_scripts 必须为 array" in m for m in v.ERRORS))


class TestSandboxRules(unittest.TestCase):
    def test_id_must_be_negative(self):
        for bad_id in (0, 1, -0.0, "-1", True, None):
            with self.subTest(bad_id=bad_id):
                run_sandbox(statusbar="{{kit}}", regex_scripts=[sandbox_rule(id=bad_id)])
                self.assertTrue(any("id 必须是**负数**" in m for m in v.ERRORS))

    def test_negative_id_passes(self):
        run_sandbox(statusbar="{{kit}}", regex_scripts=[sandbox_rule(id=-7)])
        self.assertFalse(any("id" in m for m in v.ERRORS))

    def test_missing_rule_field_is_error(self):
        rule = sandbox_rule()
        del rule["replaceString"]
        run_sandbox(statusbar="{{kit}}", regex_scripts=[rule])
        self.assertTrue(any("缺字段 replaceString" in m for m in v.ERRORS))

    def test_extra_rule_field_is_warn(self):
        run_sandbox(statusbar="{{kit}}", regex_scripts=[sandbox_rule(disabled=False)])
        self.assertTrue(any("多余字段 disabled" in m for m in v.WARNS))
        self.assertEqual(v.ERRORS, [])

    def test_script_name_blank_and_over_length(self):
        run_sandbox(statusbar="{{kit}}", regex_scripts=[sandbox_rule(scriptName="   ")])
        self.assertTrue(any("scriptName 必须为非空字符串" in m for m in v.ERRORS))
        run_sandbox(statusbar="{{kit}}",
                    regex_scripts=[sandbox_rule(scriptName="名" * (v.SANDBOX_MAX_SCRIPT_NAME + 1))])
        self.assertTrue(any("scriptName 共 %d 字" % (v.SANDBOX_MAX_SCRIPT_NAME + 1) in m
                            for m in v.ERRORS))

    def test_duplicate_script_name_is_warn(self):
        run_sandbox(statusbar="{{a}}{{b}}", regex_scripts=[
            sandbox_rule(id=-1, scriptName="同名", findRegex="{{a}}", replaceString="<b>1</b>"),
            sandbox_rule(id=-2, scriptName="同名", findRegex="{{b}}", replaceString="<b>2</b>"),
        ])
        self.assertTrue(any("重名" in m for m in v.WARNS))
        self.assertEqual(v.ERRORS, [])

    def test_find_regex_blank_and_over_length(self):
        run_sandbox(regex_scripts=[sandbox_rule(findRegex="  ")])
        self.assertTrue(any("findRegex 必须为非空字符串" in m for m in v.ERRORS))
        long_fr = "x" * (v.SANDBOX_MAX_FIND_REGEX + 1)
        run_sandbox(regex_scripts=[sandbox_rule(findRegex=long_fr)])
        self.assertTrue(any("findRegex 共 %d 字" % len(long_fr) in m for m in v.ERRORS))

    def test_replace_string_over_length(self):
        limit = v.SANDBOX_MAX_REPLACE_STRING
        run_sandbox(statusbar="{{kit}}", regex_scripts=[sandbox_rule(replaceString="x" * limit)])
        self.assertFalse(any("replaceString 共" in m for m in v.ERRORS))
        run_sandbox(statusbar="{{kit}}",
                    regex_scripts=[sandbox_rule(replaceString="x" * (limit + 1))])
        self.assertTrue(any("replaceString 共 %d 字" % (limit + 1) in m for m in v.ERRORS))


class TestSandboxPatternForm(unittest.TestCase):
    """锁定决策 D7：沙盒模式的 findRegex 不强制 slash literal，字面量是官方首选。"""

    def test_bare_literal_is_accepted(self):
        for literal in ("{{hud}}", "【图鉴】", "状态面板"):
            with self.subTest(literal=literal):
                run_sandbox(statusbar=literal,
                            regex_scripts=[sandbox_rule(findRegex=literal)])
                self.assertEqual(v.ERRORS, [])

    def test_slash_form_is_also_accepted(self):
        run_sandbox(statusbar="血量：10",
                    regex_scripts=[sandbox_rule(findRegex=r"/血量[:：]\s*(\d+)/",
                                                replaceString="<b>$1</b>")])
        self.assertEqual(v.ERRORS, [])

    def test_bad_slash_regex_is_error(self):
        for literal in (r"/([/", r"/a{2,1}/", r"/[z-a]/"):
            with self.subTest(literal=literal):
                run_sandbox(regex_scripts=[sandbox_rule(findRegex=literal)])
                self.assertTrue(any("整条规则会被静默丢弃" in m for m in v.ERRORS))

    def test_duplicate_literal_is_error(self):
        run_sandbox(statusbar="{{hud}}", regex_scripts=[
            sandbox_rule(id=-1, scriptName="a", findRegex="{{hud}}", replaceString="<b>1</b>"),
            sandbox_rule(id=-2, scriptName="b", findRegex="{{hud}}", replaceString="<b>2</b>"),
        ])
        self.assertTrue(any("永远匹配不到" in m for m in v.ERRORS))

    def test_duplicate_slash_form_is_not_deduplicated(self):
        """只有字面量会被前一条吃掉；正则形态不做重复判罚。"""
        run_sandbox(statusbar="血量：1", regex_scripts=[
            sandbox_rule(id=-1, scriptName="a", findRegex=r"/血量[:：]\s*(\d+)/",
                         replaceString="<b>$1</b>"),
            sandbox_rule(id=-2, scriptName="b", findRegex=r"/血量[:：]\s*(\d+)/",
                         replaceString="<i>$1</i>"),
        ])
        self.assertFalse(any("永远匹配不到" in m for m in v.ERRORS))

    def test_classify_pattern_strips_whitespace_and_backticks(self):
        self.assertEqual(v.classify_sandbox_pattern("  `{{hud}}`  "), ("literal", "{{hud}}"))
        self.assertEqual(v.classify_sandbox_pattern("/a/g")[0], "regex")
        self.assertEqual(v.classify_sandbox_pattern("   ")[0], "empty")
        # d/v 不在官方 flags 集合 gimsuy 内 → 整串按字面量处理，不是坏正则
        self.assertEqual(v.classify_sandbox_pattern("/a/d")[0], "literal")

    def test_unreferenced_visible_literal_is_warn(self):
        run_sandbox(regex_scripts=[sandbox_rule(findRegex="{{nowhere}}",
                                                replaceString="<div>看得见</div>")])
        self.assertTrue(any("永远不会出现" in m for m in v.WARNS))

    def test_chained_trigger_via_other_replace_string_is_accepted(self):
        run_sandbox(statusbar="{{hud}}", regex_scripts=[
            sandbox_rule(id=-1, scriptName="hud", findRegex="{{hud}}",
                         replaceString="<div>{{inner}}</div>"),
            sandbox_rule(id=-2, scriptName="inner", findRegex="{{inner}}",
                         replaceString="<b>链式</b>"),
        ])
        self.assertFalse(any("永远不会出现" in m for m in v.WARNS))

    def test_find_regex_html_tag_and_reserved_word_are_warns(self):
        run_sandbox(statusbar="<div>", regex_scripts=[sandbox_rule(findRegex="<div>")])
        self.assertTrue(any("含 HTML 标签" in m for m in v.WARNS))
        run_sandbox(statusbar="css", regex_scripts=[sandbox_rule(findRegex="css")])
        self.assertTrue(any("保留字" in m for m in v.WARNS))

    def test_reserved_word_matches_whole_word_only(self):
        run_sandbox(statusbar="htmlish", regex_scripts=[sandbox_rule(findRegex="htmlish")])
        self.assertFalse(any("保留字" in m for m in v.WARNS))


class TestSandboxSdkNames(unittest.TestCase):
    def test_unknown_capability_is_error(self):
        for ref in ("sdk.stage.opn()", "sdk.inpt.set('x')", "sdk.save.list()"):
            with self.subTest(ref=ref):
                reset()
                v.check_sandbox_sdk_names(ref, "测试")
                self.assertTrue(any("没有这个能力" in m for m in v.ERRORS))

    def test_all_known_capabilities_pass(self):
        reset()
        for name in sorted(v.SANDBOX_SDK_CAPABILITIES):
            v.check_sandbox_sdk_names("sdk.%s" % name, "测试")
        self.assertEqual(v.ERRORS, [])

    def test_unknown_event_is_error(self):
        reset()
        v.check_sandbox_sdk_names("sdk.on('msg:new', f)", "测试")
        self.assertTrue(any("不在 12 个合法事件名内" in m for m in v.ERRORS))

    def test_all_known_events_pass(self):
        reset()
        for event in sorted(v.SANDBOX_SDK_EVENTS):
            v.check_sandbox_sdk_names("sdk.on('%s', f)" % event, "测试")
        self.assertEqual(v.ERRORS, [])

    def test_once_and_off_are_errors_with_replay_hint(self):
        for name in ("once", "off"):
            with self.subTest(name=name):
                reset()
                v.check_sandbox_sdk_names("sdk.%s('ready', f)" % name, "测试")
                self.assertTrue(any("只有 sdk.on" in m for m in v.ERRORS))
        reset()
        v.check_sandbox_sdk_names("sdk.once('ready', f)", "测试")
        self.assertTrue(any("补发给后来的订阅者" in m for m in v.ERRORS))

    def test_role_and_user_fields(self):
        reset()
        v.check_sandbox_sdk_names("sdk.role.get().name + sdk.user.get().nickname", "测试")
        self.assertEqual(v.ERRORS, [])
        reset()
        v.check_sandbox_sdk_names("sdk.role.get().nickname", "测试")
        self.assertTrue(any("sdk.role.get().nickname 不存在" in m for m in v.ERRORS))
        reset()
        v.check_sandbox_sdk_names("sdk.user.get().name", "测试")
        self.assertTrue(any("sdk.user.get().name 不存在" in m for m in v.ERRORS))

    def test_sdk_names_are_only_checked_on_sandbox(self):
        run_sandbox(statusbar="{{kit}}", regex_scripts=[
            sandbox_rule(replaceString="<script>sdk.stage.opn();<\\/script>")])
        self.assertTrue(any("没有这个能力" in m for m in v.ERRORS))
        # 同样内容在 mmd 平台不做 SDK 名核对
        reset()
        v.validate_regex({"pageDepth": 2, "statusbar": "", "beginning": "", "regex_scripts": [
            {"id": -1, "scriptName": "k", "findRegex": "/x/",
             "replaceString": "<script>sdk.stage.opn();</script>"}]}, "mmd")
        self.assertFalse(any("没有这个能力" in m for m in v.ERRORS))


class TestSandboxRedlines(unittest.TestCase):
    def test_igniter_onerror_is_error(self):
        bodies = ("eval(document.getElementById('s').dataset.s)",
                  "new Function(this.dataset.code)()",
                  "document.body.innerHTML=this.dataset.h")
        for body in bodies:
            with self.subTest(body=body):
                reset()
                v.check_sandbox_redlines('<img src=x onerror="%s">' % body, "测试")
                self.assertTrue(any("点火器" in m for m in v.ERRORS))

    def test_genuine_image_fallback_is_not_flagged(self):
        bodies = ("this.style.display='none'", "this.src='/fallback.png'",
                  "this.remove()", "this.onerror=null")
        for body in bodies:
            with self.subTest(body=body):
                reset()
                v.check_sandbox_redlines('<img src="a.png" onerror="%s">' % body, "测试")
                self.assertEqual(v.ERRORS, [])

    def test_onerror_on_non_img_tag_is_not_the_igniter_rule(self):
        reset()
        v.check_sandbox_redlines('<video onerror="eval(x)"></video>', "测试")
        self.assertEqual(v.ERRORS, [])

    def test_teapot_writing_is_error(self):
        for source in ("window.teapotBoot()", "teapotEngine = {}"):
            with self.subTest(source=source):
                reset()
                v.check_sandbox_redlines("<script>%s<\\/script>" % source, "测试")
                self.assertTrue(any("teapot" in m for m in v.ERRORS))

    def test_redline_message_points_to_script_only_rule(self):
        reset()
        v.check_sandbox_redlines('<img src=x onerror="eval(a)">', "测试")
        self.assertTrue(any("只放 <script>" in m for m in v.ERRORS))


class TestSandboxContentWarnings(unittest.TestCase):
    def test_author_data_attribute_is_warn(self):
        reset()
        v.check_sandbox_content_warnings('<div data-hp="10">x</div>', "测试")
        self.assertTrue(any("data-hp" in m and "净化" in m for m in v.WARNS))

    def test_platform_data_attributes_are_not_flagged(self):
        reset()
        v.check_sandbox_content_warnings('<div data-chat="root" data-slot="left"></div>', "测试")
        self.assertFalse(any("净化" in m for m in v.WARNS))

    def test_forbidden_tags_are_warn(self):
        for tag in v.SANDBOX_FORBIDDEN_TAGS:
            with self.subTest(tag=tag):
                reset()
                v.check_sandbox_content_warnings("<%s></%s>" % (tag, tag), "测试")
                self.assertTrue(any("白名单" in m for m in v.WARNS))

    def test_global_css_is_warn(self):
        for css in ("<style>*{margin:0}</style>", "<style>body{color:red}</style>",
                    "<style>html{font-size:16px}</style>", "<style>:root{--x:1}</style>"):
            with self.subTest(css=css):
                reset()
                v.check_sandbox_content_warnings(css, "测试")
                self.assertTrue(any("全局 CSS" in m for m in v.WARNS))

    def test_scoped_css_is_not_flagged(self):
        reset()
        v.check_sandbox_content_warnings(
            '<style>[data-chat="root"] .hud{color:red}</style>', "测试")
        self.assertFalse(any("全局 CSS" in m for m in v.WARNS))

    def test_markdown_code_block_indent_is_warn(self):
        reset()
        v.check_sandbox_content_warnings("正文\n    <div>缩进四空格</div>", "测试")
        self.assertTrue(any("代码块" in m for m in v.WARNS))

    def test_two_space_indent_is_not_flagged(self):
        reset()
        v.check_sandbox_content_warnings("正文\n  <div>两空格</div>", "测试")
        self.assertFalse(any("代码块" in m for m in v.WARNS))

    def test_subscribe_inside_mount_callback_is_warn(self):
        reset()
        v.check_sandbox_content_warnings(
            "sdk.on('message:mount', function(el){ sdk.on('ready', f); })", "测试")
        self.assertTrue(any("订阅要写在**脚本体**里" in m for m in v.WARNS))

    def test_self_reply_loop_is_warn(self):
        reset()
        v.check_sandbox_content_warnings(
            "sdk.on('message:done', function(m){ sdk.message.send('再来'); })", "测试")
        self.assertTrue(any("自问自答死循环" in m for m in v.WARNS))

    def test_message_body_placeholder_trap_is_warn(self):
        reset()
        v.check_sandbox_content_warnings(
            "sdk.on('message:mount', function(el){"
            "var b=el.querySelector('[data-chat=\"message-body\"]');"
            "sdk.message.send(b.textContent); })", "测试")
        self.assertTrue(any("消息生成中" in m for m in v.WARNS))


class TestSandboxCardDeliverable(unittest.TestCase):
    def test_v2_card_under_sandbox_is_warn_not_error(self):
        """锁定决策 D6：沙盒模式不走 chara_card_v2 / PNG 整卡。"""
        reset()
        v.validate_card({"spec": "chara_card_v2", "data": {}}, "mmdsandbox")
        self.assertEqual(v.ERRORS, [])
        self.assertTrue(any("6 键" in m and "persona" in m for m in v.WARNS))

    def test_v3_card_under_sandbox_does_not_trigger_v2_enforcement(self):
        reset()
        v.validate_card({"spec": "chara_card_v3",
                         "data": {"group_only_greetings": []}}, "mmdsandbox")
        self.assertFalse(any("仅识别 chara_card_v2" in m for m in v.ERRORS))
        self.assertFalse(any("group_only_greetings" in m for m in v.ERRORS))


class TestSandboxCLI(unittest.TestCase):
    def test_platform_choices_and_default(self):
        script = os.path.join(os.path.dirname(__file__), "validate.py")
        proc = subprocess.run([sys.executable, script, "--help"],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", check=False)
        self.assertIn("mmdsandbox", proc.stdout)
        self.assertNotIn("oldmmd", proc.stdout)

    def test_cli_rejects_wrong_chat_version(self):
        script = os.path.join(os.path.dirname(__file__), "validate.py")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sandbox.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sandbox_card(chatVersion=0), f, ensure_ascii=False)
            proc = subprocess.run(
                [sys.executable, script, path, "--type", "regex", "--platform", "mmdsandbox"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", check=False)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("chatVersion 必须是 1", proc.stdout)

    def test_cli_accepts_clean_sandbox_card(self):
        script = os.path.join(os.path.dirname(__file__), "validate.py")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sandbox.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sandbox_card(), f, ensure_ascii=False)
            proc = subprocess.run(
                [sys.executable, script, path, "--type", "regex", "--platform", "mmdsandbox"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", check=False)
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
