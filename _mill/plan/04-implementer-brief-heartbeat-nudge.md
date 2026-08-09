# Batch: implementer-brief-heartbeat-nudge

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
batch: implementer-brief-heartbeat-nudge
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

`#787`: the Claude Code harness's 600s stream-watchdog constant is confirmed outside mill's config surface entirely (full-file grep of `mill-go/SKILL.md` and `mill-config.yaml`'s `llm.*_timeout` keys, which gate only `subprocess`/`psmux`-mode LLM-provider calls, not Agent-tool background dispatch).
The only lever mill has is what the dispatched agent itself outputs during a long silent phase.
This batch adds a short heartbeat-nudge instruction to `implementer-brief.md`'s `## Verify` section: when a batch's `verify:` command runs multiple sequential sub-invocations, emit a brief progress line before each one rather than staying silent until all verify output returns at once.
This is a standalone template edit with no dependency on any other batch in this plan.
No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 11: Add heartbeat-nudge instruction to the `## Verify` section

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Verify` section, the current text opens: "After every card in the batch is committed, run the batch's `verify:` command (from the batch file's frontmatter). If it fails:" followed by the self-fix bullet list.
  Immediately after that opening sentence ("...from the batch file's frontmatter.") and before "If it fails:", insert a new sentence: "If the `verify:` command is actually several sequential sub-invocations (for example, more than one `go test` call, or a `go test` run followed by a `go test -tags integration` run), print a brief progress line before each sub-invocation (for example, `Running: go test ./builderengine/...`) instead of staying silent until all of them finish — a long silent verify phase can be mistaken for a stalled session and killed by the harness's stream watchdog."
  Do not alter the self-fix bullet list, the `<SELF_FIX_ROUNDS>` sentence, or the `verify: null` skip-to-Report sentence that follow — this card is scoped to inserting the one new sentence described above.
  Do not touch any of the four trailing-JSON-report blocks elsewhere in the file (the success block, the resume-incomplete success block, the stuck block, or the closing anti-truncation restatement) — this is a `## Verify`-section-only change, unrelated to the JSON-report protocol.
- **Commit:** `docs(implementer-brief): add heartbeat-nudge instruction for multi-sub-invocation verify commands`

## Batch Tests

`verify: null` — this batch edits prompt text read by the implementer LLM, not executable code; there is no runnable surface.
Verification is re-reading the edited `## Verify` section and confirming the new sentence sits between the opening frontmatter-sourcing sentence and "If it fails:", without disturbing the self-fix bullets, the `<SELF_FIX_ROUNDS>` sentence, or the `verify: null` skip sentence.
