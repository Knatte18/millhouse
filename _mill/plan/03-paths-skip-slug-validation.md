# Batch: paths-skip-slug-validation

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: paths-skip-slug-validation
number: 3
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-paths-sanitize.py"
depends-on: []
```

## Batch Scope

Groundwork for #675. `_paths.resolve_active_hub` (used by the next batch to fix `briefs_dir`/`project_root` resolution) calls `resolve_active_worktree`, whose in-place-mode check unconditionally calls `_marker.slug_from_branch` (`_paths.py:399`) — which itself unconditionally hits the wiki daemon's `_dispatch()` retry loop via `_list_tasks_brief_with_retry` (`_marker.py:81`), the same latency `on-disk-first-resolution` removes elsewhere. Using `resolve_active_hub` unmodified for the next batch's fix would silently reintroduce that daemon round-trip on every `--stage prepare` call in the hot per-batch dispatch path — undermining this task's other fix. This batch adds an opt-in `skip_slug_validation` parameter that lets a caller who already holds a validated `slug` skip the daemon call entirely, using a cheap git-only branch comparison instead. External interface the next batch consumes: `resolve_active_hub(container_path, slug, *, cfg, git_root, skip_slug_validation=False)` and `resolve_active_worktree(container_path, slug, *, cfg, git_root, skip_slug_validation=False)` — both default to today's unchanged behavior; existing callers (`millpy-abandon.py`, `_review_common.py`'s own `resolve_active_hub` call) are unaffected.

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

  Add a docstring paragraph explaining: `skip_slug_validation=True` is for callers that already hold a `slug` validated by some other means (e.g. an on-disk source) and want to avoid the daemon round-trip `slug_from_branch` performs; it trades `slug_from_branch`'s full validation (including its non-standard-branch-name fallbacks against Home.md) for a simple prefix-strip branch comparison, which is correct for the standard `<branch_prefix><slug>` branch-naming convention every `mill-spawn`/`mill-claim` worktree uses, but will not detect in-place mode for a non-standard branch name — an acceptable trade-off since this parameter is only used by callers in the standard dispatch path. Add `import _pygit2_util` at module scope if not already imported (verify: `_pygit2_util` is very likely already imported given `resolve_active_worktree`'s existing body calls `_pygit2_util.current_branch(worktree)` further down — reuse that same import, do not add a duplicate).

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
  3. **`skip_slug_validation=False` (default) unchanged:** re-run one of the existing M1/M2 tests' exact assertions with the new parameter explicitly passed as `False`, confirming byte-for-byte identical behavior to the pre-existing (now-default) code path — this guards `millpy-abandon.py` and `_review_common.py`'s existing `resolve_active_hub` call sites, neither of which pass the new parameter.
  4. **`resolve_active_hub` threads the parameter:** one test calling `resolve_active_hub(..., skip_slug_validation=True)` on an in-place (M2) fixture, patched daemon-must-not-be-called, asserting the hub path resolves correctly.
- **Commit:** `test(paths): cover skip_slug_validation fast path`

## Batch Tests

`verify:` runs `test-paths.py` (Cards 6-7's primary coverage) and `test-paths-sanitize.py` (regression — unrelated function in the same module, cheap to include and already part of this module's existing test surface).
