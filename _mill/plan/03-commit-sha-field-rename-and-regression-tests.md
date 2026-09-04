# Batch: commit-sha-field-rename-and-regression-tests

```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
batch: commit-sha-field-rename-and-regression-tests
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

This batch closes GitHub issue #953 and adds a targeted regression test for
#932. Root cause (#953): `millpy-merge-in-subagent.py`'s conflicts-mode success
path, at both its `--stage finalize` branch and its full-mode return, funnels
through `_implementer_common.py`'s `_forward_output` generic fallback, which
does an unconditional `git rev-parse HEAD` and labels the result `commit_sha` —
but at that point in the documented mill-merge-in flow, `git merge --continue`
has not yet run, so `HEAD` is still the pre-merge commit, not a merge commit.
The field name misleadingly implies a completed commit reference. This batch
adds an optional `commit_sha_field_name` parameter (Cards 3-4) so only the two
conflicts-mode call sites rename the field to `pre_merge_head`; every other
caller (the batch/card success path, `millpy-fix.py`) is untouched and keeps
emitting `commit_sha` under the default. Cards 5-6 add regression tests: one
pinning the new override (and, via #932, that a self-reported truncated SHA is
still discarded and replaced by the real 40-char `git rev-parse HEAD` value on
the default path), and one pinning the conflicts-mode field rename at both call
sites. Card order within this batch matters: Cards 4, 5, and 6 all depend on
Card 3's new parameter existing.

## Cards

### Card 3: Add `commit_sha_field_name` parameter to `_forward_output` / `finalize_from_output`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_forward_output`'s signature, add a new keyword-only parameter
  `commit_sha_field_name: str = "commit_sha",` immediately after the existing
  last parameter `batch_verify_baseline: list[str] | None = None,` (i.e. it
  becomes the new last parameter before the closing `) -> int:`).

  In `finalize_from_output`'s signature, add the identical parameter
  `commit_sha_field_name: str = "commit_sha",` in the same position (immediately
  after its own `batch_verify_baseline: list[str] | None = None,`). Add a
  one-line `Args:` docstring entry for it, mirroring the style of the existing
  entries (e.g. `session_id: Session identifier threaded into the output
  envelope.`) — something like `commit_sha_field_name: JSON key the corrective
  SHA is attached under on the success fallback path; defaults to
  "commit_sha".` In `finalize_from_output`'s body, thread the new parameter into
  its `_forward_output(...)` call by adding
  `commit_sha_field_name=commit_sha_field_name,` as the new last keyword
  argument (after the existing `batch_verify_baseline=batch_verify_baseline,`).

  In `_forward_output`'s body, locate the unconditional success-path fallback
  block — the one guarded by `if parsed.get("status") == "success":` that runs
  `git rev-parse HEAD` and, on a valid result, does
  `parsed["commit_sha"] = result.stdout.strip()` inside the `if
  result.returncode == 0 and _is_valid_commit_sha(result.stdout.strip()):`
  branch (this is the block directly preceded by the comment beginning `# The
  corrective git rev-parse HEAD / _is_valid_commit_sha block below only ever
  applies to a self-reported status: success`). Change that one line from
  `parsed["commit_sha"] = result.stdout.strip()` to
  `parsed[commit_sha_field_name] = result.stdout.strip()`.

  Do not modify any other `commit_sha`-writing site in this file — not
  `_attach_commit_sha`, not the verify/transient/incomplete gate-result sites
  (`gate_result["commit_sha"] = ...`), not the Go build-tag retiering or
  completeness sites, not the inferred-success `git rev-parse HEAD` sites in the
  `try:` block below the `if parsed is not None:` branch. Those remain
  hardcoded to `"commit_sha"` — this parameter only controls the one fallback
  block named above.
- **Commit:** `feat(implementer-common): add commit_sha_field_name override to the success-path SHA fallback`

