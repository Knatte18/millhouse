All 7 of 7 cards committed and matched against their declared `Commit:` messages.

{"status":"success","commit_sha":"bebd55efd7ae8ebf1adae5097eb21993394fd15e","session_id":"34fc997f-8496-41e6-9d65-8837d4b768e7","cards_done":[1,2,3,4,5,6,7]}

7 of 7 cards committed. This batch is pure `mill-plan/SKILL.md` prose (plus one `mill-config.yaml` comment-line edit in Card 7); `verify: null` per the batch frontmatter, so no test command was run — nothing to run. Pre-report `git status --porcelain --untracked-files=no` came back clean.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-plan-review-round-and-gate-bugs/plugins/mill/skills/mill-plan/SKILL.md`
- `/home/knatte/Code/millhouse/wts/mill-plan-review-round-and-gate-bugs/plugins/mill/skills/mill-go-base/SKILL.md`
- `/home/knatte/Code/millhouse/wts/mill-plan-review-round-and-gate-bugs/plugins/mill/templates/mill-config.yaml`

Card-by-card summary:
1. Relocated the ERROR-only-aggregate retry gate from step 4.5 to 3.5 (physically before 4a–4d), added an unconditional per-round `plan-review-r{N}` Timeline append, and removed the now-redundant appends from 4a and 4d. Fixed the cross-reference in `mill-go-base/SKILL.md`.
2. Persisted Phase: Plan's `skip_checks` into `00-overview.md` frontmatter and threaded `plan_skip_checks` into all four Plan Review dispatch sites (Agent-mode and subprocess, primary and 3.5-retry).
3. Spelled out the explicit two-argument `_plan_dag.validate` call shape at steps 4b and 4d.
4. Added a Principles bullet banning cross-card same-commit requirements.
5. Dropped the `demoted` predicate and its dead carryforward-filtering exception paragraph from the Convergence gate; renamed the heading and reworded the round-cap commit-message append text (4 occurrences) and the 4c rationale sentence.
6. Added the `out-of-worktree-target` skip-check override paragraph and updated the fix-table row to reference it.
7. Added the verify-clean-first precondition before defaulting `done_gate` to a lint command, and synced the `mill-config.yaml` template comment.

{"status":"success","commit_sha":"bebd55efd7ae8ebf1adae5097eb21993394fd15e","session_id":"34fc997f-8496-41e6-9d65-8837d4b768e7","cards_done":[1,2,3,4,5,6,7]}
