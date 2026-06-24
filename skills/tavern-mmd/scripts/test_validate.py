#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate.py 单元测试。运行: python -m unittest test_validate -v"""
import unittest
import importlib

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
    def test_replace_over_20000(self):
        reset()
        big = "x" * 20001
        v.validate_regex({"pageDepth": 2, "statusbar": "<x>", "beginning": "",
                          "regex_scripts": [{"id": -1, "scriptName": "t",
                                             "findRegex": "<x>", "replaceString": big}]}, "oldmmd")
        self.assertTrue(any("20000" in m for m in v.ERRORS))

    def test_over_130_scripts(self):
        reset()
        scripts = [{"id": -1, "scriptName": str(i), "findRegex": "<x>", "replaceString": "y"} for i in range(131)]
        v.validate_regex({"pageDepth": 2, "statusbar": "<x>", "beginning": "",
                          "regex_scripts": scripts}, "oldmmd")
        self.assertTrue(any("130" in m for m in v.ERRORS))


class TestDanglingMarkers(unittest.TestCase):
    def test_statusbar_beginning_marker_without_matching_findregex_is_error(self):
        reset()
        v.validate_regex({"pageDepth": 2,
                          "statusbar": "<css>",
                          "beginning": "正文<missing>",
                          "regex_scripts": [
                              {"id": -1, "scriptName": "样式", "findRegex": "<css>", "replaceString": "<style></style>"}
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
        self.assertTrue(any("regex_scripts 应为数组" in m for m in v.ERRORS))


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


if __name__ == "__main__":
    unittest.main()


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
