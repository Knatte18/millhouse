# Batch: validator-move-checks

```yaml
task: "Add first-class Moves/Renames field to plan cards for rename-heavy batches"
batch: "validator-move-checks"
number: 2
cards: 8
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-millpy-validate-plan.py
depends-on: [1]
```

## Batch Scope

This batch teaches `_plan_validate.py` about `Moves:`: it makes `Moves:` a
required card field, adds five new structural checks (`move-format`,
`move-redundant`, `move-source-missing`, `move-target-collision`,
`move-mechanic-missing`), and feeds Move endpoints into the four existing checks
that account for paths (`non-existent-path`, `all-files-touched-mismatch`,
`parallel-modifies-overlap`, `batch-oversized`) per `## Shared Decisions`
(move-endpoint-accounting). It imports `parse_moves` / `compute_moves_union`
from batch 1 (single-moves-parser). The required-field change is a global
invariant flip; its fixture impact is contained to this batch's two test files
(`test-review-cli.py` passes `--skip-validate`, and the review-flow tests do not
invoke the validator).

## Cards

### Card 4: Require Moves field and import the shared parser

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_plan_validate.py`, extend the existing `from _review_common import (...)` block (lines ~41-47) to also import `parse_moves` and `compute_moves_union`. Add `"Moves"` to `_REQUIRED_CARD_FIELDS` (line ~65), positioned after `"Deletes"` and before `"Requirements"`. Do NOT add `Moves` to the module's `_RE_REFS_HEADER` (line ~54). This card makes `_check_card_missing_field` require a `Moves:` field on every card.
- **Commit:** `feat(plan-validate): require Moves card field`

### Card 5: move-format and move-redundant checks

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `_check_move_format(batch_files) -> list[dict]`: for each `- **Moves:**` header that is not inline `none`, each sub-bullet MUST match exactly `` `<src>` -> `<dst>` `` (two backtick paths separated by ` -> `); a sub-bullet that is missing the arrow, has only one backtick path, or carries prose yields an error dict with `check="move-format"`. Add `_check_move_redundant(batch_files) -> list[dict]`: for each batch, if a path is a Move endpoint (source or target via `parse_moves`) AND the same path also appears in that batch's `Creates:` or `Deletes:` (via the existing `_parse_creates_only` / `_parse_deletes_only`), emit `check="move-redundant"`. Only the identical path triggers it — a `Moves:` target plus a different `Creates:` path (the extraction pattern) is allowed. Error dicts follow the existing shape `{check, batch, card, path, message}`.
- **Commit:** `feat(plan-validate): add move-format and move-redundant checks`

### Card 6: move-source-missing and move-target-collision checks

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `_check_move_source_missing(batch_files, project_root, root, creates_union, moves_targets, *, wiki_root=None, git_root=None) -> list[dict]`: a Move source that does not resolve on disk (via the existing `resolve_existing_paths`) AND is not in `creates_union` and not in `moves_targets` (an earlier batch may create or relocate it into place) yields `check="move-source-missing"` — modeled on the Deletes branch of `_check_non_existent_path`. Add `_check_move_target_collision(batch_files, project_root, root, creates_union, *, wiki_root=None, git_root=None) -> list[dict]`: a Move target that resolves on disk (already exists), OR is named as a target by more than one card across the plan, OR collides with a `Creates:` target in a DIFFERENT batch (cross-batch), yields `check="move-target-collision"`. Do NOT flag a target that also appears in `Creates:`/`Deletes:` within the SAME batch — that same-batch duplication is `move-redundant`'s job (card 5), so the two checks do not double-report. Use deterministic sorted iteration for stable output, matching sibling checks.
- **Commit:** `feat(plan-validate): add move-source-missing and move-target-collision checks`

### Card 7: move-mechanic-missing check

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `_check_move_mechanic_missing(batch_files) -> list[dict]`: for each batch file, if `parse_moves` returns at least one non-empty pair for any card, the batch file text MUST contain a heading line matching `^##\s+Rename mechanic\b` (the canonical section authored by batch 3 in `plan-batch.md`); if absent, emit `check="move-mechanic-missing"` with a message naming the batch. A batch whose every `Moves:` is `none` is not checked.
- **Commit:** `feat(plan-validate): add move-mechanic-missing check`

