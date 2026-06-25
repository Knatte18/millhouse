MILL_REVIEW_BEGIN
# Review: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-25
```

## Findings

### [BLOCKING] Card 5 names a nonexistent `branch` field on `read_status`
**Location:** Batch 2 / Card 5
**Issue:** The card says to use "the task branch read from the status.md `branch:` field already loaded into `info` (`_status.read_status`)", but `_status.read_status` returns only `{phase, task, current_batch, last_timeline_entry, blocked_reason}` (see `_status.py:604-610`) — `info["branch"]` does not exist, so the literal instruction yields a KeyError.
**Fix:** Direct the implementer to read the branch via `_status.read_branch(status_path, cfg=cfg, slug=slug)` (or `read_full(...)["yaml"]["branch"]`); the value is in the file, just not on `read_status`.

### [BLOCKING] Card 11 test asserts a substitution the template lacks until Card 12
**Location:** Batch 3 / Card 11 (vs Card 12)
**Issue:** Card 11 adds `PARENT_BRANCH` to the render map and a `test-millpy-implement.py` test "asserting the rendered brief includes the `<PARENT_BRANCH>` substitution populated from the resolved parent," but the `<PARENT_BRANCH>` placeholder is only added to `implementer-brief.md` in Card 12. At Card 11's end the template has no `<PARENT_BRANCH>` token, so the rendered brief never contains the parent value and the asserted-substitution test cannot be green (Card 11 Edits also omit `implementer-brief.md`).
**Fix:** Either move the `implementer-brief.md` placeholder addition into Card 11 (add it to Card 11's Edits/Context), or scope Card 11's test to assert only that the render map contains `PARENT_BRANCH` (not that the rendered brief shows it), deferring the brief-text assertion to Card 12.

### [NIT] Card 9 verify-gate insertion point underspecified (5 call sites)
**Location:** Batch 3 / Card 9
**Issue:** `_run_verify_gate(project_root, verify_cmd)` is invoked at five places in `_implementer_common.py` (`_forward_output` lines 567, 691, 746, 802 plus `finalize_from_output`); the card says "after the existing batch-scoped gate returns success" without naming which of the success-emit paths must chain the module-wide gate, risking partial coverage (e.g. the formatter-drift and inferred-success paths).
**Fix:** Name the success-emit paths that must run the second gate, or factor a single helper both gates flow through, so no success path skips the module-wide check.

### [NIT] Card 11/12 omit `<PARENT_BRANCH>` from the brief's token-comment
**Location:** Batch 3 / Cards 11-12
**Issue:** `implementer-brief.md`'s leading token doc-comment enumerates every token; neither card adds `<PARENT_BRANCH>` to that list, leaving the template comment stale.
**Fix:** Have Card 12 (which edits the brief) add `<PARENT_BRANCH>` to the token comment block.

## Verdict

REQUEST_CHANGES
Two card-level factual/sequencing defects (wrong status field; test precedes its template change) block a clean green.
MILL_REVIEW_END
