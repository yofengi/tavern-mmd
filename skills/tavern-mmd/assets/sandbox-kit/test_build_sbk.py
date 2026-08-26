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
        """剥注释后必须仍语法有效（已裁决第 1 条：生成时剥注释）。有 node 才断言。"""
        adir = Path(__file__).resolve().parent / "sbk"
        if not adir.is_dir():
            self.skipTest("sbk/ 资源目录不存在")
        if not shutil.which("node"):
            self.skipTest("未装 node")
        for p in sorted(adir.glob("*.js")):
            with self.subTest(asset=p.name):
                d = B.Diag()
                r = B.node_check(B.strip_js_comments(p.read_text(encoding="utf-8")), d, p.name)
                self.assertTrue(r, "%s 剥注释后语法无效: %s" % (p.name, d.errors))


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
    """硬约束 21：findRegex 必须 slash 形态（实机裸字面量不生效）。"""

    def test_slash_ok(self):
        d = B.Diag()
        B.check_slash_form({"findRegex": "/\\{\\{hud\\}\\}/"}, d, "T")
        self.assertEqual(d.errors, [])

    def test_bare_literal_is_error(self):
        d = B.Diag()
        B.check_slash_form({"findRegex": "{{hud}}"}, d, "T")
        self.assertEqual(len(d.errors), 1)
        self.assertIn("21", d.errors[0])

    def test_empty_is_error(self):
        d = B.Diag()
        B.check_slash_form({"findRegex": ""}, d, "T")
        self.assertEqual(len(d.errors), 1)


class TestLengths(unittest.TestCase):
    """事实卡 §6：运行时真值硬限（ERROR）／编辑器 UI 值（WARN）。"""

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

    def test_unsplittable_file_warns(self):
        d = B.Diag()
        B.emit_script_rules(-1, "sbk-ui", "{{sbk-ui}}", [self._e("ui.js", 19000)],
                            18000, d, strip=False)
        self.assertTrue(any("无法再拆" in w for w in d.warns))

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


