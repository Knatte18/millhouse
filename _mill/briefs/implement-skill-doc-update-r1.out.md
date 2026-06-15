The documentation has been successfully added to mill-plan/SKILL.md Phase: Plan Review step 2 (agent-mode dispatch description), around the "Pre-review validator gate" note.

- Added agent-mode prepare-envelope-handling: when `errors` key present, route into Step 1.5 mechanical-fix loop; when stage/brief_path present, proceed with Agent -> finalize flow.
- Discriminator is the PRESENCE OF THE `errors` key, not the exit code alone.
- Clarified the pre-review validator gate note: validator runs in BOTH modes; prepare stage runs validator before returning a brief.
- Did NOT modify SKILL.md:104.
- Batch has verify: null, no tests to run.

{"status":"success","commit_sha":"d415c6339f5744f4049ef72144745e3bff8d2a23","session_id":"580c8792-8a29-48d8-9e47-83f014978900"}
