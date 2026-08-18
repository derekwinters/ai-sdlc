---
name: pipeline-gatekeeper
description: Translate the repository owner's issue comments into pipeline label moves, refusing commands that would break a pipeline rule. Use when running the gatekeeper on demand, debugging why a command did or did not apply, or wiring the gatekeeper workflows into a repository.
allowed-tools: Bash, Read
---

# Pipeline gatekeeper

The only component permitted to move an issue through the pipeline state machine. It reads the
owner's comments, applies the commands it recognises, and refuses the ones that would break a rule
— always saying which, and always leaving a mark on the comment so the same command cannot apply
twice.

## The commands

| Command | Argument | Where | Effect |
| --- | --- | --- | --- |
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

A command must start its own line. One inside a fenced code block is ignored, and so is a
`/word` mid-line — otherwise a URL would issue commands.

## Reading the marks

The gatekeeper reacts to every comment it considers:

| Reaction | Meaning |
| --- | --- |
| 👀 | seen, being processed |
| 👍 | applied |
| 👎 | refused — read the reply |

**A 👀 that never became 👍 or 👎 means the run died mid-flight.** That is the one thing a lingering
👀 can mean, which is why there are three states rather than two. Comment `/retry` on the issue, or
wait for your next comment there — catch-up processes stalled commands on the same issue first.

## When a command does nothing

- **No reaction at all** — you are not in `owners`, or the comment is on a pull request.
- **👎 with a reply** — a gate refused it; the reply says which and states that nothing changed.
- **A "not a command" reply** — a typo. The reply names the closest real command.

## Approving

`/approve` needs the issue to have a milestone, and does not take one inline:

```
/milestone v0.4
```
```
/approve
```

Two comments, deliberately — approving and scheduling are separate decisions.

## The sweep

Firing the analysis routine is a poke, and a poke can be lost. When one is, the issue sits in
triage with no analysis and nothing that will ever look at it again — the failure that stranded
eight issues in `connor-multiplying-frogs` overnight. `gatekeeper-sweep.yml` runs hourly, finds
issues in that state, and pokes them once more.

It pokes the routine directly rather than removing and re-applying the triage label. Both would
start a session, but a label round-trip also emits `labeled`, which the label handler answers with
a second poke — one intent, two sessions.

**A scheduled job that starts sessions spends the owner's usage limits while nobody is watching**,
so what it may spend is bounded twice, and the two bounds fail differently:

| Bound | Set by | What it stops |
|---|---|---|
| `sweep.ceiling` (default 20) | configuration | one faulty run turning a whole board into sessions |
| the attempt markers | labels on the issue | one broken issue being retried for as long as it exists |

The ceiling is a circuit breaker, not a throttle: it sits well above what an ordinary board strands
at once, so reaching it means something is wrong rather than busy — and the run says what it
skipped. `ceiling: 0` turns the sweep off without a code change.

**The markers are how an issue's retries are bounded.** Whoever fires the routine records that it
did, as a label, and the record only ever advances:

| Marker | Meaning |
|---|---|
| *(none)* | in triage, no poke has gone out |
| `ai-triage-pending` | a poke went out; the routine has not answered |
| `ai-triage-stalled` | poked twice, still nothing — terminal, and shown on the dashboard |

A marker is not a pipeline state: an issue carrying one is still in triage. They are cleared when
the issue leaves triage, is closed, or re-enters triage — a fresh `/admit` is a new episode and
deserves a fresh budget.

This replaced a give-up *duration*, which did not work. A duration is measured against a clock, and
every clock available here — last update, last comment — is reset by ordinary activity, so a
passing comment resurrected issues that had already been given up on. Marker state has nothing to
reset.

**Requeueing happens only on the scheduled path.** The event path may report but never requeue: a
merge or a label change can briefly make a healthy issue look stranded — a just-merged issue before
GitHub finishes closing it, a just-set label before the analysis comment is visible — and
requeueing in that window is what turns two states into a loop that fires a session on every flip.
A genuine stall has no triggering event, so waiting for the schedule loses nothing.

## Configuration

From `.claude/repo-config.yml`: `owners`, `bot.login`, `dashboard_issue`, `milestone_ordering`,
the `labels` vocabulary, and `sweep`. See `docs/spec/configuration.md`.

Specification: `docs/spec/gatekeeper.md` (`GK`), 101 requirements.
