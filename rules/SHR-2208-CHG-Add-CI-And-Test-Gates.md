# CHG-2208: Add CI And Test Gates

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Completed
**Date:** 2026-05-06
**Requested by:** Frank
**Priority:** Medium
**Change Type:** Normal

---

## What

Add pull-request CI/CD for Screen Harness:

- Python test matrix for `3.11`, `3.12`, and `3.13`.
- `pytest` and `compileall` gates.
- Alfred rules validation through `uvx --from fx-alfred af validate`.
- Package build gate with uploaded `dist/*` artifact.
- README CI badge and CI/CD documentation.
- Tests that pin the public Chrome/GitHub demo and README command contract.

## Why

`main` is now protected, so future code should enter through pull requests with automated checks. CI must prove the current MVP test suite, docs validation, and package build before merge.

## Impact Analysis

- **Systems affected:** GitHub Actions, Python packaging metadata, README, test suite, Alfred rules.
- **User-visible behavior:** Pull requests and pushes to `main` run automated validation; successful builds upload a distribution artifact.
- **Downtime required:** No.
- **Rollback plan:** Revert `.github/workflows/ci.yml`, the README CI section, the added example/README contract tests, and the dev dependency update.

## Implementation Plan

1. Add `pytest` as a dev dependency so CI is reproducible from `uv.lock`.
2. Add `.github/workflows/ci.yml`.
3. Add README badge and CI/CD section.
4. Add tests for the demo and README command contract.
5. Run local test, compile, package build, and Alfred validation.
6. Push a feature branch and open a PR into protected `main`.


## Testing / Verification

- `uv run pytest -q`
- `uv run python -m compileall -q src tests examples`
- `uv build`
- `uvx --from fx-alfred af validate`
- `af validate`


## Execution Log

| Date | Action | Result |
|------|--------|--------|
| 2026-05-06 | Created CHG for CI/test gates | Done |
| 2026-05-06 | Added GitHub Actions workflow, dev dependency, README docs, and contract tests | Done |
| 2026-05-06 | Ran local verification | `36` tests passed; `compileall`, `uv build`, `uvx --from fx-alfred af validate`, `af validate`, and workflow YAML parse passed |

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled and completed CI/test gate change record | Codex |
