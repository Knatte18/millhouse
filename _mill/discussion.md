# Discussion: Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection

```yaml
task: Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection
slug: mill-implement-finalize-gaps
status: discussing
parent: main
```

## Problem

Five interrelated bugs in `millpy-implement.py --stage finalize` and the implementer brief template cause correctness failures in the mill-go implement/finalize loop:

1. **#557 — Empty-commit accepted as success.** The no-content-commit guard checks `HEAD == start_sha` (pre-start-batch SHA), but the prepare stage makes a "mill-go: start batch" commit before the agent runs. After that commit, `HEAD != start_sha` even when the implementer made zero code commits. A haiku-model implementer edited files in-tree, ran verify (which passed on the live edits), reported `{"status":"success","commit_sha":"<start-batch-sha>"}`, and got through the guard. The cleanliness gate then reverted the uncommitted edits, approving an empty batch.

2. **#548 — Commit-count guard fires false transient.** `_batch_completeness_stuck` rejects batches where `commits_since_start < card_count`. Two failure modes: (a) cards that legitimately share a file produce one combined commit for two cards, failing the count even when verify is green; (b) on a fresh retry the prepare stage resets `start_sha` to current HEAD, so only the retry's commits count against the full card count.

3. **#545, #560 — Mid-batch stop escalates instead of continuing.** When an agent-mode implementer stops mid-batch (clean turn exhaustion, non-error non-JSON final message), `_forward_output` may infer success via the snapshot/HEAD path, then fire the completeness gate, emitting `stuck_type: transient`. The SKILL's one-retry fires a fresh dispatch. If that also stops early, the SKILL escalates — even though the "transient with commits_made > 0 → skip to cleanliness gate" routing exists in Stuck escalation. The path never fires because `_batch_completeness_stuck` does not include `commits_made` in its returned dict.

4. **#549 — Implementer deliberates shared-file cards and stops without JSON.** The brief's strict "One commit per card" rule has no exception for cards that touch the same file. The implementer spends its closing reasoning budget debating whether to create an empty commit for the second shared-file card, then stops before emitting the required JSON report.

## Scope

**In:**
- `plugins/mill/scripts/_implementer_common.py` — fix `_forward_output` empty-commit guard; fix `_batch_completeness_stuck` (add `commits_made`, add `verify_cmd` gate-disable)
- `plugins/mill/unit_tests/test-implementer-common.py` — new test cases for all three code-layer fixes
- `plugins/mill/templates/implementer-brief.md` — add shared-file card guidance, reinforce JSON-last rule
- `plugins/mill/skills/mill-go/SKILL.md` — document clean mid-work-stop path in "## Agent-mode dispatch" step 4

**Out:**
- `millpy-fix.py` / `millpy-review-*.py` — not involved; bugs are specific to implement finalize
- `_status.py`, `_cleanliness.py` — not changed; existing APIs are correct
- `test-millpy-implement.py` — existing tests already cover the prepare/finalize CLI shape; new tests belong in `test-implementer-common.py`
- mill-go holistic review path — not involved
- `mill-plan`, `mill-start`, `mill-spawn` — not in scope

## Decisions

### completeness-gate-disable-when-verify-passes

- Decision: Pass `verify_cmd` into `_batch_completeness_stuck`. When `verify_cmd is not None`, return `None` immediately (gate disabled). When `verify_cmd is None`, run the gate as before.
- Rationale: A green verify is conclusive evidence that the batch is functionally complete — the gate's commits-vs-cards heuristic adds no information on top of a passing verify. The gate is useful only when there is no verify command, as the sole completeness signal.
- Rejected: (a) Remove the gate entirely — loses the last guard for verify-null batches. (b) Lower the threshold (e.g., commits >= cards/2) — arbitrary and still fires false positives for three shared-file cards out of four. (c) Check card-file overlap to count required commits — too complex, fragile.

### commits-made-in-completeness-gate-result

