# Batch: mill-plan-auto-approve-wiring

```yaml
task: "Auto-approve on review-round cap"
batch: "mill-plan-auto-approve-wiring"
number: 2
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Wires the new `roles.plan-review.holistic.auto_approve_on_cap` config key (added in batch 1) into `mill-plan/SKILL.md`'s Phase: Plan Review step 6 ("Max-rounds escape"): when the flag is `true` and step 6's trigger condition would otherwise fire, reuse the exact terminal actions the file's existing "Live operator waiver of step 6" paragraph already documents (set `approved: true`, commit, push, proceed to Handoff) instead of halting — auto-triggered from config rather than requiring a live operator instruction. No batch-local decisions beyond the Shared Decisions ("config key shape", "commit-message suffix") this batch directly implements. `verify: null` — this batch edits only `mill-plan/SKILL.md`, a markdown orchestration-instruction file with no runnable surface of its own (mill-plan's own logic isn't executed by an automated test harness); correctness is validated by this plan's own Phase: Plan Review (holistic) round(s) and, downstream, by mill-go's Code Review round(s) on this task.

## Cards

### Card 4: Read `auto_approve_on_cap` in mill-plan's Entry step 2

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Entry`, step 2 ("Load config — deep-merge..."), the paragraph currently reads (in full): "Read `roles.plan-review.holistic.rounds` as `max_review_rounds`. Read `roles.plan-review.holistic.min_rounds` as `min_review_rounds` (default `1` when absent — see "Convergence gate" in Phase: Plan Review below)." Add one more sentence immediately after that: "Read `roles.plan-review.holistic.auto_approve_on_cap` as `auto_approve_on_cap` (default `False` when absent) — see "Live operator waiver of step 6" and step 6 "Max-rounds escape" in Phase: Plan Review below for its effect." Do not modify any other part of step 2 or the surrounding Entry steps.
- **Commit:** `mill-plan: read auto_approve_on_cap config key in Entry step 2`

### Card 5: Wire `auto_approve_on_cap` into step 6's "Max-rounds escape"

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits in `### Phase: Plan Review`, both within the same paragraph pair as the existing `**Live operator waiver of step 6.**` paragraph and the numbered step `6. **Max-rounds escape**` that follows it later in the phase.

  1. In the `**Live operator waiver of step 6.**` paragraph (currently: "The operator may separately give a live "waive remaining BLOCKINGs at cap" instruction. If given, the next time step 6's max-rounds-escape trigger condition would otherwise fire, treat it as an implicit-approve-at-cap instead of a halt — set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: approve plan for {slug} (operator waived remaining BLOCKINGs at round cap)"`), push, and proceed straight to Handoff, skipping step 6's `_status.set_blocked` halt for this occurrence. This instruction is independent of the round-cap-raise override above (an operator may raise the cap without waiving step 6, waive step 6 without raising the cap, or do both)."), append a new sentence at the end of the paragraph: "The same implicit-approve-at-cap terminal actions also fire automatically, with no live instruction needed, whenever `auto_approve_on_cap` is `True` (read at Entry step 2) — the only difference is the commit message, which for the config-driven trigger is `"mill-plan: approve plan for {slug} (auto-approved on round-cap exhaustion, config auto_approve_on_cap)"` instead of the operator-waiver message above; when both a live waiver and `auto_approve_on_cap: true` are in effect for the same occurrence, the live waiver's message wins (an explicit in-the-moment operator instruction is always the more specific signal)."

  2. In step `6. **Max-rounds escape**`, the parenthetical trigger condition currently reads: "(only when round counter exhausts without APPROVE, BLOCKINGs still remain, non-progress did not fire, AND the operator has not given a live step-6-waiver instruction — see "Live operator waiver of step 6" above; when that instruction was given, the implicit-approve-at-cap path documented there fires instead of this halt)". Replace it with: "(only when round counter exhausts without APPROVE, BLOCKINGs still remain, non-progress did not fire, the operator has not given a live step-6-waiver instruction, AND `auto_approve_on_cap` is not `True` — see "Live operator waiver of step 6" above; when either the live waiver or `auto_approve_on_cap: true` applies, the implicit-approve-at-cap path documented there fires instead of this halt)". Do not change anything else in step 6's body (the `_status.set_blocked` call, halt message, and `{M}` derivation are unaffected — they only run when this now-widened exclusion condition is false).
- **Commit:** `mill-plan: auto-approve plan review at round cap when auto_approve_on_cap is set`

## Batch Tests

No automated `verify:` — pure SKILL.md instruction edits (see Batch Scope for why). Acceptance is manual/integration per `_mill/discussion.md`'s Testing section: a hub with `roles.plan-review.holistic.rounds` set low (e.g. 1) and `auto_approve_on_cap: true`, run against a discussion/plan combination that reliably draws a `REQUEST_CHANGES` verdict from the plan reviewer, should reach Handoff (`phase: planned`) instead of `phase: blocked` after the single round's fix pass — vs. the same setup with the flag absent/false, which should still halt with `blocked_reason` starting `"max-rounds exhausted"` as today.
