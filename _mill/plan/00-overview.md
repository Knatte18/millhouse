# Plan: (A) — Subprocess handling: timeout + JSON-exit + Windows detach

```yaml
task: '(A) — Subprocess handling: timeout + JSON-exit + Windows detach'
slug: subprocess-fixes
approved: true
started: 20260513-081431
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: subprocess-util-windows-fixes
    file: 01-subprocess-util-windows-fixes.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-subprocess-util.py && python plugins/mill/integration_tests/test-subprocess-tree-kill.py
  - number: 2
    name: millpy-bg-start-sentinel
    file: 02-millpy-bg-start-sentinel.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/test-millpy-bg.py && python plugins/mill/integration_tests/test-millpy-bg-detached.py
  - number: 3
    name: session-id-propagation
    file: 03-session-id-propagation.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-implementer-common.py
```

## Shared Decisions

### Decision: ASCII-only print/log strings

- **Decision:** All new `print()` and stderr-log strings are ASCII only. Em-dash → ` -- `; right-arrow → ` -> `. Docstrings and comments are exempt from this rule. Sentinel strings written to log files MUST also be ASCII (downstream code may grep them in cp1252 environments).
- **Rationale:** Repo-wide constraint per `CLAUDE.md` `## Conventions worth carrying`. Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches.

### Decision: Public signatures unchanged

- **Decision:** No batch may change the public signature of `_subprocess_util.run`, `_subprocess_util.popen_detached`, or `_implementer_common._forward_output`. The session_id kwarg added to `_forward_output` is keyword-only with `default=None`, preserving backwards compatibility with every existing caller. The watchdog and two-stage launch are internal implementation changes only — argv, kwargs, return type, and exception types stay identical.
- **Rationale:** `_subprocess_util.run` has ~30+ call sites; `popen_detached` has fewer but `millpy-bg.py` is the only meaningful one. `_forward_output` has three call sites. Public-API changes ripple far beyond this task's scope.
- **Applies to:** all batches.

### Decision: POSIX behaviour preserved

- **Decision:** Every Windows-only code path is gated on `os.name == "nt"` inside the function body. The matching POSIX branch keeps its existing semantics (`communicate(timeout=...)` + `os.killpg(SIGKILL)` for `run`; `start_new_session=True` + no `creationflags` for `popen_detached`). Mock-based unit assertions in `test-subprocess-util.py` continue to verify the POSIX branch is unchanged.
- **Rationale:** The bugs are Windows-specific. POSIX subprocess primitives already give us the right kill semantics via process groups. Symmetrising the watchdog onto POSIX is risk without benefit.
- **Applies to:** batch 1, batch 2.

### Decision: TDD — write the red test before the production change

- **Decision:** Where a batch contains both a regression test for a documented bug and the production-code fix, the implementer writes the test FIRST, runs the test suite, confirms the new test fails against the un-fixed code, then implements the production change and confirms the suite passes. The implementer-brief.md skill already encodes this; the plan calls it out per-card so the implementer cannot mistake the order.
- **Rationale:** Red-then-green proves the test would have caught the regression. A test added alongside the fix without a red-state assertion is a coverage afterthought, not a regression guard.
- **Applies to:** batch 1 (card 1, card 3), batch 2 (card 5, card 6).

### Decision: Integration tests are Windows-only and chained into `verify:`

- **Decision:** New files under `plugins/mill/integration_tests/` are Windows-only and ARE chained into their batch's `verify:` command via `&&`. They open with a clear `if os.name != "nt": print("SKIP <name>: Windows-only"); sys.exit(0)` guard. On POSIX they exit 0 immediately (no-op chain link); on Windows they execute end-to-end. This closes the regression-coverage gap for Windows operators running `verify:` locally while keeping POSIX CI runs fast. `verify:` is a single shell command; the chain syntax `cmd-a && cmd-b` is portable across cmd.exe, PowerShell, and bash.
- **Rationale:** Excluding the integration tests from `verify:` was rejected on review as creating a regression-coverage gap. The skip-guard pattern (`if os.name != "nt": sys.exit(0)`) gives us automatic POSIX no-op behaviour, so the only cost on POSIX is a Python interpreter spin-up. On Windows, the tests are the only place the cross-process kill-tree and cross-job detach are exercised end-to-end; running them as part of `verify:` is what we want.
- **Applies to:** batch 1, batch 2.

### Decision: Shared `_subprocess_util` module constant — `_GRACE_SECONDS`

- **Decision:** The new Windows watchdog reuses the existing `_GRACE_SECONDS = 5` module-level constant for its post-kill `proc.wait(timeout=_GRACE_SECONDS)` step. No new module-level constants are introduced; if a magic number is needed, name it inline at function scope.
- **Rationale:** The constant already exists for the exact purpose (grace period between terminate and force-kill). Reusing it keeps the module's tunables in one place.
- **Applies to:** batch 1.

## All Files Touched

- `plugins/mill/integration_tests/test-millpy-bg-detached.py`
- `plugins/mill/integration_tests/test-subprocess-tree-kill.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-subprocess-util.py`
