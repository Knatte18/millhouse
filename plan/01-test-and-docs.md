# Batch: test-and-docs

```yaml
task: 2 — Enforce uv run in .millhouse shortcut wrappers
batch: test-and-docs
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

All three changes are independent and can be applied in any order within one Sonnet session. Card 1 closes the unit-test gap in `test-shortcut-wrapper.py`. Card 2 adds a Phase 4.7 block to the integration test so the cleanup behavior is exercised end-to-end (seed `.py` dummies → invoke `write_all` → assert PS1 present / `.py` absent). Card 3 adds one upgrade-path sentence to mill-setup SKILL.md Phase 4.7. No external interface is produced for other batches — this batch completes the task.

## Cards

### Card 1: Unit test — write_all deletes legacy .py wrappers

- **Reads:**
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
  - `plugins/mill/scripts/_shortcuts.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add one new test block inside `main()` in `test-shortcut-wrapper.py`, after the existing "only stale wrapper is rewritten" block. The new block must: (a) create a fresh `tempfile.TemporaryDirectory`, (b) write dummy content to `mill_dir / f"{script}.py"` for every entry in `SHORTCUT_SCRIPTS`, (c) call `write_all(mill_dir)`, (d) assert every `mill_dir / f"{script}.py"` no longer exists (FAIL + increment `errors` if any remain), (e) assert every `mill_dir / f"{script}.ps1"` exists (FAIL + increment `errors` if any are missing), (f) print `PASS: write_all deletes all N legacy .py wrappers` when both loops produce no errors. Keep the `errors` variable cumulative with the rest of `main()` — do not reset it.
- **Commit:** `test(shortcuts): add unit test for legacy .py wrapper cleanup`

### Card 2: Integration test — Phase 4.7 block in test-bootstrap.ps1

- **Reads:**
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
  - `plugins/mill/scripts/_shortcuts.py`
- **Modifies:**
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Insert a new numbered section into `test-bootstrap.ps1` immediately after the existing Phase 6a block (sidebar regen, lines ~100–104) and before the mill-add section (section 3). The new section must:
  (a) Declare `$shortcutScripts` as a PowerShell array of all 13 stem names from `SHORTCUT_SCRIPTS` (`millpy-add`, `millpy-list`, `millpy-status`, `millpy-inspect`, `millpy-spawn`, `millpy-claim`, `millpy-cleanup`, `millpy-abandon`, `millpy-color`, `millpy-terminal`, `millpy-vscode`, `millpy-worktree`, `millpy-fetch-issues`).
  (b) Write a dummy `.py` file for each stem into `$hub/.millhouse/` using `Set-Content ... -Encoding utf8` (BOM does not matter — files are deleted by `write_all`).
  (c) Call `uv run --project $millRoot python -c "from pathlib import Path; import _shortcuts; _shortcuts.write_all(Path(r'$hub/.millhouse').resolve())"`, piping to `Out-Null`. Use the same pattern (no inline PYTHONPATH) as Phase 4 and Phase 6a already in the file.
  (d) For each stem in `$shortcutScripts`, throw with a descriptive message if `$hub/.millhouse/<stem>.ps1` does not exist or if `$hub/.millhouse/<stem>.py` still exists. Use `throw` (not `Write-Host`) to match the existing assertion style; the outer `catch` block will surface it as `FAIL: <message>`.
  Number this section consistently with the existing section comments (the existing section 2 comment ends at line ~104; this becomes section 2.5 or is appended to section 2 — follow the surrounding comment style exactly).
- **Commit:** `test(bootstrap): add Phase 4.7 shortcut-wrapper assertions`

### Card 3: SKILL.md — upgrade note in Phase 4.7

- **Reads:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-setup/SKILL.md`, locate the Phase 4.7 section. Find the existing `**Note:**` paragraph (currently: "After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` to refresh PYTHONPATH and the PS1 wrappers to the new version."). Append a second sentence to that note (same paragraph, no new heading): "If upgrading from a pre-PS1 hub (one where `.millhouse/` still contains `.py` wrappers), re-run `/mill-setup` — Phase 4.7 is idempotent and will replace the `.py` wrappers with `.ps1` wrappers in a single pass, and Phase 8 will verify their absence." Do not restructure the paragraph or add new headings.
- **Commit:** `docs(mill-setup): note upgrade path for pre-PS1 hubs`

## Batch Tests

The verify command `python plugins/mill/unit_tests/run-all.py` runs every `test-*.py` in `plugins/mill/unit_tests/`, including the updated `test-shortcut-wrapper.py`. The new Card 1 test case must pass before the batch is marked complete.

Card 2 (integration test) is not covered by the unit-suite verify command — `test-bootstrap.ps1` requires a developer environment with PowerShell and git. The implementer should run `pwsh plugins/mill/integration_tests/test-bootstrap.ps1` manually from the repo root to confirm the new Phase 4.7 block works before committing.

Card 3 is a prose change with no automated test surface.
