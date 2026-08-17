# Specification — Adoption (`ADOPT`)

Joining a repository to ai-sdlc, and moving it between versions afterwards.

Adoption is per-repository and run in place. There is no fleet operation: `adopt` reads and writes
only the repository it runs in. A single command that changed eleven repositories would be exactly
the "how many changes did that just make" problem this project exists to avoid.

`ADOPT` belongs to the **substrate** capability.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — `plan` writes nothing.** It is the read-only half, and it must stay safe to run on
> a repository you have not decided about.

> **Invariant — `apply` never replaces content it did not create.** Provenance decides. Anything
> else is a conflict for the owner to resolve, not a file to overwrite.

> **Invariant — `apply` refuses while an unacknowledged workflow listens on an event it claims.**
> Two handlers on one event is worse than none: they race, and both write.

> **Invariant — `apply` works on a branch, never the default branch.** Every adoption and every
> upgrade is a reviewable pull request.

---

## 1. Detecting

- **ADOPT-001** The repository's stack is detected from marker files.
- **ADOPT-002** Detection proposes profiles; it never enables them silently.
- **ADOPT-003** An undetectable stack is reported rather than guessed at.
- **ADOPT-004** Detection is reported so the owner can correct it.
- **ADOPT-005** An existing `repo-config.yml` takes precedence over detection.

## 2. Planning

- **ADOPT-010** `plan` reports every file it would create, update or leave.
- **ADOPT-011** `plan` makes no write of any kind.
- **ADOPT-012** `plan` reports the manual tasks the owner must do.
- **ADOPT-013** `plan` reports conflicts separately from ordinary changes.
- **ADOPT-014** `plan` reports trigger collisions separately again, because they are the dangerous
  ones.
- **ADOPT-015** `plan` on an already-adopted repository at the same version reports no changes.

## 3. Classification

Every path adoption owns falls into exactly one class.

- **ADOPT-020** **Absent** — nothing there; it will be created.
- **ADOPT-021** **Managed and current** — provenance matches the pin; left alone.
- **ADOPT-022** **Managed and stale** — provenance from an earlier pin; updated.
- **ADOPT-023** **Conflict** — present with no provenance, or content differing from what the pin
  says it should be; reported, never written.
- **ADOPT-024** Provenance is the frontmatter written at install: source repository, ref and
  content hash.
- **ADOPT-025** A file whose content hash matches its recorded provenance is unmodified; a
  differing hash means the consumer edited it, which is a conflict rather than a stale file.

## 4. Trigger collisions

- **ADOPT-030** An existing workflow listening on an event the adoption claims is a collision.
- **ADOPT-031** Collisions are detected from workflow triggers, not from file names. A collision
  between differently-named files is the one a file comparison misses.
- **ADOPT-032** `apply` refuses while a collision is unacknowledged.
- **ADOPT-033** A collision may be acknowledged, which records the decision in configuration
  rather than merely silencing it.
- **ADOPT-034** The events checked are those where the pipeline is the **sole writer**:
  `issue_comment` and `issues`. `pull_request` is deliberately excluded — almost every repository
  has a test or lint workflow on it, they coexist happily, and flagging them all would train the
  owner to acknowledge collisions without reading them, which defeats the mechanism entirely.
- **ADOPT-035** Collisions are only checked for events the adoption actually installs a handler
  for. A repository taking only the hygiene capability installs no issue handler, so another
  repository's issue workflow is not its concern.
- **ADOPT-036** A workflow adoption itself manages is never a collision. It is keyed on provenance
  rather than on the file name, so a consumer's hand-written `dashboard.yml` still collides — the
  name is precisely what would match.

