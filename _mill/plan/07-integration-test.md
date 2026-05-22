# Batch: Integration test and docs

```yaml
task: V3 wiki module with daemon and in-process cache
batch: Integration test and docs
number: 7
cards: 2
verify: null
depends-on: [6]
```

## Batch Scope

Delivers the end-to-end integration test and a one-line CLAUDE.md update. The integration test exercises the full client-daemon-git stack: real TCP socket, real git, real subprocess spawn. It models `plugins/mill/integration_tests/test-wiki-concurrency.py`. The CLAUDE.md edit documents the `wiki/` subpackage exception to the "flat Python" rule. Both changes are purely additive — no existing code is modified except the one CLAUDE.md line.

## Cards

### Card 11: `test-wiki-e2e.py` — end-to-end integration test

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/integration_tests/test-wiki-concurrency.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-wiki-e2e.py`
- **Deletes:** none
- **Requirements:**
  Standalone script (no pytest). Prints `PASS`/`FAIL` per scenario, exits 0 on all-pass.

  **Setup** (in a tempfile dir, cleaned in finally): init bare repo, clone it, configure git user in clone, commit an initial `Home.md` with content `"# Home\n"`. Use a very short `idle_timeout=3` and `refresh_interval=0.5` for the daemon so the test completes in a reasonable time.

  **Scenario 1: Basic read-write**
  - Call `_client.read(clone, "Home.md", idle_timeout=3)` — daemon spawns transparently; assert returns `("# Home\n", <hash>)`.
  - Call `_client.write_commit_push(clone, {"Home.md": ("# Home\nLine 2\n", <hash>)}, "add line 2", idle_timeout=3)`.
  - Call `_client.read(clone, "Home.md", idle_timeout=3)` — assert content is `"# Home\nLine 2\n"`.
  - Call `_client.read(clone, "missing.md", idle_timeout=3)` — assert raises `WikiNotFoundError`.

  **Scenario 2: Concurrent CAS**
  Spawn two subprocesses that each do a read-modify-write on `Home.md`. Each subprocess: reads current content + hash, appends its own line, calls `write_commit_push`. At least one subprocess should either succeed outright or receive `WikiConflictError` and retry (re-read + re-call `write_commit_push`). The subprocess script: accept `wiki_path` as argv[1] and a line-label as argv[2]. Retry loop (up to 5 attempts): `content, hash_ = _client.read(...); new = content + f"{argv[2]}\n"; _client.write_commit_push(..., {"Home.md": (new, hash_)}, ...)`. Exit 0 on success, 1 on failure.

  Run both subprocesses with `subprocess.Popen`, collect with `proc.wait(timeout=30)`. Assert both exit 0. Read final `Home.md` via `_client.read(...)` — assert it contains both appended lines (order unspecified).

  **Scenario 3: Idle-exit and respawn**
  - Wait `idle_timeout + 2` seconds (5 seconds with `idle_timeout=3`). Assert state file `clone / ".wiki-daemon.json"` no longer exists (daemon idle-exited).
  - Call `_client.read(clone, "Home.md", idle_timeout=3)` — assert daemon respawns transparently and returns content successfully.

  **Scenario 4: health_check**
  - `assert _client.health_check(clone)` is True while daemon is up.

  Use `PYTHONPATH=plugins/mill/scripts` when spawning subprocess workers (same as the parent process's PYTHONPATH).

- **Commit:** `test(wiki): add test-wiki-e2e.py end-to-end integration test`

### Card 12: CLAUDE.md — record wiki subpackage exception

- **Context:**
  - `CLAUDE.md`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the `## Repo layout` section, find the bullet: `` `plugins/mill/scripts/` — flat Python (no submodules); `millpy-*.py` CLIs + `_*.py` helpers ``. Replace with: `` `plugins/mill/scripts/` — flat Python; `millpy-*.py` CLIs + `_*.py` helpers; `wiki/` subpackage is the deliberate V3 module exception; `_daemon.py` is a generic daemon base reusable by future V3 modules ``. Exactly one line changed; no other edits.
- **Commit:** `docs(CLAUDE.md): record wiki/ subpackage and _daemon.py as V3 exceptions to flat-Python rule`

## Batch Tests

`verify: null` — the integration test is long-running (daemon spawn + idle-exit wait) and not part of the automated verify cycle. Run manually to validate:
```
PYTHONPATH=plugins/mill/scripts python plugins/mill/integration_tests/test-wiki-e2e.py
```
CLAUDE.md change has no runnable verification.
