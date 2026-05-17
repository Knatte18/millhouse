# Discussion: 51 (D) — Config infra: env interpolation + agents.yaml inheritance

```yaml
task: 51 (D) — Config infra: env interpolation + agents.yaml inheritance
slug: config-env-interpolation
status: discussing
parent: main
```

## Problem

To uavhengige config-forbedringer bundlet i én task:

**Strand A — env interpolation.** Maskiner trenger en lett-vekts måte å overstyre enkeltverdier i shared config uten å touche committet kode. Eksempel-use-case: en cluster-maskin vil bruke `g25flash_cluster` som code-reviewer mens alle andre maskiner bruker `sonnethigh`. I dag krever det enten en `.millhouse/config.local.yaml`-override per worktree (klønete) eller en wiki-commit (deler valget med alle maskiner). Løsningen er env-interpolasjon i `_config.load_config()`: string-verdier med `${VAR}` eller `${VAR:-default}` blir erstattet med env-variabler etter at alle overlays er flettet.

**Strand B — agents.yaml inheritance.** `wiki/agents.yaml` lister 14 entries i dag (g25flash, g25flash_tool, g25pro, g25pro_tool, g3flash_preview, g3flash_preview_tool, haiku, opushigh, opusmax, opusmedium, sonnethigh, sonnetmax, sonnetmax_tool, sonnetmedium). Hvert tool-variant duplikat-spesifiserer `provider`/`model`/`effort` fra base. Break-even for inheritance er rundt 10+ entries — vi har passert det (14 i dag). `extends: <base>` lar `sonnetmax_tool` arve fra `sonnetmax` og kun override `tooluse: true`.

**Hvorfor nå:** Begge endringene er små, isolerte parser-utvidelser som kan shippes uavhengig. Bundlet i én task fordi de begge endrer config-lasting og deler rollout-form (parser først, schema-flip i andre commit).

## Scope

**In:**

- `plugins/mill/scripts/_config.py` — env-interpolasjonspass etter overlay-merge. Resursiv walk over hele dict-treet, substituerer `${VAR}` og `${VAR:-default}` i string-verdier (også inni lister og nested dicts). Unset `${VAR}` uten default → `ConfigError` med variabelnavn + dotted key-path.
- `plugins/mill/scripts/_reviewers.py` — `extends: <name>` på flat-form entries (type=single). Resolusjon kjøres i `load()` før entries returneres; output er fortsatt flate dicts uten `extends:`-felt. Cycle detection på extends-grafen. `extends:` ikke tillatt på cluster-entries (rejected with clear error).
- `plugins/mill/templates/reviewers.yaml` — refactor til `extends:`-form (commit-2 etter parser ships).
- `wiki/agents.yaml` — refactor til `extends:`-form (commit-2). Wiki-fil er shared state — endring må kombineres med deployment av matching `_reviewers.py`-versjon (per Home.md banner: backwards-compat rollout).
- `plugins/mill/templates/wiki-config.yaml` — eksempel-bruk av `${VAR:-default}` i kommentar-form på maskin-overridable nøkler (`roles.*.reviewer`). Templaten lever for nye hubs; eksisterende hubs påvirkes ikke.
- `plugins/mill/unit_tests/test-config.py` — nye tester for env-interp (default-substitusjon, env-override, unset-no-default raises, nested-walk, ingen-pattern-uendret).
- `plugins/mill/unit_tests/test-reviewers.py` — nye tester for extends (single-level, multi-level, cycle, missing-base, override-semantikk, cluster + extends rejected, required-after-merge).

**Out:**

- Rename av `wiki/config.yaml` → `mill-config.yaml`, eller `wiki/agents.yaml` → `mill-agents.yaml`. Det er task 57's scope. Denne tasken targets nåværende filnavn (`wiki/config.yaml`, `wiki/agents.yaml`). Hvis 57 squash-merges først, rebaser denne mot 57's path-rename — det er en mekanisk rename, ikke en logikkendring.
- Env-interp i `wiki/agents.yaml` eller `wiki/reviewers.yaml`. Bare `_config.load_config()`-output får interpolation. `_reviewers.load()` leser registry uberørt.
- `${VAR}` uten braces (`$VAR`). Bare `${VAR}` og `${VAR:-default}` syntax støttes.
- Escape-mekanisme for literal `${...}`. Hvis det skulle bli et reelt problem senere, legger vi til `$${...}`-escape da.
- Multi-inheritance på `extends:`. Bare én string, multi-level kjede (`A extends B extends C`) tillatt, men ikke `extends: [A, B]`.
- Cluster-entries med `extends:`. Cluster har allerede `workers.use`/`handler.use` for komposisjon; å legge til `extends:` på toppen lager overflødig kompleksitet.
- `roles.yaml`-splittet ut av config (det opprinnelige forslaget). Sparse `mill-config.yaml` + env-interp dekker use-casen.

