# Batch: baseline-integration-test

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: baseline-integration-test
number: 6
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-verify-baseline.py
depends-on: [3]
```

## Batch Scope

`_verify_baseline.compute_baseline` (batch 3) inherently exercises real `git worktree add`/`remove`, real junction creation, and real subprocess verify commands — none of which unit tests may use per CLAUDE.md's repo-layout convention ("`unit_tests/` — in-memory/tempfile fixtures; no real git/LLM. `integration_tests/` — invokes real git and optionally real claude; uses `.scratch/` for fixtures."). This batch adds the dedicated real-git coverage `_mill/discussion.md`'s Testing section calls for.

## Cards

### Card 13: integration test for compute_baseline

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/integration_tests/test-merge.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-verify-baseline.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create a new integration test following `test-merge.py`'s structural conventions (module docstring explaining the flow under test, real git fixtures built under a `.scratch/`-rooted temp hub+task-branch pair, `sys.path.insert` + `import _xxx` for the scripts under test, a `_run(cmd, *, cwd, check=True)` subprocess helper, exit 0 on PASS / 1 on any failure, scratch preserved on failure for inspection). Build a minimal real-git fixture: a bare "remote", a hub clone with an initial commit, and a task-branch checkout that plays the role of `project_root`/`git_root` for `_verify_baseline.compute_baseline`. Cover these cases end-to-end against the real function (no mocking of `_worktree`/`_junction`/subprocess — that is the whole point of this being an integration test rather than a unit test extension of `test-implementer-common.py`):

  1. **Clean baseline:** parent branch's own trivial verify command (e.g. `PYTHONPATH= python -c "import sys; sys.exit(0)"`) passes on the first transient-worktree run — assert `compute_baseline` returns `"clean"` and the transient worktree directory under `.scratch/` no longer exists afterward (cleanup ran).
  2. **Confirmed pre-existing failure:** a verify command that always fails (e.g. `PYTHONPATH= python -c "import sys; sys.exit(1)"`) — assert `compute_baseline` returns `"pre-existing-failures"` only after both the transient-worktree retry AND the task-worktree control run have been exercised; assert the transient worktree is cleaned up.
  3. **Flaky-then-passes (retry corroboration):** a verify command that fails on its first invocation and passes on every subsequent one within the same process (e.g. a script that writes a marker file on first run and checks for it on the second) — assert `compute_baseline` returns `"clean"` (the retry caught the flake) — assert the command was invoked more than once.
  4. **Path-sensitive deterministic failure (control-run corroboration):** a verify command that fails specifically when run from the transient worktree's path but passes when run from the task worktree's path (e.g. a script asserting `Path.cwd().name == "<task-worktree-dirname>"`) — assert `compute_baseline` returns `"clean"` (the task-worktree control run passing overrides the transient-worktree failures) rather than `"pre-existing-failures"`.
  5. **Dependency-junction reuse:** create a `.venv`-or-`node_modules`-shaped marker directory (a fixture directory with a sentinel file inside, standing in for a real dependency dir) at the task worktree's top level before calling `compute_baseline` with a verify command that asserts the same sentinel file is readable from its own cwd — assert this passes (proving the junction was created into the transient worktree) and that the marker directory itself (in the task worktree) still exists and is untouched afterward (junction removal on cleanup did not delete the real target through the junction — the exact CLAUDE.md junction-strip-before-remove hazard `_mill/discussion.md`'s Constraints section calls out).
  6. **Cleanup on exception:** force `compute_baseline` to raise partway through (e.g. pass a verify command referencing a genuinely missing binary) and assert the transient worktree is still cleaned up (no orphaned `.scratch/verify-baseline-*` directory left behind) even though the function raised.

  Follow `test-merge.py`'s "exits 0 on PASS, 1 on any failure; scratch is preserved on failure for inspection" contract exactly.
- **Commit:** `test(_verify_baseline): add real-git integration coverage for compute_baseline`

## Batch Tests

`verify:` runs this new integration test directly. It requires real git and a writable `.scratch/`; no LLM calls are involved (mirrors `test-merge.py`'s scope, not `test-claude-psmux.py`'s).
