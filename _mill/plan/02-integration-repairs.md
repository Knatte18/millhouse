# Batch: integration-repairs

```yaml
task: "millpy-implement finalize/resume fixes and the red integration suites"
batch: "integration-repairs"
number: 2
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-plan-assets.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-go-assets.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-agent-mode-commit-target.py
depends-on: [1]
```

## Prior failure

- r1 finalize: stuck verify; test-merge.py failed at the #817 cycle scenario: `expected a 10-hop cycle outcome, got {'outcome': 'resolved', 'branch': 'test/cycle-y', 'hops': ['cycle-x']}` -- the cycle fixture leaves `test/cycle-x`/`test/cycle-y` as live local branches (same cause as Card 7).

## Batch Scope

Repairs four of the five red integration suites; each is a stale test fixture or caller, not a product bug (root causes verified by running each suite).
The fifth suite is separate because its failure chain is open-ended.
`test-go-assets` and `test-agent-mode-commit-target` exercise the implementer/review machinery and so also verify Batch 1's code.
Batch-local decision: no product code is changed here.

## Cards

### Card 5: test-plan-assets supplies the YAML tokens

- **Context:**
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/templates/plan-batch.md`
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-plan-assets.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** The overview and batch templates now contain `<TASK_TITLE_YAML>` (both) and `<BATCH_NAME_YAML>` (batch).
  In `test_overview_template_renders` add `"TASK_TITLE_YAML": quote_scalar("Demo task")` to the token dict; in `test_batch_template_renders` add `"TASK_TITLE_YAML"` and `"BATCH_NAME_YAML": quote_scalar("foundation")`.
  Import `quote_scalar` from `_yaml_writer` next to the file's existing `import _render` block (the scripts dir is already on `sys.path`).
  Adjust the yaml-substitution assertions only if the quoted form changes their expected text (for example the `slug:` or `batch:` lines); the assertions must keep proving the tokens were substituted.
  Scan the rest of the file for any other `_render.render` calls against these templates and update them the same way.
- **Commit:** `test(plan-assets): supply the *_YAML tokens the plan templates now require`

### Card 6: test-go-assets passes git_root to the review runs

- **Context:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-go-assets.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `_review_code.run` in `_review_code.py` now has a required keyword-only `git_root: Path`.
  In `test_review_code_end_to_end`, pass `git_root=` to the `_review_code.run(...)` call, using the fixture's project root (the test builds a self-contained fixture; the value must be a real directory the run can resolve, so use the same path passed as `project_root` unless the run needs a git repository, in which case initialise one in the scratch fixture).
  Check every other call in the file to the review-run entry points (grep for `.run(`) for the same signature drift and fix them the same way.
  `millpy-review-code.py` shows the production calling convention.
- **Commit:** `test(go-assets): pass git_root to _review_code.run`

### Card 7: test-merge deletes the local branches of torn-down parents

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Since #879, `check_liveness` in `_parent_branch.py` treats a local `refs/heads/<branch>` as live, so the two-hop chain scenario resolves at `test/task-c` instead of `release/1.0` because the fixture leaves `test/task-c` as a local branch.
  In the "two chained dead-parent hops" block, after creating the `archive/task-c` tag and checking out `main`, run `git -C <repo_dead> branch -D test/task-c` via the file's `_run` helper; add a comment that this mirrors what mill-cleanup does to a torn-down parent.
  Deleting `test/task-b` after its `archive/task-b` tag is optional, since the walk never checks the start branch's liveness.
  Review the earlier dead-parent sub-scenarios for the same local-branch assumption and fix only those that fail.
  Do not change `_parent_branch.py`.
- **Commit:** `test(merge): delete local branches of torn-down parents in the chain-walk fixture`

### Card 8: test-agent-mode-commit-target simulates a real content commit

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-agent-mode-commit-target.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `_forward_output` in `_implementer_common.py` correctly returns stuck/logic "no content commit" when only the `mill-go: start batch` commit exists after `start_sha`; the test's premise (a housekeeping commit only) is stale.
  After the simulated prepare commit and the HEAD-advanced assertion, add a genuine implementer content commit on the task branch (write a file such as `impl-output.txt` in the task worktree, `git add`, commit with a message that does not start with `mill-go: start batch`), then call `_forward_output` with `start_sha=initial_sha` as today.
  Refresh the assertions so the recorded `commit_sha` is compared with the task worktree HEAD after the content commit, and keep the assertion that the recorded SHA is not an ancestor of the hub's `main`.
  `_forward_output` also emits a `scope_violations` list for untracked scratch files; the test must not assert its absence.
- **Commit:** `test(agent-mode-commit-target): add a content commit so the no-content-commit gate passes`

### Card 9: test-merge cycle fixture deletes the local cycle branches

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** The "#817 cycle" scenario leaves `test/cycle-x` and `test/cycle-y` as local branches, which `check_liveness` treats as live, so the walk resolves instead of hitting the 10-hop cap.
  After both `archive/cycle-*` tags exist and before calling `resolve_dead_parent`, check out `main` and delete both local branches with `git branch -D` (same rationale as Card 7).
  Run the whole `test-merge.py` and fix any further scenario that fails for the same local-branch reason; do not change `_parent_branch.py`.
  Run the full batch `verify:` chain as one command and confirm every suite exits 0.
- **Commit:** `test(merge): delete local cycle branches so the 10-hop cap scenario is reachable`

## Batch Tests

`verify:` chains the four suites this batch edits, each run singly with the isolated `PYTHONPATH=` prefix; they are integration tests, not part of the unit `run-all.py`.
No unbounded `run-all.py` is used.
