import importlib
import unittest


class HostCssTests(unittest.TestCase):
    def parse(self, css):
        if importlib.util.find_spec('sandbox_host_css') is None:
            self.fail('宿主 CSS 抽取器尚未实现')
        return importlib.import_module('sandbox_host_css').extract_host_css(css)

    def test_open_roots_including_separate_summary_confirmation(self):
        result = self.parse('[data-host="summary"] { color: red } [data-host="summary-confirm"] { color: blue }')
        self.assertEqual(result['roots'], ['summary', 'summary-confirm'])
        self.assertEqual(len(result['rules']), 2)
        self.assertFalse(result['sandbox_css'].strip())
        self.assertFalse(result['diagnostics'])

    def test_closed_and_unknown_roots_do_not_reach_host(self):
        for root in ['sdk-prompt', 'recharge', 'boot-loading', 'sandbox-lost', 'made-up']:
            result = self.parse('[data-host="%s"] { color: red }' % root)
            self.assertFalse(result['css'])
            self.assertTrue(result['diagnostics'])

    def test_sandbox_rules_stay_in_sandbox(self):
        result = self.parse('.my-ui { color: green } [data-chat="root"] { --chat-bg: black } [data-host="models"] { color: red }')
        self.assertIn('.my-ui', result['sandbox_css'])
        self.assertNotIn('data-host', result['sandbox_css'])
        self.assertNotIn('data-chat', result['css'])
        self.assertNotIn('.my-ui', result['css'])

    def test_root_must_be_leftmost_and_cannot_target_siblings(self):
        for selector in ['body [data-host="models"]', '[data-host="models"] + body', '[data-host="models"] ~ *']:
            result = self.parse(selector + ' { color: red }')
            self.assertFalse(result['css'])
            self.assertTrue(result['diagnostics'])

    def test_mixed_selector_is_not_forwarded_wholesale(self):
        result = self.parse('[data-host="models"], body { color: red }')
        self.assertNotIn('body', result['css'])
        self.assertTrue(result['diagnostics'])

    def test_nested_css_and_has_are_not_forwarded(self):
        for css in ['[data-host="models"] { color:red; .item {color: blue} }', '[data-host="models"]:has(button) {color:red}']:
            result = self.parse(css)
            self.assertFalse(result['css'])
            self.assertTrue(result['diagnostics'])

    def test_url_declaration_drops_without_losing_safe_declarations(self):
        result = self.parse('[data-host="models"] { background: URL (https://example.org/a); color: red; border: 1px solid blue }')
        self.assertNotIn('example.org', result['css'])
        self.assertIn('color: red', result['css'])
        self.assertIn('border:', result['css'])
        self.assertTrue(result['diagnostics'])

    def test_comments_cannot_obfuscate_url(self):
        result = self.parse('[data-host="models"] { background: u/**/rl(x); color:red }')
        self.assertNotIn('background', result['css'])
        self.assertIn('color:', result['css'])

    def test_strings_and_functions_do_not_split_declarations(self):
        result = self.parse('[data-host="models"] > .item {font-family:"A;B"; width: min(90vw, 500px); color: var(--chat-modal-text, #fff)}')
        self.assertIn('"A;B"', result['css'])
        self.assertIn('min(90vw, 500px)', result['css'])
        self.assertFalse(result['diagnostics'])

    def test_media_preserves_both_document_scopes(self):
        result = self.parse('@media(max-width: 600px) { [data-host="summary"] {width: 90vw} .my-ui {font-size:16px} }')
        self.assertIn('@media', result['css'])
        self.assertIn('@media', result['sandbox_css'])
        self.assertNotIn('.my-ui', result['css'])
        self.assertNotIn('data-host', result['sandbox_css'])

    def test_malformed_and_escaped_input_fail_closed(self):
        for css in ['[data-host="models"] {color:red', '[data-host="models"] { background:u\\72l(x) }', '[data-host="models"] { color:red }</style><script>alert(1)</script>']:
            result = self.parse(css)
            self.assertTrue(result['diagnostics'])
            self.assertNotIn('<script>', result['css'])
            self.assertNotIn('background:', result['css'])

    def test_platform_text_cannot_be_replaced_with_content(self):
        result = self.parse('[data-host="models"] .title::before {content:"pretend platform text";color:red}')
        self.assertNotIn('content:', result['css'])
        self.assertTrue(result['diagnostics'])


if __name__ == '__main__':
    unittest.main()