- Decision: Add `"commits_made": count` to the stuck dict returned by `_batch_completeness_stuck`. Count is the raw `git rev-list --count start_sha..HEAD` value (includes the start-batch commit if it was made).
- Rationale: The mill-go SKILL already has a `commits_made > 0` routing path (skip to cleanliness gate → code review) in Stuck escalation. That path is never reached because `commits_made` is absent from the completeness-gate stuck dict. Adding it makes the mid-batch-stop recovery route correctly on the second transient.
- Rejected: (a) Subtract 1 for the start-batch commit — the SKILL's intent is "did the implementer do any work", which is true even if count includes the start commit; code review will catch a partial batch. (b) Add a separate `partial_batch` field — redundant; `commits_made` already carries the signal.

### empty-commit-guard-also-catches-start-commit-only

- Decision: Extend the empty-commit guard in `_forward_output` (parsed-success path) to also fire when exactly one commit exists since `start_sha` and that commit's subject line starts with `"mill-go: start batch"`. Apply the same guard in the inference path before emitting inferred success.
- Rationale: The current `HEAD == start_sha` check only fires when the start-batch commit was skipped (retry path). After a normal prepare, `HEAD` is the start-batch commit, which is one commit past `start_sha`, so the check misses it. Running `git log --pretty=%s {start_sha}..HEAD` and checking for exactly one "mill-go: start batch ..." message is precise: a single-card retry produces a real code-commit message that does not match.
- Interaction with completeness gate: the start-batch-commit-only guard covers two cases the completeness gate alone misses: (a) when `verify_cmd is not None` (completeness gate is disabled with the new fix), the guard is the only backstop for zero code commits; (b) when `card_count == 1` and `verify_cmd is None`, the completeness gate check `count < card_count` evaluates to `1 < 1 = False` and does not fire -- the guard remains necessary. The guard is not redundant even when `verify_cmd is None` and `card_count >= 2` (where the completeness gate would catch it as transient rather than logic); applying the guard consistently emits the more actionable stuck/logic classification instead.
- Rejected: (a) Count <= 1 without message check -- false positive for single-card batches on retry (count=1 = real code commit). (b) Store `batch_start_commit_sha` in status.md -- schema change; broader impact than needed. (c) Apply only to parsed path -- inference path has the same vulnerability.

### brief-shared-file-guidance

- Decision: Replace the strict "One commit per card" bullet in `## Implementation discipline` with: "One commit per card is the norm. For cards that necessarily touch the same file(s), one combined commit covering both cards is acceptable — do NOT create empty commits to satisfy a per-card count. If you choose a combined commit, name it using the later card's `Commit:` message."
- Rationale: The strict rule is the direct cause of #549. The implementer can't satisfy it for shared-file cards without creating an empty commit, which conflicts with `git commit` refusing `--allow-empty` by default. Explicit permission for combined commits resolves the deliberation.
- Rejected: (a) Keep strict rule and add `--allow-empty` guidance — empty commits pollute the history and confuse the commit-count guard. (b) Only add a note about not stopping — the deliberation loop needs the rule resolved, not just the stopping rule tightened.

### skill-md-clean-mid-work-stop-path

- Decision: In mill-go SKILL.md "## Agent-mode dispatch" step 4, add: when the notification is a non-error non-JSON message (clean turn exhaustion, no `API Error` / `Internal server error` in the payload), invoke finalize normally. If finalize returns `stuck_type: transient` with `commits_made > 0`, apply the existing Stuck escalation `commits_made > 0` routing (one retry, then skip-to-cleanliness-gate) rather than treating it as a raw-API-error path.
- Rationale: The current step 4 groups all non-success notifications as API errors / interruptions and re-dispatches fresh. For a clean mid-work stop the implementer has already committed partial work; re-dispatching with a new `start_sha` discards the commit count context and can loop. The `commits_made > 0` path exists precisely for this case.
- Rejected: (a) Always re-dispatch fresh on non-JSON — loses partial work context, can cause infinite two-dispatch loops per #560. (b) Re-prompt the same agent via SendMessage — documented workaround but not automatable in mill-go's current architecture.

## Technical context

### Key files

