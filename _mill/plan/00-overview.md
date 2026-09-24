# Plan: status.md: rename parent to parent_branch, add parent_thread

```yaml
task: 'status.md: rename parent to parent_branch, add parent_thread'
slug: status-parent-fields
approved: true
started: 20260924-101441
parent: main
root: ""
verify: null
discussion_sha: d9bcc2b2f6f098213137e4a1998dc7ddce2901be
```

## Batch Index

```yaml
batches:
  - number: 1
    name: status-core
    file: 01-status-core.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py test-parent-branch.py test-cleanup.py
  - number: 2
    name: spawn-parent-thread
    file: 02-spawn-parent-thread.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-spawn-core.py test-millpy-spawn.py
  - number: 3
    name: templates-skills-fixtures
    file: 03-templates-skills-fixtures.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-abandon.py test-agent-mode-dispatch.py test-millpy-fix.py test-millpy-implement.py test-millpy-merge-in-subagent.py test-cleanup.py
```

## Shared Decisions

### Decision: legacy-parent-fallback-is-permanent

- **Decision:** every reader of the parent branch (`_status.read_parent_branch`, `_parent_branch._parse_parent_from_yaml_text`, the baseline-row anchor lookup, `_status.set_parent_branch`) accepts `parent_branch:` first and falls back to the legacy `parent:` key.
  `parent_branch:` wins when both exist; `parent:` is consulted only when `parent_branch:` is absent or empty.
  No removal date, no migration script.
- **Rationale:** `resolve_dead_parent` reads archived status.md from `archive/<slug>` tags, which can never be migrated; in-flight worktrees (this task's own `_mill/status.md` included) still carry `parent:`.
- **Applies to:** all batches

### Decision: parent-thread-is-write-only

- **Decision:** `parent_thread:` is written by `millpy-spawn --parent` only.
  No reader helper, no skill reads it, no caller passes `--parent`, and `millpy-claim.py` gets no flag.
- **Rationale:** the consumer lands in the follow-up task `parent-thread-escalation`; YAGNI.
- **Applies to:** all batches

### Decision: fixture-migration-policy

- **Decision:** test fixtures that assert rendered output or error text move to `parent_branch:`.
  Hand-written status.md fixtures in unrelated tests move to `parent_branch:` too, except the fixtures that deliberately exercise the legacy path: `integration_tests/test-merge.py`'s nested-merge child status (`parent: parent-feature`), its foreign-task and parent-side `other-task` status fixtures, and its archived-parent fixtures read by `resolve_dead_parent` (`Parent task`, `Legacy task`).
  Those keep `parent:` so at least one merge path and the archive chain-walk keep proving the fallback.
- **Rationale:** the discussion prefers moving fixtures to the new key except where a test exercises the legacy fallback.
- **Applies to:** templates-skills-fixtures, status-core

### Decision: integration-tests-excluded-from-verify

- **Decision:** batch `verify:` commands run unit tests only.
  Integration-test files edited in this plan (`test-spawn.py`, `test-plan-assets.py`, `test-merge.py`, `test-go-assets.py`, `test-agent-mode-commit-target.py`, `test-baseline-waiver.py`) get their string edits but are not run by `verify:`.
- **Rationale:** at plan time on the worktree tip, `test-spawn.py` (wiki-path fixture), `test-plan-assets.py` (`TASK_TITLE_YAML` unresolved), `test-merge.py` (two-hop chain-walk assertion), `test-go-assets.py` (`run()` missing `git_root`) and `test-agent-mode-commit-target.py` (status `stuck`) already fail for reasons unrelated to this task; gating on them would block every batch.
  `test-baseline-waiver.py` passes but needs real git; its edit is a one-line fixture swap covered by the unit tests of the anchor lookup.
- **Applies to:** all batches

### Decision: done-gate-recommendation

- **Decision:** recommendation for the operator: set `pipeline.done_gate` to `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` (the full unit suite).
  The currently effective value is `null`.
  Not applied: mill-go gates on the effective config value, not this Decision.
- **Rationale:** batch verifies are scoped; skills and fixtures in other unit tests read status.md too.
  No lint command is recommended: `uvx ruff check .` exits non-zero on the current worktree tip (pre-existing repo-wide lint debt unrelated to this task).
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/integration_tests/test-agent-mode-commit-target.py`
- `plugins/mill/integration_tests/test-baseline-waiver.py`
- `plugins/mill/integration_tests/test-go-assets.py`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/integration_tests/test-plan-assets.py`
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/scripts/_parent_branch.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/discussion.md`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/templates/status-discussing.md`
- `plugins/mill/unit_tests/test-abandon.py`
- `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-parent-branch.py`
- `plugins/mill/unit_tests/test-spawn-core.py`
- `plugins/mill/unit_tests/test-status.py`
