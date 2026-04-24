---
kind: plan-batch
batch-name: register
batch-depends: [skill]
approved: false
---

# Batch 02: register

## Batch-Specific Context

Register the new skill in the hub index and add the `groom:` config block
to the shared wiki config so the defaults are documented and overridable.

## Batch Files

- SKILLS.md
- wiki/config.yaml   (wiki repo at sibling path)

## Cards

### Card 01: Add mill-groom to SKILLS.md

- **Creates:** nothing
- **Modifies:** SKILLS.md
- **Reads:** SKILLS.md (for format — table row matching mill-ghissues-to-tasks entry)
- **Requirements:**
  - Add one table row for `mill-groom` in the same format as the `mill-ghissues-to-tasks` row.
  - Description: "Interactive Home.md backlog cleanup. Shorten, fold, drop, or extract entries. Approval-gated — one commit per session."
  - Link: `plugins/mill/skills/mill-groom/SKILL.md`
- **Commit:** `feat(mill-groom): register in SKILLS.md`

### Card 02: Add groom: block to wiki/config.yaml

- **Creates:** nothing
- **Modifies:** wiki/config.yaml (at `c:/Code/millhouse/wiki/config.yaml`)
- **Reads:** wiki/config.yaml (for placement — append after `notify:` block)
- **Requirements:**
  - Add a `groom:` section with `brevity-threshold-lines: 5` and `brevity-threshold-chars: 500`.
  - Include a short comment explaining the keys.
  - Commit+push the wiki repo directly (`git -C <wiki_path> add config.yaml && git -C <wiki_path> commit -m "config: add groom brevity thresholds" && git -C <wiki_path> push`).
- **Commit:** `config: add groom brevity thresholds` (in wiki repo)
