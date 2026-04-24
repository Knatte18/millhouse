# Batch 01 — script

```yaml
batch: 01-script
state: pending
```

## Scope

Implement `mill-abandon.py` — the CLI entrypoint for marking a task abandoned.

Flow:
1. Verify cwd is a worktree: `.millhouse/active.slug.md` must exist; abort if hub.
2. Resolve slug via `_active.read_slug(mill_dir)`.
3. Resolve `git_root` via `_paths.resolve_git_root()`, wiki via `_paths.resolve_wiki_path(git_root)`.
4. Load `<wiki>/active/<slug>/status.md` — abort if missing. Read phase via `_status.read_status`; refuse if phase is already `abandoned` or `done`.
5. Check builder lock: `_builder_lock.read(mill_dir)`. Inline stale check: `age = (now - parse_iso(info.timestamp)).total_seconds()`, ValueError on bad timestamp → treat as stale. If non-stale lock held, abort unless `--force`.
6. Confirm unless `--force`: print `Abandon <slug>? (y/N) ` to stdout, read stdin. If not `y`/`Y`, exit 0 silently.
7. Acquire wiki lock: `_wiki.acquire_lock(wiki_path, slug)`.
8. Append phase: `_status.append_phase(status_path, "abandoned", timestamp)`.
9. Commit + push: `_wiki.write_commit_push(wiki_path, [f"active/{slug}/status.md"], f"task: abandon {slug}")`.
10. Release wiki lock: `_wiki.release_lock(wiki_path)`.
11. Print: `Task '<slug>' marked abandoned. Run 'mill-cleanup' from the hub to remove the worktree and active dir, and reset Home.md.`

Error paths each call `sys.exit(<message>)` (exit 1).

## Cards

### Card 1.1 — mill-abandon.py

Reads:
- `plugins/mill/scripts/mill-spawn.py` — arg-parse + sys.path pattern
- `plugins/mill/scripts/mill-status.py` — resolve_git_root + resolve_wiki_path pattern
- `plugins/mill/scripts/_active.py` — `read_slug` API
- `plugins/mill/scripts/_status.py` — `read_status`, `append_phase` API
- `plugins/mill/scripts/_wiki.py` — `acquire_lock`, `release_lock`, `write_commit_push` API
- `plugins/mill/scripts/_builder_lock.py` — `read`, `STALE_WINDOW_SEC` (do NOT call `_is_stale`; it is module-private)
- `plugins/mill/scripts/_paths.py` — `resolve_git_root`, `resolve_wiki_path`

Creates:
- `plugins/mill/scripts/mill-abandon.py`

Requirements:
- `argparse`: `--force` flag only; no positional args.
- Script sets `sys.path` to its own directory so imports work regardless of cwd.
- All error exits via `sys.exit(str)` (prints message, exits 1).
- User-cancel (N) exits 0 with no output. Strip and lowercase the response before comparing: `if response.strip().lower() == 'y':` — guards against Windows CRLF on piped stdin.
- `_wiki.release_lock` called in a `finally` block so it runs even if `write_commit_push` raises.
- Timestamp generated with `datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` at the point of writing (after confirmation).
- `mill_dir = Path.cwd() / ".millhouse"` — local `.millhouse/` in worktree cwd.

Commit: `feat(09): add mill-abandon.py`
