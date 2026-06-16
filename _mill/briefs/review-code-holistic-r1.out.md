MILL_REVIEW_BEGIN
# Review: Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-16
```

## Findings

### [BLOCKING] Card 5: ROOD tests mock parent-diff instead of using real git fixture

**Location:** `plugins/mill/unit_tests/test-cleanliness.py:467-483` (ROOD-4)
**Issue:** Card 5 requirements explicitly state "Build the parent-diff via a real commit on a parent branch so `_parent_diff_names` returns the owned set." All four ROOD tests mock `_cleanliness._parent_diff_names` — no real git repo with a parent-branch commit is built. The shared decision "tests are unit-level, tempfile + real git, no LLM" is violated for the owned-set assertion.
**Fix:** Replace the `_parent_diff_names` mock in ROOD-4 (file-in-owned-set test) with a real `git init` + commit + branch fixture, matching the style already used in `test-finalize-cleanup.py`.

### [NIT] find_active_slug first-parameter name misleads nested-layout callers

**Location:** `plugins/mill/scripts/_review_common.py:274`
**Issue:** `find_active_slug(git_root: Path, ...)` names the first argument `git_root`, but both review CLIs now pass the hub root (not the git root) as the first argument after the batch-1 fix. The glob fallback `git_root / "_mill"` is correct in practice but the name implies the git root, making the contract opaque.
**Fix:** Rename the parameter to `hub_root` in the function signature and update the internal reference at line 283 (`hub_root / "_mill"`).

### [NIT] mill-finalize Path Setup still loads config with git_root as worktree_root

**Location:** `plugins/mill/skills/mill-finalize/SKILL.md:16`
**Issue:** Entry step 2 reads `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`. After the card-12 fix, `worktree_root` is correctly set to `_paths.resolve_hub_path()` in step 2.5, but the `load_config` call on line 16 still passes `git_root` as the `worktree_root` argument, which contradicts the nested-layout anchor decision.
**Fix:** Change the `load_config` call in step 2 to `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` (hub root for both args), consistent with the millpy-review-plan.py pattern.

## Verdict

REQUEST_CHANGES
One BLOCKING plan-alignment gap (owned-set test requires real git, not mocks) plus two NITs.
MILL_REVIEW_END
