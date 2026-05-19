# Batch: cutover

```yaml
task: "Dedicated fixer agent for post-holistic-review fix cycles"
batch: "cutover"
number: 3
cards: 3
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
depends-on: [2]
```

## Batch Scope

Cuts the orchestrator over to `millpy-fix.py` and removes every artifact that the cut-over made dead. Mill-go's per-batch fix dispatch (Execute step 3 sub-step 4 REQUEST_CHANGES branch) and holistic fix dispatch (Holistic-code-review step 5) both swap from the old implementer scripts to the new fixer CLI. Per-batch psmux cleanup moves to run immediately after the implementer's `success` report is parsed (before the cleanliness gate and review CLI), making the warm session unnecessary across the review window. The `--resume` branch of `millpy-implement.py` and its template `implementer-fix.md`, the entire `millpy-implement-holistic.py` script with its template `implementer-holistic-brief.md` and unit-test file, and the `--resume` test cases in `test-millpy-implement.py` all go. After this batch the only live fix path is `millpy-fix.py`.

Batch-local decisions:
- Card ordering inside this batch matters operationally but not for correctness: the SKILL.md edit (card 7) does not depend on the deletions, but landing it before the deletions is the natural review order. The `verify:` for the batch is `run-all.py`, which only passes after every card lands -- specifically after card 8 removes the deleted-test reference and card 9 finishes the SKILL.md cut-over.

## Cards

### Card 7: Cut mill-go SKILL.md over to millpy-fix.py and reorder per-batch psmux cleanup

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Five surgical edits to `mill-go/SKILL.md`:

  1. **Per-batch fix dispatch (REQUEST_CHANGES branch of Execute step 3 sub-step 4).** Replace the `millpy-bg --slug fix-<batch_name>-r<N>` block that currently invokes:
     ```
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume --round <N> --review-file <review-file-abs-path>
     ```
     with:
     ```
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>
     ```
     Update the surrounding sentence "resumes the warm implementer session with the fix prompt" to read "dispatches a cold-start fixer session with the fix prompt". Leave the rest of the paragraph (`millpy-receiving-review` reference, JSON-parse rules, stuck escalation) unchanged.

  2. **Holistic fix dispatch (REQUEST_CHANGES branch of holistic-code-review step 5).** Replace the inline invocation:
     ```
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement-holistic.py" --review-file <abs-path-to-holistic-review-file> --round {H}
     ```
     with:
     ```
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-fix.py" --scope holistic --review-file <abs-path-to-holistic-review-file> --round {H}
     ```
     Replace every other prose mention of `millpy-implement-holistic.py` in the same section (the "Holistic session cleanup" paragraph at the top of the Holistic code review section and the captured-`session_id` paragraph) with `millpy-fix.py --scope holistic`. The holistic-cleanup-block bash snippet itself does not need to change -- it only cleans up `holistic_sid`, which is still produced.

  3. **Resume section's `fixing` branch.** In the Resume section (around the `**`fixing`**` row), replace the invocation:
     ```
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume --round <review_round> --review-file <review-file-abs-path>
     ```
     with:
     ```
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <review_round>
     ```
     Update the `--slug fix-<batch_name>-r<review_round>-resume` argument unchanged. Leave the surrounding "CLI handles state transitions atomically" sentence unchanged -- it still applies.

  4. **Per-batch psmux cleanup relocation.** In the Execute / Per-batch session cleanup paragraph (just before the cleanup-block code), reword the trigger list. Currently it reads "Every time the per-batch implement-review-fix loop terminates (APPROVE, max-rounds blocked, cleanliness-blocked, stuck-blocked) OR the Builder is about to re-dispatch the implementer with a fresh session (transient-retry-once)". Change it to: "Every time the per-batch implementer reports `success` (immediately after step 2 parse, before step 2b cleanliness gate), AND on every loop terminus (APPROVE, max-rounds blocked, cleanliness-blocked, stuck-blocked), AND when the Builder is about to re-dispatch the implementer with a fresh session (transient-retry-once). The post-success invocation is the primary cleanup point now that fix dispatch is cold-start; the terminal invocations remain for defence-in-depth and are idempotent no-ops when the session is already gone." Then in Execute step 2 (Parse implementer report), add a new sentence at the very end of the section that reads: "After a `success` report (before the cleanliness gate at step 2b), invoke the per-batch cleanup block -- the cold-start fixer used in step 4 REQUEST_CHANGES does not need the warm session." Do NOT add a new cleanup block; just reference the existing one.

  5. **Update the diff-policy footnote.** In the Board discipline bullet at the end of the file that begins "`status_path`, `reviews_dir/<file>`, ...", replace the phrase "`millpy-implement.py` pushes its own task-branch state commits (batch-start, fix-cycle) to `origin/<task-branch>`" with "`millpy-implement.py` and `millpy-fix.py` push their own task-branch state commits (batch-start, batch-fix, holistic-fix) to `origin/<task-branch>`". This keeps the push-policy doc accurate after the cutover.

  No other section of `mill-go/SKILL.md` changes. Do not introduce new bullets, new sections, or change unrelated wording.
