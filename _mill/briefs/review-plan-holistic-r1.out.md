MILL_REVIEW_BEGIN
# Review: _plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Card 6's fixture reuse instruction cannot produce required scenarios
**Location:** batch 2 (validator-tests), Card 6. **Issue:** `_make_overview()` (the only overview-building helper in `test-plan-validate.py`) hardcodes `"    verify: null"` for every Batch Index entry with no override parameter; the `depends-on-batch-mismatch`/`verify-mixed-cwd` sibling tests it's cited as precedent for never vary the *index entry's* own `verify:` field (they hand-roll only the batch-file text). Most of Card 6's 10 listed scenarios (e.g. "overview naming a real command while the batch file carries `verify: null`", "a plain string on one side against a `{cwd, command}` mapping on the other") require setting the index entry's own `verify:` to non-null values, which is structurally impossible with the cited helper as-is. **Fix:** Either explicitly authorize extending `_make_overview` with an optional per-batch `verify` override (backward-compatible default `null`), or instruct hand-rolling the overview text for these scenarios the same way the batch-file text is hand-rolled in the sibling tests — the card currently forbids "writing a new fixture" without resolving which path to take.

### [NIT:consistency] "ASCII only" instruction in new-code cards contradicts file's existing em-dash convention
**Location:** batch 1, Cards 1, 3, 4, 5 (each ends "ASCII only in all new comments and docstrings"). **Issue:** `_plan_validate.py` already uses the em dash "—" 38 times in its comments/docstrings (including in the very sections these cards are inserted next to, e.g. the "Check 6 — reads-not-backtick-path" banner and `_strip_n_leading_spaces`'s own docstring); CLAUDE.md's ASCII-only rule targets `print()`/`_log()` stdout, not source comments. **Fix:** Either drop the ASCII-only instruction for these cards to match the file's established convention, or note explicitly that it's a deliberate new-code-only deviation.

## Verdict

REQUEST_CHANGES
Card 6's fixture-reuse instruction is structurally unworkable for most of its listed test scenarios.
MILL_REVIEW_END
