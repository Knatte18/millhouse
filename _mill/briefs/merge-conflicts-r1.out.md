All conflicts resolved, `mill-go/SKILL.md` staged (no diff shown since it matches HEAD's already-staged content exactly), and `mill-go-base/SKILL.md` staged with the ported prior-blocking feature. No conflict markers remain anywhere. I did not run `git commit` or `git merge --continue`, per instructions.

{"status":"success"}

**Summary of resolution:**

The single conflict was in `/home/knatte/Code/millhouse/wts/mill-go2-scaffold/plugins/mill/skills/mill-go/SKILL.md`. Our branch (HEAD) had already thinned this file down to a 29-line variant stub per this task's `three-file-split` decision, while `origin/main` (MERGE_HEAD) had continued developing the full pre-split body — specifically adding a "prior-blocking digest" feature (`--prior-blocking` flag, `_prior_blocking.build_digest`) at three sites in the NIT-fix dispatch flow.

This wasn't a simple pick-one-side case: the two sides were not mutually exclusive, they were "moved content" (step 4 of the brief) — the body that used to live in `mill-go/SKILL.md` now canonically lives in `plugins/mill/skills/mill-go-base/SKILL.md` (this branch's batch 1). Discarding origin/main's real feature work would have silently lost it. So I:

1. Diffed `MERGE_HEAD` against the merge-base for this file (`git diff 335ac6e1... MERGE_HEAD -- .../mill-go/SKILL.md`) to isolate exactly what origin/main added (82 lines, all "prior-blocking digest" content at 3 sites).
2. Ported that same content into the corresponding 3 sites in `plugins/mill/skills/mill-go-base/SKILL.md` (verified no site already had it, confirmed no literal `mill-go` strings needed `VARIANT_LABEL` parameterization in the ported text).
3. Resolved the conflict in `mill-go/SKILL.md` by keeping HEAD's thin-variant content only, since the body content is preserved (in updated form) in the base.
4. Staged both files with `git add`.

Verification: ran the batch verify commands (`test-guards.py test-skill-helper-drift.py test-phase-wait.py test-mill-go-variants.py`) — all pass — plus the full `run-all.py` suite. One unrelated failure (`test-language-skills-directive.py::test_render_fixer_brief`, missing `PRIOR_BLOCKING` token) exists identically on `origin/main` itself (verified via a throwaway worktree, now removed), confirming it's a pre-existing upstream issue unrelated to this conflict resolution, not something I introduced or am responsible for fixing under this brief's scope.