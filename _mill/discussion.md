# Discussion: CodeGuide support for .ipynb

```yaml
task: CodeGuide support for .ipynb
slug: codeguide-jupyter-support
status: discussing
parent: main
```

## Problem

CodeGuide generates `_codeguide/` module docs for source files, but it has zero
awareness of Jupyter notebooks (`.ipynb`). A repo that contains notebooks today
gets no docs for them, and worse: if a project simply adds `.ipynb` to its
`config.yaml` `source_extensions`, the doc-generating skills would read the raw
notebook with the **Read tool**, which renders a notebook *with all its execution
outputs* — embedded datasets, base64 figures, long stdout. For a real analysis
notebook that is megabytes of output, blowing the context budget for no
documentation value.

**Why now:** We want notebooks to be first-class documentable source in
CodeGuide, producing overviews comparable to what `.py` files get. The hard
requirement driving the design is token economy: when documenting a notebook,
CodeGuide must look **only at the input** (markdown + code cells) and must
**never** pull a notebook's produced outputs (datasets, figures, etc.) into
context.

## Scope

**In:**

- A new deterministic helper `plugins/codeguide/scripts/nb_digest.py` that
  converts a `.ipynb` into a compact text "digest" containing only markdown-cell
  text and code-cell source, with **all execution outputs stripped** and
  oversized code cells truncated. Printed to stdout.
- A hard rule, wired into the three doc skills, that a `.ipynb` is **only ever**
  accessed through `nb_digest.py` — never via the Read tool.
- A "Notebooks" subsection in `DocumentationGuide.md` defining a notebook-tailored
  doc shape, the verbatim-stem naming rule, and the never-Read-raw rule.
- Notebook handling in all three doc skills: `codeguide-generate`,
  `codeguide-update`, `codeguide-maintain`.
- Template touch-ups: add `.ipynb` to the commented examples in
  `templates/config.yaml`; add `.ipynb_checkpoints/` to `templates/cgignore.md`.
- Unit tests for `nb_digest.py` under `plugins/codeguide/unit_tests/`.

**Out:**

- Executing notebooks, validating they run, or reading/summarizing their
  *outputs* in any form. Outputs are discarded, never documented.
- Jupytext-paired representations (`.py:percent`, `.md` notebooks). A paired
  `.py` is already a normal `.py` source file and is handled by existing logic;
  we do not parse jupytext metadata or dedupe pairs.
- Making `.ipynb` recognized by default for all repos. Recognition stays
  opt-in per project via `source_extensions` (the existing mechanism;
  `/codeguide-setup .py .ipynb` already accepts the token). We only add it to
  the *example* comments, not the default active list.
- Any change to `resolve.py` / `resolve_scope.py` / `codeguide_commit.py`
  beyond what they already do — they are extension-agnostic and need no edits.
- Rich rendering of notebook outputs anywhere (the whole point is to drop them).

## Decisions

### nb-digest-helper

- Decision: Implement the truncation/strip logic as a deterministic Python
  helper `plugins/codeguide/scripts/nb_digest.py` that takes a notebook path and
  prints a plain-text digest to stdout. The doc skills run it via Bash and read
  its stdout instead of Read-ing the notebook.
- Rationale: The Read tool loads full notebook outputs into context before any
  prose guidance can act, so guidance alone cannot prevent the token blow-up.
  A helper strips outputs *at the source* so they never reach the model. This
  matches CodeGuide's existing thin-deterministic-helper pattern
  (`resolve_scope.py`).
- Rejected: (a) Prose-only guidance — Read still loads everything first.
  (b) Relying on the Read tool's default notebook rendering — no control over
  large embedded outputs; contradicts the task's explicit requirement.

### strip-all-outputs

- Decision: The digest discards **every** cell output entirely. For a code cell
  that had outputs, emit a single one-line marker noting that N outputs were
  omitted (no output content). Markdown cells are kept in full. Code-cell source
  is kept, subject to the oversized-cell cap below.
- Rationale: Outputs are produced data (datasets, figures, stdout) — never the
  "input" we document, and the dominant source of token bloat. A bare
  `[N outputs omitted]` marker signals a cell produced output without loading
  any of it.
