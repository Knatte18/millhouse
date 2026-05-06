# Review: 4 (A) — mill-setup: --from-url for separate wiki repo — 01-helpers

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-helpers
date: 2026-05-06
```

## Findings

### [NIT] WikiSetupError base class inconsistent
**Step:** Card 1
**Issue:** Plan specifies `WikiSetupError(Exception)` but both `WikiPushError` and `LockBusy` extend `RuntimeError`. Diverges from codebase pattern.
**Fix:** Use `WikiSetupError(RuntimeError)` for consistency.

### [NIT] Card 2 describes separate-function style; test-wiki.py uses inline try/except
**Step:** Card 2
**Issue:** Plan says "Add new test functions… registered in the `main()` runner block" (the `test-config.py` style), but `test-wiki.py` embeds all test logic as inline try/except blocks in `main()`. Implementer following the plan literally will diverge from the existing file's style.
**Fix:** Clarify that new tests should follow `test-wiki.py`'s inline try/except pattern, not the function-list style used in `test-config.py`.

### [NIT] No test for pull path when branch=None
**Step:** Card 2
**Issue:** `test_pull_existing_repo_match` covers branch-provided pull; there is no test verifying that when `branch is None`, the `git -C <dest> branch --show-current` call is skipped entirely.
**Fix:** Add a variant of test 4 with `branch=None` asserting no `branch --show-current` call.

### [NIT] No test for missing cfg_path parent directory
**Step:** Card 4
**Issue:** All tests compute `cfg_path = Path(tmp.name) / "config.local.yaml"` where `tmp.name` already exists, so `mkdir(parents=True, exist_ok=True)` is never exercised in the non-trivial case.
**Fix:** Add one test with `cfg_path = Path(tmp.name) / ".millhouse" / "config.local.yaml"` where `.millhouse/` is not pre-created.

## Verdict

APPROVE — no blocking issues; interfaces are well-specified and decision-aligned; four low-risk NITs only.