/* SBK 运行时回归测试（WP-1）。零依赖：自带 fake DOM 与 fake sdk，只用 node 内置模块。
   跑法：node test_sbk_runtime.mjs        （在 assets/sandbox-kit/ 下）
   覆盖：深副本 + 切会话清态 / stage 挂载前 open→close|destroy / typed entities 无 NaN /
        新三类型字符串输出 / 未知 type 告警 / hostId 非法回落 / schema.persist 删键。

   为什么自造 DOM 而不上 jsdom：
     ① 仓库 Python 侧测试零依赖，Node 侧引入 npm 依赖会让「clone 完就能跑全部测试」不再成立；
     ② 被测代码只用了 DOM 的一个很小子集（createElement/appendChild/querySelectorAll/…），
        自造 120 行足够，且【显式写出被依赖的 DOM 行为】本身就是一份契约文档；
     ③ jsdom 的 :has()/focus-visible 等实现与真实内核也不一致，装了也不能当视觉真值。
   ⚠ 因此本文件【不是】渲染正确性的真值来源：它验证的是「数据边界与生命周期」这类
     纯逻辑不变量。视觉/净化/事件顺序仍归本地仿真页与实机（main.md 的验证原则）。 */
'use strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const SBK_DIR = join(HERE, 'sbk');

/* ---------------- 迷你断言器 ---------------- */
let pass = 0;
const fails = [];
function ok(cond, name, extra) {
  if (cond) { pass++; return; }
  fails.push(name + (extra === undefined ? '' : '  ← ' + extra));
}
function eq(a, b, name) {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  ok(sa === sb, name, 'got ' + sa + ' want ' + sb);
}
function group(name) { return (t, ...r) => ok(t, name + ': ' + r[0], r[1]); }

/* ---------------- fake DOM ----------------
   只实现被测代码真正调用到的部分。每个方法都对应源码里的一处调用点，
   不多实现 —— 多实现的部分等于凭空承诺了平台行为，反而会掩盖真实约束。 */
