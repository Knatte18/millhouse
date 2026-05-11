# Batch: defensive-guards

```yaml
task: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner
batch: defensive-guards
number: 1
cards: 6
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Adds three defensive guards across `_paths.py` and `_sibling.py` (mill + codeguide twin) so any script invoked with cwd inside the wiki repo halts immediately with a clear `SystemExit` (or `ValueError` for `_sibling.resolve_path`) instead of producing nonsense paths like `wiki.wiki`. Each guard is covered by new unit tests in `test-paths.py` and `test-sibling.py`. The batch is the load-bearing fix for the 2026-05-11 incident where a stray `cd .wiki && git pull --ff-only` in an LLM thread cascaded into committing a bg-log to wiki origin.

External interface for downstream batches: the new error strings are stable and grep-able (see the `error-message-text` Shared Decision); batch 2's walker test does not depend on them, but human readers searching for the error encounter consistent text.

Batch-local decision: the guard inside `resolve_wiki_path` performs the **name check only** (`git_toplevel.name == "wiki"`), and `resolve_git_root` owns the full belt-and-suspenders (name check + path-equality with the resolved wiki path). This split avoids circular logic inside `resolve_wiki_path` (which is the function that resolves the wiki path).

## Cards

### Card 1: Add `resolve_wiki_path` defensive name-check

- **Context:**
  - `plugins/mill/scripts/_sibling.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** At the top of `_paths.resolve_wiki_path(git_toplevel)` (before any config IO, before the existing `main_root = resolve_main_worktree_root(git_toplevel)` line), add a check that raises `SystemExit` with the literal error message from the `error-message-text` Shared Decision when `Path(git_toplevel).name == "wiki"`. Substitute `{wiki_path}` in the message with `str(git_toplevel)`. Do NOT add a path-equality check here — that lives in `resolve_git_root` (card 2). Do NOT change any other behavior in `resolve_wiki_path`. The check must run before the function reads any config file.
- **Commit:** `fix(paths): guard resolve_wiki_path against wiki-named git_toplevel`

### Card 2: Add `resolve_git_root` belt-and-suspenders guard

- **Context:**
  - `plugins/mill/scripts/_sibling.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** After the existing `return Path(result.stdout.strip())` site in `_paths.resolve_git_root()`, transform the function so it (a) computes `repo_root = Path(result.stdout.strip())` into a local variable, (b) runs the name-check fast path (`repo_root.name == "wiki"` → raise `SystemExit` with the literal error message from the `error-message-text` Shared Decision, substituting `{wiki_path}` with `str(repo_root)`), (c) attempts the path-equality check by calling `resolve_wiki_path(repo_root)` inside a `try/except BaseException:` block (use `except BaseException:` or equivalently `except (Exception, SystemExit):` — `resolve_wiki_path` may raise `SystemExit` per card 1's guard, and `SystemExit` inherits from `BaseException`, not `Exception`, so a plain `except Exception:` would let the inner halt propagate and break card 5 test case 4) — on success, raise `SystemExit` when `repo_root.resolve()` equals `wiki_path.resolve()` (use `Path.samefile` when both paths exist on disk; fall back to `Path.resolve() == Path.resolve()` when either does not exist) substituting `{wiki_path}` with `str(wiki_path)`; on any `BaseException` from `resolve_wiki_path` (config missing, card-1 nested halt, etc.), silently swallow the exception — the name-check above already protects this path. Return `repo_root` only after both checks pass.
- **Commit:** `fix(paths): guard resolve_git_root with name + path-equality against wiki cwd`

### Card 3: Add `_sibling.resolve_path` (mill) wiki guard

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_sibling.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** At the top of `resolve_path(role, repo_root)` in `plugins/mill/scripts/_sibling.py`, after the existing `repo_root = Path(repo_root)` line, add a check that raises `ValueError("resolve_path called from wiki repo — wiki cannot resolve its own wiki path")` when `repo_root.name == "wiki"`. The check fires regardless of the `role` argument — the source repo being wiki is the disqualifier, not the role being requested. Place the check immediately after the `Path` coercion and before the `parent = repo_root.parent` line so the function never produces the `wiki.wiki` nonsense path. Do NOT change any other behavior.
- **Commit:** `fix(sibling): raise ValueError when resolve_path is called from wiki repo`

### Card 4: Mirror wiki guard to `_sibling.resolve_path` (codeguide twin)

- **Context:**
  - `plugins/mill/scripts/_sibling.py`
- **Edits:**
  - `plugins/codeguide/scripts/_sibling.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the exact same check as card 3 to `plugins/codeguide/scripts/_sibling.py`. The added lines must be byte-for-byte identical to the mill copy outside the module docstring — the existing identical-twin test in `plugins/mill/unit_tests/test-sibling.py` (assertion that strips module docstrings and compares the remaining source) will fail otherwise. Do NOT touch the module docstring; the per-plugin docstring divergence is intentional.
