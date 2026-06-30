# Plan: Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis

```yaml
task: "Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis"
slug: mill-ghissues-source-adapter
approved: false
started: "20260630T191500Z"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: contract-adapters
    file: 01-contract-adapters.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-gh-issues.py test-sandbox-report.py"
  - number: 2
    name: triage-to-tasks-skill
    file: 02-triage-to-tasks-skill.md
    depends-on: [1]
    verify: null
  - number: 3
    name: report-to-tasks-skill
    file: 03-report-to-tasks-skill.md
    depends-on: [1, 2]
    verify: null
  - number: 4
    name: ghissues-to-tasks-trim
    file: 04-ghissues-to-tasks-trim.md
    depends-on: [1, 2]
    verify: null
  - number: 5
    name: skills-index-regen
    file: 05-skills-index-regen.md
    depends-on: [3, 4]
    verify: null
```

## Shared Decisions

### Decision: the triage-report contract shape is fixed across every batch

- **Decision:** Every batch that produces or consumes the contract uses exactly this envelope shape: `{"source": "ghissues"|"sandbox-report", "meta": {...}, "items": [{"ref": str, "title": str, "body": str}, ...], "ref_prefix": str, "detail_hint": str|null, "embed_body": bool}`. `ref_prefix`/`detail_hint`/`embed_body` are set once per adapter (ghissues: `"#"`, `"Run 'gh issue view #{ref}' for full detail."`, `False`; sandbox-report: `""`, `null`, `True`). `meta` is adapter-owned passthrough that the analysis skill never reads.
- **Rationale:** This is the seam the whole task is organized around (`_mill/discussion.md` Decisions "triage-report contract carries ref-display fields" and "`_gh_issues.to_contract()` is a new function"). Any drift between batches breaks the handoff.
- **Applies to:** all batches.

### Decision: per-Sources-bullet rendering, including fold-ins

- **Decision:** `detail_hint` and `embed_body` apply **per Sources bullet**, never once per task. Every `- Sources: <ref_prefix><ref> — <title>` bullet — whether on a new grouped task or appended to an existing task via fold-in — is immediately followed by that same item's own `detail_hint` line (with `{ref}` substituted from that item) when `detail_hint` is non-null, and by that item's `body` text when `embed_body` is true. This is the one accepted, intentional deviation from "ghissues output stays unchanged" (today's ghissues output used one ambiguous trailing hint line for a whole task; this plan replaces it with one hint line per source, which is identical output for the common single-source case).
- **Rationale:** `_mill/discussion.md` Decision "`detail_hint` and `embed_body` apply per source bullet, including fold-ins" (added during discussion-review rounds 2–3 to close two real gaps: ambiguous multi-source `{ref}` substitution, and sandbox QA detail being silently dropped on fold-in).
- **Applies to:** `triage-to-tasks-skill` (batch 2).

### Decision: close-with-pointer is adapter-only, never in the shared skill

- **Decision:** `mill-triage-to-tasks` (batch 2) never calls `gh` and never branches on `source`. It writes the wiki and a results file (`.scratch/triage-result.json`) listing each consumed item's `ref` and route (`new_task: <slug>` / `fold_in: <slug>` / `skipped`). Closing GitHub issues with a pointer comment is entirely the ghissues entry skill's job (batch 4), reading the results file back and mapping `new_task` → `Consolidated into wiki task: <slug>`, `fold_in` → `Folded into wiki task: <slug>` (byte-identical to today's strings and to `/mill-fold`'s fold-in string).
- **Rationale:** `_mill/discussion.md` Decision "Close-with-pointer stays out of the shared skill entirely".
- **Applies to:** `triage-to-tasks-skill` (batch 2), `ghissues-to-tasks-trim` (batch 4).

### Decision: three fixed scratch handoff files

- **Decision:** `.scratch/triage-contract.json` (written by the entry skill, read by `mill-triage-to-tasks`), `.scratch/triage-proposal.md` (written by `mill-triage-to-tasks`, the operator-facing consolidated proposal), `.scratch/triage-result.json` (written by `mill-triage-to-tasks` on approval, read back by the entry skill). Same naming convention as today's `.scratch/issues.json` / `.scratch/wiki-tasks.json` / `.scratch/ghissues-to-tasks-proposal.md`.
- **Rationale:** `_mill/discussion.md` Decision "Handoff between skills uses three fixed scratch files".
- **Applies to:** `triage-to-tasks-skill` (batch 2), `report-to-tasks-skill` (batch 3), `ghissues-to-tasks-trim` (batch 4).

### Decision: unclaimed-only fold guard and slug rules are unchanged

- **Decision:** `mill-triage-to-tasks`'s fold-in routing reuses the existing guard verbatim: a fold target must have `status is None and not deferred` (`plugins/mill/scripts/millpy-fold.py`'s `unclaimed-only-allowlist` decision); any other state routes the item to a new task or skip instead. New-task slugs validate against `[a-z][a-z0-9-]*` and must not collide with an existing slug, exactly as today's `mill-ghissues-to-tasks` Step 3.
- **Rationale:** `_mill/discussion.md` Technical context — `millpy-fold.py` cross-reference; preserves operator-visible behavior parity with `/mill-fold`.
- **Applies to:** `triage-to-tasks-skill` (batch 2).

### Decision: ASCII-only stdout in new Python modules

- **Decision:** Any `print()` in `_sandbox_report.py` uses ASCII only (no em-dash, no `->`; use ` -- ` / ` -> ` spelled out) per project convention — Windows cp1252 consoles crash on non-ASCII stdout.
- **Rationale:** Project CLAUDE.md convention; mirrors `_gh_issues.py`'s existing stderr prints.
- **Applies to:** `contract-adapters` (batch 1).

### Decision: verify commands stay scoped per batch

- **Decision:** Only batch 1 has a runnable Python surface; its `verify:` runs exactly the two affected test files via `run-all.py --only`. Batches 2–5 are pure skill/doc/index edits with no test suite to run (`_mill/discussion.md` Testing: "No unit tests planned for the markdown-orchestrated skill steps"), so their `verify:` is `null`.
- **Rationale:** Avoids an unbounded `run-all.py` invocation; matches the project's per-batch scoping convention.
- **Applies to:** all batches.

## All Files Touched

- `SKILLS.md`
- `plugins/mill/scripts/_gh_issues.py`
- `plugins/mill/scripts/_sandbox_report.py`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-report-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-triage-to-tasks/SKILL.md`
- `plugins/mill/templates/triage-report.schema.md`
- `plugins/mill/unit_tests/test-gh-issues.py`
- `plugins/mill/unit_tests/test-sandbox-report.py`
