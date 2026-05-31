# Plan: haiku-4-5 implementer reliability (hang + path mangle)

```yaml
task: haiku-4-5 implementer reliability (hang + path mangle)
slug: haiku-implementer-reliability
approved: false
started: 20260531-092022
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: timeout-and-brief-size-guard
    file: 01-timeout-and-brief-size-guard.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-llm-claude.py
  - number: 2
    name: scope-violations-and-brief
    file: 02-scope-violations-and-brief.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-implementer-common.py
  - number: 3
    name: unit-tests
    file: 03-unit-tests.md
    depends-on: [1, 2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-implementer-common.py test-millpy-implement.py
```

## Shared Decisions

### Decision: ASCII-only print output

- **Decision:** All new strings passed to `print()` and `json.dumps()` in Python scripts must use ASCII only. Use `--` instead of `--` (em dash), `->` instead of unicode arrows.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII characters.
- **Applies to:** all batches

### Decision: scope_violations is a list of path strings

- **Decision:** `compute_scope_violations` returns `list[str]` of bare path strings (without the `?? ` prefix). The `scope_violations` JSON field is a JSON array of those strings.
- **Rationale:** Stripping the `?? ` prefix keeps the output clean for the operator and avoids leaking git porcelain format details into the API.
- **Applies to:** batches 2, 3

### Decision: brief-size guard is a compound condition

- **Decision:** `max_chars = cfg.get("llm", {}).get("max_implementer_prompt_chars", 0); if max_chars > 0 and len(prompt_text) > max_chars:`. When the key is absent or 0, `max_chars > 0` short-circuits and the guard never fires.
- **Rationale:** Prevents always-firing behavior when `max_implementer_prompt_chars` is absent or 0 (the disabled default).
- **Applies to:** batches 1, 3

### Decision: timeout override after impl_spec resolution

- **Decision:** In both `millpy-implement.py` and `millpy-fix.py`, the timeout line moves to AFTER `impl_spec`/`fixer_spec` is resolved: `timeout = impl_spec.get("timeout") or cfg.get("llm", {}).get("implementer_timeout", 1800)`.
- **Rationale:** `impl_spec` is resolved by `_reviewers.resolve()` which runs after the original `timeout =` line; reading `impl_spec.get("timeout")` requires the spec to already be available.
- **Applies to:** batch 1

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/mill-agents.yaml`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-cleanliness.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
