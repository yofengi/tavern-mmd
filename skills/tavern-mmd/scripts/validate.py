#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 审核脚本 validate.py
纯文本静态审核：JSON合法性 / BOM / 双重转义 / 平台红线 / v2规范 / 世界书字段。
不渲染、不联网、不依赖第三方库。子代理可直接调用以节约上下文。

用法:
  python validate.py <文件> --type <regex|card|worldbook> --platform <oldmmd|mmd|st>

  --type 省略时按文件内容自动猜测。
  --platform 省略时默认 oldmmd（最严格）。

退出码: 0=无错误(可能有警告)  1=有错误  2=用法/读取错误
输出: 文本报告，[ERROR]/[WARN]/[OK] 前缀，便于人和AI阅读。
"""
import sys
import json
import argparse
import re

# Windows 控制台默认 GBK，强制 UTF-8 输出，避免中文报告乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass  # 旧 Python 或已重定向时忽略

ERRORS = []
WARNS = []
OKS = []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNS.append(msg)


def ok(msg):
    OKS.append(msg)


def read_raw_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def check_bom(rawb):
    if rawb[:3] == b"\xef\xbb\xbf":
        err("文件带 UTF-8 BOM 头，部分平台导入会报 json 异常。请用无 BOM 的 UTF-8 保存。")
        return True
    ok("无 BOM")
    return False


def load_json(rawb):
    """返回 (obj, 已去BOM文本) 或 (None, 文本)。失败时记录错误。"""
    txt = rawb.decode("utf-8-sig", errors="replace")
    try:
        obj = json.loads(txt)
        ok("JSON 语法合法")
        return obj, txt
    except json.JSONDecodeError as e:
        # 给出常见原因提示
        hint = ""
        line = txt.splitlines()[e.lineno - 1] if 0 < e.lineno <= len(txt.splitlines()) else ""
        if "control character" in str(e).lower():
            hint = "（字符串内有未转义的真实换行/控制符——大段HTML的换行必须写成 \\n）"
        elif "delimiter" in str(e).lower() or "expecting" in str(e).lower():
            hint = "（可能是字符串内双引号未转义为 \\\"，或缺逗号/括号）"
        err("JSON 语法非法: line %d col %d: %s %s" % (e.lineno, e.colno, e.msg, hint))
        if line:
            err("  出错行: %s" % line[:120])
        return None, txt
    return None, txt


# ============ 平台红线检查（作用于解析后的 HTML/JS 字符串） ============

def check_platform_redlines(s, platform, where):
    """s: 待检字符串（如 replaceString 解析后的值）。where: 来源描述。"""
    # <script> 标签
    if re.search(r"<script\b", s, re.I):
        if platform == "oldmmd":
            err("%s 含 <script> 标签——旧版MMD会剥离，JS不执行。改用 img onerror 点火器。" % where)
        elif platform == "mmd":
            warn("%s 含 <script>——当前MMD支持但未充分验证，建议保留 onerror 回退方案。" % where)
        # st 不报

    # ES6 语法（仅 MMD 系平台关心）
    if platform in ("oldmmd", "mmd"):
        es6 = []
        if re.search(r"=>", s):
            es6.append("箭头函数(=>)")
        if re.search(r"\blet\b", s):
            es6.append("let")
        if re.search(r"\bconst\b", s):
            es6.append("const")
        if "`" in s:
            es6.append("模板字符串(反引号)")
        if re.search(r"\.\.\.", s) and re.search(r"\[\s*\.\.\.|\(\s*\.\.\.", s):
            es6.append("展开运算符")
        if re.search(r"\?\.", s):
            es6.append("可选链(?.)")
        if es6:
            lvl = err if platform == "oldmmd" else warn
            lvl("%s 含 ES6+ 语法: %s——%s。" % (
                where, "、".join(es6),
                "旧版MMD会从该处截断，后续代码丢失" if platform == "oldmmd" else "当前MMD执行环境未验证，建议ES5"))
        else:
            ok("%s 全 ES5（无箭头函数/let/const/模板字符串等）" % where)

    # 纯DOM API：innerHTML 拼接 / cssText
    if re.search(r"\.innerHTML\s*=", s):
        (err if platform == "oldmmd" else warn)("%s 用 innerHTML 赋值——易被平台破坏，改用 createElement/textContent。" % where)
    if re.search(r"\.cssText\s*=", s):
        (err if platform == "oldmmd" else warn)("%s 用 style.cssText——旧版MMD报 Unexpected identifier，改用预定义CSS类。" % where)

    # alert
    if re.search(r"\balert\s*\(", s):
        warn("%s 含 alert()——平台静默阻止且中断执行，移除。" % where)


def check_double_escape(s, where):
    """检查解析后的 HTML 是否残留多余反斜杠（双重转义典型症状）。"""
    bs = s.count("\\")
    if bs == 0:
        ok("%s 无残留反斜杠（无双重转义）" % where)
        return
    # 反斜杠后紧跟引号 = 典型的属性引号被多转义
    quote_bs = len(re.findall(r'\\[\"\']', s))
    if quote_bs > 5:
        err("%s 解析后含 %d 处 \\\" 或 \\' ——几乎确定是双重转义（HTML属性引号被转义两次）。"
            "源HTML喂给json.dumps前需先 .replace(chr(92)+chr(34), chr(34)) 还原。" % (where, quote_bs))
    elif bs > 0:
        warn("%s 解析后含 %d 个反斜杠——若为纯美化HTML通常应为0，请确认是否JS正则确需反斜杠。" % (where, bs))


def check_interactive_event_newlines(s, where, platform):
    """检查内联事件处理器（onclick/onerror）内是否有裸换行——旧版MMD会因CSP破坏。"""
    if platform not in ("oldmmd", "mmd"):
        return
    bad = re.findall(r'on\w+\s*=\s*"[^"]*\n[^"]*"', s)
    if bad:
        (err if platform == "oldmmd" else warn)(
            "%s 有 %d 个内联事件处理器(onclick/onerror)含裸换行——旧版MMD的CSP会破坏多行JS，必须单行。" % (where, len(bad)))
    else:
        ok("%s 内联事件处理器均单行" % where)


# ============ 类型专项校验 ============

def looks_like(obj):
    """猜测 JSON 类型。"""
    if isinstance(obj, dict):
        if "regex_scripts" in obj and "statusbar" in obj:
            return "regex"  # MMD 导入 json
        if "spec" in obj and "data" in obj:
            return "card"
        if "entries" in obj and isinstance(obj.get("entries"), dict):
            return "worldbook"
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "findRegex" in obj[0]:
        return "regex"  # 本地酒馆正则数组
    return None


def validate_regex(obj, platform):
    """MMD 导入json(4字段) 或 本地酒馆正则数组。"""
    scripts = []
    if isinstance(obj, dict) and "regex_scripts" in obj:
        # MMD 4字段格式
        for k in ("pageDepth", "statusbar", "beginning", "regex_scripts"):
            if k not in obj:
                warn("MMD 导入json 缺字段 %s" % k)
        scripts = obj.get("regex_scripts", [])
        sb = obj.get("statusbar", "")
        ok("识别为 MMD 导入json 格式（%d 条正则）" % len(scripts))
        if isinstance(sb, str) and sb:
            ok("statusbar 触发标记: %s" % sb)
    elif isinstance(obj, list):
        scripts = obj
        ok("识别为 本地酒馆正则数组（%d 条）" % len(scripts))
    else:
        err("无法识别的正则结构")
        return

    if platform in ("oldmmd", "mmd"):
        if len(scripts) > 30:
            err("正则条数 %d > 30，超出MMD上限。" % len(scripts))
        else:
            ok("正则条数 %d ≤ 30" % len(scripts))

    for i, sc in enumerate(scripts):
        if not isinstance(sc, dict):
            err("第%d条正则不是对象" % i)
            continue
        name = sc.get("scriptName", sc.get("name", "#%d" % i))
        fr = sc.get("findRegex", "")
        rs = sc.get("replaceString", "")
        tag = "正则[%s]" % name

        if platform in ("oldmmd", "mmd"):
            if len(fr) > 1000:
                err("%s findRegex %d 字符 > 1000" % (tag, len(fr)))
            if len(rs) > 20000:
                err("%s replaceString %d 字符 > 20000" % (tag, len(rs)))
            else:
                ok("%s replaceString %d 字符 ≤ 20000" % (tag, len(rs)))

        # 对 replaceString 内容做红线 + 转义 + 单行检查
        if rs:
            check_platform_redlines(rs, platform, tag)
            check_double_escape(rs, tag)
            check_interactive_event_newlines(rs, tag, platform)
            # 容器事件冒泡（仅含交互的美化/状态栏需要）
            if platform in ("oldmmd", "mmd") and re.search(r"onclick=", rs):
                if "stopPropagation" not in rs:
                    warn("%s 有 onclick 但未见 stopPropagation——交互模块最外层应加 onclick=\"event.stopPropagation()\" 防事件冒泡。" % tag)


def validate_card(obj, platform):
    spec = obj.get("spec", "")
    sv = obj.get("spec_version", "")
    ok("角色卡 spec=%s spec_version=%s" % (spec, sv))
    data = obj.get("data", {})

    if platform in ("oldmmd", "mmd"):
        if spec != "chara_card_v2":
            err("MMD 仅识别 chara_card_v2，当前 spec=%s。必须输出 v2（spec=\"chara_card_v2\", spec_version=\"2.0\", 删除 data.group_only_greetings）。" % spec)
        else:
            ok("v2 规范 spec 正确")
        if "group_only_greetings" in data:
            err("MMD v2 卡不应含 data.group_only_greetings（v3 专有字段），请删除。")
        else:
            ok("无 v3 专有字段 group_only_greetings")
    else:
        if spec not in ("chara_card_v2", "chara_card_v3"):
            warn("spec=%s 非标准 v2/v3" % spec)

    # 顶层与 data 同步
    for k in ("name", "first_mes", "description", "personality", "scenario", "mes_example"):
        if k in obj and k in data and obj[k] != data[k]:
            warn("顶层 %s 与 data.%s 不一致（酒馆可能行为不一）" % (k, k))

    # 卡内世界书条目里如带 HTML（美化/状态栏），也查红线
    cb = data.get("character_book", {})
    for e in cb.get("entries", []) if isinstance(cb, dict) else []:
        c = e.get("content", "")
        if "<style" in c or "onerror=" in c or "onclick=" in c:
            check_platform_redlines(c, platform, "卡内条目[%s]" % e.get("comment", "?"))
            check_interactive_event_newlines(c, "卡内条目[%s]" % e.get("comment", "?"), platform)


def validate_worldbook(obj, platform):
    entries = obj.get("entries", {})
    if not isinstance(entries, dict):
        err("独立世界书 entries 应为对象（uid字符串作键），当前为 %s" % type(entries).__name__)
        return
    ok("独立世界书：%d 个条目" % len(entries))
    for uid, e in entries.items():
        if not isinstance(e, dict):
            err("条目 %s 不是对象" % uid)
            continue
        tag = "条目[%s]" % e.get("comment", uid)
        # 绿灯必须有 key
        if e.get("constant") is False and not e.get("key"):
            warn("%s 是绿灯(constant=false)但 key 为空——永不触发。" % tag)
        # 蓝灯 selective 约定
        if e.get("constant") is True and e.get("selective") is True:
            warn("%s 蓝灯(constant=true)却 selective=true，通常蓝灯 selective=false。" % tag)
        c = e.get("content", "")
        if "<style" in c or "onerror=" in c:
            check_platform_redlines(c, platform, tag)


# ============ 主流程 ============

def main():
    p = argparse.ArgumentParser(description="tavern-mmd 静态审核")
    p.add_argument("file", help="待审核的 json 文件")
    p.add_argument("--type", choices=["regex", "card", "worldbook"], help="不填则自动猜测")
    p.add_argument("--platform", choices=["oldmmd", "mmd", "st"], default="oldmmd",
                   help="目标平台，默认 oldmmd（最严格）")
    args = p.parse_args()

    try:
        rawb = read_raw_bytes(args.file)
    except OSError as e:
        print("[ERROR] 无法读取文件: %s" % e)
        sys.exit(2)

    print("=== tavern-mmd 审核报告 ===")
    print("文件: %s  平台: %s" % (args.file, args.platform))
    print()

    check_bom(rawb)
    obj, txt = load_json(rawb)

    if obj is not None:
        t = args.type or looks_like(obj)
        if t is None:
            warn("无法自动判断类型，请用 --type 指定。已做通用JSON检查。")
        elif t == "regex":
            validate_regex(obj, args.platform)
        elif t == "card":
            validate_card(obj, args.platform)
        elif t == "worldbook":
            validate_worldbook(obj, args.platform)

    # 输出
    for m in OKS:
        print("[OK]   " + m)
    for m in WARNS:
        print("[WARN] " + m)
    for m in ERRORS:
        print("[ERROR] " + m)
    print()
    print("结果: %d 错误, %d 警告, %d 通过项" % (len(ERRORS), len(WARNS), len(OKS)))
    sys.exit(1 if ERRORS else 0)


if __name__ == "__main__":
    main()
