# Plan: _plan_validate false positives block plan authoring

```yaml
task: _plan_validate false positives block plan authoring
slug: mill-plan-validate-false-positives
approved: false
started: '2026-08-02T10:42:16Z'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: fix-plan-validate-false-positives
    file: 01-fix-plan-validate-false-positives.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
```

## Shared Decisions

### Decision: is_file() over exists() for context-completeness resolvability

- **Decision:** `_check_context_completeness`'s `resolvable` boolean uses
  `bool(existing_files)` — where `existing_files = [p for p in existing
  if p.is_file()]` — instead of `bool(existing)`. A directory can never
  legitimately appear in `Context:`/`Edits:`/etc. (those fields document
  files), so a directory-shaped backtick token can never be "missing"
  from them and must never be flagged.
- **Rationale:** deterministic regardless of incidental on-disk state
  (fixes #750's mid-run directory-creation nondeterminism as a side
  effect) and covers every directory-shaped false positive across
  #766, #756, #760 without a separate trailing-slash or punctuation
  heuristic — `Path(project_root) / '//'` also resolves to a
  directory-like path whose `.is_file()` is `False`, so #760's `//`
  repro falls out of the same fix for free.
- **Applies to:** fix-plan-validate-false-positives

### Decision: strip closing-fence trailing whitespace before quote-indent matching

- **Decision:** in `_check_requirements_quote_indent_drift`, each
  extracted `fence_body` is normalized with
  `re.sub(r"\n[ \t]*\Z", "", fence_body)` immediately after extraction,
  before either the byte-exact pre-check or the `N`-strip search loop
  runs.
- **Rationale:** `_RE_FENCE_BODY` is not line-anchored, so it always
  captures the closing ` ``` ` delimiter's own leading whitespace (0+
  spaces of Markdown list-continuation indentation) as a trailing
  fragment of the captured body — that fragment is markdown structure,
  never real quoted content. Stripping it fixes both #754 (byte-exact
  content that previously fell through to the `N`-search and matched
  an unrelated `N` via incidental adjacent-content coincidence) and
  #761 (a mid-line quoted fragment that previously matched only via
  `_strip_n_leading_spaces`'s `splitlines()` side effect of dropping
  the same trailing newline at `N=1`).
- **Applies to:** fix-plan-validate-false-positives

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