- Rejected: (a) Truncating outputs to head+tail lines — still leaks output data
  and risks one huge early output crowding out everything. (b) A global output
  size budget — less predictable, still loads output bytes.

### never-read-raw-notebook

- Decision: A hard rule, stated in `DocumentationGuide.md` and in each of the
  three skills' source-reading steps: when a scoped/undocumented source file ends
  in `.ipynb`, obtain its content **only** by running
  `python ${CLAUDE_PLUGIN_ROOT}/scripts/nb_digest.py <path>` and reading stdout.
  Never call the Read tool on a `.ipynb`.
- Rationale: A single accidental Read of a notebook defeats the entire purpose.
  The rule must be explicit and repeated at every reading site.
- Rejected: Trusting the agent to "remember" to truncate — unreliable.

### cap-oversized-code-cells

- Decision: Code-cell source is kept by default, but any single code cell above
  an internal size threshold is truncated to a head+tail slice with a
  `# [code cell truncated: NNN lines omitted]` marker.
- Rationale: Code is the input we want, but a cell can contain a pasted inline
  data literal (e.g. a 5000-row array) that is "input" only in a technical
  sense and is pure token bloat. The cap is belt-and-suspenders for the token
  goal while preserving all real logic.
- Rejected: Keeping all code unconditionally — leaves the pathological
  inline-data-blob case unguarded.
- Note: the threshold is an internal tooling constant in `nb_digest.py`
  (suggested starting point: truncate cells over ~150 lines / ~6 KB to roughly
  head-100 + tail-20). It is *not* a code-derived doc value — it lives only in
  the helper. mill-plan picks the exact numbers; they are not a doc contract.

### verbatim-stem-naming

- Decision: A notebook's doc file uses the **verbatim filename stem** with the
  extension swapped to `.md`: `notebooks/01_explore.ipynb` →
  `_codeguide/modules/01_explore.md`. No PascalCase normalization for notebooks.
- Rationale: The operator's hard requirement is that the source↔doc round-trip
  be trivial in **both** directions. Verbatim stem makes the reverse
  (notebook → doc) a literal, zero-ambiguity transform (swap `.ipynb`→`.md`,
  same stem), and the forward (doc → source) is the existing mandatory
  `## Source` relative link. The Overview module table still lists the row.
- Rejected: PascalCasing the stem like `.py` docs do — `DataCleaning.md` could
  reverse to `data_cleaning`, `data-cleaning`, or `DataCleaning` and could be a
  `.py` or `.ipynb`, so reverse lookup needs the table. Less obvious at a glance,
  which is exactly what the operator wanted to avoid.
- Note: this means `modules/` may hold mixed casing (PascalCase `.py` docs +
  verbatim notebook docs). That is accepted. See the `name-collision` edge case
  for the rare `foo.py` + `foo.ipynb` clash.

### notebook-doc-shape

- Decision: Add a "Notebooks" subsection to `DocumentationGuide.md` defining a
  notebook-tailored doc structure, comparable in depth to a `.py` module doc but
  fitting a linear analysis: **Purpose** (what the notebook is for, why it
  exists), **Inputs / data sources** (what it reads — files, tables, params),
  **Analysis / transformations** (what it does, in plain language), **Outputs /
  artifacts** (what it *produces* — described from the code, never from observed
  output), **How / when to run** (entry assumptions, ordering vs other
  notebooks), **Source** (relative link to the `.ipynb`).
- Rationale: Notebooks are not reusable modules with public interfaces; the
  `.py` Module Doc sections (Usage, public-interface contracts) read as filler.
  A tailored shape keeps the docs useful and honest.
- Rejected: Reusing the `.py` Module Doc template unchanged — several sections
  fit notebooks poorly.

### robustness-and-kernels

- Decision: `nb_digest.py` skips non-standard input gracefully. Malformed /
  non-JSON / non-nbformat files: print a warning to stderr and exit non-zero
  with no stdout digest; the skills treat that as "skip + flag to user", never a
  crash that aborts a batch. Non-Python kernels (R, Julia, etc.) are documented
  normally — the digest reads cell source plus the kernel/language from
  notebook metadata and labels code fences accordingly.
- Rationale: A monorepo may have one bad notebook among many; a single failure
  must not block the run. Notebook documentation is kernel-agnostic.
- Rejected: Python-only + hard-fail — brittle; one bad file blocks everything.

