# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 05-migration-and-docs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 05-migration-and-docs
date: 2026-04-29
```

## Findings

### [BLOCKING] Wiki path resolution claim is factually wrong

**Step:** Card 22 — pre-flight check
**Issue:** The requirement states `_paths.resolve_wiki_path(Path.cwd())` "works on the OLD layout because the old `_sibling.py` rule still recognises `hub`-form via prefix-form fallback after Batch 1's change." This is incorrect. Batch 1's new `_sibling` checks `parent.name == "wts"` (False for `<container>/hub/`) and falls to prefix-form, which returns `<container>/hub.wiki/`, not `<container>/wiki/`. Unless `config.local.yaml` has an explicit `paths.wiki:` override (not guaranteed for existing installs), the wiki lookup returns a non-existent path; the active-tasks scan finds no `active/` directories, passes vacuously, and the migration proceeds while tasks may still be in flight.
**Fix:** Derive the wiki path in the migration script as `main_root.parent / "wiki"` (the OLD layout's structural invariant: hub at `<container>/hub/`, wiki at `<container>/wiki/`). Do not rely on `resolve_wiki_path`'s sibling detection, which is calibrated for the NEW layout.

### [NIT] `portals/` mkdir idempotency not annotated

**Step:** Card 22 — Step 5
**Issue:** Step 1 explicitly marks `mkdir <container>/wts` as idempotent ("skip if exists"), but Step 5 (`mkdir <container>/portals`) carries no such note; a re-run after partial failure would crash when `_junction.create` hits pre-existing junctions.
**Fix:** Add "idempotent: skip if exists" annotation to `mkdir <container>/portals`, matching Step 1's language.

## Verdict

REQUEST_CHANGES — one BLOCKING: the prefix-form fallback claim is wrong, causing the pre-flight in-flight check to pass vacuously for typical installs.