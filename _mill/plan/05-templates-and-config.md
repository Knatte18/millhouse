# Batch: templates-and-config

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
batch: "templates-and-config"
number: 5
cards: 6
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-templates.py test-review-output-contract.py"
depends-on: [1]
```

## Batch Scope

Delivers everything the reviewer and the operator read: the five review-prompt templates, the authoritative `review-output.schema.md`, and the two `mill-config.yaml` files that must stay in sync.
The templates are what actually steer a reviewer to emit `[BLOCKING:design]` instead of `[GAP]`, so this batch is the behavioural half of the task; batch 1 only makes the backend able to read it.
Class names and the four class definitions must match batch 1's `RECOGNIZED_CLASSES` and `DEFAULT_BLOCKING_CLASSES` exactly, which is why this batch depends on batch 1 rather than running first.

Batch-local decision: the `## Out of scope for this stage` prose is deliberately different in every template rather than shared through a token.
The whole point of the section is that a code reviewer legitimately cares about things a discussion reviewer should skip, so a shared partial would have nothing to say.
Each version is kept to three or four lines so the added section cannot inflate the prompt materially, per the discussion's Constraints.

## Cards

### Card 20: Discussion template on the unified vocabulary

- **Context:**
  - `plugins/mill/templates/review-output.schema.md`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the `### [GAP] <short title, <60 chars>` and `### [NOTE] <short title>` finding examples with `### [BLOCKING:design] <short title, <60 chars>` and `### [NIT:scope] <short title>`, and replace both `GAPS_FOUND` occurrences in the `verdict:` line and the `## Verdict` body placeholder with `REQUEST_CHANGES`.
  Rewrite the severity block so it defines `BLOCKING` as must-fix-before-the-next-stage and `NIT` as record-but-do-not-block, keeps the existing closed-vocabulary paragraph with `BLOCKING`/`NIT` substituted for `GAP`/`NOTE`, and adds a class block listing the four `RECOGNIZED_CLASSES` values with the definitions from the `class-definitions-generic-across-stages` Shared Decision and one discussion-stage example each.
  State that class is written inside the same bracket as severity, colon-separated, lowercase, and that a finding with no class or an unrecognised class is a reviewer defect.
  Delete the paragraph beginning "Note: plan and code reviews use `BLOCKING` / `NIT`" entirely -- it documents the vocabulary split this task removes.
  Update the target-length line so it names `REQUEST_CHANGES` instead of `GAPS_FOUND`.
  Add the anti-ladder sentence verbatim -- "Class governs who decides and when the loop stops, never whether a finding gets fixed." -- to the severity block.
  Add a `## Out of scope for this stage` section stating that call-site and compile-breakage enumeration belongs to the build and to code review, and that an unreliable enumeration method is ONE `design` finding about method, never N `scope` findings naming individual files.
- **Commit:** `feat(templates): unify discussion review vocabulary and add class taxonomy`

### Card 21: Plan templates on the class taxonomy

- **Context:**
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In both files, replace the `### [BLOCKING] <short title, <60 chars>` and `### [NIT] <short title>` finding examples with `### [BLOCKING:design] <short title, <60 chars>` and `### [NIT:consistency] <short title>`.
  Add the same class block as card 20 -- four class names, the shared definitions, one plan-stage example each, the in-bracket colon-separated syntax rule, and the unrecognised-class-is-a-defect rule -- to each file's severity section, keeping `review-plan-holistic.md`'s existing "Severity / verdict rules match review-plan-batch.md" deferral for the severity half and stating the class rules in full in both, since the reviewer reads only one of the two.
  Add the anti-ladder sentence verbatim to both severity blocks.
  Add a `## Out of scope for this stage` section to each, stating that per-line code correctness belongs to code review and that a plan reviewer should judge whether the plan's method for enumerating work is reliable rather than re-enumerating the work itself.
  Leave the verdict vocabulary and the `NEED_CONTEXT` sections untouched -- both files already speak `APPROVE` / `REQUEST_CHANGES`.
- **Commit:** `feat(templates): add class taxonomy to plan review templates`

### Card 22: Code templates on the class taxonomy

- **Context:**
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In both files, replace the `### [BLOCKING] <short title, <60 chars>` and `### [NIT] <short title>` finding examples with `### [BLOCKING:design] <short title, <60 chars>` and `### [NIT:consistency] <short title>`.
  Add the same class block as card 20 -- four class names, the shared definitions, one code-stage example each, the in-bracket colon-separated syntax rule, and the unrecognised-class-is-a-defect rule -- to each file's severity section, stated in full in both files despite `review-code-holistic.md`'s existing "Severity / verdict rules match review-code-batch.md" deferral, since the reviewer reads only one of the two.
  Add the anti-ladder sentence verbatim to both severity blocks.
  Add a `## Out of scope for this stage` section to each, stating that re-litigating a decision already recorded in `discussion.md` is out of scope unless new evidence contradicts it.
  Leave the `## Prior non-blocking items` sections and their no-escalation rule untouched.
