# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — consumers-and-skills

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: consumers-and-skills
date: 2026-04-29
```

## Findings

### [NIT] mill-merge teardown: prose sections instead of plan-specified table rows
**Location:** `plugins/mill/skills/mill-merge/SKILL.md` (teardown section)
**Issue:** Card 20 requirement states "each step is a numbered table row with a 'Why' column referencing the discussion." The implementation uses detailed `### N.` prose sections instead. All seven steps and their rationale are present; only the table format is absent.
**Fix:** Either accept prose format as superior given the code blocks embedded in each step, or add a compact summary table before the prose body.

### [NIT] `millpy-status.py` iterates `active_worktree_list` twice
**Location:** `plugins/mill/scripts/millpy-status.py:27-30`
**Issue:** `active_worktree_list` is traversed twice to build `worktree_map` and `active_worktree_paths` separately. One pass suffices.
**Fix:** `worktree_map, active_worktree_paths = {}, {}; for path, slug, _ in active_worktree_list: worktree_map[slug] = str(path); active_worktree_paths[slug] = path`.

### [NIT] mill-resume Phases 7, 8, 10 reference obsolete `millpy.core.*` API
**Location:** `plugins/mill/skills/mill-resume/SKILL.md` (Phases 7, 8, 10)
**Issue:** These phases reference `millpy.core.junction.create`, `millpy.entrypoints.spawn_task`, and `python -m millpy.entrypoints.regenerate_sidebar` — a pre-v2 module layout that no longer exists. Card 21 was scoped to state-file path updates only; these remnants were pre-existing and not in scope, but they remain misleading after the rewrite.
**Fix:** Update Phase 8 junction creation to use `${CLAUDE_PLUGIN_ROOT}/scripts/_junction.py` and Phase 10 to the current `_sidebar.regenerate` pattern (matching the style of every other SKILL.md updated in this batch).

## Verdict

APPROVE — all seven cards are correctly implemented; no blocking defects found.