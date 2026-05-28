# Batch: nb-digest-helper

```yaml
task: "CodeGuide support for .ipynb"
batch: nb-digest-helper
number: 1
cards: 2
verify: PYTHONPATH= python plugins/codeguide/unit_tests/test-nb-digest.py
depends-on: []
```

## Batch Scope

Delivers the deterministic core of notebook support: a new thin stdlib helper
`plugins/codeguide/scripts/nb_digest.py` that converts a `.ipynb` into a compact
text digest containing only markdown-cell text and code-cell source, with every
execution output stripped and oversized code cells truncated, plus its unit-test
suite. This is the external interface the templates and skills batches consume:
they instruct doc-generation to run this helper instead of the Read tool. The
helper is pure stdlib (no `nbformat`/`jupyter`), mirrors the existing
`resolve_scope.py` shape (public function + `_cli`/`main`, stdout=payload,
stderr=diagnostics, documented exit codes), and follows the
`ascii-markers-utf8-content` shared decision.

## Cards

### Card 1: Implement nb_digest.py

- **Context:**
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Edits:** none
- **Creates:**
  - `plugins/codeguide/scripts/nb_digest.py`
- **Deletes:** none
- **Requirements:**
  - Create `plugins/codeguide/scripts/nb_digest.py`, pure stdlib only (`json`,
    `sys`, `pathlib`, `argparse`) — do NOT import `nbformat` or `jupyter`
    (not installed in the plugin venv). Parse the documented nbformat JSON shape
    directly. Follow `resolve_scope.py` conventions: a module docstring
    documenting the public API + exit codes, a public function for testability,
    and a `main(argv)`/`_cli` wrapper.
  - Define module-level truncation constants: `MAX_CODE_CELL_LINES = 150`,
    `CODE_CELL_HEAD_LINES = 100`, `CODE_CELL_TAIL_LINES = 20`. These are internal
    tooling constants, not doc-facing values.
  - `def cell_source_text(cell: dict) -> str` — return the cell's `source` joined
    into one string. `source` may be a list of strings or a single string; handle
    both.
  - `def notebook_language(nb: dict) -> str` — return
    `nb["metadata"]["kernelspec"]["language"]` if present, else
    `nb["metadata"]["language_info"]["name"]`, else `"text"`. Used as the code
    fence info-string so non-Python kernels (R, Julia, etc.) are labeled
    correctly.
  - `def build_digest(nb: dict, source_name: str) -> str` — the pure core. Emit:
    - A header block of ASCII marker lines: `# notebook digest: <source_name>`,
      `# language: <lang>`, `# cells: <n>`.
    - For each cell in `nb["cells"]`, numbered from 1 in document order:
      - `markdown` cells: a marker line `# [markdown cell K]` followed by the
        verbatim markdown source (kept in full, never truncated).
      - `code` cells: a marker line `# [code cell K]`, then a fenced block
        ```` ```<lang> ```` ... ```` ``` ```` wrapping the code source. If the
        joined source exceeds `MAX_CODE_CELL_LINES` lines, truncate to the first
        `CODE_CELL_HEAD_LINES` + a marker line `# [code cell truncated: <omitted>
        lines omitted]` + the last `CODE_CELL_TAIL_LINES` (omitted = total - head
        - tail). If the cell has a non-empty `outputs` list, append a single
        marker line `# [<count> output(s) omitted]` AFTER the fenced block. Never
        read, decode, or emit any output content (no `outputs[*].data`,
        `.text`, image bytes) — only the count.
      - `raw` (or unknown) cells: a marker line `# [raw cell K]` followed by the
        verbatim source.
  - `def load_notebook(path) -> dict` — read the file as UTF-8 and `json.loads`
    it; raise `ValueError` if the result is not a dict or has no list-valued
    `cells` key. Let `json.JSONDecodeError` propagate.
  - `def main(argv) -> int` — accept exactly one positional path argument via
    `argparse`. First call `sys.stdout.reconfigure(encoding="utf-8",
    errors="replace")` so non-ASCII cell content never crashes a cp1252 stdout.
    Then `load_notebook` + `build_digest`, print the digest to stdout, return 0.
    On `ValueError`, `json.JSONDecodeError`, `OSError`, or `KeyError`: print an
    ASCII-only warning to stderr (no traceback), emit nothing to stdout, and
    return 2 (the documented "skip this file" code). Guard with
    `if __name__ == "__main__": sys.exit(main(sys.argv))`.
  - All helper-authored marker/warning strings must be ASCII (` -- ` not `—`,
    ` -> ` not `→`); only the pass-through cell content may be non-ASCII.
