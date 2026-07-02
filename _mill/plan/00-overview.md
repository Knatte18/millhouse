# Plan: Fix agent-mode dispatch races and pipeline gaps

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
slug: agent-mode-gaps
approved: false
started: "20260702-094611"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: status-baseline-field
    file: 01-status-baseline-field.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
  - number: 2
    name: verify-gates-baseline-param
    file: 02-verify-gates-baseline-param.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
  - number: 3
    name: implement-baseline-stage
    file: 03-implement-baseline-stage.md
    depends-on: [1, 2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-status.py
  - number: 4
    name: mill-go-agent-dispatch-fixes
    file: 04-mill-go-agent-dispatch-fixes.md
    depends-on: [3]
    verify: null
  - number: 5
    name: merge-in-baseline-recompute
    file: 05-merge-in-baseline-recompute.md
    depends-on: [3]
    verify: null
  - number: 6
    name: baseline-integration-test
    file: 06-baseline-integration-test.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-verify-baseline.py
  - number: 7
    name: nits-only-carveout
    file: 07-nits-only-carveout.md
    depends-on: []
    verify: null
  - number: 8
    name: receiving-review-reword
    file: 08-receiving-review-reword.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: source-of-truth is `_mill/discussion.md`

- **Decision:** Every batch that edits prose (mill-go/SKILL.md, mill-merge-in/SKILL.md, mill-start/SKILL.md, mill-plan/SKILL.md, mill-receiving-review/SKILL.md, the fixer-brief templates) includes `_mill/discussion.md` in its `Context:` list. The Decisions section of that file (specifically the `stopped/interrupted-notification liveness probe (#587, #595)`, `baseline-aware module-wide verify gate (#590)`, `fixer-brief nits-only carve-out (#592)`, and `reword "before reading" to "before evaluating or acting" (#593)` subsections) is the authoritative source for exact wording, rationale, and line-number targets. Cards below give the concrete edit instructions distilled from it; when a card's Requirements and `_mill/discussion.md` appear to differ on a fine point, `_mill/discussion.md` wins.
- **Rationale:** The discussion went through 8 review rounds resolving concrete mechanism bugs (transient-worktree dependency reuse, junction-strip-before-remove, baseline eager-vs-lazy timing, NITS_ONLY token feasibility, `--stage baseline` argparse ordering). Re-deriving that reasoning from scratch in each card risks losing a already-fixed subtlety.
- **Applies to:** all batches.

### Decision: reuse existing `_worktree` / `_junction` helpers for the baseline transient worktree

- **Decision:** The baseline computation (batch 3) creates its transient worktree via a direct `git worktree add <tmp-path> <parent_sha>` call (detached, no new branch — `_worktree.create` always does `-b <branch>` and does not fit this shape) but tears it down via the existing `_worktree.remove_safe(path, cwd, junctions_cfg={})` helper (`plugins/mill/scripts/_worktree.py:180-276`), which already strips junctions before `git worktree remove` with a long-path fallback — this is exactly the CLAUDE.md junction-strip-first invariant the discussion's Constraints section calls for, already implemented and tested. Junction creation for the reused `.venv`/`venv`/`node_modules`/`vendor` dependency dirs uses the existing `_junction.create(target, link_path)` helper (`plugins/mill/scripts/_junction.py:174`).
- **Rationale:** `_worktree.remove_safe` and `_junction.create` already implement exactly the safety behavior the discussion's Constraints section requires (junction-strip-before-remove, long-path fallback). Hand-rolling a parallel implementation would duplicate tested logic and risk missing an edge case `remove_safe` already handles (e.g. the Windows long-path fallback).
- **Applies to:** `implement-baseline-stage` (batch 3).

## All Files Touched

- `plugins/mill/integration_tests/test-verify-baseline.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-receiving-review/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-status.py`
