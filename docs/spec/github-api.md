# Specification — GitHub access (`API`)

Every GitHub read and write in ai-sdlc passes through one module. Nothing else opens a socket.

This exists so the rest of the system is testable without a network, without credentials, and
without a live repository. A seam that is one module wide can be faked completely; a dozen
scattered `urlopen` calls cannot.

`API` belongs to the **substrate** capability and depends on nothing.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — `lib/github.py` is the only module in the repository that performs network I/O.**
> Every other module receives a client and never constructs its own.

> **Invariant — no test performs network I/O.** The suite runs with no credentials and no
> connection. A test needing GitHub uses the fake.

> **Invariant — a read never writes.** No read operation may be implemented in terms of a request
> method that mutates state.

---

## 1. The client

- **API-001** The client is constructed with a token and a repository in `owner/name` form.
- **API-002** A request targets `https://api.github.com` by default; the base URL is injectable so
  the fake and tests can substitute one.
- **API-003** Every request sends the `Accept: application/vnd.github+json` header.
- **API-004** Every request sends an `X-GitHub-Api-Version` header pinned to a named constant, not
  a literal at the call site.
- **API-005** Every request authenticates with the token as a bearer credential.
- **API-006** A repository-relative path (`/issues/1`) is resolved against the configured
  repository; an absolute path (`/rate_limit`) is used unchanged.
- **API-007** The token is never logged, never included in an error message, and never returned in
  a result.

## 2. Failure

- **API-010** A non-2xx response raises a typed error carrying the status, the method, the path,
  and a bounded excerpt of the body.
- **API-011** The body excerpt is truncated to a fixed maximum so a large error page cannot flood
  a log.
- **API-012** A `401` says the credential is wrong rather than reporting a generic failure.
- **API-013** A `403` distinguishes a rate limit from a permission failure when the response
  headers allow it.
- **API-014** A transport failure — no connection, DNS, timeout — raises the same typed error with
  a status of `None` rather than escaping as a raw exception.
- **API-015** A response body that is not valid JSON raises the typed error rather than a decoder
  exception.
- **API-016** An empty response body is `None`, not an error. A `204` is the normal case.

## 3. Pagination

- **API-020** A collection read follows pages until a page arrives that is shorter than the page
  size.
- **API-021** Items keep their order across pages.
- **API-022** An exactly-full final page costs one additional empty request; the result is
  correct.
- **API-023** An empty first page yields an empty list, not an error.
- **API-024** A `null` page body is treated as empty rather than raising.
- **API-025** Pagination stops at a configured maximum page count, so a malformed cursor cannot
  loop forever.
- **API-026** Reaching the page cap is reported by the caller-visible result, not silently
  swallowed. *(manual: surfaced through a log line; asserted by the caller in `DASH`.)*

## 4. Operations

The vocabulary is deliberately small. Anything absent here is absent by design.

- **API-030** `issue(number)` reads one issue.
- **API-031** `issues(**filters)` reads issues, paginated.
- **API-032** `comments(issue)` reads an issue's comments, paginated, in ascending order.
- **API-033** `set_labels(issue, labels)` replaces an issue's labels.
- **API-034** `set_milestone(issue, number)` sets or clears an issue's milestone.
- **API-035** `comment(issue, body)` posts a comment.
- **API-036** `reactions(comment)` reads a comment's reactions, with each reaction's author.
- **API-037** `react(comment, content)` adds a reaction.
- **API-038** `unreact(comment, reaction)` removes one.
- **API-039** `milestones(state)` reads milestones, paginated.
- **API-040** `blocked_by(issue)` reads native dependency relationships.
- **API-047** `add_blocked_by(issue, blocker)` and `remove_blocked_by(issue, blocker)` manage a
  native dependency relationship. There is no MCP tool for these, which is why dependencies were
  previously written as prose the pipeline could not read.
- **API-044** `labels()` reads the repository's labels, paginated.
- **API-045** `create_label(name, color, description)` and
  `update_label(name, color, description)` manage one.
