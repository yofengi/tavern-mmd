#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影渲法 RPG 状态栏生成器 build_rpg.py（西幻RPG，由雷达法转换）

只定义 config（单一真相源 FIELDS + 主题 CSS + 标题），引擎/协议/JSON 全部
复用 shadowcast_core。改字段只动这里。

用法:
  python build_rpg.py            # 生成 rpg-statusbar.mmd.json + RPG协议.md
  python build_rpg.py --check    # 只校验不写文件
"""
import sys
import shadowcast_core as core

S = lambda label: {"type": "section", "label": label}

FIELDS = [
    S("基本档案"),
    {"key": "name", "label": "主角姓名", "type": "text",
     "format": "角色名", "example": "{{user}}", "inherit": True,
     "aliases": ["主角姓名", "姓名"]},
    {"key": "gender", "label": "主角性别", "type": "text",
     "format": "性别", "example": "男性", "inherit": True,
     "aliases": ["主角性别", "性别"]},
    {"key": "loc", "label": "当前地点", "type": "path",
     "format": "大陆-国家-地标-房间（连字符分层）", "example": "星陨大陆-星陨王国-废弃法师塔-底层大厅",
     "inherit": True, "aliases": ["当前地点", "地点", "位置"]},
    {"key": "time", "label": "当前时间", "type": "time",
     "format": "年月日 时段（清晨/上午/中午/下午/黄昏/夜间/深夜）",
     "example": "星历1472年9月15日 黄昏", "inherit": True,
     "aliases": ["当前时间", "时间"]},
    {"key": "armor", "label": "护甲值", "type": "bar",
     "format": "数值 或 数值|成因说明", "example": "15", "inherit": True,
     "aliases": ["护甲值", "护甲", "护甲状态"]},
    {"key": "hp", "label": "生命值", "type": "bar",
     "format": "当前/最大 或 当前/最大|成因", "example": "45/45", "inherit": True,
     "aliases": ["生命值", "生命", "血量", "生命状态"]},
    {"key": "mp", "label": "魔法值", "type": "bar",
     "format": "当前/最大 或 当前/最大|成因", "example": "65/100", "inherit": True,
     "aliases": ["魔法值", "魔法", "魔力", "魔法状态"]},
    {"key": "sp", "label": "精力值", "type": "bar",
     "format": "当前/最大 或 当前/最大|成因", "example": "80/100", "inherit": True,
     "aliases": ["精力值", "精力", "精力状态"]},

    S("核心属性"),
    {"key": "race", "label": "种族等级", "type": "level",
     "format": "名|当前经验/阈值", "example": "3级精灵|100/300", "inherit": True,
     "aliases": ["种族等级", "种族"]},
    {"key": "cls", "label": "职业等级", "type": "level",
     "format": "名|当前经验/阈值", "example": "4级奥术师|200/400", "inherit": True,
     "aliases": ["职业等级", "职业"]},
    {"key": "stats", "label": "六围", "type": "stats",
     "format": "属性:值,属性:值（可选 属性:值:成因）",
     "example": "体质:10,力量:8,敏捷:14,智力:18,感知:15,魅力:16",
     "inherit": True, "aliases": ["六围", "属性"]},

    S("武装与能力"),
    {"key": "equip", "label": "装备", "type": "kvlist",
     "format": "槽位:名|说明,槽位:名|说明（说明可省）",
     "example": "头饰:月夜辉冠|感知+3智力+6,主武器:紫木法杖|每击1d4钝+1d4奥术,全身:月白奥法袍",
     "inherit": True, "aliases": ["装备", "穿戴"]},
    {"key": "skill", "label": "技能", "type": "kvlist",
     "format": "分类:名|说明,分类:名|说明（说明可省）",
     "example": "法术:奥术飞弹|消耗5魔法发3飞弹,法术:霜冻新星|消耗15魔法冻结并2d6寒霜,天赋:黑暗视觉",
     "inherit": True, "aliases": ["技能", "能力"]},

    S("背包储备"),
    {"key": "bag", "label": "背包", "type": "bag", "multi": True,
     "format": "分类|物品1/物品2/物品3（每类一条 bag=，每轮全量重出）",
     "example": "消耗品|强效恢复药剂2瓶/初级解毒剂/照明卷轴3卷",
     "inherit": True, "aliases": ["背包", "物品", "储备"]},

    S("当前局势"),
    {"key": "enemy", "label": "遭遇敌人", "type": "enemy", "multi": True,
     "format": "名|HP当前/最大|属性k:v/k:v|状态（每个敌人一条 enemy=）",
     "example": "低阶石像鬼A|28/40|AC:14/DC:12/力量:16|左翼碎裂",
     "volatile": True, "example_off": True,
     "aliases": ["遭遇敌人", "遭遇", "敌人", "敌"]},
    {"key": "goal", "label": "任务目标", "type": "text",
     "format": "短期目标（无则填 暂无）", "example": "消灭石像鬼并寻找上层实验室的隐藏阶梯",
     "inherit": True, "aliases": ["任务目标", "目标"]},
    {"key": "event", "label": "事件总结", "type": "summary",
     "format": "N/3|总结内容（N=1或2填 暂无；N=3填约150字回顾，下轮重置1）",
     "example": "1/3|暂无", "inherit": True, "aliases": ["事件总结", "事件"]},
    {"key": "turn", "label": "回复轮次", "type": "turn",
     "format": "数字（每轮+1）", "example": "5", "inherit": True,
     "aliases": ["回复轮次", "轮次"]},

    S("行动选项"),
    {"key": "opt", "label": "选项", "type": "option", "multi": True,
     "format": "简介|内容（每个选项一条 opt=；触发性爱在简介前加 ♥）",
     "example": "施放霜冻新星|消耗魔法制造大范围冰冻，延缓石像鬼B的侧翼包抄",
     "volatile": True, "inherit": False, "aliases": ["选项"]},
]

CSS = (
    ":host{all:initial}"
    ".g3-panel{font-family:system-ui,sans-serif;width:100%;"
    "background:linear-gradient(145deg,#1c1c24,#262635);color:#dcdcdc;"
    "padding:14px;border-radius:12px;border:2px solid #d4af37;margin:8px 0;"
    "box-shadow:0 8px 20px rgba(0,0,0,0.6);line-height:1.6;box-sizing:border-box;"
    "overflow-wrap:break-word}"
    ".g3-panel *{box-sizing:border-box}"
    ".g3-title{text-align:center;font-size:18px;font-weight:bold;color:#d4af37;"
    "border-bottom:2px solid #d4af37;padding-bottom:8px;margin-bottom:12px;letter-spacing:1px}"
    ".g3-sec{background:#242430;padding:11px;border-radius:8px;margin-bottom:12px;"
    "border:1px solid #3a3a48}"
    ".g3-sec-t{color:#e6c27a;font-weight:bold;margin-bottom:8px;font-size:14px}"
    ".g3-row{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px;flex-wrap:wrap}"
    ".g3-lbl{color:#a9a9a9;min-width:60px;flex-shrink:0}"
    ".g3-val{color:#dcdcdc;flex:1}"
    ".g3-crumb{background:#2a2a35;padding:2px 7px;border-radius:4px;font-size:12px;"
    "border:1px solid #3a3a48}"
    ".g3-arr{color:#d4af37;margin:0 2px}"
    ".g3-time{color:#d4af37;font-weight:bold}"
    ".g3-bar-wrap{flex:1;min-width:120px}"
    ".g3-bar-top{display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px}"
    ".g3-bar{background:#2a2a35;border-radius:4px;height:8px;width:100%;overflow:hidden}"
    ".g3-fill{height:100%;border-radius:4px}"
    ".g3-hp{background:#ff3333;box-shadow:0 0 5px #ff3333}"
    ".g3-mp{background:#3399ff;box-shadow:0 0 5px #3399ff}"
    ".g3-sp{background:#33cc66;box-shadow:0 0 5px #33cc66}"
    ".g3-ar{background:#bbbbbb;box-shadow:0 0 5px #999}"
    ".g3-xp{background:#d4af37;box-shadow:0 0 5px #d4af37}"
    ".g3-stats{display:flex;flex-wrap:wrap;gap:6px;flex:1}"
    ".g3-stat{background:#2a2a35;padding:3px 9px;border-radius:4px;font-size:12px;"
    "border-left:3px solid #d4af37}"
    ".g3-kv{display:flex;flex-direction:column;gap:5px;flex:1}"
    ".g3-kvi{font-size:13px}"
    ".g3-kk{color:#a9a9a9}"
    ".g3-kn{color:#dcdcdc}"
    ".g3-help{color:#e6c27a;cursor:help;border-bottom:1px dashed #777}"
    ".g3-tt{position:relative;display:inline-block}"
    ".g3-tt .g3-box{display:none;position:absolute;bottom:100%;left:0;background:#1e1e24;"
    "border:1px solid #d4af37;padding:7px;border-radius:4px;z-index:99;width:max-content;"
    "max-width:230px;white-space:pre-wrap;color:#e6c27a;font-size:12px;"
    "box-shadow:0 4px 8px rgba(0,0,0,0.5);margin-bottom:4px;pointer-events:none}"
    ".g3-tt:hover .g3-box{display:block}"
    ".g3-bag-h{display:flex;align-items:center;gap:5px;border-bottom:1px solid #555;"
    "margin-bottom:8px;padding-bottom:4px}"
    ".g3-tabs{display:flex;gap:4px;overflow-x:auto;flex:1}"
    ".g3-nav{background:none;border:none;color:#a9a9a9;cursor:pointer;font-size:12px;"
    "padding:2px 5px;flex-shrink:0}"
    ".g3-tab{background:none;border:none;color:#b8b8b8;cursor:pointer;padding:4px 7px;"
    "border-bottom:2px solid transparent;font-size:13px;white-space:nowrap;flex-shrink:0}"
    ".g3-tab.on{color:#d4af37;border-color:#d4af37}"
    ".g3-bag-c{padding:9px;background:#1e1e24;border-radius:4px;font-size:13px;"
    "border:1px solid #3a3a48;min-height:50px}"
    ".g3-bag-i{padding:2px 0}"
    ".g3-enemy{background:#1e1e24;padding:9px;border-radius:6px;margin-bottom:8px;"
    "border:1px solid #5a3a3a}"
    ".g3-en{color:#ff6666;font-weight:bold;margin-bottom:4px}"
    ".g3-ehp{background:#2a2a35;border-radius:3px;height:6px;width:100%;margin:4px 0;overflow:hidden}"
    ".g3-ehp-f{background:#8b0000;height:100%}"
    ".g3-eg{display:flex;flex-wrap:wrap;gap:8px;font-size:12px;color:#b8b8b8}"
    ".g3-sum{margin-top:6px;color:#b8b8b8;font-style:italic;font-size:12px}"
    ".g3-badge{background:#2a2a35;color:#e6c27a;font-size:12px;padding:2px 8px;"
    "border-radius:4px;border:1px solid #d4af37;float:right}"
    ".g3-opt{background:#2c2c3a;padding:10px;border-radius:6px;margin-bottom:8px;"
    "font-size:14px;font-weight:bold;text-align:center;cursor:pointer;"
    "border:1px solid #3c3c4a;box-shadow:0 2px 4px rgba(0,0,0,0.2)}"
    ".g3-opt:hover{background:#3a3a4c;border-color:#d4af37}"
    ".g3-opt:active{background:#2c2c3a}"
    ".g3-ero{background:#361f27;border-color:#b84b62;color:#fca5b9}"
    ".g3-ero:hover{background:#4d2633;border-color:#ff7596}"
)

CONFIG = {
    "FIELDS": FIELDS,
    "TRIGGER": "g3",
    "CSS": CSS,
    "TITLE": "角色状态与局势面板",
    "SCRIPT_NAME": "RPG影渲法状态栏",
    "LEAD": "晨星在塔底废墟站定，指尖扣住法杖。",
    "OUT": "rpg-statusbar.mmd.json",
    "PROTOCOL_OUT": "RPG协议.md",
    "WORLDBOOK_OUT": "RPG状态栏协议-蓝灯世界书.json",
    "__file__": __file__,
}

if __name__ == "__main__":
    sys.exit(core.run_main(CONFIG))
