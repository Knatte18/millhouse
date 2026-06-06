# Plan: Fix millpy-bg EXIT marker missing on wrapper crash

```yaml
task: "Fix millpy-bg EXIT marker missing on wrapper crash"
slug: "mill-bg-exit-marker"
approved: false
started: "20260606-185327"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: bg-completion-detection
    file: 01-bg-completion-detection.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py test-bg-json-contract.py
```

## Shared Decisions

### Decision: detection-side-only

- **Decision:** The fix lives entirely on the consumer/detection side (`_bg.py`). Do NOT add
  worker-side signal handlers, `atexit` hooks, or any mechanism that tries to make the worker
  write `EXIT` when hard-killed.
- **Rationale:** On Windows a psmux teardown is an uncatchable `TerminateProcess`; no in-process
  handler can run. Completion of a hard-killed worker can only be inferred by the poller from the
  trailing-JSON sentinel already present in the log. See `_mill/discussion.md` → Decisions →
  `keep-finally-clarify-framing` and Scope → Out.
- **Applies to:** all batches

### Decision: preserve-public-shapes

- **Decision:** Keep the existing public return shapes and string labels of
  `_bg.check_bg_status` (`("running"|"exit"|"dead", pid_or_code_or_None)`) and
  `_bg.is_bg_worker_alive` (`(bool, int|None)`) exactly. Only the *timing* of when
  `check_bg_status` returns `"exit"` vs `"running"` for the finished-but-killed case changes.
- **Rationale:** Orchestrator skills (`mill-go`, `mill-plan`, `mill-start`, `mill-pause`) branch
  on these labels verbatim. Changing the contract would require cross-skill edits that are
  explicitly out of scope.
- **Applies to:** all batches

### Decision: in-memory-tests-only

- **Decision:** All tests are in-memory/tempfile. Drive liveness branches by monkeypatching
  `_bg.os.kill` (raise `OSError(22, ...)` for the inconclusive-probe / Windows shape; use the
  current `os.getpid()` or a mocked clean return for affirmatively-alive). Drive the staleness
  branch by backdating log mtime with `os.utime`. No real git, LLM, or subprocess. ASCII-only
  diagnostics.
- **Rationale:** Repo unit-test convention (`plugins/mill/unit_tests/`, run via `run-all.py`);
  `os.kill(pid, 0)` semantics differ by platform, so the probe must be mocked for determinism —
  matching the existing `test_log_oserror_fallback_to_mtime` / `test_systemerror_fallback_to_mtime`.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_bg.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/unit_tests/test-bg-json-contract.py`
- `plugins/mill/unit_tests/test-bg-liveness.py`
