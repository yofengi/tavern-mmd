#!/usr/bin/env python3
"""Build the current-MMD zmr theme runtime import package."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, NamedTuple, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "mmd-theme-runtime.mmd.json"
OWNER = "tavern-mmd/zmr"
VERSION = "2.0.0"
MAX_FIND_REGEX = 1000
MAX_REPLACE_STRING = 20000
PROJECT_REPLACE_LIMIT = 17999


class Module(NamedTuple):
    marker: str
    script_name: str
    source_path: Path
    asset_id: str
    kind: str


MODULES: Tuple[Module, ...] = (
    Module(
        "<zmr-cleanup-v2>",
        "[ZMR 1/5] 清污 factory",
        BASE_DIR.parent / "mmd_cleanup_core.js",
        "zmr-cleanup-factory",
        "script",
    ),
    Module(
        "<zmr-quote-v2>",
        "[ZMR 2/5] 引号插件 factory",
        BASE_DIR / "quote-plugin.js",
        "zmr-quote-plugin-factory",
        "script",
    ),
    Module(
        "<zmr-theme-v2>",
        "[ZMR 3/5] 公共主题 CSS",
        BASE_DIR / "theme.css",
        "zmr-theme-style",
        "style",
    ),
    Module(
        "<zmr-ui-v2>",
        "[ZMR 4/5] 设置 UI factory",
        BASE_DIR / "settings-ui.js",
        "zmr-settings-ui-factory",
        "script",
    ),
    Module(
        "<zmr-runtime-v2>",
        "[ZMR 5/5] 三态运行时 bootstrap",
        BASE_DIR / "runtime.js",
        "zmr-theme-runtime",
        "script",
    ),
)


def read_source(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"源码带 UTF-8 BOM: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"源码不是合法 UTF-8: {path}: {error}") from error
    return text.replace("\r\n", "\n").replace("\r", "\n")


def compact_lines(source: str, path: Path, kind: str) -> str:
    if kind == "script" and "//" in source:
        raise ValueError(f"JS 源码含 //，逐行拼接可能改变语义: {path}")
    lines = [line.strip() for line in source.split("\n") if line.strip()]
    if not lines:
        raise ValueError(f"源码为空: {path}")
    if kind == "script":
        for number, line in enumerate(lines, start=1):
            if re.search(r"\b(?:return|throw|break|continue|yield|await)\s*$", line):
                raise ValueError(f"JS 第 {number} 个非空行可能依赖 ASI: {path}")
    compacted = " ".join(lines)
    if "\n" in compacted or "\r" in compacted:
        raise ValueError(f"逐行拼接后仍含换行: {path}")
    return compacted


def wrap_asset(module: Module, payload: str) -> str:
    metadata = (
        f"data-zmr-owned='asset' data-zmr-owner='{OWNER}' "
        f"data-zmr-version='{VERSION}' data-zmr-id='{module.asset_id}'"
    )
    if module.kind == "script":
        return f"<script {metadata}>{payload}</script>"
    if module.kind == "style":
        return f"<style id='{module.asset_id}' {metadata}>{payload}</style>"
    raise ValueError(f"未知模块类型: {module.kind}")


def marker_regex(marker: str) -> str:
    if not re.fullmatch(r"<[a-z0-9-]+>", marker):
        raise ValueError(f"触发标记含未支持字符: {marker}")
    return f"/{marker}/"


def build_object() -> Dict[str, object]:
    scripts: List[Dict[str, object]] = []
    for module in MODULES:
        source = read_source(module.source_path)
        payload = compact_lines(source, module.source_path, module.kind)
        scripts.append(
            {
                "id": -1,
                "scriptName": module.script_name,
                "findRegex": marker_regex(module.marker),
                "replaceString": wrap_asset(module, payload),
            }
        )
    return {
        "pageDepth": 2,
        "statusbar": "".join(module.marker for module in MODULES),
        "beginning": "",
        "regex_scripts": scripts,
    }


def serialize(obj: Mapping[str, object]) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def parse_hex_color(value: str) -> Tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"不是六位十六进制颜色: {value}")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def relative_luminance(color: str) -> float:
    channels = []
    for channel in parse_hex_color(color):
        normalized = channel / 255.0
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else math.pow((normalized + 0.055) / 1.055, 2.4)
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: str, second: str) -> float:
    high, low = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def extract_theme_tokens(css_source: str) -> Dict[str, Dict[str, str]]:
    themes: Dict[str, Dict[str, str]] = {}
    pattern = re.compile(r'html\[data-zmr-mode="(day|night)"\]\s*\{([^}]+)\}', re.S)
    for match in pattern.finditer(css_source):
        values = {
            name: value.strip()
            for name, value in re.findall(r"(--zmr-[a-z0-9-]+)\s*:\s*([^;]+);", match.group(2))
        }
        themes[match.group(1)] = values
    return themes


def check_contrast(css_source: str, errors: List[str]) -> None:
    themes = extract_theme_tokens(css_source)
    required = {
        "--zmr-page-bg",
        "--zmr-surface",
        "--zmr-text",
        "--zmr-accent",
        "--zmr-accent-contrast",
        "--zmr-focus",
        "--zmr-user-bubble",
        "--zmr-user-text",
        "--zmr-reading-text",
        "--zmr-reading-accent",
    }
    for mode in ("day", "night"):
        values = themes.get(mode)
        if values is None:
            errors.append(f"theme.css 缺少 {mode} token 块")
            continue
        missing = sorted(required.difference(values))
        if missing:
            errors.append(f"{mode} 缺少 token: {', '.join(missing)}")
            continue
        text_pairs = (
            ("正文/页面", values["--zmr-text"], values["--zmr-page-bg"]),
            ("正文/表面", values["--zmr-text"], values["--zmr-surface"]),
            ("阅读正文/AI气泡", values["--zmr-reading-text"], values["--zmr-surface"]),
            ("高亮/AI气泡", values["--zmr-reading-accent"], values["--zmr-surface"]),
            ("强调按钮", values["--zmr-accent-contrast"], values["--zmr-accent"]),
            ("用户气泡", values["--zmr-user-text"], values["--zmr-user-bubble"]),
        )
        for label, foreground, background in text_pairs:
            ratio = contrast_ratio(foreground, background)
            if ratio < 4.5:
                errors.append(f"{mode} {label} 对比度 {ratio:.2f}:1 < 4.5:1")
        for background_name in ("--zmr-page-bg", "--zmr-surface"):
            ratio = contrast_ratio(values["--zmr-focus"], values[background_name])
            if ratio < 3.0:
                errors.append(f"{mode} 焦点/{background_name} 对比度 {ratio:.2f}:1 < 3:1")


def slash_delimited(find_regex: object) -> bool:
    if not isinstance(find_regex, str) or not find_regex.startswith("/"):
        return False
    end = find_regex.rfind("/")
    return end > 0 and re.fullmatch(r"[dgimsuvy]*", find_regex[end + 1 :]) is not None


def check_css_scope(css_source: str, errors: List[str]) -> None:
    custom_properties = set(re.findall(r"(?<![A-Za-z0-9_-])(--[A-Za-z0-9_-]+)\s*:", css_source))
    invalid_properties = sorted(name for name in custom_properties if not name.startswith("--zmr-"))
    if invalid_properties:
        errors.append(f"theme.css 含非 --zmr-* 变量: {', '.join(invalid_properties)}")
    forbidden = (
        (r"\.content\.right\s+\*", ".content.right *"),
        (r"(?<![A-Za-z0-9_-])\.title(?![A-Za-z0-9_-])", ".title"),
        (r"(?<![A-Za-z0-9_-])\.item(?![A-Za-z0-9_-])", ".item"),
        (r"(?<![A-Za-z0-9_-])\.card(?![A-Za-z0-9_-])", ".card"),
    )
    for pattern, label in forbidden:
        if re.search(pattern, css_source):
            errors.append(f"theme.css 含禁止的宽泛选择器 {label}")
    platform_markers = (
        ".chat-body",
        ".content.left",
        ".content.right",
        ".topTabbar",
        ".chat-bottom",
        ".u-popup__content",
        ".model-setting-scope",
        ".role-setting",
        ".prologue-scope",
    )
    for selector in re.findall(r"(?:^|\})([^@{}]+)\{", css_source, re.S):
        normalized = " ".join(selector.split())
        if any(marker in normalized for marker in platform_markers):
            if "[data-zmr-mode=" not in normalized:
                errors.append(f"平台选择器未受 day/night 作用域约束: {normalized[:160]}")


def check_source_contracts(errors: List[str]) -> None:
    cleanup = read_source(BASE_DIR.parent / "mmd_cleanup_core.js")
    quote = read_source(BASE_DIR / "quote-plugin.js")
    ui = read_source(BASE_DIR / "settings-ui.js")
    runtime = read_source(BASE_DIR / "runtime.js")
    css = read_source(BASE_DIR / "theme.css")
    scripts = cleanup + "\n" + quote + "\n" + ui + "\n" + runtime

    for api_name in ("start", "stop", "setCleaning", "register", "unregister", "flush", "restore", "destroy"):
        if re.search(rf"\b{api_name}\s*:\s*{api_name}\b", cleanup) is None:
            errors.append(f"清污 factory 缺少 API: {api_name}")
    if cleanup.count("new global.MutationObserver(") != 1:
        errors.append("清污 factory 必须恰有一个 MutationObserver")
    if "pendingRecords" not in cleanup or "record.addedNodes" not in cleanup or "attributeTargets" not in cleanup:
        errors.append("清污 factory 缺少 MutationRecord 增量路径")
    if "var deltas = new Map();" not in cleanup or "pruneDisconnected" not in cleanup:
        errors.append("清污 factory 缺少可迭代 delta/prune 容器")
    if "delta.styles.set(property" not in cleanup or "delta.color = { value: colorValue };" not in cleanup:
        errors.append("清污 delta 必须更新为每次实际删除的最新值")
    if "observer.takeRecords();" not in cleanup or "observer.disconnect();" not in cleanup or "observeCurrentRoot();" not in cleanup:
        errors.append("清污 cycle/restore 必须隔离 observer 自身写入")
    if "teardownPlugin(previous, key);" not in cleanup or "teardownPlugin(plugin, key);" not in cleanup:
        errors.append("清污插件替换与显式注销必须 teardown 旧实例")
    if cleanup.find('typeof plugin.stop === "function"') > cleanup.find('typeof plugin.destroy === "function"'):
        errors.append("插件 teardown 必须优先 stop 后 destroy")
    if '"[style]"' in cleanup or '"[color]"' in cleanup or "candidateSelector" in cleanup or "scopeSelector" in cleanup:
        errors.append("清污 selector pack 禁止作用域后代任意 [style]/[color] 广扫")
    if "targets: Object.freeze" not in cleanup or "isAllowedMessageElement" not in cleanup:
        errors.append("清污必须使用明确 platform target 与消息正文边界")
    if 'element.parentElement === content && element.matches(messageWrapperSelector)' not in cleanup:
        errors.append("清污不得进入 .content.left/.right 正文子树")
    if cleanup.find("invokePlugins(context);") > cleanup.find("candidates.forEach(cleanElement);"):
        errors.append("插件必须先于清污运行，以保留确认过的语义元素")
    if "cleanup.setCleaning(false);" not in runtime or "cleanup.stop();" not in runtime:
        errors.append("runtime 缺少 native restore/route stop 契约")
    for method in ("day", "night", "native", "destroy", "enter", "leave", "reenter", "refreshAssets", "setNormalizeQuotes"):
        if re.search(rf"\b{method}\s*:", runtime) is None:
            errors.append(f"runtime 缺少生命周期 API: {method}")
    for event_name in ("hashchange", "pageshow", "pagehide", "visibilitychange"):
        if f'"{event_name}"' not in runtime:
            errors.append(f"runtime 缺少路由监督事件: {event_name}")
    if "namespace.settingsUiFactory" not in runtime or "documentRef.createElement" in runtime:
        errors.append("runtime 必须复用独立 settings UI factory")
    if 'opacityOutput.setAttribute("for", opacity.id);' not in ui:
        errors.append("settings UI 必须用 setAttribute('for', ...) 关联 output")
    if "opacityOutput.htmlFor" in ui:
        errors.append("HTMLOutputElement.htmlFor 只读，不得赋值")
    for aria_name in ("aria-expanded", "aria-pressed", "aria-disabled"):
        if aria_name not in ui:
            errors.append(f"settings UI 缺少 {aria_name}")
    if "tuning.disabled = disabled;" not in ui or "resetButton.disabled = disabled;" not in ui:
        errors.append("native 微调控件必须真实 disabled")
    if "ensureMounted: ensureMounted" not in ui or "ui.ensureMounted();" not in runtime:
        errors.append("SPA body 替换后 settings UI 必须可重挂载")
    if 'makeElement("button", "zmr-command-button", "全部恢复默认")' not in ui or "onResetAll: resetAllThemes" not in runtime:
        errors.append("settings UI 缺少清除两套 overrides 的全部恢复默认")
    normalize_position = ui.find('makeInput("zmr-normalize-quotes", "checkbox")')
    tuning_position = ui.find('makeElement("fieldset", "zmr-tuning-group")')
    if normalize_position < 0 or tuning_position < 0 or normalize_position > tuning_position:
        errors.append("引号规范化 checkbox 必须位于 native disabled fieldset 外")
    if 'normalizeQuotes: false' not in runtime or 'typeof raw.normalizeQuotes === "boolean"' not in runtime:
        errors.append("normalizeQuotes 必须默认 false 并严格布尔校验")
    if STORAGE_KEY_LITERAL not in runtime or LEGACY_STORAGE_KEY_LITERAL not in runtime or "var SCHEMA = 2;" not in runtime:
        errors.append("runtime 必须使用 schema-2 并支持 schema-1 迁移")
    if "overrides: { day: {}, night: {} }" not in runtime or "effectiveTheme(state.mode)" not in runtime:
        errors.append("runtime 必须分离 preset defaults 与白名单 overrides")
    if "delete state.overrides[state.mode];" not in runtime or "state.overrides.day = {};" not in runtime or "state.overrides.night = {};" not in runtime:
        errors.append("runtime 缺少当前/全部 overrides 重置契约")
    if "LEGACY_DEFAULTS[mode][key]" not in runtime or "migrateLegacy" not in runtime:
        errors.append("schema-1 迁移必须只保留相对固定旧默认的差异")
    if "function handlePageHide()" not in runtime or "function handlePageShow()" not in runtime:
        errors.append("runtime 缺少 pagehide/pageshow 挂起门闩")
    if "!suspended && !pageHidden" not in runtime or "global.clearTimeout(routeTimer);" not in runtime:
        errors.append("pagehide 后必须取消 route timer 并禁止 pageshow 前重入")
    if 'quotePlugin.setNormalizeQuotes(state.normalizeQuotes);' not in runtime or 'cleanup.flush(chatRoot' not in runtime:
        errors.append("normalizeQuotes 开启时必须更新插件并有界 flush 当前聊天")
    if 'setNormalizeQuotes: function setNormalizeQuotes(enabled)' not in quote or 'var normalizeQuotes = settings.normalizeQuotes === true;' not in quote:
        errors.append("quote plugin 缺少默认关闭的 normalizeQuotes 开关")
    if "COMPONENT_BOUNDARY_SELECTOR" not in quote or 'classList.remove("zmr-hdm")' not in quote:
        errors.append("quote plugin 必须保留组件边界并可增量移除 zmr-hdm")
    if '".zmr-hdm"' in cleanup:
        errors.append("zmr-hdm 是可变语义标记，不得成为清污 skip boundary")
    if "innerHTML" in scripts or "cssText" in scripts or re.search(r"\bonclick\s*=", scripts):
        errors.append("JS 源码不得使用 innerHTML/cssText/inline onclick")
    broad_scans = (
        r"document(?:Ref|Local)?\.body\.querySelectorAll",
        r"querySelectorAll\(\s*['\"]\*['\"]\s*\)",
        r"createTreeWalker\(\s*(?:document|documentRef|documentLocal)\.body",
        r"(?:document|documentRef|documentLocal)\.body\.textContent",
    )
    for pattern in broad_scans:
        if re.search(pattern, scripts):
            errors.append(f"禁止全量 body 文本/元素扫描: {pattern}")
    required_runtime_fragments = (
        "chooseNewestStyle(currentStyles())",
        "takeoverStyle(newest || themeStyle)",
        "removeDuplicateStyles(candidate)",
        "removeAllOwnedStyles(themeStyle)",
        "removeAllOwnedStyles(null)",
        "documentRef.head.appendChild(candidate)",
        "previousLease.destroy",
        'if (reason === "superseded")',
        "themeStyle.remove()",
        "previousLease.refreshAssets(incomingStyle)",
        "previousLease.reenter()",
    )
    for fragment in required_runtime_fragments:
        if fragment not in runtime:
            errors.append(f"资源接管/租约契约缺失: {fragment}")
    reuse_start = runtime.find("previousLease && previousLease.meta")
    reuse_return = runtime.find("return;", reuse_start)
    destroy_start = runtime.find("previousLease.destroy", reuse_return)
    if reuse_start < 0 or reuse_return < reuse_start or destroy_start < reuse_return:
        errors.append("同 owner/version/id 租约必须先复用并 return，不得 destroy")
    leave_match = re.search(r"function leaveChat\(\) \{([\s\S]*?)\n  \}", runtime)
    if not leave_match:
        errors.append("runtime 缺少 leaveChat")
    else:
        leave_body = leave_match.group(1)
        leave_order = [leave_body.find(fragment) for fragment in ("cleanup.stop();", "cleanup.restore();", 'rootElement.removeAttribute("data-zmr-mode")', "clearReadingVariables();")]
        if any(position < 0 for position in leave_order) or leave_order != sorted(leave_order):
            errors.append("leaveChat 必须 stop -> restore -> 移除 mode -> 清阅读变量")
    if STORAGE_KEY_LITERAL not in runtime:
        errors.append("runtime localStorage 键缺少 package namespace/schema-2")
    for bounds in (("fontSize", "12", "32"), ("lineHeight", "1.1", "2.6"), ("opacity", "40", "100")):
        if not all(value in runtime for value in bounds):
            errors.append(f"runtime 缺少存储范围校验: {bounds[0]}")
    if ':not([data-zmr-owned], [data-zmr-owned] *)' not in css:
        errors.append("theme.css 通用控件必须排除 runtime owned 后代")
    for boundary in ("[data-sid] *", "[data-g3v] *", ".g3-host *", ".z-status-box *", "[data-statusbar] *", "[data-zsf-ball] *"):
        if boundary not in css:
            errors.append(f"theme.css 缺少组件隔离边界: {boundary}")


STORAGE_KEY_LITERAL = 'tavern-mmd/zmr/theme-settings/schema-2'
LEGACY_STORAGE_KEY_LITERAL = 'tavern-mmd/zmr/theme-settings/schema-1'


def validate(obj: Mapping[str, object], rendered: str) -> List[str]:
    errors: List[str] = []
    expected_root_keys = {"pageDepth", "statusbar", "beginning", "regex_scripts"}
    if set(obj) != expected_root_keys:
        errors.append(f"MMD 根字段必须恰为四字段，当前: {sorted(obj)}")
    if obj.get("pageDepth") != 2:
        errors.append("pageDepth 必须为 2")
    expected_statusbar = "".join(module.marker for module in MODULES)
    if obj.get("statusbar") != expected_statusbar:
        errors.append("statusbar 标记缺失、重复或顺序错误")
    if obj.get("beginning") != "":
        errors.append("beginning 应为空，不夹带演示正文")
    scripts = obj.get("regex_scripts")
    if not isinstance(scripts, list) or len(scripts) != len(MODULES):
        errors.append(f"regex_scripts 必须恰有 {len(MODULES)} 条")
        return errors
    expected_script_keys = {"id", "scriptName", "findRegex", "replaceString"}
    markers = [module.marker for module in MODULES]
    asset_ids = set()
    for index, (module, script) in enumerate(zip(MODULES, scripts), start=1):
        prefix = f"规则 {index} ({module.asset_id})"
        if not isinstance(script, dict):
            errors.append(f"{prefix} 不是对象")
            continue
        if set(script) != expected_script_keys:
            errors.append(f"{prefix} 必须恰为四字段")
        if script.get("id") != -1:
            errors.append(f"{prefix} id 必须为 -1")
        find_regex = script.get("findRegex")
        replace_string = script.get("replaceString")
        if not slash_delimited(find_regex):
            errors.append(f"{prefix} findRegex 未使用 /.../ 格式")
        if isinstance(find_regex, str) and len(find_regex) > MAX_FIND_REGEX:
            errors.append(f"{prefix} findRegex {len(find_regex)} > {MAX_FIND_REGEX}")
        if not isinstance(replace_string, str):
            errors.append(f"{prefix} replaceString 不是字符串")
            continue
        if len(replace_string) > MAX_REPLACE_STRING:
            errors.append(f"{prefix} replaceString {len(replace_string)} > {MAX_REPLACE_STRING}")
        if len(replace_string) > PROJECT_REPLACE_LIMIT:
            errors.append(f"{prefix} replaceString {len(replace_string)} > 项目余量上限 {PROJECT_REPLACE_LIMIT}")
        if "\n" in replace_string or "\r" in replace_string:
            errors.append(f"{prefix} replaceString 含真实换行")
        metadata = (
            f"data-zmr-owned='asset'",
            f"data-zmr-owner='{OWNER}'",
            f"data-zmr-version='{VERSION}'",
            f"data-zmr-id='{module.asset_id}'",
        )
        for fragment in metadata:
            if fragment not in replace_string:
                errors.append(f"{prefix} 缺资源 metadata: {fragment}")
        foreign_markers = [marker for marker in markers if marker in replace_string]
        if foreign_markers:
            errors.append(f"{prefix} replaceString 含触发标记，可能交叉污染: {foreign_markers}")
        if "_mmd_" in replace_string:
            errors.append(f"{prefix} 使用了第三方 _mmd_* 命名")
        if module.asset_id in asset_ids:
            errors.append(f"资源 id 重复: {module.asset_id}")
        asset_ids.add(module.asset_id)
    css_source = read_source(BASE_DIR / "theme.css")
    check_css_scope(css_source, errors)
    check_contrast(css_source, errors)
    check_source_contracts(errors)
    if rendered.encode("utf-8").startswith(b"\xef\xbb\xbf"):
        errors.append("序列化结果带 UTF-8 BOM")
    try:
        round_trip = json.loads(rendered)
    except json.JSONDecodeError as error:
        errors.append(f"序列化结果无法回读: {error}")
    else:
        if round_trip != obj:
            errors.append("JSON 回读结果与构建对象不一致")
    return errors


def format_lengths(obj: Mapping[str, object]) -> Iterable[str]:
    scripts = obj["regex_scripts"]
    assert isinstance(scripts, list)
    for index, script in enumerate(scripts, start=1):
        assert isinstance(script, dict)
        yield (
            f"  {index}. {script['scriptName']}: "
            f"findRegex={len(script['findRegex'])}, "
            f"replaceString={len(script['replaceString'])}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="校验源码与已生成 JSON，不写文件")
    args = parser.parse_args()
    try:
        obj = build_object()
        rendered = serialize(obj)
        errors = validate(obj, rendered)
    except (OSError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    if errors:
        print("[ERROR] 构建 guard 未通过:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    if args.check:
        if not OUTPUT_PATH.exists():
            print(f"[ERROR] 缺少生成文件: {OUTPUT_PATH.name}", file=sys.stderr)
            return 1
        existing = OUTPUT_PATH.read_bytes()
        expected = rendered.encode("utf-8")
        if existing != expected:
            print(f"[ERROR] {OUTPUT_PATH.name} 已过期，请运行 python build_theme.py", file=sys.stderr)
            return 1
        action = "校验通过，生成文件与源码一致"
    else:
        OUTPUT_PATH.write_bytes(rendered.encode("utf-8"))
        action = f"已生成 {OUTPUT_PATH.name}"
    print(f"[OK] {action}")
    print(f"[OK] MMD 四字段，{len(MODULES)} 条正则，无 BOM")
    print("字符长度:")
    for line in format_lengths(obj):
        print(line)
    print(f"  JSON={len(rendered)} 字符，UTF-8={len(rendered.encode('utf-8'))} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
