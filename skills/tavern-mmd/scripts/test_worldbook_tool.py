#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worldbook_tool.py 单元测试。运行: python -m unittest test_worldbook_tool -v"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import worldbook_tool as wt

TITLE_20 = "这是一个刚好二十个字的世界书条目的标题啊"    # 恰好 20 字，合规边界
TITLE_21 = "这是一个整整二十一个字的世界书条目超长标题"    # 21 字，超限
TITLE_12 = "十二个字的普通标题啊啊啊"                  # 12 字，加 "[e0001] " 前缀后恰好 20
TITLE_13 = "十三个字的普通标题啊啊啊啊"                # 13 字，加前缀后 21，超限


class TestProjectInitAndEntryParsing(unittest.TestCase):
    def test_ensure_project_creates_expected_structure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "工作" / "世界书"
            cfg = wt.ensure_project(root)
            self.assertTrue((root / "worldbook.config.json").exists())
            self.assertTrue((root / "index.md").exists())
            self.assertTrue((root / "notes.md").exists())
            self.assertTrue((root / "entries").is_dir())
            self.assertTrue((root / "drafts").is_dir())
            self.assertTrue((root / "patches").is_dir())
            self.assertTrue((root / "archive").is_dir())
            self.assertEqual(cfg["next_entry_number"], 1)
            self.assertEqual(cfg["entry_id_prefix"], "e")
            self.assertGreaterEqual(len(cfg["layers"]), 5)
            self.assertTrue((root / "entries" / "00-世界设定层").is_dir())
            self.assertTrue((root / "entries" / "30-角色层").is_dir())

    def test_parse_and_write_entry_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "010-e0001-世界观总纲.md"
            meta = {
                "entry_id": "e0001",
                "title": "世界观总纲",
                "layer": "00-世界设定层",
                "constant": True,
                "position": 0,
                "keys": [],
                "summary": "世界类型、时代、核心矛盾",
                "status": "active",
            }
            wt.write_entry_file(path, meta, "世界正文\n第二行")
            parsed = wt.parse_entry_file(path)
            self.assertEqual(parsed["entry_id"], "e0001")
            self.assertEqual(parsed["title"], "世界观总纲")
            self.assertEqual(parsed["content"], "世界正文\n第二行")
            self.assertEqual(parsed["path"], path)
            self.assertEqual(parsed["sort_prefix"], 10)

    def test_parse_entry_rejects_missing_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.md"
            path.write_text("没有 frontmatter", encoding="utf-8")
            with self.assertRaises(ValueError) as cm:
                wt.parse_entry_file(path)
            self.assertIn("frontmatter", str(cm.exception))

    def test_config_rejects_escaping_layer_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            root.mkdir()
            cfg = wt._default_config_copy()
            cfg["layers"] = [{"dir": "..\\..\\output", "name": "bad", "order_base": 0}]
            wt.save_config(root, cfg)
            with self.assertRaises(ValueError):
                wt.ensure_project(root)

    def test_long_title_filename_is_capped(self):
        name = wt.make_entry_filename(10, "e0001", "很长" * 100)
        self.assertLess(len(name), 140)
        self.assertTrue(name.startswith("010-e0001-"))


