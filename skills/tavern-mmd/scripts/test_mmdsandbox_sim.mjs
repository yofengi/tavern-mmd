/* mmdsandbox-sim.js 回归测试。零依赖：只用 node:assert / node:test / node:vm。
 * 运行：node --test scripts/test_mmdsandbox_sim.mjs
 *   或：node scripts/test_mmdsandbox_sim.mjs（node:test 内建 runner 自动接管）
 *
 * 覆盖：事件顺序、late replay、thin 错误语义、message scope、stage、theme、switch、
 *       payload 4 键、契约与 fixtures/mmdsandbox/contract.json 对撞。
 */
import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { makeDocumentClass, buildPanoramaDom } from "./fixtures/mmdsandbox/fake-dom.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SIM_SRC = fs.readFileSync(path.join(HERE, "mmdsandbox-sim.js"), "utf8");
const CONTRACT = JSON.parse(
  fs.readFileSync(path.join(HERE, "fixtures", "mmdsandbox", "contract.json"), "utf8"));

/* 起一个仿真环境。
 * domFirst=false 复现实机时序：模拟器与作者脚本先跑，气泡 DOM 之后才存在。 */
function boot({ profile = "chat", config = {}, authorScript = null,
                greeting = "开场白正文", domFirst = false } = {}) {
  // 每个环境一个新 Document 类：模拟器要改写 Document.prototype，共用会串态。
  const FakeDocument = makeDocumentClass();
  const doc = new FakeDocument();
  const timers = [];
  const win = {
    document: doc,
    Document: FakeDocument,
    console: { log() {} },
    Promise,
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    __MMD_SANDBOX_SIM_CONFIG__: { profile, greeting, ...config },
  };
  win.window = win;
  win.globalThis = win;
  const ctx = vm.createContext(win);

  if (domFirst) buildPanoramaDom(doc, greeting);
  vm.runInContext(SIM_SRC, ctx, { filename: "mmdsandbox-sim.js" });

  // 作者脚本在 hoisted 位置执行：此刻 sdk 必须已在位，而气泡 DOM 尚未解析。
  const authorView = {};
  if (authorScript) authorScript(win, authorView);

  const dom = domFirst ? null : buildPanoramaDom(doc, greeting);
  doc.readyState = "complete";
  doc._fire("DOMContentLoaded");
  timers.splice(0).forEach((fn) => fn());

  return { win, doc, dom, DocumentClass: FakeDocument,
           sim: win.__MMD_SANDBOX_SIM__, sdk: win.sdk, authorView,
           control: win.__MMD_SANDBOX_SIM__.control };
}

test("sdk 在作者脚本执行时已就位，顶层恰 11 键且无 once/off", () => {
  let keys = null;
  let sdkAtTopLevel = null;
  boot({
    authorScript(win) {
      sdkAtTopLevel = win.sdk;
      keys = Object.keys(win.sdk).sort();
    },
  });
  assert.ok(sdkAtTopLevel, "作者脚本顶层必须已能拿到 window.sdk");
  assert.deepEqual(keys, ["cache", "composer", "debug", "input", "message", "on",
                          "role", "save", "stage", "user", "version"]);
  assert.equal(keys.length, 11);
  assert.equal(sdkAtTopLevel.once, undefined);
  assert.equal(sdkAtTopLevel.off, undefined);
  // 🚨 version 是字符串 '1'：作者写 sdk.version === 1 会永远为假。
  assert.equal(sdkAtTopLevel.version, "1");
  assert.equal(typeof sdkAtTopLevel.version, "string");
  assert.equal(Object.isFrozen(sdkAtTopLevel), false);
});

test("契约与模拟器的 sdk.version 都是字符串 '1'", () => {
  const { sdk } = boot();
  assert.equal(CONTRACT.sdk.version, "1");
  assert.equal(typeof CONTRACT.sdk.version, "string");
  assert.equal(CONTRACT.sdk.versionIsString, true);
  assert.equal(sdk.version, CONTRACT.sdk.version);
});

test("作者脚本顶层查不到气泡 DOM（实机 toplevel_found_pbOut=false）", () => {
  const { authorView } = boot({
    authorScript(win, view) {
      view.topLevelBubble = win.document.querySelector('[data-chat="message-body"]');
    },
  });
  assert.equal(authorView.topLevelBubble, null);
});

