MILL_REVIEW_BEGIN
# Review: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

Verified against source in the task worktree (not plugin cache): `mill-finalize/SKILL.md` lines 85-88 and `mill-merge/SKILL.md` lines 285-288 contain the byte-identical four-pathspec snippet cited (`:!<task_dir>`, `:!plugins/**/SKILL.md`, `:!plugins/**/unit_tests/**`, `:!plugins/**/integration_tests/**`), under Step 3 "Cleanup commit" (mill-finalize) and Step 4 "Cleanup commit" (mill-merge) respectively — matching the discussion's step/line citations exactly. `mill-merge-in/SKILL.md` is 258 lines, has no citation-scan step and zero `:!` occurrences — confirms the Scope-correction decision. A repo-wide `:!` grep across `plugins/` returns exactly these two lines, confirming the "no other occurrence" audit claim. No `CONSTRAINTS.md` exists at hub root, confirming that claim. The Testing section's `PYTHONPATH=` requirement is confirmed live in `_plan_validate.py`'s `verify-not-isolated` check, gated on `pyproject.toml` presence (present here) — consistent with CLAUDE.md.

All three `### Decision:` blocks carry rationale and explicit rejected alternatives. Scope in/out is unambiguous and each boundary is independently source-verified rather than merely asserted. No undecided items, no ambiguous language, no unaddressed failure mode (the fatal-parse-error mode is explicitly distinguished from the existing no-matches non-blocking behavior).

## Verdict

APPROVE
All claims independently verified against worktree source; no gaps found.
MILL_REVIEW_END
