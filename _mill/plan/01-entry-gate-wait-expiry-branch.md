# Batch: entry-gate-wait-expiry-branch

```yaml
task: 'Monitor tool: persistent:true doesn''''t exist, entry-gate waits break'
batch: entry-gate-wait-expiry-branch
number: 1
cards: 3
verify: null
depends-on: []
```

## Batch Scope

This batch keeps the two entry-gate wait sections' existing `Monitor(command=cmd, persistent: true,
...)` call intact (per `_mill/discussion.md`'s "Keep `persistent: true`..." Decision) and adds one
defensive outcome — an unexpected/early expiry, with a wall-clock-budget-aware re-arm — to each,
plus a refreshed, re-verified `Monitor` schema description in the shared contracts doc both sections
cite. No external interface changes: nothing outside these three markdown files depends on their
content, so there is no "next batch" to hand an interface to — this is the whole plan. Batch-local
decision beyond the overview's `## Shared Decisions`: each card owns exactly one file and must not
edit the other two — this is the boundary that lets a Sonnet builder hold each card's diff in full
without needing the other two files' final text in context, and is enforced by each card's own
same-line "Do not touch" prohibition (see Cards below).

## Cards

### Card 1: Add unexpected-expiry re-arm branch to mill-plan's entry-gate wait

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `### Entry-gate wait for upstream mill-start` section:
  1. Immediately before the existing bullet "Call the `Monitor` tool with `command=cmd`,
     `persistent: true`, `description` naming the slug and the target phase (e.g. "waiting for
     phase: discussed (mill-start handoff) for `<slug>`")." — insert a new sibling bullet at the
     same nesting level:
     `- Record wait_started_epoch (the output of` `date +%s` `in the Bash tool) now, before arming the wait for the first time. Retain it in a local orchestrator variable for the duration of this wait — it is never reset by the unexpected-expiry re-arm below, only read by it to compute the remaining budget.`
  2. In the "Branch on the `<event>` content:" list, immediately after the existing sub-bullet
     "**`TIMEOUT after <N>s waiting for phase: discussed`**" (and its two sentences) and before the
     separately-indented bullet "**If the wait itself is stopped/interrupted at the harness level**"
     — insert a new sibling sub-bullet at the same nesting level as the `READY` and `TIMEOUT after`
     sub-bullets:
     `- **Any other notification content** (an <event> that is neither` `READY` `nor a` `TIMEOUT after ...` `line — e.g. an unrequested "Monitor expired after Nm with no events delivered..." notice) — an unexpected early expiry. Run` `date +%s` `again and compute` `remaining_s = giveup_s - (<this reading> - wait_started_epoch)` `. If` `remaining_s <= 0` `: treat exactly like the` `TIMEOUT after <N>s` `branch above — halt with the same give-up message. Otherwise: rebuild` `cmd = _phase_wait.build_wait_command(status_path, "discussed", 10, remaining_s, clean_tree_root=git_root, clean_tree_paths=[status_path, discussion_path])` `and re-issue the identical` `Monitor(command=cmd, persistent: true, description=...)` `call documented above, recording the newly returned` `task_id` `in place of the old one, then resume waiting for the next <task-notification>. This is a re-arm of the same wait — it does not re-run Entry step 4's phase-table evaluation; only` `READY` `does that.`
  3. Do not change the `READY` bullet, the "If the wait itself is stopped/interrupted at the harness
     level" bullet, the "If `matched` is `True` but `entry_wait` is `False`" bullet, or the "If
     `matched` is `False`" bullet.
  4. Do not touch `plugins/mill/skills/mill-go-base/SKILL.md` or
     `plugins/mill/docs/harness-tool-contracts.md` in this card — card 2 and card 3 own those files
     respectively.
- **Commit:** `docs(mill-plan): re-arm entry-gate wait on unexpected Monitor expiry`

### Card 2: Add the identical re-arm branch to mill-go-base's mirrored entry-gate wait

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `### Entry-gate wait for upstream mill-plan` section:
  1. Immediately before the existing bullet "Call the `Monitor` tool with `command=cmd`,
     `persistent: true`, `description` naming the slug and the target phase (e.g. "waiting for
     phase: planned (mill-plan handoff) for `<slug>`")." — insert a new sibling bullet at the same
     nesting level:
     `- Record wait_started_epoch (the output of` `date +%s` `in the Bash tool) now, before arming the wait for the first time. Retain it in a local Builder variable for the duration of this wait — it is never reset by the unexpected-expiry re-arm below, only read by it to compute the remaining budget.`
  2. In the "Branch on the `<event>` content:" list, immediately after the existing sub-bullet
     "**`TIMEOUT after <N>s waiting for phase: planned`**" (and its two sentences) and before the
     separately-indented bullet "**If the wait itself is stopped/interrupted at the harness level**"
     — insert a new sibling sub-bullet at the same nesting level as the `READY` and `TIMEOUT after`
     sub-bullets:
     `- **Any other notification content** (an <event> that is neither` `READY` `nor a` `TIMEOUT after ...` `line — e.g. an unrequested "Monitor expired after Nm with no events delivered..." notice) — an unexpected early expiry. Run` `date +%s` `again and compute` `remaining_s = giveup_s - (<this reading> - wait_started_epoch)` `. If` `remaining_s <= 0` `: treat exactly like the` `TIMEOUT after <N>s` `branch above — halt with the same give-up message. Otherwise: rebuild` `cmd = _phase_wait.build_wait_command(status_path, "planned", 10, remaining_s)` `and re-issue the identical` `Monitor(command=cmd, persistent: true, description=...)` `call documented above, recording the newly returned` `task_id` `in place of the old one, then resume waiting for the next <task-notification>. This is a re-arm of the same wait — it does not re-run this Entry phase gate step; only` `READY` `does that.`
  3. Do not change the "**Speculative baseline launch.**" paragraph and its nested bullets, the
     `READY` bullet, the "If the wait itself is stopped/interrupted at the harness level" bullet, the
     "If `matched` is `True` but `entry_wait` is `False`" bullet, or the "If `matched` is `False`"
     bullet.
  4. Do not touch `plugins/mill/skills/mill-plan/SKILL.md` or
     `plugins/mill/docs/harness-tool-contracts.md` in this card — card 1 and card 3 own those files
     respectively.
- **Commit:** `docs(mill-go-base): re-arm entry-gate wait on unexpected Monitor expiry`

### Card 3: Refresh the Monitor tool contract in harness-tool-contracts.md

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Monitor tool` section:
  1. Before the existing sentence "A poll script run via `Monitor(command: ..., persistent: true,
     ...)`:", insert a new lead paragraph recording the schema as directly reconfirmed via a live
     tool-schema read on 2026-09-21 (the same verification `_mill/discussion.md`'s Problem section
     records): parameters `command`/`ws`, `description`, `timeout_ms` (number, default `300000`, max
     `3600000`, ignored when `persistent` is `true`), `persistent` (boolean, default `false` — "run
     for the lifetime of the session, no timeout; stop via `TaskStop`"). State that this contradicts
     the specific "no `persistent` parameter" claim common to ten independent field reports — GitHub
     issues #1058, #1062, #1066, #1067, #1078, #1085, #1088, #1096, #1100, #1108 — filed against
     whatever `Monitor` build they each hit, and that the two entry-gate wait sections cited at the
     bottom of this section document a defensive third outcome (an unexpected early expiry, with a
     re-arm) for a build where `persistent: true` does not hold the watch open for the full wait.
  2. Leave the existing sentence "A poll script run via `Monitor(command: ..., persistent: true,
     ...)`:" and its first four bullets ("Delivers ONE...", "Followed by a SEPARATE...", "This
     two-notification shape...", "Runs bash, not PowerShell...") unchanged.
  3. Add a fifth bullet to that same list, after the "Runs bash, not PowerShell..." bullet:
     `- An early, unrequested expiry (a notification whose <event> content is neither` `READY` `nor a` `TIMEOUT after ...` `line) is possible on a` `Monitor` `build where` `persistent: true` `does not hold the watch open for the full wait — both entry-gate wait sections below re-arm on this outcome, recomputing the remaining budget from wall-clock elapsed time rather than restarting it.`
  4. Leave the final line ("See `mill-go-base/SKILL.md`'s ... section for two independent consumers
     of this contract.") unchanged.
  5. Do not touch `plugins/mill/skills/mill-plan/SKILL.md` or
     `plugins/mill/skills/mill-go-base/SKILL.md` in this card — card 1 and card 2 own those files
     respectively.
- **Commit:** `docs(harness-tool-contracts): reconfirm Monitor persistent schema, document expiry re-arm`

## Batch Tests

`verify: null` — this batch changes only markdown prose in two `SKILL.md` files and one
`docs/*.md` file; there is no Python source change and no altered runtime behavior for any script to
exercise. `plugins/mill/unit_tests/test-phase-wait.py` — the one existing test file that mentions
"Entry-gate wait" — was confirmed during discussion to test `_phase_wait.py`'s `build_wait_command`/
`matches_wait_trigger` functions directly, never SKILL.md prose; this batch does not touch
`_phase_wait.py`, so that test file needs no update and gives no coverage to point a `verify:`
command at either way. Verification for this batch is a careful read-through instead:

- Confirm each card's new bullet lands at the correct nesting level (a sibling of `READY`/
  `TIMEOUT after ...` under "Branch on the `<event>` content:", not nested under either of them, and
  not a sibling of the separately-indented harness-stop bullet).
- Confirm the three outcomes (`READY`, `TIMEOUT after ...`, unexpected-expiry-and-re-arm) are mutually
  exclusive as written — the new bullet's own parenthetical ("an `<event>` that is neither `READY` nor
  a `TIMEOUT after ...` line") is what keeps it from swallowing the other two.
- Diff card 1's and card 2's final wording side by side: they should differ only in the target phase
  name (`discussed` vs. `planned`), the upstream skill name (mill-start vs. mill-plan), the variable
  name for the retained handle ("local orchestrator variable" vs. "local Builder variable", matching
  each file's own existing terminology), and the rebuilt `cmd` line (mill-plan's carries
  `clean_tree_root`/`clean_tree_paths`, matching its own existing `build_wait_command` call; mill-go-base's does not, matching its own).
- Confirm `harness-tool-contracts.md`'s new numbers (`timeout_ms` default `300000` / max `3600000`)
  match `_mill/discussion.md`'s Problem section exactly, and that the ten issue numbers listed match
  `_mill/discussion.md`'s Problem section's list verbatim.
