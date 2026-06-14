#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_card_image.py 单元测试。运行: python -m unittest test_make_card_image -v"""
import unittest
import importlib
import json
import struct
import subprocess
import sys
import os
import tempfile

m = importlib.import_module("make_card_image")

PNG_SIG = b"\x89PNG\r\n\x1a\n"


class TestSolidPng(unittest.TestCase):
    def test_solid_png_is_valid_and_parseable(self):
        png = m.buffer_to_png(bytearray(b"\xF5\xEB\xDC" * (8 * 8)), 8, 8)
        self.assertTrue(png.startswith(PNG_SIG))
        types = [c[0] for c in m.read_all_chunks(png)]
        self.assertEqual(types[0], b"IHDR")
        self.assertIn(b"IDAT", types)
        self.assertEqual(types[-1], b"IEND")


def _png():
    return m.buffer_to_png(bytearray(b"\xF5\xEB\xDC" * (8 * 8)), 8, 8)


class TestCharaChunk(unittest.TestCase):
    def test_v2_roundtrip_chara_only(self):
        card = {"spec": "chara_card_v2", "name": "测试"}
        s = json.dumps(card, ensure_ascii=False)
        png = m.inject_text_chunks(_png(), s, is_v3=False)
        types = [c[0] for c in m.read_all_chunks(png)]
        self.assertIn(b"tEXt", types)
        self.assertEqual(json.loads(m.read_chara(png)), card)
        self.assertIsNone(m.read_keyword(png, b"ccv3"))

    def test_v3_roundtrip_chara_and_ccv3(self):
        card = {"spec": "chara_card_v3", "name": "测试"}
        s = json.dumps(card, ensure_ascii=False)
        png = m.inject_text_chunks(_png(), s, is_v3=True)
        self.assertEqual(json.loads(m.read_chara(png)), card)
        self.assertEqual(json.loads(m.read_keyword(png, b"ccv3")), card)

    def test_text_chunk_before_idat(self):
        png = m.inject_text_chunks(_png(), '{"a":1}', is_v3=False)
        types = [c[0] for c in m.read_all_chunks(png)]
        self.assertLess(types.index(b"tEXt"), types.index(b"IDAT"))


class TestDefaultBg(unittest.TestCase):
    def test_default_bg_valid_png_with_text_pixels(self):
        png = m.make_default_bg()
        self.assertTrue(png.startswith(PNG_SIG))
        ihdr = [d for t, d in m.read_all_chunks(png) if t == b"IHDR"][0]
        w, h = struct.unpack(">II", ihdr[:8])
        self.assertEqual((w, h), (m.BG_W, m.BG_H))
        buf = m.make_default_buffer()
        text_px = sum(1 for i in range(0, len(buf), 3)
                      if tuple(buf[i:i + 3]) == m.TEXT_RGB)
        self.assertGreater(text_px, 0)

    def test_label_pixels_in_lower_portion(self):
        buf = m.make_default_buffer()
        ys = [(i // 3) // m.BG_W for i in range(0, len(buf), 3)
              if tuple(buf[i:i + 3]) == m.TEXT_RGB]
        self.assertTrue(ys)
        self.assertGreaterEqual(min(ys), int(m.BG_H * 0.65))
        self.assertLessEqual(max(ys), int(m.BG_H * 0.90))


class TestUserBgPng(unittest.TestCase):
    def test_inject_into_existing_png_roundtrips(self):
        user_png = m.buffer_to_png(bytearray(b"\x10\x20\x30" * (4 * 4)), 4, 4)
        card = {"spec": "chara_card_v2", "name": "U"}
        out = m.embed_png(user_png, json.dumps(card, ensure_ascii=False), is_v3=False)
        self.assertEqual(json.loads(m.read_chara(out)), card)
        ihdr = [d for t, d in m.read_all_chunks(out) if t == b"IHDR"][0]
        self.assertEqual(struct.unpack(">II", ihdr[:8]), (4, 4))

    def test_reinject_replaces_old_chara(self):
        png = m.embed_png(m.make_default_bg(), '{"v":1}', is_v3=False)
        png2 = m.embed_png(png, '{"v":2}', is_v3=False)
        chara_chunks = [d for t, d in m.read_all_chunks(png2)
                        if t == b"tEXt" and d.startswith(b"chara\x00")]
        self.assertEqual(len(chara_chunks), 1)
        self.assertEqual(json.loads(m.read_chara(png2)), {"v": 2})


class TestJpg(unittest.TestCase):
    def _fake_jpg(self):
        # 最小可解析的 JPEG 字节: SOI + APP0 + EOI
        app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        return b"\xff\xd8" + app0 + b"\xff\xd9"

    def test_jpg_com_roundtrip(self):
        card = {"spec": "chara_card_v2", "name": "J"}
        out = m.embed_jpg(self._fake_jpg(), json.dumps(card, ensure_ascii=False))
        self.assertEqual(out[:2], b"\xff\xd8")
        self.assertEqual(json.loads(m.read_jpg_chara(out)), card)

    def test_jpg_requires_soi(self):
        with self.assertRaises(ValueError):
            m.embed_jpg(b"not a jpeg", "{}")


class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "make_card_image.py", *args],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)))

    def test_cli_png_default_bg(self):
        with tempfile.TemporaryDirectory() as d:
            jp = os.path.join(d, "card.json")
            op = os.path.join(d, "out.png")
            with open(jp, "w", encoding="utf-8") as f:
                json.dump({"spec": "chara_card_v2", "name": "C"}, f, ensure_ascii=False)
            r = self._run(jp, "-o", op)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(op, "rb") as f:
                png = f.read()
            self.assertEqual(json.loads(m.read_chara(png))["name"], "C")

    def test_cli_jpg_without_bg_errors(self):
        with tempfile.TemporaryDirectory() as d:
            jp = os.path.join(d, "card.json")
            with open(jp, "w", encoding="utf-8") as f:
                json.dump({"spec": "chara_card_v2"}, f)
            r = self._run(jp, "--format", "jpg")
            self.assertEqual(r.returncode, 1)
            self.assertIn("jpg", r.stderr.lower())

    def test_cli_invalid_json_errors(self):
        with tempfile.TemporaryDirectory() as d:
            jp = os.path.join(d, "bad.json")
            with open(jp, "w", encoding="utf-8") as f:
                f.write("{not json")
            r = self._run(jp)
            self.assertEqual(r.returncode, 1)
