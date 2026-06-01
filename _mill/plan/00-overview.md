# Plan: Smoke-test the psmux implementer end-to-end

```yaml
task: Smoke-test the psmux implementer end-to-end
slug: smoke-test-psmux
approved: false
started: 20260601-083257
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Fix production code
    file: 01-fix-production-code.md
    depends-on: []
    verify: PYTHONPATH= "$MILL_PYTHON" plugins/mill/unit_tests/run-all.py --only test-claude-sub.py test-psmux-capture.py
  - number: 2
    name: Extend unit tests
    file: 02-extend-unit-tests.md
    depends-on: [1]
    verify: PYTHONPATH= "$MILL_PYTHON" plugins/mill/unit_tests/run-all.py --only test-claude-sub.py test-psmux-capture.py
  - number: 3
    name: Integration gate
    file: 03-integration-gate.md
    depends-on: [2]
    verify: PYTHONPATH= "$MILL_PYTHON" plugins/mill/integration_tests/test-claude-psmux.py
```

## Shared Decisions

### Decision: ASCII-substring idle markers only

- **Decision:** Idle-state detection uses only pure ASCII substrings (`"shortcuts"`, `"esctointerrupt"`). No Unicode string literals as search terms in detection logic.
- **Rationale:** psmux alternate-screen capture on Windows emits inter-word spaces as non-ASCII Unicode chars. `errors="replace"` in `_subprocess_util.run` replaces them with U+FFFD. ASCII word tokens survive intact; any check that includes a space character between two words will fail silently.
- **Applies to:** batches 1, 2

### Decision: bullet detection without trailing space

- **Decision:** `extract_response` matches the response-start bullet using `startswith("●")` alone (no space), then strips the bullet char plus any following whitespace with `[1:].lstrip()`.
- **Rationale:** Same non-ASCII-space issue: the character after `●` in the capture may be non-ASCII. Matching just `●` and stripping any whitespace handles both variants without breaking the existing test cases.
- **Applies to:** batch 1

### Decision: surface exceptions in integration test

- **Decision:** Each test function in `test-claude-psmux.py` prints `f"[FAIL] {type(exc).__name__}: {exc}"` to stderr before returning 1.
- **Rationale:** Currently every failure shows as `[FAIL] test_X: test returned non-zero` with no diagnostic detail. This makes debugging live test failures impossible without re-running manually.
- **Applies to:** batch 3

### Decision: hub config only for via_psmux flip

- **Decision:** Set `via_psmux: true` in `mill-config.yaml` (repo root). Do not touch `plugins/mill/templates/mill-config.yaml`.
- **Rationale:** psmux viability is machine-specific. The hub config is the per-machine override; the template is the portable default for new hubs.
- **Applies to:** batch 3

## All Files Touched

- `doc/psmux-tui-behavior.md`
- `mill-config.yaml`
- `plugins/mill/integration_tests/test-claude-psmux.py`
- `plugins/mill/scripts/_psmux_capture.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/unit_tests/test-claude-sub.py`
- `plugins/mill/unit_tests/test-psmux-capture.py`
