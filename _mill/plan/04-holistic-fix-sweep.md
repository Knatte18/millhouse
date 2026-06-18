# Batch: holistic-fix-sweep

```yaml
task: "Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes"
batch: "holistic-fix-sweep"
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes issue #501 (enhancement): in mill-go's holistic code-review fix loop, when a finding describes a repeating/systemic pattern across many files, the fixer only fixes the cited exemplars, so the same pattern re-surfaces in un-cited files next round (whack-a-mole that can exhaust `holistic.rounds`). The fix adds a sweep instruction to the holistic fixer brief template. Doc-only, no runnable test surface (templates are not unit-tested). Scope decision (per discussion Q4): fixer-brief only; no reviewer/schema "systemic" flag.

## Cards

### Card 4: Instruct the holistic fixer to sweep the tree for systemic patterns

- **Context:**
  - `plugins/mill/templates/review-code-holistic.md`
- **Edits:**
  - `plugins/mill/templates/fixer-holistic-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `fixer-holistic-brief.md`, in the procedure list (the numbered steps that currently tell the fixer to "Apply findings in the order the review lists them" and "edit the relevant file(s) and commit"), add an instruction: when a finding describes a repeating/systemic pattern — the same violation class appearing across multiple files (e.g. "strip X from all docs", "this call-form recurs throughout the tree") — the fixer must NOT fix only the cited exemplars. Instead it must grep/search the whole worktree for that pattern and fix every occurrence in one pass.
  - Reaffirm the existing scope guard already in this brief: any newly-touched file that is not already referenced by a batch plan's `Context:`/`Edits:`/`Creates:` must be added to the appropriate batch plan's allowlist before editing it (do not silently edit out-of-allowlist files). The sweep does not bypass that rule.
  - Instruct the fixer to note the sweep in its commit message (e.g. "swept all occurrences of <pattern>") so the next review round can see the scope of what was fixed.
  - Keep the brief's existing tone, the `mill-receiving-review` loading instruction, and all other steps unchanged. This is an additive instruction, not a rewrite.
- **Commit:** `feat(fixer): sweep whole tree for systemic patterns in holistic fix`

## Batch Tests

`verify: null` — this batch edits only a markdown brief template. There is no runnable surface (templates are rendered at dispatch time inside a live mill-go holistic loop, which is not reproducible in a unit test). Correctness is established by plan review of the instruction text. No `_mill/` or behavioural code changes.
