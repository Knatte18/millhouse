# Review: 3 (A) — codeguide improvements: sibling placement + --branch flag — 01-codeguide-generate-skill

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-codeguide-generate-skill
date: 2026-05-05
```

## Findings

### [NIT] `project_path` not bound before Card 2 uses it
**Step:** Card 2 requirements
**Issue:** The placement formula `<sibling_anchor>/<project_path.relative_to(git_toplevel)>/_codeguide/` references `project_path`, which Card 1 does not introduce and is not an output of `resolve.py --json`. An implementer writing Step 9 prose must infer that it means "the path of the project currently being documented" from SKILL.md's broader context.
**Fix:** Add one phrase to Card 2's requirements: "…where `project_path` is the source project directory being documented (established by the `$ARGUMENTS` scope in Step 5)."

## Verdict

APPROVE
Both cards are precise, well-scoped, and fully aligned with the discussion and `resolve.py` implementation.