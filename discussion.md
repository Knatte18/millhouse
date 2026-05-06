# Discussion: 11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha

```yaml
task: '11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha'
slug: review-code-enhancements
status: discussing
parent: main
```

## Problem

Three independent defects in the code-review subsystem surfaced during production runs:

1. The holistic code reviewer hardcodes `--effort max`. On large tasks (e.g. 26-card container-restructure) the holistic prompt is the most expensive call mill makes. This combination hits the Claude rate-limit first; per-batch reviews on the same window succeed. The fix is a config key (`review.code.holistic_effort`, default `max`) so operators can dial down effort for large tasks without patching source.

2. Per-batch code reviews bundle the full content of every file referenced in the batch, even when only a small patch was applied. On batches that touch mid-sized shared files, the prompt approaches holistic-review size. `mill-go` already records `start_sha = git rev-parse HEAD` per batch in `status.md` specifically for this — but `_review_code.run` ignores it. The fix uses `git diff <start_sha>..HEAD -- <file>` when the diff is small relative to the file.

3. On Windows, spawning `cmd /c claude` via `subprocess.Popen` flashes a CMD console window. This affects every subprocess mill spawns (claude CLI, git), but is most visible during tool-use reviews which run longer interactive sessions. The fix is `creationflags=subprocess.CREATE_NO_WINDOW` in the single `Popen` call site.

## Scope

**In:**
- `wiki/config.yaml` — add `review.code.holistic_effort` (default `max`) and `review.code.diff_scope_threshold` (default `0.25`)
- `plugins/mill/templates/wiki-config.yaml` — add the same two keys to the `review.code` block (line 117); seeds fresh installations and must stay in sync with the live config
- `_reviewer_sonnetmax.py` and `_reviewer_sonnetmax_tool.py` — add `effort: str | None = None` kwarg to `run`; pass it through to `run_bulk` / `run_tool_use`
- `_reviewer_test_stub.py` — add `effort: str | None = None` kwarg to `run` to stay in sync
- `_review_code.py` — thread `holistic_effort` into the holistic reviewer call; add diff-scoping for per-batch bulk reviews using `start_sha` from `status.md`
- `_review_common.py` — new `bulk_files_with_diff(file_paths, start_sha, project_root, threshold)` function
- `_subprocess_util.py` — add `creationflags=subprocess.CREATE_NO_WINDOW` on Windows

**Out:**
- `_review_plan.py` and `_review_discussion.py` — no diff scoping, no effort changes
- Auto-retry on `LLMRateLimitError` with degraded effort — out of scope; operators use the config key instead
- Per-batch effort configurability — only holistic effort is configurable; per-batch stays at the reviewer module's internal default
- `_reviewer_sonnetmax_tool.py` diff scoping — tool-use reviewer reads files itself; diff injection would confuse it

## Decisions

### effort-api-extension

- Decision: Add `effort: str | None = None` to the `run` signature of every reviewer module. `None` falls through to the module's internal default (`"max"`). `_review_code.run` passes `cfg["review"]["code"]["holistic_effort"]` only for holistic calls (`batch_name is None`). Both the initial reviewer call **and** the NEED_CONTEXT retry call (bulk mode only, `_review_code.py` line ~287) must receive the same `effort` value.
- Rationale: Keeps the reviewer API stable and backwards-compatible. Callers that don't care about effort pass nothing and get existing behaviour. Avoids duplicating module files per effort level. Threading effort into the retry path ensures a NEED_CONTEXT round-trip doesn't silently drop the configured effort.
- Rejected: Calling `_llm_claude.run_bulk` directly from `_review_code.run` (breaks the reviewer abstraction); new reviewer modules per effort level (`_reviewer_sonnetmax_medium.py`) multiplies nearly-identical files.

### diff-scoping-bulk-only

- Decision: Diff scoping only applies when the reviewer `MODE == "bulk"`. Tool-use reviewers have `Read/Grep/Glob` and read files themselves; injecting diffs would conflict with their own file access.
- Rationale: Bulk reviewers receive all content inline and have no independent read access. Tool-use reviewers are self-navigating — giving them stale diff context alongside live files creates ambiguity.
- Rejected: Diff scoping in tool-use mode.

### diff-scoping-threshold

