# Discussion: _plan_validate and baseline verify gate gaps

```yaml
task: _plan_validate and baseline verify gate gaps
slug: plan-verify-gate-gaps
status: discussing
parent: main
```

## Problem

Three small gaps in the deterministic plan/verify gates, filed as GitHub issues #1142, #1143, #1144.

1. #1142: `_plan_validate._check_card_numbering` checks duplicates and gaps between present numbers, but never that numbering starts at 1.
   A plan whose Card 1 was removed in a fix round passes the mechanical gate, then costs a full LLM review round when the holistic reviewer flags it ("Global step numbering -- unique, sequential, no gaps across batches", `templates/review-plan-holistic.md:87`).
2. #1143: `requirements-quote-indent-drift` errors identify the offending fence only by its ordinal among all fences in the card's Requirements (`fence 7`), with no line number.
   On cards with many fences the author has to count delimiters by hand.
3. #1144: a per-batch `verify:` shaped `sh -c "check_a && check_b && real_test"` short-circuits at `check_a` on the parent-branch baseline run, so the baseline never reaches `real_test`.
   The recorded baseline then says nothing about `real_test`'s pre-existing failure, and the finalize gate treats it as a fresh failure (`stuck_type: verify`).

## Scope

**In:**
- `_plan_validate.py`: starts-at-1 check in `_check_card_numbering`.
- `_plan_validate.py`: `line` field on every `requirements-quote-indent-drift` error dict (all three emit sites).
- `_verify_baseline.py` / `millpy-implement.py`: detect a short-circuited compound verify baseline and record it as "unknown" instead of a misleading signature list.
- Unit tests for each of the above.

**Out:**
- Changing `review-plan-holistic.md` wording (rejected in favour of the mechanical check, see Decisions).
- Splitting compound verify commands into independently executed conjuncts.
- Adding `line` to other `_plan_validate` checks (the issue says "ideally"; only the indent-drift family is in scope).
- The module-wide verify path's algorithm (`compute_baseline`), except where noted below.

## Decisions

### card-numbering-starts-at-1

- Decision: add a check to `_check_card_numbering` that the smallest card number across all batch files is 1; when it isn't, emit a `card-numbering` error for card 1 (the missing number) with a message in the existing style, e.g. `card 1 breaks sequential numbering within batch <stem>` where `<stem>` is the batch file that contains the minimum card number (not merely the first file in the list), and the message names the actual minimum.
  Skip the check when the plan has zero cards.
- Rationale: catches the case deterministically at Step 1.5 before any LLM dispatch, and keeps the reviewer checklist wording accurate as written.
- Rejected: softening the review template wording (option b of the issue) -- leaves a real numbering defect unenforced.

### indent-drift-line-locator

- Decision: every `requirements-quote-indent-drift` error dict gains `"line": <int>`, the 1-based line number in the batch file of the fence's opening ` ``` ` delimiter.
  The existing `fence N` ordinal in the message stays; the message additionally states the line (e.g. `fence 3 (line 142)`).
  Compute line numbers from the batch file text: locate the card's start line, then the Requirements body's offset within it, then each fence's opening line, using the same fence-toggle convention as `_parse_cards` / `_requirements_fence_aware_body` (a line whose `lstrip()` starts with ` ``` ` toggles).
  The three emit sites (strip pass, add pass, new/replacement-code sibling-indent check) all carry it.
- Rationale: mirrors `context-completeness`, whose errors already carry a `line` field (`_plan_validate.py:3197`, `:3236`); the value there is the offending line's stripped text, but the issue explicitly asks for a numeric line number here.
- Rejected: a content excerpt instead of a number -- harder to act on and noisy for multi-line fences.

### baseline-short-circuit-unknown

- Decision: option (b) of #1144.
  In `_verify_baseline._signatures_for_pair` (per-batch path), when the command contains a top-level `&&` and every signature extracted from the runs is a synthetic `NONZERO_EXIT:` line (no real failure-marker line), the baseline cannot be trusted to cover conjuncts after the failing one.
  In that case `compute_batch_baselines` returns a sentinel for that name meaning "unknown", and `_run_per_batch_baseline_standalone` does not write `verify_baseline_failures` for that batch (leaving the key absent/`None`).
  `None` already means "not computed" everywhere downstream (`millpy-implement.py:801`, `:1083`, `millpy-fix.py:455`), which falls back to the strict gate -- the existing fail-safe.
  Concretely the sentinel is `None` as the dict value; the return type becomes `dict[str, list[str] | None]`.
  The pair cache stores the same `None`.
- Rationale: today the short-circuited run yields a single `NONZERO_EXIT: exit 1: (no output)` signature, which will never subset-match the later real failure's signatures, so the waiver silently does the wrong thing.
  "Unknown -> strict" is honest and needs no new downstream branch.
- Rejected: (a) running each `&&` conjunct independently -- shell quoting inside `sh -c "..."` makes reliable splitting fragile, and conjuncts may depend on each other's side effects.
- Shared helper: the test is factored into one helper in `_verify_baseline.py`, `_is_short_circuit_baseline(command: str, signatures: list[str]) -> bool` (True when `&&` is in `command` and `signatures` is non-empty and every entry starts with `NONZERO_EXIT:`).
  `_signatures_for_pair` calls it on its own result.
