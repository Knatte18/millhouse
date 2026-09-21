# Plan: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps

```yaml
task: '_plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps'
slug: plan-validate-context-completeness-round2-gaps
approved: true
started: 20260921-153440
parent: main
root: ""
verify: null
discussion_sha: 1d3b0ccd87ddd3252e036d7dd65677e5ff382c33
```

## Batch Index

```yaml
batches:
  - number: 1
    name: plan-validate-check-fixes
    file: 01-plan-validate-check-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: mill-plan-fix-table-docs
    file: 02-mill-plan-fix-table-docs.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: no `done_gate` change

- **Decision:** `pipeline.done_gate` stays `null` (unchanged from the hub's current setting) — this plan
  does not touch `mill-config.yaml`.
- **Rationale:** per mill-plan's Done-gate reminder, `uvx ruff check .` was run against the current
  worktree tip (not this plan's own changes) from `git_root` before considering a lint-only
  `done_gate` default; it exited non-zero with 2009 pre-existing findings (`RUF100` and others),
  unrelated to this task. Setting `done_gate` to it would make every future task in the hub depend on
  unrelated repo-wide lint debt being fixed first, so it is left `null` per that same guidance's
  explicit escape hatch.
- **Applies to:** all batches.

### Decision: no `Moves:` in this plan

- **Decision:** every card in this plan uses `Moves: none` — no file is renamed or relocated.
- **Rationale:** every fix in `discussion.md` is a same-file surgical edit (new helper functions,
  tightened regexes, new parameters, new detection branches) to `_plan_validate.py`, its own test file,
  or `mill-plan/SKILL.md`'s fix-table prose. No `## Rename mechanic` section is needed in either batch.
- **Applies to:** all batches.

### Decision: no fenced quote of existing source as an edit anchor

- **Decision:** no card's `Requirements:` uses a triple-backtick fence to quote EXISTING, unchanged
  `_plan_validate.py` source as an edit anchor. Every existing-code anchor is a short, single-line,
  inline-backtick quote (e.g. `` `cs_member_re = re.compile(...)` ``) naming the exact line or
  construct to change, with prose describing the edit. A fenced block IS used where a card's
  Requirements: needs to show a complete new function body being introduced (code that does not exist
  anywhere in the repo yet) — that is safe under the current, unfixed checkers, since brand-new code
  can never accidentally byte-match (clean, strip-N, or add-N) an `Edits:` file's real content, so it
  is silently treated as an "illustrative snippet" by today's `requirements-quote-indent-drift`
  exactly like any other new-code fence, and cited paths/symbols inside it are exempted by
  `context-completeness`'s existing fence-quoting exemption either way.
- **Rationale:** this plan's own batch 1 changes `requirements-quote-indent-drift`'s fence-matching
  behavior (Card 7) and is validated by the pre-existing (not-yet-fixed) `_check_requirements_quote_
  indent_drift`/`_check_context_completeness` checks this task modifies. Quoting EXISTING source
  byte-exactly risks an accidental indent-drift finding on this plan itself if the quote's indentation
  doesn't match the source's; quoting entirely NEW code carries no such risk today, since the
  new-code path is exactly the gap this task is fixing (not live yet against this plan's own
  self-validate run) — inline single-backtick anchors are used for existing-code edit points instead,
  matching this file's own "stable identifiers" principle (name the function/constant, not necessarily
  reproduce a full diff of existing code).
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
