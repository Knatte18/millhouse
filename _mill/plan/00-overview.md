# Plan: Handle pre-closed and pre-merged PRs gracefully in mill-merge

```yaml
task: "Handle pre-closed and pre-merged PRs gracefully in mill-merge"
slug: mill-merge-pr-state-awareness
approved: false
started: "20260630-143720"
parent: "main"
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
    name: pr-state-helper
    file: 01-pr-state-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-pr-state.py
  - number: 2
    name: cleanup-refactor
    file: 02-cleanup-refactor.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanup.py test-pr-state.py
  - number: 3
    name: mill-merge-skill
    file: 03-mill-merge-skill.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

### Decision: single-pr-query-source

- **Decision:** After this task, exactly one implementation of the `gh pr list`
  query exists: `_pr_state.resolve_pr_state(branch, cwd)` in
  `plugins/mill/scripts/_pr_state.py`. Both `mill-merge` (via a SKILL.md inline
  `python -c` snippet) and `millpy-cleanup.py:_apply_pr_reap_record` call it. No
  other code constructs a `gh pr list` argv.
- **Rationale:** De-duplicates the query and guarantees consistent
  precedence/normalization across the two callers (discussion Constraint
  "Single source of truth for the PR query").
- **Applies to:** all batches

### Decision: normalized-state-precedence

- **Decision:** `resolve_pr_state` queries
  `gh pr list --head <branch> --state all --json state,mergeCommit,number,url`
  (NO `--jq '.[0]'`), parses the full JSON **array**, and returns a dict
  `{"state": <s>, "number": <int|None>, "url": <str|None>, "merge_commit": <dict|None>}`
  where `<s>` is one of `"merged"`, `"open"`, `"closed"`, `"none"`. With multiple
  PRs on one head branch, precedence is **MERGED > OPEN > CLOSED**. `"none"`
  covers no-PR, `gh` missing, non-zero exit, empty stdout, and malformed JSON.
  `merge_commit` preserves gh's raw `mergeCommit` **object** (carrying `.oid`),
  never a flattened string.
- **Rationale:** A branch can accumulate several PRs; "did the work merge?" must
  win over a stale CLOSED. `"none"` collapses every "can't determine" case to the
  single silent-fallback branch. The raw `mergeCommit` object keeps
  `_apply_pr_reap_record`'s `(merge_commit or {}).get("oid")` fallback working
  (discussion Decisions/normalized-state-precedence, cleanup-adopts-precedence).
- **Applies to:** all batches

### Decision: ascii-and-cwd-discipline

- **Decision:** `_pr_state.py` runs `gh` via `_subprocess_util.run(..., cwd=<git
  root / hub root passed by caller>)`, never `cwd=<wiki>`. All stdout/log text is
  ASCII only (` -- `, ` -> `; no em-dash/unicode arrows). The helper is a flat
  `_*.py` module in `scripts/` with a module + function docstring per Python
  conventions.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII; wiki-cwd is banned
  by repo path invariants; the caller owns the cwd so the helper stays
  context-free (discussion Technical context, CLAUDE.md conventions).
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_pr_state.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/unit_tests/test-pr-state.py`
