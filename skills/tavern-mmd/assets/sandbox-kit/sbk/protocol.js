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
     <状态> 这种中文标签会被【整个删掉】（文字保留、标签消失）。正则管线跑在剥壳【之前】，
     所以正则路径还看得见 <状态>；但凡是从气泡 textContent 读标记的路径（hydrate 的兜底解析
     即其一）拿到的都是剥壳后的裸行，标记已经没了，解析必然失败。→ 方括号形态才是全链路安全的，
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
     统一 /…/ slash 形态（约定，非硬性）：裸字面量实机也生效（卡 64304 A/B 2026-08-30，
     与 worker 源码一致），统一 slash 为跨平台一致；生成器对裸字面量出 WARN 不出 ERROR。
     §5.2：标记本身至少 6 个字符 → 绝不匹配空串，不会触发 empty-match 把整条规则撤销。
     cap=true 时整块进 $1，配合 replaceString 包一层 .sbk-snap--raw 壳给 hydrate() 升级
     成气泡内状态面板（modes.status）。 */
  function pattern(cap) { return '/' + src(NAME, !!cap) + '/g'; }

  /* ---------- 归一化（容错第一层） ----------
     模型中英标点混用是常态（「好感：熙宁＝61，阿澈=25」）。先统一成半角，
     后面所有判定就只写一套分支，不用到处 [,，] [:：]。全角数字一并折半角。 */
  /* ｜(U+FF5C) 一并折半角：| 是 2.0 §3.2 的【主分割符】（level/kvlist 都靠它），
     模型在中文输入法下吐出全角竖线是常态，不归一化就会让整个结构判定失效。 */
  var FW = { '：': ':', '，': ',', '、': ',', '＝': '=', '／': '/', '％': '%', '－': '-', '｜': '|', '\u3000': ' ' };
  function norm(s) {
    return String(s)
      .replace(/[：，、＝／％－｜\u3000]/g, function (c) { return FW[c]; })
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

  /* ---------- 值的内部结构（2.0 §3.2） ----------
     1.0 对 | 与 : 零语义，凡带内部结构的值一律退化成 text（旧资产盘点 E.2）。
     这里补四个结构解析器。分隔符分层沿用旧资产协议（盘点 D.4）：
       主分割 |    列表项 , （或空格，仅 stats）    标签值 :    次级说明 :第三段
     四个函数的共同纪律：**结构不完整就返回 null**，由调用方降级到 text。
     宁可显示成一行文本，也不能因为模型写歪一个字段就渲染出畸形控件（容错优先）。 */

  // a/b 双段纯数字。level 的经验段与 bar 复用同一判定，避免两处写法漂移。
  function bars(s) {
    var a = String(s).split('/');
    if (a.length !== 2) return null;
    var x = num(a[0]), y = num(a[1]);
    return x === null || y === null ? null : { value: x, max: y };
  }

  /* 键:值[:说明] 列表。sep 为项分隔符，min 为最少项数。
     要求【每一项都合规】：混杂一项不合规就整体返回 null。半解析的网格比纯文本更难读，
     且会让做卡人以为协议支持某种写法（实际只是碰巧过了一半）。 */
  function pairs(items, min) {
    var out = [], i, t, ci, k, v, note, ss;
    if (!items || items.length < (min || 2)) return null;
    for (i = 0; i < items.length; i++) {
      t = String(items[i]).trim();
      if (!t) return null;
      ci = t.indexOf(':');
      if (ci <= 0 || ci === t.length - 1) return null;   // 无冒号 / 冒号在首尾 → 不是键值项
      k = t.slice(0, ci).trim();
      ss = t.slice(ci + 1);
      // 第三段是「成因/说明」，折进 tooltip（盘点 B.7/B.8）。只切【第一个】冒号，说明里可含冒号。
      ci = ss.indexOf(':');
      if (ci >= 0) { v = ss.slice(0, ci).trim(); note = ss.slice(ci + 1).trim(); }
      else { v = ss.trim(); note = ''; }
      if (!k || !v) return null;
      out.push({ name: k, value: v, note: note });
      if (out.length >= MAXN) break;                     // §5.2 预算：条目数封顶
    }
    return out.length ? out : null;
  }

  // path：`内城-东市-药铺`。段内禁 | : = 交给别的类型；禁全数字段防误吃日期 2026-08-26。
  function toPath(t, min) {
    if (/[|:=]/.test(t)) return null;
    var a = t.split('-'), out = [], i, s, allNum = true;
    if (a.length < (min || 2)) return null;
    for (i = 0; i < a.length; i++) {
      s = a[i].trim();
      if (!s) return null;                               // 空段（`a--b`、首尾横线）→ 不是路径
      if (num(s) === null) allNum = false;
      out.push(s);
      if (out.length >= MAXN) break;
    }
    // 全段皆数字 = 日期/编号（2026-08-26、1-2-3），不是空间层级
    return allNum ? null : out;
  }

  // level：`炼气三层|120/300`。右段必须是 a/b 纯数字，否则不是等级（`3/3|暂无` 会落 text）。
  function toLevel(t, loose) {
    var i = t.indexOf('|');
    if (i < 0) return loose ? { name: t, value: null, max: null } : null;
    var name = t.slice(0, i).trim(), b = bars(t.slice(i + 1).trim());
    if (!name) return null;
    if (!b) return loose ? { name: name, value: null, max: null } : null;
    return { name: name, value: b.value, max: b.max };
  }

  // stats：`攻:12 防:8 敏:15`，逗号或空白分项（旧资产两种写法都有，盘点 B.7）。
  function toStats(t, min) {
    if (t.indexOf('|') >= 0) return null;                // | 属 level/kvlist 的地盘
    var a = split(t);                                    // 先逗号
    if (a.length < 2) a = t.split(/\s+/);                // 单项再按空白切
    return pairs(a, min);
  }

  // kvlist：`头:斗笠|身:麻衣`，| 分项，值可带 `:说明` 折进 tooltip。
  function toKvlist(t, min) {
    if (t.indexOf('|') < 0 && (min || 2) > 1) return null;
    return pairs(t.split('|'), min);
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
    var sl = bars(t);
    if (sl) return { type: 'bar', value: sl.value, max: sl.max, raw: t };
    /* ---- 2.0 §3.2 结构类型。位置是【bar 之后、entities/tags 之前】，这个次序是刻意的：
       · 在 bar 之后 → `84/100` 仍是 bar，`72%`/纯数字更早就返回了，既有五类型零影响。
       · 在 entities/tags 之前 → `攻:12, 防:8` 若先过 tags 就会被逗号切成两个纯文本 chip，
         `键:值` 结构永久丢失。而 entities 认的是 `名=数`（等号），与 `键:值` 不冲突，
         提前 stats 不会抢走 `苏九=61, 阿澈=25`。
       · level 在 kvlist 之前 → 两者都用 |，靠「右段是否 a/b 纯数字」区分，
         level 判定更严（必须数字），先严后宽才不会互抢。 */
    var lv = toLevel(t);
    if (lv) return { type: 'level', value: lv, raw: t };
    var kv = toKvlist(t);
    if (kv) return { type: 'kvlist', value: kv, raw: t };
    var stt = toStats(t);
    if (stt) return { type: 'stats', value: stt, raw: t };
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
    /* path 排在 tags 之后、text 之前：`内城-东市-药铺` 无逗号故走不到 tags，
       而把它放这里能保证任何带逗号的值（已被 tags/entities 吃掉）都不会被误判成路径。 */
    var ph = toPath(t);
    if (ph) return { type: 'path', value: ph, raw: t };
    return { type: 'text', value: t, raw: t };
  }

  /* ---------- 强制类型的值适配（协议说明 §3.1「强制 type 覆写时基座会重新适配值」） ----------
     hud.js 的 fit() 调它。与 value() 共用同一批解析器 —— 推断与强制两条路径【同一真相源】，
     否则「自动认出来的 stats」和「schema 写 type:'stats' 的 stats」会有两套行为。
     loose=1：强制时放宽最少项数到 1，并允许 level 只有名字没有经验条
     （做卡人明确写了 type，就该尽力渲染成那个控件，而不是因为「只有一项」退回文本）。 */
  function struct(type, raw) {
    var t = cut(norm(raw === null || raw === undefined ? '' : raw));
    if (!t) return null;
    if (type === 'path') return toPath(t, 1);
    if (type === 'level') return toLevel(t, 1);
    if (type === 'stats') return toStats(t, 1);
    if (type === 'kvlist') return toKvlist(t, 1);
    return null;
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
     入参：AI 正文。两个来源：正则捕获组（气泡面板走这条），或 message:done 载荷/气泡
     textContent（功能栏精简条 pinned 与自定义脚本走这条，注意已被剥壳，见上文块标记一节）。
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
     §5.4 剥壳发生在正则管线【之后】，所以场景规则的 replaceString 里若再吐出 <状态>，
     它会被当非白名单标签删掉，只剩裸行 → parse 认不出块。方括号形态不受影响，
     但做卡人未必这么写，故 hydrate 拿裸块体时用这个补标记再解析，两种写法都能活。 */
  function wrap(body) { return '[' + NAME + ']\n' + String(body) + '\n[/' + NAME + ']'; }

  parse.wrap = wrap;
  parse.config = config;      // 改块标记：SBK.parse.config({block:'状态'})
  parse.pattern = pattern;    // 推荐匹配式（统一 slash 形态，约定；裸字面量实机也生效），供 WP-4 与做卡人取用
  parse.value = value;        // 单值分类器，供自定义控件复用
  parse.struct = struct;      // 结构类型的强制适配器（path/level/stats/kvlist），供 hud.js 的 fit() 复用
  SBK.parse = parse;          // 覆写 core.js 里那个「未装载」占位实现
  SBK.log('protocol ready, block=' + NAME);
})(typeof window !== 'undefined' ? window : globalThis);
