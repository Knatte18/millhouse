# Plan: Agent-dispatch boundary gaps: source-read guidance, fork directive-echo, and raw FileNotFoundError on missing agent-output

```yaml
task: 'Agent-dispatch boundary gaps: source-read guidance, fork directive-echo, and raw FileNotFoundError on missing agent-output'
slug: mill-agent-dispatch-guidance-gaps
approved: true
started: 20260727-172506
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: dispatch-guidance-docs
    file: 01-dispatch-guidance-docs.md
    depends-on: []
    verify: null
  - number: 2
    name: finalize-output-missing-file-error
    file: 02-finalize-output-missing-file-error.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
```

## Shared Decisions

### Decision: no cross-batch dependency

- **Decision:** Batch 1 (documentation-only) and Batch 2 (code fix + regression test) are independent — neither reads, edits, nor depends on any file the other touches.
- **Rationale:** Batch 1 touches `CLAUDE.md` and `plugins/mill/skills/mill-start/SKILL.md` (prose guidance only); Batch 2 touches `plugins/mill/scripts/_implementer_common.py` and `plugins/mill/unit_tests/test-implementer-common.py` (a shared helper function and its regression test). Zero file overlap, zero semantic dependency.
- **Applies to:** all batches

### Decision: stderr + non-zero return code, not a JSON error envelope

- **Decision:** The `finalize_from_output` fix (Batch 2, Card 3) prints a plain, actionable message to stderr and returns `1` — it does NOT import or use `_review_cli.print_error_envelope`.
- **Rationale:** `finalize_from_output` is called only from the three implementer-family CLIs (`millpy-fix.py`, `millpy-implement.py`, `millpy-merge-in-subagent.py`), all of which already validate other missing-flag conditions with a plain `print(..., file=sys.stderr); return 1` pattern (see `millpy-fix.py`'s own `if not args.agent_output:` check immediately above its `finalize_from_output` call site). `print_error_envelope` is a review-CLI-specific JSON-envelope helper imported from `_review_cli` and used only by `millpy-review-discussion.py`/`millpy-review-plan.py`/`millpy-review-code.py`; it must not be pulled into the implementer-family shared helper, which has no such envelope contract.
- **Applies to:** finalize-output-missing-file-error

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
