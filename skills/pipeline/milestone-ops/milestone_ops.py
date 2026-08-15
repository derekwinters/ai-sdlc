#!/usr/bin/env python3
"""Milestone operations the GitHub MCP server does not provide.

It exposes no milestone CRUD at all, which is why milestone work in these
repositories has been done by hand or skipped. The existing implementations
covered list, close and reopen — and described themselves as "milestone CRUD",
while having neither the C nor the U. That gap is how a milestone ends up
created through the web interface without the description the pipeline reads:
a milestone that exists and is invisible to the thing meant to consume it.

Nothing here deletes a milestone. Deleting one detaches it from every issue
that carried it and cannot be undone; closing is always available and always
reversible.

Specification: docs/spec/milestones.md (`MS`).
"""

from __future__ import annotations

import re

#: Markers read out of a description. The focus milestone is matched live from
#: it, so these are data rather than prose.
FOCUS = "focus"
FROZEN = "frozen"

_MARKER = r"(?:^|(?<=[\s.]))%s\.(?:\s+|$)"


class MilestoneError(RuntimeError):
    """An operation that would lose information, or that names nothing."""


class CloseResult:
    __slots__ = ("milestone", "orphaned")

    def __init__(self, milestone, orphaned=0):
        self.milestone = milestone
        self.orphaned = orphaned


# ----------------------------------------------------------------- markers


def _has_marker(description, marker):
    return bool(re.search(_MARKER % marker, (description or ""), re.IGNORECASE))


def is_focus(description):
    return _has_marker(description, FOCUS)


def is_frozen(description):
    return _has_marker(description, FROZEN)


def set_marker(description, marker):
    """Add a marker, keeping whatever prose is already there."""
    if _has_marker(description, marker):
        return description
    rest = (description or "").strip()
    return f"{marker}. {rest}".strip()


def clear_marker(description, marker):
    """Remove a marker, keeping whatever prose is around it."""
    cleaned = re.sub(_MARKER % marker, " ", description or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


# -------------------------------------------------------------- operations


class Milestones:
    """Milestone CRUD, including the create and edit the MCP server lacks."""

    def __init__(self, api):
        self.api = api

    # ------------------------------------------------------------ reading

    def list(self, state="all"):
        """Every milestone, ordered by number so output is diffable."""
        return sorted(self.api.milestones(state=state), key=lambda m: m["number"])

    def find(self, title, state="all"):
        """Resolve by exact title, then by unique prefix. Never guesses."""
        if not title:
            return None

        candidates = self.list(state=state)
        wanted = title.strip().lower()

        for milestone in candidates:
            if milestone["title"].lower() == wanted:
                return milestone

        matches = [m for m in candidates if m["title"].lower().startswith(wanted)]
        return matches[0] if len(matches) == 1 else None

    def open_issue_count(self, title):
        return self._require(title)["open_issues"]

    def focus(self):
        """The milestone marked as the focus, or None."""
        for milestone in self.list(state="open") + self.list(state="closed"):
            if is_focus(milestone.get("description")):
                return milestone
        return None

    # ------------------------------------------------------------ writing

    def create(self, title, description=None, due_on=None):
        cleaned = (title or "").strip()
        if not cleaned:
            raise MilestoneError("a milestone needs a title")

        existing = self.find(cleaned)
        if existing and existing["title"].lower() == cleaned.lower():
            raise MilestoneError(
                f"a milestone titled {cleaned!r} already exists as "
                f"#{existing['number']}"
            )

        return self.api.create_milestone(cleaned, description=description, due_on=due_on)

    def edit(self, which, **fields):
        """Change only the fields given. Editing is not replacement.

        The first argument is named `which` rather than `title` because a
        caller renaming a milestone passes both — the one to find and the one
        to set — and two parameters named `title` cannot coexist.
        """
        milestone = self._require(which)

        new_title = fields.get("title")
        if new_title and new_title.lower() != milestone["title"].lower():
            clash = self.find(new_title)
            if clash and clash["number"] != milestone["number"]:
                raise MilestoneError(
                    f"#{clash['number']} is already titled {clash['title']!r}"
                )

        if "description" in fields:
            # Markers are data. Rewriting a description must not silently drop
            # a focus or frozen marker the caller did not mention.
            fields["description"] = self._preserve_markers(
                milestone.get("description"), fields["description"]
            )

        return self.api.update_milestone(milestone["number"], **fields)

    def close(self, title, force=False):
        milestone = self._require(title)
        if milestone["state"] == "closed":
            return CloseResult(milestone)

        remaining = milestone["open_issues"]
        if remaining and not force:
            raise MilestoneError(
                f"{milestone['title']!r} still has {remaining} open issue"
                f"{'s' if remaining != 1 else ''}. Closing it would leave them "
                f"carrying a milestone that no longer appears in any open list. "
                f"Use force to close anyway."
            )

        self.api.update_milestone(milestone["number"], state="closed")
        return CloseResult(milestone, orphaned=remaining)

    def reopen(self, title):
        milestone = self._require(title)
        if milestone["state"] == "open":
            return milestone
        return self.api.update_milestone(milestone["number"], state="open")

    def set_focus(self, title):
        """Mark one milestone as the focus, clearing the marker from any other."""
        target = self._require(title)

        for milestone in self.list():
            if milestone["number"] == target["number"]:
                continue
            if is_focus(milestone.get("description")):
                self.api.update_milestone(
                    milestone["number"],
                    description=clear_marker(milestone.get("description"), FOCUS),
                )

        return self.api.update_milestone(
            target["number"],
            description=set_marker(target.get("description"), FOCUS),
        )

    # ------------------------------------------------------------ private

    def _require(self, title):
        milestone = self.find(title)
        if milestone is None:
            raise MilestoneError(f"no milestone matches {title!r}")
        return milestone

    def _preserve_markers(self, before, after):
        for marker in (FOCUS, FROZEN):
            if _has_marker(before, marker) and not _has_marker(after, marker):
                after = set_marker(after, marker)
        return after
