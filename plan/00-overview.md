# Plan: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)

```yaml
task: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)
slug: dispatch-cli-and-resume
approved: true
started: 20260505-122812
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: implement-cli
    file: 01-implement-cli.md
    depends-on: []
    verify: "uv run --project plugins/mill python -m py_compile plugins/mill/scripts/millpy-implement.py"
  - name: tests-and-skill
    file: 02-tests-and-skill.md
    depends-on: [implement-cli]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: template-path-resolution

- **Decision:** The CLI resolves intra-plugin template paths via `Path(__file__).resolve().parent.parent / "templates"`, not via `${CLAUDE_PLUGIN_ROOT}`.
- **Rationale:** `${CLAUDE_PLUGIN_ROOT}` is a shell environment variable, unavailable to Python at runtime without an explicit `os.environ` lookup. `Path(__file__)` reliably resolves to the script's location regardless of how it is invoked (`uv run`, direct `python`, importlib). The templates directory is always a sibling of `scripts/` inside the plugin, so `parent.parent / "templates"` is always correct.
- **Applies to:** implement-cli

### Decision: git-subprocess-style

- **Decision:** Git operations in the CLI use plain `subprocess.run(["git", ...], capture_output=True, text=True, cwd=project_root)`, not `_subprocess_util.run`.
- **Rationale:** `_subprocess_util.run` is the LLM-caller layer (used by `_llm_claude` for subprocess logging). CLI git operations don't need that logging overhead. `subprocess.run` with `capture_output=True` is the standard approach for short git commands.
- **Applies to:** implement-cli

### Decision: no-yaml-quoting-for-brief-fix-tokens

- **Decision:** Tokens for `implementer-brief.md` and `implementer-fix.md` do not need `quote_scalar` quoting before passing to `_render.render`.
- **Rationale:** Neither template contains a fenced yaml block with dynamic content. `implementer-brief.md`'s heading and prose sections receive `TASK_TITLE` and `BATCH_NAME` as plain text, not as yaml values. `implementer-fix.md` similarly has no yaml blocks. The `quote_scalar` requirement from mill-plan's own rendering applies only when tokens land inside fenced yaml blocks.
- **Applies to:** implement-cli

### Decision: git-error-handling

- **Decision:** If a git command (add, commit, push) fails, the CLI prints the stderr to sys.stderr and returns exit code 1 with no JSON on stdout.
- **Rationale:** A failed commit or push means status.md state is inconsistent. Proceeding to spawn the implementer in that state would leave an orphaned session with no trackable state. Exit 1 without JSON triggers the Builder's pre-launch error path.
- **Applies to:** implement-cli

## All Files Touched

- `plugins/mill/scripts/_implementer_sonnet.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/implementer-fix.md`
- `plugins/mill/unit_tests/test-millpy-implement.py`
