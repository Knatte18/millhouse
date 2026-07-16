# Batch: completeness-recount-cards-done

```yaml
task: Batch verify/baseline/completeness gates produce false positives or time out
batch: completeness-recount-cards-done
number: 1
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Fixes #660: the finalize completeness gate compares raw commit count against declared card count, with no way to represent a batch brief's explicit permission to combine multiple cards into one commit — a legitimately-complete batch gets misclassified `stuck_type: incomplete`, and because `--resume-incomplete`'s re-dispatch makes no new commit, the identical misclassification repeats forever. This batch replaces the count-only heuristic with a self-reported `cards_done` field compared against the batch's actual declared card-ID set (not an assumed 1..N range), with an explicit absent-field fallback to today's count check (so old/non-compliant implementer sessions never regress), int coercion for JSON string card numbers, and an `already_complete` resume backstop. `_reclassify_verify_failure` — a second, independent function with the same buggy count check, triggered on a genuine verify failure rather than the explicit-success path — is updated in lockstep so the same bug class doesn't survive on that trigger path. The external interface the rest of the plan (batch 02) depends on: `_forward_output`/`finalize_from_output` in `_implementer_common.py` gain a `card_ids: set[int] | None` parameter (replacing `card_count: int | None`) threaded through their internal gate calls — batch 02 inserts a new gate into the same explicit-success pipeline region and must land after this batch's signature change exists, hence `depends-on: [1]`.

## Cards

### Card 1: Extract card_ids (not just card_count) in millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()`, replace the existing line `card_count = len(re.findall(r"(?m)^###\s+Card\s+\d+\s*:", _batch_text))` with extraction of a `card_ids: set[int]` via `re.findall(r"(?m)^###\s+Card\s+(\d+)\s*:", _batch_text)`, converting each captured string to `int` with a set comprehension. Keep a `card_count = len(card_ids)` local for any remaining local uses of the count. Card numbers are NOT assumed to be a contiguous `1..card_count` range — they are read verbatim from the batch file's headings (a batch's cards may be numbered e.g. `Card 7`/`Card 8` under mill-plan's global-across-batches numbering convention). In both call sites that currently pass `card_count=card_count` to `finalize_from_output` (the `--stage finalize` branch) and to `_forward_output` (the `--stage full` / default branch), add `card_ids=card_ids` as a new keyword argument passed alongside the existing `card_count=card_count` argument (Card 4 in this batch changes the callee signatures to consume `card_ids`; leave `card_count=card_count` in place at these two call sites for now — Card 4 removes it from the callee signature, at which point these two keyword arguments are updated together with that same edit for consistency, but the call-site python `card_ids` variable itself is established here).
- **Commit:** `fix(millpy-implement): extract card_ids set, not just card_count, from batch headings`

### Card 2: Rewrite `_batch_completeness_stuck` for card_ids + cards_done + absent-field fallback + type coercion

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `_batch_completeness_stuck`'s signature from `(project_root, start_sha, card_count, session_id, *, verify_cmd=None, ignore_verify=False)` to `(project_root, start_sha, card_ids, session_id, *, verify_cmd=None, ignore_verify=False, cards_done=None, already_complete=False)`. New behavior, in order:
  1. If `already_complete is True`: return `None` immediately (complete), bypassing every other check below — this is the resume-idempotent-confirmation backstop; it is not scoped to only fire on a resumed dispatch, the caller (Card 4/Card 6) is what decides when to set it.
  2. Existing short-circuit unchanged: if `verify_cmd is not None and not ignore_verify: return None`.
  3. If `start_sha is None or card_ids is None or len(card_ids) <= 0: return None` (gate disabled — mirrors the old `card_count is None or card_count <= 0` disablement, now keyed on `card_ids`).
  4. Compute `content = _content_commit_count(project_root, start_sha)`; if `content is None: return None` (unchanged).
  5. **Absent-vs-present `cards_done` branch:** if `cards_done is None`: fall back to the OLD heuristic exactly — `if content < len(card_ids): return` the stuck dict shaped as today (`stuck_type: incomplete`, reason `f"batch incomplete: {content} content commit(s) since start but {len(card_ids)} card(s) in batch -- implementer stopped before finishing all cards"`, `commits_made: content`), else `return None`. This is the fail-open path for implementer sessions that never populate `cards_done` (old sessions, non-compliant models) — behaves identically to pre-#660-fix.
  6. If `cards_done` is present (including `[]`, a genuine self-report of zero cards done): attempt `coerced = {int(x) for x in cards_done}`. If any entry raises `(ValueError, TypeError)` on `int()`: treat exactly as the absent-field case in step 5 above (same fallback logic, same stuck dict shape) — a malformed list is untrusted, not partially trusted.
  7. With a successfully coerced `coerced: set[int]`: compute `missing = card_ids - coerced`. If `missing`: return the stuck dict with reason `f"batch incomplete: cards {sorted(missing)} not reported done (cards_done={sorted(coerced)}, declared={sorted(card_ids)})"`, `stuck_type: incomplete`, `commits_made: content`. Else: `return None`.
  Extract the shared step-5/step-6-fallback/step-7 logic (absent-or-malformed-cards_done → old count check; present-and-valid → set-difference check) into a private helper, e.g. `_cards_incomplete_reason(card_ids, cards_done, content, card_count_label) -> str | None` returning the `reason` string when incomplete or `None` when complete, so Card 3's `_reclassify_verify_failure` rewrite can call the identical logic rather than duplicating it.
