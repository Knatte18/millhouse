MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (best-effort self-assessment; harness reports claude-sonnet-5)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:consistency] Card 7 wires new helper calls with no inline `signature:` line
**Location:** Batch 2, Card 7 **Issue:** SKILL.md's own Principles section states "Helper signatures are documented inline... Never Read or Grep the helper source — the signature is here, and any failure surfaces as an exception," and every existing helper call site in the file follows it (e.g. lines 672-673's `signature: _parent_branch.resolve(...)` / `signature: _cleanliness.revert_out_of_scope_drift(...)`). Card 7's Requirements instruct calling `_plan_validate.compute_next_card_number(plan_dir, target_batch_file)` and re-running `_check_card_numbering` at two insertion points (SKILL.md Stuck escalation + holistic-review.md's parallel bullet) but never instruct adding the matching `signature:` line, and never specify what `batch_files` argument the `_check_card_numbering` re-check call should receive. **Fix:** Require both insertion points to include `` `signature: _plan_validate.compute_next_card_number(plan_dir: Path, target_batch_file: str) -> int` `` (and name the exact `batch_files` list to pass to the `_check_card_numbering` re-check).

### [BLOCKING:consistency] Card 5's new subsection omits the same `signature:` convention
**Location:** Batch 2, Card 5 **Issue:** The new "Scope violations check" subsection is inserted immediately before the section's existing text (2b), which documents its own two helper calls each with an explicit `signature: ...` line right below the call (SKILL.md lines 672-673). Card 5's Requirements give `_cleanliness.clean_ephemeral_scope_violations`'s signature in prose for the plan author's benefit but never instruct writing that signature into the new SKILL.md subsection itself, breaking local consistency with the text it sits directly beside. **Fix:** Require the new subsection to include `` `signature: _cleanliness.clean_ephemeral_scope_violations(hub_root: Path, git_root: Path) -> tuple[list[str], list[str]]` `` matching the adjacent convention.

### [NIT:consistency] Card 9's serializer None-omission behavior is unspecified
**Location:** Batch 3, Card 9 **Issue:** Card 9 states `_serialise_batch_index` "mirrors `_status.py`'s `_serialise_batches` convention exactly," which omits keys whose value is `None`. The overview's actual on-disk Batch Index format always writes `verify: null` explicitly for every entry (never omitted) — if the omission behavior is carried over literally, every surviving batch's `verify: null` row would silently vanish after any `/mill-descope-batch` run. **Fix:** State explicitly whether `verify:` should always be emitted (even when null) to preserve the existing overview format, or confirm the omission is intentional.

## Verdict

REQUEST_CHANGES
Two new-helper-call insertions (Cards 5, 7) skip this file's mandatory inline `signature:` convention.
MILL_REVIEW_END
