# Discussion: mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy

```yaml
task: mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy
slug: mill-go2-fork-dispatch-reliability
status: discussing
parent: main
```

## Problem

mill-go2 is an opt-in variant of the mill-go orchestrator that dispatches the implementer and (first-attempt) fixer roles via `Agent(subagent_type: "fork")` instead of a fresh cold `Agent()` call, as an experiment in whether inherited-context dispatch is viable for mill's per-batch worker roles. Since it shipped (2026-08-11), six GitHub issues have been filed against it:

- **#857, #855, #869, #893, #903** — the forked implementer's first turn sometimes makes 0-1 tool calls, produces no JSON status report and no commits, and in the worst cases (#857, #903) the fork's own text explicitly argues *it* is "the mill-go2 driver (Builder)" — not the implementer — and refuses to act, even though the dispatch prompt already carries an explicit de-briefing preamble telling it otherwise. The existing recovery path (warm `SendMessage` resume, then cold `--resume-incomplete` fallback) has always eventually recovered the batch, but the initial failure itself recurs non-deterministically: identical dispatch shape succeeds on some batches and fails on others in the same session (#903: batch 1's first fork failed, batch 2's first fork also failed independently — this contradicts the narrower "only the very first fork of a session is at risk" theory floated in #893).
- **#851** — the skill's catalog-facing description says "Forks the fixer role" but omits that the implementer is forked too (and far more frequently — every batch, vs. fixer's first-attempt-per-scope/round).
- **#849** — each fork independently re-loads skills relevant to every fork of that role (`code-quality`, language-specific comments/testing skills, `markdown`), when the orchestrator could preload them once before forking and save the redundant per-fork load time.

