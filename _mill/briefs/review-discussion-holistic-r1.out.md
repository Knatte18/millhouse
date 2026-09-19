MILL_REVIEW_BEGIN
# Review: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

## Findings

### [BLOCKING:consistency] Verify command omits required `PYTHONPATH=` prefix
**Section:** Testing ("Manual verification (this task's `verify:` step)")
**Issue:** The literal `git grep ...` command given as "this task's `verify:` step" does not start with `PYTHONPATH=`. This repo has `plugins/mill/pyproject.toml`, so `_plan_validate.py`'s `_is_python_project` returns True and `_check_verify_not_isolated` requires every `verify:` command — regardless of whether it invokes Python — to start with the literal `PYTHONPATH=` prefix per CLAUDE.md's "Verify command shape" rule.
**Fix:** State the verify command as `PYTHONPATH= git grep ...` (or note mill-plan will auto-prepend it) so the plan writer isn't misled by the unprefixed form quoted here.

## Verdict

REQUEST_CHANGES
Testing section's quoted verify command contradicts the repo's PYTHONPATH= validator rule.
MILL_REVIEW_END
