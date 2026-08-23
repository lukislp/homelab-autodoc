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
// alone, well before Mermaid even loaded).
//
// NOT data-processed either (tried and reverted): that attribute is only set
// by mermaid.run()/startOnLoad, and Material calls mermaid.render() directly,
// so it never appears here - gating on it made every page sit through the
// full poll timeout before wrapping anything (confirmed live). The signal
// that does hold, confirmed live against Material 9.x with the mermaid
// library's CDN load artificially delayed: the raw source host is always the
// superfences-emitted <pre class="mermaid">, and Material's own mermaid
// handler detaches it from the ".mermaid" selector as soon as its bundle
// runs, long before the library has loaded; once mermaid.render() finishes,
// Material swaps in a freshly built non-<pre> host (a <div class="mermaid">
// carrying the closed shadow root). So a ".mermaid" match that is not a
// <pre> IS the finished, laid-out diagram - and a <pre> match is raw source
// that must not be measured yet. data-processed="true" is still accepted as
// an alternative for a hypothetical run()-style integration that renders in
// place into the original element.
//
// Initial zoom is "fit to view" (like a PDF viewer / lightbox): the viewport
// (mermaid-pan-zoom.css) is a fixed-size box spanning the full reading
// column, and the diagram starts scaled and centred so it fills that box,
// instead of sitting at its small natural size in the top-left corner. The
// reset button returns to that fit, not to 1:1.
(function () {
  // Low enough that even a very tall multi-namespace topology can be fitted
  // whole into the viewport-sized box (fit-to-view is clamped to this floor too).
  var MIN_SCALE = 0.05;
  var MAX_SCALE = 20;
  // The initial fit may upscale small diagrams to fill the box, but only up
  // to this factor - beyond it a 3-node diagram turns into poster-sized
  // text. Raise to Infinity for a pure "always fill" behaviour.
  var MAX_FIT_SCALE = 2.5;
  // Secondary sanity check alongside the rendered-host check (belt and
  // suspenders, e.g. against a Mermaid version that renders an
  // empty/near-empty SVG) - not the primary readiness signal, see the
  // top-of-file comment.
  var READY_MIN_PX = 40;
  var ZOOM_STEP = 1.3;
  var WHEEL_ZOOM_STEP = 1.15;

  // Mermaid's SVG (inside the closed shadow root) is "width: 100%;
  // max-width: <natural>px" with a viewBox, so its rendered height follows
  // its rendered width at a fixed aspect ratio - up to the natural width,
  // where the max-width cap kicks in and the height stops growing. Its
  // natural WIDTH can't be read directly (the SVG is unreachable, and
  // host.offsetWidth is just the host's own block width), but the host's
  // height IS observable from outside, so infer the natural size from the
  // aspect ratio: measure the height at a huge host width (SVG at its
  // max-width = natural height, plus any constant line-box gap) and at two
  // widths where the SVG is width-constrained (the difference cancels the
  // gap and gives height-per-pixel-of-width = H/W).
  //
  // The probe widths must NOT be small fixed constants (50px/100px was tried
  // and reverted): compressing a small diagram that far leaves probe heights
  // of ~20px where sub-pixel rounding noise dominates the derived slope, and
  // dividing by that near-zero slope produced natural widths off by 3x or
  // more (confirmed live: a ~900px-wide 3-node diagram measured as ~2800px
  // and rendered tiny inside a huge empty box). Instead anchor the probes to
  // the host's own container width, so they stay in a regime where probe
  // heights are tens-to-hundreds of px and the SVG scales linearly. A
  // diagram narrower than its container is unconstrained at container width
  // (its height there already equals the huge-width height), so for that
  // case halve the probe width until the height clearly drops below the
  // natural height - only then is the probe in the width-constrained,
  // linear regime that the extrapolation needs.
  function heightAt(host, width) {
    host.style.width = width + "px";
    return host.getBoundingClientRect().height;
  }

  function measureNatural(host) {
    var prevWidth = host.style.width;
    // Height with the SVG at its natural (max-width-capped) size: at an
    // absurdly wide host it cannot be width-constrained.
    host.style.width = "100000px";
    var hWide = host.getBoundingClientRect().height;
    // The host's free (unconstrained) box: its width is the container's
    // content width, and its height reveals whether the diagram is
    // width-constrained at that width.
    host.style.width = "";
    var freeRect = host.getBoundingClientRect();
    var freeW = freeRect.width;
    var freeH = freeRect.height;

    var w1;
    var h1;
    var w2;
    var h2;
    if (freeH < hWide - 2 && freeW > 0) {
      // Wider than the container: already constrained at container width,
      // so the free box itself is one probe and half of it the other.
      w2 = freeW;
      h2 = freeH;
      w1 = Math.floor(freeW / 2);
      h1 = heightAt(host, w1);
    } else {
      // Fits inside the container: halve from half the container width down
      // until the height clearly drops below the natural height, i.e. the
      // probe is genuinely constraining the SVG.
      w2 = Math.floor(freeW / 2) || 64;
      h2 = heightAt(host, w2);
      var guard = 0;
      while (h2 > hWide - 2 && w2 > 32 && guard < 6) {
        w2 = Math.floor(w2 / 2);
        h2 = heightAt(host, w2);
        guard += 1;
      }
      w1 = Math.floor(w2 / 2);
      h1 = heightAt(host, w1);
    }
    host.style.width = prevWidth;

    var perPx = (h2 - h1) / (w2 - w1); // = H / W
    var gap = h1 - perPx * w1;
    var height = hWide - gap;
    var width = height / perPx;
    if (!(perPx > 0) || !(height > 0) || !(width > 0) || width > 60000) {
      // Not aspect-ratio-constrained content (e.g. the raw-source <pre> that
      // the timeout fallback may wrap: plain text reflows, it doesn't scale)
      // - fall back to the host's own free box.
      return { width: freeW, height: freeH };
    }
    return { width: width, height: height };
  }

  // Rendered = not the raw-source <pre> (Material swaps in a non-<pre> host
  // once mermaid.render() is done - see the top-of-file comment), OR
  // data-processed for run()-style integrations that render in place.
  function isRendered(host) {
    return host.tagName !== "PRE" || host.getAttribute("data-processed") === "true";
  }

  function wrap(host, skipRenderedCheck) {
    if (host.dataset.panZoomInit === "true") return;
    // skipRenderedCheck is the timeout fallback (see the poll loop below):
    // if no rendered host ever shows up within maxPollMs (e.g. the mermaid
    // library's CDN is unreachable but a raw-source <pre> still matches),
    // fall back to the size-only guess rather than leaving the block without
    // pan/zoom forever - a possibly-mis-sized wrap still beats none.
    if (!skipRenderedCheck && !isRendered(host)) return;
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

  function scan(skipRenderedCheck) {
    document.querySelectorAll(".mermaid").forEach(function (host) {
      wrap(host, skipRenderedCheck);
    });
  }

  // document$ is Material's own reactive navigation hook - fires on every
  // page render, whether from a full page load or instant-navigation. Kept
  // polling (rather than e.g. a MutationObserver) because Mermaid's render
  // can itself be async and slow (mermaid.min.js loads from a CDN, in
  // parallel with everything else on the page) - this simply checks back
  // every 400ms until Material's rendered host shows up, for up to 20s.
  // In the normal case that's one or two ticks, not the full timeout: the
  // rendered host appears as soon as the library has loaded and drawn.
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
