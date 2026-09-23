# Build context is the repo root (not collector/) - autodoc-collector depends
# on the sibling autodoc-core package, which Docker can't COPY from outside
# its context otherwise.
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

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
# Third-party dependencies come from the hash-locked requirements/collector.txt (pip-compile
# --generate-hashes); the local packages are then installed without resolving anything else.
# The local ones go in as editable installs (-e) against the COPYed source trees that stay in
# the image: that is the form pip documents as safe when dependency resolution is switched off,
# and unlike a plain path install it leaves no unpinned resolution step in the build.
COPY requirements/collector.txt ./requirements/collector.txt
RUN pip install --no-cache-dir --require-hashes -r requirements/collector.txt
COPY core ./core
COPY collector ./collector
RUN pip install --no-cache-dir --no-deps -e ./core -e ./collector

# Non-root runtime user (numeric so runAsNonRoot can be verified). The only
# thing the collector ever writes is its push token, which lives on a
# volume - nothing inside the image needs to be writable. HOME points at
# /tmp so any library cache writes land somewhere writable.
RUN useradd --uid 10001 --user-group --no-create-home autodoc
ENV HOME=/tmp
USER 10001

ENTRYPOINT ["autodoc-collector"]
