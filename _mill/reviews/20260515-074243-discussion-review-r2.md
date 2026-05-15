I've verified all key source files. Ready to produce the review.

# Review: 56 (A) — Fix mill-go/start/plan/merge runtime behavioral bugs

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-15
```

## Findings

### [GAP] Case 6 scenario is identical to updated Case 3b
**Section:** `## Testing`
**Issue:** Case 3b (after update) and Case 6 (new) describe identical setups: pre-existing dirt captured in snapshot, empty commit (new HEAD), working tree dirty → stuck/logic. The plan writer cannot determine what distinguishes Case 6 from the updated Case 3b and may either write two duplicate tests or omit one.
**Fix:** Specify what Case 6 adds that Case 3b does not cover — for example, test a tracked file dirtied after snapshot (new dirt, different from pre-existing), or clarify that Case 6 is the renamed form of Case 3b and the update instruction already covers it.

### [NOTE] Case 4 described as "not covering the empty-dir case" — but it is one
**Section:** `## Decisions / #281`, `## Technical context`
**Issue:** The discussion states "case 4 documents the current behavior but does not cover the empty-dir case", but `test-paths.py` line 107 creates `_mill/plan/` with a bare `mkdir` (no files) — Case 4 is already an empty-dir test. After the fix, Case 4 still passes (no `task/plan/` fallback present, function falls through to `return target`), so the plan writer will not be surprised at runtime, but the description is inaccurate.
**Fix:** Clarify that Case 4 tests empty-dir with no fallback (returns original target), and Case 7 tests empty-dir with a `task/plan/` fallback present (returns fallback path). Both are needed post-fix.

## Verdict

GAPS_FOUND  
One GAP: Case 6 test specification is indistinguishable from the updated Case 3b; plan writer cannot implement it without guessing.