# Batch: foundation

```yaml
task: Drop active.slug.md marker
batch: foundation
number: 1
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-marker.py
depends-on: []
```

## Batch Scope

This batch adds the new `_marker` module, the shared test helper `_make_task_worktree`, and the `test-marker.py` suite that exercises every `_marker` path. No existing files are touched in this batch — these are pure additions. The next batch (migration) consumes these new symbols.

External interface delivered: `_marker.MarkerError`, `_marker.slug_from_branch(git_root, wiki_path, cfg)`, `_marker.task_data(git_root, wiki_path, cfg)`, and `_test_helpers._make_task_worktree(tmp, slug, title, *, branch_prefix="", phase="active")`.

Batch-local decisions (not in `## Shared Decisions`): the new test helper sits in `plugins/mill/unit_tests/_test_helpers.py`, not in `scripts/`. The leading underscore matches the existing helper-module convention and the `unit_tests/` location keeps test fixtures out of the production import path.

## Cards

### Card 1: create `_marker.py`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_active.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_marker.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/scripts/_marker.py` with a module docstring, a public `MarkerError(RuntimeError)` exception class, and two public functions: `slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str` and `task_data(git_root: Path, wiki_path: Path, cfg: dict) -> dict`. `slug_from_branch` runs `git -C <git_root> branch --show-current`, raises `MarkerError("detached HEAD or non-branch state")` when the captured stdout is empty after strip, fetches `prefix = cfg.get("spawn", {}).get("branch_prefix", "")`, raises `MarkerError(f"branch {branch!r} does not start with configured prefix {prefix!r}")` when `prefix` is non-empty and `not branch.startswith(prefix)`, and computes `slug = branch.removeprefix(prefix)`. Then load Home.md via `home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")` and `tasks = _tasks_md.parse(home_text)`. Find the task with matching slug; raise `MarkerError(f"branch slug {slug!r} not present in Home.md")` when absent. Raise `MarkerError(f"task {slug!r} is not [active] in Home.md (phase={task.phase!r})")` when `task.phase != "active"`. Return `slug`. `task_data` calls `slug_from_branch` to validate and obtain the slug, re-parses Home.md (or accepts that two reads is acceptable for symmetry — keep the function self-contained, no caller-passed tasks), captures the same branch via `_subprocess_util.run(["git", "-C", str(git_root), "branch", "--show-current"]).stdout.strip()`, and returns `{"slug": slug, "branch": branch, "task_title": task.title}`. Use `_subprocess_util.run` (not `subprocess.run`) for the `git` invocation. Public API listed in the module docstring matches the public signatures.
- **Commit:** `feat(marker): add _marker module with branch+Home.md slug derivation`

### Card 2: create `_test_helpers.py`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/_test_helpers.py` with a module docstring naming the public symbol and a public `_make_task_worktree(tmp: Path, slug: str, title: str, *, branch_prefix: str = "", phase: str = "active") -> tuple[Path, Path]` function. Implementation: under `tmp`, create `worktree_path = tmp / "worktree"` and `wiki_path = tmp / "wiki"`. In `worktree_path` initialise a real git repo via `_subprocess_util.run(["git", "init", "--initial-branch=main", str(worktree_path)])` (fall back to `git init` then `git checkout -b main` when the `--initial-branch` flag is unsupported), set a deterministic local user.email/user.name via `git config`, write a `.keep` file, `git add` and commit with message `"init"` so HEAD is non-empty, then create the task branch via `git -C worktree_path checkout -b f"{branch_prefix}{slug}"`. In `wiki_path` write a minimal `Home.md` whose body contains exactly `f"## {title}\n[[{slug}]] [{phase}]\n\n_body_\n"` when `phase != "none"` and `f"## {title}\n[[{slug}]]\n\n_body_\n"` when `phase == "none"` (test-only opt-out for "no marker"). Validate by parsing the Home.md via `_tasks_md.parse(home_text)` and asserting the slug appears with the expected phase. Return `(worktree_path, wiki_path)`. Add `sys.path` shim for the `plugins/mill/scripts/` directory so callers can `import _tasks_md` without bootstrapping themselves.
- **Commit:** `test(helpers): add _make_task_worktree shared fixture for branch+Home.md state`

### Card 3: create `test-marker.py`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-marker.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-marker.py` with one test function per scenario, all running under `tempfile.TemporaryDirectory()`. Use `_test_helpers._make_task_worktree` to set up state. Tests required: `test_slug_from_branch_happy_path` (branch=`hanf/foo`, prefix=`hanf/`, Home.md slug=`foo` phase=`active` → returns `"foo"`); `test_slug_from_branch_empty_prefix` (branch=`foo`, prefix=`""`, Home.md slug=`foo` phase=`active` → returns `"foo"`); `test_slug_from_branch_detached_head` (manually checkout a SHA so `branch --show-current` returns empty → raises `MarkerError`); `test_slug_from_branch_unknown_slug` (branch=`hanf/bar`, Home.md only has `foo` → raises `MarkerError`); `test_slug_from_branch_phase_done` (Home.md slug present at phase=`done` → raises `MarkerError`); `test_slug_from_branch_phase_abandoned` (phase=`abandoned` → raises `MarkerError`); `test_slug_from_branch_phase_none` (slug present without phase marker → raises `MarkerError`); `test_slug_from_branch_prefix_mismatch` (branch=`other/foo`, prefix=`hanf/` → raises `MarkerError`); `test_task_data_happy_path` (returns `{"slug": "foo", "branch": "hanf/foo", "task_title": "Foo Title"}`). Each test prints `PASS: <test name>` on success. Provide `main() -> int` that runs every test, prints `FAIL` per failure, and exits 1 on any failure. End with `if __name__ == "__main__": sys.exit(main())`. Add `sys.path` shim to `plugins/mill/scripts/` and `plugins/mill/unit_tests/` so imports of `_marker`, `_tasks_md`, `_test_helpers` resolve.
- **Commit:** `test(marker): add test-marker.py covering all _marker paths`

## Batch Tests

`verify:` runs only `test-marker.py`, the new file added in this batch. The other test files in `plugins/mill/unit_tests/` will not have been updated to use the new `_marker` module yet (that lands in Batch 2), so running `run-all.py` here would fail unrelated tests on existing-but-not-yet-migrated paths. Batch 2's verify covers the full suite.

`test-marker.py` exercises every public `_marker` symbol:

- happy paths for `slug_from_branch` (with and without `branch_prefix`)
- `MarkerError` paths: detached HEAD, unknown slug, slug-not-active (`done`/`abandoned`/no-marker), prefix mismatch
- happy path for `task_data` returning the three documented keys with title from Home.md
