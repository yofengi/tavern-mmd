#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shadow DOM 悬浮组件生成器 build_float.py

产出当前 MMD 可导入的悬浮球(可拖动+展开菜单)与侧边栏抽屉，UI 全部包进 shadow root：
  - host 挂 document.body（挣脱气泡 stacking context，浮在消息之上；靶10-11 已验证）
  - shadow 内 position:fixed + z-index 顶层 + 拖动 + 单例防重
  - 菜单跟随本体、翻转避裁、选项回填输入框
  - 隔离收益：CSS 不外泄/不被平台染色/不过 markdown 管线

铁律（构建期 guard 强制）：
  - onerror 用双引号包裹 → 内部 JS 全程单引号、禁裸双引号（唯一引号红线）
  - 裸 < > => 在 onerror 引号内无害（实机证实），无需规避
  - 方括号 [ ] 用 String.fromCharCode 拼（避开数据信标转换器啃断）

用法:
  python build_float.py            # 生成 float-shadow.mmd.json
  python build_float.py --check    # 只跑 guard 校验

退出码: 0=成功  1=guard失败  2=用法错误
"""
import sys
import json
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ======================================================================
# 配置：改菜单项/抽屉项/配色只动这里
# ======================================================================
BALL_TEXT = "✦"
MENU_ITEMS = [
    {"label": "📜 回顾剧情", "action": "请回顾目前的剧情进展", "drawer": False},
    {"label": "🎲 随机事件", "action": "请触发一个随机事件", "drawer": False},
    {"label": "📋 角色档案", "action": "", "drawer": True},   # 打开侧边栏
]
DRAWER_TITLE = "❖ 角色档案"
DRAWER_ITEMS = ["👤 姓名：林夏", "📜 任务：调查匿名信", "💰 持有：1200 文", "⚙️ 设置"]

COLORS = {
    "accent": "#58a6ff",
    "bg": "#161b22",
    "bg2": "#21262d",
    "fg": "#e6edf3",
    "border": "#30363d",
}


def _paint(css):
    # CSS 里大量 {} 不能用 str.format；用 @token@ 占位再 replace
    for k, v in COLORS.items():
        css = css.replace("@" + k + "@", v)
    return css


BALL_CSS = _paint(
    ".ball{position:fixed;left:18px;bottom:96px;width:50px;height:50px;border-radius:50%;"
    "background:@accent@;color:#fff;display:flex;align-items:center;justify-content:center;"
    "font-size:22px;z-index:2147483647;cursor:grab;box-shadow:0 3px 12px rgba(0,0,0,.4);"
    "touch-action:none;user-select:none}"
    ".menu{position:fixed;display:none;background:@bg@;border:1px solid @accent@;"
    "border-radius:8px;padding:6px;z-index:2147483647;min-width:140px;"
    "box-shadow:0 4px 16px rgba(0,0,0,.4)}"
    ".menu.open{display:block}"
    ".mi{padding:8px 10px;border-radius:6px;color:@fg@;font-size:13px;cursor:pointer;"
    "white-space:nowrap;font-family:system-ui,sans-serif}"
    ".mi:hover{background:@bg2@}"
)

DRAWER_CSS = _paint(
    ".sbtn{position:fixed;right:0;top:32%;background:@bg@;color:@fg@;border:1px solid @accent@;"
    "border-right:none;padding:10px 7px;border-radius:8px 0 0 8px;z-index:2147483646;"
    "cursor:pointer;font-size:18px;box-shadow:-2px 2px 10px rgba(0,0,0,.3)}"
    ".drawer{position:fixed;right:0;top:0;height:100%;width:250px;background:@bg@;color:@fg@;"
    "border-left:1px solid @accent@;z-index:2147483645;transform:translateX(100%);"
    "transition:transform .35s ease;padding:48px 16px 16px;box-sizing:border-box;"
    "overflow-y:auto;font-family:system-ui,sans-serif}"
    ".drawer.open{transform:translateX(0)}"
    ".dtitle{color:@accent@;font-weight:700;font-size:16px;margin-bottom:14px;"
    "border-bottom:1px solid @border@;padding-bottom:8px}"
    ".di{padding:9px 6px;border-radius:6px;font-size:13px;cursor:pointer;margin-bottom:4px}"
    ".di:hover{background:@bg2@}"
)


def js_literal(val):
    """单引号 JS 字面量序列化（禁双引号，避免与 onerror="" 撞引号）。"""
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
            js_literal(str(k)) + ":" + js_literal(v) for k, v in val.items()
        ) + "}"
    raise TypeError("不支持的类型: %r" % type(val))


# ======================================================================
# 悬浮球引擎（ES6，跑在 img onerror 内，挂 body + shadow）
# 注：全程单引号、零裸 < > =>；getBoundingClientRect 用 .left/.top/.bottom 取值
# ======================================================================
def build_ball_engine():
    labels = js_literal([m["label"] for m in MENU_ITEMS])
    actions = js_literal([m["action"] for m in MENU_ITEMS])
    drawers = js_literal([m["drawer"] for m in MENU_ITEMS])
    css = js_literal(BALL_CSS)
    ball_text = js_literal(BALL_TEXT)

    return """(function(img){
if(document.getElementById('zsf-ball-wrap')){img.remove();return;}
var wrap=document.createElement('div');
wrap.id='zsf-ball-wrap';
var sr=wrap.attachShadow({mode:'open'});
var st=document.createElement('style');
st.textContent=""" + css + """;
sr.appendChild(st);
var ball=document.createElement('div');
ball.className='ball';
ball.textContent=""" + ball_text + """;
sr.appendChild(ball);
var menu=document.createElement('div');
menu.className='menu';
menu.onclick=function(ev){ev.stopPropagation();};
sr.appendChild(menu);
var LB=String.fromCharCode(91),RB=String.fromCharCode(93);
var labels=""" + labels + """;
var actions=""" + actions + """;
var drawers=""" + drawers + """;
var fillInput=function(txt){
var sel='textarea, input'+LB+'type=text'+RB;
var t=document.querySelector(sel);
if(t){t.value=(t.value||'')+txt;t.dispatchEvent(new Event('input',{bubbles:true}));}
};
labels.forEach(function(lab,idx){
var mi=document.createElement('div');
mi.className='mi';
mi.textContent=lab;
mi.onclick=function(ev){
ev.stopPropagation();
if(drawers[idx]){
var dw=document.getElementById('zsf-drawer-wrap');
if(dw&&dw.shadowRoot){var d=dw.shadowRoot.querySelector('.drawer');if(d)d.classList.add('open');}
}else if(actions[idx]){fillInput(actions[idx]);}
menu.classList.remove('open');
};
menu.appendChild(mi);
});
var moved=false,sx=0,sy=0,ox=0,oy=0,GAP=8;
var reposition=function(){
if(menu.classList.contains('open')===false)return;
var r=ball.getBoundingClientRect();
var mw=menu.offsetWidth,mh=menu.offsetHeight;
var vw=window.innerWidth,vh=window.innerHeight,top;
var spaceUp=r.top-GAP-mh;
var spaceDown=r.bottom+GAP+mh;
if(Math.max(0,spaceUp)===spaceUp){top=spaceUp;}
else if(Math.min(vh,spaceDown)===spaceDown){top=r.bottom+GAP;}
else{top=Math.max(GAP,Math.min(vh-mh-GAP,r.top));}
var left=Math.max(GAP,Math.min(vw-mw-GAP,r.left));
menu.style.left=left+'px';menu.style.top=top+'px';menu.style.bottom='auto';
};
var onMove=function(cx,cy){
if(Math.max(3,Math.abs(cx-sx)+Math.abs(cy-sy))!==3)moved=true;
var nx=ox+cx-sx,ny=oy+cy-sy;
var vw=window.innerWidth,vh=window.innerHeight,bw=ball.offsetWidth,bh=ball.offsetHeight;
nx=Math.max(0,Math.min(vw-bw,nx));
ny=Math.max(0,Math.min(vh-bh,ny));
ball.style.left=nx+'px';ball.style.top=ny+'px';ball.style.bottom='auto';
reposition();
};
var mm=function(ev){onMove(ev.clientX,ev.clientY);};
var tm=function(ev){var t=ev.touches[0];onMove(t.clientX,t.clientY);ev.preventDefault();};
var up=function(){
document.removeEventListener('mousemove',mm);
document.removeEventListener('mouseup',up);
document.removeEventListener('touchmove',tm);
document.removeEventListener('touchend',up);
ball.style.cursor='grab';
if(moved===false){
if(menu.classList.contains('open')){menu.classList.remove('open');}
else{menu.classList.add('open');reposition();}
}
};
var down=function(cx,cy){
moved=false;sx=cx;sy=cy;
var r=ball.getBoundingClientRect();ox=r.left;oy=r.top;
ball.style.cursor='grabbing';
};
ball.addEventListener('mousedown',function(ev){
ev.stopPropagation();down(ev.clientX,ev.clientY);
document.addEventListener('mousemove',mm);document.addEventListener('mouseup',up);
});
ball.addEventListener('touchstart',function(ev){
ev.stopPropagation();var t=ev.touches[0];down(t.clientX,t.clientY);
document.addEventListener('touchmove',tm,{passive:false});
document.addEventListener('touchend',up);
},{passive:false});
document.body.appendChild(wrap);
img.remove();
})(this)"""


def build_drawer_engine():
    title = js_literal(DRAWER_TITLE)
    items = js_literal(DRAWER_ITEMS)
    css = js_literal(DRAWER_CSS)

    return """(function(img){
if(document.getElementById('zsf-drawer-wrap')){img.remove();return;}
var wrap=document.createElement('div');
wrap.id='zsf-drawer-wrap';
var sr=wrap.attachShadow({mode:'open'});
var st=document.createElement('style');
st.textContent=""" + css + """;
sr.appendChild(st);
var drawer=document.createElement('div');
drawer.className='drawer';
drawer.onclick=function(ev){ev.stopPropagation();};
var ti=document.createElement('div');
ti.className='dtitle';
ti.textContent=""" + title + """;
drawer.appendChild(ti);
var items=""" + items + """;
items.forEach(function(txt){
var di=document.createElement('div');
di.className='di';
di.textContent=txt;
drawer.appendChild(di);
});
var btn=document.createElement('div');
btn.className='sbtn';
btn.textContent='☰';
btn.onclick=function(ev){ev.stopPropagation();drawer.classList.toggle('open');};
sr.appendChild(drawer);
sr.appendChild(btn);
document.body.appendChild(wrap);
img.remove();
})(this)"""


def host_img(engine, marker_attr):
    return ('<img src=x ' + marker_attr + ' style="display:none" onerror="'
            + engine + '">')


def build_mmd_json():
    ball = host_img(build_ball_engine(), 'data-zsf-ball="1"')
    drawer = host_img(build_drawer_engine(), 'data-zsf-drawer="1"')
    beginning = ("【测试开场白】夜色压下来，她把一枚铜钥匙推到你面前。\n\n"
                 "<悬浮球><侧边栏>")
    return {
        "pageDepth": 2,
        "statusbar": "<悬浮球><侧边栏>",
        "beginning": beginning,
        "regex_scripts": [
            {"id": -1, "scriptName": "悬浮球-shadow",
             "findRegex": "/<悬浮球>/", "replaceString": ball},
            {"id": -1, "scriptName": "侧边栏-shadow",
             "findRegex": "/<侧边栏>/", "replaceString": drawer},
        ],
    }


def run_guards():
    errs = []
    obj = build_mmd_json()
    for sc in obj["regex_scripts"]:
        rs = sc["replaceString"]
        name = sc["scriptName"]
        # 抽 onerror 属性内的 JS 体
        body = rs.split('onerror="', 1)[1].rsplit('">', 1)[0]
        # 真红线：内部禁裸双引号（提前闭合 onerror→静默不渲染）。
        # 注：裸 < > => 经实机证实在引号内无害，曾误立的"禁裸 <>"已撤销。
        if '"' in body:
            errs.append("%s: 引擎含裸双引号（提前闭合 onerror，静默不渲染）" % name)
        # 字面 [键=值] 模板检查（数据信标转换器 /\[..=..\]/ 会啃断）；
        # 数组索引 touches[0] 这类合法，只查方括号内含 = 的危险模式
        import re as _re
        if _re.search(r"\[[^\]]*=[^\]]*\]", body):
            errs.append("%s: 引擎含字面 [键=值]（信标转换器会啃断，"
                        "用 String.fromCharCode 拼方括号）" % name)
        # 字符数红线
        if len(sc["findRegex"]) > 1000:
            errs.append("%s: findRegex 超 1000" % name)
        if len(rs) > 20000:
            errs.append("%s: replaceString 超 20000 (%d)" % (name, len(rs)))
        # 斜杠
        if not (sc["findRegex"].startswith("/") and
                sc["findRegex"].rstrip("gimsuy").endswith("/")):
            errs.append("%s: findRegex 缺斜杠分隔符" % name)
    try:
        json.dumps(obj, ensure_ascii=True)
    except (TypeError, ValueError) as e:
        errs.append("JSON 序列化失败: %s" % e)
    return errs, obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("-o", "--out", default="float-shadow.mmd.json")
    args = ap.parse_args()

    errs, obj = run_guards()
    if errs:
        print("guard 校验失败：", file=sys.stderr)
        for e in errs:
            print("  - " + e, file=sys.stderr)
        return 1

    for sc in obj["regex_scripts"]:
        print("%s: replaceString %d / 20000" % (sc["scriptName"], len(sc["replaceString"])))
    print("guard 通过：无裸双引号、无字面 [键=值]、字符数达标、findRegex 带斜杠")

    if args.check:
        print("--check 模式：未写文件")
        return 0

    import os
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, args.out)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=True, indent=2)
    print("已写: " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
