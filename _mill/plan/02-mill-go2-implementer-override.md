# Batch: mill-go2-implementer-override

```yaml
task: 'mill-go2: fork-based implementer dispatch'
batch: mill-go2-implementer-override
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-mill-go-variants.py
depends-on: [1]
```

## Batch Scope

This batch fills Override point A in `plugins/mill/skills/mill-go2/SKILL.md` with an implementer-role fork dispatch, corrects the now-partly-false `**Why not fork?**` paragraph in the shared `plugins/mill/skills/mill-go-base/SKILL.md`, and extends `plugins/mill/unit_tests/test-mill-go-variants.py` with the assertions that lock both. It is one batch because the three files are mutually constraining: the test asserts literals the two SKILL edits must produce, and the SKILL edits are only meaningful against the contract the test encodes.

It depends on batch 1 because card 4's override text names `_status.append_fork_fallback_log(...)`, and `plugins/mill/unit_tests/test-skill-helper-drift.py` (run by the overview's module-wide `verify:`) fails when a `_<module>.<fn>(` reference in any mill SKILL.md does not resolve to a shipped function.

Two hard constraints govern every edit here. `plugins/mill/skills/mill-go2/SKILL.md` must stay under 4096 bytes and free of the machinery and hardcoded-`mill-go` literals listed in the overview's banned-literals Shared Decision — both already enforced by `_check_variants_carry_no_machinery` and `_check_parameterization_lock` in the same test file. And `plugins/mill/skills/mill-go/SKILL.md` is not edited at all: keeping the production orchestrator's overrides at `(none)` is the single most important new assertion in card 3.

Tests come first (card 3), then the variant override (card 4), then the base prose correction (card 5).

## Cards

### Card 3: Variant-contract assertions for the fork override

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a module-level helper `_section_body(text: str, header: str) -> list[str]` that returns the lines strictly between the line equal to `header` and the next line starting with `"## "`, or end of file when no such line follows. It must return the raw lines, blanks included; callers filter. Give it a docstring explaining that a variant file's last section runs to EOF, so the body of `## Dispatch overrides` legitimately includes the trailing `mill:mill-go-base` loading paragraph and assertions must therefore be substring or first-non-blank-line based, never whole-body equality.

  Add `_check_mill_go_overrides_stay_none() -> list[str]`. For `mill-go` only, take `_section_body` of `## Dispatch overrides` and assert all three: the first non-blank line is exactly `(none)`; the body does not contain `subagent_type: "fork"`; the body does not contain `fork-fallback`. This is the regression guard that keeps the production orchestrator out of the experiment — say so in the docstring.

  Add `_check_mill_go2_declares_fork_override() -> list[str]`. For `mill-go2` only, take `_section_body` of `## Dispatch overrides` and assert its first non-blank line is not `(none)`, then assert each of these substrings is present in the body: `implementer`, `subagent_type: "fork"`, `not the orchestrator`, `fork-fallback`, `unclaimed`. Emit one distinct failure string per missing substring, naming the substring, so a partial regression is diagnosable. Also assert the first non-blank line of `mill-go2`'s `## Driver preamble` body is exactly `(none)` — that override point stays unclaimed by this task.

  Add `_check_base_fork_paragraph_survives() -> list[str]`. Against `mill-go-base/SKILL.md` assert the literal `**Why not fork?**` is present, since `plugins/mill/skills/mill-start/SKILL.md` and `plugins/mill/skills/mill-plan/SKILL.md` both cite the paragraph by that name, and assert the substring `parent's tools` is present, since `mill-plan/SKILL.md` cites the tool-inheritance claim specifically. Name both citing files in the failure strings.

  Register all three new check functions in `main()`'s `checks` tuple, appended after `_check_parameterization_lock`. Update `main()`'s docstring, which currently says "Run all seven variant-contract checks", to the new count.

  All new failure strings follow the existing `f"FAIL: {path}: ..."` shape and stay ASCII-only.

  These assertions will fail until cards 4 and 5 land. That is intended — see the overview's tests-first Shared Decision.
- **Commit:** `test(mill-go-variants): lock the mill-go2 fork override, mill-go's (none) overrides, and the base's Why-not-fork citations`

