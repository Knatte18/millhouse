# Review: Audit and clean up stale V2 references

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-27
```

## Findings

### [GAP] health_check does not trigger daemon auto-start
**Section:** `### mill-setup-phase6-deletion`
**Issue:** The decision states "A `health_check` call triggers daemon startup + initial render." The actual `_client.health_check` implementation (verified at `_client.py:396–422`) checks for `.wiki-daemon.json` and returns `False` if absent — it explicitly bypasses `_ensure_daemon` and does NOT spawn the daemon. Auto-start only happens via `_ensure_daemon`, called by operations like `list_tasks_brief`.
**Fix:** Replace the proposed `_client.health_check` verification with a real mutating call (e.g., `_client.list_tasks_brief(wiki_path)`) that goes through `_ensure_daemon` and triggers startup and initial Home.md render on a fresh install.

### [GAP] mill-setup change profile misidentifies hits, misses real stale refs
**Section:** `### Affected SKILL.md files — mill-setup`
**Issue:** The change profile describes two phantom fixes — (a) a `_wiki.health_check(hub_root)` call and (b) a Phase 4.8 `_wiki.write_commit_push` for config.yaml seeding — neither of which exist in the current `mill-setup/SKILL.md` (verified by grep). Meanwhile two real stale hits are unaddressed: Phase 3 prose/code at lines 136/142 uses `import _wiki; result = _wiki.clone_or_init(...)` (the function moved to `_setup.py`, confirmed at `_setup.py:43`); and Phase 6a at line 467 uses `_wiki.write_commit_push` to commit `_Sidebar.md`. A plan writer following the discussion would skip both.
**Fix:** Replace the phantom change bullets with: (a) Phase 3 — change `import _wiki; _wiki.clone_or_init(...)` to `import _setup; _setup.clone_or_init(...)`; (b) Phase 6a — replace `_wiki.write_commit_push(wiki_path, ["_Sidebar.md"], ...)` with the same direct `git -C <wiki_path> add/_commit/push` pattern described for other plain-file commits.

### [NOTE] Q&A says "all 12" but scope counts 13 SKILL.md files
**Section:** `## Q&A log`
**Issue:** Q&A entry reads "Prioritise hot-path skills or do all 12?" / "All 12 in one pass," inconsistent with Problem and Scope which both say 13 SKILL.md files (13 confirmed by grep).
**Fix:** Update the Q&A entry to say 13.

## Verdict

GAPS_FOUND
Two real mill-setup stale references are absent from the change profile, and the health_check auto-start claim contradicts the source.