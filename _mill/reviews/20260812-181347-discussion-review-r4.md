MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
duration_s: 265.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [NIT:consistency] 819 Scope still lists the dropped is_inplace()-suspect trigger
**Demoted-from:** BLOCKING
**Section:** Scope/In (#819) vs Decision `819-stale-worktree-gate`
**Issue:** Scope's #819 bullet still OR's "an `_inplace.is_inplace()` result that's itself suspect" into the definition of "genuine ambiguity," but the Decision explicitly drops/rejects that trigger as unimplementable (verified: `_inplace.is_inplace()` has no error/uncertainty return, no "suspect" notion anywhere in the codebase) and defines the gate purely by `git worktree list --porcelain` staleness/absence/mismatch.
**Fix:** Strike the is_inplace()-suspect clause from the Scope bullet so it matches the single-condition gate the Decision actually specifies.

### [NIT:consistency] 817 fallback trigger (b) is defined two incompatible ways
**Demoted-from:** BLOCKING
**Section:** Decision `817-dead-parent-detection`
**Issue:** The Decision first defines "fallback trigger (b)" as the hop occurring when *both* `_mill/status.md` and `task/status.md` are absent from the historical tree ("Only if both paths are absent from that tree is the hop treated as a genuine chain-end (fallback trigger (b) below)"), then two sentences later restates trigger (b) as "`git show ...` succeeds but the file has no `parent:` row" — a file-present-but-fieldless case, not a both-absent case. These are non-overlapping conditions.
**Fix:** State explicitly whether "both paths absent" and "file present, no `parent:` row" are the same trigger, two separate `base_branch`-fallback triggers, or one of them is an unhandled case requiring its own halt.

### [NIT:consistency] 817 Testing section hasn't kept pace with the Decision's accumulated complexity
**Demoted-from:** BLOCKING
**Section:** Testing / `817-dead-parent-detection`
**Issue:** Across r1-r3 the Decision grew to include multi-hop chain-walking, a 10-hop cycle cap with its own halt, and a `_mill/`->`task/` legacy-layout fallback for each hop's status.md read — but the Testing bullet for 817 only names two single-hop cases ((a) torn-down-with-tag, (b) never-pushed-no-tag). The cap-halt, multi-hop walk, and legacy-layout read path have no stated coverage.
**Fix:** Add test cases (or an explicit review-only justification) for the multi-hop walk, the 10-hop cap halt, and the `task/` legacy-layout fallback read.

## Verdict

APPROVE
Two artefact self-contradictions (819 scope-vs-decision, 817's dual definition of trigger b) and a testing-coverage drift need resolving.
MILL_REVIEW_END
