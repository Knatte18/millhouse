# Batch: diff-scope-and-effort

```yaml
task: '11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha'
batch: diff-scope-and-effort
cards: 2
verify: null
depends-on: [reviewer-effort-api]
```

## Batch Scope

Two tightly coupled changes: (1) add `bulk_files_with_diff` to `_review_common.py` — the new helper that substitutes git diff output for full file content when the diff is small; (2) update `_review_code.py` to thread `holistic_effort` from config into reviewer calls (both initial and NEED_CONTEXT retry) and to pass `start_sha` + `diff_threshold` for per-batch bulk reviews. These two files share most of their `Reads:` list and the changes are semantically coupled — `_review_code.py` calls the new function. Tests live in batch 04.

## Cards

### Card 5: Add bulk_files_with_diff to _review_common.py

- **Reads:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `bulk_files_with_diff` to `_review_common.py` immediately after the existing `bulk_files` function (around line 580). Also add it to the module docstring's Public API list.

  **Signature:**
  ```python
  def bulk_files_with_diff(
      file_paths: list[Path],
      start_sha: str,
      project_root: Path,
      threshold: float,
  ) -> str:
  ```

  **Imports:** Add `import subprocess` to `_review_common.py`'s import block (alongside the existing `importlib, re, sys, ...` stdlib imports). The module currently does not import `subprocess`; omitting this causes `NameError` at runtime.

  **Per-file logic** (iterate `file_paths` in order):

  1. Read the full file content (UTF-8, `errors="replace"`) into `file_content`. If the file does not exist → skip with a stderr warning (`f"[bulk_files_with_diff] warning: {p} not found, skipping"`) and continue to the next file.

  2. Run `git -C <project_root> diff <start_sha>..HEAD -- <rel_path>` where `<rel_path>` is the file path made relative to `project_root` using `p.relative_to(project_root).as_posix()` (forward-slash pathspec — portable across platforms; if the path is not under `project_root`, fall back to the absolute path's string as the argument to git). Use `subprocess.run` directly (not `_subprocess_util.run`) since we don't want the `[subprocess] spawn` breadcrumb noise filling up the review log for every file. Pass `text=True, encoding="utf-8", errors="replace"` and capture stdout and stderr. Do NOT use `check=True`.

  3. If the subprocess returns non-zero exit code → warn to stderr with `f"[bulk_files_with_diff] warning: git diff failed for {p} (returncode={result.returncode}), using full file"` and append `file_content` with `--- FILE: {p} ---` delimiter. Continue to next file.

  4. diff_text = the decoded stdout (already a string since `text=True`).

  5. If `diff_text` is empty (file exists but was not changed between `start_sha` and HEAD) → append `file_content` with `--- FILE: {p} ---` delimiter. The reviewer needs the file content as context even if it wasn't changed in this batch.

  6. If `len(diff_text) < threshold * len(file_content)` → append with `--- DIFF: {p} (from {start_sha[:8]}) ---` delimiter followed by `diff_text`.

  7. Otherwise → append `file_content` with `--- FILE: {p} ---` delimiter.

  Join all parts with `"\n\n"` and return, same as `bulk_files`.

  **Public API docstring entry** (add to the module-level docstring list):
  ```
  bulk_files_with_diff() — like bulk_files but substitutes git diff output for small-diff files
  ```
- **Commit:** `feat(review_common): add bulk_files_with_diff for diff-scoped bulk reviews`

### Card 6: Update _review_code.py — effort threading and diff-scoping

- **Reads:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
- **Modifies:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  **Import:** Add `import _status` to the imports at the top of `_review_code.py` (alongside the existing `_review_common` import block).

  **`_build_artefact_section` signature extension:** Add three keyword-only parameters with defaults:
  ```python
  def _build_artefact_section(
      reviewer_mode: str,
      overview_path: Path,
      batch_files: list[Path],
      source_files: list[Path],
      ancestors_on_disk: list[Path],
      deletes_union: set[str],
      *,
      start_sha: str | None = None,
      diff_threshold: float = 0.25,
      project_root: Path | None = None,
  ) -> str:
  ```

  In the `else:` branch of `_build_artefact_section` (the `reviewer_mode == "bulk"` path, around line 135), replace:
  ```python
  bulked = bulk_files(all_bulked)
  ```
  with:
  ```python
  # Always bulk overview + batch files + ancestors at full content.
  # source_files use diff-scoping if start_sha is set.
  plan_and_ancestors = [overview_path, *batch_files, *ancestors_on_disk]
  if start_sha is not None and project_root is not None:
      scoped_sources = bulk_files_with_diff(source_files, start_sha, project_root, diff_threshold)
      bulked = bulk_files(plan_and_ancestors) + ("\n\n" + scoped_sources if scoped_sources else "")
  else:
      bulked = bulk_files(all_bulked)
  ```

  Also add `bulk_files_with_diff` to the import from `_review_common` at the top of the file.

  **`_review_code.run` — read start_sha for per-batch reviews:** After the `batch_files` computation (around line 187, after `batch_files = _collect_batch_files(...)`), add:
  ```python
  # Per-batch diff-scoping: read start_sha from status.md if batch_name is set.
  start_sha: str | None = None
  diff_threshold: float = cfg["review"]["code"].get("diff_scope_threshold", 0.25)
  if batch_name is not None:
      try:
          status_path = resolve_path("status.md", slug)
          batches_list = _status.read_batches(status_path)
          entry = next((b for b in batches_list if b.get("name") == batch_name), None)
          start_sha = entry.get("start_sha") if entry else None
          if start_sha is None:
              print(
                  f"[_review_code] no start_sha for batch {batch_name!r}; using full file content",
                  file=sys.stderr,
              )
      except Exception as exc:
          print(
              f"[_review_code] warning: could not read start_sha for batch {batch_name!r}: {exc}; using full file content",
              file=sys.stderr,
          )
  ```

  **`_review_code.run` — read holistic_effort:** After the existing `reviewer_name = cfg["review"]["code"]["reviewer"]` line, add:
  ```python
  holistic_effort: str | None = cfg["review"]["code"].get("holistic_effort", "max") if batch_name is None else None
  ```

  **`_build_artefact_section` call:** Update the call at line ~230 to pass the new kwargs:
  ```python
  artefact_section = _build_artefact_section(
      reviewer.MODE, overview_path, batch_files, source_files, ancestors_on_disk,
      deletes_union,
      start_sha=start_sha,
      diff_threshold=diff_threshold,
      project_root=project_root,
  )
  ```

  **First `reviewer.run` call (initial, around line 250):** Pass `effort=holistic_effort`:
  ```python
  raw, session_id = reviewer.run(prompt_text, timeout=timeout, effort=holistic_effort)
  ```

  **NEED_CONTEXT retry call (around line 286):** Pass `start_sha=None` to `_build_artefact_section` to force full file content, and pass the same `effort=holistic_effort`:
  ```python
  raw, session_id = reviewer.run(
      retry_prompt, session_id=session_id, resume=True, timeout=timeout, effort=holistic_effort
  )
  ```

  Note: the retry call does not rebuild the artefact section — it sends `retry_prompt` which is the re-attached files text. The `start_sha=None` comment in the discussion refers to the fact that if we ever rebuild the artefact for a retry, we'd pass `start_sha=None`. In the current code, the retry sends `retry_prompt` directly (a re-attached section), so no artefact rebuild happens. The key fix is that `effort=holistic_effort` is passed to the retry `reviewer.run` call.

  **Per-batch reviewer call:** For per-batch reviews, `holistic_effort` is `None` (set above). The `reviewer.run(prompt_text, timeout=timeout, effort=None)` call means the reviewer uses its internal default (`"max"`). This is correct per the discussion decision (per-batch effort is not configurable).
- **Commit:** `feat(review_code): thread holistic_effort and add diff-scoping via start_sha`

## Batch Tests

`verify: null` — tests are in batch 04 (`test-diff-scope-and-effort`). The implementation can be validated by checking Python imports succeed: `python -c "from _review_common import bulk_files_with_diff; from _review_code import run; print('ok')"` from the scripts directory if desired, but no automated verify is set here since the full test suite runs in batch 04.
