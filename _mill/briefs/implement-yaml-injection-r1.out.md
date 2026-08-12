3 of 3 cards committed (all complete): Card 14, Card 15, Card 16, matching the batch file's declared card count. Verify (`test-review-common.py`) passes, and the working tree is clean.

{"status":"success","commit_sha":"b5a27e30ffbc1cecf0dc19a31b131187d6785dfa","session_id":"1b30fd1e-841a-427a-b15f-b01293719c73","cards_done":[14,15,16]}

Summary of changes:
- `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/scripts/_review_common.py`: extracted `_inject_or_rewrite_yaml_field(raw_text, field, value)` from `apply_actual_model_override` (now a thin wrapper), added `apply_cost_metadata(raw_text, *, duration_s=None, tool_calls=None, cost_usd=None)`, added `sum_optional(a, b)`, and threaded three new keyword-only args (`duration_s`, `tool_calls`, `cost_usd`) through `finalize_scope`, applied before `parse_verdict` and surfaced in the returned dict.
- `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/unit_tests/test-review-common.py`: added coverage for `apply_cost_metadata` (identity, fresh injection order, in-place rewrite, partial set, no-fence no-op, later-block anchoring, exact formatting), `sum_optional` (both-None/one-None/both-set), and `finalize_scope` cost-metadata threading (dict + written-file assertions, plus byte-identical omission case).

{"status":"success","commit_sha":"b5a27e30ffbc1cecf0dc19a31b131187d6785dfa","session_id":"1b30fd1e-841a-427a-b15f-b01293719c73","cards_done":[14,15,16]}
