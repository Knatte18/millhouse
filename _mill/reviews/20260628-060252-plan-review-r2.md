I have enough to produce the review. Let me compile findings.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-28
```

## Findings

### [BLOCKING] Card 4 test is tautological -- no #553 regression guard
**Location:** Batch 1 / Card 4
**Issue:** The prescribed test calls `_paths.resolve_task_path(hub_dir, "_mill/briefs/")` directly with `hub_dir` hardcoded and asserts the result is under `hub_dir` -- that is always true regardless of the fix, since `resolve_task_path` returns `worktree_root / cfg_relative_path` (`_paths.py:535`). The test never invokes the CLI prepare branch, so reverting Card 3 (back to `git_root`) does NOT break it. This contradicts the card's own requirement ("a reversion of the fix must break this assertion").
**Fix:** Mandate the CLI-exercising path: load the hyphenated module via `importlib.util.spec_from_file_location`, patch `resolve_hub_path`/`resolve_git_root` so `hub_dir != git_root`, run the prepare branch, and assert the written `brief_path` is under `hub_dir` and not under `git_root/_mill`. Drop the direct-`resolve_task_path` alternative.

### [NIT] Card 5 dotnet cleanup placed inside verify try/except
**Location:** Batch 2 / Card 5 (Change 1)
**Issue:** The `dotnet build-server shutdown` call (with `timeout=30`) is inserted between `result = subprocess.run(...)` and `if result.returncode != 0:`, both inside the try block (`_implementer_common.py:375-403`). If shutdown raises (`TimeoutExpired`/`FileNotFoundError`), the surrounding `except Exception` returns a stuck dict ("verify gate raised"), turning a passing verify into a false stuck -- contradicting the "non-fatal best-effort" Shared Decision.
**Fix:** Wrap the shutdown in its own `try/except Exception: pass`, or place it after the verify try block, so a cleanup failure can never affect the verify verdict.

## Verdict

REQUEST_CHANGES
Card 4's test cannot catch the #553 regression it exists to guard.
MILL_REVIEW_END
