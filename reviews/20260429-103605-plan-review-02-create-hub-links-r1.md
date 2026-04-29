# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 02-create-hub-links

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-create-hub-links
date: 2026-04-29
```

## Findings

### [BLOCKING] `portals/` must exist before `.others` junction is created

**Step:** Card 8 (`millpy-spawn.py` use `create_hub_links`)
**Issue:** Card 8 calls `create_hub_links(...)` first, then creates `portals/` as part of the portal-entry step afterward. `create_hub_links` will attempt to create `.others → <CONTAINER_PATH>/portals/` (once Card 10 lands). On Windows, `mklink /J` requires the target directory to exist and returns non-zero if it doesn't — `_junction.create` will raise `OSError`. A fresh clone with no prior spawn has no `portals/` dir, so the first spawn after Card 10 fails.
**Fix:** In Card 8, `mkdir <container>/portals/` (parents=True, exist_ok=True) **before** calling `create_hub_links`, not after. Alternatively, Card 6's spec should ensure ALL junction targets (not just `<SLUG>`-bearing ones) exist before calling `_junction.create`.

---

### [BLOCKING] Card 9 portal-creation ordering is underconstrained — "after" causes unrecoverable failure

**Step:** Card 9 (`millpy-claim.py` portal creation + `recreate_active_junction` callsite)
**Issue:** The card says "Add idempotent portal-entry creation immediately **before or after** the `recreate_active_junction` call." Only "before" is correct. If after: `recreate_active_junction` calls `target.mkdir(parents=True, exist_ok=True)` where `target = container_path / "portals" / slug`, creating a **real directory** at `portals/slug/`. The portal-entry creation step then finds a real directory, falls to the "exists but points elsewhere" branch, calls `_junction.remove(portals/slug)`, which raises `ValueError` ("not a junction or symlink — refusing to remove"). The operation is unrecoverable without manual cleanup.
**Fix:** Card 9 must specify portal-entry creation happens **before** `recreate_active_junction`, not "before or after."

---

### [NIT] Card 8 test assertions incompatible with mock-based `test-millpy-spawn.py`

**Step:** Card 8 (test extension requirements)
**Issue:** Card 8 requires extending `test-millpy-spawn.py` to "assert that after spawn the portal entry exists and resolves to the new worktree path; assert that `tasks.md` hardlink exists (inode match); assert that `.others` junction exists." The existing test file mocks `Path.exists`, `Path.mkdir`, `_junction`, and `_wiki.read_junctions` — it cannot observe real filesystem state. Implementing these assertions inline would either be vacuous (mocked) or require a parallel fixture-based integration approach that conflicts with the file's design.
**Fix:** Move portal/junction/hardlink filesystem assertions into `test-setup-hub-links.py` (Card 6), which already uses `tempfile.TemporaryDirectory()` and real disk operations. The Card 8 extension to `test-millpy-spawn.py` should focus on call-order verification only (consistent with the file's existing mock pattern).

## Verdict

REQUEST_CHANGES — two blockers: `portals/` creation order (Windows `mklink /J` requirement) and Card 9's ambiguous "before or after" ordering.