Confirmed: `prepare()` is a pure render with no status writes or commits — only reads and prompt rendering plus a `discover_round` call. Removing the redundant `prepare()` call from finalize is safe; it has no side effects beyond rendering (which finalize discards). The plan correctly identifies `reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)` as the exact value prepare returns (line 204). And `round_n` was `discover_round(reviews_dir, ...)` — the envelope `--round` matches.

I have all the verification I need. The plan is accurate, signatures match, decisions are consistently applied, DAG is valid, step numbering is sequential. Let me check one final edge: the discussion finalize change — `--max-rounds` is currently passed to `prepare()`. After removal, the `--max-rounds` round-cap enforcement that prepare did (lines 67-72 of `_review_discussion.py`) no longer runs in finalize. But that cap check is a prepare-stage concern; finalize just writes the review. This is fine and intended.

Now I'll compose the review.

```
MILL_REVIEW_BEGIN
# Review: Fix agent-pipeline reliability gaps in finalize/success contract — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-09
```

## Findings

### [NIT] discussion-review --max-rounds becomes dead in finalize
**Location:** Batch 2 / Card 5
**Issue:** Removing the `prepare()` call from `millpy-review-discussion.py` finalize drops the round-cap enforcement (`_review_discussion.prepare` lines 67-72) that `--max-rounds` previously triggered there; the arg is now silently inert in finalize.
**Fix:** Optional — note in the card that `--max-rounds` is intentionally a prepare-only concern in finalize, so a future reader does not mistake the unused arg for a bug.

### [NIT] Card 8 mock list omits read_branch/status_path specifics
**Location:** Batch 4 / Card 8
**Issue:** `millpy-fix.py` finalize is reached before `_status.read_branch` (line 139, called with `cfg=`/`slug=` kwargs) and `_paths.status_path`/`resolve_task_path`; the mock list patches `_status.read_branch` but not `_paths`, so a real `resolve_task_path` runs before the finalize early-return.
**Fix:** Confirm `millpy_fix._paths` calls (status_path, resolve_task_path) tolerate the temp fixture cwd, or add them to the patch set so Tests 1/2 reach the finalize branch cleanly.

## Verdict

APPROVE
Signatures, decisions, DAG, and step numbering all verified against source; only minor test-robustness nits.
MILL_REVIEW_END
```
