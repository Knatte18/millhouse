MILL_REVIEW_BEGIN
# Review: millpy-implement finalize/resume fixes and the red integration suites — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-26
```

## Findings

### [NIT:consistency] Card 2 edits a file its Edits list omits
**Location:** Batch 1 / Card 2 vs Card 3 **Issue:** Card 2 tells the implementer to write and run Card 3's failing test first, but its `Edits:` lists only `_implementer_common.py` while the test file belongs to Card 3, which is sequenced after it. **Fix:** Add the test file to Card 2's `Edits:`, or order the test card before the fix card.

### [NIT:design] Card 2 root cause is hypothesised, not verified
**Location:** Batch 1 / Card 2 **Issue:** `_in_scope_dirty_stuck` in `_implementer_common.py` does use `line.startswith("_mill/briefs/")` (verified), but that nested-path miss is unproven as the #1162 cause. **Fix:** None needed; the reproduce-first step plus the "adjust whichever matching is wrong" fallback already covers this.

### [NIT:scope] Card 7 sibling sub-scenarios share the live-local-branch hazard
**Location:** Batch 2 / Card 7 **Issue:** In `test-merge.py` the `test/cycle-x` and `test/cycle-y` branches (and other sub-scenarios) also remain as local branches, which `check_liveness` in `_parent_branch.py` treats as live. **Fix:** None needed; the card already says to fix only the sub-scenarios that fail, and the batch verify runs the whole file.

## Verdict

APPROVE
Plan is well-formed and source-grounded: call sites, signatures, tokens and `--only` all check out; only minor nits.
MILL_REVIEW_END
