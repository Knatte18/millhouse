# Discussion: millpy-vscode rework: hybrid spawn/pick + filter active editors

```yaml
task: 'millpy-vscode rework: hybrid spawn/pick + filter active editors'
slug: mill-vscode-rework
status: discussing
parent: main
```

## Problem

`millpy-vscode` lists every active worktree it finds, including the ones the user already has a VS Code window open in. The result is noise: the picker is dominated by entries that re-launching VS Code on would just refocus an existing window, and the user has to mentally filter for the worktree they actually still need to open. The script also has no first-class way to say "spawn a new task and open it" — that path is reachable only as a fallback when zero active worktrees exist.

The rework adds two changes: filter out worktrees whose path appears in any running VS Code process's cmdline, and unify the no-args entry point into a single prompt that lets the user pick from the (filtered) list, spawn-and-open, or quit.

## Scope

**In:**

- `plugins/mill/scripts/millpy-vscode.py` — rework `main()` to introduce the filter step, the unified prompt, and the new `--new` flag; preserve the existing `--slug` and `--list` behavior.
- New helper `plugins/mill/scripts/_vscode_processes.py` — `find_open_vscode_paths() -> set[Path]` cross-platform process probe.
- New unit test file `plugins/mill/unit_tests/test-vscode-processes.py` — parsing tests for canned PowerShell + `ps` output.
- Existing `plugins/mill/unit_tests/test-millpy-vscode.py` — add cases for filter/spawn/quit/`--new`/probe-failure.
- `plugins/mill/skills/mill-vscode/SKILL.md` — refresh the description so it documents the new prompt behavior and `--new`.

**Out:**

- `millpy-spawn.py` — unchanged. The new flow shells into spawn the same way the current `_load_spawn_main` path does.
- `_spawn_core.discover_active_worktrees` — unchanged. The filter runs on its output.
- `hub_relative_path` resolution — already honored via `resolve_hub_relative_path`; reused as-is.
- `_vscode.py` — unchanged. Settings-writing belongs in that module; process probing is a separate concern and lives in its own file.
- VS Code Insiders detection — explicitly not supported. The codebase only uses the stable `code` launcher.
- Adding `psutil` or any other runtime dependency.
- Changing the worktree color picker, `.vscode/settings.json` shape, or any other setup logic.

## Decisions

### filter-rather-than-mark

- Decision: Worktrees whose launch path matches any open VS Code cmdline are **removed from the picker list**, not displayed with an `(open)` marker.
- Rationale: User asked for "filtering out worktrees with an active editor removes the noise" — marking them keeps the noise. The user's intent is to see only the actionable choices.
- Rejected: `(open)` / `(free)` annotation; would still leave the user reading every line.

### unified-prompt

- Decision: After the filter step, always show a numbered list of remaining active worktrees followed by a single prompt: `<Enter>` spawns a new task and opens it; a number opens that index; `q` (case-insensitive) quits with exit code 0.
- Rationale: One consistent input grammar regardless of how many entries are listed. Drops the auto-select-when-single shortcut so behavior doesn't flip silently when the filter narrows the list to one entry.
- Rejected: Auto-open when filtered list has exactly one entry — surprising mode flip; user explicitly chose option 1 in Q2.

### empty-filter-falls-through-to-spawn

- Decision: When the filter empties the list (every active worktree is already open in VS Code), the script proceeds straight to spawn-and-open without showing a prompt — matching today's empty-active-worktrees fallback.
- Rationale: Symmetry with the existing zero-active-worktrees path. The user has no actionable picker entries, so the only sensible default is "make a new one."
- Rejected: Show the empty-list prompt with just `<Enter>` and `q` — extra keystroke for no information.

### post-spawn-identification

