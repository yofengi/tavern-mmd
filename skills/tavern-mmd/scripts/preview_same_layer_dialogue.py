#!/usr/bin/env python3
"""Build a local interactive DOM fixture, never an importable MMD card.

All native actions/models below operate on original local test fixtures. No MMD
account, remote service, real generation or clipboard success is implied.
"""
import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from build_same_layer import ASSETS, build


def preview(out, source=ASSETS):
    target = out / 'dialogue-preview.html'
    if target.exists():
        raise FileExistsError('预览已存在，请使用新的输出目录')
    fixtures = Path(__file__).resolve().parent / 'test-fixtures'
    with tempfile.TemporaryDirectory(prefix='mmd-dialogue-preview-') as temp:
        temp = Path(temp)
        src = temp / 'source'
        shutil.copytree(source, src)
        frame = src / 'frame.js'
        text = frame.read_text(encoding='utf-8').replace("snapshot.localPreview ? '本地演示' : 'MMD'", "'本地交互演示'")
        text = text.replace("snapshot.localPreview ? '本地模拟已连接，所有模型回复均为模拟内容。' : '已连接。原生功能可从顶部返回。'", "'本地模拟 MMD：菜单、模型与回复均为演示数据。刷新页面会重置对话。'")
        frame.write_text(text, encoding='utf-8')
        build(temp / 'built', {'appId': 'dialogue-local-fixture', 'buildId': 'dialogue-local-preview',
                              'title': '本地交互演示 · 模拟 MMD', 'engine': True, 'models': True}, src)
        package = json.loads((temp / 'built/same-layer-mmd.json').read_text(encoding='utf-8'))
        runtime = package['statusbar']
        for rule in package['regex_scripts']:
            runtime = re.sub(rule['findRegex'][1:-2], lambda _: rule['replaceString'], runtime)
        actions = (fixtures / 'same-layer-actions.html').read_text(encoding='utf-8')
        models = (fixtures / 'same-layer-models.html').read_text(encoding='utf-8')
        model_html = models[models.index('<button class="mind-type">'):models.index('<!--RUNTIME-->')]
        model_html = model_html.replace('window.fixture =', 'window.modelFixture =')
        # Scope model controls to their own nodes when both original fixtures share a page.
        model_html = model_html.replace("q('.u-popup__content__close')", "q('#model-popup .u-popup__content__close')")
        model_html = model_html.replace("q('.bottom > .btn')", "q('.model-setting-scope .bottom > .btn')")
        setup = '''<style>[hidden]{display:none!important}</style><script>
const localScope=window.modelFixture.scope;localScope.accountKey='dialogue-local-fixture';
const originalMessages=fixture.messages;
fixture.messages=function(rows){if(rows?.[0]?.[1]?.startsWith('选择了故事 ')||rows?.[0]?.[1]==='新故事')localScope.conversationKey=crypto.randomUUID();originalMessages(rows);};
fixture.messages([['assistant','雾灯一盏盏亮起来，远处的渡船刚刚靠岸。守灯人将地图推到你面前。\\n\\n“今晚想先去码头看看，还是留下来听一段旧事？”'],['user','先告诉我，这座港口藏着什么？'],['assistant','“潮水退下时，旧码头会露出一条小路。”\\n\\n他指向地图边缘的铜色记号，轻声补充：“带好灯。也记得给自己留一点返程的力气。”']]);
document.querySelector('.chat-send-proxy').onclick=()=>{const input=document.querySelector('#chat-input-scope textarea');const text=input.value;if(!text.trim())return;fixture.record('sendMessage');const rows=[...document.querySelectorAll('#msglistview .item')].map(e=>[e.classList.contains('Ai')?'assistant':'user',e.querySelector('.content').textContent]);fixture.messages([...rows,['user',text],['assistant','【本地模拟】守灯人点了点头。远处传来潮声，故事等待你的下一个选择。']]);input.value='';};
</script>'''
        html = actions.replace('<title>Original old-MMD action fixture</title>', '<title>同层卡 · 本地交互演示</title>')
        html = html.replace('<!--RUNTIME-->', model_html + setup + runtime)
    out.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding='utf-8', newline='\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ASSETS)
    args = parser.parse_args()
    print(preview(args.out, args.source))
