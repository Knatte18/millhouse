# Batch: paths-skip-slug-validation

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: paths-skip-slug-validation
number: 3
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-paths-sanitize.py test-review-common.py"
depends-on: [2]
```

## Batch Scope

Groundwork for #675, plus closing a previously-undiscovered daemon-reintroduction gap in `_review_common.resolve_path` found during plan review round 3. `_paths.resolve_active_hub` (used by the project-root-rebinding batches to fix `briefs_dir`/`project_root` resolution) calls `resolve_active_worktree`, whose in-place-mode check unconditionally calls `_marker.slug_from_branch` (`_paths.py:399`) — which itself unconditionally hits the wiki daemon's `_dispatch()` retry loop via `_list_tasks_brief_with_retry` (`_marker.py:81`), the same latency `on-disk-first-resolution` removes elsewhere. Using `resolve_active_hub` unmodified for the project-root-rebinding batches' fix would silently reintroduce that daemon round-trip on every `--stage prepare` call in the hot per-batch dispatch path — undermining this task's other fix. This batch adds an opt-in `skip_slug_validation` parameter that lets a caller who already holds a validated `slug` skip the daemon call entirely, using a cheap git-only branch comparison instead. External interface the later batches consume: `resolve_active_hub(container_path, slug, *, cfg, git_root, skip_slug_validation=False)` and `resolve_active_worktree(container_path, slug, *, cfg, git_root, skip_slug_validation=False)` — both default to today's unchanged behavior; `millpy-abandon.py`'s existing `resolve_active_hub` call is unaffected (keeps the default `False`). `_review_common.resolve_path`'s own internal `resolve_active_hub` call is **not** left unaffected, unlike originally scoped — see Card 8: `resolve_path` is always called with an already-resolved `slug` (every call site passes an explicit `slug` obtained earlier in that CLI's own flow — see `_review_code.py`, `_review_plan.py`, `_review_discussion.py`, and the `millpy-review-*.py` CLIs), so it is exactly the kind of caller `skip_slug_validation` exists for, and leaving it unfixed would mean every review CLI's `reviews_dir`/`plan_dir`/`discussion_path` resolution (called on both `prepare` and `finalize` — i.e. at least twice per review round) keeps paying the full daemon round-trip this task exists to eliminate, regardless of how the other batches land.

Depends on `on-disk-first-resolution` (batch 2): Card 8 edits `_review_common.py` and `test-review-common.py`, the same two files `on-disk-first-resolution`'s Cards 3-5 edit. The two batches have no data dependency on each other, but editing the same files from two unordered-parallel implementer sessions risks a merge conflict or one session working from a stale view of the other's edits — the dependency edge serializes them instead.

## Cards

### Card 6: Add skip_slug_validation fast path to resolve_active_worktree/resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `resolve_active_worktree` (`_paths.py`), add a keyword-only parameter `skip_slug_validation: bool = False`. When `True`, replace the unconditional `_marker.slug_from_branch` call with a cheap, daemon-free branch comparison:

  ```python
  def resolve_active_worktree(
      container_path: Path,
      slug: str,
      *,
      cfg: dict,
      git_root: Path,
      skip_slug_validation: bool = False,
  ) -> Path:
      """...(existing docstring, plus one new paragraph documenting skip_slug_validation -- see below)..."""
      import _inplace
      import _marker

      if skip_slug_validation:
          try:
              branch = _pygit2_util.current_branch(git_root) or ""
          except _pygit2_util.GitOpsError:
              branch = ""
          prefix = cfg.get("spawn", {}).get("branch_prefix", "")
          marker_slug = branch.removeprefix(prefix) if branch.startswith(prefix) else None
      else:
          try:
              wiki_path = resolve_wiki_path(git_root)
              marker_slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
          except (_marker.MarkerError, SystemExit):
              marker_slug = None
      if marker_slug == slug and _inplace.is_inplace(slug, git_root, cfg):
          return git_root

      worktree = container_path / "wts" / slug
      # ... rest of the function (worktree-dir lookup, ActiveWorktreeNotFound,
      # branch/dir_slug mismatch check, ActiveWorktreeSlugMismatch) is UNCHANGED.
  ```

  Add a docstring paragraph explaining: `skip_slug_validation=True` is for callers that already hold a `slug` validated by some other means (e.g. an on-disk source) and want to avoid the daemon round-trip `slug_from_branch` performs; it trades `slug_from_branch`'s full validation (including its non-standard-branch-name fallbacks against Home.md) for a simple prefix-strip branch comparison, which is correct for the standard `<branch_prefix><slug>` branch-naming convention every `mill-spawn`/`mill-claim` worktree uses, but will not detect in-place mode for a non-standard branch name — an acceptable trade-off since this parameter is only used by callers in the standard dispatch path. Add `import _pygit2_util` at module scope if not already imported (verify: `_pygit2_util` is very likely already imported given `resolve_active_worktree`'s existing body calls `_pygit2_util.current_branch(worktree)` further down — reuse that same import, do not add a duplicate). Also update `_paths.py`'s module-level docstring, which lists both functions' signatures — add `skip_slug_validation` to both listed signatures there so the module-level summary doesn't go stale relative to the actual (post-edit) function signatures.

  Then, in `resolve_active_hub`, add the same keyword-only parameter and thread it through:

  ```python
  def resolve_active_hub(
      container_path: Path,
      slug: str,
      *,
      cfg: dict,
      git_root: Path,
      skip_slug_validation: bool = False,
  ) -> Path:
      ...
      wt = resolve_active_worktree(
          container_path, slug, cfg=cfg, git_root=git_root,
          skip_slug_validation=skip_slug_validation,
      )
      ...  # rest unchanged
  ```
- **Commit:** `feat(paths): add skip_slug_validation fast path to resolve_active_worktree/resolve_active_hub`

### Card 7: Add tests for skip_slug_validation

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Following the existing `resolve_active_worktree`/`resolve_active_hub` test block's style in `test-paths.py` (the M1/M1+sub/M2/M2+sub scenarios using `patch(...)` and `print("PASS: ...")`), add:
  1. **`skip_slug_validation=True`, in-place mode:** construct the same M2 (in-place) fixture the existing `"resolve_active_worktree M2 — in-place returns git_root"` test uses, but patch `_marker.slug_from_branch` to raise `AssertionError("daemon should not be called")` if invoked, call `resolve_active_worktree(..., skip_slug_validation=True)`, and assert it returns `git_root` without the patched `slug_from_branch` ever being called.
  2. **`skip_slug_validation=True`, worktree mode:** construct the same M1 (container-form worktree) fixture the existing `"resolve_active_worktree M1 (new sig)"` test uses, same daemon-must-not-be-called patch, call with `skip_slug_validation=True`, assert it returns `container_path / "wts" / slug` without the patched `slug_from_branch` being called.
  3. **`skip_slug_validation=False` (default) unchanged:** re-run one of the existing M1/M2 tests' exact assertions with the new parameter explicitly passed as `False`, confirming byte-for-byte identical behavior to the pre-existing (now-default) code path — this guards `millpy-abandon.py`'s existing `resolve_active_hub` call site, which does not pass the new parameter and must keep its current (default) behavior.
  4. **`resolve_active_hub` threads the parameter:** one test calling `resolve_active_hub(..., skip_slug_validation=True)` on an in-place (M2) fixture, patched daemon-must-not-be-called, asserting the hub path resolves correctly.
- **Commit:** `test(paths): cover skip_slug_validation fast path`

### Card 8: Wire skip_slug_validation into resolve_path's internal resolve_active_hub call

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** **New card added during plan review round 3** — a previously-undiscovered daemon-reintroduction gap distinct from the `briefs_dir`/`project_root` rebind fixed by `project-root-rebinding-implement-side`/`project-root-rebinding-review-side`. `_review_common.resolve_path(path_tmpl, slug)` (see its docstring: "Computes the container, git_root, and cfg internally") independently resolves its own `container_path`/`hub_dir`/`cfg`, then calls:

  ```python
  active_hub = _paths.resolve_active_hub(
      container_path,
      slug,
      cfg=cfg,
      git_root=git_root,
  )
  ```

  with no `skip_slug_validation`, so it always defaults to `False` and pays the full daemon round-trip via `resolve_active_worktree`'s `slug_from_branch` call — regardless of anything the other batches in this plan fix. `resolve_path` is called (via `_review_code.py`, `_review_plan.py`, `_review_discussion.py`, and the `millpy-review-*.py` CLIs directly) to resolve `reviews_dir`/`plan_dir`/`discussion_path` on both the `prepare` and `finalize` stage of every review round — at least twice per round. Change the call to:

  ```python
  active_hub = _paths.resolve_active_hub(
      container_path,
      slug,
      cfg=cfg,
      git_root=git_root,
      skip_slug_validation=True,
  )
  ```

  This is safe because `resolve_path` is always invoked with an already-resolved `slug` — every call site passes an explicit `slug` value obtained earlier in that CLI's own flow (via `find_active_slug` or a `--slug` override) — never a value `resolve_path` itself needs to independently re-derive or re-validate. Then, in `test-review-common.py`, extend the existing `resolve_path` test block (look for "resolve_path: discussion.md -> worktree root" and the "plan/ and reviews/ templates" test immediately after it) with one new test: patch `_marker.slug_from_branch` to raise `AssertionError("daemon should not be called")` if invoked, call `resolve_path(...)` against a fixture where the in-place/worktree resolution would otherwise succeed without daemon validation (reuse this file's existing `_make_worktree_fixture` helper), and assert the call succeeds without the patched `slug_from_branch` ever being called. Do not weaken or remove the existing `resolve_path` tests.
- **Commit:** `fix(review-common): pass skip_slug_validation through resolve_path's resolve_active_hub call`

## Batch Tests

`verify:` runs `test-paths.py` (Cards 6-7's primary coverage), `test-paths-sanitize.py` (regression — unrelated function in the same module, cheap to include and already part of this module's existing test surface), and `test-review-common.py` (Card 8's coverage for `resolve_path`, plus regression for `on-disk-first-resolution`'s Cards 3-4 since this batch depends on it and shares the same file).
