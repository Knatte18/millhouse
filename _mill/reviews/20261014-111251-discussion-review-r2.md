MILL_REVIEW_BEGIN
# Review: Instrument and bound the verify runner

```yaml
duration_s: 80.6
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: C:\Code\millhouse\wts\verify-runner-instrumentation\_mill\discussion.md
date: 2026-10-14
```

## Findings

### [BLOCKING:design] 20-minute timeout exceeds the 10-minute Bash cap on the paths that need it
**Section:** Decisions / Timeout; Scope (Out, Bash-tool cap); Merge-in SKILL replay goes through a CLI **Issue:** `mill-go-base/SKILL.md` gives finalize, pre-flight and (per this discussion) the new merge-in CLI a 600000 ms Bash timeout, so a hung verify is cut off by the Bash tool at 10 minutes, before the runner's 20-minute timeout fires.
Finalize replays every batch sequentially, so the cap is reached even sooner on healthy runs.
On those paths the "fails the gate loudly" goal is unmet: the caller gets a tool timeout with no verdict, no `timed_out` envelope and no `## Verify log` row.
**Fix:** State how the default timeout and the Bash cap are reconciled (for example a lower default, or a stated per-path outer bound with the expected failure shape), and drop or justify the "600000 ms" instruction for the new CLI.

### [NIT:consistency] `shell_mode="posix"` is not what `_posix_shell_run_args` does
**Demoted-from:** BLOCKING
**Section:** Decisions / Shell mode preserves each site's current semantics **Issue:** The discussion says `"posix"` "reproduces" the helper, including `[$SHELL or /bin/sh, "-c", cmd]` on POSIX.
In source the helper returns `(cmd, {"shell": True})` off-Windows (so `/bin/sh`, never `$SHELL`) and `[bash, "-c", cmd]` only on Windows with bash.
It also returns a string plus a `shell=True` kwarg, which `_subprocess_util.run(argv: list[str])` cannot accept, so "the runner calls it or shares its helper" is undecided.
**Fix:** Specify the exact argv per OS for both modes (explicitly say whether `$SHELL` is intended), and say how the shell-string case is converted to a list for `_subprocess_util.run`.

### [NIT:consistency] POSIX timeout kill is not "exactly" the described mechanics
**Demoted-from:** BLOCKING
**Section:** Decisions / Timeout **Issue:** `_subprocess_util.run` on POSIX calls `proc.terminate()` and reaches `os.killpg` only if the child fails to exit within the grace period.
A `bash -c` parent that dies on SIGTERM leaves its grandchildren alive, so the stated test ("process tree including a grandchild is gone") fails on POSIX with the "reuse, do not reimplement" approach.
**Fix:** Either decide that the runner kills the group directly on timeout (and say so), or restrict the tree-kill claim and test to Windows.

### [NIT:consistency] "Existing verify-gate tests keep passing" is false for the mocked tests
**Section:** Testing **Issue:** `test-implementer-common.py` and `test-done-gate.py` patch `_implementer_common.subprocess.run` / `_done_gate.subprocess.run` and count calls, including the `dotnet build-server shutdown` call.
Routing through `_verify_run` breaks these tests, so they need rewriting, which the discussion does not acknowledge.
**Fix:** Name the new mocking seam (e.g. patch `_verify_run.run_verify`) and say the affected tests are rewritten, not preserved.

### [NIT:design] Verify-log row format is not safe for arbitrary `cmd`
**Section:** Decisions / Durable record **Issue:** `cmd` is written verbatim into a fenced `text` block row; a multi-line command or one containing a triple backtick corrupts the section and the `_find_*_block` parsing.
**Fix:** State that `cmd` is collapsed to one line and fence-safe before being written.

## Verdict

REQUEST_CHANGES
Timeout-versus-Bash-cap conflict and two false claims about reused shell and kill mechanics must be resolved before planning.
_Note: 2 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
