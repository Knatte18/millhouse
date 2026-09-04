# Batch: test-corroboration-write-commit

```yaml
task: 'millpy-implement/fix.py: stuck-type false positives and session-hygiene gaps'
batch: test-corroboration-write-commit
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: [1]
```

## Batch Scope

Adds regression coverage for #954, split into its own batch (rather than folding into batch 1) purely to keep each batch's context-token estimate under `pipeline.max_batch_context_tokens` — `test-implementer-common.py` is a 5400+ line file, and combining it with batch 1's four implementation cards pushed that batch's estimate over the cap. This batch depends on batch 1 because it exercises the `git_name`/`git_email` plumbing and commit-after-write behavior batch 1 introduces.

## Cards

### Card 5: tests — corroboration write must not self-trip the dirty gate

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add three new test cases to `plugins/mill/unit_tests/test-implementer-common.py`, following this file's existing fixture/mocking conventions (a real temp git repo with `status_path`/`task_dir`/`parent_branch` wired for the dirty gate, `_run_verify_gate` mocked to fail once then corroborate against a control checkout, mirroring the existing corroboration-waiver test(s) already present in this file):
  1. Drive `finalize_from_output` through the **explicit-JSON-success** path (a batch reports `status: success` with a JSON envelope) with the corroboration-waiver firing (stored `batch_verify_baseline` present, replay failure signatures a non-empty subset of the corroborated control's signatures), `git_name`/`git_email` both supplied. Assert the resulting envelope's `status` is `"success"`, not `"stuck"` with `stuck_type: "logic"` — this is the regression test for #954's reported self-trip, not previously exercised.
  2. Drive the same corroboration-waiver path through one of the three **no-JSON-inference** call sites in `_forward_output` (e.g. by supplying sub-agent output with no parseable `status` JSON line, forcing an inferred-success branch), `git_name`/`git_email` supplied. Assert `status_path` has no uncommitted diff afterward (`git status --porcelain <status_path>` against `project_root`, run via `_subprocess_util.run`, returns empty stdout) — this is the discriminating assertion for these three call sites, since none of them reach `_in_scope_dirty_stuck`, so "success not stuck" alone would not prove `git_name`/`git_email` were actually threaded there.
  3. Repeat case 1's setup with `git_name`/`git_email` both omitted (`None`, the default). Assert the corroboration-waiver still succeeds (envelope `status: "success"`) and no commit is attempted — the safe no-op path, matching every other optional-parameter-absent behavior already tested elsewhere in this file.
- **Commit:** `test(implementer-common): cover corroboration-write commit-before-dirty-check for #954`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-implementer-common.py` directly (the file's own `if __name__ == "__main__": sys.exit(main())` entry point), covering all three new cases plus the file's full existing regression suite.