- **Commit:** `feat(templates): add class taxonomy to code review templates`

### Card 23: Authoritative schema for severity, class, and verdict

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change the finding-heading grammar from `### [BLOCKING|NIT|GAP|NOTE] <finding title>` to `### [BLOCKING|NIT][:design|scope|decision|consistency] <finding title>` and describe the class suffix as optional in grammar but required in practice, with a missing or unrecognised class documented as a reviewer defect that preserves the stated severity, records `class: null`, and is exempt from the ceiling.
  Replace the sentence stating each review type recognises two severity labels with one stating all three review types recognise exactly `BLOCKING` and `NIT`, and that an ambiguous finding defaults to `BLOCKING`.
  Add a class section defining the four class names per the `class-definitions-generic-across-stages` Shared Decision, documenting the per-stage `blocking_classes` ceiling as demote-only, and carrying the anti-ladder sentence verbatim.
  Update the verdict table so `GAPS_FOUND` is described as a historical discussion-review value that `parse_verdict` still accepts and normalises to `REQUEST_CHANGES`, and is never emitted; update the two `verdict:` grammar lines and the envelope field table to list `APPROVE`, `REQUEST_CHANGES`, `NEED_CONTEXT` as the emitted set.
  Document the envelope's `findings` list with the exact entry shape `{"severity", "class", "title", "demoted"}`, state that `blocking_count` and `nit_count` are derived from it, and state that it appears per-scope inside `reviews[]` and aggregated at the top level.
- **Commit:** `docs(schema): document class taxonomy, ceiling, and findings envelope`

### Card 24: blocking_classes in both config files

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This is the bootstrap card for the config change, and it is safe to land mid-flight for the currently-shipping task: the installed plugin cache's config loader treats an unrecognised key as a stderr warning and proceeds, and `resolve_blocking_classes` supplies the documented default when the key is absent, so neither the old cache code nor the new worktree code can fail on the key's presence or its absence.
  In both files add a `blocking_classes:` key under `roles.discussion-review.holistic` with value `[design]`, under `roles.plan-review.batch` and `roles.plan-review.holistic` with value `[design, scope]`, and under `roles.code-review.batch` and `roles.code-review.holistic` with value `[design, scope, decision, consistency]`.
  These values must equal batch 1's `DEFAULT_BLOCKING_CLASSES` for the corresponding role, so an operator who deletes the key gets identical behaviour.
  In `plugins/mill/templates/mill-config.yaml` only, add a comment above the first occurrence explaining that the key is a ceiling -- the backend demotes `BLOCKING` to `NIT` for any finding whose class is not listed, and never promotes -- and that omitting the key falls back to the per-stage default.
  Keep the two files in sync as CLAUDE.md requires: identical key placement and identical values, differing only in the template's comment and in the pre-existing `rounds` / `reviewer` values the two files already differ on.
- **Commit:** `feat(config): add per-role blocking_classes ceiling to hub and template`

### Card 25: Template and schema contract tests

- **Context:**
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-templates.py`
  - `plugins/mill/unit_tests/test-review-output-contract.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `test-review-templates.py`, add one parametrised check over all five review templates asserting each contains no occurrence of the tokens `GAP`, `NOTE`, or `GAPS_FOUND` as a bracketed severity label or verdict value; contains at least one finding-heading example of the form `### [BLOCKING:<class>]` and one of the form `### [NIT:<class>]` whose class is in the four recognised names; contains a `## Out of scope for this stage` section heading; and contains the anti-ladder sentence "Class governs who decides and when the loop stops, never whether a finding gets fixed." verbatim.
  In `test-review-output-contract.py`, update any assertion that encodes the old per-type severity vocabulary or the old verdict set, and add an assertion that `review-output.schema.md` documents the `findings` entry keys `severity`, `class`, `title`, and `demoted`.
  Assert against the template files on disk rather than against a copied string, so the tests fail if a template drifts.
- **Commit:** `test(templates): assert unified vocabulary, class syntax, and anti-ladder text`

## Batch Tests

`verify:` runs `test-review-templates.py` and `test-review-output-contract.py`, the two files that assert the template and schema contract and the only unit-test files this batch edits.
Both read the template files from disk, so they gate every one of cards 20 through 23 directly.
The two `mill-config.yaml` files from card 24 have no dedicated unit test; their correctness is asserted indirectly by batch 1's `resolve_blocking_classes` default tests, which pin the same values from the code side, and the CLAUDE.md sync requirement is enforced by card 24's own identical-placement requirement.
