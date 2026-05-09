# Plan: 41 (A) — mill-start --auto flag

```yaml
task: 41 (A) — mill-start --auto flag
slug: mill-start-auto
approved: true
started: 20260509-145419
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
    name: mill-start-auto-skill
    file: 01-mill-start-auto-skill.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: prose-only-skill-edit

- **Decision:** the entire change is a prose edit to a single SKILL.md file. No new Python helper, no new CLI driver, no template change, no config-key change, no new tests.
- **Rationale:** mirrors the `/mill-self-report --auto` precedent. `mill-start` has no Python driver — all behaviour is prose Claude reads. Adding code-level surface for one boolean flag would be over-engineering and add maintenance burden without benefit.
- **Applies to:** all batches

### Decision: argument-detection-pattern

- **Decision:** the `--auto` argument is detected by SKILL prose mirroring `mill-self-report/SKILL.md` line 63 — "If the skill argument is `--auto`: …". The slash-command argument string is read by Claude (the assistant) directly when the slash command fires; no parsing helper is involved.
- **Rationale:** consistent with the only other `--auto`-bearing skill in mill. Keeps the change contained to one file and avoids invent-a-helper for a single-bit flag.
- **Applies to:** mill-start-auto-skill

### Decision: orthogonal-to-autonomous-mode

- **Decision:** the new `--auto` flag is independent from `pipeline.autonomous_mode`. The new SKILL prose neither reads nor writes that config key. The Auto mode subsection MUST contain a one-line orthogonality note stating that `--auto` controls Phase: Discuss/Discussion Review behaviour while `pipeline.autonomous_mode` controls mill-go's stuck-handling.
- **Rationale:** the two flags affect different skills and different decision points. Coupling them would force operators who want one to accept the other.
- **Applies to:** mill-start-auto-skill

### Decision: blocked-halt-pattern

- **Decision:** under `--auto`, when discussion review gaps remain after `max_review_rounds`, the SKILL halts via the `blocked` phase. The Auto mode subsection MUST name the exact helper sequence: `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, then `_status.update_field(status_path, "blocked_reason", "auto: discussion review gaps unresolved after <N> rounds")`, then commit + push status.md, then halt without proceeding to Handoff.
- **Rationale:** mirrors mill-go's `pipeline.autonomous_mode` halt-to-blocked pattern (`mill-go/SKILL.md` lines 144 and 197). Operators expect blocked tasks to surface via the existing `[active]`/blocked Home.md flow; introducing a new halt mechanism would diverge.
- **Applies to:** mill-start-auto-skill

### Decision: qa-log-format-extension

- **Decision:** the `## Q&A log` section in discussion.md gains an extended entry format under `--auto`: `- **Q:** <question> **A:** [auto-pick] <option-1-label>. **Why:** <rationale>.`. Operator-driven entries keep the existing bare format (`- **Q:** … **A:** …`). The `discussion.md` template (`plugins/mill/templates/discussion.md`) is NOT modified — the format extension is documented in the Auto mode subsection of mill-start SKILL.md only.
- **Rationale:** keeps a single audit section per discussion file. Operator skim-audits via grep `[auto-pick]`. Template stays minimal because mixed-mode (operator interrupts auto mid-flow) writes whichever format matches the actual answer source.
- **Applies to:** mill-start-auto-skill

### Decision: pure-docs-no-verify

- **Decision:** the batch's `verify:` is null. The change is pure prose; the only verification is the holistic plan reviewer reading the resulting SKILL.md (and downstream code review during mill-go).
- **Rationale:** there is no runnable surface to gate on. Adding a synthetic verify command (e.g. grep for "argument-hint:") would be tautological and brittle.
- **Applies to:** mill-start-auto-skill

## All Files Touched

- `plugins/mill/skills/mill-start/SKILL.md`
