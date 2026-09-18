# Batch: mill-go-base-batch-auto-approve-wiring

```yaml
task: "Auto-approve on review-round cap"
batch: "mill-go-base-batch-auto-approve-wiring"
number: 3
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Wires the new `roles.code-review.batch.auto_approve_on_cap` config key (added in batch 1) into `mill-go-base/SKILL.md`'s per-batch `### 3. Code Review loop`, step 5 ("Max-rounds exhaustion"). Unlike mill-plan's step 6 and the holistic loop's step 7 (batch 4), this loop's existing step 5 halt condition is verdict-agnostic — it fires on round-count alone, with no check of the last round's verdict. Per the overview's "per-batch site requires an explicit last-round-verdict guard" Shared Decision, this batch's wiring must gate the new auto-approve-on-cap branch on the most recently completed round's verdict having been `REQUEST_CHANGES` specifically (mirroring the holistic loop's own condition) — a cap reached after a `NEED_CONTEXT` round never auto-approves, since no fixer ever ran against real findings. No batch-local decisions beyond the Shared Decisions ("config key shape", "commit-message suffix", "per-batch site requires an explicit last-round-verdict guard") this batch directly implements. `verify: null` — this batch edits only `mill-go-base/SKILL.md`, a markdown orchestration-instruction file with no runnable surface of its own; correctness is validated by this plan's own Phase: Plan Review (holistic) round(s) and, downstream, by mill-go's Code Review round(s) on this task.

## Cards

### Card 6: Read `auto_approve_on_cap` alongside `min_batch_rounds`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `### 3. Code Review loop`, immediately after the existing line `` - `min_batch_rounds = cfg.get("roles", {}).get("code-review", {}).get("batch", {}).get("min_rounds", 1)`. `` (in the "Convergence gate (min_rounds + demoted predicate)" paragraph that precedes the per-round numbered steps), add a new line: `` - `auto_approve_on_cap = cfg.get("roles", {}).get("code-review", {}).get("batch", {}).get("auto_approve_on_cap", False)`. `` Do not change anything else in that paragraph — the convergence-gate formula and its bullets below it are untouched by this task (see `_mill/discussion.md`'s "This flag never touches the `min_rounds`/demoted-predicate convergence gate" Decision).
- **Commit:** `mill-go-base: read auto_approve_on_cap config key in per-batch Code Review loop`

### Card 7: Wire `auto_approve_on_cap` into step 5's "Max-rounds exhaustion", gated on last-round verdict

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace step `5. **Max-rounds exhaustion.**`'s body — currently: "After `roles.code-review.batch.rounds` rounds without APPROVE: `_notify.notify("<VARIANT_LABEL>.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name} after {N} rounds"`.\n   Go to *Blocked* below." — with:

  "After `roles.code-review.batch.rounds` rounds without APPROVE: branch on the most recently completed round's verdict (round `N = roles.code-review.batch.rounds`, already read at step 3/4 for that round).

  - **If `auto_approve_on_cap` is `True` AND that round's verdict was `REQUEST_CHANGES`:** run the same terminal actions step 4's `APPROVE` branch already runs at its own implicit-approve-at-cap case — set batch state → `approved`, `review_file: <path>` (using the `file` field from that round's `reviews[0]` as `<review_file_path>`, same as step 4's own convention); `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`; commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "<VARIANT_LABEL>: approve batch {batch_name} (auto-approved on round-cap exhaustion, config auto_approve_on_cap)"`. Also emit `_notify.notify("<VARIANT_LABEL>.review-exhausted-auto-approved", f"batch {batch_name}", slug=slug, rounds=N)` so the auto-approval is still observable, not silent. Continue to the next batch — do NOT go to *Blocked*.
  - **Otherwise** (flag is `False`, or that round's verdict was `NEED_CONTEXT`): `_notify.notify("<VARIANT_LABEL>.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on {batch_name} after {N} rounds"`. Go to *Blocked* below."
- **Commit:** `mill-go-base: auto-approve batch code review at round cap when auto_approve_on_cap is set and last verdict was REQUEST_CHANGES`

## Batch Tests

No automated `verify:` — pure SKILL.md instruction edits (see Batch Scope for why). Acceptance is manual/integration per `_mill/discussion.md`'s Testing section: two scenarios — (1) a hub with `roles.code-review.batch.rounds` set low and `auto_approve_on_cap: true`, run against a batch that reliably draws `REQUEST_CHANGES` on its last round, should reach `approved-{batch_name}` and continue to the next batch instead of `blocked`; (2) the same setup but the last round's verdict is `NEED_CONTEXT` (reviewer still waiting on missing files at cap) should still halt `blocked` even with the flag set, confirming the Card 7 guard.
