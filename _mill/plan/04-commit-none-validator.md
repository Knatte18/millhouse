# Batch: commit-none-validator

```yaml
task: mill-plan review severity counting and validation schema gaps
batch: commit-none-validator
number: 4
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-dag.py test-plan-validate.py
depends-on: []
```

## Batch Scope

Delivers the validator-side half of the `Commit: none` verification-only-card feature (issue #664): a shared plan-parsing helper (`_plan_dag.parse_commit_none_card_ids`) that both `_plan_validate.py` (this batch) and `millpy-implement.py`/`_implementer_common.py` (batch 6) use to identify which cards declare `Commit: none`; a new `_plan_validate.py` cross-field check enforcing that a `Commit: none` card has zero content in `Edits:`/`Creates:`/`Deletes:`/`Moves:`; the `plan-batch.md` template documentation for the convention; and a `mill-plan/SKILL.md` fix-table row so a future `mill-plan` session's validator-fix loop (Step 1.5) recognizes the new check name. No existing check needs modification -- `_check_card_missing_field` already accepts any string value (including the literal `none`) for `Commit:`, since it only checks the field label is present, never its value; only a new, additive check is needed.

## Cards

### Card 9: Add `parse_commit_none_card_ids` to `_plan_dag.py`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new public function `parse_commit_none_card_ids(batch_text: str) -> set[int]` to `_plan_dag.py`, placed after `extract_batch_index` and before `_check_shapes` (or any other sensible location among the module's public functions -- follow the file's existing ordering convention of public functions near the top, private `_check_*` helpers below). The function splits `batch_text` into card blocks the same way `millpy-implement.py`'s existing inline `card_ids` computation does (`re.findall(r"(?m)^###\s+Card\s+(\d+)\s*:", batch_text)` identifies card-start lines), then for each card block extracts the `Commit:` field's inline value via `re.search(r"^-\s*\*\*Commit:\*\*(?P<inline>.*)$", <card_block_text>, re.MULTILINE)` and returns the set of card numbers whose extracted value, stripped and lowercased, equals `"none"`. A card with no matched `Commit:` line at all is NOT included in the returned set (that is `_plan_validate`'s existing `card-missing-field` check's job, not this function's). Card blocks are bounded the same way `_plan_validate._parse_cards` bounds them (from a `### Card N:` line up to the next `### ` heading or EOF) -- implement this splitting directly in `_plan_dag.py` (do not import `_plan_validate` from `_plan_dag`; `_plan_dag.py`'s own docstring states callers import it, not the reverse, and `_plan_validate.py` already `import _plan_dag`). Add a docstring explaining the function returns card numbers (not batch-relative indices) whose `Commit:` is the literal `none` sentinel, and that this is used both by `_plan_validate.py`'s cross-field check and by `millpy-implement.py`'s no-content-commit-gate carve-out (batch 6). Add the function to the module's "Public API" docstring list at the top of the file, one line, matching the existing style.
- **Commit:** `feat(plan): add parse_commit_none_card_ids to _plan_dag`

### Card 10: Add the `Commit: none` cross-field validator check

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import _plan_dag` is already present at the top of this file (`_plan_validate.py` already does `import _plan_dag` -- do not add a duplicate import). Add a new private check function `_check_commit_none_with_content(batch_files: list[Path]) -> list[dict]`, placed immediately after `_check_card_missing_field` (which ends at line 714, right before `_check_card_numbering`), following the exact same style as `_check_card_missing_field`: for each `batch_path` in `batch_files`, read its text and call `_plan_dag.parse_commit_none_card_ids(text)` to get the set of `Commit: none` card numbers for this batch. For each such card number, re-parse the batch's cards via the file's existing `_parse_cards(text)` to get that card's `card_lines`, join into `card_text`, and check whether ANY of `Edits`, `Creates`, `Deletes` (matched via the existing `_RE_REFS_HEADER` pattern already defined in this file, scanning only within `card_text`, mirroring `_parse_edits_only`'s single-line-vs-multi-line-sub-bullet logic but scoped to this one card's `card_text` rather than the whole file) or `Moves` (matched via the existing `_RE_MOVES_HEADER` pattern, same card-scoped approach) contains at least one token that is not the literal `none` (case-insensitive). If any field has non-none content, append one error dict per offending card: `{"check": "commit-none-with-content", "batch": batch_path.stem, "card": <card_num>, "path": None, "message": f"card {<card_num>} has Commit: none but non-none <FieldName>: -- verification-only cards must have zero diff"}` (one error per offending field, so a card with both non-none Edits AND non-none Creates produces two error dicts, matching this file's existing one-error-per-offense convention seen in `_check_card_missing_field`). Register the new check in `run()` immediately after the existing `errors.extend(_check_card_missing_field(batch_files))` line: `errors.extend(_check_commit_none_with_content(batch_files))`. Update `run()`'s docstring's check-list summary to mention the new check name, following the existing docstring's listing style. Also append `commit-none-with-content` to the module-level top-of-file docstring's "Checks performed (check keys):" list (currently lines 8-42), mirroring how `_review_common.py`'s and `_plan_dag.py`'s own "Public API" docstring lists are kept in sync with their new functions elsewhere in this plan (cards 1 and 9).
- **Commit:** `feat(plan-validate): reject Commit: none cards with non-none Edits/Creates/Deletes/Moves`

### Card 11: Document the `Commit: none` convention in the plan-batch template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Cards` section's field-documentation list (currently the bullet list starting `- **Context:** every file the implementer reads...` through `- **Commit:** one-line commit message the implementer will use.`), extend the `- **Commit:**` bullet to also document the `none` sentinel: append to that bullet: `Accepts the literal "none" for a verification-only card whose sole job is confirming earlier work (e.g. a grep-and-confirm gate) -- valid ONLY when Edits:/Creates:/Deletes:/Moves: on the same card are ALL also "none" (enforced by the commit-none-with-content validator check); a card with any real edit must always carry a real commit message.` Also update the general "When a field has nothing, write the literal 'none' on the same line as the field label." paragraph immediately below the field list (the one currently listing Context/Edits/Creates/Deletes/Moves fields) to note that `Commit:` now participates in the same `none` convention, but with the cross-field constraint just described (do not imply `Commit: none` is unconditionally free-standing like the other fields' `none`).
- **Commit:** `docs(plan): document Commit: none verification-only-card convention`

