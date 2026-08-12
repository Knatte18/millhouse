# Batch: strip-subprocess-dispatch

```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'strip-subprocess-dispatch'
number: 2
cards: 10
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [1]
```

## Batch Scope

Deletes the entire subprocess/psmux dispatch surface from `plugins/mill/skills/mill-go-base/SKILL.md` while all of its sections are still in that one file.
Every card edits only that file.
The batch ends with the three literals `psmux`, `millpy-bg`, and `` `dispatch == subprocess` `` gone from it, every `` If `dispatch == agent`: `` conditional turned into unconditional prose, and the two psmux session-cleanup blocks plus all of their call sites removed.
The interface batch 3 consumes is the de-duplication-ready state of the twelve tree-guard checkpoint paragraphs: each has lost its "this does not apply to the subprocess/psmux branch" half, so what remains is mechanically identical text.

Batch-local decisions beyond the overview's Shared Decisions: none.
Cards 2–11 are ordered top-down through the file so that no card's anchor text is disturbed by an earlier card in the same batch.

## Cards

### Card 2: Delete Agent-mode step 1 and make the section unconditional

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Agent-mode dispatch`, delete numbered step 1 in full — the `**Resolve dispatch mode:** dispatch = _agent_dispatch.resolve_dispatch_mode(cfg)` line, the sentence beginning "This reads `cfg["llm"]["claude"]["dispatch"]`", and the sentence beginning "If the mode is not `agent`, skip this entire section".
  Rewrite the section's lead-in sentence "When `dispatch == agent`, follow this three-step pattern at each dispatch point:" so it no longer names a dispatch mode — the pattern is now the only dispatch pattern and applies at every dispatch point unconditionally.
  Leave the surviving steps numbered 2 through 7 and leave every `4(a)`/`4(b)`/`4(c)`, `6.5`, `6.5.1`, `6.5.2` sub-label unchanged; batch 5 owns the renumbering.
  Do not touch the `> See plugins/mill/docs/harness-tool-contracts.md …` blockquote directly beneath the heading.
- **Commit:** `docs(mill-go-base): drop the resolve-dispatch-mode step from Agent-mode dispatch`

### Card 3: Replace the Agent-mode subprocess error-recovery fallback with escalation

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Agent-mode dispatch` step 4 case **(a)**, replace the clause "read-only reviewer dispatches (which write no review file) fall back to the subprocess `--stage full` path via `millpy-bg` before escalating" so that reviewer dispatches escalate per the `### Stuck escalation` section on the second consecutive raw API error, identically to the implementer and fixer treatment already stated in the same sentence.
  The resulting sentence must name a single behaviour for all three roles and must not name any fallback mechanism.
  Leave the immediately following sentence ("There is no live agent to probe in this case…") and the `**Deliberately no ack predicate.**` paragraph untouched.
- **Commit:** `docs(mill-go-base): escalate instead of falling back to subprocess on repeat API errors`

### Card 4: Reword the residual dispatch-mode references inside the Agent-mode section

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Three edits inside `## Agent-mode dispatch`, all rewordings rather than deletions:
  1. In step 3, the sentence ending "`effort` remains present in the envelope for `subprocess`/`psmux` dispatch parity and audit visibility, in addition to now driving `subagent_type`." — drop the dispatch-parity clause and keep the audit-visibility rationale and the "in addition to now driving `subagent_type`" clause intact.
  2. Step 7's opening, "**Branch on verdict:** Use the JSON envelope to branch identically to the existing `subprocess`/`psmux` flow — the `status`, `verdict`, `stuck_type` handling is identical." — rewrite so the verdict-branching contract stands on its own terms (the envelope's `status`, `verdict`, and `stuck_type` fields are what the caller branches on) with no reference to another flow.
     Keep the following sentence about step 6.5's `incomplete` recovery being the one addition.
  3. In the `**Agent-mode properties:**` bullet list, rewrite the bullet beginning "The one-retry transient policy applies to raw API errors immediately, and to stopped/interrupted reviewer/fixer agents…" and any neighbouring bullet text that contrasts agent mode against another dispatch mode, so no bullet implies a second mode exists.
     Do not delete any bullet outright — each states a live property of the surviving flow.
- **Commit:** `docs(mill-go-base): drop dispatch-mode contrasts from Agent-mode prose`

