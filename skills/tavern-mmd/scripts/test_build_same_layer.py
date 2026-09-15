import base64
import json
import tempfile
import shutil
import unittest
from pathlib import Path
from build_same_layer import build, rules_for, sha, utf16_length
from verify_same_layer import verify


class BuildTests(unittest.TestCase):
    def test_payload_roundtrip_and_limits(self):
        source = "const text=" + json.dumps("$& $$ $` $' </script> 中文 🧪\u2028" * 2000, ensure_ascii=False)
        entry, rows, digest = rules_for(source, "test", "build-1")
        self.assertLessEqual(len(rows), 130)
        self.assertLessEqual(utf16_length(entry), 200)
        chunks = []
        for i, row in enumerate(rows[:-1]):
            self.assertEqual(set(row), {"id", "scriptName", "findRegex", "replaceString"})
            self.assertEqual(row["id"], -1)
            self.assertLessEqual(utf16_length(row["replaceString"]), 18000)
            # Decode the embedded JSON object, independently of the builder's chunk list.
            start = row["replaceString"].index('{"index":')
            data, _ = json.JSONDecoder().raw_decode(row["replaceString"][start:])
            self.assertEqual(data["index"], i)
            self.assertEqual(sha(data["text"].encode()), data["hash"])
            chunks.append(data["text"])
        rebuilt = base64.b64decode("".join(chunks)).decode()
        self.assertEqual(rebuilt, source)
        self.assertEqual(sha(rebuilt.encode()), digest)

    @unittest.skipUnless(shutil.which('node'), 'Node required for syntax verification')
    def test_verifier_detects_file_corruption_and_broken_chain(self):
        with tempfile.TemporaryDirectory(prefix="mmd-same-layer-verify-") as temp:
            out = Path(temp)
            config = {"appId": "test", "buildId": "build-1", "engine": True, "title": "示例"}
            manifest = build(out, config)
            self.assertEqual(verify(out)['syntax'], 'PASS')
            frame = (out / 'frame.html').read_bytes()
            (out / 'frame.html').write_bytes(frame + b'broken')
            with self.assertRaisesRegex(ValueError, '文件哈希'):
                verify(out)
            (out / 'frame.html').write_bytes(frame)
            path = out / 'same-layer-mmd.json'
            package = json.loads(path.read_text(encoding='utf-8'))
            package['regex_scripts'][0]['replaceString'] += 'unexpected-next-hop'
            raw = json.dumps(package, ensure_ascii=False).encode()
            path.write_bytes(raw)
            manifest['files'][path.name] = sha(raw)
            (out / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '触发链'):
                verify(out)

    @unittest.skipUnless(shutil.which('node'), 'Node required for syntax verification')
    def test_verifier_rejects_invalid_author_javascript(self):
        with tempfile.TemporaryDirectory(prefix="mmd-same-layer-syntax-") as temp:
            from build_same_layer import ASSETS
            source = Path(temp) / 'source'
            shutil.copytree(ASSETS, source)
            (source / 'frame.js').write_text('const broken = ;', encoding='utf-8')
            out = Path(temp) / 'out'
            build(out, {"appId":"test", "buildId":"bad-js", "engine":False, "title":"示例"}, source)
            with self.assertRaisesRegex(ValueError, '语法错误'):
                verify(out)

    def test_reject_overflow(self):
        with self.assertRaises(ValueError):
            rules_for("x" * 2000000, "test", "build-1")

    def test_production_mock_separation_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="mmd-same-layer-") as temp:
            out = Path(temp)
            config = {"appId": "test", "buildId": "build-1", "engine": True, "title": "示例"}
            manifest = build(out, config, preview=True)
            package = json.loads((out / "same-layer-mmd.json").read_text(encoding="utf-8"))
            self.assertEqual(set(package), {"pageDepth", "statusbar", "beginning", "regex_scripts"})
            self.assertEqual(manifest["adapter"], "native-bridge")
            for name, digest in manifest["files"].items():
                self.assertEqual(sha((out / name).read_bytes()), digest)
            self.assertIn('"mode":"mock"', (out / "preview.html").read_text(encoding="utf-8"))
            self.assertEqual(manifest["evidence"]["realMmd"], "NOT RUN")
            with self.assertRaises(FileExistsError):
                build(out, config, preview=True)


if __name__ == "__main__":
    unittest.main()
