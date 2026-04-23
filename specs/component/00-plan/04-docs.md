# Batch: docs

```yaml
task: codeguide sibling-mode + unified sibling-path convention
batch: docs
cards: 1
verify: null
depends-on: [mill-integration, codeguide-plugin]
```

## Batch Scope

One small documentation edit that lands after both behaviour-changing batches are in: the placeholder spec `13-mill-codeguide.md` needs to learn that codeguide can live either inline or sibling. It currently assumes inline only (written when sibling didn't exist yet). A single sentence edit keeps that spec accurate so future implementers don't re-derive the design.

No code changes here; no verify command.

## Cards

### Card 13: update `13-mill-codeguide.md` to mention sibling mode

- **Reads:** `specs/component/13-mill-codeguide.md`, `specs/component/00-codeguide-sibling-mode.md` (post-implementation), `plugins/codeguide/skills/codeguide-setup/SKILL.md` (post-Card-5).
- **Modifies:** `specs/component/13-mill-codeguide.md`
- **Creates:** (none)
- **Requirements:**
  - In the `## Mechanism (already partially designed)` section, update the bullet describing where codeguide lives. Currently it implicitly assumes inline. Change to: "codeguide can live either inline (`<repo>/_codeguide/`) or in a sibling repo (`<parent>/codeguide/` for hub-form, `<parent>/<repo>.codeguide/` otherwise). `resolve.py` handles both transparently — the consuming skill doesn't care."
  - In the `## Scope when implemented` section, update step 1 to note the same choice: "Write the seed `_codeguide/Overview.md` (inline or sibling, as Henrik prefers for the hub at that time)."
  - Do not change the deferral rationale — the spec is still gated on mill-v2 self-sufficiency.
  - One-line commit message tying this to spec 00.
- **Commit:** `spec: 13-mill-codeguide mentions sibling mode (closes spec 00)`

## Batch Tests

None. Pure documentation. Manual spot-check via `git diff` at commit time is sufficient.