## Decisions

### Path naming (current-world vs post-57)

- Decision: Target nåværende paths. `_config.py` leser `wiki/config.yaml`; `_reviewers.py` leser `wiki/agents.yaml` (med fallback til `reviewers.yaml`). Vi rører ikke filnavnene.
- Rationale: Task 57 er fortsatt `[active]` og ikke garantert merged først. Begge endringene fungerer like godt mot dagens filnavn. Hvis 57 lander før denne tasken merges, blir rebase en mekanisk path-rename.
- Rejected: (a) Halt-blocked-on-57 — sløser tid, parser-arbeidet er uavhengig. (b) Target post-57-paths — bygger på state som ikke eksisterer ennå.

### Env-interp scope: string values only

- Decision: Walk dict-tre rekursivt, substituer kun i str-verdier (også inni lister). Keys, ints, bools, None forblir uberørt.
- Rationale: Keys er semantiske identifikatorer, ikke konfigurerbare verdier. Ints/bools brukes for tall-lignende konfig (rounds, timeout); interpolasjon der ville krevd type-coercion og overrasket lesere.
- Rejected: Interpolere keys (åpner ukjente nøkler i runtime).

### Env-interp timing: after all overlays

- Decision: Interpolasjon kjører som siste steg i `load_config`, etter wiki + machine + worktree-stub + worktree-real merger.
- Rationale: Hvilket som helst lag kan introdusere `${VAR}`-form verdier. Hvis interpolasjon kjørte før merge, ville machine/worktree-overrides ikke kunne bruke env-syntax. Etter-merge er det enkleste invarianten.
- Rejected: Per-layer interpolasjon (semantikk-overhead, mer kode).

### Env-interp recursion: single-pass

- Decision: Etter substitusjon scannes ikke resultatet på nytt for nye `${...}`-pattern. En substituert verdi behandles som litterale tegn.
- Rationale: Single-pass eliminerer surprise-loops, gjør semantikken trivielt forutsigbar, og er konsistent med shell-defaults.
- Rejected: Rekursiv expansion (introduserer loop-risk uten reell use-case).

### Unset var without default: hard error

- Decision: Lag en ny exception-klasse i `_config.py`: `class ConfigError(ValueError): pass`. `${VAR}` der `VAR` ikke er satt, og det ikke er en `:-default`, kaster `ConfigError` med variabelnavn + dotted key-path i meldingen. `_config.py` har ingen eksisterende exception-klasser i dag, så denne lages fra grunnen.
- Rationale: Silent expansion til tom streng er bug-magnet — typos i variabelnavn ville lekke som tomme reviewer-navn, tom timeout, etc. Proposal eksplisitt: "feiler hardt hvis usatt". `ValueError`-arving gjør den naturlig fangbar med `except ValueError` i callers som ønsker generisk konfig-feilhåndtering, men den klare type-navnet gjør stack-traces lesbare.
- Rejected: Default til tom streng (silent), default til selve `${VAR}`-strengen (forvirrer downstream-validering), gjenbruke `yaml.YAMLError` (semantisk feil — det er ikke en YAML-feil, det er en post-load env-substitusjons-feil).

### `extends:` resolution timing: at load time

- Decision: `_reviewers.load()` resolverer `extends:`-kjeder før entries returneres. Output er flat dicts uten `extends:`-felt — eksisterende `resolve()`/`resolve_role()`/`validate_role_refs()` er uendret.
- Rationale: Konsentrerer kompleksiteten ett sted, holder downstream-API uberørt. Cycle detection og required-after-merge-validering hører naturlig hjemme i load.
- Rejected: Resolve lazy i `resolve()` (sprer kompleksitet, dårligere feilrapportering).

