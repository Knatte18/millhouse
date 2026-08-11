# Batch: status-fork-fallback-helper

```yaml
task: 'mill-go2: fork-based implementer dispatch'
batch: status-fork-fallback-helper
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
depends-on: []
```

## Batch Scope

This batch adds one new public helper to `plugins/mill/scripts/_status.py` — `append_fork_fallback_log` — plus its unit tests. It is a self-contained Python batch with no SKILL.md surface: nothing in it references mill-go2, and the helper is written so the sibling task `mill-go2-fork-fixer` can reuse it unchanged rather than re-adding it.

The helper is the third member of an existing family. `append_recovery_log` and `append_inferred_success_log` already implement the same shape — a lazily-created dedicated `## <Name> log` section holding an append-only fenced `text` block — and the new helper mirrors them deliberately rather than inventing a variant. The one behaviour that must not drift is that it never touches the top-level `phase:` field: that field is the routing state mill-go-base's entry phase-gate reads, and the review-round-1 BLOCKING finding this helper exists to answer was precisely that `append_phase` would overwrite it with a value the gate does not recognise.

The external interface batch 2 consumes is the function name and signature: `append_fork_fallback_log(status_path: Path, batch_name: str, timestamp: str) -> None`. Batch 2's `mill-go2/SKILL.md` text names it, and `test-skill-helper-drift.py` fails if it does not resolve, which is why batch 2 depends on this one.

Tests come first (card 1), implementation second (card 2), per the overview's tests-first Shared Decision.

## Cards

### Card 1: Unit tests for `append_fork_fallback_log`

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `append_fork_fallback_log` to the existing `from _status import (...)` import block at the top of the file, keeping the block alphabetically sorted (it goes immediately before `append_inferred_success_log`).

  Append a new `# --- append_fork_fallback_log tests ---` section inside `main()`, placed immediately after the existing `append_inferred_success_log` test section and immediately before the final `print("All _status unit tests passed.")` line. Model every test on the `append_inferred_success_log` block directly above it — same `tempfile.TemporaryDirectory()` / `render_initial(...)` fixture shape, same `heading_idx` / `fence_open_idx` / `fence_close_idx` body-slicing pattern, same one `print("PASS: ...")` per scenario.

  Five scenarios, all required:

  1. **Lazy section creation.** Assert the `render_initial` output does not pre-seed `## Fork-fallback log`. Call the helper once, then assert the heading now exists and that the fenced body is exactly one row equal to `f"{quote_scalar(ts)}  {batch_name}"`. This is also the assertion that pins the timestamp to `quote_scalar`, matching the quoted form the two sibling helpers produce — do not assert on the raw unquoted timestamp.
  2. **Append-only on a second call.** Call the helper a second time with a different batch name and timestamp, then assert the body is exactly `[first_row, second_row]` — the first row unchanged and the second appended, never a whole-section rewrite.
  3. **`phase:` is untouched.** Capture `read_full(sp)` before and after one call, and assert `after["yaml"]["phase"] == before["yaml"]["phase"]` and `after["timeline"] == before["timeline"]`. This assertion encodes the review-round-1 BLOCKING finding and must not be dropped or weakened.
  4. **Missing fenced block raises `ValueError`.** Append a bare `## Fork-fallback log` heading with no fence, call the helper, and assert `ValueError` is raised.
  5. **Unterminated fenced block raises `ValueError`.** Append the heading plus an opening fence with no closing fence, call the helper, and assert `ValueError` is raised.

  Every new `print()` string stays ASCII-only.
- **Commit:** `test(status): cover append_fork_fallback_log lazy-create, append-only, phase-safety, and malformed-section cases`

### Card 2: `append_fork_fallback_log` helper

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `append_fork_fallback_log(status_path, batch_name, timestamp) -> None` to the `Public API:` list in the module's top docstring, immediately after the existing `append_inferred_success_log(...)` entry and matching that list's argument-name-only signature style. Every public function in this module is listed there; omitting the new one would break the convention.

  Add the module-level constant `_FORK_FALLBACK_LOG_HEADING = "## Fork-fallback log"` to the existing constant block that already declares `_BATCHES_HEADING`, `_RECOVERY_LOG_HEADING`, and `_INFERRED_SUCCESS_LOG_HEADING`, placed immediately after `_INFERRED_SUCCESS_LOG_HEADING`.

  Add a new banner-comment section at the end of the module, after `append_inferred_success_log`, following the same `# ---------------------------------------------------------------------------` banner shape the two preceding sections use, with a one-line description naming it as the audit trail for mill-go2's cold-fallback-on-dead-fork path.

  In that section add `_find_fork_fallback_log_block(lines: list[str]) -> tuple[int, int, int, int] | None`, structurally identical to `_find_inferred_success_log_block` but scanning for `_FORK_FALLBACK_LOG_HEADING`: locate the heading, bound the section at the next `## ` line or EOF, find the opening `_TIMELINE_FENCE` and the closing ``` within that bound, return `(heading_idx, fence_open_idx, fence_close_idx, section_end_idx)`, return `None` when the heading is absent, and raise `ValueError` naming `_FORK_FALLBACK_LOG_HEADING` when the fence is missing or unterminated.

  Add `append_fork_fallback_log(status_path: Path, batch_name: str, timestamp: str) -> None`, mirroring `append_inferred_success_log`'s body exactly: call `_require_path(status_path, "append_fork_fallback_log")`, read and `splitlines()` the file, build `new_row = f"{quote_scalar(timestamp)}  {batch_name}"`, then either append a fresh `[_FORK_FALLBACK_LOG_HEADING, "", _TIMELINE_FENCE, new_row, "```"]` block (with a leading blank separator when the file does not already end in one) or `lines.insert(fence_close_idx, new_row)` into the located block, and write back with `"\n".join(lines) + "\n"`.

  The row carries no round number, unlike `append_inferred_success_log`. That is deliberate: at most one cold fallback occurs per batch for the implementer role, so a round column would name a dimension that cannot vary. State this in the docstring.

  The function must never touch the top-level `phase:` field, and must not call or modify `append_phase`, `set_blocked`, or any other existing function. Write a docstring in the same shape as `append_inferred_success_log`'s: what the section is, that it is created lazily and is append-only, that it is the caller's explicit separate audit-append step, an `Args:` block, and a `Raises:` block naming `ValueError`.
- **Commit:** `feat(status): add append_fork_fallback_log audit-append helper`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-status.py` directly — a single file, since that is the only test file this batch edits and `_status.py`'s coverage lives entirely there. The five new scenarios in card 1 are the batch's whole executable surface.

Cross-file coverage is deliberately not in this batch's own `verify:`. The overview's module-wide `verify:` re-runs `test-status.py` alongside `test-mill-go-variants.py`, `test-skill-helper-drift.py`, and `test-guards.py` at the batch boundary, which is where a regression from the new `_status.py` symbol would surface. Adding those three to this batch's `--only` list instead would trip `_plan_validate.py`'s `verify-unrelated-test-file` check, since this batch touches none of them.
