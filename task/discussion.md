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

### posix-uses-ps-not-proc

- Decision: POSIX detection uses `ps -ww -A -o command=` (Linux + macOS portable). `-ww` disables truncation; `-A` selects all processes; `-o command=` prints the command column with no header.
- Rationale: Single subprocess covers Linux + macOS uniformly. `/proc/<pid>/cmdline` is Linux-only and would force a second code path for macOS users with no win.
- Rejected: `/proc` enumeration; `/proc`-with-`ps`-fallback (two code paths for one signal).

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

### path-comparison-resolved-substring

- Decision: A worktree is "open" iff its launch path (after `Path(launch_path).resolve()`) appears as a substring in any VS Code cmdline (also after appropriate normalization). On Windows, comparison is case-insensitive.
- Rationale: VS Code preserves the path it received in argv. Resolving handles `..` and case-folding handles Windows. Substring rather than equality lets the match survive when VS Code re-emits the path inside a longer cmdline (e.g. `code --new-window <path>`).
- Rejected: Strict equality (misses real matches when VS Code rewrites argv); raw substring without resolve (false positives via path prefix collisions, e.g. `/wts/foo` matching `/wts/foo-bar`). Mitigation for the false-positive case: append the platform path separator to the haystack-and-needle before substring matching, or check the trailing character is a path boundary.

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

- [plugins/mill/scripts/millpy-vscode.py](plugins/mill/scripts/millpy-vscode.py) — `main()` rework. The argparse block adds `--new` (`store_true`) and the `--new` / `--slug` mutex. After `discover_active_worktrees(worktrees_dir)` runs, the filter step calls `_vscode_processes.find_open_vscode_paths()` and removes entries whose `resolve_hub_relative_path(entry_path, hub_subpath)` matches any element of the returned set. The numbered prompt is replaced with the unified prompt described in the `prompt-input-grammar` decision. `--new` short-circuits to `_load_spawn_main()([])` followed by re-discovery and `code <new launch_path>`.
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

PowerShell `Get-CimInstance Win32_Process -Filter "Name='Code.exe'"` returns one CommandLine per process on its own line (potentially with quotes around paths containing spaces). The parser splits on `\r\n`, strips empty lines, and stores each line verbatim. Matching uses substring containment on a case-folded copy.

`ps -ww -A -o command=` returns one line per process with no header. The parser keeps lines whose first whitespace-separated token's basename starts with `code` (covers `code`, `/usr/share/code/code`, `/Applications/Visual Studio Code.app/Contents/MacOS/Electron --... code`). Matching uses substring containment on the raw line — POSIX paths are case-sensitive.

### Path matching semantics

Given a launch_path computed from `resolve_hub_relative_path(worktree_path, hub_subpath)`:

1. Resolve to absolute via `Path(launch_path).resolve()`. Convert to string `s`.
2. On Windows, lowercase `s` and lowercase the cmdline haystack.
3. To avoid `/wts/foo` matching `/wts/foo-bar`, the substring search appends a path-separator-or-end-of-string sentinel: search for `s` followed by `os.sep` OR for `s` at end-of-string. (Concretely: `(s + os.sep) in cmdline` OR `cmdline.rstrip().endswith(s)` OR `(' ' + s) in cmdline.rstrip() + ' '` — the implementation is one helper function `_path_matches_cmdline(launch_path: Path, cmdline: str) -> bool` that the unit tests cover with both positive and prefix-collision negative cases.)

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
- **path_match_helper_positive** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo")` returns True.
- **path_match_helper_endsep** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo/src")` returns True.
- **path_match_helper_prefix_collision** — `_path_matches_cmdline(Path("/wts/foo"), "code /wts/foo-bar")` returns False.
- **path_match_helper_windows_case_insensitive** — when run with `os.name == "nt"` patched, `/WTS/FOO` matches `/wts/foo`.

These are TDD candidates: the parser is pure, runnable on any platform, and the failure modes are easy to express as test inputs.

### test-millpy-vscode.py (additions)

End-to-end picker behavior, with `_vscode_processes.find_open_vscode_paths` patched to return controlled sets. Cases (added — existing cases preserved):

- **filter_excludes_open_worktree** — two active worktrees `alpha` and `beta`. `find_open_vscode_paths` returns `{path_to_alpha_launch}`. The numbered list shown to the user contains only `beta`. User input `1` opens `beta`.
- **filter_empties_list_calls_spawn** — one active worktree `alpha`, filter returns `{path_to_alpha_launch}` → empty filtered list → `_load_spawn_main` is invoked exactly once with `[]`.
- **q_quits_with_zero** — two active worktrees, neither filtered, user input `q` → exit 0, `subprocess.run` not called for `code`.
- **enter_spawns_and_opens** — user input `""` → `_load_spawn_main` called, then `subprocess.run` called for `code <new launch_path>`.
- **new_flag_skips_list** — `--new` flag, two active worktrees present, neither filtered → list is NOT shown (assert no `input()` call), `_load_spawn_main` invoked, then `code` invoked.
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
- **Q:** POSIX detection algorithm? **A:** `ps -ww -A -o command=` (Linux + macOS portable).
- **Q:** Windows detection algorithm? **A:** PowerShell `Get-CimInstance Win32_Process -Filter "Name='Code.exe'"`, `-NoProfile`.
- **Q:** Probe failure handling? **A:** Silent fallback — return empty set, show all worktrees.
- **Q:** `--new` and `--slug` interplay? **A:** Mutually exclusive at argparse layer.
- **Q:** Probe timeout? **A:** 5s via `_subprocess_util.run(..., timeout=5)`; `TimeoutExpired` falls back to empty set.
- **Q:** Prompt input grammar? **A:** Empty → spawn; integer N → open index; `q`/`Q` → exit 0; otherwise re-prompt up to 3 times, then exit 1.
- **Q:** Path comparison normalization? **A:** `Path.resolve()` on both sides, case-insensitive on Windows, substring match with path-separator boundary to avoid prefix collisions.
- **Q:** Test scope? **A:** New `test-vscode-processes.py` for parsing; additions to `test-millpy-vscode.py` for picker integration.