### Card 8: Feed move endpoints into non-existent-path and all-files-touched

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Modify `_check_non_existent_path` to accept a `moves_targets` set and add it to the suppression alongside `creates_union` (a downstream card editing a Move target must not raise `non-existent-path`). Do NOT add Move-source existence logic here — Move-source existence is solely `move-source-missing`'s responsibility (card 6), so a genuinely missing source is reported once, not twice. `non-existent-path` continues to operate only on the general `Context:`/`Edits:`/`Creates:` refs and `Deletes:` tokens it already parses (it does not parse `Moves:` bullets via `_RE_REFS_HEADER`). Modify `_check_all_files_touched_mismatch` so `cards_set` includes Move **targets** (add `compute_moves_union(plan_dir)[1]`), keeping Move sources excluded — mirroring the existing exclusion of `Deletes:` tokens (issue #494). The function signatures change here; the `run()` call sites are updated in card 10.
- **Commit:** `feat(plan-validate): account for moves in non-existent-path and all-files-touched`

### Card 9: Feed move endpoints into parallel-overlap and batch-oversized

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Modify `_check_parallel_modifies_overlap` so each batch's "touched" set used for overlap detection includes that batch's Move sources AND targets (via `parse_moves`), in addition to the current `_parse_edits_only`. Modify `_check_batch_oversized` so the context-token byte estimate includes Move **sources** (the implementer reads them) and excludes Move **targets** (they do not exist yet) — mirroring how `Creates:` targets are excluded from the estimate.
- **Commit:** `feat(plan-validate): account for moves in parallel-overlap and batch-oversized`

### Card 10: Wire new checks and Move unions into run()

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `run()` (line ~1010), compute `moves_sources, moves_targets = compute_moves_union(plan_dir)` near the existing `creates_union` / `deletes_union` computation (line ~1058). Call the five new check functions (`_check_move_format`, `_check_move_redundant`, `_check_move_source_missing`, `_check_move_target_collision`, `_check_move_mechanic_missing`) and `extend` `errors` with their results, passing `moves_targets` / unions where the signatures from cards 6/8 require. Thread the Move unions into the modified `_check_non_existent_path`, `_check_all_files_touched_mismatch`, `_check_parallel_modifies_overlap`, and `_check_batch_oversized` calls. Add the five new check keys to the module-docstring "Checks performed" list (lines ~13-31). Preserve the existing `errors.sort(...)` and `skip_checks` filtering at the end.
- **Commit:** `feat(plan-validate): wire move checks and unions into run`

### Card 11: Validator tests and required-field fixture sweep

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `Moves: none` to EVERY existing card fixture in both test files so the new required-field check does not break unrelated cases (the required-field sweep). Add positive/negative tests for each new check: `move-format` (malformed bullet flagged, well-formed passes), `move-redundant` (same path in Moves+Creates flagged; Moves target plus different Creates path passes), `move-source-missing` (missing source flagged; suppressed when an earlier batch creates/moves it), `move-target-collision` (pre-existing target, duplicate target, and Creates collision flagged), `move-mechanic-missing` (non-empty Moves without `## Rename mechanic` flagged; present passes), and `card-missing-field` now firing when `Moves:` is absent. Add fixtures proving endpoint feeding: a downstream card editing a Move target does NOT raise `non-existent-path`; a Move target appears in the All Files Touched reconciliation; two parallel batches touching the same Move endpoint raise `parallel-modifies-overlap`.
- **Commit:** `test(plan-validate): cover move checks and sweep fixtures for required Moves field`

## Batch Tests

`verify:` runs `test-plan-validate.py` and `test-millpy-validate-plan.py` — the
only two suites that invoke `_plan_validate` with full card fixtures (verified:
`test-review-cli.py` bypasses the validator with `--skip-validate`, and the
review-flow tests do not call the validator). Scoping to these two files fully
covers the required-field flip and the new checks.
