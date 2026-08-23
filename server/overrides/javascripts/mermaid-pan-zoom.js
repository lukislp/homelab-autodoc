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
// ride.
//
// Detecting "Mermaid has actually rendered something" without being able to
// query inside the shadow root: NOT by the host's rendered size, even though
// that's tempting (shadow DOM content does affect normal layout from the
// outside, so it's readable). Before Mermaid processes it, the host is a
// <pre> holding the raw, un-rendered diagram source as plain text - and a
// <pre>'s natural width is the length of its longest source line, which
// routinely exceeds any reasonable "looks big enough" threshold on its own.
// Measuring at that point pins the pan/zoom to the wrong natural size
// permanently (confirmed live: a 40px threshold was fooled by source text
// alone, well before Mermaid even loaded). The reliable, encapsulation-safe
// signal instead: Mermaid's own `run()` sets data-processed="true" on each
// element once it has finished rendering into it - that attribute lives on
// the host itself (light DOM), not inside the shadow root, so it's not
// subject to the closed-root restriction at all.
//
// Initial zoom is "fit to view" (like a PDF viewer / lightbox): the viewport
// (mermaid-pan-zoom.css) is a fixed-size box spanning the full reading
// column, and the diagram starts scaled and centred so it fills that box,
// instead of sitting at its small natural size in the top-left corner. The
// reset button returns to that fit, not to 1:1.
(function () {
  // Low enough that even a very tall multi-namespace topology can be fitted
  // whole into an 80vh box (fit-to-view is clamped to this floor too).
  var MIN_SCALE = 0.05;
  var MAX_SCALE = 20;
  // The initial fit may upscale small diagrams to fill the box, but only up
  // to this factor - beyond it a 3-node diagram turns into poster-sized
  // text. Raise to Infinity for a pure "always fill" behaviour.
  var MAX_FIT_SCALE = 2.5;
  // Secondary sanity check alongside data-processed (belt and suspenders,
  // e.g. against a Mermaid version that renders an empty/near-empty SVG) -
  // no longer the primary readiness signal, see the top-of-file comment.
  var READY_MIN_PX = 40;
  var ZOOM_STEP = 1.3;
  var WHEEL_ZOOM_STEP = 1.15;

  // Mermaid's SVG (inside the closed shadow root) is "width: 100%;
  // max-width: <natural>px" with a viewBox, so its rendered height follows
  // its rendered width at a fixed aspect ratio. Its natural WIDTH can't be
  // read directly (the SVG is unreachable, and host.offsetWidth is just the
  // host's own block width - in a shrink-to-fit host a 100%-wide SVG even
  // collapses to the 300px replaced-element fallback). But the host's height
  // IS observable from outside, so infer the natural size from the aspect
  // ratio: measure the height at a huge host width (SVG at its max-width =
  // natural height, plus any constant line-box gap) and at two small widths
  // where the SVG is certainly width-constrained (the difference cancels
  // the gap and gives height-per-pixel-of-width = H/W).
  function measureNatural(host) {
    var prevWidth = host.style.width;
    host.style.width = "100000px";
    var hWide = host.getBoundingClientRect().height;
    host.style.width = "50px";
    var h50 = host.getBoundingClientRect().height;
    host.style.width = "100px";
    var h100 = host.getBoundingClientRect().height;
    host.style.width = prevWidth;
    var perPx = (h100 - h50) / 50; // = H / W
    var gap = h50 - perPx * 50;
    var height = hWide - gap;
    if (!(perPx > 0) || !(height > 0)) {
      // Not aspect-ratio-constrained content (shouldn't happen for a
      // rendered Mermaid SVG) - fall back to the host's own box.
      return { width: host.offsetWidth, height: host.offsetHeight };
    }
    return { width: height / perPx, height: height };
  }

  function wrap(host, skipProcessedCheck) {
    if (host.dataset.panZoomInit === "true") return;
    // skipProcessedCheck is the timeout fallback (see the poll loop below):
    // if Mermaid never sets data-processed within maxPollMs (a Mermaid
    // version that doesn't set it, or it renders under a different
    // attribute), fall back to the old size-only guess rather than leaving
    // the diagram without pan/zoom forever - a possibly-mis-sized wrap still
    // beats none.
    if (!skipProcessedCheck && host.getAttribute("data-processed") !== "true") return;
    if (host.offsetHeight < READY_MIN_PX || host.offsetWidth < READY_MIN_PX) return;
    host.dataset.panZoomInit = "true";

    // Natural (unscaled) rendered size, captured before any transform is
    // applied and before the host is moved into the viewport.
    var natural = measureNatural(host);
    var naturalWidth = natural.width;
    var naturalHeight = natural.height;

    var viewport = document.createElement("div");
    viewport.className = "mermaid-zoom-viewport";
    host.parentNode.insertBefore(viewport, host);
    viewport.appendChild(host);
    host.classList.add("mermaid-zoom-host");
    // Pin the host to the diagram's natural width so the SVG inside lays
    // out at exactly that size (see measureNatural) - from here on only the
    // transform changes what the reader sees.
    host.style.width = naturalWidth + "px";

    var controls = document.createElement("div");
    controls.className = "mermaid-zoom-controls";
    controls.innerHTML =
      '<button type="button" data-zoom="in" title="Zoom in" aria-label="Zoom in">+</button>' +
      '<button type="button" data-zoom="out" title="Zoom out" aria-label="Zoom out">−</button>' +
      '<button type="button" data-zoom="reset" title="Fit to view" aria-label="Fit to view">↺</button>';
    viewport.appendChild(controls);

    var scale = 1;
    var panX = 0;
    var panY = 0;
    var userAdjusted = false;
    var dragging = false;
    var startX = 0;
    var startY = 0;
    var startPanX = 0;
    var startPanY = 0;

    function apply() {
      host.style.transform = "translate(" + panX + "px, " + panY + "px) scale(" + scale + ")";
    }

    // Scale the diagram so it fills the viewport's content area (everything
    // except the padding-bottom strip reserved for the controls), preserving
    // aspect ratio, and centre it. Runs on init, on reset, and on window
    // resize while the user hasn't panned/zoomed away from the fit - so the
    // fit tracks the column width on responsive layouts.
    function fitToView() {
      var cs = getComputedStyle(viewport);
      var padL = parseFloat(cs.paddingLeft) || 0;
      var padT = parseFloat(cs.paddingTop) || 0;
      var availW = viewport.clientWidth - padL - (parseFloat(cs.paddingRight) || 0);
      var availH = viewport.clientHeight - padT - (parseFloat(cs.paddingBottom) || 0);
      if (availW <= 0 || availH <= 0 || naturalWidth <= 0 || naturalHeight <= 0) {
        scale = 1;
        panX = 0;
        panY = 0;
      } else {
        scale = Math.min(availW / naturalWidth, availH / naturalHeight, MAX_FIT_SCALE);
        scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
        panX = padL + (availW - naturalWidth * scale) / 2;
        panY = padT + (availH - naturalHeight * scale) / 2;
      }
      apply();
    }

    function zoomBy(factor, clientX, clientY) {
      var next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
      var originX;
      var originY;
      if (clientX !== undefined) {
        // Keep the point under the cursor stationary while zooming, instead
        // of always zooming toward the top-left corner.
        var rect = viewport.getBoundingClientRect();
        originX = clientX - rect.left;
        originY = clientY - rect.top;
      } else {
        // Button zoom: zoom about the centre of the viewport, so a centred
        // (fitted) diagram stays centred.
        originX = viewport.clientWidth / 2;
        originY = viewport.clientHeight / 2;
      }
      panX = originX - ((originX - panX) / scale) * next;
      panY = originY - ((originY - panY) / scale) * next;
      scale = next;
      userAdjusted = true;
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
      userAdjusted = true;
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
        userAdjusted = false;
        fitToView();
      }
    });

    // MkDocs Material's document$ navigation replaces page content without a
    // full reload, so a listener added here would otherwise never be
    // cleaned up and pile up across every page visited in one session -
    // self-unregister once this diagram's viewport has left the document.
    window.addEventListener("resize", function onResize() {
      if (!document.contains(viewport)) {
        window.removeEventListener("resize", onResize);
        return;
      }
      if (!userAdjusted) fitToView();
    });

    fitToView();
  }

  function scan(skipProcessedCheck) {
    document.querySelectorAll(".mermaid").forEach(function (host) {
      wrap(host, skipProcessedCheck);
    });
  }

  // document$ is Material's own reactive navigation hook - fires on every
  // page render, whether from a full page load or instant-navigation. Kept
  // polling (rather than e.g. a MutationObserver) because Mermaid's render
  // can itself be async and slow (mermaid.min.js loads from a CDN, in
  // parallel with everything else on the page) - this simply checks back
  // every 400ms until data-processed shows up, for up to 20s.
  document$.subscribe(function () {
    scan();
    var elapsedMs = 0;
    var pollIntervalMs = 400;
    var maxPollMs = 20000;
    var poll = setInterval(function () {
      elapsedMs += pollIntervalMs;
      var timedOut = elapsedMs >= maxPollMs;
      scan(timedOut);
      if (timedOut) clearInterval(poll);
    }, pollIntervalMs);
  });
})();
