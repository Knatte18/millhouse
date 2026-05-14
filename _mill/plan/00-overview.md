# Plan: (A) -- Benchmark Gemini single-reviewers vs sonnetmax baseline

```yaml
task: "(A) -- Benchmark Gemini single-reviewers vs sonnetmax baseline"
slug: bench-gemini-single-reviewers
approved: false
started: "20260514-083609"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: setup
    file: 01-setup.md
    depends-on: []
    verify: "PYTHONPATH=plugins/mill/scripts python -c \"from _reviewers import load; from pathlib import Path; load(Path('.wiki'))\""
  - number: 2
    name: bench-script
    file: 02-bench-script.md
    depends-on: [1]
    verify: "python plugins/mill/integration_tests/bench-reviewers.py --reviewers test_stub --types discussion"
  - number: 3
    name: run-bench
    file: 03-run-bench.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

### Decision: wiki-write-mechanism

- **Decision:** All modifications to `wiki/reviewers.yaml` must go through `_wiki.write_commit_push` or `git -C <wiki_path>` inside a `_wiki.wiki_lock` block. The `.wiki` junction is used only for path listing (Edits: fields in cards); scripts always resolve the real path via `_paths.resolve_wiki_path(git_root)`.
- **Rationale:** CLAUDE.md path invariant — junctions are IDE convenience only; scripts must never use junction paths.
- **Applies to:** batch 01 (setup)

### Decision: gemini-bulk-only-benchmark

- **Decision:** The benchmark runs all reviewers in bulk mode (tooluse=false). The bench script reads the reviewer spec from the registry and passes it to `_reviewer_single.run()`; if a reviewer has `tooluse: true` in its spec, it will run in tool-use mode automatically.
- **Rationale:** The benchmark's purpose is comparing Gemini bulk-mode stability and quality. The `_tool` variants (g3flash_preview_tool, g25pro_tool) are added to the registry for completeness but not used in the benchmark run (cards 5 uses the non-tool variants: g25flash, g3flash_preview, g25pro).
- **Applies to:** batch 01 (registry entries), batch 03 (run-bench)

### Decision: timeout-300s

- **Decision:** The bench script passes `timeout=300` to `_reviewer_single.run()`. On timeout the row records TIMEOUT in the Verdict column rather than raising.
- **Rationale:** Trial data showed g25flash timed out at 120s on a ~1900-token prompt, then returned in 61s on retry. 300s covers observed worst-case without blocking too long on a hang.
- **Applies to:** batch 02 (bench-script)

### Decision: results-to-scratch

- **Decision:** Benchmark results are written to `.scratch/bench-<YYYYMMDD-HHMMSS>.md`. The file is also printed to stdout so the implementer can inspect it immediately.
- **Rationale:** `.scratch/` is the shared ephemeral location per conversation conventions; gitignored. Results are not committed.
- **Applies to:** batch 03 (run-bench)

### Decision: format-compliance-definition

- **Decision:** Format compliance for a review response is: (1) response starts with `# Review:`, (2) response contains a fenced yaml block with a `verdict:` field parseable by `_review_common.parse_verdict()`, (3) response contains a `## Verdict` section.
- **Rationale:** These are the three structural invariants from `review-output.schema.md`. A response failing any of them indicates role drift or structural output failure.
- **Applies to:** batch 02 (bench-script metrics)

## All Files Touched

- `.wiki/reviewers.yaml`
- `plugins/mill/integration_tests/bench-reviewers.py`
- `plugins/mill/integration_tests/fixtures/sample-code.py`
