I have enough to write the review now.

# Review: 60 (A) — Branch/slug/claim fixes

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-17
```

## Findings

### [GAP] D2: config-load path has no existing error handler

**Section:** D2 — Review CLIs emit structured `verdict: ERROR` JSON
**Issue:** D2 says to "replace every `print(str(exc), file=sys.stderr); return 1` startup path (config load, reviewers load/validate, slug resolution)." But in all three review CLIs, `load_config` (which raises `ReviewError` per its docstring) and `resolve_wiki_path` are called with NO surrounding try/except — they sit before both existing handlers. A plan writer reading "replace" will find no existing handler to replace and may miss adding a new one, leaving the config-load failure path still unprotected.
**Fix:** Clarify explicitly that a new try/except must be added around `load_config` (and `resolve_wiki_path`) in each CLI, catching `ReviewError` (and `SystemExit` from wiki-cwd detection) and calling `print_error_envelope` — not merely updating the two existing handlers.

### [NOTE] D9: `test-review-cli-errors.py` named as new file; `test-review-cli.py` already exists

**Section:** D9 — Test coverage
**Issue:** D9 says "new file: test-review-cli-errors.py" but `plugins/mill/unit_tests/test-review-cli.py` already exists and covers `print_error`. Creating a second file splits related CLI test coverage.
**Fix:** Name the target `test-review-cli.py` (extend the existing file) and drop "new file" — the plan writer should add the error-envelope tests as new test functions in the existing module.

### [NOTE] D6: `_status.py` docstring shows the buggy formula

**Section:** D6 — `_status.read_branch` fallback
**Issue:** `_status.py` line 681 docstring reads ``Falls back to ``f"{cfg['spawn']['branch_prefix']}/{slug}"```, preserving the double-slash notation after the fix lands. Minor but leaves documentation inconsistent with the corrected code.
**Fix:** Note that the docstring at line 681 must also be updated to remove the spurious `/`.

## Verdict

GAPS_FOUND
D2's "config load" path has no existing handler to replace — a new try/except block is needed, but the discussion does not say so.