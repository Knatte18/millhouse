# Batch: brief-instruction-hardening

```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
batch: brief-instruction-hardening
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch closes GitHub issues #978 and #944 by hardening two adjacent
instructions in `implementer-brief.md`'s `## Report` section. #978: the
implementer sometimes restates `commit_sha` in prose before the final JSON line,
and that prose restatement — not the JSON line — is where transcription errors
happen (the JSON line's SHA is independently recomputed and validated downstream
by `_forward_output`, so the prose restatement is never load-bearing). #944: the
implementer sometimes ends its turn on an explanatory wrap-up paragraph instead
of the required bare JSON line, despite the existing "Long-session reminder"
instruction already asking for JSON-first / JSON-again discipline. Both fixes are
prose-only edits to the same section, done as one card in one focused pass. No
new interface for a later batch to consume — this batch has no code dependents.

## Cards

### Card 1: Prohibit prose commit_sha restatement and reinforce JSON-line discipline

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Report` section, immediately after the existing paragraph that ends
  `never write an unqualified "all complete"/"all done" claim without having
  actually verified the count this way.` (the end of the "Card-count self-check"
  paragraph) and before the paragraph beginning `Your last line of output (after
  all work and commits) MUST be a single JSON object:`, insert a new paragraph:

  ```
  **Never restate `commit_sha` in prose.** Your free-text summary may say the
  work is committed, but never write the SHA value (full or abbreviated)
  anywhere in prose -- the JSON line is the only place it appears. Restating it
  manually invites a transcription error the JSON line never has.
  ```

  Separately, immediately after the existing "Long-session reminder" paragraph
  (the one ending `duplicate JSON is fine, `_implementer_common._forward_output`
  reads the last match.`) and before the `## On review resume` heading, insert a
  new paragraph:

  ```
  **Nothing follows the JSON line.** If you notice yourself starting a wrap-up
  paragraph after finishing implementation -- a "Note:", "Summary:", or any
  explanation of what you did or did not run -- stop and delete it before
  ending your turn. The JSON line above is the end of your turn; no prose,
  caveats, or notes may come after it, even ones that seem helpful to a human
  reader.
  ```

  Do not touch any other paragraph in `## Report`. Do not touch `## On review
  resume` or any other section of the file.
- **Commit:** `docs(implementer-brief): prohibit prose commit_sha restatement and reinforce JSON-line discipline`

## Batch Tests

`verify: null`. This batch edits only prose instructions inside a markdown
template with no executable surface — there is nothing to run. Correctness is
verified by the plan/code review loop, not a test suite (see the overview's
Shared Decisions).
