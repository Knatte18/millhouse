MILL_REVIEW_BEGIN
# Review: plan validator and wiki-guard hook false positives — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-26
```

## Findings

### [NIT:design] echo/printf skip lets redirect targets through
**Location:** Batch 1 / Card 1, step 6 **Issue:** `echo x > <junction>/Home.md` tests no argument, so a direct write to the wiki through a redirect is allowed (discussion.md fixes the echo/printf skip, so this is a known trade-off, not a plan defect). **Fix:** Optionally note it under accepted-conservative behaviors, or test the token following a redirect operator even for echo/printf.

### [NIT:scope] Here-string and quoted `<<` not addressed in heredoc stripping
**Location:** Batch 1 / Card 1, step 1 **Issue:** The heredoc rule drops text to end of input after an unterminated start; a `<<<` here-string or a `<<` inside a quoted argument could be misread as a heredoc start and hide a later junction path (fail-open). **Fix:** State how `<<<` is treated in step 1 and add one test pinning it.

## Verdict

APPROVE
No blocking findings. Symbol-branch edits, batch index, `--only` usage, and context fields verified against `_plan_validate.py` and `run-all.py`.
MILL_REVIEW_END
