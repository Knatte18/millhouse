# Review: 18 — par-E — Migrate Python invocation to `uv run` — 04-skills-sweep

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-skills-sweep
date: 2026-04-30
```

## Findings

### [BLOCKING] Card 15: `_junction.create` argument reversal not flagged
**Step:** Card 15, requirement (2) — mill-resume Phase 8
**Issue:** The current SKILL.md call `junction_create(new_worktree / ".millhouse" / "wiki", wiki_clone_path)` has reversed arguments against the actual signature `_junction.create(target: Path, link_path: Path)`. `target` is the directory the junction points AT (should be `wiki_clone_path`); `link_path` is where the junction is created (should be `new_worktree / ".millhouse" / "wiki"`). Card 15 req (2) only says to fix the broken import and "verify `_junction.create` is the real API" — no explicit instruction to correct the reversal. An implementer fixing only the import leaves a runtime-fatal bug: the call would attempt to create a junction at `wiki_clone_path` (an existing real directory) pointing to a non-existent target.
**Fix:** Add to requirement (2): "The current call has reversed arguments; the correct form is `junction_create(wiki_clone_path, new_worktree / '.millhouse' / 'wiki')` — `target` (what the junction points to) is `wiki_clone_path`; `link_path` (where the junction lives) is `new_worktree / '.millhouse' / 'wiki'`." Note: Card 18's grep sweep does not catch this reversal, so it must be called out in Card 15.

### [NIT] Card 17: `sys.path.insert` in mill-skills-from-scripts helper block not addressed
**Step:** Card 17 — mill-skills-from-scripts "How to invoke the helper" Python block
**Issue:** The helper block contains `sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')` which is redundant once the global PYTHONPATH env var is in place (set by mill-setup per the `pythonpath-mechanism` decision). Card 17 is scoped to the two bash invocations (~line 51 and ~61) and ignores this stale manual path setup.
**Fix:** Either remove the `sys.path.insert` line from the helper block in Card 17's scope, or add a note that it remains a harmless no-op post-migration so a future reader doesn't reintroduce it.

## Verdict

REQUEST_CHANGES
One BLOCKING: Card 15 fails to flag the reversed `_junction.create(target, link_path)` argument order; a Sonnet implementer fixing only the broken import leaves a runtime-fatal junction creation call intact.