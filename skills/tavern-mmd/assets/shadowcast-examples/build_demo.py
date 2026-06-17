#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三代 MMD 状态栏 demo 生成器 build_demo.py

单一真相源(FIELDS)→ 生成:
  1. 引擎渲染配置(注入 img onerror 引擎)
  2. 模型侧协议(世界书蓝灯条目正文)
  3. 测试数据块(beginning 里的样例)
  4. MMD 导入 json(pageDepth/statusbar/beginning/regex_scripts)

架构(8靶全绿实测支撑,见 mmd.md §6b)：
  数据留 light DOM 隐藏 span → img onerror 读取(+扫历史折叠兜底)
  → attachShadow 复用幂等 → createElement 渲进 shadow(隔离/不过 markdown)
  → 模型每轮吐全量快照(per-message 无跨气泡状态)

用法:
  python build_demo.py              # 生成 g3-statusbar.mmd.json + 协议.md
  python build_demo.py --check      # 只跑一致性断言与 JSON 校验,不写文件

退出码: 0=成功  1=断言/校验失败  2=用法错误
"""
import sys
import json
import re
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ======================================================================
# 单一真相源：改字段只动这里。引擎配置/协议/测试数据全从此生成。
# ======================================================================
FIELDS = [
    {
        "key": "hp",
        "label": "生命",
        "type": "bar",            # 资源条 当前/最大
        "format": "当前/最大",
        "example": "85/100",
        "inherit": True,
    },
    {
        "key": "mood",
        "label": "心情",
        "type": "text",
        "format": "一个词或短语",
        "example": "害羞",
        "inherit": True,
    },
    {
        "key": "loc",
        "label": "地点",
        "type": "text",
        "format": "地点名",
        "example": "书房",
        "inherit": True,
    },
    {
        "key": "npc",
        "label": "在场角色",
        "type": "list",           # 条目用逗号分隔，名|属性
        "format": "名|好感:数值,名2|好感:数值2",
        "example": "茜|好感:15,真红|好感:-20",
        "inherit": True,
    },
    {
        "key": "fight",
        "label": "遭遇",
        "type": "list",
        "format": "敌名|HP:当前/最大,敌名2|HP:当前/最大2",
        "example": "野狼|HP:12/20",
        # volatile=情境绑定字段（雷达法"四类液态快照"）：仅在该情境那轮输出，
        # 情境结束就别再吐。引擎对它"不兜底"——缺失即不渲染（不从历史捞回），
        # 防高刺激数据残留污染上下文。数据层 light span 仍在历史可追溯。
        "volatile": True,
        "example_off": True,      # 测试开场白默认不带它（演示非战斗态）
    },
]

TRIGGER = "g3"  # 模型输出标记 <g3>...</g3>

# shadow 内 CSS（隔离，无需 z- 前缀/无需防 markdown 补丁）
SHADOW_CSS = (
    ":host{all:initial}"
    ".panel{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;"
    "border:1px solid #30363d;border-radius:12px;padding:14px;margin:8px 0}"
    ".row{display:flex;align-items:center;gap:10px;padding:6px 0;font-size:13px}"
    ".lbl{color:#8b949e;width:64px;flex-shrink:0;font-size:12px}"
    ".val{color:#e6edf3;flex:1}"
    ".bar{flex:1;height:6px;background:#161b22;border-radius:3px;overflow:hidden}"
    ".fill{height:100%;background:linear-gradient(90deg,#3fb950,#2ed573);border-radius:3px}"
    ".num{color:#8b949e;font-size:12px;width:64px;text-align:right;flex-shrink:0}"
    ".npcs{display:flex;flex-wrap:wrap;gap:6px;flex:1}"
    ".npc{background:#161b22;border:1px solid #30363d;border-radius:6px;"
    "padding:4px 8px;font-size:12px}"
    ".npc b{color:#58a6ff;font-weight:500}"
    ".pos{color:#3fb950}.neg{color:#f85149}"
)


# ======================================================================
# 引擎（ES6，跑在 img onerror 内）。CFG/CSS 由生成器注入为 JS 字面量。
# ======================================================================
def js_literal(val):
    """把 Python 数据序列化为 JS 字面量，字符串用单引号。
    铁律：onerror 属性用双引号包裹，注入的字面量必须全程单引号，
    否则内部的 " 会提前闭合 onerror 属性，破坏 img 标签结构（面板不渲染）。"""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return repr(val)
    if isinstance(val, str):
        # 转义反斜杠、单引号；禁止裸换行
        s = val.replace("\\", "\\\\").replace("'", "\\'")
        s = s.replace("\n", "\\n").replace("\r", "")
        return "'" + s + "'"
    if isinstance(val, list):
        return "[" + ",".join(js_literal(v) for v in val) + "]"
    if isinstance(val, dict):
        return "{" + ",".join(
            js_literal(str(k)) + ":" + js_literal(v) for k, v in val.items()
        ) + "}"
    raise TypeError("不支持的类型: %r" % type(val))


