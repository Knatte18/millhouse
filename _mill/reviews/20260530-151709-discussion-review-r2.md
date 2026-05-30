# Review: task-deps-and-isolation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-30
```

## Findings

### [NOTE] Gotcha contradicts migration decision on TinyDB delete
**Section:** Technical Context → Gotchas
**Issue:** The gotcha says "TinyDB `update` merges keys and cannot delete `group`; the migration must rewrite records wholesale" — but the migration decision (which the gotcha itself cites via "see migration decision") uses `tinydb.operations.delete` in an in-place `db.update(...)` call, explicitly rejecting wholesale rewrite as doc_id-breaking. The gotcha body is stale and contradicts the authoritative decision.
**Fix:** Reword the gotcha to: "Use `tinydb.operations.delete('group')` inside `db.update(...)` to drop a key without re-keying doc_ids; plain `db.update(dict)` merges and cannot delete — that is why `set_phase` currently uses remove+reinsert, but the migration must not."

### [NOTE] Batch validation semantics for intra-batch deps unspecified
**Section:** Decisions → validation / Technical Context → `_store.py`
**Issue:** The validation section requires "`upsert_tasks_batch` validates before any mutation" but doesn't specify behavior when the batch itself contains intra-batch dependencies (e.g., task A with `depends_on: ['B']` and task B both new, in the same call). Per-task serial validation would incorrectly reject A before B is inserted.
**Fix:** Clarify that batch validation must compute the projected post-batch state (all current + incoming tasks merged) and validate that projection, then apply. Or explicitly exclude `depends_on` from batch-level validation (acceptable since current callers never send deps via batch).

### [NOTE] "Effective depends_on" in display context is ambiguous
**Section:** Decisions → display-format
**Issue:** "A task with a non-empty effective `depends_on` gets a `Depends on:` line" uses "effective" without defining it for display. In the layer-algorithm section, `effective_deps` explicitly filters out done tasks. If the same definition applies to display, a task whose only dep is already done silently loses its `Depends on:` line.
**Fix:** Clarify whether the `Depends on:` line shows the raw `depends_on` list (all entries, including done targets) or only the done-filtered effective set. The scenario "all deps now done" should be a named test case.

## Verdict

APPROVE
All three findings are notes; the decisions are internally consistent and implementable.