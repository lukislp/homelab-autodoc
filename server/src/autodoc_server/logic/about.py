"""The static About page - the one page on the site that is written, not
generated. It lives as a Python constant rather than a package-data file so
packaging needs no data-file configuration; site_builder writes it next to
the generated root index (the About card links there, so the page must exist
whenever the index does).
"""

from __future__ import annotations

ABOUT_PAGE = """---
hide:
  - navigation
---

<p class="ns-breadcrumb" markdown>[homelab-autodoc](index.md) · **About**</p>

# About this site

Everything on this site except this page is **generated, not written** - a
living inventory of real Kubernetes clusters that documents itself on every
collector run and never goes stale silently (each cluster card shows when its
data was last collected).

## How it works

1. **Collect** - a small collector runs inside each cluster on a read-only
   ServiceAccount and inventories what is actually running: workloads,
   containers, services, routes, volumes, policies, quotas, nodes, recent
   warning events. It deliberately has **no access to Secrets** - not even
   their names.
2. **Push** - the collector registers itself once via an OAuth device grant
   (approved by a human in the admin UI) and then pushes its structured
   inventory to this server with a per-cluster token.
3. **Generate** - the server renders the inventory into these pages: fact
   tables, Mermaid topology diagrams, best-practice findings, and drift
   changelogs. All of that is **deterministic** - templated straight from the
   inventory, reproducible from the same input.
4. **Summarize** - a language model writes short prose summaries. That is the
   only non-deterministic step, and it is fenced in.

## The hallucination boundary

Every number, name, port, and policy on this site comes straight from the
Kubernetes API. The language model only ever writes the sections explicitly
labeled *AI-generated*, its prompts contain nothing but the collected facts,
and the deterministic tables always render in full alongside - so the prose
can be checked against the facts it summarizes, and a failed or absent LLM
never blocks the documentation.

## Drift

Every push is diffed against the previous inventory. Changes - an image
bump, a scaled deployment, a new service - land in each cluster's changelog
with timestamps, so the documentation also answers *what changed and when*.

---

Source: [github.com/lukislp/homelab-autodoc](https://github.com/lukislp/homelab-autodoc)
"""
