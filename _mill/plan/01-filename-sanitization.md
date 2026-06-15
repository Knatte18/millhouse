# Batch: filename-sanitization

```yaml
task: "Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading"
batch: filename-sanitization
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths-sanitize.py test-agent-dispatch.py
depends-on: []
```

## Batch Scope

This batch delivers Windows-safe filenames for batch names. It adds one shared sanitizer (`_paths.sanitize_filename_component`), applies it at the single brief-path choke point (`_agent_dispatch.write_brief`) — the root cause of both #454 (colon → NTFS ADS) and #456 (slash → missing-subdir `FileNotFoundError`) for brief files — and replaces the two duplicated inline sanitize snippets in `millpy-implement.py` with the shared helper. The external interface the next batch consumes is `_agent_dispatch.write_brief`'s signature (unchanged) and the `_paths` module (batch 2 adds an unrelated helper there). No behavior outside filename construction changes; the raw batch name is preserved everywhere it is a logical identifier (see Shared Decision `sanitize-only-filenames`).

## Cards

### Card 1: Add shared filename sanitizer to `_paths.py`

- **Context:**
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-paths-sanitize.py`
- **Deletes:** none
- **Requirements:** Add a pure function `sanitize_filename_component(name: str) -> str` to `_paths.py` that returns `re.sub(r'[:\\/*?"<>|]', '-', name)` — replacing every Windows-reserved character (colon, backslash, forward-slash, asterisk, question-mark, double-quote, less-than, greater-than, pipe) with a single hyphen. Add `re` to the module imports if not already present, and add `"sanitize_filename_component"` to the module's public-API docstring listing. Create `test-paths-sanitize.py` following the `sys.path.insert` + `test_*` + `print("PASS ...")` pattern of `test-agent-dispatch.py`: assert each unsafe character maps to `-`; assert a clean name (`Core fix emit_prepare`) passes through unchanged; assert a multi-unsafe name (`internal/lock: do x`) yields no reserved characters in the result; include a `__main__` block that runs every `test_*` function (mirror the runner block in `test-agent-dispatch.py`).
- **Commit:** `fix(paths): add sanitize_filename_component for Windows-safe filenames`

### Card 2: Sanitize the scope component in `write_brief`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_agent_dispatch.write_brief`, import `sanitize_filename_component` from `_paths` and build the filename as `brief_path = briefs_dir / f"{role}-{sanitize_filename_component(scope)}-r{round_n}.md"`. Only the `scope` component is sanitized; `role` and `round_n` are unchanged. The function must still return the actual on-disk path it wrote, and `emit_prepare` (in `_implementer_common.py`) must keep emitting the **raw** `scope` in its JSON envelope — do not change `emit_prepare`. Update `_agent_dispatch.py`'s module docstring line for `write_brief` to note the scope is sanitized for filename safety. Extend `test-agent-dispatch.py` with: a test that `write_brief(..., scope="Core fix: emit_prepare", ...)` writes a real file whose name contains no colon and whose returned path exists and round-trips the written text; a test that `write_brief(..., scope="internal/lock - x", ...)` writes a single flat file directly under `briefs_dir` (no nested directory, no `FileNotFoundError`). Register both new tests in the file's `__main__` runner block.
- **Commit:** `fix(agent-dispatch): sanitize batch-name scope in brief filename`

### Card 3: Replace inline snapshot sanitization with the shared helper

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`, replace BOTH occurrences (near lines ~189 and ~210 — one per snapshot-path construction branch) of the inline expression `_safe_batch = args.batch_name.replace(":", "-").replace("/", "-").replace("\\", "-")` (each feeding `.cleanliness-snapshot-{_safe_batch}.txt`) with `_safe_batch = _paths.sanitize_filename_component(args.batch_name)`. `_paths` is already imported in this module; confirm and reuse the existing import. Behavior for `:`/`/`/`\` is unchanged; the helper additionally covers `*?"<>|`. Do not touch any other use of `args.batch_name` (the raw name must remain for status and envelope lookups).
- **Commit:** `refactor(implement): use shared sanitizer for snapshot filename`

## Batch Tests

`verify:` runs `test-paths-sanitize.py` (the new sanitizer unit tests — full unsafe-character table, clean-name passthrough, multi-unsafe name) and `test-agent-dispatch.py` (existing `write_brief`/`resolve_dispatch_mode`/`model_to_tier` coverage plus the two new colon/slash brief-filename tests). Scope is the two files this batch's `Edits:`/`Creates:` affect; the snapshot dedup in Card 3 is behavior-preserving and exercised through the same `sanitize_filename_component` helper covered by `test-paths-sanitize.py`.
