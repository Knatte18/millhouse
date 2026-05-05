# Batch: wiki-lock-unification

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
batch: wiki-lock-unification
cards: 8
verify: uv run --project "plugins/mill" python "plugins/mill/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

This batch refactors `_wiki.py`'s lock subsystem so wiki helpers own the advisory lock instead of leaving it to callers, and migrates every call site to the new API. It subsumes three folded bugs: #27 (asymmetric `acquire_lock` / `release_lock` signatures), #82 (stale lock on uncaught exception), and the 2026-04-28 wiki-concurrency bug (`Cannot fast-forward to multiple branches` when two `mill-*` invocations overlap). The external interface that B04 / B05 / B06 will consume is the new shape: `_wiki.sync_pull(wiki_path, *, slug)`, `_wiki.write_commit_push(wiki_path, paths, msg, *, slug)`, and `with _wiki.wiki_lock(wiki_path, slug):` for multi-op windows. The old public `_wiki.acquire_lock` / `_wiki.release_lock` symbols are removed entirely; their work is now module-private.

Batch-local decisions (in addition to Shared Decisions):

- **Re-entrancy mechanism:** module-level `_held_locks: dict[Path, int]` counter (keyed by `wiki_path.resolve()`). `wiki_lock.__enter__` increments; if counter was 0, it calls `_acquire`. `__exit__` decrements; if counter drops to 0, it calls `_release`. `sync_pull` and `write_commit_push` check `_held_locks.get(resolved_path, 0)`: if > 0 they skip both `_acquire` and `_release`, otherwise they bracket the operation with `try/finally`.
- **Stale-self-lock detection:** `_acquire` reads the existing lockfile's holder slug. If holder slug equals the caller's `slug`, log a one-line stderr warning (`[wiki] _acquire: reclaiming self-lock held by {slug!r}`) and overwrite the lockfile immediately. Stale-by-age detection (5 min threshold) is preserved alongside.
- **Caller `slug` source:** explicit. Every caller passes the slug it knows about. `mill-cleanup` uses literal `"mill-cleanup"`; `_spawn_core` operations pass the slug they are about to claim or are operating on; `mill-claim` / `mill-spawn` pass the slug being claimed (or `"mill-spawn"` literal for the early discovery sync).

## Cards

### Card 1: Add `wiki_lock` context manager + held-lock counter + stale-self-lock detection

- **Reads:**
  - `plugins/mill/scripts/_wiki.py`
