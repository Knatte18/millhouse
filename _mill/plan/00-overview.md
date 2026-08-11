# Plan: mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)

```yaml
task: 'mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)'
slug: mill-go-quality-gate-gaps
approved: false
started: 20260811-042158
parent: hanf/mill-merge-in-recompute-baseline-crash
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: prior-blocking-digest-helper
    file: 01-prior-blocking-digest-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-prior-blocking.py
  - number: 2
    name: millpy-fix-prior-blocking-flag
    file: 02-millpy-fix-prior-blocking-flag.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py
  - number: 3
    name: mill-go-wire-prior-blocking-digest
    file: 03-mill-go-wire-prior-blocking-digest.md
    depends-on: [1, 2]
    verify: null
  - number: 4
    name: done-gate-lint-defaults
    file: 04-done-gate-lint-defaults.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: digest-scans-current-disk-state-no-round-boundary

- **Decision:** `_prior_blocking.build_digest` takes no round-number parameter and no round-boundary filter. It scans every review file currently on disk in `_mill/reviews/` matching the scope-appropriate glob and extracts every `### [BLOCKING...]` heading found — full stop. mill-go's orchestration prose (batch 03) calls it unconditionally at every `--nits-only` dispatch site, with no "round 1 skips this" branch (unlike the existing prior-notes/NIT digest, which explicitly special-cases round 1).
- **Rationale:** A `--nits-only` fixer dispatch only ever fires on a round whose own verdict was `APPROVE` or `REQUEST_CHANGES` with `blocking_count == 0` — meaning that round's own review file, by construction, contains zero `### [BLOCKING...]` headings. Scanning "everything on disk right now" therefore already excludes the current round's own (empty-of-BLOCKING) contribution with no explicit boundary math needed, and at round 1 no review files exist yet so the scan naturally returns `""`. Adding an explicit round-boundary parameter would duplicate information already implicit in what is or isn't on disk, and introduces an off-by-one risk the discussion's Decisions don't otherwise require solving.
- **Applies to:** batch 01 (`_prior_blocking.py`'s public API), batch 03 (every mill-go/SKILL.md call site).

### Decision: empty-digest-file-reads-as-none

- **Decision:** `_prior_blocking.build_digest` may return `""` (zero prior BLOCKING findings). The digest file written to disk by batch 03's orchestration prose can therefore legitimately exist but be empty. `millpy-fix.py`'s `--prior-blocking` read logic (batch 02) treats a missing path, a non-existent file, AND an existing-but-empty (or whitespace-only) file identically as `"(none)"` — not just missing/non-existent, which is what the existing `--prior-notes` pattern in `_review_code.py` alone checks for (it never has to handle an empty-but-existing digest file, since its digest is written by orchestrator prose that skips the write entirely at round 1).
- **Rationale:** Without the extra empty-string check, an empty digest file would render as a blank `<PRIOR_BLOCKING>` section in the fixer brief instead of the established `"(none)"` sentinel, breaking the parallel with every other digest-style token in this codebase.
- **Applies to:** batch 01 (return contract), batch 02 (read contract).

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_prior_blocking.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-prior-blocking.py`
