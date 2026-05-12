# Plan: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly

```yaml
task: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly
slug: ps1-startup-speedup
approved: false
started: 20260512-093109
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: benchmark
    file: 01-benchmark.md
    depends-on: []
    verify: null
  - number: 2
    name: shortcut-speedup
    file: 02-shortcut-speedup.md
    depends-on: [1]
    verify: "python plugins/mill/unit_tests/test-shortcut-wrapper.py"
  - number: 3
    name: vscode-filter-open
    file: 03-vscode-filter-open.md
    depends-on: [1]
    verify: "python plugins/mill/unit_tests/test-millpy-vscode.py"
  - number: 4
    name: mill-setup-skill
    file: 04-mill-setup-skill.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: benchmark-first-gate

- **Decision:** Batch 01 is a benchmark step. The implementer runs the `Measure-Command` harness from discussion.md § Technical context, writes results to `task/benchmark-notes.md`, and embeds the key timing numbers in the commit message of the first code-change batch (02) so the fix rationale is traceable in git history.
- **Rationale:** The task description mandates data-first. Making this an explicit DAG-root batch prevents accidental skip.
- **Applies to:** batches 01 and 02

### Decision: uv-run-active-with-profile-activation

- **Decision:** PS1 wrappers call `uv run --active "<hardcoded-script-path>" @args`. The venv is activated once at shell startup via a marker-delimited block mill-setup writes to `$PROFILE`. Both `<SCRIPT>` (for the comment) and `<SCRIPT_PATH>` (full hardcoded path) are required render tokens on every `_render.render` call.
- **Rationale:** `uv run --active` skips all project/lockfile resolution. The plugin-cache venv is shared across worktrees; hardcoding the path eliminates the `Get-ChildItem` scan. Keeping `uv run` in the path is an explicit operator preference (see discussion.md § uv-run-active-with-profile-activation).
- **Applies to:** all batches

### Decision: no-posix-changes

- **Decision:** All changes are Windows-only. `_probe_posix()` in `_vscode_processes.py` is untouched. No POSIX test changes.
- **Rationale:** Discussion out-of-scope clause.
- **Applies to:** all batches

### Decision: no-lazy-import

- **Decision:** `import _vscode_processes` stays at module level in `millpy-vscode.py`. Only the *call* to `_filter_open_worktrees` is gated on `--filter-open`.
- **Rationale:** Import cost is negligible; lazy import breaks ~10 existing `patch("mill_vscode._vscode_processes...")` mock paths. See discussion.md § filter-open-flag-default-off.
- **Applies to:** batch 03

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch, sorted
alphabetically. mill-go reads this to warn if two parallel batches
touch the same file — a sign of a misplaced dependency._

- `plugins/mill/scripts/_shortcuts.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/templates/shortcut-wrapper.ps1`
- `plugins/mill/unit_tests/test-millpy-vscode.py`
- `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- `task/benchmark-notes.md`
