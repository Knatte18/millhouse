# Batch: verdict-summary-demotion-note

```yaml
task: 'millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale'
batch: verdict-summary-demotion-note
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-class-taxonomy.py
depends-on: []
```

## Rename mechanic

N/A — no `Moves:` in this batch.

## Batch Scope

Add a new helper, `append_demotion_note`, to `_review_common.py`, and call it unconditionally from
`finalize_scope` whenever `demoted_any` is `True` — independent of `rewrite_verdict_token`'s own
`demoted_any and verdict != original_verdict` gate, which stays exactly as-is (it only ever
controlled the persisted verdict *token*, never the one-sentence summary). The new helper appends a
deterministic note directly after the existing `## Verdict` section's summary line, stating the
post-ceiling demoted-finding count and the current `blocking_count`, so the on-disk review file
never self-contradicts its own frontmatter/envelope when a ceiling demotion has occurred — whether
or not that demotion also happened to flip the aggregate verdict token. This batch is independent
of Batches 1-3 and 5 (it touches only `_review_common.py`, `review-output.schema.md`, and their
tests) and can run in parallel with any of them.

## Cards

### Card 12: add the `append_demotion_note` helper to `_review_common.py`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new module-level function `append_demotion_note(raw_text: str, demoted_count: int, blocking_count: int) -> str` placed immediately after `rewrite_verdict_token` and before `write_review_file` (i.e. between the two existing functions, matching the file's top-to-bottom pipeline ordering).
  - Implementation: split `raw_text` into lines via `raw_text.splitlines(keepends=True)`, matching `rewrite_verdict_token`'s own splitting approach. Locate the `## Verdict` heading the same way `rewrite_verdict_token` does (a line whose `.rstrip("\n")` equals exactly `"## Verdict"`). If no such heading is found, return `raw_text` unchanged (defensive only, same posture as `rewrite_verdict_token`'s own heading-not-found fallback).
  - From the heading, find the first subsequent non-blank line (`.strip() == ""` test) — this is the verdict token line, located the same way `rewrite_verdict_token` locates it. From the token line, find the *next* subsequent non-blank line after it — this is the one-sentence summary line. If either the token line or the summary line cannot be found (end of file reached), return `raw_text` unchanged.
  - Build the note string: `f"_Note: {demoted_count} finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is {blocking_count}._\n"`.
  - If the summary line does not already end with `"\n"` (it is the last line in the file), append `"\n"` to it in place first, so the inserted note starts on its own line.
  - Insert the note string as a new list element immediately after the summary line's index, then return `"".join(lines)`.
  - Add a docstring describing the function's purpose (append a demotion note after the `## Verdict` summary, independent of whether the verdict token itself changed), its args, and its no-op-when-heading-absent behavior — following the docstring style already used by `rewrite_verdict_token` immediately above it in the same file.
- **Commit:** `feat(review-common): add append_demotion_note helper for stale Verdict-summary staleness`

