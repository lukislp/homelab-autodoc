# Build context is the repo root - autodoc-server depends on the sibling
# autodoc-core/autodoc-generator packages, and this also bakes in the built
# React admin app (frontend/).
FROM node:22-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

# Pull in Debian's security updates on every build: the digest-pinned base image lags behind
# the security archive (fixed CRITICAL CVEs in the base layer blocked the Trivy gate on
# 2026-09-13) and a rebuild is cheaper than waiting for the next python:3.12-slim digest.
# HTTPS mirror because plain-http port 80 is blocked on some build hosts.
RUN sed -i 's#http://deb.debian.org#https://deb.debian.org#' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get -y --no-install-recommends upgrade \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Third-party dependencies come from the hash-locked requirements/server.txt (pip-compile
# --generate-hashes); the local packages are then installed without resolving anything else.
# The local ones go in as editable installs (-e) against the COPYed source trees that stay in
# the image: that is the form pip documents as safe when dependency resolution is switched off,
# and unlike a plain path install it leaves no unpinned resolution step in the build.
COPY requirements/server.txt ./requirements/server.txt
RUN pip install --no-cache-dir --require-hashes -r requirements/server.txt
COPY core ./core
COPY generator ./generator
COPY server ./server
RUN pip install --no-cache-dir --no-deps -e ./core -e ./generator -e ./server
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Non-root runtime user. Only the two generated trees are writable by it -
# docs_src and site are rebuilt from /data on every push/startup - while the
# code and everything else under /app stay root-owned and read-only. HOME
# points at /tmp so any library cache writes land somewhere writable.
RUN useradd --uid 10001 --user-group --no-create-home autodoc     && rm -rf /app/server/docs_src /app/server/site     && mkdir -p /app/server/docs_src /app/server/site     && chown -R autodoc:autodoc /app/server/docs_src /app/server/site
ENV HOME=/tmp
USER 10001

# Absolute paths so behavior doesn't depend on the container's working
# directory. /data and /config are the two things worth persisting on a
# volume; docs_src/site are fully regenerated from /data on every push.
ENV AUTODOC_DATA_DIR=/data
ENV AUTODOC_CONFIG_DIR=/config
ENV AUTODOC_DOCS_DIR=/app/server/docs_src
ENV AUTODOC_MKDOCS_CONFIG=/app/server/mkdocs.yml
ENV AUTODOC_ADMIN_UI_DIR=/app/frontend/dist

EXPOSE 8000
ENTRYPOINT ["autodoc-server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
