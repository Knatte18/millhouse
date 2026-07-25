Both commits match Card 5's and Card 6's `Commit:` messages exactly. 2 of 2 cards committed. Verify passed (`PASS -- all 2 unit tests in 0.4s`). No uncommitted tracked changes remain.

Summary: Both cards in this batch are complete — 2 of 2 cards committed.

- Card 5 (commit `79083a8c`): Deleted the duplicate `load_config`/`_deep_merge` in `plugins/mill/scripts/_review_common.py` and replaced it with a thin delegating wrapper calling `_config.load_config` (imported as `_core_load_config`), preserving the missing-source `ReviewError` and stale `review:`-key stderr warning. Removed now-unused imports (`_apply_dispatch_shim`, `apply_env_overrides`, `warn_unknown_keys`, `copy`).
- Card 6 (commit `20d42694`): Added `import _config` and a new regression test to `plugins/mill/unit_tests/test-review-common.py` proving the delegation inherits `_config.load_config`'s worktree-template cache-lag augmentation (the #676/#670 regression scenario).

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-config.py` passed (2/2 unit test files, including all five pre-existing `load_config` blocks unmodified). Ruff lint on both edited files showed only pre-existing finding categories (I001/RUF100/BLE001 already present in baseline before this batch's edits); no new lint categories introduced. `_codeguide/` is not initialized in this repo, so the codeguide-sync step in `git-commit` was a no-op.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-background-noise-and-stale-config/plugins/mill/scripts/_review_common.py`
- `/home/knatte/Code/millhouse/wts/mill-background-noise-and-stale-config/plugins/mill/unit_tests/test-review-common.py`

{"status":"success","commit_sha":"20d426941ea36cb489b2be6a72977d2c5296e6d","session_id":"442479e7-d65f-40cf-a51c-a18dbb7781f3","cards_done":[5,6]}
