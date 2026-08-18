#!/usr/bin/env python3
"""One comment event, end to end.

The stages are each pure and tested alone; this is the only place they are
wired together, and the only place that writes. The order matters and is the
whole point:

    authority → watermark(seen) → parse → scope → arguments → gates
              → apply labels → watermark(acted/refused) → reply → fire

`seen` is placed before anything is written, so a run that dies leaves a bare
👀 — the fault signal catch-up consumes. Authority comes first so a stranger's
comment produces no trace at all.

Specification: docs/spec/gatekeeper.md (`GK`).
"""

from __future__ import annotations

from acknowledge import acknowledge
from apply_actions import final_state, plan_labels
from arguments import check_arguments
from authority import Authority
from catchup import unfinished_comments
from downstream import (NOT_TRIAGE, FireResult, fires_triage,
                        record_started, should_rerender)
from refresh import refresh_quietly
from gates import run_gates
from lib.github import GitHubError
from parse_commands import parse
from reactions import Watermark
from scope import Subject, check_scope


class Settings:
    """Everything the run needs from configuration."""

    __slots__ = (
        "owners",
        "bot_login",
        "labels",
        "dashboard_issue",
        "milestone_ordering",
        "fire",
    )

    def __init__(
        self,
        owners,
        bot_login,
        labels,
        dashboard_issue=None,
        milestone_ordering="semver",
        fire=None,
    ):
        self.owners = list(owners)
        self.bot_login = bot_login
        self.labels = dict(labels)
        self.dashboard_issue = dashboard_issue
        self.milestone_ordering = milestone_ordering
        self.fire = fire

    @classmethod
    def from_config(cls, config, fire=None):
        return cls(
            owners=config.owners,
            bot_login=config.bot.login,
            labels=config.labels,
            dashboard_issue=config.dashboard_issue,
            milestone_ordering=config.milestone_ordering,
            fire=fire,
        )


class Result:
    __slots__ = ("applied", "refused", "reply", "rerender", "overrides",
                 "unverifiable", "fired")

    def __init__(self, applied=(), refused=(), reply=None,
                 rerender=False, overrides=None, unverifiable=(),
                 fired=NOT_TRIAGE):
        self.applied = list(applied)
        self.refused = list(refused)
        self.reply = reply
        self.rerender = rerender
        self.overrides = dict(overrides or {})
        self.unverifiable = list(unverifiable)
        self.fired = fired

    def __repr__(self):
        return f"<Result applied={len(self.applied)} refused={len(self.refused)}>"


def handle_comment(api, event, settings):
    """Handle one `issue_comment` event."""
    comment = event.get("comment") or {}
    issue_number = (event.get("issue") or {}).get("number")
    comment_id = comment.get("id")

    authority = Authority(settings.owners, settings.bot_login)
    if not authority.may_command(dict(comment, issue=event.get("issue") or {})):
        # No reaction, no reply, no write: a stranger must not be able to make
        # the bot act, and must not learn whether the command would have worked.
        return Result()

    watermark = Watermark(api, settings.bot_login)
    if watermark.is_finished(comment_id):
        return Result()

    # Catch up this issue's stalled commands first, so an older instruction is
    # applied before the one that triggered this run.
    for stalled in unfinished_comments(api, issue_number, watermark, settings.owners):
        if stalled.get("id") != comment_id:
            _apply(api, issue_number, stalled, settings, watermark)

    return _apply(api, issue_number, comment, settings, watermark)


def _apply(api, issue_number, comment, settings, watermark):
    watermark.seen(comment["id"])

    issue = api.issue(issue_number)
    before = [label["name"] for label in issue.get("labels") or []]

    parsed = parse(comment.get("body"))
    scoped = check_scope(
        parsed.actions,
        Subject.from_issue(issue, settings.dashboard_issue),
        skips=parsed.skips,
    )

    milestones = _safe(api.milestones, default=[])
    resolved = check_arguments(scoped.actions, milestones, skips=scoped.skips)

    blockers = _blockers(api, issue_number)
    gated = run_gates(
        resolved.actions,
        issue=issue,
        blockers=blockers,
        milestones=milestones,
        ordering=settings.milestone_ordering,
        skips=resolved.skips,
    )

    after = plan_labels(before, gated.actions, settings.labels)
    overrides = _overrides(gated.actions)
    milestone_write = _milestone_write(gated.actions)

    if should_rerender(before, after):
        api.set_labels(issue_number, after)
    if milestone_write is not None:
        api.set_milestone(issue_number, milestone_write)

    if gated.actions:
        watermark.acted(comment["id"])
    elif gated.skips:
        watermark.refused(comment["id"])
    else:
        watermark.acted(comment["id"])

    reply = acknowledge(
        gated.actions, gated.skips, state=final_state(after, settings.labels)
    )
    if reply:
        api.comment(issue_number, reply)

    rerender = should_rerender(before, after) or bool(overrides)
    if rerender:
        # The render *is* how `/focus` and `/cap` persist: the board's body is
        # their only store. Returning the value without rendering leaves it in
        # memory until this process ends (#105).
        refresh_quietly(api, settings, overrides)

    fired = _fire(api, issue_number, before, after, settings)

    return Result(
        applied=gated.actions,
        refused=gated.skips,
        reply=reply,
        rerender=rerender,
        overrides=overrides,
        unverifiable=gated.unverifiable,
        fired=fired,
    )


def _fire(api, issue_number, before, after, settings):
    """Poke the analysis routine when this run put the issue into triage.

    Last, because the label move is the gatekeeper's actual job and a routine
    that cannot be reached must not cost it. The transition is what fires, not
    the destination: re-applying `/admit` to an issue already in triage would
    otherwise make a repeated command a way to queue work repeatedly (#111).

    The label event cannot cover this. The gatekeeper writes with
    `GITHUB_TOKEN`, and GitHub starts no workflow run from an event that token
    authored, so the `labeled` event this very write emits reaches nothing
    (#126). That suppression is also what keeps the two paths from both firing
    for one `/admit` — see `GK-122`.
    """
    if not fires_triage(before, after, (settings.labels or {}).get("triage_queued")):
        return NOT_TRIAGE
    if not settings.fire:
        return FireResult(attempted=False, detail="no analysis routine configured")
    result = settings.fire.send(issue_number, api.repository)
    # Whoever fires records that a session started, by moving queued -> running
    # (`GK-138`). Exactly one state, the one only this component can know.
    record_started(api, issue_number, result, settings.labels)
    return result


def _overrides(actions):
    """`focus` and `cap` persist as dashboard render overrides.

    Never a patch of the dashboard issue's body: the body is rendered from
    live state, so editing it would be overwritten on the next render.
    """
    overrides = {}
    for action in actions:
        if action.command == "focus":
            overrides["focus"] = action.argument
        elif action.command == "cap":
            overrides["cap"] = action.value
    return overrides


def _milestone_write(actions):
    for action in actions:
        if action.command == "milestone":
            return action.value
    return None


def _blockers(api, issue_number):
    edges = _safe(lambda: api.blocked_by(issue_number), default=[])
    resolved = []
    for edge in edges:
        number = edge.get("number")
        found = _safe(lambda n=number: api.issue(n), default=None)
        resolved.append(found if found is not None else dict(edge, milestone=None))
    return resolved


def _safe(call, default):
    """A failing supplementary read degrades the snapshot; it never ends the run."""
    try:
        return call()
    except GitHubError:
        return default
