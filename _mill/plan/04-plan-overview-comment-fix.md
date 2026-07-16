# Batch: plan-overview-comment-fix

```yaml
task: "Miscellaneous small tooling and doc/template accuracy gaps"
batch: "plan-overview-comment-fix"
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Closes GitHub #632: `plugins/mill/templates/plan-overview.md`'s "All Files Touched" section
claims "mill-go reads this to warn if two parallel batches touch the same file" — false. The
only consumer is `_plan_validate.py`'s `all-files-touched-mismatch` check (a cross-check of
the derived union of every card's `Edits:`/`Creates:`/Move-target paths against this
section's declared list); parallel-overlap warnings come from a separate, unrelated check,
`parallel-modifies-overlap`, which reads the cards directly. This batch corrects the comment
to describe the section's real role. Pure documentation edit, no executable surface.
External interface for later batches: none.

## Cards

### Card 10: correct the "All Files Touched" section's stated role

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/templates/plan-overview.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "## All Files Touched" section's italic descriptive paragraph
  (currently: *"Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across
  every batch, sorted alphabetically (Move **source** paths are excluded — they disappear,
  like `Deletes:` tokens). mill-go reads this to warn if two parallel batches touch the same
  file — a sign of a misplaced dependency."*), keep the first two sentences (the
  union/exclusion description) unchanged — they are accurate. Replace only the final
  sentence ("mill-go reads this to warn if two parallel batches touch the same file — a sign
  of a misplaced dependency.") with prose stating the section's actual role: it is the input
  `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the
  derived union of every card's `Edits:`/`Creates:`/Move-target paths — cards are the source
  of truth, and this section exists to catch drift between the hand/agent-maintained list and
  that derived union. Do NOT claim mill-go reads this section, and do NOT mention
  parallel-batch overlap detection anywhere in this paragraph — that behavior belongs to the
  separate `parallel-modifies-overlap` check, which reads the cards directly and has no
  relationship to this section.
- **Commit:** `docs(plan-overview): correct All Files Touched section's stated role`

## Batch Tests

`verify: null` — a template comment wording change only. `_plan_validate.py`'s
`all-files-touched-mismatch` check behavior is unaffected (only prose changes, not the
section's structure or parse format); no automated test exists for template comment
content, per `_mill/discussion.md`'s Testing section for #632.