- Seeded pair-cache disposition: `_run_per_batch_baseline_standalone` seeds `pair_cache[(module_wide_cmd, cwd)]` with the module-wide half's `list[str]` (`millpy-implement.py:432-435`), which would bypass `_signatures_for_pair`.
  Apply the same helper at seeding time: when `_is_short_circuit_baseline(seed_cmd, seed_signatures)` is True, do NOT seed that pair; the batch then computes its own result through `_signatures_for_pair`, which returns `None`.
  The module-wide cached verdict itself (`module_verify_baseline`) is untouched.
- Known trade-off: any compound (`&&`) command whose only recorded signatures are synthetic `NONZERO_EXIT:` lines runs strict.
  That covers a pre-existing non-test failure in the first conjunct (e.g. `go vet && go test`) and equally a last-conjunct failure with non-marker output (e.g. `lint && go build` with a compile error).
  Accepted -- the baseline cannot show which conjuncts were reached, and a shell short-circuit hides any later failure either way.
- "Top-level `&&`" detection: a simple textual test that `&&` appears in the command string (including inside a `sh -c "..."` quoted body); no shell parsing.
  False positives only cost strictness, never correctness.
- The module-wide verify path (`compute_baseline`) is untouched: it has no per-conjunct signature use and its verdict is binary.

## Technical context

- `plugins/mill/scripts/_plan_validate.py`: `_check_card_numbering` (~line 943), `_parse_cards` (~161), `_requirements_fence_aware_body` (~3333), `_RE_FENCE_BODY` (134), the indent-drift check (~3440-3580).
  Note `_RE_FENCE_BODY.findall` on the Requirements text yields fence bodies without positions; the plan must derive line numbers separately (e.g. `finditer` on the body plus offset mapping back to the batch file).
  Errors are dicts with keys `check, batch, card, path, message`; `line` is an added optional key.
- `plugins/mill/scripts/_verify_baseline.py`: `compute_batch_baselines`, `_signatures_for_pair`; `_implementer_common._extract_failure_signatures` synthesizes `NONZERO_EXIT: exit <rc>: <first output line>` when returncode is non-zero and no marker line matched.
- `plugins/mill/scripts/millpy-implement.py:336-470`: `_run_per_batch_baseline_standalone` writes `verify_baseline_failures` via `_status.set_batch_field`; idempotence is by key presence, so an unwritten key is retried on the next baseline invocation (acceptable).
  `module_wide_pair_seed` seeds `pair_cache` with a `list[str]`; the `None` sentinel must not break that.
- `millpy-fix.py:470-476` unions per-batch `verify_baseline_failures` for the holistic gate and skips falsy values, so a `None` batch contributes nothing to the union while other batches' signatures still count.
  Accepted as-is: an unknown batch cannot waive anything, which is the strict direction.
- `millpy-merge-in-subagent.py:244` already sets the field to `None` on recompute, confirming `None` is a valid "unknown" value downstream.
- Tests: `unit_tests/test-plan-validate-card-numbering.py`, `test-plan-validate.py`, `test-verify-baseline.py`, `test-millpy-implement.py`.
  Run via `uv run --project plugins/mill`; plan `verify:` commands must start with `PYTHONPATH=`.

## Constraints

- No `sed`; ASCII-only `print()`/`_log()` output.
- Plan `verify:` commands for Python must begin with `PYTHONPATH=` (literal empty value).
- Working state stays in `_mill/`; nothing here cites `_mill/discussion.md` from permanent docs.

## Testing

- TDD candidates: all three.
- Card numbering: plan starting at 2 -> error; starting at 1 -> none; multi-batch plan where batch 2 starts at 1 again is already a cross-batch duplicate (unchanged); empty plan -> no error.
- Indent drift: for strip-pass, add-pass and sibling-indent errors, assert `line` equals the actual file line of the fence's opening delimiter, including a card with several fences and a card not at the top of the file.
- Baseline: compound `a && b` where `a` fails with no output -> baseline `None` (key not written by the standalone driver); non-compound failing command -> unchanged NONZERO_EXIT signature; compound command where a real marker line is present -> unchanged; green compound -> `[]`.
  Seeded pair: a batch whose compound verify command equals the module-wide command, seeded with all-synthetic signatures, is NOT seeded and ends up `None`; a non-compound or marker-bearing seed is still seeded as before.
  Holistic union (`millpy-fix.py`): a `None` batch alongside a batch with signatures yields only the latter's signatures.
  Existing `pair_cache` dedup and seeding behaviour must still pass.

## Q&A log

- **Q:** #1142: enforce starts-at-1 mechanically, or reword the review template? **A:** [auto-pick] Enforce mechanically. **Why:** deterministic and free, avoids a wasted LLM round.
- **Q:** #1144: run conjuncts independently, or treat a short-circuited baseline as unknown? **A:** [auto-pick] Treat as unknown (leave baseline unset -> strict gate). **Why:** reuses the existing `None` fail-safe; splitting shell commands is fragile.
- **Q:** Seeded module-wide pair_cache bypasses detection: what to do? **A:** [auto-pick] Apply the same helper at seeding time and skip seeding a short-circuit pair. **Why:** one detector, no bypass, module-wide verdict untouched.
- **Q:** Add `line` to other `_plan_validate` checks too? **A:** [auto-pick] Only the indent-drift family. **Why:** keeps scope to what #1143 actually reports.