### `extends:` field: single string only

- Decision: `extends: <name>` aksepterer én streng. Multi-level kjede (`A → B → C`) er tillatt; multi-inheritance (`extends: [A, B]`) er det ikke.
- Rationale: Enkel semantikk, klar merge-rekkefølge, ingen "diamant"-arve-problem.
- Rejected: List-form (åpner valgt merge-rekkefølge, ingen reell use-case i 15-entry-registry).

### `extends:` and cluster type: incompatible

- Decision: Cluster-entries kan ikke ha `extends:`, og kan ikke være target for en annens `extends:`. Validert ved load med klar feilmelding.
- Rationale: Cluster har allerede `workers.use`/`handler.use` for komposisjon. Å legge til `extends:` lager overlappende mekanismer. Ingen reell use-case for to clusters som arver fra hverandre.
- Rejected: Tillat alt (mer kode, ingen vinning).

### Required-after-merge: `type`, `provider`, `model`

- Decision: Etter at extends-kjeden er resolved, må entry ha `type` (single), `provider`, og `model`. Missing → ReviewerError ved load.
- Rationale: Disse er minimum-input for å invokere en LLM. Andre felter (`effort`, `tooluse`) har defaults eller er valgfrie.
- Rejected: Lazy-validere ved invokasjon (feil fra load-time → confusing runtime-error).

### Rollout: parser first, schema flip in second commit

- Decision: To-commit-sekvens for hver strand.
  - Strand A commit-1: `_config.py` lærer å parse `${VAR}` og `${VAR:-default}`. Ingen template-endringer. Tests dekker pattern-handling. Backwards-compat: entries uten pattern påvirkes ikke.
  - Strand A commit-2: `plugins/mill/templates/wiki-config.yaml` får eksempel-kommentar på maskin-overridable nøkler. `wiki/config.yaml` flippes ikke i denne tasken — det er per-machine override-bruk, ikke shared default.
  - Strand B commit-1: `_reviewers.py` lærer å parse `extends:`-form (handler både flat og extends). Tests dekker resolusjon.
  - Strand B commit-2: `wiki/agents.yaml` og `plugins/mill/templates/reviewers.yaml` flippes til extends-form. Krever at commit-1 er deployed på alle maskiner først per `## Wiki/config.yaml er delt resource`-banneret i Home.md.
- Rationale: Backwards-compat-rollout-pattern er allerede etablert (Home.md banner fra task 34-incident). Wiki-flip uten matching parser deploy ville knekke andre maskiner med `KeyError: 'extends'`.
- Rejected: One-shot flip (regresjonsrisiko på parallelle worktrees som ikke har oppdatert plugin-versjonen ennå).

### `extends:` recursion: top-down merge

- Decision: Resolusjonsalgoritme: walk extends-kjede til base (entry uten `extends:`), deretter merge ned mot leaf. Hvert nivå: child-felter overrider parent-felter, uspesifiserte felter arves.
- Rationale: Standard inheritance-semantikk. Match leserens mentale modell.
- Rejected: Bottom-up walk (samme resultat, mer kompleks å implementere).

## Technical context

**`_config.py` (today).**

- `load_config(wiki_path, worktree_root) -> dict` er entry-point. Merge-rekkefølge (lowest → highest precedence): wiki → machine → worktree-stub → worktree-real.
- `deep_merge(base, overlay)` er shallow-recursive (overlay wins on scalars, dicts mergers recursively).
- Returnerer `{}` når `wiki/config.yaml` mangler (lenient).
- Env-interp legges på som siste steg i `load_config`. Ny private helper, f.eks. `_interpolate_env(cfg, key_path="") -> cfg` som walker dict + list rekursivt og kaller `_substitute_string(s)` på str-verdier.

**`_substitute_string(s) -> str` (ny).**

