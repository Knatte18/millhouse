# Batch: spawn-parent-thread

```yaml
task: 'status.md: rename parent to parent_branch, add parent_thread'
batch: spawn-parent-thread
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-spawn-core.py test-millpy-spawn.py
depends-on: [1]
```

## Batch Scope

Adds the `millpy-spawn --parent <name>` option and threads it through `_spawn_core.write_initial_status` into batch 1's `_status.render_initial(..., parent_thread=...)`, so a spawned task's status.md records `parent_thread:`.
No caller passes `--parent` yet (see Shared Decision `parent-thread-is-write-only`); `millpy-claim.py` keeps calling `write_initial_status` without the new argument and needs no edit.

## Cards

### Card 5: write_initial_status forwards parent_thread

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add keyword-only `parent_thread: str | None = None` to `write_initial_status` (after `cfg`) and pass `parent_thread=parent_thread` to `_status.render_initial`.
    Document it in the docstring `Args:` (session name recorded as status.md `parent_thread:`; row omitted when `None`/empty) and update the `write_initial_status` line in the module docstring's public-API list to show `*, cfg, parent_thread=None`.
    Change the `parent_branch` arg text to name the `parent_branch:` row.
  - In `test-spawn-core.py`, change the existing check `"parent: main" not in text` (and its message) to `"parent_branch: main"`.
    In the same test function, after the existing assertions, add: the default call leaves no line starting with `parent_thread:`.
    Add a new test (registered wherever that file registers its tests) that calls `write_initial_status(..., parent_thread="mh:orch")` on a fresh git repo fixture built the same way as the existing `write_initial_status` test and asserts the written status.md's yaml, read via `_status.read`, has `parent_thread == "mh:orch"`.
- **Commit:** `feat(spawn-core): forward parent_thread to render_initial`

### Card 6: millpy-spawn --parent option

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `millpy-spawn.py` `main`, add `parser.add_argument("--parent", default=None, help="Name of the session spawning this task; recorded as status.md parent_thread:.")`.
  - Immediately after `args = parser.parse_args(argv)` and before `resolve_git_root()` (so before any wiki claim or worktree work): compute `parent_thread = args.parent.strip() if args.parent is not None else None`, then set it to `None` when empty.
    If `parent_thread` contains any character with `ord(c) < 32 or ord(c) == 127`, raise `SystemExit("[spawn] ERROR: --parent must not contain newlines or control characters.")` (ASCII only).
  - Pass `parent_thread=parent_thread` to `_spawn_core.write_initial_status`.
  - In the `--dry-run` branch, when `parent_thread` is not `None`, also print `f"[DryRun] Parent:   {parent_thread}"`.
  - Update the module docstring's `Usage:` block with `[--parent <name>]  # record the spawning session as status.md parent_thread:`.
  - In `test-millpy-spawn.py`, add tests and register them in the `tests` list in `main()`:
    `_run_main_with_mocks(["--parent", "mh:orch"])` -> `write_initial_status` called with `parent_thread="mh:orch"`;
    `_run_main_with_mocks([])` -> called with `parent_thread=None`;
    `["--parent", "  "]` -> `parent_thread=None`;
    `["--parent", "a\nb"]` and `["--parent", "a\x01b"]` each raise `SystemExit`, and the returned mocks show `claim_in_wiki` and `write_initial_status` were not called.
    `_run_main_with_mocks` returns the mocks only on a normal return, so for the two rejection cases extend it with an optional parameter that captures the `spawn_core_mock` (e.g. an `on_mocks` callback invoked before `mod.main(argv)`, or a mutable holder) so the test can inspect it after catching `SystemExit`; keep every existing caller unchanged.
- **Commit:** `feat(spawn): add --parent option recorded as parent_thread`

### Card 7: document --parent and assert parent_branch in spawn integration test

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
  - `plugins/mill/integration_tests/test-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `mill-spawn/SKILL.md`'s `## Run it` bash line, add `[--parent <name>]` before `[--dry-run]`.
    Below the code block add one sentence: `--parent <name>` records the spawning session's name as status.md's optional `parent_thread:` row (omitted when the flag is absent); the parent branch is recorded as `parent_branch:`.
  - In `integration_tests/test-spawn.py`, change the assertion `"parent: main" in status_text` to `"parent_branch: main" in status_text`.
    This file is not run by `verify:` (see Shared Decision `integration-tests-excluded-from-verify`).
- **Commit:** `docs(spawn): document --parent and parent_branch row`

## Batch Tests

`verify:` runs `test-spawn-core.py` (card 5) and `test-millpy-spawn.py` (card 6).
Card 7 is a docs line plus one integration-test string that `verify:` does not run.
