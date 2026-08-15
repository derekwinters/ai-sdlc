# ai-sdlc

The single source of truth for AI-assisted software development across a set of repositories.
It defines the issue lifecycle, the skills and agents that operate it, the CI workflows that
enforce it, and the house rules that govern it — once, so that every consuming repository behaves
identically without holding a copy of the logic.

**Documentation:** https://derekwinters.github.io/ai-sdlc/

- [Design](docs/design.md) — capabilities, spec format, testing architecture, CI gates,
  distribution, adoption.
- [Gatekeeper specification](docs/spec/gatekeeper.md) — the first area specified.
- [Migration plan](docs/decisions/migration-plan.md) — why this exists and the decisions taken.

## Capabilities

A repository adopts what it wants, not all of it. Each capability is independently installable,
specified, and useful.

| Capability | Assumes |
| --- | --- |
| substrate | a GitHub repository |
| hygiene | pull requests are how change lands |
| consistency | the repository has specs and tests |
| labels | nothing; the taxonomy itself is configuration |
| release | release-please |
| pipeline | issues are triaged, approved by a human, then built |

A capability may depend only on capabilities below it, never above.

## Development

```bash
python3 -m unittest discover -s tests      # the suite: offline, no credentials

python3 -m lib.validators.specs            # every requirement has a test
python3 -m lib.validators.boundaries       # no capability imports from above it
python3 -m lib.validators.docs             # spec pages and site navigation agree
python3 -m lib.validators.actions          # third-party actions are pinned to a SHA

pip install -r docs/requirements.txt
mkdocs build --strict                      # the docs gate, as CI runs it
```

Every commit on `main` is a Conventional Commit — the squash-merge title is the commit
release-please parses, so it is checked before merge. `/VERSION` is written by release-please and
by nothing else.
