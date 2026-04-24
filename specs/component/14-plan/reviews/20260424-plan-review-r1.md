# Review: junction-rule enforcement + _paths.py consolidation — holistic r1

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnet-4-6 (via Agent tool)
reviewed_file: specs/component/14-plan/
date: 2026-04-24
```

## Findings

### [BLOCKING] Card 10 misses a stale `.millhouse/scratch/` reference in CLAUDE.md "Repo layout pointers"
**Location:** Batch docs / Card 10
**Issue:** `CLAUDE.md` line 47 (`plugins/mill/integration_tests/` — "Use `.millhouse/scratch/` for fixtures.") is inside the `## Repo layout pointers` section, not the `## Conventions worth carrying` section. Card 10's requirements only say to remove the scratch bullet from "Conventions worth carrying" and add a new `.scratch/` sibling line under the `.millhouse/wiki` pointer. The line-47 reference is left unedited — after the PR lands, CLAUDE.md will contain contradictory guidance: the new Path invariants section says `.scratch/`, but the Repo layout pointers still say `.millhouse/scratch/`.
**Fix:** Card 10's requirements must add: update the `integration_tests/` pointer (line 47) from "Use `.millhouse/scratch/` for fixtures" to "Use `.scratch/` for fixtures."

### [NIT] Card 7 describes variable names inconsistently
**Location:** Batch scratch-move / Card 7
**Issue:** Card 7 says "Each Python test has a module-level `SCRATCH = HUB / ".millhouse" / "scratch"`." The three review integration tests (`test-review-discussion.py`, `test-review-plan.py`, `test-review-code.py`) and `smoke-llm-claude.py` actually use the name `_SCRATCH` (underscore-prefixed), not `SCRATCH`. The find-replace description could mislead an implementer who searches only for `SCRATCH =` and misses `_SCRATCH =`.
**Fix:** Amend Card 7 to note: "Three review tests and `smoke-llm-claude.py` use `_SCRATCH` rather than `SCRATCH` — the edit is the same substitution; just note both forms when doing the pass."

### [NIT] `test-bootstrap.ps1` has two distinct scratch references — prose comment and variable
**Location:** Batch scratch-move / Card 7
**Issue:** `test-bootstrap.ps1` line 23 is a prose comment (`# Per conversation/SKILL.md: never use $env:TEMP; use .millhouse/scratch/ instead.`) and line 25 is the variable `$scratch = Join-Path $hubRoot '.millhouse' 'scratch'`. Card 7 mentions "a `$scratch` variable" but not the comment. After the move the comment text will be stale.
**Fix:** Card 7 should note: also update the comment on line 23 to reference `.scratch/` so it stays consistent with the new rule.

## Verdict

REQUEST_CHANGES
One blocking gap: Card 10 omits the stale `integration_tests/` scratch pointer in CLAUDE.md "Repo layout pointers". Two NITs on Card 7 description accuracy. Blocking is a one-line addition to Card 10's requirements; plan is otherwise sound and complete.
