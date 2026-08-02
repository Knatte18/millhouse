# Batch: baseline-waiver-integration-test

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
batch: baseline-waiver-integration-test
number: 7
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-baseline-waiver.py
depends-on: [6]
```

## Batch Scope

Adds the real-git, end-to-end integration test `_mill/discussion.md`'s Testing section calls for: a small fixture task whose one batch's `verify:` command has a pre-existing failing test unrelated to the batch's own cards, confirming `--stage baseline` captures it and `--stage finalize` waives it while still catching a genuinely new failure. This is the only batch depending on batch 6 (needs the fully-wired `--stage baseline`/`--stage finalize` CLI behavior to exist).

## Cards

### Card 25: Integration test for per-batch baseline capture and waiver

- **Context:**
  - `plugins/mill/integration_tests/test-verify-baseline.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `_mill/status.md`
  - `_mill/plan/00-overview.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-baseline-waiver.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Following `plugins/mill/integration_tests/test-verify-baseline.py`'s real-git fixture conventions (bare "remote" + hub clone via `_run`/`git init --bare`/`git clone`, per-case linked worktrees via `git worktree add` under a `.scratch/`-rooted container, `_safe_rmtree.safe_rmtree(container, allowed_root=container, ignore_errors=True)` cleanup on success, scratch preserved with a printed path on failure, `_assert`-based assertions, exit 0 on PASS / 1 on any failure), build a minimal fixture mill task on the parent branch tip: a `_mill/status.md` with one `## Batches` entry, a `_mill/plan/00-overview.md`, and one batch file whose `verify:` frontmatter names a small Python script with one failing case (e.g. exits 1 and prints a `FAILED ...` line) that is unrelated to any code this fixture task would change. Drive it through the real CLI end-to-end as subprocess invocations (mirroring how `millpy-implement.py` is invoked in production — `PYTHONPATH=<scripts dir> <python> millpy-implement.py --stage <stage> ...`, with `PYTHONPATH` set to the scripts directory so the fixture's own worktree modules load, not any cache):
  1. Invoke `--stage baseline` against the fixture task worktree; confirm the batch's `verify_baseline_failures` field in `status.md` after the call captures the pre-existing failure's signature (non-empty list containing the expected `FAILED ...`-shaped line).
  2. Mutate the fixture's verify-command script to ALSO introduce a second, different failure (simulating an implementer-introduced regression, distinguishable from the original by its own distinct `FAILED ...`-shaped line) while keeping the original failure present, commit the mutation, then invoke `--stage finalize` with a fabricated `--agent-output` file containing `{"status": "success", "session_id": "test"}`; confirm the CLI's printed JSON reports `stuck_type: "verify"` (the new, non-baseline failure is not waived) rather than `status: "success"`.
  3. Revert the fixture's verify-command script back to producing ONLY the original pre-existing failure (no new one), commit the revert, re-invoke `--stage finalize` with a fresh `--agent-output` reporting `status: "success"`; confirm the CLI's printed JSON now reports `status: "success"` (the pre-existing-only failure set is waived per the subset-diff rule).
- **Commit:** `test(integration): cover per-batch baseline waiver end-to-end`

## Batch Tests

`verify:` runs the newly-created `plugins/mill/integration_tests/test-baseline-waiver.py` directly — this batch's entire deliverable IS that integration test, so running it directly is the correct verify scope (per integration-test convention, it is not wired into `unit_tests/run-all.py`).
