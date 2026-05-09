# Batch: vscode-cli-integration

```yaml
task: 'millpy-vscode rework: hybrid spawn/pick + filter active editors'
batch: vscode-cli-integration
number: 2
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

This batch wires the helper from batch 1 into the picker, replacing the old auto-select-when-single-or-numbered-prompt with the new unified prompt that filters out already-open worktrees, accepts `<Enter>` / number / `q` input, and adds the `--new` flag. It also extends the unit tests to cover the new control flow and rewrites the public-facing SKILL.md description. The batch depends on batch 1 because card 3 imports `find_open_vscode_paths` and `_path_matches_cmdline` from `_vscode_processes`, and card 4 imports the same module to construct the patch target.

External interface delivered: an updated `millpy-vscode` CLI whose:
- Default flow filters open worktrees, shows a unified prompt, supports `<Enter>` / N / `q`.
- `--new` flag forces spawn-and-open without showing the picker.
- `--slug` and `--list` behave exactly as before.
- `--new` and `--slug` are mutually exclusive (argparse exit 2).

Batch-local decision: the `_spawn_and_open` private helper inside `millpy-vscode.py` takes the *list of pre-spawn active worktrees* as a parameter, NOT a re-discovery callback or an empty placeholder. This is locked to keep the existing test mock that supplies exactly two `discover_active_worktrees` `side_effect` values working; any extra discover call would break it.

## Cards

### Card 3: rework `millpy-vscode.py` main()

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/_vscode_processes.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_active.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Refactor `plugins/mill/scripts/millpy-vscode.py` per the discussion's `Files touched > millpy-vscode.py` block. Do not modify `_build_code_argv` or `_load_spawn_main`. Concretely:

  1. **Imports.** Add `import _vscode_processes` and `from _vscode_processes import find_open_vscode_paths, _path_matches_cmdline` at the top, alongside the existing imports.

  2. **argparse.** Inside `main()`, after `parser = argparse.ArgumentParser(...)`, add `--new` (`store_true`) and put both `--slug` and `--new` inside `parser.add_mutually_exclusive_group()` so that passing both raises argparse's standard usage error (`SystemExit(2)`). The existing `--list` stays at top level (it's compatible with both). The `--list` flag retains its current behavior — it must NOT consult the filter.

  3. **Filter step.** Add a new private helper `_filter_open_worktrees(active: list[tuple[Path, str, str]], wiki_path: Path | None, hub_subpath_default: str) -> list[tuple[Path, str, str]]` defined below `_load_spawn_main`. It:
     - Calls `open_cmdlines = find_open_vscode_paths()`.
     - If `open_cmdlines` is empty, returns `active` unchanged.
     - Otherwise iterates `active`. For each `(entry_path, slug, title)`: load that worktree's per-worktree `hub_relative_path` via `_load_config(wiki_path, entry_path)` if `wiki_path is not None` else use `hub_subpath_default`; compute `launch = resolve_hub_relative_path(entry_path, hub_subpath)`; KEEP the entry iff no element of `open_cmdlines` makes `_path_matches_cmdline(launch, str(cmdline))` return True.
     - On any exception during a single entry's per-worktree config load (`SystemExit` from `_load_config`), fall back to `hub_subpath_default` for that entry.
     - Returns the filtered list, preserving original order.

  4. **`_spawn_and_open` helper.** Add a new private helper `_spawn_and_open(worktrees_dir: Path, pre_active: list[tuple[Path, str, str]], wiki_path: Path | None) -> int` defined below `_filter_open_worktrees`. Implementation:
     ```python
     def _spawn_and_open(worktrees_dir, pre_active, wiki_path):
         pre_paths = {entry[0] for entry in pre_active}
         spawn_main = _load_spawn_main()
         rc = spawn_main([])
         if rc != 0:
             return rc
         post = _spawn_core.discover_active_worktrees(worktrees_dir)
         new_entries = [e for e in post if e[0] not in pre_paths]
         if len(new_entries) == 0:
             print("[mill-vscode] spawn produced no new worktree; nothing to open.", file=sys.stderr)
             return 0
         if len(new_entries) > 1:
             print(f"[mill-vscode] spawn produced {len(new_entries)} new worktrees; refusing to guess.", file=sys.stderr)
             return 1
         new_path, new_slug, _ = new_entries[0]
         if wiki_path is not None:
             try:
                 worktree_cfg = _load_config(wiki_path, new_path)
             except SystemExit:
                 worktree_cfg = {}
         else:
             worktree_cfg = {}
         hub_subpath = worktree_cfg.get("hub_relative_path", ".")
         launch_path = resolve_hub_relative_path(new_path, hub_subpath)
         print(f"Opening VS Code in: {launch_path}", file=sys.stderr)
         subprocess.run(_build_code_argv(launch_path))
         return 0
     ```

  5. **Wire up `main()`.** Restructure the body after `active = _spawn_core.discover_active_worktrees(worktrees_dir)`:

     - **`--list` branch (unchanged semantics).** If `args.list`, print all of `active` (UNFILTERED — same as today) and return 0. Move this branch to immediately after `discover_active_worktrees` so the filter never runs in `--list` mode.
     - **`--new` branch.** If `args.new`, return `_spawn_and_open(worktrees_dir, active, wiki_path)`. Skip everything below.
     - **No active worktrees + no `--slug`/`--list`/`--new`.** Behave exactly as today's "auto-spawn fallback": delegate to `_spawn_and_open(worktrees_dir, active, wiki_path)` (here `active == []` so `pre_paths` is empty and any newly spawned worktree is the diff target). Return its rc.
     - **`--slug` branch.** Skip the filter. Resolve the slug against `active` (same code as today). If matched, `selected_path = matched[0]` and continue to the open path. If not matched, print the error and return 1.
     - **Default flow (no `--slug`, no `--new`, `active` non-empty).** Compute `filtered = _filter_open_worktrees(active, wiki_path, cfg.get("hub_relative_path", "."))`. If `filtered == []`, return `_spawn_and_open(worktrees_dir, active, wiki_path)` (empty-filter falls through to spawn per the discussion).
     - **Otherwise show the unified prompt.** Print `"Active worktrees:"` to stderr, then numbered entries with the same `slug — title` formatting as today. Print prompt: `f"<Enter> to spawn new task, 1-{len(filtered)} to open, q to quit: "` via `input(...)` (input goes to stdout/stderr per Python default; do NOT redirect). Loop up to 3 attempts:
       - `EOFError` → print `"[mill-vscode] No input available."` to stderr, return 1.
       - After `raw.strip()`: empty string → return `_spawn_and_open(worktrees_dir, active, wiki_path)` (note: `active` not `filtered` — pre-spawn snapshot must be the full pre-spawn picture).
       - `raw.lower() == "q"` → return 0.
       - Else `int(raw)` succeeds and `1 <= num <= len(filtered)` → `selected_path = filtered[num - 1][0]` and break out to open path.
       - Anything else → print `f"[mill-vscode] Invalid selection: {raw!r}"` to stderr, continue loop.
       - After 3 failed attempts → return 1.

  6. **Open path** (the existing block from `if wiki_path is not None: try: worktree_cfg = _load_config(...)` through `subprocess.run(code_argv)`) is unchanged. Both the `--slug` branch and the unified-prompt branch fall into it with `selected_path` set.

  7. **Drop the auto-select-when-single fast path** (`elif len(active) == 1: ...`) — removed unconditionally; the discussion's `unified-prompt` decision says always show the prompt.

  Do NOT touch any function not described above. Do NOT change argv/return semantics of `_build_code_argv` or `_load_spawn_main`. Do NOT alter the `--list` output format.

- **Commit:** `feat(mill-vscode): add --new flag, filter open worktrees, unified prompt`

### Card 4: extend `test-millpy-vscode.py`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/_vscode_processes.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add the following test blocks to `test-millpy-vscode.py`'s `main()` function. Preserve every existing test exactly as-is. Each new block follows the existing pattern (`with tempfile.TemporaryDirectory() as tmpdir: ...`, builds a fake repo via `_make_git_repo`, places `_write_active_marker` markers, sets up `patch(...)` chain, calls `mill_vscode.main([...])`, asserts on `subprocess_calls` / `input_calls` / `rc`). Patches: every new test patches `mill_vscode._vscode_processes.find_open_vscode_paths` (set via `return_value=<set of cmdlines>`). Where the test exercises spawn, also patch `mill_vscode._load_spawn_main` (with a `MagicMock` whose `return_value` is a callable that returns the rc the test wants) and `mill_vscode._spawn_core.discover_active_worktrees` with `side_effect=[<pre>, <post>]`.

  Test blocks to add (each prints `PASS:` / `FAIL:` and bumps `errors`):

  - **filter_excludes_open_worktree**: two active worktrees `task-alpha` and `task-beta` (markers written, `discover_active_worktrees` returns both). `find_open_vscode_paths.return_value = {Path(str(wt_alpha))}` (or `{Path(str(wt_alpha)).resolve()}`). User input `"1"`. Assert `subprocess.run` was called with `wt_beta` in argv (alpha was filtered out, so index 1 is now beta).
  - **filter_empties_list_calls_spawn_then_opens**: one active worktree `task-alpha`. `find_open_vscode_paths.return_value = {Path(str(wt_alpha))}`. Pre-spawn `discover_active_worktrees` returns `[(wt_alpha, "task-alpha", "Alpha")]`; post-spawn returns `[(wt_alpha, ...), (wt_beta, "task-beta", "Beta")]`. `_load_spawn_main` returns a MagicMock callable that returns 0. Assert that callable was called once with `[]` and `subprocess.run` was called with `wt_beta` in argv. (Side_effect supplies two values: initial fetch + post-spawn fetch.)
  - **q_quits_with_zero**: two active worktrees, `find_open_vscode_paths.return_value = set()` (no filter). User input `"q"`. Assert `rc == 0` and `subprocess.run` was NOT called.
  - **enter_spawns_and_opens**: two active worktrees `alpha` and `beta`, `find_open_vscode_paths.return_value = set()`. User input `""`. Pre-spawn discover returns `[alpha, beta]`; post-spawn returns `[alpha, beta, gamma]`. `_load_spawn_main` callable returns 0. Assert spawn callable called once with `[]` and `subprocess.run` called with `wt_gamma` in argv.
  - **new_flag_skips_list_and_opens_new**: `--new` flag passed. Two active worktrees `alpha` and `beta` (markers written; `discover_active_worktrees` returns both). Post-spawn returns `[alpha, beta, gamma]`. `find_open_vscode_paths` is NOT called (assert via `mock.assert_not_called()` or by patching it with a `MagicMock` and asserting `.called == False`). `input` is NOT called (use a `MagicMock` and assert not called). Spawn callable called once. `subprocess.run` called with `wt_gamma` in argv.
  - **spawn_returns_zero_no_new_entries**: user input `""` (or `--new`). `_load_spawn_main` callable returns 0; pre and post `discover_active_worktrees` both return the same single-entry list (no new). Assert `subprocess.run` was NOT called and `rc == 0`.
  - **spawn_returns_nonzero**: user input `""`. `_load_spawn_main` callable returns 1. Assert `subprocess.run` was NOT called and `rc == 1`.
  - **new_and_slug_mutex**: call `mill_vscode.main(["--new", "--slug", "x"])`. Assert it raises `SystemExit` with `code == 2`. Use `try/except SystemExit as exc: assert exc.code == 2`.
  - **probe_failure_falls_back**: two active worktrees `alpha` and `beta`. `find_open_vscode_paths.return_value = set()` (simulating probe failure). User input `"1"`. Assert `subprocess.run` was called with `wt_alpha` in argv (no filter applied; `alpha` is index 1).
  - **probe_returns_unrelated_paths**: two active worktrees `alpha` and `beta`. `find_open_vscode_paths.return_value = {Path("/some/unrelated/path")}`. User input `"2"`. Assert `subprocess.run` was called with `wt_beta` in argv (filter ran but excluded nothing; `beta` is index 2).

  Do NOT modify any pre-existing test. The existing `mill_vscode.subprocess.run` patch idiom (`side_effect=lambda a, **kw: subprocess_calls.append(...)`) is reused.

  When asserting `_load_spawn_main` was called, use the Mock idiom `spawn_callable.call_args_list == [call([])]` (mirroring the existing "no active worktrees, no flags → spawn called" test).

- **Commit:** `test(mill-vscode): cover filter, prompt, --new, spawn-diff paths`

### Card 5: rewrite `mill-vscode/SKILL.md`

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/scripts/millpy-vscode.py`
- **Edits:**
  - `plugins/mill/skills/mill-vscode/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite the body of `plugins/mill/skills/mill-vscode/SKILL.md` (preserve the YAML frontmatter `name: mill-vscode` and `description:` keys — `description:` may be updated, but the frontmatter delimiters `---` stay). The new body must:

  - State that the default flow lists active worktrees that DO NOT have a VS Code window already open in them, then prompts for `<Enter>` to spawn a new task and open it, a number to open one of the listed worktrees, or `q` to quit.
  - Document `--new`: "spawn a new task and open it without showing the existing-worktrees list." Note that `--new` and `--slug` are mutually exclusive.
  - Document `--slug X`: "open the worktree for slug X without showing the picker." (Unchanged from today; copy the existing wording.)
  - Document `--list`: "print every active worktree without launching VS Code or applying the filter." (Note: explicitly call out the no-filter behavior so script consumers don't expect the new filtering.)
  - Drop the line about auto-selecting when only one worktree is found (the auto-select fast-path is removed).
  - Update the `## Run it` example block to show all four flag forms:
    ```bash
    uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-vscode.py"          # default
    uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-vscode.py" --new    # spawn-and-open
    uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-vscode.py" --slug <slug>
    uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-vscode.py" --list
    ```
  - Mention briefly that the open-window detection is best-effort (Windows + Linux); on macOS or when the probe fails, all active worktrees are shown unfiltered.

  Keep the file under ~30 lines; this is a thin SKILL.md, not full documentation. Use `${CLAUDE_PLUGIN_ROOT}` in every example (already a project convention per `CLAUDE.md`'s "Conventions worth carrying").

- **Commit:** `docs(mill-vscode): document --new flag, filter, and unified prompt`

## Batch Tests

Run `python plugins/mill/unit_tests/run-all.py` from the worktree root. All existing `test-*.py` files must continue to pass; the additions in card 4 (and the standalone `test-vscode-processes.py` from batch 1) are picked up automatically by the runner's `glob("test-*.py")`. The frontmatter `verify:` runs the full suite because the integration touches behavior covered by `test-millpy-vscode.py` and depends on the helper exercised by `test-vscode-processes.py`.