- Regex match `\$\{([A-Z_][A-Z0-9_]*)(:-(.*?))?\}` — varnavn-regex er liberal POSIX-ish men strikt nok til å gjenkjenne syntax-feil.
- Iterer over alle matches: hvis `:-` finnes, default-streng brukes når env-var er unset; ellers raise.
- Ingen recursion på substituert resultat.
- For ikke-string (int/bool/None): return as-is. Funksjonen kalles bare på str.
- **Intentional: lowercase names pass through as literal.** Regex aksepterer kun uppercase + underscore + digits (POSIX-konvensjon for env-vars). `${my_var}` matcher ikke regexen og forblir som literal-tegn i string-output — det er ingen "unset var"-feil og ingen substitusjon. Dette er bevisst: lowercase-form er ikke en gyldig env-var-konvensjon på Unix/Windows. Hvis en bruker skriver `${my_var}` med mening "interpoler", får de en literal `${my_var}` i resultatet, som er en synlig debug-signal heller enn silent expansion. Regexen får en kort kommentar (`# POSIX env-var convention: uppercase only; lowercase patterns are literal`). En unit-test (`test_interp_lowercase_name_passthrough`) dokumenterer grensen.

**`_reviewers.py` (today).**

- `load(wiki_root) -> dict[str, dict]` leser `wiki_root/agents.yaml` (fallback til `reviewers.yaml`), validerer struktur, returnerer name → raw spec.
- Validerings-stages: (a) navne-regex, (b) duplikat-keys via `yaml.compose`, (c) per-entry struktur (type=single|cluster + required felter), (d) cluster cross-refs (cluster.use peker på type=single), (e) cycle detection over cluster `use:`-grafen.
- `resolve(registry, name)` flater ut cluster `use:`-referanser. For single returnerer den entry med `tooluse: False`-default.
- `resolve_role(cfg, registry, role, scope)` slår opp `cfg.roles[role][scope].reviewer`, returnerer None hvis null/rounds=0.

**Modification plan for `_reviewers.load()`.**

1. Parse raw dict (eksisterende).
2. **Ny — raw-form syntax-validering av `extends:`:** felt må være string hvis tilstede; må peke på existing entry-navn; target-entry må ikke ha `type: cluster` deklarert på sin egen raw-form. Vi kan IKKE kreve `type: single` på target på dette stadiet — intermediate noder i en multi-level kjede (`c → b → a`) får sin `type:` fra base, ikke fra raw. Sjekken her er kun "target er ikke et raw-deklarert cluster"; den fulle `type: single`-invarianten verifiseres etter resolusjon i steg 5.
3. **Ny:** detect extends-cycles (separat graf fra cluster-use-graf). Kjede `a → a` (selv-loop) eller `a → b → a` → ReviewerError som lister nodene.
4. **Ny — topologisk-sortert resolusjon:** for hver entry med `extends:`, walk kjeden til base (entry uten `extends:`), deep-merge fra base mot leaf (child-felter overrider parent-felter); fjern `extends:`-felt fra output.
5. Per-entry struktur-validering (eksisterende) kjører på **resolved** entries. Her faller required-after-merge-check naturlig ut: hver resolved entry må ha `type: single` (cluster-entries er allerede ekskludert fra extends-grafen i steg 2/4) + `provider` + `model`. En entry som mister type/provider/model gjennom kjeden (f.eks. base mangler dem) feiler her med klar melding.
6. Cluster cross-refs + cluster-cycle (eksisterende) kjører på resolved.
7. Returner resolved registry.

**Validering-ordering kommentar.** Det er fristende å spørre "kan vi ikke kreve `type:` på alle raw-entries opp front?" — men det betyr at intermediate `b: {extends: a}` må skrive `type: single` redundant. Det går på tvers av punktet med inheritance (reduce duplikasjon). Raw-stadiet sjekker bare "ingen raw cluster i extends-grafen"; resolved-stadiet er der `type: single` blir håndhevet.

**Filer som leser config / registry i dag (for kontekst, ikke endringer i denne tasken):**

- `_config.load_config` brukes av flere CLI-scripts (mill-spawn, mill-go, mill-merge-in, mill-cleanup, mill-color, mill-terminal, mill-vscode).
- `_reviewers.load`/`resolve_role` brukes av review-helpers (`_review_common.py`, `_review_discussion.py`, `_review_plan.py`, `_review_code.py`).

Ingen av disse callers trenger endringer — interpolation og extends er begge transparente for dem (de leser samme dict-form som før).

**Test-fixture-utvidelser.**