test("冷启动事件顺序严格为 new -> mount -> done -> ready", () => {
  const seen = [];
  const { control } = boot({
    authorScript(win) {
      ["message:new", "message:mount", "message:done", "ready"].forEach((ev) => {
        win.sdk.on(ev, () => seen.push(ev));
      });
    },
  });
  assert.deepEqual(seen, ["message:new", "message:mount", "message:done", "ready"]);
  // control.* 的返回值来自 vm realm，跨 realm 原型不同 → 复制进宿主数组再比。
  assert.deepEqual(Array.from(control.eventOrder()).slice(0, 4),
                   CONTRACT.events.coldStartOrder);
  assert.equal(seen[seen.length - 1], "ready", "ready 必须最后到");
});

test("payload 恰 4 键，开场白 id=greeting 且 serverId=null", () => {
  const got = [];
  boot({
    authorScript(win) {
      ["message:new", "message:mount", "message:done"].forEach((ev) => {
        win.sdk.on(ev, (p) => got.push([ev, p]));
      });
      win.sdk.on("ready", (p) => got.push(["ready", p]));
    },
    greeting: "测试-第一句话",
  });
  for (const [ev, p] of got.filter(([e]) => e !== "ready")) {
    assert.deepEqual(Object.keys(p).sort(), ["content", "id", "role", "serverId"], ev);
    assert.equal(p.content, "测试-第一句话");
    assert.equal(p.id, "greeting");
    assert.equal(p.role, "ai");
    assert.equal(p.serverId, null);
  }
  const ready = got.find(([e]) => e === "ready");
  assert.equal(ready[1], undefined, "ready 载荷为 undefined");
});

test("回调只收 1 个实参（实机 argcount=1）", () => {
  let argc = -1;
  boot({ authorScript(win) { win.sdk.on("message:mount", function () { argc = arguments.length; }); } });
  assert.equal(argc, 1);
});

test("mount/done 对晚订阅补发，ready 绝不补发", () => {
  const { sdk } = boot();
  const late = [];
  sdk.on("message:mount", (p) => late.push(["mount", p.id]));
  sdk.on("message:done", (p) => late.push(["done", p.id]));
  sdk.on("ready", () => late.push(["ready", null]));
  assert.deepEqual(late, [["mount", "greeting"], ["done", "greeting"]]);
  assert.ok(!late.some(([k]) => k === "ready"), "ready 不得补发");
});

test("sdk.on 返回 undefined，订阅不可撤销", () => {
  const { sdk } = boot();
  assert.equal(sdk.on("message:done", () => {}), undefined);
});

test("未知事件名不抛错、永不触发，并留诊断", () => {
  const { sdk, control } = boot();
  let fired = false;
  assert.equal(sdk.on("message:finished", () => { fired = true; }), undefined);
  control.addAI("x");
  assert.equal(fired, false);
  assert.ok(control.diagnose().warnings.some((w) => w.includes("永不触发")));
});

/* ================= thin-preview profile ================= */

test("thin：save.get / save.keys 同步抛带 code 的 SdkError", () => {
  const { sdk } = boot({ profile: "thin-preview" });
  for (const call of [() => sdk.save.get("k"), () => sdk.save.keys()]) {
    let caught = null;
    try { call(); } catch (e) { caught = e; }
    assert.ok(caught, "必须同步抛，不能返回 Promise");
    assert.equal(caught.name, "SdkError");
    assert.equal(caught.code, "NOT_SUPPORTED");
  }
});

test("thin：store.load() 式 try/catch 能兜住，不炸整卡", () => {
  let loaded = "fallback";
  const { authorView } = boot({
    profile: "thin-preview",
    authorScript(win, view) {
      try { loaded = win.sdk.save.get("hp"); } catch (e) { view.code = e.code; }
    },
  });
  assert.equal(loaded, "fallback");
  assert.equal(authorView.code, "NOT_SUPPORTED");
});

