MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #973 dependent-check can't be built on `_status.remove_batch` as scoped
**Section:** Scope `#973` / Decision `973-remove-batch-refuses-on-live-dependents`
**Issue:** The Decision has `remove_batch` refuse when "any remaining batch's `depends-on` still names the batch being removed," but `depends-on:` is parsed only from the Batch Index in `00-overview.md` (`_plan_dag.extract_batch_index`, confirmed via grep across `plugins/mill/scripts`); `_status.py`'s `_BATCH_ALLOWED_KEYS` (status.py:511-520) has no `depends-on` field, and the Scope's own signature `remove_batch(status_path: Path, name: str) -> None` has no way to see plan-file data.
**Fix:** State which component performs the dependent scan (the new `/mill-descope-batch` skill reading `_plan_dag.extract_batch_index` on `00-overview.md` before calling `_status.remove_batch`, or an added `overview_path`/`batch_index` param) — `_status.remove_batch` cannot enforce this alone.

### [BLOCKING:design] #906's "self-resolve card-numbering step" is not established in current text
**Section:** Scope `#906` / Decision `906-reuse-existing-plan-validate-helper`
**Issue:** The fix is framed as "wiring" `_check_card_numbering` into an existing numbering-assignment step at SKILL.md:853-856 and holistic-review.md:185-189, but both self-resolve passages only say "edit the plan file(s) ... if the failure traces to an ambiguous or incorrect card" — no card-insertion or number-assignment mechanic is described anywhere in either file (grepped, zero hits for "card number").
**Fix:** Specify the actual insertion/numbering instruction text being added (not just the validator call), or clarify this is new self-resolve behavior, not a wire-in to something already there.

### [BLOCKING:decision] #973's move-target for the orphaned card file is unnamed
**Section:** Scope `#973`
**Issue:** "moves the orphaned `NN-<batch_name>.md` card file out of `plan_dir` into a non-glob-matching location" names a constraint (don't match `??-*.md`) but never a destination; no existing repo convention for archived/removed batch files was found (grepped `archiv|descope` — only unrelated git-tag-archive hits).
**Fix:** Name the target path (e.g. an `_mill/descoped/` or `plan_dir/.descoped/` directory) so plan writer and `/mill-descope-batch` implementer agree.

### [BLOCKING:consistency] Technical Context misattributes `_plan_dag` line numbers, contradicting Scope's own citation
**Section:** Technical context
**Issue:** "`_plan_dag.extract_batch_index` / `_plan_dag.validate` / `_check_file_refs` — `:68`, `:240`, `:656`" pairs `validate` with line 240 and `_check_file_refs` with 656; actually `_check_file_refs` is defined at 240 (`validate` is defined at 647, and 656 is merely the call to `_check_file_refs` inside `validate`). This contradicts the Scope section's own correct citation "`_check_file_refs`, `_plan_dag.py:240`" for #973.
**Fix:** Correct the Technical Context line mapping to `extract_batch_index:68`, `_check_file_refs:240`, `validate:647`.

## Verdict

REQUEST_CHANGES
#973's dependent-check location and #906's numbering-step grounding are load-bearing gaps for the plan writer.
MILL_REVIEW_END
