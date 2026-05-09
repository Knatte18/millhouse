# Batch: scope-helper

```yaml
task: 37 (A) — Codeguide bug-fix batch 1
batch: scope-helper
number: 1
cards: 2
verify: python plugins/codeguide/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Deliver the new `plugins/codeguide/scripts/resolve_scope.py` helper and a unit-test harness for it. The helper encapsulates default-scope enumeration for `/codeguide-update` — parent-branch detection plus the union of `<parent>..HEAD` with the current diff that fixes #210. SKILL.md edits in the next batch reference this script by path; the script must exist and pass tests before those edits ship. The batch is one Sonnet-sized unit because both pieces (helper + tests) live under `plugins/codeguide/` and share the same fixture conventions.

External interface this batch ships and the `skill-edits` batch consumes: the CLI shape `python <plugin-root>/scripts/resolve_scope.py [<args>]` with stdout = newline-separated absolute paths and stderr's last line = a one-line JSON summary `{mode, parent, base_branch, included_committed, included_diff}`. Exit code 0 even when output is empty.

Batch-local decisions (not in `## Shared Decisions`):

- **Synthetic git fixture** — every test scenario builds its own throwaway git repo via `tempfile.TemporaryDirectory()` + `subprocess.run(['git', '-C', tmp, 'init', '-b', 'main'])`. `user.email` and `user.name` are set per-repo with `git -C tmp config`. No global `~/.gitconfig` writes; no real network; no real codeguide tree.
- **`PASS:` / `FAIL:` per scenario** — mirroring `plugins/mill/unit_tests/test-active.py`. The runner counts only top-level pass/fail per file; scenario granularity is in the per-line prints for human debugging.

## Cards

### Card 1: Implement `resolve_scope.py`

- **Context:**
  - `plugins/codeguide/scripts/resolve.py`
  - `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Deletes:** none
- **Requirements:**
  - Module docstring at the top mirroring `resolve.py`'s style: a "Scope-resolution chain" section listing the four argument modes, a "Parent detection" section listing the three-step fallback, and a "Public API" section listing the CLI invocation and `enumerate_scope()` function signature.
  - Public function `enumerate_scope(args: list[str], cwd: pathlib.Path | None = None) -> tuple[list[pathlib.Path], dict]` — returns `(absolute_paths_deduped, summary_dict)`. The CLI wraps this. Internal helpers are prefixed `_`.
  - Argument-mode dispatch on `args` (the `argparse`-parsed positional list, equivalent to `$ARGUMENTS.split()`):
    - **No-arg** (`args == []`): see "No-arg behavior" below.
    - **Time arg** (single token matching regex `^\d+[hdw]$`, case-insensitive): use `git log --since="N hour|day|week ago" --name-only --pretty=format:` and collect the unique non-empty file paths.
    - **HEAD-rev arg** (single token starting with `HEAD~` or matching `^HEAD$` or a 7-40 char hex SHA): use `git diff --name-only <rev>..HEAD`.
    - **Explicit paths** (anything else): treat each token as a path; resolve relative to git toplevel; emit deduped absolute paths. No git invocation.
    - Mode names emitted in the summary: `"no-arg"`, `"time"`, `"head-rev"`, `"explicit"`.
  - **No-arg behavior:**
    - Resolve current branch via `git rev-parse --abbrev-ref HEAD`. If it returns `HEAD` (detached), treat as base-branch case (no widening).
    - Resolve `base_branch`: try `git symbolic-ref --short refs/remotes/origin/HEAD` — output is `origin/<name>`; strip `origin/` prefix. On non-zero exit, try `git rev-parse --verify origin/main` (use `main`); on non-zero, try `origin/master` (use `master`); on non-zero, set `base_branch = None`.
    - If `base_branch is None` OR `current_branch == base_branch`: scope = current diff = union of `git diff --name-only` (unstaged) and `git diff --cached --name-only` (staged). Set summary `parent = None`.
    - Otherwise: scope = union of `git diff --name-only <base_branch>..HEAD` (committed range — two-dot, not three) ∪ `git diff --name-only` ∪ `git diff --cached --name-only`. Set summary `parent = base_branch`.
  - **Output**: stdout = absolute paths, one per line, deduped (preserve first-seen order across the union sources committed-then-unstaged-then-staged), terminated with `\n`. stderr = the script may emit progress/debug freely; the **last non-empty line of stderr** must be a single-line JSON object `{"mode": <mode>, "parent": <branch-or-null>, "base_branch": <branch-or-null>, "included_committed": <int>, "included_diff": <int>}`. `included_committed` counts files from `<parent>..HEAD` only; `included_diff` counts files from staged+unstaged only; their sum may exceed the deduped stdout count.
  - **Exit code**: 0 in all the above paths. Non-zero only on hard errors (not in a git repo at all, malformed `--json` flag) — but those are CLI-shape errors, the helper itself returns gracefully on every documented input.
  - **Path handling**: every emitted path is an absolute `pathlib.Path` resolved against git toplevel. Files deleted in `<parent>..HEAD` are still emitted (the SKILL's orphan-doc flagging step needs them); do not filter by `Path.exists()`. Forward slashes are fine on Windows when emitted by git; do not normalize separators beyond what `pathlib.Path.resolve()` returns.
  - **Git invocations**: every `subprocess.run(['git', '-C', str(toplevel), ...], capture_output=True, text=True, encoding='utf-8')`. `toplevel` is resolved once via `git -C <cwd> rev-parse --show-toplevel`. On non-zero return, the helper does not crash unless the call is `rev-parse --show-toplevel` itself (only a "not in a git repo" hard error).
  - **CLI**: `argparse` parser with `nargs='*'` for positional `args`, no flags. `python resolve_scope.py` (no-arg), `python resolve_scope.py 1h`, `python resolve_scope.py HEAD~3`, `python resolve_scope.py path/a path/b` all valid. The CLI calls `enumerate_scope(args)` and prints stdout-then-stderr-summary as specified.
  - **Constraints from `## Shared Decisions`**: stdlib only; no imports from `plugins/mill/`; no reading of `task/status.md` or `.millhouse/config.yaml`.
  - **Final block at bottom**: `if __name__ == "__main__": sys.exit(_cli(sys.argv))` — same shape as `resolve.py`.
