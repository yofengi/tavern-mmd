#!/usr/bin/env python3
"""Zero-dependency contract tests for the current-MMD zmr theme runtime."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("zmr_build_theme", BASE_DIR / "build_theme.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load build_theme.py")
build_theme = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_theme)

NODE_HARNESS = r"""
"use strict";
function check(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function splitTopLevel(source, separator) {
  var output = [];
  var current = "";
  var square = 0;
  var round = 0;
  var quote = "";
  var index;
  var character;
  for (index = 0; index < source.length; index += 1) {
    character = source.charAt(index);
    if (quote) {
      current += character;
      if (character === quote && source.charAt(index - 1) !== "\\") {
        quote = "";
      }
    } else if (character === "'" || character === '"') {
      quote = character;
      current += character;
    } else if (character === "[") {
      square += 1;
      current += character;
    } else if (character === "]") {
      square -= 1;
      current += character;
    } else if (character === "(") {
      round += 1;
      current += character;
    } else if (character === ")") {
      round -= 1;
      current += character;
    } else if (square === 0 && round === 0 && separator(character)) {
      if (current.trim()) {
        output.push(current.trim());
      }
      current = "";
    } else {
      current += character;
    }
  }
  if (current.trim()) {
    output.push(current.trim());
  }
  return output;
}

function selectorParts(source) {
  return splitTopLevel(source, function splitOnSpace(character) {
    return /\s/.test(character);
  });
}

function selectorList(source) {
  return splitTopLevel(source, function splitOnComma(character) {
    return character === ",";
  });
}

function matchesAttribute(element, expression) {
  var match = expression.trim().match(/^([A-Za-z0-9_-]+)(?:\s*(\*=|=)\s*(?:'([^']*)'|"([^"]*)"|([^\s]+)))?$/);
  var name;
  var operator;
  var expected;
  var actual;
  if (!match) {
    return false;
  }
  name = match[1];
  operator = match[2];
  expected = match[3] !== undefined ? match[3] : match[4] !== undefined ? match[4] : match[5];
  if (!element.hasAttribute(name)) {
    return false;
  }
  if (!operator) {
    return true;
  }
  actual = element.getAttribute(name);
  return operator === "=" ? actual === expected : actual.indexOf(expected) !== -1;
}

function matchesSimple(element, source) {
  var selector = source.trim();
  var rejected = [];
  var tag;
  var classMatch;
  var attributeMatch;
  selector = selector.replace(/:not\(([^()]*)\)/g, function collectNot(match, inner) {
    rejected.push(inner);
    return "";
  });
  if (rejected.some(function isRejected(inner) { return matchesSelector(element, inner); })) {
    return false;
  }
  tag = selector.match(/^([A-Za-z][A-Za-z0-9-]*|\*)/);
  if (tag && tag[1] !== "*" && element.tagName.toLowerCase() !== tag[1].toLowerCase()) {
    return false;
  }
  classMatch = /\.([A-Za-z0-9_-]+)/g;
  while ((tag = classMatch.exec(selector))) {
    if (!element.classList.contains(tag[1])) {
      return false;
    }
  }
  classMatch = /#([A-Za-z0-9_-]+)/g;
  while ((tag = classMatch.exec(selector))) {
    if (element.id !== tag[1]) {
      return false;
    }
  }
  attributeMatch = /\[([^\]]+)\]/g;
  while ((tag = attributeMatch.exec(selector))) {
    if (!matchesAttribute(element, tag[1])) {
      return false;
    }
  }
  return true;
}

function matchesComplex(element, selector) {
  var parts = selectorParts(selector);
  var current = element;
  var index;
  if (!parts.length || !matchesSimple(current, parts[parts.length - 1])) {
    return false;
  }
  for (index = parts.length - 2; index >= 0; index -= 1) {
    current = current.parentElement;
    while (current && !matchesSimple(current, parts[index])) {
      current = current.parentElement;
    }
    if (!current) {
      return false;
    }
  }
  return true;
}

function matchesSelector(element, source) {
  return selectorList(source).some(function matchesOne(selector) {
    return matchesComplex(element, selector);
  });
}

function EventTargetLike() {
  this._listeners = new Map();
}
EventTargetLike.prototype.addEventListener = function addEventListener(type, handler) {
  var handlers = this._listeners.get(type) || [];
  handlers.push(handler);
  this._listeners.set(type, handlers);
};
EventTargetLike.prototype.removeEventListener = function removeEventListener(type, handler) {
  var handlers = this._listeners.get(type) || [];
  this._listeners.set(type, handlers.filter(function keep(value) { return value !== handler; }));
};
EventTargetLike.prototype.dispatchEvent = function dispatchEvent(event) {
  var value = typeof event === "string" ? { type: event } : event;
  var handlers = (this._listeners.get(value.type) || []).slice();
  value.target = value.target || this;
  handlers.forEach(function invoke(handler) { handler.call(this, value); }, this);
};

function FakeClassList(element) {
  this.element = element;
  this.values = new Set();
}
FakeClassList.prototype.contains = function contains(value) {
  return this.values.has(value);
};
FakeClassList.prototype.add = function add() {
  var changed = false;
  var index;
  for (index = 0; index < arguments.length; index += 1) {
    if (!this.values.has(arguments[index])) {
      this.values.add(arguments[index]);
      changed = true;
    }
  }
  if (changed) {
    this.element._notifyAttribute("class");
  }
};
FakeClassList.prototype.remove = function remove() {
  var changed = false;
  var index;
  for (index = 0; index < arguments.length; index += 1) {
    changed = this.values.delete(arguments[index]) || changed;
  }
  if (changed) {
    this.element._notifyAttribute("class");
  }
};
FakeClassList.prototype.set = function set(value) {
  this.values = new Set(String(value || "").split(/\s+/).filter(Boolean));
  this.element._notifyAttribute("class");
};
FakeClassList.prototype.toString = function toString() {
  return Array.from(this.values).join(" ");
};

function FakeStyle(element) {
  this.element = element;
  this.values = new Map();
  this.priorities = new Map();
}
FakeStyle.prototype.getPropertyValue = function getPropertyValue(name) {
  return this.values.get(name) || "";
};
FakeStyle.prototype.getPropertyPriority = function getPropertyPriority(name) {
  return this.priorities.get(name) || "";
};
FakeStyle.prototype.setProperty = function setProperty(name, value, priority) {
  this.values.set(name, String(value));
  this.priorities.set(name, String(priority || ""));
  this.element._notifyAttribute("style");
};
FakeStyle.prototype.removeProperty = function removeProperty(name) {
  var previous = this.getPropertyValue(name);
  if (this.values.delete(name)) {
    this.priorities.delete(name);
    this.element._notifyAttribute("style");
  }
  return previous;
};
FakeStyle.prototype.serialize = function serialize() {
  var self = this;
  return Array.from(this.values.keys()).map(function render(name) {
    var suffix = self.getPropertyPriority(name) ? " !" + self.getPropertyPriority(name) : "";
    return name + ": " + self.getPropertyValue(name) + suffix;
  }).join("; ");
};

function FakeText(value, documentLocal) {
  this.nodeType = 3;
  this.nodeValue = value;
  this.ownerDocument = documentLocal;
  this.parentNode = null;
  this.parentElement = null;
}
Object.defineProperty(FakeText.prototype, "isConnected", {
  get: function getConnected() { return !!this.parentElement && this.parentElement.isConnected; }
});

function FakeElement(tagName, documentLocal) {
  EventTargetLike.call(this);
  this.nodeType = 1;
  this.tagName = String(tagName).toUpperCase();
  this.ownerDocument = documentLocal;
  this.parentNode = null;
  this.parentElement = null;
  this.children = [];
  this.attributes = new Map();
  this.classList = new FakeClassList(this);
  this.style = new FakeStyle(this);
  this.hidden = false;
  this.disabled = false;
  this.textContent = "";
  this.value = "";
  this.checked = false;
  this._connected = false;
}
FakeElement.prototype = Object.create(EventTargetLike.prototype);
FakeElement.prototype.constructor = FakeElement;
Object.defineProperty(FakeElement.prototype, "isConnected", {
  get: function getConnected() { return this._connected; }
});
Object.defineProperty(FakeElement.prototype, "className", {
  get: function getClassName() { return this.classList.toString(); },
  set: function setClassName(value) { this.classList.set(value); }
});
Object.defineProperty(FakeElement.prototype, "id", {
  get: function getId() { return this.getAttribute("id") || ""; },
  set: function setId(value) { this.setAttribute("id", value); }
});
FakeElement.prototype._setConnected = function setConnected(value) {
  this._connected = value;
  this.children.forEach(function update(child) {
    if (child.nodeType === 1) {
      child._setConnected(value);
    }
  });
};
FakeElement.prototype._notifyAttribute = function notifyAttribute(name) {
  if (this.ownerDocument) {
    this.ownerDocument._queueMutation({ type: "attributes", target: this, attributeName: name });
  }
};
FakeElement.prototype.appendChild = function appendChild(child) {
  if (child.parentNode) {
    child.parentNode.removeChild(child);
  }
  this.children.push(child);
  child.parentNode = this;
  child.parentElement = this;
  child.ownerDocument = this.ownerDocument;
  if (child.nodeType === 1) {
    child._setConnected(this.isConnected);
  }
  if (this.ownerDocument) {
    this.ownerDocument._queueMutation({ type: "childList", target: this, addedNodes: [child], removedNodes: [] });
  }
  return child;
};
FakeElement.prototype.removeChild = function removeChild(child) {
  var index = this.children.indexOf(child);
  if (index !== -1) {
    this.children.splice(index, 1);
    child.parentNode = null;
    child.parentElement = null;
    if (child.nodeType === 1) {
      child._setConnected(false);
    }
    if (this.ownerDocument) {
      this.ownerDocument._queueMutation({ type: "childList", target: this, addedNodes: [], removedNodes: [child] });
    }
  }
  return child;
};
FakeElement.prototype.remove = function remove() {
  if (this.parentNode) {
    this.parentNode.removeChild(this);
  }
};
FakeElement.prototype.contains = function contains(node) {
  var current = node;
  while (current) {
    if (current === this) {
      return true;
    }
    current = current.parentNode;
  }
  return false;
};
FakeElement.prototype.setAttribute = function setAttribute(name, value) {
  if (name === "class") {
    this.className = value;
    return;
  }
  this.attributes.set(name, String(value));
  this._notifyAttribute(name);
};
FakeElement.prototype.getAttribute = function getAttribute(name) {
  if (name === "class") {
    return this.className || null;
  }
  if (name === "style") {
    return this.style.values.size ? this.style.serialize() : null;
  }
  return this.attributes.has(name) ? this.attributes.get(name) : null;
};
FakeElement.prototype.hasAttribute = function hasAttribute(name) {
  if (name === "class") {
    return this.classList.values.size > 0;
  }
  if (name === "style") {
    return this.style.values.size > 0;
  }
  return this.attributes.has(name);
};
FakeElement.prototype.removeAttribute = function removeAttribute(name) {
  var changed;
  if (name === "class") {
    changed = this.classList.values.size > 0;
    this.classList.values.clear();
  } else {
    changed = this.attributes.delete(name);
  }
  if (changed) {
    this._notifyAttribute(name);
  }
};
FakeElement.prototype.matches = function matches(selector) {
  return matchesSelector(this, selector);
};
FakeElement.prototype.closest = function closest(selector) {
  var current = this;
  while (current) {
    if (current.matches(selector)) {
      return current;
    }
    current = current.parentElement;
  }
  return null;
};
FakeElement.prototype.querySelectorAll = function querySelectorAll(selector) {
  var output = [];
  function visit(node) {
    node.children.forEach(function inspect(child) {
      if (child.nodeType === 1) {
        if (child.matches(selector)) {
          output.push(child);
        }
        visit(child);
      }
    });
  }
  visit(this);
  return output;
};
FakeElement.prototype.querySelector = function querySelector(selector) {
  return this.querySelectorAll(selector)[0] || null;
};
FakeElement.prototype.getClientRects = function getClientRects() {
  return this.hidden ? [] : [{}];
};
FakeElement.prototype.focus = function focus() {
  this.ownerDocument.activeElement = this;
};

function FakeDocument() {
  EventTargetLike.call(this);
  this._observers = new Set();
  this.documentElement = new FakeElement("html", this);
  this.documentElement._setConnected(true);
  this.head = new FakeElement("head", this);
  this.body = new FakeElement("body", this);
  this.documentElement.appendChild(this.head);
  this.documentElement.appendChild(this.body);
  this.activeElement = this.body;
}
FakeDocument.prototype = Object.create(EventTargetLike.prototype);
FakeDocument.prototype.constructor = FakeDocument;
FakeDocument.prototype.createElement = function createElement(tagName) {
  return new FakeElement(tagName, this);
};
FakeDocument.prototype.createTextNode = function createTextNode(value) {
  return new FakeText(value, this);
};
FakeDocument.prototype.querySelectorAll = function querySelectorAll(selector) {
  var output = [];
  if (this.documentElement.matches(selector)) {
    output.push(this.documentElement);
  }
  return output.concat(this.documentElement.querySelectorAll(selector));
};
FakeDocument.prototype.querySelector = function querySelector(selector) {
  return this.querySelectorAll(selector)[0] || null;
};
FakeDocument.prototype.createTreeWalker = function createTreeWalker(root) {
  var nodes = [];
  var index = 0;
  function visit(node) {
    node.children.forEach(function inspect(child) {
      if (child.nodeType === 3) {
        nodes.push(child);
      } else if (child.nodeType === 1) {
        visit(child);
      }
    });
  }
  visit(root);
  return {
    nextNode: function nextNode() {
      var value = nodes[index] || null;
      index += 1;
      return value;
    }
  };
};
FakeDocument.prototype._queueMutation = function queueMutation(record) {
  this._observers.forEach(function queue(observer) {
    if (observer.active && observer.target && observer.target.contains(record.target)) {
      if (record.type !== "attributes" || !observer.options.attributeFilter || observer.options.attributeFilter.indexOf(record.attributeName) !== -1) {
        observer.records.push(record);
      }
    }
  });
};
FakeDocument.prototype.replaceBody = function replaceBody() {
  var replacement = new FakeElement("body", this);
  this.documentElement.removeChild(this.body);
  this.body = replacement;
  this.documentElement.appendChild(replacement);
  return replacement;
};

function FakeMutationObserver(callback) {
  this.callback = callback;
  this.records = [];
  this.active = false;
  this.target = null;
  this.options = {};
}
FakeMutationObserver.prototype.observe = function observe(target, options) {
  this.target = target;
  this.options = options || {};
  this.active = true;
  target.ownerDocument._observers.add(this);
};
FakeMutationObserver.prototype.disconnect = function disconnect() {
  if (this.target && this.target.ownerDocument) {
    this.target.ownerDocument._observers.delete(this);
  }
  this.active = false;
  this.records.length = 0;
};
FakeMutationObserver.prototype.takeRecords = function takeRecords() {
  var output = this.records.slice();
  this.records.length = 0;
  return output;
};

function createStorage(seed) {
  var values = Object.assign({}, seed || {});
  return {
    getItem: function getItem(key) { return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : null; },
    setItem: function setItem(key, value) { values[key] = String(value); },
    removeItem: function removeItem(key) { delete values[key]; },
    snapshot: function snapshot() { return Object.assign({}, values); }
  };
}

function createWindow(documentLocal, seed) {
  var events = new EventTargetLike();
  var timers = new Map();
  var nextTimer = 1;
  var windowLocal = {
    document: documentLocal,
    MutationObserver: FakeMutationObserver,
    NodeFilter: { SHOW_TEXT: 4 },
    location: { hash: "#/chat/chat" },
    localStorage: createStorage(seed),
    setTimeout: function setTimeoutFake(callback) {
      var id = nextTimer;
      nextTimer += 1;
      timers.set(id, callback);
      return id;
    },
    clearTimeout: function clearTimeoutFake(id) { timers.delete(id); },
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
    dispatchEvent: events.dispatchEvent.bind(events),
    runTimers: function runTimers() {
      var turns = 0;
      while (timers.size) {
        var current = Array.from(timers.entries());
        timers.clear();
        current.forEach(function run(entry) { entry[1](); });
        turns += 1;
        if (turns > 50) {
          throw new Error("timer loop did not settle");
        }
      }
    },
    timerCount: function timerCount() { return timers.size; }
  };
  return windowLocal;
}

function installSource(name, windowLocal) {
  Function("window", SOURCES[name])(windowLocal);
}

function installRuntimeEnvironment(seed) {
  var documentLocal = new FakeDocument();
  var windowLocal = createWindow(documentLocal, seed);
  var chat = documentLocal.createElement("div");
  var style = documentLocal.createElement("style");
  var calls = { starts: 0, stops: 0, restores: 0, destroys: 0, flushes: 0, cleaning: [] };
  var cleanup = {
    start: function start(root) { calls.starts += 1; calls.lastRoot = root; return cleanup; },
    stop: function stop() { calls.stops += 1; return cleanup; },
    restore: function restore() { calls.restores += 1; return cleanup; },
    setCleaning: function setCleaning(value) { calls.cleaning.push(value); return cleanup; },
    register: function register() { return cleanup; },
    unregister: function unregister() { return cleanup; },
    flush: function flush() { calls.flushes += 1; return true; },
    destroy: function destroy() { calls.destroys += 1; }
  };
  var quote = {
    setNormalizeQuotes: function setNormalizeQuotes(value) { calls.normalizeQuotes = value; return quote; },
    destroy: function destroy() {}
  };
  chat.className = "chat";
  documentLocal.body.appendChild(chat);
  style.setAttribute("data-zmr-owner", "tavern-mmd/zmr");
  style.setAttribute("data-zmr-version", "2.0.0");
  style.setAttribute("data-zmr-id", "zmr-theme-style");
  documentLocal.head.appendChild(style);
  windowLocal["tavern-mmd/zmr"] = {
    cleanupFactory: function cleanupFactory() { return cleanup; },
    quotePluginFactory: function quotePluginFactory() { return quote; }
  };
  installSource("ui", windowLocal);
  installSource("runtime", windowLocal);
  return {
    document: documentLocal,
    window: windowLocal,
    calls: calls,
    cleanup: cleanup,
    lease: windowLocal["tavern-mmd/zmr"].lease
  };
}

function finish(value) {
  process.stdout.write(JSON.stringify(value || { ok: true }));
}
"""


def run_node_scenario(sources: dict[str, str], scenario: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("Node.js is required for runtime behavior tests")
    script = "const SOURCES = " + json.dumps(sources, ensure_ascii=False) + ";\n" + NODE_HARNESS + "\n" + scenario
    with tempfile.TemporaryDirectory(prefix="zmr-runtime-test-") as temp_dir:
        path = Path(temp_dir) / "scenario.js"
        path.write_text(script, encoding="utf-8", newline="\n")
        result = subprocess.run(
            [node, str(path)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            f"Node behavior scenario failed ({result.returncode})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return json.loads(result.stdout or "{}")


class ThemeRuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cleanup = build_theme.read_source(BASE_DIR.parent / "mmd_cleanup_core.js")
        cls.quote = build_theme.read_source(BASE_DIR / "quote-plugin.js")
        cls.css = build_theme.read_source(BASE_DIR / "theme.css")
        cls.ui = build_theme.read_source(BASE_DIR / "settings-ui.js")
        cls.runtime = build_theme.read_source(BASE_DIR / "runtime.js")
        cls.sources = {
            "cleanup": cls.cleanup,
            "quote": cls.quote,
            "ui": cls.ui,
            "runtime": cls.runtime,
        }
        cls.obj = build_theme.build_object()
        cls.rendered = build_theme.serialize(cls.obj)

    def run_scenario(self, scenario: str) -> dict[str, object]:
        return run_node_scenario(self.sources, scenario)

    def test_generated_artifact_is_fresh_and_guarded(self) -> None:
        self.assertEqual([], build_theme.validate(self.obj, self.rendered))
        self.assertEqual(
            self.rendered.encode("utf-8"),
            (BASE_DIR / "mmd-theme-runtime.mmd.json").read_bytes(),
        )
        self.assertFalse(self.rendered.encode("utf-8").startswith(b"\xef\xbb\xbf"))

    def test_five_modules_have_fixed_order_and_headroom(self) -> None:
        self.assertEqual(
            [
                "zmr-cleanup-factory",
                "zmr-quote-plugin-factory",
                "zmr-theme-style",
                "zmr-settings-ui-factory",
                "zmr-theme-runtime",
            ],
            [module.asset_id for module in build_theme.MODULES],
        )
        expected_statusbar = "".join(module.marker for module in build_theme.MODULES)
        self.assertEqual(expected_statusbar, self.obj["statusbar"])
        scripts = self.obj["regex_scripts"]
        self.assertEqual(5, len(scripts))
        for script in scripts:
            self.assertTrue(build_theme.slash_delimited(script["findRegex"]))
            self.assertLessEqual(len(script["replaceString"]), build_theme.PROJECT_REPLACE_LIMIT)
            self.assertNotIn("\n", script["replaceString"])
            self.assertNotIn("\r", script["replaceString"])

    def test_guard_rejects_limit_and_findregex_regressions(self) -> None:
        changed = copy.deepcopy(self.obj)
        changed["regex_scripts"][0]["replaceString"] = "x" * (build_theme.PROJECT_REPLACE_LIMIT + 1)
        changed["regex_scripts"][1]["findRegex"] = "<zmr-quote-v2>"
        errors = build_theme.validate(changed, build_theme.serialize(changed))
        self.assertTrue(any("项目余量上限" in error for error in errors))
        self.assertTrue(any("findRegex 未使用 /.../" in error for error in errors))

    def test_cleanup_uses_one_observer_and_explicit_targets(self) -> None:
        self.assertEqual(1, self.cleanup.count("new global.MutationObserver("))
        self.assertIn("targets: Object.freeze", self.cleanup)
        self.assertIn("messageWrappers: Object.freeze", self.cleanup)
        self.assertNotIn('"[style]"', self.cleanup)
        self.assertNotIn('"[color]"', self.cleanup)
        self.assertNotIn("candidateSelector", self.cleanup)
        self.assertNotIn("scopeSelector", self.cleanup)
        self.assertIn("record.addedNodes", self.cleanup)
        self.assertIn("attributeTargets", self.cleanup)
        self.assertIn("var deltas = new Map();", self.cleanup)
        self.assertIn("pruneDisconnected", self.cleanup)

    def test_cleanup_blocks_rich_text_descendants_and_exposes_lifecycle(self) -> None:
        self.assertIn("isAllowedMessageElement", self.cleanup)
        self.assertIn(
            "element.parentElement === content && element.matches(messageWrapperSelector)",
            self.cleanup,
        )
        for name in ("start", "stop", "setCleaning", "register", "unregister", "flush", "restore", "destroy"):
            self.assertRegex(self.cleanup, rf"\b{name}\s*:\s*{name}\b")
        self.assertLess(
            self.cleanup.index("invokePlugins(context);"),
            self.cleanup.index("candidates.forEach(cleanElement);"),
        )

    def test_quote_plugin_is_ai_only_opt_in_and_preserves_ascii_quotes(self) -> None:
        self.assertIn('var AI_SELECTOR = ".content.left";', self.quote)
        for skipped in ("pre", "code", "kbd", "samp", "input", "textarea", "[hidden]", "[contenteditable]"):
            self.assertIn(skipped, self.quote)
        self.assertIn('var normalizeQuotes = settings.normalizeQuotes === true;', self.quote)
        self.assertIn('if (!normalizeQuotes) {', self.quote)
        self.assertIn('setNormalizeQuotes: function setNormalizeQuotes(enabled)', self.quote)
        self.assertIn('after = before.replace(/“([^“”]+)“/g', self.quote)
        self.assertNotIn("normalizeAsciiQuotes", self.quote)
        self.assertIn('element.classList.add("zmr-hdm")', self.quote)
        self.assertNotIn("replaceWith", self.quote)
        self.assertNotIn("outerHTML", self.quote)

    def test_settings_ui_has_accessible_state_and_safe_output_for(self) -> None:
        self.assertIn('opacityOutput.setAttribute("for", opacity.id);', self.ui)
        self.assertNotIn("opacityOutput.htmlFor", self.ui)
        for state in ("aria-expanded", "aria-pressed", "aria-disabled"):
            self.assertIn(state, self.ui)
        self.assertIn("tuning.disabled = disabled;", self.ui)
        self.assertIn("resetButton.disabled = disabled;", self.ui)
        checkbox_position = self.ui.index('makeInput("zmr-normalize-quotes", "checkbox")')
        fieldset_position = self.ui.index('makeElement("fieldset", "zmr-tuning-group")')
        self.assertLess(checkbox_position, fieldset_position)
        self.assertIn("normalizeQuotes.checked = snapshot.normalizeQuotes === true;", self.ui)
        self.assertIn("settings.onNormalizeQuotes(normalizeQuotes.checked === true);", self.ui)
        self.assertIn('event.key === "Escape"', self.ui)
        self.assertIn("lastFocus", self.ui)
        self.assertNotIn("innerHTML", self.ui)
        self.assertNotIn("cssText", self.ui)
        self.assertIsNone(re.search(r"\bonclick\s*=", self.ui))

    def test_runtime_validates_storage_and_keeps_route_supervision(self) -> None:
        self.assertIn("tavern-mmd/zmr/theme-settings/schema-2", self.runtime)
        self.assertIn("tavern-mmd/zmr/theme-settings/schema-1", self.runtime)
        self.assertIn('validInteger(value, 12, 32)', self.runtime)
        self.assertIn('validLineHeight(value)', self.runtime)
        self.assertIn('validInteger(value, 40, 100)', self.runtime)
        self.assertIn('/^#[0-9a-fA-F]{6}$/.test(value)', self.runtime)
        self.assertIn('overrides: { day: {}, night: {} }', self.runtime)
        self.assertIn('typeof raw.normalizeQuotes === "boolean"', self.runtime)
        self.assertIn('quotePlugin.setNormalizeQuotes(state.normalizeQuotes);', self.runtime)
        self.assertIn('cleanup.flush(chatRoot', self.runtime)
        self.assertIn('cleanup.setCleaning(false);', self.runtime)
        self.assertIn('cleanup.stop();', self.runtime)
        self.assertIn('cleanup.restore();', self.runtime)
        self.assertIn('delete state.overrides[state.mode];', self.runtime)
        self.assertIn('onResetAll: resetAllThemes', self.runtime)
        for event_name in ("hashchange", "popstate", "pageshow", "focus", "pagehide", "visibilitychange"):
            self.assertIn(f'"{event_name}"', self.runtime)
        for name in ("day", "night", "native", "destroy", "enter", "leave", "reenter", "refreshAssets", "setNormalizeQuotes"):
            self.assertRegex(self.runtime, rf"\b{name}\s*:")
        leave_body = re.search(r"function leaveChat\(\) \{([\s\S]*?)\n  \}", self.runtime).group(1)
        positions = [leave_body.index(fragment) for fragment in ("cleanup.stop();", "cleanup.restore();", 'rootElement.removeAttribute("data-zmr-mode")', "clearReadingVariables();")]
        self.assertEqual(sorted(positions), positions)

    def test_runtime_resource_takeover_is_repeatable_and_reason_aware(self) -> None:
        self.assertIn("chooseNewestStyle(currentStyles())", self.runtime)
        self.assertIn("takeoverStyle(newest || themeStyle)", self.runtime)
        self.assertIn("removeDuplicateStyles(candidate)", self.runtime)
        self.assertIn("removeAllOwnedStyles(themeStyle)", self.runtime)
        self.assertIn("documentRef.head.appendChild(candidate)", self.runtime)
        self.assertIn('previousLease.destroy("superseded")', self.runtime)
        self.assertIn('previousLease.refreshAssets(incomingStyle)', self.runtime)
        self.assertIn('previousLease.reenter()', self.runtime)
        reuse_start = self.runtime.index("previousLease && previousLease.meta")
        reuse_return = self.runtime.index("return;", reuse_start)
        destroy_start = self.runtime.index('previousLease.destroy("superseded")', reuse_return)
        self.assertLess(reuse_start, reuse_return)
        self.assertLess(reuse_return, destroy_start)
        self.assertIn('if (reason === "superseded")', self.runtime)
        superseded = self.runtime.split('if (reason === "superseded")', 1)[1].split("} else {", 1)[0]
        explicit = self.runtime.split('if (reason === "superseded")', 1)[1].split("} else {", 1)[1].split("}", 1)[0]
        self.assertIn("themeStyle.remove()", superseded)
        self.assertNotIn("removeAllOwnedStyles(null)", superseded)
        self.assertIn("removeAllOwnedStyles(null)", explicit)

    def test_cleanup_delta_uses_latest_removed_values_and_preserves_platform_writes(self) -> None:
        result = self.run_scenario(r"""
var documentLocal = new FakeDocument();
var windowLocal = createWindow(documentLocal);
var first = documentLocal.createElement("div");
var second = documentLocal.createElement("div");
installSource("cleanup", windowLocal);
first.className = "chat";
second.className = "chat-bg";
documentLocal.body.appendChild(first);
documentLocal.body.appendChild(second);
first.style.setProperty("background-color", "#0d0e0f", "important");
first.setAttribute("color", "#0d0e0f");
second.style.setProperty("background-color", "#0d0e0f", "");
second.setAttribute("color", "#0d0e0f");
var cleanup = windowLocal["tavern-mmd/zmr"].cleanupFactory({ document: documentLocal, delay: 0 });
cleanup.start(documentLocal.body);
cleanup.flush();
check(first.style.getPropertyValue("background-color") === "", "first pollution was not cleaned");
check(first.getAttribute("color") === null, "first color attribute was not cleaned");
first.style.setProperty("background-color", "#101113", "");
first.setAttribute("color", "#101113");
second.style.setProperty("background-color", "#101113", "important");
second.setAttribute("color", "#101113");
cleanup.flush();
check(first.style.getPropertyValue("background-color") === "", "latest first pollution was not cleaned");
check(second.style.getPropertyValue("background-color") === "", "latest second pollution was not cleaned");
first.style.setProperty("background-color", "#abcdef", "important");
first.setAttribute("color", "#123456");
cleanup.setCleaning(false);
check(first.style.getPropertyValue("background-color") === "#abcdef", "restore overwrote a legal platform style");
check(first.style.getPropertyPriority("background-color") === "important", "legal platform priority changed");
check(first.getAttribute("color") === "#123456", "restore overwrote a legal platform color attribute");
check(second.style.getPropertyValue("background-color") === "#101113", "restore did not use latest pollution value");
check(second.style.getPropertyPriority("background-color") === "important", "restore did not use latest priority");
check(second.getAttribute("color") === "#101113", "restore did not use latest color attribute");
check(cleanup.getObserver().takeRecords().length === 0, "observer retained runtime restore writes");
finish({ deltaCount: cleanup.getDeltaCount() });
""")
        self.assertEqual(0, result["deltaCount"])

    def test_cleanup_plugin_replacement_and_unregister_teardown_once(self) -> None:
        result = self.run_scenario(r"""
var documentLocal = new FakeDocument();
var windowLocal = createWindow(documentLocal);
var events = [];
installSource("cleanup", windowLocal);
var cleanup = windowLocal["tavern-mmd/zmr"].cleanupFactory({ document: documentLocal, delay: 0 });
var first = {
  id: "same",
  stop: function stop() { events.push("first-stop"); throw new Error("isolated stop"); },
  destroy: function destroy() { events.push("first-destroy"); }
};
var second = {
  id: "same",
  stop: function stop() { events.push("second-stop"); },
  destroy: function destroy() { events.push("second-destroy"); }
};
var third = {
  id: "third",
  stop: function stop() { events.push("third-stop"); },
  destroy: function destroy() { events.push("third-destroy"); }
};
cleanup.register(first);
cleanup.register(second);
cleanup.register(third);
cleanup.unregister(second);
cleanup.destroy();
check(events.join(",") === "first-stop,first-destroy,second-stop,second-destroy,third-stop,third-destroy", "plugin teardown order/count changed: " + events.join(","));
finish({ events: events, source: cleanup.getLastError().source });
""")
        self.assertEqual("plugin-stop:same", result["source"])
        self.assertEqual(6, len(result["events"]))

    def test_quote_marker_is_incrementally_removed_but_component_boundary_is_skipped(self) -> None:
        result = self.run_scenario(r"""
var documentLocal = new FakeDocument();
var windowLocal = createWindow(documentLocal);
var ai = documentLocal.createElement("div");
var orange = documentLocal.createElement("font");
var boundary = documentLocal.createElement("div");
var nested = documentLocal.createElement("font");
installSource("quote", windowLocal);
ai.className = "content left";
orange.setAttribute("color", "#dc8333");
boundary.setAttribute("data-sid", "status");
nested.setAttribute("color", "#dc8333");
boundary.appendChild(nested);
ai.appendChild(orange);
ai.appendChild(boundary);
documentLocal.body.appendChild(ai);
var plugin = windowLocal["tavern-mmd/zmr"].quotePluginFactory({ normalizeQuotes: false });
plugin.process({ addedNodes: [ai], attributeTargets: [], textTargets: [] });
check(orange.classList.contains("zmr-hdm"), "orange marker was not added");
check(!nested.classList.contains("zmr-hdm"), "component boundary was not skipped");
orange.setAttribute("color", "#123456");
plugin.process({ addedNodes: [], attributeTargets: [orange], textTargets: [] });
check(!orange.classList.contains("zmr-hdm"), "stale orange marker was not removed");
orange.setAttribute("color", "#dc8333");
plugin.process({ addedNodes: [], attributeTargets: [orange], textTargets: [] });
check(orange.classList.contains("zmr-hdm"), "orange marker was not re-added");
ai.removeChild(orange);
documentLocal.body.appendChild(orange);
plugin.destroy();
check(!orange.classList.contains("zmr-hdm"), "destroy left a marker outside the AI boundary");
finish(plugin.getStats());
""")
        self.assertEqual(2, result["highlightedElements"])

    def test_ui_host_remounts_into_replaced_body_on_reenter(self) -> None:
        result = self.run_scenario(r"""
var env = installRuntimeEnvironment();
var oldHost = env.document.querySelector("[data-zmr-owned='runtime-ui']");
var newBody = env.document.replaceBody();
var chat = env.document.createElement("div");
chat.className = "chat";
newBody.appendChild(chat);
check(!oldHost.isConnected, "old runtime host should be detached after body replacement");
env.lease.reenter();
var remounted = env.document.querySelector("[data-zmr-owned='runtime-ui']");
check(remounted === oldHost, "runtime created or selected a different host");
check(remounted.parentNode === newBody && remounted.isConnected, "runtime host was not mounted in current body");
finish({ starts: env.calls.starts });
""")
        self.assertGreaterEqual(result["starts"], 2)

    def test_pagehide_cancels_queued_route_and_pageshow_allows_reentry(self) -> None:
        result = self.run_scenario(r"""
var env = installRuntimeEnvironment();
env.window.runTimers();
var starts = env.calls.starts;
env.window.dispatchEvent({ type: "hashchange" });
check(env.window.timerCount() > 0, "route timer was not queued");
env.window.dispatchEvent({ type: "pagehide" });
check(env.window.timerCount() === 0, "pagehide did not cancel route timer");
env.window.runTimers();
check(env.calls.starts === starts, "queued route timer reentered after pagehide");
env.lease.reenter();
check(env.calls.starts === starts, "manual reenter bypassed pagehide guard");
env.window.dispatchEvent({ type: "pageshow" });
check(env.window.timerCount() === 1, "pageshow did not queue reconciliation");
env.window.runTimers();
check(env.calls.starts === starts + 1, "pageshow did not allow reentry");
finish({ starts: env.calls.starts, stops: env.calls.stops });
""")
        self.assertGreaterEqual(result["stops"], 1)

    def test_schema_one_migrates_only_legacy_differences_to_schema_two(self) -> None:
        result = self.run_scenario(r"""
var legacyKey = "tavern-mmd/zmr/theme-settings/schema-1";
var currentKey = "tavern-mmd/zmr/theme-settings/schema-2";
var legacy = {
  schema: 1,
  mode: "night",
  normalizeQuotes: true,
  themes: {
    day: { fontSize: 16, lineHeight: 1.65, textColor: "#3b2425", accentColor: "#112233", aiBubbleColor: "#fffaf2", opacity: 96 },
    night: { fontSize: 19, lineHeight: 1.65, textColor: "#f3ece2", accentColor: "#efabb5", aiBubbleColor: "#24262b", opacity: 96 }
  }
};
var seed = {};
seed[legacyKey] = JSON.stringify(legacy);
var env = installRuntimeEnvironment(seed);
var migrated = JSON.parse(env.window.localStorage.getItem(currentKey));
check(JSON.stringify(migrated) === JSON.stringify({ schema: 2, mode: "night", normalizeQuotes: true, overrides: { day: { accentColor: "#112233" }, night: { fontSize: 19 } } }), "legacy migration pinned defaults: " + JSON.stringify(migrated));
check(env.document.documentElement.style.getPropertyValue("--zmr-reading-font-size") === "19px", "effective migrated theme was not applied");
finish(migrated);
""")
        self.assertEqual({"accentColor": "#112233"}, result["overrides"]["day"])
        self.assertEqual({"fontSize": 19}, result["overrides"]["night"])

    def test_schema_two_updates_and_resets_only_overrides(self) -> None:
        result = self.run_scenario(r"""
var key = "tavern-mmd/zmr/theme-settings/schema-2";
var seed = {};
seed[key] = JSON.stringify({ schema: 2, mode: "day", normalizeQuotes: true, overrides: { day: { fontSize: 18 }, night: { opacity: 80 } } });
var env = installRuntimeEnvironment(seed);
var font = env.document.querySelector("#zmr-font-size");
var resetCurrent;
var resetAll;
font.value = "20";
font.dispatchEvent({ type: "input" });
var updated = JSON.parse(env.window.localStorage.getItem(key));
check(updated.overrides.day.fontSize === 20, "field update did not write override");
check(!Object.prototype.hasOwnProperty.call(updated, "themes"), "schema-2 persisted preset themes");
resetCurrent = env.document.querySelectorAll(".zmr-command-button")[0];
resetCurrent.dispatchEvent({ type: "click" });
var currentReset = JSON.parse(env.window.localStorage.getItem(key));
check(Object.keys(currentReset.overrides.day).length === 0, "current reset did not clear day override");
check(currentReset.overrides.night.opacity === 80, "current reset cleared night override");
resetAll = env.document.querySelectorAll(".zmr-command-button")[1];
resetAll.dispatchEvent({ type: "click" });
var allReset = JSON.parse(env.window.localStorage.getItem(key));
check(Object.keys(allReset.overrides.day).length === 0 && Object.keys(allReset.overrides.night).length === 0, "all reset did not clear both overrides");
check(allReset.mode === "day" && allReset.normalizeQuotes === true, "all reset changed mode or normalizeQuotes");
finish({ updated: updated, currentReset: currentReset, allReset: allReset });
""")
        self.assertNotIn("themes", result["updated"])
        self.assertTrue(result["allReset"]["normalizeQuotes"])

    def test_css_is_mode_scoped_and_isolates_owned_and_status_components(self) -> None:
        self.assertNotRegex(self.css, r"\.content\.right\s+\*")
        for broad in (".title", ".item", ".card"):
            self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(broad)}(?![A-Za-z0-9_-])", self.css))
        self.assertIn(':not([data-zmr-owned], [data-zmr-owned] *)', self.css)
        for boundary in ("[data-sid] *", "[data-g3v] *", ".g3-host *", ".z-status-box *", "[data-statusbar] *", "[data-zsf-ball] *"):
            self.assertIn(boundary, self.css)
        self.assertIn('html[data-zmr-mode="day"]', self.css)
        self.assertIn('html[data-zmr-mode="night"]', self.css)
        invalid_properties = [
            name
            for name in re.findall(r"(?<![A-Za-z0-9_-])(--[A-Za-z0-9_-]+)\s*:", self.css)
            if not name.startswith("--zmr-")
        ]
        self.assertEqual([], invalid_properties)

    def test_sources_do_not_scan_all_body_text_or_use_unsafe_dom_writes(self) -> None:
        scripts = "\n".join((self.cleanup, self.quote, self.ui, self.runtime))
        for token in ("innerHTML", "cssText", ".body.textContent", 'querySelectorAll("*")', "_mmd_"):
            self.assertNotIn(token, scripts)
        self.assertIsNone(re.search(r"document(?:Ref|Local)?\.body\.querySelectorAll", scripts))
        self.assertIsNone(re.search(r"\bonclick\s*=", scripts))


if __name__ == "__main__":
    unittest.main(verbosity=2)
