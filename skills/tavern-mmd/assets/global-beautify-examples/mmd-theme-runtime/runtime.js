(function installTavernMmdZmrRuntime(global) {
  "use strict";

  var OWNER = "tavern-mmd/zmr";
  var VERSION = "2.0.0";
  var ID = "zmr-theme-runtime";
  var STYLE_ID = "zmr-theme-style";
  var STORAGE_KEY = "tavern-mmd/zmr/theme-settings/schema-2";
  var LEGACY_STORAGE_KEY = "tavern-mmd/zmr/theme-settings/schema-1";
  var SCHEMA = 2;
  var documentRef = global.document;
  var rootElement = documentRef.documentElement;
  var namespace = global[OWNER];
  var previousLease;
  var incomingStyle;
  var themeStyle = null;
  var cleanup;
  var quotePlugin;
  var assetPlugin;
  var ui;
  var routeActive = false;
  var destroyed = false;
  var activeTheme = "day";
  var listeners = [];
  var routeTimer = 0;
  var suspended = false;
  var pageHidden = false;
  var workerStarted = false;
  var api;

  var DEFAULTS = Object.freeze({
    day: Object.freeze({
      fontSize: 16,
      lineHeight: 1.65,
      textColor: "#3b2425",
      accentColor: "#7b1e2b",
      aiBubbleColor: "#fffaf2",
      opacity: 96
    }),
    night: Object.freeze({
      fontSize: 16,
      lineHeight: 1.65,
      textColor: "#f3ece2",
      accentColor: "#efabb5",
      aiBubbleColor: "#24262b",
      opacity: 96
    })
  });

  var LEGACY_DEFAULTS = Object.freeze({
    day: Object.freeze({
      fontSize: 16,
      lineHeight: 1.65,
      textColor: "#3b2425",
      accentColor: "#7b1e2b",
      aiBubbleColor: "#fffaf2",
      opacity: 96
    }),
    night: Object.freeze({
      fontSize: 16,
      lineHeight: 1.65,
      textColor: "#f3ece2",
      accentColor: "#efabb5",
      aiBubbleColor: "#24262b",
      opacity: 96
    })
  });

  var THEME_KEYS = Object.freeze(["fontSize", "lineHeight", "textColor", "accentColor", "aiBubbleColor", "opacity"]);

  function ownedStyleSelector() {
    return "style[data-zmr-owner='" + OWNER + "'][data-zmr-id='" + STYLE_ID + "']";
  }

  function currentStyles() {
    return documentRef.querySelectorAll(ownedStyleSelector());
  }

  function chooseNewestStyle(nodes) {
    var candidate = null;
    var index;
    for (index = 0; index < nodes.length; index += 1) {
      if (nodes[index].getAttribute("data-zmr-version") === VERSION) {
        candidate = nodes[index];
      }
    }
    return candidate;
  }

  function removeDuplicateStyles(except) {
    var nodes = currentStyles();
    var index;
    for (index = 0; index < nodes.length; index += 1) {
      if (nodes[index] !== except && nodes[index].getAttribute("data-zmr-version") === VERSION) {
        nodes[index].remove();
      }
    }
  }

  function removeAllOwnedStyles(except) {
    var nodes = currentStyles();
    var index;
    for (index = 0; index < nodes.length; index += 1) {
      if (nodes[index] !== except) {
        nodes[index].remove();
      }
    }
  }

  function takeoverStyle(preferred) {
    var candidate = preferred && preferred.nodeType === 1 ? preferred : chooseNewestStyle(currentStyles());
    if (!candidate && themeStyle && themeStyle.nodeType === 1) {
      candidate = themeStyle;
    }
    if (!candidate) {
      return null;
    }
    candidate.id = STYLE_ID;
    candidate.setAttribute("data-zmr-owned", "asset");
    candidate.setAttribute("data-zmr-owner", OWNER);
    candidate.setAttribute("data-zmr-version", VERSION);
    candidate.setAttribute("data-zmr-id", STYLE_ID);
    if (documentRef.head && candidate.parentNode !== documentRef.head) {
      documentRef.head.appendChild(candidate);
    }
    removeDuplicateStyles(candidate);
    themeStyle = candidate;
    return candidate;
  }

  function ensureAssets() {
    var newest;
    if (destroyed) {
      return;
    }
    newest = chooseNewestStyle(currentStyles());
    takeoverStyle(newest || themeStyle);
  }

  function retireBootstrapNodes() {
    var selector = "script[data-zmr-owner='" + OWNER + "'][data-zmr-id='" + ID + "']";
    var nodes = documentRef.querySelectorAll(selector);
    var index;
    for (index = 0; index < nodes.length; index += 1) {
      nodes[index].remove();
    }
  }

  global.setTimeout(retireBootstrapNodes, 0);
  if (!namespace || typeof namespace !== "object") {
    namespace = {};
    global[OWNER] = namespace;
  }

  incomingStyle = chooseNewestStyle(currentStyles());
  if (incomingStyle && incomingStyle.parentNode) {
    incomingStyle.parentNode.removeChild(incomingStyle);
  }
  previousLease = namespace.lease;
  if (previousLease && previousLease.meta && previousLease.meta.owner === OWNER && previousLease.meta.version === VERSION && previousLease.meta.id === ID) {
    try {
      previousLease.refreshAssets(incomingStyle);
      previousLease.reenter();
    } catch (reuseError) {
      namespace.lastError = { source: "lease-reuse", error: reuseError, at: Date.now() };
    }
    return;
  }
  if (previousLease && typeof previousLease.destroy === "function") {
    try {
      previousLease.destroy("superseded");
    } catch (previousError) {
      namespace.lastError = { source: "previous-destroy", error: previousError, at: Date.now() };
    }
  }
  namespace.lease = null;

  function cloneTheme(source) {
    return {
      fontSize: source.fontSize,
      lineHeight: source.lineHeight,
      textColor: source.textColor,
      accentColor: source.accentColor,
      aiBubbleColor: source.aiBubbleColor,
      opacity: source.opacity
    };
  }

  function freshState() {
    return {
      schema: SCHEMA,
      mode: "day",
      normalizeQuotes: false,
      overrides: { day: {}, night: {} }
    };
  }

  function isRecord(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }

  function hasOwn(source, key) {
    return Object.prototype.hasOwnProperty.call(source, key);
  }

  function validMode(value) {
    return value === "day" || value === "night" || value === "native";
  }

  function validColor(value) {
    return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
  }

  function validInteger(value, minimum, maximum) {
    return typeof value === "number" && Number.isFinite(value) && Math.floor(value) === value && value >= minimum && value <= maximum;
  }

  function validLineHeight(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 1.1 && value <= 2.6;
  }

  function normalizeThemeValue(key, value) {
    if (key === "fontSize" && validInteger(value, 12, 32)) {
      return value;
    }
    if (key === "lineHeight" && validLineHeight(value)) {
      return Math.round(value * 100) / 100;
    }
    if ((key === "textColor" || key === "accentColor" || key === "aiBubbleColor") && validColor(value)) {
      return value.toLowerCase();
    }
    if (key === "opacity" && validInteger(value, 40, 100)) {
      return value;
    }
    return null;
  }

  function validateOverride(raw) {
    var output = {};
    var index;
    var key;
    var value;
    if (!isRecord(raw)) {
      return output;
    }
    for (index = 0; index < THEME_KEYS.length; index += 1) {
      key = THEME_KEYS[index];
      if (hasOwn(raw, key)) {
        value = normalizeThemeValue(key, raw[key]);
        if (value !== null) {
          output[key] = value;
        }
      }
    }
    return output;
  }

  function validateState(raw) {
    var output = freshState();
    if (!isRecord(raw) || raw.schema !== SCHEMA) {
      return output;
    }
    output.mode = validMode(raw.mode) ? raw.mode : output.mode;
    output.normalizeQuotes = typeof raw.normalizeQuotes === "boolean" ? raw.normalizeQuotes : false;
    if (isRecord(raw.overrides)) {
      output.overrides.day = validateOverride(raw.overrides.day);
      output.overrides.night = validateOverride(raw.overrides.night);
    }
    return output;
  }

  function migrateLegacy(raw) {
    var output = freshState();
    var modes = ["day", "night"];
    var modeIndex;
    var mode;
    var source;
    var keyIndex;
    var key;
    var value;
    if (!isRecord(raw) || raw.schema !== 1) {
      return output;
    }
    output.mode = validMode(raw.mode) ? raw.mode : output.mode;
    output.normalizeQuotes = typeof raw.normalizeQuotes === "boolean" ? raw.normalizeQuotes : false;
    if (!isRecord(raw.themes)) {
      return output;
    }
    for (modeIndex = 0; modeIndex < modes.length; modeIndex += 1) {
      mode = modes[modeIndex];
      source = isRecord(raw.themes[mode]) ? raw.themes[mode] : {};
      for (keyIndex = 0; keyIndex < THEME_KEYS.length; keyIndex += 1) {
        key = THEME_KEYS[keyIndex];
        if (hasOwn(source, key)) {
          value = normalizeThemeValue(key, source[key]);
          if (value !== null && value !== LEGACY_DEFAULTS[mode][key]) {
            output.overrides[mode][key] = value;
          }
        }
      }
    }
    return output;
  }

  function serializableState(source) {
    return {
      schema: SCHEMA,
      mode: source.mode,
      normalizeQuotes: source.normalizeQuotes,
      overrides: {
        day: validateOverride(source.overrides.day),
        night: validateOverride(source.overrides.night)
      }
    };
  }

  function writeState(source) {
    global.localStorage.setItem(STORAGE_KEY, JSON.stringify(serializableState(source)));
  }

  function loadState() {
    var stored;
    var legacy;
    var migrated;
    try {
      stored = global.localStorage.getItem(STORAGE_KEY);
      if (typeof stored === "string") {
        return validateState(JSON.parse(stored));
      }
      legacy = global.localStorage.getItem(LEGACY_STORAGE_KEY);
      if (typeof legacy === "string") {
        migrated = migrateLegacy(JSON.parse(legacy));
        writeState(migrated);
        return migrated;
      }
    } catch (error) {
      namespace.lastError = { source: "storage-read", error: error, at: Date.now() };
    }
    return freshState();
  }

  var state = loadState();
  if (state.mode === "day" || state.mode === "night") {
    activeTheme = state.mode;
  }

  function persist() {
    try {
      writeState(state);
    } catch (error) {
      namespace.lastError = { source: "storage-write", error: error, at: Date.now() };
    }
  }

  function effectiveTheme(mode) {
    var theme = cloneTheme(DEFAULTS[mode]);
    var override = state.overrides[mode] || {};
    var index;
    var key;
    for (index = 0; index < THEME_KEYS.length; index += 1) {
      key = THEME_KEYS[index];
      if (hasOwn(override, key)) {
        theme[key] = override[key];
      }
    }
    return theme;
  }

  function hexToChannels(color) {
    var value = color.slice(1);
    return [
      parseInt(value.slice(0, 2), 16),
      parseInt(value.slice(2, 4), 16),
      parseInt(value.slice(4, 6), 16)
    ].join(" ");
  }

  function clearReadingVariables() {
    rootElement.style.removeProperty("--zmr-reading-font-size");
    rootElement.style.removeProperty("--zmr-reading-line-height");
    rootElement.style.removeProperty("--zmr-reading-text");
    rootElement.style.removeProperty("--zmr-reading-accent");
    rootElement.style.removeProperty("--zmr-ai-bubble-rgb");
    rootElement.style.removeProperty("--zmr-ai-bubble-opacity");
  }

  function applyThemeVariables(theme) {
    rootElement.style.setProperty("--zmr-reading-font-size", String(theme.fontSize) + "px");
    rootElement.style.setProperty("--zmr-reading-line-height", String(theme.lineHeight));
    rootElement.style.setProperty("--zmr-reading-text", theme.textColor);
    rootElement.style.setProperty("--zmr-reading-accent", theme.accentColor);
    rootElement.style.setProperty("--zmr-ai-bubble-rgb", hexToChannels(theme.aiBubbleColor));
    rootElement.style.setProperty("--zmr-ai-bubble-opacity", String(theme.opacity / 100));
  }

  function editableTheme() {
    return effectiveTheme(state.mode === "native" ? activeTheme : state.mode);
  }

  function syncUi() {
    if (ui) {
      ui.sync({ mode: state.mode, normalizeQuotes: state.normalizeQuotes, theme: editableTheme() });
    }
  }

  function applyState() {
    if (destroyed) {
      return;
    }
    if (!routeActive) {
      rootElement.removeAttribute("data-zmr-mode");
      clearReadingVariables();
      syncUi();
      return;
    }
    if (state.mode === "native") {
      rootElement.removeAttribute("data-zmr-mode");
      clearReadingVariables();
      cleanup.setCleaning(false);
    } else {
      activeTheme = state.mode;
      rootElement.setAttribute("data-zmr-mode", state.mode);
      applyThemeVariables(effectiveTheme(state.mode));
      cleanup.setCleaning(true);
    }
    syncUi();
  }

  function setMode(mode) {
    if (destroyed || !validMode(mode)) {
      return api;
    }
    if (mode === "day" || mode === "night") {
      activeTheme = mode;
    }
    state.mode = mode;
    applyState();
    persist();
    return api;
  }

  function updateValue(key, value) {
    var normalized;
    if (destroyed || state.mode === "native") {
      return;
    }
    normalized = normalizeThemeValue(key, value);
    if (normalized === null) {
      syncUi();
      return;
    }
    if (normalized === DEFAULTS[state.mode][key]) {
      if (state.overrides[state.mode]) {
        delete state.overrides[state.mode][key];
      }
    } else {
      if (!state.overrides[state.mode]) {
        state.overrides[state.mode] = {};
      }
      state.overrides[state.mode][key] = normalized;
    }
    applyState();
    persist();
  }

  function setNormalizeQuotes(enabled) {
    var chatRoot;
    state.normalizeQuotes = enabled === true;
    quotePlugin.setNormalizeQuotes(state.normalizeQuotes);
    syncUi();
    persist();
    if (state.normalizeQuotes && routeActive) {
      chatRoot = documentRef.querySelector(".chat");
      cleanup.flush(chatRoot || documentRef.body || rootElement);
    }
  }

  function resetCurrentTheme() {
    if (state.mode === "day" || state.mode === "night") {
      delete state.overrides[state.mode];
      applyState();
      persist();
    }
  }

  function resetAllThemes() {
    state.overrides.day = {};
    state.overrides.night = {};
    applyState();
    persist();
  }

  function listen(target, type, handler) {
    target.addEventListener(type, handler);
    listeners.push({ target: target, type: type, handler: handler });
  }

  function isChatRoute() {
    var hash = String(global.location && global.location.hash || "").toLowerCase();
    var chat;
    if (hash.indexOf("chat/chat") !== -1) {
      return true;
    }
    chat = documentRef.querySelector(".chat");
    if (!chat || chat.hidden || chat.getAttribute("aria-hidden") === "true") {
      return false;
    }
    if (!hash) {
      return true;
    }
    return typeof chat.getClientRects !== "function" || chat.getClientRects().length > 0;
  }

  function enterChat() {
    var chatRoot;
    if (destroyed || suspended || pageHidden) {
      return;
    }
    ensureAssets();
    ui.ensureMounted();
    if (routeActive) {
      return;
    }
    routeActive = true;
    ui.setVisible(true);
    chatRoot = documentRef.querySelector(".chat");
    cleanup.start(workerStarted ? chatRoot || documentRef.body || rootElement : documentRef.body || rootElement);
    workerStarted = true;
    applyState();
  }

  function leaveChat() {
    if (destroyed) {
      return;
    }
    if (routeTimer) {
      global.clearTimeout(routeTimer);
      routeTimer = 0;
    }
    routeActive = false;
    ui.setVisible(false);
    cleanup.stop();
    cleanup.restore();
    rootElement.removeAttribute("data-zmr-mode");
    clearReadingVariables();
  }

  function refreshAssets(preferred) {
    if (!destroyed) {
      takeoverStyle(preferred || chooseNewestStyle(currentStyles()) || themeStyle);
      if (ui) {
        ui.ensureMounted();
      }
    }
    return api;
  }

  function reenter() {
    if (!destroyed && !suspended && !pageHidden) {
      if (ui) {
        ui.ensureMounted();
      }
      routeActive = false;
      reconcileRoute();
    }
    return api;
  }

  function reconcileRoute() {
    routeTimer = 0;
    if (!destroyed && !suspended && !pageHidden) {
      if (isChatRoute()) {
        enterChat();
      } else {
        leaveChat();
      }
    }
  }

  function scheduleRouteCheck() {
    if (!destroyed && !suspended && !pageHidden && !routeTimer) {
      routeTimer = global.setTimeout(reconcileRoute, 0);
    }
  }

  function handlePageHide() {
    if (destroyed) {
      return;
    }
    suspended = true;
    pageHidden = true;
    leaveChat();
  }

  function handlePageShow() {
    if (destroyed) {
      return;
    }
    pageHidden = false;
    suspended = false;
    scheduleRouteCheck();
  }

  function destroy(reason) {
    var index;
    if (destroyed) {
      return;
    }
    destroyed = true;
    if (routeTimer) {
      global.clearTimeout(routeTimer);
      routeTimer = 0;
    }
    for (index = listeners.length - 1; index >= 0; index -= 1) {
      listeners[index].target.removeEventListener(listeners[index].type, listeners[index].handler);
    }
    listeners.length = 0;
    if (cleanup) {
      cleanup.destroy();
    }
    if (ui) {
      ui.destroy();
    }
    if (reason === "superseded") {
      if (themeStyle && themeStyle.isConnected) {
        themeStyle.remove();
      }
    } else {
      removeAllOwnedStyles(null);
    }
    themeStyle = null;
    rootElement.removeAttribute("data-zmr-mode");
    clearReadingVariables();
    routeActive = false;
    if (namespace.lease === api) {
      namespace.lease = null;
    }
    namespace.lastDestroyReason = reason || "destroy";
  }

  if (!takeoverStyle(incomingStyle)) {
    namespace.lastError = { source: "theme-style", error: new Error("Missing owned theme style"), at: Date.now() };
    return;
  }
  removeAllOwnedStyles(themeStyle);
  if (typeof namespace.cleanupFactory !== "function" || typeof namespace.quotePluginFactory !== "function" || typeof namespace.settingsUiFactory !== "function") {
    namespace.lastError = { source: "factories", error: new Error("Missing zmr factories"), at: Date.now() };
    removeAllOwnedStyles(null);
    return;
  }

  cleanup = namespace.cleanupFactory({ cleaning: false });
  quotePlugin = namespace.quotePluginFactory({ normalizeQuotes: state.normalizeQuotes });
  assetPlugin = Object.freeze({
    id: "zmr-asset-supervisor",
    meta: Object.freeze({ owner: OWNER, version: VERSION, id: "zmr-asset-supervisor" }),
    process: ensureAssets
  });
  cleanup.register(quotePlugin);
  cleanup.register(assetPlugin);
  ui = namespace.settingsUiFactory({
    onMode: setMode,
    onValue: updateValue,
    onNormalizeQuotes: setNormalizeQuotes,
    onReset: resetCurrentTheme,
    onResetAll: resetAllThemes
  });

  api = Object.freeze({
    meta: Object.freeze({ owner: OWNER, version: VERSION, id: ID, storageKey: STORAGE_KEY }),
    day: function day() {
      return setMode("day");
    },
    night: function night() {
      return setMode("night");
    },
    native: function native() {
      return setMode("native");
    },
    setMode: setMode,
    destroy: destroy,
    enter: enterChat,
    leave: leaveChat,
    reenter: reenter,
    refreshAssets: refreshAssets,
    setNormalizeQuotes: setNormalizeQuotes,
    getMode: function getMode() {
      return state.mode;
    }
  });
  namespace.lease = api;

  listen(global, "hashchange", scheduleRouteCheck);
  listen(global, "popstate", scheduleRouteCheck);
  listen(global, "pageshow", handlePageShow);
  listen(global, "focus", scheduleRouteCheck);
  listen(global, "pagehide", handlePageHide);
  listen(documentRef, "visibilitychange", scheduleRouteCheck);
  reconcileRoute();
})(window);
