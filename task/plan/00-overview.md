# Plan: 50 (A) — Bug-fix batch 5 (post-44 triage)

```yaml
task: 50 (A) — Bug-fix batch 5 (post-44 triage)
slug: mill-misc-fixes-5
approved: true
started: 20260512-063514
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: status-helpers
    file: 01-status-helpers.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-status.py
  - number: 2
    name: skill-docs
    file: 02-skill-docs.md
    depends-on: [1]
    verify: null
  - number: 3
    name: small-fixes
    file: 03-small-fixes.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-no-unicode-arrow.py
  - number: 4
    name: implementer-jsonreport
    file: 04-implementer-jsonreport.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-implementer-common.py
```

## Shared Decisions

### Decision: status-row timestamps are canonical-form quoted

- **Decision:** Timeline-row timestamps written by `_status.append_phase` go
  through `_yaml_writer.quote_scalar` before insertion, matching
  `render_initial`. Canonical on-disk shape: `<phase>  '<iso-timestamp>'`.
- **Rationale:** `render_initial` already quotes; two writers producing the
  same logical column with different shapes forces consumers to tolerate or
  normalise both. Quoting is YAML-safe for ISO-8601 strings and costs one
  extra single-quote pair.
- **Applies to:** status-helpers.

### Decision: `_status.set_blocked` is purpose-built for blocked_reason

- **Decision:** Add a new helper `_status.set_blocked(status_path, reason, *, timestamp)`
  that (1) rewrites `phase: blocked` in the top yaml block, (2) writes
  `blocked_reason: <quoted reason>` (inserting the key after `phase:` when
  absent, overwriting in place when present), (3) appends
  `blocked  '<quoted timestamp>'` to the timeline. `_status.update_field`'s
  strict-key behaviour stays unchanged. Skills that previously chained
  `_status.append_phase(..., "blocked", ...)` + `_status.update_field(..., "blocked_reason", ...)`
  collapse to a single `_status.set_blocked(...)` call.
- **Rationale:** Loosening `update_field` with `add_if_missing=True` would
  mask typo bugs in the seven other call sites that rely on strict-key
  validation. Adding `blocked_reason: null` to the status template would
  put data on every status.md that ~95% of tasks never populate. A
  targeted helper keeps both contracts intact.
- **Applies to:** status-helpers (helper), skill-docs (call sites).

### Decision: #243 fallback uses `compute_new_dirt`, not a new helper

- **Decision:** The `_implementer_common._forward_output` fallback that infers
  success when stdout has no JSON object calls the existing
  `_cleanliness.compute_new_dirt(project_root, snapshot_path)` and treats an
  empty return list as "no new dirt since batch start". No new
  `_cleanliness.is_clean` is added.
- **Rationale:** `compute_new_dirt` against the per-batch snapshot mill-go
  already captures (`task/.cleanliness-snapshot-<batch_name>.txt`) is the
  correct semantic — it measures only dirt the implementer left behind, not
  pre-existing worktree state. Adding a wider `is_clean` helper would
  conflate the two.
- **Applies to:** implementer-jsonreport.

### Decision: All print()-output in unit tests stays ASCII

- **Decision:** Replace U+2192 `→` with ASCII `->` in every `print()` call
  across `plugins/mill/unit_tests/`. A regression-guard test scans every
  `test-*.py` for the character and fails on any reintroduction.
- **Rationale:** `run-all.py` already sets `PYTHONIOENCODING=utf-8` for
  child processes, but a developer running an individual test file
  directly under PowerShell 5 (cp1252 default) still hits
  `UnicodeEncodeError`. ASCII output is the portable convention elsewhere
  in mill scripts.
- **Applies to:** small-fixes.

## All Files Touched

- `plugins/mill/SCRIPTS.md`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-no-unicode-arrow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-status.py`
