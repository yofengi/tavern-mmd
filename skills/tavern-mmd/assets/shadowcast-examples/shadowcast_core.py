#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影渲法（ShadowCast 2.0）富 UI 共享核心 shadowcast_core.py

由雷达法资产转换而来的可复用引擎。build_rpg.py / build_manor.py 等场景脚本
只提供 config（FIELDS / TRIGGER / CSS / TITLE / SCRIPT_NAME / OUT），引擎 JS 与
协议/JSON 构建逻辑全部共享——单一引擎源，改 bug 只动这里，所有场景同步受益。

支持的字段 type：
  section  分组标题（仅布局）
  text     标签:值
  path     连字符分层 → 面包屑 chips + › 箭头
  time     高亮时段词（清晨/上午/中午/下午/黄昏/夜间/深夜）
  bar      资源条 当前/最大；值可带 |成因 → hover tooltip
  level    名|经验/阈值 → 名 + (经验/阈值) + XP 条
  stats    属性:值[,...]（属性:值:成因 → tooltip）→ chips 网格
  kvlist   槽位:名[|说明][,...] → 槽位：名（名带 hover 说明）
  lines    N.项|N.项|... → 编号记录列表（事件记录等）
  summary  N/3|内容 或纯文本 → 斜体摘要
  turn     数字 → 区块标题右上角角标
  bag      multi：分类|物品/物品/... → 可切页背包（◀▶ + tooltip）
  enemy    multi：名|HP当/最|属性k:v/k:v|状态 → 敌人卡（红边+血条+属性格）
  option   multi：简介|内容 → 可点击按钮，写回 .uni-textarea-textarea（♥→ero样式）

铁律（生成器 guard 自动拦）：
  1. 引擎 JS 体内禁裸双引号（会提前闭合 onerror=""，面板静默不渲染）→ 全单引号 + js_literal
  2. 禁字面 [键=值]（本方案单块捕获已不扫整条气泡，风险消除，但仍不写）
  3. findRegex 带 /.../ 斜杠
