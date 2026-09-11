#!/usr/bin/env sh
# Regenerates every hash-locked requirements/*.txt from its *.in on Linux with the CI's
# Python (must match PYTHON_VERSION in .github/workflows/ci-cd.yml and the Dockerfiles):
#   docker run --rm -v "$PWD:/w" -w /w python:3.12-slim sh requirements/compile.sh
set -eu
cd "$(dirname "$0")"
pip install -q pip-tools
for f in core collector generator server; do
  pip-compile -q --generate-hashes --strip-extras --allow-unsafe --no-emit-index-url "$f.in"
done
for f in core collector generator server; do
  pip-compile -q --generate-hashes --strip-extras --allow-unsafe --no-emit-index-url "$f-dev.in"
done
pip-compile -q --generate-hashes --strip-extras --allow-unsafe --no-emit-index-url lint.in
for f in *.txt; do echo "$f: $(grep -cE '^[a-zA-Z0-9]' "$f") packages"; done