- Decision: All three spawn-and-open paths (`<Enter>` at the prompt, `--new`, empty-filter fall-through, and the existing zero-active-worktrees fallback) follow the same pre/post snapshot procedure to identify the newly created worktree:
  1. Compute the set `pre = {entry.path for entry in discover_active_worktrees(worktrees_dir)}` BEFORE invoking `_load_spawn_main([])`.
  2. Invoke `_load_spawn_main([])`. If it returns non-zero, propagate that exit code.
  3. Re-run `discover_active_worktrees(worktrees_dir)` and compute `new_entries = [e for e in post if e.path not in pre]`.
  4. Exactly one new entry → that's the spawn target; resolve its launch path via `resolve_hub_relative_path` and open it via `code <launch_path>`.
  5. Zero new entries → spawn was cancelled (e.g. user aborted the picker, no backlog) → exit 0 silently with a one-line stderr message.
  6. Multiple new entries → defensively bail with stderr message and exit 1. (Current spawn semantics produce exactly one new worktree per invocation; this branch is a safety net.)
- Rationale: `millpy-spawn.main` returns only `int`; printing the worktree path via stdout would require modifying spawn (out of scope per the task). The diff-based approach is local to `millpy-vscode` and uses only public helpers.
- Rejected: Reading the active marker from disk to identify the new worktree — still requires the pre/post diff to know *which* new directory was just written. Modifying `millpy-spawn.main` to emit a stable stdout token — broader scope; violates "touches `millpy-vscode.py` only" from the task.

### list-flag-unfiltered

- Decision: `--list` continues to print **every** active worktree without filtering. The flag is for tooling and scripts; its output must be deterministic regardless of which VS Code windows happen to be open at probe time.
- Rationale: Filter behavior is for the interactive default. A scripted consumer of `--list` (e.g. a future status report) would be surprised by output that depends on running editors.
- Rejected: Filtered `--list`; `(open)`-annotated `--list`.

### probe-launch-path-only

- Decision: The probe matches a worktree against open VS Code cmdlines using the **launch path** (i.e. `worktree + hub_relative_path`, the same path `_build_code_argv` passes to `code`). Case-insensitive on Windows.
- Rationale: That's exactly the arg the script passes when opening, and exactly what VS Code records in its process cmdline. Matching only the worktree root would miss the hub-relative-path layout; matching both adds false positives without value.
- Rejected: Match worktree root and launch path; match worktree root only.

### code-exe-only

- Decision: On Windows, only `Code.exe` (stable VS Code) is queried. On POSIX, only processes whose argv[0] basename contains `code` are kept (covers `code` and `/usr/share/code/code` etc.).
- Rationale: The rest of the codebase only supports stable VS Code. Adding Insiders detection introduces a false-positive risk for users who have both installed but use only one.
- Rejected: `Code.exe` + `Code - Insiders.exe`; broader argv-substring matching.

### vscode-processes-helper-module

- Decision: Process detection lives in a new helper `plugins/mill/scripts/_vscode_processes.py` with one public function `find_open_vscode_paths() -> set[Path]`.
- Rationale: Pure parser → easy to unit-test by mocking `_subprocess_util.run`. Keeps `_vscode.py` (settings.json writer) focused. Inline functions in `millpy-vscode.py` would mix CLI and parsing concerns.
- Rejected: Inline private functions in the CLI script; bolting onto `_vscode.py`.

### posix-uses-ps-linux-only

- Decision: POSIX detection uses `ps -ww -A -o command=`, but the parser is **Linux-only** in practice. macOS launches VS Code via `/Applications/Visual Studio Code.app/Contents/MacOS/Electron …` (path with embedded spaces); the basename heuristic on the first whitespace-token would parse the first token as `/Applications/Visual` (basename `Visual`) and silently drop every macOS Code process. macOS therefore degrades to no-filter via the existing probe-failure fallback (the parser returns the empty set).
- Rationale: The user runs Windows; macOS is not a stated target for this task. Carrying a special-case for the Electron/`Visual Studio Code.app` cmdline shape adds parser complexity for an unused platform. The silent fallback is acceptable: macOS users see the existing (unfiltered) picker and lose nothing.
- Rejected: Special-case macOS by also keeping lines whose argv[0] basename is `Electron` AND whose cmdline contains `Visual Studio Code` — extra rule for a platform we don't support. Replace the basename heuristic with raw substring containment of `code` — too broad; matches `vscodium`, `code-server`, anything with `code` in argv. `/proc` enumeration; `/proc`-with-`ps`-fallback — two code paths for one signal.

