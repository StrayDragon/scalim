(function () {
  function initMermaid() {
    window.__scalimMermaidInitRuns = (window.__scalimMermaidInitRuns || 0) + 1;

    if (typeof mermaid === "undefined") {
      return;
    }

    mermaid.initialize({ startOnLoad: false });

    // Convert code fences to Mermaid containers.
    var converted = 0;
    var blocks = document.querySelectorAll(
      "pre.language-mermaid, pre.mermaid, pre > code.language-mermaid, pre > code.mermaid",
    );
    for (var i = 0; i < blocks.length; i++) {
      var node = blocks[i];
      var pre = node.tagName === "CODE" ? node.parentElement : node;
      if (!pre || pre.getAttribute("data-processed") === "true" || pre.querySelector("svg")) {
        continue;
      }
      var code = pre.querySelector("code");
      var div = document.createElement("div");
      div.className = "mermaid";
      div.textContent = code ? code.textContent : pre.textContent;
      pre.parentNode.replaceChild(div, pre);
      converted++;
    }

    try {
      var targets = document.querySelectorAll(".mermaid:not([data-processed])");
      if (targets.length > 0) {
        if (typeof mermaid.run === "function") {
          mermaid.run({ nodes: targets });
        } else if (typeof mermaid.init === "function") {
          mermaid.init(undefined, targets);
        }
      }
    } catch (err) {
      // Keep raw content readable as fallback.
    }

    window.__scalimMermaidConverted = converted;
  }

  document.addEventListener("DOMContentLoaded", initMermaid);
  window.addEventListener("load", initMermaid);

  // mkdocs-material navigation (SPA-like) hook (if present).
  var subscribed = false;
  function trySubscribe() {
    if (subscribed) {
      return true;
    }
    if (
      typeof document$ !== "undefined" &&
      document$ &&
      typeof document$.subscribe === "function"
    ) {
      document$.subscribe(initMermaid);
      subscribed = true;
      return true;
    }
    return false;
  }

  if (!trySubscribe()) {
    var attempts = 0;
    var timer = window.setInterval(function () {
      attempts++;
      if (trySubscribe() || attempts > 40) {
        window.clearInterval(timer);
      }
    }, 250);
  }

  // Run at script load time and retry briefly, in case Mermaid (remote) loads slowly.
  var initAttempts = 0;
  function retryInit() {
    initAttempts++;
    initMermaid();
    var pending =
      typeof mermaid === "undefined" ||
      document.querySelectorAll(
        "pre.language-mermaid, pre.mermaid, pre > code.language-mermaid, pre > code.mermaid",
      ).length > 0;
    if (pending && initAttempts < 40) {
      window.setTimeout(retryInit, 250);
    }
  }
  retryInit();
})();