### Card 13: wire `append_demotion_note` into `finalize_scope`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `finalize_scope`, inside the `if blocking_classes is not None:` block where `demoted_any = any(f.demoted for f in findings)` is already computed, add a sibling line immediately after it: `demoted_count = sum(1 for f in findings if f.demoted)`. Initialize `demoted_count = 0` alongside the existing `demoted_any = False` initialization above the `if blocking_classes is not None:` block, so both names are always bound regardless of which branch runs (matching the existing pattern for `demoted_any`).
  - Immediately after the existing `if demoted_any and verdict != original_verdict: raw_text = rewrite_verdict_token(raw_text, verdict)` block (leave that block's condition and body completely unchanged), add a new, independent block: `if demoted_any: raw_text = append_demotion_note(raw_text, demoted_count, blocking_count)`. This must run after `rewrite_verdict_token` (whether or not that block actually executed) and before `review_path = write_review_file(...)`, since the note is appended into whatever `raw_text` looks like at write time.
  - Update `finalize_scope`'s docstring to mention the new unconditional-on-`demoted_any` demotion-note step in its "Runs, in order: ..." summary sentence, immediately after the existing mention of `rewrite_verdict_token`.
- **Commit:** `fix(review-common): finalize_scope appends a demotion note whenever ceiling demotes a finding`

### Card 14: document the demotion note in `review-output.schema.md`

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the `### \`## Verdict\`` section's contract description, change "Contains exactly two lines:" to "Contains exactly two lines, plus an optional third line when a ceiling demotion occurred (see below):" — the fenced two-line example block immediately below stays unchanged (it documents the base contract; the optional third line is documented in prose, not by editing the example).
  - Immediately after the existing sentence "The verdict line must match the `verdict:` field in the yaml block exactly.", add one new sentence: "When the stage's `blocking_classes` ceiling demotes one or more findings from BLOCKING to NIT, `finalize_scope` appends a third line directly after the summary: `_Note: N finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is M._` — present only when at least one finding was demoted this call, absent otherwise."
  - Do not change the earlier, top-of-file `## Verdict` fenced-block skeleton (around line 36-40, the whole-document skeleton) — only the `### \`## Verdict\`` body-sections contract description gets the update, since that is the section documenting the actual field-by-field contract validators and consumers rely on.
- **Commit:** `docs(review-schema): document the conditional demotion-note third line in the Verdict contract`

### Card 15: unit tests for `append_demotion_note` via `finalize_scope`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `test_demotion_note_appended_when_verdict_flips` (covers #822 — token and note both change): reuse this file's existing `_finalize`/`_verdict_yaml`/`_verdict_section`/`_heading` helpers with the same fixture shape as the existing `test_verdict_token_rewritten_on_ceiling_flip` (discussion type, `resolve_blocking_classes({}, "discussion", None)`, one `BLOCKING:scope` finding — which the discussion ceiling demotes since only `design` survives). Assert the written text contains `"_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._"`, in addition to the already-established token-flip assertions (`"verdict: APPROVE" in written_text`).
  - Add `test_demotion_note_appended_without_verdict_flip` (covers #829 — count-only staleness, no token flip): build a discussion-type fixture with the discussion ceiling (`resolve_blocking_classes({}, "discussion", None)`, where only `design` survives BLOCKING) and two findings: one `BLOCKING:design` (survives the ceiling, stays BLOCKING) and one `BLOCKING:scope` (demoted to NIT). The resulting `blocking_count` stays `1` both before and after the ceiling (`original_verdict == "REQUEST_CHANGES"`, post-ceiling `verdict == "REQUEST_CHANGES"` too — no flip), so `rewrite_verdict_token` is never invoked, but `demoted_any` is still `True`. Assert the written text's verdict token is unchanged (`"verdict: REQUEST_CHANGES" in written_text`) AND contains `"_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._"`.
  - Add `test_demotion_note_absent_when_no_demotion`: reuse the existing `test_verdict_token_unchanged_when_no_demotion` fixture shape (a single `NIT:design` finding, no BLOCKING at all, so `apply_blocking_ceiling` demotes nothing). Assert `"_Note:"` does NOT appear anywhere in the written text — locking in that this batch's change is a strict no-op when `demoted_any` is `False`.
  - Add all three new `(label, test_fn)` tuples to the `TESTS` list at the bottom of the file, following the existing tuple-formatting convention (multi-line tuple form for labels that need it, matching the style already used for entries like `"verdict token rewritten on ceiling flip"`).
  - Do not modify any existing test function in this file — these are additive-only.
- **Commit:** `test(review-class-taxonomy): cover the demotion-note append in flip and no-flip cases`

## Batch Tests

`verify:` runs `test-review-class-taxonomy.py` in full — Card 15's three new cases plus every
pre-existing case in this file (ceiling table, demotion rewrite, verdict-token rewrite/no-rewrite,
etc.), confirming the new unconditional `append_demotion_note` call in `finalize_scope` does not
regress any existing byte-exact assertion (in particular `test_verdict_token_unchanged_when_no_demotion`'s
exact-substring check, which this batch's Card 15 also covers directly via the new
`test_demotion_note_absent_when_no_demotion` case).
