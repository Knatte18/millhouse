# Batch: orchestrator-shared

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "orchestrator-shared"
number: 9
cards: 3
verify: null
depends-on: [7]
```

## Batch Scope

Teaches the shared orchestrator machinery to measure and report review cost. All three orchestrators
(mill-start, mill-plan, mill-go/mill-go2) route their reviewer dispatch through `## Agent-mode
dispatch` in `plugins/mill/skills/mill-go-base/SKILL.md`, so the agent-mode duration measurement and
the `--duration-s` forwarding land there once rather than at each of the eight-odd dispatch sites.
This batch also defines the one-line cost print's exact format in a new shared subsection and wires
it into mill-go's own two code-review loops; batch 10 points mill-start and mill-plan at the same
subsection.

Documentation-only batch: no Python changes, so `verify: null`.

## Cards

### Card 34: measure agent-mode dispatch duration

- **Context:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Agent-mode dispatch` section's step 3, immediately after the instruction to record the
  `agentId` and the actually-dispatched `model`, add a **reviewer-dispatch-only** instruction to
  record a wall-clock start stamp: run `date +%s` in the Bash tool immediately before the `Agent()`
  call and hold the value in a local variable (e.g. `review_start_epoch`), then run `date +%s` again
  the moment the terminal `<task-notification>` for that `agentId` is accepted and hold the
  difference as `review_elapsed_s`. State explicitly that this applies to reviewer dispatches only —
  implementer, fixer and merge-in dispatches record nothing, since reviewer cost visibility is this
  feature's whole scope.
  In step 4, add the summation rules: a case (a) transient re-dispatch keeps the earlier attempt's
  elapsed seconds and adds the fresh dispatch's own elapsed seconds to it, because the round
  genuinely cost both attempts; a case (c) probe that reports the agent is **still running** does
  NOT restart or reset the timer (one `Agent()` call, one continuous measurement, nothing to sum);
  a case (c) probe that reports the agent is **no longer running** or errors — including the
  reviewer-only `test -f <output_path>` shortcut's file-exists outcome — routes into (a)'s
  re-dispatch and therefore sums, exactly like (a).
  In step 6, add: for the three **review** CLIs only, pass `--duration-s <review_elapsed_s>` on the
  `--stage finalize` invocation alongside the existing `--agent-output`. Never pass `--tool-calls` or
  `--cost-usd` under agent-mode — the Agent tool notification contract carries no such signal, so
  those cells are legitimately `n/a`. Implementer, fixer and merge-in finalize invocations are
  unchanged.
- **Commit:** `docs(mill-go-base): measure reviewer dispatch duration in agent mode`

### Card 35: define the review cost line

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new `## Review cost line` section immediately after the `## Agent-mode dispatch` section,
  stating that it is the single source of truth for the post-round cost print in every orchestrator
  and that mill-start and mill-plan reference it rather than restating it.
  Contents:
  - When to print: once, immediately after each review round's JSON envelope is in hand, in both
    dispatch modes, before branching on the verdict. Print it for `ERROR` rounds too — an expensive
    failed round is exactly what the operator most needs to see.
  - Format:
    `[review] <type> r<N> (<scope>): <verdict>, <model>, <duration>, <tool_calls> tool-calls` with
    `, $<cost_usd>` appended only when `cost_usd` is non-null. Render a null `duration_s`,
    `tool_calls`, or `model` as the literal `n/a`; render duration as `<n>s` under a minute and
    `<m>m<ss>s` otherwise. ASCII only.
  - Where each field comes from: `type`, `round`, `verdict` and the three metrics from the
    envelope's `reviews[...]` entry for that scope; `model` from the prepare envelope's `model`
    field under agent-mode (or the recorded actually-dispatched tier when the operator overrode it),
    and from the round's configured `roles.<review-type>.<scope>.reviewer` alias under
    subprocess/psmux.
  - A note that this line is orchestrator chat output only — it is never written to a file, and the
    persisted copy of the same numbers lives in the review file's yaml header, readable later via
    `/mill-review-summary`.
- **Commit:** `docs(mill-go-base): define the per-round review cost line`

### Card 36: wire the cost line into both code-review loops

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### 3. Code Review loop`, at the numbered step beginning
  "**Builder reads only the JSON envelope verdict, never the findings.**", add a sentence
  instructing the Builder to print the cost line for this round per the `## Review cost line`
  section before it branches on the verdict, with `<type> = code` and `<scope> = <batch_name>`.
  Note explicitly that printing the cost line does not relax the read-ban: the Builder still never
  reads the findings, only the envelope fields the cost line names.
  In the holistic code review loop, add the same instruction to the paragraph that begins
  "**Exit handling.**" — after its existing sentences about the JSON envelope, with
  `<scope> = holistic`.
  Both additions are unconditional on dispatch mode.
- **Commit:** `docs(mill-go-base): print the review cost line in both code-review loops`

## Batch Tests

`verify: null` — this batch edits one SKILL.md and adds no runnable surface. Nothing in
`unit_tests/` asserts on SKILL.md prose, and inventing a text-matching test for it would be a new
convention this task has no mandate to introduce. Correctness is checked by plan review and code
review reading the edited section against the CLI flags batch 7 actually shipped.
