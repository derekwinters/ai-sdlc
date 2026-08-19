# Changelog

## [0.4.19](https://github.com/derekwinters/ai-sdlc/compare/v0.4.18...v0.4.19) (2026-08-19)


### ⚠ BREAKING CHANGES

* **substrate:** the hygiene and mkdocs gates become actions, checking nothing out ([#162](https://github.com/derekwinters/ai-sdlc/issues/162))

### Features

* **substrate:** the hygiene and mkdocs gates become actions, checking nothing out ([#162](https://github.com/derekwinters/ai-sdlc/issues/162)) ([bc1b403](https://github.com/derekwinters/ai-sdlc/commit/bc1b4030a005f030d623a65a380c75d9007f1d76)), closes [#161](https://github.com/derekwinters/ai-sdlc/issues/161)


### Fixes

* **pipeline:** name a blocker by its database id, not its issue number ([#159](https://github.com/derekwinters/ai-sdlc/issues/159)) ([b06b6a5](https://github.com/derekwinters/ai-sdlc/commit/b06b6a5be5d1d554235a98406d8082d55b07a03d)), closes [#155](https://github.com/derekwinters/ai-sdlc/issues/155)

## [0.4.18](https://github.com/derekwinters/ai-sdlc/compare/v0.4.17...v0.4.18) (2026-08-18)


### ⚠ BREAKING CHANGES

* **substrate:** `repo-config.yml`, `ai-sdlc.pin` and `house-rules.md` move from `.claude/` to `.ai-sdlc/`. `adopt apply` performs the move; a repository that has not run it reports the move rather than reading the old path.

### Features

* **substrate:** ai-sdlc's files move to .ai-sdlc/, and a skill points at them ([#151](https://github.com/derekwinters/ai-sdlc/issues/151)) ([7ca29b1](https://github.com/derekwinters/ai-sdlc/commit/7ca29b12b797fa446ab85650db3c2b71252027aa)), closes [#150](https://github.com/derekwinters/ai-sdlc/issues/150)

## [0.4.17](https://github.com/derekwinters/ai-sdlc/compare/v0.4.16...v0.4.17) (2026-08-18)


### ⚠ BREAKING CHANGES

* **pipeline:** the `ai-triage` label is replaced by `ai-triage-queued`, `ai-triage-running` and `ai-triage-stalled`. An adopting repository must relabel issues carrying `ai-triage` to `ai-triage-queued` after adopting this version. `ai-triage` is deliberately not deleted by label sync: deleting a label strips it from every issue holding it, so any issue not yet relabelled would fall out of the pipeline with no state at all.

### Features

* **pipeline:** three triage states, and a sweep that only detects ([#137](https://github.com/derekwinters/ai-sdlc/issues/137)) ([1d5b25e](https://github.com/derekwinters/ai-sdlc/commit/1d5b25e7147f1089217e0591e4dbf7adcb7e2518)), closes [#136](https://github.com/derekwinters/ai-sdlc/issues/136)
* **substrate:** install and update a consumer's skills, never overwriting one ([#146](https://github.com/derekwinters/ai-sdlc/issues/146)) ([30f6500](https://github.com/derekwinters/ai-sdlc/commit/30f6500c13bc61a9959cc207726d9dcf5bfa9fa6)), closes [#144](https://github.com/derekwinters/ai-sdlc/issues/144)

## [0.4.16](https://github.com/derekwinters/ai-sdlc/compare/v0.4.15...v0.4.16) (2026-08-17)


### Fixes

* **gatekeeper:** never report the session a fire created ([#133](https://github.com/derekwinters/ai-sdlc/issues/133)) ([d6f6884](https://github.com/derekwinters/ai-sdlc/commit/d6f68847f5c70ac8bbdcc55695e06aaf00220b60)), closes [#132](https://github.com/derekwinters/ai-sdlc/issues/132)

## [0.4.15](https://github.com/derekwinters/ai-sdlc/compare/v0.4.14...v0.4.15) (2026-08-17)


### Fixes

* **gatekeeper:** log the session a fire created ([#130](https://github.com/derekwinters/ai-sdlc/issues/130)) ([5edc591](https://github.com/derekwinters/ai-sdlc/commit/5edc5918cd58876375d87e41b3d91247265847f4)), closes [#129](https://github.com/derekwinters/ai-sdlc/issues/129)

## [0.4.14](https://github.com/derekwinters/ai-sdlc/compare/v0.4.13...v0.4.14) (2026-08-17)


### Fixes

* **pipeline:** send a fire request the routine endpoint accepts ([#127](https://github.com/derekwinters/ai-sdlc/issues/127)) ([bb2ebe8](https://github.com/derekwinters/ai-sdlc/commit/bb2ebe8f697f44a8bd61067093a08fb5c4bca2aa)), closes [#126](https://github.com/derekwinters/ai-sdlc/issues/126)

## [0.4.13](https://github.com/derekwinters/ai-sdlc/compare/v0.4.12...v0.4.13) (2026-08-17)


### Features

* **pipeline:** fire triage from the label event, not the gatekeeper ([c6396ba](https://github.com/derekwinters/ai-sdlc/commit/c6396ba3482c2236271cae1d95a2cb52e9302110)), closes [#123](https://github.com/derekwinters/ai-sdlc/issues/123)


### Fixes

* **gatekeeper:** report what became of the analysis routine ([c8300b6](https://github.com/derekwinters/ai-sdlc/commit/c8300b665d9ed852ffa702c4b7a0387798ea785c)), closes [#121](https://github.com/derekwinters/ai-sdlc/issues/121)


### Chores

* release 0.4.13 ([bbb7032](https://github.com/derekwinters/ai-sdlc/commit/bbb70323562ac3c4cb145bb6306ff89696634322))

## [0.4.12](https://github.com/derekwinters/ai-sdlc/compare/v0.4.11...v0.4.12) (2026-08-17)


### Fixes

* **adopt:** pass the analysis routine's secrets to the caller ([0a1457b](https://github.com/derekwinters/ai-sdlc/commit/0a1457b29e3858e99a5957af9f91a2e3a2eeffaa)), closes [#118](https://github.com/derekwinters/ai-sdlc/issues/118)

## [0.4.11](https://github.com/derekwinters/ai-sdlc/compare/v0.4.10...v0.4.11) (2026-08-16)


### Fixes

* **dashboard:** link a milestone by its name, not its number ([d347583](https://github.com/derekwinters/ai-sdlc/commit/d34758387954b6bdd1ce7fb6a9ddcf320f8e0eba)), closes [#115](https://github.com/derekwinters/ai-sdlc/issues/115)

## [0.4.10](https://github.com/derekwinters/ai-sdlc/compare/v0.4.9...v0.4.10) (2026-08-16)


### Fixes

* **gatekeeper:** perform the re-render instead of returning a flag ([43d63c0](https://github.com/derekwinters/ai-sdlc/commit/43d63c046133fa05619022f3a17c8886a09df9f5)), closes [#112](https://github.com/derekwinters/ai-sdlc/issues/112)

## [0.4.9](https://github.com/derekwinters/ai-sdlc/compare/v0.4.8...v0.4.9) (2026-08-16)


### ⚠ BREAKING CHANGES

* **mkdocs:** `reusable-docs.yml` is removed. Nothing could install it, so no adopted repository references it, but a hand-written caller pointing at it will stop resolving.

### Features

* **dashboard:** rebuild the board as two charts and five sections ([#108](https://github.com/derekwinters/ai-sdlc/issues/108)) ([86edeee](https://github.com/derekwinters/ai-sdlc/commit/86edeee56e7f976a9c1ab85f3038984eabcc8a51)), closes [#106](https://github.com/derekwinters/ai-sdlc/issues/106)
* **docs:** publish to a gh-pages branch instead of a Pages artifact ([dcc9015](https://github.com/derekwinters/ai-sdlc/commit/dcc9015abef9403ca67a2ad857a694acfb076fee)), closes [#93](https://github.com/derekwinters/ai-sdlc/issues/93)
* **docs:** version the published site with mike ([#98](https://github.com/derekwinters/ai-sdlc/issues/98)) ([691d03d](https://github.com/derekwinters/ai-sdlc/commit/691d03d4036863d1576534688ff4523cc5bbdbe8)), closes [#96](https://github.com/derekwinters/ai-sdlc/issues/96)
* **mkdocs:** install a strict build, and ship no publisher ([#103](https://github.com/derekwinters/ai-sdlc/issues/103)) ([8eef8a2](https://github.com/derekwinters/ai-sdlc/commit/8eef8a2c5b52712682b93712c3c6fd45af266fa6)), closes [#100](https://github.com/derekwinters/ai-sdlc/issues/100)


### Fixes

* **mkdocs:** stop checking the consumer out at an ai-sdlc commit ([#111](https://github.com/derekwinters/ai-sdlc/issues/111)) ([9bc3ecc](https://github.com/derekwinters/ai-sdlc/commit/9bc3eccf38473fd0b24a1c4f52b2ae61ed7db71e)), closes [#110](https://github.com/derekwinters/ai-sdlc/issues/110)


### Chores

* release 0.4.9 ([b5361a5](https://github.com/derekwinters/ai-sdlc/commit/b5361a5e34fb6310ac1542050eaa6ff4fe6309fa))

## [0.4.8](https://github.com/derekwinters/ai-sdlc/compare/v0.4.7...v0.4.8) (2026-08-15)


### Fixes

* **adopt:** do not treat our own callers as collisions ([#91](https://github.com/derekwinters/ai-sdlc/issues/91)) ([cb58740](https://github.com/derekwinters/ai-sdlc/commit/cb58740d57985ab8d4a5798a39d37b45317ca25c)), closes [#90](https://github.com/derekwinters/ai-sdlc/issues/90)

## [0.4.7](https://github.com/derekwinters/ai-sdlc/compare/v0.4.6...v0.4.7) (2026-08-15)


### Fixes

* **gk:** give the gatekeeper workflows a PYTHONPATH and a SKILL_ROOT ([#88](https://github.com/derekwinters/ai-sdlc/issues/88)) ([a88c9c2](https://github.com/derekwinters/ai-sdlc/commit/a88c9c26361bb50e5ec87b3f92fb9067864a989b)), closes [#87](https://github.com/derekwinters/ai-sdlc/issues/87)

## [0.4.6](https://github.com/derekwinters/ai-sdlc/compare/v0.4.5...v0.4.6) (2026-08-15)


### Fixes

* **adopt:** install a dashboard caller, and gate reachability ([#85](https://github.com/derekwinters/ai-sdlc/issues/85)) ([f02048f](https://github.com/derekwinters/ai-sdlc/commit/f02048ffc6a4b74c56f39d2a6bb69bfa32c8b19d)), closes [#84](https://github.com/derekwinters/ai-sdlc/issues/84)

## [0.4.5](https://github.com/derekwinters/ai-sdlc/compare/v0.4.4...v0.4.5) (2026-08-15)


### Fixes

* **adopt:** install a selected profile's files ([#82](https://github.com/derekwinters/ai-sdlc/issues/82)) ([36b180d](https://github.com/derekwinters/ai-sdlc/commit/36b180df01383b6d0dcfc37ddabca273282635af)), closes [#81](https://github.com/derekwinters/ai-sdlc/issues/81)

## [0.4.4](https://github.com/derekwinters/ai-sdlc/compare/v0.4.3...v0.4.4) (2026-08-15)


### Fixes

* **adopt:** grant callers the permissions their workflows request ([#79](https://github.com/derekwinters/ai-sdlc/issues/79)) ([dca777b](https://github.com/derekwinters/ai-sdlc/commit/dca777b9a6dafae034099f4027a7a3eaa8c8c6cc)), closes [#78](https://github.com/derekwinters/ai-sdlc/issues/78)

## [0.4.3](https://github.com/derekwinters/ai-sdlc/compare/v0.4.2...v0.4.3) (2026-08-15)


### Fixes

* **adopt:** install labels.core.yml with the labels capability ([#76](https://github.com/derekwinters/ai-sdlc/issues/76)) ([6ea1630](https://github.com/derekwinters/ai-sdlc/commit/6ea1630ed497f560cbb8493d0c1f5be98b041ab6)), closes [#75](https://github.com/derekwinters/ai-sdlc/issues/75)

## [0.4.2](https://github.com/derekwinters/ai-sdlc/compare/v0.4.1...v0.4.2) (2026-08-15)


### Fixes

* **adopt:** pin caller workflows to a commit SHA, not a tag ([#73](https://github.com/derekwinters/ai-sdlc/issues/73)) ([2ac874e](https://github.com/derekwinters/ai-sdlc/commit/2ac874e51f66b68699f4c16044c41665c454d062)), closes [#72](https://github.com/derekwinters/ai-sdlc/issues/72)

## [0.4.1](https://github.com/derekwinters/ai-sdlc/compare/v0.4.0...v0.4.1) (2026-08-15)


### Features

* **rel:** add a workflow-dispatch backfill for missing release tags ([#67](https://github.com/derekwinters/ai-sdlc/issues/67)) ([e1698f3](https://github.com/derekwinters/ai-sdlc/commit/e1698f366506f063e825be257fe446682b59b711)), closes [#49](https://github.com/derekwinters/ai-sdlc/issues/49)
* **rel:** refuse a release that spends an open milestone's version ([#68](https://github.com/derekwinters/ai-sdlc/issues/68)) ([4644c2a](https://github.com/derekwinters/ai-sdlc/commit/4644c2a372745cf5d2a9da25999451fb3b56f332)), closes [#31](https://github.com/derekwinters/ai-sdlc/issues/31)


### Fixes

* **ci:** pin every action to a commit SHA and gate it ([#65](https://github.com/derekwinters/ai-sdlc/issues/65)) ([604cd01](https://github.com/derekwinters/ai-sdlc/commit/604cd0116c818406347b449f702faa412eca1086)), closes [#64](https://github.com/derekwinters/ai-sdlc/issues/64)

## 0.4.0 (2026-08-15)

Adoption. A repository can now join ai-sdlc — or move between versions — through one reviewable
pull request, taking only the capabilities it wants.

### Features

* **adopt:** the adopt command — plan, apply, verify ([#60](https://github.com/derekwinters/ai-sdlc/pull/60))
* **prof:** the mkdocs profile and the documentation gate ([#61](https://github.com/derekwinters/ai-sdlc/pull/61))
* **rules:** the shared house-rules fragment ([#62](https://github.com/derekwinters/ai-sdlc/pull/62))

### Notable decisions

* **`adopt` never overwrites what it did not write.** Provenance carries a content hash, so a
  locally-edited managed file is a conflict rather than a stale one ([#60](https://github.com/derekwinters/ai-sdlc/pull/60))
* **`pull_request` is not a claimed event.** Flagging every repository's test workflow would train
  the owner to acknowledge collisions without reading them ([#60](https://github.com/derekwinters/ai-sdlc/pull/60))
* **A profile is inert when not selected** — a repository that merely has a docs directory is not
  thereby gated ([#61](https://github.com/derekwinters/ai-sdlc/pull/61))
* **The house rules name the gate where one exists**, rather than restating an enforced rule as
  advice ([#62](https://github.com/derekwinters/ai-sdlc/pull/62))

### At this release

* 481 requirements: 473 covered by a named test, 8 explicitly manual, 0 planned
* 1214 tests, all offline
* 6 capabilities, 3 distribution channels, 13 specification areas

## 0.3.0 (2026-08-15)

The working loop. The full issue lifecycle now exists — admit, triage, approve, queue, build,
watch CI, release — and ai-sdlc has the agent that does the building.

### Features

* **tri:** issue triage, which proposes and never approves ([#55](https://github.com/derekwinters/ai-sdlc/pull/55))
* **dev:** the development queue and the stack-agnostic `dev` agent ([#56](https://github.com/derekwinters/ai-sdlc/pull/56))
* **ciw:** CI watch, which reports and never fixes ([#57](https://github.com/derekwinters/ai-sdlc/pull/57))
* **rel:** the release flow, with the gotchas written down as code ([#58](https://github.com/derekwinters/ai-sdlc/pull/58))

### Notable decisions

* **Triage cannot queue work.** No outcome maps to the approved state, so the constraint is
  structural rather than an instruction ([#55](https://github.com/derekwinters/ai-sdlc/pull/55))
* **Blockedness is derived at selection time**, which is what makes the deleted revisit sweep
  unnecessary ([#56](https://github.com/derekwinters/ai-sdlc/pull/56))
* **Nothing having run is not the same as everything having passed** — `no-checks` is a distinct
  outcome in both CI watch and the release gate ([#57](https://github.com/derekwinters/ai-sdlc/pull/57), [#58](https://github.com/derekwinters/ai-sdlc/pull/58))
* **The release flow is pure**, so no code path can reopen a release pull request to restart
  parked checks ([#58](https://github.com/derekwinters/ai-sdlc/pull/58))

### At this release

* 416 requirements: 408 covered by a named test, 8 explicitly manual, 0 planned
* 1064 tests, all offline

## 0.2.0 (2026-08-15)

Pipeline state and visibility. The pipeline can now describe its own state — milestones, labels
and dependencies — and report what has gone wrong with it.

### Features

* **ms:** milestone operations, including the create and edit the MCP server does not provide ([#50](https://github.com/derekwinters/ai-sdlc/pull/50))
* **lbl:** the label taxonomy and its sync, in git rather than clicked into the interface ([#51](https://github.com/derekwinters/ai-sdlc/pull/51))
* **blk:** native issue dependency tooling, with prose blockers reported as drift ([#52](https://github.com/derekwinters/ai-sdlc/pull/52))
* **dash:** the pipeline dashboard, reporting every fault the pipeline deliberately does not repair ([#53](https://github.com/derekwinters/ai-sdlc/pull/53))

### Notable decisions

* **A prose `Blocked by #N` is found, reported, and never honoured.** Honouring it would make the
  invisible-to-tooling form work, so it would stay ([#52](https://github.com/derekwinters/ai-sdlc/pull/52))
* **Nothing deletes a label unless explicitly listed.** Deleting one strips it from every issue
  that carried it ([#51](https://github.com/derekwinters/ai-sdlc/pull/51))
* **An empty dashboard fault section is omitted**, so a healthy pipeline renders about a dozen
  lines and length itself is the signal ([#53](https://github.com/derekwinters/ai-sdlc/pull/53))

### At this release

* 320 requirements: 314 covered by a named test, 6 explicitly manual, 0 planned
* 858 tests, all offline

## 0.1.0 (2026-08-15)

The gatekeeper pilot. ai-sdlc has a specification, a test suite that enforces it, and its first
consumer — itself.

### Features

* **api:** the GitHub seam and its fake, the one module permitted to perform network I/O ([#34](https://github.com/derekwinters/ai-sdlc/pull/34))
* **cfg:** the repository configuration schema and loader, including a stdlib YAML reader ([#35](https://github.com/derekwinters/ai-sdlc/pull/35))
* **val:** the consistency gates — spec↔test traceability, capability boundaries, spec↔site parity ([#36](https://github.com/derekwinters/ai-sdlc/pull/36))
* **gk:** authority and identity — owner list, bot identity, silent refusal ([#37](https://github.com/derekwinters/ai-sdlc/pull/37))
* **gk:** command parsing — eleven commands, fenced blocks ignored, typos suggested not applied ([#38](https://github.com/derekwinters/ai-sdlc/pull/38))
* **gk:** scope and argument checking ([#39](https://github.com/derekwinters/ai-sdlc/pull/39))
* **gk:** approval gates and configurable milestone ordering ([#40](https://github.com/derekwinters/ai-sdlc/pull/40))
* **gk:** the three-state watermark and acknowledgements ([#41](https://github.com/derekwinters/ai-sdlc/pull/41))
* **gk:** per-issue catch-up and `/retry` ([#42](https://github.com/derekwinters/ai-sdlc/pull/42))
* **gk:** lifecycle event handling ([#43](https://github.com/derekwinters/ai-sdlc/pull/43))
* **gk:** downstream effects — triage firing and dashboard re-render ([#44](https://github.com/derekwinters/ai-sdlc/pull/44))
* **gk:** packaging, reusable workflows, and the closing-keyword required check ([#45](https://github.com/derekwinters/ai-sdlc/pull/45))
* **adopt:** ai-sdlc becomes its own first consumer ([#46](https://github.com/derekwinters/ai-sdlc/pull/46))

### Documentation

* the design, migration plan, and gatekeeper specification ([#32](https://github.com/derekwinters/ai-sdlc/pull/32))
* the core restructured into six independently installable capabilities ([#32](https://github.com/derekwinters/ai-sdlc/pull/32))

### Fixes worth naming

* **the milestone-ordering gate no longer refuses on absence of evidence.** It previously treated
  "I cannot compare these milestones" as "this is inverted", which made any issue blocked by one in
  a standing non-version milestone permanently unapprovable ([#40](https://github.com/derekwinters/ai-sdlc/pull/40))
* **the spec validator read only a requirement's first line**, so a `*(manual: …)*` marker that had
  wrapped was invisible — six of them across four pages ([#45](https://github.com/derekwinters/ai-sdlc/pull/45))
* **reusable workflows moved to `.github/workflows/`.** GitHub only resolves a `uses:` reference to
  a workflow living there, so the root `workflows/` directory could never have been called
  ([#46](https://github.com/derekwinters/ai-sdlc/pull/46))

### At this release

* 209 requirements: 203 covered by a named test, 6 explicitly manual, 0 planned
* 623 tests, all offline, no credentials, no network
* 6 capabilities, boundaries enforced by CI
