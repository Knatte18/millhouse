# Plan: Replace powershell subprocess with winreg in mill-setup

```yaml
task: "Replace powershell subprocess with winreg in mill-setup"
slug: "mill-setup-winreg"
approved: true
started: "20260530-150552"
parent: "main"
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
    name: winreg-env-helper
    file: 01-winreg-env-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-winenv.py
```

## Shared Decisions

### Decision: no-powershell

- **Decision:** The replaced code path uses zero PowerShell. The new env-var
  write is a Python `winreg` call invoked through the standard inline
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
  "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."` pattern that every
  other Python phase in `mill-setup/SKILL.md` already uses.
- **Rationale:** Operator hard requirement (discussion.md `no-powershell-anywhere`).
  Also removes the ~500 ms PS5 startup tax on every `/mill-setup` run.
- **Applies to:** all batches

### Decision: ascii-only-output

- **Decision:** Every `print()` / log string in `_winenv.py` and in the new
  SKILL.md Python block uses ASCII only -- ` -- ` not an em dash, ` -> ` not a
  unicode arrow.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII (CLAUDE.md repo
  convention).
- **Applies to:** all batches

### Decision: winreg-mocked-in-tests

- **Decision:** `test-winenv.py` never touches the real registry. It patches
  `_winenv.winreg`'s functions (`CreateKeyEx`, `QueryValueEx`, `SetValueEx`,
  `CloseKey`) and the module's broadcast seam via `unittest.mock`.
- **Rationale:** Repo unit-test rule -- no real git/LLM, and here no real
  registry. `winreg` imports fine on the Windows test host, so patching its
  functions (not the module import) is sufficient and isolates the test.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_winenv.py`
- `plugins/mill/skills/mill-setup/SKILL.md`
- `plugins/mill/unit_tests/test-winenv.py`
