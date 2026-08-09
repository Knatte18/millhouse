# Batch: mill-go-dispatch-classification-observability

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
batch: mill-go-dispatch-classification-observability
number: 1
cards: 6
verify: null
depends-on: []
```

## Batch Scope

This batch closes three related gaps in `mill-go/SKILL.md`'s "## Agent-mode dispatch" step 4 (the notification-classification/recovery logic), plus the one companion doc fix that makes step 4's new `<status>`-tag-based test verifiable against the harness contract it relies on:

- **#785** widens step 4(b)'s implementer sub-case and step 4(c)'s reviewer/fixer case from a narrow "stopped/interrupted" wording to a broader "non-clean terminal notification" test keyed on the `<task-notification>`'s `<status>` tag (`!= "completed"`), so a stall/watchdog kill (which surfaces as `<status>failed</status>`, not literally "stopped/interrupted") lands in the same defined recovery path instead of falling through undefined.
- **#784** adds a cheap `test -f <output_path>` liveness check ahead of the existing `TaskOutput` probe, for the reviewer sub-case of step 4(c) only (fixer and implementer keep `TaskOutput` unchanged — neither has an equivalent pre-terminal deliverable file).
- **#781** adds a one-line observability call (`_status.append_inferred_success_log`) at the two sites where finalize's no-JSON commit-count recount produces `"inferred": true` on an otherwise-successful envelope, so a silent trailing-JSON protocol violation becomes visible in `status.md` instead of indistinguishable from a compliant run.
- The companion **harness-tool-contracts.md** fix corrects the Agent-tool section's current claim that message-text is the only signal on that path — it is not; a `<status>` tag is also present, and #785's new test depends on that fact being documented accurately.

Card 3 (the new `_status.append_inferred_success_log` Python helper this batch's cards 5-6 call) lives in a separate batch (`status-inferred-success-helper`, batch 3) — this batch only adds the `SKILL.md` prose describing when and how mill-go calls it; the two batches touch disjoint files and carry no DAG dependency between them.

No batch-local decisions differ from `## Shared Decisions` in the overview — this batch is squarely governed by `doc-batches-preserve-file-conventions`: every card below is a surgical edit inside `mill-go/SKILL.md`'s existing bold-lead-in numbered-list style (`## Entry`/`## Agent-mode dispatch` convention), not a rewrite, and must not disturb any heading numbering outside the specific sentence/bullet named in its `Requirements:`.

## Cards

### Card 1: Widen step 4(b)'s implementer "Stopped/interrupted notification" trigger to a `<status>`-based non-clean-terminal test

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In step 4(b) ("**(b) Notification for an implementer dispatch — split by trigger.**"), the second bullet of the two-bullet list currently opens with the bold lead-in `**Stopped/interrupted notification**` followed by the parenthetical `(the harness signal indicating the background agent was killed or interrupted, rather than stopping on its own)`.
  Replace the bold lead-in with `**Non-clean terminal notification**` and replace the parenthetical with a definition of the concrete test: the `<task-notification>`'s `<status>` tag is present and its value is not `completed` (observed values include `completed`, `failed`; a stall/watchdog kill surfaces as `<status>failed</status>` with the stall reason in `<summary>`), AND the message does not contain (a)'s literal API-error marker text.
  Leave every other word of that bullet unchanged — the `— **NEW liveness probe**, mirroring (c) exactly:` clause, the `TaskOutput(task_id: <agentId>, block: false)` call, the still-running / no-longer-running branching, and the closing sentence referencing `#587`/`#595`/`#610` all stay exactly as written; only the trigger's bold lead-in and its defining parenthetical change.
  In the immediately preceding first bullet (`**Clean turn-exhaustion**`), it currently reads "AND carries no stop/interrupt signal" as part of defining what this bullet's trigger excludes.
  Reword that clause to "AND carries no non-clean-terminal `<status>` signal" so the two bullets' trigger conditions remain a clean, non-overlapping partition of the notification space under the new `<status>`-based vocabulary — do not change anything else in that first bullet.
