# Batch: Unit tests

```yaml
task: V3 wiki module with daemon and in-process cache
batch: Unit tests
number: 6
cards: 5
verify: "PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-store.py && PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-protocol.py && PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-daemon.py && PYTHONPATH=plugins/mill/scripts python plugins/mill/unit_tests/test-wiki-sync.py"
depends-on: [5]
```

## Batch Scope

Writes four unit test files covering the pure logic of the wiki module. Tests follow the existing unit test style in `plugins/mill/unit_tests/` — standalone scripts that print `PASS`/`FAIL` per case and exit 0 on all-pass, non-zero on any failure. No pytest, no real daemon socket or process except in `test-wiki-sync.py` which uses a real tempfile git repo (bare remote + working clone). Each test file is self-contained and runnable via `PYTHONPATH=plugins/mill/scripts python <file>`.

Batch-local decision: `test-wiki-sync.py` requires git to be available on PATH. This is acceptable for the unit test tier because real git in a tempfile repo is fast (sub-second) and produces deterministic results.

Batch-local decision: `run-all.py` — `test-wiki-store.py`, `test-wiki-protocol.py`, and `test-wiki-daemon.py` are added to `run-all.py` (they satisfy the in-memory/tempfile constraint). `test-wiki-sync.py` is excluded from `run-all.py` because it uses real git subprocess calls, violating the "no real git" constraint documented in the unit test README. It is covered by the batch verify command instead.

## Cards

### Card 7: `test-wiki-store.py` — cache logic tests

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-store.py`
- **Deletes:** none
- **Requirements:**
  Use `_test_helpers` patterns for pass/fail tracking. Cover: (1) `Store.get` on empty store returns `None`; (2) `Store.set` then `Store.get` returns `(content, hash)` where hash equals `Store.content_hash(content)`; (3) `Store.invalidate` removes the entry (subsequent get returns None); (4) `Store.invalidate` on absent key is no-op (no exception); (5) `Store.invalidate_all` clears all entries; (6) `Store.content_hash` is SHA-256 of UTF-8 content (verify against `hashlib.sha256("hello".encode()).hexdigest()`); (7) Two stores are independent instances (setting in one does not affect the other); (8) Non-ASCII content (e.g. Norwegian `"Nær"`) survives `set` + `get` round-trip with correct hash.
- **Commit:** `test(wiki): add test-wiki-store.py unit tests for Store cache`

### Card 8: `test-wiki-protocol.py` — JSON protocol and exception mapping tests

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-protocol.py`
- **Deletes:** none
- **Requirements:**
  Cover: (1) Read request round-trip: build `{FIELD_OP: OP_READ, FIELD_TOKEN: "t", FIELD_PATH: "Home.md"}`, JSON-encode, JSON-decode, assert fields survive; (2) Write request: build with `FIELD_FILES` mapping (`{FIELD_BASE_HASH: ..., FIELD_NEW_CONTENT: ...}`), encode/decode, assert fields survive; (3) Success response envelope: `{FIELD_OK: True, FIELD_CONTENT: "x", FIELD_HASH: "y"}` — assert `resp[FIELD_OK]` is True; (4) Error response envelope: `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_NOT_FOUND, FIELD_ERROR: "Home.md"}` — assert `resp[FIELD_ERROR_TYPE] == ERR_NOT_FOUND`; (5) CONFLICT envelope uses `ERR_CONFLICT`; (6) AUTH error envelope uses `ERR_AUTH`; (7) `PROTOCOL_VERSION` is `1` (integer). These are pure dict/JSON tests — no network calls.
- **Commit:** `test(wiki): add test-wiki-protocol.py JSON protocol envelope tests`

