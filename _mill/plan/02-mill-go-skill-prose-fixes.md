# Batch: mill-go-skill-prose-fixes

```yaml
task: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion
batch: mill-go-skill-prose-fixes
number: 2
cards: 5
verify: null
depends-on: [1]
```

## Batch Scope

Five prose edits to `plugins/mill/skills/mill-go/SKILL.md`, all in the shared orchestration path every mill-go task run goes through. Depends on batch 1 because card 5 documents the `nits_only` envelope field batch 1 introduces. `verify: null` is intentional per the overview's Shared Decision "SKILL.md prose changes carry no automated test coverage" — there is no Python entry point that executes this file; correctness here is established by the exact replacement text specified in each card below plus the discussion/plan/code review rounds. Each card below gives the **exact** current text and the **exact** replacement text — this is a precision-editing batch, not a "use your judgment" one, because round 1 of discussion review already flagged the self-contradiction risk in leaving related passages half-updated (see `_mill/discussion.md`'s `implementer-liveness-probe` Decision).

## Cards

### Card 5: Thread `--nits-only` re-pass into Agent-mode dispatch step 6 (#619)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Agent-mode dispatch` section, step 6 ("**Run finalize stage:**"), locate the paragraph beginning "Additionally thread any applicable prepare-envelope fields into the finalize call". Its exact current text is:

  > Additionally thread any applicable prepare-envelope fields into the finalize call: for fix and implementer CLIs, pass `--session-id <session_id>` and `--start-sha <start_sha>` (when `start_sha` is not null in the envelope); for review CLIs, pass `--round <round>`.

  Replace it verbatim with:

  > Additionally thread any applicable prepare-envelope fields into the finalize call: for fix and implementer CLIs, pass `--session-id <session_id>` and `--start-sha <start_sha>` (when `start_sha` is not null in the envelope); for `millpy-fix.py` finalize calls specifically, additionally pass `--nits-only` when the prepare envelope's `nits_only` field is `true` (the field is present only when the prepare-stage call itself included `--nits-only`; a finalize call must NOT pass `--nits-only` when the envelope omits the field or has it `false`, since only a genuine NIT-only fix pass should skip the no-content-commit gate and receive the `nits-fixed-<scope>` marker); for review CLIs, pass `--round <round>`.

  Do not modify the following paragraph (the one starting "For `millpy-fix.py` specifically, 'the same standard arguments' means re-passing `--scope`...") — that paragraph documents a different, already-correct set of flags and is unaffected by this change.
- **Commit:** `docs(mill-go): re-pass --nits-only at finalize when prepare envelope has it (#619)`

### Card 6: Document the `nits-fixed-<scope>` marker for manual recovery (#612)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Handoff` section, locate the existing "**Nit-enforcement gate.**" block. Its exact current text (including the sentence that ends the paragraph and the following blank line + next paragraph) is:

  > If `unfixed_nits` is non-empty, halt with:
  > `BLOCKED: unfixed nits in scope(s): <scope-list> -- run the NIT-fix pass before completing`
  > where `<scope-list>` is the joined list of scope names. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can run the NIT-fix pass and re-run `/mill-go`.
  >
  > If the list is empty, proceed to terminal cleanliness gate.

  Insert a new paragraph between the two existing paragraphs above (after "...re-run `/mill-go`." and before "If the list is empty, proceed to terminal cleanliness gate."):

  > **Manual recovery note.** The gate above requires a `nits-fixed-<scope>` row in status.md's timeline for each scope that has any `[NIT]` findings in its final code-review file — it does not inspect commits directly. Under Agent-mode dispatch this marker is written automatically by the NIT-fix pass's `--stage finalize` call (see "## Agent-mode dispatch" step 6). If an operator instead completes or verifies a NIT-fix pass manually, outside this documented flow (e.g. recovering from an orphaned or crashed fixer session), the gate still requires the marker to be appended by hand: `_status.append_phase(status_path, f"nits-fixed-{scope}", _timestamp.now_utc_iso())`, where `scope` is the batch name or `"holistic"`.

  The final result must read, in order: the existing "Nit-enforcement gate" paragraph, then this new "Manual recovery note" paragraph, then the existing "If the list is empty, proceed to terminal cleanliness gate." sentence.
