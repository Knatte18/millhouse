# Batch: mill-plan-source-edit-guardrail

```yaml
task: "Miscellaneous small tooling and doc/template accuracy gaps"
batch: "mill-plan-source-edit-guardrail"
number: 5
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Closes GitHub #623: `mill-plan/SKILL.md`'s Phase: Plan Review steps 4b/4c/4d ("apply fixes
to plan files" / "editing the plan files directly") never explicitly warn against the
failure mode where a reviewer finding names an exact source-code location that needs
reconciling with a plan card — it's easy to reflexively edit the real source file instead of
the plan card describing that future edit (a near-miss of exactly this happened once
already, caught and reverted manually). This batch adds one explicit guardrail sentence,
placed once so it covers all three fix-application branches (4b/4c/4d) uniformly. Pure
documentation edit, no executable surface. External interface for later batches: none. Note
for the implementer: this batch edits `mill-plan/SKILL.md`'s *content*, not the live
`mill-plan` skill governing this very task's own plan-review process — the edit takes effect
for future mill-plan runs, not retroactively for this one.

## Cards

### Card 11: add the source-edit guardrail sentence to Phase: Plan Review

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In "### Phase: Plan Review", insert one new guardrail sentence as its own
  paragraph, placed immediately after step 3's existing text ("**Confirm
  `mill-receiving-review` is loaded before evaluating or acting on this round's findings**
  ... Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps
  review loops useful.") and immediately before the `4a.` line that begins the fix-branch
  sequence (4a/4b/4.5/4c/4d). The sentence must read exactly: *"**Guardrail:** NIT/BLOCKING
  fixes during Plan Review apply ONLY to files under `<plan_dir>` — never to the actual
  source files the plan describes editing, even when a finding quotes an exact source
  location."* Do not duplicate this sentence inline at 4b, 4c, and 4d individually — one
  placement immediately before the branches begin is sufficient, since every one of steps
  4a/4b/4c/4d is reached only after this point in the step sequence (matches
  `_mill/discussion.md`'s `mill-plan-source-edit-guardrail (#623)` Decision, which leaves
  exact placement to this batch's discretion as long as the text precedes every
  fix-application step a Builder could reach).
- **Commit:** `docs(mill-plan): guard against editing source files instead of plan files`

## Batch Tests

`verify: null` — a SKILL.md instructional-text change only, no executable surface. Verified
by plan/code review reading the guardrail sentence for clarity and correct placement, per
`_mill/discussion.md`'s Testing section for #623.
