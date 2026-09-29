All 3 of 3 cards are committed and pushed. `verify:` passes (`test-load-directive-convention.py` and `bash -n update-plugins.sh`), and the tracked tree is clean.

Card 12 (`update-plugins.sh`): both stubbed-`claude` fixture runs behaved as specified. The run under the real `HOME` never happened.
- **Fixture 1 (only `python@millhouse` installed):** printed the scribe not-installed line, "Skipped (not installed)" for mill, codeguide and weblens, and `Orphaned: python@millhouse is no longer in this marketplace -- run 'claude plugin uninstall python@millhouse'.`
- **Fixture 2 (`scribe@scribe` 1.0.0):** printed both refresh `WARNING: ... failed -- continuing` lines from the stub, then `WARNING: scribe@scribe is 1.0.0, mill needs 1.1.0 -- run 'claude plugin marketplace update scribe' and 'claude plugin update scribe@scribe'.`
- **CLI syntax:** re-checking `--help` for `claude plugin marketplace update`, `update` and `uninstall` showed no change.

Card 13 (`update-plugins.ps1`): `pwsh` is not on PATH, so the PowerShell parse check and any run were not done. I compared it with the `.sh` by reading only: step order, message text and skip rules match.

Card 14 (`CLAUDE.md`): added the scribe refresh and orphan sentence, and qualified `scribe:csharp-build` and `scribe:python-build`.

{"status":"success","commit_sha":"5809b135d4bab94f551f8b2956e98cce2799484d","session_id":"cd3cab67-b18d-4a0c-85c8-e6646cf66358","cards_done":[12,13,14]}
