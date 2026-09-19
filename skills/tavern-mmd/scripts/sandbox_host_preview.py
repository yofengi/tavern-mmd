"""Outer-document host fixtures. No platform settings or save operations run."""
import html
import re
from html.parser import HTMLParser
from sandbox_host_css import extract_host_css, load_host_contract

ALIASES = {'model': 'model-setting', 'conv': 'style', 'role': 'persona',
           'share': 'share-role', 'conversation': 'conversations',
           'assist-alert': 'assistant-intro', 'model-switch': 'models',
           'conv-intro': 'style', 'summary-intro': 'summary-confirm'}

SUMMARY_BODY = '''<div class="summary-top"><strong class="summary-top-title">剧情总结 / 记忆</strong></div>
<div class="summary-body"><div class="summary-master-bar"><span>启用记忆</span><button class="summary-tgl on" data-host-toggle>开</button></div>
<div class="summary-section"><div class="summary-label">当前总结正文</div><div class="summary-card"><div class="summary-content-shell"><div class="summary-content-box">本地预览示例：旅人在旧港遇见一位守灯人，约定天亮后前往山城。这里仅验证长内容、滚动和编辑层布局。</div></div><div class="summary-content-actions"><button class="summary-btn" data-summary-open="edit">编辑正文</button><button class="summary-btn secondary" disabled>恢复（禁用态）</button></div></div></div>
<div class="summary-section"><div class="summary-label">容量档位 · 示例</div><div class="summary-card summary-tier-row"><button class="summary-tier selected" data-host-select>当前档位</button><button class="summary-tier" data-host-select>另一档位</button></div></div>
<div class="summary-section"><div class="summary-label">模型与提示词 · 示例</div><div class="summary-card"><button class="summary-preset-item selected" data-host-select>选中态</button><button class="summary-preset-item" data-host-select>普通态</button></div></div>
<div class="summary-section"><div class="summary-label">记忆锚点</div><button class="summary-anchor-empty" data-summary-open="anchor">添加锚点</button></div>
<button data-host-open2="summary-confirm">查看树外确认层</button></div>
<div class="summary-footer bottom"><span class="summary-cost-note">仅本地布局预览，不保存平台设置</span><button class="summary-save-btn" data-host-demo-save>检查保存区</button></div>
<div class="summary-overlay summary-ov-edit" hidden><div class="summary-edit-header"><button data-summary-back>返回</button><strong>编辑正文</strong></div><div class="summary-ov-body"><textarea class="summary-ov-textarea" aria-label="示例总结正文">本地编辑示例，不向平台写入。</textarea></div></div>
<div class="summary-overlay summary-ov-anchor" hidden><div class="summary-edit-header"><button data-summary-back>返回</button><strong>添加锚点</strong></div><div class="summary-ov-body"><textarea class="summary-oa-input" aria-label="示例锚点" placeholder="本地锚点示例"></textarea></div></div>'''

