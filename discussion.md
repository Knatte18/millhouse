# Discussion: 8 (A) — Disable per-batch reviews (config-driven)

```yaml
task: 8 (A) — Disable per-batch reviews (config-driven)
slug: disable-per-batch-reviews
status: discussing
parent: main
```

## Problem

Per-batch reviews fire by default for every batch during both plan review and code review. Some repos — especially ones with fast-moving, low-risk changes — want to run only a single holistic review rather than one review per batch. There is currently no config-driven way to do this: setting `review.plan.batch: null` crashes with `ReviewError: Unknown reviewer 'None'`, and there is no flag at all for code review. This task adds a proper off-switch for both.

## Scope

**In:**
- `_review_plan.py`: null-guard on `review.plan.batch`. When null, set `holistic_only=True` inside `run()`. If both `batch` and `holistic` are null, raise `ReviewError` at startup (fail-fast to prevent silent review bypass).
- mill-go `SKILL.md`: add `review.code.per_batch` to the Entry step 3 config reads. In the Execute loop's "Code Review loop" section, add a gate: when `per_batch` is false, skip the entire review loop, set batch state directly to `approved`, and continue to the next batch.
- `wiki/config.yaml`: add inline doc comment on `review.plan.batch` explaining null semantics; add `review.code.per_batch: true` key with a doc comment explaining false semantics.
- `plugins/mill/templates/wiki-config.yaml`: mirror the same additions.
- `plugins/mill/unit_tests/test-review-plan-flow.py`: add one test case covering `batch: null` → holistic-only fires and per-batch is skipped.

**Out:**
- `millpy-review-plan.py` CLI: the `--holistic-only` / `--no-holistic` flags remain unchanged; null-batch logic lives in `run()`, not the CLI.
- `_review_code.py`: no changes — per_batch gating is entirely in the mill-go SKILL.md (the orchestrator decides whether to call the CLI at all).
- `millpy-review-code.py`: no changes.
- Discussion review (`_review_discussion.py`): not touched.
- Integration tests: no changes needed (existing tests use non-null batch config and remain valid).
- Any change to how `review.code.holistic` works — it remains independent of `per_batch`.

## Decisions

### Plan review: null-batch guard placement

- Decision: Add the null check inside `_review_plan.run()` at the start of step 3 (before `load_reviewer`). If `batch_reviewer_name is None`, set `holistic_only = True`. If `holistic_name` is also None, raise `ReviewError("review.plan.batch is null and review.plan.holistic is also null — at least one must be set")`.
- Rationale: Keeps the logic in one place (the backend). The CLI flags (`--holistic-only`, `--no-holistic`) remain unaffected. The fail-fast prevents silent review bypass.
- Rejected: Adding null detection in the CLI (`millpy-review-plan.py`) — would require duplicating the validation for every caller.

### Code review: per_batch boolean, not null reviewer

- Decision: New key `review.code.per_batch: bool` (default `true`). The existing `review.code.reviewer` key is used for both per-batch and holistic code review, so it cannot be nulled out to signal "skip per-batch". A separate boolean is the right lever.
- Rationale: Mirrors how `review.code.holistic: bool` already gates holistic review. Symmetric and easy to read in config.
- Rejected: Mirroring plan review by using `review.code.reviewer: null` — reviewer is shared across both modes so nulling it disables everything, not just per-batch.

### Status.md phases when per_batch=false (code review)

- Decision: After implement succeeds and `per_batch` is false, set batch state → `approved`, call `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`, and commit immediately. Skip all `reviewing-*` and `fixing-*` phases.
- Rationale: Keeps status.md clean — no synthetic "skipped review" noise. The `approved` state is what holistic review and handoff logic gate on; that requirement is met.
- Rejected: Writing a `reviewing-{batch}-r0` → `approved-{batch}` sequence with a synthetic flag — adds noise that would confuse mill-go resume logic.

### No validation error when both code review modes disabled

- Decision: No error when `per_batch: false` AND `review.code.holistic: false`. Zero code review is an intentional power-user choice.
- Rationale: Unlike plan review (where at least one review pass is always expected), code review might legitimately be skipped entirely in a tiny cosmetic task. Plan review has tighter guard because the plan is the primary contract for mill-plan/mill-go; code review is a quality gate.
- Rejected: Symmetric fail-fast with plan review — too prescriptive. The user knows what they're doing.

### Doc comments location

- Decision: Update both `wiki/config.yaml` (live config) and `plugins/mill/templates/wiki-config.yaml` (template for new repos). Add inline comments directly above each key rather than a new section.
- Rationale: Comments inline with the key are visible at the point of use.

## Technical context

### `_review_plan.py`

Path: `plugins/mill/scripts/_review_plan.py`

Key lines:
- Line 314: `batch_reviewer_name = cfg["review"]["plan"]["batch"]` — change to guard null before calling `load_reviewer`.
- Line 315: `batch_reviewer = load_reviewer(batch_reviewer_name)` — move inside the `if batch_reviewer_name is not None:` branch.
- Line 317: `holistic_name = cfg["review"]["plan"].get("holistic")` — already handles None gracefully.
- Lines 330-331: `if not holistic_only:` — already gates per-batch section; the null-batch fix sets `holistic_only=True` before this check.

