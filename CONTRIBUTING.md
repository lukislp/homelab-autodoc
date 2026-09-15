# Contributing to homelab-autodoc

Thanks for taking the time. homelab-autodoc is a single-maintainer project, so the process is
deliberately small - but it is the same for every change, including the maintainer's own.

## How changes get in

1. Open an issue first for anything bigger than a typo or an obvious bug fix, so the direction can
   be agreed before you spend time on it. Use the templates under `.github/ISSUE_TEMPLATE/`.
2. Fork the repository (or branch, if you have write access) and make your change on a branch.
3. Open a pull request against `master`. The pull-request template asks for what changed and why.
4. `master` is protected: a PR merges only after the whole test stage of
   [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) is green and the branch is up to
   date with `master` (enable auto-merge and it lands on its own once that is the case). Nobody
   pushes to `master` directly, not even the maintainer.

## Repository layout

Four Python packages plus a frontend, each with its own `pyproject.toml` and `tests/`:

- `core/` - shared model and serialization (`autodoc_core`), depended on by the other three
- `collector/` - the read-only in-cluster collector (`autodoc_collector`)
- `generator/` - turns collected facts into the doc site (`autodoc_generator`)
- `server/` - the web server and MkDocs site builder (`autodoc_server`)
- `frontend/` - the UI (Vite + TypeScript, oxlint, vitest)
- `charts/` - the Helm chart, `requirements/` - the compiled dependency locks

## What a pull request needs

- **Conventional Commits.** The version and the changelog are generated from the commit messages
  (`feat:` = minor release, `fix:` = patch release, `build:`/`ci:`/`docs:`/`test:` = no release).
  Squash-merge keeps the PR title as the commit message, so give the PR a Conventional Commit
  title.
- **Green required checks.** `test-lint` and `test-unit` run once per package - as
  `test-lint (core)`, `test-lint (collector)`, `test-lint (generator)`, `test-lint (server)` and
  the matching `test-unit (...)` legs - alongside `test-frontend-lint`, `test-frontend-unit`,
  `test-helm-lint` and `review / dependency-review`. All of them are required; a red one blocks
  the merge.
- **Tests for new functionality.** New features and bug fixes come with tests in the matching
  package's `tests/` directory. A PR that adds behaviour without a test is asked to add one.
  Coverage badges are regenerated per package on every release and are expected not to drop.
- **Lint and formatting.** Each package is linted with `ruff check .` **and** `ruff format --check .`
  from its own directory. Run both before pushing; `ruff check` passing does not mean the
  formatting is clean.
- **The chart has to template.** `test-helm-lint` runs `helm lint` and then templates every
  combination of the optional features (ingress, network policies, Gateway API, collector-only
  deployment), and additionally asserts that the fail-fast guards for `server.existingSecret` and
  `collector.pushUrl` still raise a clear error. A new value needs to be exercised there.
- **Facts stay deterministic.** The generated site separates facts derived from real cluster state
  from LLM-written prose. Keep that boundary: a change that lets generated prose influence a fact
  is out of scope.
- **Hash-pinned requirements.** `requirements/*.txt` are compiled with hashes and installed with
  `--require-hashes`. Add or bump a dependency by editing the matching `.in` file and
  regenerating (see below), never by hand-editing the `.txt`.

## Running things locally

CI uses Python 3.12 and Node 22. Work inside the package you are changing:

```bash
# core
cd core && pip install -e ".[dev]"

# collector or generator
cd collector && pip install -e ../core -e ".[dev]"

# server
cd server && pip install -e ../core -e ../generator -e ".[dev]"
```

Then, in that directory:

```bash
ruff check .
ruff format --check .
pytest
```

Frontend:

```bash
cd frontend
npm install
npm run lint    # oxlint
npm run build   # tsc -b && vite build - the type-check IS the build
npm run test    # vitest
```

Helm chart:

```bash
helm lint charts/homelab-autodoc
```

The fuzz job (`core`, Linux-only - `atheris` publishes no Windows wheel) is not a required check:

```bash
python core/fuzz/fuzz_serialize.py -max_total_time=30 -rss_limit_mb=1024
```

### Regenerating the requirement locks

`requirements/compile.sh` recompiles every lock with hashes. Run it in the pinned container so the
result matches CI:

```bash
docker run --rm -v "$PWD:/w" -w /w python:3.12-slim sh requirements/compile.sh
```

## Security issues

Please do not open a public issue for a vulnerability - use the private reporting path described
in [SECURITY.md](SECURITY.md). The [Code of Conduct](CODE_OF_CONDUCT.md) applies to every
interaction in this repository.
