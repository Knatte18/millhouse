# Batch: mill-go-entry-wait

```yaml
task: Blocking phase-wait gate for mill-plan/mill-go chaining
batch: mill-go-entry-wait
number: 2
cards: 1
verify: null
depends-on: [1]
```

## Batch Scope

Wires the shared `_phase_wait.py` helper (batch 1) into mill-go's own
entry-gate phase table (`plugins/mill/skills/mill-go/SKILL.md`, "Entry
phase gate" step). Widens the trigger match to also cover mill-plan's
transient `plan-review-r{N}` / `plan-fix-r{N}` mid-loop and pre-Handoff
phase values, and replaces the current unconditional halt with an
automatic blocking wait (gated by `pipeline.entry_wait`) using the
harness `Monitor` tool. This is its own batch, separate from the
mill-plan-side wiring (batch 3), because the two edits touch unrelated
files with no shared card-level context beyond the already-independent
`_phase_wait.py` helper.

## Cards

### Card 4: Blocking entry-gate wait in mill-go for phase `discussed`/`discussing`/`planning`/`plan-review-r{N}`/`plan-fix-r{N}`

- **Context:**
  - `plugins/mill/scripts/_phase_wait.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  **1. Widen the phase-table row.** In the "Entry phase gate" step's phase
  table (the fenced markdown table with header `| phase | action |`),
  locate the exact existing row:

  ```
   | `discussed` / `discussing` / `planning` | tell user to finish mill-plan and halt |
  ```

  Replace it with:

  ```
   | `discussed` / `discussing` / `planning`, or matching `^plan-review-r\d+$` / `^plan-fix-r\d+$` | wait for `phase: planned` (see "Entry-gate wait for upstream mill-plan" below) if `pipeline.entry_wait` is true; otherwise tell user to finish mill-plan and halt |
  ```

  Preserve the row's original 3-space indentation and its position
  between the `blocked` row above it and the `done` row below it. Every
  other row in this table is unchanged.

  **2. Document the two new config keys.** In this same skill's step 3
  (the numbered list of `pipeline.*`/`roles.*` config keys read at Entry,
  e.g. `pipeline.auto_merge`, `pipeline.auto_report`), add two new bullets
  in the same style:
  - `pipeline.entry_wait` — master on/off switch for the entry-gate
    blocking wait (default `true` if the key is absent).
  - `pipeline.entry_wait_timeout_minutes` — give-up timeout in minutes for
    the entry-gate wait (default `120` if the key is absent).

  **3. Add the wait-handling subsection.** Immediately after the phase
  table (and its surrounding code block showing `status = _status.read_full(status_path)` /
  `phase = status["yaml"]["phase"]`), add a new subsection (e.g. `###
  Entry-gate wait for upstream mill-plan`) describing the following
  procedure, to run whenever the phase-table lookup lands on the widened
  row from step 1 above:

  - Compute the match using
    `_phase_wait.matches_wait_trigger(phase, {"discussed", "discussing", "planning"}, [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"])`.
  - Read `entry_wait = (cfg.get("pipeline") or {}).get("entry_wait", True)`.
  - **If `matches_wait_trigger` is `True` and `entry_wait` is `True`:**
    - Read `timeout_minutes = (cfg.get("pipeline") or {}).get("entry_wait_timeout_minutes", 120)` and compute `giveup_s = timeout_minutes * 60`.
    - Build the command: `cmd = _phase_wait.build_wait_command(status_path, "planned", 10, giveup_s)`.
    - State one sentence to the user: waiting for the upstream mill-plan
      run to reach `phase: planned`.
    - Call the `Monitor` tool with `command=cmd`, `persistent: true`,
      `description` naming the slug and the target phase (e.g. "waiting
      for phase: planned (mill-plan handoff) for `<slug>`"). Do not set a
      `timeout_ms` value distinct from the default — `persistent: true`
      makes it irrelevant, matching the existing "Waiting is never a
      decision point" convention already documented for Agent-mode
      dispatch elsewhere in this file: state what is being waited for,
      then wait, with no `AskUserQuestion` or free-text prompt in between.
    - **Record the `task_id` the `Monitor` tool call returns** in a local
      Builder variable and retain it for the duration of this wait
      (mirrors the existing "record the `agentId`" step in "## Agent-mode
      dispatch" above).
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
      - **`READY`** — re-run this Entry phase gate step from its top:
        re-read `status_path` via `_status.read_full` fresh, and
        re-evaluate the whole phase table again from scratch (do not
        assume `planned` is now the phase and jump straight to Prepare;
        a fresh read could in principle still show something else if the
        upstream state changed again in the interim).
      - **`BLOCKED: <reason>`** — halt immediately, surfacing `<reason>`
        to the operator using the same message shape as this table's
        existing `blocked` row (`surface blocked_reason from status.md
        and halt`). Do not re-arm the wait automatically.
      - **`TIMEOUT after <N>s waiting for phase: planned`** — halt with a
        message distinct from the `BLOCKED` case: state that the
        configured give-up period (`pipeline.entry_wait_timeout_minutes`)
        elapsed without mill-plan reaching `phase: planned`, and that the
        operator should check on the upstream mill-plan session (it may
        be abandoned, still legitimately working past the give-up window,
        or never started) and re-run `/mill-go` to re-arm the wait if it
        is in fact still in progress.
    - **If the wait itself is stopped/interrupted at the harness level**
      (a `TaskStop` or equivalent operator-level cancellation of the
      recorded `task_id`, rather than one of the three outcomes above):
      treat it like any other harness-level stop elsewhere in this file —
      no automatic retry. Halt with a short message telling the operator
      the wait was cancelled and that re-running `/mill-go` will
      re-evaluate the phase (proceeding immediately if it has since become
      ready, or re-arming the wait if not).
  - **If `matches_wait_trigger` is `True` but `entry_wait` is `False`:**
    fall back to the table's original action — tell the user to finish
    mill-plan and halt. State explicitly in this subsection's prose that
    disabling `pipeline.entry_wait` narrows only the *action* (wait vs.
    halt), never the phase *classification* itself: even with the switch
    off, a phase of `plan-review-r{N}` / `plan-fix-r{N}` still reaches this
    same halt message (rather than falling through to the table's generic
    "any other" row) — this is a deliberate, narrow improvement to the
    halt path's message accuracy, independent of whether waiting is
    enabled.
  - **If `matches_wait_trigger` is `False`:** this phase value does not
    match the widened set at all; fall through to the remaining phase-table
    rows unchanged (this case does not actually occur for any value in
    `{discussed, discussing, planning}` plus the two regexes, since those
    are exactly what the match set covers — stated for completeness only).

  Do not modify any other row of the phase table, the *Resume* section, or
  any Agent-mode dispatch content elsewhere in this file. This card's edit
  is additive: the existing `planned` / `implementing`-`reviewing`-`fixing`
  / `blocked` / `done` / any-other rows and their actions are byte-for-byte
  unchanged.

- **Commit:** `mill-go: blocking entry-gate wait for phase discussed/discussing/planning/plan-review-r{N}/plan-fix-r{N}`

## Batch Tests

`verify: null` — this batch is a pure prose edit to a SKILL.md file with
no runnable code surface; there is no unit or integration test harness
that exercises SKILL.md-driven orchestration logic (the live `Monitor`
tool call itself is a harness behavior that cannot be exercised from
`unit_tests/` or `integration_tests/`, matching how the rest of mill's
Agent-mode dispatch prose is tested today — only the underlying
`_phase_wait.py` data/string-building helper gets coverage, already
verified in batch 1). Manual verification path: the existing
plan-review/code-review loops that already gate every mill-go/mill-plan
change apply to this SKILL.md edit unchanged.
