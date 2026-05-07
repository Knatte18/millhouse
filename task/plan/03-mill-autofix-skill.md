# Batch: Mill-autofix skill

```yaml
task: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)
batch: Mill-autofix skill
number: 3
cards: 2
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1, 2]
```

## Batch Scope

This batch writes the main deliverable: `plugins/mill/skills/mill-autofix/SKILL.md`. It also regenerates `SKILLS.md` at the repo root. The skill is a complete Claude Code skill session spec — it does not delegate to a sub-LLM; all orchestration runs inside the single CC session that invokes `/mill-autofix`. Batch 1's `_autofix.slug_from_title` and the `label_filter`-enabled `_gh_issues.fetch` are the Python interfaces consumed. Batch 2's `pipeline.autonomous_mode` key and mill-plan/mill-go guards are the behavioral contracts consumed.

Batch-local decision — **SKILL.md frontmatter format**: `---\nname: mill-autofix\ndescription: ...\n---` (standard mill skill frontmatter, per `mill-skills-index` expectations).

## Cards

### Card 8: Create `plugins/mill/skills/mill-autofix/SKILL.md`

- **Context:**
  - `plugins/mill/scripts/_autofix.py`
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/scripts/millpy-add.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_constraints.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_timestamp.py`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-autofix/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
- **Deletes:** none
- **Requirements:** Write `plugins/mill/skills/mill-autofix/SKILL.md` as a complete, self-contained Claude Code skill definition. The file MUST include: (1) YAML frontmatter with `name: mill-autofix` and a one-sentence description; (2) all five phases from the discussion's "Mill-autofix skill flow": Entry, Fetch, Pre-flight, Per-bug loop, Cleanup, Report; (3) exact invocation patterns for every CLI call using `${CLAUDE_PLUGIN_ROOT}` (not source-tree paths); (4) all decision decisions from the discussion: execution-model, discussion-md-synthesis, autonomous-mode-flag, label-filter-implementation, slug-derivation, stuck-task-cleanup, issue-close-on-success, killswitch. Key implementation details the SKILL.md must specify precisely: (a) Arguments: `--dry-run` (reads only, prints table, exits; config NOT mutated) and `--max-bugs N` (default unlimited); (b) config.local.yaml mutation: read original, set `pipeline.autonomous_mode: true` using `yaml.safe_load`/`yaml.dump`, always restore in a cleanup step (try/finally equivalent — runs on success, block, or error); (c) `_gh_issues.fetch(label_filter=["bug"])` call; (d) `_autofix.slug_from_title(title, existing_home_slugs, issue_number)` where `existing_home_slugs` is the set of slugs already present in `Home.md` (parse via `_wiki.read_home_slugs` or equivalent); (e) `millpy-add.py <slug> --title "<title>" --summary "<issue body first 200 chars>"` — on exit 1 with "already present": parse Home.md phase marker, skip if `[active]` or `[done]`, proceed to claim if unmarked; (f) pre-claim dirty-tree check: `git status --porcelain`, if non-empty run `git clean -fd task/` before claiming; (g) `millpy-claim.py --slug <slug>` — exits 0 on success, 1 on failure (halt and record); (h) codebase exploration (Glob/Grep/Read) for the specific bug, then write `task/discussion.md` covering all sections (Problem, Scope, Decisions, Technical context, Constraints from `_constraints.read_if_exists()`, Testing, Q&A log); (i) commit discussion.md: `git add task/discussion.md && git commit -m "mill-autofix: write discussion.md for <slug>"` then push; (j) invoke `/mill-plan` and check `task/status.md` `phase:` after it returns; (k) invoke `/mill-go` and check `task/status.md` `phase:` after it returns; (l) invoke `/mill-merge` (in-place mode auto-detected); (m) success detection: `git branch --show-current == parent_branch`; extract squash SHA via `git log --oneline -1 <parent_branch>`; (n) `_gh_issues.close_with_comment(issue_number, f"Autonomously fixed by mill-autofix. Squash commit: {sha}")` on success; (o) killswitch: check `.scratch/autofix-stop` after each bug, halt without deleting the file if present; (p) write `.scratch/autofix-report.md` with Date/time, issues fetched, --max-bugs applied, Fixed list (slug, issue #, title, commit SHA), Stuck list (slug, issue #, title, phase-at-block, blocked_reason), Errored list. Stuck cleanup helper (used on block or unexpected phase): `git clean -fd task/`, `git checkout <parent_branch>`, `rm .millhouse/active.slug.md`, record in stuck list.
- **Commit:** `feat(mill-autofix): add mill-autofix SKILL.md`

### Card 9: Regenerate `SKILLS.md`

- **Context:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
  - `plugins/mill/scripts/millpy-skills-index.py`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** From the worktree root, run `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"`. This script scans all `SKILL.md` files under `plugins/` and regenerates `SKILLS.md` at the repo root. Verify that `SKILLS.md` now contains an entry for `mill-autofix`. Commit the updated `SKILLS.md`: `git add SKILLS.md && git commit -m "chore: regenerate SKILLS.md with mill-autofix entry"`.
- **Commit:** `chore: regenerate SKILLS.md with mill-autofix entry`

## Batch Tests

Verify command: `python plugins/mill/unit_tests/run-all.py`. This confirms no regressions in the Python unit tests (which cover `_autofix.slug_from_title` from Batch 1). The SKILL.md files have no automated unit tests; correctness is verified by Plan Review and by running mill-autofix against a real bug after merge.
