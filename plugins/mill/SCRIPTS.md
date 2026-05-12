# mill scripts reference

Auto-generated from `--help` output. Re-generate when CLI signatures change:

```
cd <hub-root>
for script in plugins/mill/scripts/millpy-*.py; do
  uv run --project plugins/mill "$script" --help 2>/dev/null
done
```

## millpy-abandon

```
usage: millpy-abandon.py [-h] [--force]

Mark the current task abandoned.

options:
  -h, --help  show this help message and exit
  --force     Skip confirmation prompt and builder-lock guard.
```

## millpy-add

```
usage: millpy-add.py [-h] --title TITLE [--summary SUMMARY]
                     [--proposal-body PROPOSAL_BODY |
                     --proposal-body-file PROPOSAL_BODY_FILE]
                     slug

Append a task to the wiki Home.md (with optional proposal).

positional arguments:
  slug                  Task slug — kebab-case, e.g. 'fix-foo'. Must be unique
                        in Home.md.

options:
  -h, --help            show this help message and exit
  --title TITLE         Human-readable task title shown as the heading.
  --summary SUMMARY     One-paragraph description written below the heading.
  --proposal-body PROPOSAL_BODY
                        Long-form background as inline string. When provided,
                        creates proposal-<slug>.md at wiki root and links the
                        heading to it. For long bodies that may contain
                        heredoc-fragile characters (backticks, quotes), prefer
                        --proposal-body-file.
  --proposal-body-file PROPOSAL_BODY_FILE
                        Path to a UTF-8 file whose contents become the
                        proposal body. Use this for long bodies — it bypasses
                        shell heredoc quoting issues that mangle backticks and
                        quotes.
```

## millpy-claim

```
usage: millpy-claim.py [-h] [--slug SLUG] [--dry-run]

Claim a task from Home.md in the current working tree (in-place).

options:
  -h, --help   show this help message and exit
  --slug SLUG  Skip the picker and claim this specific slug (must be unmarked
               or [s]).
  --dry-run    Print what would happen; make no changes.
```

## millpy-cleanup

```
usage: millpy-cleanup.py [-h] [--apply]

Sweep done/abandoned task artefacts.

options:
  -h, --help  show this help message and exit
  --apply     Execute removals (default: dry-run).
```

## millpy-color

```
usage: mill-color [-h] color_name

Override the current worktree's VS Code titleBar color.

positional arguments:
  color_name  Palette color name; one of: blue, cyan, green, indigo, orange,
              purple, red, yellow

options:
  -h, --help  show this help message and exit
```

## millpy-inspect

```
usage: millpy-inspect.py [-h] [--json] [--since PHASE] [slug]

Deep dump of active task status files.

positional arguments:
  slug           Narrow to one slug.

options:
  -h, --help     show this help message and exit
  --json
  --since PHASE  Show only tasks at or after PHASE in the phase order.
```

## millpy-migrate-layout

```
usage: millpy-migrate-layout.py [-h] [--dry-run]

One-shot migration tool: moves an existing mill clone from the old
``hub/`` + ``worktrees/`` layout to the new ``wts/<repo>/`` + ``wts/<slug>/``
+ ``portals/`` layout.

Canonical step list: wiki/active/container-restructure/discussion.md
## Decisions → migration-strategy

Usage:
    python millpy-migrate-layout.py [--dry-run]

Options:
    --dry-run   Print planned operations with absolute paths and exit 0.
                No filesystem writes are performed.

Exit codes:
    0   Success (or successful dry-run).
    1   Pre-flight halt or any subprocess failure.

IMPORTANT: mill-setup MUST NOT be run between deploying the new mill
code and completing this migration. Run mill-setup AFTER the migration
completes (Step 6 instructs you to do this).

This script is NOT registered in _shortcuts.SHORTCUT_SCRIPTS because it
is intended for manual one-shot invocation outside the normal mill
workflow.

options:
  -h, --help  show this help message and exit
  --dry-run   Print planned operations and exit 0 without performing any
              writes.
```

## millpy-review-code

```
usage: millpy-review-code.py [-h] [--batch BATCH] [--extra-file EXTRA_FILE]
                             [--max-rounds MAX_ROUNDS]

Run a code review for the active task.

options:
  -h, --help            show this help message and exit
  --batch BATCH         Batch name from the plan's Batch Index. Omit for
                        holistic review.
  --extra-file EXTRA_FILE
                        Additional source file to include in the reviewer's
                        bulk. Repeat for each file. Typically supplied by the
                        orchestrator after a prior NEED_CONTEXT verdict.
  --max-rounds MAX_ROUNDS
                        Override roles.code-review.batch.rounds and
                        roles.code-review.holistic.rounds (overrides the
                        active scope) for this invocation. Default: use config
                        values.
```

## millpy-review-discussion

```
usage: millpy-review-discussion.py [-h] [--max-rounds MAX_ROUNDS]

Run a discussion review for the active task.

options:
  -h, --help            show this help message and exit
  --max-rounds MAX_ROUNDS
                        Override roles.discussion-review.holistic.rounds for
                        this invocation. Default: use config value.
```

## millpy-review-plan

```
usage: millpy-review-plan.py [-h] [--max-rounds MAX_ROUNDS] [--holistic-only |
                             --no-holistic] [--skip-validate]
                             [--skip-check CHECK]

Run a plan review for the active task.

options:
  -h, --help            show this help message and exit
  --max-rounds MAX_ROUNDS
                        Override roles.plan-review.batch.rounds and
                        roles.plan-review.holistic.rounds (overrides both
                        scopes) for this invocation. Default: use config
                        values.
  --holistic-only       Skip per-batch reviews; run only the holistic plan
                        review.
  --no-holistic         Skip the holistic plan review; run per-batch reviews
                        only.
  --skip-validate       Bypass the auto pre-review validator. Use only when
                        you know the validator is false-positive on a finding.
  --skip-check CHECK    Skip a named validator check (repeatable). Silently
                        ignores unknown names.
```

## millpy-skills-index

```
(no --help output; script regenerates SKILLS.md and exits 0)
```

## millpy-spawn

```
usage: millpy-spawn.py [-h] [--slug SLUG] [--dry-run]

Claim a task from Home.md and spawn a worktree for it.

options:
  -h, --help   show this help message and exit
  --slug SLUG  Skip the picker and claim this specific slug (must be unmarked
               or [s]).
  --dry-run    Print what would happen; make no changes.
```

## millpy-status

```
usage: millpy-status.py [-h] [--json] [--no-color] [--sort {slug,phase}]

Print mill task status table.

options:
  -h, --help           show this help message and exit
  --json
  --no-color
  --sort {slug,phase}
```

## millpy-terminal

```
(no --help output; opens Claude Code terminal in the active worktree and exits 0)
```

## millpy-validate-plan

```
(errors on --help; exit code 1 — see Generation notes)
```

## millpy-vscode

```
usage: mill-vscode [-h] [--slug SLUG] [--list]

Open VS Code in an active child worktree.

options:
  -h, --help   show this help message and exit
  --slug SLUG  Skip the picker and open the worktree for this slug.
  --list       Print active worktrees without launching VS Code.
```

## Generation notes

- `millpy-skills-index.py` — does not implement `--help`; invocation regenerates `SKILLS.md`.
- `millpy-terminal.py` — accepts `--help` (exit 0) but produces no stdout output.
- `millpy-validate-plan.py` — exits 1 on `--help`; excluded from sections above.
