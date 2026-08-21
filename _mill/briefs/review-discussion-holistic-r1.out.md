MILL_REVIEW_BEGIN
# Review: mill-go-base/mill-merge: documented step behavior diverges from underlying script capability

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (Anthropic)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:design] check_helpers guard does not detect #856's actual failure mode
**Section:** Scope (#856) / Technical Context — `_preflight.check_helpers`
**Issue:** `_preflight.missing_helpers` (`plugins/mill/scripts/_preflight.py` lines 25-40) only checks `(scripts_dir / f"{name}.py").exists()` — whole-file presence, not attribute presence. `check_liveness` (#817) lives inside the *same* `_parent_branch.py` file as the long-established `resolve()` (verified: `plugins/mill/scripts/_parent_branch.py`). A stale cache with an old `_parent_branch.py` (pre-#817, has `resolve()` but not `check_liveness`) passes `check_helpers(['_parent_branch'])` (file exists) and still crashes with `AttributeError` at the very call the guard is meant to protect. The Step 5.5 precedent it claims to mirror guards a *different* failure class — `_archive_tag.py` (standalone, single-function module, confirmed via `plugins/mill/scripts/_archive_tag.py`) being entirely absent from the cache (ModuleNotFoundError), not a stale-but-present file missing one function.
**Fix:** Either specify an attribute-level check (e.g. `hasattr(_parent_branch, 'check_liveness')`) as part of #856's scope, or explicitly document why file-level presence is deemed sufficient for this case.

### [BLOCKING:consistency] #850-test-coverage names the wrong branch for its own cited fixture
**Section:** Decisions → #850-test-coverage
**Issue:** The decision says to assert the `MarkerError` message "names branch `foo`" using the existing `test_slug_from_branch_detached_head` fixture. That fixture calls `_make_task_worktree(tmp, "foo", ..., branch_prefix="hanf/", ...)`, which creates and checks out branch `f"{branch_prefix}{slug}"` = `"hanf/foo"` (verified in `plugins/mill/unit_tests/_test_helpers.py` lines 205-214), not `"foo"`. `current_branch`/local-branch enumeration reads git's actual branch name, so the message would name `hanf/foo`, not `foo`.
**Fix:** Correct the decision text to assert `hanf/foo`, or specify a fresh fixture with an empty `branch_prefix` if `foo` is truly the intended asserted value.

### [NIT:consistency] mill-merge-in liveness-check citation off by one call site
**Section:** Technical Context — mill-merge-in/SKILL.md line 23
**Issue:** The `check_liveness(...)` call site is at line 21, not line 23; line 23 is the `resolve_dead_parent(...)` call in the dead-parent branch (verified in `plugins/mill/skills/mill-merge-in/SKILL.md`).
**Fix:** Cite line 21 as the guard's insertion point.

## Verdict

REQUEST_CHANGES
Two BLOCKING issues: the #856 guard mechanism doesn't cover its target failure mode, and #850's test decision misnames its own fixture's branch.
MILL_REVIEW_END
