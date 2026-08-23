// Upgrades every server-rendered "collected <absolute time>" stamp (elements
// carrying data-collected-at, see facts.collection_freshness) to a live
// relative age ("collected 3 h ago") and flags it stale once the last
// collector run is older than the threshold.
//
// This has to happen client-side: the static site only rebuilds when the
// collector pushes, so a build-time stale flag could never appear exactly in
// the case it exists for - the collector having stopped pushing. The absolute
// timestamp stays as the no-JS fallback and moves into the tooltip.
(function () {
  // The collector CronJob runs nightly (see k8s/04-collector-cronjob.yaml);
  // one missed run plus a little grace means something is actually wrong.
  var STALE_AFTER_MS = 26 * 60 * 60 * 1000;
  var MINUTE = 60 * 1000;
  var HOUR = 60 * MINUTE;
  var DAY = 24 * HOUR;

  function describe(ageMs) {
    if (ageMs < MINUTE) return "just now";
    if (ageMs < HOUR) return Math.floor(ageMs / MINUTE) + " min ago";
    if (ageMs < DAY) return Math.floor(ageMs / HOUR) + " h ago";
    return Math.floor(ageMs / DAY) + " d ago";
  }

  function refresh() {
    document.querySelectorAll("[data-collected-at]").forEach(function (el) {
      var collected = Date.parse(el.getAttribute("data-collected-at"));
      if (isNaN(collected)) return; // keep the server-rendered absolute text
      var age = Date.now() - collected;
      el.textContent = "collected " + describe(age);
      el.title = el.getAttribute("data-collected-at");
      el.classList.toggle("freshness--stale", age > STALE_AFTER_MS);
    });
  }

  refresh();
  setInterval(refresh, MINUTE);
})();