### Card 5: Delete the poll-loop max-wait and per-batch psmux cleanup blocks

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Delete two adjacent blocks that sit between the `**Agent-mode properties:**` bullet list and the `**Why not fork?**` paragraph, and every reference to the second one:
  1. The `**Subprocess/psmux poll-loop max-wait.**` paragraph in full, from that bold lead-in through the sentence ending "all follow the same time-bounded poll-until-EXIT pattern."
  2. The `**Per-batch session cleanup.**` paragraph, the `The per-batch cleanup block:` lead-in, and the fenced bash block ending in `_llm_claude.cleanup_session(sid)`.
  Then remove every instruction elsewhere in the file to invoke that block.
  Locate them by searching for the phrase `per-batch cleanup block`; each occurrence is either a standalone list item ("Invoke the per-batch cleanup block.") — delete the whole item — or a clause inside a longer sentence ("…commit …, invoke the per-batch cleanup block, and go to *Blocked*.") — delete just the clause and repair the surrounding punctuation so the sentence still reads.
  Leave the `**Why not fork?**` paragraph entirely untouched: it is unrelated to this deletion and is retained.
- **Commit:** `docs(mill-go-base): delete the psmux poll-loop and per-batch cleanup blocks`

### Card 6: Strip the subprocess branch from the Implement step

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### 1. Implement`:
  1. Delete the `Background via millpy-bg:` line and the `> **Before invoking millpy-bg**: verify pwd …` blockquote that both sit *above* the venv-check fenced block.
     Unlike every other occurrence of that blockquote, these two are outside any dispatch branch and would otherwise survive the strip.
     Keep the `Venv-check before per-batch invocation:` lead-in and its fenced bash block — the venv is needed by the surviving flow, and `test-guards.py`'s `no_windows_only_venv_check` reads it.
  2. Turn `` If `dispatch == agent`: follow the Agent-mode dispatch pattern … `` into an unconditional instruction.
  3. Delete the whole `` If `dispatch == subprocess` or `psmux`: background via millpy-bg: `` branch: its fenced `millpy-bg.py` invocation, the "Returns immediately with `pid=<N> log=<abs-path>`" and `run_in_background` sentences, the fenced poll-loop bash block, and the paragraph beginning "Parse the JSON result as `(status, pid_or_code)`".
  4. The step currently carries two `### 0.6. Per-batch baseline recapture` hook paragraphs — one for agent mode ("immediately before step 6 of the pattern above (`--stage finalize`) runs") and one for the backgrounded dispatch ("Immediately before this backgrounded dispatch is launched…").
     Delete the second; keep the first, which is the surviving flow's hook point.
  5. Keep the three closing paragraphs beginning "The CLI atomically: resolves paths and config…", "The Builder reads the JSON summary…", and "Only treat exit 1 as an unrecoverable pre-launch error…", but reword the two sentences that say the Builder reads the JSON summary "from the log file" so they name the finalize envelope the surviving flow actually parses instead.
- **Commit:** `docs(mill-go-base): make the Implement step agent-only`

### Card 7: Strip the four subprocess branches from the Code Review loop

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### 3. Code Review loop`, delete four `` If `dispatch == subprocess` or `psmux` `` branches and make each paired agent branch unconditional.
  The four are: sub-step 2's `millpy-review-code.py` dispatch; sub-step 4's `APPROVE` NIT-fix dispatch of `millpy-fix.py --nits-only`; sub-step 4's `REQUEST_CHANGES` dispatch of `millpy-fix.py`; and sub-step 4.5's ERROR-only-aggregate retry dispatch of `millpy-review-code.py`.
  For each, delete the branch's `> **Before invoking millpy-bg**` blockquote, its fenced `millpy-bg.py` invocation, any "Returns immediately with `pid=<N>`" / `run_in_background` sentence, its fenced poll-loop bash block, and its "Parse the JSON result as `(status, pid_or_code)`" paragraph.
  Two of those paragraphs have non-dispatch trailing content that must be preserved verbatim as its own sentence after the deletion: the NIT-fix branch's "The fixer loads `mill-receiving-review` and applies the NITs from the APPROVE'd review file. Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior. Do NOT re-review — the NIT fix is trusted. The NIT-fix session commits its own source-file changes atomically; on stuck escalate via the existing Stuck escalation path." and sub-step 2's trailing "The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`."
  In sub-steps 2 and 4.5, also delete the sentences "This does not apply to the subprocess/psmux branch immediately following in this same step, which keeps its existing worktree_snapshot_guard coverage unchanged." and "Does not apply to the subprocess/psmux branch immediately below." attached to the pre-dispatch tree-guard checkpoints, leaving the checkpoints themselves and their post-dispatch counterparts in place for batch 3 to de-duplicate.
  Preserve the `REQUEST_CHANGES` branch's closing paragraph beginning "The CLI atomically: resolves the batch plan, sets batch state" through "On stuck escalate.".
- **Commit:** `docs(mill-go-base): make the Code Review loop agent-only`

### Card 8: Reword the residual dispatch-mode references in the batch loop and Stuck escalation

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Four rewordings outside any deleted branch:
  1. `### 0.6. Per-batch baseline recapture (self-hosting only)` opens "This is a shared check-and-invoke block, referenced (not duplicated) from two different insertion points in `### 1. Implement` below — see the Agent-mode and subprocess/psmux dispatch branches there."
     Card 6 removes the second insertion point, so rewrite this to name the single surviving hook point in `### 1. Implement`.
  2. `### 2. Parse implementer report` has a bullet `- status: stuck, stuck_type: incomplete (subprocess/psmux mode) …` whose closing parenthetical is "(Agent mode handles `incomplete` earlier, in the Agent-mode dispatch step 6.5 warm-resume path.)".
     Delete this bullet in full — its entire content is the subprocess-mode handling of `incomplete`, and the surviving flow's handling is the step 6.5 path the parenthetical already points at.
  3. In `### Stuck escalation`, the `**infrastructure**` bullet reads "(bg worker died, likely logout) — auto-retry ONCE with a fresh re-fire: … then re-invoke `millpy-bg` with a fresh CLI (no `--resume` flag — the killed session is dead)."
     Keep the bullet and its one-retry-then-block semantics; replace the parenthetical gloss and the re-invocation instruction with dispatch-neutral wording (the worker died; re-dispatch once with a fresh session).
     Apply the same treatment to its "The re-fire matches the existing `running`-state Resume (fresh start; killed session cannot be reattached)." sentence.
  4. In the same section's `**incomplete**` bullet, the phrase "auto-resume **once** via the same `start_sha`-preserving path (warm-`SendMessage` in agent mode, `millpy-implement.py <batch_name> --resume-incomplete` in subprocess/psmux mode)" must name only the surviving path: warm-`SendMessage` first, `--resume-incomplete` as the fallback, matching the step 6.5 recovery it refers to.