### windows-uses-powershell-cim

- Decision: Windows detection invokes `powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='Code.exe'\" | Select-Object -ExpandProperty CommandLine"`. Output is split on newlines and substring-matched.
- Rationale: `Get-CimInstance` is the modern API (`Get-WmiObject` and `wmic` are deprecated on Windows 11). `-NoProfile` keeps startup fast and avoids profile-script side effects.
- Rejected: `psutil` (adds a dep that has to be vendored or pulled into `pyproject.toml`); `wmic process` (deprecated, will eventually be removed from the OS image); raw `tasklist` (cmdline output is truncated).

### probe-failure-silent-fallback

- Decision: If the probe subprocess errors (non-zero exit, missing command, `subprocess.TimeoutExpired`), `find_open_vscode_paths` returns an empty set. The picker then shows every worktree as "not open" — the script remains usable.
- Rationale: The script is interactive and frequent. A user-facing failure on probe error would block the picker for noise. An empty probe result degrades gracefully into "no filtering applied today."
- Rejected: Print warning to stderr (most users would dismiss it); abort with non-zero exit (blocks the picker for a non-essential signal).

### probe-timeout-5s

- Decision: The probe subprocess is invoked with `_subprocess_util.run(..., timeout=5)`. On `TimeoutExpired`, the helper returns an empty set per the silent-fallback decision.
- Rationale: PowerShell + WMI can occasionally wedge for several seconds on a stressed machine. 5s is a reasonable upper bound — past that, the user is better off with no filter than a hung picker.
- Rejected: 2s (some cold PowerShell starts approach 2s); no timeout (a wedged probe hangs the picker indefinitely).

### path-comparison-resolved-exact-or-trailing-slash

- Decision: A worktree is "open" iff its launch path (after `Path(launch_path).resolve()`) appears in a VS Code cmdline as **exactly that path** or as **that path with a single trailing path separator** — and nowhere else. Sub-paths do NOT count as a match. Concretely, the helper `_path_matches_cmdline(launch_path: Path, cmdline: str) -> bool` returns True iff at least one of the following holds (after case-folding both sides on Windows):
  1. The whitespace-bounded token form `<sep><resolved_launch_path><sep>` exists in `cmdline` (where `<sep>` is whitespace, the start of string, the end of string, or a quote character `"`/`'`).
  2. The same with a single trailing path separator appended: `<sep><resolved_launch_path><os.sep><sep>`.
  Specifically, `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo")` → True, `"code /wts/foo/"` → True, `"code /wts/foo/src"` → **False**, `"code /wts/foo-bar"` → False.
- Rationale: The decision states "match the launch path." A user who manually opened a sub-folder of the worktree expressed a different intent (perhaps they're working in a sub-tree on purpose); the script should still surface the worktree as an actionable picker entry. The path-separator boundary exists solely as a *prefix-collision guard* (so `/wts/foo` doesn't match `/wts/foo-bar`), not as a sub-path-inclusion mechanism.
- Rejected: Sub-path inclusion (broader match, but conflates intents — see rationale above). Strict equality without trailing-slash tolerance (misses `code <path>/` invocations VS Code may emit). Raw substring without boundary guard (prefix collisions).

### new-and-slug-mutually-exclusive

- Decision: `--new` and `--slug` are mutually exclusive at the argparse layer. Passing both produces a usage error and exit 2.
- Rationale: The two flags express conflicting intents (new task vs. open existing). Fail fast rather than silently picking one.
- Rejected: `--slug` wins silently; allow `--new --slug X` as "spawn task X" semantics (not requested).

### prompt-input-grammar

- Decision: The unified prompt accepts: empty input (`<Enter>`) → spawn-and-open; a bare integer N in [1, len(filtered_list)] → open index N; `q` or `Q` (after `.strip()`) → exit 0 with no launch. Any other input re-prompts; up to 3 attempts, then exit 1.
- Rationale: Matches the user's stated grammar. Re-prompts mirror the multi-pick prompt in `_spawn_core._prompt_numbered_multi`.
- Rejected: Single-shot validation (single typo costs a full re-run); accept slug strings (overlaps `--slug X` semantics).

