# Batch: Python noise removal

```yaml
task: Silence verbose review log lines cluttering orchestrator output
batch: Python noise removal
number: 1
cards: 3
verify: "uv run --project plugins/mill python unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Remove unconditional informational `print(..., file=sys.stderr)` calls from three Python modules: `_llm_claude.py` (3 blocks), `_review_code.py` (2 blocks), and `_review_discussion.py` (2 blocks). These are fire-on-every-call progress lines that accumulate noise in the bg-process log that the orchestrator polls. Error, warning, and rate-limit prints in all three modules are preserved. No interface changes; callers are unaffected.

## Cards

### Card 1: Remove progress prints from `_llm_claude.py`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Remove three `print(..., file=sys.stderr)` blocks from `_llm_claude.py`. Do not alter any surrounding logic, variable assignments, or blank lines beyond removing the `print(...)` statement itself (which may span multiple lines).

  Block 1 — the shared "starting..." print just before the psmux/non-psmux branch (currently lines 299–302), along with the two preceding variable assignments that exist solely to feed it (currently lines 297–298):
  ```python
  sess_label = f" session={session_id[:8]}..." if session_id else ""
  mode_suffix = "/resume" if resume else ""
  print(
      f"[_llm_claude] claude {model} ({mode_label}{mode_suffix}){sess_label} starting...",
      file=sys.stderr,
  )
  ```

  Block 2 — the psmux-path "returned N chars" print after `text = result.stdout.rstrip()` (currently lines 340–344):
  ```python
  print(
      f"[_llm_claude] claude {model} returned {len(text)} chars in {dt:.1f}s"
      f" session={sid_log}",
      file=sys.stderr,
  )
  ```

  Block 3 — the non-psmux-path "returned N chars" print after `sid_log = ...` (currently lines 395–399); identical literal content to block 2 but in the non-psmux branch.

  **Keep** (do not remove):
  - The "fast-fail retry" print (~lines 371–374) — fires only when returncode != 0 and dt < 2.0.
  - The unparseable stream-json warning (~lines 235–237).
  - The "killed psmux session" cleanup print (~lines 544–546).
- **Commit:** `chore(_llm_claude): remove noisy progress prints from bg log`

### Card 2: Remove progress prints from `_review_code.py`

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Remove two `print(..., file=sys.stderr)` blocks from `_review_code.py`. Do not alter any surrounding logic beyond removing the `print(...)` statement itself.

  Block 1 — the entry print fired on every review invocation (currently lines 217–220):
  ```python
  print(
      f"[_review_code] slug={slug!r} round={round_n} scope={scope_label}",
      file=sys.stderr,
  )
  ```

  Block 2 — the completion print fired on every review write (currently lines 444–447):
  ```python
  print(
      f"[_review_code] wrote {path.name} verdict={verdict}",
      file=sys.stderr,
  )
  ```

  **Keep** (do not remove):
  - The `rounds=0` disabled-stub print (~line 203).
  - The "warning: start_sha" print (~lines 242–247).
  - The "warning: no source files" print (~lines 271–275).
  - The `NEED_CONTEXT` retry print (~line 387).
  - The `parse_verdict failed` error print (~line 465).
- **Commit:** `chore(_review_code): remove noisy entry and completion prints from bg log`

### Card 3: Remove progress prints from `_review_discussion.py`

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Remove two `print(..., file=sys.stderr)` blocks from `_review_discussion.py`. Do not alter any surrounding logic beyond removing the `print(...)` statement itself.

  Block 1 — the entry print fired on every review invocation (currently lines 81–84):
  ```python
  print(
      f"[_review_discussion] slug={slug!r} round={round_n}",
      file=sys.stderr,
  )
  ```

  Block 2 — the completion print fired on every review write (currently lines 168–171):
  ```python
  print(
      f"[_review_discussion] wrote {review_file.name} verdict={verdict}",
      file=sys.stderr,
  )
  ```

  **Keep** (do not remove):
  - The `rounds=0` disabled print at lines 65–68.
- **Commit:** `chore(_review_discussion): remove noisy entry and completion prints from bg log`

## Batch Tests

The verify command `uv run --project plugins/mill python unit_tests/run-all.py` runs the full unit test suite from the worktree root. No existing tests assert on the removed stderr lines (tests use `sys.stderr` only for FAIL output; they do not capture these modules' own stderr). The suite verifies that callers of `_llm_claude`, `_review_code`, and `_review_discussion` remain unaffected by the removals.
