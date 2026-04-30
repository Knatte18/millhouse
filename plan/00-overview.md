# Plan: 18 — par-E — Migrate Python invocation to `uv run`

```yaml
task: 18 — par-E — Migrate Python invocation to `uv run`
slug: migrate-to-uv
approved: false
started: 20260430-175223
parent: main
root: ""
verify: uv run --project plugins/mill plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: uv run --project plugins/mill python -c "import yaml; print('ok')"
  - name: path-fix
    file: 02-path-fix.md
    depends-on: [foundation]
    verify: uv run --project plugins/mill plugins/mill/scripts/millpy-vscode.py --help
  - name: mill-setup-skill
    file: 03-mill-setup-skill.md
    depends-on: [foundation]
    verify: null
  - name: skills-sweep
    file: 04-skills-sweep.md
    depends-on: [foundation]
    verify: null
  - name: tests-and-docs
    file: 05-tests-and-docs.md
    depends-on: [foundation, path-fix, mill-setup-skill, skills-sweep]
    verify: uv run --project plugins/mill plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: invocation-shape-uv-run

- **Decision:** All Python script invocations use `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]`. Inline `python -c` becomes `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`. Exception: mill-setup SKILL.md uses inline `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix because it bootstraps the global env var (see Decision: bootstrap-pattern below).
- **Rationale:** uv handles venv + dependency management; PYTHONPATH is set globally as a Windows user env var by mill-setup Phase 4.7 so all subsequent CC sessions inherit it automatically. No per-session export needed. See discussion.md § cc-call-shape.
- **Applies to:** all batches

### Decision: bootstrap-pattern

- **Decision:** mill-setup SKILL.md is the only skill that uses inline `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."` for its `python -c` snippets. All other skills omit the inline prefix.
- **Rationale:** mill-setup *creates* the global PYTHONPATH env var; that var does not exist in the current process (nor in subprocesses spawned within the same mill-setup session) until a new shell is opened. Bootstrap chicken-and-egg. See discussion.md § Bootstrap note.
- **Applies to:** mill-setup-skill

### Decision: claude-plugin-root-paths

- **Decision:** All SKILL.md script paths use `${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py`. Repo-relative paths (`plugins/mill/scripts/millpy-X.py`) are forbidden in SKILL.md.
- **Rationale:** Skills run against the installed plugin cache (`~/.claude/plugins/cache/millhouse/mill/<version>/`), not the source checkout. Repo-relative paths break in external repos that use mill as a plugin. CLAUDE.md constraint.
- **Applies to:** mill-setup-skill, skills-sweep

### Decision: ps1-wrapper-template

- **Decision:** The shortcut wrapper template is a PS1 file (`shortcut-wrapper.ps1`) that uses lexicographic-sort to find the latest plugin version and invokes `uv run --project $latest "$latest\scripts\<SCRIPT>.py" @args`. No PYTHONPATH set in the wrapper (global env var covers it).
- **Rationale:** Wrappers are for human terminal use only. CC never invokes them. Lexicographic-sort matches the existing `.py` wrapper convention (pre-existing limitation: 0.9.0 sorts after 0.10.0; not fixed here). See discussion.md § ps1-wrapper-design.
- **Applies to:** foundation

### Decision: cmd-exe-path-pattern

- **Decision:** External program lookups via `shutil.which("<tool>")` are replaced with `["cmd", "/c", "<tool>", ...]` invocation pattern on Windows. Applies to `code.cmd`/`code` (millpy-vscode.py), `claude` (millpy-terminal.py and _llm_claude.py).
- **Rationale:** WindowsApps PATH (`%LOCALAPPDATA%\Microsoft\WindowsApps`) is omitted from subprocess inheritance; cmd.exe always has the full interactive PATH. millpy-vscode.py already has a partial fix; consistent application across all three. See discussion.md § debugpy-path.
- **Applies to:** path-fix

### Decision: helper-signature-audit-against-source

- **Decision:** Every helper-call example in SKILL.md is checked against the actual function signature in `plugins/mill/scripts/_*.py`. Known wrong patterns: `_config.load(mill_dir)` (real: `_config.load_config(wiki_path, git_root)`); `_wiki.write_commit_push(wiki_path, msg)` (real: 3-arg `wiki_path, relative_paths, commit_msg`); `python -m millpy.entrypoints.regenerate_sidebar` (no such module — replace with `_sidebar.regenerate(...)` via `python -c`).
- **Rationale:** Issue #70 — TypeErrors observed in live mill-go runs. The uv sweep touches every SKILL.md, so the audit cost is marginal.
- **Applies to:** mill-setup-skill, skills-sweep

### Decision: pyproject-location

- **Decision:** `plugins/mill/pyproject.toml` (plugin root, above `scripts/`).
- **Rationale:** Covers scripts + tests under one project; `uv run --project "${CLAUDE_PLUGIN_ROOT}"` resolves cleanly. See discussion.md § pyproject-location.
- **Applies to:** foundation, path-fix, tests-and-docs

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/SCRIPTS.md`
- `plugins/mill/integration_tests/test-abandon.py`
- `plugins/mill/integration_tests/test-bootstrap.ps1`
- `plugins/mill/integration_tests/test-cleanup.py`
- `plugins/mill/integration_tests/test-go-assets.py`
- `plugins/mill/integration_tests/test-inspect.py`
- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/integration_tests/test-plan-assets.py`
- `plugins/mill/integration_tests/test-review-code.py`
- `plugins/mill/integration_tests/test-review-discussion.py`
- `plugins/mill/integration_tests/test-review-plan.py`
- `plugins/mill/integration_tests/test-spawn.py`
- `plugins/mill/integration_tests/test-status.py`
- `plugins/mill/integration_tests/test-worktree-sibling-resolution.py`
- `plugins/mill/pyproject.toml`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_shortcuts.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-abandon/SKILL.md`
- `plugins/mill/skills/mill-add/SKILL.md`
- `plugins/mill/skills/mill-claim/SKILL.md`
- `plugins/mill/skills/mill-cleanup/SKILL.md`
- `plugins/mill/skills/mill-color/SKILL.md`
- `plugins/mill/skills/mill-fetch-issues/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-groom/SKILL.md`
- `plugins/mill/skills/mill-inspect/SKILL.md`
- `plugins/mill/skills/mill-list/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-resume/SKILL.md`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/skills/mill-skills-from-scripts/SKILL.md`
- `plugins/mill/skills/mill-skills-index/SKILL.md`
- `plugins/mill/skills/mill-spawn/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/mill-status/SKILL.md`
- `plugins/mill/skills/mill-terminal/SKILL.md`
- `plugins/mill/skills/mill-vscode/SKILL.md`
- `plugins/mill/skills/mill-worktree/SKILL.md`
- `plugins/mill/templates/shortcut-wrapper.ps1`
