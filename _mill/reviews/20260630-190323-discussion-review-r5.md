Based on independent verification of every cited claim against source (`_marker.py`, `_review_discussion.py`, `wiki/_client.py`, `wiki/__init__.py`, `millpy-bg.py`, `millpy-implement.py`, `millpy-fix.py`, `_implementer_common.py`, `mill-start/SKILL.md`, `mill-go/SKILL.md`, `mill-plan/SKILL.md`, and the referenced unit-test files), I found no factual discrepancies. All line-number citations, exception hierarchies, import aliases, gate ordering, and SKILL.md dispatch sites match the discussion's description exactly.

MILL_REVIEW_BEGIN
# Review: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: C:\Code\millhouse\wts\mill-review-and-finalize-gaps\_mill\discussion.md
date: 2026-06-30
```

All three gaps are well-scoped, each Decision carries rationale and rejected alternatives, and every prior-round correction (round-1 `MarkerError`-wrapping fix, round-2 `wiki._client.health_check` double-reference fix and citation correction, round-3 dirty-tree-gate backstop correction, round-4 `task_data()` retry-helper extension) is reflected consistently and accurately in the current text.

Spot-verified against source and all consistent with the discussion's claims:
- `_review_discussion.py` round-cap check (lines 65-71) and error string match exactly; `finalize()` has no `max_rounds` param, confirming the SKILL.md-only fix framing.
- `mill-start/SKILL.md` currently never threads `--max-rounds` at any of its four discussion-review dispatch sites (steps 2 and 3.5, agent + subprocess), matching the described bug.
- `_marker.py:52` and `:95` are the two independent `wiki.list_tasks_brief` call sites; `from wiki import _client as wiki` at line 22 confirms `wiki.health_check(...)` (not `wiki._client.health_check`) is correct.
- `wiki/__init__.py:45,70` confirms `WikiStartupError` subclasses `WikiError`; `wiki/_client.py:13-42` re-exports `WikiStartupError` (not `WikiError` itself) into `_client`'s namespace; `millpy-bg.py:152/159` confirms `WikiError` is caught ahead of `MarkerError`.
- `millpy-implement.py` has no `wiki` import today (only `_marker`), confirming the stated need for a new import alongside the new `except` clause.
- `_implementer_common.py:932-968` (no-content-commit gate) and `:996-1000` (nits marker block) match cited line ranges and current unconditional ordering precisely.
- `millpy-fix.py:249,472` both pass `nits_only=args.nits_only` and neither passes `task_dir`/`parent_branch`; `_in_scope_dirty_stuck`'s `None`-guard (lines 290-292) confirms the gate is a no-op on that path today.
- `mill-go/SKILL.md:368` (NIT-fix APPROVE branch, no re-run of cleanliness gate) and `:711-720` (terminal cleanliness gate) match the cited backstop claim; `mill-plan/SKILL.md:218,222` confirms the Shallow-escape citation; grep confirms `mill-go/SKILL.md` has no `--max-rounds` usage and only `mill-start/SKILL.md` dispatches `millpy-review-discussion.py`.
- Completeness gate (`_batch_completeness_stuck`) is disabled whenever `verify_cmd` is present (the normal nits-only path), so the claim that it's "unaffected" by the reordering holds without misfiring on a legitimate zero-commit success.
- Referenced test files exist and `test-review-discussion-flow.py:164-232` already exercises the `max_rounds` override end-to-end as claimed.

## Verdict

APPROVE
No factual errors found against source; all decisions, scope, and testing are sound and well-grounded.
MILL_REVIEW_END
