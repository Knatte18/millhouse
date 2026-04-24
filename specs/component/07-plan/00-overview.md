# Plan: mill-cleanup script

```yaml
task: mill-cleanup script
slug: 07-mill-cleanup-script
approved: false
started: 20260424-000000
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py && python plugins/mill/integration_tests/test-spawn.py && python plugins/mill/integration_tests/test-merge.py && python plugins/mill/integration_tests/test-plan-assets.py && python plugins/mill/integration_tests/test-go-assets.py && python plugins/mill/integration_tests/test-cleanup.py
```

## Batch Index

```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-worktree.py
  - name: cleanup-core
    file: 02-cleanup-core.md
    depends-on: [foundation]
    verify: python plugins/mill/unit_tests/test-cleanup.py
  - name: integration-test
    file: 03-integration-test.md
    depends-on: [cleanup-core]
    verify: python plugins/mill/integration_tests/test-cleanup.py
```

`foundation` has no deps and runs first. `cleanup-core` needs `list_worktrees()` and `remove()` from foundation before wiring them into the CLI. `integration-test` needs the full CLI script from cleanup-core. No docs batch — see Shared Decision: SKILL.md wrapper.

## Shared Decisions

### Decision: No SKILL.md wrapper

- **Decision:** `mill-cleanup.py` is a standalone CLI script. No `plugins/mill/skills/mill-cleanup/SKILL.md` is created.
- **Rationale:** mill-cleanup is a maintenance sweep tool invoked directly by the operator (`python plugins/mill/scripts/mill-cleanup.py [--apply]`), not by a Claude session acting through a skill prompt. The script's `--help` output and spec 07 serve as documentation. The v1 SKILL.md wrapper added value there because v1 skills were the invocation mechanism; v2 separates CLI scripts from Claude-facing skills.
- **Applies to:** all batches — no skill file is created at any stage.

### Decision: plan-builder stays in `mill-cleanup.py`; no `_cleanup.py` helper

- **Decision:** The plan-building logic lives in `def build_plan(...)` within `mill-cleanup.py`. No separate `_cleanup.py` helper module is created.
- **Rationale:** `build_plan` is side-effect-free with respect to git and wiki writes — it performs no subprocess calls and makes no mutations. It does read `status.md` files via `_read_phase` (file I/O), which is why the unit test uses `tempfile` fixtures rather than purely in-memory inputs. No other script calls `build_plan`, so a helper module would have exactly one caller. The unit test imports the function via `importlib.util.spec_from_file_location` (standard pattern for hyphenated-name scripts in this project).
- **Applies to:** cleanup-core and integration-test batches.

### Decision: phase read via private `_read_phase()` in `mill-cleanup.py`

- **Decision:** `mill-cleanup.py` includes a private `def _read_phase(status_path: Path) -> str | None` that extracts `phase:` from the leading fenced yaml block of `status.md`. Returns `None` on any error (missing file, unreadable, bad YAML, missing key).
- **Rationale:** `_status.py`'s public API does not expose a `read_field` function. Adding one for a single caller would expand that module's surface area unnecessarily. The parse is four lines using the same fence-extraction pattern already in `_status.py`.
- **Applies to:** cleanup-core batch.

### Decision: `CleanupPlan` and `SlugRecord` as frozen dataclasses

- **Decision:** Two `@dataclass(frozen=True)` types live in `mill-cleanup.py`:
  - `SlugRecord(slug, worktree_path, branch, active_dir, home_marker)` — one per slug needing action.
  - `CleanupPlan(to_remove_done, to_remove_abandoned, to_reset_home, to_report)` — the full plan output.
- **Rationale:** Frozen dataclasses give deterministic field access in unit tests without dict-key guessing. Frozen enforces that callers cannot mutate the plan after construction.
- **Applies to:** cleanup-core and integration-test batches.

### Decision: worktree-to-slug matching via worktree path basename

- **Decision:** `build_plan` matches a worktree record to a slug by checking `Path(worktree["path"]).name == slug`. The branch is carried from the worktree record for `git branch -D`.
- **Rationale:** mill-spawn creates worktrees at `<worktrees_dir>/<slug>` (via `_sibling.resolve_path("worktrees", git_root)`), so the directory basename IS the slug. Matching on branch name is fragile (prefix convention could change); path basename is simpler and matches the actual spawn contract.
- **Applies to:** cleanup-core batch — `build_plan` implementation and unit tests.

### Decision: `list_worktrees` and `remove` signatures

- **Decision:**
  - `list_worktrees(cwd: Path) -> list[dict[str, str | None]]` — takes `cwd` (hub root) and returns dicts with keys `"path"` (absolute str) and `"branch"` (short branch name after stripping `refs/heads/`, or `None` for detached HEAD).
  - `remove(path: Path, cwd: Path, force: bool = True) -> None` — explicit `cwd` so the caller (mill-cleanup's `main`) controls which repo context git uses.
  - Function is named `list_worktrees` (not `list`) to avoid shadowing the builtin.
- **Rationale:** Consistent with `create(branch, target, cwd)` pattern already in `_worktree.py`. Returning a short branch name simplifies callers (no `refs/heads/` stripping everywhere).
- **Applies to:** foundation and cleanup-core batches.

## All Files Touched

New files:
- `plugins/mill/scripts/mill-cleanup.py`
- `plugins/mill/unit_tests/test-cleanup.py`
- `plugins/mill/integration_tests/test-cleanup.py`

Modified files:
- `plugins/mill/scripts/_worktree.py` (add `list_worktrees()` and `remove()`)
- `plugins/mill/unit_tests/test-worktree.py` (add tests for both new functions)
