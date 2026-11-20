"""用 skill 自带的绮梦聊天页沙盒预览原生卡和传统页卡。"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


BUNDLED_SHELL = Path(__file__).resolve().parents[1] / "assets" / "suki-sandbox" / "dist-sandbox"
SHELL_FILES = ("index.html", "sandbox.js", "sandbox.css", "sandbox-zh.js")


def bundle_id(files):
    digest = hashlib.sha256()
    for name in SHELL_FILES:
        data = files[name]
        if not data.strip() or (name != "index.html" and data.lstrip().startswith(b"<")):
            raise ValueError(f"{name} 的内容与沙盒发布文件不符")
        digest.update(hashlib.sha256(data).digest())
    if not all(name in files["index.html"] for name in (b"sandbox.js", b"sandbox.css")):
        raise ValueError("index.html 未引用绮梦沙盒的 JS 与 CSS")
    return digest.hexdigest()


def local_id(folder):
    return bundle_id({name: (folder / name).read_bytes() for name in SHELL_FILES})


def resolve_shell(override):
    folder = (override or BUNDLED_SHELL).resolve()
    digest = local_id(folder)
    if override is None or folder == BUNDLED_SHELL.resolve():
        source = json.loads((BUNDLED_SHELL.parent / "source.json").read_text(encoding="utf-8"))
        if not isinstance(source, dict) or digest != source.get("bundleSha256"):
            raise ValueError("随 skill 分发的绮梦沙盒哈希不符，请重新安装 skill 或用 --shell 指定官方构建")
    elif re.fullmatch(r"[0-9a-fA-F]{64}", folder.name) and digest != folder.name.lower():
        raise ValueError(f"快照内容与目录名的哈希不一致：{folder}")
    print(f"绮梦本地沙盒 {digest}  {folder}", file=sys.stderr, flush=True)
    return folder


def find_cli():
    binary = shutil.which("hearthroom")
    if binary:
        return binary
    if os.name == "nt":
        for root in (os.environ.get("LOCALAPPDATA"), Path.home() / "AppData" / "Local"):
            if root:
                binary = Path(root) / "Programs" / "hearthroom" / "hearthroom.exe"
                if binary.is_file():
                    return str(binary)
    raise FileNotFoundError("需要 Hearthroom CLI，可从 https://github.com/hearthroom/cli/releases 安装")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", type=Path, help="含 card.json 的绮梦卡目录")
    parser.add_argument("--shell", type=Path, help="指定其他官方构建或已有快照，默认使用 skill 自带沙盒")
    parser.add_argument("--port", type=int, default=0, help="预览端口，默认自动分配")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--open", action="store_true", help="在浏览器中打开本地预览")
    mode.add_argument("--check", action="store_true", help="运行官方无头浏览器截图检查")
    parser.add_argument("--json", action="store_true", help="输出官方 CLI 的 JSON")
    args = parser.parse_args(argv)

    try:
        card = args.card.resolve()
        if not (card / "card.json").is_file():
            raise ValueError("请指定含 card.json 的绮梦原生卡目录")
        rules = card / "rules.json"
        if rules.is_file():
            settings = json.loads(rules.read_text(encoding="utf-8-sig"))
            if not isinstance(settings, dict):
                raise ValueError("原生 rules.json 应为对象")
            page_mode = settings.get("pageMode")
            if page_mode == "classic":
                print("传统页卡正在绮梦沙盒中兼容预览。", file=sys.stderr, flush=True)
            elif page_mode not in (None, "", "sandbox"):
                raise ValueError(f"无法识别 rules.json 中的 pageMode：{page_mode}")
        cli = find_cli()
        shell = resolve_shell(args.shell)
        command = [cli, "card", "preview", str(card), "--shell", str(shell), "--port", str(args.port)]
        if args.open:
            command.append("--open")
        if args.check:
            command.append("--check")
        if args.json:
            command.append("--json")
        return subprocess.run(command, env={**os.environ, "HEARTHROOM_NO_UPDATE_NOTIFIER": "1"}).returncode
    except (OSError, ValueError) as exc:
        print(f"绮梦预览失败：{exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
