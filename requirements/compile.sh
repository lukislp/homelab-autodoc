#!/usr/bin/env sh
# Regenerates every hash-locked requirements/*.txt from its *.in on Linux with the CI's
# Python (must match PYTHON_VERSION in .github/workflows/ci-cd.yml and the Dockerfiles):
#   docker run --rm -v "$PWD:/w" -w /w python:3.12-slim sh requirements/compile.sh
set -eu
cd "$(dirname "$0")"
# pip-tools itself comes from its own hash-locked file (regenerate it the same way when bumping).
pip install -q --require-hashes -r pip-tools.txt
for f in core collector generator server; do
  pip-compile -q --generate-hashes --strip-extras --allow-unsafe --no-emit-index-url "$f.in"
done
for f in core collector generator server; do
  pip-compile -q --generate-hashes --strip-extras --allow-unsafe --no-emit-index-url "$f-dev.in"
done
pip-compile -q --generate-hashes --strip-extras --allow-unsafe --no-emit-index-url lint.in
pip-compile -q --generate-hashes --strip-extras --allow-unsafe --no-emit-index-url core-fuzz.in
for f in *.txt; do echo "$f: $(grep -cE '^[a-zA-Z0-9]' "$f") packages"; done
