# Batch: orchestrator-callers

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "orchestrator-callers"
number: 10
cards: 2
verify: null
depends-on: [9]
```

## Batch Scope

Points the two remaining orchestrators at batch 9's shared machinery: mill-start's Discussion Review
loop and mill-plan's Plan Review loop each print the per-round cost line, and each states that the
agent-mode `--duration-s` forwarding is the shared section's job rather than restating the
measurement mechanics locally. Both skills already delegate their agent-mode dispatch to
`plugins/mill/skills/mill-go-base/SKILL.md`'s `## Agent-mode dispatch`, so nothing about how the
duration is measured is duplicated here.

Documentation-only batch: no Python changes, so `verify: null`.

## Cards

### Card 37: mill-start prints the cost line

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase: Discussion Review`, at the numbered step that dispatches the round, extend the
  agent-mode paragraph (the one already instructing the skill to thread `--round` and
  `--agent-output` into the finalize invocation) with one sentence: the finalize invocation also
  carries `--duration-s`, supplied by the shared `## Agent-mode dispatch` section's reviewer-only
  measurement in `plugins/mill/skills/mill-go-base/SKILL.md`; `--tool-calls` and `--cost-usd` are
  never passed under agent-mode.
  Immediately after the post-dispatch tree-guard checkpoint paragraph that ends this dispatch step,
  add a new instruction to print the round's cost line per that same file's `## Review cost line`
  section, with `<type> = discussion` and `<scope> = holistic`, before step 3's
  `mill-receiving-review` confirmation. Apply the same addition to the step 4.5 ERROR-only retry
  dispatch, so a retried round reports its own cost too.
  In the subprocess/psmux branch, the three metrics come from the JSON summary line's `reviews[0]`;
  update that branch's inline description of the JSON summary shape to include the three new
  per-entry fields.
- **Commit:** `docs(mill-start): print the per-round review cost line`

### Card 38: mill-plan prints the cost line

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### Phase: Plan Review`, at step 2's dispatch-mode instruction, extend the agent-mode
  paragraph with the same sentence as card 37: the finalize invocation carries `--duration-s` from
  the shared `## Agent-mode dispatch` section's measurement, and never `--tool-calls`/`--cost-usd`.
  Immediately after that step's post-dispatch tree-guard checkpoint paragraph, add the instruction
  to print the round's cost line per `## Review cost line`, with `<type> = plan` and
  `<scope> = holistic` (the hub runs holistic-only plan review; state that a per-batch scope prints
  one line per scope should batch plan review ever be enabled). Apply the same addition to step
  4.5's ERROR-only retry dispatch.
  Update step 2's description of the subprocess/psmux JSON summary line so its documented
  `reviews[...]` entry shape includes `duration_s`, `tool_calls` and `cost_usd`.
- **Commit:** `docs(mill-plan): print the per-round review cost line`

## Batch Tests

`verify: null` — documentation-only, same rationale as batch 9: no `unit_tests/` file asserts on
SKILL.md prose, and both edits are cross-checked during review against the shared section batch 9
added and the CLI flags batch 7 shipped.
