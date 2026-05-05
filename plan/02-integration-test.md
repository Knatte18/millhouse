# Batch: integration-test

```yaml
task: 2 — Enforce uv run in .millhouse shortcut wrappers
batch: integration-test
cards: 1
verify: pwsh plugins/mill/integration_tests/test-bootstrap.ps1
depends-on: [unit-and-docs]
```

## Batch Scope

Adds a Phase 4.7 block to `test-bootstrap.ps1` so the shortcut-wrapper write and cleanup behaviour is exercised end-to-end against a real git repo. The block seeds legacy `.py` dummy files, invokes `_shortcuts.write_all()`, then asserts PS1 wrappers are present and `.py` wrappers are absent. The batch verify runs the full integration test via `pwsh`; requires a developer environment with git and PYTHONPATH set (same prerequisite as the rest of `test-bootstrap.ps1`).

## Cards

### Card 3: Integration test — Phase 4.7 block in test-bootstrap.ps1

- **Reads:**
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
  - `plugins/mill/scripts/_shortcuts.py`
- **Modifies:**
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Insert a new numbered section into `test-bootstrap.ps1` immediately after the Phase 6a block (sidebar regen, lines ~100–104) and before the mill-add section. The new section must:

  (a) Declare `$shortcutScripts` as a PowerShell array of all 13 stem names from `SHORTCUT_SCRIPTS`: `millpy-add`, `millpy-list`, `millpy-status`, `millpy-inspect`, `millpy-spawn`, `millpy-claim`, `millpy-cleanup`, `millpy-abandon`, `millpy-color`, `millpy-terminal`, `millpy-vscode`, `millpy-worktree`, `millpy-fetch-issues`.

  (b) Write a dummy `.py` file for each stem into `$hub/.millhouse/` using `Set-Content (Join-Path $hub ".millhouse/$s.py") "# legacy" -Encoding utf8`. BOM does not matter — files are deleted by `write_all`.

  (c) Call `uv run --project $millRoot python -c "from pathlib import Path; import _shortcuts; _shortcuts.write_all(Path(r'$hub/.millhouse').resolve())"`, piping to `Out-Null`. Follow the same pattern as Phase 4 and Phase 6a already in the file — no inline PYTHONPATH prefix.

  (d) For each stem in `$shortcutScripts`, use `throw` with a descriptive message if `$hub/.millhouse/<stem>.ps1` does not exist (missing PS1 wrapper) or if `$hub/.millhouse/<stem>.py` still exists (legacy wrapper not deleted). `throw` propagates to the outer `catch` block and surfaces as `FAIL: <message>`, matching the existing assertion style.

  Use a section comment consistent with the surrounding style (e.g. `# Phase 4.7: PS1 shortcut wrappers`). Do not renumber the existing sections (3–7) — add this as a new unnumbered sub-block within section 2.

- **Commit:** `test(bootstrap): add Phase 4.7 shortcut-wrapper assertions`

## Batch Tests

The verify command `pwsh plugins/mill/integration_tests/test-bootstrap.ps1` runs the full integration test, including the new Phase 4.7 block. Requires a developer environment: git on PATH, PYTHONPATH pointing at `plugins/mill/scripts` (set by mill-setup Phase 4.7), and `pwsh` (PowerShell 7+) installed.
