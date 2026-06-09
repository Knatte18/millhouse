`--only` accepts multiple test files (`nargs="+"`). The verify command passes two files. Valid.

Let me check the `verify` command CLAUDE.md constraint: verify must start with `PYTHONPATH=` for Python projects. The batch verify is `PYTHONPATH= uv run --project plugins/mill python ...` — starts with `PYTHONPATH=`. Good. Note the overview frontmatter has `verify: null` which is fine (overview-level verify is null; per-batch verify is set).

Now let me check global step numbering. The criteria mention "Global step numbering — unique, sequential, no gaps across batches." The cards use "Card 1..4" within the single batch. There is only one batch. Let me check whether the plan format expects global step numbers. Cards are numbered 1-4 within the batch; with a single batch this is unambiguous. 

I have enough to render the verdict. Let me confirm one thing on Card 3: it says "In Case 12, update `assert data["subagent_type"] == "mill-implementer"`". Case 12 line 419 confirms that exact assertion exists. Good. And Case 14 currently has NO `subagent_type` assertion (confirmed — lines 481-487 don't assert it), so adding one is a net-new addition. Good.

All cards have Context/Edits/Creates/Requirements/Commit. Card 1 and Card 4 have `Context: none` — which is acceptable since their Edits file is implicitly readable and Requirements reference only that file. Card 2 lists `_agent_dispatch.py` in Context (needed for the constant reference). Card 3 lists both scripts in Context. Context completeness holds.

MILL_REVIEW_BEGIN
# Review: Fix agent-dispatch prepare stage to emit namespaced subagent_type — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-09
```

## Findings

### [NIT] write_brief role docstring example is misleading
**Location:** Batch 1 / Card 1
**Issue:** Card 1 changes the `write_brief` docstring `role` example from `"mill-implementer"` to `"mill:mill-implementer"`, but `role` is a brief-naming token (callers pass `"implement"`, `"merge"`) — never a subagent_type — so the namespaced form propagates a pre-existing inaccuracy.
**Fix:** Use a realistic `role` example such as `"implement"` instead of any subagent name.

## Verdict

APPROVE
Plan is complete and correctly scoped; all hardcoded subagent strings covered, constants propagate to reviewer CLIs automatically.
MILL_REVIEW_END
