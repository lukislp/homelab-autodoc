# Build context is the repo root - autodoc-server depends on the sibling
# autodoc-core/autodoc-generator packages, and this also bakes in the built
# React admin app (frontend/).
FROM node:26-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY core ./core
COPY generator ./generator
COPY server ./server
RUN pip install --no-cache-dir ./core ./generator ./server
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
