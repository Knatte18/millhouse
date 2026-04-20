---
kind: plan-batch
batch-name: reviewers
batch-depends: [foundation]
approved: false
---

# Batch 02: Reviewers — `sonnetmax` + `sonnetmax_tool`

## Batch-Specific Context

Reviewer files are tiny wrappers around `_llm_claude`'s two functions. Each
declares `MODE` as a module-level constant that the backend reads before
dispatching. Both reviewers ship in v2.

## Batch Files

- scripts/_reviewer_sonnetmax.py
- scripts/_reviewer_sonnetmax_tool.py

## Steps

### Step 3: Create both reviewer modules

- **Creates:** `scripts/_reviewer_sonnetmax.py`, `scripts/_reviewer_sonnetmax_tool.py`
- **Modifies:** none
- **Reads:** `scripts/_llm_claude.py`
- **Requirements:**
  - `_reviewer_sonnetmax.py`:
    ```python
    """Bulk-mode reviewer using Claude Sonnet at max effort."""
    from _llm_claude import run_bulk

    MODE = "bulk"

    def run(prompt_text: str) -> str:
        return run_bulk(prompt_text, model="claude-sonnet-4-5", effort="max")
    ```
  - `_reviewer_sonnetmax_tool.py`:
    ```python
    """Tool-use reviewer using Claude Sonnet at max effort."""
    from _llm_claude import run_tool_use

    MODE = "tool-use"

    def run(prompt_text: str) -> str:
        return run_tool_use(prompt_text, model="claude-sonnet-4-5", effort="max")
    ```
  - Both modules expose exactly two public symbols: `MODE` and `run`.
  - Both modules propagate `LLMError` — do not catch.
- **Explore:**
  - `scripts/_llm_claude.py` — confirm the exact signatures of `run_bulk`
    and `run_tool_use` match what the reviewer calls.
- **depends-on:** [2]
- **Test approach:** smoke-test (import each module; check `MODE` constant;
  check `run` callable; optionally call with trivial prompt if `claude` in PATH).
- **Key test scenarios:**
  - Happy: `import _reviewer_sonnetmax; assert _reviewer_sonnetmax.MODE == "bulk"`.
  - Happy: `_reviewer_sonnetmax.run("Respond APPROVE")` returns text.
  - Happy: `import _reviewer_sonnetmax_tool; assert _reviewer_sonnetmax_tool.MODE == "tool-use"`.
- **Commit:** `feat(review): add sonnetmax + sonnetmax_tool reviewers`