- **Commit:** `mill-go: cut over to millpy-fix; reorder per-batch psmux cleanup`

### Card 8: Remove --resume branch from millpy-implement.py

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete the `--resume`, `--round`, and `--review-file` argparse declarations from `millpy-implement.py`. Delete the `if args.resume and not args.review_file` check. Delete the entire `else: # Fix-cycle resume` branch (the block starting around line 214 in current head, ending at the function return at the end of `main`). The remaining structure of `main` is: parse args (only positional `batch_name`), the common setup block, the "if not args.resume" body (now unconditional -- remove that conditional and the corresponding indentation; the function ends after the `return _forward_output(...)` line). Remove the `import _timestamp` line at the top of the file -- after the resume branch is gone, `_timestamp` is no longer referenced (its sole use was `_timestamp.now_utc_iso()` inside the deleted branch). Update the module docstring -- remove the lines mentioning `--resume`, `--round`, `--review-file`, and the "resumes one for a fix cycle" sentence; the docstring now describes only the fresh per-batch dispatch.

  In `test-millpy-implement.py`, delete every test function that exercises the `--resume` path (any test whose argv to `_run_main` includes `--resume`) and remove those names from the `tests = [...]` registration list at the bottom (if one exists) or from `unittest`'s auto-discovery (no change needed for the `unittest.main()` style). Keep every test that exercises the fresh dispatch path. If the file uses `unittest.TestCase`, deleting the method definitions is sufficient.
- **Commit:** `implement: remove --resume branch; fix dispatch lives in millpy-fix.py`

### Card 9: Delete millpy-implement-holistic.py and its dead templates and tests; update _implementer_common docstring

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/templates/implementer-fix.md`
  - `plugins/mill/templates/implementer-holistic-brief.md`
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- **Requirements:** Delete the four files listed in Deletes via `git rm`. After deletion, edit `_implementer_common.py`'s module docstring (line 1): replace `"""Shared helpers for millpy-implement.py and millpy-implement-holistic.py."""` with `"""Shared helpers for millpy-implement.py and millpy-fix.py."""`. No other change to `_implementer_common.py` -- `_forward_output` is still consumed by both `millpy-implement.py` and the new `millpy-fix.py`.

  Cross-check before committing: run `Grep` for the strings `millpy-implement-holistic`, `implementer-fix.md`, and `implementer-holistic-brief` across `plugins/mill/`. The only remaining hits should be in `_codeguide/` (if any), `.scratch/`, and the deleted-by-this-card commit's own diff context. Each of the deleted-template references inside the (now also deleted) `millpy-implement-holistic.py` is removed by the same `git rm`. If any live reference survives (e.g., a stray docstring elsewhere), surface it as `stuck_type: logic` rather than guessing.
- **Commit:** `cleanup: delete millpy-implement-holistic and dead fix templates`

## Batch Tests

`uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` -- the full unit-test suite must pass. Specifically: `test-millpy-implement.py` (modified -- only fresh-dispatch tests remain) must PASS; `test-millpy-implement-holistic.py` (deleted in card 9) must NOT appear in the test sweep; `test-millpy-fix.py` (from batch 2) must still PASS. There is no orchestrator integration test in this repo's unit-test directory -- the SKILL.md edits in card 7 are reviewed by the holistic code review pass.
