"""Compose the existing old-MMD panorama shell with an original local state simulator.

The release payload is embedded unchanged. No real service or account is used.
"""
import base64
import hashlib
import html
import importlib.util
import json
import re
import struct
import shutil
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'fixtures/mmd-legacy'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def legacy_shell():
    spec = importlib.util.spec_from_file_location('mmd_legacy_preview_shell', HERE / 'build-preview.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    page = module._mmd_panorama_page('', module._panorama_hooks('mmd'), '', '')
    page = page.replace(module.MMD_PANEL_SCAFFOLD, '').replace(module.MMD_POPUP_SIM, '<template id="mmd-native-panel-templates">' + module.MMD_POPUP_SIM + '</template>')
    inventory = {'shortcuts': re.findall(r'<button class="shortcut-btn"[^>]*>([^<]+)</button>', page),
                 'more': re.findall(r'<uni-view class="item-title">([^<]+)</uni-view>', page),
                 'panels': [name for name, _, _ in module.MMD_PANEL_TOOLS]}
    return module._mmd_panorama_css(), page, inventory


def release_payload(directory):
    manifest = json.loads((directory / 'release-manifest.json').read_text(encoding='utf-8'))
    raw_package = (directory / 'same-layer-mmd.json').read_bytes()
    if sha(raw_package) != manifest['files']['same-layer-mmd.json'] or sha((directory / 'frame.html').read_bytes()) != manifest['files']['frame.html']:
        raise ValueError('预览输入文件与发布清单不一致')
    package = json.loads(raw_package)
    parts = []
    for rule in package['regex_scripts'][:-1]:
        match = re.search(r'\]=({.*?});</script>', rule['replaceString'], re.S)
        if not match:
            raise ValueError('未识别的同层载荷分片，请先运行 verify_same_layer.py')
        parts.append(json.loads(match.group(1))['text'])
    raw = base64.b64decode(''.join(parts), validate=True)
    if sha(raw) != manifest['payloadSha256']:
        raise ValueError('预览输入载荷与发布清单不一致')
    return raw.decode('utf-8'), manifest, package


def write_icons(out):
    # Original simple local glyph assets. Filenames match observed selector facts;
    # artwork is illustrative, never represented as a screenshot of MMD assets.
    names = re.findall(r"['\"]([a-z_0-9]+\.(?:png|svg))['\"]", (FIXTURES / 'host.js').read_text(encoding='utf-8'))
    icons = out / 'icons'; icons.mkdir()
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    patterns = {
        'comment': ['0111110','1100011','1010101','1000001','0111110','0011000','0010000'],
        'share': ['0001000','0001100','1111110','1001111','1001100','1001000','1111000'],
        'collect': ['0001000','0011100','1111111','0111110','0011100','0110110','1100011'],
        'refresh': ['0111110','1100011','1000011','1001111','1000000','1100001','0111110'],
        'setting': ['0011100','1011101','1111111','1100011','1111111','1011101','0011100'],
        'edit': ['0000110','0001110','0011100','0111000','1110000','1100000','1000000'],
        'default': ['0111110','0100010','0101010','0101010','0100010','0111110','0000000']}
    for name in set(names):
        if name.endswith('.svg'):
            (icons / name).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect x="5" y="4" width="14" height="16" rx="3" fill="none" stroke="#9dabbe" stroke-width="2"/><path d="M9 9h6M9 13h6" stroke="#9dabbe" stroke-width="2"/></svg>', encoding='utf-8')
            continue
        grid = patterns[next((key for key in patterns if key in name), 'default')]
        width,height={'ico_message_refresh.png':(80,81),'ico_message_edit.png':(56,57),'ico_message_share.png':(200,200)}.get(name,(24,24))
        def pixel(x, y):
            row, col = int(y*24/height-5)//2, int(x*24/width-5)//2
            return bytes((157, 171, 190, 255 if 0 <= row < 7 and 0 <= col < 7 and grid[row][col] == '1' else 0))
        rows = b''.join(b'\0' + b''.join(pixel(x,y) for x in range(width)) for y in range(height))
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
        (icons / name).write_bytes(png)


def preview_release(directory, out, preview_config=None):
    directory, out = Path(directory), Path(out)
    if out.exists():
        raise FileExistsError('预览目录已存在，请使用新目录')
    payload, manifest, package = release_payload(directory)
    css, shell, inventory = legacy_shell()
    config = {'title': manifest['appId'], **(preview_config or {}), 'appId': manifest['appId']}
    simulator = (FIXTURES / 'editor.js').read_text(encoding='utf-8') + '\n' + (FIXTURES / 'panels.js').read_text(encoding='utf-8') + '\n' + (FIXTURES / 'host.js').read_text(encoding='utf-8')
    styles = (FIXTURES / 'host.css').read_text(encoding='utf-8')
    def script(source):
        return '<script>' + re.sub(r'</script', r'<\\/script', source, flags=re.I) + '</script>'
    # Keep the published wrappers and launcher as well as the decoded payload hash.
    runtime = package['statusbar']
    for rule in package['regex_scripts']:
        pattern = rule['findRegex']
        if not pattern.startswith('/') or not pattern.endswith('/g'):
            raise ValueError('预览只接收已核验的同层构建链')
        runtime = runtime.replace(pattern[1:-2], rule['replaceString'])
    document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<base href="./"><link rel="stylesheet" href="vendor/vditor/dist/index.css"><style>' + css + '\n' + styles + '</style>' + shell
                + script('window.__MMD_LEGACY_PREVIEW_CONFIG__=' + json.dumps(config, ensure_ascii=False) + ';')
                + ''.join('<script src="vendor/' + name + '"></script>' for name in ('vditor/dist/js/i18n/zh_CN.js','vditor/dist/js/lute/lute.min.js','vditor/dist/index.min.js','opencc-js/dist/umd/full.js')) + script(simulator) + runtime + '</html>')
    outer = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>同层卡 · MMD 联动预览</title>
