#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_sbk.py 的单元测试。

    python -m unittest test_build_sbk -v

每条校验规则都有正例（不该报）与反例（该报）。断言里的节号对应 `资料/基座事实卡.md`。
"""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_sbk as B


def asset_group_text(names):
    base = Path(__file__).resolve().parent / "sbk"
    return "\n".join((base / n).read_text(encoding="utf-8") for n in names if (base / n).is_file())


def diag_of(fn, text, **kw):
    """跑单个校验器，返回 (errors, warns)。"""
    d = B.Diag()
    fn(text, d, "T", **kw)
    return d.errors, d.warns


class TestStripJsComments(unittest.TestCase):
    def test_removes_line_and_block(self):
        out = B.strip_js_comments("var a=1; // hi\n/* block\nmore */\nvar b=2;")
        self.assertNotIn("hi", out)
        self.assertNotIn("block", out)
        self.assertIn("var a=1;", out)
        self.assertIn("var b=2;", out)

    def test_keeps_url_in_string(self):
        # 字符串里的 // 不是注释
        src = 'var u = "https://x.example/a";'
        self.assertIn("https://x.example/a", B.strip_js_comments(src))

    def test_keeps_comment_like_in_template(self):
        src = 'var t = `a // b /* c */ d`;'
        out = B.strip_js_comments(src)
        self.assertIn("a // b /* c */ d", out)

    def test_keeps_regex_literal_with_slashes(self):
        # /\/*/ 里的 /* 不是块注释起点
        src = 'var r = /\\/*/g; var n = 1;'
        out = B.strip_js_comments(src)
        self.assertIn("var n = 1;", out)

    def test_division_not_treated_as_regex(self):
        src = 'var x = a / b; var y = c / d; var z = 3;'
        out = B.strip_js_comments(src)
        self.assertIn("var z = 3;", out)

    def test_real_assets_stay_valid_after_strip(self):
        """每个声明模块剥注释后仍是合法 JS，且含 script 包装不超过固定安全预算。"""
        adir = Path(__file__).resolve().parent / "sbk"
        if not adir.is_dir():
            self.skipTest("sbk/ 资源目录不存在")
        if not shutil.which("node"):
            self.skipTest("未装 node")
        for name in B.ASSET_ORDER:
            p = adir / name
            with self.subTest(asset=name):
                self.assertTrue(p.is_file(), "声明的资源文件不存在：%s" % name)
                stripped = B.strip_js_comments(p.read_text(encoding="utf-8"))
                d = B.Diag()
                self.assertTrue(B.node_check(stripped, d, name),
                                "%s 剥注释后语法无效: %s" % (name, d.errors))
                self.assertLessEqual(len(stripped) + B.WRAPPER_OVERHEAD, B.MAX_SOURCE_RULE,
                                     "%s 单模块超过 %d，必须继续按完整 IIFE 拆分"
                                     % (name, B.MAX_SOURCE_RULE))


class TestSplitModuleContracts(unittest.TestCase):
    """拆分模块必须是完整、唯一、可独立装箱的经典脚本单元。"""

    EXPECTED_CLAIMS = {
        "core.js": "core",
        "core-store.js": "core-store",
        "core-boot.js": "core-boot",
        "theme.js": "theme",
        "theme-panel.js": "theme-panel",
        "protocol.js": "protocol",
        "hud.js": "hud",
        "hud-render.js": "hud-render",
        "ui.js": "ui",
        "ui-panel.js": "ui-panel",
        "ui-nav.js": "ui-nav",
        "ui-icon.js": "ui-icon",
        "ui-fan.js": "ui-fan",
        "ui-dock.js": "ui-dock",
        "ui-bubble.js": "ui-bubble",
        "ui-inject.js": "ui-inject",
        "ui-codex.js": "ui-codex",
        "ui-map.js": "ui-map",
        "ui-stage.js": "ui-stage",
    }

    def setUp(self):
        self.adir = Path(__file__).resolve().parent / "sbk"

    def test_declared_modules_are_complete_iifes(self):
        for name in B.ASSET_ORDER:
            with self.subTest(asset=name):
                p = self.adir / name
                self.assertTrue(p.is_file(), "缺模块 %s" % name)
                code = B.strip_js_comments(p.read_text(encoding="utf-8")).strip()
                self.assertRegex(code, r"^\(function\s*\(W\)\s*\{", "%s 不是完整 IIFE 开头" % name)
                self.assertRegex(code, r"\}\)\(typeof window !== 'undefined' \? window : globalThis\);$",
                                 "%s 不是完整经典脚本 IIFE 结尾" % name)

    def test_claim_names_are_unique_and_expected(self):
        got = {}
        for name in B.ASSET_ORDER:
            src = (self.adir / name).read_text(encoding="utf-8")
            claims = re.findall(r"(?:SBK\.)?claim\('([^']+)'\)", src)
            # core.js 同时用内部 claim('core') 启动 bridge；其余模块直接 SBK.claim。
            expected = self.EXPECTED_CLAIMS[name]
            self.assertIn(expected, claims, "%s 缺 claim(%r)：%s" % (name, expected, claims))
            got[name] = expected
        self.assertEqual(len(set(got.values())), len(got), "模块 claim 名重复会让后装模块静默短路")

    def test_runtime_boot_claim_still_exists(self):
        src = asset_group_text(("core.js", "core-store.js", "core-boot.js"))
        self.assertRegex(src, r"claim\('boot'\)", "SBK.boot 必须保留独立运行时幂等哨兵")


class TestStripCssComments(unittest.TestCase):
    def test_removes_comments_keeps_rules(self):
        out = B.strip_css_comments("/* c */\n.a{color:red}\n\n/* d */.b{top:0}")
        self.assertNotIn("/*", out)
        self.assertIn(".a{color:red}", out)
        self.assertIn(".b{top:0}", out)

    def test_keeps_url_content(self):
        src = '.a{background:url("data:image/png;base64,AA//BB")}'
        self.assertIn("AA//BB", B.strip_css_comments(src))


class TestClassifyPattern(unittest.TestCase):
    """事实卡 §5.1 worker p() 的复刻。"""

    def test_slash_form(self):
        self.assertEqual(B.classify_pattern("/abc/i"), ("slash", "abc", "ig"))

    def test_auto_adds_g_flag(self):
        self.assertIn("g", B.classify_pattern("/abc/")[2])

    def test_literal_form(self):
        kind, body, _ = B.classify_pattern("{{probe}}")
        self.assertEqual(kind, "literal")
        self.assertEqual(body, "{{probe}}")

    def test_backticks_stripped(self):
        self.assertEqual(B.classify_pattern("`/abc/`")[0], "slash")

    def test_empty(self):
        self.assertEqual(B.classify_pattern("   ")[0], "empty")


class TestMatchesEmpty(unittest.TestCase):
    """事实卡 §5.2：匹配空串 → empty-match → 整条规则被撤销。"""

    def test_negative_lookahead_is_degenerate_not_empty_match(self):
        """/(?!)/ 恒【失败】，不是匹配空串——两者成因不同，但都必须拦。

        按 worker 源码它一次都不匹配，因此严格说不会触发 empty-match 回滚；
        plan.md 2.1 仍禁用它，故 zero_width_hazard 归类为 degenerate 并按 ERROR 处理。
        """
        self.assertFalse(B.matches_empty("/(?!)/"))
        self.assertEqual(B.zero_width_hazard("/(?!)/")[0], "degenerate")

    def test_hazard_classifies_empty_match(self):
        self.assertEqual(B.zero_width_hazard("/a*/")[0], "empty-match")

    def test_hazard_none_for_safe_marker(self):
        self.assertIsNone(B.zero_width_hazard("/\\{\\{sbk-css\\}\\}/"))

    def test_star_quantifier_is_empty_match(self):
        self.assertTrue(B.matches_empty("/a*/"))

    def test_optional_group_is_empty_match(self):
        self.assertTrue(B.matches_empty("/(foo)?/"))

    def test_literal_marker_is_safe(self):
        self.assertFalse(B.matches_empty("/\\{\\{sbk-css\\}\\}/"))

    def test_plus_quantifier_is_safe(self):
        self.assertFalse(B.matches_empty("/a+/"))

    def test_block_pattern_is_safe(self):
        self.assertFalse(B.matches_empty(r"/\[状态\]([\s\S]*?)\[\/状态\]/"))


class TestSlashForm(unittest.TestCase):
    """findRegex 形态：裸字面量实机生效（卡 64304 A/B，2026-08-30）→ 只 WARN 建议统一
    slash；空值仍 ERROR。"""

    def test_slash_ok(self):
        d = B.Diag()
        B.check_slash_form({"findRegex": "/\\{\\{hud\\}\\}/"}, d, "T")
        self.assertEqual(d.errors, [])
        self.assertEqual(d.warns, [])

    def test_bare_literal_is_warn_not_error(self):
        d = B.Diag()
        B.check_slash_form({"findRegex": "{{hud}}"}, d, "T")
        self.assertEqual(d.errors, [])            # 实机生效，不再判 ERROR
        self.assertEqual(len(d.warns), 1)
        self.assertIn("slash", d.warns[0])

    def test_empty_is_error(self):
        d = B.Diag()
        B.check_slash_form({"findRegex": ""}, d, "T")
        self.assertEqual(len(d.errors), 1)


class TestLengths(unittest.TestCase):
    """事实卡 §6：UI 显示值保守 WARN／源码观察值外保守 ERROR。"""

    def _rule(self, name="n", find="/x/", repl="r"):
        return {"scriptName": name, "findRegex": find, "replaceString": repl}

    def test_all_within_ui_limits_is_clean(self):
        e, w = [], []
        d = B.Diag()
        B.check_lengths(self._rule("sbk-css", "/x/", "y"), d, "T")
        self.assertEqual((d.errors, d.warns), ([], []))

    def test_script_name_20_boundary(self):
        # 20 = 编辑器 UI 上限，恰好 20 不告警，21 告警
        d = B.Diag()
        B.check_lengths(self._rule(name="a" * 20), d, "T")
        self.assertEqual(d.warns, [])
        d = B.Diag()
        B.check_lengths(self._rule(name="a" * 21), d, "T")
        self.assertEqual(len(d.warns), 1)
        self.assertEqual(d.errors, [])

    def test_script_name_200_hard_limit(self):
        d = B.Diag()
        B.check_lengths(self._rule(name="a" * 200), d, "T")
        self.assertEqual(d.errors, [])
        d = B.Diag()
        B.check_lengths(self._rule(name="a" * 201), d, "T")
        self.assertEqual(len(d.errors), 1)

    def test_find_regex_1000_warn_4096_error(self):
        d = B.Diag()
        B.check_lengths(self._rule(find="/" + "a" * 1000 + "/"), d, "T")
        self.assertEqual(len(d.warns), 1)
        self.assertEqual(d.errors, [])
        d = B.Diag()
        B.check_lengths(self._rule(find="a" * 4097), d, "T")
        self.assertEqual(len(d.errors), 1)

    def test_replace_string_20000_warn_100000_error(self):
        d = B.Diag()
        B.check_lengths(self._rule(repl="a" * 20001), d, "T")
        self.assertEqual(len(d.warns), 1)
        self.assertIn("20000", d.warns[0])
        self.assertEqual(d.errors, [])
        d = B.Diag()
        B.check_lengths(self._rule(repl="a" * 100001), d, "T")
        self.assertEqual(len(d.errors), 1)

    def test_constants_match_fact_card(self):
        # 逐字取自 var Us={beginning:4e3,statusbar:200,imageUrl:2048,
        #                  name:200,regex:4096,content:1e5,regexList:130}
        self.assertEqual(B.HARD, {"beginning": 4000, "statusbar": 200, "imageUrl": 2048,
                                  "name": 200, "regex": 4096, "content": 100000,
                                  "regexList": 130})
        self.assertEqual(B.UI_SOFT, {"name": 20, "regex": 1000, "content": 20000})


class TestBudget(unittest.TestCase):
    """事实卡 §5.2：budget = max(262144, 输入长度 × 4)，超限整条规则回滚。"""

    def test_floor_is_262144(self):
        self.assertEqual(B.BUDGET_FLOOR, 262144)

    def test_small_rule_clean(self):
        d = B.Diag()
        m = B.estimate_budget({"findRegex": "/\\{\\{hud\\}\\}/", "replaceString": "<div></div>"},
                              10, 1, d, "T")
        self.assertEqual((d.errors, d.warns), ([], []))
        self.assertEqual(m["budget"], 262144)

    def test_budget_scales_with_input(self):
        d = B.Diag()
        m = B.estimate_budget({"findRegex": "/\\{\\{a\\}\\}/", "replaceString": "x"},
                              100000, 1, d, "T")
        self.assertEqual(m["budget"], 400000)   # 100000 × 4 > 262144

    def test_replacement_alone_over_budget(self):
        d = B.Diag()
        B.estimate_budget({"findRegex": "/\\{\\{a\\}\\}/", "replaceString": "x" * 300000},
                          10, 1, d, "T")
        self.assertTrue(any("replacement-alone" in e for e in d.errors))

    def test_volume_over_budget(self):
        d = B.Diag()
        B.estimate_budget({"findRegex": "/\\{\\{a\\}\\}/", "replaceString": "x" * 30000},
                          10, 50, d, "T")
        self.assertTrue(any("volume" in e for e in d.errors))

    def test_half_budget_warns(self):
        d = B.Diag()
        B.estimate_budget({"findRegex": "/\\{\\{a\\}\\}/", "replaceString": "x" * 140000},
                          10, 1, d, "T")
        self.assertEqual(d.errors, [])
        self.assertTrue(any("一半" in w for w in d.warns))

    def test_empty_match_is_error(self):
        d = B.Diag()
        B.estimate_budget({"findRegex": "/a*/", "replaceString": "x"}, 10, 1, d, "T")
        self.assertTrue(any("empty-match" in e for e in d.errors))

    def test_degenerate_never_match_is_error(self):
        # /(?!)/ 归类 degenerate（plan.md 2.1 禁用），文案指向「用字面标记」
        d = B.Diag()
        B.estimate_budget({"findRegex": "/(?!)/", "replaceString": "x"}, 10, 1, d, "T")
        self.assertTrue(any("(?!)" in e for e in d.errors))


class TestModuleSyntax(unittest.TestCase):
    """事实卡 §3：内联脚本按经典脚本执行，import 必报错。"""

    def test_iife_is_clean(self):
        e, w = diag_of(B.check_module_syntax, "(function(W){'use strict';})(window);")
        self.assertEqual(e, [])

    def test_import_statement_is_error(self):
        e, _ = diag_of(B.check_module_syntax, "import x from 'y';")
        self.assertEqual(len(e), 1)

    def test_dynamic_import_is_error(self):
        e, _ = diag_of(B.check_module_syntax, "import('./m.js');")
        self.assertEqual(len(e), 1)

    def test_export_is_error(self):
        e, _ = diag_of(B.check_module_syntax, "export const a = 1;")
        self.assertEqual(len(e), 1)

    def test_word_important_not_flagged(self):
        # 不能把 "important" / "exports" 之类误判
        e, _ = diag_of(B.check_module_syntax, "var s = 'color:red !important';\nvar exports2 = 1;")
        self.assertEqual(e, [])


class TestCsp(unittest.TestCase):
    """事实卡 §2 CSP 边界。"""

    def test_https_image_is_allowed(self):
        # img-src https: → 图片外链允许，不要误报
        e, w = diag_of(B.check_csp, '<img src="https://r2.aitchat.org/a.jpg">')
        self.assertEqual(e, [])
        self.assertEqual(w, [])

    def test_external_stylesheet_link_is_error(self):
        e, _ = diag_of(B.check_csp, '<link rel="stylesheet" href="https://x/a.css">')
        self.assertEqual(len(e), 1)

    def test_at_import_is_error(self):
        e, _ = diag_of(B.check_csp, "@import url('https://x/a.css');")
        self.assertEqual(len(e), 1)

    def test_external_font_is_error(self):
        e, _ = diag_of(B.check_csp, "@font-face{font-family:X;src:url('https://x/a.woff2')}")
        self.assertEqual(len(e), 1)

    def test_external_fetch_is_warn(self):
        e, w = diag_of(B.check_csp, "fetch('https://api.example/x')")
        self.assertEqual(e, [])
        self.assertEqual(len(w), 1)

    def test_iframe_is_error(self):
        e, _ = diag_of(B.check_csp, '<iframe src="a"></iframe>')
        self.assertEqual(len(e), 1)

    def test_form_is_error(self):
        e, _ = diag_of(B.check_csp, "<form></form>")
        self.assertEqual(len(e), 1)

    def test_inline_style_is_allowed(self):
        e, w = diag_of(B.check_csp, '<div style="color:red"></div><style>.a{top:0}</style>')
        self.assertEqual(e, [])


class TestSanitize(unittest.TestCase):
    """事实卡 §5.5 净化行为。"""

    def test_author_data_attr_is_error(self):
        # 实测 data-mine → null
        e, _ = diag_of(B.check_sanitize, '<div data-mine="1"></div>')
        self.assertEqual(len(e), 1)
        self.assertIn("data-mine", e[0])

    def test_set_attribute_data_is_error(self):
        e, _ = diag_of(B.check_sanitize, "el.setAttribute('data-x','1')")
        self.assertEqual(len(e), 1)

    def test_reading_platform_data_attr_is_clean(self):
        # 平台自己的 data-chat 由 Vue 创建，从未进净化器；作为选择器读它合法
        e, w = diag_of(B.check_sanitize, "document.querySelector('[data-chat=\"root\"]')")
        self.assertEqual(e, [])

    def test_aria_and_role_are_warn(self):
        # ALLOW_ARIA_ATTR:!1 → aria-*/role 被删
        e, w = diag_of(B.check_sanitize, '<div role="button" aria-label="x"></div>')
        self.assertEqual(e, [])
        self.assertEqual(len(w), 1)
        self.assertIn("aria-label", w[0])
        self.assertIn("role", w[0])

    def test_bracket_gt_no_space_is_error(self):
        # SAFE_FOR_XML：属性值含 ]> → 整条属性被删
        e, _ = diag_of(B.check_sanitize, '<b onclick="if(a[0]>1)f()">x</b>')
        self.assertEqual(len(e), 1)
        self.assertIn("]>", e[0])

    def test_bracket_gt_with_space_is_clean(self):
        # 实测 title="a[0] > 1"（有空格）完整保留 → 只拦无空格的危险形态
        e, w = diag_of(B.check_sanitize, '<b title="a[0] > 1">x</b>')
        self.assertEqual(e, [])

    def test_html_comment_close_in_attr_is_error(self):
        e, _ = diag_of(B.check_sanitize, '<b title="x-->y">z</b>')
        self.assertEqual(len(e), 1)

    def test_svg_on_handler_is_error(self):
        # 实测 <circle onclick> STRIPPED
        e, _ = diag_of(B.check_sanitize, '<svg><circle onclick="f()"/></svg>')
        self.assertEqual(len(e), 1)
        self.assertIn("SVG", e[0])

    def test_html_on_handlers_are_clean(self):
        # 实测 onclick / onmouseenter 均 KEPT → 不要误报
        e, w = diag_of(B.check_sanitize,
                       '<b onclick="f()" onmouseenter="g()">x</b><input onchange="h()">')
        self.assertEqual(e, [])
        self.assertEqual(w, [])

    def test_backtick_wrapped_html_is_warn(self):
        # §5.4 反引号里的 HTML 会原样成文本
        e, w = diag_of(B.check_sanitize, "说明：`<div class=\"a\">x</div>` 是这样写的")
        self.assertEqual(e, [])
        self.assertEqual(len(w), 1)
        self.assertIn("反引号", w[0])


class TestTags(unittest.TestCase):
    """事实卡 §5.4 worker 白名单 ∩ DOMPurify。"""

    def test_whitelisted_tags_clean(self):
        e, w = diag_of(B.check_tags, "<div><span><b>x</b></span><button>y</button></div>")
        self.assertEqual((e, w), ([], []))

    def test_non_whitelisted_tag_warns(self):
        e, w = diag_of(B.check_tags, "<section>x</section>")
        self.assertEqual(len(w), 1)
        self.assertIn("section", w[0])

    def test_user_tag_warns_due_to_dompurify(self):
        # user 在 worker 白名单但 DOMPurify 默认白名单不含它
        e, w = diag_of(B.check_tags, "<user>x</user>")
        self.assertEqual(len(w), 1)

    def test_script_and_style_bodies_ignored(self):
        # <style>/<script> 装卡时被抽走，不参与标签检查
        e, w = diag_of(B.check_tags, "<script>var a='<section>'</script><style>.a{top:0}</style>")
        self.assertEqual((e, w), ([], []))

    def test_allow_flag_suppresses(self):
        e, w = diag_of(B.check_tags, "<section>x</section>", allow_non_whitelist=True)
        self.assertEqual((e, w), ([], []))


class TestPackByFile(unittest.TestCase):
    """plan.md 已裁决第 7 条：超阈值按【文件边界】自动拆条，不切开单个文件。"""

    @staticmethod
    def _e(name, n):
        return {"name": name, "raw": n, "out": n, "text": "x" * n}

    def test_single_bin_when_under_threshold(self):
        bins = B.pack_by_file([self._e("a.js", 100), self._e("b.js", 100)], 18000)
        self.assertEqual(len(bins), 1)

    def test_splits_when_over_threshold(self):
        bins = B.pack_by_file([self._e("a.js", 10000), self._e("b.js", 10000)], 18000)
        self.assertEqual([[e["name"] for e in b] for b in bins], [["a.js"], ["b.js"]])

    def test_preserves_order(self):
        files = [self._e("protocol.js", 5000), self._e("hud.js", 9000), self._e("ui.js", 19500)]
        bins = B.pack_by_file(files, 18000)
        flat = [e["name"] for b in bins for e in b]
        self.assertEqual(flat, ["protocol.js", "hud.js", "ui.js"])

    def test_oversized_file_gets_own_bin(self):
        bins = B.pack_by_file([self._e("a.js", 100), self._e("huge.js", 40000)], 18000)
        self.assertEqual([[e["name"] for e in b] for b in bins], [["a.js"], ["huge.js"]])

    def test_never_splits_a_file(self):
        bins = B.pack_by_file([self._e("huge.js", 50000)], 18000)
        self.assertEqual(len(bins), 1)
        self.assertEqual(len(bins[0]), 1)

    def test_wrapper_overhead_reserved(self):
        # 恰好等于阈值的文件，加上 <script> 包裹会溢出 → 必须独占一条
        n = 18000 - B.WRAPPER_OVERHEAD
        bins = B.pack_by_file([self._e("a.js", n), self._e("b.js", 10)], 18000)
        self.assertEqual(len(bins), 2)

    def test_marker_suffix(self):
        self.assertEqual(B._suffix_marker("{{sbk-ui}}", 2), "{{sbk-ui-2}}")
        self.assertEqual(B._suffix_marker("SBKUI", 3), "SBKUI-3")


class TestEmitScriptRules(unittest.TestCase):
    @staticmethod
    def _e(name, n):
        return {"name": name, "raw": n, "out": n, "text": "var %s=1;" % name.replace(".", "_") + "x" * n}

    def test_single_bin_keeps_base_name_and_marker(self):
        d = B.Diag()
        rules, rid, layout = B.emit_script_rules(
            -1, "sbk-ui", "{{sbk-ui}}", [self._e("a.js", 10)], 18000, d, strip=False)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["scriptName"], "sbk-ui")
        self.assertEqual(rules[0]["findRegex"], r"/\{\{sbk-ui\}\}/")
        self.assertEqual(rid, -2)
        self.assertEqual(layout[0]["files"], ["a.js"])

    def test_multi_bin_gets_numbered_names_and_unique_markers(self):
        d = B.Diag()
        files = [self._e("protocol.js", 5000), self._e("hud.js", 9000), self._e("ui.js", 19000)]
        rules, rid, layout = B.emit_script_rules(
            -2, "sbk-ui", "{{sbk-ui}}", files, 18000, d, strip=False)
        self.assertEqual([r["scriptName"] for r in rules], ["sbk-ui-1", "sbk-ui-2"])
        finds = [r["findRegex"] for r in rules]
        self.assertEqual(len(set(finds)), len(finds), "拆出的匹配式必须唯一")
        for f in finds:
            self.assertEqual(B.classify_pattern(f)[0], "slash")
            self.assertFalse(B.matches_empty(f))
        self.assertEqual([r["id"] for r in rules], [-2, -3])
        self.assertEqual(rid, -4)

    def test_load_order_preserved_across_bins(self):
        """🚨 protocol → hud → ui：hud/ui 往 SBK.ui 合并挂载，顺序错了会未定义引用。"""
        d = B.Diag()
        files = [self._e("protocol.js", 5000), self._e("hud.js", 9000), self._e("ui.js", 19000)]
        rules, _, layout = B.emit_script_rules(
            -1, "sbk-ui", "{{sbk-ui}}", files, 18000, d, strip=False)
        flat = [f for it in layout for f in it["files"]]
        self.assertEqual(flat, ["protocol.js", "hud.js", "ui.js"])
        # 数组序即装载顺序：protocol 必须出现在 ui 之前
        blob = "".join(r["replaceString"] for r in rules)
        self.assertLess(blob.index("var protocol_js"), blob.index("var ui_js"))
        # id 递减，worker 按 regexSort 升序 → 数组序生效
        self.assertEqual([r["id"] for r in rules], sorted([r["id"] for r in rules], reverse=True))

    def test_unsplittable_file_over_safe_budget_is_error(self):
        d = B.Diag()
        B.emit_script_rules(-1, "sbk-ui", "{{sbk-ui}}", [self._e("ui.js", 19000)],
                            18000, d, strip=False)
        self.assertTrue(any("安全上限" in e and "完整 IIFE" in e for e in d.errors), d.errors)

    def test_lower_custom_threshold_only_warns_for_safe_module(self):
        d = B.Diag()
        B.emit_script_rules(-1, "sbk-ui", "{{sbk-ui}}", [self._e("ui.js", 5000)],
                            4000, d, strip=False)
        self.assertEqual(d.errors, [])
        self.assertTrue(any("自定义拆条阈值" in w for w in d.warns), d.warns)

    def test_empty_input_yields_nothing(self):
        d = B.Diag()
        rules, rid, layout = B.emit_script_rules(-1, "sbk-ui", "{{sbk-ui}}", [], 18000, d, False)
        self.assertEqual((rules, rid, layout), ([], -1, []))

    def test_each_bin_is_syntactically_valid(self):
        """拆出的每箱都是若干完整 IIFE 的拼接 → 必须各自语法有效。"""
        if not shutil.which("node"):
            self.skipTest("未装 node")
        d = B.Diag()
        mk = lambda n, pad: {"name": n, "raw": 0, "out": 0,
                             "text": "(function(){var a='%s';})();" % ("x" * pad)}
        files = [mk("a.js", 9000), mk("b.js", 9000), mk("c.js", 9000)]
        rules, _, _ = B.emit_script_rules(-1, "sbk-ui", "{{sbk-ui}}", files, 18000, d, strip=True)
        self.assertGreater(len(rules), 1)
        self.assertEqual(d.errors, [])


class TestEscaping(unittest.TestCase):
    def test_js_regex_escape_avoids_hyphen(self):
        # \- 在 JS unicode 模式下是非法 IdentityEscape → 不能用 Python re.escape
        self.assertEqual(B.escape_js_regex("{{sbk-css}}"), r"\{\{sbk-css\}\}")

    def test_js_regex_escape_handles_slash(self):
        self.assertEqual(B.escape_js_regex("a/b"), r"a\/b")

    def test_dumps_escapes_script_close(self):
        """§6.10：JSON 里 </script> 写成 <\\/script>。"""
        doc = {"regex_scripts": [{"replaceString": "<script>var a=1;</script>"}]}
        text = B.dumps_sbk(doc)
        self.assertIn("<\\/script>", text)
        # 关键：这是 JSON 层转义，解析回来必须仍是 </script>，否则脚本无法闭合
        self.assertEqual(json.loads(text)["regex_scripts"][0]["replaceString"],
                         "<script>var a=1;</script>")

    def test_check_script_close_accepts_escaped(self):
        e, _ = diag_of(B.check_script_close, "<\\/script>")
        self.assertEqual(e, [])

    def test_check_script_close_rejects_raw(self):
        e, _ = diag_of(B.check_script_close, "</script>")
        self.assertEqual(len(e), 1)


class TestThemeOwnership(unittest.TestCase):
    """🚨 2.1 单一运行时所有权（审计报告高风险 1）。

    1.0 有两条主题通道：生成器把 config.theme 永久编译进静态 sbk-css，theme.js 又写
    #sbk-theme-vars。后果是 prefs.enabled(false) 只清得掉动态那条 → 「关闭美化＝完全
    跟随平台」不成立。本类守的就是「静态通道已彻底拆除」这件事。
    """

    def test_generator_no_longer_has_a_theme_to_css_compiler(self):
        """反向守卫：编译 theme→CSS 的函数必须【不存在】。

        留着它就迟早有人在 build() 里再拼一次，双通道原地复活。
        """
        self.assertFalse(hasattr(B, "theme_override_css"),
                         "theme_override_css 又回来了——静态主题通道必须彻底拆除，"
                         "作者基线只能经 boot 信封交给 theme.js")

    def test_theme_var_mapping_still_available_for_validation(self):
        """令牌名映射本身仍要保留：风格包校验要用它判断令牌落到哪个变量。"""
        self.assertEqual(B.theme_var("accent"), "--chat-accent")
        self.assertEqual(B.theme_var("muted"), "--chat-text-muted")
        self.assertEqual(B.theme_var("onAccent"), "--sbk-on-accent")
        self.assertEqual(B.theme_var("--chat-bg"), "--chat-bg")


class TestThemeEnvelope(unittest.TestCase):
    """boot 信封：作者基线 + 风格包 + 默认包名，走 o.theme 这一个键。"""

    def _cfg(self, **over):
        cfg = {"theme": {}, "presets": {}, "preset": ""}
        cfg.update(over)
        return cfg

    def test_envelope_shape(self):
        e = B.theme_envelope(self._cfg(theme={"dark": {"accent": "#111"}}))
        self.assertEqual(set(e.keys()), {"v", "base", "presets", "preset"})
        self.assertEqual(e["v"], 2, "信封必须带 v:2 判别键，否则 theme.js 分不清它和 1.0 的扁平写法")
        self.assertEqual(e["base"], {"dark": {"accent": "#111"}})

    def test_envelope_is_always_truthy_even_when_empty(self):
        """🚨 主题初始化与 chrome 解耦的落点。

        core.js 只有 `if (o.theme) SBK.theme.apply(o.theme)` 一条主题接线。信封恒为
        非空对象 → 无论 modes.chrome 真假，boot 都会把主题层 start 一次。
        1.0 关掉 chrome 就没人调 theme.start，玩家上次存的字号/配色开局不生效。
        """
        e = B.theme_envelope(self._cfg())
        self.assertTrue(e, "空配置下信封也必须是真值，否则关掉 chrome 就没人读偏好存档")
        self.assertIsNone(e["base"])
        self.assertEqual(e["presets"], {})

    def test_old_flat_theme_config_still_accepted_as_base(self):
        """规范化后的作者基线仍经信封原样下发。"""
        old = {
            "dark": {"tokens": {"accent": "#c8a15a"}, "tune": {}},
            "light": {"tokens": {"accent": "#8a6a2f"}, "tune": {}},
        }
        e = B.theme_envelope(self._cfg(theme=old))
        self.assertEqual(e["base"], old)


class TestAuthorThemeValidation(unittest.TestCase):
    """config.theme 作者基线与 preset 共用 token 安全边界，但允许局部覆写。"""

    def setUp(self):
        self.adir = Path(__file__).resolve().parent / "sbk"

    def test_partial_two_side_theme_is_normalized(self):
        d = B.Diag()
        out = B.normalize_author_theme({
            "dark": {"accent": "#c8a15a", "onAccent": "#1a1712"},
            "light": {"accent": "#8a6a2f", "onAccent": "#ffffff"},
        }, self.adir, d)
        self.assertEqual(d.errors, [], d.errors)
        self.assertEqual(out["dark"]["tokens"]["accent"], "#c8a15a")
        self.assertEqual(out["light"]["tokens"]["onAccent"], "#ffffff")

    def test_flat_legacy_theme_expands_to_both_sides(self):
        d = B.Diag()
        out = B.normalize_author_theme({"accent": "#5aa9e6"}, self.adir, d)
        self.assertEqual(d.errors, [], d.errors)
        self.assertEqual(out["dark"], out["light"])

    def test_explicit_theme_requires_both_sides(self):
        d = B.Diag()
        out = B.normalize_author_theme({"dark": {"accent": "#5aa9e6"}}, self.adir, d)
        self.assertEqual(out, {})
        self.assertTrue(any("同时给 dark/light" in e for e in d.errors), d.errors)

    def test_structural_and_unknown_tokens_are_rejected(self):
        d = B.Diag()
        out = B.normalize_author_theme({
            "--rpx": "999px", "--sbk-z-pop": 9999, "--chat-nope": "#fff", "accent": "#5aa9e6"
        }, self.adir, d)
        self.assertGreaterEqual(len(d.errors), 3, d.errors)
        for mode in ("dark", "light"):
            self.assertNotIn("--rpx", out[mode]["tokens"])
            self.assertNotIn("--sbk-z-pop", out[mode]["tokens"])
            self.assertNotIn("--chat-nope", out[mode]["tokens"])
            self.assertIn("accent", out[mode]["tokens"])

    def test_dangerous_value_is_rejected(self):
        d = B.Diag()
        out = B.normalize_author_theme({"accent": "#fff;color:red"}, self.adir, d)
        self.assertTrue(any("危险片段" in e for e in d.errors), d.errors)
        self.assertNotIn("accent", out["dark"]["tokens"])

    def test_structured_tune_is_validated(self):
        d = B.Diag()
        out = B.normalize_author_theme({
            "dark": {"tokens": {"accent": "#5aa9e6"}, "tune": {"fontSize": 16}},
            "light": {"tokens": {"accent": "#1a5f96"}, "tune": {"fontSize": 99}},
        }, self.adir, d)
        self.assertEqual(out["dark"]["tune"]["fontSize"], 16)
        self.assertNotIn("fontSize", out["light"]["tune"])
        self.assertTrue(any("tune.fontSize" in e for e in d.errors), d.errors)

    def test_supplied_color_pair_must_pass_contrast(self):
        d = B.Diag()
        B.normalize_author_theme({
            "dark": {"bg": "#ffffff", "text": "#ffffff"},
            "light": {"bg": "#000000", "text": "#ffffff"},
        }, self.adir, d)
        self.assertTrue(any("对比度不足" in e and "dark" in e for e in d.errors), d.errors)


class TestBundleCompiler(unittest.TestCase):
    """六维风格包编译与生成期校验。"""

    def _dim(self, **kw):
        return {"dark": dict(kw), "light": dict(kw)}

    def _palette(self, **over):
        """一套过得了对比度的最小 palette（核心五键齐全）。"""
        dark = {"bg": "#101010", "surface": "#1c1c1c", "text": "#f0f0f0",
                "accent": "#5aa9e6", "border": "#6b7280"}
        light = {"bg": "#f5f5f5", "surface": "#ffffff", "text": "#1a1a1a",
                 "accent": "#1a5f96", "border": "#767676"}
        dark.update(over.get("dark") or {})
        light.update(over.get("light") or {})
        return {"dark": dark, "light": light}

    def _bundle(self, **over):
        b = {
            "palette": self._palette(),
            "layout": self._dim(),
            "ui": self._dim(),
            "font": self._dim(),
            "cohesion": self._dim(),
            "decoration": self._dim(),
        }
        b.update(over)
        return b

    def test_minimal_bundle_compiles(self):
        d = B.Diag()
        c, ok = B.compile_bundle("测试包", self._bundle(), d)
        self.assertTrue(ok, d.errors)
        self.assertEqual(set(c.keys()), {"dark", "light"})
        self.assertEqual(set(c["dark"].keys()), {"tokens", "tune"})
        self.assertEqual(c["dark"]["tokens"]["accent"], "#5aa9e6")

    def test_tune_fields_go_to_tune_not_tokens(self):
        """🚨 可微调项必须以【结构化数字】下传，不能只变成 CSS。

        prefs.get 要回读 fontSize/lineHeight/opacity；若只有 tokens，运行时就得去
        反解析 'calc(24 * var(--rpx))' 这类任意 CSS —— 那必然出错（审计报告 8）。
        """
        d = B.Diag()
        c, ok = B.compile_bundle("测试包", self._bundle(
            font=self._dim(fontSize=16, lineHeight=1.8, **{"fs-sm": "calc(22 * var(--rpx))"})), d)
        self.assertTrue(ok, d.errors)
        self.assertEqual(c["dark"]["tune"], {"fontSize": 16, "lineHeight": 1.8})
        self.assertNotIn("fontSize", c["dark"]["tokens"])
        self.assertEqual(c["dark"]["tokens"]["fs-sm"], "calc(22 * var(--rpx))")

    def test_unknown_dimension_is_error(self):
        d = B.Diag()
        _, ok = B.compile_bundle("测试包", self._bundle(shadowcast=self._dim(x="1")), d)
        self.assertFalse(ok)
        self.assertTrue(any("未知六维键" in e for e in d.errors), d.errors)

    def test_six_dims_are_exactly_the_contract(self):
        self.assertEqual(B.BUNDLE_DIMS,
                         ("palette", "layout", "ui", "font", "cohesion", "decoration"))

    def test_missing_dimension_is_error(self):
        d = B.Diag()
        b = self._bundle()
        del b["decoration"]
        _, ok = B.compile_bundle("测试包", b, d)
        self.assertFalse(ok)
        self.assertTrue(any("缺少六维键" in e for e in d.errors), d.errors)

    def test_missing_one_side_is_error(self):
        """盘点 E.3：平台强制两套主题都存在，单侧包切过去会整卡失效。"""
        d = B.Diag()
        b = self._bundle()
        b["palette"] = {"dark": b["palette"]["dark"]}          # 只给 dark
        _, ok = B.compile_bundle("测试包", b, d)
        self.assertFalse(ok)
        self.assertTrue(any("双侧完整" in e for e in d.errors), d.errors)

    def test_unknown_token_name_is_error(self):
        d = B.Diag()
        _, ok = B.compile_bundle("测试包", self._bundle(layout=self._dim(wobble="3px")), d)
        self.assertFalse(ok)
        self.assertTrue(any("不在白名单" in e for e in d.errors), d.errors)

    def test_fabricated_chat_var_is_error(self):
        """--chat-* 只认平台真实存在的 14 个：臆造名写了不报错也不生效（静默失效）。"""
        d = B.Diag()
        b = self._bundle()
        b["palette"]["dark"]["--chat-nope"] = "#fff"
        b["palette"]["light"]["--chat-nope"] = "#000"
        _, ok = B.compile_bundle("测试包", b, d)
        self.assertFalse(ok)
        self.assertTrue(any("--chat-nope" in e for e in d.errors), d.errors)

    def test_unknown_private_token_is_error_on_fallback_path(self):
        """🚨 读不到 theme.js 时也必须【严格】，不能放行一切 --sbk-*。

        放行一切等于生成期不校验私有令牌：作者写错一个名字会静默无效。
        """
        d = B.Diag()
        b = self._bundle()
        b["layout"] = {"dark": {"--sbk-wobble": "3px"}, "light": {"--sbk-wobble": "3px"}}
        _, ok = B.compile_bundle("测试包", b, d, None)      # sbk_ok=None → 走内置镜像
        self.assertFalse(ok, "未知私有令牌在兜底路径上也应被拒")
        self.assertTrue(any("wobble" in e for e in d.errors), d.errors)

    def test_ok_token_defaults_to_strict(self):
        self.assertTrue(B.ok_token("gap"))
        self.assertTrue(B.ok_token("--sbk-radius"))
        self.assertTrue(B.ok_token("accent"))
        self.assertFalse(B.ok_token("wobble"))
        self.assertFalse(B.ok_token("--sbk-wobble"))
        self.assertFalse(B.ok_token("--chat-nope"))
        self.assertFalse(B.ok_token("--rpx"), "--rpx 是平台尺寸基准，只读不写")

    def test_sbk_private_token_whitelist_is_read_from_theme_js(self):
        """白名单真值只有一处（theme.js 的 SBK_OK），生成器不写死副本。"""
        adir = Path(__file__).resolve().parent / "sbk"
        if not (adir / "theme.js").is_file():
            self.skipTest("sbk/theme.js 不存在")
        wl = B._sbk_whitelist_from_theme_js(adir, B.Diag())
        self.assertIsNotNone(wl, "没能从 theme.js 读出 SBK_OK")
        for k in ("gap", "pad", "radius", "fs", "lh", "glow", "hp", "shadow"):
            self.assertIn(k, wl, "SBK_OK 里应有 %s" % k)
        # 结构约定不得让风格包改：z 层安全带（硬约束 12）与逐条 bar 的语义色游标
        self.assertNotIn("z-panel", wl, "--sbk-z-panel 是硬约束 12 的安全带，不许风格包改")
        self.assertNotIn("tone", wl, "--sbk-tone 是 hud.js 逐条 bar 的局部游标，全局写死会让所有进度条同色")

    def test_dangerous_values_are_rejected(self):
        """危险值闸门：截断样式块 / 外部资源 / 多写声明。"""
        bad = {
            "brace": "#fff}.evil{color:red",
            "style_close": "#fff</style><b>",
            "url": "url(https://x.example/a.png)",
            "import": "@import 'https://x.example/a.css'",
            "expression": "expression(alert(1))",
            "semicolon": "#fff;color:red",
        }
        for label, v in bad.items():
            with self.subTest(case=label):
                d = B.Diag()
                b = self._bundle()
                b["palette"]["dark"]["userBubble"] = v
                b["palette"]["light"]["userBubble"] = v
                _, ok = B.compile_bundle("测试包", b, d)
                self.assertFalse(ok, "%s 应被拒绝" % label)
                self.assertTrue(any("危险片段" in e for e in d.errors), d.errors)

    def test_cohesion_never_emits_css(self):
        """cohesion 是一致性元信息，只校验不输出。"""
        d = B.Diag()
        c, ok = B.compile_bundle("测试包", self._bundle(
            cohesion=self._dim(contrast="AA", density="loose", mood="纸感")), d)
        self.assertTrue(ok, d.errors)
        for mode in ("dark", "light"):
            for k in ("contrast", "density", "mood"):
                self.assertNotIn(k, c[mode]["tokens"], "cohesion 泄漏进 tokens：%s" % k)
            self.assertNotIn("contrast", c[mode]["tune"])

    def test_cohesion_object_value_is_error(self):
        d = B.Diag()
        _, ok = B.compile_bundle("测试包",
                                 self._bundle(cohesion=self._dim(contrast={"a": 1})), d)
        self.assertFalse(ok)
        self.assertTrue(any("cohesion" in e for e in d.errors), d.errors)

    def test_out_of_range_tune_is_error(self):
        """越界 tune 在运行时会被 okField 逐字段丢弃 → 生成期放行等于静默失效。"""
        d = B.Diag()
        _, ok = B.compile_bundle("测试包", self._bundle(font=self._dim(fontSize=48)), d)
        self.assertFalse(ok)
        self.assertTrue(any("越界" in e for e in d.errors), d.errors)

    def test_bad_preset_name_is_error(self):
        for nm in ("", " 前导空格", 'a"b', "<b>", "x" * 33):
            with self.subTest(name=nm):
                d = B.Diag()
                _, ok = B.compile_bundle(nm, self._bundle(), d)
                self.assertFalse(ok, "%r 应被拒绝" % nm)

    def test_good_preset_names_accepted(self):
        for nm in ("素雅阅读", "dense-status", "Neon_Tech 2"):
            with self.subTest(name=nm):
                d = B.Diag()
                _, ok = B.compile_bundle(nm, self._bundle(), d)
                self.assertTrue(ok, "%r 应被接受：%s" % (nm, d.errors))

    def test_empty_side_after_compile_is_error(self):
        d = B.Diag()
        b = {dim: self._dim() for dim in B.BUNDLE_DIMS}
        b["cohesion"] = self._dim(note="x")
        _, ok = B.compile_bundle("测试包", b, d)
        self.assertFalse(ok)
        self.assertTrue(any("没有任何令牌" in e for e in d.errors), d.errors)


class TestBundleContrast(unittest.TestCase):
    """生成期对比度校验（WCAG 2.1）。只对可解析 hex 严格检查，不可解析【报错】而非假通过。"""

    def _compiled(self, dark, light):
        return {"dark": {"tokens": dark, "tune": {}},
                "light": {"tokens": light, "tune": {}}}

    OK_DARK = {"bg": "#101010", "surface": "#1c1c1c", "text": "#f0f0f0",
               "accent": "#5aa9e6", "border": "#6b7280"}
    OK_LIGHT = {"bg": "#f5f5f5", "surface": "#ffffff", "text": "#1a1a1a",
                "accent": "#1a5f96", "border": "#767676"}

    def test_contrast_math_matches_wcag_reference(self):
        # 黑白极值 21:1，同色 1:1（WCAG 2.x 公式的两个锚点）
        self.assertAlmostEqual(B.contrast("#000000", "#ffffff"), 21.0, places=2)
        self.assertAlmostEqual(B.contrast("#777777", "#777777"), 1.0, places=6)

    def test_good_palette_passes(self):
        d = B.Diag()
        self.assertTrue(B.check_bundle_contrast("t", self._compiled(self.OK_DARK, self.OK_LIGHT), d),
                        d.errors)

    def test_body_text_below_4_5_is_error(self):
        dark = dict(self.OK_DARK, text="#4a4a4a")      # 深灰字压在近黑底上
        d = B.Diag()
        self.assertFalse(B.check_bundle_contrast("t", self._compiled(dark, self.OK_LIGHT), d))
        self.assertTrue(any("正文对页面底" in e for e in d.errors), d.errors)

    def test_accent_below_3_is_error(self):
        dark = dict(self.OK_DARK, accent="#26303a")
        d = B.Diag()
        self.assertFalse(B.check_bundle_contrast("t", self._compiled(dark, self.OK_LIGHT), d))
        self.assertTrue(any("强调色" in e for e in d.errors), d.errors)

    def test_border_below_3_is_error(self):
        """border 承载控件边界与焦点环，按 1.4.11 非文本对比 3:1 判。"""
        dark = dict(self.OK_DARK, border="#2a2d33")
        d = B.Diag()
        self.assertFalse(B.check_bundle_contrast("t", self._compiled(dark, self.OK_LIGHT), d))
        self.assertTrue(any("控件边界" in e for e in d.errors), d.errors)

    def test_unparsable_core_color_is_error_not_silent_pass(self):
        """🚨 「不可解析就跳过」是假通过：作者写 var(--x)，实机可能白底白字。"""
        for bad in ("var(--chat-text)", "rgba(255,255,255,.9)", "white"):
            with self.subTest(value=bad):
                dark = dict(self.OK_DARK, text=bad)
                d = B.Diag()
                self.assertFalse(B.check_bundle_contrast("t", self._compiled(dark, self.OK_LIGHT), d))
                self.assertTrue(any("不是可解析" in e for e in d.errors), d.errors)

    def test_missing_core_key_is_error(self):
        dark = {k: v for k, v in self.OK_DARK.items() if k != "border"}
        d = B.Diag()
        self.assertFalse(B.check_bundle_contrast("t", self._compiled(dark, self.OK_LIGHT), d))
        self.assertTrue(any("缺 palette.border" in e for e in d.errors), d.errors)

    def test_on_accent_checked_against_accent(self):
        dark = dict(self.OK_DARK, onAccent="#7ec0f0")     # 亮蓝字压在亮蓝底上
        d = B.Diag()
        self.assertFalse(B.check_bundle_contrast("t", self._compiled(dark, self.OK_LIGHT), d))
        self.assertTrue(any("onAccent" in e for e in d.errors), d.errors)

    def test_short_hex_is_normalized(self):
        self.assertEqual(B.norm_hex("#ABC"), "#aabbcc")
        self.assertEqual(B.norm_hex("#AABBCC"), "#aabbcc")
        self.assertIsNone(B.norm_hex("rgba(0,0,0,.5)"))
        self.assertIsNone(B.norm_hex(None))

    def test_light_side_is_checked_too(self):
        """双侧都查：只查一侧等于「浅色下能不能读」全凭运气。"""
        light = dict(self.OK_LIGHT, text="#cccccc")
        d = B.Diag()
        self.assertFalse(B.check_bundle_contrast("t", self._compiled(self.OK_DARK, light), d))
        self.assertTrue(any("light 侧" in e for e in d.errors), d.errors)


class TestShippedPresets(unittest.TestCase):
    """仓库自带的三套代表包必须真能编译且双侧全绿（美化决策：第一批只做三套）。"""

    NAMES = ("素雅阅读", "密集状态", "表现性科技")

    def setUp(self):
        self.here = Path(__file__).resolve().parent
        self.pdir = self.here / "presets"
        if not self.pdir.is_dir():
            self.skipTest("presets/ 目录不存在")

    def test_three_representative_bundles_exist(self):
        for n in self.NAMES:
            self.assertTrue((self.pdir / ("%s.json" % n)).is_file(), "缺风格包 %s.json" % n)

    def test_all_shipped_bundles_compile_and_pass_contrast(self):
        sbk_ok = B._sbk_whitelist_from_theme_js(self.here / "sbk", B.Diag())
        for n in self.NAMES:
            with self.subTest(preset=n):
                d = B.Diag()
                src = B.load_presets(["presets/%s.json" % n], self.here, d)
                self.assertEqual(d.errors, [], d.errors)
                c, ok = B.compile_bundle(n, src[n], d, sbk_ok)
                self.assertTrue(ok, "%s 编译失败：%s" % (n, d.errors))
                self.assertTrue(B.check_bundle_contrast(n, c, d),
                                "%s 对比度不达标：%s" % (n, d.errors))
                self.assertEqual(d.errors, [], d.errors)

    def test_shipped_bundles_are_dual_side_complete(self):
        for n in self.NAMES:
            with self.subTest(preset=n):
                doc = json.loads((self.pdir / ("%s.json" % n)).read_text(encoding="utf-8"))
                dims = [k for k in doc if k in B.BUNDLE_DIMS]
                self.assertEqual(sorted(dims), sorted(B.BUNDLE_DIMS),
                                 "%s 六维不全（代表包必须演示全部六维）" % n)
                for dim in dims:
                    self.assertIn("dark", doc[dim], "%s.%s 缺 dark" % (n, dim))
                    self.assertIn("light", doc[dim], "%s.%s 缺 light" % (n, dim))

    def test_shipped_bundles_have_no_external_resources(self):
        """美化决策：所有外部字体、图片字体、CDN 与 fetch 排除；仅系统字体与本地 CSS。

        只查【真正会编译进 CSS 的令牌值】。说明性 _ 键里出现 "url(" 这类字样是文档
        （例如「零外部资源：无 url()」），按裸文本查会把注释误判成违规。
        """
        for n in self.NAMES:
            with self.subTest(preset=n):
                doc = json.loads((self.pdir / ("%s.json" % n)).read_text(encoding="utf-8"))
                for dim in [k for k in doc if k in B.BUNDLE_DIMS]:
                    for mode in ("dark", "light"):
                        for k, v in doc[dim][mode].items():
                            if k.startswith("_"):
                                continue
                            sv = str(v)
                            for bad in ("url(", "@import", "http://", "https", "@font-face"):
                                self.assertNotIn(bad, sv,
                                                 "%s.%s.%s 含外部资源片段 %s：%r"
                                                 % (n, dim, mode, bad, sv))

    def test_palette_maps_to_platform_tokens(self):
        """要求之一：至少有一组把 palette 映到 14 个平台令牌。"""
        doc = json.loads((self.pdir / "素雅阅读.json").read_text(encoding="utf-8"))
        pal = doc["palette"]["dark"]
        mapped = {B.theme_var(k) for k in pal if not k.startswith("_")}
        platform = {"--chat-" + v for v in B._PLATFORM_VARS}
        hit = mapped & platform
        self.assertEqual(len(hit), 14,
                         "素雅阅读 的 palette 应覆盖全部 14 个平台令牌，当前 %d 个：%s"
                         % (len(hit), sorted(hit)))

    def test_other_dims_map_to_sbk_private_tokens(self):
        """layout/ui/font/decoration 必须落到 --sbk-* 已有/合理私有令牌。"""
        doc = json.loads((self.pdir / "密集状态.json").read_text(encoding="utf-8"))
        for dim in ("layout", "ui", "font", "decoration"):
            keys = [k for k in doc[dim]["dark"]
                    if not k.startswith("_") and k not in B.TUNE_FIELDS]
            self.assertTrue(keys, "%s 维没有任何令牌" % dim)
            for k in keys:
                self.assertTrue(B.theme_var(k).startswith("--sbk-"),
                                "%s.%s 应落到 --sbk-* 私有令牌，实际 %s"
                                % (dim, k, B.theme_var(k)))


class TestPresetLoading(unittest.TestCase):
    """config.presets 的两种写法。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    MINI = {"palette": {"dark": {"bg": "#101010", "surface": "#1c1c1c", "text": "#f0f0f0",
                                "accent": "#5aa9e6", "border": "#6b7280"},
                        "light": {"bg": "#f5f5f5", "surface": "#ffffff", "text": "#1a1a1a",
                                  "accent": "#1a5f96", "border": "#767676"}}}

    def test_inline_object_map(self):
        d = B.Diag()
        got = B.load_presets({"甲": self.MINI}, self.tmp, d)
        self.assertEqual(sorted(got), ["甲"])
        self.assertEqual(d.errors, [])

    def test_path_array_single_bundle_file(self):
        doc = dict(self.MINI)
        doc["name"] = "乙"
        (self.tmp / "b.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        d = B.Diag()
        got = B.load_presets(["b.json"], self.tmp, d)
        self.assertEqual(sorted(got), ["乙"])
        self.assertEqual(d.errors, [])

    def test_path_array_falls_back_to_filename(self):
        (self.tmp / "丙.json").write_text(json.dumps(self.MINI, ensure_ascii=False),
                                          encoding="utf-8")
        d = B.Diag()
        got = B.load_presets(["丙.json"], self.tmp, d)
        self.assertEqual(sorted(got), ["丙"], d.errors)

    def test_path_array_bundle_map_file(self):
        (self.tmp / "m.json").write_text(
            json.dumps({"丁": self.MINI, "戊": self.MINI}, ensure_ascii=False), encoding="utf-8")
        d = B.Diag()
        got = B.load_presets(["m.json"], self.tmp, d)
        self.assertEqual(sorted(got), ["丁", "戊"], d.errors)

    def test_missing_file_is_error(self):
        d = B.Diag()
        B.load_presets(["nope.json"], self.tmp, d)
        self.assertTrue(any("不存在" in e for e in d.errors), d.errors)

    def test_bad_json_is_error(self):
        (self.tmp / "x.json").write_text("{not json", encoding="utf-8")
        d = B.Diag()
        B.load_presets(["x.json"], self.tmp, d)
        self.assertTrue(any("不是合法 JSON" in e for e in d.errors), d.errors)

    def test_only_configured_bundles_are_shipped(self):
        """🚨 绝不把整个 style-db 打包：每个包都要进 boot 规则的 replaceString。"""
        (self.tmp / "a.json").write_text(json.dumps({"甲": self.MINI}, ensure_ascii=False),
                                         encoding="utf-8")
        (self.tmp / "b.json").write_text(json.dumps({"乙": self.MINI}, ensure_ascii=False),
                                         encoding="utf-8")
        d = B.Diag()
        got = B.load_presets(["a.json"], self.tmp, d)          # 只列 a
        self.assertEqual(sorted(got), ["甲"], "只应加载配置里列出的包")


class TestHostIdValidation(unittest.TestCase):
    """审计报告 7：hostId 同时插入 HTML 与 CSS 属性选择器，1.0 完全无校验。"""

    def test_valid_ids_pass(self):
        for v in ("sbk-hud", "hud_1", "A", "a" * 60):
            with self.subTest(host=v):
                d = B.Diag()
                self.assertEqual(B.check_host_id(v, d), v)
                self.assertEqual(d.errors, [])

    def test_invalid_ids_error_and_fall_back(self):
        for v in ("", "2hud", "a b", 'a"b', "a>b", "a]b", "a" * 61, "有中文"):
            with self.subTest(host=v):
                d = B.Diag()
                self.assertEqual(B.check_host_id(v, d), "sbk-hud")
                self.assertTrue(d.errors, "%r 应被拒绝" % v)

    def test_regex_is_the_documented_one(self):
        self.assertEqual(B.HOST_ID_RE.pattern, r"^[A-Za-z][A-Za-z0-9_-]{0,59}$")

    def test_derived_ids_stay_within_runtime_limit(self):
        d = B.Diag()
        base = B.check_host_id("a" * 60, d)
        self.assertEqual(len(base + "-pin"), 64)
        self.assertEqual(len(base + "-chr"), 64)
        self.assertEqual(d.errors, [])

    def test_end_to_end_bad_host_id_is_error(self):
        d = B.Diag()
        cfg = B.normalize_config({"beginning": "hi", "statusbar": "{{hud}}",
                                  "hostId": 'x"><script>'}, "c.json", d)
        self.assertEqual(cfg["hostId"], "sbk-hud")
        self.assertTrue(any("hostId" in e for e in d.errors), d.errors)


class TestSchemaValidation(unittest.TestCase):
    """未知 schema type 生成期报错；schema.persist 是假契约，WARN 并丢弃。"""

    def test_known_types_pass(self):
        d = B.Diag()
        fields = [{"key": "k%d" % i, "type": t} for i, t in enumerate(B.SCHEMA_TYPES)]
        B.normalize_schema({"fields": fields}, d)
        self.assertEqual(d.errors, [], d.errors)

    def test_new_display_types_are_supported(self):
        """本轮按美化决策新增三种纯展示控件。"""
        for t in ("time", "summary", "turn"):
            self.assertIn(t, B.SCHEMA_TYPES)

    def test_unknown_type_is_error(self):
        d = B.Diag()
        B.normalize_schema({"fields": [{"key": "x", "type": "table"}]}, d)
        self.assertTrue(any("不受支持" in e for e in d.errors), d.errors)

    def test_persist_is_warned_and_dropped(self):
        """审计报告 3：协议说明声称走 SBK.store，运行时既没加载也没保存。"""
        d = B.Diag()
        out = B.normalize_schema({"persist": True, "fields": []}, d)
        self.assertNotIn("persist", out, "persist 必须在进 boot 载荷之前就被删掉")
        self.assertTrue(any("假契约" in w for w in d.warns), d.warns)
        self.assertEqual(d.errors, [])

    def test_persist_never_reaches_boot_payload(self):
        d = B.Diag()
        cfg = B.normalize_config({"beginning": "hi", "statusbar": "{{hud}}",
                                  "schema": {"persist": True, "fields": []}}, "c.json", d)
        js = B.boot_script(cfg, d)
        self.assertNotIn("persist", js, "persist 泄漏进了 boot 载荷")


class TestThemeJsContract(unittest.TestCase):
    """🚨 theme.js 的源码契约。守的是【层间接缝】：生成器与运行时对同一件事的口径。

    这些断言看着"测源码形状"，但它们各自对应一个已证实的静默失效：口径一漂移，
    生成期放行的东西运行时会被逐字段丢弃，而两边的单测都测不到。
    """

    def setUp(self):
        p = Path(__file__).resolve().parent / "sbk" / "theme.js"
        if not p.is_file():
            self.skipTest("sbk/theme.js 不存在")
        self.raw = p.read_text(encoding="utf-8")
        self.code = B.strip_js_comments(self.raw)

    def test_font_size_field_is_css_px_not_rpx(self):
        """审计报告 8：v1 的 24rpx 在 323px 视口约 10px，小到几乎不能读。"""
        m = re.search(r"\{\s*key:\s*'fontSize'[^}]*\}", self.code)
        self.assertIsNotNone(m, "没能定位 fontSize 字段定义")
        f = m.group(0)
        self.assertIn("unit: 'px'", f, "fontSize 必须改成 CSS px（美化决策「尺寸」）")
        self.assertNotIn("rpx", f, "fontSize 不应再带 rpx 单位")
        got = dict(re.findall(r"(min|max|def|step):\s*([\d.]+)", f))
        self.assertEqual(int(got["min"]), B.TUNE_FIELDS["fontSize"]["min"])
        self.assertEqual(int(got["max"]), B.TUNE_FIELDS["fontSize"]["max"])
        self.assertTrue(B.TUNE_FIELDS["fontSize"]["min"] <= int(got["def"])
                        <= B.TUNE_FIELDS["fontSize"]["max"],
                        "默认字号必须落在 px 值域内")

    def test_tune_field_ranges_match_generator(self):
        """值域两侧必须一致：漂移会让生成期放行的包被运行时 okField 丢弃（静默失效）。"""
        for key, spec in B.TUNE_FIELDS.items():
            with self.subTest(field=key):
                m = re.search(r"\{\s*key:\s*'%s'[^}]*\}" % key, self.code)
                self.assertIsNotNone(m, "没能定位 %s 字段定义" % key)
                got = dict(re.findall(r"(min|max):\s*([\d.]+)", m.group(0)))
                self.assertAlmostEqual(float(got["min"]), float(spec["min"]), places=4)
                self.assertAlmostEqual(float(got["max"]), float(spec["max"]), places=4)

    def test_schema_version_bumped_for_migration(self):
        m = re.search(r"var SCHEMA = (\d+)", self.code)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 2,
                                "fontSize 换了量纲，SCHEMA 必须升版，否则旧存档被静默错解")

    def test_v1_font_size_is_migrated_not_reinterpreted(self):
        """🚨 旧 24rpx 不该直接变 24px（那是放大 2.4 倍，玩家一升级就破版）。"""
        self.assertIn("migrateFontSize", self.code, "缺 v1→v2 的 fontSize 迁移函数")
        m = re.search(r"function migrateFontSize\([^)]*\)\s*\{(.*?)\n  \}", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 migrateFontSize")
        body = m.group(1)
        self.assertIn("V1_RPX_PER_PX", body, "迁移必须做换算，不能照搬数值")
        # 必须夹取而不是丢弃：夹取保住玩家「偏小还是偏大」的意图
        self.assertIn("f.min", body)
        self.assertIn("f.max", body)

    def test_override_delete_contract_is_implemented(self):
        """审计报告 2：文档承诺写回默认值会删 override，1.0 代码无条件保存。"""
        m = re.search(r"set: function \(k, v, m\) \{(.*?)\n    \},", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 prefs.set")
        body = m.group(1)
        self.assertIn("sameAsDefault", body,
                      "set 必须比对「不含当前 override 的 resolved 默认值」")
        self.assertRegex(body, r"delete\s+prefs\.ov\[mm\]\[k\]",
                         "等于默认值时必须【删除】该 override，而不是存一份等于默认的值——"
                         "否则该字段再也跟不上 preset 升级")

    def test_same_as_default_normalizes_color_case_and_number_step(self):
        m = re.search(r"function sameAsDefault\(.*?\n  \}", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 sameAsDefault")
        body = m.group(0)
        self.assertIn("toLowerCase", body, "颜色必须大小写归一，否则 #FFF000 与 #fff000 判成不同")
        self.assertIn("f.step", body, "数字必须按 step 容差比较，否则 0.1 步进的浮点噪声会漏判")

    def test_prefs_get_reads_preset_not_just_field_default(self):
        """审计报告 8：1.0 的非颜色分支直接 return f.def，无视 preset。"""
        m = re.search(r"get: function \(k, m\) \{(.*?)\n    \},", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 prefs.get")
        body = m.group(1)
        self.assertIn("defaultOf", body, "回读必须走 override → resolved preset/base → 字段默认")
        self.assertNotRegex(body, r"return\s+f\.def\s*;",
                            "非颜色字段不能直接回落字段默认，那会无视 preset 的 tune")

    def test_default_of_uses_structured_tune_not_css_parsing(self):
        """要求：可微调项以结构化 tune 传入，避免反解析任意 CSS。"""
        m = re.search(r"function defaultOf\(.*?\n  \}", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 defaultOf")
        body = m.group(0)
        self.assertIn("tuneOf", body, "非颜色字段必须从结构化 tune 取值")
        for bad in ("parseFloat", "parseInt", "match", "replace"):
            self.assertNotIn(bad, body,
                             "defaultOf 不该反解析 CSS（出现 %s）——tune 已是数字" % bad)

    def test_bridge_covers_both_host_and_snap_for_fs_and_lh(self):
        """审计报告 8：1.0 字号只作用 .sbk-host，气泡内状态面板完全不跟着变。"""
        m = re.search(r"var BRIDGE = (.*?);\n", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 BRIDGE")
        bridge = m.group(1)
        self.assertIn(".sbk-host", bridge)
        self.assertIn(".sbk-snap", bridge, "BRIDGE 必须同时作用气泡内面板根 .sbk-snap")
        self.assertIn("font-size:var(--sbk-fs", bridge, "BRIDGE 必须桥字号")
        self.assertIn("line-height:var(--sbk-lh", bridge, "BRIDGE 必须桥行距")
        self.assertNotIn("!important", bridge,
                         "带 [data-chat=root] 祖先已是 (0,2,0)，不需要 !important（硬约束 10）")

    def test_resolve_writes_font_size_in_px(self):
        m = re.search(r"function resolve\(m\) \{(.*?)\n  \}", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 resolve")
        body = m.group(1)
        self.assertIn("'px'", body, "resolve 必须写 --sbk-fs:<n>px")
        self.assertNotIn("var(--rpx)", body, "字号不再用 calc(n * var(--rpx))")

    def test_register_requires_both_sides(self):
        m = re.search(r"function regOne\(name, def\) \{(.*?)\n  \}", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 regOne")
        body = m.group(1)
        self.assertRegex(body, r"hasOwn\(def, 'dark'\)")
        self.assertRegex(body, r"hasOwn\(def, 'light'\)")
        self.assertIn("return false", body, "校验失败必须返回 false 且不注册")
        self.assertIn("PRESETS[name] = norm", body, "成功才写进 PRESETS")

    def test_register_returns_boolean_and_batch_returns_map(self):
        m = re.search(r"register: function \(name, def\) \{(.*?)\n    \},", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 theme.register")
        body = m.group(1)
        self.assertIn("out[k] = regOne(k, name[k])", body, "批量应返回结果对象")
        self.assertIn("return regOne(name, def)", body, "单个应返回 boolean")

    def test_danger_regex_matches_generator_side(self):
        """危险值口径两侧一致：生成期拒的，运行时也要拒（反之亦然）。

        比较前把 JS 正则里的 `\\/` 还原成 `/`——JS 正则字面量里的斜杠必须转义，
        Python 侧不必，直接按裸文本比会假红。
        """
        m = re.search(r"var DANGER = /(.*?)/i;", self.code)
        self.assertIsNotNone(m, "没能定位 theme.js 的 DANGER")
        js = m.group(1).replace(r"\/", "/")
        py = B.THEME_DANGER_RE.pattern
        for frag in (r"\}", r"\{", ";", "</style", "</script",
                     "url", "@import", "expression", "javascript"):
            self.assertIn(frag, js, "theme.js DANGER 缺 %s" % frag)
            self.assertIn(frag, py, "build_sbk.THEME_DANGER_RE 缺 %s" % frag)

    def test_sbk_private_fallback_mirrors_theme_js_exactly(self):
        """🚨 内置镜像必须与 theme.js 的 SBK_OK 完全相等。

        镜像只在读不到 theme.js 时兜底（此时走严格路径而非放行一切）。一旦漂移，
        兜底路径就会与运行时口径不一致——生成期放行、运行时丢弃，静默失效。
        """
        parsed = B._sbk_whitelist_from_theme_js(
            Path(__file__).resolve().parent / "sbk", B.Diag())
        self.assertEqual(parsed, set(B.SBK_PRIVATE_FALLBACK),
                         "SBK_PRIVATE_FALLBACK 与 theme.js 的 SBK_OK 已漂移："
                         "只在 theme.js 里的 %s / 只在镜像里的 %s"
                         % (sorted(parsed - set(B.SBK_PRIVATE_FALLBACK)),
                            sorted(set(B.SBK_PRIVATE_FALLBACK) - parsed)))

    def test_enabled_true_clears_forced_native(self):
        """要求：prefs.enabled(false) 清空动态 style 后真跟随平台；重新开启要恢复。"""
        m = re.search(r"enabled: function \(v\) \{(.*?)\n    \},", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 prefs.enabled")
        body = m.group(1)
        apply = re.search(r"function apply\(x\) \{(.*?)\n  \}", self.code, re.S)
        self.assertIsNotNone(apply, "没能定位 theme.apply")
        flag = re.search(r"if \(!x \|\| x === 'native'\) \{\s*(\w+) = true;", apply.group(1))
        self.assertIsNotNone(flag, "apply(null/native) 必须设置粘滞 native 标志")
        self.assertRegex(body, r"if \(prefs\.on\)\s*%s = false" % re.escape(flag.group(1)),
                         "重新开启美化必须清掉 apply(null) 设置的同一个 native 标志")

    def test_render_is_the_only_writer(self):
        """🚨 单一所有权的结构保证：只有 render() 调底层 write()。

        write() 是唯一真正往 <style> 落 CSS 的地方。多一个调用点就多一个主题写入者，
        1.0 的双通道缺陷正是这么来的。
        """
        rm = re.search(r"function render\(\) \{.*?\n  \}", self.code, re.S)
        self.assertIsNotNone(rm, "没能定位 render()")
        # 排除 write 的函数定义本身（function write(...)），只看调用点
        calls = [m.start() for m in re.finditer(r"(?<!function )(?<![\w.])write\(", self.code)]
        self.assertTrue(calls, "源码里压根没有 write() 调用——落地口没了")
        outside = [p for p in calls if not (rm.start() <= p <= rm.end())]
        self.assertEqual(
            outside, [],
            "write() 在 render() 之外被调用（偏移 %s）——那会出现第二个主题写入者，"
            "「关闭美化＝完全跟随平台」将再次不可证明" % outside)

    def test_start_is_idempotent(self):
        """chrome 的第二次 start 不得重新读档、不得空 resolve 覆盖。"""
        m = re.search(r"start: function \(name, opt\) \{(.*?)\n    \},", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 theme.start")
        body = m.group(1)
        self.assertIn("boot1()", body, "读档必须走一次性哨兵 boot1()")
        self.assertRegex(body, r"if \(first \|\| !current\) render\(\)",
                         "第二次且已有产物时不该重画")

    def test_boot_envelope_is_recognised_by_apply(self):
        """生成器下发 v:2 信封，apply 必须认得它（否则风格包压根进不来）。"""
        m = re.search(r"function apply\(x\) \{(.*?)\n  \}", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 apply")
        body = m.group(1)
        self.assertIn("x.v === 2", body, "apply 必须按 v:2 判形识别 boot 信封")
        self.assertIn("envelope(x)", body)

    def test_preset_name_regex_matches_generator(self):
        m = re.search(r"var NAME_OK = /(.*?)/;", self.code)
        self.assertIsNotNone(m, "没能定位 NAME_OK")
        # 两侧都限 32 字符上限（首字符 + 31）
        self.assertIn("{0,31}", m.group(1))
        self.assertIn("{0,31}", B.PRESET_NAME_RE.pattern)

    def test_sbk_private_whitelist_excludes_structural_tokens(self):
        m = re.search(r"var SBK_OK = \{(.*?)\};", self.code, re.S)
        self.assertIsNotNone(m, "没能定位 SBK_OK")
        body = m.group(1)
        self.assertNotIn("'z-panel'", body, "z 层安全带属硬约束 12，不许风格包改")
        self.assertNotIn("'tone'", body, "--sbk-tone 是逐条 bar 的局部游标")


class TestConfigNormalize(unittest.TestCase):
    def _cfg(self, **over):
        base = {"beginning": "hi", "statusbar": "{{hud}}"}
        base.update(over)
        return base

    def test_underscore_keys_dropped(self):
        d = B.Diag()
        cfg = B.normalize_config(self._cfg(_comment="x"), "c.json", d)
        self.assertNotIn("_comment", cfg)

    def test_chat_version_must_be_1(self):
        d = B.Diag()
        B.normalize_config(self._cfg(chatVersion=2), "c.json", d)
        self.assertTrue(any("chatVersion" in e for e in d.errors))

    def test_page_depth_must_be_2(self):
        d = B.Diag()
        B.normalize_config(self._cfg(pageDepth=1), "c.json", d)
        self.assertTrue(any("pageDepth" in e for e in d.errors))

    def test_id_base_must_be_negative(self):
        d = B.Diag()
        B.normalize_config(self._cfg(idBase=5), "c.json", d)
        self.assertTrue(any("idBase" in e for e in d.errors))

    def test_missing_beginning_is_error(self):
        d = B.Diag()
        B.normalize_config({"statusbar": "{{hud}}"}, "c.json", d)
        self.assertTrue(any("beginning" in e for e in d.errors))

    def test_defaults_applied(self):
        cfg = B.normalize_config(self._cfg(), "c.json", B.Diag())
        self.assertEqual(cfg["markers"], B.DEFAULT_MARKERS)
        self.assertEqual(cfg["hostId"], "sbk-hud")
        self.assertEqual(cfg["protocolTag"], "状态")

    def test_split_threshold_cannot_exceed_safe_budget(self):
        d = B.Diag()
        cfg = B.normalize_config(self._cfg(splitThreshold=B.MAX_SOURCE_RULE + 1), "c.json", d)
        self.assertEqual(cfg["splitThreshold"], B.DEFAULT_SPLIT_THRESHOLD)
        self.assertTrue(any("固定安全上限" in e for e in d.errors), d.errors)

    def test_non_dict_config_raises(self):
        with self.assertRaises(B.BuildError):
            B.normalize_config([], "c.json", B.Diag())


class TestBuildEndToEnd(unittest.TestCase):
    """临时资源目录 + 最小配置，跑完整 build_document。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.assets = self.tmp / "sbk"
        self.assets.mkdir()
        (self.assets / "base.css").write_text("/* c */\n.sbk-card{color:var(--chat-text)}\n",
                                              encoding="utf-8")
        (self.assets / "core.js").write_text(
            "/* core */\n(function(W){'use strict';W.SBK={version:'1'};})(window);\n",
            encoding="utf-8")
        (self.assets / "theme.js").write_text(
            "(function(W){'use strict';W.SBK.theme={};})(window);\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # 2.0：modes.status 默认 true，一致性守卫要求【同时】有一条产出 .sbk-snap--raw 外壳的
    # 场景规则，否则报错（少了它 hydrate() 永不触发，气泡里 [状态] 原样暴露给用户）。
    # 故最小配置必须自带外壳规则 + 开场白里含协议块（否则外壳规则匹配不到任何东西会另告警）。
    SHELL_RULE = {
        "scriptName": "sbk-snap",
        "findRegex": r"/\[状态\]([\s\S]*?)\[\/状态\]/",
        "replaceString": '<div class="sbk-snap sbk-card sbk-pre sbk-snap--raw">$1</div>',
    }

    def _write_cfg(self, **over):
        cfg = {
            "assetDir": "sbk",
            "beginning": "开场白 {{sbk-css}}{{sbk-core}}{{sbk-boot}} [状态]体力: 1/2[/状态]",
            "statusbar": "{{hud}}",
            "sceneRules": [dict(self.SHELL_RULE)],
        }
        cfg.update(over)
        p = self.tmp / "c.json"
        p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        return p

    def test_produces_six_key_document(self):
        doc, metrics, _, d = B.build_document(self._write_cfg())
        self.assertEqual(set(doc.keys()),
                         {"chatVersion", "pageDepth", "statusbar", "beginning",
                          "personality", "regex_scripts"})
        self.assertEqual(doc["chatVersion"], 1)
        self.assertEqual(doc["pageDepth"], 2)
        self.assertEqual(d.errors, [])

    def test_every_rule_has_exactly_four_keys_and_negative_id(self):
        doc, _, _, _ = B.build_document(self._write_cfg())
        for r in doc["regex_scripts"]:
            self.assertEqual(set(r.keys()),
                             {"id", "scriptName", "findRegex", "replaceString"})
            self.assertIsInstance(r["id"], int)
            self.assertLess(r["id"], 0)

    def test_all_find_regex_are_slash_form(self):
        doc, _, _, _ = B.build_document(self._write_cfg())
        for r in doc["regex_scripts"]:
            self.assertEqual(B.classify_pattern(r["findRegex"])[0], "slash",
                             "%s 不是 slash 形态" % r["scriptName"])

    def test_no_rule_matches_empty_string(self):
        """§5.2：任何一条匹配空串就会被 worker 撤销。"""
        doc, _, _, _ = B.build_document(self._write_cfg())
        for r in doc["regex_scripts"]:
            self.assertFalse(B.matches_empty(r["findRegex"]),
                             "%s 匹配空串" % r["scriptName"])

    def test_rule_layout_order(self):
        doc, _, _, _ = B.build_document(self._write_cfg())
        names = [r["scriptName"] for r in doc["regex_scripts"]]
        # plan.md 2.1：css → core → (ui) → hud → boot；boot 排最后确保内核已定义
        self.assertEqual(names[0], "sbk-css")
        self.assertEqual(names[1], "sbk-core")
        self.assertIn("sbk-hud", names)
        self.assertLess(names.index("sbk-core"), names.index("sbk-boot"))

    def test_missing_ui_assets_warn_and_skip(self):
        """protocol.js/hud.js/ui.js 缺失时跳过并告警，不硬依赖（WP-2/WP-3 未交付）。"""
        doc, _, _, d = B.build_document(self._write_cfg())
        names = [r["scriptName"] for r in doc["regex_scripts"]]
        self.assertNotIn("sbk-ui", names)
        self.assertTrue(any("protocol.js" in w for w in d.warns))
        self.assertEqual(d.errors, [])

    def test_present_ui_assets_are_merged(self):
        (self.assets / "protocol.js").write_text(
            "(function(W){'use strict';W.SBK.parse=function(){};})(window);\n", encoding="utf-8")
        (self.assets / "ui.js").write_text(
            "(function(W){'use strict';W.SBK.ui={};})(window);\n", encoding="utf-8")
        cfg = self._write_cfg(beginning="开场 {{sbk-css}}{{sbk-core}}{{sbk-ui}}{{sbk-boot}}")
        doc, _, _, d = B.build_document(cfg)
        ui = [r for r in doc["regex_scripts"] if r["scriptName"] == "sbk-ui"]
        self.assertEqual(len(ui), 1)
        self.assertIn("SBK.parse", ui[0]["replaceString"])
        self.assertIn("SBK.ui", ui[0]["replaceString"])

    def test_hud_marker_missing_from_statusbar_is_error(self):
        """§5.6 功能栏正则输入是 statusbar 字段自身 → 触发串必须在里面。"""
        cfg = self._write_cfg(statusbar="纯文本没有触发串")
        _, _, _, d = B.build_document(cfg)
        self.assertTrue(any("statusbar" in e and "sbk-hud" in e for e in d.errors))

    def test_toolbar_host_omitted_when_chrome_and_pinned_off(self):
        """2.0：功能栏宿主由 chrome/pinned 决定（已废除的 modes.hud 不再参与）。

        两者都关才省略 sbk-hud——只关一个仍要产出容器，另一个要用它。
        """
        cfg = self._write_cfg(modes={"chrome": False, "pinned": False}, statusbar="无")
        doc, _, _, d = B.build_document(cfg)
        self.assertNotIn("sbk-hud", [r["scriptName"] for r in doc["regex_scripts"]])
        self.assertEqual(d.errors, [])

    def test_chrome_alone_still_emits_toolbar_host(self):
        cfg = self._write_cfg(modes={"chrome": True, "pinned": False})
        doc, _, _, d = B.build_document(cfg)
        self.assertIn("sbk-hud", [r["scriptName"] for r in doc["regex_scripts"]])
        self.assertEqual(d.errors, [])

    def test_strip_comments_shrinks_output(self):
        big = "/* " + "x" * 3000 + " */\n(function(){var a=1;})();\n"
        (self.assets / "core.js").write_text(big, encoding="utf-8")
        cfg = self._write_cfg()
        stripped, _, _, _ = B.build_document(cfg, strip=True)
        kept, _, _, _ = B.build_document(cfg, strip=False)

        def core_len(doc):
            return len([r for r in doc["regex_scripts"]
                        if r["scriptName"] == "sbk-core"][0]["replaceString"])
        self.assertLess(core_len(stripped), core_len(kept) - 2900)

    def test_beginning_over_4000_is_error(self):
        cfg = self._write_cfg(beginning="{{sbk-css}}{{sbk-core}}{{sbk-boot}}" + "字" * 4000)
        _, _, _, d = B.build_document(cfg)
        self.assertTrue(any("beginning" in e and "4000" in e for e in d.errors))

    def test_statusbar_over_200_is_error(self):
        cfg = self._write_cfg(statusbar="{{hud}}" + "字" * 200)
        _, _, _, d = B.build_document(cfg)
        self.assertTrue(any("statusbar" in e and "200" in e for e in d.errors))

    def test_scene_rule_passes_through(self):
        # 外壳必须带 .sbk-snap--raw：只带基类 .sbk-snap 会被一致性守卫按 A2 判错
        cfg = self._write_cfg(sceneRules=[{
            "scriptName": "snap",
            "findRegex": r"/\[状态\]([\s\S]*?)\[\/状态\]/",
            "replaceString": '<div class="sbk-snap sbk-snap--raw">$1</div>',
        }], beginning="开场 {{sbk-css}}{{sbk-core}}{{sbk-boot}} [状态]体力: 1/2[/状态]")
        doc, _, _, d = B.build_document(cfg)
        self.assertIn("snap", [r["scriptName"] for r in doc["regex_scripts"]])
        self.assertEqual(d.errors, [])
        self.assertEqual([w for w in d.warns if "永远不会出现" in w], [])

    def test_unreferenced_visible_marker_warns(self):
        cfg = self._write_cfg(sceneRules=[{
            "scriptName": "orphan",
            "findRegex": "/\\{\\{nobody\\}\\}/",
            "replaceString": "<div>x</div>",
        }])
        _, _, _, d = B.build_document(cfg)
        self.assertTrue(any("orphan" in w and "永远不会出现" in w for w in d.warns))

    def test_scene_rule_double_underscore_is_error(self):
        """§5.6：__ 前缀整条丢弃。"""
        cfg = self._write_cfg(sceneRules=[{
            "scriptName": "__hidden", "findRegex": "/\\{\\{x\\}\\}/", "replaceString": "y"}])
        _, _, _, d = B.build_document(cfg)
        self.assertTrue(any("__" in e for e in d.errors))

    def test_output_is_valid_json_roundtrip(self):
        doc, _, _, _ = B.build_document(self._write_cfg())
        text = B.dumps_sbk(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertNotIn("</script>", text)      # 全部转义成 <\/script>

    def test_report_renders(self):
        doc, metrics, assets, d = B.build_document(self._write_cfg())
        rep = B.render_report(doc, metrics, assets, d, verbose=True)
        self.assertIn("SBK 构建报告", rep)
        self.assertIn("sbk-core", rep)
        self.assertIn("validate.py", rep)

    def test_auto_split_end_to_end(self):
        """三件套合计超阈值 → sbk-ui-1 / sbk-ui-2，顺序 protocol → hud → ui。"""
        (self.assets / "protocol.js").write_text(
            "(function(W){W.SBK.parse=function(){};var p='%s';})(window);\n" % ("x" * 5000),
            encoding="utf-8")
        (self.assets / "hud.js").write_text(
            "(function(W){W.SBK.ui=W.SBK.ui||{};var h='%s';})(window);\n" % ("x" * 9000),
            encoding="utf-8")
        (self.assets / "ui.js").write_text(
            "(function(W){W.SBK.ui=W.SBK.ui||{};var u='%s';})(window);\n" % ("x" * 17000),
            encoding="utf-8")
        doc, _, _, d = B.build_document(self._write_cfg())
        names = [r["scriptName"] for r in doc["regex_scripts"]]
        self.assertIn("sbk-ui-1", names)
        self.assertIn("sbk-ui-2", names)
        self.assertNotIn("sbk-ui", names)
        # 数组序 = 装载顺序
        self.assertLess(names.index("sbk-ui-1"), names.index("sbk-ui-2"))
        blob = "".join(r["replaceString"] for r in doc["regex_scripts"])
        self.assertLess(blob.index("SBK.parse"), blob.index("var u="))
        # 每条都在固定安全预算内，且匹配式唯一且 slash 形态
        ui = [r for r in doc["regex_scripts"] if r["scriptName"].startswith("sbk-ui")]
        for r in ui:
            self.assertLessEqual(len(r["replaceString"]), B.MAX_SOURCE_RULE)
            self.assertEqual(B.classify_pattern(r["findRegex"])[0], "slash")
        self.assertEqual(len(set(r["findRegex"] for r in ui)), len(ui))
        self.assertEqual(d.errors, [])

    def test_no_split_keeps_single_sbk_ui(self):
        (self.assets / "protocol.js").write_text(
            "(function(W){W.SBK.parse=function(){};})(window);\n", encoding="utf-8")
        doc, _, _, _ = B.build_document(self._write_cfg())
        names = [r["scriptName"] for r in doc["regex_scripts"]]
        self.assertIn("sbk-ui", names)
        self.assertNotIn("sbk-ui-1", names)

    def test_core_also_splits(self):
        """拆条逻辑同样覆盖 sbk-core（core.js + theme.js）。"""
        (self.assets / "core.js").write_text(
            "(function(W){W.SBK={version:'1'};var c='%s';})(window);\n" % ("x" * 12000),
            encoding="utf-8")
        (self.assets / "theme.js").write_text(
            "(function(W){W.SBK.theme={};var t='%s';})(window);\n" % ("x" * 12000),
            encoding="utf-8")
        doc, _, _, _ = B.build_document(self._write_cfg())
        names = [r["scriptName"] for r in doc["regex_scripts"]]
        self.assertIn("sbk-core-1", names)
        self.assertIn("sbk-core-2", names)
        self.assertLess(names.index("sbk-core-1"), names.index("sbk-core-2"))

    def test_split_threshold_configurable(self):
        (self.assets / "protocol.js").write_text(
            "(function(W){var p='%s';})(window);\n" % ("x" * 3000), encoding="utf-8")
        (self.assets / "hud.js").write_text(
            "(function(W){var h='%s';})(window);\n" % ("x" * 3000), encoding="utf-8")
        doc, _, _, _ = B.build_document(self._write_cfg(splitThreshold=4000))
        names = [r["scriptName"] for r in doc["regex_scripts"]]
        self.assertIn("sbk-ui-1", names)
        self.assertIn("sbk-ui-2", names)

    def test_bad_split_threshold_is_error(self):
        _, _, _, d = B.build_document(self._write_cfg(splitThreshold=10))
        self.assertTrue(any("splitThreshold" in e for e in d.errors))

    def test_split_layout_in_report(self):
        (self.assets / "protocol.js").write_text(
            "(function(W){var p='%s';})(window);\n" % ("x" * 3000), encoding="utf-8")
        (self.assets / "hud.js").write_text(
            "(function(W){var h='%s';})(window);\n" % ("x" * 3000), encoding="utf-8")
        doc, metrics, assets, d = B.build_document(self._write_cfg(splitThreshold=4000))
        rep = B.render_report(doc, metrics, assets, d, verbose=True)
        self.assertIn("脚本拆条", rep)
        self.assertIn("protocol.js", rep)
        self.assertIn("{{sbk-ui-1}}", rep)

    def test_split_base_marker_left_in_beginning_warns(self):
        """多箱后 {{sbk-core}} 不再对应规则，留在正文会裸显。"""
        (self.assets / "core.js").write_text(
            "(function(W){W.SBK={version:'1'};var a='%s';})(window);\n" % ("x" * 12000), encoding="utf-8")
        (self.assets / "theme.js").write_text(
            "(function(W){var b='%s';})(window);\n" % ("x" * 12000), encoding="utf-8")
        cfg = self._write_cfg(beginning="正文 {{sbk-core}}\n[状态]\n血量: 1/2\n[/状态]")
        _, _, _, d = B.build_document(cfg)
        self.assertTrue(any("原始基名 marker" in w and "sbk-core" in w for w in d.warns), d.warns)

    def test_missing_config_raises(self):
        with self.assertRaises(B.BuildError):
            B.build_document(self.tmp / "nope.json")

    def test_bad_json_config_raises(self):
        p = self.tmp / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        with self.assertRaises(B.BuildError):
            B.build_document(p)

    def test_cli_writes_file(self):
        out = self.tmp / "out" / "sbk.json"
        rc = B.main([str(self._write_cfg()), "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertTrue(out.is_file())
        json.loads(out.read_text(encoding="utf-8"))

    def test_cli_returns_1_and_skips_write_on_error(self):
        out = self.tmp / "out2" / "sbk.json"
        cfg = self._write_cfg(statusbar="没有触发串")
        rc = B.main([str(cfg), "--out", str(out)])
        self.assertEqual(rc, 1)
        self.assertFalse(out.exists())


SAMPLE_BLOCK = "[状态]\n血量: 1/2\n[/状态]"
ANGLE_BLOCK = "<状态>\n血量: 1/2\n</状态>"


def js_regex_probe(pattern, flags, samples):
    """把 findRegex 交给真 JS 引擎编译并逐个 match，返回 {'ok':bool,'hits':[bool,...]}。

    只看字符串对不对是不够的：漏转义的 `[状态]` 是合法【字符类】，Python 侧也能编译，
    静默匹配「状」「态」任一字符。必须让 new RegExp 真跑一遍才能定性。
    """
    import subprocess
    node = shutil.which("node")
    if not node:
        return None
    src = (
        "const fs=require('fs');const x=JSON.parse(fs.readFileSync(0,'utf8'));"
        "try{const re=new RegExp(x.pattern,x.flags);"
        "const hits=x.samples.map(s=>{re.lastIndex=0;return re.test(s);});"
        "process.stdout.write(JSON.stringify({ok:true,hits}));}"
        "catch(e){process.stdout.write(JSON.stringify({ok:false,message:String(e)}));}"
    )
    payload = json.dumps({"pattern": pattern, "flags": flags, "samples": samples})
    r = subprocess.run([node, "-e", src], input=payload, capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    return json.loads(r.stdout)


class TestProtocolBracketForm(unittest.TestCase):
    """plan.md 已裁决第 9 条：协议标记一律方括号 [状态]…[/状态]。

    尖括号 <状态> 会被 worker 的剥壳正则
    /<\\/?([\\u4e00-\\u9fa5a-zA-Z0-9_]+)(\\s+[^>]*)?>/g 当非白名单标签【整个删掉】。
    正则管线跑在剥壳之前，所以模式 B 的 sbk-snap 还能匹配到；
    但模式 A 的 HUD 从气泡文本兜底读取时标记已经没了 → 解析必然失败。
    """

    GOOD = r"/\[状态\]([\s\S]*?)\[\/状态\]/"

    def test_bracket_pattern_compiles_and_matches_in_js(self):
        kind, body, flags = B.classify_pattern(self.GOOD)
        self.assertEqual(kind, "slash")
        res = js_regex_probe(body, flags, [SAMPLE_BLOCK, ANGLE_BLOCK])
        if res is None:
            self.skipTest("未装 node")
        self.assertTrue(res["ok"], "new RegExp 编译失败: %s" % res.get("message"))
        # 必须匹配方括号块，且【不匹配】尖括号块
        self.assertTrue(res["hits"][0], "方括号形态未匹配 %r" % SAMPLE_BLOCK)
        self.assertFalse(res["hits"][1], "不该匹配尖括号写法")

    def test_unescaped_brackets_become_char_class(self):
        """漏转义的反例：`[状态]` 是字符类，会匹配单个「状」字——静默失效的根源。"""
        res = js_regex_probe(r"\[状态\]", "g", ["状"])
        bad = js_regex_probe(r"[状态]", "g", ["状"])
        if res is None or bad is None:
            self.skipTest("未装 node")
        self.assertFalse(res["hits"][0], "转义后不该匹配单字")
        self.assertTrue(bad["hits"][0], "未转义的 [状态] 确实是字符类（这就是要避免的形态）")

    def test_python_side_agrees(self):
        kind, body, flags = B.classify_pattern(self.GOOD)
        rx = B._js_re_to_py(body, flags)
        self.assertIsNotNone(rx.search(SAMPLE_BLOCK))
        self.assertIsNone(rx.search(ANGLE_BLOCK))
        self.assertEqual(rx.search(SAMPLE_BLOCK).group(1).strip(), "血量: 1/2")

    def test_example_config_uses_bracket_form(self):
        here = Path(__file__).resolve().parent
        cfg_path = here / "sbk.config.example.json"
        if not cfg_path.is_file():
            self.skipTest("示例配置不存在")
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        # 开场白与 persona 的输出约定都必须是方括号
        self.assertIn("[状态]", raw["beginning"])
        self.assertNotIn("<状态>", raw["beginning"])
        self.assertIn("[状态]", raw["personality"])
        self.assertNotIn("<状态>", raw["personality"])
        for sc in raw.get("sceneRules") or []:
            fr = sc.get("findRegex", "")
            if "状态" not in fr:
                continue
            self.assertNotIn("<状态>", fr, "sceneRules 仍在用尖括号")
            self.assertIn(r"\[", fr, "方括号必须转义，否则变成字符类")

    def test_generated_protocol_regex_compiles_and_matches(self):
        """产出物级防回归：协议相关 findRegex 必须真能匹配方括号块、不匹配尖括号块。"""
        here = Path(__file__).resolve().parent
        cfg_path = here / "sbk.config.example.json"
        if not cfg_path.is_file() or not (here / "sbk").is_dir():
            self.skipTest("示例配置或 sbk/ 资源目录不存在")
        doc, _, _, d = B.build_document(cfg_path)
        self.assertEqual(d.errors, [])
        checked = 0
        for r in doc["regex_scripts"]:
            fr = r["findRegex"]
            if "状态" not in fr:
                continue
            checked += 1
            self.assertNotIn("<状态>", fr)
            kind, body, flags = B.classify_pattern(fr)
            self.assertEqual(kind, "slash")
            res = js_regex_probe(body, flags, [SAMPLE_BLOCK, ANGLE_BLOCK])
            if res is None:
                continue
            self.assertTrue(res["ok"], "%s 的 findRegex 无法编译: %s"
                            % (r["scriptName"], res.get("message")))
            self.assertTrue(res["hits"][0], "%s 匹配不到方括号状态块" % r["scriptName"])
            self.assertFalse(res["hits"][1], "%s 不该匹配尖括号写法" % r["scriptName"])
        self.assertGreater(checked, 0, "示例配置里应至少有一条协议规则")


class TestExampleConfig(unittest.TestCase):
    """仓库里的示例配置必须真能跑通。"""

    def test_example_builds_clean(self):
        here = Path(__file__).resolve().parent
        cfg = here / "sbk.config.example.json"
        if not cfg.is_file() or not (here / "sbk").is_dir():
            self.skipTest("示例配置或 sbk/ 资源目录不存在")
        doc, metrics, _, d = B.build_document(cfg)
        self.assertEqual(d.errors, [], "示例配置构建有 ERROR：%s" % d.errors)
        self.assertEqual(doc["chatVersion"], 1)
        self.assertEqual(doc["pageDepth"], 2)
        self.assertTrue(metrics)
        self.assertLessEqual(len(doc["regex_scripts"]), B.HARD["regexList"])
        # 每条规则都必须低于固定编辑器安全预算；匹配式唯一且非空串匹配
        finds = [r["findRegex"] for r in doc["regex_scripts"]]
        self.assertEqual(len(set(finds)), len(finds))
        for r in doc["regex_scripts"]:
            self.assertLessEqual(len(r["replaceString"]), B.MAX_SOURCE_RULE,
                                 "%s 超过固定安全预算" % r["scriptName"])
            self.assertFalse(B.matches_empty(r["findRegex"]))

    def test_real_assets_load_order(self):
        """真实生成物必须保持 ASSET_ORDER 的完整模块顺序。"""
        here = Path(__file__).resolve().parent
        adir = here / "sbk"
        if not (here / "sbk.config.example.json").is_file() or not adir.is_dir():
            self.skipTest("示例配置或 sbk/ 资源目录不存在")
        missing = [n for n in B.ASSET_ORDER if not (adir / n).is_file()]
        self.assertEqual(missing, [], "声明模块尚未交付：%s" % missing)
        doc, _, _, d = B.build_document(here / "sbk.config.example.json")
        self.assertEqual(d.errors, [], d.errors)
        blob = "".join(r["replaceString"] for r in doc["regex_scripts"])
        marks = {
            "core.js": "core ready", "core-store.js": "core-store ready",
            "core-boot.js": "core-boot ready", "theme.js": "theme ready",
            "theme-panel.js": "theme-panel ready", "protocol.js": "protocol ready",
            "hud.js": "hud ready", "hud-render.js": "hud-render ready",
            "ui.js": "ui ready (kit)", "ui-panel.js": "ui-panel ready",
            "ui-nav.js": "ui-nav ready (nav)", "ui-icon.js": "ui-icon ready (icon)",
            "ui-fan.js": "ui-fan ready (fan.place)", "ui-dock.js": "ui-dock ready (dock",
            "ui-bubble.js": "ui-bubble ready (bubble)",
            "ui-inject.js": "ui-inject ready (inject)",
            "ui-codex.js": "ui-codex ready (codex)",
            "ui-map.js": "ui-map ready (map)",
            "ui-stage.js": "stage ready",
        }
        seen = []
        for name in B.ASSET_ORDER:
            self.assertIn(marks[name], blob, "%s 缺 ready 指纹 %r" % (name, marks[name]))
            seen.append((name, blob.index(marks[name])))
        self.assertEqual([n for n, _ in seen], [n for n, _ in sorted(seen, key=lambda x: x[1])],
                         "装载顺序被打乱：%s" % seen)

    def _cfg_for_boot(self):
        """boot_script 需要的最小归一化配置（2.0 三键 modes）。"""
        return {
            "hostId": "sbk-hud",
            "schema": {"fields": [{"key": "体力", "type": "bar"}]},
            "modes": {"status": True, "chrome": True, "pinned": False},
            "pinnedFields": [],
            "protocolTag": "状态",
            "theme": {"dark": {"accent": "#c8a15a"}},
        }

    def test_boot_script_only_calls_methods_core_actually_exports(self):
        """🚨 防回归：boot 脚本调的每个内核方法都必须在 core.js 里真实存在。

        守的是【层间接缝】而非产物形状。生成器曾产出 `S.boot({...})`，而 sbk/ 下
        没有任何 boot 定义 → 守卫 `if(!S||!S.boot)` 命中，静默 return，
        HUD/快照/主题一个都不启动，基座导入后完全不工作。
        各层单测都测不到它：每层只测自己，生成器只测产物形状，没人测「装载后真跑起来」。
        """
        here = Path(__file__).resolve().parent
        src = asset_group_text(B.CORE_ASSETS)
        if not src:
            self.skipTest("SBK core 模块不存在")

        # core.js 的导出面：`var SBK = {…}` 里 4 空格缩进的键，加上 `SBK.x =` 形式的补挂
        exported = set(re.findall(r"^\s{4}(\w+)\s*:", src, re.M))
        exported |= set(re.findall(r"\bSBK\.(\w+)\s*=", src))

        boot_js = B.boot_script(self._cfg_for_boot(), B.Diag())
        called = set(re.findall(r"\b(?:S|SBK)\.(\w+)\s*\(", boot_js))
        called.discard("warn")          # console.warn 那条守卫，不是内核方法
        self.assertIn("boot", called, "boot 脚本竟然没调 SBK.boot——生成器被改坏了")

        missing = sorted(called - exported)
        self.assertEqual(
            missing, [],
            "boot 脚本调用了 core.js 未导出的方法 %s——导入后会命中守卫静默 return，"
            "整个基座不工作。core.js 现有导出：%s" % (missing, sorted(exported)))

    def test_example_schema_uses_authoritative_key_and_real_types(self):
        """示例 schema 必须用权威键名 fields，且 type 只用 hud.js 真实支持的那几种。

        曾经写的是 schema.rows（hud.js 只读 sc.fields → 整体忽略，退化成按模型
        输出顺序全渲染）与 type:"table"（TYPES 里不存在，静默回落 text，多实体表
        渲染不出来）。两个坑都是静默失效、极难排查。
        """
        here = Path(__file__).resolve().parent
        cfg_path = here / "sbk.config.example.json"
        hud = here / "sbk" / "hud.js"
        if not cfg_path.is_file():
            self.skipTest("示例配置不存在")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        schema = cfg.get("schema") or {}
        self.assertIn("fields", schema, "示例 schema 必须用权威键名 fields")
        self.assertNotIn("rows", schema, "示例 schema 不该再用 rows 容错别名")

        if not hud.is_file():
            self.skipTest("sbk/hud.js 不存在")
        # 控件类型真值取自 hud.js 的 TYPES 表本身，不在测试里写死一份会漂移的副本
        body = hud.read_text(encoding="utf-8")
        block = re.search(r"var TYPES = \{(.*?)\n  \};", body, re.S)
        self.assertIsNotNone(block, "没能在 hud.js 里定位 TYPES 表")
        real = set(re.findall(r"^\s{4}(\w+):\s*function", block.group(1), re.M))
        self.assertTrue(real, "TYPES 表解析为空")
        hud_render = here / "sbk" / "hud-render.js"
        hud_source = body + ("\n" + hud_render.read_text(encoding="utf-8") if hud_render.is_file() else "")
        # 版面项（section）故意不在 TYPES 表里：它由渲染模块的 tree() 分组游标处理。
        layout = set(re.findall(r"\.type === '(\w+)'", hud_source))
        self.assertIn("section", layout,
                      "没能从 hud.js 解析出版面项 section；若它已改名，请同步本断言的推导方式")
        real |= layout
        for f in schema["fields"]:
            t = f.get("type")
            if t is None:
                continue
            self.assertIn(t, real,
                          "示例配置用了 hud.js 不支持的控件类型 %r（真实支持：%s）；"
                          "写表外的名字会静默回落成 text" % (t, sorted(real)))

    def test_example_snapshot_rule_is_hydratable(self):
        """模式 B 的场景规则产物必须带 .sbk-snap--raw，否则 hydrate() 永不触发。

        hud.js 的 hydrate 靠 SBK.dom.all(root,'.sbk-snap--raw') 找待升级节点。
        少这个类，气泡里只会留一段纯文本，「结构化渲染由 snapshot() 接管」成空话。
        """
        here = Path(__file__).resolve().parent
        cfg_path = here / "sbk.config.example.json"
        if not cfg_path.is_file():
            self.skipTest("示例配置不存在")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        snaps = [s for s in (cfg.get("sceneRules") or [])
                 if isinstance(s, dict) and "snap" in str(s.get("scriptName", ""))]
        if not snaps:
            self.skipTest("示例配置没有快照场景规则")
        for s in snaps:
            rs = s["replaceString"]
            self.assertIn("sbk-snap--raw", rs,
                          "%s 的产物缺 .sbk-snap--raw，hydrate() 找不到它" % s["scriptName"])
            self.assertIn("sbk-snap", rs, "根元素必须带 .sbk-snap（硬约束 11）")

    def test_ui_assets_declared_in_load_order(self):
        """资源清单是唯一装载顺序，新增模块必须插在依赖之后、消费者之前。"""
        self.assertEqual(B.CORE_ASSETS,
                         ("core.js", "core-store.js", "core-boot.js", "theme.js", "theme-panel.js"))
        self.assertEqual(B.UI_ASSETS,
                         ("protocol.js", "hud.js", "hud-render.js", "ui.js", "ui-panel.js",
                          "ui-nav.js", "ui-icon.js", "ui-fan.js", "ui-dock.js", "ui-bubble.js",
                          "ui-inject.js", "ui-codex.js", "ui-map.js",
                          "ui-stage.js"))
        self.assertEqual(B.ASSET_ORDER, B.CORE_ASSETS + B.UI_ASSETS)
        self.assertLess(B.CORE_ASSETS.index("core-store.js"), B.CORE_ASSETS.index("core-boot.js"))
        self.assertLess(B.CORE_ASSETS.index("theme.js"), B.CORE_ASSETS.index("theme-panel.js"))
        self.assertLess(B.UI_ASSETS.index("hud.js"), B.UI_ASSETS.index("hud-render.js"))
        self.assertLess(B.UI_ASSETS.index("ui.js"), B.UI_ASSETS.index("ui-panel.js"))
        self.assertLess(B.UI_ASSETS.index("ui-panel.js"), B.UI_ASSETS.index("ui-stage.js"))
        # 侧边栏一族的依赖方向。dock 消费 nav/icon/fan，且 chrome() 在 ui-panel 里
        # 反查 SBK.ui.dock 决定入口形态 —— dock 必须晚于 ui-panel 装载，否则
        # chrome() 静默回落成旧的功能栏按钮排（正是「设置按钮镶嵌在页面里」那个观感 bug）。
        for dep in ("ui-nav.js", "ui-icon.js", "ui-fan.js"):
            self.assertLess(B.UI_ASSETS.index(dep), B.UI_ASSETS.index("ui-dock.js"),
                            "%s 必须早于 ui-dock.js，否则 dock 只能吃到兜底退化路径" % dep)
        self.assertLess(B.UI_ASSETS.index("ui-panel.js"), B.UI_ASSETS.index("ui-dock.js"))
        # bubble 是 dock 的 surface:'bubble' 呈现面提供者，也必须先到。
        self.assertLess(B.UI_ASSETS.index("ui-bubble.js"), B.UI_ASSETS.index("ui-stage.js"))
        # 三个扩展组件只依赖 core + ui kit(+nav/icon)，互不依赖，可单独裁剪。
        for ext in ("ui-inject.js", "ui-codex.js", "ui-map.js"):
            self.assertLess(B.UI_ASSETS.index("ui.js"), B.UI_ASSETS.index(ext))
            self.assertLess(B.UI_ASSETS.index(ext), B.UI_ASSETS.index("ui-stage.js"))


class TestModes20(unittest.TestCase):
    """2.0 modes 语义：status/chrome/pinned 三者职责不同（基座2.0设计.md 第二节）。

    1.0 的 {hud, snapshot} 是「两个渲染器渲染同一份 schema」，示例配置两个都开
    → 实机截图里同时出现两个一模一样的状态面板。这些测试守的就是那个缺陷不复发。
    """

    def _norm(self, **cfg):
        d = B.Diag()
        modes, pins = B.normalize_modes(cfg, d)
        return modes, pins, d

    # ---- 默认值 ----
    def test_three_modes_defaults(self):
        modes, pins, d = self._norm()
        self.assertEqual(modes, {"status": True, "chrome": True, "pinned": False})
        self.assertEqual(pins, [])
        self.assertEqual(d.errors, [])

    def test_defaults_never_render_same_data_twice(self):
        """🚨 核心回归：默认配置下只有【一个】状态数据出口。

        status 在气泡内、chrome 不渲染业务数据、pinned 默认关 → 不可能重复。
        """
        modes, _, _ = self._norm()
        outlets = [k for k in ("status", "pinned") if modes[k]]
        self.assertEqual(outlets, ["status"], "状态数据出口必须恰好一个，且是气泡内的 status")
        self.assertTrue(modes["chrome"], "chrome 默认开，但它只放入口按钮，不算数据出口")

    def test_explicit_values_override_defaults(self):
        modes, _, d = self._norm(modes={"status": False, "chrome": False, "pinned": True},
                                 pinnedFields=["体力"])
        self.assertEqual(modes, {"status": False, "chrome": False, "pinned": True})
        self.assertEqual(d.errors, [])

    def test_non_dict_modes_is_error(self):
        _, _, d = self._norm(modes=["status"])
        self.assertTrue(any("modes 必须是对象" in e for e in d.errors))

    def test_unknown_mode_key_warns(self):
        _, _, d = self._norm(modes={"sidebar": True})
        self.assertTrue(any("无法识别的 modes 键" in w and "sidebar" in w for w in d.warns))

    # ---- pinnedFields 校验 ----
    def test_pinned_on_without_fields_is_error(self):
        """pinned 开但没配字段 → boot 会静默跳过整个模式，生成期就该拦住。"""
        _, pins, d = self._norm(modes={"pinned": True})
        self.assertEqual(pins, [])
        self.assertTrue(any("modes.pinned 已开" in e and "pinnedFields 为空" in e
                            for e in d.errors))

    def test_pinned_with_status_both_on_still_requires_fields(self):
        """status 与 pinned 同时开是合法的（形态不同），但 pinnedFields 仍必填。"""
        modes, _, d = self._norm(modes={"status": True, "pinned": True})
        self.assertTrue(modes["status"] and modes["pinned"])
        self.assertTrue(any("pinnedFields 为空" in e for e in d.errors))

    def test_pinned_over_three_fields_is_error(self):
        _, pins, d = self._norm(modes={"pinned": True},
                                pinnedFields=["体力", "灵力", "银钱", "好感"])
        self.assertEqual(len(pins), B.PIN_MAX)
        self.assertEqual(pins, ["体力", "灵力", "银钱"])
        self.assertTrue(any("pinnedFields 有 4 项" in e for e in d.errors))

    def test_pinned_fields_dedup_and_trim(self):
        _, pins, _ = self._norm(modes={"pinned": True},
                                pinnedFields=[" 体力 ", "体力", "灵力"])
        self.assertEqual(pins, ["体力", "灵力"])

    def test_pinned_field_not_in_schema_is_error(self):
        _, _, d = self._norm(modes={"pinned": True}, pinnedFields=["不存在"],
                             schema={"fields": [{"key": "体力"}, {"key": "灵力"}]})
        self.assertTrue(any("不在 schema.fields 的 key 里" in e and "不存在" in e
                            for e in d.errors))

    def test_pinned_field_in_schema_is_clean(self):
        _, _, d = self._norm(modes={"pinned": True}, pinnedFields=["体力"],
                             schema={"fields": [{"key": "体力"}, {"key": "灵力"}]})
        self.assertEqual(d.errors, [])

    def test_no_schema_fields_skips_key_check(self):
        """没有 schema.fields 是合法的（靠模型输出顺序全渲染）→ 不猜、不误报。"""
        _, _, d = self._norm(modes={"pinned": True}, pinnedFields=["体力"])
        self.assertEqual(d.errors, [])

    def test_fields_without_pinned_warns(self):
        _, _, d = self._norm(pinnedFields=["体力"])
        self.assertTrue(any("modes.pinned 是 false" in w for w in d.warns))

    def test_bad_pinned_fields_type_is_error(self):
        _, _, d = self._norm(modes={"pinned": True}, pinnedFields="体力,灵力")
        # 字符串按单项容错，不报类型错
        self.assertEqual(d.errors, [])
        _, _, d2 = self._norm(modes={"pinned": True}, pinnedFields={"a": 1})
        self.assertTrue(any("pinnedFields 必须是数组" in e for e in d2.errors))

    def test_empty_string_field_is_error(self):
        _, pins, d = self._norm(modes={"pinned": True}, pinnedFields=["体力", "  "])
        self.assertEqual(pins, ["体力"])
        self.assertTrue(any("非空字符串" in e for e in d.errors))

    # ---- 旧键别名归一化 ----
    def test_legacy_snapshot_maps_to_status_with_warning(self):
        modes, _, d = self._norm(modes={"snapshot": False})
        self.assertFalse(modes["status"])
        self.assertTrue(any("modes.snapshot 是 1.0 的名字" in w for w in d.warns))

    def test_legacy_hud_true_maps_to_pinned_and_warns_semantics_changed(self):
        """🚨 hud→pinned 不是等价替换，告警必须说清形态变了。"""
        modes, _, d = self._norm(modes={"hud": True}, pinnedFields=["体力"])
        self.assertTrue(modes["pinned"])
        hit = [w for w in d.warns if "modes.hud 在 2.0 已移除" in w]
        self.assertTrue(hit, "hud=true 必须告警")
        self.assertIn("语义【变了】", hit[0])
        self.assertIn("单行精简条", hit[0])

    def test_legacy_hud_without_fields_degrades_to_warning(self):
        """🚨 老 config 不该直接报错：1.0 的配置里本就没有 pinnedFields 这个字段。

        别名间接开的 pinned + 无字段 → warn；显式 pinned:true + 无字段 → err。
        """
        _, _, d = self._norm(modes={"hud": True})
        self.assertEqual(d.errors, [], "旧 hud 别名不该让老配置构建失败")
        self.assertTrue(any("由旧键 modes.hud 映射而来" in w for w in d.warns))

    def test_explicit_pinned_without_fields_still_errors(self):
        """反面：显式写 pinned:true 却不配字段，是真配置错，必须报错。"""
        _, _, d = self._norm(modes={"pinned": True})
        self.assertTrue(any("modes.pinned 已开" in e for e in d.errors))
        self.assertEqual([w for w in d.warns if "由旧键" in w], [])

    def test_legacy_hud_false_warns_but_keeps_default(self):
        modes, _, d = self._norm(modes={"hud": False})
        self.assertFalse(modes["pinned"])
        self.assertTrue(any("它本来就是 false" in w for w in d.warns))

    def test_legacy_pair_normalizes_to_single_outlet(self):
        """1.0 那份「两个都开」的老配置：归一化后 status 开、pinned 开（显式告警过），
        但两者形态不同，不再是同一份面板渲染两遍。"""
        modes, _, d = self._norm(modes={"hud": True, "snapshot": True},
                                 pinnedFields=["体力"])
        self.assertTrue(modes["status"])
        self.assertTrue(modes["pinned"])
        self.assertEqual(len([w for w in d.warns if "modes.hud" in w]), 1)
        self.assertEqual(d.errors, [])

    def test_new_key_wins_over_legacy_alias(self):
        modes, _, d = self._norm(modes={"snapshot": True, "status": False})
        self.assertFalse(modes["status"], "显式新键优先于旧别名")
        self.assertEqual([w for w in d.warns if "1.0 的名字" in w], [])


class TestDualModeGuard(unittest.TestCase):
    """一致性守卫：modes.status 与「产出 .sbk-snap--raw 外壳的场景规则」必须同时在/同时不在。

    判定用的类名【从 hud.js 的 hydrate() 实际读出】，不写死——将来 WP-A 改类名，
    守卫会跟着改，不会漂移成「校验通过但实机不升级」。
    """

    ADIR = Path(__file__).resolve().parent / "sbk"
    SHELL = '<div class="sbk-snap sbk-card sbk-pre sbk-snap--raw">$1</div>'
    FR = r"/\[状态\]([\s\S]*?)\[\/状态\]/"

    def _cfg(self, status=True, pinned=False, scenes=()):
        return {"modes": {"status": status, "chrome": True, "pinned": pinned},
                "protocolTag": "状态", "assetDir": self.ADIR, "sceneRules": list(scenes)}

    def _run(self, cfg):
        d = B.Diag()
        info = B.check_dual_mode(cfg, d, self.ADIR)
        return info, d

    def _rule(self, rs, name="sbk-snap", fr=None):
        return {"scriptName": name, "findRegex": fr or self.FR, "replaceString": rs}

    # ---- 选择器来源 ----
    def test_hydrate_class_is_read_from_hud_renderer(self):
        """守卫类名真值优先来自拆分后的 hud-render.js。"""
        if not (self.ADIR / "hud-render.js").is_file():
            self.skipTest("sbk/hud-render.js 不存在")
        cls, found = B.hydrate_class(self.ADIR)
        self.assertTrue(found, "没能从 HUD 渲染模块读出升级选择器")
        self.assertEqual(cls, "sbk-snap--raw")
        src = (self.ADIR / "hud-render.js").read_text(encoding="utf-8")
        self.assertIn("dom.all(root, '.%s')" % cls, src)

    def test_missing_hud_js_falls_back_and_warns(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            d = B.Diag()
            cls, found = B.hydrate_class(tmp, d)
            self.assertEqual(cls, B.HYDRATE_CLASS_FALLBACK)
            self.assertFalse(found)
            self.assertTrue(any("没能从" in w for w in d.warns))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ---- 正例 ----
    def test_status_on_with_shell_is_clean(self):
        _, d = self._run(self._cfg(scenes=[self._rule(self.SHELL)]))
        self.assertEqual(d.errors, [])
        self.assertEqual(d.warns, [])

    def test_status_off_without_scenes_is_clean(self):
        """两样都不在 = 一致。此时连 hud.js 都不读。"""
        info, d = self._run(self._cfg(status=False, pinned=True))
        self.assertEqual(d.errors, [])
        self.assertIsNone(info["cls"])

    # ---- 反例 A：status 开但外壳缺失/不全 ----
    def test_status_on_without_shell_is_error(self):
        info, d = self._run(self._cfg(scenes=[]))
        self.assertTrue(any("modes.status 已开" in e and "没有任何一条产出" in e
                            for e in d.errors))
        # 文案必须给出可直接粘贴的修法
        self.assertTrue(any("sbk-snap--raw" in e and "$1" in e for e in d.errors))
        self.assertEqual(info["shells"], [])

    def test_shell_with_base_class_only_is_error(self):
        """最阴的一种：外观像渲染成卡片了，但 hydrate 命中不到，结构化渲染永不接管。"""
        info, d = self._run(self._cfg(
            scenes=[self._rule('<div class="sbk-snap sbk-pre">$1</div>')]))
        self.assertTrue(any("缺 .sbk-snap--raw" in e for e in d.errors))
        self.assertEqual(info["baseOnly"], ["sbk-snap"])

    def test_shell_without_backref_warns(self):
        info, d = self._run(self._cfg(
            scenes=[self._rule('<div class="sbk-snap sbk-snap--raw">状态</div>')]))
        self.assertEqual(d.errors, [])
        self.assertTrue(any("没有 $1/$& 之类的回填" in w for w in d.warns))
        self.assertEqual(info["shells"], ["sbk-snap"])

    def test_shell_regex_missing_protocol_tag_warns(self):
        _, d = self._run(self._cfg(scenes=[
            self._rule(self.SHELL, fr=r"/\[STATUS\]([\s\S]*?)\[\/STATUS\]/")]))
        self.assertTrue(any("不含协议标签" in w for w in d.warns))

    # ---- 反例 B：status 关但外壳还在 ----
    def test_shell_present_while_status_off_is_error(self):
        _, d = self._run(self._cfg(status=False, pinned=True,
                                   scenes=[self._rule(self.SHELL)]))
        self.assertTrue(any("modes.status 是 false" in e and "死壳" in e
                            for e in d.errors))

    # ---- 反例 B2：没有任何数据出口 ----
    def test_no_data_outlet_warns_and_chrome_does_not_count(self):
        """chrome 开着也不算数据出口——它只放入口按钮，不渲染业务数据。"""
        _, d = self._run(self._cfg(status=False, pinned=False))
        hit = [w for w in d.warns if "没有任何渲染出口" in w]
        self.assertTrue(hit)
        self.assertIn("modes.chrome 不算出口", hit[0])

    def test_pinned_alone_is_an_outlet_so_no_warning(self):
        _, d = self._run(self._cfg(status=False, pinned=True))
        self.assertEqual([w for w in d.warns if "没有任何渲染出口" in w], [])

    def test_class_matching_is_token_based(self):
        """按 token 比而非子串比：`sbk-snap--raw` 的子串含 `sbk-snap`，
        但选择器 .sbk-snap 并不命中它 → 子串比会漏掉「缺基类」这种真缺陷。"""
        _, d = self._run(self._cfg(
            scenes=[self._rule('<div class="sbk-snap--raw">$1</div>')]))
        self.assertEqual(d.errors, [], "只带升级类是合法的（基类缺失由 base.css 层面另论）")


class TestBootPayload(unittest.TestCase):
    """boot 载荷形状：生成器投喂什么，core.js 的 boot 就得认什么。"""

    def _payload(self, **over):
        cfg = {
            "hostId": "sbk-hud",
            "schema": {"fields": [{"key": "体力", "type": "bar"}]},
            "modes": {"status": True, "chrome": True, "pinned": False},
            "pinnedFields": [],
            "protocolTag": "状态",
            "theme": None,
        }
        cfg.update(over)
        js = B.boot_script(cfg, B.Diag())
        m = re.search(r"S\.boot\((\{.*\})\);\}\)\(", js, re.S)
        self.assertIsNotNone(m, "没能从 boot 脚本里抠出载荷 JSON：%s" % js)
        return json.loads(m.group(1)), js

    def test_payload_keys_are_exactly_the_contract(self):
        p, _ = self._payload()
        self.assertEqual(set(p.keys()),
                         {"hostId", "schema", "modes", "pinnedFields",
                          "protocolTag", "theme"})

    def test_payload_carries_three_modes(self):
        p, _ = self._payload()
        self.assertEqual(set(p["modes"].keys()), {"status", "chrome", "pinned"})
        self.assertNotIn("hud", p["modes"], "1.0 的 hud 键不该再出现在载荷里")
        self.assertNotIn("snapshot", p["modes"])

    def test_pinned_fields_always_present_even_when_empty(self):
        """载荷形状稳定，便于对着 sbk.json 自查。"""
        p, _ = self._payload()
        self.assertEqual(p["pinnedFields"], [])
        p2, _ = self._payload(modes={"status": True, "chrome": True, "pinned": True},
                              pinnedFields=["体力", "灵力"])
        self.assertEqual(p2["pinnedFields"], ["体力", "灵力"])

    def test_boot_is_the_only_entry_called(self):
        _, js = self._payload()
        called = set(re.findall(r"\bS\.(\w+)\s*\(", js))
        self.assertEqual(called, {"boot"}, "boot 规则只许调 SBK.boot（裁决 10）")

    def test_core_js_exports_every_key_the_payload_uses(self):
        """🚨 层间接缝：core.js 的 boot 必须真的读载荷里的每个键。

        守的是「生成器投喂了但内核不读」这类静默失效——1.0 的 modes.hud 就是这么
        变成死键的（改名后生成器还在发，boot 已经不认了）。
        """
        core = asset_group_text(("core.js", "core-store.js", "core-boot.js"))
        if not core:
            self.skipTest("SBK core 模块不存在")
        src = core
        p, _ = self._payload()
        for k in p:
            self.assertRegex(src, r"\bo\.%s\b" % re.escape(k),
                             "core.js 的 boot 没读载荷键 %r——生成器白发，功能静默不启动" % k)

    def test_core_js_no_longer_reads_retired_mode_keys(self):
        """反向守卫：core.js 不该再有 modes.hud / modes.snapshot 的读取分支。

        必须先剥注释【与字符串字面量】再查：别名兼容层的告警文案里本就含
        "modes.hud is gone in 2.0" 这类字样，按裸文本查会误报。
        """
        source = asset_group_text(("core.js", "core-store.js", "core-boot.js"))
        if not source:
            self.skipTest("SBK core 模块不存在")
        code = B.strip_js_comments(source)
        code = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", code)      # 单引号串（core.js 全用单引号）
        code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', code)
        # 只禁【modes 对象上】的点取值。SBK.ui.snapshot 是合法的——气泡内渲染器在
        # hud.js 里仍叫 snapshot，被 status 模式调用；那是层名，不是 modes 键。
        for bad in (r"\bmd\.hud\b", r"\bmodes\.hud\b",
                    r"\bmd\.snapshot\b", r"\bmodes\.snapshot\b"):
            self.assertNotRegex(code, bad, "core.js 仍在读已废除的 modes 键：%s" % bad)
        self.assertRegex(code, r"\bmd\.status\b", "boot 必须读 modes.status")
        self.assertRegex(code, r"\bmd\.chrome\b", "boot 必须读 modes.chrome")
        self.assertRegex(code, r"\bmd\.pinned\b", "boot 必须读 modes.pinned")

    def test_pinned_host_is_separate_from_chrome_host(self):
        """🚨 精简条重绘会清空自己宿主的全部子节点。

        若与 chrome 共用 #sbk-hud，第一次 state 变化就把入口按钮全擦掉 →
        boot 必须给 pinned 派生一个独立宿主 id。
        """
        source = asset_group_text(("core.js", "core-store.js", "core-boot.js"))
        if not source:
            self.skipTest("SBK core 模块不存在")
        code = B.strip_js_comments(source)
        # 按行抓：实参是 (o.hostId || 'sbk-hud') + '-pin'，含括号，不能用 [^)]* 收尾
        m = re.search(r"pinned\(pins,(.*)$", code, re.M)
        self.assertIsNotNone(m, "没能定位 boot 里的 pinned(...) 调用")
        self.assertIn("-pin", m.group(1),
                      "pinned 的宿主 id 必须与 chrome 区分（期望形如 hostId + '-pin'），"
                      "当前实参：%s" % m.group(1).strip())

    def test_pin_max_matches_core_js(self):
        """PIN_MAX 在生成器与 core.js 各有一份 → 漂移了会「校验放行 3 项、运行时截成 2 项」。"""
        source = asset_group_text(("core.js", "core-store.js", "core-boot.js"))
        if not source:
            self.skipTest("SBK core 模块不存在")
        m = re.search(r"var PIN_MAX = (\d+)", source)
        self.assertIsNotNone(m, "没能在 core 模块里定位 PIN_MAX")
        self.assertEqual(int(m.group(1)), B.PIN_MAX,
                         "build_sbk.PIN_MAX 与运行时 PIN_MAX 不一致")

    def test_core_js_defaults_match_generator_defaults(self):
        """两侧默认值也必须一致：生成器不发 modes 时，boot 自己的默认得是同一套。"""
        source = asset_group_text(("core.js", "core-store.js", "core-boot.js"))
        if not source:
            self.skipTest("SBK core 模块不存在")
        m = re.search(r"var MODES = \{([^}]*)\}", source)
        self.assertIsNotNone(m, "没能在 core 模块里定位 MODES 默认表")
        got = dict(re.findall(r"(\w+):\s*(true|false)", m.group(1)))
        self.assertEqual({k: v == "true" for k, v in got.items()}, B.DEFAULT_MODES,
                         "运行时 MODES 与 build_sbk.DEFAULT_MODES 不一致")
        self.assertIn("'hud'", source)


if __name__ == "__main__":
    unittest.main()
