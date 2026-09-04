MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (best-effort self-assessment)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Card 7 never specifies how to derive `target_batch_file` from `batch_name`
**Location:** Batch 2, Card 7 (`SKILL.md` Stuck escalation + `holistic-review.md` equivalent bullet).
**Issue:** `compute_next_card_number`'s `used_numbers` dict (Card 6) is keyed by `batch_path.stem`, which always includes the `NN-` numeric prefix (e.g. `01-mill-go-base-doc-fixes`), confirmed by every batch file in this plan and by `_check_card_numbering`'s own stem-keying. But the `batch_name` variable already in scope at both call sites (`SKILL.md`'s `## Execute — sequential loop`'s `for batch in order` — `order` is a list of batch *names* from `_plan_dag.topo_order`; and the holistic bullet's stuck-JSON `reason` text) is the bare `name:` field (e.g. `mill-go-base-doc-fixes`), never the file stem. Card 7's Requirements say only "`target_batch_file` is this batch's own file stem ... unambiguous" without stating the derivation. A literal reading passes `batch_name` straight through, which never matches any `used_numbers` key, so `compute_next_card_number` always raises `PlanDAGError(f"batch file stem {target_batch_file!r} not found under {plan_dir}")` — the whole self-resolve card-insertion feature this card adds would deterministically fail every time it's exercised, in both occurrences.
**Fix:** Card 7 must spell out the derivation explicitly, e.g. `target_batch_file = Path(next(e["file"] for e in batches if e["name"] == batch_name)).stem`, mirroring the `batch_name_to_path`/`stem_to_path` idiom `_plan_validate.py` already uses in `_check_parallel_modifies_overlap` etc. — and for the holistic occurrence, state how `batches`/`overview_text` gets (re-)loaded there, since that file's Stuck escalation flow has no `batches` binding already in scope.

### [NIT:consistency] `remove_batch_from_index`'s `re.sub` replacement is not backslash-escaped
**Location:** Batch 3, Card 9 (`_plan_dag.remove_batch_from_index`).
**Issue:** The card specifies `_BATCHES_BLOCK_RE.sub(<replacement string built from new_body>, overview_text, count=1)`. `re.sub` interprets backslash sequences (`\1`, `\g<name>`) in a plain string replacement; a `verify:` command or path token containing a literal backslash in `new_body` could corrupt the substitution or raise. `_review_common.py`'s `pattern.sub(replacement_line, ...)` at line 2393 has the same latent issue, so this mirrors existing precedent rather than introducing a new pattern, but it's still worth a defensive fix while the function is new.
**Fix:** Use `_BATCHES_BLOCK_RE.sub(lambda _m: replacement, overview_text, count=1)` (function form sidesteps backslash interpretation) instead of passing the raw string.

## Verdict

REQUEST_CHANGES
Card 7's `target_batch_file` derivation gap would make the new self-resolve card-insertion path always fail.
MILL_REVIEW_END
