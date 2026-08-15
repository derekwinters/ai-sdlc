#!/usr/bin/env python3
"""The rules that refuse a command before anything is written.

Two gates.

Milestone presence: an issue cannot be approved into the build queue without a
milestone, because the builder selects work by milestone and an unscheduled
issue would sit approved and never be picked up. The gate asks which milestone;
it never picks one, because choosing where someone's work is scheduled is not
a decision to infer from silence.

Ordering: an issue must not be approved ahead of something it depends on. This
gate has a history worth knowing. It used to refuse when a blocker's milestone
could not be *ordered* — treating "I cannot compare these" as "this is
inverted". Against a standing milestone that names no version, such as
`Direct Involvement Needed`, that made any issue blocked by a human-task issue
permanently unapprovable, and said so with a message about ordering rather than
about the cause.

So: refuse only on evidence of inversion, never on absence of evidence. A
blocker whose milestone cannot be compared is reported as an unverifiable
dependency instead, which keeps the gap visible rather than silently permissive.

Pure: actions and a snapshot in, actions and refusals out.

Specification: docs/spec/gatekeeper.md (`GK`), §4.
"""

from __future__ import annotations

from ordering import UNORDERED, ordering_for
from parse_commands import Skip

#: Commands the ordering gate applies to: both change where work is scheduled.
ORDERED_COMMANDS = ("approve", "milestone")

#: Commands requiring the issue to have a milestone already.
NEEDS_MILESTONE = ("approve",)


class Verdict:
    """Whether a gate refused, and the prose explaining it."""

    __slots__ = ("refused", "reason", "detail")

    def __init__(self, refused, reason=None, detail=""):
        self.refused = refused
        self.reason = reason if refused else None
        self.detail = detail if refused else ""

    def __repr__(self):
        return f"<Verdict refused={self.refused} reason={self.reason!r}>"


class Gated:
    """What survived the gates, what was refused, and what could not be checked."""

    __slots__ = ("actions", "skips", "unverifiable")

    def __init__(self, actions, skips, unverifiable):
        self.actions = actions
        self.skips = skips
        self.unverifiable = unverifiable


def run_gates(actions, issue, blockers, milestones, ordering="semver", skips=None):
    """Apply every gate, refusing what must be refused and nothing more."""
    rank = ordering_for(ordering)
    kept, refused = [], list(skips or [])

    # Under `none` the ordering gate does not run, so there is nothing for a
    # dependency to be unverifiable *about*. Reporting every blocker would be
    # noise, and a report nobody can act on trains people to ignore the rest.
    unverifiable = [] if ordering == "none" else _unverifiable(blockers, rank)

    for action in actions:
        verdict = _judge(action, issue, blockers, rank)
        if verdict.refused:
            skip = Skip(action.command, verdict.reason, line=action.line)
            skip.detail = verdict.detail
            refused.append(skip)
        else:
            kept.append(action)

    return Gated(kept, refused, unverifiable)


def _judge(action, issue, blockers, rank):
    if action.command == "approve" and action.argument:
        return Verdict(
            True,
            "approve-takes-no-argument",
            "`/approve` does not take a milestone. Set it first with "
            "`/milestone <title>`, then `/approve` in a separate comment.",
        )

    if action.command in NEEDS_MILESTONE and not _milestone_title(issue):
        return Verdict(
            True,
            "no-milestone",
            "This issue has no milestone, so approving it would queue work the "
            "builder cannot schedule. Which milestone should it go in? "
            "Reply `/milestone <title>`, then `/approve`.",
        )

    if action.command in ORDERED_COMMANDS:
        return _ordering_verdict(action, issue, blockers, rank)

    return Verdict(False)


def _ordering_verdict(action, issue, blockers, rank):
    subject_rank = rank(_target_title(action, issue))
    if subject_rank is UNORDERED:
        # Nothing to compare against. Absence of evidence.
        return Verdict(False)

    offenders = []
    for blocker in blockers:
        if _is_resolved(blocker):
            continue
        blocker_rank = rank(_milestone_title(blocker))
        if blocker_rank is UNORDERED:
            continue  # unverifiable, reported separately — never a refusal
        if blocker_rank > subject_rank:
            offenders.append(blocker)

    if not offenders:
        return Verdict(False)

    named = ", ".join(
        f"#{b['number']} ({_milestone_title(b)})" for b in offenders
    )
    return Verdict(
        True,
        "blocker-inversion",
        f"This is blocked by work scheduled later: {named}. Move the blocker "
        f"earlier, or schedule this issue after it.",
    )


def _unverifiable(blockers, rank):
    """Open blockers whose milestone this strategy cannot compare."""
    return [
        blocker
        for blocker in blockers
        if not _is_resolved(blocker) and rank(_milestone_title(blocker)) is UNORDERED
    ]


def _milestone_title(item):
    milestone = (item or {}).get("milestone") or {}
    return milestone.get("title") or ""


def _target_title(action, issue):
    """Where the issue will be after this command, not where it is now."""
    if action.command == "milestone" and action.milestone:
        return action.milestone.get("title") or ""
    return _milestone_title(issue)


def _is_resolved(blocker):
    return blocker.get("state") == "closed" or bool(blocker.get("merged"))
