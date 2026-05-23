# Review: Migrate wiki task store to TinyDB

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-23
```

## Findings

### [GAP] `_Sidebar.md` render format conflicts with "same style as today"
**Section:** Scope (Out) / Technical Context → render() output format
**Issue:** The existing `_sidebar.py:render_sidebar()` distinguishes tasks with proposal files (emits a wiki link `[Title](proposal-slug.md)`) from tasks without (emits plain text `Title`). The new `render()` only has TinyDB data — `has_proposal` is not in the data model and the daemon's render step has no specification for filesystem proposal-file scanning. The discussion's `_Sidebar.md` description ("list of task links in the same group order") implies all-links output, which differs from today's format.
**Fix:** Either add `has_proposal: bool` to the TinyDB data model (set on write, based on a disk scan at write time), or explicitly declare that the generated sidebar always emits links, and accept the format change.

### [GAP] Pull invalidation leaves TinyDB empty; `get("Home.md")` returns stale empty render
**Section:** Technical Context → Store replacement / render()
**Issue:** `_handle_read` calls `store.invalidate_all()` after every lazy pull. The unit test spec says `invalidate_all()` clears all tasks. After that, `store.get("Home.md")` renders from empty TinyDB, producing `"# Tasks\n\n"` — a cache *hit* returning empty content. The server never falls through to a disk read, so the client receives an empty task list on every pull cycle. The discussion does not specify how TinyDB gets repopulated after a pull (i.e., who calls `store.set("Home.md", disk_content)` to parse the pulled file back into TinyDB).
**Fix:** Define that `get("Home.md")` returns `None` when TinyDB is uninitialized (i.e., after `invalidate_all()`), so the existing server cache-miss path reads the pulled file from disk and calls `set("Home.md", content)` to repopulate TinyDB. Distinguish "uninitialized" from "genuinely zero tasks."

### [NOTE] `_server.py` changes implied but not listed in scope
**Section:** Scope (In)
**Issue:** Expanding the commit to include `tasks.json` and `_Sidebar.md`, intercepting Home.md writes for TinyDB parsing, and re-rendering after every write all require non-trivial changes to `_server.py`. The scope list names `_store.py` and commit behavior as in-scope but does not name `_server.py` explicitly.
**Fix:** Add `_server.py` to the in-scope file list so the plan writer knows to budget implementation effort for it.

### [NOTE] `invalidate(slug)` in unit test spec vs `invalidate(rel_path)` in server code
**Section:** Technical Context → Store replacement / Testing → unit tests
**Issue:** The unit test spec describes `invalidate(slug)` removing a task by slug. The server currently calls `self._store.invalidate(rel_path)` with filesystem paths (e.g., `"Home.md"`, `"other.md"`). Non-Home.md paths still use the old path-cache behaviour (per the discussion), so `invalidate(rel_path)` must still work for those paths. How `invalidate` serves both call sites — path-based cache clearing and slug-based task removal — is unspecified.
**Fix:** Clarify whether `invalidate` is overloaded, replaced by a `remove_task(slug)` method for the task-level use case, or dropped in favour of calling `invalidate_all()` after writes.

## Verdict

GAPS_FOUND
Two correctness gaps — sidebar proposal-link semantics and post-pull TinyDB repopulation — must be resolved before planning.