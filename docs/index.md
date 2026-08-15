# ai-sdlc

The single source of truth for AI-assisted software development across a set of repositories.
It defines the issue lifecycle, the skills and agents that operate it, the CI workflows that
enforce it, and the house rules that govern it — once, so that every consuming repository behaves
identically without holding a copy of the logic.

## Start here

- **[Design](design.md)** — what ai-sdlc is: capabilities, the spec format, the testing
  architecture, the CI gates, distribution, and adoption.
- **[GitHub access](spec/github-api.md)** — the one module that touches the network, and the fake
  that stands in for it everywhere else.
- **[Gatekeeper specification](spec/gatekeeper.md)** — the first pipeline area specified, and the
  model for the rest.
- **[Migration plan](decisions/migration-plan.md)** — why it is being built, the evidence, and the
  decisions taken.

## Capabilities

A repository adopts what it wants. Capabilities are ordered by how much each assumes about how a
repository works.

| Capability | Assumes |
| --- | --- |
| substrate | a GitHub repository |
| hygiene | pull requests are how change lands |
| consistency | the repository has specs and tests |
| labels | nothing; the taxonomy itself is configuration |
| release | release-please |
| pipeline | a specific way of working: issues are triaged, approved by a human, then built |

A capability may depend only on capabilities below it, never above — which is what makes partial
adoption real rather than aspirational.
