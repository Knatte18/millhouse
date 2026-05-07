# Review: 27 (A) — Prune unused skills and scripts — 01-prune-skills

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 01-prune-skills
date: 2026-05-07
```

## Findings

### [BLOCKING] Card 5 misses `iter_target_scripts` test block in test-skill-writer.py

**Step:** Card 5

**Issue:** Card 5 scopes its `test-skill-writer.py` changes to lines 155–173 (the "Third call / hyphenated skill name" block), but the `iter_target_scripts` block earlier in the file also fails after Card 3. That block: (a) builds `expected_stems` as a sorted list of 13 stems that includes `"millpy-list"`, `"millpy-worktree"`, and `"millpy-fetch-issues"`; (b) touches one `.py` file per `SHORTCUT_SCRIPTS` entry (14 files) to populate the temp scripts dir; (c) asserts `len(result) != 13`. After Card 3 reduces `SHORTCUT_SCRIPTS` from 14 to 11 entries, only 11 files are created, `iter_target_scripts` returns 10 (11 minus `millpy-add`), and the `len(result) != 13` assertion fails — causing `test-skill-writer.py` to fail the batch verify command.

**Fix:** Card 5 must also update the `iter_target_scripts` block: remove `"millpy-list"`, `"millpy-worktree"`, and `"millpy-fetch-issues"` from `expected_stems` (leaving 10 stems), change the count assertion from `13` to `10`, and update the inline comments ("13 expected paths" → "10 expected paths"; "14 total" → "11 total").

### [NIT] Card 8 runs skills-index from source tree, violating CLAUDE.md convention

**Step:** Card 8

**Issue:** `python plugins/mill/scripts/millpy-skills-index.py` is a source-tree invocation. CLAUDE.md forbids operational commands from referencing `plugins/mill/...` paths directly (the unit-tests runner is the sole exception).

**Fix:** Use `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"` — both the source and cache versions scan the current worktree's `plugins/` directory via `git rev-parse`, so the result is identical and the convention is respected.

## Verdict

REQUEST_CHANGES — one blocking gap in Card 5 causes the batch verify to fail.