class TestStructureOperations(unittest.TestCase):
    def test_add_creates_entry_and_updates_index(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            rc = wt.main(["add", str(root), "--layer", "30-角色层", "--title", "角色：莉娅",
                          "--keys", "莉娅,Lia", "--constant", "true", "--summary", "女主核心设定"])
            self.assertEqual(rc, 0)
            entries = wt.discover_entries(root)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["entry_id"], "e0001")
            self.assertEqual(entries[0]["title"], "角色：莉娅")
            self.assertEqual(entries[0]["keys"], ["莉娅", "Lia"])
            index = (root / "index.md").read_text(encoding="utf-8")
            self.assertIn("e0001", index)
            self.assertIn("角色：莉娅", index)
            self.assertTrue(list((root / "patches").glob("*-add-e0001.json")))

    def test_add_skips_existing_ids_when_config_reset(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "A", "--constant", "true"])
            cfg = wt.load_config(root)
            cfg["next_entry_number"] = 1
            wt.save_config(root, cfg)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "B", "--constant", "true"])
            self.assertEqual([e["entry_id"] for e in wt.active_entries(root)], ["e0001", "e0002"])

    def test_rename_updates_title_and_filename(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "30-角色层", "--title", "角色：莉娅"])
            wt.main(["rename", str(root), "--entry", "e0001", "--title", "角色：莉娅·银钥"])
            entry = wt.find_entry(root, "e0001")
            self.assertEqual(entry["title"], "角色：莉娅·银钥")
            self.assertIn("银钥", entry["path"].name)
            self.assertIn("角色：莉娅·银钥", (root / "index.md").read_text(encoding="utf-8"))

    def test_move_changes_layer_without_changing_entry_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "30-角色层", "--title", "状态栏输出协议"])
            wt.main(["move", str(root), "--entry", "e0001", "--to-layer", "20-驱动层"])
            entry = wt.find_entry(root, "e0001")
            self.assertEqual(entry["entry_id"], "e0001")
            self.assertEqual(entry["layer"], "20-驱动层")
            self.assertIn("20-驱动层", entry["path"].as_posix())

    def test_reorder_changes_sort_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "30-角色层", "--title", "角色：莉娅"])
            wt.main(["reorder", str(root), "--entry", "e0001", "--prefix", "5"])
            entry = wt.find_entry(root, "e0001")
            self.assertEqual(entry["sort_prefix"], 5)
            self.assertTrue(entry["path"].name.startswith("005-e0001-"))

    def test_delete_archives_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "30-角色层", "--title", "角色：莉娅"])
            wt.main(["delete", str(root), "--entry", "e0001"])
            self.assertEqual(wt.discover_entries(root), [])
            archived = list((root / "archive").rglob("*e0001*.md"))
            self.assertEqual(len(archived), 1)
            parsed = wt.parse_entry_file(archived[0])
            self.assertEqual(parsed["status"], "archived")
            index = (root / "index.md").read_text(encoding="utf-8")
            self.assertNotIn("| e0001 |", index)

    def test_archived_entry_cannot_be_deleted_or_moved_again(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "30-角色层", "--title", "角色：莉娅"])
            wt.main(["delete", str(root), "--entry", "e0001"])
            archived = list((root / "archive").rglob("*e0001*.md"))
            self.assertEqual(wt.main(["delete", str(root), "--entry", "e0001"]), 2)
            self.assertEqual(wt.main(["move", str(root), "--entry", "e0001", "--to-layer", "20-驱动层"]), 2)
            self.assertEqual(len(list((root / "archive").rglob("*e0001*.md"))), len(archived))


class TestShowAndSearch(unittest.TestCase):
    def test_show_outputs_full_entry_content(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "10-规则层", "--title", "魔法代价规则",
                     "--keys", "魔法,代价", "--summary", "代价规则", "--content", "完整正文：施法要付出记忆。"])
            out = wt.format_entry(wt.find_entry(root, "e0001"), root)
            self.assertIn("UID", out)
            self.assertIn("entry_id: e0001", out)
            self.assertIn("魔法代价规则", out)
            self.assertIn("完整正文：施法要付出记忆。", out)

    def test_exact_search_returns_full_matching_entry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "10-规则层", "--title", "魔法代价规则",
                     "--keys", "魔法,代价", "--content", "施法要付出记忆。"])
            wt.main(["add", str(root), "--layer", "30-角色层", "--title", "角色：莉娅",
                     "--keys", "莉娅", "--content", "她持有银钥匙。"])
            results = wt.search_entries(wt.active_entries(root), "exact", "银钥匙", 5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][1]["entry_id"], "e0002")
            formatted = wt.format_entry(results[0][1], root, results[0][0])
            self.assertIn("她持有银钥匙。", formatted)

    def test_fuzzy_search_prefers_title_and_keys(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "10-规则层", "--title", "灵能代偿规则",
                     "--keys", "灵能,代偿", "--summary", "魔法反噬与代价", "--content", "代偿不是惩罚。"])
            results = wt.search_entries(wt.active_entries(root), "fuzzy", "魔法反噬", 5)
            self.assertTrue(results)
            self.assertEqual(results[0][1]["entry_id"], "e0001")
            self.assertGreater(results[0][0], 0)


