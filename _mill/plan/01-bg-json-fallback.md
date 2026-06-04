# Batch: bg-json-fallback

```yaml
task: Fix millpy-bg EXIT marker and implementer reliability
batch: bg-json-fallback
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py test-millpy-bg.py
depends-on: []
```

## Batch Scope

Adds a JSON-presence fallback to `check_bg_status` in `_bg.py`: when a worker PID is dead
and no `[mill-bg] EXIT` sentinel is present, the function now scans the log in reverse for
the last line starting with `{` and attempts `json.loads`. If it parses, the worker completed
its job (the EXIT marker was lost to a hard-kill race) and `("exit", 0)` is returned.
This makes "dead" a genuine-failure signal (no JSON at all) rather than a false alarm from
the Windows job-object / psmux teardown race. Corresponding tests are added to
`test-bg-liveness.py` covering success, partial-write, and no-JSON cases, plus a regression
run of the existing `test-millpy-bg.py` EXIT-writing tests.

## Cards

### Card 1: Add JSON-presence fallback to check_bg_status

- **Context:**
  - `plugins/mill/scripts/_bg.py`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `import json` at the top of `_bg.py` (after existing stdlib imports, before `logging`).
  - Add a module-level helper `_last_json_line(text: str) -> bool` that scans `text.splitlines()` in reverse, finds the first line where `line.strip().startswith("{")`, tries `json.loads(line.strip())`, and returns `True` on success or `False` if no such line is found or if the parse raises `json.JSONDecodeError`. The function must not raise.
  - In `check_bg_status`, in the dead-path after the race-guard re-read block (the section that ends with `return ("dead", pid)`): after the `_EXIT_CODE_RE.search(text)` check on the re-read text, add: `if _last_json_line(text): return ("exit", 0)`. This replaces the bare `return ("dead", pid)` as the final else. The dead path now only returns `("dead", pid)` when truly no valid JSON is present.
  - Do not change `is_bg_worker_alive`, `_EXIT_RE`, `_EXIT_CODE_RE`, or the `_PID_RE` constants.
- **Commit:** `fix(_bg): return ("exit", 0) when dead+no-EXIT but JSON result present`

### Card 2: Add check_bg_status JSON fallback tests

- **Context:**
  - `plugins/mill/unit_tests/test-bg-liveness.py`
  - `plugins/mill/scripts/_bg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-bg-liveness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a `TestCheckBgStatusJsonFallback` unittest.TestCase class (or equivalent structure matching the existing test style in the file) with the following test methods:
    1. `test_dead_no_exit_valid_json_last_line`: log has PID=99999999 START line + `{"status":"success","commit_sha":"abc"}` as last line, no EXIT. Mock `time.time()` to return a value `_bg._STALE_LOG_SECONDS + 10` seconds after the log's mtime so the mtime fallback reports dead. Assert `check_bg_status(log_path) == ("exit", 0)`.
    2. `test_dead_no_exit_partial_json_last_line`: last line is `{"status":` (incomplete). Assert returns `("dead", 99999999)`.
    3. `test_dead_no_exit_no_json`: log has only the PID START line and some non-JSON output. Assert returns `("dead", 99999999)`.
    4. `test_dead_exit_present_unaffected`: log has PID START + `[mill-bg] EXIT 0`. Assert returns `("exit", 0)` (existing path unaffected).
    5. `test_dead_no_exit_json_mid_log_only`: JSON line appears mid-log but the last `{`-prefixed line is NOT valid JSON (e.g. `{"partial`). Assert returns `("dead", 99999999)`.
  - For tests 1-3 and 5: use PID 99999999 (assumed non-existent) so `os.kill` raises `ProcessLookupError`. Set the log file's mtime via `os.utime` to be stale so the fallback resolves to dead.
  - Use `unittest.mock.patch` for `time.time` where needed to control mtime staleness detection without relying on real clock.
- **Commit:** `test(_bg): add check_bg_status JSON fallback test cases`

## Batch Tests

Verify runs `test-bg-liveness.py` (covers the new JSON fallback logic in `check_bg_status`)
and `test-millpy-bg.py` (regression: confirms the existing `try/finally` EXIT-writing tests
still pass after the `_bg.py` change). Both test files are scoped to `_bg.py`-adjacent
behaviour. The verify command uses `run-all.py --only` to run exactly these two files.
