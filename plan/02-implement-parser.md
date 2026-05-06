# Batch: Implement parser hardening

```yaml
task: 19 (A) — mill-go + scripts infra fixes
batch: Implement parser hardening
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch hardens the JSON report parser in `millpy-implement.py` and updates the implementer brief template to discourage the model behavior that triggers the parser. The two cards are one batch because they address the same failure mode from two angles (defensive parsing + model instruction).

The external interface this batch delivers: `_forward_output()` now uses regex extraction instead of reverse line scanning. Batch 05 (Tests) depends on this batch's changes to write meaningful regression tests.

Batch-local decisions:
- The regex `r'\{[^{}]*"status"[^{}]*\}'` uses a negated character class `[^{}]*` which matches any character (including newlines) that is not `{` or `}`. This correctly handles multi-line flat JSON objects without requiring `re.DOTALL`. No flags are needed.
- The `re` module is already in the Python standard library; no new dependency.

## Cards

### Card 3: Replace _forward_output() with regex extraction

- **Reads:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`:

  1. Add `import re` to the imports block at the top of the file (before the `import _active` group).

  2. Replace the entire `_forward_output()` function body with:
     ```python
     matches = re.findall(r'\{[^{}]*"status"[^{}]*\}', output)
     if matches:
         last = matches[-1]
         try:
             json.loads(last)
             print(last)
             return 0
         except json.JSONDecodeError:
             pass
     print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}))
     return 0
     ```
     The `re` module is imported at the module level in step 1 — do not add a local `import re` inside the function body.

  3. Update the `_forward_output()` docstring to reflect the new approach: "Extract the last JSON object containing a 'status' key from output using regex. Returns 0 in both success and fallback cases — the JSON on stdout is how the caller reads state. When no valid JSON is found, emits a stuck/logic sentinel."

  The function signature `def _forward_output(output: str) -> int:` is unchanged.

- **Commit:** `fix(millpy-implement): harden _forward_output() with regex JSON extraction`

### Card 4: Add "do not wrap" warnings to implementer-brief.md

- **Reads:**
  - `plugins/mill/templates/implementer-brief.md`
- **Modifies:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `## Report` section of `implementer-brief.md`, there are two fenced JSON blocks: one showing the success report shape and one showing the stuck report shape. After each fenced block, insert the following warning on its own line (immediately after the closing ` ``` ` fence):

  ```
  **Do not wrap the JSON in a code block. Output it as a bare line — no backticks, no fence. Anything other than a bare JSON line is treated as `stuck_type: logic`.**
  ```

  Add this warning after the success block AND after the stuck block. The existing text "Anything other than this JSON on the last line is a protocol violation; mill-go treats that as `stuck_type: logic` with reason 'no structured report'" at the end of the section remains — the two warnings above reinforce the rule at the point where the model sees the examples.

- **Commit:** `docs(implementer-brief): add no-code-block warnings after JSON examples`

## Batch Tests

`verify: null` — tests for `_forward_output()` are added in Batch 05 (Tests), which depends on this batch. No standalone verify command here.
