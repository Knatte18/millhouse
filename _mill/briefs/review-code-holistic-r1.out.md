The duplicate case numbers (27 and 28) are pre-existing in the file — these exist before the new cases 36-43 were added. This is not introduced by the current implementation; it's a pre-existing inconsistency. The brief says this reviewer should not escalate pre-existing issues to BLOCKING unless new information justifies it.

Now let me confirm all four files touched match plan's "All Files Touched" list and there are no surprise files.

Plan says all files touched:
1. `plugins/mill/scripts/_implementer_common.py` - present and changed
2. `plugins/mill/skills/mill-go/SKILL.md` - present and changed
3. `plugins/mill/templates/implementer-brief.md` - present and changed
4. `plugins/mill/unit_tests/test-implementer-common.py` - present and changed

These exactly match what's listed in the manifest. No out-of-plan files.

The implementation looks solid. I now have enough to produce the final review.

MILL_REVIEW_BEGIN
# Review: Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection -- holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-28
```

## Verdict

APPROVE
All three bugs are correctly fixed across all four call sites; tests cover the new behaviour precisely.
MILL_REVIEW_END