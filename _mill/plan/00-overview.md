# Plan: Wrap claude -p via psmux to use subscription instead of API credits

```yaml
task: Wrap claude -p via psmux to use subscription instead of API credits
slug: claude-p-wrapper
approved: true
started: 20260515-112247
parent: main
root: ""
verify: python plugins/mill/unit_tests/run-all.py
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: parser
    file: 01-parser.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-psmux-capture.py
  - number: 2
    name: driver
    file: 02-driver.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-psmux-driver.py
  - number: 3
    name: wrapper
    file: 03-wrapper.md
    depends-on: [1, 2]
    verify: python plugins/mill/unit_tests/run-all.py && python -m py_compile plugins/mill/scripts/millpy-claude-sub.py
  - number: 4
    name: integration-and-report
    file: 04-integration-and-report.md
    depends-on: [3]
    verify: python -m py_compile plugins/mill/integration_tests/test-claude-psmux.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: text-in / text-out wrapper, drop-in for `claude -p`

- **Decision:** The wrapper preserves `claude -p`'s I/O contract -- prompt on
  stdin, response on stdout, one-line JSON metadata envelope on stderr. No
  file-IO from the wrapper itself; reviewer modules continue to own
  file-writing as they do today.
- **Rationale:** Cross-provider symmetry with `_llm_gemini.py` and future
  Ollama provider; preserves `_llm_claude.py`'s public API shape so a
  follow-up task can wire the wrapper in behind a single import swap.
- **Applies to:** all batches

### Decision: Dual-marker reply protocol; parser slices between them

- **Decision:** Per call the wrapper generates `MILL_BEGIN_<8-hex>` and
  `MILL_END_<8-hex>` (two independent random suffixes); appends a footer
  to the prompt instructing Claude to bracket its reply with these markers
  on their own lines; the parser extracts the slice strictly between the
  first `begin_marker`-only line and the first `end_marker`-only line
  after it.
- **Rationale:** Eliminates the prompt-echo / TUI-status / `(bullet)`-prefix
  start-boundary problem entirely. Markers are per-call random so quoted
  occurrences in source / discussion text cannot collide.
- **Applies to:** all batches

### Decision: Mode-implicit tool-set; caller does NOT pick `--allowedTools`

- **Decision:** The wrapper exposes `--mode {bulk,tool-use,implementer}`;
  each mode hardcodes its tool set (`bulk`: `--tools ""`; `tool-use`:
  `--allowedTools "Read,Grep,Glob"`; `implementer`: `--allowedTools
  "Read,Edit,Write,Bash,Grep,Glob,Skill"`). Callers cannot override.
- **Rationale:** Single source of truth, mirrors `_llm_claude.run_bulk` /
  `run_tool_use` / `run_implementer` API surface.
- **Applies to:** all batches

### Decision: ASCII-only stderr / print output; UTF-8 file content

- **Decision:** Every `print()` and `sys.stderr.write()` string in the
  wrapper, driver, parser, tests, and report uses ASCII only. Em-dash ->
  ` -- `; arrow -> ` -> `. File CONTENT (markdown bodies, YAML values)
  may contain UTF-8 since it is read by tools, not echoed to the
  terminal.
- **Rationale:** Windows cp1252 terminals crash on non-ASCII stdout/stderr.
  CLAUDE.md `## Conventions worth carrying`.
- **Applies to:** all batches

### Decision: Cleanup in `finally` for psmux session and temp prompt file

- **Decision:** Every code path that creates a psmux session OR writes a
  temp prompt file MUST tear down both inside a `try / finally` so a
  failing call still releases resources. `kill_session` is idempotent
  (silently ignores "no such session"); `Path.unlink(missing_ok=True)`
  for the temp file.
- **Rationale:** Detached psmux sessions are silent if leaked; the
  `.scratch/` directory accumulates dead prompt files otherwise.
- **Applies to:** all batches

### Decision: Test-then-implement order within batches 01 and 02

- **Decision:** Within batch 01 (parser) and batch 02 (driver), the test
  card precedes the implementation card so the implementer sees the
  expected behaviour before writing the code. The `NotImplementedError`
  stub card runs first so imports work for the test card.
- **Rationale:** TDD-friendly for pure-function and mock-based units;
  matches the discussion's testing approach.
- **Applies to:** parser, driver

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch, sorted
alphabetically. mill-go reads this to warn if two parallel batches
touch the same file — a sign of a misplaced dependency._

- `_mill/spike-report.md`
- `plugins/mill/integration_tests/test-claude-psmux.py`
- `plugins/mill/scripts/_psmux.py`
- `plugins/mill/scripts/_psmux_capture.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/unit_tests/fixtures/psmux-capture/clean.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/markers-reversed.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/multiline.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/no-end-marker.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/polling-not-ready.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/quoted-marker-text.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/whitespace-compressed.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/with-scrollback.txt`
- `plugins/mill/unit_tests/fixtures/psmux-capture/with-status.txt`
- `plugins/mill/unit_tests/test-psmux-capture.py`
- `plugins/mill/unit_tests/test-psmux-driver.py`
