# Batch: _gitignore API simplification

```yaml
task: Restructure hub junction layout
batch: _gitignore API simplification
number: 1
cards: 2
verify: python plugins/mill/unit_tests/test-gitignore-phase.py
depends-on: []
```

## Batch Scope

Drop `ANCHORED_ENTRIES`, remove `upsert_split`, and replace with a single-path `upsert(gitignore_path, glob_entries)` function. Update `GLOB_ENTRIES` to cover the new junction names. Update the test file to match. This is a pure refactor with no callers outside the test file and the mill-setup SKILL.md (which is updated in batch 4).

## Cards

### Card 1: `_gitignore.py` — new API

- **Context:**
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Edits:**
  - `plugins/mill/scripts/_gitignore.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Replace `GLOB_ENTRIES` with `["**/.millhouse/", "**/.scratch/", "**/.portals/", "**/.wiki/", "**/.active/"]`. Remove `**/wts/`, `**/portals/`, `**/plugins/*/uv.lock`. Justification for removing each: `**/wts/` and `**/portals/` were hub-layout artefacts that never belonged in the global gitignore (they would incorrectly ignore directories named `wts` or `portals` anywhere in the repo). `**/plugins/*/uv.lock` is dead coverage — plugin `uv.lock` files (e.g. `plugins/mill/uv.lock`) are tracked by git in the millhouse repo; the ignore entry is a no-op for tracked files. The implementer should verify via `git ls-files plugins/mill/uv.lock` before removing to confirm it is tracked.
  2. Delete the `ANCHORED_ENTRIES` constant entirely.
  3. Change `render_block(glob_entries, anchored_entries)` to `render_block(glob_entries: list[str]) -> str`. Remove the anchored-entries normalisation loop (the `for entry in anchored_entries:` block). Remove the `anchored_entries` parameter from the module docstring's API description.
  4. Add `upsert(gitignore_path: Path, glob_entries: list[str]) -> bool`: renders the block via `render_block(glob_entries)`, calls `_upsert_single(gitignore_path, block_text)`, and returns the bool. Add it to the module docstring's Public API section.
  5. Delete the `upsert_split` function and its docstring entirely.
  6. Update the module-level docstring: replace `render_block(glob_entries, anchored_entries)` and `upsert_split(...)` entries with the new `render_block(glob_entries)` and `upsert(gitignore_path, glob_entries)` entries. Remove the `ANCHORED_ENTRIES` entry from Constants.
- **Commit:** `refactor(_gitignore): drop anchored-entries, replace upsert_split with upsert`

### Card 2: `test-gitignore-phase.py` — updated tests

- **Context:**
  - `plugins/mill/scripts/_gitignore.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Replace imports: remove `ANCHORED_ENTRIES` and `upsert_split`; add `upsert`.
  2. Add a test that importing `ANCHORED_ENTRIES` from `_gitignore` raises `ImportError`: `try: from _gitignore import ANCHORED_ENTRIES; raise AssertionError("should have raised ImportError") except ImportError: print("PASS: ANCHORED_ENTRIES no longer exported")`.
  3. Replace all `upsert_split`-based tests with `upsert`-based tests:
     - First call on empty `.gitignore` returns `True` (wrote new block).
     - Second call on the same file returns `False` (idempotent — already up to date).
     - Call on a non-empty `.gitignore` (with existing content above the block) appends the block below the existing content (preserves existing lines).
     - `START` marker present but `END` absent raises `ValueError` (corrupt marker).
  4. Keep the `render_block` test but update the call: `render_block(GLOB_ENTRIES)` (no second arg). Assert all five `GLOB_ENTRIES` entries are present between `START` and `END`. Assert `**/wts/` and `**/portals/` and `**/plugins/*/uv.lock` are NOT in `GLOB_ENTRIES`.
  5. Add a test that checks `GLOB_ENTRIES` contains `**/.portals/`, `**/.wiki/`, and `**/.active/`.
  6. Remove the two-path (`upsert_split` diff-path), anchored-entry normalisation, and split idempotency tests — they are no longer relevant.
  7. Update the `main()` runner's `tests` list to only include the new/updated test functions.
- **Commit:** `test(_gitignore): rewrite tests for upsert API; verify new GLOB_ENTRIES`

## Batch Tests

`python plugins/mill/unit_tests/test-gitignore-phase.py` must exit 0. All tests in the file pass.
