# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8) — 02-tests-and-skill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-tests-and-skill
date: 2026-05-06
```

## Findings

### [BLOCKING] Edit 3 targets the wrong element in Board discipline
**Step:** Card 5 — Edit 3
**Issue:** The plan says "Replace the final bullet 'No push from per-card commits — mill-merge pushes the task branch at task end.'". In the current SKILL.md, this text is the trailing sentence of the **first** bullet in `## Board discipline`, not a standalone bullet. The actual final bullet is "The path-invariant rule from CLAUDE.md is load-bearing…". An implementer following "the final bullet" replaces the wrong item; one searching for the quoted text finds it embedded mid-bullet and must guess whether to replace the sentence only or the whole bullet.
**Fix:** Change "Replace the final bullet" to "In the first bullet of `## Board discipline`, replace the trailing sentence 'No push from per-card commits — mill-merge pushes the task branch at task end.' with the new push-policy text (keeping the leading 'Status.md… are committed on the task branch…' sentence intact)."

### [NIT] Tests 5 and 5b reference undefined `review_file` variable
**Step:** Card 4 — Test 5, Test 5b
**Issue:** Both test bodies say `str(review_file)` in the `main()` call but never assign `review_file`; Test 4 explicitly spells out `tmp_path / "reviews" / "review.md"`.
**Fix:** Add `review_file = tmp_path / "reviews" / "review.md"` in each test body (or note it as the expected variable name).

### [NIT] Edit numbering is non-sequential (1, 2, 3, 4, 6, 5)
**Step:** Card 5 — overall
**Issue:** Edit 6 (Parse section) is presented before Edit 5 (Stuck escalation), creating a confusing out-of-order sequence.
**Fix:** Renumber in document-presentation order (1–6), or add a note that Edit 6 precedes Edit 5 deliberately.

## Verdict

REQUEST_CHANGES
Edit 3's "final bullet" identifier targets the wrong bullet in the current SKILL.md; the quoted text lives inside the first bullet, not the last.