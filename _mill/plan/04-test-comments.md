# Batch: test-comments

```yaml
task: 'mill-go-base: take the subagent report from the SubagentHandback message'
batch: 'test-comments'
number: 4
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-review-finalize.py
depends-on: [3]
```

## Batch Scope

Keeps two test comments true after batch 3; kept separate because the two test files together are large and would push batch 3 over the context cap.

## Cards

### Card 12: test comment wording

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-finalize.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-review-finalize.py`, the docstring line reading "it is never HTML-escaped the way the implementer's <task-notification> payload is" gets reworded to "the way an implementer report taken from a <task-notification> payload may be".
  In `test-implementer-common.py`, the comment in the Case 63 block reading "The harness HTML-escapes the <task-notification> payload uniformly before delivery, so the raw file on disk may contain entities" gets reworded to say a captured <task-notification> payload may contain entities, so the raw file on disk may contain them.
  Comment/docstring text only; do not touch assertions.
- **Commit:** `test: reword HTML-escape comments for the implementer report source`

## Batch Tests

`verify:` runs both edited test files, which must still pass unchanged.
