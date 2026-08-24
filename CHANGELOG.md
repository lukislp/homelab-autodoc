# [1.43.0](https://github.com/lukislp/homelab-autodoc/compare/v1.42.4...v1.43.0) (2026-08-24)


### Features

* **findings:** collapse privileged containers into one explicit finding ([71add6c](https://github.com/lukislp/homelab-autodoc/commit/71add6c815eb866109ba0a392eacdbbb3721b5d9))

## [1.42.4](https://github.com/lukislp/homelab-autodoc/compare/v1.42.3...v1.42.4) (2026-08-24)


### Bug Fixes

* **generator:** cnpg-default-monitoring is never an orphaned ConfigMap ([31a1dd2](https://github.com/lukislp/homelab-autodoc/commit/31a1dd2e3db64e89bb39fa49cfe9f80fbf6c1803))

## [1.42.3](https://github.com/lukislp/homelab-autodoc/compare/v1.42.2...v1.42.3) (2026-08-24)


### Bug Fixes

* **k8s:** bump the collector image to the non-root 1.42.2 ([67d74dc](https://github.com/lukislp/homelab-autodoc/commit/67d74dca79d1cad7b71b5b20f7e33708884a7679))

## [1.42.2](https://github.com/lukislp/homelab-autodoc/compare/v1.42.1...v1.42.2) (2026-08-24)


### Bug Fixes

* run server and collector as non-root ([a3c1756](https://github.com/lukislp/homelab-autodoc/commit/a3c1756090ab0d1dcb99278e3586731a53514085))

## [1.42.1](https://github.com/lukislp/homelab-autodoc/compare/v1.42.0...v1.42.1) (2026-08-24)


### Bug Fixes

* **generator:** probe and PDB rules respect the workload kind ([8bb4215](https://github.com/lukislp/homelab-autodoc/commit/8bb42156d713841f0c6342bba8f74a3381fced34))

# [1.42.0](https://github.com/lukislp/homelab-autodoc/compare/v1.41.8...v1.42.0) (2026-08-23)


### Features

* **server:** touch gestures for diagram pan/zoom ([3a87b08](https://github.com/lukislp/homelab-autodoc/commit/3a87b080fd6bfa4389d6031c36522acfe41b6b08))

## [1.41.8](https://github.com/lukislp/homelab-autodoc/compare/v1.41.7...v1.41.8) (2026-08-23)


### Bug Fixes

* **server:** lower the topology box's min-height floor to 360px ([ea3b7d7](https://github.com/lukislp/homelab-autodoc/commit/ea3b7d7420ea6e177c8af487e8d32d914cb0bc2e))

## [1.41.7](https://github.com/lukislp/homelab-autodoc/compare/v1.41.6...v1.41.7) (2026-08-23)


### Bug Fixes

* **server:** absorb the cluster topology's last 16px of overflow ([67b35b1](https://github.com/lukislp/homelab-autodoc/commit/67b35b12168e373aff9d11bb3da074d7f147bdef))

## [1.41.6](https://github.com/lukislp/homelab-autodoc/compare/v1.41.5...v1.41.6) (2026-08-23)


### Bug Fixes

* **server:** chip navigation above cluster content, no H1 on cluster topology ([b55bfb1](https://github.com/lukislp/homelab-autodoc/commit/b55bfb166859f926285fade75b7bb009fcf47cbc))

## [1.41.5](https://github.com/lukislp/homelab-autodoc/compare/v1.41.4...v1.41.5) (2026-08-23)


### Bug Fixes

* **server:** pin the breadcrumb while the content scrolls ([7a107bd](https://github.com/lukislp/homelab-autodoc/commit/7a107bddbbe30d4a470e50a2806fe0a90f8394d1))

## [1.41.4](https://github.com/lukislp/homelab-autodoc/compare/v1.41.3...v1.41.4) (2026-08-23)


### Bug Fixes

* **server:** hide the Material footer ([857c6b3](https://github.com/lukislp/homelab-autodoc/commit/857c6b3127c189162e9fa2799d1f4b8926db82d4))

## [1.41.3](https://github.com/lukislp/homelab-autodoc/compare/v1.41.2...v1.41.3) (2026-08-23)


### Bug Fixes

* cut a release for the pinned-sidebars layout round ([04ada95](https://github.com/lukislp/homelab-autodoc/commit/04ada959fd735987bccdb1459a39a880211bb979)), closes [#70](https://github.com/lukislp/homelab-autodoc/issues/70) [#69](https://github.com/lukislp/homelab-autodoc/issues/69)
* **server:** keep sidebars pinned and fit topology pages to one viewport ([6493533](https://github.com/lukislp/homelab-autodoc/commit/6493533c56958efa99c1b6b5b85ec44068459fc2))

## [1.41.2](https://github.com/lukislp/homelab-autodoc/compare/v1.41.1...v1.41.2) (2026-08-23)


### Bug Fixes

* **server:** empty-state texts say none exist, not 'not collected yet' ([8d421ac](https://github.com/lukislp/homelab-autodoc/commit/8d421ac38b8ec946db151d502e3e0066fabc8e97))

## [1.41.1](https://github.com/lukislp/homelab-autodoc/compare/v1.41.0...v1.41.1) (2026-08-23)


### Bug Fixes

* **k8s:** bump the collector image to 1.41.0 ([f171f2f](https://github.com/lukislp/homelab-autodoc/commit/f171f2f995e5b82cc03f09719d2c5fcaf31317fd))

# [1.41.0](https://github.com/lukislp/homelab-autodoc/compare/v1.40.0...v1.41.0) (2026-08-23)


### Features

* **generator:** GitOps provenance badge on app pages ([850c69d](https://github.com/lukislp/homelab-autodoc/commit/850c69dafae7b03b10d490f63c86d40f2df987a8))

# [1.40.0](https://github.com/lukislp/homelab-autodoc/compare/v1.39.0...v1.40.0) (2026-08-23)


### Features

* **collector:** per-namespace Recent Warnings from cluster events ([46e26d9](https://github.com/lukislp/homelab-autodoc/commit/46e26d9c19bffc9527136597913735bf7d7b8831))
* **server:** About page explaining the pipeline ([19a6d67](https://github.com/lukislp/homelab-autodoc/commit/19a6d6718ff96ac9af8df8f47afd91ed96416a62))

# [1.39.0](https://github.com/lukislp/homelab-autodoc/compare/v1.38.0...v1.39.0) (2026-08-23)


### Features

* **server:** fleet stats on the root-index cluster cards ([125fe3b](https://github.com/lukislp/homelab-autodoc/commit/125fe3bc0b8494aeba8dd5d5d7524bb8663990ef))

# [1.38.0](https://github.com/lukislp/homelab-autodoc/compare/v1.37.0...v1.38.0) (2026-08-23)


### Features

* **server:** AI-generated drift summary on the changelog page ([1e68514](https://github.com/lukislp/homelab-autodoc/commit/1e685145ac2a4f7027d58bac04a3615669e42e46))

# [1.37.0](https://github.com/lukislp/homelab-autodoc/compare/v1.36.0...v1.37.0) (2026-08-23)


### Bug Fixes

* **generator:** sort the findings test imports ([02df756](https://github.com/lukislp/homelab-autodoc/commit/02df7560a0ae4b7d73a71c393aa7b8a3748ab9e4))


### Features

* **collector:** flag dangling and orphaned ConfigMap references ([68af6db](https://github.com/lukislp/homelab-autodoc/commit/68af6dbc93f3f460b9d9112e3d0161ffc335f0d0))

# [1.36.0](https://github.com/lukislp/homelab-autodoc/compare/v1.35.0...v1.36.0) (2026-08-23)


### Features

* **server:** cluster-wide images page ([4016a38](https://github.com/lukislp/homelab-autodoc/commit/4016a38583cae9f3c4bbf5d68fcd0dc2107438b3))

# [1.35.0](https://github.com/lukislp/homelab-autodoc/compare/v1.34.0...v1.35.0) (2026-08-23)


### Bug Fixes

* **repo:** ignore the server's generated docs_src tree ([f2829db](https://github.com/lukislp/homelab-autodoc/commit/f2829db40bdf259add2800b37380b1e63a5b65a8))


### Features

* **server:** live collection-freshness stamp on cluster cards ([ef29982](https://github.com/lukislp/homelab-autodoc/commit/ef29982b8c5c0eca760a3022d351c88f674fa004))

# [1.34.0](https://github.com/lukislp/homelab-autodoc/compare/v1.33.1...v1.34.0) (2026-08-23)


### Features

* **generator:** deterministic best-practice findings ([8e1181f](https://github.com/lukislp/homelab-autodoc/commit/8e1181fa318732bb293a45c463cc34daad6edae8))

## [1.33.1](https://github.com/lukislp/homelab-autodoc/compare/v1.33.0...v1.33.1) (2026-08-23)


### Bug Fixes

* **server:** stop wide app-page tables sliding under the ToC ([1121837](https://github.com/lukislp/homelab-autodoc/commit/11218373ff8250103bdb4ef5f615a3ef81eace65))

# [1.33.0](https://github.com/lukislp/homelab-autodoc/compare/v1.32.1...v1.33.0) (2026-08-23)


### Bug Fixes

* **k8s:** zero-downtime rollouts via RollingUpdate and a startupProbe ([51c87d9](https://github.com/lukislp/homelab-autodoc/commit/51c87d9b8145857844c0bfd93bae0083e7fbe4b0))


### Features

* **admin-ui:** live-updating lists and a GitHub logo on the login button ([47b21cb](https://github.com/lukislp/homelab-autodoc/commit/47b21cb4ad2570740db56a55ebce0dd78a6c4844))
* **server:** auto-refresh open doc pages when a new build lands ([200c28c](https://github.com/lukislp/homelab-autodoc/commit/200c28cccf6934abdfcc9197a5a63c155eadbfa0))

## [1.32.1](https://github.com/lukislp/homelab-autodoc/compare/v1.32.0...v1.32.1) (2026-08-23)


### Bug Fixes

* **admin-ui:** full-screen management view and provider-labeled login ([1950e9c](https://github.com/lukislp/homelab-autodoc/commit/1950e9ca6d76af4c22151872b8eec5b6ee69316a))
* **server:** rebuild only the root index after a cluster delete ([b44f5a8](https://github.com/lukislp/homelab-autodoc/commit/b44f5a8aa748449ceb9a2dcb6c866233ce503be0))

# [1.32.0](https://github.com/lukislp/homelab-autodoc/compare/v1.31.1...v1.32.0) (2026-08-23)


### Features

* **server:** let an admin delete a registered cluster ([69f9c60](https://github.com/lukislp/homelab-autodoc/commit/69f9c603f74ecae80747840b0f768fedfdfff693))

## [1.31.1](https://github.com/lukislp/homelab-autodoc/compare/v1.31.0...v1.31.1) (2026-08-23)


### Bug Fixes

* **docs:** stop mis-sizing small Mermaid diagrams and drop the 20s wrap delay ([edbd41e](https://github.com/lukislp/homelab-autodoc/commit/edbd41e3d5d41753f8cceb605286f8a2e2218c03))

# [1.31.0](https://github.com/lukislp/homelab-autodoc/compare/v1.30.1...v1.31.0) (2026-08-23)


### Features

* **docs:** replace the global nav tree with hub cards and a scoped sidebar ([3f44e52](https://github.com/lukislp/homelab-autodoc/commit/3f44e522ffea3083f4d4db303c68f2c28476193d))

## [1.30.1](https://github.com/lukislp/homelab-autodoc/compare/v1.30.0...v1.30.1) (2026-08-23)


### Bug Fixes

* **collector:** read exec probe action via the client's actual attribute name ([45ff4ce](https://github.com/lukislp/homelab-autodoc/commit/45ff4ceb91102753a0e525f7d7c9737e27fa1fcb))

# [1.30.0](https://github.com/lukislp/homelab-autodoc/compare/v1.29.0...v1.30.0) (2026-08-23)


### Features

* **namespace:** document ResourceQuota and LimitRange objects per namespace ([8f463e9](https://github.com/lukislp/homelab-autodoc/commit/8f463e9cfe38e4414781cc5141c5374864d5b5d1))

# [1.29.0](https://github.com/lukislp/homelab-autodoc/compare/v1.28.0...v1.29.0) (2026-08-23)


### Features

* **collector:** document each container's effective security context ([2629c8a](https://github.com/lukislp/homelab-autodoc/commit/2629c8a49905967ecb0354847542f7a2aa6b831d))

# [1.28.0](https://github.com/lukislp/homelab-autodoc/compare/v1.27.0...v1.28.0) (2026-08-23)


### Features

* **collector:** document each container's image registry and pull secrets ([479feaf](https://github.com/lukislp/homelab-autodoc/commit/479feaf94efe3779810cbcbb32bd14daaf5db256))

# [1.27.0](https://github.com/lukislp/homelab-autodoc/compare/v1.26.0...v1.27.0) (2026-08-23)


### Features

* **collector:** document each app's rollout strategy ([9a623c2](https://github.com/lukislp/homelab-autodoc/commit/9a623c28aaa781956a1a6e3839e7a4c04638fd3d))

# [1.26.0](https://github.com/lukislp/homelab-autodoc/compare/v1.25.0...v1.26.0) (2026-08-23)


### Features

* add a per-cluster StorageClasses page ([c602eff](https://github.com/lukislp/homelab-autodoc/commit/c602eff454a35f6586065a938ad9a075db4abc4a))
* add a per-namespace ConfigMap/Secret usage page ([96b880a](https://github.com/lukislp/homelab-autodoc/commit/96b880aa3d017fe50343601565f79473915402b4))

# [1.25.0](https://github.com/lukislp/homelab-autodoc/compare/v1.24.0...v1.25.0) (2026-08-23)


### Features

* **collector:** document node affinity, node selector, and tolerations ([39ecd29](https://github.com/lukislp/homelab-autodoc/commit/39ecd295c2936246eefe7cf62048e17455ef76a0))

# [1.24.0](https://github.com/lukislp/homelab-autodoc/compare/v1.23.0...v1.24.0) (2026-08-23)


### Features

* **collector:** document init containers and liveness/readiness/startup probes ([1765214](https://github.com/lukislp/homelab-autodoc/commit/176521435fa14ceadb0803e376a3e82f1c016604))

# [1.23.0](https://github.com/lukislp/homelab-autodoc/compare/v1.22.0...v1.23.0) (2026-08-23)


### Features

* **collector:** document each app's ServiceAccount and its RBAC bindings ([be4b45e](https://github.com/lukislp/homelab-autodoc/commit/be4b45e2f7dfb5f5879b1f4d1ed94158f0e9099e))

# [1.22.0](https://github.com/lukislp/homelab-autodoc/compare/v1.21.0...v1.22.0) (2026-08-23)


### Features

* **collector:** document PodDisruptionBudgets that apply to each app ([8664969](https://github.com/lukislp/homelab-autodoc/commit/8664969d3272e5ec6756eececf8689b537dc5792))

# [1.21.0](https://github.com/lukislp/homelab-autodoc/compare/v1.20.1...v1.21.0) (2026-08-23)


### Bug Fixes

* **k8s:** bump pinned collector image from 1.14.1 to 1.20.0 ([93d000c](https://github.com/lukislp/homelab-autodoc/commit/93d000c53b111b6b6bbcfb649c8c7c8b1e80e49f))


### Features

* add a per-cluster Nodes page with node capacity/spec ([f1143e5](https://github.com/lukislp/homelab-autodoc/commit/f1143e5a989b1df3272d51e8c9b6e5cc1a4caa93))

## [1.20.1](https://github.com/lukislp/homelab-autodoc/compare/v1.20.0...v1.20.1) (2026-08-23)


### Bug Fixes

* **server:** scale mermaid diagrams to fill their viewport, not shrink it to fit them ([b2183ff](https://github.com/lukislp/homelab-autodoc/commit/b2183ff1cda502e8288b87821590d737a051ad72)), closes [#34](https://github.com/lukislp/homelab-autodoc/issues/34)

# [1.20.0](https://github.com/lukislp/homelab-autodoc/compare/v1.19.0...v1.20.0) (2026-08-23)


### Bug Fixes

* **ci:** retrigger release skipped by a semantic-release race ([2edfe34](https://github.com/lukislp/homelab-autodoc/commit/2edfe340d8ce74a895bee19e656d66196fe30397)), closes [#36](https://github.com/lukislp/homelab-autodoc/issues/36)


### Features

* **collector:** document which NetworkPolicy rules apply to each app ([e3c1065](https://github.com/lukislp/homelab-autodoc/commit/e3c10653480e015911a270614eaf9cc5b64a601b))

# [1.19.0](https://github.com/lukislp/homelab-autodoc/compare/v1.18.1...v1.19.0) (2026-08-23)


### Features

* **collector:** document which node(s) an app's pods run on ([0a87a3f](https://github.com/lukislp/homelab-autodoc/commit/0a87a3fd5fd3cddd4931ed59089d2b2f66a2e236))

## [1.18.1](https://github.com/lukislp/homelab-autodoc/compare/v1.18.0...v1.18.1) (2026-08-23)


### Bug Fixes

* **server:** stop mermaid diagrams rendering into an oversized empty box ([e4a3fcb](https://github.com/lukislp/homelab-autodoc/commit/e4a3fcbb56ba29bb4f9f2783ea0cdc0e3cba3c96))

# [1.18.0](https://github.com/lukislp/homelab-autodoc/compare/v1.17.0...v1.18.0) (2026-08-23)


### Features

* **collector:** document HorizontalPodAutoscaler configuration per app ([2a419f0](https://github.com/lukislp/homelab-autodoc/commit/2a419f03c17df0f115184b60ac390d0b58229de1))

# [1.17.0](https://github.com/lukislp/homelab-autodoc/compare/v1.16.1...v1.17.0) (2026-08-23)


### Features

* **collector:** collect HTTPRoute (Gateway API), not just classic Ingress ([945d737](https://github.com/lukislp/homelab-autodoc/commit/945d7371a644cdd027e2d94e8ffdd2f400fc86b0))

## [1.16.1](https://github.com/lukislp/homelab-autodoc/compare/v1.16.0...v1.16.1) (2026-08-23)


### Bug Fixes

* **docs:** rewrite Mermaid pan-zoom to work around Material's closed shadow DOM ([5f76f8f](https://github.com/lukislp/homelab-autodoc/commit/5f76f8f3e3e0c624a05c2ee5a3845f5e42c98990))

# [1.16.0](https://github.com/lukislp/homelab-autodoc/compare/v1.15.2...v1.16.0) (2026-08-23)


### Features

* **collector:** collect DaemonSet and CronJob workloads ([d081f16](https://github.com/lukislp/homelab-autodoc/commit/d081f16ece1143d72708fac7ecaf8733e465c588))

## [1.15.2](https://github.com/lukislp/homelab-autodoc/compare/v1.15.1...v1.15.2) (2026-08-23)


### Bug Fixes

* **docs:** cache-bust the vendored pan-zoom/sidebar JS and CSS assets ([1576927](https://github.com/lukislp/homelab-autodoc/commit/1576927397ca0f09ecfa5db2d4464ac445238546)), closes [#27](https://github.com/lukislp/homelab-autodoc/issues/27) [#27](https://github.com/lukislp/homelab-autodoc/issues/27) [#28](https://github.com/lukislp/homelab-autodoc/issues/28)

## [1.15.1](https://github.com/lukislp/homelab-autodoc/compare/v1.15.0...v1.15.1) (2026-08-23)


### Bug Fixes

* **docs:** explicitly bound the sidebar nav to its own scroll area ([a8d3a8f](https://github.com/lukislp/homelab-autodoc/commit/a8d3a8fbd2a8f74599b12f59cc4f4b035fb91a33))

# [1.15.0](https://github.com/lukislp/homelab-autodoc/compare/v1.14.3...v1.15.0) (2026-08-22)


### Features

* **docs:** zoomable/pannable Mermaid diagrams ([22dce0e](https://github.com/lukislp/homelab-autodoc/commit/22dce0e3349ac3eb7d84997e865be69d6d0d81d5))

## [1.14.3](https://github.com/lukislp/homelab-autodoc/compare/v1.14.2...v1.14.3) (2026-08-22)


### Bug Fixes

* retrigger release after semantic-release race dropped [#23](https://github.com/lukislp/homelab-autodoc/issues/23)'s version ([18ea2db](https://github.com/lukislp/homelab-autodoc/commit/18ea2db7b047b1c37aac49c817cda6b383294dc6))

## [1.14.2](https://github.com/lukislp/homelab-autodoc/compare/v1.14.1...v1.14.2) (2026-08-22)


### Bug Fixes

* **docs:** sidebar nav overflow + human-readable timestamps ([0b11a6e](https://github.com/lukislp/homelab-autodoc/commit/0b11a6e26ea569fcbf475923f007c2f5d22e69b0))

## [1.14.1](https://github.com/lukislp/homelab-autodoc/compare/v1.14.0...v1.14.1) (2026-08-22)


### Bug Fixes

* **collector:** raise push timeout from 30s to 300s ([d75cbea](https://github.com/lukislp/homelab-autodoc/commit/d75cbea164943241990fbc687b24b98dd59c4b83))

# [1.14.0](https://github.com/lukislp/homelab-autodoc/compare/v1.13.0...v1.14.0) (2026-08-22)


### Features

* **generator,server:** cluster-wide and per-namespace topology diagrams ([7ebfee1](https://github.com/lukislp/homelab-autodoc/commit/7ebfee140c1f3245981bfb5c77f4954e556b57fa))

# [1.13.0](https://github.com/lukislp/homelab-autodoc/compare/v1.12.0...v1.13.0) (2026-08-22)


### Features

* **generator:** resources/env/dependencies/metadata fact tables ([8b19af0](https://github.com/lukislp/homelab-autodoc/commit/8b19af0b6b16ecdc33f92f4317b3079b3efbd333))

# [1.12.0](https://github.com/lukislp/homelab-autodoc/compare/v1.11.0...v1.12.0) (2026-08-22)


### Features

* **core,collector:** collect resource specs, env vars, config refs, metadata ([b986421](https://github.com/lukislp/homelab-autodoc/commit/b98642113aa95618ca0f1fa4143d15bb425dcce3))

# [1.11.0](https://github.com/lukislp/homelab-autodoc/compare/v1.10.1...v1.11.0) (2026-08-22)


### Features

* **docs:** dark mode + hub landing page ([2be1caa](https://github.com/lukislp/homelab-autodoc/commit/2be1caa14d2e7dca1e6f4645e8a113ac3fd8463c))

## [1.10.1](https://github.com/lukislp/homelab-autodoc/compare/v1.10.0...v1.10.1) (2026-08-22)


### Bug Fixes

* **llm:** reasoning_effort=minimal crashed server startup, use medium ([2947bdd](https://github.com/lukislp/homelab-autodoc/commit/2947bdd5a1ad14470a33ce126138b9755daf12d3))

# [1.10.0](https://github.com/lukislp/homelab-autodoc/compare/v1.9.1...v1.10.0) (2026-08-22)


### Features

* wire up OpenAI (gpt-5.6-luna) for the LLM prose summary ([5876c3b](https://github.com/lukislp/homelab-autodoc/commit/5876c3b8efc54cff43bae4ccfc5c1235fd0f450f))

## [1.9.1](https://github.com/lukislp/homelab-autodoc/compare/v1.9.0...v1.9.1) (2026-08-22)


### Bug Fixes

* **server:** rebuild site from persisted inventory on startup ([837cc45](https://github.com/lukislp/homelab-autodoc/commit/837cc45ced8dd057b27fa1a490c5b14cf48627b7))

# [1.9.0](https://github.com/lukislp/homelab-autodoc/compare/v1.8.0...v1.9.0) (2026-08-22)


### Features

* **s4:** drift detection - diff inventories, persist changelog, render page ([3fafa8b](https://github.com/lukislp/homelab-autodoc/commit/3fafa8b37c0f99b27db4c6d56d753d3723b46d44))

# [1.8.0](https://github.com/lukislp/homelab-autodoc/compare/v1.7.3...v1.8.0) (2026-08-22)


### Features

* **k8s:** onboard into homelab-infra's decentralized Flux GitOps pattern ([72572b8](https://github.com/lukislp/homelab-autodoc/commit/72572b8edd99adf2309573677b1f22e0733a4460))

## [1.7.3](https://github.com/lukislp/homelab-autodoc/compare/v1.7.2...v1.7.3) (2026-08-22)


### Bug Fixes

* configure MkDocs Material to actually render Mermaid diagrams ([6a406d3](https://github.com/lukislp/homelab-autodoc/commit/6a406d38052dcc59d4431cc89dd5ab572e2c68e3))

## [1.7.2](https://github.com/lukislp/homelab-autodoc/compare/v1.7.1...v1.7.2) (2026-08-22)


### Bug Fixes

* allow the collector to reach autodoc-server within the namespace ([8aabbe4](https://github.com/lukislp/homelab-autodoc/commit/8aabbe4b7e4f93f5eef4ecefbf2cb0ec76338715))
* grant the collector RBAC read access to statefulsets ([412411e](https://github.com/lukislp/homelab-autodoc/commit/412411e89bb41dcfe0ad0fbe6b9a842682f93e46))

## [1.7.1](https://github.com/lukislp/homelab-autodoc/compare/v1.7.0...v1.7.1) (2026-08-22)


### Bug Fixes

* redirect GET /admin (no trailing slash) to /admin/ ([e1f605d](https://github.com/lukislp/homelab-autodoc/commit/e1f605dee32322cbf867a9b9448bc2a46cd9b847))
* trust proxy headers so OAuth redirect_uri is https, not http ([4509627](https://github.com/lukislp/homelab-autodoc/commit/450962797363aeab12e1bc6af0c69c7e5b124565))

# [1.7.0](https://github.com/lukislp/homelab-autodoc/compare/v1.6.0...v1.7.0) (2026-08-22)


### Features

* add Kubernetes deployment manifests (Kustomize, FluxCD-ready) ([7f6349b](https://github.com/lukislp/homelab-autodoc/commit/7f6349bc21fe792f45080184488365066796772c))
* rebuild k8s manifests to match the real cluster's established conventions ([9cde394](https://github.com/lukislp/homelab-autodoc/commit/9cde3946805a3f460691f61a9c823a9c45f65556))

# [1.6.0](https://github.com/lukislp/homelab-autodoc/compare/v1.5.0...v1.6.0) (2026-08-22)


### Features

* add multi-arch Docker images for collector and server ([98ef5f7](https://github.com/lukislp/homelab-autodoc/commit/98ef5f7b5d9fd57d10be72a1970e13ca92a9a4c8))

# [1.5.0](https://github.com/lukislp/homelab-autodoc/compare/v1.4.0...v1.5.0) (2026-08-22)


### Features

* add collector --push mode, closing the device-grant client loop ([b81a7c3](https://github.com/lukislp/homelab-autodoc/commit/b81a7c38ed4beb77aa63d52a812bd7743576d3be))

# [1.4.0](https://github.com/lukislp/homelab-autodoc/compare/v1.3.0...v1.4.0) (2026-08-22)


### Features

* add GitHub/OIDC admin login, setup wizard, and a React admin app ([0707a3e](https://github.com/lukislp/homelab-autodoc/commit/0707a3e3d2faf954faffaa73bb3d0c368bbc5f42))

# [1.3.0](https://github.com/lukislp/homelab-autodoc/compare/v1.2.0...v1.3.0) (2026-08-22)


### Features

* add OAuth 2.0 Device Authorization Grant for cluster registration ([87a303a](https://github.com/lukislp/homelab-autodoc/commit/87a303ab7fc4aef3d14e76d9c00106756c96fac4))

# [1.2.0](https://github.com/lukislp/homelab-autodoc/compare/v1.1.0...v1.2.0) (2026-08-22)


### Features

* add S3 server with push endpoint and MkDocs site hosting ([66a5943](https://github.com/lukislp/homelab-autodoc/commit/66a5943c647ad35c3ab2ac5697b4973e61e6d5d4))

# [1.1.0](https://github.com/lukislp/homelab-autodoc/compare/v1.0.0...v1.1.0) (2026-08-22)


### Features

* add S2 generator with deterministic facts/diagrams and LiteLLM prose ([6a7ad43](https://github.com/lukislp/homelab-autodoc/commit/6a7ad43c14ba554fea303509f9d6be94e390c5bc))

# 1.0.0 (2026-08-22)


### Features

* add S1 collector with pluggable workload adapters ([8979bcc](https://github.com/lukislp/homelab-autodoc/commit/8979bcc887db186898d671d27a5b03eadfd00f13))