test("thin：只有 4 个异步能力返回 rejected Promise", async () => {
  const { sdk } = boot({ profile: "thin-preview" });
  const asyncWrites = [
    ["message.send", () => sdk.message.send("x")],
    ["message.edit", () => sdk.message.edit("s1", "x")],
    ["save.set", () => sdk.save.set("k", 1)],
    ["save.remove", () => sdk.save.remove("k")],
  ];
  assert.deepEqual(asyncWrites.map(([n]) => n).sort(),
                   [...CONTRACT.sdk.asyncCapabilities].sort());
  for (const [name, call] of asyncWrites) {
    const p = call();
    assert.equal(typeof p.then, "function", `${name} 必须返回 Promise`);
    await p.then(
      () => { throw new Error(`${name} 不该 resolve`); },
      (e) => { assert.equal(e.code, "NOT_SUPPORTED", name); });
  }
});

test("thin：同步 void 能力按签名同步抛，绝不返回 rejected Promise", () => {
  const { sdk } = boot({ profile: "thin-preview" });
  const syncWrites = [
    ["input.set", () => sdk.input.set("x")],
    ["input.add", () => sdk.input.add("x")],
    ["input.insert", () => sdk.input.insert("x")],
    ["input.clear", () => sdk.input.clear()],
    ["input.focus", () => sdk.input.focus()],
    ["input.blur", () => sdk.input.blur()],
    ["input.setCursor", () => sdk.input.setCursor(1)],
    ["composer.show", () => sdk.composer.show()],
    ["composer.hide", () => sdk.composer.hide()],
    ["cache.set", () => sdk.cache.set("k", 1)],
    ["cache.remove", () => sdk.cache.remove("k")],
  ];
  for (const [name, call] of syncWrites) {
    let caught = null;
    try { call(); } catch (e) { caught = e; }
    assert.ok(caught, `${name} 必须同步抛，不能返回 rejected Promise`);
    assert.equal(caught.name, "SdkError", name);
    assert.equal(caught.code, "NOT_SUPPORTED", name);
    // 这些能力不在异步名单里，签名就是同步 void。
    assert.ok(!CONTRACT.sdk.asyncCapabilities.includes(name), name);
  }
});

test("chat：同步 void 能力返回 undefined，不是 Promise", () => {
  const { sdk, dom } = boot({ profile: "chat" });
  const syncCalls = [
    ["input.set", () => sdk.input.set("abc")],
    ["input.add", () => sdk.input.add("d")],
    ["input.insert", () => sdk.input.insert("!")],
    ["input.focus", () => sdk.input.focus()],
    ["input.blur", () => sdk.input.blur()],
    ["input.setCursor", () => sdk.input.setCursor(1)],
    ["input.clear", () => sdk.input.clear()],
    ["composer.show", () => sdk.composer.show()],
    ["composer.hide", () => sdk.composer.hide()],
    ["cache.set", () => sdk.cache.set("k", 1)],
    ["cache.remove", () => sdk.cache.remove("k")],
    ["stage.open", () => sdk.stage.open()],
    ["stage.close", () => sdk.stage.close()],
  ];
  for (const [name, call] of syncCalls) {
    const out = call();
    assert.equal(out, undefined, `${name} 必须同步返回 undefined`);
  }
  // 同步写确实生效（不是空实现）。
  sdk.input.set("hello");
  assert.equal(dom.textarea.value, "hello");
  assert.equal(sdk.input.get(), "hello");
});

test("chat：message.send 是 Promise<void>，不回传 payload", async () => {
  const { sdk } = boot({ profile: "chat" });
  const p = sdk.message.send("你好");
  assert.equal(typeof p.then, "function");
  const value = await p;
  // 实机签名 Promise<void>：回传 payload 会让作者以为能从 send() 读 id/serverId。
  assert.equal(value, undefined);
  assert.equal(CONTRACT.sdk.messageSendReturns, "Promise<void>");
});

test("message.edit 空 serverId 用 INVALID_ARGS 错误码", async () => {
  const { sdk } = boot();
  await sdk.message.edit(null, "x").then(
    () => { throw new Error("不该 resolve"); },
    (e) => {
      assert.equal(e.code, "INVALID_ARGS");
      assert.ok(CONTRACT.sdk.errorCodes.known.includes("INVALID_ARGS"));
    });
});

test("chat：save key 非法以 Promise 拒绝 INVALID_ARGS", async () => {
  const { sdk } = boot({ profile: "chat" });
  for (const bad of ["a".repeat(65), "a:b", 123]) {
    const p = sdk.save.set(bad, 1);
    assert.equal(typeof p.then, "function", "save.set 的签名始终是 Promise<void>");
    await p.then(
      () => { throw new Error("非法 save key 不该 resolve"); },
      (e) => assert.equal(e.code, "INVALID_ARGS"));
  }
});

