# Batch: implementer-commit-sha-validation

```yaml
task: 'Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports'
batch: implementer-commit-sha-validation
number: 4
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Closes the one confirmed gap in `_implementer_common.py::_forward_output`'s already-mostly-correct `commit_sha` override — a failed or malformed `git rev-parse HEAD` result can currently pass an agent's raw self-reported `commit_sha` through unvalidated on the parsed-success path — and tightens the ambiguous `<last-HEAD-sha>` wording across all four brief templates that source that value. One batch: the validator, its guarded call site, and its direct-plus-integration test coverage share one file; the brief-template wording tightening is cheap defense-in-depth for the same bug and has no separate test surface of its own (no existing test asserts on the placeholder wording). No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 9: Add a hex-SHA validator and guard the unconditional commit_sha override

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Near `_attach_commit_sha` (~line 385), add a module-level `_COMMIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")` and a function `_is_valid_commit_sha(value: str) -> bool` returning `bool(_COMMIT_SHA_RE.match(value))`. `re` is already imported at the top of the file — no new import needed.
  - In `_forward_output`, locate the unconditional success-path override at ~lines 1648-1660:
    ```python
    result = _subprocess_util.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
    )
    if result.returncode == 0:
        parsed["commit_sha"] = result.stdout.strip()
        violations = _cleanliness.compute_scope_violations(project_root, git_root)
        if violations:
            parsed["scope_violations"] = violations
        print(json.dumps(parsed))
    else:
        print(json.dumps(parsed))
    return 0
    ```
    Change the `if` condition to `if result.returncode == 0 and _is_valid_commit_sha(result.stdout.strip()):` (the success/passthrough branch is unchanged otherwise). Change the `else` branch so it no longer prints `parsed` unmodified — instead print a stuck envelope: `{"status": "stuck", "stuck_type": "logic", "reason": "commit_sha correction failed: git rev-parse HEAD did not return a well-formed SHA", "session_id": session_id or parsed.get("session_id") or "unknown"}`. Both branches keep `return 0` unchanged.
- **Commit:** `fix(implementer-common): never pass through an unvalidated commit_sha on success`

### Card 10: Add direct validator coverage and _forward_output regression tests

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `_is_valid_commit_sha` to the existing `from _implementer_common import (...)` block (~line 18).
  - Append three new "Case" blocks to `main()` immediately before the final `if errors:` check (after Case 67, ~line 4499), following this file's existing `# Case N: <description>` / `with tempfile.TemporaryDirectory() as tmpdir: ... try/except` structure:
    - **Case 68** (`commit_sha correction still applies to an abbreviated self-report`): build a fixture via `_setup_fixture(project_root)` then a second commit (mirrors Case 21's setup at ~line 850-860, capturing the real new-HEAD SHA via `git -C <project_root> rev-parse HEAD`); call `_forward_output('{"status":"success","commit_sha":"abc","session_id":"test-session"}\n', project_root, start_sha=None, verify_cmd=None)`; assert the returned JSON's `commit_sha` equals the fixture's real new-HEAD SHA (not the self-reported `"abc"`).
    - **Case 69** (`corrective git rev-parse HEAD failure is not silently passed through`): same fixture setup as Case 68; patch `_subprocess_util.run` with a `side_effect` (mirroring the `_go_gate_mock`-style pattern already in this file, ~line 45-67: delegate every non-matching call to the real `_subprocess_util.run`) that intercepts calls where `argv == ["git", "rev-parse", "HEAD"]` and `kwargs.get("cwd") == project_root`, returning `subprocess.CompletedProcess(argv, 1, "", "fatal: not a git repository")` for those and the real result for everything else; call `_forward_output` with the same abbreviated-`commit_sha` JSON from Case 68, `start_sha=None`, `verify_cmd=None`; assert the result's `status == "stuck"`, `stuck_type == "logic"`, and that the literal string `"abc"` does not appear anywhere in the captured JSON output.
    - **Case 70** (`_is_valid_commit_sha direct coverage`): assert `_is_valid_commit_sha` returns `True` for a 40-character lowercase hex string and a 64-character lowercase hex string; returns `False` for a 7-character abbreviated SHA, a 40-character string containing an uppercase hex character, a 40-character string containing a non-hex character (e.g. `"g"`), and the empty string.
- **Commit:** `test(implementer-common): cover commit_sha validation and the guarded override`

### Card 11: Tighten the `<last-HEAD-sha>` wording in all four brief templates

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/templates/fixer-batch-brief.md`
  - `plugins/mill/templates/fixer-holistic-brief.md`
  - `plugins/mill/templates/merge-in-verify-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In each of the four templates, add the sentence **"`commit_sha` MUST be the full SHA from `git rev-parse HEAD` -- never the abbreviated form (`git rev-parse --short HEAD`) or a `git log --oneline` hash."** at the stated insertion point, without altering the `<last-HEAD-sha>` / `<HEAD-sha, unchanged from before this turn>` placeholder tokens themselves anywhere in any of the four files:
  - `implementer-brief.md`: insert as a new paragraph immediately after the existing `**\`commit_sha\` MUST be a real content commit distinct from the batch start commit.**...` paragraph (~line 112).
  - `fixer-batch-brief.md`: insert as a new paragraph immediately after the existing `**\`commit_sha\` MUST be a real new content commit distinct from the fix-round housekeeping commit**...` paragraph (~line 79).
  - `fixer-holistic-brief.md`: insert as a new paragraph immediately after the existing `**\`commit_sha\` MUST be a real new content commit distinct from the holistic fix housekeeping commit**...` paragraph (~line 85).
  - `merge-in-verify-brief.md`: this template has no equivalent existing `commit_sha` paragraph — insert the sentence as a new paragraph immediately after the `## Report` heading's intro line ("Your last output line MUST be a bare JSON object (no code fence, no backticks):", ~line 35) and before the "On success:" line.
- **Commit:** `docs(briefs): require full git rev-parse HEAD for commit_sha`

## Batch Tests

`verify:` runs `test-implementer-common.py` in full, covering Card 10's three new cases (68-70) alongside every existing `_forward_output`/`finalize_from_output` case in the file. Card 11's brief-template wording changes are prose-only and have no dedicated test surface in this repo (confirmed via grep: no test asserts on the `<last-HEAD-sha>` / `<HEAD-sha, unchanged...>` placeholder text) — they are exercised only by real agent dispatch, out of scope for unit verification.
