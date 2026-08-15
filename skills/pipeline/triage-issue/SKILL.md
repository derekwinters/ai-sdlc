---
name: triage-issue
description: Turn an admitted issue into a plan the owner can approve, or a question the owner must answer. Use when triaging a single issue, or when working out why an issue is sitting in triage rather than moving on.
allowed-tools: Bash, Read, Grep, Glob
---

# Triage an issue

Triage is the one place in the pipeline where judgement is required rather than a rule followed.
Everything around it is pinned down so the judgement is confined to the part that needs it.

## Three outcomes, and only three

| Outcome | Goes to | When |
| --- | --- | --- |
| **Plan** | `pending-approval` | the specification says what should happen, and you can say how to verify it |
| **Question** | `needs-clarification` | something is genuinely undecided |
| **Failure** | stays in `ai-triage` | you cannot act on it at all |

There is no fourth option, and in particular no outcome that queues work. **Triage proposes; the
owner approves.**

## Never invent a design decision

Where the specification is silent about what something should do, **ask**. A plan that quietly
decides a question nobody asked is worse than no plan, because it looks like an answer and gets
approved as one.

A question must offer at least two options and must not recommend one — a question with a
recommendation is a decision wearing a question mark. Enforced: a one-option question is refused.

## What a plan must contain

- A **plain-English summary** first, before any file or class name. Someone should be able to tell
  what is wrong from the first two sentences.
- A **proposed milestone**.
- **Acceptance checks** — refused without them. A plan nobody can verify is a wish.
- The **specification pages** it affects, or an explicit statement that none change.
- If it changes what a page *says*, **how it changes**: what it used to say, what it now says, why.

## Selection

Eligible issues carry the triage label and are not closed, parked, epics, or already carrying a
plan or a question. Selection is by issue number and **capped** — and when the cap truncates a run,
it says so. A silent cap makes a partial run look like a complete one.

Eligibility reads labels only, never bodies: otherwise an issue could talk its way out of the
queue.

Specification: `docs/spec/triage.md` (`TRI`), 26 requirements.
