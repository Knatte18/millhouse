MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate, timeline, and script-portability bugs

```yaml
duration_s: 132.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

None.

Verified against source: `mill-plan/SKILL.md`'s "Unconditional round-recorded append" (line 534) and 4a/4b/4c/4d branches (538-600) confirm #914 is already fixed as claimed. The "Fork scope guardrail" template (150-159) exists exactly as described for the #919 port. mill-start's "Sub-investigation guidance" (188) and its "no tool restriction to lose" claim (197) match what #919 says needs correcting, and mill-start's Entry (79-107)/Phase sequence confirms it has no phase-gate re-entry check of its own. The Agent-mode prepare-envelope validator-fix re-invocation (433-440) and Step 1.5 subprocess retry (~351) line refs for #938's dispatch-site enumeration are accurate. CLAUDE.md's `## Script invocation` section matches the #939 decision's `$MILL_PYTHON`/`PYTHONPATH=` wording exactly, no contradiction. Helper signatures cited (`_status.set_blocked`, `_status.append_phase`, `_review_common.discover_round`, `_phase_wait.matches_wait_trigger`/`build_wait_command`) all exist as referenced. Unit test files named in Testing (`test-skill-helper-drift.py`, `test-brief-commit.py`, `test-guards.py`, `test-mill-go-variants.py`) all exist. Decisions carry rationale and rejected alternatives; scope in/out is explicit; no TBDs or undecided items found.

## Verdict

APPROVE
Claims cross-checked against source hold; decisions, scope, and testing coverage are sound.
MILL_REVIEW_END
