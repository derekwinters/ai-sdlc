# Changelog

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
