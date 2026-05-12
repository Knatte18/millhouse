# Batch: setup-junction-idempotency

```yaml
task: (A) — Small infra fixes batch 7
batch: setup-junction-idempotency
number: 2
cards: 3
verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-setup-hub-links.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Delivers GitHub issue #274 — `_setup.create_hub_links` becomes idempotent on its junctions loop, mirroring the existing inode-check pattern in the hardlinks loop of the same function. The change extracts a private `_is_junction_or_symlink` helper from `_junction.remove`, adds a new public `_junction.points_to(link_path, target) -> bool` helper (with `OSError` handling for broken Windows junctions), and updates `_setup.create_hub_links` to skip-on-correct / remove-and-recreate-on-drift / refuse-on-real-directory.

Batch-local decision: when a junction exists but points to the wrong target, the fix is `_junction.remove(link_path)` followed by `_junction.create(target, link_path)`. The `_junction.remove` helper already refuses to touch a real directory (existing `ValueError` at line 191) — we re-use that safety guard without duplicating the detection logic. Drift handling appends the link path to `created_junctions` (the recreated junction counts as a created link); idempotent skip does NOT append (matches the hardlinks block's `continue` at line 137).

## Cards

### Card 4: Extract `_is_junction_or_symlink` and add `_junction.points_to`

- **Context:**
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/scripts/_junction.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Refactor `_junction.py` to extract the "is a junction or symlink" detection logic out of `remove()` into a private module-level helper, then add a new public `points_to()` function that reuses it.

  Step A — extract `_is_junction_or_symlink(link_path: Path) -> bool`. The body is taken verbatim from `remove()`'s detection block at lines 164–192 and 193–200, but returns a boolean instead of branching to a removal call:
  - If `os.path.lexists(str(link_path))` is False → return False.
  - On Windows (`os.name == "nt"`): return True iff the path is a junction (using `os.path.isjunction` on Python 3.12+, else the `0x400` reparse-point bit on `os.lstat(...).st_file_attributes`) OR `os.path.islink(str(link_path))`. Return False otherwise (regular file or directory).
  - On POSIX: return `os.path.islink(str(link_path))`.

  Place `_is_junction_or_symlink` as a module-level private function (leading underscore) immediately before `def create(...)` (currently line 85). The helper is purely detection — never raises, never mutates.

  Step B — refactor `remove()` to use `_is_junction_or_symlink`. The structure becomes:
  ```python
  if not os.path.lexists(str(link_path)):
      return
  if not _is_junction_or_symlink(link_path):
      raise ValueError(
          f"{link_path} is not a junction or symlink — refusing to remove"
      )
  if os.name == "nt":
      if os.path.islink(str(link_path)):
          os.unlink(str(link_path))
          print(f"[junction] removed symlink {link_path}", file=sys.stderr)
      else:
          os.rmdir(str(link_path))
          print(f"[junction] removed junction {link_path}", file=sys.stderr)
  else:
      os.unlink(str(link_path))
      print(f"[junction] removed symlink {link_path}", file=sys.stderr)
  ```
  The existing observable behaviour of `remove()` is preserved bit-for-bit: same outputs on every code path, same `ValueError` message, same stderr lines.

  Step C — add public `points_to(link_path: Path, target: Path) -> bool`. Place it immediately after `remove()` and BEFORE `strip_all_in_worktree`. Behaviour:
  - If `_is_junction_or_symlink(link_path)` is False → return False.
  - Otherwise: wrap BOTH `link_path.resolve()` and `target.resolve()` in a single `try/except OSError`. If either call raises `OSError`, return False (covers the broken-Windows-junction case where the junction target was deleted after creation). On success, return `link_path.resolve() == target.resolve()` (Path equality on the canonical form).

  Update the module docstring's Public API list to include `points_to(link_path, target) -> bool` between `remove` and `resolve_target`. Document the broken-junction → False semantics in the docstring of `points_to`.

  Do not change `resolve_target`, `has_slug_token`, or `strip_all_in_worktree`. Do not change any import.
- **Commit:** `refactor(junction): extract _is_junction_or_symlink; add points_to with OSError handling`

### Card 5: Make `_setup.create_hub_links` junction loop idempotent

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/scripts/_setup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Modify the junctions loop in `_setup.create_hub_links` (currently lines 91–106 in `_setup.py`) so that pre-existing junctions are handled idempotently, mirroring the hardlinks-loop pattern below it (lines 110–152).

  The new junction-handling logic per entry, replacing the unconditional `_junction.create(target, link_path)` call at line 104:

  ```python
  # Resolve target dir (existing behaviour — keep as is).
  target = Path(_junction.resolve_target(target_template, tokens))
  link_path = target_root / junction_rel

  if _junction.has_slug_token(target_template):
      target.mkdir(parents=True, exist_ok=True)

  # Idempotency: skip on correct, recreate on drift, refuse on real directory.
  # Use os.path.lexists (does NOT follow links) so a broken NTFS junction —
  # whose target was deleted, making Path.exists() return False because it
  # follows the junction to a missing target, and Path.is_symlink() return
  # False because junctions are not Python symlinks — is still recognised
  # as present and routed through the drift branch. This mirrors
  # `_junction.remove`'s own lexists-based guard at line 162. Requires
  # `import os` at the top of `_setup.py`.
  if os.path.lexists(str(link_path)):
      if _junction.points_to(link_path, target):
          # Already correct — silent skip (mirrors hardlink inode-skip at line 137).
          continue
      # Drift: junction points elsewhere, is broken, or link_path is a
      # regular file/dir. `_junction.remove` raises ValueError on a real
      # directory (existing safety guard at line 191) — propagate that
      # ValueError unchanged.
      _junction.remove(link_path)

  _junction.create(target, link_path)
  created_junctions.append(link_path)
  print(f"[setup] junction created: {link_path} -> {target}", file=sys.stderr)
  ```

  Add `import os` to the imports block at the top of `plugins/mill/scripts/_setup.py`. Current imports (line 17–23): `from __future__ import annotations`, blank, `import re`, `import sys`, `from pathlib import Path`, blank, `import _junction`, `import _wiki`. Insert `import os` between `import re` and `import sys` (alphabetical) — final order becomes `import os`, `import re`, `import sys`.

  Observable behaviour after this card:
  - Junction absent (`os.path.lexists` returns False): created as before; appended to `created_junctions`; same stderr log.
  - Junction present pointing at the correct target: silent skip, NOT appended to `created_junctions`, no stderr log (matches the hardlink `continue` at line 137 — no log on skip).
  - Junction present pointing at the WRONG target: `_junction.remove` invoked first (which emits the existing `[junction] removed junction <path>` stderr line), then `_junction.create` recreates and appends.
  - A regular file or directory at `link_path` (not a junction or symlink): `_junction.remove`'s existing `ValueError` propagates unchanged — the operator-facing error is `<link_path> is not a junction or symlink — refusing to remove`.
  - Broken junction (target deleted after creation): `os.path.lexists` returns True (the reparse point still exists on the filesystem even though its target is gone), so the outer guard FIRES — unlike `Path.exists() or Path.is_symlink()` which would both return False for a broken NTFS junction and bypass the guard entirely. Inside the guard, `points_to` returns False (the new `OSError` handling in Card 4 catches `Path.resolve()`'s failure on the broken junction). The drift branch fires — `_junction.remove` removes the broken junction (its reparse-point bit is still detectable via `_is_junction_or_symlink`, per `remove()`'s existing 0x400 check), then `_junction.create` recreates fresh against the now-existing target.

  Do not change the hardlinks loop (lines 110–152). Do not change the function signature or return shape. Do not change `_required_tokens` or the module docstring.
- **Commit:** `fix(setup): create_hub_links junctions loop idempotent on re-run`

### Card 6: Unit tests for junction idempotency

- **Context:**
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-setup-hub-links.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Extend `plugins/mill/unit_tests/test-setup-hub-links.py` with three new test functions covering the new idempotency / drift / refuse paths. The new functions are appended near the other junction-related tests (e.g. directly after `test_token_scope_filter_with_slug` in file order is fine — pick a location that keeps the junction tests grouped). All three must be registered in the `main()` function's `tests = [...]` list at the bottom of the file.

  Tests required:
  - `test_junction_idempotent_skip_on_correct_target`: use `_FULL_CFG` fixture and `SLUG` present so `.wiki` (no-slug) and `.portals` (with-slug) are both created. Call `create_hub_links(...)` once (first call: returns 2 junctions). Then call `create_hub_links(...)` a SECOND time with the same arguments. Assert: the second call returns `result["junctions"] == []` (no junctions appended on skip), does NOT raise, and the existing `.wiki` and `.portals` junctions still resolve to the same wiki / `wiki/active/<slug>/` targets (verify by writing a probe file inside each target and reading it back through the junction).
  - `test_junction_recreated_on_wrong_target`: set up two valid wiki dirs (`wiki_a/` with `config.yaml`, `wiki_b/` as a decoy). Pre-create a `.wiki` junction in `target_root` pointing at `wiki_b/` via `_junction.create(target=wiki_b, link_path=target_root / ".wiki")`. Configure `_FULL_CFG` with `WIKI_PATH = wiki_a` (the correct target). Call `create_hub_links(...)`. Assert: `.wiki` now resolves to `wiki_a` (probe file via the junction matches `wiki_a`'s content, not `wiki_b`'s); `wiki_b/` still exists on disk as a real directory (we removed the junction, not the target); `result["junctions"]` includes `.wiki` (drift was a recreate, which appends).
  - `test_junction_refuses_to_replace_real_directory`: pre-create `target_root / ".wiki"` as a REAL directory (not a junction) containing a sentinel file `target_root/.wiki/sentinel.txt` with known content. Call `create_hub_links(...)`. Assert: the call raises `ValueError` whose message contains the substring `"is not a junction or symlink"`; the real directory still exists; the sentinel file is unchanged.

  All assertions follow the existing in-file `raise AssertionError("...")` pattern (see lines 119, 124, 128 for examples). Test functions print `PASS: <name>` on success.

  Imports at the top of the file already cover `tempfile`, `pathlib.Path`, `yaml`, and the local `_setup`. If `_junction` is not already imported at file-scope, import it via `import _junction` (the `test_portal_flow_integration` function at line 410 uses `import _junction as junction_mod` inside the function body — either pattern is acceptable; pick one consistent with the file's existing test style).

  Register all three new test functions in the `main()` `tests = [...]` list (currently lines 575–585). Order: place the three new tests adjacent to other junction tests (between `test_token_scope_filter_with_slug` and `test_hardlink_inode_skip_idempotent` is natural).
- **Commit:** `test(setup): junction idempotent skip / drift recreate / refuse on real dir`

## Batch Tests

The frontmatter `verify:` runs `unit_tests/test-setup-hub-links.py` first (fast feedback on the new tests + existing tests in the same file) then `unit_tests/run-all.py` (full suite regression).

Acceptance:
- `test-setup-hub-links.py` exits 0 with the three new `test_junction_*` PASS lines and the existing nine PASS lines all present.
- `run-all.py` exits 0. Other test files (notably the upstream-of-this-batch `test-wiki.py`) remain green.
