# Plan: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs

```yaml
task: "mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs"
slug: "mill-merge-finalize-codeguide-bugs"
approved: false
started: "20260904-101011"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-merge-in-parent-and-baseline
    file: 01-mill-merge-in-parent-and-baseline.md
    depends-on: []
    verify: null
  - number: 2
    name: mill-finalize-discussion-citation-scan
    file: 02-mill-finalize-discussion-citation-scan.md
    depends-on: []
    verify: null
  - number: 3
    name: resolve-scope-cwd-anchor
    file: 03-resolve-scope-cwd-anchor.md
    depends-on: []
    verify: PYTHONPATH= "$MILL_PYTHON" plugins/codeguide/unit_tests/test-resolve-scope.py
```

## Shared Decisions

### Decision: three independent root batches, one per file family

- **Decision:** Split the five source bugs (#977, #946, #945, #930, #943) into three batches grouped by which files they touch, not one batch per bug: batch 1 covers `mill-merge/SKILL.md` + `mill-merge-in/SKILL.md` (bugs #977, #946, #945, all of which edit `mill-merge-in/SKILL.md`), batch 2 covers `mill-finalize/SKILL.md` + `CLAUDE.md` (bug #930), batch 3 covers `resolve_scope.py` + its unit test (bug #943). All three batches have `depends-on: []` — no file overlap between batches, so they are independent roots in the DAG.
- **Rationale:** Grouping every card that edits the same file into a single batch avoids a `parallel-modifies-overlap` DAG conflict without introducing an artificial dependency edge between unrelated bugs. Within batch 1, cards 1-4 each touch a distinct, non-overlapping section of `mill-merge-in/SKILL.md` (Entry vs Step 5.5 vs Step 3.5) or a different file entirely (`mill-merge/SKILL.md`), so sequential per-card commits within the batch never collide.
- **Applies to:** all batches.

### Decision: SKILL.md procedure edits carry `verify: null`

- **Decision:** Batches 1 and 2 (pure SKILL.md/CLAUDE.md doc-and-procedure edits, no executable Python surface) set `verify: null` at both the frontmatter and per-card level. Batch 3 (the one genuine Python code change) carries a real `verify:` command and is the task's sole TDD candidate.
- **Rationale:** Per `_mill/discussion.md`'s Testing section, four of the five bugs are orchestration-procedure/doc fixes with no directly executable unit under test — verification is re-reading the rendered SKILL.md sections for internal consistency after editing, which mill-go's implementer/reviewer already do as part of normal card completion. Writing synthetic tests or integration fixtures for these would be disproportionate churn for one-off doc fixes (see discussion.md Scope/Out).
- **Applies to:** batch 1 (`mill-merge-in-parent-and-baseline`), batch 2 (`mill-finalize-discussion-citation-scan`).

### Decision: ASCII-only in new printed/logged text

- **Decision:** Any new operator-facing print/warning text added by this plan (batch 1 card 4's background-dispatch log lines, batch 2 card 5's citation-scan warning) uses ASCII only — no em-dashes, no arrows other than `->`.
- **Rationale:** Repo-wide convention (`CLAUDE.md` Conventions: "`print()` / `_log()` output: ASCII only... Windows cp1252 crashes on non-ASCII stdout"), already followed by every existing `millpy-bg`/verify-gate print site this plan's cards reference as their pattern source.
- **Applies to:** all batches.

## All Files Touched

- `CLAUDE.md`
- `plugins/codeguide/scripts/resolve_scope.py`
- `plugins/codeguide/unit_tests/test-resolve-scope.py`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
