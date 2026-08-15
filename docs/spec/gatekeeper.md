# Specification — Gatekeeper (`GK`)

The gatekeeper is the only component permitted to move an issue through the pipeline state
machine. It translates the repository owner's commands, written as comments, into label changes,
and it refuses commands that would violate a pipeline rule.

`GK` belongs to the **pipeline** capability and may depend on every capability below it.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — the gatekeeper writes only in response to a command from the configured owner.**
> No inference, no heuristics, no acting on anyone else's comment.

> **Invariant — a command is applied at most once, however many times its comment is seen.**

> **Invariant — every owner command ends in exactly one of 👍 or 👎. A 👀 that outlives its run is
> a visible fault, never a silent drop.**

> **Invariant — blockedness is derived from the dependency graph at selection time, never stored
> as a label. An issue is never moved out of its state because it is blocked.**

> **Invariant — the gatekeeper never closes, reopens, deletes, or edits an issue body.** Its whole
> vocabulary is labels, milestones, reactions, and comments. A command set that can do irreversible
> things eventually does one by accident.

> **Invariant — a refusal changes nothing.** A refused command leaves labels, milestone, and
> pipeline state exactly as they were.

---

## 1. State machine

An issue occupies exactly one **pipeline state**, expressed as a label. State names are
configurable; the defaults are given here.

| State | Default label | Meaning | Written by |
|---|---|---|---|
| untracked | *(no pipeline label)* | not in the pipeline | — |
| triage | `ai-triage` | admitted; awaiting or undergoing analysis | gatekeeper |
| pending approval | `pending-approval` | analysis produced a plan; awaiting the owner's decision | analysis |
| clarification | `needs-clarification` | analysis needs a human answer | analysis |
| approved | `ready-for-work` | plan accepted; eligible for the builder | gatekeeper |
| building | `in-progress` | a builder has taken it | builder |
| parked | `parked` | deliberately set aside | gatekeeper |

- **GK-001** An issue carries at most one pipeline-state label at any time.
- **GK-002** Applying a state removes whatever state label was present, and only state labels.
- **GK-003** Labels outside the state vocabulary — `area:*`, `type:*`, `skip-docs` — are never
  added or removed by the gatekeeper. A state change that dropped them would discard the triage
  decision.
- **GK-004** `type:epic` and `type:wireframe` are classification labels, not states, and are never
  altered.
- **GK-005** The gatekeeper never writes `pending-approval`, `needs-clarification`, or
  `in-progress`. Those states are entered by analysis and by the builder; the gatekeeper only
  reads them and moves issues out of them.

---

## 2. Authority and identity

- **GK-010** A command is honoured only when the comment author's login appears in the configured
  owner list. A single-owner repository is a list of one, not a special case.
- **GK-011** The owner comparison is case-insensitive.
- **GK-012** Authority is determined by login, never by `author_association`.
- **GK-013** A command from a login outside the owner list is dropped silently: no labels, no
  reaction, no reply.
- **GK-014** Comments authored by the configured bot identity are never treated as commands.
- **GK-015** Comments authored by any account whose login ends in `[bot]` are never treated as
  commands.
- **GK-016** Comments on pull requests are ignored; the gatekeeper acts on issues only.
- **GK-017** All writes are authored by the configured bot identity, never by the owner's account.
- **GK-018** The bot identity is read from configuration and defaults to `github-actions[bot]`.
- **GK-019** An empty owner list honours nothing. Authority is never inferred from repository
  permissions when configuration is missing.

---

## 3. Command vocabulary

Eleven commands. Ten are carried over unchanged from both existing implementations; `/retry` is
new.

| Command | Argument | Scope | Effect |
|---|---|---|---|
| `/admit` | — | issue | → triage |
| `/propose` | — | issue | → triage, asking analysis for a plan |
| `/approve` | — | issue | pending approval → approved |
| `/revise` | notes | issue | → triage, carrying notes |
| `/redo` | — | issue | built work is wrong → approved, requeued |
| `/park` | — | issue | → parked |
| `/unpark` | — | issue | parked → triage |
| `/milestone` | title | issue | set the issue's milestone |
| `/focus` | title | dashboard | set the pipeline's focus milestone |
| `/cap` | integer | dashboard | set max concurrent building issues |
| `/retry` | — | issue | re-process this issue's unfinished commands |

### Parsing

- **GK-020** A command is recognised only at the start of a line, allowing up to three leading
  spaces.
