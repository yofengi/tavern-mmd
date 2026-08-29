(function installTavernMmdZmrQuotePluginFactory(global) {
  "use strict";

  var OWNER = "tavern-mmd/zmr";
  var VERSION = "2.0.0";
  var ID = "zmr-quote-plugin-factory";
  var AI_SELECTOR = ".content.left";
  var ORANGE_SELECTOR = "font[color],font[style],[color],[style]";
  var COMPONENT_BOUNDARY_SELECTOR = "[data-zmr-owned],[data-sid],[data-g3v],[data-zsf-ball],[data-zsf-drawer]";
  var SKIP_SELECTOR = "pre,code,kbd,samp,input,textarea,script,style,template,[hidden],[aria-hidden='true'],[inert],[style*='display:none'],[style*='display: none'],[contenteditable]:not([contenteditable='false'])," + COMPONENT_BOUNDARY_SELECTOR;
  var namespace = global[OWNER];
  var documentRef = global.document;

  if (!namespace || typeof namespace !== "object") {
    namespace = {};
    global[OWNER] = namespace;
  }

  function compactColor(value) {
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

  function isMmdOrange(value) {
    var color = compactColor(value);
    return color === "#dc8333" || color === "#dc8333ff" || color === "rgb(220,131,51)" || color === "rgba(220,131,51,1)";
  }

  function createTavernMmdZmrQuotePlugin(options) {
    var settings = options && typeof options === "object" ? options : {};
    var normalizeQuotes = settings.normalizeQuotes === true;
    var destroyed = false;
    var normalizedTextNodes = 0;
    var highlightedElements = 0;
    var api;

    function isElement(node) {
      return !!node && node.nodeType === 1;
    }

    function isInsideAi(node) {
      var element = isElement(node) ? node : node && node.parentElement;
      return !!element && !!element.closest(AI_SELECTOR);
    }

    function isSkipped(node, boundary) {
      var element = isElement(node) ? node : node && node.parentElement;
      var skipped;
      if (!element) {
        return true;
      }
      skipped = element.closest(SKIP_SELECTOR);
      return !!skipped && (!boundary || boundary.contains(skipped));
    }

    function fixTextNode(textNode, boundary) {
      var before;
      var after;
      if (!textNode || textNode.nodeType !== 3 || !textNode.parentElement || isSkipped(textNode, boundary)) {
        return;
      }
      before = textNode.nodeValue || "";
      if (!normalizeQuotes) {
        return;
      }
      after = before.replace(/“([^“”]+)“/g, function closeLeftQuote(match, inner) {
        if (inner.indexOf(String.fromCharCode(10)) !== -1 || inner.indexOf(String.fromCharCode(13)) !== -1) {
          return match;
        }
        return "“" + inner + "”";
      });
      if (after !== before) {
        textNode.nodeValue = after;
        normalizedTextNodes += 1;
      }
    }

    function directlyUsesMmdOrange(element) {
      var colorAttribute;
      var inlineColor;
      if (!isElement(element)) {
        return false;
      }
      colorAttribute = element.getAttribute("color");
      inlineColor = element.style ? element.style.getPropertyValue("color") : "";
      return isMmdOrange(colorAttribute) || isMmdOrange(inlineColor);
    }

    function markOrange(element, boundary) {
      if (!isElement(element) || isSkipped(element, boundary)) {
        return;
      }
      if (!directlyUsesMmdOrange(element)) {
        element.classList.remove("zmr-hdm");
        return;
      }
      if (!element.classList.contains("zmr-hdm")) {
        element.classList.add("zmr-hdm");
        highlightedElements += 1;
      }
    }

    function processRoot(root, aiRoot) {
      var walker;
      var textNode;
      var orangeElements;
      var index;
      if (!isElement(root) || !aiRoot || isSkipped(root, aiRoot)) {
        return;
      }
      if (normalizeQuotes) {
        walker = root.ownerDocument.createTreeWalker(root, global.NodeFilter.SHOW_TEXT);
        textNode = walker.nextNode();
        while (textNode) {
          fixTextNode(textNode, aiRoot);
          textNode = walker.nextNode();
        }
      }
      if (root.matches(ORANGE_SELECTOR)) {
        markOrange(root, aiRoot);
      }
      orangeElements = root.querySelectorAll(ORANGE_SELECTOR);
      for (index = 0; index < orangeElements.length; index += 1) {
        markOrange(orangeElements[index], aiRoot);
      }
    }

    function processAiRoot(aiRoot) {
      if (!isElement(aiRoot) || !aiRoot.matches(AI_SELECTOR)) {
        return;
      }
      processRoot(aiRoot, aiRoot);
    }

    function processAddedNode(node) {
      var element = isElement(node) ? node : node && node.parentElement;
      var aiRoot;
      var nestedRoots;
      var index;
      if (!element) {
        return;
      }
      aiRoot = element.closest(AI_SELECTOR);
      if (aiRoot) {
        if (isElement(node)) {
          processRoot(node, aiRoot);
        } else {
          processTextTarget(node);
        }
        return;
      }
      if (!isElement(node)) {
        return;
      }
      nestedRoots = node.querySelectorAll(AI_SELECTOR);
      for (index = 0; index < nestedRoots.length; index += 1) {
        processAiRoot(nestedRoots[index]);
      }
    }

    function processTextTarget(node) {
      var aiRoot;
      if (!node || node.nodeType !== 3 || !isInsideAi(node)) {
        return;
      }
      aiRoot = node.parentElement.closest(AI_SELECTOR);
      fixTextNode(node, aiRoot);
    }

    function processAttributeTarget(element) {
      var aiRoot;
      if (!isElement(element) || !isInsideAi(element)) {
        return;
      }
      aiRoot = element.closest(AI_SELECTOR);
      markOrange(element, aiRoot);
    }

    function process(context) {
      var roots;
      var index;
      if (destroyed || !context) {
        return;
      }
      roots = context.addedNodes || [];
      for (index = 0; index < roots.length; index += 1) {
        processAddedNode(roots[index]);
      }
      roots = context.textTargets || [];
      for (index = 0; index < roots.length; index += 1) {
        processTextTarget(roots[index]);
      }
      roots = context.attributeTargets || [];
      for (index = 0; index < roots.length; index += 1) {
        processAttributeTarget(roots[index]);
      }
    }

    function destroy() {
      var highlighted = documentRef.querySelectorAll(".zmr-hdm");
      var index;
      for (index = 0; index < highlighted.length; index += 1) {
        highlighted[index].classList.remove("zmr-hdm");
      }
      destroyed = true;
    }

    api = Object.freeze({
      id: "zmr-quote-plugin",
      meta: Object.freeze({ owner: OWNER, version: VERSION, id: "zmr-quote-plugin" }),
      process: process,
      setNormalizeQuotes: function setNormalizeQuotes(enabled) {
        normalizeQuotes = enabled === true;
        return api;
      },
      isNormalizeQuotesEnabled: function isNormalizeQuotesEnabled() {
        return normalizeQuotes;
      },
      destroy: destroy,
      getStats: function getStats() {
        return Object.freeze({
          normalizedTextNodes: normalizedTextNodes,
          highlightedElements: highlightedElements
        });
      }
    });
    return api;
  }

  createTavernMmdZmrQuotePlugin.meta = Object.freeze({ owner: OWNER, version: VERSION, id: ID });
  namespace.quotePluginFactory = createTavernMmdZmrQuotePlugin;

  global.setTimeout(function retireQuoteInstallerNodes() {
    var selector = "script[data-zmr-owner='" + OWNER + "'][data-zmr-id='" + ID + "']";
    var nodes = documentRef.querySelectorAll(selector);
    var index;
    for (index = 0; index < nodes.length; index += 1) {
      nodes[index].remove();
    }
  }, 0);
})(window);
