Clean — no tracked modifications outstanding. Both cards are committed, verify was `null` (skipped per brief), and the working tree is clean.

Summary of changes:
- `plugins/mill/scripts/millpy-merge-in-subagent.py` — added `--recompute-baseline` flag (independent of `--mode`, which is now optional), a manual validation check, and the new `_run_recompute_baseline(project_root, git_root, cfg)` function that clears then recomputes `module_verify_baseline` via `_verify_baseline.compute_baseline`, mirroring `millpy-implement.py`'s `_run_baseline_stage`.
- `plugins/mill/skills/mill-merge-in/SKILL.md` — added step "3.5. Baseline recompute" between steps 3 and 4, invoking the new flag, documenting its synchronous/fail-safe nature and the preserved No-op guarantee.

{"status":"success","commit_sha":"a0cb3f0f","session_id":"f369999a-bd87-451b-b51a-96e25b1e29d0"}