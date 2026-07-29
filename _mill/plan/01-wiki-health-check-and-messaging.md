# Batch: wiki-health-check-and-messaging

```yaml
task: "Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps"
batch: "wiki-health-check-and-messaging"
number: 1
cards: 5
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-health-check.py test-wiki-daemon.py test-wiki-client-retry.py"
depends-on: []
```

## Batch Scope

Closes #730 and #737 by giving the wiki daemon's `health_check()` real git-repo-validity and cross-machine-staleness checking, and by making failures surface an actual reason instead of a fixed generic string. This batch owns everything under `plugins/mill/scripts/wiki/` (the daemon's git-integration layer) plus the two `mill-go/SKILL.md` halt-message blocks that consume `health_check()`'s result. It does not touch `mill-resume/SKILL.md`'s own new `health_check()` call site — that's Batch 2 (`mill-resume-repair`), since it's part of the mill-resume repair feature and depends on nothing from this batch beyond the already-existing `health_check()` function signature (unchanged: `wiki_path: Path) -> bool`).

External interface this batch produces, consumed elsewhere: `wiki/_client.py`'s `health_check()` keeps its `-> bool` signature (no ripple into any other caller), but on a hard failure it now also prints `f"[wiki] health check failed: {reason}"` to stderr before returning `False`. Batch 2's mill-resume Phase 1 call site relies on this stderr line being present so its own halt message can point the operator at "the reason printed above."

## Cards

### Card 1: Extract `verify_git_repo()` from `commit_push()` in `wiki/_sync.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/unit_tests/test-wiki-sync.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `commit_push()` (`plugins/mill/scripts/wiki/_sync.py:180-225`) currently inlines a git-repo-validity check as its first block: a `subprocess.run(["git", "-C", str(wiki_path), "rev-parse", "--git-dir"], ...)` call with three `except`/`raise WikiPushError` branches (non-zero exit, `TimeoutExpired`, any other `Exception`). Extract this block verbatim into a new public function `verify_git_repo(wiki_path: Path) -> None` (place it above `commit_push()`, after `_run()`), raising the exact same `WikiPushError` messages on the exact same conditions (5.0s timeout unchanged). Update `commit_push()` to call `verify_git_repo(wiki_path)` as its first statement, replacing the inlined block — no behavior change, pure extraction. This lets `wiki/_server.py`'s `_handle_health()` (Card 2) reuse the identical check instead of duplicating it. Add module docstring's Public API list entry for `verify_git_repo(wiki_path)`. Extend `plugins/mill/unit_tests/test-wiki-sync.py` (which already uses a real tempfile bare-repo + clone fixture — see its existing `commit_push()` tests) with two new cases: `verify_git_repo()` raises `WikiPushError` when `wiki_path` has no `.git` (e.g. a plain empty tempdir); `verify_git_repo()` returns `None` without raising for a valid git clone fixture (adapt the inline bare-repo+clone setup pattern already used in that file's `main()`). Note: `plugins/mill/unit_tests/run-all.py` hardcodes `SKIP = frozenset({"test-wiki-sync.py"})`, so this file is never runnable via `run-all.py --only` (it is pre-existing, unrelated to this task) — this card's own new cases are verified by running the file standalone: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-sync.py` (see Batch Tests).
- **Commit:** `fix(wiki): extract verify_git_repo() from commit_push() for reuse by health_check`

### Card 2: `_handle_health()` — git-validity, debounced staleness fetch, hard/soft classification

