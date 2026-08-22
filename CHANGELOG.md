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
