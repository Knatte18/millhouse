# Plan: CodeGuide support for .ipynb

```yaml
task: "CodeGuide support for .ipynb"
slug: codeguide-jupyter-support
approved: false
started: 20260528-215859
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: nb-digest-helper
    file: 01-nb-digest-helper.md
    depends-on: []
    verify: PYTHONPATH= python plugins/codeguide/unit_tests/test-nb-digest.py
  - number: 2
    name: codeguide-templates
    file: 02-codeguide-templates.md
    depends-on: [1]
    verify: null
  - number: 3
    name: codeguide-skills
    file: 03-codeguide-skills.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

### Decision: notebooks-accessed-only-via-digest

- **Decision:** A `.ipynb` is NEVER read with the Read tool. Its content is
  obtained only by running `python ${CLAUDE_PLUGIN_ROOT}/scripts/nb_digest.py
  <abs-path>` and reading stdout. The digest contains only markdown-cell text +
  code-cell source; every execution output (datasets, figures, base64 images,
  stdout) is stripped at the source.
- **Rationale:** The Read tool renders a notebook *with its outputs*, which can
  be megabytes for a real analysis notebook — blowing the token budget for zero
  documentation value. Stripping at the source is the only reliable guard.
- **Applies to:** all batches (helper produces the digest; templates + skills
  encode and enforce the rule).

### Decision: verbatim-stem-doc-naming

- **Decision:** A notebook's doc file uses the verbatim filename stem with the
  extension swapped to `.md`: `notebooks/01_explore.ipynb` →
  `_codeguide/modules/01_explore.md`. No PascalCase normalization for notebooks.
- **Rationale:** Keeps the source↔doc round-trip literal in both directions —
  reverse is a `.ipynb`→`.md` swap, forward is the mandatory `## Source` relative
  link. Collisions (e.g. `foo.py` + `foo.ipynb`) use the existing sub-area-folder
  disambiguation rule.
- **Applies to:** codeguide-templates, codeguide-skills.

### Decision: ascii-markers-utf8-content

- **Decision:** The helper's own diagnostic / marker text (`[N outputs
  omitted]`, `[code cell truncated]`, stderr warnings) is ASCII-only. Cell
  *content* is user-authored and frequently non-ASCII, so the helper emits it
  through a UTF-8-reconfigured stdout (`errors='replace'`) — never escaped,
  never crashing on a cp1252 console.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII; markers must stay
  ASCII per repo convention, but cell prose/comments must survive intact.
- **Applies to:** nb-digest-helper (and its tests).

### Decision: notebook-doc-shape

- **Decision:** Notebooks use a tailored doc shape (Purpose / Inputs - data
  sources / Analysis - transformations / Outputs - artifacts / How - when to run
  / Source) instead of the `.py` Module Doc template, since notebooks are linear
  analyses, not reusable modules with public interfaces. Outputs/artifacts are
  described from the *code*, never from observed execution output.
- **Rationale:** The `.py` sections (Usage, public-interface contracts) read as
  filler for notebooks.
- **Applies to:** codeguide-templates (defines it), codeguide-skills (points to
  it).

## All Files Touched

- `plugins/codeguide/scripts/nb_digest.py`
- `plugins/codeguide/skills/codeguide-generate/SKILL.md`
- `plugins/codeguide/skills/codeguide-maintain/SKILL.md`
- `plugins/codeguide/skills/codeguide-update/SKILL.md`
- `plugins/codeguide/templates/DocumentationGuide.md`
- `plugins/codeguide/templates/cgignore.md`
- `plugins/codeguide/templates/config.yaml`
- `plugins/codeguide/unit_tests/test-nb-digest.py`
