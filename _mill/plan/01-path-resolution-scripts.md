# Batch: path-resolution-scripts

```yaml
task: "Fix nested mill layout paths, whole-repo formatter drift, and stacked-branch PR cleanup"
batch: path-resolution-scripts
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths.py test-review-discussion-flow.py test-review-plan-flow.py
depends-on: []
```

## Batch Scope

Fix the two review CLIs so every `_mill/` path (briefs and active-slug glob
fallback) resolves to the hub project root via `_paths.resolve_hub_path()`
instead of `git_root` or raw `Path.cwd()`. Add nested-layout test coverage at the
path-resolution level. This batch is self-contained — it touches only the review
CLIs and the `test-paths.py` fixtures; the existing flow tests are run as
regression (flat layout, hub == git root, must be unchanged). No external
interface is produced; the SKILL-level path callsites are handled in batch 3 and
do not depend on this batch's code.

Batch-local decision: the nested-layout fixture lives in `test-paths.py` because
that is where `resolve_hub_path`/`resolve_task_path` are unit-tested; the review
CLIs are exercised for regression only (their flat-layout behavior must not change).

## Cards

### Card 1: Anchor millpy-review-discussion.py on the hub root

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `main()`, `project_root` is already
  `resolve_hub_path()` (`hub_dir`). Change the briefs path from
  `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")` to use
  `project_root` (the hub root) instead of `git_root`. Change the active-slug call
  from `find_active_slug(git_root, wiki_root, cfg)` to
  `find_active_slug(project_root, wiki_root, cfg)` so its glob fallback
  (`<arg>/_mill/*.active` in `_review_common.find_active_slug`) resolves under the
  hub root in a nested layout. Do not change branch-based slug detection (it
  resolves correctly from either root via pygit2 upward discovery).
- **Commit:** `fix(review): anchor discussion-review briefs and slug glob on hub root`

### Card 2: Anchor millpy-review-plan.py on the hub root

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `main()`, change `project_root = Path.cwd()` to
  `project_root = _paths.resolve_hub_path()`. This single change corrects every
  downstream consumer of `project_root` (`mill_dir`, `_reviewers.load`,
  `find_active_slug` at the existing line that already passes `project_root`, and
  `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`). Do NOT
  add a separate edit to the `find_active_slug` call — it already rides on
  `project_root`. Confirm `resolve_wiki_path(project_root)` still resolves the
  wiki correctly when `project_root` is the hub root (it accepts any worktree path).
- **Commit:** `fix(review): anchor plan-review project_root on hub root not cwd`

### Card 3: Nested-layout path-resolution fixture and assertions

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a nested-layout fixture — a temp git repo whose mill
  project (`.millhouse/config.local.yaml` + `_mill/`) lives in a subdirectory,
  with a `hub_relative_path` stub at the worktree root mirroring what
  `millpy-spawn.py` writes (`millpy-spawn.py` writes
  `{"hub_relative_path": hub_subpath}` to `<worktree>/.millhouse/config.local.yaml`).
  Assert `resolve_hub_path()` returns the nested mill dir for cwd == nested dir AND
  cwd == git root, and that `resolve_task_path(resolve_hub_path(), "_mill/status.md")`
  points at the file that exists under the nested root. Pair each nested assertion
  with a flat-layout assertion (hub == git root) proving no regression. Follow the
  existing tempfile + real-`git` fixture style already in `test-paths.py`.
- **Commit:** `test(paths): cover nested-mill-layout hub resolution`

## Batch Tests

`verify:` runs `test-paths.py` (the new nested-layout fixture + assertions for
`resolve_hub_path`/`resolve_task_path`) plus `test-review-discussion-flow.py` and
`test-review-plan-flow.py` as regression for the two edited CLIs — the flat-layout
(hub == git root) behavior of both review CLIs must be unchanged after the
`git_root`/`Path.cwd()` → hub-root switch. The flow tests are not edited, only
re-run; `test-paths.py` carries the new nested coverage.
