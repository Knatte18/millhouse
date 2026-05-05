# Batch: unit-and-docs

```yaml
task: 2 — Enforce uv run in .millhouse shortcut wrappers
batch: unit-and-docs
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Two independent changes runnable in any order. Card 1 closes the unit-test gap in `test-shortcut-wrapper.py` by adding a case that verifies `write_all()` deletes legacy `.py` wrappers. Card 2 adds one upgrade-path sentence to mill-setup SKILL.md Phase 4.7. No external interface is produced — the integration-test batch that follows does not depend on either of these files.

## Cards

### Card 1: Unit test — write_all deletes legacy .py wrappers

- **Reads:**
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
  - `plugins/mill/scripts/_shortcuts.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add one new test block inside `main()` in `test-shortcut-wrapper.py`, after the existing "only stale wrapper is rewritten" block and before the final error-count check. The new block must: (a) create a fresh `tempfile.TemporaryDirectory`, (b) write dummy content to `mill_dir / f"{script}.py"` for every entry in `SHORTCUT_SCRIPTS`, (c) call `write_all(mill_dir)`, (d) assert every `mill_dir / f"{script}.py"` no longer exists — FAIL + increment the shared `errors` counter if any remain, (e) assert every `mill_dir / f"{script}.ps1"` exists — FAIL + increment `errors` if any are missing, (f) print `PASS: write_all deletes all N legacy .py wrappers` when both assertion loops produce zero errors (use `len(SHORTCUT_SCRIPTS)` for N). The `errors` variable is cumulative with the rest of `main()` — do not reset it.
- **Commit:** `test(shortcuts): add unit test for legacy .py wrapper cleanup`

### Card 2: SKILL.md — upgrade note in Phase 4.7

- **Reads:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-setup/SKILL.md`, locate the Phase 4.7 section. Find the existing `**Note:**` paragraph (currently: "After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` to refresh PYTHONPATH and the PS1 wrappers to the new version."). Append a second sentence to that note (same paragraph, no new heading): "If upgrading from a pre-PS1 hub (one where `.millhouse/` still contains `.py` wrappers), re-run `/mill-setup` — Phase 4.7 is idempotent and will replace the `.py` wrappers with `.ps1` wrappers in a single pass, and Phase 8 will verify their absence." Do not restructure the paragraph or add new headings.
- **Commit:** `docs(mill-setup): note upgrade path for pre-PS1 hubs`

## Batch Tests

The verify command `python plugins/mill/unit_tests/run-all.py` runs every `test-*.py` in `plugins/mill/unit_tests/`, including the updated `test-shortcut-wrapper.py`. Card 1's new test case must pass before this batch is marked complete. Card 2 is a prose change with no automated test surface.
