---
name: mill-add
description: Turn the conversation that just ended into a task entry in the wiki. Derive a slug, title, and one-paragraph summary; optionally extract a proposal file for long-form background. Wraps `millpy-add.py` — the script handles the wiki lock, file writes, sidebar regeneration, and commit/push. You handle the judgment.
---

# mill-add

A thin skill wrapping `plugins/mill/scripts/millpy-add.py`. Use it when the user and you have just discussed something that deserves to be tracked as a task, and the user says "log this" / "legg det inn som en task" / similar.

The script is mechanical (write files, regenerate sidebar, commit, push). The skill is judgment-heavy — you decide:

1. What slug captures the task concisely
2. What title reads well as a wiki heading
3. What the ~1-paragraph Home.md summary should say
4. Whether the discussion is substantive enough to extract as a `proposal-<slug>.md`

## When the user invokes me

Typical triggers:

- "Log this as a task."
- "Legg det inn i Home.md."
- "Lag en proposal for dette og legg den i backlog."
- Any request that amounts to "persist the conclusions of this conversation into the wiki backlog".

Preconditions:

- `.millhouse/wiki` junction exists (if not: run `/mill-setup` first)
- Working directory is a mill-enabled clone (hub or any worktree)

## How to derive the fields

### Slug (required)

Kebab-case, matches `[a-z][a-z0-9-]*`. Aim for 2–4 words. Prefer **what** over **where**:

- ✅ `reviewers-cache-warmup` — names the thing being done
- ❌ `mill-review-improvement` — too generic
- ❌ `fix-bug-42` — issue numbers age poorly

If you are unsure, propose a slug and ask the user to confirm or edit before running the script.

### Title (required)

Human-readable, sentence-case. This is the heading users see in Home.md. Examples:

- Slug: `reviewers-cache-warmup` → Title: `Warm reviewer caches on startup`
- Slug: `rewrite-plan-validator` → Title: `Rewrite the plan validator for the flat card format`

Keep titles under ~60 characters — longer headings wrap awkwardly in the GitHub Wiki sidebar.

### Summary (optional but usually wanted)

One paragraph (≤150 words) that captures the problem and the rough approach. This goes straight below the heading in Home.md. Write prose, not a bullet list. Past tense ("we decided…") is fine; future tense ("we will…") is fine too. Do not include code blocks or headings here.

If the conversation did not produce enough for a summary, pass just `--title` and skip `--summary`.

### Proposal body (optional)

Extract when the discussion produced substantive background the user will want to re-read later. Heuristic: **more than ~150 words or more than 3 paragraphs** of substantive content (not counting your own clarifying questions). When in doubt, ask the user whether a proposal file is wanted.

The proposal body is free-form markdown. Suggested structure when the conversation covers multiple concerns:

```markdown
# <Title> — background

## Why

<what problem prompted this task; what is the current state>

## What needs to happen

<the rough plan or options discussed>

## Dependencies / open questions

<anything blocking or still unresolved>

## Related

<links to specs, issues, other tasks>
```

The structure is a suggestion, not a contract. Match it to what the discussion actually covered.

## How to call the script

```bash
# WRONG — invokes from source tree
uv run --project plugins/mill plugins/mill/scripts/millpy-add.py <slug>

# RIGHT — invokes from cache
uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-add.py" <slug>
```

```powershell
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-add.py" <slug> `
    --title "<Title>" `
    --summary "<summary paragraph>" `
    --proposal-body "<proposal body in markdown>"    # omit when no proposal
```

Notes:

- `--proposal-body` accepts arbitrary markdown as a single string. For long bodies, write the content to a temp file first and read it into the argument — PowerShell handles heredoc-style strings via `@"..."@` or `Get-Content -Raw`.
- For bodies longer than ~30 chars or containing backticks/quotes, prefer `--proposal-body-file <path>` — write the body to a temp file (e.g. `.scratch/proposal-<slug>.md`) and pass the path. Avoids heredoc-quoting issues that mangle markdown.
- The script acquires the wiki lock, so never run two mill-add invocations in parallel.
- A duplicate slug is a hard error — the script exits 1 without writing anything.

### Example — short task, no proposal

```powershell
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-add.py" sidebar-tasks-alphabetise `
    --title "Alphabetise the Tasks section in _Sidebar.md" `
    --summary "The sidebar currently lists tasks in Home.md order. For easier scanning once we have more than 5 tasks, sort them alphabetically by slug at render time. Purely a _sidebar.py change; no new format."
```

### Example — task with short proposal body

```powershell
$body = @"
# Ensemble reviewer — background

## Why

Single-reviewer runs catch most issues, but we saw N false negatives ...

## What needs to happen

1. Script at `plugins/mill/scripts/mill-review-ensemble.py`
2. ...

## Open questions

- Which worker-set default?
- Does ensemble need its own prompt variant?
"@

uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-add.py" mill-review-ensemble `
    --title "Add ensemble reviewer script" `
    --summary "Spawn N workers, aggregate findings via a handler model. Separate script, not part of core mill-review." `
    --proposal-body $body
```

### Example — task with proposal (file-based)

Write the body to a temp file first, then pass the path. Recommended for any body longer than ~30 characters or containing backticks, code fences, or quotes.

```powershell
Set-Content .scratch/proposal-mill-review-ensemble.md @"
# Ensemble reviewer — background

## Why

Single-reviewer runs catch most issues, but we saw N false negatives ...

## What needs to happen

1. Script at `plugins/mill/scripts/mill-review-ensemble.py`
2. ...

## Open questions

- Which worker-set default?
- Does ensemble need its own prompt variant?
"@

uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-add.py" mill-review-ensemble `
    --title "Add ensemble reviewer script" `
    --summary "Spawn N workers, aggregate findings via a handler model. Separate script, not part of core mill-review." `
    --proposal-body-file .scratch/proposal-mill-review-ensemble.md
```

## After the script succeeds

1. Tell the user what got added: slug, title, whether a proposal file was written, and the wiki commit SHA.
2. If you set up a TODO / follow-up, remind the user it lives in the wiki now — they can pick it up later with `/mill-spawn <slug>`.

## Error handling

| Script exit | Likely cause | What you do |
|---|---|---|
| `Invalid slug ...` | Slug fails the regex | Ask user for a new slug that matches `[a-z][a-z0-9-]*` |
| `No .millhouse/wiki junction found` | mill-setup has not run in this clone | Offer to run `/mill-setup` |
| `Slug ... already present in Home.md` | A task with that slug already exists | Show the existing entry; ask user whether to pick a new slug or update the old task (update = out-of-scope for mill-add; edit wiki manually or wait for mill-groom) |
| `Proposal file ... already exists` | Stale proposal from a previous aborted run | Show the user the existing file; ask whether to reuse its content or pick a new slug |
| `git push failed ...` | Network, auth, or concurrent writer | Surface stderr verbatim; suggest rerun |

## Non-goals for this skill

- Editing an existing task — use manual wiki edit or wait for `mill-groom` (Layer 04)
- Deleting a task — same
- Creating a worktree for the task — that is `/mill-spawn` (Layer 03)

Keep this skill focused on "new task → wiki entry". Everything else belongs in another skill.
