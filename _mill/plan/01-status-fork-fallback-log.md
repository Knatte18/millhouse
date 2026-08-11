# Batch: status-fork-fallback-log

```yaml
task: 'mill-go2: fork-based fixer (NIT-fix) dispatch'
batch: 'status-fork-fallback-log'
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
depends-on: []
```

## Batch Scope

This batch delivers the only production-code change in the task: a new append-only
`## Fork-fallback log` section in `status.md`, plus the reader that turns it into control-flow state.
It is one batch because the two helpers, their shared block-locator, and their tests are a single
cohesive unit — the reader's contract is defined entirely by what the writer emits, and both live in
the same two files.

The external interface batch 2 consumes is prose-level, not code-level: batch 2's override text names
`_status.append_fork_fallback_log(status_path, scope, round, timestamp)` and
`_status.read_fork_fallback_log(status_path)` as the calls the mill-go2 Builder makes, so those two
names and their argument orders must be final when this batch closes.

Batch-local decisions beyond `## Shared Decisions`: the new code is a deliberate near-copy of the
existing `append_inferred_success_log` / `_find_inferred_success_log_block` pair rather than a
generalised refactor of all three audit logs. Extracting a shared parametrised locator would touch
two already-shipped helpers with live callers for no behavioural gain, which is out of scope here.

## Cards

### Card 1: Specify both fork-fallback-log helpers in test-status.py

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Write these tests before card 2 exists;
  they are expected to fail on import until card 2 lands.

  Extend the existing `from _status import (...)` block with `append_fork_fallback_log` and
  `read_fork_fallback_log`, keeping the block's alphabetical order (`append_fork_fallback_log`
  immediately before `append_inferred_success_log`; `read_fork_fallback_log` immediately before
  `read_full`).

  Add the new cases inside `main()`'s existing `try:` body, after the final
  `append_inferred_success_log` case and before the closing
  `print("All _status unit tests passed.")` line. Follow the file's established shape exactly:
  a `tempfile.TemporaryDirectory()` per case, `render_initial(...)` to seed the file, bare `assert`
  with a message, and one `print("PASS: ...")` per case. Bind `ts_ff = "2026-08-11T10:00:00Z"` as
  this group's base timestamp, mirroring the existing `ts_rl` / `ts_is` convention.

  Six cases for `append_fork_fallback_log(status_path, scope, round, timestamp)`, mirroring the
  `append_inferred_success_log` template case-for-case:

  1. Lazy section creation on first call — assert `"## Fork-fallback log"` is absent from
     `render_initial`'s output, call the helper with scope `"batch-a"` and round `1`, then locate the
     heading, the opening `` ```text `` fence and its closing fence by index and assert the fenced
     body equals exactly `[f"{quote_scalar(ts_ff)}  batch-a  round 1"]`.
  2. Append-only on second call — call again with scope `"holistic"`, round `2` and a later
     timestamp, then assert the body equals both rows in write order with the first row unchanged.
     This case also discharges the "cover both scope shapes" requirement, since it pairs a batch name
     with the literal `holistic`.
  3. Row format — on a fresh file, append with scope `"batch-a"` and round `3` and assert the
     substring `"batch-a  round 3"` is present in the file contents.
  4. Does not disturb `## Timeline` or the yaml block's `phase:` — capture `read_full(sp)` before and
     after one append, and assert both `["yaml"]["phase"]` and `["timeline"]` are unchanged. This is
     the case that locks the discussion-review round-1 BLOCKING finding and is the reason the helper
     exists instead of an `append_phase` call;
     say so in a comment above the case.
  5a. `ValueError` when the heading is present but there is no fenced block — append
     `"\n## Fork-fallback log\n"` to a rendered file, then assert the call raises.
  5b. `ValueError` when the fenced block is unterminated — append
     ``"\n## Fork-fallback log\n\n```text\n"``, then assert the call raises.

  Five cases for `read_fork_fallback_log(status_path)`:

  6. Absent section returns `[]` and does not raise — call it on a file straight out of
     `render_initial`. This is the common path the `fork_attempted` predicate hits every
     non-fallback round.
  7. Round-trip — append `("batch-a", 1)` and `("holistic", 2)`, read them back, and assert both are
     present with scope and round intact. Compare as a set of `(scope, round)` pairs built from the
     returned dicts rather than asserting list order, which is explicitly not contractual.
  8. `round` is returned as an `int`, not the string it is stored as — assert
     `isinstance(entry["round"], int)` for a read-back row.
  9. Exact-match discrimination — append `("batch-a", 1)`, `("batch-a", 2)` and `("batch-b", 1)`,
     read back, and assert the pair set is exactly those three. This is the assertion that stops the
     predicate false-positiving across rounds of the same scope or scopes of the same round.
  10. A line inside the fence that does not match the row format is skipped rather than raising —
      append one real row, then hand-insert a junk line into the fenced block, and assert the read
      returns only the real row.

