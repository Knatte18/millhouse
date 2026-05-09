# Batch: paths-helpers

```yaml
task: "35 (A) — Centralize path resolution across all three modes"
batch: paths-helpers
number: 1
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-paths.py
depends-on: []
```

## Batch Scope

This batch establishes the new path-resolution contract. It refactors `_paths.resolve_active_worktree` to handle all four mode/sub-dir combinations (M1, M1+sub, M2, M2+sub) and adds a sibling helper `resolve_active_hub` that returns the hub directory inside the resolved worktree. Tests are written first against the new signatures (Card 1, expected to fail at commit time); implementation follows (Card 2, tests now pass).

External interface for downstream batches:

```python
from _paths import resolve_active_worktree, resolve_active_hub
# Both: (container: Path, slug: str, *, cfg: dict, git_root: Path) -> Path
# resolve_active_worktree → git checkout root for the slug (for git-ops, branch ops).
# resolve_active_hub      → <wt>/<hub_relative_path> where .millhouse/ and task/ live.
# Both raise ActiveWorktreeNotFound / ActiveWorktreeSlugMismatch on failure.
```

The verify command runs the full `test-paths.py` suite (existing tests for unchanged helpers stay green; new + updated tests cover the two changed/new helpers across the four scenarios + error cases).

## Cards

