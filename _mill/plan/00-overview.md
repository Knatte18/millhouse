# Plan: mill-plan: entry-gate, timeline, and script-portability bugs

```yaml
task: 'mill-plan: entry-gate, timeline, and script-portability bugs'
slug: mill-plan-entry-gate-and-misc-bugs
approved: true
started: 20260904-101521
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: mill-plan-discussion-drift-and-interpreter-naming
    file: 01-mill-plan-discussion-drift-and-interpreter-naming.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py test-guards.py
  - number: 2
    name: mill-start-fork-guardrail
    file: 02-mill-start-fork-guardrail.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py test-guards.py test-brief-commit.py
```

## Shared Decisions

### Decision: source issues #914/#938/#919/#939, only two need code changes

- **Decision:** This task closes four filed bugs (#914, #938, #919, #939), all already fixed in a sibling repo/branch. Investigation during discussion showed this repo's copies of `mill-plan/SKILL.md` and `mill-start/SKILL.md` have since diverged independently: #914 (plan-review-r{N} timeline rows) is already fixed here — `mill-plan/SKILL.md`'s "Unconditional round-recorded append" step (Phase: Plan Review) already appends `plan-review-r{N}` before branching into any verdict, for every genuinely-reviewed round, regardless of which of 4a/4b/4c/4d subsequently fires. No batch exists for #914 — it is verification-only. #938 and #939 are both still live in `mill-plan/SKILL.md` and are batch 1. #919 is still live in `mill-start/SKILL.md` and is batch 2.
- **Rationale:** Planning against artifacts that are already fixed would either be a no-op (harmless but wasteful) or, worse, risk reintroducing the old asymmetry by touching working code "to be safe." Confirmed by reading the current file rather than trusting the issue text alone.
- **Applies to:** all batches (scopes what is and isn't in this plan).

### Decision: `pipeline.done_gate` left `null`

- **Decision:** `done_gate` is left `null` in this overview's frontmatter, not set to a lint command.
- **Rationale:** Per mill-plan's "Done-gate reminder," the candidate lint command (`uvx ruff check .`) was run against the current worktree tip from `git_root` before defaulting to it, per that section's own pre-check requirement. It exited 1 with 1950 pre-existing findings, entirely unrelated to this task's two prose-only SKILL.md edits. Making this task's `done` gate depend on unrelated repo-wide lint debt would block every future task in the hub on a pre-existing condition this task did not create and its batches do not touch.
- **Applies to:** all batches.

### Decision: verify scope is the SKILL.md-prose-scanning unit tests only

- **Decision:** Both batches' `verify:` targets `test-skill-helper-drift.py` and `test-guards.py` (plus `test-brief-commit.py` for batch 2, since it also scans `mill-start/SKILL.md`) via `run-all.py --only`, not the full 77-file suite.
- **Rationale:** Both batches are pure prose edits to `SKILL.md` files — no Python source changes. `test-skill-helper-drift.py` asserts every `_<module>.<fn>(` reference in these files resolves to a real shipped function (both batches introduce only references to functions already used elsewhere in the same file: `_status.set_blocked`, `_status.append_phase`, `git -C ... rev-parse` via Bash, direct-`Edit` for frontmatter — no new helper functions). `test-guards.py` catches anti-patterns (stray `->` in test files, `cd .wiki`, unguarded venv checks) that a careless prose edit could otherwise introduce. `test-brief-commit.py` locks `mill-start/SKILL.md`'s `_mill/briefs/` commit-message patterns, which batch 2's edit sits near but does not touch — included as cheap, directly-relevant insurance. This matches mill-plan's "Verify command scope" guidance: target only tests affected by the batch's `Edits:`.
- **Applies to:** batch 1, batch 2.

## All Files Touched

- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
