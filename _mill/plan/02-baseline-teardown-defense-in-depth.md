# Batch: baseline-teardown-defense-in-depth

```yaml
task: "mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages"
batch: baseline-teardown-defense-in-depth
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py test-millpy-implement.py
depends-on: []
```

## Batch Scope

Fixes the baseline-stage `WinError 145` ("directory is not empty") crash (GitHub #846, #859) at
two layers, per the discussion's `baseline-teardown-defense-in-depth` decision: (a)
`_worktree.remove_safe`'s rmtree fallback retries once after a best-effort `dotnet build-server
shutdown` when `_safe_rmtree.safe_rmtree` raises an `OSError` matching WinError 145, and (b)
`millpy-implement.py`'s `_run_baseline_stage` wraps both of its `remove_safe` call sites in a
generic `try/except Exception` so ANY exception surviving (a) is logged to stderr and swallowed,
never crashing the process -- restoring the function's own documented "never raises" contract.
Layer (a) benefits every `remove_safe` caller (also `mill-merge`/`mill-cleanup`), not just
baseline. Layer (b) is the hard backstop for when the retry is exhausted or a wholly different
exception occurs. No other batch depends on this one; it is fully independent of batch 1's
verify-gate fix.

## Cards

### Card 3: Retry `_safe_rmtree.safe_rmtree` once on WinError 145 before raising

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `import subprocess` to the existing import block at the top of the file (alongside the
  existing `import shutil` / `import sys` lines) -- `_worktree.py` currently has no `subprocess`
  import; every git invocation in this file goes through `_subprocess_util.run`, but the new
  `dotnet build-server shutdown` call is a direct, best-effort `subprocess.run` call exactly
  mirroring the existing shutdown call already present in `_implementer_common._run_verify_gate`.

  Add a new module-level helper immediately before `def remove_safe(`:

  ```python
  def _is_dir_not_empty_error(exc: OSError) -> bool:
      """
      True if exc is a Windows "directory not empty" (WinError 145) error.

      Matches on the numeric winerror attribute when present (locale-independent, unlike matching
      the OS message text). Falls back to a lowercase substring check on str(exc) only when
      winerror is absent (e.g. a test double or a non-Windows OSError).

      Args:
          exc: The OSError raised by shutil.rmtree (via _safe_rmtree.safe_rmtree).

      Returns:
          True if exc represents a WinError 145 (or a string-matching equivalent);
          False otherwise.
      """
      winerror = getattr(exc, "winerror", None)
      if winerror is not None:
          return winerror == 145
      return "directory is not empty" in str(exc).lower()
  ```

  In `remove_safe`, replace this exact block (currently at lines 304-310):

  ```python
        if path.exists():
            try:
                _safe_rmtree.safe_rmtree(path, allowed_root=path)
            except PermissionError as exc:
                raise WorktreeLockedError(
                    f"worktree is locked via rmtree fallback (path={path}): {exc}"
                ) from exc
  ```

  with:

  ```python
          if path.exists():
              try:
                  _safe_rmtree.safe_rmtree(path, allowed_root=path)
              except PermissionError as exc:
                  raise WorktreeLockedError(
                      f"worktree is locked via rmtree fallback (path={path}): {exc}"
                  ) from exc
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

  `except PermissionError` must stay listed before `except OSError` in both the outer and the
  retry's inner try/except -- `PermissionError` is a subclass of `OSError`, so Python matches the
  first textually-listed clause that fits, and a general `OSError` clause listed first would
  swallow the existing `PermissionError` -> `WorktreeLockedError` case this task must not change.
  The shutdown call is unconditional and best-effort with no `sys.platform` gate (`_worktree.py`
  has no existing platform branching to follow, and `winerror`/the "directory is not empty" string
  only realistically appear from a Windows-shaped `OSError` or an explicit test double) and no
  pre-check for whether the removed tree actually contains a dotnet project -- matching the
  discussion's `baseline-shutdown-unconditional` decision.

  Also update `remove_safe`'s own docstring "Sequence:" step 4 (currently: "If git fails with a
  long-path error ... fall back to `_safe_rmtree.safe_rmtree` — safe NOW because junctions are
  already gone.") to append one sentence: "On Windows, an `OSError` matching WinError 145
  (directory not empty, typically a lingering dotnet build-server lock) triggers one
  shutdown-and-retry before raising `WorktreeLockedError`."
- **Commit:** `fix(worktree): retry safe_rmtree fallback once on WinError 145 before raising (#846, #859)`

### Card 4: Never let `_run_baseline_stage`'s teardown crash the stage

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `_run_baseline_stage` has two `_worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})`
  call sites, neither currently wrapped in a `try`/`except`. Wrap each independently -- do not
  factor them into a shared helper, since one sits inside an `except Exception as e:` block's
  early-return path and the other sits inside a bare `finally:` block, and collapsing them would
  obscure which path fired in the printed stderr message.

  Site 1 -- the shared-checkout-failure early return (currently):

  ```python
        if tmp_path is not None:
            _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})
        return 0
  ```

  becomes:

  ```python
          if tmp_path is not None:
              try:
                  _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})
              except Exception as teardown_exc:
                  print(
                      f"[millpy-implement] baseline teardown failed (checkout-failure path): {teardown_exc}",
                      file=sys.stderr,
                  )
          return 0
  ```

  Site 2 -- the `finally` block after both module-wide and per-batch computation (currently):

  ```python
    finally:
        _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})
  ```

  becomes:

  ```python
      finally:
          try:
              _worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})
          except Exception as teardown_exc:
              print(f"[millpy-implement] baseline teardown failed: {teardown_exc}", file=sys.stderr)
  ```

  Both `except` clauses deliberately catch bare `Exception`, not `WorktreeError`/`WorktreeLockedError`
  -- `_run_baseline_stage`'s own docstring already promises "Never raises -- every failure path
  prints a JSON line describing the outcome and returns 0" as an unconditional promise, not one
  scoped to worktree-teardown exceptions alone, so a narrower `except` clause would still leave the
  docstring's contract overstated. This never changes the function's two printed JSON summary
  lines (module-wide, then per-batch) -- both still print exactly as before in every case, since
  neither call site's teardown outcome feeds into either JSON payload.

  Also append one sentence to `_run_baseline_stage`'s own docstring, immediately after the existing
  "Never raises -- every failure path prints a JSON line describing the outcome and returns 0."
  sentence: "Both `_worktree.remove_safe` teardown call sites are themselves wrapped in
  `try`/`except Exception` so a teardown failure (e.g. a still-locked dotnet build-server file) is
  logged to stderr and never propagates past this function."
- **Commit:** `fix(millpy-implement): swallow baseline-stage teardown failures instead of crashing (#846, #859)`

### Card 5: Test coverage for the `remove_safe` WinError 145 retry

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add three new test blocks to `test-worktree.py`, immediately after the existing
  `# --- remove_safe raises WorktreeLockedError when shutil.rmtree raises PermissionError
  (long-path fallback) ---` block (which ends at the `print("PASS: remove_safe raises
  WorktreeLockedError when rmtree fallback raises PermissionError")` line), matching that block's
  exact structure: `patch("_worktree._subprocess_util.run", return_value=mock_result)` for the git
  layer (with `mock_result.stderr = "Directory not empty"`, an existing `_rmtree_fallback_patterns`
  entry, so the fallback path is entered), `patch("_safe_rmtree.shutil.rmtree", side_effect=[...])`
  for the rmtree layer, `patch("_safe_rmtree._blacklist_for", return_value=[])`, and
  `patch("_worktree.kill_stale_holders")`. Each new block additionally needs
  `patch("_worktree.subprocess.run", return_value=<a MagicMock>)` (as another `with` context) for
  the new `dotnet build-server shutdown` call Card 3 adds -- capture that patch's context-manager
  return value so call counts can be asserted.

  - **Retry succeeds:** an `OSError` with `.winerror = 145` set on a first `shutil.rmtree` call,
    then `None` (success) on the second, via `side_effect=[lock_exc, None]` where `lock_exc =
    OSError("[WinError 145] The directory is not empty")` followed by `lock_exc.winerror = 145`
    set as a separate statement (the `OSError` constructor does not accept a `winerror=` keyword
    on non-Windows Python). Capture the `shutil.rmtree` patch as `mock_rmtree` and the
    `subprocess.run` patch as `mock_dotnet_run`. Call `remove_safe(path, cwd=cwd, junctions_cfg={})`
    with no exception expected. Assert `mock_rmtree.call_count == 2`. Assert
    `mock_dotnet_run.call_count == 1` and
    `mock_dotnet_run.call_args.args[0] == ["dotnet", "build-server", "shutdown"]`. Print
    `"PASS: remove_safe retries safe_rmtree once after WinError 145 and succeeds"`.
  - **Retry also raises WinError 145:** `side_effect=[lock_exc_1, lock_exc_2]`, both constructed
    the same way as above (two distinct `OSError` instances, each with `.winerror = 145` set).
    Assert `remove_safe(...)` raises `WorktreeLockedError` (catch it in a `try`/`except
    WorktreeLockedError:` block exactly like the existing `PermissionError` fallback test above
    it). Assert the captured `mock_rmtree.call_count == 2` (exactly one retry, not more). Print
    `"PASS: remove_safe raises WorktreeLockedError when retry also raises WinError 145"`.
  - **Non-145 OSError is not retried:** `plain_exc = OSError("some other rmtree failure")` (no
    `.winerror` attribute set at all). `side_effect=plain_exc` (single exception, not a list --
    `remove_safe` must never call `shutil.rmtree` a second time here). Wrap the `remove_safe(...)`
    call in `try: ... except OSError as exc: raised = True; assert exc is plain_exc, "expected the
    original OSError instance to propagate unchanged"`. Assert `raised` is `True` after the
    `with` block exits -- the plain `OSError` must propagate uncaught past `remove_safe` exactly as
    it did before this task (neither wrapped into `WorktreeError`/`WorktreeLockedError` nor
    retried). Print `"PASS: remove_safe re-raises a non-145 OSError from rmtree fallback unchanged
    (no retry)"`.

  Every new `assert` failure message must state what was expected, matching the file's existing
  convention throughout (every existing `assert` in this file carries a message).
- **Commit:** `test(worktree): cover remove_safe WinError 145 shutdown-and-retry (#846, #859)`

### Card 6: Regression test -- `_run_baseline_stage` never raises when teardown is exhausted

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add two new test methods to `TestMillpyImplement` (the `unittest.TestCase` class already
  containing `test_baseline_stage_shared_checkout_failure_module_wide_also_errored` and
  `test_baseline_stage_enumerates_batch_own_verify_despite_later_deletes`), inserted between those
  two existing methods, each calling `self._write_two_batch_fixture()` first exactly like its
  neighbors:

  - **`test_baseline_stage_finally_teardown_failure_never_raises`** -- exercises Card 4's Site 2
    (the `finally`-block call site). Patch, as a combined `with (...)` block mirroring
    `test_baseline_stage_per_batch_failure_isolation`'s own patch set:
    `millpy_implement._parent_branch.resolve` (`return_value="main"`),
    `millpy_implement._verify_baseline._checkout_parent_branch`
    (`return_value=self.tmp_path / "checkout"`), `millpy_implement._verify_baseline._link_dependency_dirs`
    (no side effect -- succeeds), `millpy_implement._worktree.remove_safe` (`side_effect=millpy_implement._worktree.WorktreeLockedError("still locked")`),
    and `millpy_implement._verify_baseline.compute_batch_baselines`
    (`return_value={"batch-a": [], "batch-b": []}` -- a flat `return_value` is sufficient here,
    unlike `test_baseline_stage_per_batch_failure_isolation`'s own `_side_effect` function above it,
    because both batches get the identical outcome in this test, so there is no need to branch on
    which batch name was passed). Call `rc, out = self._run_main(["--stage", "baseline"])`. Assert
    `rc == 0`. Assert `out.strip().splitlines()` has exactly 2 lines. Parse both as JSON and assert
    the first has `"substage": "module_wide"` and the second has `"substage": "per_batch"` with
    `"computed": ["batch-a", "batch-b"]` -- proving the function returned normally with both
    summary lines printed despite `remove_safe` raising `WorktreeLockedError` from inside the
    `finally` block.
  - **`test_baseline_stage_checkout_failure_teardown_failure_never_raises`** -- exercises Card 4's
    Site 1 (the shared-checkout-failure early-return path). Patch
    `millpy_implement._parent_branch.resolve` (`return_value="main"`),
    `millpy_implement._verify_baseline._checkout_parent_branch`
    (`return_value=self.tmp_path / "checkout"`), `millpy_implement._verify_baseline._link_dependency_dirs`
    (`side_effect=RuntimeError("link failed")` -- this is what drives execution into the
    shared-checkout-failure `except` branch with `tmp_path` already set, landing on Site 1, not
    Site 2), and `millpy_implement._worktree.remove_safe`
    (`side_effect=millpy_implement._worktree.WorktreeLockedError("still locked")`). Call
    `rc, out = self._run_main(["--stage", "baseline"])`. Assert `rc == 0`. Assert
    `out.strip().splitlines()` has exactly 2 lines, both parse as JSON, and the second has
    `"substage": "per_batch"` with both `"batch-a"` and `"batch-b"` present in `"errored"` --
    proving the function returned normally despite `remove_safe` raising from Site 1.

  Both tests directly exercise the "Never raises" contract `_run_baseline_stage`'s docstring
  already claims (and Card 4 restates more precisely) -- neither test should need a `try`/`except`
  around `self._run_main(...)` itself, since a bare exception escaping `_run_main` (rather than
  being caught internally and turned into `rc != 0`) would already fail the test via an unhandled
  exception in the test method, which is the desired failure mode if this regression reappears.
- **Commit:** `test(millpy-implement): regression -- baseline stage never raises when teardown is exhausted (#846, #859)`

## Batch Tests

`verify:` scopes to `test-worktree.py` (Card 5's new coverage plus the whole file's existing
`remove_safe` suite) and `test-millpy-implement.py` (Card 6's new coverage plus the whole file's
existing `_run_baseline_stage` suite) via `run-all.py --only`, since Cards 3-4 touch
`_worktree.remove_safe` (shared beyond baseline -- also used by `mill-merge`/`mill-cleanup`
worktree teardown, but those callers have no dedicated test file of their own to add to this
batch's scope; `test-worktree.py`'s own `remove_safe` suite is the correct and only test surface
for that shared helper) and `millpy-implement.py`'s baseline stage respectively.
