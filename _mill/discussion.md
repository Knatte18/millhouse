# Discussion: V3 wiki adoption follow-up bugs

```yaml
task: V3 wiki adoption follow-up bugs
slug: wiki-v3-followups
status: discussing
parent: main
```

## Problem

After the V3 wiki daemon (TinyDB + render-on-mutation) went live, six edge-case bugs
surfaced and were filed as GitHub issues during adoption. They are small individually but
share the same surface — the daemon + render pipeline in `plugins/mill/scripts/wiki/` and
the surrounding infrastructure helpers (`_junction.py`, `_safe_rmtree.py`,
`millpy-fix.py`). The bugs are cleared together before the next consumer depends on V3
behaviour. All six have concrete reproduction paths; none require speculative design work.

## Scope

**In:**
- `#382` — replace bare TCP connect ping with full `OP_HEALTH` exchange in `_ensure_daemon`
- `#383` — always call `_render_and_commit_all` in `_handle_remove_task`, even when the slug is absent
- `#384` — delete orphaned `proposal-<slug>.md` files in `_render_and_commit_all` when tasks are removed
- `#385` — `strip_all_in_worktree` scans the worktree root for all junctions (FS-level), not just config-declared ones
- `#366` — `_safe_rmtree.safe_rmtree` uses a chmod+retry callback instead of bare `ignore_errors`; three whitelisted test files converted to use `safe_rmtree`
- `#376` — `millpy-fix.py` detects Windows file-locking errors in `LLMError` and routes to `stuck_type: verify` instead of `transient`
- Unit tests for every changed path

**Out:**
- No changes to the daemon wire protocol or `OP_*` constants
- No changes to `_store.py`, `_parse.py`, `_sync.py`, or `_render.py` logic beyond orphan accounting
- No changes to `mill-go` SKILL.md or other stuck-type handling; `verify` is already handled
- No new stuck types
- No integration tests (unit tests suffice for these deterministic fixes)
- `_worktree.remove_safe` call-sites: already use `_junction.strip_all_in_worktree` correctly; the fix is in `strip_all_in_worktree` itself

## Decisions

### #382 — OP_HEALTH exchange replaces bare TCP ping

- **Decision:** In `_client.py::_ensure_daemon`, after a successful TCP connect to the state-file address, send `{FIELD_OP: OP_HEALTH, FIELD_TOKEN: token, "payload": {}}` with a 1.0s timeout. If the exchange raises `OSError`, times out, or returns `ok: False`, treat the state file as stale and fall through to respawn.
- **Rationale:** A bare `socket.create_connection` succeeds against any process that grabbed the recycled port. The `OP_HEALTH` exchange verifies our daemon specifically (the token is the discriminant). 1.0s is enough for a localhost JSON round-trip with a loaded machine; 0.5s risks false positives under load.
- **Rejected:** Increasing only the PID check — the PID check alone doesn't validate the port; another process can hold the same port as the PID correctly identifies a live process.

### #383 — _handle_remove_task always rerenders

- **Decision:** Move `_render_and_commit_all` outside the `if task is None` early-return path. The call order is: (1) check task existence, (2) if present remove it, (3) always call `_render_and_commit_all`, (4) return `ERR_NOT_FOUND` if the task was absent, `OK: True` if it was removed.
- **Rationale:** A prior partial failure can leave the store and rendered files inconsistent (e.g., task removed from TinyDB but `proposal-<slug>.md` not deleted). A re-attempt must reconcile, not silently no-op. `ERR_NOT_FOUND` is preserved so callers can distinguish idempotent "already gone" from "removed now".
- **Rejected:** Returning `OK: True` when task is absent — callers may use `ERR_NOT_FOUND` as an explicit signal that no mutation occurred.

### #384 — Orphan proposal files deleted in _render_and_commit_all

- **Decision:** In `_server.py::_render_and_commit_all`, before `atomic_write`, glob `wiki_path` for `proposal-*.md`, compute the orphan set (`existing_proposals - rendered.keys()`), call `os.remove` on each orphan, and include orphan paths in the `commit_push` call alongside the rendered files and `tasks.json`.
- **Rationale:** `render()` returns only files it generates; it has no access to the wiki path and cannot know about orphans. `_render_and_commit_all` owns both the rendered dict and the wiki path, making it the correct site. Deleting in the same commit as writing avoids a window where the wiki has inconsistent state.
- **Rejected:** Modifying `render()` to accept and return orphan information — `render()` is a pure function of tasks; passing on-disk state to it makes it impure and harder to test in isolation.

### #385 — strip_all_in_worktree uses FS-level scan

