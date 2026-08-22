# Build context is the repo root (not collector/) - autodoc-collector depends
# on the sibling autodoc-core package, which Docker can't COPY from outside
# its context otherwise.
FROM python:3.12-slim

WORKDIR /app
COPY core ./core
COPY collector ./collector
RUN pip install --no-cache-dir ./core ./collector

ENTRYPOINT ["autodoc-collector"]