test("thin：cache.get 返回 undefined 且不抛；读类 input 给实测降级值", () => {
  const { sdk } = boot({ profile: "thin-preview" });
  assert.equal(sdk.cache.get("k"), undefined);
  assert.equal(sdk.input.get(), "");
  assert.equal(sdk.input.getCursor(), 0);
});

test("thin：composer.visible 为 true，stage 可用", () => {
  const { sdk, control } = boot({ profile: "thin-preview" });
  assert.equal(sdk.composer.visible(), true);
  assert.equal(sdk.stage.visible(), false);
  assert.equal(sdk.stage.el().tagName, "DIV", "关闭时仍返回 DIV");
  sdk.stage.open();
  assert.equal(sdk.stage.visible(), true);
  sdk.stage.close();
  assert.equal(sdk.stage.visible(), false);
  assert.equal(control.diagnose().profile, "thin-preview");
});

test("thin：role/user 返回真实形状字段", () => {
  const { sdk } = boot({ profile: "thin-preview" });
  assert.deepEqual(Object.keys(sdk.role.get()).sort(), ["avatarUrl", "name"]);
  assert.deepEqual(Object.keys(sdk.user.get()).sort(), ["avatarUrl", "nickname"]);
});

test("chat：save/cache 在本页内可持久", () => {
  const { sdk } = boot({ profile: "chat" });
  return Promise.all([sdk.save.set("hp", 85), sdk.cache.set("tmp", 7)]).then(() => {
    assert.equal(sdk.save.get("hp"), 85);
    assert.deepEqual(Array.from(sdk.save.keys()), ["hp"]);
    assert.equal(sdk.cache.get("tmp"), 7);
  });
});

test("chat：save key 限制的错误信息说清是长度还是冒号", async () => {
  // save.set 是异步能力：非法 key 走 rejected Promise，不能同步抛。
  // 这条只额外核对错误**信息**能区分两种成因（上一条核对 code）。
  const { sdk } = boot({ profile: "chat" });
  const cases = [["a".repeat(65), /64/], ["a:b", /:/]];
  for (const [bad, pattern] of cases) {
    await sdk.save.set(bad, 1).then(
      () => { throw new Error("不该 resolve"); },
      (e) => assert.match(String(e.message), pattern));
  }
  await sdk.save.remove("a:b").then(
    () => { throw new Error("不该 resolve"); },
    (e) => assert.equal(e.code, "INVALID_ARGS"));
});

/* ================= message scope ================= */

test("mount 回调内能查到本气泡内元素，回调后查不到", () => {
  const view = {};
  const { doc } = boot({
    authorScript(win) {
      win.sdk.on("message:mount", () => {
        view.inCallback = win.document.querySelector("#author-node");
        view.byId = win.document.getElementById("author-node");
        view.rootInCallback = win.document.querySelector('[data-chat="root"]');
        view.statusbarInCallback = win.document.querySelector('[data-slot="statusbar"]');
      });
    },
  });
  assert.ok(view.inCallback, "mount 回调内必须查到气泡内元素");
  assert.ok(view.byId, "getElementById 同样收窄");
  assert.ok(view.rootInCallback, "平台 root 在回调内可达（实测 qs_from_document_works=true）");
  assert.ok(view.statusbarInCallback, "功能栏在回调内可达");
  // 回调之后：气泡内元素不可见，平台节点仍可查。
  assert.equal(doc.querySelector("#author-node"), null);
  assert.equal(doc.getElementById("author-node"), null);
  assert.ok(doc.querySelector('[data-chat="root"]'));
  assert.ok(doc.querySelector('[data-slot="statusbar"]'));
  assert.ok(doc.querySelector('[data-chat="composer"]'));
});

test("收窄不破坏 Element.querySelector", () => {
  const { doc, dom } = boot();
  // Document 级查不到，但 Element 级（含 body）仍能查到 —— 与实机一致。
  assert.equal(doc.querySelector("#author-node"), null);
  assert.ok(doc.body.querySelector("#author-node"));
  assert.ok(dom.bubble.querySelector('[data-chat="message-body"]'));
});

