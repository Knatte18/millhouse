# Batch: commit-none-backend-gate

```yaml
task: mill-plan review severity counting and validation schema gaps
batch: commit-none-backend-gate
number: 6
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: [4]
```

## Batch Scope

Delivers the code-derived exemption to `_implementer_common.py`'s no-content-commit gate, so a batch whose reported cards are all `Commit: none` verification-only cards is not mechanically demoted to `stuck_type: logic` for making zero commits. The exemption signal (`commit_none_card_ids`) is computed by `millpy-implement.py` from the batch plan file on disk via batch 4's `_plan_dag.parse_commit_none_card_ids` -- never trusted from the implementer's own self-report (Shared Decision "the no-content-commit-gate carve-out signal is code-derived, never implementer self-reported"). Depends on batch 4 for `_plan_dag.parse_commit_none_card_ids`.

## Cards

### Card 15: Thread `commit_none_card_ids` through `_reclassify_verify_failure`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new private helper function `_cards_done_all_commit_none(cards_done, commit_none_card_ids: set[int] | None) -> bool`, placed immediately before `_reclassify_verify_failure` (currently starting at line 102). The helper returns `False` if `commit_none_card_ids` is `None` or empty, `False` if `cards_done` is `None`, coerces `cards_done` entries to `int` the same way `_cards_incomplete_reason` already does (`{int(x) for x in cards_done}` inside a `try`/`except (ValueError, TypeError)` returning `False` on failure), returns `False` if the coerced set is empty, and otherwise returns whether the coerced set is a subset of `commit_none_card_ids` (`coerced.issubset(commit_none_card_ids)`). Add `commit_none_card_ids: set[int] | None = None` as a new parameter to `_reclassify_verify_failure`'s signature, after the existing `cards_done=None` parameter. `_reclassify_verify_failure`'s current signature has no bare `*` separator (`cards_done=None` is positional-or-keyword, unlike `finalize_from_output`/`_forward_output` in card 16, which already use `*`) -- insert `*,` immediately before `cards_done` in the signature (making both `cards_done` and the new `commit_none_card_ids` genuinely keyword-only, matching every existing call site, which already passes `cards_done=` by keyword). Update its docstring's Args section to document the new parameter: "commit_none_card_ids: card numbers whose Commit: field is the literal none, computed by the caller from the batch plan file (never self-reported); when the coerced cards_done is a non-empty subset of this set, the content==0 reclassification below is skipped." Modify the `if content == 0:` block (currently lines 149-160) to `if content == 0 and not _cards_done_all_commit_none(cards_done, commit_none_card_ids):` -- when the new condition is False (the exemption applies), execution falls through to the existing `reason = _cards_incomplete_reason(card_ids, cards_done, content)` line below unchanged, which already correctly reports "batch incomplete" if `cards_done` does not cover every card in `card_ids` (e.g. real cards in the same batch remain undone) or returns None (batch complete, verify_stuck returned unchanged) when `cards_done` covers everything -- no further change needed to `_cards_incomplete_reason` itself.
- **Commit:** `feat(implement): thread commit_none_card_ids through verify-failure reclassification`

### Card 16: Thread `commit_none_card_ids` through the top-level no-content-commit check

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `commit_none_card_ids: set[int] | None = None` as a new keyword-only parameter to both `finalize_from_output` (currently ending its signature at line 1202) and `_forward_output` (currently ending its signature at line 1316), threaded from `finalize_from_output` straight into its `_forward_output(...)` call unchanged (same pattern as every other existing passthrough parameter in that function, e.g. `card_ids`). Document the new parameter in both functions' docstrings following the existing Args-list style, same wording as card 15's `_reclassify_verify_failure` docstring addition.
  Inside `_forward_output`, thread `commit_none_card_ids=commit_none_card_ids` into the existing `_reclassify_verify_failure(...)` call (currently lines 1392-1399, which already passes `cards_done=_cards_done`).
  Then modify the two top-level no-content-commit `if` conditions to also consult `_cards_done_all_commit_none(_cards_done, commit_none_card_ids)` (the helper added in card 15; `_cards_done` is already in scope, assigned at line 1377 from `parsed.get("cards_done")`):
  1. `if start_sha is not None and not nits_only:` (currently line 1431) -> the nested `if result.returncode == 0 and result.stdout.strip() == start_sha:` (currently line 1436) becomes `if result.returncode == 0 and result.stdout.strip() == start_sha and not _cards_done_all_commit_none(_cards_done, commit_none_card_ids):`.
  2. The nested `if result.returncode == 0 and _is_only_start_batch_commit(project_root, start_sha):` (currently lines 1452-1454) becomes `if result.returncode == 0 and _is_only_start_batch_commit(project_root, start_sha) and not _cards_done_all_commit_none(_cards_done, commit_none_card_ids):`.
  When either condition's new clause is False (the exemption applies), that `if` block's body (the `print(json.dumps({"status":"stuck","stuck_type":"logic",...}))` + `return 0`) is skipped, and execution falls through to the existing `_batch_completeness_stuck(...)` call (currently lines 1475-1483) unchanged -- that gate already correctly recognizes a batch as complete when `cards_done` covers every declared `card_ids` entry, regardless of raw commit count, so no further change is needed there.
- **Commit:** `feat(implement): exempt all-Commit:-none success reports from the no-content-commit gate`

