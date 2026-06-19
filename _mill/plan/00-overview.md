# Plan: Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch

```yaml
task: "Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch"
slug: mill-config-and-brief-gaps
approved: false
started: 20260619-111549
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches._

```yaml
batches:
  - number: 1
    name: config-git-namespace
    file: 01-config-git-namespace.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py
  - number: 2
    name: brief-commit-uniformity
    file: 02-brief-commit-uniformity.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py test-gitignore-phase.py
```

## Shared Decisions

### Decision: orchestrator-layer brief commits (not CLI-layer)

- **Decision:** Dispatch briefs (`_mill/briefs/*.md` + `*.out.md`) are committed by the orchestrator SKILLs alongside other `_mill/` artifacts via `git add _mill/briefs/`, never by a new commit inside the dispatch CLIs.
- **Rationale:** Matches the operator directive ("follow the same setup as everything else committed in `_mill/`") and the already-shipped pattern in mill-go (SKILL lines 270/343/638/678) and mill-plan (lines 166/168/190/199). `git add _mill/briefs/` captures both the brief and its `.out.md` response in one pathspec.
- **Applies to:** brief-commit-uniformity

### Decision: guard the briefs add only where a brief may be absent

- **Decision:** Use `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi` only at commit sites reachable without a brief having been written (mill-start Handoff via the review-skip path; mill-start `--auto` halt-commits; mill-merge-in's trailing commit on a clean merge). At sites where a brief always exists by construction (mill-start step 4b / step 5, after a review round), add `_mill/briefs/` unconditionally.
- **Rationale:** `git add _mill/briefs/` errors "did not match any files" when the dir is absent. `--ignore-unmatch` is rejected (silent and non-uniform with the existing mill-go/mill-plan steps).
- **Applies to:** brief-commit-uniformity

### Decision: register git namespace via a populated template block

- **Decision:** Register `git` and its three known subkeys (`parent-branch`, `require_pr_to_base`, `base_branch`) in the schema-of-record (`plugins/mill/templates/mill-config.yaml`) with behavior-no-op defaults, rather than a validator allowlist.
- **Rationale:** `_config.walk_unknown_keys` uses the template dict as the schema; a populated block registers the keys, self-documents them, and preserves typo-detection for any other `git.*` key.
- **Applies to:** config-git-namespace

### Decision: per-batch verify scoping

- **Decision:** Each batch's `verify:` targets only the tests its edits affect (`--only` lists), prefixed with `PYTHONPATH= ` (Python project, enforced by `verify-not-isolated`).
- **Rationale:** The full suite is multi-minute; verify runs after every implementer/fixer round.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-brief-commit.py`
- `plugins/mill/unit_tests/test-config.py`
