MILL_REVIEW_BEGIN
# Review: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-06
```

## Findings

### [NIT] New prose uses em-dashes despite ASCII-only Shared Decision
**Location:** `plugins/mill/skills/mill-merge-in/SKILL.md:64`, `plugins/mill/unit_tests/test-worktree.py:426,446`
**Issue:** The plan's "ASCII-only new messages" Shared Decision (00-overview.md) requires new print/prose text introduced by this task to avoid em-dashes; the new Step-3 rationale sentence and the two new Card-4 `PASS:` lines use `—` (U+2014).
**Fix:** No action required — each instance matches the pre-existing, file-wide convention (SKILL.md and test-worktree.py both use em-dashes throughout in analogous prose/PASS strings), and per this review's instruction to prefer established codebase convention over a stricter alternative, this is informational only.

## Verdict

APPROVE
All three batches match their cards; no out-of-plan files, no duplicated helpers, tests cover happy/error paths correctly.
MILL_REVIEW_END
