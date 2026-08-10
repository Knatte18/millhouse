# Batch: mill-go-blocked-halt-fixes

```yaml
task: 'mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references'
batch: mill-go-blocked-halt-fixes
number: 1
cards: 3
verify: PYTHONPATH= sh -c '[ "$(grep -c "update_field(status_path, .blocked_reason." plugins/mill/skills/mill-go/SKILL.md)" = "0" ] && [ "$(grep -c 600000ms plugins/mill/skills/mill-go/SKILL.md)" = "4" ]'
depends-on: []
```

## Batch Scope

This batch delivers all three `plugins/mill/skills/mill-go/SKILL.md` prose fixes named in `_mill/discussion.md`: #810 (add the missing state-mutation sequence before the holistic step 3.5/3.6 halts), #809 (swap the precondition-buggy `_status.update_field` call for `_status.set_blocked` in step 7), and #792 (add the missing extended-timeout note to "0.5. Baseline pre-flight"). All three edits land in the same file at three disjoint, non-overlapping line ranges (~1095-1149, ~1200-1201, ~467-484), so they are grouped into one batch rather than three, both because a single-file edit set is a natural "smart unit" the implementer holds in its head in one pass, and because splitting them into three parallel batches touching the same file would trip the `parallel-modifies-overlap` validator check (no batch-DAG dependency would legitimately separate them — they are unrelated fixes, not sequenced work). There is no external interface this batch's output feeds to a later batch; batch 2 (mill-plan cross-refs) is fully independent.

## Cards

