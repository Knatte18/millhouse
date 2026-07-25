MILL_REVIEW_BEGIN
# Review: mill-plan review severity counting and validation schema gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] Commit:none carve-out signal options conflict with the gate's own invariant
**Section:** Technical context — "Backend no-content-commit gate must gain a `Commit: none`-aware exemption"
**Issue:** The paragraph quotes the gate's docstring approvingly ("unaffected by cards_done: zero commits means zero work regardless of any self-report" — confirmed verbatim in `_implementer_common.py:121-122` and `~1427-1430`), then offers two illustrative signal options for the carve-out, one of which is "a flag...reported by the implementer" — a self-report signal that directly violates the invariant just quoted (an implementer could falsely claim "all my remaining cards were Commit: none" to bypass the zero-commit check even when real work was skipped). The paragraph also claims the carve-out should mirror `nits_only` "exactly," but `nits_only` is a CLI flag supplied by the orchestrator via `millpy-fix.py --nits-only` (confirmed at `millpy-fix.py:170,345`), not implementer self-report — so the two candidate signal shapes are not equivalent, and only one of them actually matches the stated precedent.
**Fix:** Decide in discussion that the signal must be code-derived (plan-level scan of which cards in `cards_done`/the batch map to `Commit: none`), not implementer self-reported, to preserve the gate's self-report-independence invariant and genuinely mirror `nits_only`'s orchestrator-supplied nature.

### [NOTE] Unconditional heading+YAML dual-scan may double-count a single finding
**Section:** Technical context — unrecognized-severity scan (unconditional dual-mechanism paragraph)
**Issue:** The new helper scans both `### [XXX]` headings and yaml `findings:` entries unconditionally with no dedup, whereas `parse_blocking_count` itself already guards against exactly this shape for known severities ("heading wins over yaml: heading_count > 0 skips the yaml scan entirely," tested at `test-review-common.py:1994-1998`). If a reviewer emits both a heading and a mirroring yaml entry for the same unrecognized-severity finding, the new helper would count it twice, inflating `blocking_count` shown in the operator-facing "M BLOCKING findings remain" message (`mill-plan/SKILL.md:225`) — though convergence correctness (`blocking_count == 0`) is unaffected.
**Fix:** Note the dedup gap in the plan (or explicitly accept the double-count risk as low-probability/cosmetic-only) so it isn't silently reintroduced.

## Verdict
GAPS_FOUND
One GAP: Commit:none gate carve-out's self-report vs. code-derived signal options conflict with the gate's stated invariant.
MILL_REVIEW_END
