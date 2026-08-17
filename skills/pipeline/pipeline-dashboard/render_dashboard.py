#!/usr/bin/env python3
"""Render the pipeline dashboard from a plain-data snapshot.

Pure: state in, Markdown out. It imports no client and performs no I/O, which
is what makes the page diffable and the tests exhaustive.

The page is two charts, five collapsible sections, and then the fault report.
The fault report is the other half of a bargain made elsewhere: the reconcile
sweep was removed because auto-repair hid problems and occasionally caused
them, and the trade was that faults would be *reported* instead of fixed. A
page with nothing wrong carries no fault report at all — the charts and the
five sections are a fixed skeleton, so it is the presence of headings below
them, not the page's length, that tells you something needs attention.

Specification: docs/spec/dashboard.md (`DASH`).
"""

from __future__ import annotations

import json
import re

from lib.config import MARKERS

#: Focus buckets, in render order — Unplanned first, so the chart reads as a
#: flow downward towards Done.
BUCKETS = ("Unplanned", "In planning", "Ready", "Done")

#: Sections, in render order: (heading, role names whose issues belong here).
#: `None` means "every state no other section claims", which is how
#: waiting-for-triage catches both `ai-triage` and an issue carrying no state.
SECTIONS = (
    ("Ready for work", ("approved", "building")),
    ("Pending approval", ("pending_approval",)),
    ("Needs clarification", ("clarification",)),
    ("Waiting for triage", None),
    ("Parked", ("parked",)),
)

#: Every state a section claims by name. Waiting-for-triage is the complement.
CLAIMED = ("approved", "building", "pending_approval", "clarification", "parked")

#: A milestone naming a version, for ordering the first chart.
VERSION = re.compile(r"^v(\d+)\.(\d+)(?:\.(\d+))?(?![\d.])")

#: Chart geometry. Height is derived rather than fixed: the same chart has to
#: stay compact with three milestones and legible with twelve.
CHART_WIDTH = 700
ROW_HEIGHT = 30
CHART_PADDING = 40
MIN_HEIGHT = 180

