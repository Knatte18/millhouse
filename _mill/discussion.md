# Discussion: Write active-slug indicator file in hub

```yaml
task: Write active-slug indicator file in hub
slug: hub-active-slug
status: discussing
parent: main
```

## Problem

Review scripts (`millpy-review-code.py`, `millpy-review-discussion.py`, `millpy-review-plan.py`) detect the active task via `find_active_slug`, which delegates to `_marker.slug_from_branch`. Branch-based detection only works when the caller's cwd is a task worktree — from the hub (main branch), branch detection fails with a `MarkerError`, forcing the user to pass `--slug` manually on every invocation.

The fix is an ephemeral indicator file: an empty `_mill/<slug>.active` file written by `mill-spawn`/`mill-claim` when a task is claimed and deleted by `mill-cleanup` when the task is torn down. `find_active_slug` gains a fallback that globs `_mill/*.active` when `slug_from_branch` fails, enabling hub-side review invocations without `--slug` as long as exactly one task is active.

## Scope

**In:**
- `_spawn_core.py` — new helper `write_hub_active_indicator(hub_root, slug)` that creates `hub_root/_mill/<slug>.active`
- `millpy-spawn.py` — call the helper after the portal and `.active` junction are created
- `millpy-claim.py` — call the helper after the portal and `.active` junction are created
- `millpy-cleanup.py` — delete `hub_root/_mill/<slug>.active` in both `_apply_inplace_record` and `_apply_worktree_record`
- `_review_common.py` — `find_active_slug`: add glob fallback after `slug_from_branch` raises `MarkerError`
- `_gitignore.py` — add `**/_mill/*.active` to `GLOB_ENTRIES`
- `.gitignore` (repo root) — add `**/_mill/*.active` to the mill-managed block directly (mill-setup writes this block; we update it now so existing repos get coverage without re-running setup)
- Unit tests: `test-spawn-core.py` (new test for `write_hub_active_indicator`), `test-cleanup.py` (deletion in both apply paths), a new `test-review-common.py` covering the glob fallback paths

**Out:**
- No changes to wiki, status.md, or any committed task-branch state
- No changes to mill-setup's invocation sequence (gitignore block update is backward-compatible)
- No changes to `_marker.slug_from_branch` itself
- No changes to how review scripts accept `--slug` (still supported and takes priority)
- No interactive prompting when multiple `.active` files are found — just a clear error

## Decisions

### Helper location in _spawn_core.py

- Decision: Add `write_hub_active_indicator(hub_root: Path, slug: str) -> None` to `_spawn_core.py`.
- Rationale: Both `millpy-spawn.py` and `millpy-claim.py` already import `_spawn_core`; centralising avoids duplication. The helper is 3 lines: `mkdir(_mill, exist_ok=True)`, `(hub_root / "_mill" / f"{slug}.active").touch()`.
- Rejected: Inlining in each caller — two copies of the same logic with no shared test surface.

### Gitignore via GLOB_ENTRIES + direct update

- Decision: Add `**/_mill/*.active` to `_gitignore.py`'s `GLOB_ENTRIES` AND directly into the mill-managed block in the repo's `.gitignore`.
- Rationale: `GLOB_ENTRIES` ensures all future `mill-setup` runs propagate the pattern. The direct write covers existing repos (including this one) that won't be re-setup immediately.
- Rejected: Only updating `GLOB_ENTRIES` — existing repos would show the file as untracked until mill-setup is re-run. Only updating `.gitignore` — the template stays out of sync.

### Multiple-slug fallback behaviour

- Decision: In the glob fallback — zero matches raises `ReviewError` with a clear message explaining the indicator mechanism; multiple matches raises `ReviewError("N tasks active; use --slug <slug>")` listing the found slugs.
- Rationale: A silent wrong pick would be worse than a prompt. The error message teaches the user the correct invocation.
- Rejected: Re-raising the original `MarkerError` text — it mentions branch detection, which is confusing in the hub context.

### Deletion responsibility in cleanup

- Decision: Both `_apply_inplace_record` and `_apply_worktree_record` delete `hub_root/_mill/<slug>.active` using `Path.unlink(missing_ok=True)` (no error if absent).
- Rationale: The file is ephemeral; a missing file on cleanup is not an error (e.g., after a manual deletion or a pre-feature task). Both apply functions already receive `hub_root`.
- Rejected: Centralising deletion in `apply_plan` — the two apply functions are the right place (they own all per-record teardown), and centralising would require threading the slug differently.