class TestThemeCss(unittest.TestCase):
    """事实卡 §7.1 / 硬约束 10。"""

    def test_specificity_selector(self):
        css = B.theme_override_css({"accent": "#fff"}, B.Diag())
        # 必须 [data-chat="root"][data-theme="*"] 才是 (0,2,0)，高于平台 (0,1,0)
        self.assertIn('[data-chat="root"][data-theme="dark"]', css)
        self.assertIn('[data-chat="root"][data-theme="light"]', css)
        self.assertNotIn(":root", css)
        self.assertNotIn("!important", css)

    def test_semantic_token_mapping(self):
        css = B.theme_override_css({"accent": "#f00", "muted": "#888"}, B.Diag())
        self.assertIn("--chat-accent:#f00;", css)
        self.assertIn("--chat-text-muted:#888;", css)

    def test_unknown_token_goes_to_sbk_namespace(self):
        css = B.theme_override_css({"onAccent": "#000"}, B.Diag())
        self.assertIn("--sbk-on-accent:#000;", css)

    def test_split_dark_light(self):
        css = B.theme_override_css({"dark": {"accent": "#111"}, "light": {"accent": "#eee"}},
                                   B.Diag())
        self.assertIn('[data-theme="dark"]{--chat-accent:#111;}', css)
        self.assertIn('[data-theme="light"]{--chat-accent:#eee;}', css)

    def test_brace_in_value_is_rejected(self):
        # 扁平 theme 会同时写 dark 与 light 两套 → 同一个坏值被拒两次，属预期
        d = B.Diag()
        css = B.theme_override_css({"accent": "#fff}.evil{color:red"}, d)
        self.assertEqual(len(d.errors), 2)
        self.assertNotIn("evil", css)

    def test_style_close_in_value_is_rejected(self):
        d = B.Diag()
        css = B.theme_override_css({"dark": {"accent": "#fff</style><b>"}}, d)
        self.assertEqual(len(d.errors), 1)
        self.assertNotIn("</style>", css)

    def test_empty_theme_yields_nothing(self):
        self.assertEqual(B.theme_override_css({}, B.Diag()), "")


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

    def _write_cfg(self, **over):
        cfg = {
            "assetDir": "sbk",
            "beginning": "开场白 {{sbk-css}}{{sbk-core}}{{sbk-boot}}",
            "statusbar": "{{hud}}",
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

    def test_hud_mode_off_omits_rule(self):
        cfg = self._write_cfg(modes={"hud": False}, statusbar="无")
        doc, _, _, d = B.build_document(cfg)
        self.assertNotIn("sbk-hud", [r["scriptName"] for r in doc["regex_scripts"]])
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
        cfg = self._write_cfg(sceneRules=[{
            "scriptName": "snap",
            "findRegex": r"/\[状态\]([\s\S]*?)\[\/状态\]/",
            "replaceString": '<div class="sbk-snap">$1</div>',
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
        # 每条都在编辑器上限内，且匹配式唯一且 slash 形态
        ui = [r for r in doc["regex_scripts"] if r["scriptName"].startswith("sbk-ui")]
        for r in ui:
            self.assertLessEqual(len(r["replaceString"]), B.UI_SOFT["content"])
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
        # 每条脚本规则都必须在运行时硬限内；匹配式唯一且非空串匹配
        finds = [r["findRegex"] for r in doc["regex_scripts"]]
        self.assertEqual(len(set(finds)), len(finds))
        for r in doc["regex_scripts"]:
            self.assertLessEqual(len(r["replaceString"]), B.HARD["content"])
            self.assertFalse(B.matches_empty(r["findRegex"]))

    def test_real_assets_load_order(self):
        """真实资源：protocol.js → hud.js → ui.js → ui-stage.js 的装载顺序不能被拆条打乱。

        只断言**已交付**文件之间的相对顺序，未交付的跳过——否则每次新增资源名
        这条测试就整体 skip，反而失去防回归价值。
        """
        here = Path(__file__).resolve().parent
        adir = here / "sbk"
        if not (here / "sbk.config.example.json").is_file() or not adir.is_dir():
            self.skipTest("示例配置或 sbk/ 资源目录不存在")
        present = [n for n in B.UI_ASSETS if (adir / n).is_file()]
        if len(present) < 2:
            self.skipTest("已交付的 UI 资源不足 2 个，无顺序可验")
        doc, _, _, _ = B.build_document(here / "sbk.config.example.json")
        blob = "".join(r["replaceString"] for r in doc["regex_scripts"])
        # 每个文件末尾的 SBK.log('… ready') 是它的装载指纹
        marks = {"protocol.js": "protocol ready", "hud.js": "hud ready",
                 "ui.js": "ui ready", "ui-stage.js": "stage ready"}
        seen = [(n, blob.index(marks[n])) for n in present
                if n in marks and marks[n] in blob]
        self.assertGreaterEqual(len(seen), 2, "至少要认出两个装载指纹")
        # 出现位置必须与 UI_ASSETS 声明顺序一致
        self.assertEqual([n for n, _ in seen],
                         [n for n, _ in sorted(seen, key=lambda x: x[1])],
                         "装载顺序被打乱：%s" % seen)

    def _cfg_for_boot(self):
        """boot_script 需要的最小归一化配置。"""
        return {
            "hostId": "sbk-hud",
            "schema": {"fields": [{"key": "体力", "type": "bar"}]},
            "modes": {"hud": True, "snapshot": True},
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
        core = here / "sbk" / "core.js"
        if not core.is_file():
            self.skipTest("sbk/core.js 不存在")
        src = core.read_text(encoding="utf-8")

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
        """UI_ASSETS 是硬编码列表，顺序即装载顺序，新增文件必须插到正确位置。"""
        self.assertEqual(B.UI_ASSETS, ("protocol.js", "hud.js", "ui.js", "ui-stage.js"))
        self.assertEqual(B.CORE_ASSETS, ("core.js", "theme.js"))
        # ui-stage.js 必须排在 ui.js 之后（WP-3 拆分产物，依赖 ui.js 先挂 SBK.ui）
        self.assertLess(B.UI_ASSETS.index("ui.js"), B.UI_ASSETS.index("ui-stage.js"))


if __name__ == "__main__":
    unittest.main()
