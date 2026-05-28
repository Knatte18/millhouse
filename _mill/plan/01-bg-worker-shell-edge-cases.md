# Batch: bg-worker-shell-edge-cases

```yaml
task: Background worker + shell-metadata edge cases
batch: bg-worker-shell-edge-cases
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py test-millpy-bg.py
depends-on: []
```

## Batch Scope

This single batch delivers all three grouped edge-case fixes, because each is a small, self-contained change in a different file and a single implementer holds the full context (5 small files) well under the 200k window. The three cards share no source code — only the read-only `_mill/discussion.md` design doc — so there is no cross-card ordering requirement; cards may be implemented in any order. There is no external interface for a later batch to consume (this is the only batch). Batch-local decisions are captured per card below; cross-cutting decisions live in `00-overview.md` (`## Shared Decisions`).

Two of the three fixes are **hardening + regression coverage of already-correct code**, not green-field bug fixes (verified during discussion): card 4's `_bg.py` already catches `OSError`, and card 7's `millpy-bg.py` already writes `EXIT -1` on `Exception`. The implementer must preserve that existing behavior and add only the deltas described.

## Cards

### Card 1: #364 -- `_bg.is_bg_worker_alive` OSError-fallback debug breadcrumb + regression test

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
  - `plugins/mill/unit_tests/test-bg-liveness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/_bg.py`: add `import logging` to the imports and a module-level `_logger = logging.getLogger(__name__)`. Change the bare `except OSError:` clause inside `is_bg_worker_alive` to `except OSError as exc:` and, before the `pass`/fall-through to the mtime check, emit `_logger.debug("is_bg_worker_alive: os.kill(%s, 0) raised %r -- falling back to log-mtime staleness", pid, exc)`. Do NOT change any return value or the mtime-staleness logic: the `OSError` path must still fall through to the existing `_STALE_LOG_SECONDS` comparison (fresh log -> `(True, pid)`, stale log -> `(False, pid)`). Breadcrumb text is ASCII only.
  - In `plugins/mill/unit_tests/test-bg-liveness.py`: add a `unittest.TestCase` method (e.g. `test_log_oserror_fallback_to_mtime`) that monkeypatches `_bg.os.kill` to raise `OSError(22, "Invalid parameter")` (a WinError-87-shaped error), writes a log with a `WORKER PID` line and NO `[mill-bg] EXIT` line, and asserts both branches of the fallback: (a) with a fresh mtime the result is `(True, pid)`; (b) with the mtime backdated past `_bg._STALE_LOG_SECONDS` the result is `(False, pid)`. Assert the debug breadcrumb is emitted using `self.assertLogs(_bg.__name__, level="DEBUG")` wrapping the fresh-mtime call (branch a) -- `assertLogs` raises if no record is captured within its scope, so wrap a call that is guaranteed to emit the breadcrumb (branch a needs no `utime` backdate, so it is the simplest). Restore `os.kill` after the test (e.g. `unittest.mock.patch.object`). Follow the existing `tempfile.TemporaryDirectory` + `os.utime` patterns already in the file.
- **Commit:** `fix(bg): log os.kill OSError fallback in is_bg_worker_alive (#364)`

