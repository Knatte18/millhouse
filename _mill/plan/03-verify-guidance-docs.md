# Batch: verify-guidance-docs

```yaml
task: 'mill-plan/verify/implement pipeline: misc small bugs, round 3'
batch: verify-guidance-docs
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agents-defs.py
depends-on: []
```

## Batch Scope

Documentation fixes for two runtime-guidance gaps.
GitHub #1133: `mill-plan/SKILL.md` gives no extended Bash-tool timeout for the in-process validator self-run, which exceeds the default 120 s on large repos.
GitHub #1124: implementer/fixer sub-agents piped a backgrounded verify through `tail`, misread the empty log as a hang, and spawned unkillable redundant polling loops.
Both are one batch because both are prose-only guidance edits with no runtime code; the agent-definition change gets a test assertion.

## Cards

### Card 4: mill-plan validator self-run timeout note

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Edit `plugins/mill/skills/mill-plan/SKILL.md` (the task-worktree copy). Locate insertion points by text, not line number.
  - In Phase: Plan, immediately after the paragraph that begins "**Self-run the validator gate** before committing" (and before the python code block that follows it), insert a new paragraph whose content is:

    ```text
    **Extended timeout for every validator self-run.** Give every Bash-tool call that runs the validator self-run in this SKILL (this one and the full-validate gates in Phase: Plan Review steps 4b, 4c and 4d) an explicit Bash-tool `timeout` of 600000ms (10 minutes). The validator walks the whole source tree, spawns git subprocesses per declared path, and prints no progress output; on a large repo a single run has taken about two minutes, over the default 2-minute Bash timeout. This mirrors the finalize-stage timeout note in mill-go-base/SKILL.md.
    ```

    Write it with semantic line breaks (one sentence per line) per the prose skill.
  - In Phase: Plan Review step 4b, in the sentence beginning "Then run a full validator re-run: call", append a short back-reference clause such as "(with the extended timeout from Phase: Plan's self-run note)". Do the same in step 4c's sentence beginning "Run the identical full-validate gate steps 4b/4d's own full-validate gates use" and step 4d's bullet beginning "Run the identical full-validate gate step 4b's own full-validate gate uses". A back-reference only; do not repeat the rationale.
  - In the "**Verify command shape.**" paragraph, the non-Python example currently reads "(e.g. `verify: go test ./...` or `verify: dotnet test`)"; both example commands are themselves flagged by the verify-full-suite check. Replace them with scoped forms: "`verify: go test ./internal/foo/...`" and "`verify: dotnet test My.Tests.csproj`". Leave the "Done-gate reminder" paragraph's `dotnet test` / `go test ./...` examples unchanged (done_gate is exempt from that check).
- **Commit:** `docs(mill-plan): extended Bash timeout for validator self-runs (#1133)`

### Card 5: implementer background-verify guidance

- **Context:**
  - `plugins/mill/.claude-plugin/plugin.json`
- **Edits:**
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/agents/mill-implementer-low.md`
  - `plugins/mill/agents/mill-implementer-medium.md`
  - `plugins/mill/agents/mill-implementer-high.md`
  - `plugins/mill/agents/mill-implementer-xhigh.md`
  - `plugins/mill/agents/mill-implementer-max.md`
  - `plugins/mill/unit_tests/test-agents-defs.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In each of the six implementer agent definitions listed in Edits, append the following to the end of the `## Shell conventions` section (after the no-`sed` rule), byte-identical in all six files. The frontmatter is untouched.

    ```text
    Run the `verify:` command in the foreground with an explicit Bash-tool `timeout` (up to 600000ms), not backgrounded.
    If a long command must run in the background, redirect its output straight to a file (`cmd > log 2>&1`).
    Never pipe it through `tail`, `head`, or any other filter that buffers until EOF:
    the log stays empty until the whole command finishes, which looks like a hang when polled.
    Wait on a background job with at most one polling loop.
    Never start a second loop to check on a first one that looks stuck;
    you have no tool to kill a redundant loop afterwards.
    ```

  - In `plugins/mill/unit_tests/test-agents-defs.py`, add `test_implementer_agents_background_verify_guidance`: for each of the six implementer files (resolved via the module's `HUB` constant, as `test_implementer_agent_definition` does), read the text, take the body after the frontmatter, and assert it contains `tail` and the phrase "at most one polling loop"; then assert all six bodies (text after the closing frontmatter fence) are identical. Register it in `main()`'s `tests` list after `test_implementer_xhigh_agent_definition`.
- **Commit:** `docs(agents): implementer guidance against tail-piped background verify (#1124)`

## Batch Tests

`verify:` runs `test-agents-defs.py`, covering card 5's new guidance assertion and the existing frontmatter/registration tests for all agent definitions.
Card 4 edits SKILL.md prose only, which has no runnable surface; it is verified by review.
