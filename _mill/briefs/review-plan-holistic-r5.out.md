MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently verifiable)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:design] Card 10's rollback-fix repro never checks out `main`, so its assertions don't test what it claims
**Location:** batch 4 (`04-integration-tests.md`), Card 10, steps 3-6
**Issue:** Step 3 checks out a throwaway branch on `parent_rb` to create `mill-checkpoint-demo` and never checks back out to `main` (unlike sibling Cards 9 and 12, which explicitly `checkout main`/"Check back out to main afterward" before their own repro/assertion steps). Steps 4-6's `reset --hard` + `rev-parse HEAD` assertions therefore operate on whatever branch is currently checked out (the throwaway branch), not on `main` — the parent worktree's actual branch in production, where `-C <parent-path>` always targets the single checked-out branch. The assertions pass trivially regardless of which branch is checked out, so the test doesn't actually prove `main` gets corrupted (repro) or correctly landed on `origin/main` (fix); it only proves `reset --hard <ref>` moves HEAD, which is git's documented behavior and not what #824 is about.
**Fix:** After creating `mill-checkpoint-demo` in step 3, add an explicit `git -C parent_rb checkout main` before step 4's repro assertion, matching Card 9/Card 12's convention.

### [BLOCKING:scope] Card 6's inserted bash blocks reference `_config`/`_paths` functions not listed in Context
**Location:** batch 2 (`02-mill-merge-skill-fixes.md`), Card 6
**Issue:** The card's Requirements insert literal bash blocks calling `_config.load_config`, `_paths.resolve_hub_path`, `_paths.resolve_container_path`, `_paths.resolve_active_hub`, `_paths.resolve_task_path`, and `_paths.resolve_git_root`, but Card 6's `Context:` lists only `_parent_branch.py` and `_status.py` — `_config.py` and `_paths.py` are absent from both `Context:` and `Edits:`, triggering the Context-completeness criterion.
**Fix:** Add `_config.py` and `_paths.py` to Card 6's `Context:` list (mitigated in practice since identical patterns already appear in `mill-merge/SKILL.md` itself, which Card 6 edits and thus implicitly reads in full — but the letter of the criterion still requires the explicit entry).

## Verdict

REQUEST_CHANGES
Card 10's fixture never re-checks-out `main`, weakening its own assertions; Card 6 is missing two Context entries.
MILL_REVIEW_END
