I have enough source evidence. Let me write the review.

# Review: 18 — par-E — Migrate Python invocation to `uv run`

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-04-30
```

## Findings

### [GAP] Phase 4.7 bootstrap chicken-and-egg
**Section:** § Technical context — mill-setup Phase 4.7 / § Decisions — pythonpath-mechanism
**Issue:** The rejected "session-start `export PYTHONPATH`" is currently the mechanism that makes Phase 4.7's `python -c "... import _shortcuts; write_all()"` work. The discussion's migration (remove session export, switch all `-c` calls to `uv run --project`) leaves Phase 4.7 calling `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "import _shortcuts; ..."` with no PYTHONPATH in the process env on a first-ever setup — `_shortcuts` is not found, Phase 4.7 aborts. Verified: current `mill-setup/SKILL.md:48–54` explicitly uses `export PYTHONPATH` as the session preamble, and `mill-setup/SKILL.md:197–205` also has `sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')` inside the Phase 4.7 snippet.
**Fix:** Specify how Phase 4.7's `write_all()` call is bootstrapped on first run — e.g., a one-time `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."` for that specific call, distinguishing it from the general "uv run, no per-call PYTHONPATH" pattern.

### [NOTE] Integration-test subprocess description is partially inaccurate
**Section:** § Technical context — Integration tests
**Issue:** The discussion states tests "Currently call `subprocess.run([sys.executable, ...], env={**os.environ, "PYTHONPATH": str(SCRIPTS)})`", but only the three review tests (`test-review-code/discussion/plan.py:90-93`) explicitly set `env["PYTHONPATH"]`. The other tests (`test-spawn.py:144-146`, `test-cleanup.py:164-166`, `test-abandon.py:131`, `test-status.py:150`, `test-inspect.py:113`) use `sys.executable` with inherited env — they already rely on ambient PYTHONPATH. Verified by reading source.
**Fix:** Narrow the description: only the review tests require removing an explicit PYTHONPATH env override; the other tests just need the `sys.executable` → `["uv", "run", "--project", ...]` substitution.

### [NOTE] "Semver-sort" label is misleading
**Section:** § Decisions — ps1-wrapper-design / § Technical context — PS1 template shape
**Issue:** The decision calls the version-selection "semver-sort at runtime," but the PS1 template shows `Sort-Object Name -Descending`, which is lexicographic — identical in kind to the existing `.py` template's `sorted(..., key=lambda d: d.name, reverse=True)` (verified: `templates/shortcut-wrapper.py:20-24`). Lexicographic sort misordering (e.g., `0.9.0 > 0.10.0`) is a pre-existing limitation, not new to this task.
**Fix:** Change "semver-sort" to "lexicographic-sort (same as existing .py wrapper)" to set accurate expectations; or note the limitation explicitly.

## Verdict

GAPS_FOUND
Phase 4.7 bootstrap mechanism is unspecified; plan writer cannot safely implement first-run PYTHONPATH-less `_shortcuts.write_all()` call.