class TestBuildWorldbook(unittest.TestCase):
    def test_build_generates_sequential_uid_and_layer_orders(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            out = project / "output" / "世界书.json"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "30-角色层", "--title", "角色：莉娅",
                     "--keys", "莉娅", "--constant", "true", "--content", "角色正文"])
            wt.main(["add", str(root), "--layer", "10-规则层", "--title", "魔法代价规则",
                     "--keys", "魔法", "--content", "规则正文"])
            rc = wt.main(["build", str(root), "--out", "output/世界书.json"])
            self.assertEqual(rc, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(sorted(data["entries"].keys()), ["0", "1"])
            first = data["entries"]["0"]
            second = data["entries"]["1"]
            self.assertEqual(first["uid"], 0)
            self.assertEqual(first["comment"], "魔法代价规则")
            self.assertEqual(first["order"], 100)
            self.assertEqual(second["uid"], 1)
            self.assertEqual(second["comment"], "角色：莉娅")
            self.assertEqual(second["order"], 300)
            self.assertTrue(first["preventRecursion"])
            self.assertTrue(first["excludeRecursion"])
            self.assertFalse(first["constant"])
            self.assertTrue(second["constant"])
            index = (root / "index.md").read_text(encoding="utf-8")
            self.assertIn("| e0002 | 0 | 100 |", index)
            self.assertIn("| e0001 | 1 | 300 |", index)

    def test_entry_id_not_exported_in_comment_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            out = project / "output" / "out.json"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "世界观总纲", "--constant", "true"])
            wt.main(["build", str(root), "--out", "output/out.json"])
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["entries"]["0"]["comment"], "世界观总纲")

    def test_string_false_constant_exports_false(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            out = project / "output" / "out.json"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "10-规则层", "--title", "魔法", "--keys", "魔法"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta["constant"] = "false"
            wt.write_entry_file(path, meta, content)
            wt.main(["build", str(root), "--out", "output/out.json"])
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(data["entries"]["0"]["constant"])
            self.assertTrue(data["entries"]["0"]["selective"])

    def test_passthrough_st_fields_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            out = project / "output" / "out.json"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "10-规则层", "--title", "纠正", "--keys", "纠正"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta.update({"position": 4, "depth": 0, "role": 1, "sticky": 3, "keysecondary": ["次"]})
            wt.write_entry_file(path, meta, content)
            wt.main(["build", str(root), "--out", "output/out.json"])
            built = json.loads(out.read_text(encoding="utf-8"))["entries"]["0"]
            self.assertEqual(built["position"], 4)
            self.assertEqual(built["depth"], 0)
            self.assertEqual(built["role"], 1)
            self.assertEqual(built["sticky"], 3)
            self.assertEqual(built["keysecondary"], ["次"])

    def test_out_path_must_stay_under_output_for_relative_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "工作" / "世界书"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "世界", "--constant", "true"])
            self.assertEqual(wt.main(["build", str(root), "--out", "output/../工作/世界书/worldbook.config.json"]), 2)