test("scope 可开关且有诊断计数", () => {
  const { doc, control } = boot();
  assert.equal(control.diagnose().scopeInstalled, true);
  assert.equal(control.diagnose().scopeBlockedCount, 0, "还没查过气泡内元素，不该有拦截");
  assert.equal(doc.querySelector("#author-node"), null);
  assert.ok(control.diagnose().scopeBlockedCount > 0, "回调外查气泡内元素应被记录");
  control.setScope(false);
  assert.ok(doc.querySelector("#author-node"), "关掉收窄后气泡内元素可查");
  control.setScope(true);
  assert.equal(doc.querySelector("#author-node"), null);
});

test("scope 在 async 回调跨 await 后立即失效", async () => {
  let during = null;
  let after = null;
  boot({
    authorScript(win) {
      win.sdk.on("message:mount", async () => {
        during = win.document.querySelector('[data-chat="message-body"]');
        await Promise.resolve();
        after = win.document.querySelector('[data-chat="message-body"]');
      });
    },
  });
  await Promise.resolve();
  assert.ok(during, "同步回调期间应能查到当前气泡");
  assert.equal(after, null, "跨 await 后游标失效，不能再查询气泡内节点");
});

test("stream/done 回调期间同样收窄，且 stream 载荷 4 键", () => {
  const seen = [];
  const { control } = boot({
    authorScript(win) {
      win.sdk.on("message:stream", (p) => {
        const node = win.document.querySelector('[data-chat="message-body"]');
        // 就地读文本：node 是活引用，下一块会把同一节点改掉，回调后再读只剩末值。
        seen.push([p, !!node, node ? node.textContent : null]);
      });
    },
  });
  control.stream(["你", "好"]);
  assert.equal(seen.length, 2);
  for (const [p, found, text] of seen) {
    assert.deepEqual(Object.keys(p).sort(), ["content", "id", "role", "serverId"]);
    assert.ok(found, "stream 回调内应能查到本气泡 body");
    // 关键：查到的必须是**本条流式气泡**的 body，不是文档里第一条（开场白）的。
    assert.equal(text, p.content, "收窄应先在游标气泡内查，否则会拿到开场白那条");
  }
  assert.equal(seen[0][0].content, "你");
  assert.equal(seen[1][0].content, "你好");
  const donePayload = control.done();
  assert.equal(donePayload.content, "你好");
});

/* ================= stage / theme / switch / viewport ================= */

test("stage.el 关闭时仍返回 DIV，只有 visible 判开关", () => {
  const { sdk } = boot();
  assert.equal(sdk.stage.visible(), false);
  const el = sdk.stage.el();
  assert.ok(el);
  assert.equal(el.tagName, "DIV");
  sdk.stage.open();
  assert.equal(sdk.stage.visible(), true);
  assert.equal(sdk.stage.el().tagName, "DIV");
});

test("sdk.stage.close 不派 stage:close；平台关闭才派", () => {
  const events = [];
  const { sdk, control } = boot({
    authorScript(win) { win.sdk.on("stage:close", () => events.push("stage:close")); },
  });
  sdk.stage.open();
  sdk.stage.close();
  assert.deepEqual(events, [], "sdk.stage.close() 绝不派发 stage:close");
  control.stageClose();
  assert.deepEqual(events, ["stage:close"]);
});

test("theme 改 root data-theme 并派 theme:change", () => {
  const payloads = [];
  const { dom, control } = boot({
    authorScript(win) { win.sdk.on("theme:change", (p) => payloads.push(p)); },
  });
  assert.equal(dom.root.getAttribute("data-theme"), "light");
  assert.equal(control.theme("dark"), "dark");
  assert.equal(dom.root.getAttribute("data-theme"), "dark");
  assert.deepEqual(payloads, ["dark"]);
  control.theme();                       // 不传参 = 切换
  assert.equal(dom.root.getAttribute("data-theme"), "light");
  assert.deepEqual(payloads, ["dark", "light"]);
});

