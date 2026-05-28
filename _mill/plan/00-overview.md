# Plan: Background worker + shell-metadata edge cases

```yaml
task: Background worker + shell-metadata edge cases
slug: bg-worker-and-shell-edge-cases
approved: true
started: 20260528-211634
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
    name: bg-worker-shell-edge-cases
    file: 01-bg-worker-shell-edge-cases.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py test-millpy-bg.py
```

## Shared Decisions

### Decision: no-behavior-change-on-364

- **Decision:** `_bg.is_bg_worker_alive` keeps its existing `except OSError` -> mtime-staleness fallback unchanged. The only addition is a `logging.getLogger(__name__).debug(...)` breadcrumb on the fallback path.
- **Rationale:** The fallback is the intended, already-tested design (a fresh-log worker stays alive; a stale-log worker is declared dead after 5 min). The original issue's "treat WinError 87 as alive=False" was rejected in discussion as risking false-negative re-fires of live workers.
- **Applies to:** bg-worker-shell-edge-cases

### Decision: reraise-baseexception-on-365

- **Decision:** The `millpy-bg.py` worker writes exactly one `[mill-bg] EXIT <code>` sentinel via a `finally`. `Exception` is caught-logged-and-returned-`1`; `BaseException` (`SystemExit`/`KeyboardInterrupt`) runs the `finally` then re-raises (it is NOT swallowed).
- **Rationale:** A `finally` is the only construct that guarantees the sentinel on `BaseException`; swallowing `BaseException` would hide `KeyboardInterrupt`/`SystemExit`. The cited `OSError`/`SubprocessError` cases are `Exception` subclasses already covered today.
- **Applies to:** bg-worker-shell-edge-cases

### Decision: ascii-only-output

- **Decision:** All new log/breadcrumb/doc text is ASCII only (` -- ` not an em-dash, ` -> ` not an arrow).
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII; repo-wide convention.
- **Applies to:** bg-worker-shell-edge-cases

### Decision: test-style-matches-file

- **Decision:** New tests follow each target file's existing style — `test-bg-liveness.py` uses `unittest.TestCase`; `test-millpy-bg.py` uses the hand-rolled `main()` with `PASS/FAIL` prints and per-test `try/except`.
- **Rationale:** Consistency with the file being edited; the hand-rolled harness only catches `Exception`, which drives the BaseException-test design in card 2.
- **Applies to:** bg-worker-shell-edge-cases

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_bg.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/unit_tests/test-bg-liveness.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
