MILL_REVIEW_BEGIN
# Review: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Integration harness already dodges the exact bug being fixed
**Section:** ## Testing (Step 5 guard bullet)
**Issue:** `plugins/mill/integration_tests/test-merge.py` (~593-611) already exercises Step 5's restore sequence end-to-end, and its own comment states it seeds a hub-side `_mill/status.md` specifically "so the restore commands below have something real to act on" because a bare `git checkout -- <pathspec>` "fails ... independent of the worktree-mode bug this scenario targets" — i.e. the harness deliberately routes around this exact bug. The discussion frames this as speculative ("if an integration harness already exercises Step 5... check... add if missing") rather than a confirmed, already-diagnosed gap.
**Fix:** State definitively that no scenario currently covers "parent tracks nothing at task_dir," and require a new/modified scenario (dropping the seeded status.md) asserting the guarded checkout no longer halts.

### [GAP] Caller inventory (and its Decision rationale) omits SKILL.md's own is_inplace call
**Section:** ## Technical context / ### Decision: is-inplace-topology-check
**Issue:** `mill-merge/SKILL.md:21` calls `_inplace.is_inplace(slug, git_root, cfg)` directly in Entry Step 1 — the exact call that produces #735's symptom per the Problem section — but Technical Context's "Callers of is_inplace" bullet lists only `_paths.py:433` and `millpy-cleanup.py:434`, and the Decision's rationale then argues correctness from "Both existing callers ... already validate branch==slug," a factually incomplete count (3 call sites exist, not 2).
**Fix:** Add SKILL.md:21 to the caller inventory; note the branch==slug precondition holds there too (even more directly, since `_marker.task_data` derives `slug` from `git_root`'s own branch).

### [GAP] millpy-cleanup's is_inplace call goes from dead code to untested live branch
**Section:** ## Testing (test-cleanup.py bullet)
**Issue:** In `_resolve_inplace_mode` (millpy-cleanup.py:423-434), `is_inplace` is only reached after the caller has already computed `worktree_dir = resolve_worktrees_dir(cfg, hub_root) / slug` and confirmed `.is_dir()` is False — the old `is_inplace` recomputes that identical check internally, so it was guaranteed to return True there (the `return ("worktree", "")` fallback at line 437 was unreachable). The new topology check removes that tautology, making the branch genuinely live for the first time, but the "no changes needed" conclusion for test-cleanup.py doesn't add coverage exercising this call with a real (non-mocked) `is_inplace`/`resolve_main_worktree_root`.
**Fix:** Add a test-cleanup.py case for `_resolve_inplace_mode` that patches only `_inplace.resolve_main_worktree_root` (not `_resolve_inplace_mode` itself) to confirm both outcomes are reachable post-fix.

### [NOTE] Q&A log's fixture-site count doesn't match the itemized breakdown
**Section:** ## Q&A log (3rd entry) vs. ## Testing
**Issue:** Q&A log says "~13" sites patch `_inplace.resolve_worktrees_dir`; the Testing section's own itemized list (test-inplace.py x3, test-paths.py x6, test-review-common.py x2) sums to 11, matching a repo-wide grep.
**Fix:** Correct "~13" to 11, or drop the approximate count since the exact sites are enumerated two paragraphs later.

### [NOTE] Hybrid-approach rejection reasoning unclear for the #735 scenario
**Section:** ### Decision: is-inplace-topology-check — Rejected
**Issue:** "consult topology only when path-existence says 'in-place' ... doesn't fix the bug ... just narrows it" is unclear: when no canonical dir exists (#735's actual repro), gating on "path-existence says in-place" before consulting topology reduces exactly to the pure-topology check, so it isn't obvious this rejected variant fails to fix #735's described scenario.
**Fix:** Either name the specific residual scenario the hybrid leaves broken (likely the out-of-scope stale-worktree edge), or reword the rejection around unnecessary complexity/two sources of truth instead of "doesn't fix the bug."

## Verdict

GAPS_FOUND
Three GAPs: undersold testing gaps (integration + cleanup coverage) and an incomplete caller inventory feeding a Decision's rationale.
MILL_REVIEW_END