### Card 1: tests for resolve_active_worktree (new signature) and resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-inplace.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update existing `resolve_active_worktree` test cases (currently at `test-paths.py:359-408`) and add new test cases for `resolve_active_hub`. The function `_paths.resolve_active_worktree` is being changed to signature `(container, slug, *, cfg, git_root)` keyword-only after the positional pair. The new function `_paths.resolve_active_hub` has the same signature.

  Add a private helper at the top of `test-paths.py`:

  ```python
  def _make_active_marker(mill_dir, *, slug, branch, title="Test", spawned_at="2026-01-01T00:00:00Z"):
      mill_dir.mkdir(parents=True, exist_ok=True)
      _active.write(mill_dir, slug=slug, task_title=title, branch=branch, spawned_at=spawned_at)

  def _write_stub(mill_dir, hub_relative_path):
      mill_dir.mkdir(parents=True, exist_ok=True)
      (mill_dir / "config.local.yaml").write_text(
          f"hub_relative_path: {hub_relative_path}\n", encoding="utf-8"
      )
  ```

  Update the existing three `resolve_active_worktree` blocks to pass `cfg={"hub_relative_path": "."}` and `git_root=<some path that won't trigger in-place>`. For the happy-path block, set `git_root` to a different directory so `is_inplace` returns False (no marker at git_root → `_active.read_all` raises → branch is skipped → falls through to worktree-dir lookup).

  Add new test cases for `resolve_active_worktree`:
  - **M1 (unchanged behavior, new sig):** container-form layout; `<container>/wts/<slug>/.millhouse/active.slug.md` matches; `cfg["hub_relative_path"] = "."`; `git_root` set to a sibling tmp dir with no marker → returns `<container>/wts/<slug>`.
  - **M1+sub:** same as M1 but `cfg["hub_relative_path"] = "src/Models"` → still returns the worktree root (NOT the sub-dir hub). `resolve_active_worktree` returns the git checkout root.
  - **M2 (in-place, hub_rel="."):** scaffold `<git_root>/.millhouse/active.slug.md` with matching slug+branch; do NOT create `<container>/wts/<slug>/`; patch `_subprocess_util.run` so `git rev-parse --abbrev-ref HEAD` returns the marker's branch → returns `git_root`.
  - **M2+sub (in-place + sub-dir hub):** scaffold `<git_root>/src/Models/.millhouse/active.slug.md`; `cfg["hub_relative_path"] = "src/Models"`; same subprocess mock → returns `git_root` (NOT `git_root/src/Models`).
  - **Error: slug mismatch in worktree dir:** worktree dir exists with marker for a different slug; `git_root` has no marker → raises `ActiveWorktreeSlugMismatch`.
  - **Error: nothing exists:** no worktree dir, no in-place marker → raises `ActiveWorktreeNotFound`.

  Add new test cases for `resolve_active_hub`. The helper resolves `hub_relative_path` from the caller's cfg as default and lets the worktree-root stub override when present.
  - **M1:** same scaffold as M1 above. `cfg = {"hub_relative_path": "."}`. mill-spawn writes a stub at `<wt>/.millhouse/config.local.yaml` with `hub_relative_path: .`; scaffold this stub. Both sources agree → returns `<container>/wts/<slug>`.
  - **M1+sub:** `cfg = {"hub_relative_path": "src/Models"}`. mill-spawn bootstraps the stub at `<wt>/.millhouse/config.local.yaml` with `hub_relative_path: src/Models`; scaffold both. Both sources agree → returns `<container>/wts/<slug>/src/Models`. Add a third assertion exercising the override path: drop the cfg override (`cfg = {"hub_relative_path": "."}`) but keep the stub at `<wt>/.millhouse/config.local.yaml` declaring `src/Models` → still returns `<container>/wts/<slug>/src/Models` (stub wins).
  - **M2:** in-place scaffold; `cfg = {"hub_relative_path": "."}`; do NOT write any stub at `<git_root>/.millhouse/config.local.yaml` beyond the active marker (mill-claim does not write a hub_relative_path stub at git_root). Returns `git_root`.
  - **M2+sub:** in-place scaffold; `cfg = {"hub_relative_path": "src/Models"}`; do NOT write a stub at `<git_root>/.millhouse/config.local.yaml` (mill-claim only writes at the hub). Returns `git_root/src/Models` — the caller's cfg is the only source.
  - **Error propagation:** when neither in-place nor worktree-dir exists → propagates `ActiveWorktreeNotFound` from the inner `resolve_active_worktree` call.

  Use `unittest.mock.patch("_subprocess_util.run", return_value=_make_run_result(stdout=branch))` for the branch-name lookup AND `unittest.mock.patch("_inplace.resolve_worktrees_dir", return_value=<some-tmp-dir-without-the-slug>)` to short-circuit `_inplace.is_inplace`'s second subprocess call (`resolve_main_worktree_root → git rev-parse --git-common-dir`). Patching only the subprocess mock works by coincidence (returns the branch name as a fake `--git-common-dir` output, which `Path("branch").parent` happens to resolve to the right tmp_path); patching `resolve_worktrees_dir` directly is the explicit pattern (matches `test-inplace.py`). Apply both patches in M2 and M2+sub.

  Tests in this card are expected to fail at the post-card commit; Card 2 makes them pass.
- **Commit:** `test(paths): add resolve_active_hub + new resolve_active_worktree scenarios`

