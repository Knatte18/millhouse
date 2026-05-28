# Discussion: Background worker + shell-metadata edge cases

```yaml
task: Background worker + shell-metadata edge cases
slug: bg-worker-and-shell-edge-cases
status: discussing
parent: main
```

## Problem

Three unrelated environmental edge cases in `millpy-bg`-mediated background work on Windows were grouped because each is ~1-file scope and they collectively cause flaky failures (GitHub issues #355, #364, #365). During exploration we discovered that **two of the three premises are stale**: the code has been hardened since the issues were filed (notably commit `f424c909` "guard exceptions + bare-exit" for `_bg.py` and the test-suite work in `dae67413`). The remaining work is therefore "verify-already-fixed + add targeted test coverage + small hardening + a docs note," not three from-scratch bug fixes.

**Why now:** the three issues are open and intermittently bite background-review flows on Windows. Closing the residual gaps removes the flakiness and the open issues, and documents a recurring shell-syntax footgun that wastes turns.

## Scope

**In:**

- `plugins/mill/scripts/_bg.py` — add a `logging.getLogger(__name__).debug(...)` breadcrumb on the `except OSError` mtime-fallback path (#364). No behavior change.
- `plugins/mill/scripts/millpy-bg.py` — restructure the worker's `try/except Exception` into a `try/…/finally` so the `[mill-bg] EXIT <code>` sentinel is always written, including on `BaseException` (`SystemExit` / `KeyboardInterrupt`); keep the existing `WORKER ERROR` line for the `Exception` case; remove the dead stub `_worker_main` at line 199 (#365).
- `plugins/mill/unit_tests/test-bg-liveness.py` — add a test that monkeypatches `os.kill` to raise `OSError` (WinError 87 / EINVAL) and asserts the mtime fallback path is taken and the debug breadcrumb is emitted (#364).
- `plugins/mill/unit_tests/test-millpy-bg.py` — add a worker test simulating a `BaseException` mid-run and asserting the EXIT sentinel is still written (#365).
- `CLAUDE.md` (this repo) — add a short note that the harness `Shell: PowerShell` env metadata is advisory; the Bash tool is always POSIX (#355).

**Out:**

- **No behavior change to `_bg.is_bg_worker_alive`.** We explicitly keep the mtime-staleness fallback. The proposal's literal text ("treat WinError 87 as alive=False") is rejected — see Decisions.
- **No SIGTERM / atexit handler** in the worker (rejected alternative for #365).
- **No upstream Anthropic issue** for the shell-metadata mismatch in this task (repo docs only).
- **No GitHub issue closure inside this task.** Issues #355/#364/#365 are closed through the normal merge flow, not by mill-go.
- No changes to the launcher path of `millpy-bg.py`, the detached-spawn mechanism, `_subprocess_util`, or the global `~/.claude/CLAUDE.md`.

## Decisions

### bg-364-keep-mtime-fallback-add-breadcrumb

- Decision: For #364, keep the existing `except OSError:` → mtime-staleness fallback in `_bg.is_bg_worker_alive` unchanged. Add a single `logging.getLogger(__name__).debug(...)` line inside the `except OSError` block recording that the kill-probe raised and the probe is falling back to mtime staleness (include the pid and the exception repr). Add a unit test that forces the `OSError` path via monkeypatch.
- Rationale: The premise that the helper "lets the exception propagate" is false — `_bg.py:45` already catches `OSError` and `test-bg-liveness.py` already exercises the fallback. The fallback is the *intended, safer* design: a transiently-erroring but genuinely-alive worker (fresh log) stays `alive=True`, and a dead worker is declared dead once its log goes stale (>5 min). The only real gap is observability (no breadcrumb) and an explicit WinError-87 test. A module-level logger at DEBUG is silent unless the caller configures logging, so it never pollutes orchestrator stdout/stderr (ASCII-only per repo convention).
- Rejected: (a) Changing to `(False, pid)` immediately on WinError 87 — this is the proposal's literal ask but it diverges from the tested design and risks false-negative re-fires (declaring a live worker dead → a duplicate worker is spawned). (b) Leaving `_bg.py` entirely untouched — loses the breadcrumb and the explicit regression test.

### bg-365-finally-sentinel-and-stub-removal

- Decision: For #365, convert the worker's `try/except Exception` (`millpy-bg.py:55-85`) into a `try/…/finally` structure that always writes exactly one `[mill-bg] EXIT <code>` sentinel: `<code>` is the child's `returncode` on success and `-1` on any failure. Preserve the existing `[mill-bg] WORKER ERROR <repr>` line for the `Exception` case (write it in an `except Exception` clause that still falls through to the `finally`). The `finally` guarantees the sentinel even on `BaseException` (`SystemExit`, `KeyboardInterrupt`). Remove the dead stub `_worker_main` at line 199 that only raises `RuntimeError`.
- Rationale: The current `except Exception` already writes `EXIT -1` (proven by test `(o)`), so `OSError`/`SubprocessError` — both `Exception` subclasses — are already covered; the issue's cited cases are satisfied. The genuine residual gap is `BaseException` coverage, which only a `finally` provides. The dead stub is unreachable in launcher mode (the worker fast-path `sys.exit`s before the launcher definitions load) and is confusing; removing it is safe.
- Rejected: (a) Keeping `except Exception` and only removing the stub — leaves the `BaseException` gap the proposal pointed at. (b) Adding a SIGTERM/`atexit` handler — a hard `taskkill /F` kills the process without running any Python, so no in-process handler can ever write the sentinel; that scenario is owned by #364's mtime fallback. Adding signal handling is complexity for a case it cannot actually cover.

### bg-355-repo-claude-md-note-only

- Decision: For #355, add a short note to **this repo's** `CLAUDE.md` Environment section stating that the harness-reported `Shell: PowerShell` env metadata is advisory: the Bash tool always uses POSIX shell regardless, so emit POSIX syntax in Bash tool calls and reserve PowerShell syntax for the PowerShell tool. No upstream Anthropic issue is filed in this task.
- Rationale: The mismatch is a documentation/disambiguation problem, not a code defect — there is nothing in this repo to "fix" in code. The global `~/.claude/CLAUDE.md` already covers the operator's machine, but the repo `CLAUDE.md` is read by every session in this project (including external-repo sessions that use the mill plugin), so the note belongs there. Upstream filing is out of scope and not actionable from this task.
- Rejected: (a) Repo note + upstream issue — upstream is out of scope. (b) Relying on the global `CLAUDE.md` only — leaves the repo's own session bootstrap silent on the footgun.

## Technical context

- **`plugins/mill/scripts/_bg.py`** — single function `is_bg_worker_alive(log_path) -> tuple[bool, int | None]`. Current control flow: missing log → `(False, None)`; no `WORKER PID` line → `(False, None)`; `[mill-bg] EXIT` present → `(False, pid)`; then `os.kill(pid, 0)` with `ProcessLookupError → (False, pid)`, `PermissionError → (True, pid)`, `except OSError: pass` → mtime fallback (`> _STALE_LOG_SECONDS` (300s) → `(False, pid)`, else `(True, pid)`). The breadcrumb goes inside the existing `except OSError` block; add `import logging` and a module-level `_logger = logging.getLogger(__name__)` (or call `logging.getLogger(__name__)` inline). Confirmed on this machine (Python 3.13.1) that `os.kill(pid, 0)` is non-destructive — `test_log_live_pid` calls it on `os.getpid()` and the process survives — so the probe is safe; no change to the kill call itself.
- **`plugins/mill/scripts/millpy-bg.py`** — worker fast-path is a top-of-file block guarded by `if "--_worker" in sys.argv:` (lines 27-94) that `sys.exit`s before the launcher code (lines 96+) is defined; the launcher's stub `_worker_main` (line 199) therefore never runs in worker mode. The worker writes the `START` sentinel first, runs `subprocess.run(cmd, stdout=log_f, stderr=STDOUT, creationflags=CREATE_NO_WINDOW)`, then `EXIT <returncode>`. Restructure must keep: START line first, child output captured, exactly one EXIT line last, `_worker_main` returning `0` on success and `1` on failure. The `exit_written` flag pattern can be replaced by computing the code once and writing it in `finally`.
- **Tests** — unit tests run via `uv run --project plugins/mill python plugins/mill/unit_tests/<file>.py` (or the suite via `run-all.py`); they self-insert `scripts/` on `sys.path`. `test-bg-liveness.py` is a `unittest.TestCase`; `test-millpy-bg.py` is a hand-rolled `main()` returning `0/1` with `PASS/FAIL` prints and loads the script twice (worker + launcher mode) via `_load_bg_module`. New tests follow the file's existing style. Existing relevant tests to not regress: `test_log_dead_pid_no_exit`, `test_log_live_pid` (bg-liveness); `(i)`, `(j)`, `(o)` (millpy-bg). Fixtures are in-memory/tempfile only — no real git/LLM.
- **`CLAUDE.md`** — top of file has an `## Environment`-style section is absent; the file opens with project shape and hard constraints. The note can go near the top under a short Environment heading or appended to the Conventions section. ASCII-only in any generated/edited markdown per repo convention.

## Constraints

- `print()` / log output must be ASCII only (Windows cp1252 crashes on non-ASCII stdout). The DEBUG breadcrumb text must use ASCII (` -- `, ` -> `).
- No new third-party dependencies; `logging` is stdlib.
- Worker fast-path must remain stdlib-only (no mill imports) — it runs before mill modules are importable. `logging` is stdlib so it is permissible if ever needed there, but the #365 change does not require new imports.
- Tests must not invoke real git or a real LLM (unit-test isolation rule).

## Testing

- **`_bg.py` (#364)** — TDD candidate. Add `test_log_oserror_fallback_to_mtime` (or similar) to `test-bg-liveness.py`: monkeypatch `_bg.os.kill` to raise `OSError(22, "Invalid parameter")` (or a `WinError 87`-shaped `OSError`), write a `WORKER PID` log with **no** EXIT line, and assert: (a) fresh mtime → `(True, pid)`; (b) backdated mtime (> `_STALE_LOG_SECONDS`) → `(False, pid)`. Optionally assert the debug breadcrumb is emitted using `assertLogs(_bg.__name__, level="DEBUG")`. This both documents the WinError-87 path and pins the no-behavior-change decision.
- **`millpy-bg.py` (#365)** — TDD candidate. Add a worker test to `test-millpy-bg.py` that forces a `BaseException` from the child-run step (e.g. monkeypatch `subprocess.run` with `side_effect=KeyboardInterrupt`) and asserts the log still contains a single `[mill-bg] EXIT` line (code `-1`). Keep existing tests `(i)`/`(j)`/`(o)` green to prove success-code, non-zero-code, and `Exception`-path sentinels are unchanged. Confirm the dead-stub removal does not break `_load_bg_module(worker_mode=False)` (the launcher still imports cleanly).
- **`CLAUDE.md` (#355)** — no automated test; verification is a human read that the note is present, accurate, and ASCII-only.
- **Suite regression** — run the full unit suite (`run-all.py`) to confirm no collateral breakage; both touched test files must pass.

## Q&A log

- **Q:** #364 says the helper lets the exception propagate, but the code already catches `OSError`. Change behavior to `alive=False` on WinError 87, or keep the mtime fallback? **A:** Keep the mtime fallback (no behavior change); add a debug breadcrumb on the fallback and an explicit WinError-87 test. The proposal's `alive=False` was rejected as risking false-negative re-fires.
- **Q:** #365's `try/finally` ask is already met by `except Exception` for the cited OSError/SubprocessError cases. What's the actual delta? **A:** Convert to `try/…/finally` for `BaseException` coverage too, keep the `WORKER ERROR` line, and remove the dead stub at line 199. SIGTERM/atexit handler rejected — a hard kill runs no Python and is covered by #364's mtime fallback.
- **Q:** Where does the #355 shell-metadata disambiguation go, and do we file upstream? **A:** A short note in this repo's `CLAUDE.md` only; no upstream Anthropic issue in this task.
- **Q:** Does "all 3 issues closed" mean mill-go closes the GitHub issues? **A:** No — this task lands code/tests/docs only; issue closure happens via the normal merge flow.
