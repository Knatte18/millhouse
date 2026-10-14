# Batch: merge-in-recompute-removal

```yaml
task: "Drop the eager verify-baseline pre-flight"
batch: "merge-in-recompute-removal"
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-brief-commit.py
depends-on: []
```

## Batch Scope

Removes the post-sync baseline recompute: the `--recompute-baseline` mode of `millpy-merge-in-subagent.py` and step `### 3.5. Baseline recompute` of the `mill-merge-in` skill (discussion Decision `merge-in-recompute-removed`).
After this batch, `millpy-merge-in-subagent.py` no longer imports `_verify_baseline` and no longer calls any `_status` module-baseline function or writes `verify_baseline_failures`, which batch 4 relies on.
Independent of batches 1 and 2.

## Cards

### Card 5: Remove --recompute-baseline from millpy-merge-in-subagent.py

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Module docstring `Flags:` section: change the `--mode` entry to `--mode conflicts|verify-fix which delegation mode to run; required` (drop `unless --recompute-baseline is set`) and delete the four-line `--recompute-baseline ...` entry.
  - Delete the `import _verify_baseline` line.
  - Delete the function `_run_recompute_baseline` in full.
  - In `main()`:
    - Delete the `parser.add_argument("--recompute-baseline", ...)` call.
    - Replace the `if not args.recompute_baseline and not args.mode:` check with `if not args.mode:` and change its message to `--mode is required`; keep the manual `print(..., file=sys.stderr)` plus `return 1` shape (`--mode` stays `required=False` in argparse so the existing exit-1 contract holds).
    - Delete the `if args.recompute_baseline:` dispatch block.
  - Grep the file for `recompute`, `baseline`, `_verify_baseline` afterwards and confirm zero hits.
  - Then apply the overview's `unused-import-check` Decision to this file.
- **Commit:** `refactor(merge-in): remove --recompute-baseline mode`

### Card 6: Update merge-in subagent tests

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Delete `test_20_recompute_baseline_missing_status_md` through `test_27_recompute_baseline_sets_module_verify_baseline_from_compute_baseline_return_value`, plus the helpers `_write_recompute_baseline_fixture` and `_batch_verify_baseline_failures`.
  - Update `test_9_missing_mode`: docstring becomes `--mode absent -> exit 1, no SystemExit.` followed by one sentence that `main()` validates `--mode` manually with a print plus `return 1` rather than an argparse-required flag; the assertion becomes `self.assertIn("--mode is required", stderr_buf.getvalue())` plus `self.assertNotIn("recompute", stderr_buf.getvalue())`.
  - Add `test_recompute_baseline_flag_rejected`: `millpy_merge_in_subagent.main(["--recompute-baseline"])` raises `SystemExit` with `code == 2` (patch `sys.stderr` to an `io.StringIO`).
  - After this card, grep the file for `recompute`, `verify_baseline`, `_verify_baseline` and confirm only the new rejection test and the `assertNotIn` hit remain.
- **Commit:** `test(merge-in): drop recompute-baseline tests, assert flag rejected`

### Card 7: Delete step 3.5 from mill-merge-in SKILL.md

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Delete the section `### 3.5. Baseline recompute` in full: from its heading down to (not including) `### 4. Verify`, which covers the "Runs unconditionally ..." paragraph, the Agent-mode note, the `millpy-bg` callout, both fenced bash blocks, the polling text, the two bullets, and the trailing `Rationale:` paragraph(s).
  - Grep the file for `3.5`, `recompute`, `baseline`, `verify_baseline_failures`, `--stage baseline` afterwards; rewrite any surviving sentence that refers to step 3.5 or the recompute so it no longer does (none were found at planning time outside the section).
  - Do not renumber the remaining steps.
- **Commit:** `docs(merge-in): remove baseline recompute step`

## Batch Tests

`verify:` runs `test-millpy-merge-in-subagent.py` (CLI behaviour) and `test-brief-commit.py`, which reads `mill-merge-in/SKILL.md` and asserts its `git add _mill/briefs/` step survives the section deletion.
Both were green on the task branch tip before this batch.
