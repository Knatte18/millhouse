# Batch: cleanup-deletions

```yaml
task: 57 (A) -- Move config.yaml and agents.yaml from wiki to hub worktree
batch: cleanup-deletions
number: 4
cards: 1
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [2, 3]
```

## Batch Scope

This batch deletes the dead surface left over after batch 2 (loaders no longer call `_machine.load_layer`) and batch 3 (mill-setup SKILL.md no longer references `_machine.probe` or `config.machine.yaml`). Removes the `_machine` module, its unit-test file, the machine-config template, the old `wiki-config.yaml` template (superseded by `mill-config.yaml` from batch 1), and the old `reviewers.yaml` example template (superseded by `mill-agents.yaml` from batch 1).

The deletions are gated behind both refactor batches because each removed file was load-bearing in pre-refactor code paths. Running batch 4 before batches 2 and 3 would break test runs and mill-setup invocations.

External interface: none. After this batch, the only surface left in the plugin's `templates/` directory for shared/agent config is `mill-config.yaml`, `mill-agents.yaml`, and `config.local.yaml`.

Batch-local decisions:

- Deletions use `git rm` (or `Bash` `rm` followed by `git add -A` -- whatever the implementer's shell convention is); the implementer must ensure the deletions are tracked in the commit, not just removed from the working tree.
- Before each deletion, the implementer re-greps the candidate filename / module name across the WHOLE repo (`plugins/`, `specs/`, `wiki/`, top-level config files) to confirm no callers remain. Any hit outside the planned deletion targets is a halt -- it signals a planning gap and the implementer must surface the unexpected caller back to the orchestrator.

## Cards

### Card 22: Delete `_machine.py`, `test-machine.py`, and superseded templates; finalise CLAUDE.md

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_machine.py`
  - `plugins/mill/unit_tests/test-machine.py`
  - `plugins/mill/templates/config.machine.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
  - `plugins/mill/templates/reviewers.yaml`
- **Requirements:** Before any deletion: run each of these greps from the repo root and confirm the expected results.

  - `grep -rn "_machine" plugins/` -- expected hits ONLY in the files being deleted (`_machine.py` itself, `test-machine.py`). Any other hit (e.g. a leftover import in a script, a leftover reference in a SKILL.md, a docstring mention) means batches 2 or 3 missed a callsite -- halt and surface the file/line to the orchestrator. Do NOT delete `_machine.py` until this grep is clean for non-deletion files.
  - `grep -rn "config.machine.yaml" plugins/` -- expected hits ONLY in the template file being deleted and possibly in docstrings of `_machine.py` (also being deleted). Any other hit is a halt.
  - `grep -rn "wiki-config.yaml" plugins/` -- after batch 1 and 3, expected hits ONLY in the file being deleted and possibly in `mill-config.yaml` template's header comment (if the header references the old name for migration purposes, that's intentional documentation and must be kept). Verify each hit before deleting.
  - `grep -rn "reviewers.yaml" plugins/` -- after batch 1 and 2, expected hits ONLY in the file being deleted plus the legacy-fallback line inside `_reviewers.py` (which references `wiki_root / "reviewers.yaml"` for the wiki-legacy fallback -- that's intentional and must be kept). Any other hit (especially in templates or skills) is a halt.

  **CLAUDE.md update (must happen in the same commit as the deletions).** Open `CLAUDE.md` at the hub root and locate the bullet at approximately line 109 starting with "**Template `wiki-config.yaml` mirrors production `wiki/config.yaml`.**". Replace the entire bullet with: "**Template `mill-config.yaml` is the canonical config schema.** When changing a config key in `mill-config.yaml` at the hub repo root, mirror the change in `plugins/mill/templates/mill-config.yaml` -- the template ships with the plugin and seeds new hubs via mill-setup. Drift means new hubs are seeded with a stale schema. The hub-root file is the source of truth for valid schema; the template is the source of truth for the documentation comments inside the file (overlay precedence, env-var registry)." Locate the parenthetical "(The same invariant is documented in `wiki/config.yaml`'s header comment.)" inside the "**Junctions are IDE/terminal convenience only.**" bullet at approximately line 116 and replace `wiki/config.yaml` with `mill-config.yaml`. After the edit, grep `wiki/config.yaml` and `wiki-config.yaml` in `CLAUDE.md` -- only references that are clearly historical (e.g. inside a "before/after migration" explanatory passage) should remain; treat unexpected hits as a planning miss and update them in this card.

  Once each grep is clean (only the listed deletion targets or intentional legacy references), perform the deletions via `git rm` for each file individually:

  ```bash
  git -C <repo> rm plugins/mill/scripts/_machine.py
  git -C <repo> rm plugins/mill/unit_tests/test-machine.py
  git -C <repo> rm plugins/mill/templates/config.machine.yaml
  git -C <repo> rm plugins/mill/templates/wiki-config.yaml
  git -C <repo> rm plugins/mill/templates/reviewers.yaml
  ```

  After deletion, re-run the same greps to confirm zero unexpected hits. Run the full unit-test suite (`python plugins/mill/unit_tests/run-all.py`) to confirm nothing imports a deleted module. Run a final grep for `import _machine` and `from _machine` across the whole repo to ensure no import errors at runtime.

  This card has no edits to existing files -- the deletions ARE the change. If the grep audit surfaces any unexpected hit, the implementer fixes the unexpected caller as part of this card (treating it as a planning miss from batches 2 or 3) before completing the deletion. The fix follows the same pattern used in the originating batch (e.g. swap the `_machine` import for the new overlay logic, or update the SKILL.md narrative to point at the new template name).
- **Commit:** `chore: remove _machine and superseded templates`

## Batch Tests

The `verify:` runs the full unit-test suite via `run-all.py`. After this batch, no test file references `_machine` (the only test that did was `test-machine.py`, which is deleted in this batch). All other tests run unchanged. The aggregated run-all.py serves as the final regression check that batches 1-4 land in a coherent state.
