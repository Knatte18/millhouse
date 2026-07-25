# Batch: on-disk-first-resolution

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: on-disk-first-resolution
number: 2
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-marker.py test-review-plan-flow.py"
depends-on: []
```

## Batch Scope

Closes #665, #683, #693, #691. `_review_common.find_active_slug` and `_review_common.load_task_title` both, on the common path, end up calling the wiki daemon's `_dispatch()` retry loop (via `_marker.slug_from_branch` / `_marker.task_data` → `_marker._list_tasks_brief_with_retry` → `wiki.list_tasks_brief`), which costs up to ~134s per call (4 attempts × 30s read timeout + `[2,4,8]`s backoff — confirmed at `wiki/_client.py`). This is the confirmed single root cause behind the four "review-prepare hangs ~2min" issues; #691's "stale lock" theory was a misdiagnosis of this same latency. `millpy-implement.py` already reads `task_title` straight from `status.md`'s YAML frontmatter with zero daemon calls (existing precedent this batch follows). This batch makes both shared functions try the cheap on-disk read first, internally, so every call site — including `_review_plan.py`'s `run()`, which calls `load_task_title` independently of `prepare()` — gets the fast path automatically with no caller-side changes. External interface: neither function's signature or return-value contract changes; only internal behavior (fewer daemon round-trips in the common case).

## Cards

### Card 3: Make find_active_slug try the on-disk *.active glob before the daemon path

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `find_active_slug(hub_root, wiki_path, cfg)` (`_review_common.py`), reorder so the existing `_mill/*.active` glob fallback is tried FIRST, before `_marker.slug_from_branch`, and only fall through to `slug_from_branch` when the glob does not yield exactly one match:

  ```python
  def find_active_slug(hub_root: Path, wiki_path: Path, cfg: dict) -> str:
      """Detect active slug via _mill/*.active glob, falling back to branch name.

      Raises ReviewError (wrapping MarkerError or glob-fallback errors).
      """
      try:
          matches = list((hub_root / "_mill").glob("*.active"))
      except OSError:
          matches = []
      if len(matches) == 1:
          return matches[0].stem
      try:
          return _marker.slug_from_branch(hub_root, wiki_path, cfg)
      except _marker.MarkerError as exc:
          if len(matches) > 1:
              slugs = sorted(m.stem for m in matches)
              raise ReviewError(
                  f"{len(slugs)} tasks active ({', '.join(slugs)}); use --slug <slug>"
              ) from exc
          raise ReviewError(
              f"no active task detected; run mill-spawn or mill-claim to start a task"
              f" (branch detection: {exc})"
          ) from exc
  ```

  This preserves every existing observable outcome (single-match glob → that slug; zero-match glob → `slug_from_branch` result or its `ReviewError` translation; multi-match glob → `ReviewError` listing the slugs, now raised from inside the `except _marker.MarkerError` branch with `exc` as the cause — only reachable if `slug_from_branch` ALSO fails, matching today's behavior where the multi-match case only reports after `slug_from_branch` already failed). The only behavior change is that a single-match glob now short-circuits before ever calling `slug_from_branch`, avoiding the daemon round-trip in the common case. Update the docstring's first line to reflect the new order (see the replacement above).
- **Commit:** `fix(review-common): try on-disk .active marker before daemon in find_active_slug`

### Card 4: Make load_task_title read status.md before the daemon path

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `load_task_title(git_root, wiki_path, cfg, slug)` (`_review_common.py`), try reading `task_title` from `status.md`'s YAML frontmatter first, before falling to `_marker.task_data`:

  ```python
  def load_task_title(git_root: Path, wiki_path: Path, cfg: dict, slug: str) -> str:
      """Read task_title from status.md on disk; fall back to the wiki daemon.

      The first parameter is named git_root for historical reasons, but every
      call site passes the hub-resolved project_root -- status.md is read
      relative to whichever value is actually passed in.
      """
      try:
          status_path = _paths.require_status_path(git_root, cfg)
          full = _status.read_full(status_path)
          title = full["yaml"].get("task")
          if title:
              return title
      except (_paths.TaskHubError, ValueError, KeyError):
          pass
      try:
          data = _marker.task_data(git_root, wiki_path, cfg)
      except _marker.MarkerError:
          return slug
      return data.get("task_title") or slug
  ```

  Add `import _status` to `_review_common.py`'s existing import block (`_paths` is already imported). The three-exception catch is deliberate and each is load-bearing, not defensive over-catching: `_paths.TaskHubError` when `status.md` doesn't exist at the resolved location; `ValueError` when `_status.read_full` finds the file but its YAML/timeline block is missing or malformed; `KeyError` when `cfg` lacks a `paths.status_md` key at all (`_paths.status_path` raises `KeyError` in that case, not `TaskHubError` — this specifically happens with the minimal test-only `cfg` dicts used in `test-review-common.py`'s existing `load_task_title` tests, which pass `cfg` without a `paths` key; without catching `KeyError` here those existing tests would crash instead of falling through to the daemon path they currently exercise). This preserves every existing observable outcome — the daemon-path fallback (`_marker.task_data` / `MarkerError` → return `slug`) is untouched; the only change is that a present, well-formed, matching `status.md` now short-circuits before ever calling `_marker.task_data`.
- **Commit:** `fix(review-common): read status.md before daemon in load_task_title`

### Card 5: Add tests for on-disk-first resolution

- **Context:**
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-review-common.py`'s `main()`, add new test blocks following the file's existing style (`with _test_helpers.safe_temp_dir() as tmpdir:` / `with unittest.mock.patch(...)`, `assert`, `print("PASS: ...")`, incrementing the local `errors` counter on failure — match the existing blocks immediately surrounding the current `find_active_slug`/`load_task_title` tests around line 225-272):
  1. **`find_active_slug` daemon-skip on single on-disk marker:** create a tmpdir with a `_mill/<slug>.active` file present, patch `_marker.slug_from_branch` (via `unittest.mock.patch("_marker.slug_from_branch")`) to raise `AssertionError("daemon should not be called")` if invoked, call `find_active_slug(tmpdir, wiki_path, cfg)`, and assert it returns the slug WITHOUT the patched `slug_from_branch` ever being called.
  2. **`find_active_slug` multi-marker still resolves via existing behavior:** reuse the existing "multiple .active files -> ReviewError" test's fixture shape (already present later in the file, look for "find_active_slug glob fallback: multiple .active files") to confirm this batch's reorder didn't change that outcome — this may already be fully covered by the existing test; only add a new assertion if the existing one doesn't already exercise the multi-match-then-daemon-also-fails path introduced by the reorder.
  3. **`load_task_title` daemon-skip on present status.md:** create a tmpdir with a `.millhouse` dir absent (or a minimal one) and a `status.md` at a path matching a `cfg["paths"]["status_md"]` you set explicitly in the test's `cfg` dict (e.g. `cfg = {"paths": {"status_md": "status.md"}}`), containing a YAML frontmatter block with `task: "My On-Disk Title"`, patch `_marker.task_data` to raise `AssertionError("daemon should not be called")` if invoked, call `load_task_title(tmpdir, wiki_path, cfg, "some-slug")`, and assert it returns `"My On-Disk Title"` without the patched `task_data` ever being called.
  4. **`load_task_title` falls through on missing/malformed status.md:** confirm the existing "load_task_title: task_title present in Home.md" and "load_task_title: non-task branch -> falls back to slug" tests (already in the file, unmodified) still pass — these exercise exactly the `KeyError`/`TaskHubError` fallback paths Card 4's `except` clause exists for. Do not weaken or remove these tests; they are regression coverage for Card 4's fallback correctness.
  5. **`_review_plan.py`'s `run()` benefits too (regression for the round-2 discussion-review correction):** this is verified by the batch's `verify:` command including `test-review-plan-flow.py` in its `--only` list — no new test is required in THIS card if that file's existing flow tests already exercise `run()`'s `load_task_title` call path end-to-end; only add a targeted test here if a review of `test-review-plan-flow.py` (read it, do not edit it — it's covered by `on-disk-first-resolution`'s `verify:` as a regression check, not a target of this card's edits) shows no such coverage exists today.
- **Commit:** `test(review-common): cover on-disk-first find_active_slug/load_task_title`

## Batch Tests

`verify:` runs `test-review-common.py` (Cards 3-5's primary coverage), `test-marker.py` (regression for `_marker.slug_from_branch`/`task_data`, unchanged but exercised transitively), and `test-review-plan-flow.py` (regression confirming `_review_plan.py run()`'s independent `load_task_title` call site — flagged in discussion review round 2 — still behaves correctly and benefits from the fast path).