### Card 4: Point conflicts-mode call sites at `pre_merge_head`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `--stage finalize` handling for `args.mode == "conflicts"`, the call
  `return finalize_from_output(Path(args.agent_output), project_root,
  start_sha=None, snapshot_path=None, session_id=None,)` — add
  `commit_sha_field_name="pre_merge_head",` as an additional keyword argument to
  this call (it becomes the new last argument before the closing paren).

  In `_run_conflicts`'s full-mode return, `return _forward_output(output,
  project_root)` — change it to `return _forward_output(output, project_root,
  commit_sha_field_name="pre_merge_head")`.

  Do not modify `_run_verify_fix`'s finalize-stage or full-mode success
  responses (the `print(json.dumps({"status": "success", "commit_sha": sha}))`
  literals) — verify-fix mode's `commit_sha` is reported after a real commit
  already exists (post-fixer or clean-verify), so its field name is already
  accurate; it is out of scope for this batch.
- **Commit:** `fix(merge-in-subagent): emit pre_merge_head instead of commit_sha for conflicts-mode success`

### Card 5: Regression tests for the field-name override and #932's truncation fix

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add two new cases to `main()`, inserted after the existing `# Case 77: ...`
  block and before the final `if errors:` block, following the file's existing
  numbered-case convention (one `with tempfile.TemporaryDirectory():` block per
  case, `try:`/`except Exception as exc:` with a `FAIL: case N (...)` message
  and `errors += 1` on failure, a `PASS: ...` print on success).

  **Case 78** (`commit_sha_field_name` override): model the fixture exactly on
  the existing `# Case 21: verify_cmd=None, parsed success -> success preserved
  (backward compat)` block — same `_setup_fixture`, same empty second commit,
  same `git rev-parse HEAD` capture of `new_head` after that commit (see Case 1
  or Case 9 for the `new_head` capture pattern), same
  `agent_output = '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'`.
  Call `_forward_output(agent_output, project_root, start_sha=base_sha,
  snapshot_path=snapshot_path, verify_cmd=None,
  commit_sha_field_name="pre_merge_head")`. Assert `data["status"] ==
  "success"`, assert `"commit_sha" not in data` (the default key must NOT
  appear), and assert `data["pre_merge_head"] == new_head` (the real HEAD SHA,
  not the self-reported `"abc"`).

  **Case 79** (#932 regression — truncated self-reported SHA is discarded):
  same fixture shape as Case 78 (fresh `_setup_fixture`, empty second commit,
  `new_head` captured via `git rev-parse HEAD`), but this time set
  `agent_output = '{"status":"success","commit_sha":"' + new_head[:-1] +
  '","session_id":"test-session"}\n'` — a deliberately 39-character
  self-reported SHA (one short of `new_head`'s 40), reproducing #932's exact
  reported shape. Call `_forward_output(agent_output, project_root,
  start_sha=base_sha, snapshot_path=snapshot_path, verify_cmd=None)` — default
  `commit_sha_field_name` (omit the parameter entirely). Assert `data["status"]
  == "success"` and assert `data["commit_sha"] == new_head` (the full 40-char
  value from `git rev-parse HEAD`, proving the truncated self-reported value is
  discarded and replaced, not passed through).
- **Commit:** `test(implementer-common): pin commit_sha_field_name override and #932 truncation-correction behavior`

### Card 6: Regression tests for the conflicts-mode field rename at both call sites

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add two new test methods to `TestMillpyMergeInSubagent`, following this
  file's existing naming convention (e.g. `test_20_...`, `test_21_...`).

  **`test_20_conflicts_finalize_emits_pre_merge_head`**: model this on the
  existing `test_15_stage_finalize_conflicts` method exactly (same
  `agent_output_path` fixture writing `'{"status":"success","commit_sha":"xyz"}\n'`,
  same `unittest.mock.patch.object(millpy_merge_in_subagent._implementer_claude,
  "run")` and `unittest.mock.patch.object(_implementer_common._subprocess_util,
  "run", side_effect=_clean_gate_side_effect)` context managers, same
  `self._run_main([...])` call with `--mode conflicts --files f.py --stage
  finalize --agent-output <path>`). Instead of `test_15`'s single
  `self.assertEqual(data["status"], "success")`, additionally assert
  `self.assertNotIn("commit_sha", data)` and
  `self.assertEqual(data["pre_merge_head"], "a" * 40)` — `_clean_gate_side_effect`
  returns `"a" * 40 + "\n"` for every `git rev-parse` call, per its own
  docstring, so that is the value the fallback block attaches.

  **`test_21_conflicts_full_mode_emits_pre_merge_head`**: model this on the
  existing `test_17_conflicts_success_no_discarded_is_clean` method exactly
  (same `unittest.mock.patch.object(millpy_merge_in_subagent._render, "render",
  return_value="rendered")`, same
  `unittest.mock.patch.object(millpy_merge_in_subagent._implementer_claude,
  "run", return_value=('{"status":"success"}\n', "fake-session"))`, same
  `unittest.mock.patch.object(_implementer_common._subprocess_util, "run",
  side_effect=_clean_gate_side_effect)`, same `self._run_main(["--mode",
  "conflicts", "--files", "a.py"])` full-mode call). Assert `data["status"] ==
  "success"`, `self.assertNotIn("commit_sha", data)`, and
  `self.assertEqual(data["pre_merge_head"], "a" * 40)`.

  Both new tests assert the *field name*, not a real pre/post-`merge
  --continue` git state — this fixture (`_clean_gate_side_effect`) mocks
  `_subprocess_util.run` entirely and never operates against a real git
  repository with an actual `MERGE_HEAD`, so there is no real merge state to
  distinguish here. What is being pinned is that both conflicts-mode call sites
  use the renamed field, which is the actual bug from #953.
- **Commit:** `test(merge-in-subagent): pin pre_merge_head field name at both conflicts-mode call sites`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python
plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
test-millpy-merge-in-subagent.py`. This covers both edited/created test files:
`test-implementer-common.py` (Cards 3, 5 — the new `commit_sha_field_name`
parameter and its default-path regression coverage) and
`test-millpy-merge-in-subagent.py` (Cards 4, 6 — the two conflicts-mode call
sites). Scoped to exactly these two files rather than the full suite, per the
"Verify command scope" convention — neither `_forward_output` nor
`millpy-merge-in-subagent.py` is a cross-cutting helper every other test file
imports.
