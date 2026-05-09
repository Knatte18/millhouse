# Batch: cleanliness-helper

```yaml
task: 36 (A) — Bug-fix batch 3
batch: cleanliness-helper
number: 1
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Deliver `plugins/mill/scripts/_cleanliness.py` — a new flat helper exposing two functions, `capture_snapshot(worktree, snapshot_path)` and `compute_new_dirt(worktree, snapshot_path)` — together with its full unit-test suite at `plugins/mill/unit_tests/test-cleanliness.py`. The next batch (cleanliness-wireup) consumes this helper to replace mill-go's existing raw-`git status` cleanliness gate. This batch is one unit because the test scenarios specify the helper's API verbatim — splitting tests from helper across batches would force a downstream re-read of the discussion to know what the API should look like. Test-first ordering is preserved within the batch: card 6 (test) commits before card 7 (helper); intermediate test failure between commits is tolerated since `verify:` runs once at the end of the batch.

## Cards

### Card 6: write _cleanliness unit tests

- **Context:**
  - `plugins/mill/unit_tests/test-active.py`
  - `plugins/mill/unit_tests/test-millpy-bg.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Deletes:** none
- **Requirements:** Add a new test file `plugins/mill/unit_tests/test-cleanliness.py`. Top-of-file boilerplate matches `test-millpy-bg.py`'s style: `from __future__ import annotations`, imports for `sys`, `tempfile`, `unittest.mock`, `Path`, then `HUB = Path(__file__).resolve().parent.parent.parent.parent` and `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`, then `from _cleanliness import capture_snapshot, compute_new_dirt  # noqa: E402`. Define `def main() -> int:` returning 0 on success, 1 on assertion failure (matches `test-active.py` exit-code contract). Inside `main`, run nine independent test cases as a sequence of `try`/`except AssertionError` blocks, each printing `PASS: <description>` on success or appending to a `failures: list[str]` on failure (model after `test-millpy-bg.py`'s pattern). Print `All _cleanliness unit tests passed.` and `return 0` at the end when `failures` is empty; otherwise print each entry of `failures` to stderr and `return 1`. The nine cases are:

  1. **`compute_new_dirt`: empty pre + empty post → `[]`.** Patch `_subprocess_util.run` to return `MagicMock(returncode=0, stdout="", stderr="")`. Write an empty snapshot file in a `tempfile.TemporaryDirectory()`. Call `compute_new_dirt(Path(tmp), snapshot_path)`. Assert returned list is `[]`.

  2. **`compute_new_dirt`: empty pre + dirty post → all post lines sorted.** Patch returns `stdout=" M b.txt\n M a.txt\n"`. Empty snapshot file. Assert returned list equals `[" M a.txt", " M b.txt"]` (sorted).

  3. **`compute_new_dirt`: dirty pre + identical post → `[]` (the original repro).** Snapshot file content is `" M file.txt\n"`. Patch returns `stdout=" M file.txt\n"`. Assert `[]`.

  4. **`compute_new_dirt`: dirty pre + post is a strict superset → only extra lines are flagged.** Snapshot is `" M a.txt\n"`. Patch returns `stdout=" M a.txt\n M b.txt\n"`. Assert returned list equals `[" M b.txt"]`.

  5. **`compute_new_dirt`: dirty pre + post is a strict subset → `[]`.** Snapshot is `" M a.txt\n M b.txt\n"`. Patch returns `stdout=" M a.txt\n"`. Assert `[]`.

  6. **`compute_new_dirt`: status-code change `M` → `MM` flagged.** Snapshot is `" M file.txt\n"`. Patch returns `stdout="MM file.txt\n"`. Assert returned list equals `["MM file.txt"]`.

  7. **`compute_new_dirt`: missing snapshot file → returns post lines + emits `[cleanliness]` warning to stderr.** Use `snapshot_path = Path(tmp) / "missing.txt"` (do not create the file). Patch returns `stdout=" M a.txt\n"`. Capture stderr via `with unittest.mock.patch("sys.stderr", new=io.StringIO()) as fake_err:` (and add `import io` to the test file's imports if not already present). Assert returned list equals `[" M a.txt"]`. Assert `"[cleanliness]"` is a substring of `fake_err.getvalue()`.

  8. **`compute_new_dirt`: CRLF in snapshot, LF in subprocess stdout → no false-positive new dirt.** Write snapshot file content as `" M file.txt\r\n"` (CRLF). Patch returns `stdout=" M file.txt\n"` (LF). Assert returned list is `[]` — line splitting must normalize both terminators (using `str.splitlines()` does this).

  9. **`capture_snapshot`: writes the exact `git status --porcelain --untracked-files=no` stdout.** Patch `_subprocess_util.run` to return `MagicMock(returncode=0, stdout=" M file.txt\n", stderr="")`. Call `capture_snapshot(Path(tmp), snapshot_path)` where `snapshot_path = Path(tmp) / "task" / ".cleanliness-snapshot-foo.txt"` (parent dir intentionally absent). Assert the patch was called with argv whose first three elements are `["git", "-C", str(Path(tmp))]` (use `mock.call_args.args[0][:3]` or `.kwargs`). Assert the snapshot file exists. Assert its UTF-8 content equals `" M file.txt\n"` verbatim, including the trailing newline.

  Each case is wrapped in its own `try` / `except` so one failure does not skip subsequent cases. The tail boilerplate (`if __name__ == "__main__": sys.exit(main())`) matches `test-active.py` lines 60–61.

- **Commit:** `test: add _cleanliness gate diff helper unit tests`

### Card 7: implement _cleanliness helper

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/scripts/_cleanliness.py`. Top of file: `"""Pre-batch dirt snapshot + gate-time diff helper for mill-go."""` then `from __future__ import annotations`, then `import sys` and `from pathlib import Path`, then `import _subprocess_util`. No `if __name__ == "__main__":` block.

  Define exactly two public functions:

  - **`capture_snapshot(worktree: Path, snapshot_path: Path) -> None`** — runs `_subprocess_util.run(["git", "-C", str(worktree), "status", "--porcelain", "--untracked-files=no"], check=True)` and writes the resulting `.stdout` (a `str`) verbatim to `snapshot_path` with `encoding="utf-8"`. Before writing, call `snapshot_path.parent.mkdir(parents=True, exist_ok=True)`. The function returns `None`. Brief docstring (3–5 lines) explaining: pre-batch capture, called once per batch from the initial-dispatch path of `millpy-implement.py`, the on-disk file is committed on the task branch by mill-go's batch-start commit so it survives crash/resume.

  - **`compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]`** — reads `snapshot_path` with `encoding="utf-8"` if it exists; if it does not exist, prints `f"[cleanliness] warning: snapshot file not found at {snapshot_path}, treating pre-batch as empty"` to stderr (`file=sys.stderr`) and uses an empty string in place of the file content. Then runs `_subprocess_util.run(["git", "-C", str(worktree), "status", "--porcelain", "--untracked-files=no"], check=True)` to get the post-batch porcelain output. Computes `pre_set = {line for line in pre_text.splitlines() if line}` and `post_set = {line for line in post_text.splitlines() if line}` (using `str.splitlines()` so both LF and CRLF terminators are stripped, and dropping empty lines). Returns `sorted(post_set - pre_set)` — a `list[str]`. Brief docstring (4–6 lines) explaining: gate-time diff against the pre-batch snapshot, missing snapshot warns and treats pre as empty, line-set diff (post − pre) so a status-code change like `M` → `MM` is flagged.

  Use 4-space indentation. No mid-function comments unless the WHY is non-obvious per CLAUDE.md. Function signatures must include type annotations. The module imports `_subprocess_util` (no `from _subprocess_util import run` shorthand — match `_wiki.py`'s style of fully-qualified calls).

- **Commit:** `feat(scripts): add _cleanliness helper for batch dirt-diff`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs every `test-*.py` discovered under `plugins/mill/unit_tests/` (the batch adds one new file, `test-cleanliness.py`). The new test covers all nine scenarios from card 6's requirements. No real git or real LLM is invoked — `_subprocess_util.run` is patched in every test case. The pre-existing tests are expected to still pass (this batch makes no edits to existing `_*.py` modules).
