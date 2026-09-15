#!/usr/bin/env python3
"""Inventory a pinned local mmd-hud-iframe checkout; never execute upstream code."""
import argparse
import json
import re
import subprocess
from pathlib import Path

MODEL_ACTIONS = {'openModelSettings', 'closeModelSettings', 'selectModelFilter', 'selectModel',
                 'openModelConfiguration', 'setModelSetting', 'submitModelConfiguration', 'closeModelConfiguration'}
CORE_ACTIONS = {'sendMessage'} | MODEL_ACTIONS

def frame_ui_actions():
    kit = Path(__file__).resolve().parent.parent / 'assets/same-layer-kit'
    text = '\n'.join((kit / name).read_text(encoding='utf-8') for name in ('frame.js', 'frame-models.js', 'frame-features.js', 'frame-panels.js'))
    return set(re.findall(r"'([A-Za-z][A-Za-z0-9]+)'", text))

def builtin_actions():
    kit = Path(__file__).resolve().parent.parent / 'assets/same-layer-kit'
    contracts = (kit / 'actions.js').read_text(encoding='utf-8')
    block = contracts.split('const groups = Object.freeze({', 1)[1].split('});', 1)[0]
    extra = set(re.findall(r"'([A-Za-z]\w*)'", block))
    implementation = (kit / 'actions-handlers.js').read_text(encoding='utf-8')
    run = implementation.split('async function run(', 1)[1]
    handlers = set(re.findall(r"case '([A-Za-z]\w*)':", run))
    for name in ('featureAction', 'closeSelectors'):
        table = implementation.split('const ' + name + ' = {', 1)[1].split('};', 1)[0]
        handlers.update(re.findall(r'(\w+):', table))
    if extra != handlers:
        raise ValueError('基座动作合同和处理器不一致：' + repr(extra ^ handlers))
    return CORE_ACTIONS | extra


def inventory(upstream):
    contract_path = upstream / 'src/contracts/bridge.ts'
    handler_path = upstream / 'src/bridge/actions/actionRegistry.ts'
    contract = contract_path.read_text(encoding='utf-8')
    handlers = handler_path.read_text(encoding='utf-8')
    section = re.search(r'export const ALL_NATIVE_ACTIONS = \[(.*?)\] as const', contract, re.S)
    if not section:
        raise ValueError('上游动作定义格式已改变，需要人工复核')
    names = re.findall(r"'([A-Za-z]\w*)'", section.group(1))
    if not names or len(names) != len(set(names)):
        raise ValueError('动作定义为空或重复')
    block = handlers.split('const handlers:', 1)[1].split('export const REGISTERED', 1)[0]
    registered = set(re.findall(r'^  (?:async )?(\w+)\([^\n]*\)\s*\{', block, re.M))
    unknown = registered - set(names)
    if unknown:
        raise ValueError('需要复核未声明处理器：' + ', '.join(sorted(unknown)))
    builtin = builtin_actions()
    frame_ui = frame_ui_actions() & builtin
    if builtin - registered:
        raise ValueError('基座包含上游未实现动作，必须复核')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=upstream, text=True).strip()
    payloads = contract.split('export interface NativeActionPayloadMap {', 1)[1].split('\n}', 1)[0]
    rows = []
    for name in names:
        signature = re.search(r'^  ' + re.escape(name) + r': (.+)$', payloads, re.M)
        line = next((i for i, value in enumerate(handlers.splitlines(), 1) if re.match(r'  (?:async )?' + re.escape(name) + r'\(', value)), None)
        if name in MODEL_ACTIONS:
            group = '模型'
            condition = '唯一原生模型入口/面板；列表或设置 revision 有效；动态 capability 允许'
        elif name in {'sendMessage', 'setInputText'}:
            group = '输入'; condition = '原生输入区可用；sendMessage 保护不同的原生草稿，完全相同的内容可发送'
        elif 'Conversation' in name or name == 'newChat':
            group = '会话'; condition = '当前会话面板与目标身份有效；删除类动作需确认流程'
        elif 'Persona' in name:
            group = '人设'; condition = '用户人设面板已打开且对应字段可修改'
        elif 'Supplement' in name:
            group = '补充设定'; condition = '补充设定面板/位置选择器处于相应状态'
        elif 'Message' in name or 'Edit' in name or 'Branch' in name or 'Generation' in name:
            group = '消息'; condition = '目标消息存在且身份/操作组匹配；破坏性操作需确认流程'
        else:
            group = '导航与设置'; condition = '对应原生入口/面板存在，且最新 capability 允许'
        rows.append({'action': name, 'group': group, 'payload': signature.group(1) if signature else '人工复核',
                     'upstreamImplemented': name in registered, 'upstreamHandlerLine': line,
                     'builtin': name in builtin, 'frameUI': name in frame_ui,
                     'frameUIKind': 'native-entry' if name in {'exit', 'openComments', 'openTutorial', 'openBackgroundPanel', 'openCustomInstructions'} else ('read-submit-close' if name in {'openChatSettings', 'submitChatSettings', 'closeChatSettings'} else ('module-workflow' if name in frame_ui else None)),
                     'preconditions': condition,
                     'localVerification': 'available in test_same_layer_models_browser.mjs' if name in MODEL_ACTIONS else ('available in test_same_layer_browser.mjs' if name == 'sendMessage' else ('available in test_same_layer_actions_browser.mjs, test_same_layer_actions.mjs and test_same_layer_dialogue_browser.mjs' if name in builtin else 'NOT RUN')),
                     'realMmd': 'NOT RUN'})
    return {'source': 'https://github.com/Godcount10/mmd-hud-iframe', 'commit': revision,
            'definitions': len(rows), 'upstreamImplemented': len(registered), 'builtin': len(builtin), 'actions': rows}