- **Commit:** `docs(mill-go): document nits-fixed-<scope> marker for manual recovery (#612)`

### Card 7: Split the per-batch NIT-fix-pass dispatch sentence (#609)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the per-batch code-review APPROVE branch (the `- \`APPROVE\` — If \`nit_count > 0\` in the envelope, dispatch one cold-start NIT-only fix pass:` bullet), locate the bolded sentence immediately below it. Its exact current text is:

  > **NEVER skip the NIT-fix pass, even under time or performance pressure. 'Non-blocking' does NOT mean optional -- deferred nits re-surface as BLOCKING in later rounds and cost more total rounds. Only nits a reviewer explicitly marks 'no action required' may be left.**

  Replace it verbatim with:

  > **Dispatch the NIT-fix pass whenever `nit_count > 0` — there is no exception to this for the Builder, even under time or performance pressure. 'Non-blocking' does NOT mean optional: deferred nits re-surface as BLOCKING in later rounds and cost more total rounds.** The fixer, not the Builder, decides what to leave: within the pass, the fixer may leave a nit unfixed only when the reviewer explicitly marked it 'no action required' — that latitude governs the fixer's in-pass judgment, not the Builder's dispatch decision, and never excuses skipping the dispatch itself.

  Preserve the surrounding blank lines and indentation exactly as they appear in the original (this sentence sits inside an indented bullet under `- \`APPROVE\``).
- **Commit:** `docs(mill-go): clarify per-batch NIT-fix-pass dispatch is mandatory, not fixer-conditional (#609)`

### Card 8: Split the holistic NIT-fix-pass dispatch sentence (#609)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the holistic code-review APPROVE branch (`4. On \`APPROVE\`: If \`nit_count > 0\` in the envelope, dispatch one cold-start NIT-only fix pass:`), locate the bolded sentence immediately below it — this is the same sentence as card 7 but at a different site (one level less indentation, since it's not nested under a `-` bullet). Its exact current text is:

  > **NEVER skip the NIT-fix pass, even under time or performance pressure. 'Non-blocking' does NOT mean optional -- deferred nits re-surface as BLOCKING in later rounds and cost more total rounds. Only nits a reviewer explicitly marks 'no action required' may be left.**

  Replace it verbatim with the identical replacement text used in card 7:

  > **Dispatch the NIT-fix pass whenever `nit_count > 0` — there is no exception to this for the Builder, even under time or performance pressure. 'Non-blocking' does NOT mean optional: deferred nits re-surface as BLOCKING in later rounds and cost more total rounds.** The fixer, not the Builder, decides what to leave: within the pass, the fixer may leave a nit unfixed only when the reviewer explicitly marked it 'no action required' — that latitude governs the fixer's in-pass judgment, not the Builder's dispatch decision, and never excuses skipping the dispatch itself.

  This site's original text is IDENTICAL in wording to card 7's site (only indentation differs) — do not confuse the two; both occurrences in the file must be replaced (the per-batch one by card 7, the holistic one by this card). Preserve this site's original indentation exactly (no leading `-` bullet nesting here, unlike card 7's site).
- **Commit:** `docs(mill-go): clarify holistic NIT-fix-pass dispatch is mandatory, not fixer-conditional (#609)`

