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
- **Requirements:** Add a new test case to `test-review-common.py` that exercises the in-place branch of `_review_common.resolve_path`. The test must catch the original bug (`ActiveWorktreeNotFound` for in-place tasks). Also extend `_make_worktree_fixture` so the four existing M1 `resolve_path` tests don't regress when Card 4's `load_config` prerequisite lands.

  **Pre-step — extend `_make_worktree_fixture`** (currently at `test-review-common.py:22-62`): after creating the worktree git repo + active marker, also write a minimal wiki config. Append these lines just before `return container, worktree`:

  ```python
  wiki_root = container / "wiki"
  wiki_root.mkdir(parents=True, exist_ok=True)
  (wiki_root / "config.yaml").write_text(
      "paths:\n  discussion_file: task/discussion.md\n",
      encoding="utf-8",
  )
  ```

  Container-form sibling resolution (`_sibling.resolve_path("wiki", main_root)`) lands at `<container>/wiki/`, so `_paths.resolve_wiki_path(worktree)` finds the new file. The four existing M1 `resolve_path` tests stay green because they cd into `<worktree>`, which has no local `.millhouse/config.local.yaml` — `load_config` treats that as optional and returns the shared cfg only. `cfg["hub_relative_path"]` defaults to `"."` via the helpers' `.get(...)` calls.

  **New M2 test:** use a separate fixture (do NOT reuse `_make_worktree_fixture` because M2 has no `<container>/wts/<slug>/` directory). `tempfile.TemporaryDirectory()` for the layout, scaffold `<hub>/.millhouse/active.slug.md` with matching slug+branch, do NOT create `<container>/wts/<slug>/`, mock `_subprocess_util.run` for `git rev-parse --abbrev-ref HEAD` to return the marker's branch, and patch `_paths.resolve_hub_path` to return `<hub>` (this is what the new `resolve_path` uses to source cfg). Patch `_paths.resolve_git_root` to return `git_root` so the helper does not shell out. Patch `_inplace.resolve_worktrees_dir` to return a tmp dir without the slug subdir so `is_inplace` returns True.

  For M2 (hub_rel="."): `<hub>` IS `<git_root>`. Write `<hub>/.millhouse/config.local.yaml` with `hub_relative_path: .` and `<wiki_root>/config.yaml` with `paths: {discussion_file: task/discussion.md}`. Patch `_paths.resolve_wiki_path` with `unittest.mock.patch("_paths.resolve_wiki_path", return_value=wiki_root)`.

  Assertion: `resolve_path("task/discussion.md", slug) == git_root / "task" / "discussion.md"`.

  For M2+sub (in-place + sub-dir hub): `<hub>` is `<git_root>/src/Models`. Scaffold the active marker at `<hub>/.millhouse/active.slug.md` (NOT at `<git_root>/.millhouse/`, which is what mill-claim actually writes — mill-claim does not bootstrap a stub at `git_root/.millhouse/`). Write `<hub>/.millhouse/config.local.yaml` with `hub_relative_path: src/Models`. Patch `_paths.resolve_hub_path` to return `<hub>`. Assert `resolve_path("task/discussion.md", slug) == git_root / "src" / "Models" / "task" / "discussion.md"`.

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
        - git_root via _paths.resolve_git_root()
        - container via _paths.resolve_container_path(git_root)
        - hub_dir via _paths.resolve_hub_path() (Path.cwd().resolve() — the hub
          where mill scripts run; equals git_root for hub_relative_path == ".")
        - cfg via load_config(_paths.resolve_wiki_path(git_root), hub_dir / ".millhouse")

      cfg is sourced from the hub's own .millhouse/, not from git_root/.millhouse/,
      because mill-claim writes hub_relative_path only at the hub (it does not
      bootstrap a stub at git_root/.millhouse/ the way mill-spawn does).

      Returns active_hub / path_tmpl after substituting any "<SLUG>" token.

      Raises:
          _paths.ActiveWorktreeNotFound | _paths.ActiveWorktreeSlugMismatch:
              propagated from the inner resolve_active_hub call.
      """
      git_root = _paths.resolve_git_root()
      container_path = _paths.resolve_container_path(git_root)
      wiki_root = _paths.resolve_wiki_path(git_root)
      hub_dir = _paths.resolve_hub_path()
      cfg = load_config(wiki_root, hub_dir / ".millhouse")
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

The batch verify command runs `test-review-common.py`. Existing tests for the worktree-mode behavior (M1) remain green after Card 3 extends `_make_worktree_fixture` to scaffold `<container>/wiki/config.yaml` (Card 4 makes `resolve_path` call `load_config`, which requires the shared config to exist). `resolve_active_hub` returns `<wt>` when `hub_relative_path == "."`, matching the previous M1 behavior — no assertion changes needed for the four existing M1 tests. New tests added in Card 3 cover M2 and M2+sub. There are no Card 4-specific tests beyond what Card 3 added — the impl is verified entirely by Card 3's fixture-extension + new assertions plus the existing suite.
