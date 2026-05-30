# Review: task-deps-and-isolation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-30
```

## Findings

### [NOTE] Gotcha contradicts Migration decision on approach
**Section:** Technical context / Gotchas vs. `### migration` decision
**Issue:** The Gotcha says "the migration must rewrite records wholesale" but the Migration decision explicitly says "No clear-and-reinsert (that would re-key doc_ids)" and instead uses `tinydb.operations.delete("group")` in place. The two statements are irreconcilable; a plan writer could implement the wrong approach from the Gotcha.
**Fix:** Update the Gotcha to say "plain `db.update({...})` merges keys and cannot delete `group`; the migration uses `tinydb.operations.delete('group')` to drop the key in-place without re-keying doc_ids — see migration decision."

## Verdict

APPROVE
Discussion is thorough and resolved; one stale Gotcha line contradicts its own decision but the Migration decision section is authoritative and clear.