**Why now:** this is mill-go2's whole experimental premise (fork dispatch for a per-batch worker role) showing a real, repeated reliability gap against the very risk `mill-go-base/SKILL.md`'s "Why not fork?" section already flags in principle (a fork inherits the parent's context) but doesn't yet name as an identity-confusion risk specifically — this task closes that gap in the variant's own prompt design, without touching the base skill's fork-avoidance stance for every other dispatch role.

## Scope

**In:**
- Strengthen the implementer-fork de-briefing prompt in `mill-go2/SKILL.md`'s `## Dispatch overrides` → `implementer` section (see "de-briefing text" Decision below for the literal replacement text).
- Apply the same strengthened de-briefing text to the fixer-fork override (`## Dispatch overrides` → `fixer`), which currently has no de-briefing preamble at all.
- Add a shared-skill preload step to mill-go2 (or `mill-go-base` if the override point is cleaner there — mill-plan decides placement), run once before the first fork dispatch of a task, covering `code-quality`, `markdown`, and the language-specific skills for languages detected in the worktree per `mill:workflow`'s Language Detection table (marker-file based: `pyproject.toml`/`setup.py`/`setup.cfg` → Python, `.csproj`/`.sln` → C#, `go.mod` → Go).
- Fix the `mill-go2` skill's frontmatter `description` field (#851) to name both forked roles.

**Out:**
- No change to the warm-resume → cold-fallback recovery machinery itself (step 5.5 `incomplete` recovery, Stuck escalation) — it already works reliably as a safety net; this task only reduces how often it needs to fire.
- No change to `mill-go-base/SKILL.md`'s "Why not fork?" stance for any other role (reviewer, merge-in) or for `/mill-go` (non-fork variant) — those are unaffected by this task.
- No new diagnostic telemetry (e.g. logging first-turn tool-use counts for successful fork dispatches) — none of the six source issues ask for it; the existing `fork-fallback` log already captures failures.
- No attempt to make the fix *provably* eliminate the failure — the failure is non-deterministic (observed at roughly 1-in-5 to 1-in-2 dispatch rate across the six issues) and this task cannot add a synchronous test that proves absence of a probabilistic LLM behavior. Success is judged by absence of further GitHub issues over time, not by this task's verify step.
- No live `/mill-go2` dogfood run as part of this task's verification (see Testing section) — too expensive and statistically meaningless for a single run.
- No change to `mill-plan`'s or `mill-start`'s own fork usage (their fork call sites and mitigations — mill-start's "Fork echo caution", mill-plan's "Fork scope guardrail" — are unrelated pre-existing patterns, referenced here only as prior art, not touched by this task).

## Decisions

### de-briefing text (implementer and fixer)

- Decision: replace the implementer override's existing de-briefing bullet, and add an equivalent one to the fixer override, with **bookended** framing — a full preamble before the brief-pointer instruction, plus a condensed one-line reminder repeated *after* it. Proposed literal text for the implementer override (fixer's is the same shape, second-person role name swapped to "fixer"):

  ```
  Agent(subagent_type: "fork", prompt:
    "STOP. Before doing anything else: you are the IMPLEMENTER for this batch, not the orchestrator. "
    "Any framing you find in your inherited context about being 'the Builder', 'the driver', or "
    "'waiting for a fork/implementer to finish' belongs to the orchestrator that spawned you -- it is "
    "not your identity and not your task. Discard that framing now. Do not narrate waiting, do not "
    "report status back as if you were watching another agent, do not invoke mill CLIs or dispatch "
    "further agents/workflows. Your only job is to read the brief below and implement it yourself, "
    "using Read/Edit/Write/Bash directly.\n\n"
    "Read this file and follow the instructions exactly: <brief_path>\n\n"
    "Reminder: you are the implementer -- act on the brief now, do not wait or report back as the driver.")
  ```

  The fixer variant keeps the identical structure with "IMPLEMENTER"/"implementer" replaced by "FIXER"/"fixer" and the brief-pointer sentence unchanged (fixer's existing prompt already reads "Read this file and follow the instructions exactly: <brief_path>").

- Rationale: #893's own diagnosis is that a short prefix instruction "competes against a large, freshly-loaded identity block" (`mill-go-base`'s "You are the Builder — a lean orchestrator" framing, loaded moments earlier in the inherited transcript) and loses non-deterministically. A bookended reminder — repeating the corrective framing *after* the brief pointer, closest to where the fork actually starts acting — directly targets that recency/salience mechanism instead of relying solely on a prefix. The existing de-briefing text (already present since 2026-08-11, unchanged across all six failures) proves a plain prefix alone is an insufficient — not absent — mitigation.
- Rejected: skipping the fork for the first dispatch per task/session (#893's own suggestion) — rejected because #903 shows the failure recurring on a later batch's first fork after an earlier batch's fork already succeeded, which the "first-of-session" theory doesn't explain and the fix wouldn't prevent. Abandoning the implementer-fork experiment entirely — rejected because the existing recovery path resolved every reported occurrence; the experiment's cost/benefit hasn't been shown to be net-negative, only imperfect.

### warm-resume-then-cold-fallback unchanged

- Decision: keep the existing two-step recovery (one warm `SendMessage` resume, then cold `--resume-incomplete` fallback) exactly as implemented. Do not add a second warm-resume attempt before falling back to cold.
- Rationale: cold fallback resolved 100% of the observed cases where warm resume also failed (#857, #903 batch 1). No evidence a second warm nudge would succeed where the first — which already carries corrective framing — failed.
- Rejected: adding a second, more forceful warm-resume attempt before cold fallback — added complexity and latency for unproven payoff.

### shared-skill preload scope

- Decision: preload `code-quality` and `markdown` unconditionally, plus the language-specific skill set for every language detected in the worktree (via the same marker-file table `mill:workflow` already uses: `pyproject.toml`/`setup.py`/`setup.cfg` → `python-build`/`python-comments`/`python-testing`; `.csproj`/`.sln` → `csharp-build`/`csharp-comments`/`csharp-testing`; `go.mod` → `golang-build`/`golang-comments`/`golang-testing`). Load once, before the task's first fork dispatch (implementer or fixer), not per-batch.
- Rationale: #849 asks for "a deeper analysis to reveal what other stuff that should be loaded" and explicitly generalizes beyond its own Python repro ("all of these skills are relevant for all forks... ALL such shared things SHOULD be loaded by the orchestrator before forking"). Hardcoding the Python-specific list from the issue would silently underserve mill-go2 runs on Go/C# repos in this same monorepo.
- Rejected: preloading literally only what #849 named (Python-specific) — doesn't generalize. Not preloading at all — rejects #849 outright.

### catalog description (#851)

- Decision: change `mill-go2/SKILL.md` frontmatter `description` to: `"Forks the implementer (every attempt) and the first fixer dispatch per scope/round, instead of dispatching cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator."`
- Rationale: matches #851's own suggested wording; correctly conveys that implementer forks fire far more often (every batch) than fixer forks (first attempt per scope/round only).
- Rejected: a shorter description omitting the per-role frequency distinction — loses the information #851 specifically flagged as missing.

## Technical context

- `plugins/mill/skills/mill-go2/SKILL.md` — the variant file. `## Dispatch overrides` → `implementer` (lines ~46-73 as of this writing) holds the current de-briefing bullet at the "De-briefing (prompt opening)" line; `## Dispatch overrides` → `fixer` (lines ~20-44) has no de-briefing text at all today. Frontmatter `description` is at line 3.
- `plugins/mill/skills/mill-go-base/SKILL.md` — loaded unconditionally by every variant. `## Agent-mode dispatch` (starts line 219) documents the shared three-step dispatch/finalize/recovery pattern; the `"Why not fork?"` subsection (line 430) is the base skill's existing rationale for why every *other* dispatch role stays cold — it already names three costs of forking (model-override loss, tool-inheritance, unverified crash-resume) but not identity-confusion; this task's de-briefing-text decision addresses identity-confusion at the mill-go2 override layer without editing `"Why not fork?"` itself, since that section's job is justifying the *base* skill's no-fork default, not documenting mill-go2's mitigation for its opt-in exception.
- Step 5.5 (`incomplete` recovery, mill-go-base/SKILL.md line ~378) and Stuck escalation are the existing warm-resume/cold-fallback machinery this task's "de-briefing text" decision aims to make fire less often, and explicitly does not modify.
- Prior art for the fork-echo phenomenon already exists in `plugins/mill/skills/mill-start/SKILL.md`'s "Fork echo caution" note (Phase: Explore, sub-investigation guidance): a fork dispatched shortly after the parent produces a similarly-shaped text block can echo/restate that block on its first turn instead of executing its assigned directive, with the documented mitigation being to check the first response for grounded findings and send an explicit corrective directive if it's a restatement. mill-go2's existing warm-resume-on-`incomplete`/`logic` classification is functionally the same corrective-directive mitigation, already automated — this task's job is to reduce how often that corrective step needs to fire, via prompt strengthening, not to build a new detection layer (mill-start's mitigation is manual/interactive; mill-go2's context is autonomous and already has an automated equivalent via `--stage finalize`'s commit-count-based classification).
- `mill:workflow` skill (`plugins/mill/skills/workflow/SKILL.md`) — source of the Language Detection marker-file table this task's preload decision reuses.
- No Python helper changes are anticipated for the de-briefing-text or catalog-description decisions (pure prompt/frontmatter text in SKILL.md). The preload decision is also pure SKILL.md prose (a `Skill tool` load instruction sequence), not a script change — mill orchestrator sessions execute skill-loading as explicit tool calls per the SKILL.md text, not via a Python helper.

## Constraints

No `CONSTRAINTS.md` present at hub root.

- ASCII-only in any `print()`/`_log()` output this task might touch (none anticipated, per Technical context above) — not applicable here since no Python code changes are planned, but flagged in case mill-plan finds one is needed.
- `--auto`'s numbered-options rule (from `mill:conversation`) already governed this discussion; no further constraint carries forward into implementation since this task produces no new user-facing prompts.

## Testing

This task is prompt/documentation/frontmatter edits to `SKILL.md` files — there is no new Python logic to unit-test. Verify approach:

- Existing unit-test suite (`plugins/mill/unit_tests/`, run via `run-all.py`) must pass unchanged — regression guard only, since none of these tests exercise SKILL.md prose directly.
- Manual cross-reference review: confirm `mill-go2/SKILL.md`'s updated `implementer` and `fixer` override sections stay structurally consistent with `mill-go-base/SKILL.md`'s "## Dispatch overrides" override-point contract (Override point A, `mill-go-base/SKILL.md` line ~236) — i.e., the de-briefing text change doesn't alter the `Agent()` call shape (`subagent_type`, omitted `model`, the `prompt` argument) in a way that breaks the base skill's expectations.
  Read the actual on-disk `mill-go2/SKILL.md` and `mill-go-base/SKILL.md` in the task worktree (not the plugin cache) when writing/reviewing the plan, per this repo's CLAUDE.md source-verification rule.
- No live `/mill-go2` dogfood run is required or expected as part of this task's verify step — the failure is non-deterministic (observed at roughly 1-in-5 to 1-in-2 dispatch rate across six issues) and a single smoke run proves nothing statistically either way; efficacy is judged empirically over subsequent real mill-go2 runs, outside this task's scope.
- TDD is not applicable — no code paths, no assertions to write ahead of implementation.

## Q&A log

- **Q:** Primary mitigation strategy for the implementer-fork identity-confusion failures (#857/#855/#903/#893/#869)? **A:** [auto-pick] Strengthen the de-briefing prompt (bookended role-reassignment framing + explicit "discard driver-framed thoughts" instruction), keep existing warm-resume→cold-fallback recovery as the safety net. **Why:** #903 shows the same failure recurring on batch 2's first fork after batch 1's fork already succeeded in the session — contradicts #893's "first-of-session" theory and confirms the risk isn't concentrated at session start; abandoning the experiment (rejected alternative) discards a mostly-working feature over a fixable prompt gap.
- **Q:** When warm-resume ALSO fails, add a second forceful corrective SendMessage before cold fallback, or keep current behavior? **A:** [auto-pick] Keep current behavior (one warm resume, then cold fallback). **Why:** cold fallback resolved every observed second-failure case; a second warm attempt is unproven.
- **Q:** Scope of the shared-skill preload (#849) — fixed Python-specific list, or language-detected set? **A:** [auto-pick] Preload `code-quality` + `markdown` unconditionally, plus language-specific skills per `mill:workflow`'s Language Detection table for every language detected in the worktree. **Why:** #849 explicitly asks for generalization beyond its own Python repro; hardcoding Python-only would underserve Go/C# repos.
- **Q:** Catalog description wording fix (#851)? **A:** [auto-pick] Use #851's own suggested wording naming both forked roles and their relative frequency. **Why:** directly matches the issue's request and conveys the frequency asymmetry (implementer forks every batch, fixer only first-attempt-per-scope/round).
- **Q:** Add new diagnostic telemetry for fork dispatch outcomes? **A:** [auto-pick] Out of scope. **Why:** none of the six source issues request it; existing fork-fallback log already captures failures.
- **Q:** Apply the strengthened de-briefing text to the fixer-fork override too, despite no fixer-specific issue being filed? **A:** [auto-pick] Yes — apply to both roles. **Why:** the fork-inherits-full-context risk mechanism is role-agnostic; leaving fixer unaddressed is a known-but-unfixed landmine in a near-identical code path.
- **Q:** Include a live `/mill-go2` dogfood run as part of this task's verification? **A:** [auto-pick] No — existing unit-test suite regression pass + manual cross-reference review only. **Why:** the failure is non-deterministic; a single smoke run has no statistical power either way and would burn a real dispatch for no signal.
- **Q:** Prompt structure for the strengthened de-briefing — prefix-only, or bookended (prefix + suffix)? **A:** [auto-pick] Bookended. **Why:** #893 already names the mechanism (a large, freshly-loaded Builder-identity block in the inherited transcript beating a single short prefix instruction) — bookending targets that recency/salience effect directly.