<style>*{box-sizing:border-box}body{margin:0;background:#15181c;color:#e3e6ec;font:14px system-ui}header{min-height:54px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:9px 16px;border-bottom:1px solid #353b46}header strong{margin-right:auto}button,a{font:inherit;color:inherit;background:#262d38;border:1px solid #495364;border-radius:5px;padding:6px 10px;text-decoration:none;cursor:pointer}.preview-stage{display:block;width:100%;height:calc(100dvh - 54px);border:0}small{color:#aeb6c2}@media(max-width:650px){header{min-height:90px}.preview-stage{height:calc(100dvh - 90px)}header strong{font-size:12px}small{font-size:11px}}</style>
<header><strong>旧 MMD + 同层卡 · 本地模拟</strong><small>模型、账号与平台保存均为模拟</small><button id="native-view">MMD 页面</button><button id="card-view">同层页面</button><a href="../review-report.html">审核报告</a></header>
<iframe class="preview-stage" title="MMD 模拟页面" sandbox="allow-scripts allow-same-origin allow-downloads" src="mmd.html"></iframe>
<script>const frame=document.querySelector('iframe');document.getElementById('native-view').onclick=()=>frame.contentWindow.__MMD_PREVIEW__?.native();document.getElementById('card-view').onclick=()=>frame.contentWindow.__MMD_PREVIEW__?.card();</script></html>'''
    out.mkdir(parents=True)
    (out / 'preview.html').write_text(outer, encoding='utf-8', newline='\n')
    (out / 'mmd.html').write_text(document, encoding='utf-8', newline='\n')
    write_icons(out)
    shutil.copytree(FIXTURES / 'vendor', out / 'vendor')
    info = {'format': 'mmd-same-layer-preview', 'buildId': manifest['buildId'], 'appId': manifest['appId'],
            'releasePayloadSha256': manifest['payloadSha256'], 'releaseFrameSha256': manifest['files']['frame.html'],
            'allowedActions': json.JSONDecoder().raw_decode(payload.rsplit('\nMmdSameLayerHost.boot(', 1)[-1])[0].get('allowedActions'),
            'nativeInventory': inventory,
            'shell': 'build-preview.py / old-MMD panorama', 'hostMode': 'native-dom', 'simulatedServices': True,
            'accuracy': {'shell': 'observed structure and CSS; illustrative icons', 'actions': 'representative local state transitions',
                         'realGeneration': 'NOT SIMULATED', 'serverPersistence': 'NOT SIMULATED', 'authentication': 'NOT SIMULATED',
                         'platformSanitization': 'NOT VERIFIED', 'physicalKeyboard': 'NOT VERIFIED'},
            'files': {p.relative_to(out).as_posix(): sha(p.read_bytes()) for p in out.rglob('*') if p.is_file()}}
    (out / 'preview-manifest.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    return info
