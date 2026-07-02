All three cards are committed, verify passes, and the tree is clean.

{"status":"success","commit_sha":"bbe1b412bd44728eb6b9398f053708a3e073cfb9","session_id":"a614735f-6b2b-46af-bc97-42f4cfe0ae2d"}

Summary of work done for batch `implement-baseline-stage`:

- **Card 5** — Created `C:\Code\millhouse\wts\agent-mode-gaps\plugins\mill\scripts\_verify_baseline.py` with `compute_baseline(project_root, git_root, parent_branch, module_wide_verify_cmd) -> str`. Creates a detached-HEAD transient worktree under `.scratch/` at the parent branch's tip SHA, reuses gitignored dependency dirs (`.venv`/`venv`/`node_modules`/`vendor`) via `_junction.create`, runs the verify command, applies the retry-then-control-check sequence, and tears the worktree down via `_worktree.remove_safe` in a `finally` block. Commit `dc7e29c4`.
- **Card 6** — Edited `C:\Code\millhouse\wts\agent-mode-gaps\plugins\mill\scripts\millpy-implement.py`: made `batch_name` optional (with post-parse validation), added `"baseline"` to `--stage` choices, moved the `overview_frontmatter`/`module_wide_verify_cmd` read earlier so the new task-scoped baseline branch can dispatch before batch-entry resolution, and added `_run_baseline_stage` (idempotent no-op on cached value, fail-safe on any error). Commit `bd01853f`.
- **Card 7** — Same file: hoisted a single `module_verify_baseline = _status.get_module_verify_baseline(status_path)` read and threaded it into both the `finalize` stage's `finalize_from_output(...)` call and the `full` stage's `_forward_output(...)` call. Commit `bbe1b412`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-status.py` passes (all cases including 59-62 covering the baseline-aware gate). Working tree is clean; all commits pushed to `hanf/agent-mode-gaps`.