## Technical context

### Files touched

- [plugins/mill/scripts/millpy-vscode.py](plugins/mill/scripts/millpy-vscode.py) — `main()` rework. The argparse block adds `--new` (`store_true`) and the `--new` / `--slug` mutex. After `discover_active_worktrees(worktrees_dir)` runs, the filter step calls `_vscode_processes.find_open_vscode_paths()` and removes entries whose `resolve_hub_relative_path(entry_path, hub_subpath)` matches any element of the returned set (using `_vscode_processes._path_matches_cmdline` for boundary-safe substring containment). The numbered prompt is replaced with the unified prompt described in the `prompt-input-grammar` decision. `--new` short-circuits to a helper `_spawn_and_open(worktrees_dir)` (described below) which performs the pre/post snapshot diff per the `post-spawn-identification` decision. The same helper is invoked from the empty-filter fall-through, the existing zero-active-worktrees fallback, and the `<Enter>` branch of the prompt.

  The `_spawn_and_open(worktrees_dir, hub_subpath_resolver)` helper:
  1. Snapshots `pre = {entry.path for entry in _spawn_core.discover_active_worktrees(worktrees_dir)}`.
  2. Calls `rc = _load_spawn_main()([])`. If `rc != 0`, returns `rc`.
  3. Recomputes `post = _spawn_core.discover_active_worktrees(worktrees_dir)`.
  4. `new_entries = [e for e in post if e[0] not in pre]`.
  5. If `len(new_entries) == 0`: print `"[mill-vscode] spawn produced no new worktree; nothing to open."` to stderr; return 0.
  6. If `len(new_entries) > 1`: print `f"[mill-vscode] spawn produced {len(new_entries)} new worktrees; refusing to guess."` to stderr; return 1.
  7. Resolve the single new entry's launch path via `resolve_hub_relative_path`, invoke `subprocess.run(_build_code_argv(launch_path))`, return 0.
- [plugins/mill/scripts/_vscode_processes.py](plugins/mill/scripts/_vscode_processes.py) — new helper. Exposes `find_open_vscode_paths() -> set[Path]`. Internal `_probe_windows()` and `_probe_posix()` shell out via `_subprocess_util.run` with `timeout=5` and `check=False`. Both functions are pure parsers (input: cmdline-string-iterable; output: set of resolved Paths). The OS dispatch picks the right `_probe_*` based on `os.name`. All exceptions inside the probe (subprocess error, parse error) are caught and produce an empty set.
- [plugins/mill/unit_tests/test-vscode-processes.py](plugins/mill/unit_tests/test-vscode-processes.py) — new test file. Tests parse fixed canned strings for both PowerShell and `ps` output. The subprocess call itself is mocked (`patch("_vscode_processes._subprocess_util.run", ...)`) so the tests run on any platform.
- [plugins/mill/unit_tests/test-millpy-vscode.py](plugins/mill/unit_tests/test-millpy-vscode.py) — additions only; no existing test is modified except the two-worktree-pick test which currently relies on auto-select-when-single is not affected since it has two worktrees, and the auto-select test (none exists explicitly — the current implementation auto-selects when `len(active) == 1`, but no test asserts that behavior). New cases: (a) filter excludes one of two worktrees → picker shows only the non-open one; (b) filter empties the list → spawn called; (c) `q` input → exit 0, no `subprocess.run` call; (d) `--new` flag → spawn called regardless of active worktrees, then open; (e) `--new --slug X` → argparse error, exit 2; (f) probe-failure → all entries shown.
- [plugins/mill/skills/mill-vscode/SKILL.md](plugins/mill/skills/mill-vscode/SKILL.md) — description rewritten. Document `--new`, the filter, and the new prompt grammar. Drop the line about auto-selecting when only one worktree is found.

### Reused helpers

