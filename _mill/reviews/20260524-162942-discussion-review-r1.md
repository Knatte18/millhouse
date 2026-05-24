# Review: Adopt V3 wiki module in V2 scripts

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-24
```

## Findings

### [GAP] millpy-wikipush.py broken by _wiki.py deletion
**Section:** Scope — Out / delete-v2-wiki-layer decision
**Issue:** The discussion marks `millpy-wikipush.py` as "left as-is — out of scope" and separately decides `_wiki.py` is deleted outright. But `millpy-wikipush.py:32` has `import _wiki`, and lines 111–113 call `_wiki.wiki_lock` and catch `_wiki.LockBusy`. Deleting `_wiki.py` breaks this script at import time.
**Fix:** Add `millpy-wikipush.py` to scope for one change only: drop the `_wiki` import and remove the `wiki_lock` / `LockBusy` call sites (replace the lock guard with a bare call to `_push_inner`). Push logic stays on direct git subprocess.

### [NOTE] CAS retry count ambiguous — 5 vs 3
**Section:** Scope — `_spawn_core.groom_and_claim_merge`
**Issue:** Discussion says the retry loop uses "5 attempts, identical to the existing integration-test pattern in `test-wiki-e2e.py`." But `_client.py:40` exports `CAS_RETRIES = 3` and the test hard-codes `max_retries = 5` locally.
**Fix:** State explicitly which count governs `groom_and_claim_merge` and whether `CAS_RETRIES` will be updated to match.

### [NOTE] health_check impl after OP_READ removal not stated
**Section:** Scope — `wiki/_client.py`
**Issue:** Current `health_check` in `_client.py:170` sends `OP_READ` with an empty path. After `OP_READ` is removed, `health_check` must switch to `OP_HEALTH`, but the discussion does not say so.
**Fix:** Add one line: "Update `health_check` to send `OP_HEALTH` instead of `OP_READ`."

### [NOTE] Migration script bypasses public upsert_task without explanation
**Section:** Technical context — Migration script anatomy, step 4
**Issue:** The migration script calls `wiki._client._ensure_daemon` directly and sends raw `OP_UPSERT_TASK` with a `status` field, while the public `upsert_task(slug, title, brief, body, group)` wrapper (Scope, millpy-add.py replacement) has no `status` parameter. The bypass is necessary but unstated.
**Fix:** Either add `status` to the public `upsert_task` signature, or note explicitly that the migration script intentionally uses the internal `_ensure_daemon` + `_connect_send_recv` path because it is the only caller that needs to seed legacy status values.

## Verdict

GAPS_FOUND
`millpy-wikipush.py` will break on import when `_wiki.py` is deleted — scope must cover removing its advisory-lock usage.