- **Commit:** `docs(mill-go): widen step 4(b) implementer trigger to status-based non-clean-terminal test`

### Card 2: Widen step 4(c)'s heading and trigger to the same `<status>`-based non-clean-terminal test, mirrored for reviewer/fixer

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Step 4(c)'s heading currently reads `**(c) Stopped/interrupted notification for a reviewer or fixer dispatch — NEW liveness probe.**`.
  Replace it with `**(c) Non-clean terminal notification for a reviewer or fixer dispatch — NEW liveness probe.**`.
  Immediately below that heading, the opening sentence currently reads "Before classifying as `stuck_type: transient`, call `TaskOutput(task_id: <agentId>, block: false)` using the `agentId` retained per step 3 (...)." — insert, before that sentence, a new sentence defining the widened trigger using the identical concrete test worded in Card 1: the `<task-notification>`'s `<status>` tag is present and its value is not `completed` (observed values include `completed`, `failed`; a stall/watchdog kill surfaces as `<status>failed</status>` with the stall reason in `<summary>`), AND the message does not contain (a)'s literal API-error marker text.
  Leave the rest of (c) — the still-running/no-longer-running branching, the `#595` cross-reference, and the closing paragraph citing `#587`/`#595` and the `stopped/interrupted-notification liveness probe (#587, #595)` Decision — unchanged; those already describe mechanism, not the trigger condition being widened here.
  Do not touch the "**Agent-mode properties**" bullet list later in the file (which also uses "stopped/interrupted" language) — that section is out of scope for this task, which is scoped to only step 4's classification branches.
- **Commit:** `docs(mill-go): widen step 4(c) heading and trigger to status-based non-clean-terminal test`

### Card 3: Document the Agent-tool `<status>` tag in harness-tool-contracts.md

- **Context:** none
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Agent tool` section, the third bullet currently reads: "Delivers exactly ONE combined-result `<task-notification>` when the subagent finishes, is stopped, or is interrupted — the notification payload carries the subagent's final message text."
  This sentence currently implies message-text is the only signal on this path.
  Append a new sentence to that same bullet (do not start a new bullet): "Agent-tool `<task-notification>`s also carry a `<status>` tag, with `completed` for clean success and other values (`failed`, `stopped`, `interrupted`) for everything else, alongside the existing message-text-based signals."
  Leave every other bullet in the `## Agent tool` section (the `agentId` bullet, the stopped/interrupted-can-be-stale bullet, the `agentId`-vs-`session_id` distinction bullet) and the entire `## Monitor tool` section below it unchanged.
- **Commit:** `docs(harness-contracts): document Agent-tool <status> tag alongside message text`

### Card 4: Add a cheap `test -f` liveness check ahead of `TaskOutput` for the reviewer sub-case of step 4(c)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  This card depends on Card 2 having already widened step 4(c)'s heading and opening trigger sentence — apply this edit to the resulting (post-Card-2) text, immediately after the trigger-defining sentence Card 2 inserted and before the existing "Branch on the result:" sentence.
  Insert new prose, scoped to the **reviewer sub-case only** (not fixer): before calling `TaskOutput`, first check whether `output_path` (the absolute path read verbatim from step 2's prepare envelope, per step 6's existing convention "For the three review CLIs, `<path>` is the `output_path` field read verbatim from step 2's prepare envelope") already exists on disk via a `test -f <output_path>` shell check.
  If the file exists: treat the reviewer as no-longer-running and proceed straight to the existing "no longer running" branch below (skip the `TaskOutput` call entirely for this occurrence).
  If the file does not exist: the result is ambiguous (still-running or dead-before-writing) — fall back to `TaskOutput` exactly as today, unchanged.
  State explicitly that this `test -f` pre-check applies to the reviewer sub-case of (c) only; the fixer sub-case of (c), and the implementer's mirrored probe in (b) (widened by Card 1), continue using `TaskOutput` unchanged — fixer and implementer have no autonomously-written deliverable file available before their terminal notification arrives (per the `cheap-liveness-check-reviewer-only (#784)` Decision), so no equivalent check exists for them.
