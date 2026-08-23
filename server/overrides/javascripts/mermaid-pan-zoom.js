// Material for MkDocs renders each ".mermaid" block's diagram into a CLOSED
// shadow root attached to the host element - by design, that content is
// completely unreachable from any code outside Material's own bundle:
// querySelectorAll(".mermaid svg") never matches, a MutationObserver on
// document.body never sees the insertion, and host.attachShadow() itself
// throws NotSupportedError once Material has already attached its own
// closed root. A library like svg-pan-zoom (which needs a direct <svg>
// reference) fundamentally cannot be used here - confirmed live.
//
// So this doesn't reach inside at all: it treats the whole ".mermaid" host
// as an opaque box and pans/zooms IT via a CSS transform, the same way you'd
// zoom a photo - the shadow DOM content inside just comes along for the
// ride. Detecting "Mermaid has actually rendered something" without being
// able to query inside the shadow root: poll the host's own rendered height
// instead (shadow DOM content still affects normal layout from the outside,
// it's just not queryable) - once it grows past a trivial threshold, wrap it.
(function () {
  var MIN_SCALE = 0.2;
  var MAX_SCALE = 20;
  var READY_HEIGHT_PX = 20;
  var ZOOM_STEP = 1.3;
  var WHEEL_ZOOM_STEP = 1.15;

  function wrap(host) {
    if (host.dataset.panZoomInit === "true") return;
    if (host.offsetHeight < READY_HEIGHT_PX) return;
    host.dataset.panZoomInit = "true";

    var viewport = document.createElement("div");
    viewport.className = "mermaid-zoom-viewport";
    host.parentNode.insertBefore(viewport, host);
    viewport.appendChild(host);
    host.classList.add("mermaid-zoom-host");

    var controls = document.createElement("div");
    controls.className = "mermaid-zoom-controls";
    controls.innerHTML =
      '<button type="button" data-zoom="in" title="Zoom in" aria-label="Zoom in">+</button>' +
      '<button type="button" data-zoom="out" title="Zoom out" aria-label="Zoom out">−</button>' +
      '<button type="button" data-zoom="reset" title="Reset zoom" aria-label="Reset zoom">↺</button>';
    viewport.appendChild(controls);

    var scale = 1;
    var panX = 0;
    var panY = 0;
    var dragging = false;
    var startX = 0;
    var startY = 0;
    var startPanX = 0;
    var startPanY = 0;

    function apply() {
      host.style.transform = "translate(" + panX + "px, " + panY + "px) scale(" + scale + ")";
    }

    function zoomBy(factor, clientX, clientY) {
      var next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
      if (clientX !== undefined) {
        // Keep the point under the cursor stationary while zooming, instead
        // of always zooming toward the top-left corner.
        var rect = viewport.getBoundingClientRect();
        var originX = clientX - rect.left;
        var originY = clientY - rect.top;
        panX = originX - ((originX - panX) / scale) * next;
        panY = originY - ((originY - panY) / scale) * next;
      }
      scale = next;
      apply();
    }

    viewport.addEventListener(
      "wheel",
      function (e) {
        e.preventDefault();
        zoomBy(e.deltaY < 0 ? WHEEL_ZOOM_STEP : 1 / WHEEL_ZOOM_STEP, e.clientX, e.clientY);
      },
      { passive: false }
    );

    viewport.addEventListener("mousedown", function (e) {
      if (e.target.closest(".mermaid-zoom-controls")) return;
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      startPanX = panX;
      startPanY = panY;
      viewport.classList.add("mermaid-zoom-dragging");
    });
    window.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      panX = startPanX + (e.clientX - startX);
      panY = startPanY + (e.clientY - startY);
      apply();
    });
    window.addEventListener("mouseup", function () {
      dragging = false;
      viewport.classList.remove("mermaid-zoom-dragging");
    });

    controls.addEventListener("click", function (e) {
      var action = e.target.dataset.zoom;
      if (!action) return;
      if (action === "in") zoomBy(ZOOM_STEP);
      else if (action === "out") zoomBy(1 / ZOOM_STEP);
      else if (action === "reset") {
        scale = 1;
        panX = 0;
        panY = 0;
        apply();
      }
    });

    apply();
  }

  function scan() {
    document.querySelectorAll(".mermaid").forEach(wrap);
  }

  // document$ is Material's own reactive navigation hook - fires on every
  // page render, whether from a full page load or instant-navigation.
  document$.subscribe(function () {
    scan();
    var elapsedMs = 0;
    var pollIntervalMs = 400;
    var maxPollMs = 20000;
    var poll = setInterval(function () {
      elapsedMs += pollIntervalMs;
      scan();
      if (elapsedMs >= maxPollMs) clearInterval(poll);
    }, pollIntervalMs);
  });
})();
