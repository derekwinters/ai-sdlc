"""GK-110 to GK-119 — what a successful command sets in motion.

Two effects: analysis is fired when an issue newly enters triage, and the
dashboard is re-rendered once when labels changed. Both are guarded so that a
run which changed nothing costs nothing.
"""

import unittest

import _gatekeeper  # noqa: F401
from downstream import (
    ANTHROPIC_VERSION,
    ROUTINE_BETA,
    Fire,
    fires_triage,
    should_rerender,
)

TRIAGE = "ai-triage-queued"


class TestFiringAnalysis(unittest.TestCase):
    def test_newly_adding_triage_fires(self):  # GK-110
        self.assertTrue(fires_triage([], [TRIAGE], triage_label=TRIAGE))

    def test_an_idempotent_re_add_does_not(self):  # GK-111
        self.assertFalse(fires_triage([TRIAGE], [TRIAGE], triage_label=TRIAGE))

    def test_removing_triage_does_not(self):  # GK-112
        self.assertFalse(fires_triage([TRIAGE], [], triage_label=TRIAGE))

    def test_no_change_does_not(self):  # GK-111
        self.assertFalse(fires_triage(["parked"], ["parked"], triage_label=TRIAGE))

    def test_moving_from_another_state_into_triage_fires(self):  # GK-110
        self.assertTrue(fires_triage(["parked"], [TRIAGE], triage_label=TRIAGE))

    def test_other_labels_changing_alongside_do_not_matter(self):  # GK-110
        self.assertTrue(fires_triage(["area:x"], [TRIAGE, "area:x"], triage_label=TRIAGE))

    def test_the_label_name_comes_from_configuration(self):  # GK-110
        self.assertTrue(fires_triage([], ["queued"], triage_label="queued"))


class TestRerendering(unittest.TestCase):
    def test_a_label_change_rerenders(self):  # GK-114
        self.assertTrue(should_rerender(["a"], ["b"]))

    def test_no_label_change_does_not(self):  # GK-115
        self.assertFalse(should_rerender(["a"], ["a"]))

    def test_order_alone_is_not_a_change(self):  # GK-115
        self.assertFalse(should_rerender(["a", "b"], ["b", "a"]))

    def test_a_removal_is_a_change(self):  # GK-114
        self.assertTrue(should_rerender(["a", "b"], ["a"]))


class TestTheFireIsBestEffort(unittest.TestCase):
    """GK-117 to GK-119 — a routine that cannot be reached must not fail the run.

    The gatekeeper's job is the label move. Analysis running late is an
    inconvenience; a failed workflow run on a label move is a broken pipeline.
    """

    def test_an_unconfigured_endpoint_is_a_notice_not_an_error(self):  # GK-119
        result = Fire(endpoint=None, token=None).send(issue=7, repository="o/r")
        self.assertFalse(result.attempted)
        self.assertFalse(result.failed)

    def test_a_missing_token_is_also_a_notice(self):  # GK-119
        result = Fire(endpoint="https://example.com", token=None).send(7, "o/r")
        self.assertFalse(result.attempted)
        self.assertFalse(result.failed)

    def test_a_transport_failure_is_reported_not_raised(self):  # GK-117
        def explode(*_args, **_kwargs):
            raise OSError("no route to host")

        result = Fire("https://example.com", "t", transport=explode).send(7, "o/r")
        self.assertTrue(result.failed)

    def test_a_failure_carries_a_reason(self):  # GK-117
        def explode(*_args, **_kwargs):
            raise OSError("no route to host")

        result = Fire("https://example.com", "t", transport=explode).send(7, "o/r")
        self.assertIn("no route to host", result.detail)

    def test_a_non_2xx_is_reported_not_raised(self):  # GK-117
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (404, "nope")).send(7, "o/r")
        self.assertTrue(result.failed)

    def test_a_real_fire_succeeds(self):  # GK-117
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (200, ROUTINE_FIRE)).send(7, "o/r")
        self.assertTrue(result.attempted)
        self.assertFalse(result.failed)

    def test_the_body_snippet_is_bounded(self):  # GK-117
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (500, "x" * 10_000)).send(7, "o/r")
        self.assertLess(len(result.detail), 1_000)


