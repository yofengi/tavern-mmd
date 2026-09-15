#!/usr/bin/env python3
"""One local entry for same-layer build, audit, old-MMD preview and browser checks."""
import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from build_same_layer import ASSETS, build
from verify_same_layer import verify
from same_layer_preview import preview_release

HERE = Path(__file__).resolve().parent


def load_project(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    allowed = {'platform', 'chatVersion', 'source', 'appId', 'buildId', 'title', 'engine', 'models', 'allowedActions', 'preview'}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError('作品配置包含未知字段')
    if data.get('platform') != 'mmd' or type(data.get('chatVersion')) is not int or data['chatVersion'] != 0:
        raise ValueError('此入口仅用于当前 MMD 旧页：platform=mmd，chatVersion=0')
    for key in ('source', 'appId', 'buildId', 'title'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError('作品配置缺少有效的 ' + key)
    for key in ('engine', 'models'):
        if type(data.get(key, True)) is not bool:
            raise ValueError(key + ' 必须为布尔值')
    actions = data.get('allowedActions')
    if actions is not None and (not isinstance(actions, list) or any(not isinstance(x, str) or not x for x in actions) or len(set(actions)) != len(actions)):
        raise ValueError('allowedActions 必须是无重复动作名数组')
    preview = data.get('preview', {})
    if not isinstance(preview, dict) or set(preview) - {'messages'}:
        raise ValueError('preview 仅接受本地模拟 messages，不接受账号、后端或平台覆盖参数')
    if 'messages' in preview:
        rows = preview['messages']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
            raise ValueError('预览消息数量必须在 1–100 之间')
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'role', 'text'} or row['role'] not in ('user', 'assistant') or not isinstance(row['text'], str) or len(row['text']) > 6000:
                raise ValueError('每条预览消息必须包含有效的 role 和 text')
    source = (path.parent / data['source']).resolve()
    if not source.is_dir():
        raise ValueError('作品源码目录不存在：' + str(source))
    return {**data, 'engine': data.get('engine', True), 'models': data.get('models', True)}, source


def render_report(out, report):
    (out / 'review-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    labels = {'PASS': '本地自动检查通过', 'PARTIAL': '本地检查未完成', 'FAIL': '本地检查失败'}
    lines = ['# 同层卡预览与审核', '', labels[report['status']], '', '| 检查 | 状态 | 说明 |', '|---|---|---|']
    for step in report['steps']:
        lines.append('| ' + step['name'] + ' | ' + step['status'] + ' | ' + step.get('message', '').replace('\n', ' ').replace('|', '/') + ' |')
    lines += ['', '真实 MMD、账号权限、模型生成、服务端保存、平台净化与实体手机：未验证。',
              '截图用于人工检查外观；自动检查通过不能代表所有视觉和剧情内容已审核。']
    if (out / 'preview/preview.html').exists():
        lines += ['', '[打开 MMD 与同层卡联动预览](preview/preview.html)']
    (out / 'review-report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    rows = ''
    for step in report['steps']:
        detail = html.escape(step.get('message', ''))
        if step.get('warnings'):
            detail += '<ul>' + ''.join('<li>' + html.escape(w) + '</li>' for w in step['warnings']) + '</ul>'
        if step.get('checks'):
            detail += '<details><summary>查看交互检查明细</summary><ul>' + ''.join('<li>' + html.escape(c['name'] + '：' + c['status'] + ('；' + c['reason'] if c.get('reason') else '')) + '</li>' for c in step['checks']) + '</ul></details>'
        rows += '<tr><td>' + html.escape(step['name']) + '</td><td>' + step['status'] + '</td><td>' + detail + '</td></tr>'
    link = '<a href="preview/preview.html">打开 MMD / 同层卡预览</a>' if (out / 'preview/preview.html').exists() else '<p>尚未生成可用预览，请先修复上述问题。</p>'
    shots = ''.join('<a href="browser/' + html.escape(p.name, quote=True) + '">' + html.escape(p.stem) + '</a> ' for p in sorted((out / 'browser').glob('*.png')))
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>同层卡审核报告</title><style>body{max-width:1050px;margin:40px auto;padding:0 20px;background:#151920;color:#e0e6ed;font:15px/1.7 system-ui}a{color:#adcaf0}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #424c5b}h1{font-size:25px}.notice{color:#b2bbc8}nav{display:flex;gap:15px;flex-wrap:wrap}</style><h1>' + labels[report['status']] + '</h1><p>' + html.escape(report.get('appId','') + ' / ' + report.get('buildId','')) + '</p>' + link + '<table><tr><th>检查</th><th>状态</th><th>说明</th></tr>' + rows + '</table><p class="notice">本地模拟不连接 MMD 账号和模型服务。真实平台、服务端保存、净化与实体手机仍需验收；外观截图需要人工检查。</p><nav>' + shots + '</nav><p><a href="validation.txt">格式审核明细</a> · <a href="review-report.json">结构化报告</a> · <a href="release/release-manifest.json">发布版本与校验值</a></p></html>'
    (out / 'review-report.html').write_text(page, encoding='utf-8')


def review(project, out, browser='auto', node=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'format': 'mmd-same-layer-review', 'scope': 'local-only', 'status': 'FAIL', 'steps': [],
              'realMmd': 'NOT RUN', 'physicalMobile': 'NOT RUN', 'manualVisualReview': 'NOT RUN'}
    current = '作品配置'
    def step(name, status, message='', **evidence):
        report['steps'].append({'name': name, 'status': status, 'message': message, **evidence})
    try:
        config, source = load_project(project)
        report['buildId'] = config['buildId']; report['appId'] = config['appId']
        # Freeze the builder's source inputs, so preview and package share a version.
        snapshot = out / 'source'; snapshot.mkdir()
        hashes = {}
        for asset in ASSETS.iterdir():
            if asset.suffix not in ('.js', '.html', '.css'):
                continue
            raw = (source / asset.name).read_bytes(); hashes[asset.name] = hashlib.sha256(raw).hexdigest(); (snapshot / asset.name).write_bytes(raw)
        (out / 'review-inputs.json').write_text(json.dumps({'project': config, 'sourceFiles': hashes}, ensure_ascii=False, indent=2), encoding='utf-8')
        step(current, 'PASS', '旧 MMD；已固定本次源码与配置')
        current = '构建发布文件'
        release_config = {k: v for k, v in config.items() if k in ('appId', 'buildId', 'title', 'engine', 'models', 'allowedActions')}
        manifest = build(out / 'release', release_config, snapshot)
        step(current, 'PASS', f"{manifest['rules']} 条正则", payloadSha256=manifest['payloadSha256'])
        current = 'MMD 通用格式审核'
        result = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'validate.py'), str(out / 'release/same-layer-mmd.json'), '--platform', 'mmd'], capture_output=True, text=True, encoding='utf-8', timeout=120)
        (out / 'validation.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise ValueError('通用审核失败，详见 validation.txt')
        warnings = [line[7:] for line in result.stdout.splitlines() if line.startswith('[WARN]')]
        step(current, 'PASS', f'0 错误，{len(warnings)} 条待阅读提示', warnings=warnings)
        current = '同层载荷审核'
        verification = verify(out / 'release', node)
        step(current, 'PASS', '分片、完整载荷、Frame 一致，脚本语法通过', verification=verification)
        current = '生成联动预览'
        info = preview_release(out / 'release', out / 'preview', {'title': config['title'], **config.get('preview', {})})
        step(current, 'PASS', '复用旧 MMD 全景外壳，嵌入原样发布载荷', payloadSha256=info['releasePayloadSha256'])
        current = '浏览器交互审核'
        executable = node or shutil.which('node')
        if browser == 'skip' or not os.environ.get('PLAYWRIGHT_MODULE') or not executable:
            if browser == 'required':
                raise ValueError('浏览器审核需要 Node、PLAYWRIGHT_MODULE 与已安装浏览器')
            step(current, 'NOT RUN', '本次跳过或缺少浏览器运行环境；不能记为通过')
            report['status'] = 'PARTIAL'
        else:
            result = subprocess.run([executable, str(HERE / 'review_same_layer_browser.mjs'), str(out / 'preview'), str(out / 'browser')], capture_output=True, text=True, encoding='utf-8', timeout=180)
            (out / 'browser-log.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
            evidence_path = out / 'browser/results.json'
            evidence = json.loads(evidence_path.read_text(encoding='utf-8')) if evidence_path.exists() else None
            if result.returncode or not evidence or evidence.get('status') != 'PASS':
                raise ValueError('浏览器检查未通过，详见 browser-log.txt 与 browser/results.json')
            step(current, 'PASS', f"{len(evidence['checks'])} 项检查完成；外观截图已生成", checks=evidence['checks'])
            report['status'] = 'PASS'
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        step(current, 'FAIL', str(error)); report['status'] = 'FAIL'
    finally:
        render_report(out, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True, help='作品 JSON 配置；source 相对此文件解析')
    parser.add_argument('--out', type=Path, required=True, help='新的审核输出目录，不覆盖旧结果')
    parser.add_argument('--browser', choices=['auto', 'required', 'skip'], default='auto')
    parser.add_argument('--node', help='可选 Node 路径；其他环境依赖从 PATH / PLAYWRIGHT_MODULE 读取')
    args = parser.parse_args()
    try:
        result = review(args.project, args.out, args.browser, args.node)
    except OSError as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({'status': result['status'], 'report': str(args.out / 'review-report.html')}, ensure_ascii=False))
    sys.exit({'PASS': 0, 'FAIL': 1, 'PARTIAL': 2}[result['status']])
