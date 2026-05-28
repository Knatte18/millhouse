# Batch: codeguide-templates

```yaml
task: "CodeGuide support for .ipynb"
batch: codeguide-templates
number: 2
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Updates the codeguide template layer that seeds consuming repos: makes `.ipynb`
a recognized source extension example, ignores Jupyter's autosave dir, and adds
the authoritative "Notebooks" documentation rules to the Documentation Guide.
These are template/doc edits with no runnable surface (`verify: null`). The
guide subsection is the canonical home of the `notebooks-accessed-only-via-digest`,
`verbatim-stem-doc-naming`, and `notebook-doc-shape` shared decisions; the skills
batch points at it. Depends on batch 1 so the helper's CLI contract (invocation
string, stripped-output guarantee) is final before the guide documents it.

## Cards

### Card 3: Recognize .ipynb in config + ignore Jupyter checkpoints

- **Context:**
  - `plugins/codeguide/scripts/resolve.py`
- **Edits:**
  - `plugins/codeguide/templates/config.yaml`
  - `plugins/codeguide/templates/cgignore.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/codeguide/templates/config.yaml`, add `#   - .ipynb` to the
    commented `source_extensions` examples block (alongside the existing
    `#   - .py` etc. lines). Keep it commented — recognition stays opt-in
    per-project; this only advertises support. The format must match what
    `resolve.load_source_extensions()` parses (lines beginning `- .`).
  - In `plugins/codeguide/templates/cgignore.md`, add a `- .ipynb_checkpoints/`
    entry to the directory list (Jupyter's autosave dir holding stale notebook
    copies), grouping it naturally with the existing `__pycache__/` /
    `.pytest_cache/` cache entries.
- **Commit:** `feat(codeguide): recognize .ipynb and ignore .ipynb_checkpoints in templates`

### Card 4: Add Notebooks subsection to the Documentation Guide

- **Context:**
  - `plugins/codeguide/templates/config.yaml`
  - `plugins/codeguide/templates/cgignore.md`
- **Edits:**
  - `plugins/codeguide/templates/DocumentationGuide.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add a new `### Notebooks` subsection to `DocumentationGuide.md` under the
    `## Naming and Granularity` section (after the existing naming subsections),
    covering exactly these rules:
    - **Reading rule (hard):** Never read a raw `.ipynb` with the Read tool — it
      loads the notebook's execution outputs (datasets, figures, base64 images,
      stdout) and blows the token budget. Obtain notebook content ONLY by running
      `python ${CLAUDE_PLUGIN_ROOT}/scripts/nb_digest.py <path>` and reading its
      stdout, which contains only markdown + code cells with all outputs
      stripped. A non-zero exit means skip the file and flag it.
    - **Naming:** a notebook's doc uses the verbatim filename stem with `.md`
      (`notebooks/01_explore.ipynb` -> `_codeguide/modules/01_explore.md`), NOT
      PascalCased, so the source<->doc round-trip stays literal. The `## Source`
      link points at the exact `.ipynb`. If a verbatim stem would collide with
      another doc (e.g. `foo.py` and `foo.ipynb`), disambiguate with a sub-area
      folder per the collision rule above.
    - **Doc shape:** notebooks use a tailored shape instead of the Module Doc
      structure: **Purpose**, **Inputs / data sources**, **Analysis /
      transformations**, **Outputs / artifacts** (described from the code, never
      from observed execution output), **How / when to run**, **Source**. State
      that this replaces Usage/Behavior/public-interface sections because a
      notebook is a linear analysis, not a reusable module.
  - Use ASCII punctuation in the prose (` -- `, ` -> `) per repo markdown
    convention. Do not alter unrelated guide sections.
- **Commit:** `docs(codeguide): add Notebooks subsection to DocumentationGuide`

## Batch Tests

`verify: null` — this batch edits template markdown/YAML only; there is no
runnable surface and codeguide has no template-validation test. Correctness is
verified by the plan review and, downstream, by the skills batch consuming the
guide rules. The `config.yaml` example format is cross-checked against
`resolve.load_source_extensions()` (listed in Card 3 Context).
