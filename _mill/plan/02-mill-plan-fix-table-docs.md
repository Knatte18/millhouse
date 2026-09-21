# Batch: mill-plan-fix-table-docs

```yaml
task: '_plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps'
batch: mill-plan-fix-table-docs
number: 2
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch is a pure documentation edit to `plugins/mill/skills/mill-plan/SKILL.md`'s Step 1.5 fix
table — it does not touch `_plan_validate.py` or any code, and has no dependency on batch 1 (different
file, no shared edit surface). `verify: null` at both the batch and card level, since there is no
runnable surface to check; the card's own correctness is that the row text matches Decisions
`verify-tags-package-scoping` and `paired-fence-indent-check` in `_mill/discussion.md`.

## Cards

### Card 8: fix-table rows — verify-excludes-edited-tagged-test scoping and indent-drift new message

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite two rows of the Step 1.5 fix table (the `| check | mechanical fix |` table
  under "### Phase: Plan Review", also present verbatim in `mill-plan/SKILL.md`'s own copy of the same
  table) per `_mill/discussion.md`'s `verify-tags-package-scoping` and `paired-fence-indent-check`
  Decisions:

  1. `verify-excludes-edited-tagged-test` row: replace its current cell text (which ends "...append a
     new ` && `-chained invocation of the same base command (same verb and package pattern as the
     existing invocation) carrying its own `-tags <tag>` flag ... Otherwise (no `-tags` flag anywhere in
     the command yet): append `" -tags <tag>"` to the command in place, unchanged.") so both branches
     derive the affected package pattern from the flagged file's own directory (the payload's `path`
     field, e.g. `internal/reedcli/foo_test.go` -> package pattern `./internal/reedcli/`) instead of
     reusing the existing verify command's own (possibly multi-package) pattern:
     - "No `-tags` flag yet" branch: append a new ` && `-chained invocation of the same base command's
       verb, scoped ONLY to the affected package(s) derived from the flagged file's directory, carrying
       `-tags <tag>` — never append `-tags` to the existing multi-package invocation in place.
     - "`-tags` flag already exists" branch: change "same verb and package pattern as the existing
       invocation" to scope the new chained invocation to the flagged file's own package(s) instead of
       the existing invocation's (possibly multi-package) pattern — the identical package-derivation
       rule as the other branch, since the existing invocation may itself be multi-package.
     Keep the row's existing explanation of why comma-joining is unsafe (the ANY-membership /
     mutually-exclusive-suite-convention rationale) unchanged — only the two branches' package-scoping
     guidance changes.

  2. `requirements-quote-indent-drift` row: keep its existing two sentences (the "after stripping N
     leading spaces per line" and "after adding N leading spaces per line" remedies) verbatim, and
     append a new sentence covering the new message shape Card 7 (batch 1) introduces: "A message
     reading '...immediately follows matched fence N, but its first line is indented X spaces vs the
     anchor fence's Y spaces' means the new-code fence's own indentation doesn't match its anchor:
     compute `Y - X`; if positive, add that many leading spaces to every line of the new-code fence; if
     negative, strip `|Y - X|` leading spaces from every line -- mirroring the existing strip/add rows'
     per-line, not textwrap.dedent-style, adjustment -- so the fence's first line ends up indented
     exactly `Y` spaces, matching the anchor fence's own indentation."

  Do NOT edit the `move-target-collision` or `context-completeness` rows — per Decision
  `intra-plan-move-chain` and `declared-symbols-exemption`, neither fix in batch 1 changes any emitted
  message text (both are pure suppression/skip conditions), so neither row's existing remedy text needs
  any change.
- **Commit:** `docs(mill-plan): fix-table guidance for tag-scoping and paired-fence indent drift`

## Batch Tests

`verify: null` — pure documentation batch with no runnable surface. Correctness is verified by matching
the card's edits against `_mill/discussion.md`'s `verify-tags-package-scoping` and
`paired-fence-indent-check` Decisions during code review.
