# Batch: discussion-review-round-cap-extension

```yaml
task: Fix discussion review round-cap, daemon cold-start, and nits-only no-op in finalize
batch: discussion-review-round-cap-extension
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch closes GitHub issue #578: `mill-start --auto`'s documented non-progress-extension rule (Phase: Discussion Review, Auto mode subsection, the `extension_used` logic) allows one extra discussion-review round past the configured cap, but `millpy-review-discussion.py --stage prepare` independently rejects `round_n > effective_max` and the SKILL never passes the CLI's own pre-existing `--max-rounds` override on that round. This is a pure `SKILL.md` prose/instruction fix — no Python script changes (`--max-rounds` plumbing already exists end-to-end in `millpy-review-discussion.py` and `_review_discussion.py:prepare()`; `--stage finalize` has no round-cap check at all, confirmed by its function signature carrying no `max_rounds` parameter). There is no external interface this batch produces for another batch to consume; it is self-contained within `plugins/mill/skills/mill-start/SKILL.md`.

## Cards

### Card 1: Thread `--max-rounds` into discussion-review dispatch on the extension round only

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/_review_discussion.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the "Auto mode" subsection's "Phase: Discussion Review — `--auto` changes" bullet list (the bullet beginning "At the end of each GAPS_FOUND round (after committing and pushing gap fixes): (1) parse the current round's gap titles ... (2) if `round >= max_review_rounds` — non-progress check: ... set `extension_used = True`, allow one more round (do NOT block), and continue the loop (`round += 1`) ..."), add one sentence immediately after that bullet stating: the next iteration's Step 2 dispatch (the discussion-review prepare call) for this extension round MUST pass `--max-rounds <max_review_rounds + 1>` (Agent-mode: as `<args>`; subprocess/psmux: appended to the inner `millpy-review-discussion.py` invocation) so that `_review_discussion.py:prepare()`'s `round_n > effective_max` check does not reject it; every other round (i.e. when `extension_used` is not freshly set this iteration) omits the flag entirely and relies on the configured cap.
  - In Phase: Discussion Review, step 2's Agent-mode dispatch sentence — currently reading "follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-review-discussion.py` with no additional prepare arguments; thread `--round <round>` from the prepare envelope into the finalize invocation." — change `with no additional prepare arguments` to a conditional: `with <args> = --max-rounds <max_review_rounds + 1>` ONLY when this round is the Auto mode non-progress-extension round (per the rule above); omit `<args>` (no additional prepare arguments) on every other round. Keep the existing `--round <round>` threading into finalize unchanged (finalize has no round-cap check and never needs `--max-rounds`).
  - In step 2's "Subprocess/psmux branch — Background the CLI via `millpy-bg`" bash block (the one backgrounding `--slug review-discussion-r<N> -- "$MILL_PYTHON" ".../millpy-review-discussion.py"` with no trailing flags), add the same conditional: append ` --max-rounds <max_review_rounds + 1>` to the inner `millpy-review-discussion.py` invocation ONLY on the extension round, with a one-line note directly above the code block stating the condition (mirroring the wording used for step 3.5 below, for consistency).
  - In step 3.5 ("ERROR-only-aggregate retry (no round consumed)"), apply the identical pair of changes to its own Agent-mode dispatch sentence and its own subprocess/psmux bash block (both currently word-for-word duplicates of step 2's, per the same `with no additional prepare arguments` phrase and the same plain `millpy-review-discussion.py` invocation with no flags) — this re-dispatch must also carry `--max-rounds <max_review_rounds + 1>` if it fires during the extension round, since it is the same prepare call being retried.
  - Do not change `millpy-review-discussion.py`, `_review_discussion.py`, or any other script — the `--max-rounds` CLI/backend plumbing is already correct and unmodified by this batch (read-only Context above is for verifying the existing flag's behavior while writing the SKILL.md prose, not for editing).
- **Commit:** `fix(mill-start): thread --max-rounds into discussion-review dispatch on auto-mode extension round`

## Batch Tests

`verify: null` — this batch only edits skill prose (`plugins/mill/skills/mill-start/SKILL.md`), which has no automated test harness; `--max-rounds`'s underlying CLI/backend behavior is already covered by `plugins/mill/unit_tests/test-review-discussion-flow.py` (verified during discussion to exercise `prepare(..., max_rounds=...)` end-to-end) and is unmodified by this batch. Manual/integration verification: a future `/mill-start --auto` run that converges with disjoint gap titles at the round cap should reach round `max_review_rounds + 1` without operator intervention or a `BLOCKED` halt.
