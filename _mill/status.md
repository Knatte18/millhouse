# Status

```yaml
phase: holistic-approved
slug: mill-unit-test-suite-breakage
branch: hanf/mill-unit-test-suite-breakage
plan: _mill/plan
parent: main
task: 'Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep'
task_description: |
  Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep
```

## Timeline

```text
discussing  '2026-08-08T16:49:13Z'
discussion-fix-r2  '2026-08-08T17:14:19Z'
discussed  '2026-08-08T17:14:19Z'
planning  '2026-08-08T17:26:30Z'
plan-review-r1  '2026-08-08T17:34:40Z'
plan-fix-r1  '2026-08-08T17:35:05Z'
plan-review-r2  '2026-08-08T17:40:28Z'
planned  '2026-08-08T17:40:49Z'
implementing  '2026-08-08T17:41:25Z'
approved-claude-sub-idle-mock  '2026-08-08T18:15:55Z'
approved-wiki-stub-fixes  '2026-08-08T18:23:25Z'
approved-forward-output-stuck-passthrough  '2026-08-08T18:26:57Z'
approved-full-suite-regression  '2026-08-08T18:29:00Z'
holistic-reviewing  '2026-08-08T18:29:25Z'
holistic-fixing  '2026-08-08T18:33:08Z'
nits-fixed-holistic  '2026-08-08T18:37:38Z'
holistic-approved  '2026-08-08T18:37:47Z'
```

## Batches

```yaml
batches:
  - name: claude-sub-idle-mock
    state: approved
    implementer_session: 33bb8421-b731-4b0f-a767-5e52fd6beb9c
    start_sha: 17e3be41f60052becd1d574d36f5f3ee9e1f0f9a
    commit_sha: f20bbd9074a6cf8ff1d128fcf7f47bbd03d4b3be
    verify_baseline_failures: []
  - name: wiki-stub-fixes
    state: approved
    implementer_session: 48f303e2-1bf2-41ed-b661-ee749125b3d3
    start_sha: fd08ccad034a78f0ff1ecea67fbb457b6318bb55
    commit_sha: 10bbe0caa842ed7f33770da9627fd865facbce51
    verify_baseline_failures: ['FAIL -- 9 of 16 tests: [''test_main_happy_path_calls_spawn_core_in_order'', ''test_write_settings_uses_short_name_and_slug'',
    ''test_main_backlog_empty_exits_zero'', ''test_main_value_error_from_picker_exits_one'',
    ''test_main_runtime_error_from_capture_branch_raises_system_exit'', ''test_create_hub_links_called_after_portal_creation'',
    ''test_main_dry_run_prints_worktree_status_path'', ''test_single_selection_does_not_call_multi_select_groom_then_claim'',
    ''test_spawn_aborts_when_origin_branch_already_exists'']', 'FAIL -- 11 of 14 tests:
    [''test_main_dry_run_exits_zero'', ''test_branch_name_uses_no_extra_slash'', ''test_main_happy_path_calls_spawn_core_helpers'',
    ''test_main_dirty_tree_abort_exits_one'', ''test_main_dirty_tree_stash_invokes_git_stash'',
    ''test_main_multi_path_skips_claim_in_wiki'', ''test_portal_entry_uses_resolve_container_path'',
    ''test_portal_before_recreate_active_junction_order'', ''test_portal_idempotent_when_already_correct'',
    ''test_main_hub_title_flip_when_cwd_is_hub'', ''test_hub_paths_use_cwd_not_git_root'']',
  '--- FAIL test-millpy-spawn.py (0.2s) ---', '--- FAIL test-millpy-claim.py (110.4s)
    ---', 'FAIL -- 2 of 2 in 110.4s: [''test-millpy-spawn.py'', ''test-millpy-claim.py'']']
  - name: forward-output-stuck-passthrough
    state: approved
    implementer_session: 7454d04a-0a70-4801-81c1-348a7051fda0
    start_sha: 1404092782a1f2904d8683a4d96f7f08612d8ba9
    commit_sha: 1ac67bf5eb2ac88467055a93f4e10fa016713c40
    verify_baseline_failures: [FAILED (failures=3), FAILED (failures=1), FAILED (failures=4), '--- FAIL test-bg-json-contract.py
    (0.2s) ---', '--- FAIL test-agent-mode-dispatch.py (0.3s) ---', '--- FAIL test-millpy-merge-in-subagent.py
    (0.4s) ---', 'FAIL -- 3 of 3 in 0.4s: [''test-bg-json-contract.py'', ''test-agent-mode-dispatch.py'',
    ''test-millpy-merge-in-subagent.py'']', '--- FAIL test-bg-json-contract.py (0.1s)
    ---', '--- FAIL test-agent-mode-dispatch.py (0.2s) ---', '--- FAIL test-millpy-merge-in-subagent.py
    (0.3s) ---', 'FAIL -- 3 of 3 in 0.3s: [''test-bg-json-contract.py'', ''test-agent-mode-dispatch.py'',
    ''test-millpy-merge-in-subagent.py'']']
  - name: full-suite-regression
    state: approved
    implementer_session: 8d7b5201-55b2-4107-a514-179f147112eb
    start_sha: b9fe4d88e949f1e7740c663a0696f7912c2a48ce
    commit_sha: 4eb32629e9cd57ba089bdde05e8dba7220326ab8
    verify_baseline_failures: [FAILED (failures=3), FAILED (failures=1), 'FAIL -- 9 of 16 tests: [''test_main_happy_path_calls_spawn_core_in_order'',
    ''test_write_settings_uses_short_name_and_slug'', ''test_main_backlog_empty_exits_zero'',
    ''test_main_value_error_from_picker_exits_one'', ''test_main_runtime_error_from_capture_branch_raises_system_exit'',
    ''test_create_hub_links_called_after_portal_creation'', ''test_main_dry_run_prints_worktree_status_path'',
    ''test_single_selection_does_not_call_multi_select_groom_then_claim'', ''test_spawn_aborts_when_origin_branch_already_exists'']',
  FAILED (failures=4), 'FAIL -- 11 of 14 tests: [''test_main_dry_run_exits_zero'',
    ''test_branch_name_uses_no_extra_slash'', ''test_main_happy_path_calls_spawn_core_helpers'',
    ''test_main_dirty_tree_abort_exits_one'', ''test_main_dirty_tree_stash_invokes_git_stash'',
    ''test_main_multi_path_skips_claim_in_wiki'', ''test_portal_entry_uses_resolve_container_path'',
    ''test_portal_before_recreate_active_junction_order'', ''test_portal_idempotent_when_already_correct'',
    ''test_main_hub_title_flip_when_cwd_is_hub'', ''test_hub_paths_use_cwd_not_git_root'']',
  '--- FAIL test-bg-json-contract.py (0.3s) ---', '--- FAIL test-agent-mode-dispatch.py
    (0.4s) ---', '--- FAIL test-millpy-spawn.py (0.4s) ---', '--- FAIL test-millpy-merge-in-subagent.py
    (0.7s) ---', '--- FAIL test-millpy-claim.py (110.4s) ---', 'FAIL -- 5 of 105 in
    327.2s: [''test-bg-json-contract.py'', ''test-agent-mode-dispatch.py'', ''test-millpy-spawn.py'',
    ''test-millpy-merge-in-subagent.py'', ''test-millpy-claim.py'']', '--- FAIL test-millpy-spawn.py
    (0.2s) ---', '--- FAIL test-millpy-merge-in-subagent.py (0.4s) ---', '--- FAIL
    test-millpy-claim.py (110.5s) ---']
```