- Decision: Use character-count ratio: if `len(diff) < threshold * len(file_content)`, substitute the diff; otherwise use the full file. Default threshold is `0.25` (diff must be < 25% of file size to trigger). New/created files (in `Creates:` but absent from `start_sha..HEAD` diff) always use full content — they have no prior state.
- Rationale: Character count is the simplest accurate measure; line count underweights dense change. The 0.25 default is from the original issue analysis.
- Rejected: Line-count ratio; fixed-byte threshold.

### diff-scoping-location

- Decision: Add `bulk_files_with_diff(file_paths, start_sha, project_root, threshold)` to `_review_common.py`. Returns the same string format as `bulk_files` but substitutes diffs where small. `_review_code._build_artefact_section` accepts an optional `start_sha` and `threshold`; it delegates to `bulk_files_with_diff` when both are set and `reviewer_mode == "bulk"`, otherwise falls through to `bulk_files`.
- Rationale: Keeps diff logic in a testable pure function in `_review_common.py`. The artefact section builder stays agnostic about how content was fetched.
- Rejected: Inline diff logic in `_review_code.run`; modifying `bulk_files` in-place (would affect non-code callers).

### missing-start-sha-fallback

- Decision: If `read_batches` returns no entry for the named batch, or the batch entry has no `start_sha`, fall back silently to full file content for that review. Log a stderr warning.
- Rationale: Backwards-compatible with tasks started before this feature. No hard failure for missing metadata.

### create-no-window-location

- Decision: Add `creationflags=subprocess.CREATE_NO_WINDOW` to the `Popen` call in `_subprocess_util.run` on `os.name == "nt"`. This is the single subprocess spawn site used by all mill scripts.
- Rationale: Centralised fix covers all spawns (claude CLI, git, taskkill). The issue was first noticed via `_reviewer_sonnetmax_tool.py` but the root cause is the shared spawn helper.
- Rejected: Adding the flag in `_llm_claude._invoke` only (too narrow; git spawns remain affected).

## Technical context

### Key files

- `plugins/mill/scripts/_review_code.py` — `run()` is the per-batch/holistic review entry point. It resolves `plan_dir`, `reviews_dir`, loads the reviewer module, and calls `_build_artefact_section`. Holistic vs per-batch is distinguished by `batch_name is None`.
- `plugins/mill/scripts/_review_common.py` — `bulk_files()` at line 566 inlines file contents with `--- FILE: <path> ---` delimiters. New `bulk_files_with_diff` goes here.
- `plugins/mill/scripts/_reviewer_sonnetmax.py` — bulk reviewer, calls `run_bulk(..., effort="max")`. Needs `effort` kwarg.
- `plugins/mill/scripts/_reviewer_sonnetmax_tool.py` — tool-use reviewer, calls `run_tool_use(..., effort="max")`. Needs `effort` kwarg.
- `plugins/mill/scripts/_reviewer_test_stub.py` — stub reviewer used in unit tests. Needs `effort` kwarg to stay in sync.
- `plugins/mill/scripts/_llm_claude.py` — `run_bulk` and `run_tool_use` already accept `effort: str | None = None` and pass it to `_build_argv`. No changes needed here.
- `plugins/mill/scripts/_subprocess_util.py` — single `subprocess.Popen` call site for all mill subprocesses. Fix `CREATE_NO_WINDOW` here.
- `plugins/mill/scripts/_status.py` — `read_batches(status_path)` returns `list[dict]`; each dict may have `start_sha: str`. The status path is resolved via `resolve_path("status.md", slug)` (same pattern as `plan_dir`).
- `wiki/config.yaml` — add `holistic_effort: max` and `diff_scope_threshold: 0.25` under `review.code`.

### How `_review_code.run` gets `start_sha`

```python
# Per-batch only (batch_name is not None):
status_path = resolve_path("status.md", slug)
batches = _status.read_batches(status_path)
entry = next((b for b in batches if b.get("name") == batch_name), None)
start_sha = entry.get("start_sha") if entry else None
```

`resolve_path` is already imported; `_status` needs to be imported in `_review_code.py`.

### `bulk_files_with_diff` signature

```python
def bulk_files_with_diff(
    file_paths: list[Path],
    start_sha: str,
    project_root: Path,
    threshold: float,
) -> str:
```

For each file:
- Run `git -C <project_root> diff <start_sha>..HEAD -- <rel_path>`.
- If diff is empty string and file exists → file was not changed by this batch; include full file content (the reviewer needs context even for unchanged referenced files).
- If `len(diff) < threshold * len(file_content)` → substitute diff content, prefixed with a `--- DIFF: <path> (from <start_sha[:8]>) ---` delimiter so the reviewer understands what it's seeing.
- Otherwise → full file content with the normal `--- FILE: <path> ---` delimiter.
- Non-existent files (deleted) → skip with stderr warning (same as `bulk_files`).

