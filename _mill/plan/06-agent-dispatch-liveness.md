# Batch: agent-dispatch-liveness

```yaml
task: "mill-go-base: orchestration robustness gaps"
batch: agent-dispatch-liveness
number: 6
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; t = pathlib.Path('plugins/mill/skills/mill-go-base/SKILL.md').read_text(encoding='utf-8'); n = t.count('must never be read, logged, or otherwise acted on'); assert n >= 3, f'expected >=3 write-only warnings, found {n}'; assert 'already confirmed the agent is no longer running' in t, 'missing issue-1001 fallback-trigger rewording marker'; print('ok')"
depends-on: []
```

## Prior failure

- Round 1: verify failed with `/bin/sh: 1: Syntax error: Unterminated quoted string`. Root cause: the batch's `verify:` frontmatter value contained `#1001` preceded by a space (` #1001`), which YAML's comment syntax (`#` preceded by whitespace, even inside an unquoted plain scalar) truncated mid-value when the plan file's frontmatter was parsed — silently dropping the trailing `print('ok')"` and leaving an unterminated double-quote for the shell to choke on. Self-resolved by rewording the assertion's failure message from `'missing #1001 fallback-trigger rewording marker'` to `'missing issue-1001 fallback-trigger rewording marker'` (no `#` character), in both this file's frontmatter and the mirrored entry in `00-overview.md`. No code change was needed — the implementer's own commit (cards 9 and 10) was already correct; only the plan's `verify:` string was defective.

## Batch Scope

Fixes #995 (the `TaskOutput` liveness probe's return value must never be read/logged — a mid-flight reviewer probe once dumped a full JSONL transcript into the orchestrator's context) and #1001 (closes the residual ambiguity in the `incomplete`-recovery `--resume-incomplete` cold-fallback path, which the existing per-notification liveness probe already covers behaviorally but does not state explicitly — see `_mill/discussion.md`'s `995-taskoutput-write-only-warning` and `1001-liveness-before-cold-redispatch` Decisions). Both fixes land entirely within `SKILL.md`'s "## Agent-mode dispatch" section (steps 3(b), 3(c), and 5.5), so no other file is touched and no dependency on batches 1/2 is needed. Two cards, both editing `SKILL.md`; estimated context: 2 x 106,797/4 ≈ 53,400 tokens. This batch is the root of the `SKILL.md` file-overlap serialization chain (batches 4, 5, 3 each depend on it, directly or transitively) — the validator's `parallel-modifies-overlap` check requires every pair of DAG-parallel-eligible batches touching the same file to have an edge; this batch has no real feature dependency of its own, so it anchors the chain at position zero.

## Cards

### Card 9: TaskOutput write-only warnings at all three call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `SKILL.md` currently has exactly three `TaskOutput(task_id: <agentId>, block: false)` call sites in "## Agent-mode dispatch," none carrying any warning about its return value: step 3(b) ("before invoking `--stage finalize`, call `TaskOutput(task_id: <agentId>, block: false)` using the `agentId` retained per step 2."), step 3(c) ("Before classifying as `stuck_type: transient`, call `TaskOutput(task_id: <agentId>, block: false)` using the `agentId` retained per step 2..."), and step 5.5's `incomplete`-recovery Liveness probe ("call `TaskOutput(task_id: <agentId>, block: false)` using the same `agentId` retained from the original dispatch..."). At each of these three sentences, append (in the same sentence or the immediately following one — whichever reads more naturally in context) the exact literal warning text: "This call is for its status field only — the subagent's raw JSONL transcript in its return value must never be read, logged, or otherwise acted on." Use this exact sentence verbatim at all three sites (word-for-word identical), so the three warnings are trivially greppable as one consistent policy statement rather than three independently-phrased ones. Do not add a file-existence short-circuit (the `test -f <output_path>` pattern) to the step 3(b) implementer or step 3(c) fixer sub-cases — the existing `cheap-liveness-check-reviewer-only (#784)` Decision (already documented in this same file, immediately after the reviewer sub-case's `test -f` guard) explains why no equivalent check exists for implementer/fixer: neither has an autonomously-written deliverable file available before its terminal notification arrives. Leave that existing reviewer-only guard completely unchanged.
- **Commit:** `mill-go-base: add write-only warning at every TaskOutput liveness-probe call site (#995)`

### Card 10: close the incomplete-recovery cold-fallback liveness gap

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Step 5.5's "`incomplete` recovery (implementer only — agent mode)" subsection already has a "**Liveness probe:**" paragraph (under "1. Warm `SendMessage` resume (preferred)") that gates whether a non-clean-terminal warm-resume notification is treated as terminal, and a "2. `--resume-incomplete` fallback (cold re-dispatch)" subsection listing three trigger conditions: "no `agentId` was retained"; "the `SendMessage` call errors because the agent already terminated (the stop arrived as `status: completed`, so the harness worker is gone)"; and "the warm-resumed agent again stops without emitting JSON."

  Two edits, both within this same step 5.5 subsection:

  1. **Reword the fallback's trigger list.** For the third trigger ("the warm-resumed agent again stops without emitting JSON"), add a parenthetical or trailing clause stating explicitly, using this exact phrase verbatim: "already confirmed the agent is no longer running" — e.g. reword the trigger to read along the lines of "the warm-resumed agent again stops without emitting JSON, which per the Liveness probe paragraph above is only reachable once that probe has already confirmed the agent is no longer running." This removes the ambiguity a reader could otherwise have: that trigger is never a bare textual condition independent of the probe — it can only fire after the probe (in the paragraph immediately above) has already checked and confirmed non-liveness for that notification. The other two triggers are untouched — neither depends on the probe (no `agentId` to check; a `SendMessage` error against an already-`completed` stop already proves termination on its own).
  2. **Add a defensive re-check at the fallback's own dispatch point.** Immediately before the fallback's own dispatch action (the "Re-dispatch the implementer once via the `--resume-incomplete` path" step), add a narrow, belt-and-suspenders re-check that applies ONLY when the fallback was reached via the third trigger (the other two triggers have nothing further to re-check: no `agentId` exists for the first, and a proven-`completed` `SendMessage` error already settles the second): if the `agentId` is still in scope, call `TaskOutput(task_id: <agentId>, block: false)` one more time immediately before dispatching `--stage prepare ... --resume-incomplete`. Per Card 9's write-only-probe rule, this call's return value is for its status field only. If it reports the agent is still running: do NOT proceed with the cold `--resume-incomplete` dispatch this turn — instead, take no action and wait for the agent's own next `<task-notification>` for the same `agentId` (identical no-action-this-turn contract the Liveness probe paragraph already documents for its own "still running" branch). If it reports the agent is no longer running, or the probe call itself errors: proceed with the `--resume-incomplete` dispatch exactly as documented. State explicitly that this re-check exists to close the narrow TOCTOU window between the notification-time probe (in the Liveness probe paragraph above) and this fallback actually firing, not because the notification-time probe is itself insufficient.
- **Commit:** `mill-go-base: reword and defensively re-check incomplete-recovery cold-fallback liveness (#1001)`

## Batch Tests

`verify:` (see frontmatter above) is a `python -c` assertion confirming the exact write-only warning sentence appears at least 3 times (one per call site card 9 edits) and that the `#1001` fallback-trigger rewording marker phrase is present — per this plan's "prose-only batches verify via exact-marker grep/python assertions" Shared Decision in `00-overview.md`.
