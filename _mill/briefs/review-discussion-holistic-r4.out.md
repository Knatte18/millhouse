MILL_REVIEW_BEGIN
# Review: Remove batch review (plan-review.batch / code-review.batch)

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

Scope is unambiguous: config blocks, templates, per-batch script branches, skill sections, and test files are each named with enough precision that a plan writer would not need to guess. Every `### Decision:` carries rationale and a rejected alternative. No TBDs or open options remain.

Source-checked and confirmed accurate: `_config.py` (`ENV_REGISTRY`, `RENAMED_KEY_HINTS`, `walk_unknown_keys` block-path behaviour), `_review_common.py` (`discover_round`, `detect_resume_round`, `resolve_blocking_classes`, `DEFAULT_BLOCKING_CLASSES` keyed per role not scope), `_review_code.py` (`_splice_rename_nit_findings`, `start_sha` diff-scoping, `batch_name` legacy `run()`), `_nit_gate.py` (`approved-<batch>` / `holistic-approved` scan, `RE_BATCH` lookup), `millpy-fix.py` (`--scope`/`--batch-name`, `fixer-batch-brief.md` at line 580), `mill-go-base/SKILL.md` (Code Review loop at line 735, Stuck escalation at 874, phase regex at 146), `mill-plan/SKILL.md` (dispatch sites at 471/558, disabled-hub note at 473, cost-line aside at 510, flag description at 528-530), `mill-go2/SKILL.md` line 50, `test-fix-finalize.py` Test 5/6/7 content, `doc/backlog.md` line 332. All line numbers and code-behaviour claims match the worktree source.

Failure-mode coverage: stale config keys (warn not crash), historical status/review files (tolerant readers kept), in-flight resume (`approved-<batch>` phase preserved) are each addressed with stated rationale.

Testing strategy is concrete per-file, not generic, and includes a closing grep gate with an explicit allowed-hit list.

## Verdict

APPROVE
No blocking issues found; scope, decisions, and technical claims all check out against source.
MILL_REVIEW_END