class TestNothingSecretIsLogged(unittest.TestCase):
    def test_the_detail_never_contains_the_endpoint(self):  # GK-118
        result = Fire("https://secret.example.com/hook", "t",
                      transport=lambda *a, **k: (500, "boom")).send(7, "o/r")
        self.assertNotIn("secret.example.com", result.detail)

    def test_the_detail_never_contains_the_token(self):  # GK-118
        result = Fire("https://example.com", "s3cret-token",
                      transport=lambda *a, **k: (500, "boom")).send(7, "o/r")
        self.assertNotIn("s3cret-token", result.detail)

    def test_the_repr_contains_neither(self):  # GK-118
        fire = Fire("https://secret.example.com/hook", "s3cret-token")
        self.assertNotIn("secret.example.com", repr(fire))
        self.assertNotIn("s3cret-token", repr(fire))

    def test_a_transport_error_mentioning_the_url_is_still_scrubbed(self):  # GK-118
        def explode(*_args, **_kwargs):
            raise OSError("failed to reach https://secret.example.com/hook")

        result = Fire("https://secret.example.com/hook", "t", transport=explode).send(7, "o/r")
        self.assertNotIn("secret.example.com", result.detail)


#: What the endpoint actually returns when a session was created.
ROUTINE_FIRE = (
    '{"type": "routine_fire", "claude_code_session_id": "session_01X", '
    '"claude_code_session_url": "https://claude.ai/code/session_01X"}'
)


def _records(sent, response=(200, ROUTINE_FIRE)):
    """A transport that captures the request and returns a canned response."""

    def record(url, headers, body):
        sent.update(url=url, headers=headers, body=body)
        return response

    return record


class TestTheRequest(unittest.TestCase):
    def test_it_names_the_repository_and_issue(self):  # GK-110
        sent = {}
        Fire("https://example.com", "t", transport=_records(sent)).send(7, "owner/repo")
        self.assertIn("owner/repo", sent["body"])
        self.assertIn("7", sent["body"])

    def test_it_carries_the_api_version_header(self):  # GK-123
        """Without this the endpoint answers 400 and the routine never runs.

        This is not a detail of one deployment: `anthropic-version` is required
        on every Anthropic API request, so its absence failed every fire this
        pipeline has ever sent.
        """
        sent = {}
        Fire("https://example.com", "t", transport=_records(sent)).send(7, "owner/repo")
        self.assertEqual(sent["headers"]["anthropic-version"], ANTHROPIC_VERSION)

    def test_it_carries_the_research_preview_beta_header(self):  # GK-123
        sent = {}
        Fire("https://example.com", "t", transport=_records(sent)).send(7, "owner/repo")
        self.assertEqual(sent["headers"]["anthropic-beta"], ROUTINE_BETA)

    def test_it_still_authenticates_with_the_bearer_token(self):  # GK-123
        sent = {}
        Fire("https://example.com", "tok", transport=_records(sent)).send(7, "owner/repo")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer tok")

    def test_the_body_is_the_routines_freeform_text_payload(self):  # GK-124
        """The endpoint takes `{"text": ...}`, not a structured record.

        The routine parses the issue number back out of an untrusted wrapper,
        so the payload is prose naming the repository and the issue.
        """
        import json

        sent = {}
        Fire("https://example.com", "t", transport=_records(sent)).send(7, "owner/repo")
        body = json.loads(sent["body"])
        self.assertEqual(list(body), ["text"])
        self.assertIn("owner/repo", body["text"])
        self.assertIn("7", body["text"])


