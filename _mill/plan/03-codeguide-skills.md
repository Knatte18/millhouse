# Batch: codeguide-skills

```yaml
task: "CodeGuide support for .ipynb"
batch: codeguide-skills
number: 3
cards: 3
verify: null
depends-on: [2]
```

## Batch Scope

Wires notebook handling into the three doc-operating skills so the
`notebooks-accessed-only-via-digest` rule holds at every source-reading site.
Each skill gains, at its read-source step, a branch: when a source file ends in
`.ipynb`, obtain content via `nb_digest.py` (never the Read tool), document it
with the Notebooks doc shape and verbatim-stem naming, and treat a non-zero
helper exit as skip+flag. These are SKILL.md prose edits with no runnable surface
(`verify: null`). Depends on batch 2 so the canonical Notebooks rules already
exist in `DocumentationGuide.md` for the skills to reference and mirror wording.

## Cards

### Card 5: Notebook handling in codeguide-generate

- **Context:**
  - `plugins/codeguide/templates/DocumentationGuide.md`
- **Edits:**
  - `plugins/codeguide/skills/codeguide-generate/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `codeguide-generate/SKILL.md` Step 7 ("Read undocumented source files"),
    add a `.ipynb` branch: for any in-scope source file ending in `.ipynb`, do
    NOT use the Read tool — run `python ${CLAUDE_PLUGIN_ROOT}/scripts/nb_digest.py
    <abs-path>` and read its stdout as the file's content (markdown + code only;
    outputs stripped). A non-zero exit -> skip the file and flag it to the user.
  - In Step 8/10 (doc granularity / writing module docs), note that `.ipynb`
    files use the Notebooks doc shape and verbatim-stem naming defined in
    `DocumentationGuide.md` (do not restate the full shape — point to the guide).
  - Add a bullet to the `## Rules` section: "Never read a raw `.ipynb` — obtain
    its content via `nb_digest.py` (see the Documentation Guide's Notebooks
    rules)."
  - Preserve all existing step content; only add the notebook-specific guidance.
- **Commit:** `feat(codeguide): handle .ipynb via nb_digest in codeguide-generate`

### Card 6: Notebook handling in codeguide-update

- **Context:**
  - `plugins/codeguide/templates/DocumentationGuide.md`
- **Edits:**
  - `plugins/codeguide/skills/codeguide-update/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `codeguide-update/SKILL.md` Step 4e (per source file: "Read the doc and
    the source file"), add the same `.ipynb` branch: source files ending in
    `.ipynb` are read via `python ${CLAUDE_PLUGIN_ROOT}/scripts/nb_digest.py
    <abs-path>` (stdout), never the Read tool; non-zero exit -> skip + flag. When
    creating a new notebook doc, use the Notebooks doc shape + verbatim-stem
    naming from `DocumentationGuide.md`.
  - Add a bullet to the `## Rules` section: "Never read a raw `.ipynb` — obtain
    its content via `nb_digest.py` (see the Documentation Guide's Notebooks
    rules)."
  - The existing `config.yaml` source-extension filtering (Step 4a) already
    recognizes `.ipynb` once a project opts in — no change needed there; do not
    duplicate extension logic.
  - Preserve all existing step content; only add the notebook-specific guidance.
- **Commit:** `feat(codeguide): handle .ipynb via nb_digest in codeguide-update`

### Card 7: Notebook handling in codeguide-maintain

- **Context:**
  - `plugins/codeguide/templates/DocumentationGuide.md`
- **Edits:**
  - `plugins/codeguide/skills/codeguide-maintain/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `codeguide-maintain/SKILL.md` Step 6b ("(full mode only) Read the
    corresponding source file(s)"), add the `.ipynb` branch: when the source for
    a doc is a `.ipynb`, read it via `python
    ${CLAUDE_PLUGIN_ROOT}/scripts/nb_digest.py <abs-path>` (stdout), never the
    Read tool; non-zero exit -> skip the accuracy check for that file and flag
    it. The Step 6c `## Source` link validation and Step 6e structure checks
    already work for notebook docs (relative-path link + Notebooks doc shape) —
    note that notebook docs are validated against the Notebooks shape in
    `DocumentationGuide.md`.
  - Add a bullet to the `## Rules` section: "Never read a raw `.ipynb` — obtain
    its content via `nb_digest.py` (see the Documentation Guide's Notebooks
    rules)."
  - Preserve all existing step content; only add the notebook-specific guidance.
- **Commit:** `feat(codeguide): handle .ipynb via nb_digest in codeguide-maintain`

## Batch Tests

`verify: null` — this batch edits SKILL.md prose only; there is no runnable
surface. Correctness is verified by the plan review: each card preserves existing
steps and adds the `.ipynb` -> `nb_digest.py` branch plus a never-read-raw Rules
bullet at the skill's source-reading site, pointing at the Notebooks rules in
`DocumentationGuide.md` (batch 2).
