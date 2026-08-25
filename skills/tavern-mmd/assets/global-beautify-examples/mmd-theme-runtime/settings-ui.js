(function installTavernMmdZmrSettingsUiFactory(global) {
  "use strict";

  var OWNER = "tavern-mmd/zmr";
  var VERSION = "2.0.0";
  var ID = "zmr-settings-ui-factory";
  var documentRef = global.document;
  var namespace = global[OWNER];

  if (!namespace || typeof namespace !== "object") {
    namespace = {};
    global[OWNER] = namespace;
  }

  function createTavernMmdZmrSettingsUi(options) {
    var settings = options && typeof options === "object" ? options : {};
    var documentLocal = settings.document || documentRef;
    var listeners = [];
    var destroyed = false;
    var lastFocus = null;
    var currentMode = "day";
    var host;
    var toggle;
    var panel;
    var modeButtons = {};
    var normalizeQuotes;
    var tuning;
    var fontSize;
    var lineHeight;
    var textColor;
    var accentColor;
    var bubbleColor;
    var opacity;
    var opacityOutput;
    var resetButton;
    var resetAllButton;
    var api;

    function makeElement(tagName, className, text) {
      var element = documentLocal.createElement(tagName);
      if (className) {
        element.className = className;
      }
      if (text !== undefined) {
        element.textContent = text;
      }
      return element;
    }

    function setAttributes(element, attributes) {
      Object.keys(attributes).forEach(function setAttributeValue(name) {
        element.setAttribute(name, String(attributes[name]));
      });
      return element;
    }

    function listen(target, type, handler, eventOptions) {
      target.addEventListener(type, handler, eventOptions);
      listeners.push({ target: target, type: type, handler: handler, options: eventOptions });
    }

    function makeInput(id, type, attributes) {
      var input = makeElement("input", "zmr-settings-input");
      input.id = id;
      input.type = type;
      setAttributes(input, attributes || {});
      return input;
    }

    function makeField(labelText, input) {
      var row = makeElement("div", "zmr-settings-field");
      var label = makeElement("label", "", labelText);
      label.htmlFor = input.id;
      row.appendChild(label);
      row.appendChild(input);
      return row;
    }

    function emitMode(mode) {
      if (!destroyed && typeof settings.onMode === "function") {
        settings.onMode(mode);
      }
    }

    function emitValue(key, value) {
      if (!destroyed && typeof settings.onValue === "function") {
        settings.onValue(key, value);
      }
    }

    function emitReset() {
      if (!destroyed && typeof settings.onReset === "function") {
        settings.onReset();
      }
    }

    function emitResetAll() {
      if (!destroyed && typeof settings.onResetAll === "function") {
        settings.onResetAll();
      }
    }

    function ensureMounted() {
      var parent;
      if (destroyed) {
        return api;
      }
      parent = documentLocal.body || documentLocal.documentElement;
      if (parent && (!host.isConnected || host.parentNode !== parent)) {
        parent.appendChild(host);
      }
      return api;
    }

    function open() {
      var target;
      ensureMounted();
      if (destroyed || !panel.hidden) {
        return api;
      }
      lastFocus = documentLocal.activeElement;
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      target = modeButtons[currentMode] || modeButtons.day;
      global.setTimeout(function focusPanel() {
        if (!destroyed && !panel.hidden) {
          target.focus();
        }
      }, 0);
      return api;
    }

    function close(returnFocus) {
      var target;
      if (destroyed || panel.hidden) {
        return api;
      }
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      if (returnFocus) {
        target = lastFocus && lastFocus.isConnected ? lastFocus : toggle;
        target.focus();
      }
      lastFocus = null;
      return api;
    }

    function setVisible(visible) {
      if (destroyed) {
        return api;
      }
      if (visible === true) {
        ensureMounted();
      }
      host.hidden = visible !== true;
      if (host.hidden) {
        close(false);
      }
      return api;
    }

    function sync(snapshot) {
      var theme;
      var disabled;
      if (destroyed || !snapshot || !snapshot.theme) {
        return api;
      }
      currentMode = snapshot.mode;
      theme = snapshot.theme;
      disabled = currentMode === "native";
      Object.keys(modeButtons).forEach(function syncMode(mode) {
        modeButtons[mode].setAttribute("aria-pressed", currentMode === mode ? "true" : "false");
      });
      fontSize.value = String(theme.fontSize);
      lineHeight.value = String(theme.lineHeight);
      textColor.value = theme.textColor;
      accentColor.value = theme.accentColor;
      bubbleColor.value = theme.aiBubbleColor;
      opacity.value = String(theme.opacity);
      opacityOutput.textContent = String(theme.opacity) + "%";
      normalizeQuotes.checked = snapshot.normalizeQuotes === true;
      tuning.disabled = disabled;
      tuning.setAttribute("aria-disabled", disabled ? "true" : "false");
      resetButton.disabled = disabled;
      resetButton.setAttribute("aria-disabled", disabled ? "true" : "false");
      resetAllButton.disabled = false;
      resetAllButton.setAttribute("aria-disabled", "false");
      return api;
    }

    function onKeyDown(event) {
      if (event.key === "Escape" && !panel.hidden) {
        event.preventDefault();
        close(true);
      }
    }

    function destroy() {
      var index;
      if (destroyed) {
        return;
      }
      destroyed = true;
      for (index = listeners.length - 1; index >= 0; index -= 1) {
        listeners[index].target.removeEventListener(listeners[index].type, listeners[index].handler, listeners[index].options);
      }
      listeners.length = 0;
      if (host.isConnected) {
        host.remove();
      }
      lastFocus = null;
    }

    function build() {
      var existing = documentLocal.querySelectorAll("[data-zmr-owned='runtime-ui'][data-zmr-owner='" + OWNER + "']");
      var index;
      var header;
      var heading;
      var closeButton;
      var modeGroup;
      var normalizeRow;
      var normalizeLabel;
      var opacityRow;
      var opacityControl;
      var opacityLabel;
      var actions;
      var modes = [
        { value: "day", label: "日间" },
        { value: "night", label: "夜间" },
        { value: "native", label: "原生" }
      ];
      for (index = 0; index < existing.length; index += 1) {
        existing[index].remove();
      }
      host = makeElement("div", "zmr-runtime-host");
      setAttributes(host, {
        "data-zmr-owned": "runtime-ui",
        "data-zmr-owner": OWNER,
        "data-zmr-version": VERSION,
        "data-zmr-id": "zmr-runtime-ui"
      });
      host.hidden = true;
      toggle = makeElement("button", "zmr-settings-toggle", "Aa");
      toggle.type = "button";
      toggle.title = "阅读设置";
      setAttributes(toggle, {
        "aria-label": "打开阅读设置",
        "aria-controls": "zmr-settings-panel",
        "aria-expanded": "false"
      });
      panel = makeElement("div", "zmr-settings-panel");
      panel.id = "zmr-settings-panel";
      panel.hidden = true;
      setAttributes(panel, {
        role: "dialog",
        "aria-modal": "false",
        "aria-labelledby": "zmr-settings-heading"
      });
      header = makeElement("div", "zmr-settings-header");
      heading = makeElement("h2", "zmr-settings-heading", "阅读设置");
      heading.id = "zmr-settings-heading";
      closeButton = makeElement("button", "zmr-icon-button", "×");
      closeButton.type = "button";
      closeButton.title = "关闭";
      closeButton.setAttribute("aria-label", "关闭阅读设置");
      header.appendChild(heading);
      header.appendChild(closeButton);
      panel.appendChild(header);
      modeGroup = makeElement("div", "zmr-mode-group");
      setAttributes(modeGroup, { role: "group", "aria-label": "显示模式" });
      modes.forEach(function appendMode(mode) {
        var button = makeElement("button", "zmr-mode-button", mode.label);
        button.type = "button";
        button.setAttribute("data-zmr-mode-value", mode.value);
        button.setAttribute("aria-pressed", "false");
        modeButtons[mode.value] = button;
        modeGroup.appendChild(button);
        listen(button, "click", function selectMode() {
          emitMode(mode.value);
        });
      });
      panel.appendChild(modeGroup);
      normalizeQuotes = makeInput("zmr-normalize-quotes", "checkbox");
      normalizeRow = makeElement("div", "zmr-settings-field zmr-settings-check-field");
      normalizeLabel = makeElement("label", "", "规范化弯引号");
      normalizeLabel.htmlFor = normalizeQuotes.id;
      normalizeRow.appendChild(normalizeLabel);
      normalizeRow.appendChild(normalizeQuotes);
      panel.appendChild(normalizeRow);
      tuning = makeElement("fieldset", "zmr-tuning-group");
      tuning.setAttribute("aria-label", "当前主题微调");
      fontSize = makeInput("zmr-font-size", "number", { min: 12, max: 32, step: 1, inputmode: "numeric" });
      lineHeight = makeInput("zmr-line-height", "number", { min: 1.1, max: 2.6, step: 0.1, inputmode: "decimal" });
      textColor = makeInput("zmr-text-color", "color");
      accentColor = makeInput("zmr-accent-color", "color");
      bubbleColor = makeInput("zmr-bubble-color", "color");
      opacity = makeInput("zmr-opacity", "range", { min: 40, max: 100, step: 1 });
      opacityOutput = makeElement("output", "zmr-opacity-output", "96%");
      opacityOutput.setAttribute("for", opacity.id);
      opacityControl = makeElement("div", "zmr-opacity-control");
      opacityControl.appendChild(opacity);
      opacityControl.appendChild(opacityOutput);
      opacityRow = makeElement("div", "zmr-settings-field");
      opacityLabel = makeElement("label", "", "AI 气泡透明度");
      opacityLabel.htmlFor = opacity.id;
      opacityRow.appendChild(opacityLabel);
      opacityRow.appendChild(opacityControl);
      tuning.appendChild(makeField("字号", fontSize));
      tuning.appendChild(makeField("行距", lineHeight));
      tuning.appendChild(makeField("正文色", textColor));
      tuning.appendChild(makeField("高亮色", accentColor));
      tuning.appendChild(makeField("AI 气泡色", bubbleColor));
      tuning.appendChild(opacityRow);
      panel.appendChild(tuning);
      actions = makeElement("div", "zmr-settings-actions");
      resetButton = makeElement("button", "zmr-command-button", "恢复当前主题默认");
      resetButton.type = "button";
      resetAllButton = makeElement("button", "zmr-command-button", "全部恢复默认");
      resetAllButton.type = "button";
      actions.appendChild(resetButton);
      actions.appendChild(resetAllButton);
      panel.appendChild(actions);
      host.appendChild(toggle);
      host.appendChild(panel);
      (documentLocal.body || documentLocal.documentElement).appendChild(host);
      listen(toggle, "click", open);
      listen(closeButton, "click", function closeFromButton() {
        close(true);
      });
      listen(resetButton, "click", emitReset);
      listen(resetAllButton, "click", emitResetAll);
      listen(normalizeQuotes, "change", function updateNormalizeQuotes() {
        if (!destroyed && typeof settings.onNormalizeQuotes === "function") {
          settings.onNormalizeQuotes(normalizeQuotes.checked === true);
        }
      });
      listen(fontSize, "input", function updateFontSize() {
        emitValue("fontSize", Number(fontSize.value));
      });
      listen(lineHeight, "input", function updateLineHeight() {
        emitValue("lineHeight", Number(lineHeight.value));
      });
      listen(textColor, "input", function updateTextColor() {
        emitValue("textColor", textColor.value);
      });
      listen(accentColor, "input", function updateAccentColor() {
        emitValue("accentColor", accentColor.value);
      });
      listen(bubbleColor, "input", function updateBubbleColor() {
        emitValue("aiBubbleColor", bubbleColor.value);
      });
      listen(opacity, "input", function updateOpacity() {
        emitValue("opacity", Number(opacity.value));
      });
      listen(documentLocal, "keydown", onKeyDown);
    }

    build();
    api = Object.freeze({
      meta: Object.freeze({ owner: OWNER, version: VERSION, id: "zmr-settings-ui" }),
      sync: sync,
      open: open,
      close: close,
      ensureMounted: ensureMounted,
      setVisible: setVisible,
      destroy: destroy
    });
    return api;
  }

  createTavernMmdZmrSettingsUi.meta = Object.freeze({ owner: OWNER, version: VERSION, id: ID });
  namespace.settingsUiFactory = createTavernMmdZmrSettingsUi;

  global.setTimeout(function retireSettingsUiInstallerNodes() {
    var selector = "script[data-zmr-owner='" + OWNER + "'][data-zmr-id='" + ID + "']";
    var nodes = documentRef.querySelectorAll(selector);
    var index;
    for (index = 0; index < nodes.length; index += 1) {
      nodes[index].remove();
    }
  }, 0);
})(window);
