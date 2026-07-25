MILL_REVIEW_BEGIN
# Review: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps

```yaml
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [NOTE] load_task_title's `git_root` parameter name doesn't match its needed on-disk semantics
**Section:** Decision "On-disk-first slug/title resolution"
**Issue:** `_review_common.py:329` names the first param `git_root`, but every call site (`_review_plan.py:359/692`, `_review_code.py:361`, `_review_discussion.py:108`) actually passes the already-resolved hub `project_root`; the new on-disk fast path must read `status.md` relative to that hub value, not a raw git checkout root, which matters for M2+sub configs where they diverge.
**Fix:** Note in the plan that the on-disk fast path reads `status.md` via the passed-in value (already hub-resolved by callers), independent of the misleading parameter name; no functional change needed, just plan-writer awareness.

## Verdict

APPROVE
Source-verified against _paths.py, _marker.py, wiki/_client.py, mill-go/SKILL.md, and all 6 named call-site files; no blocking gaps found.
MILL_REVIEW_END