- **Decision:** Replace the config-driven loop in `strip_all_in_worktree` with a one-level scan of `worktree_path` using `os.scandir`. For every immediate child that is a junction or symlink (via `_is_junction_or_symlink`), call `_junction.remove`. Return the list of stripped paths. The `junctions_cfg` parameter is retained for the function signature to avoid breaking callers but is no longer iterated.
- **Rationale:** Old worktrees have `.active` (and in some cases `.portals`) at the root, which are not in the current config defaults. Config-driven stripping misses them, causing `git worktree remove --force` to fail with "Directory not empty". An FS scan is self-healing and immune to future config changes. Junctions live only at the worktree root, so a one-level scan (not recursive) is sufficient and safe.
- **Rejected:** Adding `.active` and `.portals` to `_JUNCTION_DEFAULTS` — requires config-migration awareness for hubs that override `junctions:` explicitly, and still fails if any other undeclared junction exists.

### #366 — chmod+retry in _safe_rmtree, test files converted

- **Decision:** In `_safe_rmtree.safe_rmtree`, replace `shutil.rmtree(str(original), ignore_errors=ignore_errors)` with a call that uses a chmod+retry error handler. For Python ≥ 3.12 use the `onexc` parameter; for older versions use `onerror`. The handler does `os.chmod(path, 0o777)` then retries the failing operation. When `ignore_errors=True` and the retry also fails, swallow the error. Convert `test-wiki-daemon.py`, `test-wiki-store.py`, and `test-wiki-sync.py` from bare `shutil.rmtree(tmp, ignore_errors=True)` to `_safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)`, and remove those three files from the allowlist in `test-no-direct-rmtree.py`.
- **Rationale:** Git pack files (`.idx`/`.pack`) are marked read-only on Windows. `shutil.rmtree` with `ignore_errors=True` silently skips them, leaving temp dirs around. A chmod+retry correctly deletes them. Converting test files completes the fix end-to-end and shrinks the allowlist.
- **Rejected:** Fixing `_safe_rmtree.py` only and leaving test files on the allowlist — the test files themselves create git repos as fixtures, so they also encounter pack files.

### #376 — Windows locking → stuck_type: verify in millpy-fix.py

- **Decision:** In `millpy-fix.py`, inside the `except _llm_claude.LLMError as e` block, check whether the error is a Windows file-locking error before emitting `transient`. Detection: check `str(e)` for `"WinError 32"` or `"process cannot access"` or `"being used by another process"`, and also check `isinstance(e.__cause__, OSError) and getattr(e.__cause__, 'winerror', None) == 32`. If matched, emit `stuck_type: verify` with the original reason string.
- **Rationale:** Windows `WinError 32` ("The process cannot access the file because it is being used by another process") is a deterministic infrastructure failure — the wiki daemon or another process holds a file lock. Retrying will not fix it. `verify` routes to the user via mill-go's existing path, which is exactly right (user needs to kill the daemon or wait). `transient` triggers an auto-retry that will also fail.
- **Rejected:** New `stuck_type: infrastructure` — requires updating mill-go SKILL.md, test coverage for the new type, and `_implementer_common.py` dispatch; `verify` semantics ("user must inspect and fix before retry") cover the Windows locking case exactly.

## Technical context

### Key files and their roles

| File | Role |
|---|---|
| `plugins/mill/scripts/wiki/_client.py` | Public API; `_ensure_daemon` + `_connect_send_recv` + `health_check` |
| `plugins/mill/scripts/wiki/_server.py` | `WikiServer(DaemonBase)` — `handle_request`, `_handle_remove_task`, `_render_and_commit_all` |
| `plugins/mill/scripts/wiki/_render.py` | Pure function `render(tasks) -> dict[str, str]` mapping rel-path → content |
| `plugins/mill/scripts/_junction.py` | `strip_all_in_worktree`, `remove`, `_is_junction_or_symlink` |
| `plugins/mill/scripts/_safe_rmtree.py` | `safe_rmtree(path, *, allowed_root, ignore_errors)` — junction-strip then rmtree |
| `plugins/mill/scripts/millpy-fix.py` | Fixer dispatch; emits `{"status":"stuck","stuck_type":"transient",...}` on `LLMError` |

### _ensure_daemon flow (#382)

`_ensure_daemon` reads the state file → checks protocol version → does a bare TCP connect →
returns `(host, port, token)`. After the fix, the TCP connect is followed by:
```python
req = {FIELD_OP: OP_HEALTH, FIELD_TOKEN: token, "payload": {}}
_connect_send_recv(host, port, req)  # raises OSError on failure
```
On `OSError` or non-`ok` response: unlink the state file and fall through to `_spawn_server`.
The `_is_stale` helper (lines 581–607) also does a bare TCP connect; it is used only to
decide whether to unlink before respawn and does not need the same fix (it's a hint, not a
gate).

### _render_and_commit_all orphan deletion (#384)

Current loop:
```python
for rel_path, content in rendered.items():
    atomic_write(self._wiki_path, rel_path, content)
commit_paths = list(rendered.keys()) + ["tasks.json"]
```
After fix:
```python
existing = {p.name for p in self._wiki_path.glob("proposal-*.md")}
new_proposals = {k for k in rendered if k.startswith("proposal-")}
orphans = existing - new_proposals
for name in orphans:
    (self._wiki_path / name).unlink(missing_ok=True)
for rel_path, content in rendered.items():
    atomic_write(self._wiki_path, rel_path, content)
commit_paths = list(rendered.keys()) + list(orphans) + ["tasks.json"]
```
`commit_push` handles files that no longer exist (it stages deletions via `git add`).
Verify that `git -C wiki add <orphan>` stages a deletion when the file is already removed.

