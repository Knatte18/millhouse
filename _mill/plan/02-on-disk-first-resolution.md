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

### Card 3: Make find_active_slug skip the daemon only when a cheap branch check confirms the on-disk marker

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** **Corrected design (plan-review round 1 BLOCKING finding):** a naive "glob-first, unconditionally trust a single match" reorder is a correctness regression — a stale leftover `_mill/<slug>.active` marker (e.g. from an aborted claim; `millpy-cleanup.py`'s own comments acknowledge these can go stale) would be silently returned even if the current branch has since moved to a different, valid task, whereas today's branch-first `slug_from_branch` would correctly detect the branch change. The fast path must therefore only short-circuit when the on-disk marker **agrees** with a cheap, daemon-free, branch-derived slug — not merely when the glob has exactly one match:

  ```python
  def find_active_slug(hub_root: Path, wiki_path: Path, cfg: dict) -> str:
      """Detect active slug via branch name; skip the daemon round-trip only
      when a cheap branch check confirms a single _mill/*.active on-disk marker.
      On daemon failure, an unconfirmed lone marker is still trusted, exactly
      as before this fast path existed.

      Raises ReviewError (wrapping MarkerError or glob-fallback errors).
      """
      try:
          matches = list((hub_root / "_mill").glob("*.active"))
      except OSError:
          matches = []
      if len(matches) == 1:
          try:
              branch = _pygit2_util.current_branch(hub_root) or ""
          except _pygit2_util.GitOpsError:
              branch = ""
          prefix = cfg.get("spawn", {}).get("branch_prefix", "")
          branch_slug = branch.removeprefix(prefix) if branch.startswith(prefix) else None
          if branch_slug == matches[0].stem:
              return matches[0].stem
      try:
          return _marker.slug_from_branch(hub_root, wiki_path, cfg)
      except _marker.MarkerError as exc:
          if len(matches) == 1:
              return matches[0].stem
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

  **Correction (plan-review round 2 BLOCKING finding):** the round-1 fix's exception handler only special-cased `len(matches) > 1`, silently dropping the pre-existing "daemon fails, exactly one on-disk marker exists (regardless of branch confirmation) → trust it anyway" fallback that today's (pre-this-batch) code has unconditionally. The `if len(matches) == 1: return matches[0].stem` line inside the `except _marker.MarkerError` block (added above) restores this exactly — it is what the existing, unmodified test `find_active_slug glob fallback: one .active file -> returns slug` in `test-review-common.py` (a non-git tmpdir, `slug_from_branch` mocked to raise `MarkerError`, one marker present) already exercises and requires. Behavior is now: **confirmed** single marker (branch agrees) → daemon skipped entirely (new fast path); **unconfirmed** single marker → daemon tried first (branch-validated result wins if it succeeds), and only trusted as a fallback if the daemon call itself fails — identical to pre-batch behavior in that fallback case. `_pygit2_util` is already imported in `_review_common.py`; no new import is needed for that call. Also update the module-level "Public API" summary near the top of the file — the line `find_active_slug()   — branch-based slug detection with _mill/*.active glob fallback` is now inaccurate (it describes the pre-fix order); change it to reflect that a matching on-disk marker skips the daemon, otherwise branch-based detection runs as before with the on-disk marker as a last-resort fallback on daemon failure (e.g. `find_active_slug()   — branch-based slug detection; skips the daemon when a _mill/*.active marker confirms the current branch, else falls back to the marker only if the daemon call fails`). This preserves every existing observable outcome exactly — the only NEW behavior is the confirmed-marker fast path skipping the daemon; every other branch (unconfirmed-marker-then-daemon-succeeds, unconfirmed-marker-then-daemon-fails-trust-marker, multi-match, zero-match) is byte-for-byte identical to today. Update the docstring to describe this "confirm-first, trust-as-last-resort" behavior (see the replacement above) — do not describe it as "glob-first" or "on-disk-first," since branch validation still gates the fast path and the daemon-failure fallback is unconditional.
- **Commit:** `fix(review-common): skip daemon in find_active_slug only when on-disk marker matches current branch`

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
  1. **`find_active_slug` daemon-skip when on-disk marker agrees with current branch:** create a tmpdir that is a real git repo checked out on branch `<prefix><slug>` (reuse `_test_helpers._make_task_worktree` or an equivalent minimal fixture) with a `_mill/<slug>.active` file present, patch `_marker.slug_from_branch` to raise `AssertionError("daemon should not be called")` if invoked, call `find_active_slug(tmpdir, wiki_path, cfg)` with `cfg["spawn"]["branch_prefix"]` matching the fixture, and assert it returns the slug WITHOUT the patched `slug_from_branch` ever being called.
  2. **`find_active_slug` falls through to the daemon when the on-disk marker is stale (branch mismatch) — regression test for the plan-review round 1 correctness fix:** create a tmpdir that is a real git repo checked out on a DIFFERENT branch than the one named by a leftover `_mill/<stale-slug>.active` marker, patch `_marker.slug_from_branch` to return a distinct, branch-correct slug (do NOT raise from this mock — it must be callable and return a value), call `find_active_slug(tmpdir, wiki_path, cfg)`, and assert it returns the branch-derived slug from the mock, NOT the stale marker's slug — proving the fast path does not blindly trust a lone on-disk marker when the current branch disagrees.
  3. **`find_active_slug` multi-marker still resolves via existing behavior:** reuse the existing "multiple .active files -> ReviewError" test's fixture shape (already present later in the file, look for "find_active_slug glob fallback: multiple .active files") to confirm this batch's change didn't alter that outcome — this may already be fully covered by the existing test; only add a new assertion if the existing one doesn't already exercise the multi-match-then-daemon-also-fails path.
  4. **`load_task_title` daemon-skip on present status.md:** create a tmpdir with a `.millhouse` dir absent (or a minimal one) and a `status.md` at a path matching a `cfg["paths"]["status_md"]` you set explicitly in the test's `cfg` dict (e.g. `cfg = {"paths": {"status_md": "status.md"}}`), containing a YAML frontmatter block with `task: "My On-Disk Title"`, patch `_marker.task_data` to raise `AssertionError("daemon should not be called")` if invoked, call `load_task_title(tmpdir, wiki_path, cfg, "some-slug")`, and assert it returns `"My On-Disk Title"` without the patched `task_data` ever being called.
  5. **`load_task_title` falls through on missing/malformed status.md:** confirm the existing "load_task_title: task_title present in Home.md" and "load_task_title: non-task branch -> falls back to slug" tests (already in the file, unmodified) still pass — these exercise exactly the `KeyError`/`TaskHubError` fallback paths Card 4's `except` clause exists for. Do not weaken or remove these tests; they are regression coverage for Card 4's fallback correctness.
  6. **`_review_plan.py`'s `run()` benefits too (regression for the round-2 discussion-review correction):** this is verified by the batch's `verify:` command including `test-review-plan-flow.py` in its `--only` list — no new test is required in THIS card if that file's existing flow tests already exercise `run()`'s `load_task_title` call path end-to-end; only add a targeted test here if a review of `test-review-plan-flow.py` (read it, do not edit it — it's covered by `on-disk-first-resolution`'s `verify:` as a regression check, not a target of this card's edits) shows no such coverage exists today.
- **Commit:** `test(review-common): cover on-disk-first find_active_slug/load_task_title`

## Batch Tests

`verify:` runs `test-review-common.py` (Cards 3-5's primary coverage), `test-marker.py` (regression for `_marker.slug_from_branch`/`task_data`, unchanged but exercised transitively), and `test-review-plan-flow.py` (regression confirming `_review_plan.py run()`'s independent `load_task_title` call site — flagged in discussion review round 2 — still behaves correctly and benefits from the fast path).
