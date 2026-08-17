# Specification — Configuration (`CFG`)

A consuming repository describes itself in `.claude/repo-config.yml`. Nothing else varies between
repositories: the skills, workflows and specs are identical everywhere, and this file is how one
repository differs from another.

`CFG` belongs to the **substrate** capability and depends only on `API`.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — configuration describes a repository; it does not switch behaviour on and off.**
> A key exists because repositories genuinely differ — how many owners, what a milestone means,
> what the test command is. A proposed key that would fork behaviour rather than describe a fact
> is a sign that a separate capability is wanted.

> **Invariant — every key the code reads exists in the schema.** A key that is read but
> undocumented is a private setting nobody can discover, and it drifts.

> **Invariant — a capability may depend only on capabilities below it.** Enabling one without its
> dependencies is a configuration error, refused at load, not a runtime surprise.

---

## 1. Loading

- **CFG-001** Configuration is read from `.claude/repo-config.yml` relative to the repository root.
- **CFG-002** The path is injectable, so tests and `adopt` can load a candidate file.
- **CFG-003** A missing file is an error naming the expected path, not an empty configuration.
- **CFG-004** Unparseable YAML is an error naming the file and the parse problem.
- **CFG-005** The loader is pure: given a path it returns a value or raises. It performs no network
  I/O and never mutates the file.
- **CFG-006** Parsing uses no third-party library. The subset of YAML accepted is documented in
  §6 and is a deliberate restriction, not an accident.

## 2. Validation

- **CFG-010** A loaded configuration is validated in code, and `schema/repo-config.schema.json`
  publishes the same contract for editors and `adopt`. The two are compared by test — same keys,
  same enums, same defaults — because two descriptions of one thing drift unless something
  compares them.
- **CFG-011** An unknown top-level key is an error, not ignored. A typo that silently does nothing
  is worse than a refusal.
- **CFG-012** A key of the wrong type is an error naming the key, the expected type, and what was
  found.
- **CFG-013** Every error names the key path, so a nested mistake is findable.
- **CFG-014** Validation reports every problem it can find, not only the first.
- **CFG-015** A valid configuration exposes defaults for every optional key, so a caller never
  writes `config.get(..., fallback)`.

## 3. Capabilities

- **CFG-020** `capabilities` is a list drawn from `substrate`, `hygiene`, `consistency`, `labels`,
  `release`, `pipeline`.
- **CFG-021** An unknown capability name is an error listing the valid names.
- **CFG-022** `substrate` is implied and need not be listed.
- **CFG-023** Enabling a capability whose dependencies are absent is an error naming the missing
  ones.
- **CFG-024** The dependency table is declared once in code and is the same table the design
  documents. *(manual: kept in step by the consistency gate in #4.)*
- **CFG-025** `profiles` is a list; an unknown profile name is an error.

## 4. Identity and authority

- **CFG-030** `owners` is a non-empty list of GitHub logins when `pipeline` is enabled.
- **CFG-031** A single owner is expressed as a list of one; there is no scalar form.
- **CFG-032** `bot.identity` is `github-actions` or `app`, defaulting to `github-actions`.
- **CFG-033** `bot.app_id_secret` and `bot.private_key_secret` are required when identity is `app`
  and forbidden otherwise.
- **CFG-034** `bot.login` is the login whose reactions count as the watermark, defaulting to
  `github-actions[bot]`.

## 5. Pipeline settings

- **CFG-040** `milestone_ordering` is `semver`, `date`, `lexical` or `none`, defaulting to
  `semver`.
- **CFG-041** `dashboard_issue` is a positive integer when `pipeline` is enabled.
- **CFG-042** `labels` maps each pipeline state name to the label used for it, defaulting to the
  canonical vocabulary.
- **CFG-043** Every canonical state has a mapping after defaults are applied; a partial mapping
  overrides only what it names.
- **CFG-044** Two states may not map to the same label.
- **CFG-045** `commands.test`, `commands.verify` and `commands.spec_validator` are shell strings,
  each optional.
- **CFG-046** `fire.endpoint_secret` and `fire.token_secret` name secrets, never values. A literal
  that looks like a credential is an error. `adopt` reads them to write the gatekeeper caller's
  `secrets:` block (`ADOPT-070`) — they are the only way a repository says which of its secrets
  hold the analysis routine's endpoint and token, so a repository that omits them has no triage.

## 6. The YAML subset

Parsing is stdlib-only, so the accepted subset is stated rather than inherited.

- **CFG-050** Mappings, lists, strings, integers, booleans and `null` are supported.
- **CFG-051** Nesting is by indentation, two spaces per level.
- **CFG-052** Comments begin with `#` and run to end of line.
- **CFG-053** Quoted strings preserve `#` and `:` inside them.
- **CFG-054** Anchors, aliases, multi-document files and flow style are not supported, and using
  one is an error that says so rather than misreading the file.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Loading | CFG-001–006 | `test_config_loading.py` |
| Validation | CFG-010–015 | `test_config_validation.py` |
| Capabilities | CFG-020–025 | `test_config_capabilities.py` |
| Identity | CFG-030–034 | `test_config_identity.py` |
| Pipeline settings | CFG-040–046 | `test_config_pipeline.py` |
| The YAML subset | CFG-050–054 | `test_yaml_subset.py` |
| Schema agreement | CFG-010 | `test_config_schema.py` |

**39 requirements, 38 `auto` and 1 `manual`.**