- `plugins/mill/scripts/_implementer_common.py` — `_forward_output` orchestrates all finalize gates in order: verify → empty-commit → completeness → dirty-tree. `_batch_completeness_stuck` is a standalone helper called from three places in `_forward_output` (parsed-success path and two inference sub-paths). `_run_verify_gates` is the verify helper.
- `plugins/mill/scripts/millpy-implement.py` — `--stage finalize` reads `start_sha` and `session_id` from `_mill/status.md` (written by prepare), then calls `finalize_from_output` → `_forward_output`. The prepare stage captures `start_sha = git rev-parse HEAD` *before* making the "mill-go: start batch" commit, then writes it to `status.md`. After prepare, `HEAD` = start-batch commit ≠ `start_sha`.
- `plugins/mill/unit_tests/test-implementer-common.py` — functional-style test runner (no unittest class); `_setup_fixture` creates a real git repo in a tempdir. Tests call `_forward_output` directly and assert on JSON stdout. Existing test case 27a covers completeness gate; case 27b covers pass-through.
- `plugins/mill/templates/implementer-brief.md` — rendered by `_render.render` at prepare time. Token `<BATCH_FILE>` is substituted with the absolute path. The "One commit per card" rule is in `## Implementation discipline` bullet 1, line 54. The JSON-last rule is in `## Report`.
- `plugins/mill/skills/mill-go/SKILL.md` — "## Agent-mode dispatch" at line 105 (7 steps); step 4 covers error/interrupt recovery. Stuck escalation at ~line 398; `commits_made > 0` routing is at ~line 405.

### Gate order in `_forward_output` (parsed-success path)

1. `_run_verify_gates` — batch then module-wide
2. Empty-commit guard: `HEAD == start_sha` (currently misses start-batch-commit-only case)
3. `_batch_completeness_stuck` — commit-count vs card-count (currently no `commits_made` field, not gated on `verify_cmd`)
4. `_in_scope_dirty_stuck` — uncommitted in-scope tracked files

### `_batch_completeness_stuck` callers in `_forward_output`

Three call sites, all currently passing `(project_root, start_sha, card_count, session_id)`:
1. Parsed-success path (line ~683)
2. Inference path with snapshot (two sub-paths: dirty-after-formatter-drift commit ~line 779; clean tree ~line 831)

All three need the new `verify_cmd` parameter threaded through. `_forward_output` already receives `verify_cmd` as a parameter.

### `start_sha` semantics (important for empty-commit guard)

In `millpy-implement.py` prepare/full stage:
- `start_sha = git rev-parse HEAD` — captured BEFORE making the "mill-go: start batch" commit
- Written to `status.md` immediately
- If `skip_start_commit` is True (last commit is already "mill-go: start batch <batch>"), the start commit is skipped and `start_sha` == the start-batch commit SHA

Consequence for #557: after a normal prepare (no skip), `git rev-list --count start_sha..HEAD` = 1 (only start commit) when the implementer makes no code commits. The current guard `HEAD == start_sha` = False because HEAD is the start-batch commit.

For single-card retry (skip_start_commit=True): `start_sha` = start-batch commit SHA. After implementer makes 1 code commit, `git log --pretty=%s start_sha..HEAD` = one message = that code commit. Does not match "mill-go: start batch" prefix. Guard correctly does NOT fire.

### Inference path vulnerability (#557 extension)

The inference path (`else` branch of `if parsed is not None`) fires when no JSON is found in the output. It checks `HEAD != start_sha` and clean tree to infer success. When only the start-batch commit was made and verify passes (in-tree uncommitted edits), the inference emits a false inferred-success. The same "check commit messages since start_sha" fix must be applied before emitting inferred success in the inference path.

### `commits_made` in `millpy-implement.py` (LLM-error path)

The `LLMError` handler in the full stage already emits `commits_made` via `git rev-list --count start_sha..HEAD`. That count IS from the pre-start SHA, so it includes the start-batch commit. The SKILL's `commits_made > 0` check is therefore designed to accept counts that include the start commit. No change needed there.

## Testing

### New test cases for `test-implementer-common.py`

