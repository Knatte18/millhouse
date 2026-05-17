# Plan: 60 (A) — Branch/slug/claim fixes

```yaml
task: 60 (A) — Branch/slug/claim fixes
slug: mill-branch-slug-fixes
approved: true
started: 20260517-115821
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: branch-slug-helpers
    file: 01-branch-slug-helpers.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: review-cli-error-envelope
    file: 02-review-cli-error-envelope.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: millpy-implement-push-branch
    file: 03-millpy-implement-push-branch.md
    depends-on: []
    verify: null
  - number: 4
    name: millpy-bg-cwd-validation
    file: 04-millpy-bg-cwd-validation.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 5
    name: skill-error-retry-and-cwd-preludes
    file: 05-skill-error-retry-and-cwd-preludes.md
    depends-on: [2, 4]
    verify: null
```

## Shared Decisions

### Decision: ASCII-only stderr/stdout

- **Decision:** All new `print()` strings written to stdout/stderr use ASCII only. Em-dash → ` -- ` (space-hyphen-hyphen-space); arrows → ` -> `. Docstrings and comments inside Python source may use Unicode freely.
- **Rationale:** Windows cp1252 terminals crash on non-ASCII stdout/stderr. Inherited from `CLAUDE.md`'s "ASCII-only `print()` / `_log()` output strings" rule.
- **Applies to:** all batches

### Decision: Helper signatures from discussion are authoritative

- **Decision:** New helper signatures must exactly match the names and parameter shapes given in the discussion: `print_error_envelope(review_type: str, msg: str) -> None` lives in `_review_cli.py`; the `slug_from_branch` post-D1 control flow follows the discussion's pseudocode literally.
- **Rationale:** The discussion was reviewed and approved; downstream batches (and tests) cite these exact names. Renaming during implementation would silently invalidate the test bulks.
- **Applies to:** batches 1 and 2

### Decision: Tests live next to the helper they cover

- **Decision:** Tests for a helper change ship in the same batch as the change. The implementer writes the test (or extends the existing test module) in the same card or an adjacent card in the same batch — not deferred to a later batch.
- **Rationale:** Each batch becomes self-verifying via its `verify:` command. The DAG must not have a "tests" batch that depends on every code batch, because that creates a brittle late-stage failure mode and inflates per-batch context for the test batch.
- **Applies to:** all batches

### Decision: Lazy imports inside `millpy-bg.py` `_launcher_main`

- **Decision:** New imports needed for cwd validation (`_paths`, `_config`, `_marker`) are imported INSIDE `_launcher_main`, not at module top. The worker fast-path (lines 27-85 of `millpy-bg.py`) MUST remain stdlib-only.
- **Rationale:** Existing comment in `millpy-bg.py` documents the worker fast-path constraint. Violating it adds startup cost to every worker spawn and risks import-side-effect bugs in detached child processes.
- **Applies to:** batch 4

### Decision: No mid-run behavior changes

- **Decision:** ERROR-envelope emission and consumer-side ERROR retry are scoped to startup-failure paths only. Mid-run failures (LLM timeout inside a successful slug resolution, malformed reviewer output, etc.) keep their existing behavior. The discussion's "Wider review-pipeline refactor" Out-of-scope item is binding here.
- **Rationale:** Scope discipline. The bugs we are closing are all startup-path bugs.
- **Applies to:** batches 2 and 5

## All Files Touched

- `plugins/mill/scripts/_marker.py`
- `plugins/mill/scripts/_review_cli.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-bg-launcher.py`
- `plugins/mill/unit_tests/test-marker.py`
- `plugins/mill/unit_tests/test-millpy-claim.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-status.py`
