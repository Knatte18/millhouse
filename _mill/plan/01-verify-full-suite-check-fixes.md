# Batch: verify-full-suite-check-fixes

```yaml
task: "_plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch"
batch: verify-full-suite-check-fixes
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch fixes `_check_verify_full_suite`'s Go-test detection (compound-command false positive, `go -C <dir> test` false negative) and adds a `done_gate` exemption, per the `go-test-segment-scoping` and `done-gate-exemption` Shared Decisions. It touches only `plugins/mill/scripts/_plan_validate.py`, `plugins/mill/scripts/millpy-validate-plan.py`, and `plugins/mill/scripts/millpy-review-plan.py` — no test file changes (those are batch 2, which depends on this batch so its assertions target the finished behavior). The external interface the next batch consumes: `_plan_validate.run(...)` and `_check_verify_full_suite(...)` both accept a new optional keyword-only `done_gate: str | None = None` parameter; existing callers that omit it are unaffected (default preserves current behavior).

## Cards

### Card 1: Segment-scope the Go-test detection and add the done_gate exemption to `_check_verify_full_suite`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add two module-level regex constants immediately before the `_check_verify_full_suite` function definition (in the "verify-full-suite check" section, before line ~2363):

  ```python
  # Splits a verify: command on shell-operator boundaries so each invocation in a compound
  # command is scoped independently (fixes #961: a later segment's ./... wrongly attributed
  # to an earlier go test invocation).
  _RE_SHELL_OPERATOR = re.compile(r"&&|\|\||;")

  # Matches a `go test` invocation, allowing the Go 1.20+ `-C <dir>` flag (which must precede
  # the subcommand) between `go` and `test` (fixes #933: `go -C <dir> test ./...` was never
  # matched by the old literal `\bgo test\b` pattern). Deliberately narrow -- a generic
  # "any flags between go and test" pattern would misfire on unrelated commands like
  # `go get test/pkg`.
  _RE_GO_TEST_INVOCATION = re.compile(r"\bgo\s+(?:-C\s+\S+\s+)?test\b")
  ```

  In `_check_verify_full_suite`'s signature, add a new keyword-only parameter after `overview_path: Path,`:

  ```python
      *,
      done_gate: str | None = None,
  ```

  In the function's docstring `Args:` section, add a line documenting the new parameter after the `overview_path` entry: `done_gate: The hub's configured repo-wide gate command (pipeline.done_gate), or None. When a frontmatter's verify command exactly equals this string, no verify-full-suite finding is reported for it, regardless of which sub-check would otherwise match.`

  In the inner `_check_frontmatter` closure, immediately after the existing `if command is None: return None` line and before the `if "run-all.py" in command ...` block, insert the done_gate exemption:

  ```python
          if done_gate is not None and command == done_gate:
              return None
  ```

  Replace the existing go-test detection block:

  ```python
        if re.search(r"\bgo test\b.*\./\.\.\.", command) and "-run " not in command:
            return {
                "check": "verify-full-suite",
                "batch": batch_label,
                "card": None,
                "path": command,
                "message": (
                    "verify command invokes 'go test ./...' without a -run <pattern> filter; "
                    "scope it or document the cross-cutting-helper justification in ## Batch Tests"
                ),
            }
  ```

  with the segment-scoped version:

  ```python
          for segment in _RE_SHELL_OPERATOR.split(command):
              if (
                  _RE_GO_TEST_INVOCATION.search(segment)
                  and "./..." in segment
                  and "-run " not in segment
              ):
                  return {
                      "check": "verify-full-suite",
                      "batch": batch_label,
                      "card": None,
                      "path": command,
                      "message": (
                          "verify command invokes 'go test ./...' without a -run <pattern> filter; "
                          "scope it or document the cross-cutting-helper justification in ## Batch Tests"
                      ),
                  }
  ```

  Leave the `run-all.py`, `dotnet test`, and bare-pytest branches unchanged (both their code and their `message` text) — only the go-test branch changes shape, and only the exemption check is new above it.

  Update the function's own docstring one-line summary (the line starting "Flag verify: commands that invoke an unscoped full-suite runner...") to mention the done_gate exemption: append a new sentence "A verify command that exactly equals `done_gate` (when supplied) is exempt from every sub-check below." after the existing summary sentence.
- **Commit:** `fix(plan-validate): scope go-test detection to shell segments and add done_gate exemption`

### Card 2: Add `done_gate` to `run()` and thread it through the three existing call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_plan_validate.py`'s `run()` function signature, add a new keyword-only parameter after `parent_branch: str | None = None,`:

  ```python
      done_gate: str | None = None,
  ```

  In `run()`'s docstring `Args:` section, add a line after the `parent_branch` entry: `done_gate: The hub's configured pipeline.done_gate command, or None. Threaded to _check_verify_full_suite (see that function's own done_gate documentation).`

  Change `run()`'s call to `_check_verify_full_suite` (currently `errors.extend(_check_verify_full_suite(batch_files, project_root, overview_path))`) to pass the new parameter through:

  ```python
      errors.extend(_check_verify_full_suite(batch_files, project_root, overview_path, done_gate=done_gate))
  ```

  In `plugins/mill/scripts/millpy-review-plan.py`, at both existing `validate_run(...)` call sites (the two blocks that already pass `max_cards_per_batch=cfg.get("pipeline", {}).get("max_cards_per_batch", 10)` and `max_batch_context_tokens=cfg.get("pipeline", {}).get("max_batch_context_tokens", 120000)`), add a new keyword argument immediately after `max_batch_context_tokens=...,` at each call site:

  ```python
                      done_gate=cfg.get("pipeline", {}).get("done_gate"),
  ```

  In `plugins/mill/scripts/millpy-validate-plan.py`, change the existing call (`errors = _plan_validate.run(plan_dir, project_root, wiki_root=wiki_root, skip_checks=frozenset(args.skip_checks))`) to additionally pass `done_gate=cfg.get("pipeline", {}).get("done_gate")` as a new keyword argument. This file already loads `cfg` earlier in `main()` via `load_config(project_root, mill_dir)`, so no new config read is needed.
- **Commit:** `fix(plan-validate): thread pipeline.done_gate into every _plan_validate.run call site`

## Batch Tests

`verify:` re-runs the full existing `test-plan-validate.py` suite (no new tests in this batch — those land in batch 2, which depends on this one) to confirm the segment-scoping rewrite and the done_gate exemption introduce no regression in the existing go-test/dotnet/pytest/run-all.py `verify-full-suite` coverage, nor in any of the file's other ~130 test functions (`verify-not-isolated`, DAG checks, move checks, etc., all of which call the same `_plan_validate.run` entry point).
