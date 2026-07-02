All three cards are implemented and committed:

- Card 14: `plugins/mill/scripts/millpy-fix.py` — computes `nits_only_carveout` from `args.nits_only` and wires `NITS_ONLY_CARVEOUT` into both the batch-scope and holistic-scope token dicts (commit `0ddeb855`)
- Card 15: `plugins/mill/templates/fixer-holistic-brief.md` — both zero-commit sentences now consume `<NITS_ONLY_CARVEOUT>`, token documented in the header comment (commit `31fd76f5`)
- Card 16: `plugins/mill/templates/fixer-batch-brief.md` — mirrors Card 15 for the batch-scope template (commit `b7239914`)

`verify: null` for this batch — no runnable surface, skipped per plan. Working tree is clean (`git status --porcelain --untracked-files=no` empty) and all commits are pushed to `hanf/agent-mode-gaps`.

{"status":"success","commit_sha":"b723991430b512d54c18405ddc4decfa2448747f","session_id":"c7d48356-e26d-4534-bd18-049923bf9152"}