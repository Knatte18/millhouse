MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

Verified against source: `mill-go/SKILL.md` (per-batch append_phase at line 357 with no commit, holistic loop's append_phase+commit pattern at line 639, Agent-mode dispatch step numbering at lines 111-123, 378, 643), `mill-start/SKILL.md` (Status safeguard at line 159, "single source of truth" line 172, Discussion Review step 2 at line 168), `mill-plan/SKILL.md` (no "Status safeguard" hits, Plan Review step 2 at line 156, per-round `append_phase` at lines 215/220 occurring after dispatch and immediately before commit, no pre-dispatch uncommitted window), `_review_common.py` (`ReviewerOverstepError` docstring "operator resets manually" at line 113, `should_raise = bool(added) or (head_changed and not ff) or (bool(removed) and not ff)` at lines 206-208 confirming unconditional raise on `added`), `_agent_dispatch.py:191` (`write_brief`'s `unlink(missing_ok=True)` on the same-round `.out.md` only), `_cleanliness.py` (`clean_ephemeral_scope_violations` at 243 with `os.remove` at 309; `revert_out_of_scope_drift` at 324; only skill call site is mill-go/SKILL.md), `_status.py` (`append_phase` 444, `set_blocked` 252, `_find_batches_block` 550 returning `None` on absent heading, `_write_batches` 637, `phase_entry_timestamp` 832 with `occurrence: int = 1`; `append_recovery_log` does not yet exist, consistent with it being new work), `_paths.py` (`resolve_hub_path`/`resolve_active_hub` signatures match cited call sites in mill-start/mill-plan/mill-go), `_llm_claude.py:471` (`allowedTools="Read,Grep,Glob"`), and confirmed no `CONSTRAINTS.md` exists at the hub root.

No discrepancies found between the discussion's technical claims and current source state. All cited line numbers, function signatures, and behavioral descriptions are accurate. Scope is clearly bounded (widened detect-and-recover safeguard across three review loops + one targeted mill-go commit-ordering fix; root-cause identification, `worktree_snapshot_guard` changes, and non-review-loop phases explicitly excluded with rationale). Every `### Decision:` carries rationale and rejected alternatives; the Q&A log shows six prior rounds of GAP resolution (signature ambiguity, restore granularity, residual-risk documentation, wiring-site placement, same-file modify-then-delete window) all converging to a consistent, mutually-reinforcing design. Testing section names concrete unit-test scenarios (no-deletion, single/multi-file, staged-deletion, untracked-alongside-deletion, modified-alongside-deletion regression) plus an explicit manual/integration verification step, and explicitly scopes out what it deliberately does not cover. No undecided items or TBDs remain.

## Verdict

APPROVE
All claims verified against source; decisions, scope, and test coverage are complete and internally consistent.
MILL_REVIEW_END
