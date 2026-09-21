MILL_REVIEW_BEGIN
# Review: Misc infra/wiki/PR/self-hosting reliability bugs

```yaml
duration_s: 196.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

All ten Decisions were cross-checked against source: `wiki/_client.py` (`_ensure_daemon`'s
`wait_for_socket_reachable` post-spawn loop, matching #1107's root-cause claim exactly),
`millpy-merge-in-subagent.py` (`_run_recompute_baseline`'s `overview_frontmatter.get("verify")`
bypassing `parse_verify_field`, confirming #1106), `_pr_state.py`/`_gh_issues.py` (`resolve_pr_state`
has no `--repo`, collapses all failures to `state: "none"`; `detect_repo(git_root)` signature matches
the proposed `detect_repo(Path(cwd))` call, confirming #1105), `wiki/_sync.py`/`_server.py`
(`commit_push`'s rebase-failure message and `_render_and_commit_all`'s silent
`except WikiPushError: pass`, confirming #1103), `mill-go-base/SKILL.md` sections 0.5/0.55/0.6
(0.55 uses `_done_gate.run_preflight`, distinct from 0.5/0.6's `--stage baseline` eager
`compute_batch_baselines` path, confirming #1102's scoping), `_status.py`'s
`get/set/clear_module_verify_baseline` accessor shape (confirming #1102's `baseline_parent_sha`
plan), `_agent_dispatch.py`/`_review_common.py` (`write_brief`, `output_path_for`,
`apply_cost_metadata`, `finalize_scope` signatures confirm neither finalize helper receives a brief
path today, confirming #1097), `csharp-build/SKILL.md` (current commands lack the node-reuse flags,
confirming #1094), and the exact `mill-plan`/`mill-start` SKILL.md grep counts for #1092 (12 bare in
mill-plan; mill-start's 10 split exactly 5 bare / 5 already-prefixed, verified line-by-line). #1077's
claim that `mill-merge/SKILL.md` already uses `:(exclude)` was also confirmed. No fabricated or
unverifiable claims found; no undecided items, scope ambiguity, or unaddressed failure modes surfaced
across the ten Decisions.

## Verdict

APPROVE
All ten Decisions' technical claims verified against source; no blocking gaps found.
MILL_REVIEW_END
