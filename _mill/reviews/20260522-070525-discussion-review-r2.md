# Review: Set MILL_PYTHON via mill-setup, use in all skill invocations

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-22
```

## Findings

### [NOTE] Verification command 2 uses unexpanded `~` in Python
**Section:** Testing — step 2
**Issue:** `open('~/.claude/settings.json')` inside a Python `-c` string does not expand `~` on Windows; Python's `open()` treats it as a literal path component, causing FileNotFoundError when the verification command is run as written. The Phase 4.8 snippet itself is correct (`Path.home()`).
**Fix:** Replace with `Path.home() / '.claude/settings.json'` (or `os.path.expanduser`) in the verification command example so the plan writer doesn't copy a broken form.

### [NOTE] Phase 4.8 snippet has no guard for missing `settings.json`
**Section:** Technical context — Phase 4.8 logic
**Issue:** `settings_path.read_text()` raises `FileNotFoundError` if `~/.claude/settings.json` is absent. CC running guarantees the file exists in practice, but the discussion's failure-modes coverage is silent on this assumption.
**Fix:** Either state the assumption explicitly ("CC creates settings.json on first launch; mill-setup requires an active CC session") or add a one-line guard: `data = json.loads(settings_path.read_text()) if settings_path.exists() else {}`.

## Verdict

APPROVE
Discussion is complete; two NOTEs on verification command portability and an unstated file-existence assumption.