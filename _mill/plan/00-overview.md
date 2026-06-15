# Plan: Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading

```yaml
task: "Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading"
slug: batch-name-and-skill-loading
approved: true
started: "20260615-125429"
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: filename-sanitization
    file: 01-filename-sanitization.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-paths-sanitize.py test-agent-dispatch.py
  - number: 2
    name: skill-injection
    file: 02-skill-injection.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-language-skills-directive.py test-review-common.py test-agents-defs.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: sanitize-only-filenames

- **Decision:** Filename sanitization applies ONLY to the batch-name string when it becomes a *filename component* (brief filename, cleanliness-snapshot filename). Everywhere the batch name is a logical identifier — status `set_batch_fields`, the prepare/finalize JSON envelope `scope` field, log lines, plan lookups — the **raw** batch name is preserved unchanged.
- **Rationale:** A batch like `Core fix: emit_prepare` must still be found by name in the overview and status; only its on-disk filename needs to be Windows-safe. Conflating the two would break batch lookup.
- **Applies to:** all batches

### Decision: full-windows-unsafe-set

- **Decision:** The sanitizer replaces every character in the full Windows-reserved set — colon, backslash, forward-slash, asterisk, question-mark, double-quote, less-than, greater-than, pipe — with a single hyphen `-`, via one `re.sub(r'[:\\/*?"<>|]', '-', name)`.
- **Rationale:** The two filed bugs are `:` (NTFS ADS) and `/` (path separator), but `*?"<>|` corrupt NTFS filenames the same way; defending the whole set once removes the entire bug class.
- **Applies to:** all batches

### Decision: targeted-skill-injection

- **Decision:** Language-skill loading is driven by a non-optional, targeted directive injected into the per-batch briefs, built from the batch's **touched** files only — the `Edits:` and `Creates:` tokens, NOT `Context:` (read-only references must not trigger a style directive). `code-quality` is ALWAYS named; each detected language additionally contributes `{lang}-comments` and `{lang}-testing`. Only languages with skill plugins are detected: Go (`.go`), Python (`.py`), C# (`.cs`).
- **Rationale:** Spawned Haiku implementers are weak at voluntarily loading skills (#483 observed failure). A targeted "load these now" directive beats self-detection; naming a non-existent `{lang}-comments` skill would be a dead directive, so only the three installed language plugins are mapped.
- **Applies to:** skill-injection

### Decision: python-verify-isolation

- **Decision:** Every `verify:` command is prefixed with the literal token `PYTHONPATH= ` (empty value, single space) so the test subprocess does not inherit the cache `PYTHONPATH` and load V2-cache modules instead of worktree code. Tests run via `uv run --project plugins/mill`.
- **Rationale:** mill-v2 convention (CLAUDE.md `## Script invocation`); enforced by the `verify-not-isolated` validator for Python projects.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch, sorted
alphabetically. mill-go reads this to warn if two parallel batches
touch the same file — a sign of a misplaced dependency._

- `plugins/mill/agents/mill-implementer.md`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-agents-defs.py`
- `plugins/mill/unit_tests/test-language-skills-directive.py`
- `plugins/mill/unit_tests/test-paths-sanitize.py`
