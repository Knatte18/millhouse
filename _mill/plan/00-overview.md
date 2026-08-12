# Plan: mill-go-base: remove subprocess/psmux dispatch branches

```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
slug: 'mill-go-base-agent-dispatch-only'
approved: false
started: '20260812-083517'
parent: 'main'
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: regression-guard
    file: 01-regression-guard.md
    depends-on: []
    verify: null
  - number: 2
    name: strip-subprocess-dispatch
    file: 02-strip-subprocess-dispatch.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
  - number: 3
    name: treeguard-dedup
    file: 03-treeguard-dedup.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
  - number: 4
    name: extract-cold-path
    file: 04-extract-cold-path.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
  - number: 5
    name: renumber-and-siblings
    file: 05-renumber-and-siblings.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
```

## Shared Decisions

### Decision: strip-first-then-extract

- **Decision:** the whole subprocess/psmux surface is deleted from `SKILL.md` while every section is still in that one file (batch 2), and only then are the three cold-path sections moved out (batch 4).
  The discussion's `remove-psmux-cleanup-block` says the holistic cleanup block "must be stripped *there*, not left behind in `SKILL.md`" — that requirement is about the end state (the block and its call sites must not survive anywhere), and strip-then-extract satisfies it while doing the deletion once instead of twice.
- **Rationale:** deleting first keeps every subprocess branch inside a single file with a single set of anchors, so the `dispatch == subprocess` literal search is exhaustive by construction.
  Extracting first would force the same deletion pass to be re-run against four files.
- **Applies to:** all batches

### Decision: anchor-on-literal-text-not-line-numbers

- **Decision:** every deletion in batch 2 is located by its literal anchor text (`` If `dispatch == subprocess` ``, `**Subprocess/psmux poll-loop max-wait.**`, `**Per-batch session cleanup.**`, `**Holistic session cleanup.**`, `millpy-bg`), never by the line numbers recorded in `_mill/discussion.md`.
  Line numbers shift as soon as the first deletion lands.
- **Rationale:** the discussion's own "Technical context" section says so explicitly, and its line numbers were captured at commit `356da5e5`.
  They are useful as a cross-check on completeness, not as edit coordinates.
- **Applies to:** batch 2, batch 3

### Decision: existing-suite-is-the-per-batch-gate-until-the-new-guard-goes-green

- **Decision:** batches 2 and 3 verify against `test-guards.py`, `test-mill-go-variants.py`, and `test-skill-helper-drift.py` — the three existing tests that actually read `mill-go-base/SKILL.md`.
  The new guard (`test-mill-go-base-agent-only.py`) is written first (batch 1, `verify: null`) and becomes the gate from batch 4 onward, once the companion files it asserts on exist.
- **Rationale:** TDD as the discussion asked for, without a batch whose `verify:` is knowingly red.
  The three existing tests are not decorative here: they lock the wiki-cwd allowlist entry, the base-vs-variant machinery split, and the `#496` `reviews_dir` literal — all three are things this strip can plausibly break.
- **Applies to:** all batches

### Decision: twelve-tree-guard-checkpoints-not-ten

- **Decision:** the tree-guard de-duplication in batch 3 covers **12** checkpoint paragraphs, not the 10 the discussion's `deduplicate-tree-guard-checkpoint-paragraphs` Decision names.
- **Rationale:** `SKILL.md` states its own count inline ("All 11 other tree-guard checkpoints in this file (5 more in this section, 7 in `## Holistic code review`)"), which totals 12 with the one that sentence is attached to.
  A grep of `_treeguard.check_and_restore` confirms 12 occurrences.
  The batch enumerates them by anchor rather than by count.
- **Applies to:** batch 3

### Decision: holistic-crash-recovery-loses-its-bg-log-branch

- **Decision:** `## Holistic code review` step 1's three-way crash-recovery branch collapses to two ways.
  Branch (c) — "no review file, bg log exists for round H", its `_bg.is_bg_worker_alive` probe, and the `.scratch/bg-*-review-code-holistic-r{H}.log` glob inside the inline-Python helper — is deleted along with the rest of the `millpy-bg` surface.
- **Rationale:** `.scratch/bg-*.log` files are written only by `millpy-bg`, which `mill-go-base` no longer invokes, so branch (c) can never fire.
  The discussion's deletion inventory does not name it (it lists holistic dispatch points at lines 1127/1178 only), but leaving it would keep three `millpy-bg` references and one `mill-bg` poll loop alive and fail the regression guard's own assertion.
- **Applies to:** batch 2

