# Batch: millpy-fix-prior-blocking-flag

```yaml
task: 'mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)'
batch: millpy-fix-prior-blocking-flag
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py
depends-on: []
```

## Batch Scope

This batch adds a `--prior-blocking <path>` CLI flag to `millpy-fix.py`, threads its content into a new `<PRIOR_BLOCKING>` render token consumed by both `fixer-batch-brief.md` and `fixer-holistic-brief.md`, and covers both with unit tests. It is independent of batch 01: `millpy-fix.py` never imports `_prior_blocking` — it only reads a digest file path handed to it by the orchestrator (batch 03), the same relationship `millpy-review-code.py --prior-notes` already has with its own orchestrator-built digest file. The external interface this batch delivers for batch 03 to consume is exactly: pass `--prior-blocking <path-to-digest-file>` to any `--nits-only` `millpy-fix.py` invocation, and the rendered fixer brief will show that file's content (or `"(none)"`) under `<PRIOR_BLOCKING>`.

## Cards

### Card 3: `--prior-blocking` flag, read logic, and render-token wiring

- **Context:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `main()`'s argparse block, immediately after the existing `--nits-only` argument definition (`parser.add_argument("--nits-only", action="store_true", help="Fix nits only (write nits-fixed marker if successful).")`), add:
    ```python
    parser.add_argument(
        "--prior-blocking",
        default=None,
        help=(
            "Path to a file containing a digest of prior rounds' BLOCKING findings "
            "for this scope. Used with --nits-only so the fixer does not blindly "
            "reintroduce an earlier BLOCKING problem. Omit if none available."
        ),
    )
    ```
    Mirror the existing `--prior-notes` argument's shape in `millpy-review-code.py` (same `default=None`, same plain string type, no `type=Path`).
  - Where `args` is used to resolve other path-like arguments into `Path` objects (near where `args.review_file` is turned into a `Path`), add: `prior_blocking_path = Path(args.prior_blocking) if args.prior_blocking else None`.
  - Immediately alongside the existing `nits_only_carveout` computation (the block computing `nits_only_carveout = (", unless every finding was a legitimate --nits-only no-op requiring no code change." if args.nits_only else ".")`), add:
    ```python
    if (
        prior_blocking_path is not None
        and prior_blocking_path.is_file()
        and prior_blocking_path.read_text(encoding="utf-8").strip()
    ):
        prior_blocking_text = prior_blocking_path.read_text(encoding="utf-8")
    else:
        prior_blocking_text = "(none)"
    ```
    Per `empty-digest-file-reads-as-none` (overview Shared Decisions), this checks both file-existence AND non-empty-after-strip content — unlike `_review_code.py`'s `prior_notes` read (its lines around 355-360, which check only `prior_notes.is_file()`), because `_prior_blocking.build_digest` can legitimately return `""` and batch 03's orchestration prose always writes that empty string to disk rather than skipping the write.
  - Add `"PRIOR_BLOCKING": prior_blocking_text,` to the batch-brief render-call token dict (the dict literal passed to `_render.render(template_path, {...})` for `fixer-batch-brief.md`, immediately after the existing `"NITS_ONLY_CARVEOUT": nits_only_carveout,` entry).
  - Add the identical `"PRIOR_BLOCKING": prior_blocking_text,` entry to the holistic-brief render-call token dict (the dict literal passed to `_render.render(template_path, {...})` for `fixer-holistic-brief.md`, immediately after its own `"NITS_ONLY_CARVEOUT": nits_only_carveout,` entry).
- **Commit:** `feat(mill-scripts): add --prior-blocking flag to millpy-fix.py`

### Card 4: `<PRIOR_BLOCKING>` token in both fixer brief templates

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/templates/fixer-batch-brief.md`
  - `plugins/mill/templates/fixer-holistic-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `fixer-batch-brief.md`'s leading HTML comment token list, add a new documented token line: `  <PRIOR_BLOCKING>      — digest of prior rounds' BLOCKING findings visible to this scope; "(none)" when there is none`.
  - In `fixer-batch-brief.md`'s body, add a new `## Prior BLOCKING findings` section immediately after the existing `## Before reading any finding` section and before `## Fix discipline`, containing one lead-in sentence — "The following BLOCKING findings were fixed in earlier rounds of this task. Do not reintroduce the problems they describe." — followed by the bare `<PRIOR_BLOCKING>` token on its own line. This is a genuine heading section (unlike `<LANGUAGE_SKILLS>`'s bare-line placement documented at `implementer-brief.md`'s line 17/50), because `<PRIOR_BLOCKING>` needs an explicit instruction sentence, not just injected markdown content.
  - Apply the identical treatment to `fixer-holistic-brief.md`: add the token to its leading HTML comment list, and add the same `## Prior BLOCKING findings` section (identical lead-in sentence) immediately after its `## Before reading any finding` section and before `## Fix discipline` — this file's `## Before reading any finding` section currently flows straight into `## Fix discipline` with nothing between them.
- **Commit:** `feat(mill-templates): add <PRIOR_BLOCKING> token to fixer briefs`

### Card 5: unit tests for the `--prior-blocking` flag and render-token threading

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Follow this file's existing conventions exactly: the `_make_fixture(tmp_path)` tempfile-backed fixture helper, and `unittest.mock.patch.object(millpy_fix._render, "render", ...)` / `unittest.mock.patch.object(millpy_fix._implementer_claude, "run")`-style patching already used elsewhere in this file. Note this file's existing `--nits-only` / `NITS_ONLY_CARVEOUT` tests patch `_render.render` with `return_value="Brief text"` only and assert on the JSON envelope, never on `call_args` — the new tests below are the first in this file to patch `_render.render` as a bare `Mock` and inspect `call_args` directly; follow the concrete instructions below exactly rather than an existing precedent for that specific pattern.
  - Add a test that runs `main(argv)` with `--stage prepare`, `--scope batch`, and `--prior-blocking <path>` pointing at a fixture file containing non-empty text, with `_render.render` patched as a bare `Mock` (not `return_value`-only, so `call_args` is inspectable) — assert `mock_render.call_args[0][1]["PRIOR_BLOCKING"]` equals the fixture file's exact text.
  - Add the same test for `--scope holistic`.
  - Add a test with `--prior-blocking` omitted entirely — assert `mock_render.call_args[0][1]["PRIOR_BLOCKING"] == "(none)"`.
  - Add a test with `--prior-blocking` pointing at a file that exists but is empty (zero bytes) — assert `mock_render.call_args[0][1]["PRIOR_BLOCKING"] == "(none)"` (covers `empty-digest-file-reads-as-none`, the case `_review_code.py`'s own `--prior-notes` handling never has to cover).
- **Commit:** `test(mill-scripts): cover --prior-blocking flag/render-token threading`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-millpy-fix.py` — the file this batch's card 5 directly extends, and which already exercises every other flag/render path this batch's cards 3-4 touch (`--nits-only`, `NITS_ONLY_CARVEOUT`, the batch/holistic render calls). No other test file references `millpy-fix.py`'s argparse or render wiring.
