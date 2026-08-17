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

#: Required on every Anthropic API request. Its absence is a 400 before the
#: request reaches the routine at all, which is what made every fire this
#: pipeline sent fail silently (#126).
ANTHROPIC_VERSION = "2023-06-01"

#: The `/fire` endpoint is in research preview behind this dated beta header.
#: Request and response shapes may change under a future one.
ROUTINE_BETA = "experimental-cc-routine-2026-04-01"

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


def _session_url(status, text):
    """The session URL a real `routine_fire` carries, or `None`.

    Proof that a session was actually created, rather than that something
    answered. Returning `None` for every other shape is what keeps a
    misdirected endpoint from reporting success.
    """
    if not 200 <= status < 300:
        return None
    try:
        parsed = json.loads(text or "")
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed.get("claude_code_session_url") or None


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

        # Freeform prose, not a structured record: the endpoint takes a `text`
        # payload and the routine parses the issue number back out of an
        # untrusted wrapper. A `{"repository", "issue"}` object is not a shape
        # the endpoint accepts.
        body = json.dumps(
            {"text": f"Run triage on issue #{int(issue)} in {repository}."}
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-beta": ROUTINE_BETA,
        }

        try:
            status, text = self._transport(self._endpoint, headers, body)
        except Exception as error:  # noqa: BLE001 - nothing may escape
            return FireResult(True, failed=True, detail=self._scrub(str(error)))

        session_url = _session_url(status, text)
        if session_url is None:
            # Not "not 2xx": a 2xx that is not a `routine_fire` means the
            # endpoint is not the one we think it is, and reporting that as
            # fired is how a broken wire passes for a working one.
            return FireResult(
                True, failed=True, detail=f"status {status}: {self._scrub(text)}"
            )

        return FireResult(attempted=True, detail=session_url)

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
