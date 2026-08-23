// Reloads the page when a new site build lands on the server, so open doc
// pages never go stale after a collector push or a cluster delete - no manual
// refresh needed. The build stamp comes from /api/site/version, served by the
// same FastAPI process that serves this static site.
//
// The first successful poll only records the baseline (the page just loaded,
// it IS the current build); every later change triggers one reload, which
// resets the baseline again. Hidden tabs skip polling, but a visibilitychange
// check catches up the moment the tab is foregrounded. Fetch errors are
// swallowed: the server being briefly away (a rollout) must not spam the
// console - the next tick retries.
(function () {
  var POLL_MS = 10000;
  var known = null;

  function check() {
    if (document.visibilityState === "hidden") return;
    fetch("/api/site/version", { cache: "no-store" })
      .then(function (res) {
        return res.ok ? res.json() : null;
      })
      .then(function (body) {
        if (!body || !body.version || body.version === "0") return;
        if (known === null) {
          known = body.version;
        } else if (body.version !== known) {
          window.location.reload();
        }
      })
      .catch(function () {
        /* server briefly away (rollout) - retry on the next tick */
      });
  }

  check();
  setInterval(check, POLL_MS);
  document.addEventListener("visibilitychange", check);
})();
