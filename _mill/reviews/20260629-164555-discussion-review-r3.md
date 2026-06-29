I have verified the discussion's technical claims against source. The key claims hold. The discussion is technically grounded and rounds 1-2 resolved the substantive issues. Remaining observations are minor.

MILL_REVIEW_BEGIN
# Review: Add first-class Moves/Renames field to plan cards for rename-heavy batches

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-29
```

## Findings

### [NOTE] Mechanic-section presence has no deterministic check
**Section:** Decisions / mechanic-in-plan-not-brief, verification-scope
**Issue:** Presence of the `## Rename mechanic` section on a non-empty-`Moves:` batch is enforced only by the plan-review LLM criterion; there is no `_plan_validate.py` check, despite this being the task's primary prevention lever and the premise being that LLM instructions get ignored.
**Fix:** Consider noting whether a trivial deterministic check ("non-empty Moves implies `## Rename mechanic` present") should accompany the LLM criterion, or explicitly state LLM-only enforcement is intended.

### [NOTE] Rename+extraction representation not spelled out
**Section:** Scope / Decisions, Technical context
**Issue:** The motivating workload is "module renames + kernel extractions," but `Moves:` is strictly 1:1 pairs; how a file split into a relocated target plus a newly extracted file is expressed (e.g. `a -> b` in Moves AND `c` in Creates) is never stated, leaving a plan writer to infer it.
**Fix:** Add one sentence clarifying that the extracted-to file is a `Creates:` while the relocated file is the `Moves:` pair (and that `move-redundant` permits this since the paths differ).

## Verdict

APPROVE
Scope, decisions, and verification layers are complete and source-accurate; only minor clarifying notes remain.
MILL_REVIEW_END
