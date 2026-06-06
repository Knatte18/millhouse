# Batch: agent-mode-parity-test

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
batch: agent-mode-parity-test
number: 7
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-mode-dispatch.py
depends-on: [3, 4, 5, 6]
```

## Batch Scope

Locks in the core guarantee end-to-end: for the same inputs, the agent-mode
`prepare -> (sub-agent output) -> finalize` round-trip produces byte-for-byte the
same JSON envelope and the same on-disk artifacts (review files, commits) as the
`full` (subprocess) path. A unit-level parity test covers an implementer-class
and a reviewer-class CLI with captured sub-agent output fixtures (no real LLM,
no Agent tool -- the sub-agent text is a fixture file fed to `--stage finalize`).
A separate integration test asserts the discussion gotcha: in a real worktree the
finalize-stage implementer commit lands on the task branch, not the hub.

## Cards

### Card 25: Unit parity test for the prepare/finalize round-trip

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- **Deletes:** none
- **Requirements:** New `test-agent-mode-dispatch.py` asserting parity for at
  least one implementer-class CLI (`millpy-implement.py`) and one reviewer-class
  CLI (`millpy-review-discussion.py`): (1) run the CLI with `--stage prepare`,
  capture the prepare JSON, and confirm the brief file exists at
  `_mill/briefs/<role>-<scope>-r<round>.md` and contains the same rendered text
  the `full` path would render; (2) take a captured sub-agent output fixture
  (the same text shape `claude -p`/`full` produced in the existing per-CLI tests),
  feed it to `--stage finalize --agent-output <fixture>`, and assert the printed
  JSON envelope equals the envelope the `full` path produces for the same input,
  and that the review file written by finalize (for the reviewer) matches the
  `full`-path review file. Guard `_implementer_claude.run` and
  `_reviewer_single.run` so the test fails if `prepare` or `finalize` ever spawns
  the LLM. Reuse the fixture/setup helpers in the two referenced existing test
  files.
- **Commit:** `test(agent-mode): parity test for prepare/finalize round-trip`

### Card 26: Integration test -- implementer commit lands on the task branch

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-agent-mode-commit-target.py`
- **Deletes:** none
- **Requirements:** New integration test (real git, no LLM) under
  `integration_tests/`, following the existing integration-test fixture pattern
  (real git repo in `.scratch/`). Build a task worktree on a feature branch, run
  `millpy-implement.py --stage prepare <batch>` and assert its atomic pre-commit
  landed on the feature branch (HEAD advanced on that branch, not on main/hub),
  then feed a canned implementer success-output fixture to
  `--stage finalize --agent-output <fixture>` and assert the recorded
  `commit_sha`/state is on the same feature branch. This is the mechanical proxy
  for the discussion gotcha "the implementer's git commits land on the task branch
  in the correct worktree" -- the actual Agent-tool sub-agent inherits the
  orchestrator cwd at runtime, which this test simulates by running the stages in
  the worktree cwd. Document at the top of the file that it is run via the
  integration-test harness, not the per-batch unit `verify:`.
- **Commit:** `test(agent-mode): integration test for commit-on-task-branch`

## Batch Tests

`verify:` runs the unit parity test `test-agent-mode-dispatch.py` (envelope +
artifact parity between agent-mode and full-mode, LLM guarded off). The
integration test `test-agent-mode-commit-target.py` uses real git and is run via
the integration-test harness (`plugins/mill/integration_tests/`), not the
per-batch unit `verify:` -- it asserts the commit-target guarantee from the
discussion's gotcha. The runtime Agent-tool path itself (the SKILL spawning a real
sub-agent) remains a manual smoke item per dispatch mode, as noted in the
discussion's Testing section.
