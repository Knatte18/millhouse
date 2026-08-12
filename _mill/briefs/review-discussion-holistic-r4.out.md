MILL_REVIEW_BEGIN
# Review: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude (Sonnet 5, exact model ID claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] "round: 0 fix" discards already-discovered round_n at finalize outer catch
**Section:** Decisions § "round: 0 fix"
**Issue:** The uniform rule "`round=args.round if args.round is not None else 0` at every call site" is applied to `millpy-review-plan.py`'s finalize-stage outer `except ReviewError` (line 308) and `millpy-review-discussion.py`'s equivalent (line 246) — but by that point `round_n` has already been resolved via `discover_round(reviews_dir, ...)` when `args.round` was `None` (plan: lines 269-274; discussion: lines 211-216), and is in scope at the catch with zero extra I/O. Using `args.round` there instead of the already-known `round_n` throws away exactly the "discoverable from disk" case the Problem section names, at the one site (post-`resolve_blocking_classes`-failure, per the "error_kind bucketing" Decision's own example) where that case is most likely to actually fire. The Rejected note ("calling `discover_round()` from the error path... adds filesystem I/O") does not apply here since the discovery already happened before the try block, not inside the error path.
**Fix:** Amend the "round: 0 fix" Decision to use the in-scope `round_n` (not raw `args.round`) at each finalize-stage outer catch specifically, while keeping `args.round`-or-`0` coalescing for every pre-finalize site that has no `round_n` variable; `millpy-review-code.py` is unaffected (its finalize stage requires `--round`, so `args.round` is already the only available value there).

## Verdict

REQUEST_CHANGES
The round:0 fix's uniform-args.round rule silently discards an already-in-scope disk-discovered round at the finalize outer catch.
MILL_REVIEW_END
