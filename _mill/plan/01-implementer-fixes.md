# Batch: implementer-fixes

```yaml
task: "millpy-implement finalize/resume fixes and the red integration suites"
batch: "implementer-fixes"
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
depends-on: []
```

## Batch Scope

Delivers the two `_implementer_common.py` fixes (#1163 `Commit: none` recount, #1162 briefs excluded from the finalize dirty gate at any depth), unit tests for both, and the `mill-go-base` resume-procedure note.
One batch: the two code fixes share one source file and one unit-test file; the doc edit is a single paragraph tied to the same issue.

## Cards

### Card 1: Commit: none cards excluded from the count-only completeness recount

- **Context:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a keyword parameter `commit_none_card_ids: set[int] | None = None` to `_cards_incomplete_reason`.
  In its inner `_count_only_reason`, compute `expected = len(card_ids - (commit_none_card_ids or set()))` and compare `content < expected`; the reason text reports `expected` instead of `len(card_ids)`.
  The `cards_done` set-difference branch is unchanged.
  Add the same keyword to `_batch_completeness_stuck` and forward it to `_cards_incomplete_reason`; in `_reclassify_verify_failure` forward its existing `commit_none_card_ids` argument to `_cards_incomplete_reason` as well.
  Then find every call of `_batch_completeness_stuck` and `_cards_incomplete_reason` in the file (use grep) and pass `commit_none_card_ids=commit_none_card_ids` from the enclosing `_forward_output` scope, where the value is already a parameter.
  Update the docstrings of `_cards_incomplete_reason` and `_batch_completeness_stuck` to describe the new argument.
- **Commit:** `fix(implementer-common): ignore Commit: none cards in the count-only completeness recount`

### Card 2: unit tests for the Commit: none recount

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append new numbered cases before the final `if errors:` block of `main`, following the file's existing `try/except` + `errors += 1` + `PASS:` print style and the `_setup_fixture` helper.
  Recount cases (call `_batch_completeness_stuck` directly with `card_ids={1, 2, 3}` and `commit_none_card_ids={2}`): (a) two content commits after `base_sha`, `cards_done=None` -> `None`; (b) one content commit, `cards_done=None` -> stuck/incomplete whose reason names 2 expected cards; (c) `cards_done=["x"]` (malformed) with two commits -> `None`; (d) without `commit_none_card_ids` the two-commit case still returns incomplete (regression guard); (e) `_reclassify_verify_failure` with the same inputs does not report incomplete for two commits.
- **Commit:** `test(implementer-common): cover the Commit: none recount`

### Card 3: finalize dirty gate excludes orchestrator-owned briefs at any depth (reproduce first)

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Reproduce before fixing: first add the dirty-gate unit cases below (before the final `if errors:` block of `main`, same style as the other cases), run them, and confirm the nested-layout case fails on the current code.
  Dirty-gate cases via `_in_scope_dirty_stuck` (or `_forward_output` as case 57 does): with a nested layout `hub/_mill/briefs/implement-b-r1.md` and `implement-b-r1.out.md` committed after `base_sha`, then modified in the working tree, the gate returns `None`; the same modification to a real in-scope file (for example `hub/src.txt`) still returns the stuck dict; a flat `_mill/briefs/...` modification returns `None`.
  The mechanism: in `_in_scope_dirty_stuck`, `owned_paths` comes from `git diff --name-only <start_sha>` and is matched against `_pygit2_util.status_porcelain` lines, both repo-root-relative; the current exclusion `line.startswith("_mill/briefs/")` therefore misses `<subdir>/_mill/briefs/...` in a nested (hub-relative) layout.
  Fix: replace the prefix test with a small module-level helper `_is_brief_path(path: str) -> bool` returning True when `("/" + path)` contains `"/_mill/briefs/"`, and use it in the `owned_paths` comprehension.
  The source of the briefs location is deliberately the fixed `_mill/briefs/` path component rather than the `task_dir` argument; if the reproduction shows this predicate is not the failing piece, keep the fix on the finalize side (adjust whichever `owned_paths` or porcelain matching the reproduction shows to be wrong) and record the discrepancy in the commit body.
  Do not touch the resume-incomplete branch of prepare and never add a second `mill-go: start batch`-style commit.
  Then implement the fix and confirm all cases pass.
  Update the `_in_scope_dirty_stuck` docstring paragraph about `_mill/briefs/` to say the exclusion applies at any depth.
- **Commit:** `fix(implementer-common): exclude nested _mill/briefs paths from the finalize dirty gate`

### Card 4: mill-go-base blocked-batch resume procedure names --resume-incomplete

- **Context:**
  - `plugins/mill/skills/mill-go-base/resume.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `### Entry: resuming a blocked batch after external fix` subsection, extend step 5 ("Re-run `/mill-go`") with a short note: when step 2 decided `preserve_start_sha = True`, the resumed batch's prepare stage must be run as `--stage prepare <batch_name> --resume-incomplete` (Execute's normal prepare would re-capture `start_sha` at HEAD and discard the preserved value); when `False`, the normal prepare applies.
  Cross-reference the `--resume-incomplete` fallback in the Agent-mode dispatch step 5.5 instead of restating its mechanics.
  Do not edit `resume.md`; it is listed under Context only, to confirm its routing needs no change.
  No `sed`; use the Edit tool.
- **Commit:** `docs(mill-go-base): use --resume-incomplete when resuming a blocked batch with preserve_start_sha`

## Batch Tests

`verify:` runs `test-implementer-common.py` only, the unit file both code fixes and their new cases live in; the batch touches no cross-cutting helper that other unit files import beyond the two functions covered there.