- **Commit:** `feat(codeguide): add nb_digest.py notebook-to-digest helper`

### Card 2: Unit tests for nb_digest.py

- **Context:**
  - `plugins/codeguide/unit_tests/test-resolve-scope.py`
  - `plugins/codeguide/unit_tests/run-all.py`
  - `plugins/codeguide/scripts/nb_digest.py`
- **Edits:** none
- **Creates:**
  - `plugins/codeguide/unit_tests/test-nb-digest.py`
- **Deletes:** none
- **Requirements:**
  - Create `plugins/codeguide/unit_tests/test-nb-digest.py` mirroring
    `test-resolve-scope.py` conventions: a `main() -> int` that runs assertions
    and prints `PASS:`/`FAIL:` lines, `sys.exit(main())` guard, and import via
    `HUB = Path(__file__).resolve().parent.parent.parent.parent;
    sys.path.insert(0, str(HUB / "plugins" / "codeguide" / "scripts"))` then
    `from nb_digest import build_digest, notebook_language, load_notebook`.
    Auto-discovered by `run-all.py` (`test-*.py` glob) — no edit to run-all.py.
  - Build notebook fixtures as in-memory Python dicts (nbformat shape) written to
    tempfiles via `tempfile`; no real Jupyter. Cover, at minimum:
    - **Outputs stripped:** a code cell with `outputs` containing a stream + an
      image (`data: {"image/png": "<base64>"}`) + a large text output yields the
      code source plus a `output(s) omitted` marker, and the base64/output
      payload string is ABSENT from the digest (assert the sentinel bytes are not
      a substring).
    - **Markdown kept verbatim:** markdown cell content appears unchanged.
    - **Oversized code cell truncated:** a code cell over `MAX_CODE_CELL_LINES`
      lines is truncated with the `code cell truncated` marker; a normal code
      cell is emitted intact.
    - **Non-Python kernel:** a notebook whose `metadata.kernelspec.language` is
      e.g. `"R"` produces fences labeled `R` via `notebook_language`.
    - **Empty notebook** (`cells: []`) and **outputs-free notebook** produce a
      digest with no crash and no spurious `output(s) omitted` marker.
  - For CLI-level cases, invoke the script as a subprocess with
    `subprocess.run([sys.executable, str(HUB / "plugins" / "codeguide" /
    "scripts" / "nb_digest.py"), str(nb_path)], capture_output=True, text=True,
    encoding="utf-8")`:
    - **Malformed input:** a non-JSON / non-notebook file → return code 2, empty
      stdout, non-empty stderr.
    - **Non-ASCII cell content round-trips:** a markdown or code cell containing
      Unicode prose / CJK comment is present in stdout (decoded UTF-8) without
      crashing; the run exits 0.
  - The test's own printed output must be ASCII-only so it does not crash a
    cp1252 console when run directly.
- **Commit:** `test(codeguide): unit tests for nb_digest.py`

## Batch Tests

`verify: PYTHONPATH= python plugins/codeguide/unit_tests/test-nb-digest.py` runs
the new test file directly (codeguide unit tests are pure-stdlib, invoked as
`python <test-file>` — `run-all.py` has no `--only` flag, and the suite uses
plain `python`, not `uv`). The single-file scope matches the batch's surface:
only `nb_digest.py` is created here. The `PYTHONPATH=` prefix clears the inherited
mill-cache scripts dir so the test's own `sys.path.insert` loads the worktree
helper. Covers output-stripping, code-cell truncation, kernel labeling,
malformed-input exit code, and non-ASCII round-trip.