### `_build_artefact_section` changes

The function currently takes `(reviewer_mode, overview_path, batch_files, source_files, ancestors_on_disk, deletes_union)`. Add `start_sha: str | None = None, diff_threshold: float = 0.25, project_root: Path | None = None`. When `reviewer_mode == "bulk"` and `start_sha` is not None, call `bulk_files_with_diff(source_files, start_sha, project_root, diff_threshold)` for the source files portion. The `overview_path`, `batch_files`, and `ancestors_on_disk` are always bulked as full content (plan artefacts and ancestor creates don't benefit from diffs).

### Config additions

Both `wiki/config.yaml` and `plugins/mill/templates/wiki-config.yaml` must receive the same additions. The template seeds fresh installations; omitting keys there causes `KeyError` on `cfg["review"]["code"]["holistic_effort"]` for any repo that ran `mill-setup` after this change without a prior `wiki/config.yaml`.

```yaml
# wiki/config.yaml and plugins/mill/templates/wiki-config.yaml, under review.code:
code:
  rounds: 3
  reviewer: sonnetmax
  holistic: true
  holistic_effort: max        # effort passed to holistic review call (bulk or tool-use)
  diff_scope_threshold: 0.25  # diff/file ratio below which per-batch reviews use git diff
  self_fix_rounds: 2
```

### `_subprocess_util.py` change

```python
# In run(), before subprocess.Popen:
if os.name == "nt":
    popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
```

This is valid even for the taskkill kill path because `subprocess.run` with `capture_output=True` already suppresses windows; but adding it there too doesn't hurt.

## Testing

### `test-reviewer-modules.py`

Add assertions that `_reviewer_sonnetmax.run`, `_reviewer_sonnetmax_tool.run`, and `_reviewer_test_stub.run` all accept an `effort` kwarg with default `None`. Verify `stub.run("x", effort="medium")` captures `effort="medium"` in `captured_prompts()[0][1]`.

### `test-review-code-flow.py`

Add tests covering:
- Holistic call with `holistic_effort: medium` in config → reviewer receives `effort="medium"`.
- Per-batch call → reviewer receives `effort=None` (no override).
- Per-batch with `start_sha` present in status.md → `bulk_files_with_diff` is called (stub verifies prompt contains `--- DIFF:` prefix for a small diff file).
- Per-batch with `start_sha` missing → falls back to full file content (no `--- DIFF:` prefix).
- Per-batch with large diff (≥ threshold) → full file content used.

These tests use `_reviewer_test_stub` and in-memory status.md fixtures (following the existing pattern in `test-review-code-flow.py`).

### `test-review-common.py`

Add tests for `bulk_files_with_diff`:
- File with small diff → `--- DIFF:` prefix in output.
- File with large diff → `--- FILE:` prefix (full content).
- File with empty diff (not modified in batch) → `--- FILE:` prefix (full content).
- Non-existent file → skipped with warning.

These tests use `tempfile`-based git repos with controlled commits to produce known diffs.

### `test-llm-claude.py` / `_subprocess_util` smoke

The existing `test-llm-claude.py` smoke tests exercise the subprocess path indirectly. No new test needed for `CREATE_NO_WINDOW` specifically — it's a platform flag that can't be unit-tested without Windows + a real subprocess. A comment in the code noting the behaviour is sufficient.

## Q&A log

- **Q:** Add `effort` to reviewer `run` signatures (option A), or bypass the reviewer abstraction? **A:** Option A — add `effort: str | None = None` to every reviewer `run`.
- **Q:** Include auto-retry on `LLMRateLimitError` with degraded effort? **A:** No — operators use the config key.
- **Q:** Diff scoping for tool-use mode? **A:** No — tool-use reviewers read files themselves; bulk only.
- **Q:** Threshold unit (character vs line count)? **A:** Character count, default 0.25.
- **Q:** What if `start_sha` is missing from status.md? **A:** Silently fall back to full file content.
- **Q:** Where does diff logic live? **A:** `bulk_files_with_diff` in `_review_common.py`; artefact section builder passes `start_sha` + `threshold` when available.
- **Q:** Where does `CREATE_NO_WINDOW` go? **A:** `_subprocess_util.run` — the single Popen call site.