- **Commit:** `docs(mill-go): add cheap test -f liveness pre-check for reviewer sub-case of step 4(c)`

### Card 5: Log inferred-success observability at step 4(b)'s Clean mid-work stop `status: success` sub-case

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the "**Clean mid-work stop (implementer only):**" paragraph (immediately following step 4(b)'s bullet list), the first sub-bullet reads: "**`status: success`** (all cards committed and the tree is clean) — proceed normally to step 7."
  Immediately before "proceed normally to step 7" in that same sub-bullet, insert: when the finalize envelope's `inferred` field is `true`, call `_status.append_inferred_success_log(status_path, batch_name, round, timestamp)` (`signature: _status.append_inferred_success_log(status_path: Path, batch_name: str, round: int, timestamp: str) -> None`) and commit the resulting `status.md` change on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: log inferred-success for {batch_name}"`) before proceeding.
  State explicitly that when `inferred` is absent or `false` (the implementer reported the JSON line normally), this new call is skipped entirely and the existing success path is otherwise unchanged.
  Do not touch the `stuck_type: incomplete`, `stuck_type: transient`, or `stuck_type: logic` sub-bullets in the same paragraph — this card is scoped to the `status: success` sub-bullet only.
  This is a standalone commit — do not piggyback it onto any other commit made elsewhere in step 4, and do not touch the `phase:` field.
- **Commit:** `docs(mill-go): log inferred-success observability at step 4(b) clean-success sub-case`

### Card 6: Log inferred-success observability at step 6.5's "After recovery" bullet 3

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In step 6.5 ("`incomplete` recovery (implementer only — agent mode)"), sub-step 3 ("**After recovery.**") currently reads: "Re-parse the finalize envelope and branch in step 7. A `status: success` (or inferred success) means the batch finished — proceed normally. If the envelope is **still** `stuck_type: incomplete` after one warm resume and one `--resume-incomplete` fallback, hand it to the `### Stuck escalation` `incomplete` branch (it does not silently loop)."
  Immediately after "A `status: success` (or inferred success) means the batch finished" and before "— proceed normally", insert: when the re-parsed envelope's `inferred` field is `true`, call `_status.append_inferred_success_log(status_path, batch_name, round, timestamp)` and commit the resulting `status.md` change on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: log inferred-success for {batch_name} (post-recovery)"`), before proceeding normally.
  State explicitly that this is a structurally separate check from Card 5's call site — finalize's envelope after an `incomplete` recovery is examined here independently, so an implementer that goes `incomplete` on its first turn and then completes cleanly without emitting JSON on the resumed turn is caught only by this call site, not Card 5's.
  When `inferred` is absent or `false`, skip this call entirely.
  Do not touch the `stuck_type: incomplete` escalation sentence at the end of the same sub-step — this card is scoped to the `status: success` (or inferred success) sentence only.
- **Commit:** `docs(mill-go): log inferred-success observability at step 6.5 after-recovery check`

## Batch Tests

`verify: null` — every card in this batch is a `SKILL.md`/doc prose edit describing orchestrator behavior and a doc-accuracy correction; there is no executable surface to run.
Verification is a careful re-read of each edited bullet/heading against the four dispatch-notification shapes catalogued in `_mill/discussion.md` (API-error marker, clean turn-exhaustion, non-clean terminal `<status>` signal, and the reviewer-only `test -f` pre-check), confirming each notification shape still has exactly one defined home after the edits, and confirming Cards 5-6's two call sites both name `_status.append_inferred_success_log` with the exact signature `status_path: Path, batch_name: str, round: int, timestamp: str) -> None` that batch 3 (`status-inferred-success-helper`) implements.
