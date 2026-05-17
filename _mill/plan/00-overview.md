# Plan: 61 (A) -- Review pipeline fixes

```yaml
task: "61 (A) -- Review pipeline fixes"
slug: mill-review-pipeline-fixes
approved: true
started: "20260517-140037"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-common
    file: 01-review-common.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: backend-error-envelope
    file: 02-backend-error-envelope.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: review-discussion-cli
    file: 03-review-discussion-cli.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 4
    name: mill-go-config
    file: 04-mill-go-config.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: ascii-only-output

- **Decision:** Every `print()` / `_log()` string in production code stays ASCII-only. Em-dash to ` -- `, right-arrow to ` -> `. Docstrings and comments are exempt.
- **Rationale:** Windows cp1252 terminals crash on non-ASCII stdout/stderr. Project rule from `CLAUDE.md`.
- **Applies to:** all batches

### Decision: no-new-dependencies

- **Decision:** No new external Python dependencies. Stay within `pyyaml` + stdlib. The plugin venv is intentionally minimal.
- **Rationale:** Plugin is installed on operator machines via a thin venv created by `update-plugins.ps1`. Dependency drift means re-syncing on every install.
- **Applies to:** all batches

### Decision: unit-tests-colocated-with-helper

- **Decision:** New unit tests live in the existing `test-<name>.py` file for the helper being changed (`test-review-common.py`, `test-review-code-flow.py`, `test-review-discussion-flow.py`). No new test files unless adding tests for a new module.
- **Rationale:** Matches existing convention in `plugins/mill/unit_tests/`. Run via `python plugins/mill/unit_tests/run-all.py`.
- **Applies to:** batches 1, 2

### Decision: filename-via-write-review-file

- **Decision:** Every code-path that produces a review file routes through `_review_common.write_review_file(reviews_dir, review_type, round_num, content, scope=...)`. No direct `.write_text` of a review file anywhere in `_review_*.py`.
- **Rationale:** Single naming gate prevents the `-holistic-review-` regression from re-emerging (#316). `write_review_file`'s `scope` parameter already handles per-batch vs. holistic naming correctly.
- **Applies to:** batch 2

### Decision: error-envelope-shape

- **Decision:** When `parse_verdict` raises `ReviewError` in a backend, the backend catches the exception, calls `write_review_file(...)` to persist the raw response, and returns `ReviewResult(verdict="ERROR", reviews=[{"scope": ..., "verdict": "ERROR", "file": <path>, "error": <str(exc)>, "session_id": <id>}])`. CLI exits 0. The structured ERROR envelope is consumed by `mill-go` step 3.5 / step 4.5.
- **Rationale:** Bare exit-1 with no JSON breaks mill-go's ERROR-only retry path. The shape matches the existing `_review_plan.py` envelope at lines 607-617.
- **Applies to:** batch 2

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
