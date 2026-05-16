I now have enough source verification to write the review.

# Review: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-16
```

## Findings

### [GAP] Phase 3.1 halt contradicts Phase 3.2b Case 2
**Section:** `## Scope` (Phase 3.2b definition) vs `## Technical context` (mill-setup phases)
**Issue:** Phase 3.2b Case 2 says "wiki/config.yaml exists AND mill-config.yaml already exists → skip copy, still delete wiki file and push." The Technical Context then says Phase 3.1 HALTS with an operator-error when both files coexist — the identical condition. Phase 3.1 runs before Phase 3.2b, so Case 2 is unreachable code; the Phase 3.1 halt also instructs the operator to "rerun mill-setup (so Phase 3.2b retries the wiki delete)", but on every re-run Phase 3.1 will halt again for the same condition, making the cycle unbreakable without manual deletion.
**Fix:** Decide which behaviour wins: either (a) Phase 3.2b Case 2 handles both-files-exist gracefully (no Phase 3.1 halt for this scenario), or (b) Phase 3.1 halts and Phase 3.2b Case 2 is removed (operator must always manually delete the wiki file). Remove the contradictory description.

## Verdict

GAPS_FOUND
Phase 3.1 halt and Phase 3.2b Case 2 are mutually contradictory; plan writer cannot implement both as written.