# Batch: mill-go-base-holistic-auto-approve-wiring

```yaml
task: "Auto-approve on review-round cap"
batch: "mill-go-base-holistic-auto-approve-wiring"
number: 4
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Wires the new `roles.code-review.holistic.auto_approve_on_cap` config key (added in batch 1) into `mill-go-base/holistic-review.md`'s step 7 ("Rounds exhausted"). Unlike the per-batch loop (batch 3), this loop's step 7 is already conditioned on `REQUEST_CHANGES still returned` — so no extra last-round-verdict guard is needed here; the wiring only adds the config-flag branch. No batch-local decisions beyond the Shared Decisions ("config key shape", "commit-message suffix") this batch directly implements. `verify: null` — this batch edits only `holistic-review.md`, a markdown orchestration-instruction file with no runnable surface of its own; correctness is validated by this plan's own Phase: Plan Review (holistic) round(s) and, downstream, by mill-go's Code Review round(s) on this task.

## Cards

### Card 8: Read `auto_approve_on_cap` alongside `min_holistic_rounds`

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Near the top of the file, immediately after the existing line `` `min_holistic_rounds = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("min_rounds", 1)`. `` (which itself follows `` `max_holistic_rounds = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("rounds", 1)`. ``, both preceding the "Loop variable `H` starts at 1." sentence), add a new line: `` `auto_approve_on_cap = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("auto_approve_on_cap", False)`. `` Do not change the "Convergence gate (min_rounds + demoted predicate)" section that follows — untouched by this task (see `_mill/discussion.md`'s "This flag never touches the `min_rounds`/demoted-predicate convergence gate" Decision).
- **Commit:** `mill-go-base: read auto_approve_on_cap config key in holistic Code Review loop`

### Card 9: Wire `auto_approve_on_cap` into step 7's "Rounds exhausted"

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace step `7. **Rounds exhausted** (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned):`'s body — currently: "`_status.set_blocked(status_path, f"holistic review exhausted {max_holistic_rounds} round(s)", timestamp=_timestamp.now_utc_iso())`;\n   commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review"` and push;\n   halt with "Holistic review exhausted {max_holistic_rounds} round(s).\n   Task left as [active] for manual review."" — with:

  "**If `auto_approve_on_cap` is `True`:** run the same terminal actions step 4's `APPROVE` branch already runs at its own implicit-approve-at-cap case — `_status.append_phase(status_path, "holistic-approved", _timestamp.now_utc_iso())`; commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "<VARIANT_LABEL>: holistic approve {slug} (auto-approved on round-cap exhaustion, config auto_approve_on_cap)"` — where `<review_file_path>` is the `file` field from the most recently completed round's `reviews[0]` (round `H = max_holistic_rounds`), same convention as step 4's own commit. Proceed to Handoff (`plugins/mill/skills/mill-go-base/handoff.md`) — do NOT halt.

  **Otherwise** (flag is `False`, unchanged today's behavior): `_status.set_blocked(status_path, f"holistic review exhausted {max_holistic_rounds} round(s)", timestamp=_timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on holistic review"` and push; halt with "Holistic review exhausted {max_holistic_rounds} round(s). Task left as [active] for manual review.""
- **Commit:** `mill-go-base: auto-approve holistic code review at round cap when auto_approve_on_cap is set`

## Batch Tests

No automated `verify:` — pure markdown instruction edits (see Batch Scope for why). Acceptance is manual/integration per `_mill/discussion.md`'s Testing section: a hub with `roles.code-review.holistic.rounds` set low (e.g. 1) and `auto_approve_on_cap: true`, run against a change that reliably draws a `REQUEST_CHANGES` verdict, should reach Handoff instead of `blocked` after the single round's fix pass — vs. the same setup with the flag absent/false, which should still halt as today.
