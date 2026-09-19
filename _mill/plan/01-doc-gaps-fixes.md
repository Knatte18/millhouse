# Batch: doc-gaps-fixes

```yaml
task: 'mill-merge / mill-merge-in: brief-staging path bug and easy-to-miss caching instruction'
batch: doc-gaps-fixes
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py
depends-on: []
```

## Batch Scope

Both cards add a single explanatory paragraph to an existing, already-correct SKILL.md step — no bash commands, no scripts, no behavior change. Card 1 closes the #996 doc gap in `mill-merge-in/SKILL.md` (Step 5.5's relative-path convention has no stated rationale, so a future edit can silently reintroduce the exact regression commit `7a972fbf` already fixed once). Card 2 closes the #987 doc gap in `mill-merge/SKILL.md` (Step 5's direct-squash flow has no documented recovery path for `cached_task`/`cached_task_description` when the Entry caching step is skipped, unlike the file's existing `closed`-route fallback). The cards touch two different files with no shared state, but are grouped into one batch because each is a single-paragraph insertion — splitting them into separate batches would add DAG/review overhead disproportionate to the size of the change. Neither card has a batch-local decision that differs from `## Shared Decisions` in the overview.

## Cards

### Card 1: Document the relative-path convention in mill-merge-in Step 5.5

- **Context:**
  - `plugins/mill/unit_tests/test-brief-commit.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### 5.5. Commit dispatch briefs`, insert one new paragraph immediately after the existing paragraph that begins "**Why staged-only, not unscoped porcelain:**" and immediately before the paragraph that begins "This also now picks up Step 5's inline-mode codeguide docs" (the `#946` paragraph). Do not change the existing bash fence (`if [ -d <worktree>/_mill/briefs ]; then ... fi`) or either surrounding paragraph — insert only the new paragraph between them.

  New paragraph, verbatim:

  > **Why relative, not absolute:** the `git -C <worktree> add _mill/briefs/` line above must keep the pathspec relative to `<worktree>` — never `git -C <worktree> add <worktree>/_mill/briefs/`. `git -C <dir>` already sets `<dir>` as the working directory for the command that follows it, so re-prefixing the pathspec with `<worktree>` again is redundant and resolves to a doubled, non-existent path. A past edit made exactly this mistake and broke `test-brief-commit.py`'s `"add _mill/briefs/"` substring regression lock; it was re-fixed in commit `7a972fbf` ("mill-merge-in: fix Step 5.5 git add command to match brief-commit test convention"). Keep the pathspec relative in any future edit to this step's bash block.

- **Commit:** `docs(mill-merge-in): explain the relative-path convention in Step 5.5 (#996)`

### Card 2: Document the cached_task recovery path in mill-merge Step 5

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### 5. Direct squash`'s direct-path bash block, insert one new paragraph immediately after the paragraph that begins "`reset --hard origin/<parent_branch>` is deliberately never used as the fast-forward mechanism here" and immediately before the fenced bash block whose last two lines are `git -C <parent-path> commit -m "<cached_task>"` and `git -C <parent-path> push`. Do not change the bash fence itself, the paragraph immediately before it, or the paragraph immediately after it (the one beginning "Note: these two commands specifically require the relative form") — insert only the new paragraph between the "deliberately never used" paragraph and the bash fence.

  New paragraph, verbatim:

  > **Recovery path when `cached_task`/`cached_task_description` are undefined here:** Entry's phase-gate table caches these two values from `_mill/status.md` while `phase: done`, before Step 4's cleanup commit deletes `status.md` — but if that caching step was skipped (the #987 incident), they are undefined by the time this bash block runs. Recover them instead of halting: `git -C <worktree> show HEAD~1:_mill/status.md` still returns `status.md`'s last content — at this point in the flow, `HEAD` is Step 4's own cleanup commit (the one that ran `git rm -r <task_dir>` and deleted `status.md`), so its parent, `HEAD~1`, is the commit immediately before that deletion and still has the file, regardless of how many earlier commits led up to it. Read the `task:` field from that output — falling back to the task's slug if the field itself is absent, exactly like the Entry caching block's own default — and the `task_description:` field, falling back to the just-recovered `task` value, exactly like the Entry caching block's own default. Bind the two recovered values to `cached_task` and `cached_task_description` and continue into the bash block below. This mirrors the `closed` PR-state route's own documented fallback (`### PR-state gate`) for the same two variables, adapted to this flow's own recovery source (git history here, instead of the wiki, since `status.md` is still present one commit back in this flow).

- **Commit:** `docs(mill-merge): document the cached_task recovery path in Step 5 (#987)`

## Batch Tests

`verify:` runs `test-brief-commit.py` and `test-skill-helper-drift.py` — the two existing regression locks that read `plugins/mill/skills/mill-merge-in/SKILL.md` and `plugins/mill/skills/mill-merge/SKILL.md` textually. Both cards add prose only, next to (never inside) the exact bash fences those locks assert against, so both locks are expected to continue passing unchanged; running them confirms neither insertion accidentally landed inside a fence or altered an asserted substring. No other test in the suite asserts specific content of either file — `test-guards.py`'s wiki-cwd-pattern check does read `mill-merge/SKILL.md`, but that file is allowlisted out of that check's pattern match, so it exercises no assertion this batch could break — so this two-file `--only` scope is complete for this batch: it is not a cross-cutting-helper case needing the unbounded `run-all.py` escape hatch.