### scope-all-three-skills

- Decision: Wire notebook handling into all three doc skills
  (`codeguide-generate`, `codeguide-update`, `codeguide-maintain`), plus the
  guide and templates.
- Rationale: If only generate handled notebooks, `update` (commit-time) and
  `maintain` (validation/repair) would re-read raw `.ipynb` during their
  accuracy checks — reintroducing the bloat and letting notebook docs go stale.
  Full coverage is required for the rule to hold end-to-end.
- Rejected: generate-only or generate+update — leaves reading sites that
  violate the never-Read-raw rule.

## Technical context

What mill-plan needs to know about the codebase:

- **"Source file" is entirely config-driven.** `_codeguide/config.yaml`'s
  `source_extensions:` list is the *only* place file types are recognized.
  `plugins/codeguide/scripts/resolve.py::load_source_extensions()` parses lines
  starting with `- .`. No script hardcodes a `.py`/`.cs` list. Therefore
  `.ipynb` needs **no script change** to be recognized — only config. The
  generate/update skills filter scope files to recognized extensions
  (`codeguide-generate` Steps 4-6; `codeguide-update` Step 4a).
- **Where source is read today (the sites to change):**
  - `codeguide-generate` Step 7 ("Read undocumented source files: Read only the
    source files that need new docs").
  - `codeguide-update` Step 4e (per source file: "Read the doc and the source
    file").
  - `codeguide-maintain` — wherever it re-reads source to validate doc accuracy
    (inspect its SKILL.md; add the same `.ipynb` → digest rule there).
  Each of these is where the "if `.ipynb`, use `nb_digest.py`, never Read"
  branch goes.
- **Round-trip machinery already exists and must be honored:**
  - doc → source: the mandatory `## Source` section with a relative markdown
    link (`DocumentationGuide.md` → "Source"). `codeguide-maintain` already
    validates these links resolve — that validation now also covers `.ipynb`
    targets for free.
  - source → doc: the Overview module table + the guide's two-step name lookup
    ("No searching required... never fall back to Grep/Glob").
- **Helper conventions to follow** (see `resolve_scope.py`): pure stdlib, a
  `def`-level public function for testability plus a `_cli(argv)` wrapper,
  stdout = the payload, stderr = diagnostics/JSON summary, exit codes
  documented in the module docstring. ASCII-only stdout (Windows cp1252;
  `—`→` -- `, `→`→` -> `). Notebook JSON is `json.load`-able stdlib; no third-
  party `nbformat` dependency is needed (and the venv may not have it) — parse
  the documented nbformat shape directly (`cells[].cell_type`,
  `cells[].source`, `cells[].outputs`, `metadata.kernelspec` /
  `metadata.language_info`).
- **Invocation form** for the helper from skills: it is plugin-internal, so use
  `python ${CLAUDE_PLUGIN_ROOT}/scripts/nb_digest.py <abs-path>` (mirrors how
  the skills already call `resolve.py` / `resolve_scope.py`).
- **`.ipynb_checkpoints/`** is the Jupyter autosave dir holding stale notebook
  copies. It belongs in `templates/cgignore.md` so it's skipped by default;
  add it alongside the existing `__pycache__/` etc. entries.

## Constraints

- No `CONSTRAINTS.md` was found at the hub root.
- Token economy is the governing constraint: the documenting agent must never
  load notebook *outputs* into context. This is why the helper strips at the
  source and why the never-Read-raw rule is non-negotiable.
- ASCII-only stdout from the helper (Windows cp1252 crashes on non-ASCII).
- Pure stdlib only — do not assume `nbformat`/`jupyter` packages are installed
  in the plugin venv.
- Do not edit `DocumentationGuide.md` "locally" in a consuming repo — it is
  owned by the plugin; the change is to the **plugin template**
  (`plugins/codeguide/templates/DocumentationGuide.md`) which seeds repos.
- Follow CodeGuide's doc rules: no API signatures, no code-derived
  values/constants in docs, no line-by-line walkthroughs.

## Testing

- **TDD candidate — `nb_digest.py`** (the one piece with real logic; pure,
  deterministic, no git/LLM). Unit tests at
  `plugins/codeguide/unit_tests/test-nb-digest.py`, registered with the existing
  `run-all.py` discovery (`test-*.py`). Build notebook fixtures as in-memory
  JSON dicts written to a tempfile — no real Jupyter. Cover:
  - All outputs stripped: a code cell with stream + image + data outputs yields
    code source + a `[N outputs omitted]` marker and **none** of the output
    bytes (assert the base64/data string is absent from stdout).
  - Markdown cells kept verbatim.
  - Oversized code cell truncated with the marker; normal code cell untouched.
  - Malformed / non-JSON input → non-zero exit, warning on stderr, empty stdout.
  - Non-Python kernel → code fences labeled with that language; still produces a
    digest.
  - Empty notebook (no cells) and outputs-free notebook → sensible minimal
    digest, no crash.
  - ASCII-only stdout (no raw non-ASCII bytes leak from cell content markers).
- **Not unit-testable (prose):** the guide subsection, the three skill edits,
  and the template additions. Validate by inspection / the discussion-and-plan
  review loop and, optionally, a light integration check: point
  `/codeguide-generate` at a small fixture notebook and confirm it (a) calls the
  digest helper, (b) never Reads the raw file, (c) emits a `<stem>.md` with the
  notebook doc shape and a resolving `## Source` link. Integration is optional;
  the unit suite on `nb_digest.py` is the must-have.

## Edge cases

- **Markdown-only notebook** (a narrative report): digest is just the markdown;
  documented with the Purpose/Inputs/Outputs shape (Analysis section may be
  thin). Still gets a doc.
- **Notebook with execution errors in outputs:** outputs are stripped anyway, so
  error tracebacks never reach context — no special handling.
- **Very large notebook (hundreds of cells):** digest size is bounded by
  markdown + code source (outputs gone, oversized code cells capped); acceptable.
- **Name collision `foo.py` + `foo.ipynb` in the same folder:** verbatim
  notebook stem (`foo.md`) can collide with the `.py` doc on case-insensitive
  filesystems (Windows). Resolution: apply the guide's existing collision rule —
  disambiguate via a sub-area folder — and the operator/agent picks distinct
  names. Rare; note it in the guide subsection rather than building special
  logic.
- **Notebook stem with spaces/dots** (`1. Data Cleaning.ipynb`): verbatim stem
  keeps the name as-is (`1. Data Cleaning.md`). Allowed; the `## Source` link and
  Overview row carry the exact name.
- **`.ipynb_checkpoints/` copies:** skipped via the cgignore addition; never
  documented.
- **Notebook not listed in `source_extensions`:** not recognized — expected;
  recognition is opt-in per project.
- **Jupytext-paired `.py`:** treated as an ordinary `.py` source file by existing
  logic; the helper and notebook rules do not touch it.

## Q&A log

- **Q:** How should the truncate/skip-large-output logic be implemented? **A:** Deterministic digest helper (`nb_digest.py`); skills call it instead of Read.
- **Q:** What should the reading logic do with cell outputs? **A:** Strip all outputs entirely — the operator stressed CodeGuide must look only at the *input* (markdown + code) and never load produced datasets/figures, which would cost far too many tokens.
- **Q:** How should a notebook's doc be structured? **A:** Notebook-tailored shape in DocumentationGuide.md (Purpose / Inputs / Analysis / Outputs / How-to-run / Source), not the `.py` Module Doc template.
- **Q:** Which skills/artifacts get notebook handling? **A:** All three skills (generate, update, maintain) + guide + template config.
- **Q:** Guard against oversized *code* cells too? **A:** Yes — cap a single oversized code cell (e.g. pasted inline data) with a truncation marker; keep normal code intact.
- **Q:** Filename → doc-name mapping (round-trip must be trivial both ways)? **A:** Verbatim stem (`01_explore.ipynb` → `01_explore.md`); reverse is a literal `.ipynb`→`.md` swap, forward is the `## Source` link. No PascalCase for notebooks.
- **Q:** Handle malformed / non-Python notebooks? **A:** Skip malformed gracefully (warn + skip, no crash); document any kernel (kernel-agnostic).
- **Q:** Never accidentally Read a raw `.ipynb`? **A:** Hard rule in guide + all three skills: `.ipynb` content comes only from `nb_digest.py` stdout; Read tool on a notebook is forbidden.
