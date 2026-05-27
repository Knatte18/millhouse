# Review: Audit and clean up stale V2 references

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [NOTE] mill-autofix Step 2 instruction ambiguous
**Section:** Technical context — mill-autofix/SKILL.md change profile
**Issue:** "replace Step 2 'Add to Home.md' with `_client.upsert_task` call" implies removing the `millpy-add.py` subprocess call, but `millpy-add.py` already uses V3 `_client.upsert_task` internally (confirmed at scripts/millpy-add.py:132). The only stale V2 reference in mill-autofix/SKILL.md (grep count: 1) is the `_tasks_md.parse` call in the Step 2 error-handling path.
**Fix:** Clarify that the `millpy-add.py` subprocess call stays; only the `_tasks_md.parse` error-path lookup (lines 202–212) and Phase 1b Home.md read need replacing.

### [NOTE] mill-fold LOCKED_FOLD_PHASES replace instruction inconsistent
**Section:** Technical context — mill-fold entry vs LOCKED_FOLD_PHASES section
**Issue:** The mill-fold change profile says "replace with `_client`-based phase check" while the LOCKED_FOLD_PHASES section says "inline this set directly" (i.e., hardcode `{"active", "ready-to-merge", "pr-pending"}`), the same approach used for mill-ghissues-to-tasks.
**Fix:** Align the mill-fold description to match the LOCKED_FOLD_PHASES section: inline the set rather than calling `_client` for a phase check.

## Verdict

APPROVE
All technical claims verified against source; two low-impact NOTEs, zero GAPs.