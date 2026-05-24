# Review: Adopt V3 wiki module in V2 scripts

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md (round 3)
date: 2026-05-24
```

## Findings

### [GAP] Unlisted `_tasks_md` callers break on deletion
**Section:** § Scope — "Port every V2 wiki call site" / "Delete `_tasks_md.py`… outright"
**Issue:** Six files import `_tasks_md` and call `_tasks_md.parse()` but appear nowhere in the scope or call-site table: `millpy-inspect.py:54`, `millpy-status.py:32`, `millpy-terminal.py:59`, `millpy-vscode.py:180`, `_marker.py:53,97`, `millpy-migrate-layout.py:230`. Additionally `millpy-spawn.py:130` calls `_tasks_md.parse(home_text)` immediately after the `:128` `sync_pull` drop that IS listed. All seven break with ImportError when `_tasks_md.py` is deleted.
**Fix:** Add these call sites to the "Port every V2 wiki call site" list with their V3 replacement (`wiki.list_tasks_brief()` for the read-only parse calls); the `millpy-spawn.py:130` parse should be listed alongside the `:128` `sync_pull` drop.

### [NOTE] `millpy-fold.py:15` mislabelled as "local constant"
**Section:** § Scope — `millpy-fold.py` call-site entry
**Issue:** Line 15 is inside the module docstring (triple-quoted string), not an executable Python constant definition; calling it a "local duplicate `LOCKED_FOLD_PHASES` constant — delete" could confuse a plan writer expecting to remove a top-level assignment.
**Fix:** Clarify that `:15` is a docstring line to update/remove, not a standalone Python constant.

### [NOTE] `_parse.py` scope bullet omits extended-parser additions
**Section:** § Scope — "Update `wiki/_parse.py`" vs § Testing — `test-wiki-parse.py`
**Issue:** The `_parse.py` scope bullet lists only the `[s]`/`[abandoned]` status fixes, but the testing section requires three additional features in `_parse.py`: parenthetical layer-header recognition, multi-paragraph brief capture, and info-note heading skip. These features appear only in the test list and the migration script anatomy, not in the `_parse.py` scope bullet.
**Fix:** Add the three extended-parser feature lines to the `_parse.py` scope bullet so the scope and test expectations align.

## Verdict

GAPS_FOUND
Six undocumented `_tasks_md.parse` callers will break at import when `_tasks_md.py` is deleted; add them to scope.