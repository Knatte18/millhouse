# Plan: _plan_validate.py: hardcoded tag-name check and fenced-code-block-unaware card parsing

```yaml
task: "_plan_validate.py: hardcoded tag-name check and fenced-code-block-unaware card parsing"
slug: mill-plan-validate-heuristic-gaps-2
approved: false
started: '20260808-171155'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: plan-validate-heuristic-fixes
    file: 01-plan-validate-heuristic-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
```

## Shared Decisions

### Decision: custom-tag discovery via denylist, not a hardcoded/expanded literal

- **Decision:** `verify-excludes-edited-tagged-test` discovers a Go test file's "custom" build
  tag(s) by extracting every identifier from its `//go:build` expression and excluding a
  hardcoded denylist of standard Go tags (GOOS values, GOARCH values, reserved words, and
  `^go[1-9]\d*\.\d+$`-shaped release-version tags). Remaining identifiers are custom tags. This
  denylist is intentionally separate from, and larger than, `_implementer_common.py`'s
  `_GO_BUILD_TAG_GOOS`/`_GO_BUILD_TAG_GOARCH` (a different check with a different safety
  direction — that check's misclassifications fail closed via a downstream `go build`, this
  check's would not).
- **Rationale:** discovering from the file's own expression (rather than a bigger fixed list of
  known custom tag names) is the only fix that generalizes — a bigger fixed list just reproduces
  the same false-negative bug class the next time a repo invents a new tag name.
- **Applies to:** 01-plan-validate-heuristic-fixes

### Decision: ANY custom tag on a file satisfies verify:'s -tags requirement

- **Decision:** when a file has more than one custom tag (via boolean composition, e.g.
  `//go:build scout && smoke`), the check is satisfied if ANY of the file's custom tags appears
  in `verify:`'s `-tags` value (same comma/whitespace-split token match as today, generalized
  from a single literal to a set).
- **Rationale:** matches the check's existing precision level (no real AND/OR boolean
  evaluation); requiring ALL custom tags to match is a materially larger scope not requested by
  either source issue.
- **Applies to:** 01-plan-validate-heuristic-fixes

### Decision: check every edited tagged file independently, not just the first

- **Decision:** the check's per-batch loop no longer `break`s at the first tagged edited test
  file. Every `_test.go` token in `Edits:` is resolved and checked independently; each untested
  tagged file produces its own finding.
- **Rationale:** generalizing tag *discovery* without also generalizing loop *coverage* would
  reproduce bug 1's exact false-negative class inside the fix itself — a batch editing both a
  `scout`-tagged and a `smoke`-tagged file with `verify: -tags scout` would otherwise still
  silently pass despite the untested `smoke` file.
- **Applies to:** 01-plan-validate-heuristic-fixes

### Decision: deterministic message tag selection via sorted(tags)[0]

- **Decision:** when a file has more than one custom tag, the finding message names
  `sorted(tags)[0]` (alphabetically first) — never raw `set[str]` iteration order.
- **Rationale:** `set[str]` iteration order is not guaranteed deterministic across runs;
  `sorted(...)[0]` reuses this same function's own existing convention one call up
  (`edited_test_tokens = sorted(...)`).
- **Applies to:** 01-plan-validate-heuristic-fixes

### Decision: `_parse_cards` reuses the existing fence-toggle convention, guards both boundaries

- **Decision:** `_parse_cards` tracks a single `in_fence` boolean across its whole scan (toggled
  on every line starting with ` ``` `), reusing the exact convention already established by
  `_requirements_fence_aware_body` for the identical class of problem. The guard applies to BOTH
  the `### Card N:` new-card-start match and the "any other `### ` heading ends the card" match.
- **Rationale:** a fence quoting a `### Card N:`-shaped example is the same bug class as one
  quoting a plain `### ` heading — fixing only the reported ending-match would leave a symmetric,
  equally-real gap unfixed.
- **Applies to:** 01-plan-validate-heuristic-fixes

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
