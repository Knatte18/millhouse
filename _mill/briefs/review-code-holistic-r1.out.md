MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-09
```

## Findings

No findings. Verified against all three batches:

- Batch 1 (`_implementer_common.py`, `millpy-fix.py`): `emit_prepare` adds `nits_only` after `start_sha`, omits the key entirely when falsy (matches `start_sha`-omission pattern exactly, lines 758-792). `millpy-fix.py`'s prepare branch passes `nits_only=args.nits_only` (line 516); the existing finalize branch already passed it correctly at line 319 and was left untouched, as required. New tests: Case 64 in `test-implementer-common.py` (lines 3179-3222) and the two new methods in `test-millpy-fix.py` (`test_stage_prepare_batch_scope_with_nits_only` / `..._without_nits_only_omits_field`, lines 577-616) both assert the key's presence/absence exactly per the cards' requirements.
- Batch 2 (`SKILL.md`, 5 prose cards): all five verbatim replacements verified byte-for-byte present -- Card 5 (`--nits-only` re-pass wording, line 153), Card 6 (Manual recovery note, line 736), Cards 7/8 (the split dispatch-mandatory sentence at both sites, lines 381 and 683), Card 9 (Edit A step-3 summary at line 125, Edit B step 4(b)/Clean-mid-work-stop span at lines 131-139, Edit C's two Agent-mode-properties bullets at lines 171 and 173).
- Batch 3 (`implementer-brief.md`): Card-count self-check paragraph inserted verbatim at line 100, correctly reuses the START_SHA / `--grep` fallback already documented at line 52.
- Shared Decisions consistently applied: envelope-threading (batch 1->2 contract intact), no new test for #616 config default (confirmed `test_implementer_model_default_is_sonnethigh` already exists), reused START_SHA fallback (batch 3).
- No out-of-plan files, no duplicated helpers, no language-pitfall or constraint violations observed.

## Verdict

APPROVE
All three batches match plan cards verbatim; envelope contract, SKILL.md prose, and brief template are consistent and well-tested.
MILL_REVIEW_END
