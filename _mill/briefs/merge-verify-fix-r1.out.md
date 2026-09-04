Root cause and fix summary:

**Root cause**: Commit `85a4bbfc` changed `_review_common.load_config()` to unconditionally use `git_root` as the config `worktree_root` whenever `millpy-review-plan.py` passed it in. That was correct for mill-spawn's nested-hub layout (a stub with `hub_relative_path:` at `git_root/.millhouse/`, pointing to the real config at the hub). But test28's mill-claim in-place nested-hub fixture has no stub at `git_root` at all — the real config (`hub_relative_path` + `spawn.branch_prefix`) lives only at the hub's own `.millhouse/config.local.yaml`. With `worktree_root` forced to `git_root`, that config was never read, so `cfg["spawn"]["branch_prefix"]` fell back to `""` and `cfg["hub_relative_path"]` was never set — which made `_paths.resolve_active_worktree`'s dir-slug check compare the un-stripped branch (`"hanf/test-slug"`) against the slug (`"test-slug"`), raising `ActiveWorktreeSlugMismatch` and crashing the `--stage prepare` CLI entry point (test28).

**Fix**: in `plugins/mill/scripts/_review_common.py`, `load_config()` now only uses `git_root` as `worktree_root` when `git_root/.millhouse/config.local.yaml` actually exists; otherwise it keeps the existing `mill_dir.parent` (hub root) fallback, so the hub's own local config is no longer skipped.

Files touched:
- `/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter/plugins/mill/scripts/_review_common.py` (`load_config`, docstring + worktree_root selection)

Verification: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py` now passes all tests. Also re-ran `test-config.py` (which directly exercises `load_config`'s `git_root` opt-in behavior) — all pass, no regressions. Ran the full `run-all.py` suite; the only two remaining failures (`test-mill-go-base-agent-only.py`, `test-millpy-validate-plan.py`) are pre-existing on this branch prior to my change (confirmed via `git stash`) and outside the brief's scope.

Committed as `4f4a1b8e4347350c13f826e2d3244379669c7e5d`.

{"status":"success","commit_sha":"4f4a1b8e4347350c13f826e2d3244379669c7e5d"}
