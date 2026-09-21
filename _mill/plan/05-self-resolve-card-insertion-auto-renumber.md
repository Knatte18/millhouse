# Batch: self-resolve-card-insertion-auto-renumber

```yaml
task: mill-go/mill-merge-in orchestration robustness gaps, round 2
batch: self-resolve-card-insertion-auto-renumber
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [2, 3]
```

## Batch Scope

Teaches mill-go's self-resolve card-insertion path to auto-renumber a downstream batch's cards on a
simple contiguous-range collision, instead of escalating straight to `blocked` (`_mill/discussion.md`
Decision `self-resolve-card-insertion-auto-renumber`, #1057). Depends on batch 2 (both edit
`mill-go-base/SKILL.md`) and batch 3 (both edit `_plan_validate.py`) — no design dependency, purely
to avoid a `parallel-modifies-overlap` finding on either shared file.

## Cards

### Card 11: auto-renumber helper for a card-numbering collision

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new function `renumber_after_collision(plan_dir: Path, colliding_number: int) -> None` to
  `_plan_validate.py`, placed immediately after `compute_next_card_number`. Card numbers are global
  and each batch occupies a contiguous, disjoint numeric range (this file's own established
  convention), so shifting every card numbered `>= colliding_number`, across every batch file in the
  plan, up by exactly one preserves every batch's own internal ordering and every batch's contiguous
  range relative to its neighbors — this is simpler than re-deriving `topo_order` and needs only each
  batch's own file-local card numbers:
  ```python
  def renumber_after_collision(plan_dir: Path, colliding_number: int) -> None:
      batch_files = sorted(
          p for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"
      )
      to_shift: list[tuple[Path, int]] = []
      for batch_path in batch_files:
          text = batch_path.read_text(encoding="utf-8")
          for num, _lines in _parse_cards(text):
              if num >= colliding_number:
                  to_shift.append((batch_path, num))
      # Descending order: shift the highest numbers first so no intermediate write
      # collides with a not-yet-shifted number in the same file.
      for batch_path, num in sorted(to_shift, key=lambda pair: pair[1], reverse=True):
          text = batch_path.read_text(encoding="utf-8")
          heading_re = re.compile(rf"^(###\s+Card\s+){num}(\s*:)", re.MULTILINE)
          text = heading_re.sub(rf"\g<1>{num + 1}\g<2>", text, count=1)
          batch_path.write_text(text, encoding="utf-8")
  ```
  This function performs no numbering-collision re-validation of its own and never touches any
  batch's `cards:` frontmatter count (shifting labels never changes how many cards a batch owns) —
  the caller (Card 12, in `mill-go-base/SKILL.md`) is responsible for retrying
  `compute_next_card_number` afterward and for the post-write `_check_card_numbering` re-check the
  self-resolve step already runs. Add this function's name to `_plan_validate.py`'s module-level
  docstring listing, adjacent to `compute_next_card_number`, and document in its own docstring that
  it is safe only when the caller has already confirmed every renumbered batch has not yet been
  dispatched (no commit anywhere references its old card numbers) — mill-go's own strictly-sequential
  `topo_order` execution guarantees this for the self-resolve caller, but this function itself does
  not verify it.
- **Commit:** `feat(plan-validate): add renumber_after_collision for a card-numbering collision (#1057)`

### Card 12: wire auto-renumber into mill-go-base's self-resolve step

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `mill-go-base/SKILL.md`'s `### Stuck escalation` section, the `verify` / `logic` (first
  occurrence) bullet currently reads (in the paragraph beginning "On `PlanDAGError` (a genuine
  numbering-range collision ...)"): "make no write to the target batch file at all and instead route
  directly to this same bullet's existing escalation path below ... a card-numbering collision means
  self-resolve itself cannot safely proceed, so it escalates immediately rather than attempting the
  retry-then-escalate cycle the rest of this bullet uses for implementer-reported failures." Replace
  this paragraph with: "On `PlanDAGError` from `compute_next_card_number` whose message matches the
  simple contiguous-range-collision shape (`f\"card {{N}} already used by batch {{stem}}; ...\"` —
  extract `{N}` via `re.match(r\"^card (\\d+) already used\", str(exc))`): call
  `_plan_validate.renumber_after_collision(plan_dir, N)` (`signature:
  _plan_validate.renumber_after_collision(plan_dir: Path, colliding_number: int) -> None`), then
  retry `compute_next_card_number(plan_dir, target_batch_file)` once. If the retry succeeds, proceed
  with the existing card-insertion flow below (append the `### Card N:` heading using the RETRIED
  call's returned number, run `_check_card_numbering` as the existing post-write defensive re-check
  already does) unchanged. If the retry still raises `PlanDAGError`, or the original exception's
  message did not match the simple contiguous-range-collision shape, make no write to the target
  batch file at all and route directly to this same bullet's existing escalation path below (`state
  -> blocked`, `blocked_reason` naming the collision text, commit, go to *Blocked*) exactly as
  today — a collision this auto-renumber cannot resolve still means self-resolve cannot safely
  proceed." Renumbering is safe here specifically because mill-go executes batches strictly
  sequentially per `topo_order`, so the colliding (downstream) batch has, by construction, not yet
  been dispatched and has no commits referencing its old card numbers.
- **Commit:** `docs(mill-go-base): wire auto-renumber into the self-resolve card-insertion path (#1057)`

## Batch Tests

Extends `test-plan-validate.py` with: a fixture of two adjacent batches sharing a contiguous card
range (batch A cards 7-14, batch B cards 15-20) — forcing `compute_next_card_number(plan_dir,
"batch-A-stem")` to collide at 15 — then calling `renumber_after_collision(plan_dir, 15)` and
asserting every card `>= 15` (batch B's cards 15-20) shifted to 16-21 while batch A's own 7-14 stayed
untouched, and that `compute_next_card_number` now returns 15 cleanly on retry. A second case with a
three-batch chain confirms the shift cascades through every later batch, not just the immediate
neighbor. Runs via `test-plan-validate.py` directly — this batch touches only that one test file (in
addition to the doc-only `mill-go-base/SKILL.md` edit, which has no runnable surface of its own).