def build_engine_js():
    # 渲染配置：只取引擎需要的字段，键名与协议同源。
    # volatile 字段映射为 inherit=False：引擎对它不兜底（缺失即不渲染），
    # 即雷达法"液态快照代谢"——复用已有折叠分支，引擎逻辑零改动。
    cfg = [{"k": f["key"], "label": f["label"], "type": f["type"],
            "inherit": (not f.get("volatile", False)) and f.get("inherit", True)}
           for f in FIELDS]
    cfg_literal = js_literal(cfg)
    css_literal = js_literal(SHADOW_CSS)

    # 注意：整段是 onerror 属性值（外层双引号）。注入的 CFG/CSS 必须用单引号 JS
    # 字面量，绝不能用 json.dumps（双引号会与外层 onerror="" 撞引号、提前闭合属性、
    # 导致 img 结构破坏、引擎不绑定、面板静默不渲染）。详见 js_literal。
    # 引擎其余字符串字面量全程单引号；无 innerHTML 字符串拼接。
    engine = """(function(img){
var box=img.closest('.""" + TRIGGER + """-host');
if(!box)return;
var CFG=""" + cfg_literal + """;
var read=function(host){
var d=host.querySelector('.""" + TRIGGER + """-data');
var o={};
if(!d)return o;
d.textContent.split(';').forEach(function(pair){
var i=pair.indexOf('=');
if(i===-1)return;
var k=pair.slice(0,i).trim();
if(k)o[k]=pair.slice(i+1).trim();
});
return o;
};
var cur=read(box);
var hosts=document.querySelectorAll('.""" + TRIGGER + """-host');
var hostArr=[].slice.call(hosts);
var idx=hostArr.indexOf(box);
CFG.forEach(function(f){
if((cur[f.k]===undefined||cur[f.k]==='')&&f.inherit){
var prev=hostArr.slice(0,idx).reverse();
prev.some(function(h){
var p=read(h);
if(p[f.k]!==undefined&&p[f.k]!==''){cur[f.k]=p[f.k];return true;}
return false;
});
}
});
var sr=box.shadowRoot||box.attachShadow({mode:'open'});
while(sr.firstChild)sr.removeChild(sr.firstChild);
var st=document.createElement('style');
st.textContent=""" + css_literal + """;
sr.appendChild(st);
var panel=document.createElement('div');
panel.className='panel';
var mkRow=function(labelTxt){
var r=document.createElement('div');
r.className='row';
var l=document.createElement('span');
l.className='lbl';
l.textContent=labelTxt;
r.appendChild(l);
return r;
};
CFG.forEach(function(f){
var v=cur[f.k];
if(v===undefined||v==='')return;
try{
if(f.type==='bar'){
var m=v.match(/^(-?\\d+)\\s*\\/\\s*(\\d+)/);
var r=mkRow(f.label);
var bar=document.createElement('div');
bar.className='bar';
var fill=document.createElement('div');
fill.className='fill';
if(m){
var pct=Math.max(0,Math.min(100,parseInt(m[1],10)/parseInt(m[2],10)*100));
fill.style.width=pct+'%';
}
bar.appendChild(fill);
r.appendChild(bar);
var num=document.createElement('span');
num.className='num';
num.textContent=v;
r.appendChild(num);
panel.appendChild(r);
}else if(f.type==='list'){
var r2=mkRow(f.label);
var box2=document.createElement('div');
box2.className='npcs';
v.split(',').forEach(function(item){
var parts=item.split('|');
var name=(parts[0]||'').trim();
if(!name)return;
var chip=document.createElement('div');
chip.className='npc';
var nb=document.createElement('b');
nb.textContent=name;
chip.appendChild(nb);
if(parts[1]){
var fm=parts[1].match(/(-?\\d+)/);
var sp=document.createElement('span');
sp.textContent=' '+parts[1].trim();
if(fm){sp.className=fm[1].charAt(0)==='-'?'neg':'pos';}
chip.appendChild(sp);
}
box2.appendChild(chip);
});
r2.appendChild(box2);
panel.appendChild(r2);
}else{
var r3=mkRow(f.label);
var s=document.createElement('span');
s.className='val';
s.textContent=v;
r3.appendChild(s);
panel.appendChild(r3);
}
}catch(e){
var er=mkRow(f.label);
var es=document.createElement('span');
es.className='val';
es.textContent=v;
er.appendChild(es);
panel.appendChild(er);
}
});
sr.appendChild(panel);
})(this)"""
    return engine


