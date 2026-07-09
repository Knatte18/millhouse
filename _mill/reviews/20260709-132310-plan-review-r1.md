MILL_REVIEW_BEGIN
# Review: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-09
```

## Findings

### [BLOCKING] Card 7 uses `cfg` with no load step / `_config.py` absent
**Location:** Batch 3 / Card 7
**Issue:** Requirement (a) resolves `status_path` via `_paths.resolve_task_path(hub_root, cfg['paths']['status_md'])` and forbids the `_mill/status.md` literal, but git-commit's SKILL.md loads no `cfg` today, the card gives no instruction to load it (nor a `git_root` for `_config.load_config`), and `_config.py` is not in `Context:` -- forcing cold-start exploration.
**Fix:** Either add `_config.py` to Context with an explicit `_config.load_config(hub_root, git_root)` step, or mirror mill-merge-in Step 2's established pattern `_paths.resolve_task_path(resolve_hub_path(), "_mill/status.md")` and drop the "do not hardcode" instruction.

### [NIT] Card 3 Scenario 14 assertion contradicts `<base>..HEAD` semantics
**Location:** Batch 1 / Card 3, Scenario 14
**Issue:** `git diff mill-checkpoint-feature..HEAD` yields commits *after* the checkpoint on HEAD's side; the checkpoint branch's own commits are excluded. The assertion "path set matches the files committed on `mill-checkpoint-feature`" is inverted, and "stay on it and diff from a descendant" leaves HEAD == checkpoint (empty diff).
**Fix:** Reword: point `mill-checkpoint-feature` at the base, add commits on a descendant HEAD, and assert the path set equals the files added *between* checkpoint and HEAD (mirroring Scenario 8's `HEAD~3` semantics literally).

### [NIT] `enumerate_scope` docstring signature not updated for `parent`
**Location:** Batch 1 / Card 2 (and Card 1's docstring edits)
**Issue:** Card 2 adds `parent: str | None = None` to `enumerate_scope`, but neither card updates the module docstring's `Function: enumerate_scope(args, cwd=None) -> ...` line (resolve_scope.py:35), leaving the documented API stale.
**Fix:** Have Card 2 append the new kwarg to that docstring line alongside the CLI-usage update Card 1 already makes.

## Verdict

REQUEST_CHANGES
Sound design; Card 7's cfg gap blocks implementation, two test/doc nits.
MILL_REVIEW_END