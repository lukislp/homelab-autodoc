# Build context is the repo root - autodoc-server depends on the sibling
# autodoc-core/autodoc-generator packages, and this also bakes in the built
# React admin app (frontend/).
FROM node:22-slim AS frontend-build
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
