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


class TestPipelinePreview(unittest.TestCase):
    def test_first_message_preview_applies_statusbar_and_beginning_regexes(self):
        obj = {
            "statusbar": "<theme>",
            "beginning": "第一句<choice><ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "主题", "findRegex": "<theme>", "replaceString": "<style>.theme{color:red}</style>"},
                {"scriptName": "选项", "findRegex": "<choice>", "replaceString": "<button>选项A</button>"},
                {"scriptName": "信标", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]\\s*/g", "replaceString": "<span style=\"display:none\">[$1=$2]</span>"},
                {"scriptName": "状态栏", "findRegex": "<ztl>", "replaceString": "<div class=\"z-status-box\">状态栏</div>"},
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
            "statusbar": "",
            "beginning": "正文<ztl><float>",
            "regex_scripts": [
                {"scriptName": "状态栏", "findRegex": "<ztl>", "replaceString": "<div class=\"z-status-box\">状态栏</div>"},
                {"scriptName": "悬浮球", "findRegex": "<float>", "replaceString": "<button class=\"z-float-ball\" style=\"position:fixed;right:0\">球</button>"},
            ],
        }
        html = bp.assemble_preview(obj, "mmd", "t.json")
        self.assertIn("第一句话整合预览", html)
        self.assertIn("状态栏单独预览", html)
        self.assertIn("悬浮组件预览", html)
        self.assertIn("正文", html)
        self.assertIn("z-status-box", html)
        self.assertIn("z-float-ball", html)

    def test_statusbar_panel_keeps_onerror_engine_when_runtime_creates_ui(self):
        obj = {
            "statusbar": "",
            "beginning": "正文<ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "状态栏", "findRegex": "<ztl>", "replaceString": "<img src=\"x\" data-radar-engine=\"1\" onerror=\"this.insertAdjacentHTML('afterend','&lt;div class=z-status-box&gt;状态栏&lt;/div&gt;')\">"},
            ],
        }
        html = bp.assemble_preview(obj, "mmd", "t.json")
        status_panel = html.split("状态栏单独预览", 1)[1].split("悬浮组件预览", 1)[0]
        self.assertIn("data-radar-engine", status_panel)
        self.assertNotIn("（无内容）", status_panel)

    def test_statusbar_panel_keeps_onerror_engine_when_js_contains_gt(self):
        obj = {
            "statusbar": "",
            "beginning": "正文<ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "状态栏", "findRegex": "<ztl>", "replaceString": "<img src=\"x\" onerror=\"if(c>0){var k='data-sid';this.rdrNode=1}\">"},
            ],
        }
        html = bp.assemble_preview(obj, "mmd", "t.json")
        status_panel = html.split("状态栏单独预览", 1)[1].split("悬浮组件预览", 1)[0]
        self.assertIn("rdrNode", status_panel)
        self.assertNotIn("（无内容）", status_panel)

    def test_regex_replacement_preserves_backslashes_without_python_escape_errors(self):
        obj = {
            "statusbar": "",
            "beginning": "[hp=85]",
            "regex_scripts": [
                {"scriptName": "带反斜杠", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]/g", "replaceString": "<span data-re=\"\\\\d+\">[$1=$2]</span>"},
            ],
        }
        rendered = bp.apply_regex_pipeline(obj)
        self.assertIn('data-re="\\d+"', rendered)
        self.assertIn("[hp=85]", rendered)

    def test_dangling_marker_is_reported_as_error(self):
        obj = {
            "statusbar": "<css>",
            "beginning": "正文<missing>",
            "regex_scripts": [
                {"scriptName": "样式", "findRegex": "<css>", "replaceString": "<style></style>"},
            ],
        }
        errors = bp.find_dangling_markers(obj)
        self.assertIn("<missing>", errors)
        self.assertNotIn("<css>", errors)


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
        obj = {"statusbar": "", "beginning": "正文<ball>",
               "regex_scripts": [{"scriptName": "悬浮球", "findRegex": "<ball>",
                                  "replaceString": self.DRAGGABLE_BALL}]}
        _, status, floating = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        self.assertIn("data-float-ball", floating)
        self.assertNotIn("data-float-ball", status)

    def test_slide_drawer_engine_not_misclassified_as_statusbar(self):
        obj = {"statusbar": "", "beginning": "正文<side>",
               "regex_scripts": [{"scriptName": "侧边栏", "findRegex": "<side>",
                                  "replaceString": self.SLIDE_DRAWER}]}
        _, status, floating = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        self.assertIn("data-sidebar", floating)
        self.assertNotIn("data-sidebar", status)

    def test_all_four_components_each_panel_gets_its_engine(self):
        """全局美化(style) + 侧边栏 + 悬浮球 + 状态栏雷达 同场：各引擎不串台。"""
        obj = {
            "statusbar": "<css>",
            "beginning": "正文<side><ball><ztl>\n[hp=85]",
            "regex_scripts": [
                {"scriptName": "全局美化", "findRegex": "<css>", "replaceString": "<style>body{color:red}</style>"},
                {"scriptName": "侧边栏", "findRegex": "<side>", "replaceString": self.SLIDE_DRAWER},
                {"scriptName": "悬浮球", "findRegex": "<ball>", "replaceString": self.DRAGGABLE_BALL},
                {"scriptName": "信标", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]\\s*/g", "replaceString": "<span style=\"display:none\">[$1=$2]</span>"},
                {"scriptName": "状态栏", "findRegex": "<ztl>", "replaceString": self.RADAR},
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
        obj = {"statusbar": "", "beginning": "A<side>B<ball>C<ztl>\n[hp=85]",
               "regex_scripts": [
                   {"scriptName": "侧边栏", "findRegex": "<side>", "replaceString": self.SLIDE_DRAWER},
                   {"scriptName": "悬浮球", "findRegex": "<ball>", "replaceString": self.DRAGGABLE_BALL},
                   {"scriptName": "状态栏", "findRegex": "<ztl>", "replaceString": self.RADAR},
               ]}
        first, _, _ = self._panels(bp.assemble_preview(obj, "mmd", "t.json"))
        # 整合面板保留正文骨架，不残留被抽走引擎的 data-* 属性
        self.assertNotIn("data-float-ball", first)
        self.assertNotIn("data-sidebar", first)


class TestPanorama(unittest.TestCase):
    """全景预览：所有组件组合进单文档，固定输入栏+发送按钮+占位AI气泡。"""

    FOUR = {
        "statusbar": "<css>",
        "beginning": "正文<side><ball><ztl>\n[hp=85]",
        "regex_scripts": [
            {"scriptName": "全局美化", "findRegex": "<css>", "replaceString": "<style>body{color:red}</style>"},
            {"scriptName": "侧边栏", "findRegex": "<side>",
             "replaceString": "<img src=\"x\" data-sidebar=\"1\" style=\"display:none\" onerror=\"(function(e){var d=document.createElement('div');d.id='z-drawer';d.style.cssText='position:fixed;right:0;transform:translateX(100%)';document.body.appendChild(d);e.remove();})(this)\">"},
            {"scriptName": "悬浮球", "findRegex": "<ball>",
             "replaceString": "<img src=\"x\" data-float-ball=\"1\" style=\"display:none\" onerror=\"(function(e){var b=document.createElement('button');b.id='z-fab';b.style.cssText='position:fixed;left:18px;bottom:90px';b.addEventListener('mousedown',function(ev){});document.body.appendChild(b);e.remove();})(this)\">"},
            {"scriptName": "信标", "findRegex": "/\\[([^=\\]]+)=([^\\]]+)\\]\\s*/g", "replaceString": "<span style=\"display:none\">[$1=$2]</span>"},
            {"scriptName": "状态栏", "findRegex": "<ztl>",
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

    def test_panorama_scaffold_survives_oldmmd_not_stripped_as_tested_script(self):
        """脚手架走 img onerror，oldmmd 下不应被 <script> 剥离器裸露成红框源码。"""
        html = bp.assemble_panorama(self.FOUR, "oldmmd", "t.json")
        self.assertIn("data-pano-scaffold", html)
        # 脚手架不是 <script> 标签，不会被 mmd-stripped 红框包裹
        # （被测内容里若真有 <script> 才会裸露，这里脚手架是 img onerror）
        scaffold_idx = html.find("data-pano-scaffold")
        around = html[max(0, scaffold_idx - 200):scaffold_idx]
        self.assertNotIn("mmd-stripped", around)

    def test_panorama_local_array_degrades_gracefully(self):
        """本地酒馆正则数组（无 beginning）：全景退化为片段堆叠，仍含输入栏。"""
        arr = [{"scriptName": "片段", "findRegex": "<x>", "replaceString": "<div class='card'>卡片</div>"}]
        html = bp.assemble_panorama(arr, "st", "t.json")
        self.assertIn("pano-input-bar", html)
        self.assertIn("pano-send", html)
        self.assertIn("card", html)


class TestMainModes(unittest.TestCase):
    """main() --mode 接线：both 产两文件，单一 mode 产一文件。"""

    def _run_main(self, tmpdir, mode):
        import os, sys, json as _json
        src = os.path.join(tmpdir, "fx.json")
        with open(src, "w", encoding="utf-8") as f:
            _json.dump(TestPanorama.FOUR, f, ensure_ascii=False)
        argv = ["build-preview", src, "--platform", "mmd", "--mode", mode]
        old = sys.argv
        sys.argv = argv
        try:
            bp.main()
        finally:
            sys.argv = old
        base = os.path.splitext(src)[0]
        return ("%s-preview-mmd.html" % base, "%s-panorama-mmd.html" % base)

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
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            panels, pano = self._run_main(d, "panorama")
            self.assertFalse(os.path.exists(panels))
            self.assertTrue(os.path.exists(pano))
