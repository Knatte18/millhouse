# Batch: Namespace constants

```yaml
task: Fix agent-dispatch prepare stage to emit namespaced subagent_type
batch: Namespace constants
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-implementer-common.py
depends-on: []
```

## Batch Scope

Fix the two `_agent_dispatch.py` constants to use plugin-namespaced agent names, replace hardcoded strings in `_implementer_common.py` with the constant, update the two unit tests whose assertions checked the old bare values, and correct the SKILL.md documentation example. All five files are one logical unit — the constants are the source of truth and the other changes flow directly from them.

## Cards

### Card 1: Update SUBAGENT_REVIEWER and SUBAGENT_IMPLEMENTER constants

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_agent_dispatch.py`, change `SUBAGENT_REVIEWER = "mill-reviewer"` to `SUBAGENT_REVIEWER = "mill:mill-reviewer"` and `SUBAGENT_IMPLEMENTER = "mill-implementer"` to `SUBAGENT_IMPLEMENTER = "mill:mill-implementer"`. Also update the two docstring example references: the module docstring at the top lists `SUBAGENT_REVIEWER, SUBAGENT_IMPLEMENTER` as exports (no string value shown there — no change needed in that section); the `write_brief` docstring uses `"mill-implementer"` as an example in the `role` param description — update to `"mill:mill-implementer"`. No other changes to this file.
- **Commit:** `fix(agent-dispatch): namespace SUBAGENT_REVIEWER and SUBAGENT_IMPLEMENTER constants`

### Card 2: Use SUBAGENT_IMPLEMENTER constant in _implementer_common.py

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_implementer_common.py`, in function `emit_prepare` (line ~118), replace the hardcoded string `"mill-implementer"` in `"subagent_type": "mill-implementer"` with `"subagent_type": _agent_dispatch.SUBAGENT_IMPLEMENTER`. In function `emit_prepare_no_dispatch` (line ~155), replace the same hardcoded string in `"subagent_type": "mill-implementer"` with `"subagent_type": _agent_dispatch.SUBAGENT_IMPLEMENTER`. The `_agent_dispatch` import is already present at line 4 — do not add a duplicate import.
- **Commit:** `fix(implementer-common): use SUBAGENT_IMPLEMENTER constant in emit_prepare variants`

### Card 3: Update unit test assertions for namespaced values

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-agent-dispatch.py`, in function `test_subagent_constants`, update `assert _agent_dispatch.SUBAGENT_REVIEWER == "mill-reviewer"` to `assert _agent_dispatch.SUBAGENT_REVIEWER == "mill:mill-reviewer"` and `assert _agent_dispatch.SUBAGENT_IMPLEMENTER == "mill-implementer"` to `assert _agent_dispatch.SUBAGENT_IMPLEMENTER == "mill:mill-implementer"`. In `test-implementer-common.py`, in Case 12, update `assert data["subagent_type"] == "mill-implementer"` to `assert data["subagent_type"] == "mill:mill-implementer"`. In Case 14 (the `emit_prepare_no_dispatch` test), after the existing `assert data["dispatch_needed"] is False` line, add `assert data["subagent_type"] == "mill:mill-implementer", f"expected mill:mill-implementer, got {data}"`.
- **Commit:** `test(agent-dispatch): update constant and prepare-envelope assertions to namespaced values`

### Card 4: Update mill-go SKILL.md documentation

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-go/SKILL.md`, on the line that reads `- \`subagent_type\`: one of \`"mill-implementer"\` or \`"mill-reviewer"\`` (line 113 of the file as of discussion), replace `"mill-implementer"` with `"mill:mill-implementer"` and `"mill-reviewer"` with `"mill:mill-reviewer"`. No other changes to this file.
- **Commit:** `docs(mill-go): update subagent_type examples to namespaced form`

## Batch Tests

`verify` runs `run-all.py --only test-agent-dispatch.py test-implementer-common.py`. These are the two test files whose assertions are directly updated by this batch. `_agent_dispatch.py` is a dependency of many scripts, but the change is a pure string value replacement with no API-shape change, so the cross-cutting risk is negligible. Running the unbounded suite is not justified.
