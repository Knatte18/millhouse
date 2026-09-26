# Batch: script-wording

```yaml
task: 'mill-go-base: take the subagent report from the SubagentHandback message'
batch: 'script-wording'
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py
depends-on: [1]
```

## Batch Scope

Rewords error-message text and comments in the finalize scripts; no logic change (overview decision code-changes-are-wording-only).

## Cards

### Card 9: implementer finalize message and comment

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `finalize_from_output`, the not-found error message string has a fragment ` notification message to this path before calling --stage finalize`.
  Change "notification message" to "subagent report message" (keep the rest of the message and keep it ASCII).
  In the comment directly above the `html.unescape` call, reword "The harness HTML-escapes the <task-notification> payload uniformly before delivery" to say a <task-notification> payload is HTML-escaped by the harness, so the captured text may contain entities; unescaping here is a no-op for a hand-back message that carries none.
  Do not change any code line.
- **Commit:** `refactor(implementer-common): word finalize error and unescape comment for hand-back reports`

### Card 10: merge-in finalize message and comment

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the conflicts-mode finalize branch, change the same error-message fragment "notification message" to "subagent report message" and reword the comment above its `html.unescape` call ("Mirror finalize_from_output's own read: unescape the HTML entities the harness injects into the <task-notification> payload before parsing") to say the entities may appear when the text came from a notification payload.
  No code change.
- **Commit:** `refactor(merge-in-subagent): word finalize error and unescape comment for hand-back reports`

### Card 11: review CLIs comment

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Each file has one comment line reading "Agent-mode output is a file the reviewer wrote itself via Write, never HTML-escaped -- unlike the implementer's <task-notification> payload, so no unescape happens here."
  Reword it identically in all three files to "... unlike the implementer's report (a <task-notification> payload may be HTML-escaped; a hand-back message is treated the same way), so no unescape happens here."
  No code change.
- **Commit:** `refactor(review-cli): reword agent-output comment for the implementer report source`

## Batch Tests

`verify:` runs `test-review-finalize.py`, which imports the review CLIs and the implementer finalize path, catching a syntax slip in the edited comments or strings.
