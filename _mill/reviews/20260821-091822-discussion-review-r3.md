MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs

```yaml
duration_s: 192.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; brief-designated as sonnethigh)
reviewed_file: _mill/discussion.md
date: 2026-08-21
```

## Findings

### [NIT:consistency] #881 language-detection precedent omits a real 4th Python marker
**Demoted-from:** BLOCKING
**Section:** Decision #881, and Technical context's `_check_verify_full_suite` bullet.
**Issue:** Both the Decision text and CLAUDE.md describe the `verify-not-isolated` Python-detection precedent as three markers (`pyproject.toml`/`setup.py`/`setup.cfg`), but `_plan_validate.py`'s actual `is_python_project` (line ~1986) also OR's in `(project_root / "plugins" / "mill" / "pyproject.toml").exists()` — a 4th marker. This repo itself (`millhouse`) has no root-level `pyproject.toml`/`setup.py`/`setup.cfg` — only `plugins/mill/pyproject.toml` — so it is detected as a Python project *solely* via the omitted 4th marker.
**Fix:** Correct the Decision text (and flag the pre-existing CLAUDE.md drift) to name all four markers, so the #881 "shared language-detection helper" reused by both checks doesn't silently drop the nested-plugin marker and break Python detection for this self-hosted repo.

## Verdict

APPROVE
One BLOCKING: #881's cited language-detection precedent omits a real marker this repo relies on.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
