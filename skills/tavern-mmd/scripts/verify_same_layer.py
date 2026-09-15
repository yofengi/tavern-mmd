#!/usr/bin/env python3
"""Verify artifacts from build_same_layer.py; Node is used for syntax checks only."""
import argparse
import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

from build_same_layer import rules_for, sha, utf16_length


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(directory, node=None):
    manifest = json.loads((directory / 'release-manifest.json').read_text(encoding='utf-8'))
    require(manifest.get('format') == 'mmd-same-layer-release', '不是同层卡构建清单')
    require(manifest.get('platform') == 'mmd' and manifest.get('chatVersion') == 0, '平台必须为旧 MMD')
    require(manifest.get('protocol') == 'mmd-sl/1' and manifest.get('adapter') == 'native-bridge', '连接合同不匹配')
    files = manifest.get('files', {})
    require(set(files) in ({'frame.html', 'same-layer-mmd.json'}, {'frame.html', 'same-layer-mmd.json', 'preview.html'}), '清单文件集合不匹配')
    for name, digest in files.items():
        require(sha((directory / name).read_bytes()) == digest, '文件哈希不匹配：' + name)
    package = json.loads((directory / 'same-layer-mmd.json').read_text(encoding='utf-8'))
    require(set(package) == {'pageDepth', 'statusbar', 'beginning', 'regex_scripts'}, '导入顶层必须为四键')
    require(type(package['pageDepth']) is int and package['pageDepth'] == 2, '基座 pageDepth 不匹配')
    require(isinstance(package['statusbar'], str) and isinstance(package['beginning'], str), '入口字段类型错误')
    rows = package['regex_scripts']
    require(isinstance(rows, list) and 2 <= len(rows) <= 130, '分片条数超限或缺失')
    parts = []
    for i, row in enumerate(rows):
        require(isinstance(row, dict) and set(row) == {'id', 'scriptName', 'findRegex', 'replaceString'}, '规则必须为四键')
        require(type(row['id']) is int and row['id'] == -1, '规则 id 必须为 -1')
        require(all(isinstance(row[k], str) for k in ('scriptName', 'findRegex', 'replaceString')), '规则字段类型错误')
        require(utf16_length(row['findRegex']) <= 1000 and utf16_length(row['replaceString']) <= 18000, '构建预算超限')
        if i == len(rows) - 1:
            continue
        value = row['replaceString']
        start = value.find('{"index":')
        require(start >= 0, '缺少分片元数据')
        part, _ = json.JSONDecoder().raw_decode(value[start:])
        require(set(part) == {'index', 'hash', 'text'} and part['index'] == i, '分片顺序错误')
        require(isinstance(part['text'], str) and sha(part['text'].encode()) == part['hash'], '分片哈希错误')
        parts.append(part['text'])
    source = base64.b64decode(''.join(parts), validate=True).decode('utf-8')
    entry, expected_rows, digest = rules_for(source, manifest['appId'], manifest['buildId'])
    require(package['statusbar'] == entry and rows == expected_rows, '触发链、启动器或分片包装不匹配')
    require(digest == manifest['payloadSha256'], '完整载荷哈希不匹配')
    require(len(rows) == manifest['rules'], '清单条数不匹配')
    maximum = max(utf16_length(r['replaceString']) for r in rows)
    require(maximum == manifest['maxReplacementUtf16'], '清单字符数不匹配')
    require(utf16_length(entry) <= 200, '入口超预算')

    # The builder appends JSON arguments, so they can be inspected without running author JS.
    tail = source.rsplit('\nMmdSameLayerHost.boot(', 1)[-1]
    config, end = json.JSONDecoder().raw_decode(tail)
    require(tail[end:end + 1] == ',', '缺少 Frame 参数')
    frame, frame_end = json.JSONDecoder().raw_decode(tail[end + 1:])
    require(tail[end + 1 + frame_end:].strip() == ');', '启动参数尾部异常')
    require(config.get('mode') == 'native', '交付 JSON 不得连接 Mock')
    require(config.get('appId') == manifest['appId'] and config.get('buildId') == manifest['buildId'], '版本或作品标识不一致')
    require(type(config.get('engine')) is bool and config['engine'] == manifest['engine'], '引擎配置不一致')
    if 'models' in config or 'models' in manifest:
        require(type(config.get('models')) is bool and config['models'] == manifest.get('models'), '模型模块配置不一致')
    require(isinstance(frame, str) and frame.encode() == (directory / 'frame.html').read_bytes(), 'Frame 与载荷不一致')

    executable = node or shutil.which('node')
    require(executable, '未找到 Node；请用 --node 指定，不能省略语法验证')
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script\s*>', frame, re.I | re.S)
    require(scripts, 'Frame 缺少脚本')
    for label, script in [('Host', source)] + [(f'Frame {i + 1}', text) for i, text in enumerate(scripts)]:
        result = subprocess.run([str(executable), '--check'], input=script, encoding='utf-8', capture_output=True, timeout=30)
        require(result.returncode == 0, label + ' 语法错误：' + result.stderr)
    return {'rules': len(rows), 'maxReplacementUtf16': maximum, 'payloadSha256': digest,
            'syntax': 'PASS', 'realMmd': 'NOT RUN', 'physicalMobile': 'NOT RUN'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--node', help='Node 可执行文件路径；默认从 PATH 查找')
    args = parser.parse_args()
    try:
        result = verify(args.directory, args.node)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(1, 'FAIL: ' + str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
