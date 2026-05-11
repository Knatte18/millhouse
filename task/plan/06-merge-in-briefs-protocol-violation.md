# Batch: merge-in-briefs-protocol-violation

```yaml
task: 44 (A) — Bug-fix batch 4
batch: merge-in-briefs-protocol-violation
number: 6
cards: 1
verify: null
depends-on: []
```

## Batch Scope

`millpy-merge-in-subagent.py --mode verify-fix` reports `{"status":"stuck","stuck_type":"logic","reason":"no structured report"}` even when the sub-agent's verify-replay passes and the fix is committed (#231). Root cause: `_implementer_common._forward_output` can't find the JSON sentinel because the brief templates do NOT instruct the sub-agent that anything other than a bare JSON last-line is a protocol violation — unlike `implementer-brief.md` which has this explicit instruction. Strengthen `merge-in-verify-brief.md` and `merge-in-conflict-brief.md` to mirror that contract. Template-only change; `verify: null`.

## Cards

### Card 12: Add protocol-violation sentence to both merge-in briefs

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/templates/merge-in-verify-brief.md`
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `merge-in-verify-brief.md`, locate the `## Report` section (around line 33). After the second JSON example block (the `{"status":"stuck",...}` line), insert the sentence: `Anything other than this JSON object on the last line is a protocol violation; the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost. Do not wrap the JSON in a code fence; do not add commentary after it.` Place it as a new paragraph (blank line above and below) immediately after the two JSON examples and before the `## Tools` heading.
  2. In `merge-in-conflict-brief.md`, find the analogous `## Report` (or equivalent end-of-brief) section. Add the same sentence with `merge-in dispatcher` in place — adjust wording slightly if the conflict brief's report shape differs but keep the "protocol violation" / "stuck_type: logic" / "no structured report" wording verbatim, since that is what callers grep for. If the conflict brief lacks an explicit JSON example, add a minimal one matching `_implementer_common._forward_output`'s expectation (a single `{...}` object on the last line with `"status"`).
  3. Match the wording style of `implementer-brief.md`'s line 87 (`Anything other than this JSON on the last line is a protocol violation; mill-go treats that as stuck_type: logic with reason "no structured report".`) — replace `mill-go` with `the merge-in dispatcher` since that is who reads the verify-fix sub-agent's output.
  4. Do NOT modify `_implementer_common._forward_output`. The parser regex is correct; the briefs are the contract.
  5. Do NOT modify `implementer-brief.md` (the canonical version) or `implementer-fix.md`.
- **Commit:** `docs(merge-in-briefs): name JSON last-line protocol violation (#231)`

## Batch Tests

`verify: null`. Template-text-only changes; no automated assertion. Sanity check via `git diff plugins/mill/templates/merge-in-*.md` — two files changed, each with the protocol-violation sentence inserted in the `## Report` section.
