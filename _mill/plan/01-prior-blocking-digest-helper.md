# Batch: prior-blocking-digest-helper

```yaml
task: 'mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)'
batch: prior-blocking-digest-helper
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-prior-blocking.py
depends-on: []
```

## Batch Scope

This batch adds the new pure-Python helper module `_prior_blocking.py`, which the mill-go orchestrator (batch 03) will call to build a cumulative, cross-scope digest of prior rounds' `### [BLOCKING...]` findings from `_mill/reviews/` review files, for feeding to a `--nits-only` fixer dispatch so it doesn't blindly undo an earlier BLOCKING fix. Its external interface is one function, `build_digest(reviews_dir, scope, batch_name=None) -> str`, that batch 03 invokes via an inline `python -c` snippet (mirroring how `mill-plan/SKILL.md` already self-runs `_plan_validate.run`) and batch 02's `millpy-fix.py --prior-blocking <path>` flag consumes the written-out digest file. This batch has no dependency on batch 02's flag work — it only produces the digest text; nothing here reads or writes `millpy-fix.py`. Per `digest-scans-current-disk-state-no-round-boundary` (overview Shared Decisions), the function takes no round parameter.

## Cards

### Card 1: `_prior_blocking.py` digest-extraction module

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_nit_gate.py`
  - `plugins/mill/scripts/_treeguard.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_prior_blocking.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Module docstring: this module builds a cumulative, cross-scope digest of prior `### [BLOCKING...]` findings from `_mill/reviews/` code-review files, for feeding a `--nits-only` fixer dispatch (`millpy-fix.py --prior-blocking`) so it has context on what BLOCKING problems earlier rounds already fixed. Distinguish it from the pre-existing prose-driven `prior-nonblocking-*` NIT digest documented in `mill-go/SKILL.md` (which this module does not touch or unify with).
  - `import re`, `from pathlib import Path`, `import _review_common`.
  - Define `_BLOCKING_HEADING_RE = re.compile(r"^###\s+\[(?P<sev>[A-Z0-9-]+)(?::(?P<cls>[a-z-]+))?\]\s+(?P<title>.*)$", re.MULTILINE)` — same shape as `_review_common.py`'s own `_RE_FINDING_HEADING` (near its line 1851-1854), scoped locally to this module rather than importing that private (leading-underscore) name.
  - Public function `build_digest(reviews_dir: Path, scope: str, batch_name: str | None = None) -> str`:
    - `assert scope in ("batch", "holistic")`.
    - `assert scope != "batch" or batch_name is not None` — `batch_name` is required iff `scope == "batch"`.
    - Return `""` immediately if `not reviews_dir.exists()`.
    - Classify every file in `sorted(reviews_dir.iterdir())` whose name ends in `.md`: try `_review_common.RE_SIMPLE.match(filename)` first; if it matches and `match.group("type") == "code"`, this file is holistic-scope. Otherwise try `_review_common.RE_BATCH.match(filename)`; if it matches and `match.group("type") == "code"`, this file is batch-scope for `match.group("batch")`. This mirrors `_nit_gate._find_final_code_review`'s own check-order (`_review_common.RE_SIMPLE` before `_review_common.RE_BATCH`, matches excluded from the second once matched by the first).
    - Build the selected file list: when `scope == "holistic"`, select every holistic-classified file plus every batch-classified file (any batch name). When `scope == "batch"`, select every holistic-classified file plus every batch-classified file whose batch equals `batch_name` only (never another batch's).
    - For each selected file (already `sorted()` above, so processing order is filename-ascending, i.e. chronological since every filename starts with `<timestamp>-`): read its text via `Path.read_text(encoding="utf-8")`, and for every `_BLOCKING_HEADING_RE` match in that text whose `match.group("sev") == _review_common.BLOCKING_SEVERITY` (exact string compare, imported from `_review_common`, not hardcoded `"BLOCKING"`), capture `title = match.group("title").strip()` and `context` = the first non-empty (`.strip()`-truthy) line found by scanning the file's lines strictly after the heading's own line, or `""` if none exists before EOF.
    - A finding demoted from BLOCKING to NIT is rendered on disk as `### [NIT...]` with a `**Demoted-from:** BLOCKING` marker line beneath it (per `_review_common.rewrite_demoted_findings`) — `_BLOCKING_HEADING_RE` filtered to `sev == BLOCKING_SEVERITY` never matches that heading text, so demoted findings are excluded with no separate detection logic needed. State this as a one-line comment at the filter site, not a docstring paragraph.
    - Format each finding as `f"- {title}: {context}"` when `context` is non-empty, else `f"- {title}"`; ASCII-fold the formatted line via `.encode("ascii", errors="replace").decode("ascii")` — the same convention already used in `_treeguard.py` (its lines 114-115) and `_pygit2_util.py`, not a "closest ASCII" transliteration.
    - Return `"\n".join(lines)` where `lines` is every formatted finding in file-then-heading order; `""` when no file contributed any BLOCKING heading.
- **Commit:** `feat(mill-scripts): add _prior_blocking digest-extraction helper`

### Card 2: unit tests for `_prior_blocking.build_digest`

- **Context:**
  - `plugins/mill/scripts/_prior_blocking.py`
  - `plugins/mill/unit_tests/test-nit-gate.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-prior-blocking.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Follow `test-nit-gate.py`'s fixture conventions: real tempfile-backed `_mill/reviews/`-shaped directories (`tmp_path` / `tempfile`), not in-memory strings, since `build_digest` does real file I/O (`reviews_dir.iterdir()`, `Path.read_text`).
  - Import `_prior_blocking` the same way `test-nit-gate.py` imports `_nit_gate` (direct module import via the shared `unit_tests` `PYTHONPATH` setup — mirror whatever import mechanism `test-nit-gate.py` already uses; do not introduce `importlib.util.spec_from_file_location` unless `test-nit-gate.py` itself uses that pattern).
  - Write one test method per case, each building its own small fixture directory of `.md` review files with real `### [BLOCKING...]` / `### [NIT...]` heading text, then calling `_prior_blocking.build_digest`:
    1. A single holistic-scope file (`YYYYMMDD-HHMMSS-code-review-r1.md`) with one `### [BLOCKING] <title>` heading and a following context line — `build_digest(reviews_dir, scope="holistic")` output contains that exact title.
    2. A heading with a class suffix, `### [BLOCKING:design] <title>` — included identically to case 1 (asserts the regex's optional `(?::(?P<cls>...))?` group doesn't break the `sev` match).
    3. A demoted finding rendered as `### [NIT:design] <title>` with a `**Demoted-from:** BLOCKING` line beneath it — asserted absent from the digest.
    4. Two batch-scope files for the same batch at rounds 1 and 2 (`...-code-review-foo-r1.md`, `...-code-review-foo-r2.md`), each with a distinct BLOCKING finding — `build_digest(reviews_dir, scope="batch", batch_name="foo")` includes both titles (cumulative aggregation, no round-boundary filtering per `digest-scans-current-disk-state-no-round-boundary`).
    5. A fixture spanning two different batch-named files (`foo`, `bar`) plus one holistic-round file, each with a distinct BLOCKING finding — `build_digest(reviews_dir, scope="holistic")` includes all three titles (cross-scope AND cross-batch aggregation).
    6. The identical fixture from case 5 — `build_digest(reviews_dir, scope="batch", batch_name="foo")` includes only `foo`'s own title plus the holistic file's title, and explicitly excludes `bar`'s title.
    7. An empty `_mill/reviews/`-shaped directory (or one containing only non-matching filenames) — `build_digest` returns `""`.
    8. A fixture containing a batch literally named `retry-fix` (`...-code-review-retry-fix-r1.md`, RE_BATCH match) and, separately, a genuine holistic file (`...-code-review-r1.md`, RE_SIMPLE match) — `build_digest(reviews_dir, scope="batch", batch_name="retry-fix")` picks up the `retry-fix` file's own finding correctly via `RE_BATCH`; and, using a second fixture containing ONLY the `retry-fix`-named file (no genuine holistic file), `build_digest(reviews_dir, scope="holistic")` returns `""` — proving the `retry-fix` file is never misclassified as holistic via an unanchored match.
    9. `reviews_dir` pointing at a path that does not exist on disk — `build_digest` returns `""` without raising.
- **Commit:** `test(mill-scripts): cover _prior_blocking digest extraction`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-prior-blocking.py` directly — the only file this batch's cards create or edit with runnable logic is `_prior_blocking.py`, and this is its dedicated, fully-scoped test file. No other test file is affected by this batch.
