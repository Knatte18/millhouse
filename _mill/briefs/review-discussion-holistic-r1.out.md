MILL_REVIEW_BEGIN
# Review: CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] `sys.path[0]` premise is factually wrong for `-c` invocations
**Section:** Decisions > "Resolve plugin root via `sys.path[0]`, not `os.environ`"; Technical context (SKILL.md:409-429).
**Issue:** For `python -c "..."`, CPython always sets `sys.path[0]` to `''` (cwd) — PYTHONPATH entries are inserted starting at `sys.path[1]`, never `sys.path[0]`. The existing code's `sys.path.insert(0, os.environ['CLAUDE_PLUGIN_ROOT'] + '/scripts')` is what currently forces index 0 to the scripts dir; it is not redundant with the outer `PYTHONPATH=` prefix as the Technical Context claims. The proposed fix removes that insert and then reads `sys.path[0]`, which would resolve to `''` (or cwd), not `<plugin-root>/scripts`.
**Fix:** Re-verify actual `sys.path` contents from a real `-c` invocation before deciding; either keep an explicit `sys.path.insert(0, ...)`-equivalent, or resolve from `sys.path[1]` (or search `sys.path` for a `scripts`-named entry), and update the guard/decision text and `resolve_plugin_root_from_syspath` argument accordingly. This also invalidates the "guard" decision's assumption that a malformed value is the rare case — with the current proposal every invocation would trip the guard.

## Verdict

REQUEST_CHANGES
Core `sys.path[0]` premise underlying two Decisions is factually incorrect for `-c` mode; needs re-verification before plan writing.
MILL_REVIEW_END
