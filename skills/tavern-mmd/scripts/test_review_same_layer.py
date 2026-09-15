"""Review orchestration contracts, using real build/verify paths and isolated outputs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from build_same_layer import ASSETS, build
from review_same_layer import load_project, review
from same_layer_preview import preview_release


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mmd-unified-review-')
        self.root = Path(self.temp.name)
        self.project = self.root / 'project.json'
        self.config = dict(platform='mmd', chatVersion=0, source=str(ASSETS), appId='review-test',
                           buildId='review-001', title='本地审核', engine=True, models=True)
        self.write_config()

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self):
        self.project.write_text(json.dumps(self.config, ensure_ascii=False), encoding='utf-8')

    def test_rejects_new_page_and_external_preview_configuration(self):
        for key, value in [('chatVersion', 1), ('chatVersion', False), ('platform', 'mmdsandbox'),
                           ('preview', {'accountKey': 'real-account'}), ('preview', {'messages': [{'role':'system','text':'invalid'}]}),
                           ('allowedActions', ['sendMessage','sendMessage'])]:
            with self.subTest(key=key, value=value):
                config = dict(self.config); config[key] = value
                self.project.write_text(json.dumps(config), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_project(self.project)

    def test_platform_failure_leaves_report_without_preview(self):
        self.config['chatVersion']=1; self.write_config()
        out=self.root/'failed'
        result=review(self.project,out,browser='skip')
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue((out/'review-report.html').exists())
        self.assertFalse((out/'preview').exists())

    @unittest.skipUnless(shutil.which('node'), 'Node required for syntax verification')
    def test_partial_review_freezes_source_and_same_release_for_preview(self):
        out=self.root/'partial'
        result=review(self.project,out,browser='skip')
        self.assertEqual(result['status'],'PARTIAL')
        self.assertEqual(result['steps'][-1]['status'],'NOT RUN')
        self.assertEqual(result['realMmd'],'NOT RUN')
        manifest=json.loads((out/'release/release-manifest.json').read_text(encoding='utf-8'))
        preview=json.loads((out/'preview/preview-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['payloadSha256'],preview['releasePayloadSha256'])
        self.assertEqual(manifest['files']['frame.html'],preview['releaseFrameSha256'])
        inputs=json.loads((out/'review-inputs.json').read_text(encoding='utf-8'))
        for name, digest in inputs['sourceFiles'].items():
            self.assertEqual(hashlib.sha256((out/'source'/name).read_bytes()).hexdigest(),digest)
        before=(out/'review-report.json').read_bytes()
        with self.assertRaises(FileExistsError):
            review(self.project,out,browser='skip')
        self.assertEqual((out/'review-report.json').read_bytes(),before)

    @unittest.skipUnless(shutil.which('node'), 'Node required for syntax verification')
    def test_required_browser_missing_is_failure(self):
        with patch.dict(os.environ, {'PLAYWRIGHT_MODULE':''}):
            result=review(self.project,self.root/'missing-browser',browser='required')
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['steps'][-1]['name'],'浏览器交互审核')

    @unittest.skipUnless(shutil.which('node'), 'Node required for syntax verification')
    def test_invalid_author_script_is_not_given_preview(self):
        source=self.root/'source'; shutil.copytree(ASSETS,source)
        (source/'frame.js').write_text('const broken = ;',encoding='utf-8')
        self.config['source']='source'; self.write_config()
        out=self.root/'bad-script'; result=review(self.project,out,browser='skip')
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['steps'][-1]['name'],'同层载荷审核')
        self.assertFalse((out/'preview').exists())

    def test_preview_refuses_tampered_release(self):
        release=self.root/'release'; build(release,self.config)
        with (release/'frame.html').open('ab') as target:
            target.write(b'not the reviewed frame')
        with self.assertRaisesRegex(ValueError,'不一致'):
            preview_release(release,self.root/'preview')


if __name__=='__main__':
    unittest.main()
