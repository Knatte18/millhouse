# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 05-migration-and-docs

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 05-migration-and-docs
date: 2026-04-29
```

## Findings

### [BLOCKING] `_junction.create` behavior mischaracterized in Step 5
**Step:** Card 23, Step 5 (portal junctions)
**Issue:** Requirements state the helper "raises if the junction already points elsewhere — that is the desired behaviour for partial-failure re-runs." Inspecting `_junction.py:create`: the guard is `if link_path.exists() or link_path.is_symlink()` — it raises for **any** existing path, not only wrong-target ones. A re-run after partial failure therefore fails on already-correct portal junctions too, forcing manual cleanup of everything, not just the broken entry.
**Fix:** Either pre-check each `portals/<dirname>` before calling `_junction.create` (skip if it already resolves to the correct target, raise if it resolves elsewhere), or remove the "desired behaviour for partial-failure re-runs" framing entirely and document that re-runs require manual removal of all already-created portals.

### [BLOCKING] Card 24 references non-existent discussion section
**Step:** Card 24, Requirements
**Issue:** "Add a fenced ` ```text ` block with the diagram from `discussion.md ## Target layout`" — no `## Target layout` section exists in the provided `discussion.md`. Headers present: `## Problem`, `## Scope`, `## Decisions`, `## Technical context`, `## Constraints`, `## Testing`, `## Q&A log`. The implementer has no authoritative diagram source.
**Fix:** Inline a concrete layout diagram in the Card 24 requirements directly, or replace the reference with `discussion.md ## Scope` (which lists the new paths in prose) and instruct the implementer to derive the diagram from that paragraph.

### [NIT] Reads list contains modules with no evident use
**Step:** Card 23, Reads
**Issue:** `_active.py` (reads per-worktree `.millhouse/active.slug.md`) and `_tasks_md.py` (parses `Home.md`) appear in Reads, but the requirements use neither; the pre-flight check reads `wiki/active/<slug>/status.md` via `_status.py`.
**Fix:** Remove `_active.py` and `_tasks_md.py` from Card 23 Reads, or add a sentence to the requirements identifying where each module is used.

### [NIT] `.scratch/` directory not created before log open
**Step:** Card 23, Step b (Operations log)
**Issue:** Plan instructs opening `.scratch/migrate-<timestamp>.log` for write with no preceding `mkdir`; the directory does not exist in a fresh checkout.
**Fix:** Add `Path(".scratch").mkdir(exist_ok=True)` before opening the log file.

## Verdict

REQUEST_CHANGES
Two blockers: `_junction.create` API mischaracterized for re-run semantics; Card 24 references a non-existent `discussion.md` section.