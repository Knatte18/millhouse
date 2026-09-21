# Batch: cross-batch-build-break

```yaml
task: mill-plan/mill-start planning-process gaps, round 2
batch: cross-batch-build-break
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-plan-validate-cross-batch-build-break.py
depends-on: []
```

## Batch Scope

Implements the `cross-batch-build-break` `_plan_validate` check (#1056): flags a batch whose card renames/removes a symbol via `Requirements:` while a later (or unordered, per the DAG) batch's own `Requirements:` still references the old symbol name, when the plan opts in by setting the overview's existing top-level `verify:` field (a whole-module compile/vet/smoke command). Card 13 implements and registers the check in `_plan_validate.py`; card 14 adds its tests in a new standalone file (see overview Shared Decisions for why not the existing `test-plan-validate.py`). The check's name and remedy text exactly match batch 1 card 7's fix-table row in `mill-plan/SKILL.md`.

## Cards

### Card 13: `_plan_validate._check_cross_batch_build_break` — implement and register

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add three module-level compiled regexes and one new check function, placed immediately after `_check_batch_oversized` (before the "Public API" section comment and `def run(`):

  ```python
  _RE_RENAME_TO = re.compile(r"rename\s+`([^`]+)`\s+to\s+`([^`]+)`", re.IGNORECASE)
  _RE_REMOVE_SYMBOL = re.compile(r"\bremove\s+`([^`]+)`", re.IGNORECASE)
  _RE_DELETE_SYMBOL = re.compile(r"\bdelete\s+`([^`]+)`", re.IGNORECASE)
  _CROSS_BATCH_BUILD_BREAK_PATTERNS = (_RE_RENAME_TO, _RE_REMOVE_SYMBOL, _RE_DELETE_SYMBOL)


  def _check_cross_batch_build_break(
      batch_files: list[Path],
      overview_path: Path,
      overview_text: str,
  ) -> list[dict]:
      """
      Flag a batch whose Requirements: rename/remove a symbol while a later-or-unordered batch's own
      Requirements: still reference the old symbol name, when the plan's own module-wide `verify:`
      is a whole-module build/compile/vet/smoke command (see #1056).

      Gated on the overview's existing top-level frontmatter `verify:` field (already documented in
      `plugins/mill/templates/plan-overview.md`) being non-null. A plan with `verify: null` has no
      whole-module build-breakage question to ask, so the check is a no-op for it -- no new
      frontmatter field is introduced.

      This is a plan-text-only check: at plan-review time none of the batches have been implemented
      yet, so the actual source tree never reflects any of the plan's renames -- there is nothing
      useful to grep in real source files. Instead, this check scans every OTHER batch's own
      Requirements: text for the literal old-symbol token the renaming batch's Requirements: names.

      A card that mentions the old symbol is exempt when it performs its own rename/removal of that
      same symbol (i.e. its own Requirements: text also matches one of the three patterns with that
      symbol as the matched group) -- that is a further rename in the same chain, not a stale
      reference. A batch that the renaming batch is a transitive ancestor of (via
      `_compute_transitive_ancestors` -- i.e. a batch that depends on the renaming batch, directly
      or transitively) is exempt: the depends-on edge already guarantees it runs after the rename
      lands.

      Error dict shape: ``{check, batch, card, path, message}`` -- `path` carries the stale symbol
      token, `card` the referencing card's number, `batch` the referencing batch's name.

      Args:
          batch_files: Sorted list of batch file paths to validate.
          overview_path: Path to the plan's ``00-overview.md``, whose top-level `verify:` field
              gates this check.
          overview_text: Full text of ``00-overview.md`` (source of the Batch Index DAG).

      Returns:
          List of error dicts, one per stale cross-batch symbol reference found.
      """
      if not overview_path.exists():
          return []
      if _plan_dag._read_batch_frontmatter(overview_path).get("verify") is None:
          return []

      try:
          batches = extract_batch_index(overview_text)
      except PlanDAGError:
          # Check 4 has already recorded the parse error; don't double-report.
          return []

      ancestors = _compute_transitive_ancestors(batches)
      stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}
      batch_name_to_path: dict[str, Path] = {}
      for entry in batches:
          stem = Path(entry.get("file", "")).stem
          if stem in stem_to_path:
              batch_name_to_path[entry["name"]] = stem_to_path[stem]

      def _renamed_symbols(requirements_text: str) -> set[str]:
          symbols: set[str] = set()
          for pattern in _CROSS_BATCH_BUILD_BREAK_PATTERNS:
              for m in pattern.finditer(requirements_text):
                  symbols.add(m.group(1))
          return symbols

      # Collect (renaming_batch_name, old_symbol) pairs from every card's Requirements:.
      renames: list[tuple[str, str]] = []
      for name, path in batch_name_to_path.items():
          text = path.read_text(encoding="utf-8")
          for _card_num, card_lines in _parse_cards(text):
              requirements = _extract_requirements_text("\n".join(card_lines)) or ""
              for old_symbol in _renamed_symbols(requirements):
                  renames.append((name, old_symbol))

      errors: list[dict] = []
      for renaming_batch, old_symbol in renames:
          for other_name, other_path in batch_name_to_path.items():
              if other_name == renaming_batch:
                  continue
              if renaming_batch in ancestors.get(other_name, set()):
                  # renaming_batch is an ancestor of other_name -- other_name is guaranteed to run
                  # after the rename lands (the depends-on edge already covers it) -- not at risk.
                  continue
              text = other_path.read_text(encoding="utf-8")
              for card_num, card_lines in _parse_cards(text):
                  requirements = _extract_requirements_text("\n".join(card_lines)) or ""
                  if old_symbol not in requirements:
                      continue
                  if old_symbol in _renamed_symbols(requirements):
                      continue
                  errors.append({
                      "check": "cross-batch-build-break",
                      "batch": other_name,
                      "card": card_num,
                      "path": old_symbol,
                      "message": (
                          f"batch '{other_name}' card {card_num} Requirements: still reference "
                          f"'{old_symbol}', renamed/removed by batch '{renaming_batch}', with no "
                          f"depends-on edge ordering this batch after it"
                      ),
                  })
      return errors
  ```

  Register the new check in `run()`: add `errors.extend(_check_cross_batch_build_break(batch_files, overview_path, overview_text))` immediately after the existing `errors.extend(_check_cross_batch_creates_no_depends_on(batch_files, overview_text))` line (both are dependency-graph-aware checks over the same `overview_text`).

  Update `run()`'s own docstring, the sentence listing every check name ("Checks 1, 2, 3, 4, 5, 6, 8 from issue #10, plus wiki-config-mutation, ..., cross-batch-creates-no-depends-on, and verify-batch-mismatch."), to append `, and cross-batch-build-break` at the end of that list.

  Also add a new bullet to the MODULE-level docstring at the very top of the file (the "Checks performed (check keys):" list, e.g. immediately after the existing `cross-batch-creates-no-depends-on — ...` bullet), mirroring that list's existing one-entry-per-check style:

  ```
      cross-batch-build-break — a batch's Requirements: rename/remove a symbol while a
          later-or-unordered batch's own Requirements: still reference the old symbol name, gated on
          the overview's top-level verify: field being non-null
  ```

  No new parameter is added to `run()` itself — `batch_files`, `overview_path`, and `overview_text` are already local variables in `run()` by the point this call is inserted.
- **Commit:** `feat(plan-validate): add cross-batch-build-break check`

### Card 14: standalone unit tests for `cross-batch-build-break`

- **Context:**
  - `plugins/mill/unit_tests/test-plan-validate-card-numbering.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-plan-validate-cross-batch-build-break.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create `plugins/mill/unit_tests/test-plan-validate-cross-batch-build-break.py`, mirroring `test-plan-validate-card-numbering.py`'s exact structure and header-comment convention (own standalone file with a docstring stating why it is not appended to `test-plan-validate.py`, `sys.path.insert` of `HUB / "plugins" / "mill" / "scripts"`, import of `_plan_validate` directly, own minimal local fixture helpers — do NOT import anything from `test-plan-validate.py`). Write local fixture helpers that build a minimal overview text (with a `Batch Index` yaml block naming batches/deps and a top-level frontmatter `verify:` field the test controls) and minimal batch-file text (a single `### Card N:` heading followed by a `- **Requirements:**` line, since `_check_cross_batch_build_break` reads only the Requirements: field via `_parse_cards`/`_extract_requirements_text` and the Batch Index via `extract_batch_index` — no `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:`/`Commit:` fields are needed for this check's own logic, though real plan files always have them).

  Cover exactly these three scenarios (mentioned, not read — the file citing them is this task's own discussion.md, not a file the implementer needs to open):
  1. **Fires:** overview `verify:` set (non-null); batch `alpha` (`depends-on: []`) has a card whose Requirements: reads `` Rename `Engine.HeaderText` to `Engine.StatusLineText`. ``; batch `beta` (`depends-on: []`, no edge to `alpha`) has a card whose Requirements: mentions `` `Engine.HeaderText` `` without itself renaming it. Assert `_plan_validate._check_cross_batch_build_break(batch_files, overview_path, overview_text)` returns exactly one error dict with `check == "cross-batch-build-break"`, `batch == "beta"`, and `path == "Engine.HeaderText"`.
  2. **Does not fire (depends-on edge present):** identical to scenario 1, except batch `beta`'s `depends-on: ["alpha"]` (both the per-batch file's own frontmatter `depends-on:` and the overview Batch Index entry, matching this repo's `depends-on-batch-mismatch` convention that both sides must agree). Assert the result is empty.
  3. **Skipped (verify: null):** identical to scenario 1's batch/card setup, but the overview's top-level `verify:` field is `null` (or omitted). Assert the result is empty.

  Use `tempfile.TemporaryDirectory()` for the plan directory in every test, matching every other `_plan_validate` test file's fixture style. Give each test function a `-> None` return type and a bare `assert` (raising `AssertionError` on failure, matching `test-plan-validate-card-numbering.py`'s per-function style exactly — not the `-> int` / `errors += 1` style `test-plan-validate.py` itself uses), print a `"PASS: <test name>"` line on success, and register all three in a `tests` list inside a `def main() -> int:` function with an `if __name__ == "__main__":` guard. This `main()` shape (iterate the `tests` list, catch and report each function's failure independently, return a nonzero exit code if any failed) is NOT what `test-plan-validate-card-numbering.py`'s own `main()` does today (that file calls its four tests directly inside one shared `try`/`except AssertionError` block, with no `tests` list — a failure in an earlier test there prevents later ones from running); write the list-iteration shape described here directly, without citing that file's `main()` as a mirror for it.
- **Commit:** `test(plan-validate): cross-batch-build-break check fixtures`

## Batch Tests

`verify:` runs `test-plan-validate.py` (the existing, large regression suite for `_plan_validate.run()` — a necessary check here since card 13 adds a new call into `run()`'s dispatch chain that runs on every existing fixture in that file too; confirms no existing fixture's overview `verify:` value accidentally trips the new check) and the new `test-plan-validate-cross-batch-build-break.py` (card 14's three targeted scenarios). `test-plan-dag.py` is not included — this batch never touches `_plan_dag.py` itself, only calls its already-existing `extract_batch_index`/`_read_batch_frontmatter`/`parse_verify_field` (unmodified).
