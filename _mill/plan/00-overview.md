# Plan: Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content

```yaml
task: "Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content"
slug: "mill-go-dispatch-and-skill-gaps"
approved: false
started: "20260706-171306"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: html-unescape-agent-output
    file: 01-html-unescape-agent-output.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-review-finalize.py
  - number: 2
    name: dispatch-and-skill-doc-fixes
    file: 02-dispatch-and-skill-doc-fixes.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: html.unescape at read time, not write time

- **Decision:** Every site that reads an `--agent-output` file back from disk and treats its contents as captured `<task-notification>` text wraps the read with stdlib `html.unescape(...)` before any further parsing. Do not change the SKILL.md capture-step prose (step 5, "Capture output") — the raw (possibly HTML-escaped) text is still written to `.out.md` as-is; the fix lives entirely in the code that reads that file back.
- **Rationale:** The harness escapes the `<task-notification>` payload uniformly end-to-end before delivery. Fixing the corruption at the read site is mechanical, testable, and protects every current and future caller regardless of what the orchestrator (an LLM following prose) transcribes at write time. `html.unescape` is stdlib and handles the full HTML5 entity set correctly (not a hand-rolled `&lt;`/`&gt;`/`&amp;` regex).
- **Applies to:** html-unescape-agent-output (Batch 1) only.

### Decision: documentation-only edits carry no test surface

- **Decision:** Batch 2's four fixes (#606, #599, #598, #596) are SKILL.md prose edits only — no CLI flag, behavior, or code path changes. `verify: null` for the batch; each card is checked by re-reading the edited section against the corresponding CLI's actual source behavior (already cross-checked during discussion), not by automated tests.
- **Rationale:** None of these four fixes touch executable code — inventing a test would be testing prose against itself. `mill:testing` conventions apply to code with runnable surface; these have none.
- **Applies to:** dispatch-and-skill-doc-fixes (Batch 2) only.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/skills/workflow/SKILL.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
