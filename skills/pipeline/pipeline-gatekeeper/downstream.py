#!/usr/bin/env python3
"""What a successful command sets in motion.

Two effects, both guarded so a run that changed nothing costs nothing.

Analysis fires when an issue *newly* enters triage. The transition matters, not
the destination: re-applying `/admit` to an issue already in triage must not
start a second analysis, or a repeated command becomes a way to queue work
repeatedly.

The dashboard re-renders once when labels actually changed. Comparing sets
rather than lists means a reordering is not a change.

The fire itself is best-effort by design. The gatekeeper's job is the label
move; analysis running late is an inconvenience, but a failed workflow run on a
label move is a broken pipeline. So every failure is reported and none is
raised — and neither the endpoint nor the token ever reaches a message, because
the failure text is the part most likely to be pasted somewhere public.

Specification: docs/spec/gatekeeper.md (`GK`), §8.
"""

from __future__ import annotations

import json

from lib.github import MAX_DETAIL, post_json

#: Sent so the receiving routine can pin its own behaviour to a known shape.
PAYLOAD_VERSION = 1

#: Below this length a value is not a credential, and replacing every
#: occurrence of it would shred the message instead of protecting anything —
#: a one-character token turns "no route to host" into nonsense. Real bearer
#: tokens and URLs are far longer than this.
MIN_SECRET_LENGTH = 8


def fires_triage(before, after, triage_label):
    """True only when this change newly puts the issue into triage."""
    return triage_label not in set(before) and triage_label in set(after)


def should_rerender(before, after):
    """True when the label set actually changed. Order is not a change."""
    return set(before) != set(after)


class FireResult:
    __slots__ = ("attempted", "failed", "detail")

    def __init__(self, attempted, failed=False, detail=""):
        self.attempted = attempted
        self.failed = failed
        self.detail = detail

    def __bool__(self):
        """Truthy when the routine was actually asked.

        So `result.fired` reads as "did it fire", while the object still
        carries why it did not.
        """
        return bool(self.attempted)

    def __repr__(self):
        return f"<FireResult attempted={self.attempted} failed={self.failed}>"


#: The outcome when a run never reached the question — the labels did not
#: move an issue into triage, so there was nothing to fire about.
NOT_TRIAGE = FireResult(attempted=False, detail="no triage transition")


def fire_summary(fired):
    """One line saying what happened to the analysis routine.

    Every branch says something. A run that fired and a run that silently
    skipped used to produce identical logs, which left "working", "rejected",
    "unwired" and "no routine at all" indistinguishable from the outside.
    """
    if fired is None:
        return "triage: not evaluated"
    if fired.attempted and fired.failed:
        return f"triage: fired and FAILED — {fired.detail}"
    if fired.attempted:
        return "triage: fired the analysis routine"
    return f"triage: not fired — {fired.detail or 'no reason recorded'}"


class Fire:
    """Asks the analysis routine to look at an issue. Never fails the run."""

    __slots__ = ("_endpoint", "_token", "_transport")

    def __init__(self, endpoint, token, transport=None):
        self._endpoint = endpoint
        self._token = token
        self._transport = transport or post_json

    def __repr__(self):
        # Neither value, ever: a repr reaches logs and exception chains.
        return f"<Fire configured={bool(self._endpoint and self._token)}>"

    def send(self, issue, repository):
        if not self._endpoint or not self._token:
            # Not configured is a notice, not an error: a repository may run
            # the pipeline without an analysis routine at all. It still has to
            # be *said*, or a deliberate absence and a broken wire read the
            # same — which is how #118 survived from adoption (#121).
            return FireResult(attempted=False, detail="no analysis routine configured")

        body = json.dumps(
            {"version": PAYLOAD_VERSION, "repository": repository, "issue": int(issue)}
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

        try:
            status, text = self._transport(self._endpoint, headers, body)
        except Exception as error:  # noqa: BLE001 - nothing may escape
            return FireResult(True, failed=True, detail=self._scrub(str(error)))

        if not 200 <= status < 300:
            return FireResult(
                True, failed=True, detail=f"status {status}: {self._scrub(text)}"
            )

        return FireResult(attempted=True)

    def _scrub(self, text):
        """Remove the endpoint and token, then bound the length.

        A transport error routinely quotes the URL it failed to reach, so
        scrubbing the message is not paranoia — it is the common case.
        """
        cleaned = text or ""
        for secret in (self._endpoint, self._token):
            if secret and len(secret) >= MIN_SECRET_LENGTH:
                cleaned = cleaned.replace(secret, "<redacted>")
        return cleaned[:MAX_DETAIL]
