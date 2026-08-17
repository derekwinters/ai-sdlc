#!/usr/bin/env python3
"""Work out an issue's labels after a command.

An issue occupies exactly one pipeline state, so a state change *replaces*
rather than adds. Everything else — `area:*`, `type:*`, `skip-docs` — is left
alone, because those carry the triage decision and a state change that dropped
them would discard it.

Three states are never written here. `pending-approval` and
`needs-clarification` are entered by analysis, and `in-progress` by the
builder. The gatekeeper reads them and moves issues *out* of them; writing one
would let it manufacture a state implying work nobody did.

Pure: current labels and actions in, new labels out. No I/O.

Specification: docs/spec/gatekeeper.md (`GK`), §1.
"""

from __future__ import annotations

#: Where each command leaves the issue, by state name. Commands absent from
#: this map change no labels at all — `/milestone`, `/focus`, `/cap`, `/retry`.
MOVES = {
    "admit": "triage",
    "propose": "triage",
    "revise": "triage",
    "unpark": "triage",
    "approve": "approved",
    "redo": "approved",
    "park": "parked",
}

#: States owned by other parts of the pipeline. No command may move to one.
WRITTEN_BY_OTHERS = {"pending_approval", "clarification", "building"}


def plan_labels(current, actions, labels, markers=()):
    """The label set after applying `actions` in order.

    `labels` maps a state name to the label this repository uses for it.

    `markers` are the triage attempt markers, dropped by any state move. A
    marker that outlives its episode is a slower version of the bug it prevents
    — the next episode starts with a spent budget and is never retried at all
    (`GK-145`). Re-entering triage clears them for the same reason from the
    other direction: a fresh `/admit` is a new episode and deserves a fresh
    budget (`GK-141`).
    """
    state_labels = set(labels.values())
    dropped = state_labels | set(markers)
    result = list(current)

    for action in actions:
        state = MOVES.get(action.command)
        if state is None:
            continue
        result = [name for name in result if name not in dropped]
        result.append(labels[state])

    return result


def final_state(current, labels):
    """Which state name the issue is in, or None."""
    by_label = {label: state for state, label in labels.items()}
    for name in current:
        if name in by_label:
            return by_label[name]
    return None
