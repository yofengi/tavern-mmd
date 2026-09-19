import importlib
import unittest
from html.parser import HTMLParser

bp = importlib.import_module('build-preview')


class Frames(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.frames = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'iframe' and attrs.get('class') == 'pano-frame':
            self.frames.append(attrs['srcdoc'])


class HostPreviewTests(unittest.TestCase):
    def page(self, css='', profile='chat'):
        card = {'chatVersion': 1, 'pageDepth': 2, 'statusbar': '', 'beginning': '开场白', 'personality': '',
                'regex_scripts': [{'id': -1, 'scriptName': '皮肤', 'findRegex': '/unused/', 'replaceString': '<style>' + css + '</style>'}]}
        return bp.assemble_panorama(card, 'mmdsandbox', 'test.json', sandbox_profile=profile)

    def test_css_only_reaches_its_document(self):
        page = self.page('.author-ui {color:green}[data-host="summary"] {background:tomato}')
        frame = Frames(page).frames[0]
        self.assertNotIn('[data-host="summary"] {background: tomato;', frame)
        self.assertIn('.author-ui', frame)
        self.assertIn('data-preview-host-style="1"', page)
        self.assertIn('[data-host="summary"] {background: tomato;', page)
        self.assertNotIn('data-host="summary"', frame)

    def test_twenty_one_roots_are_outside_the_sandbox(self):
        from sandbox_host_css import load_host_contract
        page = self.page()
        self.assertEqual(len(load_host_contract()['roots']), 21)
        frame = Frames(page).frames[0]
        for name in load_host_contract()['roots']:
            self.assertIn('data-host="%s"' % name, page)
            self.assertNotIn('data-host="%s"' % name, frame)
        self.assertNotIn('data-host="sdk-prompt"', page)

    def test_summary_internal_editor_and_external_confirmation(self):
        page = self.page()
        self.assertIn('summary-ov-edit', page)
        self.assertIn('summary-ov-anchor', page)
        self.assertIn('data-host="summary-confirm"', page)
        self.assertIn('内部结构待验证', page)

    def test_disallowed_host_css_is_diagnosed_not_injected(self):
        page = self.page('[data-host="recharge"] {color:chartreuse}[data-host="summary"] {background:url(https://example.org/a);color:tomato}')
        self.assertNotIn('color: chartreuse', page)
        self.assertNotIn('https://example.org/a', page)
        self.assertIn('filtered-declaration', page)
        self.assertIn('host-root', page)

    def test_thin_does_not_fake_a_host_environment(self):
        page = self.page('[data-host="summary"] {color:red}', 'thin-preview')
        self.assertNotIn('data-preview-host-style="1"', page)
        self.assertNotIn('data-host="summary"', Frames(page).frames[0])
        self.assertIn('瘦预览没有宿主弹窗', page)

    def test_runtime_style_strings_are_not_static_host_styles(self):
        from sandbox_host_preview import split_assets
        source = '<script>window.css=\'<style>[data-host="summary"]{color:red}</style>\';</script>'
        local, host, diagnostics = split_assets(source)
        self.assertEqual(local, source)
        self.assertEqual(host, '')
        self.assertFalse(diagnostics)

    def test_local_css_strings_survive_host_extraction(self):
        from sandbox_host_preview import split_assets
        for css in ['.local::before{content:"<3"}', '.local::before{content:"data-host"}',
                    '.local::before{content:\'[data-host="summary"]\'}']:
            local, host, diagnostics = split_assets('<style>' + css + '[data-host="summary"]{color:red}</style>')
            self.assertIn(css, local)
            self.assertIn('color: red', host)
            self.assertFalse(diagnostics)

    def test_style_identity_and_media_are_preserved(self):
        from sandbox_host_preview import split_assets
        source = '<style id="author-theme" media="print" nonce="demo">.local{color:blue}[data-host="summary"]{color:red}</style>'
        local, host, diagnostics = split_assets(source)
        self.assertIn('<style id="author-theme" media="print" nonce="demo">', local)
        self.assertIn('.local{color:blue}', local)
        self.assertIn('@media print{', host)
        self.assertFalse(diagnostics)

    def test_legacy_fixture_layout_is_outside_frame(self):
        page = self.page()
        frame = Frames(page).frames[0]
        from html import escape
        outer = page.replace(escape(frame, quote=True), '')
        self.assertIn('.pano-host-popup .ph-card{', outer)
        self.assertIn('.pano-host-popup .ph-mi{', outer)
        self.assertNotIn('.pano-host-popup .ph-card{', frame)

    def test_media_attribute_cannot_break_out_of_host_stylesheet(self):
        from sandbox_host_preview import split_assets
        local, host, diagnostics = split_assets('<style media="print &lt;/style&gt;&lt;script&gt;alert(1)&lt;/script&gt;">[data-host="summary"]{color:red}</style>')
        self.assertNotIn('<script>', host)
        self.assertFalse(host)
        self.assertTrue(diagnostics)

    def test_close_all_tool_closes_both_documents(self):
        page = self.page()
        self.assertIn('__sbxPanels.closeAll();if(window.__sbxHostPreview)window.__sbxHostPreview.closeAll()', page)

    def test_composer_hidden_state_has_a_visual_effect(self):
        self.assertIn('[data-chat="root"][data-composer="hidden"] [data-chat="composer"]{display:none}', bp._sandbox_chrome_css())


if __name__ == '__main__':
    unittest.main()
