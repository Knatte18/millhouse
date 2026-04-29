# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — create-hub-links

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: create-hub-links
date: 2026-04-29
```

## Findings

### [NIT] Module-level public API summary has stale `recreate_active_junction` signature
**Location:** `_spawn_core.py:50` (module docstring, "Public API" section)
**Issue:** The Public API summary still shows `recreate_active_junction(wiki_path, slug, mill_dir)` — the old three-parameter signature. The function docstring itself is correctly updated.
**Fix:** Change the Public API line to `recreate_active_junction(slug, mill_dir, container_path) -> None` to match the implementation.

### [NIT] Call-order test doesn't verify `mkdir` precedes `junction.create`
**Location:** `test-millpy-spawn.py:420` (`test_create_hub_links_called_after_portal_creation`)
**Issue:** The plan requires asserting all three steps in sequence: `portals.mkdir` → `junction.create` → `create_hub_links`. The test only logs and verifies `junction.create` before `create_hub_links`; `Path.mkdir` is patched to a no-op and never enters `call_log`.
**Fix:** Add a `call_log.append("portals_mkdir")` side-effect on `Path.mkdir` for the specific portals path, then assert `portals_mkdir` appears before `junction.create` in the log.

## Verdict

APPROVE
Two NITs (stale docstring line, incomplete call-order log); no blocking issues.