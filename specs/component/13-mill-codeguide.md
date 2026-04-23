# codeguide seed for the hub repo

```yaml
type: one-shot setup
layer: bookkeeping (no code work)
status: placeholder — deferred until mill-v2 is self-sufficient enough to run /codeguide-setup + /codeguide-generate through the mill workflow
note: "The codeguide plugin is already shipped (plugins/codeguide/) with codeguide-setup/-generate/-update/-maintain. The hub repo just hasn't been seeded. Do not seed manually."
```

**For the thread that will eventually run this:** the infrastructure is done; there is no code to write. Codeguide can live either **inline** (`<repo>/_codeguide/`) or in a **sibling** repo (`<container>/codeguide/` for hub-form, `<container>/<repo>.codeguide/` otherwise). `resolve.py` handles both transparently — the consuming skill doesn't care. The one-shot sequence is:

1. From hub root: invoke `/codeguide-setup` (inline) or `/codeguide-setup --sibling` (sibling, as Henrik prefers for the hub at that time) — seeds the `_codeguide/` tree in the chosen location.
2. Optionally `/codeguide-generate` to bulk-document existing source files.
3. Commit the seeded `_codeguide/` tree (inline → inside the hub; sibling → its own history in the sibling repo).

From that point on, every `/git-commit` invocation triggers the pre-commit "Codeguide sync" step, which calls `@codeguide:codeguide-update` against the staged diff. Docs stay fresh per-commit.

## Why this is not done yet

Henrik's rule: the codeguide must be created AND maintained by skills the user actively triggers through the mill workflow, not by hand. Seeding it manually now would mean every manual commit between now and mill-v2 self-sufficiency either keeps it fresh (extra work on every commit) or lets it rot (exactly the failure mode we designed around).

The right moment: when mill-go can orchestrate its first real task through plan + implement + merge. At that point the very first task can be "seed the codeguide", and every subsequent task's per-card commits via `/git-commit` → `@codeguide:codeguide-update` keep it alive.

## Out of scope

- Manual seeding now.
- Hook-based fallbacks.
- Any changes to the codeguide plugin itself — it is treated as a stable dependency.