- **GK-021** A command inside a fenced code block (``` or `~~~`) is ignored.
- **GK-022** A `/word` appearing mid-line — in a URL or in prose — is not a command.
- **GK-023** Prose surrounding a command line does not prevent the command being recognised.
- **GK-024** An argument is the remainder of the line, trimmed; a command with no argument has an
  empty one.
- **GK-025** Multiple commands in one comment are applied in the order written.
- **GK-026** A comment containing no command yields no action and no reaction.
- **GK-027** An unknown command is skipped, never guessed at.
- **GK-028** An unknown command's acknowledgement names the closest matching known command when
  one is within edit distance; otherwise it lists the vocabulary.

### Scope

- **GK-030** `/focus` and `/cap` are honoured only on the configured dashboard issue.
- **GK-031** `/focus` and `/cap` on any other issue are refused.
- **GK-032** Issue-scoped commands are refused on the dashboard issue.
- **GK-033** A comment on the dashboard combining `/focus` with an issue-scoped command applies
  the `/focus` and refuses the other.
- **GK-034** `/admit`, `/approve`, `/revise`, `/redo`, and `/propose` are refused on an issue
  labelled `type:epic`.
- **GK-035** `/park`, `/unpark`, and `/milestone` are permitted on an epic.

### Arguments

- **GK-040** `/cap` requires a positive integer; a non-numeric argument is refused.
- **GK-041** `/cap` with zero or a negative number is refused.
- **GK-042** `/milestone` and `/focus` match an open milestone by title, including by number
  prefix.
- **GK-043** An argument matching no open milestone is refused, and the refusal lists the open
  milestones.

---

## 4. Gates

A gate may refuse a command. Gates run before any write.

- **GK-050** `/approve` is refused when the issue has no milestone.
- **GK-051** The refusal asks which milestone to use; the gate never selects one itself.
- **GK-052** An empty-string milestone is treated as absent.
- **GK-053** `/approve` does not accept an inline milestone argument. `/milestone` then `/approve`
  are separate comments.
- **GK-054** `/approve` is refused when a hard blocker sits in a **later** milestone than the
  issue.
- **GK-055** A blocker in an earlier or the same milestone does not refuse.
- **GK-056** A closed blocker is ignored by every gate.
- **GK-057** A soft `Depends on:` reference is subject to the same ordering rule as a hard blocker.
- **GK-058** Every offending blocker is named in the refusal.
- **GK-059** `/milestone` is subject to the ordering gate; the milestone-presence gate does not
  apply to it.
- **GK-060** `/park` is never gated.
- **GK-062** A gate refusal never alters the milestone.

### Milestone ordering

The ordering gate exists to stop work being approved ahead of a prerequisite scheduled later. It
requires milestones to be *comparable*, which is a property of how a repository names them, not a
universal fact.

- **GK-061** The ordering strategy is configuration: `semver` (`v0.4` before `v0.16`), `date`,
  `lexical`, or `none`.
- **GK-063** Under `none`, the ordering gate does not run at all. Milestone presence (GK-050) is
  unaffected.
- **GK-064** A blocker in a milestone the strategy cannot order, or in no milestone, **does not
  refuse**. An unorderable milestone is an absence of information, not evidence of inversion.
- **GK-065** A blocker whose milestone cannot be ordered is reported on the dashboard as an
  unverifiable dependency, so the gap is visible rather than silently permissive.

> **Invariant — the ordering gate refuses only on evidence of inversion, never on absence of
> evidence.** A repository whose milestones are dates, themes, or a mix — including a standing
> milestone such as `Direct Involvement Needed` that names no version at all — must not find every
> approval blocked by a gate that cannot read its scheme. Refusing on unknown made any issue
> blocked by a human-task issue permanently unapprovable, with a refusal message pointing at
> ordering rather than at the cause.

---

## 5. Reactions and acknowledgement

Three reaction states on the command comment, all placed by the bot identity.

| Reaction | Meaning |
|---|---|
| 👀 | seen; processing |
| 👍 | processed; action taken |
| 👎 | processed; refused |

- **GK-070** 👀 is placed before any write is attempted.
- **GK-071** On success, 👀 is replaced by 👍.
- **GK-072** On refusal, 👀 is replaced by 👎.
- **GK-073** A comment already carrying 👍 or 👎 from the bot is never re-processed.
- **GK-074** The same reaction placed by any account other than the bot is not a watermark.
- **GK-075** A non-owner's comment receives no reaction at all.
- **GK-076** A comment containing no command receives no reaction.
- **GK-077** An applied command receives a short reply naming what changed and what can follow.
- **GK-078** A refusal receives a short reply explaining the refusal and stating that nothing
  changed.
- **GK-079** A refusal reply carries the gate's prose, not an internal reason code.
- **GK-080** An unreadable reaction lookup is treated as already-watermarked, so ambiguity never
  causes a double application.

---

## 6. Catch-up and `/retry`

Replaces the removed comment-replay sweep.

- **GK-090** On any `issue_comment` event, before handling the triggering comment, the gatekeeper
  processes that **same issue's** owner comments that carry a bare 👀 and no 👍 or 👎.
- **GK-091** Catch-up never reads or writes another issue.
- **GK-092** Catch-up applies commands in ascending comment order, so a later command wins.
- **GK-093** A comment with no reaction at all is not caught up — it was never seen, and the
  triggering event is not evidence about it. *(manual: covered by GK-070's ordering.)*
- **GK-094** `/retry` re-processes the issue's unfinished commands and is itself watermarked
  normally.
- **GK-095** A failure while catching up one comment does not prevent the triggering comment being
  handled.

---

## 7. Lifecycle events

- **GK-100** On `issues.closed`, every pipeline-state label is removed from the closed issue.
- **GK-101** Closing an issue triggers no action on any other issue.
- **GK-102** A merged pull request carrying a closing keyword closes its issue through GitHub,
  which raises `issues.closed`; GK-100 then applies. The gatekeeper takes no separate action on
  the merge. *(manual: verifies a GitHub platform behaviour, confirmed once in the pilot.)*
- **GK-103** A merged pull request **without** a closing keyword changes nothing. The issue keeps
  its state, including `in-progress`. A keyword-less merge is only reachable deliberately — the
  `closing-keyword` **required** check (see `SYS`) blocks any pull request lacking one unless it
  carries the `no-closing-keyword` label — so the gatekeeper treats it as intended and does not
  overrule it.
- **GK-104** An issue left `in-progress` with no open pull request is reported by the dashboard as
  a read-only flag and is never advanced automatically.
- **GK-105** A pull request closed without merging changes nothing.
- **GK-106** No scheduled job performs any write.

---

## 8. Downstream effects

- **GK-110** A command that newly adds the triage label fires the analysis routine.
- **GK-111** An idempotent re-application that leaves the triage label already present does not
  fire it.
- **GK-112** Removing the triage label does not fire it.
- **GK-113** A refused command fires nothing.
- **GK-114** The dashboard is re-rendered once after a run that changed at least one label.
- **GK-115** A run that changed no label does not re-render.
- **GK-116** `/focus` and `/cap` persist as dashboard render overrides; the issue body is never
  patched directly.
- **GK-117** A fire failure is reported but never raised, and never fails the run.
- **GK-118** The fire request never logs its URL or its secret.
- **GK-119** An unconfigured fire endpoint is a notice, not an error.

---

## 9. Architecture and configuration

- **GK-130** All GitHub access is performed through `lib/github.py`. No other gatekeeper module
  imports a network library.
- **GK-131** Parsing, gating, and planning modules are pure: given a snapshot they return a plan
  and perform no I/O.
- **GK-132** Paginated reads follow pages until short, preserve item order, and stop at a
  configured page cap.
- **GK-133** An empty or null page is an empty result, not an error.
- **GK-134** A failing sub-request degrades the snapshot rather than discarding it. An unreadable
  dependency edge is reported as unverifiable (GK-065) and does not refuse.
- **GK-135** Owner list, bot identity, milestone ordering strategy, dashboard issue number, label
  vocabulary, and the fire endpoint are read from `repo-config.yml` and validated against the
  schema.
- **GK-137** The gatekeeper belongs to the `pipeline` capability and may import from `substrate`,
  `hygiene`, `consistency`, `labels`, and `release`. No lower capability imports from it.
- **GK-136** No test performs network I/O.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| State machine | GK-001–005 | `test_state_machine.py` |
| Authority | GK-010–019 | `test_authority.py` |
| Parsing | GK-020–028 | `test_parse_commands.py` |
| Scope | GK-030–035 | `test_scope.py` |
| Arguments | GK-040–043 | `test_arguments.py` |
| Gates | GK-050–065 | `test_gates.py` |
| Reactions | GK-070–080 | `test_reactions.py` |
| Catch-up | GK-090–095 | `test_catchup.py` |
| Lifecycle | GK-100–106 | `test_lifecycle.py` |
| Downstream | GK-110–119 | `test_downstream.py` |
| Architecture | GK-130–137 | `test_architecture.py`, `test_github_api.py` |

**92 requirements, 90 `auto` and 2 `manual`.**
