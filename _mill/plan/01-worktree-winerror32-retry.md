# Batch: worktree-winerror32-retry

```yaml
task: "millpy-implement.py / _done_gate.py: Windows baseline teardown, truncated failure reason, ignored --start-sha"
batch: worktree-winerror32-retry
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py
depends-on: []
```

## Batch Scope

Fixes GitHub #1032: `_worktree.remove_safe`'s existing WinError-145 ("directory not empty") retry-with-backoff loop does not also cover WinError 32 ("the process cannot access the file because it is being used by another process" — a Windows sharing violation), because Python surfaces WinError 32 as a `PermissionError`, and `remove_safe`'s current exception handling catches `PermissionError` in a separate `except` clause that raises `WorktreeLockedError` immediately, before the WinError-145-only retry loop ever gets a chance to run — even mid-retry-sequence. This batch generalizes the existing retry loop to also catch WinError 32, reusing its already-proven backoff + `dotnet build-server shutdown` mechanism (originally added for #846/#859/#929/#928/#918/#909) rather than inventing a second one. No external interface changes — this is an internal exception-handling fix inside one function.

## Cards

### Card 1: Retry WinError 32 sharing-violation teardown like WinError 145

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Add a new module-level function `_is_sharing_violation_error(exc: OSError) -> bool` immediately after the existing `_is_dir_not_empty_error` function (currently ending at line 242 of `_worktree.py`), with the identical matching shape: `winerror = getattr(exc, "winerror", None)`; if `winerror is not None`, return `winerror == 32`; otherwise return `"being used by another process" in str(exc).lower()`. Docstring mirrors `_is_dir_not_empty_error`'s own (matches on the numeric `winerror` attribute when present; locale-independent; falls back to a lowercase substring check only when `winerror` is absent, e.g. a test double or non-Windows `OSError`).
  2. Add a new module-level function `_is_retryable_lock_error(exc: OSError) -> bool` immediately after `_is_sharing_violation_error`, returning `_is_dir_not_empty_error(exc) or _is_sharing_violation_error(exc)`. Docstring: true if `exc` matches either of the two known transient Windows file-lock signatures `remove_safe`'s rmtree-fallback retries with backoff — WinError 145 (directory not empty) or WinError 32 (sharing violation, e.g. a lingering dotnet testhost/MSBuild file handle left over from a `--stage baseline` verify run, GitHub #1032).
  3. In `remove_safe`'s rmtree-fallback block, the current initial `try: _safe_rmtree.safe_rmtree(path, allowed_root=path)` has two `except` clauses: `except PermissionError as exc: raise WorktreeLockedError(f"worktree is locked via rmtree fallback (path={path}): {exc}") from exc` followed by `except OSError as exc: if not _is_dir_not_empty_error(exc): raise` (then the retry loop body). Replace both with a single `except OSError as exc:` clause that opens with: `if not _is_retryable_lock_error(exc):` — inside that block, `if isinstance(exc, PermissionError): raise WorktreeLockedError(f"worktree is locked via rmtree fallback (path={path}): {exc}") from exc` else `raise` (bare re-raise). When `_is_retryable_lock_error(exc)` is True (the `if not ...` condition is False), fall through unchanged into the existing `_retry_backoffs = (0.5, 1.5)` retry loop — do not alter that loop's backoff values, attempt count, or the `dotnet build-server shutdown` subprocess call.
  4. Apply the identical restructure inside that same retry loop's per-attempt exception handling. The current per-attempt `try: _safe_rmtree.safe_rmtree(path, allowed_root=path); break` has `except PermissionError as retry_exc: raise WorktreeLockedError(f"worktree is locked via rmtree fallback (path={path}): {retry_exc}") from retry_exc` followed by `except OSError as retry_exc: if not _is_dir_not_empty_error(retry_exc): raise; if not _is_final_attempt: continue; raise WorktreeLockedError(f"worktree is locked via rmtree fallback (path={path}): {retry_exc}") from retry_exc`. Replace both with a single `except OSError as retry_exc:` clause: `if not _is_retryable_lock_error(retry_exc):` — `if isinstance(retry_exc, PermissionError): raise WorktreeLockedError(f"worktree is locked via rmtree fallback (path={path}): {retry_exc}") from retry_exc` else `raise`. When `_is_retryable_lock_error(retry_exc)` is True, keep the existing `if not _is_final_attempt: continue` / else `raise WorktreeLockedError(f"worktree is locked via rmtree fallback (path={path}): {retry_exc}") from retry_exc` unchanged.
  5. Update the retry loop's existing inline comment (currently: "Windows: a lingering dotnet build-server lock inside a generated obj/ tree can leave the directory non-empty after junction-strip + rmtree. Shut down the build-server node and retry, up to 2 more times (3 rmtree attempts total), before giving up -- #846/#859/#929/#928/#918/#909 all report the race clearing itself by the time of a bare manual re-invocation moments later, and a single retry proved insufficient.") to also describe the WinError-32 case (a lingering dotnet testhost/MSBuild file lock on a specific build-output file, not just a non-empty directory) and cite #1032, per `_mill/discussion.md`'s "winerror-32-retry" Decision.
  6. Do not change `run_preflight`, `run_gate`, `remove`, `create`, `move`, `copy_millhouse`, `list_worktrees`, `processes_holding_path`, or `kill_stale_holders` — this fix is confined to `remove_safe`'s rmtree-fallback exception handling.
