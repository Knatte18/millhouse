# Batch: implementer-contracts

```yaml
task: "Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes"
batch: "implementer-contracts"
number: 5
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes issues #500 and #499/#502, grouped because the script changes both land in `_implementer_common.py` (and its test) — they must not be parallelised. #500: the implementer finalize accepts a self-reported `status:success` even when no content commit was made (`HEAD == start_sha`). #499/#502: when an Agent dispatch returns a raw API error before any verdict, the captured-error path mislabels it `stuck_type:logic` (→ "ask user") instead of the retriable `stuck_type:transient`, and the SKILLs document no recovery step. Card 5 fixes both script contracts + the implementer brief; cards 6–7 add the SKILL-prose recovery contract (mill-go canonical, mill-start/mill-plan references). Card 5 carries the only runnable verify; cards 6–7 are doc changes validated by review.

## Cards

### Card 5: Reject no-commit success and classify captured API errors as transient

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - **#500 — reject self-reported success with no content commit.** In `_implementer_common.py`, in `_forward_output`, inside the `if parsed.get("status") == "success":` block (the parsed-report branch, after the verify-gate early-return and BEFORE the code that runs `git rev-parse HEAD` and assigns `parsed["commit_sha"]`): when `start_sha is not None`, run `git rev-parse HEAD` (via `_subprocess_util.run` with `cwd=project_root`); if it returns 0 and `stdout.strip() == start_sha`, the implementer reported success without making any content commit — print `{"status": "stuck", "stuck_type": "logic", "reason": "success reported but no content commit (HEAD == start_sha)", "session_id": session_id or parsed.get("session_id")}` and `return 0` instead of accepting the success. The existing inference-fallback path (the `parsed is None` branch) already guards on `start_sha`; this adds the same guard to the self-reported-success path, which previously never compared against `start_sha`.
  - **#499/#502 — classify captured API errors as transient.** In `_implementer_common.py`, in `_forward_output`'s final no-JSON fallback (the block that currently builds `result = {"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}` when `_extract_status_json` returned `None`): before emitting that logic sentinel, test the captured `output` for API/infrastructure-error markers using a **case-insensitive substring** match. If any marker is present, print `{"status": "stuck", "stuck_type": "transient", "reason": "agent returned a raw API error before producing a structured report"}` and `return 0`. Marker set (case-insensitive substrings): `api error`, `internal server error`, `bad gateway`, `service unavailable`, `gateway timeout`, `overloaded`, `500 internal`. Plain prose-without-JSON that contains none of these markers (e.g. the existing "garbage" fixture) must keep falling through to the `stuck_type: logic` "no structured report" sentinel. Apply this ONLY on the no-JSON-parsed branch — never against a successfully-parsed report's fields.
  - **#500 — brief contract note.** In `implementer-brief.md`, in the success/stuck JSON-report shape section, add a one-line contract note: `commit_sha` MUST be a real content commit distinct from the batch start commit; an implementer that made edits but did not run the per-card `git-commit` must report `status: stuck`, not `status: success`.
  - **Tests** in `test-implementer-common.py`:
    - #500 regression: a parsed `status:success` report passed to `_forward_output` with `start_sha` set equal to the current `HEAD` (no new commit) → assert the emitted JSON is `stuck` with `stuck_type: logic` and a reason naming the no-content-commit condition. Mirror the existing parsed-success cases (the ones around the verify-gate demotion tests) for fixture setup, but with `HEAD == start_sha`.
    - #499/#502 regression (both directions): (a) `_forward_output` called with output `"API Error: Internal server error"` and no parseable JSON → assert `stuck` with `stuck_type: transient`; (b) confirm the existing plain-garbage + `HEAD == start_sha` case still yields `stuck` with `stuck_type: logic` (it must NOT be reclassified as transient).
- **Commit:** `fix(implementer): reject no-commit success and retry captured API errors`

### Card 6: Document agent-error recovery in mill-go Agent-mode dispatch

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `mill-go/SKILL.md`, in the `## Agent-mode dispatch` section (a numbered list where "Call Agent tool" is step 3 and "Capture output" is step 4 — locate by step name, not line number), insert an explicit recovery step between the "Call Agent tool" step and the "Capture output" step. Match the section's existing numbering style when inserting (renumber following steps, or use a sub-step like "3.5" if that matches nearby conventions in the file — read the section first and follow whatever pattern is already used).
  - Content of the new step: if the Agent tool returns a raw API/infrastructure error instead of a final message — text containing markers like `API Error` / `Internal server error`, roughly 0 tokens / 0 tool uses, no `MILL_REVIEW` block and no `status` JSON — do NOT write it to `<brief>.out.md` and do NOT run `--stage finalize`. Classify it as `stuck_type: transient` and apply the existing one-retry transient policy: re-dispatch the same brief once (no `--resume`). On a second consecutive raw error: implementer and fixer dispatches escalate per the "Stuck escalation" section; read-only reviewer dispatches (which write no review file, so there is no artifact to finalize) fall back to the subprocess path — run the matching `millpy-review-<type>.py --stage full` via `millpy-bg` — before escalating. State explicitly that this recovery applies to implementer, reviewer, and fixer Agent dispatches.
  - Update the existing "Agent-mode properties" bullet that asserts "The one-retry transient policy still applies" to cross-reference the new recovery step (so a reader sees where the raw-API-error case is handled). Leave all other steps and properties unchanged.
- **Commit:** `docs(mill-go): define agent-mode raw-API-error transient recovery`

### Card 7: Reference agent-error recovery in mill-start and mill-plan

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In both `mill-start/SKILL.md` and `mill-plan/SKILL.md`, near each skill's existing reference to the mill-go `## Agent-mode dispatch` pattern (the "If `agent` ... follow the Agent-mode dispatch pattern" lines), add a short clarifying note: the same agent-error recovery applies — a raw Agent API error before any verdict is classified `stuck_type: transient` and the brief is re-dispatched once; on a second consecutive error, a read-only reviewer dispatch falls back to the subprocess `--stage full` path (via `millpy-bg`) before surfacing to the operator, rather than auto-refiring.
  - State that this holds even though mill-start and mill-plan have no autonomous stuck machinery and are otherwise interactive: the one-retry plus reviewer subprocess fallback is the defined recovery, after which the skill surfaces to the operator. Do NOT remove or contradict the existing statements (mill-start's "no stuck_type / autonomous machinery" and the dead-worker halt-with-no-auto-refire); the new note is additive and specific to the raw-API-error-before-verdict case.
- **Commit:** `docs(mill-start,mill-plan): reference agent-mode API-error recovery`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-implementer-common.py` (standalone `__main__` runner), covering the #500 no-commit-success rejection and the #499/#502 API-error→transient classification with both-direction assertions. Cards 6 and 7 are SKILL-prose changes with no runnable surface — their correctness is established by plan/code review of the inserted text, and they are intentionally grouped with card 5 because the #499/#502 fix spans both the script (card 5) and the SKILL docs (cards 6–7). Scoped to the single test file because the only Python edits in this batch are in `_implementer_common.py`.
