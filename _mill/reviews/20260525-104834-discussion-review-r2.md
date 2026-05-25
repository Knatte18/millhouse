# Review: Isolate verify PYTHONPATH so tests validate worktree code

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-25
```

## Findings

### [NOTE] `_read_batch_frontmatter` guidance misleads implementer
**Section:** Technical context → Validator changes
**Issue:** Discussion says "look for `_read_batch_frontmatter` import" in `_plan_validate.py`, but that symbol is not imported there — the in-module convention (confirmed by `_check_depends_on_batch_mismatch` at line 534–549) is inline yaml extraction: read text, find fenced block, `yaml.safe_load`.
**Fix:** Drop the "look for `_read_batch_frontmatter`" clause; just say "use the inline frontmatter extraction pattern already in `_plan_validate.py` (see `_check_depends_on_batch_mismatch`)."

### [NOTE] Coverage scenario "(top-level + batch)" is ambiguous
**Section:** Testing → Coverage scenarios
**Issue:** "Two unprefixed verify strings (top-level + batch)" implies the overview top-level `verify:` produces a validator error, but that field is explicitly excluded by the `validator-check-shape` decision.
**Fix:** Reword to "Two batch files both with unprefixed `verify:`" to match the actual validator scope.

## Verdict

APPROVE
Discussion is technically sound with two minor wording issues in non-blocking guidance.