class TestImportWorldbook(unittest.TestCase):
    def test_import_existing_json_creates_source_entries(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "工作" / "世界书"
            src = Path(d) / "old.json"
            src.write_text(json.dumps({"entries": {"0": {"uid": 0, "comment": "旧条目", "content": "旧正文", "constant": True, "key": []}}}, ensure_ascii=False), encoding="utf-8")
            wt.ensure_project(root)
            self.assertEqual(wt.main(["import", str(root), str(src), "--layer", "00-世界设定层"]), 0)
            entry = wt.find_entry(root, "e0001")
            self.assertEqual(entry["title"], "旧条目")
            self.assertEqual(entry["content"], "旧正文")
            self.assertTrue(entry["constant"])


class TestCheckWorldbook(unittest.TestCase):
    def test_check_passes_after_build(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            out = project / "output" / "out.json"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "世界观总纲", "--constant", "true"])
            wt.main(["build", str(root), "--out", "output/out.json"])
            errors, warnings = wt.check_project(root, out)
            self.assertEqual(errors, [])

    def test_check_detects_duplicate_entry_id(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "世界观总纲", "--constant", "true"])
            source = wt.find_entry(root, "e0001")["path"]
            duplicate = source.parent / "020-e0001-重复.md"
            duplicate.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            errors, warnings = wt.check_project(root, None)
            self.assertTrue(any("重复 entry_id" in e for e in errors))

    def test_check_detects_stale_output_json(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            out = project / "output" / "out.json"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "世界观总纲", "--constant", "true"])
            wt.main(["build", str(root), "--out", "output/out.json"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta["title"] = "世界观总纲改名"
            wt.write_entry_file(path, meta, content)
            errors, warnings = wt.check_project(root, out)
            self.assertTrue(any("导出 JSON 已过期" in e for e in errors))

    def test_check_rejects_archived_status_under_entries(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "世界观总纲", "--constant", "true"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta["status"] = "archived"
            wt.write_entry_file(path, meta, content)
            errors, warnings = wt.check_project(root, None)
            self.assertTrue(any("归档条目出现在 entries" in e for e in errors))

    def test_check_rejects_unknown_layer_and_green_without_keys(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "坏条目"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta["layer"] = "30-角色"
            wt.write_entry_file(path, meta, content)
            errors, warnings = wt.check_project(root, None)
            self.assertTrue(any("未知层级" in e for e in errors))
            self.assertTrue(any("keys 为空" in e for e in errors))

    def test_check_detects_over_length_title(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "短标题", "--constant", "true"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta["title"] = TITLE_21
            wt.write_entry_file(path, meta, content)
            errors, warnings = wt.check_project(root, None)
            self.assertTrue(any("超过 MMD 上限" in e for e in errors))

    def test_index_table_escapes_pipes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "A|B", "--constant", "true", "--summary", "x|y"])
            text = (root / "index.md").read_text(encoding="utf-8")
            self.assertIn("A\\|B", text)
            self.assertIn("x\\|y", text)


class TestTitleLengthLimit(unittest.TestCase):
    def test_add_rejects_over_length_title(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            rc = wt.main(["add", str(root), "--layer", "00-世界设定层",
                          "--title", TITLE_21, "--constant", "true"])
            self.assertEqual(rc, 2)
            self.assertEqual(list((root / "entries" / "00-世界设定层").glob("*.md")), [])

    def test_add_does_not_consume_entry_id_when_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层",
                     "--title", TITLE_21, "--constant", "true"])
            wt.main(["add", str(root), "--layer", "00-世界设定层",
                     "--title", "正常标题", "--constant", "true"])
            self.assertEqual(wt.find_entry(root, "e0001")["title"], "正常标题")

    def test_add_accepts_exactly_twenty_chars(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            rc = wt.main(["add", str(root), "--layer", "00-世界设定层",
                          "--title", TITLE_20, "--constant", "true"])
            self.assertEqual(rc, 0)
            self.assertEqual(wt.find_entry(root, "e0001")["title"], TITLE_20)

    def test_rename_rejects_over_length_title(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层",
                     "--title", "原标题", "--constant", "true"])
            rc = wt.main(["rename", str(root), "--entry", "e0001", "--title", TITLE_21])
            self.assertEqual(rc, 2)
            self.assertEqual(wt.find_entry(root, "e0001")["title"], "原标题")

    def test_entry_id_prefix_counts_toward_limit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            cfg = wt.ensure_project(root)
            cfg["export"]["include_entry_id_in_comment"] = True
            wt.save_config(root, cfg)
            self.assertEqual(wt.main(["add", str(root), "--layer", "00-世界设定层",
                                      "--title", TITLE_12, "--constant", "true"]), 0)
            self.assertEqual(wt.main(["add", str(root), "--layer", "00-世界设定层",
                                      "--title", TITLE_13, "--constant", "true"]), 2)

    def test_st_platform_skips_limit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            cfg = wt.ensure_project(root)
            cfg["platform"] = "st"
            wt.save_config(root, cfg)
            rc = wt.main(["add", str(root), "--layer", "00-世界设定层",
                          "--title", TITLE_21, "--constant", "true"])
            self.assertEqual(rc, 0)
            errors, _warnings = wt.check_project(root, None)
            self.assertEqual([e for e in errors if "上限" in e], [])

    def test_import_keeps_long_title_but_check_flags_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            src = Path(d) / "old.json"
            src.write_text(json.dumps({"entries": {"0": {
                "uid": 0, "comment": TITLE_21, "content": "正文",
                "constant": True, "key": []}}}, ensure_ascii=False), encoding="utf-8")
            wt.ensure_project(root)
            self.assertEqual(wt.main(["import", str(root), str(src),
                                      "--layer", "00-世界设定层"]), 0)
            self.assertEqual(wt.find_entry(root, "e0001")["title"], TITLE_21)
            errors, _warnings = wt.check_project(root, None)
            self.assertTrue(any("超过 MMD 上限" in e for e in errors))

    def test_import_warn_reports_length_consistent_with_limit(self):
        """开启 entry_id 前缀时，WARN 报的字数必须是判定所用的（含前缀）长度，不能自相矛盾。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            src = Path(d) / "old.json"
            src.write_text(json.dumps({"entries": {"0": {
                "uid": 0, "comment": TITLE_13, "content": "正文",
                "constant": True, "key": []}}}, ensure_ascii=False), encoding="utf-8")
            cfg = wt.ensure_project(root)
            cfg["export"]["include_entry_id_in_comment"] = True
            wt.save_config(root, cfg)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(wt.main(["import", str(root), str(src),
                                          "--layer", "00-世界设定层"]), 0)
            out = buf.getvalue()
            self.assertIn("[WARN]", out)
            self.assertIn("21 字", out)          # 含前缀后的真实长度
            self.assertNotIn("13 字超过", out)   # 不能报裸标题长度

    def test_check_survives_non_string_title(self):
        """非字符串 title 不应让 check 崩溃（长度判定跳过，交给别处报错）。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wb"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "正常标题", "--constant", "true"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta["title"] = 2026
            wt.write_entry_file(path, meta, content)
            errors, _warnings = wt.check_project(root, None)   # 不抛异常即达标
            self.assertFalse(any("上限" in e for e in errors))

    def test_build_warns_on_hand_edited_over_length_title(self):
        """手改 frontmatter 绕过 add/rename 时，build 仍要吭声（不阻断导出）。"""
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            wt.ensure_project(root)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", "世界观总纲", "--constant", "true"])
            entry = wt.find_entry(root, "e0001")
            meta = dict(entry)
            content = meta.pop("content")
            path = meta.pop("path")
            meta.pop("sort_prefix", None)
            meta["title"] = TITLE_21
            wt.write_entry_file(path, meta, content)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(wt.main(["build", str(root), "--out", "output/wb.json"]), 0)
            out = buf.getvalue()
            self.assertIn("[WARN]", out)
            self.assertIn("超过 MMD 上限", out)

    def test_build_quiet_on_st_platform(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            root = project / "工作" / "世界书"
            cfg = wt.ensure_project(root)
            cfg["platform"] = "st"
            wt.save_config(root, cfg)
            wt.main(["add", str(root), "--layer", "00-世界设定层", "--title", TITLE_21, "--constant", "true"])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(wt.main(["build", str(root), "--out", "output/wb.json"]), 0)
            self.assertNotIn("[WARN]", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
