# Batch: dotnet-verify-lock-retry

```yaml
task: "mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages"
batch: dotnet-verify-lock-retry
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes the finalize-stage (and any other dotnet verify call's) MSB3021/MSB3027 testhost-lock race
(GitHub #848, #860) in the single shared choke point every verify command funnels through:
`_implementer_common._run_verify_gate`. On Windows, when a `dotnet` verify command fails with an
MSB3021/MSB3027/"is locked by:" signature in its output, retry the same command once — after the
function's existing unconditional post-run `dotnet build-server shutdown` has already run — and
judge the retry's own exit code, rather than blindly treating the failure as benign. This covers
`millpy-implement.py --stage finalize` and `millpy-fix.py --stage finalize` for free (both funnel
through the same helper), plus any current or future module-wide/batch verify call. No other batch
depends on this one; it is fully independent of batch 2's baseline-teardown fix.

## Cards

### Card 1: Retry a racing dotnet verify command once after build-server shutdown

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level helper immediately after `_has_windows_cleanup_race_signature` (which
  ends at line 511) and before `_is_benign_windows_cleanup` (which starts at line 514), matching
  the same shape as the two existing signature helpers immediately above it:

  ```python
  def _has_dotnet_lock_race_signature(text: str) -> bool:
      """
      Check if text contains a dotnet build-server file-lock race signature (case-insensitive).

      Detects the MSB3021/MSB3027 testhost/MSBuild lock signature ("msb3021", "msb3027",
      "is locked by:") distinct from _has_windows_cleanup_race_signature's benign-cleanup
      signatures -- this signature triggers a retry-and-judge response, never a benign pass.

      Args:
          text: A string to check (e.g., a verify command's combined stdout+stderr).

      Returns:
          True if any dotnet-lock-race signature is present;
          False otherwise.
      """
      text_lower = text.lower()
      dotnet_lock_patterns = [
          "msb3021",
          "msb3027",
          "is locked by:",
      ]
      return any(pattern in text_lower for pattern in dotnet_lock_patterns)
  ```

  In `_run_verify_gate`, insert this paragraph into the docstring immediately after the existing
  paragraph that ends "...treats the non-zero exit as success and returns None." (the paragraph
  beginning "On Windows (sys.platform == \"win32\"), applies an additional gate:"):

  ```
      On Windows, when the command contains "dotnet" and the failure output matches a dotnet
      build-server file-lock signature (per _has_dotnet_lock_race_signature: MSB3021, MSB3027, or
      "is locked by:"), retries the same command once -- after the unconditional post-run shutdown
      below has already run. A passing retry returns None exactly like any other pass. A
      still-failing retry returns a stuck dict built from the retry's own output, with reason
      prefixed by "[retried once after dotnet build-server shutdown; still failing] ".
  ```

  Then replace the failure branch of `_run_verify_gate` (the block starting at
  `if result.returncode != 0:` and ending at the `return {"status": "stuck", ...}` closing brace)
  with:

  ```python
          if result.returncode != 0:
              output = result.stdout + result.stderr
              # On Windows, check if this is a benign cleanup-race with no test failure
              if sys.platform == "win32" and _is_benign_windows_cleanup(output):
                  return None
              retry_marker = ""
              if (
                  sys.platform == "win32"
                  and verify_cmd is not None
                  and "dotnet" in verify_cmd.lower()
                  and _has_dotnet_lock_race_signature(output)
              ):
                  # A stale build-server node from an earlier dotnet invocation in this
                  # worktree can still hold file handles into bin/obj when this command
                  # runs. The unconditional shutdown above already blocked until that
                  # process exited, so a bare re-run of the same command usually clears
                  # the race with no code changes (GitHub #848, #860).
                  retry_result = subprocess.run(
                      run_args,
                      capture_output=True,
                      text=True,
                      cwd=effective_cwd,
                      **run_kwargs,
                  )
                  if retry_result.returncode == 0:
                      return None
                  output = retry_result.stdout + retry_result.stderr
                  if sys.platform == "win32" and _is_benign_windows_cleanup(output):
                      return None
                  retry_marker = (
                      "[retried once after dotnet build-server shutdown; "
                      "still failing] "
                  )
              # Extract every raw failure-marker line from the FULL, untruncated output -- this is the signature set _run_verify_gates uses (after normalization) for baseline/finalize subset-diff comparison, distinct from the capped excerpt used below for the human-facing reason.
              signatures = _extract_failure_signatures(output)
              # Truncation enriches the reason with an omitted-content marker plus up to 20 extracted earlier-failure summary lines recovered from the omitted portion (#731) -- without this, an earlier failing package/test's identity can be silently dropped when a later, less- informative failure lands in the kept tail.
              output_stripped = output.strip()
              if len(output_stripped) > 2000:
                  tail = output_stripped[-2000:]
                  omitted = output_stripped[:-2000]
                  fail_lines = _extract_failure_signatures(omitted)[:20]
                  marker = f"[... {len(omitted)} earlier chars omitted"
                  if fail_lines:
                      marker += "; earlier failures:\n" + "\n".join(fail_lines)
                  marker += " ...]\n"
                  reason = marker + tail
              else:
                  reason = output_stripped
              return {
                  "status": "stuck",
                  "stuck_type": "verify",
                  "reason": retry_marker + reason,
                  "signatures": signatures,
              }
  ```

  Do not touch `_run_verify_gates`, `_is_benign_windows_cleanup`, or
  `_has_windows_cleanup_race_signature` in this card -- only `_run_verify_gate`'s failure branch
  and its docstring change, plus the new helper. The retry is gated on `sys.platform == "win32"`
  and `"dotnet" in verify_cmd.lower()`, exactly mirroring the existing unconditional shutdown's own
  gate a few lines above (lines 832-836) -- this is deliberate reuse of the same two conditions,
  not a coincidence. No new/second `dotnet build-server shutdown` call is added anywhere in this
  card; the retry relies entirely on the shutdown that already runs unconditionally after every
  dotnet verify subprocess, immediately before this failure branch executes.
- **Commit:** `fix(implementer-common): retry a racing dotnet verify command once after build-server shutdown (#848, #860)`

### Card 2: Test coverage for the dotnet-lock retry

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `test-implementer-common.py` already has lettered test blocks `Test A` through `Test H` (the
  next existing block after `Test C` is itself named `Test D`, at line 2021, covering unrelated
  truncation-marker behavior from #731 -- do NOT reuse that letter). Insert a new `Test I` block
  immediately after `Test H`'s `except Exception as exc:` handler closes (the `errors += 1` line
  that ends `Test H`, immediately before the `# Case 36 -- Bug #557` comment), using the same
  `unittest.mock.patch("sys.platform", "win32")` + mocked `_implementer_common.subprocess.run`
  (`side_effect` list) convention `Test C` already uses. Four sub-cases, each its own
  `with tempfile.TemporaryDirectory()` block wrapped in `try`/`except Exception as exc: print(f"FAIL: Test I<n> ({exc})", file=sys.stderr); errors += 1`, matching the file's existing
  per-sub-case try/except granularity (see `Test C1`/`Test C2` above it):

  - **Test I1** (retry succeeds): `dotnet_cmd = "dotnet test MyProject.csproj"`. Build an output
    string containing `"MSB3021"` (e.g.
    `"Build FAILED.\nMSB3021: Unable to copy file \"bin/testhost.exe\" to \"obj/testhost.exe\". "
    "The process cannot access the file because it is locked by: \"testhost (1234)\"."`).
    `mock_run.side_effect` = `[failing_result(returncode=1, stdout=<that output>, stderr=""),`
    `shutdown_result, passing_result(returncode=0, stdout="", stderr="")]` (3 `MagicMock`s in
    order). Call `_run_verify_gate(project_root, dotnet_cmd)`. Assert the result is `None`. Assert
    `mock_run.call_args_list` has exactly 3 entries. Assert the 1st and 3rd calls have identical
    positional args (same command re-run) -- `mock_run.call_args_list[0].args == mock_run.call_args_list[2].args`.
  - **Test I2** (retry still fails): same `dotnet_cmd` and same MSB3021-bearing first output.
    `mock_run.side_effect` = `[failing_result(<msb3021 output>), shutdown_result, failing_result_2(returncode=1, stdout="Build FAILED.\nMSB3021: still locked by testhost (5678).", stderr="")]`.
    Call `_run_verify_gate`. Assert the result is a dict. Assert
    `result["reason"].startswith("[retried once after dotnet build-server shutdown; still failing] ")`.
    Assert `"5678"` appears in `result["reason"]` (proves the reason reflects the *retry's own*
    output, not the first attempt's).
  - **Test I3** (dotnet fails, no lock signature): `mock_run.side_effect` =
    `[failing_result(returncode=1, stdout="Build FAILED.\nCS0103: The name 'Foo' does not exist in the current context", stderr=""), shutdown_result]`.
    Call `_run_verify_gate(project_root, dotnet_cmd)`. Assert `mock_run.call_args_list` has exactly
    2 entries (no retry call made). Assert `result["reason"]` does NOT start with the retry marker
    and contains `"CS0103"` (the original, unmarked failure).
  - **Test I4** (non-dotnet command, output happens to contain "MSB3021" text): use
    `non_dotnet_cmd = "pytest tests/ -q"` with `mock_run.side_effect` =
    `[failing_result(returncode=1, stdout="Build FAILED.\nMSB3021: is locked by: testhost", stderr="")]`
    (a single `MagicMock` -- only one call expected). Call `_run_verify_gate(project_root, non_dotnet_cmd)`.
    Assert `mock_run.call_args_list` has exactly 1 entry (neither the shutdown call nor a retry
    call fires, since `"dotnet" in verify_cmd.lower()` is `False`). Assert the returned reason is
    the original unmarked failure text.

  Print one `PASS: Test I<n> - ...` line per sub-case on success, matching the file's existing
  style. Every `MagicMock` result used as a `subprocess.run` return needs explicit string
  `.stdout`/`.stderr` attributes (not left as auto-generated `MagicMock` children) -- the function
  concatenates them directly (`result.stdout + result.stderr`), which raises `TypeError` on an
  unset `MagicMock` attribute.
- **Commit:** `test(implementer-common): cover dotnet build-server lock-race retry (Test I)`

## Batch Tests

`verify:` runs the full `test-implementer-common.py` file directly (not scoped further via
`run-all.py --only`) since Card 1's edit sits inside `_run_verify_gate`, a function already
exercised by roughly a dozen existing test blocks in this same file (`Test A`, `Test B`, `Test B2`,
`Test C`, `Test D` through `Test H`, plus several numbered `case NN` blocks later in the file) --
scoping to a `--only` subset of that one file would still mean running effectively the whole file,
so the plain per-file invocation is simpler and no slower.
