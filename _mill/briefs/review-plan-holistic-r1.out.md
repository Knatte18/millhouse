I have completed my verification. The plan is well-grounded. No BLOCKING issues. A few NIT-level observations follow.

MILL_REVIEW_BEGIN
# Review: Add first-class Moves/Renames field to plan cards for rename-heavy batches — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-29
```

## Findings

### [NIT] Card 18 line refs miss bulk-assembly sites
**Location:** Batch 4, Card 18
**Issue:** `_review_plan.py` assembles the source bulk in four places (`_review_one_batch` ~145, `prepare` per-batch ~327, `prepare` holistic ~407, `run` holistic ~733); the cited lines ~309/~583 are only the union-computation calls, and `_review_one_batch` receives unions as parameters (would need `moves_sources` threaded in).
**Fix:** Have Card 18 name all bulk-assembly sites (incl. `_review_one_batch`'s parameter) rather than two illustrative line numbers, so move sources reach the per-batch path too.

### [NIT] Move-source existence checked in two places
**Location:** Batch 2, Cards 6 + 8
**Issue:** Card 6 adds dedicated `move-source-missing`, while Card 8 also says to "treat Move sources via the same existence rule as general refs" in `_check_non_existent_path` — a genuinely missing source could emit two findings (`move-source-missing` and `non-existent-path`).
**Fix:** Clarify Card 8 to only add `moves_targets` to suppression (the real fix for downstream target edits), leaving source-existence solely to Card 6's check.

### [NIT] Redundant target-collision vs redundant overlap
**Location:** Batch 2, Cards 5 + 6
**Issue:** `move-redundant` (Card 5, same-batch Moves+Creates) and `move-target-collision` (Card 6, target in `creates_union`) both fire when a target collides with a Creates in the same batch — duplicate findings for that case.
**Fix:** Scope `move-target-collision`'s creates_union check to cross-batch collisions, or note the intended precedence in the cards.

### [NIT] CRLF handling in name-status parsing unspecified
**Location:** Batch 4, Card 20
**Issue:** `planned_rename_findings` parses `git diff --name-status` text; on Windows subprocess stdout may carry `\r\n`, and the card lists "malformed/blank" cases but not trailing-`\r` stripping.
**Fix:** Have Card 20 specify `splitlines()` (or explicit `\r` strip) and add a CRLF fixture to `test-moves-check.py`.

## Verdict

APPROVE
Sound, well-grounded plan; only minor edit-scope and dedup clarifications suggested.
MILL_REVIEW_END
