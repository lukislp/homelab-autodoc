// Material renders Mermaid diagrams lazily and asynchronously, and Mermaid's
// own DOM churn while it settles isn't fully predictable - a MutationObserver
// alone can miss the right moment (e.g. if the container gets replaced
// outright rather than filled in place, or content briefly flips through
// intermediate states). So this uses two independent strategies together:
// react to DOM mutations AND poll on a fixed interval - whichever notices
// the rendered SVG first wins, and either alone would be enough on its own.
(function () {
  function tryInit(svg) {
    if (!svg || svg.dataset.panZoomInit === "true") return false;
    // If the library didn't load, leave the diagram as a plain static image
    // at its natural size - never worse than before this feature existed.
    // The height/overflow constraint (mermaid-pan-zoom.css) is only ever
    // added once pan-zoom is confirmed active, for the same reason.
    if (typeof svgPanZoom === "undefined") return false;
    svg.dataset.panZoomInit = "true";
    svg.style.maxWidth = "none";
    svg.style.width = "100%";
    svg.style.height = "100%";
    svgPanZoom(svg, {
      zoomEnabled: true,
      controlIconsEnabled: true,
      fit: true,
      center: true,
      minZoom: 0.2,
      maxZoom: 20,
    });
    var container = svg.closest(".mermaid");
    if (container) container.classList.add("mermaid--panzoom-active");
    return true;
  }

  function scanAll() {
    document.querySelectorAll(".mermaid svg").forEach(tryInit);
  }

  function allDone() {
    var svgs = document.querySelectorAll(".mermaid svg");
    if (svgs.length === 0) return false;
    return Array.prototype.every.call(svgs, function (svg) {
      return svg.dataset.panZoomInit === "true";
    });
  }

  // document$ is Material's own reactive navigation hook - fires on every
  // page render, whether from a full page load or instant-navigation.
  document$.subscribe(function () {
    scanAll();

    var observer = new MutationObserver(scanAll);
    observer.observe(document.body, { childList: true, subtree: true });

    var elapsedMs = 0;
    var pollIntervalMs = 400;
    var maxPollMs = 20000;
    var poll = setInterval(function () {
      elapsedMs += pollIntervalMs;
      scanAll();
      if (allDone() || elapsedMs >= maxPollMs) {
        clearInterval(poll);
        observer.disconnect();
      }
    }, pollIntervalMs);
  });
})();
