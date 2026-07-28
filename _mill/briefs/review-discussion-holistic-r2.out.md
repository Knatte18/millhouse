MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] mill-merge-in SKILL.md wording: contradicted, unscoped
**Section:** Decisions/merge-in-semantic-duplication (#718) vs Technical context vs Scope/In
**Issue:** #718's Decision says the SKILL.md Step 3 row's "verify nothing load-bearing was lost" wording "must also change," but Technical context says "no change needed there beyond what the template produces," and Scope/In never lists this file as an edit target. Verified current text at `mill-merge-in/SKILL.md` line 73 is exactly the wording both sections reference.
**Fix:** Reconcile the two claims; if the row is edited, add it to Scope/In.

### [GAP] Finalize marker gate: no seam into `_forward_output`
**Section:** Decisions/merge-in-marker-verification (#713); Technical context
**Issue:** Verified in `_implementer_common.py`: `finalize_from_output` reads `--agent-output`, applies its not-found guard, `html.unescape`s, then calls `_forward_output`, which prints the final JSON itself and returns only an int -- nothing is returned to "override" after the fact. Gating "before it reaches the caller" at the finalize site needs the raw text before that call, which today exists only inside `finalize_from_output`. (The `full`-stage site has no such problem -- `output` is already a local variable there.)
**Fix:** Specify that finalize-stage gating reads/unescapes `args.agent_output` itself first (or names a shared helper to factor out), rather than treating it as an unchanged wrap.

### [GAP] Dirty-parent preflight may misfire on Step 5's own retry
**Section:** Decisions/dirty-parent-worktree-preflight (#705)
**Issue:** Step 5 is documented as re-runnable after a partial failure ("a failed step is reported... user can re-run from that step"). If `git commit` fails after `merge --squash`/`reset`/`checkout` already staged changes, the new `status --porcelain` preflight sees the parent as dirty on retry and tells the operator to commit/stash mill-merge's own half-applied squash, not independent edits.
**Fix:** Address the mid-Step-5 retry case explicitly, or note and accept the risk.

### [GAP] #705 testing conditional left open though the answer is checkable
**Section:** Testing/mill-merge dirty-parent-worktree preflight (#705)
**Issue:** Testing hedges "if an integration test exists for Step 5, extend it... if not, SKILL.md-documented behavior only is acceptable." Verified `plugins/mill/integration_tests/test-merge.py` already exists and directly exercises Step 5's squash sequence ("Direct squash-merge child -> parent", mirrors "Entry Step 5 phase-gate logic") -- the mandatory extend-it branch applies per the discussion's own stated logic.
**Fix:** Commit to extending `test-merge.py` with a dirty-parent-worktree fixture; drop the permissive fallback.

## Verdict

GAPS_FOUND
One direct section-vs-section contradiction plus three unaddressed implementation/testing interactions need resolution before plan writing.
MILL_REVIEW_END
