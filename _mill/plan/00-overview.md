# Plan: mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check

```yaml
task: 'mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check'
slug: mill-plan-autonomy-and-validation-gaps
approved: false
started: 20260729-172007
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: context-completeness-check
    file: 01-context-completeness-check.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 2
    name: plan-guardrails-and-anti-pause
    file: 02-plan-guardrails-and-anti-pause.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: Batch ordering and same-file consolidation

- **Decision:** Batch 02 depends on Batch 01, and all three `mill-plan/SKILL.md` edits driven by this task's three gaps (fork guardrail #741, anti-pause rule #743, and the context-completeness fix-table row #742) land as separate cards within Batch 02 rather than being split across multiple batches.
- **Rationale:** #741 and #743 both edit `plugins/mill/skills/mill-plan/SKILL.md` (different sections — Phase: Plan vs. Phase: Plan Review). Splitting them into independent, non-dependent batches would trip `_check_parallel_modifies_overlap` (`plugins/mill/scripts/_plan_validate.py:998-1060`), since that check compares batches' `Edits:` sets pairwise without regard to which section of a file each batch touches. Landing every `mill-plan/SKILL.md` edit (plus the related `mill-go/SKILL.md` edit) in one batch removes the risk entirely. Making Batch 02 depend on Batch 01 additionally guarantees Card 6's fix-table row documents Batch 01's actual, already-implemented check behavior rather than a still-changing design.
- **Applies to:** all batches

### Decision: `context-completeness` scope stays file-path-shaped only

- **Decision:** The new `_check_context_completeness` validator check (Batch 01) flags only backtick-quoted tokens in a card's `Requirements:` prose that are file-path-shaped (contain `/` or end in `.py`, `.go`, `.cs`, `.ts`, `.md`, `.yaml`, `.yml`, `.json`) AND independently resolve to a real file (exists on disk, or is declared as a `Creates:` target anywhere in the plan). No broader identifier-matching (function/type/sentinel-name regex patterns) is added.
- **Rationale:** Broader identifier matching would require an ever-growing, language-specific pattern list across this multi-language codebase (Python, Go, C#); the file-path-shaped heuristic reuses the plan's own existing "all references are backtick-wrapped paths" convention with zero new grammar. Requiring independent resolvability before a token can be flagged eliminates the false-positive class (e.g. a JSON body key like `` `response.json` `` or a Go package-qualified identifier) at the source, per `_mill/discussion.md`'s `context-completeness` validator check design (#742) Decision.
- **Applies to:** Batch 01 (Cards 1-2); Batch 02 Card 6 documents this same scope in the fix-table row.

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