class FakeNode {
  constructor(tag, ns) {
    this.nodeType = 1;
    this.nodeName = String(tag).toUpperCase();
    this.tagName = this.nodeName;
    this.namespaceURI = ns || null;
    this.childNodes = [];
    this.parentNode = null;
    this.attributes = {};
    this.style = makeStyle();
    this._text = null;
    this.listeners = {};
    this.disabled = false;
  }
  get id() { return this.attributes.id || ''; }
  set id(v) { this.attributes.id = String(v); }
  get firstChild() { return this.childNodes[0] || null; }
  get className() { return this.attributes['class'] || ''; }
  get textContent() {
    if (this._text !== null) return this._text;
    return this.childNodes.map((c) => c.textContent).join('');
  }
  set textContent(v) { this._text = String(v); this.childNodes = []; }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === 'disabled') this.disabled = true;
  }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null; }
  appendChild(n) {
    if (n.parentNode) n.parentNode.removeChild(n);   // 移动语义：adopt() 依赖它
    n.parentNode = this;
    this.childNodes.push(n);
    return n;
  }
  removeChild(n) {
    const i = this.childNodes.indexOf(n);
    if (i >= 0) { this.childNodes.splice(i, 1); n.parentNode = null; }
    return n;
  }
  contains(n) {
    if (n === this) return true;
    return this.childNodes.some((c) => c.contains && c.contains(n));
  }
  addEventListener(t, fn) { (this.listeners[t] || (this.listeners[t] = [])).push(fn); }
  removeEventListener(t, fn) {
    const a = this.listeners[t]; if (!a) return;
    const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1);
  }
  // 事件派发：只做「按类型调本节点的监听」，不模拟冒泡（被测代码全部 stopPropagation，用不到）
  fire(t, ev) {
    const a = (this.listeners[t] || []).slice();
    const e = Object.assign({ type: t, stopPropagation() {}, preventDefault() {} }, ev || {});
    for (const fn of a) fn.call(this, e);
    return e;
  }
  focus() { ownerDoc.activeElement = this; }
  getBoundingClientRect() { return { left: 0, top: 0, right: 100, bottom: 40, width: 100, height: 40 }; }
  get offsetWidth() { return 100; }
  get offsetHeight() { return 40; }
  _walk(out) {
    for (const c of this.childNodes) { out.push(c); if (c._walk) c._walk(out); }
    return out;
  }
  // 只支持被测代码用到的选择器形态：'[id]' / '[attr="v"]' / '.cls' / 'tag' / 逗号并列
  querySelectorAll(sel) { return this._walk([]).filter((n) => matches(n, sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
function makeStyle() {
  const s = {};
  s.setProperty = (k, v) => { s[k] = v; };
  return s;
}
function matches(n, sel) {
  return String(sel).split(',').some((one) => matchOne(n, one.trim()));
}
function matchOne(n, sel) {
  if (!sel) return false;
  let m = /^\[([A-Za-z-]+)="([^"]*)"\]$/.exec(sel);
  if (m) return n.getAttribute(m[1]) === m[2];
  m = /^\[([A-Za-z-]+)\]$/.exec(sel);
  if (m) return n.getAttribute(m[1]) !== null;
  if (sel.startsWith('.')) return (' ' + n.className + ' ').includes(' ' + sel.slice(1) + ' ');
  m = /^([a-z]+)\[([A-Za-z-]+)\]$/.exec(sel);
  if (m) return n.nodeName === m[1].toUpperCase() && n.getAttribute(m[2]) !== null;
  if (/^[a-z]+$/.test(sel)) return n.nodeName === sel.toUpperCase();
  return false;
}
let ownerDoc = null;
function makeDoc() {
  const d = new FakeNode('#document');
  d.nodeType = 9;
  d.createElement = (t) => new FakeNode(t);
  d.createElementNS = (ns, t) => new FakeNode(t, ns);
  d.createTextNode = (t) => { const n = new FakeNode('#text'); n.nodeType = 3; n._text = String(t); return n; };
  d.head = new FakeNode('head');
  d.documentElement = new FakeNode('html');
  d.body = new FakeNode('body');
  d.appendChild(d.head);
  d.appendChild(d.body);
  d.activeElement = null;
  ownerDoc = d;
  return d;
}
/* 平台 DOM 骨架（§9 实测宿主链）：root 不是 body 的直接子节点 */
function buildPlatformDom(d, { statusbar = true } = {}) {
  const outer = new FakeNode('div');
  d.body.appendChild(outer);
  const root = new FakeNode('div');
  root.setAttribute('data-chat', 'root');
  outer.appendChild(root);
  if (statusbar) {
    const sb = new FakeNode('div');
    sb.setAttribute('data-slot', 'statusbar');
    root.appendChild(sb);
  }
  for (const side of ['left', 'right']) {
    const s = new FakeNode('div');
    s.setAttribute('data-slot', side);
    root.appendChild(s);
  }
  return root;
}

/* ---------------- fake sdk ---------------- */
function makeSdk(opts = {}) {
  const handlers = {};
  const logs = [];
  const saveData = Object.assign({}, opts.saveData || {});
  const saveCalls = [];
  const stage = {
    _visible: false,
    _el: new FakeNode('div'),
    opens: 0,
    closes: 0,
    open(mode) { stage.opens++; stage._visible = true; stage._mode = mode; },
    close() { stage.closes++; stage._visible = false; },
    visible() { return stage._visible; },
    el() { return stage._el; }
  };
  const sdk = {
    on(name, fn) { (handlers[name] || (handlers[name] = [])).push(fn); },
    debug: { log: (...a) => logs.push(a.join(' ')) },
    stage: opts.noStage ? undefined : stage,
    cache: { _m: {}, get(k) { return sdk.cache._m[k]; }, set(k, v) { sdk.cache._m[k] = v; }, remove(k) { delete sdk.cache._m[k]; } },
    save: {
      get(k) {
        if (opts.saveGetThrows) { const e = new Error('save.get denied'); e.code = 'HOST_DENIED'; throw e; }
        return saveData[k];
      },
      set(k, v) { saveCalls.push(['set', k, v]); saveData[k] = v; return Promise.resolve(); },
      remove(k) { saveCalls.push(['remove', k]); delete saveData[k]; return Promise.resolve(); }
    }
  };
  sdk._emit = (name, payload) => { for (const fn of (handlers[name] || []).slice()) fn(payload); };
  sdk._logs = logs;
  sdk._stage = stage;
  sdk._saveData = saveData;
  sdk._saveCalls = saveCalls;
  return sdk;
}

function makeTimers() {
  let next = 1;
  const jobs = new Map();
  return {
    setTimeout(fn) { const id = next++; jobs.set(id, fn); return id; },
    clearTimeout(id) { jobs.delete(id); },
    runAll() {
      while (jobs.size) {
        const batch = Array.from(jobs.entries());
        jobs.clear();
        for (const [, fn] of batch) fn();
      }
    }
  };
}

/* ---------------- 装载被测源码 ----------------
   §3 经典脚本 IIFE：源码结尾是 (typeof window !== 'undefined' ? window : globalThis)，
   故用 new Function 在一个自造的 window 上跑，等价于平台的 (0,eval) 内联执行，
   且不需要 vm 模块的 context 编织。 */
function loadKit(files, { sdk, doc, timers } = {}) {
  const clock = timers || { setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout: (t) => clearTimeout(t) };
  const W = {
    document: doc,
    sdk,
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
    requestAnimationFrame: null,      // 逼 core 走 setTimeout 分支（同步性更好控）
    localStorage: { _m: {}, getItem(k) { return this._m[k] ?? null; }, setItem(k, v) { this._m[k] = String(v); } },
    innerWidth: 323, innerHeight: 1205,
    console
  };
  W.window = W;
  for (const f of files) {
    const src = readFileSync(join(SBK_DIR, f), 'utf8');
    // 传 window 进去；源码自己的 IIFE 尾部会挑 window
    new Function('window', 'globalThis', src)(W, W);
  }
  return W;
}
const CORE_FILES = ['core.js'];
const STORE_FILES = ['core.js', 'core-store.js'];
const BOOT_FILES = ['core.js', 'core-store.js', 'core-boot.js'];
const THEME_FILES = ['core.js', 'core-store.js', 'core-boot.js', 'theme.js', 'theme-panel.js'];

// 每个用例一套全新环境：core.js 有 claim 单例哨兵，复用会整体短路
function fresh(files = CORE_FILES, domOpts, sdkOpts) {
  const doc = makeDoc();
  const root = buildPlatformDom(doc, domOpts);
  const sdk = makeSdk(sdkOpts);
  const W = loadKit(files, { sdk, doc });
  return { W, SBK: W.SBK, doc, root, sdk };
}
function freshTimed(files = STORE_FILES, sdkOpts) {
  const doc = makeDoc();
  const root = buildPlatformDom(doc);
  const sdk = makeSdk(sdkOpts);
  const timers = makeTimers();
  const W = loadKit(files, { sdk, doc, timers });
  return { W, SBK: W.SBK, doc, root, sdk, timers };
}
const flush = () => new Promise((r) => setTimeout(r, 0));

/* =======================================================================
   1) 状态仓深副本 + 切会话清态
   ======================================================================= */
function testStateDeepClone() {
  const t = group('state deep clone');
  const { SBK } = fresh();

  // get() 的嵌套对象不能是内部引用
  SBK.state.replace({ 好感: { 苏九: 61 }, 标记: ['中毒'] });
  const g1 = SBK.state.get();
  g1.好感.苏九 = 999;
  g1.标记.push('骨折');
  const g2 = SBK.state.get();
  t(g2.好感.苏九 === 61, 'get() 返回值的嵌套突变不影响内部状态', JSON.stringify(g2.好感));
  t(g2.标记.length === 1, 'get() 返回的数组突变不影响内部状态', JSON.stringify(g2.标记));

  // patch 的入参在 patch 之后被改，不能影响内部
  const payload = { 装备: { 头: '斗笠' } };
  SBK.state.patch(payload);
  payload.装备.头 = '铁盔';
  t(SBK.state.get().装备.头 === '斗笠', 'patch() 入参的事后突变不影响内部状态');

  // replace 同理
  const next = { 位置: { 城: '内城' } };
  SBK.state.replace(next);
  next.位置.城 = '外城';
  t(SBK.state.get().位置.城 === '内城', 'replace() 入参的事后突变不影响内部状态');

  // 订阅者拿到的也是副本：两个订阅者不能互相污染
  let seenB = null;
  SBK.state.subscribe((s) => { s.共享 = (s.共享 || 0) + 1; });      // A 乱改
  SBK.state.subscribe((s) => { seenB = s.共享; });                   // B 观察
  SBK.state.patch({ 共享: 0 });
  t(seenB === 0, '一个订阅者的突变不影响另一个订阅者看到的载荷', String(seenB));

  // Date 保真
  SBK.state.replace({ 时刻: new Date(1700000000000) });
  t(SBK.state.get().时刻 instanceof Date, 'Date 被克隆成 Date');
  t(SBK.state.get().时刻.getTime() === 1700000000000, 'Date 值保真');

  // 深嵌套
  SBK.state.replace({ a: { b: { c: { d: [1, [2, { e: 3 }]] } } } });
  t(SBK.state.get().a.b.c.d[1][1].e === 3, '多层嵌套结构完整保留');
}

function testStateCircularSafe() {
  const t = group('state degrade');
  const { SBK, sdk } = fresh();

  // 循环引用：不能抛（炸卡），且要告警
  const cyc = { name: 'x' };
  cyc.self = cyc;
  let threw = null;
  try { SBK.state.patch({ 循环: cyc }); } catch (e) { threw = e; }
  t(threw === null, '循环引用不抛异常', threw && threw.message);
  t(SBK.state.get().循环.name === 'x', '循环引用的非循环部分仍保留');
  t(SBK.state.get().循环.self === null, '循环处降级为 null');
  t(sdk._logs.some((l) => /not structurally cloneable/.test(l)), '循环引用有告警');

  // 函数与 DOM 节点：降级 null，不抛
  const node = new FakeNode('div');
  let threw2 = null;
  try { SBK.state.patch({ 回调: function () {}, 节点: node }); } catch (e) { threw2 = e; }
  t(threw2 === null, '函数/DOM 节点不抛异常', threw2 && threw2.message);
  t(SBK.state.get().回调 === null, '函数降级为 null');
  t(SBK.state.get().节点 === null, 'DOM 节点降级为 null');

  // replace 的根对象本身成环时，循环处也必须直接降级 null，不能先 snap 出一层重复结构
  const rootCyc = { name: 'root' };
  rootCyc.self = rootCyc;
  SBK.state.replace(rootCyc);
  const rootOut = SBK.state.get();
  t(rootOut.name === 'root', 'replace 根循环的非循环字段保留');
  t(rootOut.self === null, 'replace 根循环处直接降级为 null（与 patch 一致）');

  // class 实例：原型语义可降级，但嵌套引用绝不能穿透状态边界
  class Box { constructor() { this.nested = { value: 7 }; } }
  SBK.state.patch({ 实例: new Box() });
  const ex = SBK.state.get();
  ex.实例.nested.value = 99;
  t(SBK.state.get().实例.nested.value === 7, 'exotic/class 实例的嵌套字段仍被递归断引用');
  t(!(SBK.state.get().实例 instanceof Box), 'exotic/class 实例明确降级为普通对象');

  // 告警只吼一次（state 每轮都在流动，逐值刷屏会淹掉真错误）
  const n1 = sdk._logs.filter((l) => /not structurally cloneable/.test(l)).length;
  SBK.state.patch({ 又一个: (function () { const c = {}; c.c = c; return c; })() });
  const n2 = sdk._logs.filter((l) => /not structurally cloneable/.test(l)).length;
  t(n1 === n2 && n1 === 1, '不可克隆告警只出现一次（去重）', n1 + '→' + n2);
}

function testConversationSwitch() {
  const t = group('conversation:switch');
  const { SBK, sdk } = fresh();

  SBK.state.replace({ 体力: 72, 好感: { 苏九: 61 }, _sbkTheme: { fontSize: 30 }, _sbkOther: 1 });
  let emitted = null;
  SBK.state.subscribe((s) => { emitted = s; });

  sdk._emit('conversation:switch', undefined);   // 🚨 不带任何会话 id：基座不得依赖它

  const after = SBK.state.get();
  t(after.体力 === undefined, '公开键 体力 被清除');
  t(after.好感 === undefined, '公开键 好感 被清除');
  t(after._sbkTheme !== undefined, '_sbkTheme 内部字段被保留');
  eq(after._sbkTheme, { fontSize: 30 }, '_sbkTheme 内容完整');
  t(after._sbkOther === 1, '其它 _sbk* 内部字段一并保留');
  t(emitted !== null, 'switch 之后派发了 state 事件（pinned 才能清空重绘）');
  t(emitted && emitted.体力 === undefined, '派发的载荷里公开键已空');

  // 载荷带 id 也一样清（不因为 id 相同/不同而改变行为）
  SBK.state.patch({ 体力: 5 });
  sdk._emit('conversation:switch', { id: 'same' });
  sdk._emit('conversation:switch', { id: 'same' });
  t(SBK.state.get().体力 === undefined, '重复派发同 id 仍然清（幂等，不做 id 去重）');
}

/* =======================================================================
   2) schema.persist 假契约
   ======================================================================= */
function testSchemaPersist() {
  const t = group('schema.persist');
  const { SBK, sdk } = fresh(BOOT_FILES);
  const out = SBK.schema({ fields: ['体力'], persist: true, title: '状态' });
  t(!('persist' in out), 'persist 键被删除');
  t(out.title === '状态', '其它键保留');
  eq(out.fields, ['体力'], 'fields 保留');
  t(sdk._logs.some((l) => /schema\.persist is removed/.test(l)), '有明确告警');
  t(sdk._logs.some((l) => /SBK\.store\.save/.test(l)), '告警指向显式 store API');
  // rows 别名仍然工作（不能因为加了 persist 处理而回归）
  const out2 = SBK.schema({ rows: ['体力'] });
  eq(out2.fields, ['体力'], 'rows→fields 别名仍生效');
}

/* =======================================================================
   3) hostId 规范与回落
   ======================================================================= */
function testHostId() {
  const t = group('hostId');
  const { SBK, sdk } = fresh();
  const norm = SBK.dom.hostId;
  const normBase = SBK.dom.hostBaseId;

  eq(norm('sbk-hud'), 'sbk-hud', '合法值原样返回');
  eq(norm('a'), 'a', '单字母合法');
  eq(norm('A_b-9'), 'A_b-9', '字母数字下划线连字符合法');
  eq(norm('sbk-hud-pin'), 'sbk-hud-pin', '派生 id 合法');
  eq(norm('x'.repeat(64)), 'x'.repeat(64), '最终 DOM id 允许 64 字符');
  eq(normBase('x'.repeat(60)), 'x'.repeat(60), '可派生配置基名允许 60 字符');
  eq(normBase('x'.repeat(61)), 'sbk-hud', '61 字符配置基名回落，避免派生 id 越过 64');
  t((normBase('x'.repeat(60)) + '-pin').length === 64, '60 字符基名派生 -pin 后恰为 64');

  // 非法：回落 sbk-host
  const bad = [
    ['1abc', '数字开头'],
    ['-abc', '连字符开头'],
    ['a b', '含空格'],
    ['a"]', '含选择器元字符 " 与 ]'],
    ['a]>b', '含 SAFE_FOR_XML 触发串 ]>'],
    ['状态栏', '非 ASCII'],
    ['x'.repeat(65), '超长 65 字符'],
    ['', '空串'],
    [null, 'null'],
    ['a.b', '含点（CSS 类选择器元字符）'],
    ['a#b', '含井号'],
    ['a[b]', '含方括号']
  ];
  for (const [v, why] of bad) {
    eq(norm(v), 'sbk-host', '非法值回落 sbk-host（' + why + '）');
  }
  t(sdk._logs.filter((l) => /invalid host id/.test(l)).length >= bad.length, '每个非法值都有告警');

  // 注入面：带引号的 id 不能让 mountHost 抛错或错删节点
  const inj = SBK.dom.mountHost('a"] , [data-chat="root');
  t(inj !== null, '注入型 id 不导致 mountHost 返回 null');
  t(inj.id === 'sbk-host', '注入型 id 被回落成 sbk-host', inj.id);
}

function testMountHostDedupe() {
  const t = group('mountHost');
  const { SBK, doc, root } = fresh();

  const h1 = SBK.dom.mountHost('sbk-hud');
  t(h1 !== null, '首次挂载成功');
  t(h1.id === 'sbk-hud', 'id 正确');
  const sb = doc.querySelector('[data-slot="statusbar"]');
  t(h1.parentNode === sb, '优先挂 statusbar 槽位');

  // 幂等：再调不造第二个
  const h2 = SBK.dom.mountHost('sbk-hud');
  t(h2 === h1, '重复调用复用同一节点');
  t(doc.querySelectorAll('[id]').filter((n) => n.id === 'sbk-hud').length === 1, '全文档只有一个同 id 节点');

  // 模拟平台迟到渲染造成的重复 id：内容要被搬进保留的那个
  const dup = new FakeNode('div');
  dup.id = 'sbk-hud';
  const kid = new FakeNode('span');
  kid.id = 'sbk-hud-chr';
  kid.setAttribute('class', 'sbk-chr');
  dup.appendChild(kid);
  doc.querySelector('[data-slot="left"]').appendChild(dup);
  const h3 = SBK.dom.mountHost('sbk-hud');
  t(doc.querySelectorAll('[id]').filter((n) => n.id === 'sbk-hud').length === 1, '重复 id 被归一成一个');
  t(h3.childNodes.includes(kid), '重复节点的子内容被搬进保留节点');

  // 子节点 id 含选择器元字符：adopt 不能抛、不能丢内容
  const dup2 = new FakeNode('div');
  dup2.id = 'sbk-hud';
  const weird = new FakeNode('span');
  weird.id = 'x"] , [data-chat="root';
  dup2.appendChild(weird);
  doc.querySelector('[data-slot="left"]').appendChild(dup2);
  let threw = null;
  let h4 = null;
  try { h4 = SBK.dom.mountHost('sbk-hud'); } catch (e) { threw = e; }
  t(threw === null, '子节点 id 含元字符时 adopt 不抛', threw && threw.message);
  t(h4 && h4.childNodes.includes(weird), '含元字符 id 的子节点内容未丢失');
}

function testEventPayloadIsolation() {
  const t = group('event payload isolation');
  const { SBK } = fresh();
  let seen = null;
  SBK.on('done', (p) => { p.content = 'tampered'; p.meta.deep = 9; });
  SBK.on('done', (p) => { seen = p; });
  const source = { content: 'original', meta: { deep: 1 } };
  SBK.emit('done', source, null);
  t(seen.content === 'original', '前一订阅者不能改写后一订阅者的 content');
  t(seen.meta.deep === 1, '嵌套 payload 也按订阅者隔离');
  t(source.content === 'original' && source.meta.deep === 1, '源 payload 不被订阅者突变');
}

function savedDoc(sdk, key = 'sbk-state') {
  const raw = sdk._saveData[key];
  return typeof raw === 'string' ? JSON.parse(raw) : raw;
}

function testStoreMerge() {
  const t = group('store merge');
  const initial = { 体力: 72, 背包: ['药'], _sbkTheme: { old: 1 }, _sbkOther: 8 };
  const { SBK, sdk, timers } = freshTimed(STORE_FILES, { saveData: { 'sbk-state': JSON.stringify(initial) } });

  SBK.store.merge({ _sbkTheme: { v: 2 } });
  timers.runAll();
  let doc = savedDoc(sdk);
  t(doc.体力 === 72 && doc.背包[0] === '药', 'merge 保留远端已有业务字段');
  eq(doc._sbkTheme, { v: 2 }, 'merge 覆盖自己的顶层键');
  t(doc._sbkOther === 8, 'merge 保留其它内部键');
  t(sdk._saveCalls.filter((x) => x[0] === 'set').length === 1, '一次 flush 只写一次');

  // 同一 800ms 窗口：业务整文档 + 主题补丁必须合成，而非 last-writer-wins
  SBK.store.save({ 章节: 3, 好感: { 苏九: 61 } });
  SBK.store.merge({ _sbkTheme: { v: 2, preset: 'B' } });
  timers.runAll();
  doc = savedDoc(sdk);
  t(doc.章节 === 3 && doc.好感.苏九 === 61, '同窗业务 save 不被主题补丁覆盖');
  eq(doc._sbkTheme, { v: 2, preset: 'B' }, '同窗主题补丁落地');
  t(doc._sbkOther === 8, '业务 save 未显式给内部键时自动保留旧 _sbk*');

  // 反向调用顺序也必须合成
  SBK.store.merge({ _sbkTheme: { v: 2, preset: 'C' } });
  SBK.store.save({ 章节: 4 });
  timers.runAll();
  doc = savedDoc(sdk);
  t(doc.章节 === 4, '先 merge 后 save 仍保存业务整文档');
  eq(doc._sbkTheme, { v: 2, preset: 'C' }, '先 merge 后 save 仍保留补丁');

  // key 切换必须先 flush 旧 key，且内存回落按 key 隔离
  SBK.store.merge({ a: 1 });
  SBK.store.key('other-save');
  SBK.store.save({ b: 2 });
  timers.runAll();
  t(savedDoc(sdk).a === 1, '换 key 前排队内容写回旧 key');
  t(savedDoc(sdk, 'other-save').b === 2, '新 key 保存独立文档');
}

function testStoreLoadAfterThrottle() {
  const t = group('store load after throttle');
  const initial = { gen: 0 };
  const { SBK, sdk, timers } = freshTimed(STORE_FILES, {
    saveData: { 'sbk-state': JSON.stringify(initial) }
  });
  for (let gen = 1; gen <= 25; gen++) {
    SBK.store.save({ gen });
    timers.runAll();
  }
  t(sdk._saveCalls.filter((x) => x[0] === 'set').length === 18,
    '本地令牌桶只放行 18 次远端写');
  t(savedDoc(sdk).gen === 18, '远端仍是最后一次放行版本');
  t(JSON.parse(sdk.cache._m['sbk-state']).gen === 25, 'cache 保留最新版本');
  t(SBK.store.load().gen === 25, '🚨 load 返回最新本地版本，不回退到远端旧档');
}

function testStoreMergeThinPreview() {
  const t = group('store merge thin preview');
  const { SBK, sdk, timers } = freshTimed(STORE_FILES, {
    saveData: { 'sbk-state': JSON.stringify({ 远端: '不可见' }) }, saveGetThrows: true
  });
  SBK.store.merge({ _sbkTheme: { v: 2 } });
  timers.runAll();
  t(sdk._saveCalls.filter((x) => x[0] === 'set').length === 0,
    'save.get 同步抛后不向未知远端写整文档');
  const cached = JSON.parse(sdk.cache._m['sbk-state']);
  eq(cached._sbkTheme, { v: 2 }, '瘦预览只在 cache 留本页补丁');
  t(sdk._saveData['sbk-state'].includes('远端'), '未知远端文档没有被覆盖');
}

function themeEnvelope(defaultPreset = 'A') {
  const pack = (accent) => ({ dark: { tokens: { accent }, tune: {} }, light: { tokens: { accent }, tune: {} } });
  return { v: 2, base: null, presets: { A: pack('#5aa9e6'), B: pack('#c05a7a') }, preset: defaultPreset };
}

function testThemeRuntimeContracts() {
  const t = group('theme runtime');
  const initial = { gold: 42, quest: { id: 7 }, _sbkTheme: {
    v: 2, preset: 'B', on: true, ov: { dark: {}, light: {} }
  } };
  const { SBK, sdk, timers, doc } = freshTimed(THEME_FILES, {
    saveData: { 'sbk-state': JSON.stringify(initial) }
  });

  SBK.theme.apply(themeEnvelope('A'));
  t(SBK.theme.prefs.preset() === 'B', '首次 envelope 尊重已存玩家 preset');
  SBK.theme.prefs.set('fontSize', 18, 'dark');
  timers.runAll();
  const saved = savedDoc(sdk);
  t(saved.gold === 42 && saved.quest.id === 7, '主题偏好写回不丢远端业务字段');
  t(saved._sbkTheme.ov.dark.fontSize === 18, '主题偏好补丁落地');

  SBK.theme.apply(themeEnvelope('A'));
  t(SBK.theme.prefs.preset() === 'B', '重复 envelope 不把玩家 B 拉回作者默认 A');
  t(SBK.theme.prefs.raw().preset === 'B', 'presetName 与 prefs.preset 不分叉');

  SBK.theme.apply({ dark: { '--rpx': '999px', '--sbk-z-pop': 9999, '--chat-nope': '#fff', accent: '#5aa9e6' },
    light: { '--rpx': '999px', '--sbk-z-pop': 9999, '--chat-nope': '#fff', accent: '#1a5f96' } });
  const author = SBK.theme.author();
  for (const mode of ['dark', 'light']) {
    t(!('--rpx' in author[mode].tokens), mode + ' 作者基线拒绝 --rpx');
    t(!('--sbk-z-pop' in author[mode].tokens), mode + ' 作者基线拒绝结构 z token');
    t(!('--chat-nope' in author[mode].tokens), mode + ' 作者基线拒绝臆造 chat token');
    t('accent' in author[mode].tokens, mode + ' 合法 token 保留');
  }
  const style = doc.head.childNodes.find((n) => n.id === SBK.theme.styleId);
  t(style && !/--rpx|--sbk-z-pop|--chat-nope/.test(style.textContent), '坏 token 不进入最终 CSS');

  SBK.theme.prefs.enabled(false);
  t(style.textContent === '', 'enabled(false) 清空唯一主题节点，真 native');
  SBK.theme.prefs.enabled(true);
  t(style.textContent.includes('--chat-accent'), 'enabled(true) 恢复合成主题');
}

/* =======================================================================
   4) stage 延迟竞态（审计报告问题 4）
   ======================================================================= */
const UI_FILES = [
  'core.js', 'core-store.js', 'core-boot.js', 'theme.js', 'theme-panel.js',
  'protocol.js', 'hud.js', 'hud-render.js', 'ui.js', 'ui-panel.js', 'ui-stage.js'
];

/* DOM 未就绪的环境：ui.js 的 domReady() 查 [data-chat="root"]，查不到就把任务排进队列，
   等首个 mount/done 排空 —— 这正是竞态窗口。故此处刻意不建平台 DOM。 */
function freshNoDom() {
  const doc = makeDoc();
  const sdk = makeSdk();
  const W = loadKit(UI_FILES, { sdk, doc });
  return { W, SBK: W.SBK, doc, sdk };
}
function attachDom(doc) { return buildPlatformDom(doc); }

async function testPanelOpenThenCloseBeforeMount() {
  const t = group('panel open→close before mount');
  const { SBK, doc, sdk } = freshNoDom();
  const p = SBK.ui.panel({ id: 'panel-close', mode: 'drawer', title: '设置' });
  p.open();
  p.close();
  attachDom(doc);
  sdk._emit('message:mount', {});
  await flush();
  t(p.opened() === false, 'close 作废挂载前排队的 open');
  t(p.el() !== null, '面板骨架可正常挂载但保持关闭');
  t(!/sbk-drw--on/.test(p.box().className), '关闭态不带打开 class');
}

async function testPanelOpenThenDestroyBeforeMount() {
  const t = group('panel open→destroy before mount');
  const { SBK, doc, sdk } = freshNoDom();
  const p = SBK.ui.panel({ id: 'panel-destroy', mode: 'drawer', title: '设置' });
  p.open();
  p.destroy();
  attachDom(doc);
  sdk._emit('message:mount', {});
  await flush();
  t(p.opened() === false, 'destroy 后排队的 open 不得把 opened 置真');
  t(p.el() === null && p.box() === null, 'destroy 后不复活 DOM');
}

async function testPanelOpenBeforeMountCompletes() {
  const t = group('panel open before mount');
  const { SBK, doc, sdk } = freshNoDom();
  const p = SBK.ui.panel({ id: 'panel-open', mode: 'drawer', title: '设置' });
  p.open();
  attachDom(doc);
  sdk._emit('message:mount', {});
  await flush();
  t(p.opened() === true, '未取消的挂载前 open 在 DOM 就绪后真正打开');
  t(/sbk-drw--on/.test(p.box().className), '打开态带 sbk-drw--on');
}

async function testStageOpenThenClose() {
  const t = group('stage open→close before mount');
  const { SBK, doc, sdk } = freshNoDom();
  const closes = [];
  const st = SBK.ui.stage({ title: '地图', onClose: (api, byPlatform) => closes.push(byPlatform) });

  st.open();                     // DOM 未就绪 → 入队
  t(sdk._stage.opens === 0, 'DOM 未就绪时 open 没有立即调 sdk.stage.open');
  st.close();                    // 队列必须作废

  attachDom(doc);
  sdk._emit('message:mount', {}); // 排空队列
  await flush();

  t(sdk._stage.opens === 0, '🚨 close 之后排队的 open 不得复活舞台', 'opens=' + sdk._stage.opens);
  t(sdk._stage.visible() === false, '舞台保持关闭');
  t(st.visible() === false, 'api.visible() 为 false');
  eq(closes, [false], 'onClose 恰好一次且 byPlatform=false');
}

async function testStageOpenThenDestroy() {
  const t = group('stage open→destroy before mount');
  const { SBK, doc, sdk } = freshNoDom();
  const closes = [];
  const st = SBK.ui.stage({ title: '背包', onClose: (api, by) => closes.push(by) });

  st.open();
  st.destroy();

  attachDom(doc);
  sdk._emit('message:mount', {});
  await flush();

  t(sdk._stage.opens === 0, '🚨 destroy 之后排队的 open 不得打开舞台', 'opens=' + sdk._stage.opens);
  eq(closes, [], 'destroy 时舞台本就没开 → 不回调 onClose');
  // destroy 后再 open 应被拒（且告警）
  st.open();
  sdk._emit('message:mount', {});
  await flush();
  t(sdk._stage.opens === 0, 'destroy 后再 open 无效');
  t(sdk._logs.some((l) => /destroyed stage/.test(l)), 'destroy 后 open 有告警');
}

async function testStageDestroyWhileVisible() {
  const t = group('stage destroy while visible');
  const { SBK, doc, sdk } = freshNoDom();
  attachDom(doc);                       // 这次 DOM 就绪，open 立即落地
  const closes = [];
  const st = SBK.ui.stage({ title: '小游戏', onClose: (api, by) => closes.push(by) });
  st.open();
  await flush();
  t(sdk._stage.opens === 1, '舞台已打开');
  t(st.visible() === true, 'visible() 为 true');
  const box = st.box();
  t(box !== null, 'box 已建');

  st.destroy();
  t(sdk._stage.closes === 1, '🚨 destroy 时舞台可见 → 必须调 sdk.stage.close 一次', 'closes=' + sdk._stage.closes);
  t(sdk._stage.visible() === false, '不留下一个空舞台');
  t(box.parentNode === null, 'box 已从舞台容器摘除');
  eq(closes, [false], '🚨 onClose 恰好一次，不重复');
}

async function testStageRebuildAfterClose() {
  const t = group('stage rebuild/render after close');
  const { SBK, doc, sdk } = freshNoDom();
  let renders = 0;
  const st = SBK.ui.stage({ title: 'x', render: () => { renders++; } });
  st.open();
  st.rebuild();
  st.render();
  st.close();
  attachDom(doc);
  sdk._emit('message:mount', {});
  await flush();
  t(sdk._stage.opens === 0, 'close 作废了排队的 open');
  t(renders === 0, 'close 也作废了排队的 rebuild/render（不在关闭状态下白建内容）', 'renders=' + renders);
}

async function testStagePlatformCloseCancelsQueue() {
  const t = group('stage platform close');
  const { SBK, doc, sdk } = freshNoDom();
  const closes = [];
  const st = SBK.ui.stage({ onClose: (api, by) => closes.push(by) });
  st.open();                            // 入队
  sdk._emit('stage:close', {});         // 平台侧关闭先到
  attachDom(doc);
  sdk._emit('message:mount', {});
  await flush();
  t(sdk._stage.opens === 0, '平台侧关闭同样作废排队的 open');
  eq(closes, [true], 'onClose 收到 byPlatform=true 一次');
}

/* =======================================================================
   5) typed entities 与坏值：绝不产出 NaN% / undefined
   ======================================================================= */
const HUD_FILES = ['core.js', 'core-store.js', 'core-boot.js', 'protocol.js', 'hud.js', 'hud-render.js'];
function snapOf(SBK, state, schema) { return SBK.ui.snapshot(state, schema); }

function testTypedEntitiesNoNaN() {
  const t = group('typed entities');
  const { SBK } = fresh(HUD_FILES);

  // 🚨 本次修的核心入口：值【自带 type】，旧代码整条绕过归一化
  const cases = [
    ['字符串 value', { type: 'entities', value: [{ name: '苏九', value: '很高' }] }],
    ['NaN value', { type: 'entities', value: [{ name: '苏九', value: NaN }] }],
    ['Infinity value', { type: 'entities', value: [{ name: '苏九', value: Infinity }] }],
    ['-Infinity value', { type: 'entities', value: [{ name: '苏九', value: -Infinity }] }],
    ['undefined value', { type: 'entities', value: [{ name: '苏九' }] }],
    ['null value', { type: 'entities', value: [{ name: '苏九', value: null }] }],
    ['对象 value', { type: 'entities', value: [{ name: '苏九', value: {} }] }],
    ['缺 name', { type: 'entities', value: [{ value: 5 }] }],
    ['name 是对象', { type: 'entities', value: [{ name: {}, value: 5 }] }],
    ['原始值数组', { type: 'entities', value: ['苏九', '阿澈'] }],
    ['value 不是数组', { type: 'entities', value: 'x' }],
    ['空数组', { type: 'entities', value: [] }],
    ['坏 max', { type: 'entities', value: [{ name: 'a', value: 5 }], max: NaN }],
    ['Infinity max', { type: 'entities', value: [{ name: 'a', value: 5 }], max: Infinity }],
    ['零 max', { type: 'entities', value: [{ name: 'a', value: 5 }], max: 0 }]
  ];
  for (const [why, v] of cases) {
    let html = null, threw = null;
    try { html = snapOf(SBK, { 好感: v }, { fields: [{ key: '好感', type: 'entities' }] }); } catch (e) { threw = e; }
    t(threw === null, 'typed entities 不抛（' + why + '）', threw && threw.message);
    const s = String(html ?? '');
    t(!/NaN/.test(s), '🚨 无 NaN（' + why + '）', s.slice(0, 160));
    t(!/undefined/.test(s), '🚨 无 undefined（' + why + '）', s.slice(0, 160));
    t(!/Infinity/.test(s), '无 Infinity（' + why + '）', s.slice(0, 160));
    t(!/\[object Object\]/.test(s), '无 [object Object]（' + why + '）', s.slice(0, 160));
    t(!/width:\s*%/.test(s), '无空宽度（' + why + '）', s.slice(0, 160));
  }

  // 正常值仍要正确（归一化不能把好数据改坏）
  const good = snapOf(SBK, { 好感: { type: 'entities', value: [{ name: '苏九', value: 61 }, { name: '阿澈', value: 25 }] } },
    { fields: [{ key: '好感', type: 'entities' }] });
  t(/苏九/.test(good) && /61/.test(good), '正常 entities 名与值都在');
  t(/width:100\.0%/.test(good), '最大项宽度 100%（缺 max 取组内最大值）', good);
  t(/width:41\.0%/.test(good), '次项按比例计算 25/61≈41.0%', good);

  // schema 直喂结构化数组：direct() 入口也必须走 txt()，不能漏出对象字符串
  const direct = snapOf(SBK, { 好感: [{ name: { bad: 1 }, value: 5 }] },
    { fields: [{ key: '好感', type: 'entities' }] });
  t(!/\[object Object\]/.test(direct), '直喂 entities 的对象 name 不漏 [object Object]', direct);
}

function testOtherTypesNoGarbage() {
  const t = group('typed others');
  const { SBK } = fresh(HUD_FILES);
  const cases = [
    ['bar NaN', 'bar', { type: 'bar', value: NaN, max: 100 }],
    ['bar 缺 max', 'bar', { type: 'bar', value: 50 }],
    ['bar max=0', 'bar', { type: 'bar', value: 50, max: 0 }],
    ['bar 字符串', 'bar', { type: 'bar', value: 'x', max: 100 }],
    ['num NaN', 'num', { type: 'num', value: NaN }],
    ['num 对象', 'num', { type: 'num', value: {} }],
    ['level NaN', 'level', { type: 'level', value: { name: '炼气', value: NaN, max: 300 } }],
    ['level 坏形状', 'level', { type: 'level', value: 'x' }],
    ['level null', 'level', { type: 'level', value: null }],
    ['tags 对象项', 'tags', { type: 'tags', value: [{}, 'ok'] }],
    ['path 对象项', 'path', { type: 'path', value: [{}, '东市'] }],
    ['stats 坏项', 'stats', { type: 'stats', value: [null, { name: 'a' }] }],
    ['kvlist 坏项', 'kvlist', { type: 'kvlist', value: ['x', { name: 'a', value: undefined }] }],
    ['stats 直喂对象字段', 'stats', [{ name: { bad: 1 }, value: { bad: 2 }, note: { bad: 3 } }]],
    ['kvlist 直喂对象字段', 'kvlist', [{ name: { bad: 1 }, value: { bad: 2 }, note: { bad: 3 } }]],
    ['level 直喂对象名', 'level', { name: { bad: 1 }, value: 2, max: 3 }],
    ['text 对象', 'text', { type: 'text', value: {} }]
  ];
  for (const [why, ty, v] of cases) {
    let s = null, threw = null;
    try { s = snapOf(SBK, { f: v }, { fields: [{ key: 'f', type: ty }] }); } catch (e) { threw = e; }
    t(threw === null, '不抛（' + why + '）', threw && threw.message);
    const out = String(s ?? '');
    t(!/NaN|undefined|Infinity|\[object Object\]/.test(out), '🚨 无垃圾输出（' + why + '）', out.slice(0, 160));
  }
}

/* =======================================================================
   6) 新三类型：双出口共用 vnode、零状态、格式容错
   ======================================================================= */
function testNewTypes() {
  const t = group('time/summary/turn');
  const { SBK, doc, root } = fresh(HUD_FILES);

  // ---- 字符串出口 ----
  const html = snapOf(SBK, { 时间: '第三日 黄昏', 概要: '你在药铺遇见了苏九。\n她递来一包药。', 本轮: '3/12' },
    { fields: [{ key: '时间', type: 'time' }, { key: '概要', type: 'summary' }, { key: '本轮', type: 'turn' }] });
  t(/sbk-time/.test(html), 'time 产出 .sbk-time');
  t(/sbk-time__d/.test(html) && /sbk-time__t/.test(html), 'time 带空白时切成两段');
  t(/第三日/.test(html) && /黄昏/.test(html), 'time 两段内容都在');
  t(/sbk-sum/.test(html), 'summary 产出 .sbk-sum');
  t(/苏九/.test(html), 'summary 内容在');
  t(/sbk-turn/.test(html), 'turn 产出 .sbk-turn');
  t(/3\/12/.test(html), 'turn 原样显示 3/12（不解析成进度条）');
  t(!/NaN|undefined|\[object Object\]/.test(html), '三类型无垃圾输出');

  // ---- 格式容错 ----
  const tol = [
    ['time 无空白', { 时间: '黄昏' }, 'time', /sbk-time__t/],
    ['time 多空白', { 时间: '  2026-08-26   19:30  ' }, 'time', /sbk-time__d/],
    ['time 数字', { 时间: 3 }, 'time', /sbk-time/],
    ['turn 纯数字', { 本轮: 7 }, 'turn', /sbk-turn/],
    ['turn 中文', { 本轮: '第三幕' }, 'turn', /第三幕/],
    ['summary 长文', { 概要: 'x'.repeat(80) }, 'summary', /sbk-sum/]
  ];
  for (const [why, st, ty, re] of tol) {
    const k = Object.keys(st)[0];
    let s = null, threw = null;
    try { s = snapOf(SBK, st, { fields: [{ key: k, type: ty }] }); } catch (e) { threw = e; }
    t(threw === null, '容错不抛（' + why + '）', threw && threw.message);
    t(re.test(String(s ?? '')), '容错产出正确（' + why + '）', String(s).slice(0, 140));
    t(!/NaN|undefined|\[object Object\]/.test(String(s ?? '')), '容错无垃圾（' + why + '）');
  }

  // 空值不产出空壳
  for (const [ty, k] of [['time', '时间'], ['summary', '概要'], ['turn', '本轮']]) {
    const s = snapOf(SBK, { [k]: '' }, { fields: [{ key: k, type: ty }] });
    t(!new RegExp('sbk-' + (ty === 'summary' ? 'sum' : ty)).test(String(s ?? '')),
      ty + ' 空值不产出空壳', String(s));
  }

  // ---- 双出口一致：DOM 出口（hydrate）产出同构结构 ----
  const bubble = new FakeNode('div');
  bubble.setAttribute('data-chat', 'message-body');
  const rawNode = new FakeNode('div');
  rawNode.setAttribute('class', 'sbk-snap sbk-snap--raw');
  rawNode.textContent = '[状态]\n时间: 第三日 黄昏\n本轮: 3/12\n概要: 一段摘要\n[/状态]';
  bubble.appendChild(rawNode);
  root.appendChild(bubble);

  const n = SBK.ui.snapshot.hydrate(bubble, {
    fields: [{ key: '时间', type: 'time' }, { key: '本轮', type: 'turn' }, { key: '概要', type: 'summary' }]
  });
  t(n === 1, 'hydrate 处理了 1 个节点', String(n));
  const classes = rawNode._walk([]).map((x) => x.className || '').join(' ');
  t(/sbk-time/.test(classes), 'DOM 出口也产出 .sbk-time');
  t(/sbk-turn/.test(classes), 'DOM 出口也产出 .sbk-turn');
  t(/sbk-sum/.test(classes), 'DOM 出口也产出 .sbk-sum');
  const txt = rawNode.textContent;
  t(/第三日/.test(txt) && /3\/12/.test(txt) && /一段摘要/.test(txt), 'DOM 出口内容与字符串出口一致');
  t(!/NaN|undefined|\[object Object\]/.test(txt), 'DOM 出口无垃圾');

  // 零本地状态：同一份输入渲染两次结果完全相同
  const a = snapOf(SBK, { 时间: '第三日 黄昏' }, { fields: [{ key: '时间', type: 'time' }] });
  const b = snapOf(SBK, { 时间: '第三日 黄昏' }, { fields: [{ key: '时间', type: 'time' }] });
  t(a === b, '三类型零状态：同输入两次渲染结果一致');
}

/* =======================================================================
   7) 未知 type：告警 + 明确回 text + 去重
   ======================================================================= */
function testUnknownType() {
  const t = group('unknown type');
  const { SBK, sdk } = fresh(HUD_FILES);

  const s = snapOf(SBK, { 好感: '苏九=61' }, { fields: [{ key: '好感', type: 'entites' }] });  // 拼写错误
  t(sdk._logs.some((l) => /unknown type "entites"/.test(l)), '未知 type 有告警');
  t(sdk._logs.some((l) => /rendered as text/.test(l)), '告警说明回落成 text');
  t(sdk._logs.some((l) => /SBK\.ui\.hud\.type/.test(l)), '告警指向自定义控件注册入口');
  t(/sbk-val/.test(String(s ?? '')), '确实按 text 渲染出一行值', String(s).slice(0, 160));
  t(!/NaN|undefined|\[object Object\]/.test(String(s ?? '')), '未知 type 回落无垃圾');

  // 去重：同一个坏 type 反复渲染只告警一次
  const before = sdk._logs.filter((l) => /unknown type "entites"/.test(l)).length;
  for (let i = 0; i < 5; i++) snapOf(SBK, { 好感: 'x' }, { fields: [{ key: '好感', type: 'entites' }] });
  const after = sdk._logs.filter((l) => /unknown type "entites"/.test(l)).length;
  t(before === 1 && after === 1, '🚨 同一未知 type 只告警一次（不逐轮刷屏）', before + '→' + after);

  // 不同的坏 type 各告警一次
  snapOf(SBK, { x: 'y' }, { fields: [{ key: 'x', type: 'nope' }] });
  t(sdk._logs.some((l) => /unknown type "nope"/.test(l)), '另一个未知 type 单独告警');

  // 合法类型不得误告警
  const n0 = sdk._logs.filter((l) => /unknown type/.test(l)).length;
  for (const ty of ['bar', 'num', 'text', 'tags', 'entities', 'path', 'level', 'stats', 'kvlist', 'time', 'summary', 'turn']) {
    snapOf(SBK, { f: '1/2' }, { fields: [{ key: 'f', type: ty }] });
  }
  t(sdk._logs.filter((l) => /unknown type/.test(l)).length === n0, '十二种合法类型均不告警');
  t(SBK.ui.hud.types().length === 12, '控件表恰 12 种', String(SBK.ui.hud.types().length));

  // 自定义控件注册后不再被判未知
  SBK.ui.hud.type('星级', (f) => ({ t: 'span', c: 'sbk-val', x: '★' }));
  const n1 = sdk._logs.filter((l) => /unknown type/.test(l)).length;
  const cs = snapOf(SBK, { 评价: '3' }, { fields: [{ key: '评价', type: '星级' }] });
  t(sdk._logs.filter((l) => /unknown type/.test(l)).length === n1, '已注册的自定义 type 不告警');
  t(/★/.test(String(cs ?? '')), '自定义控件生效');
}

/* =======================================================================
   8) 源码级防回归断言
   ------------------------------------------------------------------
   有些不变量在零依赖 fake DOM 下无法真正执行（需要真实内核的焦点模型、
   媒体查询求值、CSS 层叠）。对这些项做【源码级】断言并在报告里诚实标注：
   它们证明「代码里确实写了这条」，不证明「运行时确实生效」。
   运行时生效由 WP-3 的本地仿真页 + 实机验收负责（main.md 的验证原则）。 */
function testSourceInvariants() {
  const t = group('source invariants (静态断言，非运行时验证)');
  const ui = readFileSync(join(SBK_DIR, 'ui.js'), 'utf8') + '\n' +
    readFileSync(join(SBK_DIR, 'ui-panel.js'), 'utf8');
  const css = readFileSync(join(SBK_DIR, 'base.css'), 'utf8');
  const core = readFileSync(join(SBK_DIR, 'core.js'), 'utf8');

  // 原生 button
  t(/h\('button', \{ type: 'button', 'class': 'sbk-pnl__ball' \}/.test(ui), '悬浮球是 <button type=button>');
  t(/k\.push\(h\('button', attrs,/.test(ui), '菜单项是 <button>');
  t(/type: 'button'/.test(ui), '菜单项 attrs 含 type=button');
  t(!/h\('div', \{ 'class': 'sbk-pnl__ball' \}/.test(ui), '悬浮球不再是 div');

  // pointer 与 click 分路：click 是唯一触发点，pointerup 只收尾
  t(/addEventListener\('click', function \(e\) \{[\s\S]{0,200}api\.toggle\(\)/.test(ui), 'click 路径触发 toggle');
  t(/if \(moved\) \{[^}]*suppress = true;/.test(ui), '拖动后置 suppress 吞掉尾随 click');
  t(!/else api\.toggle\(\);\s*\/\/ 没拖动 = 点击/.test(ui), 'pointerup 不再直接 toggle（否则键盘失效或双触发）');
  t(/if \(k === 'Enter' \|\| k === ' '/.test(ui), 'keydown 清 suppress，键盘路径不被残留标志吃掉');

  // 焦点与键盘
  t(/:focus-visible/.test(ui), 'ui.js 有 :focus-visible');
  t(/:focus-visible/.test(css), 'base.css 有 :focus-visible');
  t(/function onEsc\(e\)[\s\S]{0,180}k === 'Escape'[\s\S]{0,100}k === 'Esc'[\s\S]{0,100}api\.close\(\)/.test(ui),
    'Escape 关闭（含旧内核 Esc 写法）');
  t(/lastFocus/.test(ui) && /releaseFocus/.test(ui), '焦点回返已实现');
  t(/d\.body\.contains\(t\)/.test(ui), '焦点回返前校验来路节点仍在文档里');
  t(/removeEventListener\('keydown', onEsc, true\)/.test(ui), 'Escape 捕获监听随关闭/销毁卸载');

  // tooltip 原生键盘语义
  const hud = readFileSync(join(SBK_DIR, 'hud.js'), 'utf8');
  t(/t: 'button', c: c \+ ' sbk-tt__hit'/.test(hud), 'tooltip 触发词是原生 button');
  t(/type=\"button\"/.test(hud), '字符串快照出口给 tooltip button 明确 type=button');
  t(/safe-area-inset-top/.test(ui), '抽屉头部处理顶部 safe-area');

  // 响应式与安全区
  t(/env\(safe-area-inset-left/.test(ui), 'ui.js 抽屉有 safe-area');
  t(/env\(safe-area-inset/.test(css), 'base.css 有 safe-area');
  t(/height:100dvh/.test(ui), '抽屉有 100dvh');
  t(/height:100vh/.test(ui), '抽屉有 100vh 回落（写在 dvh 之前）');
  t(ui.indexOf('height:100vh') < ui.indexOf('height:100dvh'), 'dvh 写在 vh 之后（否则永远用不上 dvh）');
  t(/prefers-reduced-motion/.test(ui), 'ui.js 有 reduced-motion');
  t(/prefers-reduced-motion/.test(css), 'base.css 有 reduced-motion');
  t(/orientation:landscape/.test(ui) && /orientation: landscape/.test(css), '两处都有横屏适配');

  // 字号双出口（审计报告问题 8）
  t(/\.sbk-host,\s*\n\.sbk-snap \{/.test(css), '🚨 .sbk-host 与 .sbk-snap 同一条规则消费字号');
  t(/font-size: var\(--sbk-fs, 14px\)/.test(css), '消费 --sbk-fs');
  t(/line-height: var\(--sbk-lh, 1\.5\)/.test(css), '消费 --sbk-lh（theme 层会把值改成 px）');

  // color-scheme 深浅跟随（不改 theme.js，纯 CSS 按 data-theme）
  t(/color-scheme: dark/.test(css), '深色基线声明 color-scheme');
  t(/color-scheme: light/.test(css), 'light 主题块声明 color-scheme');

  // 死类名已删
  t(!/sbk-hide/.test(css), '.sbk-hide 已删除');
  t(!/sbk-sep/.test(css), '.sbk-sep 已删除');

  /* 无选择器拼接（注入面）。
     ⚠ 必须【剥掉注释再断言】：core.js 的注释里为了讲清楚缺陷成因，原样引用了旧写法
       `'[id="' + hid + '"]'`。不剥注释的话这条断言会命中【文档而非代码】——
       那是一条永远失败（或反过来永远通过）的假断言，比没有断言更糟。 */
  const coreCode = core.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  t(!/\[id="'\s*\+/.test(coreCode), '🚨 core.js 代码里不再把 id 拼进选择器');
  t(!/querySelector(All)?\('\[id="'/.test(coreCode), 'querySelector 不接收拼接出来的 id 选择器');
  t(/querySelectorAll\('\[id\]'\)/.test(core), '改用常量选择器 [id] + 精确比较');
  t(/HOST_ID = \/\^\[A-Za-z\]\[A-Za-z0-9_-\]\{0,63\}\$\//.test(core), '最终 DOM hostId 规范为 64 字符');
  t(/HOST_BASE_ID = \/\^\[A-Za-z\]\[A-Za-z0-9_-\]\{0,59\}\$\//.test(core), '可派生 hostId 基名规范为 60 字符');
}

/* =======================================================================
   7) 侧边栏一族：chrome→dock 路由 + 数量纪律 + 回落
   ------------------------------------------------------------------
   这些不是渲染细节，是【形态契约】：
   · chrome() 默认必须变成导轨上的一枚图标页签，不再是功能栏里的「大按钮＋设置文字」；
   · ui-dock.js 被裁掉、或作者显式 form:'bar' 时必须回落旧形态（既有卡不能白屏）；
   · 单 pane 不出导航栏、单 entry 不出扇形（用户明确点过的两条「不必做第二层」）；
   · 设置页签全局唯一，扩展页签可多枚。
   ======================================================================= */
const DOCK_FILES = [
  'core.js', 'core-store.js', 'core-boot.js', 'theme.js', 'theme-panel.js',
  'protocol.js', 'hud.js', 'hud-render.js', 'ui.js', 'ui-panel.js',
  'ui-nav.js', 'ui-icon.js', 'ui-fan.js', 'ui-dock.js', 'ui-bubble.js',
  'ui-inject.js', 'ui-codex.js', 'ui-map.js', 'ui-stage.js'
];
/* 不含侧边栏一族的最小集：模拟作者把 ui-dock.js 等裁掉的卡 */
const NO_DOCK_FILES = [
  'core.js', 'core-store.js', 'core-boot.js', 'theme.js', 'theme-panel.js',
  'protocol.js', 'hud.js', 'hud-render.js', 'ui.js', 'ui-panel.js', 'ui-stage.js'
];
function freshDock(files = DOCK_FILES) {
  const doc = makeDoc();
  const root = buildPlatformDom(doc);
  const sdk = makeSdk();
  const W = loadKit(files, { sdk, doc });
  return { W, SBK: W.SBK, doc, root, sdk };
}
const clsAll = (doc, re) => doc.querySelectorAll('[class]').filter((n) => re.test(n.className));

async function testChromeRoutesToDock() {
  const t = group('chrome→dock 路由');
  const { SBK, doc, sdk } = freshDock();
  const api = SBK.ui.chrome({ hostId: 'sbk-hud' });
  sdk._emit('message:mount', {});
  await flush();
  t(api && typeof api.dock === 'function', 'dock 形态的 chrome 暴露 .dock() 句柄');
  const dk = api.dock();
  t(!!dk, '拿到导轨句柄');
  t(clsAll(doc, /sbk-dk\b/).length === 1, '导轨已挂载（.sbk-dk）');
  t(clsAll(doc, /sbk-chr/).length === 0,
    '🚨 旧的功能栏按钮排必须消失 —— 它正是「设置按钮镶嵌在页面里」的观感根因');
  const tabs = dk.el().childNodes.filter((n) => /sbk-dk__tab/.test(n.className));
  t(tabs.length === 1, '默认只有一枚页签（设置）');
  t(dk.hasRole('settings'), '那一枚带 role:settings');
  t(tabs[0].textContent === '', '页签是纯图标，不带文字标签');
  api.toggle();
  await flush();
  t(dk.opened() === true, 'toggle() 打开设置抽屉');
  api.toggle();
  await flush();
  t(dk.opened() === false, '再次 toggle() 收起（open(i) 对 drawer 即 toggle 语义）');
}

async function testChromeFallsBackWhenDockMissing() {
  const t = group('chrome 回落 bar');
  const { SBK, doc, sdk } = freshDock(NO_DOCK_FILES);
  const api = SBK.ui.chrome({ hostId: 'sbk-hud' });
  sdk._emit('message:mount', {});
  await flush();
  t(api && typeof api.dock !== 'function', 'ui-dock.js 缺失时不假装有 dock 句柄');
  t(clsAll(doc, /sbk-chr/).length === 1, '回落到旧的功能栏按钮组，既有卡不白屏');
  t(clsAll(doc, /sbk-btn/).some((n) => n.textContent === '\u8bbe\u7f6e'), '设置按钮仍可点');
}

async function testChromeExplicitBarForm() {
  const t = group('chrome form=bar');
  const { SBK, doc, sdk } = freshDock();
  const api = SBK.ui.chrome({ hostId: 'sbk-hud', form: 'bar' });
  sdk._emit('message:mount', {});
  await flush();
  t(api && typeof api.dock !== 'function', 'form:"bar" 即使 dock 在也不走导轨');
  t(clsAll(doc, /sbk-chr/).length === 1, '显式 bar 得到旧形态');
  t(clsAll(doc, /sbk-dk\b/).length === 0, '不应同时出现导轨');
}

async function testDockNavOnlyWhenMultiplePanes() {
  const t = group('dock 导航栏数量纪律');
  {
    const { SBK, doc, sdk } = freshDock();
    SBK.ui.chrome({ hostId: 'sbk-hud' }).toggle();
    sdk._emit('message:mount', {});
    await flush();
    t(clsAll(doc, /sbk-nav\b/).length === 0,
      '🚨 单 pane 不渲染导航栏（一格的导航栏是纯噪音）');
  }
  {
    const { SBK, doc, sdk } = freshDock();
    const api = SBK.ui.chrome({
      hostId: 'sbk-hud',
      panes: [{ label: '\u5173\u4e8e', content: () => SBK.dom.h('div', {}, 'x') }]
    });
    sdk._emit('message:mount', {});
    await flush();
    api.toggle();
    await flush();
    const nav = clsAll(doc, /sbk-nav\b/);
    t(nav.length === 1, '≥2 pane 才出现导航栏');
    const labels = nav[0].childNodes.map((b) => b.textContent);
    t(labels.length === 2 && labels[1] === '\u5173\u4e8e',
      '作者 pane 与美化 pane 并列进同一抽屉，got ' + JSON.stringify(labels));
  }
}

async function testDockEntriesBecomeOwnTabs() {
  const t = group('dock 作者 entries');
  const { SBK, sdk } = freshDock();
  let hit = 0;
  const api = SBK.ui.chrome({
    hostId: 'sbk-hud',
    entries: [{ label: '\u56fe\u9274', icon: 'book', onSelect: () => { hit++; } }]
  });
  sdk._emit('message:mount', {});
  await flush();
  const dk = api.dock();
  t(dk.count() === 2, 'entries 各自成为导轨上一枚独立页签（不塞进设置抽屉）');
  const tabs = dk.el().childNodes.filter((n) => /sbk-dk__tab/.test(n.className));
  t(tabs.length === 2, '导轨上渲染出两枚页签');
  dk.open(1);
  await flush();
  t(hit === 1, '扩展页签的 onSelect 被调用一次');
}

async function testSettingsTabStaysUnique() {
  const t = group('设置页签唯一');
  const { SBK, sdk } = freshDock();
  const api = SBK.ui.chrome({ hostId: 'sbk-hud' });
  sdk._emit('message:mount', {});
  await flush();
  const dk = api.dock();
  /* 作者再往共享导轨里塞一枚 settings：必须被拒，而不是造出两枚长得差不多的图标 */
  dk.addTab({ role: 'settings', icon: 'gear', label: '\u53c8\u4e00\u4e2a', onSelect() {} });
  await flush();
  t(dk.count() === 1, '第二枚 role:settings 被拒');
  /* 但普通扩展页签可以多枚 */
  dk.addTab({ icon: 'map', label: '\u5730\u56fe', onSelect() {} });
  dk.addTab({ icon: 'book', label: '\u56fe\u9274', onSelect() {} });
  await flush();
  t(dk.count() === 3, '扩展页签可多枚（图鉴/地图各占一枚）');
}

async function testThemeFormsAllStayInSync() {
  const t = group('多份设置表单同步');
  const { SBK, sdk } = freshDock();
  sdk._emit('message:mount', {});
  await flush();
  const p = SBK.theme.prefs;
  t(typeof p.pane === 'function', 'theme-panel 暴露可嵌入的 prefs.pane');
  const f1 = p.form(), f2 = p.form();
  const cbOf = (box) => box.querySelectorAll('input').filter((i) => i.attributes.type === 'checkbox')[0];
  const c1 = cbOf(f1), c2 = cbOf(f2);
  t(c1.checked === true && c2.checked === true, '两份表单初始都反映启用态');
  p.enabled(false);
  await flush();
  /* 🚨 回归点：原先 syncForm 是单槽，第二份表单一建就顶掉第一份的刷新函数，
     f1 会停在旧值。dock 形态下这正是「导轨里改了字号，另一份表单显示过期状态」。 */
  t(c1.checked === false && c2.checked === false,
    '所有存活表单都跟随 prefs 变化刷新，got f1=' + c1.checked + ' f2=' + c2.checked);
}

function testChromeFontTokensOnBothSurfaces() {
  const t = group('chrome 字号令牌');
  /* --sbk-cfs* 三档由【拥有面的 kit】定义：ui.js 给抽屉与浮层，ui-bubble.js 给气泡。
     消费者（ui-nav / ui-inject / ui-codex / ui-map）只写带兜底的取用，兜底值与定义一致
     → 缺了不会立刻显形，但风格包想统一调这三档时会改不到抽屉。故在源码层锁死。 */
  const ui = readFileSync(join(SBK_DIR, 'ui.js'), 'utf8');
  const bb = readFileSync(join(SBK_DIR, 'ui-bubble.js'), 'utf8');
  for (const [name, src, surface] of [['ui.js', ui, '.sbk-drw'], ['ui-bubble.js', bb, '.sbk-bb']]) {
    for (const tok of ['--sbk-cfs:', '--sbk-cfs-sm:', '--sbk-cfs-xs:']) {
      t(src.includes(tok), name + ' 为 ' + surface + ' 定义 ' + tok.slice(0, -1));
    }
  }
  t(/\.sbk-drw,\.sbk-pop\{--sbk-cfs:/.test(ui), '抽屉与浮层共用同一处三档定义');
  /* 兜底值必须与定义值一致，否则「缺定义」会变成静默的字号漂移 */
  const defs = { '--sbk-cfs': '15px', '--sbk-cfs-sm': '13px', '--sbk-cfs-xs': '12px' };
  for (const f of ['ui-nav.js', 'ui-inject.js', 'ui-codex.js', 'ui-map.js', 'ui.js']) {
    const src = readFileSync(join(SBK_DIR, f), 'utf8');
    for (const m of src.matchAll(/var\((--sbk-cfs[a-z-]*),\s*([^)]+)\)/g)) {
      t(defs[m[1]] === m[2].trim(), f + ' 的 ' + m[1] + ' 兜底值须为 ' + defs[m[1]],
        'got ' + m[2].trim());
    }
  }
}

function testSidebarModulesExposeApi() {
  const t = group('侧边栏一族 API 面');
  const { SBK } = freshDock();
  for (const k of ['nav', 'icon', 'icons', 'fan', 'dock', 'bubble', 'inject', 'codex', 'map']) {
    t(SBK.ui[k] !== undefined, 'SBK.ui.' + k + ' 已导出');
  }
  t(typeof SBK.ui.dock === 'function', 'dock 是工厂函数');
  t(typeof SBK.ui.nav === 'function', 'nav 是工厂函数');
  /* 图标名表与 build_sbk.py 的 CHROME_ICONS 白名单必须同源，否则生成期放过的
     图标名到运行时才回落 gear，而真机没有控制台可看告警。 */
  const names = SBK.ui.icons();
  for (const n of ['gear', 'wrench', 'tools', 'sliders', 'map', 'book', 'spark', 'dots']) {
    t(names.indexOf(n) >= 0, '图标表含 ' + n + '（与 build_sbk.CHROME_ICONS 对齐）');
  }
}

/* =======================================================================
   汇总
   ======================================================================= */
async function main() {
  testStateDeepClone();
  testStateCircularSafe();
  testConversationSwitch();
  testEventPayloadIsolation();
  testStoreMerge();
  testStoreLoadAfterThrottle();
  testStoreMergeThinPreview();
  testThemeRuntimeContracts();
  testSchemaPersist();
  testHostId();
  testMountHostDedupe();
  await testPanelOpenThenCloseBeforeMount();
  await testPanelOpenThenDestroyBeforeMount();
  await testPanelOpenBeforeMountCompletes();
  await testStageOpenThenClose();
  await testStageOpenThenDestroy();
  await testStageDestroyWhileVisible();
  await testStageRebuildAfterClose();
  await testStagePlatformCloseCancelsQueue();
  testTypedEntitiesNoNaN();
  testOtherTypesNoGarbage();
  testNewTypes();
  testUnknownType();
  await testChromeRoutesToDock();
  await testChromeFallsBackWhenDockMissing();
  await testChromeExplicitBarForm();
  await testDockNavOnlyWhenMultiplePanes();
  await testDockEntriesBecomeOwnTabs();
  await testSettingsTabStaysUnique();
  await testThemeFormsAllStayInSync();
  testChromeFontTokensOnBothSurfaces();
  testSidebarModulesExposeApi();
  testSourceInvariants();

  console.log('\nSBK runtime tests');
  console.log('  passed: ' + pass);
  console.log('  failed: ' + fails.length);
  if (fails.length) {
    console.log('\nFAILURES:');
    for (const f of fails) console.log('  - ' + f);
    process.exit(1);
  }
  console.log('\nAll green.');
}
main().catch((e) => { console.error('harness crashed:', e); process.exit(2); });