- **Commit:** `fix(_implementer_common): completeness gate compares cards_done against card_ids, not raw commit count`

### Card 3: Update `_reclassify_verify_failure` in lockstep

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `_reclassify_verify_failure` has its own independent `0 < content < card_count → stuck_type: incomplete` check (the middle branch, between the `content == 0` branch and the `content >= card_count` unchanged-passthrough branch). Change its signature from `(verify_stuck, project_root, start_sha, card_count, session_id)` to `(verify_stuck, project_root, start_sha, card_ids, session_id, cards_done=None)`. Replace the middle branch's `0 < content < card_count` condition and its stuck-dict construction with a call to the same `_cards_incomplete_reason` helper Card 2 introduces (passing `card_ids`, `cards_done`, `content`): if it returns a non-`None` reason string, build the `stuck_type: incomplete` dict using that reason (plus `commits_made: content`, `session_id: session_id or "unknown"`); if it returns `None`, fall through to the existing "return `verify_stuck` unchanged" branch (this covers both "content >= len(card_ids)" and "cards_done confirms everything declared is done" as the same "not incomplete" outcome). The `content == 0` branch (return `stuck_type: logic`, "no content commit") is unchanged — orthogonal to `cards_done`.
- **Commit:** `fix(_implementer_common): _reclassify_verify_failure shares the cards_done-aware completeness check`

### Card 4: Thread card_ids/cards_done/already_complete through the four completeness-gate call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_forward_output` and `finalize_from_output` (both in this file): rename each function's `card_count: int | None = None` parameter to `card_ids: set[int] | None = None`. Update all four call sites of `_batch_completeness_stuck` (the explicit-success path, plus the three no-JSON-inference fallback paths) and all four call sites of `_reclassify_verify_failure` (immediately preceding each of the above) to pass `card_ids=card_ids` instead of `card_count=card_count`. On the **explicit-success path only** (where `parsed: dict` from `_extract_status_json` is in scope): extract `cards_done = parsed.get("cards_done")` and `already_complete = bool(parsed.get("already_complete", False))`; pass both through to the `_batch_completeness_stuck`/`_reclassify_verify_failure` calls on that path. On the **three no-JSON-inference fallback paths** (no parsed success JSON exists there — these paths run when no valid `status` JSON was found in the implementer's output): pass `cards_done=None` and `already_complete=False` explicitly (there is nothing to self-report from, so these paths always use the absent-field fallback — this is correct and matches today's behavior for those paths, which never had a self-report mechanism to begin with).
- **Commit:** `fix(_implementer_common): thread card_ids/cards_done/already_complete through completeness gate call sites`

