# Batch: inplace-reorder

```yaml
task: 39 (A) — mill-start question-format UX
batch: inplace-reorder
number: 2
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Reorders `_inplace.prompt_stale_worktree` so the safe-default option ("Abort") sits at position 1 and is tagged `(Recommended)`, complying with the strengthened global rule. Updates the matching unit tests so input-string→returncode mappings reflect the new order. The function's external contract is unchanged: callers in `millpy-cleanup.py:269` and `mill-merge/SKILL.md` consume only the string return value (`"abort"` / `"inplace"` / `"worktree"`), so this is internally a behaviour-preserving reorder of the user-facing menu plus its input dispatch.

External interface: `prompt_stale_worktree(slug, worktree_path) -> Literal["abort","inplace","worktree"]`. Signature, return type, and docstring's stated returncodes unchanged. The docstring's enumeration of the menu and the `Returns:` clause are updated.

Batch-local decisions: none beyond `## Shared Decisions` in the overview.

## Cards

### Card 5: reorder `_inplace.prompt_stale_worktree` menu and input mapping

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/scripts/_inplace.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_inplace.py`, change the `prompt_stale_worktree` function so the menu reads, in this order:
  - `1) Abort (Recommended)`
  - `2) Treat as in-place — skip worktree remove`
  - `3) Treat as worktree — run git worktree remove`
  Update the three `print(...)` lines that emit the menu (currently lines 102–104) to match the new order. Update the input-dispatch branches so `raw == "1"` returns `"abort"`, `raw == "2"` returns `"inplace"`, `raw == "3"` returns `"worktree"`. Keep the invalid-input fallback (returning `"abort"`) and the EOF fallback (returning `"abort"`) unchanged. Update the docstring under `prompt_stale_worktree`: replace the menu enumeration in the existing prose (currently shows the old order at lines 84–86) with the new order, and update the `Returns:` clause so the choice→string mapping reflects `"abort"` when 1, `"inplace"` when 2, `"worktree"` when 3 or on invalid / EOF input — note the EOF/invalid cases also map to `"abort"`, which is now also option 1, so describe this as the "fail-safe default" in one short sentence appended to the `Returns:` clause. The `[1/2/3]` shown in `input("Choice [1/2/3]: ")` stays the same.
- **Commit:** `fix(_inplace): reorder prompt_stale_worktree menu — Abort is option 1`

### Card 6: update `test-inplace.py` fixtures and test names

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-inplace.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/unit_tests/test-inplace.py`, update the existing tests so they reflect the new input mapping defined in card 5. Specifically, in the section starting at line 119 (the `# prompt_stale_worktree tests` block):
  - Rename `_test_prompt_stale_worktree_returns_inplace_on_choice_1` to `_test_prompt_stale_worktree_returns_abort_on_choice_1` and update its stdin fixture and assertion so input `"1"` is expected to return `"abort"` (the function's new option-1 mapping).
  - Rename `_test_prompt_stale_worktree_returns_worktree_on_choice_2` to `_test_prompt_stale_worktree_returns_inplace_on_choice_2` and update so input `"2"` returns `"inplace"`.
  - Rename `_test_prompt_stale_worktree_returns_abort_on_choice_3` to `_test_prompt_stale_worktree_returns_worktree_on_choice_3` and update so input `"3"` returns `"worktree"`.
  - Keep `_test_prompt_stale_worktree_returns_abort_on_invalid_choice` (line 156) — the assertion that an invalid choice returns `"abort"` is still correct.
  - Keep `_test_prompt_stale_worktree_returns_abort_on_eof` (line 167) — the assertion that EOF returns `"abort"` is still correct.
  - Update the corresponding entries in the `tests` list near line 189 to reference the renamed test functions in the new mapping order. Three rename-edits in the function-name list; the two unchanged tests stay in their existing positions.
  Update the `print("PASS prompt_stale_worktree — input '1' -> 'inplace'")` style PASS-message strings inside each renamed test to reflect the new expected return string (`'abort'` / `'inplace'` / `'worktree'` respectively).
- **Commit:** `test(_inplace): update prompt_stale_worktree tests for reordered menu`

## Batch Tests

Verified by running `python plugins/mill/unit_tests/run-all.py` (the batch's `verify:` command). The renamed tests in `test-inplace.py` cover the three valid inputs; the invariant tests cover invalid input and EOF. Run-all also re-executes every other helper test, so a regression in any other helper would surface here. No new tests are added because no new code paths are introduced — only the input→string mapping changes.
