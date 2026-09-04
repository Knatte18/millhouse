MILL_REVIEW_BEGIN
# Review: millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] `--stage full` never threads git_name/git_email, so #954 still reproduces there
**Location:** `plugins/mill/scripts/millpy-implement.py:1016-1035`, `plugins/mill/scripts/millpy-fix.py:743-754`
**Issue:** Both files resolve `git_name`/`git_email` locally in `main()` (fail-fast if unset) and forward them into the `--stage finalize` branch's `finalize_from_output(...)` call, but the `--stage full` branch's direct `_forward_output(...)` call omits both kwargs entirely. `_forward_output` is the exact function containing the corroboration-write-then-dirty-check race Card 1 fixes (`_run_verify_gates` → corroboration waiver → `_status.set_batch_field` → `_in_scope_dirty_stuck`), and `--stage full` is still a live, reachable entry point (only blocked when `dispatch: agent`, which is the config default but not the only supported value — `dispatch: subprocess`/`psmux` still route through `--stage full`, confirmed via `_agent_dispatch.resolve_dispatch_mode`). Under those modes the exact #954 self-trip this plan sets out to fix can still occur.
**Fix:** Forward `git_name=git_name, git_email=git_email,` at both `--stage full` call sites, matching the finalize-branch treatment.

### [NIT:scope] CLI-to-finalize git identity wiring has no regression test
**Location:** `plugins/mill/unit_tests/test-millpy-implement.py`, `plugins/mill/unit_tests/test-fix-finalize.py`
**Issue:** Card 5's three new cases in `test-implementer-common.py` correctly cover the corroboration-commit logic by injecting `git_name`/`git_email` directly into `_forward_output`/`finalize_from_output`. However, neither `test-millpy-implement.py` nor `test-fix-finalize.py` (which already asserts on `finalize_from_output`'s other forwarded kwargs, e.g. `batch_verify_baseline`, in its existing mocked-call-args pattern) asserts that `main()`'s `--stage finalize` branch actually forwards the resolved `git_name`/`git_email` locals. The current two-line additions (Cards 3/4) are correct, but a future edit could silently drop them with no test catching it.
**Fix:** Add a `call_args.kwargs.get("git_name")`/`"git_email"` assertion alongside the existing forwarded-kwarg checks in each file's finalize-stage tests.

## Verdict

REQUEST_CHANGES
`--stage full` bypasses the #954 git-identity fix present in `--stage finalize`, leaving the reported bug reachable under non-agent dispatch modes.
MILL_REVIEW_END