- **Modifies:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Requirements:** Add module-level `_held_locks: dict[Path, int] = {}` keyed by resolved wiki path. Add `wiki_lock(wiki_path: Path, slug: str)` context manager (use `contextlib.contextmanager` or write a class with `__enter__` / `__exit__`). On enter: resolve the path, increment counter; if counter was 0 call the new private `_acquire(wiki_path, slug)`. On exit (including exception path): decrement counter; if counter drops to 0 call `_release(wiki_path)`. Refactor the existing public `acquire_lock` body into a module-private `_acquire(wiki_path: Path, slug: str, timeout_seconds: int = 30) -> None`; refactor `release_lock` body into `_release(wiki_path: Path) -> None`. In `_acquire`, after reading the existing lockfile, if `holder == slug` (the caller's own slug), print `[wiki] _acquire: reclaiming self-lock held by {slug!r} (age {age_seconds}s)` to stderr and overwrite the lockfile immediately (do NOT wait for timeout). Preserve the existing 5-minute stale-by-age detection. Update the module docstring to describe the new public surface (`wiki_lock`, `sync_pull(slug=...)`, `write_commit_push(slug=...)`) and to remove references to the deleted `acquire_lock` / `release_lock`. Keep `LockBusy` and `WikiPushError` exposed as before.
- **Commit:** `feat(_wiki): add wiki_lock context manager + held-lock counter + stale-self-lock`

### Card 2: Migrate `sync_pull` and `write_commit_push` to take required `slug` kwarg and acquire/release internally

- **Reads:**
  - `plugins/mill/scripts/_wiki.py`
- **Modifies:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Requirements:** Change `sync_pull` signature to `sync_pull(wiki_path: Path, *, slug: str) -> None`. Change `write_commit_push` signature to `write_commit_push(wiki_path: Path, relative_paths: list[str], commit_msg: str, *, slug: str) -> None`. Inside both: resolve the wiki path; check `_held_locks.get(resolved, 0)` — if > 0 just run the existing operation body; if 0 wrap the body in `try: _acquire(wiki_path, slug); ...; finally: _release(wiki_path)`. The "nothing to commit" early-return in `write_commit_push` must run inside the `finally`-released window so the lock is released even on no-op commits. Update the module docstring's "Public API" block to reflect the new signatures and the auto-locking behaviour. Do NOT remove the existing `acquire_lock` / `release_lock` symbols yet — Card 4 does that after Card 3 migrates callers.
- **Commit:** `feat(_wiki): sync_pull/write_commit_push acquire wiki lock internally`

### Card 3: Migrate all script callers of the wiki lock-API

- **Reads:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/millpy-add.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/millpy-spawn.py`
- **Modifies:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/millpy-add.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Requirements:** In every caller, delete the explicit `_wiki.acquire_lock(...)` / `_wiki.release_lock(...)` calls and the surrounding `try/finally` boilerplate. Add `slug=<value>` kwarg to every `_wiki.sync_pull(wiki_path)` and `_wiki.write_commit_push(wiki_path, paths, msg)` call. **Multi-op sequences (read Home.md → transform → `write_commit_push`) must be wrapped in `with _wiki.wiki_lock(wiki_path, <slug>):` — the nested `write_commit_push` inside will skip re-acquiring via the re-entrancy counter. The following functions perform multi-op atomic windows and require this treatment:** (a) `_spawn_core.claim_in_wiki(wiki_path, slug)` — wrap the full body in `with _wiki.wiki_lock(wiki_path, slug):`; (b) `_spawn_core.multi_select_groom_then_claim(wiki_path, ...)` — same treatment; (c) `millpy-add.main()` around line 170–204 — wrap the read→modify→write_commit_push sequence in `with _wiki.wiki_lock(wiki_path, args.slug):`; (d) `millpy-cleanup.main()` around lines 423, 443, 463 — wrap each read→modify→write_commit_push sequence in `with _wiki.wiki_lock(wiki_path, "mill-cleanup"):`. **For bare standalone `sync_pull` calls not currently surrounded by explicit locks, just add `slug=`:** `millpy-claim.py:179` uses `slug="mill-claim"` (early sync before any slug is picked); `millpy-spawn.py:119` uses `slug="mill-spawn"` (same reason); `millpy-abandon.py:94-103` uses local `slug`. **Also fix `millpy-claim.py:310-317`:** the call `_spawn_core.write_initial_status(wiki_path=wiki_path, ...)` passes the wrong kwarg — the function signature is `write_initial_status(worktree_path: Path, ...)`. Change to `_spawn_core.write_initial_status(worktree_path=git_root, ...)`. After this card lands, no script outside `_wiki.py` references `_wiki.acquire_lock` / `_wiki.release_lock`.
- **Commit:** `refactor(scripts): migrate wiki callers to internal-locking helpers`

### Card 4: Remove public `acquire_lock` and `release_lock`; clean up module surface

- **Reads:**
  - `plugins/mill/scripts/_wiki.py`
- **Modifies:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Requirements:** Delete the public `acquire_lock` and `release_lock` definitions from `_wiki.py`. The module-private `_acquire` and `_release` (added in Card 1) remain, used only by `wiki_lock`, `sync_pull`, and `write_commit_push`. Remove the matching entries from the module docstring's "Public API" block (Card 1 already did the docstring rewrite, but if any stale lines remain, clean them up). Run `grep -rn "_wiki\.acquire_lock\|_wiki\.release_lock"` across `plugins/mill/` and confirm Card 3 plus the SKILL.md prose / test-mock cards have removed every external call site before this card lands. If any remain, halt — Card 4 must be the final step in the helper migration so the surface change lands atomically with the callers.
- **Commit:** `refactor(_wiki): remove public acquire_lock/release_lock`

### Card 5: Update SKILL.md prose for `mill-merge` and `mill-start` to use the new lock-API

- **Reads:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Requirements:** In `mill-merge/SKILL.md` Step 7 (around line 175–183, "Home.md — mark `[done]`"): replace the four-step explicit acquire / read / set_phase / commit / release sequence with a `with _wiki.wiki_lock(wiki_path, slug):` block enclosing the read → set_phase → write_commit_push trio. The `set_phase` call inside continues to use the text helper for now (Card 19 in B04 will switch mill-go's Handoff to `set_phase_at`; mill-merge stays on the text helper because the prose already shows the read+write explicitly — leaving mill-merge unchanged on this point keeps B01 scope tight). In `mill-start/SKILL.md` Board discipline section (around line 105): rewrite the line that currently says "Home.md writes go through `_wiki.write_commit_push` with the shared lock held (see `_wiki.acquire_lock` / `_wiki.release_lock`)" to instead say: "Home.md writes go through `_wiki.write_commit_push` (which acquires the wiki lock internally). For multi-operation windows, use `with _wiki.wiki_lock(wiki_path, slug):`." Remove every reference to the deleted `_wiki.acquire_lock` / `_wiki.release_lock` symbols in both files.
- **Commit:** `docs(mill-merge,mill-start): update lock-API prose`

### Card 6: Update existing unit-test mocks for the new wiki-API signatures

- **Reads:**
  - `plugins/mill/unit_tests/test-abandon.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-abandon.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Requirements:** Remove every mock of `_wiki.acquire_lock` and `_wiki.release_lock` (e.g. `wm.acquire_lock = lambda *a, **k: None` in `test-abandon.py:69`). Update mocks of `_wiki.sync_pull` and `_wiki.write_commit_push` to accept the new `slug` kwarg signature (most existing mocks use `lambda *a, **k: None` or `Mock()` and already accept arbitrary kwargs — verify this and tighten any that don't). The CLI / script tests should still pass run-all.py after Card 4 + Card 6 land together.
- **Commit:** `test(unit): update wiki-API mocks for new signatures`

### Card 7: Add `test-wiki.py` — unit tests for the new lock subsystem

- **Reads:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki.py`
- **Requirements:** Create `test-wiki.py` covering: (a) `wiki_lock` context manager acquires and releases the lockfile in the trivial case; (b) re-entrancy — nested `with wiki_lock(p, slug):` does not deadlock and does not delete the lockfile until the outer exits; (c) inside a `wiki_lock` window, `sync_pull` and `write_commit_push` do NOT acquire/release — assert this by checking `import _wiki; assert _wiki._held_locks[resolved_path] == 1` (use the `_held_locks` counter directly; it is deterministic regardless of OS timing); (d) outside any `wiki_lock` window, `sync_pull` and `write_commit_push` acquire/release on their own (assert lockfile is gone after the call); (e) stale-self-lock detection — pre-create a lockfile with `holder == caller's slug`, call `_acquire`, assert it returns immediately (no 30s wait) and the lockfile is overwritten with the new acquire's contents; (f) release on exception — call `write_commit_push` with a path that triggers a `WikiPushError` (e.g. patch `_subprocess_util.run` to return non-zero on `git add`), assert the exception propagates AND the lockfile is gone. Use `tempfile.TemporaryDirectory` for the wiki dir; patch `_subprocess_util.run` for the git operations. Follow `test-status.py`'s structural style (in-memory fixtures, no real git, no real subprocess).
- **Commit:** `test(unit): add test-wiki.py for new lock subsystem`

### Card 8: Update integration tests — `test-merge.py` migration + new `test-wiki-concurrency.py` + `test-bootstrap.ps1` comment

- **Reads:**
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
  - `plugins/mill/integration_tests/test-spawn.py`
- **Modifies:**
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
- **Creates:**
  - `plugins/mill/integration_tests/test-wiki-concurrency.py`
- **Requirements:** In `test-merge.py:299-314`: replace the explicit `_wiki.acquire_lock(wiki, slug)` / `_wiki.release_lock(wiki)` pair with `with _wiki.wiki_lock(wiki, slug):` enclosing the existing `write_commit_push` calls; add `slug=` kwarg to every `_wiki.write_commit_push` and `_wiki.sync_pull` call inside the test. In `test-bootstrap.ps1:191`: update the comment that mentions "acquire_lock / release_lock" to reflect the new API surface (helpers own the lock; `wiki_lock` is the multi-op context manager). Create `test-wiki-concurrency.py` that spawns two subprocess calls to `_wiki.sync_pull(wiki, slug='proc-A')` and `_wiki.sync_pull(wiki, slug='proc-B')` against the same wiki clone (use `subprocess.Popen` with the live `git` binary; the test fixture initialises a real local wiki repo via `git init`); assert both succeed in turn (the second waits for the first's lock; total wall time approximates 2× single-call time, never crashes on FETCH_HEAD). This test is the 2026-04-28 regression gate. It lives under `integration_tests/` so it is opt-in (not run by `run-all.py`); document its invocation pattern in a top-of-file docstring.
- **Commit:** `test(integration): migrate test-merge to wiki_lock + add test-wiki-concurrency`

## Batch Tests

`verify:` runs the full unit-test suite via `run-all.py`. New `test-wiki.py` exercises the lock subsystem end-to-end with `tempfile` + patched `_subprocess_util.run`. Updated test mocks (Card 6) keep the existing CLI/script tests green after the API signature change. The integration `test-wiki-concurrency.py` (Card 8) is the regression gate for the 2026-04-28 bug; it is not part of `run-all.py` (it requires a real `git` binary) but the operator runs it manually before B01 ships. The mill-go / mill-plan integration tests are unaffected because no public-surface behavioural change happens — only the call shape (callers pass `slug=`).