All tests use real git repos created by `_setup_fixture` in tempfiles.

**Bug #557 — Start-batch-commit-only guard:**
- Case A: Parsed success, start_sha = pre-start SHA, one "mill-go: start batch test-batch" commit made, no code commits → must emit stuck/logic with "no content commit"
- Case B: Parsed success, start_sha = pre-start SHA, two commits (start commit + code commit) → must pass guard and emit success
- Case C: Retry scenario (skip_start_commit): start_sha = start-batch commit SHA, one code commit made → must NOT fire guard, emit success
- Inference path variant of Case A: no JSON in output, start-batch commit only → inference must not emit success; must emit stuck/logic

**Bug #548 — Completeness gate disabled when verify_cmd is set:**
- Case D: card_count=2, one commit since start_sha, verify_cmd="echo ok" → completeness gate must NOT fire; should succeed (existing case 27a behavior changes when verify_cmd != None)
- Case E: card_count=2, one commit since start_sha, verify_cmd=None → completeness gate MUST fire stuck/transient (regression guard)

**Bug #545/#560 — commits_made in completeness gate result:**
- Case F: card_count=3, two commits since start_sha, verify_cmd=None → stuck dict must include `commits_made: 2`
- Case G: card_count=3, zero commits since start_sha, verify_cmd=None → stuck dict must include `commits_made: 0`

### Existing tests to not regress

- Cases 27a and 27b: completeness gate with verify_cmd=None (27a: fewer commits → stuck; 27b: enough commits → success). These must still pass with the new `verify_cmd` parameter defaulting to None.
- Case 27 (#500 regression): parsed success with HEAD==start_sha → stuck/logic. Still fires correctly.
- All inference-path tests (snapshot-based and snapshot-None) must still produce the same results.

### No new tests for brief template or SKILL.md

Template and SKILL.md changes are documentation/text edits with no automated test coverage. Review is the validation mechanism.

## Q&A log

- **Q:** Should the completeness gate be disabled when `verify_cmd` is not None? **A:** [auto-pick] Yes — a green verify is conclusive evidence of completion; the commits-vs-cards heuristic is redundant and error-prone when verify is present. **Why:** Issue #548 explicitly states verify passing was sufficient.
- **Q:** Should `_batch_completeness_stuck` include `commits_made: count` in its returned dict? **A:** [auto-pick] Yes — the mill-go SKILL's `commits_made > 0` routing already handles partial-batch transients; the field is just missing from the completeness-gate result. **Why:** Issues #545 and #560 confirm the routing exists but never fires.
- **Q:** Should the empty-commit guard apply to both parsed-success and inference paths? **A:** [auto-pick] Yes — the inference path is equally vulnerable to false success when only the start-batch commit exists. **Why:** Both paths call verify (or check tree cleanliness), which can pass on uncommitted in-tree edits.
- **Q:** How to detect "only start-batch commit made"? **A:** [auto-pick] `git log --pretty=%s {start_sha}..HEAD` — exactly one message starting with "mill-go: start batch" — to avoid false positives on single-card retries. **Why:** Count ≤ 1 has a false positive for single-card retry (count=1 = real code commit without a start commit).
- **Q:** Where to add shared-file card guidance in the brief? **A:** [auto-pick] Replace "One commit per card" with combined-commit permission + empty-commit ban in Implementation discipline. **Why:** The strict one-commit-per-card rule is the direct trigger for the #549 deliberation loop.
- **Q:** Should the mill-go SKILL.md document the clean mid-work-stop path? **A:** [auto-pick] Yes — step 4 of agent-mode dispatch must distinguish clean turn exhaustion from raw API errors and route to finalize, not immediate fresh re-dispatch. **Why:** Issues #545 and #560 both used the `commits_made > 0` workaround, confirming it is the correct path.
- **Q:** One batch or two? **A:** [auto-pick] Two sequential (A: code + tests; B: docs/template) — Batch B references `commits_made` behavior introduced in A, establishing the dependency. **Why:** Clean separation; Batch A is independently testable.
