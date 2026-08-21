MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs

```yaml
duration_s: 238.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] codeguide-cwd-pinning fix mechanism unverified
**Section:** Decisions/codeguide-cwd-pinning (#880) **Issue:** the decision hedges "however the codeguide-update skill accepts a cwd/root — pin it explicitly," but `plugins/codeguide/skills/codeguide-update/SKILL.md` has no cwd/root parameter at all — `$ARGUMENTS` only controls file-scope (`1h`/`3d`/`HEAD~3`/explicit paths/`--parent <ref>`), and every internal step (`resolve.py`, `resolve_scope.py`) runs from whatever the ambient shell cwd is ("from the repo root", "from that file's directory"). `git-commit/SKILL.md`'s own invocation confirms this — it only ever passes `--parent <branch>`, never a cwd. **Fix:** decide and state the actual mechanism (e.g., an actual `cd <hub_root>` before the Skill-tool call, and confirm that persists into the skill's own internal bash invocations) before a plan writer can implement this.

### [NIT:consistency] #900 "3 of 4 entry points" convention claim unverified for mill-start
**Demoted-from:** BLOCKING
**Section:** Decisions/config-local-yaml-caller-alignment (#900) **Issue:** the rationale cites `mill-start/SKILL.md` Entry step 2 as already calling `_config.load_config(hub_root_value, git_root_value)`, but the actual source at that step only shows the bare `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict` comment — no concrete call, and neither `hub_root` nor `worktree_root` is even bound until the later "Path Setup" block. **Fix:** re-verify the claimed majority count against actual source (mill-plan and mill-merge are confirmed; mill-start is not), and adjust the rationale/count accordingly — it doesn't change the recommended fix but the "already-majority, lower-risk" argument needs accurate grounding.

### [BLOCKING:design] "plain non-fast-forward rejection" has no matching criteria
**Section:** Decisions/push-failure-classification (#904, #862) **Issue:** the new third branch fires "when the output matches none of the branch-protection substrings AND is a plain non-fast-forward rejection" — unlike the branch-protection check (four explicit named substrings), no substring/pattern is given to positively identify a non-fast-forward rejection vs. any other failure (auth, network, corrupt ref). **Fix:** either specify the exact match criteria (e.g. `! [rejected]`, `(fetch first)`, `non-fast-forward`) or state explicitly that the new branch is the unconditional fallback for any non-branch-protection failure.

## Verdict

REQUEST_CHANGES
Three BLOCKING gaps: an unverified codeguide cwd-pinning mechanism, an inaccurate mill-start convention claim, and unspecified push-rejection match criteria.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 2._
MILL_REVIEW_END