test("switch 清消息与 replay 历史，但订阅仍在", () => {
  const hits = [];
  const { dom, sdk, control } = boot({
    authorScript(win) {
      win.sdk.on("conversation:switch", (id) => hits.push(["switch", id]));
      win.sdk.on("message:mount", (p) => hits.push(["mount", p.id]));
    },
  });
  assert.equal(hits.filter(([k]) => k === "mount").length, 1);
  control.switchConversation("conv-2");
  assert.ok(hits.some(([k, v]) => k === "switch" && v === "conv-2"));
  assert.equal(dom.list.childNodes.length, 0, "消息列表被清空");
  // replay 历史清掉：新的晚订阅者不该收到上一会话的 mount。
  const late = [];
  sdk.on("message:mount", (p) => late.push(p.id));
  assert.deepEqual(late, []);
  // 旧订阅仍在（无 off）：新消息照样送达。
  control.addAI("新会话第一句");
  assert.ok(hits.some(([k]) => k === "mount" && hits.length > 2));
});

test("键盘/视口控制改 --chat-viewport-height", () => {
  const { dom, control } = boot({ config: { viewportHeight: 1205 } });
  control.setViewportHeight(900);
  assert.equal(dom.root.style.getPropertyValue("--chat-viewport-height"), "900px");
  control.setKeyboardInset(305);
  assert.equal(dom.root.style.getPropertyValue("--chat-viewport-height"), "900px");
});

test("back / dispose / unmountLast 都派对应事件", () => {
  const evs = [];
  const { control } = boot({
    authorScript(win) {
      ["back", "dispose", "message:unmount"].forEach((e) =>
        win.sdk.on(e, () => evs.push(e)));
    },
  });
  control.back();
  control.unmountLast();
  control.dispose();
  assert.deepEqual(evs, ["back", "message:unmount", "dispose"]);
});

test("两条气泡下，回调内 document 查询根命中的是**当前**气泡", () => {
  // 内核桥接层就是这样拿气泡根的：document.querySelector('[data-chat="message"]')。
  // 少了「游标自身命中」这一步会穿到全文档、拿到第一条气泡 → 桥接层认错 root。
  const roots = [];
  const { control, dom } = boot({
    authorScript(win) {
      win.sdk.on("message:mount", () => {
        roots.push(win.document.querySelector('[data-chat="message"]'));
      });
    },
  });
  // 第一条是开场白气泡。
  assert.equal(roots.length, 1);
  assert.equal(roots[0], dom.bubble);
  // 再追加一条：此时文档里有两条气泡，回调必须拿到新那条。
  control.addAI("第二条");
  assert.equal(roots.length, 2);
  assert.notEqual(roots[1], dom.bubble, "不能再拿到开场白那条");
  assert.equal(roots[1].getAttribute("data-msg-id"), "sim-1");
  assert.equal(roots[1].querySelector('[data-chat="message-body"]').textContent, "第二条");
});

test("两条气泡下，回调内查气泡内元素归属的是当前气泡", () => {
  // 断言**归属关系**而不是文本：收窄要保证拿到的 body 属于当前气泡，
  // 而不是文档里第一条。（文本断言会被假 DOM 的文本节点模型干扰，且不是本测试重点。）
  const pairs = [];
  const { control } = boot({
    authorScript(win) {
      win.sdk.on("message:mount", () => {
        const bubble = win.document.querySelector('[data-chat="message"]');
        const body = win.document.querySelector('[data-chat="message-body"]');
        pairs.push({ bubble, body, sameOwner: !!body && body.parentNode === bubble });
      });
    },
  });
  control.addAI("第二条");
  control.addAI("第三条");
  assert.equal(pairs.length, 3);
  const ids = new Set();
  for (const { bubble, body, sameOwner } of pairs) {
    assert.ok(body, "回调内必须查到 body");
    assert.ok(sameOwner, "查到的 body 必须属于当前气泡，而不是文档第一条");
    ids.add(bubble.getAttribute("data-msg-id"));
  }
  assert.equal(ids.size, 3, "三次 mount 应对应三条不同气泡");
});

test("querySelectorAll 在游标内只返回当前气泡内元素，平台节点仍可见", () => {
  let seen = null;
  const { control } = boot({
    authorScript(win) {
      win.sdk.on("message:mount", () => {
        const bubbles = win.document.querySelectorAll('[data-chat="message"]');
        seen = {
          bodies: win.document.querySelectorAll('[data-chat="message-body"]').length,
          roots: win.document.querySelectorAll('[data-chat="root"]').length,
          bubbles,
        };
      });
    },
  });
  control.addAI("第二条");
  // 气泡内元素：只看到当前那一条（另一条被收窄挡掉）。
  assert.equal(seen.bodies, 1);
  // 当前气泡根自身也必须作为 scope 查询结果返回，不能泄漏到第一条。
  assert.equal(seen.bubbles.length, 1);
  assert.equal(seen.bubbles[0].getAttribute("data-msg-id"), "sim-1");
  // 平台节点不受收窄影响。
  assert.equal(seen.roots, 1);
});