### Card 5: Document `cards_done` and `already_complete` in the implementer brief template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add instructions telling the implementer to include a `cards_done` field (a JSON array of the integer card numbers, exactly as they appear in this batch's `### Card N:` headings, that this commit set actually addresses) in its final `status: success` JSON report. Update any example success-envelope JSON shown in the template to include `"cards_done": [...]`. Separately, document that on a `--resume-incomplete` re-dispatch specifically (the brief already has resume-specific instructions using the `<START_SHA>` token per the existing template), if the implementer independently re-verifies that every card's requirements are already satisfied by the existing commit(s) and it makes no new commit, it should report `status: success` with `"already_complete": true` in the envelope (in addition to, not instead of, a `cards_done` list covering every declared card).
- **Commit:** `docs(implementer-brief): document cards_done and already_complete self-report fields`

### Card 6: Wire `already_complete` from the parsed success envelope

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This card is a narrow follow-on to Card 4: confirm (and if Card 4 did not already do so in the same edit pass, add) that `already_complete` extracted from `parsed.get("already_complete", False)` on the explicit-success path is passed as the `already_complete=` keyword argument to `_batch_completeness_stuck` specifically (per Card 2's step 1: `already_complete is True` short-circuits the gate to pass, bypassing the verify-present short-circuit, the absent/present `cards_done` branches, and the coercion logic entirely). `_reclassify_verify_failure` does NOT take an `already_complete` parameter — it fires on a verify-failure trigger, and `already_complete: true` is a claim about card completeness made on the explicit-`status: success` path only; a verify failure means `status` was not a clean success, so `already_complete` is not meaningful there and must not be threaded into Card 3's signature. (If Card 4's own edit already fully satisfies this, this card's diff may be empty beyond a confirming comment — that is an acceptable outcome; do not force an artificial change.)
- **Commit:** `fix(_implementer_common): already_complete short-circuits the completeness gate on resume`

### Card 7: Unit tests for card_ids/cards_done/already_complete

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-implementer-common.py` (matching this file's existing single-`main()`-with-inline-numbered-`case`-blocks style — continue the existing numbering sequence, do not introduce `def test_*()` functions or a `unittest.TestCase` class in this file), add cases covering `_batch_completeness_stuck` and `_reclassify_verify_failure`: (a) `cards_done` covers all `card_ids` despite `content < len(card_ids)` → no-stuck; (b) `cards_done` present but missing entries from `card_ids` → stuck/incomplete with the missing IDs named in the reason; (c) `cards_done` absent (`None`) with a batch that would pass the old count check → no-stuck (fallback path, passing case); (d) `cards_done` absent with a batch that would fail the old count check → stuck/incomplete (fallback path, failing case); (e) `cards_done` as JSON string card numbers (e.g. `["7", "8"]`) matching integer `card_ids` (e.g. `{7, 8}`) → coerces and passes; (f) `cards_done` with one malformed non-numeric entry (e.g. `["7", "abc"]`) → falls back to the count check, not a crash; (g) a batch with `verify_cmd` set and `ignore_verify=False` → `_batch_completeness_stuck` still returns `None` regardless of `cards_done`/`card_ids` (verify-present short-circuit preserved); (h) `already_complete=True` → `_batch_completeness_stuck` returns `None` immediately regardless of every other argument; (i) `_reclassify_verify_failure`'s `content == 0` branch is unaffected by any `cards_done` value (still reclassifies to `stuck_type: logic`, "no content commit"); (j) `_reclassify_verify_failure` mirrors cases (a) and (b) above on its own `0 < content < len(card_ids)`-equivalent trigger path. In `test-millpy-implement.py` (matching this file's existing `unittest.TestCase` style), add a test asserting `card_ids` extraction from a batch file whose only headings are `### Card 7:` and `### Card 8:` (non-contiguous, non-1-indexed within the batch, mirroring the #660 repro) yields `{7, 8}`, not `{1, 2}`.
- **Commit:** `test(implementer-common,millpy-implement): cover card_ids/cards_done/already_complete completeness gate`

## Batch Tests

`verify:` (frontmatter above) runs both test files this batch touches: `test-implementer-common.py` (Card 7's cases (a)-(j), covering `_batch_completeness_stuck` and `_reclassify_verify_failure`) and `test-millpy-implement.py` (Card 7's `card_ids` non-contiguous-numbering test). Scoped via `run-all.py --only` rather than the full suite since no other test file exercises this batch's `Edits:`.
