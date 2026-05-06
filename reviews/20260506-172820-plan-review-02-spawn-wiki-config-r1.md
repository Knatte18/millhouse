# Review: 12 (C) — Restructure hub junction layout — 02-spawn-wiki-config

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-spawn-wiki-config
date: 2026-05-06
```

## Findings

### [BLOCKING] wiki/config.yaml push leaves old junctions unstripped on current task
**Step:** Card 3
**Issue:** Card 3 immediately pushes the new junction names (`.wiki`, `.portals`) to the shared wiki. After this commit, `_junction.strip_all_in_worktree(worktree, junctions_cfg)` — called by mill-merge/mill-cleanup — reads the live config and will iterate only `.wiki` and `.portals`. The `rename-hub-junctions` worktree was spawned with the OLD layout and carries `.millhouse/wiki`, `.others`, `.active`. Those junctions will not be stripped; if any code path falls through to the `rmdir /s` / `shutil.rmtree` fallback, those junctions will be followed, risking wiki or portals directory wipeout.
**Fix:** Add an explicit bootstrap step in Card 3 (before committing the config) that calls `_junction.strip_all_in_worktree(current_worktree, old_junctions_cfg)` for every active task worktree under the container, using the OLD config read before overwriting — or defer the config push to batch 3 where `millpy-migrate-layout.py` handles the transition atomically.

### [NIT] `_wiki.py` `_JUNCTION_DEFAULTS` not updated
**Step:** (batch-wide — no card addresses it)
**Issue:** `_wiki.py`'s module-level `_JUNCTION_DEFAULTS` still references `.millhouse/wiki` and `.active` keys. After Card 3, any code path that falls back to these defaults (config file absent during bootstrap) will create junctions with old names.
**Fix:** Add `_wiki.py` to an existing card's `Edits:` and update `_JUNCTION_DEFAULTS` to `{".wiki": "<WIKI_PATH>"}` (`.portals` is SLUG-scoped and should not be in defaults).

### [NIT] Card 9 stub justification incorrect for `write_wiki_active_task_md`
**Step:** Card 9, test-millpy-spawn.py req 1
**Issue:** The plan states the stub prevents "an `AttributeError` when `millpy-spawn.py` is loaded (the module-level attribute lookup)", but Card 5 calls `_spawn_core.write_wiki_active_task_md(...)` via module reference inside `main()` — there is no module-level `from _spawn_core import write_wiki_active_task_md`. No AttributeError would occur at load time without the stub.
**Fix:** Keep the stub (it's harmless in the existing mock-injection pattern) but correct the comment to "prevents AttributeError in main() when the stub map replaces _spawn_core with a bare MagicMock that lacks the attribute."

## Verdict

REQUEST_CHANGES — one BLOCKING: Card 3 pushes config immediately without stripping old junctions from the currently-running task's worktree.