# Review: Migrate wiki task store to TinyDB

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-23
```

## Findings

### [GAP] _handle_write post-pull invalidation and TinyDB update sequence unspecified
**Section:** Technical context — Store replacement / Post-pull repopulation
**Issue:** `_handle_write` calls `self._store.invalidate_all()` at line 158 of `_server.py` (confirmed by reading source), but the discussion specifies the `invalidate_all()` replacement only for `_handle_read`. It does not specify: what replaces `invalidate_all()` in the write path; when `store.set("Home.md", new_content)` is called relative to the CAS check and `atomic_write`; or when `render()` is invoked and its outputs added to the commit. These omissions leave the plan writer unable to derive the correct write-path sequence without guessing.
**Fix:** Add a "Write path sequence" note to § Technical context specifying the order: pull → invalidate-equivalent → CAS check (using current TinyDB or disk hash for Home.md) → `atomic_write` client files → `store.set("Home.md", new_content)` to update TinyDB → `render()` → write rendered files → commit all.

### [NOTE] upsert_task body field preservation on Home.md write not specified
**Section:** Technical context — Parsing incoming Home.md writes
**Issue:** When parsing an incoming Home.md write where `body` is not recoverable, it is unspecified whether `upsert_task` preserves an existing non-empty `body` in TinyDB or overwrites it with `""`. Body is always `""` in this task's scope, so it will not cause a bug now, but the intended behavior is ambiguous for the plan writer and for future callers.
**Fix:** Add one sentence clarifying that `upsert_task` preserves the existing `body` value when the field is not present in the parsed data (i.e., upsert merges, not replaces).

## Verdict

GAPS_FOUND
Write-path `invalidate_all()` replacement and TinyDB update sequence must be specified before planning.