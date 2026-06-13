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

    def test_script_tag_mmd_warn(self):
        reset()
        v.check_platform_redlines("<script>x</script>", "mmd", "测试")
        self.assertTrue(any("script" in m.lower() for m in v.WARNS))
        self.assertEqual(v.ERRORS, [])

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

    def test_over_30_scripts(self):
        reset()
        scripts = [{"id": -1, "scriptName": str(i), "findRegex": "<x>", "replaceString": "y"} for i in range(31)]
        v.validate_regex({"pageDepth": 2, "statusbar": "<x>", "beginning": "",
                          "regex_scripts": scripts}, "oldmmd")
        self.assertTrue(any("30" in m for m in v.ERRORS))


if __name__ == "__main__":
    unittest.main()
