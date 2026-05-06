# Review: 12 (C) — Restructure hub junction layout — 04-skills-docs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-skills-docs
date: 2026-05-06
```

## Findings

### [BLOCKING] Card 13 Req 1: wrong path and missing portals update
**Step:** Card 13, Requirement 1
**Issue:** "remove the `.others -> ../wts/millhouse` entry" references a path that does not exist in CLAUDE.md's container layout. The portals section shows `millhouse -> ../wts/millhouse` and `<slug> -> ../wts/<slug>` — no `.others` entry. More critically, the `portals-target-is-wiki-active` shared decision requires changing `<slug> -> ../wts/<slug>` to `<slug> -> ../wiki/active/<slug>/`, and no requirement in Card 13 specifies this update.
**Fix:** Replace the "remove `.others → ...`" instruction with "change `<slug> → ../wts/<slug>` to `<slug> → ../wiki/active/<slug>/` in the portals section". Add this portals update to Requirement 1 explicitly.

### [NIT] Card 14 Req 1: `upsert` not yet defined, missing DAG edge
**Step:** Card 14, Requirement 1
**Issue:** The replacement snippet calls `_gitignore.upsert(hub_gi, _gitignore.GLOB_ENTRIES)`, but `_gitignore.py` exposes only `upsert_split` and `render_block`. `upsert` is introduced by batch 01. Batch 04 declares `depends-on: [2]`, not `[1, 2]`, so the dependency is untracked in the DAG.
**Fix:** Add `1` to batch 04's `depends-on` list. Sequential mill-go execution makes this safe in practice, but the DAG should reflect the true dependency.

### [NIT] Card 17 Req 4: "always remove" leaves rmtree guard unaddressed
**Step:** Card 17, Requirement 4
**Issue:** Changing Step 10 from "if `wiki_path / 'active' / slug` exists" to "always remove" is correct post-migration, but `shutil.rmtree` raises `FileNotFoundError` for pre-migration tasks (spawned before batch 02 lands). The requirement doesn't preserve or address the existence check.
**Fix:** Either note that an `errors='ignore'` / `ignore_errors=True` guard should remain, or explicitly state that migration (batch 03) must complete before mill-merge is called on any active task.

## Verdict

REQUEST_CHANGES
Card 13 Req 1 omits the required portals-section update and references a non-existent path.