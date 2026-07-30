# Batch: mill-plan-entry-wait

```yaml
task: Blocking phase-wait gate for mill-plan/mill-go chaining
batch: mill-plan-entry-wait
number: 3
cards: 1
verify: null
depends-on: [1]
```

## Batch Scope

Wires the shared `_phase_wait.py` helper (batch 1) into mill-plan's own
entry-gate phase table (`plugins/mill/skills/mill-plan/SKILL.md`, Entry
step 4). Carves `phase: discussing` (mill-start still in flight) out of
the existing catch-all "any other phase" halt row and replaces it with
an automatic blocking wait (gated by `pipeline.entry_wait`), reusing the
same `Monitor`-based mechanism as batch 2's mill-go wiring but with a
narrower trigger set — no regex widening is needed here (see the card's
Requirements for the verified reason). This is its own batch, separate
from batch 2, because the two edits touch unrelated files with no
shared card-level context beyond the already-independent
`_phase_wait.py` helper.

## Cards

### Card 5: Blocking entry-gate wait in mill-plan for phase `discussing`

- **Context:**
  - `plugins/mill/scripts/_phase_wait.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  **1. Carve `discussing` out of the catch-all row.** In Entry step 4's
  table (the fenced markdown table with header `| state | action |`),
  locate the exact existing row:

```
   | any other phase (`discussing`, `planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |
```

  Replace it with two rows — the new `discussing` row placed immediately
  before the narrowed catch-all, both at the same 3-space indentation as
  the original:

  ```
   | `phase: discussing` | wait for `phase: discussed` (see "Entry-gate wait for upstream mill-start" below) if `pipeline.entry_wait` is true; otherwise tell user what phase is set and halt |
   | any other phase (`planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |
  ```

  Every other row in this table (`phase: discussed` with no `plan_dir`,
  `phase: planning`/`plan-review-*`/`plan-fix-*` with `approved: false`,
  `approved: true` in overview frontmatter) is unchanged.

  **2. Document the two new config keys.** In this same skill's step 2
  (config loading, which currently reads `roles.plan-review.holistic.rounds`
  as `max_review_rounds`), add a sentence noting that Entry step 4's new
  `discussing` row additionally reads two `pipeline.*` keys at the point of
  use (see the new subsection added in requirement 3 below):
  `pipeline.entry_wait` (master on/off switch, default `true` if absent)
  and `pipeline.entry_wait_timeout_minutes` (give-up timeout in minutes,
  default `120` if absent).

  **3. Add the wait-handling subsection.** Immediately after Entry step
  4's table, add a new subsection (e.g. `### Entry-gate wait for upstream
  mill-start`) describing the following procedure, to run whenever the
  phase-table lookup lands on the new `discussing` row from step 1 above:

  - Compute the match using
    `_phase_wait.matches_wait_trigger(phase, {"discussing"}, [])` — no
    regex widening on this side. This is deliberate, not an oversight:
    mill-start's `discussion-fix-r{N}` phase value (written mid-loop
    during its own Discussion Review, per `mill-start/SKILL.md`'s step
    4b) is always folded into the same commit as the immediately
    following `discussed` write and is never itself pushed as a
    standalone, externally observable phase; and mill-start's
    GAPS_FOUND loop makes no `_status.append_phase` call at all. The
    entire span of mill-start's active work — including every round of
    its own review loop, in both branches — is therefore already fully
    covered by the single exact value `discussing`, unlike mill-go's side
    (batch 2), where mill-plan's own Plan Review loop commits its
    approve-phase and its Handoff-phase as separate, independently
    observable commits.
  - Read `entry_wait = (cfg.get("pipeline") or {}).get("entry_wait", True)`.
  - **If `matches_wait_trigger` is `True` and `entry_wait` is `True`:**
    - Read `timeout_minutes = (cfg.get("pipeline") or {}).get("entry_wait_timeout_minutes", 120)` and compute `giveup_s = timeout_minutes * 60`.
    - Build the command: `cmd = _phase_wait.build_wait_command(status_path, "discussed", 10, giveup_s)`.
    - State one sentence to the user: waiting for the upstream mill-start
      run to reach `phase: discussed`.
    - Call the `Monitor` tool with `command=cmd`, `persistent: true`,
      `description` naming the slug and the target phase (e.g. "waiting
      for phase: discussed (mill-start handoff) for `<slug>`"). Do not set
      a `timeout_ms` value distinct from the default — `persistent: true`
      makes it irrelevant. This is never a decision point: state what is
      being waited for, then wait, with no `AskUserQuestion` or free-text
      prompt in between (mill-plan is autonomous outside its own
      documented escape hatches; this wait introduces no new one).
    - **Record the `task_id` the `Monitor` tool call returns** in a local
      orchestrator variable and retain it for the duration of this wait.
    - Wait for the `<task-notification>`. A `Monitor` run of this poll
      script delivers exactly one per-line event notification (the single
      `READY` / `BLOCKED: ...` / `TIMEOUT after ...` line the script
      echoes before exiting, carried in that notification's `<event>`
      tag), immediately followed by a second, separate terminal
      notification (`<status>completed</status>`, no `<event>` tag) once
      the script's process actually exits — this two-notification shape
      (confirmed by a live spike during this task's plan review, not
      assumed from the Agent tool's differently-shaped single-result
      notification) is expected and requires no special handling: act on
      the first notification's `<event>` content; the second, event-less
      completion notification for the same `task_id` carries no further
      information and needs no separate branch. Branch on the `<event>`
      content:
      - **`READY`** — re-run Entry step 4 from its top: re-read
        `status_path` fresh and re-evaluate the whole entry-branch table
        again from scratch (do not assume `discussed` is now the phase and
        jump straight to Phase: Plan).
      - **`BLOCKED: <reason>`** — halt immediately, surfacing `<reason>`
        to the operator. mill-plan's phase table has no pre-existing
        `blocked` row to reuse the exact message shape from (unlike
        mill-go's side) — halt with a message of the same shape mill-plan
        already uses elsewhere for a `BLOCKED:`-prefixed halt (e.g. the
        Plan Review non-progress/max-rounds `_status.set_blocked` halts):
        state the phase is blocked and surface `<reason>` verbatim. Do not
        re-arm the wait automatically.
      - **`TIMEOUT after <N>s waiting for phase: discussed`** — halt with
        a message distinct from the `BLOCKED` case: state that the
        configured give-up period (`pipeline.entry_wait_timeout_minutes`)
        elapsed without mill-start reaching `phase: discussed`, and that
        the operator should check on the upstream mill-start session (it
        may be abandoned, still legitimately working past the give-up
        window, or never started) and re-run `/mill-plan` to re-arm the
        wait if it is in fact still in progress.
    - **If the wait itself is stopped/interrupted at the harness level**
      (a `TaskStop` or equivalent operator-level cancellation of the
      recorded `task_id`, rather than one of the three outcomes above):
      no automatic retry. Halt with a short message telling the operator
      the wait was cancelled and that re-running `/mill-plan` will
      re-evaluate the phase (proceeding immediately if it has since become
      ready, or re-arming the wait if not).
  - **If `matches_wait_trigger` is `True` but `entry_wait` is `False`:**
    fall back to the original catch-all action for this phase — tell the
    user what phase is set (`discussing`) and which skill should run
    instead (mill-start), and halt.
  - **If `matches_wait_trigger` is `False`:** the phase is not
    `discussing`; fall through to the narrowed catch-all row from step 1.

  Do not modify any other row of the Entry step 4 table, Phase: Plan,
  Phase: Plan Review, or Phase: Handoff. This card's edit is additive: the
  existing `discussed`-fresh-write / `planning`-or-`plan-review-*`-or-
  `plan-fix-*`-with-`approved:-false` / `approved:-true` rows and their
  actions are byte-for-byte unchanged.

- **Commit:** `mill-plan: blocking entry-gate wait for phase discussing`

## Batch Tests

`verify: null` — this batch is a pure prose edit to a SKILL.md file with
no runnable code surface, for the same reason given in batch 2's Batch
Tests: the live `Monitor` tool dispatch is a harness behavior outside
`unit_tests/`/`integration_tests/` reach, and the only genuinely testable
logic (`_phase_wait.matches_wait_trigger`'s narrower `{"discussing"}`,
`[]` behavior, including that it does NOT match `discussion-fix-r1`) is
already covered by batch 1's `test-phase-wait.py` (case 12). Manual
verification path: the existing plan-review/code-review loops apply to
this SKILL.md edit unchanged.
