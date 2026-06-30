I've reviewed the overview, the single batch, and verified every claim against `_client.py`, both SKILL.md files (including `gate_cmd.lower()` at mill-go line 738), and the drift test file.

MILL_REVIEW_BEGIN
# Review: Fix drift-guard false positive and mill-start missing task body/brief — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [NIT] get_task() key set not grounded in Context
**Location:** Batch 1 / Card 1
**Issue:** Card 1 tells the implementer to document the exact `get_task()` key set (`body, brief, deferred, depends_on, id, isolated, slug, status, title`), but `_client.get_task` (the only schema-adjacent file in Context) merely returns `resp.get("task")` and does not define the task schema; the set is unverifiable from provided context.
**Fix:** Confirm the key set against the wiki task model / `wiki/_server.py`, or add that source to Card 1's Context.

### [NIT] Test module docstring left stale after third check group
**Location:** Batch 1 / Card 3
**Issue:** Card 3 adds a third `main()` check group (`--- Card 3: Extract-unit checks ---`) and a new lock, but the plan does not update the file's header docstring (lines 1-13) which still enumerates only "Card 1: Drift-guard scan" and "Card 2: Regression locks".
**Fix:** Have Card 3 also refresh the module docstring to mention the extract-unit checks and mill-start body/brief lock.

## Verdict

APPROVE
Fix is sound; lookbehind subsumes all ALLOWLIST exemptions, coupling and context are correct.
MILL_REVIEW_END