# Historical 2026-09-06 content fixtures; ph-* are preview classes, not stable hooks.
HOST_FIXTURE_CSS = r'''.pano-host-popup[data-host-popup="model"],
.pano-host-popup[data-host-popup="model-switch"],
.pano-host-popup[data-host-popup="conversation"],
.pano-host-popup[data-host-popup="share"],
.pano-host-popup[data-host-popup="assist-alert"]{z-index:9000}
.pano-host-popup[data-host-popup="summary"]{z-index:1000000000}
.pano-host-popup[data-host-popup="message-edit"]{z-index:9999;top:0}
.pano-host-popup[data-host-popup="message-edit"][data-open="on"]{display:flex;
  align-items:stretch;justify-content:center}
.pano-host-popup[data-host-popup="message-edit"] .pano-host-mask{background:rgba(0,0,0,.7)}
.pano-host-popup[data-host-popup="message-edit"] .pano-host-sheet{width:100%;
  border-radius:0;display:flex;flex-direction:column}
.pano-host-popup .ph-edit-surface{flex:1;min-height:140px;white-space:pre-wrap}
.pano-host-popup .ph-mi{background:#2c2e32;border-radius:8px;padding:9px 10px;
  margin-bottom:7px;border:1px solid transparent}
.pano-host-popup .ph-mi.is-sel{border-color:#ff6d97}
.pano-host-popup .ph-mi.is-sel::before{content:'\2713';float:right;color:#ff6d97;
  font-size:12px;margin-left:6px}
.pano-host-popup .ph-mi-top{display:flex;align-items:center;gap:6px}
.pano-host-popup .ph-newbadge{font-style:normal;font-size:9px;background:#ff6d97;
  color:#fff;border-radius:3px;padding:1px 5px}
.pano-host-popup .ph-mi-bot{display:flex;align-items:center;gap:10px;margin-top:6px;
  flex-wrap:wrap}
.pano-host-popup .ph-badge{font-size:9px;background:#33353b;color:#c5c5c5;
  border-radius:10px;padding:2px 7px}
.pano-host-popup[data-host-popup="assist-alert"][data-open="on"]{display:flex;
  align-items:center;justify-content:center;top:0}
.pano-host-popup[data-host-popup="assist-alert"] .pano-host-sheet{width:260px;
  border-radius:10px;background:#1e1f24}
.pano-host-popup[data-host-popup="conv"] .pano-host-sheet,
.pano-host-popup[data-host-popup="role"] .pano-host-sheet{border-radius:0}
.pano-host-popup .ph-body{margin-top:10px;font-size:11px;color:#e6e6e6;
  max-height:60vh;overflow:auto}
.pano-host-popup .ph-body b{color:#fff;font-size:12px}
.pano-host-popup .ph-desc,.pano-host-popup .ph-hint{display:block;color:#8d949d;font-size:10px}
.pano-host-popup .ph-hint{display:inline;margin-left:6px}
.pano-host-popup .ph-bar{display:flex;justify-content:space-between;align-items:center;
  padding:6px 0 10px;border-bottom:1px solid #333;margin-bottom:8px}
.pano-host-popup .ph-ok{color:#ff6d97;font-weight:600}
.pano-host-popup .ph-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.pano-host-popup .ph-model{color:#fff}
.pano-host-popup .ph-pill{background:#3a2d33;color:#ff6d97;border-radius:11px;padding:2px 9px;font-weight:600}
.pano-host-popup .ph-pill i{font-style:normal;font-size:9px;opacity:.75}
.pano-host-popup .ph-card{background:#2c2e32;border-radius:8px;padding:9px 10px;margin-bottom:8px}
.pano-host-popup .ph-card-head{display:flex;justify-content:space-between;align-items:center}
.pano-host-popup .ph-caret{color:#8d949d}
.pano-host-popup .ph-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}
.pano-host-popup .ph-chips.ph-right{justify-content:flex-end}
.pano-host-popup .ph-chip{position:relative;background:#33353b;border-radius:6px;
  padding:5px 10px;font-size:10px;color:#c5c5c5}
.pano-host-popup .ph-chip.is-sel{background:#ff6d97;color:#fff}
.pano-host-popup .ph-chip.is-off{opacity:.45}
.pano-host-popup .ph-chip i{display:block;font-style:normal;font-size:9px;opacity:.8}
.pano-host-popup .ph-intro,.pano-host-popup .ph-help{display:inline-flex;align-items:center;
  justify-content:center;width:13px;height:13px;margin-left:5px;border-radius:50%;
  border:1px solid currentColor;font-size:9px;font-style:normal;cursor:pointer;vertical-align:middle}
.pano-host-popup .ph-sw-row{display:flex;justify-content:space-between;align-items:center}
.pano-host-popup .ph-sw{flex:0 0 auto;width:34px;height:18px;border-radius:9px;background:#4a4d55;position:relative}
.pano-host-popup .ph-sw.is-sel{background:#ff6d97}
.pano-host-popup .ph-sw::after{content:'';position:absolute;top:2px;left:2px;width:14px;height:14px;
  border-radius:50%;background:#fff}
.pano-host-popup .ph-sw.is-sel::after{left:auto;right:2px}
.pano-host-popup .ph-label{display:flex;justify-content:space-between;margin:10px 0 6px;color:#fff;font-size:11px}
.pano-host-popup .ph-textbox{background:#1e1f24;border-radius:6px;padding:9px;min-height:34px;color:#8d949d}
.pano-host-popup .ph-input{background:#1e1f24;border-radius:6px;padding:9px;margin-top:6px;color:#8d949d;
  display:flex;justify-content:space-between}
.pano-host-popup .ph-pi{display:flex;align-items:center;gap:8px;padding:8px 9px;border-radius:6px;
  margin-bottom:5px;background:#33353b}
.pano-host-popup .ph-pi>span:first-child{flex:1;color:#fff}
.pano-host-popup .ph-pi.is-sel{background:rgba(255,109,151,.16);border:1px solid #ff6d97}
.pano-host-popup .ph-radio{flex:0 0 auto;width:13px;height:13px;border-radius:50%;border:1px solid #8d949d}
.pano-host-popup .ph-pi.is-sel .ph-radio{border-color:#ff6d97;background:#ff6d97}
.pano-host-popup .ph-dashed{border:1px dashed #4a4d55;border-radius:8px;padding:12px;
  text-align:center;color:#8d949d}
.pano-host-popup .ph-cost{margin:10px 0;text-align:center;color:#c5c5c5;font-size:10px}
.pano-host-popup .ph-btn{margin-top:10px;background:#ff6d97;color:#fff;border-radius:23px;
  padding:11px;text-align:center;font-weight:600;font-size:12px}
.pano-host-popup .ph-item{display:flex;align-items:center;gap:9px;padding:7px 0}
.pano-host-popup .ph-avatar{flex:0 0 auto;width:34px;height:34px;border-radius:50%;background:#4a4d55}
.pano-host-popup .ph-item>span:nth-child(2){flex:1}
.pano-host-popup .ph-cur{color:#ff6d97;font-size:10px}
.pano-host-popup .ph-radios{display:flex;gap:6px;justify-content:space-between}
.pano-host-popup .ph-rd{font-size:10px;color:#c5c5c5;display:flex;align-items:center;gap:4px}
.pano-host-popup .ph-rd::before{content:'';width:12px;height:12px;border-radius:50%;border:1px solid #8d949d}
.pano-host-popup .ph-rd.is-sel{color:#fff}
.pano-host-popup .ph-rd.is-sel::before{border-color:#ff6d97;background:#ff6d97}
.pano-host-popup .ph-note-inline{margin:8px 0 6px;color:#d29922;font-size:10px}
.pano-host-popup .ph-center{text-align:center}
.pano-host-popup .ph-alert-title{font-size:14px;font-weight:600;color:#fff;margin-bottom:9px}
.pano-host-popup .ph-alert-text{font-size:11px;line-height:1.65;color:#e6e6e6;text-align:left}
.pano-host-popup .ph-check{display:flex;align-items:center;justify-content:center;gap:6px;
  margin:12px 0;font-size:10px;color:#c5c5c5}
.pano-host-popup .ph-check i{width:12px;height:12px;border:1px solid #8d949d;border-radius:2px}
.pano-host-popup .ph-alert-btns{display:flex;justify-content:space-around;align-items:center;
  margin-top:12px;padding-top:10px;border-top:1px solid #333;font-size:12px}
.pano-host-popup[data-host-popup="conv-intro"][data-open="on"],
.pano-host-popup[data-host-popup="summary-intro"][data-open="on"]{display:flex;
  align-items:center;justify-content:center;top:0}
.pano-host-popup[data-host-popup="conv-intro"]{z-index:10076}
.pano-host-popup[data-host-popup="conv-intro"] .pano-host-sheet{width:315px;
  border-radius:10px;background:#2c2e32;max-height:70vh;overflow:auto}
.pano-host-popup[data-host-popup="summary-intro"]{z-index:1000000001}
.pano-host-popup[data-host-popup="summary-intro"] .pano-host-sheet{width:371px;
  border-radius:10px;background:#2c2e32}'''

