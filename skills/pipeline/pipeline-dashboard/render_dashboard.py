#!/usr/bin/env python3
"""Render the pipeline dashboard from a plain-data snapshot.

Pure: state in, Markdown out. It imports no client and performs no I/O, which
is what makes the page diffable and the tests exhaustive.

Half of this file is the fault report, and that is the point. The reconcile
sweep was removed because auto-repair hid problems and occasionally caused
them; the bargain was that faults would be reported instead of fixed. Every
entry in FAULTS is the other half of a decision made somewhere else — a place
the pipeline deliberately does nothing and promises to tell you.

A page with no faults says so in one line. If this is long, something is wrong,
and that should be legible from the length alone.

Specification: docs/spec/dashboard.md (`DASH`).
"""

from __future__ import annotations

#: Each fault: a heading, and a function turning one entry into a bullet.
#: Keyed in render order — worst first, so the top of the page is the part
#: most likely to need action.
FAULTS = {
    "stalled_command": (
        "Commands that did not finish",
        lambda e: (
            f"- **#{e['issue']}** — a command was seen but never applied or refused "
            f"(comment `{e.get('comment')}`). The run died mid-flight; comment "
            f"`/retry` on the issue."
        ),
    ),
    "stalled_work": (
        "Work that stopped",
        lambda e: (
            f"- **#{e['issue']}** — in progress with no open pull request. Either it "
            f"merged without a closing keyword, or the builder never got there."
        ),
    ),
    "blocked_but_approved": (
        "Approved but blocked",
        lambda e: (
            f"- **#{e['issue']}** — approved, waiting on "
            f"{', '.join('#%s' % b for b in e.get('blockers', []))}. Not an error; "
            f"it will become eligible on its own."
        ),
    ),
    "unverifiable_dependency": (
        "Dependencies that could not be checked",
        lambda e: (
            f"- **#{e['issue']}** — blocked by **#{e['blocker']}** in "
            f"*{e.get('milestone') or 'no milestone'}*, which the ordering strategy "
            f"cannot compare. The ordering gate let it through rather than refusing "
            f"on something it could not verify."
        ),
    ),
    "prose_dependency": (
        "Dependencies written as prose",
        lambda e: (
            f"- **#{e['issue']}** — says it is blocked by "
            f"{', '.join('#%s' % n for n in e.get('numbers', []))} in its body. The "
            f"queue cannot see that, so it will be built anyway. Convert it to a "
            f"native relationship."
        ),
    ),
    "stale_state": (
        "Closed issues still carrying state",
        lambda e: (
            f"- **#{e['issue']}** — closed but still labelled "
            f"{', '.join('`%s`' % l for l in e.get('labels', []))}. A close event was "
            f"missed."
        ),
    ),
    "untracked": (
        "Open issues outside the pipeline",
        lambda e: f"- **#{e['issue']}** — open with no pipeline state. Never admitted, or lost it.",
    ),
}


def render(state):
    """The whole page, as Markdown."""
    faults = {kind: list(entries) for kind, entries in (state.get("faults") or {}).items()}
    total = sum(len(entries) for entries in faults.values())

    lines = ["# Pipeline", ""]
    lines += _summary(state, total)
    lines += _faults(faults)
    lines += _issues(state)

    return "\n".join(lines).rstrip() + "\n"


def _summary(state, total):
    focus = state.get("focus")
    if focus:
        headline = (
            f"**Focus:** {focus['title']} — {focus.get('open', 0)} open, "
            f"{focus.get('closed', 0)} closed."
        )
    else:
        headline = "**Focus:** no focus milestone is set."

    cap = state.get("cap")
    building = sum(
        1 for i in state.get("issues") or []
        if i.get("state_label") == (state.get("labels") or {}).get("building")
    )
    capacity = (
        f"**In progress:** {building} of {cap}." if cap
        else f"**In progress:** {building} (no cap set)."
    )

    if total:
        attention = f"**Needs attention:** {total}."
    else:
        attention = "**Needs attention:** nothing needs attention."

    return [headline, "", capacity, "", attention, ""]


def _faults(faults):
    lines = []
    for kind, (heading, bullet) in FAULTS.items():
        entries = faults.get(kind) or []
        if not entries:
            continue  # an empty section is noise; a short page means things are well
        lines += [f"## {heading}", ""]
        lines += [bullet(entry) for entry in sorted(entries, key=_by_issue)]
        lines += [""]
    return lines


def _issues(state):
    issues = sorted(state.get("issues") or [], key=lambda i: i["number"])
    if not issues:
        return []

    labels = state.get("labels") or {}
    order = [labels[name] for name in
             ("triage", "pending_approval", "clarification", "approved", "building", "parked")
             if name in labels]

    lines = ["## Board", ""]
    for label in order:
        in_state = [i for i in issues if i.get("state_label") == label]
        if not in_state:
            continue
        lines += [f"### {label}", ""]
        for issue in in_state:
            lines.append(_issue_line(issue, state))
        lines.append("")
    return lines


def _issue_line(issue, state):
    parts = [f"- **#{issue['number']}** {issue.get('title', '')}"]

    milestone = issue.get("milestone")
    focus = (state.get("focus") or {}).get("title")
    if milestone and milestone != focus:
        # Worth showing: an issue parked in another milestone is still stuck,
        # and its milestone is why it is not in the focus list.
        parts.append(f"*{milestone}*")

    blockers = issue.get("blockers") or []
    if blockers:
        parts.append("blocked by " + ", ".join(f"#{b}" for b in blockers))

    return " — ".join(parts)


def _by_issue(entry):
    return entry.get("issue", 0)
