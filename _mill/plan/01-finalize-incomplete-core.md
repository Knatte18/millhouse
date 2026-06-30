# Batch: finalize-incomplete-core

```yaml
task: "Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode"
batch: "finalize-incomplete-core"
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

This batch delivers the `stuck_type: incomplete` classification in the shared finalize logic (`_implementer_common.py`) plus its unit tests. It is the behavioral heart of the #574 fix: detect a partial-batch stop on the no-JSON inference paths even when verify passes, reclassify the two partial-batch detections from `transient` to `incomplete`, attach `commit_sha`/`commits_made`/`session_id` uniformly, harden the housekeeping-commit subtraction, and recognize an implementer-emitted `status: incomplete` JSON. The external interface the later batches consume is the `incomplete` envelope shape and the fact that a partial batch now yields `stuck_type: incomplete` from finalize. No dispatch/orchestration changes here — those are batches 2 and 4.

Batch-local decision: a new module-level constant `_START_BATCH_PREFIX = "mill-go: start batch"` may be introduced to avoid repeating the literal; if added, route all existing literal comparisons through it. Optional — do not over-refactor.

## Cards

### Card 1: Subtract all start-batch housekeeping commits in `_content_commit_count`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_content_commit_count` (`_implementer_common.py` lines ~83-95), change the housekeeping-commit adjustment so it subtracts the count of **all** in-range commit subjects that start with `"mill-go: start batch"`, not only the oldest (`subjects[-1]`). Concretely: replace the single-oldest check with `count = max(0, count - sum(1 for s in subjects if s.startswith("mill-go: start batch")))`. Preserve the existing None-on-subprocess-failure behavior and the existing early returns. Do not change `_is_only_start_batch_commit`.
- **Commit:** `fix(finalize): subtract all start-batch commits in content count`

### Card 2: Reclassify `_reclassify_verify_failure` partial branch to `incomplete`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_reclassify_verify_failure` (`_implementer_common.py` ~lines 100-166), change the `0 < content < card_count` branch to emit `"stuck_type": "incomplete"` instead of `"transient"` (keep the same `reason`, `session_id`, and `commits_made` fields). The `content == 0` branch stays `logic`; the `content >= card_count` path stays unchanged (returns `verify_stuck`). This rename applies to all callers (the change is inside the shared helper). Additionally, in `_forward_output`, update the four post-reclassify membership guards `if gate_result.get("stuck_type") in ("verify", "transient"):` (lines ~888, ~1047, ~1131, ~1215) to `in ("verify", "transient", "incomplete")` so reclassified `incomplete` envelopes still receive `commit_sha`.
- **Commit:** `fix(finalize): reclassify partial-batch verify failure as incomplete`

### Card 3: Emit `incomplete` from `_batch_completeness_stuck` with `commit_sha`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** (a) In `_batch_completeness_stuck` (`_implementer_common.py` ~lines 169-228), change the emitted `"stuck_type"` from `"transient"` to `"incomplete"` (keep `reason`, `session_id`, `commits_made`). (b) Add an optional keyword parameter `ignore_verify: bool = False`; when `True`, skip the `if verify_cmd is not None: return None` short-circuit so the completeness check runs even when a verify command is present (used by the no-JSON inference paths). Default `False` preserves the existing explicit-success-path behavior. (c) At every `_batch_completeness_stuck` call site on the no-JSON inference paths in `_forward_output` (the three calls at ~lines 1052, 1136, 1220, currently passing `verify_cmd=verify_cmd`), pass `ignore_verify=True` and, before `print(json.dumps(...))` of the returned `incomplete` dict, attach `commit_sha` via `git rev-parse HEAD` (reuse the existing `_subprocess_util.run(["git","rev-parse","HEAD"], cwd=project_root)` pattern; attach only on success). The explicit-success-path call at ~line 939 keeps `ignore_verify=False` (unchanged). Completeness-gate `incomplete` envelopes must carry `commit_sha` to match the reclassify-path envelopes.
- **Commit:** `fix(finalize): emit incomplete from completeness gate with commit_sha`

### Card 4: Recognize implementer-emitted `status: incomplete` in `_forward_output`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_forward_output`, in the `if parsed is not None:` block (after `_extract_status_json`), add handling for `parsed.get("status") == "incomplete"`: normalize it to a stuck envelope `{"status": "stuck", "stuck_type": "incomplete", "commits_made": <n>, "session_id": <id>, "commit_sha": <HEAD>}` where `commits_made` is computed via `_content_commit_count(project_root, start_sha)` (fall back to `parsed.get("cards_done")` only if the count is None), `session_id` is `session_id or parsed.get("session_id")`, and `commit_sha` is the current HEAD via `git rev-parse`. Print the normalized envelope and `return 0`. Place this branch so it does not interfere with the existing `status == "success"` gate logic (handle `incomplete` before the generic `parsed`-passthrough that appends `commit_sha`). Do not alter the `status == "success"` path.
- **Commit:** `feat(finalize): normalize implementer status:incomplete report`

### Card 5: Tests for the `incomplete` classification

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update the three existing cases that assert `transient` for the reclassified detections to assert `"incomplete"`: **case 27a** (~line 1256, `_batch_completeness_stuck` completeness gate), **case 50g** (~line 2463, `_batch_completeness_stuck`), and **case 44a** (~line 2223, `_reclassify_verify_failure` inference path). Add new cases: (1) no-JSON inference path with `verify_cmd` set and passing and content-commits < card_count emits `stuck_type: incomplete` carrying `commits_made` and `commit_sha` (the #574 regression — partial batch whose committed cards pass verify); (2) explicit `status: success` JSON with verify passing and content < card_count (combined commits) stays `success` (no false `incomplete`); (3) `_forward_output` given a bare `{"status":"incomplete","cards_done":1,"cards_remaining":2,"session_id":"s"}` line normalizes to the `incomplete` stuck envelope with `commits_made` and `commit_sha` attached; (4) `_content_commit_count` with two `"mill-go: start batch"` subjects and N content commits returns N (subtract-all); (5) reclassified `incomplete` envelopes carry `commit_sha` (membership guard includes `incomplete`). Follow the existing test's mocking style for `_subprocess_util.run` and stdout capture.
- **Commit:** `test(finalize): cover incomplete classification and normalization`

## Batch Tests

`verify:` runs `test-implementer-common.py`, which exercises `_content_commit_count`, `_reclassify_verify_failure`, `_batch_completeness_stuck`, and `_forward_output` — every function this batch changes. The three updated cases (27a, 44a, 50g) and the five new cases cover the reclassification, the verify-ignoring inference-path detection, the `status: incomplete` normalization, the subtract-all hardening, and the `commit_sha` parity. Scope is a single test file matching the single edited source module — no broader suite needed.
