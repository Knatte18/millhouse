# Batch: heuristic-gaps

```yaml
task: '_plan_validate.py: path-reference heuristic false positives (round 3) + run() docstring drift'
batch: heuristic-gaps
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

Five independent, small fixes to `_plan_validate.py`'s `context-completeness` heuristic (plus one
unrelated docstring-drift fix on the same file's `run()`), folded into a single task as five GitHub
issues (#807, #805, #793, #789, #796). All fixes live in one file
(`plugins/mill/scripts/_plan_validate.py`), with a companion doc update in
`plugins/mill/skills/mill-plan/SKILL.md` and new unit-test coverage in
`plugins/mill/unit_tests/test-plan-validate.py`. One batch because the total diff is small, every
card after card 1 depends on reading the current state of `_check_context_completeness` (which two
of the cards edit directly), and splitting into multiple batches would force artificial
inter-batch dependencies over a single ~2000-line file. Cards run in the fixed order below because
card 2 must land before card 3 (card 3's message-string edit sits a few lines from card 2's new
exemption-check insertions in the same function body) and card 5's tests exercise the combined
result of cards 1-4.

## Cards

### Card 1: extend _PROHIBITION_MARKERS with change/modify negation phrasing (#789)

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend the module-level `_PROHIBITION_MARKERS` tuple (~line 1365) with four new
  substrings: `"never change"`, `"not change"`, `"never modify"`, `"not modify"`. Mirror the existing
  two-tier "touch" coverage pattern already in the tuple (a specific `"never touch"` plus a catch-all
  `"not touch"` that already subsumes `"must not touch"`/`"do not touch"` as substrings), applied to
  the two verbs `change`/`modify` the brief names. Do NOT add `"edit"` variants -- out of scope per
  `_mill/discussion.md`'s `prohibition-marker-change-modify` Decision. Preserve the tuple's existing
  entries and comment line unchanged; only add the four new lines.
- **Commit:** `fix(plan-validate): extend _PROHIBITION_MARKERS with change/modify negation phrasing`

### Card 2: thread moves_sources + add _CITATION_MARKERS exemption (#807, #805)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Add a new module-level tuple `_CITATION_MARKERS`, placed immediately after
     `_PROHIBITION_MARKERS` (~line 1371) and before `_PATH_CANDIDATE_EXTENSIONS`, with a preceding
     comment line in the same style as `_PROHIBITION_MARKERS`'s own comment (explaining this tuple
     exempts a *different* semantic class -- "named as an example/citation" vs "must not act on").
     Contents, exactly: `"as an example"`, `"as examples"`, `"for example"`, `"e.g."`, `"such as"`,
     `"cited as"`, `"citing"`.
  2. Add a `moves_sources: set[str]` parameter to `_check_context_completeness`'s signature (~line
     1453), positioned immediately BEFORE the existing `moves_targets: set[str]` parameter (mirrors
     `compute_moves_union`'s `(sources, targets)` return-tuple order).
  3. Add a `moves_sources:` entry to `_check_context_completeness`'s `Args:` docstring block,
     immediately before the existing `moves_targets:` entry, reading: "Plan-wide union of Moves:
     source paths."
  4. Rewrite the docstring's "Two exemptions prevent false positives:" numbered list (currently: 1.
     prohibition-marker sentences, 2. non-path-shaped/unresolvable tokens) into a "Three exemptions
     prevent false positives:" list with items: (1) prohibition-marker sentences (unchanged wording),
     (2) citation-marker sentences (e.g. "naming `x.py` as an example") cite a file for illustration,
     not as an unlisted read dependency, (3) a token matching the plan-wide `moves_sources` set is
     exempt in any later card's `Requirements:`, not just the declaring card's own -- mirrors how
     `creates_union`/`deletes_union` are already plan-wide. Move the existing
     non-path-shaped/unresolvable-token note out of the numbered list into its own sentence
     immediately after the list (it is a pre-filter, not a marker-style exemption) -- do not delete
     its content, only relocate and de-number it.
  5. In `_check_context_completeness`'s per-token loop, immediately after the existing
     prohibition-marker exemption block (`if any(marker in lowered_line for marker in
     _PROHIBITION_MARKERS): continue`), add a citation-marker exemption block of the same shape: `if
     any(marker in lowered_line for marker in _CITATION_MARKERS): continue`, with a preceding comment
     analogous to the prohibition-marker block's comment.
  6. In the same loop's own-refs exemption block, immediately after `if stripped_token in own_refs:
     continue`, add `if stripped_token in moves_sources: continue`.
  7. Update the call site in `run()` (~line 2710-2714,
     `errors.extend(_check_context_completeness(...))`) to pass `moves_sources` positionally in the
     new parameter order (immediately before `moves_targets`, using the `moves_sources` local already
     computed at ~line 2677 via `compute_moves_union(plan_dir)` and currently discarded).
- **Commit:** `feat(plan-validate): thread moves_sources and add _CITATION_MARKERS exemption to context-completeness`

### Card 3: qualify context-completeness message and SKILL.md fix-table row with Moves:-source (#793)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In `_check_context_completeness`'s error-emission site (~line 1561-1565, the `"message":
     (...)` f-string), change the trailing field list from `Context:/Edits:/Creates:/Deletes:/Moves:`
     to `Context:/Edits:/Creates:/Deletes:/Moves:-source`.
  2. In `plugins/mill/skills/mill-plan/SKILL.md`'s `context-completeness` fix-table row (~line 320),
     change ONLY the row's first clause -- currently "the card's own
     `Edits:`/`Creates:`/`Deletes:`/`Moves:` already covers it" -- to "the card's own
     `Edits:`/`Creates:`/`Deletes:`/`Moves:`-source already covers it". Do NOT touch the row's later
     clause ("a token that legitimately belongs to `Deletes:`/`Moves:`-source means the check should
     not have fired at all") -- it is already correctly qualified; a blind find/replace across the
     whole row would turn it into `Moves:-source-source`.
- **Commit:** `fix(plan-validate): qualify context-completeness message and SKILL.md row with Moves:-source`

### Card 4: sync run() docstring signature with real params (#796)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update the module docstring's `run(...)` public-API one-line summary (top of
  file, ~line 9) from `run(plan_dir, project_root, *, root=None, wiki_root=None, git_root=None,
  skip_checks=frozenset()) -> list[dict]` to also list `max_cards_per_batch=10,
  max_batch_context_tokens=120000, parent_branch=None`, matching the real `def run(...)` signature
  (~line 2615), which already has all three params with those exact defaults. Purely a
  doc-accuracy fix -- no behavior change.
- **Commit:** `docs(plan-validate): sync run() docstring signature with real params`

### Card 5: unit tests for #807/#805/#793/#789 context-completeness fixes

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add six new test functions, following the file's existing
  `_make_overview`/`_make_batch_file`/`_write_plan` fixture convention and one-test-per-scenario
  naming (`test_check_context_completeness_<clean|dirty>_<scenario>`), each filtering the
  `_plan_validate.run(plan_dir, project_root)` result by `check == "context-completeness"` and
  printing `PASS <name>` / `FAIL <name>: <exc>` exactly like the neighboring tests in this file.
  Insert all six new functions immediately after
  `test_check_context_completeness_dirty_odd_backtick_count_line_field` (before
  `test_check_requirements_quote_indent_drift_clean_exact_match`), and register each new function's
  name in `main()`'s `tests` list immediately after the existing
  `test_check_context_completeness_dirty_odd_backtick_count_line_field` entry, in the same order:
  1. `test_check_context_completeness_clean_citation_marker` (#807): a single-batch, single-card plan
     whose card's `Requirements:` cites a real, on-disk fixture file via one of the new
     `_CITATION_MARKERS` phrases (e.g. a line reading `"...citing \`src/a.py\` as an example of the
     pattern to follow."`) where the card's own `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:`
     does NOT include `src/a.py` -> assert 0 `context-completeness` errors.
  2. `test_check_context_completeness_dirty_citation_marker_absent` (#807 regression guard): the same
     fixture as test 1 but with the `Requirements:` line reworded to drop every `_CITATION_MARKERS`
     phrase while still referencing `src/a.py` (e.g. `"See \`src/a.py\` for the pattern to
     follow."`) -> assert 1 `context-completeness` error (proves the new tuple does not over-exempt
     unmarked references).
  3. `test_check_context_completeness_clean_moves_source_plan_wide` (#805): two batches --
     `01-alpha.md` (`depends-on: []`) whose card 1 declares `Moves: \`old.py\` -> \`new.py\`` (plus a
     `## Rename mechanic` section) with `old.py` present on disk, and `02-beta.md` (`depends-on:
     [1]`) whose card 2 has `Requirements:` mentioning `old.py` with no own-ref coverage on card 2 ->
     assert 0 `context-completeness` errors (was 1 before this fix).
  4. `test_check_context_completeness_dirty_moves_target_plan_wide_still_flagged` (#805 companion):
     same two-batch shape as test 3, but batch beta's card 2 `Requirements:` mentions `new.py` (the
     Move *target*, not source) instead of `old.py`, still with no own-ref coverage -> assert 1
     `context-completeness` error (target-only exemption behavior is unchanged across batches, same
     intent as the existing same-card `test_check_context_completeness_dirty_moves_target_only`).
  5. `test_check_context_completeness_message_includes_moves_source_qualifier` (#793): reuse
     `test_check_context_completeness_dirty_missing`'s fixture shape (one card, `Requirements:`
     referencing an on-disk file absent from its own refs) and assert the single error's `message`
     field contains the exact substring `"Moves:-source"` (not bare `"Moves:"` with no suffix).
  6. `test_check_context_completeness_clean_prohibition_marker_change_modify` (#789): a single card
     whose `Requirements:` has two lines -- one reading `"...do not change \`x.py\`..."` and one
     reading `"...must not modify \`y.py\`..."` -- each referencing a real on-disk fixture file
     (`x.py`, `y.py`) absent from the card's own refs -> assert 0 `context-completeness` errors
     total.
- **Commit:** `test(plan-validate): cover #807/#805/#793/#789 context-completeness fixes`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-plan-validate.py` directly (not via `run-all.py`) --
every card in this batch edits only `_plan_validate.py` and this single test file, so a full-file
run is already scoped tightly and there is no cross-cutting-helper justification needed for a
broader `run-all.py --only` invocation.