### Card 9: Extend the liveness probe to implementer stopped/interrupted notifications (#610)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits in the `## Agent-mode dispatch` section, step 4.

  **Edit A — replace step 4(b) and its "Clean mid-work stop" paragraph.** The exact current text (from "**(b) Stopped/interrupted notification for an implementer dispatch..." through the paragraph ending "...finalize now reclassifies a partial-batch verify failure or no-JSON inference as `incomplete` rather than `transient`.") is:

  > **(b) Stopped/interrupted notification for an implementer dispatch — unchanged, routes to Clean mid-work stop below, never through the liveness probe in (c).** This carve-out exists because `--stage finalize`'s own completeness recount already disambiguates partial-vs-dead for the implementer (it inspects the actual commit count against the batch's card count), making a liveness probe redundant there.
  >
  > **Clean mid-work stop (implementer only):** When the implementer notification is a non-error non-JSON message — meaning the payload contains neither an `API Error` / `Internal server error` marker nor a valid `status` JSON block (clean turn exhaustion: the implementer ran out of budget and stopped before emitting the required JSON report), OR the background agent was stopped/interrupted before completing — do NOT re-dispatch fresh immediately. Instead, write the notification to the `.out.md` file as normal and invoke the `--stage finalize` step (step 6). Finalize inspects the commit count against the batch's card count and returns one of:
  > - **`status: success`** (all cards committed and the tree is clean) — proceed normally to step 7.
  > - **`stuck_type: incomplete`** (some-but-not-all cards committed — the partial clean stop) — route to the **`incomplete` recovery defined in step 6 below** (warm-`SendMessage` first, then the `--resume-incomplete` fallback). Do **NOT** route this to the Stuck escalation transient `commits_made > 0` skip-to-cleanliness path: that path accepts the partial batch as done and is exactly the #574 false-success bug. The whole point of the `incomplete` classification (see Shared Decision `stuck_type: incomplete is a new first-class classification`) is that the remaining cards must be finished, never accepted as complete.
  > - **`stuck_type: transient`** (genuine raw-API-error or interruption surfaced through finalize, e.g. a brief-write failure) — handle exactly as today via the one-retry transient path; this branch is **unchanged**.
  >
  > A clean turn-exhaustion stop after Batch 1 lands on the `incomplete` branch, not the transient branch — finalize now reclassifies a partial-batch verify failure or no-JSON inference as `incomplete` rather than `transient`.

  Replace this ENTIRE span verbatim with:

  > **(b) Notification for an implementer dispatch — split by trigger.** Two distinct triggers both land on an implementer dispatch that didn't cleanly report success, and they are no longer handled identically:
  > - **Clean turn-exhaustion** (the notification is a non-error, non-JSON message — the payload contains neither an `API Error` / `Internal server error` marker nor a valid `status` JSON block — AND carries no stop/interrupt signal: the implementer voluntarily ran out of turn budget before emitting the required JSON report) — **unchanged**, routes straight to Clean mid-work stop below, never through the liveness probe in (c). The redundancy rationale still holds here: `--stage finalize`'s own completeness recount disambiguates partial-vs-dead by inspecting the actual commit count against the batch's card count, which is conclusive when the implementer had a full turn to make commits before stopping.
  > - **Stopped/interrupted notification** (the harness signal indicating the background agent was killed or interrupted, rather than stopping on its own) — **NEW liveness probe**, mirroring (c) exactly: before invoking `--stage finalize`, call `TaskOutput(task_id: <agentId>, block: false)` using the `agentId` retained per step 3. If it reports the agent is still running: take no action this turn — no finalize call, no escalation — and wait for the agent's own next `<task-notification>` for the same `agentId`, exactly as (c) already does for reviewer/fixer. If it reports the agent is no longer running, or the probe call itself errors: proceed to Clean mid-work stop below exactly as documented. This closes a gap the recount alone cannot: a stopped/interrupted notification that arrives with zero commits made gives finalize no commit evidence to recount against, so it cannot tell "genuinely dead" from "still working, will finish and report later" — the same staleness problem `#587`/`#595` already solved for reviewer/fixer, now closed for implementer too (#610).
  >
  > **Clean mid-work stop (implementer only):** Reached either directly (clean turn-exhaustion, per (b) above) or after (b)'s stopped/interrupted probe branch determines the agent is no longer running. Do NOT re-dispatch fresh immediately. Instead, write the notification to the `.out.md` file as normal and invoke the `--stage finalize` step (step 6). Finalize inspects the commit count against the batch's card count and returns one of:
  > - **`status: success`** (all cards committed and the tree is clean) — proceed normally to step 7.
  > - **`stuck_type: incomplete`** (some-but-not-all cards committed — the partial clean stop) — route to the **`incomplete` recovery defined in step 6 below** (warm-`SendMessage` first, then the `--resume-incomplete` fallback). Do **NOT** route this to the Stuck escalation transient `commits_made > 0` skip-to-cleanliness path: that path accepts the partial batch as done and is exactly the #574 false-success bug. The whole point of the `incomplete` classification (see Shared Decision `stuck_type: incomplete is a new first-class classification`) is that the remaining cards must be finished, never accepted as complete.
  > - **`stuck_type: transient`** (genuine raw-API-error or interruption surfaced through finalize, e.g. a brief-write failure) — handle exactly as today via the one-retry transient path; this branch is **unchanged**.
  > - **`stuck_type: logic`, reason "no structured report"** (no commits were made and no JSON was found) — reached only via the clean-turn-exhaustion sub-case of (b) above, since the stopped/interrupted sub-case already confirmed via the probe that the agent is no longer running before ever reaching this point — ask user per *Stuck escalation*, exactly as any other `stuck_type: logic` result.
  >
  > A clean turn-exhaustion stop after Batch 1 lands on the `incomplete` branch, not the transient branch — finalize now reclassifies a partial-batch verify failure or no-JSON inference as `incomplete` rather than `transient`.

  Do not modify **(a)** (the "Raw API/infrastructure errors — unchanged" paragraph, immediately above (b)) or **(c)** (the "Stopped/interrupted notification for a reviewer or fixer dispatch — NEW liveness probe" paragraph, immediately below the span replaced above) — both remain exactly as they are today.

  **Edit B — update the two "Agent-mode properties" bullets that describe implementer stopped/interrupted handling**, in the bullet list immediately following step 7 (headed "**Agent-mode properties:**"). The exact current text of the two affected bullets is:

  > - A background agent IS a detached worker and CAN be stopped or interrupted. A stopped/interrupted agent produces a notification indicating it did not complete normally — handle that per step 4's recovery paths below (implementer: existing clean-mid-work-stop / `incomplete` routing; reviewer/fixer: liveness-probe-then-one-retry-transient path).

  and, two bullets later:

  > - The one-retry transient policy applies to raw API errors immediately, and to stopped/interrupted reviewer/fixer agents once step 4's liveness probe confirms the agent is no longer running (see step 4). Stopped/interrupted implementer agents are routed to the existing clean-mid-work-stop / `incomplete` recovery instead (see step 4).

  Replace the first verbatim with:

  > - A background agent IS a detached worker and CAN be stopped or interrupted. A stopped/interrupted agent produces a notification indicating it did not complete normally — handle that per step 4's recovery paths below (implementer: liveness-probe-then-clean-mid-work-stop/`incomplete` routing per step 4(b); reviewer/fixer: liveness-probe-then-one-retry-transient path per step 4(c)).

  Replace the second verbatim with:

  > - The one-retry transient policy applies to raw API errors immediately, and to stopped/interrupted reviewer/fixer agents once step 4's liveness probe confirms the agent is no longer running (see step 4). Stopped/interrupted implementer agents are first checked by the same liveness probe (step 4(b)); once it confirms the agent is no longer running, they are routed to the existing clean-mid-work-stop / `incomplete` recovery (see step 4).

  The two bullets bracket a third, unrelated bullet ("`transient` stuck errors can still be emitted by `finalize` as synthetic JSON...") — leave that middle bullet untouched.

  After both edits, re-read the full `## Agent-mode dispatch` section once to confirm no other passage still describes the implementer's stopped/interrupted path as going "never through the liveness probe" — this exact self-contradiction was flagged in `_mill/discussion.md`'s review history and must not survive this card.
- **Commit:** `fix(mill-go): extend liveness probe to implementer stopped/interrupted notifications (#610)`

## Batch Tests

`verify: null` — no automated test coverage applies to SKILL.md prose edits (see the overview's Shared Decision "SKILL.md prose changes carry no automated test coverage"). Correctness is verified by the exact before/after text specified in each card above, and by the plan-review and code-review rounds that follow.
