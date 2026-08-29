(function installTavernMmdZmrCleanupFactory(global) {
  "use strict";

  var OWNER = "tavern-mmd/zmr";
  var VERSION = "2.0.0";
  var ID = "zmr-cleanup-factory";
  var documentRef = global.document;
  var namespace = global[OWNER];

  if (!namespace || typeof namespace !== "object") {
    namespace = {};
    global[OWNER] = namespace;
  }

  var SELECTOR_PACK = Object.freeze({
    reviewedAt: "2026-08-25",
    targets: Object.freeze([
      ".chat",
      ".chat-bg",
      ".chat-scope-box",
      ".scroll-view",
      ".chat-body",
      ".topTabbar",
      ".header-scope",
      ".chat-bottom-wapper",
      ".chat-bottom",
      ".chat-input-scope",
      ".shortcut-bar-wrapper",
      ".shortcut-btn",
      ".instruction-chip",
      ".chat-input-tool-btn",
      ".msg-option-scope",
      ".more-options-scope",
      ".u-popup__content",
      ".u-safe-bottom",
      ".u-picker",
      ".role-setting",
      ".custom-instruction-scope",
      ".model-setting-scope",
      ".history-setting-scope",
      ".share-chat-page",
      ".share-chat-scope",
      ".share-chat-wrapper",
      ".share-chat-topbar",
      ".modify-scope",
      ".confirm-scope",
      ".prologue-scope",
      ".textarea-wrapper",
      ".input-wrapper",
      ".input-scope",
      ".custom-textarea-box",
      ".depth-input",
      ".uni-input-wrapper",
      ".uni-textarea-wrapper",
      ".uni-input-input",
      ".uni-textarea-textarea",
      ".vig-native-input__el",
      ".vig-native-textarea__el",
      ".content.left",
      ".content.right",
      ".theme-dark",
      ".doc-markdown-body--dark",
      ".vditor--dark",
      ".active-dark",
      ".textarea-dark",
      ".input-dark"
    ]),
    messageWrappers: Object.freeze([
      ".msg-content-box",
      ".msg-options-box",
      ".msg-mask"
    ]),
    skipped: Object.freeze([
      "[data-zmr-owned]",
      "[data-sid]",
      "[data-g3v]",
      "[data-zsf-ball]",
      "[data-zsf-drawer]",
      "[data-shadowcast]",
      "[data-shadow-cast]",
      "[data-statusbar]",
      "[data-status-bar]",
      ".g3-host",
      ".z-status-box",
      "z-live-widget"
    ])
  });

  var STYLE_PROPERTIES = Object.freeze([
    "background",
    "background-color",
    "color",
    "border-color",
    "box-shadow",
    "text-shadow",
    "-webkit-text-fill-color",
    "filter",
    "--background-color",
    "--primary-font-color",
    "--input-font-color",
    "--card-background-color",
    "--input-background-color",
    "--model-setting",
    "--share-item-bg-color",
    "--vig-native-ph-color"
  ]);

  var CUSTOM_PROPERTIES = Object.freeze([
    "--background-color",
    "--primary-font-color",
    "--input-font-color",
    "--card-background-color",
    "--input-background-color",
    "--model-setting",
    "--share-item-bg-color",
    "--vig-native-ph-color"
  ]);

  var DARK_CLASSES = Object.freeze([
    "theme-dark",
    "doc-markdown-body--dark",
    "vditor--dark",
    "active-dark",
    "textarea-dark",
    "input-dark"
  ]);

  var POLLUTION_COLORS = Object.freeze([
    "#0d0e0f",
    "#101113",
    "#101014",
    "#141414",
    "#17181a",
    "#1a1a1a",
    "#1c1c1e",
    "#1e1f24",
    "#212226",
    "#25262a",
    "#2a2b30",
    "#33353b",
    "#fff",
    "#ffffff",
    "#dc8333",
    "#ff6d97",
    "#409eff",
    "#3c9cff",
    "#1989fa",
    "rgb(255,255,255)",
    "rgb(13,14,15)",
    "rgb(16,17,19)",
    "rgb(23,24,26)",
    "rgb(30,31,36)",
    "rgb(220,131,51)",
    "rgb(255,109,151)",
    "rgb(64,158,255)",
    "rgb(25,137,250)"
  ]);

  var EFFECT_FRAGMENTS = Object.freeze([
    "drop-shadow(",
    "brightness(0)",
    "invert(1)",
    "0px0px",
    "0 0 "
  ]);

  function joinSelectors(parts) {
    return parts.join(",");
  }

  function compactCssValue(value) {
    var source = String(value || "").toLowerCase();
    var output = "";
    var index;
    var code;
    for (index = 0; index < source.length; index += 1) {
      code = source.charCodeAt(index);
      if (code !== 9 && code !== 10 && code !== 12 && code !== 13 && code !== 32) {
        output += source.charAt(index);
      }
    }
    return output;
  }

  function isHexDigit(character) {
    var code = character ? character.toLowerCase().charCodeAt(0) : 0;
    return code >= 48 && code <= 57 || code >= 97 && code <= 102;
  }

  function containsColor(value, token) {
    var start = 0;
    var position;
    var after;
    if (token.charAt(0) !== "#") {
      return value.indexOf(token) !== -1;
    }
    while (start < value.length) {
      position = value.indexOf(token, start);
      if (position === -1) {
        return false;
      }
      after = value.charAt(position + token.length);
      if (!isHexDigit(after)) {
        return true;
      }
      start = position + token.length;
    }
    return false;
  }

  function hasKnownPollutionColor(value) {
    var normalized = compactCssValue(value);
    var index;
    for (index = 0; index < POLLUTION_COLORS.length; index += 1) {
      if (containsColor(normalized, POLLUTION_COLORS[index])) {
        return true;
      }
    }
    return false;
  }

  function hasKnownEffect(value) {
    var normalized = String(value || "").toLowerCase();
    var index;
    for (index = 0; index < EFFECT_FRAGMENTS.length; index += 1) {
      if (normalized.indexOf(EFFECT_FRAGMENTS[index]) !== -1) {
        return true;
      }
    }
    return false;
  }

  function createTavernMmdZmrCleanup(options) {
    var settings = options && typeof options === "object" ? options : {};
    var delay = Number.isFinite(settings.delay) ? Math.max(0, settings.delay) : 24;
    var targetSelector = joinSelectors(SELECTOR_PACK.targets);
    var messageWrapperSelector = joinSelectors(SELECTOR_PACK.messageWrappers);
    var skippedSelector = joinSelectors(SELECTOR_PACK.skipped);
    var documentLocal = settings.document || documentRef;
    var deltas = new Map();
    var deferredCandidates = new Set();
    var plugins = new Map();
    var pendingRecords = [];
    var pendingRoots = [];
    var initialRoot = null;
    var initialScanDone = false;
    var timer = 0;
    var running = false;
    var cleaning = settings.cleaning !== false;
    var destroyed = false;
    var processing = false;
    var rerun = false;
    var lastError = null;
    var observedRoot = null;
    var observer = new global.MutationObserver(onMutations);
    var observerOptions = {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["style", "class", "color", "hidden", "aria-hidden"]
    };
    var api;

    function reportError(error, source) {
      lastError = { error: error, source: source, at: Date.now() };
      if (typeof settings.onError === "function") {
        try {
          settings.onError(error, source);
        } catch (ignored) {
          lastError = { error: ignored, source: "onError", at: Date.now() };
        }
      }
    }

    function isElement(node) {
      return !!node && node.nodeType === 1;
    }

    function elementFromNode(node) {
      if (isElement(node)) {
        return node;
      }
      return node && node.parentElement ? node.parentElement : null;
    }

    function isSkipped(node) {
      var element = elementFromNode(node);
      return !!element && !!element.closest(skippedSelector);
    }

    function isAllowedMessageElement(element) {
      var content = element && element.closest ? element.closest(".content.left,.content.right") : null;
      if (!content) {
        return true;
      }
      if (element === content) {
        return true;
      }
      return element.parentElement === content && element.matches(messageWrapperSelector);
    }

    function isInSelectorPack(node) {
      var element = elementFromNode(node);
      return !!element && !isSkipped(element) && element.matches(targetSelector + "," + messageWrapperSelector) && isAllowedMessageElement(element);
    }

    function drainObserverRecords() {
      var records = observer.takeRecords();
      var index;
      for (index = 0; index < records.length; index += 1) {
        pendingRecords.push(records[index]);
      }
    }

    function observeCurrentRoot() {
      if (running && observedRoot) {
        observer.observe(observedRoot, observerOptions);
      }
    }

    function pauseObservation() {
      var shouldResume = running && !!observedRoot && !processing;
      if (shouldResume) {
        drainObserverRecords();
        observer.disconnect();
      }
      return shouldResume;
    }

    function resumeObservation(shouldResume) {
      if (shouldResume && running && !destroyed) {
        observeCurrentRoot();
        if (pendingRecords.length) {
          schedule(0);
        }
      }
    }

    function ensureDelta(element) {
      var delta = deltas.get(element);
      if (!delta) {
        delta = { styles: new Map(), classes: new Set(), color: null };
        deltas.set(element, delta);
      }
      return delta;
    }

    function shouldRemoveProperty(property, value, nativeClassPresent) {
      if (!value) {
        return false;
      }
      if (CUSTOM_PROPERTIES.indexOf(property) !== -1) {
        return true;
      }
      if (hasKnownPollutionColor(value)) {
        return true;
      }
      if (nativeClassPresent && (property === "box-shadow" || property === "text-shadow" || property === "filter")) {
        return true;
      }
      return property === "filter" && hasKnownEffect(value);
    }

    function cleanElement(element) {
      var nativeClassPresent = false;
      var index;
      var className;
      var property;
      var value;
      var delta;
      var colorValue;
      if (!isElement(element) || !element.isConnected || !isInSelectorPack(element)) {
        return;
      }
      for (index = 0; index < DARK_CLASSES.length; index += 1) {
        if (element.classList.contains(DARK_CLASSES[index])) {
          nativeClassPresent = true;
          break;
        }
      }
      for (index = 0; index < DARK_CLASSES.length; index += 1) {
        className = DARK_CLASSES[index];
        if (element.classList.contains(className)) {
          delta = ensureDelta(element);
          delta.classes.add(className);
          element.classList.remove(className);
        }
      }
      for (index = 0; index < STYLE_PROPERTIES.length; index += 1) {
        property = STYLE_PROPERTIES[index];
        value = element.style.getPropertyValue(property);
        if (shouldRemoveProperty(property, value, nativeClassPresent)) {
          delta = ensureDelta(element);
          delta.styles.set(property, {
            value: value,
            priority: element.style.getPropertyPriority(property)
          });
          element.style.removeProperty(property);
        }
      }
      colorValue = element.getAttribute("color");
      if (colorValue && hasKnownPollutionColor(colorValue)) {
        delta = ensureDelta(element);
        delta.color = { value: colorValue };
        element.removeAttribute("color");
      }
    }

    function collectCandidateSubtree(root, output) {
      var candidates;
      var index;
      if (!isElement(root) || isSkipped(root)) {
        return;
      }
      if (isInSelectorPack(root)) {
        output.add(root);
      }
      candidates = root.querySelectorAll(targetSelector + "," + messageWrapperSelector);
      for (index = 0; index < candidates.length; index += 1) {
        if (isInSelectorPack(candidates[index])) {
          output.add(candidates[index]);
        }
      }
    }

    function pruneDisconnected() {
      deltas.forEach(function pruneDelta(value, element) {
        if (!element.isConnected) {
          deltas.delete(element);
        }
      });
      deferredCandidates.forEach(function pruneDeferred(element) {
        if (!element.isConnected) {
          deferredCandidates.delete(element);
        }
      });
    }

    function restore() {
      var shouldResume = pauseObservation();
      try {
        deltas.forEach(function restoreDelta(delta, element) {
          if (!element.isConnected) {
            deltas.delete(element);
            return;
          }
          delta.styles.forEach(function restoreStyle(saved, property) {
            if (!element.style.getPropertyValue(property)) {
              element.style.setProperty(property, saved.value, saved.priority);
            }
          });
          delta.classes.forEach(function restoreClass(className) {
            if (!element.classList.contains(className)) {
              element.classList.add(className);
            }
          });
          if (delta.color && !element.hasAttribute("color")) {
            element.setAttribute("color", delta.color.value);
          }
          deltas.delete(element);
        });
      } finally {
        resumeObservation(shouldResume);
      }
      return api;
    }

    function teardownPlugin(plugin, pluginId) {
      var shouldResume = pauseObservation();
      if (typeof plugin.stop === "function") {
        try {
          plugin.stop();
        } catch (error) {
          reportError(error, "plugin-stop:" + pluginId);
        }
      }
      if (typeof plugin.destroy === "function") {
        try {
          plugin.destroy();
        } catch (error) {
          reportError(error, "plugin-destroy:" + pluginId);
        }
      }
      resumeObservation(shouldResume);
    }

    function invokePlugins(context) {
      plugins.forEach(function invokePlugin(plugin, pluginId) {
        try {
          if (typeof plugin === "function") {
            plugin(context);
          } else if (plugin && typeof plugin.process === "function") {
            plugin.process(context);
          }
        } catch (error) {
          reportError(error, "plugin:" + pluginId);
        }
      });
    }

    function buildContext(records, full, fullRoot, addedNodes, attributeTargets, textTargets) {
      return Object.freeze({
        records: records,
        full: full,
        root: fullRoot,
        addedNodes: Object.freeze(addedNodes.slice()),
        attributeTargets: Object.freeze(attributeTargets.slice()),
        textTargets: Object.freeze(textTargets.slice()),
        cleaning: cleaning,
        selectorPack: SELECTOR_PACK,
        isSkipped: isSkipped,
        isInSelectorPack: isInSelectorPack,
        engine: api
      });
    }

    function runCycle() {
      var records;
      var roots;
      var fullRoot;
      var full;
      var candidates = new Set();
      var addedNodes = [];
      var attributeTargets = [];
      var textTargets = [];
      var index;
      var record;
      var childIndex;
      var context;
      if (!running || destroyed) {
        return false;
      }
      if (processing) {
        rerun = true;
        return false;
      }
      processing = true;
      if (timer) {
        global.clearTimeout(timer);
        timer = 0;
      }
      drainObserverRecords();
      observer.disconnect();
      records = pendingRecords.splice(0, pendingRecords.length);
      roots = pendingRoots.splice(0, pendingRoots.length);
      fullRoot = initialRoot;
      full = !!fullRoot && !initialScanDone;
      if (full) {
        initialRoot = null;
        initialScanDone = true;
        roots.unshift(fullRoot);
      }
      try {
        for (index = 0; index < records.length; index += 1) {
          record = records[index];
          if (record.type === "childList") {
            for (childIndex = 0; childIndex < record.addedNodes.length; childIndex += 1) {
              addedNodes.push(record.addedNodes[childIndex]);
            }
          } else if (record.type === "attributes") {
            attributeTargets.push(record.target);
          } else if (record.type === "characterData") {
            textTargets.push(record.target);
          }
        }
        for (index = 0; index < roots.length; index += 1) {
          addedNodes.push(roots[index]);
        }
        context = buildContext(records, full, fullRoot, addedNodes, attributeTargets, textTargets);
        invokePlugins(context);
        for (index = 0; index < addedNodes.length; index += 1) {
          collectCandidateSubtree(addedNodes[index], candidates);
        }
        for (index = 0; index < attributeTargets.length; index += 1) {
          if (isInSelectorPack(attributeTargets[index])) {
            candidates.add(attributeTargets[index]);
          }
        }
        if (cleaning) {
          deferredCandidates.forEach(function mergeDeferred(element) {
            if (element.isConnected) {
              candidates.add(element);
            }
          });
          deferredCandidates.clear();
          candidates.forEach(cleanElement);
        } else {
          candidates.forEach(function deferCandidate(element) {
            deferredCandidates.add(element);
          });
        }
        pruneDisconnected();
      } catch (error) {
        reportError(error, "cycle");
      } finally {
        processing = false;
        observeCurrentRoot();
      }
      if (rerun || pendingRecords.length || pendingRoots.length) {
        rerun = false;
        schedule(0);
      }
      return true;
    }

    function schedule(wait) {
      if (!running || destroyed || timer) {
        return api;
      }
      timer = global.setTimeout(function executeScheduledCycle() {
        timer = 0;
        runCycle();
      }, Number.isFinite(wait) ? Math.max(0, wait) : delay);
      return api;
    }

    function onMutations(records) {
      var index;
      if (!running || destroyed) {
        return;
      }
      for (index = 0; index < records.length; index += 1) {
        pendingRecords.push(records[index]);
      }
      schedule(delay);
    }

    function start(root) {
      var nextRoot;
      var wasRunning = running;
      if (destroyed) {
        return api;
      }
      nextRoot = root || documentLocal.body || documentLocal.documentElement;
      if (!nextRoot) {
        return api;
      }
      running = true;
      if (!initialScanDone && !initialRoot) {
        initialRoot = nextRoot;
      } else if (!wasRunning) {
        pendingRoots.push(nextRoot);
      }
      if (observedRoot !== documentLocal.documentElement) {
        observer.disconnect();
        observedRoot = documentLocal.documentElement;
      }
      observeCurrentRoot();
      schedule(0);
      return api;
    }

    function stop() {
      running = false;
      observer.disconnect();
      observer.takeRecords();
      observedRoot = null;
      if (timer) {
        global.clearTimeout(timer);
        timer = 0;
      }
      pendingRecords.length = 0;
      pendingRoots.length = 0;
      return api;
    }

    function setCleaning(enabled) {
      var next = enabled === true;
      if (destroyed || cleaning === next) {
        return api;
      }
      cleaning = next;
      if (!cleaning) {
        restore();
      } else if (running) {
        pendingRoots.push(documentLocal.body || documentLocal.documentElement);
        schedule(0);
      }
      return api;
    }

    function register(idOrPlugin, possiblePlugin) {
      var plugin = possiblePlugin || idOrPlugin;
      var pluginId = typeof idOrPlugin === "string" ? idOrPlugin : plugin && (plugin.id || plugin.meta && plugin.meta.id);
      var key;
      var previous;
      if (destroyed || !plugin || !pluginId) {
        return api;
      }
      key = String(pluginId);
      previous = plugins.get(key);
      if (previous === plugin) {
        return api;
      }
      if (previous) {
        plugins.delete(key);
        teardownPlugin(previous, key);
      }
      plugins.set(key, plugin);
      if (running && !initialScanDone) {
        schedule(0);
      }
      return api;
    }

    function unregister(idOrPlugin) {
      var pluginId = typeof idOrPlugin === "string" ? idOrPlugin : idOrPlugin && (idOrPlugin.id || idOrPlugin.meta && idOrPlugin.meta.id);
      var key;
      var plugin;
      if (!pluginId) {
        return api;
      }
      key = String(pluginId);
      plugin = plugins.get(key);
      if (!plugin || typeof idOrPlugin !== "string" && plugin !== idOrPlugin) {
        return api;
      }
      plugins.delete(key);
      teardownPlugin(plugin, key);
      return api;
    }

    function flush(input) {
      var index;
      if (destroyed || !running) {
        return false;
      }
      if (Array.isArray(input)) {
        for (index = 0; index < input.length; index += 1) {
          pendingRecords.push(input[index]);
        }
      } else if (input && typeof input.nodeType === "number") {
        pendingRoots.push(input);
      }
      return runCycle();
    }

    function destroy() {
      if (destroyed) {
        return;
      }
      destroyed = true;
      stop();
      restore();
      plugins.forEach(function destroyPlugin(plugin, pluginId) {
        teardownPlugin(plugin, pluginId);
      });
      plugins.clear();
      deferredCandidates.clear();
    }

    api = Object.freeze({
      meta: Object.freeze({ owner: OWNER, version: VERSION, id: "zmr-cleanup-instance" }),
      start: start,
      stop: stop,
      setCleaning: setCleaning,
      register: register,
      unregister: unregister,
      flush: flush,
      restore: restore,
      destroy: destroy,
      isRunning: function isRunning() {
        return running;
      },
      isCleaning: function isCleaning() {
        return cleaning;
      },
      getObserver: function getObserver() {
        return observer;
      },
      getSelectorPack: function getSelectorPack() {
        return SELECTOR_PACK;
      },
      getLastError: function getLastError() {
        return lastError;
      },
      getDeltaCount: function getDeltaCount() {
        return deltas.size;
      }
    });
    return api;
  }

  createTavernMmdZmrCleanup.meta = Object.freeze({
    owner: OWNER,
    version: VERSION,
    id: ID,
    selectorPackReviewedAt: SELECTOR_PACK.reviewedAt
  });
  namespace.cleanupFactory = createTavernMmdZmrCleanup;

  global.setTimeout(function retireCleanupInstallerNodes() {
    var selector = "script[data-zmr-owner='" + OWNER + "'][data-zmr-id='" + ID + "']";
    var nodes = documentRef.querySelectorAll(selector);
    var index;
    for (index = 0; index < nodes.length; index += 1) {
      nodes[index].remove();
    }
  }, 0);
})(window);
