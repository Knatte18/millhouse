# Batch: mill-plan-handoff-guard

```yaml
task: Accumulated bug fixes
batch: mill-plan-handoff-guard
number: 2
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fix bug 2 (mill-plan-approved-false) by adding an `approved: true` assertion at the very start of Phase: Handoff in `mill-plan/SKILL.md`. After this batch, mill-plan can never write `phase: planned` to status.md while `plan/00-overview.md` still has `approved: false` — the guard halts the run with a clear recovery instruction instead. This is a SKILL.md documentation/instruction change only: no Python edits, no tests, no executable surface. `verify: null` because there is no runnable check (mill-go's own entry-step 6 `approved: true` check serves as the runtime backstop).

## Cards

### Card 5: add `approved: true` guard at start of Phase: Handoff

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-plan/SKILL.md`, modify the `### Phase: Handoff` section (currently at line 182):
  - Before the existing first sentence (``_status.append_phase(status_path, "planned", _timestamp.now_utc_iso())`. Commit+push.``), insert a new opening paragraph that defines the guard. The new opening text must be a single instruction paragraph followed by the existing `_status.append_phase` line. Concretely:
    - State: "**Guard.** Read `plan_dir / "00-overview.md"` and parse the `approved:` field from the top fenced yaml block. If it is not the literal boolean `true`, halt with: ``BLOCKED: mill-plan Handoff guard -- plan/00-overview.md has approved: false. Plan review did not complete. Re-run /mill-plan to enter Phase: Plan Review.``"
    - State that the guard runs *before* any `_status` mutation, so a guard failure leaves status.md untouched and the operator can re-enter cleanly.
    - Specify the parse approach: extract the YAML block via the existing pattern (``re.search(r"```yaml(.*?)```", overview_text, re.DOTALL)``), then read `approved:` with `yaml.safe_load(yaml_text)["approved"]`. Reject string `"true"` — the value must be the YAML boolean (overview template writes `approved: false`, the flip in step 4a/4b/4c writes `approved: true` as bare YAML).
    - The halt message must be ASCII only (use `--` not em-dash).
  - Do not alter any other section. Do not touch the `auto_report` paragraph or the final "Plan complete." report line. The guard is the new first instruction inside Phase: Handoff; the rest follows unchanged.
  - The reference to mill-go's own `approved: true` entry-step-6 check in `plugins/mill/skills/mill-go/SKILL.md` (line 94) is shown to the implementer as Context: only — do not edit mill-go. This reference exists so the implementer can phrase the halt message consistently with mill-go's check (both refer to "approved: true" in the overview frontmatter).
- **Commit:** `fix(mill-plan): guard Phase Handoff against approved: false`

## Batch Tests

`verify: null` — SKILL.md is instruction text consumed by the planner skill itself, not executable code. The fix is validated by:

1. The implementer reading the modified Phase: Handoff section back and confirming the guard text is present, runs *before* `_status.append_phase`, and uses the parse approach specified in Card 5's Requirements.
2. The code-reviewer in the subsequent review round checking that the halt message wording matches the discussion.md's specified message (modulo ASCII), and that the YAML-block parse instruction is unambiguous.

No unit-test surface exists for SKILL.md edits in this repo.