### Card 12: Register the new check in mill-plan/SKILL.md's validator fix table

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "Step 1.5: pre-review validator gate" fix table (the markdown table with columns `check` / `mechanical fix`), add a new row for `commit-none-with-content` immediately after the `card-missing-field` row, with a `halt` mechanical fix (matching the table's existing pattern for checks that require planner judgment rather than a safe mechanical rewrite, e.g. the `depends-on-unknown` and `parallel-modifies-overlap` rows' "halt" branches): `Halt -- a card declares Commit: none but also has non-none Edits:/Creates:/Deletes:/Moves:. The planner must either give the card a real Commit: message (if the content is genuinely this card's own work) or move the non-none content to a separate card and leave this card as a true zero-diff verification-only card. Not mechanically fixable -- either resolution changes the plan's structure.` Follow this table's existing row-formatting exactly (pipe-delimited markdown table row, same column widths style as neighboring rows).
- **Commit:** `docs(mill-plan): register commit-none-with-content in validator fix table`

### Card 13: Add unit tests for `parse_commit_none_card_ids` and the new validator check

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-dag.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `test-plan-dag.py`: add tests for `parse_commit_none_card_ids(batch_text)` covering: a batch text with one card whose `Commit:` is a real message -> empty set; a batch text with one card whose `Commit:` is `none` (and, separately, `None`/`NONE` mixed case) -> set containing that card's number; a batch text with 3 cards where only card 2's `Commit:` is `none` -> `{2}`; a batch text where a card has no `Commit:` line at all -> that card's number is NOT in the returned set (empty set for a single-card batch missing the field). Follow this file's existing test function/assertion style (see existing tests in this file for the pattern).

  In `test-plan-validate.py`: first extend the existing `_make_batch_file(...)` helper (currently hardcodes `- **Commit:** feat({name}): card {card_num}\n` at its `Commit` line) to accept a new optional keyword parameter `commit: str | None = None` -- when `None` (the default), preserve today's exact hardcoded output unchanged (`feat({name}): card {card_num}`); when a string is supplied, write `- **Commit:** {commit}\n` instead (so a test can pass `commit="none"`). This is a backward-compatible extension -- every existing call site that omits `commit=` must continue to behave identically. Then add a new `test_check_commit_none_with_content_*` set of test functions (mirroring `test_check_card_missing_field_clean`/`test_check_card_missing_field_dirty`'s structure: build a plan via `_make_overview` + `_make_batch_file` + `_write_plan`, call `_plan_validate.run(plan_dir, project_root)`, filter `result` for `e["check"] == "commit-none-with-content"`), covering: (a) `commit="none"` with all other fields `none` (the default for `_make_batch_file` when `edits`/`creates`/`deletes`/`moves` args are omitted) -> zero errors; (b) `commit="none"` with a non-none `edits=["src/a.py"]` -> exactly one error, `card == 1`, message mentions `Edits`; (c) `commit="none"` with non-none `edits` AND non-none `creates` -> exactly two errors (one per offending field), matching the check's documented one-error-per-offense behavior; (d) a real `commit=` message with real edits (the pre-existing default `_make_batch_file` behavior, `commit=None`) -> zero errors from this check (regression: normal cards are unaffected); (e) a card missing the `Commit:` field entirely (`missing_fields={"Commit"}`) -> zero errors from `commit-none-with-content` specifically (the pre-existing `card-missing-field` check still fires for that card, unaffected -- assert on the `card-missing-field` list separately in this same test to prove the two checks are independent and this card isn't silently exempted from the existing required-field check). Register every new `test_*` function in this file's `main()` in the same style as the existing `test_check_card_missing_field_*` calls.
- **Commit:** `test(plan): cover parse_commit_none_card_ids and commit-none-with-content check`

## Batch Tests

`verify:` runs `test-plan-dag.py` (covers card 9's new `_plan_dag` helper) and `test-plan-validate.py` (covers card 10's new check, using card 9's helper) together via `run-all.py --only`, since both are exercised by this batch's own tests and both are small, fast files -- no unbounded suite run needed.
