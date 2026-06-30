# Batch: cleanup-refactor

```yaml
task: "Handle pre-closed and pre-merged PRs gracefully in mill-merge"
batch: cleanup-refactor
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanup.py test-pr-state.py
depends-on: [1]
```

## Batch Scope

Refactor `millpy-cleanup.py:_apply_pr_reap_record` to obtain PR state from the
batch-1 helper `_pr_state.resolve_pr_state` instead of constructing its own
`gh pr list ... --jq '.[0]'` query, and update the three existing PR-reap tests
in `test-cleanup.py` whose mocks return the old single-object form. The refactor
and the test update share one card because the batch `verify:` runs
`test-cleanup.py`: the refactor changes the mocked gh response shape from a
single object to an array, so the tests would fail at the card boundary unless
both files change together. Multi-PR behavior intentionally changes (precedence
now wins over gh recency); the function still finalizes only on `merged` and its
archive-tag target is unchanged (overview Shared Decisions; discussion
Decisions/cleanup-adopts-precedence, cleanup-tag-target-unchanged).

## Cards

### Card 2: Route `_apply_pr_reap_record` through `_pr_state` and fix test mocks

- **Context:**
  - `plugins/mill/scripts/_pr_state.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `millpy-cleanup.py`, add `import _pr_state` to the existing imports.
  - In `_apply_pr_reap_record`, replace the inline `_subprocess_util.run(["gh",
    "pr", "list", ... "--jq", ".[0]"], cwd=hub_root)` call plus the
    `result.returncode != 0 or not result.stdout.strip()` guard and the
    `json.loads(result.stdout.strip())` block with a single call:
    `pr = _pr_state.resolve_pr_state(record.branch, hub_root)`. Then set
    `state = pr["state"]`, `merge_commit = pr["merge_commit"]`,
    `number = pr["number"]`.
  - The branch checks must use the helper's **lowercase** normalized states:
    `state == "none"` takes the former gh-failed/empty early-return (keep the
    existing `[cleanup] PR-reap {slug}: gh pr list failed ...`-style stderr
    message, reworded to "no PR / gh unavailable" since the helper no longer
    surfaces stderr); `state == "open"` keeps the "still OPEN -- skipping"
    stdout return; `state == "closed"` keeps the "CLOSED without merge -- inspect
    manually" stderr return; the final `state != "merged"` defensive guard
    remains. The MERGED teardown block (archive-tag creation via
    `git fetch origin <branch>` / `FETCH_HEAD`, the
    `(merge_commit or {}).get("oid")` fallback, `git tag`, `git push`,
    `wiki.set_phase(..., "done")`, mode-resolve, `_apply_*_record`) is unchanged
    — `merge_commit` is still the raw gh object so `.get("oid")` works.
  - Do NOT change the archive-tag target logic; cleanup keeps tagging
    `FETCH_HEAD`/merge-SHA (overview Shared Decisions: precedence is unified, the
    tag target is not).
  - In `test-cleanup.py`, update the three PR-reap mocks
    (`_mock_run_18a` MERGED ~line 836, `_mock_run_18b` OPEN ~line 926,
    `_mock_run_18c` CLOSED ~line 992) so the `if "gh" in argv and "pr" in argv`
    branch returns the gh **array** form instead of a single object — wrap each
    existing object in a list and add a `url` field, e.g.
    `'[{"state": "MERGED", "mergeCommit": {"oid": "abc123"}, "number": 42,
    "url": "https://example/pr/42"}]'`. Keep every existing assertion (MERGED ->
    archive tag created + Home.md `[done]` + worktree removed; OPEN -> no-op;
    CLOSED -> stderr reports CLOSED + slug, no teardown) — they must still pass
    unchanged, proving the refactor preserves single-PR behavior.
  - Confirm no other callsite in `millpy-cleanup.py` reads `pr_data`/`state`
    from the removed inline block (grep the function body; the local names
    `state`, `merge_commit`, `number` are reused so downstream lines need no
    change).
- **Commit:** `refactor(mill): route cleanup PR-reap through _pr_state helper`

## Batch Tests

`verify` runs `run-all.py --only test-cleanup.py test-pr-state.py`.
`test-cleanup.py` covers the refactored `_apply_pr_reap_record` via its three
updated PR-reap cases (MERGED/OPEN/CLOSED) plus the rest of the cleanup suite;
`test-pr-state.py` is re-run to confirm the helper contract the refactor relies
on still holds. Both use mocked `_subprocess_util.run`; no real gh/git.
