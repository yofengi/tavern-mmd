/* fixtures/mmdsandbox/fake-dom.mjs
 * 给 mmdsandbox-sim.js 用的最小假 DOM 测试支撑。零依赖（不引 jsdom 等 npm 包），
 * 只实现模拟器与 Node 测试需要的子集；使用者是 test_mmdsandbox_sim.mjs。
 *
 * 关键点：Document.prototype 上必须有那 5 个查询方法（模拟器要改写它们），
 * 而 Element 上的 querySelector 必须是**独立实现**——否则测不出「只改 Document、
 * 不破坏 Element.querySelector」这条契约。 */

const ATTR = /\[([a-zA-Z_:][-\w:.]*)(?:=(?:"([^"]*)"|'([^']*)'|([^\]]*)))?\]/g;

function parseCompound(sel) {
  const parts = { tag: null, id: null, classes: [], attrs: [] };
  let rest = String(sel).trim();
  rest = rest.replace(ATTR, (_m, name, dq, sq, bare) => {
    parts.attrs.push([name, dq !== undefined ? dq : sq !== undefined ? sq : bare]);
    return "";
  });
  const tokens = rest.match(/[.#]?[^.#]+/g) || [];
  for (const tok of tokens) {
    if (tok.startsWith("#")) parts.id = tok.slice(1);
    else if (tok.startsWith(".")) parts.classes.push(tok.slice(1));
    else if (tok.trim()) parts.tag = tok.trim().toLowerCase();
  }
  return parts;
}

export class FakeStyle {
  constructor() { this.props = Object.create(null); }
  setProperty(k, v) { this.props[k] = String(v); }
  getPropertyValue(k) { return this.props[k] === undefined ? "" : this.props[k]; }
}

export class FakeElement {
  constructor(tagName, doc) {
    this.tagName = String(tagName).toUpperCase();
    this.nodeType = 1;
    this.ownerDocument = doc;
    this.childNodes = [];
    this.parentNode = null;
    this.style = new FakeStyle();
    this._attrs = new Map();
    this._text = "";
    this._listeners = new Map();
    this.scrollTop = 0;
    this.scrollHeight = 100;
    this.value = "";
    this.selectionStart = 0;
  }

  get className() { return this.getAttribute("class") || ""; }
  set className(v) { this.setAttribute("class", v); }

  setAttribute(name, value) { this._attrs.set(String(name), String(value)); }
  getAttribute(name) {
    const v = this._attrs.get(String(name));
    return v === undefined ? null : v;
  }
  removeAttribute(name) { this._attrs.delete(String(name)); }
  hasAttribute(name) { return this._attrs.has(String(name)); }

  appendChild(node) {
    node.parentNode = this;
    this.childNodes.push(node);
    return node;
  }
  removeChild(node) {
    const i = this.childNodes.indexOf(node);
    if (i >= 0) { this.childNodes.splice(i, 1); node.parentNode = null; }
    return node;
  }

  get textContent() {
    if (!this.childNodes.length) return this._text;
    return this.childNodes.map((c) => c.textContent).join("");
  }
  set textContent(v) {
    this.childNodes.forEach((c) => { c.parentNode = null; });
    this.childNodes = [];
    this._text = String(v);
  }

  matches(sel) {
    const p = parseCompound(sel);
    if (p.tag && this.tagName.toLowerCase() !== p.tag) return false;
    if (p.id && this.getAttribute("id") !== p.id) return false;
    for (const c of p.classes) {
      if (!this.className.split(/\s+/).includes(c)) return false;
    }
    for (const [name, want] of p.attrs) {
      if (!this.hasAttribute(name)) return false;
      if (want !== undefined && this.getAttribute(name) !== want) return false;
    }
    return true;
  }

  _descendants(out = []) {
    for (const c of this.childNodes) {
      if (c.nodeType === 1) { out.push(c); c._descendants(out); }
    }
    return out;
  }

  // Element 级查询：始终原生，模拟器不得改写它。
  querySelector(sel) {
    return this._descendants().find((n) => n.matches(sel)) || null;
  }
  querySelectorAll(sel) {
    return this._descendants().filter((n) => n.matches(sel));
  }

  addEventListener(type, fn) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(fn);
  }
  _fire(type, ev = {}) {
    (this._listeners.get(type) || []).forEach((fn) => fn(ev));
  }
  focus() { this._focused = true; }
  blur() { this._focused = false; }
  setSelectionRange(a) { this.selectionStart = a; }
}

/* 🚨 每个仿真环境必须拿到**全新的 Document 类**。
 * 模拟器按实机方式改写 Document.prototype 的 5 个查询方法；若多个 boot() 共用同一个类，
 * 第二次改写会把第一次的补丁当成 native 存起来，闭包里的 cursor/document 全是上一个
 * 环境的 —— 单测单跑能过、连跑就串。真机每个 iframe realm 各改写一次，故这里按 realm 造类。 */
export function makeDocumentClass() {
  class FakeDocument {
    constructor() {
      this.nodeType = 9;
      this.readyState = "loading";
      this._listeners = new Map();
      this.documentElement = new FakeElement("html", this);
      this.body = new FakeElement("body", this);
      this.documentElement.appendChild(this.body);
    }
    createElement(tag) { return new FakeElement(tag, this); }
    addEventListener(type, fn) {
      if (!this._listeners.has(type)) this._listeners.set(type, []);
      this._listeners.get(type).push(fn);
    }
    _fire(type, ev = {}) {
      (this._listeners.get(type) || []).slice().forEach((fn) => fn(ev));
    }
    _all() { return this.documentElement._descendants([this.documentElement]); }
  }

  // 这 5 个必须挂在 prototype 上，模拟器要按实机方式改写 prototype。
  FakeDocument.prototype.querySelector = function (sel) {
    return this._all().find((n) => n.matches(sel)) || null;
  };
  FakeDocument.prototype.querySelectorAll = function (sel) {
    return this._all().filter((n) => n.matches(sel));
  };
  FakeDocument.prototype.getElementById = function (id) {
    return this._all().find((n) => n.getAttribute("id") === String(id)) || null;
  };
  FakeDocument.prototype.getElementsByClassName = function (cls) {
    return this._all().filter((n) => n.className.split(/\s+/).includes(String(cls)));
  };
  FakeDocument.prototype.getElementsByTagName = function (tag) {
    return this._all().filter((n) => n.tagName.toLowerCase() === String(tag).toLowerCase());
  };
  return FakeDocument;
}

/* 搭出与 build-preview 沙盒全景一致的骨架。返回若干稳定引用。 */
export function buildPanoramaDom(doc, greeting = "开场白正文") {
  const el = (tag, attrs = {}, cls = "") => {
    const n = doc.createElement(tag);
    if (cls) n.className = cls;
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    return n;
  };
  const root = el("div", { "data-chat": "root", "data-theme": "light",
                           "data-composer": "visible" }, "page");
  const header = el("div", { "data-chat": "header" }, "topTabbar");
  const statusbar = el("div", { "data-slot": "statusbar" }, "pano-statusbar");
  const messages = el("div", { "data-chat": "messages" }, "chat pano-chat");
  const list = el("div", { "data-chat": "list" }, "chat-body");

  const frame = el("div", { "data-chat": "message-frame" }, "item");
  const bubble = el("div", { "data-chat": "message", "data-from": "ai",
                            "data-state": "done", "data-msg-id": "pano-2" }, "touch-scope");
  const body = el("div", { "data-chat": "message-body" }, "content left");
  body.textContent = greeting;
  const inner = el("span", { id: "author-node" }, "author-inner");
  inner.textContent = "作者节点";
  body.appendChild(inner);
  bubble.appendChild(body);
  frame.appendChild(bubble);
  list.appendChild(frame);
  messages.appendChild(list);

  const stage = el("div", { "data-chat": "author-stage", hidden: "" }, "pano-stage");
  const composer = el("div", { "data-chat": "composer" }, "pano-input-bar");
  const textarea = el("textarea", { "data-chat": "input" }, "uni-textarea-textarea");
  const send = el("button", { "data-chat": "send" }, "pano-send");
  composer.appendChild(textarea);
  composer.appendChild(send);

  root.appendChild(header);
  root.appendChild(statusbar);
  root.appendChild(messages);
  root.appendChild(stage);
  root.appendChild(composer);
  doc.body.appendChild(root);
  return { root, header, statusbar, messages, list, frame, bubble, body, inner,
           stage, composer, textarea, send };
}
