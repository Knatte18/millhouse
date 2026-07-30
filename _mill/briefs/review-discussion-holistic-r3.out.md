MILL_REVIEW_BEGIN
# Review: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

Verified all cited source facts against `plugins/mill/scripts/_plan_validate.py` and `plugins/mill/skills/mill-plan/SKILL.md`: `run()` at line 2403, `_extract_requirements_text` at 1384 (header_re/any_field_header_re patterns match exactly as quoted), `_parse_cards` at 120 (boundary-on-`"### "` behavior confirmed as described), `_RE_REFS_HEADER`/`_RE_REFS_SUB` at 79/94, `_card_own_reference_set` at 1408, `_check_context_completeness` at 1462 (confirmed it follows the exact `_parse_cards` → `_extract_requirements_text` iteration pattern the new check is told to mirror), `resolve_existing_paths` import at 71, error-dict contract `{check, batch, card, path, message}` at 2417-2418, fix table at 141-165, Principles `Requirements:` bullet at 278, and test fixture helpers `_make_batch_file`/`_make_batch_file_cards` at 96/169 — every line reference and quoted pattern is byte-accurate. Confirmed no `CONSTRAINTS.md` exists at hub root.

All three Decisions superseded across rounds 1-2 (dedent-to-common-minimum, dedent-to-column-0, non-fence-aware boundary scan) are cleanly resolved in this round's final design (ranged-N search, N-preserving strip, fence-aware re-scan owned by the new check without touching shared helpers), each with rationale and rejected alternatives. The `fence-aware-boundary-detection` Decision explicitly and correctly scopes out fixing `_parse_cards`'s own pre-existing non-fence-awareness, and traced through the interaction: since the check fires only on fences where a uniform indent is still present at scan time, embedded `### `/`- **Field:**`-look-alike lines inside a still-buggy fence are not flush at column 0 and so don't trip `_parse_cards`'s pre-existing boundary bug during detection of the primary case this task targets — this is a subtle but self-consistent design, not a gap.

Testing section enumerates 9 named unit tests covering clean/dirty pairs, near-miss vs. illustrative-snippet discrimination, nonzero-baseline-indentation recovery, multi-fence/multi-file tie-breaks, CRLF normalization, and the nested-heading fence-awareness case, with an explicit escape hatch for the pre-existing `_parse_cards` fixture limitation. No TBDs, unresolved alternatives, or undecided items remain in Decisions or Q&A log.

## Verdict

APPROVE
All cited source references verified accurate; decisions, scope, and tests are complete and internally consistent.
MILL_REVIEW_END