- **Commit:** `feat(codeguide): add resolve_scope.py for default-scope enumeration`

### Card 2: Add unit-test runner and `test-resolve-scope.py`

- **Context:**
  - `plugins/codeguide/scripts/resolve_scope.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-active.py`
- **Edits:** none
- **Creates:**
  - `plugins/codeguide/unit_tests/run-all.py`
  - `plugins/codeguide/unit_tests/test-resolve-scope.py`
- **Deletes:** none
- **Requirements:**
  - **`plugins/codeguide/unit_tests/run-all.py`**: structurally identical to `plugins/mill/unit_tests/run-all.py`. Same `main() -> int` body, same `PYTHONIOENCODING=utf-8` env override, same `if __name__ == "__main__": sys.exit(main())` tail. Docstring may say `"plugins/codeguide/unit_tests/"` instead of mill's; otherwise unchanged.
  - **`plugins/codeguide/unit_tests/test-resolve-scope.py`**: top-of-file docstring `"""Unit tests for plugins/codeguide/scripts/resolve_scope.py."""`. `sys.path.insert` line that resolves the `plugins/codeguide/scripts/` directory four levels up from the test file: `HUB = Path(__file__).resolve().parent.parent.parent.parent; sys.path.insert(0, str(HUB / "plugins" / "codeguide" / "scripts"))`. Import: `from resolve_scope import enumerate_scope` (no other imports from the module).
  - **Shared fixture helper inside the test file**: a `def _make_repo(tmp: Path, *, with_origin: bool, default_branch: str = "main") -> None` that runs `git init -b <default_branch>`, `git config user.email/user.name`, and (when `with_origin`) sets up a fake bare remote at `<tmp>/origin.git` plus `git remote add origin <tmp>/origin.git` and a remote-tracking branch via `git fetch origin`. Plus `def _commit(tmp: Path, files: dict[str, str], msg: str) -> str` that writes/overwrites the named files, `git add` them, `git commit -m`, returns the new SHA.
  - **`origin/HEAD` simulation**: after pushing the default branch to the fake bare origin, `git -C <tmp> remote set-head origin <branch>` registers `refs/remotes/origin/HEAD`. To simulate "no `origin/HEAD`" for scenarios 5–7, skip the `set-head` call.
  - **Scenarios** — one assertion block per scenario, each prints `PASS: <one-line-description>` on success. `main() -> int` returns 0 if every block printed PASS, 1 if any `AssertionError` was raised. All scenarios resolve `cwd=<tmp>` so `enumerate_scope([], cwd=Path(tmp))` reads the synthetic repo. Required scenarios (numbering local to the test file, not card numbers):
    1. **No-arg, on `main`, clean tree**: `_make_repo(with_origin=True)`, one commit, no working-tree edits → `paths == []`, `summary["parent"] is None`, `summary["base_branch"] == "main"`.
    2. **No-arg, on `main`, dirty tree**: same setup; create one unstaged file edit and one staged-only file edit → `paths` contains both files (deduped), `summary["parent"] is None`.
    3. **No-arg, on task branch, clean tree**: `_make_repo(with_origin=True)`; one commit on `main`; `git checkout -b feature`; two commits on `feature` editing files A and B; clean tree → `paths == [A, B]` (set-equal), `summary["parent"] == "main"`, `summary["included_committed"] == 2`, `summary["included_diff"] == 0`.
    4. **No-arg, on task branch, dirty tree**: scenario 3 + an unstaged edit to file C → `paths` is a deduped set of `{A, B, C}`, `summary["included_diff"] >= 1`.
    5. **No-arg, task branch, no `origin/HEAD`, has `main`**: `_make_repo(with_origin=True)` then explicitly skip `set-head`; verify the helper falls through to probing `origin/main`. Setup: commit on `main`, push, `git checkout -b feature`, edit + commit → `paths` = files in `main..HEAD`, `summary["base_branch"] == "main"`.
    6. **No-arg, task branch, no `origin/HEAD`, no `main`, has `master`**: same as 5 but the default branch was created as `master` (`_make_repo(default_branch="master")`) → `summary["base_branch"] == "master"`.
    7. **No-arg, task branch, no `origin/HEAD`, no `origin/main`, no `origin/master`**: `_make_repo(with_origin=False)`; commit on `main` locally; `git checkout -b feature`; edit + commit → `paths == []`, `summary["parent"] is None`, `summary["base_branch"] is None`. (Graceful degradation — no widening when no base can be found.)
    8. **Arg `HEAD~3`**: `_make_repo(with_origin=False)`; four commits each editing one file → `paths` = files from the last 3 commits.
    9. **Arg `1h`**: `_make_repo(with_origin=False)`; one commit → `paths` includes that commit's file. (Time-window is wide enough that "1h" always covers a just-made commit; do not test the exclusion side — that's a `git log` behavior, not the helper's.)
    10. **Arg explicit paths**: pass two relative paths (one valid, one nonexistent) → both come back as absolute paths in stdout; the helper does not filter by existence.
    11. **Files deleted in `parent..HEAD`**: scenario 3 setup but the second commit deletes file A → file A still appears in `paths` (`Path.exists()` is False but the helper does not filter).
    12. **Branch == base where base is `master`**: `_make_repo(default_branch="master", with_origin=True)`; clean tree on `master` → `paths == []` (on-base behavior, no widening).
    13. **Files modified in both `parent..HEAD` and current diff**: scenario 4 but the unstaged edit is to file A (which was also modified in the committed range) → `A` appears once in the deduped output, `summary["included_committed"] >= 1`, `summary["included_diff"] >= 1`.
  - **Test runner integration**: `python plugins/codeguide/unit_tests/run-all.py` (from the worktree root) discovers `test-resolve-scope.py` and exits 0 on PASS. Verify-command in the overview's Batch Index points at this script.
  - **No real network, no real LLM, no real codeguide tree** — all fixtures are throwaway tmp directories.
- **Commit:** `test(codeguide): add unit tests for resolve_scope.py`

## Batch Tests

`verify: python plugins/codeguide/unit_tests/run-all.py` runs every `test-*.py` under `plugins/codeguide/unit_tests/`. The only file in this batch is `test-resolve-scope.py`, covering all 13 scenarios listed in Card 2's Requirements. The runner exits 0 on PASS, 1 on any failure; mill-go's verify hook reads that exit code.

No integration test for the helper. The CLI shape is verified through scenario 10 (explicit paths) and the JSON-summary scenarios; the in-skill consumer (`codeguide-update` SKILL.md) is doc-only and reviewed in the next batch.
