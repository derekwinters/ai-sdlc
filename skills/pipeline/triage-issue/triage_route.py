#!/usr/bin/env python3
"""Where a triaged issue ends up, and what it is told.

Three outcomes, and exactly three: a plan, a question, or a failure. Every
triage run ends in one of them, which is what makes "what happened to this
issue" answerable without reading a transcript.

The constraints here exist because triage is the one place an LLM makes a
judgement. A plan with no acceptance checks is a wish; a question that
recommends an answer is a decision wearing a question mark; and an outcome that
could write the approved state would let triage put work into the build queue on
its own. All three are refused structurally rather than by instruction.

Specification: docs/spec/triage.md (`TRI`), §2–5.
"""

from __future__ import annotations


class PlanError(ValueError):
    """An outcome that would not be actionable, or would decide something."""


class Outcome:
    """A plan, a question, or a failure."""

    __slots__ = ("kind", "summary", "milestone", "checks", "specs", "spec_change",
                 "options", "reason")

    def __init__(self, kind, **fields):
        self.kind = kind
        for name in self.__slots__[1:]:
            setattr(self, name, fields.get(name))

    # ------------------------------------------------------------ builders

    @classmethod
    def plan(cls, summary, milestone, checks, specs=None, spec_change=None):
        if not (summary or "").strip():
            raise PlanError("a plan needs a plain-English summary of what is wrong or wanted")
        if not milestone:
            raise PlanError("a plan needs a proposed milestone")

        real = [c for c in (checks or []) if c and c.strip()]
        if not real:
            raise PlanError(
                "a plan needs acceptance checks; a plan nobody can verify is a wish"
            )

        return cls(
            "plan", summary=summary.strip(), milestone=milestone, checks=real,
            specs=list(specs or []), spec_change=spec_change,
        )

    @classmethod
    def question(cls, question, options):
        real = [o for o in (options or []) if o and o.strip()]
        if len(real) < 2:
            raise PlanError(
                "a question needs at least two options; one option is a decision"
            )
        return cls("question", summary=question.strip(), options=real)

    @classmethod
    def failed(cls, reason):
        return cls("failed", reason=reason)

    # ------------------------------------------------------------ rendering

    def render(self, issue):
        if self.kind == "plan":
            return self._plan_body()
        if self.kind == "question":
            return self._question_body()
        return self._failure_body()

    def _plan_body(self):
        lines = [self.summary, "", f"**Proposed milestone:** {self.milestone}", ""]
        lines += ["**Acceptance**", ""]
        lines += [f"- {check}" for check in self.checks]
        lines += [""]

        if self.specs:
            lines += ["**Specification pages affected**", ""]
            lines += [f"- `{page}`" for page in self.specs]
            if self.spec_change:
                lines += ["", f"**How the specification changes:** {self.spec_change}"]
        else:
            lines += ["**Specification:** none change."]

        lines += ["", "Your move: `/approve` · `/revise <notes>` · `/park`"]
        return "\n".join(lines)

    def _question_body(self):
        lines = [self.summary, "", "**Options**", ""]
        lines += [f"- {option}" for option in self.options]
        lines += [
            "",
            "Triage will not choose between these — it is a design decision, "
            "so it is yours to decide.",
            "",
            "Answer in a comment, then `/revise <notes>` to re-plan with the answer.",
        ]
        return "\n".join(lines)

    def _failure_body(self):
        return (
            f"Triage could not produce a plan: {self.reason}\n\n"
            f"The issue stays in triage rather than being routed somewhere "
            f"convenient. `/park` it, or `/revise <notes>` with more detail."
        )


class Routed:
    __slots__ = ("issue", "state", "outcome")

    def __init__(self, issue, state, outcome):
        self.issue = issue
        self.state = state
        self.outcome = outcome


#: Where each outcome sends the issue. Note what is absent: no outcome maps to
#: `approved` or `building`. Triage proposes; it never queues work.
DESTINATION = {"plan": "pending_approval", "question": "clarification"}


def route(api, issue, outcome, labels):
    """Apply the outcome: one state label, one comment."""
    state = DESTINATION.get(outcome.kind)

    if state is not None:
        current = [label["name"] for label in api.issue(issue).get("labels") or []]
        state_labels = set(labels.values())
        kept = [name for name in current if name not in state_labels]
        api.set_labels(issue, kept + [labels[state]])

    api.comment(issue, outcome.render(issue))
    return Routed(issue, state, outcome)