### Card 2: implement resolve_active_worktree (new signature) and resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Refactor `_paths.resolve_active_worktree` to the new signature and add the new `resolve_active_hub` helper.

  Replace the existing `resolve_active_worktree` (currently at `_paths.py:255-292`) with:

  ```python
  def resolve_active_worktree(
      container_path: Path,
      slug: str,
      *,
      cfg: dict,
      git_root: Path,
  ) -> Path:
      """Return the git checkout root for the active task with the given slug.

      Detection order:
      1. In-place mode: when the cwd's hub has an active marker matching ``slug``
         AND ``_inplace.is_inplace`` returns True, return ``git_root``.
      2. Worktree mode: when ``container_path / "wts" / slug`` exists and its
         marker matches ``slug``, return that path.

      Raises:
          ActiveWorktreeNotFound: neither mode applies.
          ActiveWorktreeSlugMismatch: worktree-dir exists but marker slug differs.
      """
      import _active
      import _inplace

      hub_dir = resolve_hub_relative_path(git_root, cfg.get("hub_relative_path", "."))
      try:
          active_data = _active.read_all(hub_dir / ".millhouse")
      except _active.ActiveError:
          active_data = None
      if active_data is not None and active_data.get("slug") == slug:
          if _inplace.is_inplace(active_data, git_root, cfg):
              return git_root

      worktree = container_path / "wts" / slug
      if not worktree.is_dir():
          raise ActiveWorktreeNotFound(
              f"No worktree directory at {worktree} for slug {slug!r}"
          )
      marker_slug = _active.read_slug(worktree / ".millhouse")
      if marker_slug != slug:
          raise ActiveWorktreeSlugMismatch(
              f"Worktree at {worktree} has slug {marker_slug!r}, expected {slug!r}"
          )
      return worktree
  ```

  Add new helper directly below it:

  ```python
  def resolve_active_hub(
      container_path: Path,
      slug: str,
      *,
      cfg: dict,
      git_root: Path,
  ) -> Path:
      """Return the hub directory (where ``.millhouse/`` and ``task/`` live) for the slug.

      Calls ``resolve_active_worktree`` then resolves ``hub_relative_path``.
      Resolution order:
      1. Default from the caller's cfg: ``cfg.get("hub_relative_path", ".")``.
      2. Override from the resolved worktree's own ``.millhouse/config.local.yaml``
         when that file exists and declares ``hub_relative_path:``.

      The two-tier resolution covers both cases:
      - In-place mode (mill-claim): mill-claim writes the stub only at the hub
        (``<git_root>/<hub_rel>/.millhouse/``), never at ``<git_root>/.millhouse/``.
        So the worktree-root stub is absent for M2+sub and the caller's cfg is the
        authoritative source.
      - Worktree mode (mill-spawn): mill-spawn bootstraps a stub at
        ``<wt>/.millhouse/config.local.yaml`` carrying ``hub_relative_path:`` so
        cross-worktree consumers (cleanup, status) that have no cfg about the
        target can still resolve correctly.

      Propagates ``ActiveWorktreeNotFound`` and ``ActiveWorktreeSlugMismatch``
      from the inner call.
      """
      import yaml

      wt = resolve_active_worktree(container_path, slug, cfg=cfg, git_root=git_root)
      hub_subpath = cfg.get("hub_relative_path", ".")
      stub_path = wt / ".millhouse" / "config.local.yaml"
      if stub_path.exists():
          try:
              stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
              stub_value = stub_data.get("hub_relative_path")
              if stub_value is not None:
                  hub_subpath = stub_value
          except Exception:
              pass
      return resolve_hub_relative_path(wt, hub_subpath)
  ```

  Add `"resolve_active_hub"` to the `__all__` list at `_paths.py:74-87`.

  Update the module docstring at `_paths.py:1-65`: replace the existing `resolve_active_worktree(container_path, slug)` description (lines 56-60) with the new four-mode-aware description, and append a `resolve_active_hub(container_path, slug, *, cfg, git_root)` block immediately after.

  After this card lands, the verify command (`test-paths.py`) must pass.
- **Commit:** `feat(paths): add resolve_active_hub; resolve_active_worktree handles in-place + sub-dir hub`

## Batch Tests

The batch verify command runs `test-paths.py` end-to-end. The new and updated test cases in Card 1 cover all four mode/sub-dir scenarios for both helpers plus the two error paths for `resolve_active_worktree`. Existing tests for unchanged helpers (`resolve_git_root`, `resolve_hub_path`, `resolve_main_worktree_root`, `resolve_worktrees_dir`, `resolve_container_path`, `resolve_short_name`, `resolve_hub_relative_path`, `resolve_wiki_path`) remain unmodified and stay green.

After Card 1 commits, the test file references the new signature and the not-yet-existing `resolve_active_hub` — running it would error. mill-go does not run verify between cards inside a batch, so this intermediate red state is invisible. After Card 2 commits, the file's import + signature usage matches the implementation and `test-paths.py` is fully green.
