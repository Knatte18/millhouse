All 5 cards of batch `plan-review-wiring` (cards 6-10) are complete and committed: 5 of 5 cards committed, matching the batch's declared card count. Verify passes except for a confirmed pre-existing, unrelated `test28` failure (reproduced identically on `main`).

Files touched:
- `/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter/plugins/mill/scripts/_review_plan.py` — wired `DisplayRoots` into all four prompt-assembly sites (`_review_one_batch`, both `prepare()` blocks, `run()`'s holistic block) and both NEED_CONTEXT resume-retry `build_reattached_section` call sites.
- `/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter/plugins/mill/unit_tests/test-review-plan-flow.py` — added tests 53-61 asserting plan-relative prompt content at each site, in bulk and tool-use modes, plus NEED_CONTEXT re-attachment.

{"status":"success","commit_sha":"3b637a73cce4ba0ddffed0e28d29d477c9a7f6e8","session_id":"b26ed942-856e-4f08-8f05-dc20fc69862b","cards_done":[6,7,8,9,10]}
