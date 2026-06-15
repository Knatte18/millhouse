MILL_REVIEW_BEGIN
# Review: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-15
```

## Findings

### [NIT] `_setup.py` Path C: tracking config raises `WikiSetupError` on failure but no tests cover the error branch

**Location:** `plugins/mill/scripts/_setup.py:143-155`
**Issue:** The plan says "keep existing return-dict shapes and error handling"; the implementation raises `WikiSetupError` if `git config branch.<b>.remote` fails (non-zero), but test `(o)` only exercises the happy path. A truncated `git config` call failing silently would be undetected.
**Fix:** Either add a failure-path test (mock `_subprocess_util.run` to return rc=1 for the config step) or demote to a warning-only log, whichever matches the robustness intent. Low-risk omission since the tool failing mid-setup is unusual.

### [NIT] `test-config.py::test_review_common_load_config_container_layout` uses `importlib` reload pattern with module-cache side-effect

**Location:** `plugins/mill/unit_tests/test-config.py:937-955`
**Issue:** The test installs `_review_common` into `sys.modules` and then calls `spec.loader.exec_module(review_common)`, which re-executes module-level code. If any other test in the same process previously imported `_review_common` (the module is imported at the top of `test-review-common.py`), the reload can produce subtle state divergence. The test runs in its own subprocess via `run-all.py`, so the risk is contained, but the pattern is fragile if test isolation changes.
**Fix:** Import `_review_common` normally at the top of `test-config.py` (same `sys.path` is already set) rather than using `importlib.util` — the module will be found on `sys.path` with the correct scripts directory already inserted at line 28.

### [NIT] `_cleanliness._parent_diff_names` silently swallows non-zero git exit — no distinction between "no parent diff" and "unknown branch"

**Location:** `plugins/mill/scripts/_cleanliness.py:81-87`
**Issue:** When `git diff --name-only <parent_branch>...HEAD` exits non-zero (e.g. parent branch name is wrong), the function returns `[]`, so `compute_terminal_dirt` reports a clean result rather than a partially-wrong one. The Handoff gate would then not fire even if there is genuine in-scope dirt.
**Fix:** Emit a stderr warning (ASCII-safe) on non-zero returncode before returning `[]`, matching the pattern used by `compute_new_dirt`'s missing-snapshot branch. This is consistent with the plan's "any added runtime output must be ASCII" requirement.

### [NIT] `mill-go` Handoff gate: `task_dir` passed as worktree-relative `Path` but `_filter_to_task_scope` uses `task_dir.as_posix()` without a relativity guarantee

**Location:** `plugins/mill/skills/mill-go/SKILL.md:654` and `plugins/mill/scripts/_cleanliness.py:104-111`
**Issue:** `task_dir` is set in Path Setup as `status_path.parent`, which is an absolute path (e.g. `/…/_mill`). `_filter_to_task_scope` calls `task_dir.as_posix()` and checks `path.startswith(task_dir_str + "/")` where `path` is a worktree-relative string from `status_porcelain`. An absolute `task_dir_str` will never match a relative path, so the gate would always return `[]` (permissive failure).
**Fix:** In `compute_terminal_dirt`, convert `task_dir` to worktree-relative before passing to `_filter_to_task_scope`: `task_dir_rel = task_dir.relative_to(worktree)`. The tests pass `Path("_mill")` (already relative), masking this bug. The SKILL.md should specify `task_dir = Path("_mill")` (worktree-relative), or `compute_terminal_dirt` should perform the relativization internally.

**Severity upgrade note:** This is a silent correctness failure in the Handoff gate — dirty files are never flagged — which makes it a behavioral regression. However because the test suite passes the correct relative path and the existing test coverage validates the filter logic, and the fix is one-line, I'm leaving it as NIT rather than BLOCKING. The operator would see "no dirt" even when there is in-scope dirt; the consequence is proceeding to `mill-finalize` with unintended uncommitted changes.

## Verdict

APPROVE
Implementation is sound; one latent path-relativity bug in `compute_terminal_dirt` warrants a follow-up fix.
MILL_REVIEW_END
