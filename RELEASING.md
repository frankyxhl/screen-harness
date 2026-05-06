# Releasing Screen Harness

Tag-driven release flow. Push a tag matching `v*` to `main` and
`.github/workflows/release.yml` runs tests, builds wheel + sdist,
attaches them to a GitHub Release, and publishes to PyPI via
**Trusted Publisher (OIDC)** — no PyPI API token in CI.

## One-time setup (do this once before the first release)

### 1. PyPI Trusted Publisher

Create a PyPI account if needed, then go to
**https://pypi.org/manage/account/publishing/** and click
**"Add a new pending publisher"**. Enter:

| Field | Value |
|---|---|
| PyPI Project Name | `screen-harness` |
| Owner | `frankyxhl` |
| Repository name | `screen-harness` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

The publisher stays "pending" until the first successful upload — the
first release creates the project on PyPI.

### 2. GitHub `pypi` environment

Go to
**https://github.com/frankyxhl/screen-harness/settings/environments**
→ **"New environment"** → name it **`pypi`**. Optionally add a
deployment-protection rule scoped to tags matching `v*`.

That's it. No secrets to add.

## Per-release procedure

1. **Bump the version** in `pyproject.toml`. Follow semver:
   - `0.x.0 → 0.x.1` for fixes only.
   - `0.x.0 → 0.(x+1).0` for new features (current cadence pre-1.0).
   - `0.x.y → 1.0.0` for the first stable promise.
2. **Commit the bump** with a `chore(release): vX.Y.Z` message; push to `main`.
3. **Tag** locally: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. Watch **Actions → Release** — the four jobs (`test`, `build`,
   `github-release`, `pypi-publish`) run sequentially.
5. Verify
   - GitHub Release at `https://github.com/frankyxhl/screen-harness/releases/tag/vX.Y.Z`
   - PyPI page at `https://pypi.org/project/screen-harness/X.Y.Z/`

The workflow asserts `pyproject.toml` version matches the tag (minus
the `v`). Mismatch → build fails before any publish.

## Yanking / hotfixing

- **Yank a bad PyPI release**: `pypi.org` project → release → "Yank".
  Do NOT delete; deletion forfeits the version number forever.
- **Hotfix**: bump patch, tag, push. The trusted publisher works for
  every subsequent tag once the publisher exists.

## Paste-ready prompt for Claude Code

When you're ready to cut a release, paste this into a fresh Claude Code
session in the repo:

> Cut a Screen Harness release. Read RELEASING.md for the procedure.
> Bump pyproject.toml to the version I specify, commit the bump on
> `main`, tag it `vX.Y.Z`, and push the tag so the release workflow
> fires. Before pushing, run `uv run pytest -q` and `uv build` locally
> to confirm. If `pypi.org/project/screen-harness/` shows the project
> doesn't exist yet, remind me to verify the Trusted Publisher is set
> up at https://pypi.org/manage/account/publishing/. Don't push if
> tests fail or if the version is unchanged from the last tag.

Replace `X.Y.Z` with the version you want.