- **Commit:** `fix(codeguide-sibling): mirror wiki-repo guard from mill _sibling.py`

### Card 5: Unit tests for the new `_paths` guards

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add the following test cases to `plugins/mill/unit_tests/test-paths.py`, following the existing `main()` function's `try/except AssertionError` style (each `_check_…` block prints `PASS:` on success, accumulates failures via `failures.append`). Use `unittest.mock.patch` on `_subprocess_util.run` for `resolve_git_root` cases. Cases to add:
    1. `resolve_git_root` raises `SystemExit` when the resolved cwd's `name == "wiki"` — patch `_subprocess_util.run` to return `_make_run_result(stdout="C:/Code/millhouse/wiki\n")`. Assert the raised `SystemExit` message contains the substring `"cwd is inside wiki"` and `"C:/Code/millhouse/wiki"`.
    2. `resolve_git_root` raises `SystemExit` via path-equality when the resolved cwd equals the resolved wiki path but the cwd directory name is something other than `"wiki"` — patch `_subprocess_util.run` to return a tmp path; patch `_paths.resolve_wiki_path` to return the same tmp path; assert `SystemExit` is raised.
    3. `resolve_git_root` falls through (does not raise) when neither name nor equality matches — patch `_subprocess_util.run` to return a tmp path outside any wiki; patch `_paths.resolve_wiki_path` to return a different path; assert the returned `Path` equals the patched stdout path.
    4. `resolve_git_root` falls through to the name check when `resolve_wiki_path` raises internally — patch `_paths.resolve_wiki_path` to raise `SystemExit("nested-halt")`; assert that with a non-wiki cwd the outer call returns normally, and with a wiki cwd it raises the outer `SystemExit` (NOT the inner nested-halt).
    5. `resolve_wiki_path` raises `SystemExit` when `git_toplevel.name == "wiki"` — pass a `Path("/tmp/anything/wiki")`; assert the message contains `"cwd is inside wiki"` and the path substring.
    6. `resolve_wiki_path` falls through when `git_toplevel.name != "wiki"` — use the existing `_container_form(tmp_path)` helper to build a main_root, then wrap the call in `with patch("_paths.resolve_main_worktree_root", return_value=main_root):` (matching the existing test conventions in this file, which always patch this subprocess-touching helper). Assert no exception is raised and the returned path is well-formed.
  Each new case must be additive (do not modify existing assertions) and run inside the same `main()` body, ordered after the existing tests.
- **Commit:** `test(paths): cover resolve_git_root + resolve_wiki_path wiki-cwd guards`

### Card 6: Unit tests for the new `_sibling` guard (mill + codeguide twin)

- **Context:**
  - `plugins/mill/scripts/_sibling.py`
  - `plugins/codeguide/scripts/_sibling.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-sibling.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add new test cases to `plugins/mill/unit_tests/test-sibling.py` inside the existing `main()` `try` block, ordered after the existing PASS lines but before the existing identical-twin assertion (so a mirroring failure still surfaces at the end). Use `try/except ValueError` to assert each raise. Cases to add:
    1. `resolve_path("wiki", Path("/c/Code/wiki"))` raises `ValueError` with message containing `"resolve_path called from wiki repo"`.
    2. `resolve_path("plan", Path("/c/Code/wiki"))` raises the same `ValueError` (role-agnostic).
    3. `resolve_path("worktrees", Path("/projects/wts/wiki"))` raises the same `ValueError` (container-form parent does not bypass the guard because the source repo's own `.name == "wiki"`).
    4. Regression guard: `resolve_path("wiki", Path("/c/Code/wts/millhouse"))` still returns `Path("/c/Code/wiki")` as before — the guard does not fire when the source repo is not named wiki.
    5. Import-and-call from the codeguide module path: load `plugins/codeguide/scripts/_sibling.py` via `importlib.util.spec_from_file_location` (the file is not on `sys.path`) and assert its `resolve_path("wiki", Path("/c/Code/wiki"))` raises the same `ValueError` with the same message — proves the identical-twin mirror is functionally identical, not just textually similar.
  Each new case prints `PASS:` on success; failures bubble to the outer `except AssertionError`. Do NOT remove or modify the existing identical-twin assertion at the end of `main()` — it must continue to pass once both `_sibling.py` files are updated.
- **Commit:** `test(sibling): cover wiki-repo guard in mill and codeguide twins`

## Batch Tests

Running `python plugins/mill/unit_tests/run-all.py` from the worktree root must finish with every test green. The runner auto-discovers `test-*.py` files; new cases added to `test-paths.py` (card 5) and `test-sibling.py` (card 6) are picked up automatically. The existing identical-twin assertion in `test-sibling.py` continues to enforce byte-equality of mill's and codeguide's `_sibling.py` outside the module docstring — card 4's mirror keeps this assertion green.