def build_replace_string():
    """正则 replaceString：把 <g3>$1</g3> 变成 host(含隐藏数据 span + onerror 引擎)。
    单行无标签间换行(防 markdown 空白条)；引擎在 onerror 属性内,其换行无害。"""
    engine = build_engine_js()
    host = (
        '<div class="' + TRIGGER + '-host" onclick="event.stopPropagation()">'
        '<span class="' + TRIGGER + '-data" style="display:none">$1</span>'
        '<img src=x style="display:none" onerror="' + engine + '">'
        '</div>'
    )
    return host


def build_find_regex():
    # 铁律：findRegex 必须带 /.../ 斜杠分隔符,否则实际聊天不替换。
    return "/<" + TRIGGER + ">([\\s\\S]*?)<\\/" + TRIGGER + ">/"


def _sample_fields():
    """测试样例/开场白用的字段：跳过 example_off（演示非情境态，如非战斗）。"""
    return [f for f in FIELDS if not f.get("example_off", False)]


def build_protocol_md():
    lines = []
    lines.append("# 状态面板生成协议（模型侧 · 蓝灯常驻条目）\n")
    lines.append("每次回复正文结束后，**另起一行**输出当前状态。**固态字段每轮必出**（即"
                 "使没变也照原值重出）；**情境字段仅在对应情境那轮输出**（见下）。格式：\n")
    lines.append("```")
    lines.append("<" + TRIGGER + ">")
    lines.append(";".join(f["key"] + "=" + f["example"] for f in _sample_fields()))
    lines.append("</" + TRIGGER + ">")
    lines.append("```\n")
    lines.append("## 字段表\n")
    lines.append("| 键名 | 含义 | 格式 | 示例 | 代谢 |")
    lines.append("|---|---|---|---|---|")
    for f in FIELDS:
        meta = "情境（用完即焚）" if f.get("volatile") else "固态（继承）"
        lines.append("| `%s` | %s | %s | `%s` | %s |"
                     % (f["key"], f["label"], f["format"], f["example"], meta))
    lines.append("")
    lines.append("## 铁律")
    lines.append("- 用 `<%s>` 包裹，字段间用 `;` 分隔，键值用 `=`。" % TRIGGER)
    lines.append("- **固态字段每轮必出**（panel 无跨气泡状态、靠每轮全量，缺了引擎才向历史兜底）。")
    volatile_keys = [f["key"] for f in FIELDS if f.get("volatile")]
    if volatile_keys:
        lines.append("- **情境字段 %s：只在该情境发生的那轮输出，情境一结束就停止输出**。"
                     "不要每轮重复、不要在情境外保留——面板会随之消失（这是防高刺激信息"
                     "污染上下文的代谢机制，不是 bug）。" % "/".join("`%s`" % k for k in volatile_keys))
    lines.append("- 值里**不要出现** `<` `>` `;` `=` 与换行（会破坏解析/HTML）。")
    lines.append("- 列表字段条目用 `,` 分隔，名与属性用 `|`。")
    lines.append("- 不要解释、不要加任何排版标记，只吐数据块。")
    return "\n".join(lines)


def build_beginning():
    sample = ";".join(f["key"] + "=" + f["example"] for f in _sample_fields())
    return ("【测试开场白】她抬眼看你，欲言又止。\n\n<" + TRIGGER + ">\n"
            + sample + "\n</" + TRIGGER + ">")


