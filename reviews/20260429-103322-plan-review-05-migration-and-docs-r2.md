# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 05-migration-and-docs

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 05-migration-and-docs
date: 2026-04-29
```

## Findings

### [NIT] `_junction.create` semantics misrepresented for Step 5 portals
**Step:** Card 23 — Step 5 (portals)
**Issue:** The spec says "the helper raises if the junction already points elsewhere" but `_junction.create` in `_junction.py:62–63` raises on `link_path.exists() or link_path.is_symlink()` — any existing junction, not just wrong-target ones. The "idempotent: skip if exists" note and the direct `_junction.create` call are therefore contradictory: calling `_junction.create` directly fails re-runs even when the portal already correctly points to `wts/<dirname>`.
**Fix:** Either add a note that the implementer wraps `_junction.create` with an existence-then-skip check (accepting that wrong-target portals are silently preserved), or remove "idempotent" from the Step 5 description and document that partial-failure recovery requires manual portal cleanup before re-run.

### [NIT] `_tasks_md.py` listed in Reads is unused by the migration logic
**Step:** Card 23 — Reads field
**Issue:** `_tasks_md.py` parses Home.md task headings; the migration pre-flight reads `wiki/active/<slug>/status.md` via `_status`, not Home.md. No other step in Card 23 touches Home.md.
**Fix:** Remove `_tasks_md.py` from Reads; optionally also remove `_wiki.py` (no wiki lock or commit operations in the migration script) to keep the read list purposeful.

## Verdict

APPROVE — two NITs; no BLOCKINGs; core design, ordering, and path arithmetic are sound.