- **API-046** `delete_label(name)` removes one. This is the only deletion in the vocabulary; it
  exists because a label taxonomy needs to be able to retire a name, and it is guarded by the
  manifest's explicit delete list rather than being reachable from ordinary use.
- **API-042** `create_milestone(title, description, due_on)` creates one and returns it with its
  assigned number.
- **API-043** `update_milestone(number, **fields)` changes only the fields it is given.
- **API-041** The client exposes no operation that closes, reopens, or deletes an issue, and none
  that edits an issue body. Milestones are different: a milestone's state is a normal field, and
  closing one is reversible, so `update_milestone` may set it. Nothing deletes a milestone.

## 6. Reaching the module from a workflow

`lib/github.py` is imported by skills that reusable workflows run. A workflow that runs such a
skill without putting the repository root on `PYTHONPATH` fails on the import, before doing
anything at all.

- **API-060** A reusable workflow running a skill that imports `lib` sets `PYTHONPATH` to the root
  it checked out, and refers to that root by variable rather than hard-coding the checkout path —
  which is where a *consumer* checks ai-sdlc out and is not where ai-sdlc itself is.
- **API-061** A reusable workflow checks ai-sdlc out into `.ai-sdlc-checkout/`, never into the
  consumer's `.ai-sdlc/` configuration directory, and the `path:` it fetches to is the same
  directory `SKILL_ROOT` reads from. `actions/checkout` empties the directory it writes into, so
  fetching over `.ai-sdlc/` would replace the consumer's `repo-config.yml` with ai-sdlc's own —
  same name, same place, wrong repository — and every skill in that run would read the wrong
  configuration without saying so.

> **How the spec is changing (#150).** `.ai-sdlc/` was the checkout path and nothing else, so
> naming it as the consumer's configuration directory made two different things share one name in
> one working directory. The checkout path is an implementation detail of these workflows and
> nothing outside them names it; the configuration directory is committed, documented and pointed
> at. So the checkout moved. Found while drawing the seam in #150, before any consumer ran it.

> **How the spec is changing (#87).** `API` described the module and said nothing about reaching
> it. The gatekeeper workflow ran `python3 .ai-sdlc/…/main.py` with no `PYTHONPATH` and died on
> `ModuleNotFoundError: No module named 'lib'` — the pipeline's central workflow, which had never
> executed anywhere until `connor-multiplying-frogs` adopted it. Its siblings `labels-sync` and
> `dashboard` set `PYTHONPATH` correctly, so the defect was a difference between siblings, which is
> the kind of thing a test should hold still.

## 5. The fake

- **API-050** `FakeGitHub` implements the same interface and is constructed from a plain dictionary
  of repository state.
- **API-051** Writes through the fake mutate its state, so a test asserts on the result rather
  than on calls made.
- **API-052** The fake records every request in order, so a test can assert what was *not* called.
- **API-053** The fake can be told to fail a specific operation, so degradation paths are testable.
- **API-054** The fake paginates using the same page size as the real client, so pagination
  behaviour is exercised rather than bypassed.
- **API-055** The fake performs no I/O and imports no network library.
- **API-056** Where a value changes meaning as it crosses the boundary, the fake models the change
  rather than the happy case. An issue's database id is not its number, so the fake gives every
  issue an id unlike its number and its dependency edges carry both. A double in which two distinct
  identities are equal cannot express a client confusing them, and a suite written against it is
  green for a defect it structurally cannot see (#155).

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| The client | API-001–007 | `test_github_client.py` |
| Failure | API-010–016 | `test_github_failure.py` |
| Pagination | API-020–026 | `test_github_pagination.py` |
| Operations | API-030–041 | `test_github_operations.py` |
| The fake | API-050–056 | `test_fake_github.py` |
| Reaching it from a workflow | API-060–061 | `test_reusable_workflows.py` |
| Invariants | — | `test_architecture.py` |

**53 requirements, 52 `auto` and 1 `manual`.**
