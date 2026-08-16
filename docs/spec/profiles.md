# Specification — Profiles (`PROF`)

Opt-in behaviour shared by a family of repositories, layered on whichever capabilities are
installed.

A profile adds; it never alters a capability's behaviour. That distinction is what keeps profiles
from becoming a second configuration system: if a profile needed to change how a capability
behaves, the right answer is a capability, not a flag.

`PROF` belongs to the **substrate** capability, which owns profile selection; each profile's own
content belongs to itself.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a profile adds behaviour; it never alters a capability's.** A profile that changes
> what a capability does is a capability wearing a disguise.

> **Invariant — a profile is inert when not selected.** Installing ai-sdlc must not make a
> repository run a docs gate it never asked for.

---

## 1. Selection

- **PROF-001** A profile is enabled only by being listed in configuration.
- **PROF-002** Detection proposes profiles; it never enables one.
- **PROF-003** An unknown profile name is a configuration error.
- **PROF-004** A profile whose files are absent is inert rather than an error.
- **PROF-005** Selecting a profile **installs** that profile's files. PROF-004 makes an absent
  profile harmless, which is right — but it also made a profile that installs nothing look
  identical to one that works, and `mkdocs` shipped fully specified and entirely inert.

> **How the spec is changing (#81).** §1 described how a profile is *selected* and said nothing
> about a selection having any effect. `adopt` accordingly installed capability files and never
> looked at profiles, so enabling `mkdocs` produced no documentation gate and no error — the
> failure PROF-004 was written to tolerate, wearing the same face as success. This is the fourth
> defect of the shape "something ships incomplete", after #71, #75 and #78.

## 2. The mkdocs profile

What a repository selecting `mkdocs` gets: a strict build and a reconciliation gate. Nothing else.

- **PROF-010** It provides a strict documentation build as a pull request check, and installs it.
- **PROF-011** A build warning fails the check. Strict mode exists because a broken link is a
  broken page, and a warning nobody sees is a broken page shipped.

> **Invariant — the profile installs no publisher.** Publishing is the most repository-specific
> thing there is: Pages or a branch, versioned or not, which alias scheme, which requirements file.
> A shared build is the same everywhere; a shared publisher is a guess about someone else's site.

- **PROF-012** The profile installs no publisher, and the workflow it does install has no means to
  become one — no `gh-pages` push, no `mike`, no Pages action, and `contents: read` and nothing
  more. A consumer already publishing keeps its own arrangement; one that is not decides for
  itself.

> **How the spec is changing (#100).** §2 used to specify a build *and* a publisher, delivered as
> one workflow — `PROF-012` said the profile publishes on merge, `PROF-013` that publication is
> skipped when the build fails, `PROF-014` that it pushes `gh-pages`, `PROF-015` that the site is
> versioned. Bundling them meant the build could not be installed without the publisher, so
> `adopt` installed neither, and `reusable-docs.yml` sat unreachable behind an explicit ADOPT-069
> exemption — specified, tested, and impossible to reach, the same shape as #81. The build is now
> its own workflow and is installed; the publisher is deleted. `PROF-013`–`015` are not gone: they
> were never really about the profile, and now say so in §3.

## 3. This repository's own documentation site

Not part of the profile, and not installed anywhere. ai-sdlc publishes its own specification, and
these requirements describe that — kept because the behaviour is real and tested, moved because
filing it under the profile is what let a consumer-facing publisher be specified by accident.

- **PROF-013** Publication happens only from the default branch, never from a pull request, and
  only after the strict build has passed. Publishing a site that failed to build replaces a working
  one with a broken one.
- **PROF-014** Publication is a push to a **`gh-pages` branch**, not an upload to GitHub's Pages
  artifact pipeline. It therefore needs `contents: write` and no other grant — no `pages: write`,
  no OIDC token exchange — and depends on no third-party action.
- **PROF-015** The published site is **versioned**. Each release series gets its own tree and
  `latest` follows the newest, so a repository pinned three releases back reads the specification
  for the code it is actually running. The version is read from the release manifest rather than
  written anywhere a second time.

> **How the spec is changing (#96).** `PROF-010`–`014` described one site, published from `main`.
> That is wrong for a project whose consumers **pin a version**: they read the specification to know
> what their pinned version does, and an unversioned site can only ever answer for `main`. Versions
> are per release series — `0.4.7` and `0.4.8` do not describe different systems, so they share a
> tree — and `latest` is the alias a bare URL resolves to.

> **How the spec is changing (#93).** `PROF-012` said the profile publishes on merge and left the
> mechanism open, and the implementation used `upload-pages-artifact`, `configure-pages` and
> `deploy-pages`. It now names the mechanism, because the mechanism turned out to matter: this
> repository requires actions to be SHA-pinned and the policy reaches *inside* composite actions, so
> `upload-pages-artifact@v3` — which calls `actions/upload-artifact@v4` unpinned in its own
> `action.yml` — was refused before it ran (#64). Moving to v5 fixed it by relying on someone else's
> pinning discipline, rechecked at every bump. A branch push has no such surface.

## 4. The documentation gate

- **PROF-020** A pull request that changes code and no documentation fails the gate.
- **PROF-021** The `skip-docs` label makes the gate **pass**, never skip. A skipped required check
  stays pending and blocks the merge it was meant to permit.
- **PROF-022** A pull request changing only documentation passes.
- **PROF-023** A pull request changing neither passes; there is nothing to reconcile.
- **PROF-024** What counts as documentation is configurable, defaulting to `docs/` and `*.md`.
- **PROF-025** The gate reports which files it judged code and which documentation, so a
  surprising verdict is explainable.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Selection | PROF-001–005 | `test_profiles.py` |
| The mkdocs profile | PROF-010–012 | `test_profiles.py` |
| This repository's own site | PROF-013–015 | `test_profiles.py` |
| The documentation gate | PROF-020–025 | `test_docs_gate.py` |

**17 requirements, all `auto`.**