- `plugins/mill/unit_tests/_test_registry.py` (existing) — `write_to(wiki)` skriver en minimal valid `agents.yaml`. Trenger ikke endringer; nye tester kan skrive egne YAML-fixtures via `_write_yaml`.
- `plugins/mill/unit_tests/_test_cfg.py` (existing) — brukes som fixture-helper. Sannsynligvis ingen endringer.

## Constraints

- **`CLAUDE.md` `## Wiki/config.yaml er delt resource` (Home.md banner):** Schema-endringer i `wiki/config.yaml` eller `wiki/agents.yaml` må enten kjøres alene eller bruke backwards-compat-rollout. Strand B commit-1 (parser) deployes via `update-plugins.ps1`; strand B commit-2 (wiki-flip) kommer etter at alle maskiner har commit-1. Denne tasken (D) er allerede merket "isolated — run alone", men commit-rekkefølgen er fortsatt et hard krav.
- **ASCII-only print/log strings (CLAUDE.md):** Alle nye error-meldinger, log-linjer bruker ASCII. Em-dash → ` -- `, right-arrow → ` -> `. Docstrings og kommentarer er exempt.
- **`${CLAUDE_PLUGIN_ROOT}` for plugin-paths (CLAUDE.md):** Ingen hardkodede `plugins/mill/...` paths i Python-helpers. Eksisterende _config.py / _reviewers.py er allerede compliant.
- **No `if __name__ == "__main__"` smoke-tests in `_*.py` helpers (CLAUDE.md):** Helpers er kun produksjonskode.
- **Unit-tests må kjøre uten reell git/LLM (CLAUDE.md):** `tempfile` + `_test_*.py`-fixtures kun. Ingen subprocess-calls til `claude`.

## Testing

**`plugins/mill/unit_tests/test-config.py` (utvidelse).**

Nye test-funksjoner:

- `test_interp_default_when_var_unset` — config har `key: "${UNSET_VAR:-mydefault}"`, env tom → resultat `"mydefault"`.
- `test_interp_env_value_when_var_set` — sett `os.environ["MY_VAR"] = "actual"`, config har `key: "${MY_VAR:-default}"` → resultat `"actual"`. Restore env i finally-block.
- `test_interp_unset_no_default_raises` — config har `key: "${REQUIRED_VAR}"`, env tom → load_config kaster ConfigError som inneholder `"REQUIRED_VAR"` og dotted key-path.
- `test_interp_no_pattern_unchanged` — config har `key: "plain string"` → resultat uendret.
- `test_interp_nested_walk` — config har `a: {b: {c: "${X:-deep}"}}` → resultat `{"a": {"b": {"c": "deep"}}}`.
- `test_interp_list_walk` — config har `xs: ["${X:-a}", "${Y:-b}"]` → resultat `["a", "b"]`.
- `test_interp_non_string_values_untouched` — config har `count: 5`, `flag: true`, `nothing: null` → uendret etter pass.
- `test_interp_applied_after_all_overlays` — wiki har `key: "${A:-wiki}"`, worktree-local har `key: "${B:-local}"`. Local skal vinne i merge, deretter interpoleres `"${B:-local}"` → `"local"` (eller env-verdi hvis satt).
- `test_interp_multiple_in_one_string` — config har `key: "${A:-x}-${B:-y}"` → resultat `"x-y"` (eller env-substituert).
- `test_interp_empty_default` — config har `key: "${UNSET:-}"` → resultat `""` (empty string allowed).
- `test_interp_lowercase_name_passthrough` — config har `key: "${my_var}"`, env `my_var=foo` satt → resultat `"${my_var}"` (literal, ikke substituert). Dokumenterer POSIX-konvensjon: bare uppercase env-var-navn matcher regexen.

**`plugins/mill/unit_tests/test-reviewers.py` (utvidelse).**

Nye test-funksjoner:

- `test_extends_single_level` — `child: {extends: base, tooluse: true}` + `base: {type: single, provider: claude, model: foo}` → load returnerer `child` som `{type: single, provider: claude, model: foo, tooluse: true}`.
- `test_extends_multi_level` — `c → b → a` kjede, c arver alt fra a + b's overrides + sine egne.
- `test_extends_child_overrides_parent_scalar` — child specifiserer `model: bar` selv om base har `model: foo` → child får `model: bar`.
- `test_extends_unknown_base_raises` — `child: {extends: nonexistent}` → ReviewerError nevner `nonexistent`.
- `test_extends_cycle_raises` — `a: {extends: b, ...}` + `b: {extends: a, ...}` → ReviewerError nevner cycle.
- `test_extends_self_cycle_raises` — `a: {extends: a, ...}` → ReviewerError.
- `test_extends_target_must_be_single` — `child: {extends: my_cluster}` der my_cluster er type=cluster → ReviewerError nevner type-mismatch.
- `test_cluster_cannot_extend` — entry med både `type: cluster` og `extends: ...` → ReviewerError.
- `test_required_field_missing_after_merge_raises` — `child: {extends: base, model: foo}` + `base: {extends: base2}` + `base2: {type: single, provider: claude}` (mangler model) — vent, dette har model fra child. Annet eksempel: `a: {type: single, model: foo}` (mangler provider) → ReviewerError.
- `test_extends_field_removed_from_output` — verifiser at returned dict ikke inneholder `extends:`-key.

**TDD-kandidater.** Begge strands er pure parser-arbeid med klar input/output, ideelt for TDD.

- Strand A: skriv `test_interp_no_pattern_unchanged` + `test_interp_default_when_var_unset` + `test_interp_unset_no_default_raises` først, så implementer `_substitute_string` + integrasjon i `load_config`. Add resterende tester for nested/list/multi-pattern.
- Strand B: skriv `test_extends_single_level` + `test_extends_unknown_base_raises` + `test_extends_cycle_raises` først, så implementer extends-resolusjon i `load()`. Add resterende tester for multi-level/cluster-rejection/required-fields.

**Integrasjonstester.** Ikke nødvendig for denne tasken — alle stier eksisterer mellom eksisterende callere og _config/_reviewers. Funksjonell verifisering skjer via eksisterende `test-config.py` og `test-reviewers.py` + nye test-cases.

## Q&A log