HOST_CSS = HOST_FIXTURE_CSS + '''.pano-host-popup{position:fixed;inset:0;z-index:10075;display:none;align-items:center;justify-content:center;font:14px/1.5 system-ui;color:#e8e8e8}
.pano-host-popup[data-open="on"]{display:flex}.pano-host-mask{position:absolute;inset:0;background:#0009}
.pano-host-sheet{position:relative;box-sizing:border-box;width:min(540px,92vw);max-height:88vh;overflow:auto;padding:20px;border:1px solid #51565f;border-radius:14px;background:#17181a;color:#e8e8e8}
.pano-host-popup button,.pano-host-popup textarea{font:inherit}.pano-host-popup button{cursor:pointer}.pano-host-popup button:disabled{opacity:.45;cursor:default}
.pano-host-tag,.pano-host-note{font-size:12px;opacity:.7}.pano-host-close{float:right}.pano-host-popup[data-host-popup="summary-confirm"],.pano-host-popup[data-host-popup="summary-intro"]{z-index:1000000001}
.pano-host-popup[data-host-popup="summary"]{z-index:1000000000}.pano-host-popup [hidden]{display:none!important}
.summary-sheet{display:flex;flex-direction:column;height:min(760px,88vh);overflow:hidden}.summary-top,.summary-footer{flex-shrink:0;padding:12px 0}.summary-body{flex:1;min-height:0;overflow:auto}.summary-section{margin:14px 0}.summary-card{border:1px solid #51565f;border-radius:8px;padding:12px}.summary-label{margin:8px 0}.summary-tier,.summary-preset-item{margin:4px;padding:8px}.summary-tier.selected,.summary-preset-item.selected{outline:2px solid #93c5fd}.summary-overlay{position:absolute;inset:0;z-index:30;background:#17181a;padding:18px;display:flex;flex-direction:column}.summary-edit-header{display:flex;gap:18px;margin-bottom:16px}.summary-ov-body{flex:1;min-height:0}.summary-ov-body textarea{box-sizing:border-box;width:100%;height:100%;resize:none}.summary-footer{display:flex;gap:12px;align-items:center;justify-content:space-between}.summary-master-bar{display:flex;justify-content:space-between}
@media(max-width:480px){.pano-host-sheet{padding:12px}.summary-footer{flex-wrap:wrap}}'''

