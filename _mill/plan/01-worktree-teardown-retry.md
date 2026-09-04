# Batch: worktree-teardown-retry

```yaml
task: 'millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting'
batch: worktree-teardown-retry
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py
depends-on: []
```

## Batch Scope

`_worktree.remove_safe`'s Windows WinError145 rmtree-fallback currently does exactly one
`dotnet build-server shutdown` + one retry (added in `07334bff`/`9cdd393f`) before giving up and
raising `WorktreeLockedError`. GitHub issues #929/#928/#918/#909 all report this teardown still
failing, and all 4 reports postdate that fix — one retry is empirically insufficient. This batch
strengthens the fallback to a bounded loop of up to 3 total `_safe_rmtree.safe_rmtree` attempts
(the original attempt plus 2 retries), each preceded by `dotnet build-server shutdown`, with a short
fixed backoff between attempts (0.5s after attempt 1, 1.5s after attempt 2). Applied generically
inside `remove_safe` itself (not a baseline-only wrapper) so every caller — baseline pre-flight,
mill-merge, mill-cleanup (including this task's own batch 2) — benefits. No public signature
changes; `remove_safe`'s external interface (`remove_safe(path, cwd, junctions_cfg, force=True) ->
None`, raising `WorktreeLockedError`/`WorktreeError`) is unchanged, so no other batch or existing
caller needs any edit.

## Cards

### Card 1: Bounded retry loop for the WinError145 rmtree fallback

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `import time` to `_worktree.py`'s existing import block (after `import subprocess`, before
  `import sys`, matching the existing alphabetical stdlib-import ordering).

  In `remove_safe`, the current WinError145 handling (inside the `except OSError as exc:` branch
  that follows the first `_safe_rmtree.safe_rmtree(path, allowed_root=path)` call at line ~330) is:

  ```python
            except OSError as exc:
                if not _is_dir_not_empty_error(exc):
                    raise
                # Windows: a lingering dotnet build-server lock inside a generated obj/
                # tree can leave the directory non-empty after junction-strip + rmtree.
                # Shut down the build-server node and retry once before giving up --
                # both #846/#859 report the race clearing itself by the time of a bare
                # manual re-invocation moments later.
                try:
                    subprocess.run(
                        ["dotnet", "build-server", "shutdown"],
                        capture_output=True,
                        timeout=30,
                    )
                except Exception:
                    pass
                try:
                    _safe_rmtree.safe_rmtree(path, allowed_root=path)
                except PermissionError as retry_exc:
                    raise WorktreeLockedError(
                        f"worktree is locked via rmtree fallback (path={path}): {retry_exc}"
                    ) from retry_exc
                except OSError as retry_exc:
                    raise WorktreeLockedError(
                        f"worktree is locked via rmtree fallback (path={path}): {retry_exc}"
                    ) from retry_exc
  ```

  Replace the single-retry body (everything from the first `try:` after the comment block through
  the final `except OSError as retry_exc:` block) with a bounded loop performing up to 2 further
  attempts (3 total rmtree attempts counting the original one at line ~330), each preceded by the
  same best-effort `dotnet build-server shutdown` call, with `time.sleep(0.5)` before the first
  retry and `time.sleep(1.5)` before the second retry. On the final (3rd) attempt, a
  `PermissionError` or `OSError` still raises `WorktreeLockedError` exactly as today (same message
  format: `f"worktree is locked via rmtree fallback (path={path}): {retry_exc}"`), preserving the
  existing exception chaining (`from retry_exc`). A non-WinError145 `OSError` on any retry attempt
  still re-raises unchanged (matching the existing `if not _is_dir_not_empty_error(exc): raise`
  guard on the first attempt — retries only continue looping on the same WinError145 condition, not
  on an unrelated OSError). Keep the existing explanatory comment (the `#846/#859` reference) at the
  top of the block, updated to note the loop now makes up to 2 retries rather than 1. The
  `subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30)` call and
  its own `except Exception: pass` swallow are unchanged in shape, just executed once per retry
  attempt inside the loop instead of once total.

  Do not change `_safe_rmtree.safe_rmtree`'s own signature or behavior, `_is_dir_not_empty_error`,
  or anything outside this one `except OSError as exc:` block. Do not change the first
  `_safe_rmtree.safe_rmtree(path, allowed_root=path)` call at line ~330 or its own
  `except PermissionError as exc:` branch immediately above this block — a `PermissionError` on the
  very first attempt still raises `WorktreeLockedError` immediately without entering the WinError145
  retry loop at all, exactly as today (only a WinError145 `OSError` on the first attempt enters the
  new loop).
- **Commit:** `fix(worktree): retry WinError145 rmtree fallback up to 3 times with backoff`

### Card 2: Unit tests for the strengthened retry loop

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add new test cases to `test-worktree.py` covering `remove_safe`'s strengthened WinError145 retry
  loop from Card 1. Follow this file's existing fixture/mocking conventions (read the file's current
  tests for `remove_safe`'s WinError145 fallback path before writing new ones, to match its exact
  mocking style — patching `_subprocess_util.run` for the `git worktree remove`/`prune` calls,
  `_safe_rmtree.safe_rmtree` for the rmtree attempts, and the module-level `subprocess.run` in
  `_worktree.py` for the `dotnet build-server shutdown` call).

  New cases:
  1. `_safe_rmtree.safe_rmtree` raises a WinError145-shaped `OSError` (`winerror=145` attribute, or a
     matching message when simulating on a non-Windows test host — mirror whatever pattern the
     existing WinError145 test in this file already uses) on its first two calls, then succeeds on
     the 3rd call. Assert `remove_safe` returns normally (no exception) and that the module-level
     `subprocess.run` mock (the `dotnet build-server shutdown` call) was invoked exactly twice — once
     before each of the two retries, matching "once per retry, not just once total".
  2. `_safe_rmtree.safe_rmtree` raises the same WinError145 `OSError` on all 3 calls. Assert
     `remove_safe` raises `WorktreeLockedError` (matching the existing message format
     `"worktree is locked via rmtree fallback (path=...)"`), and that the `dotnet build-server
     shutdown` mock was invoked exactly twice (once per retry — the first attempt at line ~330 does
     not call it).
  3. `_safe_rmtree.safe_rmtree` raises a non-WinError145 `OSError` on its first call (e.g. a plain
     `OSError("some other error")` with no `winerror` attribute and a message that does not match
     `_is_dir_not_empty_error`). Assert `remove_safe` re-raises that same `OSError` directly (not
     `WorktreeLockedError`) and that the retry loop / `dotnet build-server shutdown` mock was never
     invoked (0 calls) — confirming the non-WinError145 guard still short-circuits before the new
     loop, exactly as today's `if not _is_dir_not_empty_error(exc): raise` behavior.
  4. Assert `time.sleep` (patch `_worktree.time.sleep`) is called with `0.5` before the first retry
     and `1.5` before the second retry, in case 1 above (the two-failures-then-success case) —
     confirms the backoff schedule, not just the retry count.
- **Commit:** `test(worktree): cover the strengthened WinError145 retry loop`

## Batch Tests

`verify:` runs `test-worktree.py` directly (single file, matches this batch's sole edited module).
Card 2's new cases exercise `remove_safe`'s WinError145 fallback path — the exact code this batch
changes — via mocked `_subprocess_util.run`/`_safe_rmtree.safe_rmtree`/`subprocess.run`/`time.sleep`,
no real git worktree or Windows process involved.