#: Each fault: a heading, and a function turning one entry into a bullet.
#: Keyed in render order — worst first.
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
    "stalled_triage": (
        "Triage that never answered",
        lambda e: (
            f"- **#{e['issue']}** — poked twice and the analysis routine never "
            f"answered. It will not be poked again; this one needs a human."
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
}


def render(state):
    """The whole page, as Markdown."""
    faults = {kind: list(entries) for kind, entries in (state.get("faults") or {}).items()}
    total = sum(len(entries) for entries in faults.values())

    lines = ["# Pipeline", ""]
    lines += _markers(state)
    lines += _summary(state, total)
    lines += _milestone_chart(state)
    lines += _focus_chart(state)
    lines += _sections(state)
    lines += _faults(faults)

    return "\n".join(lines).rstrip() + "\n"


# ------------------------------------------------------------------ markers


def _markers(state):
    """The focus and cap, re-emitted as HTML comments.

    This is the store, not decoration. The renderer writes back the marker it
    read, which is the whole reason a `/focus` survives from the gatekeeper's
    workflow run into the dashboard's separate one — there is nowhere else the
    value is kept.
    """
    lines = []
    focus = (state.get("focus") or {}).get("title")
    if focus:
        lines.append(f"<!-- pipeline-focus: {focus} -->")
    cap = state.get("cap")
    if cap is not None:
        lines.append(f"<!-- pipeline-cap: {cap} -->")
    return lines + [""] if lines else []


def _summary(state, total):
    focus = state.get("focus")
    headline = (
        f"**Focus:** {focus['title']}." if focus
        else "**Focus:** no milestone set."
    )

    cap = state.get("cap")
    building = sum(
        1 for i in _open(state)
        if i.get("state_label") == (state.get("labels") or {}).get("building")
    )
    capacity = (
        f"**In progress:** {building} of {cap}." if cap
        else f"**In progress:** {building} (no cap set)."
    )

    attention = (
        f"**Needs attention:** {total}." if total
        else "**Needs attention:** nothing needs attention."
    )

    return [headline, "", capacity, "", attention, ""]


# ------------------------------------------------------------------- charts


def _chart(title, labels, values, axis):
    """One horizontal, single-series bar chart.

    Horizontal is what lets a label render in full: mermaid neither wraps nor
    rotates axis labels, and on a vertical chart a long milestone title prints
    straight through its neighbour. Single-series is not a simplification —
    mermaid draws several `bar` series overlaid from zero rather than stacked,
    so a second series would hide the first rather than sit on top of it.
    """
    top = max([*values, 1])
    height = max(MIN_HEIGHT, CHART_PADDING + ROW_HEIGHT * len(labels))
    quoted = ", ".join(f'"{_escape(label)}"' for label in labels)

    # Built with json rather than `%`-formatting or an f-string: mermaid needs
    # the directive's percent signs doubled, and `"...%%..." % (...)` collapses
    # them to one, producing a directive mermaid ignores. That failed silently
    # — the chart rendered at default size — and no unit test caught it.
    config = json.dumps({"xyChart": {"width": CHART_WIDTH, "height": height}})

    return [
        "```mermaid",
        "%%{init: " + config + "}%%",
        "xychart-beta horizontal",
        f'    title "{_escape(title)}"',
        f"    x-axis [{quoted}]",
        f'    y-axis "{_escape(axis)}" 0 --> {top}',
        f"    bar [{', '.join(str(v) for v in values)}]",
        "```",
        "",
    ]


def _escape(text):
    """A quote in a title would end the label early and break the syntax."""
    return str(text).replace('"', "'")


def _milestone_chart(state):
    milestones = _ordered(state.get("milestones") or [])
    if not milestones:
        return []
    return _chart(
        "Open issues by milestone",
        [m["title"] for m in milestones],
        [m.get("open", 0) for m in milestones],
        "Open issues",
    )


def _ordered(milestones):
    """Version milestones in version order, everything else after them.

    The API returns creation order, which puts a v0.5 created late after a
    v0.12 created early. A milestone naming no version — a standing bucket for
    work only a person can do — sorts last rather than being interleaved by
    its title.
    """
    def key(milestone):
        found = VERSION.match(milestone.get("title", ""))
        if not found:
            return (1, (), milestone.get("title", ""))
        return (0, tuple(int(p or 0) for p in found.groups()), "")

    return sorted(milestones, key=key)


def _focus_chart(state):
    focus = state.get("focus")
    if not focus:
        # A sentence rather than an empty chart: an empty chart looks exactly
        # like a milestone whose work is finished.
        return ["**Focus milestone:** no milestone set.", ""]

    counts = {name: 0 for name in BUCKETS}
    for issue in state.get("issues") or []:
        if issue.get("milestone") != focus.get("title"):
            continue
        bucket = _bucket(issue, state)
        if bucket is not None:
            counts[bucket] += 1

    return _chart(
        f"Focus: {focus['title']}",
        list(BUCKETS),
        [counts[name] for name in BUCKETS],
        "Issues",
    )


def _bucket(issue, state):
    """The chart bucket for one issue, or None to leave it out entirely.

    Parked is the only `None`. Work deliberately set aside is not work waiting
    to be planned, and counting it as Unplanned put the same issue in two
    places in two different senses — it already has its own section.
    """
    if issue.get("closed"):
        return "Done"
    labels = state.get("labels") or {}
    label = issue.get("state_label")
    if label == labels.get("parked"):
        return None
    if label in (labels.get("approved"), labels.get("building")):
        return "Ready"
    if label in (labels.get("triage"), labels.get("pending_approval"),
                 labels.get("clarification")):
        return "In planning"
    # Untracked lands here: nobody has decided about it, which is exactly
    # what Unplanned means.
    return "Unplanned"


# ----------------------------------------------------------------- sections


def _sections(state):
    labels = state.get("labels") or {}
    claimed = {labels[role] for role in CLAIMED if role in labels}

    lines = []
    for heading, roles in SECTIONS:
        if roles is None:
            rows = [i for i in _open(state) if i.get("state_label") not in claimed]
        else:
            wanted = {labels[role] for role in roles if role in labels}
            rows = [i for i in _open(state) if i.get("state_label") in wanted]
        lines += _section(state, heading, rows, status=(heading == "Ready for work"))
    return lines


def _section(state, heading, rows, status):
    """One collapsible section, always rendered.

    Empty sections stay: a board whose shape is constant makes a missing
    section unambiguously a defect, where a board that drops empty sections
    makes it indistinguishable from an empty queue.

    The blank lines around the table are load-bearing — without them GitHub
    renders the table as literal text inside `<details>`.
    """
    columns = ["Issue", "Title", "Milestone", "Blocked by"]
    if status:
        columns.append("Status")

    table = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for issue in sorted(rows, key=lambda i: i["number"]):
        table.append(_row(state, issue, status))

    return [
        "<details>",
        f"<summary><b>{heading}</b> — {len(rows)}</summary>",
        "",
        *table,
        "",
        "</details>",
        "",
    ]


def _row(state, issue, status):
    repository = state.get("repository", "")
    cells = [
        _issue_link(repository, issue["number"]),
        _cell(issue.get("title", "")) + _marker_note(issue),
        _milestone_link(repository, issue),
        _blocker_links(repository, issue),
    ]
    if status:
        cells.append(issue.get("state_label") or "-")
    return "| " + " | ".join(cells) + " |"


def _marker_note(issue):
    """What to append to a title when triage has stopped retrying (`DASH-029`).

    Annotated rather than moved out of the section: the issue genuinely *is*
    waiting for triage, so removing it would make the section's count wrong.
    Leaving it unmarked is the other failure — a section that lists a dead
    issue beside live ones reports it as ordinary waiting work.

    Only the terminal marker is shown. `pending` is transient bookkeeping that
    most issues carry for a few minutes, and a board that annotates the normal
    case teaches its reader to skip the annotation.
    """
    if issue.get("marker") == MARKERS["triage_stalled"]:
        return " — **triage stalled**"
    return ""


def _cell(text):
    """A pipe would end the table cell early."""
    return str(text).replace("|", "\\|")


def _issue_link(repository, number):
    return f"[#{number}](https://github.com/{repository}/issues/{number})"


def _milestone_link(repository, issue):
    """Linked by name, targeted by number.

    `v0.5` tells a reader which milestone this is; `#13` tells them nothing,
    and the link goes to the same place either way.
    """
    number = issue.get("milestone_number")
    if not number:
        return "-"
    name = _cell(issue.get("milestone") or f"#{number}")
    return f"[{name}](https://github.com/{repository}/milestone/{number})"


def _blocker_links(repository, issue):
    blockers = issue.get("blockers") or []
    if not blockers:
        return "-"
    return ", ".join(_issue_link(repository, b) for b in blockers)


def _open(state):
    """Issues that are still open.

    Closed issues are in the snapshot because the Done bucket is closed issues
    by definition, but they belong in no section.
    """
    return [i for i in (state.get("issues") or []) if not i.get("closed")]


# ------------------------------------------------------------------- faults


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


def _by_issue(entry):
    return entry.get("issue", 0)