- **Context:**
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_server.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite `_handle_health(self, payload)` (currently `plugins/mill/scripts/wiki/_server.py:295-297`, an unconditional `return {FIELD_OK: True}`) as follows. (0) Gate the entire new git-validity/staleness logic behind the same `WIKI_DAEMON_SKIP_GIT` check `_render_and_commit_all` already uses (`plugins/mill/scripts/wiki/_server.py:418`, `skip_git = os.environ.get("WIKI_DAEMON_SKIP_GIT") == "1"`): when `skip_git` is true, return `{FIELD_OK: True}` immediately, unchanged from today's behavior, without calling `verify_git_repo`/`pull` at all. This is required, not optional: `plugins/mill/unit_tests/_test_helpers.py`'s `init_wiki_repo()` — under the test suite's own `WIKI_DAEMON_SKIP_GIT=1` default — only `mkdir`s the wiki directory and never runs `git init`, so an unconditional `verify_git_repo()` call would hard-fail `OP_HEALTH` for the large majority of existing fixtures across the unit-test suite that never opted into real git; this dispatch is also reached internally by `_ensure_daemon()`'s own reuse-probe (`wiki/_client.py:643-649`, sent on every existing-daemon reuse check), so an unconditional failure would additionally flip that probe to always-false and trigger spurious respawns across the suite, not just in this batch's own new tests. `os` is already imported in this module. (1) When `skip_git` is false, import `verify_git_repo` alongside the existing `pull, atomic_write, commit_push` import at `plugins/mill/scripts/wiki/_server.py:36` (`from wiki._sync import pull, atomic_write, commit_push, verify_git_repo`). Call `verify_git_repo(self._wiki_path)` first; on `WikiPushError` return `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_PUSH_FAILED, FIELD_ERROR: str(e)}` — a missing/invalid `.git` directory is always a hard failure (per `discussion.md`'s `health-check-failure-semantics` decision). (2) When the git-validity check passes, debounce a fetch+ff-merge using the daemon's existing `self._last_pull` timestamp (`plugins/mill/scripts/wiki/_server.py:62`, already updated elsewhere in `_render_and_commit_all`) and `time` (already imported at line 5) — add a module-level constant `_HEALTH_CHECK_PULL_TTL = 60.0` near the top of the file (after imports). If `time.monotonic() - self._last_pull >= _HEALTH_CHECK_PULL_TTL`, call `pull(self._wiki_path)` inside a `try`/`except WikiPushError as e`; on success, set `self._last_pull = time.monotonic()`. Reuse the pre-existing field — do not add a second timestamp attribute. `_render_and_commit_all` (`plugins/mill/scripts/wiki/_server.py:421-433`) closes `self._store` before its own `pull()` call and reopens it in a `finally` block, with a comment explaining that TinyDB's open `tasks.json` file handle blocks git's working-tree checkout on Windows; this new debounced `pull()` call inside `_handle_health` must wrap itself in the identical `self._store.close()` / `try: pull(...) / finally: self._store.reload()` pattern (not just a bare `try`/`except WikiPushError`), so a health-check-triggered pull that actually updates `tasks.json` does not hit the same Windows lock failure. (3) On a `pull()` failure inside that try block, classify by message content: if `"fast-forward"` appears in `str(e).lower()` (git's own stderr for a failed `--ff-only`, e.g. `"Not possible to fast-forward, aborting."` — per `discussion.md`'s `wiki-pull-failure-classification` decision), treat it as a **hard failure** with the same `{FIELD_OK: False, FIELD_ERROR_TYPE: ERR_PUSH_FAILED, FIELD_ERROR: str(e)}` shape as the git-validity failure — a diverged local wiki needs manual resolution. Any other `WikiPushError` (network timeout, unreachable remote) is a **soft warning**: do not update `self._last_pull` on failure, and do not return a failure — fall through to the healthy return. (4) When the TTL window has not elapsed, or after a successful/soft-warned pull attempt, return `{FIELD_OK: True}`.
- **Commit:** `fix(wiki): _handle_health validates git repo and debounces staleness fetch`

### Card 3: `health_check()` logs the failure reason before returning `False`

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `health_check()` (`plugins/mill/scripts/wiki/_client.py:585-604`), after computing the response from the existing `resp = _dispatch(wiki_path, OP_HEALTH, {})` call, when `bool(resp.get(FIELD_OK))` is `False`, print the failure reason to stderr before returning: `print(f"[wiki] health check failed: {resp.get(FIELD_ERROR, '(no reason given)')}", file=sys.stderr)`. `sys` and `FIELD_ERROR` are already imported in this module. Keep the function's `-> bool` signature and its outer `except Exception: return False` unchanged (no reason to log there — the daemon itself is unreachable, there is no `resp` to read a reason from). Only the in-`try` hard-failure branch gains the log line.
- **Commit:** `fix(wiki): health_check logs the daemon-reported failure reason to stderr`