注：onerror 引号内裸 < > => 无害（HTML 属性不解析标签），比较/箭头函数可正常用。
"""
import sys
import json
import re
import argparse
import os

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def js_literal(val):
    """Python → JS 字面量，字符串单引号（铁律1：禁 json.dumps 的双引号）。"""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return repr(val)
    if isinstance(val, str):
        s = val.replace("\\", "\\\\").replace("'", "\\'")
        s = s.replace("\n", "\\n").replace("\r", "")
        return "'" + s + "'"
    if isinstance(val, list):
        return "[" + ",".join(js_literal(v) for v in val) + "]"
    if isinstance(val, dict):
        return "{" + ",".join(
            js_literal(str(k)) + ":" + js_literal(v) for k, v in val.items()) + "}"
    raise TypeError("不支持的类型: %r" % type(val))


def data_fields(FIELDS):
    return [f for f in FIELDS if f.get("type") != "section"]


def sample_fields(FIELDS):
    return [f for f in data_fields(FIELDS) if not f.get("example_off", False)]


def build_engine_js(FIELDS, TRIGGER, CSS, TITLE):
    cfg = []
    for f in FIELDS:
        if f.get("type") == "section":
            cfg.append({"t": "section", "label": f["label"]})
        else:
            cfg.append({
                "k": f["key"], "label": f["label"], "t": f["type"],
                "multi": f.get("multi", False),
                "inherit": (not f.get("volatile", False)) and f.get("inherit", True),
            })
    cfg_literal = js_literal(cfg)
    css_literal = js_literal(CSS)
    title_literal = js_literal(TITLE)

    alias_map = {}
    for f in data_fields(FIELDS):
        std = f["key"]
        alias_map[std.lower()] = std
        for a in f.get("aliases", []):
            alias_map[a.lower()] = std
    alias_literal = js_literal(alias_map)

    multi_map = {f["key"]: True for f in data_fields(FIELDS) if f.get("multi")}
    multi_literal = js_literal(multi_map)

    T = TRIGGER
    engine = """(function(img){
var box=img.closest('.""" + T + """-host');
if(!box)return;
var us=String.fromCharCode(95);
var VER='sc2r';
var CFG=""" + cfg_literal + """;
var CSS=""" + css_literal + """;
var ALIAS=""" + alias_literal + """;
var MULTI=""" + multi_literal + """;
var TITLE=""" + title_literal + """;
var trim=function(s){return (s||'').replace(/^\\s+|\\s+$/g,'');};
var normKey=function(k){var n=ALIAS[k.toLowerCase()];return n?n:k;};
var read=function(host){
var d=host.querySelector('.""" + T + """-data');
var o={},mu={};
if(!d)return {o:o,mu:mu};
d.textContent.split(';').forEach(function(pair){
var i=pair.indexOf('=');
if(i===-1)return;
var k=normKey(trim(pair.slice(0,i)));
var v=trim(pair.slice(i+1));
if(!k)return;
if(MULTI[k]){if(!mu[k])mu[k]=[];if(v!=='')mu[k].push(v);}
else o[k]=v;
});
return {o:o,mu:mu};
};
var rd=read(box);
var cur=rd.o,mu=rd.mu;
var hosts=[].slice.call(document.querySelectorAll('.""" + T + """-host'));
var idx=hosts.indexOf(box);
CFG.forEach(function(f){
if(f.t==='section'||f.multi||!f.inherit)return;
if(cur[f.k]===undefined||cur[f.k]===''){
var prev=hosts.slice(0,idx).reverse();
prev.some(function(h){
var p=read(h).o;
if(p[f.k]!==undefined&&p[f.k]!==''){cur[f.k]=p[f.k];return true;}
return false;
});
}
});
var ce=function(tag,cl){var e=document.createElement(tag);if(cl)e.className=cl;return e;};
var tx=function(t){return document.createTextNode(t);};
var P=function(s){return '""" + T + """-'+s;};
var mkTip=function(holder,word,tip){
var sp=ce('span',P('tt'));
var w=ce('span',P('help'));w.textContent=word;
sp.appendChild(w);
var b=ce('span',P('box'));b.textContent=tip;
sp.appendChild(b);
holder.appendChild(sp);
};
var mkRow=function(lbl){var r=ce('div',P('row'));var l=ce('span',P('lbl'));l.textContent=lbl;r.appendChild(l);return r;};
var renderBar=function(f,v,panel){
var parts=v.split('|');var num=trim(parts[0]);var tip=parts[1]?trim(parts[1]):'';
var r=mkRow(f.label);
var w=ce('div',P('bar-wrap'));
var top=ce('div',P('bar-top'));
var nm=ce('span');
if(tip){mkTip(nm,num,tip);}else{nm.textContent=num;}
top.appendChild(nm);
w.appendChild(top);
var bar=ce('div',P('bar'));
var cls=f.k==='hp'?P('hp'):f.k==='mp'?P('mp'):f.k==='sp'?P('sp'):P('ar');
var fl=ce('div',P('fill')+' '+cls);
var m=num.match(/(-?\\d+)\\s*\\/\\s*(\\d+)/);
if(m&&parseInt(m[2],10)>0){fl.style.width=Math.max(0,Math.min(100,parseInt(m[1],10)/parseInt(m[2],10)*100))+'%';}
else{fl.style.width='100%';}
bar.appendChild(fl);w.appendChild(bar);
r.appendChild(w);panel.appendChild(r);
};
var renderLevel=function(f,v,panel){
var parts=v.split('|');var nm=trim(parts[0]);var xp=parts[1]?trim(parts[1]):'';
var r=mkRow(f.label);
var w=ce('div',P('bar-wrap'));
var top=ce('div',P('bar-top'));
var ns=ce('span');ns.textContent=nm;top.appendChild(ns);
if(xp){var xs=ce('span');xs.style.color='#a9a9a9';xs.textContent=xp;top.appendChild(xs);}
w.appendChild(top);
var m=xp.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
if(m&&parseInt(m[2],10)>0){
var bar=ce('div',P('bar'));var fl=ce('div',P('fill')+' '+P('xp'));
fl.style.width=Math.max(0,Math.min(100,parseInt(m[1],10)/parseInt(m[2],10)*100))+'%';
bar.appendChild(fl);w.appendChild(bar);
}
r.appendChild(w);panel.appendChild(r);
};
var renderPath=function(f,v,panel){
var r=mkRow(f.label);var box2=ce('div');box2.style.flex='1';
var segs=v.split('-');
segs.forEach(function(s,i){
var c=ce('span',P('crumb'));c.textContent=trim(s);box2.appendChild(c);
if(i<segs.length-1){var a=ce('span',P('arr'));a.textContent='\\u203A';box2.appendChild(a);}
});
r.appendChild(box2);panel.appendChild(r);
};
var renderTime=function(f,v,panel){
var r=mkRow(f.label);var s=ce('span',P('val'));
var tod=['清晨','上午','中午','下午','黄昏','夜间','深夜'];var hit='';
tod.some(function(t){if(v.indexOf(t)!==-1){hit=t;return true;}return false;});
if(hit){var ps=v.split(hit);s.appendChild(tx(ps[0]));var h=ce('span',P('time'));h.textContent=hit;s.appendChild(h);s.appendChild(tx(ps[1]||''));}
else{s.textContent=v;}
r.appendChild(s);panel.appendChild(r);
};
var renderStats=function(f,v,panel){
var r=mkRow(f.label);var box2=ce('div',P('stats'));
v.split(',').forEach(function(it){
it=trim(it);if(!it)return;
var ps=it.split(':');var k=trim(ps[0]);var val=ps[1]?trim(ps[1]):'';var tip=ps[2]?trim(ps[2]):'';
var chip=ce('span',P('stat'));
if(tip){chip.appendChild(tx(k+':'));mkTip(chip,val,tip);}
else{chip.textContent=k+':'+val;}
box2.appendChild(chip);
});
r.appendChild(box2);panel.appendChild(r);
};
var renderKv=function(f,v,panel){
var r=mkRow(f.label);var box2=ce('div',P('kv'));
v.split(',').forEach(function(it){
it=trim(it);if(!it)return;
var ci=it.indexOf(':');if(ci===-1){var d0=ce('div',P('kvi'));d0.textContent=it;box2.appendChild(d0);return;}
var slot=trim(it.slice(0,ci));var rest=it.slice(ci+1);
var np=rest.split('|');var nm=trim(np[0]);var tip=np[1]?trim(np[1]):'';
var d=ce('div',P('kvi'));
var ks=ce('span',P('kk'));ks.textContent=slot+'：';d.appendChild(ks);
if(tip){mkTip(d,nm,tip);}else{var vs=ce('span',P('kn'));vs.textContent=nm;d.appendChild(vs);}
box2.appendChild(d);
});
r.appendChild(box2);panel.appendChild(r);
};
var renderLines=function(f,v,panel){
var r=mkRow(f.label);var box2=ce('div',P('kv'));
v.split('|').forEach(function(it){
it=trim(it);if(!it)return;
var d=ce('div',P('kvi'));d.textContent=it;box2.appendChild(d);
});
r.appendChild(box2);panel.appendChild(r);
};
var renderBag=function(f,arr,panel){
if(!arr||!arr.length)return;
var cats=arr.map(function(e){var p=e.split('|');return {name:trim(p[0]),items:trim(p[1]||'')};});
var h=ce('div',P('bag-h'));
var lb=ce('button',P('nav'));lb.textContent='\\u25C0';
var tabs=ce('div',P('tabs'));
var rb=ce('button',P('nav'));rb.textContent='\\u25B6';
h.appendChild(lb);h.appendChild(tabs);h.appendChild(rb);
var cont=ce('div',P('bag-c'));
var curIdx={i:0};
var btns=[];
var show=function(n){
while(cont.firstChild)cont.removeChild(cont.firstChild);
btns.forEach(function(b,bi){if(bi===n)b.className=P('tab')+' on';else b.className=P('tab');});
curIdx.i=n;
var items=cats[n].items.split(/[\\/、]+/);
items.forEach(function(it){it=trim(it);if(!it)return;var d=ce('div',P('bag-i'));d.textContent='\\u00B7 '+it;cont.appendChild(d);});
};
cats.forEach(function(c,ci){
var b=ce('button',P('tab'));b.textContent=c.name;
b.onclick=function(ev){ev.stopPropagation();show(ci);};
tabs.appendChild(b);btns.push(b);
});
lb.onclick=function(ev){ev.stopPropagation();var n=curIdx.i-1;if(n<0)n=cats.length-1;show(n);};
rb.onclick=function(ev){ev.stopPropagation();var n=curIdx.i+1;if(n>=cats.length)n=0;show(n);};
panel.appendChild(h);panel.appendChild(cont);
if(cats.length)show(0);
};
var renderEnemy=function(f,arr,panel){
if(!arr||!arr.length)return;
arr.forEach(function(e){
var p=e.split('|');
var card=ce('div',P('enemy'));
var nm=ce('div',P('en'));nm.textContent=trim(p[0]||'未知敌人');card.appendChild(nm);
var hp=trim(p[1]||'');
if(hp){
var hl=ce('div');hl.style.fontSize='12px';hl.textContent='HP '+hp;card.appendChild(hl);
var bg=ce('div',P('ehp'));var fl=ce('div',P('ehp-f'));
var m=hp.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
if(m&&parseInt(m[2],10)>0)fl.style.width=Math.max(0,Math.min(100,parseInt(m[1],10)/parseInt(m[2],10)*100))+'%';
bg.appendChild(fl);card.appendChild(bg);
}
var attrs=trim(p[2]||'');
if(attrs){var g=ce('div',P('eg'));attrs.split(/[\\/]+/).forEach(function(a){a=trim(a);if(!a)return;var d=ce('div');d.textContent=a;g.appendChild(d);});card.appendChild(g);}
var st=trim(p[3]||'');
if(st){var s=ce('div',P('sum'));s.textContent='状态：'+st;card.appendChild(s);}
panel.appendChild(card);
});
};
var renderSummary=function(f,v,panel){
var r=mkRow(f.label);var s=ce('span',P('val'));
var p=v.split('|');s.textContent=p.length>1?(trim(p[0])+'：'+trim(p[1])):v;
r.appendChild(s);panel.appendChild(r);
};
var renderText=function(f,v,panel){
var r=mkRow(f.label);var s=ce('span',P('val'));s.textContent=v;r.appendChild(s);panel.appendChild(r);
};
var renderTurn=function(f,v,panel,secTitle){
if(secTitle){var b=ce('span',P('badge'));b.textContent=f.label+'：'+v;secTitle.appendChild(b);}
};
var renderOpt=function(f,arr,panel){
if(!arr||!arr.length)return;
arr.forEach(function(e){
var p=e.split('|');var brief=trim(p[0]||'选项');var content=trim(p[1]||brief);
var btn=ce('div',P('opt'));
if(/[\\u2665\\u2764\\u{1F495}-\\u{1F49E}]/u.test(brief)){btn.className=P('opt')+' '+P('ero');}
btn.textContent=brief;
btn.setAttribute('data-c',content);
btn.onclick=function(ev){
ev.stopPropagation();
var t=ev.currentTarget.getAttribute('data-c');
var a=document.querySelector('.uni-textarea-textarea');
if(a){a.value=t;a.dispatchEvent(new Event('input',{bubbles:true}));}
};
panel.appendChild(btn);
});
};
var buildPanel=function(){
var root=ce('div',P('panel'));
var title=ce('div',P('title'));title.textContent=TITLE;root.appendChild(title);
var sec=null,secTitle=null;
CFG.forEach(function(f){
if(f.t==='section'){
sec=ce('div',P('sec'));
secTitle=ce('div',P('sec-t'));secTitle.textContent=f.label;sec.appendChild(secTitle);
root.appendChild(sec);
return;
}
if(!sec){sec=ce('div',P('sec'));root.appendChild(sec);secTitle=null;}
if(f.multi){
var arr=mu[f.k];
if(f.t==='bag')renderBag(f,arr,sec);
else if(f.t==='enemy')renderEnemy(f,arr,sec);
else if(f.t==='option')renderOpt(f,arr,sec);
return;
}
var v=cur[f.k];
if(f.t==='turn'){if(v!==undefined&&v!=='')renderTurn(f,v,sec,secTitle);return;}
if(v===undefined||v==='')return;
if(f.t==='bar')renderBar(f,v,sec);
else if(f.t==='level')renderLevel(f,v,sec);
else if(f.t==='path')renderPath(f,v,sec);
else if(f.t==='time')renderTime(f,v,sec);
else if(f.t==='stats')renderStats(f,v,sec);
else if(f.t==='kvlist')renderKv(f,v,sec);
else if(f.t==='lines')renderLines(f,v,sec);
else if(f.t==='summary')renderSummary(f,v,sec);
else renderText(f,v,sec);
});
return root;
};
var shadowOf=function(b){
try{return b.shadowRoot||(b.attachShadow?b.attachShadow({mode:'open'}):null);}
catch(e){return null;}
};
var clearNode=function(n){while(n&&n.firstChild)n.removeChild(n.firstChild);};
var applyCss=function(sr){
if(sr.adoptedStyleSheets!==undefined&&window.CSSStyleSheet){
try{
var key=us+'""" + T + """Sheet';
var sh=window[key];
if(!sh){sh=new CSSStyleSheet();sh.replaceSync(CSS);window[key]=sh;}
sr.adoptedStyleSheets=[sh];return;
}catch(e){}
}
var st=ce('style');st.textContent=CSS;sr.appendChild(st);
};
var styleLight=function(){
var key=us+'""" + T + """LightCss';
if(window[key])return;
var st=ce('style');st.textContent=CSS;(document.head||document.body).appendChild(st);
window[key]=1;
};
var resetPlain=function(){
var sr=box.shadowRoot;if(sr)clearNode(sr);
var old=box.querySelector('.""" + T + """-panel');
if(old&&old.parentNode)old.parentNode.removeChild(old);
box.removeAttribute('data-""" + T + """v');
};
try{
var panel=buildPanel();
var sr=shadowOf(box);
if(sr){clearNode(sr);applyCss(sr);sr.appendChild(panel);}
else{
styleLight();
var prev=box.querySelector('.""" + T + """-panel');
if(prev&&prev.parentNode)prev.parentNode.removeChild(prev);
box.appendChild(panel);
}
box.setAttribute('data-""" + T + """v',VER);
}catch(e){
window.""" + T + """LastError=e;
resetPlain();
}
})(this)"""
    return engine


def build_replace_string(FIELDS, TRIGGER, CSS, TITLE):
    engine = build_engine_js(FIELDS, TRIGGER, CSS, TITLE)
    return (
        '<div class="' + TRIGGER + '-host" onclick="event.stopPropagation()">'
        '<span class="' + TRIGGER + '-data" style="display:none">$1</span>'
        '<img src=x style="display:none" onerror="' + engine + '">'
        '</div>'
    )


def build_find_regex(TRIGGER):
    return "/<" + TRIGGER + ">([\\s\\S]*?)<\\/" + TRIGGER + ">/"


def _sample_block(FIELDS):
    return ";".join(f["key"] + "=" + f["example"] for f in sample_fields(FIELDS))


def build_beginning(FIELDS, TRIGGER, lead):
    return ("【测试开场白】" + lead + "\n\n<" + TRIGGER + ">\n"
            + _sample_block(FIELDS) + "\n</" + TRIGGER + ">")


def build_protocol_md(FIELDS, TRIGGER, title):
    L = []
    L.append("# %s 生成协议（模型侧 · 蓝灯常驻条目）\n" % title)
    L.append("每次回复正文结束后，**另起一行**用单个 `<%s>...</%s>` 块输出当前状态全量快照。"
             "**固态字段每轮必出**（即使没变也照原值重出）；**情境字段仅在对应情境那轮输出**。\n"
             % (TRIGGER, TRIGGER))
    L.append("> 由雷达法转换而来：取消散落正文的 `[键=值]` 信标与信标转换器，改单块结构化输出。"
             "tooltip 说明（效果/成因等）**内联进对应字段**，不再散落正文。\n")
    L.append("## 输出格式\n```")
    L.append("<" + TRIGGER + ">")
    single = [f["key"] + "=" + f["example"] for f in sample_fields(FIELDS) if not f.get("multi")]
    multi = [f["key"] + "=" + f["example"] for f in sample_fields(FIELDS) if f.get("multi")]
    L.append(";".join(single))
    for m in multi:
        L.append(";" + m)
    L.append("</" + TRIGGER + ">\n```\n")
    L.append("- 字段间用 `;` 分隔，键值用 `=`。")
    L.append("- **multi 字段**每条目重复一次该键（如 `opt=...;opt=...`）。")
    L.append("- 值里**禁止** `< > = ;` 与换行。各字段内部分隔符见下表。\n")
    L.append("## 字段表\n")
    L.append("| 键名 | 含义 | 类型 | 格式 | 示例 | 代谢 | 别名 |")
    L.append("|---|---|---|---|---|---|---|")
    for f in data_fields(FIELDS):
        meta = "情境（用完即焚）" if f.get("volatile") else (
            "每轮全量" if f.get("multi") else "固态（继承）")
        aliases = f.get("aliases", [])
        at = "／".join("`%s`" % a for a in aliases) if aliases else "—"
        L.append("| `%s` | %s | %s | %s | `%s` | %s | %s |"
                 % (f["key"], f["label"], f["type"], f["format"], f["example"], meta, at))
    L.append("")
    L.append("## 分隔符约定\n")
    L.append("| 层级 | 符号 | 用于 |")
    L.append("|---|---|---|")
    L.append("| 字段间 | `;` | 所有字段 |")
    L.append("| 键值 | `=` | 所有字段 |")
    L.append("| 主分割 | `\\|` | bar成因/level经验/kvlist名↔说明/enemy各段/opt简介↔内容/bag类↔物品/lines各条 |")
    L.append("| 列表项 | `,` | stats各属性/kvlist各条 |")
    L.append("| 次级项 | `/`或`、` | bag同类物品/enemy属性组 |")
    L.append("| 标签值 | `:` | stats`属性:值`/kvlist`槽位:名`/enemy属性`AC:14` |")
    L.append("")
    L.append("## 铁律\n")
    L.append("- **推荐标准键名**（表第一列）；引擎对别名归一化容错，但标准键名最稳。")
    L.append("- **固态字段每轮必出**（面板无跨气泡状态、靠每轮全量，缺了引擎才向历史折叠兜底）。")
    volatile = [f["key"] for f in data_fields(FIELDS) if f.get("volatile")]
    if volatile:
        L.append("- **情境字段 %s：只在该情境那轮输出，情境结束立即停止**（不每轮重复、不在情境外保留——"
                 "面板随之消失，是防高刺激信息污染上下文的代谢机制，不是 bug）。"
                 % "/".join("`%s`" % k for k in volatile))
    multi_keys = [f["key"] for f in data_fields(FIELDS) if f.get("multi") and not f.get("volatile")]
    if multi_keys:
        L.append("- **%s 每轮全量重出**（multi 字段不继承，靠模型每轮吐全集）。"
                 % "/".join("`%s`" % k for k in multi_keys))
    if any(f["type"] == "option" for f in data_fields(FIELDS)):
        L.append("- 选项：3~4 个差异化走向；可触发性爱在简介前加 `♥`；简介≤10字、内容约70~80字含动作言语。")
    L.append("- 只吐数据块，不解释、不加排版标记。")
    return "\n".join(L)


def build_worldbook_json(config):
    """模型侧协议作为 constant=true 蓝灯条目的 SillyTavern 世界书 json。
    铁律：内嵌正则只负责渲染，没有这条常驻条目模型不会持续输出 <g3> 数据块。"""
    content = build_protocol_md(config["FIELDS"], config["TRIGGER"], config["TITLE"])
    return {"entries": {"0": {
        "uid": 0,
        "comment": "【%s · 状态栏生成协议】" % config["TITLE"],
        "content": content,
        "constant": True,
        "disable": False,
        "position": 4,
        "role": 0,
        "depth": 4,
        "order": 100,
        "probability": 100,
        "key": [],
        "keysecondary": [],
    }}}


def build_mmd_json(config):
    return {
        "pageDepth": 2,
        "statusbar": "",
        "beginning": build_beginning(config["FIELDS"], config["TRIGGER"], config["LEAD"]),
        "regex_scripts": [{
            "id": -1,
            "scriptName": config["SCRIPT_NAME"],
            "findRegex": build_find_regex(config["TRIGGER"]),
            "replaceString": build_replace_string(
                config["FIELDS"], config["TRIGGER"], config["CSS"], config["TITLE"]),
        }],
    }


def check_consistency(config):
    FIELDS, TRIGGER = config["FIELDS"], config["TRIGGER"]
    field_keys = [f["key"] for f in data_fields(FIELDS)]
    engine = build_engine_js(FIELDS, TRIGGER, config["CSS"], config["TITLE"])
    cfg_src = engine.split("var CFG=", 1)[1].split(";\nvar CSS", 1)[0]
    engine_keys = re.findall(r"'k':'([^']*)'", cfg_src)

    errs = []
    if engine_keys != field_keys:
        errs.append("引擎键名 %s != 字段键名 %s" % (engine_keys, field_keys))
    if '"' in engine:
        errs.append('引擎含裸双引号 "（会提前闭合 onerror，面板静默不渲染），改单引号')

    obj = build_mmd_json(config)
    for sc in obj["regex_scripts"]:
        fr, rs = sc["findRegex"], sc["replaceString"]
        if len(fr) > 1000:
            errs.append("findRegex 超 1000: %d" % len(fr))
        if len(rs) > 20000:
            errs.append("replaceString 超 20000: %d" % len(rs))
        if not (fr.startswith("/") and fr.rstrip("gimsuy").endswith("/")):
            errs.append("findRegex 缺斜杠分隔符: %s" % fr)
    try:
        json.dumps(obj, ensure_ascii=True)
    except (TypeError, ValueError) as e:
        errs.append("JSON 序列化失败: %s" % e)
    return errs, obj


def run_main(config):
    """场景脚本的共享 CLI。config 需含 FIELDS/TRIGGER/CSS/TITLE/SCRIPT_NAME/LEAD/OUT/PROTOCOL_OUT。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("-o", "--out", default=config["OUT"])
    args = ap.parse_args()

    errs, obj = check_consistency(config)
    rs_len = len(obj["regex_scripts"][0]["replaceString"])
    fr_len = len(obj["regex_scripts"][0]["findRegex"])

    if errs:
        print("校验失败：", file=sys.stderr)
        for e in errs:
            print("  - " + e, file=sys.stderr)
        return 1

    print("一致性断言通过：字段 = 引擎 CFG 键名一致")
    print("findRegex %d/1000；replaceString %d/20000" % (fr_len, rs_len))
    if args.check:
        print("--check：未写文件")
        return 0

    base = os.path.dirname(os.path.abspath(config["__file__"]))
    json_path = os.path.join(base, args.out)
    md_path = os.path.join(base, config["PROTOCOL_OUT"])
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=True, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_protocol_md(FIELDS=config["FIELDS"], TRIGGER=config["TRIGGER"],
                                  title=config["TITLE"]))
    print("已写: " + json_path)
    print("已写: " + md_path)
    if config.get("WORLDBOOK_OUT"):
        wb_path = os.path.join(base, config["WORLDBOOK_OUT"])
        with open(wb_path, "w", encoding="utf-8") as f:
            json.dump(build_worldbook_json(config), f, ensure_ascii=True, indent=2)
        print("已写: " + wb_path)
    return 0
