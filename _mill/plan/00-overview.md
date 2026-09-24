# Plan: Prefix session names with repo short name; add MH:orch session

```yaml
task: Prefix session names with repo short name; add MH:orch session
slug: session-name-short-prefix
approved: true
started: 20260924-090947
parent: main
root: ""
verify: null
discussion_sha: 23cb2c534ff145008cc519a9ac37c15328a0ea91
skip_checks: ["wiki-config-mutation", "verify-full-suite"]
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: core-helpers
    file: 01-core-helpers.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-vscode-tasks.py test-vscode-keybindings.py test-paths-short-name.py test-setup-short-name.py
  - number: 2
    name: session-name-callers
    file: 02-session-name-callers.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-spawn.py test-millpy-session-tasks.py test-millpy-terminal.py
  - number: 3
    name: docs-and-setup
    file: 03-docs-and-setup.md
    depends-on: [1, 2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: session_prefix is the single name-assembly and lower-casing site

- **Decision:** every caller that puts a short name into a session name builds the prefix with `_vscode_tasks.session_prefix(short, slug=None)`; `render_tasks`/`write_tasks`/`build_command` take the finished prefix and never change case. `repo.short_name` in config and the VS Code window title stay as configured (`MH`).
- **Rationale:** discussion "Name composition and lower-casing"; one place covers tasks.json and the phase-less terminal session.
- **Applies to:** all batches

### Decision: fallback short name comes from the main worktree

- **Decision:** `millpy-spawn`, `millpy-session-tasks` and `millpy-terminal` pass `resolve_main_worktree_root(git_root).name` to `resolve_short_name`; `millpy-color`, `millpy-claim` and `_vscode` keep their current argument.
- **Rationale:** discussion "Where the prefix is built"; on a task worktree `git_root.name` is the slug.
- **Applies to:** session-name-callers

### Decision: no-prompt phases are marked by `_NO_PROMPT_PHASES`

- **Decision:** `build_command` omits the trailing prompt for phases in `_NO_PROMPT_PHASES = frozenset({"orch"})`; `_prompt` is unchanged.
- **Rationale:** the discussion left the marker choice to the plan; a set keeps `build_command`'s signature unchanged and `_prompt` single-purpose.
- **Applies to:** core-helpers

### Decision: new predicate and setup tests go in new test files

- **Decision:** `short_name_is_derived` tests live in a new `test-paths-short-name.py` and `set_repo_short_name` tests in a new `test-setup-short-name.py`, rather than in the existing large `test-paths.py` / `test-setup-hub-links.py`.
- **Rationale:** keeps batch 1's context small and the tests focused; the existing suites still run in batch 3's full-suite verify.
- **Applies to:** core-helpers

### Decision: hub mill-config.yaml edit is a safe bootstrap (wiki-config-mutation skip)

- **Decision:** card 1 adds `spawn.sessions.orch` to the hub `mill-config.yaml`; the `wiki-config-mutation` check is skipped.
- **Rationale:** card 1 carries the bootstrap justification: the running cached `resolve_sessions` ignores unknown `spawn.sessions` keys and nothing else reads `spawn.sessions`, so the change is inert until the new code ships. CLAUDE.md requires the hub file and the template to stay in sync.
- **Applies to:** core-helpers

### Decision: full suite runs once, in batch 3 (verify-full-suite skip)

- **Decision:** batch 3's `verify:` is the unbounded `run-all.py`; batches 1 and 2 stay scoped.
- **Rationale:** the discussion's Testing section makes the full suite the acceptance bar, and batches 1 and 2 change helpers imported by suites outside their scoped `verify:`; batch 3 is prose-only, so its implementer/fixer rounds are few. Justification also recorded in batch 3's `## Batch Tests`.
- **Applies to:** docs-and-setup

### Decision: no done_gate lint recommendation (pre-existing ruff debt)

- **Decision:** recommend no `pipeline.done_gate` change; the effective value stays `null`.
- **Rationale:** `uvx ruff check .` at the current worktree tip exits 1 with about 2000 pre-existing findings unrelated to this task, so a lint gate would block every task on unrelated debt. The full-suite acceptance run is expressed as batch 3's `verify:` instead.
- **Applies to:** all batches

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_setup.py`
- `plugins/mill/scripts/_vscode_tasks.py`
- `plugins/mill/scripts/millpy-session-tasks.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/skills/mill-session-tasks/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/vscode-tasks-orch.json`
- `plugins/mill/templates/vscode-tasks.json`
- `plugins/mill/unit_tests/test-millpy-session-tasks.py`
- `plugins/mill/unit_tests/test-millpy-spawn.py`
- `plugins/mill/unit_tests/test-millpy-terminal.py`
- `plugins/mill/unit_tests/test-paths-short-name.py`
- `plugins/mill/unit_tests/test-setup-short-name.py`
- `plugins/mill/unit_tests/test-vscode-tasks.py`
