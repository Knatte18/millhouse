MILL_REVIEW_BEGIN
# Review: mill-merge / mill-merge-in: brief-staging path bug and easy-to-miss caching instruction

```yaml
duration_s: 117.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: /home/knatte/Code/millhouse/wts/mill-merge-family-doc-gaps/_mill/discussion.md
date: 2026-09-19
```

## Findings

### [NIT:consistency] Testing section's verify command violates this repo's own verify-command-shape rule
**Demoted-from:** BLOCKING
**Section:** `## Testing`, "Verify command for the plan" bullet.
**Issue:** States the plan's verify command as bare `plugins/mill/unit_tests/run-all.py` with no `PYTHONPATH=` prefix and no `-k`/`--only` scope. `_plan_validate.py`'s `_check_verify_not_isolated` (requires `PYTHONPATH=` prefix for Python projects, confirmed via `pyproject.toml`/`plugins/mill/pyproject.toml` markers) and its `verify-full-suite` check (flags `run-all.py` with no filter) would both flag exactly this command; CLAUDE.md's "Verify command shape" section and `plugins/mill/templates/plan-batch.md` both mandate `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only <files>`.
**Fix:** Restate the Testing bullet as `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py` (or explicitly scope via `-k`), matching the enforced convention.

## Verdict

APPROVE
Testing section's stated verify command contradicts this repo's own enforced verify-command-shape convention.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
