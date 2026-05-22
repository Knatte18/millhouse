# Plan: Replace psmux marker protocol with idle-prompt detection

```yaml
task: Replace psmux marker protocol with idle-prompt detection
slug: psmux-idle-prompt-detection
approved: true
started: 20260522-064837
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: Core implementation
    file: 01-core-implementation.md
    depends-on: []
    verify: null
  - number: 2
    name: Tests
    file: 02-tests.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-psmux-capture.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-sub.py"
```

## Shared Decisions

### Decision: Unicode literals vs ASCII output

- **Decision:** `❯` and `● ` are hardcoded string literals in implementation constants (`idle_prompt`, `bullet_prefix`) and are not parameterised. All `print()` and `_log()` calls in `millpy-claude-sub.py` and `_psmux_capture.py` must remain ASCII-only on stdout/stderr.
- **Rationale:** The ASCII-only constraint applies to stdout/stderr (Windows cp1252 crashes on non-ASCII output). String literals in source code are UTF-8.
- **Applies to:** all batches

### Decision: MarkerNotFoundError propagation in Step 11

- **Decision:** The call to `_psmux_capture.extract_response(snapshot_b)` in the new Step 11 is not wrapped in a try/except. If `MarkerNotFoundError` is raised it propagates to the outer `except Exception as exc:` handler, which logs it to stderr and returns 1.
- **Rationale:** The outer handler already covers all exceptions from inside the try block and handles session cleanup based on `session_owned_by_us`. A separate catch would duplicate that logic.
- **Applies to:** Batch 1 (Card 2), Batch 2 (Card 5 S11)

### Decision: _wait_for_marker_in_pane stays

- **Decision:** `_wait_for_marker_in_pane` is not deleted from `millpy-claude-sub.py`. Only the Step 11 marker-polling loop is replaced. The function is still used in Step 7 (CLAUDE_READY check).
- **Rationale:** The discussion scopes the change to "Step 11" and explicitly says "Steps 5–9: unchanged". Step 7 calls `_wait_for_marker_in_pane` for CLAUDE_READY.
- **Applies to:** Batch 1 (Card 2), Batch 2 (Card 5)

## All Files Touched

- `plugins/mill/scripts/_psmux_capture.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/unit_tests/fixtures/psmux-capture/clean.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/markers-reversed.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/multiline.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/no-end-marker.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/polling-not-ready.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/quoted-marker-text.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/whitespace-compressed.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/with-scrollback.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/with-status.txt`
- `plugins/mill/unit_tests/test-claude-sub.py`
- `plugins/mill/unit_tests/test-psmux-capture.py`
