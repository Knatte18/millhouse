# Batch: finalize-timeout-guidance-generalization

```yaml
task: Batch verify/baseline/completeness gates produce false positives or time out
batch: finalize-timeout-guidance-generalization
number: 5
cards: 1
verify: null
depends-on: [4]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Fixes #639 and #624: mill-go SKILL.md's extended-timeout note (recommending 600000ms/10min for Bash-tool calls whose finalize stage replays a batch's `verify:` command as a regression guard) is scoped only to `millpy-fix.py --stage finalize`, but `millpy-implement.py --stage finalize` runs the identical regression-guard verify replay and hits the same default 2-minute Bash-tool timeout. This is a pure documentation change — no code, one card. It depends on batch 04 (`depends-on: [4]`) because it also extends the same timeout note to the new "0.55. Done-gate baseline pre-flight" block batch 04 adds, which must exist in SKILL.md before this batch can annotate it.

## Cards

### Card 18: Generalize the extended-timeout note across all three call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite the existing timeout sentence in the Agent-mode dispatch step 6 paragraph (currently scoped to `millpy-fix.py --stage finalize` specifically) to state the rule generically: any `--stage finalize` call for a CLI whose finalize stage replays a batch's `verify:` command as a regression guard gets the extended 600000ms (10-minute) Bash-tool timeout. Explicitly name the current instances — `millpy-fix.py --stage finalize` and `millpy-implement.py --stage finalize` — so the rule reads as concrete, not just abstract. Keep the existing carve-out sentence ("review-CLI finalize calls don't run verify commands and aren't affected") verbatim, adjusted only as needed for grammatical fit with the generalized lead sentence. Additionally, add the same 600000ms timeout recommendation as a note alongside BOTH: (a) the pre-existing Handoff-time "0. Pre-done gate" inline-Python block (which runs `pipeline.done_gate` via a Bash-tool `$MILL_PYTHON -c` call and currently has no timeout note at all), and (b) the new "0.55. Done-gate baseline pre-flight" block batch 04's Card 16 added (same risk: an arbitrary, potentially slow project command run via the same Bash-tool call shape). State the rationale inline: both `done_gate` call sites can run an arbitrary project test command (e.g. a full regression suite) with no bound on runtime, sharing the identical default-2-minute-Bash-timeout risk that motivated the original finalize-stage-CLI fix.
- **Commit:** `docs(mill-go): generalize extended-timeout guidance to all finalize-stage and done_gate call sites`

## Batch Tests

`verify: null` — this is a pure SKILL.md prose change with no runnable surface. Manual proofread for internal consistency (the "review-CLI... aren't affected" carve-out must still read correctly against the generalized rule, and the two done_gate call sites' new timeout notes must correctly reference the block each is attached to) is the only verification.
