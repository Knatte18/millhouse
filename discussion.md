# Discussion: 23 (A) — mill infra bugfix-batch

```yaml
task: 23 (A) — mill infra bugfix-batch
slug: mill-infra-bugfix-batch
status: discussing
parent: main
```

## Problem

Four independent bugs were filed against the mill infra layer. Bug A (`_yaml_writer.quote_scalar` line-wrapping long paths at 80 chars) was fixed in task 19 (commit `ce38808`) and is already in main. The remaining three are:

- **Bug B (#160):** `millpy-implement.py` makes three consecutive `set_batch_field` calls in both the initial-dispatch and fix-cycle paths. Each call does its own read-modify-write. A crash between calls leaves `status.md` in an inconsistent state (e.g. `state: running` with no `start_sha`).
- **Bug C (#168):** The implementer's JSON report contains `commit_sha`, but the value's format is whatever Claude chose — sometimes 7-char abbreviated, sometimes 40-char. The builder and downstream tooling assume a stable format; the inconsistency causes confusion.
- **Bug D (#156):** `millpy-bg.py` uses `datetime.utcnow()`, which is deprecated since Python 3.12 and emits a `DeprecationWarning` in newer environments.

## Scope

**In:**
- Add `set_batch_fields(status_path, name, fields: dict)` to `_status.py` — atomic multi-field update for a single named batch entry.
- Replace the two 3-call sequences in `millpy-implement.py` (lines ~151–153 and ~228–230) with single `set_batch_fields` calls.
- After `_forward_output` extracts the implementer's JSON, run `git rev-parse HEAD` in the project root and overwrite `commit_sha` unconditionally before printing.
- Change `datetime.utcnow()` → `datetime.now(timezone.utc)` in `millpy-bg.py`.

**Out:**
- Bug A — already fixed in main; no code change.
- Changes to the implementer brief template (the `commit_sha` override happens server-side in `millpy-implement.py`, not by re-educating the implementer).
- Any other `millpy-*.py` or `_status.py` callers not directly involved in the three bugs.

## Decisions

### skip-bug-a

- Decision: Skip bug A entirely. No code change, no comment.
- Rationale: `_yaml_writer.py` line 60 already has `width=float("inf")` after task 19. Adding a no-op change would pollute the diff.
- Rejected: Adding an assertion or comment confirming the fix — unnecessary noise.

### atomic-set-batch-fields

- Decision: Add `set_batch_fields(status_path: Path, name: str, fields: dict[str, str | int | None]) -> None` to `_status.py`. It performs one `read_batches` → mutate all requested keys → `_write_batches` cycle. Validation (key allowlist, state allowlist) runs before mutation.
- Rationale: Makes the atomic multi-field update reusable for any future caller. Keeps `millpy-implement.py` clean — both call sites shrink to a single call.
- Rejected: Inlining the fix in `millpy-implement.py` — duplicates the validation logic and leaves `set_batch_field` as a footgun for callers who don't know they need atomicity.

### commit-sha-override

- Decision: Modify `_forward_output(output: str, project_root: Path) -> int` to accept the project root as a second argument. After extracting the JSON dict, run `subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root, ...)` and overwrite `commit_sha` with the result before printing. On non-zero exit from `git rev-parse`, forward the original JSON unmodified (preserving the always-0 return contract).
- Rationale: `git rev-parse HEAD` is authoritative and always 40 chars. Overriding unconditionally means format is stable regardless of what the implementer reported. Call sites in `main()` already have `project_root` in scope. The fallback-to-original policy on git failure preserves the function's no-exception, always-0 contract.
- Rejected: Patching the implementer brief to mandate a specific SHA format — doesn't fix existing sessions and relies on the LLM following format instructions exactly.

### datetime-utcnow-fix

- Decision: `from datetime import datetime, timezone` → `datetime.now(timezone.utc).strftime(...)` in `millpy-bg.py`.
- Rationale: `timezone.utc` is available from Python 3.2+, covers all supported environments. `datetime.UTC` (Python 3.11+ shorthand) is more concise but excludes older runtimes unnecessarily.
- Rejected: `datetime.now(datetime.UTC)` — requires Python 3.11+.

### single-batch

- Decision: Implement bugs B, C, and D in one batch.
- Rationale: Total change is ~30 lines across 3 files in the same `plugins/mill/scripts/` directory. No ordering dependency between the fixes. Splitting would add unnecessary overhead.
- Rejected: Two batches (B+C / D) — overkill for a one-line fix in a separate file.

## Technical context

- `plugins/mill/scripts/_status.py`: `set_batch_field` (line 624) does `read_batches → mutate → _write_batches`. The new `set_batch_fields` follows the same pattern but mutates multiple keys in a single pass. `_BATCH_ALLOWED_KEYS` and `_BATCH_STATES` are the validation constants; both must be checked before any mutation.
- `plugins/mill/scripts/millpy-implement.py`: `_forward_output(output: str) -> int` (line 42) extracts the last JSON object with `"status"` from implementer output and prints it. It needs a `project_root: Path` parameter added so it can run `git rev-parse HEAD`. Both call sites (lines 210 and 291) have `project_root` in scope.
- `plugins/mill/scripts/millpy-bg.py`: line 109 — single-line fix.
- Unit tests: `plugins/mill/unit_tests/test-status.py`, `test-millpy-implement.py`, `test-millpy-bg.py`. Tests use in-memory/`tempfile` fixtures; no real git or LLM calls.

## Testing

- **`test-status.py`**: Add tests for `set_batch_fields` — success path (all fields written, single read-modify-write cycle), validation path (unknown key raises `ValueError`, unknown state raises `ValueError`, unknown batch name raises `ValueError`). Import `set_batch_fields` from `_status`.
- **`test-millpy-implement.py`**: Add tests for `_forward_output`: (1) success path — implementer reports 7-char SHA, `git rev-parse HEAD` returns 40-char SHA, output JSON has the 40-char value; (2) git failure path — `git rev-parse HEAD` exits non-zero, original JSON forwarded unmodified (preserving 7-char or whatever the implementer reported). Mock `subprocess.run` for both paths.
- **`test-millpy-bg.py`**: Add test verifying the log-file timestamp is UTC-aware (timezone-aware `datetime` object, not naive). This can verify the format output or check that no `DeprecationWarning` is raised.

## Q&A log

- **Q:** Bug A already fixed — skip entirely? **A:** Yes. No code change.
- **Q:** `set_batch_fields` in `_status.py` or inline in `millpy-implement.py`? **A:** Add to `_status.py` for reusability.
- **Q:** Override `commit_sha` unconditionally or only when format is wrong? **A:** Unconditionally — authoritative source is `git rev-parse HEAD`.
- **Q:** `timezone.utc` or `datetime.UTC`? **A:** `timezone.utc` for Python 3.2+ compatibility.
- **Q:** One batch or two? **A:** One batch.
