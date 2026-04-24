# Batch A — status-read-full

```yaml
batch: A
name: status-read-full
commit: "feat(_status): add read_full for full yaml + timeline parse"
```

## Scope

Add `read_full(status_path) -> dict` to `_status.py`. Returns the complete YAML block as a dict plus the full timeline as a list of raw strings. New sibling alongside `read_status` — does not call `read_status` internally.

## Cards

### A1 — `_status.read_full`

**Reads:** `plugins/mill/scripts/_status.py`

**Modifies:** `plugins/mill/scripts/_status.py`

- Add `read_full(status_path: Path) -> dict` after `read_status`.
- Parse top yaml block via `_split_fences(text, _YAML_FENCE)` → `yaml.safe_load` → full dict.
- Parse timeline block via `_split_fences(text, _TIMELINE_FENCE)` → raw non-empty lines as `list[str]`.
- Return `{"yaml": data, "timeline": timeline_lines}`.
- Raise `ValueError` (same pattern as `read_status`) on missing file, missing/unterminated blocks, yaml parse error.
- Update module docstring `Public API:` line to list `read_full`.

**Requirements:**
- `yaml` dict contains ALL keys from the yaml block (not the slim 5-key summary `read_status` returns).
- `timeline` list contains raw stripped lines; empty lines excluded.
- Batches section (`## Batches`) is NOT included in `timeline` — timeline block is strictly the `\`\`\`text` fence.

**Commit:** `feat(_status): add read_full for full yaml + timeline parse`

---

### A2 — unit test for `read_full`

**Reads:** `plugins/mill/unit_tests/test-status.py`

**Modifies:** `plugins/mill/unit_tests/test-status.py`

- Add `test_read_full_basic`: tempfile status.md with known yaml block and 2-entry timeline; assert yaml dict and timeline list match expected.
- Add `test_read_full_no_timeline`: status.md with empty timeline block; assert `timeline == []`.
- Add `test_read_full_missing_file`: assert `ValueError` on nonexistent path.

**Requirements:**
- Uses `tempfile.NamedTemporaryFile` (or `tmp_path` if the test file already uses pytest fixtures — match the existing style).
- No real git, no real LLM.

**Commit:** same as A1 (single commit for A).
