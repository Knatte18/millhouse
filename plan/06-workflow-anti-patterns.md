# Batch: workflow-anti-patterns

```yaml
task: 6 — mill-go SKILL.md prose + lock-API + lock-coverage + Builder-oppførsel
batch: workflow-anti-patterns
cards: 1
verify: null
depends-on: [wiki-lock-unification]
```

## Batch Scope

A one-card edit to `plugins/mill/skills/workflow/SKILL.md` that does two things at once:

1. Updates the wiki lock-API guidance (currently line ~32: "Hold `_wiki.acquire_lock` only for shared wiki files…") to reflect that helpers own the lock after B01.
2. Adds two anti-pattern rules — "don't Read or Grep helper internals" and "don't write wrapper scripts for orchestration loops" — folding the durable corrective for #16, #19, and #81. The user explicitly placed these in `mill:workflow` (not `mill:conversation`) because they govern HOW to invoke skills/helpers, not response style.

Depends on B01 because the rewritten wiki-lock prose references `_wiki.wiki_lock` and the new internal-locking helpers. The anti-pattern rules themselves are independent of B01 but ship in the same card to keep workflow/SKILL.md edits to a single commit.

## Cards

### Card 24: Update workflow/SKILL.md wiki-lock prose + add two anti-pattern rules

- **Reads:**
  - `plugins/mill/skills/workflow/SKILL.md`
  - `plugins/mill/scripts/_wiki.py`
- **Modifies:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Creates:** none
- **Requirements:** In the `## Wiki mutations` section (currently around line 30–34), replace the existing paragraph with: "Wiki edits go through `_wiki.write_commit_push(wiki_path, paths, msg, slug=...)` (which acquires the wiki lock internally). For multi-operation read-modify-write windows (e.g. read Home.md → flip a phase → write back), wrap the whole sequence in `with _wiki.wiki_lock(wiki_path, slug):` — the inner `write_commit_push`'s lock acquire becomes a no-op via the held-lock counter. Never edit wiki files via raw `Edit` / `Write` — that bypasses the commit + push and the lock, leaving the wiki out of sync across machines. Per-task working state (`status.md`, `discussion.md`, `plan/`, `reviews/`) is NOT in the wiki — it lives at the worktree root on the task branch. Only `Home.md` and `_Sidebar.md` belong in the wiki." Add a new section `## Anti-patterns` after `## Wiki mutations` containing two numbered rules: (1) "**Don't Read or Grep helper internals.** When a SKILL.md names a helper to call, call it. Signatures are documented in the calling SKILL.md (mill-go's Principles section makes this explicit). If a helper fails, handle the exception then. Reading a helper's source to predict failure wastes turns and inverts the API contract — that's why the helpers exist. *Reasons preserved from incidents #16, #81.*" (2) "**Don't write wrapper scripts for orchestration loops the SKILL.md describes inline.** If the SKILL says 'for each round N do X, Y, Z', execute X, Y, Z as separate tool calls per round. The user must be able to see and interrupt each round. A script that packages a *transactional* operation (e.g. one implementer-spawn step) is fine because the operation is a unit; a script that packages a *loop* is not, because the loop is the orchestrator's behavior. *Reason preserved from incident #19.*" Place the new section between `## Wiki mutations` and `## Language Detection` so the anti-patterns are seen before language-specific routing.
- **Commit:** `docs(workflow): update wiki-lock prose + add anti-pattern rules`

## Batch Tests

No `verify:` command — pure SKILL.md prose. Effectiveness is measured at the next mill-go integration run: zero Builder reads of helper source, zero `.scratch/` wrapper scripts for the per-round review loop, correct invocation of `_wiki.write_commit_push` without external `acquire_lock` / `release_lock` calls.