def markdown(data):
    source = data['source'] + '/tree/' + data['commit']
    lines = ['# 原生能力清单', '', f"来源：[mmd-hud-iframe 固定提交 {data['commit'][:8]}]({source})。",
             '', f"共 {data['definitions']} 项动作定义，上游实现 {data['upstreamImplemented']} 项；本基座内置 {data['builtin']} 项功能接口；现成对话页已提供这些动作的入口与操作流程。",
             '', '“已实现”指源码中有处理器，不等于所有页面状态均可调用，也不等于通过真实 MMD 验证。背景、自定义指令和教程为原生跳转入口，对话设置只能读取/提交/关闭。仅定义动作不可只加 UI 按钮就声称支持。',
             '', '本表的本地测试入口不代表本次已执行；执行结果见具体发布的验证报告。所有真实 MMD 项当前均为 NOT RUN。功能调用详见 [原生动作模块](mmd-action-modules.md)，模型 UI 详见 [模型制作模块](mmd-model-controls.md)。',
             '', '| 动作 | 分组 | 上游实现 | 基座/界面 | 前置条件 |', '|---|---|---|---|---|']
    for row in data['actions']:
        upstream = '有' if row['upstreamImplemented'] else '**仅定义**'
        builtin = ('内置 / 示例 UI' if row['frameUI'] else '内置 / 作者自绘 UI') if row['builtin'] else '未实现'
        lines.append(f"| `{row['action']}` | {row['group']} | {upstream} | {builtin} | {row['preconditions']} |")
    lines += ['', '## 维护', '', '`mmd-native-capabilities.json` 保存动作参数、源码行与证据状态。用 `scripts/audit_native_capabilities.py --upstream 已下载仓库 --out 输出目录` 重新生成，然后核对新增动作与实际内置模块。不要把解析脚本当 TypeScript 编译器，遇到上游定义形态变化须复核。',
              '', '第三方代码不随该清单分发。默认基座自动启动自己的原生 DOM 适配器；外部 NativeBridge 的能力以实例声明、已注册处理器与当前状态为准。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = inventory(args.upstream)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in [('mmd-native-capabilities.json', json.dumps(data, ensure_ascii=False, indent=2)),
                       ('mmd-native-capabilities.md', markdown(data))]:
        (args.out / name).write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in data.items() if k != 'actions'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