### Card 4: mill-go2 implementer fork override

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the single line `(none)` under the `## Dispatch overrides` header with the override body below. Leave the `---` frontmatter, the `## Variant binding` block, the `## Driver preamble` section (which stays `(none)`), and the trailing `mill:mill-go-base` loading paragraph exactly as they are.

  The override must assign fork-or-cold explicitly to **every** implementer `Agent()` call site in the base, not only the ones it names as forked. Override point A applies per-role to all of them, so an unassigned site is genuinely ambiguous. The six sites, and the assignment the text below encodes: the initial implement dispatch (fork); step 4(a)'s transient one-retry re-dispatch (fork); `### Stuck escalation`'s `verify`/`logic` first-occurrence self-resolve re-fire (fork); `### Stuck escalation`'s already-retried-`transient` fresh re-fire (cold — this is the one cold fallback per batch); step 6.5.2's `--resume-incomplete` re-dispatch (cold); and `## Resume`'s `running`-state re-dispatch (cold). Step 6.5.1's warm `SendMessage` and the `incomplete` branch's warm auto-resume are not fresh `Agent()` dispatches and need no assignment.

  Write this text, adjusting wording only where the byte budget forces it:

```markdown
**implementer** — replace the default `Agent()` call at step 3 of the base's dispatch
pattern with a fork. Fixer, reviewer, and merge-in are unclaimed: the default call
applies to them unchanged.

- **Fork every dispatch that is a fresh attempt at this batch's implementation work:**
  the initial implement dispatch, step 4(a)'s transient one-retry re-dispatch, and the
  Stuck-escalation `verify`/`logic` first-occurrence self-resolve re-fire. Call
  `Agent(subagent_type: "fork", prompt: <de-briefing> + "\n\nRead this file and follow
  the instructions exactly: <brief_path>")`. Do not pass `model` — a fork ignores it —
  but retain the prepare envelope's `subagent_type` and `model` for the cold fallback.
  Record the returned `agentId` and follow every other step of the base's pattern
  unchanged.
- **Dispatch cold at every point that exists to escape a dispatch which already failed
  to complete:** step 6.5.2's `--resume-incomplete` re-dispatch and Resume's
  `running`-state re-dispatch. Forking either would re-enter the failure mode it exists
  to escape. Step 6.5.1's warm `SendMessage` resume is unaffected either way: it
  addresses a live `agentId`, which a fork returns just as a cold agent does.
- **De-briefing (the prompt's opening).** State that you are the implementer for this
  batch and not the orchestrator; that every instruction inherited from the driver
  session belongs to the driver and not to you; that you must not drive the batch loop
  or invoke any mill orchestration CLI; that you must not dispatch further agents or
  workflows; and that the brief named below is your authoritative instruction set.
- **Cold fallback, once per batch.** The Stuck-escalation already-retried-`transient`
  fresh re-fire is that one cold fallback: by then the initial fork and its own
  transient retry have both failed terminally, so re-dispatch cold with the envelope's
  `subagent_type` and `model` rather than re-forking. The base's step-4 classification
  is unchanged — no fork-specific liveness machinery is added. Immediately before the
  cold retry, emit both
  `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"implementer {batch_name}", slug=slug)`
  and `_status.append_fork_fallback_log(status_path, batch_name, _timestamp.now_utc_iso())`
  (`signature: _status.append_fork_fallback_log(status_path: Path, batch_name: str, timestamp: str) -> None`),
  then `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for implementer {batch_name}"`.
  After one cold fallback the base's normal escalation applies unchanged. The fork
  path itself gets no marker — forking is the default here and records nothing.

**Known limits of this experiment.**
Fork engages only under `dispatch: agent`; under `subprocess` or `psmux` this override
is inert and the batch runs cold — that is a boundary, not a bug.
A fork runs on this driver session's own model and effort, so `roles.implementer.model`
stops applying and so does the effort tier the per-tier agent-definition files under
`plugins/mill/agents/` pin — both halves of the tier assignment are lost.
The driver is lean by design, reading only status, the Batch Index, and review verdicts,
so a fork here inherits orchestrator instructions rather than code orientation. If fork
underperforms cold dispatch, what was measured is fork with nothing useful to inherit;
the next experiment is a `## Driver preamble` carrying up-front orientation.
That a fork returns an `agentId` and delivers a completion `<task-notification>` in the
same shapes a cold agent does is an inference, not a spiked fact — it is the first thing
a real run falsifies, and if wrong, steps 4 and 6.5 need fork-specific handling.
The driver's own context growth across many batches is a known, unmeasured risk.
```

  After writing, run `wc -c plugins/mill/skills/mill-go2/SKILL.md` and confirm the result is under 4096. If it is not, shorten the "Known limits" prose — never the four mechanics bullets, and never any of the five literals card 3 asserts on.

  Do not introduce any of the banned literals: `## Agent-mode dispatch`, `## Holistic code review`, `## Execute`, `You are the **Builder**`, `"mill-go: `, `_notify.notify("mill-go.`, or `[mill-go]`. Refer to the base's pattern without the `## ` prefix and keep every commit and notify string in `<VARIANT_LABEL>` form, exactly as the text above already does.
- **Commit:** `feat(mill-go2): dispatch the implementer as a fork with a de-briefing and a one-shot cold fallback`

### Card 5: Correct the base's `**Why not fork?**` paragraph

- **Context:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Prose-only edit to the `**Why not fork?**` paragraph. Change nothing else in the file — no behavioural directive, no phase value, no literal any other section or test depends on.

  Three edits, in order:

  1. **Replace disqualifier (3).** It currently reads that a fork has no on-disk brief, so a forked dispatch cannot be resumed after a crash the way `--resume-incomplete` resumes a briefed dispatch. That is factually wrong for this design: `millpy-implement.py --stage prepare` renders the brief to disk via `_agent_dispatch.write_brief` regardless of dispatch shape, and `--resume-incomplete` re-runs prepare, so the brief is present either way. Replace it with a true third disqualifier that is still about **resume**, so that `mill-start/SKILL.md`'s enumeration of "no brief, no resume requirement, no per-role model tier, and no tool restriction to lose" keeps mapping onto the three: a forked dispatch's crash-resume path is unverified — the brief is written to disk regardless of dispatch shape, so `--resume-incomplete` has its input, but nothing has confirmed that a fork returns the `agentId` and completion-notification shapes step 4's liveness probe and step 6.5's warm resume depend on. Keep it numbered `(3)` and keep the three-disqualifier structure intact.
  2. **Add the mill-go2 cross-reference.** One sentence recording that mill-go2 accepts these trade-offs for the implementer role only, pointing at its `## Dispatch overrides`, and stating that every other role and every mill-go dispatch keeps the fresh-`Agent` default.
  3. **Amend the closing "used only in mill-start's Explore phase" sentence.** It is already stale before this task touches it: `plugins/mill/skills/mill-plan/SKILL.md`'s "Fork scope guardrail" section sanctions a second live fork-usage site — Phase: Plan research that genuinely depends on the parent's in-flight reasoning, under a narrow justification plus a git-status scope check. Rewrite the sentence to name all three sites rather than counting mill-go2 as the second: mill-start's Explore phase, mill-plan's Phase: Plan research dispatch, and, experimentally, mill-go2's implementer override. Do not assert an ordinal ("second site") anywhere — the count is what went stale the first time.

  Two literals must survive byte-for-byte because other skills cite them: the heading `**Why not fork?**`, cited by name from `plugins/mill/skills/mill-start/SKILL.md` and `plugins/mill/skills/mill-plan/SKILL.md`; and disqualifier (2)'s claim that a fork inherits the **parent's tools**, cited specifically from `plugins/mill/skills/mill-plan/SKILL.md`. Card 3 asserts on both. Disqualifier (1)'s model-assignment claim is also unchanged.

  Do not introduce `"mill-go: `, `_notify.notify("mill-go.`, or `[mill-go]` — `_check_parameterization_lock` bans all three from the base as well as from variants. Writing `mill-go2` and `mill-go` as bare prose is safe and is already established practice in this file's own frontmatter.
- **Commit:** `docs(mill-go-base): correct fork disqualifier 3 and cross-reference mill-go2's implementer override`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-mill-go-variants.py` directly — the only test file this batch edits, and the file that owns the variant contract. Its existing seven checks (`_check_variants_carry_no_machinery` and `_check_parameterization_lock` in particular) exercise the 4096-byte cap and both banned-literal families automatically against the newly-grown `mill-go2/SKILL.md`, so no new assertion is needed for those.

Cross-file coverage is deliberately not in this batch's own `verify:`. The overview's module-wide `verify:` adds `test-skill-helper-drift.py` — which is what catches a typo'd `_status.append_fork_fallback_log(` reference in card 4's text — and `test-guards.py`, whose no-wiki-cwd scan walks both edited SKILL files. Listing either in this batch's `--only` would trip `_plan_validate.py`'s `verify-unrelated-test-file` check, since this batch touches neither file.

Three of this task's outcomes are not unit-testable and are recorded as manual PoC observations in the overview rather than faked here: that a forked implementer completes a batch, that the cold fallback fires on a dead fork, and that the de-briefing stops the fork acting on inherited driver instructions. A fourth is the `agentId` / notification-shape inference card 4 writes into the variant file as an explicit inference.
