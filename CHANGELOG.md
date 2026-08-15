# Changelog

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
