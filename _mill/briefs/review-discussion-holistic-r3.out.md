MILL_REVIEW_BEGIN
# Review: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-09
```

Discussion is thorough and source-grounded. Verified against `resolve_scope.py` (dispatch chain, `_no_arg_scope`, `_head_rev_scope` `f"{token}..HEAD"`, hex-only `_HEX_RE`, argparse `nargs="*"`), `_parent_branch.py` (`resolve(status_path, *, interactive)` + `_read_parent_from_status` + `ParentBranchError`), `codeguide-update/SKILL.md` Step 2 (`resolve_scope.py $ARGUMENTS` passed verbatim, so `--parent` threads through cleanly), `git-commit/SKILL.md` Step 2, `mill-merge-in/SKILL.md` line 110 (the malformed `git diff "$CHK"..HEAD` string), `test-resolve-scope.py` (13 scenarios; scen 3/8/10 shapes as described), and `_paths.resolve_task_path(worktree_root, cfg_relative_path)` (the `resolve_task_path(hub_root, cfg['paths']['status_md'])` form matches git-pr/mill-start/mill-plan usage). All claims hold; the round-2 unresolvable-`--parent` fallback gap is now covered in Decisions and Testing. Zero GAPs.

## Findings

### [NOTE] Fix efficacy hinges on recorded parent != main
**Section:** Problem / Testing (integration)
**Issue:** The fix only narrows a stacked branch if status.md's `parent:` holds the *immediate* parent; `_spawn_core.capture_parent_branch` records hub HEAD at spawn time, so a task spawned while the hub sat on `main` records `parent: main` and `--parent main` reproduces the wrong-base scope.
**Fix:** State this dependency; have the proposed integration test assert the recorded `parent:` is the non-main immediate parent so the actual #617/#621 repro is genuinely exercised.

### [NOTE] codeguide-update Scope docs go stale re: --parent
**Section:** Scope (Out) / Decisions
**Issue:** `codeguide-update/SKILL.md` lines 19-26 document `$ARGUMENTS` as no-arg/time/`HEAD~N`/paths and call parent detection "git-native" only; after the fix a mill caller passes an undocumented `--parent` that overrides that detection, leaving a maintainer no breadcrumb for the flag flowing through.
**Fix:** Even keeping `--parent` mill-only, add a one-line internal note in codeguide-update Step 2 that `resolve_scope.py` accepts a `--parent` override so the doc doesn't silently misdescribe behavior.

## Verdict

APPROVE
Complete and source-verified; two non-blocking NOTEs on repro validation and doc staleness.
MILL_REVIEW_END