## Technical context

**`_review_common.find_active_slug`** ([plugins/mill/scripts/_review_common.py:243](plugins/mill/scripts/_review_common.py#L243)) — current implementation calls `_marker.slug_from_branch(git_root, wiki_path, cfg)` and re-raises any `MarkerError` as `ReviewError`. The glob fallback goes in the `except _marker.MarkerError` block: glob `git_root / "_mill" / "*.active"`, extract stem (`path.stem`) to get the slug.

**`_spawn_core.recreate_active_junction`** ([plugins/mill/scripts/_spawn_core.py:746](plugins/mill/scripts/_spawn_core.py#L746)) — already creates `hub_root/_mill` if absent and sets up the `.active` junction. `write_hub_active_indicator` follows the same mkdir-then-write pattern and can rely on `recreate_active_junction` having already been called (both callers call it first).

**`millpy-spawn.py` call site** — after `recreate_active_junction(dest_hub)` at line 226, before `pick_worktree_color`. Note: in spawn, `dest_hub` is the TASK worktree root, not the real hub. The indicator must go to `git_root/_mill/<slug>.active` (the real hub), not `dest_hub/_mill/`. Pass `git_root` (resolved at top of `main()`) as `hub_root`.

**`millpy-claim.py` call site** — after `recreate_active_junction(resolve_hub_path())` at line 299. Hub = `resolve_hub_path()` (in-place task; hub IS the task worktree). Pass `resolve_hub_path()` as `hub_root`.

**`millpy-cleanup.py` — `_apply_inplace_record`** ([plugins/mill/scripts/millpy-cleanup.py:307](plugins/mill/scripts/millpy-cleanup.py#L307)) — already receives `hub_root`. After removing the `.active` junction (line 384), add `(hub_root / "_mill" / f"{record.slug}.active").unlink(missing_ok=True)`.

**`millpy-cleanup.py` — `_apply_worktree_record`** ([plugins/mill/scripts/millpy-cleanup.py:393](plugins/mill/scripts/millpy-cleanup.py#L393)) — already receives `hub_root`. After removing the portal entry (line 428), add the same `unlink(missing_ok=True)` call.

**`_gitignore.py` `GLOB_ENTRIES`** ([plugins/mill/scripts/_gitignore.py:32](plugins/mill/scripts/_gitignore.py#L32)) — add `"**/_mill/*.active"` to the list. The current list ends at `"**/.active/"`.

**`.gitignore` mill-managed block** — the block is delimited by `# === mill-managed` / `# === end mill-managed ===`. Add `**/_mill/*.active` to the end of this block (before the closing delimiter).

## Testing

**`test-spawn-core.py` — `write_hub_active_indicator`**
- Happy path: call with a temp dir as hub_root, verify `hub_root/_mill/<slug>.active` exists and is a file.
- Idempotent: calling twice does not error.
- Mkdir: `hub_root/_mill/` is created if absent.

**`test-cleanup.py` — indicator deletion**
- `_apply_inplace_record`: extend existing test or add new fixture — verify `hub_root/_mill/<slug>.active` is deleted.
- `_apply_worktree_record`: same; verify deletion happens even when the worktree itself was already removed.
- Missing file tolerance: `unlink(missing_ok=True)` — calling cleanup when no indicator file exists must not raise.

**New `test-review-common.py` — `find_active_slug` glob fallback**
- Zero `.active` files + `slug_from_branch` raises → `ReviewError` with meaningful message.
- Exactly one `.active` file (`my-task.active`) → returns `"my-task"`.
- Multiple `.active` files → `ReviewError` mentioning "use --slug".
- Happy path (branch detection succeeds): glob is never consulted (mock `slug_from_branch` returns without raising).

## Q&A log

- **Q:** Should `**/_mill/*.active` go into `_gitignore.py`'s `GLOB_ENTRIES` (mill-setup managed) AND directly into the current repo's `.gitignore`? **A:** Yes — both.
- **Q:** When the glob fallback in `find_active_slug` finds 0 or >1 `.active` files, how should it behave? **A:** 0 matches → `ReviewError` with clear message; multiple matches → `ReviewError` listing slugs and telling user to use `--slug`.
- **Q:** Should `write_hub_active_indicator` be a shared helper in `_spawn_core.py`? **A:** Yes.