HOST_SCRIPT = '''<script data-preview-host-controls="1">(function(){
var D=document,frame=D.querySelector('.pano-frame'),lastFocus=null;
function all(){return D.querySelectorAll('.pano-host-popup');}
function node(name){return D.querySelector('.pano-host-popup[data-host-popup="'+name+'"]');}
function closeOne(name){var el=node(name);if(!el)return false;el.setAttribute('data-open','off');if(lastFocus&&lastFocus.focus)lastFocus.focus();return true;}
function closeAll(){all().forEach(function(el){el.setAttribute('data-open','off');});if(lastFocus&&lastFocus.focus)lastFocus.focus();}
function open2(name){var el=node(name);if(!el)return false;lastFocus=D.activeElement;el.setAttribute('data-open','on');var b=el.querySelector('button,textarea');if(b)b.focus();return true;}
function open(name){closeAll();return open2(name);}
window.__sbxHostPreview={open:open,open2:open2,closeOne:closeOne,closeAll:closeAll};
D.querySelectorAll('[data-host-close]').forEach(function(b){b.onclick=function(){closeOne(b.getAttribute('data-host-close'));};});
D.querySelectorAll('[data-host-open2]').forEach(function(b){b.onclick=function(){open2(b.getAttribute('data-host-open2'));};});
D.querySelectorAll('[data-summary-open]').forEach(function(b){b.onclick=function(){var root=b.closest('[data-host="summary"]');root.querySelector('.summary-ov-'+b.getAttribute('data-summary-open')).hidden=false;};});
D.querySelectorAll('[data-summary-back]').forEach(function(b){b.onclick=function(){b.closest('.summary-overlay').hidden=true;};});
D.querySelectorAll('[data-host-select]').forEach(function(b){b.onclick=function(){b.parentElement.querySelectorAll('[data-host-select]').forEach(function(x){x.classList.remove('selected');});b.classList.add('selected');};});
D.querySelectorAll('[data-host-toggle]').forEach(function(b){b.onclick=function(){b.classList.toggle('on');b.textContent=b.classList.contains('on')?'开':'关';};});
D.querySelectorAll('[data-host-demo-save]').forEach(function(b){b.onclick=function(){b.textContent='本地检查完成（未保存）';};});
D.addEventListener('keydown',function(e){if(e.key==='Escape')closeAll();});
window.addEventListener('message',function(e){if(!frame||e.source!==frame.contentWindow)return;var m=e.data;if(!m||m.type!=='mmd-preview-host')return;if(m.action==='open')open(m.name);else if(m.action==='open2')open2(m.name);else if(m.action==='close')closeAll();});
})();</script>'''