> **How the spec is changing (#90).** §4 said a workflow listening on a claimed event is a
> collision, without excepting adoption's own. Installing `pipeline` therefore made every later
> `apply` refuse, and `ADOPT-046` — *upgrading is the same operation* — became false for exactly the
> repositories that had taken the most. Found upgrading `connor-multiplying-frogs` from v0.4.6 to
> v0.4.7, one command after the pipeline landed.

## 5. Applying

- **ADOPT-040** `apply` writes to a branch.
- **ADOPT-041** `apply` is idempotent: a second run with no version change writes nothing.
- **ADOPT-042** `apply` never renames an existing label.
- **ADOPT-043** `apply` never rewrites `CLAUDE.md`; it inserts an import line or reports that one
  is needed.
- **ADOPT-044** `apply` reuses an existing dashboard issue rather than creating a second.
- **ADOPT-045** `apply` records the version it installed, so the next run can compare.
- **ADOPT-046** Upgrading is the same operation: `apply` at a higher version updates managed files
  and leaves conflicts alone.

> **Invariant — a capability installs everything it references.** A workflow and the files that
> workflow reads land together, or neither lands.

- **ADOPT-047** Enabling a capability installs every file its workflows require, not only the
  workflows. `labels` installs `labels.core.yml` as well as `labels-sync.yml`; `hygiene` installs
  `house-rules.md` alongside the import line that points at it.

> **How the spec is changing (#75).** §5 described what `apply` writes without saying that the set
> has to be *complete*. Twice a capability then shipped half of itself: the `CLAUDE.md` import with
> no `house-rules.md` (#71), and `labels-sync.yml` with no `labels.core.yml` (#75). Both fail only
> when something runs — long after the review that should have caught them — and both were found by
> the first real consumer rather than by this repository. ADOPT-047 states the completeness rule
> that was assumed and unwritten.

## 6. Verifying

- **ADOPT-050** `verify` reports whether the repository matches its recorded version.
- **ADOPT-051** `verify` fails when an installed capability's dependencies are absent.
- **ADOPT-052** `verify` fails when a managed file has been edited locally.
- **ADOPT-053** `verify` reports recorded exceptions rather than hiding them, so a repository
  keeping its own version of something is visibly non-standard.
- **ADOPT-054** `verify` writes nothing.

## 7. Pinning a caller

A caller names the ai-sdlc workflow it runs. What it names it *by* is a security decision rather
than a formatting one: a reusable workflow runs with the **caller's** token, on `issue_comment` and
`issues`, in the consumer's repository.

> **Invariant — a caller references a commit SHA, never a tag or a branch.** A tag is a mutable
> pointer. Publishing it ourselves narrows who could move it; it does not make the reference
> immutable, and immutability is the property being relied on.

- **ADOPT-060** A caller's `uses:` names a full 40-character commit SHA, and its `ref:` input is
  that same SHA. The two cannot be allowed to disagree: a caller running one version of the
  workflow against another version of the code is exactly what pairing them prevents.
- **ADOPT-061** The SHA carries a trailing comment naming the version it resolves to. Forty
  characters of hexadecimal tell a reviewer nothing about how far behind they are, which was the
  one real advantage a tag had.
- **ADOPT-062** The command still takes a **version**. A human knows `v0.4.1`; nobody resolves a
  SHA by hand, and an upgrade stays a pull request moving one line because `apply` rewrites it.
- **ADOPT-063** Resolution from version to SHA goes through an injected resolver, so no test
  performs network I/O and the one-module network seam holds.
- **ADOPT-064** An annotated tag is dereferenced to the commit it points at. `refs/tags/v4` and
  `refs/tags/v4^{}` are different objects and only the second is a commit; pinning the tag object
  produces a reference that does not resolve.
- **ADOPT-065** A version that resolves to nothing is an error naming the version, never a caller
  written with an empty or partial ref.
- **ADOPT-066** The recorded pin holds the version and the SHA together, so `verify` at the same
  version needs no network.

> **Invariant — `ref` names a commit in ai-sdlc, never in the caller.** A reusable workflow may
> use it only when checking ai-sdlc out; handing it to a checkout of the caller's own repository
> asks GitHub for a commit that repository has never seen.

- **ADOPT-067** A reusable workflow checks the caller's repository out at the commit that
  triggered the run, and uses `inputs.ref` only on a checkout that also names
  `repository: derekwinters/ai-sdlc`. The two checkouts serve different purposes — one is the work
  being examined, the other is the code doing the examining — and conflating them fails as
  `upload-pack: not our ref`, at fetch time, before any step of the workflow runs.

> **How the spec is changing (#110).** §7 covered what a *caller* must write and said nothing
> about what the *callee* may do with it. `reusable-docs-build.yml` therefore passed `inputs.ref`
> to a checkout of the consumer's repository (#103), which worked in every test here and failed on
> the first consumer that ran it — ai-sdlc does not install its own callers, so this path is never
> exercised by its own CI. The rule is stated for the callee because that is where it can be
> checked.

> **Invariant — a caller grants exactly the permissions the workflow it calls requests.** Not
> fewer, or the run cannot start; not more, or adoption quietly widens what the pipeline may do.

- **ADOPT-068** A caller's `permissions:` block is derived from the reusable workflow it calls. A
  called workflow cannot be granted more than its caller holds, so a caller granting too little
  fails as `startup_failure` — no jobs, no logs, no annotation, which is close to silent.
- **ADOPT-069** Every reusable workflow ai-sdlc ships is reachable: some capability or profile
  installs a caller for it. A workflow nothing can install is indistinguishable from one that does
  not exist, and this is the gate that makes the next such omission fail here rather than in a
  consumer's repository.

- **ADOPT-070** A caller passes the secrets the workflow it calls declares, naming them from
  configuration. `fire.endpoint_secret` and `fire.token_secret` are the only place a repository can
  say which of its secrets hold the analysis routine's endpoint and token, and a caller that omits
  them hands the workflow empty strings. Named rather than inherited: `secrets: inherit` is one
  line and grants every secret the repository holds, which is the same mistake as a too-wide
  permissions block. A repository naming none gets no block, and a pipeline with no analysis
  routine keeps working.

> **How the spec is changing (#118).** §7 covered the caller's `uses:`, its `ref:` and its
> `permissions:`, and said nothing about secrets. Every caller `adopt` had ever written therefore
> omitted the `secrets:` block that `reusable-gatekeeper-comment.yml` declares, so `Fire` received
> empty strings and reported the routine as unconfigured — silently, because `GK-119` makes that a
> notice rather than an error. Triage had never run in `connor-multiplying-frogs` since adoption.
> `CFG-046` had specified how a repository names those secrets since before the pipeline shipped,
> and nothing read them.

> **How the spec is changing (#84).** Five defects of one shape reached a consumer before ADOPT-069
> existed — an import with no file (#71), a workflow with no manifest (#75), a permissions block too
> narrow to start (#78), a profile that installed nothing (#81), and a dashboard nothing could
> install (#84). Each was fixed on its own. ADOPT-047 states that a capability installs what it
> *references*; ADOPT-069 states the converse, that everything shipped is installable, which is the
> half that catches an omission rather than a dangling pointer.

> **How the spec is changing (#72).** Callers used to reference a tag — `@v0.4.1` — and §7 did not
> exist. The reason given was that a tag keeps an upgrade readable, and that a workflow we publish
> ourselves is not third-party code. The first is true and is now served by the trailing comment;
> the second confuses *who could move the tag* with *whether it can move*. Found adopting
> `connor-multiplying-frogs`, whose own action-pin checker rejected the caller `adopt` wrote and
> was right to. `VAL-056` moved with it, in the same direction.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Detecting | ADOPT-001–005 | `test_adopt_detect.py` |
| Planning | ADOPT-010–015 | `test_adopt_plan.py` |
| Classification | ADOPT-020–025 | `test_adopt_classify.py` |
| Trigger collisions | ADOPT-030–036 | `test_adopt_collision.py` |
| Applying | ADOPT-040–047 | `test_adopt_apply.py` |
| Verifying | ADOPT-050–054 | `test_adopt_verify.py` |
| Pinning a caller | ADOPT-060–066 | `test_adopt_pin.py` |
| What a callee may do | ADOPT-067 | `test_reusable_workflows.py` |
| Caller permissions | ADOPT-068–069 | `test_adopt_permissions.py` |
| Caller secrets | ADOPT-070 | `test_adopt_permissions.py` |

**48 requirements, all `auto`.**
