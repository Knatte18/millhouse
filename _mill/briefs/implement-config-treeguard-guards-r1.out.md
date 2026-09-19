Both cards' commit messages match exactly. 2 of 2 cards committed — full completion confirmed.

Both cards of batch `config-treeguard-guards` are complete: 2 of 2 cards committed, matching the batch's declared card count exactly.

- `/home/knatte/Code/millhouse/wts/shared-helper-script-validation-gaps/plugins/mill/scripts/_config.py` — added `RENAMED_KEY_HINTS`, updated `warn_unknown_keys` to append the hint for the two legacy pipeline round-cap keys.
- `/home/knatte/Code/millhouse/wts/shared-helper-script-validation-gaps/plugins/mill/unit_tests/test-config.py` — added `test_renamed_key_hints_named_in_warning` and `test_unrelated_unknown_key_no_hint_bleed`, registered in `main()`.
- `/home/knatte/Code/millhouse/wts/shared-helper-script-validation-gaps/plugins/mill/scripts/_treeguard.py` — added `isinstance` guards on `worktree`/`git_root` in `check_and_restore`.
- `/home/knatte/Code/millhouse/wts/shared-helper-script-validation-gaps/plugins/mill/unit_tests/test-treeguard.py` — added two new scenarios for str `worktree`/`git_root` TypeErrors.

Verify command (`run-all.py --only test-config.py test-treeguard.py`) passes with all tests green. Working tree is clean of tracked in-scope changes.

{"status":"success","commit_sha":"c676fbf3dd43d12c804d874c625b2e87706f0b40","session_id":"69f8d8b1-a936-4e5f-bfcb-af28e52fa379","cards_done":[1,2]}
