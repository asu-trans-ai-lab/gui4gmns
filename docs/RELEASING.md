# Releasing gui4gmns

How to publish a new version of `gui4gmns` to PyPI. The release pipeline uses **PyPI Trusted
Publishing (OIDC)** — no API tokens are stored anywhere. A GitHub Release triggers the upload.

- Real release workflow: [`.github/workflows/publish.yml`](../.github/workflows/publish.yml) (fires on Release published)
- Dry-run workflow: [`.github/workflows/publish-testpypi.yml`](../.github/workflows/publish-testpypi.yml) (manual, TestPyPI)

---

## 0. One-time trusted-publisher setup

Do this once per index (PyPI and TestPyPI). **This is the step that has caused every failure so
far** — the config must match the workflow *filename* and *environment name* exactly.

On **pypi.org** → your account → *Publishing* → *Add a pending publisher*:

| Field | Value |
|---|---|
| PyPI Project Name | `gui4gmns` |
| Owner | `asu-trans-ai-lab` |
| Repository name | `gui4gmns` |
| Workflow filename | `publish.yml`  ← the **file name**, not the workflow's `name:` |
| Environment name | `pypi` |

On **test.pypi.org** → same thing, but Workflow filename `publish-testpypi.yml`, Environment
`testpypi`.

> **The classic mistake:** entering the workflow's display `name:` (`Publish to PyPI`) in the
> "Workflow filename" field instead of the actual file name (`publish.yml`). PyPI then rejects the
> OIDC token with a mismatch error and the publish step fails. If a publish fails, check this first.

The GitHub environments (`pypi`, `testpypi`) are referenced by the workflows; GitHub creates them on
first run. You can pre-create them under repo *Settings → Environments* to add required reviewers.

---

## 1. Pre-flight (local, every release)

From a clean checkout, in a fresh venv:

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
python -m pip install --upgrade pip build twine

# a) packaging installs and the API/CLI work
python -m pip install -e .
python -c "import gui4gmns; print(gui4gmns.__version__); from gui4gmns import generate"
python -c "import sys,gui4gmns; sys.argv=['gui4gmns','datasets/05_toy_bottleneck']; gui4gmns.main()"

# b) build + metadata check
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*        # both wheel and sdist must say PASSED

# c) private-data guard MUST pass
python validate_no_private_data.py  # must print "clean: no private-looking files tracked"
```

Bump the version in [`pyproject.toml`](../pyproject.toml) **and** `__version__` in
[`ai-gen/gui4gmns.py`](../ai-gen/gui4gmns.py) — they must match. Semver: exporter / contract
output-format changes bump the minor.

## 2. TestPyPI dry-run (recommended before any real release)

Proves the OIDC plumbing without burning a real version number.

```bash
gh workflow run publish-testpypi.yml -R asu-trans-ai-lab/gui4gmns
gh run watch -R asu-trans-ai-lab/gui4gmns   # or watch the Actions tab
```

Then confirm from a clean venv:

```bash
pip install -i https://test.pypi.org/simple/ gui4gmns
python -c "import gui4gmns; print(gui4gmns.__version__)"
```

## 3. Cut the real release

```bash
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 \
  --repo asu-trans-ai-lab/gui4gmns \
  --title "gui4gmns v0.1.0" \
  --generate-notes \
  --notes "First public release. Pure-Python generator: GMNS folder -> self-contained dashboard + auto portals. See README. Works/experimental status per the QA report."
```

Publishing the Release fires `publish.yml` → builds → publishes to PyPI via OIDC.

```bash
gh run watch -R asu-trans-ai-lab/gui4gmns
```

## 4. Verify from a user's seat

```bash
python -m venv .verify && source .verify/Scripts/activate
pip install gui4gmns
python -c "import gui4gmns; print(gui4gmns.__version__)"
python -c "from gui4gmns import generate; generate('datasets/05_toy_merge')"   # dashboard appears
```

Screenshot the install + a generated dashboard for the QA report.

---

## Gotchas

- **PyPI versions are permanent.** `0.1.0` can never be re-uploaded, even after `yank`. Dry-run on
  TestPyPI first; only tag when pre-flight is green.
- **Publish step failed with an OIDC/trust error?** 99% of the time it's the workflow-filename vs
  workflow-`name:` mix-up in §0. Fix the pending publisher, then re-run: `gh workflow run
  publish.yml` (or re-publish the release).
- **No `password:` in the workflow is correct** — OIDC is used automatically when `id-token: write`
  is granted. Do not add a token.
- The wheel intentionally ships only `gui4gmns.py`; `engine/` and `python-lab/` are excluded.
