# Discussion: 26 (A) — auto-report-auto-submit

```yaml
task: 26 (A) — auto-report-auto-submit
slug: auto-report-auto-submit
status: discussing
parent: main
```

## Problem

When `pipeline.auto_report: true` is set in config, mill-plan and mill-go auto-fire `mill-self-report` at end-of-work. The intent is hands-free bug filing after an autonomous pipeline run. However, the skill always presents a numbered candidate list and waits for the user to type which issues to file — blocking the pipeline until a human responds. This defeats the point of `auto_report`.

The fix is straightforward: when mill-self-report is invoked in auto-fire mode, it should file all distilled candidates immediately and print a summary, without prompting for confirmation.

## Scope

**In:**
- `mill-self-report/SKILL.md` — add `--auto` mode: when `--auto` argument is present, skip the numbered-list prompt and file all candidates automatically, then print the summary line.
- `mill-go/SKILL.md` — change the step-5 invocation from `/mill-self-report` (no arg) to `/mill-self-report --auto`.
- `mill-plan/SKILL.md` — change the Handoff invocation similarly to `/mill-self-report --auto`.

**Out:**
- Manual `/mill-self-report` invocations (with or without a steering argument) — always show the numbered list as today.
- The `millhouse-issue` skill — no changes.
- Any Python scripts — this is a pure SKILL.md change; no helper scripts are involved.
- The `pipeline.auto_report` config key itself — meaning unchanged; callers read it, skill does not.

## Decisions

### auto-mode signal: caller-passed `--auto` flag

- Decision: mill-go and mill-plan pass `--auto` as the argument to mill-self-report when they invoke it due to `auto_report: true`. The skill interprets `--auto` as "file all candidates without confirmation."
- Rationale: Explicit at the callsite. Manual invocations are unambiguous regardless of config value — a user typing `/mill-self-report` with no arg always gets the prompt. If the skill read config itself, `/mill-self-report` with no arg would silently auto-file when `auto_report: true`, which is surprising for an interactive user.
- Rejected: (B) skill reads `pipeline.auto_report` — can't distinguish auto-fire from manual no-arg invocation, leading to silent auto-filing on manual use.

### auto-mode still prints the summary line

- Decision: In `--auto` mode, after filing all candidates, print the one-line summary (`Filed N issues: <titles>` or `Filed 0 issues.`) as today.
- Rationale: The user can see what happened in the transcript. No blocking, but not completely silent either.
- Rejected: silent — hides filing activity; overkill to suppress.

### no filtering in auto-mode

- Decision: In `--auto` mode, all distilled candidates are filed; there is no threshold or severity filter.
- Rationale: The distillation step in mill-self-report already drops transient frustrations and non-reproducible observations. Anything that survives distillation is worth filing. Adding a secondary filter would complicate the skill without clear benefit.
- Rejected: file only "high-confidence" candidates — adds judgment call with no clear criteria.

## Technical context

All three affected files are pure SKILL.md — no Python scripts:

- [plugins/mill/skills/mill-self-report/SKILL.md](plugins/mill/skills/mill-self-report/SKILL.md) — Step 4 (present numbered list) is the blocking step. In `--auto` mode, skip Step 4 entirely and go directly to Step 5 (file all). Step 6 (summary) runs in both modes.
- [plugins/mill/skills/mill-go/SKILL.md](plugins/mill/skills/mill-go/SKILL.md) — Step 5 of the Handoff section (line 219): `invoke '/mill-self-report' directly with no argument` → change to `invoke '/mill-self-report --auto'`.
- [plugins/mill/skills/mill-plan/SKILL.md](plugins/mill/skills/mill-plan/SKILL.md) — Handoff section (line 146): `invoke '/mill-self-report' with no argument` → change to `invoke '/mill-self-report --auto'`.

The `millhouse-issue` skill is invoked per-candidate in Step 5 of mill-self-report. In `--auto` mode, this is called in a loop over all candidates without waiting for user selection. The invocation contract (`Skill tool with candidate title as argument`) is unchanged.

The argument-hint in mill-self-report's frontmatter currently says `[free-text steering]`. It should be updated to `[--auto | free-text steering]` to document the new flag.

## Testing

This is a pure SKILL.md change with no Python code — no unit tests apply. Manual verification:

- Invoke `/mill-self-report --auto` in a session that has candidate bugs → confirm all are filed without prompting.
- Invoke `/mill-self-report` (no arg) in a session with candidates → confirm numbered list still appears.
- Invoke `/mill-self-report "some steering text"` → confirm numbered list still appears with focused candidates.
- Run a full `mill-plan` session with `pipeline.auto_report: true` → confirm mill-self-report fires at handoff, files all candidates, and the pipeline continues to the "Plan complete" message without blocking.

## Q&A log

- **Q:** How does mill-self-report know it's in auto-fire mode vs. manually invoked? **A:** Caller passes `--auto` flag. Skill interprets presence of `--auto` as auto-file-all mode.
- **Q:** Should auto-mode still print a summary after filing? **A:** Yes — the summary line always runs in both modes.
- **Q:** Should auto-mode apply any filtering beyond the existing distillation step? **A:** No — anything that survives distillation is filed.
