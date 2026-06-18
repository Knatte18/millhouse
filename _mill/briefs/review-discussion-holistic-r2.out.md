All helper signatures confirmed. The discussion's Technical context is accurate. Note one detail: mill-merge Step 1 currently resolves `container_path` (line 21 calls `_paths.resolve_container_path(git_root)`) — confirmed available. The discussion's claim that `resolve_active_hub` inputs (`container_path`, `slug`, `cfg`, `git_root`) are all in hand is accurate.

I have verified all the load-bearing claims. The discussion is technically sound and well-grounded. Let me compose the review.

MILL_REVIEW_BEGIN
# Review: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-18
```

The discussion is technically sound and source-grounded. Verified against source: all helper signatures match (`resolve_active_hub(container_path, slug, *, cfg, git_root)` _paths.py:414; `resolve_task_path(worktree_root, cfg_relative_path)` :525; `_config.load_config(hub_root, worktree_root)` _config.py:193; `_parent_branch.resolve(status_path, *, interactive=True)` :61). The stale-code claims hold: mill-merge SKILL.md:35 still has `worktree_root = git_root`, line 21 still loads the obsolete `<wiki_path>/config.yaml`; mill-merge-in lines 13/54 use cwd-relative `Path("_mill/...").resolve()` while line 56 already uses `resolve_hub_path()`. The four already-fixed issues check out (#495 review-plan.py:102; #496 mill-go:529-530; #504/#505 `_cleanliness.revert_out_of_scope_drift` :151). Drift-guard premises verified: `wiki/_client.py` exists as a subpackage, `signature: _module.fn(` annotation convention is real (mill-plan:15-19), `run-all.py:58` auto-discovers `test-*.py` via glob. The `test-merge.py` fixture-path caveat is accurate (`container/"worktrees"/slug` at :90, not `wts/`). Decisions all carry rationale + rejected alternatives. Scope in/out is crisp. Testing strategy is concrete and TDD-anchored.

## Findings

### [NOTE] Drift-guard false-positive surface beyond subpackages
**Section:** Decisions › drift-guard scope; Testing
**Issue:** The `_<module>.<fn>(` regex will also match instance/local variables that happen to be underscore-prefixed (e.g. a SKILL writing `_status.read(` where `_status` is a local) and dunder/private method calls, which the resolver against `scripts/**/*.py` top-level functions cannot satisfy.
**Fix:** Note in the plan that the resolver matches against module-level `def`s only and that any legitimate non-module match goes in the allowlist, so the implementer expects and curates these rather than treating them as failures.

### [NOTE] mill-merge in-place mode interacts with hub-resolution change
**Section:** Scope › mill-merge 1.5 Path Setup
**Issue:** mill-merge Step 1.5 runs for both `worktree` and `inplace` modes; in in-place mode cwd is the hub and there is no separate worktree, so `resolve_active_hub` (which routes through `resolve_active_worktree` -> `container/"wts"/slug`) may not match the in-place layout.
**Fix:** Confirm in the plan that the chosen hub resolver behaves correctly (or is bypassed) in in-place mode, since the discussion only cites mill-go's worktree-mode usage as precedent.

## Verdict

APPROVE
Scope, decisions, and source claims are accurate and verifiable; two non-blocking notes for the plan.
MILL_REVIEW_END