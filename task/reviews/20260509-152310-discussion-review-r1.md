# Review: 34 (A) — Config schema cleanup + reviewer registry

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [GAP] `--max-rounds` semantics undefined after batch/holistic split
**Section:** Technical Context — Files that read the old `review.*` keys
**Issue:** Both `_review_plan.py:287` and `_review_code.py:183` use a single `max_rounds` integer that currently gates all rounds regardless of scope. After the split, batch and holistic each own their own `rounds`. The discussion says help-text must change to `roles.X-review.<scope>.rounds` but a single `--max-rounds <N>` flag has no scope — the decision of whether it overrides batch rounds, holistic rounds, or both is never made.
**Fix:** Add a decision: does `--max-rounds <N>` override both scopes, or is the flag split into `--max-batch-rounds` / `--max-holistic-rounds`? The plan writer cannot implement the CLI changes without this.

### [NOTE] `reviewer.MODE` occurrence count is off by one
**Section:** Technical Context — Files that load reviewer modules
**Issue:** Discussion states "currently 7 occurrences" of `reviewer.MODE`, but grep finds 8 across the three backends (`_review_code.py` lines 263 and 265, `_review_discussion.py` lines 72 and 75, `_review_plan.py` lines 145, 150, 457, and 461).
**Fix:** Correct the count to 8; no planning impact but worth accurate tracking.

## Verdict

GAPS_FOUND
`--max-rounds` CLI semantics are unresolved after the batch/holistic split; needs a decision before plan writing.