The complete guard goes at the top of step 3 (around line 313), before the `load_reviewer` calls:
```python
batch_reviewer_name = cfg["review"]["plan"]["batch"]
if batch_reviewer_name is None:
    holistic_name = cfg["review"]["plan"].get("holistic")
    if holistic_name is None:
        raise ReviewError(
            "review.plan.batch is null and review.plan.holistic is also null"
            " — at least one must be set"
        )
    holistic_only = True

if not holistic_only:
    batch_reviewer = load_reviewer(batch_reviewer_name)
else:
    batch_reviewer = None  # unused; holistic_only branch will skip it
```

`load_reviewer` raises `ReviewError: Unknown reviewer 'None'` when passed None, so it must not be called in the null-batch path.

### mill-go SKILL.md

Path: `plugins/mill/skills/mill-go/SKILL.md`

Two edit locations:

1. **Entry step 3 config reads** (currently lists 5 keys ending with `review.code.holistic`). Add:
   - `review.code.per_batch` — if false (missing key defaults to true), skip per-batch code review for all batches.

2. **Execute loop — "### 3. Code Review loop"** (line 79). Insert a gate at the top of that section:
   ```
   Skip this entire section if `review.code.per_batch` is false.
   Instead: set batch state → `approved`, call
   `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`.
   Commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: approve batch {batch_name} (per-batch review disabled)"`.
   Continue to next batch.
   ```

### `wiki/config.yaml` and `plugins/mill/templates/wiki-config.yaml`

Current `review` block (config.yaml lines 148-157, template lines 112-121):
```yaml
  plan:
    rounds: 3
    batch: sonnetmax            # per-batch reviewer; MODE must be "bulk"
    holistic: sonnetmax         # holistic reviewer; MODE must be "bulk"

  code:
    rounds: 3
    reviewer: sonnetmax         # reviewer module suffix; MODE must be "bulk"
    holistic: true              # run one end-of-task holistic code review after all batches approve
    self_fix_rounds: 2
```

Target state (config.yaml):
```yaml
  plan:
    rounds: 3
    batch: sonnetmax            # per-batch reviewer; MODE must be "bulk". null = skip per-batch (holistic must be set)
    holistic: sonnetmax         # holistic reviewer; MODE must be "bulk"

  code:
    rounds: 3
    reviewer: sonnetmax         # reviewer module suffix; MODE must be "bulk"
    holistic: true              # run one end-of-task holistic code review after all batches approve
    per_batch: true             # false = skip per-batch code review; holistic gate is independent
    self_fix_rounds: 2
```

(Template gets the same additions but with `sonnetmax_tool` for discussion as-is.)

### `test-review-plan-flow.py`

Path: `plugins/mill/unit_tests/test-review-plan-flow.py`

Existing tests use `batch: sonnetmax` (non-null). New test appended at the end:
- Config: `review.plan.batch: null`, `review.plan.holistic: sonnetmax` (mocked).
- Fixture: one batch file (`01-core.md`) + overview.
- Assertion: `_review_one_batch` is never called; holistic reviewer IS called once; `ReviewResult.verdict == "APPROVE"`.
- Also test: `batch: null, holistic: null` → `ReviewError` raised.

The test mocks `load_reviewer` and `_review_one_batch` to avoid real LLM calls (existing pattern in the file).

## Constraints

No `CONSTRAINTS.md` found at the hub root.

- Back-compat required: existing configs with `batch: sonnetmax` and no `per_batch` key must continue to behave identically.
- Junctions and hardlinks are never used by scripts. `_paths.py` for all path resolution.
- Scripts invoked via `uv run --project "${CLAUDE_PLUGIN_ROOT}"`, never from the source tree path directly.

## Testing

### `_review_plan.py` (unit)

File: `plugins/mill/unit_tests/test-review-plan-flow.py`

Add two cases:
1. `batch: null, holistic: sonnetmax` → holistic fires, per-batch skipped. Verify `_review_one_batch` call count == 0 and holistic reviewer invoked.
2. `batch: null, holistic: null` → `ReviewError` raised before any review attempt.

Use in-memory config dict (existing pattern). Mock `load_reviewer` to return a dummy reviewer that returns `("APPROVE", "session-1")`.

### mill-go SKILL.md (no unit tests)

SKILL.md is a text instruction consumed by the Claude Code agent. No unit-testable code involved.

### Config keys (no dedicated test)

The config keys are strings/booleans in YAML. `test-config.py` tests config loading — no new cases needed since the key follows the existing pattern.

## Q&A log

- **Q:** When `review.plan.batch: null` and `review.plan.holistic: null`, fail-fast or silent skip? **A:** Fail-fast with `ReviewError` — at least one plan review mode must be set.
- **Q:** When `review.code.per_batch: false` and `review.code.holistic: false`, fail-fast? **A:** No error — zero code review is a valid choice.
- **Q:** When per_batch=false, should status.md still emit review phase markers? **A:** No — set batch directly to `approved`, skip all `reviewing-*` / `fixing-*` phases.
- **Q:** Does nulling `review.plan.batch` affect the `--holistic-only` CLI flag? **A:** No — null-batch sets `holistic_only` inside `run()`, independent of the CLI flag. Both paths converge on the same branch.