test("message:unmount 无载荷（不伪装 4 键）", () => {
  const payloads = [];
  const { control } = boot({
    authorScript(win) { win.sdk.on("message:unmount", (p) => payloads.push(p)); },
  });
  control.unmountLast();
  assert.equal(payloads.length, 1);
  assert.equal(payloads[0], undefined, "官方事件表无载荷，绝不能伪造 msg.content");
  assert.equal(CONTRACT.eventPayloads["message:unmount"].shape, "undefined");
  assert.equal(CONTRACT.eventPayloads["message:unmount"].accuracy, "exact");
});

test("幂等：重复执行模拟器脚本不重复安装", () => {
  const { win, control } = boot();
  const before = control.eventOrder().length;
  vm.runInContext(SIM_SRC, vm.createContext(win), { filename: "again.js" });
  assert.equal(win.__MMD_SANDBOX_SIM__.control.eventOrder().length, before);
});

/* ================= 与 contract.json 对撞 ================= */

test("模拟器契约表与 fixtures/mmdsandbox/contract.json 一致", () => {
  const { sim, control } = boot();
  const c = control.diagnose();
  assert.equal(sim.contract.version, CONTRACT.contractVersion);
  assert.deepEqual(Array.from(c.events).sort(), [...CONTRACT.events.names].sort());
  assert.equal(c.events.length, CONTRACT.events.count);
  assert.deepEqual(Array.from(c.replayEvents).sort(),
                   [...CONTRACT.events.lateReplay.replayed].sort());
  assert.deepEqual(Array.from(c.coldStartOrder), CONTRACT.events.coldStartOrder);
  assert.deepEqual(Array.from(c.payloadKeys), CONTRACT.events.payload.keys);
  assert.equal(c.payloadKeys.length, CONTRACT.events.payload.keyCount);
  // 30 个能力名逐一对齐，且 accuracy 取值合法。
  const simCaps = Object.keys(c.accuracy).sort();
  assert.deepEqual(simCaps, Object.keys(CONTRACT.capabilities).sort());
  assert.equal(simCaps.length, CONTRACT.sdk.capabilityCount);
  const levels = Object.keys(CONTRACT.accuracyLevels);
  for (const [name, level] of Object.entries(c.accuracy)) {
    assert.ok(levels.includes(level), `${name} 的 accuracy ${level} 不在契约等级内`);
  }
});

test("chat profile 下 accuracy 与契约逐项相同", () => {
  const { control } = boot({ profile: "chat" });
  for (const [name, level] of Object.entries(control.diagnose().accuracy)) {
    assert.equal(level, CONTRACT.capabilities[name].accuracy, name);
  }
});

test("thin profile 把未探到的 cache 写操作降级为 probe-needed", () => {
  const { control } = boot({ profile: "thin-preview" });
  const acc = control.diagnose().accuracy;
  assert.equal(acc["cache.set"], "probe-needed");
  assert.equal(acc["cache.remove"], "probe-needed");
  // 实测项不许被降级。
  assert.equal(acc["save.get"], "exact");
  assert.equal(acc["cache.get"], "exact");
  assert.equal(acc["composer.visible"], "exact");
});

test("契约声明 ready 无 late replay、裸字面量政策为 ERROR", () => {
  assert.deepEqual(CONTRACT.events.lateReplay.notReplayed, ["ready"]);
  assert.equal(CONTRACT.regexPipeline.patternPolicy.delivery, "slash");
  assert.equal(CONTRACT.regexPipeline.patternPolicy.severity, "ERROR");
  assert.equal(CONTRACT.regexPipeline.outputBudget.floor, 262144);
  assert.equal(CONTRACT.regexPipeline.outputBudget.inputMultiplier, 4);
  assert.equal(CONTRACT.cssContract.tokenCount, 14);
  assert.equal(CONTRACT.cssContract.designTokens.length, 14);
});