### Card 1: #810 -- add state-mutation sequence to holistic step 3.5/3.6 halts

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_notify.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Add an explicit state-mutation sentence before each of the three `halt with BLOCKED:` sentences in holistic steps 3.5 and 3.6, mirroring the pattern already used by `### Blocked` (lines 853-862) and the sibling holistic escalation branches at lines 1187, 1190, 1195 (which do `_status.append_phase` + commit + cleanup-block + "go to *Blocked*" -- this batch instead inlines `_status.set_blocked` + commit + cleanup-block + `_notify.notify` + builder-lock release, per `_mill/discussion.md`'s `810-mutation-sequence` Decision, since the holistic scope has no `batch_name` to key a `### Blocked`-style redirect on and these two halts need to keep their own custom `reviews[].error` detail).

  1. In step 3.5 (currently around line 1127), insert one new line immediately before the existing sentence `If sub-step 3.6 does NOT apply, halt with \`BLOCKED: holistic code review ERROR-only round {H}\` and surface each entry's \`error\` string from \`reviews[]\` to the user.` -- leave that sentence byte-for-byte unchanged on its own line after the insertion. Use the same 3-space indent as its neighboring lines (`   The round counter...` / `   On the **second**...`). New line's exact text:

    `Before halting: \`_status.set_blocked(status_path, f"holistic code review ERROR-only round {H}", timestamp=_timestamp.now_utc_iso())\`; commit \`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (ERROR-only round {H})"\` and push; invoke the holistic cleanup block; \`_notify.notify("mill-go.blocked", f"holistic review: ERROR-only round {H}", slug=slug)\`; release the builder lock (\`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release\`).`

  2. In step 3.6 item 4 (currently around line 1146), the numbered list item currently reads exactly: `4. If the fallback reviewer ALSO returns \`verdict: ERROR\` on its first pass: halt with \`BLOCKED: holistic code review fallback also failed at round {H}\` and surface every \`reviews[*].error\` from BOTH the original and fallback attempts.` Insert the mutation-sequence clause between the condition (`...on its first pass:`) and the halt clause, so the item reads exactly:

    `4. If the fallback reviewer ALSO returns \`verdict: ERROR\` on its first pass: before halting, \`_status.set_blocked(status_path, f"holistic code review fallback also failed at round {H}", timestamp=_timestamp.now_utc_iso())\`; commit \`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (fallback also failed at round {H})"\` and push; invoke the holistic cleanup block; \`_notify.notify("mill-go.blocked", f"holistic review: fallback also failed at round {H}", slug=slug)\`; release the builder lock (\`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release\`); then halt with \`BLOCKED: holistic code review fallback also failed at round {H}\` and surface every \`reviews[*].error\` from BOTH the original and fallback attempts.`

    The following continuation line, `Do NOT cascade to a second fallback.`, is unchanged.

  3. In step 3.6 item 5 (currently around line 1148), the numbered list item currently reads exactly: `5. If \`fallback_reviewer is None\` AND a rate-limit was detected on both 3.5 passes: halt with \`BLOCKED: holistic rate-limited, no fallback_reviewer configured\`.` Restructure it the same way, so the item reads exactly:

    `5. If \`fallback_reviewer is None\` AND a rate-limit was detected on both 3.5 passes: before halting, \`_status.set_blocked(status_path, "holistic rate-limited, no fallback_reviewer configured", timestamp=_timestamp.now_utc_iso())\`; commit \`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (rate-limited, no fallback)"\` and push; invoke the holistic cleanup block; \`_notify.notify("mill-go.blocked", "holistic review: rate-limited, no fallback_reviewer configured", slug=slug)\`; release the builder lock (\`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release\`); then halt with \`BLOCKED: holistic rate-limited, no fallback_reviewer configured\`.`

    The following continuation line, `The operator-visible message is intentional -- silent infinite fallback is wrong.`, is unchanged.

  Do not modify any other line inside steps 3.5 or 3.6 (in particular, leave the known pre-existing item-5-reachability inconsistency noted in `_mill/discussion.md`'s `810-mutation-sequence` Decision untouched -- it is explicitly out of scope for this task).

  Cross-check `plugins/mill/scripts/_status.py`'s `set_blocked(status_path, reason, *, timestamp)` signature (line 241) before writing the three calls above, to confirm the keyword-only `timestamp=` argument shape matches what is written here.

- **Commit:** `docs(mill-go): add state-mutation sequence to holistic ERROR/rate-limit halts (#810)`

### Card 2: #809 -- swap update_field for set_blocked in step 7

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In holistic step 7 "Rounds exhausted" (currently around lines 1200-1201), replace the two-call sequence:

  `\`_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())\`;` followed on the next line by `\`_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s)")\`;`

  with a single call, on one line, in the same position (immediately after the step 7 heading's parenthetical condition and colon):

  `\`_status.set_blocked(status_path, f"holistic review exhausted {max_holistic_rounds} round(s)", timestamp=_timestamp.now_utc_iso())\`;`

  The rest of step 7 -- the `commit \`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review"\` and push;` line, the `invoke the holistic cleanup block;` line, and the `halt with "Holistic review exhausted {max_holistic_rounds} round(s). Task left as [active] for manual review."` line -- is unchanged. Do not touch any other step.

  `_status.update_field` (`plugins/mill/scripts/_status.py:203`) is strict-key and raises `ValueError` when `blocked_reason` does not already exist in the yaml block, which is exactly the case on a task's first-ever block; `_status.set_blocked` (`_status.py:241`) already performs the `phase: blocked` overwrite, the `blocked_reason:` upsert, and the timeline-row append in one atomic call, so no separate `append_phase` call remains after this swap.

- **Commit:** `fix(mill-go): swap update_field for set_blocked in step 7 rounds-exhausted halt (#809)`

### Card 3: #792 -- add extended-timeout note to 0.5 baseline pre-flight

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In "### 0.5. Baseline pre-flight (first batch of the task only)", immediately after the sentence `Skip this step entirely for every batch after the first.` (its current last sentence, currently ending line 483) and before the blank line that precedes the "### 0.6. Per-batch baseline recapture (self-hosting only)" heading, insert one new paragraph (blank line before it, blank line after it, matching this file's existing paragraph-spacing convention -- do not run it into the same line as the sentence before or after it). Exact text of the new paragraph:

  `Give this Bash-tool call the same extended 600000ms (10-minute) timeout recommended for finalize-stage verify replays above: \`--stage baseline\`'s \`per_batch\` substage replays every batch's \`verify:\` command to seed \`verify_baseline_failures\`, which is an arbitrary, potentially slow project command with no bound on runtime, sharing the identical default-2-minute-Bash-timeout risk that motivated the original finalize-stage-CLI fix.`

  This reuses the established lead sentence verbatim (matching the existing sibling notes at line 456, in "### 0.55. Done-gate baseline pre-flight", and at line 1314, in Handoff's "0. Pre-done gate"), adapting only the rationale clause to what 0.5 actually replays (`--stage baseline`'s `per_batch` substage, per its own documented behavior at what are currently lines 478-480) rather than the `done_gate`/`gate_cmd`-specific rationale the two siblings use, since 0.5 does not invoke `done_gate`.

  Do not alter the "### 0.6." heading, the "Skip this step entirely for every batch after the first." sentence, or any other line inside "### 0.5. Baseline pre-flight".

- **Commit:** `docs(mill-go): add extended-timeout note to 0.5 baseline pre-flight (#792)`

## Batch Tests

Pure documentation edits to one `SKILL.md` file -- no application/script code changes, so no unit tests apply. `verify:` above is a mechanical grep-based gate covering cards 2 and 3 exactly as specified by `_mill/discussion.md`'s Testing section (zero remaining `update_field(status_path, "blocked_reason"` occurrences; exactly 4 total `600000ms` occurrences after adding card 3's one new match to the 3 pre-existing sibling matches). Card 1 (#810) has no reliable automated check -- per the discussion's own Testing section, confirming the mutation sequence landed correctly ahead of all three halts is a structural/ordering check best done by eye during plan/code review, not a grep presence check.
