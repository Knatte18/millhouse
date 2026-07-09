# Plan: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability

```yaml
task: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability
slug: mill-start-and-baseline-tooling-gaps
approved: true
started: 20260709-131233
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: mill-skill-entry-and-note
    file: 01-mill-skill-entry-and-note.md
    depends-on: []
    verify: null
  - number: 2
    name: baseline-longpath
    file: 02-baseline-longpath.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-verify-baseline.py
  - number: 3
    name: dotnet-noise
    file: 03-dotnet-noise.md
    depends-on: []
    verify: null
  - number: 4
    name: goimports-halt
    file: 04-goimports-halt.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: batches are independent and parallel

- **Decision:** All four batches touch disjoint file sets, so every batch is a DAG root (`depends-on: []`). The only file edited by two cards is `plugins/mill/skills/mill-start/SKILL.md` (cards 1 and 2), and both live in batch 1 — no cross-batch file overlap exists.
- **Rationale:** These are six unrelated reliability gaps bundled for convenience; sequencing them would only slow the run. Batch 1 co-locates the two mill-start cards so no two batches write the same file in parallel.
- **Applies to:** all batches

### Decision: doc-only batches are verified by review, not by a test runner

- **Decision:** Batches 1, 3, and 4 edit `SKILL.md` / `CLAUDE.md` prose only and carry `verify: null`. There is no automated test that asserts SKILL instruction content (the existing `test-skills-index.py` / `test-skill-helper-drift.py` check index/helper consistency, not Entry ordering or prose rules), so a runtime verify would be theatre. Correctness is established by the plan reviewer and, at merge time, human read-through.
- **Rationale:** Honest `verify: null` with a stated reason beats a green check that proves nothing.
- **Applies to:** mill-skill-entry-and-note, dotnet-noise, goimports-halt

### Decision: ASCII-only in Python source and comments

- **Decision:** The only code batch (baseline-longpath, batch 2) must keep any added comment/string ASCII-only (`->` not the arrow glyph, `--` not em-dash) per the repo's cp1252-safe stdout rule.
- **Rationale:** Non-ASCII stdout crashes on Windows cp1252.
- **Applies to:** baseline-longpath

### Decision: core.longpaths is applied per-invocation, never to global config

- **Decision:** The long-path fix passes `-c core.longpaths=true` on the single `git worktree add` invocation only. It is never written to any persistent git config, and the worktree teardown is left unchanged (its existing `safe_rmtree` fallback already covers long-path deletion).
- **Rationale:** Scoped, reversible, zero blast radius on the shared `_worktree.remove_safe` helper.
- **Applies to:** baseline-longpath

## All Files Touched

- `CLAUDE.md`
- `plugins/csharp/skills/csharp-build/SKILL.md`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/skills/git-commit/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-verify-baseline.py`
