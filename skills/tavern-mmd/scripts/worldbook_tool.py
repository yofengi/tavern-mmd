#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 世界书源文件工具。

工作层使用稳定 entry_id；导出 JSON 的 uid/order 由 build 生成。
纯 Python 标准库，无第三方依赖。
"""
import argparse
import datetime
import difflib
import json
import re
import sys
from pathlib import Path, PureWindowsPath

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

DEFAULT_CONFIG = {
    "entry_id_prefix": "e",
    "next_entry_number": 1,
    "uid_strategy": "rebuild_sequential",
    "order_strategy": "layer_base_plus_step",
    "order_step": 10,
    # 目标平台，决定是否套用 MMD 平台限额（标题 20 字等）。
    # mmd = 当前MMD（20 字硬拦）/ mmdsandbox = MMD沙盒模式（20 字只告警，见 enforces_comment_limit）
    # / st = 本地酒馆（不查）。默认 mmd 取严。
    "platform": "mmd",
    "export": {"include_entry_id_in_comment": False},
    "layers": [
        {"dir": "00-世界设定层", "name": "世界设定层", "order_base": 0,
         "description": "世界观、时代、地理、总纲"},
        {"dir": "10-规则层", "name": "规则层", "order_base": 100,
         "description": "世界运行规则、禁忌、代价"},
        {"dir": "20-驱动层", "name": "驱动层", "order_base": 200,
         "description": "主线、阶段、状态栏协议"},
        {"dir": "30-角色层", "name": "角色层", "order_base": 300,
         "description": "主角、核心角色、NPC、关系"},
        {"dir": "40-场景物品事件层", "name": "场景物品事件层", "order_base": 400,
         "description": "地点、组织、道具、能力、事件"},
        {"dir": "90-文风约束层", "name": "文风约束层", "order_base": 900,
         "description": "文风指导、禁忌写法、输出协议"},
    ],
}
PASSTHROUGH_FIELDS = {
    "keysecondary", "vectorized", "selective", "selectiveLogic", "addMemo", "disable", "ignoreBudget",
    "excludeRecursion", "preventRecursion", "matchPersonaDescription", "matchCharacterDescription",
    "matchCharacterPersonality", "matchCharacterDepthPrompt", "matchScenario", "matchCreatorNotes",
    "delayUntilRecursion", "probability", "useProbability", "depth", "outletName", "group",
    "groupOverride", "groupWeight", "scanDepth", "caseSensitive", "matchWholeWords", "useGroupScoring",
    "automationId", "role", "sticky", "cooldown", "delay", "triggers", "extensions", "characterFilter",
}


# MMD 条目标题（导出为 JSON comment）硬上限，按字符数计，中文一字算 1。
# 超限部分在平台侧被截断；本地酒馆无此限制。
MAX_COMMENT_LEN = 20


def die(message, code=2):
    print("[ERROR] " + message, file=sys.stderr)
    raise SystemExit(code)


def include_entry_id_in_comment(config):
    return bool(config.get("export", {}).get("include_entry_id_in_comment", False))


def enforces_comment_limit(config):
    """本地酒馆标题无长度限制，只有 MMD 系（mmd / mmdsandbox）需要查。

    黑名单语义：除 `st` 之外一律套用 20 字上限——20 字来源是 MMD 创卡页 UI 对世界书
    条目标题的截断，与 chatVersion（新旧聊天页）无关，沙盒模式同样在册。"""
    return config.get("platform", "mmd") != "st"


def comment_limit_is_hard(config):
    """标题超限是否硬拦（拒绝写入 + 退出码 2）。

    锁定决策 D8：沙盒模式**只告警不拦**。限制仍在（见 enforces_comment_limit），
    但官方 validate-worldbook.mjs 不检查该项，本 skill 不拿一条无官方脚本背书的
    平台侧 UI 限制去阻断交付。当前 MMD 仍硬拦。请勿"顺手修正"成一律硬拦。"""
    return config.get("platform", "mmd") != "mmdsandbox"


def export_comment(title, entry_id, config):
    """条目导出后的实际 comment，含可选 entry_id 前缀。"""
    if include_entry_id_in_comment(config):
        return "[%s] %s" % (entry_id, title)
    return title


def comment_length_problem(title, entry_id, config):
    """标题超限时返回提示文本，未超限返回 None。按导出后的 comment 计长。"""
    if not enforces_comment_limit(config):
        return None
    if not isinstance(title, str):
        return None  # 非字符串标题由别处报错，这里不参与计长（与 validate.py 口径一致）
    comment = export_comment(title, entry_id, config)
    if len(comment) <= MAX_COMMENT_LEN:
        return None
    prefix_note = "（已含 entry_id 前缀）" if include_entry_id_in_comment(config) else ""
    return "标题%s共 %d 字，超过 MMD 上限 %d 字，导入后会被截断: %s" % (
        prefix_note, len(comment), MAX_COMMENT_LEN, comment)


def require_title_length(title, entry_id, config):
    """生成路径上的前置拦截：不写出注定被平台截断的源文件。

    硬拦平台（mmd）抛 ValueError → 退出码 2；软拦平台（mmdsandbox）不抛，
    把提示原文返回给调用方去打 [WARN]，写入照常进行。未超限返回 None。"""
    problem = comment_length_problem(title, entry_id, config)
    if not problem:
        return None
    if comment_limit_is_hard(config):
        raise ValueError(problem)
    return problem


def _default_config_copy():
    return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))


def load_config(root):
    path = Path(root) / "worldbook.config.json"
    if not path.exists():
        return _default_config_copy()
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    merged = _default_config_copy()
    for key, value in cfg.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    if "layers" not in cfg:
        merged["layers"] = DEFAULT_CONFIG["layers"]
    return merged


def save_config(root, config):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "worldbook.config.json").open("w", encoding="utf-8", newline="\n") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")


def safe_relative_dir(value, label):
    text = str(value).replace("\\", "/").strip("/")
    if not text:
        raise ValueError("%s 不能为空" % label)
    if Path(text).is_absolute() or PureWindowsPath(text).is_absolute() or PureWindowsPath(text).drive:
        raise ValueError("%s 必须是相对目录: %s" % (label, value))
    parts = [p for p in text.split("/") if p]
    if any(p in (".", "..") for p in parts):
        raise ValueError("%s 不能包含 . 或 ..: %s" % (label, value))
    bad_chars = set('<>:"|?*')
    if any(any(ch in bad_chars for ch in p) for p in parts):
        raise ValueError("%s 含 Windows 非法文件名字符: %s" % (label, value))
    return "/".join(parts)


def validate_config(config):
    seen = set()
    for layer in config.get("layers", []):
        layer["dir"] = safe_relative_dir(layer["dir"], "层级目录")
        if layer["dir"] in seen:
            raise ValueError("重复层级目录: %s" % layer["dir"])
        seen.add(layer["dir"])


def layer_dirs(config):
    return [layer["dir"] for layer in config.get("layers", [])]


def ensure_project(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cfg = load_config(root)
    validate_config(cfg)
    save_config(root, cfg)
    for name in ("entries", "drafts", "patches", "archive"):
        (root / name).mkdir(exist_ok=True)
    entries_root = root / "entries"
    for layer in cfg.get("layers", []):
        layer_path = entries_root / layer["dir"]
        if not _is_under(layer_path, entries_root):
            raise ValueError("层级目录越界: %s" % layer["dir"])
        layer_path.mkdir(parents=True, exist_ok=True)
    notes = root / "notes.md"
    if not notes.exists():
        notes.write_text(
            "# 世界书设计说明与变更记录\n\n"
            "## 设计约束\n\n"
            "- 在这里记录平台、蓝灯预算、世界观边界和用户确认过的决策。\n\n"
            "## 变更记录\n\n",
            encoding="utf-8",
            newline="\n",
        )
    render_index(root, active_entries(root), cfg, None)
    return cfg


def parse_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "蓝", "蓝灯"):
        return True
    if text in ("0", "false", "no", "n", "绿", "绿灯", ""):
        return False
    raise ValueError("不能解析布尔值: %r" % value)


def parse_keys(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_frontmatter(text, path):
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError("%s 缺少 JSON frontmatter" % path)
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("%s frontmatter 未闭合" % path)
    raw = text[4:end]
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("%s frontmatter 不是合法 JSON: line %d col %d %s" %
                         (path, e.lineno, e.colno, e.msg))
    content = text[end + 5:]
    if content.startswith("\n"):
        content = content[1:]
    if content.endswith("\n"):
        content = content[:-1]
    return meta, content


def filename_sort_prefix(path):
    m = re.match(r"^(\d+)-", Path(path).name)
    return int(m.group(1)) if m else 999999


def parse_entry_file(path):
    path = Path(path)
    meta, content = parse_frontmatter(path.read_text(encoding="utf-8"), path)
    required = ["entry_id", "title", "layer", "constant", "position", "keys", "summary", "status"]
    for key in required:
        if key not in meta:
            raise ValueError("%s frontmatter 缺少字段 %s" % (path, key))
    keys = parse_keys(meta["keys"])
    entry = dict(meta)
    entry["keys"] = keys
    entry["constant"] = parse_bool(entry["constant"])
    entry["position"] = int(entry["position"])
    entry["content"] = content
    entry["path"] = path
    entry["sort_prefix"] = filename_sort_prefix(path)
    return entry


def write_entry_file(path, meta, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_meta = dict(meta)
    clean_meta.pop("path", None)
    clean_meta.pop("content", None)
    clean_meta.pop("sort_prefix", None)
    content = str(content).strip("\n")
    text = "---\n" + json.dumps(clean_meta, ensure_ascii=False, indent=2) + "\n---\n\n" + content + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def discover_entries(root, include_archive=False):
    root = Path(root)
    bases = [root / "entries"]
    if include_archive:
        bases.append(root / "archive")
    entries = []
    for base in bases:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            entries.append(parse_entry_file(path))
    return sort_entries(entries, load_config(root))


def sort_entries(entries, config):
    layer_order = {layer["dir"]: i for i, layer in enumerate(config.get("layers", []))}
    return sorted(entries, key=lambda e: (
        layer_order.get(e.get("layer"), 999),
        e.get("sort_prefix", 999999),
        e.get("entry_id", ""),
    ))


def _relative_to_root(path, root):
    path = Path(path)
    root = Path(root)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def md_cell(value):
    text = str(value).replace("\n", "<br>").replace("|", "\\|")
    return text


def render_index_text(root, entries, config, build_map):
    root = Path(root)
    lines = []
    lines.append("# 世界书索引")
    lines.append("")
    lines.append("> 本文件由 `worldbook_tool.py` 维护。AI 可读取本文件定位条目，但不要手动修改结构字段。")
    lines.append("> 稳定定位使用 `entry_id`；导出 JSON 的 `uid` / `order` 是 build 结果，可重排。")
    lines.append("")
    lines.append("## 层级规划")
    lines.append("")
    lines.append("| 层级目录 | 层级名 | order 起点 | 说明 |")
    lines.append("|---|---|---:|---|")
    for layer in config.get("layers", []):
        lines.append("| %s | %s | %s | %s |" % (
            md_cell(layer["dir"]), md_cell(layer.get("name", layer["dir"])),
            md_cell(layer.get("order_base", "")), md_cell(layer.get("description", ""))))
    lines.append("")
    lines.append("## 条目索引")
    lines.append("")
    lines.append("| entry_id | 当前uid | 当前order | 层级 | 文件 | 标题 | 灯色 | keys | 摘要 | 状态 |")
    lines.append("|---|---:|---:|---|---|---|---|---|---|---|")
    build_map = build_map or {}
    for entry in entries:
        mapped = build_map.get(entry["entry_id"], {})
        uid = mapped.get("uid", "")
        order = mapped.get("order", "")
        rel = _relative_to_root(entry["path"], root)
        light = "蓝" if entry.get("constant") else "绿"
        keys = ",".join(entry.get("keys", [])) or "-"
        cells = [entry.get("entry_id", ""), uid, order, entry.get("layer", ""), rel,
                 entry.get("title", ""), light, keys, entry.get("summary", ""), entry.get("status", "")]
        lines.append("| " + " | ".join(md_cell(c) for c in cells) + " |")
    return "\n".join(lines) + "\n"


def render_index(root, entries, config, build_map):
    (Path(root) / "index.md").write_text(render_index_text(root, entries, config, build_map), encoding="utf-8", newline="\n")


def allocate_entry_id(config, existing_ids=None):
    existing_ids = set(existing_ids or [])
    number = int(config.get("next_entry_number", 1))
    prefix = config.get("entry_id_prefix", "e")
    while True:
        entry_id = "%s%04d" % (prefix, number)
        number += 1
        if entry_id not in existing_ids:
            config["next_entry_number"] = number
            return entry_id


def slugify_title(title):
    s = re.sub(r"[\\/:*?\"<>|\s]+", "-", title.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    s = s[:80].rstrip("-")
    return s or "entry"


def next_sort_prefix(layer_dir):
    layer_dir = Path(layer_dir)
    used = [filename_sort_prefix(p) for p in layer_dir.glob("*.md")]
    if not used:
        return 10
    return max(used) + 10


def make_entry_filename(prefix, entry_id, title):
    return "%03d-%s-%s.md" % (prefix, entry_id, slugify_title(title))


def _is_under(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def find_entry(root, entry_id, include_archive=False):
    root = Path(root)
    entries = discover_entries(root, include_archive=include_archive)
    matches = [e for e in entries if e.get("entry_id") == entry_id]
    if not matches:
        raise ValueError("未找到 entry_id %s" % entry_id)
    active = [e for e in matches if not _is_under(e["path"], root / "archive")]
    if active:
        return active[0]
    raise ValueError("entry_id %s 已归档；如需查看，请直接读取 archive/ 中的源文件" % entry_id)


def active_entries(root):
    return [e for e in discover_entries(root) if e.get("status") != "archived"]


def existing_entry_ids(root):
    try:
        return [e.get("entry_id") for e in discover_entries(root, include_archive=True)]
    except Exception:
        return []


def log_patch(root, operation, payload):
    root = Path(root)
    patch_dir = root / "patches"
    patch_dir.mkdir(exist_ok=True)
    entry = payload.get("entry_id") or payload.get("entry") or "project"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    path = patch_dir / ("%s-%s-%s.json" % (stamp, operation, entry))
    data = {"operation": operation, "timestamp": stamp}
    data.update(payload)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def refresh_index(root, build_map=None):
    cfg = load_config(root)
    render_index(root, active_entries(root), cfg, build_map)


def require_layer(config, layer):
    if layer not in layer_dirs(config):
        raise ValueError("未知层级 %s，可用层级: %s" % (layer, ", ".join(layer_dirs(config))))


def format_entry(entry, root, score=None):
    rel = _relative_to_root(entry["path"], root)
    lines = []
    lines.append("## Entry %s" % entry["entry_id"])
    if score is not None:
        lines.append("score: %.3f" % score)
    lines.append("entry_id: %s" % entry["entry_id"])
    lines.append("UID: build-time export uid; run `build` to refresh current uid in index.md")
    lines.append("file: %s" % rel)
    lines.append("title: %s" % entry.get("title", ""))
    lines.append("layer: %s" % entry.get("layer", ""))
    lines.append("constant: %s" % entry.get("constant"))
    lines.append("position: %s" % entry.get("position"))
    lines.append("keys: %s" % (", ".join(entry.get("keys", [])) or "-"))
    lines.append("summary: %s" % entry.get("summary", ""))
    lines.append("status: %s" % entry.get("status", ""))
    lines.append("")
    lines.append("完整正文：")
    lines.append(entry.get("content", ""))
    return "\n".join(lines)


def entry_search_text(entry):
    return "\n".join([
        entry.get("entry_id", ""),
        entry.get("title", ""),
        ",".join(entry.get("keys", [])),
        entry.get("summary", ""),
        entry.get("content", ""),
    ])


def fuzzy_score(entry, query):
    q = query.strip().lower()
    title = entry.get("title", "").lower()
    keys = ",".join(entry.get("keys", [])).lower()
    summary = entry.get("summary", "").lower()
    content = entry.get("content", "").lower()
    scores = [
        1.0 if q and q in title else difflib.SequenceMatcher(None, q, title).ratio() * 0.95,
        0.9 if q and q in keys else difflib.SequenceMatcher(None, q, keys).ratio() * 0.85,
        0.75 if q and q in summary else difflib.SequenceMatcher(None, q, summary).ratio() * 0.65,
        0.55 if q and q in content else difflib.SequenceMatcher(None, q, content[:500]).ratio() * 0.35,
    ]
    return max(scores)


def search_entries(entries, mode, query, limit):
    mode = mode.lower()
    query_l = query.lower()
    results = []
    for entry in entries:
        if mode == "exact":
            if query_l in entry_search_text(entry).lower():
                results.append((1.0, entry))
        elif mode == "title":
            if query_l in entry.get("title", "").lower():
                results.append((1.0, entry))
        elif mode == "key":
            if any(query_l in k.lower() for k in entry.get("keys", [])):
                results.append((1.0, entry))
        elif mode == "fuzzy":
            score = fuzzy_score(entry, query)
            if score > 0.15:
                results.append((score, entry))
        else:
            raise ValueError("未知搜索模式 %s" % mode)
    results.sort(key=lambda item: (-item[0], item[1].get("entry_id", "")))
    return results[:int(limit)]


def layer_base_map(config):
    return {layer["dir"]: int(layer.get("order_base", 0)) for layer in config.get("layers", [])}


def default_worldbook_entry(entry, uid, order, config):
    comment = export_comment(entry["title"], entry["entry_id"], config)
    constant = parse_bool(entry.get("constant"))
    return {
        "uid": uid,
        "key": entry.get("keys", []),
        "keysecondary": [],
        "comment": comment,
        "content": entry.get("content", ""),
        "constant": constant,
        "vectorized": False,
        "selective": not constant,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": order,
        "position": int(entry.get("position", 1)),
        "disable": False,
        "ignoreBudget": False,
        "excludeRecursion": True,
        "preventRecursion": True,
        "matchPersonaDescription": False,
        "matchCharacterDescription": False,
        "matchCharacterPersonality": False,
        "matchCharacterDepthPrompt": False,
        "matchScenario": False,
        "matchCreatorNotes": False,
        "delayUntilRecursion": False,
        "probability": 100,
        "useProbability": True,
        "depth": 1,
        "outletName": "",
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": False,
        "automationId": "",
        "role": 0,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "triggers": [],
        "displayIndex": uid,
        "extensions": {},
        "characterFilter": {"isExclude": False, "names": [], "tags": []},
    }


def entry_to_worldbook_entry(entry, uid, order, config):
    out = default_worldbook_entry(entry, uid, order, config)
    for field in PASSTHROUGH_FIELDS:
        if field in entry:
            out[field] = entry[field]
    out["uid"] = uid
    out["order"] = order
    out["displayIndex"] = uid
    out["comment"] = export_comment(entry["title"], entry["entry_id"], config)
    out["content"] = entry.get("content", "")
    out["key"] = entry.get("keys", [])
    out["constant"] = parse_bool(out.get("constant"))
    if "selective" not in entry:
        out["selective"] = not out["constant"]
    return out


def build_worldbook(root):
    root = Path(root)
    cfg = load_config(root)
    entries = active_entries(root)
    bases = layer_base_map(cfg)
    per_layer_count = {}
    out_entries = {}
    build_map = {}
    for uid, entry in enumerate(entries):
        layer = entry.get("layer")
        if layer not in bases:
            raise ValueError("%s 使用未知层级 %s" % (entry.get("entry_id"), layer))
        idx = per_layer_count.get(layer, 0)
        per_layer_count[layer] = idx + 1
        order = bases[layer] + idx * int(cfg.get("order_step", 10))
        out_entries[str(uid)] = entry_to_worldbook_entry(entry, uid, order, cfg)
        build_map[entry["entry_id"]] = {"uid": uid, "order": order}
    return {"entries": out_entries}, build_map


def load_export_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_out_path(root, out_path):
    out_text = str(out_path)
    out = Path(out_text)
    if out.is_absolute():
        return out
    safe = safe_relative_dir(out_text, "输出路径")
    root = Path(root).resolve()
    if root.name == "世界书":
        project = root.parent.parent
    else:
        project = root.parent
    resolved = (project / safe).resolve()
    output_root = (project / "output").resolve()
    if not _is_under(resolved, output_root):
        raise ValueError("输出路径必须位于项目 output/ 下: %s" % out_path)
    return resolved


def read_index_text(root):
    path = Path(root) / "index.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def check_project(root, out_path=None):
    root = Path(root)
    errors = []
    warnings = []
    cfg = load_config(root)
    try:
        all_entries = discover_entries(root)
    except Exception as e:
        return ["读取源条目失败: %s" % e], warnings
    entries = [e for e in all_entries if e.get("status") != "archived"]
    seen = {}
    valid_layers = set(layer_dirs(cfg))
    for entry in all_entries:
        eid = entry.get("entry_id")
        if eid in seen:
            errors.append("重复 entry_id %s: %s 和 %s" % (eid, seen[eid], entry["path"]))
        seen[eid] = entry["path"]
        if not entry.get("title"):
            errors.append("%s 标题为空" % eid)
        else:
            problem = comment_length_problem(entry["title"], eid, cfg)
            if problem:
                # 沙盒模式降级为 warning（D8），当前 MMD 仍算 error
                bucket = errors if comment_limit_is_hard(cfg) else warnings
                bucket.append("%s %s" % (eid, problem))
        if entry.get("status") == "archived" and _is_under(entry["path"], root / "entries"):
            errors.append("归档条目出现在 entries 中: %s" % eid)
        if entry.get("layer") not in valid_layers:
            errors.append("%s 使用未知层级: %s" % (eid, entry.get("layer")))
        expected_name_part = "-%s-" % eid
        if expected_name_part not in entry["path"].name:
            warnings.append("%s 文件名未包含 entry_id: %s" % (eid, entry["path"]))
        if not entry.get("constant") and not entry.get("keys"):
            errors.append("%s 是绿灯条目但 keys 为空" % eid)
    expected_indexes = {render_index_text(root, entries, cfg, None)}
    try:
        _expected_for_index, build_map_for_index = build_worldbook(root)
        expected_indexes.add(render_index_text(root, entries, cfg, build_map_for_index))
    except ValueError:
        pass
    actual_index = read_index_text(root)
    if actual_index and actual_index not in expected_indexes:
        warnings.append("index.md 与当前源文件不同步；运行 init/add/move/rename/build 会重写索引")
    if out_path:
        out_path = resolve_out_path(root, out_path)
        if not out_path.exists():
            errors.append("导出 JSON 不存在: %s" % out_path)
        else:
            try:
                expected, _build_map = build_worldbook(root)
                actual = load_export_json(out_path)
            except (OSError, json.JSONDecodeError, ValueError) as e:
                errors.append("导出 JSON 读取/构建失败: %s" % e)
                actual = None
                expected = None
            if actual is not None:
                if actual != expected:
                    errors.append("导出 JSON 已过期或被手动修改，请重新运行 build: %s" % out_path)
                entries_obj = actual.get("entries") if isinstance(actual, dict) else None
                if not isinstance(entries_obj, dict):
                    errors.append("导出 JSON entries 不是对象")
                else:
                    for key, value in entries_obj.items():
                        try:
                            uid_key = int(key)
                        except ValueError:
                            errors.append("导出 JSON entries key 不是数字: %s" % key)
                            continue
                        if not isinstance(value, dict) or value.get("uid") != uid_key:
                            errors.append("导出 JSON entries[%s].uid 与 key 不一致" % key)
    return errors, warnings


def entry_meta_from_json(entry, entry_id, layer, title=None):
    title = title or entry.get("comment") or entry_id
    return {
        "entry_id": entry_id,
        "title": title,
        "layer": layer,
        "constant": bool(entry.get("constant", False)),
        "position": int(entry.get("position", 1)),
        "keys": entry.get("key", []),
        "summary": "",
        "status": "active",
        **{field: entry[field] for field in PASSTHROUGH_FIELDS if field in entry},
    }


def cmd_init(args):
    ensure_project(Path(args.root))
    print("[OK] initialized %s" % args.root)
    return 0


def cmd_add(args):
    root = Path(args.root)
    cfg = ensure_project(root)
    require_layer(cfg, args.layer)
    entry_id = allocate_entry_id(cfg, existing_entry_ids(root))
    title_warning = require_title_length(args.title, entry_id, cfg)
    save_config(root, cfg)
    layer_dir = root / "entries" / args.layer
    prefix = next_sort_prefix(layer_dir)
    meta = {
        "entry_id": entry_id,
        "title": args.title,
        "layer": args.layer,
        "constant": parse_bool(args.constant),
        "position": int(args.position),
        "keys": parse_keys(args.keys),
        "summary": args.summary or "",
        "status": "active",
    }
    path = layer_dir / make_entry_filename(prefix, entry_id, args.title)
    write_entry_file(path, meta, args.content or "")
    refresh_index(root)
    log_patch(root, "add", {"entry_id": entry_id, "path": path.relative_to(root).as_posix(), "title": args.title})
    print("[OK] added %s %s" % (entry_id, path.relative_to(root).as_posix()))
    if title_warning:
        print("[WARN] %s %s" % (entry_id, title_warning))
    return 0


def cmd_import(args):
    root = Path(args.root)
    cfg = ensure_project(root)
    require_layer(cfg, args.layer)
    data = load_export_json(args.json_file)
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        raise ValueError("导入文件不是独立世界书 JSON：缺少 entries 对象")
    long_titles = []
    for key in sorted(entries, key=lambda k: int(k) if str(k).isdigit() else 999999):
        entry = entries[key]
        if not isinstance(entry, dict):
            continue
        entry_id = allocate_entry_id(cfg, existing_entry_ids(root))
        save_config(root, cfg)
        title = entry.get("comment") or "条目%s" % key
        layer_dir = root / "entries" / args.layer
        prefix = next_sort_prefix(layer_dir)
        path = layer_dir / make_entry_filename(prefix, entry_id, title)
        meta = entry_meta_from_json(entry, entry_id, args.layer, title)
        write_entry_file(path, meta, entry.get("content", ""))
        log_patch(root, "import", {"entry_id": entry_id, "source_uid": key, "path": path.relative_to(root).as_posix()})
        # 导入的标题不是本工具写的，超限也照样落地，交给 check/rename 收拾，不阻断导入
        problem = comment_length_problem(title, entry_id, cfg)
        if problem:
            long_titles.append((entry_id, problem))
    refresh_index(root)
    print("[OK] imported %d entries" % len(entries))
    for entry_id, problem in long_titles:
        print("[WARN] %s %s（需 rename 缩短）" % (entry_id, problem))
    return 0


def cmd_rename(args):
    root = Path(args.root)
    entry = find_entry(root, args.entry)
    title_warning = require_title_length(args.title, entry["entry_id"], load_config(root))
    old_path = entry["path"]
    meta = dict(entry)
    content = meta.pop("content")
    meta.pop("path", None)
    meta.pop("sort_prefix", None)
    old_title = meta["title"]
    meta["title"] = args.title
    new_path = old_path.with_name(make_entry_filename(entry["sort_prefix"], entry["entry_id"], args.title))
    write_entry_file(new_path, meta, content)
    if new_path != old_path:
        old_path.unlink()
    refresh_index(root)
    log_patch(root, "rename", {"entry_id": args.entry, "old_title": old_title, "new_title": args.title})
    print("[OK] renamed %s" % args.entry)
    if title_warning:
        print("[WARN] %s %s" % (args.entry, title_warning))
    return 0


def cmd_move(args):
    root = Path(args.root)
    cfg = ensure_project(root)
    require_layer(cfg, args.to_layer)
    entry = find_entry(root, args.entry)
    old_path = entry["path"]
    meta = dict(entry)
    content = meta.pop("content")
    meta.pop("path", None)
    meta.pop("sort_prefix", None)
    old_layer = meta["layer"]
    meta["layer"] = args.to_layer
    target_dir = root / "entries" / args.to_layer
    prefix = next_sort_prefix(target_dir)
    new_path = target_dir / make_entry_filename(prefix, entry["entry_id"], meta["title"])
    write_entry_file(new_path, meta, content)
    old_path.unlink()
    refresh_index(root)
    log_patch(root, "move", {"entry_id": args.entry, "from_layer": old_layer, "to_layer": args.to_layer,
                              "from": old_path.relative_to(root).as_posix(), "to": new_path.relative_to(root).as_posix()})
    print("[OK] moved %s" % args.entry)
    return 0


def cmd_reorder(args):
    root = Path(args.root)
    entry = find_entry(root, args.entry)
    old_path = entry["path"]
    meta = dict(entry)
    content = meta.pop("content")
    meta.pop("path", None)
    meta.pop("sort_prefix", None)
    new_prefix = int(args.prefix)
    new_path = old_path.with_name(make_entry_filename(new_prefix, entry["entry_id"], meta["title"]))
    write_entry_file(new_path, meta, content)
    if new_path != old_path:
        old_path.unlink()
    refresh_index(root)
    log_patch(root, "reorder", {"entry_id": args.entry, "old_prefix": entry["sort_prefix"], "new_prefix": new_prefix})
    print("[OK] reordered %s" % args.entry)
    return 0


def cmd_delete(args):
    root = Path(args.root)
    entry = find_entry(root, args.entry)
    if args.hard:
        entry["path"].unlink()
        action = "hard-delete"
    else:
        meta = dict(entry)
        content = meta.pop("content")
        old_path = meta.pop("path")
        meta.pop("sort_prefix", None)
        meta["status"] = "archived"
        safe_layer = safe_relative_dir(entry["layer"], "归档层级")
        archive_dir = root / "archive" / safe_layer
        if not _is_under(archive_dir, root / "archive"):
            raise ValueError("归档目录越界: %s" % entry["layer"])
        archive_dir.mkdir(parents=True, exist_ok=True)
        new_path = archive_dir / old_path.name
        if new_path.exists():
            new_path = archive_dir / (datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + "-" + old_path.name)
        write_entry_file(new_path, meta, content)
        old_path.unlink()
        action = "archive"
    refresh_index(root)
    log_patch(root, "delete", {"entry_id": args.entry, "mode": action})
    print("[OK] deleted %s (%s)" % (args.entry, action))
    return 0


def cmd_show(args):
    root = Path(args.root)
    entry = find_entry(root, args.entry)
    print(format_entry(entry, root))
    return 0


def cmd_search(args):
    root = Path(args.root)
    results = search_entries(active_entries(root), args.mode, args.query, int(args.limit))
    if not results:
        print("[WARN] no matches")
        return 1
    for score, entry in results:
        print(format_entry(entry, root, score))
        print("\n---\n")
    return 0


def cmd_build(args):
    root = Path(args.root)
    data, build_map = build_worldbook(root)
    out = resolve_out_path(root, args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    cfg = load_config(root)
    render_index(root, active_entries(root), cfg, build_map)
    log_patch(root, "build", {"entry": "project", "out": str(out), "entries": len(data["entries"])})
    print("[OK] built %s (%d entries)" % (out, len(data["entries"])))
    # mmd 下 add/rename 已在入口拦超限标题（沙盒只告警不拦），这里兜手改 frontmatter
    # 与沙盒放行的情况：一律不阻断导出，但必须吭声
    if enforces_comment_limit(cfg):
        for entry in data["entries"].values():
            comment = entry.get("comment", "")
            if isinstance(comment, str) and len(comment) > MAX_COMMENT_LEN:
                print("[WARN] 导出标题 %d 字超过 MMD 上限 %d 字，导入后会被截断: %s"
                      % (len(comment), MAX_COMMENT_LEN, comment))
    return 0


def cmd_check(args):
    errors, warnings = check_project(Path(args.root), Path(args.out) if args.out else None)
    for msg in errors:
        print("[ERROR] " + msg)
    for msg in warnings:
        print("[WARN] " + msg)
    if errors:
        return 1
    print("[OK] worldbook source check passed")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="tavern-mmd 世界书源文件工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="初始化 工作/世界书 源目录")
    sp.add_argument("root")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("add", help="新增正式条目源文件")
    sp.add_argument("root")
    sp.add_argument("--layer", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--keys", default="")
    sp.add_argument("--constant", default="false")
    sp.add_argument("--position", default="1")
    sp.add_argument("--summary", default="")
    sp.add_argument("--content", default="")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("import", help="把既有独立世界书 JSON 导入源文件目录")
    sp.add_argument("root")
    sp.add_argument("json_file")
    sp.add_argument("--layer", default="40-场景物品事件层")
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("rename", help="修改条目标题并同步文件名")
    sp.add_argument("root")
    sp.add_argument("--entry", required=True)
    sp.add_argument("--title", required=True)
    sp.set_defaults(func=cmd_rename)

    sp = sub.add_parser("move", help="移动条目到另一层级")
    sp.add_argument("root")
    sp.add_argument("--entry", required=True)
    sp.add_argument("--to-layer", required=True)
    sp.set_defaults(func=cmd_move)

    sp = sub.add_parser("reorder", help="调整条目在层内的文件排序前缀")
    sp.add_argument("root")
    sp.add_argument("--entry", required=True)
    sp.add_argument("--prefix", required=True)
    sp.set_defaults(func=cmd_reorder)

    sp = sub.add_parser("delete", help="归档或硬删除条目")
    sp.add_argument("root")
    sp.add_argument("--entry", required=True)
    sp.add_argument("--hard", action="store_true")
    sp.set_defaults(func=cmd_delete)

    sp = sub.add_parser("show", help="按 entry_id 输出完整条目")
    sp.add_argument("root")
    sp.add_argument("--entry", required=True)
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("search", help="搜索并输出完整条目")
    sp.add_argument("root")
    sp.add_argument("mode", choices=["exact", "fuzzy", "title", "key"])
    sp.add_argument("query")
    sp.add_argument("--limit", default="5")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("build", help="从源文件生成独立世界书 JSON")
    sp.add_argument("root")
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("check", help="检查源文件、索引和导出 JSON 是否一致")
    sp.add_argument("root")
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_check)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print("[ERROR] %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
