# Plan: Post-merge teardown: keep PR notes, remove checkpoint branches

```yaml
task: 'Post-merge teardown: keep PR notes, remove checkpoint branches'
slug: merge-teardown-hygiene
approved: false
started: '20260926-085141'
parent_branch: main
discussion_sha: fb638e03b3de2f46479bf62b346c98efd1ba1828
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: helpers-and-cleanup
    file: 01-helpers-and-cleanup.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-finalize-cleanup.py test-cleanup.py
  - number: 2
    name: skill-text
    file: 02-skill-text.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-guards.py
```

## Shared Decisions

### Decision: checkpoint naming

- **Decision:** the checkpoint branch for task branch `B` is `mill-checkpoint-` plus `B` with every `/` replaced by `-`, matching `mill-merge-in`'s `tr '/' '-'`.
  The Python helper is the single source for this rule on the script side.
- **Rationale:** cleanup must delete exactly the name merge-in created.
- **Applies to:** all batches

### Decision: pr-notes travel via a slug-specific scratch file and an explicit flag

- **Decision:** `mill-finalize` copies the task dir's pr-notes file to `.scratch/pr-notes-<slug>.md` before cleanup and passes `--pr-notes <path>` to `git-pr`, which appends it to the PR body and deletes it after PR creation succeeds.
  The source file always overwrites an existing scratch copy; a missing or empty source keeps an existing scratch copy.
- **Rationale:** `_mill/` must keep being removed at cleanup; `.scratch/` is gitignored, and the explicit flag prevents a stale file from attaching to an unrelated PR.
- **Applies to:** all batches

### Decision: failures of checkpoint deletion are non-fatal

- **Decision:** a missing checkpoint is success; any other git failure is logged (ASCII) and ignored, never halting merge-in or cleanup.
- **Rationale:** matches the existing tolerant `branch -D` handling in cleanup.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_finalize_cleanup.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/skills/git-pr/SKILL.md`
- `plugins/mill/skills/mill-finalize/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-finalize-cleanup.py`