def split_assets(assets):
    """Hoisted scripts remain in-frame; only static styles are considered."""
    host, diagnostics = [], []
    class Splitter(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.local, self.style = [], None
            self.style_tag, self.style_attrs = '', {}

        def handle_starttag(self, tag, attrs):
            if tag == 'style':
                self.style = []
                self.style_tag, self.style_attrs = self.get_starttag_text(), dict(attrs)
            else:
                self.local.append(self.get_starttag_text())

        def handle_endtag(self, tag):
            if tag == 'style' and self.style is not None:
                result = extract_host_css(''.join(self.style))
                rules = result['rules']
                media = self.style_attrs.get('media', '')
                if media and rules:
                    wrapped = extract_host_css('@media ' + media + '{' + '\n'.join(rules) + '}')
                    rules = wrapped['rules']
                    diagnostics.extend(wrapped['diagnostics'])
                host.extend(rules)
                diagnostics.extend(result['diagnostics'])
                self.local.append(self.style_tag + result['sandbox_css'] + '</style>')
                self.style = None
            else:
                self.local.append('</' + tag + '>')

        def handle_data(self, data):
            (self.style if self.style is not None else self.local).append(data)

        def handle_comment(self, data):
            self.handle_data('<!--' + data + '-->')

        def handle_entityref(self, name):
            self.handle_data('&' + name + ';')

        def handle_charref(self, name):
            self.handle_data('&#' + name + ';')

    parser = Splitter()
    parser.feed(assets)
    parser.close()
    return ''.join(parser.local), '\n'.join(host), diagnostics


def popup(name, title, note, body=''):
    root = ALIASES.get(name, name)
    root_attr = ' data-host="%s"' % root if root in load_host_contract()['roots'] else ''
    cls = 'pano-host-sheet' + (' summary-sheet theme-dark' if root == 'summary' else '')
    if root == 'summary':
        body = SUMMARY_BODY
    return ('<div class="pano-host-popup" data-host-popup="%s" data-open="off">'
            '<div class="pano-host-mask" data-host-close="%s"></div>'
            '<div class="%s"%s><button class="pano-host-close" type="button" data-host-close="%s">×</button>'
            '<span class="pano-host-tag">宿主 CSS 预览 · 静态转发</span>'
            '<div class="pano-host-title">%s</div><div class="pano-host-note">%s</div>%s</div></div>') % (
                name, name, cls, root_attr, name, html.escape(title), note, body)


def complete_popups(legacy_markup):
    roots = load_host_contract()['roots']
    present = set(re.findall(r'data-host="([a-z-]+)"', legacy_markup))
    extra = ''.join(popup(name, title, '仅根名与范围有文档；内部结构待验证。此占位不代表业务表单。')
                    for name, title in roots.items() if name not in present or name == 'summary-confirm')
    return legacy_markup + extra


def root_tools():
    return ('<span class="preview-tools-label">宿主开放根（内部结构分级模拟）</span>' +
            ''.join('<button class="preview-tool" type="button" onclick="window.__sbxHostPreview.open(\'%s\')">%s</button>' %
                    (next((alias for alias, root in ALIASES.items() if root == name and not alias.endswith('-intro')), name), html.escape(title))
                    for name, title in load_host_contract()['roots'].items()))
