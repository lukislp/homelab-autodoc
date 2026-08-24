# Build context is the repo root (not collector/) - autodoc-collector depends
# on the sibling autodoc-core package, which Docker can't COPY from outside
# its context otherwise.
FROM python:3.12-slim

WORKDIR /app
COPY core ./core
COPY collector ./collector
RUN pip install --no-cache-dir ./core ./collector

# Non-root runtime user (numeric so runAsNonRoot can be verified). The only
# thing the collector ever writes is its push token, which lives on a
# volume - nothing inside the image needs to be writable. HOME points at
# /tmp so any library cache writes land somewhere writable.
RUN useradd --uid 10001 --user-group --no-create-home autodoc
ENV HOME=/tmp
USER 10001

ENTRYPOINT ["autodoc-collector"]
