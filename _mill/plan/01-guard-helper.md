# Batch: guard-helper

```yaml
task: '63 (A) — Reviewer tool-sandbox: git snapshot guard + fix --allowedTools'
batch: guard-helper
number: 1
cards: 2
verify: python plugins/mill/unit_tests/test-review-guard.py
depends-on: []
```

## Batch Scope

Add the runtime guard infrastructure that detects reviewer-overstep: a new exception class `ReviewerOverstepError` (subclass of existing `ReviewError`) and a context manager `worktree_snapshot_guard(project_root, *, expected_paths=None)` that captures HEAD SHA + porcelain status on enter and raises on diff at exit. Both live in `_review_common.py`. Add a focused unit-test file `test-review-guard.py` with eight cases covering clean / HEAD-change / porcelain-change / expected_paths filtering / error-class shape. No consumer wiring in this batch — batch 2 wires the three review backends to call it. This batch is self-contained: existing review flow tests must remain green because the helper is unused.

External interface this batch defines (consumed by batch 2):

```python
class ReviewerOverstepError(ReviewError):
    def __init__(self, before_sha: str, after_sha: str, porcelain_diff: str): ...

@contextmanager
def worktree_snapshot_guard(project_root: Path, *, expected_paths: list[str] | None = None) -> Iterator[None]:
    ...  # captures before-state, yields, captures after-state, raises ReviewerOverstepError on diff
```