### Card 4: New unit test `test-wiki-health-check.py` — git-validity, staleness, debounce, hard/soft classification

- **Context:**
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/unit_tests/test-wiki-sync.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/test-fold.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-health-check.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** New test file using the existing in-memory/tempfile daemon harness (`WIKI_DAEMON_INPROCESS=1`, per `plugins/mill/unit_tests/_test_helpers.py` and `test-fold.py`'s established pattern — `wiki.use_inprocess(wiki_path)` keeps one `WikiServer` instance alive per wiki_path so `self._last_pull` state persists across calls within a test). This test needs real git pull behavior, so it must override `_test_helpers.py`'s `WIKI_DAEMON_SKIP_GIT` default: set `os.environ["WIKI_DAEMON_SKIP_GIT"] = ""` before importing `wiki._client`/`_test_helpers` (mirroring the documented override pattern in `_test_helpers.py`'s module docstring). Build fixtures with two real tempdir git repos — one configured as the `origin` remote of the other — adapting `test-wiki-sync.py`'s inline bare-repo+clone setup pattern as a reference. Cover: (a) wiki dir with no `.git` at all -> `_client.health_check()` returns `False` (assert the stderr log line from Card 3 is emitted, e.g. via `capsys`/subprocess stderr capture consistent with this file's harness). (b) local clone behind `origin` by one commit -> after calling `health_check()`, the local clone has fast-forwarded (assert via `git log`/`git rev-parse HEAD` inside the local clone matching `origin`'s tip). (c) debounce -- two `health_check()` calls within the `_HEALTH_CHECK_PULL_TTL` window trigger only one `pull()` invocation (assert via a call-count spy/mock patched onto `wiki._server.pull` specifically -- `wiki/_server.py` does `from wiki._sync import pull`, binding a local name, so only patching that local `wiki._server.pull` reference actually intercepts the call inside `_handle_health`; patching `wiki._sync.pull` has no effect on the already-bound reference). (d) diverged local wiki (local clone has a commit `origin` doesn't have, so `git pull --ff-only` fails with a "fast-forward" message) -> `health_check()` returns `False` (hard failure), distinct from (e) a simulated network-timeout `pull()` failure (patch `wiki._sync.pull` to raise `WikiPushError("git command timed out after 30s: ...")`) -> `health_check()` still returns `True` (soft warning) — covers `wiki-pull-failure-classification`'s message-content split end-to-end through the client.
- **Commit:** `test(wiki): add health_check git-validity, staleness, debounce, and hard/soft classification coverage`

### Card 5: `mill-go/SKILL.md` — soften both health-check halt messages

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update both halt-message blocks that follow a failed wiki health-check dispatch — `plugins/mill/skills/mill-go/SKILL.md:216` (inside "### 0. Wiki health-check") and `plugins/mill/skills/mill-go/SKILL.md:604` (the byte-identical Handoff-time duplicate, indentation differs since it sits inside a numbered list) — from the current unconditional `echo "[mill-go] HALT: no config source reachable -- re-run mill-setup if mill-config.yaml is missing" >&2` to: `echo "[mill-go] HALT: wiki daemon unreachable or unhealthy -- see the reason printed above; re-run mill-setup only if mill-config.yaml is confirmed missing" >&2`. Apply the identical wording change at both locations, preserving each block's existing surrounding indentation. This stops unconditionally implying `mill-setup` is the fix for every failure cause (a diverged or missing-`.git` wiki is not fixed by `mill-setup`) while still pointing operators at the daemon's own printed reason from Card 3's stderr log line.
- **Commit:** `docs(mill-go): stop presuming mill-setup fixes every wiki health-check failure`

## Batch Tests

`verify:` runs the four unit test files covering this batch's code changes: `test-wiki-sync.py` (Card 1's extracted `verify_git_repo`), `test-wiki-health-check.py` (Card 4, new — Cards 2+3's `_handle_health`/`health_check` behavior), and the two pre-existing `test-wiki-daemon.py`/`test-wiki-client-retry.py` files as a regression guard against `OP_HEALTH` dispatch/protocol behavior this batch touches indirectly. Card 5 (`mill-go/SKILL.md` text) has no automated test in this repo (skill markdown is not executed by a test harness) — verified by direct text review during code review instead.
