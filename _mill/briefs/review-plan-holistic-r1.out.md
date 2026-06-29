I have everything needed to evaluate the plan against the source. My verification confirms:

- Batch Index DAG: three batches, all `depends-on: []`, files all present, no cycle.
- Global card numbering 1-6: unique, sequential, no gaps.
- Verify shape: batches 1/2 begin with `PYTHONPATH= `, batch 3 is `verify: null` (doc-only) — correct for this Python project. `run-all.py` does support `--only` (lines 49-69).
- Batch 1's claim that `test-agents-defs.py` is unaffected is correct — that test only validates the two `agents/*.md` files, not registry contents. The naming-convention test (which would break) lives in `test-reviewers.py` and is in the batch verify scope. New `opus`/`sonnet`/`_bulk` entries satisfy all five of its rules.
- Card 4's `_is_go_main_artifact` design (`git ls-files "*.go"`, `Path(go_file).parent.name == basename`, `package main` check) is sound; pathlib handles git's posix separators on Windows.
- Card 6: `git branch -f "$CHK"` is legal since checkpoint branches are never checked out; the mill-merge consumer (resets to `mill-checkpoint-<name>`) is left unchanged and the force-refresh only makes the ref more correct.
- All Shared Decisions are faithfully implemented.

One minor inaccuracy found.

MILL_REVIEW_BEGIN
# Review: Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-29
```

## Findings

### [NIT] Card 2 cites tests that don't assert "Unknown reviewer"
**Location:** Batch 1 / Card 2
**Issue:** Requirements states the existing `test_load_raises_*` and `validate_role_refs` tests "assert on substring 'Unknown reviewer'", but none in `test-reviewers.py` do — those tests assert on load-validation strings and on the reviewer name (e.g. `does-not-exist`, `typo-reviewer`).
**Fix:** Reword to "tests that assert on the reviewer name / the `Unknown reviewer:` prefix remain satisfied since the prefix is unchanged"; the substantive instruction (preserve `{name!r}` prefix) is already correct, so no behavioral change.

## Verdict

APPROVE
Plan is complete, decisions implemented, scoping and verify commands correct; only a cosmetic prose inaccuracy.
MILL_REVIEW_END