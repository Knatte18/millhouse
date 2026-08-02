MILL_REVIEW_BEGIN
# Review: Verify/build gates leak shell state and ignore nested Go modules

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version unconfirmed)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

Verified against source: `_resolve_holistic_verify` (millpy-fix.py:67-120, join at line 116, both call sites at lines 451 and 574) matches the described bug exactly, including the untouched `cwd_to_batch_name` conflict-raise logic preceding the join. `_go_build_tag_retiering_stuck` (_implementer_common.py:1031), `_go_build_pattern` (line 980), and both hardcoded `cwd=project_root` build-invocation sites (lines 1140, 1177) confirmed as described; the pre-existing directory-existence guards at lines 1129/1165 (which the walk-up is correctly scoped to run after) also confirmed. The cited fail-open convention (`_plan_validate.py:2107`, `if not (project_root / "go.mod").exists(): return []`) is an exact match. `parse_verify_field` (`_plan_dag.py:366`) confirmed as the single normalizer producing `(command, cwd)` with plain-string batches resolving `cwd=None`. `_go_gate_mock` (test-implementer-common.py:46) confirmed to delegate non-`go` argv to the real `_subprocess_util.run` and currently capture only bare argv lists, consistent with the described `cwd_calls` widening plan. `test-millpy-fix.py` confirmed to load `millpy-fix.py` via `importlib` (module-level, not package-imported), making `_resolve_holistic_verify` directly callable from `TestMillpyFix` as claimed, with no I/O required.

Decisions are each paired with rationale and rejected alternatives; the r1 gaps (cwd_calls mock-widening shape, subpath-branch test case) are present and consistent with the rest of the discussion. Scope boundaries (no cwd-mapping-form changes, no dedup collapsing, no new general-purpose module-detection utility, no new gate trigger) are explicit and each has a stated rationale. No unresolved TBDs or undecided alternatives found. No CONSTRAINTS.md present at hub root (confirmed by glob).

## Verdict

APPROVE
All source-grounded claims verified accurate; decisions complete with rationale; no undecided items or scope ambiguity found.
MILL_REVIEW_END
