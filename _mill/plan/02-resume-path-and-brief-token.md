# Batch: resume-path-and-brief-token

```yaml
task: "Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode"
batch: "resume-path-and-brief-token"
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py
depends-on: [1]
```

## Batch Scope

This batch adds the start_sha-preserving resume path to `millpy-implement.py` and the `<START_SHA>` render token plus resume/partial-progress instructions to the implementer brief, with a unit test. It depends on batch 1 because the resume path's value is realized only against the `incomplete` classification finalize now emits. The external interface batch 4 (mill-go routing) consumes is: a resume invocation of `millpy-implement.py` that reuses the original `start_sha` (no HEAD re-capture, no second housekeeping commit) and a brief that tells the implementer to skip already-committed cards.

Batch-local decision: the resume mode is exposed as a new `--resume-incomplete` boolean flag on `millpy-implement.py` (chosen over a new `--stage` value to keep the existing three-stage model intact). When set with `--stage prepare`/`full`, the prepare logic reads the existing `start_sha` from status.md instead of capturing HEAD and does not overwrite `start_sha`/`implementer_session`.

## Cards

### Card 6: Add `<START_SHA>` token and resume instructions to the implementer brief

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** (a) Document a new `<START_SHA>` token in the template's leading HTML comment token list (alongside `<PARENT_BRANCH>`): "the batch's original start_sha on a resume-after-incomplete dispatch; empty string on a normal first-pass dispatch." (b) Add a best-effort partial-progress instruction in the Report / Implementation-discipline area: when forced to stop before the batch is complete, emit `{"status":"incomplete","cards_done":N,"cards_remaining":M,"session_id":"<SESSION_ID>"}` as the final line (finalize detection remains authoritative). (c) Add a "resume-after-incomplete" instruction: when re-dispatched on a batch that already has commits since the batch start, first run `git -C <PROJECT_ROOT> log <START_SHA>..HEAD --oneline` (when `<START_SHA>` is non-empty; otherwise derive the range start from the most-recent `"mill-go: start batch"` commit via `git -C <PROJECT_ROOT> log --grep="^mill-go: start batch" -n 1 --format=%H`), identify cards already committed by their `Commit:` message, and implement only the remaining cards — do not re-edit or re-commit completed cards. Keep all existing brief sections intact. Use `<START_SHA>` and `<PROJECT_ROOT>` token spellings exactly.
- **Commit:** `feat(brief): add START_SHA token and resume-after-incomplete instructions`

### Card 7: Add start_sha-preserving resume path to `millpy-implement.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** (a) Add a `--resume-incomplete` boolean flag (`action="store_true"`, default False) to the argparse setup. (b) In the prepare/full setup (the path beginning at the `git rev-parse HEAD` capture, ~line 282-301): when `--resume-incomplete` is set, do NOT run the HEAD capture into `start_sha`; instead read the existing `start_sha` from the batch's status.md entry (`_status.read_batches` -> matching batch -> `start_sha`) and do NOT call `_status.set_batch_fields` to overwrite `start_sha`/`implementer_session`, and do NOT make a `"mill-go: start batch"` housekeeping commit (skip the staging+commit block that produces it). Also do NOT call `_cleanliness.capture_snapshot` (~line 293) on resume — that would overwrite the original batch-start baseline snapshot with post-partial-work state and, with the commit block skipped, leave it uncommitted, corrupting finalize's new-dirt baseline. Reuse the existing snapshot file written by the original dispatch (the `snapshot_path` is derived from the batch name, so it already points at the original file). (c) When rendering the implementer brief (the `_render.render` call at ~line 351-364), always include a `"START_SHA"` key in the token dict: the resolved original `start_sha` when `--resume-incomplete`, otherwise the empty string `""`. This is mandatory because `_render.render` raises `KeyError` on any unresolved `<TOKEN>` (the brief now contains `<START_SHA>`). Also: on `--resume-incomplete`, the `session_id` used for the brief's `SESSION_ID` token (and the prepare envelope's `session_id`) MUST be the retained `implementer_session` read from status.md, NOT a freshly generated `uuid` (the `session_id = str(uuid.uuid4())` at ~line 295). Finalize reports `implementer_session` from status.md, so a fresh uuid in the brief would diverge from the reported session id. On the normal (non-resume) path, keep generating a fresh uuid as today. (d) Leave the finalize stage unchanged — it already reads `start_sha` from status.md (line 258), so preserving it there yields a correct completeness recount. Do not change normal (non-resume) dispatch behavior.
- **Commit:** `feat(implement): add start_sha-preserving resume-incomplete path`

### Card 8: Test the resume-incomplete path preserves `start_sha`

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add unit cases following the file's existing fixture/mocking style: (1) with `--resume-incomplete` set, the prepare stage reads `start_sha` from status.md and does NOT call `_status.set_batch_fields` to overwrite it (assert the original `start_sha` is preserved and no new housekeeping commit is staged); (2) the rendered brief token dict includes `START_SHA` equal to the preserved sha on resume and `""` on a normal dispatch (guard the `_render.render` KeyError contract), and `SESSION_ID` equals the retained `implementer_session` from status.md on resume (not a fresh uuid); (3) an end-to-end-style finalize after a resume that counts content commits from the original `start_sha` for a now-complete batch (content commits == card_count) emits `success`, not `incomplete` (the false-re-incomplete-loop regression). Mock git/subprocess and status.md as the existing tests do; do not invoke real git or claude.
- **Commit:** `test(implement): cover start_sha-preserving resume path`

## Batch Tests

`verify:` runs `test-millpy-implement.py`, covering the new `--resume-incomplete` prepare branch and the START_SHA token wiring in `millpy-implement.py`. The brief template change (card 6) is prose with no runnable surface; its contract (the `<START_SHA>` token must be supplied at every render site) is exercised indirectly by card 8's token-dict assertion, which guards the `_render.render` KeyError. Scope is the single implement test file matching the single edited script.
