#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影渲法 宅邸场景状态栏生成器 build_manor.py（由雷达法「完整美化」状态栏转换）

源：完整美化-状态栏规则.txt（单角色聚焦：姓名/时间/地点/外貌/神态/宅邸掠影/
堕落值/事件记录/事件总结/色情特写[情境]/怀疑度[条件触发]/选项）。
注：源「完整美化」的全局日夜主题美化按影渲法规范不可转（穿透 vs 隔离相反），
本生成器只转其状态栏部分。

引擎复用 shadowcast_core（与 RPG 同一引擎源）。改字段只动这里。

用法:
  python build_manor.py            # 生成 manor-statusbar.mmd.json + 宅邸协议.md
  python build_manor.py --check
"""
import sys
import shadowcast_core as core

S = lambda label: {"type": "section", "label": label}

FIELDS = [
    S("交互对象"),
    {"key": "name", "label": "姓名", "type": "text",
     "format": "当前交互对象角色名", "example": "白雪凝", "inherit": True,
     "aliases": ["姓名", "交互对象"]},
    {"key": "time", "label": "时间", "type": "time",
     "format": "年月日 时段（清晨/上午/中午/下午/黄昏/夜间/深夜）",
     "example": "深秋十月 黄昏", "inherit": True, "aliases": ["时间"]},
    {"key": "loc", "label": "地点", "type": "path",
     "format": "区域-具体位置（连字符分层）", "example": "云岚宅邸-主楼-二层书房",
     "inherit": True, "aliases": ["地点", "位置"]},
    {"key": "look", "label": "外貌", "type": "text",
     "format": "当前衣着状态及容貌特写", "example": "月白旗袍，发髻微松，眼角含春",
     "inherit": True, "aliases": ["外貌", "衣着"]},
    {"key": "mood", "label": "神态", "type": "text",
     "format": "当前表情或动作", "example": "垂眸抿唇，指尖轻绞衣角",
     "inherit": True, "aliases": ["神态", "表情"]},
    {"key": "manor", "label": "宅邸掠影", "type": "text",
     "format": "宅邸内女仆动态/流言/画面特写（离开宅邸则换为环境描写）",
     "example": "回廊尽头两名女仆低声议论着昨夜的动静",
     "inherit": True, "aliases": ["宅邸掠影", "掠影", "环境"]},

    S("状态"),
    {"key": "fall", "label": "堕落值", "type": "bar",
     "format": "当前/100（交互对象非白雪凝时键名语义为好感度）",
     "example": "35/100", "inherit": True, "aliases": ["堕落值", "好感度", "好感"]},
    {"key": "doubt", "label": "怀疑度", "type": "bar",
     "format": "当前/100（条件触发常驻：起疑后解锁，解锁后每轮必出，误会解除前不停）",
     "example": "20/100", "volatile": True, "example_off": True,
     "aliases": ["怀疑度", "疑心"]},
    {"key": "turn", "label": "回复轮次", "type": "turn",
     "format": "数字（每轮+1）", "example": "5", "inherit": True,
     "aliases": ["回复轮次", "轮次"]},

    S("记忆"),
    {"key": "log", "label": "事件记录", "type": "lines",
     "format": "N.内容|N.内容|...（每条≤60字，最多4条，超4条删最旧上移）",
     "example": "1.初见于宅邸门前|2.书房密谈|3.察觉异样|4.暂无",
     "inherit": True, "aliases": ["事件记录", "记录"]},
    {"key": "event", "label": "事件总结", "type": "summary",
     "format": "N/3|内容（N=1或2填 暂无；N=3填约150字总结，下轮重置1）",
     "example": "1/3|暂无", "inherit": True, "aliases": ["事件总结", "总结"]},

    S("情境特写"),
    {"key": "lewd", "label": "色情特写", "type": "kvlist",
     "format": "部位:描写,部位:描写（仅色情互动那轮输出，脱离立即停）",
     "example": "蜜穴:微微开合渗出晶莹,体位:背入",
     "volatile": True, "example_off": True, "aliases": ["色情特写", "特写", "淫靡"]},

    S("行动选项"),
    {"key": "opt", "label": "选项", "type": "option", "multi": True,
     "format": "简介|内容（每个选项一条 opt=；触发性爱在简介前加 ♥）",
     "example": "温柔安抚|上前轻握她的手，柔声问她在烦扰什么",
     "volatile": True, "inherit": False, "aliases": ["选项"]},
]

# 宅邸主题：暗紫/酒红 + 金描边（区别 RPG 暗金）。结构类名沿用 g3-* 与引擎一致。
CSS = (
    ":host{all:initial}"
    ".g3-panel{font-family:'Songti SC',serif;width:100%;"
    "background:linear-gradient(150deg,#1a1320,#241a2e);color:#e8dfe8;"
    "padding:14px;border-radius:12px;border:1px solid #8a6d9e;margin:8px 0;"
    "box-shadow:0 8px 22px rgba(0,0,0,0.65);line-height:1.7;box-sizing:border-box;"
    "overflow-wrap:break-word}"
    ".g3-panel *{box-sizing:border-box}"
    ".g3-title{text-align:center;font-size:18px;font-weight:bold;color:#d8b4e0;"
    "border-bottom:1px solid #8a6d9e;padding-bottom:8px;margin-bottom:12px;letter-spacing:2px}"
    ".g3-sec{background:#221a2c;padding:11px;border-radius:8px;margin-bottom:12px;"
    "border:1px solid #3d2f4d}"
    ".g3-sec-t{color:#c79fd6;font-weight:bold;margin-bottom:8px;font-size:14px}"
    ".g3-row{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px;flex-wrap:wrap}"
    ".g3-lbl{color:#9a8aa8;min-width:60px;flex-shrink:0}"
    ".g3-val{color:#e8dfe8;flex:1}"
    ".g3-crumb{background:#2c2238;padding:2px 7px;border-radius:4px;font-size:12px;"
    "border:1px solid #3d2f4d}"
    ".g3-arr{color:#c79fd6;margin:0 2px}"
    ".g3-time{color:#d8b4e0;font-weight:bold}"
    ".g3-bar-wrap{flex:1;min-width:120px}"
    ".g3-bar-top{display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px}"
    ".g3-bar{background:#2c2238;border-radius:4px;height:8px;width:100%;overflow:hidden}"
    ".g3-fill{height:100%;border-radius:4px}"
    ".g3-hp{background:#c2477a;box-shadow:0 0 5px #c2477a}"
    ".g3-mp{background:#9a6cd0;box-shadow:0 0 5px #9a6cd0}"
    ".g3-sp{background:#c79fd6;box-shadow:0 0 5px #c79fd6}"
    ".g3-ar{background:#b07ed0;box-shadow:0 0 5px #b07ed0}"
    ".g3-xp{background:#d8b4e0;box-shadow:0 0 5px #d8b4e0}"
    ".g3-stats{display:flex;flex-wrap:wrap;gap:6px;flex:1}"
    ".g3-stat{background:#2c2238;padding:3px 9px;border-radius:4px;font-size:12px;"
    "border-left:3px solid #c79fd6}"
    ".g3-kv{display:flex;flex-direction:column;gap:5px;flex:1}"
    ".g3-kvi{font-size:13px}"
    ".g3-kk{color:#9a8aa8}"
    ".g3-kn{color:#e8dfe8}"
    ".g3-help{color:#d8b4e0;cursor:help;border-bottom:1px dashed #7a6a88}"
    ".g3-tt{position:relative;display:inline-block}"
    ".g3-tt .g3-box{display:none;position:absolute;bottom:100%;left:0;background:#1a1320;"
    "border:1px solid #c79fd6;padding:7px;border-radius:4px;z-index:99;width:max-content;"
    "max-width:230px;white-space:pre-wrap;color:#d8b4e0;font-size:12px;"
    "box-shadow:0 4px 8px rgba(0,0,0,0.5);margin-bottom:4px;pointer-events:none}"
    ".g3-tt:hover .g3-box{display:block}"
    ".g3-bag-h{display:flex;align-items:center;gap:5px;border-bottom:1px solid #4d3f5d;"
    "margin-bottom:8px;padding-bottom:4px}"
    ".g3-tabs{display:flex;gap:4px;overflow-x:auto;flex:1}"
    ".g3-nav{background:none;border:none;color:#9a8aa8;cursor:pointer;font-size:12px;"
    "padding:2px 5px;flex-shrink:0}"
    ".g3-tab{background:none;border:none;color:#b8a8c8;cursor:pointer;padding:4px 7px;"
    "border-bottom:2px solid transparent;font-size:13px;white-space:nowrap;flex-shrink:0}"
    ".g3-tab.on{color:#d8b4e0;border-color:#c79fd6}"
    ".g3-bag-c{padding:9px;background:#1a1320;border-radius:4px;font-size:13px;"
    "border:1px solid #3d2f4d;min-height:50px}"
    ".g3-bag-i{padding:2px 0}"
    ".g3-enemy{background:#1a1320;padding:9px;border-radius:6px;margin-bottom:8px;"
    "border:1px solid #5a3a4a}"
    ".g3-en{color:#e06a9a;font-weight:bold;margin-bottom:4px}"
    ".g3-ehp{background:#2c2238;border-radius:3px;height:6px;width:100%;margin:4px 0;overflow:hidden}"
    ".g3-ehp-f{background:#8b2050;height:100%}"
    ".g3-eg{display:flex;flex-wrap:wrap;gap:8px;font-size:12px;color:#b8a8c8}"
    ".g3-sum{margin-top:6px;color:#b8a8c8;font-style:italic;font-size:12px}"
    ".g3-badge{background:#2c2238;color:#d8b4e0;font-size:12px;padding:2px 8px;"
    "border-radius:4px;border:1px solid #c79fd6;float:right}"
    ".g3-opt{background:#2a2238;padding:10px;border-radius:6px;margin-bottom:8px;"
    "font-size:14px;font-weight:bold;text-align:center;cursor:pointer;"
    "border:1px solid #3d2f4d;box-shadow:0 2px 4px rgba(0,0,0,0.2)}"
    ".g3-opt:hover{background:#382c48;border-color:#c79fd6}"
    ".g3-opt:active{background:#2a2238}"
    ".g3-ero{background:#3a1f2e;border-color:#c24b78;color:#fca5c5}"
    ".g3-ero:hover{background:#4d2638;border-color:#ff75a0}"
)

CONFIG = {
    "FIELDS": FIELDS,
    "TRIGGER": "g3",
    "CSS": CSS,
    "TITLE": "宅邸状态面板",
    "SCRIPT_NAME": "宅邸影渲法状态栏",
    "LEAD": "她立在书房窗前，听见你推门的声音，肩头几不可察地一颤。",
    "OUT": "manor-statusbar.mmd.json",
    "PROTOCOL_OUT": "宅邸协议.md",
    "WORLDBOOK_OUT": "宅邸状态栏协议-蓝灯世界书.json",
    "__file__": __file__,
}

if __name__ == "__main__":
    sys.exit(core.run_main(CONFIG))
