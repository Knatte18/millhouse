MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] mill-merge:45's current `interactive=` value is mischaracterized
**Section:** Technical context / mill-merge / `_parent_branch.py`; Decision `stays-a-genuine-halt-list`
**Issue:** Source at `mill-merge/SKILL.md:45` reads `interactive=<True unless called non-interactively>`, not a plain `interactive=True` — this is already a conditional/templated value with no defined trigger anywhere else in the file (unlike mill-finalize's unconditional `interactive=False` at `mill-finalize/SKILL.md:34`, which the discussion cites correctly as the pattern to copy). The discussion's "switch to `interactive=False` too" framing implies today's call is a plain `True`, but doesn't address what "called non-interactively" currently means or resolves to, so a plan writer can't tell whether there's an existing mechanism to remove/replace vs. one to just delete.
**Fix:** Add a note clarifying that `<True unless called non-interactively>` has no current resolution mechanism in mill-merge/SKILL.md and should simply be replaced with a hardcoded `interactive=False`, matching mill-finalize.

## Verdict

GAPS_FOUND
One gap: mill-merge's current parent-branch-resolve call site is described imprecisely.
MILL_REVIEW_END
