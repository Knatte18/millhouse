MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [BLOCKING:scope] #900 fix understates `_review_common.load_config`'s blast radius
**Section:** Decisions / config-local-yaml-caller-alignment
**Issue:** The decision frames the fix as "the wrapper `_review_common.py` uses on behalf of `millpy-review-plan.py`," but `_review_common.load_config(hub_root, mill_dir)` is a shared function called from at least 7 more sites confirmed by source read: `millpy-review-code.py`, `millpy-validate-plan.py`, `millpy-review-summary.py`, `millpy-fix.py` (x2), `millpy-abandon.py` (x2), `millpy-merge-in-subagent.py` (x2), `millpy-implement.py` (x2). `millpy-implement.py:517` and `millpy-abandon.py:41` both pass the identical hub-anchored `mill_dir = project_root / ".millhouse"` pattern that #900 calls buggy for `millpy-review-plan.py`.
**Fix:** State explicitly whether the fix changes the wrapper globally (affecting all ~9 call sites, most of which currently pass the same hub-anchored pattern) or adds a narrow branch/param used only by `millpy-review-plan.py`'s call.

### [BLOCKING:design] Wrapper's dual use of `mill_dir` unaddressed by the git_root swap
**Section:** Decisions / config-local-yaml-caller-alignment
**Issue:** Confirmed via source read: `_review_common.load_config`'s `mill_dir` param is used twice — (1) `worktree_root = mill_dir.parent` (line 2757, feeds the delegate call the decision wants pointed at `git_root`), and (2) a separate direct read `local_path = mill_dir / "config.local.yaml"` (line 2772-2784) for the stale-`review:`-key warning. Swapping the second positional argument to `git_root` (as the decision literally proposes) breaks (2) — either the stale-key peek starts reading `git_root/config.local.yaml` (wrong file, doesn't exist) or the wrapper needs a new third parameter, neither of which the decision states.
**Fix:** Specify the wrapper's post-fix signature (e.g., add an explicit `git_root` param distinct from `mill_dir`) rather than "pass git_root ... as the second positional argument."

### [NIT:consistency] Step 8 relocation leaves renumbering unspecified
**Section:** Decisions / merge-lock-early-release
**Issue:** Moving "Step 8" to run before Steps 5.5/6/7 either leaves it out-of-numeric-order in the document or requires renumbering 5.5/6/7/8/9, and the PR-state gate's `merged` route lists steps in ascending numeric order (4, 5.5, 6, 7, 8, 9) that would need matching updates.
**Fix:** State whether Step 8 keeps its literal number (moved earlier, numbering left non-monotonic) or the sequence is renumbered.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps in the #900 caller-alignment fix's scope and mechanism.
MILL_REVIEW_END