- [discover_active_worktrees](plugins/mill/scripts/_spawn_core.py#L152-L202) — unchanged; called as today.
- [resolve_hub_relative_path](plugins/mill/scripts/_paths.py) — unchanged; called once per worktree to compute the launch path used for both filtering and the eventual `code` invocation.
- [_subprocess_util.run](plugins/mill/scripts/_subprocess_util.py) — `_vscode_processes` uses it with `timeout=5` and `check=False`. The breadcrumb output is acceptable; tests that don't want the noise can pipe stderr.
- [_load_spawn_main](plugins/mill/scripts/millpy-vscode.py#L52-L57) — unchanged; reused on both the existing zero-active-worktrees path and the new `--new` and empty-filter paths.

### Probe parser details

PowerShell `Get-CimInstance Win32_Process -Filter "Name='Code.exe'"` returns one CommandLine per process on its own line (potentially with quotes around paths containing spaces). The parser splits on `\r\n`, strips empty lines, and stores each line verbatim. Matching uses `_path_matches_cmdline` on a case-folded copy.

`ps -ww -A -o command=` returns one line per process with no header. The parser keeps lines whose first whitespace-separated token's basename starts with `code` (covers `code`, `/usr/share/code/code`, `/opt/visual-studio-code/code`). macOS's `/Applications/Visual Studio Code.app/Contents/MacOS/Electron` is intentionally not covered — see decision `posix-uses-ps-linux-only`. Matching uses `_path_matches_cmdline` on the raw line; POSIX paths are case-sensitive.

### Path matching semantics

Given a launch_path computed from `resolve_hub_relative_path(worktree_path, hub_subpath)`:

1. Resolve to absolute via `Path(launch_path).resolve()`. Convert to string `s`.
2. On Windows, lowercase `s` and lowercase the cmdline haystack before all comparisons.
3. The helper `_path_matches_cmdline(launch_path: Path, cmdline: str) -> bool` returns True iff `s` appears in `cmdline` either bare or with a single trailing `os.sep`, in either case bounded on both sides by one of: start-of-string, end-of-string, ASCII whitespace, `"`, or `'`. Sub-paths and prefix collisions return False. Pseudo-code:
   ```
   def _path_matches_cmdline(launch_path, cmdline):
       s = str(launch_path.resolve())
       hay = cmdline
       if os.name == "nt":
           s, hay = s.lower(), hay.lower()
       boundaries = {"", " ", "\t", "\"", "'"}
       for needle in (s, s + os.sep):
           idx = hay.find(needle)
           while idx != -1:
               left = hay[idx - 1] if idx > 0 else ""
               right_index = idx + len(needle)
               right = hay[right_index] if right_index < len(hay) else ""
               if left in boundaries and right in boundaries:
                   return True
               idx = hay.find(needle, idx + 1)
       return False
   ```
   This collapses the three cases (`code <s>`, `code <s>/`, end-of-string) into a single boundary check. Sub-path inputs like `code /wts/foo/src` fail because the right-boundary check sees `/`.

### Mocking strategy in tests

`test-vscode-processes.py` patches `_vscode_processes._subprocess_util.run` to return a `subprocess.CompletedProcess` whose stdout holds canned cmdline output. Tests assert on the resulting set of Paths.

`test-millpy-vscode.py` patches `mill_vscode._vscode_processes.find_open_vscode_paths` directly so existing tests don't need to construct fake cmdline output. The new test cases set the patch's return value to an explicit set of launch paths.

### Existing test compatibility

The current "two worktrees, user picks first" test does not assert auto-select-when-single (it has two entries and exercises the picker). It does pass `input` returning `"1"`. Under the new prompt grammar, `"1"` still selects index 1, so the test continues to pass without change.

The current "no active worktrees, no flags → spawn called, new worktree opened" test continues to pass because the new code shells into spawn the same way when the (post-filter) list is empty.

The current `--list` test continues to pass because `--list` keeps its unfiltered semantics.

The current `--slug` and `hub_relative_path` tests continue to pass because those code paths are unchanged.

## Constraints

- **No new runtime dependencies.** `psutil` is rejected. The probe must use shell-out to system tools (`powershell` on Windows, `ps` on POSIX) routed through `_subprocess_util.run`.
- **`${CLAUDE_PLUGIN_ROOT}` invariant.** All intra-plugin paths in SKILL.md examples use `${CLAUDE_PLUGIN_ROOT}` (per [CLAUDE.md](CLAUDE.md) "Conventions worth carrying").
- **No junctions in code paths.** Path resolution stays inside the existing helpers. The probe consumes only paths already resolved by `resolve_hub_relative_path` and OS process tables — no junction traversal.
- **Helpers carry no `if __name__ == "__main__":` block** (per [CLAUDE.md](CLAUDE.md) "Repo layout pointers"). `_vscode_processes.py` is a helper, not a CLI.
- **Scratch lives at `<cwd>/.scratch/`, not under `.millhouse/`** — irrelevant to this task; flagged for completeness because the new helper writes nothing to disk.
- **PYTHONPATH on Windows.** Test invocations follow the existing pattern: `python plugins/mill/unit_tests/run-all.py` from the worktree root, with `_subprocess_util.run` resolved via the existing `sys.path.insert(0, ...)` in the test file.

## Testing

Two test files cover this work.

### test-vscode-processes.py (new)

Per-helper unit tests for `_vscode_processes`. Test fixtures supply canned subprocess output via `patch("_vscode_processes._subprocess_util.run", ...)`. Cases:

- **windows_parser_basic** — given canned PowerShell output with three CommandLine values referencing two distinct worktree paths, returns the expected set of two Paths (after resolve + lowercase).
- **windows_parser_quoted_paths** — paths containing spaces appear quoted in PowerShell output; parser preserves them.
- **windows_parser_empty_output** — empty stdout returns the empty set.
- **posix_parser_basic** — given canned `ps -ww -A -o command=` output with `code` and non-`code` processes, returns only paths from lines whose argv[0] basename starts with `code`.
- **posix_parser_no_code_processes** — `ps` output with no Code.exe / code lines returns the empty set.
- **probe_subprocess_nonzero_exit** — `_subprocess_util.run` returns rc=1; `find_open_vscode_paths` returns the empty set.
- **probe_subprocess_timeout** — `_subprocess_util.run` raises `TimeoutExpired`; helper returns the empty set.
- **probe_subprocess_oserror** — `_subprocess_util.run` raises `FileNotFoundError` (e.g. `powershell` missing); helper returns the empty set.
- **path_match_helper_bare** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo")` returns True.
- **path_match_helper_trailing_slash** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo/")` returns True.
- **path_match_helper_subpath_excluded** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo/src")` returns **False** (sub-path is not a match per the `path-comparison-resolved-exact-or-trailing-slash` decision).
- **path_match_helper_prefix_collision** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo-bar")` returns False.
- **path_match_helper_quoted_path** — `_path_matches_cmdline(Path("/wts/foo bar"), 'code "/wts/foo bar"')` returns True (quote characters count as boundaries).
- **path_match_helper_end_of_string** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo")` (no trailing whitespace) returns True (end-of-string is a boundary).
- **path_match_helper_windows_case_insensitive** — when run with `os.name == "nt"` patched, `/WTS/FOO` matches `/wts/foo`.

These are TDD candidates: the parser is pure, runnable on any platform, and the failure modes are easy to express as test inputs.

### test-millpy-vscode.py (additions)

End-to-end picker behavior, with `_vscode_processes.find_open_vscode_paths` patched to return controlled sets. Cases (added — existing cases preserved):

- **filter_excludes_open_worktree** — two active worktrees `alpha` and `beta`. `find_open_vscode_paths` returns `{path_to_alpha_launch}`. The numbered list shown to the user contains only `beta`. User input `1` opens `beta`.
- **filter_empties_list_calls_spawn_then_opens** — one active worktree `alpha`, filter returns `{path_to_alpha_launch}` → empty filtered list. Pre-spawn `discover_active_worktrees` returns `[alpha]`; post-spawn returns `[alpha, beta]`. Assert `_load_spawn_main` is invoked exactly once with `[]`, then `subprocess.run` is invoked with `code <beta launch_path>` (the new entry from the post-spawn diff).
- **q_quits_with_zero** — two active worktrees, neither filtered, user input `q` → exit 0, `subprocess.run` not called for `code`.
- **enter_spawns_and_opens** — user input `""`. Pre-spawn `discover_active_worktrees` returns `[alpha, beta]`; post-spawn returns `[alpha, beta, gamma]`. Assert `_load_spawn_main([])` is called once, then `subprocess.run` called for `code <gamma launch_path>` (the diff identifies `gamma` as the new entry).
- **new_flag_skips_list_and_opens_new** — `--new` flag, two active worktrees present, neither filtered. List is NOT shown (assert no `input()` call). Pre/post-spawn diff identifies the new worktree; `_load_spawn_main([])` invoked, then `code` invoked with the new entry's launch path.
- **spawn_returns_zero_no_new_entries** — user pressed `<Enter>` (or `--new`); `_load_spawn_main` returns 0 but the post-spawn diff finds zero new entries (e.g. user aborted spawn's task picker). Assert `subprocess.run` for `code` is NOT called and the script exits 0 with a stderr breadcrumb.
- **spawn_returns_nonzero** — `_load_spawn_main` returns 1. Assert `subprocess.run` for `code` is NOT called and the script exits with that non-zero code.
- **new_and_slug_mutex** — `mill_vscode.main(["--new", "--slug", "x"])` raises SystemExit(2) (argparse mutex error).
- **probe_failure_falls_back** — `find_open_vscode_paths` returns the empty set (simulating probe failure); the picker displays all active worktrees unfiltered.
- **probe_returns_unrelated_paths** — `find_open_vscode_paths` returns a set with paths that don't match any worktree; no entries are filtered.

These are added to `test-millpy-vscode.py` rather than a new file because they exercise the `main()` integration; the pure-parser tests are isolated in `test-vscode-processes.py`.

## Q&A log

- **Q:** Filter, mark, or annotate already-open worktrees? **A:** Filter (remove from list).
- **Q:** Keep auto-select-when-single? **A:** No — always show the unified prompt.
- **Q:** `--list` filter behavior? **A:** Unchanged — show all, no filter.
- **Q:** Match scope for "VS Code is open here"? **A:** Match launch path (worktree + `hub_relative_path`) only; case-insensitive on Windows.
- **Q:** Detect `Code.exe` only or also Insiders? **A:** Stable `Code.exe` only; codebase doesn't support Insiders.
- **Q:** Where does the process-probe code live? **A:** New helper `_vscode_processes.py` exposing `find_open_vscode_paths() -> set[Path]`.
- **Q:** POSIX detection algorithm? **A:** `ps -ww -A -o command=`, Linux-only in practice. macOS degrades to no-filter via the silent probe-failure fallback (Electron-based VS Code launch shape isn't matched by the basename heuristic, and macOS isn't a stated target).
- **Q:** Windows detection algorithm? **A:** PowerShell `Get-CimInstance Win32_Process -Filter "Name='Code.exe'"`, `-NoProfile`.
- **Q:** Probe failure handling? **A:** Silent fallback — return empty set, show all worktrees.
- **Q:** `--new` and `--slug` interplay? **A:** Mutually exclusive at argparse layer.
- **Q:** Probe timeout? **A:** 5s via `_subprocess_util.run(..., timeout=5)`; `TimeoutExpired` falls back to empty set.
- **Q:** Prompt input grammar? **A:** Empty → spawn; integer N → open index; `q`/`Q` → exit 0; otherwise re-prompt up to 3 times, then exit 1.
- **Q:** Path comparison normalization? **A:** `Path.resolve()` on both sides, case-insensitive on Windows. Match is exact-or-with-trailing-slash, bounded by whitespace/quote/start/end-of-string. Sub-paths do NOT count as a match; the boundary check exists solely as a prefix-collision guard.
- **Q:** Post-spawn worktree identification? **A:** Pre/post snapshot diff of `discover_active_worktrees`; the single new entry is the spawn target. Zero new → exit 0; multiple new → exit 1 (defensive — current spawn semantics produce exactly one).
- **Q:** Test scope? **A:** New `test-vscode-processes.py` for parsing; additions to `test-millpy-vscode.py` for picker integration including the post-spawn diff cases.