- **Commit:** `test(status): specify fork-fallback log helpers`

### Card 2: Add append_fork_fallback_log and read_fork_fallback_log to _status.py

- **Context:**
  - `plugins/mill/unit_tests/test-status.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `_FORK_FALLBACK_LOG_HEADING = "## Fork-fallback log"` alongside the existing
  `_RECOVERY_LOG_HEADING` and `_INFERRED_SUCCESS_LOG_HEADING` constants.

  At the end of the module, under a new `# Fork-fallback log` banner comment matching the existing
  `# Inferred-success log` banner's shape, add:

  - `_find_fork_fallback_log_block(lines: list[str]) -> tuple[int, int, int, int] | None` — a direct
    copy of `_find_inferred_success_log_block` with `_FORK_FALLBACK_LOG_HEADING` substituted for
    `_INFERRED_SUCCESS_LOG_HEADING`. Same return tuple, same `None`-when-absent contract, same two
    `ValueError` raises for a missing and an unterminated fence.
  - `append_fork_fallback_log(status_path: Path, scope: str, round: int, timestamp: str) -> None` —
    mirrors `append_inferred_success_log` line for line, differing only in the heading constant and
    the row format. Call `_require_path(status_path, "append_fork_fallback_log")` first;
    build the row as `f"{quote_scalar(timestamp)}  {scope}  round {round}"`;
    lazily create the section at end-of-file when `_find_fork_fallback_log_block` returns `None`,
    otherwise insert the row immediately before the closing fence.
  - `read_fork_fallback_log(status_path: Path) -> list[dict]` — returns one dict per parsed row with
    keys `scope` (`str`) and `round` (`int`). Call `_require_path` first, read and `splitlines()` the
    file, then call `_find_fork_fallback_log_block`. Return `[]` when it returns `None`;
    let its two `ValueError`s propagate unchanged. Iterate the lines strictly between the opening and
    closing fence indices, match each against a module-level
    `_FORK_FALLBACK_ROW_RE = re.compile(r"^\S+\s\s(?P<scope>.+?)\s\sround\s(?P<round>\d+)\s*$")`,
    skip non-matching lines silently, and build each dict with `int(match.group("round"))`.

  Both new public helpers get a full docstring in the module's existing style. The
  `read_fork_fallback_log` docstring must state that this section, unlike
  `## Tracked-file recovery log` and `## Inferred-success log`, is control-flow state rather than a
  write-only audit trail: the mill-go2 fixer override reads it to reconstruct its `fork_attempted`
  predicate, so the reader must not be removed as dead code. State the guarantee's scope exactly as
  Shared Decision `fork-fallback-log-is-control-flow-state` frames it — the reader keeps a recorded
  fallback cold across a resume;
  it does not make forking idempotent across a crash that happens before any fallback is recorded.
  The
  `append_fork_fallback_log` docstring must state that the row is committed before the cold retry is
  issued, and that this ordering is what makes the reconstruction available when it is needed.

  Add both helpers to the module docstring's `Public API:` list, immediately after the existing
  `append_inferred_success_log` line, using the same `name(args) -> return` shorthand:
  `append_fork_fallback_log(status_path, scope, round, timestamp) -> None` and
  `read_fork_fallback_log(status_path) -> list[dict]`.

  Do not refactor `_find_recovery_log_block` or `_find_inferred_success_log_block` into a shared
  parametrised locator, and do not touch any existing function.

- **Commit:** `feat(status): add fork-fallback audit log helpers`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-status.py`, the single standalone runner that owns every
`_status.py` assertion. It is scoped to exactly the file this batch changes — no `run-all.py` sweep is
needed, since `_status.py`'s new helpers are purely additive and no existing caller is touched.

The eleven new cases split into the six `append_fork_fallback_log` cases mirroring the
`append_inferred_success_log` template (lazy creation, append-only, row format, `phase:`/`## Timeline`
preservation, and the two malformed-fence `ValueError` cases) and the five
`read_fork_fallback_log` cases specifying the reader from scratch (absent section, round-trip,
`int` round, exact-match discrimination across scope and round, and lenient row skipping). The
`phase:`-preservation case is the load-bearing one: it is the regression lock for the discussion
review round-1 BLOCKING finding that made an `append_phase` call unusable here.
