# Batch: codeguide-generate-skill

```yaml
task: '3 (A) — codeguide improvements: sibling placement + --branch flag'
batch: codeguide-generate-skill
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Updates `plugins/codeguide/skills/codeguide-generate/SKILL.md` so agents writing docs in sibling mode know where to place each project's `_codeguide/` directory. Two coupled changes: Step 1 must expose the values Step 9 needs (`mode`, `sibling_anchor`, `git_toplevel`); Step 9 then uses those to compute the correct path. The current SKILL.md never mentions sibling mode, which is why agents collapse all docs into a flat `<sibling-anchor>/_codeguide/modules/` instead of the per-project mirrored layout that `resolve.py`'s sibling walk expects.

External interface this batch produces: an updated SKILL.md whose Step 1 emits a JSON-parsed dict and whose Step 9 conditionally branches on `mode`. No code consumes this — the next batch (codeguide-setup-skill) is independent.

Batch-local decisions: none beyond the Shared Decisions in the overview.

## Cards

### Card 1: Update Step 1 to use `resolve.py --json` and fetch git_toplevel

- **Reads:**
  - `plugins/codeguide/skills/codeguide-generate/SKILL.md`
  - `plugins/codeguide/skills/codeguide-setup/SKILL.md`
  - `plugins/codeguide/scripts/resolve.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/codeguide/skills/codeguide-generate/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the current Step 1 text — which reads "Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py` to locate the nearest `_codeguide/` containing config.yaml. If it exits with an error, stop — run `/codeguide-setup` first." — with prose that instructs the agent to (a) run `python ${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py --json`, (b) parse the JSON object `{mode, cg_root, sibling_anchor, found}`, (c) additionally run `git rev-parse --show-toplevel` and bind the result as `git_toplevel`, and (d) preserve the existing exit-on-error behavior (if `found == false` or the resolve call errors, stop and tell the user to run `/codeguide-setup` first). The pattern must match codeguide-setup Step 3, which already does the JSON parse. Step numbering and surrounding text stay unchanged. Do not modify any other step in this card.
- **Commit:** `docs(codeguide-generate): parse resolve.py --json and fetch git_toplevel in Step 1`

### Card 2: Add sibling placement rule + multi-project worked example to Step 9

- **Reads:**
  - `plugins/codeguide/skills/codeguide-generate/SKILL.md`
  - `plugins/codeguide/scripts/resolve.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/codeguide/skills/codeguide-generate/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Step 9 currently begins "Create docs for new project (if no Overview exists):" and lists three sub-bullets (create `_codeguide/`, write Overview.md, update repo-level Overview). Add a placement rule at the top of Step 9 that branches on the `mode` value bound in Step 1: when `mode == "inline"`, place `_codeguide/` at `<project_path>/_codeguide/` (current behavior, must be preserved verbatim for inline users); when `mode == "sibling"`, place `_codeguide/` at `<sibling_anchor>/<project_path.relative_to(git_toplevel)>/_codeguide/`. Explicitly call out the wrong layout to avoid: do NOT place all docs under a single flat `<sibling_anchor>/_codeguide/modules/`. Append a worked example after the rule using the multi-project monorepo from `discussion.md` Technical context (lines showing `c:/Code/acme/wts/acme/` with two projects `src/csharp/Api/` and `src/csharp/Worker/`, sibling anchor at `c:/Code/acme/codeguide/`, docs landing at `c:/Code/acme/codeguide/src/csharp/Api/_codeguide/` and `c:/Code/acme/codeguide/src/csharp/Worker/_codeguide/`, NOT at `c:/Code/acme/codeguide/_codeguide/modules/`). Format the example as a fenced code block. Reference `resolve.py`'s `_sibling_walk` once in passing so the rule's correctness is traceable. The remaining Step 9 sub-bullets (create directory, write Overview.md, update repo-level Overview) follow the placement rule and must continue to apply to whichever path the rule chose.
- **Commit:** `docs(codeguide-generate): add sibling placement rule + multi-project example in Step 9`

## Batch Tests

`verify: null` — pure SKILL.md prose, no executable surface. Manual integration verification per `discussion.md` Testing section: run `/codeguide-generate` on a multi-project repo in sibling mode and confirm docs land at `<anchor>/<rel>/_codeguide/`; verify inline-mode regression (docs still land at `<project>/_codeguide/`).
