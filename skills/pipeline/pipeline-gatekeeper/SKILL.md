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

## Configuration

From `.claude/repo-config.yml`: `owners`, `bot.login`, `dashboard_issue`, `milestone_ordering`,
and the `labels` vocabulary. See `docs/spec/configuration.md`.

Specification: `docs/spec/gatekeeper.md` (`GK`), 92 requirements.
