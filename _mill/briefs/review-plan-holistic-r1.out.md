I have enough to complete the review. All plan claims verified against source: the `_dispatch` retry loop structure, `_ensure_daemon` idempotency, the `MILL_FINALIZE_PR_CLEANUP` env-var guard in git-pr, the mill-setup token-walk pattern, `_extract_frontmatter`/`_scan` in millpy-skills-index.py, `_print_task_brief` in millpy-wiki-migrate.py, and the `importlib.util.spec_from_file_location` + `ok()`/`fail()` harness patterns in test-abandon.py (which contains the identical harness, so cards 6/8 have it in-Context despite naming test-wiki-client-retry.py).

MILL_REVIEW_BEGIN
# Review: Fix daemon health-check race, finalize env-var delivery, skills-index drop, and encoding crash — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-02
```

## Findings

### [NIT] Card 2 omits the load-bearing WIKI_DAEMON_INPROCESS="" patch
**Location:** Batch 1 (daemon-respawn-on-retry) / Card 2
**Issue:** All 8 existing tests wrap the retry-loop assertions in `patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""})`; without it `_dispatch` takes the in-process branch and never reaches the retry loop, so the new cases (a)/(b)/(c) would silently not exercise Card 1's code. The card lists every other patch explicitly but not this one (only "follow the existing pattern" implies it).
**Fix:** Add the `patch.dict(os.environ, {"WIKI_DAEMON_INPROCESS": ""})` context to the explicit patch list for all three new cases.

### [NIT] Card 1 respawns pointlessly on the final attempt
**Location:** Batch 1 / Card 1
**Issue:** Re-invoking `_ensure_daemon()` "before the existing sleep/raise logic" means on `attempt == 3` (ConnectionRefusedError) a respawn fires immediately before `raise WikiBusyError`, with no subsequent connect — wasted work, and a final-attempt `WikiStartupError` would mask the `WikiBusyError`. Harmless but slightly off.
**Fix:** Optional — gate the respawn on `attempt < 3` so the terminal attempt just raises `WikiBusyError`.

## Verdict

APPROVE
Plan is complete, source-grounded, DAG-clean, and numbering-consistent; two NITs only.
MILL_REVIEW_END