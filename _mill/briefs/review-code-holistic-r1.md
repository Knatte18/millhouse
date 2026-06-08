**You are a READ-ONLY reviewer. You MUST NOT call Edit, Write, Bash, or any
tool that modifies files or runs commands. You MUST NOT make git commits.
Your sole output is the review file in the format below. If you find issues,
REPORT them — do NOT fix them.**

You are an independent code reviewer for **Track _mill/briefs/ instead of gitignoring them**. You evaluate the complete implementation (every batch) against the approved plan and produce a structured review.

Reviewer model: **sonnethigh**. Round **1**.

**CRITICAL: Do NOT request tool calls. All content you need is in this prompt.**
**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**
**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**
**CRITICAL: Do NOT use Write. Return review as text.**

## Constraints


## Files included (N=25)

- C:\Code\millhouse\wts\track-task-briefs\_mill\plan\00-overview.md
- C:\Code\millhouse\wts\track-task-briefs\_mill\plan\01-reviewer-tooluse-convention.md
- C:\Code\millhouse\wts\track-task-briefs\_mill\plan\02-track-briefs.md
- C:\Code\millhouse\wts\track-task-briefs\_mill\plan\03-review-mode-tests.md
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_reviewers.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\mill-agents.yaml
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\mill-config.yaml
- C:\Code\millhouse\wts\track-task-briefs\mill-config.yaml
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\review-output.schema.md
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_test_registry.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\_test_registry.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-reviewers.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-large-prompt-switch.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-config.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-code.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-discussion.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-plan.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\skills\mill-go\SKILL.md
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\skills\mill-plan\SKILL.md
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_gitignore.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-gitignore-phase.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_review_code.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_review_common.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_reviewer_single.py
- C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-review-common.py

## Plan + source content (overview + batch files + referenced source + ancestor creates)
--- FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\00-overview.md ---
# Plan: Track _mill/briefs/ instead of gitignoring them

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
slug: track-task-briefs
approved: true
started: "20260608-072059"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: reviewer-tooluse-convention
    file: 01-reviewer-tooluse-convention.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-large-prompt-switch.py test-config.py
  - number: 2
    name: track-briefs
    file: 02-track-briefs.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-gitignore-phase.py
  - number: 3
    name: review-mode-tests
    file: 03-review-mode-tests.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
```

## Shared Decisions

### Decision: tool-use is the default name, _bulk is the suffixed exception

- **Decision:** Across the entire `mill-agents.yaml` catalogue, the unsuffixed name is
  the tool-use variant with an explicit `tooluse: true`; the `_bulk` suffix marks the
  bulk variant with `tooluse: false`. Every former `*_tool` name is removed (folded into
  the unsuffixed name). Every model/effort combo gets a symmetric `<name>` + `<name>_bulk`
  pair. All reviewer roles in config reference unsuffixed (tool-use) names.
- **Rationale:** Tool-use is now the norm; the naming must be uniform with no mixed
  formats (`*_tool` for tool-use here, unsuffixed-bulk there).
- **Applies to:** all batches (batch 1 implements it; batches 2-3 assume it).

### Decision: bulk is demoted, not deleted

- **Decision:** The bulk code path (`_read_for_bulk`, `run_bulk`, the bulk artefact
  assembly, the large-prompt `tooluse` override) is retained, reachable only through
  `_bulk` agents. No reviewer role references a `_bulk` agent today.
- **Rationale:** Cheap escape hatch; deleting it is a large, irreversible diff for no
  present benefit.
- **Applies to:** all batches.

### Decision: code default `tooluse` stays False; base entries set it explicitly

- **Decision:** `_reviewers.py`'s absent-`tooluse`→`False` default is unchanged. Tool-use
  is expressed by an explicit `tooluse: true` on each base entry, not by flipping the
  code default.
- **Rationale:** Explicit flags are self-documenting; the discussion specified adding
  `tooluse: true` to each tool-use definition.
- **Applies to:** batch 1.

### Decision: briefs are committed on the task branch via mill-go and mill-plan only

- **Decision:** Briefs (`_mill/briefs/`, both `.md` briefs and `.out.md` responses) are
  committed by folding `_mill/briefs/` into the existing task-branch state commits of
  mill-go (per-batch approve, holistic approve, done) and mill-plan (plan-review approve
  / plan-fix). No new dedicated commit; no CLI-side commit.
- **Rationale:** Those orchestrators already write the response file and already commit
  `_mill/` state; incremental commits preserve the audit trail even if a run dies midway.
- **Applies to:** batch 2.

### Decision: mill-start and mill-merge-in are OUT of scope for brief tracking

- **Decision:** Discussion-review briefs are written under the **hub** worktree
  (`millpy-review-discussion.py` sets `project_root = resolve_hub_path()`, line 69), not
  the task worktree, so they are not on the task branch and cannot be committed to it —
  relocating them is a separate design change. mill-merge-in's briefs are task-side but it
  exposes no augmentable task-branch commit pathspec and its briefs would be removed by
  mill-merge's `git rm -r _mill/` moments later. Both are excluded.
- **Rationale:** Correctness — committing hub-side briefs to the task branch is impossible
  without a separate change; merge-in tracking is marginal. This corrects the discussion's
  inclusion of mill-start, which the discussion reviewer did not catch.
- **Applies to:** batch 2.

### Decision: the `.gitignore` is NOT touched

- **Decision:** No change to `.gitignore` or `_gitignore.GLOB_ENTRIES`. Briefs are already
  un-ignored on this branch; the only work is to commit them and lock the un-ignored state
  with a test.
- **Rationale:** `git check-ignore _mill/briefs/x.md` exits 1; `GLOB_ENTRIES` has no
  briefs entry. The proposal's `.gitignore:40` premise was stale.
- **Applies to:** batch 2.

### Decision: SKILL edits take effect only after merge + cache refresh

- **Decision:** mill-go/mill-plan/SKILL edits change source; the running orchestrator loads
  SKILLs from the plugin cache. So this task's own mill-go run uses the OLD (cached) SKILLs
  — the brief-commit behavior does not self-apply during this implementation. This is
  expected and not a defect.
- **Rationale:** Avoids a false expectation that batch 2's behavior is observable in this
  task's own run.
- **Applies to:** batch 2 (reviewer context).

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/integration_tests/test-review-code.py`
- `plugins/mill/integration_tests/test-review-discussion.py`
- `plugins/mill/integration_tests/test-review-plan.py`
- `plugins/mill/scripts/_test_registry.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-agents.yaml`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/unit_tests/_test_registry.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-gitignore-phase.py`
- `plugins/mill/unit_tests/test-large-prompt-switch.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-reviewers.py`

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\00-overview.md ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\01-reviewer-tooluse-convention.md ---
# Batch: reviewer-tooluse-convention

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
batch: reviewer-tooluse-convention
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-large-prompt-switch.py test-config.py
depends-on: []
```

## Batch Scope

Flip the reviewer naming convention across the whole catalogue and every consumer:
tool-use becomes the unsuffixed default (explicit `tooluse: true`), bulk becomes the
`_bulk`-suffixed opt-in (`tooluse: false`), and all `*_tool` names are retired. This
batch rewrites `mill-agents.yaml`, repoints all config roles, updates the test-registry
fixtures and the unit tests that assert on them, updates the integration-test configs,
and locks the convention with a catalogue test. It is one batch because every card is a
facet of a single rename and they share the same small set of config/registry files. No
production code logic changes — flipping reviewers to `tooluse: true` is what stops
bulking (the prepare stage already branches on mode), so the bulk code is reached only
via the new `_bulk` names.

## Cards

### Card 1: Rewrite mill-agents.yaml to the symmetric tool-use/_bulk scheme

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite the catalogue so that for each distinct model/effort/provider
  combo currently present there are exactly two entries: an unsuffixed entry with an
  explicit `tooluse: true` (the tool-use default) and a `<name>_bulk` entry with
  `tooluse: false`. Remove every `*_tool` key (its behaviour is now the unsuffixed name).
  Preserve each entry's existing `model`, `provider`, `effort`, `timeout`, and
  `type: single` fields; only add the `tooluse` flag. The 10 combos to produce as
  `<name>` + `<name>_bulk` pairs: `g25flash`, `g25pro`, `g3flash_preview` (provider
  `gemini`); `haiku`; `opushigh`, `opusmax`, `opusmedium` (provider `claude`, model
  `claude-opus-4-7`, efforts high/max/medium); `sonnethigh`, `sonnetmax`, `sonnetmedium`
  (provider `claude`, model `claude-sonnet-4-6`, efforts high/max/medium). Result: 20
  entries. Keep the file's existing header comment, updating it to describe the new
  convention; in that comment note that `tooluse` is consumed only by reviewer dispatch
  and is irrelevant for entries used as implementer/fixer/merge models (e.g. `haiku`), so
  `tooluse: true` on such an entry is harmless and the convention still applies uniformly.
- **Commit:** `refactor(agents): make tool-use the default name, _bulk the suffixed exception`

### Card 2: Point reviewer roles and the schema example at tool-use names

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both `mill-config.yaml` files, repoint every reviewer role to a
  tool-use (unsuffixed) name: `roles.discussion-review.holistic.reviewer` `sonnetmax_tool`
  → `sonnetmax`; `roles.plan-review.holistic.reviewer` stays `sonnetmax` (now tool-use);
  `roles.plan-review.batch.reviewer` (if non-null in the template) likewise unsuffixed;
  `roles.code-review.holistic.reviewer` stays `sonnethigh`; `merge.model` stays
  `sonnethigh`. No role may reference a `*_tool` or `*_bulk` name. Keep the plugin template
  and the hub `mill-config.yaml` in sync per CLAUDE.md. In `review-output.schema.md`,
  update the `reviewer_model` metadata-fields table row (currently
  `(e.g. \`sonnetmax\`, \`sonnetmax_tool\`)`) to drop `sonnetmax_tool`, e.g.
  `(e.g. \`sonnetmax\`, \`sonnethigh\`)`. The line-14 example is already `sonnetmax` and
  needs no change. Confirm `grep sonnetmax_tool plugins/mill/templates/review-output.schema.md`
  returns nothing afterward.
- **Commit:** `refactor(config): point reviewer roles at tool-use names`

### Card 3: Update test-registry baseline and the assertions that depend on it

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/_test_registry.py`
  - `plugins/mill/unit_tests/_test_registry.py`
  - `plugins/mill/unit_tests/test-reviewers.py`
  - `plugins/mill/unit_tests/test-large-prompt-switch.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both `_test_registry.py` copies, change `make_minimal_registry`'s
  baseline so it contains `sonnetmax` with explicit `tooluse: True` (tool-use) and a new
  `sonnetmax_bulk` entry with `tooluse: False`; remove the `sonnetmax_tool` key. Update the
  docstring line "Contains sonnetmax (bulk) and sonnetmax_tool (tool-use)..." to match.
  Then fix the consumers so each assertion still tests its original intent:
  in `test-reviewers.py`, the inline-YAML registry test that asserts
  `registry["sonnetmax_tool"]["tooluse"] is True` → rename the fixture key to a tool-use
  name and assert against it; the resolver test asserting `resolve(registry, "sonnetmax")`
  yields `tooluse is False  # defaulted` → point it at a spec that OMITS `tooluse`
  entirely (construct an inline no-`tooluse` spec) so it still verifies the default-False
  path, since baseline `sonnetmax` now sets `tooluse: true` explicitly. In
  `test-large-prompt-switch.py` and `test-config.py`, replace `sonnetmax_tool` with
  `sonnetmax`, and use `sonnetmax_bulk` wherever the test's intent is a bulk/`tooluse:false`
  reviewer. After editing, confirm `grep sonnetmax_tool plugins/mill/unit_tests` returns
  no remaining references.
- **Commit:** `test(reviewers): update fixtures and assertions to the new reviewer naming`

### Card 4: Update integration-test reviewer configs

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/integration_tests/test-review-code.py`
  - `plugins/mill/integration_tests/test-review-discussion.py`
  - `plugins/mill/integration_tests/test-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each integration test's inline `_CONFIG_YAML`, update reviewer
  names to the new convention: `discussion.holistic: sonnetmax_tool` → `sonnetmax`;
  `plan.batch: sonnetmax`, `plan.holistic: sonnetmax`, and `code.reviewer: sonnetmax`
  stay `sonnetmax` (now tool-use). If a test deliberately exercises bulk behaviour, use
  `sonnetmax_bulk` instead; otherwise tool-use `sonnetmax`. Every referenced name must
  exist in the catalogue after Card 1.
- **Commit:** `test(integration): update reviewer names to the tool-use convention`

### Card 5: Lock the catalogue naming convention with a test

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a test (e.g. `test_agents_catalogue_naming_convention`) that loads
  `plugins/mill/templates/mill-agents.yaml` (resolve the path via the module's existing
  `HUB` root pattern) and asserts every entry obeys the convention: a key that does NOT
  end in `_bulk` has `tooluse` present and `True`; a key ending in `_bulk` has `tooluse`
  present and `False`; and no key ends in `_tool`. Follow the existing test style in the
  file (return int error count or assert-based, matching siblings). Add a short comment in
  the test noting that `tooluse` is reviewer-only and the convention is applied uniformly,
  so entries used as implementer/merge models (e.g. `haiku`) still assert `tooluse: True`
  by design — this is not an oversight.
- **Commit:** `test(agents): lock the tool-use/_bulk naming convention`

## Batch Tests

`verify` runs `test-reviewers.py`, `test-large-prompt-switch.py`, and `test-config.py`
via `run-all.py --only` — the three unit suites that consume the test-registry baseline
or reference reviewer names and are affected by Cards 3 and 5. The integration tests
(`test-review-*.py`) invoke a real LLM and are NOT part of `verify`; Card 4 keeps their
configs internally consistent and is validated by review. `mill-agents.yaml`,
`mill-config.yaml`, and `review-output.schema.md` are data/doc files with no direct unit
test beyond the Card 5 convention test (which runs inside `test-reviewers.py`).

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\01-reviewer-tooluse-convention.md ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\02-track-briefs.md ---
# Batch: track-briefs

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
batch: track-briefs
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-gitignore-phase.py
depends-on: []
```

## Batch Scope

Make agent briefs and responses part of the committed task record. Two orchestrator
SKILLs (mill-go, mill-plan) gain `_mill/briefs/` in the pathspec of the task-branch state
commits they already make, so briefs accumulate on the branch and are preserved under the
`archive/<slug>` tag (mill-merge's existing `git rm -r _mill/` sweeps them from the squash
diff). The agent-response filename is renamed `<brief>.md.out` → `<brief>.out.md` so it is
a readable Markdown file. A unit test locks in that briefs are never re-added to the
managed `.gitignore` block. These are mostly Markdown SKILL edits with no runnable surface
(verified by review); only the gitignore test is executable. The SKILL edits take effect
after merge + cache refresh, not in this task's own run (see Shared Decisions).

## Cards

### Card 6: Rename the response file to .out.md and commit mill-go briefs

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `## Agent-mode dispatch` section: (a) Step 4 ("Capture output")
  and Step 5 (`--agent-output`) currently use `<brief_path>.out`. Change the response-file
  path to the brief path with its trailing `.md` replaced by `.out.md` (for a brief
  `foo-r1.md` the response is `foo-r1.out.md`). State the rule explicitly in both steps so
  any SKILL that references this pattern (mill-plan, mill-start) inherits it. (b) Add
  `_mill/briefs/` to the `git -C <worktree> add` pathspec of the task-branch commits that
  finalize a unit of work, leaving their commit messages unchanged: the per-batch approve
  commit (`mill-go: approve batch {batch_name}`), the per-batch review-disabled approve
  commit (`mill-go: approve batch {batch_name} (per-batch review disabled)`), the
  holistic-approve commit (`mill-go: holistic approve {slug}`), and the done commit
  (`mill-go: done {slug}`). Do NOT add `_mill/briefs/` to prepare, blocked, or
  holistic-reviewing commits.
- **Commit:** `feat(mill-go): track briefs and rename response file to .out.md`

### Card 7: Commit plan-review briefs in mill-plan

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `_mill/briefs/` to the `git -C <worktree> add` pathspec of the
  plan-review terminus commits that already stage `<plan_dir> <reviews_dir> <status_path>`:
  the approve commit in step 4a (`mill-plan: approve plan for {slug}`), the NIT/approve
  fix commit in steps 4b and 4c, and the blocking plan-fix commit in step 4d
  (`mill-plan: plan-fix round {N} for {slug}`). Leave commit messages unchanged. Do NOT add
  it to the write-plan commit (step at line ~90 — no briefs exist yet) or the validator-fix
  commit (no LLM brief produced).
- **Commit:** `feat(mill-plan): track plan-review briefs on the task branch`

### Card 8: Lock that briefs stay out of the managed .gitignore block

- **Context:**
  - `plugins/mill/scripts/_gitignore.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a test (e.g. `test_glob_entries_excludes_briefs`) asserting that no
  entry in `_gitignore.GLOB_ENTRIES` contains the substring `_mill/briefs` — locking in
  that a future managed-block regeneration cannot silently re-ignore briefs. Follow the
  file's existing test style (it imports `GLOB_ENTRIES` and returns an int error count).
- **Commit:** `test(gitignore): assert briefs are not in the managed ignore block`

## Batch Tests

`verify` runs only `test-gitignore-phase.py` (Card 8) — the single executable surface in
this batch. Cards 6 and 7 edit orchestrator `SKILL.md` files, which have no unit-test
surface; they are verified by code review against the cited commit-message strings and the
`## Agent-mode dispatch` step references. `verify` is intentionally narrow (one file) per
the per-batch scoping rule.

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\02-track-briefs.md ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\03-review-mode-tests.md ---
# Batch: review-mode-tests

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
batch: review-mode-tests
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
depends-on: []
```

## Batch Scope

Add regression coverage for the two halves of the bulking decision: a tool-use reviewer
must NOT inline reviewed source into its prompt (the property that makes briefs small
enough to track), and the demoted bulk path must still inline source when explicitly
selected (proving the `_bulk` opt-in survives). This is its own batch because the tests
exercise the review prompt-assembly code (`_review_code.py`, `_review_common.py`), whose
combined size dominates the context budget — isolating them keeps every batch within the
context-token limit. The tests use inline reviewer specs, so the batch is independent of
the catalogue rename in batch 1.

## Cards

### Card 9: Assert tool-use omits bulked bodies and bulk remains reachable

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewer_single.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two tests to `test-review-common.py`. (1) A no-bulked-bodies test:
  build the review artefact/prompt section for a reviewer spec with `tooluse: true` over a
  fixture source file containing a unique sentinel line, and assert the rendered prompt
  contains the tool-use `<TOOL_RULE>` block (granting Read/Grep/Glob) and the file's
  *path* but NOT the sentinel line (no inlined body). Drive it through the same
  tool-use-mode assembly the prepare stage uses — `_review_code._build_artefact_section`
  with mode `"tool-use"` and `_review_common.build_tool_rule("tool-use")`. (2) A
  bulk-still-reachable test: for a spec with `tooluse: false`, assert the bulk assembly
  inlines the body — the sentinel line IS present — confirming `_read_for_bulk` /
  `bulk_files` remain reachable. Construct reviewer specs inline (do not import the
  production catalogue or `make_minimal_registry`). Use `tempfile` fixtures; no real
  git/LLM. Match the file's existing test signature/return convention.
- **Commit:** `test(review): assert tool-use omits bulked bodies and bulk stays reachable`

## Batch Tests

`verify` runs `test-review-common.py` via `run-all.py --only`, which now includes the two
new tests plus the file's existing review-common coverage. Scope is the single file this
batch edits, per the per-batch scoping rule. The new tests are pure unit tests over the
prompt-assembly helpers — no real LLM call, no network — so they run in the same fast
suite as the rest of `test-review-common.py`.

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\_mill\plan\03-review-mode-tests.md ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_reviewers.py ---
"""
Registry loader, name resolver, and role-aware lookup for named reviewer definitions.

Provides the bridge between plugin template mill-agents.yaml (the base registry),
.millhouse/agents.local.yaml (per-hub overrides), and legacy wiki/agents.yaml or
wiki/reviewers.yaml (for in-flight branches before migration).

Public API:
    ReviewerError  — raised on every validation/resolution failure.
    load(hub_dir: Path) -> dict[str, dict]
        Load and validate plugin template + local overlay + legacy wiki fallback.
        Returns name → raw spec dict.
    resolve(registry: dict, name: str) -> dict
        Resolve a reviewer name to a fully-flattened spec dict.
        Special case: "test_stub" returns a synthetic spec without consulting the registry.
    resolve_role(cfg: dict, registry: dict, role: str, scope: str) -> dict | None
        Read cfg.roles.<role>.<scope>.reviewer and resolve via registry.
        Returns None if reviewer is null or rounds is 0.
    validate_role_refs(cfg: dict, registry: dict) -> None
        Walk cfg.roles.<role>.<scope>.reviewer for every (role, scope) pair;
        confirm each non-null name resolves. Raises ReviewerError listing all failures.
"""
from __future__ import annotations

import re
import sys
from copy import deepcopy
from pathlib import Path

import yaml

import _paths
from _config import deep_merge, resolve_plugin_template_path

_NAME_REGEX = re.compile(r"^[a-z0-9_-]+$")


class ReviewerError(Exception):
    """Raised on every validation/resolution failure in the reviewer registry."""


def _validate_extends_syntax(raw: dict) -> list[str]:
    """Validate raw-form extends syntax. Returns list of error messages."""
    errors: list[str] = []
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        if "extends" not in entry:
            continue
        extends_value = entry["extends"]
        if not isinstance(extends_value, str):
            errors.append(f"Reviewer {name!r}: 'extends' must be a string")
            continue
        if extends_value not in raw:
            errors.append(f"Reviewer {name!r}: extends references unknown name {extends_value!r}")
            continue
        target_entry = raw[extends_value]
        if isinstance(target_entry, dict) and target_entry.get("type") == "cluster":
            errors.append(
                f"Reviewer {name!r}: extends references {extends_value!r} which declares"
                " type 'cluster' (clusters cannot be extended)"
            )
        if entry.get("type") == "cluster":
            errors.append(f"Reviewer {name!r}: cluster entries cannot use 'extends'")
    return errors


def _detect_extends_cycles(raw: dict) -> list[str]:
    """DFS cycle detection over extends edges. Returns list of cycle error messages."""
    errors: list[str] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {name: WHITE for name in raw}

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        entry = raw.get(node, {})
        if isinstance(entry, dict) and "extends" in entry:
            neighbor = entry["extends"]
            if neighbor not in color:
                pass
            elif color[neighbor] == GRAY:
                cycle_chain = path + [neighbor]
                errors.append(f"Cycle detected in extends chain: {' -> '.join(cycle_chain)}")
            elif color[neighbor] == WHITE:
                dfs(neighbor, path + [neighbor])
        color[node] = BLACK

    for name in list(raw.keys()):
        if color[name] == WHITE:
            dfs(name, [name])
    return errors


def _resolve_extends(raw: dict) -> dict:
    """Top-down extends-chain merge; returns flat dict with no 'extends:' fields."""
    resolved: dict[str, dict] = {}

    def _walk(name: str) -> dict:
        if name in resolved:
            return resolved[name]
        entry = raw[name]
        if "extends" not in entry:
            flat = dict(entry)
        else:
            base = _walk(entry["extends"])
            flat = dict(base)
            for k, v in entry.items():
                if k == "extends":
                    continue
                flat[k] = v
        resolved[name] = flat
        return flat

    for name in raw:
        _walk(name)
    return resolved


def load(hub_dir: Path) -> dict[str, dict]:
    """Load and validate plugin template + local overlay + legacy wiki fallback.

    Returns name → raw spec dict after merging all available layers and validating.

    Validates: all names match [a-z0-9_-]+, no duplicate names in each source file,
    every entry has a known type, required fields per type, cluster use: references
    resolve to type=single only, no cycles in the use: graph, and entries with
    `extends: <name>` are resolved top-down at load time (single-string form only;
    cluster entries may neither extend nor be extended; cycle detection raises
    with the chain).

    Raises ReviewerError listing every problem in a single message.
    """
    # Load plugin template.
    template_path = resolve_plugin_template_path("mill-agents.yaml")
    template_registry = {}
    if template_path.exists():
        template_text = template_path.read_text(encoding="utf-8")
        _validate_source_for_duplicates(template_text, template_path)
        template_registry = yaml.safe_load(template_text) or {}

    # Load local overlay.
    local_path = hub_dir / ".millhouse" / "agents.local.yaml"
    local_registry = {}
    if local_path.exists():
        local_text = local_path.read_text(encoding="utf-8")
        _validate_source_for_duplicates(local_text, local_path)
        local_registry = yaml.safe_load(local_text) or {}

    # Legacy wiki fallback if both layers are empty.
    if not template_registry and not local_registry:
        wiki_path = None
        try:
            wiki_path = _paths.resolve_wiki_path(hub_dir)
            agents_path = wiki_path / "agents.yaml"
            if agents_path.exists():
                sys.stderr.write(
                    f"[reviewers] using legacy wiki agents file at {agents_path}; "
                    "run mill-setup to migrate to plugin template + .millhouse/agents.local.yaml\n"
                )
                wiki_text = agents_path.read_text(encoding="utf-8")
                _validate_source_for_duplicates(wiki_text, agents_path)
                return _validate_and_return(
                    yaml.safe_load(wiki_text) or {}, template_registry
                )
            reviewers_path = wiki_path / "reviewers.yaml"
            if reviewers_path.exists():
                sys.stderr.write(
                    f"[reviewers] using legacy wiki agents file at {reviewers_path}; "
                    "run mill-setup to migrate to plugin template + .millhouse/agents.local.yaml\n"
                )
                wiki_text = reviewers_path.read_text(encoding="utf-8")
                _validate_source_for_duplicates(wiki_text, reviewers_path)
                return _validate_and_return(
                    yaml.safe_load(wiki_text) or {}, template_registry
                )
        except (Exception, SystemExit):
            pass

        # No source found.
        raise ReviewerError(
            f"Missing registry: no plugin template at {template_path}, "
            f"no .millhouse/agents.local.yaml at {local_path}, "
            f"no legacy wiki/agents.yaml or wiki/reviewers.yaml"
        )

    # Merge layers: local overlays template.
    raw = deep_merge(template_registry, local_registry)

    # Per-agent unknown-key validation: local-only agents are allowed.
    for agent_name in local_registry:
        if agent_name in template_registry:
            unknown = _walk_unknown_agent_keys(
                local_registry[agent_name], template_registry[agent_name]
            )
            for key in unknown:
                sys.stderr.write(
                    f"[reviewers] unknown key in {agent_name}: {key} "
                    "(in .millhouse/agents.local.yaml)\n"
                )

    # Run full validation on merged registry.
    return _validate_and_return(raw, template_registry)


def _validate_source_for_duplicates(text: str, source_path: Path) -> None:
    """Check a YAML source for duplicate top-level keys via compose."""
    doc = yaml.compose(text)
    if doc is None or not isinstance(doc, yaml.MappingNode):
        return

    seen_keys: set[str] = set()
    dup_keys: list[str] = []
    for key_node, _ in doc.value:
        k = key_node.value
        if k in seen_keys:
            dup_keys.append(k)
        seen_keys.add(k)
    if dup_keys:
        raise ReviewerError(
            f"Duplicate reviewer names in {source_path}: {sorted(set(dup_keys))!r}"
        )


def _walk_unknown_agent_keys(actual_entry: dict, template_entry: dict) -> list[str]:
    """Walk actual agent entry and return keys not in template_entry."""
    unknown = []
    for key in actual_entry:
        if key not in template_entry:
            unknown.append(key)
    return unknown


def _validate_and_return(raw: dict, template_registry: dict) -> dict[str, dict]:
    """Validate merged registry and return it; raise ReviewerError on any problems."""
    if not isinstance(raw, dict):
        raise ReviewerError("Registry must be a YAML mapping")

    errors: list[str] = []

    errors.extend(_validate_extends_syntax(raw))
    errors.extend(_detect_extends_cycles(raw))
    if errors:
        raise ReviewerError("\n".join(errors))

    raw = _resolve_extends(raw)

    # Per-entry validation; track valid types for cross-ref checks.
    valid_types: dict[str, str] = {}
    for name, entry in raw.items():
        if not isinstance(name, str) or not _NAME_REGEX.match(str(name)):
            errors.append(f"Invalid reviewer name {name!r}: must match [a-z0-9_-]+")
            continue
        if not isinstance(entry, dict):
            errors.append(f"Reviewer {name!r}: entry must be a YAML mapping")
            continue
        entry_type = entry.get("type")
        if entry_type not in ("single", "cluster"):
            errors.append(f"Reviewer {name!r}: unknown type {entry_type!r}")
            continue
        if entry_type == "single":
            if not isinstance(entry.get("provider"), str):
                errors.append(f"Reviewer {name!r} (single): missing or invalid 'provider'")
            if not isinstance(entry.get("model"), str):
                errors.append(f"Reviewer {name!r} (single): missing or invalid 'model'")
        elif entry_type == "cluster":
            workers = entry.get("workers")
            if not isinstance(workers, dict):
                errors.append(
                    f"Reviewer {name!r} (cluster): 'workers' must be a mapping with 'use' and 'count'"
                )
            else:
                if "use" not in workers:
                    errors.append(f"Reviewer {name!r} (cluster): 'workers.use' is required")
                count = workers.get("count")
                if not isinstance(count, int) or count <= 0:
                    errors.append(
                        f"Reviewer {name!r} (cluster): 'workers.count' must be a positive integer"
                    )
            handler = entry.get("handler")
            if not isinstance(handler, dict):
                errors.append(
                    f"Reviewer {name!r} (cluster): 'handler' must be a mapping with 'use'"
                )
            elif "use" not in handler:
                errors.append(f"Reviewer {name!r} (cluster): 'handler.use' is required")
        valid_types[name] = entry_type

    # Cross-ref validation: cluster use: values must resolve to type=single.
    for name in list(valid_types.keys()):
        if valid_types[name] != "cluster":
            continue
        entry = raw[name]
        workers = entry.get("workers") or {}
        handler = entry.get("handler") or {}
        for use_name, label in [
            (workers.get("use"), "workers.use"),
            (handler.get("use"), "handler.use"),
        ]:
            if use_name is None:
                continue
            if use_name not in valid_types:
                errors.append(
                    f"Reviewer {name!r}: {label} references unknown name {use_name!r}"
                )
            elif valid_types[use_name] != "single":
                errors.append(
                    f"Reviewer {name!r}: {label} references {use_name!r}"
                    f" which is not type 'single' (no nested clusters)"
                )

    # Cycle detection DFS over use: edges (defensive; unreachable given no-nested-cluster rule).
    _detect_cycles(raw, valid_types, errors)

    if errors:
        raise ReviewerError("\n".join(errors))

    return raw


def _detect_cycles(
    registry: dict,
    valid_types: dict[str, str],
    errors: list[str],
) -> None:
    """DFS cycle detection over cluster use: edges. Appends cycle messages to errors."""
    adjacency: dict[str, list[str]] = {}
    for name, entry_type in valid_types.items():
        if entry_type == "cluster":
            entry = registry.get(name, {})
            refs: list[str] = []
            workers_use = (entry.get("workers") or {}).get("use")
            handler_use = (entry.get("handler") or {}).get("use")
            if workers_use:
                refs.append(workers_use)
            if handler_use:
                refs.append(handler_use)
            adjacency[name] = refs
        else:
            adjacency[name] = []

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in valid_types}

    def dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor in adjacency.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                errors.append(f"Cycle detected: {node!r} → {neighbor!r}")
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for name in list(valid_types.keys()):
        if color[name] == WHITE:
            dfs(name)


def resolve(registry: dict, name: str) -> dict:
    """Resolve a reviewer name to a fully-flattened spec.

    Special case: name == "test_stub" returns
    {"type": "single", "provider": "test_stub", "tooluse": False}
    without consulting the registry.

    For type=single: returns a copy of the entry with tooluse defaulted to False.
    For type=cluster: returns a deep copy with workers.use and handler.use replaced
    by their fully-resolved single-spec dicts (bounded at depth 1 by load validation).

    Raises ReviewerError on missing name or unknown type.
    """
    if name == "test_stub":
        return {"type": "single", "provider": "test_stub", "tooluse": False}

    if name not in registry:
        raise ReviewerError(f"Unknown reviewer: {name!r}")

    spec = dict(registry[name])

    if spec["type"] not in ("single", "cluster"):
        raise ReviewerError(f"Unknown reviewer type: {spec['type']!r}")

    if spec["type"] == "single":
        if "tooluse" not in spec:
            spec["tooluse"] = False
        return spec

    # cluster: flatten use: references to their resolved single-specs.
    spec = deepcopy(spec)
    workers = spec.get("workers", {})
    handler = spec.get("handler", {})
    if isinstance(workers, dict) and "use" in workers:
        workers["use"] = resolve(registry, workers["use"])
    if isinstance(handler, dict) and "use" in handler:
        handler["use"] = resolve(registry, handler["use"])
    return spec


def resolve_role(
    cfg: dict,
    registry: dict,
    role: str,
    scope: str,
) -> dict | None:
    """Read cfg.roles.<role>.<scope>.reviewer; resolve via registry.

    Returns None if reviewer is null or rounds is 0.
    Raises ReviewerError if the role or scope key is absent from cfg.
    """
    if role not in cfg.get("roles", {}) or scope not in cfg["roles"][role]:
        raise ReviewerError(f"Missing roles.{role}.{scope} in config")

    subsection = cfg["roles"][role][scope]
    reviewer = subsection.get("reviewer")
    rounds = subsection.get("rounds", 0)

    if reviewer is None or rounds == 0:
        return None

    return resolve(registry, reviewer)


def validate_role_refs(cfg: dict, registry: dict) -> None:
    """Walk cfg.roles.<role>.<scope>.reviewer for every (role, scope) pair.

    Confirms each non-null name resolves in the registry.
    Raises ReviewerError with all missing names listed in the message.
    """
    errors: list[str] = []
    for role, role_cfg in cfg.get("roles", {}).items():
        if not isinstance(role_cfg, dict):
            continue
        for scope, scope_cfg in role_cfg.items():
            if not isinstance(scope_cfg, dict):
                continue
            reviewer = scope_cfg.get("reviewer")
            if reviewer is None:
                continue
            try:
                resolve(registry, reviewer)
            except ReviewerError as exc:
                errors.append(f"roles.{role}.{scope}.reviewer={reviewer!r}: {exc}")
            lp_reviewer = (scope_cfg.get("large_prompt") or {}).get("reviewer")
            if lp_reviewer is not None:
                try:
                    lp_spec = resolve(registry, lp_reviewer)
                    if lp_spec.get("type") == "cluster":
                        errors.append(
                            f"roles.{role}.{scope}.large_prompt.reviewer={lp_reviewer!r}: "
                            "cluster type not supported for large-prompt override"
                        )
                except ReviewerError as exc:
                    errors.append(
                        f"roles.{role}.{scope}.large_prompt.reviewer={lp_reviewer!r}: {exc}"
                    )

    impl_model = cfg.get("roles", {}).get("implementer", {}).get("model")
    if impl_model is not None:
        try:
            resolve(registry, impl_model)
        except ReviewerError as exc:
            errors.append(f"roles.implementer.model={impl_model!r}: {exc}")

    fixer_model = cfg.get("roles", {}).get("fixer", {}).get("model")
    if fixer_model is not None:
        try:
            resolve(registry, fixer_model)
        except ReviewerError as exc:
            errors.append(f"roles.fixer.model={fixer_model!r}: {exc}")

    if errors:
        raise ReviewerError("\n".join(errors))

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_reviewers.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\mill-agents.yaml ---
# mill-agents.yaml -- the mill agent catalogue.
#
# This file is the plugin template for the mill agent catalogue.
#
# Overlay precedence (first source wins):
#   plugin template -> .millhouse/agents.local.yaml
#
# Per-machine model swaps belong in `.millhouse/agents.local.yaml`, not here
# -- this file ships with the plugin.
#
# Schema: each entry is keyed by reviewer name and has `type: single|cluster`
# plus type-specific fields (provider + model for single; workers + handler
# for cluster). Tool-use is the default naming convention: an unsuffixed name
# is a tool-use agent with explicit `tooluse: true`, and the `_bulk` suffix
# marks a bulk variant with `tooluse: false`. The `tooluse` flag is consumed
# only by reviewer dispatch logic and is irrelevant for entries used as
# implementer/fixer/merge models (e.g. `haiku`), so `tooluse: true` on such
# entries is harmless and the convention applies uniformly.

g25flash:
  model: gemini-2.5-flash
  provider: gemini
  tooluse: true
  type: single

g25flash_bulk:
  model: gemini-2.5-flash
  provider: gemini
  tooluse: false
  type: single

g25pro:
  model: gemini-2.5-pro
  provider: gemini
  tooluse: true
  type: single

g25pro_bulk:
  model: gemini-2.5-pro
  provider: gemini
  tooluse: false
  type: single

g3flash_preview:
  model: gemini-3-flash-preview
  provider: gemini
  tooluse: true
  type: single

g3flash_preview_bulk:
  model: gemini-3-flash-preview
  provider: gemini
  tooluse: false
  type: single

haiku:
  model: claude-haiku-4-5-20251001
  provider: claude
  timeout: 600
  tooluse: true
  type: single

opushigh:
  effort: high
  model: claude-opus-4-7
  provider: claude
  tooluse: true
  type: single

opushigh_bulk:
  effort: high
  model: claude-opus-4-7
  provider: claude
  tooluse: false
  type: single

opusmax:
  effort: max
  model: claude-opus-4-7
  provider: claude
  tooluse: true
  type: single

opusmax_bulk:
  effort: max
  model: claude-opus-4-7
  provider: claude
  tooluse: false
  type: single

opusmedium:
  effort: medium
  model: claude-opus-4-7
  provider: claude
  tooluse: true
  type: single

opusmedium_bulk:
  effort: medium
  model: claude-opus-4-7
  provider: claude
  tooluse: false
  type: single

sonnethigh:
  effort: high
  model: claude-sonnet-4-6
  provider: claude
  tooluse: true
  type: single

sonnethigh_bulk:
  effort: high
  model: claude-sonnet-4-6
  provider: claude
  tooluse: false
  type: single

sonnetmax:
  effort: max
  model: claude-sonnet-4-6
  provider: claude
  tooluse: true
  type: single

sonnetmax_bulk:
  effort: max
  model: claude-sonnet-4-6
  provider: claude
  tooluse: false
  type: single

sonnetmedium:
  effort: medium
  model: claude-sonnet-4-6
  provider: claude
  tooluse: true
  type: single

sonnetmedium_bulk:
  effort: medium
  model: claude-sonnet-4-6
  provider: claude
  tooluse: false
  type: single

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\mill-agents.yaml ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\mill-config.yaml ---
# mill-config.yaml — shared configuration for mill.
#
# This file is the plugin template for `mill-config.yaml` at the hub repo root.
#
# Overlay precedence (first source wins):
#   plugin template -> mill-config.yaml at hub repo root -> .millhouse/config.local.yaml
#
# Local (non-secret) overrides go in .millhouse/config.local.yaml (gitignored).
# Secrets belong in .env at the repo root, not here.
#
# Environment-variable overrides (when set, takes precedence over config file values):
#   MILL_DISCUSSION_REVIEWER        -> roles.discussion-review.holistic.reviewer
#   MILL_PLAN_REVIEWER              -> roles.plan-review.holistic.reviewer
#   MILL_PLAN_BATCH_REVIEWER        -> roles.plan-review.batch.reviewer
#   MILL_CODE_REVIEWER              -> roles.code-review.holistic.reviewer
#   MILL_CODE_BATCH_REVIEWER        -> roles.code-review.batch.reviewer
#   MILL_IMPLEMENTER                -> roles.implementer.model
#
# Unknown keys emit a stderr warning at load time; load proceeds.
#
# Review roles live under `roles:`. Reviewer names reference agents.yaml.
# Skip semantics: rounds: 0 OR reviewer: null -> skip the scope.
#
# Path tokens (substituted by mill scripts at run time, always UPPERCASE):
#   <HUB_PATH>        -- primary clone root
#   <CONTAINER_PATH>  -- parent of HUB_PATH (holds hub/, wiki/, worktrees/)
#   <WIKI_PATH>       -- wiki clone root
#   <REPO>            -- short repo name from origin URL
#   <SLUG>            -- task slug (valid only in mill-spawn-created entries)
#
# Env-var interpolation (substituted by mill scripts at run time):
#   ${VAR}          -- replaced with the value of env var VAR; unset raises ConfigError
#   ${VAR:-default} -- replaced with VAR if set; otherwise the literal "default"
# Variable names must be uppercase (POSIX convention); lowercase forms pass through
# as literal text. Interpolation applies to string values everywhere in this file,
# including inside lists and nested maps.
#
# Junctions and hardlinks are IDE/terminal convenience — scripts always
# resolve paths via _paths.py, never via the link paths themselves.

# ---------------------------------------------------------------------------
# Junctions
# ---------------------------------------------------------------------------
# Each entry: `<junction-path>: <target-template>`.
# Scope inferred from token presence:
#   * Target contains <SLUG>   -> per-worktree; created by mill-spawn.
#   * Target has no <SLUG>     -> hub-scope; created by mill-setup.

# ---------------------------------------------------------------------------
# Repo identity
# ---------------------------------------------------------------------------
# short_name -- 2-4 character prefix used in VS Code window titles.
#   Hub form:      "<short_name>"
#   Worktree form: "<short_name>: <slug>"
#   Default when absent or empty: <repo>[:2].upper() (e.g. "millhouse" -> "MI").

repo:
  short_name: ""    # e.g. "MH" for millhouse

junctions:
  .wiki: <WIKI_PATH>
  .portals: <CONTAINER_PATH>/portals/
  # .active is created explicitly by mill-spawn/mill-claim (points to <hub>/_mill/);
  # not declared here so it is not auto-created in non-task worktrees.

# ---------------------------------------------------------------------------
# mill-spawn
# ---------------------------------------------------------------------------
# branch_prefix -- prepended directly to the slug (no separator added).
#   Include any separator in the prefix itself, e.g. "hanf/" -> "hanf/<slug>".
#   Empty string -> branch == slug.

spawn:
  branch_prefix: ""

# ---------------------------------------------------------------------------
# Git integration
# ---------------------------------------------------------------------------
# Uncomment if your remote enforces PRs to the base branch (branch protection).
# git:
#   require_pr_to_base: true   # create a PR instead of pushing directly; dispatch lives in mill-finalize
#   base_branch: main          # branch to target; defaults to main if absent

# ---------------------------------------------------------------------------
# File-path templates (relative to active worktree root)
# ---------------------------------------------------------------------------

paths:
  discussion_file: _mill/discussion.md
  plan_dir:        _mill/plan/
  reviews_dir:     _mill/reviews/
  status_md:       _mill/status.md

# ---------------------------------------------------------------------------
# LLM-provider timeouts (seconds)
# ---------------------------------------------------------------------------

llm:
  bulk_timeout: 600
  holistic_timeout: 1800
  tool_use_timeout: 900
  implementer_timeout: 3600
  max_implementer_prompt_chars: 0
  claude:
    dispatch: agent  # LLM dispatch mode: subprocess | psmux | agent (agent is Claude-only; the default)
    psmux:
      shell_path: pwsh  # Shell binary passed to new_session. Use the full path if pwsh on PATH is a broken stub (e.g. C:/Code/tools/powershell7/pwsh.exe on Windows machines with App Execution Alias disabled).
      reuse_idle_timeout_s: 10  # Seconds to wait for an existing psmux session to return to its idle prompt before reuse fails
      response_poll_timeout_s:  # Max seconds to wait for psmux Claude TUI to return to idle per mode. Note: review-layer timeout overrides this when invoked via _llm_claude._build_psmux_argv (the --response-poll-timeout flag); this key applies only to direct millpy-claude-sub.py invocations without that flag.
        bulk: 300
        tool-use: 600
        implementer: 1800

# ---------------------------------------------------------------------------
# mill-go pipeline
# ---------------------------------------------------------------------------

pipeline:
  auto_merge: false
  auto_report: true
  autonomous_mode: false  # Set true by mill-autofix; read by mill-go and mill-plan for autonomous stuck-handling
  max_cards_per_batch: 10  # batch-oversized validator gate (#371)
  max_batch_context_tokens: 120000  # batch-oversized validator gate (#371)

# ---------------------------------------------------------------------------
# Reviewer roles
# ---------------------------------------------------------------------------
# Reviewer names reference agents.yaml entries.

roles:
  discussion-review:
    holistic:
      rounds: 4
      reviewer: sonnetmax
      # large_prompt:            # optional: override reviewer for large prompts
      #   threshold_ktok: 100    # switch when estimated tok count >= this (char/4000)
      #   reviewer: null         # override reviewer from agents.yaml; null = disabled

  plan-review:
    batch:
      rounds: 0
      reviewer: null
    holistic:
      rounds: 4
      reviewer: sonnetmax
      # large_prompt:            # optional: override reviewer and timeout for large prompts
      #   threshold_ktok: 100    # switch when estimated tok count >= this (char/4000)
      #   reviewer: null         # override reviewer from agents.yaml; null = disabled
      #   timeout: 3600          # optional: override the default holistic_timeout for large prompts

  code-review:
    batch:
      rounds: 0
      reviewer: null
    holistic:
      rounds: 4
      reviewer: sonnethigh
      fallback_reviewer: null     # reviewer name from agents.yaml to swap in on consecutive rate-limit ERRORs; null = no fallback
      fallback_on:                 # list of substrings (lowercased match) in reviews[].error that trigger fallback
        - "rate-limit"
      # large_prompt:            # optional: override reviewer for large prompts
      #   threshold_ktok: 100    # switch when estimated tok count >= this (char/4000)
      #   reviewer: null         # override reviewer from agents.yaml; null = disabled
    diff_scope_threshold: 0.25

  implementer:
    self_fix_rounds: 2
    model: haiku

  fixer:
    model: haiku

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

notify:
  backend: stdout

# ---------------------------------------------------------------------------
# mill-groom: backlog cleanup thresholds
# ---------------------------------------------------------------------------

groom:
  brevity-threshold-lines: 5
  brevity-threshold-chars: 500

# ---------------------------------------------------------------------------
# mill-merge-in
# ---------------------------------------------------------------------------
# verify_fix_rounds: how many self-fix attempts the verify-fix sub-agent makes
# before reporting stuck. The CLI defaults to 3 if this key is absent, so
# existing hubs do not need to add this key -- only new hubs set up from this
# template will have it pre-populated.

merge:
  # model: LLM alias for the merge-in sub-agent (haiku is sufficient for conflict resolution)
  model: haiku
  verify_fix_rounds: 3

# ---------------------------------------------------------------------------
# verify command shape (canonical, enforced by _plan_validate.verify-not-isolated)
# ---------------------------------------------------------------------------
# Every non-null verify: in a per-batch plan file's frontmatter MUST start
# with the literal token "PYTHONPATH=" followed by a single space and the
# command. Example:
#     verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
# The empty value on the same line scopes the PYTHONPATH reset to that one
# command, so the test subprocess does not inherit the mill plugin-cache
# scripts dir (set by every mill skill's PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
# invocation pattern). Without this reset, tests load V2-cache modules
# instead of the worktree code they are meant to validate.
# This is schema documentation only -- no key change here; the planner
# bakes the prefix into each per-batch verify: command per mill-plan SKILL.

# ---------------------------------------------------------------------------
# mill-merge-in: verify allowlist
# ---------------------------------------------------------------------------
# verify.skip_known_broken is a list of path substrings. If any entry appears
# as a substring of a plan batch's verify: command, mill-merge-in skips that
# command and logs: [verify] skipped <path> (allowlisted as known-broken).
# Values are per-machine and belong in .millhouse/config.local.yaml, not here
# in the shared wiki config -- this block is for schema documentation only.
# verify:
#   skip_known_broken: []  # e.g. ["tests/foo/test_flaky.py"]

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\mill-config.yaml ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\mill-config.yaml ---
repo:
  short_name: MH
spawn:
  branch_prefix: hanf/
llm:
  bulk_timeout: 900
  implementer_timeout: 1800
  max_implementer_prompt_chars: 0
  claude:
    dispatch: agent
    psmux:
      shell_path: "${PWSH:-pwsh}"
      reuse_idle_timeout_s: 10
pipeline:
  auto_merge: true
  auto_report: true
  max_cards_per_batch: 10
  max_batch_context_tokens: 120000
merge:
  model: sonnethigh
junctions:
  .wiki: <WIKI_PATH>
  .portals: <CONTAINER_PATH>/portals/
paths:
  discussion_file: _mill/discussion.md
  plan_dir: _mill/plan/
  reviews_dir: _mill/reviews/
  status_md: _mill/status.md
roles:
  discussion-review:
    holistic:
      rounds: 5
      reviewer: sonnetmax
  plan-review:
    batch:
      rounds: 0
      reviewer: null
    holistic:
      rounds: 7
      reviewer: sonnetmax
  code-review:
    batch:
      rounds: 0
      reviewer: null
    holistic:
      rounds: 5
      reviewer: sonnethigh
      fallback_reviewer: null
      fallback_on:
      - rate-limit
    diff_scope_threshold: 0.25
  implementer:
    self_fix_rounds: 2
    model: haiku
  fixer:
    model: haiku
notify:
  backend: stdout
groom:
  brevity-threshold-lines: 5
  brevity-threshold-chars: 500

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\mill-config.yaml ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\review-output.schema.md ---
# Review Output Schema

This file documents the canonical format for all review output files produced by the Layer 02 review system. Every file written by `_review_common.write_review_file()` must conform to this schema. `parse_verdict()` in `_review_common.py` validates against this schema — specifically the `verdict:` field inside the fenced yaml block.

---

## File format

```markdown
# Review: <title>

```yaml
verdict: APPROVE | REQUEST_CHANGES | GAPS_FOUND | NEED_CONTEXT
reviewer_model: <reviewer name from config, e.g. sonnetmax>
reviewed_file: <path to the artefact that was reviewed>
date: <UTC YYYY-MM-DD>
```

## Findings

### [BLOCKING|NIT|GAP|NOTE] <finding title>
**Section:** ...
**Issue:** ...
**Suggested fix:** ...

## Missing context
(present only when verdict is NEED_CONTEXT — one bullet per file the
reviewer needs but could not find in the bulk)

- `path/to/needed_file.py` — why the reviewer needs it

## Verdict

APPROVE | REQUEST_CHANGES | GAPS_FOUND | NEED_CONTEXT
<one-sentence summary>
```

---

## Metadata block fields

The fenced ` ```yaml ` block placed immediately after the `# Review: ...` heading contains review metadata. Fields:

| Field | Type | Required | Values |
|---|---|---|---|
| `verdict` | string | yes | `APPROVE`, `REQUEST_CHANGES`, `GAPS_FOUND`, or `NEED_CONTEXT` |
| `reviewer_model` | string | yes | reviewer name from config (e.g. `sonnetmax`, `sonnethigh`) |
| `reviewed_file` | string | yes | path to the artefact reviewed (discussion file, batch file, or `plan/`) |
| `date` | string | yes | UTC date in `YYYY-MM-DD` format |

`parse_verdict()` scans for the first fenced ` ```yaml ` block in the document and returns the `verdict` value. If no fenced block is found, it falls back to scanning for an unfenced `verdict:` line (case-sensitive, with leading whitespace allowed). It raises `ReviewError` if:
- No ` ```yaml ` opening fence is found AND no unfenced `verdict:` line is found.
- The yaml block is not closed by a ` ``` ` line.
- The `verdict:` field is absent from the block.
- The `verdict:` value is not one of the four listed above.

Note: `---`-style YAML frontmatter is reserved for SKILL.md and plugin manifests per the markdown skill. Review output files must never use `---` frontmatter.

---

## Body sections

### `## Findings`

Required section. Each finding uses this structure:

```markdown
### [BLOCKING|NIT] <finding title>
**Section:** the plan section / file / step the finding applies to
**Issue:** what is wrong or missing
**Suggested fix:** concrete suggestion for resolution
```

**Finding severity:**
- `BLOCKING` — must be resolved before the artefact can be approved. Causes `verdict: REQUEST_CHANGES`.
- `NIT` — optional quality improvement. Does not block approval.

If there are no findings, write `(no findings)` under `## Findings`.

### `## Verdict`

Required section. Contains exactly two lines:

```
APPROVE | REQUEST_CHANGES
<one-sentence summary of the verdict rationale>
```

The verdict line must match the `verdict:` field in the yaml block exactly.

---

## Canonical filenames

Review files are named by `write_review_file()` according to these patterns:

| Review type | Filename pattern |
|---|---|
| Discussion / code / plan holistic | `<ts>-<type>-review-r<N>.md` |
| Plan per-batch | `<ts>-plan-review-<batch-name>-r<N>.md` |

Where:
- `<ts>` = `YYYYMMDD-HHMMSS` UTC timestamp
- `<type>` = `discussion`, `code`, or `plan`
- `<N>` = 1-indexed round number
- `<batch-name>` = batch stem from `plan/NN-<name>.md`, matching `[a-z0-9-]+`

Examples:
- `20260418-001200-discussion-review-r1.md`
- `20260418-143300-code-review-r2.md`
- `20260418-143300-plan-review-r1.md`
- `20260418-143300-plan-review-03-templates-r1.md`

---

## Verdict vocabulary

| Verdict | Meaning | Appears in |
|---|---|---|
| `APPROVE` | Artefact is complete and correct. NITs recorded but do not block. | yaml block + `## Verdict` body |
| `REQUEST_CHANGES` | One or more BLOCKING findings must be resolved. Plan / code reviews only. | yaml block + `## Verdict` body |
| `GAPS_FOUND` | Discussion review only: at least one GAP in the discussion. | yaml block + `## Verdict` body |
| `NEED_CONTEXT` | Reviewer cannot evaluate without source files not provided in the bulk. The body's `## Missing context` section lists which files. Orchestrator responds by re-firing with `--extra-file <path>` per needed file, and must also notify + self-report the incomplete plan reference. Never guess. | yaml block + `## Verdict` body |
| `ERROR` | Sub-review failed (LLM error, timeout, etc.). | `reviews[]` entries in `ReviewResult` only — never in review files |

`ERROR` never appears inside a review file. It is only used in the `ReviewResult` JSON emitted by the API scripts when a sub-review fails at the LLM-provider layer.

`NEED_CONTEXT` is the reviewer's escape hatch when it cannot evaluate without reading a file the orchestrator did not bulk. The discipline is: reviewers never fabricate file contents from filename/position clues. If a claim cannot be verified against the provided source, emit `NEED_CONTEXT` — the orchestrator owns the retry.

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\templates\review-output.schema.md ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_test_registry.py ---
"""
Baseline reviewer registry builder for unit tests.

Provides:
    make_minimal_registry(**overrides) -> dict
        Returns a baseline registry dict with sonnetmax (tool-use) and sonnetmax_bulk (bulk) entries.
    write_to(wiki_root: Path, **overrides) -> Path
        Writes the registry to wiki_root/reviewers.yaml and returns the path.

Tests that need _reviewers.load(wiki_root) to succeed should call write_to()
from their fixture to create the file on disk.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def make_minimal_registry(**overrides) -> dict:
    """Return a baseline reviewer registry dict.

    Contains sonnetmax (tool-use) and sonnetmax_bulk (bulk) single-specs.
    The **overrides kwargs are deep-merged into the baseline.
    """
    baseline: dict = {
        "sonnetmax": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": True,
        },
        "sonnetmax_bulk": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": False,
        },
    }
    if overrides:
        return _deep_merge(baseline, overrides)
    return baseline


def write_to(wiki_root: Path, **overrides) -> Path:
    """Write the registry to wiki_root/agents.yaml and return the path.

    Creates wiki_root (and parents) if absent — fixture code typically assigns
    wiki_root = tmp_path / "wiki" without creating the directory first.
    """
    wiki_root.mkdir(parents=True, exist_ok=True)
    registry = make_minimal_registry(**overrides)
    out_path = wiki_root / "agents.yaml"
    out_path.write_text(yaml.safe_dump(registry, default_flow_style=False), encoding="utf-8")
    return out_path

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_test_registry.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\_test_registry.py ---
"""
Baseline reviewer registry builder for unit tests.

Provides:
    make_minimal_registry(**overrides) -> dict
        Returns a baseline registry dict with sonnetmax (tool-use) and sonnetmax_bulk (bulk) entries.
    write_to(wiki_root: Path, **overrides) -> Path
        Writes the registry to wiki_root/agents.yaml and returns the path.

Tests that need _reviewers.load(wiki_root) to succeed should call write_to()
from their fixture to create the file on disk.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def make_minimal_registry(**overrides) -> dict:
    """Return a baseline reviewer registry dict.

    Contains sonnetmax (tool-use) and sonnetmax_bulk (bulk) single-specs.
    The **overrides kwargs are deep-merged into the baseline.
    """
    baseline: dict = {
        "sonnetmax": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": True,
        },
        "sonnetmax_bulk": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            "tooluse": False,
        },
    }
    if overrides:
        return _deep_merge(baseline, overrides)
    return baseline


def write_to(wiki_root: Path, **overrides) -> Path:
    """Write the registry to wiki_root/agents.yaml and return the path.

    Creates wiki_root (and parents) if absent — fixture code typically assigns
    wiki_root = tmp_path / "wiki" without creating the directory first.
    """
    wiki_root.mkdir(parents=True, exist_ok=True)
    registry = make_minimal_registry(**overrides)
    out_path = wiki_root / "agents.yaml"
    out_path.write_text(yaml.safe_dump(registry, default_flow_style=False), encoding="utf-8")
    return out_path

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\_test_registry.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-reviewers.py ---
"""Unit tests for _reviewers.py (load, resolve, resolve_role, validate_role_refs)
plus _reviewer_single.run dispatch (was test-reviewer-single.py, merged 2026-05-28).
"""
from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
sys.path.insert(0, str(HUB / "plugins" / "mill" / "unit_tests"))

import _paths  # noqa: E402
import _reviewers  # noqa: E402
import _reviewer_single  # noqa: E402
import _reviewer_test_stub as stub  # noqa: E402
from _reviewers import ReviewerError  # noqa: E402
from _test_cfg import make_minimal_cfg  # noqa: E402
from _test_registry import make_minimal_registry, write_to  # noqa: E402
from unittest.mock import patch  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_with_overlay(yaml_text: str) -> dict:
    """Load reviewers from a fresh hub with yaml_text as its local overlay.

    Used by the extends/cluster test block. Patches the plugin template path
    to a nonexistent location so the local overlay is the only source.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub = tmp_path / "hub"
        hub.mkdir()
        (hub / ".millhouse").mkdir()
        (hub / ".millhouse" / "agents.local.yaml").write_text(yaml_text, encoding="utf-8")
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml",
        ):
            return _reviewers.load(hub)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_happy_path() -> None:
    """load() round-trips a valid agents.yaml via local overlay."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Write registry to local overlay
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "sonnetmax:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n  tooluse: true\n"
            "sonnetmax_bulk:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n  tooluse: false\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert "sonnetmax" in registry
        assert registry["sonnetmax"]["type"] == "single"
        assert registry["sonnetmax"]["provider"] == "claude"
        assert "sonnetmax_bulk" in registry
        assert registry["sonnetmax_bulk"]["tooluse"] is False
    print("PASS: load happy path round-trips")


def test_load_raises_on_missing_file() -> None:
    """load() raises ReviewerError when no source is available."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "Missing registry" in str(exc)
    print("PASS: load raises on missing file")


def test_load_raises_single_missing_provider() -> None:
    """load() raises when a single entry is missing 'provider'."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "bad:\n  type: single\n  model: claude-sonnet-4-6\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "provider" in str(exc)
    print("PASS: load raises single missing provider")


def test_load_raises_cluster_missing_workers() -> None:
    """load() raises when a cluster entry is missing 'workers'."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n  handler:\n    use: myworker\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "workers" in str(exc)
    print("PASS: load raises cluster missing workers")


def test_load_raises_cluster_missing_handler() -> None:
    """load() raises when a cluster entry is missing 'handler'."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n  workers:\n    use: myworker\n    count: 2\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "handler" in str(exc)
    print("PASS: load raises cluster missing handler")


def test_load_raises_cluster_workers_count_non_positive() -> None:
    """load() raises when cluster workers.count is not a positive integer."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "mycluster:\n  type: cluster\n"
            "  workers:\n    use: myworker\n    count: 0\n"
            "  handler:\n    use: myworker\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "count" in str(exc)
    print("PASS: load raises cluster workers.count non-positive")


def test_load_raises_unknown_type() -> None:
    """load() raises on unknown type."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "bad:\n  type: unknown\n  provider: claude\n  model: x\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "unknown" in str(exc).lower() or "type" in str(exc)
    print("PASS: load raises unknown type")


def test_load_raises_invalid_name_uppercase() -> None:
    """load() raises on names with uppercase letters."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "BadName:\n  type: single\n  provider: claude\n  model: x\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "BadName" in str(exc) or "Invalid" in str(exc)
    print("PASS: load raises invalid name (uppercase)")


def test_load_raises_invalid_name_dot() -> None:
    """load() raises on names containing a dot."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "bad.name:\n  type: single\n  provider: claude\n  model: x\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "bad.name" in str(exc) or "Invalid" in str(exc)
    print("PASS: load raises invalid name (dot)")


def test_load_raises_duplicate_name() -> None:
    """load() raises when the same name appears twice in the file."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "sonnetmax:\n  type: single\n  provider: claude\n  model: x\n"
            "sonnetmax:\n  type: single\n  provider: claude\n  model: y\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "sonnetmax" in str(exc) or "Duplicate" in str(exc)
    print("PASS: load raises duplicate name")


def test_load_raises_cluster_use_nonexistent() -> None:
    """load() raises when a cluster use: references a non-existent name."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: x\n"
            "mycluster:\n  type: cluster\n"
            "  workers:\n    use: nonexistent\n    count: 2\n"
            "  handler:\n    use: myworker\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "nonexistent" in str(exc)
    print("PASS: load raises cluster use referencing nonexistent name")


def test_load_raises_cluster_use_referencing_cluster() -> None:
    """load() raises when a cluster use: references another cluster."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "myworker:\n  type: single\n  provider: claude\n  model: x\n"
            "clusterb:\n  type: cluster\n"
            "  workers:\n    use: myworker\n    count: 2\n"
            "  handler:\n    use: myworker\n"
            "clustera:\n  type: cluster\n"
            "  workers:\n    use: clusterb\n    count: 3\n"
            "  handler:\n    use: myworker\n"
        )
        with patch.object(_reviewers, "resolve_plugin_template_path", return_value=tmp_path / "nonexistent" / "mill-agents.yaml"):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "single" in str(exc) or "cluster" in str(exc).lower()
    print("PASS: load raises cluster use referencing another cluster")


def test_resolve_single_happy_path() -> None:
    """resolve() returns spec for a known single entry."""
    # Test with a spec that omits tooluse to verify the default-False path
    registry = {
        "sonnetmax": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
            # tooluse intentionally omitted to test default behavior
        }
    }
    spec = _reviewers.resolve(registry, "sonnetmax")
    assert spec["type"] == "single"
    assert spec["provider"] == "claude"
    assert spec["model"] == "claude-sonnet-4-6"
    assert spec["tooluse"] is False  # defaulted
    print("PASS: resolve single happy path")


def test_resolve_cluster_happy_path() -> None:
    """resolve() returns cluster spec with use: values replaced by fully-resolved single-specs."""
    registry = {
        "myworker": {
            "type": "single",
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "effort": "max",
        },
        "mycluster": {
            "type": "cluster",
            "workers": {"use": "myworker", "count": 3},
            "handler": {"use": "myworker"},
        },
    }
    spec = _reviewers.resolve(registry, "mycluster")
    assert spec["type"] == "cluster"
    assert isinstance(spec["workers"]["use"], dict)
    assert spec["workers"]["use"]["provider"] == "claude"
    assert isinstance(spec["handler"]["use"], dict)
    assert spec["workers"]["count"] == 3
    print("PASS: resolve cluster flattens use: references")


def test_resolve_raises_missing_name() -> None:
    """resolve() raises ReviewerError on unknown name."""
    registry = make_minimal_registry()
    try:
        _reviewers.resolve(registry, "does-not-exist")
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "does-not-exist" in str(exc)
    print("PASS: resolve raises on missing name")


def test_resolve_test_stub_special_case() -> None:
    """resolve(registry, 'test_stub') returns synthetic spec without consulting registry."""
    registry: dict = {}  # empty — test_stub must not need it
    spec = _reviewers.resolve(registry, "test_stub")
    assert spec == {"type": "single", "provider": "test_stub", "tooluse": False}
    print("PASS: resolve test_stub returns synthetic spec")


def test_resolve_role_null_reviewer_returns_none() -> None:
    """resolve_role returns None when reviewer is null."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = None
    registry = make_minimal_registry()
    result = _reviewers.resolve_role(cfg, registry, "plan-review", "batch")
    assert result is None
    print("PASS: resolve_role null reviewer returns None")


def test_resolve_role_rounds_zero_returns_none() -> None:
    """resolve_role returns None when rounds is 0."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["rounds"] = 0
    registry = make_minimal_registry()
    result = _reviewers.resolve_role(cfg, registry, "plan-review", "batch")
    assert result is None
    print("PASS: resolve_role rounds==0 returns None")


def test_resolve_role_valid_name_returns_spec() -> None:
    """resolve_role returns resolved spec for a valid reviewer name."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = "sonnetmax"
    registry = make_minimal_registry()
    spec = _reviewers.resolve_role(cfg, registry, "plan-review", "batch")
    assert spec is not None
    assert spec["type"] == "single"
    assert spec["provider"] == "claude"
    print("PASS: resolve_role valid name returns spec")


def test_validate_role_refs_happy_path() -> None:
    """validate_role_refs passes when all reviewer names exist in registry."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = "sonnetmax"
    cfg["roles"]["plan-review"]["holistic"]["reviewer"] = "sonnetmax"
    registry = make_minimal_registry()
    _reviewers.validate_role_refs(cfg, registry)  # must not raise
    print("PASS: validate_role_refs happy path")


def test_validate_role_refs_missing_raises() -> None:
    """validate_role_refs raises listing all missing reviewer names."""
    cfg = make_minimal_cfg()
    cfg["roles"]["plan-review"]["batch"]["reviewer"] = "typo-reviewer"
    cfg["roles"]["code-review"]["holistic"]["reviewer"] = "another-typo"
    registry = make_minimal_registry()
    try:
        _reviewers.validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        msg = str(exc)
        assert "typo-reviewer" in msg
        assert "another-typo" in msg
    print("PASS: validate_role_refs lists all missing names")


def test_load_falls_back_to_reviewers_yaml() -> None:
    """load() succeeds when only legacy wiki/reviewers.yaml exists."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()
        # Write legacy reviewers.yaml
        (wiki_path / "reviewers.yaml").write_text(
            "sonnetmax:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", return_value=wiki_path):
                registry = _reviewers.load(hub_dir)

        assert "sonnetmax" in registry
    print("PASS: load falls back to reviewers.yaml")


def test_validate_role_refs_catches_bad_implementer_model() -> None:
    """validate_role_refs raises ReviewerError for bad roles.implementer.model."""
    registry = make_minimal_registry()
    cfg = {"roles": {"implementer": {"self_fix_rounds": 2, "model": "nonexistent_entry"}}}
    try:
        _reviewers.validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError:
        pass
    print("PASS: validate_role_refs catches bad implementer model ref")


def test_validate_role_refs_catches_bad_fixer_model() -> None:
    """validate_role_refs raises ReviewerError for bad roles.fixer.model."""
    registry = make_minimal_registry()
    cfg = {"roles": {"fixer": {"model": "nonexistent_entry"}}}
    try:
        _reviewers.validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError:
        pass
    print("PASS: validate_role_refs catches bad fixer model ref")


def test_load_plugin_template_only() -> None:
    """load() uses plugin template when no local override present."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Mock plugin template with 2 entries
        template_content = (
            "sonnetmax:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
            "sonnetmedium:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "templates" / "mill-agents.yaml"
        ):
            (tmp_path / "templates").mkdir(exist_ok=True)
            (tmp_path / "templates" / "mill-agents.yaml").write_text(template_content)
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert "sonnetmax" in registry
        assert "sonnetmedium" in registry
    print("PASS: load plugin template only")


def test_local_overlay_adds_new_agent() -> None:
    """load() merges plugin template and local overlay."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Mock plugin template
        template_content = "agentA:\n  type: single\n  provider: claude\n  model: claude-sonnet-4-6\n"
        # Mock local overlay
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "agentB:\n  type: single\n  provider: claude\n  model: claude-opus-4-1\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "templates" / "mill-agents.yaml"
        ):
            (tmp_path / "templates").mkdir(exist_ok=True)
            (tmp_path / "templates" / "mill-agents.yaml").write_text(template_content)
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert "agentA" in registry
        assert "agentB" in registry
    print("PASS: load local overlay adds new agent")


def test_local_overlay_overrides_model() -> None:
    """load() deep-merges local overrides into plugin template."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # Mock plugin template
        template_content = (
            "agentA:\n  type: single\n  provider: claude\n  model: model-x\n"
        )
        # Mock local override that only changes the model
        (hub_dir / ".millhouse").mkdir()
        (hub_dir / ".millhouse" / "agents.local.yaml").write_text(
            "agentA:\n  model: model-y\n"
        )
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "templates" / "mill-agents.yaml"
        ):
            (tmp_path / "templates").mkdir(exist_ok=True)
            (tmp_path / "templates" / "mill-agents.yaml").write_text(template_content)
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                registry = _reviewers.load(hub_dir)

        assert registry["agentA"]["model"] == "model-y"
        assert registry["agentA"]["provider"] == "claude"
    print("PASS: load local overlay overrides model")


def test_raises_when_nothing_found() -> None:
    """load() raises ReviewerError when no source is found."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        hub_dir = tmp_path / "hub"
        hub_dir.mkdir()
        # No template, no local, no wiki
        with patch.object(
            _reviewers,
            "resolve_plugin_template_path",
            return_value=tmp_path / "nonexistent" / "mill-agents.yaml"
        ):
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                try:
                    _reviewers.load(hub_dir)
                    raise AssertionError("Expected ReviewerError")
                except ReviewerError as exc:
                    assert "Missing registry" in str(exc)
    print("PASS: load raises when nothing found")


def test_extends_single_level() -> None:
    """Single-level extends: child inherits from base."""
    registry = _load_with_overlay(
        "base:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: claude-sonnet-4-6\n"
        "child:\n"
        "  extends: base\n"
        "  tooluse: true\n",
    )
    assert registry["child"] == {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "tooluse": True,
    }
    assert registry["base"] == {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
    }
    print("PASS: extends single level")


def test_extends_multi_level() -> None:
    """Multi-level chain c -> b -> a resolves correctly."""
    registry = _load_with_overlay(
        "a:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: claude-sonnet-4-6\n"
        "b:\n"
        "  extends: a\n"
        "c:\n"
        "  extends: b\n"
        "  tooluse: true\n",
    )
    assert registry["c"]["type"] == "single"
    assert registry["c"]["provider"] == "claude"
    assert registry["c"]["model"] == "claude-sonnet-4-6"
    assert registry["c"]["tooluse"] is True
    print("PASS: extends multi-level")


def test_extends_child_overrides_parent_scalar() -> None:
    """Child overrides parent scalar value."""
    registry = _load_with_overlay(
        "base:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: foo\n"
        "child:\n"
        "  extends: base\n"
        "  model: bar\n",
    )
    assert registry["child"]["model"] == "bar"
    print("PASS: extends child overrides parent scalar")


def test_extends_unknown_base_raises() -> None:
    """Extends referencing unknown base raises ReviewerError."""
    try:
        _load_with_overlay(
            "child:\n"
            "  extends: nonexistent\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "nonexistent" in str(exc)
    print("PASS: extends unknown base raises")


def test_extends_cycle_raises() -> None:
    """Cycle in extends chain raises ReviewerError."""
    try:
        _load_with_overlay(
            "a:\n"
            "  extends: b\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n"
            "b:\n"
            "  extends: a\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: y\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "Cycle detected" in exc_str
        assert "a" in exc_str
        assert "b" in exc_str
    print("PASS: extends cycle raises")


def test_extends_self_cycle_raises() -> None:
    """Self-loop in extends raises ReviewerError."""
    try:
        _load_with_overlay(
            "a:\n"
            "  extends: a\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "Cycle detected" in exc_str
        assert "a -> a" in exc_str
    print("PASS: extends self-cycle raises")


def test_extends_target_must_not_be_cluster() -> None:
    """Extends cannot target a cluster entry."""
    try:
        _load_with_overlay(
            "x:\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: y\n"
            "my_cluster:\n"
            "  type: cluster\n"
            "  workers:\n"
            "    use: x\n"
            "    count: 1\n"
            "  handler:\n"
            "    use: x\n"
            "child:\n"
            "  extends: my_cluster\n"
            "  tooluse: true\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "my_cluster" in exc_str
        assert "cluster" in exc_str
    print("PASS: extends target must not be cluster")


def test_cluster_cannot_extend() -> None:
    """Cluster entries cannot use extends."""
    try:
        _load_with_overlay(
            "a:\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: x\n"
            "my_cluster:\n"
            "  type: cluster\n"
            "  extends: a\n"
            "  workers:\n"
            "    use: a\n"
            "    count: 1\n"
            "  handler:\n"
            "    use: a\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        exc_str = str(exc)
        assert "my_cluster" in exc_str
        assert "cluster" in exc_str
    print("PASS: cluster cannot extend")


def test_required_field_missing_after_merge_raises() -> None:
    """Missing required field after merge is caught by validation."""
    try:
        _load_with_overlay(
            "base:\n"
            "  type: single\n"
            "  model: foo\n"
            "child:\n"
            "  extends: base\n",
        )
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "provider" in str(exc)
    print("PASS: required field missing after merge raises")


def test_extends_field_removed_from_output() -> None:
    """The extends: field is removed from resolved output."""
    registry = _load_with_overlay(
        "a:\n"
        "  type: single\n"
        "  provider: claude\n"
        "  model: x\n"
        "b:\n"
        "  extends: a\n",
    )
    assert "extends" not in registry["b"]
    print("PASS: extends field removed from output")


def test_agents_catalogue_naming_convention() -> None:
    """Lock the catalogue naming convention: unsuffixed = tool-use, _bulk = bulk, no _tool.

    Every entry obeys: a key that does NOT end in _bulk has tooluse present
    and True; a key ending in _bulk has tooluse present and False; and no key
    ends in _tool. tooluse is reviewer-only and the convention applies uniformly,
    so entries used as implementer/merge models (e.g. haiku) assert tooluse: True
    by design — this is not an oversight.
    """
    import yaml
    from pathlib import Path

    # Resolve the catalogue path via the module's HUB pattern
    catalogue_path = HUB / "plugins" / "mill" / "templates" / "mill-agents.yaml"
    assert catalogue_path.exists(), f"mill-agents.yaml not found at {catalogue_path}"

    with open(catalogue_path, encoding="utf-8") as f:
        catalogue = yaml.safe_load(f)

    assert isinstance(catalogue, dict), f"Expected dict, got {type(catalogue)}"

    # Check convention: every key is either unsuffixed (tooluse: true) or _bulk (tooluse: false)
    for name, entry in catalogue.items():
        assert isinstance(entry, dict), f"Entry {name} is not a dict: {entry}"

        # Rule 1: No keys ending in _tool
        assert not name.endswith("_tool"), (
            f"Entry {name!r} ends in _tool; convention requires unsuffixed "
            f"(tool-use) or _bulk (bulk) names only"
        )

        # Rule 2: tooluse field must be present and bool
        assert "tooluse" in entry, f"Entry {name!r} missing tooluse field"
        assert isinstance(entry["tooluse"], bool), (
            f"Entry {name!r} has non-bool tooluse: {entry['tooluse']!r}"
        )

        # Rule 3: _bulk suffix correlates with tooluse: false
        if name.endswith("_bulk"):
            assert entry["tooluse"] is False, (
                f"Entry {name!r} ends in _bulk but has tooluse: {entry['tooluse']}"
            )
        # Rule 4: unsuffixed keys have tooluse: true
        else:
            assert entry["tooluse"] is True, (
                f"Entry {name!r} does not end in _bulk but has tooluse: {entry['tooluse']}"
            )

    print("PASS: agents catalogue naming convention locked")


def main() -> int:
    tests = [
        test_load_happy_path,
        test_load_raises_on_missing_file,
        test_load_raises_single_missing_provider,
        test_load_raises_cluster_missing_workers,
        test_load_raises_cluster_missing_handler,
        test_load_raises_cluster_workers_count_non_positive,
        test_load_raises_unknown_type,
        test_load_raises_invalid_name_uppercase,
        test_load_raises_invalid_name_dot,
        test_load_raises_duplicate_name,
        test_load_raises_cluster_use_nonexistent,
        test_load_raises_cluster_use_referencing_cluster,
        test_resolve_single_happy_path,
        test_resolve_cluster_happy_path,
        test_resolve_raises_missing_name,
        test_resolve_test_stub_special_case,
        test_resolve_role_null_reviewer_returns_none,
        test_resolve_role_rounds_zero_returns_none,
        test_resolve_role_valid_name_returns_spec,
        test_validate_role_refs_happy_path,
        test_validate_role_refs_missing_raises,
        test_load_falls_back_to_reviewers_yaml,
        test_validate_role_refs_catches_bad_implementer_model,
        test_validate_role_refs_catches_bad_fixer_model,
        test_extends_single_level,
        test_extends_multi_level,
        test_extends_child_overrides_parent_scalar,
        test_extends_unknown_base_raises,
        test_extends_cycle_raises,
        test_extends_self_cycle_raises,
        test_extends_target_must_not_be_cluster,
        test_cluster_cannot_extend,
        test_required_field_missing_after_merge_raises,
        test_extends_field_removed_from_output,
        test_agents_catalogue_naming_convention,
        # --- _reviewer_single tests merged from test-reviewer-single.py ---
        test_single_signature,
        test_single_cluster_spec_raises,
        test_single_test_stub_forwards_prompt,
        test_single_claude_bulk_mode,
        test_single_claude_tool_use_mode,
        test_single_gemini_bulk_mode,
        test_single_unknown_provider_raises,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"\n{failures} of {len(tests)} tests FAILED", file=sys.stderr)
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


# ---------------------------------------------------------------------------
# _reviewer_single tests (was test-reviewer-single.py).
# ---------------------------------------------------------------------------

def test_single_signature() -> None:
    sig = inspect.signature(_reviewer_single.run)
    params = sig.parameters
    assert "spec" in params
    assert "prompt_text" in params
    assert "session_id" in params and params["session_id"].default is None
    assert "resume" in params and params["resume"].default is False
    assert "timeout" in params and params["timeout"].default is None
    assert "effort" not in params, "run must not expose an effort kwarg — effort lives in the spec"
    print("PASS: _reviewer_single.run signature")


def test_single_cluster_spec_raises() -> None:
    cluster_spec = {
        "type": "cluster",
        "workers": {"use": "sonnetmax", "count": 3},
        "handler": {"use": "sonnetmax"},
    }
    try:
        _reviewer_single.run(cluster_spec, "prompt")
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "cluster" in str(exc).lower()
    print("PASS: cluster spec raises ReviewerError")


def test_single_test_stub_forwards_prompt() -> None:
    stub.seed([("# Review\n\n```yaml\nverdict: APPROVE\n```\n", "sid-001")])
    spec = {"type": "single", "provider": "test_stub", "tooluse": False}
    text, session_id = _reviewer_single.run(spec, "hello prompt", session_id="sid-001")
    assert "APPROVE" in text
    captured = stub.captured_prompts()
    assert len(captured) == 1
    assert captured[0][0] == "hello prompt"
    print("PASS: test_stub provider forwards prompt and returns seeded response")


def test_single_claude_bulk_mode() -> None:
    import _llm_claude as llm_claude
    calls: list[dict] = []

    def fake_run_bulk(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("bulk response", "sid-bulk")

    original = llm_claude.run_bulk
    llm_claude.run_bulk = fake_run_bulk
    try:
        spec = {
            "type": "single", "provider": "claude", "model": "claude-sonnet-4-6",
            "effort": "max", "tooluse": False,
        }
        text, sid = _reviewer_single.run(spec, "test prompt", session_id="abc")
        assert text == "bulk response"
        assert len(calls) == 1
        assert calls[0]["model"] == "claude-sonnet-4-6"
        assert calls[0]["effort"] == "max"
        assert "timeout" not in calls[0], "timeout must not be forwarded when None"
    finally:
        llm_claude.run_bulk = original
    print("PASS: claude bulk mode calls run_bulk with model and effort")


def test_single_claude_tool_use_mode() -> None:
    import _llm_claude as llm_claude
    calls: list[dict] = []

    def fake_run_tool_use(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("tool response", "sid-tool")

    original = llm_claude.run_tool_use
    llm_claude.run_tool_use = fake_run_tool_use
    try:
        spec = {
            "type": "single", "provider": "claude", "model": "claude-sonnet-4-6",
            "effort": "max", "tooluse": True,
        }
        text, sid = _reviewer_single.run(spec, "test prompt", timeout=300)
        assert text == "tool response"
        assert len(calls) == 1
        assert calls[0]["model"] == "claude-sonnet-4-6"
        assert calls[0]["effort"] == "max"
        assert calls[0].get("timeout") == 300
    finally:
        llm_claude.run_tool_use = original
    print("PASS: claude tool-use mode calls run_tool_use with model, effort, and timeout")


def test_single_gemini_bulk_mode() -> None:
    import _llm_gemini as llm_gemini
    calls: list[dict] = []

    def fake_run_bulk(prompt_text: str, **kwargs) -> tuple[str, str]:
        calls.append({"prompt_text": prompt_text, **kwargs})
        return ("gemini bulk response", "sid-gemini-bulk")

    original = llm_gemini.run_bulk
    llm_gemini.run_bulk = fake_run_bulk
    try:
        spec = {
            "type": "single", "provider": "gemini", "model": "gemini-2.5-flash",
            "effort": None, "tooluse": False,
        }
        text, sid = _reviewer_single.run(spec, "test prompt", session_id="abc")
        assert text == "gemini bulk response"
        assert len(calls) == 1
        assert calls[0]["model"] == "gemini-2.5-flash"
    finally:
        llm_gemini.run_bulk = original
    print("PASS: gemini bulk mode calls run_bulk with model")


def test_single_unknown_provider_raises() -> None:
    spec = {
        "type": "single", "provider": "unk_provider_xyz", "model": "some-model",
        "effort": "medium", "tooluse": False,
    }
    try:
        _reviewer_single.run(spec, "test prompt")
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        assert "Unknown provider" in str(exc)
        assert "unk_provider_xyz" in str(exc)
    print("PASS: unknown provider raises ReviewerError")


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-reviewers.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-large-prompt-switch.py ---
"""Unit tests for maybe_switch_spec_for_large_prompt and validate_role_refs (large_prompt extension)."""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _review_common import maybe_switch_spec_for_large_prompt  # noqa: E402
from _reviewers import ReviewerError, validate_role_refs  # noqa: E402
from _test_cfg import make_minimal_cfg  # noqa: E402
from _test_registry import make_minimal_registry  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_cfg_with_large_prompt(
    role="code-review",
    scope="holistic",
    threshold_ktok=1,
    reviewer="override-reviewer",
) -> dict:
    cfg = make_minimal_cfg()
    cfg["roles"][role][scope]["large_prompt"] = {
        "threshold_ktok": threshold_ktok,
        "reviewer": reviewer,
    }
    return cfg


def _make_registry_with_cluster() -> dict:
    registry = make_minimal_registry()
    registry["worker_single"] = {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
    }
    registry["my_cluster"] = {
        "type": "cluster",
        "workers": {"use": "worker_single", "count": 3},
        "handler": {"use": "worker_single"},
    }
    return registry


def _override_spec() -> dict:
    return {
        "type": "single",
        "provider": "claude",
        "model": "claude-opus-4-7",
        "effort": "max",
        "tooluse": False,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_below_threshold_no_switch() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 3999
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    assert result_spec is original_spec
    assert result_name == "sonnetmax"
    assert buf.getvalue() == ""
    print("PASS: below threshold no switch")


def test_above_threshold_switches() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 4000
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    assert result_name == "override-reviewer"
    assert result_spec["model"] == "claude-opus-4-7"
    stderr = buf.getvalue()
    assert "large-prompt switch" in stderr
    assert "sonnetmax" in stderr
    assert "override-reviewer" in stderr
    print("PASS: above threshold switches reviewer")


def test_no_large_prompt_config_noop() -> None:
    cfg = make_minimal_cfg()
    registry = make_minimal_registry()
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 100_000
    result_spec, result_name = maybe_switch_spec_for_large_prompt(
        prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
    )
    assert result_spec is original_spec
    assert result_name == "sonnetmax"
    print("PASS: no large_prompt config is noop")


def test_null_reviewer_noop() -> None:
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1, reviewer=None)
    registry = make_minimal_registry()
    original_spec = {"type": "single", "provider": "claude", "model": "claude-sonnet-4-6", "tooluse": False}
    prompt = "x" * 4000
    result_spec, result_name = maybe_switch_spec_for_large_prompt(
        prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
    )
    assert result_spec is original_spec
    assert result_name == "sonnetmax"
    print("PASS: null reviewer is noop")


def test_tooluse_coercion_original_true_override_false() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()  # tooluse=False
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "tooluse": True,
    }
    prompt = "x" * 4000
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    assert result_spec["tooluse"] is True
    assert result_name == "override-reviewer"
    assert "tooluse differs" in buf.getvalue()
    print("PASS: tooluse coercion preserves original tooluse=True")


def test_tooluse_matching_no_notice() -> None:
    registry = make_minimal_registry()
    registry["override-reviewer"] = _override_spec()  # tooluse=False
    cfg = _make_cfg_with_large_prompt(threshold_ktok=1)
    original_spec = {
        "type": "single",
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "tooluse": False,
    }
    prompt = "x" * 4000
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result_spec, result_name = maybe_switch_spec_for_large_prompt(
            prompt, original_spec, "sonnetmax", cfg, "code-review", "holistic", registry
        )
    stderr = buf.getvalue()
    assert result_spec["tooluse"] is False
    assert "tooluse differs" not in stderr
    assert "large-prompt switch" in stderr
    print("PASS: matching tooluse produces no notice")


def test_validate_role_refs_bad_large_prompt_reviewer() -> None:
    cfg = make_minimal_cfg()
    cfg["roles"]["code-review"]["holistic"]["large_prompt"] = {
        "threshold_ktok": 100,
        "reviewer": "nonexistent-override",
    }
    registry = make_minimal_registry()
    try:
        validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        msg = str(exc)
        assert "nonexistent-override" in msg
        assert "large_prompt" in msg
    print("PASS: validate_role_refs raises on bad large_prompt reviewer")


def test_validate_role_refs_cluster_large_prompt_reviewer() -> None:
    cfg = make_minimal_cfg()
    cfg["roles"]["code-review"]["holistic"]["large_prompt"] = {
        "threshold_ktok": 100,
        "reviewer": "my_cluster",
    }
    registry = _make_registry_with_cluster()
    try:
        validate_role_refs(cfg, registry)
        raise AssertionError("Expected ReviewerError")
    except ReviewerError as exc:
        msg = str(exc)
        assert "my_cluster" in msg
        assert "cluster" in msg.lower()
    print("PASS: validate_role_refs raises on cluster large_prompt reviewer")


def main() -> int:
    tests = [
        test_below_threshold_no_switch,
        test_above_threshold_switches,
        test_no_large_prompt_config_noop,
        test_null_reviewer_noop,
        test_tooluse_coercion_original_true_override_false,
        test_tooluse_matching_no_notice,
        test_validate_role_refs_bad_large_prompt_reviewer,
        test_validate_role_refs_cluster_large_prompt_reviewer,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"\n{failures} of {len(tests)} tests FAILED", file=sys.stderr)
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-large-prompt-switch.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-config.py ---
"""Unit tests for plugins/mill/scripts/_config.py.

Covers:
  - load_config: three-layer merge (plugin template -> repo -> local)
  - load_config: environment variable overrides
  - load_config: unknown-key validation and warnings
  - load_config: legacy wiki/config.yaml fallback
  - load_config: local override wins via deep_merge
  - load_config: repo sources absent -> returns plugin template only (lenient)
  - load_config: subfolder-install layout — stub + real config merged
  - load_config: stub-only (real config absent) — hub_relative_path present
  - deep_merge: scalar in overlay wins over scalar in base
  - deep_merge: nested dicts are merged recursively
  - deep_merge: empty overlay leaves base unchanged
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import yaml  # noqa: E402

import _config  # noqa: E402
import _paths  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(path: Path) -> None:
    """Initialise a minimal git repo so resolve_git_root would accept it."""
    subprocess.run(
        ["git", "init", str(path)],
        check=True,
        capture_output=True,
    )


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _setup_plugin_template(tmp_path: Path) -> None:
    """Write a minimal mill-config.yaml template to tmp_path/templates/."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "mill-config.yaml"
    template_path.write_text(
        "spawn:\n  branch_prefix: ''\n"
        "roles:\n"
        "  discussion-review:\n"
        "    holistic:\n"
        "      reviewer: sonnetmax\n"
        "  plan-review:\n"
        "    holistic:\n"
        "      reviewer: sonnetmax\n"
        "    batch:\n"
        "      reviewer: sonnetmedium\n"
        "  code-review:\n"
        "    holistic:\n"
        "      reviewer: sonnetmedium\n"
        "    batch:\n"
        "      reviewer: sonnetmedium\n"
        "  implementer:\n"
        "    model: sonnethigh\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_shared_present() -> None:
    """load_config merges plugin template with repo-layer config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: feat\n")

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "feat", f"Unexpected cfg: {cfg!r}"
    print("PASS load_config — repo config present, overrides plugin template")


def test_load_config_local_override_wins() -> None:
    """load_config deep-merges local override; local values win on conflict."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: repo\n  workers: 2\n")
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "spawn:\n  branch_prefix: local\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "local", (
            f"Local override should win; got {cfg['spawn']['branch_prefix']!r}"
        )
        assert cfg["spawn"]["workers"] == 2, (
            f"Shared key not in local should be preserved; got {cfg['spawn'].get('workers')!r}"
        )
    print("PASS load_config — local override wins; shared-only keys preserved")




def test_load_config_subfolder_install() -> None:
    """load_config merges stub then real config for subfolder-install layout."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "wt"
        wt_root.mkdir()
        # mill-config.yaml at worktree root (not in hub subpath)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: hub_root\n")
        # Stub at worktree root .millhouse
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "hub_relative_path: sub/hub\n",
        )
        # Real config at the declared hub subpath
        _write_yaml(
            wt_root / "sub" / "hub" / ".millhouse" / "config.local.yaml",
            "spawn:\n  branch_prefix: real\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("hub_relative_path") == "sub/hub", (
            f"hub_relative_path from stub should be present; got {cfg.get('hub_relative_path')!r}"
        )
        assert cfg.get("spawn", {}).get("branch_prefix") == "real", (
            f"Real config keys should be in result; got {cfg.get('spawn')!r}"
        )
    print("PASS load_config — subfolder-install: stub + real config merged, both keys present")


def test_load_config_stub_only_real_absent() -> None:
    """load_config returns stub keys when real config is absent (no real hub)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "wt"
        wt_root.mkdir()
        # mill-config.yaml at worktree root (required, but real config at sub/hub will not exist)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: hub_root\n")
        # Stub only — no real config at sub/hub
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "hub_relative_path: sub/hub\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("hub_relative_path") == "sub/hub", (
            f"hub_relative_path from stub should be present; got {cfg.get('hub_relative_path')!r}"
        )
    print("PASS load_config — stub-only (real config absent): hub_relative_path present, real keys absent")


def test_three_layer_merge() -> None:
    """load_config merges plugin template, repo layer, and local layer."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: repo\n")
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "spawn:\n  workers: 4\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "repo", "Repo value should be present"
        assert cfg["spawn"]["workers"] == 4, "Local value should be present"
    print("PASS load_config — three-layer merge")


def test_env_override_impl() -> None:
    """Environment variable overrides config values."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_IMPLEMENTER"] = "custom_model"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["implementer"]["model"] == "custom_model", (
                f"Env override should apply; got {cfg['roles']['implementer'].get('model')!r}"
            )
        finally:
            os.environ.pop("MILL_IMPLEMENTER", None)
    print("PASS load_config — env override applies")


def test_machine_layer_not_loaded() -> None:
    """load_config does not load machine-layer config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: repo\n")

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "repo", "Config should not include machine layer"
    print("PASS load_config — machine layer not loaded")


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


def test_deep_merge_scalar_wins() -> None:
    """Scalar overlay value wins over scalar base value."""
    result = _config.deep_merge({"a": 1, "b": 2}, {"b": 99})
    assert result == {"a": 1, "b": 99}, f"Unexpected: {result!r}"
    print("PASS deep_merge — scalar overlay wins")


def test_deep_merge_nested_merge() -> None:
    """Nested dicts are merged recursively; disjoint keys from both sides survive."""
    base = {"x": {"p": 1, "q": 2}}
    overlay = {"x": {"q": 99, "r": 3}}
    result = _config.deep_merge(base, overlay)
    assert result == {"x": {"p": 1, "q": 99, "r": 3}}, f"Unexpected: {result!r}"
    print("PASS deep_merge — nested merge, overlay wins on conflict, disjoint keys kept")


def test_deep_merge_empty_overlay() -> None:
    """An empty overlay leaves the base dict unchanged."""
    base = {"a": 1, "b": {"c": 2}}
    result = _config.deep_merge(base, {})
    assert result == base, f"Unexpected: {result!r}"
    # Must be a copy, not the same object.
    assert result is not base, "deep_merge must return a new dict, not the base"
    print("PASS deep_merge — empty overlay returns copy of base")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# set_local_wiki_overrides
# ---------------------------------------------------------------------------


def test_no_op_when_both_args_none() -> None:
    """Returns False and creates no file when both repo_url and branch are None."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        result = _config.set_local_wiki_overrides(cfg_path, repo_url=None, branch=None)
        assert result is False, f"Expected False, got {result!r}"
        assert not cfg_path.exists(), "File must not be created when both args are None"
    print("PASS set_local_wiki_overrides — no-op when both args are None")


def test_creates_file_when_missing() -> None:
    """Creates the file with wiki.repo_url when file did not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://example.com/x.git", branch=None
        )
        assert result is True, f"Expected True, got {result!r}"
        assert cfg_path.exists(), "File must be created"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data["wiki"]["repo_url"] == "https://example.com/x.git"
        assert "branch" not in data["wiki"], "branch key must be absent"
    print("PASS set_local_wiki_overrides — creates file with repo_url; branch absent")


def test_updates_existing_value() -> None:
    """Updates repo_url in an existing file."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        cfg_path.write_text(
            yaml.safe_dump({"wiki": {"repo_url": "https://old.git"}}, sort_keys=False),
            encoding="utf-8",
        )
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://new.git", branch=None
        )
        assert result is True, f"Expected True, got {result!r}"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data["wiki"]["repo_url"] == "https://new.git"
    print("PASS set_local_wiki_overrides — updates existing repo_url value")


def test_idempotent_when_already_correct() -> None:
    """Returns False without touching the file when content is already up-to-date."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        initial_data = {"wiki": {"repo_url": "https://x.git", "branch": "B"}}
        initial_text = yaml.safe_dump(initial_data, sort_keys=False, allow_unicode=True)
        cfg_path.write_text(initial_text, encoding="utf-8")
        before = cfg_path.read_text(encoding="utf-8")
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://x.git", branch="B"
        )
        assert result is False, f"Expected False (no-op), got {result!r}"
        after = cfg_path.read_text(encoding="utf-8")
        assert before == after, "File contents must be unchanged on no-op"
    print("PASS set_local_wiki_overrides — idempotent when already correct")


def test_partial_update_branch_only_preserves_repo_url() -> None:
    """Updating only branch preserves the existing repo_url."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        cfg_path.write_text(
            yaml.safe_dump(
                {"wiki": {"repo_url": "https://x.git", "branch": "old"}},
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        result = _config.set_local_wiki_overrides(cfg_path, repo_url=None, branch="new")
        assert result is True, f"Expected True, got {result!r}"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data["wiki"]["repo_url"] == "https://x.git", "repo_url must be preserved"
        assert data["wiki"]["branch"] == "new", "branch must be updated"
    print("PASS set_local_wiki_overrides — partial update: branch updated, repo_url preserved")


def test_preserves_other_top_level_keys() -> None:
    """Adds wiki block without removing other top-level keys."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        cfg_path.write_text(
            yaml.safe_dump({"hub_relative_path": "."}, sort_keys=False),
            encoding="utf-8",
        )
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://x.git", branch=None
        )
        assert result is True, f"Expected True, got {result!r}"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data.get("hub_relative_path") == ".", "hub_relative_path must be preserved"
        assert data["wiki"]["repo_url"] == "https://x.git", "wiki.repo_url must be present"
    print("PASS set_local_wiki_overrides — other top-level keys preserved")


def test_env_override_discussion_reviewer() -> None:
    """MILL_DISCUSSION_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_DISCUSSION_REVIEWER"] = "custom_reviewer"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["discussion-review"]["holistic"]["reviewer"] == "custom_reviewer"
        finally:
            os.environ.pop("MILL_DISCUSSION_REVIEWER", None)
    print("PASS load_config — MILL_DISCUSSION_REVIEWER env override")


def test_env_override_plan_reviewer() -> None:
    """MILL_PLAN_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_PLAN_REVIEWER"] = "custom_holistic"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["plan-review"]["holistic"]["reviewer"] == "custom_holistic"
        finally:
            os.environ.pop("MILL_PLAN_REVIEWER", None)
    print("PASS load_config — MILL_PLAN_REVIEWER env override")


def test_env_override_plan_batch_reviewer() -> None:
    """MILL_PLAN_BATCH_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_PLAN_BATCH_REVIEWER"] = "custom_batch"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["plan-review"]["batch"]["reviewer"] == "custom_batch"
        finally:
            os.environ.pop("MILL_PLAN_BATCH_REVIEWER", None)
    print("PASS load_config — MILL_PLAN_BATCH_REVIEWER env override")


def test_env_override_code_reviewer() -> None:
    """MILL_CODE_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_CODE_REVIEWER"] = "custom_code_holistic"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["code-review"]["holistic"]["reviewer"] == "custom_code_holistic"
        finally:
            os.environ.pop("MILL_CODE_REVIEWER", None)
    print("PASS load_config — MILL_CODE_REVIEWER env override")


def test_env_override_code_batch_reviewer() -> None:
    """MILL_CODE_BATCH_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_CODE_BATCH_REVIEWER"] = "custom_code_batch"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["code-review"]["batch"]["reviewer"] == "custom_code_batch"
        finally:
            os.environ.pop("MILL_CODE_BATCH_REVIEWER", None)
    print("PASS load_config — MILL_CODE_BATCH_REVIEWER env override")


def test_env_override_empty_string_is_noop() -> None:
    """Empty-string env value is treated as unset."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_PLAN_REVIEWER"] = ""
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            # Should use the template value, not empty string
            assert cfg["roles"]["plan-review"]["holistic"]["reviewer"] == "sonnetmax"
        finally:
            os.environ.pop("MILL_PLAN_REVIEWER", None)
    print("PASS load_config — empty-string env value is noop")


def test_list_replace_semantics() -> None:
    """Lists are replaced wholesale, not merged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "verify:\n  skip_known_broken:\n    - a.py\n    - b.py\n",
        )
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "verify:\n  skip_known_broken:\n    - c.py\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("verify", {}).get("skip_known_broken") == ["c.py"], (
            f"List should be replaced, not merged; got {cfg.get('verify', {}).get('skip_known_broken')!r}"
        )
    print("PASS load_config — list replace semantics")


def test_unknown_key_warning_emitted() -> None:
    """Unknown keys in local config emit warnings to stderr."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "pipeline:\n  autonomous_mode: true\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert "pipeline" in stderr_output, (
            f"Unknown key warning should be in stderr; got {stderr_output!r}"
        )
    print("PASS load_config — unknown-key warning emitted")


def test_deep_merge_none_overlay_dict_base() -> None:
    """None overlay on dict base skips override, preserves base dict."""
    result = _config.deep_merge({"roles": {"k": "v"}}, {"roles": None})
    assert result == {"roles": {"k": "v"}}, f"None overlay must not clobber base dict; got {result!r}"
    print("PASS deep_merge -- None overlay on dict base is skipped, base dict preserved")


def test_deep_merge_none_overlay_scalar_base() -> None:
    """None overlay on scalar base is allowed (reviewer: null semantics)."""
    result = _config.deep_merge({"reviewer": "foo"}, {"reviewer": None})
    assert result == {"reviewer": None}, f"None overlay should override scalar; got {result!r}"
    print("PASS deep_merge -- None overlay on scalar base allowed (reviewer: null semantics)")


def test_resolve_plugin_template_path_stale_root() -> None:
    """resolve_plugin_template_path with stale CLAUDE_PLUGIN_ROOT falls back with warning."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        nonexistent_root = tmp_path / "nonexistent_plugin_root"
        _saved_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        try:
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(nonexistent_root)
            with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                result = _config.resolve_plugin_template_path("mill-config.yaml")
                stderr_output = mock_stderr.getvalue()
            fallback_path = Path(_config.__file__).resolve().parent.parent / "templates" / "mill-config.yaml"
            assert result == fallback_path, (
                f"Expected fallback path {fallback_path}, got {result}"
            )
            assert "CLAUDE_PLUGIN_ROOT" in stderr_output or str(nonexistent_root) in stderr_output, (
                f"Expected warning about CLAUDE_PLUGIN_ROOT or path in stderr; got {stderr_output!r}"
            )
        finally:
            if _saved_root is not None:
                os.environ["CLAUDE_PLUGIN_ROOT"] = _saved_root
            else:
                os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
    print("PASS resolve_plugin_template_path -- stale CLAUDE_PLUGIN_ROOT falls back to source tree with warning")


def test_load_config_bare_roles_key() -> None:
    """load_config with bare roles: key does not crash; template roles: dict preserved."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        wt_root.mkdir(parents=True)
        _write_yaml(wt_root / "mill-config.yaml", "roles:\n")
        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                result = _config.load_config(wt_root, wt_root)
        assert isinstance(result.get("roles"), dict), (
            f"Expected roles to be a dict; got {result.get('roles')!r}"
        )
    print("PASS load_config -- bare roles: key does not crash; template roles: dict preserved")


def test_load_config_hub_relative_path_no_warning() -> None:
    """load_config with hub_relative_path in config.local.yaml does not emit unknown-key warning."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")
        _write_yaml(wt_root / ".millhouse" / "config.local.yaml", "hub_relative_path: subdir\n")
        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()
        assert "hub_relative_path" not in stderr_output, (
            f"hub_relative_path should not appear in warning; got {stderr_output!r}"
        )
    print("PASS load_config -- hub_relative_path in config.local.yaml does not emit unknown-key warning")


def test_load_config_no_hub_overlay_returns_template() -> None:
    """load_config without hub overlay (mill-config.yaml absent) returns template defaults."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        hub_root = tmp_path / "hub"
        hub_root.mkdir()
        # No mill-config.yaml at hub_root; test that load_config does not raise

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(hub_root, hub_root)

        # Should return template defaults, not raise FileNotFoundError
        assert isinstance(cfg, dict), f"Expected dict, got {type(cfg)!r}"
        assert cfg.get("spawn", {}).get("branch_prefix") == "", (
            f"Template default should be present; got {cfg.get('spawn')!r}"
        )
    print("PASS load_config -- no hub overlay: returns template defaults, does not raise")


def test_load_config_sub_project_hub_overlay() -> None:
    """load_config with sub-project hub overlay merges template + hub overlay."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        # Hub is in a subdirectory (sub-project layout)
        hub_root = tmp_path / "projects" / "sub"
        hub_root.mkdir(parents=True)
        # Hub overlay with non-default value
        _write_yaml(hub_root / "mill-config.yaml", "spawn:\n  branch_prefix: sub_project\n")

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(hub_root, tmp_path)

        # Hub overlay should win over template
        assert cfg.get("spawn", {}).get("branch_prefix") == "sub_project", (
            f"Hub overlay value should win; got {cfg.get('spawn', {}).get('branch_prefix')!r}"
        )
    print("PASS load_config -- sub-project hub overlay: hub value wins over template")


def test_worktree_template_augments_template_cfg() -> None:
    """load_config augments template_cfg with worktree-local template to avoid unknown-key warnings."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Set up cache template without pipeline.max_cards_per_batch
        cache_template_dir = tmp_path / "cache_templates"
        cache_template_dir.mkdir(parents=True, exist_ok=True)
        cache_template_path = cache_template_dir / "mill-config.yaml"
        cache_template_path.write_text(
            "spawn:\n  branch_prefix: ''\n"
            "roles:\n"
            "  discussion-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax\n"
            "  plan-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  code-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmedium\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  implementer:\n"
            "    model: sonnethigh\n",
            encoding="utf-8",
        )

        # Set up worktree with its own template that includes pipeline.max_cards_per_batch
        wt_root = tmp_path / "wt"
        wt_root.mkdir()
        wt_template_dir = wt_root / "plugins" / "mill" / "templates"
        wt_template_dir.mkdir(parents=True, exist_ok=True)
        wt_template_path = wt_template_dir / "mill-config.yaml"
        wt_template_path.write_text(
            "spawn:\n  branch_prefix: ''\n"
            "pipeline:\n  max_cards_per_batch: 10\n"
            "roles:\n"
            "  discussion-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax\n"
            "  plan-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  code-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmedium\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  implementer:\n"
            "    model: sonnethigh\n",
            encoding="utf-8",
        )

        # Set up hub config with pipeline.max_cards_per_batch
        hub_config_path = wt_root / "mill-config.yaml"
        hub_config_path.write_text(
            "pipeline:\n  max_cards_per_batch: 10\n",
            encoding="utf-8",
        )
        _git_init(wt_root)

        # Capture stderr to check for unknown-key warnings
        with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=cache_template_path
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            stderr_output = mock_stderr.getvalue()
            # Check that pipeline.max_cards_per_batch doesn't generate unknown-key warning
            assert "unknown key: pipeline.max_cards_per_batch" not in stderr_output, (
                f"Unexpected unknown-key warning; stderr: {stderr_output!r}"
            )
            # And verify the key is in the result
            assert cfg.get("pipeline", {}).get("max_cards_per_batch") == 10, (
                f"Expected pipeline.max_cards_per_batch in result; got {cfg.get('pipeline')!r}"
            )
    print("PASS load_config -- worktree template augments template_cfg, no unknown-key warning")


def test_same_template_path_skips_augmentation() -> None:
    """load_config skips augmentation when worktree template path resolves to same path."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "wt"
        wt_root.mkdir()

        # Create a worktree but DON'T create plugins/mill/templates/mill-config.yaml
        # (or create it with identical content)
        # This tests the guard: if _worktree_template.exists() is False
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        # When worktree template doesn't exist, augmentation is skipped
        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        # Result should still have the template and repo config merged
        assert cfg.get("spawn", {}).get("branch_prefix") == "test", (
            f"Repo config should be present; got {cfg.get('spawn')!r}"
        )
    print("PASS load_config -- same/missing template path skips augmentation")


def test_dispatch_shim_via_psmux_true_resolves_to_psmux() -> None:
    """dispatch shim converts via_psmux: true to dispatch: psmux."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    psmux:\n      via_psmux: true\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    cfg = _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "psmux", (
            f"Expected dispatch: psmux, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
        assert "[config] llm.claude.psmux.via_psmux is deprecated" in stderr_output, (
            f"Expected deprecation warning in stderr, got {stderr_output!r}"
        )
    print("PASS dispatch shim -- via_psmux: true -> dispatch: psmux with deprecation warning")


def test_dispatch_shim_via_psmux_false_resolves_to_subprocess() -> None:
    """dispatch shim converts via_psmux: false to dispatch: subprocess."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    psmux:\n      via_psmux: false\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "subprocess", (
            f"Expected dispatch: subprocess, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
    print("PASS dispatch shim -- via_psmux: false -> dispatch: subprocess")


def test_dispatch_shim_explicit_dispatch_wins_over_via_psmux() -> None:
    """Explicit dispatch key wins over legacy via_psmux."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    dispatch: agent\n    psmux:\n      via_psmux: true\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "agent", (
            f"Expected dispatch: agent, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
    print("PASS dispatch shim -- explicit dispatch wins over via_psmux")


def test_via_psmux_does_not_trigger_unknown_key_warning() -> None:
    """via_psmux does not trigger generic unknown-key warning."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    psmux:\n      via_psmux: false\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert "unknown key: llm.claude.psmux.via_psmux" not in stderr_output, (
            f"via_psmux should not trigger unknown-key warning, stderr: {stderr_output!r}"
        )
    print("PASS dispatch shim -- via_psmux does not trigger unknown-key warning")


def test_dispatch_shim_unknown_value_falls_back_to_subprocess() -> None:
    """Unknown dispatch value falls back to subprocess with error message."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    dispatch: invalid_value\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    cfg = _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "subprocess", (
            f"Expected fallback to subprocess, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
        assert "invalid_value" in stderr_output and "falling back" in stderr_output, (
            f"Expected error message in stderr, got {stderr_output!r}"
        )
    print("PASS dispatch shim -- unknown dispatch value falls back to subprocess with error")


def main() -> int:
    tests = [
        test_load_config_shared_present,
        test_load_config_local_override_wins,
        test_load_config_subfolder_install,
        test_load_config_stub_only_real_absent,
        test_three_layer_merge,
        test_env_override_impl,
        test_env_override_discussion_reviewer,
        test_env_override_plan_reviewer,
        test_env_override_plan_batch_reviewer,
        test_env_override_code_reviewer,
        test_env_override_code_batch_reviewer,
        test_env_override_empty_string_is_noop,
        test_list_replace_semantics,
        test_unknown_key_warning_emitted,
        test_machine_layer_not_loaded,
        test_deep_merge_scalar_wins,
        test_deep_merge_nested_merge,
        test_deep_merge_empty_overlay,
        test_deep_merge_none_overlay_dict_base,
        test_deep_merge_none_overlay_scalar_base,
        test_resolve_plugin_template_path_stale_root,
        test_load_config_bare_roles_key,
        test_load_config_hub_relative_path_no_warning,
        test_load_config_no_hub_overlay_returns_template,
        test_load_config_sub_project_hub_overlay,
        test_no_op_when_both_args_none,
        test_creates_file_when_missing,
        test_updates_existing_value,
        test_idempotent_when_already_correct,
        test_partial_update_branch_only_preserves_repo_url,
        test_preserves_other_top_level_keys,
        test_worktree_template_augments_template_cfg,
        test_same_template_path_skips_augmentation,
        test_dispatch_shim_via_psmux_true_resolves_to_psmux,
        test_dispatch_shim_via_psmux_false_resolves_to_subprocess,
        test_dispatch_shim_explicit_dispatch_wins_over_via_psmux,
        test_via_psmux_does_not_trigger_unknown_key_warning,
        test_dispatch_shim_unknown_value_falls_back_to_subprocess,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-config.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-code.py ---
"""
Integration test for millpy-review-code.py

The .millhouse/ layout, wiki junction, and slug file are placed inside
$tmp/project/ (not directly in $tmp/) because the code backend uses
cwd=project_root for its git commands (git merge-base, git diff).

Setup:
  1. Init git repo in $tmp/project/ with main branch.
  2. Create base-file.py, commit as "base" on main.
  3. Checkout task-branch; apply sample-code-diff.patch; commit.
  4. Seed .millhouse/ + wiki junction + slug file inside $tmp/project/.
  5. Seed active/test-slug/plan/00-overview.md in the fixture wiki.
  6. Invoke millpy-review-code.py with cwd=$tmp/project/.

Assertions:
  - Exit 0
  - Valid JSON with type="code", reviews length 1, scope="holistic"
  - review file exists, has matching verdict: in frontmatter

Also tests the "No active task" error path.

Prerequisites: claude in PATH, valid Claude subscription, git in PATH.

Usage (from hub/):
    python plugins/mill/integration_tests/test-review-code.py

Exits 0 on PASS, non-zero with a descriptive error on FAIL.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


# Resolve paths relative to this file
_INTEGRATION_TESTS_DIR = Path(__file__).resolve().parent
_MILL_ROOT = _INTEGRATION_TESTS_DIR.parent
_HUB = _MILL_ROOT.parent.parent          # plugins/mill -> plugins -> hub
_SCRIPTS = _MILL_ROOT / "scripts"
_PLUGIN_ROOT = _MILL_ROOT
_FIXTURES = _INTEGRATION_TESTS_DIR / "fixtures"
_SCRATCH = _HUB / ".scratch"

# Ensure scripts/ is importable
sys.path.insert(0, str(_SCRIPTS))
import _junction  # noqa: E402  (after sys.path manipulation)
import _review_common  # noqa: E402
import _safe_rmtree  # noqa: E402


_CONFIG_YAML = """\
paths:
  discussion_file: active/<SLUG>/discussion.md
  plan_dir:        active/<SLUG>/plan/
  reviews_dir:     active/<SLUG>/reviews/

review:
  discussion:
    rounds: 2
    holistic: sonnetmax

  plan:
    rounds: 3
    batch: sonnetmax
    holistic: sonnetmax

  code:
    rounds: 3
    reviewer: sonnetmax
    style: single
"""

_SLUG_FILE_CONTENT = """\
---
slug: test-slug
task_title: "Test code review"
---
"""

_PLAN_OVERVIEW_CONTENT = """\
---
kind: plan-overview
task: Test code review
verify: N/A
dev-server: N/A
approved: true
started: 20260420-100000
batches: [core]
root: .
---

# Test code review — Plan

## Context

Small refactor of base-file.py: add input validation to `greet()`, introduce
a `slugify()` helper with lru_cache.

## All Files Touched

- base-file.py
"""

_BASE_FILE_CONTENT = '''\
"""base-file.py — simple utility module used as a code-review test fixture."""
from __future__ import annotations


def greet(name: str) -> str:
    """Return a greeting string for the given name."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


def main() -> None:
    print(greet("world"))
    print(add(1, 2))


if __name__ == "__main__":
    main()
'''

_MODIFIED_FILE_CONTENT = '''\
"""base-file.py — simple utility module used as a code-review test fixture."""
from __future__ import annotations

import re
from functools import lru_cache


def greet(name: str) -> str:
    """Return a greeting string for the given name."""
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"


@lru_cache(maxsize=128)
def slugify(text: str) -> str:
    """Return a URL-safe slug of text."""
    slug = re.sub(r"\\s+", "-", text.strip().lower())
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug


def main() -> None:
    print(greet("world"))
    print(slugify("Hello World"))
    print(slugify("Hello World"))  # cached hit


if __name__ == "__main__":
    main()
'''


def _git(project_root: Path, *args: str) -> None:
    """Run a git command inside project_root, raise on non-zero exit."""
    result = subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )


def _run_script(script: Path, cwd: Path) -> tuple[int, str, str]:
    """Run a Python script; return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["uv", "run", "--project", str(_PLUGIN_ROOT), str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = _SCRATCH / f"mill-layer02-test-code-{uuid.uuid4().hex[:8]}"
    tmp.mkdir()
    failed = False
    try:
        project_root = tmp / "project"
        project_root.mkdir()

        # ---------------------------------------------------------------
        # Setup: git repo
        # ---------------------------------------------------------------
        _git(project_root, "init", "--initial-branch=main")
        _git(project_root, "config", "user.email", "test@mill")
        _git(project_root, "config", "user.name", "mill-test")

        base_file = project_root / "base-file.py"
        base_file.write_text(_BASE_FILE_CONTENT, encoding="utf-8")
        _git(project_root, "add", "base-file.py")
        _git(project_root, "commit", "-m", "base")

        _git(project_root, "checkout", "-b", "task-branch")

        # Instead of applying a brittle patch fixture, write the modified
        # base-file.py directly and commit. Diff is generated naturally by
        # `git diff main..HEAD` inside the code-review backend.
        base_file.write_text(_MODIFIED_FILE_CONTENT, encoding="utf-8")
        _git(project_root, "add", "base-file.py")
        _git(project_root, "commit", "-m", "apply diff")

        # ---------------------------------------------------------------
        # Setup: .millhouse/ + wiki fixture inside project_root
        # ---------------------------------------------------------------
        millhouse_dir = project_root / ".millhouse"
        wiki_dir = project_root / "wiki-fixture"
        plan_dir = wiki_dir / "active" / "test-slug" / "plan"
        reviews_dir = wiki_dir / "active" / "test-slug" / "reviews"

        millhouse_dir.mkdir()
        plan_dir.mkdir(parents=True)
        reviews_dir.mkdir(parents=True)

        (millhouse_dir / ".test-slug.slug.md").write_text(
            _SLUG_FILE_CONTENT, encoding="utf-8"
        )
        (wiki_dir / "config.yaml").write_text(_CONFIG_YAML, encoding="utf-8")
        (plan_dir / "00-overview.md").write_text(_PLAN_OVERVIEW_CONTENT, encoding="utf-8")

        # Create wiki junction: .millhouse/wiki -> wiki-fixture/
        _junction.create(wiki_dir.resolve(), (millhouse_dir / "wiki").resolve())

        # ---------------------------------------------------------------
        # Test 1: happy path
        # ---------------------------------------------------------------
        print("Test 1: happy path (code review)...", file=sys.stderr)

        script = _SCRIPTS / "millpy-review-code.py"
        exit_code, stdout, stderr = _run_script(script, project_root)

        if exit_code != 0:
            print(f"FAIL: millpy-review-code.py exited {exit_code}")
            print(f"stderr: {stderr}")
            print(f"stdout: {stdout}")
            failed = True
            return 1

        if not stdout.strip():
            print("FAIL: stdout is empty (expected JSON)")
            failed = True
            return 1

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            print(f"FAIL: stdout is not valid JSON: {stdout!r} ({exc})")
            failed = True
            return 1

        if result.get("type") != "code":
            print(f"FAIL: expected type='code', got {result.get('type')!r}")
            failed = True
            return 1

        if result.get("round") != 1:
            print(f"FAIL: expected round=1, got {result.get('round')!r}")
            failed = True
            return 1

        if result.get("verdict") not in ("APPROVE", "REQUEST_CHANGES"):
            print(f"FAIL: unexpected verdict {result.get('verdict')!r}")
            failed = True
            return 1

        reviews = result.get("reviews", [])
        if len(reviews) != 1:
            print(f"FAIL: expected reviews length 1, got {len(reviews)}")
            failed = True
            return 1

        if reviews[0].get("scope") != "holistic":
            print(
                f"FAIL: expected reviews[0].scope='holistic', got {reviews[0].get('scope')!r}"
            )
            failed = True
            return 1

        review_file = Path(reviews[0]["file"])
        if not review_file.exists():
            print(f"FAIL: review file does not exist: {review_file}")
            failed = True
            return 1

        # Use production parse_verdict — no duplicate YAML-block parser in tests.
        file_verdict = _review_common.parse_verdict(review_file.read_text(encoding="utf-8"))
        entry_verdict = reviews[0]["verdict"]
        if file_verdict != entry_verdict:
            print(
                f"FAIL: review file verdict={file_verdict!r}, "
                f"expected {entry_verdict!r} (matching reviews[0].verdict)"
            )
            failed = True
            return 1

        print("Test 1 PASS", file=sys.stderr)

        # ---------------------------------------------------------------
        # Test 2: error path — no active task (slug file removed)
        # ---------------------------------------------------------------
        print("Test 2: error path (no active task)...", file=sys.stderr)

        slug_file = millhouse_dir / ".test-slug.slug.md"
        slug_file.unlink()

        exit_code2, stdout2, stderr2 = _run_script(script, project_root)

        if exit_code2 == 0:
            print("FAIL: expected exit 1 when no slug file present, got exit 0")
            failed = True
            return 1

        combined = stdout2 + stderr2
        if "No active task" not in combined:
            print(f"FAIL: expected 'No active task' in output, got: {combined!r}")
            failed = True
            return 1

        print("Test 2 PASS", file=sys.stderr)

    except Exception:
        failed = True
        raise
    finally:
        if failed:
            print(f"Scratch dir preserved for inspection: {tmp}", file=sys.stderr)
        else:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)

    print("PASS — all code review tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-code.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-discussion.py ---
"""
Integration test for millpy-review-discussion.py

Sets up a temporary .millhouse/ layout with a seeded slug file, a wiki/
junction pointing at a fixture wiki containing a sample discussion.md,
then invokes millpy-review-discussion.py and asserts:
  - Exit 0
  - Valid JSON with type/round/verdict/reviews fields
  - verdict in {APPROVE, GAPS_FOUND}  (discussion uses v1 GAPS_FOUND vocab)
  - reviews has 1 entry, scope == "holistic"
  - review file exists on disk
  - review file has YAML frontmatter with matching verdict:

Also tests the "No active task" error path.

Prerequisites: claude in PATH, valid Claude subscription.

Usage (from hub/):
    python plugins/mill/integration_tests/test-review-discussion.py

Exits 0 on PASS, non-zero with a descriptive error on FAIL.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path


# Resolve paths relative to this file
_INTEGRATION_TESTS_DIR = Path(__file__).resolve().parent
_MILL_ROOT = _INTEGRATION_TESTS_DIR.parent
_HUB = _MILL_ROOT.parent.parent          # plugins/mill -> plugins -> hub
_SCRIPTS = _MILL_ROOT / "scripts"
_PLUGIN_ROOT = _MILL_ROOT
_FIXTURES = _INTEGRATION_TESTS_DIR / "fixtures"
_SCRATCH = _HUB / ".scratch"

# Ensure scripts/ is importable
sys.path.insert(0, str(_SCRIPTS))
import _junction  # noqa: E402  (after sys.path manipulation)
import _review_common  # noqa: E402
import _safe_rmtree  # noqa: E402

import subprocess  # noqa: E402


_CONFIG_YAML = """\
paths:
  discussion_file: active/<SLUG>/discussion.md
  plan_dir:        active/<SLUG>/plan/
  reviews_dir:     active/<SLUG>/reviews/

review:
  discussion:
    rounds: 2
    holistic: sonnetmax

  plan:
    rounds: 3
    batch: sonnetmax
    holistic: sonnetmax

  code:
    rounds: 3
    reviewer: sonnetmax
    style: single
"""

_SLUG_FILE_CONTENT = """\
---
slug: test-slug
task_title: "Test discussion review"
---
"""


def _remove_tree(root: Path) -> None:
    """Remove a scratch tree, detaching any NTFS junctions first."""
    junction = root / ".millhouse" / "wiki"
    if junction.exists() or junction.is_symlink():
        _junction.remove(junction)
    _safe_rmtree.safe_rmtree(root, allowed_root=root, ignore_errors=True)


def _run_script(script: Path, cwd: Path) -> tuple[int, str, str]:
    """Run a Python script; return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["uv", "run", "--project", str(_PLUGIN_ROOT), str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = _SCRATCH / f"mill-layer02-test-discussion-{uuid.uuid4().hex[:8]}"
    tmp.mkdir()
    failed = False
    try:
        # ---------------------------------------------------------------
        # Setup
        # ---------------------------------------------------------------
        millhouse_dir = tmp / ".millhouse"
        wiki_dir = tmp / "wiki-fixture"
        active_dir = wiki_dir / "active" / "test-slug"
        reviews_dir = active_dir / "reviews"

        millhouse_dir.mkdir()
        active_dir.mkdir(parents=True)
        reviews_dir.mkdir(parents=True)

        (millhouse_dir / ".test-slug.slug.md").write_text(
            _SLUG_FILE_CONTENT, encoding="utf-8"
        )
        (wiki_dir / "config.yaml").write_text(_CONFIG_YAML, encoding="utf-8")

        # Seed discussion fixture
        shutil.copy(_FIXTURES / "sample-discussion.md", active_dir / "discussion.md")

        # Create wiki junction: .millhouse/wiki -> wiki-fixture/
        _junction.create(wiki_dir.resolve(), (millhouse_dir / "wiki").resolve())

        # ---------------------------------------------------------------
        # Test 1: happy path
        # ---------------------------------------------------------------
        print("Test 1: happy path (discussion review)...", file=sys.stderr)

        script = _SCRIPTS / "millpy-review-discussion.py"
        exit_code, stdout, stderr = _run_script(script, tmp)

        if exit_code != 0:
            print(f"FAIL: millpy-review-discussion.py exited {exit_code}")
            print(f"stderr: {stderr}")
            print(f"stdout: {stdout}")
            failed = True
            return 1

        if not stdout.strip():
            print("FAIL: stdout is empty (expected JSON)")
            failed = True
            return 1

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            print(f"FAIL: stdout is not valid JSON: {stdout!r} ({exc})")
            failed = True
            return 1

        if result.get("type") != "discussion":
            print(f"FAIL: expected type='discussion', got {result.get('type')!r}")
            failed = True
            return 1

        if result.get("round") != 1:
            print(f"FAIL: expected round=1, got {result.get('round')!r}")
            failed = True
            return 1

        if result.get("verdict") not in ("APPROVE", "GAPS_FOUND"):
            print(f"FAIL: unexpected verdict {result.get('verdict')!r}")
            failed = True
            return 1

        reviews = result.get("reviews", [])
        if len(reviews) != 1:
            print(f"FAIL: expected reviews length 1, got {len(reviews)}")
            failed = True
            return 1

        if reviews[0].get("scope") != "holistic":
            print(
                f"FAIL: expected reviews[0].scope='holistic', got {reviews[0].get('scope')!r}"
            )
            failed = True
            return 1

        review_file = Path(reviews[0]["file"])
        if not review_file.exists():
            print(f"FAIL: review file does not exist: {review_file}")
            failed = True
            return 1

        # Use production parse_verdict — no duplicate YAML-block parser in tests.
        file_verdict = _review_common.parse_verdict(review_file.read_text(encoding="utf-8"))
        entry_verdict = reviews[0]["verdict"]
        if file_verdict != entry_verdict:
            print(
                f"FAIL: review file verdict={file_verdict!r}, "
                f"expected {entry_verdict!r} (matching reviews[0].verdict)"
            )
            failed = True
            return 1

        print("Test 1 PASS", file=sys.stderr)

        # ---------------------------------------------------------------
        # Test 2: error path — no active task (slug file removed)
        # ---------------------------------------------------------------
        print("Test 2: error path (no active task)...", file=sys.stderr)

        slug_file = millhouse_dir / ".test-slug.slug.md"
        slug_file.unlink()

        exit_code2, stdout2, stderr2 = _run_script(script, tmp)

        if exit_code2 == 0:
            print("FAIL: expected exit 1 when no slug file present, got exit 0")
            failed = True
            return 1

        combined = stdout2 + stderr2
        if "No active task" not in combined:
            print(f"FAIL: expected 'No active task' in output, got: {combined!r}")
            failed = True
            return 1

        print("Test 2 PASS", file=sys.stderr)

    except Exception:
        failed = True
        raise
    finally:
        if failed:
            print(f"Scratch dir preserved for inspection: {tmp}", file=sys.stderr)
        else:
            _remove_tree(tmp)

    print("PASS — all discussion review tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-discussion.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-plan.py ---
"""
Integration test for millpy-review-plan.py

Sets up a temporary .millhouse/ layout with a seeded slug file, a wiki/
junction pointing at a fixture wiki containing a sample plan (00-overview.md
+ 01-core.md), then invokes millpy-review-plan.py and asserts:
  - Exit 0
  - Valid JSON with type/round/verdict/reviews fields
  - verdict in {APPROVE, REQUEST_CHANGES}
  - reviews has 2 entries (1 batch + 1 holistic)
  - reviews contains entry with scope "01-core" and entry with scope "holistic"
  - each entry's file exists on disk
  - each review file has YAML frontmatter with matching verdict:

Also tests the "No active task" error path.

Prerequisites: claude in PATH, valid Claude subscription.

Usage (from hub/):
    python plugins/mill/integration_tests/test-review-plan.py

Exits 0 on PASS, non-zero with a descriptive error on FAIL.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path


# Resolve paths relative to this file
_INTEGRATION_TESTS_DIR = Path(__file__).resolve().parent
_MILL_ROOT = _INTEGRATION_TESTS_DIR.parent
_HUB = _MILL_ROOT.parent.parent          # plugins/mill -> plugins -> hub
_SCRIPTS = _MILL_ROOT / "scripts"
_PLUGIN_ROOT = _MILL_ROOT
_FIXTURES = _INTEGRATION_TESTS_DIR / "fixtures"
_SCRATCH = _HUB / ".scratch"

# Ensure scripts/ is importable
sys.path.insert(0, str(_SCRIPTS))
import _junction  # noqa: E402  (after sys.path manipulation)
import _review_common  # noqa: E402
import _safe_rmtree  # noqa: E402

import subprocess  # noqa: E402


_CONFIG_YAML = """\
paths:
  discussion_file: active/<SLUG>/discussion.md
  plan_dir:        active/<SLUG>/plan/
  reviews_dir:     active/<SLUG>/reviews/

review:
  discussion:
    rounds: 2
    holistic: sonnetmax

  plan:
    rounds: 3
    batch: sonnetmax
    holistic: sonnetmax

  code:
    rounds: 3
    reviewer: sonnetmax
    style: single
"""

_SLUG_FILE_CONTENT = """\
---
slug: test-slug
task_title: "Test plan review"
---
"""


def _remove_tree(root: Path) -> None:
    """Remove a scratch tree, detaching any NTFS junctions first."""
    junction = root / ".millhouse" / "wiki"
    if junction.exists() or junction.is_symlink():
        _junction.remove(junction)
    _safe_rmtree.safe_rmtree(root, allowed_root=root, ignore_errors=True)


def _run_script(script: Path, cwd: Path) -> tuple[int, str, str]:
    """Run a Python script; return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["uv", "run", "--project", str(_PLUGIN_ROOT), str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = _SCRATCH / f"mill-layer02-test-plan-{uuid.uuid4().hex[:8]}"
    tmp.mkdir()
    failed = False
    try:
        # ---------------------------------------------------------------
        # Setup
        # ---------------------------------------------------------------
        millhouse_dir = tmp / ".millhouse"
        wiki_dir = tmp / "wiki-fixture"
        plan_dir = wiki_dir / "active" / "test-slug" / "plan"
        reviews_dir = wiki_dir / "active" / "test-slug" / "reviews"

        millhouse_dir.mkdir()
        plan_dir.mkdir(parents=True)
        reviews_dir.mkdir(parents=True)

        (millhouse_dir / ".test-slug.slug.md").write_text(
            _SLUG_FILE_CONTENT, encoding="utf-8"
        )
        (wiki_dir / "config.yaml").write_text(_CONFIG_YAML, encoding="utf-8")

        # 01-core.md has a "Reads: plugins/mill/scripts/_render.py" directive.
        # The plan backend resolves Reads: paths relative to project_root (cwd).
        # Mirror the real file at $tmp/plugins/mill/scripts/_render.py.
        reads_target = tmp / "plugins" / "mill" / "scripts"
        reads_target.mkdir(parents=True)
        shutil.copy(_SCRIPTS / "_render.py", reads_target / "_render.py")

        shutil.copy(_FIXTURES / "sample-plan" / "00-overview.md", plan_dir / "00-overview.md")
        shutil.copy(_FIXTURES / "sample-plan" / "01-core.md", plan_dir / "01-core.md")

        # Create wiki junction: .millhouse/wiki -> wiki-fixture/
        _junction.create(wiki_dir.resolve(), (millhouse_dir / "wiki").resolve())

        # ---------------------------------------------------------------
        # Test 1: happy path
        # ---------------------------------------------------------------
        print("Test 1: happy path (plan review)...", file=sys.stderr)

        script = _SCRIPTS / "millpy-review-plan.py"
        exit_code, stdout, stderr = _run_script(script, tmp)

        if exit_code != 0:
            print(f"FAIL: millpy-review-plan.py exited {exit_code}")
            print(f"stderr: {stderr}")
            print(f"stdout: {stdout}")
            failed = True
            return 1

        if not stdout.strip():
            print("FAIL: stdout is empty (expected JSON)")
            failed = True
            return 1

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            print(f"FAIL: stdout is not valid JSON: {stdout!r} ({exc})")
            failed = True
            return 1

        if result.get("type") != "plan":
            print(f"FAIL: expected type='plan', got {result.get('type')!r}")
            failed = True
            return 1

        if result.get("verdict") not in ("APPROVE", "REQUEST_CHANGES"):
            print(f"FAIL: unexpected verdict {result.get('verdict')!r}")
            failed = True
            return 1

        reviews = result.get("reviews", [])
        if len(reviews) != 2:
            print(
                f"FAIL: expected reviews length 2 (1 batch + 1 holistic), got {len(reviews)}"
            )
            failed = True
            return 1

        scopes = [r.get("scope") for r in reviews]
        if "01-core" not in scopes:
            print(f"FAIL: no reviews entry with scope='01-core'. Scopes present: {scopes}")
            failed = True
            return 1

        if "holistic" not in scopes:
            print(f"FAIL: no reviews entry with scope='holistic'. Scopes present: {scopes}")
            failed = True
            return 1

        for entry in reviews:
            review_file = Path(entry["file"])
            if not review_file.exists():
                print(
                    f"FAIL: review file does not exist for scope {entry.get('scope')!r}: "
                    f"{review_file}"
                )
                failed = True
                return 1

            # Use production parse_verdict — no duplicate YAML-block parser in tests.
            file_verdict = _review_common.parse_verdict(review_file.read_text(encoding="utf-8"))
            entry_verdict = entry["verdict"]
            if file_verdict != entry_verdict:
                print(
                    f"FAIL: review file for scope {entry.get('scope')!r} "
                    f"verdict={file_verdict!r}, expected {entry_verdict!r}"
                )
                failed = True
                return 1

        print("Test 1 PASS", file=sys.stderr)

        # ---------------------------------------------------------------
        # Test 2: error path — no active task (slug file removed)
        # ---------------------------------------------------------------
        print("Test 2: error path (no active task)...", file=sys.stderr)

        slug_file = millhouse_dir / ".test-slug.slug.md"
        slug_file.unlink()

        exit_code2, stdout2, stderr2 = _run_script(script, tmp)

        if exit_code2 == 0:
            print("FAIL: expected exit 1 when no slug file present, got exit 0")
            failed = True
            return 1

        combined = stdout2 + stderr2
        if "No active task" not in combined:
            print(f"FAIL: expected 'No active task' in output, got: {combined!r}")
            failed = True
            return 1

        print("Test 2 PASS", file=sys.stderr)

    except Exception:
        failed = True
        raise
    finally:
        if failed:
            print(f"Scratch dir preserved for inspection: {tmp}", file=sys.stderr)
        else:
            _remove_tree(tmp)

    print("PASS — all plan review tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\integration_tests\test-review-plan.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\skills\mill-go\SKILL.md ---
---
name: mill-go
description: In a spawned worktree with an approved plan, sequentially execute every batch in the plan's DAG. Per batch spawn one implementer Sonnet, run code review, loop with receive-review on REQUEST_CHANGES, halt on stuck. Hand off to mill-finalize.
---

# mill-go

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are the **Builder** — a lean orchestrator. You coordinate per-batch implementation but never read card bodies or diffs yourself. The **Implementer** (spawned per batch) reads its own batch file, implements cards, runs `verify:`, and fixes on receive-review. You read only `status.md`, the Batch Index DAG in `00-overview.md`, and the fenced yaml verdict block of each code review. Keeping your context lean is the whole point — Builder cost is a rounding error next to the Implementer and code-reviewer calls.

## Entry

**Step 0: Verify `CLAUDE_PLUGIN_ROOT`.**

```bash
[ -n "${CLAUDE_PLUGIN_ROOT}" ] || { echo "[mill-go] HALT: CLAUDE_PLUGIN_ROOT is not set" >&2; exit 1; }
```

**Path variable rule:** All Bash tool calls in this skill use `${CLAUDE_PLUGIN_ROOT}` directly — it is an environment variable already present in the shell. Do NOT read or memorize its value. Write the variable reference; the shell expands it at runtime. The full absolute path must never appear in a command string.

1. Read the task slug: `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
   `signature: _marker.slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str`
2. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())`.
3. Load config — load `mill-config.yaml` from the hub root, merged with `.millhouse/config.local.yaml`, via `_review_common.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path() / ".millhouse")`. Read these keys:
   - `pipeline.auto_merge` — whether to invoke mill-finalize after success.
   - `pipeline.auto_report` — whether to auto-fire mill-self-report at end-of-work. mill-go fires it at Handoff step 6, AFTER any `/mill-merge` invocation in step 5 — including after PR-pending halts. See step 6 for the explicit "do not treat PR-pending as termination" rule.
   - `roles.code-review.batch.rounds` — max review rounds per batch.
   - `roles.code-review.holistic.rounds` — max holistic review rounds (parallel cap for the holistic scope, default 1).
   - `roles.implementer.self_fix_rounds` — passed to the implementer brief.
   - `roles.code-review.holistic.reviewer` — if non-null, run one holistic code review after all batches approve.
   - `roles.code-review.batch.reviewer` — if null (or rounds: 0), skip per-batch code review for all batches.
4. Acquire the builder lock:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
   ```
   On exit code 1: surface the stderr message and halt — a second mill-go will corrupt state.
4.5. **Path Setup.** `worktree_root` is not yet set in prior steps; `slug` is in scope from step 1 and `cfg` was loaded in step 3. Derive:
   ```python
   git_root       = _paths.resolve_git_root()
   container_path = _paths.resolve_container_path(git_root)
   worktree_root  = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)
   status_path   = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
   plan_dir      = _paths.resolve_task_path(worktree_root, cfg['paths']['plan_dir'])
   overview_path = plan_dir / "00-overview.md"
   reviews_dir   = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])
   task_dir      = status_path.parent
   ```
   Use these variables for all subsequent path references. Exception: the cleanliness snapshot path `_mill/.cleanliness-snapshot-<batch_name>.txt` keeps its `_mill/` literal — `millpy-implement.py` writes it unconditionally to `_mill/` and is out of scope.
5. **Entry phase gate.** Before reading `status_path`, guard against the merge-interrupted state where `_mill/status.md` has been removed by mill-merge's cleanup commit but teardown did not complete -- mirrors mill-merge's own Step 5 fallback. Wiki daemon errors are caught explicitly so a daemon outage surfaces a readable message instead of a raw traceback.
   ```python
   if not status_path.exists():
       import sys
       from wiki import _client
       from wiki import WikiStartupError, WikiProtocolError
       import _phase_gate
       try:
           task = _client.get_task(wiki_path, slug)
       except (WikiStartupError, WikiProtocolError) as e:
           print(f"_mill/status.md absent and wiki daemon unavailable: {e} -- inspect manually.", file=sys.stderr)
           raise SystemExit(1)
       print(_phase_gate.absent_status_halt_message(task, slug), file=sys.stderr)
       raise SystemExit(1)
   ```

   Inspect the phase:
   ```python
   status = _status.read_full(status_path)
   phase = status["yaml"]["phase"]
   blocked_reason = status["yaml"].get("blocked_reason")
   ```
   `signature: _status.read_full(status_path: Path) -> {"yaml": dict, "timeline": list[str]}`

   | phase | action |
   | --- | --- |
   | `planned` | fresh run — continue to Prepare |
   | `implementing` / `reviewing` / `fixing` | resume (see *Resume*) |
   | `blocked` | surface `blocked_reason` from status.md and halt |
   | `discussed` / `discussing` / `planning` | tell user to finish mill-plan and halt |
   | `done` | tell user the task is complete; suggest `/mill-finalize` if auto-merge was off |
   | any other | surface + halt |

6. Read the plan overview from `overview_path`. Confirm `approved: true` in the frontmatter. Extract the Batch Index via `_plan_dag.extract_batch_index(overview_text)`, validate via `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`, then compute `order = _plan_dag.topo_order(batches)`.
   `signature: _plan_dag.extract_batch_index(overview_text: str) -> list[dict]`
   `signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`
   `signature: _plan_dag.topo_order(batches: list[dict]) -> list[str]`

> If mill-go is interrupted mid-run, re-run `/mill-go` — it will auto-reclaim the builder lock for the same task (stale-self-lock detection is built in).

## Prepare

On a fresh run only (no `## Batches` section in status.md):

- `_status.init_batches(status_path, order)` — seeds every batch at `state: pending`.
  `signature: _status.init_batches(status_path: Path, names: list[str]) -> None`
- `_status.append_phase(status_path, "implementing", _timestamp.now_utc_iso())`.
  `signature: _status.append_phase(status_path: Path, phase: str, timestamp: str) -> None`
  `signature: _timestamp.now_utc_iso() -> str`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: prepare for {slug}"`.

## Execute — sequential loop

For each batch in `order`:

## Agent-mode dispatch

When `dispatch == agent`, follow this three-step pattern at each dispatch point:

1. **Resolve dispatch mode:** `dispatch = _agent_dispatch.resolve_dispatch_mode(cfg)`. This reads `cfg["llm"]["claude"]["dispatch"]` and returns one of `"subprocess"`, `"psmux"`, or `"agent"`. If the mode is not `agent`, skip this entire section and use the existing `subprocess`/`psmux` flow unchanged (documented below in each dispatch subsection).

2. **Run prepare stage:** Invoke the CLI with `--stage prepare` and the standard arguments (see each subsection for the exact CLI invocation). Parse the returned JSON line to extract:
   - `brief_path`: absolute file path to the rendered brief
   - `subagent_type`: one of `"mill-implementer"` or `"mill-reviewer"`
   - `model`: Agent-tool tier (`"sonnet"`, `"opus"`, or `"haiku"`)

3. **Call Agent tool:** Synchronously invoke the Agent tool with:
   - `subagent_type`: the value from step 2
   - `model`: the value from step 2
   - `prompt`: `"Read this file and follow the instructions exactly: <brief_path>"`
   
   The Agent returns its final message text.

4. **Capture output:** Write the Agent's returned final message to `<brief_path>.out.md` (utf-8). The response file extends the brief path by replacing the trailing `.md` with `.out.md` — for a brief `foo-r1.md` the response is `foo-r1.out.md`.

5. **Run finalize stage:** Invoke the CLI with `--stage finalize`, the same standard arguments, and `--agent-output <brief_path>.out.md`. The response file follows the same naming rule: `.out.md` replaces the trailing `.md` of the brief path. Parse the returned JSON envelope.

6. **Branch on verdict:** Use the JSON envelope to branch identically to the existing `subprocess`/`psmux` flow — the `status`, `verdict`, `stuck_type` handling is identical.

**Agent-mode properties:**
- No log-polling or liveness check required (the Agent tool is synchronous).
- No `infrastructure` stuck path (no detached worker).
- `transient` stuck errors can still be emitted by `finalize` as synthetic JSON (e.g., if the brief write fails).
- The one-retry transient policy still applies.

**Subprocess/psmux poll-loop max-wait.** When `dispatch == subprocess` or `psmux`, all poll loops that wait for `[mill-bg] EXIT` must have a bounded max-wait (~3600s) to self-terminate if the worker dies without writing the exit marker. Exceedance of the max-wait is a fatal `infrastructure` stuck escalation. The explicit timeout guard prevents infinite polling when the worker session is killed (e.g., logout or crash). This applies to implementer, reviewer, and fixer dispatch in all scopes (per-batch and holistic), and to ERROR-only retries. See individual subsections for the loop structure; all follow the same time-bounded poll-until-EXIT pattern.

**Per-batch session cleanup.** Every time the per-batch implementer reports `success` (immediately after step 2 parse, before step 2b cleanliness gate), AND on every loop terminus (APPROVE, max-rounds blocked, cleanliness-blocked, stuck-blocked), AND when the Builder is about to re-dispatch the implementer with a fresh session (transient-retry-once), invoke the *per-batch cleanup block* defined below — it reaps the psmux TUI session associated with the batch's `implementer_session`, idempotent and failure-swallowing. The post-success invocation is the primary cleanup point now that fix dispatch is cold-start; the terminal invocations remain for defence-in-depth and are idempotent no-ops when the session is already gone.

The per-batch cleanup block:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
sys.path.insert(0, r'${CLAUDE_PLUGIN_ROOT}/scripts')
from pathlib import Path
import _paths, _status, _llm_claude
status_path = _paths.resolve_task_path(_paths.resolve_git_root(), '_mill/status.md')
batches = _status.read_batches(status_path)
sid = next((b.get('implementer_session') for b in batches if b['name'] == '<batch_name>'), None)
_llm_claude.cleanup_session(sid)
" || true
```

### 0. Wiki health-check

Before launching the implementer / reviewer for this batch, verify a config source is reachable. If the check fails, release the builder lock and halt — a config source became unavailable mid-run and the implementer's downstream error would mask the root cause.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
import _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
if not _client.health_check(wiki_path):
    print('[mill-go] wiki daemon health check failed', file=sys.stderr)
    raise SystemExit(1)
" || {
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
    echo "[mill-go] HALT: no config source reachable -- re-run mill-setup if mill-config.yaml is missing" >&2
    exit 1
}
```

### 1. Implement

Background via millpy-bg:

> **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

Venv-check before per-batch invocation:

```bash
if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
    echo "[mill-go] venv missing -- attempting uv sync"
    uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
    if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
        echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
        exit 1
    fi
fi
```

If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-implement.py` and `<args> = <batch_name>`.

If `dispatch == subprocess` or `psmux`: background via millpy-bg:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
    --slug implement-<batch_name> -- \
    "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
```

Returns immediately with `pid=<N> log=<abs-path>`. Do not use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check with a bounded max-wait (~3600s):
```bash
start_time=$(date +%s)
max_wait=3600
while true; do
  current_time=$(date +%s)
  elapsed=$((current_time - start_time))
  if [ $elapsed -ge $max_wait ]; then
    echo "[mill-go] HALT: subprocess poll loop timeout (max_wait=$max_wait exceeded) — worker died without writing [mill-bg] EXIT. Escalate to infrastructure stuck." >&2
    exit 1
  fi
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
  # parse JSON result and branch: "running" -> sleep; "exit"/"dead" -> exit loop
done
```
Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> sleep briefly then continue polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. If max-wait is exceeded, halt with infrastructure escalation (worker died without EXIT).

The CLI atomically: resolves paths and config, renders the implementer brief, generates a `session_id`, sets batch state → `running`, records `start_sha` and `implementer_session` in status.md, commits and pushes on the task branch, and spawns the implementer. The Builder reads the JSON summary from the log file. Note: the CLI exits 0 when the implementer produced JSON (success or stuck). On exit code 1 the JSON line in the log file still carries a `{"status":"stuck","stuck_type":"transient",...}` line if an LLM-layer failure (timeout, dead session, etc.) occurred — parse it the same way and route through Stuck escalation. Only treat exit 1 as an unrecoverable pre-launch error when the JSON line in the log file is absent.

### 2. Parse implementer report

The implementer's last output line must be JSON:

```json
{"status":"success|stuck","commit_sha":"...","session_id":"...", ...}
```

- `status: success` → continue to Code Review.
- `status: stuck, stuck_type: transient` → auto-retry ONCE: invoke the per-batch cleanup block, then re-invoke `millpy-implement.py <batch_name>` (no `--resume` flag — a fresh batch start). Record `review_round: 0`, do not change batch state. If the second invocation also reports `stuck_type: transient` → escalate per *Stuck escalation* below.
- `status: stuck, stuck_type: verify | logic` → **ask user** per *Stuck escalation*.
- Malformed / missing JSON line → treat as `stuck_type: logic` reason "no structured report".

### 2b. Cleanliness gate

After a `success` report: compute new dirt via `_cleanliness.compute_new_dirt(<worktree>, <worktree>/_mill/.cleanliness-snapshot-<batch_name>.txt)`. If the returned list is non-empty (genuine implementer-introduced dirt that did not pre-date the batch):
- `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
- `_status.set_batch_field(status_path, batch_name, "blocked_reason", "uncommitted working tree after implementer report")`
- `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on <batch_name> — dirty tree"`
- Invoke the per-batch cleanup block.
- Go to *Blocked*.

`signature: _cleanliness.compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]`

If the returned list is empty, invoke the per-batch cleanup block (after a `success` report, before the cleanliness gate at step 2b) — the cold-start fixer used in step 4 REQUEST_CHANGES does not need the warm session. Record `commit_sha` via `_status.set_batch_field(status_path, batch_name, "commit_sha", <sha from JSON report>)`. Then continue to "3. Code Review loop" as normal.

### 3. Code Review loop

If `roles.code-review.batch.reviewer` is null (or rounds: 0): set batch state → `approved`, `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: approve batch {batch_name} (per-batch review disabled)"`, and continue to the next batch. Skip the rest of this section.

- Set batch state → `reviewing`, `review_round: 1`.
- `extra_files = []`.

For each round `N` from 1 to `roles.code-review.batch.rounds`:

- `_status.append_phase(status_path, f"reviewing-{batch_name}-r{N}", _timestamp.now_utc_iso())`.

1. **Crash-recovery check.** Before firing the CLI, scan `reviews_dir` for a file matching `*-code-review-{batch_name}-r{N}.md`. If found, validate its freshness: fetch `ref_ts = _status.phase_entry_timestamp(status_path, f"reviewing-{batch_name}-r{N}", occurrence=1)`; treat the file as this round's review ONLY if `ref_ts` is not None AND the file's mtime (UTC) is at or after `ref_ts`. If freshness validation passes, parse its verdict from the fenced yaml block via `_review_common.parse_verdict(file_content)` and skip to step 4 below. This covers the case where mill-go crashed after writing the review but before committing state. If the file is stale (mtime before `ref_ts`) or `ref_ts` is None, ignore the file and fall through to firing the CLI.

   Freshness validation in inline Python:
   ```python
   from datetime import datetime, timezone
   from pathlib import Path
   ref_ts_str = "<iso-timestamp-string>"  # result from phase_entry_timestamp
   file_path = Path("<review-file-path>")
   ref_ts = datetime.fromisoformat(ref_ts_str.strip('"')).replace(tzinfo=timezone.utc) if ref_ts_str else None
   file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
   is_fresh = ref_ts is not None and file_mtime >= ref_ts
   ```

   State explicitly: ERROR-only retries still do NOT consume the round counter; freshness — not counter consumption — is what rejects stale pre-retry files.
   `signature: _review_common.parse_verdict(text: str) -> str`
   `signature: _status.phase_entry_timestamp(status_path: Path, phase: str, *, occurrence: int = 1) -> str | None`

2. If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name> [--extra-file <p> ...]`.

   If `dispatch == subprocess` or `psmux`: background via `millpy-bg`:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-<batch_name>-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
           --batch <batch_name> [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Do **not** use `run_in_background: true`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears with a bounded max-wait (~3600s), but on each iteration also run a liveness check:
   ```bash
   start_time=$(date +%s)
   max_wait=3600
   while true; do
     current_time=$(date +%s)
     elapsed=$((current_time - start_time))
     if [ $elapsed -ge $max_wait ]; then
       echo "[mill-go] HALT: code-review poll loop timeout (max_wait=$max_wait exceeded) — worker died without writing [mill-bg] EXIT. Escalate to infrastructure stuck." >&2
       exit 1
     fi
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
     # parse JSON result and branch: "running" -> sleep; "exit"/"dead" -> exit loop
   done
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> sleep briefly then continue polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. If max-wait is exceeded, halt with infrastructure escalation. The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.

3. **Builder reads only the JSON envelope verdict, never the findings.** Loading `mill-receiving-review` is the dispatched implementer's job (see Principles below). Builder does not load the skill.

4. Branch on verdict:
   - `APPROVE` — If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:
   
     If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>`.
     
     If `dispatch == subprocess` or `psmux`: via `millpy-bg`:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<N>-nits -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>
     ```
     Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
     ```
     Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. The fixer loads `mill-receiving-review` and applies the NITs from the APPROVE'd review file. Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior. Do NOT re-review — the NIT fix is trusted. The NIT-fix session commits its own source-file changes atomically; on stuck → escalate via the existing Stuck escalation path. After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): set batch state → `approved`, `review_file: <path>`. `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`. Use the `file` field from `reviews[0]` in the JSON summary (or the crash-recovery scan path) as `<review_file_path>`. Commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"`. Invoke the per-batch cleanup block. Break out of the loop → next batch.
   - `NEED_CONTEXT` — read the `## Missing context` bullets from the review file. For each listed path, if it exists under the worktree, append to `extra_files` for the NEXT round. `_notify.notify("mill-go.review-need-context", f"batch {batch_name} round {N}", slug=slug, files=len(missing))`. Record this gap for mill-self-report (see Handoff). Increment round and continue the loop. If ALL the missing files are paths already in `extra_files` from a prior round (no new info), treat as a stuck-logic failure and break. Reading the structured `## Missing context` bullet list does not require `mill-receiving-review` -- only finding-handling does.
     `signature: _notify.notify(event: str, detail: str, **context) -> None`
   - `REQUEST_CHANGES` — If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>`.

     If `dispatch == subprocess` or `psmux`: background via millpy-bg:

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<N> -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>
     ```
     Returns immediately with `pid=<N> log=<abs-path>`. Do not use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
     ```
     Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

     The CLI atomically: resolves the batch plan, sets batch state → `fixing`, calls `_status.append_phase` for `fixing-{batch_name}-r{N}`, commits and pushes (status.md plus the review file), and dispatches a cold-start fixer session with the fix prompt (which instructs the fixer to load `mill-receiving-review` and apply findings). Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior described under "1. Implement". On stuck → escalate.

4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from sub-step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip sub-step 4 entirely and immediately re-run:

   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name> [--extra-file <p> ...]`.

   If `dispatch == subprocess` or `psmux`:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-<batch_name>-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
           --batch <batch_name> [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter `N` is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: code review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors mill-plan's existing step 4.5. *(Closes #228 — rate-limit errors no longer mis-dispatch the implementer with a null review file.)*

5. **Max-rounds exhaustion.** After `roles.code-review.batch.rounds` rounds without APPROVE: `_notify.notify("mill-go.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} after {N} rounds"`. Invoke the per-batch cleanup block. Go to *Blocked* below.

### Stuck escalation

If the deep-merged config has `pipeline.autonomous_mode: true`: for any `stuck_type` (`transient` already-retried, `verify`, `logic`, `infrastructure`): skip the user prompt; auto-handle according to the stuck_type rules below. **For `infrastructure` only**, skip straight to the autonomous-mode handling. For all others, set batch state → `blocked`, `blocked_reason: "autonomous-mode stuck: {stuck_type}"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} (autonomous-mode)"` and push; invoke the per-batch cleanup block; go to *Blocked*.

- **`infrastructure`** (bg worker died, likely logout) — **interactive** mode: surface to user with options `1) Re-fire fresh (Recommended)` / `2) Block`; user picks. On re-fire: invoke the per-batch cleanup block, then re-invoke `millpy-bg` with a fresh CLI (no `--resume` flag — the killed session is dead). If the re-fire also reports `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. **`autonomous_mode: true`**: auto-retry ONCE with a fresh re-fire (no `--resume`). If the re-fire also fails with `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. State explicitly that the re-fire matches the existing `running`-state Resume (fresh start; killed session cannot be reattached).
- **CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2; the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session). If the second invocation also reports `stuck_type: transient`, escalate per the routing below.
- `transient` (already retried once):
  - **If `commits_made > 0` in the stuck JSON** (the implementer timed out after committing some work):
    - Interactive mode: present options:
      1) Skip to cleanliness gate (Recommended) — commits were made before the timeout; proceed directly to the cleanliness gate then code review
      2) Retry from scratch — re-fire the implementer as a fresh batch start
    - On option 1: skip re-invocation of the implementer; proceed to the per-batch cleanliness gate (scope violations check) then code review as if the implementer had reported success.
    - `autonomous_mode: true`: auto-pick option 1 (skip to cleanliness gate).
    - If `commits_made == 0` or the field is absent: use the existing three-option path below.
  - **Otherwise** (no commits made or timeout before any commit) → surface to user with three options: retry fresh, edit plan and retry, block. User picks.
- `verify` / `logic` → surface to user with three options: edit plan to clarify then retry fresh, skip this batch (block the task), block the task. User picks.
- On user-chosen block: set batch state → `blocked`, `blocked_reason: <reason>`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`. Invoke the per-batch cleanup block. Go to *Blocked*.

### Blocked

- `_notify.notify("mill-go.blocked", f"batch {batch_name}: {blocked_reason}", slug=slug, batch=batch_name)`.
- Release the builder lock:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
  ```
- Tell the user: "Batch X blocked with reason Y. Inspect reviews/ and status.md. Re-run `/mill-go` after resolving, or `/mill-abandon` to wind down." Do not proceed to Handoff.

## Resume

When mill-go's Entry-step 5 phase gate routes here (phase is `implementing`, `reviewing`, or `fixing`), the previous run was interrupted mid-batch. The CLIs that mutate task state (`millpy-implement.py`, `millpy-review-code.py`) are atomic — they record state-mutation commits before the heavy work starts and after each transition — so the resume playbook is simple: read the current batch entry and re-invoke the CLI for the current state.

1. Read `_mill/status.md`; locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
2. Branch on the batch's `state`:
   - **`running`** — the implementer was mid-implementation. Re-invoke:

     If `dispatch == agent`: in agent mode the SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state. The prepare-stage pre-commit makes this idempotent; the brief at `_mill/briefs/<role>-<scope>-r<round>.md` is reused/re-rendered. Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-implement.py` and `<args> = <batch_name>`.

     If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug implement-<batch_name>-resume -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
     ```
     The interrupted implementer session is dead and cannot be re-attached. A fresh batch start is the correct recovery: the CLI re-initialises state -> running, captures a new snapshot, and spawns a fresh implementer session. After parsing the report, continue at Execute step 2b (cleanliness gate).
   - **`reviewing`** — the implementer report was already consumed; the reviewer was running. Re-invoke the per-batch code-review CLI from the start of round `review_round` (read this field from the batch entry):

     If `dispatch == agent`: in agent mode the SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state. Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name>`.

     If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug review-code-<batch_name>-r<review_round>-resume -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" --batch <batch_name>
     ```
     The CLI's crash-recovery scan handles a written-but-uncommitted review file. After parsing the JSON verdict, continue at Execute step 3 sub-step 3 (load `mill-receiving-review`) and step 4 (branch on verdict).
   - **`fixing`** — the reviewer returned `REQUEST_CHANGES`; the fix-implementer was running. Re-invoke:

     If `dispatch == agent`: in agent mode the SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state. Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <review_round>`.

     If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<review_round>-resume -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <review_round>
     ```
     The `<review-file-abs-path>` is the most recent `_mill/reviews/*-code-review-<batch_name>-r<review_round>.md` file. After parsing the report, continue at Execute step 3 sub-step 5 (max-rounds check) or back to step 3 round N+1 if the fix produced an APPROVE-eligible state on next review.
3. **No state mutation before resume.** Do NOT pre-emptively flip `state` or call `_status.append_phase` before re-invoking the CLI. The CLI handles state transitions atomically; double-writes corrupt the timeline.
4. **`mill-receiving-review` remains the fixer's responsibility.** When resume re-dispatches the fixer (`millpy-fix.py --scope batch ...`), the fix-prompt itself instructs the fixer to load the skill before reading findings. Builder still does not load it.

## Holistic code review

**Holistic session cleanup.** Whenever a `millpy-fix.py --scope holistic` invocation completes (success, stuck, or any error path), capture the `session_id` field from the parsed JSON envelope into a local Bash variable `holistic_sid`. At any point where the holistic loop is about to dispatch a NEW `millpy-fix.py --scope holistic` round, AND at every loop terminus (APPROVE, autonomous-mode block, user-block, max-rounds), invoke the *holistic cleanup block* defined below.

The holistic cleanup block:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
sys.path.insert(0, r'${CLAUDE_PLUGIN_ROOT}/scripts')
import _llm_claude
_llm_claude.cleanup_session('${holistic_sid}')
" || true
```

If the captured `holistic_sid` is empty or the literal `unknown`, cleanup is a documented no-op — the implementer brief contract guarantees the id is emitted on the happy path.

**Guard:** The skip semantics have two conditions: `reviewer: null` OR `rounds: 0` means "skip holistic". Only execute this section if `cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("reviewer") is not None`.

`max_holistic_rounds = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("rounds", 1)`. Loop variable `H` starts at 1. `extra_files = []`.

For each round `H` from 1 to `max_holistic_rounds`:

0. Wiki health-check

   Before launching the implementer / reviewer for this batch, verify a config source is reachable. If the check fails, release the builder lock and halt — a config source became unavailable mid-run and the implementer's downstream error would mask the root cause.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import sys
   import _paths
   from wiki import _client
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   if not _client.health_check(wiki_path):
       print('[mill-go] wiki daemon health check failed', file=sys.stderr)
       raise SystemExit(1)
   " || {
       PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
       echo "[mill-go] HALT: no config source reachable -- re-run mill-setup if mill-config.yaml is missing" >&2
       exit 1
   }
   ```

1. **Crash-recovery.** Three-way branch based on what is on disk in `_mill/reviews/` and `.scratch/`:
   - **(a) Review file present.** Scan `reviews/` for a file matching `*-code-review-r{H}.md` (holistic code review files have format `{ts}-code-review-r{N}.md` -- no batch-name segment, no `-holistic-` substring; per-batch files embed `{batch_name}` so the glob never collides). If found, validate its freshness: fetch `ref_ts = _status.phase_entry_timestamp(status_path, "holistic-reviewing", occurrence=H)` (the Hth occurrence corresponds to round H); treat the file as this round's review ONLY if `ref_ts` is not None AND the file's mtime (UTC) is at or after `ref_ts`. If freshness validation passes, skip the CLI and use that file's verdict directly. Proceed to step 4 (verdict branch); do NOT execute step 2 (the phase entry was already appended on the original run) and do NOT execute step 3. If the file is stale or `ref_ts` is None, fall through to branch (b)/(c) handling (fire the CLI). Provide the inline-Python comparison snippet as per the per-batch section above.
   - **(b) No review file, no bg log for round H.** Proceed normally to step 2 (append `holistic-reviewing` phase) and step 3 (fire CLI via `millpy-bg`).
   - **(c) No review file, bg log exists for round H** (matching glob `.scratch/bg-*-review-code-holistic-r{H}.log`). Pick the most recent matching file and call `_bg.is_bg_worker_alive(log_path)`:
      - **Alive** -> poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
        ```bash
        PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
        ```
        Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed to step 4 (parse JSON, branch on verdict); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. Do NOT execute step 2; do NOT execute step 3.
      - **Dead** -> log `[mill-go] previous holistic round H bg worker died (pid=N); re-firing CLI` to stderr, then jump directly to step 3 (fire fresh CLI via `millpy-bg`). Do NOT execute step 2 (the phase entry was already appended on the original run).

   Inline Python helper for branches (a) and (c):

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from pathlib import Path
   import _paths, _bg, json, sys
   git_root = _paths.resolve_git_root()
   reviews_dir = git_root / '_mill/reviews'
   scratch_dir = git_root / '.scratch'
   H = ${H}
   # (a) review file scan
   matches = sorted(reviews_dir.glob(f'*-code-review-r{H}.md')) if reviews_dir.exists() else []
   if matches:
       print(json.dumps({'branch': 'a', 'review_file': str(matches[-1])}))
       sys.exit(0)
   # (c) bg log liveness probe
   bg_logs = sorted(scratch_dir.glob(f'bg-*-review-code-holistic-r{H}.log')) if scratch_dir.exists() else []
   if bg_logs:
       alive, pid = _bg.is_bg_worker_alive(bg_logs[-1])
       print(json.dumps({'branch': 'c', 'log_path': str(bg_logs[-1]), 'alive': alive, 'pid': pid}))
       sys.exit(0)
   # (b) nothing on disk
   print(json.dumps({'branch': 'b'}))
   "
   ```

   Parse the JSON line. Branch dispatch is exactly as enumerated above. The helper is one-shot; do not poll it.

2. **Skip this step when step 1 returned branch (a) or any sub-branch of (c).** `_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())`. Commit: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: holistic reviewing round {H}"`.

3. If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = [--extra-file <p> ...]` (no `--batch` flag for holistic scope). Include any accumulated `extra_files` from prior `NEED_CONTEXT` rounds via `--extra-file <p>` (one flag per path).

   If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   Venv-check before holistic review invocation:

   ```bash
   if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
       echo "[mill-go] venv missing -- attempting uv sync"
       uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
       if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
           echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
           exit 1
       fi
   fi
   ```

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
     --slug review-code-holistic-r{H} -- \
     "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
       [--extra-file <p> ...]
   ```
   Include any accumulated `extra_files` from prior `NEED_CONTEXT` rounds via `--extra-file <p>` (one flag per path). Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   **Exit handling.** If `[mill-bg] EXIT` reports a non-zero exit AND no JSON summary line is present in the log, halt with "BLOCKED: holistic review pre-launch failure" and surface the last stderr line from the log to the user. If a JSON envelope IS present (even with `verdict: ERROR`), drop through to sub-step 3.5 ERROR-only retry as normal. Matches the per-batch section's "only treat exit 1 as unrecoverable when JSON line is absent" branch.

3.5. **Step 3.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 3 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4 and 5 entirely and immediately re-run:

   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = [--extra-file <p> ...]`.

   If `dispatch == subprocess` or `psmux`:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
     --slug review-code-holistic-retry-r<H> -- \
     "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
       [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter `H` is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, **first check rate-limit fallback** (see sub-step 3.6 below). If sub-step 3.6 does NOT apply, halt with `BLOCKED: holistic code review ERROR-only round {H}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass.

3.6. **Rate-limit fallback (no round consumed)**

   When sub-step 3.5's second pass returns `verdict: ERROR` AND `roles.code-review.holistic.fallback_reviewer` is not null AND any `reviews[*].error` string contains (case-insensitive) a substring listed in `roles.code-review.holistic.fallback_on` (default `["rate-limit"]`):

   1. Emit `_notify.notify("mill-go.holistic-fallback", f"swap reviewer -> {fallback_name}", slug=slug, round=H)`.
   2. In-memory mutation: `cfg["roles"]["code-review"]["holistic"]["reviewer"] = cfg["roles"]["code-review"]["holistic"]["fallback_reviewer"]`. Do NOT write back to disk -- the swap lasts only for the current mill-go invocation.
   3. Re-run sub-step 3 (the holistic review CLI) with the swapped reviewer. The round counter `H` is **not** consumed.
   4. If the fallback reviewer ALSO returns `verdict: ERROR` on its first pass: halt with `BLOCKED: holistic code review fallback also failed at round {H}` and surface every `reviews[*].error` from BOTH the original and fallback attempts. Do NOT cascade to a second fallback.
   5. If `pipeline.autonomous_mode: true` AND `fallback_reviewer is None` AND a rate-limit was detected on both 3.5 passes: halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured`. The operator-visible message is intentional -- silent infinite fallback is wrong.

   Operator interactive path (no `autonomous_mode`, no `fallback_reviewer`): user prompt remains identical to today (the existing step 5 ROUND-EXHAUSTION sub-section handles this case).

4. On `APPROVE`: If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:
   
   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <review-file-abs-path> --round {H}`.
   
   If `dispatch == subprocess` or `psmux` (via `millpy-bg`):
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug fix-holistic-r{H}-nits -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope holistic --review-file <review-file-abs-path> --round {H}
   ```
   Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. The fixer loads `mill-receiving-review` and applies the NITs. Do NOT re-review — the NIT fix is trusted. On stuck → escalate via the existing Stuck escalation path. After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): `_status.append_phase(status_path, "holistic-approved", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: holistic approve {slug}"`, where `<review_file_path>` is the `file` field from `reviews[0]` of the JSON envelope (or the crash-recovery branch (a) scan path). This mirrors the per-batch APPROVE branch, which already stages its review file. If a NIT-fix pass ran for the holistic scope this round, the fixer already committed its own changes; this commit still stages the review file plus the `holistic-approved` status row. Invoke the holistic cleanup block. Proceed to Handoff.

5. On `REQUEST_CHANGES`: the holistic-fix CLI dispatches a fresh fixer; the fixer loads `mill-receiving-review` (see Principles below). Builder does not load the skill. Invoke the holistic cleanup block (reaps the previous round's session before the next one starts). 
   
   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <abs-path-to-holistic-review-file> --round {H}`.
   
   If `dispatch == subprocess` or `psmux`: Dispatch:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope holistic --review-file <abs-path-to-holistic-review-file> --round {H}
   ```
   Parse stdout JSON (same last-`{"status":...}`-line pattern as per-batch). The CLI handles `holistic-fixing` phase + commit + push itself.
   - `stuck_type: infrastructure`: **interactive** mode — surface with options `1) Re-fire fresh (Recommended)` / `2) Skip holistic / 3) Block task`; user picks. On re-fire: invoke the holistic cleanup block, then re-invoke `millpy-fix.py --scope holistic` once (fresh). If the re-fire also fails with `infrastructure`: present user with same three options. **`autonomous_mode: true`** — auto-retry ONCE with a fresh re-fire. If the re-fire also fails: invoke the holistic cleanup block, set batch state -> `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. State that the re-fire is fresh (killed session cannot be reattached).
   - `stuck_type: transient`: one-retry policy (re-invoke once). If still transient: surface to user — retry fresh / skip holistic / block task. On user-chosen block: invoke the holistic cleanup block, then go to *Blocked*.
   - `stuck_type: verify` or `logic`: surface to user — edit plan and retry / skip holistic and proceed to Handoff / block task. On user-chosen block: invoke the holistic cleanup block, then go to *Blocked*.
   - On success: increment H and loop.

6. On `NEED_CONTEXT`: apply the same extra-files / notify path as per-batch.

7. **Rounds exhausted** (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned): If the deep-merged config has `pipeline.autonomous_mode: true`: `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; `_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s) (autonomous-mode)")`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (autonomous-mode)"` and push; invoke the holistic cleanup block; halt with "Autonomous mode: holistic review exhausted. Task left as [active]." Otherwise surface to user with a **blocked-task halt** (not blocked-batch):
   > Holistic review exhausted {max_holistic_rounds} round(s). Task is blocked.
   > 1) Rethink — revise discussion and re-run mill-plan.
   > 2) Skip holistic — accept remaining findings and proceed to Handoff.
   > 3) Block — halt and leave for manual resolution.
   On user choice of "3) Block": invoke the holistic cleanup block, then halt and leave for manual resolution. Wait for user choice before proceeding.

## Handoff

**Terminal cleanliness gate.** Run `git -C <worktree> status --porcelain --untracked-files=no`. If the output is non-empty (any tracked files have uncommitted modifications), halt with:
`BLOCKED: dirty working tree at task completion -- <N> file(s) uncommitted: <file-list>. Commit or discard before proceeding.`
where `<N>` is the count of dirty lines and `<file-list>` is the filenames extracted from the porcelain output. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and fix.

If the output is empty, proceed normally.

1. `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: done {slug}"`.

2. Flip Home.md's task line to `[ready-to-merge]` — the new intermediate state signalling 'mill-go done, mill-merge pending':
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from pathlib import Path; import _paths
   from wiki import _client
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   _client.set_phase(wiki_path, '<slug>', 'ready-to-merge')
   "
   ```
3. `_notify.notify("mill-go.done", f"task {slug} complete", slug=slug)`.
4. **Release the builder lock immediately:**
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
   ```
5. If `pipeline.auto_merge: true` → invoke `/mill-finalize`. Otherwise tell the user: "Task complete. Run `/mill-finalize` to finalize the task (creates a PR or squashes directly, depending on config)." mill-finalize may halt on `pr-pending` in PR mode — that is expected; treat it as completion of step 5 and continue to step 6.
6. If `pipeline.auto_report: true` → invoke `/mill-self-report --auto`. **Always fires** at the end of Handoff, including after a `pr-pending` halt in step 5 — do NOT treat the PR-pending message as task termination. The skill checks `gh auth` itself and bails cleanly if absent. Cross-thread merges and post-PR teardowns are not auto-reflected; user can run `/mill-self-report` manually if wanted.

## Principles

- **Lean Builder.** You never read card bodies, diffs, or source files unless responding to a stuck-logic event on a specific batch. Your context stays small by design — this is what lets Opus be a legitimate Builder choice.
- **Implementer owns receive-review.** On `REQUEST_CHANGES` the implementer (not Builder) loads `mill-receiving-review` and applies findings. Builder passes a pointer to the review file; the implementer's warm session already knows the code.
- **Commits go through `git-commit`.** `implementer-brief.md` already instructs this, but enforce it if the implementer asks for confirmation: every per-card commit invokes the `git-commit` skill so lint + `codeguide-update` run per-commit. Batch N+1's implementer then reads a codeguide that already reflects batch N's additions.
- **One task per worktree.** The builder lock enforces this at runtime. Do not attempt to relax it.
- **Never guess when stuck.** Surface to the user with concrete options; don't invent a recovery.
- **Review files are the ground truth.** Verdict parsing reads only the fenced yaml block; the `## Findings` body is the implementer's job to read, not yours.
- **Helper signatures are documented inline.** Every helper this skill names has an explicit one-line signature in the section that calls it. Never Read or Grep the helper source — the signature is here, and any failure surfaces as an exception. (See `mill:workflow` for the project-wide rule.)
- **TodoWrite items name batches by number.** Emit todo items as `Implement batch N (<batch-slug>)` — e.g. `Implement batch 1 (foundations)` — so progress in the todo list correlates 1:1 with plan files (`NN-<batch-slug>.md`). Bare names without a number force the operator to cross-reference the Batch Index every time.

## Board discipline

- `status_path`, `reviews_dir/<file>`, and `plan_dir/<file>` writes are committed on the **task branch** via `git -C <worktree> add ... && git -C <worktree> commit`. `millpy-implement.py` and `millpy-fix.py` push their own task-branch state commits (batch-start, batch-fix, holistic-fix) to `origin/<task-branch>` immediately after each `git commit`. The Builder's own state commits (Prepare, Approve, blocked, done) and per-card implementer commits do not push — mill-merge pushes the full task branch at task end. Adding push to the Builder's own commits is a follow-up task; this PR scopes the push policy to CLI commits only.
- Wiki phase mutations (the Handoff `[ready-to-merge]` flip) go through `_client.set_phase(wiki_path, slug, "ready-to-merge")`. The daemon serializes all writes and pushes automatically.
- Phase transitions via `_status.append_phase`; batch-state mutations via `_status.set_batch_field`. Hand-editing either yaml block is banned.
- The path-invariant rule from CLAUDE.md is load-bearing: working state never goes to the wiki — only Home.md / _Sidebar.md do.

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\skills\mill-go\SKILL.md ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\skills\mill-plan\SKILL.md ---
---
name: mill-plan
description: In a spawned worktree with a committed discussion.md, autonomously write a batch-based implementation plan, self-review it via mill-review-plan, and hand off to mill-go.
---

# mill-plan

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are an autonomous planner running on Opus. Your job is to turn `discussion.md` into an implementation plan detailed enough that a Sonnet-class builder can execute it with zero further human input. Never pause mid-phase to ask the user. Only the max-rounds escape (below) is allowed to break that rule.

## Entry

1. Resolve the wiki path via `_paths.resolve_wiki_path(_paths.resolve_git_root())`.
   `signature: _paths.resolve_git_root(start: Path | None = None) -> Path`
   `signature: _paths.resolve_wiki_path(git_toplevel: Path) -> Path`
2. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
3. Load config — deep-merge `<hub_root>/mill-config.yaml` with `.millhouse/config.local.yaml`. Read `roles.plan-review.holistic.rounds` as `max_review_rounds`.
   `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict`

**Path Setup.** Derive from config: `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`. `plan_dir` and `reviews_dir` will be derived during Phase: Plan (writes) or Phase: Plan Review (reads) as appropriate — see those phases for details.

4. Read `status_path` and inspect `phase:` + the plan state on disk (no `plan_dir` dir at worktree root, using `cfg['paths']['plan_dir']`). Decide entry branch:

   | state | action |
   | --- | --- |
   | `phase: discussed`, no `plan_dir` dir at worktree root | Phase: Plan (fresh write) |
   | `phase: planning`/`plan-review-*`/`plan-fix-*`, `plan_dir/00-overview.md` exists, `approved: false` | Phase: Plan Review (re-enter loop; do NOT rewrite plan files) |
   | `approved: true` in overview frontmatter | Tell user: "plan already approved, run `/mill-go`". Halt. |
   | any other phase (`discussing`, `planned`, …) | Tell user what phase is set and which skill should run instead. Halt. |

## Phases

Report the current phase to the user at each transition.

### Phase: Plan

Read `_mill/discussion.md` in full. Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`). Then **think the plan through end-to-end before writing any file** — you are Opus and this is exactly where the planning budget pays off.

**Batch sizing.** A batch is a *smart unit*: code that logically belongs together and that a Sonnet builder with a 200k-token context window can hold in its head while implementing. Split on natural module/subsystem boundaries, not on file count. If a proposed batch would force Sonnet to load the entire codebase to understand its own `Context:` list, split it. If two adjacent batches share >80% of their `Context:`, merge them. The planner must keep each batch within `pipeline.max_cards_per_batch` (default 10) cards and within the `pipeline.max_batch_context_tokens` (default 120000) context estimate (sum of each card's `Context:` + `Edits:` + `Creates:` file bytes / 4); the `batch-oversized` validator enforces this at step 1.5, so split proactively.

**Write the files.**

**YAML-quoted tokens for fenced blocks.** Tokens destined for YAML blocks must be pre-quoted; heading tokens remain raw. Heading tokens (`<TASK_TITLE>`, `<BATCH_NAME>`) substitute directly into H1 lines (raw form). YAML-block tokens (`<TASK_TITLE_YAML>`, `<BATCH_NAME_YAML>`) substitute into fenced yaml blocks (quoted form via `_yaml_writer.quote_scalar`). This separation lets templates use both forms without repeating quote logic. Concretely:

```python
from _yaml_writer import quote_scalar
tokens = {
    "TASK_TITLE":      task_title,
    "TASK_TITLE_YAML": quote_scalar(task_title),
    "SLUG":            quote_scalar(slug),
    "STARTED":         quote_scalar(_timestamp.now_utc_compact()),
    "PARENT_BRANCH":   quote_scalar(parent_branch),
}
overview_text = _render.render(template_path, tokens)
```

Apply the same pattern when rendering `plan-batch.md` for each batch:

```python
tokens["BATCH_NAME"]      = batch_name
tokens["BATCH_NAME_YAML"] = quote_scalar(batch_name)
tokens["BATCH_SLUG"]      = batch_slug
```

1. Render `plugins/mill/templates/plan-overview.md` into `<plan_dir>/00-overview.md` using the pre-quoted tokens dict.
2. Fill the Batch Index DAG, Shared Decisions, and All Files Touched sections in place. Set `number:` for each entry to the NN integer from the batch filename. Write `depends-on:` as a list of integers (e.g., `depends-on: [1]` meaning this batch depends on batch number 1). Leave `depends-on: []` for root batches.
3. For each batch, render `plugins/mill/templates/plan-batch.md` into `<plan_dir>/NN-<batch-slug>.md` using the pre-quoted tokens dict. Fill Batch Scope + Cards + Batch Tests. Set `number: NN` in the rendered frontmatter to the batch's integer (same as the filename prefix).

**Card numbering is global across batches**: card 1 lives in batch 01, card 7 might live in batch 02, etc. Never restart at 1 inside each batch — the reviewer and implementer cite cards by number and need uniqueness.

**Verify command shape.** For Python/mill projects: every non-null `verify:` in a per-batch file's frontmatter MUST start with the literal token `PYTHONPATH=` followed by a single space and then the command. The empty value on the same line scopes the `PYTHONPATH` reset to that one command, so the test subprocess does not inherit the mill cache scripts dir from the parent shell and tests load worktree modules instead of stale cache modules. For non-Python projects (e.g. Go, C#): use the native test runner directly without the prefix (e.g. `verify: go test ./...` or `verify: dotnet test`). The validator check `verify-not-isolated` enforces this conditionally based on project language; see the Step 1.5 fix table.

**Verify command scope.** `verify:` runs after every implementer round and every fixer round — many times per batch. Target only the tests affected by this batch's `Edits:` + `Creates:` — DO NOT use `run-all.py` without `--only` for a focused batch (the full 77-file suite is multiple minutes). Patterns (Python projects):
- **Single test file:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-fold.py`
- **Multiple files:** `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-fold.py test-marker.py` — `run-all.py --only <basenames...>` runs only the named files (unknown names error out).

A batch that legitimately touches a cross-cutting helper that every test imports MAY use the unbounded `run-all.py` — but state the justification in `## Batch Tests` so the plan reviewer can validate the scope choice. The default expectation is per-batch scoping.

**Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`. Any `PlanDAGError` → fix the plan files, then re-validate. Do not commit a plan that fails this check.

`signature: _status.read(status_path: Path) -> dict`

**Update `_mill/status.md`.**

- `plan_dir = worktree_root / cfg['paths']['plan_dir']` (config-canonical; write path).
- `_status.update_field(status_path, "plan", cfg['paths']['plan_dir'].rstrip('/'))` — pointer to the plan dir (worktree-relative).
- `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())`.

**Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git commit -m "mill-plan: write plan for {slug}"`.

### Phase: Plan Review

**Path Setup (Plan Review).** Derive: `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])`. Use this variable for all review file path references in this phase.

The new schema has two skip conditions: `rounds: 0` OR `reviewer: null` means "skip plan review". If `roles.plan-review.holistic.rounds == 0` OR `roles.plan-review.holistic.reviewer` is `None`: set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git commit -m "mill-plan: skip plan review (reviewer null or rounds 0) for {slug}"`), push, and proceed straight to Handoff. The skip is recorded in commit history; no `status.md` phase flip beyond the existing Handoff `planned` row.

Loop up to `max_review_rounds` rounds. Each round:

1. Report: **"Plan Review — round N/max_review_rounds"**.

1.5. **Step 1.5: pre-review validator gate (auto-run, no round consumed)**

   - The CLI auto-runs `_plan_validate` before invoking the LLM. If the validator finds anything, the CLI exits 1 with a JSON envelope on stdout (`{"errors": [...], "summary": "<n> finding(s) across <m> batch(es)"}`). No review file is written; no LLM token is spent; no review round is consumed.
   - On validator-failure exit, mill-plan parses the JSON and applies one mechanical fix per error dict, per the mapping table below. After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then run `grep '^{' <log-path> | tail -1` to extract the JSON line.
   - **Two-pass cap:** if the validator fails again on the second pass, mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user. Do NOT auto-retry beyond the second pass. The two-pass cap matches the `roles.implementer.self_fix_rounds` self-fix pattern.
   - If `pipeline.skip_validate: true` ever appears in config (currently it does not; this is a future hook), pass `--skip-validate` to the CLI and skip step 1.5 entirely. mill-plan passes `--skip-check wiki-config-mutation` only when the fix table instructs it — see the `wiki-config-mutation` row.

   | check                          | mechanical fix                                                                                                  |
   | ------------------------------ | ----------------------------------------------------------------------------------------------------------- |
   | non-existent-path              | If the path is a typo of an existing file, correct it. If it is meant to be a Creates: target in this plan, move it from Context:/Edits: to Creates: in the appropriate card. If neither applies, the planner intended to read a file that does not exist — halt; this is not mechanically fixable. |
   | card-missing-field             | Add the missing field with a sensible default: Context: → list the file(s) the requirement names; Edits: → none if the card creates a new file only; Creates: → none if the card edits an existing file only; Requirements: → restate the card title as a one-sentence requirement; Commit: → derive from the card title using the existing conventional-commit prefix pattern. |
   | card-numbering                 | Renumber cards within the affected batch sequentially starting at the lowest existing number; if the conflict is across batches, re-number the later-batch's cards to start above the earlier batch's max. Update every "card N" reference inside the plan. |
   | depends-on-unknown             | If the unknown dep is an integer, compare it against the `number:` values in the Batch Index — if close to an existing number (likely a typo), correct it. If the unknown dep is a string (legacy format), compare it against the `name:` values — if it is a typo of an existing entry, correct it. If the dependency genuinely needs a new batch, halt — adding a batch is not a mechanical fix. |
   | parallel-modifies-overlap      | If one batch logically depends on the other, add the missing edge to the dependent's depends-on list. If the two batches truly need to write to the same file in parallel, the plan is structurally wrong — halt.        |
   | reads-not-backtick-path        | Re-format the bullet to backtick-only paths; move any inline parenthetical commentary to the card's Requirements: prose. Strip any line-range suffix (e.g. `:55-65`) from the path.                                       |
   | all-files-touched-mismatch     | Update the overview's All Files Touched to match the union of every card's Edits: + Creates:. (The overview list is derivative; the cards are the source of truth.)                                                |
   | verify-not-isolated            | Open the per-batch file named by the error payload's `batch:` field (resolve `_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field. Replace the frontmatter line `verify: <original>` with `verify: PYTHONPATH= <original>` (literal `PYTHONPATH=`, single space, original command). One row, one prepend. |
   | wiki-config-mutation           | This check cannot be fixed by editing plan files — the batch intentionally modifies `wiki/config.yaml`. To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.) If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-check wiki-config-mutation`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-check wiki-config-mutation`. If neither condition holds: halt — the plan requires redesign. |
   | batch-oversized                | Halt — the batch exceeds `pipeline.max_cards_per_batch` cards and/or the `pipeline.max_batch_context_tokens` context estimate. Splitting a batch is a structural change, not a mechanical fix; the planner must re-split at Phase: Plan. Not auto-fixable. |
   | out-of-worktree-target         | Halt — an `Edits:`/`Creates:` target resolves outside the worktree (home-dir or absolute path). The operator must handle such edits manually; the implementer can never be pointed at them. Not auto-fixable. |
   | missing-overview               | Halt — the plan is structurally broken, not mechanically fixable.                                                                                                                                                       |
   | batch-index-parse              | Halt — the overview's fenced-yaml block is unparseable; not mechanically fixable.                                                                                                                                        |

   Rows where the fix is "halt" are deliberate: those errors signal a structural planning bug that auto-fixing would mask. The two-pass cap fires for these too (the second pass will produce the same error and trigger halt).

   After applying mechanical fixes for every error in the JSON, mill-plan commits the fix(es) on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"` and re-runs the CLI. The commit message uses `validator-fix` to distinguish it from `plan-fix-r{N}` commits (which are LLM-fix-pass commits).

   Before re-running via millpy-bg for the `plan-validator-fix` slug, verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

2. **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`. If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`. Because plan batch review is disabled in this hub (`roles.plan-review.batch.reviewer: null`), the agent-mode branch targets the holistic scope only. If per-batch plan review is ever enabled, the SKILL loops the three-step flow once per enabled scope. If `subprocess` or `psmux`: use the subprocess branch below.

   **Pre-review validator gate:** The pre-review validator (step 1.5) runs unchanged in BOTH modes — it is a Python-only `_plan_validate` check that never dispatches an LLM, so it is independent of dispatch mode.

   **Subprocess/psmux branch — Invoke the CLI as a subprocess:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   The CLI accepts two optional scope flags (mutually exclusive): `--holistic-only` skips per-batch reviews and runs only the holistic plan review; `--no-holistic` skips the holistic plan review and runs per-batch reviews only. Default — both run per the `roles.plan-review.batch.reviewer` and `roles.plan-review.holistic.reviewer` config keys. Append the flag to the inner `uv run …millpy-review-plan.py` portion of the millpy-bg invocation when needed.

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The script discovers the slug and round from disk. It prints one JSON line: `{"type": "plan", "round": N, "verdict": "APPROVE" | "REQUEST_CHANGES", "blocking_count": N, "reviews": [...]}` where each review entry has `{scope, verdict, file}`.

3. **BEFORE reading any review file, load the `mill-receiving-review` skill** (`plugins/mill/skills/mill-receiving-review/SKILL.md`). Non-negotiable. The VERIFY → HARM CHECK → FIX-or-PUSH-BACK decision tree is what keeps review loops useful.

4a. On `APPROVE` (verdict from JSON) with zero `[NIT]` findings (read the review file at `reviews[0].file` and confirm zero `[NIT]`-prefixed findings): set overview frontmatter `approved: true` via direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`. Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"`. Push. Break loop → Handoff. `iso_ts` is `_timestamp.now_utc_iso()`.

4b. On `APPROVE` with one or more `[NIT]` findings: apply each NIT per the `mill-receiving-review` decision tree by editing the plan files directly. Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` (timestamp from `_timestamp.now_utc_compact()`) with two sections — `## Fixed` (one line per fixed NIT: short reference to the source review file + quoted finding title) and `## Pushed Back` (one line per rejected NIT: short reference + reason citing code, doc, or scope per `mill-receiving-review`'s legitimate-pushback rules). Re-validate the plan DAG via `_plan_dag.validate`. Call `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`. Set overview frontmatter `approved: true` via direct Edit. Single git commit covering exactly four pathspecs — `<plan_dir>`, `<reviews_dir>`, `<status_path>`, `_mill/briefs/` — with message `mill-plan: plan-fix round {N} for {slug}` (matches existing 4d message shape; the round counter is NOT advanced). Push. Break loop → Handoff.

4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 2 has a non-empty `reviews[]` array AND at least one entry's `verdict` is `"ERROR"`, OR when no JSON line appears in the bg log (no `^{` summary line after `[mill-bg] EXIT`, indicating the worker died before printing — e.g. killed, OOM), skip steps 4a/4b/4c/4d entirely and immediately re-run:

   **Agent-mode:** follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-review-plan.py` and `<args> = --holistic-only`.

   **Subprocess/psmux branch:**

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug plan-review-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py"
   ```

   This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter is **not** consumed — the round produced no reviewable output. Absent-JSON and `verdict: ERROR` share **one consecutive-non-reviewable-round counter**: any mix of two consecutive non-reviewable rounds (ERROR then absent-JSON, or vice versa) triggers the two-pass cap. On the **second** consecutive non-reviewable run, halt: if it was absent-JSON, report `BLOCKED: plan review no-JSON round {N}` and surface the last stderr line(s) from the bg log; if it was `verdict: ERROR`, report `BLOCKED: review ERROR-only round {N}` and surface each entry's `error` string to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors step 1.5's validator gate. *(Note: the CLI now emits a `verdict: ERROR` envelope on uncaught exceptions per millpy-review-plan.py, so a true absent-JSON line means the worker died before printing — mirroring mill-go's "only treat exit 1 as unrecoverable when the JSON line is absent" rule. Closes #84 — `verdict: ERROR` tracking was introduced so ERROR rounds never silently collapse into 4c's NIT path.)*

4c. On `REQUEST_CHANGES` AND `blocking_count == 0` (the JSON's top-level field): the round produced only NITs. Apply NIT fixes per the `mill-receiving-review` Decision Tree (no different from a regular fix-pass), write the fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md`, append `plan-fix-r{N}` to status timeline, set overview frontmatter `approved: true`, commit+push (single commit covering plan + reviews + status + `_mill/briefs/`), break loop → Handoff. Do NOT run round N+1. Rationale: 0-BLOCKING means the planner and reviewer have converged; further rounds only churn cosmetic NITs.

4d. On `REQUEST_CHANGES` AND `blocking_count > 0`:
   - `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`.
   - Read each review file. For each finding, run the `mill-receiving-review` decision tree.
   - Apply fixes to plan files.
   - Write a fixer report at `<reviews_dir>/<YYYYMMDD-HHMMSS>-plan-fix-r<N>.md` with two sections: `## Fixed` (each fixed finding, one-line reference to the review file + quoted finding title) and `## Pushed Back` (each rejected finding, same format + reason citing code/doc/scope).
   - Re-validate the plan DAG (`_plan_dag.validate`).
   - `_status.append_phase(status_path, f"plan-fix-r{N}", iso_ts)`.
   - Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git commit -m "mill-plan: plan-fix round {N} for {slug}"`.

5. **Non-progress check** (after writing each fixer report from round 2 onward): **Skip this check when the latest round's `## Pushed Back` section is empty.** Empty Pushed Back means the planner addressed every finding cleanly — that is convergence, not non-progress. The check only fires when both rounds have a non-empty Pushed Back AND the title set is identical. If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.set_blocked(status_path, f"non-progress round {N}", timestamp=ts)`; commit `git -C <worktree> add <status_path> <reviews_dir> && git -C <worktree> commit -m "mill-plan: blocked (autonomous-mode non-progress) for {slug}"` and push; halt with "Autonomous mode: plan blocked on non-progress at round {N}. Task left as [active] for manual review." If the set is identical, halt with `BLOCKED: Plan review non-progress round {N}` and tell the user to look at the fixer reports. Do not escape-hatch — non-progress means the planner and reviewer are stuck in a stable disagreement; user intervention is required.

6. **Max-rounds escape** (only when round counter exhausts without APPROVE, BLOCKINGs still remain, AND non-progress did not fire): If the deep-merged config has `pipeline.autonomous_mode: true`: skip the user prompt; `_status.set_blocked(status_path, f"max-rounds exhausted after {N} rounds, {M} BLOCKINGs remain", timestamp=ts)`; commit and push; halt with "Autonomous mode: plan blocked after {N} rounds, {M} BLOCKINGs remain. Task left as [active]." present the user with the prompt below verbatim, computing `{N}` and `{M}` and a one-line recommendation. `{M}` is `result["blocking_count"]` from the most recent CLI invocation — do not re-count manually. If `blocking_count` was 0 in the latest round, this prompt should not have fired — verify step 4c logic before presenting.

   > After {N} rounds, {M} BLOCKING findings remain unresolved (blocking_count from latest round's review JSON). Options:
   > A) Deep problems — rethink approach. Go back to mill-start and revise discussion.
   > B) Shallow — one more review round. Invoke: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds {N+1}` (the `--max-rounds` flag overrides the configured cap; without it the script re-reads config and exits at the same cap again).
   > C) Override — accept findings and proceed to mill-go anyway.
   > Recommended: {A/B/C} based on {analysis of remaining findings}.

   Wait for the user's choice. A → halt and tell user to check out fresh after they revise. B → invoke `millpy-review-plan.py --max-rounds {N+1}` where `{N}` is the round count just reported (one extra round beyond the configured max). C → set `approved: true` and proceed to Handoff.

### Phase: Handoff

**Guard.** Read `plan_dir / "00-overview.md"` and parse the `approved:` field from the top fenced yaml block. If it is not the literal boolean `true`, halt with: `BLOCKED: mill-plan Handoff guard -- plan/00-overview.md has approved: false. Plan review did not complete. Re-run /mill-plan to enter Phase: Plan Review.` To parse: extract the YAML block via the existing pattern (`re.search(r"```yaml(.*?)```", overview_text, re.DOTALL)`), then read `approved:` with `yaml.safe_load(yaml_text)["approved"]`. Reject string `"true"` — the value must be the YAML boolean (overview template writes `approved: false`, the flip in step 4a/4b/4c writes `approved: true` as bare YAML). The guard runs *before* any `_status` mutation, so a guard failure leaves status.md untouched and the operator can re-enter cleanly.

`_status.append_phase(status_path, "planned", _timestamp.now_utc_iso())`. Commit+push.

If the deep-merged config has `pipeline.auto_report: true`, invoke `/mill-self-report --auto` and let it finish before reporting to the user. The skill checks `gh auth` itself and bails cleanly if absent, so this is always safe to call.

Report: **"Plan complete. Run `/mill-go` next to start autonomous implementation."** Do not invoke mill-go yourself — handoff to mill-go is always an explicit user decision, even when auto-report fired.

## Timestamps

Always use `_timestamp.now_utc_compact()` / `now_utc_iso()` for any generated timestamp (plan `started:`, fixer-report filenames, status.md timeline rows). Never hand-write or guess a date.

## Principles

- **Plan the full scope** — no "we'll add X later" phases inside the plan.
- **YAGNI ruthlessly** — don't plan for hypothetical requirements.
- **Follow `mill-receiving-review`'s decision tree** — never dismiss a finding with "low risk", "out of scope", "pre-existing".
- **Autonomous** — the only user interaction is the max-rounds escape and non-progress halt.
- **Card `Context:` is an allowlist** — list every file the implementer needs to read WITHOUT editing. An empty or terse `Context:` is a review-blocker. The implementer reads ONLY listed files; any unlisted file is a plan defect. `Edits:` files are implicitly read — do not repeat them in `Context:`. All paths must be backtick-wrapped, one per bullet; no inline prose, no line-range suffixes.
- **`Requirements:` must use stable identifiers** — name the specific function, class, or constant being changed. "Replace `_load_config` in `mill-claim.py` with `from _config import load_config`" is correct. "Refactor config loading to use the shared helper" is not — it forces the implementer to explore, defeating the cold-start guarantee.

## Board discipline

- Task-state writes (`status_path`, `plan_dir`, `reviews_dir`) are committed on the task branch via `git add` + `git commit`, then pushed to remote. They never go through the wiki.
- Phase transitions via `_status.append_phase`. Hand-editing the status.md yaml block is banned; use `update_field` for the plan pointer.
- The overview frontmatter's `approved:` field is the exception — it lives in `plan/00-overview.md`, not `status.md`, and is flipped by a direct Edit because `_status.py` only knows about status.md.

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\skills\mill-plan\SKILL.md ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_gitignore.py ---
"""
Idempotent .gitignore marker-block helper for mill-setup Phase 4.5b.

Writes and maintains a ``# === mill-managed ... # === end mill-managed ===``
block at the end of the repo's ``.gitignore``. The block covers standard
mill paths declared in ``GLOB_ENTRIES``.

Outside-marker content is NEVER modified. Duplicate entries that already
exist outside the markers are left alone.

Public API:
    render_block(glob_entries)
        Return the full marker-block text. ``glob_entries`` are written as-is.
    upsert(gitignore_path, glob_entries)
        Write or rewrite the marker block in a single ``.gitignore`` file.
        Returns ``True`` if the file was written (content changed), ``False``
        if already byte-equal.

Constants:
    START        — opening marker line
    END          — closing marker line
    GLOB_ENTRIES — glob-pattern entries always written to the repo root gitignore
"""
from __future__ import annotations

from pathlib import Path

START = "# === mill-managed (regenerated by mill-setup) ==="
END = "# === end mill-managed ==="

GLOB_ENTRIES: list[str] = [
    "**/.millhouse/",
    "**/.scratch/",
    "**/.wiki/",
    "**/.active/",
    "**/_mill/*.active",
    "**/.portals/",
]


def render_block(glob_entries: list[str]) -> str:
    """
    Return the marker-block text.

    ``glob_entries`` are written as-is between the START and END markers.

    Args:
        glob_entries: Glob-pattern entries (e.g. ``GLOB_ENTRIES``).

    Returns:
        Multi-line string starting with ``START`` and ending with
        ``END\\n``.
    """
    lines = [START]
    for entry in glob_entries:
        lines.append(entry)
    lines.append(END)
    return "\n".join(lines) + "\n"


def _upsert_single(gitignore_path: Path, block_text: str) -> bool:
    """Write or rewrite a marker block in a single .gitignore file.

    Locates the existing ``START`` / ``END`` markers (if any), removes the
    old block and its blank-line separator, and appends the new block. If no
    prior block exists the block is appended with a blank-line separator.

    Returns True if the file was written (content changed), False if already
    byte-equal.

    Raises:
        ValueError: ``START`` is present but ``END`` is absent — the file is
            in a corrupt/partial state that cannot be repaired automatically.
    """
    if gitignore_path.exists():
        existing = gitignore_path.read_text(encoding="utf-8")
    else:
        existing = ""

    start_idx = existing.find(START)
    end_idx = existing.find(END)

    if start_idx != -1 and end_idx == -1:
        raise ValueError(
            f"Found START marker but no END marker in {gitignore_path}. "
            "The file appears corrupt — remove the partial block manually and re-run."
        )

    if start_idx != -1:
        prefix = existing[:start_idx]
        stripped_prefix = prefix.rstrip("\n")
        rebuilt = stripped_prefix + "\n\n" + block_text if stripped_prefix else block_text
    else:
        stripped = existing.rstrip("\n")
        rebuilt = stripped + "\n\n" + block_text if stripped else block_text

    if rebuilt == existing:
        return False

    gitignore_path.write_text(rebuilt, encoding="utf-8")
    return True


def upsert(gitignore_path: Path, glob_entries: list[str]) -> bool:
    """
    Write or rewrite the mill marker block in a single ``.gitignore`` file.

    Renders the block via ``render_block(glob_entries)`` and delegates to
    ``_upsert_single``.

    Args:
        gitignore_path: Path to the ``.gitignore`` file to update.
        glob_entries: Glob-pattern entries (e.g. ``GLOB_ENTRIES``).

    Returns:
        ``True`` if the file was written (content changed), ``False`` if
        already byte-equal.

    Raises:
        ValueError: START marker present but END marker absent in the file.
    """
    block = render_block(glob_entries)
    return _upsert_single(gitignore_path, block)

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_gitignore.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-gitignore-phase.py ---
"""Unit tests for plugins/mill/scripts/_gitignore.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _gitignore import (  # noqa: E402
    END,
    GLOB_ENTRIES,
    START,
    render_block,
    upsert,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_anchored_entries_not_exported() -> int:
    errors = 0
    try:
        from _gitignore import ANCHORED_ENTRIES  # noqa: F401
        print("FAIL: ANCHORED_ENTRIES import should have raised ImportError", file=sys.stderr)
        errors += 1
    except ImportError:
        print("PASS: ANCHORED_ENTRIES no longer exported")
    return errors


def test_upsert_first_call_returns_true() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        changed = upsert(gi, GLOB_ENTRIES)
        if not changed:
            print("FAIL: upsert first call on empty .gitignore should return True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: upsert first call returns True (wrote new block)")
    return errors


def test_upsert_idempotent() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        upsert(gi, GLOB_ENTRIES)
        changed = upsert(gi, GLOB_ENTRIES)
        if changed:
            print("FAIL: upsert second call should return False (already up to date)", file=sys.stderr)
            errors += 1
        else:
            print("PASS: upsert second call returns False (idempotent)")
    return errors


def test_upsert_preserves_existing_content() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")
        upsert(gi, GLOB_ENTRIES)
        content = _read(gi)
        if "*.pyc" not in content:
            print("FAIL: upsert did not preserve existing content above the block", file=sys.stderr)
            errors += 1
        if START not in content:
            print("FAIL: upsert did not append block to non-empty .gitignore", file=sys.stderr)
            errors += 1
        if content.index("*.pyc") > content.index(START):
            print("FAIL: existing content should appear before the mill block", file=sys.stderr)
            errors += 1
        if errors == 0:
            print("PASS: upsert appends block below existing content, preserving existing lines")
    return errors


def test_upsert_corrupt_marker_raises() -> int:
    errors = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text(f"{START}\n**/.millhouse/\n", encoding="utf-8")
        try:
            upsert(gi, GLOB_ENTRIES)
            print("FAIL: expected ValueError for corrupt marker (START without END)", file=sys.stderr)
            errors += 1
        except ValueError:
            print("PASS: upsert raises ValueError for corrupt marker (START without END)")
    return errors


def test_render_block_contains_glob_entries() -> int:
    errors = 0
    block = render_block(GLOB_ENTRIES)
    for entry in GLOB_ENTRIES:
        if entry not in block:
            print(f"FAIL: render_block output missing entry: {entry}", file=sys.stderr)
            errors += 1
        elif not (block.index(START) < block.index(entry) < block.index(END)):
            print(f"FAIL: '{entry}' not between START and END markers", file=sys.stderr)
            errors += 1
    for removed in ("**/wts/", "**/portals/", "**/plugins/*/uv.lock"):
        if removed in GLOB_ENTRIES:
            print(f"FAIL: '{removed}' should not be in GLOB_ENTRIES", file=sys.stderr)
            errors += 1
    if errors == 0:
        print("PASS: render_block includes all five GLOB_ENTRIES between START and END; removed entries absent")
    return errors


def test_glob_entries_contains_new_junction_names() -> int:
    errors = 0
    for expected in ("**/.portals/", "**/.wiki/", "**/.active/"):
        if expected not in GLOB_ENTRIES:
            print(f"FAIL: GLOB_ENTRIES missing '{expected}'", file=sys.stderr)
            errors += 1
    if errors == 0:
        print("PASS: GLOB_ENTRIES contains **/.portals/, **/.wiki/, **/.active/")
    return errors


def test_glob_entries_excludes_briefs() -> int:
    errors = 0
    for entry in GLOB_ENTRIES:
        if "_mill/briefs" in entry:
            print(f"FAIL: GLOB_ENTRIES contains _mill/briefs in entry '{entry}' — briefs must remain tracked", file=sys.stderr)
            errors += 1
    if errors == 0:
        print("PASS: GLOB_ENTRIES contains no _mill/briefs entry — briefs are tracked, not ignored")
    return errors


def main() -> int:
    tests = [
        test_anchored_entries_not_exported,
        test_upsert_first_call_returns_true,
        test_upsert_idempotent,
        test_upsert_preserves_existing_content,
        test_upsert_corrupt_marker_raises,
        test_render_block_contains_glob_entries,
        test_glob_entries_contains_new_junction_names,
        test_glob_entries_excludes_briefs,
    ]
    errors = 0
    for test in tests:
        errors += test()

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _gitignore unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-gitignore-phase.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_review_code.py ---
"""
Review backend for code artefacts.

v2 code review does NOT look at git diff. It reads the approved plan and
the source files the plan says were touched, then asks the reviewer:
"does the implementation on disk realise what the plan promised?" The
orchestrator (mill-go) invokes this once per batch after the implementer
commits that batch, and optionally one holistic review at end-of-task.

Two modes, selected by ``scope``:

- ``scope="<name>"`` — per-batch review. Bulks
  ``00-overview.md`` + the single ``NN-<batch>.md`` + every file under
  that batch's ``Context:`` / ``Edits:`` / ``Creates:`` lines.
- ``scope="holistic"`` — holistic review. Bulks ``00-overview.md`` +
  every batch file + the union of all referenced files.

Both modes accept ``extra_files`` — source files the orchestrator has
decided to include in the bulk this round, typically because a previous
round returned ``verdict: NEED_CONTEXT`` pointing at them. The reviewer
never scrapes git for files; the backend is explicit about what ends up
in the prompt.

Public API:
    prepare(cfg, slug, *, scope, mill_dir, project_root, wiki_root, git_root, extra_files=None) -> dict
        Render prompt and resolve spec; return prepare dict.
    finalize(cfg, slug, raw_text, *, scope, round_n, reviews_dir, mill_dir, project_root, wiki_root, git_root) -> ReviewResult
        Parse verdict from raw_text and return ReviewResult.
    run(cfg, slug, mill_dir, wiki_root, project_root,
        *, batch_name=None, extra_files=None) -> ReviewResult
        Legacy API; calls prepare -> reviewer -> finalize.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _paths
import _reviewer_single
import _reviewers
from _llm_common import LLMError
from _plan_dag import PlanDAGError, extract_batch_index
import _status
from _review_common import (
    ReviewError,
    ReviewResult,
    _load_root_from_overview,
    build_deletes_section,
    build_manifest_section,
    build_reattached_section,
    build_tool_rule,
    bulk_files,
    bulk_files_with_diff,
    compute_creates_union,
    compute_deletes_union,
    discover_round,
    extract_review_content,
    finalize_scope,
    load_task_title,
    maybe_switch_spec_for_large_prompt,
    parse_batch_refs,
    parse_blocking_count,
    parse_missing_context,
    parse_verdict,
    read_constraints_md,
    render_prompt,
    resolve_existing_paths,
    resolve_path,
    resolve_ref_paths,
    worktree_snapshot_guard,
    write_review_file,
)


def _aggregate_top_verdict(reviews_list: list[dict], parsed_verdict: str) -> str:
    """Return 'ERROR' if every sub-review has verdict 'ERROR', else parsed_verdict."""
    return (
        "ERROR"
        if reviews_list and all(r.get("verdict") == "ERROR" for r in reviews_list)
        else parsed_verdict
    )


def _collect_batch_files(
    plan_dir: Path,
    batch_name: str | None,
    overview_path: Path,
) -> list[Path]:
    """Return the batch files this review covers.

    ``batch_name=None`` → every ``NN-<name>.md`` in ``plan_dir`` except
    ``00-overview.md``. ``batch_name="<name>"`` → the single batch file
    the overview's Batch Index maps ``<name>`` to.
    """
    if batch_name is None:
        files = sorted(
            p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
        )
        if not files:
            raise ReviewError(f"No batch files found in {plan_dir}")
        return files

    overview_text = overview_path.read_text(encoding="utf-8")
    try:
        batches = extract_batch_index(overview_text)
    except PlanDAGError as exc:
        raise ReviewError(f"Could not parse Batch Index: {exc}") from exc

    entry = next((b for b in batches if b.get("name") == batch_name), None)
    if entry is None:
        known = ", ".join(repr(b.get("name")) for b in batches) or "(none)"
        raise ReviewError(
            f"Batch {batch_name!r} not found in Batch Index; known: {known}"
        )
    batch_file = plan_dir / entry["file"]
    if not batch_file.exists():
        raise ReviewError(
            f"Batch {batch_name!r} declared but file missing: {batch_file}"
        )
    return [batch_file]


def _build_artefact_section(
    reviewer_mode: str,
    overview_path: Path,
    batch_files: list[Path],
    source_files: list[Path],
    ancestors_on_disk: list[Path],
    deletes_union: set[str],
    *,
    start_sha: str | None = None,
    diff_threshold: float = 0.25,
    project_root: Path | None = None,
) -> str:
    """Return the ``<ARTEFACT_SECTION>`` block for the prompt.

    In tool-use mode we pass paths and tell the reviewer to Read them
    itself; in bulk mode we splice the file contents inline. Both modes
    list the same files — only the delivery mechanism differs.
    ``ancestors_on_disk`` holds cross-batch creates that already exist on
    disk; they are appended to the bulk so the reviewer can verify
    cross-batch contracts. ``deletes_union`` appends an
    ``## Intentionally deleted`` section when non-empty.
    """
    all_bulked = [overview_path, *batch_files, *source_files, *ancestors_on_disk]
    manifest = build_manifest_section(all_bulked)

    if reviewer_mode == "tool-use":
        batch_list = "\n".join(f"  - `{p}`" for p in batch_files) or "  (none)"
        read_list = "\n".join(f"- `{p}`" for p in [*source_files, *ancestors_on_disk]) or "(none)"
        body = (
            f"{manifest}\n\n"
            "## Plan + source files to review\n"
            f"- Overview: `{overview_path}`\n"
            f"- Batch file(s):\n{batch_list}\n\n"
            "Read the overview and every batch file above. Then read every "
            "source file listed below for full context (includes cross-batch "
            f"ancestor creates already on disk):\n{read_list}"
        )
    else:
        # Always bulk overview + batch files + ancestors at full content.
        # source_files use diff-scoping if start_sha is set.
        plan_and_ancestors = [overview_path, *batch_files, *ancestors_on_disk]
        if start_sha is not None and project_root is not None:
            scoped_sources = bulk_files_with_diff(source_files, start_sha, project_root, diff_threshold)
            bulked = bulk_files(plan_and_ancestors) + ("\n\n" + scoped_sources if scoped_sources else "")
        else:
            bulked = bulk_files(all_bulked)
        body = (
            f"{manifest}\n\n"
            "## Plan + source content (overview + batch files + referenced source + ancestor creates)\n"
            f"{bulked}"
        )

    if deletes_union:
        body += "\n\n" + build_deletes_section(sorted(deletes_union))
    return body


def prepare(
    cfg: dict,
    slug: str,
    *,
    scope: str | None,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    git_root: Path,
    extra_files: list[Path] | None = None,
    max_rounds: int | None = None,
) -> dict:
    """Prepare a code review by rendering the prompt for a single scope.

    Args:
        scope: Batch name (e.g., "01-setup") or None for holistic.
        extra_files: Additional source files to include in the bulk.
        max_rounds: Override the configured round cap for this scope.

    Returns:
        Dict with keys: prompt_text, model, round, reviews_dir, scope.
    """
    # 1. Paths + round counter
    plan_dir = resolve_path(cfg["paths"]["plan_dir"], slug)
    reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
    scope_label = scope or "holistic"
    round_n = discover_round(reviews_dir, "code", scope_label)

    # Round cap check. The max_rounds kwarg overrides the configured cap
    # (mirrors run()'s pre-refactor behaviour); enforcing here covers both the
    # full path and the agent-mode CLI prepare stage.
    if scope is not None:
        configured_max = cfg["roles"]["code-review"]["batch"]["rounds"]
    else:
        configured_max = cfg["roles"]["code-review"]["holistic"]["rounds"]
    effective_max = max_rounds if max_rounds is not None else configured_max
    if round_n > effective_max:
        raise ReviewError(
            f"Round {round_n} exceeds max {effective_max} for code review"
        )

    # 2. Overview (required)
    overview_path = plan_dir / "00-overview.md"
    if not overview_path.exists():
        raise ReviewError(f"Plan overview not found: {overview_path}")
    root = _load_root_from_overview(overview_path)

    # 3. Target batch files + referenced source files
    batch_files = _collect_batch_files(plan_dir, scope, overview_path)

    # Per-batch diff-scoping: read start_sha from status.md if scope is set.
    start_sha: str | None = None
    diff_threshold: float = cfg["roles"]["code-review"].get("diff_scope_threshold", 0.25)
    if scope is not None:
        try:
            status_path = _paths.status_path(project_root, cfg)
            batches_list = _status.read_batches(status_path)
            entry = next((b for b in batches_list if b.get("name") == scope), None)
            start_sha = entry.get("start_sha") if entry else None
            if start_sha is None:
                print(
                    f"[_review_code] no start_sha for batch {scope!r}; using full file content",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                f"[_review_code] warning: could not read start_sha for batch {scope!r}: {exc}; using full file content",
                file=sys.stderr,
            )

    all_raw_refs: dict[str, None] = {}
    for bp in batch_files:
        for ref in parse_batch_refs(bp):
            all_raw_refs[ref] = None
    creates_union = compute_creates_union(plan_dir)
    deletes_union = compute_deletes_union(plan_dir)
    referenced = resolve_ref_paths(
        list(all_raw_refs.keys()), project_root, root,
        creates_union=creates_union, deletes_union=deletes_union, wiki_root=wiki_root, git_root=git_root,
    )

    # Deduplicate while preserving order across the two lists.
    seen: dict[Path, None] = {}
    source_files: list[Path] = []
    for p in (*referenced, *(extra_files or [])):
        if p not in seen:
            seen[p] = None
            source_files.append(p)

    if not source_files and not (extra_files or []):
        print(
            f"[_review_code] warning: no source files resolved for scope={scope_label}; "
            f"reviewer will only see plan content",
            file=sys.stderr,
        )

    ancestors_on_disk = resolve_existing_paths(
        [raw for raw in creates_union if raw not in all_raw_refs],
        project_root,
        root,
        wiki_root=wiki_root,
        git_root=git_root,
    )
    ancestors_on_disk = [p for p in ancestors_on_disk if p not in source_files]

    # 4. Reviewer + prompt
    if scope is not None:
        reviewer_name = cfg["roles"]["code-review"]["batch"]["reviewer"]
    else:
        reviewer_name = cfg["roles"]["code-review"]["holistic"]["reviewer"]
    if reviewer_name is None:
        raise ReviewError(
            f"code-review {'batch' if scope else 'holistic'} reviewer is null; "
            f"the orchestrator should not have invoked this scope"
        )
    hub_dir = project_root
    registry = _reviewers.load(hub_dir)
    spec = _reviewers.resolve(registry, reviewer_name)

    template_name = "review-code-batch" if scope else "review-code-holistic"
    mode = "tool-use" if spec.get("tooluse") else "bulk"
    tool_rule = build_tool_rule(mode)
    artefact_section = _build_artefact_section(
        mode, overview_path, batch_files, source_files, ancestors_on_disk,
        deletes_union,
        start_sha=start_sha,
        diff_threshold=diff_threshold,
        project_root=project_root,
    )

    prompt_kwargs = {
        "task_title": load_task_title(project_root, wiki_root, cfg, slug),
        "tool_rule": tool_rule,
        "artefact_section": artefact_section,
        "constraints": read_constraints_md(project_root),
        "round": round_n,
        "reviewer_model": reviewer_name,
    }
    if scope:
        prompt_kwargs["batch_name"] = scope

    prompt_text = render_prompt(template_name, **prompt_kwargs)

    if scope is None:
        spec, reviewer_name = maybe_switch_spec_for_large_prompt(
            prompt_text, spec, reviewer_name, cfg, "code-review", "holistic", registry
        )

    return {
        "prompt_text": prompt_text,
        "model": spec.get("model"),
        "round": round_n,
        "reviews_dir": reviews_dir,
        "scope": scope_label,
    }


def finalize(
    cfg: dict,
    slug: str,
    raw_text: str,
    *,
    scope: str | None,
    round_n: int,
    reviews_dir: Path,
    mill_dir: Path,
    project_root: Path,
    wiki_root: Path,
    git_root: Path,
) -> ReviewResult:
    """Finalize a code review by parsing verdict and writing the review file.

    Args:
        raw_text: Raw review output from the reviewer.
        scope: Batch name or None for holistic.
        round_n: Round number.
        reviews_dir: Directory where review files are stored.

    Returns:
        ReviewResult with verdict, blocking count, and review entries.
    """
    scope_label = scope or "holistic"

    try:
        review_entry = finalize_scope(
            reviews_dir, "code", round_n, raw_text, scope=scope
        )
    except ReviewError as exc:
        path = write_review_file(
            reviews_dir,
            "code",
            round_n,
            raw_text,
            scope=scope,
        )
        return ReviewResult(
            type="code",
            round=round_n,
            verdict="ERROR",
            blocking_count=0,
            reviews=[{
                "scope": scope_label,
                "verdict": "ERROR",
                "file": str(path),
                "error": f"parse_verdict failed: {exc}",
                "session_id": None,
            }],
        )

    return ReviewResult(
        type="code",
        round=round_n,
        verdict=review_entry["verdict"],
        blocking_count=review_entry["blocking_count"],
        nit_count=review_entry["nit_count"],
        reviews=[{
            "scope": scope_label,
            "verdict": review_entry["verdict"],
            "file": review_entry["file"],
            "session_id": None,
        }],
    )


def run(
    cfg: dict,
    slug: str,
    mill_dir: Path,
    wiki_root: Path,
    project_root: Path,
    *,
    git_root: Path,
    max_rounds: int | None = None,
    batch_name: str | None = None,
    extra_files: list[Path] | None = None,
) -> ReviewResult:
    """Review the code produced for a task.

    ``batch_name`` selects per-batch vs. holistic mode. ``extra_files`` are
    additional source files to bulk this round.
    """
    with worktree_snapshot_guard(project_root, expected_paths=[cfg["paths"]["reviews_dir"]]):
        # Check if review is disabled
        scope_label = batch_name or "holistic"
        reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)
        if batch_name is not None:
            effective_max = max_rounds if max_rounds is not None else cfg["roles"]["code-review"]["batch"]["rounds"]
        else:
            effective_max = max_rounds if max_rounds is not None else cfg["roles"]["code-review"]["holistic"]["rounds"]
        if effective_max == 0:
            print(
                "[_review_code] rounds=0 -- review disabled, returning APPROVE",
                file=sys.stderr,
            )
            return ReviewResult(
                type="code",
                round=0,
                verdict="APPROVE",
                blocking_count=0,
                reviews=[{"scope": scope_label, "verdict": "APPROVE", "file": None, "skipped": True}],
            )

        # Prepare
        prepare_result = prepare(
            cfg, slug, scope=batch_name, mill_dir=mill_dir, project_root=project_root,
            wiki_root=wiki_root, git_root=git_root, extra_files=extra_files,
            max_rounds=max_rounds,
        )
        prompt_text = prepare_result["prompt_text"]
        round_n = prepare_result["round"]
        reviews_dir = prepare_result["reviews_dir"]

        # Get spec for reviewer call
        if batch_name is not None:
            reviewer_name = cfg["roles"]["code-review"]["batch"]["reviewer"]
        else:
            reviewer_name = cfg["roles"]["code-review"]["holistic"]["reviewer"]
        registry = _reviewers.load(project_root)
        spec = _reviewers.resolve(registry, reviewer_name)
        timeout = cfg["llm"]["holistic_timeout"] if batch_name is None else cfg["llm"]["bulk_timeout"]
        if batch_name is None:
            spec, _ = maybe_switch_spec_for_large_prompt(
                prompt_text, spec, reviewer_name, cfg, "code-review", "holistic", registry
            )

        # Invoke reviewer
        try:
            raw, session_id = _reviewer_single.run(spec, prompt_text, timeout=timeout)
            raw = extract_review_content(raw)
        except LLMError as exc:
            return ReviewResult(
                type="code",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=[{
                    "scope": scope_label,
                    "verdict": "ERROR",
                    "file": None,
                    "error": str(exc),
                    "session_id": None,
                }],
            )

        # Try to parse verdict; if NEED_CONTEXT, retry
        try:
            verdict = parse_verdict(raw)
        except ReviewError as exc:
            path = write_review_file(
                reviews_dir,
                "code",
                round_n,
                raw,
                scope=batch_name,
            )
            return ReviewResult(
                type="code",
                round=round_n,
                verdict="ERROR",
                blocking_count=0,
                reviews=[{
                    "scope": scope_label,
                    "verdict": "ERROR",
                    "file": str(path),
                    "error": f"parse_verdict failed: {exc}",
                    "session_id": session_id,
                }],
            )

        # Handle NEED_CONTEXT with retry
        if verdict == "NEED_CONTEXT":
            root = _load_root_from_overview(resolve_path(cfg["paths"]["plan_dir"], slug) / "00-overview.md")
            missing_raw = parse_missing_context(raw)
            missing_paths = resolve_existing_paths(
                missing_raw, project_root, root, wiki_root=wiki_root, git_root=git_root
            )
            if missing_paths:
                retry_prompt = (
                    build_reattached_section(missing_paths)
                    + "\n\n"
                    + "Please continue your review using the re-attached files above. "
                    + "The original prompt is already in your session context."
                )
                print(
                    f"[_review_code] NEED_CONTEXT round-1; retrying with resume "
                    f"({len(missing_paths)} re-attached file(s)) session={(session_id or '?')[:8]}",
                    file=sys.stderr,
                )
                try:
                    raw, session_id = _reviewer_single.run(
                        spec, retry_prompt, session_id=session_id, resume=True, timeout=timeout
                    )
                    raw = extract_review_content(raw)
                except LLMError as exc:
                    return ReviewResult(
                        type="code",
                        round=round_n,
                        verdict="ERROR",
                        blocking_count=0,
                        reviews=[{
                            "scope": scope_label,
                            "verdict": "ERROR",
                            "file": None,
                            "error": f"resume retry failed: {exc}",
                            "session_id": None,
                        }],
                    )
                try:
                    verdict = parse_verdict(raw)
                except ReviewError as exc:
                    path = write_review_file(
                        reviews_dir,
                        "code",
                        round_n,
                        raw,
                        scope=batch_name,
                    )
                    return ReviewResult(
                        type="code",
                        round=round_n,
                        verdict="ERROR",
                        blocking_count=0,
                        reviews=[{
                            "scope": scope_label,
                            "verdict": "ERROR",
                            "file": str(path),
                            "error": f"parse_verdict failed: {exc}",
                            "session_id": session_id,
                        }],
                    )

        # Finalize
        result = finalize(
            cfg, slug, raw, scope=batch_name, round_n=round_n, reviews_dir=reviews_dir,
            mill_dir=mill_dir, project_root=project_root, wiki_root=wiki_root, git_root=git_root
        )
        # Preserve session_id from reviewer call
        if result.reviews:
            result.reviews[0]["session_id"] = session_id
        return result

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_review_code.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_review_common.py ---
"""
Shared helpers, regex constants, data classes, and exceptions used by
every Layer 02 review backend.

No dependencies on any other Layer 02 file. Import this from
_review_discussion.py, _review_plan.py, _review_code.py, and the API
scripts.

Public API:
    ReviewError          — raised by the backend on config/slug/round errors
    ReviewerOverstepError — raised by worktree_snapshot_guard when a reviewer mutates HEAD or working tree
    ReviewResult         — dataclass; serialised to the CLI's stdout JSON
    RE_SIMPLE            — regex matching simple review filenames
    RE_BATCH             — regex matching plan-batch review filenames
    find_active_slug()   — branch-based slug detection with _mill/*.active glob fallback
    load_task_title()    — delegate to _marker.task_data for task_title; fall back to slug on MarkerError
    worktree_snapshot_guard() — context manager; snapshot guard wrapping each backend run()
    read_constraints_md()— read CONSTRAINTS.md, empty string if absent
    resolve_path()       — locate a path inside the active hub (where task/ lives) from a config template
    discover_round()     — determine next review round number per (review_type, scope)
    detect_resume_round() — return highest per-batch-only round (no holistic yet), or None
    bulk_files()         — concatenate file contents with FILE delimiters
    bulk_files_with_diff() — like bulk_files but substitutes git diff output for small-diff files
    build_manifest_section() — return a `## Files included` markdown block listing every bulked file
    build_deletes_section() — return a `## Intentionally deleted` markdown block listing deleted tokens
    parse_missing_context() — extract path strings from a `## Missing context` section in review text
    build_reattached_section() — return a `## Re-attached files` block with inlined file contents for NEED_CONTEXT retry
    build_tool_rule()    — mode-specific <TOOL_RULE> block (bulk / tool-use)
    render_prompt()      — render a template from plugins/mill/templates/
    parse_verdict()      — extract APPROVE/REQUEST_CHANGES from fenced yaml block
    parse_blocking_count() — count "### [<severity>]" headings in review output
    write_review_file()  — write a review file with a canonical timestamp name
    aggregate_verdict()  — worst-case verdict across a list of sub-verdicts
    load_config()        — load mill-config.yaml + optional config.local.yaml
    parse_batch_refs()   — extract Context/Edits/Creates paths from a batch file (case-insensitive none filter)
    compute_creates_union() — union of all Creates: tokens across every batch in a plan_dir
    compute_deletes_union() — union of all Deletes: tokens across every batch in a plan_dir
    resolve_ref_paths()  — resolve raw ref strings against project_root; hard-fails on missing paths not in creates_union or deletes_union
    resolve_existing_paths() — resolve raw paths and return only those that already exist on disk (silent drop, no creates_union check)
    _load_root_from_overview() — read root: field from overview's fenced-yaml block
    _check_large_prompt()    — check if prompt exceeds large_prompt threshold; return (is_over_threshold, estimated_ktok)
    resolve_large_prompt_timeout() — return large_prompt.timeout when prompt is over threshold and key is set
    maybe_switch_spec_for_large_prompt() — check prompt size; return (spec, reviewer_name), possibly overridden for large prompts
"""
from __future__ import annotations

import copy
import json
import re
import _subprocess_util
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
import _marker
import _paths
import _pygit2_util
import _render
import _reviewers
from _config import (
    _apply_dispatch_shim,
    apply_env_overrides,
    warn_unknown_keys,
    resolve_plugin_template_path,
)

# ---------------------------------------------------------------------------
# Module-level regex constants
# ---------------------------------------------------------------------------

# Matches simple (non-batch) review filenames:
#   20260418-001200-discussion-review-r1.md
#   20260418-143300-code-review-r2.md
#   20260418-143300-plan-review-r1.md   (plan holistic)
RE_SIMPLE = re.compile(
    r"^\d{8}-\d{6}-(?P<type>discussion|code|plan)-review-r(?P<n>\d+)\.md$"
)

# Matches plan / code per-batch review filenames:
#   20260418-143300-plan-review-01-setup-r1.md
#   20260418-143300-code-review-foundation-r1.md
# RE_SIMPLE is checked first; a file matching RE_SIMPLE is excluded from
# RE_BATCH matching (prevents holistic files from being mis-identified).
RE_BATCH = re.compile(
    r"^\d{8}-\d{6}-(?P<type>plan|code)-review-(?P<batch>[a-z0-9-]+)-r(?P<n>\d+)\.md$"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ReviewError(Exception):
    """Raised by the backend on config / slug / reviewer / round errors.

    Caught by the API scripts, which print str(exc) to stderr and exit 1.
    """


class ReviewerOverstepError(ReviewError):
    """Raised when a reviewer mutated git state (HEAD or working tree) during a review pass.

    Carries the before/after HEAD SHA and the unfiltered git status --porcelain
    diff for operator inspection. The guard does not auto-rollback; the operator
    resets manually after investigating.
    """

    def __init__(self, before_sha: str, after_sha: str, porcelain_diff: str) -> None:
        self.before_sha = before_sha
        self.after_sha = after_sha
        self.porcelain_diff = porcelain_diff
        msg = (
            f"reviewer overstep detected: HEAD {before_sha[:8]} -> {after_sha[:8]}; "
            f"porcelain diff:\n{porcelain_diff}"
        )
        super().__init__(msg)


@contextmanager
def worktree_snapshot_guard(
    project_root: Path,
    *,
    expected_paths: list[str] | None = None,
) -> Iterator[None]:
    """Snapshot git state before/after the with-block; raise on any change.

    Captures `git rev-parse HEAD` and `git status --porcelain` on entry,
    re-captures on exit, and raises ``ReviewerOverstepError`` if either the
    HEAD SHA or the porcelain diff (filtered by ``expected_paths``) differs.

    ``expected_paths`` is a list of substring patterns that filter the
    porcelain diff before comparison. A porcelain line is filtered when its
    path field (with backslashes normalised to forward slashes) contains
    ANY entry in ``expected_paths`` as a substring. HEAD-SHA changes are
    NEVER filtered.

    A fast-forward HEAD advance (where the new HEAD is a descendant of the old
    HEAD) is tolerated if no new working-tree dirt is introduced and no dirt
    is removed outside of a fast-forward commit. A stderr warning is emitted
    when a fast-forward is detected.

    If the wrapped block raises AND state was mutated, ``ReviewerOverstepError`` takes priority and chains the inner exception via ``__cause__``; if state was unchanged the inner exception is re-raised unchanged.
    If the post-snapshot capture itself raises (e.g. ``_capture_head_sha`` propagating a ``ReviewError`` from a broken git invocation), that error propagates and the inner exception is NOT chained -- the capture failure indicates the snapshot is untrustworthy, so the typed ``ReviewerOverstepError`` cannot be raised safely. This is an intentional trade-off; the inner exception, if any, is visible in the traceback frames above the capture call.
    """
    before_sha = _capture_head_sha(project_root)
    before_porcelain = _capture_porcelain(project_root)
    inner_exc: Exception | None = None
    try:
        yield
    except Exception as exc:
        inner_exc = exc
    after_sha = _capture_head_sha(project_root)
    after_porcelain = _capture_porcelain(project_root)
    before_filtered = _filter_porcelain(before_porcelain, expected_paths)
    after_filtered = _filter_porcelain(after_porcelain, expected_paths)

    added = set(after_filtered) - set(before_filtered)
    removed = set(before_filtered) - set(after_filtered)
    head_changed = before_sha != after_sha
    fast_forward = head_changed and _pygit2_util.is_ancestor(project_root, before_sha, after_sha)

    should_raise = (
        (added)  # New working-tree dirt added
        or (head_changed and not fast_forward)  # HEAD rewritten/reset to non-descendant
        or (removed and not fast_forward)  # Dirt removed without a fast-forward commit
    )

    if should_raise:
        diff = _porcelain_diff(before_filtered, after_filtered)
        raise ReviewerOverstepError(before_sha, after_sha, diff) from inner_exc

    if fast_forward and not added and not (removed and not fast_forward):
        print(
            f"[_review_common] HEAD advanced {before_sha[:8]} -> {after_sha[:8]} "
            f"during review window (fast-forward; allowed)",
            file=sys.stderr,
        )

    if inner_exc is not None:
        raise inner_exc


def _capture_head_sha(project_root: Path) -> str:
    """Return the current HEAD SHA as a hex string. Raises ReviewError on git failure."""
    try:
        return _pygit2_util.head_sha(project_root)
    except _pygit2_util.GitOpsError as e:
        raise ReviewError(
            f"worktree_snapshot_guard: HEAD SHA read failed in {project_root}: {e}"
        ) from e


def _capture_porcelain(project_root: Path) -> list[str]:
    """Return git status --porcelain as a list of lines (one per entry). Raises ReviewError on failure."""
    try:
        return _pygit2_util.status_porcelain(project_root, include_untracked=True)
    except _pygit2_util.GitOpsError as e:
        raise ReviewError(
            f"worktree_snapshot_guard: status read failed in {project_root}: {e}"
        ) from e


def _filter_porcelain(lines: list[str], expected_paths: list[str] | None) -> list[str]:
    """Drop porcelain lines whose path field matches any expected_paths substring.

    Each porcelain line has a 2-character status code, a space, then the path.
    Renames have ' -> ' between old and new path; both are checked against expected_paths.
    Path comparison normalises backslashes to forward slashes.
    """
    if not expected_paths:
        return list(lines)
    kept: list[str] = []
    for line in lines:
        # Porcelain format: "XY path" or "XY old -> new" for renames
        path_field = line[3:] if len(line) > 3 else line
        normalised = path_field.replace("\\", "/")
        # Split rename arrows so both sides are checked
        candidates = [s.strip() for s in normalised.split(" -> ")]
        if any(pat in cand for cand in candidates for pat in expected_paths):
            continue
        kept.append(line)
    return kept


def _porcelain_diff(before: list[str], after: list[str]) -> str:
    """Return a human-readable diff string of before vs after porcelain line sets."""
    before_set = set(before)
    after_set = set(after)
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    parts: list[str] = []
    for line in added:
        parts.append(f"  + {line}")
    for line in removed:
        parts.append(f"  - {line}")
    return "\n".join(parts) if parts else "  (no porcelain line diff; HEAD changed)"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReviewResult:
    """Serialisable result returned by every review backend's run() function."""

    type: str                              # "discussion" | "plan" | "code"
    round: int
    verdict: str                           # "APPROVE" | "REQUEST_CHANGES"
    reviews: list[dict] = field(default_factory=list)
    blocking_count: int = 0
    nit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "round": self.round,
            "verdict": self.verdict,
            "blocking_count": self.blocking_count,
            "nit_count": self.nit_count,
            "reviews": self.reviews,
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def find_active_slug(git_root: Path, wiki_path: Path, cfg: dict) -> str:
    """Detect active slug via branch name, falling back to _mill/*.active glob.

    Raises ReviewError (wrapping MarkerError or glob-fallback errors).
    """
    try:
        return _marker.slug_from_branch(git_root, wiki_path, cfg)
    except _marker.MarkerError as exc:
        try:
            matches = list((git_root / "_mill").glob("*.active"))
        except OSError:
            matches = []
        if len(matches) == 1:
            return matches[0].stem
        if len(matches) > 1:
            slugs = sorted(m.stem for m in matches)
            raise ReviewError(
                f"{len(slugs)} tasks active ({', '.join(slugs)}); use --slug <slug>"
            ) from exc
        raise ReviewError(
            f"no active task detected; run mill-spawn or mill-claim to start a task"
            f" (branch detection: {exc})"
        ) from exc


def load_task_title(git_root: Path, wiki_path: Path, cfg: dict, slug: str) -> str:
    """Delegate to _marker.task_data for task_title; fall back to slug on MarkerError."""
    try:
        data = _marker.task_data(git_root, wiki_path, cfg)
    except _marker.MarkerError:
        return slug
    return data.get("task_title") or slug


def read_constraints_md(project_root: Path) -> str:
    """Read CONSTRAINTS.md from the project root.

    Returns empty string if the file is absent.
    """
    constraints_path = project_root / "CONSTRAINTS.md"
    try:
        return constraints_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def resolve_path(path_tmpl: str, slug: str) -> Path:
    """Resolve a config path template to an absolute path inside the active hub.

    Computes the container, git_root, and cfg internally:
      - git_root via _paths.resolve_git_root()
      - container via _paths.resolve_container_path(git_root)
      - hub_dir via _paths.resolve_hub_path() (Path.cwd().resolve() — the hub
        where mill scripts run; equals git_root for hub_relative_path == ".")
      - cfg via load_config(hub_dir, hub_dir / ".millhouse")

    cfg is sourced from the hub's own .millhouse/, not from git_root/.millhouse/,
    because mill-claim writes hub_relative_path only at the hub (it does not
    bootstrap a stub at git_root/.millhouse/ the way mill-spawn does).

    Returns active_hub / path_tmpl after substituting any "<SLUG>" token.

    Raises:
        _paths.ActiveWorktreeNotFound | _paths.ActiveWorktreeSlugMismatch:
            propagated from the inner resolve_active_hub call.
    """
    git_root = _paths.resolve_git_root()
    container_path = _paths.resolve_container_path(git_root)
    hub_dir = _paths.resolve_hub_path()
    cfg = load_config(hub_dir, hub_dir / ".millhouse")
    active_hub = _paths.resolve_active_hub(
        container_path, slug, cfg=cfg, git_root=git_root,
    )
    resolved_tmpl = path_tmpl.replace("<SLUG>", slug)
    return _paths.resolve_task_path(active_hub, resolved_tmpl)


def discover_round(reviews_dir: Path, review_type: str, scope: str) -> int:
    """Scan reviews_dir and return the next round number for (review_type, scope).

    ``scope`` is either ``"holistic"`` (for discussion reviews and plan/code
    holistic reviews) or a batch name string (for per-batch plan/code reviews).

    If ``reviews_dir`` does not exist, return 1.

    Scope semantics:
    - ``scope == "holistic"``: count files where RE_SIMPLE matches AND
      ``m.group("type") == review_type``. RE_BATCH matches are ignored entirely.
    - ``scope == <batch_name>``: count files where RE_SIMPLE does NOT match AND
      RE_BATCH matches AND ``m.group("type") == review_type`` AND
      ``m.group("batch") == scope``.

    RE_SIMPLE is checked before RE_BATCH for every file, matching the existing
    convention that prevents a plan-holistic file (e.g. …-plan-review-r1.md)
    from being mis-identified as a batch review via RE_BATCH.

    Return ``max(found) + 1`` if any matching files exist, else 1.
    """
    if not reviews_dir.exists():
        return 1

    found: list[int] = []
    for entry in reviews_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        m_simple = RE_SIMPLE.match(name)
        if m_simple:
            if scope == "holistic" and m_simple.group("type") == review_type:
                found.append(int(m_simple.group("n")))
            # RE_SIMPLE matched — skip RE_BATCH for this file regardless.
            continue
        # RE_SIMPLE did not match — try RE_BATCH (per-batch scope only).
        if scope != "holistic":
            m_batch = RE_BATCH.match(name)
            if (
                m_batch
                and m_batch.group("type") == review_type
                and m_batch.group("batch") == scope
            ):
                found.append(int(m_batch.group("n")))

    return max(found) + 1 if found else 1


def detect_resume_round(reviews_dir: Path, review_type: str) -> int | None:
    """Return the highest per-batch-only round for review_type, or None.

    Returns the highest round number ``N`` such that at least one per-batch
    review file exists for round ``N`` AND no holistic review file exists for
    round ``N``. Returns ``None`` when no such round exists (either all rounds
    have a holistic file, no per-batch files exist at all, or ``reviews_dir``
    does not exist).

    Uses RE_SIMPLE (checked first per convention) to identify holistic files
    and RE_BATCH to identify per-batch files, both filtered by ``review_type``.

    Consumed by ``_review_plan.run`` to detect a partially-complete run where
    per-batch reviews are done but the holistic pass has not yet fired.
    """
    if not reviews_dir.exists():
        return None

    batch_rounds: set[int] = set()
    holistic_rounds: set[int] = set()

    for entry in reviews_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        m_simple = RE_SIMPLE.match(name)
        if m_simple:
            if m_simple.group("type") == review_type:
                holistic_rounds.add(int(m_simple.group("n")))
            continue
        m_batch = RE_BATCH.match(name)
        if m_batch and m_batch.group("type") == review_type:
            batch_rounds.add(int(m_batch.group("n")))

    candidates = batch_rounds - holistic_rounds
    if not candidates:
        return None
    return max(candidates)


# Regex constants for parse_batch_refs.
# Header line: - **Context:** <inline>  (inline may be empty for multi-line bullet form).
_RE_REFS_HEADER = re.compile(
    r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$"
)
# Sub-bullet under a multi-line header (leading whitespace + dash).
_RE_REFS_SUB = re.compile(r"^\s+-\s*(.+)$")


def parse_batch_refs(batch_path: Path) -> list[str]:
    """Extract raw path strings from a batch file's Context/Edits/Creates/Deletes lines.

    Handles the single-line form (- **Context:** `a`, `b`) and the multi-line
    bullet form (- **Context:**\\n  - `a`\\n  - `b`). Filters tokens whose
    lowercase form equals ``'none'`` (case-insensitive). Returns a
    deduplicated list preserving first-seen order. Used by both plan review
    and code review to build the source-file bulk.
    """
    text = batch_path.read_text(encoding="utf-8")
    seen: dict[str, None] = {}
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        m = _RE_REFS_HEADER.match(lines[i])
        if m:
            inline = m.group("inline").strip()
            if inline:
                backtick_tokens = re.findall(r"`([^`]+)`", inline)
                tokens = backtick_tokens if backtick_tokens else [
                    t.strip() for t in inline.split(",") if t.strip()
                ]
            else:
                tokens = []
                j = i + 1
                while j < len(lines):
                    sm = _RE_REFS_SUB.match(lines[j])
                    if not sm:
                        break
                    rest = sm.group(1).strip()
                    bt = re.findall(r"`([^`]+)`", rest)
                    if bt:
                        tokens.extend(bt)
                    j += 1
            for t in tokens:
                if t.lower() != "none":
                    seen[t] = None
        i += 1

    return list(seen.keys())


def compute_creates_union(plan_dir: Path) -> set[str]:
    """Return the union of all Creates: tokens across every batch in plan_dir.

    Iterates every ``??-*.md`` file under ``plan_dir`` except
    ``00-overview.md``, extracts only the ``Creates:`` lines, and returns
    a flat set of raw token strings (NOT resolved Paths). Filters tokens
    whose lowercase form equals ``'none'`` (case-insensitive). Returns an
    empty set if ``plan_dir`` doesn't exist or contains no batch files.
    """
    if not plan_dir.exists():
        return set()
    creates: set[str] = set()
    for batch_path in sorted(plan_dir.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = _RE_REFS_HEADER.match(lines[i])
            if m and m.group(1) == "Creates":
                inline = m.group("inline").strip()
                if inline:
                    backtick_tokens = re.findall(r"`([^`]+)`", inline)
                    tokens = backtick_tokens if backtick_tokens else [
                        t.strip() for t in inline.split(",") if t.strip()
                    ]
                else:
                    tokens = []
                    j = i + 1
                    while j < len(lines):
                        sm = _RE_REFS_SUB.match(lines[j])
                        if not sm:
                            break
                        rest = sm.group(1).strip()
                        bt = re.findall(r"`([^`]+)`", rest)
                        if bt:
                            tokens.extend(bt)
                        j += 1
                for t in tokens:
                    if t.lower() != "none":
                        creates.add(t)
            i += 1
    return creates


def compute_deletes_union(plan_dir: Path) -> set[str]:
    """Return the union of all Deletes: tokens across every batch in plan_dir.

    Iterates every ``??-*.md`` file under ``plan_dir`` except
    ``00-overview.md``, extracts only the ``Deletes:`` lines, and returns
    a flat set of raw token strings (NOT resolved Paths). Filters tokens
    whose lowercase form equals ``'none'`` (case-insensitive). Returns an
    empty set if ``plan_dir`` doesn't exist or contains no batch files.
    """
    if not plan_dir.exists():
        return set()
    deletes: set[str] = set()
    for batch_path in sorted(plan_dir.glob("??-*.md")):
        if batch_path.name == "00-overview.md":
            continue
        text = batch_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = _RE_REFS_HEADER.match(lines[i])
            if m and m.group(1) == "Deletes":
                inline = m.group("inline").strip()
                if inline:
                    backtick_tokens = re.findall(r"`([^`]+)`", inline)
                    tokens = backtick_tokens if backtick_tokens else [
                        t.strip() for t in inline.split(",") if t.strip()
                    ]
                else:
                    tokens = []
                    j = i + 1
                    while j < len(lines):
                        sm = _RE_REFS_SUB.match(lines[j])
                        if not sm:
                            break
                        rest = sm.group(1).strip()
                        bt = re.findall(r"`([^`]+)`", rest)
                        if bt:
                            tokens.extend(bt)
                        j += 1
                for t in tokens:
                    if t.lower() != "none":
                        deletes.add(t)
            i += 1
    return deletes


def resolve_ref_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
    *,
    creates_union: set[str] | None = None,
    deletes_union: set[str] | None = None,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
    caller_label: str = "resolve_ref_paths",
) -> list[Path]:
    """Resolve batch-reference path strings to absolute ``Path``s.

    ``root`` is the optional filesystem sub-path declared in the plan
    overview's frontmatter ``root:`` field. When present every raw path
    is resolved under ``project_root / root``; otherwise directly under
    ``project_root``.

    Resolution order (first match wins):
    1. wiki/ prefix routes through wiki_root (unchanged).
    2. Candidate path under project_root (unchanged).
    3. Candidate path under git_root (when provided).
    4. creates_union/deletes_union suppression (unchanged).
    5. Hard-fail ReviewError (unchanged).

    Keyword args:
        creates_union: Set of raw token strings extracted from ``Creates:``
            lines across all batches. A path not on disk but present in
            ``creates_union`` is silently skipped — the file will exist
            after the creating batch runs (#60).
        deletes_union: Set of raw token strings extracted from ``Deletes:``
            lines across all batches. A path not on disk but present in
            ``deletes_union`` is silently skipped — the file has already
            been deleted by a prior batch. Paths still on disk that appear
            in ``deletes_union`` are resolved normally and included.
        wiki_root: When provided, raw paths starting with ``wiki/`` are
            resolved against ``wiki_root`` instead of ``project_root`` (#43).
        git_root: When provided, paths not found under project_root are
            tried under git_root as a fallback before suppression/hard-fail.
        caller_label: Prefix used in ``ReviewError`` messages. Defaults to
            the function name.

    Raises ``ReviewError`` when a candidate path is not on disk AND not in
    either ``creates_union`` or ``deletes_union`` — hard-fail replaces the
    old silent-skip + warning behaviour (#41).
    """
    creates = creates_union or set()
    deletes = deletes_union or set()
    resolved: list[Path] = []
    for raw in raw_paths:
        # Defensive None/none filter — must run before any string operations.
        if raw is None or (isinstance(raw, str) and raw.lower() == "none"):
            continue
        # Wiki-path resolution.
        if raw.startswith("wiki/"):
            if wiki_root is None:
                raise ReviewError(
                    f"[{caller_label}] wiki-prefixed ref {raw!r} but no wiki_root provided"
                )
            candidate = wiki_root / raw[len("wiki/"):]
        elif root:
            candidate = project_root / root / raw
        else:
            candidate = project_root / raw
        # Hit on disk.
        if candidate.exists():
            resolved.append(candidate)
            continue
        # Git-root fallback (only for non-wiki paths).
        if not raw.startswith("wiki/") and git_root is not None:
            gr_candidate = git_root / raw
            if gr_candidate.exists():
                resolved.append(gr_candidate)
                continue
        # Suppression via creates_union or deletes_union.
        if raw in creates or raw in deletes:
            continue
        # Hard-fail.
        raise ReviewError(
            f"[{caller_label}] referenced path not found: {raw!r}; "
            f"not in plan creates_union, not on disk; resolved candidate: {candidate}"
        )
    return resolved


def resolve_existing_paths(
    raw_paths: list[str],
    project_root: Path,
    root: str | None,
    *,
    wiki_root: Path | None = None,
    git_root: Path | None = None,
) -> list[Path]:
    """Resolve raw paths and return only those that already exist on disk.

    Mirrors resolve_ref_paths's standard-vs-wiki routing (wiki/ prefix
    routes through wiki_root; otherwise project_root + root) plus optional
    git_root fallback. Unlike resolve_ref_paths, missing paths and routing
    failures are silently dropped — no warning, no error, no creates_union
    check. Used to expand the bulk with cross-batch ancestor creates that
    already exist; missing creates are not an error here, they just aren't
    included.

    Resolution order (first match wins):
    1. wiki/ prefix routes through wiki_root (unchanged).
    2. Candidate path under project_root (unchanged).
    3. Candidate path under git_root (when provided).
    4. Silent drop (no raise).

    Keyword args:
        wiki_root: When provided, raw paths starting with ``wiki/`` are
            resolved against ``wiki_root`` instead of ``project_root``.
        git_root: When provided, paths not found under project_root are
            tried under git_root as a fallback before silent drop.
    """
    result: list[Path] = []
    for raw in raw_paths:
        # Defensive None/none filter — same as resolve_ref_paths.
        if raw is None or (isinstance(raw, str) and raw.lower() == "none"):
            continue
        # Wiki-path routing.
        if raw.startswith("wiki/"):
            if wiki_root is None:
                # Key divergence from resolve_ref_paths: silent drop instead of raise.
                continue
            candidate = wiki_root / raw[len("wiki/"):]
        elif root:
            candidate = project_root / root / raw
        else:
            candidate = project_root / raw
        if candidate.exists():
            result.append(candidate)
            continue
        # Git-root fallback (only for non-wiki paths).
        if not raw.startswith("wiki/") and git_root is not None:
            gr_candidate = git_root / raw
            if gr_candidate.exists():
                result.append(gr_candidate)
                continue
    return result


def _load_root_from_overview(overview_path: Path) -> str | None:
    """Read the `root:` field from the overview's top fenced-yaml block.

    v2 plan overviews use fenced ```yaml``` frontmatter (per the
    project markdown convention; `---` is reserved for SKILL.md). This
    parser locates the first ```yaml``` block and reads `root:` from
    it. Returns the root string if present and truthy, else None.
    Any structural problem (no block, unterminated, bad yaml, absent
    key) silently yields None — the review surface degrades to
    resolving paths against project_root directly, which is the right
    behaviour for a mill-v2 worktree where root is typically empty.
    """
    try:
        text = overview_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "```yaml":
            start = i + 1
            break
    if start is None:
        return None
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "```":
            end = j
            break
    if end is None:
        return None

    fm_text = "\n".join(lines[start:end])
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data.get("root") or None


def _read_for_bulk(p: Path) -> str:
    """Read file content, handling .ipynb notebooks specially.

    For .ipynb files: reads as JSON, extracts cell source for 'code' and
    'markdown' cell types, joins sources with blank lines between cells.
    For other extensions: returns standard UTF-8 text read.

    On JSON parse error for .ipynb: prints warning to stderr and returns
    empty string so the file still appears in bulk output as an empty section.

    If p is a directory: prints warning to stderr and returns empty string.
    """
    if p.is_dir():
        print(f"[_read_for_bulk] warning: {p} is a directory, skipping", file=sys.stderr)
        return ""

    if p.suffix == ".ipynb":
        try:
            content = p.read_text(encoding="utf-8")
            notebook = json.loads(content)
        except json.JSONDecodeError as exc:
            print(f"[_read_for_bulk] warning: {p} JSON parse error: {exc}", file=sys.stderr)
            return ""

        cells = notebook.get("cells", [])
        sources: list[str] = []
        for cell in cells:
            cell_type = cell.get("cell_type")
            if cell_type not in ("code", "markdown"):
                continue
            source = cell.get("source", "")
            if isinstance(source, list):
                sources.append("".join(source))
            else:
                sources.append(str(source))
        return "\n\n".join(sources)
    else:
        return p.read_text(encoding="utf-8", errors="replace")


def bulk_files(file_paths: list[Path]) -> str:
    """Concatenate file contents with '--- FILE: <path> ---' delimiters.

    Paths that do not exist are skipped with a stderr warning.
    """
    parts: list[str] = []
    for p in file_paths:
        try:
            contents = _read_for_bulk(p)
        except (FileNotFoundError, PermissionError):
            print(f"[bulk_files] warning: {p} not found or not readable, skipping", file=sys.stderr)
            continue
        parts.append(f"--- FILE: {p} ---\n{contents}\n--- END FILE: {p} ---")
    return "\n\n".join(parts)


def bulk_files_with_diff(
    file_paths: list[Path],
    start_sha: str,
    project_root: Path,
    threshold: float,
) -> str:
    """Like bulk_files but substitutes git diff output for small-diff files.

    For each file: if the diff from start_sha to HEAD is smaller than
    threshold * file_content_size, include the diff instead of full content.
    Files with no diff (unchanged between start_sha and HEAD) are included
    at full content so the reviewer has all context.
    """
    parts: list[str] = []
    for p in file_paths:
        try:
            file_content = _read_for_bulk(p)
        except (FileNotFoundError, PermissionError):
            print(f"[bulk_files_with_diff] warning: {p} not found or not readable, skipping", file=sys.stderr)
            continue

        try:
            rel_path = p.relative_to(project_root).as_posix()
        except ValueError:
            rel_path = str(p)

        result = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff", f"{start_sha}..HEAD", "--", rel_path],
        )

        if result.returncode != 0:
            print(
                f"[bulk_files_with_diff] warning: git diff failed for {p} (returncode={result.returncode}), using full file",
                file=sys.stderr,
            )
            parts.append(f"--- FILE: {p} ---\n{file_content}\n--- END FILE: {p} ---")
            continue

        diff_text = result.stdout

        if not diff_text:
            parts.append(f"--- FILE: {p} ---\n{file_content}\n--- END FILE: {p} ---")
            continue

        if len(diff_text) < threshold * len(file_content):
            parts.append(f"--- DIFF: {p} (from {start_sha[:8]}) ---\n{diff_text}\n--- END DIFF: {p} ---")
            continue

        parts.append(f"--- FILE: {p} ---\n{file_content}\n--- END FILE: {p} ---")

    return "\n\n".join(parts)


def build_manifest_section(file_paths: list[Path]) -> str:
    """Return a `## Files included` markdown block listing every bulked file.

    Output shape (no trailing newline):

        ## Files included (N=<count>)

        - <path-1>
        - <path-2>
        ...

    The manifest is the FIRST thing the reviewer reads inside the
    artefact section. Its job is to remove the long-context
    haystack effect: the reviewer scans this list, then can answer
    "is file X provided?" in O(1) instead of scanning a 200k-char
    bulk for the matching `--- FILE: X ---` delimiter.
    """
    if not file_paths:
        return "## Files included (N=0)\n\n(no files)"
    count = len(file_paths)
    bullets = "\n".join(f"- {p}" for p in file_paths)
    return f"## Files included (N={count})\n\n{bullets}"


def build_deletes_section(deletes_tokens: list[str]) -> str:
    """Return a `## Intentionally deleted` markdown block listing deleted tokens.

    Output shape (no trailing newline):

        ## Intentionally deleted (N=<count>)

        - <token-1>
        - <token-2>
        ...

    Empty list returns the empty string so callers can splice unconditionally.
    Tokens are emitted as-is — no backtick wrapping is added by this helper.
    """
    if not deletes_tokens:
        return ""
    count = len(deletes_tokens)
    bullets = "\n".join(f"- {t}" for t in deletes_tokens)
    return f"## Intentionally deleted (N={count})\n\n{bullets}"


_RE_MISSING_CONTEXT_BULLET = re.compile(r"^\s*-\s+`([^`]+)`")

_REVIEW_BEGIN = "MILL_REVIEW_BEGIN"
_REVIEW_END = "MILL_REVIEW_END"


def extract_review_content(raw: str) -> str:
    """Strip everything outside MILL_REVIEW_BEGIN / MILL_REVIEW_END markers.

    Falls back to raw unchanged when markers are absent (e.g. test stubs).
    """
    begin = raw.find(_REVIEW_BEGIN)
    if begin == -1:
        return raw
    end = raw.find(_REVIEW_END, begin + len(_REVIEW_BEGIN))
    if end == -1:
        return raw
    return raw[begin + len(_REVIEW_BEGIN):end].strip()


def parse_missing_context(review_text: str) -> list[str]:
    """Extract path strings from a `## Missing context` section.

    The reviewer's NEED_CONTEXT output uses the convention:

        ## Missing context

        - `path/a` — reason text
        - `path/b` — reason text

    Returns the list of raw path tokens (NOT resolved Paths). Empty
    list if the heading is absent or no bullet matches the expected
    shape. Multi-line bullets are not supported — paths must appear
    backtick-wrapped on their own bullet line.
    """
    lines = review_text.splitlines()
    in_section = False
    paths: list[str] = []
    for line in lines:
        if not in_section:
            if line.startswith("## Missing context"):
                in_section = True
            continue
        # Stop at the next ## heading.
        if line.startswith("## "):
            break
        m = _RE_MISSING_CONTEXT_BULLET.match(line)
        if m:
            token = m.group(1)
            if token.lower() != "none":
                paths.append(token)
    return paths


def build_reattached_section(file_paths: list[Path]) -> str:
    """Return a `## Re-attached files (you said these were missing)` block
    with the listed files inlined via bulk_files.

    Used by the NEED_CONTEXT resume retry: the missing-context paths
    from the prior round are re-attached at the top of the new prompt
    so the reviewer cannot claim absence again without contradicting
    itself. The section is appended to the existing artefact section.
    """
    if not file_paths:
        return ""
    return (
        "## Re-attached files (you said these were missing)\n\n"
        + bulk_files(file_paths)
    )


_TOOL_RULE_BULK = (
    "**CRITICAL: Do NOT request tool calls. All content you need is in this prompt.**\n"
    "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
    "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**\n"
    "**CRITICAL: Do NOT use Write. Return review as text.**"
)

_TOOL_RULE_TOOL_USE = (
    "**You MAY use Read, Grep, and Glob to verify claims against source files.**\n"
    "**CRITICAL: Do NOT use Write, Edit, or run git/bash. Return review as text.**\n"
    "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
    "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**"
)


def build_tool_rule(mode: str) -> str:
    """Return the <TOOL_RULE> block for a reviewer's MODE.

    Templates embed this as the top-of-prompt directive. In bulk mode the
    reviewer is told all content is inline; in tool-use mode it is granted
    Read/Grep/Glob. Write, Edit, and shell access are forbidden in both modes
    — the backend owns file writes and git.
    """
    if mode == "bulk":
        return _TOOL_RULE_BULK
    if mode == "tool-use":
        return _TOOL_RULE_TOOL_USE
    raise ValueError(f"Unknown reviewer mode: {mode!r} (expected 'bulk' or 'tool-use')")


def _check_large_prompt(
    prompt_text: str,
    cfg: dict,
    role: str,
    scope: str,
) -> tuple[bool, int]:
    """Check if prompt exceeds large_prompt threshold.

    Returns (is_over_threshold, estimated_ktok) where estimated_ktok is computed as
    len(prompt_text) // 4000 and threshold_ktok is read from
    cfg["roles"][role][scope]["large_prompt"]["threshold_ktok"] (default 100).
    """
    large_prompt_cfg = cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
    if not large_prompt_cfg:
        return (False, len(prompt_text) // 4000)
    threshold_ktok = large_prompt_cfg.get("threshold_ktok", 100)
    estimated_ktok = len(prompt_text) // 4000
    is_over_threshold = estimated_ktok >= threshold_ktok
    return (is_over_threshold, estimated_ktok)


def resolve_large_prompt_timeout(
    prompt_text: str,
    cfg: dict,
    role: str,
    scope: str,
    default_timeout: int,
) -> int:
    """Return large_prompt.timeout when prompt is over threshold and key is set, else default_timeout.

    Uses _check_large_prompt to compute size check; returns the override value from
    cfg["roles"][role][scope]["large_prompt"]["timeout"] if the prompt exceeds the
    threshold and the timeout key is set, otherwise returns default_timeout.
    """
    is_over_threshold, _ = _check_large_prompt(prompt_text, cfg, role, scope)
    if not is_over_threshold:
        return default_timeout
    large_prompt_cfg = cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
    if not large_prompt_cfg:
        return default_timeout
    override_timeout = large_prompt_cfg.get("timeout")
    if override_timeout is None:
        return default_timeout
    return override_timeout


def maybe_switch_spec_for_large_prompt(
    prompt_text: str,
    spec: dict,
    reviewer_name: str,
    cfg: dict,
    role: str,
    scope: str,
    registry: dict,
) -> tuple[dict, str]:
    """Check prompt size; return (spec, reviewer_name), possibly overridden for large prompts."""
    is_over_threshold, estimated_ktok = _check_large_prompt(prompt_text, cfg, role, scope)
    large_prompt_cfg = cfg.get("roles", {}).get(role, {}).get(scope, {}).get("large_prompt")
    if not large_prompt_cfg or not is_over_threshold:
        return (spec, reviewer_name)
    override_name = large_prompt_cfg.get("reviewer")
    if override_name is None:
        return (spec, reviewer_name)
    override_spec = _reviewers.resolve(registry, override_name)
    if override_spec.get("type") == "cluster":
        raise ReviewError(
            f"large_prompt.reviewer {override_name!r} is cluster type; "
            "only single reviewers are supported for large-prompt switch"
        )
    effective_spec = dict(override_spec)
    original_tooluse = spec.get("tooluse", False)
    if effective_spec.get("tooluse", False) != original_tooluse:
        print(
            f"[_review_common] large-prompt switch: override {override_name!r} tooluse differs; "
            f"preserving original tooluse={original_tooluse}",
            file=sys.stderr,
        )
        effective_spec["tooluse"] = original_tooluse
    print(
        f"[_review_common] large-prompt switch: estimated ~{estimated_ktok}k tok, "
        f"switching reviewer {reviewer_name!r} -> {override_name!r}",
        file=sys.stderr,
    )
    return (effective_spec, override_name)


def render_prompt(template_name: str, **tokens) -> str:
    """Render a review prompt template from plugins/mill/templates/.

    Auto-uppercases keyword-argument keys so callers can use idiomatic
    Python kwarg style (e.g. artefact_path="..." becomes ARTEFACT_PATH).

    Template path:
        <scripts_dir>/../templates/<template_name>.md

    Raises FileNotFoundError if the template is absent.
    Lets KeyError from _render.render() propagate unwrapped — a missing token
    is a programming error, not a user error.
    """
    templates_dir = Path(__file__).parent.parent / "templates"
    template_path = templates_dir / f"{template_name}.md"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    uppercased = {k.upper(): str(v) for k, v in tokens.items()}
    return _render.render(template_path, uppercased)


def parse_verdict(raw_output: str) -> str:
    """Extract a valid verdict value from a fenced yaml block, or unfenced fallback.

    Scans raw_output for the first fenced ```yaml block (on its own line,
    possibly with trailing whitespace). Extracts the 'verdict:' field from
    inside the block (between the opening ```yaml and closing ``` fences).

    If no fenced block is found, attempts a fallback: scans lines for an
    unfenced 'verdict: <VALUE>' line (allowing leading whitespace; strips quotes).
    If <VALUE> is one of the valid verdicts, returns it.

    Valid verdict values:
    - 'APPROVE'          — any review type
    - 'REQUEST_CHANGES'  — plan and code review
    - 'GAPS_FOUND'       — discussion review (v1 convention; a missing
                           criterion is not a must-fix defect)
    - 'NEED_CONTEXT'     — plan and code review only; reviewer cannot
                           evaluate without source files that were not
                           included in the bulk. Orchestrator responds by
                           re-firing with `--extra-file` plus a notify +
                           self-report entry.

    Raises ReviewError if:
    - No ```yaml opening fence is found AND no unfenced verdict line is found.
    - The yaml block is not closed by a ``` line.
    - The 'verdict:' field is absent from the block.
    - The verdict value is not one of the four above.

    The first ~400 chars of raw_output are included in error messages for
    debuggability.
    """
    preview = raw_output[:400].strip()
    lines = raw_output.splitlines()

    # Find the first ```yaml opening fence.
    open_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == "```yaml":
            open_idx = i
            break

    if open_idx is not None:
        # Find the closing ``` fence after the opening.
        close_idx = None
        for i, line in enumerate(lines[open_idx + 1:], start=open_idx + 1):
            if line.rstrip() == "```":
                close_idx = i
                break

        if close_idx is None:
            raise ReviewError(
                f"Could not parse verdict: ```yaml block not closed.\n"
                f"Raw output preview:\n{preview}"
            )

        # Scan block body for verdict: field.
        for line in lines[open_idx + 1:close_idx]:
            stripped = line.strip()
            if stripped.startswith("verdict:"):
                value = stripped[len("verdict:"):].strip().strip('"').strip("'")
                if value in ("APPROVE", "REQUEST_CHANGES", "GAPS_FOUND", "NEED_CONTEXT"):
                    return value
                raise ReviewError(
                    f"Could not parse verdict: invalid value {value!r}; "
                    f"expected APPROVE, REQUEST_CHANGES, GAPS_FOUND, or NEED_CONTEXT.\n"
                    f"Raw output preview:\n{preview}"
                )

        raise ReviewError(
            f"Could not parse verdict: 'verdict:' key not found in ```yaml block.\n"
            f"Raw output preview:\n{preview}"
        )

    # Fallback: scan for unfenced verdict line.
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("verdict:"):
            value = stripped[len("verdict:"):].strip().strip('"').strip("'")
            if value in ("APPROVE", "REQUEST_CHANGES", "GAPS_FOUND", "NEED_CONTEXT"):
                return value

    raise ReviewError(
        f"Could not parse verdict: no ```yaml block found and no unfenced verdict line found.\n"
        f"Raw output preview:\n{preview}"
    )


def _warn_if_prose_diverges(raw_output: str, severity: str, heading_count: int) -> None:
    _WORD_TO_INT = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    pattern = re.compile(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+" + re.escape(severity),
        re.IGNORECASE,
    )
    matches = pattern.findall(raw_output)
    if not matches:
        return
    raw_val = matches[0]
    prose_count = int(raw_val) if raw_val.isdigit() else _WORD_TO_INT.get(raw_val.lower(), -1)
    if prose_count != heading_count:
        print(
            f"[_review_common] warning: parse_blocking_count heading count {heading_count} "
            f"diverges from prose count {prose_count} (severity={severity}) "
            f"— check review file for missing heading.",
            file=sys.stderr,
        )


def parse_blocking_count(raw_output: str, *, severity: str) -> int:
    """Count "### [<severity>]" ATX headings in review output.

    Searches for lines matching ``^###\\s+\\[<severity>\\]\\s+`` using
    MULTILINE mode. The severity argument is required (keyword-only).
    Match is case-sensitive. Only line-start headings are counted —
    mid-line occurrences are ignored.

    Emits a one-line stderr warning when a prose count phrase in the output
    (e.g. "Five blocking issues remain") disagrees with the heading count.
    The returned count is unchanged; the warning is for log inspection only (#225).
    """
    pattern = re.compile(
        r"^###\s+\[" + re.escape(severity) + r"\]\s+",
        re.MULTILINE,
    )
    heading_count = len(pattern.findall(raw_output))
    _warn_if_prose_diverges(raw_output, severity, heading_count)
    return heading_count


def write_review_file(
    reviews_dir: Path,
    review_type: str,
    round_num: int,
    content: str,
    scope: str | None = None,
) -> Path:
    """Build a canonical review filename, create dirs, write content, return path.

    Filename rules:
    - Discussion / code / plan-holistic:
        <ts>-<type>-review-r<N>.md
    - Plan per-batch (scope is a batch name, e.g. '01-setup'):
        <ts>-plan-review-<scope>-r<N>.md
    - Plan holistic (scope == 'holistic'):
        <ts>-plan-review-r<N>.md

    Timestamp is UTC, formatted as YYYYMMDD-HHMMSS.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if (
        review_type in ("plan", "code")
        and scope is not None
        and scope != "holistic"
    ):
        filename = f"{ts}-{review_type}-review-{scope}-r{round_num}.md"
    else:
        filename = f"{ts}-{review_type}-review-r{round_num}.md"

    reviews_dir.mkdir(parents=True, exist_ok=True)
    out_path = reviews_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path.resolve()


def finalize_scope(
    reviews_dir: Path,
    review_type: str,
    round_n: int,
    raw_text: str,
    *,
    scope: str | None = None,
) -> dict:
    """Finalize a single review scope by parsing verdict and writing the review file.

    Runs parse_verdict, then write_review_file, and returns a dict
    with the review entry plus blocking/nit counts for ReviewResult assembly.

    Args:
        reviews_dir: Directory where review files are stored.
        review_type: Type of review ("discussion", "code", or "plan").
        round_n: Round number (integer).
        raw_text: Raw review output text to parse and write.
        scope: Optional scope name ("holistic" or batch name); if None defaults to "holistic".

    Returns:
        Dict with keys: scope, verdict, file, blocking_count, nit_count.

    Raises:
        ReviewError: from parse_verdict if verdict cannot be extracted.
    """
    verdict = parse_verdict(raw_text)
    review_path = write_review_file(
        reviews_dir, review_type, round_n, raw_text, scope=scope
    )
    # Severity labels are per-review-type: discussion uses GAP/NOTE; plan and
    # code use BLOCKING/NIT. The old inline finalize paths counted the matching
    # type-specific label, so finalize_scope must mirror that mapping rather
    # than a single hardcoded severity.
    if review_type == "discussion":
        blocking_severity, nit_severity = "GAP", "NOTE"
    else:
        blocking_severity, nit_severity = "BLOCKING", "NIT"
    blocking_count = parse_blocking_count(raw_text, severity=blocking_severity)
    nit_count = parse_blocking_count(raw_text, severity=nit_severity)

    effective_scope = scope if scope else "holistic"

    return {
        "scope": effective_scope,
        "verdict": verdict,
        "file": str(review_path),
        "blocking_count": blocking_count,
        "nit_count": nit_count,
    }


# ---------------------------------------------------------------------------
# Dispatch helpers and config loader (Step 8 additions)
# ---------------------------------------------------------------------------

def aggregate_verdict(sub_verdicts: list[str]) -> str:
    """Return the worst-case aggregate verdict across sub-verdicts.

    Rules:
    - Any NEED_CONTEXT propagates up to the aggregate (orchestrator must
      resolve the missing-context request before it can act on any
      REQUEST_CHANGES finding, so NEED_CONTEXT takes priority).
    - Any REQUEST_CHANGES or ERROR escalates the aggregate to REQUEST_CHANGES.
    - All APPROVE → APPROVE.
    - ERROR appears only inside reviews[] entries; aggregate is never ERROR.
    """
    if "NEED_CONTEXT" in sub_verdicts:
        return "NEED_CONTEXT"
    for v in sub_verdicts:
        if v in ("REQUEST_CHANGES", "ERROR"):
            return "REQUEST_CHANGES"
    return "APPROVE"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflict."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        elif val is None and isinstance(result.get(key), dict):
            continue
        else:
            result[key] = val
    return result


def load_config(hub_root: Path, mill_dir: Path) -> dict:
    """Load mill config with overlay from plugin template, repo layer, and local layer.

    Merge order (lowest to highest precedence):
    1. Plugin template (mill-config.yaml)
    2. Hub layer (mill-config.yaml at hub root)
    3. Local layer (mill_dir / config.local.yaml)
    4. Environment variable overrides

    Raises ReviewError if no sources are found (strict form for reviews).

    Args:
        hub_root: Absolute path to the hub directory.
        mill_dir: Absolute path to the .millhouse directory.

    Returns:
        Merged configuration dict.
    """
    # 1. Load plugin template
    template_path = resolve_plugin_template_path("mill-config.yaml")
    if template_path.exists():
        with template_path.open(encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
    else:
        cfg = {}
    template_cfg = copy.deepcopy(cfg)

    # 2. Resolve hub-layer sources
    mill_cfg_path = _paths.resolve_mill_config_path(hub_root)

    # 3. Apply repo-layer merge logic
    found_repo_layer = False
    if mill_cfg_path.exists():
        with mill_cfg_path.open(encoding="utf-8") as fh:
            repo_cfg = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, repo_cfg)
        found_repo_layer = True

    # 4. Strict-missing semantics: require at least one source
    if not template_path.exists() and not found_repo_layer:
        raise ReviewError(
            f"Missing config: searched plugin template at {template_path} "
            f"and mill-config.yaml at {mill_cfg_path}"
        )

    # 5. Deep-merge the local layer
    local_path = mill_dir / "config.local.yaml"
    if local_path.exists():
        with local_path.open(encoding="utf-8") as fh:
            local_cfg = yaml.safe_load(fh) or {}
        stale_review = local_cfg.get("review")
        if stale_review:
            orphaned = sorted(stale_review.keys())
            print(
                f"[load_config] warning: {local_path} contains stale 'review:' keys "
                f"(orphaned: {orphaned}); remove them or update to 'roles:'",
                file=sys.stderr,
            )
        cfg = _deep_merge(cfg, local_cfg)

    # 6. Validate unknown keys
    check_cfg = {k: v for k, v in cfg.items() if k != "hub_relative_path"}
    warn_unknown_keys(check_cfg, template_cfg, "merged config")

    # 7. Apply environment overrides
    cfg = apply_env_overrides(cfg)

    # 8. Apply dispatch enum back-compat shim for legacy via_psmux
    _apply_dispatch_shim(cfg)

    return cfg


--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_review_common.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_reviewer_single.py ---
"""
Single-reviewer dispatcher.

Takes a fully-flattened reviewer spec (as returned by _reviewers.resolve) and
dispatches to the appropriate _llm_<provider> module. The spec carries all
dispatch information — provider, model, effort, tooluse — so no per-call
overrides are needed or accepted.

Spec contract:
    {
        "type": "single",
        "provider": "<name>",   # e.g. "claude"; drives importlib.import_module("_llm_<provider>")
        "model": "<model-id>",
        "effort": "<effort>",   # optional; passed verbatim to the LLM provider
        "tooluse": bool,        # false → run_bulk; true → run_tool_use
    }

Cluster specs are detected and raise ReviewerError immediately — cluster dispatch
is deferred to task 13.
"""
from __future__ import annotations

import importlib


def run(
    spec: dict,
    prompt_text: str,
    *,
    session_id: str | None = None,
    resume: bool = False,
    timeout: int | None = None,
) -> tuple[str, str]:
    """Dispatch a single-reviewer call via spec.

    Reads spec["provider"] and spec["tooluse"] to select the LLM function.
    Forwards session_id, resume, and (when not None) timeout to the provider.

    Raises:
        ReviewerError: when spec.type == "cluster", provider is unknown, or
            the provider module cannot be imported.
    """
    if spec["type"] == "cluster":
        from _reviewers import ReviewerError
        raise ReviewerError("cluster dispatch not yet implemented; see task 13")

    provider = spec.get("provider")

    if provider == "test_stub":
        import _reviewer_test_stub as stub
        return stub.run(prompt_text, session_id=session_id, resume=resume, timeout=timeout)

    try:
        llm = importlib.import_module(f"_llm_{provider}")
    except ImportError:
        from _reviewers import ReviewerError
        raise ReviewerError(f"Unknown provider: {provider!r}")

    fn = llm.run_tool_use if spec.get("tooluse") else llm.run_bulk

    kwargs: dict = {
        "model": spec["model"],
        "effort": spec.get("effort"),
        "session_id": session_id,
        "resume": resume,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout

    return fn(prompt_text, **kwargs)

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\scripts\_reviewer_single.py ---

--- FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-review-common.py ---
"""Unit tests for plugins/mill/scripts/_review_common.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_UNIT_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_UNIT_TESTS))

import _test_helpers  # noqa: E402
from _test_helpers import _make_task_worktree  # noqa: E402
from _paths import ActiveWorktreeSlugMismatch  # noqa: E402
import _marker  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helper for resolve_path tests
# ---------------------------------------------------------------------------


def _make_worktree_fixture(tmp: str, slug: str) -> tuple[Path, Path]:
    """Create a container-form git fixture at ``<tmp>/container/wts/<slug>``.

    Layout:
        <tmp>/container/wts/<slug>/  ← git repo on task branch ``hanf/<slug>``
        <tmp>/container/wiki/        ← wiki with Home.md and config.yaml

    Returns:
        ``(container_path, worktree_path)``

    The caller must ``os.chdir(worktree_path)`` so that ``Path.cwd()`` resolves
    inside the fixture when calling ``resolve_path``.
    """
    container = Path(tmp) / "container"
    worktree = container / "wts" / slug
    worktree.mkdir(parents=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    (worktree / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(worktree), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "checkout", "-b", f"hanf/{slug}"],
        check=True, capture_output=True,
    )
    (worktree / "mill-config.yaml").write_text(
        "paths:\n  discussion_file: discussion.md\n"
        "spawn:\n  branch_prefix: \"hanf/\"\n",
        encoding="utf-8",
    )
    wiki_root = container / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "config.yaml").write_text(
        "paths:\n  discussion_file: task/discussion.md\n"
        "spawn:\n  branch_prefix: \"hanf/\"\n",
        encoding="utf-8",
    )
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[[{slug}]] [active]\n\n_body_\n",
        encoding="utf-8",
    )
    return container, worktree


def _make_run_result(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    result.stderr = stderr
    return result


from _review_common import (  # noqa: E402
    RE_BATCH,
    RE_SIMPLE,
    ReviewError,
    ReviewResult,
    _load_root_from_overview,
    _read_for_bulk,
    aggregate_verdict,
    build_deletes_section,
    build_manifest_section,
    build_reattached_section,
    build_tool_rule,
    bulk_files,
    bulk_files_with_diff,
    compute_creates_union,
    compute_deletes_union,
    detect_resume_round,
    discover_round,
    find_active_slug,
    load_config,
    load_task_title,
    parse_batch_refs,
    parse_blocking_count,
    parse_missing_context,
    parse_verdict,
    render_prompt,
    resolve_existing_paths,
    resolve_large_prompt_timeout,
    resolve_path,
    resolve_ref_paths,
    write_review_file,
)

import _review_code  # noqa: E402


def main() -> int:
    errors = 0

    # discover_round: nonexistent dir -> 1
    assert discover_round(Path("/tmp/__nx_reviews__"), "discussion", "holistic") == 1
    print("PASS: discover_round nonexistent dir returns 1")

    # RE_SIMPLE matches holistic plan file; RE_BATCH is NOT applied
    holistic_name = "20260418-001200-plan-review-r1.md"
    m = RE_SIMPLE.match(holistic_name)
    assert m is not None
    assert m.group("type") == "plan"
    assert m.group("n") == "1"
    _ = RE_BATCH.match(holistic_name)  # noqa: F841 — documented ambiguity
    print("PASS: RE_SIMPLE matches plan-holistic before RE_BATCH could mis-identify")

    # discover_round cross-type isolation
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r2.md").write_text("x")
        assert discover_round(reviews, "discussion", "holistic") == 1
        print("PASS: discover_round cross-type isolation (plan-batch ignored for discussion)")
        result = discover_round(reviews, "plan", "01-setup")
        assert result == 3, f"expected 3, got {result}"
        print(f"PASS: discover_round for plan with batch file: {result}")
        assert discover_round(reviews, "plan", "holistic") == 1
        print("PASS: discover_round plan holistic unaffected by batch file")
        assert discover_round(reviews, "plan", "other-batch") == 1
        print("PASS: discover_round plan other-batch unaffected by 01-setup file")

    # discover_round per-scope isolation across all five (review_type, scope) axes
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        # discussion holistic: 2 files
        (reviews / "20260418-001200-discussion-review-r1.md").write_text("x")
        (reviews / "20260418-001300-discussion-review-r2.md").write_text("x")
        # plan holistic: 1 file
        (reviews / "20260418-001400-plan-review-r1.md").write_text("x")
        # plan batch-a: 2 files
        (reviews / "20260418-001500-plan-review-batch-a-r1.md").write_text("x")
        (reviews / "20260418-001600-plan-review-batch-a-r2.md").write_text("x")
        # plan batch-b: 1 file
        (reviews / "20260418-001700-plan-review-batch-b-r1.md").write_text("x")
        # code holistic: 1 file
        (reviews / "20260418-001800-code-review-r1.md").write_text("x")
        # code batch-a: 1 file
        (reviews / "20260418-001900-code-review-batch-a-r1.md").write_text("x")

        result = discover_round(reviews, "discussion", "holistic")
        assert result == 3, f"expected 3, got {result}"
        print(f"PASS: discover_round per-scope discussion/holistic: {result}")

        result = discover_round(reviews, "plan", "holistic")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope plan/holistic: {result}")

        result = discover_round(reviews, "plan", "batch-a")
        assert result == 3, f"expected 3, got {result}"
        print(f"PASS: discover_round per-scope plan/batch-a: {result}")

        result = discover_round(reviews, "plan", "batch-b")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope plan/batch-b: {result}")

        result = discover_round(reviews, "plan", "batch-c")
        assert result == 1, f"expected 1, got {result}"
        print(f"PASS: discover_round per-scope plan/batch-c (absent): {result}")

        result = discover_round(reviews, "code", "holistic")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/holistic: {result}")

        result = discover_round(reviews, "code", "batch-a")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/batch-a: {result}")

        result = discover_round(reviews, "code", "batch-b")
        assert result == 1, f"expected 1, got {result}"
        print(f"PASS: discover_round per-scope code/batch-b (absent for code): {result}")

    # find_active_slug: not on a task branch -> MarkerError re-raised as ReviewError
    with _test_helpers.safe_temp_dir() as tmpdir:
        wt, wiki = _make_task_worktree(Path(tmpdir) / "sub", "some-task", "Some Task", branch_prefix="hanf/")
        subprocess.run(["git", "-C", str(wt), "checkout", "main"], check=True, capture_output=True)
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        try:
            find_active_slug(wt, wiki, cfg)
            print("FAIL: find_active_slug: expected ReviewError on non-task branch", file=sys.stderr)
            errors += 1
        except ReviewError:
            print("PASS: find_active_slug non-task branch -> ReviewError (MarkerError translation)")

    # find_active_slug: on task branch -> returns slug
    with _test_helpers.safe_temp_dir() as tmpdir:
        wt, wiki = _make_task_worktree(Path(tmpdir), "my-task", "My Task", branch_prefix="hanf/", seed_task=True)
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        assert find_active_slug(wt, wiki, cfg) == "my-task"
        print("PASS: find_active_slug: 'my-task'")

    # load_task_title: task_title present in Home.md
    with _test_helpers.safe_temp_dir() as tmpdir:
        wt, wiki = _make_task_worktree(Path(tmpdir), "my-task", "My Task Title", branch_prefix="hanf/", seed_task=True)
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        assert load_task_title(wt, wiki, cfg, "my-task") == "My Task Title"
        print("PASS: load_task_title with task_title in Home.md")

    # load_task_title: non-task branch -> falls back to slug
    with _test_helpers.safe_temp_dir() as tmpdir:
        assert load_task_title(Path(tmpdir), Path(tmpdir), {}, "my-task") == "my-task"
        print("PASS: load_task_title non-task branch -> fallback to slug")

    # resolve_path: discussion.md -> worktree root
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            p = resolve_path("discussion.md", slug)
        finally:
            os.chdir(original_cwd)
        expected = worktree / "discussion.md"
        assert p == expected, f"Expected {expected}, got {p}"
        print("PASS: resolve_path('discussion.md', slug) -> worktree/discussion.md")

    # resolve_path: plan/ and reviews/ templates
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            p_plan = resolve_path("plan/", slug)
            p_reviews = resolve_path("reviews/", slug)
            p_nested = resolve_path("reviews/r1/holistic.md", slug)
        finally:
            os.chdir(original_cwd)
        assert p_plan == worktree / "plan/", f"plan/ wrong: {p_plan}"
        assert p_reviews == worktree / "reviews/", f"reviews/ wrong: {p_reviews}"
        assert p_nested == worktree / "reviews/r1/holistic.md", f"nested wrong: {p_nested}"
        print("PASS: resolve_path covers plan/, reviews/, nested reviews/r1/holistic.md")

    # resolve_path: stale <SLUG> in template is substituted (not a literal segment)
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            p = resolve_path("active/<SLUG>/discussion.md", slug)
        finally:
            os.chdir(original_cwd)
        # <SLUG> is substituted, so no literal segment named "<SLUG>" in result
        assert "<SLUG>" not in str(p), f"<SLUG> should not appear literally in {p}"
        assert slug in str(p), f"slug {slug!r} should appear in {p}"
        print("PASS: resolve_path stale <SLUG> template substituted (no literal segment)")

    # resolve_path: slug-mismatch raises ActiveWorktreeSlugMismatch
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        # Create a directory named "wrong-slug" but checked out on branch "hanf/my-task"
        # (directory slug ≠ branch-derived slug -> mismatch).
        wrong_slug = "wrong-slug"
        wrong_dir = container / "wts" / wrong_slug
        wrong_dir.mkdir(parents=True)
        subprocess.run(["git", "-C", str(wrong_dir), "init"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(wrong_dir), "config", "user.email", "test@test.com"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "config", "user.name", "Test"],
            check=True, capture_output=True,
        )
        (wrong_dir / ".keep").write_text("", encoding="utf-8")
        subprocess.run(["git", "-C", str(wrong_dir), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(wrong_dir), "commit", "-m", "init"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "checkout", "-b", "hanf/my-task"],
            check=True, capture_output=True,
        )
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            try:
                resolve_path("discussion.md", wrong_slug)
                print("FAIL: resolve_path: expected ActiveWorktreeSlugMismatch for wrong slug", file=sys.stderr)
                errors += 1
            except ActiveWorktreeSlugMismatch:
                print("PASS: resolve_path raises ActiveWorktreeSlugMismatch on branch mismatch")
        finally:
            os.chdir(original_cwd)

    # resolve_path: M2 in-place mode (hub_rel=".")
    with _test_helpers.safe_temp_dir() as tmp:
        tmp_path = Path(tmp)
        git_root = tmp_path / "git_root"
        git_root.mkdir()
        hub = git_root
        slug = "my-inplace-task"

        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir()
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: task/discussion.md\n",
            encoding="utf-8",
        )

        hub_mill_dir = hub / ".millhouse"
        hub_mill_dir.mkdir(parents=True)
        (hub_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: .\n", encoding="utf-8"
        )

        worktrees_dir = tmp_path / "wts"
        worktrees_dir.mkdir()

        with patch("_marker.slug_from_branch", return_value=slug), \
             patch("_paths.resolve_git_root", return_value=git_root), \
             patch("_paths.resolve_wiki_path", return_value=wiki_root), \
             patch("_paths.resolve_hub_path", return_value=hub), \
             patch("_paths.resolve_main_worktree_root", return_value=git_root), \
             patch("_inplace.resolve_worktrees_dir", return_value=worktrees_dir):
            p = resolve_path("task/discussion.md", slug)

        expected = git_root / "task" / "discussion.md"
        assert p == expected, f"M2 in-place (hub_rel='.'): expected {expected}, got {p}"
        print("PASS: resolve_path M2 in-place (hub_rel='.') -> git_root/task/discussion.md")

    # resolve_path: M2+sub in-place mode (hub_rel="src/Models")
    with _test_helpers.safe_temp_dir() as tmp:
        tmp_path = Path(tmp)
        git_root = tmp_path / "git_root"
        git_root.mkdir()
        hub = git_root / "src" / "Models"
        slug = "my-subdir-inplace-task"

        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir()
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: task/discussion.md\n",
            encoding="utf-8",
        )

        hub_mill_dir = hub / ".millhouse"
        hub_mill_dir.mkdir(parents=True)
        (hub_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: src/Models\n", encoding="utf-8"
        )

        worktrees_dir = tmp_path / "wts"
        worktrees_dir.mkdir()

        with patch("_marker.slug_from_branch", return_value=slug), \
             patch("_paths.resolve_git_root", return_value=git_root), \
             patch("_paths.resolve_wiki_path", return_value=wiki_root), \
             patch("_paths.resolve_hub_path", return_value=hub), \
             patch("_paths.resolve_main_worktree_root", return_value=git_root), \
             patch("_inplace.resolve_worktrees_dir", return_value=worktrees_dir):
            p = resolve_path("task/discussion.md", slug)

        expected = git_root / "src" / "Models" / "task" / "discussion.md"
        assert p == expected, f"M2+sub in-place: expected {expected}, got {p}"
        print("PASS: resolve_path M2+sub in-place (hub_rel='src/Models') -> git_root/src/Models/task/discussion.md")

    # parse_verdict: APPROVE
    raw = "# Review: My Task\n\n```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict APPROVE")

    # parse_verdict: REQUEST_CHANGES
    raw = "# Review: My Task\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"
    assert parse_verdict(raw) == "REQUEST_CHANGES"
    print("PASS: parse_verdict REQUEST_CHANGES")

    # parse_verdict: NEED_CONTEXT
    raw = "# Review: My Task\n\n```yaml\nverdict: NEED_CONTEXT\n```\n"
    assert parse_verdict(raw) == "NEED_CONTEXT"
    print("PASS: parse_verdict NEED_CONTEXT")

    # parse_verdict: yaml block not at top
    raw = "# Review: My Task\n\nPreamble.\n\n```yaml\nverdict: APPROVE\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict yaml block not at top")

    # parse_verdict: no yaml block -> ReviewError
    try:
        parse_verdict("No yaml block here.")
        print("FAIL: parse_verdict: expected ReviewError for no yaml block", file=sys.stderr)
        errors += 1
    except ReviewError:
        print("PASS: parse_verdict no yaml block -> ReviewError")

    # parse_verdict: unclosed yaml block -> ReviewError
    try:
        parse_verdict("# Review: X\n\n```yaml\nverdict: APPROVE\n")
        print("FAIL: parse_verdict: expected ReviewError for unclosed yaml block", file=sys.stderr)
        errors += 1
    except ReviewError as e:
        assert "not closed" in str(e)
        print("PASS: parse_verdict unclosed yaml block -> ReviewError")

    # parse_verdict: invalid verdict value -> ReviewError
    try:
        parse_verdict("# Review: X\n\n```yaml\nverdict: MAYBE\n```\n")
        print("FAIL: parse_verdict: expected ReviewError for invalid verdict", file=sys.stderr)
        errors += 1
    except ReviewError as e:
        assert "MAYBE" in str(e)
        print("PASS: parse_verdict invalid verdict -> ReviewError")

    # parse_verdict: multiple yaml blocks; first wins
    raw = "# Header\n\n```yaml\nverdict: APPROVE\n```\n\nMore text\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict multiple yaml blocks (first wins)")

    # parse_verdict: trailing prose after yaml
    raw = "```yaml\nverdict: APPROVE\n```\n\nThanks, this looks great.\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict trailing prose after yaml")

    # parse_verdict: yaml fence with trailing whitespace
    raw = "```yaml   \nverdict: APPROVE\n```   \n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict yaml fence with trailing whitespace")

    # parse_verdict: prose preamble + yaml block
    raw = "Review written to file.md. Verdict is APPROVE.\n\n# Review: X\n\n```yaml\nverdict: APPROVE\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict prose preamble + yaml block")

    # parse_verdict: verdict with extra whitespace
    raw = "```yaml\n  verdict:   APPROVE   \n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict verdict with extra whitespace")

    # write_review_file: creates file
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir / "reviews"
        path = write_review_file(reviews, "discussion", 1, "---\nverdict: APPROVE\n---\n")
        assert path.exists() and "discussion-review-r1" in path.name
        print(f"PASS: write_review_file discussion: {path.name}")

        path2 = write_review_file(reviews, "plan", 1, "content", scope="01-setup")
        assert "plan-review-01-setup-r1" in path2.name
        print(f"PASS: write_review_file plan-batch: {path2.name}")

        path3 = write_review_file(reviews, "plan", 1, "content", scope="holistic")
        assert "plan-review-r1" in path3.name and "holistic" not in path3.name
        print(f"PASS: write_review_file plan-holistic: {path3.name}")

        path4 = write_review_file(reviews, "code", 1, "content", scope="foundation")
        assert "code-review-foundation-r1" in path4.name
        print(f"PASS: write_review_file code-batch: {path4.name}")

    # bulk_files: nonexistent skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        existing = Path(tmpdir) / "a.md"
        existing.write_text("hello")
        result = bulk_files([existing, Path("/nonexistent/x.md")])
        assert "hello" in result and "FILE:" in result
        print("PASS: bulk_files skips missing files")

    # bulk_files: END FILE delimiter present
    with _test_helpers.safe_temp_dir() as tmpdir:
        p1 = Path(tmpdir) / "a.py"
        p2 = Path(tmpdir) / "b.py"
        p1.write_text("content-a", encoding="utf-8")
        p2.write_text("content-b", encoding="utf-8")
        result = bulk_files([p1, p2])
        assert f"--- END FILE: {p1} ---" in result, f"END FILE missing for p1: {result!r}"
        assert f"--- END FILE: {p2} ---" in result, f"END FILE missing for p2: {result!r}"
        assert result.index(f"--- FILE: {p1}") < result.index(f"--- END FILE: {p1}"), \
            "opener must precede closer for p1"
        print("PASS: bulk_files END FILE delimiters present and ordered")

    # bulk_files_with_diff: END FILE delimiter present
    with _test_helpers.safe_temp_dir() as tmpdir:
        p1 = Path(tmpdir) / "a.py"
        p2 = Path(tmpdir) / "b.py"
        p1.write_text("content-a", encoding="utf-8")
        p2.write_text("content-b", encoding="utf-8")
        result = bulk_files_with_diff([p1, p2], None, Path(tmpdir), 0.25)
        assert f"--- END FILE: {p1} ---" in result, f"END FILE missing for p1: {result!r}"
        assert f"--- END FILE: {p2} ---" in result, f"END FILE missing for p2: {result!r}"
        assert result.index(f"--- FILE: {p1}") < result.index(f"--- END FILE: {p1}"), \
            "opener must precede closer for p1"
        print("PASS: bulk_files_with_diff END FILE delimiters present and ordered (start_sha=None)")

    # render_prompt: missing template -> FileNotFoundError
    try:
        render_prompt("nonexistent-template-xyz")
        print("FAIL: render_prompt: expected FileNotFoundError for missing template", file=sys.stderr)
        errors += 1
    except FileNotFoundError:
        print("PASS: render_prompt missing template -> FileNotFoundError")

    # aggregate_verdict
    assert aggregate_verdict(["APPROVE", "APPROVE"]) == "APPROVE"
    assert aggregate_verdict(["APPROVE", "REQUEST_CHANGES"]) == "REQUEST_CHANGES"
    assert aggregate_verdict(["APPROVE", "ERROR"]) == "REQUEST_CHANGES"
    assert aggregate_verdict(["APPROVE", "NEED_CONTEXT"]) == "NEED_CONTEXT"
    assert aggregate_verdict(["NEED_CONTEXT", "REQUEST_CHANGES"]) == "NEED_CONTEXT"
    assert aggregate_verdict([]) == "APPROVE"
    print("PASS: aggregate_verdict (incl. NEED_CONTEXT precedence)")

    # build_tool_rule modes
    assert "Do NOT request tool calls" in build_tool_rule("bulk")
    assert "MAY use Read, Grep, and Glob" in build_tool_rule("tool-use")
    print("PASS: build_tool_rule bulk + tool-use")

    try:
        build_tool_rule("weird")
        print("FAIL: build_tool_rule: expected ValueError for unknown mode", file=sys.stderr)
        errors += 1
    except ValueError as e:
        assert "weird" in str(e)
        print("PASS: build_tool_rule unknown mode -> ValueError")

    # load_config: valid YAML + local override
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        wiki = tmpdir_path / "wiki"
        wiki.mkdir()
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        _write_mill_config_yaml = tmpdir_path / "mill-config.yaml"
        _write_mill_config_yaml.write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 3\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        cfg = load_config(tmpdir_path, mill)
        assert cfg["roles"]["plan-review"]["batch"]["rounds"] == 3
        print("PASS: load_config loads repo config")

        (mill / "config.local.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 1\n",
            encoding="utf-8",
        )
        cfg = load_config(tmpdir_path, mill)
        assert cfg["roles"]["plan-review"]["batch"]["rounds"] == 1
        assert cfg["roles"]["plan-review"]["batch"]["reviewer"] == "sonnetmax"
        print("PASS: load_config local override wins; other keys preserved")

    # load_config: missing config -> ReviewError
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        try:
            with patch(
                "_review_common.resolve_plugin_template_path",
                return_value=Path("/nonexistent/mill-config.yaml"),
            ):
                load_config(tmpdir_path, mill)
            print("FAIL: load_config: expected ReviewError for missing config", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "Missing config" in str(e)
            print("PASS: load_config missing config -> ReviewError")

    # load_config: stale review: overlay in config.local.yaml -> stderr warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        import io as _io
        import contextlib as _cl
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        (tmpdir_path / "mill-config.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 3\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        (mill / "config.local.yaml").write_text(
            "review:\n  code:\n    rounds: 1\n",
            encoding="utf-8",
        )
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            cfg = load_config(tmpdir_path, mill)
        _warning = _err_buf.getvalue()
        assert _warning, "expected a stderr warning, got empty string"
        assert "review" in _warning, f"warning should mention 'review': {_warning!r}"
        local_path_str = str(mill / "config.local.yaml")
        assert local_path_str in _warning, f"warning should mention overlay path: {_warning!r}"
        print("PASS: load_config stale review: overlay emits stderr warning with overlay path")

    # load_config bare roles: key does not crash
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        (tmpdir_path / "mill-config.yaml").write_text(
            "roles:\n",
            encoding="utf-8",
        )
        # Create a test template with a full roles: dict
        template_dir = tmpdir_path / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)
        template_path = template_dir / "mill-config.yaml"
        template_path.write_text(
            "roles:\n"
            "  plan-review:\n"
            "    batch:\n"
            "      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        with patch("_review_common.resolve_plugin_template_path", return_value=template_path):
            cfg = load_config(tmpdir_path, mill)
        assert isinstance(cfg.get("roles"), dict), f"Expected roles to be dict; got {cfg.get('roles')!r}"
        print("PASS: load_config bare roles: does not crash; template roles: preserved")

    # load_config hub_relative_path does not emit unknown-key warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        (tmpdir_path / "mill-config.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        (mill / "config.local.yaml").write_text(
            "hub_relative_path: subdir\n",
            encoding="utf-8",
        )
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            with patch("_review_common.resolve_plugin_template_path", return_value=tmpdir_path / "mill-config.yaml"):
                cfg = load_config(tmpdir_path, mill)
        _warning = _err_buf.getvalue()
        assert "hub_relative_path" not in _warning, f"hub_relative_path should not appear in warning; got {_warning!r}"
        print("PASS: load_config hub_relative_path in config.local.yaml does not emit unknown-key warning")

    # parse_batch_refs: multi-line bullet form returns all sub-bullet paths
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "### Card 1\n\n"
            "- **Context:**\n"
            "  - `path/a`\n"
            "  - `path/b`\n"
            "- **Creates:** none\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == ["path/a", "path/b"], f"Got {refs}"
        print("PASS: parse_batch_refs multi-line bullet form returns both paths")

    # parse_batch_refs: 'none' token is filtered out
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Creates:** none\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'none' token filtered")

    # parse_batch_refs: single-line form returns both paths
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Context:** `x`, `y`\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == ["x", "y"], f"Got {refs}"
        print("PASS: parse_batch_refs single-line form returns both paths")

    # parse_batch_refs: mixed single-line and multi-line fields
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Context:** `a`\n"
            "- **Edits:**\n"
            "  - `b`\n"
            "  - `c`\n"
            "- **Creates:** none\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == ["a", "b", "c"], f"Got {refs}"
        print("PASS: parse_batch_refs mixed single-line and multi-line fields")

    # parse_batch_refs: case-variant none tokens filtered (Block A: None)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Creates:** None\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'None' (capital N) filtered")

    # parse_batch_refs: case-variant none tokens filtered (Block B: NONE)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Edits:** NONE\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'NONE' (all caps) filtered")

    # parse_batch_refs: case-variant none in sub-bullet form (Block C: `None`)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Creates:**\n"
            "  - `None`\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs sub-bullet `None` filtered")

    # parse_batch_refs: mixed token + lowercase none inline (Block D: regression pin)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Context:** `a`, none\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        # backtick tokens win; "none" is comma-fallback and filtered
        assert refs == ["a"], f"Got {refs}"
        print("PASS: parse_batch_refs backtick tokens win; trailing 'none' filtered")

    # parse_batch_refs: Deletes: field extracted alongside Context/Edits/Creates
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Context:** `src/a.py`\n"
            "- **Edits:** `src/b.py`\n"
            "- **Creates:** `src/c.py`\n"
            "- **Deletes:** `src/d.py`\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert "src/a.py" in refs, f"Context token missing: {refs}"
        assert "src/b.py" in refs, f"Edits token missing: {refs}"
        assert "src/c.py" in refs, f"Creates token missing: {refs}"
        assert "src/d.py" in refs, f"Deletes token missing: {refs}"
        print("PASS: parse_batch_refs includes Deletes tokens alongside Context/Edits/Creates")

    # resolve_ref_paths: hit on disk
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths([str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths hit on disk returns resolved path")

    # resolve_ref_paths: suppression via creates_union (no error, empty return)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"], tmp_dir, root=None,
            creates_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths creates_union suppresses missing path")

    # resolve_ref_paths: hard-fail on unresolved path
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["nonexistent.py"], tmp_dir, root=None)
            print("FAIL: resolve_ref_paths: expected ReviewError for missing path", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            assert "nonexistent.py" in str(e), f"Path not in message: {e}"
            print("PASS: resolve_ref_paths hard-fails with 'referenced path not found'")

    # resolve_ref_paths: wiki path resolved
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        (tmp_wiki / "active" / "x").mkdir(parents=True)
        (tmp_wiki / "active" / "x" / "discussion.md").write_text("d")
        result = resolve_ref_paths(
            ["wiki/active/x/discussion.md"], tmp_project, root=None,
            wiki_root=tmp_wiki,
        )
        assert result == [tmp_wiki / "active" / "x" / "discussion.md"], f"Got {result}"
        print("PASS: resolve_ref_paths wiki/ prefix resolved via wiki_root")

    # resolve_ref_paths: wiki path missing wiki_root raises ReviewError
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["wiki/foo"], tmp_dir, root=None)
            print("FAIL: resolve_ref_paths: expected ReviewError for wiki/ without wiki_root", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "no wiki_root provided" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths wiki/ without wiki_root raises ReviewError")

    # resolve_ref_paths: wiki path exists in wiki_root but not in creates_union -> hard-fail
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        tmp_wiki.mkdir()
        try:
            resolve_ref_paths(
                ["wiki/active/missing.md"], tmp_project, root=None,
                wiki_root=tmp_wiki,
            )
            print("FAIL: resolve_ref_paths: expected ReviewError for missing wiki path", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths wiki path missing on disk hard-fails")

    # resolve_ref_paths: caller_label appears in error message
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["missing.py"], tmp_dir, root=None,
                caller_label="_review_plan",
            )
            print("FAIL: resolve_ref_paths: expected ReviewError", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert str(e).startswith("[_review_plan]"), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths caller_label appears in error message")

    # resolve_ref_paths: defensive None filter (Python None in list)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths([None, str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths defensive None skipped silently")

    # resolve_ref_paths: defensive lowercase 'none' filter
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(["none", str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths 'none' string skipped silently")

    # resolve_ref_paths: defensive 'None' (capital N) filter
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(["None", str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths 'None' string skipped silently")

    # resolve_ref_paths: missing + in deletes_union -> silent suppress
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"], tmp_dir, root=None,
            deletes_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths deletes_union suppresses missing path")

    # resolve_ref_paths: missing + in both unions -> silent suppress
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"], tmp_dir, root=None,
            creates_union={"nonexistent.py"},
            deletes_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths missing + in both unions -> silent suppress")

    # resolve_ref_paths: on-disk + in deletes_union -> resolved normally, included
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(
            ["real.py"], tmp_dir, root=None,
            deletes_union={"real.py"},
        )
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths on-disk + in deletes_union -> resolved and included")

    # resolve_ref_paths: missing + in neither union -> ReviewError (existing behaviour preserved)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["nonexistent.py"], tmp_dir, root=None,
                deletes_union={"other.py"},
            )
            print("FAIL: resolve_ref_paths: expected ReviewError for missing path not in deletes_union", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths missing + not in deletes_union -> ReviewError")

    # resolve_ref_paths: caller_label in error when deletes_union present but path missing
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["missing.py"], tmp_dir, root=None,
                deletes_union={"other.py"},
                caller_label="test_caller",
            )
            print("FAIL: resolve_ref_paths: expected ReviewError", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert str(e).startswith("[test_caller]"), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths caller_label in error with deletes_union present")

    # resolve_ref_paths: git_root fallback hit
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        git_file = tmp_git / "fallback.py"
        git_file.parent.mkdir(parents=True)
        git_file.write_text("x")
        result = resolve_ref_paths(
            ["fallback.py"], tmp_project, root=None,
            git_root=tmp_git,
        )
        assert result == [git_file], f"Got {result}"
        print("PASS: resolve_ref_paths git_root fallback hit returns git_root path")

    # resolve_ref_paths: git_root fallback miss (hard-fail)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        try:
            resolve_ref_paths(
                ["missing.py"], tmp_project, root=None,
                git_root=tmp_git,
            )
            print("FAIL: resolve_ref_paths git_root fallback miss: expected ReviewError", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths git_root fallback miss -> hard-fail ReviewError")

    # resolve_ref_paths: no git_root kwarg (current behavior unchanged)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["missing.py"], tmp_dir, root=None)
            print("FAIL: resolve_ref_paths no git_root: expected ReviewError", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths without git_root preserves current behavior")

    # resolve_ref_paths: creates_union precedence over git_root
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        result = resolve_ref_paths(
            ["missing.py"], tmp_project, root=None,
            creates_union={"missing.py"},
            git_root=tmp_git,
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths creates_union suppresses even with git_root fallback")

    # resolve_ref_paths: wiki/ prefix unaffected by git_root fallback
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        tmp_wiki.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        wiki_file = tmp_wiki / "doc.md"
        wiki_file.write_text("x")
        result = resolve_ref_paths(
            ["wiki/doc.md"], tmp_project, root=None,
            wiki_root=tmp_wiki,
            git_root=tmp_git,
        )
        assert result == [wiki_file], f"Got {result}"
        print("PASS: resolve_ref_paths wiki/ prefix ignores git_root fallback")

    # compute_creates_union: empty plan dir returns empty set
    with _test_helpers.safe_temp_dir() as tmpdir:
        result = compute_creates_union(Path(tmpdir) / "nonexistent")
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union nonexistent plan_dir returns empty set")

    # compute_creates_union: one batch with inline Creates tokens
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** `a`, `b`\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_creates_union inline Creates returns set of tokens")

    # compute_creates_union: none token filtered
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** none\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union 'none' token filtered")

    # compute_creates_union: two batches with sub-bullet Creates -> union
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:**\n"
            "  - `x.py`\n"
            "  - `y.py`\n",
            encoding="utf-8",
        )
        (plan_dir / "02-wire.md").write_text(
            "- **Creates:**\n"
            "  - `z.py`\n",
            encoding="utf-8",
        )
        result = compute_creates_union(plan_dir)
        assert result == {"x.py", "y.py", "z.py"}, f"Got {result}"
        print("PASS: compute_creates_union two batches -> union of Creates tokens")

    # compute_creates_union: 00-overview.md excluded
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "00-overview.md").write_text(
            "- **Creates:** `overview-token`\n", encoding="utf-8"
        )
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** `real-token`\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == {"real-token"}, f"Got {result}"
        print("PASS: compute_creates_union 00-overview.md excluded")

    # compute_creates_union: case-variant None filtered
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** None\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union 'None' (capital N) filtered")

    # ---------------------------------------------------------------------------
    # compute_deletes_union
    # ---------------------------------------------------------------------------

    # empty plan dir returns empty set
    with _test_helpers.safe_temp_dir() as tmpdir:
        result = compute_deletes_union(Path(tmpdir) / "nonexistent")
        assert result == set(), f"Got {result}"
        print("PASS: compute_deletes_union nonexistent plan_dir returns empty set")

    # single batch single-line Deletes tokens
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:** `a`, `b`\n", encoding="utf-8"
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_deletes_union inline Deletes returns set of tokens")

    # multi-line bullet form
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:**\n"
            "  - `a`\n"
            "  - `b`\n",
            encoding="utf-8",
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_deletes_union multi-line bullet form returns tokens")

    # 'none' sentinel filtered (case variants)
    for sentinel in ("none", "None", "NONE"):
        with _test_helpers.safe_temp_dir() as tmpdir:
            plan_dir = Path(tmpdir)
            (plan_dir / "01-setup.md").write_text(
                f"- **Deletes:** {sentinel}\n", encoding="utf-8"
            )
            result = compute_deletes_union(plan_dir)
            assert result == set(), f"Got {result} for sentinel {sentinel!r}"
        print(f"PASS: compute_deletes_union '{sentinel}' sentinel filtered")

    # two batches with overlapping deletes — de-duplicated
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:** `x.py`, `y.py`\n", encoding="utf-8"
        )
        (plan_dir / "02-wire.md").write_text(
            "- **Deletes:** `y.py`, `z.py`\n", encoding="utf-8"
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"x.py", "y.py", "z.py"}, f"Got {result}"
        print("PASS: compute_deletes_union two batches with overlap -> de-duplicated")

    # Deletes: absent on a card contributes nothing; other cards in same batch do
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Context:** `src/a.py`\n"
            "- **Deletes:** `old.py`\n"
            "- **Context:** `src/b.py`\n",
            encoding="utf-8",
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"old.py"}, f"Got {result}"
        print("PASS: compute_deletes_union Deletes absent on some cards; present on others")

    # 00-overview.md is skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "00-overview.md").write_text(
            "- **Deletes:** `overview-token`\n", encoding="utf-8"
        )
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:** `real-token`\n", encoding="utf-8"
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"real-token"}, f"Got {result}"
        print("PASS: compute_deletes_union 00-overview.md excluded")

    # ---------------------------------------------------------------------------
    # build_manifest_section
    # ---------------------------------------------------------------------------

    # Empty input
    result = build_manifest_section([])
    assert result == "## Files included (N=0)\n\n(no files)", f"Got {result!r}"
    print("PASS: build_manifest_section empty input")

    # Three-path input
    paths = [Path("/a/foo.py"), Path("/b/bar.py"), Path("/c/baz.py")]
    result = build_manifest_section(paths)
    assert result.startswith("## Files included (N=3)"), f"Got {result!r}"
    lines = result.split("\n")
    assert lines[1] == "", f"Expected blank line, got {lines[1]!r}"
    assert lines[2] == f"- {paths[0]}", f"Got {lines[2]!r}"
    assert lines[3] == f"- {paths[1]}", f"Got {lines[3]!r}"
    assert lines[4] == f"- {paths[2]}", f"Got {lines[4]!r}"
    print("PASS: build_manifest_section three-path input (heading + blank + bullets)")

    # No trailing newline
    assert not result.endswith("\n"), f"Expected no trailing newline, got {result!r}"
    print("PASS: build_manifest_section no trailing newline")

    # ---------------------------------------------------------------------------
    # build_deletes_section
    # ---------------------------------------------------------------------------

    # Empty list -> empty string
    result = build_deletes_section([])
    assert result == "", f"Expected empty string, got {result!r}"
    print("PASS: build_deletes_section empty list -> empty string")

    # Single token
    result = build_deletes_section(["old_module.py"])
    assert result == "## Intentionally deleted (N=1)\n\n- old_module.py", f"Got {result!r}"
    print("PASS: build_deletes_section single token -> heading + bullet")

    # Multiple tokens preserve input order
    result = build_deletes_section(["a.py", "b.py", "c.py"])
    assert result.startswith("## Intentionally deleted (N=3)"), f"Wrong heading: {result!r}"
    lines = result.split("\n")
    assert lines[2] == "- a.py", f"Wrong first bullet: {lines[2]!r}"
    assert lines[3] == "- b.py", f"Wrong second bullet: {lines[3]!r}"
    assert lines[4] == "- c.py", f"Wrong third bullet: {lines[4]!r}"
    print("PASS: build_deletes_section multiple tokens preserve input order")

    # Bullets are exactly '- <token>' — no backticks added
    result = build_deletes_section(["path/to/file.py"])
    assert "- path/to/file.py" in result, f"Expected plain bullet, got {result!r}"
    assert "`" not in result, f"No backticks should be added: {result!r}"
    print("PASS: build_deletes_section bullets have no backticks added")

    # No trailing newline
    result = build_deletes_section(["x.py"])
    assert not result.endswith("\n"), f"Expected no trailing newline, got {result!r}"
    print("PASS: build_deletes_section no trailing newline")

    # ---------------------------------------------------------------------------
    # resolve_existing_paths
    # ---------------------------------------------------------------------------

    with _test_helpers.safe_temp_dir() as tmpdir:
        project = Path(tmpdir) / "project"
        project.mkdir()

        # Path on disk -> returned
        existing = project / "real.py"
        existing.write_text("x")
        result = resolve_existing_paths([str(existing)], project, root=None)
        assert result == [existing], f"Got {result}"
        print("PASS: resolve_existing_paths path on disk returned")

        # Path NOT on disk -> silently dropped
        result = resolve_existing_paths(["nonexistent.py"], project, root=None)
        assert result == [], f"Got {result}"
        print("PASS: resolve_existing_paths missing path silently dropped")

        # Wiki-prefixed path that exists under wiki_root -> returned
        wiki = Path(tmpdir) / "wiki"
        (wiki / "active" / "slug").mkdir(parents=True)
        wiki_file = wiki / "active" / "slug" / "foo.md"
        wiki_file.write_text("w")
        result = resolve_existing_paths(
            ["wiki/active/slug/foo.md"], project, root=None, wiki_root=wiki
        )
        assert result == [wiki_file], f"Got {result}"
        print("PASS: resolve_existing_paths wiki-prefixed path exists -> returned")

        # Wiki-prefixed path missing -> silently dropped (no error)
        result = resolve_existing_paths(
            ["wiki/active/slug/missing.md"], project, root=None, wiki_root=wiki
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_existing_paths wiki-prefixed path missing -> silently dropped")

        # Wiki-prefixed path with wiki_root=None -> silently dropped (no raise)
        result = resolve_existing_paths(
            ["wiki/active/slug/foo.md"], project, root=None, wiki_root=None
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_existing_paths wiki/ with wiki_root=None -> silently dropped (no raise)")

        # None token silently dropped
        result = resolve_existing_paths([None, str(existing)], project, root=None)
        assert result == [existing], f"Got {result}"
        print("PASS: resolve_existing_paths None token silently dropped")

        # 'none' (any case) tokens silently dropped
        result = resolve_existing_paths(["none", "NONE", "None", str(existing)], project, root=None)
        assert result == [existing], f"Got {result}"
        print("PASS: resolve_existing_paths 'none'/'NONE'/'None' tokens silently dropped")

        # Mixed: [exists, missing, "none", None, wiki-exists] -> [exists, wiki-exists]
        result = resolve_existing_paths(
            [str(existing), "nonexistent.py", "none", None, "wiki/active/slug/foo.md"],
            project,
            root=None,
            wiki_root=wiki,
        )
        assert result == [existing, wiki_file], f"Got {result}"
        print("PASS: resolve_existing_paths mixed input -> only existing paths returned")

    # resolve_existing_paths: git_root fallback hit
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        git_file = tmp_git / "fallback.py"
        git_file.parent.mkdir(parents=True)
        git_file.write_text("x")
        result = resolve_existing_paths(
            ["fallback.py"], tmp_project, root=None,
            git_root=tmp_git,
        )
        assert result == [git_file], f"Got {result}"
        print("PASS: resolve_existing_paths git_root fallback hit returns git_root path")

    # resolve_existing_paths: git_root fallback miss (silent drop, no error)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        result = resolve_existing_paths(
            ["missing.py"], tmp_project, root=None,
            git_root=tmp_git,
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_existing_paths git_root fallback miss silently drops (no error)")

    # resolve_existing_paths: no git_root kwarg (current behavior unchanged)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        result = resolve_existing_paths(
            ["missing.py"], tmp_project, root=None,
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_existing_paths without git_root preserves current behavior")

    # Per-scope counters survive interleaved per-batch + holistic writes (regression for #21, #62, #63)
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        ts = "20260418-002000"
        (reviews / f"{ts}-code-review-helper-modules-r1.md").write_text("x")

        result = discover_round(reviews, "code", "helper-modules")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/helper-modules after r1: {result}")

        result = discover_round(reviews, "code", "spawn-core")
        assert result == 1, f"expected 1, got {result}"
        print(f"PASS: discover_round per-scope code/spawn-core (different batch, fresh count): {result}")

        (reviews / f"{ts}-code-review-r1.md").write_text("x")

        result = discover_round(reviews, "code", "holistic")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/holistic independent after holistic r1: {result}")

        result = discover_round(reviews, "code", "helper-modules")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/helper-modules still independent of holistic: {result}")

    # ---------------------------------------------------------------------------
    # parse_missing_context
    # ---------------------------------------------------------------------------

    # No ## Missing context heading -> []
    result = parse_missing_context("# Review\n\n```yaml\nverdict: NEED_CONTEXT\n```\n")
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context no heading -> []")

    # One path bullet
    text = "## Missing context\n\n- `a/b.py` — reason text\n"
    result = parse_missing_context(text)
    assert result == ["a/b.py"], f"Got {result}"
    print("PASS: parse_missing_context one path bullet -> ['a/b.py']")

    # Two path bullets in order
    text = "## Missing context\n\n- `a/b.py` — reason\n- `c/d.py` — other reason\n"
    result = parse_missing_context(text)
    assert result == ["a/b.py", "c/d.py"], f"Got {result}"
    print("PASS: parse_missing_context two path bullets -> list in order")

    # Empty section (heading present, no bullets)
    text = "## Missing context\n\nNo bullets here.\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context empty section -> []")

    # Section terminated by next ## heading — only paths between headings captured
    text = (
        "## Missing context\n\n"
        "- `x/y.py` — reason\n\n"
        "## Verdict\n\n"
        "- `z/w.py` — should NOT be captured\n"
    )
    result = parse_missing_context(text)
    assert result == ["x/y.py"], f"Got {result}"
    print("PASS: parse_missing_context stops at next ## heading")

    # Bullet without backticks -> not captured
    text = "## Missing context\n\n- a/b.py — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context bullet without backticks not captured")

    # Bullet with `none` token -> filtered (lowercase)
    text = "## Missing context\n\n- `none` — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context `none` token filtered")

    # Bullet with `None` token -> filtered (capital N)
    text = "## Missing context\n\n- `None` — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context `None` token filtered")

    # ---------------------------------------------------------------------------
    # build_reattached_section
    # ---------------------------------------------------------------------------

    # Empty input -> ""
    result = build_reattached_section([])
    assert result == "", f"Got {result!r}"
    print("PASS: build_reattached_section empty input -> ''")

    # One path -> heading + blank line + FILE delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        f = Path(tmpdir) / "foo.py"
        f.write_text("content")
        result = build_reattached_section([f])
        assert "## Re-attached files (you said these were missing)" in result, f"Missing heading in: {result!r}"
        assert str(f) in result, f"Path not in output: {result!r}"
        assert "--- FILE:" in result, f"No FILE delimiter in: {result!r}"
        print("PASS: build_reattached_section one path -> heading + FILE delimiter")

    # Two paths -> both delimiters in order
    with _test_helpers.safe_temp_dir() as tmpdir:
        fa = Path(tmpdir) / "a.py"
        fb = Path(tmpdir) / "b.py"
        fa.write_text("aaa")
        fb.write_text("bbb")
        result = build_reattached_section([fa, fb])
        assert str(fa) in result, "fa not in output"
        assert str(fb) in result, "fb not in output"
        assert result.index(str(fa)) < result.index(str(fb)), "fa should appear before fb"
        print("PASS: build_reattached_section two paths -> both delimiters in order")

    # ---------------------------------------------------------------------------
    # parse_blocking_count
    # ---------------------------------------------------------------------------

    # Empty string -> 0
    result = parse_blocking_count("", severity="BLOCKING")
    assert result == 0, f"expected 0, got {result}"
    print("PASS: parse_blocking_count empty string -> 0")

    # One BLOCKING heading
    result = parse_blocking_count(
        "# Review\n\n## Findings\n\n### [BLOCKING] foo\n",
        severity="BLOCKING",
    )
    assert result == 1, f"expected 1, got {result}"
    print("PASS: parse_blocking_count one BLOCKING heading -> 1")

    # Two BLOCKINGs and one NIT
    text = "### [BLOCKING] one\n### [BLOCKING] two\n### [NIT] three\n"
    result = parse_blocking_count(text, severity="BLOCKING")
    assert result == 2, f"expected 2, got {result}"
    print("PASS: parse_blocking_count two BLOCKINGs -> 2")
    result = parse_blocking_count(text, severity="NIT")
    assert result == 1, f"expected 1, got {result}"
    print("PASS: parse_blocking_count one NIT -> 1")

    # Discussion-style GAP/NOTE
    text = "### [GAP] missing edge case\n### [NOTE] minor\n"
    result = parse_blocking_count(text, severity="GAP")
    assert result == 1, f"expected 1, got {result}"
    print("PASS: parse_blocking_count GAP severity -> 1")

    # Severity match is case-sensitive
    result = parse_blocking_count("### [blocking] foo\n", severity="BLOCKING")
    assert result == 0, f"expected 0, got {result}"
    print("PASS: parse_blocking_count case-sensitive: lowercase blocking with BLOCKING severity -> 0")

    # Heading at start of line only — mid-line marker not counted
    result = parse_blocking_count("text ### [BLOCKING] foo\n", severity="BLOCKING")
    assert result == 0, f"expected 0, got {result}"
    print("PASS: parse_blocking_count mid-line marker not counted -> 0")

    # ---------------------------------------------------------------------------
    # parse_blocking_count divergence warning
    # ---------------------------------------------------------------------------

    def test_parse_blocking_count_warns_on_prose_divergence_numeric():
        import contextlib
        import io
        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "There are 5 blocking findings in this review.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert "heading count 3 diverges from prose count 5" in buf.getvalue(), (
            f"expected divergence warning, got: {buf.getvalue()!r}"
        )
        print("PASS: parse_blocking_count_warns_on_prose_divergence_numeric")

    def test_parse_blocking_count_warns_on_prose_divergence_spelled():
        import contextlib
        import io
        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "Five blocking issues remain in this review.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert "heading count 3 diverges from prose count 5" in buf.getvalue(), (
            f"expected divergence warning, got: {buf.getvalue()!r}"
        )
        print("PASS: parse_blocking_count_warns_on_prose_divergence_spelled")

    def test_parse_blocking_count_silent_when_aligned():
        import contextlib
        import io
        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "3 blocking issues found.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert buf.getvalue() == "", f"expected no warning, got: {buf.getvalue()!r}"
        print("PASS: parse_blocking_count_silent_when_aligned")

    def test_parse_blocking_count_silent_when_no_prose_count():
        import contextlib
        import io
        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "No prose count phrase here.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert buf.getvalue() == "", f"expected no warning, got: {buf.getvalue()!r}"
        print("PASS: parse_blocking_count_silent_when_no_prose_count")

    def test_parse_blocking_count_warns_for_gap_severity():
        import contextlib
        import io
        raw = (
            "### [GAP] missing edge case\n"
            "### [GAP] another gap\n"
            "Three gaps remain in the discussion.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="GAP")
        assert count == 2, f"expected 2, got {count}"
        stderr = buf.getvalue()
        assert "heading count 2 diverges from prose count 3 (severity=GAP)" in stderr, (
            f"expected GAP divergence warning, got: {stderr!r}"
        )
        print("PASS: parse_blocking_count_warns_for_gap_severity")

    test_parse_blocking_count_warns_on_prose_divergence_numeric()
    test_parse_blocking_count_warns_on_prose_divergence_spelled()
    test_parse_blocking_count_silent_when_aligned()
    test_parse_blocking_count_silent_when_no_prose_count()
    test_parse_blocking_count_warns_for_gap_severity()

    # ---------------------------------------------------------------------------
    # _load_root_from_overview: importable from _review_common
    # ---------------------------------------------------------------------------

    # Confirm the function is importable (not AttributeError); do not exercise behaviour
    assert callable(_load_root_from_overview), "_load_root_from_overview should be callable"
    print("PASS: _load_root_from_overview importable from _review_common")

    # ---------------------------------------------------------------------------
    # detect_resume_round
    # ---------------------------------------------------------------------------

    # reviews_dir does not exist -> None
    result = detect_resume_round(Path("/tmp/__nx_detect_resume__"), "plan")
    assert result is None, f"Got {result}"
    print("PASS: detect_resume_round nonexistent dir -> None")

    # no files -> None
    with _test_helpers.safe_temp_dir() as tmpdir:
        result = detect_resume_round(Path(tmpdir), "plan")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round empty dir -> None")

    # per-batch round-1 files + holistic round-1 file -> None
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-r1.md").write_text("x")
        result = detect_resume_round(reviews, "plan")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1 + holistic r1 -> None")

    # per-batch round-1 files + no holistic round-1 -> 1
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-02-wire-r1.md").write_text("x")
        result = detect_resume_round(reviews, "plan")
        assert result == 1, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1 + no holistic -> 1")

    # per-batch rounds 1 and 2 + holistic round-1 + no holistic round-2 -> 2
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-01-setup-r2.md").write_text("x")
        (reviews / "20260418-001400-plan-review-r1.md").write_text("x")  # holistic r1
        result = detect_resume_round(reviews, "plan")
        assert result == 2, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1+r2, holistic r1 only -> 2")

    # per-batch round 2 partial (some at r2, some at r1) + no holistic r2 -> 2
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-01-setup-r2.md").write_text("x")
        (reviews / "20260418-001400-plan-review-02-wire-r1.md").write_text("x")
        # no holistic at any round
        result = detect_resume_round(reviews, "plan")
        assert result == 2, f"Got {result}"
        print("PASS: detect_resume_round partial r2 batches, no holistic -> 2 (highest batch round)")

    # type isolation: plan per-batch files don't affect code detect_resume_round
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        result = detect_resume_round(reviews, "code")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round type isolation: plan files ignored for code")

    # ---------------------------------------------------------------------------
    # bulk_files_with_diff
    # ---------------------------------------------------------------------------

    # Test A — file with small diff uses DIFF delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "a.py").write_text("x\n" * 2000, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        with open(src / "a.py", "a", encoding="utf-8") as fh:
            fh.write("y\n" * 10)
        subprocess.run(["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "small change"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "a.py"], start_sha, repo, 0.25)
        assert "--- DIFF:" in result, f"expected DIFF delimiter, got: {result[:200]!r}"
        assert "--- FILE: " not in result, f"expected no FILE delimiter, got: {result[:200]!r}"
        assert start_sha[:8] in result, f"expected start_sha[:8] in result, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff small diff -> DIFF delimiter")

    # Test B — file with large diff uses FILE delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "b.py").write_text("x\n" * 20, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/b.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (src / "b.py").write_text("y\n" * 20, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/b.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "large change"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "b.py"], start_sha, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter, got: {result[:200]!r}"
        assert "--- DIFF:" not in result, f"expected no DIFF delimiter, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff large diff -> FILE delimiter")

    # Test C — unchanged file (empty diff) uses FILE delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "c.py").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/c.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (src / "other.py").write_text("z\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/other.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "other file"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "c.py"], start_sha, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff empty diff (unchanged file) -> FILE delimiter")

    # Test D — non-existent file is skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        (repo / "dummy.py").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "dummy.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        result = bulk_files_with_diff([repo / "nonexistent.py"], start_sha, repo, 0.25)
        assert result == "", f"expected empty string, got: {result!r}"
        print("PASS: bulk_files_with_diff non-existent file skipped")

    # Test E — git diff failure falls back to full file
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "a.py").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "a.py"], "deadbeef" * 5, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter fallback, got: {result[:200]!r}"
        assert "--- DIFF:" not in result, f"expected no DIFF delimiter, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff git diff failure -> FILE delimiter fallback")

    # _read_for_bulk: code-cell-only notebook -> source concatenated with \n\n
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "code_only.ipynb"
        notebook_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "code", "source": "print('hello')"},
                    {"cell_type": "code", "source": "x = 42"},
                ]
            }),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "print('hello')\n\nx = 42", f"Got: {result!r}"
        print("PASS: _read_for_bulk code-cell-only notebook")

    # _read_for_bulk: markdown-cell-only notebook
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "md_only.ipynb"
        notebook_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "markdown", "source": "# Title"},
                    {"cell_type": "markdown", "source": "Some text"},
                ]
            }),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "# Title\n\nSome text", f"Got: {result!r}"
        print("PASS: _read_for_bulk markdown-cell-only notebook")

    # _read_for_bulk: mixed code + markdown
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "mixed.ipynb"
        notebook_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "markdown", "source": "# Section"},
                    {"cell_type": "code", "source": "x = 1"},
                    {"cell_type": "markdown", "source": "## Subsection"},
                ]
            }),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "# Section\n\nx = 1\n\n## Subsection", f"Got: {result!r}"
        print("PASS: _read_for_bulk mixed code + markdown")

    # _read_for_bulk: cell with source as list of strings
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "list_source.ipynb"
        notebook_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "code", "source": ["line1", "line2", "line3"]},
                ]
            }),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "line1line2line3", f"Got: {result!r}"
        print("PASS: _read_for_bulk cell with list-form source")

    # _read_for_bulk: cell with source as single string
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "str_source.ipynb"
        notebook_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "code", "source": "x = 42\ny = 43"},
                ]
            }),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "x = 42\ny = 43", f"Got: {result!r}"
        print("PASS: _read_for_bulk cell with string-form source")

    # _read_for_bulk: raw cell present -> skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "with_raw.ipynb"
        notebook_path.write_text(
            json.dumps({
                "cells": [
                    {"cell_type": "code", "source": "x = 1"},
                    {"cell_type": "raw", "source": "ignore this"},
                    {"cell_type": "markdown", "source": "y"},
                ]
            }),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "x = 1\n\ny", f"Got: {result!r}"
        assert "ignore this" not in result
        print("PASS: _read_for_bulk raw cell skipped")

    # _read_for_bulk: non-.ipynb file (e.g. .py)
    with _test_helpers.safe_temp_dir() as tmpdir:
        py_path = Path(tmpdir) / "code.py"
        py_path.write_text("def hello():\n    return 42", encoding="utf-8")
        result = _read_for_bulk(py_path)
        assert result == "def hello():\n    return 42", f"Got: {result!r}"
        print("PASS: _read_for_bulk .py file returns text as-is")

    # _read_for_bulk: malformed JSON .ipynb -> returns "" with stderr warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        import io as _io
        import contextlib as _cl
        notebook_path = Path(tmpdir) / "bad.ipynb"
        notebook_path.write_text("{bad json", encoding="utf-8")
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            result = _read_for_bulk(notebook_path)
        assert result == "", f"Expected empty string, got: {result!r}"
        stderr_out = _err_buf.getvalue()
        assert "[_read_for_bulk]" in stderr_out, f"Warning should contain [_read_for_bulk]: {stderr_out!r}"
        assert "warning" in stderr_out.lower(), f"Warning should contain 'warning': {stderr_out!r}"
        print("PASS: _read_for_bulk malformed JSON -> empty string + stderr warning")

    # write_review_file: UTC-timestamp regression test (frozen clock)
    import datetime as _dt
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews_dir = Path(tmpdir)
        frozen_dt = _dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc)
        with patch("_review_common.datetime") as mock_dt_module:
            mock_dt_module.now.return_value = frozen_dt
            mock_dt_module.timezone = _dt.timezone
            # Test case 1: code review, no scope
            path = write_review_file(reviews_dir, "code", 1, "content")
            assert "20260102-030405" in path.name, f"Expected UTC timestamp 20260102-030405, got: {path.name}"
            assert "code-review-r1" in path.name
            print("PASS: write_review_file UTC timestamp (code, no scope)")

            # Test case 2: code review with scope="holistic"
            path = write_review_file(reviews_dir, "code", 1, "content", scope="holistic")
            assert "20260102-030405" in path.name
            assert "code-review-r1" in path.name
            assert "holistic" not in path.name
            print("PASS: write_review_file UTC timestamp (code, scope=holistic)")

            # Test case 3: code review with batch scope
            path = write_review_file(reviews_dir, "code", 1, "content", scope="01-foundation")
            assert "20260102-030405" in path.name
            assert "code-review-01-foundation-r1" in path.name
            print("PASS: write_review_file UTC timestamp (code, scope=batch)")

            # Test case 4: discussion review (scope ignored)
            path = write_review_file(reviews_dir, "discussion", 1, "content")
            assert "20260102-030405" in path.name
            assert "discussion-review-r1" in path.name
            print("PASS: write_review_file UTC timestamp (discussion)")

            # Test case 5: plan review with batch scope
            path = write_review_file(reviews_dir, "plan", 1, "content", scope="01-foundation")
            assert "20260102-030405" in path.name
            assert "plan-review-01-foundation-r1" in path.name
            print("PASS: write_review_file UTC timestamp (plan, scope=batch)")

    # Test: write_review_file holistic naming (#316)
    # Regression: ensure "-holistic-review-" substring never appears in filenames.
    # scope=None, scope="holistic", and scope="01-foo" should produce the correct patterns.
    try:
        with _test_helpers.safe_temp_dir() as tmpdir:
            reviews_dir = Path(tmpdir)

            # Case 1: scope=None (holistic)
            path1 = write_review_file(reviews_dir, "code", 1, "content", scope=None)
            assert "-holistic-review-" not in path1.name, (
                f"scope=None should not contain '-holistic-review-': {path1.name}"
            )
            assert "code-review-r1" in path1.name, (
                f"scope=None should have code-review-r1 pattern: {path1.name}"
            )

            # Case 2: scope="holistic" (explicit holistic)
            path2 = write_review_file(reviews_dir, "code", 1, "content", scope="holistic")
            assert "-holistic-review-" not in path2.name, (
                f"scope='holistic' should not contain '-holistic-review-': {path2.name}"
            )
            assert "code-review-r1" in path2.name, (
                f"scope='holistic' should have code-review-r1 pattern: {path2.name}"
            )

            # Case 3: scope="01-foo" (per-batch)
            path3 = write_review_file(reviews_dir, "code", 1, "content", scope="01-foo")
            assert "-holistic-review-" not in path3.name, (
                f"scope='01-foo' should not contain '-holistic-review-': {path3.name}"
            )
            assert "code-review-01-foo-r1" in path3.name, (
                f"scope='01-foo' should have code-review-01-foo-r1 pattern: {path3.name}"
            )

            print("PASS: write_review_file holistic naming regression (#316)")
    except AssertionError as exc:
        print(f"FAIL: write_review_file holistic naming: {exc}", file=sys.stderr)
        errors += 1
    except Exception as exc:
        print(f"FAIL: write_review_file holistic naming (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        errors += 1

    # find_active_slug glob fallback: one .active file -> returns slug
    try:
        with _test_helpers.safe_temp_dir() as tmp:
            hub_root = Path(tmp)
            mill_dir = hub_root / "_mill"
            mill_dir.mkdir(parents=True)
            (mill_dir / "my-task.active").write_text("", encoding="utf-8")

            cfg = {}
            with patch("_review_common._marker.slug_from_branch", side_effect=_marker.MarkerError("test")):
                result = find_active_slug(hub_root, Path(tmp) / "wiki", cfg)

            assert result == "my-task", f"Expected 'my-task', got {result!r}"
            print("PASS: find_active_slug glob fallback — one .active file -> 'my-task'")
    except AssertionError as exc:
        print(f"FAIL: find_active_slug glob fallback one file: {exc}", file=sys.stderr)
        errors += 1
    except Exception as exc:
        print(f"FAIL: find_active_slug glob fallback one file (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        errors += 1

    # find_active_slug glob fallback: multiple .active files -> ReviewError
    try:
        with _test_helpers.safe_temp_dir() as tmp:
            hub_root = Path(tmp)
            mill_dir = hub_root / "_mill"
            mill_dir.mkdir(parents=True)
            (mill_dir / "task-a.active").write_text("", encoding="utf-8")
            (mill_dir / "task-b.active").write_text("", encoding="utf-8")

            cfg = {}
            with patch("_review_common._marker.slug_from_branch", side_effect=_marker.MarkerError("test")):
                try:
                    find_active_slug(hub_root, Path(tmp) / "wiki", cfg)
                    print("FAIL: find_active_slug glob fallback multiple files: expected ReviewError", file=sys.stderr)
                    errors += 1
                except ReviewError as e:
                    if "use --slug" not in str(e):
                        print(f"FAIL: find_active_slug glob fallback multiple files: expected 'use --slug' in error, got {e!r}", file=sys.stderr)
                        errors += 1
                    else:
                        print("PASS: find_active_slug glob fallback — multiple .active files -> ReviewError with 'use --slug'")
    except Exception as exc:
        if not isinstance(exc, AssertionError):
            print(f"FAIL: find_active_slug glob fallback multiple files (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
            errors += 1

    # find_active_slug glob fallback: no _mill/ dir -> ReviewError
    try:
        with _test_helpers.safe_temp_dir() as tmp:
            hub_root = Path(tmp)
            # Do NOT create _mill/

            cfg = {}
            with patch("_review_common._marker.slug_from_branch", side_effect=_marker.MarkerError("test")):
                try:
                    find_active_slug(hub_root, Path(tmp) / "wiki", cfg)
                    print("FAIL: find_active_slug glob fallback no _mill: expected ReviewError", file=sys.stderr)
                    errors += 1
                except ReviewError:
                    print("PASS: find_active_slug glob fallback — no _mill/ dir -> ReviewError")
    except AssertionError as exc:
        print(f"FAIL: find_active_slug glob fallback no _mill: {exc}", file=sys.stderr)
        errors += 1
    except Exception as exc:
        if not isinstance(exc, (ReviewError, AssertionError)):
            print(f"FAIL: find_active_slug glob fallback no _mill (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
            errors += 1

    # ---------------------------------------------------------------------------
    # ReviewResult.nit_count field
    # ---------------------------------------------------------------------------

    # nit_count defaults to 0
    result = ReviewResult(type="code", round=1, verdict="APPROVE")
    assert result.nit_count == 0, f"Expected nit_count=0 by default, got {result.nit_count}"
    print("PASS: ReviewResult nit_count defaults to 0")

    # to_dict() includes nit_count
    result_dict = result.to_dict()
    assert "nit_count" in result_dict, f"nit_count not in to_dict(): {result_dict.keys()}"
    assert result_dict["nit_count"] == 0, f"Expected to_dict()['nit_count']=0, got {result_dict['nit_count']}"
    print("PASS: ReviewResult.to_dict() includes nit_count field")

    # nit_count non-default value round-trips
    result_with_nits = ReviewResult(type="code", round=1, verdict="APPROVE", nit_count=5)
    assert result_with_nits.nit_count == 5, f"Expected nit_count=5, got {result_with_nits.nit_count}"
    result_dict = result_with_nits.to_dict()
    assert result_dict["nit_count"] == 5, f"Expected to_dict()['nit_count']=5, got {result_dict['nit_count']}"
    print("PASS: ReviewResult nit_count non-default value round-trips through to_dict()")

    # ---------------------------------------------------------------------------
    # parse_verdict: unfenced fallback line
    # ---------------------------------------------------------------------------

    # parse_verdict: unfenced verdict line with leading whitespace
    raw = "  verdict: GAPS_FOUND\n"
    assert parse_verdict(raw) == "GAPS_FOUND"
    print("PASS: parse_verdict unfenced verdict line with leading whitespace")

    # parse_verdict: fenced block still works as primary path
    raw = "# Review: X\n\n```yaml\nverdict: APPROVE\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict fenced block (primary path)")

    # parse_verdict: no verdict at all (no fenced, no unfenced) raises ReviewError
    try:
        parse_verdict("No verdict anywhere in this text.")
        print("FAIL: parse_verdict: expected ReviewError for no verdict", file=sys.stderr)
        errors += 1
    except ReviewError:
        print("PASS: parse_verdict no verdict -> ReviewError")

    # parse_verdict: invalid value inside fenced block raises even with unfenced fallback available
    try:
        raw = "```yaml\nverdict: INVALID_VALUE\n```\n\nverdict: APPROVE\n"
        parse_verdict(raw)
        print("FAIL: parse_verdict: expected ReviewError for invalid fenced value", file=sys.stderr)
        errors += 1
    except ReviewError as e:
        assert "INVALID_VALUE" in str(e)
        print("PASS: parse_verdict invalid fenced value raises (fallback not used)")

    # ---------------------------------------------------------------------------
    # _read_for_bulk and bulk_files: directory handling
    # ---------------------------------------------------------------------------

    # _read_for_bulk: directory path returns empty string with warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        import io as _io
        import contextlib as _cl
        tmpdir_path = Path(tmpdir)
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            result = _read_for_bulk(subdir)
        assert result == "", f"Expected empty string for directory, got {result!r}"
        stderr_out = _err_buf.getvalue()
        assert "is a directory" in stderr_out, f"Expected 'is a directory' warning, got {stderr_out!r}"
        print("PASS: _read_for_bulk directory path -> empty string + warning")

    # bulk_files: real file and directory in path list -> file included, directory skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        real_file = tmpdir_path / "real.py"
        real_file.write_text("content")
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()
        result = bulk_files([real_file, subdir])
        assert "real.py" in result and "content" in result, f"File should be bulked: {result!r}"
        assert "--- FILE:" in result, f"FILE delimiter expected: {result!r}"
        print("PASS: bulk_files directory skipped, file included")

    # ---------------------------------------------------------------------------
    # tool-use mode: artefact omits inlined bodies, build_tool_rule grants tools
    # ---------------------------------------------------------------------------

    # tool-use reviewer must NOT inline source file content (sentinel line must be absent)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a fixture source file with a unique sentinel line
        source_file = tmpdir_path / "source.py"
        sentinel_line = "UNIQUE_SENTINEL_LINE_FOR_TEST_xyz123"
        source_file.write_text(f"def foo():\n    # {sentinel_line}\n    return 42\n", encoding="utf-8")

        # Create overview and batch files (empty for this test)
        overview = tmpdir_path / "overview.md"
        overview.write_text("# Overview", encoding="utf-8")

        batch_file = tmpdir_path / "01-batch.md"
        batch_file.write_text("# Batch 1", encoding="utf-8")

        # Build artefact section in tool-use mode (as prepare() does)
        artefact = _review_code._build_artefact_section(
            reviewer_mode="tool-use",
            overview_path=overview,
            batch_files=[batch_file],
            source_files=[source_file],
            ancestors_on_disk=[],
            deletes_union=set(),
        )

        # Also build the tool-use TOOL_RULE (as the template would)
        tool_rule = build_tool_rule("tool-use")

        # Verify: tool-use TOOL_RULE grants tools
        assert "MAY use Read, Grep, and Glob" in tool_rule, (
            f"Expected tool-use TOOL_RULE to grant tools, got: {tool_rule!r}"
        )

        # Verify: source file PATH is present in artefact
        assert str(source_file) in artefact, (
            f"Source file path not in artefact: {artefact!r}"
        )

        # Verify: sentinel line (the body content) is NOT present in artefact
        assert sentinel_line not in artefact, (
            f"Sentinel line should NOT be inlined in tool-use mode, but found it: {artefact!r}"
        )

        print("PASS: tool-use omits bulked bodies and build_tool_rule grants tools")

    # ---------------------------------------------------------------------------
    # bulk mode: artefact inlines source content, build_tool_rule forbids tools
    # ---------------------------------------------------------------------------

    # bulk reviewer must inline source file content (sentinel line must be present)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a fixture source file with a unique sentinel line
        source_file = tmpdir_path / "source.py"
        sentinel_line = "UNIQUE_SENTINEL_LINE_FOR_BULK_TEST_abc789"
        source_file.write_text(f"def bar():\n    # {sentinel_line}\n    return 99\n", encoding="utf-8")

        # Create overview and batch files (empty for this test)
        overview = tmpdir_path / "overview.md"
        overview.write_text("# Overview", encoding="utf-8")

        batch_file = tmpdir_path / "01-batch.md"
        batch_file.write_text("# Batch 1", encoding="utf-8")

        # Build artefact section in bulk mode (as prepare() does)
        artefact = _review_code._build_artefact_section(
            reviewer_mode="bulk",
            overview_path=overview,
            batch_files=[batch_file],
            source_files=[source_file],
            ancestors_on_disk=[],
            deletes_union=set(),
        )

        # Also build the bulk TOOL_RULE (as the template would)
        tool_rule = build_tool_rule("bulk")

        # Verify: bulk TOOL_RULE forbids tools
        assert "Do NOT request tool calls" in tool_rule, (
            f"Expected bulk TOOL_RULE to forbid tools, got: {tool_rule!r}"
        )

        # Verify: sentinel line (the body content) IS present in bulk mode
        assert sentinel_line in artefact, (
            f"Sentinel line should be inlined in bulk mode, but missing from: {artefact!r}"
        )

        # Verify: source file path is also present
        assert str(source_file) in artefact, (
            f"Source file path not in artefact: {artefact!r}"
        )

        print("PASS: bulk inlines source content and build_tool_rule forbids tools")

    # ---------------------------------------------------------------------------
    # resolve_large_prompt_timeout
    # ---------------------------------------------------------------------------

    # resolve_large_prompt_timeout: under threshold -> returns default
    cfg = {
        "roles": {
            "plan-review": {
                "holistic": {
                    "large_prompt": {
                        "threshold_ktok": 100,
                        "timeout": 3600,
                    }
                }
            }
        }
    }
    prompt = "x" * 50000  # ~12 ktok
    timeout = resolve_large_prompt_timeout(prompt, cfg, "plan-review", "holistic", default_timeout=1800)
    assert timeout == 1800, f"Expected default 1800, got {timeout}"
    print("PASS: resolve_large_prompt_timeout under threshold -> default timeout")

    # resolve_large_prompt_timeout: over threshold, key set -> returns override
    cfg = {
        "roles": {
            "plan-review": {
                "holistic": {
                    "large_prompt": {
                        "threshold_ktok": 100,
                        "timeout": 3600,
                    }
                }
            }
        }
    }
    prompt = "x" * 500000  # ~125 ktok
    timeout = resolve_large_prompt_timeout(prompt, cfg, "plan-review", "holistic", default_timeout=1800)
    assert timeout == 3600, f"Expected override 3600, got {timeout}"
    print("PASS: resolve_large_prompt_timeout over threshold + timeout key set -> override")

    # resolve_large_prompt_timeout: over threshold, key not set -> returns default
    cfg = {
        "roles": {
            "plan-review": {
                "holistic": {
                    "large_prompt": {
                        "threshold_ktok": 100,
                    }
                }
            }
        }
    }
    prompt = "x" * 500000  # ~125 ktok
    timeout = resolve_large_prompt_timeout(prompt, cfg, "plan-review", "holistic", default_timeout=1800)
    assert timeout == 1800, f"Expected default 1800, got {timeout}"
    print("PASS: resolve_large_prompt_timeout over threshold but key not set -> default")

    # resolve_large_prompt_timeout: no large_prompt key -> returns default
    cfg = {"roles": {"plan-review": {"holistic": {}}}}
    prompt = "x" * 500000
    timeout = resolve_large_prompt_timeout(prompt, cfg, "plan-review", "holistic", default_timeout=1800)
    assert timeout == 1800, f"Expected default 1800, got {timeout}"
    print("PASS: resolve_large_prompt_timeout no large_prompt key -> default")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_common unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

--- END FILE: C:\Code\millhouse\wts\track-task-briefs\plugins\mill\unit_tests\test-review-common.py ---

## Source-grounding rule

**Never guess.** A `## Files included` manifest at the top of the artefact section above lists every file delivered to you in this prompt. Before emitting `verdict: NEED_CONTEXT`, scan the manifest and confirm the file you claim is missing is genuinely absent from the list. If a file IS in the manifest but you cannot find its content via the `--- FILE: <path> ---` delimiter, that is a long-context recall failure on your side — re-scan; do not emit NEED_CONTEXT for files in the manifest. Only emit `verdict: NEED_CONTEXT` for paths that are NOT in the manifest, and explain under `## Missing context` why each path is needed (one line per path). The orchestrator will re-fire the review with those files added. Fabricating file contents — or inferring them from filename / position alone — is a worse failure than halting honestly.

## Criteria (apply to the implementation as a whole)

- **End-to-end plan alignment** — every batch's cards are realised; every file listed across all batches' `Context:`/`Edits:`/`Creates:` is present in the source files provided.
- **Shared-decisions alignment** — the `## Shared Decisions` subsections are applied consistently across all batches; deviation is BLOCKING.
- **Out-of-plan files** — BLOCKING if any source file is present that is not accounted for in any batch's reference lists. If the implementer added it, the batch file must have been updated first; a review with surprise files means that discipline was skipped somewhere.
- **Cross-batch contracts** — interfaces produced by one batch and consumed by another are compatible. Dependency order implied by `depends-on:` is reflected in the code (consumers don't assume behaviour the producer doesn't guarantee).
- **Integration correctness** — the pieces work together, not just per-batch. Call sites match signatures; shared state is consistently managed; error surfaces compose.
- **Global utility duplication** — BLOCKING if two batches independently reimplement the same helper. Consolidate into a shared module.
- **Test coverage across the whole surface** — happy paths + errors for every batch's entry point. Integration tests reach across batch boundaries where appropriate.
- **Constraint violations** — BLOCKING.
- **Codebase consistency** — naming, error handling, imports, and style match the conventions visible in the source files provided.
- **Language pitfalls** — BLOCKING if high-risk (Python: mutable defaults, import side-effects, Windows path sep, CRLF/LF).

## Output format — STRICT

Wrap your entire output in `MILL_REVIEW_BEGIN` / `MILL_REVIEW_END` markers, each on its own line. Everything outside these markers is ignored by the backend. **No preamble inside the markers.** Per finding: 3–5 lines, short and factual. Cite file and line, state the issue, propose the fix.

Target length: ~400 tokens for APPROVE, ~800–1500 tokens for REQUEST_CHANGES across multiple batches. If you produce more than ~1800 tokens, compress.

~~~markdown
MILL_REVIEW_BEGIN
# Review: Track _mill/briefs/ instead of gitignoring them — holistic

```yaml
verdict: APPROVE | REQUEST_CHANGES | NEED_CONTEXT
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: <UTC YYYY-MM-DD>
```

## Findings

### [BLOCKING] <short title, <60 chars>
**Location:** `path/to/file.py:42` (or `:42-58`)
**Issue:** <one sentence>
**Fix:** <one sentence>

### [NIT] <short title>
**Location:** `path/to/file.py:N`
**Issue:** <one sentence>
**Fix:** <one sentence>

## Missing context
(include ONLY when verdict is NEED_CONTEXT — omit the section otherwise)

- `path/to/file.py` — <one-line reason the reviewer needs this file>

## Verdict

<APPROVE | REQUEST_CHANGES | NEED_CONTEXT>
<one sentence — max 20 words>
MILL_REVIEW_END
~~~

Severity / verdict rules match review-code-batch.md.

Omit `## Findings` if zero findings. Never invent findings to pad.
