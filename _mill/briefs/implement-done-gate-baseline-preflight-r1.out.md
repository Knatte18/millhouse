{"status":"success","commit_sha":"937bbff4326311bd5d0a2b5c6c6e72a11586b45f","session_id":"a5dd4e89-e18b-4d6c-b236-b019f3031edb"}

All 4 of 4 cards committed (card-count self-check confirmed by diffing `70adfafb..HEAD` against the batch file's Commit messages — all four present, no extras, no gaps). Verify command passed (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-done-gate.py` — 5/5 cases PASS). Working tree is clean (`git status --porcelain --untracked-files=no` empty).

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/scripts/_done_gate.py` (new) — `run_preflight(gate_cmd, git_root) -> dict`, never raises.
- `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/templates/mill-config.yaml` and `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/mill-config.yaml` — new `pipeline.done_gate_baseline_preflight: false` key. Note: the hub's `mill-config.yaml` had no pre-existing `done_gate: null` line to anchor "immediately below" (unlike the template), so I appended the new key at the end of the hub's `pipeline:` section instead, keeping the comment text identical to the template's per the card's "match exactly" instruction.
- `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/skills/mill-go/SKILL.md` — new `### 0.55. Done-gate baseline pre-flight` subsection between `0. Wiki health-check` and `0.5. Baseline pre-flight`.
- `/home/knatte/Code/millhouse/wts/mill-go-batch-verify-baseline-reliability/plugins/mill/unit_tests/test-done-gate.py` (new) — 5 cases covering skipped/ok/blocked/truncation/never-raise.

Four commits on `hanf/mill-go-batch-verify-baseline-reliability`: `468682b0`, `5e4effb6`, `eafadf75`, `937bbff4` (HEAD), all pushed.
