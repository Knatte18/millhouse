# Batch: Git sync layer

```yaml
task: V3 wiki module with daemon and in-process cache
batch: Git sync layer
number: 2
cards: 1
verify: null
depends-on: [1]
```

## Batch Scope

Creates `wiki/_sync.py` — the git-operations layer the server uses to pull, stage, commit, push, and write files atomically. All operations are subprocess-based (stdlib `subprocess`), running `git` against the wiki clone directory. This batch delivers the V2 behavior set (`write_commit_push` with one rebase-retry on non-fast-forward, `pull --ff-only`, atomic write via temp+rename) as a clean standalone module. The path-traversal guard is also here because it is used by both read and write paths in the server. The server (Batch 4) imports from this module directly; no external API is exposed to the client.

## Cards

### Card 3: `wiki/_sync.py` — git operations

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/wiki/_sync.py`
- **Deletes:** none
- **Requirements:**
  Import `subprocess`, `os`, `tempfile`, `pathlib.Path` from stdlib. Import `WikiPushError`, `WikiPathError` from `wiki`. No other mill imports.

  `path_guard(rel_path: str) -> None` — raises `WikiPathError` if `rel_path` is empty (`not rel_path`), is absolute (`Path(rel_path).is_absolute()`), or contains any `..` component (`".." in Path(rel_path).parts`). No dummy-base resolve needed — part-level checks are sufficient since paths are validated before any filesystem access. Called by server before any read or write.

  `atomic_write(wiki_path: Path, rel_path: str, content: str) -> None` — writes `content` (UTF-8) to a temp file in `wiki_path`, then `os.replace(tmp, wiki_path / rel_path)` (atomic on POSIX and Windows). Creates parent directories if needed.

  `pull(wiki_path: Path) -> bool` — runs `git -C <wiki_path> pull --ff-only`; returns `True` if the working tree was updated (check stdout for "Already up to date." — if absent, updated); raises `WikiPushError` on non-zero exit.

  `commit_push(wiki_path: Path, rel_paths: list[str], message: str) -> None` — mirrors V2 `write_commit_push`:
  1. `git -C <wiki_path> add <rel_paths...>`
  2. `git -C <wiki_path> diff --cached --quiet` — if rc=0 (nothing staged), return immediately (idempotent re-run success).
  3. `git -C <wiki_path> commit -m <message>`
  4. `git -C <wiki_path> push` — on rc=0, done. On rc!=0 (non-fast-forward / rejected): one retry: `git -C <wiki_path> pull --rebase`, then check for conflicts (`git -C <wiki_path> rebase --abort` if `REBASE_HEAD` exists after pull failure); if clean rebase: `git -C <wiki_path> push` again; if push still fails: `git -C <wiki_path> rebase --abort` + raise `WikiPushError`. A genuine rebase conflict (detected by non-zero exit from `git pull --rebase`): run `git -C <wiki_path> rebase --abort` + raise `WikiPushError("rebase conflict")`.

  Helper `_run(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess` — runs the command with `capture_output=True, text=True, encoding="utf-8"`. When `check=True` and rc!=0: raises `WikiPushError(stderr)`.

- **Commit:** `feat(wiki): add _sync.py git operations layer`

## Batch Tests

`verify: null` — tested in Batch 6 (`test-wiki-sync.py`) against a real tempfile bare-repo + clone. Implementer should import-check: `PYTHONPATH=plugins/mill/scripts python -c "from wiki import _sync; print('ok')"`.
