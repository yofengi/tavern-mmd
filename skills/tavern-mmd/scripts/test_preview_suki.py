import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import preview_suki as preview


FILES = {
    "index.html": b'<script src="./sandbox.js"></script><link href="./sandbox.css">',
    "sandbox.js": b"window.stageLoaded = true",
    "sandbox.css": b"body { margin: 0 }",
    "sandbox-zh.js": b"window.dictionaryLoaded = true",
}


class TestSukiPreview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.card = self.make_card("test card")

    def make_card(self, name):
        card = self.root / name
        card.mkdir()
        (card / "card.json").write_text('{"formatVersion":1}', encoding="utf-8")
        return card

    def make_shell(self, name):
        folder = self.root / name
        folder.mkdir()
        for filename, data in FILES.items():
            (folder / filename).write_bytes(data)
        return folder

    def invoke(self, card, *args, exit_code=0):
        output = io.StringIO()
        with redirect_stderr(output), \
                mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("unexpected download")), \
                mock.patch.object(preview, "find_cli", return_value="hearthroom"), \
                mock.patch.object(preview.subprocess, "run", return_value=subprocess.CompletedProcess([], exit_code)) as run:
            result = preview.main([str(card), *args])
        return result, run, output.getvalue()

    def test_two_new_cards_use_same_installed_shell_without_downloading_or_caching(self):
        bundled = Path(preview.__file__).resolve().parents[1] / "assets" / "suki-sandbox" / "dist-sandbox"
        for card in (self.card, self.make_card("another card")):
            result, run, _ = self.invoke(card, "--open")
            self.assertEqual(result, 0)
            args = run.call_args.args[0]
            self.assertEqual(args[args.index("--shell") + 1], str(bundled))
            self.assertIn("--open", args)
            self.assertFalse((card / "preview" / "suki-shell").exists())
        manifest = json.loads((bundled.parent / "source.json").read_text(encoding="utf-8"))
        self.assertEqual(preview.local_id(bundled), manifest["bundleSha256"])

    def test_classic_card_opens_for_compatibility_without_rewriting_rules(self):
        rules = self.card / "rules.json"
        original = b'{"pageMode": "classic", "rules": []}'
        rules.write_bytes(original)
        result, run, notice = self.invoke(self.card, "--check", "--json")
        self.assertEqual(result, 0)
        self.assertIn("--check", run.call_args.args[0])
        self.assertIn("兼容预览", notice)
        self.assertEqual(rules.read_bytes(), original)

    def test_unrecognized_page_mode_does_not_launch(self):
        (self.card / "rules.json").write_text('{"pageMode":"unknown"}', encoding="utf-8")
        result, run, _ = self.invoke(self.card)
        self.assertNotEqual(result, 0)
        run.assert_not_called()

    def test_local_build_and_official_cli_exit_code(self):
        shell = self.make_shell("dist-sandbox")
        result, run, _ = self.invoke(self.card, "--shell", str(shell), "--port", "4317", "--check", "--json", exit_code=7)
        self.assertEqual(result, 7)
        self.assertEqual(run.call_args.args[0], [
            "hearthroom", "card", "preview", str(self.card), "--shell", str(shell), "--port", "4317", "--check", "--json",
        ])

    def test_explicit_old_snapshot_checks_its_content_hash(self):
        snapshot = self.make_shell(preview.bundle_id(FILES))
        self.assertEqual(self.invoke(self.card, "--shell", str(snapshot))[0], 0)
        (snapshot / "sandbox.js").write_bytes(b"changed since it was pinned")
        result, run, error = self.invoke(self.card, "--shell", str(snapshot))
        self.assertNotEqual(result, 0)
        self.assertIn("哈希", error)
        run.assert_not_called()

    def test_incomplete_build_rejects_missing_or_html_dictionary(self):
        shell = self.make_shell("dist-sandbox")
        (shell / "sandbox-zh.js").unlink()
        for payload in (None, b"<!doctype html><title>site</title>"):
            if payload:
                (shell / "sandbox-zh.js").write_bytes(payload)
            result, run, error = self.invoke(self.card, "--shell", str(shell))
            self.assertNotEqual(result, 0)
            self.assertIn("sandbox-zh.js", error)
            run.assert_not_called()

    def test_damaged_bundled_shell_keeps_preview_offline(self):
        shell = self.make_shell("dist-sandbox")
        manifest = {"bundleSha256": preview.bundle_id(FILES)}
        (shell.parent / "source.json").write_text(json.dumps(manifest), encoding="utf-8")
        (shell / "sandbox.js").write_bytes(b"wrong bundle version")
        with mock.patch.object(preview, "BUNDLED_SHELL", shell):
            result, run, error = self.invoke(self.card)
        self.assertNotEqual(result, 0)
        self.assertIn("哈希", error)
        run.assert_not_called()
