# Batch: baseline-longpath

```yaml
task: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability
batch: baseline-longpath
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-verify-baseline.py
depends-on: []
```

## Batch Scope

Fixes #615/#620: the module-wide verify baseline's transient `git worktree add` fails with "Filename too long" on deep-path Windows repos because `core.longpaths` is not set for the throwaway checkout, silently disabling the baseline gate. Card 3 adds `-c core.longpaths=true` to that single invocation in `_verify_baseline.compute_baseline`. Card 4 adds a monkeypatch unit test asserting the flag is present in the captured argv. This is the only batch with a runnable surface; `verify:` runs the new test. The teardown path is deliberately untouched (its existing `safe_rmtree` fallback already handles long-path deletion).

## Cards

### Card 3: Pass core.longpaths=true to the baseline git worktree add

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `compute_baseline` (`_verify_baseline.py`, the `git worktree add` call currently at lines ~152-153), insert `-c core.longpaths=true` into the argv immediately after the `-C`, `str(git_root)` pair and before the `worktree` token, so the list reads `["git", "-C", str(git_root), "-c", "core.longpaths=true", "worktree", "add", str(tmp_path), parent_sha]`. This scopes long-path handling to that one checkout without mutating any persistent git config. Do NOT modify the `git rev-parse` call, the teardown `_worktree.remove_safe(...)` call, or any other invocation. If a clarifying comment is added, keep it ASCII-only (`->` / `--`, no glyphs).
- **Commit:** `fix(verify-baseline): set core.longpaths on transient worktree add for Windows deep paths`

### Card 4: Unit test asserting the longpaths flag on the worktree-add argv

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `test-verify-baseline.py` following the monkeypatch/in-memory fixture style of `test-worktree.py` (match its test-harness convention — the same `run-all.py`-discoverable shape, no real git). The test monkeypatches `_verify_baseline._subprocess_util.run` to (a) return a successful `rev-parse` result for the parent SHA and (b) capture the argv of the `git worktree add` call; it also stubs `_verify_baseline._run_verify_in` to return `0` (so `compute_baseline` short-circuits to `"clean"` on the first verify) and stubs `_verify_baseline._junction.create` and `_verify_baseline._worktree.remove_safe` to no-ops. Pass `project_root` and `git_root` as paths inside a `tempfile.TemporaryDirectory` (as `test-worktree.py` does), because `compute_baseline` unconditionally runs `scratch_dir.mkdir(parents=True, exist_ok=True)` on `project_root/.scratch` (`_verify_baseline.py:148-149`) — the temp dir makes that mkdir land in an auto-cleaned path rather than a stray real directory. Invoke `compute_baseline` and assert: the captured `worktree add` argv contains `-c` immediately followed by `core.longpaths=true`, and that this `-c core.longpaths=true` pair appears after the `-C <git_root>` pair and before the `worktree` token. Assert `compute_baseline` returned `"clean"`. The filename `test-verify-baseline.py` is auto-discovered by `run-all.py` (glob of `test-*.py`, minus the SKIP set) — no registration needed.
- **Commit:** `test(verify-baseline): assert core.longpaths flag on baseline worktree add`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-verify-baseline.py` runs the single new test file, which covers card 3's argv change directly. Scope is deliberately one file (not `run-all.py`): the change touches only `_verify_baseline.py`, a module no other test imports, so a bounded per-batch verify is correct. The Python `PYTHONPATH=` prefix is required so the test subprocess loads worktree modules rather than the mill-cache copies.
