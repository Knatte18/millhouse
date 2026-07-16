2 of 2 cards committed for this batch (Card 16 and Card 17). Verify was run: `test-review-finalize.py` passes fully (including all new `--actual-model` coverage). `test-review-cli.py` fails, but only on two pre-existing failures (`test_plan_prepare_brief_path_uses_git_root`, `test_code_prepare_brief_path_uses_git_root`) unrelated to this batch's `--actual-model` changes — confirmed pre-existing by stashing my diff and reproducing the identical failure at the batch-start commit `fb886e3c`, and confirmed via `git log hanf/linux-port-more..HEAD` showing no same-task commit touches the failure's dependency chain (`_paths.py`, `_test_helpers.py`, or the test file's brief-path assertions). My new `test_finalize_actual_model_flag_reflected_in_review_file` function passed cleanly for all three CLIs.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/scripts/millpy-review-code.py`
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/scripts/millpy-review-plan.py`
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/scripts/millpy-review-discussion.py`
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/unit_tests/test-review-finalize.py`
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/unit_tests/test-review-cli.py`
- `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps/plugins/mill/skills/mill-go/SKILL.md`

{"status":"success","commit_sha":"82f4d80efb0ee7093d88cc85339f49ecef80ba25","session_id":"d0bddc2e-1ad2-431e-8678-fc7e3248b2b8"}