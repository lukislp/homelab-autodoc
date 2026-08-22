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
