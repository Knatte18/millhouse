# Batch: verify-cwd-foundation

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: verify-cwd-foundation
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-dag.py
depends-on: []
```

## Batch Scope

Introduces `_plan_dag.parse_verify_field`, the single normalizer for the new `verify:` `{cwd, command}` mapping form (see the overview's "verify `cwd` field schema" Shared Decision), and updates `_plan_dag.iter_batch_verifies` to yield `(name, command, cwd)` 3-tuples through it instead of bare 2-tuples. This is the foundation batch every downstream verify-cwd batch (4, 5, 6, 7, 8) depends on — none of them may re-implement the string-vs-mapping branch themselves.

## Cards

### Card 10: Add parse_verify_field to _plan_dag.py

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `parse_verify_field(frontmatter: dict, hub_root: Path, git_root: Path) -> tuple[str | None, Path | None]` to `_plan_dag.py`. Read `verify = frontmatter.get("verify")`. Contract:
  - `verify` is `None`, or a string that is empty/whitespace-only after `.strip()`: return `(None, None)`.
  - `verify` is a non-empty string: return `(verify.strip(), None)` — `None` cwd means "caller uses its existing default", preserving today's behavior exactly.
  - `verify` is a `dict`: read `cwd_key = verify.get("cwd")` and `command = verify.get("command")`. If `command` is not a non-empty string after `.strip()`, raise `ValueError` (mapping missing `command`). If `cwd_key == "hub"`, return `(command.strip(), hub_root)`. If `cwd_key == "git_root"`, return `(command.strip(), git_root)`. Any other `cwd_key` value (including `None`/missing) raises `ValueError` (unrecognized `cwd` value) — the mapping form always requires an explicit `cwd`, unlike the string form's implicit default.
  - Any other type for `verify` (e.g. a list, int) raises `ValueError`.
  Document this contract in the function's docstring, including the deliberate fail-loud policy (no silent default) for malformed input.
- **Commit:** `feat(plan-dag): add parse_verify_field for the verify cwd mapping form (#604)`

### Card 11: Update iter_batch_verifies to yield 3-tuples

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `iter_batch_verifies(plan_dir: Path) -> list[tuple[str, str]]` to `iter_batch_verifies(plan_dir: Path, hub_root: Path, git_root: Path) -> list[tuple[str, str, Path | None]]`. Replace the existing `if isinstance(verify, str) and verify.strip(): commands.append((name, verify.strip()))` body with a call to `parse_verify_field(frontmatter, hub_root, git_root)`; when the returned command is not `None`, append `(name, command, cwd)` to `commands` (skip appending when command is `None`, preserving the existing skip-null/pure-docs-batch behavior exactly). Update the docstring's return-type description and the two new parameters.
- **Commit:** `feat(plan-dag): thread parse_verify_field through iter_batch_verifies (#604)`

### Card 12: Update test-plan-dag.py for the new signatures

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-dag.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update the existing `iter_batch_verifies` assertion (currently `commands == [("a", "pytest tests/a -q"), ("b", "pytest tests/b -q")]`) to call the new signature with a flat-layout fixture (`hub_root == git_root == plan_dir.parent` or equivalent) and assert the 3-tuple form `[("a", "pytest tests/a -q", None), ("b", "pytest tests/b -q", None)]` — `None` cwd for the plain-string form, matching Card 11's contract. Add a `parse_verify_field` TDD test with these cases: plain-string form returns `(command, None)`; `{cwd: hub, command: ...}` resolves to `(command, hub_root)`; `{cwd: git_root, command: ...}` resolves to `(command, git_root)`; an invalid `cwd` value raises `ValueError`; a mapping missing `command` raises `ValueError`; absent/`None`/empty-or-whitespace-only `verify` returns `(None, None)`.
- **Commit:** `test(plan-dag): cover parse_verify_field and the 3-tuple iter_batch_verifies (#604)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-dag.py` runs the full file, covering the updated `iter_batch_verifies` assertion and the new `parse_verify_field` cases from Card 12.