- **Commit:** `docs(mill-go-base): drop dead-mode wording from the batch loop and stuck escalation`

### Card 9: Strip the three subprocess branches from Resume

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Resume` step 2, each of the three state branches (`running`, `reviewing`, `fixing`) carries a `` If `dispatch == agent`: … `` paragraph followed by a `` If `dispatch == subprocess` or `psmux` (via millpy-bg): `` paragraph, its `> **Before invoking millpy-bg**` blockquote, and a fenced `millpy-bg.py` invocation.
  Delete all three subprocess paragraphs with their blockquotes and fenced blocks, and make the three agent paragraphs unconditional.
  Preserve the non-dispatch trailing prose in each branch verbatim: the `running` branch's paragraph beginning "The interrupted implementer session is dead and cannot be re-attached…" through "continue at Execute step 2b (cleanliness gate)."; the `reviewing` branch's "The CLI's crash-recovery scan handles a written-but-uncommitted review file." and its "After parsing the JSON verdict, continue at Execute step 3 sub-step 3…" sentence; and the `fixing` branch's "The `<review-file-abs-path>` is the most recent …" and "After parsing the report, continue at Execute step 3 sub-step 5…" sentences.
  Leave steps 1, 3, and 4 of `## Resume` untouched.
- **Commit:** `docs(mill-go-base): make Resume agent-only`

### Card 10: Delete the holistic cleanup block and the bg-log crash-recovery branch

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two deletions in `## Holistic code review`:
  1. Delete the `**Holistic session cleanup.**` paragraph, the `The holistic cleanup block:` lead-in, the fenced bash block ending in `_llm_claude.cleanup_session('${holistic_sid}')`, and the following sentence "If the captured `holistic_sid` is empty or the literal `unknown`, cleanup is a documented no-op — the implementer brief contract guarantees the id is emitted on the happy path."
     Then remove every instruction in the section to invoke it, found by searching for the phrase `holistic cleanup block`; delete standalone list items whole, and delete in-sentence clauses while repairing punctuation, exactly as card 5 does for the per-batch block.
  2. In step 1 `**Crash-recovery.**`, collapse the three-way branch to two.
     Delete branch **(c)** ("No review file, bg log exists for round H") in full, including its `_bg.is_bg_worker_alive` probe, its **Alive** and **Dead** sub-bullets, and their fenced blocks.
     Reword branch **(b)** so it no longer says "no bg log for round H" and no longer says the CLI is fired "via `millpy-bg`".
     In the "Inline Python helper" fenced block below, delete the `# (c) bg log liveness probe` stanza (the `scratch_dir` assignment, the `bg_logs` glob, and the `_bg.is_bg_worker_alive` call with its `json.dumps` emission) and the now-unused `_bg` import, and update the helper's lead-in and the "Branch dispatch is exactly as enumerated above" prose to describe two branches.
     Preserve the line `reviews_dir = hub / '_mill/reviews'` byte-for-byte — `test-skill-helper-drift.py` asserts on that exact literal.
     Also update the two sentences elsewhere in the section that reference the deleted branch by name: step 2's "Skip this step when step 1 returned branch (a) or any sub-branch of (c)." and step 4's parenthetical "(or the crash-recovery branch (a) scan path)" — the first must name only the surviving skip condition, the second is already correct and needs no change.