### strip_all_in_worktree one-level scan (#385)

Replace:
```python
for link_relative in junctions_cfg.keys():
    abs_link = worktree_path / link_relative
    remove(abs_link)
    removed.append(abs_link)
```
With:
```python
with os.scandir(str(worktree_path)) as it:
    for entry in it:
        ep = Path(entry.path)
        if entry.is_symlink() or _is_junction_or_symlink(ep):
            remove(ep)
            removed.append(ep)
```
`_is_junction_or_symlink` is already defined in `_junction.py` (line 150) — reuse it.

### _safe_rmtree chmod+retry (#366)

Python 3.12 replaced `shutil.rmtree`'s `onerror` kwarg with `onexc`. Use version check:
```python
import sys, stat
def _readonly_handler(func, path, exc):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        if not ignore_errors:
            raise
if sys.version_info >= (3, 12):
    shutil.rmtree(str(original), onexc=_readonly_handler)
else:
    shutil.rmtree(str(original), onerror=lambda f, p, e: _readonly_handler(f, p, e[1]))
```
The `ignore_errors` local from the outer scope is captured by the closure.

### millpy-fix.py detection helper (#376)

```python
def _is_windows_lock_error(e: Exception) -> bool:
    cause = getattr(e, "__cause__", None)
    if isinstance(cause, OSError) and getattr(cause, "winerror", None) == 32:
        return True
    msg = str(e).lower()
    return any(p in msg for p in ("winerror 32", "process cannot access", "being used by another process"))
```
Insert before the `json.dumps` line in the `except _llm_claude.LLMError` block.

## Testing

### test-wiki-daemon.py (existing, extend for #382)
Add: mock `socket.create_connection` to succeed but mock `_connect_send_recv` to raise `OSError`. Verify that `_ensure_daemon` unlinks the state file and calls `_spawn_server`. Also add: mock `_connect_send_recv` to return `{FIELD_OK: False}`. Same expected outcome.

### test-wiki-protocol.py or test-wiki-server.py (existing/new, #383 + #384)
**#383:** Call `_handle_remove_task` with a slug that is not in the store. Verify `_render_and_commit_all` is called (via mock/spy) and that `ERR_NOT_FOUND` is returned.
**#384:** Seed `wiki_path` with a `proposal-old-slug.md` file. Call `_render_and_commit_all` with tasks that do not include `old-slug`. Verify `proposal-old-slug.md` is deleted and its path appears in the `commit_push` call.

### test-junction.py (existing, extend for #385)
Add: create a temp worktree dir with a symlink/junction named `.active` and another named `.wiki`. Call `strip_all_in_worktree(worktree, junctions_cfg={})` (empty config). Verify both are stripped and returned in the result list.

### test-safe-rmtree.py (existing, extend for #366)
Add: create a temp dir containing a git-like subdirectory with a read-only file (set via `os.chmod(f, 0)`). Call `safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)`. Verify the temp dir is fully deleted (no leftover files).

### test-wiki-daemon.py / test-wiki-store.py / test-wiki-sync.py (#366)
Convert all `shutil.rmtree(tmp, ignore_errors=True)` calls to `_safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)`. Remove these three files from the `ALLOWED_FILES` set in `test-no-direct-rmtree.py`.

### test-millpy-fix.py (existing, extend for #376)
Add: construct an `LLMError` whose message contains `"WinError 32"`. Call the main logic (or extract `_is_windows_lock_error` as a separate helper and test it directly). Verify the JSON output has `stuck_type: verify`. Also verify a generic `LLMError` still produces `stuck_type: transient`.

## Q&A log

- **Q:** #382 — should `_ensure_daemon` health exchange use a different timeout than the existing 0.5s TCP ping? **A:** 1.0s — sufficient for localhost JSON round-trip under load; 0.5s risks false positives.
- **Q:** #383 — after rerendering when slug is absent, return `OK: True` or `ERR_NOT_FOUND`? **A:** Keep `ERR_NOT_FOUND`; callers may use it to detect no-op removes.
- **Q:** #384 — orphan deletion in `render()` or in `_render_and_commit_all`? **A:** `_render_and_commit_all`; `render()` stays a pure function with no access to the wiki path.
- **Q:** #385 — add missing junctions to config defaults vs walk-and-strip FS? **A:** Walk-and-strip (one-level FS scan); immune to config drift and legacy worktrees.
- **Q:** #366 — fix `_safe_rmtree` only, or also convert whitelisted test files? **A:** Both; test files create git repos as fixtures and also encounter read-only pack files.
- **Q:** #376 — route Windows locking to `verify` or new `infrastructure` stuck type? **A:** `verify`; semantics match ("user must fix before retry"), no new type or SKILL update needed.
