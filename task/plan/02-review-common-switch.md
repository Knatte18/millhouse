# Batch: review-common-switch

```yaml
task: "35 (A) — Centralize path resolution across all three modes"
batch: review-common-switch
number: 2
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
depends-on: [1]
```

## Batch Scope

Switch `_review_common.resolve_path` from `_paths.resolve_active_worktree` to `_paths.resolve_active_hub`. This is the original bug surface from the external user report: the path templates `task/discussion.md`, `task/plan/`, `task/reviews/` live under the hub, not the git checkout root, and the current code crashes with `ActiveWorktreeNotFound` for in-place tasks.

The function signature stays `resolve_path(path_tmpl: str, slug: str) -> Path` — internal change only. Callers pass the same arguments; behavior changes only for in-place tasks (now works) and sub-dir hub configs (now correctly returns `<wt>/<hub_rel>/<tmpl>` instead of `<wt>/<tmpl>`).

A focused unit test is added to `test-review-common.py` for the in-place branch. Card 3 (test) is committed before Card 4 (impl) per the shared TDD-first decision.

## Cards

### Card 3: focused in-place test for resolve_path

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/unit_tests/test-paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new test case to `test-review-common.py` that exercises the in-place branch of `_review_common.resolve_path`. The test must catch the original bug (`ActiveWorktreeNotFound` for in-place tasks).

  Use the same fixture style as the M2 scenario in `test-paths.py` Card 1: `tempfile.TemporaryDirectory()` for the layout, scaffold `<git_root>/.millhouse/active.slug.md` with matching slug+branch, do NOT create `<container>/wts/<slug>/`, mock `_subprocess_util.run` for `git rev-parse --abbrev-ref HEAD` to return the marker's branch, and patch `Path.cwd` (or `os.chdir`) to point at `git_root`. Patch `_paths.resolve_git_root` to return `git_root` so the helper does not shell out.

  Also write `<wiki_root>/config.yaml` with the minimum keys `paths: {discussion_file: task/discussion.md}` and write the wiki path so `_review_common.load_config` finds it. The `_paths.resolve_wiki_path` call should resolve to that wiki root — patch it with `unittest.mock.patch("_paths.resolve_wiki_path", return_value=wiki_root)`.

  Assertion: `resolve_path("task/discussion.md", slug) == git_root / "task" / "discussion.md"`.

  Add a second assertion for the in-place + sub-dir hub case (M2+sub): scaffold `<git_root>/src/Models/.millhouse/active.slug.md`, write `<git_root>/.millhouse/config.local.yaml` with `hub_relative_path: src/Models`, also write `<git_root>/src/Models/.millhouse/config.local.yaml` with the same key (the helper reads from the resolved worktree's stub). Assert `resolve_path("task/discussion.md", slug) == git_root / "src" / "Models" / "task" / "discussion.md"`.

  Test will fail at this card's commit because Card 4 has not yet switched the function — that's expected per TDD-first ordering.
- **Commit:** `test(review-common): cover in-place + sub-dir hub branches of resolve_path`

### Card 4: switch resolve_path to resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the body of `_review_common.resolve_path` (currently at `_review_common.py:155-184`) so it calls `_paths.resolve_active_hub` instead of `_paths.resolve_active_worktree`. Public signature stays `resolve_path(path_tmpl: str, slug: str) -> Path`.

  New body:

  ```python
  def resolve_path(path_tmpl: str, slug: str) -> Path:
      """Resolve a config path template to an absolute path inside the active hub.

      Computes the container, git_root, and cfg internally:
        - container via _paths.resolve_container_path(Path.cwd())
        - git_root via _paths.resolve_git_root()
        - cfg via load_config(_paths.resolve_wiki_path(git_root), git_root / ".millhouse")

      Returns active_hub / path_tmpl after substituting any "<SLUG>" token.

      Raises:
          _paths.ActiveWorktreeNotFound | _paths.ActiveWorktreeSlugMismatch:
              propagated from the inner resolve_active_hub call.
      """
      git_root = _paths.resolve_git_root()
      container_path = _paths.resolve_container_path(git_root)
      wiki_root = _paths.resolve_wiki_path(git_root)
      cfg = load_config(wiki_root, git_root / ".millhouse")
      active_hub = _paths.resolve_active_hub(
          container_path, slug, cfg=cfg, git_root=git_root,
      )
      resolved_tmpl = path_tmpl.replace("<SLUG>", slug)
      return active_hub / resolved_tmpl
  ```

  Update the function's docstring (lines 156-179) to describe the new behavior: returns the path inside the active hub (not the worktree root), works for all three modes, propagates the same two exceptions plus any `ReviewError` from `load_config` if `wiki/config.yaml` is missing.

  Also update the module-level public-API docstring at `_review_common.py:17` from `resolve_path() — locate a path inside the active worktree from a config template` to `resolve_path() — locate a path inside the active hub (where task/ lives) from a config template`.

  After this card lands, both new test cases from Card 3 must pass alongside the existing `resolve_path` tests in `test-review-common.py`.
- **Commit:** `refactor(review-common): switch resolve_path to resolve_active_hub`

## Batch Tests

The batch verify command runs `test-review-common.py`. Existing tests for the worktree-mode behavior (M1) remain green because `resolve_active_hub` returns `<wt>` when `hub_relative_path == "."`, which equals the previous behavior. New tests added in Card 3 cover M2 and M2+sub. There are no Card 4-specific tests beyond what Card 3 added — the impl is verified entirely by Card 3's new assertions plus the existing suite.
