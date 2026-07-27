# Discussion: Agent-dispatch boundary gaps: source-read guidance, fork directive-echo, and raw FileNotFoundError on missing agent-output

```yaml
task: Agent-dispatch boundary gaps: source-read guidance, fork directive-echo, and raw FileNotFoundError on missing agent-output
slug: mill-agent-dispatch-guidance-gaps
status: discussing
parent: main
```

## Problem

Three gaps surfaced during a real self-hosted mill-plan/mill-start/mill-go session (consolidated from GitHub issues #711, #710, #704) and were folded into this one task since they're all small boundary-condition fixes to the agent-dispatch guidance and machinery:

1. **#711 — cache vs. worktree source reads.** mill-plan/mill-start tell orchestrators to invoke scripts via `${CLAUDE_PLUGIN_ROOT}/scripts/...` — correct, since the cache holds the deployed plugin used to run skills. But no guidance says that *reading source code to verify plan/discussion accuracy* (i.e. reading the actual code a plan is about to edit, not invoking a script) must instead target the task-worktree path. In this self-hosted repo (millhouse developing millhouse), the cache and the worktree can silently diverge. In the cited incident, reading `millpy-review-code.py`/`millpy-review-plan.py` from the cache during plan-writing produced a wrong conclusion (that 2 of 6 affected call sites didn't need fixing, since the cache's version already used a different, non-buggy resolver) that had to be walked back mid-plan after re-verifying against the worktree — a wasted rework round.
2. **#710 — fork echoing instead of executing.** During mill-start's Explore phase, `Agent(subagent_type: "fork")` was dispatched with a specific, self-contained investigation directive. Its first response was essentially a restatement of the parent's own just-written scope digest — no file reads, no requested findings. A second explicit SendMessage nudge ("stop restating the digest, actually investigate") fixed it. The reproduction hint: dispatching a fork shortly after the parent produces a similarly-shaped text block risks the fork continuing that block instead of following the new directive on its first turn.
3. **#704 — raw traceback on missing `--agent-output` file.** `millpy-fix.py --stage finalize --agent-output <path>` crashes with an unhandled `FileNotFoundError` traceback when `<path>` doesn't exist on disk, instead of a clean, actionable message. This happens in the shared helper `_implementer_common.py:finalize_from_output` (the `Path(agent_output_path).read_text(...)` call), which is used by all three implementer-family finalize paths: `millpy-fix.py`, `millpy-implement.py`, and `millpy-merge-in-subagent.py`. An analogous clean error already exists for `millpy-review-discussion.py --stage finalize`'s *missing flag* case — this is the sibling "flag present, file absent" case.

**Why now:** all three were discovered live, during actual mill-go/mill-plan/mill-start sessions on this repo, and are the kind of small, well-scoped guidance/robustness fixes best fixed immediately rather than left to recur.

## Scope

**In:**
- A new hard-constraint bullet distinguishing "read source via `${CLAUDE_PLUGIN_ROOT}` for script invocation" from "read/verify actual source code via the task-worktree path" — added to CLAUDE.md's `## Hard constraints` section, next to the existing `${CLAUDE_PLUGIN_ROOT}` rule it contrasts with.
- A caution note added to mill-start/SKILL.md's existing "Sub-investigation guidance" paragraph (in Phase: Explore) about forks potentially echoing a recently-produced parent text block instead of executing their directive, plus a check-before-trust instruction (look for grounded findings/file:line citations in the fork's first response; re-dispatch via SendMessage if absent).
- A fix in `_implementer_common.py`'s `finalize_from_output`: catch the missing-`--agent-output`-file case at the read site, print a clean actionable message to stderr, and return a non-zero exit code — instead of letting `FileNotFoundError` propagate as a raw traceback. Fixes all three call sites (`millpy-fix.py`, `millpy-implement.py`, `millpy-merge-in-subagent.py`) at once since they share this helper.
- A unit test in `plugins/mill/unit_tests/test-implementer-common.py` covering `finalize_from_output` called with a nonexistent `--agent-output` path, asserting the clean message and non-zero return code.

**Out:**
- No change to how `${CLAUDE_PLUGIN_ROOT}` is used for script invocation elsewhere — that convention is correct and unchanged.
- No mechanical/automatic safeguard against fork echo (e.g. auto-verifying file:line citations and auto-resuming) — this is a one-off observed quirk, not a reproducible failure mode worth codifying as enforced machinery. Documented as a caution + manual check only.
- No change to `millpy-review-discussion.py`'s existing missing-flag / missing-file handling — it already has correct behavior (clean error for missing flag; silent-empty degradation for missing file, which is appropriate for a review that can legitimately return no findings). This task does not change review-CLI finalize paths, only the implementer-family ones.
- No broader audit of every other place a `--agent-output`-shaped path is read across the codebase — scoped strictly to `finalize_from_output`, the one function named in #704.

