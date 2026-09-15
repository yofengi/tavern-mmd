#!/usr/bin/env python3
"""Build the self-contained old-MMD same-layer starter; standard library only."""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "same-layer-kit"
LIMIT = 18000  # Engineering margin; the platform replacement limit remains 20000.


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rules_for(source, app_id, build_id):
    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    parts = [encoded[i:i + 16000] for i in range(0, len(encoded), 16000)]
    if len(parts) + 1 > 130:
        raise ValueError("载荷超过 130 条正则，请减少依赖或拆分产品功能")
    digest = sha(source.encode("utf-8"))
    key = app_id + "_" + sha(build_id.encode())[:10]
    token = lambda i: "【SL_" + key + "_" + str(i).zfill(3) + "】"
    rows = []
    for i, part in enumerate(parts):
        data = {"index": i, "hash": sha(part.encode()), "text": part}
        start = "globalThis.__MMD_SL_PARTS__=globalThis.__MMD_SL_PARTS__||Object.create(null);"
        if i == 0:
            start += "globalThis.__MMD_SL_PARTS__[" + dump(key) + "]=[];"
        code = start + "globalThis.__MMD_SL_PARTS__[" + dump(key) + "][" + str(i) + "]=" + dump(data) + ";"
        rows.append({"id": -1, "scriptName": "SL" + str(i).zfill(3),
                     "findRegex": "/" + token(i) + "/g", "replaceString": "<script>" + code + "</script>" + token(i + 1)})
    # No author source occurs in these wrappers: replacement-template tokens cannot corrupt it.
    launcher = """(async function(){
const key=KEY, expected=TOTAL, digest=DIGEST;
try {
 const parts=globalThis.__MMD_SL_PARTS__?.[key];
 if(!Array.isArray(parts)||parts.length!==expected)throw Error('载荷分片数量不匹配');
 async function hash(bytes){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');}
 for(let i=0;i<expected;i++){
  const part=parts[i];if(!part||part.index!==i||await hash(new TextEncoder().encode(part.text))!==part.hash)throw Error('载荷分片校验失败');
 }
 const bytes=Uint8Array.from(atob(parts.map(p=>p.text).join('')),c=>c.charCodeAt(0));
 if(await hash(bytes)!==digest)throw Error('完整载荷校验失败');
 const script=document.createElement('script');script.textContent=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
 (document.head||document.documentElement).appendChild(script);script.remove();
}catch(error){
 const box=document.createElement('div');box.style.cssText='position:fixed;inset:12px;z-index:2147483647;padding:20px;background:white;color:#702020;white-space:normal';
 const text=document.createElement('p');text.textContent='同层卡启动失败：'+error.message;
 const close=document.createElement('button');close.textContent='关闭并返回 MMD';close.onclick=()=>box.remove();
 box.append(text,close);document.body.appendChild(box);
}
})();""".replace("KEY", dump(key)).replace("TOTAL", str(len(parts))).replace("DIGEST", dump(digest))
    rows.append({"id": -1, "scriptName": "SL启动", "findRegex": "/" + token(len(parts)) + "/g",
                 "replaceString": "<script>" + launcher + "</script>"})
    for row in rows:
        if utf16_length(row["replaceString"]) > LIMIT or utf16_length(row["findRegex"]) > 1000:
            raise ValueError("规则超出构建安全线")
    if utf16_length(token(0)) > 200:
        raise ValueError("入口超过保守 200 字符预算")
    return token(0), rows, digest


def build(out, config, source_dir=ASSETS, preview=False):
    if not re.fullmatch(r"[a-z0-9-]{1,40}", config["appId"]):
        raise ValueError("appId 必须为 1–40 位小写字母、数字或连字符")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", config["buildId"]) or config["buildId"] == "dev":
        raise ValueError("buildId 必须是明确的发布标识，不能为 dev")
    config = {**config, "models": config.get("models", True)}
    js = "\n".join((source_dir / name).read_text(encoding="utf-8-sig") for name in ("core.js", "actions.js", "actions-dom.js", "actions-handlers.js", "provided-actions.js", "models.js", "provided-models.js", "native.js", "host.js"))
    frame_js = "\n".join((source_dir / name).read_text(encoding="utf-8-sig") for name in ("frame-ui-config.js", "frame-models.js", "frame-panels.js", "frame-features.js", "frame.js"))
    # Protect HTML parsing, while keeping JavaScript source readable before bundling.
    frame_js = re.sub(r"</script", r"<\\/script", frame_js, flags=re.I)
    template = (source_dir / "frame.html").read_text(encoding="utf-8-sig")
    if template.count("/*__FRAME_JS__*/") != 1:
        raise ValueError("frame.html 必须含一个 /*__FRAME_JS__*/ 插入点")
    if "/*__FRAME_CSS__*/" in template:
        template = template.replace("/*__FRAME_CSS__*/", (source_dir / "frame.css").read_text(encoding="utf-8-sig"))
    frame = template.replace("/*__FRAME_JS__*/", frame_js)
    native_config = {**config, "mode": "native"}
    boot = "\nMmdSameLayerHost.boot(" + dump(native_config) + "," + dump(frame) + ");"
    payload = js + boot
    entry, rules, digest = rules_for(payload, config["appId"], config["buildId"])
    package = {"pageDepth": 2, "statusbar": entry,
               "beginning": "游戏页面已准备。顶部可返回 MMD 使用原生聊天功能。", "regex_scripts": rules}
    outputs = {"same-layer-mmd.json": dump(package), "frame.html": frame}
    if preview:
        mock_boot = "\nMmdSameLayerHost.boot(" + dump({**config, "mode": "mock"}) + "," + dump(frame) + ");"
        preview_js = re.sub(r"</script", r"<\\/script", js + mock_boot, flags=re.I)
        outputs["preview.html"] = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>同层卡本地预览</title>'
                                   '<body><h1>MMD 原生界面占位</h1><p>这是本地模拟，未连接真实 MMD。</p>'
                                   '<script>' + preview_js + '</script></body></html>')
    manifest = {"format": "mmd-same-layer-release", "platform": "mmd", "chatVersion": 0,
                "buildId": config["buildId"], "appId": config["appId"], "protocol": "mmd-sl/1",
                "adapter": "native-bridge", "engine": config["engine"], "models": config["models"], "payloadSha256": digest,
                "rules": len(rules), "maxReplacementUtf16": max(utf16_length(r["replaceString"]) for r in rules),
                "files": {name: sha(text.encode()) for name, text in outputs.items()},
                "evidence": {"realMmd": "NOT RUN", "physicalMobile": "NOT RUN"}}
    outputs["release-manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2)
    out.mkdir(parents=True, exist_ok=True)
    if any((out / name).exists() for name in outputs):
        raise FileExistsError("候选文件已存在，请使用新的输出目录；不会覆盖旧候选")
    for name, text in outputs.items():
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ASSETS, help="复制并编辑后的同层卡源码目录")
    parser.add_argument("--app-id", default="fog-harbor")
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--title", default="雾港寻物")
    parser.add_argument("--no-engine", action="store_true")
    parser.add_argument("--no-models", action="store_true", help="不显示模型列表与模型设置模块")
    parser.add_argument("--preview", action="store_true", help="另建纯本地 Mock 预览，导入 JSON 仍为 native 模式")
    args = parser.parse_args()
    result = build(args.out, {"appId": args.app_id, "buildId": args.build_id,
                   "title": args.title, "engine": not args.no_engine, "models": not args.no_models}, args.source, args.preview)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