- **Q:** Task 57 (config-move-to-hub) er fortsatt `[active]` mens denne tasken's proposal sier "Forutsetter task 57 squash-merged". Hvordan håndtere? **A:** [auto-pick] Proceed targeting current paths (`wiki/config.yaml`, `wiki/agents.yaml`); rebase mekanisk hvis 57 lander først. **Why:** Parser-arbeidet er uavhengig av filnavn; halt-blocked sløser tid; rename er en kjapp rebase.
- **Q:** Skal env-interp gjelde dict keys eller bare values? **A:** [auto-pick] Bare string-values (inkl. inside lister og nested dicts). **Why:** Keys er semantiske identifikatorer; interpolere dem åpner ukjente nøkler i runtime.
- **Q:** Når i `load_config` kjøres interpolation? **A:** [auto-pick] Som siste steg, etter alle overlays er flettet (wiki + machine + worktree-stub + worktree-real). **Why:** Hvilket som helst lag kan introdusere `${VAR}`-strenger; etter-merge er enkleste invariant.
- **Q:** Recursion i substitusjon — skal substituert resultat skannes på nytt? **A:** [auto-pick] Single-pass. **Why:** Surprise-loops elimineres; matcher shell-standard `${VAR:-default}`-semantikk.
- **Q:** Hva skjer ved `${VAR}` uten default og uten env-verdi? **A:** [auto-pick] Hard error med variabelnavn + dotted key-path i exception. **Why:** Proposal eksplisitt; silent expansion til tom streng er bug-magnet.
- **Q:** Hva skjer ved `${UNSET:-}` (empty default)? **A:** [auto-pick] Tillatt, gir tom streng. **Why:** Eksplisitt opt-in til tom streng er gyldig; matcher shell.
- **Q:** Støtt `$VAR` uten braces? **A:** [auto-pick] Nei, bare `${VAR}` og `${VAR:-default}`. **Why:** Færre kant-tilfeller; brace-form er entydig terminert.
- **Q:** Escape-mekanisme for literal `${...}`? **A:** [auto-pick] Ikke i denne tasken. **Why:** Ingen aktuell use-case; `$${...}`-escape kan legges til hvis behov dukker opp.
- **Q:** Hvor resolveres `extends:`-kjeden? **A:** [auto-pick] I `_reviewers.load()` før entries returneres; output har ingen `extends:`-felt. **Why:** Konsentrerer kompleksitet ett sted; downstream-API (`resolve`, `resolve_role`) uberørt.
- **Q:** Multi-inheritance på `extends:`? **A:** [auto-pick] Nei — bare én string. Multi-level kjede er OK. **Why:** Diamant-arve-problemet forsvinner; ingen use-case i 15-entry-registry.
- **Q:** Kan cluster-entries bruke `extends:` eller være target for `extends:`? **A:** [auto-pick] Nei. **Why:** Cluster har allerede `workers.use`/`handler.use` for komposisjon; å legge til `extends:` lager overlappende mekanismer.
- **Q:** Cycle detection for `extends:` — runtime-feil eller load-time? **A:** [auto-pick] Load-time, hard error, inkluderer kjede-nodene i meldingen. **Why:** Cycle = config-bug, ikke runtime-condition; fail-fast.
- **Q:** Hvilke felter er required etter merge? **A:** [auto-pick] `type`, `provider`, `model`. **Why:** Minimum-input for å invokere en LLM; andre felter har defaults eller er valgfrie.
- **Q:** Rollout-pattern for Strand B? **A:** [auto-pick] Commit-1: parser ships (handler både flat og extends). Commit-2: flip `wiki/agents.yaml` og `plugins/mill/templates/reviewers.yaml` til extends-form. **Why:** Matcher Home.md-banner-pattern; unngår å knekke parallelle worktrees som ikke har deployed commit-1.
- **Q:** Skal Strand A flippe `wiki/config.yaml` til `${VAR:-default}`-form i samme task? **A:** [auto-pick] Nei. Bare templaten (`plugins/mill/templates/wiki-config.yaml`) får kommentar-eksempel; produksjons-`wiki/config.yaml` rører vi ikke. **Why:** Per-machine override er use-casen; konfig-eieren flipper selv når en maskin trenger det.
- **Q:** Skal Strand A og Strand B være én PR eller to? **A:** [auto-pick] Én PR, men plan-batchene holder dem adskilt (uavhengig kode, uavhengige tester). **Why:** Proposal bundler dem; review-overhead er lavt; rollback av én strand er triviell.
- **Q:** Env-interp i `wiki/agents.yaml` eller `wiki/reviewers.yaml`? **A:** [auto-pick] Nei — bare i `_config.load_config()`-output. **Why:** Proposal scope; ingen aktuell use-case for env-driven reviewer-entries (de er en lukket katalog).
- **Q:** Reviewer-finding r1 [GAP]: Multi-level `extends:`-kjede (`c → b → a`) har intermediate `b` uten raw `type:`. Step 2's "target must be type=single" er uresolverbart fra raw. Hvordan splitte validering? **A:** [auto-pick] Steg 2 sjekker kun "target er ikke et raw-deklarert cluster"; full `type: single`-invariant verifiseres etter resolusjon i steg 5 (per-entry struktur-validering). Intermediate-noder trenger ikke å re-deklarere `type:`. **Why:** Inheritance handler om å redusere duplikasjon — å kreve `type: single` på hver intermediate raw-entry går imot poenget. Resolved-stadiet er det naturlige stedet for full type-håndhevelse.
- **Q:** Reviewer-finding r1 [NOTE]: `ConfigError` eksisterer ikke i `_config.py`. **A:** [auto-pick] Lag en ny `class ConfigError(ValueError): pass` i `_config.py` som del av Strand A commit-1. **Why:** `ValueError`-base gir caller-fleksibilitet for generisk håndtering; eget type-navn gir lesbar stack-trace.
- **Q:** Reviewer-finding r1 [NOTE]: Regex `[A-Z_][A-Z0-9_]*` matcher kun uppercase — `${my_var}` passerer gjennom som literal-tekst uten feil. Asymmetri med uppercase unset → hard error. **A:** [auto-pick] Behold uppercase-only-regex (POSIX-konvensjon). Dokumenter eksplisitt at lowercase-form er literal-passthrough. Legg til `test_interp_lowercase_name_passthrough` og en regex-kommentar. **Why:** Lowercase env-var-navn er ikke konvensjon på Unix/Windows. Literal-passthrough gjør debug-feil synlig i output heller enn silent expansion til feilverdier.
