# Batch: write-brief-warning

```yaml
task: mill-plan/mill-start planning-process gaps, round 2
batch: write-brief-warning
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-agent-dispatch.py
depends-on: []
```

## Batch Scope

Adds a stderr warning to `_agent_dispatch.write_brief` when it is about to overwrite an existing, unfinalized `.out.md` — the mechanical half of #1054 (mill-plan's own doc statement, "Finalize advances the round", is batch 1 card 4). One card: the source change plus its test.

## Cards

### Card 12: `write_brief` — warn before overwriting a stale unfinalized `.out.md`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `write_brief(briefs_dir, role, scope, round_n, prompt_text, output_contract=False)`, immediately before the existing line `output_path_for(brief_path).unlink(missing_ok=True)`, add a check for the `.out.md` already existing and, when it does, print a warning to stderr before the unlink proceeds:

  ```python
    # Warn (never refuse) when a prior dispatch's output is about to be discarded -- a legitimate
    # transient-retry re-dispatch reuses this same path by design, so this must never become a
    # hard failure (#1054).
    stale_out_path = output_path_for(brief_path)
    if stale_out_path.exists():
        print(
            f"[write_brief] warning: overwriting existing unfinalized output "
            f"'{stale_out_path}' -- if this round's finalize already ran, its result is about "
            f"to be lost",
            file=sys.stderr,
        )
  ```

  This replaces the standalone `output_path_for(brief_path).unlink(missing_ok=True)` line — call `output_path_for(brief_path)` once (bound to `stale_out_path` above) and reuse it for both the existence check and the unlink, rather than calling `output_path_for` twice. `_agent_dispatch.py` does not currently import `sys` — add `import sys` to its import block. Update the module's top-of-file docstring `write_brief` entry to mention the new warning (one clause, e.g. "...printing a warning to stderr first when a stale `.out.md` already exists.").

  The warning fires for both `output_contract=True` and `output_contract=False` calls, and regardless of whether the stale file existed before this specific call — it is purely a diagnostic print, never a behavior change: the unlink and subsequent write must still succeed exactly as they do today.

  Add a new test to `test-agent-dispatch.py`, `def test_write_brief_warns_on_stale_out_md_overwrite() -> None:`, placed immediately after the existing `test_write_brief_truncates_stale_out_md` function and added to the `tests` list in `main()` right after `test_write_brief_truncates_stale_out_md`. Mirror that existing test's setup (pre-create a brief, plant a stale `.out.md` next to it, re-dispatch the same role/scope/round), but capture stderr via `contextlib.redirect_stderr` and `io.StringIO` around the re-dispatch `write_brief` call, then assert the captured text contains both `"[write_brief] warning:"` and the stale `.out.md` path string. Also assert that when NO stale `.out.md` exists before a `write_brief` call (a fresh `briefs_dir`), the captured stderr is empty — the warning must never fire spuriously. `test-agent-dispatch.py` does not currently import `contextlib`/`io` — add both to its import block.
- **Commit:** `feat(agent-dispatch): warn before overwriting a stale unfinalized .out.md`

## Batch Tests

`verify:` runs `test-agent-dispatch.py` directly (single file, per the "Single test file" convention) — covers every existing `write_brief`/`output_path_for` test plus the new stderr-warning test and its empty-stderr counterpart.