### Card 17: Compute `commit_none_card_ids` in `millpy-implement.py` and thread it into finalize

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately after the existing `card_ids: set[int] = {...}` computation (currently lines 370-372, which reads `_batch_text`), add: `commit_none_card_ids: set[int] = _plan_dag.parse_commit_none_card_ids(_batch_text)` (reusing the already-read `_batch_text` variable; `_plan_dag` is already imported in this file per its existing `_plan_dag._read_batch_frontmatter` and `_plan_dag.parse_verify_field` usage). Add a one-line comment above it mirroring the style of the existing `card_ids` comment, explaining this set feeds the no-content-commit gate's `Commit: none` carve-out (batch 6, cards 15-16), computed from the batch file on disk rather than trusted from implementer self-report. This file has TWO call sites that pass `card_ids=card_ids` to a finalize-style call, and both need the same new keyword argument added, mirroring the existing `card_ids` threading exactly:
  1. The `--stage finalize` branch's `finalize_from_output(...)` call (currently lines 406-421): add `commit_none_card_ids=commit_none_card_ids` as a new keyword argument, following the existing `card_ids=card_ids` line.
  2. The `--stage full` branch's `_forward_output(...)` call (currently lines 672-687, the synchronous/subprocess dispatch path -- a second, symmetric call site distinct from the finalize-stage one): add `commit_none_card_ids=commit_none_card_ids` as a new keyword argument, following the existing `card_ids=card_ids` line there too. Both call sites read the same `commit_none_card_ids` local variable computed once above; do not compute it twice.
- **Commit:** `feat(implement): compute commit_none_card_ids from the batch file for the no-content-commit gate`

### Card 18: Add unit tests for the `Commit: none` no-content-commit-gate exemption

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add new test cases to `test-implementer-common.py`, modeled directly on the existing "Case 27: #500 regression" block (currently lines 1173-1209: `_setup_fixture(project_root)` for `base_sha`, no new commit so `HEAD == start_sha`, `verify_cmd = "exit 0"`, call `_forward_output(agent_output, project_root, start_sha=base_sha, snapshot_path=snapshot_path, verify_cmd=verify_cmd)`, parse the JSON captured from stdout). Add these cases immediately after case 27, using the same fixture helpers already imported/used in this file:
  1. **Exemption fires:** same zero-commit setup as case 27, but `agent_output` includes `"cards_done":[1,2]` and the call passes `commit_none_card_ids={1, 2}` and `card_ids={1, 2}` (so the completeness gate also sees full coverage). Assert the result is `status: success` (not `stuck`/`logic`) -- the exemption suppresses the no-content-commit demotion and the completeness gate recognizes `cards_done` covers `card_ids`.
  2. **Exemption does not overfire on a mixed batch:** same zero-commit setup, `agent_output` includes `"cards_done":[1,2]`, but `commit_none_card_ids={1}` only (card 2 is a real card, falsely or mistakenly reported alongside a commit-none card with no actual commit made) and `card_ids={1, 2}`. Assert the result is still `status: stuck, stuck_type: logic` with `"no content commit"` in the reason (case-insensitive), proving the exemption requires cards_done to be a subset of commit_none_card_ids, not merely overlapping it.
  3. **`commit_none_card_ids` absent (default None) behaves exactly as today:** repeat case 27's exact setup and assertions verbatim but do not pass `commit_none_card_ids` at all -- regression-proves the new parameter is opt-in and does not change existing zero-commit-report behavior for calls that never populate it (e.g. calls originating from `millpy-fix.py`, which this task does not modify).
  4. **`_reclassify_verify_failure` exemption:** call `_reclassify_verify_failure` directly (already imported or importable from `_implementer_common` in this test file -- add the import if not already present) with a synthetic `verify_stuck` dict, `content` effectively 0 (no commits since `start_sha` in a fresh fixture), `card_ids={3}`, `cards_done=[3]`, `commit_none_card_ids={3}` -- assert the returned dict does NOT have `stuck_type: logic` with a "no content commit" reason (either the original `verify_stuck` is returned unchanged, or an `incomplete` reclassification occurs per `_cards_incomplete_reason`, depending on how `card_ids`/`cards_done` compare -- assert specifically that it is NOT the content==0 "no content commit" logic dict, i.e. the premature hard-fail was skipped). Follow this file's existing direct-call test pattern for `_reclassify_verify_failure` if one already exists elsewhere in the file (search for `_reclassify_verify_failure(` in this file) as the template for fixture setup; otherwise construct the minimal required fixture inline.
  Follow this file's existing PASS/FAIL print convention, `errors` counter, and case-numbering comment style (ASCII-only per project `CLAUDE.md`).
  These cases exercise `_forward_output` directly, which is the shared function BOTH of `millpy-implement.py`'s call sites (the `--stage finalize` branch via `finalize_from_output`, and the `--stage full` branch calling `_forward_output` directly -- see Card 17) delegate to identically. The gate logic itself is therefore fully covered by these direct-call tests; only the two call sites' own kwarg-threading (each passing `commit_none_card_ids=commit_none_card_ids` alongside the existing `card_ids=card_ids`, per Card 17) is covered by code-identity with the existing, already-tested `card_ids` threading pattern rather than by a discrete `millpy-implement.py`-level test -- no separate test is needed for that wiring since it mirrors a pattern this codebase already trusts for `card_ids`.
- **Commit:** `test(implement): cover Commit: none no-content-commit-gate exemption`

## Batch Tests

`verify:` runs `test-implementer-common.py` in full (not `--only`-scoped further, since it is already the single dedicated test file for `_implementer_common.py` and this batch's changes touch that module's core gate logic directly -- a targeted subset would risk missing an interaction with a neighboring existing gate, e.g. the completeness or dirty-tree gates that run immediately after the no-content-commit checks this batch modifies).