def build_mmd_json():
    return {
        "pageDepth": 2,
        "statusbar": "",
        "beginning": build_beginning(),
        "regex_scripts": [
            {
                "id": -1,
                "scriptName": "G3状态栏渲染",
                "findRegex": build_find_regex(),
                "replaceString": build_replace_string(),
            }
        ],
    }


def check_consistency():
    """断言：协议字段键名 == 引擎 CFG 键名 == 测试数据键名。"""
    field_keys = [f["key"] for f in FIELDS]

    engine = build_engine_js()
    # 引擎里 CFG 是单引号 JS 字面量（非 JSON），用正则抽 k:'...' 键名
    cfg_src = engine.split("var CFG=", 1)[1].split(";\n", 1)[0]
    engine_keys = re.findall(r"\{'k':'([^']*)'", cfg_src)

    sample = build_beginning().split("<" + TRIGGER + ">", 1)[1]
    sample = sample.split("</" + TRIGGER + ">", 1)[0].strip()
    test_keys = [seg.split("=", 1)[0] for seg in sample.split(";") if seg]

    errs = []
    if engine_keys != field_keys:
        errs.append("引擎键名 %s != 字段键名 %s" % (engine_keys, field_keys))
    # 测试样例只含非 example_off 字段（情境字段默认不在开场白）
    sample_keys = [f["key"] for f in _sample_fields()]
    if test_keys != sample_keys:
        errs.append("测试键名 %s != 样例字段键名 %s" % (test_keys, sample_keys))

    # 铁律（唯一真红线，2026-06-17 浏览器+MMD 实机三组对照确认）：
    # onerror 用双引号包裹，引擎 JS 体内禁用裸双引号——内部 " 会提前闭合 onerror 属性、
    # 破坏 img 标签结构、引擎不绑定、面板静默不渲染（不爆代码但完全不显示）。
    # 所有字面量用单引号、CFG/CSS 用 js_literal 序列化（非 json.dumps）。
    # 注：裸 < > => 经实机证实在 onerror 引号内无害（HTML 属性值不解析标签；雷达法引擎
    #     满是 i<n/c>0 实战正常）。曾误立"禁裸 <>"已撤销——当初暴露真因仅是此处双引号。
    if '"' in engine:
        errs.append('引擎 JS 含裸双引号 "（会提前闭合 onerror="" 属性，'
                    '面板静默不渲染），所有字符串字面量改用单引号')

    # 字符数红线
    obj = build_mmd_json()
    for sc in obj["regex_scripts"]:
        if len(sc["findRegex"]) > 1000:
            errs.append("findRegex 超 1000: %d" % len(sc["findRegex"]))
        if len(sc["replaceString"]) > 20000:
            errs.append("replaceString 超 20000: %d" % len(sc["replaceString"]))
    # findRegex 必须带斜杠
    for sc in obj["regex_scripts"]:
        if not (sc["findRegex"].startswith("/") and sc["findRegex"].rstrip("gimsuy").endswith("/")):
            errs.append("findRegex 缺斜杠分隔符: %s" % sc["findRegex"])
    # JSON 可序列化
    try:
        json.dumps(obj, ensure_ascii=True)
    except (TypeError, ValueError) as e:
        errs.append("JSON 序列化失败: %s" % e)
    return errs, obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    ap.add_argument("-o", "--out", default="g3-statusbar.mmd.json")
    args = ap.parse_args()

    errs, obj = check_consistency()
    rs_len = len(obj["regex_scripts"][0]["replaceString"])
    fr_len = len(obj["regex_scripts"][0]["findRegex"])

    if errs:
        print("一致性/红线校验失败：", file=sys.stderr)
        for e in errs:
            print("  - " + e, file=sys.stderr)
        return 1

    print("一致性断言通过：字段 = 引擎 = 测试数据键名一致")
    print("findRegex 长度 %d / 1000；replaceString 长度 %d / 20000" % (fr_len, rs_len))

    if args.check:
        print("--check 模式：未写文件")
        return 0

    import os
    base = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base, args.out)
    md_path = os.path.join(base, "协议.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=True, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_protocol_md())

    print("已写: " + json_path)
    print("已写: " + md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
