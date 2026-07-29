MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (Anthropic)
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [BLOCKING] Debounced health-check pull can exceed `_ensure_daemon`'s 1.0s reuse-probe timeout
**Location:** Batch 1 / Card 2 (`_handle_health` in `wiki/_server.py`)
**Issue:** `_ensure_daemon()` (`wiki/_client.py:643-649`) probes an existing daemon with `_connect_send_recv(state["host"], state["port"], req, timeout=1.0)` where `req`'s op is `OP_HEALTH` — and since `read_timeout` is left `None`, the socket keeps the 1.0s timeout for `recv()` too (`_connect_send_recv`, `wiki/_client.py:706-748`). Card 2's new `_handle_health` can now block for up to `_GIT_NETWORK_TIMEOUT_SECONDS` (30.0s, `wiki/_sync.py:35`) servicing that very request whenever the `_HEALTH_CHECK_PULL_TTL` (60s) window has elapsed. Because `_dispatch()` calls `_ensure_daemon()` before *every* op (not just explicit `health_check()` calls), this means roughly once every 60 seconds of continued wiki usage, the reuse-probe will reliably time out waiting on its own request, fall through to `_spawn_server()`, and race a redundant daemon spawn against the still-busy original — at best wasted subprocess churn (the redundant spawn self-exits via `_claim_state_file`'s staleness check), at worst a `WikiStartupError` if `wait_for_socket_reachable` doesn't recover within `SPAWN_TIMEOUT` (10-20s) while the original daemon is still mid-pull. This directly undermines the batch's own goal (#730/#737 accurate health-check messaging) by making the daemon's *own* reuse mechanism spuriously flaky.
**Fix:** Either exempt the reuse-probe's `OP_HEALTH` dispatch from the new pull logic (e.g. a payload flag distinguishing "liveness probe" from "full health check"), or give `_ensure_daemon`'s probe a read timeout comfortably above `_GIT_NETWORK_TIMEOUT_SECONDS`, or bound the debounced pull's own timeout well under the probe's 1.0s budget. Card 2 as written does not reconcile these two numbers.

### [NIT] `capsys` suggested for a non-pytest test harness
**Location:** Batch 1 / Card 4 (`test-wiki-health-check.py`)
**Issue:** Requirements say to assert the Card 3 stderr log line "e.g. via `capsys`/subprocess stderr capture." `capsys` is a pytest fixture; this repo's unit tests are plain `test-*.py` scripts invoked directly (`run-all.py` does `subprocess.run([sys.executable, str(test)], ...)`, no pytest runner anywhere in `unit_tests/`), and `pytest` isn't even a declared dependency in `plugins/mill/pyproject.toml`. `capsys` is not usable in this harness.
**Fix:** Drop the `capsys` option; specify the actual mechanism (e.g. redirect `sys.stderr` to an `io.StringIO` around the call, matching this file's real harness).

## Verdict

REQUEST_CHANGES
Card 2's debounced pull latency is unreconciled with `_ensure_daemon`'s hardcoded 1.0s reuse-probe timeout.
MILL_REVIEW_END
