# Batch: wiki-client-retry

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: wiki-client-retry
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-client-retry.py
depends-on: []
```

## Batch Scope

Delivers transient-connection-error retry for the wiki daemon client
(issues #404, #407). The single change is in `wiki/_client._dispatch`,
the chokepoint every public client op funnels through, so it covers
`set_phase`, `merge_tasks`, `upsert_*`, `get_task`, etc. No external
interface changes; the function's signature and `WikiBusyError` contract
are unchanged. Self-contained -- touches only `wiki/_client.py` and a new
test file.

## Cards

### Card 1: Retry transient connection errors in `_dispatch`

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_dispatch` (the retry loop around
  `_connect_send_recv`, currently `except TimeoutError:`), widen the caught
  exceptions to also include `ConnectionResetError` and
  `ConnectionRefusedError` (WinError 10054 / 10061). Keep the existing
  `backoff_sleeps = [2, 4, 8]` schedule and the 4-attempt budget; on
  exhaustion still raise `WikiBusyError` with the same message shape
  (mentioning the `op`). Do NOT widen to bare `OSError` -- only the two
  named transient subclasses plus `TimeoutError`. Behavior on success and
  on a single transient-then-success must return the daemon response.
- **Commit:** `fix(wiki-client): retry transient connection resets/refusals in _dispatch`

### Card 2: Unit test for `_dispatch` retry

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-wiki-protocol.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-client-retry.py`
- **Deletes:** none
- **Requirements:** Monkeypatch `_client._connect_send_recv` (and
  `time.sleep` to a no-op) to assert: (a) a `ConnectionResetError` raised
  once then a successful response -> `_dispatch` returns the response after
  one retry; (b) same for `ConnectionRefusedError`; (c) persistent
  `ConnectionRefusedError` across all attempts -> raises `WikiBusyError`;
  (d) a non-retryable error (e.g. `ValueError`) propagates without retry.
  Follow the existing test style in `test-wiki-protocol.py`. Resolve a
  dummy `wiki_path` without touching a real socket or daemon.
- **Commit:** `test(wiki-client): cover _dispatch transient-error retry`

## Batch Tests

`verify:` runs the new `test-wiki-client-retry.py` only -- the change is
confined to `_dispatch`. The test stubs the socket boundary
(`_connect_send_recv`) and `time.sleep`, so it is fast and hermetic.

Ordering: Card 2 Creates `test-wiki-client-retry.py`, which the `verify:`
`--only` flag requires on disk. mill-go runs `verify:` once at batch end
(after all cards in the batch are implemented and committed), so the file
is present when verify runs -- implement both cards before the batch's
verify, never run the `--only` command against a half-built batch.
