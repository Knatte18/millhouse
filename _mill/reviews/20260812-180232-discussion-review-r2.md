MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
duration_s: 268.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] FF-only-merge halt not exempted from rollback
**Section:** Decisions/824-parent-fast-forward + 824-rollback-ref, `## Rollback (Steps 1-5 only)` (`SKILL.md:419-440`)
**Issue:** The new FF-failure halt (parent has local-only commits) leaves nothing mutated, exactly like the existing "Dirty-parent-worktree halt (Step 5)" which `SKILL.md:437-438` explicitly exempts from rollback. The discussion never adds a matching exemption for the new halt. Without one, a subsequent Steps-1-5 failure hitting the generic rollback runs the now-changed `git -C <parent-path> reset --hard origin/<parent_branch>` (824-rollback-ref's own fix) — silently destroying the exact local-only parent commits the FF-only choice was designed to protect.
**Fix:** State explicitly that the FF-failure halt gets the same rollback exemption as the dirty-parent-worktree halt, and add that to the Rollback section's scope.

### [NIT:scope] #817 liveness check's target call site is ambiguous
**Demoted-from:** BLOCKING
**Section:** Decisions/817-dead-parent-detection; Technical context (`_parent_branch.py` bullet)
**Issue:** `_parent_branch.resolve()` is called independently at two separate SKILL.md locations reading the same `status_path` — `mill-merge/SKILL.md` Entry Step 4, and `mill-merge-in/SKILL.md` Entry Step 2 (invoked as `mill-merge`'s own Step 2, "picks up the parent from status.md the same way"). The Decision says "wrapping the existing `_parent_branch.resolve()` call site" (singular) and Technical Context echoes "this call site" — never confirming both locations need the wrap, so a plan could fix only one and leave the bug live via the other entry path (e.g. mill-merge-in run standalone).
**Fix:** State explicitly that the liveness check wraps both call sites (mill-merge's Entry Step 4 and mill-merge-in's Entry Step 2), and note the interactive vs non-interactive (`interactive=False` propagation) difference between them.

### [NIT:consistency] `-NN` archive-tag suffix claim unused and likely wrong
**Section:** Technical context (`_archive_tag.py` bullet) vs Decisions/817-dead-parent-detection
**Issue:** Technical context states the #817 chain-walk "needs to handle the `-NN` suffix form too when scanning for a match," but per `_archive_tag.create_or_resolve` the unsuffixed `archive/<slug>` is always force-updated/re-created to be the canonical current tag for a slug — `-NN` tags are only the moved-aside, superseded copies. The Decision's actual algorithm ("check for an `archive/<slug>` tag") never scans suffixes, so the two sections disagree on requirements.
**Fix:** Drop the `-NN`-handling claim from Technical context (unsuffixed lookup is sufficient), or justify why a superseded tag would ever need to be matched.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps: missing rollback exemption for the new FF-failure halt, and ambiguous #817 call-site scope.
MILL_REVIEW_END