### Card 9: `test-wiki-sync.py` — git operations tests

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-sync.py`
- **Deletes:** none
- **Requirements:**
  Set up a real tempfile bare repo + working clone in a `tempfile.mkdtemp()` dir (clean up in finally). Initialize: `git init --bare <bare>`, `git clone <bare> <clone>`, configure `user.email` and `user.name` in clone (`git -C <clone> config ...`), commit an initial `Home.md`. Cover: (1) `pull(clone)` on up-to-date returns False (or True if the implementation always returns False — accept whichever the implementation defines for "already up to date"); actually just verify it does not raise; (2) `atomic_write` writes content to a file at a relative path inside the clone, content readable back via `(clone / rel_path).read_text("utf-8")`; (3) `commit_push(clone, ["Home.md"], "test commit")` after writing a change to `Home.md` succeeds and `git -C bare log --oneline` shows the commit; (4) `commit_push` when nothing changed (file content identical to HEAD) succeeds without creating a new commit (nothing-staged is idempotent success); (5) Non-fast-forward rebase-retry: push a commit to bare from a second clone, then call `commit_push` from the first clone — assert it raises `WikiPushError` or succeeds after rebase (depending on whether the changes conflict); (6) `path_guard("")` raises `WikiPathError`; `path_guard("../escape")` raises `WikiPathError`; `path_guard("/absolute")` raises `WikiPathError`; `path_guard("Home.md")` does not raise; `path_guard("subdir/file.md")` does not raise.
- **Commit:** `test(wiki): add test-wiki-sync.py git operations unit tests`

### Card 10: `test-wiki-daemon.py` — daemon base logic tests

- **Context:**
  - `plugins/mill/scripts/_daemon.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Deletes:** none
- **Requirements:**
  All tests use tempfile dirs; no real TCP socket or accept loop. Cover: (1) `_write_state_file(path, data)`: call it, read back the JSON, assert fields match; (2) `_is_stale` returns True when given a state dict with `pid=os.getpid()+999999` (non-existent PID) — call the method directly on a `DaemonBase` subclass instance; (3) `_is_stale` returns False when given a state dict with `pid=os.getpid()` (current process); (4) O_EXCL claim: `open(path, 'x')` succeeds once; second `open(path, 'x')` raises `FileExistsError` — assert this is the correct behavior (not testing `DaemonBase.run()`, just the O_EXCL primitive); (5) Idle-timeout computation: elapsed > idle_timeout triggers exit — test the predicate `(time.monotonic() - last_activity) > idle_timeout` with injected values; (6) `.gitignore` idempotent: write a `.gitignore` with `.wiki-daemon.json` already present; call a standalone helper that checks and appends missing entries; verify the file still has exactly one occurrence of `.wiki-daemon.json` after a second call. For (2) and (3), subclass `DaemonBase` with a trivial `handle_request` so it can be instantiated.
- **Commit:** `test(wiki): add test-wiki-daemon.py daemon base logic tests`

### Card 11: `run-all.py` — register wiki unit tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-wiki-store.py`
  - `plugins/mill/unit_tests/test-wiki-protocol.py`
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
- **Edits:**
  - `plugins/mill/unit_tests/run-all.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  `run-all.py` currently discovers tests via `HERE.glob("test-*.py")` with no exclusion mechanism. Adding `test-wiki-sync.py` to the directory would auto-include it, violating the no-real-git constraint. Fix: add a `SKIP: frozenset[str] = frozenset({"test-wiki-sync.py"})` constant near the top of `run-all.py`, and change the discovery line from `sorted(HERE.glob("test-*.py"))` to `sorted(p for p in HERE.glob("test-*.py") if p.name not in SKIP)`. `test-wiki-store.py`, `test-wiki-protocol.py`, and `test-wiki-daemon.py` are NOT listed in `SKIP` — they are automatically discovered and run. No other changes to `run-all.py`.
- **Commit:** `test(wiki): register wiki unit tests in run-all.py (excluding test-wiki-sync)`

## Batch Tests

Run all five with `PYTHONPATH=plugins/mill/scripts`:
```
python plugins/mill/unit_tests/test-wiki-store.py
python plugins/mill/unit_tests/test-wiki-protocol.py
python plugins/mill/unit_tests/test-wiki-daemon.py
python plugins/mill/unit_tests/test-wiki-sync.py
```
All four standalone tests must exit 0. `run-all.py` must also pass with the three new tests included. The verify command in the frontmatter chains the four standalone tests with `&&`.
