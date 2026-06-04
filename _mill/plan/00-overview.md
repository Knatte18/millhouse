# Plan: Fix millpy-bg EXIT marker and implementer reliability

```yaml
task: Fix millpy-bg EXIT marker and implementer reliability
slug: millpy-bg-and-implement-fixes
approved: false
started: 20260604-164011
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: bg-json-fallback
    file: 01-bg-json-fallback.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py test-millpy-bg.py

  - number: 2
    name: implementer-stuck-fields
    file: 02-implementer-stuck-fields.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py

  - number: 3
    name: psmux-timeout-config
    file: 03-psmux-timeout-config.md
    depends-on: []
    verify: null

  - number: 4
    name: mill-go-skill-update
    file: 04-mill-go-skill-update.md
    depends-on: [1, 2]
    verify: null
```

## Shared Decisions

### Decision: imports-stdlib-only-in-worker-path

- **Decision:** `_bg.py` uses only stdlib (`json`, `re`, `os`, `time`, `logging`, `pathlib`). Adding `import json` does not violate this constraint — `json` is stdlib.
- **Rationale:** The `_bg.py` module is imported by the worker fast-path in `millpy-bg.py` which has a stdlib-only constraint; adding `json` (stdlib) is safe.
- **Applies to:** batch bg-json-fallback

### Decision: commits_made-default-zero

- **Decision:** When `git rev-list --count` fails or `start_sha is None`, `commits_made` defaults to 0 rather than being omitted from the JSON.
- **Rationale:** Callers check `commits_made > 0` for the skip-to-cleanliness routing; a missing key would require `stuck.get("commits_made", 0)` everywhere. Explicit 0 is cleaner.
- **Applies to:** implementer-stuck-fields

### Decision: response-poll-fallback-order

- **Decision:** `_resolve_response_poll_timeout_s(mode)` falls back to `RESPONSE_POLL_TIMEOUT_S.get(mode, 600)` — not a hard-coded number — so any unknown future mode gets 600 s by default.
- **Rationale:** Keeps the default table as the single source of truth; config overrides are additive.
- **Applies to:** psmux-timeout-config

## All Files Touched

- `plugins/mill/scripts/_bg.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-bg-liveness.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
