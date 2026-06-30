# Batch: report-to-tasks-skill

```yaml
task: "Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis"
batch: report-to-tasks-skill
number: 3
cards: 1
verify: null
depends-on: [1, 2]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

This batch writes `mill-report-to-tasks`, the new entry skill that takes a local `sandbox-report.json`-shaped file (or any file on the `sandbox-report` contract) and drives it through `mill-triage-to-tasks` with no GitHub dependency at all. It depends on batch 1 (`_sandbox_report.read()` must exist to validate the input file) and batch 2 (`mill-triage-to-tasks` must exist to invoke). It can run in parallel with batch 4 — the two entry skills touch entirely different files and neither depends on the other, only on batches 1 and 2.

No batch-local decisions beyond `## Shared Decisions` in the overview.

## Cards

### Card 5: `mill-report-to-tasks` entry skill

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
  - `plugins/mill/scripts/_sandbox_report.py`
  - `plugins/mill/skills/mill-triage-to-tasks/SKILL.md`
  - `plugins/mill/templates/triage-report.schema.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-report-to-tasks/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - **Frontmatter:** `name: mill-report-to-tasks`, `description:` one line describing it as draining a local JSON triage report (sandbox-report contract) into Home.md tasks via `mill-triage-to-tasks`, with no GitHub dependency. Same `---` frontmatter format as `mill-ghissues-to-tasks/SKILL.md`.
  - **Invocation:** `/mill-report-to-tasks <path-to-json>` — a required positional argument, no default-path fallback. State this explicitly near the top of the file (mirror how `mill-fold/SKILL.md` documents its invocation forms).
  - **Entry checks** (mirror `mill-ghissues-to-tasks/SKILL.md`'s `## Entry checks` section, two checks instead of `gh auth status`):
    1. `.millhouse/wiki/` junction must exist. If not, stop and tell the user to run `mill-setup` — exact same check and message as `mill-ghissues-to-tasks/SKILL.md` entry check 2 (this skill writes the wiki via `mill-triage-to-tasks` just like ghissues does, so the same precondition applies).
    2. The given path must exist as a file, parse as JSON, and pass `_sandbox_report.read()` validation. On any failure (missing path, invalid JSON, `SandboxReportError`), stop with the error message `_sandbox_report.read()` raised — do not catch and reword it.
  - **Step 1 — Read and validate the file.** Call `_sandbox_report.read(path)` (this doubles as entry check 2 and produces the contract dict — do not call it twice). Result is the full contract envelope: `{"source": "sandbox-report", "meta": ..., "items": [...], "ref_prefix": "", "detail_hint": None, "embed_body": True}`.
  - **Step 2 — Empty-items short-circuit.** If `contract["items"]` is an empty list, this is the entry skill's own "nothing to do" detection (per `_mill/discussion.md` Decision "`mill-report-to-tasks` takes a required positional path arg and validates it as an entry check" — case 1, knowable from the file alone). Print a one-line "nothing to do — 0 items in <path>" message and stop. Do NOT write `.scratch/triage-contract.json` and do NOT invoke `mill-triage-to-tasks` in this case.
  - **Step 3 — Hand off to the shared analysis skill.** Write the full contract dict to `.scratch/triage-contract.json` (`json.dump`, indent for readability). Invoke `mill-triage-to-tasks` via the Skill tool (same pattern used elsewhere in this project to invoke `mill-receiving-review`) and let it run its full Steps 1–7 (read contract, read wiki tasks, group, propose, wait for approval, apply, write results, report). This skill does not re-implement any part of that flow.
  - **Step 4 — No post-processing.** After `mill-triage-to-tasks` completes, this skill performs no further action — there is no GitHub issue to close for `sandbox-report` items. If `.scratch/triage-result.json` exists (meaning at least one item was consumed), this skill does not need to read it; `mill-triage-to-tasks`'s own Step 7 report already covers the operator-visible summary. State this explicitly in the skill text so a future maintainer does not assume a missing post-step is an oversight: "Unlike `mill-ghissues-to-tasks`, there is nothing to close — `mill-triage-to-tasks`'s report is the final output of this skill."
  - **Rules section:** mirror the relevant subset of `mill-ghissues-to-tasks/SKILL.md`'s `## Rules` (one-shot model inherited from `mill-triage-to-tasks`; skipped items untouched; writes only on `approve`) plus one rule specific to this skill: "No GitHub side effects of any kind — this skill never imports or shells out to `gh`."
- **Commit:** `feat(mill-report-to-tasks): add sandbox-report entry skill`

## Batch Tests

`verify: null` — pure skill/markdown batch with no runnable surface, consistent with `_mill/discussion.md` Testing. Manual end-to-end verification (already named in `_mill/discussion.md` Testing): run `/mill-report-to-tasks` against a hand-crafted `sandbox-report.json` fixture once this batch and batch 2 are both implemented, to confirm the new path produces a proposal, accepts approval, and writes the wiki with no GitHub calls.
