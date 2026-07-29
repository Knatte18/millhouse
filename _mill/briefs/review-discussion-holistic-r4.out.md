MILL_REVIEW_BEGIN
# Review: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Widened `_junction.py` scandir guard's log text is ambiguous, may mislabel FileNotFoundError as "permission denied"
**Section:** Decisions > Guard placement; Technical context (`_junction.py` bullet)
**Issue:** Both spots say to widen `_walk`'s `except PermissionError:` (line 318, message `"[junction] WARNING: permission denied scanning {dir_path}; ..."`) to also catch `FileNotFoundError`, "same as the existing PermissionError branch's shape" / "the pattern to extend for FileNotFoundError too" — read literally this reuses the identical "permission denied" message text for a vanished-directory case, which is factually wrong and undermines the Logging decision's stated goal (accurate skip-and-log signal, not silent/misleading).
**Fix:** State explicitly whether the widened except keeps one combined clause with a shared generic message, or splits into `except PermissionError` / `except FileNotFoundError` with distinct wording (e.g. a `[junction]`-prefixed "vanished" message parallel to `_safe_rmtree`'s `skip vanished entry:` text).

### [NOTE] Testing section doesn't flag the context-manager vs plain-list `os.scandir` usage difference between the two walks
**Section:** Testing (Scenario 1/2 mocking guidance)
**Issue:** `_safe_rmtree._walk_strip_reparse_points` calls `os.scandir` via `with os.scandir(str(root)) as it:` (context-manager protocol), while `_junction.py`'s `_walk` calls it as `list(os.scandir(str(dir_path)))` (plain iterable) — the Testing section's "mock `os.scandir` ... following the same tempfile-based fixture pattern" advice doesn't note that a mock satisfying the `_junction.py` case (plain return value) won't satisfy `_safe_rmtree`'s `with` usage without also implementing `__enter__`/`__exit__`.
**Fix:** Add a one-line note that the two walks' `os.scandir` call shapes differ and the test mocks need to match each (context-manager stand-in for `_safe_rmtree`, plain iterable for `_junction.py`).

## Verdict

GAPS_FOUND
One GAP: ambiguous log-message wording for the widened `_junction.py` FileNotFoundError guard.
MILL_REVIEW_END
