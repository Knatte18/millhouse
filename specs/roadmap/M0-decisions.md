# M0 — Decision gates (before writing any code)

```yaml
depends-on: none
delivers: signed-off spec
status: complete
```

Before writing code, confirm these decisions:

- [x] Plan format: **bundles**. `layer-03-orchestration.md` and `ref-formats.md` must be updated to reflect bundles before implementing Layer 03.
- [x] Gemini-in-v2.0: **yes** (per current spec). Layer 02 includes the Gemini provider at M2.4.
- [x] Repo name (settled: `millhouse`). Container path (`C:\Code\millhouse\`).
- [x] Primary-clone folder name (settled: `hub`).
- [x] `.millhouse/` layout details (dot-prefix `.active` and `.<slug>.slug.md` — settled).

## Exit criteria

- [x] Every checkbox above is ticked.

⛔ **Gate:** don't start M1 until every box is ticked. If any can't be, update the relevant spec until it can.
