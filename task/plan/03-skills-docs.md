# Batch: skills-docs

```yaml
task: 34 (A) — Config schema cleanup + reviewer registry
batch: skills-docs
number: 3
cards: 1
verify: null
depends-on: [2]
```

## Batch Scope

Pure documentation cleanup. Skill-doc references to the old `review.<type>.<key>` paths flip to the new `roles.<role>.<scope>.<key>` paths. No code, no tests, no runtime behaviour change. `verify: null` because there is no runnable surface — `run-all.py` does not exercise SKILL.md content.

## Cards

### Card 15: Update skill docs to reference new schema keys

- **Context:**
  - `task/discussion.md`
  - `wiki/config.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Sweep every reference to the old schema keys and rewrite to the new keys. Concrete edits:
  - `plugins/mill/skills/mill-go/SKILL.md`:
    - Line ~19 reference to `review.code.rounds` → `roles.code-review.batch.rounds` for the per-batch round cap; add a parallel sentence pointing at `roles.code-review.holistic.rounds` for the holistic cap.
    - Line ~20 reference to `review.code.self_fix_rounds` → `roles.implementer.self_fix_rounds`.
    - Line ~21 sentence `review.code.holistic — if true, run one holistic code review after all batches approve.` → `roles.code-review.holistic.reviewer — if non-null, run one holistic code review after all batches approve.`
    - Line ~22 reference to `review.code.holistic_rounds` → `roles.code-review.holistic.rounds`.
    - Line ~23 sentence about `review.code.per_batch` → `roles.code-review.batch.reviewer — if null (or rounds: 0), skip per-batch code review for all batches.`
    - Line ~106 conditional `If review.code.per_batch is false:` → `If roles.code-review.batch.reviewer is null (or rounds: 0):`.
    - Line ~112 round-counter loop: `For each round N from 1 to review.code.rounds:` → `For each round N from 1 to roles.code-review.batch.rounds:`.
    - Line ~140 sentence about `review.code.rounds` exhaustion → `roles.code-review.batch.rounds`.
    - Line ~162 holistic Guard expression: `cfg.get("review", {}).get("code", {}).get("holistic", True)` is truthy → `cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("reviewer") is not None`. The new condition is "a holistic reviewer is configured"; the old boolean `holistic: true` enabled the section by default, so the new default flips to "skip if no reviewer set" — which matches the schema's skip semantics (null reviewer = skip). Word the SKILL prose to make this explicit.
    - Lines ~164–166: `cfg.get("review", {}).get("code", {}).get("holistic_rounds", 1)` → `cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("rounds", 1)`. The `For each round H from 1 to max_holistic_rounds:` line stays unchanged (variable name preserved).
    - Line ~198 `Holistic review exhausted {max_holistic_rounds} round(s)…` reference stays unchanged (variable name preserved).
  - `plugins/mill/skills/mill-plan/SKILL.md`:
    - Line ~15 `Read review.plan.rounds as max_review_rounds.` → `Read roles.plan-review.holistic.rounds as max_review_rounds.` (the SKILL uses this single int as its review-round cap; the plan-review holistic scope is what gates plan-review iteration in mill-plan's loop).
    - Line ~78 `the review.code.self_fix_rounds self-fix pattern` → `the roles.implementer.self_fix_rounds self-fix pattern`.
    - Line ~106 sentence about `review.plan.batch` and `review.plan.holistic` config keys → `roles.plan-review.batch.reviewer` and `roles.plan-review.holistic.reviewer` config keys.
  - `plugins/mill/skills/mill-start/SKILL.md`:
    - Line ~15 `Read review.discussion.rounds as max_review_rounds.` → `Read roles.discussion-review.holistic.rounds as max_review_rounds.`
    - Line ~66 skip guard `If max_review_rounds == 0: skip straight to Handoff.` → `If max_review_rounds == 0 OR roles.discussion-review.holistic.reviewer is None: skip straight to Handoff.` The new schema has two skip conditions per the discussion's "Skip semantics" decision (`rounds: 0` OR `reviewer: null`); the SKILL must cover both. Capture the two conditions in a brief preceding sentence so the SKILL prose makes the why clear, not just the boolean.
  Run a final grep for `review\.\(code\|plan\|discussion\)\.` across `plugins/mill/skills/**/*.md` to confirm zero remaining matches before commit. If any other skill file (not in the Edits list) contains a match, halt — the planner missed a file. Do NOT silently edit a file that is not in the Edits: list.
- **Commit:** `docs(skills): update SKILL.md references to roles + registry schema`

## Batch Tests

`verify: null`. SKILL.md files have no runnable surface; the existing `run-all.py` does not exercise them. Manual smoke check after the batch lands: open each edited SKILL.md and confirm no `review.<type>.<key>` token remains, and that the new `roles.<role>.<scope>.<key>` token is grammatically integrated (not just a regex substitute).