## Decisions

### cache-vs-worktree guidance location

- Decision: Add the new rule to CLAUDE.md's `## Hard constraints` section as its own bullet.
- Rationale: CLAUDE.md is read on every session start regardless of which skill (mill-plan, mill-start, mill-go, or an ad-hoc session) is running, and it already documents the `${CLAUDE_PLUGIN_ROOT}`-for-intra-plugin-paths rule this new rule directly contrasts against — placing them adjacent makes the distinction legible in one place instead of split across skill files.
- Rejected: Skill-local wording in mill-plan/SKILL.md and mill-start/SKILL.md only (too narrow — the same trap applies to any ad-hoc exploration in this self-hosted repo, not just those two skills' documented phases). A dedicated note in mill-go/SKILL.md (mill-go's own dispatch guidance doesn't do source-code verification reads the way plan/discussion-writing does, so it's not the natural home).

### fork directive-echo mitigation

- Decision: Document a caution + manual verification step in mill-start/SKILL.md's "Sub-investigation guidance" paragraph; no mechanical enforcement.
- Rationale: This is the one site in mill that already forks (per the existing "Why not fork?" disqualifier analysis in mill-go/SKILL.md), and the failure was observed once and fixed with a manual SendMessage nudge — consistent with mill's "YAGNI ruthlessly" principle, a lightweight documented caution is proportionate; an automatic citation-checking/auto-resume mechanism would add process complexity for a single anecdotal incident.
- Rejected: No documentation change at all (loses the reproduction hint for future orchestrators); automatic mechanical safeguard (over-engineered for a one-off, unconfirmed-as-systemic quirk).

### finalize_from_output error handling

- Decision: Catch the missing-file condition inside `_implementer_common.py:finalize_from_output` itself (wrapping the `Path(agent_output_path).read_text(...)` call), print `ERROR: --agent-output file not found: <path> -- for implementer/fixer/merge-in dispatches the orchestrator must write the notification message to this path before calling --stage finalize` to stderr, and return `1`.
- Rationale: `finalize_from_output` is a shared helper called from three CLIs (`millpy-fix.py`, `millpy-implement.py`, `millpy-merge-in-subagent.py`); fixing it once at the shared call site fixes all three, matching the issue's explicit framing ("this is the sibling case where the flag is present but the file it names doesn't exist yet", generalized across the implementer family). A missing implementer/fixer/merge-in output represents an orchestrator-side dispatch bug (the notification-to-file write step was skipped) and should surface immediately as a clear failure, not be silently reinterpreted as a stuck/logic signal the way a missing *reviewer* output legitimately can be (reviewers can produce empty findings; implementers/fixers/merge-in cannot legitimately produce "no output").
- Rejected: Fixing only `millpy-fix.py`'s call site (leaves the identical latent bug in `millpy-implement.py` and `millpy-merge-in-subagent.py`); mirroring `millpy-review-discussion.py`'s silent-empty-string degradation (wrong semantics here — an implementer/fixer/merge-in with no captured output is always an orchestrator bug, never a legitimate empty result).

## Technical context

- **`_implementer_common.py:finalize_from_output`** (currently starting at line 1232) is the shared function; the crash site is the `Path(agent_output_path).read_text(encoding="utf-8")` call (currently line 1298), immediately preceded by an existing comment about HTML-unescaping the harness's `<task-notification>` payload. The new file-existence check must go around this line, before the `html.unescape(...)` call, and must not otherwise change the unescape/`_forward_output` delegation for the success path.
- **Call sites to verify after the fix** (no code changes needed at these sites themselves — they already pass `Path(args.agent_output)` through unconditionally): `millpy-fix.py` (~line 448), `millpy-implement.py` (~line 434), `millpy-merge-in-subagent.py` (~line 310).
- **Reference pattern for the CLI-level "flag missing" clean error** (already correct, not being changed): `millpy-fix.py` lines 415-417 — `if not args.agent_output: print("--agent-output is required when --stage finalize", file=sys.stderr); return 1`. The new fix should use the same plain-stderr-print + `return 1` style for consistency, since `finalize_from_output`'s callers are the implementer-family CLIs (which use plain stderr prints), not the review CLIs (which use `_review_cli.print_error_envelope` for a JSON error envelope — that helper is review-specific and should not be imported into `_implementer_common.py`).
- **Reference pattern for "missing file, not missing flag"** (contrast, not to be copied): `millpy-review-discussion.py` lines 165-177 — checks `agent_output_path.exists()` and falls back to `""` on a missing file, deliberately, with an inline comment explaining that downstream `finalize()` turns empty text into a `verdict: ERROR` result. This is review-specific graceful degradation and is the wrong model for the implementer family (see Decision above).
- **CLAUDE.md's existing `## Hard constraints` section** already has the adjacent rule to contrast against: `` **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** Never `plugins/mill/…` — external repos have no millhouse checkout. Write `${CLAUDE_PLUGIN_ROOT}` literally in Bash tool calls — do NOT read or memorize its value; let the shell expand it at runtime. ``
- **mill-start/SKILL.md's existing "Sub-investigation guidance" paragraph** (in Phase: Explore) is the exact spot for the #710 caution note — it already describes when to use `Agent(subagent_type: "fork")` vs. a cold `Explore` agent vs. inline exploration.
- **mill-go/SKILL.md's "Why not fork?"** note (in the "## Agent-mode dispatch" section) already explains why fork is used nowhere else in mill; it does not need to change, but is useful cross-reference context for why mill-start's Explore phase is the sole fork call site this caution applies to.
- **`plugins/mill/unit_tests/test-implementer-common.py`** already exists and is the natural home for the new regression test (project convention: `test-<name>.py`, in-memory/tempfile fixtures, no real git/LLM, run via `run-all.py`).

