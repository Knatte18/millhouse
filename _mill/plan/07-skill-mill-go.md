# Batch: skill-mill-go

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
batch: "skill-mill-go"
number: 7
cards: 1
verify: null
depends-on: [1]
```

## Batch Scope

Isolates `mill-go/SKILL.md` into its own batch because it is by far the largest SKILL in the repo and its changes are narrow: two prior-round NIT heading scans that must tolerate a class suffix, and the surrounding envelope documentation that must mention the new `findings` key.
mill-go already speaks `BLOCKING` / `NIT` and `APPROVE` / `REQUEST_CHANGES`, so there is no vocabulary rename here at all -- keeping it out of batch 6 avoids loading 32k tokens of unrelated orchestration prose into that batch's context for two regex sentences.
It depends on batch 1 only, for the envelope key it documents.

Batch-local decision: the two prior-round scans keep reading the review **file** rather than switching to an envelope read.
They compare against round `N-1`, whose envelope the orchestrator no longer holds by the time round `N` runs, so the file is the only surviving source.
The `structured-findings-in-envelope` Decision's "those all become envelope reads" applies where the envelope for the round being read is in hand; here it is not, and the demotion rewrite guarantees the file's headings already agree with what that round's envelope said.

## Cards

### Card 29: mill-go tolerates classed NIT headings and documents findings

- **Context:**
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the per-batch review loop's prior-round scan (the step that runs when `N > 1` and scans the round `N-1` review file for every line matching `### [NIT] <title>`) and in the holistic review loop's equivalent scan (the step that runs when `H > 1` against `*-code-review-r{H-1}.md`), state that the heading may carry a class suffix so `### [NIT:consistency] <title>` matches as well as `### [NIT] <title>`, and that the title is the heading text after the closing bracket in either form.
  Add one sentence to each of those two steps stating that a heading carrying a `**Demoted-from:** BLOCKING` line on the line below it was demoted by the stage ceiling and is a genuine NIT for the purposes of the prior-non-blocking-items list, not a suppressed BLOCKING.
  In the two APPROVE branches that gate the NIT-fix pass on `nit_count > 0`, add one sentence stating that `nit_count` is derived from the envelope's post-ceiling `findings` list and that the per-finding `title`, `severity`, and `class` are available there if the fixer brief needs them; leave the `nit_count > 0` condition and the no-exception dispatch rule exactly as they are.
  In the nit-gate paragraph that describes requiring a `nits-fixed-<scope>` timeline row for each scope with any `[NIT]` findings in its final code-review file, state that classed `[NIT:<class>]` headings count identically.
  Do not change any control flow, any batch-state transition, any `_status` call, any commit command, any stuck-type classification, or the Agent-mode dispatch section.
- **Commit:** `docs(mill-go): tolerate classed NIT headings and document the findings envelope`

## Batch Tests

`verify: null`.
This batch edits one SKILL markdown file -- orchestrator instructions with no runnable surface and no test harness in this repo.
The behaviour it describes is the same widened `parse_blocking_count` regex that batch 4's `test-nit-gate.py` cards assert from the code side, including the demoted-heading case, so the machine-checkable half of card 29 is already gated there.
