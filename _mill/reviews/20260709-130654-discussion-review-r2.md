I have verified the key claims against the source files. Here is my review.

MILL_REVIEW_BEGIN
# Review: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-09
```

## Findings

### [GAP] Unresolvable `--parent` ref reproduces silent-empty-scope
**Section:** Decisions -> "--parent flag takes unconditional precedence"; Technical context (`_no_arg_scope` change)
**Issue:** The decision has `_no_arg_scope` use `<parent>` directly and skip `_detect_base_branch()` entirely, but `parent:` in status.md is a branch *name* that may not resolve locally (e.g. a parent task branch already merged+deleted). Per current `resolve_scope.py` lines 121-124, `git diff <bad-parent>..HEAD` returns rc!=0, `committed` stays `[]`, no error surfaced. On a clean post-commit tree (the exact no-arg-on-task-branch case) `included_diff` is also 0 -> silent empty scope, codeguide-update does nothing. This is the same silent-wrong-scope failure class the task exists to fix.
**Fix:** Specify behavior when `--parent <ref>` fails `git rev-parse --verify`: fall back to `_detect_base_branch()`/`origin/<ref>`, or surface an explicit error -- do not silently emit empty committed scope.

### [NOTE] Broadened dispatch silently flips filename-that-is-a-refname to head-rev
**Section:** Decisions -> "Broaden single-token ref dispatch"; Testing
**Issue:** The new single-token `rev-parse --verify` probe fires only on `len(args)==1`. A bare single filename that also resolves as a branch/tag (e.g. a repo-root file named `main`) would route to `_head_rev_scope` instead of `_explicit_scope` -- the inverse of the bug being fixed. Scenario 10 and the new single-token regression only cover *non-resolving* paths.
**Fix:** Note this accepted edge in the decision, or add a single-token test where the path *does* collide with a ref name to pin the intended precedence.

### [NOTE] Cited precedent for `cfg['paths']['status_md']` is inaccurate
**Section:** Scope (git-commit Step 2); Decisions -> "New helper"; Technical context (git-commit mechanics)
**Issue:** The discussion prescribes `cfg['paths']['status_md']` and cites "mill-merge-in's Entry" as the precedent, but mill-merge-in SKILL.md line 13 actually uses the hardcoded literal `"_mill/status.md"` (as does mill-go line 185). The prescription is correct and matches the majority (mill-start, mill-plan, mill-go:43, mill-merge, git-pr, mill-finalize), but the citation contradicts itself and could mislead the plan writer.
**Fix:** Cite mill-start/mill-plan (which use the cfg key) as the precedent, or drop the mill-merge-in reference.

## Verdict

GAPS_FOUND
One unaddressed failure mode (unresolvable `--parent`) reproduces the silent-empty-scope bug; otherwise sound.
MILL_REVIEW_END