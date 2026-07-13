MILL_REVIEW_BEGIN
# Review: Port mill to POSIX, not just Windows — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-13
```

## Findings

### [BLOCKING] Card 6 Requirements ref a file not in Context
**Location:** Batch 2 / Card 6
**Issue:** Requirements says "resolve the venv python via the dual-existence probe from `mill-setup/SKILL.md:74`" and to reuse `$MILL_PYTHON`, but Card 6's `Context:` lists only `test-bootstrap.ps1` — the implementer cannot read `mill-setup/SKILL.md` to see the `test -f ".../.venv/bin/python" && ... || ...` idiom it is told to copy.
**Fix:** Add `plugins/mill/skills/mill-setup/SKILL.md` to Card 6's `Context:`.

### [BLOCKING] Card 6 cannot discover current script surface to adapt to
**Location:** Batch 2 / Card 6
**Issue:** The `.ps1` is materially stale vs. current mill: it drives `millpy-list.py` (no longer exists — now `millpy-status.py`), invokes via `uv run --project` rather than `$MILL_PYTHON`, and calls `_shortcuts.write_all(Path)` with one arg / asserts `.ps1` wrappers (current `write_all(mill_dir, latest_path)` writes `.cmd` and deletes `.ps1`). Card 6 says "adapt to current behavior" but its `Context:` gives no way to learn that current behavior, forcing cold-start exploration.
**Fix:** Add the current-behavior sources to Context (e.g. `plugins/mill/scripts/millpy-status.py`, `_shortcuts.py`) or scope Card 6's Requirements to name the exact renames/invocation form to use.

### [NIT] Batch 2 scope omits Phase 4.7 divergence from the port
**Location:** Batch 2 / Card 6 Requirements
**Issue:** The `.ps1` seeds a Phase 4.7 `.ps1`-wrapper step that is Windows-only and no longer applies (POSIX skips 4.7; `write_all` now writes `.cmd`). Card 6 does not tell the implementer to drop that section, only the generic "adapt" instruction.
**Fix:** State explicitly that the ported `.sh` omits the Phase 4.7 shortcut-wrapper seed/assert block (Windows-only, skipped on POSIX).

### [NIT] All-Files-Touched omits Card 6's created file
**Location:** overview `## All Files Touched`
**Issue:** The list has 6 entries but does not include `plugins/mill/integration_tests/test-bootstrap.sh` (Card 6 `Creates:`); it lists `test-bootstrap.sh` without the `integration_tests/` path prefix used elsewhere. Minor consistency gap.
**Fix:** Normalise the entry to the full repo-relative path `plugins/mill/integration_tests/test-bootstrap.sh`.

## Verdict

REQUEST_CHANGES
Card 6 Context is incomplete for the stale-`.ps1` adaptation it mandates.
MILL_REVIEW_END