- **Commit:** `fix(worktree): retry WinError 32 sharing-violation teardown like WinError 145 (#1032)`

### Card 2: Cover WinError 32 retry-then-succeed and retry-exhausted paths

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Add two new test blocks to `main()` in `test-worktree.py`, placed immediately after the existing "remove_safe raises WorktreeLockedError after exhausting all 3 attempts on WinError 145" block and before "remove_safe re-raises a non-145 OSError from a retry attempt unchanged" (the block with `plain_exc = OSError("some other error")`). Both new blocks follow the exact same structure already used by the WinError-145 blocks immediately above them: a `tempfile.TemporaryDirectory()`, `path`/`cwd` setup, a `mock_result` with `returncode = 1` and `stderr = "Directory not empty"` (the exact `stderr` text does not matter to which retry path fires — that is now determined solely by the mocked `_safe_rmtree.shutil.rmtree` side_effect exceptions, not by the git subprocess's stderr text), `_worktree._subprocess_util.run` patched to return that `mock_result`, `_safe_rmtree._blacklist_for` patched to `[]`, and `_worktree.kill_stale_holders` patched.
     - **WinError-32 retry-then-succeed:** build `lock_exc = OSError("[WinError 32] The process cannot access the file because it is being used by another process")` with `lock_exc.winerror = 32` set as an attribute, patch `_safe_rmtree.shutil.rmtree` with `side_effect=[lock_exc, None]` (captured as `mock_rmtree`), patch `_worktree.subprocess.run` to return a bare `MagicMock()` (captured as `mock_dotnet_run`), call `remove_safe(path, cwd=cwd, junctions_cfg={})` with no exception expected, then assert `mock_rmtree.call_count == 2`, `mock_dotnet_run.call_count == 1`, and `mock_dotnet_run.call_args.args[0] == ["dotnet", "build-server", "shutdown"]` — this exactly mirrors the existing "remove_safe retries safe_rmtree once after WinError 145 and succeeds" block, substituting a WinError-32 exception for the WinError-145 one. Print `"PASS: remove_safe retries safe_rmtree once after WinError 32 and succeeds"` on success.
     - **WinError-32 retry-exhausted:** build three separate `OSError` instances, each with its own `.winerror = 32` attribute set, `side_effect=[exc1, exc2, exc3]` on the patched `_safe_rmtree.shutil.rmtree` (captured as `mock_rmtree`), patch `_worktree.subprocess.run` to return a `MagicMock()`, call `remove_safe(...)` inside a `try`/`except WorktreeLockedError` capturing a `raised_locked` boolean, then assert `raised_locked` is `True`, `mock_rmtree.call_count == 3` — this exactly mirrors the existing "remove_safe raises WorktreeLockedError after exhausting all 3 attempts on WinError 145" block, substituting winerror 32 for winerror 145. Print `"PASS: remove_safe raises WorktreeLockedError after exhausting all 3 attempts on WinError 32"` on success.
  2. Wrap each new block in the file's existing `try:`/`except AssertionError as exc: print(f"FAIL: ...", file=sys.stderr); errors += 1` pattern used by every other block in this file's `main()`, incrementing the same `errors` accumulator so a failure here is counted toward the file's final exit code.
  3. Do not modify the existing "remove_safe raises WorktreeLockedError when shutil.rmtree raises PermissionError (long-path fallback)" test (the one using `PermissionError("locked")` with no `winerror` attribute and no matching substring text) — it must continue to pass completely unmodified. That test's continued, unmodified pass is itself the regression guard for the "an unidentified `PermissionError` signature still fails immediately, with no retry loop entered" contract this card's Card-1 fix depends on: that test never mocks `_worktree.subprocess.run`, so if the restructured code in Card 1 incorrectly routed a non-matching `PermissionError` into the retry loop, the test would attempt a real, unmocked `subprocess.run(["dotnet", ...])` call and fail or hang rather than passing cleanly.
  4. Do not modify any of the other existing WinError-145 test blocks (retry-then-succeed, retry-exhausted-after-3, retries-twice-succeeds-on-3rd, backoff-timing, non-145-OSError-propagates-from-retry, non-145-OSError-propagates-from-first-attempt) — all must continue passing unchanged, since Card 1's restructure preserves their exact behavior (only the exception-matching predicate changed from `_is_dir_not_empty_error` alone to `_is_retryable_lock_error`, which is a strict superset for the WinError-145 case).
- **Commit:** `test(worktree): cover WinError 32 retry-then-succeed and retry-exhausted paths (#1032)`

## Batch Tests

`verify:` runs `test-worktree.py` in full (a single, already-scoped file covering every `_worktree.py` function, including both the pre-existing WinError-145 coverage and this batch's new WinError-32 coverage) — no `--only` narrowing needed since the whole file already targets exactly the module this batch edits.
