# Batch: reviewer-and-docs-sync

```yaml
task: '_plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose'
batch: reviewer-and-docs-sync
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
depends-on: [1]
```

## Batch Scope

This batch closes the validator-versus-reviewer disagreement and syncs the planner-facing documentation. The LLM plan reviewer currently blocks on any path in a card's `Requirements:` absent from `Context:` or `Edits:`, with none of the validator's exemptions, so it burns review rounds on findings the validator was designed to suppress. Three cards rewrite that criterion in both plan-review templates and update mill-plan's own fix table and phrasing guidance; a fourth pins the template wording with an assertion so a later edit cannot silently drop it.

It depends on batch 1 only, so it may run in parallel with batches 2 and 3; it touches no file those batches touch. `plugins/mill/scripts/_plan_validate.py` is listed as read-only `Context:` on every card here so the documented exemption list can be checked against the shipped implementation rather than against this plan's prose.

Batch-local decision beyond the overview's Shared Decisions: the two plan-review templates' criterion bullets are near-identical today and must stay in step. Wording that differs between them would produce scope-dependent verdicts on the same plan, so both cards use the same enumeration.

## Cards

### Card 18: Holistic plan-review template exemption enumeration

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite the `Context completeness` criterion bullet in `plugins/mill/templates/review-plan-holistic.md` so it keeps its current BLOCKING rule but adds an explicit exemption list the reviewer must apply before raising a finding. Keep the existing first sentence's meaning — a `Requirements:` reference to a function, class, or constant from a file listed in neither `Context:` nor `Edits:` is BLOCKING — and keep the existing follow-on sentences about `Context:` being the implementer's read allowlist and a missing entry meaning cold-start exploration. Then enumerate the cases that are not findings, mirroring the exemptions `_check_context_completeness` implements: a path named on a same-line prohibition; a path named on a citation, contrast, or escape-marker line, including the markers `signature inlined`, `no file read needed`, and `mentioned, not read`; a path inside quoted material, meaning a fenced block or a blockquote line, within `Requirements:`; a git-ignored path; a path outside the repository, including absolute and home-relative literals; a trailing-slash directory reference; and a forward reference to a path a later card in the plan declares as its own `Creates:` target. State that a path in any of those categories must not be raised, because the remedy the reviewer would be asking for — adding the path to `Context:` — is either impossible or actively wrong. Leave every other criterion bullet in the file untouched, and preserve verbatim the existing All-Files-Touched-scope bullet, the platform-behavior-claim-verification bullet, the mechanism-claims-must-be-source-verified sentence, and the MILL_REVIEW markers; a pre-existing test asserts each of those is present.
- **Commit:** `docs(review-templates): mirror validator context-completeness exemptions in holistic plan review`

### Card 19: Batch plan-review template exemption enumeration

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Apply the same rewrite as card 18 to the `Context completeness` criterion bullet in `plugins/mill/templates/review-plan-batch.md`, using the identical exemption enumeration and the identical wording, so the two templates cannot drift into scope-dependent verdicts. Position the new text so it reads consistently with the file's existing reviewer note stating that the plan reviewer sees only the union of `Context:` and `Edits:` and must not flag missing `Creates:` files — the forward-reference exemption is that same idea extended from the bulk to `Requirements:` prose, and the bullet should say so in one clause rather than restating the note. Leave every other criterion bullet untouched and preserve the same verbatim passages card 18 preserves.
- **Commit:** `docs(review-templates): mirror validator context-completeness exemptions in batch plan review`

### Card 20: mill-plan fix table and phrasing guidance

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Make two edits to `plugins/mill/skills/mill-plan/SKILL.md`. First, in the Step 1.5 fix table's `context-completeness` row, keep the existing add-to-`Context:` remedy and the existing note that the error payload's line field carries the offending Requirements line, but state up front that the remedy applies only when no exemption covers the token, and list the escape hatches available to the planner instead: the `mentioned, not read` marker for a path named but not read; the existing `signature inlined` and `no file read needed` markers for an inlined signature; moving quoted material into a fenced block or a blockquote line; and rephrasing a not-involved mention into one of the supported negation forms. Second, extend the Principles bullet that currently covers one-line prohibitions and double negatives into guidance covering the added exemptions, keeping its existing two paragraphs intact and appending the new material: that a contrast citation is exempt only when the path sits in the same clause as `rather than` or `instead of`, with no comma, semicolon, colon, or period between them; that a path inside a fenced block or on a blockquote line within `Requirements:` is exempt; that a git-ignored path, an out-of-repository literal, and a trailing-slash directory reference are exempt automatically and need no phrasing accommodation; and that a forward reference to a later card's `Creates:` target is exempt while a backward reference to an earlier card's target is a genuine dependency the planner must declare. Do not alter any other fix-table row and do not renumber or reorder the Principles list.
- **Commit:** `docs(mill-plan): document context-completeness exemptions and escape hatches`

### Card 21: Template assertion for the exemption enumeration

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-plan-batch.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-templates.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add one test function to `plugins/mill/unit_tests/test-review-templates.py` asserting that both plan-review templates' raw source carries the context-completeness exemption enumeration cards 18 and 19 added, and register it wherever the file already registers its test functions for execution. Follow the shape of the file's existing criteria-bullet assertions: read each template's raw source through the same helper those tests use, loop over the two plan-review template names, and assert on short distinctive substrings rather than on whole paragraphs, so ordinary rewording does not break the test while removal does. Assert at minimum that each template names the `mentioned, not read` marker and mentions the forward-reference-to-a-later-card exemption. Give the function a docstring stating that the enumeration exists to keep the LLM reviewer from blocking on findings the validator deliberately suppresses, so a future editor removing it understands the cost.
- **Commit:** `test(review-templates): assert plan-review exemption enumeration is present`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-review-templates.py` directly, the file card 21 edits and the file that asserts on plan-review template content. It is the right gate for this batch because it both guards the passages cards 18 and 19 must preserve — the render check, the All-Files-Touched-scope bullet, the platform-behavior-claim bullet, the mechanism-claim sentence, and the MILL_REVIEW markers — and, after card 21, pins the new enumeration itself. Card 20 edits a skill document with no runnable surface and therefore contributes no assertion; it is verified by the plan reviewer reading it against the shipped implementation, which is why `plugins/mill/scripts/_plan_validate.py` is on every card's `Context:` in this batch.