### Card 2: #365 -- `millpy-bg.py` worker EXIT sentinel via try/finally + re-raise + dead-stub removal + test

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/millpy-bg.py` `_worker_main` (the worker fast-path function near the top, guarded by `if "--_worker" in sys.argv:`): restructure the `try/except Exception` around the child `subprocess.run` so the `[mill-bg] EXIT <code>` sentinel is written from a `finally` block, guaranteeing exactly one EXIT line on every exit path including `BaseException` (`SystemExit`/`KeyboardInterrupt`). `<code>` is the child `returncode` on success and `-1` on any failure. The `finally` must write the sentinel via an append-mode open (`open(log_path, "a", ...)`), because the `with open(log_path, "w") as log_f:` handle is already closed once control leaves the `with` block (including when `subprocess.run` raises inside it) -- this mirrors the existing `Exception`-path which already appends. Capture the success `returncode` into a variable before the `with` block closes; do NOT also write an EXIT line inside the `with` block, so exactly one EXIT line is produced on every path. Preserve the existing `[mill-bg] WORKER ERROR <repr>` line for the `Exception` case and the existing return values (`0` on success, `1` on caught `Exception`). A `BaseException` must run the `finally` (writing the sentinel) and then propagate (re-raise) out of `_worker_main` -- it must NOT be swallowed and must NOT be converted to a return. Keep the `START` sentinel as the first log line, keep child stdout/stderr captured to the log, and keep the `creationflags=CREATE_NO_WINDOW` argument unchanged.
  - In `plugins/mill/scripts/millpy-bg.py`: delete the dead stub `def _worker_main(...)` in the launcher section (the one whose body is only `raise RuntimeError("_worker_main is only available in worker mode")`). The worker fast-path `sys.exit`s before the launcher definitions load, so this stub is unreachable; confirm `main`/`_launcher_main` and the worker-mode loader still work after removal.
  - In `plugins/mill/unit_tests/test-millpy-bg.py`: add a worker-mode test (next sequential letter, e.g. `(p)`) that monkeypatches `subprocess.run` with `side_effect=KeyboardInterrupt` and invokes `_worker_main(["--log", <path>, "--", <cmd>])`. The call MUST be wrapped in `try/except BaseException` (e.g. `except KeyboardInterrupt`) before reading the log, because the worker re-raises and the file's hand-rolled per-test wrapper only catches `Exception` (an uncaught propagation would crash the runner). After catching, assert the log contains exactly one `[mill-bg] EXIT` line and that it is `[mill-bg] EXIT -1`. Keep existing tests `(i)`/`(j)`/`(o)` semantics intact (success code, non-zero code, and `Exception`-path `EXIT -1`). Follow the file's existing `failures.append(...)` / `print("PASS ...")` style.
  - After the restructure, the existing tests `(i)`, `(j)`, `(o)` must still pass unchanged.
- **Commit:** `fix(bg): always write EXIT sentinel via finally + re-raise BaseException (#365)`

### Card 3: #355 -- document Bash-tool-is-POSIX vs `Shell: PowerShell` metadata in repo `CLAUDE.md`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a short note to this repo's `CLAUDE.md` stating that the harness-reported `Shell: PowerShell` environment metadata is advisory and that the Bash tool always uses a POSIX shell regardless: emit POSIX syntax (`$null` no -- use `2>/dev/null`, `[ -f x ]`, `for x in ...`) in Bash tool calls, and reserve PowerShell syntax for the PowerShell tool. Place it under a short `## Environment` heading near the top of the file (the file currently opens with project shape and hard constraints and has no Environment section), or append it to `## Conventions` if that fits better. Keep the note tight (a few lines). ASCII only -- use ` -- ` and ` -> ` rather than Unicode dashes/arrows. Do NOT touch `~/.claude/CLAUDE.md` (out of scope) and do NOT file an upstream issue.
- **Commit:** `docs: note Bash tool is POSIX regardless of Shell metadata (#355)`

## Batch Tests

`verify:` runs the two affected unit-test files only, via `run-all.py --only test-bg-liveness.py test-millpy-bg.py` -- card 1 touches `test-bg-liveness.py` and card 2 touches `test-millpy-bg.py`; card 3 (`CLAUDE.md`) has no runnable surface. The scope is deliberately narrow (not the full ~77-file suite) because no cross-cutting helper is modified. `test-bg-liveness.py` covers the `_bg.py` OSError-fallback breadcrumb and both fresh/stale mtime branches; `test-millpy-bg.py` covers the worker EXIT sentinel on success, non-zero exit, caught `Exception`, and the new `BaseException` re-raise path. Card 3 is verified by human read of the `CLAUDE.md` note (present, accurate, ASCII-only).