class TestOnlyARealFireIsSuccess(unittest.TestCase):
    """GK-125 — a 2xx is not proof that a session was created.

    `urlopen` raises only on 4xx/5xx, so "2xx ⇒ fired" reported success for a
    misdirected endpoint that returned a 200 HTML page. Success requires the
    endpoint's own `routine_fire` answer.
    """

    def test_a_routine_fire_response_is_success(self):  # GK-125
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (200, ROUTINE_FIRE)).send(7, "o/r")
        self.assertTrue(result.attempted)
        self.assertFalse(result.failed)

    def test_the_session_url_is_never_reported(self):  # GK-126
        """A session link is private, and a workflow log is not.

        Every repository adopting this pipeline is public, so anything the
        run prints is readable by anyone. Verifying the `routine_fire` shape
        is what makes success truthful; carrying the link back out of that
        check is what published it.
        """
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (200, ROUTINE_FIRE)).send(7, "o/r")
        self.assertNotIn("claude.ai", result.detail or "")
        self.assertNotIn("session_01X", result.detail or "")

    def test_a_2xx_carrying_no_session_url_is_a_failure(self):  # GK-125
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (202, "{}")).send(7, "o/r")
        self.assertTrue(result.failed)

    def test_a_2xx_html_page_is_a_failure(self):  # GK-125
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (200, "<!doctype html><html>")).send(7, "o/r")
        self.assertTrue(result.failed)

    def test_an_unparseable_2xx_body_is_a_failure(self):  # GK-125
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (200, "not json at all")).send(7, "o/r")
        self.assertTrue(result.failed)

    def test_the_failure_still_names_the_status(self):  # GK-125
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (202, "{}")).send(7, "o/r")
        self.assertIn("202", result.detail)

    def test_a_failing_response_carrying_a_session_link_is_scrubbed(self):  # GK-126
        """The leak that survives deleting the success path.

        `_session_url` returns `None` for any non-2xx, so the run falls to the
        failure branch and reports the raw body. A response that failed *after*
        creating a session would carry the link straight into the log, and
        `_scrub` only knew about the endpoint and the token.
        """
        body = ('{"type": "routine_fire", '
                '"claude_code_session_url": "https://claude.ai/code/session_01X", '
                '"error": "downstream timeout"}')
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (503, body)).send(7, "o/r")
        self.assertTrue(result.failed)
        self.assertNotIn("claude.ai", result.detail)
        self.assertNotIn("session_01X", result.detail)
        # Still says enough to act on.
        self.assertIn("503", result.detail)


class TestReportingTheOutcome(unittest.TestCase):
    """GK-121 — a run says whether it fired, and why not when it did not.

    A run that fired the routine and one that silently skipped it produced
    byte-identical logs, so "working", "rejected", "unwired" and "no routine
    at all" were indistinguishable. That is why #118 survived from adoption
    until somebody noticed triage had never run.
    """

    def test_a_fired_run_says_so(self):  # GK-121
        from downstream import FireResult, fire_summary

        self.assertIn("fired", fire_summary(FireResult(attempted=True)).lower())

    def test_a_fired_run_never_names_the_session_it_created(self):  # GK-126
        """Belt to `test_the_session_url_is_never_reported`'s suspenders.

        Even handed a result that somehow carries a link, the summary must not
        print it — the guarantee is about what reaches the log, so the last
        thing before the log is the right place to enforce it too.
        """
        from downstream import FireResult, fire_summary

        line = fire_summary(
            FireResult(attempted=True, detail="https://claude.ai/code/session_01X")
        )
        self.assertNotIn("claude.ai", line)
        self.assertNotIn("session_01X", line)
        self.assertIn("fired", line.lower())

    def test_a_fired_run_without_a_url_still_reads_cleanly(self):  # GK-121
        from downstream import FireResult, fire_summary

        self.assertEqual(
            fire_summary(FireResult(attempted=True)),
            "triage: fired the analysis routine",
        )

    def test_a_failure_says_why(self):  # GK-121
        from downstream import FireResult, fire_summary

        line = fire_summary(FireResult(True, failed=True, detail="502 from the endpoint"))
        self.assertIn("502 from the endpoint", line)

    def test_an_unconfigured_routine_is_named_as_such(self):  # GK-121
        """GK-119 keeps this a notice rather than an error.

        It must still be *visible*, or a deliberate absence and a broken wire
        read the same.
        """
        from downstream import Fire, fire_summary

        line = fire_summary(Fire(None, None).send(7, "owner/repo"))
        self.assertIn("no analysis routine", line.lower())

    def test_not_a_triage_transition_is_distinguished(self):  # GK-121
        from downstream import NOT_TRIAGE, fire_summary

        self.assertIn("no triage transition", fire_summary(NOT_TRIAGE).lower())

    def test_a_result_is_falsy_when_it_did_not_fire(self):  # GK-121
        """So `result.fired` keeps meaning what four existing tests assert."""
        from downstream import FireResult

        self.assertFalse(FireResult(attempted=False))
        self.assertTrue(FireResult(attempted=True))
