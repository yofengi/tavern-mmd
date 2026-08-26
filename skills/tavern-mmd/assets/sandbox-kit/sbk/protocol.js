/* SBK protocol —— 数据协议解析器。依据：资料/基座事实卡.md、plan.md §2.3
   经典脚本 IIFE：§3 内联脚本走 (0,eval)，import 必报错。零外部依赖（§2 connect-src 'self'）。 */
(function (W) {
  'use strict';
  var SBK = W.SBK;
  if (!SBK || !SBK.claim) {
    (W.console && W.console.warn) && W.console.warn('[SBK] protocol.js loaded before core.js');
    return;
  }
  if (!SBK.claim('protocol')) return;   // 预览重跑幂等（§3/§4.2 无 off/once）

  /* 三个上限都是为 §5.2 服务：单条规则输出预算 max(262144, 输入长度×4)，超限【整条规则回滚】，
     页面上完全不生效只留告警。模型偶尔会吐出巨长一行，从解析源头就掐掉最省事。 */
  var MAXV = 200;   // 单值字符数
  var MAXN = 24;    // 标签/实体条目数
  var MAXK = 40;    // 键名字符数

  /* ---------- 块标记 ----------
     默认 <状态>…</状态>（plan.md §2.3），同时认 [状态] 与 【状态】三种括号族，可混用。
     🚨 §5.4：worker 用 /<\/?([\u4e00-\u9fa5a-zA-Z0-9_]+)(\s+[^>]*)?>/g 剥非白名单标签，
     <状态> 这种中文标签会被【整个删掉】。正则管线跑在剥壳之前，所以模式 B 的正则看得见
     <状态>；但 HUD 兜底从气泡 textContent 读时标记已经没了。→ 方括号形态才是全链路安全的，
     协议说明里因此推荐 [状态]。这里两种都认，做卡人怎么写都不会解析失败。 */
  var OB = '[<\\[【]';
  var CB = '[>\\]】]';
  var NAME = '状态';

  function esc(s) { return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function src(name, cap) {
    var n = esc(name);
    // 块内换行必须 [\s\S]*?：用 .*? 会在第一个换行处断掉，整块只吃到第一行
    var b = OB + '\\s*' + n + '\\s*' + CB + '([\\s\\S]*?)' + OB + '\\s*[\\/／]\\s*' + n + '\\s*' + CB;
    return cap ? '(' + b + ')' : b;
  }
  // g 标记的 RegExp 带 lastIndex 状态，跨调用共享会漏匹配 → 每次现造，绝不缓存实例
  function block(name) { return new RegExp(src(name, false), 'g'); }
  function opener(name) { return new RegExp(OB + '\\s*' + esc(name) + '\\s*' + CB, 'g'); }

  function config(o) {
    if (o && typeof o === 'object') {
      var n = o.block || o.name;
      if (typeof n === 'string' && n) NAME = n.replace(/^[<\[【\/]+|[>\]】]+$/g, '') || NAME;
    }
    return { block: NAME, pattern: pattern(true) };
  }

  /* 给 WP-4 生成器与做卡人用的推荐匹配式。
     硬约束 21：一律 /…/ slash 形态（实机裸字面量 {{probe}} 不生效，加斜杠立即生效）。
     §5.2：标记本身至少 6 个字符 → 绝不匹配空串，不会触发 empty-match 把整条规则撤销。
     cap=true 时整块进 $1，配合 replaceString 包一层 .sbk-snap--raw 壳给 JS 升级（模式 B）。 */
  function pattern(cap) { return '/' + src(NAME, !!cap) + '/g'; }

  /* ---------- 归一化（容错第一层） ----------
     模型中英标点混用是常态（「好感：熙宁＝61，阿澈=25」）。先统一成半角，
     后面所有判定就只写一套分支，不用到处 [,，] [:：]。全角数字一并折半角。 */
  var FW = { '：': ':', '，': ',', '、': ',', '＝': '=', '／': '/', '％': '%', '－': '-', '\u3000': ' ' };
  function norm(s) {
    return String(s)
      .replace(/[：，、＝／％－\u3000]/g, function (c) { return FW[c]; })
      .replace(/[\uff10-\uff19]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0xfee0); });
  }

  function num(s) {
    var t = String(s).trim();
    if (!/^[+-]?(\d+\.?\d*|\.\d+)$/.test(t)) return null;
    var v = parseFloat(t);
    return isFinite(v) ? v : null;
  }
  function cut(s) {
    var t = String(s).trim();
    if (t.length <= MAXV) return t;
    SBK.warn('protocol: value truncated to ' + MAXV + ' chars (§5.2 output budget)');
    return t.slice(0, MAXV);
  }
  function split(s) {
    var out = [], a = String(s).split(','), i, t;
    for (i = 0; i < a.length; i++) { t = a[i].trim(); if (t) out.push(t); }
    if (out.length > MAXN) { SBK.warn('protocol: list clipped to ' + MAXN); out = out.slice(0, MAXN); }
    return out;
  }

  /* ---------- 值分类 ----------
     判定顺序即优先级。每一档都要求「结构完整」才认，否则一路降级到 text —— 宁可显示成
     文本，也不能因为模型写歪一个字段就让整块解析失败（容错优先，plan.md §2.3）。 */
  function value(raw) {
    var t = cut(norm(raw)), i, m;
    if (!t) return { type: 'text', value: '', raw: t };
    var n = num(t);
    if (n !== null) return { type: 'num', value: n, raw: t };
    var pc = /^([+-]?[\d.]+)\s*%$/.exec(t);
    if (pc && num(pc[1]) !== null) return { type: 'bar', value: num(pc[1]), max: 100, unit: '%', raw: t };
    // a/b 进度条：必须【恰好两段且两段皆纯数字】。
    // 「北门/东街/西市」三段、「12/未知」右侧非数字 → 都落回文本，不会被误判成进度条。
    var sl = t.split('/');
    if (sl.length === 2) {
      var a = num(sl[0]), b = num(sl[1]);
      if (a !== null && b !== null) return { type: 'bar', value: a, max: b, raw: t };
    }
    // 名=数 多实体表：右侧必须是数字。「找到钥匙=打开门」右侧非数字 → 降级为标签组。
    var items = split(t), ent = [], plain = 0, v;
    for (i = 0; i < items.length; i++) {
      m = /^([\s\S]+?)\s*=\s*([\s\S]+)$/.exec(items[i]);
      v = m ? num(m[2]) : null;
      if (m && v !== null) ent.push({ name: m[1].trim(), value: v });
      else plain++;
    }
    if (ent.length && ent.length >= plain) return { type: 'entities', value: ent, raw: t };
    if (items.length > 1) return { type: 'tags', value: items, raw: t };
    return { type: 'text', value: t, raw: t };
  }

  /* ---------- 逐行解析 ----------
     只在【第一个】冒号处切分：值里含冒号（「时间: 12:30」）不会把 30 丢掉。
     单行失败 = 跳过并计数，绝不冒泡成整块失败（容错优先）。 */
  function lines(body, out, order, bad) {
    var raw = String(body).split(/\r?\n/), i, ln, ci, k, fv;
    for (i = 0; i < raw.length; i++) {
      ln = norm(raw[i]).trim();
      if (!ln) continue;
      // 允许模型写 markdown 列表前缀（- 血量: 72/100），常见漂移
      ln = ln.replace(/^[-*+•]\s+/, '');
      ci = ln.indexOf(':');
      if (ci <= 0) { bad.push(raw[i].trim()); continue; }   // 无冒号或冒号在行首 → 跳过
      k = ln.slice(0, ci).trim().replace(/^[*_`#]+|[*_`#]+$/g, '').trim();
      if (!k) { bad.push(raw[i].trim()); continue; }
      if (k.length > MAXK) k = k.slice(0, MAXK);
      try { fv = value(ln.slice(ci + 1)); }
      catch (e) { bad.push(raw[i].trim()); continue; }      // 分类器万一抛错也只丢这一行
      // 重复键：后者覆盖前者，order 里不重复出现（保持首次出现的位置）
      if (!Object.prototype.hasOwnProperty.call(out, k)) order.push(k);
      out[k] = fv;
    }
  }

  /* ---------- SBK.parse ----------
     入参：AI 正文（模式 A 从 message:done 载荷/气泡文本取，模式 B 从正则捕获组取）。
     返回：{ state, order, cleanedText, skipped } 或 null（无状态块）。 */
  function parse(text) {
    if (typeof text !== 'string' || !text) return null;
    var re = block(NAME), bodies = [], m;
    while ((m = re.exec(text)) !== null) {
      bodies.push(m[1]);
      if (m.index === re.lastIndex) re.lastIndex++;   // 防御：理论上不会零宽，但死循环代价太大
    }
    var cleaned;
    if (bodies.length) {
      cleaned = text.replace(block(NAME), '');
    } else {
      // 兜底：模型漏了闭合标记。取开标记之后的全部内容，不然整轮状态白丢。
      var op = opener(NAME), o = op.exec(text);
      if (!o) return null;                            // 真的没有状态块 → null，契约要求
      SBK.warn('protocol: closing tag missing, parsing to end of text');
      bodies.push(text.slice(o.index + o[0].length));
      cleaned = text.slice(0, o.index);
    }
    var state = {}, order = [], bad = [], i;
    for (i = 0; i < bodies.length; i++) lines(bodies[i], state, order, bad);
    if (bad.length) SBK.warn('protocol: ' + bad.length + ' line(s) skipped', bad.slice(0, 3).join(' | '));
    // 收尾空行压成一个，避免正文末尾留一大片空白（气泡有 white-space:pre-line，§7.3）
    cleaned = cleaned.replace(/\n{3,}/g, '\n\n').replace(/^\s+|\s+$/g, '');
    return { state: state, order: order, cleanedText: cleaned, skipped: bad };
  }

  /* 给块体补回标记。用途见 hud.js 的 hydrate：
     §5.4 剥壳发生在正则管线【之后】，所以模式 B 的 replaceString 里若再吐出 <状态>，
     它会被当非白名单标签删掉，只剩裸行 → parse 认不出块。方括号形态不受影响，
     但做卡人未必这么写，故 hydrate 拿裸块体时用这个补标记再解析，两种写法都能活。 */
  function wrap(body) { return '[' + NAME + ']\n' + String(body) + '\n[/' + NAME + ']'; }

  parse.wrap = wrap;
  parse.config = config;      // 改块标记：SBK.parse.config({block:'状态'})
  parse.pattern = pattern;    // 推荐匹配式（slash 形态，硬约束 21），供 WP-4 与做卡人取用
  parse.value = value;        // 单值分类器，供自定义控件复用
  SBK.parse = parse;          // 覆写 core.js 里那个「未装载」占位实现
  SBK.log('protocol ready, block=' + NAME);
})(typeof window !== 'undefined' ? window : globalThis);