### Decision: infrastructure-stuck-type-survives-the-strip

- **Decision:** the `stuck_type: infrastructure` bullets in `### Stuck escalation` and in the holistic `REQUEST_CHANGES` branch are **kept**, with their `millpy-bg`-specific wording ("bg worker died, likely logout", "re-invoke `millpy-bg` with a fresh CLI") replaced by a dispatch-neutral re-dispatch instruction.
- **Rationale:** `infrastructure` is a `stuck_type` the SKILL must still be able to route, and deleting the classification would be a behaviour change well outside a dead-path removal.
  Only the wording that names the dead mechanism goes.
- **Applies to:** batch 2

### Decision: drift-test-must-follow-the-extracted-content

- **Decision:** `test-skill-helper-drift.py` is updated in the same batch as the extraction (batch 4): its helper-reference scan is widened to include `plugins/mill/skills/mill-go-base/*.md`, and its `#496` lock on the literal `reviews_dir = hub / '_mill/reviews'` is re-pointed so it searches `SKILL.md` plus the companion files rather than `SKILL.md` alone.
- **Rationale:** that literal lives inside the holistic crash-recovery helper, which moves to `holistic-review.md`; without this change the extraction turns a passing lock into a false failure, and every `_<module>.<fn>(` reference in 524 extracted lines silently drops out of drift coverage.
  This is a correctness defect introduced by this task, so fixing it is in scope on the same footing as the discussion's `fix-only-falsified-sibling-references` Decision.
- **Applies to:** batch 4

### Decision: companion-files-carry-no-wiki-access-banner

- **Decision:** the three companion files do not reproduce `SKILL.md`'s `> Wiki access: never cd .wiki/ …` banner line.
- **Rationale:** `test-guards.py`'s `no_wiki_cwd` check walks every `*.md` under `plugins/mill/skills/` and allowlists by exact repo-relative path.
  `mill-go-base/SKILL.md` is allowlisted; the companion files are not.
  Copying the banner would make three new files fail that check for no benefit — the banner is a reminder, not machinery.
- **Applies to:** batch 4

### Decision: renumber-last-in-one-sweep

- **Decision:** Agent-mode step 1 is deleted in batch 2 but the surviving steps keep their numbers (2–7) until batch 5, which renumbers them to 1–6 and sweeps every reference across `SKILL.md`, the three companion files, and `mill-go2/SKILL.md` in one pass.
- **Rationale:** the companion files do not exist until batch 4, so a single five-file sweep is only possible afterwards.
  Renumbering earlier would mean renumbering text that batch 2 and batch 4 then delete or relocate.
  The intermediate "list starts at 2" state is internal to this task and never ships.
- **Applies to:** batch 2, batch 5

### Decision: reference-inventory-counts-are-a-cross-check-not-a-worklist

- **Decision:** batch 5's sweep enumerates `step N` occurrences from the post-batch-4 files themselves and classifies each against the four numbered-step namespaces; the per-token counts recorded in the discussion are used only to sanity-check that nothing was missed.
- **Rationale:** those counts were taken from the pre-strip file, and batches 2–4 delete and relocate large amounts of text, so most of them are already stale by the time the sweep runs.
  A worked example: the discussion records `step 6.5` ×1 for `mill-go2/SKILL.md`, but that file actually names `step 6.5.2` and `6.5.1` and no bare `6.5`.
- **Applies to:** batch 5

### Decision: done-gate-stays-null

- **Decision:** `pipeline.done_gate` is left at its current `null` and no `mill-config.yaml` edit is planned.
- **Rationale:** the hub `mill-config.yaml` lives in the `wts/millhouse` worktree, outside this task worktree, and the discussion's `keep-dispatch-config-and-resolver` and Scope sections put all config changes out of scope.
  Coverage is not lost: batches 2–5 each run the three existing tests that read `SKILL.md`, plus the new guard from batch 4 on.
- **Applies to:** all batches

### Decision: no-renames-in-this-task

- **Decision:** the extraction in batch 4 is `Creates:` of three new files plus deletion of the corresponding prose from `SKILL.md`, not `Moves:`.
- **Rationale:** `Moves:` expresses whole-file renames.
  Here three *sections* leave a file that itself survives; there is no source file being renamed, so no batch carries a `## Rename mechanic` section.
- **Applies to:** batch 4

## All Files Touched

- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/handoff.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-go-base/resume.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/unit_tests/test-mill-go-base-agent-only.py`
- `plugins/mill/unit_tests/test-skill-helper-drift.py`
