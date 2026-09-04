# Plan: mill-start: discussion-review timeline gaps and stray orch-review.md scratch file

```yaml
task: 'mill-start: discussion-review timeline gaps and stray orch-review.md scratch file'
slug: mill-start-discussion-review-timeline-and-orch-review-hygiene
approved: true
started: 20260904-101002
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-hygiene-fixes
    file: 01-review-hygiene-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py test-brief-commit.py test-orch-review-scratch-path.py
```

## Shared Decisions

### Decision: gap-fix-timeline-label

- **Decision:** The `mill-start` interactive Phase: Discussion Review step 5 gap-fix round appends the phase label `discussion-gap-fix-r{N}` to `status.md`'s Timeline (distinct from step 4b's `discussion-fix-r{N}`).
- **Rationale:** `plugins/mill/unit_tests/test-phase-wait.py` and `mill-go-base/SKILL.md`'s "Entry-gate wait for upstream mill-plan" section already hard-code and test for exactly this pattern (`^discussion-gap-fix-r\d+$`) as a distinct, already-anticipated phase string. It is the only label that makes that existing consumer's pattern reachable.
- **Applies to:** review-hygiene-fixes (Card 1).

### Decision: gap-fix-commit-pathspec

- **Decision:** `<status_path>` is added to step 5's final commit pathspec, producing `git -C <worktree> add <discussion_path> <reviews_dir>/ _mill/briefs/ <status_path> && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`.
- **Rationale:** The phase-append (`gap-fix-timeline-label`, above) writes to `status.md`; the append must land in the same commit as the discussion/review changes it's paired with, matching step 4b's existing four-pathspec pattern (`<discussion_path>`, `<reviews_dir>/`, `<status_path>`, `_mill/briefs/`).
- **Applies to:** review-hygiene-fixes (Card 1).

### Decision: orch-review-scratch-location

- **Decision:** The `--orch` hand-off file moves from `<worktree>/_mill/orch-review.md` to `<worktree>/.scratch/orch-review.md`, in both the write side (`orch-review/SKILL.md`) and the read side (`orch-wait/SKILL.md`).
- **Rationale:** `.scratch/` is gitignored (`**/.scratch/` per the hub `.gitignore`), so `git status --porcelain` never reports it as untracked — this removes the file from `_cleanliness.compute_scope_violations()`'s consideration by construction rather than depending on every consumer remembering to delete it, and matches `mill:conversation`'s "Plugin-managed scratch" convention.
- **Applies to:** review-hygiene-fixes (Card 2, Card 3).

### Decision: atomic-write-read-path-change

- **Decision:** The write-side (`orch-review/SKILL.md`) and read-side (`orch-wait/SKILL.md`) path edits ship as a single card with one commit, never as two separately-committable cards.
- **Rationale:** A mismatched write path vs. read path (e.g. write-side updated but read-side still polling the old `_mill/` location) would silently break the entire `--orch` hand-off mechanism. This is the "genuinely atomic — must land together or not at all" case the plan Principles call out explicitly.
- **Applies to:** review-hygiene-fixes (Card 2).

## All Files Touched

- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/orch-review/SKILL.md`
- `plugins/mill/skills/orch-wait/SKILL.md`
- `plugins/mill/unit_tests/test-orch-review-scratch-path.py`