## Constraints

_No CONSTRAINTS.md present at the hub root; no additional constraints surfaced during discussion beyond the existing project conventions in CLAUDE.md (ASCII-only `print()`/`_log()` output, `PYTHONPATH=` verify-command prefix for Python test subprocess isolation, etc.), which apply unchanged to any new code/tests this task adds._

## Testing

- **`_implementer_common.py:finalize_from_output`** is the TDD candidate. Add a test to `plugins/mill/unit_tests/test-implementer-common.py` that calls `finalize_from_output` with a path to a file that does not exist (e.g. a tempfile path that was never created, or a path inside a tempdir fixture that is deleted before the call) and asserts: (a) the function returns a non-zero exit code, (b) no `FileNotFoundError`/traceback is raised, (c) the printed message names the missing path and explains the orchestrator's write-before-finalize responsibility.
- Existing tests in `test-fix-finalize.py` and `test-review-finalize.py` cover the success and other-error paths for the finalize stage across the various CLIs — confirm the new missing-file test doesn't duplicate or conflict with any existing fixture in those files (a quick grep for `agent_output`/`agent-output` in each before adding the new test is sufficient; no broad refactor of those files is in scope). Note: despite the similar name, `test-mill-finalize-dispatch.py` is unrelated — it covers `require_pr_to_base` PR-vs-direct dispatch logic for the `mill-finalize` skill, with zero `agent_output`/`finalize_from_output` references; it is not a `finalize_from_output` test and should not be checked for dedup.
- No test is needed for the CLAUDE.md or mill-start/SKILL.md documentation changes (#711, #710) — these are guidance-only changes with no executable behavior to assert against.

## Q&A log

- **Q:** Where should the cache-vs-worktree source-read guidance (#711) live? **A:** [auto-pick] Add a new bullet to CLAUDE.md's `## Hard constraints` section, next to the existing `${CLAUDE_PLUGIN_ROOT}` rule it contrasts with. **Why:** CLAUDE.md loads on every session start regardless of which skill runs, unlike skill-local wording which only helps operators who happen to be inside that skill's documented phases.
- **Q:** Should #710 (fork echoing the parent's own text block) get a documented mitigation? **A:** [auto-pick] Add a caution note to mill-start/SKILL.md's existing "Sub-investigation guidance" paragraph, with a manual check-before-trust instruction; no mechanical enforcement. **Why:** proportionate to a single observed incident, consistent with mill's YAGNI-ruthlessly principle; an automatic citation-checking/auto-resume mechanism would be over-engineering for an unconfirmed-as-systemic quirk.
- **Q:** Fix approach for #704 (`finalize_from_output` raw `FileNotFoundError`)? **A:** [auto-pick] Catch the missing-file case inside the shared `_implementer_common.py:finalize_from_output` helper itself, print a clean actionable stderr message, and return 1 — fixing all three call sites (`millpy-fix.py`, `millpy-implement.py`, `millpy-merge-in-subagent.py`) at once. **Why:** the issue explicitly frames this as the general implementer-family sibling case, not a `millpy-fix.py`-only bug; a missing implementer/fixer/merge-in output is always an orchestrator bug and should error clearly, not silently degrade the way a missing reviewer output legitimately can.
- **Q:** Test coverage for the #704 fix? **A:** [auto-pick] Add a unit test in `plugins/mill/unit_tests/test-implementer-common.py` calling `finalize_from_output` with a nonexistent `--agent-output` path, asserting the clean message and non-zero return code. **Why:** matches the project's existing tempfile-fixture unit-test convention for this exact file, and this is squarely a TDD-shaped bug fix.
