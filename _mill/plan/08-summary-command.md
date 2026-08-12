# Batch: summary-command

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "summary-command"
number: 8
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-summary.py
depends-on: [3]
```

## Batch Scope

Delivers the user-facing read side: a new `millpy-review-summary.py` CLI plus its thin
`mill-review-summary` skill wrapper, printing one row per review file for the active task — round,
type, scope, verdict, model, effort, duration, tool-calls, cost. It reads only what is already on
disk, so it depends on batch 3's field definitions but on none of the write-side batches; review
files written before this task render `n/a` per missing cell.

The schema doc gains the three new metadata rows in the same batch, since it is the canonical
description of exactly the header this command parses.

## Cards

### Card 30: the summary CLI

- **Context:**
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-review-summary.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  New CLI following `millpy-status.py`'s conventions: module docstring with a Usage line, the same
  `_SCRIPTS = Path(__file__).resolve().parent; sys.path.insert(0, str(_SCRIPTS))` preamble, and
  `main()` returning an int under `if __name__ == "__main__": sys.exit(main())`.
  Flags: `--slug` (override active-slug detection), `--json` (dest `json_mode`), `--no-color`,
  `--sort` with choices `round` (default) and `scope`.
  Structure the module around three testable units so the unit test never needs a worktree:
  - `parse_review_filename(name: str) -> dict | None` — returns `{"round": int, "type": str, "scope": str}`
    for the canonical patterns documented in `plugins/mill/templates/review-output.schema.md`
    (`<ts>-<type>-review-r<N>.md` with scope `holistic`, and the batch-scoped
    `<ts>-<type>-review-<batch-name>-r<N>.md` with the batch name as scope), and `None` for anything
    else — notably the `*-fix-r<N>.md` fixer reports that share the reviews dir and must never appear
    as rows. The batch-scoped form is emitted for **both** `plan` and `code` review types by
    `write_review_file` (its filename branch is `review_type in ("plan", "code") and scope not in
    (None, "holistic")`), so per-batch code reviews — the artifact mill-go produces for every batch —
    must parse exactly like per-batch plan reviews. Mirror `_review_common`'s own `RE_BATCH`
    `type=plan|code` alternation rather than hard-coding `plan`.
  - `build_rows(reviews_dir: Path, registry: dict | None = None) -> list[dict]` — walks
    `reviews_dir.rglob("*.md")` (rglob, so `revise-<N>/` subdirectories written by mill-plan's
    `--revise` mode are included), keeps files `parse_review_filename` accepts, and for each one
    extracts the first fenced ` ```yaml ` block via a `re.search(r"```yaml(.*?)```", text, re.DOTALL)`
    and `yaml.safe_load`. Every yaml-derived cell is `None` when the block is missing, unparseable,
    or lacks the key — this function never raises on a malformed file. Row keys: `round`, `type`,
    `scope`, `verdict`, `model` (from `reviewer_model`), `effort`, `duration_s`, `tool_calls`,
    `cost_usd`, `file` (the file's name). When the yaml block carries its own `round`, prefer the
    filename-derived value and keep the yaml one only when the filename yielded none — the filename
    is written by `write_review_file` and the header by the reviewer. `effort` is resolved from
    `registry` by looking `model` up via `_reviewers.resolve`; when `registry` is `None`, the alias
    is unknown, or resolution raises, `effort` is `None`.
  - `render_table(rows: list[dict], *, no_color: bool, sort_by: str) -> None` — the same
    width-computed, ` | `-joined table `millpy-status.py` renders, with headers
    `ROUND`, `TYPE`, `SCOPE`, `VERDICT`, `MODEL`, `EFFORT`, `DURATION`, `TOOLS`, `COST`. Every
    `None` cell renders as the literal `n/a`. Colour the `VERDICT` column only, reusing
    `millpy-status.py`'s `sys.stdout.isatty() and not no_color` gate: green for `APPROVE`, red for
    `REQUEST_CHANGES`, magenta for `ERROR`/`NEED_CONTEXT`.
  Add a module-level `format_duration(seconds: float | None) -> str` rendering `None` as `n/a`,
  under 60 seconds as `"{n}s"` (integer seconds), and otherwise as `"{m}m{ss:02d}s"`. `cost_usd`
  renders as `$0.4212` (four decimals); `tool_calls` renders as a plain integer.
  `main()` resolves `git_root` via `_paths.resolve_git_root()`, the hub via
  `_paths.resolve_hub_path()`, `wiki_root` via `_paths.resolve_wiki_path(git_root)`, `cfg` via
  `_review_common.load_config`, the slug via `--slug` or
  `_review_common.find_active_slug(<hub>, wiki_root, cfg)` (which takes the wiki path as its second
  positional argument — hence the `wiki_root` resolution), and `reviews_dir` via
  `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)`; the registry via
  `_reviewers.load(<hub>)` wrapped so a registry failure degrades to `None` rather than aborting the
  table. When `reviews_dir` does not exist or `build_rows` returns nothing, print
  `no review files found for <slug>` to stdout and return 0. `--json` prints
  `json.dumps(rows, indent=2)` with raw numeric values (never the display strings) and returns 0.
  All printed output is ASCII only, per the repo's cp1252 constraint.
- **Commit:** `feat(review): add millpy-review-summary per-task cost/verdict table`

### Card 31: unit tests for the summary CLI

- **Context:**
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-summary.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  New `test-<name>.py` following the directory's conventions: a `main()` returning an int, one
  `PASS:`/`FAIL:` line per case, `sys.exit(main())` at the bottom, `tempfile`-based fixtures only
  (no real git, no LLM, nothing written outside the temp dir). Load the CLI module by path with
  `importlib.util` the way the other CLI-level tests in this directory do, since its filename is not
  importable as a module name.
  Cases:
  - `parse_review_filename` accepts `20260418-001200-discussion-review-r1.md` (round 1, type
    discussion, scope holistic), `20260418-143300-plan-review-03-templates-r2.md` (round 2, type
    plan, scope `03-templates`), `20260418-143300-code-review-05-cards-r3.md` (round 3, type code,
    scope `05-cards` — the per-batch code review case), `20260418-143300-code-review-r5.md`, and
    rejects `20260418-143300-plan-fix-r2.md` and an arbitrary non-review filename.
  - `build_rows` over a fixture dir mixing a new-format file (all three fields present), an
    old-format file (none present), a file whose yaml block is malformed, and a file with no yaml
    fence at all: all four produce rows, the missing cells are `None`, and nothing raises.
  - A fixture file inside a `revise-1/` subdirectory is included in the rows (rglob coverage).
  - Rows are sorted by round then scope by default.
  - `format_duration` renders `None` as `n/a`, `37.4` as `37s`, and `252.0` as `4m12s`.
  - `render_table` output (captured from stdout with `--no-color` semantics) contains the literal
    `n/a` for every missing cell and one line per row plus a header and separator.
  - The `--json` shape carries raw numbers: `duration_s` stays a float, not `"4m12s"`.
- **Commit:** `test(review): cover millpy-review-summary row building and rendering`

### Card 32: skill wrapper

- **Context:**
  - `plugins/mill/skills/mill-status/SKILL.md`
  - `plugins/mill/scripts/millpy-review-summary.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-review-summary/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  A thin wrapper mirroring `mill-status`'s shape: YAML frontmatter with `name: mill-review-summary`
  and a one-line `description:` starting lowercase ("print a per-task table of review rounds:
  verdict, model, effort, duration, tool-calls, cost."), an H1, two or three sentences on when to
  reach for it, and a `## Run it` fenced bash block using the standard
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-summary.py" [--slug <slug>] [--json] [--no-color] [--sort {round,scope}]`
  invocation form.
  Add a short `## Reading the table` section stating which cells can legitimately be `n/a`: every
  cell for review files written before this feature existed; `tool_calls` and `cost_usd` for any
  round dispatched in agent-mode or through psmux; `tool_calls`/`cost_usd` for every gemini-provider
  round; and `effort` when `reviewer_model` names something the reviewer registry does not resolve.
  Do not add the script to `_shortcuts.py`'s `SHORTCUT_SCRIPTS` — that list deliberately excludes
  review-scoped commands.
- **Commit:** `docs(skills): add mill-review-summary skill wrapper`

### Card 33: schema doc rows and regenerated skills index

- **Context:**
  - `plugins/mill/skills/mill-review-summary/SKILL.md`
  - `plugins/mill/scripts/millpy-skills-index.py`
- **Edits:**
  - `plugins/mill/templates/review-output.schema.md`
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the schema doc's `## Metadata block fields` table, add three rows after `reviewer_model`:
  `duration_s` (number, required: no, wall-clock seconds for the whole round including any
  resume-retry or fast-fail-retry), `tool_calls` (integer, required: no, tool-use blocks the reviewer
  made, or the CLI's native turn count when it reports one), `cost_usd` (number, required: no,
  reported dollar cost of the round). Show them in the `## File format` sample block too, and add a
  sentence below the table stating these three are orchestrator-supplied like `reviewer_model` (via
  the review CLIs' `--duration-s`/`--tool-calls`/`--cost-usd` finalize flags), that `tool_calls` and
  `cost_usd` are absent under agent-mode and psmux dispatch and for the gemini provider, and that
  files written before this feature carry none of the three — readers must treat all three as
  optional.
  Regenerate `SKILLS.md` rather than hand-editing it (its header says so) by running the standard
  cache-form invocation CLAUDE.md mandates for operational calls —
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"`
  — with cwd the worktree root so the script's own repo-root resolution still lands on the worktree.
  Then confirm the diff contains exactly the one new
  `mill-review-summary` row and no unrelated churn.
- **Commit:** `docs(review): document duration/tool-call/cost metadata fields`

## Batch Tests

`verify:` runs `test-review-summary.py`, the new unit test created by this batch and the only
automated coverage of the new CLI. The two documentation edits in card 33 have no runnable surface;
the `SKILLS.md` regeneration is verified by inspecting its diff, as the file is script-generated.