- **Commit:** `docs(mill-go-base): delete the holistic psmux cleanup block and bg-log recovery branch`

### Card 11: Strip the four subprocess branches from Holistic code review and clean the Handoff reference

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `## Holistic code review`, delete four `` If `dispatch == subprocess` or `psmux` `` branches and make each paired agent branch unconditional: step 3's `millpy-review-code.py` dispatch; sub-step 3.5's ERROR-only retry; step 4's `APPROVE` NIT-fix dispatch of `millpy-fix.py --nits-only`; and step 5's `REQUEST_CHANGES` dispatch of `millpy-fix.py`.
  For each, delete the `> **Before invoking millpy-bg**` blockquote, the fenced `millpy-bg.py` or bare `millpy-fix.py` invocation, any "Returns immediately with `pid=<N>`" sentence, the fenced poll-loop bash block, and the "Parse the JSON result as `(status, pid_or_code)`" paragraph.
  Step 3's subprocess branch also carries a duplicate `Venv-check before holistic review invocation:` lead-in and fenced block — delete both, since they exist only to guard the deleted invocation and the surviving flow already has the venv-check in `### 1. Implement`.
  Preserve as standalone prose: step 3's `**Exit handling.**` paragraph, but reworded — its first sentence keys on "`[mill-bg] EXIT` reports a non-zero exit AND no JSON summary line is present in the log" and must instead key on the finalize envelope being absent, keeping the same "BLOCKED: holistic review pre-launch failure" halt, the same drop-through to sub-step 3.5 when an envelope is present, and the same closing cross-reference to the per-batch "only treat exit 1 as unrecoverable when JSON line is absent" rule.
  Preserve step 4's trailing "The fixer loads `mill-receiving-review` and applies the NITs. Do NOT re-review — the NIT fix is trusted. On stuck escalate via the existing Stuck escalation path." and step 5's "Parse stdout JSON (same last-`{"status":...}`-line pattern as per-batch)." and "The CLI handles `holistic-fixing` phase + commit + push itself.", the latter two reworded to describe parsing the finalize envelope rather than stdout of a backgrounded worker.
  Delete the two "does not apply to the subprocess/psmux branch" sentences attached to the pre-dispatch tree-guard checkpoints in step 3 and sub-step 3.5, and the equivalent "Applies only when dispatch == agent; the subprocess/psmux path keeps its existing worktree_snapshot_guard coverage." in sub-step 3.6, leaving the checkpoints themselves for batch 3.
  Apply the same `millpy-bg`-neutral treatment to the `stuck_type: infrastructure` bullet in step 5 that card 8 applies to the one in `### Stuck escalation`.
  Finally, in `## Handoff`'s `**Nit-enforcement gate.**`, the sentence "Dispatch the NIT-fix pass for that review file using the identical CLI, args, and dispatch-mode handling already documented for the in-flow NIT-fix pass" must drop "and dispatch-mode handling" — there is only one dispatch shape left.
  After this card, `grep -n 'psmux\|millpy-bg\|dispatch == subprocess'` over the edited file must return nothing; run it and fix any straggler before committing.
- **Commit:** `docs(mill-go-base): make Holistic code review agent-only`

## Batch Tests

`verify:` runs `test-guards.py`, `test-mill-go-variants.py`, and `test-skill-helper-drift.py` via `run-all.py --only`.
These are the three existing tests that read `plugins/mill/skills/mill-go-base/SKILL.md`, and each guards something this batch can plausibly break:

- `test-guards.py` — its `no_wiki_cwd` check allowlists `mill-go-base/SKILL.md` by exact path, and its `no_windows_only_venv_check` requires any file testing `.venv/Scripts/python.exe` to also mention `.venv/bin/python`.
  Card 6 keeps the per-batch venv-check and card 11 deletes the holistic duplicate, so this check is directly exercised.
- `test-mill-go-variants.py` — locks the base-vs-variant split and the `<VARIANT_LABEL>` parameterization; every card in this batch rewrites prose that carries `[<VARIANT_LABEL>]` and `commit -m "<VARIANT_LABEL>: …"` literals.
- `test-skill-helper-drift.py` — resolves every `_<module>.<fn>(` reference in each SKILL.md against the shipped scripts, and locks the literal `reviews_dir = hub / '_mill/reviews'`.
  Card 10 edits the block containing that literal and removes a `_bg.is_bg_worker_alive` reference, so both halves of this test are exercised.

The batch's own new-guard assertions (`test-mill-go-base-agent-only.py`) are not in scope here: three of its four checks depend on companion files that batch 4 creates.
Card 11 instead closes the loop manually with an explicit grep for the three banned literals before its commit.
