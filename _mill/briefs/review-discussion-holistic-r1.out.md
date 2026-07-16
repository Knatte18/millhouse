MILL_REVIEW_BEGIN
# Review: Unhandled exceptions in mill-go orchestration components should degrade gracefully

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [NOTE] Other bare-connect sites hit the same daemon
**Section:** Problem #2 / Decision "Remove the redundant bare-connect probe"
**Issue:** Two sibling sites in `wiki/_client.py` also connect-then-close with zero bytes to the same daemon: `wait_for_socket_reachable` (L124-125, post-spawn) and `_is_stale` (L799-800, stale path); the discussion attributes the empty-payload noise to the single `_ensure_daemon` probe.
**Fix:** Note that these two are purposeful reachability checks (not redundant like the `_ensure_daemon` probe) and remain intentionally, relying on the `_daemon.py` debug downgrade to keep their empty-payload connections benign.

### [NOTE] Malformed-nonempty payload no longer gets a response
**Section:** Decision "_handle_connection empty/malformed-payload handling"
**Issue:** Today's outer `except Exception` sends a `server_error` response (L156-163) even on a parse failure; the new JSONDecodeError branch closes without responding, which the rationale justifies only for the zero-byte case ("client that sent no bytes is not waiting for one") — a real client sending malformed-but-nonempty JSON may be awaiting a reply.
**Fix:** Explicitly acknowledge that dropping the response for malformed-nonempty payloads is intended (the only known sender is the empty probe), so a plan writer does not preserve the old sendall.

## Verdict

APPROVE
Thorough, source-grounded, decisions well-justified; two non-blocking notes on scope framing.
MILL_REVIEW_END