Batch-local decisions: porcelain comparison uses **substring match on the path field with `\` -> `/` normalization** (see overview Shared Decision `Snapshot guard expected_paths uses substring match`). HEAD-SHA comparison is **never** filtered by `expected_paths`. Error message embeds before-SHA, after-SHA, and the unfiltered porcelain diff for debugging.

## Cards

### Card 1: Add ReviewerOverstepError and worktree_snapshot_guard to _review_common.py

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  1. In `_review_common.py`, immediately below the existing `class ReviewError(Exception):` declaration, add:

     ```python
     class ReviewerOverstepError(ReviewError):
         """Raised when a reviewer mutated git state (HEAD or working tree) during a review pass.

         Carries the before/after HEAD SHA and the unfiltered git status --porcelain
         diff for operator inspection. The guard does not auto-rollback; the operator
         resets manually after investigating.
         """

         def __init__(self, before_sha: str, after_sha: str, porcelain_diff: str) -> None:
             self.before_sha = before_sha
             self.after_sha = after_sha
             self.porcelain_diff = porcelain_diff
             msg = (
                 f"reviewer overstep detected: HEAD {before_sha[:8]} -> {after_sha[:8]}; "
                 f"porcelain diff:\n{porcelain_diff}"
             )
             super().__init__(msg)
     ```

  2. Add a module-level import at the top of `_review_common.py` (with the other stdlib imports):

     ```python
     from contextlib import contextmanager
     from typing import Iterator
     ```

     Also import `_subprocess_util` if not already imported (verify against existing imports — do not add a duplicate).

  3. Add the context manager directly below `ReviewerOverstepError`:

     ```python
     @contextmanager
     def worktree_snapshot_guard(
         project_root: Path,
         *,
         expected_paths: list[str] | None = None,
     ) -> Iterator[None]:
         """Snapshot git state before/after the with-block; raise on any change.

         Captures `git rev-parse HEAD` and `git status --porcelain` on entry,
         re-captures on exit, and raises ``ReviewerOverstepError`` if either the
         HEAD SHA or the porcelain diff (filtered by ``expected_paths``) differs.

         ``expected_paths`` is a list of substring patterns that filter the
         porcelain diff before comparison. A porcelain line is filtered when its
         path field (with backslashes normalised to forward slashes) contains
         ANY entry in ``expected_paths`` as a substring. HEAD-SHA changes are
         NEVER filtered.

         Exceptions raised inside the with-block propagate unchanged — the guard
         only raises if the block exits cleanly but state was mutated.
         """
         before_sha = _capture_head_sha(project_root)
         before_porcelain = _capture_porcelain(project_root)
         try:
             yield
         except Exception:
             raise  # do not swallow LLMError / ReviewError / etc.
         after_sha = _capture_head_sha(project_root)
         after_porcelain = _capture_porcelain(project_root)

         before_filtered = _filter_porcelain(before_porcelain, expected_paths)
         after_filtered = _filter_porcelain(after_porcelain, expected_paths)

         if before_sha != after_sha or set(before_filtered) != set(after_filtered):
             diff = _porcelain_diff(before_filtered, after_filtered)
             raise ReviewerOverstepError(before_sha, after_sha, diff)


     def _capture_head_sha(project_root: Path) -> str:
         """Return the current HEAD SHA as a hex string. Raises ReviewError on git failure."""
         result = _subprocess_util.run(
             ["git", "-C", str(project_root), "rev-parse", "HEAD"],
         )
         if result.returncode != 0:
             raise ReviewError(
                 f"worktree_snapshot_guard: git rev-parse HEAD failed in {project_root}: "
                 f"{(result.stderr or '').strip()}"
             )
         return result.stdout.strip()


     def _capture_porcelain(project_root: Path) -> list[str]:
         """Return git status --porcelain as a list of lines (one per entry). Raises ReviewError on failure."""
         result = _subprocess_util.run(
             ["git", "-C", str(project_root), "status", "--porcelain"],
         )
         if result.returncode != 0:
             raise ReviewError(
                 f"worktree_snapshot_guard: git status --porcelain failed in {project_root}: "
                 f"{(result.stderr or '').strip()}"
             )
         return [line for line in result.stdout.splitlines() if line.strip()]


     def _filter_porcelain(lines: list[str], expected_paths: list[str] | None) -> list[str]:
         """Drop porcelain lines whose path field matches any expected_paths substring.

         Each porcelain line has a 2-character status code, a space, then the path.
         Renames have ' -> ' between old and new path; both are checked against expected_paths.
         Path comparison normalises backslashes to forward slashes.
         """
         if not expected_paths:
             return list(lines)
         kept: list[str] = []
         for line in lines:
             # Porcelain format: "XY path" or "XY old -> new" for renames
             path_field = line[3:] if len(line) > 3 else line
             normalised = path_field.replace("\\", "/")
             # Split rename arrows so both sides are checked
             candidates = [s.strip() for s in normalised.split(" -> ")]
             if any(pat in cand for cand in candidates for pat in expected_paths):
                 continue
             kept.append(line)
         return kept


     def _porcelain_diff(before: list[str], after: list[str]) -> str:
         """Return a human-readable diff string of before vs after porcelain line sets."""
         before_set = set(before)
         after_set = set(after)
         added = sorted(after_set - before_set)
         removed = sorted(before_set - after_set)
         parts: list[str] = []
         for line in added:
             parts.append(f"  + {line}")
         for line in removed:
             parts.append(f"  - {line}")
         return "\n".join(parts) if parts else "  (no porcelain line diff; HEAD changed)"
     ```

  4. The exact placement: `ReviewerOverstepError` immediately after `ReviewError`'s class block; `worktree_snapshot_guard` after `ReviewerOverstepError`; private helpers `_capture_head_sha`, `_capture_porcelain`, `_filter_porcelain`, `_porcelain_diff` immediately after the context manager. Keep the existing module order otherwise intact.

  5. All `print()` / log strings introduced here are ASCII only (Shared Decision `ASCII-only log strings`). The functions above contain no `print()` calls; if any are added during implementation (e.g. for debugging during dev), they must use `--` and `->` ASCII forms before commit.

- **Commit:** `feat(_review_common): add ReviewerOverstepError and worktree_snapshot_guard`

### Card 2: Create test-review-guard.py with eight focused cases

- **Context:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-guard.py`
- **Deletes:** none
- **Requirements:**

  1. Create `plugins/mill/unit_tests/test-review-guard.py` following the same harness shape as `test-review-plan-flow.py`: a `main() -> int` returning 0 on success / 1 on any FAIL, `if __name__ == "__main__": sys.exit(main())`, `PASS:` / `FAIL:` lines per case. Add the same `HUB = Path(__file__).resolve().parent.parent.parent.parent` + `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))` preamble that the other tests use.

  2. Import the surface under test:

     ```python
     from _review_common import (
         ReviewError,
         ReviewerOverstepError,
         worktree_snapshot_guard,
     )
     ```

  3. Implement a fixture helper `_init_repo(tmp: Path) -> Path` that runs `subprocess.run(["git", "-C", str(tmp), "init"], check=True, capture_output=True)`, configures `user.name`/`user.email` via `git config`, creates a tracked file `seed.txt` with content `"seed"`, runs `git add seed.txt && git commit -m "seed"`, and returns `tmp`. Use `tempfile.TemporaryDirectory()` as a context manager around each test case so each case starts from a fresh repo.

  4. Eight test cases (one PASS line each, increment a local `errors` counter on FAIL):

     - **Case A — clean snapshot, no raise:** Enter the guard, do nothing, exit. No exception. PASS.

     - **Case B — git commit inside with raises ReviewerOverstepError, HEAD differs:** Inside the with-block, write a new tracked file `foo.txt`, `git add` + `git commit`. Catching `ReviewerOverstepError` must verify `e.before_sha != e.after_sha` and `len(e.before_sha) == 40` and `len(e.after_sha) == 40`.

     - **Case C — untracked file dropped raises (porcelain differs, HEAD same):** Inside the with-block, `Path(tmp / "scratch.tmp").write_text("x")` without adding/committing. `ReviewerOverstepError` raises; `e.before_sha == e.after_sha`; `"scratch.tmp"` appears in `e.porcelain_diff`.

     - **Case D — modified tracked file raises (porcelain M, HEAD same):** Inside the with-block, append to `seed.txt` without committing. Raises; `e.before_sha == e.after_sha`; the diff string contains `seed.txt`.

     - **Case E — expected_paths filters allowed write:** Pass `expected_paths=["allowed/"]`. Inside the with-block, first `(tmp / "allowed").mkdir(parents=True, exist_ok=True)`, then `Path(tmp / "allowed" / "output.md").write_text("x")` (without committing). Guard MUST NOT raise. (The `mkdir` is required — `_init_repo` only seeds `seed.txt` at repo root; the `allowed/` directory does not pre-exist.)

     - **Case F — commit inside expected_paths directory still raises (HEAD changed):** Pass `expected_paths=["allowed/"]`. Inside the with-block, create `allowed/output.md`, `git add` + `git commit`. Guard MUST raise (HEAD-SHA filter is never applied). Verify `e.before_sha != e.after_sha`.

     - **Case G — ReviewerOverstepError is a ReviewError subclass:** Assert `issubclass(ReviewerOverstepError, ReviewError) is True`. Assert that a try/except over `ReviewError` catches `ReviewerOverstepError` (raise an instance via the constructor with dummy strings).

     - **Case H — error message includes both SHAs and porcelain diff:** Construct `ReviewerOverstepError("abcdef0123456789" * 2 + "01234567", "fedcba9876543210" * 2 + "76543210", "  + ?? foo.txt")` directly; assert `"abcdef01"` and `"fedcba98"` and `"?? foo.txt"` all appear in `str(e)`.

  5. The Windows-path-normalization edge case is exercised implicitly: the helper's `_filter_porcelain` uses `.replace("\\", "/")` so the test works on both POSIX and Windows runners. Tests must not branch on `os.name`.

  6. All `print()` strings are ASCII; em-dashes in the file's narrative `PASS:` / `FAIL:` messages use `--` / `->`.

  7. Target length: under 150 lines including the helper. Reuse the inline-fixture pattern; do not add a class hierarchy or pytest dependency.

- **Commit:** `test(_review_common): add test-review-guard.py covering snapshot guard`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-review-guard.py`

The unit test covers the helper's eight states (clean, HEAD-change, porcelain-change, expected_paths filtering, error-class hierarchy, message shape) against a real `tempfile`-backed git repo per case. No real LLM, no network. Run-time under 5 seconds on a typical workstation.

Additionally, `test-review-common.py` (existing) imports `_review_common` — verifying the new symbols do not break its import is a free side-check; a green `python plugins/mill/unit_tests/test-review-common.py` confirms no import-time regression.

`run-all.py` (the global test runner used by `overview.verify`) auto-discovers tests via `HERE.glob("test-*.py")` (see [`plugins/mill/unit_tests/run-all.py:19`](plugins/mill/unit_tests/run-all.py)), so the new `test-review-guard.py` is automatically picked up. No registration step is needed.
