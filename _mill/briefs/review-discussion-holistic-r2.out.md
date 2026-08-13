MILL_REVIEW_BEGIN
# Review: mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:consistency] #818's consumer list contradicts #825's rewrite of that consumer
**Section:** Decisions › cleanliness-unresolvable-parent-diff (#818), interacting with finalize-batch-scoped-dirty-check (#825) **Issue:** #818 lists `_in_scope_dirty_stuck` as needing an explicit `is None` branch, hedging with "whatever underlying `_parent_diff_names`-derived call remains in its dependency chain" — but #825 replaces that function's owned-paths source with a new `git diff --name-only <start_sha>` call (confirmed distinct from `_parent_diff_names`, which is hardcoded to `<parent_branch>...HEAD`), so after #825 there is likely no `_parent_diff_names`-derived call left in `_in_scope_dirty_stuck` at all. **Fix:** State explicitly whether the new `start_sha`-based git-diff call needs its own resolvable/unresolvable distinction (mirroring #818's pattern) or whether #818's obligation for this function is dropped now that #825 supersedes its call path.

### [BLOCKING:design] #825 batch-scoped check doesn't address start_sha == None
**Section:** Decisions › finalize-batch-scoped-dirty-check (#825); Technical context (`_implementer_common.py` call-site note) **Issue:** `start_sha: str | None` is a genuinely nullable parameter at the same call site (`_batch_completeness_stuck`'s own docstring, case 3, explicitly special-cases `start_sha is None` as "gate has nothing to check against" — e.g. docs-only batch, zero cards) — but #825's decision only says start_sha is "already available," with no stated behavior for the batch-scoped `_in_scope_dirty_stuck` when it's None. **Fix:** Add an explicit disposition — e.g. extend the existing `task_dir is None or parent_branch is None` disable-guard to also include `start_sha is None`, or state why that case can't reach this gate.

### [NIT:consistency] `signature:` doc-comments in SKILL.md not flagged for update
**Section:** Decisions › cleanliness-unresolvable-parent-diff (#818); `SKILL.md` step 2b **Issue:** #818 changes `revert_out_of_scope_drift`'s return type to `tuple[list[str], list[str] | None]`, but the discussion doesn't mention updating `SKILL.md`'s line 653 `signature:` doc-comment (currently `-> tuple[list[str], list[str]]`), which the drift-guard unit test does not check (confirmed: `test-skill-helper-drift.py` validates only that referenced function names resolve, not signature text). **Fix:** Add the `signature:` comment update to #818's SKILL.md/handoff.md scope so the doc-comment doesn't silently go stale.

## Verdict

REQUEST_CHANGES
Two decisions (#818, #825) leave their interaction and a nullable-input case unresolved.
MILL_REVIEW_END
