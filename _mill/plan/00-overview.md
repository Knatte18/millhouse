# Plan: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps

```yaml
task: 'millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps'
slug: millpy-implement-fix-stuck-type-false-positives
approved: true
started: 20260904-105216
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: commit-baseline-write-before-dirty-check
    file: 01-commit-baseline-write-before-dirty-check.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 2
    name: test-corroboration-write-commit
    file: 02-test-corroboration-write-commit.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
  - number: 3
    name: forward-verify-baselines-millpy-fix
    file: 03-forward-verify-baselines-millpy-fix.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fix-finalize.py
  - number: 4
    name: fresh-session-after-self-resolve
    file: 04-fresh-session-after-self-resolve.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-millpy-implement.py
  - number: 5
    name: bg-heartbeat-diagnosability
    file: 05-bg-heartbeat-diagnosability.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-bg.py
```

## Shared Decisions

### Decision: git identity is threaded as parameters, never re-resolved

- **Decision:** `_implementer_common.py` never calls `git config --global --get user.name`/`user.email` itself. `git_name`/`git_email` are accepted as new optional (`None`-defaulting) keyword parameters on `_run_verify_gates`, `finalize_from_output`, and `_forward_output`, sourced from the two CLI callers' (`millpy-implement.py`, `millpy-fix.py`) already-existing local resolution of these values at the top of `main()`.
- **Rationale:** Both callers already resolve and fail-fast on missing git identity before reaching finalize. Re-resolving inside the shared module would duplicate that check or silently diverge from it. Discussion.md Decision `954-commit-baseline-write-before-dirty-check`.
- **Applies to:** all batches touching `_implementer_common.py`, `millpy-implement.py`, `millpy-fix.py` (batches 1, 2, 3).

### Decision: `None`-default parameters degrade to a safe no-op, never raise

- **Decision:** Every new optional parameter introduced by this plan (`git_name`, `git_email`, and any new field defaults touched in `_status.py`) preserves this module's existing convention: when the value needed to perform the new behavior is absent (`None`), the new code path is skipped silently rather than raising. This matches how every other optional parameter in `_run_verify_gates`/`finalize_from_output` already behaves (e.g. `batch_verify_baseline=None` disables the waiver; `status_path=None` disables the self-healing persist).
- **Rationale:** `_implementer_common.py`'s entire optional-parameter surface follows this backward-compatible-default convention already; introducing an exception for the new parameters would be an inconsistent surprise for the next reader.
- **Applies to:** all batches.

### Decision: no new CLI flags, no orchestrator (`mill-go-base/SKILL.md`) edits

- **Decision:** None of the four fixes in this plan add a new CLI flag or touch `mill-go-base/SKILL.md`'s escalation/phase-gate logic. `_status.py`'s `_BATCH_ALLOWED_KEYS` gains one new key; no other schema surface changes.
- **Rationale:** discussion.md's `## Scope` "Out:" list explicitly excludes orchestrator escalation-path changes and new CLI flags — the fixes read existing signals (the phase timeline, already-resolved git identity, existing baseline fields) rather than adding new ones.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-fix-finalize.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-status.py`
