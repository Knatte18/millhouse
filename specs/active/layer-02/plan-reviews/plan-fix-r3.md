# Plan Fix Report — Round 3

```yaml
round: 3
applied_on: 2026-04-20
review_file: plan-reviews/holistic-r3.md
protocol: mill-receiving-review (v1 legacy skill)
```

The round-3 review returned APPROVE with 6 NITs. Decision-tree applied per
finding before any change. Summary:

## Fixed

- **NIT 01** (`Write → Glob` not in Shared Decisions): added a new
  `### Decision: run_tool_use exposes Read,Grep,Glob …` entry in
  `00-overview.md`'s Shared Decisions section, citing Decision 24 as the
  rationale. Also added a companion `### Decision: Code-review diff
  baseline via git merge-base main HEAD` while I was there, since that
  was also an implementation refinement deserving surface area.

- **NIT 03** (`root:` resolution underspecified): Step 10 now says "if
  `root:` is absent, resolve as `project_root / path`; if present, resolve
  as `project_root / root / path`." One sentence covers both cases.

- **NIT 04** (`subprocess.run` vs `_subprocess_util.run`): Step 11's git
  commands now use `_subprocess_util.run` with `cwd=project_root, timeout=30`.
  The requirement's closing note was rewritten to forbid bare `subprocess`
  imports for git in the backend.

- **NIT 05** (`git apply` needs existing base file): Step 16 fixture spec
  now explicitly requires `project/base-file.py` in the base commit, and
  the patch modifies this same file. Prevents "does not match index"
  failures.

- **NIT 06** (`scope="holistic"` notation vs actual call): Step 11 item 11
  now reads "no `scope` kwarg — code's canonical filename is
  `<ts>-code-review-r<N>.md` (no batch suffix); the `"holistic"` string
  appears only in the ReviewResult entry to match the unified shape."
  Prose / call now consistent.

## Pushed Back

- **NIT 02** (`check_mode` error message uses `reviewer.MODE` where
  `expected_mode` belongs).
  **Evidence:** `specs/active/layer-02/discussion.md` — the "Mode mechanics"
  section explicitly gives the canonical message as
  `"No bulk template exists for discussion review. Configure a tool-use
  reviewer."` Our current formulation
  `f"No {reviewer.MODE} template exists for {review_type} review. Configure a {expected_mode} reviewer."`
  produces exactly this message when `reviewer.MODE="bulk"` and
  `expected_mode="tool-use"`. The reviewer's suggested replacement
  `f"No {expected_mode} template exists …"` would produce
  `"No tool-use template exists for discussion review"` — which is factually
  wrong (we DO have a tool-use discussion template). The current spec is
  correct and matches discussion.md verbatim; changing it would contradict
  the canonical spec.

## Plan now at approved: true

All BLOCKING resolved across rounds 1–3. APPROVE verdict from r3. Fixer
report filed. `approved: true` set on `00-overview.md` frontmatter.
