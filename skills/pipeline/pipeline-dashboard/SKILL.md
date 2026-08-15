---
name: pipeline-dashboard
description: Render the pipeline dashboard from live GitHub state — the board, the ready queue, and every fault the pipeline deliberately does not repair. Use when previewing or manually refreshing the dashboard, or when working out why an issue is stuck.
allowed-tools: Bash, Read
---

# Pipeline dashboard

One issue, rendered from live state. The only scheduled job in the pipeline, and it writes to no
issue but its own body.

## Reading it

The top three lines answer the usual questions: which milestone is in focus, how many issues are
in progress against the cap, and how many things need attention. If that last number is zero the
page is a dozen lines long — **length is the signal**.

## The fault sections

Each one exists because the pipeline deliberately does *not* repair something. The reconcile sweep
was removed because auto-repair hid problems and occasionally caused them; the bargain was that
faults get reported instead. These sections are that bargain.

| Section | What happened | What to do |
| --- | --- | --- |
| Commands that did not finish | a comment has 👀 but never 👍 or 👎 — the run died | comment `/retry` |
| Work that stopped | `in-progress` with no open pull request | check whether it merged without a closing keyword |
| Approved but blocked | waiting on an unresolved blocker | nothing — it becomes eligible on its own |
| Dependencies that could not be checked | a blocker's milestone cannot be ordered | confirm the order yourself |
| Dependencies written as prose | `Blocked by #N` in a body | convert to a native relationship |
| Closed issues still carrying state | a close event was missed | close it again, or strip the label |
| Open issues outside the pipeline | never admitted, or lost its state | `/admit`, or leave it |

"Approved but blocked" is not an error. It is there so that "why is nothing being built" has a
visible answer.

## Running it

```bash
GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
  python3 .claude/skills/pipeline-dashboard/main.py
```

Fetching and rendering are separate: `fetch_state.py` reads and returns plain data,
`render_dashboard.py` turns that into Markdown and touches no client. The render is deterministic,
so two runs over unchanged state produce identical text and a diff shows real change.

Specification: `docs/spec/dashboard.md` (`DASH`), 24 requirements.
