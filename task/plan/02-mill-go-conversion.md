# Batch: mill-go-conversion

```yaml
task: Replace uv-run-project with direct venv Python in SKILL.md invocations
batch: mill-go-conversion
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

mill-go is the only mill skill that uses `$PLUGIN_ROOT` (a local alias set at the top of Step 0) instead of `${CLAUDE_PLUGIN_ROOT}` directly. It is also the only skill with nested `millpy-bg.py` invocations where one Python call passes a second Python call as argv after `--`. Both characteristics require special handling not covered by Batch 1's mechanical rules:

- Step 0 must define a new `MILL_PYTHON` variable so the body calls have a stable handle to the venv binary.
- The Step 0 fallback block needs an operator-facing note that the source-tree venv must exist when `CLAUDE_PLUGIN_ROOT` is unset.
- Direct (top-level) calls in the body get the `PYTHONPATH="${PLUGIN_ROOT}/scripts"` prefix.
- Nested calls (the inner command after `--` inside a `millpy-bg.py` line) MUST NOT carry the `PYTHONPATH=` prefix — see the Shared Decision `nested-call-exception`.

This batch touches only `plugins/mill/skills/mill-go/SKILL.md`. It does not change script files or wrap mill-go's logic. The cards split Step-0 modification (Card 2) from body-call conversion (Card 3) because they are distinct in shape — Card 2 ADDS lines; Card 3 REWRITES existing lines — and splitting them makes the diff and the review easier to follow.

## Cards

### Card 2: Add `MILL_PYTHON` variable and fallback note to mill-go Step 0

- **Context:**
  - `task/discussion.md`
  - `task/plan/00-overview.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Locate the Step 0 block at the top of mill-go SKILL.md (the bash block introduced by "**Step 0: Resolve `PLUGIN_ROOT`.**" — currently containing the lines `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"`, the `if [ -z "$PLUGIN_ROOT" ]` fallback, and a closing `fi`).

  Modify that block so it reads exactly:

  ```bash
  PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
  if [ -z "$PLUGIN_ROOT" ]; then
      PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
      echo "[mill-go] CLAUDE_PLUGIN_ROOT unset; resolved to: $PLUGIN_ROOT"
      echo "[mill-go] NOTE: source-tree venv must exist at $PLUGIN_ROOT/.venv — run 'uv sync --project $PLUGIN_ROOT' if not."
  fi
  MILL_PYTHON="${PLUGIN_ROOT}/.venv/Scripts/python.exe"
  ```

  Two concrete mutations:
  1. ADD a new `echo` line inside the `if`-block (after the existing `echo "[mill-go] CLAUDE_PLUGIN_ROOT unset; resolved to: $PLUGIN_ROOT"` line) that warns about the source-tree venv requirement, with the exact text shown above.
  2. ADD a new line `MILL_PYTHON="${PLUGIN_ROOT}/.venv/Scripts/python.exe"` AFTER the closing `fi`. This line is unconditional — it always runs.

  Do not touch any other line in the file in this card. Do not convert the body calls (that is Card 3).

- **Commit:** `refactor(mill-go): introduce MILL_PYTHON variable in Step 0`

### Card 3: Convert all mill-go body invocations to use `$MILL_PYTHON`

- **Context:**
  - `task/discussion.md`
  - `task/plan/00-overview.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  After Card 2 has run, locate every body invocation of the form `uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/<script>.py"` (and the braced-variable variant `"${PLUGIN_ROOT}"`) in mill-go SKILL.md. There are approximately 22 such occurrences.

  Two distinct shapes appear, and they convert differently:

  **Shape A — direct call (top-level shell line, NOT after `--`).**

  Replace
  ```
  uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/<script>.py" [args]
  ```
  with
  ```
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/<script>.py" [args]
  ```

  Preserve trailing arguments and any line-continuation backslashes.

  **Shape B — nested call (the command after `--` inside a `millpy-bg.py` launcher line).**

  Replace
  ```
  uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/<script>.py" [args]
  ```
  with
  ```
  "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/<script>.py" [args]
  ```

  This shape MUST NOT carry the `PYTHONPATH=` prefix. Rationale: tokens after `--` are passed as argv to `subprocess.run` inside the millpy-bg worker; the shell does not parse `PYTHONPATH=...` as an env assignment in that position. The outer launcher (the Shape A `millpy-bg.py` line that preceded the `--`) already set PYTHONPATH in the process environment; it is inherited automatically.

  **Identifying Shape A vs Shape B:** Every multi-line bg invocation in mill-go has the pattern
  ```bash
  uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/millpy-bg.py" \
      --slug <slug> -- \
      uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/<inner-script>.py" [args]
  ```
  The first `uv run` line (the one calling `millpy-bg.py`) is Shape A and becomes:
  ```bash
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug <slug> -- \
      "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/<inner-script>.py" [args]
  ```
  The second `uv run` line (the one after `-- \`) is Shape B — no PYTHONPATH= prefix.

  **Standalone (non-bg) body calls** — e.g. `uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/millpy-builder-lock.py" acquire <slug>` — are Shape A: they are top-level shell lines, not after a `--`, so they get the PYTHONPATH prefix.

  **DO NOT TOUCH:**
  - The Step 0 block (modified by Card 2; leave its post-Card-2 form intact).
  - Any line that does not match the `uv run --project "$PLUGIN_ROOT" ...` pattern.
  - Prose paragraphs and headings; modify only fenced ```bash blocks.

  Post-edit invariant: `grep -E 'uv run --project ["]?\$\{?PLUGIN_ROOT\}?["]?' plugins/mill/skills/mill-go/SKILL.md` returns zero matches. The literal token `$MILL_PYTHON` appears in every former `uv run --project "$PLUGIN_ROOT"` location.

- **Commit:** `refactor(mill-go): convert body invocations to direct venv Python via MILL_PYTHON`

## Batch Tests

This is a documentation-only batch; `verify: null`.

Verification is mechanical and performed by the implementer after applying both cards:

1. `grep -E 'uv run --project ["]?\$\{?PLUGIN_ROOT\}?["]?' plugins/mill/skills/mill-go/SKILL.md` — expected zero matches.
2. `grep -n '\$MILL_PYTHON' plugins/mill/skills/mill-go/SKILL.md` — expected ≥22 matches (every former `uv run --project "$PLUGIN_ROOT" "$PLUGIN_ROOT/scripts/..."` site now uses `$MILL_PYTHON`).
3. `grep -n 'MILL_PYTHON=' plugins/mill/skills/mill-go/SKILL.md` — expected exactly one match (the Step 0 definition line added by Card 2).
4. `grep -n 'source-tree venv must exist' plugins/mill/skills/mill-go/SKILL.md` — expected exactly one match (the new echo line in Card 2's fallback block).
5. For every line in the file that contains both `"$MILL_PYTHON"` and is preceded by a line ending in `-- \`, confirm that line does NOT begin with `PYTHONPATH=` (Shape B nested-call rule).
6. For every line in the file that contains `"$MILL_PYTHON"` and is a top-level shell line (not preceded by a line ending in `-- \`), confirm the line begins with `PYTHONPATH="${PLUGIN_ROOT}/scripts"` (Shape A direct-call rule).
